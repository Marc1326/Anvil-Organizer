# Review Issue #103 — Runde 2

Datum: 2026-08-08
Branch: `fix/issue-103`, Spitze `08d8588` + **unversionierte** Aenderung an `anvil/widgets/profile_bar.py`
+ **unversionierte** Dateien `tests/conftest.py`, `tests/test_profile_bar_inline_input.py`
Vorgaenger-Bericht: `docs/review-103-issuestand.md`

Alle Zahlen in diesem Bericht sind gemessen, nicht geschaetzt. Messaufbau: echte
`QApplication`, echtes Theme geladen (`load_theme("Anvil Dunkel")` bzw. `"Paper Dark"`),
echte Ereignisse ueber `QTest.mouseClick` / `QTest.mouseDClick` / `QTest.keyClicks` /
`QApplication.sendEvent(QWheelEvent|QKeyEvent)`, und nach jedem Schritt eine echte
Ereignisschleife (`QEventLoop` + `QTimer.singleShot(300–400 ms)`), damit die 100 ms in
`set_profiles`, der 200-ms-Klick-Timer und der `singleShot(0)`-Reveal wirklich feuern.
`QT_QPA_PLATFORM=offscreen`. 30 Profile (`Default` + `Profil 01..29`).

---

## Kurzfassung

| Punkt | Runde 1 | Runde 2 |
|---|---|---|
| 1 — Deploy / plugins.txt | NICHT GELOEST | unveraendert **NICHT GELOEST** (bewusst, keine Arbeit daran) |
| 2 — Profil anlegen | GELOEST | **funktional geloest — aber der Fix ist nicht committet** |
| 3 — Profilleiste scrollen | GELOEST | **GELOEST**, mit echten Rad-/Tastenereignissen bestaetigt |

**Ein Schliessen von #103 auf Basis dieses Branches ist nicht gerechtfertigt.** Begruendung
am Ende.

---

## Punkt 3 — Scrollen. Ergebnis: GELOEST

