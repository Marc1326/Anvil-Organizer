"""Dragon's Dogma: Dark Arisen game plugin for Anvil Organizer.

Dragon's Dogma: Dark Arisen nutzt ein nativePC-Verzeichnis fuer Mods.
Das Spiel verwendet Capcoms MT Framework Engine.

Features:
  - Store-Erkennung (Steam, GOG)
  - Nexus-Mods-Integration

TODO:
  - nativePC Ordner-Validierung
  - .arc Datei-Handling
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class DragonsDogmaDarkArisenGame(BaseGame):
    """Dragon's Dogma: Dark Arisen support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Dragon's Dogma: Dark Arisen Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Dragon's Dogma: Dark Arisen"
    GameShortName = "dragonsdogma"
    GameBinary = "DDDA.exe"
    GameDataPath = "nativePC"

    GameSteamId = 367500
    GameGogId = 1242384383

    GameNexusName = "dragonsdogma"

    GameSupportURL = "https://github.com/Marc1326/anvil-wiki"
