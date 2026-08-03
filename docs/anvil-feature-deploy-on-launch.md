# Analyse: Deploy nur beim Spielstart (MO2-Verhalten)

**Stand:** 03.08.2026 — reine Analyse, kein Code geändert.

## Ziel

| Situation | Spielordner |
|---|---|
| Anvil läuft, kein Spiel | **sauber** |
| Spiel über Steam/Heroic gestartet | **sauber** — läuft vanilla |
| Spiel über Anvil gestartet | Mods ausgerollt |
| Spiel beendet | wieder sauber |
| BG3 | Sonderweg über den Installer, bleibt |

Das entspricht der Nexus-Beschreibung (`docs/nexus-description-detailed-de.txt:22`):

> *„Spielverzeichnis bleibt sauber — Mods werden beim Start deployed, beim Beenden entfernt"*

und dem Gründungs-Commit `8fac595` (10.02.2026). Die Absicht wurde in 539 Commits nie geändert; es gibt keinen einzigen Commit zu VFS oder Overlay.

## Ist-Zustand: fünf Stellen rollen aus

| # | Stelle | Auslöser | Soll |
|---|---|---|---|
| 1 | `mainwindow.py:1952` `_apply_instance` | **jeder Anvil-Start**, jeder Instanzwechsel | entfernen |
| 2 | `mainwindow.py:2616` `_unlock_ui` | Spiel beendet — direkt **nach** dem Purge | entfernen |
| 3 | `mainwindow.py:4561` `_on_profile_changed` | Profilwechsel | entfernen |
| 4 | `mainwindow.py:2295` `_do_redeploy` | 500-ms-Timer nach Mod-Umschalten, dazu 6 direkte Aufrufer | **Entscheidung nötig** |
| 5 | `mainwindow.py:2526` `_predeploy_for_launch` | vor dem Spielstart | bleibt |

Nummer 2 ist der auffälligste Fehler:

```python
def _unlock_ui(self) -> None:
    self._game_running = False
    self._game_panel.silent_purge()      # räumt auf
    self._game_panel.silent_deploy()     # legt eine Zeile später alles zurück
```

Das Aufräumen nach dem Spiel wird sofort rückgängig gemacht.

Die sechs direkten Aufrufer von `_do_redeploy`: `_restore_backup:4337`, `_import_csv:4926`,
`_import_collection:5140`, `_ctx_rename_mod:6151`, `_ctx_reinstall_mod:6212`, `_ctx_remove_mods:6276`.

## Was am gefüllten Spielordner hängt

Ich habe alle Lesezugriffe auf `game_path` außerhalb des Deployers geprüft. Es sind **vier** Stellen — und drei davon gehören zusammen.

### A) Framework-Erkennung — `base_game.py:724-755`

```python
p = self._game_path / det_path
disabled = p.with_name(p.name + ".anvil-disabled")
if p.exists() or disabled.exists():
    installed = True
```

Liest ausschließlich den Spielordner. Deshalb steht der Deploy in `_apply_instance` **vor** der Erkennung — siehe Commit `8e539b3` (22.03.2026):

> *„Da Framework-Detection vor silent_deploy() lief, fehlte der Shim zum Erkennungszeitpunkt. Deploy-Reihenfolge korrigiert: erst deployen, dann prüfen."*

Der Start-Deploy ist also kein Versehen. Er trägt die Erkennung.

### B) Shim-Installation — `mainwindow.py:2668`

```python
already = any((game_path / f).exists() for f in companion.detect_installed)
```

Dieselbe Logik, anderer Ort.

### C) Framework an/aus — `mainwindow.py:7938-8006` ← **der harte Fall**

`_fw_toggle_active` schaltet ein Framework ab, indem es die **ausgerollte Datei im Spielordner umbenennt**:

```python
dst = f.with_name(f.name + framework_state.DISABLED_SUFFIX)
f.rename(dst)
```

Ohne Deployment gibt es diese Datei nicht. Der Mechanismus funktioniert dann gar nicht mehr.

**Nebenbefund:** Er funktioniert auch heute nur halb. `mod_deployer.py` kennt `.anvil-disabled` an keiner Stelle — der nächste Deploy legt die Datei ungefragt daneben. Das ist der Fehler, über den wir am 03.08. bei `okayyyyy3333.archive` gestolpert sind.

### D) Data-Reiter — `game_panel.py:2678` `_populate_data_tree`

Zeigt den Inhalt des Spielordners. Rein visuell. Nach dem Umbau zeigt er einen sauberen Ordner — was fachlich richtig ist, aber die Anzeige „REDmods liegen im Spiel" verliert ihren Sinn.

### Was **nicht** betroffen ist

Alle übrigen Zugriffe prüfen **Vanilla-Dateien**, die ohnehin da sind:
`redMod.exe`, `bg3_dx11`, `DWrite.dll`, sowie `SKSE/F4SE/SFSE/NVSE/MWSE/FOSE`-Binaries,
ModEngine und Script Merger in den Spiel-Plugins.

**Kein einziges Teilsystem außer der Erkennung braucht ausgerollte Mods.**

## Frameworks: gelten dieselben Regeln

Ja — auch Frameworks landen erst beim Spielstart im Spielordner. Alles andere wäre
inkonsequent: Ein Spielordner mit CET, RED4ext und `version.dll` ist nicht vanilla.

Daraus folgen drei Punkte, die über den bisherigen Plan hinausgehen.

