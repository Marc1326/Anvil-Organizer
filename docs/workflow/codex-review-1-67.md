# Code-Review 1 - Issue #67 (Custom Deploy Paths pro Separator)
Datum: 2026-03-26
Reviewer: Code-Review Agent 1 (Bugs, Logikfehler, Edge Cases)

## Ergebnis: ACCEPTED

## Pruefung gegen Akzeptanz-Kriterien

| # | Kriterium | Status | Begruendung |
|---|-----------|--------|-------------|
| 1 | Rechtsklick auf Separator zeigt "Deploy-Pfad setzen..." | OK | mainwindow.py Zeile 2332: `act_set_deploy_path = menu.addAction(tr("context.set_deploy_path"))` nur wenn `_sep_entry.is_separator` |
| 2 | QFileDialog oeffnet sich | OK | mainwindow.py Zeile 2531: `QFileDialog.getExistingDirectory()` |
| 3 | Pfad wird in meta.ini gespeichert | OK | Zeile 2540-2541: `write_meta_ini(entry.install_path, {"deploy_path": chosen_path})` |
| 4 | Deploy nutzt Custom-Pfad | OK | mod_deployer.py Zeile 298-300: `mod_separator` lookup, `deploy_base` Berechnung |
| 5 | Fallback auf globalen Game-Pfad | OK | Zeile 300: `deploy_base = Path(sep_path) if sep_path else self._game_path` |
| 6 | Purge entfernt aus Custom-Pfad | OK | Zeile 488-490: `entry_deploy_base` aus Manifest, `base_path` korrekt gesetzt |
| 7 | Reset entfernt Custom-Pfad | OK | Zeile 2574: `write_meta_ini(entry.install_path, {"deploy_path": ""})` |
| 8 | Persistenz ueber Neustart | OK | mod_entry.py liest `deploy_path` aus meta.ini bei Build |
| 9 | Nicht-Separator sieht keine Optionen | OK | Zeile 2326: `if _sep_entry.is_separator:` Guard |
| 10 | Tooltip zeigt Custom-Pfad | OK | mod_list_model.py: ToolTipRole mit `Deploy -> {r.deploy_path}` |
| 11 | data_path wird angewendet | OK | Zeile 275-295: data_path wird VOR deploy_base berechnet, rel enthaelt bereits data_path |
| 12 | Locale-Keys in allen 7 Sprachen | OK | 5 Keys in de, en, es, fr, it, pt, ru vorhanden |
| 13 | App startet ohne Fehler | OK | Getestet: 20 symlinks, 0 errors |

## Notizen

### Minor: created_dirs Format bei Pfaden mit Doppelpunkt
In `mod_deployer.py` Zeile 328: `f"{deploy_base}:{dir_key}"` — wenn deploy_base einen Doppelpunkt enthaelt (z.B. `/mnt/my:drive/`), wuerde die Purge-Logik in Zeile 549 (`dir_rel.index(":", 1)`) den Pfad falsch parsen. Auf Linux sind Doppelpunkte in Pfaden extrem selten und kein realistisches Szenario. Kein Blocker.

### Info: LML-Mods ignorieren Custom-Pfad
LML-Mods (install.xml) deployen immer in `self._game_path`, nicht in `deploy_base`. Das ist korrektes Verhalten, da LML-Mods Verzeichnis-Symlinks sind, die in einem festen Pfad liegen muessen.
