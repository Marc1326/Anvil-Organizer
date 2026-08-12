# Review Issue #103 — Runde 3 (Nachprüfung)

Datum: 2026-08-08
Branch: `fix/issue-103`
Geprüft: `git diff` auf `anvil/mainwindow.py`, `anvil/widgets/profile_bar.py`,
`tests/test_profile_create_feedback.py` sowie die unversionierten Dateien
`tests/conftest.py` und `tests/test_profile_bar_inline_input.py`

## Vorgehen

- Runde-2-Bericht `docs/review-103-bugs-runde2.md` Punkt für Punkt nachgeprüft
- Kompletten Diff gelesen, dazu `profile_bar.py` Zeilen 500–950 und
  `mainwindow.py:4340-4482` im Zusammenhang
- Architektur-Doku `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md` gelesen
- Zehn Offscreen-Messskripte gefahren (echte Pixelwerte, `shiboken6.isValid`,
  `qInstallMessageHandler`, Aufruf-Protokoll auf `_update_container_width`)
- Sechs Mutationen ins Produktivfile gesetzt und die Suite jeweils laufen lassen,
  danach Datei wiederhergestellt (Wiederherstellung verifiziert: 346 Zeilen, 23 Tests)
- Volle Suite 20-mal gefahren, die neue Testdatei zusätzlich 13-mal allein
- `python -m py_compile` auf allen fünf Dateien sauber; im Projekt ist kein
  Linter/Typechecker konfiguriert (`pyproject.toml` hat keinen `[tool.ruff]`/`[tool.mypy]`)

---

## Teil 1 — Status der Befunde aus Runde 2

| # | Befund Runde 2 | Status | Beleg |
|---|---|---|---|
| N1 | Pillen-Gruppe bleibt nach dem Umbenennen zu breit | **BEHOBEN** | 3 Profile, modern: vorher **260**, mit Feld **387**, nach Abbruch **260**, nach Bestätigen ("Vanilla"→"Kurz") **247** = exakt `sizeHint()+8`. Auch beim Verlängern korrekt: "Vanilla" → langer Name ergibt **504** statt der alten 387. |
| N2 | Nach Abbruch bleibt die Leiste am rechten Ende stehen | **BEHOBEN für das Anlegen** | 30 Profile: Scroll vor "+" 0, mit Feld 2387, nach Abbruch **0**, aktiver Tab **80 von 80 px** sichtbar. Auch im klassischen Theme (Scroll 0, 80/80 px). — **Für das Umbenennen ist daraus ein neuer Fehler geworden, siehe N5.** |
| N3 | Reentranter Aufräumblock in `set_profiles` nicht erkennbar | **BEHOBEN** | Der Kommentar `profile_bar.py:588-589` benennt jetzt beide Gründe für die Reihenfolge ("+"-Knopf lahm, `tab.show()` auf totem Objekt). Nachgemessen: nach `set_profiles` bei offenem Feld ist das alte Feld ungültig, alle 30 alten Tabs sind zerstört, 30 neue existieren, keine unsichtbaren Tabs, **keine Qt-Meldung**. |
| N4 | Rück-Reveal nur im modernen Theme | **teilweise** | `resizeEvent` reveal't jetzt themenunabhängig, `_update_container_width` weiterhin nur bei `_plus_inline`. Für `_delayed_select` hängt das klassische Theme also weiter allein am frühen Ausstieg in `_scroll_to_tab`. Folgenlos, unverändert LOW. |

### Restpunkte aus Runde 1, die weiter offenstehen

| # | Punkt | Status |
|---|---|---|
| 6 | `QTimer.singleShot(100, _delayed_select)` in `set_profiles:641` ohne Kontextobjekt | unverändert (Stilhinweis) |
| 7 | Redundanter Feld-Guard in `_handle_scroll_key` | unverändert, defensiv, schadet nicht |
| T3 | `_plus_inline` wird im Test nach `__init__` gesetzt | unverändert |
| T4 | Keine Aufräum-Fixture, kein `close()` | **unverändert — und jetzt die Ursache von N6** |
| T5 | Docstring "35 px of 140" (Testdatei Zeile 90) | unverändert; beschreibt den historischen Bug, vertretbar |

---

## Teil 2 — Die vier ausdrücklich gestellten Fragen

### 1. `_scroll_to_active_tab` — zerstörte Widgets oder unerwünschtes Scrollen?

