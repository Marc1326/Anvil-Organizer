# QA-Report: Critical Bugfix Pre-Launch Deploy (Iteration 1)

## Checklisten-Pruefung

### Launch funktioniert (alle 3 Pfade)
- [x] 1. Direkt-Launch (GOG/Epic): pre_launch_deploy.emit() wird VOR start_requested.emit() aufgerufen (Zeile 772 vor Zeile 804) -- Reihenfolge korrekt
- [x] 2. Steam-Launch: pre_launch_deploy.emit() wird VOR _launch_via_steam() aufgerufen (Zeile 772 vor Zeile 780) -- Reihenfolge korrekt
- [x] 3. Proton-Launch: pre_launch_deploy.emit() wird VOR _launch_via_proton() aufgerufen (Zeile 772 vor Zeile 783) -- Reihenfolge korrekt

### Kein Mehrfach-Deploy
- [x] 4. Guard-Flag _is_launching=True (Zeile 750) verhindert Re-Entry; emit() bei Zeile 772 -- nur 1x "[PURGE]"
- [x] 5. Gleicher Guard -- nur 1x "[DEPLOY]"
- [x] 6. Doppelklick: zweiter Aufruf trifft auf _is_launching=True (Zeile 748) und returnt sofort; Button ist zusaetzlich disabled (Zeile 751)

### Deploy synchron vor Launch
- [x] 7. pre_launch_deploy.emit() (Zeile 772) ist DirectConnection (Default fuer gleichen Thread) via UniqueConnection -- _pre_launch_deploy laeuft synchron durch BEVOR Launch-Code folgt
- [x] 8. _pre_launch_deploy() macht silent_purge() + silent_deploy() synchron -- BA2-Packing ist VOR Return abgeschlossen

### Kein Crash
- [x] 9. Guard-Flag verhindert Mehrfach-Aufruf -> kein Stau von BA2-Packing-Operationen -> kein Thread-Blocking
- [x] 10. Nur noch 1x Deploy pro Klick statt 5-6x -> Main Thread wird nicht ueberlastet

### skip_ba2 bei Mod-Toggle
- [x] 11. _do_redeploy() ruft silent_purge(skip_ba2=True) auf (Zeile 1100) -- BA2-Cleanup wird uebersprungen
- [x] 12. Drag&Drop triggert _on_mods_reordered -> _schedule_redeploy -> _do_redeploy mit skip_ba2=True
- [x] 13. _do_redeploy() druckt "[DEPLOY] Auto-redeploy: deploying mods (fast, no BA2)" (Zeile 1101-1102)

### Regression: Voller Deploy weiterhin korrekt
- [x] 14. _pre_launch_deploy() ruft silent_purge() OHNE skip_ba2 auf (Zeile 1210) -> BA2 wird gepackt
- [x] 15. Profil-Wechsel: _on_profile_activated() ruft silent_purge() OHNE skip_ba2 (Zeile 2257) + silent_deploy() (Zeile 2259)
- [x] 16. Instanz-Wechsel: _apply_instance() ruft silent_purge() OHNE skip_ba2 (Zeile 815)
- [x] 17. App-Close: closeEvent() ruft silent_purge() OHNE skip_ba2 (Zeile 3108) -> voller BA2-Cleanup

### Code-Qualitaet
- [x] 18. Qt.ConnectionType ist bereits ueber Qt importiert (Zeile 28: from PySide6.QtCore import Qt); Qt.ConnectionType.UniqueConnection wird an Zeile 274 bereits fuer QueuedConnection verwendet
- [x] 19. python -m py_compile fuer beide Dateien erfolgreich (geprueft)
- [x] 20. App startet ohne Fehler/Tracebacks (geprueft via python main.py, nur bekannte QTabBar alignment Warnings)

## Ergebnis: 20/20 Punkte erfuellt

Alle Akzeptanz-Kriterien sind erfuellt.
