"""Valheim game plugin for Anvil Organizer.

Valheim nutzt BepInEx als Mod-Loader. Mods werden ins Spielverzeichnis
installiert, BepInEx-Plugins nach BepInEx/plugins/.

Features:
  - Store-Erkennung (Steam — mehrere App-IDs)
  - Proton-Prefix-Pfade fuer Savegames
  - Nexus-Mods-Integration

TODO:
  - BepInEx-Erkennung und Auto-Setup
  - Overwrite-Sync (Config-Dateien zurueck zu Mods)
  - winhttp.dll forced load
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class ValheimGame(BaseGame):
    """Valheim support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Valheim Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Valheim"
    GameShortName = "valheim"
    GameBinary = "valheim.exe"
    GameDataPath = ""

    GameSteamId = [892970, 896660, 1223920]

    GameSaveExtension = "fch"

    GameNexusId = 3667
    GameNexusName = "valheim"

    GameSupportURL = "https://github.com/Marc1326/anvil-wiki"

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_SAVES = (
        "drive_c/users/steamuser/AppData/LocalLow/IronGate/Valheim"
    )
