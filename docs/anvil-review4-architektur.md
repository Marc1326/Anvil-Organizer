# QA Review 4 — Architektur / Regeln / MO2

Datum: 2026-08-06
Stand: nicht committete Änderungen gegen HEAD `d174cd6` (v1.7.0)
Umfang: 16 Dateien, +1174 / -111 Zeilen

Gelesen (Pflicht):
- `/home/mob/Projekte/Anvil Organizer/CLAUDE.md`
- `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md` (244 Zeilen, vollständig)
- MO2-Referenz: **tatsächlicher Pfad `/home/mob/Projekte/Fremd-Mod Manager/mo2-referenz/src/`**
  (`processrunner.h/.cpp`, `usvfsconnector.cpp`, `organizercore.cpp`).
  ARCHITEKTUR.md:217 und :233 nennen `/home/mob/Projekte/mo2-referenz/src/` — der Pfad
  existiert nicht mehr (`find` ausgeführt). **Doku-Fehler, siehe LOW-5.**

---

## 0. Kurzergebnis

| Prüfpunkt | Ergebnis |
|---|---|
| Fixes aus Runde 3 (5 Stück) | **alle 5 umgesetzt und belegt** |
| Testsuite | `304 passed, 1 skipped` (4,2 s / 5,3 s) |
| `py_compile` alle geänderten Dateien | OK |
| tr()-Keys in 7 Locales | **vollständig, Key-Sets deckungsgleich** |
| MO2-Erwähnungen im neuen Code | keine |
| `setStyleSheet()` in neuen Zeilen | keine |
| hardcoded Pfade | keine (nur `/proc`, Testfixtures) |
| ARCHITEKTUR.md §9 Regeln 1–5, 7 | nicht berührt |
| ARCHITEKTUR.md §9 Regel 6 (Purge-Zeitpunkt) | **10 von 10 Purge-Stellen geändert → Freigabe nötig** |
| Löschlogik selbst | **unangetastet** |

**Ergebnis: NEEDS DECISION** — kein blockierender Bug gefunden. Die Freigabe von
Marc nach ARCHITEKTUR.md:215 fehlt (Abschnitt 5). Zusätzlich 1 × MEDIUM,
5 × LOW zur AI-Sichtbarkeit und Codehygiene.

---

## 1. Verifikation der Runde-3-Fixes

| # | Fix | Beleg | Status |
|---|-----|-------|--------|
| 1 | `clear_watch_target()` erhöht `_watch_generation` | `game_panel.py:2777-2786`, `self._watch_generation += 1` in Zeile 2786; Test `test_clearing_the_target_retires_the_running_watcher` prüft 7 → 8 | ✅ |
| 2 | `confirm_start_while_running()` öffentlich, leert das Ziel nicht mehr, setzt `_forced_launch` | Definition `game_panel.py:1912`; kein `clear_watch_target()` im Ja-Zweig, stattdessen `self._forced_launch = True` (1934). Aufrufer: `game_panel.py:1966`, `mainwindow.py:1317` (Proton-Tool), `mainwindow.py:2685` (eigenes Programm) | ✅ |
| 3 | `plugin_watch_target()` + `_search_terms()` als Fallback | `game_process.py:143-156`, `game_panel.py:2792-2801`; Test `test_state_falls_back_to_the_current_game` belegt `("1091500", "cp.exe")` | ✅ |
| 4 | `_predeploy_for_launch` → `bool \| None` | `mainwindow.py:2598`, `return None` in 2615; beide Aufrufer werten aus (`mainwindow.py:2648-2657`, `game_panel.py:2007-2015`) | ✅ |
| 5 | `_QUERY_STATE_TTL` | `game_panel.py:27`, Wert 3; genutzt in `game_state()` `game_panel.py:2842` | ✅ |

**Zu Fix 2 — Lückenprüfung ausgeführt.** Alle 4 Aufrufer von
`_predeploy_for_launch` (`mainwindow.py:1319, 2648, 2687`, `game_panel.py:2007`)
haben unmittelbar davor ein `confirm_start_while_running()`. Da diese Methode
`_forced_launch` in Zeile 1918 **zuerst auf False setzt**, kann kein alter
`True`-Wert die Sperre in `_predeploy_for_launch` überspringen. Kein Leck.
(Latentes Risiko siehe LOW-1.)

**Zu Fix 4 — Doppeldialog geprüft.** Bei laufendem Spiel meldet
`_predeploy_for_launch` `error.game_already_running` und gibt `None` zurück;
beide Aufrufer unterdrücken daraufhin `error.deploy_failed_*`. Kein zweiter,
falsch begründeter Dialog mehr.

---

## 2. AI-SICHTBARKEIT — gemessen, nicht geschätzt

Messgrundlage: AST + tokenize über **alle 1978 Funktionen in `anvil/`**.

### 2.1 Bestand (Baseline aus HEAD)

