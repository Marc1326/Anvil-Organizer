# Agent 2: Nexus API Analysis (nexus_api.py)

## Zusammenfassung

Die Datei `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_api.py` (226 Zeilen) implementiert einen asynchronen Nexus Mods API v1 Client, der ausschließlich Python-Stdlib (`urllib.request`) und Qt-Threads (`QThread`) nutzt — keine externen HTTP-Bibliotheken.

---

## 1. Klassen-Übersicht

### `_ApiWorker(QThread)` (Zeile 29-59)
- Interner Worker-Thread für einzelne HTTP GET-Requests
- **Signals:**
  - `finished(str, int, dict, bytes)` — (tag, status_code, headers, body)
  - `error(str, str)` — (tag, error_message)
- Timeout: 30 Sekunden hardcoded (Zeile 44)
- Behandelt `HTTPError` separat: Liest trotzdem Body und emittiert `finished` mit dem HTTP-Statuscode
- Alle anderen Exceptions werden als `error` emittiert

### `NexusAPI(QObject)` (Zeile 62-226)
- Öffentlicher API-Client
- Hält eine Liste `_workers` um Worker vor Garbage Collection zu schützen
- Speichert API-Key und Rate-Limit-Werte intern

---

## 2. Methoden

| Methode | Endpoint | Tag-Format | Beschreibung |
|---------|----------|------------|--------------|
| `set_api_key(key)` | — | — | Setzt API-Key (strip()) |
| `api_key()` | — | — | Gibt aktuellen Key zurück |
| `has_api_key()` | — | — | Bool: Key gesetzt? |
| `daily_remaining()` | — | — | Letzter bekannter Daily-Limit (-1 = unbekannt) |
| `hourly_remaining()` | — | — | Letzter bekannter Hourly-Limit (-1 = unbekannt) |
| `validate_key()` | `GET /users/validate.json` | `"validate"` | Key prüfen, User-Info holen |
| `get_mod_info(game, mod_id)` | `GET /games/{game}/mods/{mod_id}.json` | `"mod_info:{game}:{mod_id}"` | Mod-Metadaten abrufen |
| `get_mod_files(game, mod_id)` | `GET /games/{game}/mods/{mod_id}/files.json` | `"mod_files:{game}:{mod_id}"` | Dateiliste eines Mods |
| `get_download_links(game, mod_id, file_id, key?, expires?)` | `GET .../download_link.json` | `"download_link:{game}:{mod_id}:{file_id}"` | Download-URLs holen |
| `_get(path, tag)` | intern | — | Erzeugt `_ApiWorker`, verwaltet Lifecycle |
| `_cleanup_worker(worker)` | intern | — | Worker aus Liste entfernen + `deleteLater()` |
| `_on_worker_error(tag, message)` | intern | — | Leitet Netzwerk-Fehler weiter |
| `_on_worker_finished(tag, status, headers, body)` | intern | — | Rate-Limits lesen, HTTP-Status prüfen, JSON parsen |

---

## 3. Signals

| Signal | Parameter | Zweck |
|--------|-----------|-------|
| `request_finished` | `(str, object)` — (endpoint/tag, parsed JSON) | Erfolgreiche API-Antwort |
| `request_error` | `(str, str)` — (endpoint/tag, error message) | Fehler bei API-Request |
| `rate_limit_updated` | `(int, int)` — (daily_remaining, hourly_remaining) | Nach jeder Antwort mit Rate-Limit-Headern |
| `user_validated` | `(dict,)` — user info dict | Nach erfolgreichem `validate_key()` |

### Verwendung in MainWindow (Zeile 252-260):
```python
self._nexus_api = NexusAPI(self)
self._nexus_api.request_finished.connect(self._on_nexus_response)
self._nexus_api.request_error.connect(self._on_nexus_error)
self._nexus_api.rate_limit_updated.connect(self._update_api_status)
```

### Verwendung in SettingsDialog (Zeile 519-523):
```python
self._nexus_api = NexusAPI(self)
self._nexus_api.user_validated.connect(self._nx_on_validated)
self._nexus_api.request_error.connect(self._nx_on_error)
self._nexus_api.rate_limit_updated.connect(self._nx_on_rate_limit)
```

**Wichtig:** ZWEI separate `NexusAPI`-Instanzen — eine im MainWindow, eine im SettingsDialog. Kein geteilter State.

---

## 4. Ausreichend für Settings-Tab?

### Was bereits funktioniert:

