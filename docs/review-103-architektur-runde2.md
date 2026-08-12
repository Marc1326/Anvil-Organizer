# Review #103 — Runde 2: Architektur, Qt-Konformitaet, Stil

Datum: 2026-08-08
Branch: fix/issue-103
Geprueft: uncommitted `git diff` (anvil/widgets/profile_bar.py) + tests/test_profile_bar_inline_input.py + tests/conftest.py
Vorgaenger: docs/review-103-architektur.md (Runde 1)

Alle Zahlen unten sind gemessen, nicht geschaetzt. Messungen offscreen gegen die echte
ProfileBar (PySide6 6.11.1). Mutationen wurden auf einer Kopie angewandt und der
Arbeitsstand danach per md5 wiederhergestellt (84260078b5c0ca07def3043bf6a6eb03).

Testlauf: `pytest tests/ -q` → **237 passed, 1 skipped** (mit QT_QPA_PLATFORM=wayland wie
in Marcs Umgebung, und identisch mit QT_QPA_PLATFORM=offscreen).

---

## 0. Architektur-Pflichtpunkte

| Regel | Ergebnis |
|---|---|
| 1. Mod-Dateien nie ins Game-Verzeichnis kopieren | nicht beruehrt (reine GUI-Aenderung) |
| 2. Ordnerstruktur in `.mods/` unveraendert | nicht beruehrt |
| 3. Frameworks nicht in `.mods/`/modlist.txt | nicht beruehrt |
| 4. active_mods.json in allen Profilen aktualisieren | nicht beruehrt — der Diff aendert kein Rename-Verhalten auf der Platte; `_on_profile_renamed` in mainwindow.py:4422 bleibt unangetastet |
| 5. Nur globale API, keine Legacy-modlist | nicht beruehrt |
| 6. MO2-Referenz konsultiert | weiterhin **nicht moeglich** — `/home/mob/Projekte/mo2-referenz/` existiert auf dieser Maschine nicht. Betroffen ist ohnehin keiner der vergleichspflichtigen Bereiche |
| 7. Architektur-Doku gelesen | ja (Runde 1) |

Kein Deploy-Pfad, kein Symlink, keine modlist.txt. Aus Architektursicht unbedenklich.

---

## 1. Status der Befunde aus Runde 1

