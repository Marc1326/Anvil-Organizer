# Nachprüfung — Architektur- und Regel-Review (Runde 2)

Datum: 2026-08-06
Branch: main (HEAD = d174cd6 „v1.7.0")
Umfang: `git status` + `git diff HEAD` inkl. der gestageten neuen Dateien
`anvil/core/debug_log.py` und `anvil/core/game_process.py`

---

## 0. Vorfrage: Existiert ARCHITEKTUR.md?

**Im Anvil-Repo: nein. Im Wiki-Repo: ja.**

Belege:

```
$ find . -iname "ARCHITEKTUR*" -not -path "./.git/*"     → keine Ausgabe
$ git ls-files | grep -i architekt                        → keine Ausgabe
$ git log --all --oneline -- ARCHITEKTUR.md docs/ARCHITEKTUR.md → keine Ausgabe
$ ls /home/mob/Projekte/anvil-wiki/dev-notes/
2026-02-26-analyse-savegames-fallout4-loadorder.md
ARCHITEKTUR.md
$ wc -l /home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md → 244
```

Die Datei liegt in einem **anderen Git-Repository** (`/home/mob/Projekte/anvil-wiki`,
zuletzt committet als 5228a78 „Speicherverwaltung und GRB dokumentieren"). Sie ist
in `CLAUDE.md` nicht verlinkt, wohl aber in der Agent-Beschreibung des QA-Prüfers.

Die von der Vorrunde zitierten Stellen existieren wörtlich:

- **Abschnitt 9, Punkt 6** (`ARCHITEKTUR.md:215`): „**NIEMALS** den Deploy-Mechanismus
  (Symlinks, Kopien, Manifest, Purge, Frameworks) ändern ohne ausdrückliche Zustimmung
  von Marc."
- **Abschnitt 5** (`ARCHITEKTUR.md:106`) und **Abschnitt 6** (`ARCHITEKTUR.md:150`):
  jeweils eine „⚠️ SCHUTZREGEL" gleichen Inhalts.

Die Vorrunde hat diese Regeln also **nicht erfunden**. Der Vorwurf trifft nicht zu —
korrekt ist nur, dass die Datei nicht im Anvil-Repo liegt und die Zitate deshalb
ohne Pfadangabe nicht nachvollziehbar waren. Alle Regelverweise in diesem Bericht
sind mit Datei **und** Zeile belegt.

---

## 1. Verifikation der drei gemeldeten Fixes

### 1.1 Prozesssuche aus `subprocess_env.py` ausgelagert — ✅ erledigt

```
$ git diff HEAD -- anvil/core/subprocess_env.py   → leer
$ git status --porcelain anvil/core/subprocess_env.py → leer
```

`subprocess_env.py` ist byteidentisch mit HEAD. Das neue Modul
`anvil/core/game_process.py` (154 Zeilen, gestaget) enthält die Suche.

**Konventionspassung** — geprüft gegen die 50 Module in `anvil/core/`:

| Kriterium | Bestand | `game_process.py` |
|---|---|---|
| Ein Modul pro Zuständigkeit | ja (`instance_paths.py`, `framework_state.py`, `single_instance.py`) | ✅ passt |
| `from __future__ import annotations` | in allen neueren Modulen | ✅ vorhanden |
| Modul-Docstring | ~46/50 vorhanden | ✅ vorhanden |
| Docstring-Sprache | gemischt: Deutsch (`activity_log`, `diagnostics`, `icon_manager`, `notification_center`) und Englisch (`mod_deployer`, `subprocess_env`, `mod_entry`) | gemischt **innerhalb** der Datei — siehe LOW-4 |

Gemessene Kommentardichte (Kommentarzeilen + Docstring-Zeilen / Gesamtzeilen):

```
anvil/core/game_process.py       154 Zeilen   24,7 %
anvil/core/subprocess_env.py     238 Zeilen   25,2 %   (Bestand, Herkunft des Codes)
anvil/core/single_instance.py     86 Zeilen   25,6 %   (Bestand)
anvil/core/mod_deployer.py       992 Zeilen   20,1 %   (Bestand)
anvil/core/debug_log.py          122 Zeilen    9,0 %
anvil/core/activity_log.py        72 Zeilen    9,7 %   (Bestand, Schwestermodul)
anvil/core/diagnostics.py        326 Zeilen    8,3 %   (Bestand)
```

Beide neuen Module liegen exakt im Korridor ihrer jeweiligen Nachbarn. **Kein
Befund** zur Kommentardichte.

### 1.2 `_unlock_ui`-Verrenkung aufgelöst — ✅ erledigt

`anvil/mainwindow.py:2721-2765`. Der alte Aufbau
(`if not stopped: still_running = True` … `if still_running: if stopped:`) ist
weg. Jetzt drei Methoden mit je einer Aufgabe:

- `_unlock_ui(stopped=True)` — Entscheidung (2721)
- `_purge_after_game()` — Aufräumen + Protokoll (2741)
- `_release_ui_lock()` — Overlay/Widgets freigeben (2757)

Die Verzweigung ist linear (`if not stopped` / `elif is_game_running()` / `else`),
kein toter Zweig mehr. `_release_ui_lock()` wird auf allen drei Wegen genau einmal
erreicht. **Sauber und lesbar** — Punkt erfüllt.

Der defensive `getattr(self._game_panel, "is_game_running", lambda: False)()` ist
ebenfalls verschwunden (jetzt direkter Aufruf, `mainwindow.py:2733`) — konsistent
mit den übrigen 5 Aufrufstellen.

### 1.3 `start_debug_log()` hinter den Single-Instance-Check — ✅ erledigt

`anvil/main.py`: `single.try_lock()` steht in Zeile 129, der Forwarder-Zweig endet
mit `os._exit(0)` in Zeile 149, `start_debug_log(...)` steht in Zeile 153. Reihenfolge
stimmt, der Kommentar (151-152) begründet sie zutreffend.

Einschränkung siehe LOW-9.

---

## 2. Findings

### [HIGH] `_clear_watch_target()` im „nie aufgetaucht"-Zweig hebt genau den Schutz auf, den der ganze Umbau herstellen soll

- Datei: `anvil/widgets/game_panel.py:2826-2839`, wirkt auf `anvil/mainwindow.py:2733`
- Problem: Läuft der Appear-Timeout (`_GAME_APPEAR_TIMEOUT = 120`) ab, ohne dass der
  Prozess gefunden wurde, und war der Lookup dabei zuverlässig (`blind_since is None`),
  passiert der Reihe nach:

  ```python
  _dlog("[WATCHER] game process never appeared")
  self._clear_watch_target()      # 2835 — löscht _watch_binary, _watch_app_id, _game_state
  if proc is not None:
      proc.wait()                 # 2837 — kann Stunden dauern (Direktstart!)
  self.game_stopped.emit(blind_since is None)   # 2838 → _unlock_ui(True)
  ```

  Nach Zeile 2835 liefert `game_state()` über den frühen Ausstieg in
  `game_panel.py:2771-2772` **immer** `GAME_STOPPED`, weil kein Watch-Ziel mehr
  gesetzt ist. Damit gilt:

  1. **Purge während eines noch startenden Spiels.** `_unlock_ui(True)` prüft in
     `mainwindow.py:2733` `is_game_running()` nach — diese Nachprüfung ist durch
     das vorangegangene Löschen wirkungslos und der `else`-Zweig
     `self._purge_after_game()` (2738) läuft. Ein Proton-Erststart mit
     Shader-Kompilierung über 120 s reicht aus.
  2. **Purge-Fenster während `proc.wait()`.** Beim Direktstart (GOG/Epic) ist `proc`
     das Spiel selbst. Zwischen 2835 und dem Ende von 2837 meldet `is_game_running()`
     „gestoppt", obwohl das Spiel läuft. In diesem Fenster purgen `closeEvent`
     (`mainwindow.py:7091`), Profilwechsel (4702), Instanzwechsel (1629) und
     `_do_redeploy` (2309) ohne jede Schutzprüfung.

- Regression gegenüber HEAD, belegt mit `git show HEAD:anvil/widgets/game_panel.py`:
  dort wurde `_watch_binary` **nicht** gelöscht, und der Kommentar sagte ausdrücklich
  „It may still be starting, so unlock the UI but let MainWindow decide whether
  anything may be removed." Genau diese Entscheidungsgrundlage nimmt der neue Code
  dem MainWindow weg. Der neue Kommentar (2827-2829) behauptet das Gegenteil
  („the game really is gone").
- Berührt `ARCHITEKTUR.md:106` (Schutzregel Deploy/Purge).
- Fix: `_clear_watch_target()` im Nie-aufgetaucht-Zweig entfernen — der Fall ist
  gerade **nicht** „confirmed gone", was der eigene Docstring in Zeile 2746
  („once its process is confirmed gone") auch sagt. Alternativ erst nach
  `proc.wait()` und nur nach erneuter Bestätigung durch einen Lookup.

### [MEDIUM] „Spiel läuft schon" erzeugt einen zweiten Dialog mit falscher Begründung

- Dateien: `anvil/mainwindow.py:2614-2620` und `anvil/widgets/game_panel.py:1971-1978`
- Problem: `_predeploy_for_launch()` zeigt bei laufendem Spiel selbst eine Warnung
  (`error.game_already_running`, `mainwindow.py:2574-2581`) und gibt `False` zurück.
  Beide Aufrufer werten `False` weiterhin als Deploy-Fehler und blenden direkt
  danach `error.deploy_failed_title` / `error.deploy_failed_message` ein. Der
  Benutzer sieht zwei Meldungen, die zweite mit einer sachlich falschen Ursache
  („Die Mods konnten nicht ins Spiel deployed werden").
  `_on_custom_tool_start` (`mainwindow.py:2650`) und `_run_proton_tool` (1311)
  machen es richtig: `return` ohne zweite Meldung.
- Kein Test deckt das ab: `test_running_game_blocks_a_second_launch`
  (`tests/test_predeploy_launch.py:648`) ruft `_predeploy_for_launch` direkt auf,
  nicht `_on_start_game`.
- Fix: `_predeploy_for_launch` einen Grund zurückgeben lassen, oder in den beiden
  Aufrufern kommentarlos zurückkehren, wenn die Funktion bereits gemeldet hat.

### [MEDIUM] Der Test zur Grace-Periode testet die Grace-Periode nicht

- Datei: `tests/test_predeploy_launch.py:698-704`
- Problem: `test_watcher_gives_up_only_after_the_grace_period` setzt
  `panel._GAME_LOOKUP_GRACE = GamePanel._GAME_LOOKUP_GRACE` und **benutzt den Wert
  nie** — die Zuweisung ist tot. Geprüft werden nur `game_state() == "unknown"` und
  `is_game_running() is True`; das ist wörtlich derselbe Vorgang wie in
  `test_failed_lookup_reports_the_game_as_running` (Zeile 561-567). Die eigentliche
  Logik (`game_panel.py:2850-2858`: erst nach 60 s Dauerausfall aufgeben) wird nie
  ausgeführt, weil die Watcher-Schleife nicht läuft. Der Name und der Docstring
  („One failed host call is noise") versprechen mehr als der Test hält.
- Gleiches, schwächer, bei `test_confirmed_stop_forgets_the_target` (707-712): der
  Test ruft `_clear_watch_target()` selbst auf und prüft nur dessen Wirkung, nicht
  dass der Watcher es an der richtigen Stelle tut — und übersieht dadurch HIGH-1.
- Fix: Watcher-Schleife mit gepatchtem `time.monotonic`/`time.sleep` und einem
  Lookup-Stub durchlaufen lassen und prüfen, dass vor Ablauf von
  `_GAME_LOOKUP_GRACE` **kein** `game_stopped` kommt und danach genau eines mit
  `False`.

### [LOW-1] Umlaut-Schreibweise widerspricht innerhalb derselben Datei

- Datei: `anvil/widgets/game_panel.py:2775`
- Problem: Der neue Kommentar schreibt „geloescht", während dieselbe Datei
  **60 Umlautzeichen** enthält (gezählt über den gesamten Quelltext) und die
  ebenfalls neuen Kommentare in `mainwindow.py:1628` („Läuft … räumt auf") und
  `mainwindow.py:2575` („würden") korrekt gesetzte Umlaute verwenden.
  Die beiden neuen Module `game_process.py` und `debug_log.py` sind dagegen
  konsequent umlautfrei („ueber", „zusaetzlich", „Menueeintrag", „haengender",
  „Schlaegt", „raeumt") — dafür gibt es mit `activity_log.py` (0 Umlautzeichen,
  „fuer", „Wochentliche") einen Präzedenzfall, das ist also vertretbar.
  Nur die eine Zeile in `game_panel.py` fällt aus dem Rahmen ihrer eigenen Datei.
- Fix: „gelöscht" schreiben.

### [LOW-2] Fehlende Leerzeile — PEP8 E302 in neuem Code

- Datei: `anvil/widgets/game_panel.py:33-37`
- Problem: Zwischen `_state_of()` und `_dlog()` steht nur **eine** Leerzeile,
  überall sonst in der Datei stehen zwei. Verifiziert mit `cat -A`.
- Fix: eine Leerzeile ergänzen.

### [LOW-3] Lokaler `import time` jetzt redundant

- Datei: `anvil/widgets/game_panel.py:1545` (`import time` innerhalb einer Methode)
- Problem: `time` wurde auf Modulebene gezogen (`game_panel.py:11`), der lokale
  Import überschattet ihn jetzt ohne Nutzen. Der zweite lokale Import in
  `_start_process_watcher` wurde korrekt entfernt.
  Vorbestehend (in HEAD an Zeile 1526), aber durch die Änderung erst redundant
  geworden.
- Verwaiste Imports: **keine**. `os`, `signal`, `subprocess`, `shutil` sind in
  `game_panel.py` weiterhin in Gebrauch (`os` 11×, `signal` 1×, `subprocess` 8×,
  `shutil` 2×). `ruff check --select F` meldet über alle geänderten Dateien
  26 Treffer — **alle** liegen außerhalb der geänderten Zeilen (Bestand, z. B.
  `mainwindow.py:8 fnmatch`, `mainwindow.py:4215 F821 QColor`). In
  `game_process.py`, `debug_log.py` und der Testdatei: **null Treffer**.

### [LOW-4] Sprachmischung innerhalb von `game_process.py`

- Datei: `anvil/core/game_process.py`
- Problem: Modul-Docstring deutsch (1-10), Funktions-Docstrings englisch (20-25,
  93, 110-113, 137-142), Kommentare gemischt: englisch (52-58, 84), deutsch
  (87-88, 144). Der Code stammt aus `subprocess_env.py` (rein englisch) und
  `game_panel.py` (englische Docstrings). Ein Präzedenzfall für die Mischung
  existiert (`single_instance.py`: englisch mit einer deutschen Zeile 34) — es ist
  also kein Regelverstoß, aber die neue Datei ist der ausgeprägteste Fall im
  Verzeichnis.
- Fix (optional): eine Sprache pro Datei; bei Herkunft aus `subprocess_env.py`
  wäre Englisch die naheliegende Wahl.
- **AI-Sichtbarkeit sonst:** keine „Co-Authored-By"-Zeile, kein „Generated by",
  keine Docstring-Flut (siehe Messung 1.1), keine Docstrings auf trivialen
  Hilfsfunktionen (`_state_of` hat bewusst keine), Kommentare erklären
  durchgehend das *Warum* statt das *Was*. Die eingebettete `_HOST_SCAN`-Quelle
  (59-82) ist ungewöhnlich, aber im Kommentar 52-58 sachlich begründet und durch
  `test_host_scan_snippet_matches_the_local_scan` gegen Auseinanderdriften
  abgesichert. **Nichts wirkt maschinengeneriert.**

### [LOW-5] `game_state()`-Docstring verspricht mehr, als der Code hält

- Datei: `anvil/widgets/game_panel.py:2764-2783`
- Problem: Der Docstring sagt, jeder Lookup koste im Flatpak einen Host-Prozess,
  „which must not happen on the GUI thread". Genau das passiert aber, sobald der
  Zwischenspeicher älter als `_GAME_STATE_TTL` (15 s) ist **oder** `GAME_STOPPED`
  enthält — letzteres ist in der 120-Sekunden-Appear-Phase der Normalfall, weil
  `_note_game_state` dort im Sekundentakt `STOPPED` schreibt (2818-2819) und
  `game_state()` gecachtes `STOPPED` bewusst verwirft (2774-2781). Jeder
  `is_game_running()`-Aufruf blockiert dann bis zu 3 s (`_HOST_SCAN_TIMEOUT`),
  im `ps`-Fallback bis zu 6 s.
  Das ist gegenüber dem Vorrunden-Stand (bis 20 s) deutlich entschärft, der
  Docstring beschreibt aber einen Zustand, der so nicht gilt.
- Fix: Docstring auf „hält Host-Aufrufe klein" abschwächen, oder den STOPPED-Fall
  während der Appear-Phase ebenfalls kurz cachen.

### [LOW-6] `debug_log.py` fehlt der Schutz, den `activity_log.py` hat

- Datei: `anvil/core/debug_log.py:105-107` vs. `anvil/core/activity_log.py:59-64`
- Problem: `activity_log` prüft vor dem Schreiben
  `if configured_base_is_custom() and not _LOG_DIR.parent.is_dir(): return`, damit
  auf einem nicht eingehängten externen Laufwerk keine Geisterverzeichnisse
  entstehen. `start_debug_log()` ruft direkt `log_dir.mkdir(parents=True,
  exist_ok=True)` auf und legt sie an. Aus der Vorrunde übernommen, **nicht behoben**.
- Fix: dieselbe Prüfung übernehmen.

### [LOW-7] Die Flatpak-Manifest-Änderung wirkt sich auf keinen Build aus

- Datei: `packaging/flatpak/net.anvil_organizer.AnvilOrganizer.yml:27-28`
- Problem: Es gibt zwei Manifeste. Gebaut und installiert wird ausschließlich das
  andere:
  - `.github/workflows/flatpak.yml:23` → `packaging/flatpak/com.github.Marc1326.AnvilOrganizer.yml`
  - `build-flatpak.sh:35` → dasselbe Manifest, `:39` `APP_ID="com.github.Marc1326.AnvilOrganizer"`
  - `install-flatpak.sh:16` → dieselbe App-ID
  - `flatpak list` → installiert ist `com.github.Marc1326.AnvilOrganizer`
  Das gebaute Manifest hat `--talk-name=org.freedesktop.Flatpak` **bereits** in
  Zeile 31 (bestätigt durch `flatpak info --show-permissions`:
  `org.freedesktop.Flatpak=talk`). Die Ergänzung ist inhaltlich richtig, ändert
  aber nichts am ausgelieferten Paket — sie darf nicht als Voraussetzung für die
  neue Erkennung verbucht werden. `grep` findet außer diesem Bericht und
  `docs/anvil-review-regression.md:146` keine Referenz auf das net.-Manifest.
- Nebenbefund (Bestand, gleiche Datei): `--filesystem=~/.anvil:create` (Zeile 22)
  trifft nicht das tatsächliche Basisverzeichnis. `anvil/core/base_dir.py:54`
  liefert `~/.anvil-organizer` (real vorhanden: `/home/mob/.anvil-organizer`),
  und Flatpak-Freigaben sind Verzeichnis- und keine Präfix-Regeln. In diesem
  Manifest könnten weder `activity.log` noch das neue `debug.log` geschrieben
  werden. Betrifft den ausgelieferten Build nicht (`--filesystem=home`).

### [LOW-8] Uneinheitliche Bedingung beim Startschutz

- Datei: `anvil/mainwindow.py:2574`
- Problem: `_predeploy_for_launch` prüft `self._game_panel.game_state() == GAME_RUNNING`
  und ignoriert `self._game_running`. Die fünf anderen Schutzstellen (1629, 2309,
  4702, 7091 sowie 1016/1078 in der `game_state`-Variante) prüfen
  `self._game_running or …`. Bei unzuverlässigem Lookup (`UNKNOWN`) ist ein
  zweiter Start damit erlaubt, obwohl Anvil selbst noch im Spiel-Lock steht.
  Praktisch schwer erreichbar, weil `_lock_ui` (`mainwindow.py:2686-2692`) den
  Splitter mit dem Start-Knopf deaktiviert; die Uneinheitlichkeit bleibt.
- Fix: `if self._game_running or self._game_panel.game_state() == GAME_RUNNING:`

### [LOW-9] Startfehler vor `main.py:153` landen weiterhin in keiner Datei

- Datei: `anvil/main.py:151-153`
- Problem: Der Fix für die Log-Rotation ist richtig, verschiebt aber den Beginn der
  Mitschrift hinter `_ensure_base_directory()` (107), den Theme-/Style-Aufbau
  (95-105), `log_action("START", …)` (117) und den Single-Instance-Block (128-149).
  Ein Absturz in diesem Bereich — also genau beim Basisverzeichnis-Wechsel, dem
  Hauptrisiko beim Start — erscheint nicht im `debug.log`. Zielkonflikt, keine
  Fehlfunktion; Kommentar 151-152 nennt nur die eine Seite.
- Fix (optional): den Kommentar um die Einschränkung ergänzen oder für die zweite
  Instanz eine eigene Logdatei/Rotationssperre statt eines späteren Starts.

### [LOW-10] Aus der Vorrunde offen geblieben

- `mainwindow.py:2702-2703`: Ohne Deployment ruft `_on_unlock_clicked`
  `_unlock_ui(False)` und protokolliert dadurch „game state unknown — keeping the
  deployment" (2730-2731), obwohl schlicht nichts vorhanden ist. Irreführend.
- `anvil/core/debug_log.py:22-24`: `debug_log_path()` ist toter Code
  (`grep -rn "debug_log_path" --include=*.py .` → nur die Definition).
- `anvil/core/diagnostics.py:251`: `dbg != dbg_log` kann nie `True` ergeben,
  weil `dbg` immer `<projekt>/debug.log` und `dbg_log` immer `<basis>/logs/debug.log`
  ist. Harmlos defensiv.
- `anvil/core/diagnostics.py:252`: Label `"debug.log (Projekt)"` ist ein deutsches
  Wort in einer unübersetzten Liste; erscheint auch bei englischer UI.
- Re-Entranz: Trifft `game_stopped(True)` ein, während der Entsperren-Dialog offen
  steht, läuft `_purge_after_game()` zweimal. Folgenlos (zweiter Purge findet ein
  leeres Manifest), aber der Dialog fragt dann nach etwas, das es nicht mehr gibt.
- `_Tee` (`debug_log.py:52-96`) implementiert nur einen Teil der Stream-API.
  Unkritisch: `grep -rn "stdout=sys.stdout|stderr=sys.stderr" anvil/` findet keine
  Weitergabe von `sys.stdout` an Subprozesse, `fileno()` wird nie von außen gerufen.

---

## 3. Governance-Hinweis (kein Bug — braucht GO von Marc)

`ARCHITEKTUR.md:106` (Abschnitt 5), `:150` (Abschnitt 6) und `:215` (Abschnitt 9,
Punkt 6) stellen die Purge-Logik unter Änderungsvorbehalt. Der Diff ändert **nicht**
`mod_deployer.py`, wohl aber an sechs Stellen, **wann** gepurgt wird:

| Datei:Zeile | Vorher | Nachher |
|---|---|---|
| `mainwindow.py:1629` | Instanzwechsel purgt immer | purgt nicht bei laufendem/unbekanntem Spiel |
| `mainwindow.py:2309` | `_do_redeploy` purgt Reste immer | dito |
| `mainwindow.py:2574` | Start purgt+deployt immer | Start wird bei laufendem Spiel verweigert |
| `mainwindow.py:2718` | Entsperren purgt nur nach Gegenprüfung | purgt auf Nutzerwunsch ohne Gegenprüfung |
| `mainwindow.py:4702` | Profilwechsel purgt immer | purgt nicht bei laufendem/unbekanntem Spiel |
| `mainwindow.py:7091` | `closeEvent` purgt immer | dito |

Fachlich sind alle sechs die richtige Richtung (Fail-Safe zugunsten der laufenden
Spielsitzung), und `CLAUDE.md` beschreibt „Anvil überschreibt modlist.txt beim
Start" — das Aufräumen beim nächsten Start ist also systemkonform. Die Regel
verlangt trotzdem eine ausdrückliche Freigabe, bevor das committet wird.

---

## 4. Ausdrücklich geprüft — kein Befund

### 4.1 Übersetzungen — vollständig, verlustfrei, unverändertes Format

Skript über alle 7 Locale-Dateien, flach aufgelöst, gegen `git show HEAD:…`:

```
de: 1294->1297 keys | FEHLEND=[] | VERLOREN=[] | GEAENDERT=[] | NEU=[3]
en: 1294->1297 keys | FEHLEND=[] | VERLOREN=[] | GEAENDERT=[] | NEU=[3]
es: 1294->1297 keys | FEHLEND=[] | VERLOREN=[] | GEAENDERT=[] | NEU=[3]
fr: 1294->1297 keys | FEHLEND=[] | VERLOREN=[] | GEAENDERT=[] | NEU=[3]
it: 1294->1297 keys | FEHLEND=[] | VERLOREN=[] | GEAENDERT=[] | NEU=[3]
pt: 1294->1297 keys | FEHLEND=[] | VERLOREN=[] | GEAENDERT=[] | NEU=[3]
ru: 1294->1297 keys | FEHLEND=[] | VERLOREN=[] | GEAENDERT=[] | NEU=[3]
```

- `dialog.unlock_purge_title`, `dialog.unlock_purge_text`, `error.game_already_running`:
  in allen 7 Sprachen vorhanden und **inhaltlich übersetzt** (nicht kopiert) —
  Stichprobe ru: „Разблокировать игру", „Игра ещё запущена…".
- Kein Key verloren, **kein** bestehender Wert verändert, keine Umformatierung:
  jede Datei wächst um exakt 3 Zeilen (1379 → 1382), Einrückung und
  abschließendes Newline (`0a`) unverändert, Diff berührt nur je zwei Blöcke.
- Weitere im Diff verwendete Keys existieren bereits: `game_panel.start`,
  `status.game_lock.unlock_button`, `error.deploy_failed_title/_message`,
  `storage.error_game_running`.
- Nebenbefund (Bestand, **nicht** von diesem Diff verursacht):
  `storage.error_game_running` ist in es/fr/it/pt/ru unübersetzt englisch.

### 4.2 Projektregeln aus `CLAUDE.md`

| Regel | Ergebnis |
|---|---|
| Keine MO2/ModOrganizer-Erwähnung | ✅ `git diff HEAD \| grep "^+" \| grep -i "mo2\|mod organizer\|usvfs"` → leer |
| Keine „Co-Authored-By: Claude" / AI-Spuren | ✅ leer |
| Kein `setStyleSheet()` | ✅ leer |
| Keine hardcoded Pfade | ✅ nur `Path("/tmp/instance")` in Tests (Bestandsmuster) |
| Alle neuen Imports vorhanden | ✅ `time` (11), `find_game_process` (26), `GAME_RUNNING` (51 in mainwindow), `start_debug_log` (main.py:152) |
| Keine Syntaxfehler | ✅ `py_compile` über alle 7 geänderten/neuen Dateien OK |
| tr()-Keys in allen Sprachen | ✅ siehe 4.1 |
| Signal mit `bool`-Parameter | ✅ `game_stopped = Signal(bool)`, alle 3 `emit()` übergeben ein bool, einzige Verbindung `mainwindow.py:436` → `_unlock_ui(stopped=True)`; Default hält die Bestandstests kompatibel |
| Lambda mit `checked`-Parameter | ✅ `mainwindow.py:330` `lambda checked=False: self._on_unlock_clicked()` |

### 4.3 Architektur-Regeln (`ARCHITEKTUR.md`, Abschnitt 9)

1. Keine Mod-Dateien direkt ins Game-Verzeichnis kopiert — ✅ Diff fasst
   `mod_deployer.py` nicht an
2. Ordnerstruktur in `.mods/` unverändert — ✅ nicht berührt
3. Frameworks nicht in `.mods/`/modlist.txt — ✅ nicht berührt
4. `active_mods.json` bei Rename/Delete — ✅ nicht berührt
5. Nur globale modlist-API — ✅ nicht berührt
6. Deploy-/Purge-Mechanismus nur mit GO — ⚠️ siehe Abschnitt 3
7. Kein Flatten — ✅ nicht berührt
8. MO2-Referenz vor Änderungen an Mod-Verwaltung — n/a: der Diff betrifft
   Prozessüberwachung und Logging; MO2 hat dafür kein Gegenstück (VFS endet mit
   dem Prozess, `usvfsconnector.cpp` kennt keinen Purge-Begriff), was
   `ARCHITEKTUR.md:227` unter „bewusst anders" bereits festhält

### 4.4 Tests

```
$ .venv/bin/python -m pytest tests/ -q
298 passed, 1 skipped in 1.51s
$ .venv/bin/python -m pytest tests/test_predeploy_launch.py -q
29 passed
```

Neu: `SandboxedProcessLookupTests` mit 11 Tests. Gut abgedeckt sind der
Nutzer-„Ja"/„Nein"-Pfad im Entsperren-Dialog, der blinde Lookup, der Startschutz,
`_do_redeploy`, die Gleichheit von lokalem und Host-Scan und der Selbstfund-Schutz.
Nicht abgedeckt: HIGH-1 (Appear-Timeout mit anschließendem Purge) und das
Zusammenspiel `_on_start_game` → `_predeploy_for_launch` (MEDIUM-1). Zur Qualität
zweier Tests siehe MEDIUM-3.

### 4.5 Packaging der neuen Module

`anvil/core/debug_log.py` und `anvil/core/game_process.py` sind gestaget
(`git status`) — der CRITICAL-Punkt der Vorrunde ist erledigt.
`pyproject.toml:63-64` (`packages.find include = ["anvil*"]`) nimmt sie mit;
`anvil-organizer.spec` braucht keinen Eintrag, weil beide statisch importiert
werden (`game_panel.py:20`, `main.py:152`) und PyInstaller auch
funktionsinterne Imports auflöst.

---

## 5. Ergebnis

**NEEDS FIXES**

Die drei gemeldeten Punkte sind sauber erledigt (Abschnitt 1). Neu ist ein
HIGH-Befund, der genau das Schadensbild wieder herstellt, das der Umbau verhindern
soll (`_clear_watch_target()` im Nie-aufgetaucht-Zweig), dazu eine falsche
Fehlermeldung beim blockierten Start und ein Test, der sein Versprechen nicht
einlöst.

Reihenfolge:

1. HIGH — `_clear_watch_target()` aus `game_panel.py:2835` entfernen
2. MEDIUM — zweiten Fehlerdialog in `mainwindow.py:2615-2620` und
   `game_panel.py:1973-1977` unterdrücken
3. MEDIUM — `test_watcher_gives_up_only_after_the_grace_period` so umbauen, dass
   er die Watcher-Schleife durchläuft
4. LOW-1 bis LOW-3 (Einzeiler: „gelöscht", Leerzeile, lokaler `import time`)
5. Rest nach Ermessen
6. Vor dem Commit: GO von Marc zum Purge-Zeitpunkt-Umbau (Abschnitt 3)
