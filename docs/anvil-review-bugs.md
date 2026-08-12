# Code-Review — Game-Watcher / Flatpak-PID-Namespace / debug_log
Datum: 2026-08-06
Geprüft: uncommittete Änderungen (`git status`) + neue Datei `anvil/core/debug_log.py`

## Prüfumfang und Belege
- `git diff` aller 12 geänderten Dateien gelesen
- `python -m py_compile` für alle geänderten Module → OK
- `python -m pytest tests/ --ignore=tests/test_base_migration_dialog.py -q` → **291 passed, 1 skipped**
- Signal-Zustellung `Signal(bool)` → `_unlock_ui(stopped=True)` real getestet (PySide6, offscreen) → Slot empfängt `False`/`True` korrekt
- Rotation von `debug.log` real getestet → erzeugt `debug.log.1` / `debug.log.2`, `debug.log.3` entsteht nicht (korrekt, `_MAX_BACKUPS=2`)
- `_Tee` mit `stream=None` real getestet → `write()`/`flush()`/`isatty()` OK, `fileno()` wirft `OSError`
- Host-Scan **end-to-end im echten Flatpak-Sandbox** getestet
  (`flatpak run --command=sh com.github.Marc1326.AnvilOrganizer`):
  - Sandbox-`/proc` listet nur **4** PIDs → das beschriebene Problem ist bestätigt
  - `_HOST_SCAN` über `flatpak-spawn --host python3` fand den Host-Testprozess (PID 1327042) → **der Fix funktioniert**
  - `flatpak-spawn --host false` → rc=1, `flatpak-spawn --host kein-solcher-befehl` → rc=1 und **leeres stdout**
    → die Unterscheidung „Scan lief" / „Scan lief nicht" über den Returncode trägt auf diesem System
  - stdin wird korrekt an den Host-Prozess durchgereicht

**Der eigentliche Fix ist richtig und wirksam.** Die folgenden Befunde betreffen Folgeverhalten.

---

## Findings

### [HIGH] Ein bestätigtes „Ja" im Entsperren-Dialog kann folgenlos verpuffen
- Datei: `anvil/mainwindow.py:2686-2693` zusammen mit `2704-2716`
- Problem: `_on_unlock_clicked()` fragt den Benutzer ausdrücklich „Mods jetzt entfernen?" und
  gibt die Antwort als `stopped=True` weiter. `_unlock_ui(True)` verwirft diese Entscheidung
  aber sofort wieder und ruft erneut `self._game_panel.is_game_running()` auf. Dieses liefert
  laut neuer Semantik (`game_panel.py:2746-2749`) **True, sobald der Lookup unzuverlässig ist** —
  also genau in dem Flatpak-Fall, für den der Dialog überhaupt eingebaut wurde.
  Ergebnis: der Benutzer bestätigt das Entfernen, es passiert nichts, und er bekommt
  **keinerlei Rückmeldung** (nur eine `print()`-Zeile ins Log).
  Der Docstring „the decision belongs to the user rather than to a guess" wird vom Code nicht eingelöst.
- Fix: die Benutzerentscheidung durchreichen (z. B. `_unlock_ui(stopped=True, forced=True)`,
  das den Re-Check überspringt) — und wenn der Purge trotzdem unterbleibt, das dem Benutzer
  sichtbar melden (Statusbar/QMessageBox), nicht nur ins Log schreiben.

### [HIGH] Der „Nie aufgetaucht"-Timeout ist keine Zeitgrenze mehr — UI kann ~40 Minuten gesperrt bleiben
- Datei: `anvil/widgets/game_panel.py:2713-2715` und `2767-2774`
- Problem: `_GAME_APPEAR_TIMEOUT = 120` zählt Schleifendurchläufe. Solange der Lookup lokal
  war (`os.scandir("/proc")`, Millisekunden), entsprach das ≈120 Sekunden. Jetzt kostet **ein**
  Durchlauf im Flatpak zusätzlich die Laufzeit des Host-Aufrufs — im Fehlerfall
  `_HOST_SCAN_TIMEOUT = 10` s für den python3-Versuch **plus** 10 s für den `ps`-Fallback
  (`subprocess_env.py:196-241`). Worst Case: 21 s × 120 = **~42 Minuten**, bevor
  `game_stopped(False)` gefeuert wird. So lange bleibt das Lock-Overlay stehen.
  Zusätzlich: auch im Gutfall werden im Flatpak bis zu 120 Host-Prozesse im Sekundentakt
  gestartet, die jeweils **alle** `/proc/<pid>/environ` des Hosts lesen.
