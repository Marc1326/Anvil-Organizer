# QA-Nachprüfung — Spielprozess-Überwachung, Purge-Guards, debug.log
Datum: 2026-08-06
Geprüfter Stand: nicht committete Änderungen gegen `d174cd6` (v1.7.0)

## Vorgehen (ausgeführt, nicht angenommen)
- `git status --porcelain`, `git diff HEAD` (15 Dateien, +798/-97)
- Vollständig gelesen: `anvil/core/game_process.py`, `anvil/core/debug_log.py`,
  Diffs von `mainwindow.py`, `game_panel.py`, `main.py`, `diagnostics.py`,
  `tests/test_predeploy_launch.py`, Flatpak-Manifest, alle 7 Locale-Diffs
- `python3 -m py_compile` über alle geänderten Python-Dateien → OK
- `python3 -m pytest tests/ -q --ignore=tests/test_base_migration_dialog.py`
  → **297 passed, 1 skipped** (1,44 s)
- JSON-Validierung aller 7 Locales + Key-Existenz → alle drei neuen Keys in
  de/en/es/fr/it/pt/ru vorhanden
- Eigene Laufzeit-Experimente (Skripte im Scratchpad):
  `_rotate`, `game_state()`-Cache, Watcher-Ablauf „nie erschienen“,
  zwei parallele Watcher, Re-Entranz eines Signals während eines modalen Dialogs
- Gelesen: `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md`
- `ls /home/mob/Projekte/mo2-referenz` → **existiert nicht** (siehe INFO-2)

---

## Teil 1 — Status der 9 Befunde aus der ersten Runde

| # | Befund | Status |
|---|--------|--------|
| 1 | Bestätigtes „Ja“ verpuffte | ✅ behoben |
| 2 | Timeout war Iterationszähler | ✅ behoben |
| 3 | Ein Fehlschlag beendete die Überwachung | ✅ behoben |
| 4 | `_watch_binary` nie zurückgesetzt | ⚠️ teilweise — neuer Nebeneffekt, siehe HIGH-1/HIGH-2/MEDIUM-1 |
| 5 | `is_game_running()` blockiert den GUI-Thread | ⚠️ deutlich verbessert, nicht vollständig |
| 6 | `emit(False)` auch bei zuverlässigem Lookup | ✅ behoben |
| 7 | `start_debug_log()` „wirft nie“ | ⚠️ nicht vollständig |
| 8 | `_Tee` ohne writelines/encoding | ✅ behoben |
| 9 | Re-Entranz während des Dialogs | ❌ nicht behoben (praktisch belegt) |

### 1 — ✅ behoben
`_on_unlock_clicked` (mainwindow.py:2695-2719) führt das „Ja“ direkt aus:
`_game_running = False` → `_purge_after_game()` → `_release_ui_lock()`, ohne
`is_game_running()` erneut zu fragen. `_unlock_ui(False)` wird nur bei
„Nein“/kein Deployment benutzt. Testabdeckung vorhanden
(`test_confirmed_unlock_removes_the_deployment`, `test_declined_unlock_keeps_the_deployment`).

### 2 — ✅ behoben
`deadline = time.monotonic() + self._GAME_APPEAR_TIMEOUT`, Schleife
`while time.monotonic() < deadline` (game_panel.py:2815-2822). Echte Zeitgrenze;
Worst Case 120 s + ein Lookup (max. 2 × `_HOST_SCAN_TIMEOUT` = 6 s).

### 3 — ✅ behoben
Lauf-Schleife: `blind_since` + `_GAME_LOOKUP_GRACE = 60` (game_panel.py:2842-2861).
Ein einzelner Fehlschlag setzt nur den Startzeitpunkt; erst nach > 60 s
durchgehender Blindheit wird mit `emit(False)` aufgegeben, ohne zu purgen.

### 4 — ⚠️ teilweise
`_clear_watch_target()` existiert (game_panel.py:2745-2749) und wird bei
bestätigtem Ende gerufen. Zwei Nebeneffekte:
- Die Löschung passiert im „nie erschienen“-Pfad zu früh → **HIGH-1**
- Ein alter Watcher kann das Ziel eines neuen löschen → **HIGH-2**
- Die Migration wurde auf `game_state() == GAME_RUNNING` umgestellt, damit sie
  nicht dauerhaft blockiert — dadurch purged sie bei UNKNOWN ungeschützt → **MEDIUM-1**
