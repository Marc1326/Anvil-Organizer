# Feature: LOOT-Integration
Datum: 2026-03-26

## Zusammenfassung

LOOT (Load Order Optimisation Tool) ist das Standardwerkzeug fuer die automatische Sortierung von Plugin-Ladereihenfolgen (.esp/.esm/.esl) in Bethesda-Spielen. Es analysiert Masterfile-Abhaengigkeiten, erkennt dirty Edits, fehlende Masters und Inkompatibilitaeten und sortiert die Plugins in eine sichere Ladereihenfolge.

Anvil hat bereits einen Plugins-Tab fuer Bethesda-Spiele, einen PluginsTxtWriter der plugins.txt generiert, und vorbereitete TODO-Kommentare in allen 5 Bethesda Game-Plugins. Die Integration erfolgt in zwei Phasen:

- **Phase 1 (v1.2):** LOOT als externes Binary starten, Output parsen, plugins.txt aktualisieren
- **Phase 2 (v1.3):** Eigener Python ESP-Header-Parser mit topologischer Sortierung + LOOT-Masterlist

Diese Spec beschreibt **Phase 1**.

---

## User Stories

- Als Bethesda-Modder moechte ich per Toolbar-Button meine Plugin-Ladereihenfolge mit LOOT sortieren, damit ich keine Abstuerze durch falsche Load Order bekomme.
- Als Bethesda-Modder moechte ich nach der LOOT-Sortierung einen Report sehen (Warnungen, dirty Edits, fehlende Masters), damit ich problematische Plugins identifizieren kann.
- Als Bethesda-Modder moechte ich in den Settings den LOOT-Pfad konfigurieren, damit Anvil mein installiertes LOOT findet.
- Als Bethesda-Modder moechte ich, dass der LOOT-Button nur bei Bethesda-Spielen sichtbar ist, damit die Toolbar bei nicht-Bethesda-Spielen nicht ueberladen wirkt.
- Als Bethesda-Modder moechte ich optional LOOT automatisch bei jedem Deploy ausfuehren, damit meine Load Order immer aktuell ist.
- Als Bethesda-Modder moechte ich den LOOT-Vorgang abbrechen koennen, falls er zu lange dauert.

---

## Technische Planung

### Phasen-Plan

| Phase | Version | Inhalt | Aufwand |
|-------|---------|--------|---------|
| Phase 1 | v1.2 | Externes LOOT-Binary via QProcess starten, Report parsen, plugins.txt aktualisieren | 15-25h |
| Phase 2 | v1.3 | Python ESP-Header-Parser, topologische Sortierung, LOOT-Masterlist YAML | 30-50h |

### Neue Dateien

| Datei | Beschreibung | Zeilen (geschaetzt) |
|-------|-------------|---------------------|
| `anvil/core/loot/__init__.py` | Package-Init | 5 |
| `anvil/core/loot/loot_runner.py` | QProcess-Wrapper: LOOT starten, stdout lesen, Prozess-Management | ~120 |
| `anvil/core/loot/loot_report.py` | JSON-Report-Parser: lootreport.json einlesen und strukturieren | ~80 |
| `anvil/widgets/loot_dialog.py` | QDialog mit Fortschrittsanzeige, Report-Tree, Apply/Cancel-Buttons | ~250 |

### Betroffene bestehende Dateien

| Datei | Aenderung | Aufwand |
|-------|-----------|---------|
| `anvil/plugins/base_game.py` | Neues Attribut `LootGameName: str = ""` | 1 Zeile |
| `anvil/plugins/games/game_skyrimse.py` | `LootGameName = "Skyrim Special Edition"` | 1 Zeile |
| `anvil/plugins/games/game_fallout4.py` | `LootGameName = "Fallout4"` | 1 Zeile |
| `anvil/plugins/games/game_starfield.py` | `LootGameName = "Starfield"` | 1 Zeile |
| `anvil/plugins/games/_wip/game_fallout3.py` | `LootGameName = "Fallout3"` | 1 Zeile |
| `anvil/plugins/games/_wip/game_falloutnv.py` | `LootGameName = "FalloutNV"` | 1 Zeile |
| `anvil/widgets/toolbar.py` | LOOT-Button + Separator (analog merger_btn) | ~20 Zeilen |
| `anvil/mainwindow.py` | LOOT-Button-Sichtbarkeit + `_on_loot_sort_clicked()` | ~40 Zeilen |
| `anvil/widgets/settings_dialog.py` | LOOT-Tab: Pfad, Log-Level, Auto-Sort, Masterlist | ~60 Zeilen |
| `anvil/core/plugins_txt_writer.py` | Neue Methode `write_sorted(sorted_plugins)` | ~25 Zeilen |
| `anvil/widgets/game_panel.py` | Sort-Button im Plugins-Tab + Auto-Sort in Deploy-Chain | ~30 Zeilen |
| 7 Locale-Dateien (`anvil/locales/*.json`) | ~30 neue tr()-Keys | Je ~30 Keys |

