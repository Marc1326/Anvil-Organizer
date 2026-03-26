"""Read and write MO2-compatible modlist.txt files.

Each profile folder (e.g. ``.profiles/Default/``) contains a
``modlist.txt`` that defines mod load order and enabled/disabled state.

Format::

    # Managed by Anvil Organizer
    +EnabledModName
    -DisabledModName
    +AnotherMod

- Lines starting with ``+`` are enabled mods.
- Lines starting with ``-`` are disabled mods.
- Lines starting with ``#`` are comments.
- Empty lines are ignored.
- Order = priority: first line = highest priority (wins conflicts),
  last line = lowest priority. The deployer reverses internally.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HEADER = "# Managed by Anvil Organizer\n"
_HEADER_V2 = "# Managed by Anvil Organizer v2\n"


def read_modlist(profile_path: Path) -> list[tuple[str, bool]]:
    """Read ``modlist.txt`` from *profile_path*.

    Args:
        profile_path: Path to a profile folder
                      (e.g. ``.profiles/Default/``).

    Returns:
        List of ``(mod_name, enabled)`` in file order
        (first entry = highest priority).
    """
    modlist = profile_path / "modlist.txt"
    if not modlist.is_file():
        return []

    result: list[tuple[str, bool]] = []

    try:
        text = modlist.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"mod_list_io: failed to read {modlist}: {exc}",
            file=sys.stderr,
        )
        return []

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("+"):
            result.append((line[1:], True))
        elif line.startswith("-"):
            result.append((line[1:], False))
        # Lines without +/- prefix are ignored (malformed)

    return result


def write_modlist(
    profile_path: Path, mods: list[tuple[str, bool]],
) -> None:
    """Write ``modlist.txt`` to *profile_path*.

    Args:
        profile_path: Path to a profile folder.
        mods: List of ``(mod_name, enabled)`` in desired order.
    """
    modlist = profile_path / "modlist.txt"

    lines = [_HEADER_V2]
    for name, enabled in mods:
        prefix = "+" if enabled else "-"
        lines.append(f"{prefix}{name}\n")

    try:
        profile_path.mkdir(parents=True, exist_ok=True)
        modlist.write_text("".join(lines), encoding="utf-8")
    except OSError as exc:
        print(
            f"mod_list_io: failed to write {modlist}: {exc}",
            file=sys.stderr,
        )


def add_mod_to_modlist(
    profile_path: Path, mod_name: str, enabled: bool = True,
) -> None:
    """Append a mod at the end of ``modlist.txt`` (highest priority).

    If the mod is already in the list it is **not** added again.

    Args:
        profile_path: Path to a profile folder.
        mod_name: Name of the mod to add.
        enabled: Whether the mod should be enabled.
    """
    existing = read_modlist(profile_path)

    # Skip if already present
    for name, _ in existing:
        if name == mod_name:
            return

    existing.append((mod_name, enabled))
    write_modlist(profile_path, existing)


def insert_mod_in_modlist(
    profile_path: Path, mod_name: str, position: int, enabled: bool = True,
) -> None:
    """Insert a mod at a specific position in ``modlist.txt``.

    If the mod is already in the list it is **not** added again.

    Args:
        profile_path: Path to a profile folder.
        mod_name: Name of the mod to insert.
        position: 0-based index in the list.
        enabled: Whether the mod should be enabled.
    """
    existing = read_modlist(profile_path)

    for name, _ in existing:
        if name == mod_name:
            return

    position = max(0, min(position, len(existing)))
    existing.insert(position, (mod_name, enabled))
    write_modlist(profile_path, existing)


def remove_mod_from_modlist(profile_path: Path, mod_name: str) -> None:
    """Remove a mod from ``modlist.txt``.

    Does nothing if the mod is not in the list.

    Args:
        profile_path: Path to a profile folder.
        mod_name: Name of the mod to remove.
    """
    existing = read_modlist(profile_path)
    filtered = [(n, e) for n, e in existing if n != mod_name]

    if len(filtered) != len(existing):
        write_modlist(profile_path, filtered)


def remove_mod_from_global_modlist(profiles_dir: Path, mod_name: str) -> None:
    """Remove a mod from the global ``modlist.txt``.

    Does nothing if the mod is not in the list.

    Args:
        profiles_dir: Path to the .profiles directory.
        mod_name: Name of the mod to remove.
    """
    existing = read_global_modlist(profiles_dir)
    filtered = [n for n in existing if n != mod_name]

    if len(filtered) != len(existing):
        write_global_modlist(profiles_dir, filtered)


def rename_mod_in_modlist(
    profile_path: Path, old_name: str, new_name: str,
) -> None:
    """Rename a mod in ``modlist.txt``.

    Args:
        profile_path: Path to a profile folder.
        old_name: Current mod name.
        new_name: New mod name.
    """
    existing = read_modlist(profile_path)
    updated = [
        (new_name if n == old_name else n, e) for n, e in existing
    ]
    write_modlist(profile_path, updated)


# ─────────────────────────────────────────────────────────────────────
# Profile-specific active mods (active_mods.json)
# ─────────────────────────────────────────────────────────────────────

def read_active_mods(profile_path: Path) -> set[str]:
    """Read ``active_mods.json`` from a profile folder.

    Args:
        profile_path: Path to a profile folder
                      (e.g. ``.profiles/Default/``).

    Returns:
        Set of mod names that are active in this profile.
        Empty set if file doesn't exist.
    """
    json_file = profile_path / "active_mods.json"
    if not json_file.is_file():
        return set()

    try:
        text = json_file.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, list):
            return set(data)
        return set()
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"mod_list_io: failed to read {json_file}: {exc}",
            file=sys.stderr,
        )
        return set()


def write_active_mods(profile_path: Path, active_mods: set[str]) -> None:
    """Write ``active_mods.json`` to a profile folder.

    Args:
        profile_path: Path to a profile folder.
        active_mods: Set of mod names that are active.
    """
    json_file = profile_path / "active_mods.json"

    try:
        profile_path.mkdir(parents=True, exist_ok=True)
        # Sort for consistent output
        json_file.write_text(
            json.dumps(sorted(active_mods), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        print(
            f"mod_list_io: failed to write {json_file}: {exc}",
            file=sys.stderr,
        )


def read_global_modlist(profiles_dir: Path) -> list[str]:
    """Read global ``modlist.txt`` from the .profiles directory.

    The global modlist contains only the load order (all mods listed).
    Active/inactive state comes from profile-specific active_mods.json.

    Args:
        profiles_dir: Path to the .profiles directory
                      (e.g. ``instance_path/.profiles/``).

    Returns:
        List of mod names in load order (first = highest priority).
    """
    modlist = profiles_dir / "modlist.txt"
    if not modlist.is_file():
        return []

    result: list[str] = []

    try:
        text = modlist.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"mod_list_io: failed to read {modlist}: {exc}",
            file=sys.stderr,
        )
        return []

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Strip +/- prefix if present (treat all as order-only)
        if line.startswith("+") or line.startswith("-"):
            result.append(line[1:])
        else:
            result.append(line)

    return result


def _is_separator_name(name: str) -> bool:
    """Check if a mod name represents a separator (ends with ``_separator``)."""
    return name.endswith("_separator")


def write_global_modlist(profiles_dir: Path, mod_names: list[str]) -> None:
    """Write global ``modlist.txt`` to the .profiles directory.

    All mods are written with '+' prefix (order-only, no enabled state).
    Uses the v2 header to indicate the new separator-before-mods format.

    Args:
        profiles_dir: Path to the .profiles directory.
        mod_names: List of mod names in desired load order.
    """
    modlist = profiles_dir / "modlist.txt"

    lines = [_HEADER_V2]
    for name in mod_names:
        lines.append(f"+{name}\n")

    try:
        profiles_dir.mkdir(parents=True, exist_ok=True)
        modlist.write_text("".join(lines), encoding="utf-8")
    except OSError as exc:
        print(
            f"mod_list_io: failed to write {modlist}: {exc}",
            file=sys.stderr,
        )


def migrate_modlist_order(profiles_dir: Path) -> bool:
    """Update modlist.txt header from v1 to v2.

    Previously this function also reordered entries (moving separators
    before their mods). That reordering logic has been removed because
    ``write_global_modlist()`` already writes the correct v2 format.
    Running the reorder on data that is already in v2 order (but with a
    v1 header) caused mods to shift down by one separator group on every
    start.

    Now the function only:
    1. Checks if the header is already v2 — if yes, returns False.
    2. Creates a backup (modlist.txt.bak).
    3. Replaces the v1 header with v2, keeping all entries unchanged.

    Args:
        profiles_dir: Path to the .profiles directory.

    Returns:
        True if the header was updated, False if not needed.
    """
    modlist = profiles_dir / "modlist.txt"
    if not modlist.is_file():
        return False

    try:
        text = modlist.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"mod_list_io: migrate_modlist_order: failed to read {modlist}: {exc}",
            file=sys.stderr,
        )
        return False

    # Already migrated? Check for v2 header
    first_line = text.split("\n", 1)[0].strip()
    if "v2" in first_line:
        return False

    # Create backup before modifying
    backup = profiles_dir / "modlist.txt.bak"
    try:
        backup.write_text(text, encoding="utf-8")
        print(f"mod_list_io: backup created: {backup}", flush=True)
    except OSError as exc:
        print(
            f"mod_list_io: failed to create backup {backup}: {exc}",
            file=sys.stderr,
        )

    # Replace the v1 header with v2, keep everything else unchanged
    new_text = text.replace(_HEADER, _HEADER_V2, 1)
    # If the old header wasn't found exactly (e.g. extra whitespace),
    # replace the first line manually
    if new_text == text:
        lines = text.split("\n", 1)
        new_text = _HEADER_V2.rstrip("\n") + "\n" + (lines[1] if len(lines) > 1 else "")

    try:
        modlist.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        print(
            f"mod_list_io: failed to write {modlist}: {exc}",
            file=sys.stderr,
        )
        return False

    print(
        f"mod_list_io: updated modlist header to v2: {modlist}",
        flush=True,
    )
    return True


# ─────────────────────────────────────────────────────────────────────
# Locked mods (locked_mods.json)
# ─────────────────────────────────────────────────────────────────────

def read_locked_mods(profiles_dir: Path) -> set[str]:
    """Read ``locked_mods.json`` from the .profiles directory.

    Args:
        profiles_dir: Path to the .profiles directory.

    Returns:
        Set of mod names that are locked.
        Empty set if file doesn't exist.
    """
    json_file = profiles_dir / "locked_mods.json"
    if not json_file.is_file():
        return set()

    try:
        text = json_file.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, list):
            return set(data)
        return set()
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"mod_list_io: failed to read {json_file}: {exc}",
            file=sys.stderr,
        )
        return set()


def write_locked_mods(profiles_dir: Path, locked_mods: set[str]) -> None:
    """Write ``locked_mods.json`` to the .profiles directory.

    Args:
        profiles_dir: Path to the .profiles directory.
        locked_mods: Set of mod names that are locked.
    """
    json_file = profiles_dir / "locked_mods.json"

    try:
        profiles_dir.mkdir(parents=True, exist_ok=True)
        # Sort for consistent output
        json_file.write_text(
            json.dumps(sorted(locked_mods), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        print(
            f"mod_list_io: failed to write {json_file}: {exc}",
            file=sys.stderr,
        )


def rename_mod_globally(
    profiles_dir: Path, old_name: str, new_name: str,
) -> None:
    """Rename a mod in global modlist.txt and active_mods.json in ALL profiles.

    Args:
        profiles_dir: Path to the .profiles directory.
        old_name: Current mod name.
        new_name: New mod name.
    """
    # 1. Update global modlist.txt
    order = read_global_modlist(profiles_dir)
    updated = [new_name if n == old_name else n for n in order]
    write_global_modlist(profiles_dir, updated)

    # 2. Update active_mods.json in every profile
    if not profiles_dir.is_dir():
        return
    for profile_dir in sorted(profiles_dir.iterdir()):
        if not profile_dir.is_dir():
            continue
        active = read_active_mods(profile_dir)
        if old_name in active:
            active.discard(old_name)
            active.add(new_name)
            write_active_mods(profile_dir, active)

    # 3. Update locked_mods.json
    locked = read_locked_mods(profiles_dir)
    if old_name in locked:
        locked.discard(old_name)
        locked.add(new_name)
        write_locked_mods(profiles_dir, locked)


def remove_mod_globally(profiles_dir: Path, mod_name: str) -> None:
    """Remove a mod from global modlist.txt and active_mods.json in ALL profiles.

    Args:
        profiles_dir: Path to the .profiles directory.
        mod_name: Name of the mod to remove.
    """
    # 1. Update global modlist.txt
    order = read_global_modlist(profiles_dir)
    filtered = [n for n in order if n != mod_name]
    if len(filtered) != len(order):
        write_global_modlist(profiles_dir, filtered)

    # 2. Update active_mods.json in every profile
    if not profiles_dir.is_dir():
        return
    for profile_dir in sorted(profiles_dir.iterdir()):
        if not profile_dir.is_dir():
            continue
        active = read_active_mods(profile_dir)
        if mod_name in active:
            active.discard(mod_name)
            write_active_mods(profile_dir, active)

    # 3. Update locked_mods.json
    locked = read_locked_mods(profiles_dir)
    if mod_name in locked:
        locked.discard(mod_name)
        write_locked_mods(profiles_dir, locked)


def migrate_to_global_modlist(profiles_dir: Path) -> bool:
    """Migrate from per-profile modlist.txt to global modlist + active_mods.json.

    This function checks if migration is needed and performs it automatically.
    Migration happens when:
    - No global modlist.txt exists in profiles_dir
    - At least one profile has a legacy per-profile modlist.txt

    The Default profile's modlist.txt becomes the global load order.
    Each profile's enabled mods are extracted to active_mods.json.

    Args:
        profiles_dir: Path to the .profiles directory.

    Returns:
        True if migration was performed, False if not needed.
    """
    global_modlist = profiles_dir / "modlist.txt"

    # Already migrated?
    if global_modlist.is_file():
        return False

    # Find all profile folders
    if not profiles_dir.is_dir():
        return False

    profile_folders = [d for d in profiles_dir.iterdir() if d.is_dir()]
    if not profile_folders:
        return False

    # Use Default profile as the source for global order, or first available
    default_profile = profiles_dir / "Default"
    source_profile = default_profile if default_profile.is_dir() else profile_folders[0]
    source_modlist = source_profile / "modlist.txt"

    if not source_modlist.is_file():
        return False

    # Read source modlist for global order
    source_data = read_modlist(source_profile)
    if not source_data:
        return False

    # Write global modlist (order only)
    mod_order = [name for name, _ in source_data]
    write_global_modlist(profiles_dir, mod_order)

    # Migrate each profile's enabled state to active_mods.json
    for profile_folder in profile_folders:
        legacy_modlist = profile_folder / "modlist.txt"
        if not legacy_modlist.is_file():
            continue

        legacy_data = read_modlist(profile_folder)
        active_mods = {name for name, enabled in legacy_data if enabled}
        write_active_mods(profile_folder, active_mods)

        # Remove legacy per-profile modlist.txt
        try:
            legacy_modlist.unlink()
        except OSError:
            pass

    return True
