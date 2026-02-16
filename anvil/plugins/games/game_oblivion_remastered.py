"""Oblivion Remastered game plugin for Anvil Organizer.

IMPORTANT: Oblivion Remastered uses UNREAL ENGINE 5, NOT the original
Gamebryo engine! This means:
  - NO .esp/.esm plugins
  - NO plugins.txt load order
  - Uses .pak files like other UE5 games
  - Mod structure is completely different from original Oblivion

Features:
  - Store detection (Steam)
  - Proton prefix paths
  - UE5 .pak mod support

TODO:
  - .pak file handling
  - UE5 mod loading order
  - Blueprint mod support
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class OblivionRemasteredGame(BaseGame):
    """Oblivion Remastered (UE5) support plugin."""

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Oblivion Remastered Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "The Elder Scrolls IV: Oblivion Remastered"
    GameShortName = "OblivionRemastered"
    GameBinary = "OblivionRemastered.exe"
    GameDataPath = "OblivionRemastered/Content/Paks"

    GameSteamId = 2623190
    GameGogId = 0  # Nicht auf GOG verfügbar (Stand 2025)

    GameLauncher = ""

    GameDocumentsDirectory = ""
    GameSavesDirectory = ""
    GameSaveExtension = "sav"

    GameNexusId = 7583  # oblivionremastered auf Nexus
    GameNexusName = "oblivionremastered"

    # -- UE5-spezifische Pfade ----------------------------------------------

    # UE5 Spiele nutzen ~mods oder Paks/mods Ordner
    _PAKS_DIR = "OblivionRemastered/Content/Paks"
    _MODS_DIR = "OblivionRemastered/Content/Paks/~mods"

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_SAVES = "drive_c/users/steamuser/AppData/Local/OblivionRemastered/Saved/SaveGames"

    # -- Methoden -----------------------------------------------------------

    def gameDocumentsDirectory(self) -> Path | None:
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / "drive_c/users/steamuser/AppData/Local/OblivionRemastered"
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

    def paks_path(self) -> Path | None:
        """Return the Paks directory for .pak mods."""
        if self._game_path is not None:
            return self._game_path / self._PAKS_DIR
        return None

    def mods_path(self) -> Path | None:
        """Return the ~mods directory for loose .pak mods."""
        if self._game_path is not None:
            path = self._game_path / self._MODS_DIR
            return path
        return None

    def get_framework_mods(self) -> list[FrameworkMod]:
        # UE5 hat keine klassischen Script Extender
        return []

    def get_conflict_ignores(self) -> list[str]:
        return [
            "**/readme*.txt",
            "**/docs/**",
        ]

    def executables(self) -> list[dict[str, str]]:
        exes = []
        if self._game_path:
            # Main executable
            main = self._game_path / self.GameBinary
            if main.exists():
                exes.append({
                    "title": "Oblivion Remastered",
                    "binary": str(main),
                    "workingDirectory": str(self._game_path),
                })
        return exes
