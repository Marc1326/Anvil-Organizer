# Issue-State-Review - Issue #67 (Custom Deploy Paths pro Separator)
Datum: 2026-03-26
Reviewer: Claude Review Agent 2 (Issue State + Locale + Vollstaendigkeit)

## Ergebnis: ACCEPTED

## Locale-Pruefung (5 Keys x 7 Sprachen)

| Key | DE | EN | ES | FR | IT | PT | RU |
|-----|----|----|----|----|----|----|-----|
| context.set_deploy_path | OK | OK | OK | OK | OK | OK | OK |
| context.reset_deploy_path | OK | OK | OK | OK | OK | OK | OK |
| dialog.deploy_path_title | OK | OK | OK | OK | OK | OK | OK |
| dialog.deploy_path_set | OK | OK | OK | OK | OK | OK | OK |
| dialog.deploy_path_reset | OK | OK | OK | OK | OK | OK | OK |

Alle 35 Eintraege vorhanden und korrekt platziert (context.* im context-Block, dialog.* im dialog-Block).

## Geaenderte Dateien (Vollstaendigkeit)

| Datei | In Spec geplant | Implementiert |
|-------|----------------|---------------|
| anvil/core/mod_deployer.py | Ja | Ja |
| anvil/core/mod_entry.py | Ja | Ja |
| anvil/mainwindow.py | Ja | Ja |
| anvil/widgets/game_panel.py | Ja | Ja |
| anvil/models/mod_list_model.py | Nein (nicht in Spec) | Ja (fuer ToolTip) |
| 7 Locale-Dateien | Ja | Ja |

mod_list_model.py war nicht explizit in der Spec geplant, aber die Aenderung (ModRow.deploy_path + ToolTipRole) ist notwendig fuer Kriterium 10 (Tooltip).

## NICHT geaenderte Dateien (korrekt laut Spec)

- mod_list_io.py: Nicht betroffen (deploy_path kommt aus meta.ini, nicht modlist.txt)
- conflict_scanner.py: Nicht betroffen
- Game-Plugins: Nicht betroffen
- mod_groups.py: Nicht betroffen

## Deploy-Chain Vollstaendigkeit

_sync_separator_deploy_paths() wird aufgerufen in:
1. _apply_instance() (Zeile ~1071) — Initial-Deploy nach Instanz-Wechsel
2. _auto_redeploy_now() (Zeile ~1379) — Redeploy nach Mod-Aenderungen
3. _launch_game() (Zeile ~1500) — Pre-launch Deploy
4. _switch_profile() (Zeile ~3139) — Profil-Wechsel

Alle 4 Deploy-Pfade sind abgedeckt.

## Keine offenen Punkte

Issue #67 ist vollstaendig implementiert. Alle 13 Akzeptanz-Kriterien sind erfuellt.