- Im blinden Aufgeben-Pfad (`emit(False)`, game_panel.py:2857) bleibt das Ziel
  bewusst gesetzt: Purge bleibt bis zum Anvil-Neustart blockiert. Beim nächsten
  Anvil-Start ist `_watch_binary` leer → `_do_redeploy` räumt auf. Verhalten OK.

### 5 — ⚠️ verbessert, nicht vollständig
Gemessen (Skript `t_state.py`):
- RUNNING/UNKNOWN werden aus dem Zwischenspeicher beantwortet → 0 Lookups
- STOPPED wird **nie** aus dem Zwischenspeicher beantwortet → immer frischer Lookup
- Ohne Watch-Ziel: sofort STOPPED, 0 Lookups

Ein synchroner Lookup auf dem GUI-Thread bleibt möglich in genau diesen Fällen:
Watcher hat gerade STOPPED notiert (Startphase), Zwischenspeicher älter als 15 s,
oder noch gar keine Messung. Betroffen: `closeEvent`, `_do_redeploy`,
`_predeploy_for_launch`, Migrationsprüfungen. Obergrenze laut Code jetzt
2 × 3 s = 6 s statt 20 s (`_HOST_SCAN_TIMEOUT = 3`, ps-Fallback nur bei
`_SCAN_FAILED`, game_process.py:149-153).

### 6 — ✅ behoben
`self.game_stopped.emit(blind_since is None)` (game_panel.py:2838): zuverlässiger
Lookup ohne Fund → `True` → das Deployment wird aufgeräumt.

### 7 — ⚠️ nicht vollständig
`start_debug_log()` (debug_log.py:99-122) fängt OSError/RuntimeError/ValueError
nur um Import, mkdir, `_rotate` und `open`. **Außerhalb** des try liegen
`handle.write(...)` und `handle.flush()` (Zeile 118/119) — ein voller Datenträger
wirft dort OSError, und `main.py:153` ruft ohne Schutz auf → Absturz beim Start.
Auch ein ImportError aus `from anvil.core.base_dir import anvil_base_paths`
ist nicht gefangen. Docstring „Wirft nie“ stimmt also weiterhin nicht.

### 8 — ✅ behoben
`writelines`, `encoding` (Property mit utf-8-Fallback), `flush`, `isatty`,
`fileno` vorhanden; `write` gibt korrekt `len(data)` zurück; `_stream=None`
wird überall abgefangen. Rest siehe LOW-9.

### 9 — ❌ nicht behoben
Kein Guard in `_on_unlock_clicked`, kein `blockSignals`, kein Disconnect.
Praktisch belegt (Skript `t_reentrant.py`, offscreen Qt): ein aus einem
Fremd-Thread emittiertes Signal wird **während** `QMessageBox.exec()` zugestellt.
Reihenfolge der Messung: `[('unlock_ui', True), ('dialog_beantwortet', 'Yes')]`.
Folge: `_unlock_ui(True)` purged + entsperrt, danach purged das „Ja“ ein zweites
Mal und entsperrt erneut. Auswirkung gering (zweiter Purge ist ein No-Op über
das leere Manifest), aber „Nein“ kann nach bereits erfolgtem Purge nichts mehr
retten.

---

## Teil 2 — Neue Befunde

### [HIGH-1] `_clear_watch_target()` läuft vor `proc.wait()` — Spiel wird unsichtbar, obwohl es läuft
- Datei: `anvil/widgets/game_panel.py:2824-2839`
- Problem: Im Zweig „Prozess nie erschienen, Lookup war zuverlässig“ wird
  `self._clear_watch_target()` aufgerufen **bevor** `proc.wait()` blockiert und
  bevor `game_stopped` gesendet wird. `proc` ist bei Direkt-/Proton-Start der
  gestartete Prozess und kann Stunden laufen. In diesem Fenster liefert
  `game_state()` sofort `stopped` (kein Watch-Ziel mehr) und
  `is_game_running()` `False` → `closeEvent`, `_do_redeploy`, Instanz- und
  Profilwechsel entfernen das Deployment unter dem laufenden Spiel.
- Beleg (Skript `t_watcher.py`, Timeout 2 s, `proc.wait()` blockiert):
  `A) während proc.wait(): _watch_binary=''  state=stopped  is_running=False  emits=[]`
