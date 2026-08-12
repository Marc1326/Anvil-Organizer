# Review Issue #103 — Runde 3

Datum: 2026-08-08
Branch: `fix/issue-103`, Spitze weiterhin `08d8588`
Arbeitsverzeichnis: **unversionierte** Aenderungen an `anvil/mainwindow.py`,
`anvil/widgets/profile_bar.py`, `tests/test_profile_create_feedback.py` sowie die
**unversionierten** Dateien `tests/conftest.py` und `tests/test_profile_bar_inline_input.py`
Vorgaenger: `docs/review-103-issuestand.md`, `docs/review-103-issuestand-runde2.md`

Messaufbau wie in Runde 2: echte `QApplication`, echt geladenes Theme
(`load_theme("Anvil Dunkel")` bzw. `"Paper Dark"`), echte Ereignisse ueber
`QTest.mouseClick` / `mouseDClick` / `keyClicks` / `keyClick` und
`QApplication.sendEvent(QWheelEvent|QKeyEvent)`, nach jedem Schritt eine echte
Ereignisschleife (`QEventLoop` + `QTimer.singleShot(300–500 ms)`).
`QT_QPA_PLATFORM=offscreen`. 30 Profile (`Default` + `Profil 01..29`), Fenster 1000 px,
sofern nicht anders angegeben. Alle Zahlen sind gemessen, nicht geschaetzt.

Der Arbeitsstand wurde nicht veraendert: nichts committet, nichts gestasht, beide
Wegwerf-Arbeitsverzeichnisse wieder entfernt. `git status` zeigt am Ende exakt dieselben
fuenf Eintraege wie am Anfang.

---

## Kurzfassung

| Punkt | Runde 1 | Runde 2 | Runde 3 |
|---|---|---|---|
| 1 — Deploy / plugins.txt | NICHT GELOEST | NICHT GELOEST | unveraendert **NICHT GELOEST** (bewusst) |
| 2 — Profil anlegen | GELOEST | funktional geloest, **nicht committet** | funktional geloest, **weiterhin nicht committet** |
| 3 — Profilleiste scrollen | GELOEST | GELOEST | **GELOEST** |

**Ein Schliessen von #103 auf Basis dieses Branches waere weiterhin nicht gerechtfertigt.**
Begruendung am Ende.

Gute Nachricht zuerst: die drei seit Runde 2 gemeldeten Korrekturen halten alle einer
Messung stand. Der `{name}`-Fehler ist wirklich weg, die Pillen-Gruppe schrumpft wieder,
`resizeEvent` holt das Feld zurueck, und das aktive Profil kommt nach dem Schliessen
wieder ins Bild. Das ist echter Fortschritt.

Schlechte Nachricht: der **Commit-Zustand des Branches ist gegenueber Runde 2 unveraendert**.
Die Spitze ist immer noch `08d8588`. Der gesamte Nutzen fuer Punkt 2 — inklusive der neuen
`{name}`-Korrektur, die jetzt auch `anvil/mainwindow.py` betrifft — liegt weiterhin
ausschliesslich im Arbeitsverzeichnis.

---

## Punkt 3 — Scrollen. Ergebnis: GELOEST

