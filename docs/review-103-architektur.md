# Review #103 — Architektur & Qt-Qualitaet (Profil-Leiste, Inline-Eingabe)

Datum: 2026-08-08
Branch: fix/issue-103
Geprueft: uncommitted `git diff` (anvil/widgets/profile_bar.py) + neue Datei tests/test_profile_bar_inline_input.py
Gelesene Grundlagen: /home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md, CLAUDE.md (global + Projekt), GitHub-Issue #103

Alle Aussagen unten sind nachgemessen. Die Messskripte liefen offscreen gegen die echte ProfileBar
(`QT_QPA_PLATFORM=offscreen`, PySide6 6.11.1). Zahlen in Klammern sind gemessene Pixelwerte.

---

## 0. Vorab: Architektur-Pflichtpunkte

| Regel | Ergebnis |
|---|---|
| 1. Mod-Dateien nie ins Game-Verzeichnis kopieren | nicht beruehrt (reine GUI-Aenderung) |
| 2. Ordnerstruktur in `.mods/` unveraendert | nicht beruehrt |
| 3. Frameworks nicht in `.mods/`/modlist.txt | nicht beruehrt |
| 4. active_mods.json in allen Profilen aktualisieren | nicht beruehrt (kein Rename/Delete von Profilen im Diff) |
| 5. Nur globale API, keine Legacy-modlist | nicht beruehrt |
| 6. MO2-Referenz konsultiert | **nicht moeglich** — `/home/mob/Projekte/mo2-referenz/` existiert auf dieser Maschine nicht (`ls` schlaegt fehl). Betroffen ist ohnehin keiner der vergleichspflichtigen Bereiche (Installation, modlist.txt, Deploy, Rename/Delete von Mods, Separatoren, Kontextmenue der Modliste). |
| 7. Architektur-Doku gelesen | ja |

Der Diff aendert ausschliesslich Darstellung/Bedienung der Profil-Leiste. Kein Deploy-Pfad,
kein Symlink, kein Manifest, keine modlist.txt. Aus Architektursicht unbedenklich.

Testlauf: `pytest tests/` → **229 passed, 1 skipped**. Kein Regressionsschaden feststellbar.

---

## 1. Ist die manuelle Scrollbalken-Rechnung statt ensureWidgetVisible gerechtfertigt?

**Ja — die Begruendung im Docstring stimmt, nachgeprueft statt geglaubt.**

Qt vergleicht in `QScrollArea::ensureWidgetVisible()` das Ergebnis von
`childWidget->inputMethodQuery(Qt::ImCursorRectangle)` mit der Basisimplementierung
`QWidget::inputMethodQuery(...)`. Sind sie verschieden, wird nur das Cursor-Rechteck
ins Bild geschoben, sonst das ganze Widget-Rechteck. QLineEdit ueberschreibt
`inputMethodQuery`, QPushButton nicht.

Gemessen mit identischem Aufbau (Feldbreite 200, Viewport 398):

| Kind-Widget | ImCursorRectangle des Kindes | QWidget-Default | sichtbar nach ensureWidgetVisible |
|---|---|---|---|
| QLineEdit | QRect(-2, 0, 9, 22) | QRect(100, 0, 1, 30) | **7 px von 200** |
| QPushButton | QRect(100, 0, 1, 30) | QRect(100, 0, 1, 30) | **200 px von 200** |

Damit ist auch belegt, dass das bestehende `_scroll_to_tab()` (ensureWidgetVisible auf
einem QPushButton) weiterhin korrekt arbeitet — dort besteht kein Handlungsbedarf.

**Aber:** der Docstring schliesst nur `ensureWidgetVisible` aus und erweckt damit den
Eindruck, Qt biete nichts anderes. Es gibt `QScrollArea.ensureVisible(x, y, xmargin, ymargin)`
— koordinatenbasiert, ohne Cursor-Rechteck. Zwei Aufrufe (rechte Kante, dann linke Kante)
liefern exakt denselben Scrollwert wie die Handrechnung (beide `value=2384`, sichtbar 200 px).
Siehe Befund LOW-4.

## 2. Ist QTimer.singleShot(0, ...) hier der uebliche Weg?

