# QA Report — Runde 4: Regression & Auslieferung

Datum: 2026-08-06
Prüfer: QA (Runde 4)
Grundlage: `git status`, `git diff HEAD`, isolierter Snapshot des Arbeitsbaums

---

## 0. WARNUNG — der Arbeitsbaum hat sich während der Prüfung dreimal geändert

Das ist kein Nebensatz, sondern beeinflusst die Gültigkeit jeder Aussage unten.

| Zeit | Beobachtung |
|---|---|
| 21:25 | Prüfbeginn, erster `git diff HEAD` gelesen |
| 21:37–21:39 | `game_process.py`, `game_panel.py`, `mainwindow.py`, `test_predeploy_launch.py` **neu geschrieben** (u. a. `TOOL_ENV_MARKER`, `_FORCED_LAUNCH_TTL`, `dialog.start_while_unknown_text`) |
| 21:41:09 | **Eigener Snapshot** angelegt — alle Messungen unten laufen gegen diesen Stand |
| 21:53–21:55 | erneut geändert (Nullbyte-Grenze bei `SteamAppId`, `_launch_via_proton` mit AppId, `_refuse_while_game_runs`, zwei neue Tests) |

Belegte MD5 des Snapshots vs. Endstand 22:03:

```
21:41  faa4e6bd…  anvil/core/game_process.py     22:03  5b7b320c…
21:41  5da13d86…  anvil/widgets/game_panel.py    22:03  f6a0e4e4…
21:41  4c967419…  anvil/mainwindow.py            22:03  ba875776…
```

**Konsequenz:** Mutationstest, 30 Suite-Läufe und Paketierungsprüfung beziehen sich auf
den Stand 21:41:09. Die Änderungen von 21:53–21:55 sind gelesen und am Ende bewertet,
aber nicht mehr durchgemessen. Eine Freigabe kann erst auf einem eingefrorenen Baum
erteilt werden.

Zusätzlich: ein lokaler Flatpak-Build lief parallel und hat **eingecheckte Dateien
verändert** (`packaging/flatpak/repo/**`, `packaging/flatpak/build/**` sind in git
getrackt). Das verschmutzt jeden `git status` und gehört in `.gitignore` — siehe L-4.

---

## 1. Verifikation der Runde-3-Fixes

### 1.1 `_predeploy_for_launch` prüft `self._game_running` + `take_forced_launch()` — ✅ vorhanden, ❌ nicht abgesichert

`anvil/mainwindow.py:2614-2624`:

```python
self._redeploy_timer.stop()
forced = self._game_panel.take_forced_launch()
running = self._game_running or self._game_panel.game_state() == GAME_RUNNING
if running and not forced:
    ...
    return None
```

Der Code ist da. **Aber:** die Mutation S3 (`self._game_running or` entfernt, also exakt
der Rückbau des Runde-3-Fixes) wird von der Suite **nicht bemerkt** — 307 passed.
Siehe Abschnitt 5. Der Fix ist implementiert, aber ungetestet.

`launch_instance_shortcut` (`mainwindow.py:7001`) ruft `start_selected()` →
`_on_start_clicked()` → `confirm_start_while_running()`. Der Umgehungsweg aus Runde 3
ist damit geschlossen. ✅

### 1.2 Suchbegriff im `_crash_recovery_purge` = SteamAppId + GameBinary — ✅ mit Einschränkung

`mainwindow.py:1586-1596` nutzt `plugin_watch_target(plugin)`. Belegt für alle
41 Plugins (ausgeführt):

```
baldursgate3 ('1086940', 'bg3.exe')   cyberpunk2077 ('1091500', 'cyberpunk2077.exe')
SkyrimSE ('489830', 'skyrimse.exe')   StardewValley ('413150', 'stardew valley')
```

Kein Plugin liefert `(None, None)`. Der Spielpfad wird nicht mehr verwendet. ✅

Einschränkungen: siehe H-2 (Purge fällt komplett aus, wenn kein Plugin gefunden wird)
und M-3 (`StardewValley` sucht nach `stardew valley` in jeder Kommandozeile).

### 1.3 Flaky-Test / 30 Läufe der Gesamtsuite — ✅ stabil, ⚠️ aber die Suite stürzt reproduzierbar ab

30 Läufe der **gesamten** Suite auf dem Snapshot, jeweils mit `QT_QPA_PLATFORM=offscreen`:

