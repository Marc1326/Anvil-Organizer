"""ReShade management for Anvil Organizer.

Handles detection, installation, removal and preset management of
ReShade post-processing injector for games.

ReShade is deployed directly into the game root directory:
- A renamed DLL (dxgi.dll / d3d9.dll / opengl32.dll depending on the API)
- A ReShade.ini configuration file
- Optional preset files (.ini / .txt)
"""

from __future__ import annotations

import configparser
import shutil
from pathlib import Path

# Map of supported render APIs to the DLL filename that ReShade uses.
API_DLL_MAP: dict[str, str] = {
    "dx9": "d3d9.dll",
    "dx11": "dxgi.dll",
    "dx12": "dxgi.dll",
    "opengl": "opengl32.dll",
}

# Human-readable labels for the API dropdown.
API_LABELS: dict[str, str] = {
    "dx9": "DirectX 9",
    "dx11": "DirectX 10/11",
    "dx12": "DirectX 12",
    "opengl": "OpenGL",
}


class ReshadeManager:
    """Manage ReShade installation for a single game instance.

    Args:
        game_path: Absolute path to the game root directory.
        game_binary: Relative path to the game executable
                     (e.g. ``bin/x64/Cyberpunk2077.exe``).
    """

    def __init__(self, game_path: Path, game_binary: str) -> None:
        self._game_path = game_path
        self._game_binary = game_binary
        # ReShade files live next to the game binary
        self._binary_dir = game_path / Path(game_binary).parent

    # ── Detection ─────────────────────────────────────────────────────

    def detect_installed(self) -> dict | None:
        """Check whether ReShade is currently installed.

        Returns:
            A dict with keys ``api``, ``dll_name``, ``dll_path``,
            ``ini_path`` if found, or ``None``.
        """
        for api, dll_name in API_DLL_MAP.items():
            dll_path = self._binary_dir / dll_name
            if not dll_path.is_file():
                continue
            # Symlinks do not count (those are game/engine originals or
            # mod-deployer links).
            if dll_path.is_symlink():
                continue
            # Check for companion ReShade.ini — that distinguishes a
            # real ReShade install from a plain game DLL.
            ini_path = self._binary_dir / "ReShade.ini"
            if ini_path.is_file():
                return {
                    "api": api,
                    "dll_name": dll_name,
                    "dll_path": str(dll_path),
                    "ini_path": str(ini_path),
                }
        return None

    # ── Installation ──────────────────────────────────────────────────

    def install(
        self,
        source_dll: Path,
        api: str,
        preset_path: Path | None = None,
    ) -> tuple[bool, str]:
        """Install ReShade into the game directory.

        Args:
            source_dll: Path to the ReShade DLL the user downloaded.
            api: Render API key (``dx9``, ``dx11``, ``dx12``, ``opengl``).
            preset_path: Optional preset file to activate after install.

        Returns:
            ``(success, message)`` tuple.
        """
        if api not in API_DLL_MAP:
            return False, f"Unbekannte API: {api}"

        if not source_dll.is_file():
            return False, f"DLL nicht gefunden: {source_dll}"

        dll_name = API_DLL_MAP[api]
        target_dll = self._binary_dir / dll_name

        # Safety: do not overwrite a non-ReShade DLL if ReShade.ini
        # is missing (could be a real game DLL).
        ini_path = self._binary_dir / "ReShade.ini"
        if target_dll.is_file() and not target_dll.is_symlink() and not ini_path.is_file():
            # Backup original DLL
            backup = target_dll.with_suffix(".dll.anvil_backup")
            if not backup.exists():
                shutil.copy2(target_dll, backup)

        # Copy the ReShade DLL
        try:
            self._binary_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_dll, target_dll)
        except OSError as exc:
            return False, f"Konnte DLL nicht kopieren: {exc}"

        # Create / update ReShade.ini
        try:
            self._write_reshade_ini(api, preset_path)
        except OSError as exc:
            return False, f"Konnte ReShade.ini nicht erstellen: {exc}"

        return True, f"ReShade installiert ({API_LABELS.get(api, api)}, {dll_name})"

    def uninstall(self) -> tuple[bool, str]:
        """Remove ReShade from the game directory.

        Removes the ReShade DLL, ReShade.ini, and ReShade log/cache
        files.  Restores a backed-up original DLL if present.

        Returns:
            ``(success, message)`` tuple.
        """
        info = self.detect_installed()
        if info is None:
            return False, "ReShade ist nicht installiert."

        dll_path = Path(info["dll_path"])
        ini_path = Path(info["ini_path"])

        errors: list[str] = []

        # Remove DLL
        try:
            dll_path.unlink()
        except OSError as exc:
            errors.append(f"DLL: {exc}")

        # Restore backup if it exists
        backup = dll_path.with_suffix(".dll.anvil_backup")
        if backup.is_file():
            try:
                backup.rename(dll_path)
            except OSError:
                pass  # Non-critical

        # Remove ReShade.ini
        try:
            if ini_path.is_file():
                ini_path.unlink()
        except OSError as exc:
            errors.append(f"INI: {exc}")

        # Remove ReShade log
        log_path = self._binary_dir / "ReShade.log"
        if log_path.is_file():
            try:
                log_path.unlink()
            except OSError:
                pass  # Non-critical

        if errors:
            return False, "Fehler beim Deinstallieren: " + "; ".join(errors)

        return True, "ReShade wurde deinstalliert."

    # ── Presets ───────────────────────────────────────────────────────

    def list_presets(self) -> list[Path]:
        """Find ReShade preset files in the game binary directory.

        Presets are ``.ini`` or ``.txt`` files that are NOT
        ``ReShade.ini`` itself.
        """
        presets: list[Path] = []
        if not self._binary_dir.is_dir():
            return presets

        for ext in ("*.ini", "*.txt"):
            for f in self._binary_dir.glob(ext):
                name_lower = f.name.lower()
                # Skip ReShade's own files
                if name_lower in ("reshade.ini", "reshade.log"):
                    continue
                # Heuristic: preset files typically contain ReShade
                # shader references.  We include all .ini/.txt for now
                # and let the user manage them.
                # Skip known game config files
                if name_lower in ("dxvk.conf", "steam_appid.txt"):
                    continue
                presets.append(f)
        return sorted(presets, key=lambda p: p.name.lower())

    def get_active_preset(self) -> str | None:
        """Read the active preset path from ReShade.ini.

        Returns:
            The preset filename, or ``None`` if not configured.
        """
        ini_path = self._binary_dir / "ReShade.ini"
        if not ini_path.is_file():
            return None

        cfg = configparser.ConfigParser(strict=False)
        cfg.read(str(ini_path), encoding="utf-8")

        # ReShade uses [GENERAL] PresetPath
        preset = cfg.get("GENERAL", "PresetPath", fallback=None)
        if preset:
            # May be an absolute Windows path or relative — return the
            # filename portion for display purposes.
            return Path(preset).name
        return None

    def set_active_preset(self, preset_name: str) -> tuple[bool, str]:
        """Set the active preset in ReShade.ini.

        Args:
            preset_name: Filename of the preset (must exist in binary dir).

        Returns:
            ``(success, message)`` tuple.
        """
        ini_path = self._binary_dir / "ReShade.ini"
        if not ini_path.is_file():
            return False, "ReShade.ini nicht gefunden."

        preset_file = self._binary_dir / preset_name
        if not preset_file.is_file():
            return False, f"Preset nicht gefunden: {preset_name}"

        cfg = configparser.ConfigParser(strict=False)
        cfg.read(str(ini_path), encoding="utf-8")

        if not cfg.has_section("GENERAL"):
            cfg.add_section("GENERAL")
        # Use a Windows-style relative path (ReShade runs inside Wine)
        cfg.set("GENERAL", "PresetPath", f".\\{preset_name}")

        with open(ini_path, "w", encoding="utf-8") as fh:
            cfg.write(fh)

        return True, f"Preset aktiviert: {preset_name}"

    def add_preset(self, source: Path) -> tuple[bool, str]:
        """Copy a preset file into the game binary directory.

        Args:
            source: Path to the source preset file.

        Returns:
            ``(success, message)`` tuple.
        """
        if not source.is_file():
            return False, f"Datei nicht gefunden: {source}"

        target = self._binary_dir / source.name
        if target.exists():
            return False, f"Preset existiert bereits: {source.name}"

        try:
            shutil.copy2(source, target)
        except OSError as exc:
            return False, f"Konnte Preset nicht kopieren: {exc}"

        return True, f"Preset hinzugefuegt: {source.name}"

    def remove_preset(self, preset_name: str) -> tuple[bool, str]:
        """Remove a preset file from the game binary directory.

        Args:
            preset_name: Filename of the preset to remove.

        Returns:
            ``(success, message)`` tuple.
        """
        target = self._binary_dir / preset_name
        if not target.is_file():
            return False, f"Preset nicht gefunden: {preset_name}"

        # Safety: never delete ReShade.ini itself
        if preset_name.lower() == "reshade.ini":
            return False, "ReShade.ini kann nicht als Preset entfernt werden."

        try:
            target.unlink()
        except OSError as exc:
            return False, f"Konnte Preset nicht loeschen: {exc}"

        return True, f"Preset entfernt: {preset_name}"

    # ── Internal helpers ──────────────────────────────────────────────

    def _write_reshade_ini(
        self, api: str, preset_path: Path | None = None
    ) -> None:
        """Create or update ReShade.ini with sensible defaults."""
        ini_path = self._binary_dir / "ReShade.ini"

        cfg = configparser.ConfigParser(strict=False)
        if ini_path.is_file():
            cfg.read(str(ini_path), encoding="utf-8")

        # [GENERAL]
        if not cfg.has_section("GENERAL"):
            cfg.add_section("GENERAL")
        if preset_path and preset_path.is_file():
            cfg.set("GENERAL", "PresetPath", f".\\{preset_path.name}")

        # [INPUT]
        if not cfg.has_section("INPUT"):
            cfg.add_section("INPUT")
        # Default overlay toggle key: Home
        if not cfg.has_option("INPUT", "KeyOverlay"):
            cfg.set("INPUT", "KeyOverlay", "36,0,0,0")

        with open(ini_path, "w", encoding="utf-8") as fh:
            cfg.write(fh)
