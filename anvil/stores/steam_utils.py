"""Steam game detection for Linux.

Finds installed Steam games by parsing libraryfolders.vdf and
appmanifest_*.acf files.  No external dependencies — uses a minimal
VDF parser built on regex.

Typical usage::

    from anvil.stores.steam_utils import find_steam_games
    games = find_steam_games()          # {1091500: Path(".../Cyberpunk 2077")}
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# ── Steam installation candidates (checked in order) ─────────────────

_STEAM_PATHS: list[Path] = [
    Path.home() / ".local" / "share" / "Steam",
    Path.home() / ".steam" / "steam",
    # Flatpak
    Path.home() / ".var" / "app" / "com.valvesoftware.Steam"
    / ".local" / "share" / "Steam",
    # Snap
    Path.home() / "snap" / "steam" / "common" / ".local" / "share" / "Steam",
]

# Regex: captures one or two quoted strings per line.
# Matches both  "key"  "value"  and  "key"  (section name) lines.
_RE_TOKENS = re.compile(r'"([^"]*)"')


# ── Minimal VDF parser ────────────────────────────────────────────────

def parse_vdf(text: str) -> dict:
    """Parse Valve Data Format text into a nested dict.

    Only handles the subset needed for libraryfolders.vdf and
    appmanifest ACF files:  quoted key/value pairs and brace-delimited
    sections.  Comments and unquoted values are ignored.

    Args:
        text: VDF/ACF file content.

    Returns:
        Nested dictionary.
    """
    root: dict = {}
    stack: list[dict] = [root]
    pending_key: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        if stripped == "{":
            # Open a section for the key we saw on the previous line.
            new_section: dict = {}
            if pending_key is not None:
                stack[-1][pending_key] = new_section
                pending_key = None
            stack.append(new_section)
            continue

        if stripped == "}":
            if len(stack) > 1:
                stack.pop()
            pending_key = None
            continue

        tokens = _RE_TOKENS.findall(stripped)
        if len(tokens) == 2:
            # "key"  "value"
            stack[-1][tokens[0]] = tokens[1]
            pending_key = None
        elif len(tokens) == 1:
            # "key" on its own line — next "{" opens its section.
            pending_key = tokens[0]

    return root


# ── Public API ────────────────────────────────────────────────────────

def find_steam_path() -> Path | None:
    """Return the first existing Steam installation path, or None.

    Checks the standard locations in order:
    ``~/.local/share/Steam``, ``~/.steam/steam``, Flatpak, Snap.
    """
    for candidate in _STEAM_PATHS:
        if candidate.is_dir():
            return candidate
    return None


def _parse_library_folders(vdf_path: Path) -> list[Path]:
    """Extract library paths from ``libraryfolders.vdf``.

    Args:
        vdf_path: Absolute path to the VDF file.

    Returns:
        List of library root directories (each containing a
        ``steamapps/`` subdirectory).
    """
    try:
        data = parse_vdf(vdf_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        print(f"steam_utils: cannot read {vdf_path}: {exc}", file=sys.stderr)
        return []

    libraries: list[Path] = []

    # Top-level key is "libraryfolders" (or "LibraryFolders" in old format).
    folders = data.get("libraryfolders") or data.get("LibraryFolders") or {}

    for key, value in folders.items():
        # Numeric keys ("0", "1", …) are library entries.
        if not key.isdigit():
            continue

        if isinstance(value, dict):
            # New format: value is a dict with a "path" key.
            path_str = value.get("path")
        elif isinstance(value, str):
            # Old format: value is the path string directly.
            path_str = value
        else:
            continue

        if path_str:
            libraries.append(Path(path_str))

    return libraries


def _parse_appmanifest(acf_path: Path) -> tuple[int, str] | None:
    """Extract appid and installdir from a single appmanifest ACF file.

    Args:
        acf_path: Path to an ``appmanifest_*.acf`` file.

    Returns:
        ``(appid, installdir)`` tuple, or None on failure.
    """
    try:
        data = parse_vdf(acf_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        print(f"steam_utils: cannot read {acf_path}: {exc}", file=sys.stderr)
        return None

    app_state = data.get("AppState") or data.get("appstate") or {}
    appid_str = app_state.get("appid") or app_state.get("appID")
    installdir = app_state.get("installdir")

    if not appid_str or not installdir:
        return None

    try:
        appid = int(appid_str)
    except ValueError:
        return None

    return appid, installdir


def find_steam_games() -> dict[int, Path]:
    """Find all installed Steam games.

    Scans every Steam library for appmanifest files and resolves
    each game's installation directory.  Only games whose directory
    actually exists on disk are included.

    Returns:
        Mapping from Steam App-ID (int) to the absolute game
        installation path.
    """
    steam_path = find_steam_path()
    if steam_path is None:
        return {}

    vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
    libraries = _parse_library_folders(vdf_path)

    # The Steam root is itself a library — add it if not already present.
    if steam_path not in libraries:
        libraries.append(steam_path)

    games: dict[int, Path] = {}

    for library in libraries:
        steamapps = library / "steamapps"
        if not steamapps.is_dir():
            continue

        for acf in steamapps.glob("appmanifest_*.acf"):
            result = _parse_appmanifest(acf)
            if result is None:
                continue

            appid, installdir = result
            game_path = steamapps / "common" / installdir

            if game_path.is_dir():
                games[appid] = game_path

    return games
