# Regressionsprüfung Runde 3 — Issue #103

Datum: 2026-08-08
Branch: fix/issue-103 (Arbeitskopie, HEAD = 08d8588)
Geprüfter Umfang: `git diff` = `anvil/widgets/profile_bar.py` (+101/-8), `anvil/mainwindow.py` (+2/-2),
`tests/test_profile_create_feedback.py` (+25) sowie die noch nicht eingecheckten Dateien
`tests/conftest.py` und `tests/test_profile_bar_inline_input.py`.

Alle Zahlen sind gemessen (PySide6, `QT_QPA_PLATFORM=offscreen`), nicht geschätzt.
Vergleichsbasis war wieder die HEAD-Fassung, die im selben Lauf als eigenes Modul geladen wurde
(`git show HEAD:anvil/widgets/profile_bar.py` → `head_profile_bar.py`), damit ALT und NEU direkt
nebeneinander messbar sind. Messkripte liegen im Scratchpad (`r3base.py`, `s1_kapsel.py` …
`s20_edge2.py`). `./restart.sh` wurde auftragsgemäß nicht ausgeführt.

## Kurzfassung

Die MITTEL-Regression aus Runde 2 (aufgeblähte Pillen-Kapsel nach dem Umbenennen) ist **behoben**,
ebenso zwei der vier NIEDRIG-Punkte. Die Signaländerung ist sauber und vollständig nachgezogen.
Es gibt **keine Endlosschleife** und **keinen Startfehler** durch das neue `resizeEvent`.

Zwei neue Punkte sind dazugekommen:

* **[HOCH] Die Testsuite ist instabil geworden.** `pytest tests/ -q` fällt in rund einem Drittel
  der Läufe durch — ausschließlich wegen der neu hinzugefügten Datei
  `tests/test_profile_bar_inline_input.py`. Ohne diese Datei: 8 von 8 Läufen grün.
* **[MITTEL] Die von Hand gewählte Scrollposition geht bei jedem Feldabschluss verloren.**
  Das neue `_scroll_to_active_tab()` reißt die Leiste unbedingt zum aktiven Profil zurück — auch
  dann, wenn der Nutzer vorher selbst woanders hingescrollt hatte und der Reveal die Ansicht gar
  nicht verschoben hat.

## Testlauf

    .venv/bin/python -m pytest tests/ -q
    → 20 Läufe: 12× "242 passed, 1 skipped", 8× "1 failed, 241 passed"
    → weitere 18 Läufe: 13 grün, 5 rot (bis zu 3 Fehlschläge gleichzeitig)

    .venv/bin/python -m pytest tests/ -q --ignore=tests/test_profile_bar_inline_input.py
    → 8 von 8 Läufen: "219 passed, 1 skipped"

`python -m py_compile` auf `profile_bar.py`, `mainwindow.py`, `tests/conftest.py`,
`tests/test_profile_bar_inline_input.py` und `tests/test_profile_create_feedback.py` ist sauber.

## Die Punkte aus Runde 2

### [MITTEL] Kapsel bleibt nach dem Umbenennen aufgebläht → **geschlossen**

Gemessen mit 3 Profilen („Default“, „Vanilla“, „Test“) bei 900 px, Format maxW/benötigt:

| Zeitpunkt | ALT (HEAD) | NEU Runde 2 | NEU Runde 3 |
|---|---|---|---|
| Start | 260/260 | 260/260 | 260/260 |
| Umbenennen-Feld offen | 260/327 | 387/379 | 387/387 |
| nach Escape | 260/260 | 387/252 | **260/260** |
| nach Enter („Xy“) | 260/234 | 387/226 | **234/234** |

Der erste Aktionsknopf steht nach dem bestätigten Umbenennen wieder bei x=248 statt bei x=401
(Runde 2). ALT lässt die Kapsel bei 260 stehen, obwohl nur 234 gebraucht werden — NEU ist hier
also sogar genauer als HEAD.

