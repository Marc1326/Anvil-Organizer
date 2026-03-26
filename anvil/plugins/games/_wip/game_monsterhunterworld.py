"""Monster Hunter: World game plugin for Anvil Organizer — auto-generated from MO2.

Monster Hunter: World Mods werden direkt ins Spielverzeichnis platziert.
Stracker's Loader und andere Tools modifizieren die Engine.

Features:
  - Store-Erkennung (Steam)
  - Nexus-Mods-Integration

TODO:
  - Stracker's Loader Erkennung
  - nativePC Ordner-Handling
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class MonsterHunterWorldGame(BaseGame):
    """Monster Hunter: World support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Monster Hunter: World Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Monster Hunter: World"
    GameShortName = "monsterhunterworld"
    GameBinary = "MonsterHunterWorld.exe"
    GameDataPath = ""

    GameSteamId = 582010

    GameSaveExtension = "dat"

    GameNexusId = 2531
    GameNexusName = "monsterhunterworld"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Monster-Hunter:-World"
    )