### Signal-Flow

```
1. TOOLBAR-BUTTON FLOW:
   [LOOT Toolbar-Button] clicked
     → MainWindow._on_loot_sort_clicked()
       → Prueft: plugin.has_plugins_txt() AND plugin.LootGameName != ""
       → Prueft: LOOT-Binary existiert (QSettings oder shutil.which)
       → Oeffnet LootDialog(parent, plugin, game_path, instance_path)

2. LOOT-DIALOG FLOW:
   LootDialog
     → [Sort-Button] → LootRunner.start() → QProcess
       → readyReadStandardOutput → Fortschritts-Label
       → finished → LootReport.parse(json) → QTreeWidget Report
       → [Apply-Button] enabled
     → [Apply-Button] → PluginsTxtWriter.write_sorted()
       → GamePanel._refresh_plugins_tab()
       → StatusBar: "Load Order aktualisiert"
     → [Cancel-Button] → QProcess.kill() → reject()

3. SETTINGS FLOW:
   SettingsDialog (LOOT-Tab)
     → QLineEdit: LOOT-Binary-Pfad (+ Browse-Button)
     → QComboBox: Log-Level (info/debug/trace)
     → QCheckBox: Auto-Sort bei Deploy
     → QCheckBox: Masterlist aktualisieren
     → accept() → QSettings: "LOOT/binary_path", "LOOT/log_level",
                              "LOOT/auto_sort_on_deploy", "LOOT/update_masterlist"

4. AUTO-SORT FLOW (Optional):
   silent_deploy() / silent_deploy_fast()
     → [Wenn LOOT/auto_sort_on_deploy == True]
       → LootRunner.run_sync() → sortierte Liste
       → PluginsTxtWriter.write_sorted(sorted_plugins)

5. GAME-SWITCH FLOW:
   _apply_instance()
     → has_loot = plugin.has_plugins_txt() and plugin.LootGameName
     → toolbar.loot_sep.setVisible(has_loot)
     → toolbar.loot_action.setVisible(has_loot)
```

### MO2-Vergleich

| Aspekt | MO2 | Anvil (Phase 1) |
|--------|-----|-----------------|
| LOOT-Backend | Eigenes lootcli.exe mit libloot C++ | System-installiertes LOOT-Binary |
| Kommunikation | Named Pipe (Windows) | QProcess stdout/stderr |
| Report-Format | JSON (lootreport.json) | JSON (gleiches Format) |
| Report-Anzeige | QWebEngineView (HTML) | QTreeWidget (leichtgewichtiger) |
| Sortier-Trigger | Button in Plugin-Liste | Toolbar-Button + Plugins-Tab |
| Auto-Sort | Nein (nur manuell) | Optional bei Deploy (QSettings) |
| Plattform | Windows-only | Linux-native |

---

## Verwandte Funktionen (geprueft)