In der vollen Ablaufmatrix (30 Profile und 4 Profile, je 13 Schritte) gilt für NEU in **jedem**
Schritt `maximumWidth == sizeHint+8`. ALT weicht nach jedem Umbenennen ab (2920 statt 2899
bzw. 390 statt 386).

### [NIEDRIG] Nach dem Abbrechen bleibt die Leiste am Feld stehen → **geschlossen**

Gemessen, 30 Profile, aktiv „Default“ ganz links, 900 px:

| Ablauf | ALT Scroll / Default sichtbar | NEU Scroll / Default sichtbar |
|---|---|---|
| Start | 0 / 80 von 80 px | 0 / 80 von 80 px |
| nach „+“ | 0 / Feld 0 von 140 px | 2387 / Feld 200 von 200 px |
| nach Escape | 0 / 80 von 80 px | **0 / 80 von 80 px** |
| Umbenennen Tab 25, danach Escape | 0 / 80 von 80 px | **0 / 80 von 80 px** |

Siehe aber den neuen MITTEL-Befund weiter unten: die Rückkehr ist **zu** unbedingt.

### [NIEDRIG] Größenänderung schiebt ein offenes Feld aus dem Bild → **geschlossen**

Gemessen, 30 Profile, Feld offen und fokussiert, sichtbarer Anteil des Feldes:

| Breitenwechsel | Viewport | ALT | NEU (Anlegen) | NEU (Umbenennen) |
|---|---|---|---|---|
| 900 → 1400 | 1126 px | 0/140 | 200/200 | 200/200 |
| 900 → 600 | 326 px | 0/140 | **200/200** | **200/200** |
| 900 → 400 | 126 px | 0/140 | **126/200** | **126/200** |
| 900 → 300 | 68 px | 0/140 | **68/200** | **68/200** |
| 900 → 120 | 68 px | 0/140 | **68/200** | **68/200** |

Bei 400 px und darunter ist der Viewport schmaler als das Feld; dann greift der linke Zweig in
`_reveal_input` und es wird so viel gezeigt, wie überhaupt passt. Das ist das Bestmögliche.
Auch im klassischen Theme (`_plus_inline = False`) greift es jetzt: 900/1300/600 px → jeweils
200 von 200 px sichtbar, ALT jeweils 0 von 140.

Bemerkenswert: `_update_container_width()` steigt bei `not self._plus_inline` früh aus
(`profile_bar.py:722`) und ruft dort `_reveal_input` nie. Dass das klassische Theme trotzdem
funktioniert, liegt allein an den beiden direkten Aufrufen in `_start_inline_*` und im neuen
`resizeEvent`. Das ist kein Fehler, aber eine stille Abhängigkeit.

### [NIEDRIG] Aufräumblock in `set_profiles` ruft sich über `focus_lost` selbst auf → **weiterhin offen, harmlos**

Unverändert vorhanden (`profile_bar.py:590-596`). Gemessen (Aufrufzähler, ALT vs. NEU,
Escape mit fokussiertem Feld):

| Ablauf | ALT | NEU |
|---|---|---|
| Escape beim Anlegen | `_cancel_inline_create` 2×, `_update_container_width` 2× | `_cancel_inline_create` 2×, `_update_container_width` 2×, `_scroll_to_active_tab` 2×, `_scroll_to_tab` 2× |
| Escape beim Umbenennen | `_cancel_inline_rename` 2× | `_cancel_inline_rename` 2×, `_update_container_width` 2×, `_scroll_to_active_tab` 2×, `_scroll_to_tab` 2× |

Die Doppelausführung gibt es also schon in HEAD; neu ist nur, dass `_scroll_to_active_tab`
mitläuft. Beide Durchläufe sind idempotent, die Verschachtelung bleibt bei 4, der Endzustand ist
in ALT und NEU identisch (`inline=None`, `rename=None`, `renametab=None`, Tab wieder sichtbar).
Kein Absturz, keine Schleife.

