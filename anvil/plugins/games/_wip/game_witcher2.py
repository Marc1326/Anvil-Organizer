"""The Witcher 2: Assassins of Kings game plugin for Anvil Organizer — auto-generated from MO2.

The Witcher 2 nutzt das CookedPC-Verzeichnis fuer Mods. Config-Dateien
liegen im Documents-Ordner unter witcher 2/Config.

Features:
  - Store-Erkennung (Steam, GOG)
  - Proton-Prefix-Pfade fuer Dokumente und Savegames
  - INI-Datei-Verwaltung
  - Nexus-Mods-Integration

TODO:
  - Savegame-Vorschau (BMP-Thumbnails)
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class Witcher2Game(BaseGame):
    """The Witcher 2: Assassins of Kings support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "The Witcher 2 Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "The Witcher 2: Assassins of Kings"
    GameShortName = "witcher2"
    GameBinary = "bin/witcher2.exe"
    GameDataPath = "CookedPC"

    GameSteamId = 20920
    GameGogId = 1207658930

    GameLauncher = "Launcher.exe"

    GameSaveExtension = "sav"

    GameNexusName = "witcher2"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-The-Witcher-2"
    )

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_DOCUMENTS = "drive_c/users/steamuser/Documents/witcher 2/Config"
    _WIN_SAVES = "drive_c/users/steamuser/Documents/witcher 2/gamesaves"

    # -- INI-Dateien --------------------------------------------------------

    def iniFiles(self) -> list[str]:
        """Config-Dateien fuer The Witcher 2."""
        return [
            "User.ini",
            "Rendering.ini",
            "Community.ini",
            "UserContent.ini",
            "DIMapping.ini",
            "Input_QWERTY.ini",
            "Input_AZERTY.ini",
            "Input_QWERTZ.ini",
        ]