1. **Key validieren** — `validate_key()` vorhanden, `user_validated` Signal wird verarbeitet
2. **User-Info anzeigen** — User-ID, Name, Account-Typ (Premium/Supporter/Standard)
3. **Rate-Limits anzeigen** — Daily und Hourly Remaining
4. **Key-Management** — `set_api_key()`, `has_api_key()`, `api_key()`

**Fazit: Die API reicht für den Settings-Tab aus.** Alle nötigen Methoden sind vorhanden. Die Buttons müssen nur enabled werden.

---

## 5. Fehlende Funktionalität

### Fehlende API-Methoden (Vergleich mit MO2):

| MO2-Methode | Anvil-Status | Priorität |
|-------------|--------------|-----------|
| `requestFileInfo` | **FEHLT** (Einzeldatei-Info) | Mittel |
| `requestToggleEndorsement` | **FEHLT** (erfordert POST) | Mittel |
| `requestToggleTracking` | **FEHLT** (erfordert POST) | Mittel |
| `requestEndorsementInfo` | **FEHLT** | Niedrig |
| `requestTrackingInfo` | **FEHLT** | Niedrig |
| `requestUpdateInfo` | **FEHLT** (Update-Check für Mods) | Hoch |
| `requestGameInfo` | **FEHLT** | Niedrig |
| `requestInfoFromMd5` | **FEHLT** (Mod-Identifikation via Hash) | Mittel |

### Fehlende Infrastruktur:

| Feature | MO2-Referenz | Anvil-Status |
|---------|-------------|--------------|
| **Request Queue** | `QQueue` mit `MAX_ACTIVE_DOWNLOADS = 6` | FEHLT — jeder Request startet sofort einen neuen QThread |
| **Request Throttling** | `shouldThrottle()` bei < 200 Remaining | FEHLT |
| **Disk Cache** | `QNetworkDiskCache` | FEHLT |
| **Max-Limits** | `maxDailyRequests`, `maxHourlyRequests` | FEHLT — nur Remaining wird getrackt |
| **POST-Requests** | Für Endorsement/Tracking Toggle | FEHLT — nur GET implementiert |

---

## 6. Fehlerbehandlung

### HTTP-Status-Codes:
| Status | Verhalten |
|--------|-----------|
| 429 | "Rate Limit erreicht. Bitte warten." — Kein Retry |
| 401 | "Ungültiger API-Schlüssel." |
| >= 400 | Generische Meldung "HTTP {status}" |
| 200-399 | JSON parsen |

### Netzwerk-Fehler:
- `urllib.error.HTTPError`: Body wird trotzdem gelesen, `finished` Signal emittiert
- Alle anderen Exceptions: `error` Signal mit Exception-Text
- Timeout: 30 Sekunden hardcoded

### JSON-Parsing:
- `json.JSONDecodeError` und `UnicodeDecodeError` werden gefangen
- Fehler wird als `request_error` emittiert

### Fehlende Fehlerbehandlung:
1. **Kein Retry-Mechanismus** bei Netzwerk-Fehlern oder Rate-Limits
2. **Kein Exponential Backoff** besonders bei 429
3. **Keine Timeout-Konfiguration** — fest 30 Sekunden
4. **Kein Abbruch laufender Requests**

---

## 7. API-Key Speicherung

- **QSettings Key:** `"nexus/api_key"`
- **Klartext** in `~/.config/AnvilOrganizer/AnvilOrganizer.conf` (INI-Format)
- MO2 speichert den Key auch im Klartext — akzeptables Verhalten

---

## 8. Empfehlungen

### Priorität 1 — Settings-Tab aktivieren:
1. Die drei Buttons (Connect, Manual Key, Disconnect) müssen enabled werden
2. Manual Key und Disconnect können sofort aktiviert werden
3. SSO-Button erst nach Slug-Registrierung bei Nexus

### Priorität 2 — Singleton-Pattern:
Die zwei NexusAPI-Instanzen sollten zu einer werden (MainWindow-Instanz an SettingsDialog durchreichen oder nach Dialog-Schließen Key neu laden)

### Priorität 3 — Request Queue:
Max 6 parallele Requests (wie MO2) bevor weitere API-Methoden hinzugefügt werden

### Priorität 4 — Fehlende API-Methoden:
1. `requestUpdateInfo` — für Mod-Update-Checks
2. `requestToggleEndorsement` — erfordert POST-Support
3. `requestToggleTracking` — erfordert POST-Support
