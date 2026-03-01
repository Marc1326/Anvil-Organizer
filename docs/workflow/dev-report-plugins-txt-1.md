# Dev-Report: plugins.txt Fix -- Iteration 1

## Implementierte Aenderungen

### 1. `anvil/core/plugins_txt_writer.py`

**Neue Methode `_remove_case_variants()`** (Zeilen 40-64):
- Scannt das Verzeichnis nach Dateien die case-insensitiv den gleichen Namen haben
- Loescht alle Varianten die NICHT exakt dem Ziel-Dateinamen entsprechen
- Defensiv: OSError wird still gefangen

**In `write()` eingebaut** (Zeile 144):
- `self._remove_case_variants(txt_path)` wird VOR dem Schreiben aufgerufen
- Stellt sicher dass nur EINE Datei verbleibt

**In `remove()` eingebaut** (Zeile 167):
- `self._remove_case_variants(txt_path)` wird VOR dem Loeschen aufgerufen
- Entfernt auch Case-Varianten bei Purge

**Diagnostik-Logging in `scan_plugins()`** (Zeilen 78, 94-96):
- Data-Verzeichnis nicht vorhanden: "Data directory not found: {path}"
- Keine Plugin-Dateien: "No plugin files found in {path}"
- OSError: war bereits implementiert

### 2. `anvil/widgets/game_panel.py`

**write()-Rueckgabe-Pruefung in `silent_deploy()`** (Zeilen 599-600):
- Speichert Rueckgabewert von `writer.write()`
- Bei None: "[GamePanel] plugins.txt write failed or skipped"

## Verifizierung

- [x] `python -m py_compile plugins_txt_writer.py` -- OK
- [x] `python -m py_compile game_panel.py` -- OK
- [x] App startet ohne Fehler (QTabBar alignment Warnings sind bekannt)
- [x] plugins.txt enthaelt 21 Eintraege (8 PRIMARY + 4 Mod-ESPs + 9 CC-ESLs)
- [x] Log zeigt: "[PluginsTxtWriter] Wrote 21 plugins to ..."
- [x] Nur EINE plugins.txt Datei im Verzeichnis (keine Plugins.txt)