### Der Purge muss die Kopien mitnehmen

`mod_deployer.py:637`:

```python
# Direct-install copies are intentionally left in place
if deploy_type == "copy":
    continue
```

Diese Ausnahme muss fallen, sonst bleiben die Frameworks dauerhaft liegen und der
Spielordner wird nie sauber. **Kopie statt Symlink bleibt richtig** — manche Loader
folgen unter Proton keinen Symlinks; das ist der Grund für `GameDirectInstallMods`
und bleibt unverändert.

### Handinstallierte Frameworks brauchen einen Rückfall

Sucht die Erkennung nur noch in `.mods/`, übersieht sie ein Framework, das der
Nutzer selbst in den Spielordner kopiert hat. Sie muss **beide** Orte prüfen:

| Fundort | Bedeutung |
|---|---|
| `.mods/<Mod>/…` | von Anvil verwaltet — ausrollen, aufräumen |
| Spielordner, ohne Deployment | handinstalliert — **nicht anfassen** |

Sonst installiert Anvil ein zweites Mal darüber oder meldet fälschlich „nicht installiert".

### Framework an/aus wird ein Schalter

Heute benennt `_fw_toggle_active` (`mainwindow.py:7938-8006`) die ausgerollte Datei
im Spielordner um. Ohne Deployment gibt es diese Datei nicht.

Stattdessen: Zustand in `framework_state.json` (`active`, ist bereits vorhanden),
und der Deployer überspringt inaktive Frameworks beim Ausrollen. Der Block mit
Entsperren bleibt unverändert — nur der Weg dahinter ändert sich.

Das behebt gleichzeitig den Fehler vom 03.08.: Beim Umbenennen legt der nächste
Deploy die Datei ungefragt daneben, weil `mod_deployer.py` `.anvil-disabled` nicht
kennt. Ein Schalter kann nicht überschrieben werden.

## Der Zielkonflikt — hier braucht es eine Entscheidung

Zwei Anforderungen widersprechen sich:

**(a)** „Wenn eine Mod aktiviert wird, ist sie deployt." — Auto-Redeploy nach 500 ms, Stelle 4.
**(b)** „Anvil offen → Spielordner sauber." — dann darf Stelle 4 nicht ausrollen.

Beides zusammen geht nicht. Zwei Wege:

| | Verhalten | Preis |
|---|---|---|
| **A** | Auto-Redeploy bleibt | Spielordner ist voll, solange Anvil offen ist. Das heutige Problem bleibt bestehen |
| **B** | Auto-Redeploy entfällt, Deploy nur beim Spielstart | Echtes MO2-Verhalten. „Aktiviert" heißt dann *vorgemerkt*, sichtbar nur in Anvil |

Bei **B** wird das Aktivieren einer Mod sofort wirksam — aber erst beim nächsten Spielstart sichtbar im Ordner. Das ist bei MO2 genauso.

## Umbauplan (für Weg B)

1. **Erkennung umstellen** — `get_installed_frameworks()` und die Shim-Prüfung lesen `.mods/`
   statt des Spielordners. `detect_installed`-Pfade sind spielrelativ und müssen auf die
   Mod-Ordner abgebildet werden. `GameDirectInstallMods` beachten.
2. **Framework an/aus entkoppeln** — nicht mehr im Spielordner umbenennen, sondern
   `framework_state.json` (`active`) führen; der Deployer überspringt inaktive Frameworks.
   Löst gleichzeitig den `.anvil-disabled`-Fehler.
3. **Deploy-Aufrufe 1–3 entfernen.**
4. **Stelle 4 nach Entscheidung** behandeln.
5. **Einmalige Bereinigung** — Direct-Install-Kopien werden vom Purge bewusst
   übersprungen (`mod_deployer.py:637`). Sie liegen also aus früheren Läufen im
   Spielordner und müssen einmalig entfernt werden.
6. **Data-Reiter** — entweder klar beschriften oder auf „würde ausgerollt" umstellen.

Schritt 2 ist der aufwendigste. Schritte 3–5 sind klein.

## Tests

Betroffen sind fünf Dateien:
`test_predeploy_launch.py`, `test_custom_deployer_paths.py`, `test_bodyslide_deployment.py`,
`test_grb_deployer.py`, `test_framework_download_status.py` — dazu
`test_plugin_load_order.py` und `test_game_ghostreconbreakpoint.py`, die
`get_installed_frameworks` bzw. `silent_deploy` benutzen.

Neu nötig: ein Test, der belegt, dass der Spielordner nach Anvil-Start **leer** bleibt,
und einer für Framework-Erkennung ohne Deployment.

## Risiken

- **Absturz während des Spiels** → kein Purge. Es gibt bereits eine Crash-Recovery
  (`_crash_recovery_purge`, Commit `bb4ff21`); die muss weiter greifen.
- **Spiel über Steam gestartet, während Anvil ausgerollt hat** → der Purge beim
  Spielende bleibt aus, weil Anvil das Spielende nicht mitbekommt. Offene Frage:
  Soll Anvil fremdgestartete Spiele erkennen?
- **Andere Spiele** — Bethesda, Witcher 3, GRB, RDR2 hängen an denselben Pfaden.
  Der Umbau betrifft alle Plugins, nicht nur Cyberpunk.
- **REDmod** — `redMod.exe deploy` schreibt nach `r6/cache/modded` in den Spielordner.
  Muss innerhalb des Spielstart-Deploys bleiben.
