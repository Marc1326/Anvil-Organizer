# Agent 2 Report: Redeploy-Analyse -- Signal-Flow und Luecken

**Datum:** 2026-03-02
**Agent:** Agent 2 (Planer)
**Scope:** mainwindow.py + game_panel.py -- alle deploy/purge Aufrufe

---

## 1. Vollstaendige Auflistung aller deploy/purge Aufrufe

### 1.1 In mainwindow.py

| Zeile | Methode                     | Aufruf              | Trigger                        |
|-------|-----------------------------|----------------------|--------------------------------|
| 803   | `_apply_instance()`         | `silent_purge()`     | Instanz-Wechsel (alte Daten)   |
| 953   | `_apply_instance()`         | `silent_deploy()`    | Instanz-Wechsel (neue Daten)   |
| 2211  | `_on_profile_changed()`     | `silent_purge()`     | Profil-Wechsel (alte Daten)    |
| 2213  | `_on_profile_changed()`     | `silent_deploy()`    | Profil-Wechsel (neue Daten)    |
| 3057  | `closeEvent()`              | `silent_purge()`     | App wird geschlossen           |

### 1.2 In game_panel.py

| Zeile | Methode            | Was passiert                                           |
|-------|--------------------|--------------------------------------------------------|
| 546   | `silent_deploy()`  | deployer.deploy() + BA2-Packing + plugins.txt schreiben |
| 605   | `silent_purge()`   | deployer.purge() + BA2-Cleanup + plugins.txt loeschen   |

### 1.3 Crash-Recovery (mainwindow.py)

| Zeile | Methode                    | Aufruf                        | Trigger                   |
|-------|----------------------------|-------------------------------|---------------------------|
| 733   | `_crash_recovery_purge()`  | `ModDeployer.purge()` direkt  | App-Start (alle Instanzen)|

---

## 2. Signal-Flow Diagramme

### 2.1 Checkbox-Klick (Mod aktivieren/deaktivieren)

```
User klickt Checkbox in ModListView
    |
    v
ModListModel.setData() [Zeile 329-337]
    |-- setzt row.enabled = new_enabled
    |-- emittiert dataChanged (visuelles Update)
    |-- emittiert mod_toggled(row, enabled)
    |
    v
MainWindow._on_mod_toggled(row, enabled) [Zeile 1022-1034]
    |-- findet ModEntry ueber display_name
    |-- setzt entry.enabled = enabled
    |-- ruft _write_current_modlist() auf
    |       |-- schreibt modlist.txt (globale Reihenfolge)
    |       |-- schreibt active_mods.json (aktive Mods im Profil)
    |-- ruft _update_active_count() auf
    |
    v
    ENDE --- KEIN silent_purge() / silent_deploy()
```

**Ergebnis:** Die Aenderung wird auf Disk gespeichert, aber die Symlinks im Spielverzeichnis werden NICHT aktualisiert.

### 2.2 Drag & Drop (Mod-Reihenfolge aendern)

```
User zieht Mod an neue Position
    |
    v
ModListModel.dropMimeData() [Zeile ~470]
    |-- verschiebt Zeile im Model
    |-- ruft _update_priorities() auf
    |       |-- nummeriert Prioritaeten neu durch
    |       |-- emittiert dataChanged (Prioritaets-Spalte)
    |       |-- emittiert mods_reordered()
    |
    v
MainWindow._on_mods_reordered() [Zeile 1036-1063]
    |-- baut new_entries aus Model-Reihenfolge
    |-- setzt entry.priority = i
    |-- haengt Framework-Entries an
    |-- ruft _write_current_modlist() auf
    |-- ruft _update_active_count() auf
    |-- berechnet conflict_data neu
    |-- emittiert dataChanged (Conflict-Icons)
    |
    v
    ENDE --- KEIN silent_purge() / silent_deploy()
```

### 2.3 Instanz-Wechsel (funktioniert korrekt)

```
User waehlt neue Instanz in Dropdown
    |
    v
MainWindow.switch_instance(name) [Zeile 789]
    |-- setzt current_instance
    |-- ruft _apply_instance(name) auf
    |
    v
MainWindow._apply_instance(name) [Zeile 793-1000]
    |-- silent_purge()                    [Zeile 803]
    |-- load_instance(name)
    |-- update_game()
    |-- set_instance_path()
    |-- silent_deploy()                   [Zeile 953]
    |
    v
    OK --- Purge + Deploy korrekt
```

### 2.4 Profil-Wechsel (funktioniert korrekt)

