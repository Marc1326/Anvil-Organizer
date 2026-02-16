"""Background update checker for Anvil Organizer.

Checks GitHub releases API for newer versions without blocking the UI.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
import ssl

from PySide6.QtCore import QObject, Signal, QThread

from anvil.version import APP_VERSION


GITHUB_API_URL = "https://api.github.com/repos/Marc1326/Anvil-Organizer/releases/latest"
RELEASES_URL = "https://github.com/Marc1326/Anvil-Organizer/releases/latest"
REQUEST_TIMEOUT = 5  # seconds


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse version string like 'v0.1.0' or '0.1.0' into tuple (0, 1, 0)."""
    # Remove leading 'v' if present
    v = version_str.lstrip("vV")
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0, 0, 0)


def _is_newer(remote: str, local: str) -> bool:
    """Return True if remote version is newer than local."""
    return _parse_version(remote) > _parse_version(local)


class _UpdateWorker(QThread):
    """Background thread for GitHub API request."""

    finished = Signal(str, str)  # (version, url) or ("", "") on error/no update

    def __init__(self, local_version: str):
        super().__init__()
        self._local_version = local_version

    def run(self):
        try:
            # Create SSL context that works on most systems
            ctx = ssl.create_default_context()

            req = urllib.request.Request(
                GITHUB_API_URL,
                headers={
                    "User-Agent": f"Anvil Organizer/{self._local_version}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            tag_name = data.get("tag_name", "")
            html_url = data.get("html_url", RELEASES_URL)

            if tag_name and _is_newer(tag_name, self._local_version):
                self.finished.emit(tag_name, html_url)
            else:
                self.finished.emit("", "")

        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
                TimeoutError, OSError):
            # Network errors are silently ignored
            self.finished.emit("", "")


class UpdateChecker(QObject):
    """Checks for updates on GitHub in the background.

    Usage:
        checker = UpdateChecker()
        checker.update_available.connect(on_update)
        checker.check()

    Signals:
        update_available(version: str, url: str) - Emitted when a newer version exists.
    """

    update_available = Signal(str, str)  # (version, url)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: _UpdateWorker | None = None

    def check(self):
        """Start background check for updates."""
        if self._worker is not None and self._worker.isRunning():
            return  # Already checking

        self._worker = _UpdateWorker(APP_VERSION)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_finished(self, version: str, url: str):
        """Handle worker result."""
        if version and url:
            self.update_available.emit(version, url)

        # Cleanup
        if self._worker:
            self._worker.deleteLater()
            self._worker = None
