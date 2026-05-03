"""Game plugin for Windrose — Anvil Organizer.

Windrose is an Unreal Engine 5 co-op survival/pirate game (Early Access
since April 14, 2026). It uses the standard UE pak-mod system: .pak files
go into ``R5/Content/Paks/~mods/`` (the tilde is required so UE loads
them last and they override vanilla content).

Mod ecosystem:
  - PAK-Mods (most common, must match between server and clients)
  - UE4SS / Lua-Scripts (more update-resistant, optional framework)
  - WindrosePlus (server-side only framework, separate plugin)

There is no Steam Workshop and no first-party modding tool.
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame


class WindroseGame(BaseGame):
    """Windrose support plugin (client / solo)."""

    Tested = False  # Early Access — Mod-API kann sich noch ändern

    Name = "Windrose Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    GameName = "Windrose"
    GameShortName = "windrose"
    GameBinary = "Windrose.exe"  # Launcher im Spiel-Root
    GameDataPath = "R5/Content/Paks/~mods"

    GameSteamId = 3041230

    GameSaveExtension = ""  # RocksDB-Storage, kein Single-File-Save

    GameNexusId = 0  # noch nicht recherchiert — Slug genügt
    GameNexusName = "windrose"

    GameSupportURL = "https://www.nexusmods.com/windrose"

    # Save-Pfad (innerhalb Proton-Prefix):
    # %LOCALAPPDATA%/R5/Saved/SaveProfiles/<SteamID>/RocksDB/<Version>/Worlds/<WorldID>
    _WIN_SAVES = (
        "drive_c/users/steamuser/AppData/Local/R5/Saved/SaveProfiles"
    )

    # Echtes Shipping-Binary (Windrose.exe ist nur ein Launcher-Wrapper)
    _SHIPPING_BINARY = "R5/Binaries/Win64/Windrose-Win64-Shipping.exe"

    def looksValid(self, path: Path | str) -> bool:
        directory = Path(path)
        if super().looksValid(directory):
            return True
        # Akzeptiere auch Installs ohne Launcher-Wrapper
        return (directory / self._SHIPPING_BINARY).exists()

    def executables(self) -> list[dict[str, str]]:
        result: list[dict[str, str]] = [
            {"name": "Windrose", "binary": self.GameBinary},
        ]
        if self._game_path is not None:
            shipping = self._game_path / self._SHIPPING_BINARY
            if shipping.exists():
                result.append({
                    "name": "Windrose (direkt, ohne Launcher)",
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