Modernes Theme („Anvil Dunkel"), Fenster 1000 px, 30 Profile:

```
plus_inline=True  viewport=441  strip=2640  scrollbar 0..2199  wert=0
Rad ueber Viewport: 0   -> 120
Rad ueber Tab:      120 -> 240
Rad ueber '+':      240 -> 360
nach 60 Radschritten: 2199 (= maximum)
Pos1-Taste: 0        Ende-Taste: 2199
Fremdes Widget (Rad + Ende): 0   -> keine Wirkung, korrekt
```

Klassisches Theme — diesmal **echt** geladen (`Paper Dark`, `is_modern_theme_active()` = False,
`_plus_inline=False`, „+" ausserhalb des Streifens):

```
viewport=669  strip=2606  max=1937
Rad ueber Viewport: 0   -> 120
Rad ueber Tab:      120 -> 240
Ende-Taste: 1937 (= maximum)
```

Zum Vergleich an der Branch-Spitze ohne die unversionierte Aenderung: Rad funktioniert
(kommt aus `08d8588`), **Pos1/Ende nicht** — `Ende-Taste -> 0 (max 2199)`. Pos1/Ende sind also
ein Zusatz der unversionierten Arbeit.

Drag & Drop der Tabs laeuft weiter (`profiles_reordered` feuerte einmal, Reihenfolge
geaendert) — der erweiterte Ereignisfilter bricht es nicht.

---

## Punkt 2 — Profil anlegen. Ergebnis: funktional geloest, aber nicht committet

### Der entscheidende Messwert

An der **Branch-Spitze `08d8588`** (also dem, was ein `git merge fix/issue-103` mitbringt):

```
'+'-Klick: Feld=True  breite=140  sichtbar=0 px  visible=True  scroll=0
```

Das Eingabefeld entsteht — und ist **null Pixel breit sichtbar**. Genau der Zustand, den der
Melder beschreibt. Punkt 2 ist an der Branch-Spitze **nicht** behoben.

Mit der **unversionierten** Aenderung im Arbeitsverzeichnis:

```
'+'-Klick: Feld sichtbar 200/200 px, Fokus=True, scroll=2369/2403
"Mein Profil" + Enter -> profile_create_confirmed=['Mein Profil'], tabs=31, neuer Tab vorhanden
```

Der gesamte Nutzen fuer Punkt 2 steckt also in nicht eingecheckter Arbeit.

### Randfaelle (alle mit echten Ereignissen)

| Fall | Messung | Bewertung |
|---|---|---|
| Letztes Profil umbenennen (Doppelklick auf Tab 29) | Feld 200/200 px sichtbar, Fokus, Text `'Profil 29'`, Enter -> `profile_renamed=('Profil 29','XX')` | OK |
| Anlegen direkt nach Profilwechsel (Klick Tab 20, dann sofort „+") | aktiv=`'Profil 20'`, Feld 200/200 sichtbar, scroll=2369 | OK. `_on_profile_changed` in `mainwindow.py:4483` ruft `set_profiles` **nicht** auf, der Fall ist auch in der echten App unkritisch |
| Zwei Anlegeversuche hintereinander | 1.: `ok=['Neu A']`, tabs=31 — 2.: Feld 200/200, `ok=['Neu A','Neu B']`, tabs=32 | OK |
| Nach dem Anlegen | scroll=2252/2253, „+" 29/30 px sichtbar, neuer Tab 53/53 sichtbar | OK |
| Nur 3 Profile | viewport=254, max=0, „+" 30/30 sichtbar, Feld 200/200 | OK |
| Abbruch per **Escape** | Feld bleibt offen, behaelt Fokus | **FEHLER**, siehe Befund 3 |
| Schmales Fenster | ab ~500 px Fensterbreite wird das Feld beschnitten | siehe Befund 5 |
| Fenster verkleinern **waehrend** das Feld offen ist | Feld 0/200 px sichtbar | **FEHLER**, siehe Befund 4 |

---

## Befunde

### 1. [HIGH — blockiert den Merge] Der Fix fuer Punkt 2 ist nicht committet

```
$ git status --short anvil/ tests/
 M anvil/widgets/profile_bar.py
?? tests/conftest.py
?? tests/test_profile_bar_inline_input.py
```

88 hinzugefuegte / 2 geloeschte Zeilen in `profile_bar.py` plus 300 Zeilen Tests plus die
`conftest.py` liegen nur im Arbeitsverzeichnis. Wer heute `fix/issue-103` nach `main`
mergt, bekommt Punkt 2 **unbehoben** (0 px sichtbares Eingabefeld, siehe Messung oben).

*Fix:* Aenderung und beide Testdateien committen, bevor irgendetwas gemergt oder
geschlossen wird.

### 2. [HIGH — nutzersichtbar, von diesem Branch eingefuehrt] Toast zeigt `{name}` woertlich

`anvil/widgets/profile_bar.py:805` sendet nur den Schluessel:

```python
self.profile_create_rejected.emit("toast.profile_exists")
```

`anvil/mainwindow.py:4343-4345` fuellt keinen Platzhalter:

```python
def _on_profile_create_rejected(self, message_key: str) -> None:
    Toast(self, tr(message_key))
```

Gemessen, was der Nutzer wirklich liest:

```
de | "Ein Profil namens '{name}' gibt es bereits."
en | "A profile named '{name}' already exists."
es | "Ya existe un perfil llamado '{name}'."
fr | "Un profil nomme '{name}' existe deja."
it | "Esiste gia un profilo chiamato '{name}'."
pt | "Ja existe um perfil chamado '{name}'."
ru | "Профиль с именем '{name}' уже существует."
```

In allen sieben Sprachen steht `{name}` woertlich im Toast. Der Schluessel stammt aus
`ac740d6` — also aus dem Fix fuer Punkt 2 selbst. `tests/test_profile_create_feedback.py:38`
zementiert das sogar (`assert "{name}" in toast["profile_exists"]`) und prueft in Zeile 49
ein `.format(name="Test")`, das im Produktivcode **nirgends** stattfindet.

*Fix:* entweder `profile_create_rejected = Signal(str, str)` (Schluessel + Name) und
`tr(key, name=...)`, oder `{name}` aus allen sieben Locale-Dateien entfernen. Der Test in
Zeile 38/49 muss mitgezogen werden.

### 3. [MEDIUM] Escape bricht die Eingabe nicht ab

`grep -c Key_Escape anvil/widgets/profile_bar.py` = **0**. Die Docstrings von
`_cancel_inline_create` (Zeile 824) und `_cancel_inline_rename` (Zeile 909) behaupten
„Handle Escape or focus loss" — verbunden ist nur `focus_lost`.

Gemessen (Anlegen):
```
nach Escape: inline_input gesetzt=True, selbes Objekt=True, Fokus=True, sichtbar=True
```
Gemessen (Umbenennen):
```
nach Escape: rename_input=True, Tab wieder sichtbar=False
```
Beim Umbenennen bleibt zusaetzlich der Original-Tab versteckt.

Der Nutzer kommt heraus, indem er irgendwohin klickt (`focus_lost` -> Abbruch); ein
erneuter „+"-Klick raeumt das alte Feld ueber denselben Weg weg und oeffnet ein neues.
Eine Sackgasse ist es also nicht, aber Escape tut nichts.

`git show 7a2c6f6:anvil/widgets/profile_bar.py | grep -c Key_Escape` = 0 — **keine
Regression dieses Branches**, sondern ein Altbestand. Da der Branch ausdruecklich die
Profilanlage reparieren soll und der Melder „can't seem to create a new profile"
schreibt, gehoert es trotzdem hierher.

*Fix:* `keyPressEvent` in `_FocusOutLineEdit` oder Escape im Ereignisfilter abfangen und
den passenden `_cancel_*` aufrufen.

### 4. [MEDIUM] Fenstergroesse aendern schiebt das offene Feld aus dem Bild

```
vorher:            sichtbar=200/200  viewport=441
nach resize 420:   sichtbar=0/200    viewport=151  scroll=2369/2693
nach resize 1400:  sichtbar=200/200  viewport=641
```

Bei 420 px ist das Feld vollstaendig weg. Die neue Aenderung haengt den Reveal an
`_update_container_width` (Zeile 732-736) mit dem Kommentar „Mit der Breite wandert auch
das Sichtfenster — ein offenes Eingabefeld muss danach neu ausgerichtet werden".
`resizeEvent` (Zeile 519-522) ruft aber nur `_position_fade_edges` und
`_update_fade_visibility` — **nicht** `_update_container_width`. Der Kommentar deckt einen
Fall zu, der nicht verdrahtet ist.

*Fix:* in `resizeEvent` das offene Feld erneut hereinholen (z. B. `_update_container_width()`
bzw. direkt `_reveal_input`).

### 5. [MEDIUM] Schmales Fenster: das Feld wird beschnitten

30 Profile, modernes Theme, direkt nach dem „+"-Klick:

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
`_reveal_input` (Zeile 788) bevorzugt dann bewusst die linke Kante, der Textanfang bleibt
also sichtbar und die Eingabe funktioniert. Bei 240 px sind es aber nur noch 66 px — der
Platzhalter ist dort nicht mehr lesbar. Kein Blocker, aber der Grenzfall ist eng.

Nebenbei geprueft: 200 px reichen fuer alle sieben Sprachen. Gemessene Textbreiten des
Platzhalters im modernen Theme: de 89, en 101, es 132, fr 110, it 105, pt 118, ru 112 px.
Die Kommentarangabe „es: 139 px" in Zeile 30/31 stimmt mit meiner Messung (132 px) nicht
exakt ueberein, die Schlussfolgerung bleibt richtig.

### 6. [LOW] Pillen-Container schrumpft nach dem Umbenennen nicht zurueck

2 Profile, Fenster 1600 px, langes Profil auf „A" umbenannt:

```
vorher:  container=349  max=349  hint=341
nachher: container=349  max=349  hint=160   -> 183 px Leerraum in der Pille
```

`_finish_inline_rename` / `_cancel_inline_rename` rufen `_update_container_width()` nicht auf,
im Gegensatz zu `_cancel_inline_create`. Gegenprobe an der Branch-Spitze: identische Werte
(`max=349, hint=160`) — **Altbestand, keine Regression**. Loest sich beim naechsten
`set_profiles` von selbst auf.

### 7. [LOW — Testqualitaet] Der „moderne" Testaufbau existiert so nicht

`tests/test_profile_bar_inline_input.py:34-42` setzt `bar._plus_inline` **nach** dem
Konstruktor. `_plus_inline` steuert aber schon den Aufbau (Zeilen 339, 345, 390, 399, 421,
491, 507). Im Testprozess wird kein Theme geladen, also ist `_current_palette` leer,
`is_modern_theme_active()` liefert **False** und die Leiste wird immer **klassisch**
gebaut. `modern=True` erzeugt daher eine Mischform, die es in keiner echten Konfiguration
gibt (Balken-Label und der aeussere `addStretch(1)` fehlen, das „+" wird nachtraeglich in
den Streifen umgehaengt). Umgekehrt ist ausgerechnet
`test_inline_input_is_visible_in_the_classic_theme_too` (`modern=False`) der einzige echte
Aufbau.

Ich habe alle Kernmessungen deshalb mit wirklich geladenem Theme wiederholt (siehe oben) —
das Verhalten haelt in beiden echten Themes. Der Fix ist also in Ordnung, das Testbett
misst nur nicht, was seine Namen behaupten.

*Fix:* im Test `load_theme("Anvil Dunkel")` bzw. `"Paper Dark"` setzen und `_plus_inline`
nicht von aussen ueberschreiben.

### 8. [LOW] Das „+" bleibt schwer auffindbar

30 Profile, modernes Theme, „+" jeweils **0 von 30 px** sichtbar ohne Scrollen:

```
Fenster 1280px -> Sichtfenster  581px (45%), Streifen 2640px, ~633px ungenutzt
Fenster 1600px -> Sichtfenster  741px (46%), Streifen 2640px, ~793px ungenutzt
Fenster 1920px -> Sichtfenster  901px (46%), Streifen 2640px, ~953px ungenutzt
Fenster 2560px -> Sichtfenster 1221px (47%), Streifen 2640px, ~1273px ungenutzt
```

Bei 1920 px sind **15 Radschritte** noetig, bis das „+" im Bild ist. Ursache ist der
`layout.addStretch(1)` neben `layout.addWidget(self._tab_container, 1)` (Zeilen 389-392):
die Pillengruppe bekommt nur die Haelfte der Breite, die andere Haelfte bleibt leer,
waehrend 30 Profile sich draengen. Beide Bildlaufleisten stehen auf `ScrollBarAlwaysOff`
(Zeilen 364-365); einziger Hinweis ist die rechte Fade-Kante (`_fade_right.isVisible()` =
True — gemessen, immerhin vorhanden).

Altbestand, keine Regression — aber es ist genau die Situation, aus der die Meldung
„I can't seem to create a new profile" entstanden ist. Solange das „+" das einzige
Bedienelement zum Anlegen bleibt (`_start_inline_create` wird nur an Zeile 420 aufgerufen),
bleibt der Einstieg schwach.

### 9. [INFO] Einmaliger, nicht reproduzierbarer Absturz im Testlauf

Der allererste `pytest`-Lauf im Merge-Arbeitsverzeichnis brach mit einem Core-Dump ab
(Qt-Extension-Module im Stack, kein Python-Fehler). In **acht** weiteren Laeufen desselben
Standes trat er nicht wieder auf (jeweils `333 passed, 1 skipped`). Ich kann ihn weder
zuordnen noch ausschliessen; hier festgehalten, damit er nicht verloren geht.

---

## Punkt 1 — unveraendert

Am Deploy-/`plugins.txt`-Pfad wurde nichts geaendert (`git diff --stat` betrifft nur
`anvil/widgets/profile_bar.py`). Die vier Ursachen und die vier noetigen Schritte aus
`docs/review-103-issuestand.md` gelten unveraendert weiter:

1. ein fehlgeschlagener `plugins.txt`-Schreibvorgang kippt das gesamte Deploy auf
   `success = False` und blockiert den Spielstart (`game_panel.py:1108-1122`),
2. `mainwindow.py:2540` uebergibt `details=""` — die neue, verstaendlichere Meldung aus
   `8c8036b` erreicht den Startdialog gar nicht,
3. das Flatpak-Manifest (`--filesystem=home`) blendet Flatpak-Steam aus,
4. Heroic/GOG/Epic bekommen ueber `protonPrefix()` grundsaetzlich keinen Prefix, und ein
   manuelles Feld gibt es nicht.

Das ist bekannt und so gewollt — die Entscheidung liegt beim Projektinhaber.

---

## Mergefaehigkeit

```
merge-base:                 7a2c6f6  (30.07.)
main...fix/issue-103:       20 hinter / 3 voraus
origin/main...main:         main ist 3 Commits VOR origin/main (unveroeffentlicht:
                            8768545, 46aa6ca, 49504b9)
```

Ueberschneidende Dateien zwischen `main` und Branch seit der Merge-Base:
`anvil/locales/{de,en,es,fr,it,pt,ru}.json`, `anvil/mainwindow.py`,
`anvil/widgets/game_panel.py`.

Probemerge in einem Wegwerf-Arbeitsverzeichnis (`git worktree add --detach`, danach
`git worktree remove --force`):

```
$ git merge --no-commit --no-ff main
automatischer Merge von anvil/locales/de.json
... (alle sieben Locales)
automatischer Merge von anvil/mainwindow.py
automatischer Merge von anvil/widgets/game_panel.py
Automatischer Merge abgeschlossen; halte, wie gewuenscht, vor dem Commit an
```

**Keine Konflikte.** Testlaeufe im gemergten Stand:

| Stand | Ergebnis |
|---|---|
| Arbeitsverzeichnis (Branch + unversioniert) | `237 passed, 1 skipped` |
| Merge `main` -> Branch, nur Commits | `333 passed, 1 skipped` (9 Laeufe, davon 1 Core-Dump, siehe Befund 9) |
| Merge `main` -> Branch **plus** unversionierte Aenderung + neue Tests | `352 passed, 1 skipped` |

Der Arbeitsstand wurde nicht veraendert: beide Wegwerf-Arbeitsverzeichnisse sind entfernt,
`git status` im Projekt zeigt weiterhin genau `M anvil/widgets/profile_bar.py` sowie die
beiden unversionierten Testdateien. Es wurde nichts gestasht und nichts committet.

**Technisch mergefaehig: ja.** Inhaltlich fehlt der Commit der eigentlichen Korrektur.

---

## Gesamturteil

**Ein Schliessen von #103 auf Basis dieses Branches waere nicht gerechtfertigt.**

Drei Gruende, in dieser Reihenfolge:

1. **Punkt 1 ist der Titel des Issues und unangetastet.** Der Melder kann sein Spiel weiter
   nicht starten. Solange das offen ist, ist der Issue offen — unabhaengig von der
   Profilleiste.
2. **Punkt 2 ist im gemergten Ergebnis nicht behoben.** Gemessen an der Branch-Spitze:
   „+"-Klick, Feld da, **0 px sichtbar**. Die Korrektur liegt ausschliesslich im
   unversionierten Arbeitsverzeichnis.
3. **Der Branch fuehrt einen neuen, nutzersichtbaren Fehler ein:** der Toast bei doppeltem
   Profilnamen zeigt in allen sieben Sprachen woertlich `{name}`.

Was mindestens fehlt, bevor ueberhaupt ueber ein Schliessen gesprochen werden kann:

- [ ] `anvil/widgets/profile_bar.py`, `tests/conftest.py` und
      `tests/test_profile_bar_inline_input.py` committen (Befund 1)
- [ ] `{name}` im Ablehnungs-Toast fuellen oder entfernen, inkl. der beiden Zusicherungen in
      `tests/test_profile_create_feedback.py:38/49` (Befund 2)
- [ ] Escape muss abbrechen — beim Anlegen und beim Umbenennen (Befund 3)
- [ ] Groessenaenderung des Fensters darf das offene Feld nicht aus dem Bild schieben
      (Befund 4)
- [ ] Testaufbau auf ein echt geladenes Theme umstellen, sonst misst die Testreihe eine
      Konfiguration, die es nicht gibt (Befund 7)
- [ ] Punkt 1 entscheiden: entweder beheben, oder als eigenen Issue abspalten und #103 auf
      die Profilleiste eindampfen — dann aber im Issue sichtbar dokumentieren

Punkt 3 (Scrollen) ist aus meiner Sicht fertig und braucht nichts weiter.
