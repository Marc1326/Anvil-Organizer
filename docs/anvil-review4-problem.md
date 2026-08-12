# QA-Review 4 — "Anvil löscht die Mods, während das Spiel läuft"

Datum: 2026-08-06
Geprüfter Stand (nicht committet, Arbeitsverzeichnis):

| Datei | md5 |
|---|---|
| `anvil/widgets/game_panel.py` | `5da13d866f46696fdee6ca84a80fea3b` |
| `anvil/mainwindow.py` | `4c967419a581fddcb0301515b5d62e23` |
| `anvil/core/game_process.py` | `faa4e6bdca839eadf1fa0af7bd02155c` |

> Hinweis: Die Dateien wurden **während** dieses Reviews weiterbearbeitet
> (21:37–21:39). Alle Aussagen unten beziehen sich auf die oben genannten
> Prüfsummen; ein späterer Stand ist erneut zu prüfen.

Testbedingungen: alles mit `QT_QPA_PLATFORM=offscreen`, kein sichtbares
Fenster, keine GUI-Instanz gestartet. Suchbegriffe (Binärnamen, AppIds)
wurden zur Laufzeit zusammengesetzt — ein Fehlversuch, bei dem der Name
doch in der Shell-Kommandozeile stand, hat prompt den eigenen Prozess
getroffen und ist im Abschnitt "Messfallen" dokumentiert.

---

## Urteil

**Der gemeldete Vorfall ist behoben.** Der Kern — Flatpak-PID-Namespace,
`/proc` zeigt nur Anvil, Suche findet nie etwas, Zeitlimit purgt — ist an
allen drei Stellen dicht: Suche läuft über den Host, "kein Fund" wird von
"Suche fehlgeschlagen" unterschieden, und das Zeitlimit räumt nicht mehr auf.
Die vier Punkte N-1 bis N-4 aus Runde 3 sind umgesetzt und belegt.

**Aber:** Es gibt einen weiteren, reproduzierbaren Weg, auf dem Anvil den
Spielordner unter einem laufenden Spiel leert (HIGH-1), plus zwei ungesicherte
Löschpfade (MEDIUM-1/2). Deshalb: **NEEDS FIXES**.

---

## 1. Grundlage empirisch bestätigt

Aus der installierten Sandbox heraus gemessen
(`flatpak run --command=python3 … com.github.Marc1326.AnvilOrganizer`):

```
SANDBOX_PROC_PIDS 2          <- /proc zeigt nur Anvil selbst
HAS_FLATPAK_INFO True
HOST_RC 0 OUT 613            <- flatpak-spawn --host python3 sieht 613 Prozesse
PS_RC 0 LINES 613            <- ps-Rückfallweg funktioniert ebenfalls
```

Und mit dem Arbeitsstand von `game_process.py`, gegen einen echten
Host-Prozess mit `SteamAppId` in der Umgebung:

```
LOCAL_SCAN (sandbox /proc) None      <- der alte Weg findet nichts (= die Ursache)
FIND appid+bin (1835676, True)  0,03 s
FIND appid only (1835676, True)
FIND binary only (1835676, True)
HOST_PY appid 1835676
HOST_PS  bin  1835676
FIND bogus (None, True)              <- "nichts gefunden" ist zuverlässig
FIND nothing (None, True)
```

Die installierte Flatpak hat `org.freedesktop.Flatpak=talk` bereits gesetzt;
beide Manifeste im Repo führen die Zeile jetzt.

---

## 2. Inventur: alle Wege, auf denen etwas aus dem Spielordner verschwindet

