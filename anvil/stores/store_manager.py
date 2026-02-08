"""Unified store manager for Anvil Organizer.

Scans all supported Linux game stores and merges the results into
a single, deduplicated view.  Each store utility is called
independently — if one fails, the others still work.

Merge priority (highest wins): Steam > Heroic > Legendary > Lutris.

Typical usage::

    from anvil.stores.store_manager import StoreManager
    sm = StoreManager()
    sm.scan_all_stores()
    print(sm.steam_games)
"""

from __future__ import annotations

import sys
from pathlib import Path

from anvil.stores.steam_utils import find_steam_games
from anvil.stores.heroic_utils import (
    find_heroic_gog_games,
    find_heroic_epic_games,
    find_legendary_games,
)
from anvil.stores.lutris_utils import (
    find_lutris_gog_games,
    find_lutris_steam_games,
    find_lutris_epic_games,
)
from anvil.stores.bottles_utils import find_bottles


class StoreManager:
    """Central manager that aggregates game data from all Linux stores.

    Call :meth:`scan_all_stores` once to populate the internal caches,
    then use the property getters to access the results.
    """

    def __init__(self) -> None:
        self._steam_games: dict[int, Path] = {}
        self._gog_games: dict[int, Path] = {}
        self._epic_games: dict[str, Path] = {}
        self._bottles: list[dict] = []
        self._scanned: bool = False

    # ── Scan ───────────────────────────────────────────────────────────

    def scan_all_stores(self) -> None:
        """Scan all supported stores and cache the results.

        Each store is scanned independently.  If one store fails,
        the error is logged to stderr and the remaining stores are
        still scanned.

        Merge priority (highest overwrites lowest):
          - **Steam**: direct detection via VDF/ACF
          - **GOG**: Heroic > Lutris
          - **Epic**: Heroic > Legendary > Lutris
          - **Bottles**: no merging (list of Wine prefixes)
        """
        # ── Steam ──────────────────────────────────────────────────
        try:
            self._steam_games = find_steam_games()
        except Exception as exc:
            print(f"StoreManager: Steam scan failed: {exc}", file=sys.stderr)
            self._steam_games = {}

        # ── GOG: Lutris first, then Heroic overwrites ─────────────
        try:
            gog = find_lutris_gog_games()
        except Exception as exc:
            print(f"StoreManager: Lutris GOG scan failed: {exc}", file=sys.stderr)
            gog = {}

        try:
            gog.update(find_heroic_gog_games())
        except Exception as exc:
            print(f"StoreManager: Heroic GOG scan failed: {exc}", file=sys.stderr)

        self._gog_games = gog

        # ── Epic: Lutris → Legendary → Heroic (ascending prio) ────
        try:
            epic = find_lutris_epic_games()
        except Exception as exc:
            print(f"StoreManager: Lutris Epic scan failed: {exc}", file=sys.stderr)
            epic = {}

        try:
            epic.update(find_legendary_games())
        except Exception as exc:
            print(f"StoreManager: Legendary scan failed: {exc}", file=sys.stderr)

        try:
            epic.update(find_heroic_epic_games())
        except Exception as exc:
            print(f"StoreManager: Heroic Epic scan failed: {exc}", file=sys.stderr)

        self._epic_games = epic

        # ── Bottles ────────────────────────────────────────────────
        try:
            self._bottles = find_bottles()
        except Exception as exc:
            print(f"StoreManager: Bottles scan failed: {exc}", file=sys.stderr)
            self._bottles = []

        self._scanned = True

    # ── Getters ────────────────────────────────────────────────────────

    @property
    def steam_games(self) -> dict[int, Path]:
        """Steam games: ``{app_id: install_path}``."""
        return self._steam_games

    @property
    def gog_games(self) -> dict[int, Path]:
        """GOG games (merged Heroic + Lutris): ``{product_id: install_path}``."""
        return self._gog_games

    @property
    def epic_games(self) -> dict[str, Path]:
        """Epic games (merged Heroic + Legendary + Lutris): ``{app_name: install_path}``."""
        return self._epic_games

    @property
    def bottles(self) -> list[dict]:
        """Bottles (Wine prefixes): list of dicts with name, path, environment, runner."""
        return self._bottles

    def all_found_games(self) -> dict:
        """Return a summary dict for debugging and display.

        Returns:
            Dict with keys ``steam``, ``gog``, ``epic``, ``bottles``,
            each containing their respective data, plus a ``counts``
            key with the number of entries per store.
        """
        return {
            "steam": self._steam_games,
            "gog": self._gog_games,
            "epic": self._epic_games,
            "bottles": self._bottles,
            "counts": {
                "steam": len(self._steam_games),
                "gog": len(self._gog_games),
                "epic": len(self._epic_games),
                "bottles": len(self._bottles),
            },
        }

    # ── Repr ───────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        if not self._scanned:
            return "<StoreManager (not scanned)>"
        c = self.all_found_games()["counts"]
        return (
            f"<StoreManager steam={c['steam']} gog={c['gog']} "
            f"epic={c['epic']} bottles={c['bottles']}>"
        )