**Ja, und er ist hier sogar notwendig — belegt.** Gemessen mit 30 Profilen, Fensterbreite 1000:

| Theme | Reveal synchron (ohne Timer) | Reveal im naechsten Zyklus |
|---|---|---|
| modern (`_plus_inline=True`) | sichtbar 200 px, Scrollbereich max=2318 | sichtbar 200 px |
| klassisch (`_plus_inline=False`) | **sichtbar 87 px**, max noch 2116 (veraltet) | sichtbar 200 px, max=2320 |

Grund: im modernen Theme ruft `_update_container_width()` bereits `adjustSize()` auf dem
Streifen auf, wodurch die QScrollArea ihren Bereich sofort nachzieht. Im klassischen Theme
kehrt `_update_container_width()` sofort zurueck (Zeile 707-708), also bleibt der
Scrollbereich bis zum naechsten LayoutRequest veraltet. Ein `layout().activate()` auf
Streifen/Container/Bar aendert daran nichts (gemessen: identisch zum Synchronfall).
`resizeEvent`/`showEvent` scheiden aus, weil das Feld erst auf Knopfdruck entsteht.

Der Timer passt ausserdem zum Bestand: `set_profiles()` benutzt seit jeher
`QTimer.singleShot(100, _delayed_select)`.

---

## Findings

### [MEDIUM] Der Umbenennen-Pfad hat exakt denselben Fehler und wurde nicht mitgefixt
- Datei: anvil/widgets/profile_bar.py:811-845 (`_start_inline_rename`)
- Problem: Der Pfad ist strukturgleich zum Anlegen-Pfad — `insertWidget` + `setFocus` —
  aber ohne `edit.show()`, ohne `_update_container_width()` und ohne Reveal.
  Gemessen (modernes Theme, 30 Profile, Fenster 1200, Doppelklick auf Tab 25):
  **sichtbar = 0 px von 140**, `hasFocus() == True`. Der Nutzer tippt in ein Feld,
  das er nicht sieht — dieselbe Symptomatik, die der Melder von #103 beschreibt
  ("I can't seem to create a new profile", 30 Profile).
- Nebeneffekt: die Datei ist nach dem Fix in sich inkonsistent — zwei fast identische
  Code-Bloecke, einer korrigiert, einer nicht.
- Fix: `_reveal_inline_input` zu einem allgemeinen Helfer machen
  (`_scroll_widget_into_view(widget)`), und im Rename-Pfad `show()`,
  `_update_container_width()` und den verzoegerten Reveal analog aufrufen.
  Falls das bewusst ausserhalb des Scope bleiben soll: als eigenes Issue anlegen, sonst
  geht es verloren.

### [MEDIUM] Versteckte Reihenfolge-Abhaengigkeit: der Guard funktioniert nur, weil verzoegert wird
- Datei: anvil/widgets/profile_bar.py:741 (Timer) vs. 747 (`self._inline_input = edit`)
  und 756 (`if edit is not self._inline_input: return`)
- Problem: `self._inline_input` wird erst NACH dem Einplanen des Timers gesetzt. Wird der
  Aufruf jemals synchron gemacht oder der Timer entfernt, greift der Guard sofort
  (`_inline_input` ist noch `None`), die Methode kehrt still zurueck und es wird gar nicht
  gescrollt — ohne Exception, ohne Log, der Bug ist einfach wieder da.
  Nachgestellt: `QTimer.singleShot(0, f)` durch Direktaufruf ersetzt →
  `test_inline_input_is_fully_visible_with_many_profiles` schlaegt fehl, aber die
  Fehlermeldung zeigt nur "0 != 200" und nicht die Ursache.
- Fix: `self._inline_input = edit` vor die `QTimer.singleShot`-Zeile ziehen. Das kostet
  nichts und macht den Guard unabhaengig von der Aufrufreihenfolge.