- Zweiter Aspekt: Erscheint das Spiel nach Ablauf der 120 s doch (Steam-Shader,
  langsame Platte), wird es für den Rest der Sitzung **nie** wieder erkannt,
  weil das Watch-Ziel weg ist. Der Kommentar über `_GAME_APPEAR_TIMEOUT`
  („Running out is not dangerous any more: MainWindow re-checks before removing
  anything“) trifft damit nicht mehr zu — der Re-Check kann nichts mehr finden.
- Fix: Erst `proc.wait()` (falls vorhanden), danach ein letzter Lookup; nur bei
  `(None, True)` `_clear_watch_target()` + `emit(True)`. Findet der letzte
  Lookup den Prozess doch, in die Lauf-Schleife wechseln statt aufzugeben.
  Kommentar an `_GAME_APPEAR_TIMEOUT` entsprechend korrigieren.

### [HIGH-2] Kein Watcher-Token: ein alter Watcher löscht das Ziel eines neuen
- Datei: `anvil/widgets/game_panel.py:2800-2865` (`_start_process_watcher`)
- Problem: Der Thread hat keine Generation/Identität. Startet ein zweiter
  Watcher (zweiter Startversuch nach dem Entsperren, anderes Spiel nach
  Instanzwechsel), löscht der erste beim Ablaufen seines Zeitfensters mit
  `_clear_watch_target()` das Ziel des zweiten und sendet `game_stopped(True)`.
  Danach liefert `lookup_game_pid()` des zweiten Watchers `(None, True)` —
  er meldet ebenfalls „gestoppt“, obwohl das Spiel läuft.
- Beleg (Skript `t_watcher2.py`, Spiel läuft nachweislich):
  `t=2.2 (Watcher1 timeout vorbei): _watch_binary='' state=stopped is_running=False emits=[True]`
  `t=3.2 (Spiel läuft weiter):      _watch_binary='' state=stopped is_running=False emits=[True]`
  → `_unlock_ui(True)` purged hier unter dem laufenden Spiel.
- Erreichbarkeit: Solange Watcher 1 in der Suchphase nichts findet, ist der
  Zustand `stopped`, damit lässt `_predeploy_for_launch` einen zweiten Start zu.
- Fix: Bei jedem Start ein Token hochzählen (`self._watch_token += 1`), Token in
  der Closure festhalten; `_clear_watch_target()`, `_note_game_state()` und
  `game_stopped.emit()` nur ausführen, wenn das eigene Token noch das aktuelle ist.

### [MEDIUM-1] Migration purged bei unbekanntem Spielstatus ungeschützt
- Datei: `anvil/mainwindow.py:1016`, `:1078` (Guard) und `:1047`, `:1128` (Purge)
- Problem: Beide Migrationspfade prüfen nur `game_state() == GAME_RUNNING`.
  Bei UNKNOWN (blinder Lookup, z. B. Flatpak ohne funktionierendes
  `flatpak-spawn`) laufen sie durch und rufen `silent_purge()` je Instanz auf —
  genau das, was alle anderen Pfade über `is_game_running()` (UNKNOWN → True)
  verhindern. Zwei Sicherheitsstufen für dieselbe Frage.
- Fix: Entweder auch hier `is_game_running()` verwenden, oder bei UNKNOWN einen
  eigenen Bestätigungsdialog zeigen („Status nicht feststellbar — trotzdem
  fortfahren?“). Die bewusste Abweichung sonst im Code kommentieren.

### [MEDIUM-2] GRB- und REDmod-Startpfade umgehen den neuen „Spiel läuft“-Guard
- Datei: `anvil/widgets/game_panel.py:1946-1956` (Forge) und `:1961-1965` (REDmod)
- Problem: Beide rufen `silent_deploy()` direkt, ohne `_predeploy_hook`
  (= `_predeploy_for_launch`). Der neue Schutz gegen einen zweiten Start bei
  laufendem Spiel greift dort nicht; für GRB wird der Hook danach zusätzlich
  über `forge_done` übersprungen (Zeile 1970-1971).
- Fix: Den Zustandscheck vor die Verzweigung in `_on_start_clicked` ziehen,
  damit alle Startpfade ihn durchlaufen.

### [MEDIUM-3] Zwei widersprüchliche Dialoge, wenn der Start blockiert wird
- Datei: `anvil/mainwindow.py:2577-2581` + `:2615-2619`, ebenso
  `anvil/widgets/game_panel.py:1972-1978`
- Problem: `_predeploy_for_launch` zeigt selbst „Es läuft noch ein Spiel …“ und
  gibt `False` zurück; die Aufrufer werten `False` als Deploy-Fehler und zeigen
  direkt danach „Die Mods konnten nicht ins Spiel deployed werden“. Der Nutzer
  sieht zwei Meldungen, die zweite ist falsch.
