"""Game plugin for Windrose Dedicated Server — Anvil Organizer.

Separate Steam-App (4129620, kostenlos via SteamCMD anonymous) für den
dedizierten Server. Eigene Binary, eigene Mod-Verwaltung, eigene Saves
(im Server-Root, nicht im Proton-Prefix).

Mods müssen laut Community-Doku auf Server UND allen Clients identisch
installiert sein, sonst kommt es zu Desyncs. Anvil verwaltet beide
Instanzen getrennt — die Sync-Verantwortung liegt beim Nutzer.

Server-Layout-Varianten (je nach Quelle der Installation):
  - SteamCMD-Build: Mods nach R5/Content/Paks/~mods/
  - EGS/Stove-Build: Mods nach R5/Builds/WindowsServer/R5/Content/Paks/~mods/

Dieses Plugin nutzt die SteamCMD-Variante als Default. Für den
EGS-Layout-Fall kann eine zweite Anvil-Instanz mit angepasstem
GameDataPath angelegt werden.
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame


class WindroseServerGame(BaseGame):
    """Windrose Dedicated Server support plugin."""

    Tested = False  # Early Access

    Name = "Windrose Dedicated Server Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    GameName = "Windrose (Dedicated Server)"
    GameShortName = "windroseserver"
    GameBinary = "WindroseServer.exe"
    GameDataPath = "R5/Content/Paks/~mods"

    GameSteamId = 4129620  # Free dedicated server tool

    GameSaveExtension = ""

    GameNexusId = 0  # noch nicht recherchiert
    GameNexusName = "windrose"  # Server nutzt dieselbe Nexus-Page

    GameSupportURL = "https://playwindrose.com/dedicated-server-guide/"

    _SHIPPING_BINARY = "R5/Binaries/Win64/WindroseServer-Win64-Shipping.exe"
    _SERVER_DESCRIPTION = "ServerDescription.json"
    _START_SCRIPT = "StartServerForeground.bat"

    def looksValid(self, path: Path | str) -> bool:
        directory = Path(path)
        # Drei Indikatoren — Server-Installs sind layout-variabel
        candidates = [
            self.GameBinary,
            self._SHIPPING_BINARY,
            self._SERVER_DESCRIPTION,
        ]
        return any((directory / c).exists() for c in candidates)

    def gameSavesDirectory(self) -> Path | None:
        """Server-Saves liegen im Installations-Verzeichnis, nicht im Prefix."""
        if self._game_path is None:
            return None
        path = self._game_path / "R5" / "Saved" / "SaveProfiles"
        if path.is_dir():
            return path
        return None

    def executables(self) -> list[dict[str, str]]:
        result: list[dict[str, str]] = [
            {"name": "Windrose Server", "binary": self.GameBinary},
        ]
        if self._game_path is not None:
            start_bat = self._game_path / self._START_SCRIPT
            if start_bat.exists():
                result.insert(0, {
                    "name": "Server starten (mit Konsolenfenster)",
                    "binary": self._START_SCRIPT,
                })
            shipping = self._game_path / self._SHIPPING_BINARY
            if shipping.exists():
                result.append({
                    "name": "Server (direkt, ohne Wrapper)",
                    "binary": self._SHIPPING_BINARY,
                })
        return result

    def get_default_categories(self) -> list[dict] | None:
        return [
            {"id": 1, "name": "Gameplay"},
            {"id": 2, "name": "Quality of Life"},
            {"id": 3, "name": "Graphics & Visuals"},
            {"id": 4, "name": "UI & HUD"},
            {"id": 5, "name": "Schiffe"},
            {"id": 6, "name": "Waffen & Ausrüstung"},
            {"id": 7, "name": "Charaktere & Outfits"},
            {"id": 8, "name": "Karte & Welt"},
            {"id": 9, "name": "Crafting & Wirtschaft"},
            {"id": 10, "name": "Audio"},
            {"id": 11, "name": "UE4SS / Lua"},
            {"id": 12, "name": "Frameworks"},
            {"id": 13, "name": "Bug Fixes"},
            {"id": 14, "name": "Patches"},
            {"id": 15, "name": "Utilities"},
            {"id": 16, "name": "Server Admin"},
            {"id": 17, "name": "RCON & Tools"},
            {"id": 18, "name": "WindrosePlus"},
        ]

    def get_conflict_ignores(self) -> list[str]:
        return [
            "**/readme*",
            "**/README*",
            "**/docs/**",
            "**/*.txt",
            "**/LICENSE*",
            "**/changelog*",
        ]
