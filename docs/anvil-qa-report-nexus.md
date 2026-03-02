# QA Report -- Nexus Mods API Integration (Settings Tab)
Datum: 2026-03-02

## Gepruefte Dateien

| Datei | Zeilen |
|-------|--------|
| `anvil/core/nexus_sso.py` | Zeile 34 (APPLICATION_SLUG) |
| `anvil/widgets/settings_dialog.py` | Zeilen 440-450 (Buttons), 529 (init), 935-964 (neue Methode), 966-1070 (Aufrufe) |
| `anvil/core/nexus_api.py` | Komplett (Referenz fuer Signal-/Slot-Pruefung) |
| `anvil/locales/*.json` | Alle 6 Locale-Dateien (i18n-Keys) |

## Git-Diff Zusammenfassung

- `nexus_sso.py`: 1 Zeile geaendert (Slug-Korrektur)
- `settings_dialog.py`: 3 `_disabled()`-Aufrufe entfernt, 1 neue Methode `_nx_update_button_states()` (32 Zeilen), 8 Aufrufe dieser Methode eingefuegt

---

## Checklisten-Pruefung

### 1. APPLICATION_SLUG ist `"nathuk-anvilorganizer"`
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/core/nexus_sso.py`, Zeile 34
- Code: `APPLICATION_SLUG = "nathuk-anvilorganizer"`
- Git-Diff bestaetigt Aenderung von `"anvilorganizer"` auf `"nathuk-anvilorganizer"`
- Verwendung in Zeile 162: `f"https://www.nexusmods.com/sso?id={self._session_id}&application={APPLICATION_SLUG}"`

### 2. Ohne API-Key: Connect + API-Key klickbar, Disconnect ausgegraut
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/widgets/settings_dialog.py`, Zeilen 955-959
- Die drei `_disabled()`-Aufrufe (frueher Zeilen 442, 446, 450) sind entfernt
- `_nx_update_button_states()` wird in `__init__` (Zeile 529) aufgerufen
- Im `else`-Zweig (kein Key): `_btn_connect.setEnabled(True)`, `_btn_api_key.setEnabled(True)`, `_btn_disconnect.setEnabled(False)`

### 3. Browser oeffnet sich mit korrekter URL inkl. `nathuk-anvilorganizer`
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/core/nexus_sso.py`, Zeile 162
- Code: `url = f"https://www.nexusmods.com/sso?id={self._session_id}&application={APPLICATION_SLUG}"`
- APPLICATION_SLUG ist jetzt `"nathuk-anvilorganizer"` (Zeile 34)
- `webbrowser.open(url)` in Zeile 163

### 4. Waehrend SSO: Connect-Button zeigt "Abbrechen", andere Buttons ausgegraut
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/widgets/settings_dialog.py`
- Zeile 979: `self._btn_connect.setText(tr("button.cancel"))` -- setzt Button-Text auf "Abbrechen"
- Zeile 981: `self._nx_update_button_states()` -- wird nach SSO-Start aufgerufen
- Zeilen 940-944: Im `sso_active`-Zweig: Connect enabled (als Abbrechen-Button), API-Key disabled, Disconnect disabled
- i18n-Key `button.cancel` existiert in allen 6 Locales

### 5. API-Key wird empfangen, in QSettings gespeichert, validate_key() aufgerufen
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/widgets/settings_dialog.py`, Zeilen 996-1004
- `_nx_on_sso_key()`: `self._nexus_api.set_api_key(api_key)` (Zeile 999)
- `settings.setValue("nexus/api_key", api_key)` (Zeile 1001)
- `self._nexus_api.validate_key()` (Zeile 1003)
- Signal-Kette: `NexusSSOLogin.key_changed` -> `_nx_on_sso_key` (verbunden in Zeile 978)

### 6. Nach Validierung: User-ID, Name, Account-Typ werden angezeigt
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/widgets/settings_dialog.py`, Zeilen 1045-1062
- `_nx_on_validated()`: setzt `_nx_uid`, `_nx_name`, `_nx_account`
- Account-Typ-Logik: Premium -> Supporter -> Standard (Zeilen 1049-1056)
- Signal: `NexusAPI.user_validated` -> `_nx_on_validated` (verbunden in Zeile 518)