Modernes Theme („Anvil Dunkel"), `is_modern_theme_active()` = True, `_plus_inline` = True:

```
viewport=441  strip=2640  max=2199  wert=0
Rad ueber Viewport: 0   -> 120
Rad ueber Tab:      120 -> 240
Rad ueber '+':      240 -> 360
nach 60 Radschritten: 2199 (= maximum)
Pos1: 0        Ende: 2199
Fremdes Widget (Rad + Ende): 0   -> keine Wirkung, korrekt
```

Klassisches Theme („Paper Dark", echt geladen), `is_modern_theme_active()` = False,
`_plus_inline` = False:

```
viewport=669  strip=2606  max=1937
Rad ueber Viewport: 0   -> 120
Rad ueber Tab:      120 -> 240
Rad ueber '+':      240 -> 360
nach 60 Radschritten: 1937 (= maximum)
Pos1: 0        Ende: 1937
Fremdes Widget (Rad + Ende): 0
```

Der Ereignisfilter haengt an der `QApplication` (Zeile 518), greift aber nur bei
Widgets aus `_is_own_scroll_target` — das habe ich mit einem fremden `QPushButton`
gegengeprueft: Rad und Ende-Taste bleiben dort wirkungslos.

Drag & Drop laeuft weiter: `profiles_reordered` feuerte einmal, Reihenfolge
`['Default','A','B','C']` -> `['Default','B','C','A']`.

Pos1/Ende **waehrend** ein Eingabefeld offen ist: der Bildlauf bleibt stehen (2369 -> 2369),
der Text im Feld wird bearbeitet (`'abc'` + Pos1 + `'X'` -> `'Xabc'`). Der Guard in
`_handle_scroll_key` funktioniert.

---

## Punkt 2 — Profil anlegen

### Der entscheidende Messwert (unveraendert seit Runde 2)

An der **Branch-Spitze `08d8588`** — also dem, was ein `git merge fix/issue-103` heute
mitbringt, gemessen in einem eigenen `git worktree`:

```
Modul: .../wt-tip/anvil/widgets/profile_bar.py
'+'-Klick: Feld=True  breite=140  sichtbar=0 px  visible=True  scroll=0/2343
Signal-Arity profile_create_rejected: profile_create_rejected(QString)
```

Null Pixel sichtbar. Genau der Zustand, den der Melder beschreibt. Und die Signatur mit
einem Argument zeigt, dass auch der `{name}`-Fehler an der Spitze noch vollstaendig drin ist.

Im **Arbeitsverzeichnis** (mit den unversionierten Aenderungen):

```
'+'-Klick: sichtbar=200/200  fokus=True  visible=True  scroll=2369/2403  viewport=441
"Mein Profil" + Enter -> confirmed=['Mein Profil']  tabs=31  neuer Tab vorhanden=True
danach: scroll=2298/2303  '+' sichtbar=25 px  neuer Tab sichtbar=103/103
```

### Randfaelle aus Runde 2, alle wiederholt

| Fall | Messung | Runde 2 | Runde 3 |
|---|---|---|---|
| Letztes Profil umbenennen (Doppelklick Tab 29) | Feld 200/200 sichtbar, Fokus, Text `'Profil 29'`, Enter -> `renamed=[('Profil 29','XX')]` | OK | **OK** |
| Anlegen direkt nach Profilwechsel (Klick Tab 20, dann „+") | aktiv=`'Profil 20'`, Feld 200/200 sichtbar, scroll=2368/2402 | OK | **OK** |
| Zwei Anlegeversuche hintereinander | 1.: `ok=['Neu A']`, tabs=31 — 2.: Feld 200/200, `ok=['Neu A','Neu B']`, tabs=32 | OK | **OK** |
| Nur 3 Profile | viewport=411, max=0, Feld 200/200, „+" 30/30 sichtbar | OK | **OK** |
| Schmales Fenster | ab ~500 px beschnitten, siehe unten | Randbefund | **unveraendert** |
| Fenster verkleinern waehrend das Feld offen ist | 420 px -> 151/200 statt vorher 0/200 | FEHLER | **BEHOBEN** |
| Abbruch per Escape | Feld bleibt offen, behaelt Fokus | FEHLER | **unveraendert** (Altbestand, siehe Befund 2) |

### Schmales Fenster — Zahlen wie in Runde 2

```
Fenster  viewport  Feld  sichtbar  scroll
1000px      441     200    200     2369/2403
 700px      291     200    200     2519/2553
 500px      191     200    191     2610/2653
 420px      151     200    151     2610/2693
 360px      121     200    121     2610/2723
 300px       91     200     91     2610/2753
 240px       66     200     66     2610/2778
```

Ab ~500 px Fensterbreite passt das 200-px-Feld nicht mehr ins Sichtfenster.
`_reveal_input` bevorzugt dann die linke Kante, der Textanfang bleibt sichtbar und die
Eingabe funktioniert. Bei 240 px sind es nur noch 66 px. Kein Blocker, der Grenzfall
bleibt eng.

### Was seit Runde 2 nachweislich besser geworden ist

**Fenstergroesse waehrend das Feld offen ist** (Runde-2-Befund 4 — behoben):

```
vorher:            sichtbar=200/200  viewport=441
nach resize  420:  sichtbar=151/200  viewport=151  scroll=2610/2693
nach resize  300:  sichtbar= 91/200  viewport= 91  scroll=2610/2753
nach resize 1400:  sichtbar=200/200  viewport=641  scroll=2203/2203
```

Runde 2 mass hier `0/200`. Jetzt ist das Feld nur noch durch die Sichtfensterbreite
begrenzt, nicht mehr weggeschoben. `resizeEvent` ruft neu `_reveal_input` auf
(`profile_bar.py:521-527`).

**Pillen-Gruppe nach dem Umbenennen** (Runde-2-Befund 6 — behoben),
2 Profile, Fenster 1600 px, langes Profil auf „A" umbenannt:

```
vorher:  container=359  max=359  hint=351
nachher: container=168  max=168  hint=160
```

Runde 2 mass `nachher: container=349 max=349 hint=160` — 183 px Leerraum. Der ist weg.
Gegenprobe mit abgebrochenem Umbenennen (Fokusverlust): Breite bleibt korrekt bei 359,
Tab wieder sichtbar, `_rename_input=None`.

**Aktives Profil nach dem Schliessen** (neu):

```
aktiv='Default':   scroll offen=2369 -> zu=0     aktiver Tab sichtbar=80/80
aktiv='Profil 15': scroll offen=2368 -> zu=1251  aktiver Tab sichtbar=85/85
aktiv='Profil 29': scroll offen=2368 -> zu=2198  aktiver Tab sichtbar=85/85
```

Funktioniert in allen drei Lagen.

---

## Der `{name}`-Fehler — wirklich weg

Gemessen mit echtem Signal und dem **echten** Slot aus `anvil/mainwindow.py`
(`MainWindow._on_profile_create_rejected`, an ein `QWidget` gebunden; nur `Toast` wurde im
Testprozess durch einen Mitschnitt ersetzt). Ausgeloest ueber echte Ereignisse:
`QTest.mouseClick` auf „+", `QTest.keyClicks("Vanilla")`, `QTest.keyClick(Return)`.

Doppelter Name, alle sieben Sprachen — was der Nutzer wirklich liest:

```
de | "Ein Profil namens 'Vanilla' gibt es bereits."
en | "A profile named 'Vanilla' already exists."
es | "Ya existe un perfil llamado 'Vanilla'."
fr | "Un profil nomme 'Vanilla' existe deja."
it | "Esiste gia un profilo chiamato 'Vanilla'."
pt | "Ja existe um perfil chamado 'Vanilla'."
ru | "Профиль с именем 'Vanilla' уже существует."
```

Kein `{` mehr in irgendeiner Sprache. In jedem Durchlauf zusaetzlich geprueft:
Feld weg (`_inline_input=None`), Tab-Zahl unveraendert bei 3 — es wird also kein
Geister-Tab angelegt.

Ungueltiger Name (`a/b`), alle sieben Sprachen: die Meldung enthaelt keinen Platzhalter,
obwohl der Name jetzt mitgeliefert wird — `str.format()` ignoriert ueberzaehlige
Argumente, und `Translator.t` faengt `KeyError`/`ValueError` ohnehin ab.

```
de | 'Ungueltiger Profilname. Keine / oder \\ und keine Leerzeichen am Anfang oder Ende.'
en | 'Invalid profile name. No / or \\ and no leading or trailing spaces.'
... (es, fr, it, pt, ru ebenso ohne Platzhalter)
```

Leere Eingabe + Enter -> dieselbe „ungueltiger Name"-Meldung. Korrekt.

Zum Vergleich derselbe Test an der **Branch-Spitze `08d8588`** im eigenen Worktree —
dort ist der Fehler vollstaendig vorhanden:

```
de | "Ein Profil namens '{name}' gibt es bereits."   <-- PLATZHALTER
en | "A profile named '{name}' already exists."      <-- PLATZHALTER
... (alle sieben Sprachen)
```

Ein Kuriosum ohne praktische Bedeutung: gibt der Nutzer woertlich `{name}` als Profilname
ein und existiert bereits ein Profil `{name}`, liest der Toast
`"Ein Profil namens '{name}' gibt es bereits."` — was dann sachlich richtig ist.
Kein Fehler, nur erwaehnt, damit es niemanden verwirrt.

`tests/test_profile_create_feedback.py` ist nachgezogen: die Zusicherungen in Zeile 38
(`"{name}" in toast["profile_exists"]`) und Zeile 49 (`.format(name="Test")`) sind jetzt
konsistent mit dem Produktivcode, weil der Platzhalter dort wirklich gefuellt wird. Der
neue Test `test_the_rejection_carries_the_name_the_message_needs` prueft genau das
(`"{" not in message`). Runde-2-Befund 2 ist damit erledigt.

---

## Befunde

### 1. [HIGH — blockiert den Merge] Der Fix ist immer noch nicht committet

```
$ git branch --show-current
fix/issue-103
$ git log --oneline -1
08d8588 fix profile bar not scrollable with many profiles
$ git status --short anvil/ tests/
 M anvil/mainwindow.py
 M anvil/widgets/profile_bar.py
 M tests/test_profile_create_feedback.py
?? tests/conftest.py
?? tests/test_profile_bar_inline_input.py
```

Die Branch-Spitze ist seit Runde 2 unveraendert. Der Umfang der unversionierten Arbeit ist
sogar **gewachsen** — jetzt haengt auch `anvil/mainwindow.py` mit drin, also der Slot, ohne
den die Signal-Signatur `Signal(str, str)` gar keinen Sinn ergibt.

Gemessene Folge fuer den, der heute mergt: „+"-Klick -> Feld da, **0 px sichtbar**;
Toast zeigt in allen sieben Sprachen `{name}`. Beides oben belegt.

Das ist derselbe Befund wie in Runde 2, unveraendert. Er ist der einzige echte Blocker,
der in der Hand dieses Branches liegt.

*Fix:* die drei geaenderten Dateien und die beiden neuen Testdateien committen.

### 2. [MEDIUM — Altbestand, kein Blocker] Escape bricht die Eingabe nicht ab

Auftragsgemaess geprueft, woher das kommt:

```
main         -> Key_Escape: 0
origin/main  -> Key_Escape: 0
HEAD         -> Key_Escape: 0
7a2c6f6      -> Key_Escape: 0   (merge-base)
ac740d6      -> Key_Escape: 0
08d8588      -> Key_Escape: 0
v1.6.1       -> Key_Escape: 0
Arbeitsverzeichnis -> 0
```

`git log -S"Handle Escape or focus loss" -- anvil/widgets/profile_bar.py` zeigt genau einen
Commit: `0f2a82f Profile: Segmented Tabs mit Persistenz und Kontextmenue`. Der Docstring
verspricht seit der Einfuehrung der Funktion etwas, das nie verdrahtet war.

**Klares Ergebnis: Altbestand.** Auch in `main`, auch im veroeffentlichten `v1.6.1`. Keine
Regression dieses Branches. Damit **kein Blocker**, wie beauftragt nur berichtet.

Gemessenes Verhalten im Arbeitsstand:
```
Anlegen    -> nach Escape: inline_input gesetzt=True  selbes Objekt=True  fokus=True  sichtbar=True
Umbenennen -> nach Escape: rename_input gesetzt=True  Tab wieder sichtbar=False
```

`_FocusOutLineEdit` (Zeile 264-270) hat nur `focusOutEvent`, kein `keyPressEvent`.
Verbunden ist ausschliesslich `focus_lost`.

Sackgasse ist es nicht — geprueft:
```
Escape beim Umbenennen, danach woanders hinklicken
  nach Escape:          rename offen=True   Tab sichtbar=False
  nach Klick woanders:  rename offen=False  Tab sichtbar=True
Umbenennen offen, dann '+' klicken
  nach '+': rename_input=None  inline_input=True  Tab wieder sichtbar=True
```

Der Nutzer kommt also immer heraus. Escape tut nur nichts.

*Empfehlung (kein Blocker):* eigener kleiner Issue, `keyPressEvent` in
`_FocusOutLineEdit` oder Escape im Ereignisfilter.

### 3. [LOW — Testqualitaet, unveraendert seit Runde 2] Der „moderne" Testaufbau existiert so nicht

`tests/test_profile_bar_inline_input.py:24-32` setzt `bar._plus_inline` **nach** dem
Konstruktor:

```python
def _bar(profiles, modern=True, width=900):
    bar = ProfileBar()
    bar._plus_inline = modern  # only the modern theme limits the container
```

`_plus_inline` steuert aber bereits den Aufbau (Zeilen 339, 345, 390, 399, 421, 491, 507).
Im Testprozess wird kein Theme geladen, `is_modern_theme_active()` liefert False, die
Leiste wird immer klassisch gebaut. `modern=True` erzeugt eine Mischform, die es in keiner
echten Konfiguration gibt.

Unveraendert gegenueber Runde 2. Ich habe alle Kernmessungen deshalb erneut mit echt
geladenem Theme gemacht — das Verhalten haelt in **beiden** echten Themes. Der Fix ist in
Ordnung, das Testbett misst nur nicht, was seine Namen behaupten.

*Fix:* `load_theme("Anvil Dunkel")` bzw. `"Paper Dark"` im Test setzen, `_plus_inline`
nicht von aussen ueberschreiben.

### 4. [LOW — Altbestand] Das „+" bleibt schwer auffindbar

Unveraendert gegenueber Runde 2: `layout.addStretch(1)` neben
`layout.addWidget(self._tab_container, 1)` (Zeilen 389-392) gibt der Pillengruppe nur die
Haelfte der Fensterbreite, waehrend sich 30 Profile draengen; beide Bildlaufleisten stehen
auf `ScrollBarAlwaysOff`. Ohne Scrollen ist das „+" bei 30 Profilen 0 von 30 px sichtbar.

Altbestand, keine Regression. Es ist aber genau die Lage, aus der die Meldung
„I can't seem to create a new profile" entstanden ist.

### 5. [LOW — Umgebung, nicht dieser Branch] Der nackte `pytest`-Aufruf bricht ab

```
$ pytest -q
ERROR _dev/tests/test_instance.py - AssertionError: modlist.txt missing
Interrupted: 1 error during collection
```

`_dev/` ist nicht versioniert (`git ls-files _dev/` ist leer) und in `pyproject.toml` gibt
es kein `testpaths`. Wer ohne Pfad testet, bekommt einen Fehlalarm.
Mit `pytest tests/` laeuft alles.

*Fix (optional):* `testpaths = ["tests"]` in `pyproject.toml`.

### 6. [INFO] Der Absturz aus Runde-2-Befund 9 ist nicht wieder aufgetreten

Sechs aufeinanderfolgende Laeufe im Arbeitsverzeichnis:

```
Lauf 1..6: 242 passed, 1 skipped  (6,5 s je Lauf)
```

Kein Core-Dump, kein `Fatal`, kein `Aborted`. Ich kann den Einzelfall aus Runde 2 weder
zuordnen noch endgueltig ausschliessen, aber er hat sich nicht reproduzieren lassen.

### 7. [INFO] Regressionsproben zu den neuen Aenderungen — alle sauber

`set_profiles` raeumt jetzt offene Eingabefelder ab (`setParent(None)` + `deleteLater()`).
Das ist der riskanteste Teil der neuen Arbeit, deshalb gezielt geprueft:

```
set_profiles waehrend das Anlege-Feld offen ist (mit halb getipptem Text)
  -> kein Absturz, inline_input=None, tabs=31, danach weiter benutzbar
set_profiles waehrend das Umbenenn-Feld offen ist
  -> kein Absturz, rename_input=None, alle Tabs sichtbar=True
```

Kein `RuntimeError` durch ein geloeschtes C++-Objekt, kein haengender versteckter Tab.
Halb getippter Text geht dabei verloren — akzeptabel, weil alle sechs Aufrufer von
`set_profiles` in `anvil/mainwindow.py` (Zeilen 1902, 4358, 4454, 4675, 4686, 7077)
nutzerausgeloest sind. Es gibt keinen Zeitgeber, der die Leiste im Hintergrund neu baut.

`python -m py_compile` auf allen fuenf betroffenen Dateien: fehlerfrei.
Ein Linter ist im Projekt nicht eingerichtet (kein `ruff`/`flake8`/`mypy` in
`pyproject.toml`, `ruff` ist im Venv nicht installiert).

Keine neuen sichtbaren Zeichenketten in der Aenderung — die Locale-Schluessel
`toast.profile_exists` und `toast.profile_invalid_name` liegen bereits in allen sieben
Sprachdateien vor (Zeilen 555/556 in de, en, es, fr, it, pt, ru).

---

## Punkt 1 — unveraendert, im gemergten Stand nachgeprueft

An diesem Branch wurde dazu bewusst nicht gearbeitet. Ich habe die vier Ursachen aus
`docs/review-103-issuestand.md` trotzdem im **gemergten** Stand (`main` + Branch)
nachgeschlagen, damit klar ist, dass auch die 20 Commits aus `main` nichts davon geloest
haben:

1. **Ein fehlgeschlagener `plugins.txt`-Schreibvorgang kippt das ganze Deploy.**
   `game_panel.py:1148-1163` — `_record_plugin_write_failure` setzt hart
   `setattr(result, "success", False)`. `mainwindow.py:2647` bricht daraufhin
   `_predeploy_for_launch` mit `return False` ab, der Spielstart wird verweigert.
   Genau die Kette, die der Melder erlebt.

2. **Die verstaendlichere Meldung erreicht den Startdialog nicht.**
   `8c8036b` hat `localized_write_error()` gebaut (`game_panel.py:234-247`), inklusive
   „Spiel einmal starten"-Hinweis bei fehlendem Prefix. Der Text landet in
   `result.errors` — und `mainwindow.py:2661` zeigt dann
   `tr("error.deploy_failed_message", details="")`. Der Hinweis wird verworfen.
   Beim Aufraeumpfad (`mainwindow.py:2354`) wird `details` dagegen korrekt gefuellt;
   ausgerechnet der Spielstart nicht.

3. **Flatpak: Flatpak-Steam bleibt ausgeblendet.**
   Gebaut wird `packaging/flatpak/com.github.Marc1326.AnvilOrganizer.yml`
   (`build-flatpak.sh:35`, `.github/workflows/flatpak.yml:23`). Dort steht
   `--filesystem=home`, `/media`, `/mnt`, `/run/media`. Nirgends
   `~/.var/app/com.valvesoftware.Steam`. Der Melder nutzt Bazzite und Flatpak.
   Das zweite Manifest `net.anvil_organizer.AnvilOrganizer.yml` ist sogar noch enger
   (kein `home`, `/mnt` nur lesend) — welches davon perspektivisch gelten soll, ist offen.

4. **Heroic/GOG/Epic bekommen grundsaetzlich keinen Prefix.**
   `anvil/plugins/base_game.py:354-357`:
   ```python
   def protonPrefix(self) -> Path | None:
       if self._detected_store != "steam":
           return None
   ```
   Der Melder schreibt „tried steam and heroic". Fuer Heroic ist der Prefix per Bauart
   `None` -> `plugins.txt path is unavailable` -> Deploy `success=False` -> kein Start.
   Ein Feld zum manuellen Eintragen gibt es nicht.

Ergaenzend, als **Hypothese** und nicht als Messung: der Melder schreibt, seine Spiele
laegen auf einem Laufwerk, das unterhalb seines Home-Verzeichnisses eingehaengt ist.
Ob `--filesystem=home` einen solchen Untereinhaengepunkt zuverlaessig mit in die Sandbox
nimmt, haengt vom Einhaengezeitpunkt ab. Das habe ich nicht nachgestellt und behaupte es
nicht — es waere aber der naechste Punkt, den ich beim Melder abfragen wuerde.

---

## Mergefaehigkeit

```
merge-base:            7a2c6f6  (30.07.)
main...fix/issue-103:  20 hinter / 3 voraus
origin/main...main:    main ist 3 Commits VOR origin/main (unveroeffentlicht)
```

Ueberschneidende Dateien seit der Merge-Base: `anvil/locales/{de,en,es,fr,it,pt,ru}.json`,
`anvil/mainwindow.py`, `anvil/widgets/game_panel.py`.

Probemerge in einem Wegwerf-Arbeitsverzeichnis:

```
$ git merge --no-commit --no-ff main
automatischer Merge von anvil/locales/... (alle sieben)
automatischer Merge von anvil/mainwindow.py
automatischer Merge von anvil/widgets/game_panel.py
Automatischer Merge abgeschlossen; haelt vor dem Commit an
```

**Keine Konflikte.** Auch die unversionierte Aenderung liess sich sauber darauflegen:

```
$ git apply -3 worktree.patch
Patch auf 'anvil/mainwindow.py' sauber angewendet.
Patch auf 'anvil/widgets/profile_bar.py' sauber angewendet.
Patch auf 'tests/test_profile_create_feedback.py' sauber angewendet.
```

| Stand | Tests | Punkt-2-Messung |
|---|---|---|
| Arbeitsverzeichnis (Branch + unversioniert) | `242 passed, 1 skipped` (6 Laeufe) | Feld 200/200 sichtbar |
| Merge `main` -> Branch, **nur Commits** | `333 passed, 1 skipped` | Feld **0 px** sichtbar, Signal `(QString)`, `{name}` in allen 7 Sprachen |
| Merge `main` -> Branch **plus** unversionierte Arbeit | `357 passed, 1 skipped` | Feld 200/200 sichtbar, Signal `(QString,QString)`, Toast sauber |

Beide Wegwerf-Arbeitsverzeichnisse wurden per `git worktree remove --force` entfernt;
der Merge wurde abgebrochen, nichts committet, nichts gestasht.

**Technisch mergefaehig: ja. Inhaltlich fehlt weiterhin der Commit.**

---

## Gesamturteil

**Nein — ein Schliessen von #103 auf Basis dieses Branches waere jetzt nicht gerechtfertigt.**

Zwei Gruende, in dieser Reihenfolge:

1. **Punkt 1 ist der Titel des Issues und unangetastet.** Der Melder schreibt
   „Can't launch anything… plugins.txt path not available". Punkt 2 und 3 hat er selbst
   als Nachtrag ergaenzt, um ueberhaupt Fehler suchen zu koennen. Solange das Kernproblem
   offen ist, ist der Issue offen.
2. **Punkt 2 ist im committeten Stand nicht behoben.** Gemessen an der Branch-Spitze:
   „+"-Klick, Feld da, **0 px sichtbar**, Toast mit `{name}` in allen sieben Sprachen.
   Die gesamte Korrektur liegt im Arbeitsverzeichnis.

Der neue Fehler aus Runde 2 (`{name}`) ist dagegen **erledigt** — sauber geloest ueber
`Signal(str, str)` und `tr(key, name=name)`, in allen sieben Sprachen mit echtem Signal
und echtem Slot nachgemessen. Auch die beiden Randbefunde 4 und 6 aus Runde 2 sind weg.
Das ist gute Arbeit; sie muss nur in den Branch.

### Was fuer ein Schliessen fehlt

- [ ] **Committen:** `anvil/mainwindow.py`, `anvil/widgets/profile_bar.py`,
      `tests/test_profile_create_feedback.py`, `tests/conftest.py`,
      `tests/test_profile_bar_inline_input.py` (Befund 1) — der einzige harte Blocker
      dieses Branches
- [ ] **Punkt 1 entscheiden.** Entweder beheben, oder als eigenen Issue abspalten und
      #103 auf die Profilleiste eindampfen — dann aber im Issue sichtbar dokumentieren
      und dem Melder sagen, wo sein Startproblem weiterverfolgt wird

### Fuer Punkt 1 konkret noetig (vier Schritte, unveraendert)

1. `plugins.txt`-Fehler duerfen den Spielstart nicht mehr blockieren — Warnung statt
   `success = False` (`game_panel.py:1148-1163`)
2. `mainwindow.py:2661`: `details=""` durch die echten `result.errors` ersetzen, damit
   die lokalisierte Meldung aus `8c8036b` beim Nutzer ankommt
3. Flatpak-Manifest um `~/.var/app/com.valvesoftware.Steam` erweitern und klaeren,
   welches der beiden Manifeste kuenftig gilt
4. Prefix-Ermittlung fuer Heroic/GOG/Epic — entweder Erkennung in
   `base_game.protonPrefix()` oder ein Feld zum manuellen Eintragen in den Einstellungen

### Nicht blockierend, aber offen

- Escape bricht die Eingabe nicht ab (Befund 2) — **Altbestand**, auch in `main` und
  `v1.6.1`; eigener Issue waere ehrlicher
- Testaufbau in `tests/test_profile_bar_inline_input.py` misst eine Konfiguration, die es
  nicht gibt (Befund 3)
- Das „+" bleibt bei vielen Profilen schwer auffindbar (Befund 4) — Altbestand, aber genau
  die Situation, aus der die Meldung entstand
- `pytest` ohne Pfadangabe bricht an `_dev/tests` ab (Befund 5)

Punkt 3 (Scrollen) ist aus meiner Sicht fertig und braucht nichts weiter.
