"""Collection/Modpack export and import for Anvil Organizer.

A *collection* is a ``.anvilpack`` file (a ZIP archive) that stores
mod-list metadata so users can share their setups.  The archive does
**not** contain mod files — only a ``manifest.json`` describing the
load order, Nexus IDs, separator structure, categories, etc.

Optionally a ``categories.json`` is embedded so custom category names
are preserved across imports.

File layout inside the archive::

    manifest.json
    categories.json   (optional)
"""

from __future__ import annotations

import json
import sys
import zipfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from anvil.core.mod_list_io import (
    read_active_mods,
    read_global_modlist,
    write_active_mods,
    write_global_modlist,
)
from anvil.core.mod_metadata import read_meta_ini, write_meta_ini
from anvil.version import APP_VERSION


# ── Manifest dataclass ──────────────────────────────────────────────

FORMAT_VERSION = 1


@dataclass
class CollectionMod:
    """Metadata for a single mod inside a collection."""

    name: str
    display_name: str = ""
    enabled: bool = True
    is_separator: bool = False
    nexus_id: int = 0
    version: str = ""
    author: str = ""
    url: str = ""
    category_ids: list[int] = field(default_factory=list)
    color: str = ""


@dataclass
class CollectionManifest:
    """Top-level manifest describing the collection."""

    anvil_version: str = APP_VERSION
    format_version: int = FORMAT_VERSION

    # Game info
    game_name: str = ""
    game_short_name: str = ""
    game_nexus_name: str = ""

    # Collection info
    collection_name: str = ""
    collection_description: str = ""
    collection_author: str = ""
    collection_created: str = ""

    # Mod list (in load-order, first = highest priority)
    mods: list[CollectionMod] = field(default_factory=list)


# ── Serialization helpers ───────────────────────────────────────────

def _manifest_to_dict(m: CollectionManifest) -> dict[str, Any]:
    """Convert a manifest to a JSON-serializable dict."""
    return {
        "anvil_version": m.anvil_version,
        "format_version": m.format_version,
        "game": {
            "name": m.game_name,
            "short_name": m.game_short_name,
            "nexus_name": m.game_nexus_name,
        },
        "collection": {
            "name": m.collection_name,
            "description": m.collection_description,
            "author": m.collection_author,
            "created": m.collection_created,
        },
        "mods": [asdict(mod) for mod in m.mods],
    }


def _dict_to_manifest(data: dict[str, Any]) -> CollectionManifest:
    """Parse a dict (from JSON) into a CollectionManifest."""
    game = data.get("game", {})
    coll = data.get("collection", {})
    mods_raw = data.get("mods", [])

    mods: list[CollectionMod] = []
    for md in mods_raw:
        mods.append(CollectionMod(
            name=md.get("name", ""),
            display_name=md.get("display_name", ""),
            enabled=md.get("enabled", True),
            is_separator=md.get("is_separator", False),
            nexus_id=md.get("nexus_id", 0),
            version=md.get("version", ""),
            author=md.get("author", ""),
            url=md.get("url", ""),
            category_ids=md.get("category_ids", []),
            color=md.get("color", ""),
        ))

    return CollectionManifest(
        anvil_version=data.get("anvil_version", ""),
        format_version=data.get("format_version", 1),
        game_name=game.get("name", ""),
        game_short_name=game.get("short_name", ""),
        game_nexus_name=game.get("nexus_name", ""),
        collection_name=coll.get("name", ""),
        collection_description=coll.get("description", ""),
        collection_author=coll.get("author", ""),
        collection_created=coll.get("created", ""),
        mods=mods,
    )


# ── Export ──────────────────────────────────────────────────────────

