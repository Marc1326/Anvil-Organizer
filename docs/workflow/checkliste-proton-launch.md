# Feature: Non-Primary Executables via Proton starten

## Analyse

### Problem
In `game_panel.py` Zeile 520-576, Methode `_on_start_clicked()`:
- Zeile 534: `if binary == plugin.GameBinary` -- NUR das Hauptspiel wird ueber Steam/Proton gestartet
- Zeile 558-576: Alle anderen Executables (F4SE, Launcher, REDmod, DX12, etc.) fallen in den "direkten Start" Branch
- Der "direkte Start" emittiert `start_requested` Signal, das in `mainwindow.py` Zeile 1167-1179 `QProcess.startDetached(binary_path, [], working_dir)` aufruft
- Das startet die .exe direkt als Linux-Prozess -- das schlaegt fehl weil .exe unter Linux nicht ausfuehrbar ist

### Loesung
Fuer Steam-Spiele muessen ALLE Executables ueber Proton gestartet werden.

**Ansatz:** Wenn ein Steam-Spiel erkannt wird, werden auch Nicht-GameBinary-Executables ueber `steam -applaunch <SteamID>` gestartet. Fuer Executables die NICHT das GameBinary sind, nutzen wir direkt Proton (`proton run <exe>`), weil Steam nur ein einziges Binary pro `-applaunch` starten kann.

**Bester Ansatz: `STEAM_COMPAT_DATA_PATH` + `proton run`**
- Findet die Proton-Version die Steam fuer das Spiel nutzt
- Setzt die richtigen Environment-Variablen
- Startet das .exe ueber Proton direkt

**Alternativ: `steam -applaunch` mit Launch Options Hack** -- nicht gut weil Steam UI-Dialog oeffnet.

### Betroffene Dateien
1. `anvil/widgets/game_panel.py` -- `_on_start_clicked()` Methode
2. `anvil/plugins/base_game.py` -- Neue Helper-Methode `protonRunEnv()` oder aehnlich
3. `anvil/mainwindow.py` -- `_on_start_game()` Methode (Signal-Handler)
4. `anvil/locales/*.json` -- Neue i18n-Keys fuer Fehlermeldungen

### Nicht-betroffene Dateien (NICHT anfassen!)
- `anvil/plugins/games/game_baldursgate3.py` -- BG3 NIEMALS aendern
- Cover-Bilder, Icons

## Akzeptanz-Kriterien (ALLE muessen erfuellt sein)

- [ ] 1. Wenn User F4SE aus dem Executable-Dropdown waehlt und "Start" klickt, wird f4se_loader.exe ueber Proton gestartet (nicht direkt als Linux-Binary)
- [ ] 2. Wenn User das Haupt-GameBinary (z.B. Fallout4.exe) startet, wird es weiterhin ueber `steam -applaunch <SteamID>` gestartet (keine Regression)
- [ ] 3. Wenn User eine Nicht-Haupt-Executable eines Steam-Spiels startet, wird diese ueber Proton mit korrekt gesetztem `STEAM_COMPAT_DATA_PATH` und `STEAM_COMPAT_CLIENT_INSTALL_PATH` gestartet
- [ ] 4. Wenn kein Proton-Prefix gefunden wird, zeigt die App eine Fehlermeldung (nicht stiller Absturz)
- [ ] 5. Wenn kein Proton-Binary gefunden wird, zeigt die App eine Fehlermeldung mit Hinweis
- [ ] 6. Cyberpunk 2077 REDmod/REDprelauncher-Start funktioniert ueber Proton (kein direkter .exe Start)
- [ ] 7. Witcher 3 DX12-Variante funktioniert ueber Proton (kein direkter .exe Start)
- [ ] 8. BG3-Code wurde NICHT veraendert (git diff zeigt keine Aenderungen an BG3-Dateien)
- [ ] 9. Neue i18n-Keys sind in ALLEN 6 Locale-Dateien vorhanden (de, en, es, fr, it, pt)
- [ ] 10. Keine hardcoded Pfade -- Proton-Pfad wird dynamisch aus Steam Library ermittelt
- [ ] 11. Die Proton-Erkennung findet die richtige Proton-Version (aus compatdata des Spiels oder aus common/Proton*)
- [ ] 12. Die Methode `_on_start_game()` in mainwindow.py wird NICHT mehr fuer Steam-Executables aufgerufen (alles in game_panel.py gehandelt)
- [ ] 13. `./restart.sh` startet ohne Fehler
