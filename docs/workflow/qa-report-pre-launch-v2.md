# QA Gesamt-Report — Critical Bugfix Pre-Launch Deploy v2

Datum: 2026-03-02
Spec: docs/specs/critical-bugfix-pre-launch-deploy-v2.md
Betroffene Dateien: anvil/mainwindow.py, anvil/widgets/game_panel.py

---

## Agent-Ergebnisse

| Agent | Bereich | Ergebnis | Status |
|-------|---------|----------|--------|
| Agent 1 | Code-Korrektheit game_panel.py | 9/9 | PASS |
| Agent 2 | Code-Korrektheit mainwindow.py | 9/9 | PASS |
| Agent 3 | Signal-Flow + Race Conditions | 8/8 | PASS |
| Agent 4 | Regression + Akzeptanzkriterien | 27/27 (7/7 + 20/20) | PASS |

**Gesamt: 53/53 Punkte erfuellt**

---

## Agent 1 — game_panel.py (9/9)

- [x] 1. `pre_launch_deploy = Signal()` als Klassenattribut (Z.87)
- [x] 2. `self._is_launching = False` in `__init__` (Z.91)
- [x] 3. Guard `if self._is_launching: return` am Anfang (Z.750-751)
- [x] 4. `_is_launching = True` + `setEnabled(False)` (Z.752-753)
- [x] 5. `pre_launch_deploy.emit()` VOR allen 3 Launch-Pfaden (Z.764-765)
- [x] 6. try/finally mit Flag-Reset + Button re-enable (Z.754 / Z.805-807)
- [x] 7. `skip_ba2: bool = False` als keyword-only Parameter (Z.628)
- [x] 8. `if skip_ba2: return` VOR BA2-Cleanup (Z.638-639)
- [x] 9. Restlicher silent_purge Code unveraendert (Z.641-665)

## Agent 2 — mainwindow.py (9/9)

- [x] 1. Signal-Connection mit UniqueConnection (Z.281-284)
- [x] 2. `_pre_launch_deploy()` Methode existiert (Z.1119-1127)
- [x] 3. `_redeploy_timer.stop()` als erste Aktion (Z.1121)
- [x] 4. `silent_purge()` OHNE skip_ba2 (Z.1125)
- [x] 5. `silent_deploy()` voller Deploy (Z.1127)
- [x] 6. `_do_redeploy` mit `skip_ba2=True` (Z.1114)
- [x] 7. `_on_start_game` KEIN Deploy-Code (Z.1229-1241)
- [x] 8. `_on_start_game` KEIN Timer-Stop (Z.1229-1241)
- [x] 9. `_on_start_game` NUR QProcess + Statusbar (Z.1229-1241)

## Agent 3 — Signal-Flow + Race Conditions (8/8)

- [x] 1. Flow Steam: emit (Z.765) -> _pre_launch_deploy (synchron) -> _launch_via_steam (Z.781)
- [x] 2. Flow Proton: emit (Z.765) -> _pre_launch_deploy (synchron) -> _launch_via_proton (Z.783)
- [x] 3. Flow Direkt: emit (Z.765) -> _pre_launch_deploy (synchron) -> start_requested.emit (Z.804)
- [x] 4. Kein Doppel-Deploy: _on_start_game macht NUR QProcess.startDetached
- [x] 5. Guard: _is_launching wird VOR emit gesetzt (Z.752), Check ist erste Aktion (Z.750)
- [x] 6. Timer-Stop bei allen Pfaden: _redeploy_timer.stop() in _pre_launch_deploy (Z.1121)
- [x] 7. UniqueConnection bei connect (Z.281-284)
- [x] 8. finally-Block Timing korrekt: AutoConnection = DirectConnection bei gleichem Thread

## Agent 4 — Regression + Akzeptanzkriterien (27/27)

### Regressions-Check (7/7)

- [x] 1. closeEvent: silent_purge() OHNE skip_ba2 (Z.3128)
- [x] 2. Profil-Wechsel: silent_purge() OHNE skip_ba2 (Z.2272)
- [x] 3. Instanz-Wechsel: silent_purge() OHNE skip_ba2 (Z.829)
- [x] 4. Keine neuen Imports in beiden Dateien
- [x] 5. py_compile game_panel.py — OK
- [x] 6. py_compile mainwindow.py — OK
- [x] 7. Nur 2 Dateien geaendert (git diff --stat)

### Akzeptanzkriterien (20/20)

- [x] 1. GOG/Epic Pre-Launch Deploy
- [x] 2. Steam Pre-Launch Deploy
- [x] 3. Proton Pre-Launch Deploy
- [x] 4. Einmal-Klick: genau 1x PURGE + 1x DEPLOY
- [x] 5. Doppel-Klick: Guard verhindert zweiten Durchlauf
- [x] 6. Button visuell deaktiviert waehrend Deploy
- [x] 7. Mod-Toggle + sofort Starten: Timer gestoppt, voller Deploy
- [x] 8. Steam/Proton: Timer wird gestoppt
- [x] 9. Auto-Redeploy: kein BA2-Cleanup
- [x] 10. Auto-Redeploy: kein BA2-Packing
- [x] 11. Nach Auto-Redeploy: Spielstart mit vollem BA2-Deploy
- [x] 12. Bethesda-Game: BA2-Packing bei Spielstart
- [x] 13. Profil-Wechsel: voller Purge + Deploy
- [x] 14. Instanz-Wechsel: voller Purge + Deploy
- [x] 15. App-Close: voller Purge mit BA2-Cleanup
- [x] 16. UniqueConnection verhindert doppelte Signal-Verbindung
- [x] 17. _on_start_game ohne eigenen Deploy
- [x] 18. py_compile game_panel.py — OK
- [x] 19. py_compile mainwindow.py — OK
- [x] 20. restart.sh startet ohne Fehler

---

## Hinweise (kein Blocker)

- [LOW] Parameter `skip_ba2` ueberspringt auch plugins.txt-Cleanup — beabsichtigt, aber Name koennte langfristig zu `skip_cleanup` umbenannt werden

---

## Ergebnis

# READY FOR COMMIT

Alle 53/53 Pruefpunkte erfuellt. Keine Bugs, keine Regressionen, keine Abweichungen von der Spec.

Einzelberichte:
- docs/workflow/qa-agent1-pre-launch-v2.md
- docs/workflow/qa-agent2-pre-launch-v2.md
- docs/workflow/qa-agent3-pre-launch-v2.md
- docs/workflow/qa-agent4-pre-launch-v2.md
