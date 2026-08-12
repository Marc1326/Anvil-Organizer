# Review Issue #103 — Runde 2 (Nachprüfung)

Datum: 2026-08-08
Branch: `fix/issue-103`
Geprüft: `git diff` auf `anvil/widgets/profile_bar.py`, neue Dateien
`tests/test_profile_bar_inline_input.py` und `tests/conftest.py`

## Vorgehen

- Runde-1-Bericht `docs/review-103-bugs.md` Punkt für Punkt durchgegangen
- Kompletten Diff und die geänderten Bereiche der Datei neu gelesen
- Volle Testsuite: **237 passed, 1 skipped** (`python -m pytest tests/ -q`)
- Sechs Offscreen-Messskripte gefahren (echte Pixel- und Zustandswerte, keine Vermutungen):
  Container-Breiten vor/während/nach Umbenennen, Reentranz des Aufräumblocks in
  `set_profiles()`, Gültigkeit der C++-Objekte via `shiboken6.isValid`, Qt-Meldungen
  via `qInstallMessageHandler`, linke Kante bei zu schmalem Sichtfenster,
  Scrollposition nach Abbruch
- Alte Fassung über `git show HEAD:anvil/widgets/profile_bar.py` gegengelesen, um
  "neu" von "vorbestehend" sauber zu trennen
- `python -m py_compile` sauber; kein `ruff` im Projekt-venv installiert

---

## Teil 1 — Status der Befunde aus Runde 1

| # | Befund Runde 1 | Status | Beleg |
|---|---|---|---|
| 1 | Umbenennen ohne `show()`/Breite/Reveal | **BEHOBEN** | `_start_inline_rename` hat jetzt `edit.show()`, `_update_container_width()`, `INLINE_INPUT_WIDTH`, `QTimer.singleShot(0, self, …)`. Gemessen: Tab 405 px → Feld 405 px, **405 von 405 px sichtbar**. Vorher 124 von 140. |
| 2 | `_delayed_select` scrollt 100 ms später weg | **BEHOBEN** | `_scroll_to_tab` steigt bei offenem Feld aus, `_delayed_select` → `_update_container_width` → `_reveal_input`. Test `test_the_deferred_selection_does_not_scroll_the_field_away` fängt es ab (mit echter Ereignisschleife, nicht nur `processEvents`). |
| 3 | `set_profiles()` lässt offenes Feld stehen, "+" wird tot | **BEHOBEN** | Gemessen nach `set_profiles()` bei offenem Feld: `_inline_input is None`, `edit.parent() is None`, nach Ereignisschleife `shiboken6.isValid(edit) == False`, `_start_inline_create()` legt wieder an. Beim Umbenennen zusätzlich: `_rename_input is None`, `_rename_tab is None`, **keine unsichtbaren Tabs übrig**. Qt-Meldungsliste leer. |
| 4 | Pos1/Ende vom Ziffernblock | **BEHOBEN** | `modifiers & ~KeypadModifier`; `test_the_keypad_variants_work_too` grün. |
| 5 | Feld breiter als Sichtfenster: linke Kante draußen | **BEHOBEN** | Gemessen bei 68 px Sichtfenster / 200 px Feld: linke Kante bei **0** (vorher −132). |
| 6 | `QTimer.singleShot` ohne Kontextobjekt | **teilweise** | Die beiden neuen 0-ms-Timer haben jetzt `self` als Kontext. Das vorbestehende `QTimer.singleShot(100, _delayed_select)` in `set_profiles` (Zeile 642) hat weiterhin keines. War in Runde 1 als Stilhinweis eingestuft — bleibt offen, kein Bug. |
| 7 | Redundanter Guard in `_handle_scroll_key` | **unverändert** | Weiterhin praktisch unerreichbar (bei offenem Feld hat das QLineEdit den Fokus und besteht `_is_own_scroll_target` nicht). Schadet nichts. |
| 8 | Pos1/Ende nur bei Fokus auf der Leiste, kein Hinweis | **unverändert** | War von vornherein "eigenes Issue", nicht Teil von #103. |
| 9 | `_is_own_scroll_target` kennt `_btn_add` nicht | **BEHOBEN** | Zeile 535. Nachgeprüft: `_btn_add` liegt im modernen Theme im Streifen (`set_profiles` Zeile 630); der Zusatz hat keine Nebenwirkung auf Drag & Drop, weil der Block vor `if obj not in self._tabs` steht und nur Wheel/KeyPress auswertet. |

