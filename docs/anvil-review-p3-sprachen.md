# Sprachprüfung Punkt 3 — Reihenfolge, Dateinamen, Archiv-Gewinner

Geprüft am 13.08.2026. Grundlage: `git diff anvil/locales/` gegen HEAD (8179975).
Sieben Dateien: de, en, es, fr, it, pt, ru.

---

## Kurzfassung

Die eigentliche Übersetzungsarbeit ist **sauber**: alle 13 neuen Schlüssel liegen
in allen sieben Sprachen, alle Platzhalter stimmen, alle Dateien sind gültiges
JSON, die Diffs sind klein und gezielt, die deutschen Texte sind gut lesbar und
korrekt geschrieben.

Es gibt **einen kritischen Fund** — er stammt aber **nicht** aus dieser Änderung,
sondern liegt als Altlast direkt daneben im selben Dialog (`mod_detail_dialog.py`):
neun `tr()`-Schlüssel werden im Code benutzt, existieren aber in **keiner** der
sieben Dateien. Der Nutzer sieht dort rohe Schlüsselnamen auf dem Bildschirm.

Dazu ein unbenutzter neuer Schlüssel (`order_scope.hide`) und acht verwaiste
Schlüssel aus zwei entfernten Dialogen.

---

## 1. Vollständigkeit — BESTANDEN

Alle 13 neuen plus der eine geänderte Schlüssel sind in **allen sieben** Sprachen
vorhanden. Nachgezählt, kein Fehlender:

| Schlüssel | Sprachen |
|---|---|
| `context.keep_file_names` | 7/7 |
| `tooltip.keep_file_names` | 7/7 |
| `log.keep_file_names_on` | 7/7 |
| `log.keep_file_names_off` | 7/7 |
| `order_scope.tooltip_head` | 7/7 |
| `order_scope.numbered_all` | 7/7 |
| `order_scope.numbered_dirs` | 7/7 |
| `order_scope.numbered_rest` | 7/7 |
| `order_scope.not_numbered` | 7/7 |
| `order_scope.bethesda_plugins` | 7/7 |
| `order_scope.hide` | 7/7 |
| `mod_detail.archive_winner_unsure` | 7/7 |
| `mod_detail.archive_winner_numbered` | 7/7 |
| `mod_detail.archive_conflicts_hint` (geändert) | 7/7 |

Darüber hinaus: **jede der sieben Dateien hat exakt 1393 Schlüssel**, und der
Vergleich jeder Sprache gegen `de.json` ergibt „fehlt 0, extra 0". Die Dateien
sind strukturell deckungsgleich.

## 2. Platzhalter — BESTANDEN

Maschinell verglichen (Regex `\{[^}]*\}`, sortiert, gegen `de.json` als Original):

- `log.keep_file_names_on` / `_off` → `{name}` in allen 7 Sprachen, identisch
- `order_scope.numbered_dirs` → `{dirs}` in allen 7 Sprachen, identisch
- `order_scope.numbered_rest` → `{rest}` in allen 7 Sprachen, identisch
- alle übrigen neuen Schlüssel: keine Platzhalter, in keiner Sprache einer
  hinzuerfunden

Keine Abweichung, keine Leerzeichen in den Klammern, keine unbalancierten
Klammern. Die Aufrufseite passt dazu:
`anvil/core/load_order_scope.py:103` (`dirs=`), `:107` (`rest=`),
`anvil/mainwindow.py:2246` (`name=`).

## 3. JSON-Gültigkeit — BESTANDEN

Alle sieben Dateien mit `json.load()` geladen, alle OK.

## 4. Diff-Umfang — BESTANDEN

```
anvil/locales/de.json | 24 ++++++++++++++++++++----
... (identisch für alle 7)
7 files changed, 140 insertions(+), 28 deletions(-)
```

Exakt 20 hinzugefügte und 4 geänderte Zeilen pro Datei — durchgehend gleich.
Nichts wurde umformatiert, nichts gelöscht, keine Einrückung verrutscht.

---

# FUNDE

## KRITISCH — 9 tr()-Schlüssel im Code, die es in keiner Sprache gibt

**Nicht durch diese Änderung verursacht** (Altlast), aber sieben davon sitzen im
**selben Dialog und im selben Codeblock**, der gerade angefasst wurde — die
Info-Zeile direkt unter dem geänderten Archiv-Hinweis.

Belegt durch echten `tr()`-Aufruf, nicht durch Textsuche:

