"""Morrowind game plugin for Anvil Organizer.

Based on the MO2 game_morrowind plugin, adapted for Linux with Proton support.

Morrowind uses an older Gamebryo engine version. Unlike newer Bethesda games,
it does NOT use plugins.txt — load order is defined in Morrowind.ini under
[Game Files] section.

Features:
  - Store detection (Steam, GOG)
  - Proton prefix paths
  - MWSE (Morrowind Script Extender) detection
  - INI-based load order (not plugins.txt!)

TODO:
  - Morrowind.ini [Game Files] Parser/Writer for load order
  - .esp/.esm Scanner
  - OpenMW support (native Linux)
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class MorrowindGame(BaseGame):
    """Morrowind support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Morrowind Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "The Elder Scrolls III: Morrowind"
    GameShortName = "Morrowind"
    GameBinary = "Morrowind.exe"
    GameDataPath = "Data Files"

    GameSteamId = 22320
    GameGogId = 1440163901

    GameLauncher = "Morrowind Launcher.exe"

    GameDocumentsDirectory = ""
    GameSavesDirectory = ""
    GameSaveExtension = "ess"

    GameNexusId = 100
    GameNexusName = "morrowind"

    # -- Primary Plugins ----------------------------------------------------
    # Morrowind hat keine DLCs im modernen Sinne, aber Tribunal und Bloodmoon

    PRIMARY_PLUGINS = [
        "Morrowind.esm",
        "Tribunal.esm",
        "Bloodmoon.esm",
    ]

    DLC_PLUGINS = [
        "Tribunal.esm",
        "Bloodmoon.esm",
    ]

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------
    # Morrowind speichert alles im Spielordner, nicht in Documents!

    _WIN_SAVES = "Saves"  # Relativ zum Spielordner
    _WIN_INI = "Morrowind.ini"  # Im Spielordner

    # -- MWSE (Morrowind Script Extender) -----------------------------------

    _MWSE_BINARY = "MWSE-Update.exe"
    _MWSE_DLL = "MWSE.dll"
    _MWSE_PLUGINS_DIR = "Data Files/MWSE"

    # -- Methoden -----------------------------------------------------------

    def gameDocumentsDirectory(self) -> Path | None:
        # Morrowind hat kein Documents-Verzeichnis, alles im Spielordner
        return self._game_path

    def gameSavesDirectory(self) -> Path | None:
        if self._game_path is not None:
            path = self._game_path / self._WIN_SAVES
            if path.is_dir():
                return path
        return None

    def ini_path(self) -> Path | None:
        """Return path to Morrowind.ini (contains load order)."""
        if self._game_path is not None:
            return self._game_path / self._WIN_INI
        return None

    def data_path(self) -> Path | None:
        if self._game_path is not None:
            return self._game_path / "Data Files"
        return None

    def has_script_extender(self) -> bool:
        if self._game_path is None:
            return False
        return (self._game_path / self._MWSE_DLL).exists()

    def get_framework_mods(self) -> list[FrameworkMod]:
        return [
            FrameworkMod(
                name="MWSE",
                pattern=["MWSE.dll", "MWSE-Update.exe"],
                target="",
                description="Morrowind Script Extender — erweitert die Scripting-Engine",
                detect_installed=["MWSE.dll"],
                required_by=["MWSE-Lua Mods"],
                nexus_id=45468,
            ),
            FrameworkMod(
                name="MGE XE",
                pattern=["MGEXEgui.exe", "d3d8.dll"],
                target="",
                description="Morrowind Graphics Extender XE — Grafik-Verbesserungen",
                detect_installed=["MGEXEgui.exe"],
                required_by=[],
                nexus_id=41102,
            ),
            FrameworkMod(
                name="MCP",
                pattern=["Morrowind Code Patch.exe"],
                target="",
                description="Morrowind Code Patch — Engine-Bugfixes",
                detect_installed=["Morrowind Code Patch.exe"],
                required_by=[],
                nexus_id=19510,
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
            # MWSE (via Morrowind.exe with MWSE.dll)
            if self.has_script_extender():
                vanilla = self._game_path / self.GameBinary
                if vanilla.exists():
                    exes.append({
                        "title": "Morrowind (MWSE)",
                        "binary": str(vanilla),
                        "workingDirectory": str(self._game_path),
                    })
            # Vanilla
            vanilla = self._game_path / self.GameBinary
            if vanilla.exists():
                exes.append({
                    "title": "Morrowind",
                    "binary": str(vanilla),
                    "workingDirectory": str(self._game_path),
                })
            # MGE XE GUI
            mge = self._game_path / "MGEXEgui.exe"
            if mge.exists():
                exes.append({
                    "title": "MGE XE",
                    "binary": str(mge),
                    "workingDirectory": str(self._game_path),
                })
            # Launcher
            launcher = self._game_path / self.GameLauncher
            if launcher.exists():
                exes.append({
                    "title": "Morrowind Launcher",
                    "binary": str(launcher),
                    "workingDirectory": str(self._game_path),
                })
        return exes
