# QA Nachprüfung — Regression & Auslieferung (Prozesssuche/Watcher)
Datum: 2026-08-06
Umfang: nicht committete Änderungen (`git status`, `git diff HEAD`), Stand nach den Fixes der Vorrunde

---

## 1. Verifikation der behobenen Punkte aus der Vorrunde

### 1.1 [CRITICAL, Vorrunde] Untrackte Module — BEHOBEN ✅
`git status --porcelain`:
```
A  anvil/core/debug_log.py
A  anvil/core/game_process.py
```
`git ls-files anvil/core/debug_log.py anvil/core/game_process.py` gibt beide Pfade zurück.
Beide Module sind im Index. Der Fix greift.

### 1.2 Flatpak-Manifest `net.anvil_organizer.AnvilOrganizer.yml` — TEILWEISE ✅/❌
Hinzugefügt wurde:
```yaml
  # Host access (launch Steam, find the running game process)
  - --talk-name=org.freedesktop.Flatpak
```
**Reicht das für die Prozesssuche?** Ja, technisch. `flatpak-spawn --host` läuft über das
Development-Portal auf `org.freedesktop.Flatpak`; ohne diesen talk-name schlägt jeder
Host-Aufruf fehl. Beleg aus der laufenden Installation
(`flatpak info --show-permissions com.github.Marc1326.AnvilOrganizer`):
```
[Session Bus Policy]
org.freedesktop.Flatpak=talk
```
Dort funktionieren `host_which`/`host_popen` bereits produktiv — dieselbe Mechanik.

**Aber:** siehe Befund H2. Das Manifest hat weitere, gravierendere Lücken, und es baut
gar nicht den geänderten Code.

### 1.3 Direktstart startet jetzt einen Watcher — VERDRAHTET ✅, Binärname RISKANT ❌
Kette verifiziert:
- `game_panel.py:2013` `start_requested.emit(...)`
- `mainwindow.py:433` `start_requested.connect(self._on_start_game)`
- `mainwindow.py:2637-2639`
  ```python
  plugin = getattr(self._game_panel, "_current_plugin", None)
  watched = getattr(plugin, "GameBinary", "") or binary_path
  self._game_panel.notify_game_started(pid, watched, proc)
  ```
- `game_panel.py:2015-2023` `notify_game_started()` → `_start_process_watcher(Path(binary).name.lower(), proc=proc)`
- `mainwindow.py:435` `game_started.connect(self._on_game_started)` → `_lock_ui()` läuft synchron vor dem Watcher-Start.

`_current_plugin` existiert (game_panel.py:533 im `__init__`), Fallback auf `binary_path`
bei fehlendem/leerem `GameBinary` ist korrekt.
Zum Binärnamen selbst: Befund H1.

---

## 2. Regression außerhalb Flatpak — KEINE (empirisch belegt) ✅

Direkter Vergleich `git show HEAD:anvil/widgets/game_panel.py` (`find_game_pid`) gegen
`anvil/core/game_process.py` (`scan_proc_for_game`), beide Implementierungen im selben
Prozess gegen dieselben laufenden Prozesse ausgeführt:

```
  app_id=None binary=None:                 alt=None    neu=None     GLEICH
  app_id=None binary='':                   alt=None    neu=None     GLEICH
  app_id=''   binary=None:                 alt=None    neu=None     GLEICH
  app_id=''   binary='':                   alt=None    neu=None     GLEICH
  app_id=None binary='testspiel88.exe':    alt=1391875 neu=1391875  GLEICH
  app_id=None binary='Testspiel88.exe':    alt=None    neu=1391875  ABWEICHUNG
  app_id='999999' binary=None:             alt=None    neu=None     GLEICH
  app_id='999999' binary='testspiel88.exe':alt=1391875 neu=1391875  GLEICH
  SteamAppId-Treffer über /proc/<pid>/environ: alt=1391884 neu=1391884  GLEICH
```

Bewertung der Unterschiede:
- **Reihenfolge** (SteamAppId vor cmdline), **Rückgabewert** (`int(pid)`/`None`) und
  **Fehlerbehandlung** (inneres + äußeres `except OSError: pass`) sind identisch.
  `Path(...).read_bytes()` → `open(..., "rb").read()` ist verhaltensgleich
  (PermissionError ist OSError-Subklasse und wird gefangen).
