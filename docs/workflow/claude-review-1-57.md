# Claude Review 1 - Issue #57: BG3 Einheitliche Mod-Liste (Code-Review)
Datum: 2026-03-23

## Geaenderte Dateien

### anvil/widgets/bg3_mod_list.py
- Komplett umgeschrieben: Inaktiv-Sektion, Cross-Tree-DnD, Section-Headers entfernt
- Nur noch ein Model (_mod_model) statt _active_model + _inactive_model
- Splitter: 2 Panes statt 3 (Mods + Extras)
- load_mods() Signatur vereinfacht: mods-Liste statt active+inactive
- _dict_to_row() liest enabled aus dem Dict statt als Parameter
- Unbenutzte Imports bereinigt
- Keine neuen setStyleSheet() Aufrufe

### anvil/models/bg3_mod_list_model.py
- Neue Methode get_active_uuid_order() hinzugefuegt
- Restlicher Code unveraendert

### anvil/core/bg3_mod_installer.py
- activate_mod(): +_write_modsettings() (Auto-Deploy)
- deactivate_mod(): +_write_modsettings() (Auto-Deploy)
- reorder_mods(): +_write_modsettings() (Auto-Deploy)
- get_mod_list(): Gibt unified "mods" Liste zurueck mit "enabled" Flag
- _read_state(): Auto-Repair fuer fehlende UUIDs in mod_order
- _migrate_state(): Neue .pak auch in mod_order einfuegen

### anvil/mainwindow.py
- _apply_bg3_instance(): deploy_sep/deploy_action hidden
- _bg3_reload_mod_list(): Neue API (mods, active_count, total_count)
- _on_bg3_mod_activated/deactivated: Kein _bg3_mark_dirty() mehr
- _on_bg3_mods_reordered: Kein _bg3_mark_dirty() mehr
- _on_bg3_archives_dropped: Kein _bg3_mark_dirty() mehr
- _on_bg3_context_menu: enabled-basiert statt section-basiert

## Potenzielle Probleme
- _bg3_mark_dirty() und _bg3_mark_clean() sind jetzt toter Code -> harmlos, koennte spaeter entfernt werden
- deploy() Methode bleibt erhalten -> kann als Notfall-Fallback dienen

## Ergebnis: ACCEPTED
