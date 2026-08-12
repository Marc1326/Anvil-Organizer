# Review Issue #103 — Runde 4 (Bugs, Logik, Regressionen)

Datum: 2026-08-08
Branch: `fix/issue-103`, Spitze unveraendert `08d8588` (nichts committet)
Geprueft: `git diff` auf `anvil/widgets/profile_bar.py` (+103/-9), `anvil/mainwindow.py` (+2/-2),
`tests/test_profile_create_feedback.py` (+25) sowie die unversionierten Dateien
`tests/conftest.py` und `tests/test_profile_bar_inline_input.py`.

Vorgaenger: `docs/review-103-bugs-runde3.md`, `docs/review-103-regression-runde3.md`
(beide gelesen, jeder Befund einzeln nachgeprueft).

## Messaufbau

- `QT_QPA_PLATFORM=offscreen`, echte `QApplication`, echte Ereignisschleifen
  (`QEventLoop` + `QTimer.singleShot`), echte `QFocusEvent`/`QMouseEvent`/`QKeyEvent`.
- Vergleichsbasis: `git show HEAD:anvil/widgets/profile_bar.py` als eigenes Modul
  (`importlib`) im selben Prozess geladen, damit ALT und NEU direkt nebeneinander messbar sind.
- 21 Messkripte (`m1_focusreasons.py` … `m21_realnames.py`) im Scratchpad.
- 20 Mutationen einzeln ins Produktivfile gesetzt, Suite jeweils gefahren, Datei danach
  aus einer Sicherung wiederhergestellt. Integritaet per md5 belegt
  (`430dbed5629282a6567772e0f6368c91`, `git status` am Ende identisch mit dem Anfang).
- `./restart.sh` wurde auftragsgemaess **nicht** ausgefuehrt. Keine Produktionsdaten beruehrt.
- `python -m py_compile` auf allen fuenf Dateien sauber. Im Projekt ist kein Linter/Typechecker
  konfiguriert (`pyproject.toml` ohne `[tool.ruff]`/`[tool.mypy]`, keine `pytest.ini`).
- Architektur-Doku `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md` gelesen.
  MO2-Referenz: `/home/mob/Projekte/mo2-referenz/` existiert auf diesem Rechner nicht
  (`ls` ausgefuehrt, kein Treffer) — Abgleich mit `profile.cpp` nicht moeglich. Fachlich
  nicht einschlaegig: der Diff bewegt ausschliesslich Qt-Widgets der Profilleiste.

---

## Teil 1 — Status der Befunde aus Runde 3

