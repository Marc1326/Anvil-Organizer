# Review: Nicht committete Änderungen gegen Architektur- und Projektregeln

Datum: 2026-08-06
Branch: main (nichts gestaged)
Geprüfter Stand: `git diff` gegen HEAD (d174cd6) + neue Datei `anvil/core/debug_log.py`

## Geprüfter Umfang

| Datei | +/- |
|---|---|
| anvil/core/subprocess_env.py | +142 |
| anvil/core/diagnostics.py | +13/-6 |
| anvil/core/debug_log.py | neu, 114 Zeilen |
| anvil/main.py | +3 |
| anvil/mainwindow.py | +55/-14 |
| anvil/widgets/game_panel.py | +99/-58 |
| anvil/locales/{de,en,es,fr,it,pt,ru}.json | je +3/-1 |
| tests/test_predeploy_launch.py | +112 |

Herangezogen: `CLAUDE.md` (global + Projekt), `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md`
(im Projektordner selbst liegt **keine** ARCHITEKTUR.md — nur im Wiki), `docs/anvil-feature-issue84-deploy-flatpak.md`.

Belege: alle Aussagen unten sind durch ausgeführte Befehle/Testläufe gedeckt (Abschnitt "Durchgeführte Prüfungen").

---

## Findings

### [HIGH] Der neue Purge-Dialog wird von `is_game_running()` wieder ausgehebelt

- Datei: `anvil/mainwindow.py:2686-2693` und `2708-2715`
- Problem: `_on_unlock_clicked()` fragt den Nutzer per Dialog, ob das Deployment jetzt entfernt
  werden soll. Der Dialogtext sagt ausdrücklich: *„Jetzt entfernen? Wenn das Spiel noch läuft,
  stürzt es dabei ab."* — der Nutzer bestätigt also bewusst das Risiko. Bei „Ja" ruft der Code
  `_unlock_ui(True)` auf, und dort wird die Entscheidung sofort wieder überstimmt:

  ```python
  still_running = getattr(self._game_panel, "is_game_running", lambda: False)()
  ```

  `is_game_running()` liefert seit dieser Änderung **True, sobald der Lookup fehlschlägt**
  (`game_panel.py:2746-2749`). Genau das ist der Flatpak-Fall, für den der Dialog gebaut wurde.
  Ergebnis: Der Nutzer klickt „Ja", nichts passiert, und ins Log geht die Meldung
  „unlock requested, but the game is still running — keeping the deployment".
  Das Feature verfehlt seinen Zweck in exakt dem Szenario, das es adressieren soll.
- Fix: Bei explizitem „Ja" muss `_unlock_ui` den Purge ohne erneute Rückfrage an
  `is_game_running()` ausführen, z. B. über einen dritten Zustand (`force`) statt des
  bool-Parameters `stopped`. Der Signal-Pfad (`game_stopped`) behält die bisherige
  Sicherheitsprüfung.
- Zusatz: Es gibt **keinen Test** für `_on_unlock_clicked` und keinen für den Ja-Zweig
  (`grep -n "_on_unlock_clicked" tests/` → 0 Treffer).

### [HIGH] `start_debug_log()` läuft vor dem Single-Instance-Check und rotiert das Log der laufenden Instanz weg

- Datei: `anvil/main.py:117-118` (Aufruf) vs. `anvil/main.py:131-151` (Single-Instance-Check)
- Problem: Jeder kurzlebige Forwarder-Prozess — und das ist **jeder Klick auf „Mod Manager
  Download" bei Nexus** (nxm://) sowie jeder Start über eine `.desktop`-Verknüpfung bei bereits
  laufender App — durchläuft `start_debug_log()`, bevor `single.try_lock()` ihn wieder
  hinauswirft. Damit:
  1. schreibt der Forwarder einen eigenen `===== … Anvil vX =====`-Header in die gemeinsame
     `<base>/logs/debug.log`;
  2. ruft er `_rotate()` auf. Ist die Datei über 2 MB, wird sie per `rename()` zu `debug.log.1`
     — **während die laufende Instanz sie offen hält**. Die laufende Instanz schreibt ab dann in
     die umbenannte Inode; nach zwei weiteren Rotationen wird diese Inode per `unlink()`
     entfernt und alle weitere Ausgabe landet in einer gelöschten Datei.
  Das ist genau der Datenverlust, den das Modul verhindern soll.
