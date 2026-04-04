"""Sekiro: Shadows Die Twice game plugin for Anvil Organizer.

Sekiro nutzt FromSoftware's Engine. Mods werden im mods-Verzeichnis
platziert. Savegames verwenden das .sl2 Format.

Features:
  - Store-Erkennung (Steam)
  - Nexus-Mods-Integration

TODO:
  - ModEngine Erkennung
  - .dcx Datei-Handling
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class SekiroGame(BaseGame):
    """Sekiro: Shadows Die Twice support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Sekiro: Shadows Die Twice Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Sekiro: Shadows Die Twice"
    GameShortName = "sekiro"
    GameBinary = "sekiro.exe"
    GameDataPath = "mods"

    GameSteamId = 814380

    GameSaveExtension = "sl2"

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_SAVES = "drive_c/users/steamuser/AppData/Roaming/Sekiro"
