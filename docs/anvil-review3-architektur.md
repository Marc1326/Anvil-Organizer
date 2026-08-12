# QA Review 3 — Architektur & Projektregeln

Datum: 2026-08-06
Stand: nicht committete Änderungen gegen `d174cd6` (v1.7.0)
Grundlagen: `/home/mob/Projekte/Anvil Organizer/CLAUDE.md`,
`/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md` (244 Zeilen, gelesen),
MO2-Referenz (siehe Abschnitt 7)

Geprüfte Dateien laut `git status`: `anvil/core/debug_log.py` (neu),
`anvil/core/game_process.py` (neu), `anvil/core/diagnostics.py`, `anvil/main.py`,
`anvil/mainwindow.py`, `anvil/widgets/game_panel.py`, 7 Locale-Dateien,
`packaging/flatpak/net.anvil_organizer.AnvilOrganizer.yml`,
`tests/test_predeploy_launch.py`, `tests/test_game_ghostreconbreakpoint.py`
(16 Dateien, +987/−105).

---

## 1. Ergebnis

**NEEDS FIXES.**

Ein Befund ist blockierend: `clear_watch_target()` erhöht den neuen
Generationszähler nicht. Dadurch meldet ein noch laufender Watcher-Thread
„Spiel beendet" und Anvil purgt die gerade frisch deployten Mods. Genau der
Vorfall, den der ganze Umbau verhindern soll. Reproduziert (Abschnitt 3).

Zusätzlich enthält der Änderungssatz 16 Stellen, an denen sich der **Zeitpunkt**
des Purge verschiebt. ARCHITEKTUR.md Zeile 215 verlangt dafür ausdrückliche
Zustimmung von Marc. Die vollständige Liste steht in Abschnitt 6.

---

## 2. Verifikation der fünf Fixes aus Runde 2

| # | Behauptung | Ergebnis |
|---|---|---|
| 1 | `_clear_watch_target()` → `clear_watch_target()`, nur noch aus mainwindow.py nach dem Purge, nicht mehr aus dem Watcher-Thread | **TEILWEISE FALSCH** — siehe unten |
| 2 | Generationszähler `_watch_generation` mit `outdated()` | ✅ vorhanden, greift aber nicht für Fix 1 |
| 3 | `_confirm_start_while_running()` + `dialog.start_while_running_text` | ✅ |
| 4 | „geloescht" → „gelöscht", lokaler `import time` weg, `_Tee` um close/buffer/writelines ergänzt | ✅ |
| 5 | Direktstart-Watcher zurückgebaut, `notify_game_started` wieder einstellig | ✅ |

### Fix 1 — im Detail

Umbenennung ist erfolgt, und der Watcher-Thread ruft die Methode tatsächlich
nicht mehr auf. Belegt durch `grep -rn "clear_watch_target" --include=*.py`:

```
anvil/mainwindow.py:2754        self._game_panel.clear_watch_target()   # nach _purge_after_game()
anvil/mainwindow.py:2779        self._game_panel.clear_watch_target()   # nach _purge_after_game()
anvil/widgets/game_panel.py:1926    self.clear_watch_target()           # OHNE Purge
anvil/widgets/game_panel.py:2767    def clear_watch_target(self)
```

Der Teil „nur noch aus mainwindow.py, nachdem gepurgt wurde" stimmt **nicht**:
es gibt einen dritten Aufrufer, `game_panel.py:1926` in
`_confirm_start_while_running()`, und dort wird **nicht** gepurgt. Diese Stelle
ist die Ursache des blockierenden Befundes.

### Fix 4 — Belege

- `anvil/widgets/game_panel.py:2801` — „gelöscht", korrekt.
- Kein lokales `import time` mehr im DLL-Override-Zweig; Modulimport steht in
  `anvil/widgets/game_panel.py:11`.
- `_Tee`: `writelines` (debug_log.py:72), `close` (92), `buffer` (97-99).

### Fix 5 — Beleg

`anvil/widgets/game_panel.py:2043` `def notify_game_started(self, pid: int)` ist
zeichengleich mit dem HEAD-Stand (`git show HEAD:...` Zeile 1996). Der
Direktstart-Pfad startet keinen Watcher — `_start_process_watcher` wird nur an
`game_panel.py:2606` (`_launch_via_steam`) und `2699` (`_launch_via_proton`)
gerufen.

---

## 3. Befunde

### [HIGH] H-1 — `clear_watch_target()` invalidiert den laufenden Watcher nicht → frisch deployte Mods werden gepurgt

- Datei: `anvil/widgets/game_panel.py:2767-2775` (fehlendes
  `self._watch_generation += 1`), Aufruf `anvil/widgets/game_panel.py:1926`
