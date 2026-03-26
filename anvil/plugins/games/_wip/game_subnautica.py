"""Subnautica game plugin for Anvil Organizer — auto-generated from MO2.

Subnautica nutzt BepInEx als Mod-Loader. Mods werden entweder als
BepInEx-Plugins oder als QMods installiert.

Features:
  - Store-Erkennung (Steam, Epic)
  - Nexus-Mods-Integration

TODO:
  - BepInEx-Erkennung und Auto-Setup
  - QMods-Unterstuetzung
  - Root-Mapping fuer BepInEx-Dateien
  - winhttp.dll forced load
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class SubnauticaGame(BaseGame):
    """Subnautica support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Subnautica Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Subnautica"
    GameShortName = "subnautica"
    GameBinary = "Subnautica.exe"
    GameDataPath = ""

    GameSteamId = 264710
    GameEpicId = "Jaguar"

    GameNexusName = "subnautica"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Subnautica"
    )

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_SAVES = (
        "drive_c/users/steamuser/AppData/LocalLow"
        "/Unknown Worlds/Subnautica/Subnautica/SavedGames"
    )
