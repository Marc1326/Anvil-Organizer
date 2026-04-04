"""Kingdom Come: Deliverance game plugin for Anvil Organizer.

Kingdom Come: Deliverance unterstuetzt Mods ueber ein eigenes mods-Verzeichnis.
Config-Dateien (.cfg) werden im Spielverzeichnis verwaltet.

Features:
  - Store-Erkennung (Steam, GOG, Epic)
  - Proton-Prefix-Pfade fuer Savegames
  - INI-Datei-Verwaltung (custom.cfg, system.cfg, user.cfg)
  - Nexus-Mods-Integration

TODO:
  - Mod-Ordner automatisch erstellen
  - .cfg Dateien beim Profilwechsel verwalten
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class KingdomComeDeliveranceGame(BaseGame):
    """Kingdom Come: Deliverance support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Kingdom Come: Deliverance Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Kingdom Come: Deliverance"
    GameShortName = "kingdomcomedeliverance"
    GameBinary = "bin/Win64/KingdomCome.exe"
    GameDataPath = "mods"

    GameSteamId = 379430
    GameGogId = 1719198803
    GameEpicId = "Eel"

    GameSaveExtension = "whs"

    GameNexusId = 2298
    GameNexusName = "kingdomcomedeliverance"

    GameSupportURL = "https://github.com/Marc1326/anvil-wiki"

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_SAVES = (
        "drive_c/users/steamuser/Saved Games/kingdomcome/saves"
    )

    # -- INI-Dateien --------------------------------------------------------

    def iniFiles(self) -> list[str]:
        """Config-Dateien fuer Kingdom Come: Deliverance."""
        return ["custom.cfg", "system.cfg", "user.cfg"]
