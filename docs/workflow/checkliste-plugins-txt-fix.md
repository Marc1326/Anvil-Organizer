# Akzeptanz-Checkliste: plugins.txt Fix

- [ ] Kriterium 1: Wenn Anvil plugins.txt schreibt und eine `Plugins.txt` (gross-P) im selben Verzeichnis existiert, wird die gross-P-Variante VOR dem Schreiben geloescht, sodass nur EINE Datei mit dem korrekten Namen (`plugins.txt`) verbleibt
- [ ] Kriterium 2: Wenn User silent_deploy() ausfuehrt und 4 Mod-ESPs deployed sind, enthaelt die resultierende plugins.txt mindestens 12 Eintraege (8 PRIMARY + 4 Mod-ESPs) -- nicht 0
- [ ] Kriterium 3: Wenn User silent_deploy() ausfuehrt und Creation Club ESLs im Data-Verzeichnis liegen, werden diese ebenfalls in plugins.txt aufgefuehrt (aktuell 21 total)
- [ ] Kriterium 4: Wenn User silent_purge() ausfuehrt, werden ALLE Case-Varianten von plugins.txt entfernt (sowohl `plugins.txt` als auch `Plugins.txt` als auch andere Varianten wie `PLUGINS.TXT`)
- [ ] Kriterium 5: Wenn scan_plugins() eine leere Liste zurueckgibt, wird im Log der Grund ausgegeben ("Data directory not found" vs. "No plugin files found" vs. OSError-Details)
- [ ] Kriterium 6: Wenn write() fehlschlaegt (return None), wird in silent_deploy() eine Warnung ins Log geschrieben
- [ ] Kriterium 7: Wenn write() erfolgreich ist, wird im Log die Anzahl der geschriebenen Plugins UND der Ziel-Pfad ausgegeben (bereits implementiert -- sicherstellen dass es bestehen bleibt)
- [ ] Kriterium 8: Wenn die Proton-Prefix-Verzeichnisstruktur nicht existiert, wird sie von write() automatisch erstellt (bereits implementiert via makedirs -- sicherstellen dass es bestehen bleibt)
- [ ] Kriterium 9: Nicht-Bethesda-Spiele (Cyberpunk 2077, Witcher 3, BG3, RDR2) sind von den Aenderungen nicht betroffen -- kein veraendertes Verhalten
- [ ] Kriterium 10: restart.sh startet ohne Fehler
