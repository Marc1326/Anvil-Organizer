# QA Report — Regressions- und Auslieferungsprüfung Prozesserkennung / debug.log
Datum: 2026-08-06
Geprüfter Stand: nicht committete Änderungen auf `main` (HEAD = d174cd6 "v1.7.0")

## Prüfumfang

Geänderte Dateien (`git status`):
`anvil/core/diagnostics.py`, `anvil/core/subprocess_env.py`, `anvil/main.py`,
`anvil/mainwindow.py`, `anvil/widgets/game_panel.py`, `tests/test_predeploy_launch.py`,
alle 7 Locale-Dateien; neu und **untracked**: `anvil/core/debug_log.py`.

Gelesen: `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md` (Abschnitte 5/6, Deploy- und
Purge-Logik). Die MO2-Referenz `/home/mob/Projekte/mo2-referenz/src/` **existiert auf diesem
Rechner nicht** (`ls` schlägt fehl, das gesamte Verzeichnis `/home/mob/Projekte/mo2-referenz`
fehlt) — ein Zeilenvergleich war deshalb nicht möglich. Für diese Änderung ist das vertretbar:
Deployer, Installer, modlist.txt und Separatoren sind unangetastet (`git status` zeigt keine
Änderung an `mod_deployer.py`, `mod_installer.py`, `mod_list_io.py`). Geändert wurde nur, *wann*
`silent_purge()` ausgelöst wird, nicht *wie* deployed/gepurged wird.

Architektur-Regeln 1–5 sind eingehalten: keine Direktkopien, keine Strukturänderung in `.mods/`,
keine Frameworks in modlist.txt, kein Rename/Delete-Pfad berührt, keine Legacy-API.

---

## Findings

### [CRITICAL] Neue Datei ist nicht in Git — jeder git-basierte Build startet nicht mehr
- Datei: `anvil/core/debug_log.py` (untracked), Import in `anvil/main.py:117-118`
- Beleg:
  - `git ls-files --error-unmatch anvil/core/debug_log.py` → "stimmt mit keinen Git bekannten Dateien überein"
  - `git check-ignore -v anvil/core/debug_log.py` → exit 1 (die Datei wird **nicht** von `.gitignore` ausgeschlossen, `.gitignore` enthält nur `debug.log`)
- Problem: Der Import in `main()` ist ungeschützt (`from anvil.core.debug_log import start_debug_log`,
  kein try/except). Wird nur mit `git commit -a` committet, fehlt das Modul in allen Build-Pfaden,
  die aus Git bauen: `.github/workflows/appimage.yml` und `flatpak.yml` (beide `actions/checkout`),
  AUR-git (`git+https://…`), sowie die Release-Tarballs für AUR/RPM. Ergebnis: `ModuleNotFoundError`
  direkt nach der Basisverzeichnis-Prüfung → App startet nicht.
  Der lokale Build über `build-flatpak.sh` maskiert den Fehler, weil das Manifest
  `com.github.Marc1326.AnvilOrganizer.yml` mit `type: dir / path: ../..` den **Arbeitsbaum** kopiert.
- Fix: `git add anvil/core/debug_log.py` vor dem Commit. Zusätzlich empfohlen: den Import in
  `main()` defensiv kapseln, damit ein fehlendes optionales Log-Modul den Start nie verhindert.

### [HIGH] `is_game_running()` blockiert im Flatpak den GUI-Thread (bis 10 s, im Fallback bis 20 s)
- Datei: `anvil/widgets/game_panel.py:2739-2749`, aufgerufen aus `anvil/mainwindow.py:1016`, `1078`, `2710`, `7059`
- Problem: Der Aufruf geht jetzt über `find_game_process()` → `flatpak-spawn --host python3 …`
  mit `_HOST_SCAN_TIMEOUT = 10`; schlägt der Python-Weg fehl, folgt der `ps`-Fallback mit weiteren
  10 s. Alle vier Aufrufstellen laufen im GUI-Thread — insbesondere `closeEvent` (7059) und die
  Speicher-/Migrationsprüfungen. Anvil kann beim Schließen bis zu 20 s einfrieren.
  Außerhalb Flatpak unverändert (lokaler `/proc`-Scan, Millisekunden).
