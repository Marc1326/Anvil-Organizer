"""Nexus Mods SSO login via WebSocket.

Flow (Nexus SSO protocol v2):
1. Connect WebSocket to wss://sso.nexusmods.com
2. Send {"id": "<uuid>", "token": null, "protocol": 2}
3. Receive {"success": true, "data": {"connection_token": "..."}}
4. Open browser: https://www.nexusmods.com/sso?id=<uuid>&application=<slug>
5. User authorizes in browser
6. Receive {"success": true, "data": {"api_key": "..."}}

NOTE: The application parameter MUST be registered with Nexus Mods.
      Until registered, use manual API key entry as fallback.

Uses Python stdlib (ssl + socket) in a QThread — no QtNetwork/krb5 needed.
"""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import socket
import struct
import subprocess
import uuid
from urllib.parse import urlparse

from anvil.core.subprocess_env import clean_subprocess_env

from PySide6.QtCore import QObject, Signal, QThread, QTimer


WSS_URL = "wss://sso.nexusmods.com"
# Registered with Nexus Mods
APPLICATION_SLUG = "nathuk-anvilorganizer"


class _SSOState:
    """SSO connection states."""
    CONNECTING = 0       # Connecting to WebSocket
    WAITING_TOKEN = 1    # Waiting for connection_token
    WAITING_BROWSER = 2  # Waiting for user to authorize in browser
    FINISHED = 3         # Successfully received API key
    TIMEOUT = 4          # Connection timed out
    CLOSED_BY_REMOTE = 5 # Server closed connection
    CANCELLED = 6        # User cancelled
    ERROR = 7            # Generic error


STATE_MESSAGES = {
    _SSOState.CONNECTING: "Verbinde zu Nexus...",
    _SSOState.WAITING_TOKEN: "Warten auf Nexus...",
    _SSOState.WAITING_BROWSER: "Nexus im Browser geöffnet.\nWechsle zu deinem Browser und akzeptiere die Anfrage.",
    _SSOState.FINISHED: "Erfolgreich mit Nexus verknüpft.",
    _SSOState.TIMEOUT: "Zeitüberschreitung bei der Verbindung.",
    _SSOState.CLOSED_BY_REMOTE: "Verbindung vom Server geschlossen.",
    _SSOState.CANCELLED: "Abgebrochen.",
    _SSOState.ERROR: "Ein Fehler ist aufgetreten.",
}


class _WebSocketWorker(QThread):
    """Background thread that handles the WebSocket SSO handshake.

    Uses Python stdlib ssl+socket for a minimal WebSocket client
    (no QtNetwork, no external packages).
    """

    state_changed = Signal(int, str)   # (state, detail)
    key_received = Signal(str)         # api_key
    error_occurred = Signal(str)       # error message

    def __init__(self, session_id: str, parent=None):
        super().__init__(parent)
        self._session_id = session_id
        self._cancelled = False
        self._sock: socket.socket | None = None

    def cancel(self) -> None:
        self._cancelled = True
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass

    def run(self) -> None:
        try:
            self._do_sso()
        except Exception as exc:
            if not self._cancelled:
                self.error_occurred.emit(str(exc))

    def _do_sso(self) -> None:
        """Execute the full SSO WebSocket handshake."""
        parsed = urlparse(WSS_URL)
        host = parsed.hostname or "sso.nexusmods.com"
        port = parsed.port or 443

        self.state_changed.emit(_SSOState.CONNECTING, "")

        # Create SSL socket
        ctx = ssl.create_default_context()
        raw = socket.create_connection((host, port), timeout=10)
        self._sock = ctx.wrap_socket(raw, server_hostname=host)

        # WebSocket upgrade handshake
        ws_key = _ws_random_key()
        handshake = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        self._sock.sendall(handshake.encode())

        # Read upgrade response
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self._sock.recv(4096)
            if not chunk:
                self.state_changed.emit(_SSOState.CLOSED_BY_REMOTE, "")
                return
            resp += chunk

        if b"101" not in resp.split(b"\r\n")[0]:
            self.error_occurred.emit(f"WebSocket upgrade fehlgeschlagen: {resp[:200].decode(errors='replace')}")
            return

        # Send session ID
        msg = json.dumps({"id": self._session_id, "token": None, "protocol": 2})
        _ws_send_text(self._sock, msg)
        self.state_changed.emit(_SSOState.WAITING_TOKEN, "")

        # Receive loop
        while not self._cancelled:
            try:
                self._sock.settimeout(120)  # 2 min timeout for browser auth
                frame = _ws_recv_text(self._sock)
            except (socket.timeout, OSError):
                if not self._cancelled:
                    self.state_changed.emit(_SSOState.TIMEOUT, "")
                return

            if frame is None:
                if not self._cancelled:
                    self.state_changed.emit(_SSOState.CLOSED_BY_REMOTE, "")
                return

            data = json.loads(frame)
            if not data.get("success"):
                err = data.get("error", "Unknown error")
                self.error_occurred.emit(err)
                return

            payload = data.get("data", {})

            # First message: connection_token
            if "connection_token" in payload:
                url = f"https://www.nexusmods.com/sso?id={self._session_id}&application={APPLICATION_SLUG}"
                subprocess.Popen(["xdg-open", url], env=clean_subprocess_env())
                self.state_changed.emit(_SSOState.WAITING_BROWSER, "")

            # Second message: api_key
            elif "api_key" in payload:
                api_key = payload["api_key"]
                self.key_received.emit(api_key)
                self.state_changed.emit(_SSOState.FINISHED, "")
                break

        # Close
        try:
            _ws_send_close(self._sock)
            self._sock.close()
        except OSError:
            pass