```
n=30  min=10485 ms  max=10875 ms  median=10530 ms  mean=10542 ms
stdev=68 ms  Spanne=390 ms (3,70 %)   Ergebnis: 30/30 grün (307 passed, 1 skipped)
```

Streuung also sehr gering; der in Runde 3 reparierte Test ist in 30/30 Läufen grün.

**Aber** — siehe C-1: sobald eine Quelldatei angefasst wurde, segfaultet der
nächste Suite-Lauf reproduzierbar (5/5 bzw. 9/9). Die 30 sauberen Läufe kamen nur
zustande, weil dazwischen nichts geändert wurde.

Nebenbefund: die Suite ist von **1,4 s (HEAD) auf 10,4 s** gewachsen (7,4×), weil die
neuen Tests echte Prozesse starten und `time.sleep()` benutzen. Siehe M-6.

### 1.4 `tests/conftest.py` — ✅ funktioniert genau wie beschrieben

Empirisch geprüft (vier Läufe, jeweils Ausgabe von `os.environ`):

| Umgebung | `QT_QPA_PLATFORM` im Test |
|---|---|
| keine Variablen gesetzt | `offscreen` (erzwungen) ✅ |
| `ANVIL_TEST_SHOW_WINDOWS=1`, extern `offscreen` | `offscreen` (nicht angefasst) ✅ |
| `ANVIL_TEST_SHOW_WINDOWS=1`, extern anderer Wert | unverändert → **Ausstieg funktioniert** ✅ |
| `ANVIL_TEST_SHOW_WINDOWS=0` | `offscreen` (erzwungen) ✅ |

Die Datei enthält **keine** Fixtures und **keine** Hooks, nur den einen `os.environ`-Schreibzugriff.
Kein Test im Projekt liest `QT_QPA_PLATFORM` aus oder hängt an einer Plattform.
Es gibt keine zweite `conftest.py` und keine pytest-Konfiguration
(`pytest.ini`/`setup.cfg`/`[tool.pytest…]` fehlen alle) — die Datei ist die einzige Stelle.
Andere Tests werden also ausschließlich in der Sichtbarkeit beeinflusst. ✅

### 1.5 Tool-Starts fragen nach statt abzulehnen — ✅

* Proton-Werkzeuge: `mainwindow.py:1318` `if not self._game_panel.confirm_start_while_running(): return`
* Eigene Werkzeuge: `mainwindow.py:2686` dito
* Spielstart: `game_panel.py:1973` dito

`confirm_start_while_running()` lehnt nie hart ab, sondern fragt — und fragt seit 21:37
auch bei `unknown`. ✅

---

## 2. Regression HEAD vs. aktueller Stand

Verglichen wurde `git show HEAD:anvil/widgets/game_panel.py` bzw. `…:anvil/mainwindow.py`
Zeile für Zeile gegen den Snapshot.

### Verhaltensänderungen, die durch den Bugfix gedeckt sind

| Änderung | Bewertung |
|---|---|
| `find_game_pid()` → `lookup_game_pid()`/`game_state()`, `(pid, reliable)` | gedeckt, Kern des Fixes |
| `is_game_running()`: `unknown` zählt als „läuft" | gedeckt, dokumentiert |
| `game_stopped = Signal()` → `Signal(bool)` | gedeckt; einziger Empfänger `_unlock_ui(stopped=True)`, Signatur passt, keine weiteren `connect`/`emit` im Repo (geprüft) |
| Purge-Sperren in `closeEvent`, `_do_redeploy`, `_teardown_current_instance`, Profilwechsel | gedeckt |
| `_on_unlock_clicked()` mit Rückfrage statt stillem `_unlock_ui()` | gedeckt |
| `run_env = env` → `run_env = env.copy()` (REDmod, 2×) | echte Verbesserung, kein Nebeneffekt |
| `set_game()` verwirft `_game_state` | gedeckt, korrekt |

### Verhaltensänderungen, die **nicht** durch den Bugfix begründet sind — Befunde

