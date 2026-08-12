# QA Report — Runde 4: Spielprozess-Erkennung, Watcher, Purge-Schutz
Datum: 2026-08-06
Geprueft: nicht committete Aenderungen (`git diff HEAD` + neue Dateien
`anvil/core/debug_log.py`, `anvil/core/game_process.py`, `tests/conftest.py`)

Alle Kommandos wurden mit `QT_QPA_PLATFORM=offscreen` ausgefuehrt, kein
sichtbares Fenster, kein `restart.sh`.

Gelesen: `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md`
(Abschnitt 5 Deploy-Mechanismus, Zeile 23 "Nach Game-Ende: Symlinks bleiben
bis Purge", Schutzregeln Zeile 210-215).

---

## Teil A — Verifikation der acht Befunde aus Runde 3

| # | Befund Runde 3 | Status | Beleg |
|---|----------------|--------|-------|
| 1 | `clear_watch_target()` erhoehte `_watch_generation` nicht | **BEHOBEN** | `game_panel.py:2790-2793`; Live-Test: Watcher laeuft, `clear_watch_target()`, Spiel verschwindet -> **keine** `game_stopped`-Emission |
| 2 | Dritter Aufrufer leerte ohne Purge | **BEHOBEN** | `confirm_start_while_running()` (`game_panel.py:1913-1936`) loescht nichts mehr, setzt nur `_forced_launch`; Aufrufer `mainwindow.py:1318`, `mainwindow.py:2686`, `game_panel.py:1973` |
| 3 | Schutz beim Anvil-Neustart hielt nur einen Moment | **BEHOBEN** | `_search_terms()` (`game_panel.py:2803-2807`) faellt auf `plugin_watch_target()` zurueck; alle 11 Plugins haben `GameSteamId` **und** `GameBinary` (geprueft per grep) — siehe aber Befund N1 |
| 4 | 120-s-Timeout purgte weiter | **BEHOBEN** | Watcher meldet `game_stopped(False)`; Live-Test "Blindflug" -> `[False]`, Zustand `unknown`, Ziel `game.exe` bleibt erhalten; `_unlock_ui(False)` purgt nicht (`mainwindow.py:2781-2783`) |
| 5 | Guard im `_crash_recovery_purge()` hing an `has_manifest` | **BEHOBEN** | Guard steht jetzt vor `has_manifest`, `purge()` **und** `remove_orphaned_links()` (`mainwindow.py:1586-1597`); Suchmerkmal SteamAppId+GameBinary statt Spielpfad — siehe aber Befund N6 |
| 6 | `_predeploy_for_launch` prueft `self._game_running` nicht | **BEHOBEN** | `mainwindow.py:2608` |
| 7 | Zweiter Dialog haengt an erneuter Messung | **BEHOBEN** | Rueckgabe `bool \| None`, `mainwindow.py:2599-2616`, ausgewertet in `mainwindow.py:2650-2658` und `game_panel.py:2014-2023` |
| 8 | Tool-Starts wurden hart abgelehnt | **BEHOBEN** | `mainwindow.py:1318` (Proton-Tool) und `mainwindow.py:2686` (eigenes Programm) fragen jetzt |

Zusaetzlich geprueft und in Ordnung:
* Testsuite: `304 passed, 1 skipped` (offscreen).
* `py_compile` aller geaenderten Module fehlerfrei.
* Uebersetzungen `dialog.unlock_purge_title`, `dialog.unlock_purge_text`,
  `dialog.start_while_running_text`, `error.game_already_running` in **allen
  7** Locale-Dateien vorhanden (de, en, es, fr, it, pt, ru), keine
  Platzhalter, Anrede (Du-Form) passt zum Rest von `de.json`.
* `game_stopped` ist jetzt `Signal(bool)`; der einzige Slot `_unlock_ui(self,
  stopped=True)` nimmt den Parameter entgegen (`mainwindow.py:436`).
* `find_game_pid()` restlos entfernt, keine Aufrufer mehr im Code.
* Alle 10 `silent_purge()/silent_deploy()`-Stellen in `mainwindow.py` haben
  einen Running-Guard; die einzige bewusst ungeschuetzte ist
  `_purge_after_game()` aus `_on_unlock_clicked()` (Nutzerentscheidung).
* **Zwischenspeicher kann keinen Purge ausloesen:** `GAME_STOPPED` wird nie
  aus dem Cache beantwortet (`game_panel.py:2833-2839`). Nachgemessen: ein
  kuenstlich auf 999 s gesetzter STOPPED-Eintrag fuehrt zu einer Neuabfrage.
  Ein veralteter Wert kann also nur *bremsen*, nie loeschen.
* **Thread-Sicherheit:** `_game_state` wird als komplettes Tupel zugewiesen
  (unter der GIL atomar), Leser kopieren die Referenz in eine lokale Variable
  -> kein zerrissener Zustand. `_watch_generation += 1` laeuft ausschliesslich
  im GUI-Thread (`clear_watch_target`, `_start_process_watcher`), der Watcher
  liest nur.
* **Bleibt beim Timeout etwas dauerhaft liegen? Nein.** Das Watch-Ziel bleibt
  gesetzt (Live-Test bestaetigt `_watch_binary == 'slowgame.exe'`), damit
  liefert `game_state()` spaeter ein echtes STOPPED und `closeEvent`
  (`mainwindow.py:7143`), `_do_redeploy` (`:2337`) bzw. der Vorab-Purge
  raeumen auf. Eine Ausnahme beschreibt Befund N1.
* Architektur-Regeln 1-5 unberuehrt: kein Eingriff in Deployer,
  `.mods/`-Struktur, Frameworks, `active_mods.json` oder `modlist.txt`.
* Flatpak: `--talk-name=org.freedesktop.Flatpak` ist die richtige Berechtigung
  fuer `flatpak-spawn --host`. Das vom Release-Workflow gebaute Manifest
  (`com.github.Marc1326.AnvilOrganizer.yml`, `.github/workflows/flatpak.yml:23`)
  hatte sie schon; `net.anvil_organizer...yml` zieht damit nach.

---

## Findings

### [HIGH] N1 — Der Fallback haelt jedes Proton-Tool fuer das Spiel
- Datei: `anvil/widgets/game_panel.py:2803-2807` (`_search_terms`) i. V. m.
  `anvil/widgets/game_panel.py:2649-2653` (`_build_proton_env`) und
  `anvil/widgets/game_panel.py:2723-2765` (`run_with_proton`)
- Problem: `_build_proton_env()` setzt `env["SteamAppId"]` fuer **jeden**
  Proton-Start — auch fuer `run_with_proton()`, also xEdit, BodySlide, LOOT,
  Wrye Bash und jedes eigene Programm mit "Proton"-Haken. Der neue Fallback
  sucht nach genau dieser SteamAppId im `environ` fremder Prozesse. Ein
  laufendes Tool ist damit von einem laufenden Spiel nicht unterscheidbar.
  Experimentell belegt (offscreen):
  ```
  Prozess mit SteamAppId=489830 gestartet -> scan_proc_for_game('489830', None) = 1836414
  Treffer: 1836414  '.../python3 -c import time; time.sleep(...)'   # das "Tool"
  ```
  Folgen, solange ein Proton-Tool laeuft:
  * `mainwindow.py:1017` und `:1082` brechen die Basisverzeichnis- bzw.
    Speicher-Migration mit *"Beende das laufende Spiel …"* ab, obwohl kein
    Spiel laeuft. Das ist ein harter, falscher Funktionsblocker.
  * Auch die Schleife `mainwindow.py:1048` / `:1132` bricht mitten in der
    Migration ab — nach `switch_instance()`, also mit halb umgeschaltetem
    Zustand.
  * Jeder Spielstart zeigt den Angst-Dialog "Es sieht so aus, als wuerde noch
    ein Spiel laufen … stuerzt ab".
  * `closeEvent` (`:7143`), Instanzwechsel (`:1657`) und Profilwechsel
    (`:4754`) lassen das Deployment liegen.
  * Bleibt ein Tool oder ein `wineserver`/`explorer.exe` des Prefix haengen,
    raeumt Anvil in dieser Sitzung ueberhaupt nichts mehr auf. (Der Code
    selbst warnt an `game_panel.py:2714` davor, dass die SteamAppId-Suche
    Wine/Proton-Prozesse findet — genau das holt der Fallback zurueck.)
- Fix: In `run_with_proton()` eine Markierung setzen (z. B.
  `env["ANVIL_TOOL"] = "1"`) und im Scanner (`scan_proc_for_game` **und**
  `_HOST_SCAN`) Prozesse mit dieser Variable im `environ` ueberspringen.
  Alternativ im Fallback nur ueber den Binaernamen suchen und die
  SteamAppId-Spur `plugin_watch_target()` weglassen — dann faellt allerdings
  die Erkennung von Startern wie Windrose.exe aus.

### [MEDIUM] N2 — Zustands-Cache ueberlebt den Instanz-/Spielwechsel
- Datei: `anvil/widgets/game_panel.py:636` (`set_game` setzt `_current_plugin`,
  nicht aber `_game_state`), gelesen in `:2831`
- Problem: `_game_state` ist an keinen Suchbegriff gebunden. Nach einem
  Instanzwechsel beantwortet der Cache Fragen zu Spiel B mit der Messung von
  Spiel A. Nachgemessen:
  ```
  2a) Spiel A laeuft                      -> running
  2b) nach Instanzwechsel (B laeuft NICHT) -> running   | Cache: (…, 'running')
  ```
  Fenster: 3 s (Query-TTL) bzw. 15 s (Watcher-TTL). Folge: ein Start von
  Spiel B kann mit *"Es laeuft noch ein Spiel"* abgelehnt werden
  (`mainwindow.py:2608`), und die Migrationsschleife (`:1048`) bricht fuer die
  falsche Instanz ab. Ein Fehl-Purge ist nicht moeglich (STOPPED kommt nie aus
  dem Cache).
- Fix: In `set_game()` `self._game_state = None` setzen; sauberer waere, den
  Cache-Eintrag zusammen mit den Suchbegriffen zu speichern und bei
  Abweichung zu verwerfen.

### [MEDIUM] N3 — UNKNOWN schuetzt ausgerechnet den gefaehrlichsten Purge nicht
- Datei: `anvil/mainwindow.py:2608` und `anvil/widgets/game_panel.py:1920`
- Problem: Ueberall sonst gilt UNKNOWN als "laeuft" (`is_game_running()` ->
  True: `closeEvent`, `_do_redeploy`, Teardown, Profilwechsel). Nur der
  Vorab-Purge/Deploy — der einzige Pfad, der Dateien *waehrend* eines
  moeglicherweise laufenden Spiels anfasst — prueft auf `== GAME_RUNNING`,
  und `confirm_start_while_running()` fragt ebenfalls nur bei RUNNING. Faellt
  die Suche aus (Flatpak ohne Portal-Berechtigung, kein `python3`/`ps` auf dem
  Host, Zeitlimit unter Last), ist das Ergebnis UNKNOWN: Anvil fragt nichts
  und purged unter das laufende Spiel. Genau der Fehler, den die ganze Serie
  beseitigen soll — nur eine Ebene tiefer.
- Fix: `confirm_start_while_running()` auch bei `GAME_UNKNOWN` fragen, mit
  eigenem Text ("Anvil kann nicht feststellen, ob noch ein Spiel laeuft").

### [MEDIUM] N4 — `_forced_launch` bleibt im GRB- und REDmod-Zweig haengen
- Datei: `anvil/widgets/game_panel.py:1935` (gesetzt), `:1938-1942`
  (`take_forced_launch`), Zweige `:1988-1998` (Forge) und `:2003-2007` (REDmod)
- Problem: Nur `_predeploy_for_launch()` verbraucht das Flag. Die
  Forge-Variante (Ghost Recon Breakpoint) und der REDmod-Zweig kehren zurueck,
  ohne den Hook zu rufen — die Zustimmung "Trotzdem starten" bleibt
  unbegrenzt gespeichert. Nachgemessen:
  ```
  1) GRB-Zweig: _forced_launch nach Start = True   (erwartet: False)
  ```
  Dasselbe gilt, wenn der Start nach dem "Ja" abbricht (Steam nicht gefunden,
  Binary fehlt, Forge-Deploy schlaegt fehl, REDmod-Deploy scheitert). Heute
  nicht ausnutzbar, weil jeder der vier `_predeploy_for_launch`-Aufrufer
  (`mainwindow.py:1320`, `:2649`, `:2688`, `game_panel.py:2014`) vorher
  `confirm_start_while_running()` durchlaeuft, das die Variable auf False
  zuruecksetzt. Es ist aber eine scharfe Falle: der naechste neue Aufrufer
  erbt eine Zustimmung, die der Nutzer vor Minuten und fuer eine andere
  Instanz gegeben hat.
- Fix: Flag am Ende von `_on_start_clicked()`/`_do_launch()` und in jedem
  Fehler-Rueckweg zuruecksetzen, oder es an `_watch_generation` bzw. einen
  Zeitstempel koppeln.

### [LOW] N5 — Crash-Recovery sucht fuer jede Instanz, auch ohne Deployment
- Datei: `anvil/mainwindow.py:1586-1597`
- Problem: Der Docstring sagt "every directory with a live deployment is
  checked first", der Code prueft aber **jede** Instanz, bevor er ueberhaupt
  weiss, ob dort etwas liegt (`has_manifest` wird erst danach berechnet). In
  Flatpak ist jede Pruefung ein Host-Prozess. Gemessen: der reine Scan kostet
  21 ms je Aufruf bei 603 Prozessen (ohne `flatpak-spawn`-Aufschlag); im
  Fehlerfall bis zu 3 s (Python) + 3 s (ps-Fallback) je Instanz. Das laeuft
  im GUI-Thread in `_check_first_start()`, also bevor das Fenster erscheint.
- Fix: Erst `has_manifest` bzw. `is_deployed()` pruefen, nur bei vorhandenem
  Deployment die Prozesssuche starten — oder das Ergebnis der Suche einmal je
  Spielpfad/AppId zwischenspeichern.

### [LOW] N6 — Ohne Plugin-Treffer purged die Crash-Recovery ungeschuetzt
- Datei: `anvil/mainwindow.py:1587-1589`
- Problem: `if app_id or binary:` — liefert `plugin_loader.get_game()` None
  (unbekannter/umbenannter `game_short_name`) oder fehlen dem Plugin beide
  Attribute, faellt der Schutz komplett weg und es wird gepurged, obwohl das
  Spiel laufen koennte. Aktuell haben alle 11 ausgelieferten Plugins beide
  Attribute (geprueft), der Fall ist also nur ueber eine verwaiste Instanz
  erreichbar.
- Fix: Fehlende Suchmerkmale wie UNKNOWN behandeln (Deployment behalten und
  eine Zeile ins Log schreiben), statt sie als "sicher gestoppt" zu lesen.

### [LOW] N7 — Ein bestaetigter Stopp waehrend des Entsperr-Dialogs geht verloren
- Datei: `anvil/mainwindow.py:2744-2752` und `:2775-2778`
- Problem: `_unlock_pending` laesst `_unlock_ui()` sofort zurueckkehren. Ein
  `game_stopped(True)`, das waehrend des offenen Dialogs eintrifft, wird damit
  ersatzlos verworfen — der Watcher-Thread ist danach beendet. Antwortet der
  Nutzer mit "Nein", bleibt das Deployment liegen, obwohl bewiesen ist, dass
  das Spiel beendet wurde. Selbstheilend beim naechsten Purge-Anlass, aber
  unnoetig.
- Fix: Die gemeldete Antwort merken (`self._pending_stop = stopped`) und nach
  dem Dialog auswerten.

### [LOW] N8 — Wettlauf zwischen `outdated()` und `game_stopped.emit()`
- Datei: `anvil/widgets/game_panel.py:2875-2882` (`outdated`/`observe`), Emissionen `:2911-2912`, `:2933-2934`, `:2939-2940`
- Problem: Zwischen der `outdated()`-Pruefung und dem `emit()` kann ein neuer
  Start die Generation erhoehen. Der alte Stopp wird dann fuer den neuen Start
  zugestellt; `_unlock_ui()` ruft `_release_ui_lock()` bedingungslos, die
  UI-Sperre faellt also waehrend des neuen Spiels weg. Dateien bleiben liegen,
  weil `is_game_running()` frisch nachfragt. Fenster: Mikrosekunden, und ein
  neuer Start setzt eine vorherige Entsperrung voraus — praktisch nicht
  erreichbar, aber der Vollstaendigkeit halber notiert.
- Fix (optional): Generation im Signal mitschicken und im Slot vergleichen.

### [LOW] N9 — `net.anvil_organizer…yml` bleibt hinter dem anderen Manifest zurueck
- Datei: `packaging/flatpak/net.anvil_organizer.AnvilOrganizer.yml:7-28`
- Problem: Die neue Zeile ist korrekt, aber diesem Manifest fehlen weiterhin
  `--talk-name=org.freedesktop.portal.Desktop` (NXM-Handler),
  `--talk-name=org.freedesktop.secrets` und `--talk-name=org.kde.kwalletd5/6`
  (Nexus-Schluessel), die `com.github.Marc1326.AnvilOrganizer.yml` seit
  Laengerem hat. Kein Regress dieser Aenderung, faellt nur auf, weil die Datei
  angefasst wurde. Wenn das lokal installierte Flatpak aus diesem Manifest
  gebaut wird, funktionieren Schluesselspeicher und NXM-Links dort nicht.
- Fix: Beide Manifeste angleichen (analog zum bekannten Zwei-Build-Pfad-Thema
  beim AppImage).

---

## Ergebnis

**NEEDS FIXES**

Alle acht Befunde aus Runde 3 sind sauber behoben und durch Tests abgedeckt;
die neue Zustands-Maschine ist in sich stimmig (STOPPED nie aus dem Cache,
Generationszaehler, Blindflug-Karenz). Neu hinzugekommen ist mit dem
Plugin-Fallback aber eine Verwechslung von Proton-Tools mit dem Spiel (N1),
die eine dokumentierte Funktion (Speicher-/Basisverzeichnis-Migration) falsch
blockiert, dazu ein Cache, der ueber den Instanzwechsel hinweg gilt (N2), und
eine Luecke bei UNKNOWN im gefaehrlichsten Pfad (N3).

Vor dem Commit zu beheben: **N1, N2, N3**. N4 sollte mit, weil es billig ist
und die naechste Aenderung sonst darueber stolpert. N5-N9 nach Marcs Ermessen.