| # | Befund Runde 1 | Status | Beleg |
|---|---|---|---|
| 1 | MEDIUM — Umbenennen-Pfad nicht mitgefixt | **behoben** | `_start_inline_rename` hat jetzt `edit.show()`, `_update_container_width()` und den verzoegerten Reveal (Zeilen 862, 863, 872). Gemessen: Feld 200/200 px sichtbar auf Tab 25 |
| 2 | MEDIUM — `_inline_input = edit` nach dem Timer | **behoben** | Zeile 767 steht vor Zeile 770. Kein Test deckt das ab (Mutation M4 ueberlebt) — es ist reine Absicherung, das ist vertretbar |
| 3 | MEDIUM — INLINE_INPUT_WIDTH unbegruendet, halb durchgezogen | **weitgehend behoben** | Kommentar Zeile 30-32 nennt jetzt den Grund; Zeile 857 benutzt die Konstante im Rename-Pfad. Nachgemessen am echten Feld (13 px Schrift, padding 6/12, 1 px Rahmen): de 103, en 114, **es 141**, fr 121, it 117, pt 128, ru 123 px. 140 war also tatsaechlich zu schmal. Die Zahl "139 px" im Kommentar ist 2 px zu niedrig (ohne Rahmen gerechnet), die Aussage stimmt trotzdem. Offen bleibt, warum 200 und nicht ~150 — siehe LOW-6 |
| 4 | LOW — `ensureVisible()` nicht erwaehnt | **nicht umgesetzt** | Nachgemessen: `ensureVisible(rechts,0,0,0)` + `ensureVisible(links,0,0,0)` liefert exakt denselben Scrollwert wie die Handrechnung (beide 2387). Kuer, kein Fehler |
| 5 | LOW — Feld breiter als Viewport | **behoben** | Zeile 788 `if edit.width() > visible or left < scrollbar.value():`. Kein Test deckt es ab (Mutation M14 ueberlebt) |
| 6 | LOW — Timer ohne Kontextobjekt | **behoben** | Zeilen 770 und 872 nutzen `QTimer.singleShot(0, self, ...)` |
| 7 | LOW — Benennung (`bar`, `sicht`, `links`, `rechts`) | **behoben** | jetzt `scrollbar`, `visible`, `left`, `right` |
| 8 | LOW — ASCII-Umschreibung der Umlaute | **behoben** | grep ueber alle neuen Zeilen findet keine Umschreibung mehr |
| 9 | LOW — Kommentardichte ueber dem Hausmass | **nicht behoben, eher verschaerft** | siehe LOW-1 |
| 10 | LOW — Guard in `_handle_scroll_key` zur Laufzeit unerreichbar | **unveraendert** | jetzt mit echter Event-Zustellung belegt, siehe LOW-4 |
| 11 | LOW — fehlende Typannotation | **nicht behoben** | Zeile 539 `def _handle_scroll_key(self, event) -> bool:`. `wheelEvent` daneben ist genauso unannotiert, also im Rahmen der Datei |
| 12 | LOW — Testluecke klassisches Theme + viele Profile | **behoben, und zwar genau richtig** | `test_inline_input_is_visible_in_the_classic_theme_too` ist der Test, der faellt, wenn man den Timer durch einen Direktaufruf ersetzt (Mutation M13) |
| 13 | LOW — QT_QPA_PLATFORM-Behandlung | **behoben** | `tests/conftest.py`, noqa-Kette entfaellt. Zwei Einschraenkungen, siehe Abschnitt 3 |

---

## 2. Ueberlappen sich die drei Schutzmechanismen?

Nein. Jeder der drei hat einen eigenen Test, der faellt, sobald man ihn entfernt.
Gemessen per Mutation (`tests/test_profile_bar_inline_input.py` + `..._scrolling.py`):

| Mutation | Ergebnis |
|---|---|
| Ausstieg in `_scroll_to_tab` entfernt | FAILED `test_selecting_a_profile_does_not_scroll_the_field_away` |
| Nachjustieren in `_update_container_width` entfernt | FAILED `test_a_pending_tab_click_does_not_scroll_the_field_away` |
| Guard in `_reveal_input` entfernt | FAILED `test_reveal_ignores_a_field_that_was_already_dismissed` |

Der zweite Fall ist der unintuitive: der Klick-Timer wird zwar schon vom `_scroll_to_tab`-
Ausstieg abgefangen, aber `_delayed_select()` ruft danach `_update_container_width()`, und die
geaenderte Containerbreite aendert Sichtfenster und Scrollbereich — ohne Nachjustieren rutscht
das Feld dabei wieder heraus. Kein Mechanismus ist also ueberfluessig.

Weitere Mutationen zur Kontrolle: `edit.show()` beim Anlegen (2 Tests fallen), `edit.show()`
beim Umbenennen (1 Test), `set_profiles`-Aufraeumen (1 Test), KeypadModifier (1 Test),
Guard in `_handle_scroll_key` (1 Test), `INLINE_INPUT_WIDTH` zurueck auf 140 (1 Test).
Ohne Testabdeckung geblieben sind: `_update_container_width()` im Rename-Pfad (LOW-3),
der Timer im Rename-Pfad (LOW-5), `_btn_add` in `_is_own_scroll_target` (LOW-2),
der Breiter-als-Sichtfenster-Zweig und die Reihenfolge von `self._inline_input = edit`.

---

## Findings

### [MEDIUM] Nach einem Umbenennen bleibt die Pillen-Gruppe zu breit — neu durch diesen Diff

