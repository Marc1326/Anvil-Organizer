# Issue-Verification Review — ReShade Wizard (Issue #71)
Datum: 2026-03-26
Reviewer: Codex-Agent 2

## Issue #71 Anforderungen vs. Implementierung

### User Story 1: "Als Modder moechte ich ReShade per Wizard installieren"
- **Status:** ERFUELLT
- `ReshadeWizard` Dialog mit Status-Seite, DLL-Auswahl, API-Dropdown
- `ReshadeManager.install()` kopiert DLL + erstellt ReShade.ini
- DLL-Backup-Mechanismus vorhanden (Sicherheit)

### User Story 2: "Als Modder moechte ich aus vorhandenen Presets waehlen"
- **Status:** ERFUELLT
- Preset-Seite im Wizard mit Liste, Aktivieren, Hinzufuegen
- `ReshadeManager.list_presets()`, `set_active_preset()`, `add_preset()`

### User Story 3: "Als Modder moechte ich ReShade wieder deinstallieren"
- **Status:** ERFUELLT
- "Deinstallieren" Button mit Bestaetigung
- `ReshadeManager.uninstall()` entfernt DLL + INI + Log
- Backup-Wiederherstellung

### Abgrenzung: "Keine Aenderungen an Game-Plugins"
- **Status:** EINGEHALTEN
- Kein Code in `anvil/plugins/games/` geaendert

### Abgrenzung: "ReShade-Dateien gehen ins Game-Root"
- **Status:** EINGEHALTEN
- `ReshadeManager._binary_dir` berechnet sich aus `game_path + GameBinary.parent`
- Dateien werden direkt dorthin kopiert, nicht ins Staging

## Checkliste-Abgleich

| AK | Beschreibung | Status |
|----|-------------|--------|
| AK-01 | Wizard oeffnet sich ueber Menu | OK — mainwindow.py `_on_reshade_wizard()` |
| AK-02 | Roter Indikator wenn nicht installiert | OK — `_refresh_status()` setzt rote Farbe |
| AK-03 | reshade.me oeffnet im Browser | OK — `QDesktopServices.openUrl` |
| AK-04 | DLL-Validierung (Datei + .dll) | OK — `_on_install()` prueft beides |
| AK-05 | DLL-Kopie + ReShade.ini | OK — `ReshadeManager.install()` |
| AK-06 | Gruener Indikator nach Installation | OK — `_refresh_status()` |
| AK-07 | Deinstallation entfernt DLL + INI | OK — `ReshadeManager.uninstall()` |
| AK-08 | Preset hinzufuegen per Datei-Dialog | OK — `_on_add_preset()` |
| AK-09 | Preset aktivieren | OK — `_on_activate_preset()` |
| AK-10 | Preset entfernen | OK — `_on_remove_preset()` |
| AK-11 | Menu ausgegraut ohne Instanz | OK — `_act_reshade.setEnabled(False)` |
| AK-12 | Einstellungen persistent | OK — QSettings load/save |
| AK-13 | Alle 7 Locale-Dateien | OK — de, en, es, fr, it, pt, ru |
| AK-14 | App startet ohne Fehler | OK — Getestet, kein Traceback |

## Ergebnis: ACCEPTED