- **Groß-/Kleinschreibung:** neu wird der Suchbegriff zusätzlich `.lower()`-normalisiert.
  Praktisch folgenlos, weil alle drei Aufrufer den Namen bereits klein übergeben:
  `game_panel.py:2583`, `:2676`, `:2023` benutzen jeweils `Path(...).name.lower()`.
- **Eigener PID wird übersprungen** (neu). Reine Verbesserung; greift nur, wenn Anvils
  eigene cmdline den Suchbegriff enthält.
- **Nicht-Flatpak-Pfad:** `find_game_process()` gibt hier immer `reliable=True` zurück
  (`if not is_flatpak(): return scan_proc_for_game(...), True`), damit ist
  `is_game_running()` semantisch identisch zu vorher (`pid is not None`).

Verhaltensänderungen ohne Regressionscharakter, aber erwähnenswert: siehe L4.

## 3. `find_game_pid()` — restlos entfernt ✅
`grep -rn "find_game_pid" .` über das gesamte Repo (alle Dateitypen, inkl.
`anvil/plugins/`, `tests/`, `packaging/`, `.github/`) liefert genau einen Treffer, und
zwar eine Prosa-Erwähnung im Review-Dokument `docs/anvil-review-bugs.md:166`.
Kein Aufruf mehr im Code.

## 4. Signal `game_stopped = Signal(bool)` — alle Stellen korrekt ✅
emit-Stellen (alle mit genau einem bool-Argument):
- `game_panel.py:2838` `self.game_stopped.emit(blind_since is None)`
- `game_panel.py:2857` `self.game_stopped.emit(False)`
- `game_panel.py:2863` `self.game_stopped.emit(True)`

connect-Stelle: `mainwindow.py:436` `self._game_panel.game_stopped.connect(self._unlock_ui)`
mit `def _unlock_ui(self, stopped: bool = True)`.

Cross-Thread-Verhalten real geprüft (Signal(bool) aus zwei Python-Threads,
Empfänger im GUI-Thread, offscreen):
```
empfangen: [(False, 'MainThread'), (True, 'MainThread')]
```
Der Wert kommt korrekt an, der Slot läuft im GUI-Thread (automatische Queued Connection).
Kein weiterer Verbraucher des Signals im Repo (`grep`).

## 5. Paketierung — beide Module in allen Build-Pfaden ✅
- **pyproject.toml:** `[tool.setuptools.packages.find] include = ["anvil*"]`.
  `find_packages(include=["anvil*"])` liefert `anvil.core` (geprüft, 10 Pakete).
  Damit landen alle `.py` aus `anvil/core/` im Wheel — keine Datei-Whitelist im Weg
  (`package-data` betrifft nur Nicht-Python-Dateien).
- **AUR** (`packaging/aur/PKGBUILD`, `packaging/aur-git/PKGBUILD`): `python -m build --wheel` → abgedeckt.
- **deb** (`packaging/deb/debian/rules`): `dh --buildsystem=pybuild` → abgedeckt.
- **rpm** (`packaging/rpm/anvil-organizer.spec`): `pip3 install ... .`, `%files` nimmt
  `%{python3_sitelib}/anvil/` komplett → abgedeckt.
- **snap** (`packaging/snap/snapcraft.yaml`): `plugin: python`, `source: .` → abgedeckt.
- **flatpak** (beide Manifeste): `pip3 install --no-build-isolation --no-deps --prefix=/app .` → abgedeckt.
- **AppImage** (`anvil-organizer.spec` + `build-appimage.sh` + `.github/workflows/appimage.yml`):
  keine Anpassung nötig. `anvil.core.game_process` wird auf Modulebene importiert
  (`game_panel.py:20`), `anvil.core.debug_log` funktionslokal in `main()`.
  Bytecode-basierter Import-Scan (stdlib `modulefinder`, gleiche Technik wie PyInstallers
  modulegraph) ab `main.py`:
  ```
  anvil.core.debug_log gefunden: True
  anvil.core.game_process gefunden: True
  anvil.core.activity_log gefunden: True
  ```
  (`activity_log` ist der Präzedenzfall: ebenfalls funktionslokal importiert und im
  ausgelieferten AppImage vorhanden.)