def build_manifest(
    instance_path: Path,
    profile_path: Path,
    game_name: str,
    game_short_name: str,
    game_nexus_name: str,
    collection_name: str,
    collection_description: str = "",
    collection_author: str = "",
) -> CollectionManifest:
    """Build a CollectionManifest from the current instance state.

    Reads global modlist, active_mods, and all meta.ini files to
    assemble the mod list with full metadata.

    Args:
        instance_path: Root of the instance.
        profile_path: Current profile folder.
        game_name: Human-readable game name.
        game_short_name: Game short identifier.
        game_nexus_name: Nexus Mods URL slug for the game.
        collection_name: Name for the collection.
        collection_description: Optional description.
        collection_author: Optional author name.

    Returns:
        A populated CollectionManifest.
    """
    profiles_dir = instance_path / ".profiles"
    mods_dir = instance_path / ".mods"

    mod_order = read_global_modlist(profiles_dir)
    active_mods = read_active_mods(profile_path)

    mods: list[CollectionMod] = []
    for name in mod_order:
        mod_path = mods_dir / name
        meta = read_meta_ini(mod_path) if mod_path.is_dir() else {}

        is_sep = name.endswith("_separator")

        nexus_id = 0
        raw_id = meta.get("modid", "0")
        try:
            nexus_id = int(raw_id)
        except (ValueError, TypeError):
            pass

        display = meta.get("name", "")
        if is_sep and not display:
            display = name[: -len("_separator")]

        raw_cat = meta.get("category", "")
        cat_ids: list[int] = []
        if raw_cat:
            for part in raw_cat.split(","):
                part = part.strip()
                if part:
                    try:
                        cid = int(part)
                        if cid > 0:
                            cat_ids.append(cid)
                    except ValueError:
                        pass

        # Separator color
        sep_color = ""
        if is_sep:
            sep_color = meta.get("color", "")

        # Build URL from nexus_id if not present in meta
        url = meta.get("url", "")
        if not url and nexus_id > 0 and game_nexus_name:
            url = f"https://www.nexusmods.com/{game_nexus_name}/mods/{nexus_id}"

        mods.append(CollectionMod(
            name=name,
            display_name=display,
            enabled=name in active_mods,
            is_separator=is_sep,
            nexus_id=nexus_id,
            version=meta.get("version", ""),
            author=meta.get("author", ""),
            url=url,
            category_ids=cat_ids,
            color=sep_color,
        ))

    return CollectionManifest(
        anvil_version=APP_VERSION,
        format_version=FORMAT_VERSION,
        game_name=game_name,
        game_short_name=game_short_name,
        game_nexus_name=game_nexus_name,
        collection_name=collection_name,
        collection_description=collection_description,
        collection_author=collection_author,
        collection_created=datetime.now(timezone.utc).isoformat(),
        mods=mods,
    )


