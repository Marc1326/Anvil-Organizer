"""Stardew Valley game plugin for Anvil Organizer.

Stardew Valley uses a custom engine with SMAPI (Stardew Modding API)
as the mod loader. Mods are placed directly in the Mods/ folder in
the game directory.

Features:
  - Store detection (Steam, GOG)
  - Native Linux support (no Proton needed!)
  - SMAPI detection
  - Mods/ folder structure

TODO:
  - manifest.json Parser for mod metadata
  - Dependency resolution
  - Content Patcher support
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class StardewValleyGame(BaseGame):
    """Stardew Valley support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Stardew Valley Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Stardew Valley"
    GameShortName = "StardewValley"
    GameBinary = "Stardew Valley"  # Linux native, kein .exe!
    GameDataPath = "Mods"

    GameSteamId = 413150
    GameGogId = 1453375253

    GameLauncher = ""

    GameDocumentsDirectory = ""
    GameSavesDirectory = ""
    GameSaveExtension = ""  # Saves are folders

    GameNexusId = 1303
    GameNexusName = "stardewvalley"

    # -- Stardew-spezifische Pfade ------------------------------------------

    _SMAPI_BINARY_LINUX = "StardewModdingAPI"
    _SMAPI_BINARY_WIN = "StardewModdingAPI.exe"
    _MODS_DIR = "Mods"

    # -- Linux native Pfade -------------------------------------------------
    # Stardew Valley läuft nativ unter Linux!

    _LINUX_SAVES = "~/.config/StardewValley/Saves"
    _LINUX_CONTENT = "Content"

    # -- Methoden -----------------------------------------------------------

    def gameDocumentsDirectory(self) -> Path | None:
        # Linux native: ~/.config/StardewValley/
        config_path = Path.home() / ".config" / "StardewValley"
        if config_path.is_dir():
            return config_path
        return None

    def gameSavesDirectory(self) -> Path | None:
        # Linux native: ~/.config/StardewValley/Saves/
        saves_path = Path.home() / ".config" / "StardewValley" / "Saves"
        if saves_path.is_dir():
            return saves_path
        return None

    def mods_path(self) -> Path | None:
        """Return the Mods directory."""
        if self._game_path is not None:
            return self._game_path / self._MODS_DIR
        return None

    def has_smapi(self) -> bool:
        """Check if SMAPI is installed."""
        if self._game_path is None:
            return False
        # Check for Linux version first
        if (self._game_path / self._SMAPI_BINARY_LINUX).exists():
            return True
        # Check for Windows version (Proton)
        if (self._game_path / self._SMAPI_BINARY_WIN).exists():
            return True
        return False

    def get_framework_mods(self) -> list[FrameworkMod]:
        return [
            FrameworkMod(
                name="SMAPI",
                pattern=["StardewModdingAPI", "StardewModdingAPI.exe"],
                target="",
                description="Stardew Modding API — Mod-Loader für Stardew Valley",
                detect_installed=["StardewModdingAPI"],
                required_by=["Alle SMAPI-Mods"],
            ),
            FrameworkMod(
                name="Content Patcher",
                pattern=["ContentPatcher.dll"],
                target="Mods/ContentPatcher",
                description="Content Patcher — Ermöglicht Textur/Asset-Ersetzung",
                detect_installed=["Mods/ContentPatcher/ContentPatcher.dll"],
                required_by=["Die meisten Textur-Mods"],
            ),
            FrameworkMod(
                name="Generic Mod Config Menu",
                pattern=["GenericModConfigMenu.dll"],
                target="Mods/GenericModConfigMenu",
                description="Generic Mod Config Menu — In-Game Mod-Einstellungen",
                detect_installed=["Mods/GenericModConfigMenu/GenericModConfigMenu.dll"],
                required_by=[],
            ),
            FrameworkMod(
                name="SpaceCore",
                pattern=["SpaceCore.dll"],
                target="Mods/SpaceCore",
                description="SpaceCore — Erweiterte Modding-Features",
                detect_installed=["Mods/SpaceCore/SpaceCore.dll"],
                required_by=["JsonAssets", "SpaceChase Mods"],
            ),
        ]

    def get_conflict_ignores(self) -> list[str]:
        return [
            "**/readme*.txt",
            "**/docs/**",
            "**/manifest.json",  # Each mod has its own
        ]

    def executables(self) -> list[dict[str, str]]:
        exes = []
        if self._game_path:
            # SMAPI (preferred)
            smapi_linux = self._game_path / self._SMAPI_BINARY_LINUX
            smapi_win = self._game_path / self._SMAPI_BINARY_WIN
            if smapi_linux.exists():
                exes.append({
                    "title": "Stardew Valley (SMAPI)",
                    "binary": str(smapi_linux),
                    "workingDirectory": str(self._game_path),
                })
            elif smapi_win.exists():
                exes.append({
                    "title": "Stardew Valley (SMAPI)",
                    "binary": str(smapi_win),
                    "workingDirectory": str(self._game_path),
                })
            # Vanilla
            vanilla = self._game_path / self.GameBinary
            if vanilla.exists():
                exes.append({
                    "title": "Stardew Valley",
                    "binary": str(vanilla),
                    "workingDirectory": str(self._game_path),
                })
        return exes
