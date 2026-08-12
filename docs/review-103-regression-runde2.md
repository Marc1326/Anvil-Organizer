# Regressionsprüfung Runde 2 — Issue #103

Datum: 2026-08-08
Branch: fix/issue-103 (Arbeitskopie, HEAD = 08d8588)
Geprüfter Umfang: `git diff` = **nur** `anvil/widgets/profile_bar.py` (+88/-2) sowie die noch nicht
eingecheckten Dateien `tests/test_profile_bar_inline_input.py` und `tests/conftest.py`.

Alle Zahlen unten sind gemessen (PySide6, `QT_QPA_PLATFORM=offscreen`), nicht geschätzt.
Vergleichsbasis war wie in Runde 1 die HEAD-Fassung, die im selben Lauf als eigenes Modul geladen
wurde (`git show HEAD:anvil/widgets/profile_bar.py`), damit alt und neu direkt nebeneinander messbar sind.
Messkripte liegen im Scratchpad (`s1_scroll.py` … `s9_pos.py`, Basis `r2base.py`).

## Kurzfassung

Beide Lücken aus Runde 1 sind **geschlossen**, ebenso die drei Kleinigkeiten.
Die Nachbesserungen haben dafür **eine neue Regression** erzeugt (Kapselbreite nach dem
Umbenennen) und **eine neue Nebenwirkung**, die gegenüber HEAD messbar schlechter ist
(Leiste bleibt nach dem Abbrechen am Feld stehen). Kein Absturz, keine Endlosschleife,
keine Zerstörung während laufender Signale.

## Testlauf

    .venv/bin/python -m pytest tests/ -q
    237 passed, 1 skipped in 5.19s

    QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q -p no:randomly
    237 passed, 1 skipped in 4.81s

`python -m py_compile` auf `profile_bar.py`, `tests/test_profile_bar_inline_input.py` und
`tests/conftest.py` sauber. `./restart.sh` wurde auftragsgemäß nicht ausgeführt.

## Die beiden offenen Punkte aus Runde 1

### Lücke 1 — laufende Scroll-Timer scrollen das Feld wieder weg → **geschlossen**

Gemessen mit 30 Profilen bei 900 px Leistenbreite, sichtbare Breite des Feldes von 200 px:

| Ablauf | ALT (HEAD) | NEU |
|---|---|---|
| Klick auf „Profile 27“, danach sofort „+“, direkt nach dem Reveal | 0/200 | 200/200 |
| dieselbe Stelle, nach Ablauf des 200-ms-Klick-Timers | 0/200 | 200/200 |
| `set_profiles()` kurz vor „+“, nach Ablauf von `_delayed_select` (100 ms) | 0/200 | 200/200 |

`_scroll_to_tab()` steigt bei offenem Feld aus (`profile_bar.py:706`), damit greifen weder
`_delayed_select` noch `_on_click_timer_timeout` dem Reveal ins Handwerk. Der Klick-Timer wird in
`_start_inline_create()` weiterhin nicht gestoppt — das ist hier folgenlos, weil
`mainwindow._on_profile_changed` (`mainwindow.py:4483`) die Leiste nicht neu aufbaut, sondern nur
den Profilordner anlegt und den Zähler auffrischt.

### Lücke 2 — `set_profiles` hinterlässt bei offenem Feld eine Karteileiche → **geschlossen**

Gemessen, Feld offen, dann `set_profiles(...)`:

| Prüfung | ALT (HEAD) | NEU |
|---|---|---|
| `_inline_input` danach | Objekt bleibt gesetzt | `None` |
| Feld im Layout | freischwebend, sichtbar | 0 Felder im Streifen |
| `parent()` des alten Feldes | `_tabs_widget` | `None` |
| „+“ danach noch benutzbar | nein (tot) | ja |
| beim Umbenennen versteckter Tab | blieb versteckt | 0 von 30 versteckt |
| `_rename_tab` | blieb gesetzt | `None` |

Auch der Weg über `_on_profile_deleted` (Profil löschen, während das Feld offen ist) räumt jetzt
sauber auf: 29 Tabs, `_inline_input is None`, aktives Profil wieder voll sichtbar (80/80 px).

### Die drei Kleinigkeiten aus Runde 1

* **Zerstörtes C++-Objekt im Reveal** → geschlossen. `QTimer.singleShot(0, self, …)` bindet den
  Rückruf an die Leiste. Gemessen: Leiste mit offenem Feld zerstört, danach 300 ms Ereignisschleife —
  kein `RuntimeError` mehr (vorher reproduzierbar mit `shiboken6.delete()`).
