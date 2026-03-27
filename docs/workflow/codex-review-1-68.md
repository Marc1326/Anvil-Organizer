# QA-Review 1: Code-Review (Issue #68)
Datum: 2026-03-26
Reviewer: Codex-1

## Geprueft
- `anvil/core/fomod_parser.py` (159 neue Zeilen)
- `anvil/core/mod_deployer.py` (1 Zeile geaendert — Skip-Liste)
- `anvil/dialogs/fomod_dialog.py` (15 neue Zeilen)
- `anvil/mainwindow.py` (49 neue Zeilen)

## Checkliste

### K1: Reinstall mit gespeicherten Choices
- `_ctx_reinstall_mod()` uebergibt `reinstall_mod_path` an `_install_archives()`
- `_install_archives()` laedt via Priority 1 (expliziter Pfad) die Choices
- `FomodDialog` erhaelt `previous_choices` und setzt `_step_selections`
- `_show_step()` nutzt `prev_sels = self._step_selections.get(step_idx, {})`
- ERGEBNIS: Vorherige Auswahl wird vorausgewaehlt
- PASSED

### K2: Speicherung nach Install
- `fomod_config_for_save`, `fomod_selections_for_save`, `fomod_flags_for_save` werden nach Dialog-Accept gesetzt
- Nach `install_from_extracted()` wird `save_fomod_choices()` aufgerufen
- `save_fomod_choices()` schreibt `fomod_choices.json` mit korrekter Struktur
- PASSED

### K3: Erstinstallation ohne gespeicherte Choices
- `load_fomod_choices()` gibt None zurueck wenn Datei nicht existiert
- `FomodDialog(previous_choices=None)` → leeres `_step_selections` dict → Standard-Auswahl
- PASSED

### K4: Ueberschreiben bei neuer Auswahl
- `save_fomod_choices()` ueberschreibt die Datei komplett via `write_text()`
- PASSED

### K5: Fingerprint-Mismatch
- `_build_config_fingerprint()` erfasst Steps, Groups, Plugin-Counts, Namen, Typen
- `load_fomod_choices()` vergleicht Fingerprints und gibt None bei Mismatch
- PASSED

### K6: Cancel aendert nichts
- Bei `dlg.exec() != Accepted` → continue → `save_fomod_choices()` wird nie aufgerufen
- PASSED

### K7: DnD-Duplikat mit Replace
- Priority 2 (FOMOD info name) und Priority 3 (archive stem) finden bestehenden Ordner
- PASSED

### K8: JSON-Struktur
- Unit-Tests verifizieren: fomod_module, timestamp, fingerprint, steps, flags vorhanden
- PASSED

### K9: Multi-Step
- Unit-Tests verifizieren korrekte Speicherung und Wiederherstellung mehrerer Steps
- PASSED

### K10: App-Start
- App startet ohne Fehler
- PASSED

## Potenzielle Probleme geprueft

1. **Shallow Copy von previous_choices**: `dict(previous_choices)` kopiert nur die aeussere Ebene.
   Die inneren Dicts (`{grp_idx: [plugin_indices]}`) sind NICHT kopiert.
   ABER: `_save_current_step()` ueberschreibt die Werte vollstaendig via `_collect_current_selections()`,
   also kein Mutations-Problem im Praxiseinsatz.

2. **`dlg.flags()` wird zweimal aufgerufen**: Einmal fuer `fomod_flags_for_save` und einmal fuer `collect_fomod_files()`.
   Beide Aufrufe geben das gleiche Ergebnis, da `_save_current_step()` idempotent ist.
   Kein Problem.

3. **Deployer**: `fomod_choices.json` wird im Mod-Ordner gespeichert. Der Deployer hat `_SKIP_FILES`
   und `fomod_choices.json` wurde dort hinzugefuegt → wird NICHT deployed. GELOEST.

## Ergebnis
ACCEPTED
