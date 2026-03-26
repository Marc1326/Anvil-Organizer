# Codex Review 1 — Issue #63: Code-Review (Bugs, Logikfehler, Edge Cases)

## Geprueft

### base_game.py
- [x] `_WIN_DOCUMENTS` und `_WIN_SAVES` als leere Strings (Default) — korrekt, `if not self._WIN_DOCUMENTS` faengt das ab
- [x] `gameDocumentsDirectory()` und `gameSavesDirectory()` pruefen `is_dir()` — korrekt
- [x] `Tested: bool = True` Default — korrekt, bestehende Plugins aendern sich nicht
- [x] `all_framework_mods()` — Merge-Logik korrekt: Python-Namen werden zuerst gesammelt, JSON nur bei neuem Namen
- [x] `_load_json_frameworks()` — try/except mit stderr, graceful bei Fehlern
- [x] `_load_json_frameworks()` — `entry["name"]` wirft KeyError wenn "name" fehlt → wird vom aeusseren except gefangen → graceful
- [x] `_framework_json_dirs()` — lazy import von `get_anvil_base` korrekt
- [x] `is_framework_mod()` nutzt jetzt `all_framework_mods()` statt `get_framework_mods()` — korrekt
- [x] `get_installed_frameworks()` nutzt jetzt `all_framework_mods()` statt `get_framework_mods()` — korrekt
- [x] `json` und `sys` Import hinzugefuegt — korrekt

### mainwindow.py
- [x] Zeile 1430: `get_framework_mods()` → `all_framework_mods()` — korrekt
- [x] Zeile 4188: `get_framework_mods()` → `all_framework_mods()` — korrekt
- [x] Zeile 4230: `get_framework_mods()` → `all_framework_mods()` — korrekt
- [x] Keine weiteren Stellen mit `get_framework_mods()` im Core-Code

### plugin_loader.py
- [x] `_scan_directory(_BUILTIN_GAMES_DIR / "_wip")` — korrekt, `_scan_directory` prueft `if not directory.is_dir()` am Anfang
- [x] README-Text ist vollstaendig und korrekt
- [x] Keine bestehende Logik geaendert

### instance_wizard.py
- [x] `getattr(plugin, "Tested", True)` — sicherer Zugriff, Fallback True — korrekt

### settings_dialog.py
- [x] `getattr(plugin, "Tested", True)` — sicherer Zugriff, Fallback True — korrekt
- [x] Zwei Stellen angepasst (Plugin-Liste + Plugin-Details) — korrekt

### WIP-Plugins
- [x] Alle 8 Plugins: `Tested = False` gesetzt — korrekt
- [x] Kein anderer Code in den WIP-Plugins geaendert — korrekt

### .gitignore
- [x] _wip/ Eintrag auskommentiert — korrekt

## Edge Cases
- [x] JSON-Datei existiert aber ist leer → `data.get("frameworks", [])` gibt leere Liste → OK
- [x] JSON-Datei mit fehlenden optionalen Feldern → `.get()` mit Defaults → OK
- [x] Zwei JSON-Dateien (builtin + user) mit gleichem Framework-Namen → erste gewinnt → OK
- [x] Plugin ohne `GameShortName` → leerer String → `game_.json` → existiert nicht → OK

## Ergebnis

**ACCEPTED** — Keine Findings.
