"""Dark Souls game plugin for Anvil Organizer.

Dark Souls: Prepare to Die Edition verwendet eine einfache Mod-Struktur.
Mods werden im DATA-Verzeichnis platziert. DSfix und andere Tools
ersetzen Dateien direkt im Spielverzeichnis.

Features:
  - Store-Erkennung (Steam)
  - Proton-Prefix-Pfade fuer Dokumente und Savegames
  - Nexus-Mods-Integration

TODO:
  - DSfix-Erkennung
  - .dcx Datei-Handling
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class DarkSoulsGame(BaseGame):
    """Dark Souls support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Dark Souls Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Dark Souls"
    GameShortName = "darksouls"
    GameBinary = "DATA/DARKSOULS.exe"
    GameDataPath = "DATA"

    GameSteamId = 211420

    GameSaveExtension = "sl2"

    GameNexusId = 162
    GameNexusName = "darksouls"

    GameSupportURL = "https://github.com/Marc1326/anvil-wiki"

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_DOCUMENTS = "drive_c/users/steamuser/Documents/NBGI/DarkSouls"
    _WIN_SAVES = "drive_c/users/steamuser/Documents/NBGI/DarkSouls"
