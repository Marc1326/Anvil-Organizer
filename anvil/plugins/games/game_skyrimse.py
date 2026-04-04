"""Skyrim Special Edition game plugin for Anvil Organizer.

Adapted for Linux with Proton prefix support.

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

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class SkyrimSEGame(BaseGame):
    """Skyrim Special Edition support plugin."""

    Tested = True

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Skyrim Special Edition Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Skyrim Special Edition"
    GameShortName = "SkyrimSE"
    GameBinary = "SkyrimSE.exe"
    GameDataPath = "Data"  # Mods go into <GameDir>/Data/

    GameSteamId = 489830
    # GOG: SE (1711230643) + Anniversary Upgrade (1162721350)
    GameGogId = [1711230643, 1162721350]

    GameLauncher = "SkyrimSELauncher.exe"

    GameDocumentsDirectory = ""  # resolved dynamically via gameDocumentsDirectory()
    GameSavesDirectory = ""     # resolved dynamically via gameSavesDirectory()
    GameSaveExtension = "ess"

    GameNexusId = 1704
    GameNexusName = "skyrimspecialedition"

    GameSupportURL = "https://github.com/Marc1326/anvil-wiki"

    ProtonShimFiles: list[str] = ["winhttp.dll"]

    ScriptExtenderDir = "SKSE"

    GameDirectInstallMods = [
        "SKSE64",
        "Address Library for SKSE Plugins",
        "SSE Engine Fixes",
        "powerofthree's Tweaks",
        "Base Object Swapper",
        "Keyword Item Distributor",
        "Spell Perk Item Distributor",
    ]

    # -- Primary & DLC Plugins -----------------------------------------------

    PRIMARY_PLUGINS = [
        "Skyrim.esm",
        "Update.esm",
        "Dawnguard.esm",
        "HearthFires.esm",
        "Dragonborn.esm",
    ]

    # -- BA2-Packing (loose files → BA2 archives via BSArch/Proton) ---------

    NeedsBa2Packing = True
    Ba2Format = "sse"             # BSArch: -sse -mt
    Ba2TextureFormat = "sse"      # SSE textures: same flag
    Ba2IniSection = "Archive"
    Ba2IniKey = "sResourceArchiveList2"   # NOTE: "List2" not "2List"!
    Ba2IniFile = "SkyrimCustom.ini"

    DLC_PLUGINS = [
        "Dawnguard.esm",
        "HearthFires.esm",
        "Dragonborn.esm",
    ]

    # -- Windows-Pfade (innerhalb Proton-Prefix) ----------------------------
    # Windows: Documents/My Games/Skyrim Special Edition

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
                pattern=["skse64_loader.exe", "skse64_1_6_1170.dll"],
                target="",
                description="Skyrim Script Extender 64 — erweitert die Scripting-Engine",
                detect_installed=["skse64_loader.exe"],
                required_by=["SKSE-Plugins", "SkyUI", "MCM", "RaceMenu"],
                nexus_id=30379,
            ),
            FrameworkMod(
                name="Address Library for SKSE Plugins",
                pattern=["SKSE/Plugins/versionlib*.bin", "Data/SKSE/Plugins/versionlib*.bin"],
                target="Data",
                description="Adressen-Datenbank fuer SKSE-Plugins (versions-unabhaengig)",
                detect_installed=["Data/SKSE/Plugins/versionlib*.bin"],
                required_by=["Die meisten SKSE-Plugins"],
                nexus_id=32444,
            ),
            FrameworkMod(
                name="SSE Engine Fixes",
                pattern=["Data/SKSE/Plugins/EngineFixes.dll"],
                target="Data",
                description="Behebt Engine-Bugs und verbessert Performance",
                detect_installed=["Data/SKSE/Plugins/EngineFixes.dll"],
                nexus_id=17230,
            ),
            FrameworkMod(
                name="powerofthree's Tweaks",
                pattern=["Data/SKSE/Plugins/po3_Tweaks.dll"],
                target="Data",
                description="Framework-Erweiterungen und Bug-Fixes",
                detect_installed=["Data/SKSE/Plugins/po3_Tweaks.dll"],
                nexus_id=51073,
            ),
            FrameworkMod(
                name="Base Object Swapper",
                pattern=["Data/SKSE/Plugins/BaseObjectSwapper.dll"],
                target="Data",
                description="Ermoeglicht dynamischen Austausch von Objekten",
                detect_installed=["Data/SKSE/Plugins/BaseObjectSwapper.dll"],
                required_by=["Object-Swap-Mods"],
                nexus_id=60805,
            ),
            FrameworkMod(
                name="Keyword Item Distributor",
                pattern=["Data/SKSE/Plugins/KeywordItemDistributor.dll"],
                target="Data",
                description="Verteilt Keywords an Items zur Laufzeit",
                detect_installed=["Data/SKSE/Plugins/KeywordItemDistributor.dll"],
                nexus_id=55728,
            ),
            FrameworkMod(
                name="Spell Perk Item Distributor",
                pattern=["Data/SKSE/Plugins/SpellPerkItemDistributor.dll"],
                target="Data",
                description="Verteilt Spells, Perks und Items an NPCs",
                detect_installed=["Data/SKSE/Plugins/SpellPerkItemDistributor.dll"],
                required_by=["SPID-Patches"],
                nexus_id=36869,
            ),
            FrameworkMod(
                name="SKSE64 Proton Shim",
                pattern=["winhttp.dll"],
                target="",
                description="Proxy-DLL — ermoeglicht SKSE64 unter Linux/Proton",
                detect_installed=["winhttp.dll"],
                required_by=["SKSE64"],
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
            "**/readme*.txt",
            "**/docs/**",
            "**/changelog*.txt",
            "**/*.md",
            "**/credits*.txt",
            "**/fomod/**",
        ]

    def get_default_categories(self) -> list[dict] | None:
        """Return Skyrim SE specific default categories."""
        return [
            {"id": 1, "name": "Gameplay"},
            {"id": 2, "name": "Waffen & Rüstung"},
            {"id": 3, "name": "Magie & Spells"},
            {"id": 4, "name": "NPCs & Followers"},
            {"id": 5, "name": "Quests"},
            {"id": 6, "name": "Grafik & ENB"},
            {"id": 7, "name": "Texturen"},
            {"id": 8, "name": "UI"},
            {"id": 9, "name": "Audio"},
            {"id": 10, "name": "Umgebung & Landschaft"},
            {"id": 11, "name": "Häuser & Player Homes"},
            {"id": 12, "name": "Charaktererstellung"},
            {"id": 13, "name": "Animationen"},
            {"id": 14, "name": "Bug Fixes"},
            {"id": 15, "name": "Utilities"},
            {"id": 16, "name": "Frameworks"},
            {"id": 17, "name": "Patches"},
            {"id": 18, "name": "Overhauls"},
        ]

    def executables(self) -> list[dict[str, str]]:
        """Return executable definitions for Skyrim Special Edition.

        Includes: Skyrim SE, SKSE64 (if installed), Launcher, Creation Kit.
        """
        result: list[dict[str, str]] = [
            {"name": "Skyrim Special Edition", "binary": self.GameBinary},
            {"name": "Skyrim SE Launcher", "binary": self.GameLauncher},
        ]

        # SKSE64 injection is handled by the winhttp.dll Proton shim —
        # skse64_loader.exe is not needed and would cause double injection.
        if self._game_path is not None:
            # Add Creation Kit if available
            ck = self._game_path / self._CK_BINARY
            if ck.exists():
                result.append({"name": "Creation Kit", "binary": self._CK_BINARY})

        return result

    def iniFiles(self) -> list[str]:
        """Return config files managed by Skyrim Special Edition.

        Skyrim.ini, SkyrimPrefs.ini, SkyrimCustom.ini.
        Located in the My Games/Skyrim Special Edition directory.
        """
        return ["Skyrim.ini", "SkyrimPrefs.ini", "SkyrimCustom.ini"]
