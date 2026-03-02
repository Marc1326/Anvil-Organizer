# Feature: Nexus Mods API Integration — Settings Tab
Datum: 2026-03-02

## Ziel

User klickt "Mit Nexus verbinden" im Settings-Dialog (Tab Nexus) → Browser öffnet sich auf nexusmods.com → User autorisiert Anvil Organizer → API-Key wird empfangen, validiert und in QSettings gespeichert → User-Info (Name, Premium-Status) und Rate-Limits werden angezeigt. Alternativ kann der User einen API-Key manuell eingeben.

## Ist-Zustand (aus Agent-Reports)

### Was bereits VOLLSTÄNDIG implementiert ist:
- **SSO-Flow** (`anvil/core/nexus_sso.py`, 352 Zeilen): WebSocket-Verbindung, Browser-Öffnung, Key-Empfang, State-Machine mit 8 Zuständen, Abbruch-Mechanismus
- **NexusAPI** (`anvil/core/nexus_api.py`, 226 Zeilen): `validate_key()`, `set_api_key()`, `has_api_key()`, Rate-Limit-Tracking, Signals (`user_validated`, `request_error`, `rate_limit_updated`)
- **SettingsDialog Backend** (Zeilen 928-1062): `_nx_connect_sso()`, `_nx_enter_api_key()`, `_nx_disconnect()`, `_nx_on_validated()`, `_nx_on_error()`, `_nx_on_rate_limit()`
- **Signal-Verbindungen**: Alle Buttons haben `.clicked.connect()` zu den Backend-Methoden
- **QSettings**: Laden (Zeile 525), Speichern (Zeilen 969, 985), Löschen (Zeile 998) unter Key `nexus/api_key`
- **i18n-Keys**: Alle relevanten Keys in allen 6 Locale-Dateien vorhanden

### Was NICHT funktioniert:
1. **Alle 3 Kern-Buttons sind disabled** (Zeilen 442, 446, 450 via `_disabled()`)
2. **APPLICATION_SLUG ist falsch**: `"anvilorganizer"` statt `"nathuk-anvilorganizer"`
3. **Keine dynamische Button-State-Verwaltung**: Buttons ändern ihren Enabled-Zustand nie basierend auf Verbindungsstatus

## Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `anvil/core/nexus_sso.py` | Zeile 34: `APPLICATION_SLUG` von `"anvilorganizer"` auf `"nathuk-anvilorganizer"` ändern |
| `anvil/widgets/settings_dialog.py` | Zeilen 440-451: `_disabled()` bei den 3 Kern-Buttons entfernen, neue Methode `_nx_update_button_states()` hinzufügen, Button-States nach Validierung/Disconnect/Error aktualisieren |

## Änderungen im Detail

### 1. APPLICATION_SLUG korrigieren

**Datei:** `anvil/core/nexus_sso.py`, Zeile 34
**Was:** `APPLICATION_SLUG = "anvilorganizer"` ändern zu `APPLICATION_SLUG = "nathuk-anvilorganizer"`
**Warum:** Der offiziell bei Nexus Mods registrierte Slug ist `"nathuk-anvilorganizer"`. Ohne den korrekten Slug wird der SSO-Flow von Nexus abgelehnt.
**Impact:** Der Slug wird nur an einer Stelle verwendet (Zeile 162 in derselben Datei, in der Browser-URL). Keine weiteren Vorkommen im Projekt.

### 2. Buttons aktivieren + dynamische States

**Datei:** `anvil/widgets/settings_dialog.py`

**Schritt 2a: `_disabled()` bei den 3 Kern-Buttons entfernen**

Zeilen 442, 446, 450: Die drei `_disabled(self._btn_xxx)` Aufrufe entfernen. Diese setzen `setEnabled(False)` und `setToolTip("Noch nicht verfügbar")`.

**Schritt 2b: Neue Methode `_nx_update_button_states()` hinzufügen**

Eine zentrale Methode, die den Enabled-Zustand aller drei Buttons basierend auf dem aktuellen Verbindungsstatus setzt:

| Zustand | _btn_connect | _btn_api_key | _btn_disconnect |
|---------|-------------|-------------|----------------|
| Nicht verbunden (`api_key` leer) | Enabled | Enabled | Disabled |
| SSO läuft (`_sso_login.is_active()`) | Enabled (Text: "Abbrechen") | Disabled | Disabled |
| Verbunden (`api_key` gesetzt + validiert) | Disabled | Disabled | Enabled |
| Fehler bei Validierung | Enabled | Enabled | Enabled |

**Schritt 2c: `_nx_update_button_states()` aufrufen an folgenden Stellen:**

