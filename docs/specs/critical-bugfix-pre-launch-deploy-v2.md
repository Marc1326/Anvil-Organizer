# CRITICAL BUGFIX v2: Pre-Launch Deploy, Guard-Flags, skip_ba2

Datum: 2026-03-02
Vorgaenger: docs/specs/critical-bugfix-pre-launch-deploy.md (v1 — Fixes NICHT committed)
Status: SPEC READY — wartet auf GO

---

## Zusammenfassung

Fuenf kritische Bugs verhindern zuverlaessiges Mod-Deployment vor dem Spielstart.
Die v1-Spec identifizierte die Bugs korrekt, wurde per QA validiert (20/20),
aber die Fixes wurden nie committed. Diese v2-Spec konsolidiert alle Erkenntnisse
der Agents 1-3 und liefert eine vollstaendige, implementierbare Loesung.

---

## Bug 1 (KRITISCH): Steam/Proton-Launches umgehen Pre-Launch Deploy

### Root Cause
`_on_start_clicked()` in `game_panel.py` (Zeile 738) hat 3 Launch-Pfade:

| Pfad | Methode | Deploy? |
|------|---------|---------|
| Steam (Haupt-Binary) | `_launch_via_steam()` (Z.764) | NEIN — startet Spiel direkt via `QProcess.startDetached()` |
| Proton (F4SE, REDmod) | `_launch_via_proton()` (Z.767) | NEIN — startet Spiel direkt via `subprocess.Popen()` |
| Direkt (GOG/Epic) | `start_requested.emit()` (Z.788) | JA — MainWindow._on_start_game() macht Purge+Deploy |

**Konsequenz:** Bei Steam- und Proton-Launches werden Mods NICHT deployed.
Das Spiel startet mit dem alten oder gar keinem Mod-Stand.

### Aktueller Code-Pfad (Ist-Zustand)
```
_on_start_clicked()
  |-- is_steam + is_main_binary  -> _launch_via_steam()  -> QProcess.startDetached() -> KEIN DEPLOY
  |-- is_steam + !is_main_binary -> _launch_via_proton() -> subprocess.Popen()       -> KEIN DEPLOY
  +-- !is_steam -> start_requested.emit() -> MainWindow._on_start_game()             -> Purge + Deploy
```

### Fix
Neues Signal `pre_launch_deploy = Signal()` in GamePanel.
Wird VOR jedem Launch-Pfad emittiert.
MainWindow verbindet dieses Signal mit `_pre_launch_deploy()`,
die synchron Purge + vollstaendiges Deploy (inkl. BA2) ausfuehrt.

---

## Bug 2 (KRITISCH): Kein Guard gegen Mehrfach-Klick

### Root Cause
`_on_start_clicked()` hat:
- Kein `_is_launching` Flag
- Kein `_is_deploying` Flag
- Start-Button wird NICHT deaktiviert waehrend Deploy/Launch

Da `silent_deploy()` -> BA2-Packing -> `subprocess.run(timeout=300)` den
Main Thread blockiert, werden Qt-Click-Events gepuffert. Nach dem Block
werden die gepufferten Klicks abgearbeitet -> mehrfaches Deploy + Launch.

### Konsequenz
- Doppelklick = 2x vollstaendiges Deploy + 2x Spielstart
- Bei langem BA2-Packing (>5s): noch mehr gepufferte Klicks moeglich
- 5-6x Purge+Deploy in der Konsole beobachtet

### Fix
1. Guard-Flag `_is_launching = False` in GamePanel.__init__()
2. Start-Button deaktivieren: `self._start_btn.setEnabled(False)` zu Beginn
3. try/finally Block: Flag und Button werden IMMER zurueckgesetzt
4. UniqueConnection bei Signal-Verbindung als Sicherheitsnetz

---

## Bug 3 (KRITISCH): Redeploy-Timer laeuft bei Steam/Proton weiter

### Root Cause
`_on_start_game()` in MainWindow (Z.1217) stoppt den Redeploy-Timer:
```python
self._redeploy_timer.stop()
```
Aber `_on_start_game()` wird NUR beim Direkt-Launch aufgerufen (via `start_requested` Signal).
Bei Steam- und Proton-Launches wird der Timer NICHT gestoppt.

### Konsequenz
Wenn der User kurz vor dem Spielstart eine Mod toggled (was den 500ms Debounce-Timer startet),
kann der Timer WAEHREND des Spiels feuern. `_do_redeploy()` ruft dann `silent_purge()` auf,
was Symlinks loescht -> Mods verschwinden waehrend das Spiel laeuft.