- Problem:
  `_start_process_watcher()` erhöht `_watch_generation` (2838) und der Watcher
  prüft über `outdated()` (2842-2845), ob er noch zuständig ist.
  `clear_watch_target()` setzt aber nur `_watch_binary`, `_watch_app_id` und
  `_game_state` zurück — der Zähler bleibt unverändert. Ein laufender Watcher
  ist danach weiterhin „aktuell", bekommt bei der nächsten Abfrage
  `lookup_game_pid()` → `(None, True)` (weil `_watch_binary` leer ist,
  game_panel.py:2785-2787), bricht aus der Schleife aus und sendet
  `game_stopped.emit(True)` (2908).

  Ablauf im Alltag:
  1. Ein Spiel läuft (oder wird fälschlich als laufend erkannt).
  2. Nutzer klickt Starten → `_confirm_start_while_running()` (1907) →
     Dialog → „Ja" → `clear_watch_target()` (1926).
  3. `_on_start_clicked` läuft weiter: `_predeploy_hook("game_start")` →
     `_predeploy_for_launch` → Purge + Deploy (Sekunden bis Minuten).
  4. Der **alte** Watcher wacht auf (Poll 5 s bzw. 1 s in der Erscheinungsphase),
     hält sich für zuständig, sendet `game_stopped(True)`.
  5. `MainWindow._unlock_ui(True)` (2757) → `is_game_running()` → `game_state()`
     liefert GAME_STOPPED, weil das Watch-Ziel leer ist → `_purge_after_game()`
     (2778) räumt das gerade erzeugte Deployment weg, danach
     `clear_watch_target()` und `_release_ui_lock()`.

  Beim **Steam/Proton-Pfad** schließt `_start_process_watcher()` das Fenster
  wieder (Generation +1) — aber erst nach Purge+Deploy, das Fenster ist also
  mehrere Sekunden breit.

  Beim **Direktstart** (GOG/Epic) wird `_start_process_watcher()` überhaupt nie
  gerufen (nur 2606/2699 = Steam/Proton). Dort ist der Fehler **deterministisch**:
  der alte Watcher meldet garantiert „beendet", das Deployment fliegt raus, und
  die UI entsperrt sich unmittelbar nachdem sie gesperrt wurde. Das Spiel startet
  ohne Mods.

- Beweis (ausgeführt, beide Tests bestanden):

  Teil 1 — der Zähler bleibt stehen und der alte Watcher meldet:
  ```
  generation vorher=1 nachher=1
  [WATCHER] game process gone
  game_stopped-Emissionen: [True]
  is_game_running() nach clear: False
  ```
  Teil 2 — die Meldung löst den Purge aus:
  ```
  [LAUNCH] game stopped — cleaning up
  [LAUNCH] purge result: success=True, removed=7, errors=0
  game_state: stopped | purges: 1
  ```

- Fix: In `clear_watch_target()` `self._watch_generation += 1` ergänzen. Damit
  ist jeder laufende Watcher sofort `outdated()` und schweigt.

### [MEDIUM] M-2 — Zwei verschiedene Prädikate: UNKNOWN gilt an den Launch-Guards als „läuft nicht"

- Dateien: `anvil/mainwindow.py:1016, 1081, 2599`;
  `anvil/widgets/game_panel.py:1913, 2000`
- Problem: `is_game_running()` ist ausdrücklich so gebaut, dass ein unbekannter
  Zustand als „läuft" zählt (Docstring `game_panel.py:2818-2823`). Genau diese
  Regel wird an fünf Stellen umgangen, weil dort direkt auf
  `game_state() == GAME_RUNNING` geprüft wird — GAME_UNKNOWN rutscht durch:

  ```
  mainwindow.py:1016   game_state() == GAME_RUNNING   (Basisverzeichnis-Migration)
  mainwindow.py:1081   game_state() == GAME_RUNNING   (Storage-Migration)
  mainwindow.py:2599   game_state() == GAME_RUNNING   (Pre-Launch-Purge/Deploy)
  game_panel.py:1913   game_state() != GAME_RUNNING   (Start-Rückfrage)
  game_panel.py:2000   game_state() != GAME_RUNNING   (Dialog-Unterdrückung)
  ```
  gegenüber `is_game_running()` an 1047, 1131, 1653, 2333, 2773, 4743, 7132.

  Folge: Wenn der Host-Lookup in Flatpak dauerhaft scheitert (UNKNOWN), purgt
  und deployt der Spielstart trotzdem — unter einem möglicherweise laufenden
  Spiel. Das ist genau der Schadensfall, den der Umbau abstellen soll.
