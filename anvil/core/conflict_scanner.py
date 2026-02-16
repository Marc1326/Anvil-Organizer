"""Intelligent conflict detection for mod files.

MO2 detects conflicts purely by filename — two mods having a file called
"readme.txt" counts as a conflict even if they live at different relative
paths and would never overwrite each other.

ConflictScanner improves on this by comparing *relative paths* instead of
bare filenames.  A conflict only exists when two or more mods contain a
file at the **exact same relative path** (e.g. both have
``archive/pc/mod/outfit.archive``).

Game plugins can additionally supply ignore patterns (via
``get_conflict_ignores()``) to suppress known harmless matches like
readme files or per-mod metadata.
"""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path, PurePosixPath


def _match_ignore(rel_path: str, pattern: str) -> bool:
    """Match a relative path against an ignore pattern.

    Supports ``**`` as a directory wildcard:
    - ``**/readme*.txt`` matches ``readme.txt`` AND ``docs/readme.txt``
    - ``**/docs/**`` matches ``docs/foo.txt`` AND ``sub/docs/bar.txt``

    Both *rel_path* and *pattern* are compared case-insensitively.
    """
    rl = rel_path.lower()
    pl = pattern.lower()

    # If pattern starts with **/, also match against the bare filename
    # and every suffix of the path.
    if pl.startswith("**/"):
        tail = pl[3:]  # pattern after **/
        # Direct match against full path
        if fnmatch(rl, tail):
            return True
        # Match against full path with ** mapped to *
        if fnmatch(rl, pl.replace("**/", "*/")):
            return True
        # Match each path suffix (e.g. "a/b/c" -> try "b/c", "c")
        parts = PurePosixPath(rl).parts
        for i in range(1, len(parts)):
            suffix = "/".join(parts[i:])
            if fnmatch(suffix, tail):
                return True
        return False

    return fnmatch(rl, pl)


class ConflictScanner:
    """Scan active mods for real file conflicts."""

    # Files that are always internal to Anvil and never conflict.
    _INTERNAL_FILES = {"meta.ini"}

    # Extensions that are never real conflicts (readme files, docs, etc.)
    _IGNORED_EXTENSIONS = {".txt"}

    def scan_conflicts(
        self,
        mods: list[dict],
        game_plugin=None,
    ) -> dict:
        """Scan *mods* for file conflicts.

        Args:
            mods: Ordered list of mod dicts, each with ``name`` (str) and
                  ``path`` (str or Path).  Index 0 = lowest priority,
                  last entry = highest priority (winner on conflict).
            game_plugin: Optional ``BaseGame`` instance.  If provided,
                         ``get_conflict_ignores()`` is called to obtain
                         patterns for harmless files that should be
                         filtered out.

        Returns:
            Dict with two keys:

            - ``conflicts`` — list of real conflict dicts, each with
              ``file`` (relative path), ``mods`` (list of mod names),
              and ``winner`` (mod name with highest priority).
            - ``ignored`` — list of filtered-out matches (same format
              but without ``winner``).
        """
        # 1. Collect ignore patterns from game plugin
        ignore_patterns: list[str] = []
        if game_plugin is not None and hasattr(game_plugin, "get_conflict_ignores"):
            ignore_patterns = game_plugin.get_conflict_ignores()

        # 2. Build mapping: relative_path -> [mod_name, ...]
        #    Preserves insertion order (= priority order).
        file_owners: dict[str, list[str]] = {}

        for mod in mods:
            mod_name = mod["name"]
            mod_root = Path(mod["path"])

            if not mod_root.is_dir():
                continue

            for file_path in mod_root.rglob("*"):
                if not file_path.is_file():
                    continue

                rel = file_path.relative_to(mod_root).as_posix()

                # Skip Anvil-internal files
                if file_path.name in self._INTERNAL_FILES:
                    continue

                # Skip ignored extensions (readme files, docs, etc.)
                if file_path.suffix.lower() in self._IGNORED_EXTENSIONS:
                    continue

                owners = file_owners.setdefault(rel, [])
                owners.append(mod_name)

        # 3. Separate real conflicts from ignored matches
        conflicts: list[dict] = []
        ignored: list[dict] = []

        for rel_path, owners in file_owners.items():
            if len(owners) < 2:
                continue

            # Check against ignore patterns (case-insensitive)
            is_ignored = any(
                _match_ignore(rel_path, pat)
                for pat in ignore_patterns
            )

            if is_ignored:
                ignored.append({
                    "file": rel_path,
                    "mods": owners,
                })
            else:
                conflicts.append({
                    "file": rel_path,
                    "mods": owners,
                    "winner": owners[-1],  # highest priority = last in list
                })

        return {"conflicts": conflicts, "ignored": ignored}