```
tr('mod_detail.conflicts_count')      -> 'mod_detail.conflicts_count'
tr('mod_detail.conflicts_with_ignored') -> 'mod_detail.conflicts_with_ignored'
tr('mod_detail.wins_conflicts')       -> 'mod_detail.wins_conflicts'
tr('mod_detail.loses_conflicts')      -> 'mod_detail.loses_conflicts'
tr('mod_detail.ini_files_found')      -> 'mod_detail.ini_files_found'
tr('mod_detail.plugins_count')        -> 'mod_detail.plugins_count'
tr('mod_detail.ignored_matches')      -> 'mod_detail.ignored_matches'
tr('mod_detail.error')                -> 'mod_detail.error'
tr('game_panel.shim_steam_hint')      -> 'game_panel.shim_steam_hint'
```

Der Fallback auf Englisch greift nicht, weil die Schlüssel auch in `en.json`
fehlen (in allen sieben geprüft). `anvil/core/translator.py:88-89` gibt dann den
Schlüssel selbst zurück.

| Schlüssel | Verwendungsstelle |
|---|---|
| `mod_detail.conflicts_count` | `anvil/dialogs/mod_detail_dialog.py:1533` |
| `mod_detail.conflicts_with_ignored` | `anvil/dialogs/mod_detail_dialog.py:1531` |
| `mod_detail.wins_conflicts` | `anvil/dialogs/mod_detail_dialog.py:1411`, `:1414` |
| `mod_detail.loses_conflicts` | `anvil/dialogs/mod_detail_dialog.py:1441`, `:1446` |
| `mod_detail.ini_files_found` | `anvil/dialogs/mod_detail_dialog.py:736` |
| `mod_detail.plugins_count` | `anvil/dialogs/mod_detail_dialog.py:922`, `:964`, `:1007`, `:1008` |
| `mod_detail.ignored_matches` | `anvil/dialogs/mod_detail_dialog.py:1399` |
| `mod_detail.error` | `anvil/dialogs/mod_detail_dialog.py:656`, `:845` |
| `game_panel.shim_steam_hint` | `anvil/widgets/game_panel.py:2763` |

Besonders auffällig: `mod_detail.wins_conflicts` wird in Zeile 1411 zusätzlich
mit `.upper()` verarbeitet — der Nutzer sieht dort also `MOD_DETAIL.WINS_CONFLICTS`
in Großbuchstaben als Überschrift über der Gewinner-Liste.

Auch `mod_detail.error` ist verdächtig: zwei Zeilen darüber steht jeweils
`tr("mod_detail.error_loading", ...)`, und **dieser** Schlüssel existiert
(`error_loading = 'Fehler beim Laden: {error}'`). Vermutlich ein Tippfehler in
`:656` und `:845`.

**Vorschlag:**
1. `mod_detail.error` in `:656` und `:845` auf `mod_detail.error_loading`
   umbiegen — der Schlüssel existiert und hat denselben `{error}`-Platzhalter.
2. Die übrigen acht Schlüssel in allen sieben Dateien anlegen. Deutsche Entwürfe:
   - `conflicts_count` = `"{count} Konflikte"`
   - `conflicts_with_ignored` = `"{total} Konflikte ({ignored} ignoriert)"`
   - `wins_conflicts` = `"Gewinnt {count} Konflikte"`
   - `loses_conflicts` = `"Verliert {count} Konflikte"`
   - `ini_files_found` = `"{count} INI-Dateien gefunden"`
   - `plugins_count` = `"{count} Plugins"`
   - `ignored_matches` = `"{count} Treffer ignoriert"`
   - `game_panel.shim_steam_hint` = Text mit `{overrides}`, Inhalt muss Marc
     festlegen (es geht um WINEDLLOVERRIDES, die Steam nicht selbst setzen kann)

Weil das eine Altlast ist und die Texte inhaltlich abgestimmt werden müssen,
wäre das ein eigener Commit — nicht in den laufenden mit hineinmischen.

---

## MITTEL — `order_scope.hide` existiert, wird aber nirgends benutzt

`order_scope.hide` liegt in allen sieben Sprachen (de: `"Hinweis ausblenden"`),
kommt aber im gesamten Python-Code **kein einziges Mal** vor. Gegengeprüft mit
Volltextsuche über `anvil/` und `tests/`.

Das ist mehr als Ballast: der Schlüssel wurde offensichtlich für den
Ausblenden-Knopf der Hinweiszeile geschrieben, und dieser Knopf hat aktuell
**gar keinen erklärenden Text**:

`anvil/mainwindow.py:314-320`
```python
self._order_hint_close = QToolButton()
self._order_hint_close.setText("×")
self._order_hint_close.setAutoRaise(True)
self._order_hint_close.clicked.connect(
    lambda checked=False: self._hide_order_hint(),
)
```