- Fix: Entweder auf `is_game_running()` vereinheitlichen und den UNKNOWN-Fall
  über `_confirm_start_while_running()` mitfangen (Text passt bereits: „Es sieht
  so aus, als würde noch ein Spiel laufen"), oder die Asymmetrie in
  ARCHITEKTUR.md als bewusste Entscheidung festhalten.

### [MEDIUM] M-3 — Dauerhaftes UNKNOWN bedeutet: Anvil purgt nie wieder, ohne Hinweis und ohne Ausweg

- Dateien: `anvil/widgets/game_panel.py:2817-2824`, `anvil/mainwindow.py:1653,
  2333, 4743, 7132, 1584-1594`
- Problem: Solange `find_game_process()` `reliable=False` liefert, blocken alle
  `is_game_running()`-Guards. Betroffen sind Instanzwechsel, Profilwechsel,
  `_do_redeploy`, `closeEvent` **und** die Crash-Recovery beim nächsten Start
  (`mainwindow.py:1588` `if pid is not None or not reliable: continue`). Das
  Deployment bleibt dann dauerhaft im Spielordner liegen.

  Der Nutzer erfährt davon nichts: alle Meldungen gehen nur nach stdout
  (`[PURGE] ... deployment kept`) bzw. in `_dlog`. Es gibt in der UI **keine**
  manuelle Purge-/Bereinigen-Aktion — geprüft mit `grep -n purge` über
  `anvil/locales/de.json` (nur `dialog.unlock_purge_*` und ein Migrations-Text)
  und über `anvil/mainwindow.py`. Der einzige nutzergesteuerte Purge ist der
  Entsperren-Knopf, und der ist nur sichtbar, solange das Lock-Overlay steht.
- Fix: Bei anhaltendem UNKNOWN einen Toast/Statusbar-Hinweis ausgeben und eine
  Menü-Aktion „Spielordner bereinigen" anbieten (neuer tr()-Key in allen 7
  Locales).

### [MEDIUM] M-4 — `game_state()` blockiert den GUI-Thread, entgegen dem eigenen Docstring

- Datei: `anvil/widgets/game_panel.py:2790-2809`, insbesondere 2808
- Problem: Der Docstring (2793-2795) sagt zu, dass in Flatpak kein Host-Aufruf
  im GUI-Thread stattfindet. Tatsächlich fällt `game_state()` immer dann auf
  `lookup_game_pid()` durch, wenn der Zwischenspeicher kalt ist **oder** zuletzt
  STOPPED gemeldet wurde (bewusst, Kommentar 2800-2801). Der Normalfall „Spiel
  läuft nicht" führt also bei jedem Guard-Aufruf zu einem echten Lookup.

  In Flatpak kostet das bis zu `_HOST_SCAN_TIMEOUT = 3` s
  (`game_process.py:86`) plus bis zu 3 s für den `ps`-Fallback
  (`game_process.py:120-133`) — 6 s GUI-Freeze pro Aufruf.

  Aufrufer im GUI-Thread: `_do_redeploy` (`mainwindow.py:2333`, hängt am
  500-ms-Debounce nach **jeder** Modlisten-Änderung, `mainwindow.py:448`),
  `closeEvent` (7132), `_teardown_current_instance` (1653),
  `_on_profile_changed` (4743), `_predeploy_for_launch` (2599).
  `_crash_recovery_purge` (1587) macht das beim App-Start sequenziell einmal pro
  Instanz mit Manifest.

  Entschärft wird das nur dadurch, dass `game_state()` bei leerem Watch-Ziel
  sofort STOPPED liefert (2797-2798) — das gilt aber nicht in der Sitzung nach
  einem Erscheinungs-Timeout, wo das Ziel absichtlich stehen bleibt (2865-2881).
- Fix: Entweder Docstring korrigieren, oder auch STOPPED kurz cachen (z. B. 2 s)
  und den Timeout für GUI-Aufrufe deutlich senken.

### [LOW] L-5 — Migrationsabbruch nach bereits erfolgtem Instanzwechsel

- Datei: `anvil/mainwindow.py:1044-1049`, `_storage_fail` bei `1264-1270`
- Problem: Der Eintritts-Guard (1016) lässt UNKNOWN durch, der Guard in der
  Schleife (1047) nicht. Bei UNKNOWN läuft die Migration also an, ruft
  `switch_instance(name)` (1044) und bricht erst danach ab. `_storage_fail`
  stellt die ursprüngliche Instanz nicht wieder her — Anvil bleibt auf einer
  fremden Instanz stehen. Gleiches Muster bei `1128-1133`.
- Fix: Am Eintritt dieselbe Prüfung wie in der Schleife verwenden
  (`is_game_running()`), dann entfällt der Halbabbruch.

### [LOW] L-6 — `debug_log_path()` ist toter Code

- Datei: `anvil/core/debug_log.py:22-25`
- Problem: Die Funktion wird nirgends aufgerufen (`grep -rn debug_log_path
  --include=*.py anvil/ tests/` → genau 1 Treffer, die Definition selbst).
  `anvil/core/diagnostics.py:241` baut den Pfad stattdessen selbst zusammen.
- Fix: Entweder in `diagnostics.log_sources()` verwenden oder entfernen.

### [LOW] L-7 — `_Tee.fileno()` wirft, wenn kein Originalstream existiert

