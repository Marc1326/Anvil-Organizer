"""plugins.txt generator for Bethesda Creation Engine games.

Scans the game's Data/ directory for .esp/.esm/.esl plugin files and
writes a plugins.txt in the correct Proton prefix location.

Format: UTF-8, \\r\\n line endings, *-prefix for active plugins.
"""

from __future__ import annotations

import os
from pathlib import Path

_TAG = "[PluginsTxtWriter]"

_PLUGIN_EXTENSIONS = {".esp", ".esm", ".esl"}

_HEADER = (
    "# This file is used by the game to keep track of your downloaded content.\r\n"
    "# Please do not modify this file.\r\n"
)


class PluginsTxtWriter:
    """Scan, write and remove plugins.txt for Bethesda games."""

    def __init__(
        self,
        game_plugin,
        game_path: Path,
        instance_path: Path,
    ) -> None:
        self._game_plugin = game_plugin
        self._game_path = game_path
        self._instance_path = instance_path
        self._primary: list[str] = getattr(game_plugin, "PRIMARY_PLUGINS", [])

    # ── Public API ────────────────────────────────────────────────────

    def scan_plugins(self) -> list[str]:
        """Scan game_path/Data/ for plugin files.

        Returns a sorted list: primary plugins first (only if present
        on disk), then masters (.esm), then normal plugins (.esp/.esl).
        """
        data_dir = self._game_path / getattr(
            self._game_plugin, "GameDataPath", "Data"
        )
        if not data_dir.is_dir():
            return []

        # Collect all plugin files directly in Data/ (not subdirs)
        found: set[str] = set()
        try:
            for entry in os.scandir(data_dir):
                if not entry.is_file():
                    continue
                ext = Path(entry.name).suffix.lower()
                if ext in _PLUGIN_EXTENSIONS:
                    found.add(entry.name)
        except OSError as exc:
            print(f"{_TAG} Error scanning {data_dir}: {exc}")
            return []

        # Build primary list (only plugins that actually exist on disk)
        primary_lower = {p.lower() for p in self._primary}
        found_lower_map = {f.lower(): f for f in found}

        result: list[str] = []
        for p in self._primary:
            if p.lower() in found_lower_map:
                result.append(found_lower_map[p.lower()])

        # Remaining plugins (not primary)
        remaining = [f for f in found if f.lower() not in primary_lower]

        # Sort remaining: .esm first, then .esp/.esl
        masters = sorted(
            [f for f in remaining if f.lower().endswith(".esm")],
            key=str.lower,
        )
        others = sorted(
            [f for f in remaining if not f.lower().endswith(".esm")],
            key=str.lower,
        )

        result.extend(masters)
        result.extend(others)
        return result

    def write(self) -> Path | None:
        """Write plugins.txt to the Proton prefix.

        All plugins are marked active (*) in Phase 1.
        Returns the written path, or None on failure.
        """
        txt_path = self._game_plugin.plugins_txt_path()
        if txt_path is None:
            print(f"{_TAG} No plugins_txt_path — skipping write")
            return None

        plugins = self.scan_plugins()
        if not plugins:
            print(f"{_TAG} No plugins found — skipping write")
            return None

        # Ensure parent directory exists
        os.makedirs(txt_path.parent, exist_ok=True)

        # Build content
        lines = [_HEADER]
        for plugin in plugins:
            # Phase 1: all plugins active
            lines.append(f"*{plugin}\r\n")

        try:
            txt_path.write_text("".join(lines), encoding="utf-8")
            print(f"{_TAG} Wrote {len(plugins)} plugins to {txt_path}")
            return txt_path
        except OSError as exc:
            print(f"{_TAG} Error writing {txt_path}: {exc}")
            return None

    def remove(self) -> bool:
        """Delete plugins.txt.  Returns True if removed or already absent."""
        txt_path = self._game_plugin.plugins_txt_path()
        if txt_path is None:
            return True
        try:
            if txt_path.exists():
                txt_path.unlink()
                print(f"{_TAG} Removed {txt_path}")
            return True
        except OSError as exc:
            print(f"{_TAG} Error removing {txt_path}: {exc}")
            return False
