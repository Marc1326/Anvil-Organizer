# QA Report -- Agent 1: nexus_sso.py Pruefung
Datum: 2026-03-02

## Geprueft
**Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py` (352 Zeilen)
**Vergleich mit:** `/home/mob/Projekte/mo2-referenz/src/nxmaccessmanager.cpp` (MO2 NexusSSOLogin)

---

## Punkt 1: APPLICATION_SLUG

**Status: OK**

- Zeile 34: `APPLICATION_SLUG = "nathuk-anvilorganizer"`
- Der Slug ist exakt `"nathuk-anvilorganizer"` wie gefordert.
- Fruehere Docs (agent1-nexus-api.md) erwaehnen noch den alten Wert `"anvilorganizer"` -- dieser wurde offensichtlich bereits korrigiert.

---

## Punkt 2: Slug-Verwendung in Browser-URL

**Status: OK**

- Zeile 162: `url = f"https://www.nexusmods.com/sso?id={self._session_id}&application={APPLICATION_SLUG}"`
- Die URL wird korrekt zusammengebaut mit:
  - `id` = UUID der Session (generiert in `NexusSSOLogin.start()` Zeile 207)
  - `application` = die Konstante `APPLICATION_SLUG`
- Danach wird `webbrowser.open(url)` aufgerufen (Zeile 163).
- **MO2-Vergleich:** MO2 nutzt `NexusSSOPage.arg(m_guid)` mit Template `"https://www.nexusmods.com/sso?id=%1&application=modorganizer2"` (Zeile 48 in nxmaccessmanager.cpp). Das Anvil-Aequivalent ist identisch im Format, nur mit anderem Slug. Korrekt.

---

## Punkt 3: SSO-Flow Fehlerbehandlung

### 3a) Timeout
**Status: OK mit Anmerkung**

- `_WebSocketWorker` setzt `socket.settimeout(120)` (Zeile 140) -- 2 Minuten Timeout fuer Browser-Auth.
- Bei `socket.timeout` oder `OSError` (Zeile 142): Wenn nicht cancelled, wird `_SSOState.TIMEOUT` emittiert (Zeile 144). Dann `return`.
- Der initiale `socket.create_connection` hat `timeout=10` (Zeile 103) fuer den Verbindungsaufbau.

**Anmerkung (MEDIUM):** MO2 nutzt einen separaten `QTimer` mit 10 Sekunden Timeout (`m_timeout.setInterval(10s)`, Zeile 158 in nxmaccessmanager.cpp) fuer die initiale Verbindung, und stoppt ihn nach Erhalt des `connection_token` (Zeile 311). Anvil hat keinen separaten Timeout-Timer fuer die initiale Phase -- der 10-Sekunden-Timeout kommt implizit durch `socket.create_connection(..., timeout=10)`. Das funktioniert, ist aber weniger praezise: MO2 unterscheidet zwischen "Server antwortet nicht auf Upgrade" und "Socket-Timeout". In Anvil wuerde beides als `OSError` in `_do_sso()` landen und als generische Exception behandelt (Zeile 89-91), NICHT als `TIMEOUT` State. Der TIMEOUT-State wird nur im Receive-Loop emittiert (Zeile 144), nicht bei Verbindungsfehlern.

### 3b) Server-Close
**Status: OK**

- Wenn der Server die Verbindung waehrend des Upgrades schliesst (leerer chunk, Zeile 123-125): `CLOSED_BY_REMOTE` emittiert.
- Wenn `_ws_recv_text` `None` zurueckgibt im Receive-Loop (Zeile 147-149): `CLOSED_BY_REMOTE` emittiert.
- Beide Faelle korrekt behandelt.

### 3c) Cancel
**Status: OK**

- `_WebSocketWorker.cancel()` (Zeile 78-84): Setzt `_cancelled = True`, schliesst den Socket.
- Der Receive-Loop in `_do_sso()` prueft `while not self._cancelled` (Zeile 138).
- Bei `socket.timeout`/`OSError` nach Cancel: `self._cancelled` ist True, also wird kein State emittiert (Zeile 143). Korrekt.
- Bei `frame is None` nach Cancel: Ebenfalls kein State emittiert (Zeile 148). Korrekt.
- Die aeussere Exception-Behandlung (Zeile 90) prueft ebenfalls `not self._cancelled`. Korrekt.
- `NexusSSOLogin.cancel()` emittiert `CANCELLED` (Zeile 221). Korrekt.

### 3d) JSON-Parse-Fehler
**Status: MEDIUM Finding**

- Zeile 152: `data = json.loads(frame)` -- Wenn der Server ungueltiges JSON sendet, wirft das eine `json.JSONDecodeError`.
- Diese Exception wird von `_do_sso()` Zeile 89 gefangen und als `error_occurred` emittiert, was dann zu `_SSOState.ERROR` fuehrt.
- Das ist funktional korrekt, aber die Fehlermeldung waere technisch (z.B. `"Expecting value: line 1 column 1 (char 0)"`). MO2 nutzt Qt's `QJsonDocument::fromJson()` das bei Fehlern einfach ein leeres Dokument zurueckgibt und dann wird `success` False sein. Anvils Verhalten ist akzeptabel.

### 3e) success=false vom Server
**Status: OK**

- Zeile 153-156: Wenn `data.get("success")` falsch ist, wird der Error aus `data.get("error")` extrahiert und via `error_occurred` emittiert. Korrekt.

---

## Punkt 4: is_active()

**Status: OK mit MEDIUM Finding**

- Zeile 199-200: `is_active()` gibt `self._active` zurueck. Einfach und korrekt.
- `_active` wird `True` in `start()` (Zeile 206).
- `_active` wird `False` in: `cancel()` (Zeile 220), `_on_error()` (Zeile 230), `_on_thread_done()` (Zeile 234).

**Finding (MEDIUM): Race Condition bei _active:**
- `_on_thread_done()` wird aufgerufen wenn der Worker-Thread endet (via `QThread.finished` Signal, Zeile 213).
- `cancel()` setzt `_active = False` sofort (Zeile 220) und emittiert `CANCELLED`.
- ABER: Der Worker-Thread laeuft moeglicherweise noch. Wenn der Thread dann endet, wird `_on_thread_done()` erneut `_active = False` setzen -- das ist harmlos (idempotent).
- Das echte Problem: Wenn `start()` schnell nach `cancel()` aufgerufen wird, koennte `_on_thread_done()` vom ALTEN Worker den NEUEN `_active = True` ueberschreiben. Der alte Worker ist als `parent=self` angelegt, wird aber durch `self._worker = _WebSocketWorker(...)` ueberschrieben -- der alte Worker hat dann keinen Python-Referenz mehr, aber Qt haelt ihn noch als Child. Das `finished`-Signal des alten Workers ist noch an `_on_thread_done` verbunden.
- **MO2-Vergleich:** MO2's `NexusSSOLogin::cancel()` ruft `abort()` auf, das `m_active = false` setzt UND `m_socket.abort()` aufruft (synchron, da im gleichen Thread). Kein Threading-Problem, weil MO2 keinen separaten Thread nutzt sondern Qt's Event-Loop mit QWebSocket.

**Empfohlener Fix:** In `start()` vor dem Erstellen eines neuen Workers pruefen ob der alte Thread noch laeuft, und ggf. `disconnect()` aufrufen. Oder den alten Worker explizit disconnecten und warten (`wait()`).

---

## Punkt 5: cancel() setzt _active=False und emittiert CANCELLED

**Status: OK**

- Zeile 216-221:
```python
def cancel(self) -> None:
    if self._worker:
        self._worker.cancel()
    self._active = False
    self.state_changed.emit(_SSOState.CANCELLED, "")
