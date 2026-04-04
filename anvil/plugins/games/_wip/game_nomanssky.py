"""No Man's Sky game plugin for Anvil Organizer.

No Man's Sky Mods werden als .pak-Dateien ins GAMEDATA/PCBANKS/MODS
Verzeichnis installiert.

Features:
  - Store-Erkennung (Steam, GOG)
  - Nexus-Mods-Integration

TODO:
  - VR-Modus Unterstuetzung
  - .pak Datei-Validierung
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class NoMansSkyGame(BaseGame):
    """No Man's Sky support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "No Man's Sky Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "No Man's Sky"
    GameShortName = "nomanssky"
    GameBinary = "Binaries/NMS.exe"
    GameDataPath = "GAMEDATA/PCBANKS/MODS"

    GameSteamId = 275850
    GameGogId = 1446213994

    GameNexusId = 1634
    GameNexusName = "nomanssky"

    GameSupportURL = "https://github.com/Marc1326/anvil-wiki"
