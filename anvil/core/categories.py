"""Category management for Anvil Organizer.

Each instance has its own categories.json.  Categories are flat (no hierarchy)
and referenced by integer ID.  Mods store their category IDs as a
comma-separated list in meta.ini (primary category first).

Default categories based on common Nexus Mods taxonomy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from anvil.core.translator import tr


# Default categories (sorted alphabetically).
_DEFAULT_CATEGORIES: list[dict[str, Any]] = [
    {"id": 1,  "name": "Animations"},
    {"id": 2,  "name": "Armor & Clothing"},
    {"id": 3,  "name": "Audio"},
    {"id": 4,  "name": "Bug Fixes"},
    {"id": 5,  "name": "Gameplay"},
    {"id": 6,  "name": "Graphics"},
    {"id": 7,  "name": "Hair & Face"},
    {"id": 8,  "name": "Items"},
    {"id": 9,  "name": "Miscellaneous"},
    {"id": 10, "name": "Models & Textures"},
    {"id": 11, "name": "NPC"},
    {"id": 12, "name": "Overhauls"},
    {"id": 13, "name": "Patches"},
    {"id": 14, "name": "Player Homes"},
    {"id": 15, "name": "UI"},
    {"id": 16, "name": "Utilities"},
    {"id": 17, "name": "Weapons"},
]

# Mapping from internal name to translation key
_CATEGORY_KEYS: dict[str, str] = {
    "Animations": "category.animations",
    "Armor & Clothing": "category.armor_clothing",
    "Audio": "category.audio",
    "Bug Fixes": "category.bug_fixes",
    "Gameplay": "category.gameplay",
    "Graphics": "category.graphics",
    "Hair & Face": "category.hair_face",
    "Items": "category.items",
    "Miscellaneous": "category.miscellaneous",
    "Models & Textures": "category.models_textures",
    "NPC": "category.npc",
    "Overhauls": "category.overhauls",
    "Patches": "category.patches",
    "Player Homes": "category.player_homes",
    "UI": "category.ui",
    "Utilities": "category.utilities",
    "Weapons": "category.weapons",
}


def get_display_name(name: str, lang: str = "de") -> str:
    """Get localized display name for a category.

    Args:
        name: Internal category name (English).
        lang: Language code (ignored, tr() uses current app language).

    Returns:
        Translated name if available, otherwise original name.
    """
    key = _CATEGORY_KEYS.get(name)
    if key:
        translated = tr(key)
        # tr() returns the key if not found - fall back to original name
        if translated != key:
            return translated
    return name


class CategoryManager:
    """Manages categories for a single instance.

    Categories are stored as ``categories.json`` inside the instance
    directory.  The file is created with defaults the first time it's
    loaded for an instance that doesn't have one yet.
    """

    FILENAME = "categories.json"

    def __init__(self) -> None:
        self._categories: list[dict[str, Any]] = []
        self._path: Path | None = None

    # ── Load / Save ────────────────────────────────────────────────

    def load(self, instance_path: Path) -> None:
        """Load categories from *instance_path*/categories.json.

        Creates the file with defaults if it doesn't exist yet.
        """
        self._path = instance_path / self.FILENAME

        if self._path.is_file():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._categories = data
                    return
            except (json.JSONDecodeError, OSError):
                pass

        # First load or corrupt file — initialise with defaults
        self._categories = [dict(c) for c in _DEFAULT_CATEGORIES]
        self.save()

    def save(self) -> None:
        """Persist categories to disk."""
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._categories, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    # ── Query ──────────────────────────────────────────────────────

    def all_categories(self) -> list[dict[str, Any]]:
        """Return all categories sorted by name."""
        return sorted(self._categories, key=lambda c: c["name"].lower())

    def get_name(self, cat_id: int) -> str:
        """Return the name for *cat_id*, or '' if not found."""
        for c in self._categories:
            if c["id"] == cat_id:
                return c["name"]
        return ""

    def get_id(self, name: str) -> int:
        """Return the ID for a category *name*, or 0 if not found."""
        lower = name.lower()
        for c in self._categories:
            if c["name"].lower() == lower:
                return c["id"]
        return 0

    def exists(self, cat_id: int) -> bool:
        """Return True if a category with *cat_id* exists."""
        return any(c["id"] == cat_id for c in self._categories)

    # ── Mutate ─────────────────────────────────────────────────────

    def _next_id(self) -> int:
        """Return the next available category ID."""
        if not self._categories:
            return 1
        return max(c["id"] for c in self._categories) + 1

    def add_category(self, name: str) -> int:
        """Add a new category and return its ID.

        Returns 0 if a category with that name already exists.
        """
        if self.get_id(name) != 0:
            return 0
        new_id = self._next_id()
        self._categories.append({"id": new_id, "name": name})
        self.save()
        return new_id

    def rename_category(self, cat_id: int, new_name: str) -> bool:
        """Rename a category.  Returns False if *cat_id* not found."""
        for c in self._categories:
            if c["id"] == cat_id:
                c["name"] = new_name
                self.save()
                return True
        return False

    def remove_category(self, cat_id: int) -> bool:
        """Remove a category.  Returns False if *cat_id* not found."""
        before = len(self._categories)
        self._categories = [c for c in self._categories if c["id"] != cat_id]
        if len(self._categories) < before:
            self.save()
            return True
        return False