```
- `_active` wird auf `False` gesetzt. Korrekt.
- `_SSOState.CANCELLED` wird emittiert. Korrekt.
- Der Worker wird ueber `_worker.cancel()` benachrichtigt. Korrekt.

**Anmerkung (LOW):** `cancel()` emittiert CANCELLED auch wenn kein SSO aktiv war (`_active` war schon `False`). MO2 prueft `if (m_active)` bevor `setState(Cancelled)` aufgerufen wird (Zeile 236 in nxmaccessmanager.cpp). In Anvil wuerde ein doppelter Cancel-Aufruf ein doppeltes CANCELLED Signal emittieren. Nicht kritisch, aber unschoen.

---

## Zusaetzliche Findings

### [MEDIUM] Rekursion in _ws_recv_text bei Ping-Frames
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py:335`
- **Problem:** Bei Empfang eines Ping-Frames wird `_ws_recv_text(sock)` rekursiv aufgerufen (Zeile 335). Wenn der Server viele Pings sendet (unwahrscheinlich, aber moeglich), koennte ein Stack Overflow entstehen.
- **Fix:** Iterative Schleife statt Rekursion (while-Loop in `_ws_recv_text`).
- **Hinweis:** Dies wurde bereits im Security-Report erwaehnt (security-agent3-plugins.md, Finding 9). Noch nicht gefixt.