- Fix: Eigenen Rückgabewert/Sentinel für „bewusst abgelehnt“ oder den Guard in
  die Aufrufer verschieben.

### [LOW-1] Re-Entranz (alter Befund 9) — siehe oben, offen
- Fix: `self._unlock_dialog_open`-Flag setzen und in `_unlock_ui` früh
  zurückkehren, oder den Dialog vor dem Öffnen von `game_stopped` trennen.

### [LOW-2] `start_debug_log()` kann doch werfen — siehe alter Befund 7
- Datei: `anvil/core/debug_log.py:100`, `:118-119`
- Fix: Schreiben des Kopfzeilen-Stempels in den try-Block ziehen bzw. eigenen
  try, `ImportError` mitfangen oder Docstring korrigieren.

### [LOW-3] Irreführende Logzeile beim Entsperren ohne Deployment
- Datei: `anvil/mainwindow.py:2702-2703`
- Problem: `_unlock_ui(False)` protokolliert „game state unknown — keeping the
  deployment“, obwohl es gar kein Deployment gibt.
- Fix: eigener Zweig, der nur entsperrt.

### [LOW-4] Nach bestätigtem manuellem Purge kein `_clear_watch_target()`
- Datei: `anvil/mainwindow.py:2715-2719`
- Problem: Der Watcher läuft weiter; endet das Spiel später, purged
  `_unlock_ui(True)` ein zweites Mal (No-Op) und schreibt vollständige
  Purge-Logs für nichts. Kein Datenschaden.

### [LOW-5] Kosten der Suchphase in der Sandbox
- Datei: `anvil/widgets/game_panel.py:2822` (`time.sleep(1)`)
- Problem: In Flatpak bis zu 120 Host-Prozesse à 1 s in der Suchphase
  (Lauf-Phase dagegen 5 s). Zusätzlich beendet `subprocess.run(..., timeout=)`
  bei einem Timeout `flatpak-spawn`; der auf dem Host gestartete `python3` kann
  verwaisen und sich bei wiederholten Timeouts ansammeln.
- Fix: Suchintervall auf 2 s anheben und/oder nach einem Timeout die Host-Suche
  für einen Zyklus aussetzen.

### [LOW-6] `debug.log` wird nur beim Start rotiert
- Datei: `anvil/core/debug_log.py:104-110`
- Problem: In einer langen Sitzung wächst die Datei unbegrenzt über die 2 MB
  hinaus; die Grenze wirkt erst beim nächsten Start.

### [LOW-7] Startfehler vor der Basisverzeichnis-Auswahl landen in keinem Log
- Datei: `anvil/main.py:107-153`
- Problem: `start_debug_log()` läuft erst nach `_ensure_base_directory()` und
  dem Single-Instance-Check. Genau die häufigen Startprobleme (Basisverzeichnis
  fehlt/nicht schreibbar) werden weiterhin nicht mitgeschrieben. Technisch
  nachvollziehbar (das Log liegt im Basisverzeichnis), sollte aber bekannt sein.

### [LOW-8] Stil: fehlende Leerzeile
- Datei: `anvil/widgets/game_panel.py:36-37` — zwischen `_state_of` und `_dlog`
  steht nur eine Leerzeile (PEP8 E302). Im Projekt ist kein Linter konfiguriert
  (kein ruff/flake8 in `pyproject.toml`, beide Module fehlen im venv), daher rein
  kosmetisch.

### [LOW-9] `_Tee` ohne `buffer`/`close`
- Datei: `anvil/core/debug_log.py:52-96`
- Problem: Code, der `sys.stdout.buffer` (Binärausgabe) oder `sys.stdout.close()`
  erwartet, bekommt AttributeError. Im aktuellen Anvil-Code nicht nachweisbar
  genutzt, bei Fremdbibliotheken aber möglich.
- Fix: `buffer`-Property auf den Originalstream durchreichen, `close()` als No-Op.

---

## Teil 3 — Bewertung der neu eingeführten Konstrukte (gefragte Punkte)

### Zustandsmodell `game_state()` / `_game_state` / TTL 15 s
- **Wer schreibt:** ausschließlich `_note_game_state()` (game_panel.py:2785-2788),
  aufgerufen nur aus dem Watcher-Thread (Zeilen 2819, 2845) — per Grep bestätigt.
  Zusätzlich setzen `_start_process_watcher()` und `_clear_watch_target()` den
  Wert auf `None`.
