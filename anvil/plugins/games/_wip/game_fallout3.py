"""Fallout 3 game plugin for Anvil Organizer.

Based on the MO2 game_fallout3 plugin, adapted for Linux with Proton support.

Features:
  - Store detection (Steam, GOG)
  - Proton prefix paths
  - FOSE (Fallout Script Extender) detection
  - INI file paths

TODO:
  - plugins.txt Parser/Writer
  - .esp/.esm Scanner
  - LOOT Integration (--game="Fallout3")
  - Save-Game Metadata Parsing
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class Fallout3Game(BaseGame):
    """Fallout 3 support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Fallout 3 Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Fallout 3"
    GameShortName = "Fallout3"
    GameBinary = "Fallout3.exe"
    GameDataPath = "Data"

    GameSteamId = 22300  # Base game (22370 = GOTY)
    GameGogId = 1454315831

    GameLauncher = "FalloutLauncher.exe"

    GameDocumentsDirectory = ""
    GameSavesDirectory = ""
    GameSaveExtension = "fos"

    GameNexusId = 120
    GameNexusName = "fallout3"

    # -- Primary & DLC Plugins ----------------------------------------------

    PRIMARY_PLUGINS = [
        "Fallout3.esm",
        "Anchorage.esm",
        "ThePitt.esm",
        "BrokenSteel.esm",
        "PointLookout.esm",
        "Zeta.esm",
    ]

    DLC_PLUGINS = [
        "Anchorage.esm",      # Operation: Anchorage
        "ThePitt.esm",        # The Pitt
        "BrokenSteel.esm",    # Broken Steel
        "PointLookout.esm",   # Point Lookout
        "Zeta.esm",           # Mothership Zeta
    ]

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_DOCUMENTS = "drive_c/users/steamuser/Documents/My Games/Fallout3"
    _WIN_SAVES = "drive_c/users/steamuser/Documents/My Games/Fallout3/Saves"
    _WIN_PLUGINS_TXT = "drive_c/users/steamuser/AppData/Local/Fallout3/plugins.txt"

    # -- FOSE (Fallout Script Extender) -------------------------------------

    _FOSE_BINARY = "fose_loader.exe"
    _FOSE_PLUGINS_DIR = "Data/fose/plugins"

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
        return (self._game_path / self._FOSE_BINARY).exists()

    def get_framework_mods(self) -> list[FrameworkMod]:
        return [
            FrameworkMod(
                name="FOSE",
                pattern=["fose_loader.exe", "fose_*.dll"],
                target="",
                description="Fallout Script Extender — erweitert die Scripting-Engine",
                detect_installed=["fose_loader.exe"],
                required_by=["FOSE-Plugins"],
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
            # FOSE
            fose = self._game_path / self._FOSE_BINARY
            if fose.exists():
                exes.append({
                    "title": "Fallout 3 (FOSE)",
                    "binary": str(fose),
                    "workingDirectory": str(self._game_path),
                })
            # Vanilla
            vanilla = self._game_path / self.GameBinary
            if vanilla.exists():
                exes.append({
                    "title": "Fallout 3",
                    "binary": str(vanilla),
                    "workingDirectory": str(self._game_path),
                })
            # Launcher
            launcher = self._game_path / self.GameLauncher
            if launcher.exists():
                exes.append({
                    "title": "Fallout 3 Launcher",
                    "binary": str(launcher),
                    "workingDirectory": str(self._game_path),
                })
        return exes