### [MEDIUM] INLINE_INPUT_WIDTH: undokumentierte UI-Aenderung, Konstante nur halb durchgezogen
- Datei: anvil/widgets/profile_bar.py:30-31, 723 vs. 833
- Problem 1: Die Verbreiterung 140 → 200 gehoert nicht zum gemeldeten Fehler und wird
  nirgends begruendet. Der Kommentar sagt nur, was die Konstante ist, nicht warum 200.
  Gemessen (13 px Schrift + 24 px Padding) brauchen die Platzhalter:
  de 101, en 112, es 139, fr 119, it 115, pt 126 px — Spanisch war bei 140 px auf Kante.
  Wenn das der Grund ist, gehoert er in den Kommentar; wenn nicht, gehoert die Aenderung
  nicht in diesen Fix (breiteres Feld verschaerft das Abschneide-Problem sogar).
- Problem 2: `_start_inline_rename` behaelt `max(140, tab.width())` als Literal. Die
  Konstante vereinheitlicht also nichts, sondern erzeugt zwei Wahrheiten fuer dieselbe UI.
- Fix: Grund in den Kommentar oder zurueck auf 140; in beiden Faellen die Konstante auch
  im Rename-Pfad als Untergrenze verwenden.

### [LOW] Qt bietet mit ensureVisible() eine koordinatenbasierte API, die nicht erwaehnt wird
- Datei: anvil/widgets/profile_bar.py:749-767
- Problem: Nicht falsch, aber die Handrechnung dupliziert, was
  `QScrollArea.ensureVisible(x, y, xmargin, ymargin)` bereits kann (existiert in
  PySide6 6.11.1, verifiziert). Zwei Aufrufe — erst rechte Kante, dann linke Kante —
  ergeben denselben Scrollwert (2384) und dieselben 200 px Sichtbarkeit, ohne
  `bar.minimum()/maximum()/value()`-Arithmetik im eigenen Code.
- Fix: entweder `ensureVisible` nutzen, oder im Docstring einen Halbsatz ergaenzen,
  warum auch das nicht passt. So wie es dasteht, wirkt es, als gaebe es nur
  ensureWidgetVisible.

### [LOW] Feld breiter als Viewport: Anfang des Textes wird herausgescrollt
- Datei: anvil/widgets/profile_bar.py:764-767
- Problem: Ist das Sichtfenster schmaler als das Feld, greift der `if`-Zweig und richtet die
  RECHTE Kante aus; der `elif` kann das nicht mehr korrigieren. Gemessen bei Leistenbreite
  420 px: linke Feldkante liegt bei -54 px, d.h. Cursor und Platzhalteranfang liegen
  ausserhalb. Praktisch heute nicht erreichbar (`setMinimumSize(1000, 650)` in
  mainwindow.py:200), deshalb LOW — bei 500 px Fensterbreite ist es noch in Ordnung
  (linke Kante +26).
- Fix: bei `edit.width() > sicht` die linke Kante bevorzugen (Reihenfolge der beiden
  Zweige tauschen bzw. `links` zuletzt anwenden).

### [LOW] Verzoegerter Rueckruf laeuft potenziell gegen ein zerstoertes C++-Objekt
- Datei: anvil/widgets/profile_bar.py:741
- Problem: `QTimer.singleShot(0, lambda: self._reveal_inline_input(edit))` haelt `self` ohne
  Kontextobjekt. Nachgestellt mit `shiboken6.delete(bar)` direkt nach `_start_inline_create`:
  der Rueckruf laeuft weiter und wirft
  `RuntimeError: Internal C++ object (PySide6.QtWidgets.QScrollArea) already deleted`.
  Im Alltag unwahrscheinlich, weil die Bar einmalig als Kind des Hauptfensters entsteht
  (mainwindow.py:236) und nie neu gebaut wird — deshalb LOW.
- Fix: `QTimer.singleShot(0, self, lambda: self._reveal_inline_input(edit))`.
  Die Kontext-Ueberladung ist in PySide6 6.11.1 vorhanden (verifiziert) und trennt die
  Verbindung automatisch, wenn das Objekt stirbt.

### [LOW] Benennung passt nicht zum Rest der Datei
- Datei: anvil/widgets/profile_bar.py:548 (`bar = ...`), 760-762 (`sicht`, `links`, `rechts`)
- Problem 1: Der Scrollbalken heisst im Bestand durchgehend `scrollbar`
  (wheelEvent:560, _update_fade_visibility:576). `bar` ist zusaetzlich irrefuehrend, weil
  "bar" im Projekt und in den Tests die ProfileBar meint.
