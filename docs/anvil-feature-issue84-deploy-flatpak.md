# Feature: Issue #84 — Deploy-Chain-Lücken + Flatpak Host-Popen-Vervollständigung
Datum: 2026-04-23
Issue: https://github.com/Marc1326/Anvil-Organizer/issues/84

## Problem (Kurzfassung)

QA-Analyse am 2026-04-23 hat zwei strukturelle Mängel identifiziert:

**Block A — Deploy-Chain:**
- `_unlock_ui` purged das Deploy-Verzeichnis, ohne danach je wieder ein Deploy auszulösen. Zwischen Spielende und nächstem Start-/Wechsel-Event ist `.mods` leer.
- REDmod (`redMod.exe deploy`) läuft auf dem Game-Dir-Zustand **vor** Klick auf Start. Wenn der User zuvor Unlock gedrückt hat, läuft REDmod über ein leeres `/mods/`-Verzeichnis und erzeugt keine REDmod-Symlinks — das Spiel startet ohne REDmod-Inhalte.
- Sieben `except Exception: pass`-Blöcke in den .meta-Parser-Pfaden schlucken Corrupt-File-Fehler still; User sieht nie, warum Install-Tracking oder Hide-Status nicht mehr stimmt.

**Block B — Flatpak:**
- Commit `125c7f8` (9. April) hat den Proton-Launch auf `host_popen` umgestellt, Commit `608eae9` (heute) dito für die REDmod-Popens. Dabei sind vier strukturell identische Host-Tool-Aufrufe vergessen worden:
  - `mainwindow.py:1871` — Direct-Launch für Non-Steam-Games
  - `game_panel.py:1811` — `run_with_proton` (Bodyslide, FNIS, xEdit etc.)
  - `ba2_packer.py:182, 281` — `winepath` und `wine BSArch.exe`
  - `script_merger_dialog.py:826` — `kdiff3` via QProcess

Resultat im Flatpak: Game-Start für Non-Steam scheitert, Proton-Tool-Launch scheitert, BA2-Packing scheitert, KDiff3-Merge scheitert — alles still.

## User Stories

- Als User möchte ich nach dem Beenden eines Spiels ohne manuellen Wechsel wieder einen konsistenten Deploy-Zustand vorfinden, damit externe Tools (xEdit, LOOT, Script Merger) auf die deployten Dateien zugreifen können.
- Als Cyberpunk-User möchte ich, dass REDmod zuverlässig über ein gefülltes `/mods/`-Verzeichnis läuft — auch nach einem vorherigen Unlock-Klick.
- Als Flatpak-User möchte ich Non-Steam-Games starten, Proton-Tools aufrufen und BA2-Packer sowie KDiff3 benutzen können, ohne in der Sandbox hängen zu bleiben.
- Als Debugger möchte ich in Logs sehen, wenn eine .meta-Datei kaputt ist, statt stillen Install-Tracking-Verlust.

## Technische Planung

### Betroffene Dateien