```
1264 von 1978 Funktionen haben einen Docstring (63 %)
Docstring-Zeilen: Median 1  |  Mittel 2,7  |  90. Perzentil 7  |  max 29
Docstring >= 4 Zeilen: 28 %   |   >= 5 Zeilen: 23,7 %   |   >= 6 Zeilen: 15 %
Docstring LÄNGER als der eigene Code: 78 von 1264 = 6,2 %
Kommentardichte (Fn >= 5 Zeilen): Median 0,0 %  |  Mittel 3,3 %
```

### 2.2 Die neuen Konstrukte

| Funktion | Zeilen | Docstring-Z. | Kommentar-Z. | Doc-Anteil |
|---|---:|---:|---:|---:|
| `is_game_running()` | 8 | **6** | 0 | **75 %** |
| `_search_terms()` | 10 | **6** | 0 | **60 %** |
| `lookup_game_pid()` | 12 | **7** | 0 | **58 %** |
| `clear_watch_target()` | 10 | **5** | 0 | **50 %** |
| `game_state()` | 26 | **11** | 2 | **42 %** |
| `plugin_watch_target()` | 13 | 5 | 0 | 38 % |
| `find_game_process()` | 25 | 6 | 3 | 24 % |
| `confirm_start_while_running()` | 24 | 5 | 2 | 21 % |
| `scan_proc_for_game()` | 31 | 6 | 0 | 19 % |
| `_on_unlock_clicked()` | 34 | 6 | 3 | 18 % |
| `_note_game_state()` | 7 | 1 | 0 | 14 % |
| `_release_ui_lock()` | 7 | 1 | 0 | 14 % |
| `_predeploy_for_launch()` | 47 | 6 | 2 | 13 % |
| `_purge_after_game()` | 15 | 1 | 0 | 7 % |

### 2.3 Bewertung

**Kommentardichte: unauffällig.** 0–12 % gegen einen Projektmittelwert von 3,3 %.
Die Kommentare sitzen dort, wo die Logik nicht selbsterklärend ist (Generation-Zähler,
stdin statt argv, Event-Schleife des Dialogs). Kein Befund.

**Docstring-Länge: auffällig — siehe LOW-2.** Sechs der neuen Funktionen haben
einen Docstring, der **länger ist als ihr eigener Code**. Im Bestand trifft das
auf 6,2 % der dokumentierten Funktionen zu, hier auf 6 von 14 = 43 % — der
Siebenfache Anteil. `is_game_running()` besteht aus 2 Zeilen Code und 6 Zeilen
Docstring. `game_state()` hat mit 11 Zeilen einen Docstring über dem
90. Perzentil des gesamten Projekts (7). Das ist das klassische Muster
„jede Designentscheidung im Docstring rechtfertigen" und liest sich
übererklärt.

**Neue Tests: passt zur Datei, nicht zum Projekt — siehe LOW-3.**

```
tests/test_predeploy_launch.py  HEAD:  17 Tests, 8 mit Docstring (47 %), 1 mehrzeilig
tests/test_predeploy_launch.py  jetzt: 35 Tests, 22 mit Docstring (62 %), 5 mehrzeilig
alle übrigen tests/:                  264 Tests, 33 mit Docstring (12 %), 10 mehrzeilig (3 %)
```

Die Datei war schon vor der Änderung ein Ausreißer (47 % gegen 12 % im Rest).
Die neuen Tests setzen den Stil fort — **formal konsistent**. Auffällig ist
nicht die Anzahl, sondern der **Inhalt** von 5 mehrzeiligen Docstrings: sie
erzählen die Fehlerhistorie statt die Prüfung. Beispiel
`test_scan_does_not_find_itself` (`tests/test_predeploy_launch.py:889-894`):

> „Passing it in argv put it into the scanner's own cmdline, so every lookup
> matched the scanner — the game looked like it was running forever and the UI
> never unlocked."

Das gehört in eine Commit-Nachricht, nicht in einen Testnamen-Kommentar.
Gleiches bei `test_appear_timeout_leaves_the_target_in_place`,
`test_state_falls_back_to_the_current_game`,
`test_confirmed_unlock_removes_the_deployment`. Ein menschlicher Entwickler
schreibt hier eher eine Zeile oder gar nichts.

**Sprachmischung — gemessen:**

```
Baseline HEAD   mainwindow.py    89 DE / 179 EN  ->  33 % deutsch
Baseline HEAD   game_panel.py    40 DE /  72 EN  ->  36 % deutsch

Neue Zeilen     game_panel.py    10 DE /  20 EN  ->  33 % deutsch   (= Baseline)
Neue Zeilen     mainwindow.py     7 DE /   6 EN  ->  54 % deutsch   (n=13, Rauschen)
Neue Zeilen     debug_log.py      6 DE /   0 EN  ->  100 % deutsch  (in sich konsistent)
Neue Zeilen     game_process.py   7 DE /  11 EN  ->  39 % deutsch   (NEUE Datei)
Neue Zeilen     tests/            0 DE /  16 EN
```

