# Nachprüfung — Anvil löscht Mods bei laufendem Spiel (Flatpak)
Datum: 2026-08-06
Prüfstand: uncommitted Änderungen auf `main` (d174cd6 + Arbeitsverzeichnis)
Geprüfte Dateien: `anvil/core/game_process.py` (neu), `anvil/core/debug_log.py` (neu),
`anvil/mainwindow.py`, `anvil/widgets/game_panel.py`, `anvil/main.py`,
`anvil/core/diagnostics.py`, `packaging/flatpak/*.yml`, `tests/test_predeploy_launch.py`

---

## 0. Was empirisch belegt wurde (echte Sandbox)

Alle Messungen in `flatpak run --command=python3 com.github.Marc1326.AnvilOrganizer`,
neuer Code aus `/home/mob/Projekte/Anvil Organizer` per `sys.path` hineingereicht.

| Test | Ergebnis |
|---|---|
| PIDs in `/proc` innerhalb der Sandbox | **4** — die Ursache des Vorfalls ist reproduziert |
| `scan_proc_for_game(None, "steamwebhelper")` lokal | `None` (blind) |
| `find_game_process(None, "steamwebhelper")` (Host) | `(22491, True)` in **25 ms** |
| `scan_proc_for_game("999999", None)` lokal, Stand-in `env SteamAppId=999999 sleep` | `None` |
| `find_game_process("999999", None)` (Host) | `(1391889, True)` — **exakt die Host-PID des Stand-ins** |
| `find_game_process` ohne `flatpak-spawn` im PATH | `(None, False)` → *unknown*, nie „gestoppt" |
| Host-`python3` kaputt (`sys.exit(7)`) → ps-Fallback | `22491, True` — Fallback greift |
| Host-`python3` kaputt + nur AppId (kein Binärname) | `(None, False)` → sicher *unknown* |
| Kein Ziel gesetzt | `(None, True)` → zuverlässig „gestoppt" |

**Fazit:** Der Kern des Fixes — Prozesssuche auf dem Host statt in der Sandbox —
funktioniert nachweislich, beide Erkennungswege (SteamAppId/environ und
Binärname/cmdline) und beide Fallbacks. Die ursprüngliche Ursache ist behoben.

Nebenbefund aus dem Test: Der Host-Scan sieht **auch die Sandbox-Prozesse und jede
beliebige Host-Kommandozeile**. Mein eigenes Test-Shell wurde als „Spiel" erkannt,
weil der Suchbegriff in seiner Kommandozeile stand. Falsch-Positive gehen in die
sichere Richtung (nicht löschen), erzeugen aber das Aussperr-Risiko aus Punkt 3.

Testsuite: `297 passed, 1 skipped`. Der Segfault in
`tests/test_base_migration_dialog.py` tritt **auch ohne die Änderungen** auf
(mit `git stash` verifiziert) — nicht durch diesen Fix verursacht.

Übersetzungen: `dialog.unlock_purge_title`, `dialog.unlock_purge_text`,
`error.game_already_running` in allen 7 Locales vorhanden und übersetzt.
(`storage.error_game_running` ist in es/fr/it/pt/ru weiter englisch — vorbestehend.)

---

## 1. Vollständige Inventur aller `silent_purge()`-Aufrufer