| Datei | Zeile | Änderung |
|---|---|---|
| `anvil/widgets/game_panel.py` | ~1099 (vor `_run_redmod_deploy_then_launch`) | Vor REDmod-Deploy: `self.silent_deploy()` aufrufen, damit `redMod.exe` über ein gefülltes `/mods/` läuft (Punkt 1) |
| `anvil/mainwindow.py` | ~1908 (in `_unlock_ui`) | Nach `silent_purge()` direkt `silent_deploy()` nachziehen, damit das Deploy-Verzeichnis nicht leer zurückbleibt (Punkt 2) |
| `anvil/widgets/game_panel.py` | 2016-2017, 2053-2054, 2088-2089, 2420-2421, 2434-2435 | `except Exception: pass` → `except Exception as exc: print(f"[META] parse failed: {meta_path}: {exc}", flush=True)` (Punkt 3a) |
| `anvil/mainwindow.py` | 2365-2366, 2449-2450, 2496-2497, 5077-5078 | Dito: Logging in den stummen Meta-Parser-Excepts (Punkt 3b) |
| `anvil/mainwindow.py` | 1871 | `subprocess.Popen([binary_path], cwd=…, env=…)` → `host_popen([binary_path], cwd=…, env=…)` (Punkt 4) |
| `anvil/mainwindow.py` | Import-Block | `from anvil.core.subprocess_env import clean_subprocess_env` ergänzen um `host_popen` |
| `anvil/widgets/game_panel.py` | 1811 (in `run_with_proton`) | `subprocess.Popen(cmd, cwd=cwd, env=env, …)` → `host_popen(cmd, cwd=cwd, env=env, …)` (Punkt 5) |
| `anvil/core/ba2_packer.py` | 182 (`_to_wine_path`) | `subprocess.run(["winepath", "-w", …], capture_output=True, text=True, timeout=5, env=env)` → `host_popen(…).communicate(timeout=5)` inkl. Rückgabe-Parsing (Punkt 6a) |
| `anvil/core/ba2_packer.py` | 281 (`_pack_ba2`) | `subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)` → `host_popen(…).communicate(timeout=300)` inkl. Returncode/Stderr (Punkt 6b) |
| `anvil/core/ba2_packer.py` | Import-Block (Z.27) | `clean_env` um `host_popen` ergänzen |
| `anvil/widgets/script_merger_dialog.py` | 820-826 | Wenn `is_flatpak()`: KDiff3 via `host_popen([kdiff3, *args])` (detached) starten und Exit-Code über Polling/Thread an `_on_kdiff3_finished` weiterreichen. **Alternative:** QProcess beibehalten und den `kdiff3_path` via `host_which` aufgelöst weitergeben, dazu prüfen, ob `flatpak-spawn --host` als `program` mit `["--host", kdiff3, *args]` als `args` funktioniert (Punkt 7). Dev entscheidet pragmatisch — wenn QProcess nicht sauber wrapbar ist, wird die Stelle mit Code-Kommentar `# NOTE: KDiff3 läuft im Flatpak aktuell nicht, Host-Call via QProcess nicht wrapbar` als bewusste Ausnahme markiert und Issue #84-Followup angelegt |
| `anvil/widgets/script_merger_dialog.py` | Import-Block | Ggf. `from anvil.core.subprocess_env import is_flatpak, host_popen, host_which` ergänzen |

### Signal-Flow / Aufrufreihenfolge

**Vorher (buggy):**
```
User klickt Unlock
 → _unlock_ui
   → silent_purge
   → (Verzeichnis leer, kein Deploy bis zum nächsten Event)

User klickt Start (Cyberpunk, vorher Unlock)
 → _on_start_clicked
   → _needs_redmod_deploy = True
   → _run_redmod_deploy_then_launch
     → redMod.exe deploy  ← läuft auf LEEREM /mods/
   → _on_redmod_finished → _do_launch
   → start_requested.emit
 → mainwindow._on_start_game
   → silent_purge
   → silent_deploy    ← Symlinks jetzt zu spät, REDmod ist durch
   → subprocess.Popen(binary)
```

**Nachher (fix):**
```
User klickt Unlock
 → _unlock_ui
   → silent_purge
   → silent_deploy    ← NEU: Verzeichnis sofort wieder konsistent

User klickt Start (Cyberpunk)
 → _on_start_clicked
   → _needs_redmod_deploy = True
   → silent_deploy    ← NEU: REDmod läuft über gefülltes /mods/
   → _run_redmod_deploy_then_launch
     → redMod.exe deploy
   → _on_redmod_finished → _do_launch
   → start_requested.emit
 → mainwindow._on_start_game
   → silent_purge
   → silent_deploy
   → host_popen(binary)   ← NEU: Flatpak-fähig
```

**Flatpak-Wrapping:**
```
Innerhalb Flatpak-Sandbox:
  host_popen(cmd, env=env)
   → ["flatpak-spawn", "--host",
      "--env=KEY=VALUE", …, *cmd]
   → subprocess.Popen(…)

Nicht-Flatpak:
  host_popen(cmd, env=env)
   → subprocess.Popen(cmd, env=env)
```

### MO2-Vergleich