def export_collection(
    manifest: CollectionManifest,
    target_path: Path,
    categories_path: Path | None = None,
) -> Path:
    """Write a ``.anvilpack`` ZIP to *target_path*.

    Args:
        manifest: The collection manifest to export.
        target_path: Destination file path (should end with .anvilpack).
        categories_path: Optional path to categories.json to include.

    Returns:
        The path to the written file.
    """
    manifest_json = json.dumps(
        _manifest_to_dict(manifest),
        ensure_ascii=False,
        indent=2,
    )

    with zipfile.ZipFile(target_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", manifest_json)

        if categories_path and categories_path.is_file():
            zf.write(str(categories_path), "categories.json")

    return target_path


# ── Import ──────────────────────────────────────────────────────────

def read_collection(zip_path: Path) -> CollectionManifest:
    """Read and parse a ``.anvilpack`` file.

    Args:
        zip_path: Path to the .anvilpack file.

    Returns:
        A CollectionManifest parsed from the archive.

    Raises:
        ValueError: If the archive has no manifest.json or it is
            malformed.
        zipfile.BadZipFile: If the file is not a valid ZIP.
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        if "manifest.json" not in zf.namelist():
            raise ValueError("Kein manifest.json in der .anvilpack-Datei gefunden")

        raw = zf.read("manifest.json")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"manifest.json ist kein gueltiges JSON: {exc}") from exc

    return _dict_to_manifest(data)


def read_collection_categories(zip_path: Path) -> list[dict[str, Any]] | None:
    """Read categories.json from a .anvilpack file if present.

    Returns:
        List of category dicts, or None if not present.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            if "categories.json" not in zf.namelist():
                return None
            raw = zf.read("categories.json")
            data = json.loads(raw)
            if isinstance(data, list):
                return data
    except (zipfile.BadZipFile, json.JSONDecodeError, OSError):
        pass
    return None


@dataclass
class ImportResult:
    """Result of comparing a collection against installed mods."""

    manifest: CollectionManifest
    installed: list[CollectionMod] = field(default_factory=list)
    missing: list[CollectionMod] = field(default_factory=list)
    separators: list[CollectionMod] = field(default_factory=list)


def analyze_collection(
    manifest: CollectionManifest,
    instance_path: Path,
) -> ImportResult:
    """Compare the collection's mods against what is installed.

    Args:
        manifest: The collection manifest.
        instance_path: Root of the current instance.

    Returns:
        An ImportResult with installed, missing, and separator lists.
    """
    mods_dir = instance_path / ".mods"
    on_disk: set[str] = set()
    if mods_dir.is_dir():
        try:
            on_disk = {c.name for c in mods_dir.iterdir() if c.is_dir()}
        except OSError:
            pass

    result = ImportResult(manifest=manifest)

    for mod in manifest.mods:
        if mod.is_separator:
            result.separators.append(mod)
        elif mod.name in on_disk:
            result.installed.append(mod)
        else:
            result.missing.append(mod)

    return result


def apply_collection(
    manifest: CollectionManifest,
    instance_path: Path,
    profile_path: Path,
    apply_categories: bool = True,
    categories_data: list[dict[str, Any]] | None = None,
) -> int:
    """Apply a collection to the current instance.

    Updates the global modlist order and profile active_mods.
    Creates separator folders if missing.  Optionally updates
    categories.json and mod category assignments.

    Args:
        manifest: The collection manifest.
        instance_path: Root of the instance.
        profile_path: Current profile folder.
        apply_categories: Whether to update category assignments.
        categories_data: Optional categories.json data to write.

    Returns:
        Number of missing mods (not on disk, excluding separators).
    """
    profiles_dir = instance_path / ".profiles"
    mods_dir = instance_path / ".mods"
    mods_dir.mkdir(parents=True, exist_ok=True)

    on_disk: set[str] = set()
    if mods_dir.is_dir():
        try:
            on_disk = {c.name for c in mods_dir.iterdir() if c.is_dir()}
        except OSError:
            pass

    # Build new mod order and active set
    new_order: list[str] = []
    new_active: set[str] = set()
    missing_count = 0

    for mod in manifest.mods:
        if mod.is_separator:
            # Create separator folder if missing
            sep_path = mods_dir / mod.name
            if not sep_path.is_dir():
                sep_path.mkdir(parents=True, exist_ok=True)
                # Write meta.ini for separator with color
                meta_data: dict[str, str] = {}
                if mod.display_name:
                    meta_data["name"] = mod.display_name
                if mod.color:
                    meta_data["color"] = mod.color
                if meta_data:
                    write_meta_ini(sep_path, meta_data)
            new_order.append(mod.name)
            if mod.enabled:
                new_active.add(mod.name)
        elif mod.name in on_disk:
            new_order.append(mod.name)
            if mod.enabled:
                new_active.add(mod.name)

            # Update meta.ini category assignment
            if apply_categories and mod.category_ids:
                mod_path = mods_dir / mod.name
                cat_str = ",".join(str(cid) for cid in mod.category_ids)
                write_meta_ini(mod_path, {"category": cat_str})
        else:
            missing_count += 1

    # Also keep mods that are on disk but not in collection (append at end)
    existing_order = read_global_modlist(profiles_dir)
    for name in existing_order:
        if name not in new_order and name in on_disk:
            new_order.append(name)

    # Write new global modlist
    write_global_modlist(profiles_dir, new_order)

    # Write new active mods for this profile
    write_active_mods(profile_path, new_active)

    # Update categories.json if provided
    if apply_categories and categories_data is not None:
        cats_file = instance_path / "categories.json"
        try:
            cats_file.write_text(
                json.dumps(categories_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            print(
                f"collection_io: failed to write categories: {exc}",
                file=sys.stderr,
            )

    return missing_count
