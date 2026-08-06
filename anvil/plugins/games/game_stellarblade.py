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

    # Basis ist SB, nicht der Pak-Ordner -- das Spiel kennt vier Mod-Arten
    # mit vier Zielen, die Verteilung macht GameDeployRoutes.
    GameDataPath = "SB"

    GameSteamId = 3489700

    GameLauncher = "SB.exe"
    GameSaveExtension = "sav"

    GameNexusId = 7804
    GameNexusName = "stellarblade"

    GameSupportURL = "https://www.nexusmods.com/stellarblade"

    # IO Store: Symlinks funktionieren nicht, Mods muessen kopiert werden
    GameCopyDeployPaths: list[str] = [
        "SB/Content/Paks",
        "SB/Content/Movies",
    ]

    # Nicht umbenennen. Die Mod-Autoren verbieten es ausdruecklich
    # ("Do NOT rename the files"), und die Loader suchen ihre Dateien am
    # Namen. Ein Zaehler davor macht Logic- und CNS-Mods unbrauchbar.
    GamePakLoadOrderPrefix = False

    # Diese Ordner benennen im Archiv nur die Mod-Art und gehoeren nicht
    # in den Zielpfad.
    GameDeployStripPrefixes: list[str] = ["~mods", "LuaMod", "PakMod"]

    # Faengt ein Mod damit an, bringt er seine Zielstruktur schon mit --
    # dann wird nichts umsortiert (z.B. Content/Paks/LogicMods/...).
    GameDeployAnchors: list[str] = ["SB", "Content", "Binaries", "Engine"]

    # Vier Mod-Arten, vier Ziele. Ohne eigene Struktur entscheidet die
    # Dateiendung, wohin eine Datei gehoert.
    GameDeployRoutes: list[dict] = [
        # Blueprint-Mods erkennt man am Mount-Point ihres Containers:
        # er zeigt auf Content/Mods/. Am Dateinamen ist das nicht zu
        # sehen -- sie liegen flach im Archiv wie jede andere Pak-Mod.
        # Im ~mods-Ordner bleiben sie wirkungslos.
        {"dest": "Content/Paks/LogicMods", "mount_contains": ["/content/mods/"]},
        # Menue-Hintergruende gehoeren in den Unterordner Menu -- dort
        # sucht der Video-Randomiser sie, durchnummeriert als menu_0,
        # menu_1 und so weiter. Direkt in Movies bleiben sie ungenutzt.
        {
            "dest": "Content/Movies/Menu",
            "names": ["menu_*.bk2", "menu_*.webm"],
            # Der Zielordner steht fest -- bringt das Archiv seinen
            # eigenen menu-Ordner mit, darf der nicht verdoppelt werden.
            "flatten": True,
        },
        # Alle uebrigen Filmsequenzen ersetzen Zwischensequenzen
        {"dest": "Content/Movies", "suffixes": [".bk2", ".webm"]},
        # UE4SS-Zubehoer behaelt seinen Unterbau
        {"dest": "Binaries/Win64", "folders": ["ue4ss"]},
        # Bringt eine CNS-Mod ihren Ordner schon mit, bleibt er erhalten
        {"dest": "Content/Paks/~mods", "folders": ["CustomNanosuitSystem"]},
        # Sonst gehoeren die Outfit- und Animationsbeschreibungen dorthin,
        # wo das Framework auch seine eigenen ablegt. Flach in ~mods
        # findet CNS sie nicht.
        {
            "dest": "Content/Paks/~mods/CustomNanosuitSystem",
            "suffixes": [".dekcns.json", ".dekani.json"],
            "flatten": True,
        },
        # Alles Uebrige: gewoehnliche Pak-Mods
        {
            "dest": "Content/Paks/~mods",
            "suffixes": [".pak", ".utoc", ".ucas"],
        },
    ]

    # Ohne diesen Eintrag laedt Proton seine eigene dwmapi.dll und UE4SS
    # wird nie gestartet -- damit bleiben Logic- und CNS-Mods wirkungslos.
    GameProtonDllOverrides: dict[str, str] = {"dwmapi": "native,builtin"}

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
        # UE4SS wird an der DLL erkannt, nicht an UE4SS-settings.ini --
        # die bringen auch Frameworks mit, die auf UE4SS aufsetzen.
        # Ohne dwmapi.dll laedt Windows den Loader nie, deshalb steht sie
        # bei detect_installed an erster Stelle.
        return [
            FrameworkMod(
                name="UE4SS",
                pattern=["UE4SS.dll"],
                target="SB/Binaries/Win64",
                description="Unreal Engine Scripting System — Lua/C++ Mod-Loader",
                detect_installed=[
                    "SB/Binaries/Win64/dwmapi.dll",
                    "SB/Binaries/Win64/ue4ss/UE4SS.dll",
                ],
                required_by=["Lua-Mods", "Blueprint-Mods"],
                nexus_id=2952,
            ),
            FrameworkMod(
                name="Custom Nanosuit System",
                pattern=["Mods/DekCNS/Scripts/main.lua"],
                target="SB",
                description="Outfit- und Kosmetik-Loader, setzt UE4SS voraus",
                detect_installed=["SB/Content/Paks/LogicMods/DekCNS_P.pak"],
                required_by=["CNS-Outfits", "CNS-Kosmetik"],
                nexus_id=1496,
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
