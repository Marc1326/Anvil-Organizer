"""Nexus Mods API v1 client using urllib.request + QThread.

No external dependencies — uses only Python stdlib for HTTP.
Runs requests in background threads so the GUI stays responsive.

Provides async access to the Nexus Mods REST API for:
- API key validation and user info
- Mod metadata retrieval
- File listing and download link generation

Rate limits are tracked from response headers.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from urllib.parse import urlencode

from PySide6.QtCore import QObject, Signal, QThread

from anvil.version import APP_VERSION


API_BASE = "https://api.nexusmods.com/v1"


class _ApiWorker(QThread):
    """Background thread that performs a single HTTP GET request."""

    finished = Signal(str, int, dict, bytes)  # (tag, status_code, headers, body)
    error = Signal(str, str)                  # (tag, error_message)

    def __init__(self, url: str, headers: dict[str, str], tag: str, parent=None):
        super().__init__(parent)
        self._url = url
        self._headers = headers
        self._tag = tag

    def run(self) -> None:
        try:
            req = urllib.request.Request(self._url, headers=self._headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                headers = {k.lower(): v for k, v in resp.getheaders()}
                body = resp.read()
                self.finished.emit(self._tag, status, headers, body)
        except urllib.error.HTTPError as exc:
            status = exc.code
            headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
            body = b""
            try:
                body = exc.read()
            except Exception:
                pass
            self.finished.emit(self._tag, status, headers, body)
        except Exception as exc:
            self.error.emit(self._tag, str(exc))


class _ApiPostWorker(QThread):
    """Background thread that performs a single HTTP POST request."""

    finished = Signal(str, int, dict, bytes)  # (tag, status_code, headers, body)
    error = Signal(str, str)                  # (tag, error_message)

    def __init__(self, url: str, headers: dict[str, str], body: bytes, tag: str, parent=None):
        super().__init__(parent)
        self._url = url
        self._headers = headers
        self._body = body
        self._tag = tag

    def run(self) -> None:
        try:
            req = urllib.request.Request(self._url, data=self._body, headers=self._headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                headers = {k.lower(): v for k, v in resp.getheaders()}
                body = resp.read()
                self.finished.emit(self._tag, status, headers, body)
        except urllib.error.HTTPError as exc:
            status = exc.code
            headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
            body = b""
            try:
                body = exc.read()
            except Exception:
                pass
            self.finished.emit(self._tag, status, headers, body)
        except Exception as exc:
            self.error.emit(self._tag, str(exc))


class NexusAPI(QObject):
    """Async Nexus Mods API v1 client (stdlib only, no QtNetwork).

    Signals:
        request_finished(endpoint, data): Successful JSON response.
        request_error(endpoint, message): Error message.
        rate_limit_updated(daily_remaining, hourly_remaining): After each response.
        user_validated(user_info): After successful validate_key().
    """

    request_finished = Signal(str, object)    # (endpoint, parsed JSON)
    request_error = Signal(str, str)          # (endpoint, error message)
    rate_limit_updated = Signal(int, int)     # (daily_remaining, hourly_remaining)
    user_validated = Signal(dict)             # user info dict

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._api_key: str = ""
        self._daily_remaining: int = -1
        self._hourly_remaining: int = -1
        self._workers: list[_ApiWorker] = []  # prevent GC

    # ── Configuration ─────────────────────────────────────────────────

    def set_api_key(self, key: str) -> None:
        """Set the API key for all future requests."""
        self._api_key = key.strip()

    def api_key(self) -> str:
        """Return the current API key."""
        return self._api_key

    def has_api_key(self) -> bool:
        """Return True if an API key is set."""
        return bool(self._api_key)

    def daily_remaining(self) -> int:
        """Return last known daily rate limit remaining (-1 if unknown)."""
        return self._daily_remaining

    def hourly_remaining(self) -> int:
        """Return last known hourly rate limit remaining (-1 if unknown)."""
        return self._hourly_remaining

    # ── Public API methods ────────────────────────────────────────────

    def validate_key(self) -> None:
        """Validate the current API key.  GET /users/validate.json

        On success, emits user_validated(dict) with keys:
            user_id, key, name, is_premium, is_supporter, email, profile_url
        """
        self._get("/users/validate.json", tag="validate")

    def get_mod_info(self, game: str, mod_id: int) -> None:
        """Fetch mod metadata.  GET /games/{game}/mods/{mod_id}.json"""
        self._get(f"/games/{game}/mods/{mod_id}.json", tag=f"mod_info:{game}:{mod_id}")

    def query_mod_info(self, game: str, mod_id: int) -> None:
        """Fetch mod metadata for Query Info feature.
        Uses separate tag prefix to avoid collision with NXM download flow.
        """
        self._get(f"/games/{game}/mods/{mod_id}.json",
                  tag=f"query_mod_info:{game}:{mod_id}")

    def update_check_mod(self, game: str, mod_id: int) -> None:
        """Fetch mod metadata for post-install update check.
        Uses 'update_check:' tag prefix to distinguish from other queries.
        """
        self._get(f"/games/{game}/mods/{mod_id}.json",
                  tag=f"update_check:{game}:{mod_id}")

    def update_check_framework(self, game: str, mod_id: int, name: str) -> None:
        """Fetch mod metadata for a framework update check."""
        self._get(f"/games/{game}/mods/{mod_id}.json",
                  tag=f"fw_update:{name}")

    def get_mod_files(self, game: str, mod_id: int) -> None:
        """Fetch file list for a mod.  GET /games/{game}/mods/{mod_id}/files.json"""
        self._get(
            f"/games/{game}/mods/{mod_id}/files.json",
            tag=f"mod_files:{game}:{mod_id}",
        )

    def get_download_links(
        self,
        game: str,
        mod_id: int,
        file_id: int,
        key: str | None = None,
        expires: str | None = None,
    ) -> None:
        """Get download URLs for a file.

        GET /games/{game}/mods/{mod_id}/files/{file_id}/download_link.json

        For free users with an nxm:// link, pass key and expires.
        Premium users can call without key/expires.
        """
        path = f"/games/{game}/mods/{mod_id}/files/{file_id}/download_link.json"
        params = {}
        if key:
            params["key"] = key
        if expires:
            params["expires"] = expires
        if params:
            path += "?" + urlencode(params)
        self._get(path, tag=f"download_link:{game}:{mod_id}:{file_id}")

    def get_game_info(self, game: str) -> None:
        """Fetch game info including categories.  GET /games/{game}.json"""
        self._get(f"/games/{game}.json", tag=f"game_categories:{game}")

    # ── Internal ──────────────────────────────────────────────────────

    def _post(self, path: str, body: dict, tag: str = "") -> None:
        """Send a POST request via a background QThread."""
        if not self._api_key:
            self.request_error.emit(tag, "Kein API-Schlüssel gesetzt.")
            return

        url = API_BASE + path
        headers = {
            "apikey": self._api_key,
            "User-Agent": f"Anvil Organizer/{APP_VERSION}",
            "Content-Type": "application/json",
        }
        encoded = json.dumps(body).encode("utf-8")

        worker = _ApiPostWorker(url, headers, encoded, tag, parent=self)
        worker.finished.connect(self._on_worker_finished)
        worker.error.connect(self._on_worker_error)
        worker.finished.connect(lambda *_: self._cleanup_worker(worker))
        worker.error.connect(lambda *_: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def _get(self, path: str, tag: str = "") -> None:
        """Send a GET request via a background QThread."""
        if not self._api_key:
            self.request_error.emit(tag, "Kein API-Schlüssel gesetzt.")
            return

        url = API_BASE + path
        headers = {
            "apikey": self._api_key,
            "User-Agent": f"Anvil Organizer/{APP_VERSION}",
            "Content-Type": "application/json",
        }

        worker = _ApiWorker(url, headers, tag, parent=self)
        worker.finished.connect(self._on_worker_finished)
        worker.error.connect(self._on_worker_error)
        worker.finished.connect(lambda *_: self._cleanup_worker(worker))
        worker.error.connect(lambda *_: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker: _ApiWorker) -> None:
        """Remove finished worker from the list."""
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()

    def _on_worker_error(self, tag: str, message: str) -> None:
        """Handle network-level errors (timeout, DNS, etc.)."""
        self.request_error.emit(tag, message)

    def _on_worker_finished(self, tag: str, status: int, headers: dict, body: bytes) -> None:
        """Handle a completed HTTP response."""
        # Read rate limit headers
        daily_str = headers.get("x-rl-daily-remaining", "")
        hourly_str = headers.get("x-rl-hourly-remaining", "")
        if daily_str:
            try:
                self._daily_remaining = int(daily_str)
            except ValueError:
                pass
        if hourly_str:
            try:
                self._hourly_remaining = int(hourly_str)
            except ValueError:
                pass
        if daily_str or hourly_str:
            self.rate_limit_updated.emit(self._daily_remaining, self._hourly_remaining)

        # Check HTTP status
        if status == 429:
            self.request_error.emit(tag, "Rate Limit erreicht. Bitte warten.")
            return
        if status == 401:
            self.request_error.emit(tag, "Ungültiger API-Schlüssel.")
            return
        if status >= 400:
            self.request_error.emit(tag, f"HTTP {status}")
            return

        # Parse JSON
        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self.request_error.emit(tag, f"JSON-Fehler: {exc}")
            return

        # Special handling for validate
        if tag == "validate" and isinstance(data, dict):
            self.user_validated.emit(data)

        self.request_finished.emit(tag, data)