```
User waehlt neues Profil in ProfileBar
    |
    v
MainWindow._on_profile_changed(name) [Zeile 2149-2213]
    |-- speichert active_mods des ALTEN Profils
    |-- laedt active_mods des NEUEN Profils
    |-- ruft _apply_active_state() auf (Checkboxes aktualisieren)
    |-- silent_purge()                    [Zeile 2211]
    |-- set_instance_path(profile_name)
    |-- silent_deploy()                   [Zeile 2213]
    |
    v
    OK --- Purge + Deploy korrekt
```

### 2.5 App schliessen (funktioniert korrekt)

```
User schliesst App
    |
    v
MainWindow.closeEvent() [Zeile 3055-3059]
    |-- silent_purge()                    [Zeile 3057]
    |-- _save_ui_state()
    |
    v
    OK --- Purge korrekt, kein Deploy noetig
```

### 2.6 App-Start (funktioniert korrekt)

```
App startet
    |
    v
MainWindow._initial_load() [Zeile 726-757]
    |-- _crash_recovery_purge()           [Zeile 733]
    |-- _apply_instance(current)          [Zeile 750]
    |       |-- silent_purge() + silent_deploy()
    |
    v
    OK --- Crash-Recovery + Auto-Deploy
```

---

## 3. Kontextmenu-Aktionen OHNE Redeploy

### 3.1 _ctx_enable_selected (Zeile 2430-2443)

```
User markiert mehrere Mods -> Rechtsklick -> "Alle aktivieren/deaktivieren"
    |
    v
_ctx_enable_selected(rows, enabled) [Zeile 2430-2443]
    |-- setzt entry.enabled fuer alle Zeilen
    |-- setzt model._rows[row].enabled
    |-- emittiert dataChanged (CheckState)
    |-- ruft _write_current_modlist() auf
    |-- ruft _update_active_count() auf
    |
    v
    ENDE --- KEIN Redeploy
```

### 3.2 _ctx_enable_all (Zeile 2445-2450)

Ruft `_ctx_enable_selected` mit allen Zeilen auf. Gleiches Problem.

### 3.3 _install_archives -> _reload_mod_list (Zeile 1362)

```
User installiert Mod (Drop oder Downloads-Tab)
    |
    v
_install_archives() [Zeile 1194-1381]
    |-- Mod wird in .mods/ extrahiert
    |-- add_mod_to_modlist() aufgerufen
    |-- _reload_mod_list() aufgerufen    [Zeile 1362]
    |
    v
    ENDE --- KEIN Redeploy (neue Mod ist in modlist, aber nicht deployed)
```

### 3.4 _ctx_remove_mods -> _reload_mod_list (Zeile 2755)

```
User loescht Mod ueber Kontextmenu
    |
    v
_ctx_remove_mods() [Zeile 2726-2757]
    |-- Mod-Ordner wird geloescht
    |-- Mod aus modlist.txt entfernt
    |-- _reload_mod_list() aufgerufen    [Zeile 2755]
    |
    v
    ENDE --- KEIN Redeploy (alte Symlinks zeigen ins Leere!)
```

### 3.5 _ctx_rename_mod -> _reload_mod_list (Zeile 2689)

```
User benennt Mod um
    |
    v
_ctx_rename_mod() [Zeile 2655-2691]
    |-- Ordner wird umbenannt
    |-- modlist.txt wird aktualisiert
    |-- _reload_mod_list() aufgerufen    [Zeile 2689]
    |
    v
    ENDE --- KEIN Redeploy (Symlinks zeigen auf alten Ordnernamen!)
```

---

## 4. Luecken-Analyse: Wo FEHLT ein Redeploy?

### KRITISCHE Luecken (deployed State stimmt nicht mit UI ueberein)

| Nr | Stelle               | Zeile | Problem                                                    | Schwere |
|----|----------------------|-------|------------------------------------------------------------|---------|
| 1  | `_on_mod_toggled`    | 1022  | Checkbox-Klick aendert Disk, aber nicht die Symlinks       | HOCH    |
| 2  | `_on_mods_reordered` | 1036  | Prioritaets-Aenderung per D&D, Symlinks unveraendert      | HOCH    |
| 3  | `_ctx_enable_selected`| 2430 | Bulk-Enable/Disable, Symlinks unveraendert                 | HOCH    |
| 4  | `_ctx_remove_mods`   | 2726  | Mod geloescht, aber Symlinks zeigen ins Leere              | HOCH    |
| 5  | `_ctx_rename_mod`    | 2655  | Mod umbenannt, Symlinks zeigen auf alten Namen             | HOCH    |