- Fix: Abbruch über `time.monotonic()`-Deadline statt Iterationszähler; nach z. B. 3
  aufeinanderfolgenden unzuverlässigen Ergebnissen sofort abbrechen (weitere Versuche sind
  ohnehin aussichtslos); Poll-Abstand in der Appear-Phase im Flatpak erhöhen.

### [MEDIUM] Ein einzelner fehlgeschlagener Lookup beendet die Überwachung endgültig
- Datei: `anvil/widgets/game_panel.py:2791-2801`
- Problem: In der Laufschleife führt **ein** `reliable == False` sofort zu
  `game_stopped.emit(False)` + `return`. Es gibt keinen Wiederholungsversuch. Ein einmaliges
  Überschreiten des 10-s-Timeouts (Systemlast beim Spielstart ist genau der Normalfall)
  beendet die Überwachung dauerhaft: die UI entsperrt mitten im Spiel und nach dem Spielende
  räumt niemand mehr auf (kein `game_stopped(True)` mehr möglich).
- Fix: erst nach N aufeinanderfolgenden Fehlversuchen aufgeben, dazwischen weiterpollen.

### [MEDIUM] Watch-Daten werden nie zurückgesetzt → `is_game_running()` kann dauerhaft True liefern
- Datei: `anvil/widgets/game_panel.py:2734, 2761-2762`
- Problem: `_watch_binary` / `_watch_app_id` werden beim Start gesetzt und **nie** wieder
  geleert. Sobald in einer Sitzung einmal gestartet wurde und der Host-Lookup dauerhaft
  fehlschlägt (fehlendes `--talk-name=org.freedesktop.Flatpak`, kein `python3` **und** kein
  `ps` auf dem Host), liefert `is_game_running()` für den Rest der Sitzung True. Folgen:
  - `mainwindow.py:7059` — `closeEvent` purged **nie** mehr
  - `mainwindow.py:1016` und `1078` — Basisverzeichnis-Migration und Instanz-Verschiebung
    werden dauerhaft mit `storage.error_game_running` abgelehnt, obwohl kein Spiel läuft
  Es gibt keinen benutzerseitigen Ausweg (der Entsperren-Dialog hilft wegen Finding 1 nicht).
- Fix: Watch-Daten beim Eintreffen von `game_stopped` löschen; zusätzlich einen „Lookup
  dauerhaft kaputt"-Zustand einmalig ermitteln und dem Benutzer eine Override-Möglichkeit geben.

### [MEDIUM] `is_game_running()` blockiert bis zu 20 s im GUI-Thread
- Datei: `anvil/mainwindow.py:1016, 1078, 2709, 7059`
- Problem: Der Aufruf ist synchron und startet im Flatpak `subprocess.run(...)` mit
  `timeout=10`, im Fehlerfall zweimal hintereinander (python3-Versuch + `ps`-Fallback).
  Diese Aufrufe laufen im Qt-Hauptthread. Besonders unangenehm in `closeEvent`: das Fenster
  bleibt beim Schließen bis zu 20 s stehen.
- Fix: für die synchronen GUI-Aufrufe einen deutlich kürzeren Timeout verwenden, oder das
  letzte Ergebnis des Watcher-Threads zwischenspeichern und im GUI-Thread nur lesen.

