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
        self._write_ini(ini_path, game_plugin, instance_dir)

        return instance_dir

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
        s.endGroup()

        s.beginGroup("Paths")
        s.setValue("mods_directory", "%INSTANCE_DIR%/.mods")
        s.setValue("downloads_directory", "%INSTANCE_DIR%/.downloads")
        s.setValue("profiles_directory", "%INSTANCE_DIR%/.profiles")
        s.setValue("overwrite_directory", "%INSTANCE_DIR%/.overwrite")
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
