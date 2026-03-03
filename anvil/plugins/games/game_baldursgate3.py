"""Baldur's Gate 3 game plugin for Anvil Organizer.

Based on the MO2 basic_games plugin by daescha, adapted for
Linux with Proton prefix support.

Features implemented:
  - Store detection (Steam, GOG)
  - Proton prefix paths for documents, saves, modsettings, pak mods
  - Executable list (Vulkan, DX11, Larian Launcher)
  - BG3-specific path helpers for mod management
  - modsettings.lsx reading and writing (load order)
  - Script Extender detection
  - pak mod scanning with LSPK metadata extraction (UUID, Name, Dependencies)
  - Unregistered mod detection (by UUID + filename)

TODO (future):
  - Dependency-Resolver — sort mods by dependencies from meta.lsx
  - Post-update cache cleanup
"""

from __future__ import annotations

import sys
from pathlib import Path

from anvil.core.bg3_mod_installer import BG3ModInstaller
from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod
from anvil.plugins.games.bg3_mod_handler import (
    BG3ScriptExtender,
    ModsettingsParser,
    ModsettingsWriter,
    find_unregistered_mods,
    read_pak_info,
    scan_pak_mods,
)


class BaldursGate3Game(BaseGame):
    """Baldur's Gate 3 support plugin."""

    # ── Plugin-Metadaten ───────────────────────────────────────────────

    Name = "Baldur's Gate 3 Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # ── Spiel-Attribute ────────────────────────────────────────────────

    GameName = "Baldur's Gate 3"
    GameShortName = "baldursgate3"
    GameBinary = "bin/bg3.exe"
    GameDataPath = ""  # Mods go to various locations depending on type

    GameSteamId = [1086940, 2626479850]
    GameGogId = 1456460669

    GameLauncher = "Launcher/LariLauncher.exe"

    GameDocumentsDirectory = ""  # resolved dynamically via gameDocumentsDirectory()
    GameSavesDirectory = ""     # resolved dynamically via gameSavesDirectory()
    GameSaveExtension = "lsv"

    GameNexusId = 3474
    GameNexusName = "baldursgate3"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Baldur's-Gate-3"
    )

    # ── Windows-Pfade (innerhalb Proton-Prefix) ────────────────────────

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/AppData/Local"
        "/Larian Studios/Baldur's Gate 3"
    )
    _WIN_SAVES_SUBDIR = "Savegames/Story"
    _WIN_PROFILES = (
        "drive_c/users/steamuser/AppData/Local"
        "/Larian Studios/Baldur's Gate 3/PlayerProfiles"
    )
    _WIN_PAK_MODS = (
        "drive_c/users/steamuser/AppData/Local"
        "/Larian Studios/Baldur's Gate 3/Mods"
    )

    # ── DX11-Binary ────────────────────────────────────────────────────

    _DX11_BINARY = "bin/bg3_dx11.exe"

    # ── Überschriebene Methoden ────────────────────────────────────────

    def gameDocumentsDirectory(self) -> Path | None:
        """Return the game's documents directory.

        For Steam (Proton): derived from the Proton prefix.
        For GOG: may be in a Wine prefix managed by Heroic/Lutris.
        Returns None if no prefix is found.
        """
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_DOCUMENTS
            if path.is_dir():
                return path
        return None

    def gameSavesDirectory(self) -> Path | None:
        """Return the save game directory of the active profile.

        Uses the same profile as modsettings_path() (newest mtime).
        Falls back to the Public profile if the active profile has no saves.
        Returns None if no prefix is found.
        """
        ms = self.modsettings_path()
        if ms is not None:
            path = ms.parent / self._WIN_SAVES_SUBDIR
            if path.is_dir() and any(path.glob("*/*.lsv")):
                return path
        # Fallback: Public-Profil pruefen
        profiles = self._profiles_dir()
        if profiles is not None:
            public = profiles / "Public" / self._WIN_SAVES_SUBDIR
            if public.is_dir() and any(public.glob("*/*.lsv")):
                return public
        return None

    def listSaves(self, folder: Path) -> list[Path]:
        """Find BG3 save files (.lsv inside per-save subdirectories)."""
        if not folder.is_dir():
            return []
        return sorted(
            folder.glob("*/*.lsv"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    # ── BG3-spezifische Pfade (Grundlage für Teil 2) ──────────────────

    def _profiles_dir(self) -> Path | None:
        """Return the PlayerProfiles directory inside the Proton prefix."""
        prefix = self.protonPrefix()
        if prefix is not None:
            d = prefix / self._WIN_PROFILES
            if d.is_dir():
                return d
        return None

    def modsettings_path(self) -> Path | None:
        """Return the path to modsettings.lsx of the **active** profile.

        BG3 may use different profile directories (Public,
        Debug_Client_Profile_1, etc.).  The active profile is
        detected by finding the most recently modified
        ``PlayerProfiles/*/modsettings.lsx`` file.

        Returns:
            Absolute path to modsettings.lsx, or None if the
            Proton prefix is not available.
        """
        profiles = self._profiles_dir()
        if profiles is None:
            return None

        candidates = list(profiles.glob("*/modsettings.lsx"))
        if not candidates:
            # No profile yet — fall back to Public
            return profiles / "Public" / "modsettings.lsx"

        # Most recently modified = active profile
        best = max(candidates, key=lambda p: p.stat().st_mtime)
        print(f"bg3: active profile → {best.parent.name}/modsettings.lsx",
              file=sys.stderr)
        return best

    def pak_mods_path(self) -> Path | None:
        """Return the directory where .pak mod files are stored.

        BG3 pak mods go into the ``Mods/`` folder inside the game's
        documents directory in the Proton prefix.

        Returns:
            Absolute path to the Mods directory, or None.
        """
        prefix = self.protonPrefix()
        if prefix is not None:
            return prefix / self._WIN_PAK_MODS
        return None

    def data_mods_path(self) -> Path | None:
        """Return the Data directory in the game root for data mods.

        Some BG3 mods install directly into ``<game>/Data/``.

        Returns:
            Absolute path to the Data directory, or None if game
            path is not set.
        """
        if self._game_path is not None:
            return self._game_path / "Data"
        return None

    # ── Mod-Management (delegiert an bg3_mod_handler) ─────────────────

    def read_mod_list(self) -> dict:
        """Read the current mod list from modsettings.lsx.

        Returns:
            Dict with version, mod_order (UUID list), and mods
            (list of mod metadata dicts).  Empty defaults if the
            file doesn't exist.
        """
        path = self.modsettings_path()
        if path is None:
            return {"version": {}, "mod_order": [], "mods": []}
        return ModsettingsParser.read(path)

    def write_mod_list(
        self, mod_order: list[str], mods: list[dict]
    ) -> None:
        """Write the mod list to modsettings.lsx.

        Creates a backup before overwriting.  Gustav/GustavDev is
        ensured as the first entry.

        Args:
            mod_order: List of UUIDs defining load order.
            mods: List of mod dicts with uuid, name, folder, etc.
        """
        path = self.modsettings_path()
        if path is None:
            return
        ModsettingsWriter.write(path, mod_order, mods)

    def has_script_extender(self) -> bool:
        """Check if BG3 Script Extender is installed."""
        if self._game_path is None:
            return False
        return BG3ScriptExtender.detect(self._game_path)

    def scan_mods(self) -> list[dict]:
        """Scan the Mods directory for .pak files with metadata.

        Returns file info (filename, path, size) plus LSPK metadata
        (uuid, name, folder, author, version, dependencies) extracted
        from info.json or meta.lsx inside each .pak.
        """
        path = self.pak_mods_path()
        if path is None:
            return []
        return scan_pak_mods(path)

    def find_new_mods(self) -> list[dict]:
        """Find .pak files not registered in modsettings.lsx.

        These are mods that were manually copied into the Mods
        folder but not yet added to the load order.
        """
        pak_mods = self.scan_mods()
        mod_list = self.read_mod_list()
        return find_unregistered_mods(pak_mods, mod_list["mods"])

    def get_framework_mods(self) -> list[FrameworkMod]:
        """Return known framework mods for Baldur's Gate 3."""
        return [
            FrameworkMod(
                name="BG3 Script Extender",
                pattern=["DWrite.dll"],
                target="bin/",
                description="Script Extender fuer BG3 (Native Mod Support)",
                detect_installed=["bin/DWrite.dll"],
                required_by=["SE-Mods", "Native Mods"],
            ),
            FrameworkMod(
                name="NativeModLoader",
                pattern=["bink2w64.dll", "bink2w64_original.dll"],
                target="bin/",
                description="DLL-Loader fuer Native Mods (bink2w64 hook)",
                detect_installed=["bin/bink2w64_original.dll"],
                required_by=["WASD", "Native Mods"],
            ),
        ]

    def get_data_override_path_rewrites(self) -> dict[str, str]:
        """Return path prefix rewrites for data-override installation.

        Keys are prefixes found in archives, values are the correct
        target prefix relative to the game root.  For example,
        ``"NativeMods/"`` in an archive should become ``"bin/NativeMods/"``
        in the game directory, not ``"Data/NativeMods/"``.
        """
        return {
            "NativeMods/": "bin/NativeMods/",
        }

    def get_conflict_ignores(self) -> list[str]:
        """Return patterns for harmless files in BG3 mods."""
        return [
            "**/info.json",    # mod metadata, each mod has own
            "**/readme*.txt",  # readme files
        ]

    def executables(self) -> list[dict[str, str]]:
        """Return executable definitions for Baldur's Gate 3.

        Includes the Vulkan renderer (default), DX11 renderer
        (if available), and the Larian Launcher.
        """
        result: list[dict[str, str]] = [
            {"name": "Baldur's Gate 3 (Vulkan)", "binary": self.GameBinary},
        ]

        # Add DX11 variant if available
        if self._game_path is not None:
            dx11 = self._game_path / self._DX11_BINARY
            if dx11.exists() or (self._game_path / "bin" / "bg3_dx11").exists():
                result.append(
                    {"name": "Baldur's Gate 3 (DX11)", "binary": self._DX11_BINARY}
                )

        result.append(
            {"name": "Larian Launcher", "binary": self.GameLauncher}
        )

        return result

    # ── Mod Installer ────────────────────────────────────────────────

    _mod_installer: BG3ModInstaller | None = None

    def get_mod_installer(self) -> BG3ModInstaller:
        """Return a cached BG3ModInstaller instance."""
        if self._mod_installer is None:
            self._mod_installer = BG3ModInstaller(self)
        return self._mod_installer

    def iniFiles(self) -> list[str]:
        """Return config files managed by Baldur's Gate 3."""
        return []