- `.github/workflows/flatpak.yml` baut `com.github.Marc1326.AnvilOrganizer.yml` — dieses
  Manifest hatte `--talk-name=org.freedesktop.Flatpak` bereits vorher.

## 6. Tests / Kompilierung ✅
```
$ python3 -m pytest tests/ -q --ignore=tests/test_base_migration_dialog.py
297 passed, 1 skipped in 1.45s
```
```
$ python3 -m py_compile anvil/core/debug_log.py anvil/core/game_process.py \
    anvil/core/diagnostics.py anvil/main.py anvil/mainwindow.py \
    anvil/widgets/game_panel.py tests/test_predeploy_launch.py
PY_COMPILE OK
```
Kein Fehlschlag.

## 7. Übersetzungen ✅
Neue Keys `dialog.unlock_purge_title`, `dialog.unlock_purge_text`,
`error.game_already_running` sind in **allen sieben** Locale-Dateien vorhanden
(de, en, es, fr, it, pt, ru), alle JSON-Dateien parsen fehlerfrei.

## 8. Startpfade eines Spiels — Durchgang
| Pfad | Watcher | app_id | Signal | Aufräumen |
|---|---|---|---|---|
| `_launch_via_steam` (2545) | ja, `_start_process_watcher(name, app_id=steam_id)` | ja | ok | ok |
| `_launch_via_proton` (2630) | ja, `_start_process_watcher(GameBinary, proc, app_id=None)` | nein (bewusst) | ok | ok |
| `_on_start_game` Direktstart (mainwindow 2612) | **neu** ja, über `notify_game_started` | nein (korrekt: GOG/Epic) | ok | siehe H1, M2 |
| REDmod (`_run_redmod_deploy_then_launch`) | ja — alle Zweige (2130, 2253, 2273) münden in `_do_launch` | erbt vom Zielpfad | ok | ok |
| Custom Tools (`_on_custom_tool_start`) | kein Watcher/Lock (dokumentiert gewollt), aber `_predeploy_for_launch` schützt jetzt vor Purge unter laufendem Spiel | – | – | ok |

---

## Findings

### [HIGH] H1 — Direktstart überwacht den Launcher statt des Spiels
- Datei: `anvil/mainwindow.py:2637-2639`, `anvil/widgets/game_panel.py:2015-2023`
- Problem: Als Watch-Ziel wird `plugin.GameBinary` gesetzt. Für mindestens ein
  ausgeliefertes Plugin ist das nachweislich ein Launcher-Wrapper, nicht das Spiel:
  `anvil/plugins/games/game_windrose.py:34`
  ```python
  GameBinary = "Windrose.exe"  # Launcher im Spiel-Root
  ...
  # Echtes Shipping-Binary (Windrose.exe ist nur ein Launcher-Wrapper)
  _SHIPPING_BINARY = "R5/Binaries/Win64/Windrose-Win64-Shipping.exe"
  ```
  Der Substring-Vergleich `"windrose.exe" in cmdline.lower()` trifft
  `Windrose-Win64-Shipping.exe` **nicht** (Bindestrich). Folge im Direktstart-Pfad
  (Store ≠ steam): Watcher sieht den Launcher, der Launcher beendet sich nach Sekunden,
  der Watcher meldet `game_stopped(True)` → `_unlock_ui(True)` → `_purge_after_game()`
  zieht die Mods unter dem laufenden Spiel weg.
- Vorher gab es im Direktstart gar keinen Watcher, dieser automatische Purge ist also
  **neu eingeführt**. Im Proton-Pfad (`:2676`) besteht dieselbe Annahme bereits (Bestand),
  wird dort aber durch den mitgegebenen `proc` teilweise abgefedert.
- Fix: mehrere Kandidaten überwachen statt genau einem — zusätzlich den tatsächlich
  gestarteten `binary_path` und, falls das Plugin es anbietet, `_SHIPPING_BINARY`.
  Alternativ `_start_process_watcher()` eine Namensliste übergeben und in
  `scan_proc_for_game()` gegen alle Namen prüfen.