- Datei: anvil/widgets/profile_bar.py:863 (neu) gegen 908-920 und 891-899 (unveraendert)
- Problem: `_start_inline_rename` ruft jetzt `_update_container_width()` auf, der Container
  waechst also auf die Feldbreite. `_cancel_inline_rename` und `_finish_inline_rename` rufen es
  aber nicht auf — anders als `_cancel_inline_create`/`_finish_inline_create`, die es beide tun.
  Die aufgeblaehte `maximumWidth` bleibt stehen.
  Gemessen im modernen Theme mit 3 Profilen (Fenster 900 px):

  | Zeitpunkt | Pillenbreite (tatsaechlich) | Inhalt braucht |
  |---|---|---|
  | vor dem Umbenennen | 260 | 260 |
  | waehrend des Umbenennens | 387 | 387 |
  | nach Abbruch (Esc/Fokus weg) | **387** | 260 |
  | nach Bestaetigung mit kuerzerem Namen | **387** | 236 |

  Zum Vergleich derselbe Ablauf mit HEAD (ohne den Diff): 260 / 260 / 260 — der Fehler ist neu.
  Zum Vergleich der Anlegen-Pfad im Arbeitsstand: 260 / 464 / 260 — dort stimmt es.
  Die Pille steht also nach jedem Umbenennen rund 130 px zu breit im Bild, sichtbar als
  leerer Streifen im Pillen-Hintergrund. Sie korrigiert sich erst beim naechsten
  `_update_container_width()`, und nach einem erfolgreichen Umbenennen kommt keins:
  `_on_profile_renamed` (mainwindow.py:4422) ruft `set_profiles` nur im Fehlerfall auf.
  Betroffen ist nur das moderne Theme (`_plus_inline`), und nur solange der Streifen
  schmaler ist als der Platz — also der Normalfall bei wenigen Profilen.
- Fix: `self._update_container_width()` ans Ende von `_cancel_inline_rename` und von
  `_finish_inline_rename` (nach `tab.show()`). Nachgestellt und gemessen: danach 260 bzw. 236,
  und die 24 Profilleisten-Tests bleiben gruen.

### [LOW-1] Kommentardichte weiterhin ueber dem Hausmass der Datei

- Datei: anvil/widgets/profile_bar.py:588-590, 706-709, 732-734, 757-759, 768-769
- Problem: 18 der 88 neuen Zeilen sind Kommentarzeilen. Bezogen auf Code+Kommentar sind das
  **23,4 %**, die Datei selbst liegt bei **7,7 %** (66 von 861 Zeilen). Dazu kommen zwei neue
  mehrzeilige Docstrings (`_handle_scroll_key`, `_reveal_input`) — die Datei hatte vor dem
  #103-Arbeitsstrang keinen einzigen mehrzeiligen Docstring, der einzige weitere
  (`_is_own_scroll_target`) stammt aus Commit 08d8588, also aus demselben Arbeitsstrang.
  Inhaltlich sind es "Warum"-Kommentare, das ist die gute Sorte, und der Ton ist sachlich.
  Zwei Stellen erklaeren aber dasselbe doppelt: Zeile 757-759 und Zeile 862 begruenden beide
  `edit.show()`.
  Zum AI-Geruch, ehrlich bewertet: keine Marketing-Formulierungen, keine
  "Note that"-Saetze, keine Emojis, echte Umlaute, kein MO2-Bezug, sinnvolle Kuerzel.
  Der Gedankenstrich kommt zweimal vor, die Datei benutzt ihn selbst (Zeile 371) — kein
  Fremdkoerper. Was auffaellt, ist ausschliesslich die Menge: dreimal so dicht wie der
  Bestand, und zwei Docstrings, die erklaeren statt zu benennen.
- Fix: die drei Bloecke auf je einen Satz kuerzen, die Doppelbegruendung bei `edit.show()`
  auf eine Stelle reduzieren.

### [LOW-2] `_btn_add` in `_is_own_scroll_target`: ungetestet und im klassischen Theme sachlich falsch

