# QA-Report: Non-Primary Executables via Proton starten

## Checklisten-Pruefung

- [x] 1. F4SE ueber Proton gestartet -- `_launch_via_proton()` wird aufgerufen wenn binary != GameBinary und Spiel ist Steam
- [x] 2. Haupt-GameBinary weiterhin ueber `steam -applaunch` -- `_launch_via_steam()` wird aufgerufen wenn binary == GameBinary
- [x] 3. Nicht-Haupt-Executable mit korrektem `STEAM_COMPAT_DATA_PATH` und `STEAM_COMPAT_CLIENT_INSTALL_PATH` -- beide gesetzt in `_launch_via_proton()`
- [x] 4. Fehlermeldung wenn kein Proton-Prefix -- `proton_not_found` Key wird angezeigt wenn `findProtonRun()` None zurueckgibt
- [x] 5. Fehlermeldung wenn kein Proton-Binary -- selbe Meldung wie 4, da `findProtonRun()` None zurueckgibt wenn kein proton-Script gefunden
- [x] 6. Cyberpunk REDmod/REDprelauncher ueber Proton -- binary ("tools/redmod/bin/redMod.exe" / "REDprelauncher.exe") != GameBinary ("bin/x64/Cyberpunk2077.exe") -> geht in _launch_via_proton
- [x] 7. Witcher 3 DX12-Variante ueber Proton -- binary ("bin/x64_dx12/witcher3.exe") != GameBinary ("bin/x64/witcher3.exe") -> geht in _launch_via_proton
- [x] 8. BG3-Code nicht veraendert -- git diff zeigt keine Aenderungen an BG3-Dateien
- [x] 9. i18n-Keys in allen 6 Locale-Dateien -- `proton_not_found` und `proton_launch_failed` in de, en, es, fr, it, pt
- [x] 10. Keine hardcoded Pfade -- Proton-Pfad dynamisch aus config_info und Steam Libraries ermittelt
- [x] 11. Proton-Erkennung findet richtige Version -- config_info wird gelesen, Fallback auf neueste Proton-Version in Libraries
- [x] 12. `_on_start_game()` in mainwindow.py nicht mehr fuer Steam-Executables -- alle Steam-Launches (Haupt + Non-Primary) werden in game_panel.py gehandelt, start_requested.emit() nur noch fuer Non-Steam-Spiele
- [x] 13. App startet ohne Fehler -- nur bekannte QTabBar alignment Warnings

## Ergebnis: 13/13 Punkte erfuellt