### [HIGH] H2 — `net.anvil_organizer`-Manifest ist mit dem talk-name noch nicht auslieferbar
- Datei: `packaging/flatpak/net.anvil_organizer.AnvilOrganizer.yml:7-28, 78-82`
- Probleme (alle durch Lesen des Manifests belegt):
  1. `--filesystem=~/.anvil:create` — der reale Basisordner heißt
     `~/.anvil-organizer` (`anvil/core/base_dir.py:54`:
     `Path.home() / ".anvil-organizer"`, verifiziert: `/home/mob/.anvil-organizer/logs`
     existiert). Anvils Datenverzeichnis wäre in dieser Variante nicht beschreibbar —
     auch das neue `logs/debug.log` nicht.
  2. `--filesystem=/mnt:ro`, `/media:ro`, `/run/media:ro` und `~/.steam:ro` sind
     **read-only**. Deploy legt Symlinks im Spielordner an; auf Zweitplatten
     (`/mnt/...`) oder unter `~/.steam` ist das damit unmöglich.
  3. Kein `--filesystem=home` → GOG/Epic-Spielordner außerhalb der Steam-Pfade sind
     unerreichbar. Genau die Stores, für die H1/Punkt 3 den Watcher nachrüstet.
  4. Fehlt `--talk-name=org.freedesktop.portal.Desktop` (NXM-Handler) sowie
     `org.freedesktop.secrets` / `org.kde.kwalletd5` / `org.kde.kwalletd6`
     (Nexus-API-Key). Alle vier sind im Schwestermanifest
     `com.github.Marc1326.AnvilOrganizer.yml:25-31` vorhanden.
  5. `sources: type: git, tag: v1.2.2, commit: 3dd4eb8...` — das Manifest baut einen
     festgenagelten Stand, in dem `anvil/core/game_process.py` gar nicht existiert.
     Der neue talk-name wirkt sich damit auf einen Build aus, der die Prozesssuche
     nicht enthält.
- Fix: entweder das Manifest auf den Stand des Schwestermanifests bringen
  (`--filesystem=home`, `/mnt`, `/media`, `/run/media` schreibbar, korrekter
  Basisordner-Pfad, portal.Desktop + Keyring-Namen, Source/Tag aktualisieren) oder
  ausdrücklich als „nicht gepflegt" markieren.
- Randnotiz: Marcs installierte App ist `com.github.Marc1326.AnvilOrganizer`
  (`flatpak list`), das net-Manifest ist nicht installiert — der Fehler fällt im
  Alltag daher nicht auf, träfe aber jeden Flathub-Nutzer.

### [MEDIUM] M1 — Doppelte, widersprüchliche Fehlermeldung beim zweiten Spielstart
- Datei: `anvil/mainwindow.py:2571-2580` zusammen mit `:2614-2620`,
  ebenso `anvil/widgets/game_panel.py:1971-1978`
- Problem: `_predeploy_for_launch()` zeigt bei laufendem Spiel korrekt
  `tr("error.game_already_running")` und gibt `False` zurück. Der Aufrufer
  `_on_start_game()` wertet `False` unverändert als Deploy-Fehler und zeigt direkt
  danach `tr("error.deploy_failed_message")`. Der Nutzer bekommt zwei Dialoge, der
  zweite nennt eine falsche Ursache. Gleiches im Steam-Pfad über `_predeploy_hook`.
