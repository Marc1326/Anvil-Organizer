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
- Order = priority: first line = lowest priority (loaded first,
  can be overwritten), last line = highest priority (wins conflicts).
"""

from __future__ import annotations

import sys
from pathlib import Path

_HEADER = "# Managed by Anvil Organizer\n"


def read_modlist(profile_path: Path) -> list[tuple[str, bool]]:
    """Read ``modlist.txt`` from *profile_path*.

    Args:
        profile_path: Path to a profile folder
                      (e.g. ``.profiles/Default/``).

    Returns:
        List of ``(mod_name, enabled)`` in file order
        (first entry = lowest priority).
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

    lines = [_HEADER]
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