* **Pos1/Ende vom Ziffernblock** → geschlossen. Gemessen über `eventFilter`:

  | Modifier | behandelt | Scrollwert |
  |---|---|---|
  | keiner | ja | 2217 (Maximum) |
  | Ziffernblock | ja | 2217 |
  | Strg | nein | 0 |
  | Strg + Ziffernblock | nein | 0 |
  | Umschalt | nein | 0 |
  | Alt | nein | 0 |

  Andere Tasten (z. B. Pfeil links) werden nicht angefasst.
* **Zwei verschiedene Feldbreiten** → geschlossen, beide Pfade nutzen `INLINE_INPUT_WIDTH`.
  Gemessen im klassischen Theme (`is_modern_theme_active` auf `False` gepatcht, „+“ liegt dort
  außerhalb des Streifens): Anlegen 200/200 px sichtbar, Umbenennen 200/200 px — ALT jeweils 0/140.

## Neue Befunde

### [MITTEL] Umbenennen bläht die Pillen-Kapsel auf und schrumpft sie nie zurück

- Datei: `anvil/widgets/profile_bar.py:863` (neues `_update_container_width()` in
  `_start_inline_rename`) gegen `:874-906` (`_finish_inline_rename`) und `:908-920`
  (`_cancel_inline_rename`) — beide rufen `_update_container_width()` **nicht** auf.
- Der Anlege-Pfad ist symmetrisch (`_start_inline_create` :761, `_finish_inline_create` :815,
  `_cancel_inline_create` :833). Der Umbenennen-Pfad ist es seit dieser Änderung nicht mehr:
  vorher hat `_start_inline_rename` die Breite gar nicht angefasst, jetzt vergrößert es sie und
  niemand macht sie wieder klein.
- Gemessen mit 3 Profilen („Default“, „Vanilla“, „Test“) bei 900 px Leistenbreite:

  | Zeitpunkt | ALT maxW/istW | NEU maxW/istW | benötigt (`sizeHint`) |
  |---|---|---|---|
  | Start | 260/260 | 260/260 | 252 |
  | Umbenennen-Feld offen | 260/260 | 387/387 | 379 |
  | nach Escape | 260/260 | **387/387** | 252 |
  | nach Enter (Name „Xy“) | 260/260 | **387/387** | 226 |

- Sichtbare Folge: nach einem bestätigten Umbenennen rutscht der erste Aktionsknopf von x=274 auf
  x=401 (127 px nach rechts), in der Kapsel stehen 153 px Leerraum. Der Anlege-Zyklus zeigt das
  nicht — dort geht die Kapsel nach Escape korrekt auf 260 zurück.
- Es heilt sich erst beim nächsten `set_profiles()` (gemessen: Knopf wieder bei x=248, maxW=234).
  `mainwindow._on_profile_renamed` ruft `set_profiles` aber nur im Fehlerfall (`reject_rename`,
  `mainwindow.py:4444`) — nach einem erfolgreichen Umbenennen bleibt die Kapsel breit, bis der
  Nutzer die Instanz wechselt oder ein Profil anlegt/löscht.
- Bei vielen Profilen fällt es nicht auf, weil die Kapsel dort ohnehin durch den Platz begrenzt ist.
  Betroffen ist der Normalfall mit wenigen Profilen.
- Fix: `_update_container_width()` am Ende von `_finish_inline_rename` und `_cancel_inline_rename`
  aufrufen — genau wie im Anlege-Pfad.

### [NIEDRIG] Nach dem Abbrechen bleibt die Leiste am Feld stehen, das aktive Profil bleibt draußen

- Datei: `anvil/widgets/profile_bar.py:822-833` (`_cancel_inline_create`) im Zusammenspiel mit
  `:706` (`_scroll_to_tab` steigt bei offenem Feld aus)
- Das Feld wird beim Anlegen ganz rechts eingefügt, der Reveal schiebt die Leiste ans Ende.
  Beim Abbrechen wird nur das Feld entfernt; niemand holt das aktive Profil zurück ins Bild.
- Gemessen, 30 Profile, aktiv „Default“ (ganz links), 900 px Leistenbreite:

  | Ablauf | ALT Scroll / Default sichtbar | NEU Scroll / Default sichtbar |
  |---|---|---|
  | Start | 0 / 80 von 80 px | 0 / 80 von 80 px |
  | nach „+“ | 0 / 80 px (Feld 0/200 = der Fehler) | 2387 / — (Feld 200/200) |
  | nach Escape | 0 / **80 von 80 px** | 2217 / **0 von 80 px** |

  Dasselbe Bild, wenn `set_profiles()` kurz vorher lief: ALT landet nach dem Abbruch bei Scroll 11
  und zeigt Default zu 69/80 px, NEU bleibt bei 2217 und zeigt 0/80 px.
- Leicht erreichbar: „+“ drücken, es sich anders überlegen, irgendwohin klicken (der
  anwendungsweite Filter bei :952 bricht dann ab) oder Escape drücken.
