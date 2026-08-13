"""Central mod file index with filesystem caching.

Stores file lists for every mod in a JSON cache file
(``.modindex.json``) inside the instance directory.  On subsequent
loads only mods whose directory tree changed are re-scanned: the tree
is fingerprinted over every directory, the per-file ``stat`` calls and
the JSON rebuild are what the cache saves.

Note: overwriting a file in place leaves every directory timestamp
untouched.  The file list stays correct, but the cached size does not.

Usage::

    idx = ModIndex(instance_path)
    idx.rebuild()                     # scan changed mods only
    files = idx.get_file_list("MyMod")   # cached list
    count, size = idx.get_stats("MyMod") # cached counts

The deployer, conflict scanner and mod-entry builder all consume
this index instead of calling ``rglob("*")`` themselves.
"""

from __future__ import annotations

import json
import os
import sys
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path


_CACHE_VERSION = 3
_CACHE_FILENAME = ".modindex.json"


def _fingerprint(mod_dir: Path) -> str | None:
    """Abdruck ueber alle Ordner einer Mod, oder ``None`` bei Lesefehler.

    Die Wurzelzeit allein reicht nicht (eine Aenderung im Unterordner
    bliebe unsichtbar), das Maximum aller Zeiten auch nicht (ein falsch
    datierter Ordner aus der Zukunft nagelt es fest). Deshalb eine
    Pruefsumme -- sie schlaegt in jede Richtung an.

    Ein an Ort und Stelle ueberschriebener Dateiinhalt bleibt unsichtbar.
    """
    h = hashlib.blake2b(digest_size=8)
    leer = True
    fehler: list[OSError] = []
    try:
        # Ein unlesbarer Unterordner darf nicht einfach uebersprungen werden:
        # seine Dateien fehlen dann im Index, ohne dass es jemand merkt.
        for ordner, unter, _dateien in os.walk(str(mod_dir), onerror=fehler.append):
            unter.sort()  # gleiche Reihenfolge bei jedem Lauf
            rel = os.path.relpath(ordner, str(mod_dir))
            h.update(f"{rel}\x00{os.stat(ordner).st_mtime_ns}\x01".encode(
                "utf-8", "surrogateescape"))
            leer = False
    except OSError:
        return None

    return None if leer or fehler else h.hexdigest()


def _als_zahl(wert) -> int:
    """Groessenangabe aus einer moeglicherweise beschaedigten Datei."""
    try:
        return max(0, int(wert))
    except (TypeError, ValueError):
        return 0


@dataclass
class _ModCache:
    """Cached data for a single mod directory."""
    fingerprint: str = ""
    files: list[dict] = field(default_factory=list)
    # Aggregates (pre-computed for fast access)
    file_count: int = 0
    total_size: int = 0
    # Archivpfad -> Pruefsummen der enthaltenen Spieldateien. Nur
    # gefuellt, wenn das Spiel-Plugin gepackte Archive lesen kann.
    archives: dict[str, list[int]] = field(default_factory=dict)


