"""BA2 archive packer for Bethesda games under Proton.

Packs loose mod files into BA2 archives using BSArch (Windows CLI)
executed via the game's Proton installation.  Textures (.dds) are
packed into separate archives with DX10 compression.

Usage::

    packer = BA2Packer(game_plugin, instance_path)
    if packer.is_available():
        result = packer.pack_all_mods(enabled_mods)

The ``anvil_`` prefix on all generated BA2 filenames guarantees safe
cleanup — original game archives are never touched.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from configparser import ConfigParser
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QSettings


# ── Constants ────────────────────────────────────────────────────────

BA2_PREFIX = "anvil_"

# Extensions that are always deployed as symlinks (never packed)
_SYMLINK_EXTENSIONS = {
    ".esp", ".esm", ".esl",   # plugins
    ".dll", ".exe",            # script extenders / binaries
    ".ini", ".cfg", ".toml",   # config files
    ".ba2", ".bsa",            # existing archives
}

_TEXTURE_EXTENSIONS = {".dds"}

# Characters illegal in Windows filenames
_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*]')


# ── Result dataclasses ───────────────────────────────────────────────

@dataclass
class PackResult:
    """Result of packing a single mod."""
    mod_name: str = ""
    ba2_paths: list[str] = field(default_factory=list)
    general_files: int = 0
    texture_files: int = 0
    skipped_files: int = 0
    success: bool = True
    error: str = ""


@dataclass
class PackAllResult:
    """Result of packing all mods."""
    ba2_paths: list[str] = field(default_factory=list)
    mods_packed: int = 0
    mods_skipped: int = 0
    total_general: int = 0
    total_textures: int = 0
    errors: list[str] = field(default_factory=list)
    success: bool = True


# ── Helper ───────────────────────────────────────────────────────────

def _sanitize_name(name: str) -> str:
    """Sanitize a mod name for use as a BA2 filename.

    Removes Windows-illegal characters, collapses whitespace/underscores,
    and truncates to 200 chars.
    """
    clean = _ILLEGAL_CHARS.sub("", name)
    clean = re.sub(r"[\s_]+", " ", clean).strip()
    return clean[:200]


def _classify_file(rel_path: Path) -> str:
    """Classify a file as 'skip', 'texture', or 'general'."""
    ext = rel_path.suffix.lower()
    if ext in _SYMLINK_EXTENSIONS:
        return "skip"
    if ext in _TEXTURE_EXTENSIONS:
        return "texture"
    return "general"


# ── BA2Packer ────────────────────────────────────────────────────────

class BA2Packer:
    """Pack mod files into BA2 archives using BSArch via Proton."""

    def __init__(
        self,
        game_plugin,
        instance_path: Path,
        bsarch_path: Path | None = None,
    ) -> None:
        self._plugin = game_plugin
        self._instance_path = instance_path
        self._mods_path = instance_path / ".mods"
        self._game_path: Path | None = game_plugin.gameDirectory()
        self._data_path = self._game_path / (game_plugin.GameDataPath or "") if self._game_path else None
        self._bsarch_override = bsarch_path

    # ── BSArch finden ────────────────────────────────────────────────

    def find_bsarch(self) -> Path | None:
        """Locate the BSArch.exe binary.

        Search order:
        1. Explicit path (constructor parameter)
        2. QSettings ``Tools/bsarch_path``
        3. Instance tools: ``.tools/BSArch.exe``
        4. Global tools: ``~/.local/share/anvil-organizer/tools/BSArch.exe``
        """
        # 1) Explicit
        if self._bsarch_override and self._bsarch_override.is_file():
            return self._bsarch_override

        # 2) QSettings
        settings = QSettings()
        stored = settings.value("Tools/bsarch_path", "")
        if stored and Path(stored).is_file():
            return Path(stored)

        # 3) Instance tools
        instance_tool = self._instance_path / ".tools" / "BSArch.exe"
        if instance_tool.is_file():
            return instance_tool

        # 4) Global tools
        global_tool = (
            Path.home() / ".local" / "share" / "anvil-organizer"
            / "tools" / "BSArch.exe"
        )
        if global_tool.is_file():
            return global_tool

        return None

    # ── Proton environment ───────────────────────────────────────────

    def _get_proton_env(self) -> tuple[Path, dict] | None:
        """Build environment variables for running BSArch via Proton.

        Returns (proton_script, env_dict) or None if Proton is unavailable.
        """
        proton_info = self._plugin.findProtonRun()
        if proton_info is None:
            return None

        proton_script, compat_data, steam_root = proton_info
        steam_id = self._plugin.GameSteamId
        if isinstance(steam_id, list):
            steam_id = steam_id[0]

        env = os.environ.copy()
        env["STEAM_COMPAT_DATA_PATH"] = str(compat_data)
        env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(steam_root)
        env["SteamAppId"] = str(steam_id)

        return proton_script, env

    # ── Staging ──────────────────────────────────────────────────────

    def _stage_mod_files(
        self, mod_dir: Path, staging_dir: Path
    ) -> tuple[int, int, int]:
        """Copy mod files into staging subdirectories.

        Creates ``staging_dir/general/`` and ``staging_dir/textures/``
        with the appropriate directory structure.

        Returns (general_count, texture_count, skipped_count).
        """
        general_dir = staging_dir / "general"
        textures_dir = staging_dir / "textures"
        general_count = 0
        texture_count = 0
        skipped_count = 0

        for src in mod_dir.rglob("*"):
            if not src.is_file():
                continue
            if src.name in {"meta.ini", "codes.txt"}:
                skipped_count += 1
                continue

            try:
                rel = src.relative_to(mod_dir)
            except ValueError:
                continue

            classification = _classify_file(rel)
            if classification == "skip":
                skipped_count += 1
                continue

            if classification == "texture":
                dest = textures_dir / rel
                texture_count += 1
            else:
                dest = general_dir / rel
                general_count += 1

            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

        return general_count, texture_count, skipped_count

    # ── BSArch execution ─────────────────────────────────────────────

    def _run_bsarch(
        self,
        source_dir: Path,
        output_ba2: Path,
        proton_script: Path,
        env: dict,
        is_textures: bool = False,
    ) -> tuple[bool, str]:
        """Execute BSArch via Proton to create a BA2 archive.

        Returns (success, error_message).
        """
        bsarch = self.find_bsarch()
        if bsarch is None:
            return False, "BSArch.exe not found"

        fmt = self._plugin.Ba2TextureFormat if is_textures else self._plugin.Ba2Format
        if not fmt:
            return False, "No BA2 format configured for this game"

        cmd = [
            str(proton_script), "run",
            str(bsarch),
            "pack",
            str(source_dir),
            str(output_ba2),
            f"-{fmt}",
            "-mt",
        ]

        print(f"[BA2] Running: {' '.join(cmd)}", flush=True)

        try:
            proc = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if proc.returncode != 0:
                stderr = proc.stderr.strip() or proc.stdout.strip()
                return False, f"BSArch exited with code {proc.returncode}: {stderr}"
            print(f"[BA2] Created: {output_ba2.name}", flush=True)
            return True, ""
        except subprocess.TimeoutExpired:
            return False, f"BSArch timed out after 300s for {output_ba2.name}"
        except OSError as exc:
            return False, f"Failed to run BSArch: {exc}"

    # ── Public API ───────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Return True if BSArch and Proton are both available."""
        return self.find_bsarch() is not None and self._get_proton_env() is not None

    def pack_mod(
        self,
        mod_name: str,
        proton_script: Path,
        env: dict,
    ) -> PackResult:
        """Pack a single mod into 0-2 BA2 archives.

        Creates ``anvil_<name>.ba2`` (general assets) and/or
        ``anvil_<name> - Textures.ba2`` (DDS textures) in the
        game's Data directory.
        """
        result = PackResult(mod_name=mod_name)
        mod_dir = self._mods_path / mod_name

        if not mod_dir.is_dir():
            result.error = f"Mod directory not found: {mod_dir}"
            result.success = False
            return result

        if self._data_path is None:
            result.error = "Game data path not available"
            result.success = False
            return result

        safe_name = _sanitize_name(mod_name)
        staging_dir = self._instance_path / ".ba2_staging" / safe_name

        try:
            # Clean previous staging
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            staging_dir.mkdir(parents=True, exist_ok=True)

            # Stage files
            gen_count, tex_count, skip_count = self._stage_mod_files(
                mod_dir, staging_dir
            )
            result.general_files = gen_count
            result.texture_files = tex_count
            result.skipped_files = skip_count

            # Pack general archive
            if gen_count > 0:
                general_dir = staging_dir / "general"
                out_ba2 = self._data_path / f"{BA2_PREFIX}{safe_name}.ba2"
                ok, err = self._run_bsarch(
                    general_dir, out_ba2, proton_script, env, is_textures=False
                )
                if ok:
                    result.ba2_paths.append(str(out_ba2.relative_to(self._game_path)))
                else:
                    result.error = err
                    result.success = False

            # Pack textures archive
            if tex_count > 0:
                textures_dir = staging_dir / "textures"
                out_tex = self._data_path / f"{BA2_PREFIX}{safe_name} - Textures.ba2"
                ok, err = self._run_bsarch(
                    textures_dir, out_tex, proton_script, env, is_textures=True
                )
                if ok:
                    result.ba2_paths.append(str(out_tex.relative_to(self._game_path)))
                else:
                    if not result.error:
                        result.error = err
                    result.success = False

        finally:
            # Cleanup staging
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

        return result

    def pack_all_mods(
        self,
        enabled_mods: list[str],
        profile_name: str = "Default",
    ) -> PackAllResult:
        """Pack all enabled mods into BA2 archives.

        Pre-flight checks BSArch + Proton availability, cleans up
        old ``anvil_*.ba2`` files, then packs each mod.

        Args:
            enabled_mods: List of mod names (in priority order).
            profile_name: Active profile name (unused currently, for future).

        Returns:
            PackAllResult with all generated BA2 paths.
        """
        result = PackAllResult()

        # Pre-flight
        proton_env = self._get_proton_env()
        if proton_env is None:
            result.success = False
            result.errors.append("Proton not available for this game")
            return result

        proton_script, env = proton_env

        if self.find_bsarch() is None:
            result.success = False
            result.errors.append(
                "BSArch.exe not found. Download from Nexus Mods and place in "
                f"{self._instance_path / '.tools'} or "
                "~/.local/share/anvil-organizer/tools/"
            )
            return result

        # Cleanup old anvil BA2s
        cleaned = self.cleanup_ba2s()
        if cleaned > 0:
            print(f"[BA2] Cleaned {cleaned} old anvil_*.ba2 files", flush=True)

        # Abort threshold: stop packing after too many consecutive failures
        _MAX_CONSECUTIVE_ERRORS = 3
        consecutive_errors = 0

        # Pack each mod
        for mod_name in enabled_mods:
            if mod_name.endswith("_separator"):
                continue

            mod_dir = self._mods_path / mod_name
            if not mod_dir.is_dir():
                continue

            # Check if mod has any packable files
            has_packable = False
            for f in mod_dir.rglob("*"):
                if f.is_file() and _classify_file(f.relative_to(mod_dir)) != "skip":
                    has_packable = True
                    break

            if not has_packable:
                result.mods_skipped += 1
                continue

            print(f"[BA2] Packing: {mod_name}", flush=True)
            try:
                pack_result = self.pack_mod(mod_name, proton_script, env)
            except Exception as exc:
                result.errors.append(f"{mod_name}: unexpected error: {exc}")
                result.mods_skipped += 1
                consecutive_errors += 1
                if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    result.errors.append(
                        f"Aborted: {_MAX_CONSECUTIVE_ERRORS} consecutive "
                        "packing failures — BSArch or Proton may be broken"
                    )
                    break
                continue

            if pack_result.success:
                result.ba2_paths.extend(pack_result.ba2_paths)
                result.mods_packed += 1
                result.total_general += pack_result.general_files
                result.total_textures += pack_result.texture_files
                consecutive_errors = 0
            else:
                result.errors.append(
                    f"{mod_name}: {pack_result.error}"
                )
                result.mods_skipped += 1
                consecutive_errors += 1
                if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    result.errors.append(
                        f"Aborted: {_MAX_CONSECUTIVE_ERRORS} consecutive "
                        "packing failures — BSArch or Proton may be broken"
                    )
                    break

        print(
            f"[BA2] Done: {result.mods_packed} mods packed, "
            f"{len(result.ba2_paths)} archives created, "
            f"{len(result.errors)} errors",
            flush=True,
        )

        if result.errors:
            result.success = False

        return result

    def cleanup_ba2s(self) -> int:
        """Delete all ``anvil_*.ba2`` files from the game's Data directory.

        Only removes files with the ``anvil_`` prefix — original game
        archives are never touched.

        Returns the number of deleted files.
        """
        if self._data_path is None or not self._data_path.is_dir():
            return 0

        count = 0
        for f in self._data_path.iterdir():
            if (
                f.is_file()
                and f.name.startswith(BA2_PREFIX)
                and f.suffix.lower() in (".ba2", ".bsa")
            ):
                try:
                    f.unlink()
                    count += 1
                except OSError as exc:
                    print(f"[BA2] Failed to delete {f.name}: {exc}", flush=True)
        return count

    # ── INI Management ───────────────────────────────────────────────

    def update_ini(self, ba2_names: list[str]) -> bool:
        """Add anvil BA2 names to the game's Custom INI file.

        Creates a backup (``.anvil_backup``) before modifying.
        Preserves existing non-anvil entries.
        Encoding: CP1252 (Bethesda standard).

        Args:
            ba2_names: List of BA2 filenames (just names, no paths).

        Returns True on success.
        """
        ini_path = self._plugin.ba2_ini_path()
        if ini_path is None:
            return False

        section = self._plugin.Ba2IniSection
        key = self._plugin.Ba2IniKey
        if not section or not key:
            return False

        # Backup
        backup_path = ini_path.parent / f"{ini_path.name}.anvil_backup"
        if ini_path.is_file():
            shutil.copy2(ini_path, backup_path)
            print(f"[BA2] INI backup: {backup_path}", flush=True)

        # Read existing INI (CP1252)
        config = ConfigParser()
        config.optionxform = str  # preserve case
        if ini_path.is_file():
            try:
                config.read(str(ini_path), encoding="cp1252")
            except Exception as exc:
                print(f"[BA2] Warning: could not parse {ini_path}: {exc}", flush=True)

        # Get existing entries, filter out old anvil_ ones
        existing = ""
        if config.has_section(section) and config.has_option(section, key):
            existing = config.get(section, key)
        existing_list = [
            e.strip() for e in existing.split(",")
            if e.strip() and not e.strip().startswith(BA2_PREFIX)
        ]

        # Build new value
        all_entries = existing_list + ba2_names
        new_value = ", ".join(all_entries)

        # Write
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, key, new_value)

        ini_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(ini_path, "w", encoding="cp1252") as f:
                config.write(f)
            print(f"[BA2] INI updated: {key}={new_value}", flush=True)
            return True
        except OSError as exc:
            print(f"[BA2] Failed to write INI: {exc}", flush=True)
            return False

    def restore_ini(self) -> bool:
        """Restore the game's Custom INI from the ``.anvil_backup``.

        If no backup exists, removes only ``anvil_*`` entries from the
        current INI instead.

        Returns True on success.
        """
        ini_path = self._plugin.ba2_ini_path()
        if ini_path is None:
            return False

        backup_path = ini_path.parent / f"{ini_path.name}.anvil_backup"

        # Try restoring from backup
        if backup_path.is_file():
            try:
                shutil.copy2(backup_path, ini_path)
                backup_path.unlink()
                print(f"[BA2] INI restored from backup", flush=True)
                return True
            except OSError as exc:
                print(f"[BA2] Failed to restore INI backup: {exc}", flush=True)

        # Fallback: strip anvil_ entries from current INI
        if not ini_path.is_file():
            return True

        section = self._plugin.Ba2IniSection
        key = self._plugin.Ba2IniKey
        if not section or not key:
            return False

        config = ConfigParser()
        config.optionxform = str
        try:
            config.read(str(ini_path), encoding="cp1252")
        except Exception:
            return False

        if config.has_section(section) and config.has_option(section, key):
            existing = config.get(section, key)
            cleaned = [
                e.strip() for e in existing.split(",")
                if e.strip() and not e.strip().startswith(BA2_PREFIX)
            ]
            if cleaned:
                config.set(section, key, ", ".join(cleaned))
            else:
                config.remove_option(section, key)

            try:
                with open(ini_path, "w", encoding="cp1252") as f:
                    config.write(f)
                print(f"[BA2] INI cleaned (anvil_ entries removed)", flush=True)
                return True
            except OSError:
                return False

        return True