### Teststand aus Runde 1

| # | Mangel Runde 1 | Status |
|---|---|---|
| T1 | Kein Test wartet die 100 ms ab | **teilweise** — `_settle()` existiert und wird in vier Tests genutzt. `_bar()` selbst settelt weiter nicht, die übrigen Tests laufen also weiterhin vor `_delayed_select`. Reicht für die Regressionen, bleibt aber ein Rest. |
| T2 | `…_with_few_profiles` reiner Nicht-Regressions-Test | unverändert, vertretbar |
| T3 | `_plus_inline` nach `__init__` gesetzt → themeabhängig | **unverändert.** Nachgemessen: in der Testumgebung ist `is_modern_theme_active() == False`, also legt `__init__` `_btn_add` in die Werkzeugzeile und `set_profiles` holt es bei `modern=True` in den Streifen. Läuft hier korrekt, hängt aber weiter am real aktiven Theme. |
| T4 | Kein Aufräumen / keine Fixture | unverändert (keine Fixture, kein `close()`); durch den `set_profiles`-Fix entschärft |
| T5 | Docstring "35 px of 140" veraltet | **unverändert**, Zeile 100 der Testdatei |
| T6 | Breite 200 durch keinen Test gesichert | **BEHOBEN** — `test_field_is_at_least_as_wide_as_the_longest_placeholder` prüft gegen die harte 200 |
| T7 | Keine `conftest.py` | **BEHOBEN** — `tests/conftest.py` setzt `QT_QPA_PLATFORM`, die `# noqa: E402` sind aus der Testdatei verschwunden |

Die deutschen lokalen Variablennamen sind ersetzt (`scrollbar`, `visible`, `left`,
`right`, `field`, `modifiers`), Umlaute sind einheitlich. `self._inline_input = edit`
steht vor dem Timer. Alles wie angekündigt.

---

## Teil 2 — Neue Befunde

### [MEDIUM] N1 — Nach dem Umbenennen bleibt die Pillen-Gruppe zu breit

- Datei: `anvil/widgets/profile_bar.py:863` gegen `:874-906` und `:908-920`
- Problem: `_start_inline_rename` ruft jetzt `_update_container_width()` und weitet den
  Container auf die Feldbreite (mindestens 200 px statt der Tab-Breite).
  **Weder `_finish_inline_rename` noch `_cancel_inline_rename` rufen
  `_update_container_width()` wieder auf.** Der `maximumWidth` bleibt auf dem Wert von
  "Feld offen" stehen.
- Gemessen (modernes Theme):
  - 3 Profile: Container vor dem Umbenennen **260 px**, während **387 px**,
    nach Abbruch **387 px** (`width()` und `maximumWidth()`).
    Ein manuell nachgeschobenes `_update_container_width()` bringt exakt 260 px zurück.
  - 30 Profile: `maximumWidth` 2851 → 2961, `sizeHint` danach 2843 (Abbruch)
    bzw. 2801 (bestätigt) — der Container ist 118 bzw. 160 px zu breit.
- Sichtbar, weil `_tab_container` ein QFrame mit eigener Hintergrundfarbe und
  `border-radius: 8px` ist (`_tab_container_style`): es bleibt ein leerer dunkler
  Streifen rechts neben dem letzten Tab stehen.
- Heilt **nicht** von selbst: `_on_profile_renamed` in `mainwindow.py:4422-4481` ruft im
  Erfolgsfall kein `set_profiles()`. Der Zustand bleibt, bis irgendwann ein
  `set_profiles()` (Instanzwechsel, Profil anlegen/löschen, Neu laden) oder ein
  Drag-&-Drop-Umsortieren (`_finish_drag`, Zeile 1054) läuft.
- Neu durch diesen Diff: `git show HEAD:` belegt, dass die alte Fassung
  `_update_container_width()` **nur** in der Anlege-Strecke aufrief (Zeilen 708/738/756),
  in der Umbenennen-Strecke gar nicht. Erst das neue Aufweiten ohne Gegenstück erzeugt
  den Effekt.
- Betrifft nur das moderne Theme (`_update_container_width` kehrt bei
  `not self._plus_inline` sofort zurück).
- Von keinem der neuen Tests abgedeckt — `test_container_does_not_clip_the_rename_field`
  prüft nur `maximumWidth() >= sizeHint()`, also genau die Richtung, die hier nicht
  das Problem ist.
