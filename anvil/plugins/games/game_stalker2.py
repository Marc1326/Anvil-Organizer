"""Game plugin for S.T.A.L.K.E.R. 2: Heart of Chornobyl — Anvil Organizer.

Unreal Engine 5 game with IO Store (symlinks don't work).
Pak mods go into ~mods, blueprint mods into LogicMods, loaders and
dll plugins into Binaries/Win64.
Supports Steam, GOG and Epic.
"""

from __future__ import annotations

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class Stalker2Game(BaseGame):
    """S.T.A.L.K.E.R. 2: Heart of Chornobyl support plugin."""

    Tested = False

    Name = "S.T.A.L.K.E.R. 2 Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.1.0"

    GameName = "S.T.A.L.K.E.R. 2: Heart of Chornobyl"
    GameShortName = "Stalker2"
    GameBinary = "Stalker2/Binaries/Win64/Stalker2-Win64-Shipping.exe"

    # Basis ist Stalker2, nicht der Pak-Ordner -- das Spiel kennt drei
    # Mod-Arten mit drei Zielen, die Verteilung macht GameDeployRoutes.
    GameDataPath = "Stalker2"

    GameSteamId = 1643320
    GameGogId = 1529799785
    GameEpicId = "c04ba25a0e674b1ab3ea79e50c24a722"

    GameLauncher = "Stalker2.exe"
    GameSaveExtension = "sav"

    GameNexusId = 6944
    GameNexusName = "stalker2heartofchornobyl"

    GameSupportURL = "https://www.nexusmods.com/stalker2heartofchornobyl"

    # IO Store: Symlinks funktionieren nicht, Mods muessen kopiert werden.
    # Win64 steht mit drin, weil Proton eine verlinkte DLL nicht als
    # gueltige DLL annimmt und die Loader dann nie starten.
    GameCopyDeployPaths: list[str] = [
        "Stalker2/Content/Paks",
        "Stalker2/Binaries/Win64",
    ]

    # Nicht ohne Begrenzung umbenennen: der Zaehler wuerde auch die Paks
    # in LogicMods treffen, und dort sucht UE4SS seinen Blueprint am
    # Dateinamen -- umbenannt findet er ihn nicht mehr.
    GamePakLoadOrderPrefix = False

    # In ~mods dagegen zaehlt nur die alphabetische Reihenfolge: das Spiel
    # haengt die Paks der Reihe nach ein und laesst die letzte gewinnen.
    # Ohne Zaehler waere die Reihenfolge aus Anvil hier wirkungslos.
    # LogicMods und Binaries/Win64 stehen bewusst nicht mit drin.
    GamePakLoadOrderDirs: list[str] = ["Stalker2/Content/Paks/~mods"]

    # Diese drei Ordner legt erst das Modden an, das Spiel selbst bringt
    # sie nicht mit. Was dort ohne Anvil auftaucht, wurde von Hand
    # hineinkopiert und laedt an der Mod-Liste vorbei.
    GameModDirs: list[str] = [
        "Stalker2/Content/Paks/~mods",
        "Stalker2/Content/Paks/LogicMods",
        "Stalker2/Binaries/Win64/plugins",
    ]

    # Dieser Ordner benennt im Archiv nur die Mod-Art und gehoert nicht
    # in den Zielpfad. LogicMods bleibt stehen -- er ist das einzige
    # Kennzeichen, an dem ein Blueprint-Mod ohne Container zu erkennen ist.
    GameDeployStripPrefixes: list[str] = ["~mods"]

    # Faengt ein Mod damit an, bringt er seine Zielstruktur schon mit --
    # dann wird nichts umsortiert.
    GameDeployAnchors: list[str] = ["Stalker2", "Content", "Binaries"]

    # Drei Mod-Arten, drei Ziele. Ohne eigene Struktur entscheidet der
    # Mount-Point, der Ordnername oder die Dateiendung.
    GameDeployRoutes: list[dict] = [
        # Blueprint-Mods erkennt man am Mount-Point ihres Containers:
        # er zeigt auf Content/Mods/. Am Dateinamen ist das nicht zu
        # sehen -- sie liegen flach im Archiv wie jede andere Pak-Mod.
        # Im ~mods-Ordner bleiben sie wirkungslos.
        {"dest": "Content/Paks/LogicMods", "mount_contains": ["/content/mods/"]},
        # Viele Autoren legen ihren Blueprint-Mod in einen LogicMods-Ordner,
        # damit die Mod-Manager ihn zuordnen koennen. Der Ordner selbst
        # darf sich im Ziel nicht verdoppeln.
        {
            "dest": "Content/Paks/LogicMods",
            "folders": ["logicmods"],
            "flatten": True,
        },
        # UE4SS-Zubehoer behaelt seinen Unterbau. Steht vor der
        # plugins-Regel, sonst wuerde ein ue4ss/plugins/-Ordner dort landen.
        {"dest": "Binaries/Win64", "folders": ["ue4ss"]},
        # Der Dll Plugin Loader laedt alles aus seinem plugins-Ordner
        {"dest": "Binaries/Win64/plugins", "folders": ["plugins"], "flatten": True},
        # Die Loader selbst sind einzelne DLLs neben der Spiel-Exe
        {"dest": "Binaries/Win64", "suffixes": [".dll"], "flatten": True},
        # Alles Uebrige: gewoehnliche Pak-Mods
        {
            "dest": "Content/Paks/~mods",
            "suffixes": [".pak", ".ucas", ".utoc", ".sig"],
        },
    ]

    # Ohne diese Eintraege laedt Proton seine eigenen DLLs und die Loader
    # werden nie gestartet -- damit bleiben Lua- und Blueprint-Mods
    # wirkungslos. dwmapi gehoert zu UE4SS, winmm und xinput1_3 sind die
    # beiden Varianten des Dll Plugin Loaders.
    GameProtonDllOverrides: dict[str, str] = {
        "dwmapi": "native,builtin",
        "winmm": "native,builtin",
        "xinput1_3": "native,builtin",
    }

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/AppData/Local"
        "/Stalker2/Saved/Config/Windows"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/AppData/Local"
        "/Stalker2/Saved/SaveGames"
    )

    def executables(self) -> list[dict[str, str]]:
        return [
            {"name": "S.T.A.L.K.E.R. 2", "binary": self.GameBinary},
            {"name": "S.T.A.L.K.E.R. 2 (Launcher)", "binary": "Stalker2.exe"},
        ]

    def get_framework_mods(self) -> list[FrameworkMod]:
        # UE4SS wird zuerst an dwmapi.dll erkannt -- ohne die laedt
        # Windows den Loader nie, egal ob UE4SS.dll daneben liegt.
        # UETools steht bewusst nicht in dieser Liste: der Autor hat es
        # mit Spiel-Patch 1.6 eingestellt und verweist selbst auf UE4SS
        # und den Simple BP ModLoader.
        return [
            FrameworkMod(
                name="UE4SS",
                pattern=["UE4SS.dll"],
                target="Stalker2/Binaries/Win64",
                description="Unreal Engine Scripting System — Lua/C++ Mod-Loader",
                detect_installed=[
                    "Stalker2/Binaries/Win64/dwmapi.dll",
                    "Stalker2/Binaries/Win64/UE4SS.dll",
                    "Stalker2/Binaries/Win64/ue4ss/UE4SS.dll",
                ],
                required_by=["Lua-Mods", "Blueprint-Mods"],
                nexus_id=1910,
            ),
            FrameworkMod(
                name="Simple BP ModLoader",
                pattern=["Simple_Mod_Loader*.pak", "Simple_Mod_Loader*.utoc"],
                target="Stalker2/Content/Paks/~mods",
                description="Mod-Loader mit Entwicklerkonsole, als Pak-Mod",
                detect_installed=[
                    "Stalker2/Content/Paks/~mods/Simple_Mod_Loader*",
                    "Stalker2/Content/Paks/Simple_Mod_Loader*",
                ],
                required_by=["Blueprint-Mods", "Konsolen-Befehle"],
                nexus_id=304,
            ),
            FrameworkMod(
                name="Dll Plugin Loader",
                pattern=["winmm.dll", "xinput1_3.dll"],
                target="Stalker2/Binaries/Win64",
                description="Laedt mehrere DLL-Mods aus dem plugins-Ordner",
                detect_installed=[
                    "Stalker2/Binaries/Win64/winmm.dll",
                    "Stalker2/Binaries/Win64/xinput1_3.dll",
                ],
                required_by=["DLL-Mods"],
                nexus_id=2058,
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