| # | Befund Runde 3 | Status | Beleg |
|---|---|---|---|
| N5 (MITTEL) | `_scroll_to_active_tab()` im Umbenennen-Pfad reisst die Leiste zum aktiven statt zum bearbeiteten Profil | **BEHOBEN** | Beide Aufrufe entfernt, `_scroll_to_active_tab` existiert im Code nicht mehr (Volltextsuche). 30 Profile, Tab 25 umbenannt: Ansicht bleibt bei Scroll 1916, Tab 25 **91/91 bzw. 106/106 px** sichtbar bei Breite 900/600/400, nach Enter **und** nach Escape. |
| N6 (HOCH, flaky Suite) | `pytest tests/` in 3 von 20 Laeufen rot, Datei allein praktisch immer rot | **BEHOBEN** | **volle Suite 30 Laeufe: 30 gruen** („247 passed, 1 skipped"), **Datei allein 25 Laeufe: 25 gruen** („28 passed"). Deckt Marcs 0/30. |
| N7 (NIEDRIG) | Schrumpf-Test prueft nur die Richtung | **BEHOBEN** | `test_container_shrinks_back_after_confirming_a_rename` prueft `== sizeHint().width() + 8`. Mutation `_update_container_width` aus `_finish_inline_rename` entfernt → gefangen. |
| N8 (NIEDRIG) | Kommentarzahl zu `INLINE_INPUT_WIDTH` falsch (141 px) | **NICHT behoben, dritte falsche Zahl** | siehe Befund B2. |
| Rest 6 | `QTimer.singleShot(100, _delayed_select)` ohne Kontextobjekt (`:644`) | unveraendert (Bestand aus HEAD) | Stilhinweis, kein Blocker |
| Rest 7 | „redundanter" Feld-Guard in `_handle_scroll_key` | unveraendert — und **nicht** redundant | Mutation Guard entfernt → `test_scroll_keys_are_left_alone_while_typing_a_name` faellt |
| Rest T4 | keine Aufraeum-Fixture | **fuer die neue Datei behoben**, in `test_profile_create_feedback.py` weiter offen | dort wird die Leiste nie `show()`n → keine Fensteraktivierung, kein Schaden messbar |
| Rest T5 | Docstring „35 px of 140" | unveraendert, beschreibt den historischen Bug | vertretbar |
| Regression Runde 3, MITTEL | von Hand gewaehlte Scrollposition wird verworfen | **BEHOBEN** | `_restore_scroll()`: Start 0/700/Maximum × Breiten 900/600/400 → in **allen 9 Faellen** exakt der Ausgangswert wieder da (HEAD hatte gar nicht gescrollt, also den Feldbug). |
| Regression Runde 3, NIEDRIG (mapTo-Warnung) | nur kuenstlich erreichbar | unveraendert | 11 normale Ablaeufe mit `qInstallMessageHandler`: **null Qt-Meldungen, null Ausnahmen** |

---

## Teil 2 — Die fuenf gestellten Fragen

### 1. Ist die Suite jetzt stabil?

**Ja.**

