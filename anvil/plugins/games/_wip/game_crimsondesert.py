"""Game plugin for Crimson Desert — Anvil Organizer.

BlackSpace Engine game (Pearl Abyss). Mods go into the ~mods folder inside Paks.
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class CrimsonDesertGame(BaseGame):
    """Crimson Desert support plugin."""

    Tested = False

    Name = "Crimson Desert Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    GameName = "Crimson Desert"
    GameShortName = "CrimsonDesert"
    GameBinary = "bin64/CrimsonDesert.exe"
    GameDataPath = "Paks/~mods"

    GameSteamId = 3321460

    GameSaveExtension = "save"

    GameNexusName = "crimsondesert"

    GameSupportURL = "https://www.nexusmods.com/crimsondesert"

    _WIN_SAVES = (
        "drive_c/users/steamuser/AppData/Local"
        "/Pearl Abyss/CD/save"
    )

    def get_default_categories(self) -> list[dict] | None:
        """Return Crimson Desert specific default categories."""
        return [
            {"id": 1, "name": "Gameplay"},
            {"id": 2, "name": "Outfits & Cosmetics"},
            {"id": 3, "name": "Weapons & Armor"},
            {"id": 4, "name": "Characters"},
            {"id": 5, "name": "Graphics & ReShade"},
            {"id": 6, "name": "UI"},
            {"id": 7, "name": "Audio"},
            {"id": 8, "name": "Bug Fixes"},
            {"id": 9, "name": "Utilities"},
        ]
