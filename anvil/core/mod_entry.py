"""ModEntry dataclass and filesystem scanner.

A ``ModEntry`` holds all metadata for a single mod.  The
:func:`scan_mods_directory` function builds a list of entries by
merging data from three sources:

1. ``modlist.txt`` — load order and enabled/disabled state
2. ``meta.ini``   — display name, version, author, etc.
3. Filesystem     — file count and total size
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from anvil.core.mod_list_io import read_modlist
from anvil.core.mod_metadata import read_meta_ini


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
    category: str = ""
    nexus_id: int = 0
    author: str = ""
    description: str = ""
    url: str = ""
    install_date: str = ""                 # ISO format

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
) -> ModEntry:
    """Build a ModEntry from filesystem + meta.ini."""
    mod_path = mods_dir / name
    meta = read_meta_ini(mod_path)

    file_count, total_size = _count_files(mod_path)

    nexus_id = 0
    raw_id = meta.get("modid", "0")
    try:
        nexus_id = int(raw_id)
    except (ValueError, TypeError):
        pass

    return ModEntry(
        name=name,
        enabled=enabled,
        priority=priority,
        install_path=mod_path,
        display_name=meta.get("name", ""),
        version=meta.get("version", ""),
        category=meta.get("category", ""),
        nexus_id=nexus_id,
        author=meta.get("author", ""),
        description=meta.get("description", ""),
        url=meta.get("url", ""),
        install_date=meta.get("installDate", ""),
        file_count=file_count,
        total_size=total_size,
    )


def scan_mods_directory(
    instance_path: Path,
    profile_path: Path,
) -> list[ModEntry]:
    """Scan an instance's mods and return a sorted list of ModEntry.

    Merge logic:

    1. Read ``modlist.txt`` from *profile_path* for order + enabled state.
    2. Scan ``.mods/`` under *instance_path* for actual mod folders.
    3. For each mod in ``modlist.txt`` that exists on disk: build entry.
    4. For each mod on disk **not** in ``modlist.txt``: append at end
       (newly installed, enabled by default).
    5. Mods in ``modlist.txt`` but **not** on disk are skipped (deleted).

    Args:
        instance_path: Root of the instance
                       (e.g. ``~/.anvil-organizer/instances/Cyberpunk 2077/``).
        profile_path: Profile folder
                      (e.g. ``instance_path/.profiles/Default/``).

    Returns:
        List of :class:`ModEntry`, ordered by priority
        (index 0 = lowest priority).
    """
    mods_dir = instance_path / ".mods"

    # 1. Read modlist.txt
    modlist = read_modlist(profile_path)

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

    for name, enabled in modlist:
        if name not in on_disk:
            continue  # deleted from disk
        seen.add(name)
        result.append(_build_entry(name, enabled, priority, mods_dir))
        priority += 1

    # 4. Append new mods (on disk but not in modlist)
    new_mods = sorted(on_disk - seen)
    for name in new_mods:
        result.append(_build_entry(name, True, priority, mods_dir))
        priority += 1

    return result