- Fix: am Ende von `_finish_inline_rename` und `_cancel_inline_rename` jeweils
  `self._update_container_width()` aufrufen — analog zu `_finish_inline_create` /
  `_cancel_inline_create`. In `_cancel_inline_rename` erst **nach** `self._rename_input = None`,
  sonst misst der eingebaute Reveal ein bereits abgehängtes Feld.

### [LOW] N2 — Nach Abbruch bleibt die Leiste am rechten Ende stehen

- Datei: `anvil/widgets/profile_bar.py:822-833` (`_cancel_inline_create`), gleiches Bild
  bei `_cancel_inline_rename`
- Gemessen (30 Profile, aktiv "Default"): Scrollwert vor dem "+" **0**, mit offenem
  Feld **2387**, nach dem Abbruch **2217**. Die linke Kante des aktiven Tabs liegt danach
  bei **−2217** bei 626 px Sichtfenster — das aktive Profil ist nicht mehr im Bild.
- Neu, weil vor dem Diff gar nicht gescrollt wurde. Fachlich vertretbar (der Nutzer hat
  die Leiste durch das "+" selbst dorthin gebracht), aber es ist eine sichtbare
  Verhaltensänderung, die weder im Diff kommentiert noch getestet ist.
- Fix (falls gewollt): am Ende der beiden Abbruchpfade den aktiven Tab suchen und
  `self._scroll_to_tab(tab)` aufrufen — das ist ab dann wieder erlaubt, weil die
  Feldzeiger vorher auf `None` gesetzt werden.

### [LOW] N3 — Der Aufräumblock in `set_profiles` läuft reentrant

- Datei: `anvil/widgets/profile_bar.py:591-597`
- Gemessen: `field.setParent(None)` löst `focusOutEvent` → `focus_lost` aus, also läuft
  mitten in der Schleife `_cancel_inline_create` bzw. `_cancel_inline_rename` durch
  (mit Zähler nachgewiesen: genau ein reentranter Aufruf je Fall).
  Danach macht die Schleife `setParent(None)` und `deleteLater()` ein **zweites Mal**.
- Ergebnis der Messung: **kein Fehler.** Qt-Meldungsliste leer, Objekt genau einmal
  zerstört (`shiboken6.isValid` → `False`), `_rename_tab` und die Sichtbarkeit der Tabs
  korrekt, "+" wieder bedienbar. Der reentrante `_cancel_inline_create` ruft dabei
  `_update_container_width()` auf, während die alten Tabs noch im Layout hängen —
  folgenlos, weil `_delayed_select` die Breite ohnehin neu setzt.
