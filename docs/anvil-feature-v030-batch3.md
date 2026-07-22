# Feature: v0.3.0 Bugfix — Batch 3
Datum: 2026-03-04

---

## BUG 6: NXM-Download öffnet neue Anvil-Instanz statt an laufende zu übergeben

### Problembeschreibung
Wenn Anvil bereits läuft und der User auf nexusmods.com "Download with Manager" klickt,
startet das System über die `.desktop`-Datei eine **zweite Anvil-Instanz** (`python3 main.py nxm://...`).
Die zweite Instanz verarbeitet den NXM-Link alleine — die erste Instanz bekommt nichts mit.

### Ursache
`main.py` hat keinen Single-Instance-Check. Jeder Aufruf erzeugt eine neue `QApplication` + `MainWindow`.

---

## User Stories
- Als User möchte ich auf Nexus "Download with Manager" klicken und den Download in meiner laufenden Anvil-Instanz sehen, nicht in einer neuen.
- Als User möchte ich, dass die zweite Instanz sich sofort beendet nachdem sie den Link weitergeleitet hat.
- Als User möchte ich bei einem Socket-Fehler eine informative Fehlermeldung sehen.

---

## Technische Planung

### MO2-Vergleich
MO2 nutzt **`QSharedMemory`** als Lock + **`QLocalServer`/`QLocalSocket`** als IPC-Kanal
(siehe `mo2-referenz/src/multiprocess.cpp`):

1. Erste Instanz: `QSharedMemory.create(1)` → Erfolg → `m_OwnsSM = true`
2. Erste Instanz: `QLocalServer.listen(key)` → wartet auf Verbindungen
3. Zweite Instanz: `QSharedMemory.create(1)` → `AlreadyExists` → ephemere Instanz
4. Zweite Instanz: `QLocalSocket.connectToServer(key)` → sendet NXM-URL als UTF-8
5. Erste Instanz: `receiveMessage()` → `emit messageSent(url)` → Download starten
6. Zweite Instanz: `return 0` (beendet sich sofort)

### Anvil-Lösung (analog zu MO2)

Wir nutzen **`QLocalServer`/`QLocalSocket`** — das ist der Qt-native IPC-Mechanismus,
plattformunabhängig und benötigt keine externen Dependencies. `QSharedMemory` ist auf
Linux seit Qt 6.6 weniger zuverlässig (System V vs. POSIX Wechsel), daher nutzen wir
den Server-Listen-Fehler direkt als Lock-Mechanismus:
- `QLocalServer.listen()` schlägt fehl wenn der Socket-Name bereits belegt ist
- Auf Linux bleibt nach einem Crash ein Stale-Socket zurück → `removeServer()` vor retry

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `anvil/core/single_instance.py` | **NEU** — `SingleInstance`-Klasse mit QLocalServer/Socket |
| `main.py` | Single-Instance-Check VOR QApplication, Weiterleitung bei Duplikat |
| `anvil/mainwindow.py` | Signal-Verbindung für eingehende NXM-URLs vom IPC-Server |

### Neue Klasse: `anvil/core/single_instance.py`

```python
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

    message_received = Signal(str)  # emitted when a message arrives from another instance

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
```

### Änderungen in `main.py`

```python
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Anvil Organizer")
    app.setApplicationVersion("0.3.0")

    # ── Single-instance check ────────────────────────────────
    from anvil.core.single_instance import SingleInstance

    single = SingleInstance(app)
    if not single.try_lock():
        # Another instance is running — forward nxm:// URL if present
        from anvil.core.nxm_handler import check_cli_for_nxm
        nxm_link = check_cli_for_nxm()
        if nxm_link:
            SingleInstance.send_message(nxm_link.raw_url)
        # Exit silently — the primary instance handles it
        sys.exit(0)

    # ── Normal startup ────────────────────────────────────────
    _init_translator()
    # ... (Qt-Übersetzungen, MainWindow, etc.)

    w = MainWindow()

    # Connect IPC → MainWindow
    single.message_received.connect(w.handle_nxm_url)

    w.showMaximized()
    sys.exit(app.exec())
```

### Signal-Flow

