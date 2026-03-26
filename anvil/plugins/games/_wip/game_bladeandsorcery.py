"""Blade & Sorcery game plugin for Anvil Organizer — auto-generated from MO2.

Blade & Sorcery platziert Mods im StreamingAssets/Mods Verzeichnis.
Savegames liegen im Documents-Ordner.

Features:
  - Store-Erkennung (Steam)
  - Proton-Prefix-Pfade fuer Dokumente und Savegames
  - Nexus-Mods-Integration

TODO:
  - Savegame-Metadata-Parsing (JSON-Format)
  - Spielmodus-Erkennung
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class BladeAndSorceryGame(BaseGame):
    """Blade & Sorcery support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Blade & Sorcery Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Blade & Sorcery"
    GameShortName = "bladeandsorcery"
    GameBinary = "BladeAndSorcery.exe"
    GameDataPath = "BladeAndSorcery_Data/StreamingAssets/Mods"

    GameSteamId = 629730

    GameSaveExtension = "chr"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Blade-&-Sorcery"
    )

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/Documents/My Games/BladeAndSorcery"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/Documents/My Games/BladeAndSorcery"
        "/Saves/Default"
    )
