"""Skyrim Special Edition game plugin for Anvil Organizer.

Based on the MO2 game_skyrimSE plugin (C++), adapted for
Linux with Proton prefix support.

Features implemented:
  - Store detection (Steam, GOG — SE + Anniversary Upgrade)
  - Proton prefix paths for documents and saves
  - Executable list (Skyrim SE, SKSE64, Launcher, Creation Kit)
  - INI file list
  - Bethesda-style path helpers (plugins.txt, Data dir)
  - SKSE64 detection
  - Framework mods (SKSE64)

TODO (future):
  - plugins.txt Parser/Writer — Load-Order verwalten
  - .esp/.esm Scanner — Mod-Dateien erkennen
  - .bsa Archive — Bethesda-Archive
  - SKSE64 Integration (Version check, plugin loading)
  - Creation Kit Integration (Steam ID 1946180)
  - LOOT-Integration (--game="Skyrim Special Edition")
  - Creation Club / Skyrim.ccc Parser
  - Save-Game Metadata Parsing (.ess/.skse)
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class SkyrimSEGame(BaseGame):
    """Skyrim Special Edition support plugin."""

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Skyrim Special Edition Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute (aus MO2 gameskyrimse.cpp) -------------------------

    GameName = "Skyrim Special Edition"
    GameShortName = "SkyrimSE"
    GameBinary = "SkyrimSE.exe"
    GameDataPath = ""  # Mods go into <GameDir>/Data/

    GameSteamId = 489830
    # GOG: SE (1711230643) + Anniversary Upgrade (1162721350)
    GameGogId = [1711230643, 1162721350]

    GameLauncher = "SkyrimSELauncher.exe"

    GameDocumentsDirectory = ""  # resolved dynamically via gameDocumentsDirectory()
    GameSavesDirectory = ""     # resolved dynamically via gameSavesDirectory()
    GameSaveExtension = "ess"

    GameNexusId = 1704
    GameNexusName = "skyrimspecialedition"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Skyrim-Special-Edition"
    )

    # -- Primary & DLC Plugins (aus MO2) ------------------------------------

    PRIMARY_PLUGINS = [
        "Skyrim.esm",
        "Update.esm",
        "Dawnguard.esm",
        "HearthFires.esm",
        "Dragonborn.esm",
    ]

    DLC_PLUGINS = [
        "Dawnguard.esm",
        "HearthFires.esm",
        "Dragonborn.esm",
    ]

    # -- Windows-Pfade (innerhalb Proton-Prefix) ----------------------------
    # MO2: determineMyGamesPath("Skyrim Special Edition")
    #       -> Documents/My Games/Skyrim Special Edition

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/Documents/My Games/Skyrim Special Edition"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/Documents/My Games/Skyrim Special Edition/Saves"
    )
    # plugins.txt: AppData/Local/Skyrim Special Edition/plugins.txt
    _WIN_PLUGINS_TXT = (
        "drive_c/users/steamuser/AppData/Local"
        "/Skyrim Special Edition/plugins.txt"
    )

    # -- SKSE64 (Skyrim Script Extender 64) ---------------------------------

    _SKSE_BINARY = "skse64_loader.exe"
    _SKSE_PLUGINS_DIR = "Data/skse/plugins"

    # -- Creation Kit -------------------------------------------------------

    _CK_BINARY = "CreationKit.exe"
    _CK_STEAM_ID = 1946180

    # -- Ueberschriebene Methoden -------------------------------------------

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
        """Return the save game directory.

        For Steam (Proton): derived from the Proton prefix.
        Returns None if no prefix is found.
        """
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_SAVES
            if path.is_dir():
                return path
        return None

    # -- Skyrim SE-spezifische Pfade ----------------------------------------

    def plugins_txt_path(self) -> Path | None:
        """Return the path to plugins.txt (load order).

        Bethesda games store plugins.txt in AppData/Local/<GameName>/.
        Returns the full path inside the Proton prefix, or None.
        """
        prefix = self.protonPrefix()
        if prefix is not None:
            return prefix / self._WIN_PLUGINS_TXT
        return None

    def data_path(self) -> Path | None:
        """Return the Data directory in the game installation folder.

        This is where .esm/.esp/.bsa files live and where most mods
        install their data files.
        """
        if self._game_path is not None:
            return self._game_path / "Data"
        return None

    def has_script_extender(self) -> bool:
        """Check if SKSE64 (Skyrim Script Extender 64) is installed."""
        if self._game_path is None:
            return False
        return (self._game_path / self._SKSE_BINARY).exists()

    # -- Framework-Mods -----------------------------------------------------

    def get_framework_mods(self) -> list[FrameworkMod]:
        """Return known framework mods for Skyrim Special Edition."""
        return [
            FrameworkMod(
                name="SKSE64",
                pattern=["skse64_loader.exe", "skse64_1_6_"],
                target="",
                description="Skyrim Script Extender 64 — erweitert die Scripting-Engine",
                detect_installed=["skse64_loader.exe"],
                required_by=["SKSE-Plugins", "SkyUI", "MCM", "RaceMenu"],
            ),
        ]

    # TODO: plugins.txt Parser/Writer -- Load-Order verwalten
    # TODO: .esp/.esm Scanner -- Mod-Dateien erkennen
    # TODO: .bsa Archive -- Bethesda-Archive
    # TODO: SKSE64 Integration (Version check, plugin loading)
    # TODO: Creation Kit Integration (Steam ID 1946180)
    # TODO: LOOT-Integration (--game="Skyrim Special Edition")
    # TODO: Creation Club / Skyrim.ccc Parser
    # TODO: Save-Game Metadata Parsing (.ess/.skse)

    def get_conflict_ignores(self) -> list[str]:
        """Return patterns for harmless files in Skyrim SE mods."""
        return [
            "**/readme*.txt",  # readme files
            "**/docs/**",      # documentation folders
        ]

    def executables(self) -> list[dict[str, str]]:
        """Return executable definitions for Skyrim Special Edition.

        Includes: Skyrim SE, SKSE64 (if installed), Launcher, Creation Kit.
        Matches MO2's executable list.
        """
        result: list[dict[str, str]] = [
            {"name": "Skyrim Special Edition", "binary": self.GameBinary},
            {"name": "Skyrim SE Launcher", "binary": self.GameLauncher},
        ]

        # Add SKSE64 if available
        if self._game_path is not None:
            skse = self._game_path / self._SKSE_BINARY
            if skse.exists():
                result.insert(0, {"name": "SKSE64", "binary": self._SKSE_BINARY})

            # Add Creation Kit if available
            ck = self._game_path / self._CK_BINARY
            if ck.exists():
                result.append({"name": "Creation Kit", "binary": self._CK_BINARY})

        return result

    def iniFiles(self) -> list[str]:
        """Return config files managed by Skyrim Special Edition.

        From MO2: Skyrim.ini, SkyrimPrefs.ini, SkyrimCustom.ini.
        Located in the My Games/Skyrim Special Edition directory.
        """
        return ["Skyrim.ini", "SkyrimPrefs.ini", "SkyrimCustom.ini"]