- **Wer liest:** ausschließlich `game_state()` (Zeile 2773).
- **Veralteter Wert → Purge?** Nein. Gemessen: STOPPED wird nie aus dem
  Zwischenspeicher beantwortet, RUNNING/UNKNOWN blockieren einen Purge ohnehin.
  Ein Purge setzt STOPPED voraus, und STOPPED entsteht nur aus einem frischen
  Lookup **oder** aus „kein Watch-Ziel“. Genau der zweite Weg ist die Lücke →
  HIGH-1/HIGH-2.
- Nebenwirkung: Ein zwischengespeichertes RUNNING kann einen legitimen Start bis
  zu 15 s lang verweigern (`_predeploy_for_launch`). Akzeptabel.

### Thread-Sicherheit
- `_game_state` wird als vollständiges Tupel zugewiesen — unter dem GIL atomar,
  kein Riss beim Lesen. OK.
- `_clear_watch_target()` setzt drei Attribute nacheinander. Liest der GUI-Thread
  dazwischen, ist `_watch_app_id` noch gesetzt → es folgt ein regulärer Lookup,
  kein falsches STOPPED. OK.
- Das eigentliche Problem ist keine Datenrace, sondern fehlende Zuordnung
  Watcher → Ziel (HIGH-2).

### `_clear_watch_target()`
- Aufrufstellen: game_panel.py:2833 (nie erschienen, zuverlässig) und 2862
  (bestätigtes Ende). Zweite Stelle korrekt. Erste Stelle zu früh → HIGH-1.
- Nicht aufgerufen im blinden Aufgeben-Pfad — richtig so.
- Nicht aufgerufen nach dem manuell bestätigten Purge → LOW-4.

### Grace-Period `_GAME_LOOKUP_GRACE = 60`
- Korrekt implementiert: `blind_since` wird beim ersten Fehlschlag gesetzt, bei
  jedem zuverlässigen Lookup zurückgesetzt, Abbruch erst bei > 60 s. Bei
  `_GAME_POLL_INTERVAL = 5` sind das mindestens 13 Fehlversuche. Beim Aufgeben
  wird `emit(False)` gesendet und **nicht** gepurged. Richtig.
- In der Suchphase gibt es bewusst keinen Grace-Abbruch; dort entscheidet allein
  der letzte Lookup, ob als „blind“ oder „gestoppt“ gemeldet wird. Logisch
  korrekt, weil nur der letzte Lookup die aktuelle Aussage trägt.

### `notify_game_started(pid, binary, proc)`
- `mainwindow.py:2637-2639` reicht `plugin.GameBinary or binary_path` und den
  Popen durch; `_start_process_watcher(Path(binary).name.lower(), proc=proc)`.
- Alle Plugins verwenden Forward-Slashes in `GameBinary` (geprüft:
  `bin/x64/Cyberpunk2077.exe`, `SB/Binaries/Win64/SB-Win64-Shipping.exe`, …),
  `Path(...).name` liefert also den richtigen Namen. OK.
- Keine Doppelüberwachung: Steam läuft über `_launch_via_steam`, Proton über
  `_launch_via_proton`, der Direktstart über `start_requested` →
  `_on_start_game` → `notify_game_started`. Die Pfade schließen sich aus.
- `binary=""` (kein Plugin, kein Pfad) startet keinen Watcher — dann bleibt es
  beim alten Verhalten „Deployment bleibt liegen“. Vertretbar.

### Neue Guards
- `_do_redeploy` (mainwindow.py:2309): korrekt, gibt `True` zurück (kein
  Fehlerdialog), Test vorhanden.
- `_teardown_current_instance` (1629), Profilwechsel (4702), `closeEvent` (7091):
  einheitlich `self._game_running or self._game_panel.is_game_running()`. Korrekt
  konservativ. Konsequenz: Bei blindem Lookup bleibt das Deployment über das
  Schließen hinaus liegen und wird erst beim nächsten Anvil-Start bzw.
  Spielstart entfernt — gewollt und dokumentiert im Code-Kommentar.
- `_predeploy_for_launch` (2574): siehe MEDIUM-2 (Lücken) und MEDIUM-3 (Dialoge).

### Weitere geprüfte Punkte ohne Befund
- `find_game_process()` liefert `(None, True)` wenn nichts zu suchen ist —
  „nichts gestartet“ gilt korrekt als zuverlässige Antwort (Test vorhanden).
