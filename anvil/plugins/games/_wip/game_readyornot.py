"""Game plugin for Ready or Not — Anvil Organizer.

Unreal Engine 5 game. Mods go into ~mods folder inside Paks.
Supports Steam only (no GOG/Epic release).
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class ReadyOrNotGame(BaseGame):
    """Ready or Not support plugin."""

    Tested = False

    Name = "Ready or Not Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    GameName = "Ready or Not"
    GameShortName = "ReadyOrNot"
    GameBinary = "ReadyOrNot/Binaries/Win64/ReadyOrNotSteam-Win64-Shipping.exe"
    GameDataPath = "ReadyOrNot/Content/Paks/~mods"

    GameSteamId = 1144200
    GameGogId = 0
    GameEpicId = ""

    GameLauncher = ""
    GameSaveExtension = "sav"

    GameNexusId = 4205
    GameNexusName = "readyornot"

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/AppData/Local"
        "/ReadyOrNot/Saved"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/AppData/Local"
        "/ReadyOrNot/Saved/SaveGames"
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
            {"name": "Ready or Not", "binary": self.GameBinary},
        ]

    def get_framework_mods(self) -> list[FrameworkMod]:
        return [
            FrameworkMod(
                name="UE4SS",
                pattern=["UE4SS.dll", "UE4SS-settings.ini"],
                target="ReadyOrNot/Binaries/Win64",
                description="Unreal Engine Scripting System — Lua/C++ Mod-Loader",
                detect_installed=["ReadyOrNot/Binaries/Win64/UE4SS.dll"],
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
            {"id": 2, "name": "Weapons & Equipment"},
            {"id": 3, "name": "Maps"},
            {"id": 4, "name": "Skins & Cosmetics"},
            {"id": 5, "name": "AI & NPCs"},
            {"id": 6, "name": "Graphics & Visuals"},
            {"id": 7, "name": "UI"},
            {"id": 8, "name": "Audio"},
            {"id": 9, "name": "Bug Fixes"},
            {"id": 10, "name": "Utilities"},
        ]

    def get_conflict_ignores(self) -> list[str]:
        return [
            "**/readme*.txt",
            "**/docs/**",
        ]