- Das ist der Preis des gewollten Reveals und keine Fehlfunktion, aber gegenüber HEAD messbar
  schlechter. Fix: in `_cancel_inline_create` / `_cancel_inline_rename` nach dem Aufräumen den
  aktiven Tab wieder anfahren (`_scroll_to_tab` läuft dann wieder durch, weil die Felder schon
  auf `None` stehen).

### [NIEDRIG] Der Aufräumblock in `set_profiles` ruft sich selbst über `focus_lost` wieder auf

- Datei: `anvil/widgets/profile_bar.py:591-597`
- Provoziert und gemessen: `field.setParent(None)` nimmt dem fokussierten Feld synchron den Fokus,
  `_FocusOutLineEdit` feuert `focus_lost`, und der bereits verbundene Handler läuft **mitten in der
  Schleife** los. Signalspur (Anlege-Feld):
  `[('cancel_enter', _inline_input is edit = True), ('cancel_exit', None), ('focus_lost', …)]`.
  Beim Umbenennen-Feld dasselbe: `_cancel_inline_rename` läuft durch, setzt `_rename_input`/`_rename_tab`
  auf `None` und ruft `tab.show()` auf einem Tab, den `set_profiles` unmittelbar danach löscht.
- Folgen, alle gemessen und harmlos: `setParent(None)` und `deleteLater()` laufen doppelt (Qt fängt
  das ab, `shiboken6.isValid(edit)` erst nach der Ereignisschleife `False`), und
  `_update_container_width()` läuft einmal zusätzlich, bevor die alten Tabs entfernt sind.
  **Keine Ausnahme, kein Absturz, kein doppeltes Feld** — auch nicht, wenn `set_profiles` aus einem
  echten `returnPressed`-Signal heraus gestartet wird (Feld wird sauber übernommen,
  neuer Tab „Frisch“ aktiv) oder wenn der noch offene 0-ms-Reveal-Timer auf ein gelöschtes Feld trifft
  (die Identitätsprüfung bei :778 fängt das ab).
- Zwei Felder gleichzeitig sind nicht erreichbar: `_start_inline_rename` setzt den Fokus, das
  Anlege-Feld bricht dabei selbst ab (gemessen: `inline=False, rename=True`).
- Sauberer wäre, in `set_profiles` vor dem Löschen die Signale zu trennen oder die vorhandenen
  Abbruchmethoden aufzurufen, statt an ihnen vorbei zu löschen. Kein Muss.

### [NIEDRIG] Größenänderung der Leiste bei offenem Feld schiebt es wieder aus dem Bild

- Datei: `anvil/widgets/profile_bar.py:519-522` (`resizeEvent` ruft `_update_container_width` nicht)
- Der Kommentar bei :732 verspricht, dass ein offenes Feld nach einer Breitenänderung neu
  ausgerichtet wird. Das gilt nur für die Aufrufer von `_update_container_width` — eine echte
  Größenänderung des Widgets gehört nicht dazu.
- Gemessen, 30 Profile, Feld offen und weiterhin fokussiert:

  | Breitenwechsel | ALT Feld sichtbar | NEU Feld sichtbar |
  |---|---|---|
  | 900 → 1400 | 0/200 | 200/200 |
  | 900 → 600 | 0/200 | **0/200** |
  | 900 → 400 | 0/200 | **0/200** |

- Gegenüber HEAD keine Verschlechterung (dort war es ohnehin 0), aber beim Verkleinern kehrt das
  Symptom aus #103 zurück: das Feld hat den Fokus und ist nicht zu sehen.
- Erreichbarkeit ist schmal: ein Mausklick auf den Fensterrand bricht das Feld über den
  anwendungsweiten Filter meist vorher ab. Ohne Klick (Kachel-Fenstermanager, Tastenkürzel, ein
  Panel das sich per Kürzel öffnet) bleibt das Feld stehen.
- Fix: `resizeEvent` um `_update_container_width()` bzw. einen direkten `_reveal_input` ergänzen.

### [NIEDRIG] Der 100-ms-Timer in `set_profiles` hat weiterhin kein Kontextobjekt

- Datei: `anvil/widgets/profile_bar.py:642` — `QTimer.singleShot(100, _delayed_select)`
- Die beiden neuen Reveal-Timer haben `self` als Kontext bekommen (:770, :872), dieser nicht.
- Gemessen: Leiste nach `set_profiles()` sofort zerstört, dann 400 ms Ereignisschleife →
  `RuntimeError: Internal C++ object (PySide6.QtWidgets.QPushButton) already deleted` aus
  `_delayed_select` → `_select_profile`. **Identisch in ALT und NEU** — Bestand, keine Regression.
  Qt fängt die Ausnahme ab, der Ablauf läuft weiter, im Log steht ein Traceback.
