"""Final Fantasy VII Remake game plugin for Anvil Organizer — auto-generated from MO2.

Final Fantasy VII Remake nutzt Unreal Engine 4 und platziert Mods als
.pak-Dateien im End/Content/Paks/~mods Verzeichnis.

Features:
  - Store-Erkennung (Steam)
  - Nexus-Mods-Integration

TODO:
  - Load-Order via Dateinamen-Prefix (00_, 01_, etc.)
  - Custom Root-Mapping fuer .pak Dateien
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class FinalFantasy7RemakeGame(BaseGame):
    """Final Fantasy VII Remake support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Final Fantasy VII Remake Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Final Fantasy VII Remake"
    GameShortName = "finalfantasy7remake"
    GameBinary = "ff7remake.exe"
    GameDataPath = "End/Content/Paks/~mods"

    GameSteamId = 1462040

    GameSaveExtension = "sav"

    GameNexusName = "finalfantasy7remake"