### 7. Rate-Limits werden in den Feldern angezeigt
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/widgets/settings_dialog.py`, Zeilen 1072-1081
- `_nx_on_rate_limit()`: setzt `_nx_daily.setText()` und `_nx_hourly.setText()`
- Signal: `NexusAPI.rate_limit_updated` -> `_nx_on_rate_limit` (verbunden in Zeile 520)
- `NexusAPI._on_worker_finished()` liest `x-rl-daily-remaining` und `x-rl-hourly-remaining` Header (Zeilen 188-201)

### 8. Nach Validierung: Status "Verbunden." in Gruen, Disconnect klickbar, Connect+API-Key ausgegraut
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/widgets/settings_dialog.py`
- Zeile 1060: `self._nx_status_label.setText(tr("status.connected"))` -- "Verbunden."
- Zeile 1061: `self._nx_status_label.setStyleSheet("color: #4CAF50;")` -- Gruen
- Zeile 1062: `self._nx_update_button_states()` -- aktualisiert Buttons
- Zeilen 945-949: Im `has_key and self._nx_uid.text()`-Zweig: Connect disabled, API-Key disabled, Disconnect enabled

### 9. Disconnect: Felder geleert, Key aus QSettings geloescht, Buttons zurueck
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/widgets/settings_dialog.py`, Zeilen 1024-1043
- `_nx_disconnect()`:
  - `settings.remove("nexus/api_key")` (Zeile 1032)
  - `self._nexus_api.set_api_key("")` (Zeile 1033)
  - `_nx_uid.clear()`, `_nx_name.clear()`, `_nx_account.clear()`, `_nx_daily.clear()`, `_nx_hourly.clear()` (Zeilen 1034-1038)
  - `self._nx_update_button_states()` (Zeile 1043) -- setzt Buttons auf "Nicht verbunden"

### 10. Manueller API-Key: InputDialog, Key wird gespeichert und validiert
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/widgets/settings_dialog.py`, Zeilen 1006-1022
- `_nx_enter_api_key()`: Verwendet `get_text_input()` (aus `anvil/core/ui_helpers.py`)
- Key wird gespeichert: `settings.setValue("nexus/api_key", key.strip())` (Zeile 1018)
- Key wird gesetzt: `self._nexus_api.set_api_key(key.strip())` (Zeile 1016)
- Validierung: `self._nexus_api.validate_key()` (Zeile 1021)
- Button-States aktualisiert: `self._nx_update_button_states()` (Zeile 1022)
- Identischer Ablauf wie SSO (gleiche Signals fuehren zu gleichen Slots)

### 11. Fehlerfall: Fehlermeldung in Log + Status, Connect+API-Key bleiben klickbar
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/widgets/settings_dialog.py`, Zeilen 1064-1070
- `_nx_on_error()`: Schreibt Fehler in Log und Status-Label
- Zeile 1069: `self._nx_status_label.setStyleSheet("color: #F44336;")` -- Rot
- Zeile 1070: `self._nx_update_button_states()` -- aktualisiert Buttons
- Im Fehlerfall: `has_key` ist True (Key wurde ja gesetzt), `_nx_uid.text()` ist leer (Validierung schlug fehl)
- Dadurch greift Zeile 950-954: Connect enabled, API-Key enabled, Disconnect enabled
- Dass Disconnect auch enabled ist, entspricht der Checkliste Punkt 11 (Fehler-Zustand laut Feature-Doku Tabelle Zeile 56)

### 12. SSO-Abbruch: Flow gestoppt, Buttons zurueck zum Nicht-verbunden-Zustand
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/widgets/settings_dialog.py`, Zeilen 966-973
- `_nx_connect_sso()`: Wenn SSO aktiv ist, wird `self._sso_login.cancel()` aufgerufen
- Button-Text zurueck: `self._btn_connect.setText(tr("button.connect_nexus"))` (Zeile 971)
- `self._nx_update_button_states()` (Zeile 972)
- Nach cancel(): `_sso_login.is_active()` gibt False zurueck (NexusSSOLogin.cancel() setzt `_active = False`)
- Ohne Key: Buttons gehen in "Nicht verbunden"-Zustand

### 13. Gespeicherter Key wird beim Oeffnen automatisch validiert
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/widgets/settings_dialog.py`, Zeilen 522-529
- `saved_key = settings.value("nexus/api_key", "")` (Zeile 522)
- Wenn Key vorhanden: `self._nexus_api.set_api_key(saved_key)` und `self._nexus_api.validate_key()` (Zeilen 524-526)
- Bei Erfolg: `user_validated` Signal -> `_nx_on_validated()` -> Verbunden-Zustand angezeigt
- `self._nx_update_button_states()` wird danach aufgerufen (Zeile 529)

### 14. Kein Button hat Tooltip "Noch nicht verfuegbar"
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/widgets/settings_dialog.py`, Zeilen 961-964
- `_nx_update_button_states()` setzt fuer alle 3 Buttons: `setToolTip("")`
- Die drei `_disabled()`-Aufrufe (die den Tooltip "Noch nicht verfuegbar" setzten) sind entfernt
- `_nx_update_button_states()` wird bei Init und jedem State-Wechsel aufgerufen