| Lauf | Wiederholungen | rot |
|---|---|---|
| `pytest tests/ -q` | **30** | **0** („247 passed, 1 skipped", 5,10–5,32 s) |
| `pytest tests/test_profile_bar_inline_input.py -q` | **25** | **0** („28 passed") |

Damit ist der Zustand aus Runde 3 (3/20 bzw. 13/38 rot, Datei allein immer rot) beendet.
Beide Ursachen wirken; die Fixture allein haette nicht genuegt: mit wieder unbedingtem
`focus_lost` (Mutation `focusreason`) faellt sofort
`test_switching_windows_keeps_the_half_typed_name`.

### 2. Nebenwirkungen des Eingriffs in `_FocusOutLineEdit.focusOutEvent`

Zehn Szenarien, je ein eigener Prozess (damit die Fensteraktivierung eindeutig ist),
Leiste als Kind eines `QMainWindow` wie in der App, Feld nachweislich mit Fokus
(`hasFocus() == True`), NEU gegen HEAD:

| Vorgang | FocusReason | HEAD | NEU |
|---|---|---|---|
| Klick auf ein anderes Widget im Fenster | `MouseFocusReason` | schliesst | **schliesst** |
| Tabulator weg | `TabFocusReason` | schliesst | **schliesst** |
| `clearFocus()` (der Weg des app-weiten Ereignisfilters) | `OtherFocusReason` | schliesst | **schliesst** |
| Kontextmenue / Popup | `PopupFocusReason` | schliesst | **schliesst** |
| `bar.hide()` | `TabFocusReason` | schliesst | **schliesst** |
| `set_profiles()` bei offenem Feld | `TabFocusReason` | — | Aufraeumblock greift, `inline`/`rename`/`rename_tab` = `None`, 0 versteckte Tabs |
| Fenster deaktiviert (Alt-Tab) | `ActiveWindowFocusReason` | **verwirft die Eingabe** | **bleibt offen, Text erhalten** ← gewollt |
| modaler Dialog geoeffnet | `ActiveWindowFocusReason` | verwirft | bleibt offen; nach Schliessen des Dialogs Feld offen **und wieder fokussiert** |
| Fenster minimiert | (kein Ereignis) | bleibt offen | bleibt offen (unveraendert) |
| **Fenster geschlossen** | `ActiveWindowFocusReason` | schliesst das Feld | **Feld bleibt offen** ← einzige ungeplante Abweichung, siehe B4 |

**Kein Feld bleibt auf einem erreichbaren Weg haengen.** Entscheidend dafuer ist, dass der
app-weite Ereignisfilter (`profile_bar.py:955-961`) bei **jedem** `MouseButtonPress` irgendwo
in der Anwendung explizit `clearFocus()` aufruft — das erzeugt `OtherFocusReason` und ist von
der neuen Ausnahme nicht betroffen. Gemessen: Klick auf einen fremden Knopf schliesst in NEU
wie in HEAD das Anlegen- **und** das Umbenennen-Feld, der versteckte Tab kommt zurueck
(`Tab25 sichtbar=True`). Der Nutzen bleibt also genau da, wo er gemeint ist: beim Wechsel in
eine **fremde Anwendung** (dort entstehen keine Mausereignisse in Anvil).

Ende-zu-Ende gegengeprueft: „+" druecken, Text tippen, in ein anderes Fenster wechseln,
zurueckkommen, Enter → Profil „Spaeter" wird angelegt, keine Qt-Meldung. In HEAD war der
Text zu diesem Zeitpunkt weg. Das war wirklich ein Produktivfehler.

### 3. `_restore_scroll()` — Randfaelle

| Fall | Ergebnis |
|---|---|
| Profilzahl schrumpft (30 → 3) waehrend das Feld offen ist | Merker 1900, `set_profiles(3)` → Endwert **0**, `min`/`max` = 0/0, im Bereich, `inline`/`rename` = `None`, 0 versteckte Tabs, keine Ausnahme |
| Fenster waehrend des offenen Feldes von 600 auf 4000 px (Maximum faellt auf 0) | Merker 2517 → nach Escape **0**, im Bereich |
| dreimal hintereinander anlegen+abbrechen (0/1200/2100) | jedes Mal exakt der Ausgangswert |
| `_restore_scroll()` ohne vorheriges Oeffnen direkt gerufen | springt auf den `__init__`-Wert **0** — ueber die Oberflaeche **nicht erreichbar**, weil der einzige Aufrufer `_cancel_inline_create` ein offenes Feld voraussetzt und `_start_inline_create` den Merker immer setzt. Kein `AttributeError` (Feld in `__init__:317` vorbelegt). |
| Umbenennen-Pfad | setzt den Merker **nicht** und ruft `_restore_scroll` **nicht** — die Ansicht bleibt beim bearbeiteten Tab. Absicht, deckt sich mit N5. |

Das `min(..., scrollbar.maximum())` ist dabei **wirkungslos**: `QScrollBar.setValue` klemmt
selbst (gemessen: `setValue(999999)` → 2217, `setValue(-500)` → 0). Siehe B5.

### 4. Sind die beiden entfernten `_scroll_to_tab`-Aufrufe verzichtbar?

Gemessen: 30 Profile, Tab-Index 1/25/29, Fensterbreiten 900/600/400 (Viewport 626/326/126),
neuer Name kurz („Ab") und lang, Enter und Escape — 36 Kombinationen, jeweils nachdem der
`_delayed_select`-Timer aus `set_profiles` abgelaufen war.

**Fast ueberall ja.** In 30 von 36 Kombinationen bleibt der bearbeitete Tab **vollstaendig**
sichtbar; in den uebrigen 6 ist der Tab breiter als der Viewport und es wird das Maximum
gezeigt (126 von 126 px) — besser geht nicht.

**Eine Ausnahme, und die ist echt:** wird auf einen Namen umbenannt, dessen Tab **breiter als
das 200 px breite Eingabefeld** wird, haengt der Ueberschuss rechts aus dem Bild:

| neuer Name | Tab | sichtbar | mit `_scroll_to_tab(tab)` |
|---|---|---|---|
| „Nur Grafik ohne Gameplay" (24 Zeichen) | 195 px | 195 (voll) | 195 |
| „Ultra Realismus Grafikpaket 2026" (32 Zeichen) | 235 px | **200 → 35 px abgeschnitten** | **235 (voll)** |
| „Ein sehr langer Profilname 123" bei 900 px | 220 px | **200 → 20 px abgeschnitten** | **220 (voll)** |

Bei Breite 900 ist der Viewport 626 px — der Tab wuerde also bequem passen, das Abschneiden
ist vermeidbar. Der Mutationstest hat das nicht gezeigt, weil kein Test mit einem so langen
Namen arbeitet. Zum Vergleich HEAD: dort waren im selben Fall nur 141 von 220 px sichtbar.
**Also keine Regression gegenueber HEAD, aber die Aussage „nachweisbar wirkungslos" trifft
fuer `_finish_inline_rename` nicht zu.** Fuer `_cancel_inline_rename` trifft sie zu: dort
behaelt der Tab seinen alten Text und ist wegen `max(200, tab.width())` nie breiter als das
Feld, das eben noch an derselben Stelle stand.

### 5. Vergleich gegen HEAD

Elf Ablaeufe, NEU und HEAD im selben Prozess, nach jedem Schritt Kapselbreite gegen
`sizeHint+8`, aktiver Tab gegen seine Breite, Scrollwert gegen `[min, max]`, Feldzeiger,
versteckte Tabs:

| Ablauf | NEU | HEAD |
|---|---|---|
| Start | Kapsel ok, aktiv 80/80, Scroll 0 | identisch |
| anlegen + Enter | Kapsel ok, aktiv 59/59, Scroll 2276/2277 | identisch |
| anlegen + Escape | Kapsel ok, aktiv 80/80, Scroll 0 | identisch |
| umbenennen + Enter | **Kapsel 2836/2836 ok**, Ansicht bleibt beim bearbeiteten Tab | **Kapsel 2851/2836 ABW**, Ansicht beim aktiven Tab |
| umbenennen + Escape | Kapsel ok, Ansicht bleibt beim bearbeiteten Tab | Kapsel ok, Ansicht beim aktiven Tab |
| Profil per Klick wechseln | aktiv 93/93, Scroll 539 | identisch |
| Instanz wechseln (30 → 5) | Kapsel 411/411, aktiv 70/70 | identisch |
| Profil geloescht | Kapsel 2757/2757 | identisch |
| Fenster 500 → 1500 | Kapsel ok, Scroll im Bereich | identisch |
| Pos1/Ende | Scroll 0 bzw. Maximum | identisch |
| Drag & Drop | Kapsel ok, aktiv 80/80 | identisch |

Der einzige inhaltliche Unterschied ist gewollt: nach dem Umbenennen bleibt die Ansicht beim
**bearbeiteten** Profil statt beim **aktiven**. Genau das war die Forderung aus N5. Das aktive
Profil kann dabei aus dem Bild wandern (gemessen 0 von 80 px) — das ist die Kehrseite und
sollte nicht in der naechsten Runde erneut umgedreht werden.

Ausserdem behebt NEU eine ALT-Abweichung: HEAD liess die Pillen-Kapsel nach dem Umbenennen
mit 2851 statt 2836 px stehen.

---

## Teil 3 — Mutationstests (20 Mutationen)

| Mutation | Ergebnis | ausloesender Test |
|---|---|---|
| `focus_lost` wieder unbedingt (Ausnahme entfernt) | gefangen | `test_switching_windows_keeps_the_half_typed_name` |
| `_restore_scroll()` aus `_cancel_inline_create` entfernt | gefangen | `test_cancelling_puts_the_view_back_where_it_was` |
| Merker `_scroll_before_input` nicht setzen | gefangen | dito |
| `or obj is self._btn_add` entfernt | gefangen | `test_the_wheel_works_over_the_add_button_too` |
| `edit.show()` im Anlegen entfernt | gefangen (2 Tests) | `…classic_theme_too`, `…does_not_clip_the_new_field` |
| `edit.show()` im Umbenennen entfernt | gefangen | `test_container_does_not_clip_the_rename_field` |
| `_update_container_width()` aus `_cancel_inline_rename` | gefangen | `test_container_shrinks_back_after_renaming` |
| `_update_container_width()` aus `_finish_inline_rename` | gefangen | `test_container_shrinks_back_after_confirming_a_rename` |
| `_reveal_input` aus `_update_container_width` | gefangen | `test_a_pending_tab_click_does_not_scroll_the_field_away` |
| Feld-Guard in `_scroll_to_tab` entfernt | gefangen | `test_selecting_a_profile_does_not_scroll_the_field_away` |
| Aufraeumblock in `set_profiles` entfernt | gefangen | `test_reloading_the_profiles_drops_an_open_field` |
| `QTimer.singleShot(0, …)` im Anlegen entfernt | gefangen (4 Tests) | u. a. `…fully_visible_with_many_profiles` |
| `QTimer.singleShot(0, …)` im Umbenennen entfernt | gefangen (3 Tests) | u. a. `test_the_renamed_tab_stays_in_view` |
| Guard in `_reveal_input` entfernt | gefangen | `test_reveal_ignores_a_field_that_was_already_dismissed` |
| Feld-Guard in `_handle_scroll_key` entfernt | gefangen | `test_scroll_keys_are_left_alone_while_typing_a_name` |
| Modifier-Guard in `_handle_scroll_key` entfernt | gefangen | `test_scroll_keys_with_a_modifier_are_passed_on` |
| `INLINE_INPUT_WIDTH` auf 140 zurueck | gefangen | `test_field_fits_the_longest_placeholder_of_any_language` |
| Name im Signal durch `"{name}"` ersetzt | gefangen | `test_the_rejection_carries_the_name_the_message_needs` |
| Klemmung in `_restore_scroll` entfernt | **nicht gefangen** | — (harmlos, siehe B5) |
| `_reveal_input` aus `resizeEvent` entfernt | **nur in 8 von 12 Laeufen gefangen** | `test_resizing_keeps_an_open_field_in_view`, siehe B3 |

18 von 20 sauber gefangen, und — anders als in Runde 3 — **ohne** Kollateraltreffer bei
unbeteiligten Tests. Die Zustandskopplung, die Runde 3 bemaengelt hat, ist mit der Fixture weg.

---

## Teil 4 — Neue Befunde

### [MITTEL] B1 — Der neue Platzhalter-Test faellt, wenn pytest nicht im Projektwurzelverzeichnis laeuft

- Datei: `tests/test_profile_bar_inline_input.py:131` — `locales = _Path("anvil/locales")`
- Der Pfad ist relativ zum **Arbeitsverzeichnis**, nicht zur Testdatei. Aus einem anderen
  Verzeichnis gestartet liefert `glob("*.json")` nichts und `max()` bricht ab:

      cd /tmp/… && pytest "/home/mob/Projekte/Anvil Organizer/tests/test_profile_bar_inline_input.py" -q
      → ValueError: max() iterable argument is empty
      → 1 failed, 27 passed

- Das ganze uebrige Projekt macht es anders: `tests/test_translations.py:7`,
  `tests/test_profile_create_feedback.py:12`, `tests/test_aur_packaging.py:7`,
  `tests/test_skyrimse_skse.py:10` und `tests/test_game_ghostreconbreakpoint.py:186`
  benutzen alle `Path(__file__).parents[1]`. Dieser Test ist der einzige Ausreisser.
- Fix: `_Path(__file__).resolve().parents[1] / "anvil" / "locales"`.

### [NIEDRIG] B2 — Die 158 px im Kommentar sind mit der falschen Schrift gemessen

- Dateien: `anvil/widgets/profile_bar.py:31-33` und der Docstring
  `tests/test_profile_bar_inline_input.py:123`.
- Nachgemessen. Das Feld erzwingt per Stylesheet `font-size: 13px`; sein `fontMetrics()`
  liefert damit (Roboto Flex 13 px, unabhaengig von `QT_FONT_DPI`/`QT_SCALE_FACTOR`, je fuenf
  Kombinationen geprueft):

  | Sprache | advance | advance+26 | gerendert benoetigt |
  |---|---|---|---|
  | de | 77 | 103 | 107 |
  | en | 88 | 114 | 119 |
  | **es** | **115** | **141** | **145** |
  | fr | 95 | 121 | 126 |
  | it | 91 | 117 | 122 |
  | pt | 102 | 128 | 133 |
  | ru | 97 | 123 | 128 |

  „gerendert benoetigt" ist die tatsaechliche Tinte im gerenderten Feld
  (`grab()` → Pixelvergleich mit leerem Platzhalter, `devicePixelRatio` 1,75 herausgerechnet),
  rechter Rand so gross wie der gemessene linke (16 px, nicht 13 — QLineEdit legt intern noch
  2 px drauf).
- Die genannten Zahlen (de 115, en 127, es 158, fr 136, it 131, pt 144, ru 138) sind exakt die
  des **Standard-App-Fonts** (Roboto Flex **11 pt ≈ 15 px**) plus 26 — also mit einem Feld
  **ohne** das Inline-Stylesheet gemessen. Belegt: `QFont("Roboto Flex")` mit `setPixelSize(15)`
  reproduziert die sieben Zahlen ziffergenau.
- Folge: Der Kommentar nennt eine um ~12 % zu grosse Zahl, und der Docstring des Tests
  behauptet 158 px, waehrend der Test daneben 141 px ausrechnet. Funktional harmlos —
  `INLINE_INPUT_WIDTH = 200` reicht mit **jeder** der drei Zahlen (141 / 145 / 158).
- Nach drei Runden mit drei verschiedenen Zahlen (141 → 132 → 158): am besten die absolute
  Zahl aus dem Kommentar streichen und nur schreiben, dass Spanisch der laengste Platzhalter
  ist und der Test die Breite absichert. Sonst wird in Runde 5 die vierte Zahl gemessen.

### [NIEDRIG] B3 — Der Resize-Test erkennt den Defekt nur in zwei Dritteln der Laeufe

- Datei: `tests/test_profile_bar_inline_input.py:317-325`
- Mit entferntem `_reveal_input` im `resizeEvent` (Mutation) gemessen:
  **volle Suite 8 von 12 Laeufen rot, Datei allein 8 von 12 rot.** In den uebrigen Laeufen
  laeuft der Test gruen, obwohl der Produktivcode kaputt ist.
- Der Produktivcode selbst wirkt zuverlaessig — isoliert gemessen, 900 → 600/400 px:
  ohne die Zeile **0 von 200 px** sichtbar, mit ihr **200 von 200** bzw. **126 von 200**
  (Viewport 126). Der Fehler liegt also im Test, nicht im Code.
- Auffaellig: eine Kopie des Tests, die vor der Zusicherung einmal zusaetzlich
  `_visible_width(...)` liest (mein Diagnose-Print), erkennt die Mutation **8 von 8** Mal.
  Das riecht nach einer verspaetet aktivierten Geometrie.
- Mit korrektem Code ist der Test stabil gruen (30 + 25 Laeufe), er blockiert also nichts.
  Er gibt aber falsche Sicherheit.
- Fix-Vorschlag: nach `bar.resize(600, 60)` ein `_settle()` statt nur `processEvents()`, und
  zusaetzlich zusichern, dass die Groessenaenderung ueberhaupt angekommen ist
  (`bar._scroll_area.viewport().width() < vorher`).

### [NIEDRIG] B4 — Nach `close()` des Fensters bleibt ein offenes Feld stehen

- Datei: `anvil/widgets/profile_bar.py:268-272`
- `win.close()` liefert `ActiveWindowFocusReason`, also faellt der Abbruch jetzt weg:
  `_inline_input` bleibt gesetzt, beim Umbenennen bleibt zusaetzlich der Tab versteckt.
  In HEAD wurde beides aufgeraeumt.
- Praktisch folgenlos: Die Leiste wird in der Anwendung nie versteckt oder erneut gezeigt
  (Volltextsuche nach `_profile_bar.hide/show/setVisible/close` → kein Treffer), und
  `MainWindow.closeEvent` (`mainwindow.py:6972`) haengt nicht am Feldzustand. Gemessen:
  Fenster mit offenem Feld schliessen, dann `deleteLater()` + 300 ms Schleife → keine
  Qt-Meldung, kein `RuntimeError`.
- Nur der Vollstaendigkeit halber notiert. Wer es sauber will, prueft zusaetzlich
  `self.window().isVisible()`.

### [NIEDRIG] B5 — Die Klemmung in `_restore_scroll` ist toter Code

- Datei: `anvil/widgets/profile_bar.py:830-833`
- `QScrollBar.setValue` klemmt selbst (gemessen: 999999 → 2217, −500 → 0). Das
  `min(self._scroll_before_input, scrollbar.maximum())` aendert nie ein Ergebnis; die Mutation
  ohne `min()` faellt in keinem Test auf und in keiner meiner Randfallmessungen auf.
- Harmlos und lesbar-defensiv. Nur zu wissen: der Ausdruck ist von Tests **nicht** gedeckt.

### [INFO] B6 — `_scroll_before_input` gilt nur fuer den Anlegen-Pfad

Geschrieben wird der Merker ausschliesslich in `_start_inline_create` (`:742`), gelesen
ausschliesslich ueber `_cancel_inline_create` → `_restore_scroll` (`:828`). Der
Umbenennen-Pfad laesst die Ansicht bewusst beim bearbeiteten Tab. Der allgemeine Name legt
etwas anderes nahe; wer spaeter `_restore_scroll()` in den Umbenennen-Pfad haengt, restauriert
einen Wert aus einer voellig anderen Operation. Ein Satz Kommentar an `_restore_scroll` oder
ein Name wie `_scroll_before_create` wuerde das ausschliessen.

### [INFO] B7 — `_bar.made` als Ablage

`tests/test_profile_bar_inline_input.py:33` haengt die Liste als Attribut an die Funktion
`_bar`. Funktioniert, weil die Fixture `autouse` ist; ohne sie waere es ein `AttributeError`.
Ein normales Fixture-Argument waere die ueblichere Form. Kein Fehler.

---

## Teil 5 — Ausdruecklich geprueft und unauffaellig

| Punkt | Ergebnis |
|---|---|
| Qt-Meldungen / Ausnahmen | 11 vollstaendige Ablaeufe (anlegen Enter/Escape/ungueltig, umbenennen Enter/Escape, `set_profiles` bei beiden offenen Feldern, Fensterwechsel + Enter, Fenster schliessen + zerstoeren, 5× Groesse aendern, Leiste mit offenem Feld per `shiboken6.delete` zerstoeren) → **null Meldungen, null Ausnahmen** |
| Signal `profile_create_rejected` | genau ein Empfaenger (`mainwindow.py:260-261` → `_on_profile_create_rejected`, zweistellig, `:4343`), Sender zweistellig (`:793`, `:799`), Test verbindet zweistellig |
| `tr()` mit ueberzaehligem `name=` | unkritisch, `str.format` ignoriert es; Format-Injection ausgeschlossen (`{name}`, `{0}`, `{`, `}`, `%s`, `a{b}c` kommen woertlich an) |
| Locale-Schluessel | keine neuen Schluessel; `toast.profile_exists` / `toast.profile_invalid_name` in allen 7 Locales vorhanden, per Bestandstest `test_feedback_messages_exist_in_every_language` abgesichert |
| Importe | `QKeyEvent` ergaenzt und benutzt; keine ungenutzten Zusaetze |
| `setStyleSheet` in neuen Widgets | keine neuen Aufrufe, nur Bestand |
| hartcodierte Pfade | keine (Ausnahme: der Testpfad aus B1) |
| Ereignisfilter-Reihenfolge | KeyPress-Zweig steht hinter Maus/Rad und vor der Drag-Logik, wirkt nur bei `_is_own_scroll_target(obj)`, Drag & Drop unveraendert |
| Cover-Bilder / redprelauncher / REDmod / BG3 | nicht beruehrt |
| Architektur-Regeln 1–5 | nicht beruehrt: keine Mod-Dateien, kein `.mods/`, keine Frameworks, keine `active_mods.json`, keine `modlist.txt`, kein Deploy/Purge. Der Diff bewegt Qt-Widgets der Profilleiste plus einen Toast-Text. |
| Architektur-Doku gelesen | ja |
| MO2-Referenz | Verzeichnis existiert nicht (geprueft) — Abgleich nicht moeglich, fuer eine Scroll-/Fokusaenderung auch nicht einschlaegig |
| Arbeitsstand | unveraendert: `git status` am Ende identisch, md5 von `profile_bar.py` wie vor den Mutationen, Branchspitze weiter `08d8588` |

---

## Ergebnis

**NEEDS FIXES — aber nur noch Kleinkram; der Produktivcode ist sauber.**

Was jetzt sitzt: Die Suite ist stabil (30/30 und 25/25 gruen). Der Eingriff in
`focusOutEvent` behebt einen echten Produktivfehler und hat **keine** schaedliche
Nebenwirkung — der Abbruch per Mausklick laeuft ueber `clearFocus()` im app-weiten
Ereignisfilter und ist von der Ausnahme nicht betroffen; nur der Fall „Fenster geschlossen"
raeumt nicht mehr auf, was in der Anwendung nirgends erreichbar ist. `_restore_scroll()` haelt
allen Randfaellen stand (schrumpfende Profilzahl, wegfallendes Maximum, Mehrfachnutzung) und
loest den MITTEL-Punkt aus Runde 3 messbar. Die entfernten `_scroll_to_tab`-Aufrufe sind in 30
von 36 gemessenen Kombinationen tatsaechlich verzichtbar, und in den restlichen 6 ist der
Viewport schuld. 18 von 20 Mutationen werden gefangen, diesmal ohne Kollateraltreffer.

Offen sind:

1. **B1 (MITTEL)** — `tests/test_profile_bar_inline_input.py:131` benutzt einen Pfad relativ
   zum Arbeitsverzeichnis und faellt reproduzierbar, sobald pytest von anderswo gestartet
   wird. Einzeiler, das ganze restliche Projekt macht es schon richtig.
2. **B2 (NIEDRIG)** — die 158 px im Kommentar und im Test-Docstring sind mit dem
   Standard-App-Font (15 px) gemessen, nicht mit den 13 px des Feldes; richtig sind 141 px
   (advance+26) bzw. ~145 px gerendert. Dritte falsche Zahl in drei Runden — besser ohne Zahl.
3. **B3 (NIEDRIG)** — `test_resizing_keeps_an_open_field_in_view` erkennt den zugehoerigen
   Defekt nur in 8 von 12 Laeufen.
4. **Praezisierung zur Vorgabe:** Die Aussage, die entfernten `_scroll_to_tab`-Aufrufe seien
   „nachweisbar wirkungslos", gilt fuer `_cancel_inline_rename`, **nicht** fuer
   `_finish_inline_rename`: bei einem neuen Namen ab ~28 Zeichen bleiben 20–35 px des Tabs
   rechts abgeschnitten, obwohl der Viewport Platz haette. Kein Blocker (HEAD war schlechter),
   aber es ist eine bewusste Entscheidung, nicht ein Beweis.

B4 bis B7 sind Notizen ohne Handlungsdruck. Sind B1 bis B3 erledigt, ist der Stand aus meiner
Sicht bereit fuer den Commit — der Deploy-/plugins.txt-Punkt aus #103 bleibt davon unberuehrt
und weiterhin offen (bewusst, siehe `docs/review-103-issuestand-runde3.md`).
