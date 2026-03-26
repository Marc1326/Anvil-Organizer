# Architektur-Review - Issue #67 (Custom Deploy Paths pro Separator)
Datum: 2026-03-26
Reviewer: Claude Review Agent 1 (Architektur + Code-Qualitaet)

## Ergebnis: ACCEPTED

## Architektur-Konformitaet

### Schichtenmodell
- **Data Layer** (mod_entry.py): Neues Feld `deploy_path` — korrekt, analog zu `color`
- **Core Layer** (mod_deployer.py): Neue Logik isoliert in deploy() und purge() — kein Leak in andere Module
- **View Layer** (mod_list_model.py): ToolTipRole fuer deploy_path — korrekt, analog zu conflict tooltips
- **Orchestration** (mainwindow.py): Kontextmenue + _sync_separator_deploy_paths() — folgt bestehendem Pattern (vgl. Separator-Color)
- **Widget Layer** (game_panel.py): set_separator_deploy_paths() als Clean API — korrekt

### Pattern-Konsistenz

| Pattern | Separator Color (bestehend) | Custom Deploy Path (neu) | Konsistent? |
|---------|----------------------------|--------------------------|-------------|
| meta.ini Key | `color` | `deploy_path` | Ja |
| ModEntry Feld | `color: str = ""` | `deploy_path: str = ""` | Ja |
| ModRow Slot | `color` | `deploy_path` | Ja |
| Kontextmenue | set/reset Color | set/reset Deploy Path | Ja |
| _build_entry() | Liest aus meta.ini | Liest aus meta.ini | Ja |
| mainwindow Handler | _ctx_select_color / _ctx_reset_color | _ctx_set_deploy_path / _ctx_reset_deploy_path | Ja |

### Import-Analyse
- `write_meta_ini` Import in mainwindow.py: Lazy import innerhalb der Handler-Funktionen — korrekt, konsistent mit bestehendem Color-Pattern
- Keine fehlenden Imports identifiziert
- `QFileDialog` bereits im mainwindow.py importiert (oben im File)

### Signal-Verbindungen
- Keine neuen Signal-Verbindungen noetig
- `dataChanged.emit()` korrekt mit ToolTipRole als Role-Liste
- Kein Lambda mit bool-Parameter Problem

### Abwaertskompatibilitaet
- Manifest ohne `deploy_base` Feld: Purge nutzt game_path als Fallback — korrekt
- created_dirs ohne `:` Format: game_path wird genutzt — korrekt
- ModEntry ohne deploy_path: leerer String = Fallback — korrekt
- Bestehende meta.ini ohne deploy_path: kein Fehler — korrekt

### Code-Qualitaet
- Keine hardcoded Pfade
- Keine setStyleSheet() Aufrufe
- Korrekte Benennung (Deutsch/Englisch-Mix konsistent mit Codebase)
- Kommentare erklaeren das "Warum", nicht das "Was"

## Keine Findings
