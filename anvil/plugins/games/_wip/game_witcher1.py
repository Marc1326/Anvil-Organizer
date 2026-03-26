"""The Witcher: Enhanced Edition game plugin for Anvil Organizer — auto-generated from MO2.

The Witcher verwendet ein Data-Verzeichnis fuer Mods. Savegames sind
im Documents-Ordner unter The Witcher/saves.

Features:
  - Store-Erkennung (Steam, GOG)
  - Proton-Prefix-Pfade fuer Dokumente und Savegames
  - Nexus-Mods-Integration

TODO:
  - TheWitcherSave Datei-Parsing
  - Savegame-Vorschau
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class Witcher1Game(BaseGame):
    """The Witcher: Enhanced Edition support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "The Witcher Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "The Witcher: Enhanced Edition"
    GameShortName = "witcher"
    GameBinary = "System/witcher.exe"
    GameDataPath = "Data"

    GameSteamId = 20900
    GameGogId = 1207658924

    GameSaveExtension = "TheWitcherSave"

    GameNexusId = 150
    GameNexusName = "witcher"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-The-Witcher"
    )

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_DOCUMENTS = "drive_c/users/steamuser/Documents/The Witcher"
    _WIN_SAVES = "drive_c/users/steamuser/Documents/The Witcher/saves"
