"""Game plugin for Stellar Blade — Anvil Organizer.

Unreal Engine 4 (4.26.2) game with IO Store (.pak/.utoc/.ucas).
Pak mods go into the ~mods folder inside Paks, UE4SS mods into
SB/Binaries/Win64/UE4SS/Mods.
Steam only.
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class StellarBladeGame(BaseGame):
    """Stellar Blade support plugin."""

    Tested = False

    Name = "Stellar Blade Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    GameName = "Stellar Blade"
    GameShortName = "StellarBlade"
    GameBinary = "SB/Binaries/Win64/SB-Win64-Shipping.exe"
    GameDataPath = "SB/Content/Paks/~mods"

    GameSteamId = 3489700

    GameLauncher = "SB.exe"
    GameSaveExtension = "sav"

    GameNexusId = 7804
    GameNexusName = "stellarblade"

    GameSupportURL = "https://www.nexusmods.com/stellarblade"

    # IO Store: Symlinks funktionieren nicht, Mods muessen kopiert werden
    GameCopyDeployPaths: list[str] = ["SB/Content/Paks/~mods"]

    # Das Spiel haengt die Paks alphabetisch ein und laesst die letzte
    # gewinnen. Ohne Zaehler im Dateinamen haette die Reihenfolge in Anvil
    # keine Wirkung.
    GamePakLoadOrderPrefix = True

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/AppData/Local"
        "/SB/Saved/Config/WindowsNoEditor"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/AppData/Local"
        "/SB/Saved/SaveGames"
    )

    def executables(self) -> list[dict[str, str]]:
        return [
            {"name": "Stellar Blade", "binary": self.GameBinary},
            {"name": "Stellar Blade (Launcher)", "binary": "SB.exe"},
        ]

    def get_framework_mods(self) -> list[FrameworkMod]:
        return [
            FrameworkMod(
                name="UE4SS",
                pattern=["UE4SS.dll", "UE4SS-settings.ini"],
                target="SB/Binaries/Win64",
                description="Unreal Engine Scripting System — Lua/C++ Mod-Loader",
                detect_installed=["SB/Binaries/Win64/UE4SS.dll"],
                required_by=["Lua-Mods", "Blueprint-Mods"],
            ),
        ]

    def iniFiles(self) -> list[str]:
        return [
            "GameUserSettings.ini",
            "Engine.ini",
            "Input.ini",
        ]

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

    def get_conflict_ignores(self) -> list[str]:
        return [
            "**/readme*.txt",
            "**/docs/**",
        ]