- Der Host-Schnipsel bekommt den Suchnamen über **stdin**, steht also nicht in
  der eigenen Kommandozeile — die alte Selbstfundstelle ist ausgeschlossen und
  durch zwei Tests abgesichert (`test_scan_does_not_find_itself`,
  `test_host_scan_snippet_matches_the_local_scan`, beide laufen grün).
- `scan_proc_for_game()` überspringt jetzt die eigene PID (vorher nicht).
- `game_stopped = Signal(bool)` → einzige Verbindung `mainwindow.py:436` auf
  `_unlock_ui(self, stopped: bool = True)`; Signatur passt.
- Unlock-Button: `clicked.connect(lambda checked=False: self._on_unlock_clicked())`
  — der bool-Parameter ist korrekt abgefangen.
- Log-Rotation praktisch geprüft: 3 Rotationen → `debug.log.1` (neuestes),
  `debug.log.2`, ältere gelöscht. Korrekt.
- `diagnostics.log_sources()`: neue debug.log-Quellen aus dem Basisverzeichnis
  plus Projekt-Fallback mit Duplikatschutz (`dbg != dbg_log`). Korrekt.
- Flatpak-Manifest: `--talk-name=org.freedesktop.Flatpak` ist die richtige und
  nötige Berechtigung für `flatpak-spawn --host`.
- Übersetzungen: `dialog.unlock_purge_title`, `dialog.unlock_purge_text`,
  `error.game_already_running` in allen 7 Locale-Dateien, JSON gültig.
  Alle neuen sichtbaren Strings laufen über `tr()`.

---

## Teil 4 — Architektur-Abgleich

Prüfpunkte laut `ARCHITEKTUR.md` §9:
1. Keine Mod-Dateien direkt ins Game-Verzeichnis — ✅ (Deployer unverändert)
2. Ordnerstruktur in `.mods/` unverändert — ✅
3. Frameworks nicht in `.mods/`/modlist.txt — ✅
4. `active_mods.json` bei Rename/Delete — nicht berührt
5. Nur globale API — nicht berührt
6. Deploy-/Purge-Mechanismus nur mit Marcs Zustimmung — ⚠️ siehe INFO-1
7. Architektur-Doku gelesen — ✅

### [INFO-1] Purge-Bedingungen geändert — Doku/Freigabe
`mod_deployer.py` ist unverändert, aber **wann** gepurged wird, ist an fünf
Stellen neu geregelt (Timer, Instanzwechsel, Profilwechsel, closeEvent,
Vorstart). ARCHITEKTUR.md §9.6 stellt die Purge-Logik ausdrücklich unter
Zustimmungsvorbehalt, §2 („Nach Game-Ende: Symlinks bleiben bis Purge“) und §10.5
beschreiben den neuen Zustand „Purge kann bei unbekanntem Spielstatus ganz
ausbleiben“ noch nicht. Empfehlung: kurzer Abschnitt in der Doku + Freigabe.

### [INFO-2] MO2-Referenz nicht vorhanden
`ls /home/mob/Projekte/mo2-referenz` → „Datei oder Verzeichnis nicht gefunden“.
Der von ARCHITEKTUR.md §11 geforderte Abgleich ist damit nicht durchführbar. Der
Diff berührt weder `mod_deployer.py` noch modlist/Installation, ein Vergleich
wäre inhaltlich ohnehin nur für den Deploy-Zeitpunkt relevant (MO2 beendet mit
dem VFS automatisch, Anvil purged explizit — bereits als bewusste Abweichung in
§10.5 dokumentiert). §11 nennt weiterhin einen Pfad, den es nicht mehr gibt.

---

## Ergebnis

**NEEDS FIXES**

Blocker: **HIGH-1** und **HIGH-2** — beide führen belegbar dazu, dass Anvil ein
laufendes Spiel als beendet meldet und das Deployment darunter entfernt. Genau
das sollte die Änderung verhindern.

Vor dem Commit zusätzlich zu klären: MEDIUM-1 (Migration bei UNKNOWN),
MEDIUM-2 (GRB/REDmod umgehen den Guard), MEDIUM-3 (doppelter Dialog).
Die LOW-Punkte sind Aufräumarbeit, kein Hindernis.

Tests: 297 passed, 1 skipped — die neuen Tests decken die behobenen Befunde ab,
aber weder den `proc.wait()`-Ablauf noch zwei parallele Watcher. Beide Fälle
sollten mit Regressionstests abgesichert werden.
