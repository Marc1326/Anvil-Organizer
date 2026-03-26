# Codex Review 2 — Issue #63: Signal/Slot-Flow, Variable Scope, Imports

## Geprueft

### Imports
- [x] `json` Import in base_game.py hinzugefuegt — korrekt
- [x] `sys` Import in base_game.py hinzugefuegt — korrekt
- [x] Keine fehlenden Imports in mainwindow.py (keine neuen noetig)
- [x] Keine fehlenden Imports in instance_wizard.py (nutzt `getattr` builtin)
- [x] Keine fehlenden Imports in settings_dialog.py (nutzt `getattr` builtin)
- [x] Keine fehlenden Imports in plugin_loader.py (keine neuen noetig)

### Aufruf-Kette
- [x] `all_framework_mods()` → `get_framework_mods()` + `_load_json_frameworks()` — korrekt
- [x] `is_framework_mod()` → `all_framework_mods()` — korrekt
- [x] `get_installed_frameworks()` → `all_framework_mods()` — korrekt
- [x] `mainwindow.py` 3 Stellen umgestellt — korrekt
- [x] `bg3_mod_installer.py` ruft `is_framework_mod()` und `get_installed_frameworks()` auf → intern umgestellt → korrekt
- [x] `game_panel.py` ruft `get_installed_frameworks()` auf → intern umgestellt → korrekt

### Variable Scope
- [x] `all_framework_mods()` — `python_fws` wird lokal erzeugt und mutiert (append), das ist sicher da `get_framework_mods()` immer eine neue Liste zurueckgibt
- [x] `_load_json_frameworks()` — `results` ist lokal, `short` und `json_name` lokal — korrekt
- [x] `_framework_json_dirs()` — gibt neue Liste zurueck — korrekt
- [x] Kein mutable default argument Problem (alle Attribute sind Class-Level)

### MRO-Pruefung
- [x] Bestehende Plugins (Cyberpunk, Fallout 4, Starfield, BG3, Witcher 3, RDR2) ueberschreiben `gameDocumentsDirectory()` und/oder `gameSavesDirectory()` → Override gewinnt
- [x] WIP-Plugins (Skyrim SE, Elden Ring, Fallout 3, Fallout NV, Morrowind, Oblivion Rem., Bannerlord, Stardew Valley) ueberschreiben ebenfalls → Override gewinnt
- [x] BaseGame Default-Implementierung greift NUR wenn Subklasse NICHT ueberschreibt UND `_WIN_DOCUMENTS`/`_WIN_SAVES` gesetzt ist

### Beta-Markierung
- [x] `getattr(plugin, "Tested", True)` statt `plugin.Tested` — sicherer fuer Plugins die das Attribut nicht haben
- [x] Drei UI-Stellen angepasst: Wizard-Spieleliste, Settings-Plugin-Liste, Settings-Plugin-Details

## Ergebnis

**ACCEPTED** — Keine Findings.