MO2 arbeitet mit Virtual File System (USVFS) und hat per Design keinen „Purge"-Begriff — Deploy ist transparent. Anvil's Symlink-basierter Deploy braucht deshalb eine explizite Purge→Deploy-Sequenz. MO2 kennt das Problem von `_unlock_ui` daher nicht, weil der VFS-Zustand prozessgebunden ist. Die Anvil-Lösung ist korrekt: Nach einem Purge sofort wieder deployen, außer beim App-Close und Crash-Recovery.

Für Flatpak hat MO2 keine Referenz (MO2 läuft nativ unter Wine). Die `host_popen`-Schicht ist Anvil-eigene Infrastruktur (Commit 125c7f8).

## Verwandte Funktionen (geprüft)

- **`_on_start_game` (mainwindow.py:1856-1868)** → kein Fix nötig. Macht bereits purge + deploy direkt vor `subprocess.Popen`. Der Fix in `host_popen` (Punkt 4) ist hier die Abrundung.
- **`_do_redeploy` (mainwindow.py:1667-1670)** → kein Fix nötig. `silent_purge` direkt gefolgt von `silent_deploy_fast`.
- **`_apply_instance` (mainwindow.py:1339)** / **`_on_profile_changed` (mainwindow.py:3734-3737)** / **`_teardown_current_instance` (mainwindow.py:1080)** → kein Fix nötig. Alle Purge-Calls haben in ihrer Aufrufkette ein folgendes Deploy.
- **`closeEvent` (mainwindow.py:5970-5975)** → kein Fix nötig (App-Ende, gewolltes Purge ohne Deploy).
- **`_crash_recovery_purge` (mainwindow.py:1016-1037)** → kein Fix nötig (App-Start, gewolltes Purge ohne Deploy).
- **`_launch_via_steam` (game_panel.py:1653)** → bereits `host_popen` seit 125c7f8.
- **`_launch_via_proton` (game_panel.py:1756)** → bereits `host_popen` seit 125c7f8.
- **REDmod-Auto/Manual (game_panel.py:1276, 1566)** → bereits `host_popen` seit 608eae9.
- **LOOT-Runner (core/loot/loot_runner.py)** → eigenes flatpak-spawn-Wrapping, bereits OK.
- **`secure_storage.py:47` dbus-send / `update_checker.py:27,135` git/pip / `nxm_handler.py:116` xdg-mime / `settings_dialog.py:1145` QProcess-Restart** → **NICHT in dieser Issue adressiert** (P3/Komfort laut qa-agent-2.md). Bleiben für Followup.
- **`bg3_mod_installer.py:1374, 1388` / `mod_installer.py:490, 514` unrar/7z** → NICHT adressiert (kein BG3-Code laut CLAUDE.md, und 7z ist in KDE-Runtime vorhanden).

## Bereiche die NICHT angefasst werden

- **BG3**-Code (alles unter `anvil/plugins/games/bg3.py`, `anvil/core/bg3_mod_installer.py`) — Projektregel.
- **REDmod-Shim / Cover-Bilder / Icons** — Projektregel.
- **i18n / Locale-Dateien** — keine neuen User-sichtbaren Strings in diesem Feature.
- **UI-Layout / Styling** — keine Widget-Änderungen.
- **Refactoring** — nur die Minimal-Änderungen der sieben Punkte.
- **Dead-Code-Removal** — ausserhalb Scope.
- **P3-Flatpak-Komfort-Punkte** (dbus-send, git, pip, xdg-mime, QProcess-Restart) — separate Followup-Issues.

## Akzeptanz-Kriterien

Alle Kriterien sind mit `grep -n`, `diff`, `ls` oder einem Log-Check auf `/tmp/anvil-deploy.log` verifizierbar.