| # | Stelle | Guard | Bewertung |
|---|---|---|---|
| 1 | `mainwindow.py:1047` `_schedule_base_directory_migration` | Eingang `:1016` `_game_running or game_state()==RUNNING` | ⚠️ intent-konform, Restweg siehe F-3 |
| 2 | `mainwindow.py:1128` `_start_next_storage_instance` | Eingang `:1078`, gleiche Logik | ⚠️ intent-konform, Restweg siehe F-3 |
| 3 | `mainwindow.py:1633` `_teardown_current_instance` | `_game_running or is_game_running()` | ✅ korrekt (unbekannt = nicht löschen) |
| 4 | `mainwindow.py:2314` `_do_redeploy` | `_game_running or is_game_running()` | ✅ korrekt |
| 5 | `mainwindow.py:2588` `_predeploy_for_launch` | `game_state()==RUNNING` → Start abgelehnt | ✅ korrekt (Asymmetrie gewollt) |
| 6 | `mainwindow.py:2744` `_purge_after_game` (Helper) | Aufrufer: `_unlock_ui` (nur `stopped and not is_game_running()`) und `_on_unlock_clicked` (nur nach ausdrücklichem „Ja") | ✅ korrekt |
| 7 | `mainwindow.py:4706` Profilwechsel | `_game_running or is_game_running()` | ✅ korrekt |
| 8 | `mainwindow.py:7095` `closeEvent` | `_game_running or is_game_running()` | ✅ korrekt |

**Die vier gemeldeten Pfade sind alle abgesichert.** Die Asymmetrie
(`is_game_running()` bei Aufräumpfaden, `game_state()==RUNNING` bei Start/Migration)
ist an jeder Stelle so umgesetzt wie beschrieben.

### Purge-Wege, die NICHT über `silent_purge()` laufen

| # | Stelle | Guard | Bewertung |
|---|---|---|---|
| 9 | **`mainwindow.py:1550-1585` `_crash_recovery_purge()`** (aufgerufen `:1519` beim App-Start) | **keiner** | ❌ **HIGH — siehe F-1** |
| 10 | `mod_deployer.py:331` — `deploy()` purgt intern („clean slate") | erbt den Guard des Aufrufers | ⚠️ macht **jeden** `silent_deploy()` zu einem Purge |
| 11 | `game_panel.py:1947` GRB-Forge `silent_deploy()` in `_on_start_clicked` | keiner | ⚠️ kein „Spiel läuft"-Abbruch (F-4) |
| 12 | `game_panel.py:1963` REDmod-Pfad `silent_deploy()` (**Cyberpunk!**) | keiner, und **kein** `_predeploy_hook` | ⚠️ kein „Spiel läuft"-Abbruch (F-4) |
| 13 | `mod_deployer.py:940` `remove_orphaned_links()` — löscht jeden Symlink im Spielordner, der nach `.mods/` zeigt, ohne Manifest | nur über #9 erreichbar | ❌ Teil von F-1 |
| 14 | `mainwindow.py:6416` `_ctx_remove_mods` → `shutil.rmtree(mod_path)` | UI-Lock (umgehbar nach „Entsperren") | LOW — zerstört die Symlink-Ziele des laufenden Spiels |

---

## 2. Befunde

### [HIGH] F-1 — `_crash_recovery_purge()` beim App-Start ist ungeschützt

- Datei: `anvil/mainwindow.py:1519` → `:1550-1585`
- Problem: Beim Start läuft über **alle** Instanzen `deployer.purge()` +
  `remove_orphaned_links()`. Kein Check, ob ein Spiel läuft — und er *kann* auch
  keinen machen, weil das Watch-Ziel (`_watch_binary`/`_watch_app_id`) **nirgends
  persistiert** wird. Nach einem Anvil-Neustart ist `_watch_binary == ""`, also
  liefert `game_state()` unbedingt `GAME_STOPPED` und **sämtliche neuen Guards
  (#3, #4, #7, #8) sind wirkungslos**.
- Der Fix verschärft das: `closeEvent` behält das Deployment jetzt bewusst
  („The next start cleans up instead"). Genau dieser „next start" räumt aber
  ungeprüft auf.
- Reproduzierbarer Ablauf: Spiel starten → Anvil schließen (Deployment bleibt,
  by design) → Anvil erneut öffnen, während das Spiel läuft → Mods weg.
  Ebenso: nach dem Anvil-Neustart eine Mod an-/abschalten → `_do_redeploy` →
  `is_game_running()` = False (Ziel unbekannt) → Purge.
- Fix: Watch-Ziel (`app_id`, `binary`, Instanz) in einer Datei unter
  `anvil_base_paths().base` ablegen, beim Start vor `_crash_recovery_purge()`
  lesen und `find_game_process()` befragen; nur purgen, wenn zuverlässig
  „gestoppt". Datei löschen, sobald `_clear_watch_target()` greift.

### [HIGH] F-2 — Watcher-Timeout löscht trotzdem: `_clear_watch_target()` entwertet die Nachprüfung

- Datei: `anvil/widgets/game_panel.py:2831-2838` und `:2744-2749`
- Problem: Im Zweig „Prozess nie aufgetaucht" (120 s) wird bei *zuverlässiger*
  Suche `self._clear_watch_target()` aufgerufen **bevor** `game_stopped.emit(True)`
  gesendet wird. `_unlock_ui(True)` fragt danach `is_game_running()` — das trifft
  auf `not self._watch_binary and not self._watch_app_id` und liefert
  bedingungslos `GAME_STOPPED`. Es wird also **immer** gepurgt.
- Belegt (ausgeführt):
  ```
  vorher  game_state: running is_running: True
  nach _clear_watch_target (Spiel laeuft weiter!): stopped is_running: False
  ```
  (Lookup gab durchgehend `(4242, True)` zurück, das „Spiel" lief also.)
- Damit ist der Kommentar bei `_GAME_APPEAR_TIMEOUT` (`game_panel.py:2734`)
  sachlich falsch: „Running out is not dangerous any more: MainWindow re-checks
  before removing anything" — die Nachprüfung kann nach dem Clear nichts mehr finden.
- Realistischer Schaden: Cyberpunk über Steam mit Shader-Precache oder
  Erst-Anlage des Proton-Prefix braucht regelmäßig **mehr als 120 s**, bis
  `Cyberpunk2077.exe` existiert. Dann tritt exakt der gemeldete Vorfall wieder
  ein — diesmal mit voll funktionierender Prozesssuche.
- Fix: Im Timeout-Zweig **nicht** clearen und `game_stopped.emit(False)` senden
  (das Deployment bleibt liegen, die UI entsperrt trotzdem; aufgeräumt wird beim
  nächsten Spielstart). Alternativ: `_GAME_APPEAR_TIMEOUT` deutlich anheben und
  die Nachprüfung in `_unlock_ui` wieder wirksam machen.
- Zusatz: `blind_since` wird bei jeder zuverlässigen Runde auf `None` gesetzt.
  War die Suche 119 s blind und in der letzten Sekunde erfolgreich, gilt der
  Lauf als „zuverlässig nie aufgetaucht" → clear + purge.

### [MEDIUM] F-3 — Storage-/Basisverzeichnis-Migration purgt bei „unbekannt"

- Datei: `anvil/mainwindow.py:1016`, `:1047`, `:1078`, `:1128`
- Problem: Der Guard prüft `game_state() == GAME_RUNNING`. Bei kaputtem Lookup
  ist der Zustand `UNKNOWN` → die Migration läuft und purgt **jede** Instanz.
  Erreichbar, sobald der Nutzer über „Entsperren → Nein" die UI freigegeben hat,
  während das Spiel weiterläuft.
- Bewertung: Die Absicht (kein dauerhaftes Aussperren) trägt hier weniger als
  bei `_predeploy_for_launch`: Eine Datenmigration ist kein Vorgang, den man
  „jetzt sofort" braucht, aber ein Vorgang, der bei laufendem Spiel garantiert
  Schaden anrichtet (Quelle wird verschoben, Symlinks laufen ins Leere).
- Fix: Hier `is_game_running()` verwenden (unbekannt = blockieren) und den
  Nutzer die Meldung wegklicken lassen — er kann die Migration jederzeit
  wiederholen. Zusätzlich den Guard vor jeder Schleifen-Iteration prüfen,
  nicht nur einmal am Eingang.

### [MEDIUM] F-4 — REDmod- und GRB-Startpfad kennen den „Spiel läuft"-Abbruch nicht

- Datei: `anvil/widgets/game_panel.py:1946-1965`
- Problem: Beide Zweige verlassen `_on_start_clicked` **vor** dem
  `_predeploy_hook`. Sie rufen stattdessen direkt `silent_deploy()` auf, und
  `ModDeployer.deploy()` purgt intern (`mod_deployer.py:329-338`). Es gibt dort
  weder die neue Abfrage `game_state() == GAME_RUNNING` noch einen Purge-Guard.
- Betrifft ausgerechnet **Cyberpunk** (REDmod), also das Spiel des Vorfalls,
  sobald REDmod-Mods installiert sind.
- Der Schaden ist kleiner als beim reinen Purge (es wird sofort neu deployed),
  aber ein zweiter Start bei laufendem Spiel reißt die Links kurzzeitig weg.
- Fix: In `_on_start_clicked` **ganz oben** einmal den Predeploy-Hook bzw. eine
  eigene `game_state() == GAME_RUNNING`-Abfrage setzen, bevor in die
  REDmod-/GRB-Zweige verzweigt wird.

### [MEDIUM] F-5 — Kein Ausweg aus einem falschen „Spiel läuft"

- Datei: `anvil/mainwindow.py:2574-2581`
- Problem: Meldet die Suche `GAME_RUNNING`, wird der Start hart abgelehnt —
  ohne „Trotzdem starten". Der Host-Scan trifft aber auf **jede** Host- oder
  Sandbox-Kommandozeile, die den Binärnamen enthält (empirisch belegt, s. §0),
  und über `SteamAppId=` auf jeden Prozess mit dieser Variable im Environment
  (z. B. hängengebliebene wine/proton-Reste nach einem Absturz).
  Solange so ein Prozess existiert, kommt der Nutzer nicht mehr ins Spiel —
  und auch nicht mehr an Proton-Tools (`:1311`) oder eigene Programme (`:2650`),
  die denselben Hook benutzen.
- Fix: `QMessageBox` mit zusätzlichem Knopf „Trotzdem starten"; bei Bestätigung
  `_clear_watch_target()` und normal weiter.

### [LOW] F-6 — Nach blindem Aufgeben bleibt das Watch-Ziel für immer stehen

- Datei: `anvil/widgets/game_panel.py:2853-2858`, `:2831-2836`
- Problem: In beiden „blind"-Zweigen wird `_clear_watch_target()` nicht gerufen.
  `is_game_running()` liefert danach dauerhaft `True` → `_do_redeploy`,
  Profilwechsel und `closeEvent` räumen nie wieder auf, und jeder dieser Aufrufe
  löst einen Host-Scan auf dem GUI-Thread aus (gemessen 22–38 ms normal,
  im Hängefall bis 2 × `_HOST_SCAN_TIMEOUT` = 6 s).
- Kein Aussperren: `_predeploy_for_launch` benutzt `game_state()==RUNNING`,
  bei `UNKNOWN` wird der Start zugelassen — dieser Teil der Asymmetrie ist korrekt.

### [LOW] F-7 — `game_state()` schreibt das eigene Suchergebnis nicht in den Zwischenspeicher

- Datei: `anvil/widgets/game_panel.py:2764-2784`
- Nach einem Cache-Miss wird `lookup_game_pid()` ausgeführt, das Ergebnis aber
  nicht über `_note_game_state()` abgelegt. Mehrere GUI-Abfragen kurz
  hintereinander erzeugen jeweils einen neuen Host-Prozess.

### [LOW] F-8 — Ein einzelner Fehltreffer beendet den Watcher sofort

- Datei: `anvil/widgets/game_panel.py:2844-2849`
- `if reliable and pid is None: break` → sofort Purge. Keine Bestätigung durch
  eine zweite Messung. Bei einem kurzzeitig unvollständigen `/proc`-Scan
  (z. B. `ps`-Fallback unter Last) wird zu früh aufgeräumt.

### [LOW] F-9 — Kein Generationszähler für Watcher-Threads

- `_start_process_watcher` startet einen neuen Thread, ohne den alten zu stoppen.
  Nach „Entsperren → Ja" + erneutem Start laufen zwei Threads auf denselben
  Feldern und feuern beide `game_stopped`. Folgen sind harmlos (zweiter Purge
  ist ein No-Op), aber der Zustand ist nicht eindeutig.

### [LOW] F-10 — Kosmetik im Entsperren-Dialog

- `mainwindow.py:2706-2708`: Ohne Deployment wird `_unlock_ui(False)` gerufen,
  was „game state unknown — keeping the deployment" ins Log schreibt, obwohl
  nichts unbekannt ist und nichts liegen bleibt.

### [LOW] F-11 — `start_debug_log()` startet erst nach dem Single-Instance-Check

- `anvil/main.py:150-154`. Alles davor (Basisverzeichnis-Recovery, Style-,
  Icon-, Qt-Meldungen) landet nicht in `debug.log`. Begründung im Kommentar ist
  nachvollziehbar; die Lücke sollte aber bekannt sein.

### [INFO] F-12 — Flatpak-Manifest

- Gebaut wird `packaging/flatpak/com.github.Marc1326.AnvilOrganizer.yml`
  (`build-flatpak.sh:35`, `.github/workflows/flatpak.yml:23`). Dort stand
  `--talk-name=org.freedesktop.Flatpak` bereits (Zeile 31) — bestätigt durch
  `flatpak info --show-permissions`: `org.freedesktop.Flatpak=talk` ist gesetzt,
  ohne User-Override. Der Diff ergänzt die Berechtigung im zweiten Manifest
  `net.anvil_organizer.AnvilOrganizer.yml`. Beide sind jetzt gleich — gut,
  aber die Änderung wirkt für den aktuell gebauten Flatpak nicht neu.

---

## 3. Antworten auf die gestellten Fragen

### Frage 1 — Sind alle vier abgesichert?
**Ja.** `_do_redeploy`, Profilwechsel, `_teardown_current_instance` und
`_predeploy_for_launch` haben jetzt jeweils einen Guard (Tabelle §1, #3–#5, #7).
**Aber** es gibt weitere Purge-Wege: `_crash_recovery_purge()` (F-1, ungeschützt),
`remove_orphaned_links()` (Teil von F-1) und den internen Purge in
`ModDeployer.deploy()`, der über die REDmod-/GRB-Startzweige ohne Guard
erreichbar ist (F-4).

### Frage 2 — Ist die Asymmetrie richtig umgesetzt?
An den Aufräumpfaden ja: `_do_redeploy`, Profilwechsel, Instanzwechsel und
`closeEvent` verwenden alle `is_game_running()`, das bei `UNKNOWN` `True` liefert
(`game_state() != GAME_STOPPED`) — also „im Zweifel nicht löschen". Korrekt.
`_predeploy_for_launch` verwendet `game_state() == GAME_RUNNING` — bei kaputtem
Lookup bleibt der Start möglich. Korrekt und getestet.
**Ausnahme:** Die Storage-Migration benutzt zwar dieselbe Formel wie
`_predeploy_for_launch`, ist aber kein Pfad, der den Nutzer aussperren würde —
dort ist die harte Variante angebracht (F-3).

### Frage 3 — Kann der Nutzer sich aussperren?
- **Spielstart:** Nein, solange der Lookup *fehlschlägt* (`UNKNOWN` → erlaubt).
  **Ja**, wenn der Lookup einen **falschen Treffer** liefert — dann ist der Start
  dauerhaft blockiert, ohne Ausweg (F-5).
- **Profilwechsel:** immer möglich; es wird nur nicht gepurgt (harmlos, der
  Predeploy vor dem nächsten Start räumt auf).
- **Instanzwechsel:** dito.
- **App beenden:** immer möglich; `closeEvent` purgt ggf. nicht, `super().closeEvent()`
  läuft immer. Kein Blockieren.
- **Entsperren:** immer möglich, der Dialog hat beide Wege.
- **Proton-Tools / eigene Programme:** gleiches Falsch-Positiv-Risiko wie der
  Spielstart (F-5).

### Frage 4 — Ablauf Start 1 → Beenden → Start 2 → Start 3

| Schritt | Ablauf | Bewertung |
|---|---|---|
| Start 1 | `_on_start_clicked` → `_predeploy_hook` → `_predeploy_for_launch`: `_watch_binary` leer → `GAME_STOPPED` → erlaubt → `silent_purge()` + `silent_deploy()` → `_launch_via_steam` → `game_started` → UI-Lock, `_start_process_watcher(binary, app_id)` | ✅ deployt |
| Watcher | Sucht bis 120 s nach dem Prozess (Host-Scan, ~25 ms/Runde + 1 s), dann Polling alle 5 s | ✅ **sofern das Spiel binnen 120 s erscheint** — sonst F-2 |
| Spiel beenden | `pid=None, reliable=True` → `_clear_watch_target()` → `game_stopped(True)` → `_unlock_ui(True)` → `is_game_running()` = False → `_purge_after_game()` | ✅ räumt korrekt auf |
| Start 2 | `_watch_binary` leer → `GAME_STOPPED` → Purge (No-Op) + Deploy → Start | ✅ |
| Start 3 | identisch zu Start 2 | ✅ |
| Zwischendurch Mod umschalten (Spiel läuft) | `_do_redeploy` → `is_game_running()` = True → „leftover kept" | ✅ nichts wird gelöscht |
| Anvil schließen (Spiel läuft) | `closeEvent` → Guard greift → Deployment bleibt | ✅ |
| **Anvil danach neu öffnen (Spiel läuft noch)** | `_crash_recovery_purge()` löscht alles | ❌ **F-1 — der Vorfall wiederholt sich** |
| **Spiel braucht >120 s zum Erscheinen** | Watcher-Timeout → `_clear_watch_target()` → `game_stopped(True)` → Purge | ❌ **F-2 — der Vorfall wiederholt sich** |

### Frage 5 — Entsperren-Dialog
- **Kein Deployment vorhanden** (`has_deployment()` False, `mainwindow.py:2706`):
  kein Dialog, direkt `_unlock_ui(False)` → nur Overlay weg. ✅ (Logtext irreführend, F-10)
- **„Ja"** (`:2714-2719`): `_game_running = False`, `_purge_after_game()` **ohne**
  zweite Abfrage der Prozesssuche — die Entscheidung des Nutzers wird ausgeführt,
  auch wenn das Spiel noch läuft. Der Dialogtext warnt ausdrücklich davor
  („Wenn das Spiel noch läuft, stürzt es dabei ab."). ✅ so gewollt.
  Anmerkung: `_clear_watch_target()` wird dabei nicht gerufen; der Watcher läuft
  weiter und feuert beim Spielende erneut `game_stopped(True)` → zweiter Purge
  (No-Op) + zweites `_release_ui_lock()` (No-Op). Harmlos.
- **„Nein" / Dialog geschlossen** (`:2712-2713`): `_unlock_ui(False)` →
  Deployment bleibt liegen, UI entsperrt, `_game_running = False`. ✅
  Aufgeräumt wird beim nächsten Spielstart (Predeploy-Purge) oder — mit dem
  Risiko aus F-1 — beim nächsten App-Start.

---

## 4. Ergebnis

**NEEDS FIXES**

Der eigentliche Auslöser (blinde Prozesssuche in der Sandbox) ist behoben und in
der echten Sandbox nachgewiesen. Die vier gemeldeten `silent_purge()`-Pfade sind
korrekt abgesichert, die Asymmetrie ist an den Aufräumpfaden sauber umgesetzt.

Es bleiben aber **zwei Wege, die exakt denselben Schaden erneut erzeugen**:

1. **F-1** — `_crash_recovery_purge()` beim App-Start ist ungeschützt, und weil
   das Watch-Ziel keinen Anvil-Neustart überlebt, sind nach einem Neustart
   *alle* neuen Guards wirkungslos.
2. **F-2** — Der Watcher-Timeout nach 120 s löscht bedingungslos, weil
   `_clear_watch_target()` vor dem Signal läuft und die Nachprüfung in
   `_unlock_ui` damit tot ist (im Test belegt).

Beide sollten vor einem Commit behoben werden. F-3 bis F-5 sind ebenfalls
relevant, F-6 bis F-12 sind Nacharbeit.