- Datei: `anvil/core/debug_log.py:101-105`
- Problem: Genau in dem Szenario, für das das Modul gebaut wurde (Start ohne
  Terminal), kann `sys.__stdout__` `None` sein; `fileno()` wirft dann `OSError`.
  Im Anvil-Code selbst wird `sys.stdout.fileno()` nicht benutzt (geprüft), Qt
  oder Bibliotheken könnten es aber tun.
- Fix: Auf `os.devnull` zurückfallen statt zu werfen, oder den Fall dokumentieren.

### [LOW] L-8 — Fehlender Titel-Key für zwei neue Dialoge

- Dateien: `anvil/widgets/game_panel.py:1917`, `anvil/mainwindow.py:2605`
- Problem: `dialog.unlock_purge_title` existiert, aber
  `dialog.start_while_running_text` und `error.game_already_running` haben keinen
  eigenen Titel; als Titel dient `tr("game_panel.start")` („Starten"). Das ist
  inkonsistent zum Rest der Datei, in der Dialoge Titel- und Text-Key haben.
- Fix: `dialog.start_while_running_title` in allen 7 Locales ergänzen.

### [LOW] L-9 — Umlaut-Schreibweise innerhalb desselben Diffs uneinheitlich

- ASCII-Transliteration: `game_process.py:5, 9, 88`;
  `debug_log.py:1, 3, 5, 6, 93, 94`; `mainwindow.py:1585, 2734, 2735`
- Echte Umlaute: `game_panel.py:2801` („gelöscht"), `mainwindow.py:1652,
  2600-2602`
- Bewertung: Beide Schreibweisen gibt es im Bestand (15 Dateien mit
  Transliteration, 35 mit echten Umlauten), also **kein Regelverstoß**. Innerhalb
  eines einzigen Änderungssatzes fällt der Wechsel aber auf.

---

## 4. AI-Sichtbarkeit — gemessen, nicht geschätzt

CLAUDE.md verbietet AI-typische Docstrings „überall" und verlangt sparsame
Kommentare. Gemessen mit einem AST/tokenize-Skript, jeweils Arbeitsstand gegen
`git worktree` auf HEAD.

### Kommentardichte je Datei

| Datei | Zeilen | Kommentarzeilen | Anteil |
|---|---|---|---|
| anvil/main.py (Bestand) | 178 | 23 | 12,9 % |
| anvil/core/mod_deployer.py (Bestand) | 992 | 103 | 10,4 % |
| anvil/core/mod_installer.py (Bestand) | 737 | 60 | 8,1 % |
| anvil/mainwindow.py | 8434 | 636 | 7,5 % |
| **anvil/core/game_process.py (neu)** | **167** | **13** | **7,8 %** |
| anvil/widgets/game_panel.py | 3773 | 237 | 6,3 % |
| anvil/core/diagnostics.py (Bestand) | 326 | 16 | 4,9 % |
| **anvil/core/debug_log.py (neu)** | **141** | **3** | **2,1 %** |
| anvil/core/subprocess_env.py (Bestand) | 238 | 5 | 2,1 % |

Beide neuen Dateien liegen mitten im Korridor des Bestands. **Unauffällig.**

### Kommentar/Code je neuer Funktion

| Funktion | Code | Kommentar | Anteil |
|---|---|---|---|
| `outdated()` (game_panel.py:2842) | 2 | 2 | 100 % |
| `lookup_game_pid()` | 4 | 1 | 25 % |
| `find_game_process()` (game_process.py) | 16 | 3 | 19 % |
| `_watcher()` | 58 | 10 | 17 % |
| `game_state()` | 12 | 2 | 17 % |
| `_start_process_watcher()` | 72 | 10 | 14 % |
| `_on_unlock_clicked()` | 25 | 3 | 12 % |
| `_unlock_ui()` | 15 | 2 | 13 % |
| `_predeploy_for_launch()` | 39 | 4 | 10 % |
| `_crash_recovery_purge()` | 40 | 2 | 5 % |
| `_purge_after_game()` | 14 | 0 | 0 % |
| `_release_ui_lock()` | 6 | 0 | 0 % |
| `_confirm_start_while_running()` | 16 | 0 | 0 % |
| `observe()` | 3 | 0 | 0 % |

Referenz Bestand (HEAD): mainwindow.py Kommentar/Code über alle 233 Funktionen
**8,5 %**, game_panel.py über 118 Funktionen **6,7 %**. Von den Funktionen mit
≥ 10 Codezeilen liegen in mainwindow.py **21 %** bei ≥ 14 %, in game_panel.py
**4 %** (Ausreißer: `refresh_downloads` 20 %, `_insert_archive_row` 19 %).

Bewertung: Der Watcher (14-17 %) liegt am **oberen Rand** des Hausstils, aber
innerhalb — `refresh_downloads` im selben File liegt höher. `_purge_after_game()`,
`_release_ui_lock()` und `_confirm_start_while_running()` sind kommentarfrei.
Die einzige formal übererklärte Stelle ist `outdated()`: 2 Codezeilen, 2
Kommentarzeilen. Der Kommentar erklärt allerdings die Race-Bedingung, die aus
dem Code nicht ablesbar ist — sachlich gerechtfertigt, könnte aber auf eine
Zeile zusammengezogen werden.

**Kein maschinengenerierter Eindruck**: keine Aufzählungs-Docstrings mit
„Args/Returns/Raises"-Schema, keine Wiederholung des Funktionsnamens im
Docstring, keine „This function ..."-Formulierungen, keine Emojis.

### Docstrings bei Kurzfunktionen

Im Bestand hat game_panel.py bei **89 %** aller Funktionen einen Docstring — die
neuen Funktionen fügen sich also ein. Auffällig ist nur die **Länge** bei sehr
kurzen Funktionen:

| Neue Funktion | Codezeilen | Docstringzeilen |
|---|---|---|
| `is_game_running()` | 2 | 6 |
| `clear_watch_target()` | 4 | 5 |
| `lookup_game_pid()` | 4 | 7 |

Im Bestand haben in game_panel.py **5 von 36** Kurzfunktionen (14 %) einen
Docstring ≥ 4 Zeilen (`set_predeploy_hook` 2/5, `cancel_redmod_if_running` 3/5,
`set_virtual_files` 3/5, `_exe_identity` 4/6, `set_separator_deploy_paths` 4/6),
in mainwindow.py **0 von 42**. Präzedenzfälle existieren also, aber die Häufung
(3 von 6 neuen Kurzfunktionen) liegt über dem Hausschnitt.

Empfehlung (kosmetisch, kein Blocker): `is_game_running()` und
`clear_watch_target()` auf eine Docstring-Zeile kürzen.

### Sprachmischung

Gemessen über alle aussagekräftigen Kommentare (≥ 3 Wörter):

| Datei | HEAD | Arbeitsstand |
|---|---|---|
| game_panel.py | DE 43 / EN 86 | DE 48 / EN 98 |
| mainwindow.py | DE 93 / EN 242 | DE 103 / EN 244 |
| main.py | DE 11 / EN 1 | DE 13 / EN 1 |
| diagnostics.py | DE 7 / EN 0 | DE 7 / EN 0 |
| game_process.py (neu) | — | DE 5 / EN 7 |
| debug_log.py (neu) | — | DE 3 / EN 0 |

Bewertung je Datei:
- `main.py` (deutschdominiert) — neuer Kommentar 150-151 auf Deutsch. **Passt.**
- `diagnostics.py` (deutsch) — neuer Kommentar 247 auf Deutsch. **Passt.**
- `mainwindow.py` (mischsprachig, EN-dominiert) — neue Docstrings englisch,
  neue Inline-Kommentare teils deutsch (1585, 1652, 2600-2602, 2734-2735, 2766).
  **Passt zum Bestand.**
- `game_panel.py` (mischsprachig, EN-dominiert) — Docstrings englisch,
  zwei deutsche Inline-Kommentare (1956-1957, 2800-2801). **Passt.**
- `debug_log.py` (neu) — durchgehend deutsch. **Konsistent.**
- `game_process.py` (neu) — Moduldocstring deutsch, alle Funktionsdocstrings
  englisch, Inline-Kommentare gemischt. Bei einer **neuen** Datei ohne
  Altlasten ist das die einzige stilistisch fragwürdige Stelle. Kein
  Regelverstoß (der Bestand mischt genauso), aber vermeidbar.

### Weitere Verbotsprüfungen (alle auf dem Diff ausgeführt)

- MO2 / ModOrganizer / USVFS in neuen Zeilen: **keine Treffer.**
- „Claude", „Anthropic", „generated by", „Co-Authored": **keine Treffer.**
- `setStyleSheet()` in neuen Zeilen: **keine Treffer.**
- Hardcodierte Pfade in neuen Python-Zeilen: nur `/proc`,
  `/proc/{pid}/environ`, `/proc/{pid}/cmdline` (Systempfade, unvermeidbar) sowie
  `/game/` und `/tmp/instance` aus den Tests. **Kein Verstoß.**

---

## 5. Werkzeuge, Tests, Modulaufteilung

### Ruff `--select F`

`ruff` ist weder im venv noch im System installiert (`pip` fehlt im venv);
ausgeführt über `uvx ruff`. Vergleich Arbeitsstand ↔ `git worktree` auf HEAD,
Zeilennummern normalisiert:

```
=== nur JETZT (neu) ===   (nur Summenzeilen)
=== nur HEAD (weggefallen) ===   (nur Summenzeilen)
```

**26 F-Befunde, in HEAD und Arbeitsstand identisch — kein einziger neuer.**
Die beiden neuen Dateien `game_process.py` und `debug_log.py` erzeugen **null**
F-Befunde. Zusätzlich geprüft: `E301,E302,E303,E305` (Preview) → 4 Befunde in
HEAD, 4 im Arbeitsstand, identisch. `E741` in game_panel.py:1594 ist bestehend.

### Tests

`.venv/bin/python -m pytest tests/ -q` → **300 passed, 1 skipped in 2,62 s.**
`py_compile` über alle sechs geänderten Python-Dateien: OK.
Alle 7 Locale-Dateien sind valides JSON.

Anmerkung: keiner der 300 Tests deckt Befund H-1 ab.
`test_an_old_watcher_does_not_report_for_a_new_launch`
(tests/test_predeploy_launch.py:748) prüft nur den Generationswechsel über
`_start_process_watcher()`, nicht über `clear_watch_target()`.

### tr()-Keys

Skriptgeprüft, rekursiv flachgeklopft, gegen `git show HEAD:` je Datei:

```
de/en/es/fr/it/pt/ru: keys HEAD=1294  jetzt=1298
  fehlende Pflichtkeys: keine
  verlorene Keys:       keine
  geänderte Werte:      keine
  neue Keys: dialog.start_while_running_text, dialog.unlock_purge_text,
             dialog.unlock_purge_title, error.game_already_running
RESULT: OK
```

Zusätzlich Strukturvergleich aller sechs übrigen Locales gegen `de.json`:
keine Abweichung. Alle vier geforderten Keys stehen in **allen 7** Dateien.

### Modulaufteilung

Die Prozesssuche ist korrekt aus `game_panel.py` nach `anvil/core/game_process.py`
herausgezogen worden — Core-Logik gehört nicht in ein Widget. `game_panel.py`
importiert nur noch `find_game_process` (Zeile 17). `debug_log.py` liegt
ebenfalls richtig unter `anvil/core/`. Keine Zirkelimporte: `game_process.py`
importiert nur `anvil.core.subprocess_env`, `debug_log.py` importiert
`anvil.core.base_dir` verzögert innerhalb der Funktion (108-121). **In Ordnung.**

### Flatpak-Manifest

`--talk-name=org.freedesktop.Flatpak` (Zeile 27-28) ist für
`flatpak-spawn --host` erforderlich und **fehlte bisher** — obwohl HEAD
`flatpak-spawn --host` bereits an drei Stellen benutzt
(`subprocess_env.py:36, 56`, `script_merger_dialog.py:831`). Die Ergänzung
behebt also zusätzlich eine bestehende Lücke. **Korrekt.**

---

## 6. Purge-Zeitpunkt — Liste zur Freigabe durch Marc (ARCHITEKTUR.md:215)

ARCHITEKTUR.md Zeile 215: *„NIEMALS den Deploy-Mechanismus (Symlinks, Kopien,
Manifest, Purge, Frameworks) ändern ohne ausdrückliche Zustimmung von Marc."*

### 6a. Die Löschlogik selbst ist unangetastet — verifiziert

- `git status` meldet `anvil/core/mod_deployer.py`, `anvil/core/mod_installer.py`,
  `anvil/core/storage_migration.py` und `anvil/plugins/**` als **unverändert**.
- Im Diff von `game_panel.py` gibt es **keine einzige** Zeile, die
  `silent_purge`, `silent_deploy`, `_deployer.`, `MANIFEST`, `symlink`, `unlink`,
  `shutil.`, `os.remove` oder `rmtree` berührt (gezielt gegrept).
- `GamePanel.silent_purge()` / `silent_deploy()` (game_panel.py:1403 / 1412)
  sind unverändert, nur zeilenverschoben.
- Manifest-Format, `shim_copy`-Behandlung und Framework-Kopien: nicht berührt.

**Ergebnis: Symlink-Handling, Manifest und Löschlogik sind identisch zu v1.7.0.
Geändert hat sich ausschließlich, WANN gepurgt wird.**

### 6b. Purge wird jetzt übersprungen (neue Guards)

| # | Stelle | Zeile | Vorher | Jetzt |
|---|---|---|---|---|
| 1 | `_crash_recovery_purge` — App-Start, pro Instanz | mainwindow.py:1583-1594 | Purge lief immer, wenn ein Manifest existierte | `find_game_process(None, str(game_path))`; bei Treffer **oder** unzuverlässiger Auskunft `continue` |
| 2 | dieselbe Stelle, Nebenwirkung | mainwindow.py:1603-1604 | `remove_orphaned_links()` lief unabhängig vom Manifest | wird durch das `continue` **mit** übersprungen |
| 3 | `_teardown_current_instance` — Instanzwechsel, Schritt 4 | mainwindow.py:1653-1657 | `silent_purge()` unbedingt | nur wenn nicht `_game_running` und nicht `is_game_running()` |
| 4 | `_do_redeploy` — 500-ms-Debounce nach Modlisten-Änderung | mainwindow.py:2333-2336 | Purge des Restbestands | `return True` ohne Purge |
| 5 | `_on_profile_changed` — Profilwechsel | mainwindow.py:4743-4747 | `silent_purge()` unbedingt | übersprungen, wenn Spiel laufen könnte |
| 6 | `closeEvent` — App schließen | mainwindow.py:7132-7136 | beim Beenden wurde **immer** gepurgt | übersprungen, wenn Spiel laufen könnte |
| 7 | `_unlock_ui` — nach `game_stopped` | mainwindow.py:2757-2780 | Purge, sobald `is_game_running()` False war | zusätzlich: bei `stopped=False` (Zustand unbekannt) wird gar nicht erst geprüft |
| 8 | `_start_next_storage_instance` — Storage-Migration | mainwindow.py:1131-1134 | direkt `silent_purge()` | neuer Abbruch davor |
| 9 | `_schedule_base_directory_migration` — Basisverzeichnis | mainwindow.py:1047-1050 | direkt `silent_purge()` | neuer Abbruch davor |

### 6c. Purge wird verweigert oder an eine Nutzerentscheidung gebunden

| # | Stelle | Zeile | Änderung |
|---|---|---|---|
| 10 | `_predeploy_for_launch` | mainwindow.py:2599-2609 | Bei GAME_RUNNING wird der in ARCHITEKTUR.md:109-111 dokumentierte Ablauf **purge → deploy → starten** komplett abgebrochen: kein Purge, kein Deploy, kein Start, stattdessen `error.game_already_running` |
| 11 | `GamePanel._on_start_clicked` / `_confirm_start_while_running` | game_panel.py:1907-1927, 1956-1959 | Bei GAME_RUNNING fragt Anvil vor dem Start nach; „Nein" ⇒ der Pre-Launch-Purge findet nicht statt |
| 12 | `_on_unlock_clicked` (neu) | mainwindow.py:2722-2755 | Der Entsperren-Knopf purgte bisher automatisch, sobald `is_game_running()` False war. Jetzt: Rückfrage. „Nein" ⇒ kein Purge. „Ja" ⇒ Purge **ohne jede** Zustandsprüfung (bewusst, Docstring 2725-2727) |
| 13 | Eintritts-Guards Storage-Migration | mainwindow.py:1016, 1081 | `_game_running` um `game_state() == GAME_RUNNING` erweitert; blockiert den gesamten Migrationslauf samt seiner Purges |

### 6d. Purge-Zeitpunkt verschiebt sich indirekt über den Watcher

| # | Stelle | Zeile | Änderung |
|---|---|---|---|
| 14 | Poll-Intervall im „läuft"-Loop | game_panel.py:2762, 2904 | 2 s → 5 s (`_GAME_POLL_INTERVAL`). Der Purge nach Spielende kommt bis zu 5 s später, in Flatpak plus bis zu 6 s Host-Aufruf |
| 15 | Erscheinungs-Timeout | game_panel.py:2853-2854 | `for _ in range(120)` → Wanduhr-Deadline `time.monotonic() + 120`. In Flatpak dauerte die alte Schleife real 120 × (1 s + Host-Aufruf); jetzt sind es echte 120 s — der Purge-Auslöser kommt **früher** |
| 16 | Neue Karenzzeit `_GAME_LOOKUP_GRACE = 60` | game_panel.py:2765, 2895-2903 | Bei dauerhaft scheiterndem Lookup: `game_stopped(False)` → UI wird frei, aber es wird **nie** gepurgt |
| 17 | „Nie aufgetaucht"-Zweig | game_panel.py:2865-2881 | statt immer `game_stopped()` jetzt `game_stopped(blind_since is None)` — bei blindem Lookup also kein Purge |

Zusätzlich, unbeabsichtigt: Befund **H-1** ändert den Purge-Zeitpunkt in die
falsche Richtung (Purge unmittelbar nach dem Deploy). Der muss vor der Freigabe
behoben sein.

### 6e. Bewertung gegen ARCHITEKTUR.md

- ARCHITEKTUR.md:23 („Nach Game-Ende: Symlinks bleiben bis Purge") und :227
  („Persistent Deploy — Symlinks bleiben nach Game-Ende bestehen"): Der Umbau
  bewegt Anvil **auf die Doku zu**, nicht davon weg. Der bisherige Code purgte
  nach Spielende bedingungslos, was der Doku schon vorher widersprach.
- ARCHITEKTUR.md:109-111 (Ablauf beim Game-Start: purge → deploy → starten):
  Punkt 10 der Liste bricht diesen Ablauf ab. **Einzige Stelle, an der der
  Umbau der dokumentierten Reihenfolge widerspricht.** Wenn Marc zustimmt,
  gehört das in ARCHITEKTUR.md nachgetragen.

---

## 7. MO2-Vergleich

**Wichtiger Sachhinweis:** Der in ARCHITEKTUR.md:233 und :217 genannte Pfad
`/home/mob/Projekte/mo2-referenz/src/` **existiert nicht** (`ls` schlägt fehl,
`/home/mob/Projekte/mo2-referenz` gibt es nicht). Die Referenz liegt seit der
MO2-Bereinigung unter `/home/mob/Projekte/Fremd-Mod Manager/mo2-referenz/src/`
(per `find` verifiziert). **ARCHITEKTUR.md muss an dieser Stelle korrigiert
werden**, sonst kann Regel 8 formal nie erfüllt werden.

Gelesen: `processrunner.cpp`, `usvfsconnector.cpp`, `organizercore.cpp`.

| Aspekt | MO2 | Anvil (dieser Änderungssatz) | Bewertung |
|---|---|---|---|
| Wie wird „Spiel läuft" festgestellt | Job-Objekt + `WaitForSingleObject` (processrunner.cpp:63, 284-340) — autoritativ vom Kernel, nie Polling | Polling über `/proc` bzw. `flatpak-spawn --host` | Strukturell unvermeidbar (Sandbox + Steam-Reaper). Keine Abweichung im Sinne der Regel |
| Zustandsmodell | `Completed` / `Running` / `ForceUnlocked` / `Cancelled` / `Error` (processrunner.cpp:242-266) — `ForceUnlocked` gilt ausdrücklich **nicht** als „beendet" (shouldRefresh, 805-840) | `GAME_RUNNING` / `GAME_STOPPED` / `GAME_UNKNOWN` + `game_stopped(bool)` | **Bewegt sich auf MO2 zu.** Der Tri-State ist keine Anvil-Erfindung |
| Aufräumen nach Spielende | Kein Abbau. `usvfsClearVirtualMappings()` nur beim **Neuaufbau vor dem Start** (usvfsconnector.cpp:211-215, organizercore.cpp:476-478); `usvfsDisconnectVFS()` erst im Destruktor (188-190) | Neu: Deployment bleibt liegen, wenn das Spiel laufen könnte; der nächste Start räumt auf | **Näher an MO2 als vorher** |
| Nutzer-Entsperren | `ForceUnlocked` ist folgenlos, weil der VFS virtuell ist | Purge ist destruktiv, deshalb Rückfrage (mainwindow.py:2738-2744) | Bewusste, begründete Abweichung — MO2 hat das Problem nicht |

**Fazit MO2:** Keine Abweichung, die als Bug zu werten wäre. Der Umbau folgt dem
MO2-Muster enger als der bisherige Code. Punkt 10 der Purge-Liste (Startabbruch)
hat in MO2 keine Entsprechung, weil MO2 den Fall gar nicht kennt.

---

## 8. Die 7 Architektur-Pflichtprüfpunkte

| # | Regel | Ergebnis |
|---|---|---|
| 1 | Mod-Dateien niemals direkt ins Game-Verzeichnis kopieren | ✅ Deployer unverändert, keine neue Kopierlogik |
| 2 | Ordnerstruktur in `.mods/` nicht verändern | ✅ nicht berührt |
| 3 | Frameworks nicht in `.mods/` oder modlist.txt | ✅ nicht berührt |
| 4 | Bei Rename/Delete `active_mods.json` in allen Profilen aktualisieren | ✅ nicht betroffen |
| 5 | Nur globale API, keine Legacy-per-Profile-modlist.txt | ✅ nicht betroffen |
| 6 | MO2-Referenz konsultiert | ✅ gelesen — aber unter dem korrigierten Pfad, siehe Abschnitt 7 |
| 7 | Architektur-Doku gelesen | ✅ ARCHITEKTUR.md vollständig gelesen |

Keine der 7 Regeln ist verletzt. Der Blocker ist ein Logikfehler (H-1), kein
Architekturverstoß.

---

## 9. Empfohlene Reihenfolge

1. **H-1 beheben** — `self._watch_generation += 1` in `clear_watch_target()`
   (`anvil/widgets/game_panel.py:2767`). Blockierend.
2. **Regressionstest ergänzen** — „`clear_watch_target()` bringt einen laufenden
   Watcher zum Schweigen"; deckt aktuell kein Test ab.
3. **M-2 entscheiden** — UNKNOWN an den Launch-Guards: vereinheitlichen oder
   dokumentieren.
4. **M-3 / M-4** — Nutzerhinweis bei dauerhaftem UNKNOWN und GUI-Freeze in
   Flatpak; können auch in einem Folgeschritt kommen.
5. **Freigabe von Marc einholen** für die 17 Purge-Zeitpunkt-Änderungen aus
   Abschnitt 6 (ARCHITEKTUR.md:215), danach ARCHITEKTUR.md:109-111 und :233
   nachziehen.
6. L-5 bis L-9 nach Bedarf.

Ohne Punkt 1 und 5: **NEEDS FIXES.**
