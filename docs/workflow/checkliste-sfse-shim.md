# Akzeptanz-Checkliste: SFSE Proton Shim (Issue #55)
Datum: 2026-03-22

## Anvil Plugin (game_starfield.py)

- [ ] 1. Wenn User Anvil startet und Starfield (Steam ID 1716740) installiert ist, erscheint "Starfield" in der Spieleliste
- [ ] 2. Wenn User Starfield als aktives Spiel waehlt, werden Game-Dir, Documents-Dir und Saves-Dir korrekt aufgeloest
- [ ] 3. Wenn User eine neue Starfield-Instanz erstellt, werden 19 Starfield-spezifische Kategorien als Default angelegt (inkl. Ships, Outposts)
- [ ] 4. Wenn User Deploy ausfuehrt und sfse_loader.exe im Spielordner liegt, wird version.dll ins Spielverzeichnis kopiert
- [ ] 5. Wenn User Deploy ausfuehrt und sfse_loader.exe NICHT im Spielordner liegt, wird version.dll NICHT kopiert
- [ ] 6. Wenn User Starfield ueber Proton startet und version.dll im Spielordner existiert, wird WINEDLLOVERRIDES="version=n,b" gesetzt
- [ ] 7. Wenn User Starfield ueber Proton startet und version.dll NICHT im Spielordner existiert, wird WINEDLLOVERRIDES nicht gesetzt
- [ ] 8. Wenn User Purge ausfuehrt, wird die per Deploy kopierte version.dll aus dem Spielverzeichnis entfernt

## SFSE Proton Shim DLL (sfse-proton-shim Projekt)

- [ ] 9. Wenn `./build.sh` ausgefuehrt wird, entsteht `dist/version.dll` als PE32+ x86-64 DLL ohne Fehler
- [ ] 10. Wenn `objdump -p dist/version.dll` ausgefuehrt wird, zeigt die Export-Table genau 3 Funktionen: GetFileVersionInfoA, GetFileVersionInfoSizeA, VerQueryValueA
- [ ] 11. Wenn `objdump -p dist/version.dll | grep "DLL Name"` ausgefuehrt wird, erscheinen NUR System-DLLs (keine MinGW-Runtime-DLLs)
- [ ] 12. Wenn `file dist/version.dll` ausgefuehrt wird, zeigt es "PE32+ executable (DLL) (console) x86-64"
- [ ] 13. Wenn die kompilierte version.dll nach `anvil/data/shims/starfield/version.dll` kopiert wird, ist sie kleiner als 200KB

## Keine Seiteneffekte

- [ ] 14. Wenn Fallout 4 als aktives Spiel gewaehlt wird, funktioniert der F4SE-Shim-Deploy weiterhin identisch
- [ ] 15. Wenn ein anderes Spiel gewaehlt wird, aendert sich dessen Verhalten nicht
- [ ] 16. Wenn `_wip/game_starfield.py` nicht mehr existiert (verschoben), laeuft Anvil fehlerfrei

## Abschluss

- [ ] 17. restart.sh startet ohne Fehler
