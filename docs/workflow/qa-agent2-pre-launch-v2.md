# QA Agent 2 — Code-Korrektheit mainwindow.py
Datum: 2026-03-02

## Checkliste

- [x] 1. Signal-Connection `pre_launch_deploy.connect(_pre_launch_deploy, UniqueConnection)` existiert ✅
  - Zeile 281-284:
    ```python
    self._game_panel.pre_launch_deploy.connect(
        self._pre_launch_deploy,
        Qt.ConnectionType.UniqueConnection,
    )
    ```

- [x] 2. `_pre_launch_deploy()` existiert als neue Methode in MainWindow ✅
  - Zeile 1119-1127:
    ```python
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

- [x] 3. `_pre_launch_deploy`: `_redeploy_timer.stop()` als erste Aktion ✅
  - Zeile 1121: `self._redeploy_timer.stop()` — ist die erste Anweisung im Methodenkoerper (nach Docstring).

- [x] 4. `_pre_launch_deploy`: `silent_purge()` OHNE `skip_ba2` (voller Cleanup) ✅
  - Zeile 1125: `self._game_panel.silent_purge()` — kein `skip_ba2` Parameter, also Default `False` = voller Cleanup inkl. BA2.

- [x] 5. `_pre_launch_deploy`: `silent_deploy()` (voller Deploy mit BA2) ✅
  - Zeile 1127: `self._game_panel.silent_deploy()` — voller Deploy (nicht `silent_deploy_fast()`).

- [x] 6. `_do_redeploy`: `silent_purge(skip_ba2=True)` — `skip_ba2` wird uebergeben ✅
  - Zeile 1114: `self._game_panel.silent_purge(skip_ba2=True)` — korrekt, BA2-Archive bleiben bei Auto-Redeploy erhalten.

- [x] 7. `_on_start_game`: KEIN Deploy-Code mehr (kein `silent_purge`, kein `silent_deploy`) ✅
  - Zeile 1229-1241: Methode enthaelt ausschliesslich `QProcess.startDetached()`, Statusbar-Message und Error-Handling. Kein `silent_purge()`, kein `silent_deploy()` vorhanden.

- [x] 8. `_on_start_game`: KEIN `_redeploy_timer.stop()` mehr ✅
  - Zeile 1229-1241: Kein `_redeploy_timer` Zugriff in der Methode. Timer-Stop erfolgt jetzt in `_pre_launch_deploy()`.

- [x] 9. `_on_start_game`: NUR noch `QProcess.startDetached` + Statusbar (ggf. Error-Message) ✅
  - Zeile 1229-1241:
    ```python
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
  - Nur QProcess.startDetached + Statusbar + QMessageBox.warning bei Fehler. Exakt wie in der Spec.

## Ergebnis: 9/9 Punkte erfuellt

Alle Checklistenpunkte fuer `mainwindow.py` sind korrekt implementiert.
Die Implementierung entspricht 1:1 der Spec `critical-bugfix-pre-launch-deploy-v2.md`.

**READY FOR COMMIT** (bezogen auf mainwindow.py)
