# Claude Review 1 — Issue #70 (Collection Export/Import)
Datum: 2026-03-26
Reviewer: Claude-Agent 1 (Architektur + Signal/Slot-Flow)

## Pruefumfang
Architektur-Konsistenz, Signal/Slot-Verbindungen, Variable Scope, ARCHITEKTUR-Konformitaet.

## Signal-Flow Analyse

### Export-Flow:
```
ProfileBar.dots_menu → QAction("collection.export_menu")
  → lambda checked: export_collection_requested.emit()          [profile_bar.py:291]
  → MainWindow._export_collection                                [mainwindow.py:172]
  → CollectionExportDialog.exec()                                [mainwindow.py:3035]
  → build_manifest() → export_collection()                       [mainwindow.py:3043-3071]
  → Toast + statusBar                                            [mainwindow.py:3073-3084]
```

**Alternativ-Pfad (Datei-Menue):**
```
File Menu → QAction("collection.export_menu")
  → act.triggered.connect(self._export_collection)               [mainwindow.py:381]
```

### Import-Flow:
```
ProfileBar.dots_menu → QAction("collection.import_menu")
  → lambda checked: import_collection_requested.emit()          [profile_bar.py:292]
  → MainWindow._import_collection                                [mainwindow.py:173]
  → QFileDialog.getOpenFileName()                                [mainwindow.py:3107]
  → read_collection() → analyze_collection()                     [mainwindow.py:3120-3130]
  → CollectionImportDialog.exec()                                [mainwindow.py:3140-3147]
  → apply_collection()                                           [mainwindow.py:3156-3162]
  → _reload_mod_list() + _do_redeploy()                          [mainwindow.py:3172-3173]
  → Toast                                                        [mainwindow.py:3176-3183]
```

### Signal-Verbindungen geprueft:
| Signal | Empfaenger | Korrekt |
|--------|------------|---------|
| export_collection_requested | _export_collection | Ja (mainwindow.py:172) |
| import_collection_requested | _import_collection | Ja (mainwindow.py:173) |
| QAction.triggered (Export-Menu) | _export_collection | Ja (mainwindow.py:381) |
| QAction.triggered (Import-Menu) | _import_collection | Ja (mainwindow.py:384) |
| link_btn.clicked | lambda → QDesktopServices.openUrl | Ja (import_dialog:67-71) |

### Lambda-Pattern korrekt:
- `lambda checked=False:` in profile_bar.py:291, 292 — OK (Qt clicked bool)
- `lambda checked=False, u=nexus_url:` in import_dialog:68 — OK (Closure + Qt bool)

## Architektur-Konformitaet

### Positiv:
1. **Lazy Imports**: Dialoge und collection_io werden innerhalb der Methoden importiert — konsistent mit bestehendem Pattern (_create_backup, _ctx_export_csv)
2. **Instanz-Pfade aus Config**: `self._current_instance_path` und `self._current_profile_path` kommen aus instance_manager, keine hardcoded Pfade
3. **Plugin-Attribute via getattr**: `getattr(self._current_plugin, "GameName", "")` — sicher bei fehlendem Attribut
4. **Neue Dateien korrekt platziert**: core → collection_io.py, dialogs → collection_*_dialog.py
5. **Kein BG3-Code angefasst**: Keine Aenderungen an BG3-spezifischem Code
6. **Keine Game-Plugin Aenderungen**: Korrekt
7. **Separator-Konvention**: `name.endswith("_separator")` — konsistent mit dem Rest des Projekts

### Variable Scope:
- `self._current_instance_path`: initialisiert in __init__ (Zeile 305), gesetzt in _load_instance
- `self._current_profile_path`: initialisiert in __init__ (Zeile 304), gesetzt in _load_instance
- `self._current_plugin`: initialisiert in __init__ (Zeile 307), gesetzt in _load_instance
- `self._current_mod_entries`: initialisiert in __init__ (Zeile 301), gesetzt in _load_instance
- Alle Guards (`if not self._current_instance_path`) sind vorhanden

### Datei-I/O Konsistenz:
- `read_global_modlist(profiles_dir)` / `write_global_modlist(profiles_dir, ...)` — konsistent mit mod_list_io.py API
- `read_active_mods(profile_path)` / `write_active_mods(profile_path, ...)` — konsistent
- `read_meta_ini(mod_path)` / `write_meta_ini(mod_path, data)` — konsistent

### _reload_mod_list + _do_redeploy nach Import:
- Notwendig um UI und Deployer zu aktualisieren
- Gleicher Pattern wie bei `_restore_backup` — konsistent

## Keine Findings

## Ergebnis: ACCEPTED

Architektur ist konsistent mit dem bestehenden Projekt. Signal/Slot-Flow korrekt. Alle Variable-Scopes geprueft und sicher.
