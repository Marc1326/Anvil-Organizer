# Codex Review 2 — Issue #55 (SFSE Proton Shim)
Datum: 2026-03-22
Reviewer: Agent 2 (Deploy-Flow, Plugin-Integration, Seiteneffekte)

## Gepruefte Dateien
- `anvil/plugins/games/game_starfield.py` (NEU, untracked)
- `anvil/data/shims/starfield/version.dll` (NEU, untracked)
- `anvil/widgets/game_panel.py` — Methoden: `silent_deploy`, `_deploy_proton_shims`, `_launch_via_proton`, `_launch_via_steam`
- `anvil/plugins/games/game_fallout4.py` (Referenz)
- `anvil/plugins/base_game.py` — `ProtonShimFiles`, `get_proton_env_overrides`, `get_installed_frameworks`
- `anvil/core/mod_deployer.py` — Purge-Logik fuer `shim_copy`

## Architektur-Regeln (7/7 bestanden)
1. Mod-Dateien werden NICHT direkt ins Game-Dir kopiert (nur Symlinks) — OK (Shim ist Framework-artig, `shim_copy` Typ)
2. Ordnerstruktur in `.mods/` wird NICHT veraendert — OK (Shim liegt in `anvil/data/shims/`, nicht in `.mods/`)
3. Frameworks landen NICHT in `.mods/` oder modlist.txt — OK (Shim wird per `_deploy_proton_shims` direkt kopiert)
4. Rename/Delete aktualisiert active_mods.json — Nicht relevant (kein Rename/Delete)
5. Globale API wird verwendet — Nicht relevant
6. MO2-Referenz konsultiert — OK (usvfsconnector.cpp gelesen)
7. Architektur-Doku gelesen — OK (ARCHITEKTUR.md gelesen)

## Checklisten-Pruefung

### Anvil Plugin (game_starfield.py)
- [x] 1. Steam ID 1716740 korrekt → `GameSteamId = 1716740`
- [x] 2. Game-Dir, Documents-Dir, Saves-Dir korrekt aufgeloest via `protonPrefix()` + `_WIN_DOCUMENTS` / `_WIN_SAVES`
- [x] 3. 19 Default-Kategorien vorhanden (inkl. Ships id=4, Outposts id=5) — Verifiziert per Python-Import
- [x] 4. Deploy: Wenn `sfse_loader.exe` existiert → `version.dll` wird kopiert. Logik: `get_installed_frameworks()` prueft `detect_installed=["sfse_loader.exe"]`, `any_fw_installed` steuert `_deploy_proton_shims(["version.dll"])`
- [x] 5. Deploy: Wenn `sfse_loader.exe` NICHT existiert → `any_fw_installed=False` → Shims werden NICHT deployed
- [x] 6. Proton-Start: `get_proton_env_overrides()` prueft `(game_path / "version.dll").exists()` → `{"WINEDLLOVERRIDES": "version=n,b"}`. In `_launch_via_proton` Zeile 1148-1154 korrekt in Env eingesetzt
- [x] 7. Proton-Start: Wenn version.dll NICHT existiert → `get_proton_env_overrides()` gibt `{}` zurueck → WINEDLLOVERRIDES wird NICHT gesetzt
- [x] 8. Purge: Manifest-Eintrag hat `type: "shim_copy"`, `mod: "__proton_shim__"`. In `mod_deployer.py` Zeile 438-444 wird `shim_copy` beim Purge per `link_path.unlink(missing_ok=True)` entfernt

### SFSE Proton Shim DLL
- [x] 9. version.dll existiert in `anvil/data/shims/starfield/version.dll`
- [x] 10. Export-Table zeigt genau 3 Funktionen: `GetFileVersionInfoA`, `GetFileVersionInfoSizeA`, `VerQueryValueA`
- [x] 11. DLL-Dependencies: nur System-DLLs (`KERNEL32.dll`, `api-ms-win-crt-*`) — keine MinGW-Runtime
- [x] 12. `file` zeigt: `PE32+ executable for MS Windows 5.02 (DLL), x86-64` (aequivalent zu erwartetem Output)
- [x] 13. Groesse: 112651 Bytes = ~110 KB < 200 KB

### Keine Seiteneffekte
- [x] 14. `game_fallout4.py` hat KEINE Aenderungen (`git diff` leer). F4SE Shim-Deploy bleibt identisch
- [x] 15. Andere Spiele: `game_cyberpunk.py`, `game_bg3.py`, `game_rdr2.py`, `game_witcher3.py` haben KEINE Aenderungen
- [x] 16. `_wip/game_starfield.py` existiert NICHT mehr — korrekt verschoben nach `anvil/plugins/games/`
- [x] 17. Python-Import erfolgreich, keine Fehler — restart.sh wurde nicht getestet da keine geaenderten tracked Dateien

## Pfad-Korrektheit
- `GameShortName = "Starfield"` → `.lower()` = `"starfield"` → Shim-Pfad: `anvil/data/shims/starfield/` — KORREKT
- `ProtonShimFiles = ["version.dll"]` — passt zu `anvil/data/shims/starfield/version.dll` — KORREKT
- `get_proton_env_overrides()` prueft `self._game_path / "version.dll"` (Game-Root) — KORREKT (Shim wird nach Game-Root kopiert)

## Deploy-Flow Analyse
```
silent_deploy()
  → deployer.deploy()           # Normale Mod-Symlinks
  → BA2 Packing                 # Falls NeedsBa2Packing (Starfield: nein)
  → plugins.txt                 # Falls has_plugins_txt (Starfield: TODO)
  → _deploy_proton_shims()      # Nur wenn Framework installiert (sfse_loader.exe)
    → shim_dir = anvil/data/shims/starfield/
    → shutil.copy2(src, game_path / "version.dll")
    → Manifest-Eintrag: type="shim_copy", mod="__proton_shim__"
  → _apply_proton_dll_overrides()  # GameProtonDllOverrides (Starfield: leer)
```

## Findings

### [LOW] Fehlender Locale-Key: game_panel.shim_steam_hint
- Datei: `anvil/widgets/game_panel.py:1087`
- Problem: Der Key `game_panel.shim_steam_hint` wird verwendet, existiert aber in keiner der 6 Locale-Dateien. Wenn ein User Starfield (oder Fallout 4) ueber Steam-Launch startet und ein Shim vorhanden ist, wuerde statt einer lesbaren Meldung der rohe Key angezeigt.
- Hinweis: Dies ist ein VORBESTEHENDER Bug aus dem F4SE-Shim-Feature (Commit 8fc47c3), NICHT neu durch diesen PR.
- Fix: Key `game_panel.shim_steam_hint` in allen 6 Locale-Dateien ergaenzen.

## Ergebnis

**ACCEPTED**

Alle 17 Checklisten-Punkte bestanden. Keine CRITICAL, HIGH oder MEDIUM Findings.
Der einzige LOW-Fund (fehlender Locale-Key) ist vorbestehend und blockiert diesen PR nicht.

Das Starfield Plugin folgt exakt dem gleichen Pattern wie das Fallout 4 Plugin:
- Gleiche `ProtonShimFiles`-Mechanik
- Gleiche `get_proton_env_overrides()`-Logik
- Gleiche `get_installed_frameworks()`-Pruefung vor Shim-Deploy
- Gleiche Manifest-Eintraege fuer Purge

Keine Seiteneffekte auf andere Spiele nachweisbar.
