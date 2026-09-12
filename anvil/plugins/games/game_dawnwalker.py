"""Game plugin for The Blood of Dawnwalker — Anvil Organizer.

Unreal Engine 5.5 game with IO Store (symlinks don't work).
No official mod support. Pak mods go into ~mods, blueprint mods into
LogicMods, UE4SS and its Lua mods into Binaries/Win64, and the SML
console loader straight into Paks.
Supports Steam and GOG.
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class DawnwalkerGame(BaseGame):
    """The Blood of Dawnwalker support plugin."""

    Tested = False

    Name = "The Blood of Dawnwalker Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    GameName = "The Blood of Dawnwalker"
    GameShortName = "Dawnwalker"
    GameBinary = "Dawnwalker/Binaries/Win64/Dawnwalker.exe"

    # Basis ist der Projektordner, nicht der Pak-Ordner -- das Spiel kennt
    # mehrere Mod-Arten mit eigenen Zielen, die Verteilung macht
    # GameDeployRoutes.
    GameDataPath = "Dawnwalker"

    GameSteamId = 3751260
    GameGogId = 1889754300

    GameSaveExtension = "sav"

    GameNexusName = "thebloodofdawnwalker"
    GameSupportURL = "https://www.nexusmods.com/thebloodofdawnwalker"

    # IO Store: Symlinks funktionieren nicht, Mods muessen kopiert werden.
    # Win64 steht mit drin, weil Proton eine verlinkte DLL nicht als
    # gueltige DLL annimmt und UE4SS dann nie startet.
    GameCopyDeployPaths: list[str] = [
        "Dawnwalker/Content/Paks",
        "Dawnwalker/Binaries/Win64",
        "Dawnwalker/Mods",
    ]

    # Nicht ueberall umbenennen: in LogicMods sucht UE4SS seinen Blueprint
    # am Dateinamen, und der SML-Loader heisst fest SML.*.
    GamePakLoadOrderPrefix = False

    # Nur hier zaehlt die alphabetische Reihenfolge -- das Spiel haengt die
    # Paks der Reihe nach ein und laesst die letzte gewinnen. Ohne Zaehler
    # waere die Sortierung aus Anvil in ~mods wirkungslos.
    GamePakLoadOrderDirs: list[str] = ["Dawnwalker/Content/Paks/~mods"]

    # Diese Ordner legt erst das Modden an, das Spiel bringt sie nicht mit.
    # Was dort ohne Anvil auftaucht, wurde von Hand hineinkopiert.
    GameModDirs: list[str] = [
        "Dawnwalker/Content/Paks/~mods",
        "Dawnwalker/Content/Paks/LogicMods",
        "Dawnwalker/Binaries/Win64/ue4ss/Mods",
        "Dawnwalker/Mods",
    ]

    # Benennt im Archiv nur die Mod-Art und gehoert nicht in den Zielpfad.
    GameDeployStripPrefixes: list[str] = ["~mods"]

    # Faengt ein Mod damit an, bringt er seine Zielstruktur schon mit --
    # dann wird nichts umsortiert. So kommen auch SML-Mods an, die als
    # Dawnwalker/Mods/<Name>/ ausgeliefert werden.
    GameDeployAnchors: list[str] = ["Dawnwalker", "Content", "Binaries", "Engine"]

    GameDeployRoutes: list[dict] = [
        # Der SML-Loader liegt direkt in Paks, nicht in ~mods -- dort
        # wuerde er nicht geladen. Muss vor der Pak-Regel stehen.
        {"dest": "Content/Paks", "names": ["SML.*"], "flatten": True},
        # Blueprint-Mods erkennt man am Mount-Point ihres Containers:
        # er zeigt auf Content/Mods/. Am Dateinamen ist das nicht zu sehen.
        {"dest": "Content/Paks/LogicMods", "mount_contains": ["/content/mods/"]},
        # Manche Autoren packen ihren Blueprint-Mod schon in einen
        # LogicMods-Ordner. Der darf sich im Ziel nicht verdoppeln.
        {
            "dest": "Content/Paks/LogicMods",
            "folders": ["logicmods"],
            "flatten": True,
        },
        # UE4SS-Zubehoer behaelt seinen Unterbau (ue4ss/UE4SS.dll,
        # ue4ss/Mods/...). Steht vor der DLL-Regel, sonst landet
        # UE4SS.dll flach neben der Exe.
        {"dest": "Binaries/Win64", "folders": ["ue4ss"]},
        # Lua-Mods ohne ue4ss-Praefix: nur Mods/<Name>/Scripts/main.lua.
        # SML-Mods liegen ebenfalls unter Mods/, bringen aber laut
        # Installationsanleitung das Dawnwalker/-Praefix mit und werden
        # schon vom Anker abgefangen.
        {"dest": "Binaries/Win64/ue4ss", "first_folder": ["Mods"]},
        # Der Loader selbst ist eine einzelne DLL neben der Spiel-Exe
        {"dest": "Binaries/Win64", "suffixes": [".dll"], "flatten": True},
        # Alles Uebrige: gewoehnliche Pak-Mods
        {
            "dest": "Content/Paks/~mods",
            "suffixes": [".pak", ".ucas", ".utoc", ".sig"],
        },
    ]

    # Ohne diesen Eintrag laedt Proton seine eigene dwmapi.dll und UE4SS
    # wird nie gestartet -- Lua- und Blueprint-Mods blieben wirkungslos.
    GameProtonDllOverrides: dict[str, str] = {"dwmapi": "native,builtin"}

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/AppData/Local"
        "/Dawnwalker/Saved/Config/Windows"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/AppData/Local"
        "/Dawnwalker/Saved/SaveGames"
    )

    def executables(self) -> list[dict[str, str]]:
        return [
            {"name": "The Blood of Dawnwalker", "binary": self.GameBinary},
        ]

    def get_framework_mods(self) -> list[FrameworkMod]:
        # UE4SS wird zuerst an dwmapi.dll erkannt -- ohne die laedt
        # Windows den Loader nie, egal ob UE4SS.dll daneben liegt.
        # Die Standard-Einstellungen von UE4SS lassen das Spiel abstuerzen;
        # die Nexus-Pakete bringen eine passende UE4SS-settings.ini mit und
        # sind an den jeweiligen Spiel-Build gebunden.
        return [
            FrameworkMod(
                name="UE4SS",
                pattern=["UE4SS.dll"],
                target="Dawnwalker/Binaries/Win64",
                description=(
                    "Unreal Engine Scripting System — Lua/Blueprint-Loader. "
                    "Nur das fuer Dawnwalker vorkonfigurierte Paket nehmen, "
                    "die Standardeinstellungen stuerzen ab; nach einem "
                    "Spiel-Update auf eine neue Fassung warten."
                ),
                detect_installed=[
                    "Dawnwalker/Binaries/Win64/dwmapi.dll",
                    "Dawnwalker/Binaries/Win64/ue4ss/UE4SS.dll",
                ],
                required_by=["Lua-Mods", "Blueprint-Mods"],
                nexus_id=18,
            ),
            FrameworkMod(
                name="Console Enabler and Mod Loader",
                pattern=["SML.pak", "SML.utoc"],
                target="Dawnwalker/Content/Paks",
                description=(
                    "Entwicklerkonsole und Blueprint-Mod-Loader (SML), "
                    "liegt direkt im Paks-Ordner"
                ),
                detect_installed=["Dawnwalker/Content/Paks/SML.pak"],
                required_by=["Blueprint-Mods", "Konsolen-Befehle"],
                nexus_id=16,
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
            {"id": 2, "name": "Combat"},
            {"id": 3, "name": "Characters & Outfits"},
            {"id": 4, "name": "Graphics & Visuals"},
            {"id": 5, "name": "UI"},
            {"id": 6, "name": "Audio"},
            {"id": 7, "name": "Quality of Life"},
            {"id": 8, "name": "Bug Fixes"},
            {"id": 9, "name": "Utilities"},
            {"id": 10, "name": "Frameworks"},
        ]

    def get_conflict_ignores(self) -> list[str]:
        return [
            "**/readme*.txt",
            "**/docs/**",
        ]