- Problem 2: `sicht`, `links`, `rechts` sind die einzigen deutschen lokalen Variablennamen
  im gesamten `anvil/`-Baum (per grep geprueft); dieselbe Datei benutzt sonst
  `insert_index`, `local_x`, `tab_center`, `at_start`, `new_index`.
- Fix: `scrollbar`, `viewport_width`, `left`, `right`.

### [LOW] Umlaut-Umschreibung innerhalb einer Datei, die Umlaute benutzt
- Datei: anvil/widgets/profile_bar.py:541, 733, 737, 739, 754, 757
  ("gehoeren", "zaehlt", "ausserhalb", "naechsten", "uebrig", "bestaetigt")
- Problem: Dieselbe Datei schreibt an 21 Stellen echte Umlaute ("fuer Drag & Drop" gibt es
  dort nicht — es steht "für Drag & Drop", "Menü", "zurücksetzen", "löschbar").
  Ehrlichkeitshalber: projektweit gibt es die ASCII-Schreibweise durchaus
  (script_merger_dialog.py, plugin_creator_dialog.py, export_import_dialog.py), es ist also
  kein Alleinstellungsmerkmal des neuen Codes — innerhalb dieser Datei ist es aber ein Bruch.
- Fix: echte Umlaute verwenden, wie im Rest der Datei.

### [LOW] Kommentardichte ueber dem Hausmass
- Datei: anvil/widgets/profile_bar.py:732-741, 750-755
- Problem: Auf ~5 Zeilen neue Logik kommen 6 Kommentarzeilen plus ein 5-zeiliger Docstring.
  Inhaltlich sind es "Warum"-Kommentare, also die gute Sorte — aber CLAUDE.md verlangt
  ausdruecklich sparsame Kommentare und keine Docstrings ueberall, und der erzaehlende Ton
  ("Ohne das Scrollen wirkt der '+'-Knopf wirkungslos") faellt gegenueber dem knappen
  Bestand ("Vorlage: Pill-Gruppe nur so breit wie ihr Inhalt.") auf.
- Fix: auf je einen Satz eindampfen, z.B. "Layout zeigt eingefuegte Widgets nicht selbst an"
  und "Scrollbereich steht erst nach dem naechsten Layout fest". Der ensureWidgetVisible-
  Hinweis im Docstring sollte bleiben, er ist die wertvollste Zeile des Diffs.

### [LOW] Der Eingabefeld-Guard in _handle_scroll_key ist zur Laufzeit unerreichbar
- Datei: anvil/widgets/profile_bar.py:545-546
- Problem: Tastendruecke gehen an das Fokus-Widget. Waehrend ein Inline-Feld offen ist, ist
  das die QLineEdit — die ist kein Ziel von `_is_own_scroll_target()` (dort stehen nur
  `_tabs_widget`, `_tab_container`, `_scroll_area`, dessen Viewport und die Tabs). Der Guard
  kann im Betrieb nicht ausloesen. Er schadet nicht (defensiv ist in Ordnung), aber der
  zugehoerige Test `test_scroll_keys_are_left_alone_while_typing_a_name` beweist nichts
  ueber echtes Verhalten, weil er `eventFilter` mit einem Tab als `obj` aufruft — einen
  Zustand, den es nicht geben kann.
- Fix: Guard behalten, Testkommentar entsprechend ehrlich formulieren.

### [LOW] Fehlende Typannotation
- Datei: anvil/widgets/profile_bar.py:537 `def _handle_scroll_key(self, event) -> bool:`
- Problem: Rueckgabe annotiert, Parameter nicht — `eventFilter` daneben annotiert
  (`event: QEvent`).
- Fix: `event: QKeyEvent` (Import ergaenzen) oder wenigstens `QEvent`.

### [LOW] Tests: Luecke genau an der Stelle, die den Timer rechtfertigt
- Datei: tests/test_profile_bar_inline_input.py:176-190
- Problem: `test_classic_theme_keeps_the_field_unclipped` benutzt FEW_PROFILES — dort gibt es
  nichts zu scrollen. Das klassische Theme mit VIELEN Profilen ist aber der einzige Fall, in
  dem die Verzoegerung wirklich noetig ist (gemessen 87 px statt 200 px ohne Timer). Faellt
  der Timer weg, faellt derzeit nur der moderne 30-Profile-Test, und zwar aus einem anderen
  Grund (siehe MEDIUM "Reihenfolge-Abhaengigkeit").