### Fix
Timer-Stop in `_pre_launch_deploy()` (neue Methode), die bei JEDEM Launch-Pfad aufgerufen wird.

---

## Bug 4 (HOCH): silent_purge() loescht IMMER BA2-Archive

### Root Cause
`silent_purge()` (Z.626) hat keinen `skip_ba2` Parameter:
```python
def silent_purge(self) -> None:
    if self._deployer:
        self._deployer.purge()
    # BA2-Cleanup — IMMER
    needs_ba2 = getattr(self._current_plugin, "NeedsBa2Packing", False)
    if needs_ba2 ...:
        packer.cleanup_ba2s()   # <- Loescht alle BA2-Archive
        packer.restore_ini()    # <- Stellt Original-INI wieder her
```

`_do_redeploy()` (Z.1104) ruft `silent_purge()` auf, gefolgt von
`silent_deploy_fast()` — welches KEIN BA2-Packing macht.

### Konsequenz
Bei jedem Mod-Toggle (Checkbox an/aus) oder Drag&Drop-Reorder:
1. `_schedule_redeploy()` -> 500ms Timer
2. `_do_redeploy()` -> `silent_purge()` -> BA2-Archive GELOESCHT
3. `silent_deploy_fast()` -> Symlinks erstellt, aber KEINE neuen BA2
4. Ergebnis: Alle BA2-gepackten Texturen/Meshes VERSCHWUNDEN

### Fix
`skip_ba2` Parameter fuer `silent_purge()`:
```python
def silent_purge(self, *, skip_ba2: bool = False) -> None:
```
`_do_redeploy()` ruft dann `silent_purge(skip_ba2=True)` auf.
Alle anderen Aufrufe bleiben OHNE `skip_ba2` -> voller Cleanup.

---

## Bug 5 (HOCH): BA2-Packing blockiert Main Thread

### Root Cause
`ba2_packer.py` Z.279:
```python
proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
```
Dies blockiert den Main Thread fuer die gesamte Dauer des BA2-Packing-Prozesses.

### Konsequenz
- UI friert ein waehrend BA2-Packing laeuft
- Qt puffert alle Maus-/Tastatur-Events
- Gepufferte Button-Klicks werden NACH dem Block abgearbeitet
- Ohne Guard-Flag (Bug 2) -> zweiter Deploy-Zyklus startet sofort

### Fix (Kurzfristig)
Bug 5 wird durch den Guard-Flag aus Bug 2 ENTSCHAERFT: Selbst wenn Events
gepuffert werden, verhindert `_is_launching = True` einen zweiten Aufruf.

### Fix (Langfristig, NICHT Teil dieser Spec)
BA2-Packing in QThread oder QProcess auslagern. Separate Spec.

---

## Betroffene Dateien

| Datei | Zeilen | Aenderung |
|-------|--------|-----------|
| `anvil/widgets/game_panel.py` | Z.84-86 | Neues Signal `pre_launch_deploy = Signal()` |
| `anvil/widgets/game_panel.py` | Z.88 (__init__) | `self._is_launching = False` initialisieren |
| `anvil/widgets/game_panel.py` | Z.626 | `skip_ba2` Parameter fuer `silent_purge()` |
| `anvil/widgets/game_panel.py` | Z.738-788 | Guard-Flag, Button-Disable, emit pre_launch_deploy |
| `anvil/mainwindow.py` | Z.280 | Signal-Connection fuer `pre_launch_deploy` |
| `anvil/mainwindow.py` | Z.1104-1112 | `_do_redeploy()`: `silent_purge(skip_ba2=True)` |
| `anvil/mainwindow.py` | nach Z.1113 | Neue Methode `_pre_launch_deploy()` |
| `anvil/mainwindow.py` | Z.1215-1234 | `_on_start_game()` vereinfachen (Deploy entfernen) |

---

## Loesung im Detail

### Schritt 1: Signal + Guard in GamePanel

```python
# game_panel.py — Klasse GamePanel (Z.84-86)
class GamePanel(QWidget):
    install_requested = Signal(list)
    start_requested = Signal(str, str)
    pre_launch_deploy = Signal()       # NEU

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_launching = False     # NEU
        # ... rest ...
```

### Schritt 2: _on_start_clicked mit Guard + pre_launch_deploy

