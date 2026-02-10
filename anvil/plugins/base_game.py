"""Base class for Anvil Organizer game plugins.

Every game plugin inherits from BaseGame and sets class-level attributes
to describe the game. The store-detection logic in detectGame() works
automatically as long as the plugin provides at least one store ID.

Inspired by MO2's BasicGame but adapted for Linux (no Windows registry,
Proton prefix support, .exe-agnostic binary lookup).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _as_list(value: Any) -> list:
    """Normalize a scalar or list value into a list.

    Falsy scalars (0, "", None) become an empty list.
    """
    if isinstance(value, list):
        return value
    if value:
        return [value]
    return []


class BaseGame:
    """Base class that every game plugin must inherit from.

    Subclasses override class-level attributes to describe a game.
    The default method implementations should work for most games;
    override individual methods for game-specific behaviour.
    """

    # ── Pflicht-Attribute (Subklasse MUSS diese setzen) ──────────────

    Name: str = ""
    """Plugin display name, e.g. 'Cyberpunk 2077 Support Plugin'."""

    Author: str = ""
    """Plugin author."""

    Version: str = ""
    """Plugin version string."""

    GameName: str = ""
    """Human-readable game name, e.g. 'Cyberpunk 2077'."""

    GameShortName: str = ""
    """Unique short identifier, e.g. 'cyberpunk2077'."""

    GameBinary: str = ""
    """Main executable relative to the game directory, e.g. 'bin/x64/Cyberpunk2077.exe'."""

    GameDataPath: str = ""
    """Directory for mods relative to the game directory.  Empty string means game root."""

    # ── Optional-Attribute ────────────────────────────────────────────

    GameSteamId: int | list[int] = 0
    """One or more Steam App-IDs.  Use a list for games with multiple editions."""

    GameGogId: int | list[int] = 0
    """One or more GOG product IDs."""

    GameEpicId: str | list[str] = ""
    """One or more Epic/Legendary app name identifiers."""

    GameLauncher: str = ""
    """Alternative launcher binary relative to the game directory."""

    GameDocumentsDirectory: str = ""
    """Path to the game's documents folder.  Supports ~ for home."""

    GameSavesDirectory: str = ""
    """Path to the save-game folder.  Falls back to GameDocumentsDirectory."""

    GameSaveExtension: str = "save"
    """File extension for save-game files (without dot)."""

    GameNexusId: int = 0
    """Nexus Mods game ID."""

    GameNexusName: str = ""
    """Nexus Mods URL slug.  Falls back to GameShortName."""

    GameSupportURL: str = ""
    """Wiki or support URL for modding instructions."""

    GameLaunchArgs: list[str] = []
    """Extra arguments passed to the game binary on launch (e.g. ['--launcher-skip'])."""

    # ── Interner State ────────────────────────────────────────────────

    def __init__(self) -> None:
        self._game_path: Path | None = None
        self._detected_store: str | None = None

    # ── Store-Erkennung ───────────────────────────────────────────────

    def detectGame(
        self,
        steam_games: dict[str, Path],
        gog_games: dict[str, Path],
        epic_games: dict[str, Path],
    ) -> bool:
        """Try to find this game in the provided store dictionaries.

        Each dictionary maps a store ID (as string) to an install path.
        Iterates Steam -> GOG -> Epic and stops at the first match.
        Sets ``_game_path`` and ``_detected_store`` on success.

        Returns:
            True if the game was found in any store.
        """
        for steam_id in _as_list(self.GameSteamId):
            key = str(steam_id)
            if key in steam_games:
                self.setGamePath(steam_games[key], store="steam")
                return True

        for gog_id in _as_list(self.GameGogId):
            key = str(gog_id)
            if key in gog_games:
                self.setGamePath(gog_games[key], store="gog")
                return True

        for epic_id in _as_list(self.GameEpicId):
            key = str(epic_id)
            if key in epic_games:
                self.setGamePath(epic_games[key], store="epic")
                return True

        return False

    def setGamePath(self, path: Path | str, store: str | None = None) -> None:
        """Manually set the game installation path.

        Args:
            path:  Absolute path to the game directory.
            store: Which store this path came from ('steam', 'gog', 'epic')
                   or None for manual selection.
        """
        self._game_path = Path(path)
        self._detected_store = store

    def looksValid(self, path: Path | str) -> bool:
        """Check whether *path* looks like a valid installation of this game.

        Tests for the presence of ``GameBinary``.  On Linux the binary may
        or may not have a .exe extension (native vs. Proton), so both
        variants are checked.

        Args:
            path: Directory to validate.

        Returns:
            True if the game binary was found.
        """
        directory = Path(path)
        binary = Path(self.GameBinary)

        if (directory / binary).exists():
            return True

        # Try without .exe suffix (native Linux build)
        if binary.suffix.lower() == ".exe":
            if (directory / binary.with_suffix("")).exists():
                return True

        return False

    # ── Getter ────────────────────────────────────────────────────────

    def gameDirectory(self) -> Path | None:
        """Return the game installation path, or None if not detected."""
        return self._game_path

    def isInstalled(self) -> bool:
        """Return True if the game has been detected and the path is set."""
        return self._game_path is not None

    def detectedStore(self) -> str | None:
        """Return which store the game was found in ('steam', 'gog', 'epic', or None)."""
        return self._detected_store

    def protonPrefix(self) -> Path | None:
        """Return the Proton/Wine compatibility-data prefix for Steam games.

        Path pattern: ``~/.local/share/Steam/steamapps/compatdata/{appid}/pfx/``

        Only returns a path for Steam games where a compatdata folder exists.
        Returns None for non-Steam games or when no prefix is found.
        """
        if self._detected_store != "steam":
            return None

        steam_root = Path.home() / ".local" / "share" / "Steam"
        for steam_id in _as_list(self.GameSteamId):
            prefix = steam_root / "steamapps" / "compatdata" / str(steam_id) / "pfx"
            if prefix.is_dir():
                return prefix

        return None

    def icon(self) -> str | None:
        """Return path to a game icon, or None.

        Subclasses can override this to provide a custom icon.
        """
        return None

    # ── Override-Punkte (Subklassen können diese überschreiben) ───────

    def executables(self) -> list[dict[str, str]]:
        """Return a list of executable definitions for this game.

        Each entry is a dict with:
          - ``name``:   Display name
          - ``binary``: Path relative to the game directory

        The default implementation returns the main binary and,
        if set, the launcher.
        """
        result: list[dict[str, str]] = [
            {"name": self.GameName, "binary": self.GameBinary},
        ]
        if self.GameLauncher:
            result.append({"name": f"{self.GameName} Launcher", "binary": self.GameLauncher})
        return result

    def iniFiles(self) -> list[str]:
        """Return a list of INI/config filenames managed by this game.

        Default: empty list.
        """
        return []

    def listSaves(self, folder: Path) -> list[Path]:
        """Find save-game files inside *folder*.

        Default: globs for ``*.{GameSaveExtension}``.

        Args:
            folder: Directory to search for saves.

        Returns:
            Sorted list of save-game file paths.
        """
        if not folder.is_dir():
            return []
        ext = self.GameSaveExtension
        return sorted(folder.glob(f"*.{ext}"), key=lambda p: p.stat().st_mtime, reverse=True)

    # ── Repr ──────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        installed = self._game_path or "not found"
        return f"<{self.__class__.__name__} '{self.GameName}' [{installed}]>"
