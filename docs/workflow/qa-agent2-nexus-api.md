# QA Report -- Nexus API: Signal/Slot-Flow, Validierung und Button-States
Datum: 2026-03-02

---

## Pruefung 1: validate_key() wird korrekt aufgerufen

### Nach SSO-Key-Empfang
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py:1003`
- **Ergebnis:** KORREKT
- `_nx_on_sso_key()` empfaengt den Key via `NexusSSOLogin.key_changed` Signal,
  ruft `self._nexus_api.set_api_key(api_key)` (Zeile 999) und danach
  `self._nexus_api.validate_key()` (Zeile 1003) auf.
- Reihenfolge ist korrekt: Erst Key setzen, dann validieren.

### Nach manuellem Key
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py:1021`
- **Ergebnis:** KORREKT
- `_nx_enter_api_key()` prueft `if ok and key.strip():` (Zeile 1013),
  setzt den Key (Zeile 1016) und ruft `validate_key()` (Zeile 1021) auf.

### Beim Laden eines gespeicherten Keys
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py:526`
- **Ergebnis:** KORREKT
- `saved_key = settings.value("nexus/api_key", "")` (Zeile 522), dann
  `self._nexus_api.set_api_key(saved_key)` (Zeile 524) und
  `self._nexus_api.validate_key()` (Zeile 526).

---

## Pruefung 2: Signal-Verbindungen

### NexusAPI Signale (nexus_api.py)
| Signal | Definiert | Verbunden in settings_dialog.py |
|--------|-----------|-------------------------------|
| `user_validated(dict)` | Zeile 75 | Zeile 518: `.connect(self._nx_on_validated)` |
| `request_error(str, str)` | Zeile 73 | Zeile 519: `.connect(self._nx_on_error)` |
| `rate_limit_updated(int, int)` | Zeile 74 | Zeile 520: `.connect(self._nx_on_rate_limit)` |
| `request_finished(str, object)` | Zeile 72 | NICHT verbunden im SettingsDialog |

- **Ergebnis:** KORREKT -- `request_finished` wird im SettingsDialog nicht benoetigt
  (nur fuer spaeteren Mod-Download relevant, wird in `mainwindow.py:258` verbunden).

### NexusSSOLogin Signale (nexus_sso.py)
| Signal | Definiert | Verbunden in settings_dialog.py |
|--------|-----------|-------------------------------|
| `key_changed(str)` | Zeile 189 | Zeile 978: `.connect(self._nx_on_sso_key)` |
| `state_changed(int, str)` | Zeile 190 | Zeile 977: `.connect(self._nx_on_sso_state)` |

- **Ergebnis:** KORREKT -- Beide Signale korrekt verbunden in `_nx_connect_sso()`.

### Signal-Signaturen stimmen ueberein
- `user_validated(dict)` -> `_nx_on_validated(self, user_info: dict)` -- PASST
- `request_error(str, str)` -> `_nx_on_error(self, tag: str, message: str)` -- PASST
- `rate_limit_updated(int, int)` -> `_nx_on_rate_limit(self, daily: int, hourly: int)` -- PASST
- `key_changed(str)` -> `_nx_on_sso_key(self, api_key: str)` -- PASST
- `state_changed(int, str)` -> `_nx_on_sso_state(self, state: int, detail: str)` -- PASST

---

## Pruefung 3: User-Info nach Validierung

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py:1045-1062`
- **Ergebnis:** KORREKT

```python
def _nx_on_validated(self, user_info: dict) -> None:
    self._nx_uid.setText(str(user_info.get("user_id", "")))       # user_id
    self._nx_name.setText(user_info.get("name", ""))               # name
    is_premium = user_info.get("is_premium", False)                # is_premium
    is_supporter = user_info.get("is_supporter", False)            # is_supporter
    # ... Account-Typ korrekt abgeleitet: Premium > Supporter > Standard
    self._nx_account.setText(account_type)
```