```python
# game_panel.py — _on_start_clicked (Z.738)
def _on_start_clicked(self) -> None:
    """Start the currently selected executable."""
    if self._is_launching:
        return
    self._is_launching = True
    self._start_btn.setEnabled(False)
    try:
        idx = self._selected_exe_index
        if idx < 0 or idx >= len(self._executables):
            return

        exe = self._executables[idx]
        binary = exe.get("binary", "")
        if not binary:
            return

        # Pre-launch deploy fuer ALLE Pfade
        self.pre_launch_deploy.emit()

        plugin = self._current_plugin
        is_steam = (
            plugin
            and hasattr(plugin, "GameSteamId")
            and plugin.GameSteamId
            and hasattr(plugin, "detectedStore")
            and plugin.detectedStore() == "steam"
        )

        if is_steam:
            is_main_binary = (
                hasattr(plugin, "GameBinary") and binary == plugin.GameBinary
            )
            if is_main_binary:
                self._launch_via_steam(plugin)
            else:
                self._launch_via_proton(plugin, binary)
            return

        # Non-Steam: direct start (GOG, Epic, etc.)
        game_path = self._current_game_path
        if game_path is None:
            QMessageBox.warning(
                self, tr("game_panel.start"),
                tr("game_panel.game_dir_not_found"),
            )
            return

        binary_path = game_path / binary
        if not binary_path.exists():
            QMessageBox.warning(
                self, tr("game_panel.start"),
                tr("game_panel.exe_not_found", path=str(binary_path)),
            )
            return

        working_dir = str(binary_path.parent)
        self.start_requested.emit(str(binary_path), working_dir)
    finally:
        self._is_launching = False
        self._start_btn.setEnabled(True)
```

### Schritt 3: skip_ba2 in silent_purge

```python
# game_panel.py — silent_purge (Z.626)
def silent_purge(self, *, skip_ba2: bool = False) -> None:
    """Purge deployed mods silently.

    Args:
        skip_ba2: If True, skip BA2 cleanup (used for quick redeploy
                  after mod toggle where BA2 should remain intact).
    """
    if self._deployer:
        self._deployer.purge()

    if skip_ba2:
        return  # BA2-Cleanup und plugins.txt ueberspringen

    # BA2-Cleanup for Bethesda games (wie bisher)
    # ... bestehender Code ...

    # Remove plugins.txt for Bethesda games (wie bisher)
    # ... bestehender Code ...
```

### Schritt 4: Signal-Connection in MainWindow

```python
# mainwindow.py — __init__ (nach Z.280)
self._game_panel.start_requested.connect(self._on_start_game)
self._game_panel.pre_launch_deploy.connect(
    self._pre_launch_deploy,
    Qt.ConnectionType.UniqueConnection,
)
```

### Schritt 5: _pre_launch_deploy in MainWindow

```python
# mainwindow.py — neue Methode (nach _do_redeploy, ca. Z.1114)
def _pre_launch_deploy(self) -> None:
    """Full purge + deploy (with BA2) before any game launch."""
    self._redeploy_timer.stop()
    if not self._current_instance_path:
        return
    print("[PURGE] Pre-launch purge", flush=True)
    self._game_panel.silent_purge()
    print("[DEPLOY] Pre-launch full deploy (with BA2)", flush=True)
    self._game_panel.silent_deploy()
```

### Schritt 6: _do_redeploy mit skip_ba2

```python
# mainwindow.py — _do_redeploy (Z.1104)
def _do_redeploy(self) -> None:
    self._redeploy_timer.stop()
    if not self._current_instance_path:
        return
    print("[PURGE] Auto-redeploy: purging current deployment", flush=True)
    self._game_panel.silent_purge(skip_ba2=True)    # <- NEU: skip_ba2
    print("[DEPLOY] Auto-redeploy: deploying mods (fast, no BA2)", flush=True)
    self._game_panel.silent_deploy_fast()
    self.statusBar().showMessage(tr("status.deployed"), 3000)
```

### Schritt 7: _on_start_game vereinfachen

```python
# mainwindow.py — _on_start_game (Z.1215)
def _on_start_game(self, binary_path: str, working_dir: str) -> None:
    """Launch the selected game executable (deploy already done via pre_launch_deploy)."""
    from PySide6.QtCore import QProcess
    success, pid = QProcess.startDetached(binary_path, [], working_dir)
    if success:
        self.statusBar().showMessage(
            tr("status.started", name=Path(binary_path).name), 5000,
        )
    else:
        QMessageBox.warning(
            self, tr("error.start_failed_title"),
            tr("error.start_failed_message", path=binary_path),
        )
```