- [ ] **Punkt 1 — REDmod-Pre-Deploy:** `grep -n "silent_deploy" anvil/widgets/game_panel.py` zeigt in `_on_start_clicked` vor dem Aufruf `_run_redmod_deploy_then_launch` einen `self.silent_deploy()`-Call. Der Aufruf steht zwischen Zeile ~1099 (nach `print("[START] _needs_redmod_deploy=…")`) und Zeile ~1103 (Aufruf `_run_redmod_deploy_then_launch`).
- [ ] **Punkt 1 — Funktional:** Wenn User bei Cyberpunk auf Unlock klickt und dann direkt Start drückt, erscheint im Log die Sequenz `[DEPLOY] … → [REDmod] deploy starting`, und `.mods/` enthält während des REDmod-Runs Symlinks (nicht leer). Nachweis: `ls -la .mods/` kurz nach Klick (oder `/tmp/anvil-deploy.log` zeigt Deploy-Zeile VOR REDmod-Zeile).
- [ ] **Punkt 2 — Unlock-Post-Deploy:** `grep -n "silent_deploy\|silent_purge" anvil/mainwindow.py` zeigt in `_unlock_ui` (Z.1905-1913) zwei aufeinanderfolgende Aufrufe: `silent_purge()` **und** direkt danach `silent_deploy()`.
- [ ] **Punkt 2 — Funktional:** Wenn User ein Spiel beendet (oder Unlock-Button klickt), enthält `.mods/` nach Rückkehr der UI weiterhin die erwarteten Symlinks (nicht leer). Nachweis: `ls .mods/ | wc -l` vor und nach Unlock gibt dieselbe Zahl zurück.
- [ ] **Punkt 3 — Meta-Parse-Logging (game_panel):** `grep -c 'except Exception: pass' anvil/widgets/game_panel.py` gibt 0 (oder zumindest weniger) als vorher. Jeder der fünf bezeichneten Blöcke (Zeilen 2016, 2053, 2088, 2420, 2434) endet mit einem `print("[META] parse failed: …", flush=True)` statt `pass`.
- [ ] **Punkt 3 — Meta-Parse-Logging (mainwindow):** In den vier mainwindow-Blöcken (Z.2365, 2449, 2496, 5077) steht je ein `print("[META] parse failed: …", flush=True)`. Nachweis: `grep -n "\[META\] parse failed" anvil/mainwindow.py` liefert ≥ 4 Treffer.
- [ ] **Punkt 3 — Funktional:** Eine absichtlich kaputte `.meta` (`echo "[[[malformed" > foo.zip.meta`) führt beim nächsten Refresh der Download-Liste zu einer `[META] parse failed:`-Zeile in der Console, ohne dass die App abstürzt oder die Download-Liste leer bleibt.
- [ ] **Punkt 4 — Direct-Launch Flatpak:** `grep -n "subprocess.Popen" anvil/mainwindow.py` findet den Aufruf in Z.~1871 **nicht mehr**; dafür taucht dort `host_popen([binary_path], …)` auf. `grep -n "host_popen" anvil/mainwindow.py` liefert mindestens einen Treffer in `_on_start_game`.
- [ ] **Punkt 4 — Import:** `grep -n "from anvil.core.subprocess_env" anvil/mainwindow.py` zeigt `host_popen` im Import.
- [ ] **Punkt 5 — `run_with_proton`:** In `anvil/widgets/game_panel.py:1811` steht `host_popen(cmd, cwd=cwd, env=env, …)` statt `subprocess.Popen`. Nachweis: `grep -n "subprocess.Popen" anvil/widgets/game_panel.py` liefert **keinen** Treffer in `run_with_proton` (Zeilen 1790-1820).
- [ ] **Punkt 5 — Funktional (Nicht-Flatpak):** Proton-Tool-Launch (Bodyslide, FNIS, xEdit) startet in einer lokalen Dev-Umgebung weiterhin fehlerfrei (kein `OSError`).
- [ ] **Punkt 6 — ba2_packer:** `grep -n "subprocess.run" anvil/core/ba2_packer.py` liefert 0 Treffer für die Zeilen 182 und 281. Beide Stellen nutzen stattdessen `host_popen([...], ...).communicate(timeout=…)` und behalten die bestehende `returncode`-Prüfung und stderr/stdout-Aggregation bei.
- [ ] **Punkt 6 — Import:** `grep -n "from anvil.core.subprocess_env" anvil/core/ba2_packer.py` zeigt sowohl `clean_env` als auch `host_popen`.
- [ ] **Punkt 6 — Funktional (Nicht-Flatpak):** `_to_wine_path(Path("/tmp/test"), env)` liefert weiterhin einen Windows-Pfad-String oder den `Z:`-Fallback; das Pack-Ergebnis eines Testmods ist unverändert.
- [ ] **Punkt 7 — KDiff3:** Entweder `anvil/widgets/script_merger_dialog.py:826` startet KDiff3 über `host_popen` / einen flatpak-spawn-gewrappten Aufruf, ODER die Stelle hat einen Code-Kommentar `# NOTE: KDiff3 QProcess-Call ist in Flatpak aktuell nicht funktional — siehe Issue #84 Followup`. `grep -n "KDiff3\|kdiff3" anvil/widgets/script_merger_dialog.py` zeigt den Kommentar oder den neuen `host_popen`-Call.
- [ ] **Regression — modlist.txt-Reihenfolge:** Nach Start → Stopp → Unlock → erneut Start bleibt die Reihenfolge in `profiles/<p>/modlist.txt` identisch zur GUI-Reihenfolge (kein Scrambling durch das doppelte Deploy). Nachweis: `diff <(git show HEAD:…) <(cat …)` zeigt keine Änderung durch den Fix.
- [ ] **Regression — keine neuen Syntax-Fehler:** `python -m py_compile anvil/mainwindow.py anvil/widgets/game_panel.py anvil/core/ba2_packer.py anvil/widgets/script_merger_dialog.py` läuft ohne Exception durch.
- [ ] **Regression — Locale-Dateien unverändert:** `git diff --stat anvil/locales/` ist leer (keine tr()-Keys eingeführt).
- [ ] **`./restart.sh` startet ohne Fehler** (keine Traceback-/ImportError/NameError-Zeilen im Log, QTabBar-Alignment-Warnings dürfen ignoriert werden).

