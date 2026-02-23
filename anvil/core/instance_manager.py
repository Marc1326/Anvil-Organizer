"""Instance management for Anvil Organizer.

Each instance represents one managed game with its own mod directory,
download folder, profiles, and overwrite directory.  Instance metadata
is stored in a ``.anvil.ini`` file (QSettings INI format).

Default base path: ``~/.anvil-organizer/instances/``

Directory layout per instance::

    ~/.anvil-organizer/instances/<Name>/
    ├── .anvil.ini
    ├── .mods/
    ├── .downloads/
    ├── .profiles/
    │   └── Default/
    │       └── modlist.txt
    └── .overwrite/
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QSettings

from anvil.plugins.base_game import BaseGame

# ── Defaults ──────────────────────────────────────────────────────────

_DEFAULT_BASE = Path.home() / ".anvil-organizer" / "instances"
_CURRENT_FILE = Path.home() / ".anvil-organizer" / ".current"

_SUBDIRS = (".mods", ".downloads", ".profiles", ".overwrite")


class InstanceManager:
    """Create, list, load, switch, and delete game instances."""

    def __init__(self, base_path: Path | None = None) -> None:
        self._base = base_path or _DEFAULT_BASE
        self._base.mkdir(parents=True, exist_ok=True)

    # ── Getters ───────────────────────────────────────────────────────

    def instances_path(self) -> Path:
        """Return the base directory that holds all instances."""
        return self._base

    # ── List ──────────────────────────────────────────────────────────

    def list_instances(self) -> list[dict]:
        """Scan sub-directories for ``.anvil.ini`` and return metadata.

        Returns:
            List of dicts with keys: name, game_name, game_short_name,
            game_path, detected_store, selected_profile, created.
        """
        result: list[dict] = []

        if not self._base.is_dir():
            return result

        for child in sorted(self._base.iterdir()):
            ini = child / ".anvil.ini"
            if not ini.is_file():
                continue

            data = self._read_ini(ini)
            data["name"] = child.name
            result.append(data)

        return result

    # ── Create ────────────────────────────────────────────────────────

    def create_instance(
        self,
        game_plugin: BaseGame,
        name: str | None = None,
        *,
        portable: bool = False,
        local_inis: bool = False,
        local_saves: bool = False,
        auto_archive: bool = False,
        mods_path: str | None = None,
        downloads_path: str | None = None,
        overwrite_path: str | None = None,
    ) -> Path:
        """Create a new instance for *game_plugin*.

        Args:
            game_plugin: A loaded BaseGame plugin (must be installed).
            name: Instance directory name.  Defaults to
                  ``game_plugin.GameName``.

        Returns:
            Path to the newly created instance directory.

        Raises:
            FileExistsError: If the instance directory already exists.
        """
        name = name or game_plugin.GameName
        instance_dir = self._base / name

        if instance_dir.exists():
            raise FileExistsError(
                f"Instance directory already exists: {instance_dir}"
            )

        # Create directory tree
        instance_dir.mkdir(parents=True)
        for sub in _SUBDIRS:
            (instance_dir / sub).mkdir()

        # Default profile
        default_profile = instance_dir / ".profiles" / "Default"
        default_profile.mkdir()
        (default_profile / "modlist.txt").write_text(
            "# Anvil Organizer mod list\n"
            "# +ModName = enabled, -ModName = disabled\n",
            encoding="utf-8",
        )

        # Write .anvil.ini
        ini_path = instance_dir / ".anvil.ini"
        self._write_ini(
            ini_path,
            game_plugin,
            instance_dir,
            portable=portable,
            local_inis=local_inis,
            local_saves=local_saves,
            auto_archive=auto_archive,
            mods_path=mods_path,
            downloads_path=downloads_path,
            overwrite_path=overwrite_path,
        )

        return instance_dir

    # ── Rename ─────────────────────────────────────────────────────────

    def rename_instance(self, old_name: str, new_name: str) -> bool:
        """Rename an instance directory.

        Args:
            old_name: Current instance name.
            new_name: New instance name.

        Returns:
            True if renamed, False if failed or name collision.
        """
        old_dir = self._base / old_name
        new_dir = self._base / new_name

        if not old_dir.is_dir() or new_dir.exists():
            return False

        try:
            old_dir.rename(new_dir)
        except OSError:
            return False

        # Update .current if needed
        if self.current_instance() == old_name:
            self.set_current_instance(new_name)

        return True

    # ── Delete ────────────────────────────────────────────────────────

    def delete_instance(self, name: str) -> bool:
        """Delete an instance by name.

        Removes the entire instance directory tree.  The caller is
        responsible for showing a confirmation dialog beforehand.

        Returns:
            True if deleted, False if the directory didn't exist.
        """
        instance_dir = self._base / name

        if not instance_dir.is_dir():
            return False

        try:
            shutil.rmtree(instance_dir)
        except OSError as exc:
            print(
                f"instance_manager: failed to delete {instance_dir}: {exc}",
                file=sys.stderr,
            )
            return False

        # Clear .current if it pointed to this instance
        if self.current_instance() == name:
            self._current_file().unlink(missing_ok=True)

        return True

    def get_objects_for_deletion(self, name: str) -> list[tuple[str, int]]:
        """Return list of (path, size) for deletion confirmation dialog.

        Args:
            name: Instance name.

        Returns:
            List of tuples (path_str, size_bytes) for each sub-directory
            and the .anvil.ini file.
        """
        instance_dir = self._base / name
        if not instance_dir.is_dir():
            return []

        result: list[tuple[str, int]] = []

        for sub in _SUBDIRS:
            sub_path = instance_dir / sub
            if sub_path.is_dir():
                size = sum(
                    f.stat().st_size for f in sub_path.rglob("*") if f.is_file()
                )
                result.append((str(sub_path), size))

        ini = instance_dir / ".anvil.ini"
        if ini.is_file():
            result.append((str(ini), ini.stat().st_size))

        return result

    # ── Instance Type ──────────────────────────────────────────────────

    def is_portable(self, name: str) -> bool:
        """Check if instance is portable (stored in app directory).

        Args:
            name: Instance name.

        Returns:
            True if portable, False if global.
        """
        # Check .anvil.ini for portable flag
        ini = self._base / name / ".anvil.ini"
        if ini.is_file():
            s = QSettings(str(ini), QSettings.Format.IniFormat)
            s.beginGroup("General")
            portable = s.value("portable", False, type=bool)
            s.endGroup()
            return portable
        return False

    def get_instance_type(self, name: str) -> str:
        """Return 'portable' or 'global' for the given instance.

        Args:
            name: Instance name.

        Returns:
            'portable' or 'global'.
        """
        return "portable" if self.is_portable(name) else "global"

    # ── Load ──────────────────────────────────────────────────────────

    def load_instance(self, name: str) -> dict:
        """Load an instance's config from ``.anvil.ini``.

        Args:
            name: Instance directory name.

        Returns:
            Dict with all config values.  Empty dict if not found.
        """
        ini = self._base / name / ".anvil.ini"
        if not ini.is_file():
            return {}

        data = self._read_ini(ini)
        data["name"] = name
        return data

    def save_instance(self, name: str, data: dict) -> None:
        """Save updated instance config to ``.anvil.ini``.

        Args:
            name: Instance directory name.
            data: Dict with config values to update.
        """
        ini = self._base / name / ".anvil.ini"
        if not ini.is_file():
            return

        s = QSettings(str(ini), QSettings.Format.IniFormat)

        s.beginGroup("General")
        if "selected_profile" in data:
            s.setValue("selected_profile", data["selected_profile"])
        if "game_path" in data:
            s.setValue("game_path", data["game_path"])
        if "local_inis" in data:
            s.setValue("local_inis", data["local_inis"])
        if "local_saves" in data:
            s.setValue("local_saves", data["local_saves"])
        s.endGroup()

        s.beginGroup("Paths")
        if "path_downloads_directory" in data:
            s.setValue("downloads_directory", data["path_downloads_directory"])
        if "path_mods_directory" in data:
            s.setValue("mods_directory", data["path_mods_directory"])
        if "path_profiles_directory" in data:
            s.setValue("profiles_directory", data["path_profiles_directory"])
        if "path_overwrite_directory" in data:
            s.setValue("overwrite_directory", data["path_overwrite_directory"])
        s.endGroup()

        s.sync()

    # ── Current instance ──────────────────────────────────────────────

    def current_instance(self) -> str | None:
        """Return the name of the currently active instance.

        Reads from ``~/.anvil-organizer/.current``.

        Returns:
            Instance name, or None if not set or file missing.
        """
        f = self._current_file()
        if not f.is_file():
            return None

        text = f.read_text(encoding="utf-8").strip()
        if not text:
            return None

        # Verify the instance still exists
        if not (self._base / text / ".anvil.ini").is_file():
            return None

        return text

    def set_current_instance(self, name: str) -> None:
        """Set the currently active instance.

        Args:
            name: Instance directory name.
        """
        f = self._current_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(name + "\n", encoding="utf-8")

    # ── Internal helpers ──────────────────────────────────────────────

    def _current_file(self) -> Path:
        """Path to the .current file (respects custom base_path)."""
        return self._base.parent / ".current"

    @staticmethod
    def _write_ini(
        ini_path: Path,
        game_plugin: BaseGame,
        instance_dir: Path,
        *,
        portable: bool = False,
        local_inis: bool = False,
        local_saves: bool = False,
        auto_archive: bool = False,
        mods_path: str | None = None,
        downloads_path: str | None = None,
        overwrite_path: str | None = None,
    ) -> None:
        """Write .anvil.ini with QSettings."""
        s = QSettings(str(ini_path), QSettings.Format.IniFormat)

        s.beginGroup("General")
        s.setValue("game_name", game_plugin.GameName)
        s.setValue("game_short_name", game_plugin.GameShortName)
        gd = game_plugin.gameDirectory()
        s.setValue("game_path", str(gd) if gd else "")
        s.setValue("detected_store", game_plugin.detectedStore() or "")
        s.setValue("selected_profile", "Default")
        s.setValue("created", datetime.now(timezone.utc).isoformat())
        s.setValue("portable", portable)
        s.setValue("local_inis", local_inis)
        s.setValue("local_saves", local_saves)
        s.setValue("auto_archive", auto_archive)
        s.endGroup()

        s.beginGroup("Paths")
        s.setValue("mods_directory", mods_path or "%INSTANCE_DIR%/.mods")
        s.setValue("downloads_directory", downloads_path or "%INSTANCE_DIR%/.downloads")
        s.setValue("profiles_directory", "%INSTANCE_DIR%/.profiles")
        s.setValue("overwrite_directory", overwrite_path or "%INSTANCE_DIR%/.overwrite")
        s.endGroup()

        s.sync()

    @staticmethod
    def _read_ini(ini_path: Path) -> dict:
        """Read .anvil.ini and return a flat dict."""
        s = QSettings(str(ini_path), QSettings.Format.IniFormat)

        data: dict[str, str] = {}

        s.beginGroup("General")
        for key in s.childKeys():
            data[key] = str(s.value(key, ""))
        s.endGroup()

        s.beginGroup("Paths")
        for key in s.childKeys():
            data[f"path_{key}"] = str(s.value(key, ""))
        s.endGroup()

        return data

    # ── Repr ──────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        count = len(self.list_instances())
        current = self.current_instance()
        return (
            f"<InstanceManager instances={count} "
            f"current={current!r} path={self._base}>"
        )