---

## Signal-Flow NACHHER (Soll-Zustand)

### Flow 1: Steam-Launch (Haupt-Binary)
```
User klickt "Starten"
  -> _on_start_clicked()
    -> _is_launching = True, Button disabled
    -> pre_launch_deploy.emit()
      -> MainWindow._pre_launch_deploy()  [synchron, DirectConnection]
        -> _redeploy_timer.stop()
        -> silent_purge()  [OHNE skip_ba2 -> voller BA2-Cleanup]
        -> silent_deploy() [MIT BA2-Packing]
    -> _launch_via_steam(plugin)
      -> QProcess.startDetached("steam", ["-applaunch", steam_id])
    -> finally: _is_launching = False, Button enabled
```

### Flow 2: Proton-Launch (F4SE, REDmod etc.)
```
User klickt "Starten"
  -> _on_start_clicked()
    -> _is_launching = True, Button disabled
    -> pre_launch_deploy.emit()
      -> MainWindow._pre_launch_deploy()  [synchron]
        -> _redeploy_timer.stop()
        -> silent_purge()
        -> silent_deploy()
    -> _launch_via_proton(plugin, binary)
      -> subprocess.Popen(["proton", "run", exe])
    -> finally: _is_launching = False, Button enabled
```

### Flow 3: Direkt-Launch (GOG/Epic)
```
User klickt "Starten"
  -> _on_start_clicked()
    -> _is_launching = True, Button disabled
    -> pre_launch_deploy.emit()
      -> MainWindow._pre_launch_deploy()  [synchron]
        -> _redeploy_timer.stop()
        -> silent_purge()
        -> silent_deploy()
    -> start_requested.emit(binary_path, working_dir)
      -> MainWindow._on_start_game()
        -> QProcess.startDetached(binary_path)
    -> finally: _is_launching = False, Button enabled
```

### Flow 4: Auto-Redeploy (Mod-Toggle/Reorder)
```
User toggled Mod-Checkbox
  -> _on_mod_toggled()
    -> _schedule_redeploy()
      -> _redeploy_timer.start(500ms)
  -> [500ms spaeter]
  -> _do_redeploy()
    -> _redeploy_timer.stop()
    -> silent_purge(skip_ba2=True)  [NUR Symlinks, BA2 bleibt]
    -> silent_deploy_fast()         [OHNE BA2-Packing]
```

### Flow 5: App-Close
```
User schliesst App
  -> closeEvent()
    -> _redeploy_timer.stop()
    -> silent_purge()  [OHNE skip_ba2 -> voller BA2-Cleanup]
    -> _save_ui_state()
```

---

## Abhaengigkeiten

| Komponente | Abhaengigkeit |
|------------|---------------|
| `pre_launch_deploy` Signal | PySide6.QtCore.Signal — bereits importiert |
| `Qt.ConnectionType.UniqueConnection` | PySide6.QtCore.Qt — bereits importiert |
| `skip_ba2` Parameter | Reine Python-Logik, keine externen Abhaengigkeiten |
| Guard-Flag | Reine Python-Logik |

**Keine neuen Imports erforderlich.**

---

## Risiken

| Risiko | Wahrscheinlichkeit | Auswirkung | Mitigation |
|--------|-------------------|------------|------------|
| BA2-Packing blockiert UI bei Pre-Launch | Hoch | UI friert ein (aber nur 1x, nicht 5-6x) | Guard verhindert Mehrfach-Aufruf; Langfristig: QThread |
| `start_requested` Signal wird doppelt verarbeitet | Niedrig | Doppelter Game-Start | UniqueConnection + Guard |
| `skip_ba2` vergessen bei neuem Aufruf | Niedrig | BA2 wird geloescht bei Auto-Redeploy | Default ist `False` -> sicher |
| finally-Block: Button re-enabled bevor Launch fertig | Niedrig | User kann sofort erneut klicken | Launch ist async, Button-Re-Enable ist gewollt |

---

## Akzeptanz-Kriterien (ALLE muessen erfuellt sein)