Marc sieht ein nacktes `×` ohne Tooltip. Dass ein Klick darauf den Hinweis
**dauerhaft und pro Spiel** wegschaltet (`anvil/mainwindow.py:2188-2191`,
gespeichert unter `ModList/order_hint_hidden/<Spiel>`), erfährt er nirgends.

**Vorschlag:** eine Zeile nach `:316` einfügen —
`self._order_hint_close.setToolTip(tr("order_scope.hide"))`.
Damit ist der Schlüssel benutzt und der Knopf erklärt sich selbst.

---

## MITTEL — `archive_winner_unsure`: „bei diesem Spiel" fehlt in es, fr, it, pt

Der deutsche Satz schränkt die Aussage ausdrücklich auf das aktuelle Spiel ein:

> „Wer bei gepackten Archiven gewinnt, entscheidet **bei diesem Spiel** nicht die
> Reihenfolge in Anvil, sondern das Spiel selbst."

Englisch (`in this game`) und Russisch (`в этой игре`) haben diese Einschränkung
ebenfalls. In vier Sprachen fehlt sie ersatzlos:

| Datei | Text | fehlt |
|---|---|---|
| `anvil/locales/es.json:995` | „En los archivos empaquetados no decide el orden en Anvil, sino el propio juego." | „en este juego" |
| `anvil/locales/fr.json:995` | „Pour les archives compressées, ce n'est pas l'ordre dans Anvil qui décide, mais le jeu lui-même." | „dans ce jeu" |
| `anvil/locales/it.json:995` | „Per gli archivi compressi non decide l'ordine in Anvil, ma il gioco stesso." | „in questo gioco" |
| `anvil/locales/pt.json:995` | „Nos arquivos compactados não é a ordem no Anvil que decide, mas o próprio jogo." | „neste jogo" |

Damit liest sich der Satz in diesen vier Sprachen wie eine **allgemeine Regel für
alle Spiele** — und widerspricht damit dem Gegenstück
`order_scope.numbered_all`, das im selben Programm behauptet, die Reihenfolge
komme sehr wohl im Spiel an. Für Spanisch/Französisch/Italienisch/Portugiesisch
könnten beide Sätze denselben Nutzer erreichen, sobald er die Instanz wechselt.

Zweitens fehlt in denselben vier Fassungen das Subjekt „wer gewinnt" —
es steht nur „X entscheidet nicht, sondern Y", ohne zu sagen, worüber.

**Vorschlag:**
- es: „En los archivos empaquetados **de este juego**, quién gana no lo decide el orden en Anvil, sino el propio juego."
- fr: „Pour les archives compressées, **dans ce jeu** ce n'est pas l'ordre dans Anvil qui décide du gagnant, mais le jeu lui-même."
- it: „Per gli archivi compressi, **in questo gioco** a decidere chi vince non è l'ordine in Anvil, ma il gioco stesso."
- pt: „Nos arquivos compactados **deste jogo**, quem ganha não é decidido pela ordem no Anvil, mas pelo próprio jogo."

---

## KLEIN — „Bei gepackten Archiven" steht zweimal im selben Absatz (de)

`anvil/dialogs/mod_detail_dialog.py:1519-1521` klebt die beiden Sätze mit einem
Leerzeichen aneinander. Auf Deutsch ergibt das:

> „**Bei gepackten Archiven** zeigt Anvil nur die Anzahl gemeinsamer Spieldateien —
> die Dateinamen stehen nicht im Archiv, nur Prüfsummen. Wer **bei gepackten
> Archiven** gewinnt, entscheidet bei diesem Spiel nicht die Reihenfolge in Anvil,
> sondern das Spiel selbst."

Inhaltlich richtig, aber die Wiederholung fällt auf und klingt nach
Textbaustein-Montage. Das gleiche Problem in es, it, pt („En los archivos
empaquetados … En los archivos empaquetados", „Per gli archivi compressi … Per
gli archivi compressi", „Nos arquivos compactados … Nos arquivos compactados").

**Vorschlag (de):** im zweiten Satz die Wiederholung streichen —
`archive_winner_unsure` = „Wer dabei gewinnt, entscheidet bei diesem Spiel nicht
die Reihenfolge in Anvil, sondern das Spiel selbst."
Der zweite Satz wird ausschließlich hinter `archive_conflicts_hint` gehängt
(`mod_detail_dialog.py:1519`), das „dabei" hat also immer seinen Bezug.

## KLEIN — Anrede springt zwischen den neuen Texten

