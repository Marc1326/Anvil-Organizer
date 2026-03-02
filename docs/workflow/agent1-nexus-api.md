# Agent 1: Nexus SSO Analysis (nexus_sso.py)

## 1. SSO-Flow Übersicht

Die Datei `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py` (352 Zeilen) implementiert den Nexus Mods SSO-Login über WebSocket. Der Flow ist wie folgt:

### Schritt-für-Schritt-Flow:

1. **`NexusSSOLogin.start()`** wird aufgerufen (z.B. durch den "Verbinden"-Button in `settings_dialog.py`)
2. Eine UUID wird als `session_id` generiert
3. Ein `_WebSocketWorker` (QThread) wird erstellt und gestartet
4. Der Worker verbindet sich per SSL-Socket zu `wss://sso.nexusmods.com`
5. Ein manueller WebSocket-Upgrade-Handshake wird durchgeführt (RFC 6455)
6. Die Session-Nachricht wird gesendet: `{"id": "<uuid>", "token": null, "protocol": 2}`
7. State wechselt zu `WAITING_TOKEN`
8. **Erste Antwort** vom Server: `{"success": true, "data": {"connection_token": "..."}}`
   - Browser wird geöffnet: `https://www.nexusmods.com/sso?id=<uuid>&application=anvilorganizer`
   - State wechselt zu `WAITING_BROWSER`
9. **User autorisiert** im Browser auf nexusmods.com
10. **Zweite Antwort** vom Server: `{"success": true, "data": {"api_key": "..."}}`
    - Signal `key_received` wird emittiert
    - State wechselt zu `FINISHED`
11. WebSocket-Close-Frame wird gesendet, Socket wird geschlossen

### Architektur-Aufbau:

| Klasse | Rolle |
|--------|-------|
| `_SSOState` | Enum-artige Klasse für Zustände (0-7) |
| `STATE_MESSAGES` | Deutsche Klartext-Zuordnung zu States |
| `_WebSocketWorker(QThread)` | Hintergrund-Thread für den WebSocket-Handshake |
| `NexusSSOLogin(QObject)` | Öffentliche API-Klasse, delegiert an Worker |
| `_ws_*` Funktionen | Minimaler WebSocket-Client (RFC 6455) mit stdlib |

## 2. APPLICATION_SLUG Vorkommen

Der Slug `"anvilorganizer"` kommt im gesamten Projekt **genau an einem Ort** vor:

- **Zeile 34** in `anvil/core/nexus_sso.py`: `APPLICATION_SLUG = "anvilorganizer"`
- **Zeile 162** in derselben Datei: Verwendung in der Browser-URL

Die Konstante ist sauber als Modul-Level-Variable definiert und wird nur innerhalb der Datei verwendet. Es gibt keine Duplizierung.

**MO2-Vergleich:** MO2 verwendet `"modorganizer2"` als hardcoded String in der URL-Konstante (Zeile 48, `nxmaccessmanager.cpp`):
```cpp
const QString NexusSSOPage("https://www.nexusmods.com/sso?id=%1&application=modorganizer2");
```

**Wichtiger Hinweis:** Der Docstring in Zeile 11-12 warnt:
> *"The application parameter MUST be registered with Nexus Mods. Until registered, use manual API key entry as fallback."*

## 3. Vollständigkeit des Flows

### Was ist vollständig implementiert:

- WebSocket-Verbindung über SSL (stdlib, kein QtNetwork)
- WebSocket-Upgrade-Handshake (RFC 6455 konform)
- Maskierte Text-Frames senden (Client-Pflicht nach RFC)
- Text-Frames empfangen (mit/ohne Maske)
- Close-Frame senden/empfangen
- Ping/Pong-Handling (Zeile 329-335)
- Session-ID-Generierung (uuid4)
- JSON-Protokoll mit Nexus SSO
- Browser-Öffnung mit `webbrowser.open()`
- API-Key-Extraktion aus der Server-Antwort
- State-Machine mit 8 Zuständen
- Abbruch-Mechanismus (cancel)
- Integration in `settings_dialog.py` (3 Buttons: Verbinden, API-Key manuell, Trennen)
- Key-Speicherung in QSettings (`nexus/api_key`)
- Key-Validierung nach Empfang via `NexusAPI.validate_key()`

### Was FEHLT oder ist ABWEICHEND von MO2:

| Aspekt | MO2 | Anvil | Status |
|--------|-----|-------|--------|
| WebSocket-Implementierung | Qt `QWebSocket` (event-driven) | Stdlib `ssl+socket` in QThread (blocking) | Funktional äquivalent, aber anders |
| Timeout-Strategie | 10s Timer für initiale Verbindung, wird nach `connection_token` gestoppt | Fester 120s `settimeout` auf dem Socket für die gesamte Receive-Loop | **Lücke** |
| SSL-Fehlerbehandlung | Dedizierter `onSslErrors` Handler | Implizit via `ssl.create_default_context()` | OK, aber weniger Feedback |
| `"token": null` vs. fehlendes Feld | MO2 sendet `{"id": ..., "protocol": 2}` OHNE "token"-Feld | Anvil sendet `{"id": ..., "token": null, "protocol": 2}` | Funktioniert vermutlich, aber abweichend |
| Key-Validierung mit Retry | `NexusKeyValidator` mit mehreren Attempts und Timeouts | Einmaliger `validate_key()` Aufruf | **Lücke** |
| Button-State-Management | Dedizierte `updateState()` Methode | Buttons initial mit `_disabled()` deaktiviert | **Lücke** |

