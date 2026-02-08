"""Bottles detection for Linux.

Finds Bottles (Wine prefix manager) installations and reads their
configuration.  Uses a simple top-level YAML key-value parser to
avoid depending on PyYAML.

Bottles does **not** track individual games — it manages Wine
prefixes (bottles).  Game-to-bottle mapping is done manually by
the user.

Typical usage::

    from anvil.stores.bottles_utils import find_bottles
    bottles = find_bottles()   # [{"name": "BG3", "path": Path(...), ...}]
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Bottles directory candidates (checked in order) ───────────────────

_BOTTLES_PATHS: list[Path] = [
    Path.home() / ".local" / "share" / "bottles" / "bottles",
    # Flatpak
    Path.home() / ".var" / "app" / "com.usebottles.bottles"
    / "data" / "bottles" / "bottles",
]

# Top-level keys we care about in bottle.yml
_WANTED_KEYS = {"Name", "Path", "Environment", "Runner", "Arch"}


# ── Simple YAML parser ────────────────────────────────────────────────

def _parse_bottle_yml(yml_path: Path) -> dict[str, str] | None:
    """Parse top-level scalar key-value pairs from a bottle.yml file.

    Only reads lines of the form ``Key: value`` at the top level
    (no leading whitespace).  Skips nested blocks, lists, and
    mapping values (``{}``, ``[]``, ``-``).  This is intentionally
    minimal to avoid a PyYAML dependency.

    Args:
        yml_path: Path to a ``bottle.yml`` file.

    Returns:
        Dict of parsed key-value pairs, or None on failure.
    """
    try:
        text = yml_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"bottles_utils: cannot read {yml_path}: {exc}", file=sys.stderr)
        return None

    result: dict[str, str] = {}

    for line in text.splitlines():
        # Skip blank lines, comments, and indented (nested) lines
        if not line or line[0] in (" ", "\t", "#"):
            continue

        colon = line.find(":")
        if colon < 1:
            continue

        key = line[:colon]
        raw_value = line[colon + 1:].strip()

        # Skip block openers — value is a nested structure
        if raw_value in ("", "{}", "[]") or raw_value.startswith("{") or raw_value.startswith("["):
            continue
        if raw_value.startswith("- "):
            continue

        # Strip surrounding quotes if present
        if len(raw_value) >= 2 and raw_value[0] in ("'", '"') and raw_value[-1] == raw_value[0]:
            raw_value = raw_value[1:-1]

        result[key] = raw_value

    return result


# ── Public API ─────────────────────────────────────────────────────────

def find_bottles() -> list[dict]:
    """Find all Bottles (Wine prefixes) on the system.

    Scans the Bottles data directories for subdirectories containing
    a ``bottle.yml`` configuration file.

    Returns:
        List of dicts, each with keys:

        - ``name`` (str): Bottle display name
        - ``path`` (Path): Absolute path to the bottle directory
        - ``environment`` (str): Environment type (Gaming, Application, Custom)
        - ``runner`` (str): Wine/Proton runner used
    """
    bottles: list[dict] = []
    seen_paths: set[Path] = set()

    for base in _BOTTLES_PATHS:
        if not base.is_dir():
            continue

        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue

            yml_path = entry / "bottle.yml"
            if not yml_path.is_file():
                continue

            # Avoid duplicates if nativ and Flatpak point to the same dir
            real = entry.resolve()
            if real in seen_paths:
                continue
            seen_paths.add(real)

            parsed = _parse_bottle_yml(yml_path)
            if parsed is None:
                continue

            name = parsed.get("Name", entry.name)

            bottles.append({
                "name": name,
                "path": entry,
                "environment": parsed.get("Environment", ""),
                "runner": parsed.get("Runner", ""),
            })

    return bottles
