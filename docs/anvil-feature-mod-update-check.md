# Feature: Mod-Update-Benachrichtigungen (Nexus API)
Datum: 2026-03-29

## Zusammenfassung

Anvil Organizer soll automatisch pruefen koennen, ob fuer installierte Mods Updates auf Nexus Mods verfuegbar sind. Das Feature nutzt die Nexus API v1 mit einer effizienten Zwei-Phasen-Strategie (Bulk-Check + Detail-Abfrage), zeigt Updates visuell in der Mod-Liste an, und benachrichtigt den User per Toast und Toolbar-Badge. Das Design orientiert sich am MO2-Vorbild, vereinfacht aber die File-Update-Ketten-Verfolgung fuer die erste Version.

**Nicht im Scope:** BG3-Instanzen sind vom Update-Check ausgeschlossen (CLAUDE.md-Regel).

---

## User Stories

- Als User moechte ich per Klick auf einen Toolbar-Button pruefen, ob Updates fuer meine Mods verfuegbar sind, damit ich meine Mods aktuell halten kann.
- Als User moechte ich in der Mod-Liste sofort sehen, welche Mods veraltet sind, damit ich Prioritaeten beim Updaten setzen kann.
- Als User moechte ich optional beim App-Start automatisch auf Updates pruefen lassen, damit ich keine manuellen Checks brauche.
- Als User moechte ich ein bestimmtes Update ignorieren koennen, damit ich nicht staendig an Updates erinnert werde, die ich bewusst nicht installiere.
- Als User moechte ich sehen, welche Version ich installiert habe und welche die neueste ist, damit ich die Dringlichkeit einschaetzen kann.
- Als User moechte ich, dass der Update-Check meine API-Rate-Limits nicht ueberschreitet, damit meine Nexus-API-Nutzung nicht beeintraechtigt wird.

---

## Technische Planung

### Betroffene Dateien (konsolidiert aus allen 3 Agents)

| Datei | Aenderungstyp | Beschreibung |
|---|---|---|
| `anvil/core/mod_update_checker.py` | **NEU** | Zentrale Klasse `ModUpdateChecker(QObject)` — orchestriert den 2-Phasen-Update-Check mit Queue-System |
| `anvil/core/nexus_api.py` | AENDERN | Neuer Endpoint `get_updated_mods(game, period)` fuer Bulk-Check; optionale Throttle-Schwelle |
| `anvil/core/mod_entry.py` | AENDERN | Neue Felder: `newest_version: str`, `has_update: bool`, `update_ignored: bool`, `last_nexus_check: str` |
| `anvil/models/mod_list_model.py` | AENDERN | `ModRow`: neue Slots `newest_version`, `has_update`, `update_ignored`; `ForegroundRole` fuer Farbkodierung; `DecorationRole` fuer Update-Icon; Tooltip mit installierter vs. neuester Version; Separator-Aggregation fuer Updates |
| `anvil/mainwindow.py` | AENDERN | `ModUpdateChecker` instanziieren, Signal-Verbindungen, Response-Handler fuer Update-Tags, Toolbar-Button aktivieren, Kontextmenue-Eintrag "Update ignorieren", BG3-Gate-Check |
| `anvil/widgets/toolbar.py` | AENDERN | `notifications_btn` aktivieren, Badge/Counter-Overlay, Click-Handler fuer Update-Liste |
| `anvil/widgets/settings_dialog.py` | AENDERN | Neue Checkboxen: "Mod-Updates beim Start pruefen", "Pruef-Intervall" (ComboBox: 1d/1w/1m) |
| `anvil/core/mod_metadata.py` | KEINE | Bereits vollstaendig — `read_meta_ini()` und `write_meta_ini()` lesen/schreiben `newestVersion`, `lastNexusQuery` |
| `anvil/widgets/toast.py` | KEINE | Bereits vorhanden, wird direkt wiederverwendet |
| `anvil/widgets/status_bar.py` | OPTIONAL | Update-Counter in StatusBar anzeigen |
| `anvil/dialogs/mod_detail_dialog.py` | OPTIONAL | Update-Hinweis im Detail-Dialog hervorheben |
| Locale-Dateien (6 Sprachen) | AENDERN | Neue tr()-Keys fuer alle UI-Texte |

### Kritischer Bug: version vs. newestVersion bei Query Info

