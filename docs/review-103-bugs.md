# Review Issue #103 — Inline-Eingabefeld der Profil-Leiste

Datum: 2026-08-08
Branch: `fix/issue-103`
Geprueft: `git diff` auf `anvil/widgets/profile_bar.py` + neue Datei `tests/test_profile_bar_inline_input.py`

## Vorgehen

- Kompletten Diff und die gesamte Datei `anvil/widgets/profile_bar.py` gelesen
- Volle Testsuite ausgefuehrt: **229 passed, 1 skipped**
- Vier Mutationen in den Fix eingebaut und geprueft, ob die neuen Tests sie fangen (Ergebnis unten)
- Verhalten der Umbenennen-Strecke, der `set_profiles()`-Kollision und der 100-ms-Verzoegerung
  aus `set_profiles()` mit Offscreen-Qt nachgemessen (echte Pixelwerte, keine Vermutungen)
- Lebensdauer von `edit`/`self` im QTimer-Lambda mit `shiboken6.delete()` erzwungen geprueft

## Bewertung des Fixes

Die drei Bausteine des Fixes sind sachlich richtig und loesen den gemeldeten Fall:

- `edit.show()` ist noetig, weil `QLayout::sizeHint()` versteckte Widgets ueberspringt
  (`QWidgetItem::isEmpty()`); ohne das misst `_update_container_width()` die alte Breite.
- Der Verzicht auf `ensureWidgetVisible()` ist richtig begruendet — Qt nimmt bei einem
  QLineEdit das Cursor-Rechteck.
- Der `QTimer.singleShot(0, ...)`-Umweg ist noetig, weil der Scrollbereich unmittelbar
  nach `insertWidget` noch nicht steht.

Gemessen mit 30 Profilen: vorher 0 px sichtbar, nachher 200 von 200 px.

Trotzdem: der Fix deckt nur die Anlege-Strecke ab und laesst drei Loecher offen.

---

## Findings

### [MEDIUM] 1 — Umbenennen hat exakt denselben Fehler, wurde nicht mitgefixt

- Datei: `anvil/widgets/profile_bar.py:811-845` (`_start_inline_rename`)
- Problem: Die Methode macht genau das, was in `_start_inline_create` als Ursache
  identifiziert wurde — nur eben unrepariert:
  - kein `edit.show()`
  - kein `_update_container_width()` (der `maximumWidth` des Containers bleibt auf dem
    Wert, der noch aus der Zeit vor dem Feld stammt)
  - kein Scrollen, damit das Feld ganz sichtbar wird
  - die Breite ist weiterhin hart `max(140, tab.width())` — die neue Konstante
    `INLINE_INPUT_WIDTH` wird hier nicht benutzt
- Nachgemessen (modernes Theme, 30 Profile, letzten Tab per Doppelklick umbenennen,
  Container-Breite realistisch nach Ablauf von `_delayed_select`):
  Feld 140 px breit, davon **124 px sichtbar — 16 px abgeschnitten**.
  Der Tab selbst war vorher zu 100 % sichtbar (90 von 90 px), das Feld ist breiter als
  der Tab, den es ersetzt, und laeuft deshalb rechts aus dem Sichtfenster.
- Fix: In `_start_inline_rename` nach `insertWidget` ebenfalls `edit.show()`,
  `self._update_container_width()` und `QTimer.singleShot(0, ...)` auf eine gemeinsame
  Reveal-Hilfsmethode (die dann auch `_rename_input` beruecksichtigt).
  `_reveal_inline_input` liesse sich dazu auf ein beliebiges Feld verallgemeinern,
  z. B. `_reveal_field(edit, expected)`.

### [MEDIUM] 2 — `_delayed_select` scrollt 100 ms spaeter wieder weg

