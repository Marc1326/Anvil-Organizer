"""Fallout: New Vegas game plugin for Anvil Organizer.

Based on the MO2 game_falloutnv plugin, adapted for Linux with Proton support.

Features:
  - Store detection (Steam, GOG)
  - Proton prefix paths
  - NVSE (New Vegas Script Extender) detection
  - INI file paths

TODO:
  - plugins.txt Parser/Writer
  - .esp/.esm Scanner
  - LOOT Integration (--game="FalloutNV")
  - Save-Game Metadata Parsing
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class FalloutNVGame(BaseGame):
    """Fallout: New Vegas support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Fallout: New Vegas Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Fallout: New Vegas"
    GameShortName = "FalloutNV"
    GameBinary = "FalloutNV.exe"
    GameDataPath = "Data"

    GameSteamId = 22380
    GameGogId = 1454587428

    GameLauncher = "FalloutNVLauncher.exe"

    GameDocumentsDirectory = ""
    GameSavesDirectory = ""
    GameSaveExtension = "fos"

    GameNexusId = 130
    GameNexusName = "newvegas"

    # -- Primary & DLC Plugins ----------------------------------------------

    PRIMARY_PLUGINS = [
        "FalloutNV.esm",
        "DeadMoney.esm",
        "HonestHearts.esm",
        "OldWorldBlues.esm",
        "LonesomeRoad.esm",
        "GunRunnersArsenal.esm",
        "CaravanPack.esm",
        "ClassicPack.esm",
        "MercenaryPack.esm",
        "TribalPack.esm",
    ]

    DLC_PLUGINS = [
        "DeadMoney.esm",
        "HonestHearts.esm",
        "OldWorldBlues.esm",
        "LonesomeRoad.esm",
        "GunRunnersArsenal.esm",
    ]

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_DOCUMENTS = "drive_c/users/steamuser/Documents/My Games/FalloutNV"
    _WIN_SAVES = "drive_c/users/steamuser/Documents/My Games/FalloutNV/Saves"
    _WIN_PLUGINS_TXT = "drive_c/users/steamuser/AppData/Local/FalloutNV/plugins.txt"

    # -- NVSE (New Vegas Script Extender) -----------------------------------

    _NVSE_BINARY = "nvse_loader.exe"
    _NVSE_PLUGINS_DIR = "Data/nvse/plugins"

    # -- Methoden -----------------------------------------------------------

    def gameDocumentsDirectory(self) -> Path | None:
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_DOCUMENTS
            if path.is_dir():
                return path
        return None

    def gameSavesDirectory(self) -> Path | None:
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_SAVES
            if path.is_dir():
                return path
        return None

    def plugins_txt_path(self) -> Path | None:
        prefix = self.protonPrefix()
        if prefix is not None:
            return prefix / self._WIN_PLUGINS_TXT
        return None

    def data_path(self) -> Path | None:
        if self._game_path is not None:
            return self._game_path / "Data"
        return None

    def has_script_extender(self) -> bool:
        if self._game_path is None:
            return False
        return (self._game_path / self._NVSE_BINARY).exists()

    def get_framework_mods(self) -> list[FrameworkMod]:
        return [
            FrameworkMod(
                name="NVSE",
                pattern=["nvse_loader.exe", "nvse_*.dll"],
                target="",
                description="New Vegas Script Extender — erweitert die Scripting-Engine",
                detect_installed=["nvse_loader.exe"],
                required_by=["JIP LN NVSE", "JohnnyGuitar NVSE", "MCM"],
            ),
            FrameworkMod(
                name="4GB Patcher",
                pattern=["FalloutNV.exe.backup", "fnv4gb.exe"],
                target="",
                description="4GB RAM Patch für bessere Stabilität",
                detect_installed=["FalloutNV.exe.backup"],
                required_by=[],
            ),
        ]

    def get_conflict_ignores(self) -> list[str]:
        return [
            "**/readme*.txt",
            "**/docs/**",
        ]

    def executables(self) -> list[dict[str, str]]:
        exes = []
        if self._game_path:
            # NVSE
            nvse = self._game_path / self._NVSE_BINARY
            if nvse.exists():
                exes.append({
                    "title": "New Vegas (NVSE)",
                    "binary": str(nvse),
                    "workingDirectory": str(self._game_path),
                })
            # Vanilla
            vanilla = self._game_path / self.GameBinary
            if vanilla.exists():
                exes.append({
                    "title": "New Vegas",
                    "binary": str(vanilla),
                    "workingDirectory": str(self._game_path),
                })
            # Launcher
            launcher = self._game_path / self.GameLauncher
            if launcher.exists():
                exes.append({
                    "title": "New Vegas Launcher",
                    "binary": str(launcher),
                    "workingDirectory": str(self._game_path),
                })
        return exes