- Fix: Timeout für die synchronen GUI-Aufrufe deutlich senken (1–2 s) oder das Ergebnis des
  Watchers cachen, statt bei jedem Aufruf neu auf dem Host zu suchen.

### [HIGH] Speicher-/Migrationsoperationen können im Flatpak dauerhaft blockiert werden
- Datei: `anvil/mainwindow.py:1016` und `1078` (`if self._game_running or self._game_panel.is_game_running():` → `storage.error_game_running`)
- Problem: `is_game_running()` liefert per neuer Fail-Safe-Semantik `True`, wenn der Lookup nicht
  durchführbar war (`reliable=False`). Ist `flatpak-spawn` nicht nutzbar (fehlendes
  `--talk-name=org.freedesktop.Flatpak`, kein `python3`/`ps` auf dem Host, Portal-Fehler), melden
  beide Stellen dauerhaft „Spiel läuft", obwohl kein Spiel läuft. Basisverzeichnis-Migration und
  Instanz-Speicheroperationen sind dann nicht mehr möglich, ohne Ausweg in der UI.
  Vor der Änderung prüften diese Stellen nur `self._game_running`.
- Fix: Hier `lookup_game_pid()` verwenden und nur bei `reliable=True and pid is not None`
  blockieren — oder wie beim Entsperren den Nutzer entscheiden lassen.

### [MEDIUM] Watcher gibt nach einem einzigen fehlgeschlagenen Lookup endgültig auf
- Datei: `anvil/widgets/game_panel.py:2791-2801`
- Problem: In der Laufschleife führt ein einzelnes `reliable=False` sofort zu
  `game_stopped.emit(False)` + `return`. Ein transienter Timeout (Host unter Volllast, 10 s
  überschritten) beendet die Überwachung für den Rest der Sitzung; das tatsächliche Spielende wird
  danach nie mehr erkannt, das Deployment bleibt liegen und der Nutzer muss von Hand entsperren.
- Fix: Fehlversuche zählen (z. B. 3 in Folge) und erst dann aufgeben.

