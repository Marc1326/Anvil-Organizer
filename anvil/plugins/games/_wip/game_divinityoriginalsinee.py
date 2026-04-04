"""Divinity: Original Sin Enhanced Edition game plugin for Anvil Organizer.

Divinity: Original Sin EE nutzt ein Data-Verzeichnis fuer Mods (.pak-Dateien).
Savegames liegen im Documents-Ordner unter Larian Studios.

Features:
  - Store-Erkennung (Steam, GOG)
  - Proton-Prefix-Pfade fuer Dokumente und Savegames
  - Nexus-Mods-Integration

TODO:
  - .pak Datei-Validierung
  - DOCS_MOD Mapping (Mods die in den Documents-Ordner gehoeren)
  - Savegame-Vorschau (PNG-Screenshots)
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class DivinityOriginalSinEEGame(BaseGame):
    """Divinity: Original Sin Enhanced Edition support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Divinity: Original Sin (Enhanced Edition) Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Divinity: Original Sin (Enhanced Edition)"
    GameShortName = "divinityoriginalsinenhancededition"
    GameBinary = "Shipping/EoCApp.exe"
    GameDataPath = "Data"

    GameSteamId = [373420]
    GameGogId = [1445516929, 1445524575]

    GameSaveExtension = "lsv"

    GameNexusId = 1995
    GameNexusName = "divinityoriginalsinenhancededition"

    GameSupportURL = "https://github.com/Marc1326/anvil-wiki"

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/Documents/Larian Studios"
        "/Divinity Original Sin Enhanced Edition"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/Documents/Larian Studios"
        "/Divinity Original Sin Enhanced Edition/PlayerProfiles"
    )
