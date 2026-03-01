"""Fallout 4 game plugin for Anvil Organizer.

Based on the MO2 game_fallout4 plugin (C++), adapted for
Linux with Proton prefix support.

Features implemented:
  - Store detection (Steam, GOG)
  - Proton prefix paths for documents and saves
  - Executable list (Fallout 4, F4SE, Launcher, Creation Kit)
  - INI file list
  - Fallout 4-specific path helpers (plugins.txt, Data dirs)
  - F4SE detection

TODO (future):
  - plugins.txt Parser/Writer — Load-Order verwalten
  - .esp/.esm Scanner — Mod-Dateien erkennen
  - .ba2 Archive — Bethesda-Archive
  - F4SE (Fallout 4 Script Extender) Integration
  - Creation Kit Integration (Steam ID 1946160)
  - LOOT-Integration (--game="Fallout4")
  - Creation Club / Fallout4.ccc Parser
  - Save-Game Metadata Parsing (.fos/.f4se)
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class Fallout4Game(BaseGame):
    """Fallout 4 support plugin."""

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Fallout 4 Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute (aus MO2 gamefallout4.cpp) -------------------------

    GameName = "Fallout 4"
    GameShortName = "Fallout4"
    GameBinary = "Fallout4.exe"
    GameDataPath = "Data"  # Mods go into <GameDir>/Data/

    GameSteamId = 377160
    GameGogId = 1998527297  # Fallout 4: Game of the Year Edition

    GameLauncher = "Fallout4Launcher.exe"

    GameDocumentsDirectory = ""  # resolved dynamically via gameDocumentsDirectory()
    GameSavesDirectory = ""     # resolved dynamically via gameSavesDirectory()
    GameSaveExtension = "fos"

    GameNexusId = 1151
    GameNexusName = "fallout4"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Fallout-4"
    )

    # -- Primary & DLC Plugins (aus MO2) ------------------------------------

    PRIMARY_PLUGINS = [
        "Fallout4.esm",
        "DLCRobot.esm",
        "DLCworkshop01.esm",
        "DLCCoast.esm",
        "DLCworkshop02.esm",
        "DLCworkshop03.esm",
        "DLCNukaWorld.esm",
        "DLCUltraHighResolution.esm",
    ]

    # -- BA2-Packing (loose files → BA2 archives via BSArch/Proton) ---------

    NeedsBa2Packing = True
    Ba2Format = "fo4"             # BSArch: -fo4 -mt
    Ba2TextureFormat = "fo4dds"   # BSArch: -fo4dds -mt (DX10 textures)
    Ba2IniSection = "Archive"
    Ba2IniKey = "sResourceArchiveList2"
    Ba2IniFile = "Fallout4Custom.ini"

    DLC_PLUGINS = [
        "DLCRobot.esm",          # Automatron
        "DLCworkshop01.esm",     # Wasteland Workshop
        "DLCCoast.esm",          # Far Harbor
        "DLCworkshop02.esm",     # Contraptions Workshop
        "DLCworkshop03.esm",     # Vault-Tec Workshop
        "DLCNukaWorld.esm",      # Nuka-World
    ]

    # -- Windows-Pfade (innerhalb Proton-Prefix) ----------------------------
    # MO2: determineMyGamesPath("Fallout4") -> Documents/My Games/Fallout4

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/Documents/My Games/Fallout4"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/Documents/My Games/Fallout4/Saves"
    )
    # plugins.txt: AppData/Local/Fallout4/plugins.txt (Bethesda standard)
    _WIN_PLUGINS_TXT = (
        "drive_c/users/steamuser/AppData/Local/Fallout4/plugins.txt"
    )

    # -- F4SE (Fallout 4 Script Extender) -----------------------------------

    _F4SE_BINARY = "f4se_loader.exe"
    _F4SE_PLUGINS_DIR = "Data/f4se/plugins"

    # -- Creation Kit -------------------------------------------------------

    _CK_BINARY = "CreationKit.exe"
    _CK_STEAM_ID = 1946160

    # -- Ueberschriebene Methoden -------------------------------------------

    def gameDocumentsDirectory(self) -> Path | None:
        """Return the game's documents directory (My Games/Fallout4).

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

    # -- Fallout 4-spezifische Pfade ----------------------------------------

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
        """Return the Data directory inside the game installation folder.

        This is where .esm/.esp/.ba2 files live and where most mods
        install their data files.
        """
        if self._game_path is not None:
            return self._game_path / "Data"
        return None

    def has_script_extender(self) -> bool:
        """Check if F4SE (Fallout 4 Script Extender) is installed."""
        if self._game_path is None:
            return False
        return (self._game_path / self._F4SE_BINARY).exists()

    def get_framework_mods(self) -> list[FrameworkMod]:
        """Return known framework mods for Fallout 4."""
        return [
            FrameworkMod(
                name="F4SE",
                pattern=["f4se_loader.exe", "f4se_1_10_163.dll"],
                target="",
                description="Fallout 4 Script Extender — erweitert die Scripting-Engine",
                detect_installed=["f4se_loader.exe"],
                required_by=["F4SE-Plugins", "MCM", "Looksmenu"],
            ),
        ]

    # TODO: plugins.txt Parser/Writer -- Load-Order verwalten
    # TODO: .esp/.esm Scanner -- Mod-Dateien erkennen
    # TODO: .ba2 Archive -- Bethesda-Archive
    # TODO: F4SE Integration (Version check, plugin loading)
    # TODO: Creation Kit Integration (Steam ID 1946160)
    # TODO: LOOT-Integration (--game="Fallout4")
    # TODO: Creation Club / Fallout4.ccc Parser
    # TODO: Save-Game Metadata Parsing (.fos/.f4se)

    def get_default_categories(self) -> list[dict] | None:
        """Return Fallout 4 specific default categories."""
        return [
            {"id": 1, "name": "Gameplay"},
            {"id": 2, "name": "Weapons"},
            {"id": 3, "name": "Armor & Clothing"},
            {"id": 4, "name": "Settlements"},
            {"id": 5, "name": "Power Armor"},
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
        """Return patterns for harmless files in Fallout 4 mods."""
        return [
            "**/readme*.txt",  # readme files
            "**/docs/**",      # documentation folders
        ]

    def executables(self) -> list[dict[str, str]]:
        """Return executable definitions for Fallout 4.

        Includes: Fallout 4, F4SE (if installed), Launcher, Creation Kit.
        Matches MO2's executable list.
        """
        result: list[dict[str, str]] = [
            {"name": "Fallout 4", "binary": self.GameBinary},
            {"name": "Fallout 4 Launcher", "binary": self.GameLauncher},
        ]

        # Add F4SE if available
        if self._game_path is not None:
            f4se = self._game_path / self._F4SE_BINARY
            if f4se.exists():
                result.insert(0, {"name": "F4SE", "binary": self._F4SE_BINARY})

            # Add Creation Kit if available
            ck = self._game_path / self._CK_BINARY
            if ck.exists():
                result.append({"name": "Creation Kit", "binary": self._CK_BINARY})

        return result

    def iniFiles(self) -> list[str]:
        """Return config files managed by Fallout 4.

        From MO2: Fallout4.ini, Fallout4Prefs.ini, Fallout4Custom.ini.
        Located in the My Games/Fallout4 directory.
        """
        return ["Fallout4.ini", "Fallout4Prefs.ini", "Fallout4Custom.ini"]