- Fix: `start_debug_log()` erst **nach** `single.try_lock()` aufrufen (also nach `main.py:151`),
  oder `_rotate()` überspringen, solange der Instanz-Lock nicht gehalten wird. Ausgaben des
  Forwarders vor dem Lock landen ohnehin nur in zwei Fehlermeldungen (`main.py:138-147`).

### [MEDIUM] `is_game_running()` ist jetzt ein blockierender Host-IPC-Aufruf im GUI-Thread

- Datei: `anvil/core/subprocess_env.py:_HOST_SCAN_TIMEOUT = 10`, Aufrufer
  `anvil/mainwindow.py:1016`, `1078`, `7059`
- Problem: Vorher war `is_game_running()` ein lokaler `/proc`-Scan (Millisekunden). Jetzt
  startet der Aufruf im Flatpak `flatpak-spawn --host python3` (Timeout 10 s) und bei
  Fehlschlag zusätzlich `flatpak-spawn --host ps` (weitere 10 s) — bis zu **20 s eingefrorene
  GUI**, unter anderem im `closeEvent`. `self._watch_binary` wird nach Spielende nie
  zurückgesetzt (`game_panel.py:537, 2761`, kein Reset im Watcher), der Zustand betrifft also
  jede weitere Aktion in derselben Sitzung nach dem ersten Spielstart.
- Fix: Ergebnis mit kurzem TTL cachen (der Watcher pollt ohnehin) oder `_HOST_SCAN_TIMEOUT`
  für synchrone GUI-Aufrufe deutlich senken (1-2 s); `_watch_binary`/`_watch_app_id` nach
  bestätigtem Spielende zurücksetzen.

### [MEDIUM] Fehlgeschlagener Lookup blockiert die Speicher-/Basisverzeichnis-Migration mit falscher Meldung

- Datei: `anvil/mainwindow.py:1016` und `1078`
- Problem: `if self._game_running or self._game_panel.is_game_running(): self._storage_fail(tr("storage.error_game_running"))`.
  Da `is_game_running()` bei nicht durchführbarem Lookup True liefert, bricht die Migration mit
  „Spiel läuft" ab, obwohl kein Spiel läuft. Das Fail-Safe-Verhalten (sinnvoll beim Purge)
  wandert hier in einen Bereich, in dem „unbekannt" nicht „läuft" bedeuten darf — und die
  Meldung an den Nutzer ist schlicht unwahr.
