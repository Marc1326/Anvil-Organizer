"""Mount & Blade II: Bannerlord game plugin for Anvil Organizer.

Bannerlord uses TaleWorlds' custom engine. Mods are placed in the
Modules/ folder and each mod has a SubModule.xml defining metadata
and dependencies.

Features:
  - Store detection (Steam, GOG)
  - Proton prefix paths
  - Modules/ folder structure
  - SubModule.xml parsing (TODO)

TODO:
  - SubModule.xml Parser for mod metadata
  - Dependency resolution
  - Native/Managed mod detection
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class BannerlordGame(BaseGame):
    """Mount & Blade II: Bannerlord support plugin."""

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Bannerlord Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Mount & Blade II: Bannerlord"
    GameShortName = "Bannerlord"
    GameBinary = "Bannerlord.exe"
    GameDataPath = "Modules"

    GameSteamId = 261550
    GameGogId = 1802539526

    GameLauncher = "TaleWorlds.MountAndBlade.Launcher.exe"

    GameDocumentsDirectory = ""
    GameSavesDirectory = ""
    GameSaveExtension = "sav"

    GameNexusId = 3174
    GameNexusName = "mountandblade2bannerlord"

    # -- Bannerlord-spezifische Pfade ---------------------------------------

    _MODULES_DIR = "Modules"
    _BIN_DIR = "bin/Win64_Shipping_Client"

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_DOCUMENTS = "drive_c/users/steamuser/Documents/Mount and Blade II Bannerlord"
    _WIN_SAVES = "drive_c/users/steamuser/Documents/Mount and Blade II Bannerlord/Game Saves"
    _WIN_CONFIGS = "drive_c/users/steamuser/Documents/Mount and Blade II Bannerlord/Configs"

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

    def modules_path(self) -> Path | None:
        """Return the Modules directory for mods."""
        if self._game_path is not None:
            return self._game_path / self._MODULES_DIR
        return None

    def get_framework_mods(self) -> list[FrameworkMod]:
        return [
            FrameworkMod(
                name="Harmony",
                pattern=["0Harmony.dll"],
                target="Modules/Harmony",
                description="Harmony — Runtime-Patching Framework",
                detect_installed=["Modules/Harmony/SubModule.xml"],
                required_by=["Die meisten Bannerlord Mods"],
            ),
            FrameworkMod(
                name="ButterLib",
                pattern=["ButterLib.dll"],
                target="Modules/ButterLib",
                description="ButterLib — Gemeinsame Utility-Bibliothek",
                detect_installed=["Modules/ButterLib/SubModule.xml"],
                required_by=["MCM", "Viele größere Mods"],
            ),
            FrameworkMod(
                name="UIExtenderEx",
                pattern=["UIExtenderEx.dll"],
                target="Modules/UIExtenderEx",
                description="UIExtenderEx — UI-Erweiterungen",
                detect_installed=["Modules/UIExtenderEx/SubModule.xml"],
                required_by=["UI-Mods"],
            ),
            FrameworkMod(
                name="MCM",
                pattern=["MCMv5.dll"],
                target="Modules/MCMv5",
                description="Mod Configuration Menu — In-Game Mod-Einstellungen",
                detect_installed=["Modules/MCMv5/SubModule.xml"],
                required_by=[],
            ),
        ]

    def get_conflict_ignores(self) -> list[str]:
        return [
            "**/readme*.txt",
            "**/docs/**",
            "**/SubModule.xml",  # Each mod has its own
        ]

    def executables(self) -> list[dict[str, str]]:
        exes = []
        if self._game_path:
            bin_dir = self._game_path / self._BIN_DIR
            # Main game
            main = bin_dir / self.GameBinary
            if main.exists():
                exes.append({
                    "title": "Bannerlord",
                    "binary": str(main),
                    "workingDirectory": str(bin_dir),
                })
            # Launcher
            launcher = bin_dir / self.GameLauncher
            if launcher.exists():
                exes.append({
                    "title": "Bannerlord Launcher",
                    "binary": str(launcher),
                    "workingDirectory": str(bin_dir),
                })
        return exes