| Funktion | Datei | Wiederverwendbar | Aenderung |
|----------|-------|------------------|-----------|
| `has_plugins_txt()` | `base_game.py:453` | JA — Gate-Check | NEIN |
| `plugins_txt_path()` | `base_game.py:457` | JA — Schreibziel | NEIN |
| `PRIMARY_PLUGINS` | 5 Game-Plugins | JA — Reihenfolge erzwingen | NEIN |
| `PluginsTxtWriter.scan_plugins()` | `plugins_txt_writer.py:58` | JA — Plugin-Liste | NEIN |
| `PluginsTxtWriter.write()` | `plugins_txt_writer.py:124` | JA — Fallback | NEIN |
| Toolbar-Pattern (Script Merger) | `toolbar.py:138-157` | JA — 1:1 kopierbar | Kopieren |
| Sichtbarkeits-Pattern | `mainwindow.py:970-973` | JA — 1:1 kopierbar | Kopieren |
| QProcess-Pattern (KDiff3) | `script_merger_dialog.py:820-826` | JA — Vorlage | Kopieren |
| LOOT-Settings-Platzhalter | `settings_dialog.py:710-716` | JA — ausbauen | Erweitern |
| Bestehende Locale-Keys | `locales/*.json` | JA — 4 Keys vorhanden | +26 Keys |

---

## Risiken

| # | Risiko | Schwere | Mitigation |
|---|--------|---------|------------|
| 1 | Kein offizielles LOOT-CLI fuer Linux | KRITISCH | LOOT --help evaluieren. Falls kein CLI: Phase 1 = "LOOT GUI oeffnen" Button |
| 2 | LOOT nicht installiert | HOCH | Button ausgegraut + Installationshinweis in Settings |
| 3 | Flatpak-Sandbox blockiert Zugriff | HOCH | Dokumentation: AUR statt Flatpak. Oder `flatpak run --filesystem=host` |
| 4 | JSON-Report-Format aendert sich | MITTEL | Defensiver Parser mit Fallbacks + Versions-Check |
| 5 | PRIMARY_PLUGINS umsortiert | NIEDRIG | `write_sorted()` erzwingt Primary zuerst |
| 6 | Wayland Fokus-Problem | NIEDRIG | Nicht relevant bei QProcess-basiertem Ansatz |

---

## LOOT-CLI Evaluierung (VOR Implementierung)

```bash
# Muss vor Phase 1 geprueft werden:
loot --help 2>&1
flatpak run io.github.loot.loot --help 2>&1
```

| LOOT hat CLI | Phase 1 Scope |
|-------------|---------------|
| JA (--sort + JSON-Report) | Vollstaendige Integration: Sort + Report + Apply |
| TEILWEISE (nur GUI-Start) | LOOT GUI oeffnen + plugins.txt nach Schliessung neu lesen |
| NEIN | Nur "Open LOOT" Button + Hinweis "Sortiere manuell, dann Reload" |

---

## Neue Locale-Keys (Phase 1)

| Key | DE | EN |
|-----|----|----|
| `toolbar.loot_sort` | "Plugins sortieren (LOOT)" | "Sort Plugins (LOOT)" |
| `loot.dialog_title` | "LOOT — Ladereihenfolge-Optimierung" | "LOOT — Load Order Optimisation" |
| `loot.sort_button` | "Plugins sortieren" | "Sort Plugins" |
| `loot.apply_button` | "Ladereihenfolge anwenden" | "Apply Load Order" |
| `loot.sorting_in_progress` | "Sortiere Plugins..." | "Sorting plugins..." |
| `loot.sorting_complete` | "Sortierung abgeschlossen" | "Sorting complete" |
| `loot.sorting_failed` | "Sortierung fehlgeschlagen" | "Sorting failed" |
| `loot.no_binary` | "LOOT nicht gefunden. Pfad in Einstellungen konfigurieren." | "LOOT not found. Configure path in Settings." |
| `loot.not_bethesda` | "LOOT ist nur fuer Bethesda-Spiele verfuegbar." | "LOOT is only available for Bethesda games." |
| `loot.report_warnings` | "Warnungen" | "Warnings" |
| `loot.report_errors` | "Fehler" | "Errors" |
| `loot.report_dirty` | "Dirty Plugins" | "Dirty Plugins" |
| `loot.report_missing_masters` | "Fehlende Masters" | "Missing Masters" |
| `loot.report_incompatible` | "Inkompatibilitaeten" | "Incompatibilities" |
| `loot.plugins_reordered` | "%n Plugin(s) umsortiert" | "%n plugin(s) reordered" |
| `loot.no_changes` | "Ladereihenfolge ist bereits optimal" | "Load order is already optimal" |
| `loot.confirm_apply` | "Neue Ladereihenfolge anwenden?" | "Apply new load order?" |
| `settings.tab_loot` | "LOOT" | "LOOT" |
| `settings.loot_binary_path` | "LOOT-Pfad:" | "LOOT Path:" |
| `settings.loot_browse` | "Durchsuchen..." | "Browse..." |
| `settings.loot_auto_sort` | "Automatisch bei Deploy sortieren" | "Automatically sort on deploy" |
| `settings.loot_update_masterlist` | "Masterlist vor Sortierung aktualisieren" | "Update masterlist before sorting" |
| `settings.loot_install_hint` | "LOOT installieren: AUR (loot) oder Flatpak (io.github.loot.loot)" | "Install LOOT: AUR (loot) or Flatpak (io.github.loot.loot)" |