| # | Weg | Löscht | Absicherung | Bewertung |
|---|---|---|---|---|
| 1 | `GamePanel.silent_purge()` → `ModDeployer.purge()` | alle Links/Kopien aus dem Manifest, leere Ordner | siehe 1a–1i | — |
| 1a | `_begin_storage_migration` (mainwindow:1051) | wie 1 | `is_game_running()` davor | OK |
| 1b | `_start_next_storage_instance` (1135) | wie 1 | `is_game_running()` davor | OK |
| 1c | `_teardown_current_instance` / Instanzwechsel (1669) | wie 1 | `_game_running or is_game_running()` | OK |
| 1d | `_do_redeploy` / Mod-Häkchen, 500-ms-Debounce (2350) | wie 1 | `_game_running or is_game_running()` | OK — außer bei falschem Suchziel, siehe HIGH-1 |
| 1e | `_predeploy_for_launch` / Vorab-Purge vor Start (2631) | wie 1 | Abbruch bei `game_state()==RUNNING`, außer der Nutzer besteht darauf | OK |
| 1f | `_purge_after_game` aus `_unlock_ui` (2804) | wie 1 | nur bei `stopped=True` **und** `not is_game_running()` | OK |
| 1g | `_purge_after_game` aus `_on_unlock_clicked` ("Ja") | wie 1 | ausdrückliche Nutzerentscheidung, Dialogtext warnt vor dem Absturz | Bewusst ungeprüft — richtig so |
| 1h | Profilwechsel (4766) | wie 1 | `_game_running or is_game_running()` | OK |
| 1i | `closeEvent` (7155) | wie 1 | `_game_running or is_game_running()` | OK |
| 2 | `ModDeployer.deploy()` purgt intern zuerst (mod_deployer:331) | wie 1 | nur aus dem Startpfad erreichbar, dort abgesichert | OK |
| 3 | `ModDeployer.remove_orphaned_links()` | jeden Symlink im Spielordner, der nach `.mods/` zeigt | nur noch in `_crash_recovery_purge`, dort hinter der Prozessprüfung (`continue` überspringt **beide** Purges) | OK — N-4 behoben |
| 4 | `GRBDeployer.purge()` | Forge-Deploy | derselbe `silent_purge()`-Einstieg | OK |
| 5 | `BA2Packer.cleanup_ba2s()` / `restore_ini()` | BA2-Archive, INI | innerhalb `silent_purge()` | OK |
| 6 | `_fw_uninstall` (mainwindow:7984) | löscht `detect_installed`-Dateien **direkt im Spielordner** (`unlink`/`rmtree`) | **keine** Prüfung, ob das Spiel läuft | **MEDIUM-2** |
| 7 | `_ctx_remove_mods` (6422) | `rmtree` auf den Mod-Ordner in `.mods/` | **keine** Prüfung; danach `_do_redeploy()`, das die Links stehen lässt → tote Symlinks im Spielordner | **MEDIUM-1** |
| 8 | `storage_migration.py:687` `self.purge()` | Callback | wird nirgends befüllt (`purge=` kommt im ganzen Baum nicht vor) → toter Zweig | OK |

Alle neun `silent_purge()`-Aufrufe wurden einzeln im Quelltext nachgesehen;
keiner ist ohne Absicherung geblieben.

---

## 3. Belege für die geforderten Abläufe

Aufbau: echtes Instanzverzeichnis, echter `ModDeployer` (Symlink liegt
wirklich im "Spielordner"), echte `GamePanel`, echte `MainWindow`-Methoden,
echter Ersatzprozess mit `SteamAppId` in der Umgebung.
45 Prüfpunkte, davon 42 direkt bestanden; die drei anderen waren der
absichtliche Nachlauf des Zwischenspeichers (siehe LOW-1) und danach
ebenfalls korrekt.

### a) Start 1 → Spiel beenden → Start 2 → Start 3

Drei vollständige Runden, jede mit echtem Prozess und echtem Watcher:

```
R1..R3: vor Start ausgerollt              ['a.pak']
R1..R3: Spiel erkannt                     ja
R1..R3: Mod-Umschalten lässt Links stehen ['a.pak']
R1..R3: Entsperren lässt Links stehen     ['a.pak']
R1..R3: game_stopped gemeldet             [True]
R1..R3: nach Spielende aufgeräumt         []
R1..R3: Vanilla-Datei unversehrt          ja
Watch-Ziel nach Runde 3: '' None, generation 5
```

Der gemeldete Vorfall (dritter Start räumt unter dem laufenden Spiel auf)
tritt nicht mehr auf. Entscheidend dafür: `clear_watch_target()` erhöht die
Generation (N-2), sodass ein alter Watcher-Thread nicht mehr für den neuen
Start meldet — im Test bleibt `generation` sauber durchgezählt, und es kam
pro Runde genau ein `game_stopped`.

### b) Spiel läuft → Anvil beenden → neu starten → Häkchen → Profil → schließen

