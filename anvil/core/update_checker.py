"""Git-based self-update for Anvil Organizer.

Checks for new commits on origin/main via git fetch, and can apply
updates via git pull --ff-only.  Optionally re-installs Python
dependencies when requirements.txt changes.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal


# Project root: two levels up from anvil/core/update_checker.py
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_GIT_TIMEOUT = 10  # seconds


def _git(*args: str, cwd: Path = _PROJECT_ROOT) -> subprocess.CompletedProcess:
    """Run a git command with standard safety flags."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
    )


def _is_git_repo() -> bool:
    """Return True if the project root contains a .git directory."""
    return (_PROJECT_ROOT / ".git").is_dir()


def _file_hash(path: Path) -> str:
    """Return SHA-256 hex digest of a file, or empty string if missing."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


# ── Workers ───────────────────────────────────────────────────────────


class _GitCheckWorker(QThread):
    """Background thread: git fetch + count new commits."""

    finished = Signal(int, str)  # (commit_count, changelog)

    def run(self) -> None:
        try:
            if not _is_git_repo():
                self.finished.emit(0, "")
                return

            # Fetch latest from remote
            result = _git("fetch", "origin", "main")
            if result.returncode != 0:
                self.finished.emit(0, "")
                return

            # Count commits ahead on remote
            result = _git("rev-list", "HEAD..origin/main", "--count")
            if result.returncode != 0:
                self.finished.emit(0, "")
                return

            count = int(result.stdout.strip() or "0")
            if count == 0:
                self.finished.emit(0, "")
                return

            # Build changelog from new commits
            result = _git("log", "--oneline", "HEAD..origin/main")
            changelog = result.stdout.strip() if result.returncode == 0 else ""

            self.finished.emit(count, changelog)

        except (subprocess.TimeoutExpired, OSError, ValueError):
            self.finished.emit(0, "")


class _GitPullWorker(QThread):
    """Background thread: check dirty tree, git pull, optional pip."""

    finished = Signal(bool, bool)  # (success, pip_ran)
    progress = Signal(str)         # status messages

    def run(self) -> None:
        try:
            if not _is_git_repo():
                self.finished.emit(False, False)
                return

            # Check for uncommitted changes
            self.progress.emit("Checking working tree...")
            result = _git("status", "--porcelain")
            if result.returncode != 0:
                self.progress.emit("git status failed")
                self.finished.emit(False, False)
                return

            if result.stdout.strip():
                self.progress.emit("dirty_tree")
                self.finished.emit(False, False)
                return

            # Hash requirements.txt BEFORE pull
            req_path = _PROJECT_ROOT / "requirements.txt"
            hash_before = _file_hash(req_path)

            # Pull with fast-forward only
            self.progress.emit("Pulling updates...")
            result = _git("pull", "origin", "main", "--ff-only")
            if result.returncode != 0:
                self.progress.emit(f"git pull failed: {result.stderr.strip()}")
                self.finished.emit(False, False)
                return

            # Hash requirements.txt AFTER pull
            hash_after = _file_hash(req_path)
            pip_ran = False

            if hash_before != hash_after and hash_after:
                self.progress.emit("requirements.txt changed — installing dependencies...")
                try:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-r", str(req_path)],
                        cwd=_PROJECT_ROOT,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    pip_ran = True
                except (subprocess.TimeoutExpired, OSError):
                    self.progress.emit("pip install failed (timeout or OS error)")

            self.progress.emit("Update applied successfully")
            self.finished.emit(True, pip_ran)

        except (subprocess.TimeoutExpired, OSError):
            self.progress.emit("Update failed (timeout or OS error)")
            self.finished.emit(False, False)


# ── Public API ────────────────────────────────────────────────────────


class UpdateChecker(QObject):
    """Git-based update checker and applier.

    Usage:
        checker = UpdateChecker()
        checker.update_available.connect(on_updates)
        checker.update_applied.connect(on_applied)
        checker.update_progress.connect(on_status)
        checker.check()
        # later:
        checker.apply_update()

    Signals:
        update_available(count, changelog) - New commits found on origin/main.
        update_applied(success, pip_ran) - Pull completed (or failed).
        update_progress(message) - Status text during apply.
    """

    update_available = Signal(int, str)    # (commit_count, changelog)
    update_applied = Signal(bool, bool)    # (success, pip_ran)
    update_progress = Signal(str)          # status messages

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._check_worker: _GitCheckWorker | None = None
        self._pull_worker: _GitPullWorker | None = None

    # ── Check ─────────────────────────────────────────────────────

    def check(self) -> None:
        """Start background check for new commits on origin/main."""
        if not _is_git_repo():
            return
        if self._check_worker is not None and self._check_worker.isRunning():
            return

        self._check_worker = _GitCheckWorker()
        self._check_worker.finished.connect(self._on_check_finished)
        self._check_worker.start()

    def _on_check_finished(self, count: int, changelog: str) -> None:
        """Handle check worker result."""
        if count > 0:
            self.update_available.emit(count, changelog)

        if self._check_worker:
            self._check_worker.deleteLater()
            self._check_worker = None

    # ── Apply ─────────────────────────────────────────────────────

    def apply_update(self) -> None:
        """Start background git pull to apply the update."""
        if not _is_git_repo():
            return
        if self._pull_worker is not None and self._pull_worker.isRunning():
            return

        self._pull_worker = _GitPullWorker()
        self._pull_worker.progress.connect(self._on_pull_progress)
        self._pull_worker.finished.connect(self._on_pull_finished)
        self._pull_worker.start()

    def _on_pull_progress(self, message: str) -> None:
        """Forward pull worker status messages."""
        self.update_progress.emit(message)

    def _on_pull_finished(self, success: bool, pip_ran: bool) -> None:
        """Handle pull worker result."""
        self.update_applied.emit(success, pip_ran)

        if self._pull_worker:
            self._pull_worker.deleteLater()
            self._pull_worker = None