class ModIndex:
    """Central file index for all mods in an instance.

    Args:
        instance_path: Root of the game instance
            (e.g. ``~/.anvil-organizer/instances/Cyberpunk 2077/``).
    """

    def __init__(
        self,
        instance_path: Path,
        mods_path: Path | None = None,
        game_plugin=None,
    ) -> None:
        self._instance_path = instance_path
        self._mods_path = mods_path if mods_path is not None else instance_path / ".mods"
        self._cache_path = instance_path / _CACHE_FILENAME
        self._index: dict[str, _ModCache] = {}
        self._dirty = False
        self._archive_suffixes: tuple[str, ...] = ()
        self._archive_reader = None
        if game_plugin is not None:
            endungen = getattr(game_plugin, "GameArchiveSuffixes", []) or []
            leser = getattr(game_plugin, "read_archive_hashes", None)
            if endungen and callable(leser):
                self._archive_suffixes = tuple(e.lower() for e in endungen)
                self._archive_reader = leser

    # ── Public API ─────────────────────────────────────────────────

    def rebuild(self) -> float:
        """Rebuild the index, re-scanning only changed mods.

        Returns:
            Wall-clock seconds taken for the rebuild.
        """
        t0 = time.monotonic()

        # Load existing cache from disk
        self._load_cache()

        if not self._mods_path.is_dir():
            self._index.clear()
            self._save_cache()
            return time.monotonic() - t0

        # Discover current mod folders
        on_disk: set[str] = set()
        try:
            for entry in os.scandir(str(self._mods_path)):
                # follow symlinks: a mod folder may be a symlink to a
                # repo checkout.  scan_mods_directory() accepts those,
                # so the index has to as well -- otherwise the mod shows
                # up in the list but deploys nothing.
                if entry.is_dir():
                    on_disk.add(entry.name)
        except OSError as exc:
            print(
                f"modindex: failed to scan {self._mods_path}: {exc}",
                file=sys.stderr,
            )
            return time.monotonic() - t0

        # Remove deleted mods from cache
        stale = set(self._index.keys()) - on_disk
        for name in stale:
            del self._index[name]
            self._dirty = True

        # Check each mod for changes
        for name in on_disk:
            mod_dir = self._mods_path / name
            abdruck = _fingerprint(mod_dir)
            if abdruck is None:
                continue

            cached = self._index.get(name)
            if cached is not None and cached.fingerprint == abdruck:
                continue  # Cache hit -- skip re-scan

            # Cache miss -- re-scan this mod
            self._scan_mod(name, mod_dir, abdruck)
            self._dirty = True

        if self._dirty:
            self._save_cache()
            self._dirty = False

        elapsed = time.monotonic() - t0
        total_mods = len(self._index)
        cached_count = total_mods - len(stale)
        print(
            f"[ModIndex] rebuild: {total_mods} mods, "
            f"{elapsed:.3f}s",
            flush=True,
        )
        return elapsed

    def get_file_list(self, mod_name: str) -> list[dict]:
        """Return cached file list for *mod_name*.

        Each entry is a dict with keys ``rel`` (relative path as string)
        and ``size`` (int, bytes).

        Returns an empty list if the mod is not in the index.
        """
        cached = self._index.get(mod_name)
        if cached is None:
            return []
        return cached.files

    def get_archives(self, mod_name: str) -> dict[str, frozenset[int]]:
        """Pruefsummen je gepacktem Archiv von *mod_name*.

        Leer, wenn die Mod keine Archive hat oder das Spiel-Plugin sie
        nicht lesen kann.
        """
        cached = self._index.get(mod_name)
        if cached is None or not cached.archives:
            return {}
        return {rel: frozenset(werte) for rel, werte in cached.archives.items()}

    def get_stats(self, mod_name: str) -> tuple[int, int]:
        """Return ``(file_count, total_size)`` for *mod_name*.

        Returns ``(0, 0)`` if the mod is not in the index.
        """
        cached = self._index.get(mod_name)
        if cached is None:
            return 0, 0
        return cached.file_count, cached.total_size

    def invalidate(self, mod_name: str, save: bool = True) -> None:
        """Remove *mod_name* from the cache.

        The next :meth:`rebuild` will re-scan this mod. Mit ``save=False``
        bleibt das Schreiben :meth:`flush` ueberlassen -- fuer Aufrufer in
        einer Schleife, die sonst die ganze Datei pro Mod neu schrieben.
        """
        if mod_name in self._index:
            del self._index[mod_name]
            self._dirty = True
            if save:
                self._save_cache()
                self._dirty = False

    def invalidate_and_rescan(self, mod_name: str) -> None:
        """Immediately invalidate and re-scan *mod_name*.

        Useful after install/rename operations where the caller
        needs up-to-date data right away.
        """
        mod_dir = self._mods_path / mod_name
        if not mod_dir.is_dir():
            self.invalidate(mod_name)
            return
        abdruck = _fingerprint(mod_dir)
        if abdruck is None:
            self.invalidate(mod_name)
            return
        self._scan_mod(mod_name, mod_dir, abdruck)
        self._dirty = True
        self._save_cache()
        self._dirty = False

    def refresh(self, mod_name: str) -> bool | None:
        """Liest *mod_name* neu ein, falls sich der Ordner geaendert hat.

        Fuer Aufrufer, die mitten in einer Schleife stehen: gespeichert
        wird hier nicht, das erledigt :meth:`flush` einmal am Ende. Sonst
        schriebe der Deployer die ganze Cache-Datei pro Mod neu.

        Returns:
            True, wenn neu eingelesen wurde. False, wenn unveraendert.
            ``None``, wenn der Ordner nicht lesbar war -- dann weiss
            niemand, ob die Liste noch stimmt, und der Aufrufer muss es
            melden statt stillschweigend weiterzumachen.
        """
        mod_dir = self._mods_path / mod_name
        if not mod_dir.is_dir():
            if mod_name in self._index:
                del self._index[mod_name]
                self._dirty = True
                return True
            return False

        abdruck = _fingerprint(mod_dir)
        if abdruck is None:
            return None

        cached = self._index.get(mod_name)
        if cached is not None and cached.fingerprint == abdruck:
            return False

        self._scan_mod(mod_name, mod_dir, abdruck)
        self._dirty = True
        return True

    def flush(self) -> None:
        """Schreibt ausstehende Aenderungen einmal auf die Platte."""
        if self._dirty:
            self._save_cache()
            self._dirty = False

    def rename(self, old_name: str, new_name: str) -> None:
        """Update the cache after a mod rename."""
        cached = self._index.pop(old_name, None)
        if cached is not None:
            self._index[new_name] = cached
            self._dirty = True
            self._save_cache()
            self._dirty = False

    def clear(self) -> None:
        """Delete the cache file and clear in-memory data.

        The next :meth:`rebuild` will do a full scan.
        """
        self._index.clear()
        try:
            self._cache_path.unlink(missing_ok=True)
        except OSError:
            pass

    def mod_count(self) -> int:
        """Return number of mods in the index."""
        return len(self._index)

    def mod_names(self) -> list[str]:
        """Return the names of all indexed mods."""
        return list(self._index.keys())

    # ── Internal ──────────────────────────────────────────────────

    def _scan_mod(
        self, name: str, mod_dir: Path, fingerprint: str,
    ) -> None:
        """Scan *mod_dir* and update the index entry."""
        files: list[dict] = []
        total_size = 0
        file_count = 0
        archives: dict[str, list[int]] = {}

        try:
            for entry in self._walk_files(mod_dir):
                rel = entry.relative_to(mod_dir).as_posix()
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = 0
                files.append({"rel": rel, "size": size})
                total_size += size
                file_count += 1

                if self._archive_reader is not None and rel.lower().endswith(
                    self._archive_suffixes,
                ):
                    # Ein kaputtes Archiv darf den Scan nicht abbrechen --
                    # sonst faellt die ganze Mod aus dem Index.
                    try:
                        hashes = self._archive_reader(entry)
                    except Exception as exc:  # noqa: BLE001
                        print(
                            f"modindex: {rel} nicht lesbar: {exc}",
                            file=sys.stderr,
                        )
                        hashes = None
                    if hashes:
                        archives[rel] = sorted(hashes)
        except OSError as exc:
            print(
                f"modindex: failed to scan {mod_dir}: {exc}",
                file=sys.stderr,
            )

        self._index[name] = _ModCache(
            fingerprint=fingerprint,
            files=files,
            file_count=file_count,
            total_size=total_size,
            archives=archives,
        )

    @staticmethod
    def _walk_files(root: Path):
        """Yield all file paths under *root* recursively.

        Uses ``os.scandir`` for performance (faster than ``rglob``).
        """
        stack = [root]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(str(current)) as it:
                    for entry in it:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=True):
                            yield Path(entry.path)
            except OSError:
                pass

    def _load_cache(self) -> None:
        """Load the cache file from disk."""
        if not self._cache_path.is_file():
            self._index.clear()
            return

        try:
            text = self._cache_path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(
                f"modindex: cache corrupt, will rebuild: {exc}",
                file=sys.stderr,
            )
            self._index.clear()
            self._dirty = True
            return

        if not isinstance(data, dict) or data.get("version") != _CACHE_VERSION:
            self._index.clear()
            self._dirty = True
            return

        # Wurde der Cache ohne Archiv-Leser gebaut (z.B. beim Neuaufbau
        # nach einem Umzug), fehlen die Pruefsummen -- und "nie gelesen"
        # sieht im Cache aus wie "hat keine Archive". Dann lieber neu
        # einlesen, sonst faellt die Archiv-Konfliktanzeige still aus.
        gebaut_mit = data.get("archive_suffixes")
        if not isinstance(gebaut_mit, list):
            gebaut_mit = []
        if [str(e) for e in gebaut_mit] != list(self._archive_suffixes):
            self._index.clear()
            self._dirty = True
            return

        mods = data.get("mods")
        if not isinstance(mods, dict):
            self._index.clear()
            self._dirty = True
            return
        for name, info in mods.items():
            if not isinstance(info, dict):
                continue
            # Unbrauchbare Eintraege hier wegwerfen und nicht bei jedem
            # Leser einzeln: der Konfliktscanner griff blank auf ``rel``
            # zu und riss an einer beschaedigten Datei komplett ab.
            roh = info.get("files")
            dateien = [
                {"rel": f["rel"], "size": _als_zahl(f.get("size"))}
                for f in (roh if isinstance(roh, list) else [])
                if isinstance(f, dict) and isinstance(f.get("rel"), str) and f["rel"]
            ]
            if not isinstance(roh, list) or len(dateien) != len(roh):
                # Die Datei war beschaedigt. Der gemerkte Abdruck taugt
                # dann nicht mehr -- sonst gilt die lueckenhafte Liste als
                # aktuell und die fehlenden Dateien kaemen nie ins Spiel.
                self._index[name] = _ModCache()
                self._dirty = True
                continue
            roh_arch = info.get("archives")
            archives: dict[str, list[int]] = {}
            if isinstance(roh_arch, dict):
                for pfad, werte in roh_arch.items():
                    if isinstance(pfad, str) and isinstance(werte, list):
                        archives[pfad] = [w for w in werte if isinstance(w, int)]
            self._index[name] = _ModCache(
                fingerprint=str(info.get("fingerprint", "")),
                files=dateien,
                file_count=len(dateien),
                total_size=sum(f["size"] for f in dateien),
                archives=archives,
            )

    def _save_cache(self) -> None:
        """Write the cache to disk."""
        mods = {}
        for name, cached in self._index.items():
            eintrag = {
                "fingerprint": cached.fingerprint,
                "files": cached.files,
                "file_count": cached.file_count,
                "total_size": cached.total_size,
            }
            if cached.archives:
                eintrag["archives"] = cached.archives
            mods[name] = eintrag

        data = {
            "version": _CACHE_VERSION,
            "archive_suffixes": list(self._archive_suffixes),
            "mods": mods,
        }

        try:
            self._cache_path.write_text(
                json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
        except OSError as exc:
            print(
                f"modindex: failed to write cache: {exc}",
                file=sys.stderr,
            )