- Alle 4 Felder (user_id, name, is_premium, is_supporter) werden korrekt aus dem dict gelesen
- Konto-Typ wird korrekt priorisiert: Premium > Supporter > Standard
- Status-Label wird auf "Verbunden" gesetzt mit gruener Farbe (#4CAF50)
- Log-Eintraege werden korrekt hinzugefuegt

---

## Pruefung 4: QSettings -- nexus/api_key

| Operation | Stelle | Code |
|-----------|--------|------|
| **Laden** | settings_dialog.py:522 | `settings.value("nexus/api_key", "")` |
| **Speichern (SSO)** | settings_dialog.py:1001 | `settings.setValue("nexus/api_key", api_key)` |
| **Speichern (Manual)** | settings_dialog.py:1018 | `settings.setValue("nexus/api_key", key.strip())` |
| **Loeschen** | settings_dialog.py:1032 | `settings.remove("nexus/api_key")` |
| **Laden (MainWindow)** | mainwindow.py:254 | `settings.value("nexus/api_key", "")` |

- **Ergebnis:** KORREKT
- Key wird konsistent unter `"nexus/api_key"` gespeichert, geladen und geloescht.
- Der Key wird AUCH in `mainwindow.py:254` geladen -- das Feature ist also nicht nur UI,
  sondern wird ausserhalb des Settings-Dialogs verwendet.

---

## Pruefung 5: _nx_update_button_states() -- 9 Aufrufstellen

Die Methode ist definiert in Zeile 935 und wird an folgenden Stellen aufgerufen:

| Nr. | Kontext | Zeile | Korrekt? |
|-----|---------|-------|----------|
| 1 | **Init** (nach Key-Laden/Validierung) | 529 | JA |
| 2 | **SSO Cancel** (in _nx_connect_sso) | 972 | JA |
| 3 | **SSO Start** (in _nx_connect_sso) | 981 | JA |
| 4 | **SSO State End** (in _nx_on_sso_state) | 994 | JA |
| 5 | **SSO Key empfangen** (in _nx_on_sso_key) | 1004 | JA |
| 6 | **Enter API Key** (in _nx_enter_api_key) | 1022 | JA |
| 7 | **Disconnect** (in _nx_disconnect) | 1043 | JA |
| 8 | **On Validated** (in _nx_on_validated) | 1062 | JA |
| 9 | **On Error** (in _nx_on_error) | 1070 | JA |

- **Ergebnis:** KORREKT -- Alle 9 Stellen vorhanden und an den richtigen Positionen.

### Analyse der Button-Logik (_nx_update_button_states):

```
SSO aktiv:     Connect=AN (als "Abbrechen"), API-Key=AUS, Disconnect=AUS
Verbunden:     Connect=AUS, API-Key=AUS, Disconnect=AN
Key aber !val: Connect=AN, API-Key=AN, Disconnect=AN
Nicht verb.:   Connect=AN, API-Key=AN, Disconnect=AUS
```

- Die Logik ist korrekt implementiert und deckt alle Zustaende ab.
- Zustand "verbunden" wird ueber `has_key and self._nx_uid.text()` geprueft --
  das ist sinnvoll, da `_nx_uid` nur nach erfolgreicher Validierung gefuellt wird.

---

## Pruefung 6: Keine _disabled() Aufrufe auf den 3 Nexus-Buttons

Die 3 Nexus-Buttons sind:
- `self._btn_connect` (Zeile 440)
- `self._btn_api_key` (Zeile 443)
- `self._btn_disconnect` (Zeile 446)

Grep-Ergebnis fuer `_disabled(self._btn_connect|_disabled(self._btn_api_key|_disabled(self._btn_disconnect)`:
**Keine Treffer.**

- **Ergebnis:** KORREKT -- Keiner der 3 Nexus-Buttons wird mit `_disabled()` versehen.
  Ihre Enabled/Disabled-Zustaende werden ausschliesslich ueber `_nx_update_button_states()` gesteuert.

---

## Pruefung 7: Andere disabled-Widgets bleiben disabled

### Nexus-Tab: disabled-Widgets (Optionen, Server, NXM, Cache)

| Widget | Zeile | disabled? |
|--------|-------|-----------|
| Optionen-Checkboxen (Endorsement, Tracking, Category, Hide API) | 476 | JA -- `_disabled(cb)` im Loop |
| NXM Link Button | 482 | JA -- `_disabled(btn_link)` |
| Clear Cache Button | 484 | JA -- `_disabled(QPushButton(...))` |
| Known Servers List | 498 | JA -- `_disabled(known_list)` |
| Preferred Servers List | 506 | JA -- `_disabled(pref_list)` |

- **Ergebnis:** KORREKT -- Alle Optionen/Server/NXM/Cache-Widgets im Nexus-Tab
  sind weiterhin mit `_disabled()` markiert und zeigen den "Noch nicht verfuegbar" Tooltip.

### Andere Tabs (Stichproben)
- Auto-Archive-Invalidation (Zeile 144): disabled
- Open Preview DblClick (Zeile 164): disabled
- Edit Categories (Zeile 172): disabled
- Color Text Buttons (Zeile 222): disabled
- Reset Colors (Zeile 231): disabled
- Workarounds-Tab Widgets (Zeilen 638-673): alle disabled

Alles unveraendert und korrekt.

---

## Zusaetzliche Findings

### [LOW] Hardcoded Strings in nexus_sso.py
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py:49-58`
- **Problem:** Die STATE_MESSAGES in nexus_sso.py sind hardcoded auf Deutsch,
  nicht ueber tr() uebersetzt. z.B. `"Verbinde zu Nexus..."`, `"Abgebrochen."`, etc.
- **Auswirkung:** Diese Strings werden direkt in `_nx_on_sso_state()` via
  `state_to_string()` ins Log geschrieben und sind nicht uebersetzbar.
- **Fix:** STATE_MESSAGES auf tr()-Keys umstellen.

### [LOW] Hardcoded String in settings_dialog.py:525
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py:525`
- **Problem:** `"API-Schlüssel überprüfen..."` ist ein hardcoded deutscher String,
  nicht ueber tr() uebersetzt.
- **Fix:** Durch `tr("settings.nexus_key_checking")` ersetzen.

### [LOW] QListWidget StyleSheet in settings_dialog.py:458
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py:458`
- **Problem:** `self._nx_log.setStyleSheet("QListWidget { font-size: 11px; }")` --
  laut CLAUDE.md soll kein `setStyleSheet()` in neuen Widgets verwendet werden.
  Der QSS-Theme soll alles erben.
- **Auswirkung:** Gering, da es nur die Schriftgroesse setzt und den Theme nicht bricht.
- **Fix:** Entweder in QSS-Theme verschieben oder als akzeptierte Ausnahme dokumentieren.

### [INFO] SSO Login -- NexusSSOLogin wird jedes Mal neu erstellt
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py:976`
- **Problem:** Bei jedem SSO-Connect wird ein neues `NexusSSOLogin(self)` erstellt.
  Das alte Objekt wird durch Python-GC bereinigt (hat `self` als parent).
  Das ist kein Bug, da Qt-Parents das Cleanup uebernehmen.
- **Ergebnis:** Kein Problem.

### [INFO] _ApiWorker cleanup Reihenfolge
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_api.py:170-171`
- **Problem:** `_cleanup_worker` wird sowohl bei `finished` als auch bei `error`
  verbunden. Wenn `error` emittiert wird, wird `finished` von QThread trotzdem
  emittiert (da der Thread endet), was zu einem doppelten `_cleanup_worker`-Aufruf
  fuehren koennte. Der Guard `if worker in self._workers` (Zeile 177) verhindert
  einen Crash, also ist dies sicher.
- **Ergebnis:** Kein Problem -- der Guard schuetzt korrekt.

---

## Zusammenfassung

| Pruefpunkt | Ergebnis |
|------------|----------|
| 1. validate_key() korrekt aufgerufen | KORREKT |
| 2. Signal/Slot-Verbindungen | KORREKT |
| 3. User-Info nach Validierung | KORREKT |
| 4. QSettings nexus/api_key | KORREKT |
| 5. _nx_update_button_states() 9x | KORREKT (9/9 Stellen) |
| 6. Keine _disabled() auf 3 Buttons | KORREKT |
| 7. Andere disabled-Widgets bleiben | KORREKT |

## Ergebnis
**READY FOR COMMIT** -- Alle 7 Pruefpunkte bestanden. 3 LOW-Findings (hardcoded Strings,
setStyleSheet) sind kosmetischer Natur und blockieren keinen Commit.