- Fix: einen Fall `_plus_inline=False` + MANY_PROFILES ergaenzen.
- Nebenbefund: `assert bar._inline_input.width() == INLINE_INPUT_WIDTH` (Zeile 189)
  prueft nur `setFixedWidth` nach und traegt nichts bei.

### [LOW] Tests: QT_QPA_PLATFORM-Behandlung weicht von der Schwesterdatei ab
- Datei: tests/test_profile_bar_inline_input.py:17-25
- Problem: Die neue Datei setzt `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` und
  braucht dafuer `# noqa: E402` an fuenf Importen. `tests/test_profile_bar_scrolling.py`
  macht das nicht, und ein `tests/conftest.py` existiert nicht (geprueft) — die
  Schwesterdatei bleibt also headless-anfaellig, waehrend die neue robust ist. Zwei
  Loesungen fuer dasselbe Problem in einem Verzeichnis.
- Fix: die Zeile in eine `tests/conftest.py` verschieben; dann entfallen auch die
  noqa-Kommentare und die Schwesterdatei profitiert mit.

---

## Ausdrueckliche Entwarnungen (kein Befund)

- **Doppelte Logik zu `_scroll_to_tab`:** nein. Beide scrollen etwas ins Bild, aber
  `_scroll_to_tab` arbeitet auf einem QPushButton, wo ensureWidgetVisible nachweislich
  korrekt ist (200/200 px gemessen). Kein duplizierter Code, nur zwei Mechanismen
  nebeneinander — vertretbar, ein gemeinsamer Helfer waere Kuer (siehe MEDIUM 1, dort
  waere er ohnehin nuetzlich).
- **Doppelte Logik zu `_update_container_width`:** nein, es wird korrekt wiederverwendet
  statt nachgebaut.
- **Doppelte Logik zu `wheelEvent`:** nein, `_handle_scroll_key` liegt sauber daneben und
  benutzt denselben Einstiegspunkt `_is_own_scroll_target()`.
- **`edit.show()`:** korrekt und ausdruecklich von CLAUDE.md gefordert
  ("addWidget() macht neue Widgets NICHT automatisch sichtbar → show() noetig").
- **eventFilter-Einhaengung:** die neue KeyPress-Abfrage steht vor dem
  `if obj not in self._tabs`-Ausstieg, wird also auch fuer Viewport/Container erreicht.
  Richtig platziert.
- **Uebersetzungen:** keine neuen sichtbaren Strings, `tr()` nicht noetig. Der genutzte
  Schluessel `placeholder.profile_name` liegt in allen 6 Locales vor (geprueft).
- **Signal/Slot:** `returnPressed` und `focus_lost` werden weiterhin verbunden, das
  `_inline_input`-Feld bleibt Instanzvariable, kein GC-Risiko durch lokale Referenzen.
- **Testort/-stil:** `tests/test_profile_bar_inline_input.py` liegt richtig, folgt der
  Namens- und Aufbaukonvention der Schwesterdatei (Modul-Docstring mit Fallbeschreibung,
  `_app()`-Helfer, Zugriff auf Privates, englische Testnamen als Saetze). Der Docstring ist
  mit 16 Zeilen etwas laenger als die 7 der Schwesterdatei, aber im selben Geist.

---

## Ergebnis

**NEEDS FIXES**

Der Kern des Fixes ist technisch richtig und — anders als es solche Begruendungen oft sind —
nachweisbar korrekt: die ensureWidgetVisible-Aussage und die Notwendigkeit der Verzoegerung
habe ich beide gemessen, nicht geglaubt. Blockierend sind:

1. MEDIUM — der Umbenennen-Pfad zeigt exakt denselben Fehler (0 px sichtbar, gemessen).
2. MEDIUM — `_inline_input` wird nach dem Timer gesetzt; der Guard haengt still am Timing.
3. MEDIUM — die Verbreiterung auf 200 px ist unbegruendet und die Konstante nur halb
   durchgezogen.

Der Rest ist Feinschliff (Benennung, Umlaute, Kommentardichte, Testluecke).