### 15. Optionen, Server, NXM-Handler, Cache-Button bleiben disabled
**Ergebnis: ERFUELLT** ✅
- Datei: `anvil/widgets/settings_dialog.py`
- Zeile 476: `_disabled(cb)` -- Optionen-Checkboxen (Endorsement, Tracking, Category, Counter)
- Zeile 482: `_disabled(btn_link)` -- NXM-Handler-Button
- Zeile 484: `_disabled(QPushButton(...))` -- Cache-leeren-Button
- Zeile 498: `_disabled(known_list)` -- Known-Server-Liste
- Zeile 506: `_disabled(pref_list)` -- Preferred-Server-Liste
- Alle diese `_disabled()`-Aufrufe sind unveraendert im Code

### 16. restart.sh startet ohne Fehler
**Ergebnis: NICHT GEPRUEFT** ⚠️
- Laufzeit-Test wurde nicht durchgefuehrt (reine Code-Review)
- Alle Imports sind vorhanden (`NexusAPI`, `NexusSSOLogin`, `QSettings`)
- `_nx_update_button_states()` greift nur auf existierende Instanzvariablen zu
- Keine offensichtlichen Syntaxfehler oder fehlenden Referenzen
- Empfehlung: Vor Commit `./restart.sh` ausfuehren

---

## Zusaetzliche Findings

### [LOW] Doppelter i18n-Key `nexus_error` in settings-Namespace
- Datei: `anvil/locales/de.json`, Zeile 404 und 690
- Problem: Der Key `nexus_error` existiert zweimal -- einmal im `status`-Namespace (Zeile 404: "Nexus Fehler: {message}") und einmal im `settings`-Namespace (Zeile 690: "Fehler: {message}"). Da sie in verschiedenen Namespaces liegen (`status.nexus_error` vs `settings.nexus_error`), funktioniert es technisch korrekt. Der Code verwendet `tr("settings.nexus_error", ...)` was auf den richtigen Key zugreift.
- Severity: LOW (kein Bug, aber potentiell verwirrend bei Wartung)

### [LOW] Pong-Frame in _ws_recv_text sendet ungemaskte Payload-Daten
- Datei: `anvil/core/nexus_sso.py`, Zeilen 330-331
- Problem: Der Pong-Response sendet `bytearray([0x8A, 0x80]) + os.urandom(4)` -- das ist ein Pong mit MASK-Bit und 0-Byte-Payload, was technisch korrekt ist, aber der Payload aus dem Ping wird nicht zurueckgeschickt (RFC 6455 Abschnitt 5.5.3: "A Pong frame [...] MUST have identical Application Data as found in the message body of the Ping frame being replied to"). In der Praxis funktioniert es mit Nexus, da Ping-Frames typischerweise keine signifikante Payload haben.
- Severity: LOW (Feature-Doku sagt "Ping-Rekursion-Fix nicht in Scope")
- Fix: Nicht in Scope dieses Features

### [LOW] `_ws_recv_text` rekursiver Aufruf bei Ping
- Datei: `anvil/core/nexus_sso.py`, Zeile 335
- Problem: Bei einem Ping-Frame ruft `_ws_recv_text` sich selbst rekursiv auf. Bei vielen aufeinanderfolgenden Pings koennte theoretisch ein Stack-Overflow auftreten. In der Praxis unrealistisch, da Nexus nur gelegentlich Pings sendet.
- Severity: LOW (Feature-Doku sagt explizit "Ping-Rekursion-Fix nicht in Scope")

### [LOW] setStyleSheet im Log-Widget
- Datei: `anvil/widgets/settings_dialog.py`, Zeile 458
- Problem: `self._nx_log.setStyleSheet("QListWidget { font-size: 11px; }")` -- laut CLAUDE.md soll `setStyleSheet()` in neuen Widgets vermieden werden, da QSS-Theme vererbt wird. Allerdings ist diese Zeile nicht Teil der aktuellen Aenderung (existierte bereits vorher).
- Severity: LOW (bestehendes Problem, nicht durch diese Aenderung eingefuehrt)

