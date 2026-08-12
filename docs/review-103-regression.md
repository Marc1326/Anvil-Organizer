# Regressionsprüfung — Issue #103 (uncommittete Änderungen in `anvil/widgets/profile_bar.py`)

Datum: 2026-08-08
Branch: fix/issue-103 (Arbeitskopie, HEAD = 08d8588)
Geprüfter Umfang: `git diff` = **nur** `anvil/widgets/profile_bar.py` (+60/-1) sowie die noch
nicht eingecheckte Testdatei `tests/test_profile_bar_inline_input.py`.

Alle Aussagen unten sind gemessen (PySide6, `QT_QPA_PLATFORM=offscreen`), nicht geschätzt.
Vergleichsbasis war jeweils die HEAD-Fassung der Datei, die parallel als eigenes Modul geladen
wurde (`git show HEAD:anvil/widgets/profile_bar.py`), damit alt und neu im selben Lauf messbar sind.

## Kurzfassung

Eine echte Regression gegenüber dem bisherigen Verhalten wurde **nicht** gefunden.
An keiner geprüften Fensterbreite und in keinem geprüften Ablauf ist die neue Fassung
schlechter als HEAD. Gefunden wurden dagegen zwei Lücken, in denen der neue Fix wieder
ausgehebelt wird, und drei Kleinigkeiten.

## Testlauf

    QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q -p no:randomly
    229 passed, 1 skipped in 2.74s

`tests/test_profile_bar_scrolling.py` (5 Tests) läuft unverändert durch,
`tests/test_profile_bar_inline_input.py` (11 Tests) ebenfalls. `python -m py_compile` sauber.
Ein Linter ist im Projekt weder konfiguriert noch im venv installiert.

## Befunde

### [MITTEL] Ein noch laufender Klick-Timer scrollt das frisch eingeblendete Feld wieder weg
- Datei: `anvil/widgets/profile_bar.py:741` (Reveal, 0 ms) gegen `:628` (`_delayed_select`, 100 ms)
  und `:635/:642` (`_click_timer`, 200 ms → `_select_profile` → `_scroll_to_tab`)
- Gemessen (30 Profile, Leiste 900 px breit):
  - Klick auf ein *anderes* Profil, danach innerhalb von 200 ms auf „+“:
    direkt nach dem Reveal sind 200 von 200 px des Feldes sichtbar, nach Ablauf des
    Klick-Timers 0 von 200 px. Das Feld hat weiterhin den Fokus und liegt weiterhin im Layout —
    der Nutzer tippt also blind, genau das Symptom aus #103.
  - Dasselbe mit `set_profiles()` weniger als 100 ms vor dem „+“ (dann feuert `_delayed_select`):
    200/200 px → 0/200 px.
- Ursache: `_start_inline_create()` stoppt die beiden laufenden Timer nicht, und
  `_scroll_to_tab()` kennt das offene Eingabefeld nicht.
- Vorschlag: in `_start_inline_create()` `self._click_timer.stop()` +
  `self._pending_click_profile = None` setzen (macht `_start_inline_rename()` bei :819 bereits so)
  und in `_scroll_to_tab()` früh zurückkehren, solange `self._inline_input is not None`.

### [MITTEL] `set_profiles()` bei offenem Eingabefeld hinterlässt eine Karteileiche — jetzt auch mit toten Pos1/Ende
- Datei: `anvil/widgets/profile_bar.py:583-596` (`set_profiles`) im Zusammenspiel mit `:715`, `:545`
- Gemessen: Wird `set_profiles()` aufgerufen, während das Inline-Feld offen ist, nimmt die Schleife
  bei :592 alle Layout-Einträge heraus. Das Feld wird dabei **nicht** gelöscht und
  `self._inline_input` **nicht** zurückgesetzt:
  - `edit.isVisible() == True`, `parent == _tabs_widget`, `layout.indexOf(edit) == -1`
    → sichtbares, freischwebendes Feld über der Leiste
  - jedes weitere `_start_inline_create()` bricht bei :715 sofort ab → der „+“-Knopf ist für
    den Rest der Sitzung tot
- **Das ist Bestand, keine Regression**: mit der HEAD-Fassung gemessen ergibt sich exakt dasselbe
  Bild (`visible=True`, `indexOf=-1`, „+“ tot). Das neue `edit.show()` macht das Feld lediglich
  einen Zyklus früher sichtbar; nach `processEvents()` war es auch vorher schon sichtbar.
