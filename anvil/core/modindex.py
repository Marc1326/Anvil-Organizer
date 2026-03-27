"""Central mod file index with filesystem caching.

Stores file lists for every mod in a JSON cache file
(``.modindex.json``) inside the instance directory.  On subsequent
loads only mods whose directory ``st_mtime`` changed are re-scanned,
making startup and deploy dramatically faster for large mod setups.

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
import time
from dataclasses import dataclass, field
from pathlib import Path


_CACHE_VERSION = 1
_CACHE_FILENAME = ".modindex.json"


@dataclass
class _ModCache:
    """Cached data for a single mod directory."""
    mtime: float = 0.0
    files: list[dict] = field(default_factory=list)
    # Aggregates (pre-computed for fast access)
    file_count: int = 0
    total_size: int = 0


class ModIndex:
    """Central file index for all mods in an instance.

    Args:
        instance_path: Root of the game instance
            (e.g. ``~/.anvil-organizer/instances/Cyberpunk 2077/``).
    """

    def __init__(self, instance_path: Path) -> None:
        self._instance_path = instance_path
        self._mods_path = instance_path / ".mods"
        self._cache_path = instance_path / _CACHE_FILENAME
        self._index: dict[str, _ModCache] = {}
        self._dirty = False

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
                if entry.is_dir(follow_symlinks=False):
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
            try:
                current_mtime = os.stat(str(mod_dir)).st_mtime
            except OSError:
                continue

            cached = self._index.get(name)
            if cached is not None and cached.mtime == current_mtime:
                continue  # Cache hit -- skip re-scan

            # Cache miss -- re-scan this mod
            self._scan_mod(name, mod_dir, current_mtime)
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

    def get_stats(self, mod_name: str) -> tuple[int, int]:
        """Return ``(file_count, total_size)`` for *mod_name*.

        Returns ``(0, 0)`` if the mod is not in the index.
        """
        cached = self._index.get(mod_name)
        if cached is None:
            return 0, 0
        return cached.file_count, cached.total_size

    def invalidate(self, mod_name: str) -> None:
        """Remove *mod_name* from the cache.

        The next :meth:`rebuild` will re-scan this mod.
        """
        if mod_name in self._index:
            del self._index[mod_name]
            self._dirty = True
            self._save_cache()
            self._dirty = False

    def invalidate_and_rescan(self, mod_name: str) -> None:
        """Immediately invalidate and re-scan *mod_name*.

        Useful after install/rename operations where the caller
        needs up-to-date data right away.
        """
        mod_dir = self._mods_path / mod_name
        if mod_dir.is_dir():
            try:
                mtime = os.stat(str(mod_dir)).st_mtime
            except OSError:
                self.invalidate(mod_name)
                return
            self._scan_mod(mod_name, mod_dir, mtime)
            self._dirty = True
            self._save_cache()
            self._dirty = False
        else:
            self.invalidate(mod_name)

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

    # ── Internal ──────────────────────────────────────────────────

    def _scan_mod(
        self, name: str, mod_dir: Path, mtime: float,
    ) -> None:
        """Scan *mod_dir* and update the index entry."""
        files: list[dict] = []
        total_size = 0
        file_count = 0

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
        except OSError as exc:
            print(
                f"modindex: failed to scan {mod_dir}: {exc}",
                file=sys.stderr,
            )

        self._index[name] = _ModCache(
            mtime=mtime,
            files=files,
            file_count=file_count,
            total_size=total_size,
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

        mods = data.get("mods", {})
        for name, info in mods.items():
            if not isinstance(info, dict):
                continue
            self._index[name] = _ModCache(
                mtime=info.get("mtime", 0.0),
                files=info.get("files", []),
                file_count=info.get("file_count", 0),
                total_size=info.get("total_size", 0),
            )

    def _save_cache(self) -> None:
        """Write the cache to disk."""
        mods = {}
        for name, cached in self._index.items():
            mods[name] = {
                "mtime": cached.mtime,
                "files": cached.files,
                "file_count": cached.file_count,
                "total_size": cached.total_size,
            }

        data = {
            "version": _CACHE_VERSION,
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