| Methode | Nach welchem Event | Erwarteter Zustand |
|---------|-------------------|-------------------|
| `__init__` (Zeile ~531) | Nach Key-Lade-Check | Nicht verbunden ODER Validierung läuft |
| `_nx_connect_sso()` | SSO gestartet/abgebrochen | SSO läuft / Nicht verbunden |
| `_nx_on_sso_state()` | SSO beendet (Finished/Error/Timeout/Cancelled) | Je nach Ergebnis |
| `_nx_on_sso_key()` | Key empfangen, Validierung läuft | Zwischen-Zustand |
| `_nx_enter_api_key()` | Manueller Key eingegeben | Validierung läuft |
| `_nx_disconnect()` | Verbindung getrennt | Nicht verbunden |
| `_nx_on_validated()` | Key erfolgreich validiert | Verbunden |
| `_nx_on_error()` | Validierung fehlgeschlagen | Fehler |

### 3. Tooltip zurücksetzen

Da `_disabled()` den Tooltip auf `tr("settings.coming_soon")` setzt, muss `_nx_update_button_states()` auch die Tooltips der Buttons zurücksetzen (auf `""` oder einen kontextbezogenen Tooltip).

## Signal-Flow (komplett)

```
[User klickt "Verbinde zu Nexus"]
  |
  v
_nx_connect_sso()
  |- _nx_update_button_states()  <-- NEU: Buttons für SSO-Modus setzen
  |- NexusSSOLogin.start()
  |    |- _WebSocketWorker startet in QThread
  |    |- SSL + WS-Handshake zu wss://sso.nexusmods.com
  |    |- Session-Nachricht: {"id": "<uuid>", "token": null, "protocol": 2}
  |    |- Server antwortet mit connection_token
  |    |- Browser öffnet: https://www.nexusmods.com/sso?id=<uuid>&application=nathuk-anvilorganizer
  |    |
  |    [User autorisiert im Browser]
  |    |
  |    |- Server sendet api_key
  |    |- worker.key_received Signal
  |    v
  |- NexusSSOLogin.key_changed Signal
  v
_nx_on_sso_key(api_key)
  |- NexusAPI.set_api_key(api_key)
  |- QSettings.setValue("nexus/api_key", api_key)
  |- NexusAPI.validate_key()
  |    |- _ApiWorker startet GET /users/validate.json
  |    |- HTTP 200 + JSON-Response
  |    v
  |- NexusAPI.user_validated Signal
  v
_nx_on_validated(user_info)
  |- _nx_uid.setText(user_id)
  |- _nx_name.setText(name)
  |- _nx_account.setText("Premium"/"Supporter"/"Standard")
  |- _nx_status_label.setText("Verbunden.")
  |- _nx_update_button_states()  <-- NEU: Buttons für Verbunden-Modus

[Parallel dazu:]
NexusAPI.rate_limit_updated Signal
  v
_nx_on_rate_limit(daily, hourly)
  |- _nx_daily.setText(daily)
  |- _nx_hourly.setText(hourly)
  |- parent._update_api_status(daily, hourly)  (MainWindow)
```

## MO2-Vergleich

| Aspekt | MO2 | Anvil (nach diesem Feature) |
|--------|-----|---------------------------|
| SSO-Slug | `"modorganizer2"` (hardcoded in URL) | `"nathuk-anvilorganizer"` (Konstante) |
| WebSocket | Qt `QWebSocket` (event-driven) | Python stdlib `ssl+socket` in QThread (blocking) |
| Button-States | `updateState()` Methode | `_nx_update_button_states()` (neu) |
| Key-Speicherung | INI-Datei (Klartext) | QSettings INI (Klartext) — identisch |
| Key-Validierung | `NexusKeyValidator` mit Retry | Einmaliger `validate_key()` Aufruf |
| API-Instanzen | Singleton via Plugin-System | 2 separate Instanzen (bekanntes Problem, nicht in Scope) |

## NICHT in diesem Feature (Scope-Grenze)

- **Optionen-Checkboxen** (Endorsement, Tracking, Kategorie-Mapping, API-Zähler) — bleiben disabled
- **Server-Listen** (Known/Preferred) — bleiben disabled
- **NXM-Handler-Button** — bleibt disabled (separates Feature)
- **Cache-leeren-Button** — bleibt disabled
- **Request Queue / Throttling** — nicht in Scope
- **NexusAPI-Singleton** (Zusammenführung der 2 Instanzen) — nicht in Scope
- **Neue API-Methoden** (requestUpdateInfo, Endorsement, Tracking) — nicht in Scope
- **Timeout-Überarbeitung** (separater kurzer Timeout für initiale Verbindung) — nicht in Scope
- **STATE_MESSAGES i18n** — nicht in Scope
- **Ping-Rekursion-Fix** — nicht in Scope

## Abhängigkeiten