**Zerstörte Widgets: nein.** Gemessen mit `shiboken6.isValid` und Qt-Meldungshandler:

- Der einzige reentrante Pfad ist der Aufräumblock in `set_profiles`. Dort löst
  `field.setParent(None)` einen `focusOutEvent` aus, also läuft `_cancel_inline_create`
  bzw. `_cancel_inline_rename` mitten in der Schleife — und damit auch das neue
  `_scroll_to_active_tab()`. Zu diesem Zeitpunkt stehen die **alten** Tabs noch
  vollständig im Layout (der Aufräumblock steht vor der Lösch-Schleife), also greift
  `ensureWidgetVisible` auf lebende Objekte zu.
- `_finish_inline_rename` und `_cancel_inline_rename` rufen `_scroll_to_active_tab()`,
  bevor `profile_renamed` ausgelöst wird. Der einzige Empfänger
  (`mainwindow._on_profile_renamed`) ruft nur im Fehlerfall `set_profiles()`, also
  erst danach. Kein Zugriff auf Gelöschtes.
- `_scroll_to_active_tab()` bei leerem `_active_profile` (frisch konstruierte Leiste)
  läuft ins Leere und kehrt zurück. Geprüft, kein Fehler.
- In allen Messläufen: **keine einzige Qt-Meldung**, keine `RuntimeError`.

**Unerwünschtes Scrollen: ja — siehe N5.**

### 2. Signaländerung `Signal(str)` → `Signal(str, str)`

- Sender: nur `profile_bar.py:789` und `:795`, beide auf zwei Argumente umgestellt.
- Empfänger: nur `mainwindow.py:260-261` → `_on_profile_create_rejected`, Signatur
  angepasst. Repoweite Suche über `*.py`, `*.ui`, `*.json` findet keine weitere
  Verbindung, keine Plugin-Nutzung.
- Tests: `test_profile_create_feedback.py:86` verbindet mit zwei Parametern.
- **`tr()` mit `name=` auf einem Schlüssel ohne `{name}`:** unkritisch.
  `toast.profile_invalid_name` enthält keinen Platzhalter; `str.format` ignoriert
  überzählige Schlüsselwortargumente. Zusätzlich fängt `Translator.t`
  (`translator.py:94-98`) `KeyError`/`ValueError` ab und liefert dann den
  unformatierten Text. In allen **sieben** Locales (de, en, es, fr, it, pt, **ru**)
  geprüft: `profile_invalid_name` ohne Klammerrest, `profile_exists` mit
  eingesetztem Namen.
- Format-Injection über den Profilnamen ist ausgeschlossen (ein einziger
  `format`-Durchlauf): `{name}`, `{0}`, `{`, `}`, `%s`, `a{b}c` kommen alle wörtlich
  im Toast an.

### 3. `resizeEvent` → `_reveal_input` während des Aufbaus?

**Nein.** `_inline_input` und `_rename_input` werden in `__init__` Zeile 314/316
gesetzt, also vor jedem Widget. Mit einem Zähler auf `resizeEvent` gemessen:
während `ProfileBar()` fällt **kein einziger** `resizeEvent` an (auch `setFixedHeight(44)`
in Zeile 308 löst keinen aus). Halbfertige Widgets sind damit nicht erreichbar; der
`None`-Guard vor `_reveal_input` trägt zusätzlich.

Funktional geprüft: Fenster von 900 auf 300 px verkleinert, Feld 200 px, Sichtfenster
68 px → linke Kante bündig, 68 von 68 px sichtbar, und zwar bereits **direkt im
resizeEvent**, ohne zusätzliches `processEvents()`.

### 4. Ist `_update_container_width` in `_finish_inline_rename` an der richtigen Stelle?

**Ja.** Die Reihenfolge stimmt in beiden Richtungen:

- **nach** `tab.setText(new_name)` und `tab.show()` — sonst würde die alte Beschriftung
  gemessen. Schrittweise nachgemessen: `sizeHint` 379 (Feld offen) → 252
  (`setParent(None)`) → 239 (`setText`) — der Wert ist zum Zeitpunkt des Aufrufs frisch.
- **vor** `profile_renamed.emit(...)` — der Empfänger kann im Fehlerfall
  `set_profiles()` aufrufen und alles neu aufbauen; ein Aufruf danach wäre sinnlos.