### MITTLERE Luecken (neuer Content nicht deployed)

| Nr | Stelle                | Zeile | Problem                                                   | Schwere  |
|----|-----------------------|-------|-----------------------------------------------------------|----------|
| 6  | `_install_archives`   | 1194  | Neue Mod installiert, aber nicht deployed                  | MITTEL   |
| 7  | `_ctx_reinstall_mod`  | 2693  | Mod reinstalliert, alte Symlinks bleiben                   | MITTEL   |
| 8  | Backup wiederherstellen| 2105 | Backup-Restore, Deployment veraltet                       | MITTEL   |

### NIEDRIGE Luecken (kosmetisch / Edge Cases)

| Nr | Stelle                 | Zeile | Problem                                                  | Schwere  |
|----|------------------------|-------|----------------------------------------------------------|----------|
| 9  | F5-Refresh             | 504   | Nur UI-Refresh, kein Redeploy (intentional?)             | NIEDRIG  |
| 10 | Leere Mod erstellen    | 2389  | Leere Mod = nichts zu deployen (kein Problem)            | KEINE    |
| 11 | Separator erstellen    | 1812  | Separator = kein deploybare Mod (kein Problem)           | KEINE    |

---

## 5. Signal-Verbindungen (Ueberblick)

```
ModListModel (mod_list_model.py)
    |
    |-- mod_toggled(int, bool)     --> MainWindow._on_mod_toggled()
    |-- mods_reordered()           --> MainWindow._on_mods_reordered()

ProfileBar
    |
    |-- profile_changed(str)       --> MainWindow._on_profile_changed()

GamePanel
    |
    |-- install_requested(list)    --> MainWindow._on_downloads_install()
    |-- start_requested(str, str)  --> MainWindow._on_start_game()

ModListView
    |
    |-- archives_dropped(list)     --> MainWindow._on_archives_dropped()
```

---

## 6. Detail: Was passiert in silent_deploy() / silent_purge()

### silent_deploy() -- game_panel.py Zeile 546-603

```
silent_deploy()
    |
    |-- 1. deployer.deploy()
    |       |-- Liest modlist.txt + active_mods.json
    |       |-- Erstellt Symlinks fuer alle aktiven Mods
    |       |-- Speichert Manifest (.deploy_manifest.json)
    |
    |-- 2. BA2-Packing (nur Bethesda-Spiele mit NeedsBa2Packing)
    |       |-- Packt loose Files in BA2-Archive
    |       |-- Aktualisiert INI-Eintraege
    |
    |-- 3. plugins.txt schreiben (nur Bethesda-Spiele mit has_plugins_txt())
    |       |-- PluginsTxtWriter.write()
    |       |-- _refresh_plugins_tab()
```

### silent_purge() -- game_panel.py Zeile 605-634

```
silent_purge()
    |
    |-- 1. deployer.purge()
    |       |-- Liest Manifest
    |       |-- Entfernt alle Symlinks
    |       |-- Loescht Manifest
    |
    |-- 2. BA2-Cleanup (nur Bethesda-Spiele)
    |       |-- Entfernt BA2-Archive
    |       |-- Stellt INI wieder her
    |
    |-- 3. plugins.txt loeschen (nur Bethesda-Spiele)
    |       |-- PluginsTxtWriter.remove()
```

---

## 7. Empfehlung

Ein Redeploy muss nach folgenden Aktionen stattfinden:

1. **`_on_mod_toggled`** -- nach Checkbox-Klick (mit Debounce)
2. **`_on_mods_reordered`** -- nach Drag & Drop (mit Debounce)
3. **`_ctx_enable_selected`** -- nach Bulk-Enable/Disable
4. **`_ctx_remove_mods`** -- nach Mod-Loeschung
5. **`_ctx_rename_mod`** -- nach Umbenennung
6. **`_install_archives`** -- nach Mod-Installation

Das Muster waere jeweils: `silent_purge()` gefolgt von `silent_deploy()`.

Bei Performance-Bedenken: Ein QTimer mit ~500ms Debounce, der nach dem letzten Toggle/Reorder feuert.

---

## 8. Betroffene Dateien

| Datei | Rolle |
|-------|-------|
| `anvil/mainwindow.py` | Orchestriert alles, alle Luecken sind hier |
| `anvil/widgets/game_panel.py` | Enthaelt silent_deploy/purge (korrekt) |
| `anvil/core/mod_deployer.py` | Deploy-Logik (korrekt) |
| `anvil/models/mod_list_model.py` | Signal-Emitter (korrekt) |