- Nexus Mods muss den Slug `"nathuk-anvilorganizer"` akzeptieren (laut Marc bereits bestätigt/registriert)
- `anvil/core/nexus_sso.py` und `anvil/core/nexus_api.py` müssen unverändert funktional sein (verifiziert)
- Alle i18n-Keys sind bereits in allen 6 Locale-Dateien vorhanden (verifiziert)

## Risiken

| Risiko | Wahrscheinlichkeit | Auswirkung | Mitigation |
|--------|-------------------|------------|------------|
| Nexus lehnt neuen Slug ab | Niedrig (bestätigt) | SSO funktioniert nicht | Manueller API-Key als Fallback |
| 120s Socket-Timeout zu kurz | Mittel | User wird getrennt wenn er lange braucht | Bekanntes Problem, nicht in Scope |
| Doppelte NexusAPI-Instanz | Niedrig (für dieses Feature) | Key-Desync möglich | Nicht in Scope, funktioniert aktuell durch QSettings-Reload |

## Änderungs-Zusammenfassung

| Datei | Zeile(n) | Änderung |
|-------|----------|----------|
| `anvil/core/nexus_sso.py` | 34 | `APPLICATION_SLUG = "anvilorganizer"` → `"nathuk-anvilorganizer"` |
| `anvil/widgets/settings_dialog.py` | 442, 446, 450 | Drei `_disabled()` Aufrufe entfernen |
| `anvil/widgets/settings_dialog.py` | Neu (~928+) | Neue Methode `_nx_update_button_states()` mit ~25 Zeilen |
| `anvil/widgets/settings_dialog.py` | 531, 943, 950, 962, 971, 988, 1008, 1026, 1033 | Aufrufe von `_nx_update_button_states()` an 9 Stellen einfügen |

## Akzeptanz-Checkliste

- [ ] 1. APPLICATION_SLUG in `anvil/core/nexus_sso.py` Zeile 34 ist `"nathuk-anvilorganizer"`
- [ ] 2. Wenn User den Settings-Dialog öffnet und KEIN API-Key gespeichert ist, sind "Verbinde zu Nexus" und "API-Schlüssel manuell eingeben" klickbar, "Trennen" ist ausgegraut
- [ ] 3. Wenn User "Verbinde zu Nexus" klickt, öffnet sich der Browser mit URL `https://www.nexusmods.com/sso?id=<uuid>&application=nathuk-anvilorganizer`
- [ ] 4. Während der SSO-Flow läuft, zeigt der Connect-Button den Text "Abbrechen" und die anderen beiden Buttons sind ausgegraut
- [ ] 5. Wenn User im Browser autorisiert, wird der API-Key empfangen, in QSettings unter `nexus/api_key` gespeichert und `validate_key()` automatisch aufgerufen
- [ ] 6. Nach erfolgreicher Validierung werden User-ID, Name und Account-Typ (Premium/Supporter/Standard) in den entsprechenden Feldern angezeigt
- [ ] 7. Nach erfolgreicher Validierung werden Daily- und Hourly-Rate-Limits in den entsprechenden Feldern angezeigt
- [ ] 8. Nach erfolgreicher Validierung zeigt das Status-Label "Verbunden." in Grün, und der Disconnect-Button ist klickbar, Connect und API-Key-Button sind ausgegraut
- [ ] 9. Wenn User "Trennen" klickt, werden alle Felder (User-ID, Name, Konto, Daily, Hourly) geleert, der API-Key wird aus QSettings gelöscht, und die Buttons wechseln zurück zum Nicht-verbunden-Zustand
- [ ] 10. Wenn User "API-Schlüssel manuell eingeben" klickt, erscheint ein InputDialog; nach Eingabe eines gültigen Keys wird dieser gespeichert und validiert (identisches Verhalten wie nach SSO)
- [ ] 11. Wenn die Validierung fehlschlägt (ungültiger Key, Netzwerk-Fehler), wird eine Fehlermeldung im Log und Status-Label angezeigt, und Connect + API-Key-Button bleiben klickbar
- [ ] 12. Wenn User den SSO-Flow abbricht (klickt "Abbrechen" während SSO läuft), wird der Flow gestoppt und die Buttons kehren zum Nicht-verbunden-Zustand zurück
- [ ] 13. Wenn ein gespeicherter API-Key existiert und der Settings-Dialog geöffnet wird, wird der Key automatisch validiert und bei Erfolg der Verbunden-Zustand angezeigt
- [ ] 14. Keiner der drei Buttons hat den Tooltip "Noch nicht verfügbar" — Tooltips sind leer oder kontextbezogen
- [ ] 15. Die Optionen-Checkboxen, Server-Listen, NXM-Handler-Button und Cache-Button bleiben UNVERÄNDERT disabled
- [ ] 16. `restart.sh` startet ohne Fehler