```
b1: Schließen lässt Links stehen                        ['a.pak']
b2: Neustart (_crash_recovery_purge) lässt Links stehen  ['a.pak']   Log: "[PURGE] CP: game may still be running — deployment kept"
b3: frisches Panel erkennt Spiel über Plugin-Rückfall     running
b4: Mod-Häkchen lässt Links stehen                       ['a.pak']
b5: Profilwechsel lässt Links stehen                     ['a.pak']
b6: erneutes Schließen lässt Links stehen                ['a.pak']
```

b3 ist der Beleg für N-1: Das frische Panel hat kein Watch-Ziel; über
`plugin_watch_target()` (SteamAppId + GameBinary) wird das Spiel aus der
alten Sitzung trotzdem gefunden — dauerhaft, nicht nur "einen Moment".

### c) Spiel braucht länger als 120 s

```
c1: Zeitlimit meldet [False]  (= "unbekannt", nicht "beendet")
c2: Zeitlimit räumt nicht auf            ['a.pak']
c3: Watch-Ziel bleibt bestehen           'anvprobecp77.exe'
c4: später gestartetes Spiel wird noch erkannt   running
c5: Mod-Umschalten nach dem Zeitlimit lässt Links stehen   ['a.pak']
c6/c7: nach echtem Spielende → stopped → wird aufgeräumt
```

N-3 ist belegt: `game_stopped(False)` → `_unlock_ui(False)` → Protokoll
"[LAUNCH] game state unknown — keeping the deployment", kein Purge.
Ergänzung: Im Proton-Startweg wird `proc` mitgegeben, dort blockiert der
Watcher nach dem Zeitlimit zusätzlich in `proc.wait()` — die Oberfläche
bleibt also bis zum echten Prozessende gesperrt.

### d) Spiel läuft, Entsperren → "Nein", danach "Start"

```
d1: "Nein" lässt Links stehen                       ['a.pak']
d2: Oberfläche ist wieder frei                       ja
d3: Rückfrage vor dem Start, "Nein" bricht ab        kein Start
d4: Links unangetastet                               ['a.pak']
d5: Vorab-Deploy lehnt ab (None) und meldet es       genau 1 Warnung
d6: Links unangetastet                               ['a.pak']
d7: "Ja" erlaubt den Start                           ja
d8: erzwungener Start purgt und rollt neu aus        ['a.pak']
```

Der doppelte Boden greift: erst die Rückfrage im Panel, dann noch einmal die
Prüfung im Vorab-Deploy. Ohne Bestätigung kommt keine Löschung zustande;
mit Bestätigung wird sie ausgeführt (`_FORCED_LAUNCH_TTL` 120 s, verfällt
von selbst — ein Zweig, der die Marke nie abholt, entwaffnet die Prüfung
nicht dauerhaft).

---

## 4. Kann sich der Nutzer aussperren? Bleibt etwas liegen?

Gemessen mit dauerhaft blinder Suche (`find_game_process → (None, False)`):

```
3a: Zustand ist "unbekannt"
3b: Mod-Umschalten räumt nicht auf              ['a.pak']
3c: Schließen räumt nicht auf                   ['a.pak']
3d: Neustart/Crash-Recovery räumt nicht auf     ['a.pak']
3e: Start fragt nach, lässt sich erzwingen      ja
3f: Vorab-Deploy läuft bei "unbekannt" durch    True, keine Warnung
3g: dabei neu ausgerollt                        ['a.pak']
```

**Aussperren: nein.** "unbekannt" blockiert den Start nicht
(`_predeploy_for_launch` prüft auf `== GAME_RUNNING`), und selbst bei
"läuft" gibt es die Rückfrage mit "trotzdem starten".