1. **`is_game_running()` gilt jetzt auch für Spiele, die Anvil nie gestartet hat.**
   `_search_terms()` fällt auf `plugin_watch_target(self._current_plugin)` zurück. Bei
   HEAD war `find_game_pid()` ohne Watch-Ziel immer `None`. Das ist beabsichtigt
   (Absturz-Wiederherstellung), verändert aber `closeEvent`, `_do_redeploy`,
   Instanz- und Profilwechsel: läuft das Spiel extern, wird nicht mehr aufgeräumt.
   → bewusst, dokumentiert im Docstring. Kein Befund, aber erwähnenswert.

2. **`_GAME_POLL_INTERVAL` 2 s → 5 s.** Nach Spielende dauert es außerhalb von Flatpak
   bis zu 5 statt 2 Sekunden, bis die UI entsperrt und aufgeräumt wird. Begründet mit
   den Host-Aufrufen im Flatpak — trifft aber auch alle Nicht-Flatpak-Nutzer. → L-1.

3. **Defensives `getattr` in `_unlock_ui` entfernt.** HEAD:
   `getattr(self._game_panel, "is_game_running", lambda: False)()`, jetzt direkter
   Aufruf. In Produktion egal (immer echtes `GamePanel`), aber die Absicherung ist weg. → L-2.

4. **`_launch_via_proton` übergibt seit 21:53 wieder die SteamAppId** — die Vorgänger-Zeile
   trug den ausdrücklichen Kommentar *„app_id=None: SteamAppId-Suche würde wine/proton
   Prozesse finden die auch zu früh sterben"*. Das ist die Umkehr einer dokumentierten
   Entscheidung. → M-5.

---

## 3. Startpfade und `bool | None`

Alle Pfade nachverfolgt (`grep` + Lesen):

| Startpfad | `confirm_start_while_running()` |
|---|---|
| `_on_start_clicked` (Start-Knopf) | ✅ `game_panel.py:1973`, **vor** allen Deploy-Zweigen |
| `start_selected()` / `launch_instance_shortcut` | ✅ über `_on_start_clicked` |
| Eigenes Executable aus dem Menü | ✅ über `custom_start_requested` → `_on_custom_tool_start:2686` |
| Proton-Werkzeuge (Toolbar) | ✅ `_run_proton_tool:1318` |
| REDmod | ✅ Rückfrage steht vor dem REDmod-Zweig |
| GRB / Forge | ✅ Rückfrage steht vor dem Forge-Zweig |
| `_launch_via_steam` / `_launch_via_proton` | ✅ nur über `_do_launch`, das nur aus `_on_start_clicked` bzw. `_run_redmod_deploy_then_launch` erreicht wird |
| `_on_start_game` | ✅ nur Slot von `start_requested`, das ausschließlich `_do_launch:2058` sendet |

**Kein Startpfad umgeht die Rückfrage.** ✅

`bool | None`-Behandlung — alle vier Aufrufer geprüft:

| Aufrufer | Verhalten bei `None` |
|---|---|
| `_on_start_game:2649` | `if not result:` + `if result is not None:` → kein doppelter Dialog ✅ |
| `_on_custom_tool_start:2688` | `if not …: return` → bricht ab, keine zweite Meldung ✅ |
| `_run_proton_tool:1320` | dito ✅ |
| `game_panel._on_start_clicked:2014` | `if not result:` + `if result is not None:` ✅ |

Kein Aufrufer verwechselt `None` mit Erfolg. ✅

---

## 4. `_search_terms()` und `self._current_plugin`

* `self._current_plugin = None` wird in `GamePanel.__init__` (`game_panel.py:538`)
  gesetzt, also **vor** `self._game_state` (558) und `_forced_launch` (565).
* `game_state()` wird nur aus `confirm_start_while_running`, `is_game_running` und
  MainWindow gerufen — keiner dieser Wege läuft während `__init__`.
* `plugin_watch_target(None)` liefert `(None, None)`, kein Fehler.

**Kein `AttributeError` möglich.** ✅

Randnotiz: `set_game()` setzt `_game_state = None`, aber **nicht** `_watch_binary`/
`_watch_app_id`. Nach einem Instanzwechsel bei laufendem Spiel A meldet
`is_game_running()` für Instanz B weiter „läuft". Wirkung ist konservativ
(es wird nur nicht aufgeräumt), daher kein eigener Befund.

---

## 5. Mutationstest — 18 eigene Sabotagen, 10 unentdeckt

