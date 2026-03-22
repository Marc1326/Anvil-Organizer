"""Starfield game plugin for Anvil Organizer.

Based on the MO2 game_starfield plugin (C++), adapted for
Linux with Proton prefix support.

Features implemented:
  - Store detection (Steam only — no GOG/Epic release)
  - Proton prefix paths for documents and saves
  - Executable list (Starfield, SFSE, Creation Kit)
  - INI file list
  - Starfield-specific path helpers (plugins.txt, Data dirs)
  - SFSE detection

TODO (future):
  - plugins.txt Parser/Writer — Load-Order verwalten
  - .esp/.esm Scanner — Mod-Dateien erkennen
  - .ba2 Archive — Bethesda-Archive
  - SFSE (Starfield Script Extender) Integration
  - Creation Kit Integration (Steam ID 2722710)
  - LOOT-Integration (--game="Starfield")
  - Creation Club / ContentCatalog.txt Parser
  - sTestFile-Diagnostik (StarfieldCustom.ini)
  - Save-Game Metadata Parsing (.sfs/.sfse)
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class StarfieldGame(BaseGame):
    """Starfield support plugin."""

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Starfield Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute (aus MO2 gamestarfield.cpp) ------------------------

    GameName = "Starfield"
    GameShortName = "Starfield"
    GameBinary = "Starfield.exe"
    GameDataPath = "Data"  # Mods go into <GameDir>/Data/

    GameSteamId = 1716740
    # Starfield has no GOG or Epic release as of 2025
    GameGogId = 0
    GameEpicId = ""

    GameLauncher = ""  # No separate launcher

    GameDocumentsDirectory = ""  # resolved dynamically via gameDocumentsDirectory()
    GameSavesDirectory = ""     # resolved dynamically via gameSavesDirectory()
    GameSaveExtension = "sfs"

    GameNexusId = 4187
    GameNexusName = "starfield"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Starfield"
    )

    ProtonShimFiles = ["version.dll"]

    # -- Primary & DLC Plugins (aus MO2) ------------------------------------

    PRIMARY_PLUGINS = [
        "Starfield.esm",
        "Constellation.esm",
        "ShatteredSpace.esm",
        "OldMars.esm",
        "SFBGS003.esm",
        "SFBGS004.esm",
        "SFBGS006.esm",
        "SFBGS007.esm",
        "SFBGS008.esm",
        "BlueprintShips-Starfield.esm",
    ]

    DLC_PLUGINS = [
        "Constellation.esm",
        "ShatteredSpace.esm",
    ]

    # -- Windows-Pfade (innerhalb Proton-Prefix) ----------------------------
    # MO2: determineMyGamesPath("Starfield") -> Documents/My Games/Starfield

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/Documents/My Games/Starfield"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/Documents/My Games/Starfield/Saves"
    )
    # plugins.txt: AppData/Local/Starfield/plugins.txt (Bethesda standard)
    _WIN_PLUGINS_TXT = (
        "drive_c/users/steamuser/AppData/Local/Starfield/plugins.txt"
    )

    # -- SFSE (Starfield Script Extender) -----------------------------------

    _SFSE_BINARY = "sfse_loader.exe"
    _SFSE_PLUGINS_DIR = "Data/sfse/plugins"

    # -- Creation Kit -------------------------------------------------------

    _CK_BINARY = "CreationKit.exe"
    _CK_STEAM_ID = 2722710

    # -- Ueberschriebene Methoden -------------------------------------------

    def gameDocumentsDirectory(self) -> Path | None:
        """Return the game's documents directory (My Games/Starfield).

        For Steam (Proton): derived from the Proton prefix.
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

    # -- Starfield-spezifische Pfade ----------------------------------------

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
        """Return the Data directory inside Documents (for loose file mods).

        MO2: documentsDirectory().absoluteFilePath("Data")
        This is where Starfield looks for loose mod files.
        """
        docs = self.gameDocumentsDirectory()
        if docs is not None:
            return docs / "Data"
        return None

    def game_data_path(self) -> Path | None:
        """Return the Data directory in the game installation folder.

        This is where .esm/.ba2 base game files live.
        Some mods also install here.
        """
        if self._game_path is not None:
            return self._game_path / "Data"
        return None

    def has_script_extender(self) -> bool:
        """Check if SFSE (Starfield Script Extender) is installed."""
        if self._game_path is None:
            return False
        return (self._game_path / self._SFSE_BINARY).exists()

    def get_framework_mods(self) -> list[FrameworkMod]:
        """Return known framework mods for Starfield."""
        return [
            FrameworkMod(
                name="SFSE",
                pattern=["sfse_loader.exe", "sfse_1_0_0.dll"],
                target="",
                description="Starfield Script Extender — erweitert die Scripting-Engine",
                detect_installed=["sfse_loader.exe"],
                required_by=["SFSE-Plugins"],
            ),
        ]

    def get_proton_env_overrides(self) -> dict[str, str]:
        """Return WINEDLLOVERRIDES for SFSE Proton shim."""
        if self._game_path is None:
            return {}
        if (self._game_path / "version.dll").exists():
            return {"WINEDLLOVERRIDES": "version=n,b"}
        return {}

    # TODO: plugins.txt Parser/Writer -- Load-Order verwalten
    # TODO: .esp/.esm Scanner -- Mod-Dateien erkennen
    # TODO: .ba2 Archive -- Bethesda-Archive
    # TODO: SFSE Integration (Version check, plugin loading)
    # TODO: Creation Kit Integration
    # TODO: LOOT-Integration (--game="Starfield")
    # TODO: Creation Club / ContentCatalog.txt Parser
    # TODO: sTestFile-Diagnostik (StarfieldCustom.ini)
    # TODO: Save-Game Metadata Parsing (.sfs/.sfse)

    def get_default_categories(self) -> list[dict] | None:
        """Return Starfield specific default categories."""
        return [
            {"id": 1, "name": "Gameplay"},
            {"id": 2, "name": "Weapons"},
            {"id": 3, "name": "Armor & Clothing"},
            {"id": 4, "name": "Ships"},
            {"id": 5, "name": "Outposts"},
            {"id": 6, "name": "Graphics & Visuals"},
            {"id": 7, "name": "UI"},
            {"id": 8, "name": "Audio"},
            {"id": 9, "name": "NPCs & Companions"},
            {"id": 10, "name": "Environment"},
            {"id": 11, "name": "Hair & Face"},
            {"id": 12, "name": "Body"},
            {"id": 13, "name": "Quests"},
            {"id": 14, "name": "Crafting"},
            {"id": 15, "name": "Creatures"},
            {"id": 16, "name": "Bug Fixes"},
            {"id": 17, "name": "Utilities"},
            {"id": 18, "name": "Frameworks"},
            {"id": 19, "name": "Patches"},
        ]

    def get_conflict_ignores(self) -> list[str]:
        """Return patterns for harmless files in Starfield mods."""
        return [
            "**/readme*.txt",  # readme files
            "**/docs/**",      # documentation folders
        ]

    def executables(self) -> list[dict[str, str]]:
        """Return executable definitions for Starfield.

        Includes: Starfield, SFSE (if installed), Creation Kit (if installed).
        Matches MO2's executable list.
        """
        result: list[dict[str, str]] = [
            {"name": "Starfield", "binary": self.GameBinary},
        ]

        # Add SFSE if available
        if self._game_path is not None:
            sfse = self._game_path / self._SFSE_BINARY
            if sfse.exists():
                result.insert(0, {"name": "SFSE", "binary": self._SFSE_BINARY})

            # Add Creation Kit if available
            ck = self._game_path / self._CK_BINARY
            if ck.exists():
                result.append({"name": "Creation Kit", "binary": self._CK_BINARY})

        return result

    def iniFiles(self) -> list[str]:
        """Return config files managed by Starfield.

        From MO2: StarfieldPrefs.ini and StarfieldCustom.ini.
        Located in the My Games/Starfield directory.
        """
        return ["StarfieldPrefs.ini", "StarfieldCustom.ini"]