- Datei: `anvil/widgets/profile_bar.py:620-628` gegen `:741`
- Problem: `set_profiles()` plant `QTimer.singleShot(100, _delayed_select)`.
  `_delayed_select` ruft `_select_profile()` und damit `_scroll_to_tab()` →
  `ensureWidgetVisible(aktiver Tab)`. Wird das Eingabefeld innerhalb dieser 100 ms
  geoeffnet, laeuft erst der Reveal (bei 0 ms) und danach das Zurueckscrollen auf den
  aktiven Tab (bei 100 ms). Weder `_delayed_select` noch `_select_profile` fragen
  `self._inline_input` ab.
- Nachgemessen: direkt nach dem Reveal **200 px sichtbar**, nach `_delayed_select`
  wieder **0 px** — also exakt der Zustand aus dem Issue.
- Erreichbarkeit ehrlich eingeschaetzt: das Zeitfenster ist nur 100 ms breit und
  beginnt bei jedem `set_profiles()` (Programmstart, Instanzwechsel, Profil geloescht,
  Profil angelegt, Menue "Neu laden"). Ein Nutzer muesste sehr schnell auf "+" klicken.
  Selten, aber die Regression ist genau die, die hier behoben werden soll, und der Fix
  ist eine Zeile.
- Fix: In `_delayed_select` das `_select_profile()`/`_scroll_to_tab()` ueberspringen
  bzw. das Scrollen unterdruecken, solange `self._inline_input is not None`.
  Alternativ am Ende von `_delayed_select` `self._reveal_inline_input(self._inline_input)`
  nachziehen.

### [MEDIUM] 3 — `set_profiles()` raeumt ein offenes Eingabefeld nicht ab, "+" wird tot

- Datei: `anvil/widgets/profile_bar.py:583-596` (`set_profiles`), Wechselwirkung mit `:713-716`
- Problem: `set_profiles()` leert das Layout mit
  `while self._tabs_layout.count(): item = self._tabs_layout.takeAt(0)`.
  Ein offenes Inline-Feld wird dabei aus dem Layout genommen, aber **nicht geloescht,
  nicht neu verortet, und `self._inline_input` wird nicht zurueckgesetzt.**
- Nachgemessen: nach einem externen `set_profiles()` bei offenem Feld gilt
  `_tabs_layout.indexOf(edit) == -1`, `edit.parent() is _tabs_widget`,
  `edit.isVisible() == True`, `_inline_input is not None`.
  Jeder weitere Klick auf "+" faellt danach in `if self._inline_input is not None: return`
  — der Knopf reagiert nicht mehr. Das ist dieselbe Aussenwirkung wie im Issue
  ("ich kann kein Profil anlegen").
- Selbstheilung: Das Feld behaelt den Fokus, also raeumt der naechste Mausklick
  irgendwo den Zustand ueber `clearFocus()` → `focus_lost` → `_cancel_inline_create` auf
  (verifiziert). Verliert das Feld den Fokus vorher anderweitig, bleibt der Zustand haengen.
- Zusaetzlich: Der noch eingereihte `_reveal_inline_input(edit)` laeuft in diesem Fall
  durch (die Pruefung `edit is not self._inline_input` greift nicht!) und misst ein
  Widget, das nicht mehr im Layout haengt — die Leiste scrollt an eine willkuerliche Stelle.
- Vorbestehend, nicht durch diesen Diff eingefuehrt — aber durch den neuen Reveal
  bekommt der Zustand jetzt eine zusaetzliche sichtbare Auswirkung.
- Fix: `set_profiles()` beginnt mit `self._cancel_inline_create(self._inline_input)`
  bzw. `self._cancel_inline_rename(...)`, falls offen.

### [LOW] 4 — Pos1/Ende vom Ziffernblock werden nicht erkannt

- Datei: `anvil/widgets/profile_bar.py:543`
- Problem: `if event.modifiers() != Qt.KeyboardModifier.NoModifier: return False`.
  Qt setzt bei Tasten des Ziffernblocks `Qt.KeyboardModifier.KeypadModifier`.
  Pos1/Ende ueber Num-7 / Num-1 (NumLock aus) tragen damit einen Modifier und werden
  abgelehnt, obwohl der Nutzer nichts zusaetzlich gedrueckt hat.