```
User klickt "Download with Manager" auf Nexus
        │
        ▼
xdg-open nxm://... → .desktop → python3 main.py nxm://...
        │
        ▼
main.py: SingleInstance.try_lock() → False (Server läuft bereits)
        │
        ▼
main.py: check_cli_for_nxm() → NxmLink
        │
        ▼
SingleInstance.send_message(nxm_link.raw_url)
  → QLocalSocket → Unix Domain Socket → QLocalServer
        │
        ▼
Erste Instanz: SingleInstance._on_new_connection()
  → message_received.emit(url)
        │
        ▼
MainWindow.handle_nxm_url(url)  [Zeile 3218]
  → parse_nxm_url(url) → _handle_nxm_link()
  → Nexus API → Download starten
        │
        ▼
Zweite Instanz: sys.exit(0)
```

### Besondere Überlegungen

1. **Stale Socket nach Crash:** `QLocalServer.removeServer()` löscht den Unix-Socket
   wenn `listen()` fehlschlägt — bevor wir annehmen, dass eine Instanz läuft, wird
   ein zweiter Versuch unternommen.

2. **Keine neuen Dependencies:** `QLocalServer`/`QLocalSocket` sind in `PySide6.QtNetwork`
   enthalten, das bereits im Projekt genutzt wird (Nexus SSO WebSocket).

3. **Kein QSharedMemory:** Qt 6.6+ hat auf Linux den SharedMemory-Backend von System V
   auf POSIX umgestellt, was Kompatibilitätsprobleme verursachen kann. Der
   `QLocalServer.listen()`-Fehler reicht als Lock-Mechanismus.

4. **Kein Fenster-Raise:** Die erste Instanz muss NICHT in den Vordergrund gebracht
   werden — der Download startet im Hintergrund, der Downloads-Tab wird gewechselt.
   (Raise über Wayland ist ohnehin nicht möglich ohne Compositor-Kooperation.)

5. **Bestehende MainWindow-API:** `handle_nxm_url()` (Zeile 3218) existiert bereits
   mit dem Kommentar "Can be called from external IPC" — genau für diesen Zweck.

---

## Abhängigkeiten
- `PySide6.QtNetwork` (bereits im Projekt vorhanden)
- `.desktop`-Datei muss korrekt registriert sein (`register_nxm_handler()`)

## Risiken
- **Stale Socket:** Wenn Anvil crasht und der Socket nicht aufgeräumt wird, könnte
  der nächste Start den Stale-Socket als "laufende Instanz" interpretieren →
  gelöst durch `removeServer()` + retry
- **Gleichzeitiger Start:** Zwei Instanzen starten exakt gleichzeitig → Race Condition.
  Ist in der Praxis bei NXM-Downloads nicht relevant (Desktop startet App sequentiell)

## Geschätzter Aufwand
- 1 neue Datei (~70 Zeilen)
- 2 geänderte Dateien (~20 Zeilen)
- Gering — alle Bausteine existieren bereits

---

## Akzeptanz-Kriterien (ALLE müssen erfüllt sein)

- [ ] Wenn Anvil läuft und der User `python3 main.py nxm://skyrim/mods/1/files/2` ausführt, öffnet sich KEINE zweite Instanz — die zweite beendet sich sofort
- [ ] Wenn Anvil läuft und ein NXM-Link per CLI übergeben wird, erscheint der Download im Downloads-Tab der laufenden Instanz
- [ ] Wenn Anvil NICHT läuft und `python3 main.py nxm://...` ausgeführt wird, startet Anvil normal und verarbeitet den NXM-Link direkt
- [ ] Wenn Anvil abstürzt und danach neu gestartet wird, startet es normal (kein Stale-Socket-Block)
- [ ] Wenn Anvil läuft und `python3 main.py` OHNE NXM-Link ausgeführt wird, beendet sich die zweite Instanz sofort ohne Fehlermeldung
- [ ] Wenn der QLocalSocket-Connect fehlschlägt (Timeout), beendet sich die zweite Instanz trotzdem sauber (exit 0, kein Traceback)
- [ ] `SingleInstance` nutzt `QLocalServer`/`QLocalSocket` aus `PySide6.QtNetwork` — keine externen Dependencies
- [ ] `SingleInstance.message_received` Signal ist mit `MainWindow.handle_nxm_url()` verbunden
- [ ] Keine hardcoded Pfade — Socket-Name ist eine Konstante in `single_instance.py`
- [ ] `restart.sh` startet ohne Fehler