- **Neu ist die Folgewirkung:** `_handle_scroll_key()` steigt bei `self._inline_input is not None`
  aus, d. h. in diesem Zustand sind Pos1/Ende dauerhaft wirkungslos (gemessen: `eventFilter` liefert
  `False`). Das neue Tastenkürzel erbt also den alten Hängezustand.
- Erreichbar u. a. über Instanzwechsel und `mainwindow.py:1902 / 4358 / 4675 / 4686`. Ein Mausklick
  auf die Oberfläche bricht das Feld vorher ab (App-Filter bei :925), ein Tastenweg wie
  Strg+M/F5 nicht zwingend.
- Vorschlag: `set_profiles()` beginnt mit „offenes Inline-/Rename-Feld abbrechen“.

### [NIEDRIG] Die Wächterprüfung im Reveal schützt nicht vor einem zerstörten C++-Objekt
- Datei: `anvil/widgets/profile_bar.py:756`
- `if edit is not self._inline_input: return` fängt Abbruch und Bestätigung korrekt ab (beide setzen
  `_inline_input = None`, `deleteLater()` wirkt ohnehin erst später) — gemessen und in Ordnung.
  Nicht abgefangen ist der Fall, dass `edit` zerstört wird, während `_inline_input` noch darauf zeigt:
  dann läuft der Rumpf und wirft `RuntimeError: Internal C++ object (_FocusOutLineEdit) already deleted`
  (mit `shiboken6.delete()` nachgestellt und ausgelöst).
- Praktisch erreichbar nur, wenn die ProfileBar samt Kindern innerhalb desselben Ereigniszyklus
  stirbt (Fenster schließen). `close()` + `deleteLater()` + 50 ms Ereignisschleife hat den Fehler
  im Test **nicht** ausgelöst — Restrisiko, kein Nachweis.
- Vorschlag: Kontext-Überladung `QTimer.singleShot(0, self, lambda: ...)` nutzen oder zusätzlich
  `shiboken6.isValid(edit)` prüfen.

### [NIEDRIG] Pos1/Ende vom Ziffernblock lösen das Scrollen nicht aus
- Datei: `anvil/widgets/profile_bar.py:543`
- `event.modifiers() != Qt.KeyboardModifier.NoModifier` verwirft auch `KeypadModifier`. Qt setzt den
  bei Pos1/Ende vom Ziffernblock (Num-Lock aus). Auf dieser Taste passiert nichts.
- Vorschlag: `KeypadModifier` aus der Prüfung ausklammern.

### [NIEDRIG] Zwei verschiedene Feldbreiten für dieselbe Optik
- Datei: `anvil/widgets/profile_bar.py:723` (neu 200 px) gegen `:833` (Umbenennen: `max(140, tab.width())`)
- Die neue Konstante `INLINE_INPUT_WIDTH` gilt nur beim Anlegen. Anlegen und Umbenennen sehen damit
  unterschiedlich aus. Rein kosmetisch.

## Ausdrücklich geprüft und unauffällig

- **Aufrufer der ProfileBar.** Einziger Verwender ist `anvil/mainwindow.py` (`ProfileBar(self)` bei
  :236, `set_profiles` bei :1902/4358/4675/4686/7077, `update_active_count` :2263,
  `current_profile()` :7436, Direktzugriffe auf `_tabs`/`_active_profile` :4445-4454/4673).
  Keine dieser Stellen hängt an der Feldbreite oder am Eingabefeld.
- **Layoutbreite der Nachbarn.** Die Pillen-Gruppe wird bei offenem Feld breiter als vorher
  (gemessen bei 900 px Leiste: Container 257 → 461 px, Aktionsknöpfe rücken von x=271 auf x=475).
  Das ist der beabsichtigte Fix (vorher schnitt der Container das Feld ab). Die Knöpfe bleiben
  vollständig sichtbar; bei 500 px und 360 px Leistenbreite ändert sich gar nichts, weil der
  Container dort ohnehin durch den Platz begrenzt ist. Kein Verdrängen, kein Abschneiden.
