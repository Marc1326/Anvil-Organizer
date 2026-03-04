"""Single-instance guard using QLocalServer / QLocalSocket.

Ensures only one Anvil Organizer process runs at a time.
If a second instance is started with an nxm:// URL, it forwards
the URL to the running instance via Unix domain socket and exits.
"""

from PySide6.QtCore import Signal, QObject, QByteArray
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = "anvil-organizer-single-instance"


class SingleInstance(QObject):
    """Manages single-instance enforcement via QLocalServer."""

    message_received = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._server: QLocalServer | None = None

    def try_lock(self) -> bool:
        """Try to become the primary instance.

        Returns True if this is the first instance (server started).
        Returns False if another instance is already running.
        """
        self._server = QLocalServer(self)
        if self._server.listen(SERVER_NAME):
            self._server.newConnection.connect(self._on_new_connection)
            return True

        # Listen failed — maybe stale socket from a crash
        QLocalServer.removeServer(SERVER_NAME)
        if self._server.listen(SERVER_NAME):
            self._server.newConnection.connect(self._on_new_connection)
            return True

        # Another instance is truly running
        return False

    @staticmethod
    def send_message(message: str, timeout_ms: int = 3000) -> bool:
        """Send a message to the running primary instance.

        Returns True if the message was sent successfully.
        """
        socket = QLocalSocket()
        socket.connectToServer(SERVER_NAME)
        if not socket.waitForConnected(timeout_ms):
            return False
        socket.write(message.encode("utf-8"))
        socket.waitForBytesWritten(timeout_ms)
        socket.disconnectFromServer()
        return True

    def _on_new_connection(self):
        """Handle incoming connection from a secondary instance."""
        socket = self._server.nextPendingConnection()
        if not socket:
            return
        socket.waitForReadyRead(3000)
        data = socket.readAll()
        if isinstance(data, QByteArray):
            data = data.data()
        message = data.decode("utf-8", errors="replace")
        if message:
            self.message_received.emit(message)
        socket.disconnectFromServer()