Durchgeführt auf einer Kopie (`…/qa4-r4/mutproj`), jede Sabotage einzeln angewandt,
volle Suite, danach zurückgesetzt. Segfault-Läufe (siehe C-1) wurden erkannt und
bis zu 6× wiederholt, damit ein Absturz nicht fälschlich als „erkannt" zählt.

| # | Sabotage | Ergebnis |
|---|---|---|
| S1 | `game_state()` beantwortet auch `STOPPED` aus dem Zwischenspeicher | ❌ **nicht erkannt** |
| S2 | `take_forced_launch()` verbraucht die Zustimmung nicht | ✅ `test_forced_launch_expires` |
| S3 | `_predeploy_for_launch` ignoriert `self._game_running` (= Rückbau Fix 1) | ❌ **nicht erkannt** |
| S4 | `plugin_watch_target` liefert den vollen Pfad statt des Dateinamens | ✅ `test_state_falls_back_to_the_current_game` |
| S5 | `scan_proc_for_game` vergleicht die cmdline ohne `.lower()` | ❌ **nicht erkannt** |
| S6 | Host-Snippet bekommt die Suchbegriffe wieder über `argv` (= Rückbau Fix 2) | ✅ `test_host_scan_snippet_matches_the_local_scan` |
| S7 | `_unlock_pending`-Sperre entfernt | ❌ **nicht erkannt** |
| S8 | `closeEvent` purgt wieder bedingungslos | ❌ **nicht erkannt** |
| S9 | Rückfrage erst nach dem GRB/REDmod-Zweig | ✅ `test_declining_the_start_launches_nothing` |
| S10 | Watcher meldet nach dauerhaft blinder Suche „sicher beendet" | ❌ **nicht erkannt** |
| S11 | Werkzeug-Markierung beim `/proc`-Scan ignoriert | ✅ `test_own_tools_are_not_mistaken_for_the_game` |
| S12 | `confirm_start_while_running` merkt sich das Ja nicht | ❌ **nicht erkannt** |
| S13 | `plugin_watch_target` vertauscht AppId und Dateinamen | ✅ `test_state_falls_back_to_the_current_game` |
| S14 | `_Tee.write` meldet 0 geschriebene Zeichen | ❌ **nicht erkannt** |
| S15 | Vorab-Deploy meldet `False` statt `None` bei laufendem Spiel | ✅ `test_running_game_blocks_a_second_launch` |
| S16 | `_on_start_clicked` zeigt den Deploy-Fehler auch für `None` | ❌ **nicht erkannt** |
| S17 | `confirm_start_while_running` fragt bei `unknown` nicht mehr | ✅ `test_unknown_state_asks_before_starting` |
| S18 | `set_game` verwirft den gemerkten Zustand nicht | ❌ **nicht erkannt** |

**Erkannt: 8 von 18 (44 %). Unentdeckt: 10.**

Die drei schmerzhaftesten Lücken:

* **S3** — genau der Fix aus Runde 3 Nr. 1. Man kann ihn spurlos zurückbauen.
* **S10** — der Watcher darf nach dauerhaft fehlgeschlagener Suche `game_stopped(True)`
  melden, ohne dass ein Test anschlägt. Genau daraus entsteht der Ursprungsbug
  (Purge unter laufendem Spiel).
* **S1** — `STOPPED` aus dem Zwischenspeicher zu beantworten hebelt die einzige
  Sicherung aus, die vor einem veralteten „beendet" schützt.

Ebenfalls unschön: **S12** — der Nutzer bestätigt „trotzdem starten", die Zustimmung
wird nicht gemerkt, und `_predeploy_for_launch` lehnt danach mit
„Es läuft noch ein Spiel" ab. Eine Sackgasse für den Nutzer, von keinem Test bemerkt.

---

## 6. Paketierung

### Beide neuen Module

Wheel real gebaut (`setuptools.build_meta.build_wheel`) und Inhalt gelistet:

```
game_process : ['anvil/core/game_process.py']   ✅
debug_log    : ['anvil/core/debug_log.py']      ✅
conftest     : []                                ✅ (nicht ausgeliefert)
tests/*      : []                                ✅
locales      : 7 Dateien                         ✅
329 Dateien gesamt
```

* **pyproject / Flatpak / Snap** — alle drei installieren über
  `[tool.setuptools.packages.find] include = ["anvil*"]`; beide Module sind Teil von
  `anvil.core` und damit automatisch drin, `tests/` liegt außerhalb des Musters. ✅
