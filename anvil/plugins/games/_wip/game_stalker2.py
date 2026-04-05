"""Game plugin for S.T.A.L.K.E.R. 2: Heart of Chornobyl — Anvil Organizer.

Unreal Engine 5 game with IO Store (symlinks don't work).
Mods go into ~mods folder inside Paks.
Supports Steam, GOG and Epic.
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class Stalker2Game(BaseGame):
    """S.T.A.L.K.E.R. 2: Heart of Chornobyl support plugin."""

    Tested = False

    Name = "S.T.A.L.K.E.R. 2 Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    GameName = "S.T.A.L.K.E.R. 2: Heart of Chornobyl"
    GameShortName = "Stalker2"
    GameBinary = "Stalker2/Binaries/Win64/Stalker2-Win64-Shipping.exe"
    GameDataPath = "Stalker2/Content/Paks/~mods"

    GameSteamId = 1643320
    GameGogId = 1529799785
    GameEpicId = "c04ba25a0e674b1ab3ea79e50c24a722"

    GameLauncher = "Stalker2.exe"
    GameSaveExtension = "sav"

    GameNexusId = 6944
    GameNexusName = "stalker2heartofchornobyl"

    # IO Store: Symlinks funktionieren nicht, Mods muessen kopiert werden
    GameCopyDeployPaths: list[str] = ["Stalker2/Content/Paks/~mods"]

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/AppData/Local"
        "/Stalker2/Saved"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/AppData/Local"
        "/Stalker2/Saved/SaveGames"
    )

    def gameDocumentsDirectory(self) -> Path | None:
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_DOCUMENTS
            if path.is_dir():
                return path
        return None

    def gameSavesDirectory(self) -> Path | None:
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_SAVES
            if path.is_dir():
                return path
        return None

    def executables(self) -> list[dict[str, str]]:
        return [
            {"name": "S.T.A.L.K.E.R. 2", "binary": self.GameBinary},
            {"name": "S.T.A.L.K.E.R. 2 (Launcher)", "binary": "Stalker2.exe"},
        ]

    def get_framework_mods(self) -> list[FrameworkMod]:
        return [
            FrameworkMod(
                name="UE4SS",
                pattern=["UE4SS.dll", "UE4SS-settings.ini"],
                target="Stalker2/Binaries/Win64",
                description="Unreal Engine Scripting System — Lua/C++ Mod-Loader",
                detect_installed=["Stalker2/Binaries/Win64/UE4SS.dll"],
                required_by=["Lua-Mods", "Blueprint-Mods"],
                nexus_id=560,
            ),
        ]

    def iniFiles(self) -> list[str]:
        return [
            "GameUserSettings.ini",
            "Engine.ini",
            "Input.ini",
        ]

    def get_default_categories(self) -> list[dict] | None:
        return [
            {"id": 1, "name": "Gameplay"},
            {"id": 2, "name": "Weapons"},
            {"id": 3, "name": "Armor & Outfits"},
            {"id": 4, "name": "Graphics & Visuals"},
            {"id": 5, "name": "UI"},
            {"id": 6, "name": "Audio"},
            {"id": 7, "name": "Anomalies & A-Life"},
            {"id": 8, "name": "NPCs & Factions"},
            {"id": 9, "name": "Maps & Locations"},
            {"id": 10, "name": "Bug Fixes"},
            {"id": 11, "name": "Utilities"},
            {"id": 12, "name": "Frameworks"},
        ]

    def get_conflict_ignores(self) -> list[str]:
        return [
            "**/readme*.txt",
            "**/docs/**",
        ]
