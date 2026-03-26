"""Darkest Dungeon game plugin for Anvil Organizer — auto-generated from MO2.

Darkest Dungeon Mods werden direkt ins Spielverzeichnis platziert.
Das Spiel hat separate Binaries fuer Steam und Standalone.

Features:
  - Store-Erkennung (Steam, GOG)
  - Nexus-Mods-Integration

TODO:
  - Steam Cloud Save Erkennung
  - Binary Save File Parsing
  - Mod-Ordner-Validierung (gueltige Unterverzeichnisse)
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class DarkestDungeonGame(BaseGame):
    """Darkest Dungeon support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Darkest Dungeon Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Darkest Dungeon"
    GameShortName = "darkestdungeon"
    GameBinary = "_windowsnosteam/darkest.exe"
    GameDataPath = ""

    GameSteamId = 262060
    GameGogId = 1719198803

    GameNexusId = 804
    GameNexusName = "darkestdungeon"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Darkest-Dungeon"
    )

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_SAVES = "drive_c/users/steamuser/Documents/Darkest"