- Fix: Statt auf `NoModifier` zu vergleichen gezielt auf die stoerenden Modifier pruefen:
  `if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | ShiftModifier | AltModifier | MetaModifier): return False`.

### [LOW] 5 — Feld breiter als Sichtfenster: linke Kante bleibt draussen

- Datei: `anvil/widgets/profile_bar.py:764-767`
- Problem: Der erste Zweig richtet immer die **rechte** Kante aus. Ist das Feld breiter
  als das Sichtfenster, verschwindet die linke Kante — und damit Textcursor und
  Platzhaltertext, also genau das, worauf der Nutzer schaut.
- Nachgemessen bei 68 px Sichtfenster: Feld 200 px, sichtbar 68 px, linker Rand bei
  Offset **-132**.
- Erreichbarkeit: Das Hauptfenster hat `setMinimumSize(1000, 650)`, die Leiste sitzt aber
  im linken Bereich eines `QSplitter` (mainwindow.py:230/267) ohne eigene Mindestbreite,
  und im modernen Theme teilt sich der Container die Breite mit einem `addStretch(1)`.
  Sehr schmal gezogen ist der Fall also erreichbar, im Alltag aber unwahrscheinlich.
- Fix: `if edit.width() >= sicht: bar.setValue(max(bar.minimum(), links))` vorziehen.

### [LOW] 6 — `QTimer.singleShot` ohne Kontext-Objekt (geprueft: aktuell kein Bug)

- Datei: `anvil/widgets/profile_bar.py:741`
- Geprueft, weil ausdruecklich gefragt: Das Lambda haelt `self` und `edit` als
  Python-Referenzen; die C++-Objekte koennten aber schon weg sein.
  - `edit` geloescht: unkritisch, `edit is not self._inline_input` vergleicht nur
    Python-Identitaeten und fasst kein C++-Objekt an. Die Mutation "Guard entfernt"
    zeigt, dass ohne den Guard Qt sofort meckert
    (`QWidget::mapTo(): parent must be in parent hierarchy`).
  - `self` geloescht: `ProfileBar` wird genau einmal erzeugt (`mainwindow.py:236`) und
    nie geloescht; beim Beenden laeuft die Ereignisschleife nicht mehr. Ein erzwungenes
    `shiboken6.delete(bar)` mit anschliessendem Aufruf hat **keinen** `RuntimeError`
    ausgeloest.
  - Ergebnis: **kein Befund**, die Sorge ist geprueft und ausgeraeumt.
- Trotzdem als Stilhinweis: `QTimer.singleShot(0, self, lambda: ...)` (Kontext-Objekt-
  Ueberladung) trennt die Verbindung automatisch mit dem Empfaenger und waere die
  robustere Form. Gilt genauso fuer das bestehende `QTimer.singleShot(100, _delayed_select)`.

### [LOW] 7 — Redundanter Guard in `_handle_scroll_key`

- Datei: `anvil/widgets/profile_bar.py:545-546`
- Problem: `if self._inline_input is not None or self._rename_input is not None: return False`
  kann praktisch nicht greifen. Tastendruecke gehen an das fokussierte Widget; das ist
  bei offenem Feld das QLineEdit, und ein QLineEdit besteht `_is_own_scroll_target()`
  ohnehin nicht (es ist weder `_tabs_widget` noch `_tab_container` noch ein Tab).
  Der Guard schadet nichts, aber `test_scroll_keys_are_left_alone_while_typing_a_name`
  sichert damit einen Pfad ab, der im Betrieb nicht vorkommt — der Test ruft `eventFilter`
  kuenstlich mit einem Tab als `obj` auf.

### [LOW] 8 — Pos1/Ende nur bei Tastaturfokus auf der Leiste; nicht auffindbar

