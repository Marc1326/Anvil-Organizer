# QA Report — Bug 6: Single-Instance Guard
Datum: 2026-03-04

---

## Root Cause (BESTÄTIGT)

**Datei:** `anvil/core/single_instance.py:35`

```python
# Listen failed — maybe stale socket from a crash
QLocalServer.removeServer(SERVER_NAME)          # ← LÖSCHT Socket der LAUFENDEN Instanz!
if self._server.listen(SERVER_NAME):            # ← Gelingt jetzt IMMER
    ...
    return True                                 # ← FALSCH POSITIV!
```

`QLocalServer.removeServer()` löscht die Unix-Domain-Socket-Datei **bedingungslos** —
egal ob sie zu einer laufenden Instanz gehört oder ein Stale-Socket von einem Crash ist.

**Ablauf:**
1. Instanz A läuft, hat Server auf `/tmp/anvil-organizer-single-instance`
2. Instanz B startet, `listen()` (Zeile 30) schlägt fehl (korrekt)
3. `removeServer()` (Zeile 35) **löscht Socket-Datei von Instanz A**
4. `listen()` (Zeile 36) **gelingt** — neuer Socket erstellt
5. `try_lock()` gibt **True** zurück → zweite Instanz mit vollem MainWindow
6. Instanz A ist jetzt "taub" — ihr Socket existiert nicht mehr im Dateisystem

---

## Findings

### [CRITICAL] removeServer() löscht Socket der laufenden Instanz — Guard wirkungslos
- **Datei:** `anvil/core/single_instance.py:35-38`
- **Problem:** Kein Lebendigkeits-Check vor removeServer(). Jede zweite Instanz kann starten.
- **Fix:** Vor removeServer() einen Probe-Connect mit QLocalSocket durchführen:

```python
def try_lock(self) -> bool:
    self._server = QLocalServer(self)
    if self._server.listen(SERVER_NAME):
        self._server.newConnection.connect(self._on_new_connection)
        return True

    # Listen failed — check if existing server is alive
    probe = QLocalSocket()
    probe.connectToServer(SERVER_NAME)
    if probe.waitForConnected(1000):
        # Server antwortet — echte laufende Instanz
        probe.disconnectFromServer()
        return False

    # Server antwortet nicht — stale Socket von Crash
    QLocalServer.removeServer(SERVER_NAME)
    if self._server.listen(SERVER_NAME):
        self._server.newConnection.connect(self._on_new_connection)
        return True

    return False
```

### [HIGH] MO2-Vergleich: Fehlendes Zwei-Stufen-System
- **Datei:** `anvil/core/single_instance.py` (gesamte Datei)
- **Problem:** MO2 nutzt QSharedMemory als atomaren Lock + QLocalServer nur für IPC. Anvil nutzt nur QLocalServer für beides.
- **Fix:** Der Probe-Connect (CRITICAL Fix) ist pragmatisch ausreichend. QSharedMemory ist auf Linux seit Qt 6.6 problematisch (System V → POSIX Wechsel).

### [MEDIUM] Race Condition bei gleichzeitigem Start
- **Datei:** `anvil/core/single_instance.py:29-41`
- **Problem:** Zwei gleichzeitig startende Instanzen können sich gegenseitig den Socket löschen.
- **Fix:** Durch den Probe-Connect ebenfalls gelöst — die Gewinnerin antwortet auf den Probe.

### [MEDIUM] send_message() Rückgabewert wird nicht geprüft
- **Datei:** `main.py:35`
- **Problem:** Wenn IPC-Übertragung fehlschlägt, geht der NXM-Link still verloren. Kein Logging.
- **Fix:** Rückgabewert prüfen und bei Fehler debug.log-Warnung ausgeben.

### [LOW] Kein expliziter Server-Shutdown bei normalem Beenden
- **Datei:** `anvil/core/single_instance.py` (fehlend)
- **Problem:** Kein close()/Destruktor. Qt räumt über Parent-Hierarchie auf, aber bei sys.exit() nicht garantiert.
- **Fix:** Optional: close()-Methode hinzufügen. Mit dem Probe-Fix nicht mehr kritisch.

### [LOW] Socket-Leak in _on_new_connection()
- **Datei:** `anvil/core/single_instance.py:58-70`
- **Problem:** Socket aus nextPendingConnection() hat kein Parent-Objekt, wird nur durch Python-GC aufgeräumt.
- **Fix:** `socket.deleteLater()` nach disconnectFromServer() hinzufügen.

### [LOW] send_message() ohne waitForDisconnected()
- **Datei:** `anvil/core/single_instance.py:55`
- **Problem:** Nach disconnectFromServer() wird nicht auf Bestätigung gewartet.
- **Fix:** `socket.waitForDisconnected(1000)` hinzufügen.

---

## Akzeptanz-Checkliste

| # | Kriterium | Status |
|---|-----------|--------|
| 1 | Keine zweite Instanz bei laufendem Anvil | ❌ CRITICAL — removeServer() löscht Socket, try_lock() gibt True zurück |
| 2 | NXM-Link erscheint in laufender Instanz | ❌ Abhängig von #1 — zweite Instanz wird Primary |
| 3 | Normaler Start mit NXM wenn Anvil nicht läuft | ✅ MainWindow verarbeitet NXM über check_cli_for_nxm() in __init__ |
| 4 | Kein Stale-Socket-Block nach Crash | ✅ removeServer() + retry funktioniert (zu aggressiv, aber funktional) |
| 5 | Zweite Instanz ohne NXM beendet sich sofort | ❌ Abhängig von #1 — try_lock() gibt True zurück |
| 6 | Sauberer Exit bei Socket-Timeout | ✅ sys.exit(0) ohne try/except, kein Traceback |
| 7 | Nur PySide6.QtNetwork, keine externen Deps | ✅ QLocalServer/QLocalSocket aus PySide6.QtNetwork |
| 8 | message_received mit handle_nxm_url verbunden | ✅ main.py:51 — single.message_received.connect(w.handle_nxm_url) |
| 9 | Keine hardcoded Pfade, Socket-Name als Konstante | ✅ SERVER_NAME = "anvil-organizer-single-instance" |
| 10 | restart.sh startet ohne Fehler | ✅ restart.sh existiert und startet die App |

## Ergebnis: 7/10 Punkte erfüllt — NEEDS FIXES

Kritische Punkte 1, 2, 5 hängen alle am selben Root Cause:
**removeServer() ohne Lebendigkeits-Check.**

**Minimal-Fix: 7 Zeilen Code** — Probe-Connect vor removeServer() in try_lock().
