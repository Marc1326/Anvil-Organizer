"""Icon-Manager: Lädt Game-/Executable-Icons von GitHub, cached lokal.

Cache-Verzeichnis: ``~/.anvil-organizer/cache/icons/``

URL-Schema (raw.githubusercontent.com)::

    icons/{game_short_name}/game.png
    icons/{game_short_name}/game_wide.jpg
    icons/{game_short_name}/executables/{exe_name}.png
"""

from __future__ import annotations

import sys
import urllib.request
import urllib.error
from pathlib import Path

from PySide6.QtCore import QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon

GITHUB_BASE = (
    "https://raw.githubusercontent.com/"
    "Marc1326/anvil-organizer-icons/main/icons"
)

_CACHE_DIR = Path.home() / ".anvil-organizer" / "cache" / "icons"

# Magic bytes for image validation
_PNG_MAGIC = b"\x89PNG"
_JPEG_MAGIC = b"\xff\xd8\xff"


# ── Placeholder generators ────────────────────────────────────────────


def placeholder_game_icon(size: int = 128) -> QPixmap:
    """Grey square with a controller-style icon."""
    pix = QPixmap(size, size)
    pix.fill(QColor("#2A2A2A"))
    p = QPainter(pix)
    p.setPen(QColor("#555555"))
    f = QFont()
    f.setPixelSize(size // 3)
    p.setFont(f)
    p.drawText(pix.rect(), 0x0084, "\U0001f3ae")  # AlignCenter
    p.end()
    return pix


def placeholder_banner(width: int = 280, height: int = 140, text: str = "") -> QPixmap:
    """Grey rectangle with game name as text."""
    pix = QPixmap(width, height)
    pix.fill(QColor("#242424"))
    if text:
        p = QPainter(pix)
        p.setPen(QColor("#808080"))
        f = QFont()
        f.setPixelSize(14)
        p.setFont(f)
        p.drawText(pix.rect(), 0x0084, text)  # AlignCenter
        p.end()
    return pix


# ── Download worker (QThread) ─────────────────────────────────────────


class _IconWorker(QThread):
    """Background thread that downloads icon files from GitHub."""

    icon_ready = Signal(str, QPixmap)  # (cache_key, pixmap)

    def __init__(self, jobs: list[tuple[str, Path, str]], parent=None):
        """
        Args:
            jobs: List of ``(url, save_path, cache_key)`` tuples.
        """
        super().__init__(parent)
        self._jobs = jobs

    def run(self) -> None:
        for url, save_path, cache_key in self._jobs:
            pix = self._download_and_load(url, save_path)
            if pix is not None:
                self.icon_ready.emit(cache_key, pix)

    @staticmethod
    def _download_and_load(url: str, save_path: Path) -> QPixmap | None:
        """Download *url*, validate magic bytes, save, return QPixmap."""
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read()
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(
                f"icon_manager: download failed {url}: {exc}",
                file=sys.stderr,
            )
            return None

        # Validate magic bytes
        if not (data[:4] == _PNG_MAGIC or data[:3] == _JPEG_MAGIC):
            print(
                f"icon_manager: invalid image data from {url}",
                file=sys.stderr,
            )
            return None

        # Save to cache
        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(data)
        except OSError as exc:
            print(
                f"icon_manager: failed to cache {save_path}: {exc}",
                file=sys.stderr,
            )

        pix = QPixmap()
        pix.loadFromData(data)
        if pix.isNull():
            return None
        return pix


# ── IconManager ───────────────────────────────────────────────────────


class IconManager:
    """Downloads game/executable icons from GitHub and caches locally."""

    def __init__(self) -> None:
        self._cache_dir = _CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, QPixmap] = {}
        self._workers: list[_IconWorker] = []

    # ── Public getters (synchronous, from cache) ──────────────────────

    def get_game_icon(self, game_short_name: str) -> QPixmap | None:
        """Return cached game icon, or None if not yet downloaded."""
        key = f"{game_short_name}/game"
        return self._get_cached(key, game_short_name, "game.png")

    def get_game_banner(self, game_short_name: str) -> QPixmap | None:
        """Return cached game banner, or None if not yet downloaded."""
        key = f"{game_short_name}/banner"
        return self._get_cached(key, game_short_name, "game_wide.jpg")

    def get_executable_icon(
        self, game_short_name: str, exe_binary: str,
    ) -> QPixmap | None:
        """Return cached executable icon, or None if not yet downloaded.

        Args:
            game_short_name: e.g. ``cyberpunk2077``
            exe_binary: Binary path from plugin, e.g. ``bin/x64/Cyberpunk2077.exe``
                        Only the basename is used for lookup.
        """
        basename = Path(exe_binary).name
        key = f"{game_short_name}/exe/{basename}"
        return self._get_cached(
            key, game_short_name, f"executables/{basename}.png",
        )

    # ── Preload (async) ───────────────────────────────────────────────

    def preload_icons(
        self,
        game_short_name: str,
        exe_binaries: list[str] | None = None,
    ) -> _IconWorker | None:
        """Start background download for all icons of a game.

        Args:
            game_short_name: e.g. ``cyberpunk2077``
            exe_binaries: List of binary paths from plugin.executables().

        Returns:
            The worker thread (caller connects ``icon_ready``), or None
            if everything is already cached.
        """
        jobs: list[tuple[str, Path, str]] = []

        # Game icon
        key_game = f"{game_short_name}/game"
        if key_game not in self._mem:
            path_game = self._cache_dir / game_short_name / "game.png"
            if not path_game.is_file():
                url = f"{GITHUB_BASE}/{game_short_name}/game.png"
                jobs.append((url, path_game, key_game))

        # Banner
        key_banner = f"{game_short_name}/banner"
        if key_banner not in self._mem:
            path_banner = self._cache_dir / game_short_name / "game_wide.jpg"
            if not path_banner.is_file():
                url = f"{GITHUB_BASE}/{game_short_name}/game_wide.jpg"
                jobs.append((url, path_banner, key_banner))

        # Executable icons
        for binary in exe_binaries or []:
            basename = Path(binary).name
            key_exe = f"{game_short_name}/exe/{basename}"
            if key_exe not in self._mem:
                path_exe = (
                    self._cache_dir / game_short_name
                    / "executables" / f"{basename}.png"
                )
                if not path_exe.is_file():
                    url = (
                        f"{GITHUB_BASE}/{game_short_name}"
                        f"/executables/{basename}.png"
                    )
                    jobs.append((url, path_exe, key_exe))

        if not jobs:
            return None

        worker = _IconWorker(jobs)
        # Store reference so it doesn't get garbage collected
        self._workers.append(worker)
        worker.finished.connect(lambda w=worker: self._workers.remove(w))
        return worker

    # ── Cache management ──────────────────────────────────────────────

    def clear_cache(self) -> None:
        """Delete the entire icon cache (disk + memory)."""
        self._mem.clear()
        import shutil
        if self._cache_dir.is_dir():
            shutil.rmtree(self._cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Internal ──────────────────────────────────────────────────────

    def _get_cached(
        self, key: str, game_short_name: str, rel_path: str,
    ) -> QPixmap | None:
        """Look up memory cache, then disk cache."""
        if key in self._mem:
            return self._mem[key]

        disk_path = self._cache_dir / game_short_name / rel_path
        if disk_path.is_file():
            pix = QPixmap(str(disk_path))
            if not pix.isNull():
                self._mem[key] = pix
                return pix

        return None

    def store_pixmap(self, key: str, pixmap: QPixmap) -> None:
        """Store a downloaded pixmap in the memory cache.

        Called by the UI when ``icon_ready`` fires.
        """
        self._mem[key] = pixmap
