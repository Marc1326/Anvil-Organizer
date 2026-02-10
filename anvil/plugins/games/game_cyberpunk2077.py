"""Cyberpunk 2077 game plugin for Anvil Organizer.

Based on the MO2 basic_games plugin by 6788 and Zash, adapted for
Linux with Proton prefix support.

Features implemented:
  - Store detection (Steam, GOG, Epic)
  - Proton prefix paths for documents and saves
  - Executable list (game, REDmod, launcher)
  - INI file list

TODO (future):
  - REDmod deployment (redMod.exe deploy)
  - Archive load order management
  - CrashReporter handling (dummy mod)
  - Cache file mapping after game updates
  - Forced DLL loads (version.dll, winmm.dll)
  - Save game metadata parsing (playtime, level, character)
  - Mod data validation (CyberpunkModDataChecker)
  - RootBuilder conversion dialog
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame


class Cyberpunk2077Game(BaseGame):
    """Cyberpunk 2077 support plugin."""

    # ── Plugin-Metadaten ───────────────────────────────────────────────

    Name = "Cyberpunk 2077 Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # ── Spiel-Attribute ────────────────────────────────────────────────

    GameName = "Cyberpunk 2077"
    GameShortName = "cyberpunk2077"
    GameBinary = "bin/x64/Cyberpunk2077.exe"
    GameDataPath = ""  # Mods go into the game root directory

    GameSteamId = 1091500
    GameGogId = 1423049311
    GameEpicId = "77f2b98e2cef40c8a7437518bf420e47"

    GameLauncher = "REDprelauncher.exe"
    GameLaunchArgs = ["--launcher-skip"]

    GameDirectInstallMods = [
        "TweakXL",
        "ArchiveXL",
        "CET",
        "Cyber Engine Tweaks",
        "CET 1.37.1 - Scripting fixes",
        "Codeware",
        "RED4ext",
        "RedData",
        "RedFileSystem",
        "redscript",
        "Native Settings UI",
        "mod_settings",
    ]

    GameDocumentsDirectory = ""  # resolved dynamically via gameDocumentsDirectory()
    GameSavesDirectory = ""     # resolved dynamically via gameSavesDirectory()
    GameSaveExtension = "dat"

    GameNexusId = 3333
    GameNexusName = "cyberpunk2077"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Cyberpunk-2077"
    )

    # ── Windows-Pfade (innerhalb Proton-Prefix) ────────────────────────

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/AppData/Local"
        "/CD Projekt Red/Cyberpunk 2077"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/Saved Games"
        "/CD Projekt Red/Cyberpunk 2077"
    )

    # ── REDmod (Pfade für spätere Implementierung) ─────────────────────

    # TODO: REDmod deployment
    _REDMOD_BINARY = "tools/redmod/bin/redMod.exe"

    # ── Überschriebene Methoden ────────────────────────────────────────

    def gameDocumentsDirectory(self) -> Path | None:
        """Return the game's documents directory.

        For Steam (Proton): derived from the Proton prefix.
        For GOG/Epic: may be in a Wine prefix managed by Heroic/Lutris.
        Returns None if no prefix is found.
        """
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_DOCUMENTS
            if path.is_dir():
                return path
        # Fallback: check game directory itself (native Linux, unlikely)
        if self._game_path is not None:
            path = self._game_path / "AppData" / "Local" / "CD Projekt Red" / "Cyberpunk 2077"
            if path.is_dir():
                return path
        return None

    def gameSavesDirectory(self) -> Path | None:
        """Return the save game directory.

        For Steam (Proton): derived from the Proton prefix.
        Returns None if no prefix is found.
        """
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_SAVES
            if path.is_dir():
                return path
        return None

    def executables(self) -> list[dict[str, str]]:
        """Return executable definitions for Cyberpunk 2077.

        Includes the main game binary, the REDprelauncher, and
        REDmod if the tools directory exists.
        """
        result: list[dict[str, str]] = [
            {"name": "Cyberpunk 2077", "binary": self.GameBinary},
            {"name": "REDprelauncher", "binary": self.GameLauncher},
        ]

        # Add REDmod if available
        if self._game_path is not None:
            redmod = self._game_path / self._REDMOD_BINARY
            if redmod.exists():
                result.append({"name": "REDmod", "binary": self._REDMOD_BINARY})

        return result

    def iniFiles(self) -> list[str]:
        """Return config files managed by Cyberpunk 2077."""
        return ["UserSettings.json"]