- Fix: `_predeploy_for_launch()` unterscheidbar machen (z. B. eigenes Ergebnis
  „abgelehnt, Meldung bereits gezeigt") oder in den beiden Aufrufern die
  Deploy-Fehlermeldung überspringen.

### [MEDIUM] M2 — `_clear_watch_target()` vor `proc.wait()` öffnet ein Purge-Fenster
- Datei: `anvil/widgets/game_panel.py:2828-2840`
  ```python
  else:
      _dlog("[WATCHER] game process never appeared")
      self._clear_watch_target()
  if proc is not None:
      proc.wait()
  self.game_stopped.emit(blind_since is None)
  ```
- Problem: Zwischen dem Leeren des Watch-Ziels und dem `emit` blockiert `proc.wait()`
  potenziell beliebig lange. In diesem Fenster liefert `game_state()` sofort
  `stopped` (kein Watch-Ziel) und `is_game_running()` `False`. Damit dürfen alle
  frisch eingebauten Schutzabfragen — `_do_redeploy` (`mainwindow.py:2309`),
  Instanzwechsel (`:1629`), Profilwechsel (`:4702`), `closeEvent` (`:7091`) —
  aufräumen, obwohl der gestartete Prozess noch lebt.
- Fix: `_clear_watch_target()` erst nach `proc.wait()` aufrufen.

### [MEDIUM] M3 — `start_debug_log()` läuft zu spät für die typischen Startfehler
- Datei: `anvil/main.py:150-153`
- Problem: Der Aufruf steht nach `_ensure_base_directory()`, dem Style-/Icon-Setup und
  dem Single-Instance-Check. Ein Traceback beim Laden von Theme, Basisordner oder
  Plugins entsteht davor und landet weiterhin nicht in `logs/debug.log` — also genau
  der Fall, für den das Modul laut Docstring gedacht ist („Start über Menüeintrag,
  .desktop oder Flatpak"). Die Reihenfolge ist begründet (`anvil_base_paths()` ist
  vorher nicht gültig, der Forwarder-Prozess würde rotieren), aber der Nutzen ist
  dadurch eingeschränkt.
- Fix: früh in einen Speicherpuffer schreiben und ihn beim Aktivieren der Datei
  nachziehen, oder zumindest den `sys.excepthook` (`main.py:119-124`) zusätzlich in
  die Datei schreiben lassen.
- Funktion selbst verifiziert: Aufruf schreibt Kopfzeile, stdout und stderr in
  `/home/mob/.anvil-organizer/logs/debug.log`; `isatty()` und `fileno()` verhalten
  sich korrekt; `Path('debug.log').with_suffix('.log.1')` ergibt wie beabsichtigt
  `debug.log.1`; `diagnostics.log_sources()` listet die Datei jetzt auf.

### [MEDIUM] M4 — `game_state()` kann den GUI-Thread bis zu 6 s blockieren
- Datei: `anvil/widgets/game_panel.py:2769-2789`, `anvil/core/game_process.py:89-131`
- Problem: `game_state()` fällt bei fehlendem/veraltetem Zwischenspeicher auf
  `lookup_game_pid()` zurück. In Flatpak sind das nacheinander bis zu
  `_HOST_SCAN_TIMEOUT` (3 s) für den Python-Scan **plus** 3 s für den ps-Fallback.
  Aufrufer im GUI-Thread: `_predeploy_for_launch` (:2574), Storage-Migration
  (:1016, :1078), `_do_redeploy` (:2309), Profilwechsel (:4702), `closeEvent` (:7091).
  Praktisch tritt das nur ein, solange ein Watch-Ziel gesetzt und der Lookup blind ist
  — dann aber bei jeder dieser Aktionen erneut.
- Fix: in diesen Pfaden ausschließlich den zwischengespeicherten Zustand des Watchers
  lesen, oder den Host-Scan mit einem harten Gesamtbudget versehen.

### [LOW] L1 — PEP8: fehlende Leerzeile
- Datei: `anvil/widgets/game_panel.py:37`
- Zwischen `_state_of()` und `_dlog()` steht nur eine Leerzeile (E302).

### [LOW] L2 — Sichtbarer String ohne `tr()`
- Datei: `anvil/core/diagnostics.py:253`
- `{"label": "debug.log (Projekt)", ...}` — fest deutscher Text, erscheint im
  Diagnose-Tab auch in den sechs anderen Sprachen. Verifiziert über
  `log_sources()`-Aufruf.

### [LOW] L3 — Irreführende Logzeile beim Entsperren ohne Deployment
- Datei: `anvil/mainwindow.py:2702-2704`
- Ohne Deployment wird `_unlock_ui(False)` gerufen, das loggt
  „game state unknown — keeping the deployment", obwohl weder der Zustand unbekannt
  ist noch etwas liegen bleibt.

### [LOW] L4 — Bewusste Verhaltensänderungen außerhalb Flatpak
- `game_state()` beantwortet `running`/`unknown` bis zu `_GAME_STATE_TTL` = 15 s aus
  dem Zwischenspeicher (`game_panel.py:30, 2777-2786`). Vorher war jede Abfrage live.
  `stopped` wird bewusst nie zwischengespeichert, damit greift der Schutz.
- Poll-Intervall im laufenden Spiel 2 s → `_GAME_POLL_INTERVAL` = 5 s
  (`game_panel.py:2740`): das Deployment bleibt nach Spielende bis zu 3 s länger liegen.
- `closeEvent` purget nicht mehr, solange ein Spiel laufen könnte
  (`mainwindow.py:7089-7095`). Aufgeräumt wird dann beim nächsten Start über
  `_do_redeploy`/`_predeploy_for_launch` — Pfad geprüft und vorhanden.
Alle drei sind gewollt und im Code begründet; hier nur als Änderungsprotokoll notiert.

### [LOW] L5 — Kein Stopp-Mechanismus für alte Watcher-Threads (Bestand)
- Datei: `anvil/widgets/game_panel.py:2800-2865`
- Bei mehreren Starts hintereinander laufen ältere Watcher weiter und lesen dasselbe
  `_watch_binary`, das der neue Start bereits überschrieben hat; jeder von ihnen kann
  `game_stopped` senden. Bestand aus HEAD, durch die neuen Startpfade aber häufiger
  erreichbar. `_predeploy_for_launch` fängt den Normalfall (`running`) ab.

### [LOW] L6 — Arbeitsverzeichnis vor dem Commit aufräumen
- `001Bericht/` ist untracked und enthält Fundus-Material
  (`DESIGN-BERICHT.md`, `Fundus Design Varianten.zip`, `icons/`) — gehört nicht ins
  Anvil-Repo.
- `docs/anvil-offene-punkte-04-08.md`, `docs/anvil-review-architektur.md`,
  `docs/anvil-review-bugs.md`, `docs/anvil-review-regression.md` und diese Datei sind
  untracked; `docs/` ist **nicht** in `.gitignore` (nur `docs/workflow/`), ein
  `git add -A` würde sie mit einchecken.
- `debug.log` am Projektroot ist durch `.gitignore` abgedeckt — in Ordnung.

---

## Architektur-Pflichtprüfung
1. Mod-Dateien nur per Symlink, nie direkt kopiert — unberührt, Deployer nicht angefasst ✅
2. Ordnerstruktur in `.mods/` unverändert — unberührt ✅
3. Frameworks nicht in `.mods/` oder modlist.txt — unberührt ✅
4. Rename/Delete aktualisiert `active_mods.json` in allen Profilen — unberührt ✅
5. Nur globale API, keine per-Profil-modlist.txt — unberührt ✅
6. Referenz-Implementierung konsultiert — **nicht möglich**: `/home/mob/Projekte/mo2-referenz/`
   existiert auf diesem System nicht (`ls` schlägt fehl). Die Änderung betrifft
   ausschließlich Prozessüberwachung und Sandbox-Zugriff, nicht Mod-Verwaltung,
   Installation, modlist.txt oder Deploy-Reihenfolge.
7. Architektur-Doku gelesen — `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md`,
   Abschnitt 5 „Deploy-Mechanismus" ✅. Die Schutzregel („Deploy-Mechanismus nicht ohne
   Zustimmung ändern") ist eingehalten: Purge-/Deploy-Logik selbst ist unverändert,
   geändert wurde nur, **wann** gepurgt wird.

---

## Ergebnis

**NEEDS FIXES**

Die drei nachzuprüfenden Punkte der Vorrunde sind erledigt (1 vollständig, 2 technisch
korrekt aber Manifest weiterhin nicht auslieferbar, 3 verdrahtet aber mit Namensrisiko).
Regression außerhalb Flatpak: keine, empirisch belegt. Tests, Kompilierung,
Übersetzungen und Paketierung sind sauber.

Offen vor dem Commit: **H1** und **H2**, danach **M1**, **M2**.
M3/M4 und die LOW-Punkte können nachgezogen werden.
