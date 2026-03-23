# Codex Review 1 - Issue #57: BG3 Einheitliche Mod-Liste
Datum: 2026-03-23

## Geprueft gegen Checkliste

1. EINE Mod-Liste ohne Section-Header: PASS - Inaktiv-Sektion + aktiv/inaktiv Labels komplett entfernt
2. Checkbox aktivieren -> Auto-Deploy: PASS - activate_mod() ruft _write_modsettings() auf
3. Checkbox deaktivieren -> Auto-Undeploy: PASS - deactivate_mod() ruft _write_modsettings() auf
4. DnD Reorder + Auto-Deploy: PASS - reorder_mods() ruft _write_modsettings() auf
5. Kein Deploy-Button: PASS - deploy_sep/deploy_action auf setVisible(False) in _apply_bg3_instance()
6. Zaehler X/Y: PASS - update_active_count(active_count, total_count) mit 2 Parametern
7. Neu installierter Mod als inaktiv: PASS - _register_pak_files schreibt mod_order NICHT -> nicht in active -> enabled=False
8. Kontextmenu: PASS - Nutzt mod_data["enabled"] statt section fuer activate/deactivate
9. _migrate_state Fix: PASS - Neue .pak -> mods UND mod_order
10. Auto-Repair fehlende UUIDs: PASS - _read_state() prueft und ergaenzt
11. Andere Games: PASS - Nur BG3-Dateien geaendert
12. Extras-Sektion: PASS - Unveraendert
13. GustavX hidden: PASS - _HIDDEN_UUIDS bleibt
14. restart.sh: PASS - App startet ohne Tracebacks

## Code-Qualitaet
- Unbenutzte Imports bereinigt (QHBoxLayout, QModelIndex, ROLE_UUID)
- Signal-Flow klar: Checkbox -> mod_toggled -> mod_activated/deactivated -> activate_mod/deactivate_mod -> write_state + write_modsettings
- Keine hardcoded Pfade
- Kein setStyleSheet() in neuen Widgets

## Ergebnis: ACCEPTED
