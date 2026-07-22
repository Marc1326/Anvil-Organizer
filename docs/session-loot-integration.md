# Anvil Organizer — Session 2026-03-26: LOOT-Integration

## Zusammenfassung

LOOT (Load Order Optimisation Tool) wurde als externes GUI-Tool in Anvil Organizer eingebunden. Die Integration umfasst einen QProcess-Wrapper mit Flatpak-Support, einen automatisch startenden Dialog mit Fortschrittsanzeige sowie die automatische Übernahme der sortierten plugins.txt. Im Verlauf der Implementierung wurden 5 Bugs iterativ identifiziert und behoben.

## Commits

| Hash | Message |
|------|---------|
| `9390965` | feat: LOOT-Integration fuer Bethesda-Spiele (Skyrim SE, Fallout 4, Starfield) |

## Neue Dateien

| Datei | Beschreibung |
|-------|-------------|
| `anvil/core/loot/__init__.py` | Package-Init |
| `anvil/core/loot/loot_runner.py` | QProcess-Wrapper, Flatpak-Support (`--filesystem=host` + `/mnt`) |
| `anvil/core/loot/loot_report.py` | JSON-Report-Parser (vorbereitet für Phase 2 / CLI-Nutzung) |
| `anvil/widgets/loot_dialog.py` | Dialog mit Auto-Start, Fortschrittsanzeige, Neustart-Button |

## Modifizierte Dateien

| Datei | Änderung |
|-------|---------|
| `anvil/core/plugins_txt_writer.py` | plugins.txt nach LOOT-Abschluss neu einlesen |
| `anvil/mainwindow.py` | LOOT-Button in Toolbar eingebunden, Dialog-Aufruf |
| `anvil/widgets/game_panel.py` | `_auto_loot_sort()` deaktiviert — LOOT ist GUI, kein CLI |
| `anvil/widgets/settings_dialog.py` | LOOT-Pfad-Konfiguration (Binary oder Flatpak) |
| `anvil/widgets/toolbar.py` | LOOT-Button nur bei Bethesda-Spielen sichtbar |
| `anvil/plugins/base_game.py` | Property `loot_game_name` hinzugefügt |
| `anvil/plugins/games/game_skyrimse.py` | `loot_game_name = "Skyrim Special Edition"` |
| `anvil/plugins/games/game_fallout4.py` | `loot_game_name = "Fallout4"` |
| `anvil/plugins/games/game_starfield.py` | `loot_game_name = "Starfield"` |
| `anvil/plugins/games/_wip/game_fallout3.py` | `loot_game_name = "Fallout3"` |
| `anvil/plugins/games/_wip/game_falloutnv.py` | `loot_game_name = "FalloutNV"` |
| 7x `anvil/locales/*.json` | LOOT-Übersetzungsschlüssel (de, en, es, fr, it, pt, ru) |

Gesamt: **22 Dateien, 865 Zeilen** (848 Einfügungen, 17 Löschungen)

## Gelöste Bugs

| # | Bug | Ursache | Fix |
|---|-----|---------|-----|
| 1 | Doppel-Klick nötig (Toolbar + Dialog) | Kein Auto-Start im Dialog | `QTimer.singleShot(0)` — LOOT startet beim Öffnen automatisch; Start-Button entfernt |
| 2 | Flatpak Double-Program: `flatpak flatpak run ...` | `parts[0:]` statt `parts[1:]` für run_args | `parts[1:]` — Programm-Name nicht nochmals als Argument übergeben |
| 3 | "failed to override game path" | `--game-path` kollidiert mit LOOT `settings.toml` | `--game-path` komplett entfernt |
| 4 | Flatpak blockiert Zugriff auf `/mnt` | `--filesystem=host` deckt `/mnt`-Mounts nicht ab | Explizit `--filesystem=/mnt` als zusätzliches Argument |
| 5 | Falsche Erfolgsmeldung ohne Sortierung | "Plugin-Liste aktualisiert" wurde immer angezeigt | Neutrale Meldung "plugins.txt wurde neu eingelesen" |

## Technische Details

| Parameter | Wert |
|-----------|-----|
| LOOT-Version | Flatpak v0.28.0 (`io.github.loot.loot`) |
| Aufruf | `flatpak run --filesystem=host --filesystem=/mnt io.github.loot.loot --game "Skyrim Special Edition" --auto-sort` |
| LOOT-Config | `~/.var/app/io.github.loot.loot/data/LOOT/settings.toml` |
| Getestetes Spiel | Skyrim SE auf `/mnt/gamingS/SteamLibrary/steamapps/common/Skyrim Special Edition/` |

## QA Ergebnis

Kein automatischer QA-Report vorhanden. Feature-Spec (`docs/anvil-feature-loot-integration.md`) wurde als Grundlage verwendet.

Implementiert gemäss Feature-Spec Phase 1 (v1.2). Phase 2 (eigener Python ESP-Parser) ist noch offen.

## Offene Punkte

- [ ] Phase 2: Eigener Python ESP-Header-Parser mit topologischer Sortierung (v1.3)
- [ ] Phase 2: LOOT-Masterlist YAML-Integration
- [ ] Akzeptanz-Kriterium 7: Report-Anzeige (Warnungen, Dirty Plugins, fehlende Masters) im QTreeWidget — abhängig von LOOT-CLI-Ausgabe
- [ ] Akzeptanz-Kriterium 12: Auto-Sort bei Deploy (QSettings `LOOT/auto_sort_on_deploy`) noch nicht implementiert
- [ ] LOOT native Binary (AUR `loot`) testen — bisher nur Flatpak getestet
- [ ] Oberon, Morrowind und weitere Bethesda-WIP-Plugins: `loot_game_name` prüfen

## Nächste Schritte

1. Auto-Sort-bei-Deploy implementieren (`LOOT/auto_sort_on_deploy` in `silent_deploy()`)
2. Report-Anzeige im Dialog mit QTreeWidget ausbauen (Warnungen, Dirty Plugins, fehlende Masters)
3. LOOT mit nativem AUR-Binary testen (`/usr/bin/loot`)
4. Phase 2 planen: Python ESP-Parser + Masterlist YAML