**Fundstelle:** `mainwindow.py:4141-4142` (Handler fuer `query_mod_info:*`)

Aktuell wird bei "Query Nexus Info" sowohl `version` als auch `newestVersion` mit dem Nexus-Wert ueberschrieben:
```python
"version": data.get("version", ""),
"newestVersion": data.get("version", ""),
```
Das ist **falsch** — `version` sollte die **installierte** Version sein und darf durch einen Query nicht ueberschrieben werden. Nur `newestVersion` darf mit dem Nexus-Wert aktualisiert werden.

**Fix erforderlich VOR der Update-Check-Implementierung:** `version` darf nur bei Installation gesetzt werden, nicht bei Query.

---

### Architektur-Ueberblick

#### Neue Klasse: ModUpdateChecker

```
ModUpdateChecker(QObject):
    Signals:
        check_started()
        check_progress(int, int)           # (checked_count, total_count)
        mod_update_found(str, str, str)    # (folder_name, installed_ver, newest_ver)
        check_finished(int)                # (total_updates_found)
        check_error(str)                   # (error_message)

    Methoden:
        check_for_updates(entries: list[ModEntry], game_slug: str)
        cancel()
        is_running() -> bool

    Intern:
        _phase1_bulk_check()   — 1 API-Request an /mods/updated?period=
        _phase2_detail_check() — N API-Requests fuer geaenderte Mods (Queue mit MAX_CONCURRENT=2)
        _determine_period()    — Waehlt 1d/1w/1m basierend auf aeltestem lastNexusQuery
        _compare_versions()    — Vergleicht installierte vs. neueste Version
```

#### Signal-Flow (End-to-End)

```
1. TRIGGER:
   a) User klickt "Benachrichtigungen"-Button (Toolbar) → MainWindow._on_check_mod_updates()
   b) App-Start + Setting aktiviert → QTimer.singleShot(5000, ...) → MainWindow._on_check_mod_updates()

2. GATE-CHECKS (MainWindow._on_check_mod_updates):
   - self._nexus_api.has_api_key()? → Nein: stiller Abbruch, kein Dialog
   - self._bg3_installer is not None? → Ja: stiller Abbruch (BG3 ausgeschlossen)
   - self._mod_update_checker.is_running()? → Ja: stiller Abbruch (kein Doppel-Check)
   - self._nexus_api.hourly_remaining() < 10? → Ja: Toast "Rate-Limit niedrig", Abbruch

3. PHASE 1 — Bulk-Check:
   ModUpdateChecker.check_for_updates(entries, game_slug)
   → Filtere Mods: nexus_id > 0, nicht Separator, nicht Framework
   → Bestimme period via _determine_period() aus aeltestem lastNexusQuery
   → NexusAPI._get("/games/{game}/mods/updated.json?period={period}", tag="batch_update:{game}")
   → check_started Signal → Toolbar-Badge: Spinner/Pulsieren

4. BATCH-RESPONSE (MainWindow._on_nexus_response, tag="batch_update:*"):
   → Parse Liste: [{mod_id, latest_file_update, latest_mod_activity}, ...]
   → Filtere gegen installierte Mods: latest_file_update > lastNexusQuery?
   → Treffer-Liste an ModUpdateChecker._phase2_detail_check() weiterleiten

5. PHASE 2 — Detail-Checks (Queue mit MAX_CONCURRENT=2):
   → Fuer jeden Treffer: NexusAPI._get("/games/{game}/mods/{id}.json", tag="update_check:{game}:{id}")
   → check_progress Signal → Log-Panel: "Pruefe Mod 3/12..."

6. DETAIL-RESPONSES (MainWindow._on_nexus_response, tag="update_check:*"):
   → Vergleiche: meta.ini[version] != response[version]?
   → Wenn Update: write_meta_ini(newestVersion=response[version], lastNexusQuery=now)
   → mod_update_found Signal → ModRow aktualisieren (gezieltes dataChanged, KEIN Full-Rebuild)

7. ABSCHLUSS:
   → check_finished(N) Signal
   → Toast: "N Updates verfuegbar" (klickbar → scrollt zu erstem Update)
   → Toolbar notifications_btn: Badge mit Zahl N, Button aktiviert
   → Klick auf Badge: Popup-Liste aller Mods mit Updates (Name, installiert, neueste)
```

