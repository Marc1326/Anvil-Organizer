"""The Witcher 3: Wild Hunt game plugin for Anvil Organizer.

Based on the MO2 basic_games plugin by Holt59, adapted for
Linux with Proton prefix support.

Features implemented:
  - Store detection (Steam, GOG — multiple editions each)
  - Proton prefix paths for documents and saves
  - Executable list (Witcher 3 x64, DX12 variant)
  - INI/settings file list
  - Witcher 3-specific path helpers (Mods, DLC, menu config)
  - Script Merger detection

TODO (future):
  - Script Merger Integration (Konflikt-Erkennung + Aufruf)
  - Mod-Struktur-Validator (modXXX/content/ Pattern)
  - .bundle Konflikt-Erkennung
  - .ws Script Konflikt-Erkennung
  - DLC vs Mods Ordner-Routing bei Installation
  - Menu-XML Mod-Erkennung (bin/config/r4game/user_config_matrix/pc/)
  - Save-Game Screenshot-Zuordnung (.sav -> .png)
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame


class Witcher3Game(BaseGame):
    """The Witcher 3: Wild Hunt support plugin."""

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "The Witcher 3 Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute (aus MO2 game_witcher3.py) -------------------------

    GameName = "The Witcher 3: Wild Hunt"
    GameShortName = "witcher3"
    GameBinary = "bin/x64/witcher3.exe"
    GameDataPath = "Mods"  # Mods go into <GameDir>/Mods/

    # Steam: 292030 (Standard), 499450 (GOTY)
    GameSteamId = [292030, 499450]
    # GOG: Multiple editions (Standard, GOTY, Enhanced, etc.)
    GameGogId = [1640424747, 1495134320, 1207664663, 1207664643]

    GameLauncher = ""  # No separate launcher

    GameFlattenArchive = False        # Keep modXXX/content/ structure intact
    GameNestModsUnderName = False     # Witcher 3 scannt nur EINE Ebene in Mods/

    # Multi-Ordner Routing: Mods wie "Brothers In Arms" haben
    # mods/, dlc/, bin/ Unterordner die an verschiedene Ziele gehen
    GameMultiFolderRoutes = {"mods": "Mods", "dlc": "DLC", "bin": "bin"}

    GameDocumentsDirectory = ""  # resolved dynamically via gameDocumentsDirectory()
    GameSavesDirectory = ""     # resolved dynamically via gameSavesDirectory()
    GameSaveExtension = "sav"

    GameNexusId = 952
    GameNexusName = "witcher3"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-The-Witcher-3"
    )

    # -- Windows-Pfade (innerhalb Proton-Prefix) ----------------------------
    # MO2: %DOCUMENTS%/The Witcher 3

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/Documents/The Witcher 3"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/Documents/The Witcher 3/gamesaves"
    )

    # -- DX12-Binary --------------------------------------------------------

    _DX12_BINARY = "bin/x64_dx12/witcher3.exe"

    # -- Script Merger (externes Tool) --------------------------------------

    _SCRIPT_MERGER_BINARY = "WitcherScriptMerger/WitcherScriptMerger.exe"

    # -- Ueberschriebene Methoden -------------------------------------------

    def gameDocumentsDirectory(self) -> Path | None:
        """Return the game's documents directory (Documents/The Witcher 3).

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
        """Return the save game directory (Documents/The Witcher 3/gamesaves).

        For Steam (Proton): derived from the Proton prefix.
        Returns None if no prefix is found.
        """
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_SAVES
            if path.is_dir():
                return path
        return None

    # -- Witcher 3-spezifische Pfade ----------------------------------------

    def mods_path(self) -> Path | None:
        """Return the Mods directory in the game installation folder.

        Witcher 3 mods are installed as subfolders (modXXX/content/)
        inside <GameDir>/Mods/.
        """
        if self._game_path is not None:
            return self._game_path / "Mods"
        return None

    def dlc_path(self) -> Path | None:
        """Return the DLC directory in the game installation folder.

        Some mods install into <GameDir>/DLC/ as dlcXXX/ subfolders,
        alongside official DLC content.
        """
        if self._game_path is not None:
            return self._game_path / "DLC"
        return None

    def menu_config_path(self) -> Path | None:
        """Return the menu config directory for XML menu mods.

        Located at bin/config/r4game/user_config_matrix/pc/.
        Menu mods add .xml files here for in-game configuration options.
        """
        if self._game_path is not None:
            return (
                self._game_path / "bin" / "config" / "r4game"
                / "user_config_matrix" / "pc"
            )
        return None

    def vanilla_scripts_dir(self) -> Path | None:
        """Return the vanilla scripts directory (content/content0/scripts).

        Used by the native Script Merger to compare mod scripts against
        the original game files for 3-way diff.
        """
        if self._game_path is not None:
            path = self._game_path / "content" / "content0" / "scripts"
            if path.is_dir():
                return path
        return None

    def has_script_merger(self) -> bool:
        """Check if Witcher Script Merger is available.

        Looks for WitcherScriptMerger.exe in the game directory.
        Script Merger is an external tool that resolves .ws and .bundle
        conflicts between mods.
        """
        if self._game_path is None:
            return False
        return (self._game_path / self._SCRIPT_MERGER_BINARY).exists()

    # TODO: Script Merger Integration (Konflikt-Erkennung + Aufruf)
    # TODO: Mod-Struktur-Validator (modXXX/content/ Pattern)
    # TODO: .bundle Konflikt-Erkennung
    # TODO: .ws Script Konflikt-Erkennung
    # TODO: DLC vs Mods Ordner-Routing bei Installation
    # TODO: Menu-XML Mod-Erkennung
    # TODO: Save-Game Screenshot-Zuordnung (.sav -> .png)

    def get_conflict_ignores(self) -> list[str]:
        """Return patterns for harmless files in Witcher 3 mods."""
        return [
            "**/readme*.txt",  # readme files
        ]

    def executables(self) -> list[dict[str, str]]:
        """Return executable definitions for The Witcher 3.

        Includes the main x64 binary and the DX12 variant (Next-Gen)
        if available.
        """
        result: list[dict[str, str]] = [
            {"name": "The Witcher 3", "binary": self.GameBinary},
        ]

        # Add DX12 variant (Next-Gen update) if available
        if self._game_path is not None:
            dx12 = self._game_path / self._DX12_BINARY
            if dx12.exists():
                result.append(
                    {"name": "The Witcher 3 (DX12)", "binary": self._DX12_BINARY}
                )

        return result

    def iniFiles(self) -> list[str]:
        """Return config files managed by The Witcher 3.

        From MO2: user.settings and input.settings.
        Located in the Documents/The Witcher 3 directory.
        """
        return ["user.settings", "input.settings"]
