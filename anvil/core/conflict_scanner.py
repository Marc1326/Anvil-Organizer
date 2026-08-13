"""Intelligent conflict detection for mod files.

Traditional mod managers detect conflicts purely by filename — two mods having
a file called "readme.txt" counts as a conflict even if they live at different
relative paths and would never overwrite each other.

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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anvil.core.modindex import ModIndex


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
        mod_index: ModIndex | None = None,
        pak_file_lists: dict[str, list[dict]] | None = None,
        archive_hashes: dict[str, dict[str, frozenset[int]]] | None = None,
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
            mod_index: Optional :class:`ModIndex` for cached file lists.
                       When provided, avoids expensive ``rglob`` calls.
            archive_hashes: Mod-Name -> Archivpfad -> Pruefsummen der
                       enthaltenen Spieldateien. Damit werden Konflikte
                       *innerhalb* gepackter Archive sichtbar, die im
                       Dateivergleich unsichtbar bleiben: zwei Archive
                       mit verschiedenen Namen liefern dieselbe Datei.

        Returns:
            Dict with two keys:

            - ``conflicts`` — list of real conflict dicts, each with
              ``file`` (relative path), ``mods`` (list of mod names),
              and ``winner`` (mod name with highest priority).
            - ``ignored`` — list of filtered-out matches (same format
              but without ``winner``).
            - ``file_owners`` — every file the active mods provide,
              mapped to its owning mods in priority order (last wins).
              This is what the game would see once deployed.
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

            # Try pak file lists first (BG3 .pak archives)
            if pak_file_lists is not None and mod_name in pak_file_lists:
                for finfo in pak_file_lists[mod_name]:
                    rel = finfo["rel"]
                    fname = rel.rsplit("/", 1)[-1] if "/" in rel else rel
                    if fname in self._INTERNAL_FILES:
                        continue
                    dot_pos = fname.rfind(".")
                    ext = fname[dot_pos:].lower() if dot_pos >= 0 else ""
                    if ext in self._IGNORED_EXTENSIONS:
                        continue
                    owners = file_owners.setdefault(rel, [])
                    owners.append(mod_name)
                continue

            # pak mode active but mod not in file lists → skip entirely
            if pak_file_lists is not None:
                continue

            # Try cached file list next
            if mod_index is not None:
                cached_files = mod_index.get_file_list(mod_name)
                if cached_files:
                    for finfo in cached_files:
                        rel = finfo["rel"]
                        # Extract filename for internal-file check
                        fname = rel.rsplit("/", 1)[-1] if "/" in rel else rel
                        if fname in self._INTERNAL_FILES:
                            continue
                        # Extract extension for ignored-extension check
                        dot_pos = fname.rfind(".")
                        ext = fname[dot_pos:].lower() if dot_pos >= 0 else ""
                        if ext in self._IGNORED_EXTENSIONS:
                            continue
                        owners = file_owners.setdefault(rel, [])
                        owners.append(mod_name)
                    continue

            # Fallback: scan filesystem directly
            # Ohne Pfad nichts tun -- Path("") ist das Arbeitsverzeichnis
            # und wuerde den halben Rechner einlesen.
            if not mod.get("path"):
                continue
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

        return {
            "conflicts": conflicts,
            "ignored": ignored,
            "file_owners": file_owners,
            "archive_conflicts": self._archive_conflicts(mods, archive_hashes),
        }

    @staticmethod
    def _archive_conflicts(
        mods: list[dict],
        archive_hashes: dict[str, dict[str, frozenset[int]]] | None,
    ) -> list[dict]:
        """Archive, die sich dieselben Spieldateien teilen.

        Bewusst getrennt von ``file_owners``: dort stehen echte Pfade,
        die in den Data-Tab fliessen. Hier sind es Pruefsummen -- der
        Klartextname der Datei laesst sich daraus nicht zurueckrechnen.

        Gerechnet wird ueber eine Pruefsumme->Besitzer-Abbildung und
        nicht ueber alle Archivpaare: bei 600 Archiven waeren das
        180.000 Vergleiche, so bleibt es linear.
        """
        if not archive_hashes:
            return []

        # Pruefsumme -> Liste (Mod, Archiv) in Prioritaetsreihenfolge.
        besitzer: dict[int, list[tuple[str, str]]] = {}
        for mod in mods:
            name = mod["name"]
            for rel, hashes in (archive_hashes.get(name) or {}).items():
                for h in hashes:
                    besitzer.setdefault(h, []).append((name, rel))

        # Paar -> Anzahl gemeinsamer Dateien.
        paare: dict[tuple[tuple[str, str], tuple[str, str]], int] = {}
        for eintraege in besitzer.values():
            if len(eintraege) < 2:
                continue
            for i, a in enumerate(eintraege):
                for b in eintraege[i + 1:]:
                    if a[0] == b[0]:
                        continue  # dieselbe Mod, kein Konflikt
                    if a[1] == b[1]:
                        # Gleicher Pfad in zwei Mods: das ist ein
                        # gewoehnlicher Dateikonflikt und steht schon in
                        # ``conflicts``. Sonst zaehlt das Symbol doppelt.
                        continue
                    paare[(a, b)] = paare.get((a, b), 0) + 1

        ergebnis = [
            {
                "mod_a": a[0], "archive_a": a[1],
                "mod_b": b[0], "archive_b": b[1],
                "count": anzahl,
                # Wie bei den losen Dateien: der spaetere Eintrag in der
                # uebergebenen Reihenfolge gewinnt.
                "winner": b[0],
            }
            for (a, b), anzahl in paare.items()
        ]
        ergebnis.sort(key=lambda e: (-e["count"], e["mod_a"], e["mod_b"]))
        return ergebnis