### [NIEDRIG] 100-ms-Timer in `set_profiles` ohne Kontextobjekt → **weiterhin offen**

`profile_bar.py:641` ist unverändert `QTimer.singleShot(100, _delayed_select)`. Gemessen: Leiste
nach `set_profiles()` sofort zerstört (`shiboken6.delete`), dann 400 ms Ereignisschleife →
`RuntimeError` im Log. **Identisch in ALT und NEU** — Bestand, keine Regression. Die beiden
Reveal-Timer haben ihr Kontextobjekt behalten (gemessen: Leiste mit offenem Feld zerstört, danach
300 ms Ereignisschleife → kein `RuntimeError`, weder in ALT noch in NEU).

## Neue Befunde

### [HOCH] Die neue Testdatei macht `pytest tests/` unzuverlässig

- Datei: `tests/test_profile_bar_inline_input.py` (neu, noch nicht eingecheckt)
- Gemessen über 38 vollständige Läufe von `pytest tests/ -q`: 13 rot, 25 grün (≈ 34 % Fehlerquote).
  Ohne die Datei (`--ignore=tests/test_profile_bar_inline_input.py`): 8 von 8 grün, immer
  „219 passed, 1 skipped“. Die Instabilität kommt also ausschließlich aus dieser Datei.
- Beobachtete Fehlschläge (wechselnd, teils mehrere gleichzeitig):
  * `test_the_deferred_selection_does_not_scroll_the_field_away` (am häufigsten)
  * `test_a_pending_tab_click_does_not_scroll_the_field_away`
  * `test_the_active_profile_comes_back_into_view_after_cancelling`
  * `test_scroll_keys_are_left_alone_while_typing_a_name`
  * `test_resizing_keeps_an_open_field_in_view`
- Ursache, nachgewiesen mit einem Haken in `_FocusOutLineEdit.focusOutEvent` und einem Stapel-
  auszug in `_cancel_inline_create`: Während des echten Ereignisumlaufs in `_settle()` bekommt das
  Eingabefeld ein `FocusOut` mit **`ActiveWindowFocusReason`** — die Offscreen-Plattform stellt die
  Fensteraktivierung verzögert zu. `focus_lost` feuert, `_cancel_inline_create` räumt das Feld weg,
  und das neue `_scroll_to_active_tab()` zieht die Leiste auf 0 zurück. Danach ist entweder
  `bar._inline_input is None` (Test bricht mit `AttributeError` ab) oder das Feld ist 0 statt 200 px
  sichtbar.
- Spur aus dem nachgestellten Testfall (10 Durchgänge, gleicher Code wie der Test):

  | Durchgang | Scroll nach Reveal | Scroll am Ende | Feld sichtbar |
  |---|---|---|---|
  | 0–3, 8, 9 | 2774 | 0 | Feld weggeräumt |
  | 4–7 | 2774 | 2421 | 200 px |

- Gegenmaßnahmen, die ich gemessen habe und die **nicht** helfen: vorherige Fenster schließen
  (3 von 8 Läufen weiterhin kaputt), `bar.activateWindow()` vor dem Öffnen (7 von 10 kaputt).
  Es hilft nur, die Tests unabhängig vom echten Fensterfokus zu machen — zum Beispiel indem der
  Test die `focus_lost`-Verbindung des gerade geöffneten Feldes trennt
  (`bar._inline_input.focus_lost.disconnect()`), bevor er `_settle()` aufruft, oder indem er statt
  des Abbruchs über den Fokus direkt den zu prüfenden Zustand herstellt.
- Alternativ (und in der Anwendung sowieso das freundlichere Verhalten): ein `FocusOut` mit
  `Qt.FocusReason.ActiveWindowFocusReason` in `_FocusOutLineEdit.focusOutEvent` nicht als Abbruch
  werten. Dann verschwindet der halb getippte Profilname auch nicht mehr, wenn der Nutzer kurz in
  ein anderes Fenster wechselt. `_FocusOutLineEdit` ist vom Diff nicht angefasst, das wäre also
  eine bewusste zusätzliche Änderung.