### [MEDIUM] Fehlgeschlagener Spielstart lässt die Mods jetzt immer deployt zurück
- Datei: `anvil/widgets/game_panel.py:2776-2788`, Kommentar `2713-2714`
- Problem: Der „nie aufgetaucht"-Zweig feuert **immer** `game_stopped(False)` — auch dann,
  wenn der Lookup die ganze Zeit zuverlässig war (nativer Start ohne Flatpak, Spiel ist beim
  Start abgestürzt oder wurde gar nicht gestartet). `_unlock_ui(False)` überspringt dann den
  Purge grundsätzlich, obwohl sicher feststeht, dass nichts läuft. Vorher hat MainWindow
  gegengeprüft und aufgeräumt.
  Der Kommentar in Zeile 2713-2714 („Running out is not dangerous any more: MainWindow
  re-checks before removing anything") beschreibt genau dieses Gegenprüfen — das findet mit
  `emit(False)` aber nicht mehr statt. Kommentar und Code widersprechen sich.
- Fix: `self.game_stopped.emit(not lookup_broken)` — bei zuverlässigem Lookup wieder `True`
  senden und MainWindow gegenprüfen lassen; den Kommentar entsprechend anpassen.

### [LOW] `start_debug_log()` kann entgegen seinem Docstring werfen
- Datei: `anvil/core/debug_log.py:91-105`, aufgerufen in `anvil/main.py:118`
- Problem: Der Docstring sagt „Wirft nie", gefangen wird aber nur `OSError`.
  `anvil_base_paths()` → `resolve_base_dir()` (`base_dir.py:58-65`) ruft `Path(raw).expanduser()`
  auf, das `RuntimeError` werfen kann, wenn das Home-Verzeichnis nicht auflösbar ist; auch
  QSettings-/Import-Fehler sind nicht abgedeckt. Der Aufruf steht unbedingt im Startpfad —
  eine Exception dort verhindert den kompletten App-Start, und zwar wegen des Loggings.
- Fix: `except Exception` statt `except OSError`.

### [LOW] `_Tee` ist ein sehr unvollständiges Stream-Objekt
- Datei: `anvil/core/debug_log.py:52-88`
- Problem: Implementiert sind nur `write`, `flush`, `isatty`, `fileno`. Real geprüft fehlen
  u. a. `close`, `writelines`, `encoding`, `errors`, `buffer`, `writable`, `closed`.
  Im Anvil-Code selbst nutzt aktuell nichts davon (geprüft: kein `logging.StreamHandler`,
  kein `faulthandler`, kein `stdout=sys.stdout`), akut bricht also nichts. Eine Fremdbibliothek,
  die `sys.stderr.encoding` liest, würde aber `AttributeError` bekommen — und der landet dann
  ausgerechnet in der Fehlerbehandlung.
  Ebenso wirft `fileno()` `OSError`, wenn `sys.__stdout__` None ist (fensterloser/gefrorener
  Start); für einen Aufrufer, der einen Descriptor erwartet, ist das ein harter Fehler.
- Fix: `io.TextIOBase` ableiten bzw. `encoding`/`errors`/`writelines`/`close` nachreichen und
  `__getattr__` an den Originalstream delegieren.

### [LOW] Rotation greift nur beim Start
- Datei: `anvil/core/debug_log.py:27-49`, aufgerufen ausschließlich in `start_debug_log()`
- Problem: Die 2-MB-Grenze wird nur einmal beim Programmstart geprüft. In einer langen
  Sitzung mit gesprächigem Deploy-Logging (`_dlog` schreibt jede Zeile zusätzlich per `print`)
  wächst `debug.log` unbegrenzt über die Grenze hinaus.
  (Die Dateinamen selbst sind korrekt — real getestet: `debug.log.1`, `debug.log.2`.)
- Fix: geschriebene Bytes in `_Tee.write` mitzählen und bei Überschreiten rotieren, oder
  `logging.handlers.RotatingFileHandler` verwenden.

### [LOW] Re-Entranz: Purge kann während des offenen Entsperren-Dialogs doppelt laufen
- Datei: `anvil/mainwindow.py:2686-2693`
- Problem: `QMessageBox.question()` betreibt eine eigene Event-Loop. Trifft in dieser Zeit
  `game_stopped(True)` aus dem Watcher-Thread ein, läuft `_unlock_ui(True)` **im** Dialog durch
  (inkl. `silent_purge()` und Ausblenden des Overlays); danach kehrt der Dialog zurück und
  `_unlock_ui(answer)` läuft ein zweites Mal. Der zweite Purge ist zwar folgenlos, der Dialog
  fragt aber nach etwas, das bereits passiert ist.
- Fix: den Dialog nur zeigen, wenn `self._lock_overlay.isVisible()`, bzw. ein Re-Entranz-Flag setzen.

### [LOW] Toter Vergleich in `log_sources()`
- Datei: `anvil/core/diagnostics.py:252`
- Problem: `dbg != dbg_log` vergleicht `<projektroot>/debug.log` mit `<base>/logs/debug.log`.
  Die beiden Pfade können konstruktionsbedingt nie gleich sein, die Dedup-Bedingung ist immer wahr.
  Harmlos, aber sie suggeriert eine Absicherung, die es nicht gibt.
- Fix: entfernen oder auf `resolve()`-Basis gegen alle bereits gesammelten Pfade prüfen.

---

## Ausdrücklich geprüft und in Ordnung
- **Signal-Signatur `Signal()` → `Signal(bool)`:** einzige `connect()`-Stelle ist
  `mainwindow.py:436` (`self._unlock_ui`), alle drei `emit()`-Stellen übergeben ein bool.
  Zustellung an einen Slot mit Default-Argument real mit PySide6 verifiziert.
  `_unlock_ui` wird sonst nur mit explizitem Argument gerufen (2684, 2693).
- **`lookup_game_pid()` bei nichts gestartetem Spiel:** `game_panel.py:2734` liefert
  `(None, True)` → `is_game_running()` False → Purge beim Schließen findet normal statt,
  solange in der Sitzung nie gestartet wurde. Kein dauerhafter Blocker im Normalfall.
- **Selbstfund-Falle:** Der Suchbegriff läuft über stdin, nicht über argv — im echten Sandbox
  bestätigt. `scan_proc_for_game()` überspringt zusätzlich die eigene PID. Die neue
  Kleinschreibung auf **beiden** Seiten (`binary_name.lower()` und `read().lower()`) behebt
  nebenbei einen alten Fehler: vorher wurde der Suchbegriff nicht kleingeschrieben, ein
  `GameBinary` mit Großbuchstaben konnte nie matchen.
- **Zombie-Fehltreffer:** Der Launch-Wrapper wird im „aufgetaucht"-Zweig nicht mehr `wait()`et
  und bleibt als Zombie stehen — Zombies haben leeres `cmdline`/`environ`, ein Fehltreffer
  entsteht daraus nicht.
- **Locale-Keys:** `dialog.unlock_purge_title` und `dialog.unlock_purge_text` sind in **allen
  sieben** Locale-Dateien vorhanden (de, en, es, fr, it, pt, ru) — per JSON-Parser geprüft.
- **Imports/tote Variablen:** keine verwaisten Imports. `os` wird in `game_panel.py` weiterhin
  an 11 Stellen benutzt. `find_game_pid()` wird nach dem Umbau nur noch von den Tests
  verwendet — bewusst als Kompatibilitäts-Wrapper stehengelassen, kein Defekt.
- **Signal-Emission aus dem Thread:** `game_stopped` wird per Auto-Connection in den GUI-Thread
  gequeued; der Watcher ist Daemon, `main.py:172` beendet mit `os._exit()`. Kein Hänger beim Beenden.
- **Architektur:** Der Deploy-/Purge-Mechanismus selbst (Symlinks, Manifest, Frameworks,
  `.mods/`-Struktur, `modlist.txt`) wurde nicht angefasst. Geändert wurde nur der Zeitpunkt,
  zu dem gepurged wird. Die Schutzregeln aus ARCHITEKTUR.md Abschnitt 5/6 sind eingehalten.

---

## Ergebnis
**NEEDS FIXES** — 2× HIGH, 4× MEDIUM, 4× LOW.
Der Kern des Fixes (Host-Scan über `flatpak-spawn`, `reliable`-Flag, kein Purge bei
unbekanntem Zustand) ist korrekt und im echten Sandbox verifiziert. Nachzuarbeiten sind vor
allem: die folgenlose Ja-Antwort im Entsperren-Dialog, der entgleiste Appear-Timeout, das
Aufgeben nach einem einzigen Fehlversuch und die nie zurückgesetzten Watch-Daten.
