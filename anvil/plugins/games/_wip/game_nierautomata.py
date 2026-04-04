"""NieR:Automata game plugin for Anvil Organizer.

NieR:Automata Mods werden direkt ins Spielverzeichnis platziert.
FAR (Fix Automata Resolution) und andere Tools ersetzen Dateien
im Spielverzeichnis.

Features:
  - Store-Erkennung (Steam)
  - Nexus-Mods-Integration

TODO:
  - FAR-Erkennung
  - Textur-Mod-Handling
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class NierAutomataGame(BaseGame):
    """NieR:Automata support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "NieR:Automata Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "NieR:Automata"
    GameShortName = "nierautomata"
    GameBinary = "NieRAutomata.exe"
    GameDataPath = ""

    GameSteamId = 524220

    GameNexusName = "nierautomata"

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/Documents/My Games/NieR_Automata"
    )
