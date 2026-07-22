# Handoff: Issue #98 – nativer Anvil-Loadorder-Sorter

Stand: 2026-07-22, nach Marcs ausdrücklichem GO. Keine Commits erstellt.

## Ziel / Entscheidung
- Marc wollte ursprünglich eine eigene native Anvil-Sortierung, keine dauerhafte externe LOOT-GUI-/libloot-Pflicht.
- LOOT dient als Architektur-/Datenreferenz.
- Danach folgt separat die Funktion „Ordner/Dateien verschieben“; nicht mit diesem Scope vermischen.

## Historie / Ursachen
- `67435e3`: eigener PluginsTxtWriter/Plugins-Tab, ausdrücklich Phase 1.
- `69521fc`: plugins.txt darf beim Purge nicht gelöscht werden.
- `5415a01`: BA2-Commit führte Löschung versehentlich wieder ein (Regression).
- `9390965`: externe LOOT-Integration unvollständig; behauptete Re-Read, scannte aber alphabetisch; `write_sorted`/Report tot.
- Hauptbug: `LootRunner.start()` NameError `is_flatpak`; zusätzlich UI/Deploy ignorierten echte Reihenfolge.

## Bereits geändert
1. `tests/test_plugin_load_order.py` neu, derzeit 10 Tests grün.
2. `anvil/core/plugins_txt_writer.py`
   - `PluginEntry`, `PluginSortResult`
   - `profile_name` und `<Instanz>/.profiles/<Profil>/plugins.txt`
   - reale Asterisk-Datei lesen, Reihenfolge/Aktivierung erhalten
   - atomar in Profil + Proton-Prefix schreiben
   - `write()` nutzt Profilzustand statt alphabetischen Neuaufbau
   - `sort_entries()` / `sort_and_write()`, ungültige Ergebnisse werden nicht angewendet
3. `anvil/core/plugin_sorter.py` neu
   - TES4-Headerparser, MAST, Master-/Light-Flag
   - Skyrim/Fallout `.ccc`-Parser
   - stabiler Kahn-Toposort
   - Primär-/implizite Inhalte, Missing Masters, Zyklen, Parsefehler
4. `anvil/widgets/game_panel.py`
   - Writer-Aufrufe erhalten aktives Profil
   - `silent_purge()` löscht plugins.txt nicht mehr
   - Plugins-Tab liest echte Profilreihenfolge/Aktivierung
   - Checkboxen speichern Profil + Spiel
   - InternalMove / manuelles Reorder mit Persistenz
   - Primärplugins nicht check-/dragbar
   - `sort_plugins_native()` und Auto-Sort nutzt nativen Sortierer
5. `anvil/plugins/base_game.py`
   - `PluginLoadOrderFormat`, `CreationClubFile`
   - `has_plugins_txt()` nur für explizites `asterisk`
6. Skyrim/Fallout4/Starfield
   - explizites `PluginLoadOrderFormat = "asterisk"`
   - Skyrim `CreationClubFile = "Skyrim.ccc"`
   - Fallout4 `CreationClubFile = "Fallout4.ccc"`
7. `anvil/mainwindow.py`
   - Toolbar-Methode startet nativen Sortierer statt `LootDialog`
   - zeigt Missing Masters/Zyklen/Parsefehler oder Erfolg

## Letzter grüner Test
```bash
QT_QPA_PLATFORM=offscreen uv run --python .venv/bin/python --with pytest python -m pytest -q tests/test_plugin_load_order.py
# 10 passed in 0.25s
```

## TDD-Status / unmittelbarer nächster Schritt
Begonnen, aber noch NICHT als Test eingefügt:
- Screenshot-Fallback ohne vorhandene `Skyrim.ccc`: bekannte `cc...`-Dateien und `_ResourcePack.esl` müssen als implizite Inhalte vor normalen Mods stehen.
- FakeSkyrimGame im Test besitzt bereits:
  - `ImplicitPluginPrefixes = ("cc",)`
  - `ImplicitPluginNames = ("_ResourcePack.esl",)`
- Nächster Schritt: roten Test `test_native_sort_recognises_skyrim_cc_files_without_ccc_manifest` am Dateiende ergänzen, laufen lassen, danach minimale Implementierung in Writer/Spielplugin.

## Danach noch erforderlich
1. MainWindow-/Toolbar-Sichtbarkeit von `LootGameName` entkoppeln; Capability reicht.
2. Hardcodierte deutsche Diagnoseüberschriften in MainWindow lokalisieren (7 Locales oder vorhandene Keys nutzen).
3. Externe LOOT-Einstellungen/Tab bereinigen oder als veraltete UI entfernen/umwidmen; aktuell darf kein falscher externer Pfadbedarf suggeriert werden.
4. Implizite CC-Plugins auch in UI sperren, nicht nur Primary.
5. ESL-/Light-Indexanzeige korrigieren (mindestens FE:xxx anhand Headerflag); Starfield gesondert vorsichtig.
6. Test für Zyklus und für zwei unabhängige Profile ergänzen.
7. `write_sorted()`/`remove()`/externe LootDialog/LootRunner als toten Legacy-Code bewerten und sauber entfernen, sofern keine Aufrufer.
8. Alle regulären Tests:
```bash
QT_QPA_PLATFORM=offscreen uv run --python .venv/bin/python --with pytest python -m pytest -q tests
```
Baseline vor Änderungen: `67 passed, 1 skipped`; neue Tests kommen hinzu.
9. `python -m compileall -q anvil`, Git diff/scope prüfen.
10. Kein Commit ohne Marc zu fragen. >50 Zeilen, eigener LOOT-Commit dringend empfehlen.

## Nicht anfassen
- BG3, GRB, Cyberpunk, Speicherverwaltung und sonstige sachfremde Dateien.
- Keine Ordner-/Dateiverschiebe-Funktion in diesen Commit mischen.