- Solange die Datei so bleibt, ist jeder CI-Lauf ein Münzwurf.

### [MITTEL] `_scroll_to_active_tab()` verwirft die von Hand gewählte Scrollposition

- Datei: `anvil/widgets/profile_bar.py:826-831`, aufgerufen aus `:824` (`_cancel_inline_create`),
  `:904` (`_finish_inline_rename`) und `:923` (`_cancel_inline_rename`)
- Der Rücksprung ist unbedingt. Er läuft auch dann, wenn der Reveal die Ansicht gar nicht bewegt
  hat, weil der Nutzer vorher selbst dorthin gescrollt war.
- Gemessen, 30 Profile, 900 px, aktives Profil ist „Default“ ganz links, der Nutzer scrollt von
  Hand auf 1900 und arbeitet an Tab 25:

  | Ablauf | ALT Scroll / Tab 25 sichtbar | NEU Scroll / Tab 25 sichtbar |
  |---|---|---|
  | Ausgangslage | 1900 / 91 von 91 px | 1900 / 91 von 91 px |
  | umbenennen + Enter | 1900 / **117 von 117 px** | 0 / **0 von 117 px** |
  | umbenennen + Escape | 1900 / **91 von 91 px** | 0 / **0 von 91 px** |
  | von Hand auf 1200, „+“, Escape | 1200 (Position bleibt) | 0 |

- Sichtbare Folge: Der Nutzer benennt ein weit hinten liegendes Profil um, drückt Enter — und die
  Leiste springt ans andere Ende der Liste. Das Ergebnis der eigenen Aktion ist nicht mehr zu
  sehen, er muss von Hand zurückscrollen. In HEAD blieb die Ansicht stehen.
- Der Punkt aus Runde 2 war ein anderer: dort hatte **der Reveal** die Leiste verschoben und
  niemand hat sie zurückgeholt. Die jetzige Umsetzung überschießt und wirft auch die Positionen
  weg, die der Reveal nie angefasst hat.
- Vorschlag: in `_start_inline_create` / `_start_inline_rename` den Scrollwert vor dem Reveal
  merken (z. B. `self._scroll_before_reveal`) und beim Schließen genau diesen Wert wiederherstellen,
  statt zum aktiven Tab zu springen. Das schließt den Runde-2-Punkt und lässt die Handposition
  in Ruhe. Wenn es beim aktiven Tab bleiben soll: nur dann anfahren, wenn der Reveal den Wert
  tatsächlich verändert hat.
- Beim Anlegen mit Enter fällt es nicht auf, weil `set_profiles()` ohnehin neu zum neuen Profil
  scrollt (gemessen: Scroll 2285 ALT / 2286 NEU, neuer Tab in beiden Fällen 68 von 68 px sichtbar).

### [NIEDRIG] `_reveal_input` warnt, wenn das Feld keinen Platz mehr im Streifen hat

- Datei: `anvil/widgets/profile_bar.py:774` — `edit.mapTo(self._tabs_widget, QPoint(0, 0))`
- Erzwungen (Feld per `setParent(None)` aus dem Streifen genommen, Zeiger bleibt gesetzt):
  Qt schreibt `QWidget::mapTo(): parent must be in parent hierarchy` und `_reveal_input` rechnet
  mit x=0 weiter. Kein Absturz, keine Ausnahme.
- Über die normalen Wege ist das nicht erreichbar: `_finish_*` setzt vorher `_*_confirmed = True`,
  `_cancel_*` und der Aufräumblock in `set_profiles` setzen den Zeiger synchron auf `None`, und
  zwischen `setParent(None)` und der `None`-Zuweisung wird keine Ereignisschleife betreten.
  Nur der Vollständigkeit halber notiert; eine Prüfung auf `edit.parent() is self._tabs_widget`
  wäre der Einzeiler, falls das später einmal anders läuft.

