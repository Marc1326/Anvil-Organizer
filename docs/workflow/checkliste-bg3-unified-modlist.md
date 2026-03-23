# Feature-Spec: BG3 Einheitliche Mod-Liste (Issue #57)
Datum: 2026-03-23

## User Stories
- Als User moechte ich alle BG3 Mods in einer einzigen Liste sehen, mit Checkbox zum Aktivieren/Deaktivieren.
- Als User moechte ich, dass ein Mod sofort deployed wird wenn ich die Checkbox aktiviere (Auto-Deploy).
- Als User moechte ich den Deploy-Button nicht mehr sehen, weil er unnoetig ist.
- Als User moechte ich sehen wie viele Mods aktiv sind im Format "X / Y".
- Als User moechte ich, dass neu installierte Mods sofort in der Liste erscheinen.

## Technische Planung

### Betroffene Dateien
| Datei | Aenderung |
|-------|-----------|
| `anvil/widgets/bg3_mod_list.py` | Inaktiv-Sektion + Section-Header entfernen, eine Liste mit einem Model |
| `anvil/models/bg3_mod_list_model.py` | allow_reorder immer True, Checkbox toggle triggert Signal |
| `anvil/core/bg3_mod_installer.py` | `get_mod_list()` gibt eine Liste zurueck, `_migrate_state()` fuegt neue .pak in mod_order ein, Auto-Deploy in activate/deactivate |
| `anvil/mainwindow.py` | Deploy-Button/Separator hidden fuer BG3, Zaehler auf "X / Y", Signale anpassen |

### Signal-Flow (Neu)
```
User klickt Checkbox
  -> BG3ModListModel.mod_toggled(row, enabled)
  -> BG3ModListView.mod_activated(uuid) / mod_deactivated(uuid)
  -> MainWindow._on_bg3_mod_activated(uuid) / _on_bg3_mod_deactivated(uuid)
  -> BG3ModInstaller.activate_mod(uuid) / deactivate_mod(uuid)
  -> _write_state() + _write_modsettings()  [AUTO-DEPLOY]
  -> _bg3_reload_mod_list()
  -> ProfileBar.update_active_count(active, total)
```

### Aenderungsplan Detail

#### 1. bg3_mod_installer.py
- `get_mod_list()`: Gibt statt `active`+`inactive` eine einzige `mods`-Liste zurueck. Jeder Mod hat `enabled: true/false`.
- `activate_mod()` + `deactivate_mod()`: Nach `_write_state()` automatisch `_write_modsettings()` aufrufen (Auto-Deploy).
- `_migrate_state()`: Neue .pak-Dateien die nicht in `mod_order` sind, dort hinzufuegen.
- Fix: Bestehende bg3_modstate.json mit fehlenden UUIDs in mod_order reparieren (21 Mods).

#### 2. bg3_mod_list.py
- Inaktiv-Sektion komplett entfernen (_inactive_model, _inactive_tree, _inactive_label, _inactive_pane).
- Active-Section-Header (_active_label) entfernen.
- Cross-Tree DnD entfernen (nicht mehr noetig).
- Splitter-Proportionen anpassen: Nur noch 2 Panes (Mods + Extras).
- `load_mods()` Signatur aendern: eine `mods`-Liste statt active+inactive.
- Signal `mod_toggled` statt getrennte `mod_activated`/`mod_deactivated`.

#### 3. bg3_mod_list_model.py
- Model immer mit `allow_reorder=True` da es nur noch ein Model gibt.
- Sorting via Header-Klick trotzdem ermoeglichen.

#### 4. mainwindow.py
- `_apply_bg3_instance()`: Deploy-Button + Separator verstecken.
- `_bg3_reload_mod_list()`: Neue Signatur `load_mods(mods, ...)`, Zaehler als "X / Y".
- `_on_bg3_mod_activated/deactivated`: Auto-Deploy ist bereits im Installer, kein _bg3_mark_dirty() mehr.
- `_on_bg3_deploy()`: Bleibt als Fallback, wird aber nicht mehr via Button aufgerufen.
- Context-Menu: Keine aktiv/inaktiv Unterscheidung mehr, Checkbox steuert alles.

### Verwandte Funktionen (geprueft)
- `_bg3_mark_dirty()` / `_bg3_mark_clean()` -> Koennen entfernt oder ignoriert werden, da Auto-Deploy.
- `_on_bg3_archives_dropped()` -> Muss neue `_bg3_reload_mod_list()` nutzen. Kein `_bg3_mark_dirty()` mehr.
- `_on_bg3_mods_reordered()` -> Muss nach Reorder auto-deploy ausfuehren.
- `_on_bg3_context_menu()` -> Kein section=="inactive" Zweig mehr noetig.

## Akzeptanz-Checkliste

- [ ] 1. Wenn User BG3-Instanz laedt, sieht er EINE Mod-Liste ohne Section-Header "Aktive Mods" / "Inaktive Mods"
- [ ] 2. Wenn User die Checkbox eines inaktiven Mods (grauer Kreis) anklickt, wird der Mod sofort aktiv (gruener Haken) UND modsettings.lsx wird sofort aktualisiert
- [ ] 3. Wenn User die Checkbox eines aktiven Mods (gruener Haken) anklickt, wird der Mod sofort inaktiv (grauer Kreis) UND modsettings.lsx wird sofort aktualisiert
- [ ] 4. Wenn User Mods per DnD in der Liste verschiebt, aendert sich die Reihenfolge und modsettings.lsx wird sofort aktualisiert
- [ ] 5. Wenn User BG3-Instanz laedt, ist kein Deploy-Button in der Toolbar sichtbar
- [ ] 6. Wenn User Mods aktiviert/deaktiviert, zeigt der gruene Zaehler oben rechts "X / Y" (X=aktive, Y=gesamt)
- [ ] 7. Wenn User einen neuen Mod per Drag&Drop installiert, erscheint er in der einheitlichen Liste als inaktiv (grauer Kreis)
- [ ] 8. Wenn User Rechtsklick auf einen Mod macht, erscheint Kontextmenu mit Aktivieren/Deaktivieren + Deinstallieren (kein getrenntes active/inactive Menu)
- [ ] 9. Wenn _migrate_state() neue .pak-Dateien findet, werden sie automatisch in mod_order aufgenommen (nicht nur in mods)
- [ ] 10. Wenn bg3_modstate.json geladen wird und UUIDs in mods aber nicht in mod_order sind, werden sie in mod_order ergaenzt
- [ ] 11. Wenn User zwischen BG3 und anderem Game wechselt, bleibt die Standard-Mod-Liste fuer andere Games unveraendert
- [ ] 12. Die Extras-Sektion (Data-Overrides & Frameworks) bleibt unveraendert sichtbar und funktional
- [ ] 13. GustavX (cb555efe-2d9e-131f-8195-a89329d218ea) bleibt hidden und erscheint nicht in der Mod-Liste
- [ ] 14. restart.sh startet ohne Fehler