- Fix: An diesen beiden Stellen `lookup_game_pid()` direkt auswerten und bei `reliable=False`
  eine eigene Meldung ausgeben („Spielstatus nicht ermittelbar") oder den Vorgang zulassen.

### [MEDIUM] Der Watcher gibt nach einem einzigen fehlgeschlagenen Lookup dauerhaft auf

- Datei: `anvil/widgets/game_panel.py:2791-2801`
- Problem: In der Laufschleife führt der **erste** `reliable=False` sofort zu
  `game_stopped.emit(False)` + `return`. Der Watcher-Thread ist damit tot: es kommt nie mehr ein
  `game_stopped(True)`, das Deployment bleibt bis zum nächsten Spielstart liegen. Ein einzelner
  10-s-Timeout des Host-Aufrufs während einer Ladephase des Spiels ist realistisch — das reicht,
  um die Überwachung endgültig zu verlieren.
- Fix: Erst nach N aufeinanderfolgenden Fehlversuchen (z. B. 3) aufgeben, dazwischen weiter
  pollen.

### [MEDIUM] `_GAME_APPEAR_TIMEOUT = 120` ist keine Zeitschranke mehr, und die Poll-Optimierung greift dort nicht

- Datei: `anvil/widgets/game_panel.py:2713-2719`, `2767-2774`
- Problem: Der neue Kommentar zu `_GAME_POLL_INTERVAL = 5` begründet das grobe Intervall damit,
  dass „inside Flatpak every check spawns a host process". Genau diese Optimierung fehlt in der
  Appear-Schleife darüber: sie ruft `lookup_game_pid()` **jede Sekunde**, 120-mal — also bis zu
  120 Host-Prozesse in der Startphase, der teuersten Phase überhaupt. Zusätzlich ist die
  „120 Sekunden" der Konstanten nicht mehr gültig: pro Iteration kommen bis zu 20 s Host-Timeout
  hinzu, im Extremfall bleibt die UI ~40 Minuten gesperrt.
- Fix: Auch in der Appear-Schleife nach den ersten Sekunden auf ein gröberes Intervall gehen und
  die Schleife über eine echte Deadline (`time.monotonic()`) statt über einen Iterationszähler
  begrenzen.

### [MEDIUM] Die Prozesssuche gehört nicht in `subprocess_env.py`

- Datei: `anvil/core/subprocess_env.py:123-264`
- Problem: Der Modul-Docstring definiert den Zweck eng und wurde **nicht** angepasst:
  *„This module provides helpers to restore the original environment before spawning child
  processes."* Prozess-*Suche* ist keine Umgebungsbereinigung. Der Anbau macht aus einem
  fokussierten 240-Zeilen-Helfer ein 380-Zeilen-Modul mit zwei Zuständigkeiten, und die
  Begründung („braucht `is_flatpak()`") trägt nicht — ein Import genügt dafür.
  Die Hausordnung in `anvil/core/` ist eindeutig ein Modul pro Zuständigkeit
  (`single_instance.py` 86 Z., `activity_log.py` 72 Z., `profile_name.py` 40 Z.,
  `desktop_shortcut.py` 91 Z. — und in diesem Diff wird für das Log-Tee sogar bewusst ein
  eigenes `debug_log.py` angelegt).
- Fix: Nach `anvil/core/game_process.py` verschieben (`scan_proc_for_game`, `_HOST_SCAN`,
  `_host_scan_via_python`, `_host_scan_via_ps`, `find_game_process`), dort
  `from anvil.core.subprocess_env import is_flatpak` importieren. `game_panel.py` importiert
  dann `find_game_process` von dort. Falls es bei `subprocess_env.py` bleiben soll: Modul-
  Docstring zwingend um die zweite Zuständigkeit erweitern.

### [MEDIUM] Zwei Funktionen, gleicher Eingabefall, unterschiedlicher Vertrag

- Datei: `anvil/core/subprocess_env.py:236-238` vs. `anvil/widgets/game_panel.py:2734-2736`
- Problem: Ohne `app_id` und ohne `binary_name` liefert `find_game_process()` `(None, False)`
  („unzuverlässig" → Aufrufer muss „läuft" annehmen), `GamePanel.lookup_game_pid()` im selben
  Fall aber `(None, True)` („nichts gestartet"). Der Test `test_lookup_without_target_is_unreliable`
  zementiert diese Asymmetrie sogar. Jeder künftige direkte Aufrufer von `find_game_process()`
  bekommt „Spiel läuft", wenn er nichts zu suchen angibt.
- Fix: Einen Vertrag festlegen. Sauber ist `(None, True)` in beiden Fällen — „nichts zu suchen"
  ist ein vollständig durchgeführter Lookup mit dem Ergebnis „nichts da", kein Fehlschlag.

### [LOW] Irreführende Logmeldung „game state unknown"

- Datei: `anvil/mainwindow.py:2683-2684` und `2704-2706`
- Problem: `stopped=False` transportiert drei verschiedene Sachverhalte: „Zustand unbekannt",
  „Nutzer hat Nein geklickt" und „es gibt gar kein Deployment". In allen drei Fällen wird
  „[LAUNCH] game state unknown — keeping the deployment" geloggt. In den letzten beiden Fällen
  ist das schlicht falsch, und bei fehlendem Deployment gibt es auch nichts zu behalten.
- Fix: Getrennte Meldungen, bzw. einen Enum/drei-Zustand statt eines bool.

### [LOW] Umständliche, teils tote Verzweigung in `_unlock_ui`

- Datei: `anvil/mainwindow.py:2703-2715`
- Problem: `if not stopped: … still_running = True` gefolgt von `if still_running: if stopped:`
  — der innere Zweig ist nur erreichbar, wenn `stopped` True ist, die Verschachtelung ist also
  eine Verrenkung um die künstlich gesetzte Variable herum. Liest sich generiert, nicht
  geschrieben (Projektregel „AI-Sichtbarkeit").
- Fix: Flach ausformulieren:
  `if not stopped: print(...)` / `elif is_game_running(): print(...)` / `else: purge()`.

### [LOW] Inkonsistente `getattr`-Absicherung

- Datei: `anvil/mainwindow.py:2709-2711`
- Problem: Hier wird `is_game_running` defensiv per `getattr(..., lambda: False)` geholt,
  an den drei anderen neuen/geänderten Stellen (`1016`, `1078`, `7059`) aber direkt aufgerufen.
  Die Absicherung existiert nur, weil Tests ein `SimpleNamespace` einsetzen — und ihr Default
  (`False` = „läuft nicht") widerspricht dem gerade eingeführten Fail-Safe (`True`).
- Fix: `getattr` entfernen und die Testdoubles vollständig bestücken.

### [LOW] `debug_log_path()` ist toter Code

- Datei: `anvil/core/debug_log.py:22-24`
- Beleg: `grep -rn "debug_log_path" --include=*.py .` → nur die Definition.
- Problem: Ungenutzte Symmetrie-API. Die Diagnose (`diagnostics.py:242`) baut den Pfad selbst
  aus `anvil_base_paths().logs` zusammen, statt die Funktion zu nutzen.
- Fix: Entweder in `diagnostics.log_sources()` verwenden oder entfernen.

### [LOW] Deutsches Wort in einem sonst rein technischen, unübersetzten Label

- Datei: `anvil/core/diagnostics.py:253`
- Problem: `{"label": "debug.log (Projekt)"}`. Alle übrigen Labels dieser Liste sind reine
  Dateinamen (`activity.log`, `debug.log.1`). Das Label erscheint in der Auswahlbox des
  Diagnose-Tabs (`settings_dialog.py:1487-1489`) und ist nicht übersetzbar — ein
  englischsprachiger Nutzer liest „(Projekt)".
- Fix: Neutral halten (z. B. `debug.log (source tree)`) oder über `tr()` führen.

### [LOW] Fehlende Rückgabe-Annotationen

- Datei: `anvil/core/subprocess_env.py:186` (`_host_scan_via_python`), `:206` (`_host_scan_via_ps`)
- Problem: Beide ohne Rückgabetyp, während alle Nachbarfunktionen im Modul annotiert sind
  (`-> bool`, `-> str | None`, `-> tuple[int | None, bool]`). Grund ist offensichtlich das
  Sentinel `_SCAN_FAILED`.
- Fix: `-> int | None | object` oder ein `Literal`-/Enum-Sentinel mit sauberem Typ.

### [LOW] `debug_log.py` ohne den Schutz, den das Schwestermodul hat

- Datei: `anvil/core/debug_log.py:96-100` vs. `anvil/core/activity_log.py:59-64`
- Problem: `activity_log.log_action()` prüft `configured_base_is_custom() and not
  _LOG_DIR.parent.is_dir()`, bevor es `mkdir(parents=True)` ausführt — damit auf einem nicht
  gemounteten externen Laufwerk keine Geisterverzeichnisse entstehen. `start_debug_log()` macht
  denselben `mkdir` ungeschützt.
- Restrisiko gering: Der Aufruf erfolgt nach `_ensure_base_directory()` (`main.py:110`), das
  einen fehlenden Custom-Base über den Recovery-Dialog abfängt. Trotzdem eine unnötige
  Abweichung vom direkten Vorbild.
- Fix: Denselben Guard übernehmen.

### [LOW] Ungetrackte Fremd-Dateien im Arbeitsbaum

- `001Bericht/` enthält `DESIGN-BERICHT.md`, `Fundus Design Varianten.zip` und `icons/` — also
  **Fundus**-Material im Anvil-Repo (`CLAUDE.md`: „PROJEKTE NICHT VERWECHSELN").
  `git check-ignore` liefert exit 1: der Ordner ist nicht ignoriert und würde bei `git add -A`
  mit eingecheckt.
- `.gitignore:8` enthält `debug.log`, deckt aber die neuen Rotations-Backups `debug.log.1` /
  `debug.log.2` nicht ab. Praktisch unkritisch (sie entstehen unter `<base>/logs/`, nicht im
  Repo), aber die Regel sollte mitziehen.
- Fix: `001Bericht/` verschieben oder ignorieren; `.gitignore` um `debug.log.*` ergänzen.

---

## Governance-Hinweis (kein Bug, braucht aber GO von Marc)

`ARCHITEKTUR.md` Abschnitt 5 und Abschnitt 9 Punkt 6:

> **NIEMALS** den Deploy-Mechanismus (Symlinks, Kopien, Manifest, **Purge**, Frameworks) ändern
> ohne ausdrückliche Zustimmung von Marc. Das schließt ein: […] die Purge-Logik, und alles was
> bestimmt wie Dateien ins Game-Verzeichnis gelangen.

Die Purge-*Logik* selbst (`mod_deployer.py`) ist unangetastet — korrekt. Geändert wurden aber die
**Auslösebedingungen** des Purge an zwei Stellen:

- `mainwindow.py:7057-7063` (`closeEvent`): `silent_purge()` wird beim App-Schließen jetzt
  übersprungen, wenn ein Spiel läuft (bzw. der Status unbekannt ist). Vorher immer.
- `mainwindow.py:2676-2715`: Unlock purged nur noch nach Nutzerbestätigung.

Beides ist inhaltlich sinnvoll und deckt sich mit ARCHITEKTUR.md Abschnitt 10 Punkt 5
(„Persistent Deploy — Symlinks bleiben nach Game-Ende bestehen"). Die Behauptung in beiden
Kommentaren, „the next start cleans up instead", ist verifiziert: `_predeploy_for_launch()`
(`mainwindow.py:2570-2571`) und `_cleanup_leftover_deployment()` (`mainwindow.py:2304-2305`)
purgen beide. Trotzdem fällt die Änderung unter die Schutzregel und braucht ein ausdrückliches
GO, bevor sie committet wird. In ARCHITEKTUR.md ist das neue Verhalten noch nicht dokumentiert.

---

## Explizit geprüft und in Ordnung

### 1. AI-Sichtbarkeit — gemessen, nicht geschätzt

- **Em-Dash und doppeltes Leerzeichen nach dem Punkt** sind **kein** Fremdkörper:
  `grep -rn -- "—" --include=*.py anvil/` → 614 Treffer; `grep -rn -P '\.  [A-Z]'` ohne die
  neuen Dateien → 117 Treffer. Die neuen Kommentare fügen sich also stilistisch ein.
- **`debug_log.py` passt zum Haus-Stil.** Es spiegelt sein direktes Vorbild `activity_log.py`
  fast eins zu eins: deutscher Modul-Docstring mit `ae/ue/oe`-Transliteration
  („zusaetzlich", „Menueeintrag" — ebenso `activity_log.py:1` „fuer", `:4` „Wochentliche"),
  identisches Rotationsmuster mit `with_suffix(f".log.{i}")`, identische Fehlerform
  `print(f"debug_log: cannot write: {exc}", file=sys.stderr)` gegen
  `print(f"activity_log: cannot write: {exc}", …)`. Transliteration ist in `anvil/core/`
  belegt (activity_log, mod_installer, mod_deployer, reshade_manager), echte Umlaute in
  14 Dateien — beide Stile existieren, die Wahl ist am Schwestermodul ausgerichtet und damit
  richtig.
  *Einzige Abweichung:* `activity_log.py` hat **englische** Funktions-Docstrings
  („Never raises."), `debug_log.py` deutsche („Wirft nie."). Kosmetisch, kein Befund.
- **Kommentardichte in `subprocess_env.py`**: hoch (drei mehrzeilige Blöcke), aber jeder erklärt
  ein nicht ableitbares *Warum* — PID-Namespace des Sandbox, warum der Suchbegriff über stdin
  statt über argv kommt (sonst matcht der Scanner sich selbst), warum das Sentinel existiert.
  Das ist genau die von `CLAUDE.md` verlangte Sorte Kommentar, keine Docstring-Flut.
  Kein Befund — abgesehen von der Verrenkung in `_unlock_ui` (siehe LOW oben).
- Keine überflüssigen Docstrings auf trivialen Methoden; `_Tee.write/flush/isatty/fileno` sind
  bis auf einen Ein-Zeiler zu `fileno()` unkommentiert. Angemessen.

### 2. Keine MO2/ModOrganizer-Erwähnungen

`grep -n -i -E "mo2|modorganizer|mod organizer|usvfs|vortex"` über **alle acht geänderten
Code-/Locale-Dateien**: 0 Treffer. (Treffer gibt es nur in unveränderten SVG-Metadaten und
`.qss` sowie in `docs/` — nicht Teil dieses Diffs.)

### 3. Keine hardcoded Pfade

`git diff | grep '^+' | grep -E "'/|\"/"` liefert ausschließlich `/proc` (Kernel-Schnittstelle,
kein Instanzpfad) und `"/game/" + binary` als Fake-argv in einem Test. Das Log-Verzeichnis kommt
über `anvil_base_paths().logs` (`debug_log.py:97`), `diagnostics.py:233`. Keine `~`-Literale,
keine Spielpfade.

### 4. Kein `setStyleSheet()`

`git diff | grep '^+' | grep -c setStyleSheet` → 0. Es wird auch kein neues Widget angelegt;
`_on_unlock_clicked` nutzt `QMessageBox.question`.

### 5. Übersetzungen — vollständig und minimal

Skriptgestützt über alle **7** Locale-Dateien (`de, en, es, fr, it, pt, ru`):

- `dialog.unlock_purge_title` und `dialog.unlock_purge_text`: in allen 7 vorhanden und
  tatsächlich übersetzt (kein Copy-Paste des englischen Textes).
- Key-Vergleich `HEAD` gegen Arbeitsstand, rekursiv geflacht: **verloren = [] in allen 7
  Dateien**, geändert = [] in allen 7, neu = genau die zwei erwarteten Keys.
- Diff-Umfang pro Datei: `3 +/1 -` — also keine Umformatierung, keine Neuserialisierung,
  Einrückung und Reihenfolge unberührt.
- Beide Keys werden verwendet (`mainwindow.py:2688-2689`), also keine Karteileichen.

### 6. Signal/Slot-Flow — empirisch verifiziert

- `game_stopped = Signal(bool)` (`game_panel.py:214`), Verbindung
  `self._game_panel.game_stopped.connect(self._unlock_ui)` (`mainwindow.py:436`).
- Alle drei `emit`-Stellen übergeben ein Argument (`2787`, `2799`, `2804`) — kein
  argumentloser Emit übrig geblieben.
- Der Default-Parameter ist **kein** Problem: mit einem laufenden `QApplication` geprüft —
  ein Slot `def slot(self, stopped: bool = True)` erhält an einer `Signal(bool)` tatsächlich
  `False` bzw. `True` (empfangen: `[False, True]`); ein parameterloser Slot an derselben
  Signal wird ebenfalls korrekt bedient. Der Default greift also nur beim Direktaufruf
  (`_unlock_ui(window)` in den Bestandstests) — genau wie beabsichtigt.
- Der Emit kommt aus dem Watcher-Thread, `GamePanel` lebt im GUI-Thread → Qt AutoConnection
  = QueuedConnection. Der `QMessageBox` in `_on_unlock_clicked` läuft dagegen aus dem
  Button-Klick, also im GUI-Thread. Korrekt.
- Der Button ist auf `lambda checked=False: self._on_unlock_clicked()` umgestellt — der
  `bool` von `clicked` wird korrekt abgefangen (bekannte Falle aus `CLAUDE.md`).

### 7. Imports

- `game_panel.py:16-19`: `find_game_process` neu importiert und benutzt; alle fünf bisherigen
  Namen (`clean_subprocess_env`, `clean_env`, `host_popen`, `host_open_url`, `host_open_path`)
  weiterhin verwendet — keine Waise durch die Umstellung auf Klammer-Import.
- Trotz Entfernen des lokalen `/proc`-Scans bleiben `os` (11 Verwendungen) und `Path`
  (20 Verwendungen) in `game_panel.py` nötig — kein toter Import.
- `debug_log.py`: `sys`, `datetime`, `Path` alle verwendet; `anvil_base_paths` bewusst lazy
  in der Funktion importiert (Basisverzeichnis muss vorher feststehen) — konsistent mit dem
  Lazy-Import-Muster in `main.py:110-118`.
- `subprocess_env.py`: `subprocess` wie im ganzen Modul funktionslokal importiert — konsistent.
- `mainwindow.py`: `QMessageBox` war bereits importiert.
- `py_compile` über alle sieben geänderten `.py`-Dateien: fehlerfrei.

### 8. Architektur-Regeln 1-5 und 7-8 (ARCHITEKTUR.md, Abschnitt 9)

| Regel | Ergebnis |
|---|---|
| 1 Keine Mod-Dateien direkt ins Game-Verzeichnis | nicht berührt |
| 2 `.mods/`-Struktur unverändert | nicht berührt |
| 3 Frameworks nicht in `.mods`/modlist.txt | nicht berührt |
| 4 Rename/Delete → `active_mods.json` in allen Profilen | nicht berührt |
| 5 Nur globale API, keine per-Profile modlist.txt | nicht berührt |
| 6 Deploy-/Purge-Mechanismus nur mit GO | siehe Governance-Hinweis oben |
| 7 Kein Flatten | nicht berührt |
| 8 MO2-Referenz vor Änderung an Mod-Verwaltung lesen | Diff berührt weder Mod-Verwaltung noch modlist.txt noch den Deployer — reine Prozessüberwachung, Logging und Dialogführung. Kein direktes MO2-Gegenstück (MO2 nutzt USVFS und kennt keinen Purge-Begriff; so bereits in `docs/anvil-feature-issue84-deploy-flatpak.md:107` dokumentiert). |

### 9. Tests

`python3 -m pytest tests/test_predeploy_launch.py -q` → **23 passed**.
Die neuen Testfälle prüfen sinnvolle Dinge und der narrative Docstring-Ton entspricht dem
Bestand in derselben Datei (`"""Pulling the mods out from under a running game crashes it."""`).
Der Vergleichstest zwischen lokalem Scan und Host-Snippet (`test_host_scan_snippet_matches_the_local_scan`)
ist die richtige Absicherung gegen ein Auseinanderlaufen der duplizierten Logik.
**Lücke:** kein Test für `_on_unlock_clicked` und keiner für den Ja-Zweig (siehe HIGH-Finding 1).

---

## Durchgeführte Prüfungen (Belege)

- `git status --porcelain`, `git diff --stat`, `git diff` je Datei
- Locale-Skript: Key-Präsenz in allen 7 Dateien + rekursiver Key-Diff `HEAD` vs. Arbeitsstand
- `git diff --numstat -- anvil/locales/` → 3/1 je Datei
- `python3 -m py_compile` über alle geänderten `.py`
- `python3 -m pytest tests/test_predeploy_launch.py -q` → 23 passed
- PySide6-Live-Test: `Signal(bool)` an Slot mit Default-Argument
- Live-Test: `sys.__excepthook__` schreibt in den **ersetzten** `sys.stderr` → Tracebacks landen
  tatsächlich in `debug.log` (der `_excepthook` in `main.py:121-125` funktioniert mit dem Tee)
- Live-Test: `Path("debug.log").with_suffix(".log.1")` → `debug.log.1` (Rotation korrekt,
  Python 3.13.14)
- `grep` auf `setStyleSheet`, MO2-Begriffe, absolute Pfad-Literale, Import-Nutzung,
  `debug_log_path`, `sys.stdout`/`sys.stderr`-Weitergabe an `subprocess`
- Stilmessung: Em-Dash- und Doppelleerzeichen-Häufigkeit im Bestand
- `git check-ignore -v 001Bericht/ …`, `.gitignore` gelesen
- `ARCHITEKTUR.md` (Wiki) Abschnitte 5, 6, 9, 10 gelesen; `restart.sh`, `activity_log.py`,
  `base_dir.py`, `main.py`, `diagnostics.py` gelesen
- Hinweis: `ruff` und `pyflakes` sind in dieser Umgebung nicht installiert; `pyproject.toml`
  definiert keine Lint-Konfiguration. Statische Prüfung daher über `py_compile` + gezielte greps.

---

## Ergebnis

**NEEDS FIXES** — 2 HIGH, 6 MEDIUM, 8 LOW.

Blockierend vor einem Commit:
1. HIGH — „Ja" im Unlock-Dialog muss tatsächlich purgen (`mainwindow.py:2693` / `2709`).
2. HIGH — `start_debug_log()` hinter den Single-Instance-Check verschieben (`main.py:117`).
3. Governance — ausdrückliches GO von Marc für die geänderten Purge-Auslöser einholen und
   ARCHITEKTUR.md nachziehen.

Sauber und ohne Beanstandung: Übersetzungen (alle 7 Locales, verlustfrei, minimaler Diff),
Signal/Slot-Verdrahtung, Imports, keine hardcoded Pfade, kein `setStyleSheet`, keine
MO2-Erwähnungen, AI-Sichtbarkeit (Stil ist am Bestand ausgerichtet und messbar unauffällig).