## Ausdrücklich geprüft und unauffällig

### Signaländerung `profile_create_rejected`

Suche im gesamten Projekt (`*.py`, `*.md`, `*.sh`, `*.json`, `*.txt`, ohne `.venv/` und
`packaging/flatpak/repo/objects/`):

| Fundstelle | Zustand |
|---|---|
| `anvil/widgets/profile_bar.py:300` | Deklaration `Signal(str, str)` |
| `anvil/widgets/profile_bar.py:789` | `emit("toast.profile_invalid_name", name)` |
| `anvil/widgets/profile_bar.py:795` | `emit("toast.profile_exists", name)` |
| `anvil/mainwindow.py:260-261` | einzige Verbindung, auf `_on_profile_create_rejected` |
| `anvil/mainwindow.py:4343` | Handler, zweistellig |
| `tests/test_profile_create_feedback.py:86` | Lambda mit zwei Parametern |

Es gibt **keine** weitere Verbindung, keinen Slot mit alter einstelliger Signatur, keine
Unterklasse von `ProfileBar` (nur `mainwindow.py:236` erzeugt eine) und kein `_dev/`-Verzeichnis
im Projekt. End-to-End gemessen:

| Eingabe | Schlüssel | name | Text (de) |
|---|---|---|---|
| `Vanilla` (Duplikat) | `toast.profile_exists` | `'Vanilla'` | „Ein Profil namens 'Vanilla' gibt es bereits.“ |
| `a/b` | `toast.profile_invalid_name` | `'a/b'` | „Ungueltiger Profilname. …“ |
| `   ` (nur Leerzeichen) | `toast.profile_invalid_name` | `''` | „Ungueltiger Profilname. …“ |
| `Neu` | — | — | kein Abweisungssignal, Profil wird angelegt |

`toast.profile_invalid_name` hat gar keinen `{name}`-Platzhalter. Das ist unkritisch:
`Translator.t` ruft `value.format(**kwargs)`, und `str.format` ignoriert überzählige
Schlüsselwörter. Beide Schlüssel liegen in allen sieben Locale-Dateien
(de, en, es, fr, it, pt, ru) vor; `{name}` steht in allen sieben `profile_exists`-Werten.
Der Diff bringt keinen neuen sichtbaren Text.

### Keine Schleife zwischen `_scroll_to_active_tab` und `_update_container_width`

Strukturell ausgeschlossen und gemessen. `_scroll_to_active_tab` wird nur aufgerufen, **nachdem**
`_inline_input` und `_rename_input` auf `None` stehen; `_update_container_width` ruft
`_reveal_input` nur, **solange** eines von beiden gesetzt ist. Die beiden können sich also nie
gegenseitig auslösen. `_scroll_to_tab` steigt zusätzlich bei offenem Feld aus (`:705`), und
`valueChanged` landet ausschließlich in `_update_fade_visibility`.

Mit Tiefenzähler auf `_update_container_width`, `_reveal_input`, `_scroll_to_active_tab`,
`_scroll_to_tab`, `resizeEvent`, `_select_profile` und `set_profiles` gemessen (Abbruch wäre bei
Tiefe 50 erfolgt):

| Ablauf | max. Verschachtelung | Aufrufe |
|---|---|---|
| „+“ gedrückt | 1 | `_update_container_width` 1×, `_reveal_input` 1× |
| Anlegen + Enter | 2 | `set_profiles` 1×, `_update_container_width` 2×, `_select_profile` 1× |
| Anlegen + Escape | 2 | `_update_container_width` 2×, `_scroll_to_active_tab` 2× |
| Umbenennen geöffnet | 1 | `_update_container_width` 1×, `_reveal_input` 1× |
| Umbenennen + Enter | 2 | `_update_container_width` 1×, `_scroll_to_active_tab` 1× |
| Umbenennen + Escape | 2 | `_update_container_width` 2×, `_scroll_to_active_tab` 2× |
| 4× Fenstergröße geändert | 2 | `resizeEvent` 4×, `_reveal_input` 4× |
| Profil per Klick wechseln | 2 | `_select_profile` 1×, `_scroll_to_tab` 1× |
| Instanz wechseln | 2 | `set_profiles` 1×, `_update_container_width` 1× |
| `set_profiles` bei offenem Feld | 3 | `_update_container_width` 2×, `_scroll_to_tab` 2× |