- `_scroll_to_active_tab()` steht nach der Aktualisierung von `_active_profile`,
  findet den umbenannten Tab also. (Dass es der falsche Zielpunkt ist, ist ein
  eigener Befund — N5.)

---

## Teil 3 — Neue Befunde

### [MEDIUM] N5 — Nach dem Umbenennen springt die Leiste weg vom umbenannten Profil

- Datei: `anvil/widgets/profile_bar.py:904` (`_finish_inline_rename`) und
  `:923` (`_cancel_inline_rename`), Methode `:826-831`
- Problem: Beide Endpunkte rufen `_scroll_to_active_tab()`. Die Methode scrollt zum
  **aktiven** Profil — nicht zu dem Tab, den der Nutzer gerade bearbeitet hat.
  Wer ein nicht-aktives Profil umbenennt, verliert es sofort aus dem Bild.
- Gemessen (30 Profile, aktiv "Default", Doppelklick auf `_tabs[25]`, Sichtfenster 626 px):

  | Schritt | Scrollwert | Tab 25 sichtbar |
  |---|---|---|
  | vor dem Umbenennen | 1857 | 91 von 91 px |
  | Feld offen | 1916 | Feld 200 px voll sichtbar |
  | nach **Bestätigen** | **0** | **0 von 106 px** |
  | nach **Abbruch (Esc)** | **0** | **0 von 91 px** |

- Neu durch diesen Diff: vor Runde 3 wurde in beiden Pfaden gar nicht gescrollt, die
  Leiste blieb bei 1857 stehen und der umbenannte Tab war weiter zu sehen.
- Betrifft genau das Szenario aus Issue #103 (viele Profile). Beim Anlegen ist das
  Verhalten dagegen richtig (das Feld sitzt am Ende neben "+", die Rückkehr zum
  aktiven Profil ist dort erwünscht) — deshalb ist nicht die Methode falsch, sondern
  ihr Einsatzort.
- Von keinem Test abgedeckt: `test_container_shrinks_back_after_renaming` und
  `…_after_confirming_a_rename` benutzen `FEW_PROFILES`, da passt alles ins
  Sichtfenster und es wird nie gescrollt.
- Fix: in den beiden Umbenennen-Pfaden statt `_scroll_to_active_tab()` den bearbeiteten
  Tab anzeigen, also `self._scroll_to_tab(tab)` (die Feldzeiger sind an der Stelle
  bereits `None`, der frühe Ausstieg greift also nicht mehr). Im Anlege-Pfad bleibt
  `_scroll_to_active_tab()` richtig. Dazu ein Test mit `MANY_PROFILES`, der nach
  Bestätigen **und** nach Abbruch die Sichtbarkeit des umbenannten Tabs prüft.

### [MEDIUM] N6 — Die Testsuite ist unzuverlässig (zufällige Rotläufe)

- Datei: `tests/test_profile_bar_inline_input.py:24-32` (`_bar`), zusätzlich
  `tests/test_profile_create_feedback.py:73-97`
- Problem: `_bar()` erzeugt für jeden Test eine neue `ProfileBar`, ruft `show()` und
  lässt sie danach **stehen** — kein `close()`, kein `deleteLater()`, keine Fixture.
  Jede dieser Leisten hängt bis Prozessende als eigenes Fenster in der gemeinsamen
  `QApplication` und installiert in `__init__` einen anwendungsweiten Ereignisfilter.
  Wird ein weiteres Fenster gezeigt, verliert das offene Eingabefeld der vorherigen
  Leiste den Fokus → `focus_lost` → `_cancel_inline_create`. Die Zustellung ist
  asynchron; landet sie innerhalb eines Tests, der selbst gerade eine echte
  Ereignisschleife laufen lässt (`_settle()`), wird dessen eigenes Feld geschlossen und
  `bar._inline_input` ist `None`.