- Datei: anvil/widgets/profile_bar.py:535 gegen 525 (Docstring) und 421-422
- Problem: Der Docstring sagt "Whether *obj* is part of this bar's scrollable tab strip".
  Im klassischen Theme haengt `_btn_add` aber im aeusseren Layout (Zeile 421-422), also
  ausserhalb des Streifens; nur im modernen Theme sitzt er im `_tabs_layout` (Zeile 630).
  Die Erweiterung ist von keinem Test gedeckt (Mutation: entfernt man die Zeile, bleiben alle
  24 Tests gruen) und im Diff nicht begruendet.
- Fix: entweder einen Test (Rad ueber dem "+" scrollt den Streifen) oder die Zeile streichen.

### [LOW-3] `test_container_does_not_clip_the_rename_field` prueft ins Leere, wenn die Breite gar nicht gesetzt wird

- Datei: tests/test_profile_bar_inline_input.py:213-220
- Problem: Entfernt man `self._update_container_width()` aus `_start_inline_rename`, bleibt der
  Test gruen. Grund: dann wird `setMaximumWidth` nie aufgerufen, die `maximumWidth` steht auf
  dem Qt-Standard 16777215 und `>= sizeHint().width()` ist trivial erfuellt. Der Test faengt
  also nur das fehlende `show()`, nicht die fehlende Breitenkorrektur.
- Fix: wie im Anlegen-Test gegen die rechte Feldkante pruefen und zusaetzlich
  `assert bar._tab_container.maximumWidth() < 16777215`.

### [LOW-4] Der Guard in `_handle_scroll_key` ist zur Laufzeit weiterhin unerreichbar — der Test suggeriert das Gegenteil

- Datei: anvil/widgets/profile_bar.py:548-549, tests/test_profile_bar_inline_input.py:262-273
- Problem: jetzt mit echter Zustellung gemessen (`QApplication.sendEvent` an das fokussierte
  Feld): der anwendungsweite Filter sieht ausschliesslich `_FocusOutLineEdit/profileInlineInput`,
  `_handle_scroll_key` wird **0 mal** aufgerufen, die Pos1-Taste setzt nur den Cursor auf 0.
  Die QLineEdit nimmt die Taste an, es gibt keine Weiterreichung an den Streifen. Der Test
  ruft dagegen `eventFilter` mit einem Tab als `obj` auf, waehrend ein Feld offen ist —
  diesen Zustand gibt es im Betrieb nicht. Der Guard schadet nicht, der Testtext
  ("Home/End belong to the text as long as an input is open") behauptet aber eine Wirkung,
  die er nicht hat.