`order_scope.numbered_all` und `numbered_dirs` duzen („**Deine** Reihenfolge").
Das passt zur Mehrheit der App — Duz-Form kommt in `de.json` 17-mal vor,
Sietz-Form nur 5-mal.

Direkt daneben steht aber `tooltip.keep_file_names`:

> „Anvil lässt die Dateinamen dieser Mod unverändert.\n**Ihre** Position in der
> Liste wirkt dadurch nicht mehr, …"

Grammatisch ist „Ihre" hier das Possessivpronomen der Mod, nicht die
Höflichkeitsform. Beim Lesen im Tooltip — direkt nach einem Satz, der mit
„Anvil" beginnt — kann man es aber sekundenlang als Siezen lesen, während zwei
Zeilen weiter geduzt wird.

**Vorschlag:** „**Diese Mod** wirkt dadurch nicht mehr über ihre Position in der
Liste, und eine gleichnamige Datei einer anderen Mod kann zusätzlich im Spiel
liegen." — oder schlicht „Ihre" durch „Die" ersetzen.

## KLEIN — „Ausrollen" vs. Knopfaufschrift „Deploy"

Die neuen deutschen Texte sagen „beim **Ausrollen**"
(`order_scope.numbered_all`, `numbered_dirs`). Der Knopf, den Marc dafür drückt,
heißt in der Oberfläche `toolbar.deploy` = **„Deploy"**, und 18 weitere deutsche
Texte verwenden ebenfalls „Deploy" (`context.set_deploy_path`,
`status.deploy_auto`, `error.deploy_failed_title` …).

Kein Fehler — `preset.stray_moved` sagt bereits „ab dem nächsten Ausrollen", der
Begriff ist also nicht neu erfunden. Aber wer den Hinweis liest und dann den
Knopf sucht, findet kein „Ausrollen".

**Vorschlag:** entweder „beim Deploy" schreiben, oder einmal projektweit
entscheiden und `preset.stray_moved` mitziehen. Marcs Entscheidung.

## KLEIN — Russisch: „лose Dateien" ungenau übersetzt

`anvil/locales/ru.json:1484` und `:1485` übersetzen „lose Dateien" mit
**„отдельные файлы"** („einzelne Dateien"). Der Gegensatz, um den es geht —
entpackt/lose gegen gepackt/im Archiv — geht dabei verloren; „отдельные" heißt
nur „einzelne, getrennte".

In `not_numbered` verschiebt das zusätzlich die Satzaussage:
„В этой игре порядок **определяет только отдельные файлы**" liest sich als „die
Reihenfolge bestimmt nur einzelne Dateien" statt „entscheidet nur über lose
Dateien".

