"""ModEntry dataclass and filesystem scanner.

A ``ModEntry`` holds all metadata for a single mod.  The
:func:`scan_mods_directory` function builds a list of entries by
merging data from three sources:

1. ``modlist.txt`` — global load order (in .profiles/)
2. ``active_mods.json`` — profile-specific enabled state
3. ``meta.ini``   — display name, version, author, etc.
4. Filesystem     — file count and total size (via ModIndex cache)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from anvil.core.mod_list_io import (
    read_active_mods,
    read_global_modlist,
    read_modlist,
)
from anvil.core.mod_metadata import read_meta_ini

if TYPE_CHECKING:
    from anvil.core.modindex import ModIndex


@dataclass
class ModEntry:
    """Complete metadata for a single mod."""

    name: str                              # Folder name under .mods/
    enabled: bool = True
    priority: int = 0                      # 0 = lowest (top of modlist.txt)
    install_path: Path | None = None       # .mods/<name>/

    # From meta.ini
    display_name: str = ""                 # May differ from folder name
    version: str = ""
    category: str = ""                     # Comma-separated IDs (primary first)
    primary_category: int = 0              # First ID in category list
    category_ids: list[int] = field(default_factory=list)  # Parsed IDs
    nexus_id: int = 0
    author: str = ""
    description: str = ""
    url: str = ""
    install_date: str = ""                 # ISO format

    # Special types
    is_separator: bool = False             # True for _separator dirs
    is_direct_install: bool = False        # True for framework mods (copy, not symlink)
    is_data_override: bool = False         # True for BG3 data-override mods (loose files in Data/)

    # Separator color (from meta.ini, compatible with common meta.ini format)
    color: str = ""                        # Hex color e.g. "#FF0000", empty = no custom color

    # Custom deploy path (from meta.ini, only for separators)
    deploy_path: str = ""                  # Absolute path or empty = use global game path

    # Group membership (set by GroupManager, NOT from meta.ini)
    group: str = ""                        # Group name this mod belongs to

    # Nexus metadata
    nexus_category: int = 0                # Nexus category ID from meta.ini

    # Computed from filesystem
    file_count: int = 0
    total_size: int = 0                    # Bytes


def _count_files(path: Path) -> tuple[int, int]:
    """Count files and total size under *path* (recursive).

    Returns:
        ``(file_count, total_bytes)``
    """
    count = 0
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                count += 1
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return count, total


def _build_entry(
    name: str,
    enabled: bool,
    priority: int,
    mods_dir: Path,
    mod_index: ModIndex | None = None,
) -> ModEntry:
    """Build a ModEntry from filesystem + meta.ini.

    When *mod_index* is provided, file_count and total_size are read
    from the cache instead of scanning the filesystem.
    """
    mod_path = mods_dir / name
    meta = read_meta_ini(mod_path)

    if mod_index is not None:
        file_count, total_size = mod_index.get_stats(name)
    else:
        file_count, total_size = _count_files(mod_path)

    nexus_id = 0
    raw_id = meta.get("modid", "0")
    try:
        nexus_id = int(raw_id)
    except (ValueError, TypeError):
        pass

    is_sep = name.endswith("_separator")
    display = meta.get("name", "")
    if is_sep and not display:
        display = name[:-len("_separator")]

    # Parse comma-separated category IDs (primary first)
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
    primary_cat = cat_ids[0] if cat_ids else 0

    # Read separator color from meta.ini (compatible with common meta.ini format)
    sep_color = ""
    sep_deploy_path = ""
    if is_sep:
        raw_color = meta.get("color", "")
        if raw_color:
            sep_color = raw_color
        raw_deploy = meta.get("deploy_path", "")
        if raw_deploy:
            sep_deploy_path = raw_deploy

    # Parse Nexus category ID
    nexus_cat = 0
    raw_ncat = meta.get("nexuscategory", meta.get("nexusCategory", "0"))
    try:
        nexus_cat = int(raw_ncat)
    except (ValueError, TypeError):
        pass

    return ModEntry(
        name=name,
        enabled=enabled,
        priority=priority,
        install_path=mod_path,
        display_name=display,
        version=meta.get("version", ""),
        category=raw_cat,
        primary_category=primary_cat,
        category_ids=cat_ids,
        nexus_id=nexus_id,
        author=meta.get("author", ""),
        description=meta.get("description", ""),
        url=meta.get("url", ""),
        install_date=meta.get("installDate", ""),
        is_separator=is_sep,
        color=sep_color,
        deploy_path=sep_deploy_path,
        nexus_category=nexus_cat,
        file_count=file_count,
        total_size=total_size,
    )


def scan_mods_directory(
    instance_path: Path,
    profile_path: Path,
    include_external: bool = True,
    mod_index: ModIndex | None = None,
) -> list[ModEntry]:
    """Scan an instance's mods and return a sorted list of ModEntry.

    Merge logic:

    1. Read global ``modlist.txt`` from ``.profiles/`` for load order.
    2. Read ``active_mods.json`` from *profile_path* for enabled state.
    3. Scan ``.mods/`` under *instance_path* for actual mod folders.
    4. For each mod in ``modlist.txt`` that exists on disk: build entry.
    5. For each mod on disk **not** in ``modlist.txt``: append at end
       (newly installed, enabled by default).  Skipped when
       *include_external* is ``False``.
    6. Mods in ``modlist.txt`` but **not** on disk are skipped (deleted).

    Falls back to legacy per-profile modlist.txt if no global modlist exists.

    Args:
        instance_path: Root of the instance
                       (e.g. ``~/.anvil-organizer/instances/Cyberpunk 2077/``).
        profile_path: Profile folder
                      (e.g. ``instance_path/.profiles/Default/``).
        include_external: When ``False``, mods on disk but not in
                          ``modlist.txt`` are excluded from the result.
        mod_index: Optional :class:`ModIndex` instance for cached
                   file counts and sizes.

    Returns:
        List of :class:`ModEntry`, ordered by priority
        (index 0 = lowest priority).
    """
    mods_dir = instance_path / ".mods"
    profiles_dir = instance_path / ".profiles"

    # 1. Try global modlist first, fallback to legacy per-profile
    global_modlist = profiles_dir / "modlist.txt"
    if global_modlist.is_file():
        # New system: global order + profile-specific active state
        mod_order = read_global_modlist(profiles_dir)
        active_mods = read_active_mods(profile_path)
        use_global = True
    else:
        # Legacy: per-profile modlist with +/- prefixes
        legacy = read_modlist(profile_path)
        mod_order = [name for name, _ in legacy]
        active_mods = {name for name, enabled in legacy if enabled}
        use_global = False

    # 2. Discover actual mod folders on disk
    on_disk: set[str] = set()
    if mods_dir.is_dir():
        try:
            for child in mods_dir.iterdir():
                if child.is_dir():
                    on_disk.add(child.name)
        except OSError as exc:
            print(
                f"mod_entry: failed to scan {mods_dir}: {exc}",
                file=sys.stderr,
            )

    # 3. Build entries from modlist order (skip missing)
    result: list[ModEntry] = []
    seen: set[str] = set()
    priority = 0

    for name in mod_order:
        if name not in on_disk:
            continue  # deleted from disk
        seen.add(name)
        enabled = name in active_mods
        entry = _build_entry(name, enabled, priority, mods_dir, mod_index)
        result.append(entry)
        priority += 1

    # 4. Append new mods (on disk but not in modlist)
    # New mods default to enabled
    # When include_external=False, skip mods not listed in modlist.txt
    if include_external:
        new_mods = sorted(on_disk - seen)
        for name in new_mods:
            entry = _build_entry(name, True, priority, mods_dir, mod_index)
            result.append(entry)
            priority += 1

    return result