---

## Akzeptanz-Kriterien (Phase 1)

- [ ] 1. Wenn User ein Bethesda-Spiel (SkyrimSE, Fallout 4, Starfield) als aktive Instanz hat, erscheint ein "Plugins sortieren (LOOT)"-Button in der Toolbar
- [ ] 2. Wenn User ein Nicht-Bethesda-Spiel (Cyberpunk 2077, Witcher 3, BG3, RDR2) als aktive Instanz hat, ist der LOOT-Button und sein Separator unsichtbar
- [ ] 3. Wenn User zwischen Instanzen wechselt (z.B. Skyrim SE → Cyberpunk), aktualisiert sich die LOOT-Button-Sichtbarkeit sofort
- [ ] 4. Wenn User den LOOT-Button klickt und LOOT nicht installiert ist, erscheint eine Fehlermeldung mit Installationshinweis
- [ ] 5. Wenn User den LOOT-Button klickt und LOOT installiert ist, oeffnet sich der LootDialog mit aktuellem Spielnamen im Titel
- [ ] 6. Wenn User im LootDialog auf "Plugins sortieren" klickt, startet ein LOOT-Prozess und eine Fortschrittsanzeige wird sichtbar
- [ ] 7. Wenn der LOOT-Prozess erfolgreich beendet wird, zeigt der Dialog den Report in einem QTreeWidget an (Warnungen, Dirty Plugins, fehlende Masters)
- [ ] 8. Wenn User im LootDialog auf "Ladereihenfolge anwenden" klickt, wird plugins.txt mit der LOOT-sortierten Reihenfolge ueberschrieben, wobei PRIMARY_PLUGINS immer zuerst stehen
- [ ] 9. Wenn User im LootDialog auf "Abbrechen" klickt waehrend LOOT laeuft, wird der QProcess terminiert ohne Aenderungen an plugins.txt
- [ ] 10. Wenn User in den Settings den LOOT-Tab oeffnet, sieht er Pfad-Feld, Browse-Button, Log-Level-Dropdown, Auto-Sort-Checkbox, Masterlist-Checkbox
- [ ] 11. Wenn User in den Settings einen LOOT-Pfad eingibt und OK klickt, wird der Pfad in QSettings gespeichert und beim naechsten Start verwendet
- [ ] 12. Wenn User "Auto-Sort bei Deploy" aktiviert und einen Deploy ausfuehrt, wird LOOT automatisch ausgefuehrt
- [ ] 13. Wenn LOOT keine Aenderungen vorschlaegt, zeigt der Dialog "Ladereihenfolge ist bereits optimal"
- [ ] 14. Wenn der LOOT-Prozess mit Fehler beendet wird, zeigt der Dialog eine Fehlermeldung mit stderr-Output
- [ ] 15. Wenn User die App nach LOOT-Sortierung neu startet, bleibt die sortierte Reihenfolge erhalten
- [ ] 16. Wenn der LootDialog geoeffnet wird, sind alle Texte in der aktuellen Anvil-Sprache (alle 7 Locale-Dateien)
- [ ] 17. Wenn User den LOOT-Pfad als Flatpak-Befehl eintraegt (z.B. "flatpak run io.github.loot.loot"), funktioniert der Aufruf korrekt
- [ ] 18. Wenn BaseGame kein LootGameName hat (leerer String), ist der LOOT-Button unsichtbar
- [ ] 19. `restart.sh` startet ohne Fehler