**Vorschlag:** „отдельные файлы" durch **„распакованные файлы"** ersetzen
(gebräuchlich in der russischen Modding-Szene, exakter Gegenbegriff zu
„упакованные архивы", das im selben Satz steht). Also:
`not_numbered` → „В этой игре порядок определяет только **распакованные файлы**."
`numbered_rest` → „За их пределами ({rest}) порядок действует только для **распакованных файлов**."

---

# TOTE SCHLÜSSEL — die beiden entfernten Dialoge

Beide gesucht, beide gefunden. **Nichts davon wurde entfernt**, wie beauftragt.

## Entsperr-Dialog — 2 Schlüssel × 7 Sprachen = 14 Einträge

Entfernt in Commit **d0b8a4e** „Entsperren loest nur die Sperre, keine doppelten
Presets mehr".

| Schlüssel | Deutscher Text |
|---|---|
| `dialog.unlock_purge_title` | „Spiel entsperren" |
| `dialog.unlock_purge_text` | „Die Mods liegen noch im Spielordner.\n\nJetzt entfernen? Wenn das Spiel noch läuft, stürzt es dabei ab.\nBeim nächsten Spielstart räumt Anvil ohnehin auf." |

Dass diese wirklich tot sind, ist im Projekt sogar **festgeschrieben**:
`tests/test_entsperren.py:125-131` prüft ausdrücklich, dass `"unlock_purge"` im
Quelltext von `MainWindow._on_unlock_clicked` **nicht** vorkommt
(`assert verboten not in quelle, f"{verboten} ist zurueck"`). Der Dialog soll
also nie wiederkommen. Die Schlüssel können bedenkenlos weg.

## Steam-Startdialog — 6 Schlüssel × 7 Sprachen = 42 Einträge

Eingeführt in **5f6ec4f** „Spielstart fragt nach, wenn Steam nicht laeuft",
wieder entfernt in **833246c** „Steam startet ohne Rueckfrage". Seitdem startet
`anvil/widgets/game_panel.py:2694` Steam kommentarlos, ohne Rückfrage.

| Schlüssel | Deutscher Text |
|---|---|
| `game_panel.steam_not_running_text` | „Dieses Spiel braucht einen laufenden Steam-Client, sonst kommt der Startbefehl nirgendwo an.\n\nSteam jetzt starten?" |
| `game_panel.steam_start_now` | „Steam starten" |
| `game_panel.steam_continue_without` | „Ohne Steam weiter" |
| `game_panel.steam_cancel` | „Abbrechen" |
| `game_panel.steam_wait_title` | „Warten" |
| `game_panel.steam_wait_text` | „Auf OK klicken, sobald die Anmeldung bei Steam abgeschlossen ist." |

**Achtung beim Aufräumen:** zwei benachbarte Schlüssel derselben Gruppe werden
weiterhin gebraucht und dürfen **nicht** mit gelöscht werden:
- `game_panel.steam_not_running_title` → `game_panel.py:2702`
- `game_panel.steam_start_failed` → `game_panel.py:2703`

Ebenso ist `game_panel.steam_not_found` (`:2735`) aktiv.

## Nicht tot, obwohl sie in der Textsuche fehlen

Diese drei Gruppen sehen bei einfacher Suche verwaist aus, werden aber über
zusammengesetzte Schlüssel benutzt — beim Aufräumen nicht anfassen:

| Schlüssel | wird gebildet in |
|---|---|
| `dialog.start_while_running_text`, `dialog.start_while_unknown_text` | `anvil/widgets/game_panel.py:2002-2007` (Variable `key`) |
| `status.fw_unlocked` | `anvil/mainwindow.py:9528` (Ternär im `tr()`-Argument) |
| `status.fw_auto_reason_anvil_start`, `status.fw_auto_reason_game_start` | `anvil/mainwindow.py:9546` (f-String) |

## Weitere Verwaiste, außerhalb des Auftrags

Insgesamt haben **235 von 1393** Schlüsseln in `de.json` keine `tr()`-Fundstelle.
Nicht alle davon sind tot — dynamisch gebaute Schlüssel wie
`storage.component_*` und `preset.variant_*` sind darin enthalten. Aufgefallen
sind zusätzlich `proton_tools.browse`, `.launch`, `.new_tool`, `.no_instance`,
`.tools_label` und `tooltip.start`. Das war nicht Teil des Auftrags und ist nur
zur Kenntnis notiert.

---

# UNSICHER

1. **Ob die 9 fehlenden `mod_detail`/`game_panel`-Schlüssel je vorhanden waren.**
   Ich habe die Git-Historie nicht rückwärts durchsucht — belegt ist nur, dass sie
   **heute** in keiner der sieben Dateien stehen und `tr()` den rohen Schlüssel
   ausgibt. Ob sie versehentlich gelöscht oder nie angelegt wurden, weiß ich nicht.

2. **Die vorgeschlagenen deutschen Texte für die fehlenden Schlüssel** sind meine
   Entwürfe, kein Befund. Besonders `game_panel.shim_steam_hint` (Platzhalter
   `overrides=`) müsste Marc inhaltlich festlegen — ich kenne den Wortlaut nicht,
   den er dort sehen will.

3. **Übersetzungsqualität es/fr/it/pt/ru jenseits des Sinngehalts.** Ich habe auf
   Vollständigkeit, Platzhalter und logischen Widerspruch geprüft. Ob die Sätze
   für einen Muttersprachler natürlich klingen, kann ich nicht beurteilen. Der
   russische Befund unter „KLEIN" ist ein Terminologie-Hinweis, keine
   muttersprachliche Bewertung.

4. **Ob die 4 fehlenden „bei diesem Spiel" in es/fr/it/pt Absicht waren.** Möglich,
   dass die Kürzung bewusst erfolgte, weil der Satz nur im passenden Kontext
   angezeigt wird. Ich halte es trotzdem für einen Fund, weil derselbe Nutzer bei
   einem Instanzwechsel die gegenteilige Aussage zu lesen bekommt.

5. **Der Anrede- und der „Ausrollen"-Punkt** sind Geschmacksfragen, keine Fehler.
   Ich melde sie, weil Marc auf durchgängige Sprache Wert legt — die Entscheidung
   liegt bei ihm.

6. **Nicht geprüft:** ob die Testsuite grün ist. Der Auftrag war die
   Sprachprüfung; `tests/test_reihenfolge_anzeige.py` habe ich nur gelesen, nicht
   ausgeführt.