Mischung ist im Bestand die Norm — für `game_panel.py` und `mainwindow.py`
**kein Befund**. `debug_log.py` ist durchgängig deutsch, sauber.
Der einzige echte Befund ist `game_process.py`: eine **brandneue Datei ohne
Altlast**, die deutschen Modul-Docstring, englische Funktions-Docstrings und
deutsche Inline-Kommentare **innerhalb derselben Funktion** mischt
(`find_game_process()`, `game_process.py:158-182`: englischer Docstring,
deutsche Kommentare in Zeile 168 und 175). Siehe LOW-4.

---

## 3. `bool | None` als Rückgabewert — projektüblich?

Gemessen im Bestand: `bool | None` als Rückgabe-Annotation kommt in `anvil/`
sonst **nicht** vor. Das Projekt löst vergleichbare Fälle anders:

- `silent_purge() -> object | None` / `silent_deploy() -> object | None`
  (`game_panel.py:1401`, `:1178`) — Ergebnisobjekt mit `.success` / `.errors`,
  `None` = „nicht zuständig". Das ist das etablierte Muster für
  „Erfolg + Begründung".
- Andernorts wird schlicht `bool` zurückgegeben und der Grund über einen
  Log-Print transportiert.

`bool | None` ist in Python nicht falsch, aber hier **schwer zu lesen**: beide
Aufrufer müssen `if not result:` **und** `if result is not None:` prüfen
(`mainwindow.py:2649-2656`, `game_panel.py:2008-2014`), also einen
Drei-Zustand über einen Zweizustands-Typ. Der Kommentar
„# None heisst: der Hook hat den Grund schon gemeldet"
(`game_panel.py:2010`) ist nötig, weil der Typ es nicht sagt.

**Projekttypischer wäre** ein kleines Ergebnisobjekt analog `silent_purge()`,
z. B. `SimpleNamespace(ok=False, reported=True)`, oder ein Enum
`LaunchResult.OK / .DEPLOY_FAILED / .REFUSED`. Da `GAME_RUNNING` /
`GAME_STOPPED` / `GAME_UNKNOWN` in `game_panel.py:20-22` bereits als
String-Konstanten eingeführt wurden, wäre eine dritte Konstante hier stilistisch
schlüssig.

Einstufung: **LOW** (LOW-6). Funktional korrekt, durch Tests abgedeckt
(`test_running_game_blocks_a_second_launch` prüft `assertIsNone`), aber kein
Muster, das es im Projekt sonst gibt.

---

## 4. MO2-Vergleich — „läuft das Spiel noch?" und „wann wird aufgeräumt?"

Gelesen: `processrunner.h:20-35`, `processrunner.cpp:214-281` (`timedWait`),
`:805-840` (`shouldRefresh`), `usvfsconnector.cpp:188-194` (Destruktor),
`organizercore.cpp:2028-2043` (`afterRun`).

### 4.1 Wie MO2 die Frage beantwortet

MO2 fragt **nicht**. Es wartet auf ein **Kernel-Handle**:
`timedWait(HANDLE handle, DWORD pid, ...)` (`processrunner.cpp:218`) blockiert
in `singleWait(handle, pid)`. Ein Handle, das man selbst hält, kann nicht
„unbekannt" sein — die Antwort ist per Konstruktion zuverlässig. Anvil hat unter
Linux/Proton/Steam kein solches Handle (Steam reicht den Prozess weiter), muss
also die Prozessliste durchsuchen — und Flatpak nimmt ihm sogar die.