### `resizeEvent` beim Programmstart

Mit einer Unterklasse gemessen, die jedes `resizeEvent` protokolliert: **während `__init__` kommt
kein einziges an**; das erste trifft erst nach dem expliziten `resize()` ein, und dort sind
`_inline_input` und `_fade_left` beide vorhanden. Der neue Zugriff ist auch theoretisch ungefährlich,
weil `self._inline_input` in Zeile 314 gesetzt wird, `self._fade_left` (das `resizeEvent` schon in
HEAD anfasst) dagegen erst in Zeile 385. Zusätzlich geprüft:

* Leiste konstruiert, ohne je `set_profiles` zu rufen, dann 900 → 400 → 1200 px: kein Fehler,
  in ALT wie in NEU.
* `set_profiles([])` (leere Profilliste), danach „+“ und `_scroll_to_active_tab()`: kein Fehler,
  Feld 200 von 200 px sichtbar (ALT: 54 px).

### Die geforderten Abläufe, jeweils vollständig gemessen

30 Profile bei 900 px sowie 4 Profile bei 900 px, nach jedem Schritt Kapselbreite gegen
`sizeHint`, aktiver Tab gegen seine eigene Breite, Scrollwert gegen `[minimum, maximum]`:

| Ablauf | ALT (30 Profile) | NEU (30 Profile) |
|---|---|---|
| Start | Kapsel ok, aktiv 80/80, Scroll 0/2217 | Kapsel ok, aktiv 80/80, Scroll 0/2217 |
| anlegen + Enter | Kapsel ok, aktiv 68/68, Scroll 2285/2286 | Kapsel ok, aktiv 68/68, Scroll 2285/2286 |
| anlegen + Escape | Kapsel ok, aktiv 68/68 | Kapsel ok, aktiv 68/68 |
| umbenennen + Enter | Kapsel **2920/2899 ABW** | Kapsel **2899/2899 ok** |
| umbenennen + Escape | Kapsel **2920/2899 ABW** | Kapsel **2899/2899 ok** |
| Profil per Klick wechseln | aktiv 68/68 | aktiv 68/68 |
| Instanz wechseln | Kapsel ok, aktiv 62/62, Scroll 0/0 | identisch |
| zurückgewechselt | Kapsel ok, aktiv 93/93, Scroll 2217/2217 | identisch |
| Profil gelöscht | Kapsel ok, aktiv 80/80, Scroll 0/2123 | identisch |
| Reihenfolge getauscht | Kapsel ok, aktiv 80/80 | identisch |
| Fenster 1500 px | Kapsel ok, aktiv 80/80, Scroll 0/1523 | identisch |
| Fenster 500 px | Kapsel ok, aktiv 80/80, Scroll 0/2523 | identisch |
| Fenster zurück auf 900 px | Kapsel ok, aktiv 80/80, Scroll 0/2123 | identisch |

Mit 4 Profilen dasselbe Bild: NEU in allen 12 Schritten „Kapsel = Inhalt“, ALT nach jedem
Umbenennen 390 statt 386. Der Scrollwert lag in **keinem** gemessenen Zustand außerhalb von
`[minimum, maximum]`.

### Drag & Drop

Mit echten `QMouseEvent`-Folgen durch den `eventFilter` gefahren (Press, 260 ms Drag-Timer, Move
um 120 px, Release):