### Launch-Pfade (3 Pfade, 3 Kriterien)
- [ ] 1. Wenn User bei einem GOG/Epic-Spiel auf "Starten" klickt, erscheint in der Konsole "[PURGE] Pre-launch purge" gefolgt von "[DEPLOY] Pre-launch full deploy (with BA2)" BEVOR das Spiel startet
- [ ] 2. Wenn User bei einem Steam-Spiel (Haupt-Binary) auf "Starten" klickt, erscheint in der Konsole "[PURGE] Pre-launch purge" gefolgt von "[DEPLOY] Pre-launch full deploy (with BA2)" BEVOR "steam -applaunch" ausgefuehrt wird
- [ ] 3. Wenn User bei einem Steam-Spiel einen nicht-primaeren Launcher (z.B. F4SE) auf "Starten" klickt, erscheint in der Konsole "[PURGE] Pre-launch purge" gefolgt von "[DEPLOY] Pre-launch full deploy (with BA2)" BEVOR "proton run" ausgefuehrt wird

### Mehrfach-Klick-Schutz (3 Kriterien)
- [ ] 4. Wenn User einmal auf "Starten" klickt, erscheint genau 1x "[PURGE] Pre-launch purge" und genau 1x "[DEPLOY] Pre-launch full deploy" in der Konsole
- [ ] 5. Wenn User schnell doppelt auf "Starten" klickt, erscheint trotzdem nur 1x "[PURGE]" und 1x "[DEPLOY]" in der Konsole
- [ ] 6. Wenn User auf "Starten" klickt, ist der Start-Button visuell deaktiviert (ausgegraut) waehrend Deploy laeuft, und wird nach Abschluss wieder aktiviert

### Redeploy-Timer-Sicherheit (2 Kriterien)
- [ ] 7. Wenn User eine Mod toggled (500ms Debounce-Timer startet) und dann sofort "Starten" klickt, wird der Timer gestoppt und der volle Pre-Launch-Deploy ausgefuehrt — KEIN Auto-Redeploy feuert nach dem Spielstart
- [ ] 8. Wenn User ein Steam/Proton-Spiel startet, wird der Redeploy-Timer gestoppt (verifizierbar: kein "[PURGE] Auto-redeploy" nach dem Start in der Konsole)

### skip_ba2 bei Auto-Redeploy (3 Kriterien)
- [ ] 9. Wenn User eine Mod-Checkbox toggled, zeigt die Konsole "[PURGE] Auto-redeploy: purging current deployment" OHNE nachfolgendes "[BA2] INI restored" oder "[BA2] Cleaned up"
- [ ] 10. Wenn User eine Mod per Drag&Drop verschiebt, zeigt die Konsole "[DEPLOY] Auto-redeploy: deploying mods (fast, no BA2)" — KEIN BA2-Packing
- [ ] 11. Wenn User nach einem Auto-Redeploy (Mod-Toggle) das Spiel startet, zeigt die Konsole beim Start-Klick "[DEPLOY] Pre-launch full deploy (with BA2)" mit BA2-Packing — die BA2-Archive werden korrekt neu erstellt

### Regression: Voller Deploy (4 Kriterien)
- [ ] 12. Wenn User das Spiel startet und das Spiel BA2-Packing benoetigt (Bethesda-Game), erscheint "[BA2] Running:" und "[BA2] Created:" in der Konsole
- [ ] 13. Wenn User das Profil wechselt, wird voller Purge (mit BA2-Cleanup) + Deploy (mit BA2-Packing) ausgefuehrt
- [ ] 14. Wenn User die Instanz wechselt, wird voller Purge der alten + Deploy der neuen Instanz ausgefuehrt (mit BA2)
- [ ] 15. Wenn User die App schliesst, wird voller Purge (mit BA2-Cleanup) ausgefuehrt — "[BA2] INI restored" erscheint in der Konsole

### Signal-Integritaet (2 Kriterien)
- [ ] 16. Wenn `pre_launch_deploy` Signal mehrfach connected wird (z.B. durch Bug), verhindert UniqueConnection doppelte Ausfuehrung — nur 1x Deploy pro Emit
- [ ] 17. Wenn `_on_start_game()` nach dem Refactor aufgerufen wird, fuehrt es KEINEN eigenen Deploy mehr aus (kein doppelter Deploy bei Direkt-Launch)

### Code-Qualitaet (3 Kriterien)
- [ ] 18. `python -m py_compile anvil/widgets/game_panel.py` laeuft ohne Fehler
- [ ] 19. `python -m py_compile anvil/mainwindow.py` laeuft ohne Fehler
- [ ] 20. `./restart.sh` startet ohne Fehler/Tracebacks (bekannte QTabBar alignment Warnings sind OK)
