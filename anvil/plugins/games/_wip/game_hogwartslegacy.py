"""Game plugin for Hogwarts Legacy — Anvil Organizer.

Unreal Engine 4 game. Mods go into the ~mods folder inside Paks.
Supports Steam and GOG.
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class HogwartsLegacyGame(BaseGame):
    """Hogwarts Legacy support plugin."""

    Tested = False

    Name = "Hogwarts Legacy Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    GameName = "Hogwarts Legacy"
    GameShortName = "HogwartsLegacy"
    GameBinary = "HogwartsLegacy.exe"
    GameDataPath = "Phoenix/Content/Paks/~mods"

    GameSteamId = 990080
    GameGogId = 1456460669

    GameLauncher = ""
    GameSaveExtension = "sav"

    GameNexusId = 5064
    GameNexusName = "hogwartslegacy"

    GameSupportURL = "https://www.nexusmods.com/hogwartslegacy"

    _WIN_SAVES = (
        "drive_c/users/steamuser/AppData/Local"
        "/Hogwarts Legacy/Saved/SaveGames"
    )

    def get_default_categories(self) -> list[dict] | None:
        """Return Hogwarts Legacy specific default categories."""
        return [
            {"id": 1, "name": "Gameplay"},
            {"id": 2, "name": "Outfits & Cosmetics"},
            {"id": 3, "name": "Wands"},
            {"id": 4, "name": "Brooms"},
            {"id": 5, "name": "Companions"},
            {"id": 6, "name": "UI"},
            {"id": 7, "name": "Graphics & ReShade"},
            {"id": 8, "name": "Audio"},
            {"id": 9, "name": "Bug Fixes"},
            {"id": 10, "name": "Utilities"},
        ]
