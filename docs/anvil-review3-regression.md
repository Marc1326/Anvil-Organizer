# QA Runde 3 — Regressions- und Auslieferungsprüfung
Datum: 2026-08-06
Prüfstand: nicht committete Änderungen auf `main` (HEAD = d174cd6 „v1.7.0")
Referenz: `git show HEAD:anvil/widgets/game_panel.py`, `git show HEAD:anvil/mainwindow.py`

Geänderte Dateien laut `git status --porcelain`:
`A anvil/core/debug_log.py`, `A anvil/core/game_process.py`, `M anvil/core/diagnostics.py`,
`M anvil/main.py`, `M anvil/mainwindow.py`, `M anvil/widgets/game_panel.py`,
`M anvil/locales/{de,en,es,fr,it,pt,ru}.json`,
`M packaging/flatpak/net.anvil_organizer.AnvilOrganizer.yml`,
`M tests/test_predeploy_launch.py`, `M tests/test_game_ghostreconbreakpoint.py`

---

## 1. Verifikation der vier Fixes aus Runde 2

### 1.1 Direktstart-Watcher zurückgebaut — ✅ bestätigt, aber mit Folgeloch
`grep -rn "notify_game_started" --include=*.py .` liefert genau zwei Codestellen:
```
anvil/mainwindow.py:2666:        self._game_panel.notify_game_started(pid)
anvil/widgets/game_panel.py:2043:    def notify_game_started(self, pid: int) -> None:
```
Beide sind **byte-identisch mit HEAD** (`git show HEAD:… | grep -A3 notify_game_started`
→ `def notify_game_started(self, pid: int)` + `self.game_started.emit(self._game_label.text(), pid)`).
Der Direktstart startet also wieder **keinen** Watcher, das Windrose-Risiko
(`GameBinary = "Windrose.exe"` ≠ `Windrose-Win64-Shipping.exe`) ist weg.

Verhaltensvergleich Direktstart HEAD ↔ jetzt (`_on_start_clicked` → `_do_launch` →
`start_requested` → `_on_start_game`):

| Schritt | HEAD | jetzt | Delta |
|---|---|---|---|
| Vorab-Deploy | `_predeploy_for_launch` | dito, zusätzlich Ablehnung bei `game_state()==RUNNING` | nur bei gesetztem Watch-Ziel; beim Direktstart nie gesetzt → identisch |
| Popen + Fehlerdialog | identisch | identisch | – |
| `notify_game_started(pid)` → `_lock_ui` | identisch | identisch | – |
| Watcher | keiner | keiner | – |
| Entsperren | `_unlock_ui()` → purgt still | `_on_unlock_clicked()` → **Rückfrage** | **Verhaltensänderung**, siehe §3 A1 |
| Anvil schließen | `silent_purge()` | übersprungen, weil `_game_running` True | **Verhaltensänderung**, siehe §3 A2 |

Der Startpfad selbst entspricht HEAD. Die beiden Deltas liegen danach und sind gewollt —
das Folgeproblem daraus steht als **H1**.

### 1.2 `_clear_watch_target()` → `clear_watch_target()` — ⚠️ teilweise
Öffentlich umbenannt, Definition `anvil/widgets/game_panel.py:2767`. Aufrufer:
```
anvil/mainwindow.py:2754   _on_unlock_clicked  → nach _purge_after_game()
anvil/mainwindow.py:2779   _unlock_ui          → nach _purge_after_game()
anvil/widgets/game_panel.py:1926  _confirm_start_while_running → VOR dem Purge
```
Die Vorgabe „Aufruf nur noch aus mainwindow.py nach erfolgtem Purge" ist damit **nicht**
erfüllt: es gibt einen dritten Aufruf in `game_panel.py`, und er steht dort *vor* dem
Purge (er macht den Purge überhaupt erst möglich). Funktional ist das beabsichtigt
(„Nutzer startet trotzdem"), die Beschreibung stimmt aber nicht. In `_start_process_watcher`
selbst wird nicht mehr gecleart (`git grep -n "clear_watch_target" anvil/widgets/game_panel.py`
→ nur 1926 und die Definition), der Timeout-Zweig lässt das Ziel stehen — das war der
eigentliche Punkt und ist erfüllt.

### 1.3 `_SCAN_TIMEOUT` getrennt von `_SCAN_FAILED` — ✅ empirisch bestätigt
Gemessen **in der echten Sandbox** (`flatpak run --command=python3 com.github.Marc1326.AnvilOrganizer`,
neuer Code per `sys.path` hineingereicht):
```
is_flatpak: True
PIDs sichtbar in /proc: 2
A) flatpak-spawn --host <fehlender Befehl>  -> rc=1, "Portal call failed: Failed to start command"
B) find_game_process(None,'steamwebhelper')            -> (22491, True)   0.02 s
C) python3 auf dem Host FEHLT -> ps-Fallback           -> (22491, True)   0.03 s   ✅
C2) python3 fehlt, nur app_id (ps kann kein environ)   -> (None, False)   → UNKNOWN ✅
D) _host_scan_via_python liefert _SCAN_TIMEOUT         -> (None, False), ps-Fallback aufgerufen: False ✅
E) echter Host-Timeout (Scan schläft 30 s)             -> (None, False), ps-Fallback aufgerufen: False, 3.00 s ✅
```
Wichtig für die Frage: ein fehlendes `python3` erzeugt **kein** `OSError`, sondern
`returncode=1` → `_SCAN_FAILED` → ps-Fallback greift (Messung C). Die Timeout-Trennung
kostet den Fallback also nicht.

### 1.4 `_confirm_start_while_running()` — ✅ vorhanden, Abdeckung siehe §2
Definition `anvil/widgets/game_panel.py:1907-1927`, Aufruf `:1956-1959` in
`_on_start_clicked`, **vor** allen Deploy-Zweigen (GRB `:1973`, REDmod `:1988`,
Steam-Predeploy-Hook `:1998`, `_do_launch` `:2008`).
**Nicht** abgedeckt: der Zweig für eigene Programme (`exe.get("custom")`, `:1940-1950`),
der vorher `return`t.

---

## 2. Startpfade — Durchgang

| Pfad | Einstieg | `_confirm_start_while_running` | Purge/Deploy vorher | Watcher | Aufräumen |
|---|---|---|---|---|---|
| Start-Button (Steam, Hauptbinary) | `_on_start_clicked` → `_do_launch` → `_launch_via_steam` (2567) | ✅ | `_predeploy_hook` (1998) | ✅ `_start_process_watcher(name, app_id)` (2606) | ✅ |
| Start-Button (Steam, Nebenbinary/Proton) | → `_launch_via_proton` (2652) | ✅ | `_predeploy_hook` | ✅ `(GameBinary, proc, app_id=None)` (2699) | ✅ |
| Direktstart GOG/Epic | → `start_requested` → `_on_start_game` (2640) | ✅ | `_predeploy_for_launch` (2594) | ❌ keiner (bewusst) | nur über Entsperren-Knopf |
| REDmod | `_on_start_clicked` (1988) → alle drei Zweige (2152/2275/2295) → `_do_launch` | ✅ | `silent_deploy()` (1990) + Zielpfad | erbt vom Zielpfad | ok |
| GRB/Forge | `_on_start_clicked` (1973) `silent_deploy()` | ✅ | ja | erbt vom Zielpfad | ok |
| Verknüpfung (.desktop/IPC) | `launch_instance_shortcut` (6990) → `start_selected` (943) → `_on_start_clicked` | ✅ | wie oben | wie oben | ok |
| Eigene Programme (Custom Tools) | `_on_start_clicked` (1944) `custom_start_requested` → `_on_custom_tool_start` (2668) | ❌ | `_predeploy_for_launch` → **harte Ablehnung** | kein Lock (gewollt) | – |
| Proton-Tools (Menü) | `_run_proton_tool` (1306) | ❌ | `_predeploy_for_launch` → **harte Ablehnung** | kein Lock (gewollt) | – |

Belegt: `_do_launch` wird ausschließlich aus `_on_start_clicked` und der REDmod-Kette
gerufen (`grep -n "_do_launch" anvil/widgets/game_panel.py` → 2008, 2010, 2152, 2275, 2295).

---

## 3. Verhaltensunterschiede zu HEAD außerhalb Flatpak

Außerhalb Flatpak liefert `find_game_process()` immer `reliable=True`
(`game_process.py:155-156`), `GAME_UNKNOWN` ist dort unerreichbar. Damit ist
`is_game_running()` semantisch gleich wie HEADs `find_game_pid() is not None` — mit
folgenden Ausnahmen:

**A1 — Entsperren fragt jetzt nach.** `mainwindow.py:330` verbindet den Knopf auf
`_on_unlock_clicked` statt `_unlock_ui`. Bei vorhandenem Deployment erscheint immer
ein Ja/Nein-Dialog. HEAD purgte still. Gewollt, aber sichtbar bei **jedem** Direktstart,
weil dort das Entsperren der einzige Weg zurück ist.

**A2 — `closeEvent` purgt nicht mehr, solange `_game_running` gesetzt ist**
(`mainwindow.py:7132`). Beim Direktstart bleibt `_game_running` bis zum manuellen
Entsperren True → Anvil schließen ohne Entsperren lässt die Mods im Spielordner.
Der Ersatz („der nächste Start räumt auf") greift nicht zuverlässig, siehe **H2**.

**A3 — `_do_redeploy`, Instanzwechsel, Profilwechsel, Speicher-Migration** purgen nicht
mehr, wenn `_game_running or is_game_running()` (2333, 1653, 4743, 1047/1131). Neu, gewollt.

**A4 — `game_state()`-Zwischenspeicher (15 s).** `RUNNING`/`UNKNOWN` werden bis zu
`_GAME_STATE_TTL` aus dem Cache beantwortet (`game_panel.py:30, 2795-2807`); `STOPPED`
nie. HEAD fragte jedes Mal live. Sicherheitsseitig unkritisch.

**A5 — Poll-Intervall 2 s → 5 s** (`_GAME_POLL_INTERVAL`, `game_panel.py:2763`): das
Deployment bleibt nach Spielende bis zu 3 s länger liegen.

**A6 — `_GAME_APPEAR_TIMEOUT` ist jetzt echte Wanduhr** (`while time.monotonic() < deadline`)
statt 120 Iterationen à 1 s + Suchzeit → die Wartephase ist etwas kürzer als vorher.

**A7 — Eigener PID wird beim Scan übersprungen** (`game_process.py:33`) und der
Suchbegriff zusätzlich kleingeschrieben (`:29`). Reine Verbesserung.

**A8 — `_crash_recovery_purge` überspringt bei Verdacht auch `remove_orphaned_links()`**
(`mainwindow.py:1594 continue`). In HEAD lief die Verwaisten-Bereinigung immer.

Kein weiterer Verhaltensunterschied gefunden; die übrigen Änderungen sind
Umstrukturierungen (`_purge_after_game`, `_release_ui_lock`) ohne eigene Logik.

---

## Findings

### [HIGH] H1 — `_predeploy_for_launch()` ist der einzige Purge-Wächter ohne `self._game_running`
- Datei: `anvil/mainwindow.py:2599`, dazu `anvil/widgets/game_panel.py:1913`
- Problem: Nach dem Rückbau aus Runde 2 gibt es beim Direktstart (GOG/Epic, alle
  Nicht-Steam-Stores) **keinen Watcher**. `_watch_binary`/`_watch_app_id` bleiben leer,
  `game_state()` steigt in `game_panel.py:2796-2797` sofort mit `GAME_STOPPED` aus.
  Die einzige verbleibende Information, dass ein Spiel läuft, ist `self._game_running`.
  Alle sechs anderen Wächter prüfen sie:
  `mainwindow.py:1653`, `:2333`, `:4743`, `:7132`, `:1016`, `:1081`.
  `_predeploy_for_launch` (`:2599`) und `_confirm_start_while_running`
  (`game_panel.py:1913`) prüfen sie **nicht** — genau die beiden Stellen, die vor einem
  Start purgen und deployen.
- Erreichbar, obwohl die UI gesperrt ist:
  1. `launch_instance_shortcut` (`mainwindow.py:6990`) ruft
     `QTimer.singleShot(0, self._game_panel.start_selected)` — ein **programmatischer**
     Aufruf. `_lock_ui` setzt nur `self._splitter.setEnabled(False)` (`:2716`), und der
     GamePanel hängt in genau diesem Splitter (`:311`). `setEnabled(False)` blockiert
     Eingaben, keine Methodenaufrufe. Ein zweiter Doppelklick auf die .desktop-Verknüpfung
     läuft also mitten in das laufende Spiel: `_confirm_start_while_running` → STOPPED →
     durch, `_predeploy_for_launch` → STOPPED → `silent_purge()` + `silent_deploy()`.
  2. Nach „Entsperren → Nein" ist `_game_running` False und das Watch-Ziel beim
     Direktstart ohnehin leer — dann purgt schon die nächste Mod-Änderung
     (`_schedule_redeploy` → `_do_redeploy`, 500 ms Debounce).
- Kein Regress gegenüber HEAD (dort fehlte der Schutz ebenfalls), aber der Fix ist an
  dieser Stelle unvollständig, und der Rückbau hat den einzigen Ersatz entfernt.
- Fix: `if self._game_running or self._game_panel.game_state() == GAME_RUNNING:` in
  `_predeploy_for_launch`; `_confirm_start_while_running()` einen Parameter
  `assume_running: bool` geben oder die Rückfrage nach MainWindow verlagern, wo
  `_game_running` bekannt ist.

### [HIGH] H2 — `_crash_recovery_purge()`: Pfad-Suche trifft Prozessleichen, Aufräumen unterbleibt dauerhaft
- Datei: `anvil/mainwindow.py:1583-1594`
- Problem: Der neue Wächter sucht mit dem **Spielordnerpfad** als Kommandozeilen-Muster:
  `pid, reliable = find_game_process(None, str(game_path))`. Auf Marcs Rechner **jetzt
  gemessen** (nur lesend, über die echten Instanzen):
  ```
  Cyberpunk 2077   -> (1443772, True)   /mnt/Gaming/SteamLibrary/steamapps/common/Cyberpunk 2077
  ```
  Der Treffer ist eine Leiche:
  ```
  PID 1443772  PPID 1 (systemd --user)  ELAPSED 03:39  comm=sleep
  /home/mob/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=1091500 -- \
    '/mnt/Gaming/SteamLibrary/steamapps/common/Cyberpunk 2077/REDprelauncher.exe' --launcher-skip 600
  ```
  Weder `Cyberpunk2077.exe` noch `wine`/`proton` laufen (`ps -eo … | grep -iE
  "Cyberpunk2077.exe|REDprelauncher|wine|proton"` findet nur diesen einen Eintrag).
  Ein verwaister Steam-`reaper` überlebt das Spiel und trägt den Spielpfad dauerhaft in
  seiner Kommandozeile.
- Folge in Verbindung mit A2 (`closeEvent` purgt nicht mehr): Für diese Instanz wird beim
  nächsten Anvil-Start **weder** `deployer.purge()` **noch** `remove_orphaned_links()`
  ausgeführt (`continue` in Zeile 1594). Die Mods bleiben unbegrenzt im Spielordner —
  bis der Zombie stirbt. Die Begründung im Docstring von `closeEvent`
  („The next start cleans up instead") trägt damit nicht.
  (Für Cyberpunk fällt es heute nicht auf, weil die Instanz gerade kein
  `.deploy_manifest.json` hat — der Zweig gilt nur bei vorhandenem Manifest.)
- Weitere Falsch-Positive derselben Bauart, live reproduziert:
  `scan_proc_for_game(None, 'cyberpunk2077.exe')` traf meine eigene `ps | grep`-Pipeline.
- Fix: nicht auf den Ordnerpfad matchen. Besser das Watch-Ziel (`app_id`, `binary`,
  Instanz) beim Start in eine Datei unter `anvil_base_paths().base` schreiben und beim
  nächsten Start damit prüfen; die Datei löschen, sobald `clear_watch_target()` greift.
  Mindestens: `remove_orphaned_links()` auch im Verdachtsfall laufen lassen und den
  Treffer auf `argv[0]`/`comm` statt auf die gesamte Kommandozeile einschränken.

### [HIGH] H3 — Neuer Test ist flaky und bricht die Suite
- Datei: `tests/test_predeploy_launch.py:746-767`
  (`test_an_old_watcher_does_not_report_for_a_new_launch`)
- Problem: `panel.game_stopped.connect(seen.append)` steht **nach** den beiden
  `_start_process_watcher()`-Aufrufen. Mit `_GAME_APPEAR_TIMEOUT = 0` läuft der zweite
  Watcher-Thread sofort in den Timeout und ruft `game_stopped.emit(True)` — unter Last
  bevor `connect()` im Hauptthread ausgeführt wurde. Dann bleibt `seen` leer, die
  10-s-Warteschleife läuft voll aus und der Test fällt durch.
- Gemessen: 3 Fehlschläge in 45 vollen Suite-Läufen (≈7 %), jeweils
  ```
  E  AssertionError: 0 != 1 : only the current watcher may report
  FAILED tests/test_predeploy_launch.py::SandboxedProcessLookupTests::test_an_old_watcher_does_not_report_for_a_new_launch
  ```
  und einer Laufzeit von 12,3 s statt 2,4 s. Isoliert (`pytest tests/test_predeploy_launch.py`,
  10 Läufe) trat es nicht auf — es braucht die Last der ganzen Suite.
- Fix: `panel.game_stopped.connect(seen.append)` vor die beiden
  `_start_process_watcher()`-Aufrufe ziehen (so wie es
  `test_appear_timeout_leaves_the_target_in_place` bereits macht) und die Warteschleife
  auf ein kurzes Zeitbudget setzen.

### [MEDIUM] M1 — Die neuen Tests sichern die neuen Fixes praktisch nicht ab
- Datei: `tests/test_predeploy_launch.py` (`_bind_unlock_helpers`, Zeile 49-57)
- Belegt durch Mutationstest auf einer Kopie des Baums
  (`anvil/ tests/ main.py pyproject.toml` nach `/tmp/.../mut`, Original unangetastet).
  Jede Mutation einzeln, danach die volle Suite ohne
  `test_base_migration_dialog.py` und `test_aur_packaging.py`:

  | Mutation | Ergebnis |
  |---|---|
  | `clear_watch_target()` aus `_on_unlock_clicked` entfernt | **nicht erkannt** (296 passed) |
  | Aufruf `_confirm_start_while_running()` aus `_on_start_clicked` entfernt | **nicht erkannt** |
  | `clear_watch_target()` aus `_unlock_ui` entfernt | **nicht erkannt** |
  | `_launch_refused`-Guard entfernt (Doppeldialog zurück) | **nicht erkannt** |
  | `clear_watch_target()` im Ja-Zweig von `_confirm_start_while_running` entfernt | **nicht erkannt** |
  | Wächter in `_crash_recovery_purge` entfernt (`if False:`) | **nicht erkannt** |
  | `game_state()`-Cache liefert auch `STOPPED` | **nicht erkannt** |
  | `_SCAN_TIMEOUT`-Frühausstieg entfernt | nicht erkannt (der einmalige Fehlschlag war H3, bei Wiederholung grün) |

  8 von 8 Mutationen unentdeckt.
- Ursache: `_bind_unlock_helpers` hängt `clear_watch_target = lambda: None` an die
  `SimpleNamespace`-Attrappen, ohne die Aufrufe je zu zählen. `_confirm_start_while_running`
  hat gar keinen eigenen Test — der neue Eintrag in
  `tests/test_game_ghostreconbreakpoint.py:172` ist ein reiner Kompatibilitäts-Stub.
- Fix: Aufrufe mitzählen statt wegzustubben
  (`panel.clear_watch_target = lambda: calls.append("clear")`), und je einen Test für
  `_confirm_start_while_running` (Nein → kein Start, Ja → Ziel gelöscht, kein Watch-Ziel →
  keine Rückfrage) sowie für den `_crash_recovery_purge`-Wächter.

### [MEDIUM] M2 — Der Entsperren-Dialog verspricht etwas, das der Redeploy-Timer sofort bricht
- Datei: `anvil/locales/de.json` (`dialog.unlock_purge_text`), `anvil/mainwindow.py:2311-2337`
- Problem: Der Text sagt „Beim nächsten Spielstart räumt Anvil ohnehin auf." Wer „Nein"
  wählt, landet in `_unlock_ui(False)` → UI frei, `_game_running = False`. Beim
  Direktstart ist zusätzlich kein Watch-Ziel gesetzt, `is_game_running()` also False.
  Die nächste Mod-Änderung startet `_schedule_redeploy()` (500 ms) → `_do_redeploy()` →
  der Wächter in `:2333` greift nicht → `silent_purge()`. Aufgeräumt wird also nicht
  „beim nächsten Spielstart", sondern beim nächsten Klick — unter dem laufenden Spiel.
- Fix: gehört zu H1. Solange `_game_running` in `_predeploy_for_launch`/`_do_redeploy`
  nach dem Entsperren nicht mehr gilt, ist die Zusage im Text nicht haltbar.

### [MEDIUM] M3 — Tool-Starts werden hart abgelehnt statt gefragt, ohne Ausweg
- Datei: `anvil/mainwindow.py:2668` (`_on_custom_tool_start`), `:1306` (`_run_proton_tool`),
  beide über `_predeploy_for_launch` `:2599-2610`
- Problem: Beim Spielstart darf der Nutzer per Rückfrage entscheiden
  (`_confirm_start_while_running`); für eigene Programme und Proton-Tools gibt es nur
  `tr("error.game_already_running")` und Abbruch. Die Suche kann sich irren — der
  Code sagt das selbst (`game_panel.py:1910` „The lookup can be wrong — a stray command
  line carrying the binary name is enough"), und §H2 zeigt einen echten Fall. Dann sind
  xEdit, BodySlide und LOOT gesperrt, bis der Nutzer den Umweg über Spielstart-Dialog
  oder Entsperren-Knopf findet.
- Fix: dieselbe Rückfrage auch für Tool-Starts, oder im Dialog einen Hinweis, wie man
  den Zustand zurücksetzt.

### [MEDIUM] M4 — `_confirm_start_while_running()` fragt bei `UNKNOWN` nicht nach
- Datei: `anvil/widgets/game_panel.py:1913`
- Problem: `if self.game_state() != GAME_RUNNING: return True`. `GAME_UNKNOWN` (Flatpak,
  Host-Suche gescheitert) läuft also **ohne Rückfrage** durch, und
  `_predeploy_for_launch` prüft ebenfalls nur `== GAME_RUNNING` (`mainwindow.py:2599`).
  Damit purgt und deployt Anvil in genau dem Zustand, für den der ganze Umbau gemacht
  wurde. Alle Aufräumpfade behandeln `UNKNOWN` dagegen als „läuft"
  (`is_game_running()` = `game_state() != GAME_STOPPED`, `game_panel.py:2824`).
- Die Asymmetrie ist im Code begründet (Nutzer nicht aussperren) — die Rückfrage wäre
  aber genau das Mittel, das beides erlaubt.
- Fix: bei `UNKNOWN` denselben Dialog zeigen (Text ist schon passend formuliert:
  „Es sieht so aus, als würde noch ein Spiel laufen").

### [MEDIUM] M5 — `net.anvil_organizer`-Manifest weiter nicht auslieferbar (aus Runde 2 offen)
- Datei: `packaging/flatpak/net.anvil_organizer.AnvilOrganizer.yml`
- Neu ist nur `--talk-name=org.freedesktop.Flatpak` (Zeile 28). Unverändert offen,
  durch erneutes Lesen belegt:
  - `--filesystem=/media:ro`, `/mnt:ro`, `/run/media:ro`, `~/.steam:ro` (Zeilen 14-18) —
    Deploy legt Symlinks im Spielordner an, auf Zweitplatten damit unmöglich.
  - `--filesystem=~/.anvil:create` (Zeile 21) — der echte Basisordner ist
    `~/.anvil-organizer` (`anvil/core/base_dir.py`, real vorhanden:
    `/home/mob/.anvil-organizer/logs`). Auch das neue `logs/debug.log` wäre unerreichbar.
  - Kein `--filesystem=home` → GOG/Epic-Ordner unerreichbar.
  - Es fehlen `--talk-name=org.freedesktop.portal.Desktop`, `org.freedesktop.secrets`,
    `org.kde.kwalletd5`, `org.kde.kwalletd6` — im Schwestermanifest
    `com.github.Marc1326.AnvilOrganizer.yml:25-31` alle vorhanden.
  - `sources: type: git, tag: v1.2.2, commit: 3dd4eb87…` (Zeilen 78-82) — dieses Manifest
    baut einen Stand, in dem `anvil/core/game_process.py` gar nicht existiert. Der neu
    hinzugefügte talk-name wirkt auf einen Build ohne die Prozesssuche.
- Fix: auf den Stand des Schwestermanifests bringen oder ausdrücklich als ungepflegt
  markieren. `.github/workflows/flatpak.yml:23` baut ohnehin nur
  `com.github.Marc1326.AnvilOrganizer.yml` (`type: dir, path: ../..`).

### [LOW] L1 — PEP8 E302 weiterhin offen (aus Runde 2)
- `anvil/widgets/game_panel.py:36-38`: zwischen `_state_of()` und `_dlog()` steht nur
  eine Leerzeile (mit `cat -A` geprüft).

### [LOW] L2 — Sichtbarer String ohne `tr()` (aus Runde 2, nur umbenannt)
- `anvil/core/diagnostics.py:253`: `{"label": "debug.log (src)", …}`. Der deutsche
  Klammerzusatz ist weg, aber der Text ist weiterhin fest verdrahtet und erscheint im
  Diagnose-Tab in allen sieben Sprachen gleich.

### [LOW] L3 — `_launch_refused` nicht in `__init__` gesetzt
- `anvil/mainwindow.py:2597` (Setzen), `:2643` (Lesen ohne `getattr`-Absicherung).
  Heute sicher, weil `_predeploy_for_launch()` immer vorher läuft. `_unlock_pending`
  ist an derselben Stelle defensiv geholt (`:2765 getattr(...)`) — uneinheitlich.

### [LOW] L4 — `game_stopped` während des Entsperren-Dialogs wird verworfen
- `anvil/mainwindow.py:2765-2768`: Trifft `game_stopped(True)` ein, während der Dialog
  offen ist, kehrt `_unlock_ui` sofort zurück. Antwortet der Nutzer danach „Nein",
  bleibt das Deployment liegen, obwohl das Spiel nachweislich beendet ist. Aufgeräumt
  wird dann erst beim nächsten Start.

### [LOW] L5 — Entsperren ohne Deployment löscht das Watch-Ziel nicht
- `anvil/mainwindow.py:2728-2731`: `_unlock_ui(False)` → Zweig „state unknown", Ziel
  bleibt gesetzt. Danach melden alle Wächter weiter „läuft", obwohl nichts deployt ist.

### [LOW] L6 — `start_debug_log()` läuft weiter erst nach dem Single-Instance-Check
- `anvil/main.py:150-153`. Tracebacks aus Basisordner-Auswahl, Theme- und Plugin-Laden
  landen weiterhin nicht in `logs/debug.log`. Begründung steht im Kommentar, der Nutzen
  bleibt eingeschränkt. Unverändert seit Runde 2.

### [LOW] L7 — `game_state()` kann den GUI-Thread bis 3 s blockieren (aus Runde 2, verbessert)
- `anvil/widgets/game_panel.py:2795-2809`. `STOPPED` wird bewusst nie zwischengespeichert,
  also fragt jeder `is_game_running()`-Aufruf bei gesetztem Ziel live nach. In Flatpak
  ist das ein Host-Prozess mit `_HOST_SCAN_TIMEOUT = 3` (gemessen: 3,00 s im Timeoutfall,
  Messung E). Betroffen: `_do_redeploy` (2333), Instanzwechsel (1653), Profilwechsel
  (4743), `closeEvent` (7132), Migration (1047/1131). Durch den Wegfall des
  ps-Nachschlags nach Timeout jetzt maximal 3 s statt 6 s — der Punkt ist entschärft,
  nicht behoben. Zusätzlich ruft `_crash_recovery_purge` beim Start je Instanz mit
  Manifest einen weiteren Lookup auf (auf dem Host gemessen: 0,005 s je Instanz, in
  Flatpak je ein Host-Prozess).

### [LOW] L8 — Arbeitsverzeichnis vor dem Commit aufräumen
- `001Bericht/` ist untracked und enthält Fundus-Material (`DESIGN-BERICHT.md`,
  `Fundus Design Varianten.zip`, `icons/`) — gehört nicht ins Anvil-Repo.
- `docs/` ist nicht in `.gitignore` (nur `docs/workflow/`); ein `git add -A` würde
  `anvil-offene-punkte-04-08.md`, `anvil-review*.md` und diese Datei mit einchecken.

---

## 4. Signal `game_stopped = Signal(bool)`
Deklaration `anvil/widgets/game_panel.py:228`. Alle Sender übergeben genau ein bool:
```
game_panel.py:2880   self.game_stopped.emit(blind_since is None)   # "nie erschienen"
game_panel.py:2902   self.game_stopped.emit(False)                 # Suche dauerhaft blind
game_panel.py:2908   self.game_stopped.emit(True)                  # Prozess sauber weg
```
Einziger Empfänger: `mainwindow.py:436` `self._game_panel.game_stopped.connect(self._unlock_ui)`
mit `def _unlock_ui(self, stopped: bool = True)` (`:2759`). Der Default hält die
Bestandsaufrufe (`_on_unlock_clicked` ruft `_unlock_ui(False)`) kompatibel.
Kein weiterer Verbraucher im Repo (`grep -rn "game_stopped" --include=*.py`).
Alle drei `emit`-Stellen stehen hinter `if not outdated():` (Generationszähler
`_watch_generation`, `game_panel.py:2838-2845`), ein alter Watcher kann nicht mehr für
einen neuen Start melden. Emission aus dem Watcher-Thread, Zustellung per
Auto-Connection im GUI-Thread. ✅

`game_started = Signal(str, int)`: Sender 2045 (Direktstart), 2603 (Steam), 2694 (Proton);
Empfänger `mainwindow.py:435` `_on_game_started(game_name, pid)`. ✅

---

## 5. Paketierung — beide neuen Module in allen Build-Pfaden ✅
Erreichbarkeit im Import-Graph ab dem Spec-Einstieg `main.py` (eigener AST-Scan, dem
PyInstaller-Modulegraph nachgebaut, 109 `anvil*`-Module):
```
anvil.core.debug_log: JA      anvil.core.game_process: JA
anvil.core.activity_log: JA   anvil.core.diagnostics: JA
```
(`anvil.core.game_process` wird auf Modulebene importiert — `game_panel.py:20` — und
zusätzlich funktionslokal in `mainwindow.py:1570`; `anvil.core.debug_log` funktionslokal
in `main.py:152`. Beide Formen findet PyInstaller im Bytecode.)

| Build-Pfad | Mechanik | Bewertung |
|---|---|---|
| `pyproject.toml` | `[tool.setuptools.packages.find] include = ["anvil*"]` (Zeile 63-64); `package-data` betrifft nur Nicht-Python-Dateien | ✅ nimmt `anvil/core/*.py` komplett |
| `packaging/aur/PKGBUILD`, `packaging/aur-git/PKGBUILD` | `python -m build --wheel --no-isolation` + `python -m installer` | ✅ |
| `packaging/deb/debian/rules` | `dh --with python3 --buildsystem=pybuild` | ✅ |
| `packaging/rpm/anvil-organizer.spec` | `pip3 install … .`, `%files: %{python3_sitelib}/anvil/` | ✅ |
| `packaging/snap/snapcraft.yaml` | `plugin: python`, `source: .` | ✅ |
| `packaging/flatpak/com.github…yml` | `type: dir, path: ../..` + `pip3 install … .` | ✅ |
| `packaging/flatpak/net.anvil_organizer…yml` | `type: git, tag: v1.2.2` | ❌ siehe M5 |
| `anvil-organizer.spec` + `build-appimage.sh` + `.github/workflows/appimage.yml` | PyInstaller ab `main.py`, keine Datei-Whitelist für `.py` | ✅ keine Anpassung nötig |
| `.github/workflows/{flatpak,rpm,snap}.yml` | bauen die oben geprüften Manifeste/Specs | ✅ |

Keine Änderung an `hiddenimports` nötig — beide Module sind statisch erreichbar.

---

## 6. Tests und Kompilierung

```
$ python3 -m pytest tests/ -q --ignore=tests/test_base_migration_dialog.py
299 passed, 1 skipped in 2.39s
```
Aber: **bei 45 Wiederholungen 3 Fehlschläge** — siehe H3. Ausschließlich
`SandboxedProcessLookupTests::test_an_old_watcher_does_not_report_for_a_new_launch`.

```
$ python3 -m py_compile anvil/core/debug_log.py anvil/core/game_process.py \
    anvil/core/diagnostics.py anvil/main.py anvil/mainwindow.py \
    anvil/widgets/game_panel.py tests/test_predeploy_launch.py \
    tests/test_game_ghostreconbreakpoint.py
PY_COMPILE OK
```
Alle sieben Locale-Dateien parsen fehlerfrei.
Linter (`ruff`, `flake8`, `pycodestyle`) sind in diesem Baum nicht installiert —
L1 wurde per `cat -A` von Hand geprüft.

Übersetzungen: `dialog.unlock_purge_title`, `dialog.unlock_purge_text`,
`dialog.start_while_running_text`, `error.game_already_running` sind in **allen sieben**
Locales vorhanden und übersetzt (de, en, es, fr, it, pt, ru) — einzeln ausgelesen.

---

## 7. Architektur-Pflichtprüfung
1. Mod-Dateien nur per Symlink, nie direkt kopiert — Deployer unberührt ✅
2. Ordnerstruktur in `.mods/` unverändert ✅
3. Frameworks nicht in `.mods/` oder modlist.txt ✅
4. Rename/Delete aktualisiert `active_mods.json` in allen Profilen — unberührt ✅
5. Nur globale API, keine per-Profil-modlist.txt ✅
6. Referenz-Implementierung — `/home/mob/Projekte/mo2-referenz/` existiert auf diesem
   System nicht (`ls` schlägt fehl). Die Änderung betrifft ausschließlich
   Prozessüberwachung, Sandbox-Zugriff und Logging, nicht Mod-Verwaltung, Installation,
   modlist.txt-Reihenfolge oder Deploy-Logik.
7. Architektur-Doku `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md`, Abschnitt
   Deploy-Mechanismus ✅ — Purge/Deploy selbst ist unverändert, geändert wurde nur,
   **wann** gepurgt wird.

---

## Ergebnis

**NEEDS FIXES**

Die vier nachzuprüfenden Punkte aus Runde 2:
1. Direktstart-Rückbau ✅ (Startpfad exakt wie HEAD; die zwei Deltas danach sind gewollt)
2. `clear_watch_target()` ⚠️ (drei Aufrufer, einer davon in `game_panel.py` und vor dem Purge)
3. `_SCAN_TIMEOUT`/`_SCAN_FAILED` ✅ in der echten Sandbox belegt, ps-Fallback greift bei fehlendem `python3`
4. `_confirm_start_while_running()` ✅ verdrahtet, deckt Start-Button, Verknüpfung, REDmod, GRB, Steam, Proton, Direktstart; nicht Custom-/Proton-Tools

Vor dem Commit zu beheben: **H1**, **H2**, **H3**.
Danach **M1**–**M5**. Die LOW-Punkte können nachgezogen werden;
L1, L2, L6 und L8 stehen seit Runde 2 offen.
