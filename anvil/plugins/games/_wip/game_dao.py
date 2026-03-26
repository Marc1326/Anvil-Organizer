"""Dragon Age: Origins game plugin for Anvil Organizer — auto-generated from MO2.

Dragon Age: Origins platziert Mods im Documents-Verzeichnis unter
BioWare/Dragon Age/packages/core/override. Savegames liegen in
Characters/.

Features:
  - Store-Erkennung (Steam, GOG)
  - Proton-Prefix-Pfade fuer Dokumente und Savegames
  - Nexus-Mods-Integration

TODO:
  - Savegame-Vorschau (screen.dds)
  - EA Desktop Erkennung
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class DragonAgeOriginsGame(BaseGame):
    """Dragon Age: Origins support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Dragon Age: Origins Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Dragon Age: Origins"
    GameShortName = "dragonage"
    GameBinary = "bin_ship/DAOrigins.exe"
    GameDataPath = ""

    GameSteamId = [17450, 47810]
    GameGogId = 1949616134

    GameSaveExtension = "das"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Dragon-Age:-Origins"
    )

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/Documents/BioWare/Dragon Age"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/Documents/BioWare/Dragon Age/Characters"
    )