### [MEDIUM] Verhaltensänderung auch außerhalb Flatpak: „Prozess nie aufgetaucht" räumt nicht mehr auf
- Datei: `anvil/widgets/game_panel.py:2772-2789` (vorher: `git show HEAD:anvil/widgets/game_panel.py`, Zeile „`self.game_stopped.emit()`")
- Problem: Läuft der Appear-Timeout ab (Spiel stürzt beim Start ab, Launcher startet nichts, Proton
  scheitert), wurde früher `game_stopped()` gesendet; `_unlock_ui()` prüfte selbst nach und purgte,
  wenn nichts lief. Jetzt wird `emit(False)` gesendet → das Deployment bleibt **garantiert** liegen,
  auch auf AppImage/Systeminstallation/Quellcode-Start, wo die Erkennung zuverlässig ist.
  Aufgeräumt wird erst beim nächsten Spielstart (`_predeploy_for_launch`) oder beim Schließen
  (`closeEvent` → `silent_purge()`, da `is_game_running()` dann korrekt `False` liefert).
- Fix (falls nicht gewollt): Im Appear-Zweig `lookup_broken` auswerten und `emit(not lookup_broken)`
  senden — dann bleibt außerhalb Flatpak das alte Aufräumverhalten erhalten.

### [MEDIUM] Direktstart (GOG/Epic) endet jetzt regelmäßig mit liegengebliebenem Deployment
- Datei: `anvil/mainwindow.py:2595-2620` (`_on_start_game`), `anvil/mainwindow.py:2676-2693` (`_on_unlock_clicked`)
- Problem: Der Direktstart startet — unverändert gegenüber HEAD — **keinen** Watcher
  (`_start_process_watcher` wird nur in `_launch_via_steam:2563` und `_launch_via_proton:2656`
  aufgerufen). Das Entsperren war bisher der reguläre Weg und purgte; jetzt kommt eine Rückfrage
  mit Vorgabe **Nein** (und Escape = Nein). Für Nicht-Steam-Spiele bleiben die Mods damit nach
  jeder Sitzung im Spielordner, bis Anvil geschlossen wird.
- Fix/Prüfen: Entweder für den Direktstart einen Watcher starten (die PID ist aus `host_popen`
  bekannt) oder die Vorgabe des Dialogs auf „Ja" setzen, wenn kein Watcher aktiv war.

### [LOW] Irreführende Log-Zeile beim Entsperren ohne Deployment
- Datei: `anvil/mainwindow.py:2683-2685`
- Problem: Ohne Deployment wird `_unlock_ui(False)` gerufen; das protokolliert
  „[LAUNCH] game state unknown — keeping the deployment", obwohl der Zustand bekannt ist und es
  gar kein Deployment gibt. Funktional folgenlos (der Cleanup-Zweig enthält nur Purge + Logging,
  die UI wird danach in jedem Fall entsperrt), aber die neue debug.log wird dadurch irreführend.
- Fix: Eigener Zweig, der ohne Meldung direkt entsperrt.

### [LOW] Groß-/Kleinschreibung des Suchmusters verhält sich anders als vorher
- Datei: `anvil/core/subprocess_env.py:136` (`binary = binary_name.lower().encode()`), vorher `binary_name.encode() in cmdline.lower()`
- Beleg (ausgeführter Vergleichslauf alt vs. neu auf demselben Prozess):
  - gemischt `MixedCaseProbe88.exe` → alt `None`, neu `PID 1324611`
  - klein geschrieben → alt `1324611`, neu `1324611`
  - nach Prozessende → alt `None`, neu `None`
  - SteamAppId-Weg → alt `1324702`, neu `1324702` (erwartete PID)
- Bewertung: Praktisch nicht erreichbar, weil beide Aufrufer bereits `.name.lower()` übergeben
  (`game_panel.py:2562` und `2655`). Reihenfolge (SteamAppId vor cmdline, pro PID), `/proc`-Scan,
  OSError-Behandlung und Rückgabewert sind ansonsten **identisch**. Kein Handlungsbedarf, nur
  dokumentiert.

### [LOW] Überspringen der eigenen PID ist folgenlos (keine Regression)
- Datei: `anvil/core/subprocess_env.py:138`, `144`
- Beleg: Auch die alte Implementierung findet sich selbst nicht — `/proc/self/environ` zeigt die
  Startumgebung, ein nachträglich gesetztes `SteamAppId` taucht dort nicht auf (Testlauf:
  „eigene Env alt: None / neu: None"). Die Härtung verhindert nur den Selbsttreffer über die
  Kommandozeile und ist korrekt.

### [LOW] `debug_log` fehlt der Schutz gegen ein nicht eingehängtes Basisverzeichnis
- Datei: `anvil/core/debug_log.py:96-100` vs. `anvil/core/activity_log.py:57-63`
- Problem: `activity_log` bricht ab, wenn eine benutzerdefinierte Basis nicht verfügbar ist;
  `debug_log` ruft direkt `log_dir.mkdir(parents=True, exist_ok=True)` und würde am leeren
  Mountpoint ein Verzeichnisskelett anlegen. Entschärft dadurch, dass `_ensure_base_directory()`
  in `main()` vorher läuft und bei fehlender Basis den Recovery-Dialog zeigt.
- Fix: Dieselbe Guard-Bedingung wie in `activity_log` übernehmen.

### [LOW] Zweite Instanz rotiert die Logdatei unter der laufenden Instanz weg
- Datei: `anvil/main.py:117-118` (vor der Single-Instance-Prüfung in Zeile 130 ff.)
- Problem: Eine zweite Anvil-Instanz (z. B. NXM-Link-Weiterleitung) ruft `start_debug_log()`,
  rotiert ggf. `debug.log` per `rename` und schreibt einen neuen Session-Header. Die laufende
  Instanz hält ihr Handle auf die umbenannte Datei — ihre weiteren Ausgaben landen dann in
  `debug.log.1`. Kosmetisch, aber verwirrend bei der Fehlersuche.
- Fix: `start_debug_log()` erst nach `single.try_lock()` aufrufen.

### [LOW] `_Tee` implementiert nur einen Teil der Stream-API
- Datei: `anvil/core/debug_log.py:52-89`
- Vorhanden: `write`, `flush`, `isatty`, `fileno`. Nicht vorhanden: `encoding`, `buffer`,
  `writelines`, `close`, `errors`.
- Geprüft: Im gesamten Projekt greift nichts darauf zu — `grep -rn "sys\.stdout\|sys\.stderr"`
  liefert außerhalb von `debug_log.py` nur `print(..., file=sys.stderr)` und
  `sys.stdout.flush()`/`sys.stderr.flush()` in `anvil/main.py:148,149,170,171`. Kein
  `stdout=sys.stdout` an `subprocess`. Derzeit unkritisch, bei künftigen Bibliotheken aber eine
  mögliche Stolperstelle.

### [LOW] Ungenutztes Flatpak-Manifest würde die neue Erkennung nicht unterstützen
- Datei: `packaging/flatpak/net.anvil_organizer.AnvilOrganizer.yml`
- Problem: Dort fehlt `--talk-name=org.freedesktop.Flatpak` (also kein `flatpak-spawn`) und die
  Basis wird nur mit `--filesystem=~/.anvil:create` freigegeben, was das tatsächliche
  `~/.anvil-organizer` nicht abdeckt. Würde dieses Manifest gebaut, funktionierte weder die neue
  Prozesserkennung noch das debug.log. Aktiv verwendet wird es nicht:
  `build-flatpak.sh:MANIFEST` und `.github/workflows/flatpak.yml` zeigen beide auf
  `com.github.Marc1326.AnvilOrganizer.yml` (dort sind `--filesystem=home` und
  `--talk-name=org.freedesktop.Flatpak` gesetzt). Zusätzlich ist das Manifest auf Tag `v1.2.2`
  festgenagelt.
- Fix: Pflegen oder entfernen.

---

## Antworten auf die Prüfaufträge

### 1. Regression außerhalb Flatpak — Prozesserkennung
**Kein Verhaltensunterschied, der außerhalb Flatpak greift** (bis auf den dokumentierten
Groß-/Kleinschreibungsfall, den kein Aufrufer erreicht).

- `find_game_process()` verzweigt in `if not is_flatpak(): return scan_proc_for_game(...), True`
  (`subprocess_env.py:255-256`) — außerhalb Flatpak ist `reliable` **immer** `True`, also kann
  `is_game_running()` dort nie fälschlich `True` liefern.
- `is_flatpak()` prüft `os.path.isfile("/.flatpak-info")` — in AppImage, Systeminstallation und
  Quellcode-Start `False` (auf diesem Rechner verifiziert: `is_flatpak: False`).
- `lookup_game_pid()` fängt „nichts gestartet" vorab ab und liefert `(None, True)`; das
  `(None, False)` aus `find_game_process(None, None)` ist von der GamePanel-Seite unerreichbar.
- Reihenfolge SteamAppId → cmdline pro PID, `os.scandir("/proc")`, `OSError`-Behandlung und
  Rückgabewerte sind identisch zur alten Implementierung (per Vergleichslauf gegen eine 1:1
  nachgebaute HEAD-Version belegt, siehe Findings LOW oben).
- Geändertes Verhalten *nach* der Erkennung: siehe Finding MEDIUM „Prozess nie aufgetaucht" —
  das betrifft alle Distributionsformen, nicht nur Flatpak.

### 2. Startpfade und Watcher
| Startweg | Watcher | Signal | Bewertung |
|---|---|---|---|
| `_launch_via_steam` (`game_panel.py:2563`) | ja, `app_id` + Binärname | `game_started(-1)` → Lock | korrekt |
| `_launch_via_proton` (`game_panel.py:2656`) | ja, Binärname + `proc` | `game_started(proc.pid)` → Lock | korrekt |
| REDmod (`_on_redmod_finished:2231/2252`) | über `_do_launch` → Steam/Proton | wie oben | korrekt |
| Direktstart `_on_start_game` (`mainwindow.py:2620`) | **nein** (unverändert seit HEAD) | `notify_game_started` → Lock | siehe Finding MEDIUM |
| Eigene Programme `_on_custom_tool_start` | nein — bewusst kein Lock (Kommentar im Code) | keins | korrekt, nicht betroffen |
| `run_with_proton` (Proton-Tools) | nein, kein Lock | keins | unverändert |

Signalbehandlung: `game_stopped = Signal(bool)` hat genau **eine** Verbindung
(`mainwindow.py:436` → `_unlock_ui`); es gibt keine weitere Verbindung im Projekt
(`grep -rn "game_stopped"`). Die Emission erfolgt aus dem Watcher-Thread, die Verbindung ist
`AutoConnection` → queued in den GUI-Thread; `bool` ist ein registrierter Metatyp.
`_unlock_ui(stopped=True)` behält den Default, sodass die Altaufrufe in den Tests weiter passen.
Der Entsperren-Knopf zeigt jetzt auf `_on_unlock_clicked` (`mainwindow.py:330`), Lambda mit
`checked=False` korrekt beibehalten. `QMessageBox` ist in `mainwindow.py:27` importiert.

### 3. Paketierung von `anvil/core/debug_log.py`
**Es gibt in keinem Build-Pfad eine explizite Python-Dateiliste.** Geprüft:
- `pyproject.toml`: `[tool.setuptools.packages.find] include = ["anvil*"]` → alle Module in
  `anvil.core` werden automatisch mitgenommen; `[tool.setuptools.package-data]` listet nur
  Nicht-Python-Dateien (qss, svg, png, json, dll) — dort ist **nichts** nachzutragen.
- `anvil-organizer.spec`: nur `datas` (Ressourcenverzeichnisse) und `hiddenimports` für dynamisch
  geladene Module. `anvil.core.debug_log` wird statisch importiert — nachgewiesen per Bytecode:
  `IMPORT_NAME gefunden in Code-Objekt main -> anvil.core.debug_log`. PyInstaller durchsucht auch
  verschachtelte Code-Objekte, das Modul landet also im Bundle; dieselbe Import-Form wird dort
  bereits für `nxm_handler`, `single_instance` usw. verwendet.
- `packaging/aur/PKGBUILD`, `packaging/aur-git/PKGBUILD`, `packaging/rpm/anvil-organizer.spec`,
  `packaging/deb/debian/rules`, `packaging/snap/snapcraft.yaml`, `Makefile`: alle bauen über
  `pip`/`python -m build`/`pybuild` aus `pyproject.toml`, keine Dateilisten
  (`%files` im RPM listet nur `%{python3_sitelib}/anvil/`).
- `build-appimage.sh` und `.github/workflows/appimage.yml`: bauen über die Spec.
- `.github/workflows/flatpak.yml` + `build-flatpak.sh`: `pip3 install … .` über dasselbe pyproject.
- `anvil_organizer.egg-info/SOURCES.txt` enthält die neue Datei nicht — das ist ein veraltetes
  Build-Artefakt (`*.egg-info/` ist in `.gitignore`) und wird bei jedem Build neu erzeugt; für
  Wheels ist ohnehin die Paketfindung maßgeblich. Kein Handlungsbedarf.

→ **Einziger Stolperstein ist das fehlende `git add`** (Finding CRITICAL).

### 4. Schreibbarkeit des debug.log-Pfads
`start_debug_log()` schreibt nach `anvil_base_paths().logs` — **exakt dasselbe Verzeichnis**, in
das `activity_log` seit jeher `activity.log` schreibt (`activity_log.py:15-16`). Es entsteht also
keine neue Schreibanforderung für irgendein Paketformat.
- Flatpak (`com.github.Marc1326.AnvilOrganizer.yml`): `--filesystem=home` deckt
  `~/.anvil-organizer/logs` ab; zusätzlich `/media`, `/mnt`, `/run/media` für Basisverzeichnisse
  auf externen Datenträgern.
- Liegt die Basis außerhalb dieser Freigaben, scheitert `start_debug_log()` **sauber**: getestet
  mit schreibgeschütztem Zielverzeichnis → Ausgabe `debug_log: cannot write: [Errno 13] …`,
  Rückgabe `None`, keine Exception, App läuft weiter.
- Snap: das `home`-Plug erlaubt keine versteckten Verzeichnisse in `$HOME`; `~/.anvil-organizer`
  ist dort grundsätzlich nicht erreichbar. Das betrifft aber die gesamte App (Instanzen,
  activity.log) und ist kein neues Problem dieser Änderung.
- Weiter getestet: Rotation bei >2 MB erzeugt `debug.log.1`, danach `debug.log.2`
  (`Path.with_suffix(".log.1")` liefert korrekt `debug.log.1`, verifiziert unter Python 3.13);
  mehrfacher Aufruf von `start_debug_log()` ist idempotent; stdout **und** stderr landen in der
  Datei. `diagnostics.log_sources()` findet `debug.log`, `debug.log.1/2` sowie zusätzlich das
  Projekt-`debug.log` aus `restart.sh` (mit Dedupe über `dbg != dbg_log`) — konsistent.

### 5. Testsuite
`python3 -m pytest tests/ -q --ignore=tests/test_base_migration_dialog.py`
→ **291 passed, 1 skipped in 1.44s** — keine Fehlschläge.
Die neuen Tests in `SandboxedProcessLookupTests` laufen mit, inklusive
`test_host_scan_snippet_matches_the_local_scan` (führt `_HOST_SCAN` real aus) und
`test_scan_does_not_find_itself`.

### 6. py_compile
`python3 -m py_compile` über `diagnostics.py`, `subprocess_env.py`, `debug_log.py`, `main.py`,
`mainwindow.py`, `game_panel.py`, `tests/test_predeploy_launch.py` → fehlerfrei.
Zusätzlich: alle 7 Locale-JSONs sind valide, die neuen Schlüssel `dialog.unlock_purge_title` und
`dialog.unlock_purge_text` sind in **allen 7** Sprachen (de, en, es, fr, it, pt, ru) vorhanden und
nicht leer. Keine Platzhalter in diesen Strings, daher kein Format-Risiko.
Ein Linter/Type-Checker ist im Projekt nicht konfiguriert (kein ruff/flake8/mypy in
`pyproject.toml`, `requirements.txt` oder als Konfigurationsdatei).

---

## Ergebnis

**NEEDS FIXES**

Blocker vor dem Commit: `git add anvil/core/debug_log.py` (CRITICAL — sonst startet jeder aus Git
gebaute Release nicht mehr).
Vor der Auslieferung zusätzlich zu entscheiden: die beiden HIGH-Punkte (GUI-Blockade und die
dauerhaft blockierten Speicheroperationen im Flatpak) sowie die MEDIUM-Verhaltensänderungen
(Watcher gibt nach einem Fehlversuch auf; Deployment bleibt nach Appear-Timeout und beim
Direktstart liegen).
Ergänzend: `ARCHITEKTUR.md` beschreibt bisher nur „Purge → Deploy → Start"; das neue Verhalten
„bei unbekanntem Spielzustand bleibt das Deployment stehen" sollte dort nachgetragen werden.