- Gemessen:
  - **volle Suite, 20 Läufe: 3 rot** — immer
    `test_scroll_keys_are_left_alone_while_typing_a_name`
    (`assert True is False`, weil das Feld weg ist und der Guard in
    `_handle_scroll_key` nicht mehr greift)
  - **Testdatei allein, 13 Läufe: jedes Mal 1 bis 4 rot** —
    `test_the_deferred_selection_does_not_scroll_the_field_away`,
    `test_a_pending_tab_click_does_not_scroll_the_field_away`,
    `test_resizing_keeps_an_open_field_in_view`,
    `test_scroll_keys_are_left_alone_while_typing_a_name`
    (`AttributeError: 'NoneType' object has no attribute 'mapTo'`)
  - Gegenprobe: mit entfernten Runde-3-Tests **7 von 12** vollen Läufen rot. Die
    Ursache liegt also nicht in den neuen Tests, sie verschieben nur das Timing.
    Der Mangel steckt seit Runde 1 in der Datei (dort als T4 notiert) und ist
    inzwischen scharf.
- Kein Produktivfehler: in der Anwendung existiert genau eine `ProfileBar` in genau
  einem Fenster. Der Schaden ist trotzdem real — `pytest tests/` schlägt zufällig
  fehl, und `pytest tests/test_profile_bar_inline_input.py` allein ist praktisch
  immer rot.
- Fix: eine Fixture, die jede erzeugte Leiste am Testende `close()` + `deleteLater()`
  und die Ereignisschleife einmal leerlaufen lässt (`_bar` gibt die Leiste dafür an
  eine Liste); alternativ die betroffenen Tests unabhängig vom Fokus machen, indem
  das Feld nicht über `_start_inline_create()` + Fokus, sondern über einen
  Zustandsaufbau ohne Fensterwechsel geprüft wird.

### [LOW] N7 — Der Test zum Schrumpfen prüft nur die Richtung, nicht den Wert

- Datei: `tests/test_profile_bar_inline_input.py:229-240`
- `assert bar._tab_container.maximumWidth() <= before` geht nur auf, weil der neue Name
  ("Kurz") kürzer ist als der alte ("Vanilla"). Bei einer Umbenennung auf einen
  **längeren** Namen ist der korrekte Wert größer als `before` (gemessen 504 gegen 260),
  der Test würde also bei richtigem Code fehlschlagen.
- Er fängt die Regression aus N1 zwar (Mutationstest bestätigt), beschreibt aber nicht,
  was eigentlich gilt.
- Fix: gegen `bar._tabs_widget.sizeHint().width() + 8` prüfen statt gegen `before`.
  Dann trägt derselbe Test auch den Fall "längerer Name".

### [LOW] N8 — Der Kommentar zu `INLINE_INPUT_WIDTH` nennt eine falsche Zahl

- Datei: `anvil/widgets/profile_bar.py:31-33` — "der längste Platzhalter (es) misst 141 px".
- Nachgemessen mit der Schrift des Feldes: es 132 px, pt 118, ru 112, fr 110, it 105,
  en 101, de 89. Der spanische ist tatsächlich der längste, die 141 px stimmen nicht.
- Die 200 px sind für alle sieben Locales ausreichend (größter Bedarf 132 + 24 = 156).
  Nur die Zahl im Kommentar ist irreführend.

### [INFO] Einmalige, nicht reproduzierbare Beobachtung

Im allerersten Messlauf blieb `maximumWidth` nach `_finish_inline_rename` bei 387
stehen statt bei 247 (und bei 387 statt 504 im Fall "längerer Name") — so, als hätte
`_update_container_width()` in `_finish_inline_rename` nicht gewirkt. In **75 weiteren
Läufen** (15 Einzelprozesse, 60 Wiederholungen in einem Prozess, mit und ohne
`processEvents`, mit und ohne vorherige Leiste) trat es kein zweites Mal auf; ein
Protokoll auf `_update_container_width` zeigt seither immer den korrekten Wert.
Ich kann daraus keinen Befund machen und führe es nur der Vollständigkeit halber auf.

---

## Teil 4 — Mutationstests (fangen die neuen Tests wirklich etwas?)

Jede Mutation einzeln ins Produktivfile gesetzt, volle Suite gefahren, danach
zurückgesetzt:

| Mutation | Ergebnis | Auslösender Test |
|---|---|---|
| `_update_container_width()` aus `_finish_inline_rename` entfernt | **gefangen** | `test_container_shrinks_back_after_confirming_a_rename` |
| `_update_container_width()` aus `_cancel_inline_rename` entfernt | **gefangen** | `test_container_shrinks_back_after_renaming` |
| `_scroll_to_active_tab()` aus `_cancel_inline_create` entfernt | **gefangen** | `test_the_active_profile_comes_back_into_view_after_cancelling` (+3 weitere durch Zustandskopplung) |
| `_reveal_input` aus `resizeEvent` entfernt | **gefangen** | `test_resizing_keeps_an_open_field_in_view` |
| Name im Signal durch `"{name}"` ersetzt | **gefangen** | `test_the_rejection_carries_the_name_the_message_needs` |
| `_scroll_to_active_tab()` aus `_finish_inline_rename` entfernt | **gefangen** | `test_container_shrinks_back_after_renaming` (+1) |