* **PyInstaller (`anvil-organizer.spec`)** — beide Module werden über statische
  `from …import`-Anweisungen erreicht
  (`game_panel.py:20` Modulebene, `mainwindow.py:1573` und `main.py:152` in Funktionen —
  modulegraph folgt beidem). Kein `hiddenimports`-Eintrag nötig. `datas` enthält kein
  `tests/`. ✅
* **AppImage + .deb (`.github/workflows/appimage.yml`)** — kopieren
  `dist/anvil-organizer/*` aus dem PyInstaller-Lauf. ✅
* **`tests/conftest.py`** landet in keinem Auslieferungspfad. ✅

### Flatpak-Manifest — Änderung sitzt im falschen Manifest

`--talk-name=org.freedesktop.Flatpak` wurde in
`packaging/flatpak/net.anvil_organizer.AnvilOrganizer.yml` ergänzt.

Ausgeliefert wird aber `com.github.Marc1326.AnvilOrganizer.yml`:

```
.github/workflows/flatpak.yml:  manifest-path: packaging/flatpak/com.github.Marc1326.AnvilOrganizer.yml
build-flatpak.sh:35             MANIFEST=".../com.github.Marc1326.AnvilOrganizer.yml"
```

Dort steht `--talk-name=org.freedesktop.Flatpak` **bereits seit vorher** drin — die
Host-Suche funktioniert also im echten Paket. Die Änderung ist damit wirkungslos, aber
auch nicht schädlich. Zusätzlich: das `net.*`-Manifest baut aus
`tag: v1.2.2 / commit 3dd4eb87` — es kann den neuen Code gar nicht enthalten. → L-3.

---

## 7. `python3 -m py_compile`

Alle geänderten/neuen Dateien, ausgeführt:

```
OK anvil/core/debug_log.py       OK anvil/core/diagnostics.py
OK anvil/core/game_process.py    OK anvil/main.py
OK anvil/mainwindow.py           OK anvil/widgets/game_panel.py
OK tests/conftest.py             OK tests/test_predeploy_launch.py
OK tests/test_game_ghostreconbreakpoint.py
```

Übersetzungen: alle 5 neuen Schlüssel (`dialog.unlock_purge_title`,
`dialog.unlock_purge_text`, `dialog.start_while_running_text`,
`dialog.start_while_unknown_text`, `error.game_already_running`) in **allen 7**
Locales vorhanden (de/en/es/fr/it/pt/ru) — programmatisch geprüft. ✅

---

## Findings

### [CRITICAL] C-1 — Die Suite segfaultet nach jeder Quelltextänderung

* Datei: ausgelöst über `tests/test_predeploy_launch.py`, Absturzstelle
  `anvil/widgets/base_migration_dialog.py:89` (`BaseMigrationProgressDialog.start()`)
* Problem: Wird eine Datei unter `anvil/` angefasst und danach die volle Suite
  gestartet, endet der Lauf mit `SIGSEGV` (rc = −11) statt mit einem Ergebnis.
  Der unmittelbar folgende Lauf ist grün.

  Gemessen (jeweils `QT_QPA_PLATFORM=offscreen`, volle Suite):

  | Szenario | HEAD | mit Änderung |
  |---|---|---|
  | `__pycache__` gelöscht, 5 Läufe | 5/5 Absturz | 5/5 Absturz |
  | warmer Cache, keine Änderung, 5 Läufe | 0/5 | 0/5 |
  | `anvil/mainwindow.py` neu geschrieben, 5 Läufe | **0/5** | **5/5 Absturz** |

  Der Absturz bei kaltem Cache existiert also schon bei HEAD. Neu ist, dass er im
  normalen Arbeitsablauf *bearbeiten → testen* **jedes Mal** zuschlägt. Eingegrenzt:
  mit `--ignore tests/test_predeploy_launch.py` verschwindet er (3/3 grün), mit
  `--deselect` beider Testklassen bleibt er — es genügt also, dass das Modul
  eingesammelt wird. Mit HEADs Fassung derselben Datei im geänderten Baum: 2/3 grün.
* Auswirkung: Wer nach einem Fix `pytest` startet, sieht einen Absturz statt eines
  Ergebnisses. Damit ist die Suite als Sicherheitsnetz für genau diese Änderung
  praktisch unbrauchbar.