| Ablauf | ALT | NEU |
|---|---|---|
| Tab „Alpha“ zwei Plätze nach rechts | Reihenfolge `Default, Beta, Gamma, Alpha, Delta`, Signal einmal, Kapsel 411/411, aktiv 80/80 | identisch |
| dasselbe bei offenem Anlege-Feld | kein Drag, kein Signal, Kapsel **411/555 ABW** | kein Drag, kein Signal, Kapsel **615/615 ok** |

Der `eventFilter` steigt bei offenem Feld weiterhin vor der Drag-Logik aus (`:982`).

### Weitere Randfälle

| Fall | ALT | NEU |
|---|---|---|
| `set_profiles` bei offenem Umbenennen-Feld | `RuntimeError` (`tab.show()` auf gelöschtem Tab), `_rename_input` bleibt als Karteileiche gesetzt | 30 Tabs, `inline`/`rename` beide `None`, 0 versteckte Tabs, aktiv 93/93, Kapsel ok |
| Profil löschen bei offenem Anlege-Feld | 29 Tabs, aktiv 93/93, Scroll 2120 | 29 Tabs, aktiv 93/93, Scroll 2042, Kapsel ok |
| zweimal „+“, dann Enter | 1 Feld im Streifen, 31 Tabs, aktiv „Doppelt“ | identisch |
| Leiste mit offenem Feld zerstört, 300 ms Schleife | kein `RuntimeError` | kein `RuntimeError` |

### Architektur

Die sieben Pflichtregeln aus `ARCHITEKTUR.md` (gelesen, Stand 2026-03-21) sind vom Diff nicht
berührt: es werden keine Mod-Dateien angefasst, `.mods/` bleibt unverändert, keine Frameworks,
keine `active_mods.json`, keine `modlist.txt`, keine Deploy- oder Purge-Logik. Der Diff bewegt
ausschließlich Qt-Widgets in der Profilleiste plus eine Toast-Meldung.

**Nicht möglich:** Der MO2-Referenzcode liegt laut Vorgabe unter
`/home/mob/Projekte/mo2-referenz/src/`. Dieses Verzeichnis existiert auf diesem Rechner nicht
(`ls /home/mob/Projekte/mo2-referenz/` → „Datei oder Verzeichnis nicht gefunden“, ebenso
`find /home/mob/Projekte -maxdepth 3 -iname profile.cpp` ohne Treffer). Ein Abgleich mit
`profile.cpp` konnte deshalb nicht stattfinden. Fachlich fällt das hier nicht ins Gewicht: die
Änderung betrifft nur das Scroll- und Fokusverhalten einer Qt-Leiste, keine Profil- oder
Mod-Verwaltung.

## Nicht geprüft

`./restart.sh` wurde auftragsgemäß nicht ausgeführt. Alle Messungen liefen offscreen gegen frisch
erzeugte `ProfileBar`-Objekte; es wurden keine Produktionsdaten gelesen oder verändert.

## Ergebnis

**NEEDS FIXES**

1. **[HOCH]** `tests/test_profile_bar_inline_input.py` macht `pytest tests/` in rund einem Drittel
   der Läufe rot. Ursache ist der Fensterfokus, nicht die Produktivlogik — die Tests müssen aber
   deterministisch werden, bevor das eingecheckt wird.
2. **[MITTEL]** `_scroll_to_active_tab()` wirft die von Hand gewählte Scrollposition weg. Nach dem
   Umbenennen eines weit hinten liegenden Profils springt die Leiste ans andere Ende; in HEAD blieb
   sie stehen.

Die MITTEL-Regression aus Runde 2 und zwei der vier NIEDRIG-Punkte sind sauber geschlossen. Die
beiden verbliebenen NIEDRIG-Punkte (Reentranz im Aufräumblock, 100-ms-Timer ohne Kontextobjekt)
sind unverändert Bestand aus HEAD und keine Commit-Blocker.
