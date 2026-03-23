# Claude Review 2 - Issue #57: BG3 Einheitliche Mod-Liste (Architektur)
Datum: 2026-03-23

## Architektur-Pruefung

### Signal-Flow
```
Checkbox -> BG3ModListModel.mod_toggled(row, enabled)
         -> BG3ModListView._on_mod_toggled(row, enabled)
         -> [mod_activated | mod_deactivated](uuid)
         -> MainWindow._on_bg3_mod_[activated|deactivated](uuid)
         -> BG3ModInstaller.[activate_mod|deactivate_mod](uuid)
         -> _write_state() + _write_modsettings()
         -> _bg3_reload_mod_list()
         -> get_mod_list() -> load_mods(unified) + update_active_count(X, Y)
```
Signal-Flow ist korrekt und konsistent.

### MO2-Vergleich
- MO2 hat auch eine einheitliche Liste mit Checkboxen
- Anvil folgt jetzt demselben Prinzip fuer BG3
- Auto-Deploy ist BG3-spezifisch (MO2 hat VFS)

### Architektur-Konformitaet
- Keine hardcoded Pfade
- Keine setStyleSheet() in neuen Widgets
- tr() wird korrekt verwendet
- Keine Aenderungen an base_game.py, mod_deployer.py oder anderen Games
- bg3_mod_handler.py NICHT angefasst (Legacy-Parser)
- Extras-Sektion unveraendert

### Datenfluss
- bg3_modstate.json bleibt Master
- modsettings.lsx wird bei jeder Aenderung sofort geschrieben
- Auto-Repair in _read_state() ist idempotent (schreibt nur einmal)

### Keine Regressionen
- Andere Games: Kein Code geaendert der fuer alle Games gilt
- BG3: Cover-Bilder, Icons, redprelauncher nicht angefasst
- Frameworks/Extras: Unveraendert

## Ergebnis: ACCEPTED
