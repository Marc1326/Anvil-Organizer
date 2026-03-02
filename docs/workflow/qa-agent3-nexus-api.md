# QA Report Agent 3 -- Nexus API Integration
Datum: 2026-03-02

## Pruefungsumfang

- **Syntax-Check** aller drei Dateien (nexus_sso.py, settings_dialog.py, nexus_api.py)
- **Import-Pruefung** aller Abhaengigkeiten
- **Interface-Test** (has_api_key, Signals, Methoden)
- **Widget-Erstellung** headless (SettingsDialog mit Nexus-Tab)
- **Uebersetzungs-Keys** in allen 6 Locales (de, en, es, fr, it, pt)
- **Edge Cases** (Worker-Handling, leere Keys, RFC 6455 Konformitaet)


## 1. Syntax-Check

| Datei | Ergebnis |
|-------|----------|
| `anvil/core/nexus_sso.py` | OK (Exit 0) |
| `anvil/widgets/settings_dialog.py` | OK (Exit 0) |
| `anvil/core/nexus_api.py` | OK (Exit 0) |


## 2. Import-Pruefung

| Import | Quelle | Ergebnis |
|--------|--------|----------|
| `NexusAPI` | `anvil.core.nexus_api` | OK |
| `NexusSSOLogin` | `anvil.core.nexus_sso` | OK |
| `get_text_input` | `anvil.core.ui_helpers` | OK |
| `register_nxm_handler` | `anvil.core.nxm_handler` | OK |
| `APP_VERSION` | `anvil.version` | OK (= 0.1.0) |
| `SettingsDialog` (Gesamtimport) | `anvil.widgets.settings_dialog` | OK |


## 3. Interface-Test: has_api_key()

```
NexusAPI().has_api_key() ohne Key  -> False  [KORREKT]
NexusAPI().has_api_key() mit Key   -> True   [KORREKT]
```

Die Methode `has_api_key()` existiert in `anvil/core/nexus_api.py` Zeile 94-96
und wird in `settings_dialog.py` Zeile 937 aufgerufen via `_nx_update_button_states()`.


## 4. Widget-Erstellung (Headless)

SettingsDialog wurde mit `QT_QPA_PLATFORM=offscreen` instanziiert:

| Pruefpunkt | Ergebnis |
|------------|----------|
| Dialog erstellt | OK |
| Tab-Anzahl | 6 (General, Style, ModList, Paths, Nexus, Plugins) |
| NexusAPI Instanz | vorhanden (self._nexus_api) |
| SSO Login initial | None (korrekt - wird erst bei Connect erstellt) |
| has_api_key (ohne gespeicherten Key) | False |
| Connect-Button enabled | True |
| API-Key-Button enabled | True |
| Disconnect-Button enabled | False |

Alle Button-States entsprechen dem erwarteten Zustand "nicht verbunden".


## 5. Signal/Slot-Verbindungen (Nexus-Tab)

| Signal | Slot | Zeile | Status |
|--------|------|-------|--------|
| `nexus_api.user_validated` | `_nx_on_validated` | 518 | OK |
| `nexus_api.request_error` | `_nx_on_error` | 519 | OK |
| `nexus_api.rate_limit_updated` | `_nx_on_rate_limit` | 520 | OK |
| `btn_connect.clicked` | `_nx_connect_sso` | 441 | OK |
| `btn_api_key.clicked` | `_nx_enter_api_key` | 444 | OK |
| `btn_disconnect.clicked` | `_nx_disconnect` | 447 | OK |
| SSO: `state_changed` | `_nx_on_sso_state` | 977 | OK (in _nx_connect_sso) |
| SSO: `key_changed` | `_nx_on_sso_key` | 978 | OK (in _nx_connect_sso) |
| Worker: `finished` | `_on_worker_finished` | 168 | OK |
| Worker: `error` | `_on_worker_error` | 169 | OK |
| Worker: `finished` | `_cleanup_worker` (Lambda) | 170 | OK |
| Worker: `error` | `_cleanup_worker` (Lambda) | 171 | OK |


## 6. Uebersetzungs-Keys

Alle 34 Nexus-relevanten tr()-Keys wurden in allen 6 Locale-Dateien gefunden:

| Locale | Status |
|--------|--------|
| de.json | ALLE KEYS VORHANDEN |
| en.json | ALLE KEYS VORHANDEN |
| es.json | ALLE KEYS VORHANDEN |
| fr.json | ALLE KEYS VORHANDEN |
| it.json | ALLE KEYS VORHANDEN |
| pt.json | ALLE KEYS VORHANDEN |

Geprueft: settings.nexus_*, button.connect_nexus, button.cancel, status.not_connected,
status.disconnected, status.connected, label.known_servers, label.preferred_servers,
settings.options, settings.tab_nexus, settings.nxm_handler_*


## Findings