- Fix wäre derselbe Einzeiler: `QTimer.singleShot(100, self, _delayed_select)`.

## Ausdrücklich geprüft und unauffällig

- **Keine Endlosschleife über `_update_container_width` → `_reveal_input`.** Mit Tiefenzähler
  gemessen: maximale Verschachtelung 1, „+“ = 1× `_update_container_width` + 1× `_reveal_input`,
  Escape = 2× `_update_container_width` + 0× `_reveal_input`, Umbenennen = 1×/1×.
  `_reveal_input` ruft `_update_container_width` nicht zurück, und `valueChanged` landet nur in
  `_update_fade_visibility`. Ein Sprung an eine falsche Stelle ist nicht möglich: die
  Identitätsprüfung bei :778 lässt nur genau das Feld durch, auf das `_inline_input`/`_rename_input`
  gerade zeigt, und `field` in `_update_container_width` stammt aus denselben beiden Feldern.
- **Mausrad über dem „+“-Knopf.** ALT: `handled=False`, Scrollwert bleibt 0. NEU: `handled=True`,
  Scrollwert 120 — das Rad scrollt jetzt also auch über „+“. Im klassischen Theme liegt „+“ außerhalb
  des Streifens (`_tabs_layout.indexOf(_btn_add) == -1`), auch dort wird gescrollt und das Ereignis
  verbraucht. Das stört nichts: die ProfileBar hängt in `mainwindow.py:267` in einem einfachen
  `QVBoxLayout`, es gibt keinen scrollbaren Vorfahren, dem das Rad entzogen würde.
- **Die fünf geforderten Abläufe, jeweils gemessen (30 Profile, 900 px).**

  | Ablauf | ALT aktiver Tab sichtbar | NEU aktiver Tab sichtbar |
  |---|---|---|
  | Profil per Klick wechseln | 93 von 93 px | 93 von 93 px |
  | Instanz wechseln (`set_profiles`, aktiv = Profile 27) | 93/93 | 93/93 |
  | Profil anlegen + Enter | 108/108 (neuer Tab) | 108/108 |
  | Profil umbenennen + Enter | 0 px | **106 px** (neu besser) |
  | Profil löschen bei offenem Feld | 80/80 | 80/80 |
  | Abbruch per Escape | 93/93 | 93/93 (aktives Profil rechts) |

  Dauerhaft unterdrückt wird das Scrollen zum aktiven Profil in keinem dieser Abläufe: `_scroll_to_tab`
  hat nur einen Aufrufer (`_select_profile`, :683), und in allen fünf Wegen stehen
  `_inline_input`/`_rename_input` zu diesem Zeitpunkt auf `None`. Der einzige Fall, in dem der
  Rücksprung ausbleibt, ist der oben beschriebene Abbruch mit weit entferntem aktiven Profil.
- **Mehrfaches „+“.** Zweiter Aufruf legt kein zweites Feld an (1 Feld im Layout), nach
  `set_profiles` sind 0 Felder übrig und „+“ funktioniert wieder.
- **Drag & Drop.** `eventFilter` steigt bei offenem Feld weiterhin vor der Drag-Logik aus (:979).
- **`tests/conftest.py`.** Setzt `QT_QPA_PLATFORM` per `setdefault`, greift also nur, wenn die
  Variable nicht schon gesetzt ist. Läuft vor dem Import der Testmodule, damit ziehen auch
  `test_profile_bar_scrolling.py` und `test_profile_bar_inline_input.py` ohne Display an.
  Kein Einfluss auf die Nicht-Qt-Tests.
- **Übersetzungen.** Der Diff bringt keinen neuen sichtbaren Text (nur Kommentare, eine Konstante,
  Logik). `tests/test_translations.py` läuft durch, keine Locale-Datei betroffen.
- **Architektur-Regeln** (Mod-Dateien nur als Symlink, `.mods/`-Struktur, Frameworks,
  `active_mods.json` in allen Profilen, globale API): vom Diff nicht berührt — reine
  GUI-Änderung an der Profilleiste, kein Datei- oder Profilinhalt wird angefasst.

## Nicht geprüft

`./restart.sh` wurde auftragsgemäß nicht ausgeführt. Alle Messungen liefen offscreen gegen frisch
erzeugte ProfileBar-Objekte, keine Produktionsdaten berührt.

## Ergebnis

**NEEDS FIXES** — wegen des MITTEL-Befunds. Die beiden Lücken aus Runde 1 sind sauber geschlossen,
aber `_start_inline_rename` vergrößert die Pillen-Kapsel jetzt dauerhaft (127 px Versatz der
Aktionsknöpfe nach jedem Umbenennen). Der Einzeiler `_update_container_width()` in
`_finish_inline_rename` und `_cancel_inline_rename` behebt es. Die vier NIEDRIG-Befunde sind
keine Commit-Blocker.