* Fix: Ursache in `BaseMigrationProgressDialog.start()` beheben —
  `self._thread.start()` direkt vor `self.exec()` ist ein Rennen: endet der Worker,
  bevor die Ereignisschleife läuft, feuern `finished` → `quit` → `deleteLater` ins
  Leere. Thread erst aus `showEvent`/`QTimer.singleShot(0, …)` starten und
  `_thread`/`_worker` bis zum Dialogende am Leben halten. Zusätzlich prüfen, welche
  Importe aus `test_predeploy_launch.py` (echte `QApplication` + `GamePanel` auf
  Modulebene) das Rennen scharf machen.

### [HIGH] H-1 — Zentrale Sicherungen sind ohne Test

* Datei: `anvil/mainwindow.py:2616`, `anvil/widgets/game_panel.py:2910-2940`, `:2852`
* Problem: Die Mutationen S3, S10 und S1 (Abschnitt 5) bleiben unbemerkt. Damit sind
  drei Eigenschaften ungeschützt, die den Ursprungsbug verhindern sollen:
  `self._game_running` im Vorab-Deploy, „blinde Suche meldet nie *beendet*", und
  „`STOPPED` nie aus dem Zwischenspeicher".
* Fix: Je ein Test:
  1. `_predeploy_for_launch` mit `_game_running=True` und `game_state()=="stopped"`
     → muss `None` liefern.
  2. Watcher mit `lookup_game_pid` = dauerhaft `(None, False)` und
     `_GAME_LOOKUP_GRACE = 0` → `game_stopped` muss `False` senden.
  3. `_note_game_state(None, True)` setzen, danach `lookup_game_pid` auf
     `(123, True)` umstellen → `game_state()` muss `running` liefern, nicht den
     zwischengespeicherten Wert.

### [HIGH] H-2 — Crash-Recovery räumt gar nicht mehr auf, wenn kein Plugin gefunden wird

* Datei: `anvil/mainwindow.py:1586-1597`
* Problem:

  ```python
  short_name = data.get("game_short_name", "") if data else ""
  plugin = self.plugin_loader.get_game(short_name) if short_name else None
  app_id, binary = plugin_watch_target(plugin)
  if not app_id and not binary:
      ...  # "no way to tell if the game runs — deployment kept"
      continue
  ```

  Fehlt `game_short_name` in der `.anvil.ini` (ältere oder handgepflegte Instanz) oder
  liefert `get_game()` `None` (Nutzer-Plugin entfernt oder umbenannt), wird die
  Instanz **komplett übersprungen** — weder `deployer.purge()` noch
  `remove_orphaned_links()` laufen. Bei HEAD wurde immer aufgeräumt.
  Ergebnis: die Symlinks im Spielverzeichnis bleiben dauerhaft liegen, in **jeder**
  weiteren Sitzung.
* Fix: Ohne Suchmerkmale nicht überspringen, sondern das tun, was HEAD tat — purgen —
  oder wenigstens `remove_orphaned_links()` ausführen. Alternativ den Namen aus
  `list_instances()` als Rückfall nehmen (dort liefert `game_short_name` denselben Wert).

### [MEDIUM] M-1 — `_FORCED_LAUNCH_TTL = 120 s` verfällt mitten im REDmod-Deploy

* Datei: `anvil/widgets/game_panel.py:35`, `:1945`, `anvil/mainwindow.py:2615`
* Problem: Bei einem Nicht-Steam-Spiel mit REDmod läuft die Kette
  `confirm_start_while_running()` (Zustimmung, TTL 120 s) → REDmod-Deploy (dauert bei
  vielen Mods deutlich länger) → `_do_launch` → `start_requested` → `_on_start_game`
  → `_predeploy_for_launch` → `take_forced_launch()` ist **abgelaufen** →
  „Es läuft noch ein Spiel. Beende es, bevor du neu startest." Der Nutzer hat
  zugestimmt, minutenlang gewartet und wird dann abgewiesen.
* Fix: TTL nicht an Wanduhrzeit hängen, sondern an den Startvorgang (z. B. Zähler
  wie `watch_generation`), oder die Zustimmung erst beim Verlassen von
  `_on_start_clicked` verfallen lassen.

### [MEDIUM] M-2 — Werkzeug-Markierung wirkt nur auf dem AppId-Zweig