## 4. Signals

### `_WebSocketWorker` (interner Thread):

| Signal | Parameter | Beschreibung |
|--------|-----------|--------------|
| `state_changed` | `(int, str)` | State-ID + Detail-Text |
| `key_received` | `(str)` | Der empfangene API-Key |
| `error_occurred` | `(str)` | Fehlermeldung |
| `finished` | (von QThread geerbt) | Thread beendet |

### `NexusSSOLogin` (öffentliche API):

| Signal | Parameter | Beschreibung |
|--------|-----------|--------------|
| `key_changed` | `(str)` | API-Key empfangen |
| `state_changed` | `(int, str)` | State-Änderung |

### Signal-Flow:

```
[User klickt "Verbinden"]
  → SettingsDialog._nx_connect_sso()
  → NexusSSOLogin.start()
    → _WebSocketWorker erstellt + gestartet
    → worker.state_changed → self._on_state → self.state_changed
    → worker.key_received  → self._on_key   → self.key_changed
    → worker.error_occurred → self._on_error → self.state_changed(ERROR, msg)
    → worker.finished      → self._on_thread_done

[Im Thread: _WebSocketWorker.run()]
  → SSL-Verbindung → WS-Upgrade → Session-Nachricht
  → Warte auf connection_token → Browser öffnen
  → Warte auf api_key

[Zurück im Main-Thread:]
  → SettingsDialog._nx_on_sso_key(api_key)
    → NexusAPI.set_api_key(api_key)
    → QSettings.setValue("nexus/api_key", api_key)
    → NexusAPI.validate_key()
      → request_finished → _nx_on_validated() → UI aktualisieren
```

## 5. Fehlerbehandlung

### Behandelte Fehler:

| Fehlerfall | Handling |
|------------|----------|
| Socket-Verbindung fehlgeschlagen | Exception → `error_occurred` Signal |
| WS-Upgrade fehlgeschlagen (nicht 101) | `error_occurred` mit Response-Auszug |
| Leerer Chunk beim WS-Upgrade | `CLOSED_BY_REMOTE` State |
| Socket-Timeout (120s) | `TIMEOUT` State |
| Socket-Fehler (OSError) | `TIMEOUT` State |
| Leerer Frame | `CLOSED_BY_REMOTE` State |
| Server meldet `success: false` | `error_occurred` mit Fehlermeldung |
| Abbruch durch User | `cancel()` setzt `_cancelled`, schließt Socket |
| Close-Frame vom Server | `_ws_recv_text` gibt `None` zurück → `CLOSED_BY_REMOTE` |
| Ping-Frame vom Server | Automatischer Pong + weiter empfangen |

### NICHT behandelte Fehler:

1. **JSON-Decode-Error** in der Receive-Loop — wird vom äußeren `try/except` gefangen
2. **Kein separater Timeout** für die initiale Verbindung vs. Browser-Wartezeit
3. **Rekursion bei Ping** — `_ws_recv_text` ruft sich selbst rekursiv auf (theoretisches Stack-Overflow-Risiko)
4. **Kein Retry-Mechanismus** bei Verbindungsfehler

## 6. Lücken und Probleme

### Kritisch:

1. **Buttons dauerhaft deaktiviert**: Alle drei Nexus-Buttons sind mit `_disabled()` initial deaktiviert. Es gibt keinen Code der sie wieder aktiviert. **Der User kann den SSO-Flow aktuell gar nicht nutzen.**

2. **APPLICATION_SLUG muss geändert werden**: Der offiziell bei Nexus registrierte Slug ist `"nathuk-anvilorganizer"`, nicht `"anvilorganizer"`.

### Hoch:

3. **Timeout-Differenz zu MO2**: MO2 stoppt den Timer nach Erhalt des connection_token. Anvil hat einen festen 120s Socket-Timeout für ALLES — wenn der User länger als 2 Minuten braucht, kommt ein Timeout.

4. **Doppelte NexusAPI-Instanz**: MainWindow und SettingsDialog haben jeweils eigene `NexusAPI`-Instanzen ohne Synchronisation.

### Mittel:

5. **STATE_MESSAGES hardcoded auf Deutsch** statt über `tr()` (i18n)
6. **Kein Logging** — weder `debug.log` noch andere Mechanismen
7. **Rekursion bei Ping-Frames** — sollte durch Schleife ersetzt werden

## 7. Empfehlungen

### Sofort-Maßnahmen (Priorität 1):

1. **APPLICATION_SLUG ändern**: `"anvilorganizer"` → `"nathuk-anvilorganizer"`
2. **Buttons aktivieren**: `_disabled()` entfernen, dynamische Button-States implementieren

### Kurzfristig (Priorität 2):

3. **Timeout-Strategie überarbeiten**: Separaten kurzen Timeout für initiale Verbindung, keinen/langen Timeout für Browser-Autorisierung
4. **`"token": null` entfernen**: Feld aus Session-Nachricht entfernen (MO2-Kompatibilität)
5. **Button-State-Management** nach MO2-Vorbild

### Mittelfristig (Priorität 3):

6. **NexusAPI-Singleton oder Signal-Bridge** zwischen MainWindow und Settings
7. **STATE_MESSAGES internationalisieren** via `tr()`
8. **Ping-Rekursion** durch Schleife ersetzen
9. **Logging** hinzufügen
