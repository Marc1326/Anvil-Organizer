"""Game plugin for Stellar Blade — Anvil Organizer.

Unreal Engine 5 game. Mods go into the ~mods folder inside Paks.
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame


class StellarBladeGame(BaseGame):
    """Stellar Blade support plugin."""

    Tested = False

    Name = "Stellar Blade Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    GameName = "Stellar Blade"
    GameShortName = "StellarBlade"
    GameBinary = "StellarBlade.exe"
    GameDataPath = "StellarBlade/Content/Paks/~mods"

    GameSteamId = 2627090

    GameSaveExtension = "sav"

    GameNexusId = 7507
    GameNexusName = "stellarblade"

    GameSupportURL = "https://www.nexusmods.com/stellarblade"

    _WIN_SAVES = (
        "drive_c/users/steamuser/AppData/Local"
        "/StellarBlade/Saved/SaveGames"
    )

    def get_default_categories(self) -> list[dict] | None:
        """Return Stellar Blade specific default categories."""
        return [
            {"id": 1, "name": "Gameplay"},
            {"id": 2, "name": "Outfits & Cosmetics"},
            {"id": 3, "name": "Characters"},
            {"id": 4, "name": "Graphics & ReShade"},
            {"id": 5, "name": "UI"},
            {"id": 6, "name": "Audio"},
            {"id": 7, "name": "Bug Fixes"},
            {"id": 8, "name": "Utilities"},
        ]