- Datei: `anvil/widgets/profile_bar.py:941-945`
- `_is_own_scroll_target()` verlangt, dass `obj` ein Tab, `_tabs_widget`, `_tab_container`,
  die `QScrollArea` oder deren Viewport ist. Das trifft nur zu, wenn der Nutzer vorher
  einen Profil-Tab angeklickt hat. Aus dem Modlisten-Baum heraus passiert nichts.
  Es gibt keinen Tooltip und keinen Hinweis auf die Tastenkuerzel.
- Ausserdem: die Funktion war nicht Teil von Issue #103 (dort ging es um das
  unsichtbare Eingabefeld). Sauberer waere ein eigenes Issue.
- Rueckgabewerte des `eventFilter` sind korrekt: `True` nur, wenn `_handle_scroll_key`
  wirklich behandelt hat; sonst faellt der Aufruf durch. Der Block steht vor dem
  `if obj not in self._tabs: return super().eventFilter(...)` und blockiert Drag & Drop
  nicht (dort werden nur Maus-Ereignisse ausgewertet).
  Anwendungsweite Nebenwirkungen: kein weiterer Ort im Projekt wertet `Key_Home`/`Key_End`
  aus (`grep` ueber `anvil/`), Kurzbefehle laufen ueber `ShortcutOverride`/`Shortcut`
  und nicht ueber `KeyPress` — Pos1/Ende koennen also anderswo nicht verschluckt werden.

### [LOW] 9 — `_is_own_scroll_target` kennt den "+"-Knopf nicht

- Datei: `anvil/widgets/profile_bar.py:529-535`
- Im modernen Theme liegt `_btn_add` im scrollbaren Streifen (`set_profiles`, Zeile 616).
  Mausrad ueber dem "+"-Knopf scrollt die Leiste deshalb nicht.
  Vorbestehend, aber im selben Themenkreis.

---

## Tests

### Sind die Tests aussagekraeftig? Ja — mit Mutationstest belegt

| Mutation | Ergebnis |
|---|---|
| `edit.show()` entfernt | `test_container_does_not_clip_the_new_field` FAILED |
| `QTimer.singleShot(0, reveal)` entfernt | `test_inline_input_is_fully_visible_with_many_profiles` FAILED |
| `eventFilter`-Hook fuer Pos1/Ende entfernt | 2 Tests FAILED |
| Guard `edit is not self._inline_input` entfernt | `test_reveal_ignores_a_field_that_was_already_dismissed` FAILED |

Keine der vier Aenderungen bleibt unbemerkt — die Tests sind nicht tautologisch.
`_visible_width()` misst ueber `mapTo(viewport, ...)` echte Pixel und ist damit ein
sinnvoller Massstab. Die Datei wurde nach jeder Mutation wiederhergestellt
(Pruefsumme identisch).

### Maengel an den Tests

- **[MEDIUM] T1 — Kein Test wartet die 100 ms von `_delayed_select` ab.**
  `_bar()` ruft nur `processEvents()`. Damit laufen **alle** Tests in einem Zustand, in
  dem weder `_update_container_width()` aus `set_profiles()` noch `_select_profile()` /
  `_scroll_to_tab()` je ausgefuehrt wurden. Der realistische Zustand (enger
  `maximumWidth`, Leiste auf den aktiven Tab gescrollt) wird gar nicht getestet — und
  genau dort steckt Finding 2.
- **[LOW] T2** `test_inline_input_is_fully_visible_with_few_profiles` faellt bei keiner
  der vier Mutationen um. Reiner Nicht-Regressions-Test, prueft das eigentliche
  Verhalten nicht mit.
- **[LOW] T3** `_plus_inline` wird erst **nach** `__init__` umgesetzt. Dadurch haengt das
  Ergebnis vom real aktiven Theme ab: laeuft das moderne Theme, ist `_btn_add` in
  `test_classic_theme_keeps_the_field_unclipped` in gar keinem Layout (elternloses
  Waisen-Widget); laeuft das klassische, fehlt in `_bar()` das `layout.addStretch(1)`.
  Keiner der beiden echten Aufbauten wird also exakt nachgestellt.
  Besser: `is_modern_theme_active` bzw. `theme_color` monkeypatchen und erst danach
  `ProfileBar()` bauen.
