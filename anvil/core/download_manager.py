"""Download manager for Nexus Mods files.

Uses urllib.request + QThread for HTTP downloads with progress tracking.
No QtNetwork dependency — no extra system packages needed.
Creates .meta files alongside downloaded archives (compatible with common format).
"""

from __future__ import annotations

import configparser
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse, quote, urlunparse
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, Signal, QThread

from anvil.version import APP_VERSION


CHUNK_SIZE = 64 * 1024  # 64 KB per read


class _DownloadWorker(QThread):
    """Background thread that downloads a file via urllib."""

    progress = Signal(int, int)        # (bytes_received, bytes_total)
    finished = Signal(bytes)           # empty bytes — file written to disk
    error = Signal(str)                # error message

    def __init__(self, url: str, save_path: Path, parent=None):
        super().__init__(parent)
        self._url = url
        self._save_path = save_path
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        part_path = Path(str(self._save_path) + ".part")
        try:
            parsed = urlparse(self._url)
            safe_path = quote(parsed.path, safe="/:@!$&'()*+,;=-._~")
            clean_url = urlunparse(parsed._replace(path=safe_path))
            req = urllib.request.Request(
                clean_url,
                headers={"User-Agent": f"Anvil Organizer/{APP_VERSION}"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                received = 0

                self._save_path.parent.mkdir(parents=True, exist_ok=True)
                with open(part_path, "wb") as f:
                    while True:
                        if self._cancelled:
                            self.error.emit("Abgebrochen")
                            return
                        chunk = resp.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        received += len(chunk)
                        self.progress.emit(received, total)

            # Atomic rename: .part → final path
            part_path.rename(self._save_path)
            self.finished.emit(b"")
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            # Clean up .part file on error/cancel
            if part_path.exists():
                try:
                    part_path.unlink()
                except OSError:
                    pass


@dataclass
class DownloadTask:
    """State of a single download."""

    download_id: int
    url: str
    file_name: str
    save_path: Path
    game: str = ""
    mod_id: int = 0
    file_id: int = 0
    mod_name: str = ""
    mod_version: str = ""

    # Progress
    bytes_received: int = 0
    bytes_total: int = 0
    speed_bps: float = 0.0
    status: str = "pending"  # pending, downloading, paused, finished, error
    error_message: str = ""

    # Internal
    worker: _DownloadWorker | None = field(default=None, repr=False)
    start_time: float = 0.0
    _last_bytes: int = 0
    _last_time: float = 0.0

    def progress_percent(self) -> float:
        """Return download progress as 0..100."""
        if self.bytes_total <= 0:
            return 0.0
        return min(100.0, self.bytes_received / self.bytes_total * 100.0)

    def speed_str(self) -> str:
        """Return human-readable speed string."""
        bps = self.speed_bps
        if bps < 1024:
            return f"{bps:.0f} B/s"
        if bps < 1024 * 1024:
            return f"{bps / 1024:.1f} KB/s"
        return f"{bps / (1024 * 1024):.1f} MB/s"


class DownloadManager(QObject):
    """Manages HTTP downloads with a queue (stdlib only, no QtNetwork).

    Signals:
        download_started(download_id): Download has begun.
        download_progress(download_id, percent, speed_str): Progress update.
        download_finished(download_id, save_path): Download completed.
        download_error(download_id, message): Download failed.
        all_finished(): All queued downloads are done.
    """

    download_started = Signal(int)
    download_progress = Signal(int, float, str)  # (id, percent, speed_str)
    download_finished = Signal(int, str)          # (id, save_path)
    download_error = Signal(int, str)             # (id, message)
    all_finished = Signal()

    MAX_CONCURRENT = 2

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._downloads: dict[int, DownloadTask] = {}
        self._queue: list[int] = []
        self._active: set[int] = set()
        self._next_id = 1
        self._downloads_dir: Path | None = None

    def set_downloads_dir(self, path: Path) -> None:
        """Set the target directory for downloads."""
        self._downloads_dir = path
        path.mkdir(parents=True, exist_ok=True)

    def downloads_dir(self) -> Path | None:
        """Return the current downloads directory."""
        return self._downloads_dir

    # ── Public API ────────────────────────────────────────────────────

    def enqueue(
        self,
        url: str,
        file_name: str,
        game: str = "",
        mod_id: int = 0,
        file_id: int = 0,
        mod_name: str = "",
        mod_version: str = "",
    ) -> int:
        """Add a download to the queue.

        Returns the download ID for tracking.
        """
        if not self._downloads_dir:
            return -1

        dl_id = self._next_id
        self._next_id += 1

        save_path = self._downloads_dir / file_name
        # Avoid overwriting
        counter = 1
        while save_path.exists():
            stem = Path(file_name).stem
            suffix = Path(file_name).suffix
            save_path = self._downloads_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        task = DownloadTask(
            download_id=dl_id,
            url=url,
            file_name=file_name,
            save_path=save_path,
            game=game,
            mod_id=mod_id,
            file_id=file_id,
            mod_name=mod_name,
            mod_version=mod_version,
        )
        self._downloads[dl_id] = task
        self._queue.append(dl_id)

        self._start_next()
        return dl_id

    def cancel(self, download_id: int) -> None:
        """Cancel a download (queued or active)."""
        task = self._downloads.get(download_id)
        if not task:
            return

        if task.worker:
            task.worker.cancel()
            # Worker will emit error("Abgebrochen") which handles cleanup

        task.status = "error"
        task.error_message = "Abgebrochen"
        self._active.discard(download_id)

        if download_id in self._queue:
            self._queue.remove(download_id)

        # Clean up partial file (.part or final)
        part_path = Path(str(task.save_path) + ".part")
        for p in (part_path, task.save_path):
            if p.exists() and task.bytes_received < task.bytes_total:
                try:
                    p.unlink()
                except OSError:
                    pass

        self._start_next()

    def get_task(self, download_id: int) -> DownloadTask | None:
        """Return a DownloadTask by ID."""
        return self._downloads.get(download_id)

    def active_downloads(self) -> list[DownloadTask]:
        """Return all non-finished downloads."""
        return [t for t in self._downloads.values() if t.status in ("pending", "downloading")]

    def all_tasks(self) -> list[DownloadTask]:
        """Return all download tasks."""
        return list(self._downloads.values())

    # ── Internal ──────────────────────────────────────────────────────

    def _start_next(self) -> None:
        """Start next queued download if under the concurrency limit."""
        while self._queue and len(self._active) < self.MAX_CONCURRENT:
            dl_id = self._queue.pop(0)
            task = self._downloads.get(dl_id)
            if not task:
                continue
            self._start_download(task)

    def _start_download(self, task: DownloadTask) -> None:
        """Begin downloading a task in a background thread."""
        task.status = "downloading"
        task.start_time = time.monotonic()
        task._last_time = task.start_time
        task._last_bytes = 0
        self._active.add(task.download_id)

        worker = _DownloadWorker(task.url, task.save_path, parent=self)
        task.worker = worker

        worker.progress.connect(
            lambda recv, total, t=task: self._on_progress(t, recv, total)
        )
        worker.finished.connect(lambda _, t=task: self._on_finished(t))
        worker.error.connect(lambda msg, t=task: self._on_error(t, msg))

        self.download_started.emit(task.download_id)
        worker.start()

    def _on_progress(self, task: DownloadTask, bytes_received: int, bytes_total: int) -> None:
        """Handle download progress updates."""
        task.bytes_received = bytes_received
        task.bytes_total = bytes_total

        # Calculate speed (update every 500ms)
        now = time.monotonic()
        dt = now - task._last_time
        if dt >= 0.5:
            db = bytes_received - task._last_bytes
            task.speed_bps = db / dt
            task._last_time = now
            task._last_bytes = bytes_received

        self.download_progress.emit(
            task.download_id,
            task.progress_percent(),
            task.speed_str(),
        )

    def _on_finished(self, task: DownloadTask) -> None:
        """Handle successful download completion."""
        task.worker = None
        task.status = "finished"
        self._active.discard(task.download_id)

        # Write .meta file
        self._write_meta(task)

        self.download_finished.emit(task.download_id, str(task.save_path))
        self._start_next()
        self._check_all_finished()

    def _on_error(self, task: DownloadTask, message: str) -> None:
        """Handle download error."""
        task.worker = None
        task.status = "error"
        task.error_message = message
        self._active.discard(task.download_id)

        self.download_error.emit(task.download_id, message)
        self._start_next()
        self._check_all_finished()

    def _write_meta(self, task: DownloadTask) -> None:
        """Write a .meta file next to the downloaded archive."""
        meta_path = Path(str(task.save_path) + ".meta")
        cp = configparser.ConfigParser()
        cp.optionxform = str
        cp["General"] = {
            "gameName": task.game,
            "modID": str(task.mod_id),
            "fileID": str(task.file_id),
            "url": task.url,
            "name": task.mod_name,
            "version": task.mod_version,
            "installed": "false",
            "removed": "false",
        }
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                cp.write(f)
        except OSError:
            pass

    def _check_all_finished(self) -> None:
        """Emit all_finished if no active or queued downloads remain."""
        if not self._active and not self._queue:
            self.all_finished.emit()
