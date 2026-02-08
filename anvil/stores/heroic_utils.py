"""Heroic Games Launcher detection for Linux.

Finds installed GOG and Epic games managed by Heroic (or standalone
Legendary) by parsing their JSON config files.

Heroic stores:
  - GOG installs in   ``<config>/heroic/gog_store/installed.json``
  - Epic installs in  ``<config>/heroic/legendaryConfig/legendary/installed.json``

Standalone Legendary uses ``~/.config/legendary/installed.json``.

Typical usage::

    from anvil.stores.heroic_utils import find_all_heroic_games
    gog, epic = find_all_heroic_games()
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ── Heroic config candidates (checked in order) ───────────────────────

_HEROIC_PATHS: list[Path] = [
    Path.home() / ".config" / "heroic",
    # Flatpak
    Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl"
    / "config" / "heroic",
]

# Standalone Legendary (not managed by Heroic)
_LEGENDARY_PATHS: list[Path] = [
    Path.home() / ".config" / "legendary",
    # Flatpak Legendary
    Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl"
    / "config" / "legendary",
]


# ── Helpers ────────────────────────────────────────────────────────────

def _read_json(path: Path) -> dict | list | None:
    """Read and parse a JSON file, returning None on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"heroic_utils: cannot read {path}: {exc}", file=sys.stderr)
        return None


def _find_heroic_config() -> Path | None:
    """Return the first existing Heroic config directory, or None."""
    for candidate in _HEROIC_PATHS:
        if candidate.is_dir():
            return candidate
    return None


# ── GOG via Heroic ─────────────────────────────────────────────────────

def find_heroic_gog_games() -> dict[int, Path]:
    """Find GOG games installed through Heroic.

    Reads ``gog_store/installed.json`` inside the Heroic config
    directory.  Only games whose install directory actually exists
    on disk are included.  DLCs are skipped.

    Returns:
        Mapping from GOG product ID (int) to installation path.
    """
    heroic = _find_heroic_config()
    if heroic is None:
        return {}

    installed_json = heroic / "gog_store" / "installed.json"
    if not installed_json.is_file():
        return {}

    data = _read_json(installed_json)
    if not isinstance(data, dict):
        return {}

    entries = data.get("installed")
    if not isinstance(entries, list):
        return {}

    games: dict[int, Path] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        # Skip DLCs
        if entry.get("is_dlc", False):
            continue

        app_name = entry.get("appName")
        install_path = entry.get("install_path")

        if not app_name or not install_path:
            continue

        # GOG appName is the numeric product ID as string
        try:
            gog_id = int(app_name)
        except (ValueError, TypeError):
            continue

        game_path = Path(install_path)
        if game_path.is_dir():
            games[gog_id] = game_path

    return games


# ── Epic / Legendary via Heroic ────────────────────────────────────────

def _parse_legendary_installed(json_path: Path) -> dict[str, Path]:
    """Parse a Legendary-format installed.json file.

    The file is a JSON object mapping app_name strings to metadata
    dicts that contain an ``install_path`` key.

    Args:
        json_path: Path to ``installed.json``.

    Returns:
        Mapping from Epic app name (str) to installation path.
    """
    if not json_path.is_file():
        return {}

    data = _read_json(json_path)
    if not isinstance(data, dict):
        return {}

    games: dict[str, Path] = {}

    for app_name, meta in data.items():
        if not isinstance(meta, dict):
            continue

        install_path = meta.get("install_path")
        if not install_path:
            continue

        game_path = Path(install_path)
        if game_path.is_dir():
            games[app_name] = game_path

    return games


def find_heroic_epic_games() -> dict[str, Path]:
    """Find Epic games installed through Heroic.

    Reads ``legendaryConfig/legendary/installed.json`` inside the
    Heroic config directory.

    Returns:
        Mapping from Epic app name (str) to installation path.
    """
    heroic = _find_heroic_config()
    if heroic is None:
        return {}

    json_path = heroic / "legendaryConfig" / "legendary" / "installed.json"
    return _parse_legendary_installed(json_path)


# ── Standalone Legendary ───────────────────────────────────────────────

def find_legendary_games() -> dict[str, Path]:
    """Find Epic games installed through standalone Legendary.

    Reads ``~/.config/legendary/installed.json`` (or the Flatpak
    equivalent).  Same JSON format as Heroic's Legendary config.

    Returns:
        Mapping from Epic app name (str) to installation path.
    """
    for candidate in _LEGENDARY_PATHS:
        json_path = candidate / "installed.json"
        if json_path.is_file():
            return _parse_legendary_installed(json_path)

    return {}


# ── Convenience: everything at once ───────────────────────────────────

def find_all_heroic_games() -> tuple[dict[int, Path], dict[str, Path]]:
    """Find all GOG and Epic games from Heroic and standalone Legendary.

    Epic results are merged: Heroic entries take priority over
    standalone Legendary entries when the same app_name appears in both.

    Returns:
        ``(gog_games, epic_games)`` tuple.
    """
    gog_games = find_heroic_gog_games()

    # Epic: standalone Legendary first, then Heroic overwrites
    epic_games = find_legendary_games()
    epic_games.update(find_heroic_epic_games())

    return gog_games, epic_games
