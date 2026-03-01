# QA-Report: plugins.txt Fix -- Iteration 1

## Checklisten-Pruefung

- [x] Kriterium 1: Case-Varianten-Handling -- `_remove_case_variants()` wird in `write()` VOR dem Schreiben aufgerufen (Zeile 144). Die Methode scannt das Verzeichnis, vergleicht case-insensitiv, und loescht alle Varianten die nicht exakt dem Ziel-Dateinamen entsprechen. Verifiziert: Nach App-Start nur EINE `plugins.txt` im Verzeichnis.

- [x] Kriterium 2: plugins.txt Inhalt nach Deploy -- Verifiziert durch `cat plugins.txt`: 21 Eintraege vorhanden (8 PRIMARY + 4 Mod-ESPs + 9 CC-ESLs). Deutlich mehr als die geforderten 12.

- [x] Kriterium 3: Creation Club ESLs -- Verifiziert: 9 CC-ESL-Dateien sind in plugins.txt enthalten (ccBGSFO4044, ccBGSFO4046, ccBGSFO4096, ccBGSFO4110, ccBGSFO4115, ccBGSFO4116, ccFSVFO4007, ccOTMFO4001, ccSBJFO4003).

- [x] Kriterium 4: Purge entfernt Case-Varianten -- `remove()` ruft `self._remove_case_variants(txt_path)` auf (Zeile 167) VOR dem Loeschen der eigentlichen Datei. Alle Case-Varianten (Plugins.txt, PLUGINS.TXT etc.) werden entfernt, danach wird die Ziel-Datei selbst geloescht.

- [x] Kriterium 5: Diagnostik-Logging bei leerer Liste -- Drei Pfade implementiert:
  - Data-Verzeichnis nicht vorhanden: `"Data directory not found: {data_dir}"` (Zeile 78)
  - Keine Plugin-Dateien: `"No plugin files found in {data_dir}"` (Zeile 95)
  - OSError: `"Error scanning {data_dir}: {exc}"` (Zeile 91, war bereits vorhanden)

- [x] Kriterium 6: write()-Fehlschlag-Warnung in silent_deploy() -- In game_panel.py Zeile 599-600: `result_path = writer.write()` + `if result_path is None: print("[GamePanel] plugins.txt write failed or skipped", flush=True)`

- [x] Kriterium 7: Erfolgs-Logging -- `print(f"{_TAG} Wrote {len(plugins)} plugins to {txt_path}")` in Zeile 154. Verifiziert durch Laufzeit-Output: `[PluginsTxtWriter] Wrote 21 plugins to /mnt/.../plugins.txt`

- [x] Kriterium 8: makedirs fuer Proton-Prefix -- `os.makedirs(txt_path.parent, exist_ok=True)` in Zeile 141. Unveraendert beibehalten.

- [x] Kriterium 9: Nicht-Bethesda-Spiele nicht betroffen -- Geprueft: Cyberpunk 2077, Witcher 3, BG3, RDR2 haben kein PRIMARY_PLUGINS (erben leere Liste aus base_game.py). `has_plugins_txt()` gibt `False` zurueck. Der PluginsTxtWriter-Block in silent_deploy() und silent_purge() wird durch die `has_plugins_txt()`-Pruefung komplett uebersprungen.

- [x] Kriterium 10: App startet ohne Fehler -- `python main.py` startet ohne Tracebacks, NameError, ImportError oder AttributeError. QTabBar "alignment" Warnings sind bekannt und koennen ignoriert werden.

## Ergebnis: 10/10 Punkte erfuellt

Keine CRITICAL Bugs gefunden. Keine zusaetzlichen Probleme identifiziert.