- **Sichtbarkeit über Fensterbreiten (alt gegen neu, jeweils gemessen).**

  | Breite | Profile | ALT sichtbar | NEU sichtbar |
  |---|---|---|---|
  | 1200 | 3 | 32/140 | 200/200 |
  | 900 | 3 | 32/140 | 200/200 |
  | 600 | 3 | 32/140 | 200/200 |
  | 500 | 3 | 7/140 | 200/200 |
  | 420 | 3 | 0/140 | 146/200 (Sichtfenster nur 146 px) |
  | 1200 | 30 | 0/140 | 200/200 |
  | 900 | 30 | 0/140 | 200/200 |
  | 600 | 30 | 0/140 | 200/200 |
  | 420 | 30 | 0/140 | 146/200 |

  Neu ist nirgends schlechter als alt. Unterhalb von rund 500 px Leistenbreite ist das Sichtfenster
  schmaler als 200 px, dort bleibt das Feld zwangsläufig angeschnitten (vorher war es dort gar nicht zu sehen).
- **Flackern durch das frühe `show()`.** Kein Flackern messbar: unmittelbar nach
  `_start_inline_create()` — also noch vor der Ereignisschleife — steht die Geometrie bereits
  endgültig auf `(2810, 0, 200, 34)` und ändert sich durch `processEvents()` nicht mehr. Grund:
  `_update_container_width()` ruft direkt danach `adjustSize()` und aktiviert damit das Layout
  synchron. Zwischen `show()` und `adjustSize()` wird nicht gezeichnet.
- **Doppelte Anzeige.** `_cancel_inline_create` (:798) und `_finish_inline_create` (:769) hängen das
  Feld sauber aus (`setParent(None)` + `deleteLater()`), setzen `_inline_input = None` und rufen
  `_update_container_width()`. Beide sind gegen Doppelaufruf abgesichert
  (`_inline_confirmed`, `_inline_input is None`). Kein zweites sichtbares Feld nachweisbar.
- **Anwendungsweiter eventFilter / Pos1 und Ende.** Im gesamten Projekt gibt es außerhalb dieser
  Datei **keine** Verwendung von `Qt.Key_Home` / `Qt.Key_End` (nur in den Tests) und **keinen**
  Tastenkürzel-Eintrag mit Pos1/Ende (`setShortcut`-Liste: Strg+M, Strg+N, F5, Strg+F, Strg+E,
  Strg+I, Strg+S, Strg+H). `mainwindow.eventFilter` (:1482) reagiert nur auf ContextMenu und Alt,
  `mainwindow.keyPressEvent` (:881) reicht nur weiter.
  Gegenprobe gemessen: ein fremdes `QLineEdit` mit Fokus bekommt die Ende-Taste weiterhin
  (Cursor springt auf Position 10), die Profilleiste scrollt dabei nicht (Wert bleibt 0).
  `_is_own_scroll_target` bleibt eng genug — Modliste, Suchfeld, Downloads, Tabellen und Dialoge
  liegen alle außerhalb.
  Der reguläre Weg funktioniert: fokussierter Profil-Tab + Ende → Scrollwert 2214 = Maximum.
- **Gelöschte Tabs in `self._tabs`.** Vergleich `obj in self._tabs` mit einem hart gelöschten Tab
  löst weder Ausnahme noch Absturz aus (gemessen). Da die neue Tastenprüfung diesen Vergleich nun
  bei *jedem* Tastendruck der Anwendung durchläuft, wurde das eigens geprüft. `set_profiles()`
  löscht die Tabs per `deleteLater()` und leert die Liste unmittelbar danach — keine Leichen.
- **Übersetzungen.** Der Diff bringt keinen neuen sichtbaren Text, nur Kommentare und eine
  Konstante. `tr()`-Bestand unverändert, keine Locale-Datei betroffen.
- **Architektur-Regeln** (Mod-Dateien, `.mods/`-Struktur, Frameworks, `active_mods.json`,
  globale API): vom Diff nicht berührt, reine GUI-Änderung an der Profilleiste.

## Nicht geprüft

`./restart.sh` wurde bewusst nicht ausgeführt: der Start schreibt `modlist.txt` der echten Instanz
neu, das wäre ein Eingriff in Produktionsdaten. Alle Messungen liefen offscreen gegen frisch
erzeugte ProfileBar-Objekte.

## Ergebnis

Keine Regression nachweisbar. Vor dem Commit sollten die beiden MITTEL-Befunde behoben werden,
weil der Fix aus #103 sonst in erreichbaren Abläufen (schneller Klick auf ein Profil und dann „+“)
wieder wirkungslos ist.