- Fix: Guard behalten, Docstring ehrlich formulieren ("defensiv: der Filter laeuft
  anwendungsweit").
- Zur Absicherung mitgemessen: mit Fokus auf einem Tab funktioniert Pos1/Ende ueber echte
  Event-Zustellung (Scrollwert springt auf das Maximum 2217). Die Funktion selbst ist also real.

### [LOW-5] Testhelfer `_visible_width` misst am falschen Widget — und trifft nur zufaellig

- Datei: tests/test_profile_bar_inline_input.py:52-57
- Problem: `field.parent().parent().parent()` mit dem Kommentar "strip -> viewport" landet
  tatsaechlich bei der **QScrollArea**, nicht beim Viewport (Kette gemessen:
  `_FocusOutLineEdit -> QWidget(_tabs_widget) -> qt_scrollarea_viewport -> QScrollArea`).
  Es geht heute gut, weil die Bereichs-Breite gleich der Viewport-Breite ist (626 == 626,
  kein Rahmen, keine sichtbare Bildlaufleiste). Sobald ein Rahmen oder eine Leiste dazukommt,
  misst der Helfer still daneben.
- Fix: `bar._scroll_area.viewport()` direkt uebergeben statt die Elternkette zu laufen.

### [LOW-6] `INLINE_INPUT_WIDTH = 200`: der Grund steht jetzt da, die Zahl aber nicht

- Datei: anvil/widgets/profile_bar.py:30-32
- Problem: Nachgemessen braucht der laengste Platzhalter (es) 141 px inklusive Rahmen. Der
  Kommentar nennt 139 px und begruendet damit "mehr als 140" — richtig, aber 200 sind 59 px
  mehr als noetig. Der Test dazu
  (`test_field_is_at_least_as_wide_as_the_longest_placeholder`, Zeile 114-120) behauptet im
  Docstring, er pruefe den Platzhalterbedarf, prueft aber `>= 200`, also die Konstante
  gegen sich selbst — mit einer neuen Magic Number statt `INLINE_INPUT_WIDTH`, das die
  Nachbartests benutzen.
- Fix: entweder den Test wirklich rechnen lassen
  (`QFontMetrics(edit.font()).horizontalAdvance(tr("placeholder.profile_name")) + 26`)
  oder ihn streichen; im Kommentar die 141 statt 139 nennen.

### [LOW-7] Verkleinert man das Fenster mit offenem Feld, verschwindet es wieder

- Datei: anvil/widgets/profile_bar.py:519-522 (`resizeEvent`)
- Problem: `resizeEvent` justiert nur die Verlaufskanten. Gemessen mit 30 Profilen, Feld offen:
  Fenster 1200 → sichtbar 200/200; Fenster auf 700 verkleinert → **sichtbar 0**; wieder auf
  1400 → 200. Gilt in beiden Themes. Dasselbe Krankheitsbild wie im gemeldeten Fehler, nur
  ueber einen anderen Ausloeser. Praktisch selten (man tippt selten und zieht gleichzeitig am
  Fenster), deshalb LOW.
- Fix: im `resizeEvent` das offene Feld nachziehen, analog zu `_update_container_width`:
  `field = self._inline_input or self._rename_input; if field: self._reveal_input(field)`.

### [LOW-8] Modul-Docstring der neuen Testdatei faellt aus dem Rahmen

- Datei: tests/test_profile_bar_inline_input.py:1-18
- Problem: 17 Zeilen mit Aufzaehlungsliste. Zum Vergleich alle anderen Test-Docstrings im
  Verzeichnis: `test_profile_bar_scrolling.py` 6, `test_plugins_txt_prefix_message.py` 7,
  `test_profile_create_feedback.py` 5, der Rest 1 Zeile. Es ist die einzige Testdatei im
  Projekt mit einer Aufzaehlung im Docstring (grep ueber `tests/`). Inhaltlich gut und
  menschlich formuliert (inkl. Zitat des Melders), nur eben lang.
- Fix: auf die Schwesterdatei-Laenge eindampfen, die drei Aufzaehlungspunkte in zwei Saetze.

---

## 3. tests/conftest.py — richtiger Ort, aber zwei Einschraenkungen

Der Ort stimmt: `tests/conftest.py` wird vor den Testmodulen importiert, die Variable steht
also fest, bevor `QApplication` entsteht. Die noqa-Kette in der neuen Datei ist weg, die
Schwesterdatei profitiert mit. Verhalten bestehender Tests: **unveraendert** — 237 passed
sowohl mit `QT_QPA_PLATFORM=wayland` (Marcs Umgebung) als auch mit `QT_QPA_PLATFORM=offscreen`.

Zwei Dinge, die der Kommentar "Ohne Display laufen die Qt-Tests sonst gar nicht erst an"
nicht abdeckt (kein Fehler, aber gut zu wissen):

1. In Marcs Shell ist `QT_QPA_PLATFORM=wayland` global gesetzt. `setdefault` greift dann
   nicht — die Tests laufen bei ihm weiter auf Wayland und oeffnen echte Fenster.
2. Ohne Display reicht die Zeile auf dieser Maschine trotzdem nicht: gemessen bricht der Lauf
   auch mit gesetztem `offscreen` bei `tests/test_base_migration_dialog.py` ab
   (`env -u DISPLAY -u WAYLAND_DISPLAY -u QT_QPA_PLATFORM python -m pytest tests/` → rc=1,
   Ausgabe `Gtk-WARNING: cannot open display`). Ursache ist `QT_QPA_PLATFORMTHEME=gtk3` in der
   Umgebung, nicht Qt selbst; mit zusaetzlich `-u QT_QPA_PLATFORMTHEME` laeuft alles durch.
   Wer die Zeile also fuer Headless-Betrieb gedacht hat, braucht dort auch
   `os.environ.setdefault("QT_QPA_PLATFORMTHEME", "")`.

In den GitHub-Workflows (appimage/flatpak/rpm/snap) laeuft kein pytest, die Datei aendert dort
also nichts.

---

## 4. Ausdrueckliche Entwarnungen (nachgeprueft, kein Befund)

- **Re-Entrancy beim Aufraeumen in `set_profiles`:** `field.setParent(None)` loest waehrend der
  Schleife `focus_lost` und damit `_cancel_inline_rename` aus (gemessen: 1 Rueckruf). Ergebnis
  bleibt sauber: `_rename_input`/`_rename_tab` None, 30 Tabs, alle sichtbar, keine Exception.
  Das doppelte `deleteLater()` ist in Qt folgenlos.
- **Verliert der Nutzer beim Aufraeumen Eingaben?** Alle sechs `set_profiles`-Aufrufer in
  mainwindow.py sind nutzergetrieben (`_apply_instance`, `_apply_bg3_instance`,
  `_on_profile_deleted`, `_on_dialog_profile_selected`, `_profile_creation_failed`,
  `reject_rename`). Kein Timer, kein Hintergrund-Refresh — ein offenes Feld wird nicht
  spontan weggeraeumt.
- **Endlosschleife durch `_update_container_width` → `_reveal_input` → `setValue`?** Nein.
  `valueChanged` haengt nur an `_update_fade_visibility`, und `_reveal_input` ruft die
  Breitenkorrektur nicht zurueck.
- **Uebersetzungen:** keine neuen sichtbaren Strings. `placeholder.profile_name` liegt in
  allen Locales inkl. ru vor.
- **Signal/Slot, Variable Scope:** `returnPressed`/`focus_lost` unveraendert verbunden,
  beide Felder bleiben Instanzvariablen, die Timer haben jetzt ein Kontextobjekt.
  Der Bestand `QTimer.singleShot(100, _delayed_select)` (Zeile 642) hat weiterhin keins —
  vorbestehend, ausserhalb dieses Diffs.
- **Qt-Antipatterns:** kein `setStyleSheet()` in neuem Widget-Code (nur die bestehenden
  Stilfunktionen), keine hardcoded Pfade, keine fehlenden Parents, `py_compile` sauber.
- **Docstring-Sprache:** deutsche Docstrings gibt es in der Datei schon
  (`apply_theme_metrics`, `_update_container_width`, `_on_drag_timer_timeout`) — die beiden
  neuen sind also kein Sprachbruch, nur laenger als der Bestand (siehe LOW-1).

---

## Ergebnis

**NEEDS FIXES** — wegen genau eines Punktes.

Blockierend ist der MEDIUM-Befund: die Pillen-Gruppe bleibt nach jedem Umbenennen zu breit
(gemessen 387 statt 260 px, mit HEAD tritt es nicht auf). Das ist eine sichtbare Regression,
die dieser Diff selbst einbaut, und sie kostet zwei Zeilen.

Alles andere ist LOW. Der Kern des Fixes ist jetzt sauber: alle drei Schutzmechanismen sind
belegt noetig, der Umbenennen-Pfad ist gleichgezogen, die Benennung und die Umlaute passen zum
Bestand, die conftest sitzt richtig, und die Tests sind — bis auf drei benannte Stellen —
scharf: 11 von 15 Mutationen werden von je einem Test gefangen.

Vom Bestand unterscheidbar bleibt der neue Code nur an einer Stelle: er ist dreimal so dicht
kommentiert (23,4 % gegen 7,7 %) und bringt zwei mehrzeilige Docstrings in eine Datei, die
sonst mit Einzeilern auskommt. Nach AI-Fingerabdruecken habe ich gezielt gesucht und keine
gefunden — Ton, Wortwahl, Gedankenstriche, Testnamen und das Melderzitat wirken menschlich.