## Hinweise für Dev

- `host_popen` nutzt `subprocess.Popen`. Für `subprocess.run`-artige Aufrufe in `ba2_packer.py` muss der Dev via `proc = host_popen(...)` + `stdout, stderr = proc.communicate(timeout=300)` + `proc.returncode` umbauen. `TimeoutExpired` und `OSError` Exceptions werden 1:1 beibehalten.
- Beim `_to_wine_path`-Fix muss `capture_output=True, text=True` durch `stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True` ersetzt werden (Popen-kompatibel).
- Der Import `subprocess` in `ba2_packer.py` bleibt, weil `TimeoutExpired`-Exception-Klasse davon kommt.
- Das doppelte `silent_deploy` in `_unlock_ui` und in `_on_start_clicked` vor REDmod ist **gewollt** — die Kosten sind niedrig (Symlink-Recreation), der Nutzen ist der garantierte Zustand.
- KDiff3-Wrapping (Punkt 7): Die saubere Lösung ist QProcess mit `setProgram("flatpak-spawn")` und `setArguments(["--host", kdiff3_resolved, *args])` bei `is_flatpak()`. Falls das funktioniert, muss der `finished`-Handler nichts wissen. Alternative Pragmatik: Mit Code-Kommentar als bekannte Einschränkung markieren — dann muss Issue-Followup angelegt werden.

## Hinweise für QA (4-Agent-Review)

- **Agent 1 (Code-Review):** Alle 7 Änderungen auf Syntax/Typing/Logik prüfen. Besonders `ba2_packer.py` — das Popen-Rewrite der `subprocess.run`-Stellen ist nicht trivial (communicate + returncode + Timeout).
- **Agent 2 (Signal/Slot):** `_unlock_ui` und `_on_start_clicked` signalfrei prüfen — die Fixes dürfen keine Signal-Rekursion auslösen. `silent_deploy()` darf nicht erneut `_unlock_ui` triggern.
- **Agent 3 (Architektur + MO2):** Sind die Fixes konsistent zu den bestehenden host_popen-Pfaden (125c7f8, 608eae9)? Gibt es einen neuen Path, der übersehen wurde?
- **Agent 4 (Konsolidierung):** Prüft Akzeptanzliste Punkt-für-Punkt, inkl. `./restart.sh`-Check.