### [LOW] Pong-Frame-Laenge falsch
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py:330`
- **Problem:** Der Pong-Frame wird als `[0x8A, 0x80] + os.urandom(4)` gesendet. `0x80` bedeutet "masked, payload length 0", dann kommen 4 Bytes Mask-Key mit 0 Bytes Payload. Das ist formal korrekt (leerer maskierter Pong). ABER: RFC 6455 sagt, ein Pong SOLL den gleichen Payload wie der Ping enthalten. Der Ping-Payload wird hier verworfen.
- **Impact:** Nexus-Server koennte den Pong als ungueltig betrachten. In der Praxis ignorieren die meisten Server den Pong-Payload, aber es ist nicht spec-konform.
- **Fix:** Den Ping-Payload im Pong zuruecksenden (maskiert).

### [LOW] Hardcodierte deutsche Strings in STATE_MESSAGES
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py:49-58`
- **Problem:** `STATE_MESSAGES` enthaelt hardcodierte deutsche Strings ohne `tr()`. Die `state_to_string()` Methode nutzt dieses Dict direkt.
- **Impact:** Wenn die App auf eine andere Sprache umgestellt wird, bleiben die SSO-Statusmeldungen deutsch.
- **Hinweis:** Der Settings-Dialog nutzt `NexusSSOLogin.state_to_string()` (Zeile 985 in settings_dialog.py), die Meldungen werden dem Benutzer direkt angezeigt.
- **Fix:** `tr()` verwenden, z.B. `tr("sso.state_connecting")` etc., und Keys in allen 6 Locale-Dateien anlegen.

---

## Zusammenfassung Findings

| # | Severity | Beschreibung | Zeile |
|---|----------|-------------|-------|
| 1 | MEDIUM | Race Condition: alter Worker-Thread kann `_active` des neuen ueberschreiben | 196-234 |
| 2 | MEDIUM | Rekursion bei Ping-Frames (Stack Overflow moeglich) | 335 |
| 3 | MEDIUM | Initialer Verbindungs-Timeout fuehrt zu ERROR statt TIMEOUT State | 89-91 vs. 144 |
| 4 | LOW | `cancel()` emittiert CANCELLED auch wenn nicht aktiv (doppeltes Signal) | 216-221 |
| 5 | LOW | Pong-Frame sendet leeren Payload statt Ping-Echo | 330 |
| 6 | LOW | Hardcodierte deutsche Strings ohne tr() in STATE_MESSAGES | 49-58 |

## Pruefergebnis der 5 geforderten Punkte

| # | Pruefpunkt | Ergebnis |
|---|-----------|----------|
| 1 | APPLICATION_SLUG = "nathuk-anvilorganizer" | OK |
| 2 | Slug korrekt in Browser-URL verwendet | OK |
| 3 | Timeout/Server-Close/Cancel States korrekt | OK (3 MEDIUM Anmerkungen) |
| 4 | is_active() funktioniert korrekt | OK (1 MEDIUM Race Condition) |
| 5 | cancel() setzt _active=False und emittiert CANCELLED | OK (1 LOW: doppelt moeglich) |

## Ergebnis
**Alle 5 Pruefpunkte: BESTANDEN** -- keine CRITICAL Findings.
6 Findings insgesamt (3x MEDIUM, 3x LOW), keines davon blockiert die Funktionalitaet.