MO2 kennt den blinden Fall trotzdem: `getInterestingProcess()` gibt ein leeres
Ergebnis zurück, wenn kein Prozess geöffnet werden kann
(`processrunner.cpp:805-810`, Kommentar *„this can happen if none of the
processes can be opened"*). MO2 behandelt das als „nichts zum Warten", **nicht**
als „beendet".

Das Zustandsmodell ist ausdrücklich mehr als zweiwertig
(`processrunner.h:20-35`): `Running` / `Completed` / `Error` / `Cancelled` /
`ForceUnlocked`. `shouldRefresh()` (`processrunner.cpp:805-840`) wertet nur
`Completed` und `ForceUnlocked` als handlungsauslösend; `Error` und `Cancelled`
lösen **nichts** aus.

**Bewertung:** Anvils Tri-State `GAME_RUNNING / GAME_STOPPED / GAME_UNKNOWN`
(`game_panel.py:20-22`) ist damit **keine Anvil-Erfindung**, sondern die
Linux-Entsprechung zu MO2s `Results`-Enum. `UNKNOWN` entspricht MO2s `Error`:
kein Anlass zum Handeln. Das ist die **richtige** Richtung.

### 4.2 Wann MO2 aufräumt

**Gar nicht.** MO2 hat keinen Purge-Begriff. USVFS ist prozessgebunden; endet
der gehookte Prozessbaum, gilt das Mapping einfach nicht mehr. Der einzige
Abbau ist `usvfsDisconnectVFS()` im Destruktor
(`usvfsconnector.cpp:188-193`) — also beim **Beenden von MO2**, nicht beim
Beenden des Spiels. `afterRun()` (`organizercore.cpp:2028-2043`) macht
ausschließlich `refreshDirectoryStructure()` + `cycleDiagnostics()`, keine
Aufräumarbeiten im Spielverzeichnis.

MO2 kann die Frage „darf ich jetzt löschen?" also **nie falsch beantworten** —
sie stellt sich nicht. Anvil muss sie stellen (ARCHITEKTUR.md:20-25).

**Bewertung des Umbaus gegen MO2:** Der Umbau verschiebt Anvil systematisch in
Richtung MO2-Semantik: Bei Zweifel wird **nichts** angefasst, das Deployment
bleibt liegen. ARCHITEKTUR.md:227 nennt genau das als bewussten Unterschied
Nr. 5 — *„Persistent Deploy — Symlinks bleiben nach Game-Ende bestehen"*, und
ARCHITEKTUR.md:23 *„Symlinks bleiben bis Purge"*. Der Code in HEAD purgt in
`_unlock_ui` unmittelbar nach Spielende und weicht damit **stärker** von der
Doku ab als der neue Stand. **Der Umbau passt zu MO2 und zu ARCHITEKTUR.md.**

Eine Ausnahme läuft der MO2-Logik zuwider: Punkt 8 in Abschnitt 5 — der
Entsperren-Knopf purgt jetzt auf ausdrücklichen Wunsch **auch dann**, wenn der
Prozess noch gefunden wird. MO2s `ForceUnlocked` gibt nur die Oberfläche frei
und fasst nichts an (`processrunner.cpp:249-252`, `:829-833`). Das ist eine
bewusste Anvil-Abweichung, die Marc mitentscheiden muss.

---

## 5. ARCHITEKTUR.md:215 — vollständige Liste geänderter Purge-ZEITPUNKTE

> „**NIEMALS** den Deploy-Mechanismus (Symlinks, Kopien, Manifest, Purge,
> Frameworks) ändern ohne ausdrückliche Zustimmung von Marc. Das schließt ein:
> […] die Purge-Logik […]" — ARCHITEKTUR.md:215

Methodik: `grep -n "silent_purge\|deployer.purge()\|remove_orphaned_links"` in
HEAD **und** im Arbeitsstand. **Beide Male exakt 10 Fundstellen** — es wurde
keine Purge-Stelle hinzugefügt und keine entfernt. Geändert wurde
ausschließlich, **unter welcher Bedingung** sie erreicht werden.

### Es sind alle 10. Neun purgen seltener, eine purgt öfter.

| # | Stelle (aktuell) | Was sich am Zeitpunkt ändert |
|---|---|---|
| 1 | `mainwindow.py:1050` — Basisverzeichnis-Migration, Schleife über alle Instanzen | Neuer Vorab-Wächter `mainwindow.py:1047` `is_game_running()`: Wird bei irgendeiner Instanz ein laufendes Spiel vermutet, bricht die Migration mit `storage.error_game_running` ab **statt zu purgen**. |
| 2 | `mainwindow.py:1134` — Instanz-Migration (`_storage_next`) | Neuer Vorab-Wächter `mainwindow.py:1131` `is_game_running()`: gleiche Wirkung — Abbruch statt Purge für die gerade umgezogene Instanz. |
| 3 | `mainwindow.py:1606` + `:1607` — Crash-Recovery beim Start (`_crash_recovery_purge`, gerufen aus `_check_first_start` `:1527`) | Neu `mainwindow.py:1585-1595`: pro Instanz wird über `plugin_watch_target()` + `find_game_process()` nachgesehen. Bei Treffer **oder** bei nicht durchführbarer Suche → `continue`. Das überspringt **beides**, `deployer.purge()` **und** `remove_orphaned_links()`. Betrifft nur Instanzen, deren Plugin `GameSteamId` oder `GameBinary` liefert. |
| 4 | `mainwindow.py:1660` — Instanzwechsel, Schritt 4 | Neu `mainwindow.py:1656`: `self._game_running or is_game_running()` → Purge entfällt, Log „instance switch while the game may run — deployment kept". Vorher **bedingungslos**. |
| 5 | `mainwindow.py:2341` — `_do_redeploy`, der 500-ms-Debounce nach Änderungen an der Mod-Liste | Neu `mainwindow.py:2336`: gleicher Wächter → Aufräumen des Restbestands entfällt. Vorher lief der Purge, sobald `has_deployment()` True war. |
| 6 | `mainwindow.py:2622` — Vorab-Purge vor jedem Start (`_predeploy_for_launch`) | Neu `mainwindow.py:2607-2615`: bei `_game_running` oder `game_state()==RUNNING` **und** nicht `_forced_launch` → Rückgabe `None`, **kein Purge, kein Deploy, kein Start**, Dialog `error.game_already_running`. Bricht den in ARCHITEKTUR.md:108-111 dokumentierten Ablauf purge → deploy → starten vollständig ab. |
| 7 | `mainwindow.py:2795` via `_unlock_ui` (`mainwindow.py:2767`, verbunden mit `game_stopped` in `:436`) | Zwei Verschiebungen: **(a)** neuer Parameter `stopped`; bei `stopped=False` (Suche war blind, `game_panel.py:2913`/`:2935`) wird gar nicht erst geprüft, sondern nur entsperrt — vorher purgte HEAD hier, sobald `is_game_running()` False lieferte. **(b)** neuer Frühausstieg `mainwindow.py:2775` `_unlock_pending`: ein während des Entsperren-Dialogs eintreffendes `game_stopped` wird **verworfen** statt sofort zu purgen. |
| 8 | `mainwindow.py:2795` via `_on_unlock_clicked` (`mainwindow.py:2732`) — **NEUER Pfad, purgt MEHR** | Der Entsperren-Knopf ist von `_unlock_ui` auf `_on_unlock_clicked` umgehängt (`mainwindow.py:330`). Nach „Ja" im neuen Dialog `dialog.unlock_purge_*` wird `_purge_after_game()` **ohne erneute Nachprüfung** ausgeführt (`:2763`) — also **auch dann, wenn der Prozess weiterhin gefunden wird**. In HEAD war das unmöglich: `_unlock_ui` überstimmte den Nutzer per `still_running`-Prüfung. Der Test `test_confirmed_unlock_removes_the_deployment` fixiert dieses Verhalten mit `running=True`. **Das ist die einzige Stelle, an der jetzt in einer Lage gelöscht wird, in der HEAD nicht löschte.** |
| 9 | `mainwindow.py:4757` — Profilwechsel, Schritt 6 | Neu `mainwindow.py:4753`: Wächter → Purge des alten Profils entfällt bei laufendem Spiel. Vorher **bedingungslos**. |
| 10 | `mainwindow.py:7146` — `closeEvent`, Purge beim Beenden von Anvil | Neu `mainwindow.py:7142`: Wächter → Anvil schließt **ohne** zu purgen, wenn ein Spiel laufen könnte. Vorher **bedingungslos**. Vergleich: MO2 baut den VFS an dieser Stelle ab (`usvfsconnector.cpp:188`) — die Abweichung ist hier größer als bei den anderen neun. |

### Indirekte Verschiebung ohne eigene Purge-Stelle

| A | `game_panel.py:1966` — `confirm_start_while_running()` steht **vor** allen Deploy-Zweigen in `_on_start_clicked` | Bei „Nein" endet der Start sofort. Damit unterbleiben der GRB-Forge-`silent_deploy()`, der REDmod-Zweig und der Vorab-Purge aus Punkt 6. Kein eigener Purge-Aufruf, aber ein neuer Abbruchpunkt davor. |
| B | `game_panel.py:2777-2786` — `clear_watch_target()` | Wird nach jedem bestätigten Stopp gerufen (`mainwindow.py:2764`, `:2785`). Ohne Watch-Ziel greift der Fallback `_search_terms()` → `plugin_watch_target(self._current_plugin)`, die Wächter bleiben also auch nach einem Anvil-Neustart wirksam. Kein Purge, aber Voraussetzung dafür, dass die Punkte 1–10 überhaupt je wieder purgen. |

### Die Löschlogik selbst — unangetastet ✅

```
git diff HEAD --stat -- anvil/core/mod_deployer.py   ->  leer
git diff HEAD -- anvil/widgets/game_panel.py | grep "silent_purge\|def purge"  ->  leer
```

- `anvil/core/mod_deployer.py` ist **nicht** in `git status`. `purge()`,
  `remove_orphaned_links()`, die Manifest-Behandlung, `shim_copy`, die
  Framework-Ausnahme (`type: "copy"` bleibt liegen) und das Entfernen leerer
  Verzeichnisse sind Zeile für Zeile unverändert.
- `GamePanel.silent_purge()` (`game_panel.py:1401`),
  `silent_deploy()` (`:1178`), `silent_deploy_fast()` (`:1342`),
  `has_deployment()` (`:1142`) sind unverändert.
- **Was gelöscht wird, wie es gelöscht wird und was verschont bleibt: identisch
  zu HEAD.** Geändert ist ausschließlich das *Ob* und *Wann*.

**→ Freigabe von Marc nach ARCHITEKTUR.md:215 erforderlich.**
Empfehlung: Punkte 1–7 und 9–10 sind reine Sicherheits-Wächter in
Richtung ARCHITEKTUR.md:23/227 („Symlinks bleiben bis Purge") und decken sich
mit MO2s Verhalten (Abschnitt 4.2) — unkritisch. **Punkt 8** ist die einzige
Erweiterung des Löschzeitpunkts und der einzige Punkt, der wirklich eine
Entscheidung braucht.

---

## 6. Prüfung der Architektur-Regeln (ARCHITEKTUR.md §9)

| Regel | Beleg | Ergebnis |
|---|---|---|
| 1 — nie direkt ins Game-Dir kopieren | `mod_deployer.py` unverändert; kein `shutil.copy`/`copytree` in neuen Zeilen | ✅ |
| 2 — `.mods/`-Struktur nicht verändern | kein Installer/Flatten-Code berührt | ✅ |
| 3 — Frameworks nicht in `.mods/`/modlist.txt | kein Framework-Code berührt (`_auto_relock_instance` nur aufgerufen, nicht geändert) | ✅ |
| 4 — `active_mods.json` bei Rename/Delete | kein Rename-/Delete-Pfad berührt | ✅ |
| 5 — nur globale API | keine `modlist.txt`-Zugriffe in den Änderungen | ✅ |
| 6 — Purge-Mechanismus | **Abschnitt 5 — Zeitpunkt an 10 Stellen geändert, Freigabe fehlt** | ⚠️ |
| 7 — Flatten | nicht berührt | ✅ |
| 8 — MO2-Referenz gelesen | Abschnitt 4 | ✅ |

---

## 7. Befunde

### [MEDIUM-1] Neuer Wächter in `_crash_recovery_purge` schaltet bei blinder Suche das gesamte Aufräumen ab
- Datei: `anvil/mainwindow.py:1585-1595`
- Problem: Die Bedingung ist `if pid is not None or not reliable: continue`.
  In Flatpak liefert `find_game_process()` `reliable=False`, sobald
  `flatpak-spawn --host` nicht durchkommt (`game_process.py:172-181`) — etwa in
  einer bereits installierten Flatpak-Version **ohne** das neu ergänzte
  `--talk-name=org.freedesktop.Flatpak`
  (`packaging/flatpak/net.anvil_organizer.AnvilOrganizer.yml:28`). Dann wird
  beim Start **jede** Instanz mit Plugin-Suchmerkmalen übersprungen, inklusive
  `remove_orphaned_links()` — also auch das Aufräumen verwaister Links, die gar
  nichts mit einem laufenden Spiel zu tun haben. Nach einem echten Absturz
  bliebe das Spielverzeichnis dauerhaft verschmutzt, ohne dass der Nutzer eine
  Meldung sieht (nur ein `print`).
  Die Richtung ist sicher (es wird nichts Falsches gelöscht), die Wirkung aber
  weitreichender als der Docstring in `:1562-1569` andeutet, der nur von
  „a game started from an earlier Anvil session" spricht.
  Gemessen: Ein Scan kostet lokal 4,8 ms, als Subprozess 21,4 ms (597 Prozesse
  in `/proc`) — die Laufzeit ist **kein** Problem; das Zeitlimit von 3 s
  (`game_process.py:90`) greift nur im Pathologiefall.
- Fix: `remove_orphaned_links()` vom `continue` ausnehmen (verwaiste Links ohne
  Manifest gehören nicht zu einem laufenden Deployment), oder den blinden Fall
  vom Trefferfall trennen und bei `not reliable` mindestens einen sichtbaren
  Hinweis geben. Alternativ Docstring `:1562-1569` präzisieren.

### [LOW-1] `_forced_launch` wird nie zurückgesetzt, nur überschrieben
- Datei: `anvil/widgets/game_panel.py:1918`, `:1934`; gelesen in
  `anvil/mainwindow.py:2606`
- Problem: Nach einem erzwungenen Start bleibt `_forced_launch = True` bis zum
  nächsten `confirm_start_while_running()`. Heute unschädlich, weil alle vier
  Aufrufer von `_predeploy_for_launch` (`mainwindow.py:1319, 2648, 2687`,
  `game_panel.py:2007`) unmittelbar davor bestätigen lassen — geprüft und
  belegt. Es ist aber ein stiller Sicherheitsschalter: ein künftiger fünfter
  Aufrufer ohne vorherige Bestätigung würde den Wächter aus Abschnitt 5 Punkt 6
  unbemerkt aushebeln.
- Fix: `_forced_launch` in `_predeploy_for_launch` nach dem Auslesen wieder auf
  False setzen (Einmal-Ticket), oder als Parameter durchreichen statt als Feld.
- Zusatz: `mainwindow.py:2606` greift mit `getattr(self._game_panel,
  "_forced_launch", False)` auf ein **privates** Feld eines anderen Objekts zu.
  Eine öffentliche Abfrage (analog `watch_generation()`, `game_panel.py:2788`)
  wäre sauberer und macht den Vertrag sichtbar.

### [LOW-2] Docstrings der neuen Kleinfunktionen sind länger als ihr Code
- Dateien: `anvil/widgets/game_panel.py:2851` (`is_game_running`, 6 Doc-/2
  Codezeilen), `:2792` (`_search_terms`, 6/3), `:2803` (`lookup_game_pid`, 7/4),
  `:2777` (`clear_watch_target`, 5/4), `:2816` (`game_state`, 11 Doc-Zeilen);
  `anvil/core/game_process.py:143` (`plugin_watch_target`, 5/…)
- Problem: Gemessen (Abschnitt 2): im Bestand haben 6,2 % der dokumentierten
  Funktionen einen Docstring, der länger ist als ihr Code — hier 43 %.
  `game_state()` liegt mit 11 Zeilen über dem 90. Perzentil des Projekts (7).
  Verstößt gegen CLAUDE.md „KEINE AI-typischen Docstrings überall reinschreiben
  — nur wo wirklich nötig" und „Kommentare sparsam".
- Fix: Auf je 1–2 Zeilen kürzen. Die Begründung, warum `UNKNOWN` als „läuft"
  gilt, gehört **einmal** an eine Stelle (sinnvoll: der Modul-Docstring von
  `game_process.py:1-10`, wo sie bereits steht), nicht in vier Funktionen
  parallel.

### [LOW-3] Neue Test-Docstrings erzählen die Fehlerhistorie
- Datei: `tests/test_predeploy_launch.py:889-894`, `:733-738`, `:855-860`,
  `:640-646`, `:718-723`
- Problem: 5 mehrzeilige Docstrings begründen, welcher Bug einmal existierte
  („Passing it in argv put it into the scanner's own cmdline …", „Clearing the
  watch target here made game_state() answer STOPPED unconditionally …"). Der
  Rest des Projekts kommentiert Tests zu 12 % überhaupt und zu 3 % mehrzeilig
  (gemessen über 264 Tests). Innerhalb dieser Datei ist der Stil zwar
  konsistent (HEAD hatte dort schon 47 % / 1 mehrzeilig), der Inhalt liest sich
  aber wie ein Änderungsprotokoll — genau das Muster, das CLAUDE.md unter
  „AI-SICHTBARKEIT" ausschließen will.
- Fix: Auf eine Zeile eindampfen oder ganz weglassen; die Testnamen sind
  bereits sprechend.

### [LOW-4] `game_process.py` mischt Deutsch und Englisch innerhalb einer Funktion
- Datei: `anvil/core/game_process.py` — deutscher Modul-Docstring (`:1-10`),
  englische Funktions-Docstrings (`:20-25`, `:100-104`, `:117-120`, `:159-165`),
  deutscher `plugin_watch_target`-Docstring (`:144-148`), deutsche
  Inline-Kommentare in einer Funktion mit englischem Docstring (`:168`, `:175`),
  deutscher Kommentar bei `_HOST_SCAN_TIMEOUT` (`:88-89`) neben englischem bei
  `_SCAN_FAILED` (`:85`)
- Problem: Gemessen ist Mischung im Bestand normal (33–36 % deutsch in
  `mainwindow.py`/`game_panel.py`), dort aber historisch gewachsen. Hier ist es
  eine **neue Datei ohne Altlast**, die den Wechsel sogar innerhalb einer
  Funktion vollzieht. `debug_log.py` zeigt es richtig: durchgängig deutsch.
- Fix: `game_process.py` auf eine Sprache vereinheitlichen — naheliegend
  deutsch, passend zum Modul-Docstring und zu `debug_log.py`.

### [LOW-5] ARCHITEKTUR.md nennt einen MO2-Pfad, den es nicht gibt
- Datei: `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md:217` und `:233`
- Problem: Beide Stellen verweisen auf `/home/mob/Projekte/mo2-referenz/src/`.
  `find /home/mob/Projekte -maxdepth 4 -type d -iname "*mo2*"` liefert dort
  nichts; die Referenz liegt unter
  `/home/mob/Projekte/Fremd-Mod Manager/mo2-referenz/src/`. Regel 8 in
  ARCHITEKTUR.md:217 („NIEMALS Code ändern ohne vorher MO2-Referenz zu lesen")
  ist mit dem angegebenen Pfad nicht befolgbar.
- Fix: Beide Zeilen im Wiki korrigieren. Betrifft nicht dieses Änderungspaket,
  gehört aber protokolliert.

### [LOW-6] `bool | None` ist im Projekt ohne Vorbild
- Datei: `anvil/mainwindow.py:2598`
- Details und Alternativvorschlag: Abschnitt 3.

### [LOW-7] Kleinigkeiten
- `anvil/widgets/game_panel.py:33-37`: Zwischen `_state_of()` und `_dlog()`
  steht nur **eine** Leerzeile (per `cat -A` geprüft), PEP 8 verlangt zwei.
  Kein Linter im Projekt konfiguriert (`pyproject.toml` enthält weder ruff noch
  flake8; flake8 ist im Venv nicht installiert) — daher rein kosmetisch.
- `anvil/mainwindow.py:2746`, `:2756`, `:2775`: `_unlock_pending` wird **nicht**
  in `__init__` angelegt, sondern lazy erzeugt und in `_unlock_ui` per
  `getattr(self, "_unlock_pending", False)` abgesichert. Funktioniert, ist aber
  das Muster, das der QA-Prüfpunkt „Variable Scope" adressiert. Sauberer:
  `self._unlock_pending = False` neben `self._game_running` im Konstruktor,
  dann kann `getattr` durch direkten Zugriff ersetzt werden.
- `tests/test_predeploy_launch.py:88`: `_launch_refused=False` im
  `SimpleNamespace`. `grep -rn "_launch_refused" anvil/` liefert **nichts** —
  totes Attribut aus einer früheren Iteration. Entfernen.

---

## 8. Was ausdrücklich geprüft und für gut befunden wurde

- **Signalsignatur.** `game_stopped = Signal(bool)` (`game_panel.py:232`), drei
  `emit()`-Stellen (`:2913` False, `:2935` False, `:2941` True), genau **eine**
  Verbindung (`mainwindow.py:436` → `_unlock_ui`), Slot hat
  `stopped: bool = True` — der Default hält die Altaufrufe in den Tests gültig.
- **Generation-Zähler.** `_watch_generation` wird in `_start_process_watcher`
  (`:2867`) **und** in `clear_watch_target` (`:2786`) erhöht. Der Watcher-Thread
  prüft `outdated()` vor jedem Zustandsschreiben **und** vor jedem `emit`.
  Test `test_an_old_watcher_does_not_report_for_a_new_launch` belegt genau ein
  Signal bei zwei Startvorgängen.
- **Selbstfund verhindert.** Der Suchbegriff geht über **stdin** in das
  Host-Schnipsel (`game_process.py:53-58, 104`), nicht über argv — sonst fände
  jeder Scan den Scanner. `scan_proc_for_game` überspringt zusätzlich die eigene
  PID (`:30`). Test `test_scan_does_not_find_itself` und
  `test_host_scan_snippet_matches_the_local_scan` decken beide Pfade ab; letzterer
  vergleicht Schnipsel und lokale Funktion gegen denselben echten Prozess.
- **Locales.** Rekursiver Key-Diff über alle 7 Sprachen: HEAD 1294 → jetzt 1298
  Keys, in **jeder** Datei dieselben 4 neuen
  (`dialog.start_while_running_text`, `dialog.unlock_purge_text`,
  `dialog.unlock_purge_title`, `error.game_already_running`), **keine** entfernt,
  Key-Mengen aller 7 Dateien untereinander deckungsgleich.
- **`has_manifest`-Vorziehen** (`mainwindow.py:1596`): reines Umstellen.
  `ModDeployer.__init__` legt kein Manifest an (geprüft) — verhaltensgleich.
- **Kein `setStyleSheet()`**, keine MO2-/ModOrganizer-/USVFS-Erwähnung, keine
  hardcodierten Pfade in neuen Zeilen (nur `/proc` und Testfixtures unter `/tmp`).
- **Flatpak-Manifest.** `--talk-name=org.freedesktop.Flatpak`
  (`packaging/flatpak/…yml:28`) ist die Voraussetzung für `flatpak-spawn --host`
  und damit für den ganzen Ansatz — korrekt ergänzt.
- **Testsuite.** `304 passed, 1 skipped`. Kein Regress.

---

## 9. Ergebnis

**NEEDS DECISION**

Kein CRITICAL, kein HIGH. Der Umbau ist technisch stimmig, gut getestet und
bewegt Anvil in Richtung MO2-Semantik und in Richtung der eigenen
Architektur-Doku (ARCHITEKTUR.md:23, :227).

Vor dem Commit nötig:
1. **Freigabe von Marc** zur Liste in Abschnitt 5 (ARCHITEKTUR.md:215).
   Neun Stellen purgen vorsichtiger, eine (Punkt 8, Entsperren-Knopf) purgt in
   einer Lage, in der HEAD nicht purgte.
2. MEDIUM-1 klären (`remove_orphaned_links()` vom `continue` ausnehmen oder
   Docstring präzisieren).
3. Optional vor dem Commit: LOW-2/3/4 (AI-Sichtbarkeit — Docstrings kürzen,
   `game_process.py` sprachlich vereinheitlichen), LOW-7 (totes Testattribut,
   `_unlock_pending` in `__init__`).
