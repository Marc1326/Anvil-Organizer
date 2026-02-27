# Deploy-Bug Fix — Mods werden nicht in den Game-Ordner verlinkt

## Kontext

Anvil Organizer ist ein nativer Linux Mod Manager (Python/PySide6/Qt).

Aktuell werden Mods nach der Installation NICHT als Symlinks in den Game-Ordner deployed. Das Spiel lädt daher keine Mods.

## Workflow-Agent aufrufen

Nutze den **Workflow-Agent** (`.claude/agents/workflow.md`) für die Umsetzung — kompletter Zyklus: Planung → Implementierung → QA → Loop bis fertig.

## Bug-Analyse

### Symptom
- Mods sind in `.mods/` installiert (8 Stück für Fallout 4)
- Beim Starten des Spiels werden KEINE Symlinks in `<GameDir>/Data/` erstellt
- Kein `.deploy_manifest.json` → Deploy wird nie erfolgreich ausgeführt

### Root Cause

**Der `ModDeployer` bekommt den falschen Profilnamen.**

In `game_panel.py` → `set_instance_path()` wird `ModDeployer` ohne `profile_name` erstellt → Default-Wert `"Default"` wird verwendet. In `_apply_instance()` (mainwindow.py) ist der aktive Profilname als lokale Variable `profile_name` vorhanden, wird aber NICHT an `set_instance_path()` weitergegeben.

Der Deployer liest dann `active_mods.json` aus `.profiles/Default/` statt aus dem richtigen Profil → findet keine aktiven Mods → erstellt keine Symlinks.

Zusätzlich: Beim Profilwechsel (`_on_profile_changed()`) wird kein Redeploy ausgelöst.

### Betroffene Dateien & konkrete Fixes

**1. `anvil/widgets/game_panel.py` — `set_instance_path()`**
- Parameter `profile_name: str = "Default"` hinzufügen
- `profile_name` an `ModDeployer()` weitergeben
- `self._current_profile_name` als Instanzvariable speichern (für `update_game()`)

**2. `anvil/widgets/game_panel.py` — `update_game()`**
- Dort wird ebenfalls ein `ModDeployer` erstellt (Zeile `if self._instance_path and game_path:`)
- Muss `self._current_profile_name` verwenden statt den Default

**3. `anvil/widgets/game_panel.py` — `__init__()`**
- `self._current_profile_name: str = "Default"` initialisieren

**4. `anvil/mainwindow.py` — `_apply_instance()`**
- Zeile `self._game_panel.set_instance_path(instance_path)` ändern zu:
  `self._game_panel.set_instance_path(instance_path, profile_name=profile_name)`
- Die Variable `profile_name` existiert bereits als lokale Variable in der Methode

**5. `anvil/mainwindow.py` — `_on_profile_changed()`**
- Am Ende der Methode (nach Schritt 5) Redeploy hinzufügen:
  ```python
  # 6. Redeploy with new profile
  self._game_panel.silent_purge()
  self._game_panel.set_instance_path(self._current_instance_path, profile_name=name)
  self._game_panel.silent_deploy()
  ```

**6. `anvil/core/mod_deployer.py` — `deploy()`**
- Logging hinzufügen (print mit flush=True):
  - Welches Profil: `f"[DEPLOY] Profile: {self._profile_path}"`
  - Enabled Mods: `f"[DEPLOY] Enabled mods: {len(enabled_mods)}"`
  - Data path: `f"[DEPLOY] Data path: {self._data_path or '(root)'}"`
  - Am Ende: `f"[DEPLOY] Result: {result.links_created} symlinks, {result.files_copied} copies, {len(result.errors)} errors"`

**7. `anvil/mainwindow.py` — `_apply_bg3_instance()`**
- Auch dort wird `set_instance_path()` aufgerufen — prüfen ob `profile_name` nötig ist
  (BG3 nutzt kein Symlink-Deploy, daher wahrscheinlich unkritisch, aber konsistent halten)

### Aufrufkette nach Fix

```
_apply_instance()
  → game_panel.update_game(...)
  → game_panel.set_instance_path(instance_path, profile_name=profile_name)
    → self._current_profile_name = profile_name
    → ModDeployer(..., profile_name=profile_name)
  → game_panel.silent_deploy()
    → deployer.deploy()
      → read_active_mods(.profiles/<richtiges_profil>/)
      → Symlinks erstellen ✅

_on_profile_changed(name)
  → ... (bestehende Logik: Checkboxen, Collapsed State) ...
  → game_panel.silent_purge()
  → game_panel.set_instance_path(instance_path, profile_name=name)
  → game_panel.silent_deploy()
```

## Wichtige Regeln

- **KEINE Änderungen an Game-Plugins** (`anvil/plugins/`) — die sind tabu
- **KEINE Änderungen an Cover-Bildern, REDmod, redprelauncher**
- **Erst DIFF zeigen, dann auf "GO" warten**
- Code nur über Claude Code ändern, MCP-Tools nur zum Lesen
- Commit-Message auf Englisch: `fix: pass active profile to ModDeployer for correct symlink deployment`

## Test-Validierung

Nach dem Fix sollte Marc folgendes prüfen können:
```bash
# Anvil starten, Fallout 4 Instanz laden
# Terminal-Output sollte Deploy-Log zeigen:
# [DEPLOY] Profile: .../.profiles/Default
# [DEPLOY] Enabled mods: 8
# [DEPLOY] Result: X symlinks, 0 copies, 0 errors

# Symlinks prüfen:
ls -la "/mnt/gamingS/SteamLibrary/steamapps/common/Fallout 4/Data/" | grep "^l"
# → Symlinks zu .mods/ Dateien sollten sichtbar sein

# Manifest prüfen:
cat "/home/mob/.anvil-organizer/instances/Fallout 4/.deploy_manifest.json" | head -20
# → Manifest mit symlinks-Array sollte existieren
```