* Datei: `anvil/core/game_process.py:41-52`, `_HOST_SCAN`, `_host_scan_via_ps`
* Problem: `if _TOOL_NEEDLE in environ: continue` steht **innerhalb** von `if needle:`.
  Wird ohne `app_id` gesucht (Nicht-Steam-Plugin, oder Watch-Ziel ohne AppId), wird
  `environ` nie gelesen und die Markierung nie beachtet — es zählt allein der
  Dateiname in der cmdline. `_host_scan_via_ps` kann `environ` grundsätzlich nicht
  lesen und ignoriert die Markierung immer; der Docstring erwähnt nur die AppId.
  Konkreter Fall: ein eigenes Werkzeug, dessen Exe die Spiel-Exe ist
  („Spiel mit F4SE starten" als eigenes Programm) — trotz Markierung ein Treffer.
* Fix: Markierung vor beide Zweige ziehen (environ immer lesen, wenn les­bar) und im
  `ps`-Rückfall im Docstring und im Log festhalten, dass Werkzeuge dort nicht
  unterscheidbar sind.

### [MEDIUM] M-3 — Der Dateiname-Rückfall trifft zu viel

* Datei: `anvil/core/game_process.py:47-50`
* Problem: `binary in cmdline.lower()` ist eine Teilstring-Suche ohne Grenzen.
  `StardewValley` sucht nach `stardew valley` — das steht in **jedem** Prozess, dessen
  Kommandozeile den Spielordner erwähnt (Dateimanager, Shell, Steam-Hilfsprozess).
  Ein Treffer bedeutet `RUNNING` und blockiert damit Purge, Instanzwechsel,
  Profilwechsel, Speicherumzug und den nächsten Start.
* Fix: Am Pfadtrenner oder am Argument-Nullbyte verankern, statt frei im String zu
  suchen (die AppId-Seite hat mit dem Nullbyte-Fix von 21:53 genau das bekommen).

### [MEDIUM] M-4 — Bei `unknown` läuft der Vorab-Purge trotzdem

* Datei: `anvil/mainwindow.py:2616`
* Problem: `is_game_running()` behandelt `unknown` als „läuft" (schützt Purges),
  `_predeploy_for_launch` aber vergleicht auf `== GAME_RUNNING` — `unknown` läuft
  also durch und purgt. Wenn die Suche dauerhaft blind ist (Flatpak ohne Host-Zugriff),
  ist genau der Pfad ungeschützt, um den es geht. Die Rückfrage federt das ab, aber
  nur, solange der Nutzer sie sieht — nach einem „Ja" purgt Anvil unter dem Spiel.
* Fix: Bewusst entscheiden und im Docstring festhalten, oder auch hier
  `is_game_running()` verwenden.

### [MEDIUM] M-5 — `_launch_via_proton` kehrt eine dokumentierte Entscheidung um

* Datei: `anvil/widgets/game_panel.py:2730-2733` (Änderung von 21:53)
* Problem: Bisher stand dort ausdrücklich
  *„app_id=None: SteamAppId-Suche würde wine/proton Prozesse finden die auch zu früh
  sterben"*. Jetzt wird die AppId doch übergeben. Protons eigene Hilfsprozesse
  (`reaper`, `wineserver`, `pv-bwrap`) tragen dieselbe `SteamAppId` und **nicht** die
  Anvil-Markierung. Die neue Begründung im Kommentar geht nur auf Anvils eigene
  Werkzeuge ein, nicht auf Protons.
* Fix: Entweder belegen, dass die Hilfsprozesse nicht länger leben als das Spiel
  (dann Kommentar entsprechend), oder die alte Entscheidung wiederherstellen.
  Diese Änderung kam nach meinem Messsnapshot und ist **nicht durchgemessen**.

### [MEDIUM] M-6 — Suite-Laufzeit versiebenfacht, weil Tests echte Prozesse starten

* Datei: `tests/test_predeploy_launch.py`
* Problem: 1,4 s (HEAD) → 10,4 s. Die neuen Tests starten echte `python3`-Prozesse
  (`test_own_tools_are_not_mistaken_for_the_game`,
  `test_host_scan_snippet_matches_the_local_scan`, `test_appid_match_stops_at_the_value_boundary`),
  schlafen in Warteschleifen und bauen echte `GamePanel`-Widgets mit Watcher-Threads.
  Das ist auch der Grund, warum C-1 jetzt zuverlässig zuschlägt.
* Fix: Wo möglich `/proc`-Zugriff über `tmp_path` abbilden statt echte Prozesse zu
  starten; die Warteschleifen auf Ereignisse statt auf `sleep` stellen.

### [LOW] L-1 — Entsperren nach Spielende dauert bis zu 5 s statt 2 s
* Datei: `anvil/widgets/game_panel.py:2796` (`_GAME_POLL_INTERVAL = 5`)
* Fix: Außerhalb von Flatpak bei 2 s bleiben — der lokale Scan kostet gemessen 5,3 ms.

### [LOW] L-2 — Defensives `getattr` in `_unlock_ui` ersatzlos entfernt
* Datei: `anvil/mainwindow.py:2784`

### [LOW] L-3 — `--talk-name` im unbenutzten Flatpak-Manifest ergänzt
* Datei: `packaging/flatpak/net.anvil_organizer.AnvilOrganizer.yml:28`
* Gebaut wird `com.github.Marc1326.AnvilOrganizer.yml` (dort schon vorhanden).

### [LOW] L-4 — Flatpak-Build-Artefakte sind in git getrackt
* Datei: `packaging/flatpak/repo/**`, `packaging/flatpak/build/**`
* Problem: Ein lokaler `build-flatpak.sh`-Lauf während dieser Prüfung hat getrackte
  Dateien geändert und gelöscht. Jeder `git status` und jeder Diff wird dadurch
  unbrauchbar; ein versehentliches `git add -A` schiebt hunderte MB ins Repo.
* Fix: In `.gitignore` aufnehmen und aus dem Index nehmen.

### [LOW] L-5 — `test_destination_inspection_uses_nearest_existing_parent` ist flakey
* Datei: `tests/test_storage_inventory.py:105`
* Problem: `assert result.free_bytes <= usage.free` vergleicht zwei Messungen des
  freien Speichers zu verschiedenen Zeitpunkten. Schreibt irgendein Prozess in der
  Zwischenzeit auf dieselbe Partition, schlägt der Test fehl — 1× in dieser Prüfung
  reproduziert, während parallel nach `/tmp` kopiert wurde.
* Vorbestehend, nicht Teil dieser Änderung.
* Fix: Toleranz einbauen oder `free_bytes` nur auf Plausibilität (>0) prüfen.

### [LOW] L-6 — Zwei `tr()`-Schlüssel fehlen in allen Locales (vorbestehend)
* `game_panel.shim_steam_hint` (`game_panel.py:2633`) und `dialog.warning`
  (`mainwindow.py`) sind in keiner der 7 Locale-Dateien definiert — schon bei HEAD.
* Nicht durch diese Änderung verursacht, aber bei einem Steam-Start mit
  `WINEDLLOVERRIDES` sieht der Nutzer den rohen Schlüssel.

---

## Ergebnis

**NEEDS FIXES**

Blockierend:
1. **C-1** — die Suite stürzt nach jeder Quelltextänderung ab. Solange das so ist,
   belegt kein grüner Lauf irgendetwas.
2. **H-2** — die Crash-Wiederherstellung räumt für Instanzen ohne auflösbares Plugin
   gar nicht mehr auf; das ist eine echte Verschlechterung gegenüber HEAD.
3. **H-1** — die drei tragenden Sicherungen des Fixes sind nicht getestet;
   der Runde-3-Fix Nr. 1 lässt sich spurlos zurückbauen.

Vor einer erneuten Prüfung muss der Arbeitsbaum eingefroren werden. Die Änderungen
von 21:53–21:55 (Nullbyte-Grenze, `_launch_via_proton` mit AppId, `_refuse_while_game_runs`)
sind gelesen, aber nicht durchgemessen — für sie gilt keine Aussage aus den
Abschnitten 5 und 6.

Bestätigt in Ordnung: Rückfrage auf allen Startpfaden, `bool | None` bei allen vier
Aufrufern, kein `AttributeError` in `_search_terms`, `tests/conftest.py` inklusive
Ausstieg, alle 5 neuen Schlüssel in 7 Locales, `py_compile` für alle 9 Dateien,
beide neuen Module in allen Auslieferungspfaden und `tests/` in keinem.