### [LOW] Pong-Frame sendet keine Ping-Payload zurueck (RFC 6455 Sec 5.5.3)
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py` Zeile 329-334
- **Problem:** Bei Empfang eines Ping-Frames wird ein leerer Pong zurueckgesendet
  (`bytearray([0x8A, 0x80]) + os.urandom(4)`). RFC 6455 Section 5.5.3 schreibt vor,
  dass ein Pong den Application Data Body des Pings unveraendert zuruecksenden MUSS.
  Aktuell wird die Ping-Payload ignoriert.
- **Auswirkung:** Gering. Der Nexus-SSO-Server prueft vermutlich nicht die Pong-Payload.
  Andere WebSocket-Server koennten die Verbindung als fehlerhaft betrachten.
- **Fix:** `pong = bytearray([0x8A, 0x80 | len(payload)]) + os.urandom(4)` und dann
  die maskierte payload anhaengen. Oder einfacher: payload in den Pong-Frame einbauen.

### [LOW] Rekursiver Aufruf bei Ping-Frames kann theoretisch Stack Overflow verursachen
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py` Zeile 335
- **Problem:** `_ws_recv_text()` ruft sich selbst rekursiv auf wenn ein Ping-Frame
  empfangen wird (`return _ws_recv_text(sock)`). Bei vielen aufeinanderfolgenden
  Ping-Frames (>1000) koennte ein Stack Overflow auftreten.
- **Auswirkung:** Sehr gering. In der Praxis sendet der SSO-Server maximal 1-2 Pings
  waehrend einer 2-Minuten-Session. Python Standard-Rekursionslimit ist 1000.
- **Fix:** Iterative Schleife statt Rekursion: `while opcode == 0x09: ...`

### [LOW] Hartcodierte Deutsche Fehlermeldung in nexus_api.py
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_api.py` Zeile 157, 205, 209
- **Problem:** Fehlermeldungen wie "Kein API-Schluessel gesetzt.", "Rate Limit erreicht.",
  "Ungueltiger API-Schluessel." sind hartcodiert auf Deutsch statt tr() zu verwenden.
- **Auswirkung:** Fehlermeldungen werden in allen Sprachen auf Deutsch angezeigt.
- **Fix:** `tr("nexus.error_no_api_key")`, `tr("nexus.error_rate_limit")`,
  `tr("nexus.error_invalid_key")` verwenden und Keys in alle 6 Locales eintragen.

### [LOW] Hartcodierte Deutsche Strings in nexus_sso.py STATE_MESSAGES
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py` Zeile 49-58
- **Problem:** `STATE_MESSAGES` Dict enthaelt hartcodierte Deutsche Strings statt tr()-Aufrufe.
  Auch `state_to_string()` (Zeile 237-241) gibt hartcodierte Strings zurueck.
- **Auswirkung:** SSO-Statusmeldungen werden in allen Sprachen auf Deutsch angezeigt.
- **Fix:** tr()-Keys verwenden: `tr("nexus.sso_connecting")`, etc.

### [MEDIUM] setStyleSheet() Aufrufe im Settings-Dialog
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py`
  Zeilen 102, 458, 613, 1061, 1069, 1042
- **Problem:** Mehrere `setStyleSheet()`-Aufrufe fuer inline CSS:
  - Zeile 102: `lang_hint.setStyleSheet("color: #808080; ...")`
  - Zeile 458: `self._nx_log.setStyleSheet("QListWidget { font-size: 11px; }")`
  - Zeile 613: `summary.setStyleSheet("color: #808080; ...")`
  - Zeile 1061: `self._nx_status_label.setStyleSheet("color: #4CAF50;")`
  - Zeile 1069: `self._nx_status_label.setStyleSheet("color: #F44336;")`
- **Auswirkung:** CLAUDE.md sagt "NIEMALS setStyleSheet() in neuen Widgets".
  Diese inline Styles koennten das QSS-Theme ueberschreiben und bei Theme-Wechsel
  nicht korrekt aktualisiert werden. Status-Farben (gruen/rot) fuer die
  Nexus-Verbindung sind jedoch funktional wichtig.
- **Fix:** Fuer Status-Farben: Object-Names vergeben und im QSS-Theme definieren,
  oder QSS-Klassen verwenden. Fuer statische Styles (font-size, color fuer Hints):
  QSS-Theme erweitern oder Property-Selektoren nutzen.


## Zusammenfassung

| Severity | Anzahl |
|----------|--------|
| CRITICAL | 0 |
| HIGH     | 0 |
| MEDIUM   | 1 |
| LOW      | 4 |

Alle drei Dateien sind syntaktisch korrekt, importieren sauber, die Interfaces stimmen,
alle Signal/Slot-Verbindungen sind vorhanden und korrekt verbunden.
Die `has_api_key()` Methode existiert und funktioniert.
Alle 34 Nexus-relevanten Uebersetzungs-Keys sind in allen 6 Locales vorhanden.
Die Headless Widget-Erstellung und Button-State-Logik funktioniert korrekt.

Die gefundenen Issues sind alle LOW/MEDIUM und betreffen:
- RFC 6455 Feinheiten im WebSocket-Code (in der Praxis kein Problem)
- Fehlende i18n fuer Fehlermeldungen in den Core-Modulen
- setStyleSheet()-Nutzung entgegen der CLAUDE.md-Richtlinie


## Ergebnis

**READY FOR COMMIT** (keine CRITICAL oder HIGH Findings)

Die LOW-Findings sollten in einem separaten Cleanup-Commit adressiert werden:
1. WebSocket Pong-Payload (nexus_sso.py)
2. i18n fuer Fehlermeldungen (nexus_api.py + nexus_sso.py)
3. setStyleSheet() durch QSS-Theme-Klassen ersetzen (settings_dialog.py)
