# Code-Review — Features #21 (Nexus Server-Auswahl) & #23 (Diagnose-Tab)

Datum: 2026-07-02
Reviewer: qa-pruefer (nur lesend)
Commits: 6fb4259 (#21), 35c7e18 (#23)
Geprüfte Dateien:
- anvil/core/diagnostics.py (neu, komplett)
- anvil/widgets/settings_dialog.py (Diagnose-Tab + Nexus-Server-Sektion)
- anvil/mainwindow.py (_server_id, _cache_known_servers, _select_download_server,
  _run_conflict_scan, collect_diagnostics_conflicts)
- anvil/locales/{de,en,es,fr,it,pt,ru}.json

Vorab gelesen: ARCHITEKTUR.md. MO2-Vergleich hier nicht einschlägig — beide Features
berühren KEINE Mod-Verwaltung/Deploy/modlist.txt/Installation (Diagnose ist read-only,
Nexus-Server nur Download-URL-Auswahl). Die 7 Architektur-Regeln sind nicht verletzt.

---

## Funde

### 1. MITTEL — Blockierende I/O beim Öffnen des Settings-Dialogs
- Datei: anvil/widgets/settings_dialog.py:896-897 (`_diag_refresh()`, `_diag_populate_log_sources()` im __init__)
- Problem: Beide werden EAGER bei jedem Öffnen der Einstellungen aufgerufen — auch wenn
  der Diagnose-Tab nie angeschaut wird. `collect_deploy_status` stattet JEDEN Manifest-
  Eintrag ab (reales Starfield-Manifest: 504 Einträge → 504+ synchrone `is_symlink`/`exists`
  Stat-Calls im GUI-Thread). `read_log_tail` liest die komplette activity.log. Auf großen
  Deploys oder langsamen Mounts (z.B. /mnt/gamingS) friert die UI beim Öffnen der
  Einstellungen kurz ein.
- Fix: Lazy laden, wenn der Diagnose-Tab zum ersten Mal aktiviert wird
  (QTabWidget.currentChanged), oder Deploy-/Log-Sammlung in einen Worker-Thread auslagern.

### 2. MITTEL — Blockierender Konflikt-Scan im GUI-Thread
- Datei: anvil/widgets/settings_dialog.py:1176-1194 (`_diag_scan_conflicts`) → mainwindow.py `collect_diagnostics_conflicts` → `_run_conflict_scan` → `ConflictScanner().scan_conflicts`
- Problem: Auf Knopfdruck läuft ein vollständiger Dateisystem-Scan aller aktiven Mods
  synchron im GUI-Thread. Bei vielen Mods spürbarer UI-Freeze ohne Fortschrittsanzeige.
- Fix: Scan in Worker-Thread/QThreadPool, Button während des Scans deaktivieren, Busy-Cursor.

### 3. MITTEL — read_log_tail lädt die gesamte Datei in den RAM
- Datei: anvil/core/diagnostics.py:257-269
- Problem: `f.readlines()` liest die komplette Logdatei, erst danach werden die letzten
  max_lines geschnitten. Bei großer activity.log unnötiger Speicher-/Zeitaufwand.
- Fix: Rückwärts lesen (seek ans Dateiende) oder `collections.deque(f, maxlen=max_lines)`.

### 4. NIEDRIG — Export verschluckt Fehler still, kein Feedback
- Datei: anvil/widgets/settings_dialog.py:1258-1266 (`_diag_export`)
- Problem: `except OSError: pass` — schlägt das Schreiben fehl, erfährt der Nutzer nichts.
  Auch bei Erfolg gibt es keine Rückmeldung. Nutzer weiß nicht, ob der Export geklappt hat.
- Fix: Erfolg/Fehler über statusBar oder QMessageBox rückmelden.

### 5. NIEDRIG — Diagnose-Report enthält vollständige Pfade inkl. Benutzername
- Datei: anvil/core/diagnostics.py:288-296 (build_report, Abschnitt [Pfade])
- Problem: Der Export enthält absolute Pfade wie /home/mob/... (Benutzername). KEIN API-Key
  (positiv, siehe unten), aber der Username ist milde PII. Für Support-Reports üblich,
  dennoch erwähnenswert.
- Fix: Optional Home-Pfad zu `~` normalisieren oder Hinweis im Export-Dialog.

### 6. NIEDRIG — Hardcoded Hex-Farben statt Theme-Palette
- Datei: anvil/widgets/settings_dialog.py:1141-1148 (Pfad-Status), 1170-1174 (Problem-Severity)
- Problem: `#98C379/#E5C07B/#E06C75/#888888` via `setForeground` — passen sich nicht an
  wechselnde Themes an. (Kein setStyleSheet-Verstoß, aber theme-inkonsistent.)
- Fix: Farben aus der Theme-Palette/COLOR_ROLES beziehen, sofern verfügbar.

### 7. NIEDRIG — Wiederholte lokale Imports (kosmetisch)
- Datei: diagnostics.py (`import PySide6`, `find_loot_binary`), settings_dialog.py
  (`from anvil.core import diagnostics` in mehreren Methoden), mainwindow.py
  (`from urllib.parse import urlparse` pro _server_id-Aufruf)
- Problem: Reiner Stil; Module sind gecacht. Kein Bug.
- Fix: Optional an den Dateikopf ziehen.

---

## Bestätigte Anforderungen (positiv)

- Imports vollständig: QAbstractItemView, QPlainTextEdit, QApplication, QFileDialog,
  host_open_path, json — alle vorhanden. KEIN fehlender Import.
- Signal/Slot bool-Falle: Alle Lambdas absorbieren den Qt-Parameter korrekt
  (`lambda checked=False`, `lambda _i`, `lambda _t`).
- tr()-Keys: Alle 44 geprüften Keys existieren in ALLEN 7 Locales (de,en,es,fr,it,pt,ru).
  Platzhalter {path}/{label}/{mode}/{total}/{broken}/{missing} passen zu den tr()-kwargs.
- Anforderung #8 (KEIN API-Key im Export): build_report enthält ausschliesslich
  Systeminfo, Pfad-Checks, Deploy-Status, Probleme und Konflikte — KEINE Credentials/
  API-Keys. Bestätigt sicher.
- Anforderung #9 (Fallback data[0]): `_select_download_server` fällt korrekt auf data[0]
  zurück — bei len<=1, fehlender Präferenz, keinem Treffer UND leerem URI des Treffers.
  Alle Nicht-Dict-Fälle sind abgesichert.
- _PATH_KEYS matchen die realen Config-Keys (Paths-Gruppe erhält path_-Präfix via
  _read_ini, game_path in [General]). Korrekt.
- Manifest-Format: reale Einträge haben KEIN deploy_base → Fallback auf game_path greift,
  Deploy-Status wird korrekt berechnet.
- Konflikt-Dicts tragen immer file/winner → Anzeige robust.
- Hardcoded Systempfade (/etc/os-release, /proc/meminfo, ~/.anvil-organizer/logs) sind
  begründet/unvermeidbar, KEINE spielbezogenen hardcoded Pfade.
- Kein setStyleSheet in neuem Diagnose-/Nexus-Server-Code.
- _idata/_instance_path sind vor _diag_refresh() gesetzt (Zeilen 72-78) — keine
  Reihenfolge-Falle.
- Instanzvariablen halten alle neuen Widgets (_nexus_known_list, _nexus_pref_list,
  _diag_* ) — keine GC-Gefahr.

---

## Ergebnis

KEINE kritischen/crash-relevanten Bugs. Beide Features sind funktional korrekt
implementiert und erfüllen die Kern-Anforderungen (#8 API-Key-Schutz, #9 Fallback).
Offene Punkte sind 3x MITTEL (blockierende I/O im GUI-Thread) und 4x NIEDRIG (UX/Style).

NEEDS FIXES (nicht blockierend für Commit, aber Punkte 1-3 sollten adressiert werden,
bevor große Deploys / langsame Mounts betroffen sind).
