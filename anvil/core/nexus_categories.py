"""Nexus category cache and mapping to Anvil categories.

Caches Nexus game categories per instance (nexus_categories.json).
Maps Nexus category names to Anvil category names via fuzzy matching.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anvil.core.categories import CategoryManager

# Nexus category name (lowercase) → Anvil category name
_NEXUS_TO_ANVIL: dict[str, str] = {
    "animations": "Animations",
    "animation": "Animations",
    "armour": "Armor & Clothing",
    "armor": "Armor & Clothing",
    "armour - shields": "Armor & Clothing",
    "clothing": "Armor & Clothing",
    "audio": "Audio",
    "sound": "Audio",
    "music": "Audio",
    "bug fixes": "Bug Fixes",
    "patches": "Patches",
    "gameplay": "Gameplay",
    "combat": "Gameplay",
    "graphics": "Graphics",
    "visuals": "Graphics",
    "visuals and graphics": "Graphics",
    "hair and face": "Hair & Face",
    "hair": "Hair & Face",
    "face": "Hair & Face",
    "items": "Items",
    "items and objects - player": "Items",
    "weapons": "Weapons",
    "weapons and armour": "Weapons",
    "miscellaneous": "Miscellaneous",
    "modders resources and tutorials": "Miscellaneous",
    "models and textures": "Models & Textures",
    "models & textures": "Models & Textures",
    "textures": "Models & Textures",
    "npc": "NPC",
    "npcs": "NPC",
    "companions": "NPC",
    "companions - creatures": "NPC",
    "creatures": "NPC",
    "overhauls": "Overhauls",
    "player homes": "Player Homes",
    "locations": "Player Homes",
    "cities, towns, villages, andடhd hamlets": "Player Homes",
    "user interface": "UI",
    "ui": "UI",
    "hud": "UI",
    "utilities": "Utilities",
    "tools": "Utilities",
    "skills and leveling": "Gameplay",
    "magic": "Gameplay",
    "crafting": "Gameplay",
    "quests and adventures": "Gameplay",
    "races, classes, and birthsigns": "Gameplay",
    "cheats and god items": "Gameplay",
    "body, face, and hair": "Hair & Face",
    "dungeons": "Gameplay",
    "environmental": "Graphics",
    "performance": "Utilities",
    "save games": "Miscellaneous",
    "character presets": "Hair & Face",
    "collectibles": "Items",
    "loot": "Items",
    "immersion": "Gameplay",
    "weather": "Graphics",
    "lighting": "Graphics",
    "shaders and effects": "Graphics",
    "vehicles": "Items",
    "maps": "UI",
    "poses": "Animations",
    "scripts": "Utilities",
    "buildings": "Player Homes",
    "config": "Utilities",
    "configuration": "Utilities",
    "frameworks": "Utilities",
    "libraries": "Utilities",
    "translation": "Miscellaneous",
    "followers": "NPC",
}


class NexusCategoryCache:
    """Cached Nexus categories per instance (nexus_categories.json)."""

    FILENAME = "nexus_categories.json"
    MAX_AGE_DAYS = 30

    def __init__(self, instance_path: Path):
        self._path = instance_path / self.FILENAME
        self._categories: list[dict] = []
        self._game_slug: str = ""
        self._timestamp: float = 0

    def load(self) -> bool:
        """Load cache from disk. Returns True if valid cache exists."""
        if not self._path.exists():
            return False
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._categories = raw.get("categories", [])
            self._game_slug = raw.get("game_slug", "")
            self._timestamp = raw.get("timestamp", 0)
            return bool(self._categories)
        except (json.JSONDecodeError, OSError):
            return False

    def save(self, game_slug: str, categories: list[dict]) -> None:
        """Save categories to disk."""
        self._categories = categories
        self._game_slug = game_slug
        self._timestamp = time.time()
        data = {
            "game_slug": game_slug,
            "timestamp": self._timestamp,
            "categories": categories,
        }
        try:
            self._path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    def is_expired(self) -> bool:
        """Return True if cache is older than MAX_AGE_DAYS."""
        if not self._timestamp:
            return True
        age_days = (time.time() - self._timestamp) / 86400
        return age_days > self.MAX_AGE_DAYS

    def get_categories(self) -> list[dict]:
        return self._categories

    def find_nexus_category(self, nexus_cat_id: int) -> str:
        """Return the name of a Nexus category by its ID, or ''."""
        for cat in self._categories:
            if cat.get("category_id") == nexus_cat_id:
                return cat.get("name", "")
        return ""


def map_nexus_to_anvil(nexus_name: str) -> str | None:
    """Map a Nexus category name to an Anvil category name.

    Returns None if no mapping found.
    """
    return _NEXUS_TO_ANVIL.get(nexus_name.lower().strip())


def assign_nexus_categories(
    mod_path: Path,
    nexus_cat_id: int,
    nexus_cache: NexusCategoryCache,
    category_manager: CategoryManager,
) -> list[int]:
    """Assign Anvil category based on Nexus category ID.

    MERGES with existing categories — never overwrites.
    Returns list of newly added category IDs.
    """
    from anvil.core.mod_metadata import read_meta_ini, write_meta_ini

    nexus_name = nexus_cache.find_nexus_category(nexus_cat_id)
    if not nexus_name:
        return []

    # Map Nexus name → Anvil name
    anvil_name = map_nexus_to_anvil(nexus_name)
    if not anvil_name:
        # Create new Anvil category with Nexus name
        anvil_name = nexus_name

    # Find or create Anvil category
    anvil_id = category_manager.get_id(anvil_name)
    if anvil_id == 0:
        anvil_id = category_manager.add_category(anvil_name)
    if anvil_id == 0:
        return []

    # Read existing categories from meta.ini
    meta = read_meta_ini(mod_path)
    raw_cat = meta.get("category", "")
    existing_ids: list[int] = []
    if raw_cat:
        for part in raw_cat.split(","):
            part = part.strip()
            if part:
                try:
                    cid = int(part)
                    if cid > 0:
                        existing_ids.append(cid)
                except ValueError:
                    pass

    # MERGE: only add if not already present
    if anvil_id in existing_ids:
        return []

    existing_ids.append(anvil_id)
    new_cat_str = ",".join(str(c) for c in existing_ids)
    write_meta_ini(mod_path, {"category": new_cat_str})
    return [anvil_id]