class NexusSSOLogin(QObject):
    """SSO login manager for Nexus Mods.

    Signals:
        key_changed(api_key): API key received from Nexus.
        state_changed(state, detail): Connection state update.
    """

    key_changed = Signal(str)
    state_changed = Signal(int, str)

    State = _SSOState

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker: _WebSocketWorker | None = None
        self._active = False

    def is_active(self) -> bool:
        return self._active

    def start(self) -> None:
        """Start the SSO login flow."""
        if self._active:
            return
        self._active = True
        session_id = str(uuid.uuid4())

        self._worker = _WebSocketWorker(session_id, parent=self)
        self._worker.state_changed.connect(self._on_state)
        self._worker.key_received.connect(self._on_key)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._on_thread_done)
        self._worker.start()

    def cancel(self) -> None:
        """Cancel the SSO login."""
        if self._worker:
            self._worker.cancel()
        self._active = False
        self.state_changed.emit(_SSOState.CANCELLED, "")

    def _on_state(self, state: int, detail: str) -> None:
        self.state_changed.emit(state, detail)

    def _on_key(self, api_key: str) -> None:
        self.key_changed.emit(api_key)

    def _on_error(self, message: str) -> None:
        self._active = False
        self.state_changed.emit(_SSOState.ERROR, message)

    def _on_thread_done(self) -> None:
        self._active = False

    @staticmethod
    def state_to_string(state: int, detail: str = "") -> str:
        """Convert state to user-readable German string."""
        if state == _SSOState.ERROR and detail:
            return f"Fehler: {detail}"
        return STATE_MESSAGES.get(state, "Unbekannter Status.")


# ── Minimal WebSocket helpers (RFC 6455) ──────────────────────────────

def _ws_random_key() -> str:
    """Generate a random Sec-WebSocket-Key."""
    import base64
    return base64.b64encode(os.urandom(16)).decode()


def _ws_send_text(sock: socket.socket, text: str) -> None:
    """Send a text frame (masked, as required by RFC 6455 for clients)."""
    payload = text.encode("utf-8")
    mask_key = os.urandom(4)

    # Frame header
    header = bytearray()
    header.append(0x81)  # FIN + TEXT opcode
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)  # MASK bit set
    elif length < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack(">H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack(">Q", length))

    header.extend(mask_key)

    # Mask payload
    masked = bytearray(len(payload))
    for i, b in enumerate(payload):
        masked[i] = b ^ mask_key[i % 4]

    sock.sendall(bytes(header) + bytes(masked))


def _ws_send_close(sock: socket.socket) -> None:
    """Send a close frame."""
    mask_key = os.urandom(4)
    sock.sendall(bytes([0x88, 0x80]) + mask_key)


def _ws_recv_text(sock: socket.socket) -> str | None:
    """Receive a text frame. Returns None on close/error."""
    # Read first 2 bytes
    header = _ws_recv_exact(sock, 2)
    if header is None:
        return None

    opcode = header[0] & 0x0F
    masked = bool(header[1] & 0x80)
    length = header[1] & 0x7F

    if length == 126:
        ext = _ws_recv_exact(sock, 2)
        if ext is None:
            return None
        length = struct.unpack(">H", ext)[0]
    elif length == 127:
        ext = _ws_recv_exact(sock, 8)
        if ext is None:
            return None
        length = struct.unpack(">Q", ext)[0]

    mask_key = None
    if masked:
        mask_key = _ws_recv_exact(sock, 4)
        if mask_key is None:
            return None

    payload = _ws_recv_exact(sock, length)
    if payload is None:
        return None

    if mask_key:
        payload = bytearray(payload)
        for i in range(len(payload)):
            payload[i] ^= mask_key[i % 4]
        payload = bytes(payload)

    # Close frame
    if opcode == 0x08:
        return None

    # Ping → respond with pong
    if opcode == 0x09:
        pong = bytearray([0x8A, 0x80]) + os.urandom(4)
        try:
            sock.sendall(bytes(pong))
        except OSError:
            pass
        return _ws_recv_text(sock)  # continue receiving

    return payload.decode("utf-8", errors="replace")


def _ws_recv_exact(sock: socket.socket, n: int) -> bytes | None:
    """Read exactly n bytes from socket."""
    data = b""
    while len(data) < n:
        try:
            chunk = sock.recv(n - len(data))
        except (socket.timeout, OSError):
            return None
        if not chunk:
            return None
        data += chunk
    return data