Alle sechs Mutationen werden erkannt. Auffällig ist, dass drei davon Tests umwerfen,
die mit der mutierten Stelle nichts zu tun haben — das ist dieselbe Zustandskopplung
wie in N6 und macht die Fehlersuche im Ernstfall irreführend.

---

## Teil 5 — Projektregeln und Architektur

| Punkt | Ergebnis |
|---|---|
| Mod-Dateien nur per Symlink ins Game-Verzeichnis | nicht berührt — reine GUI-Änderung an der Profil-Leiste |
| Ordnerstruktur in `.mods/` unverändert | nicht berührt |
| Frameworks nicht in `.mods/`/modlist.txt | nicht berührt |
| `active_mods.json` bei Rename/Delete in allen Profilen | nicht berührt; der Diff ändert nichts an `_on_profile_renamed`s Plattenlogik (`mainwindow.py:4422-4481`), nur die Signatur von `_on_profile_create_rejected` |
| Nur globale API, keine Legacy-per-Profil-modlist.txt | nicht berührt |
| Architektur-Doku gelesen | ja (`anvil-wiki/dev-notes/ARCHITEKTUR.md`) |
| MO2-Referenz | `/home/mob/Projekte/mo2-referenz/src/` enthält keine Datei zur Profil-Leiste; laut Architektur-Doku Abschnitt 11 entspricht `profile.cpp` der Profil-Logik in `mainwindow.py`, die dieser Diff nicht anfasst. Ein Vergleich ist für eine Scroll-/Eingabefeld-Änderung nicht einschlägig. |
| Keine hartcodierten Pfade | OK |
| Kein neues `setStyleSheet()` | OK — die Aufrufe sind Bestand |
| `tr()`-Schlüssel in allen Locales | OK — keine neuen Schlüssel; `toast.profile_exists` und `toast.profile_invalid_name` liegen in allen 7 Locales vor und wurden in allen 7 gerendert |
| Signalverbindungen | OK — `profile_create_rejected` hat genau einen Empfänger, Signatur passt |
| Importe | OK — `QKeyEvent` ergänzt und genutzt, keine ungenutzten Zusätze |
| `python -m py_compile` | sauber (5 Dateien) |
| Cover-Bilder / redprelauncher / REDmod / BG3 | nicht berührt |

---

## Ergebnis

**NEEDS FIXES**

Die Nachbesserungen aus Runde 3 sitzen inhaltlich: N1 ist in beiden Endpunkten
belegt behoben (260/247/504 statt der stehengebliebenen 387), N2 ist für das Anlegen
behoben, N3 ist dokumentiert, die Signaländerung ist vollständig und in allen sieben
Sprachen unkritisch, `resizeEvent` ist während des Aufbaus nicht erreichbar, und
`_update_container_width` steht in `_finish_inline_rename` an der richtigen Stelle.
Alle sechs Mutationen werden von den Tests gefangen.

Offen sind zwei Punkte:

1. **N5 (MEDIUM)** — `_scroll_to_active_tab()` in den beiden Umbenennen-Pfaden scrollt
   zum aktiven statt zum bearbeiteten Profil. Wer ein nicht-aktives Profil umbenennt,
   sieht es danach nicht mehr (gemessen: 0 von 106 px). Das ist eine neue, sichtbare
   Verhaltensänderung aus dieser Runde und trifft genau den Fall vieler Profile.
2. **N6 (MEDIUM)** — Die Testdatei kennt keine Aufräum-Fixture. Die volle Suite ist in
   3 von 20 Läufen rot, die Datei allein in jedem einzelnen Lauf. Ein Test, der
   zufällig fehlschlägt, blockiert jede spätere Arbeit an dieser Stelle.

N7 und N8 sind Kleinkram und können mitlaufen. Erst wenn N5 und N6 erledigt sind
(und `pytest tests/` mehrfach hintereinander grün bleibt), ist der Stand sauber.
