"""Dragon Age 2 game plugin for Anvil Organizer — auto-generated from MO2.

Dragon Age 2 platziert Mods im Documents-Verzeichnis unter
BioWare/Dragon Age 2/packages/core/override. Savegames liegen in
Characters/.

Features:
  - Store-Erkennung (Steam)
  - Proton-Prefix-Pfade fuer Dokumente und Savegames
  - Nexus-Mods-Integration

TODO:
  - Savegame-Vorschau (screen.dds)
  - EA Desktop Erkennung
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class DragonAge2Game(BaseGame):
    """Dragon Age 2 support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Dragon Age 2 Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Dragon Age 2"
    GameShortName = "dragonage2"
    GameBinary = "bin_ship/DragonAge2.exe"
    GameDataPath = ""

    GameSteamId = 1238040

    GameSaveExtension = "das"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Dragon-Age-II"
    )

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/Documents/BioWare/Dragon Age 2"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/Documents/BioWare/Dragon Age 2/Characters"
    )