#### Tag-Routing-Schema (Erweiterung)

| Tag-Praefix | Bedeutung | Phase |
|---|---|---|
| `batch_update:{game}` | Bulk-Check Response (Liste aktualisierter Mod-IDs) | 1 |
| `update_check:{game}:{mod_id}` | Einzelner Mod-Detail-Check | 2 |
| (bestehend) `mod_info:*`, `query_mod_info:*`, etc. | Unveraendert | - |

#### Queue-System (nach Vorbild DownloadManager)

Der Detail-Check in Phase 2 nutzt dasselbe Queue-Pattern wie `download_manager.py`:
- `MAX_CONCURRENT = 2` (weniger aggressiv als MO2's 6)
- `_queue: list[tuple[str, int]]` — (game_slug, mod_id) Paare
- `_active: set[str]` — aktuell laufende Tags
- `_start_next()` — startet naechsten Request wenn Slot frei
- Abbruch bei Instanz-Wechsel oder User-Cancel

---

### MO2-Vergleich

| Aspekt | MO2 | Anvil (geplant) | Abweichung |
|---|---|---|---|
| Bulk-Endpoint | `GET /mods/updated?period=` | Gleich | Keine |
| Perioden-Wahl | Automatisch nach lastNexusUpdate | Gleich | Keine |
| Phase 2: Detail | `GET /mods/{id}/files.json` + file_updates-Kette | `GET /mods/{id}.json` (einfacher Versionsvergleich) | Vereinfacht — keine File-Ketten-Verfolgung in Phase 1 |
| Concurrent Requests | max 6 | max 2 | Weniger aggressiv |
| Cooldown pro Mod | 300 Sekunden | 300 Sekunden | Gleich |
| Throttle-Schwelle | < 200 Requests verbleibend | < 50 Requests verbleibend (konservativer) | Angepasst |
| Version-Vergleich | Semantisch (VersionInfo Klasse) | String-Vergleich (Phase 1), `packaging.version` spaeter | Vereinfacht |
| ignoredVersion | In meta.ini | In meta.ini (MO2-kompatibel) | Gleich |
| UI: Versionsfarbe | Rot (Update), Gruen (aktuell), Gelb (Downgrade) | Rot (Update), Standard (aktuell) | Kein Downgrade-Erkennung in Phase 1 |
| UI: Separator-Aggregation | Update-Icon wenn Kind-Mod Update hat | Gleich (bestehendes Pattern erweitern) | Gleich |
| Cache | QNetworkDiskCache | `.update_cache.json` pro Instanz | Anvil-spezifisch |

---

### Cache-Strategie

**Hybrid-Ansatz (wie MO2):**
1. **meta.ini pro Mod:** `newestVersion`, `lastNexusQuery`, `ignoredVersion` — bleibt bestehen
2. **`.update_cache.json` pro Instanz:** Bulk-Check-Ergebnis cachen, TTL 1 Stunde
   - Pfad: `{instance_path}/.update_cache.json`
   - Inhalt: `{"last_check": "ISO-Timestamp", "period": "1d", "updated_mods": [mod_id, ...]}`
   - Wird beim naechsten Check gelesen — wenn TTL nicht abgelaufen, Phase 1 ueberspringen

---

## Verwandte Funktionen (geprueft)

| Funktion | Gleicher Fix noetig? | Begruendung |
|---|---|---|
| `_on_nexus_response()` query_mod_info Handler | **JA** | Ueberschreibt `version` mit Nexus-Wert — muss nur `newestVersion` setzen |
| `_build_entry()` in mod_entry.py | **JA** | Liest `newestVersion` nicht aus meta.ini — muss erweitert werden |
| `mod_entry_to_row()` in mod_list_model.py | **JA** | Uebergibt `newest_version` nicht an ModRow — muss erweitert werden |
| `_any_child_has_version()` in ModListModel | **JA** | Koennte zu `_any_child_has_update()` erweitert werden fuer Update-spezifisches Separator-Icon |
| `notifications_btn` in toolbar.py | **JA** | Aktuell deaktiviert (`setEnabled(False)`) — muss aktiviert und mit Handler verbunden werden |
| `UpdateChecker` (update_checker.py) | **NEIN** | Git-basierter Self-Update, voellig anderer Kontext |
| `download_manager.py` Queue-Pattern | **NEIN** (nur als Vorlage) | Queue-Pattern als Architektur-Vorlage, keine Code-Aenderung noetig |

---

## Implementierungs-Phasen

### Phase 1 — Grundgeruest (MVP)

**Ziel:** Manueller Update-Check mit visueller Anzeige

1. **Bug-Fix:** `mainwindow.py` Query-Info-Handler — `version` nicht mehr ueberschreiben
2. **ModEntry erweitern:** `newest_version`, `has_update`, `update_ignored`, `last_nexus_check`
3. **`_build_entry()` erweitern:** `newestVersion` und `lastNexusQuery` aus meta.ini lesen
4. **`ModUpdateChecker` erstellen:** Neue Datei mit Phase-1-Logik (Bulk-Check)
5. **NexusAPI erweitern:** `get_updated_mods(game, period)` Endpoint
6. **ModRow erweitern:** `newest_version`, `has_update`, `update_ignored` Slots
7. **ModListModel erweitern:** ForegroundRole (rote Versionsfarbe), DecorationRole (Update-Icon), Tooltip
8. **Toolbar:** `notifications_btn` aktivieren, Click-Handler verbinden
9. **MainWindow:** `_on_check_mod_updates()`, Signal-Verbindungen, Gate-Checks

### Phase 2 — Detail-Checks und Queue

**Ziel:** Einzelne Mod-Details pruefen, praeziserer Versionsvergleich

1. **Phase-2-Logik:** Detail-Requests fuer geaenderte Mods (Queue mit MAX_CONCURRENT=2)
2. **Response-Handler:** `update_check:*` Tag im MainWindow verarbeiten
3. **meta.ini Update:** `newestVersion`, `lastNexusQuery` nach Detail-Check schreiben
4. **Gezieltes UI-Update:** `dataChanged` fuer einzelne Rows statt `_reload_mod_list()`
5. **Toast-Benachrichtigung:** "N Updates verfuegbar" nach Abschluss

### Phase 3 — Settings und Automatik

**Ziel:** Automatischer Check beim Start, konfigurierbare Intervalle

1. **Settings-Dialog:** Checkboxen "Mod-Updates beim Start pruefen", ComboBox "Pruef-Intervall"
2. **Auto-Check:** `QTimer.singleShot(5000, ...)` nach App-Start wenn Setting aktiv
3. **Perioden-Logik:** Automatische Wahl von 1d/1w/1m basierend auf aeltestem lastNexusQuery
4. **Cache:** `.update_cache.json` pro Instanz mit TTL
5. **Cooldown:** 300 Sekunden pro Mod (kein Doppel-Check)

### Phase 4 — Polishing und erweiterte Features

**Ziel:** Feature-Paritaet mit MO2 (soweit sinnvoll)

1. **"Update ignorieren":** Kontextmenue-Eintrag, `ignoredVersion` in meta.ini
2. **Toolbar-Badge:** Zahl-Overlay auf `notifications_btn`
3. **Notifications-Popup:** Klick auf Badge zeigt Liste aller Mods mit Updates
4. **Separator-Aggregation:** Update-Icon auf Separator wenn Kind-Mod Update hat
5. **Downgrade-Erkennung:** Warnung wenn installierte Version neuer als Nexus
6. **Throttle-Schwelle:** Automatischer Abbruch bei < 50 verbleibenden Requests
7. **Locale-Dateien:** Alle 6 Sprachen (de, en, es, fr, it, pt)

---

## Risiken und Mitigations

| Risiko | Schwere | Mitigation |
|---|---|---|
| **API-Rate-Limits bei 500+ Mods** | KRITISCH | Bulk-Endpoint nutzt nur 1 Request pro Game; Detail-Checks nur fuer tatsaechlich geaenderte Mods; MAX_CONCURRENT=2; Throttle-Schwelle bei <50 Requests |
| **version vs. newestVersion Bug** | HOCH | Muss VOR dem Feature-Start gefixt werden — Query-Info darf `version` nicht ueberschreiben |
| **Thread-Safety bei Model-Updates** | HOCH | ALLE Model-Aenderungen im Main-Thread; Worker emittiert nur Daten via Signal; gezieltes `dataChanged` statt Full-Rebuild |
| **GC bei QThread-Workern** | HOCH | Worker als Instanzvariable halten (wie `NexusAPI._workers` Liste); `deleteLater()` nach finished |
| **Versionsvergleich-Problematik** | MITTEL | Phase 1: String-Vergleich `!=`; spaeter `packaging.version` oder eigener Parser; Freitext-Versionen ("Final", "2024-01-01") als "unbekannt" behandeln |
| **Nexus Mod entfernt (404)** | MITTEL | HTTP 404 stiller Abbruch, kein "Update verfuegbar"; optional: Marker "Nicht mehr auf Nexus" |
| **Kein API-Key vorhanden** | NIEDRIG | Stiller Abbruch, kein Fehler-Dialog, kein Statusbar-Spam |
| **Offline/Netzwerk-Fehler** | NIEDRIG | Timeout → stiller Abbruch; Cache-Daten verwenden; StatusBar: "Update-Check fehlgeschlagen" |
| **Concurrent Update-Checks** | NIEDRIG | `is_running()` Gate-Check; Instanz-Wechsel bricht laufenden Check ab |
| **BG3-Instanzen** | NIEDRIG | Gate-Check `self._bg3_installer is not None` → stiller Abbruch |

---

## Akzeptanz-Checkliste

- [ ] 1. Wenn User den Benachrichtigungen-Button in der Toolbar klickt und ein API-Key gesetzt ist, startet ein Update-Check und im Log-Panel erscheint "Pruefe Mod-Updates..." innerhalb von 2 Sekunden
- [ ] 2. Wenn der Bulk-Check 3 Mods mit Updates findet, erscheint eine Toast-Benachrichtigung "3 Updates verfuegbar" nach Abschluss aller Detail-Checks
- [ ] 3. Wenn ein Mod ein Update hat, wird die Versionsnummer in der Mod-Liste in roter Schriftfarbe angezeigt und ein Update-Icon erscheint links neben der Version
- [ ] 4. Wenn der User mit der Maus ueber die rote Versionsnummer faehrt, zeigt der Tooltip "Installiert: 1.2.3 | Neueste: 1.4.0" (mit den tatsaechlichen Versionsnummern)
- [ ] 5. Wenn der Update-Check laeuft und der User die Instanz wechselt, wird der laufende Check abgebrochen und kein Ergebnis fuer die alte Instanz angezeigt
- [ ] 6. Wenn kein API-Key gesetzt ist und der User den Benachrichtigungen-Button klickt, passiert nichts (kein Dialog, kein Fehler, kein Statusbar-Eintrag)
- [ ] 7. Wenn eine BG3-Instanz aktiv ist, ist der Benachrichtigungen-Button ausgegraut und zeigt einen Tooltip "Update-Check fuer BG3 nicht verfuegbar"
- [ ] 8. Wenn 500 Mods installiert sind, werden in Phase 1 maximal 1 API-Request (Bulk-Check) und in Phase 2 maximal 2 gleichzeitige Requests ausgefuehrt (ueberpruefbar via Log-Panel)
- [ ] 9. Wenn der User in den Einstellungen "Mod-Updates beim Start pruefen" aktiviert, startet beim naechsten App-Start automatisch ein Update-Check nach 5 Sekunden
- [ ] 10. Wenn der User per Rechtsklick auf einen Mod mit Update "Update ignorieren" waehlt, verschwindet die rote Markierung und der Mod zaehlt nicht mehr zum Update-Badge
- [ ] 11. Wenn ein Mod manuell installiert wurde (nexus_id = 0), wird er beim Update-Check uebersprungen und zeigt keinen Update-Status an
- [ ] 12. Wenn der Hourly-Rate-Limit unter 10 faellt, bricht der Update-Check ab und zeigt eine Toast-Warnung "Rate-Limit niedrig — Update-Check abgebrochen"
- [ ] 13. Wenn ein Separator eingeklappt ist und ein Kind-Mod ein Update hat, zeigt der Separator ein Update-Icon in der Versions-Spalte
- [ ] 14. Wenn "Query Nexus Info" fuer einen Mod ausgefuehrt wird, bleibt die installierte Version (`version` in meta.ini) unveraendert und nur `newestVersion` wird aktualisiert
- [ ] 15. Wenn der Update-Check abgeschlossen ist, zeigt der Benachrichtigungen-Button in der Toolbar eine Badge-Zahl (z.B. "5") und ist klickbar
- [ ] 16. `restart.sh` startet ohne Fehler
