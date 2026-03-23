# Codex Review 2 - Issue #57: BG3 Einheitliche Mod-Liste (Issue-State)
Datum: 2026-03-23

## Issue-Anforderungen vs. Implementierung

1. "EINE einheitliche Mod-Liste" -> Implementiert: bg3_mod_list.py hat nur noch _mod_model + _mod_tree
2. "Alle Mods mit Checkbox" -> Implementiert: _BG3CheckboxDelegate unveraendert, funktioniert mit unified model
3. "Auto-Deploy" -> Implementiert: activate_mod() + deactivate_mod() + reorder_mods() rufen _write_modsettings()
4. "Auto-Undeploy" -> Implementiert: deactivate_mod() schreibt modsettings.lsx ohne den Mod
5. "Gruener Zaehler X/Y" -> Implementiert: update_active_count(active_count, total_count)
6. "Deploy-Button entfernen" -> Implementiert: deploy_sep/deploy_action auf setVisible(False)
7. "DnD bleibt erhalten" -> Implementiert: _mod_model mit allow_reorder=True
8. "_migrate_state() Fix" -> Implementiert: Neue .pak werden in mod_order aufgenommen
9. "Fehlende UUIDs fixen" -> Implementiert: _read_state() auto-repair + verifiziert (21->0 missing)
10. "Extras bleiben" -> Implementiert: Extras-Sektion Code unveraendert

## Ergebnis: ACCEPTED
