# Feature: Deploy-Bug Fix -- Mods werden nicht in den Game-Ordner verlinkt
Datum: 2026-02-26

## Analyse

### Root Cause
`ModDeployer` bekommt den falschen Profilnamen ("Default" statt des aktiven Profils).
In `game_panel.py` wird `ModDeployer()` ohne `profile_name` erstellt.
In `mainwindow.py` -> `_apply_instance()` ist der aktive Profilname als lokale Variable vorhanden, wird aber NICHT weitergegeben.

### Betroffene Dateien
1. `anvil/widgets/game_panel.py` -- `__init__()`, `set_instance_path()`, `update_game()`
2. `anvil/mainwindow.py` -- `_apply_instance()`, `_on_profile_changed()`, `_apply_bg3_instance()`
3. `anvil/core/mod_deployer.py` -- `deploy()`

### Aenderungen im Detail

**game_panel.py:**
- `__init__()`: `self._current_profile_name: str = "Default"` hinzufuegen
- `set_instance_path()`: Parameter `profile_name: str = "Default"` hinzufuegen, an ModDeployer weitergeben, als Instanzvariable speichern
- `update_game()`: Bei Re-Init des Deployers `self._current_profile_name` verwenden

**mainwindow.py:**
- `_apply_instance()` Zeile 953: `profile_name` an `set_instance_path()` weitergeben
- `_on_profile_changed()`: Am Ende Redeploy mit neuem Profil ausfuehren (silent_purge + set_instance_path + silent_deploy)
- `_apply_bg3_instance()` Zeile 3120: `profile_name` weitergeben (Konsistenz)

**mod_deployer.py:**
- `deploy()`: Logging-Zeilen mit print(flush=True) hinzufuegen

---

## Akzeptanz-Kriterien (ALLE muessen erfuellt sein)

- [ ] K1: Wenn `_apply_instance()` aufgerufen wird, erhaelt `set_instance_path()` den aktiven Profilnamen (nicht "Default") als Parameter
- [ ] K2: Wenn `set_instance_path(path, profile_name="MyProfile")` aufgerufen wird, erstellt der ModDeployer mit `profile_name="MyProfile"` und `self._current_profile_name` wird auf "MyProfile" gesetzt
- [ ] K3: Wenn `update_game()` den Deployer re-initialisiert, verwendet er `self._current_profile_name` statt den Default-Wert "Default"
- [ ] K4: Wenn ein Profil gewechselt wird (`_on_profile_changed()`), fuehrt die App silent_purge + set_instance_path(neues Profil) + silent_deploy aus
- [ ] K5: Wenn `deploy()` ausgefuehrt wird, gibt es im Log "[DEPLOY] Profile: ..." mit dem korrekten Profil-Pfad
- [ ] K6: Wenn `deploy()` ausgefuehrt wird, gibt es im Log "[DEPLOY] Enabled mods: N" mit der Anzahl aktivierter Mods
- [ ] K7: Wenn `deploy()` ausgefuehrt wird, gibt es im Log "[DEPLOY] Data path: ..." und "[DEPLOY] Result: X symlinks, Y copies, Z errors"
- [ ] K8: Wenn `_apply_bg3_instance()` aufgerufen wird, wird `profile_name` an `set_instance_path()` uebergeben (Konsistenz)
- [ ] K9: Wenn `GamePanel.__init__()` aufgerufen wird, existiert `self._current_profile_name` mit Default-Wert "Default"
- [ ] K10: `python -m py_compile` fuer alle geaenderten Dateien laeuft fehlerfrei
- [ ] K11: `./restart.sh` startet ohne Fehler (Tracebacks, NameError, ImportError, AttributeError)
