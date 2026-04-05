"""Game plugin for MechWarrior 5: Mercenaries — Anvil Organizer.

Unreal Engine 4 game. Mods go into the Mods folder inside MW5Mercs.
Supports Steam, GOG and Epic.
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame


class MechWarrior5Game(BaseGame):
    """MechWarrior 5: Mercenaries support plugin."""

    Tested = False

    Name = "MechWarrior 5: Mercenaries Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    GameName = "MechWarrior 5: Mercenaries"
    GameShortName = "MechWarrior5"
    GameBinary = "MW5Mercs/Binaries/Win64/MechWarrior-Win64-Shipping.exe"
    GameDataPath = "MW5Mercs/Mods"

    GameSteamId = 784080
    GameGogId = 2147483045
    GameEpicId = "Camel"

    GameLauncher = ""
    GameSaveExtension = "sav"

    GameNexusId = 3099
    GameNexusName = "mechwarrior5mercenaries"

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/AppData/Local"
        "/MW5Mercs/Saved"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/AppData/Local"
        "/MW5Mercs/Saved/SaveGames"
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
            {"name": "MechWarrior 5", "binary": self.GameBinary},
        ]

    def iniFiles(self) -> list[str]:
        return [
            "Engine.ini",
            "GameUserSettings.ini",
            "Input.ini",
            "Game.ini",
        ]

    def get_default_categories(self) -> list[dict] | None:
        return [
            {"id": 1, "name": "Gameplay"},
            {"id": 2, "name": "Mechs"},
            {"id": 3, "name": "Weapons"},
            {"id": 4, "name": "Maps & Missions"},
            {"id": 5, "name": "Graphics & Visuals"},
            {"id": 6, "name": "UI"},
            {"id": 7, "name": "Audio"},
            {"id": 8, "name": "Bug Fixes"},
            {"id": 9, "name": "Utilities"},
        ]

    def get_conflict_ignores(self) -> list[str]:
        return [
            "**/readme*.txt",
            "**/mod.json",
        ]