**Liegenbleiben: ja, unbegrenzt** — siehe MEDIUM-4. Solange die Suche blind
ist, räumt *kein* Weg mehr auf: nicht das Schließen, nicht der Neustart,
nicht das Mod-Umschalten. Nur ein Spielstart oder "Entsperren → Ja" leert
den Ordner wieder. Für die Datensicherheit ist das die richtige Richtung,
für die Aufräumzusage ("Mods liegen nur im Spielordner, solange gespielt
wird") ist es ein Loch.

Zusätzlich: Zwei Stellen bewerten denselben Zustand verschieden.
`_schedule_base_directory_migration` (1017) und `_begin_storage_migration`
(1082) lassen "unbekannt" durch (`== GAME_RUNNING`), die Purges direkt
danach (1048, 1132) brechen bei "unbekannt" ab (`is_game_running()`).
Ergebnis: Die Migration startet, wechselt schon die Instanz und bricht dann
mit "Spiel läuft" ab. Kein Datenverlust, aber unschöner Zwischenzustand.

---

## 5. Rückfall auf Plugin-Daten (GOG/Epic, Launcher-GameBinary)

### Spiele ohne GameSteamId

```
plugin_watch_target(GameSteamId=None, GameBinary="bin/x64/<spiel>.exe")
  -> (None, '<spiel>.exe')
4a2: GOG-Spiel wird über den Binärnamen gefunden      running
4a3: nichts wird aufgeräumt, solange es läuft         ['a.pak']
4a4: nach Spielende → stopped
4a5: danach wird aufgeräumt                           []
```

Funktioniert. Im aktuellen Pluginbestand hat allerdings **jedes** Plugin eine
`GameSteamId`, der Fall ist also derzeit theoretisch.

### Launcher als GameBinary (`game_windrose.py`)

`GameBinary = "Windrose.exe"` ist laut Plugin-Kommentar nur ein
Launcher-Wrapper; das echte Spiel ist
`R5/Binaries/Win64/Windrose-Win64-Shipping.exe`, und genau dieses bietet das
Plugin als zweiten Eintrag "Windrose (direkt, ohne Launcher)" an.

- Über Steam gestartet (`_launch_via_steam`, `app_id` gesetzt): Das Kind
  erbt `SteamAppId`, der Watcher findet es auch nach dem Ende des Launchers.
  Belegt: nach Launcher-Ende weiterhin `running`, kein `game_stopped`,
  Links stehen.
- Über `_launch_via_proton` (jeder Nicht-Haupteintrag, also auch "direkt,
  ohne Launcher"): Der Watcher bekommt bewusst `app_id=None` und sucht nach
  `Path(GameBinary).name` = `windrose.exe`. Der laufende Prozess heißt aber
  `Windrose-Win64-Shipping.exe` — **kein Treffer, und zwar zuverlässig**.
  Daraus folgt HIGH-1.

---

## Befunde

### [HIGH-1] Falsches Watch-Ziel → Spielordner wird unter laufendem Spiel geleert
- Datei: `anvil/widgets/game_panel.py:2732` (`_start_process_watcher(game_binary, proc, app_id=None)`),
  `anvil/widgets/game_panel.py:2823` (`_search_terms` bevorzugt das Watch-Ziel
  und kommt nicht mehr an den Plugin-Rückfall heran),
  `anvil/mainwindow.py:2350` (`_do_redeploy`)
- Problem: Wird ein Spiel über `_launch_via_proton` gestartet und passt
  `GameBinary` nicht auf den echten Prozessnamen (Windrose "direkt, ohne
  Launcher"), liefert die Suche **zuverlässig** "nichts gefunden" →
  `game_state()` = `stopped`, obwohl das Spiel läuft. Der Plugin-Rückfall
  greift nicht, weil `_watch_binary` gesetzt ist; die `SteamAppId`, die das
  Spiel sicher identifizieren würde, wird absichtlich nicht mitgegeben.
- Beleg (echter Prozess, echte Dateien, `wr3.py`):
  ```
  1) Suchmerkmale: (None, 'windrose.exe')
  2) Anvils Sicht: stopped | Spiel läuft: True
  3) Links nach "Entsperren/Nein": ['a.pak'] | UI frei: True
  4) Links nach Mod-Umschalten:    []        | Spiel läuft: True
  URTEIL: DATENVERLUST unter laufendem Spiel
  ```
- Der Kommentar an der Stelle ("SteamAppId-Suche würde wine/proton Prozesse
  finden, die auch zu früh sterben") ist überholt: Seit `TOOL_ENV_MARKER`
  tragen von Anvil gestartete Werkzeuge `ANVIL_TOOL=1` und werden von der
  Suche übersprungen.
- Fix: In `_launch_via_proton` die `SteamAppId` mitgeben (wie im Steam-Weg) —
  `_build_proton_env` setzt sie ohnehin in die Umgebung des Prozesses.
  Ergänzend: zusätzlich den tatsächlich gestarteten `binary` als Suchnamen
  führen, nicht nur `GameBinary`.

### [MEDIUM-1] `_ctx_remove_mods` löscht Mod-Ordner ohne Prüfung, ob das Spiel läuft
- Datei: `anvil/mainwindow.py:6466-6468` (`shutil.rmtree(mod_path)`), danach `_do_redeploy()`
- Problem: Nach "Entsperren → Nein" ist die Oberfläche frei, während das Spiel
  läuft. Das Löschen einer Mod entfernt das Ziel der Symlinks; `_do_redeploy`
  lässt die Links (korrekt) stehen — im Spielordner bleiben tote Symlinks
  zurück, dem laufenden Spiel fehlen die Dateien.
- Fix: Gleiche Absicherung wie bei den Purges (`_game_running or
  is_game_running()` → ablehnen oder rückfragen).

### [MEDIUM-2] `_fw_uninstall` löscht direkt im Spielordner ohne Prüfung
- Datei: `anvil/mainwindow.py:8020-8030` (`target.unlink()` / `shutil.rmtree(target)`
  auf `game_path / det_path`)
- Problem: Derselbe Zustand wie MEDIUM-1; hier werden echte Dateien im
  Spielverzeichnis entfernt (Framework-DLLs), nicht nur Symlinks.
- Fix: dieselbe Absicherung.

### [MEDIUM-3] Nicht-Steam-Start hat keinen Watcher — Sperre und Aufräumen hängen am Nutzer
- Datei: `anvil/mainwindow.py:2682` (`notify_game_started`), keine `_start_process_watcher`-Stelle
  für den Direktstart (nur `game_panel.py:2639` und `:2732`)
- Problem: Bei GOG/Epic-Installationen wird `game_started` gemeldet und die
  Oberfläche gesperrt, aber niemand meldet je `game_stopped`. Die Sperre
  bleibt bis zum Klick auf "Entsperren"; das automatische Aufräumen nach dem
  Spielende findet nie statt.
- Fix: Auch im Direktstart einen Watcher starten (`plugin_watch_target()`
  liefert die Suchmerkmale, `proc` ist vorhanden).

### [MEDIUM-4] Blinde Suche = nichts wird je aufgeräumt
- Datei: `anvil/widgets/game_panel.py:2851` (`is_game_running` = "alles außer stopped"),
  `anvil/mainwindow.py:1596` (Crash-Recovery überspringt bei `not reliable`)
- Problem: Kann die Suche dauerhaft nicht ausgeführt werden (fehlendes
  `flatpak-spawn`, fehlende Berechtigung, überlasteter Host), bleibt der
  Deploy dauerhaft im Spielordner — auch über Neustarts hinweg. Belegt in
  Abschnitt 4 (3b–3d).
- Fix-Vorschlag: einmalig melden ("Anvil kann nicht feststellen, ob ein Spiel
  läuft — der Spielordner wird nicht automatisch aufgeräumt") und im
  Diagnose-Tab sichtbar machen; alternativ nach einer Karenzzeit ohne
  bekannten Start doch aufräumen.

### [LOW-1] Zustand läuft dem Spielende hinterher (3 s bzw. 15 s)
- Datei: `anvil/widgets/game_panel.py:33-41` (`_GAME_STATE_TTL`, `_QUERY_STATE_TTL`)
- Gemessen: nach Prozessende meldet `game_state()` noch 3,0 s (eigene
  Abfrage) bzw. 15,0 s (Beobachtung des Watchers) "running".
- Folge: Wer direkt nach dem Beenden auf "Start" klickt, bekommt die
  Rückfrage "Es läuft noch ein Spiel". Ungefährlich, verschwindet von selbst.

### [LOW-2] `game_stopped` während des Entsperren-Dialogs geht verloren
- Datei: `anvil/mainwindow.py:2779` (`if self._unlock_pending: return`)
- Problem: Endet das Spiel, während der Dialog offen steht, wird das Signal
  verworfen. Antwortet der Nutzer dann "Nein", bleibt der Deploy liegen,
  obwohl das Spiel längst beendet ist. Erst der nächste Start räumt auf.
- Bewertung: sicher, aber die Absicht ("beim Beenden aufräumen") geht verloren.

### [LOW-3] Crash-Recovery ohne Suchmerkmale lässt alles liegen
- Datei: `anvil/mainwindow.py:1586-1595`
- Problem: Hat ein Plugin weder `GameSteamId` noch `GameBinary`, wird die
  Instanz übersprungen — der Deploy bleibt für immer liegen. Derzeit
  theoretisch (alle Plugins haben beides).

### [LOW-4] SteamAppId-Suche trifft längere AppIds mit gleichem Präfix
- Datei: `anvil/core/game_process.py:28` und `:67` (`needle = "SteamAppId=" + app_id`)
- Beleg: Ein Prozess mit `SteamAppId=10915000` wird als AppId `1091500`
  erkannt (gemessen, Fehltreffer bestätigt).
- Folge: fällt sicher aus (Deploy bleibt liegen), kann aber einen Start mit
  "Es läuft noch ein Spiel" blockieren.
- Fix: Nullbyte anhängen (`b"SteamAppId=1091500\0"`).

### [INFO-1] Die Erscheinungs-Schleife kann sehr kurzlebige Prozesse verpassen
- Datei: `anvil/widgets/game_panel.py` (`time.sleep(1)` in der Appear-Schleife)
- Beobachtet: Ein Ersatzprozess, der nur ~1 s lebte, wurde vom Watcher nicht
  gesehen, von einer parallelen Abfrage aber sehr wohl. Folge: Zeitlimit-Weg
  → `game_stopped(False)` → Deploy bleibt liegen. Ungefährlich.

### [INFO-2] `dialog.start_while_unknown_text` — vollständig übersetzt
Alle vier neuen Schlüssel (`dialog.unlock_purge_title`,
`dialog.unlock_purge_text`, `dialog.start_while_running_text`,
`dialog.start_while_unknown_text`, `error.game_already_running`) liegen in
allen sieben Sprachdateien (de, en, es, fr, it, pt, ru) vor und werden
verwendet.

---

## 6. Status der Punkte aus Runde 3

| Punkt | Zustand | Beleg |
|---|---|---|
| N-1 Schutz beim Anvil-Neustart hält nur einen Moment | behoben | b2/b3: frisches Panel ohne Watch-Ziel erkennt das Spiel über `plugin_watch_target()`; Crash-Recovery überspringt die Instanz |
| N-2 `clear_watch_target()` erhöht die Generation nicht | behoben | `game_panel.py:2802` `self._watch_generation += 1`; drei Startrunden ohne Fremdmeldung |
| N-3 120-s-Zeitlimit purgt weiter | behoben | c1/c2: `game_stopped(False)`, Links bleiben |
| N-4 Crash-Recovery-Guard hing an `has_manifest` | behoben | `has_manifest` wird vor der Prozessprüfung berechnet, `continue` überspringt Purge **und** `remove_orphaned_links()` |
| Spielpfad als Suchbegriff | behoben | Suche nur noch über SteamAppId + Binärname; Selbsttreffer geprüft (`FIND bogus → (None, True)`) |

Zusätzlich seit Runde 3 hinzugekommen und geprüft: `TOOL_ENV_MARKER`
(`ANVIL_TOOL=1`) für von Anvil gestartete Werkzeuge, `_FORCED_LAUNCH_TTL`
(120 s), Zurücksetzen des Zwischenspeichers beim Instanzwechsel
(`set_instance_path`), Unterscheidung `_SCAN_TIMEOUT` / `_SCAN_FAILED`.

Testlauf: `QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q`
→ **308 passed, 1 skipped**.

---

## 7. Messfallen (zur Nachahmung)

1. **Heredoc in der Shell.** Ein Prüfskript, das `GameBinary="Windrose.exe"`
   im Text enthielt, wurde über einen Heredoc geschrieben — damit stand der
   Suchbegriff in der Kommandozeile der Shell, und die Suche fand *diese*.
   Ergebnis: zwei Fehlmessungen ("Watcher findet das Spiel"), die erst nach
   dem Zusammensetzen der Namen zur Laufzeit verschwanden.
2. **Übriggebliebene Ersatzprozesse** aus einem abgebrochenen Lauf haben eine
   spätere Messung verfälscht. Vor jedem Lauf aufräumen.
3. **Zu früh beendete Ersatzprozesse**: Der Watcher prüft im Sekundentakt;
   ein Prozess, der nur eine Sekunde lebt, wird eventuell nicht gesehen.

---

## Ergebnis

**NEEDS FIXES** — HIGH-1 (Watch-Ziel ohne SteamAppId bei Launcher-Binärnamen)
führt reproduzierbar zum Leeren des Spielordners unter laufendem Spiel.
MEDIUM-1 und MEDIUM-2 sind zwei ungesicherte Löschpfade in derselben Lage.
Der ursprünglich gemeldete Vorfall selbst ist behoben und belegt.