---

## Signal/Slot-Pruefung

| Signal | Quelle | Slot | Verbindung | Status |
|--------|--------|------|-----------|--------|
| `NexusAPI.user_validated(dict)` | `nexus_api.py:75` | `_nx_on_validated` | Zeile 518 | OK |
| `NexusAPI.request_error(str,str)` | `nexus_api.py:73` | `_nx_on_error` | Zeile 519 | OK |
| `NexusAPI.rate_limit_updated(int,int)` | `nexus_api.py:74` | `_nx_on_rate_limit` | Zeile 520 | OK |
| `NexusSSOLogin.state_changed(int,str)` | `nexus_sso.py:190` | `_nx_on_sso_state` | Zeile 977 | OK |
| `NexusSSOLogin.key_changed(str)` | `nexus_sso.py:189` | `_nx_on_sso_key` | Zeile 978 | OK |
| `_btn_connect.clicked` | QPushButton | `_nx_connect_sso` | Zeile 441 | OK |
| `_btn_api_key.clicked` | QPushButton | `_nx_enter_api_key` | Zeile 444 | OK |
| `_btn_disconnect.clicked` | QPushButton | `_nx_disconnect` | Zeile 447 | OK |

Alle Signal-Verbindungen sind korrekt. Keine verwaisten Signale oder fehlenden Slots.

## Aufruf-Stellen von `_nx_update_button_states()`

| Nr | Methode | Zeile | Kontext | OK? |
|----|---------|-------|---------|-----|
| 1 | `__init__` | 529 | Nach Key-Lade-Check | OK |
| 2 | `_nx_connect_sso` (Cancel-Pfad) | 972 | Nach SSO-Abbruch | OK |
| 3 | `_nx_connect_sso` (Start-Pfad) | 981 | Nach SSO-Start | OK |
| 4 | `_nx_on_sso_state` | 994 | Nach SSO-State-Wechsel (Terminal States) | OK |
| 5 | `_nx_on_sso_key` | 1004 | Nach Key-Empfang | OK |
| 6 | `_nx_enter_api_key` | 1022 | Nach manuellem Key | OK |
| 7 | `_nx_disconnect` | 1043 | Nach Trennung | OK |
| 8 | `_nx_on_validated` | 1062 | Nach erfolgreicher Validierung | OK |
| 9 | `_nx_on_error` | 1070 | Nach Fehler | OK |

Feature-Doku fordert 9 Aufrufstellen -- alle 9 sind vorhanden.

---

## Ergebnis: 15/16 Punkte erfuellt, 1 Punkt nicht geprueft (Laufzeit)

| Punkt | Status |
|-------|--------|
| 1. APPLICATION_SLUG korrekt | ✅ |
| 2. Buttons ohne Key: Connect+API-Key an, Disconnect aus | ✅ |
| 3. Browser-URL mit korrektem Slug | ✅ |
| 4. SSO-Modus: Abbrechen-Text + andere Buttons aus | ✅ |
| 5. Key empfangen, gespeichert, validiert | ✅ |
| 6. User-Info nach Validierung angezeigt | ✅ |
| 7. Rate-Limits angezeigt | ✅ |
| 8. Verbunden-Status: Gruen + Disconnect einzig aktiver Button | ✅ |
| 9. Disconnect: alles zurueckgesetzt | ✅ |
| 10. Manueller Key: InputDialog + identischer Flow | ✅ |
| 11. Fehlerfall: Meldung + Buttons klickbar | ✅ |
| 12. SSO-Abbruch: Flow gestoppt, Buttons zurueck | ✅ |
| 13. Gespeicherter Key: Auto-Validierung | ✅ |
| 14. Keine "Noch nicht verfuegbar"-Tooltips | ✅ |
| 15. Disabled-Elemente unveraendert | ✅ |
| 16. restart.sh ohne Fehler | ⚠️ Nicht geprueft (Laufzeit) |

## Gesamtergebnis

**NEEDS MANUAL TEST** -- Alle 15 Code-basierten Punkte sind erfuellt. Punkt 16 (restart.sh startet ohne Fehler) erfordert einen Laufzeit-Test. Es gibt keine CRITICAL oder HIGH Findings. Die 4 LOW-Findings betreffen bestehenden Code, der nicht Teil dieser Aenderung ist, oder sind explizit als "nicht in Scope" deklariert.

Nach erfolgreichem `./restart.sh`: **READY FOR COMMIT**