- Kein Bug, aber die Reihenfolge (Feld-Aufräumen **vor** dem Löschen der Tabs) ist genau
  das, was `_cancel_inline_rename`s `tab.show()` vor einem `RuntimeError` bewahrt. Das
  ist im Code nicht erkennbar. Ein Satz im vorhandenen Kommentar ("muss vor dem Löschen
  der Tabs stehen") würde die Falle für den nächsten Umbau sichtbar machen.

### [LOW] N4 — Der Rück-Reveal in `_update_container_width` gilt nur im modernen Theme

- Datei: `anvil/widgets/profile_bar.py:724-736`
- Der neue Reveal steht **unter** dem frühen `if not self._plus_inline: return`.
  Im klassischen Theme richtet `_delayed_select` ein offenes Feld also nie nach.
- Aktuell folgenlos: im klassischen Theme gibt es keine Container-Begrenzung, und der
  frühe Ausstieg in `_scroll_to_tab` verhindert das Wegscrollen. Das Sicherheitsnetz
  hängt damit aber allein an `_scroll_to_tab`. Wird der Guard dort je entfernt, verliert
  das klassische Theme still seine Absicherung — der Test
  `test_inline_input_is_visible_in_the_classic_theme_too` merkt es nicht, weil er
  `_settle()` nicht benutzt.

### Was ausdrücklich geprüft und in Ordnung ist

- **Rekursion `_update_container_width` ↔ `_reveal_input`:** keine. `_reveal_input` ruft
  nur `scrollbar.setValue()`; `valueChanged` hängt an `_update_fade_visibility`, und die
  Blenden werden per `move()` positioniert, hängen also in keinem Layout. Kein Rücklauf.
- **Reveal auf ein abgehängtes Feld (`mapTo`-Warnung):** in beiden Startmethoden wird
  `_update_container_width()` aufgerufen, **bevor** `self._inline_input`/`_rename_input`
  gesetzt ist — dort passiert also gar kein Reveal. In `_finish_inline_create` und
  `_cancel_inline_create` wird der Zeiger **vor** `_update_container_width()` genullt.
  Keine Qt-Meldung in allen Messläufen.
- **Verwaister Timer nach Aufräumen:** der eingereihte `_reveal_input(edit)` findet
  `_inline_input`/`_rename_input` auf `None` und kehrt zurück, ohne ein C++-Objekt
  anzufassen. Gemessen, keine `RuntimeError`.
- **Früher Ausstieg in `_scroll_to_tab` blockiert nicht dauerhaft:** die Zeiger werden in
  allen fünf Pfaden zurückgesetzt (`_finish`/`_cancel` je Strecke + `set_profiles`).
  Ein Hängenbleiben über `_inline_confirmed`/`_rename_confirmed` ist nicht möglich, weil
  das Flag jeweils unmittelbar vor dem Nullen des Zeigers gesetzt wird und dazwischen
  nichts laufen kann. Nach `_finish_inline_create` → `set_profiles` → `_delayed_select`
  scrollt die Leiste wieder normal auf das neue Profil.
- **Zwei Felder gleichzeitig:** `_start_inline_create` prüft nur `_inline_input`,
  `_start_inline_rename` nur `_rename_input`. Praktisch nicht erreichbar, weil der
  anwendungsweite `MouseButtonPress`-Filter vorher `clearFocus()` auslöst und
  Tastaturfokuswechsel `focusOutEvent` liefert. Der neue Aufräumblock behandelt beide
  Felder ohnehin. (Vorbestehend, kein neuer Befund.)
- **Langer Profilname:** Tab 405 px → Feld 405 px, vollständig sichtbar. `tab.hide()`
  vor dem Lesen von `tab.width()` liefert weiterhin die alte Breite.
- **Home/End anwendungsweit:** kein zweiter Ort in `anvil/` wertet `Key_Home`/`Key_End`
  aus (`grep`). `_handle_scroll_key` gibt für alle anderen Tasten `False` zurück, der
  Filter fällt sauber durch.

---

## Projektregeln

| Regel | Ergebnis |
|---|---|
| Keine hartcodierten Pfade | OK — der Diff fasst keine Pfade an |
| Kein neues `setStyleSheet()` | OK — die vorhandenen Aufrufe sind Bestand |
| `tr()`-Schlüssel in allen Locales | OK — keine neuen sichtbaren Texte |
| Signalverbindungen | OK — keine neuen Signale; `returnPressed`/`focus_lost` unverändert verdrahtet |
| Importe | OK — `QPoint`, `QTimer`, `QEvent`, `Qt` waren vorhanden |
| Cover-Bilder / redprelauncher / REDmod | nicht berührt |
| Mod-Verwaltung / Deploy / modlist.txt | nicht berührt — reine GUI-Änderung an der Profil-Leiste, kein Bezug zu `.mods/`, `active_mods.json` oder Frameworks |
| `python -m py_compile` | sauber |
| Testsuite | 237 passed, 1 skipped |

---

## Ergebnis

**NEEDS FIXES**

Alle neun Befunde aus Runde 1 sind sachlich abgearbeitet — sieben vollständig, Nr. 6
als Stilhinweis nur zur Hälfte (der 100-ms-Timer bleibt ohne Kontextobjekt), Nr. 7 und 8
waren von vornherein nur Hinweise. Die drei ausdrücklich benannten Risikostellen
(Aufräumblock, Rückruf aus `_update_container_width`, früher Ausstieg in
`_scroll_to_tab`) habe ich einzeln nachgemessen: der Aufräumblock ist reentrant, tut
aber genau das Richtige; eine Rekursion gibt es nicht; das Scrollen zum aktiven Profil
wird nirgends dauerhaft unterdrückt.

Offen ist **ein neuer Fehler**, der durch die Nachbesserung entstanden ist:

1. **N1 (MEDIUM)** — `_start_inline_rename` weitet die Pillen-Gruppe, keiner der beiden
   Endpunkte schrumpft sie zurück. Gemessen 387 statt 260 px bei drei Profilen, und der
   Zustand heilt nach einem erfolgreichen Umbenennen nicht von selbst.
   Zwei Zeilen Fix, dazu ein Test, der die Container-Breite nach `_cancel_inline_rename`
   und `_finish_inline_rename` gegen `sizeHint()` prüft.

N2 bis N4 sind Kleinkram und können mitlaufen oder liegen bleiben; T1/T3/T4/T5 aus
Runde 1 ebenso.