- **[LOW] T4** Kein Aufraeumen: keine Fixture, kein `close()`/`deleteLater()`.
  Jede Leiste haengt bis Prozessende einen anwendungsweiten Ereignisfilter ein, und
  `test_reveal_ignores_a_field_that_was_already_dismissed` hinterlaesst einen
  eingereihten `_reveal_inline_input`-Aufruf auf ein bereits geloeschtes C++-QLineEdit,
  der erst im `processEvents()` eines spaeteren Tests feuert. Aktuell harmlos, weil der
  Guard greift — aber genau dieser Guard ist das, was der Test prueft. Faellt er weg,
  brechen fremde Tests.
- **[LOW] T5** Docstring von `test_container_does_not_clip_the_new_field` sagt
  "it showed 35 px of 140" — die Breite ist inzwischen 200.
- **[LOW] T6** Die Aenderung `INLINE_INPUT_WIDTH` 140 → 200 ist durch keinen Test
  abgesichert; alle Tests vergleichen gegen die Konstante selbst. Setzt man sie auf 140
  zurueck, bleibt alles gruen. Bei einem reinen Optikwert vertretbar, sollte aber
  bewusst sein.
- **[LOW] T7** Die neue Datei setzt `QT_QPA_PLATFORM` per `os.environ.setdefault` auf
  Modulebene und braucht dafuer `# noqa: E402` an jedem Import. Es gibt keine
  `conftest.py`; `tests/test_profile_bar_scrolling.py` verlaesst sich stillschweigend
  darauf, dass die alphabetisch vorher eingelesene Datei das erledigt hat.
  Sauberer waere eine `tests/conftest.py`.

---

## Projektregeln

| Regel | Ergebnis |
|---|---|
| Keine hartcodierten Pfade | OK — die Aenderung fasst keine Pfade an |
| Kein `setStyleSheet()` in neuen Widgets | OK — das `setStyleSheet` auf `edit` ist Bestand, der Diff fuegt keines hinzu |
| `tr()`-Schluessel in allen Locales | OK — keine neuen sichtbaren Texte, Locale-Dateien unberuehrt |
| Signalverbindungen | OK — keine neuen Signale; `_btn_add.clicked.connect(self._start_inline_create)` unveraendert |
| Importe vorhanden | OK — `QPoint`, `QTimer`, `QEvent` waren bereits importiert |
| Cover-Bilder / redprelauncher / REDmod | nicht beruehrt |
| Volle Testsuite | 229 passed, 1 skipped |

Nebenbei: `anvil/locales/` enthaelt inzwischen **7** Sprachen (de, en, es, fr, it, pt, ru).
In `CLAUDE.md` steht noch "alle 6 Locale-Dateien" — fuer diesen Diff ohne Belang, aber
die Regel gehoert nachgezogen.

---

## Ergebnis

**NEEDS FIXES**

Der Kern des Fixes ist richtig und behebt den gemeldeten Fall nachweisbar
(0 px → 200 px sichtbar bei 30 Profilen). Offen sind:

1. Finding 1 — Umbenennen hat denselben Fehler, gemessen 16 px abgeschnitten (MEDIUM)
2. Finding 2 — `_delayed_select` scrollt das Feld innerhalb von 100 ms wieder weg,
   gemessen 200 px → 0 px (MEDIUM)
3. Finding 3 — `set_profiles()` laesst ein offenes Feld stehen, "+" reagiert danach
   nicht mehr (MEDIUM, vorbestehend, aber gleiche Aussenwirkung wie #103)
4. Test-Maengel T1 (die Tests laufen nicht im realistischen Zustand) und T3
   (Theme-Abhaengigkeit) sollten mit behoben werden.

Die uebrigen Punkte (4-9, T2/T4-T7) sind Kleinkram und koennen auch spaeter kommen.
