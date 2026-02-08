"""Lutris game detection for Linux.

Finds installed games tracked by Lutris by querying its SQLite
database (``pga.db``).  Lutris stores service metadata (GOG, Steam,
Epic/EGS) for games added through its store integration.

Typical usage::

    from anvil.stores.lutris_utils import find_lutris_games
    games = find_lutris_games()   # {("gog", "1423049311"): Path(...)}
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# ── Lutris DB candidates (checked in order) ───────────────────────────

_LUTRIS_DB_PATHS: list[Path] = [
    Path.home() / ".local" / "share" / "lutris" / "pga.db",
    # Flatpak
    Path.home() / ".var" / "app" / "net.lutris.Lutris"
    / "data" / "lutris" / "pga.db",
]

_QUERY = """
    SELECT service, service_id, name, directory
    FROM games
    WHERE installed = 1
      AND service IS NOT NULL
      AND service_id IS NOT NULL
"""


# ── Helpers ────────────────────────────────────────────────────────────

def _find_lutris_db() -> Path | None:
    """Return the first existing Lutris pga.db path, or None."""
    for candidate in _LUTRIS_DB_PATHS:
        if candidate.is_file():
            return candidate
    return None


# ── Public API ─────────────────────────────────────────────────────────

def find_lutris_games() -> dict[tuple[str, str], Path]:
    """Find all installed Lutris games that have store metadata.

    Queries the Lutris SQLite database for games with a known
    service (GOG, Steam, EGS, …) and service ID.  Only entries
    whose install directory exists on disk are included.

    Returns:
        Mapping from ``(service, service_id)`` tuple to the
        game installation path.  Example::

            {("gog", "1423049311"): Path("/path/to/game")}
    """
    db_path = _find_lutris_db()
    if db_path is None:
        return {}

    games: dict[tuple[str, str], Path] = {}

    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            for service, service_id, name, directory in con.execute(_QUERY):
                if not directory:
                    continue
                game_path = Path(directory)
                if game_path.is_dir():
                    games[(service, service_id)] = game_path
        finally:
            con.close()
    except sqlite3.Error as exc:
        print(f"lutris_utils: cannot query {db_path}: {exc}", file=sys.stderr)

    return games


# ── Convenience filters ───────────────────────────────────────────────

def find_lutris_gog_games() -> dict[int, Path]:
    """Find GOG games tracked by Lutris.

    Returns:
        Mapping from GOG product ID (int) to installation path.
    """
    result: dict[int, Path] = {}
    for (service, service_id), path in find_lutris_games().items():
        if service == "gog":
            try:
                result[int(service_id)] = path
            except (ValueError, TypeError):
                continue
    return result


def find_lutris_steam_games() -> dict[int, Path]:
    """Find Steam games tracked by Lutris.

    Returns:
        Mapping from Steam App-ID (int) to installation path.
    """
    result: dict[int, Path] = {}
    for (service, service_id), path in find_lutris_games().items():
        if service == "steam":
            try:
                result[int(service_id)] = path
            except (ValueError, TypeError):
                continue
    return result


def find_lutris_epic_games() -> dict[str, Path]:
    """Find Epic/EGS games tracked by Lutris.

    Returns:
        Mapping from Epic app name (str) to installation path.
    """
    return {
        service_id: path
        for (service, service_id), path in find_lutris_games().items()
        if service == "egs"
    }
