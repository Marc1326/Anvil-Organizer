# Punkt 1: Anvil soll sagen, wann die Reihenfolge NICHT ankommt

Stand: 13.08.2026
Grundlage: `docs/anvil-plan-reihenfolge-ehrlich.md` (Empfehlung „Weg 1 —
ehrlich sein")
Umfang: **reine Anzeige.** Kein Eingriff in den Deploy-Weg, keine
Nummerierung für weitere Spiele, kein BG3-Code.

---

## 1. Was weiß Anvil schon?

### 1.1 Die vier Plugin-Schalter

Definiert in der Basisklasse, jeweils mit Doku-String:

| Schalter | Datei:Zeile | Standard |
|---|---|---|
| `GamePakLoadOrderPrefix` | `anvil/plugins/base_game.py:149` | `False` |
| `GamePakLoadOrderDirs` | `anvil/plugins/base_game.py:151` | `[]` |
| `GamePakLoadOrderExtensions` | `anvil/plugins/base_game.py:159` | `[]` |
| `GamePakLoadOrderFirstWins` | `anvil/plugins/base_game.py:165` | `False` |

Die Warnung, die Punkt 3 aus dem Vorgängerplan blockiert, steht als
Kommentar direkt darüber: `anvil/plugins/base_game.py:143-148`
(„viele Mod-Autoren verbieten das Umbenennen ausdruecklich").

### 1.2 Wer setzt sie? (alle Spiel-Plugins durchsucht)

Gegrept über `anvil/plugins/games/*.py`. Treffer:

| Spiel | Datei:Zeile | Wert |
|---|---|---|
| Cyberpunk 2077 | `game_cyberpunk2077.py:78` | `GamePakLoadOrderDirs = ["archive/pc/mod"]` |
| Cyberpunk 2077 | `game_cyberpunk2077.py:79` | `GamePakLoadOrderExtensions = [".archive"]` |
| Cyberpunk 2077 | `game_cyberpunk2077.py:82` | `GamePakLoadOrderFirstWins = True` |
| Stalker 2 | `game_stalker2.py:55` | `GamePakLoadOrderPrefix = False` |
| Stalker 2 | `game_stalker2.py:61` | `GamePakLoadOrderDirs = ["Stalker2/Content/Paks/~mods"]` |
| Stellar Blade | `game_stellarblade.py:59` | `GamePakLoadOrderPrefix = False` (ausdrücklich aus) |

**Kein einziges Plugin setzt `GamePakLoadOrderPrefix = True`.** Skyrim SE,
Fallout 4, Starfield, Witcher 3, RDR 2, Ghost Recon Breakpoint und
Baldur's Gate 3 setzen keinen der vier Schalter — sie erben die
Standardwerte aus `base_game.py`.

### 1.3 Wann nummeriert der Deployer wirklich?

`anvil/core/mod_deployer.py:786`:

```python
if self._pak_load_order_prefix or self._pak_load_order_dirs:
    if pak_order_allows(rel, self._pak_load_order_dirs):
```

Also: **Nummerierung ist an, wenn `Prefix` True ODER `Dirs` nicht leer
ist.** Dieselbe Bedingung noch einmal beim Aufräumen doppelter Dateien:
`anvil/core/mod_deployer.py:1033`.

Damit gilt heute:

| Spiel | Nummerierung aktiv | Freigegebene Ordner |
|---|---|---|
| Cyberpunk 2077 | ja (über `Dirs`) | `archive/pc/mod` |
| Stalker 2 | ja (über `Dirs`) | `Stalker2/Content/Paks/~mods` |
| alle übrigen | nein | — |

### 1.4 Gibt es schon eine Funktion „wird hier nummeriert?"

**Nein.** Gesucht wurde nach `pak_order_allows`, `load_order_index`,
`nummerier`, `zaehler`, `Ladereihenfolge`, `load_order` über `anvil/**/*.py`.
Vorhanden sind nur die drei Helfer im Deployer:

| Funktion | Datei:Zeile | Was sie beantwortet |
|---|---|---|
| `pak_load_order_name(rel, index, extensions, breite)` | `anvil/core/mod_deployer.py:201` | Wie heißt die **Datei** mit Zähler? |
| `load_order_index(load_index, gesamt, first_wins)` | `anvil/core/mod_deployer.py:227` | Welche **Zahl** bekommt eine Mod? |
| `pak_order_allows(rel, dirs)` | `anvil/core/mod_deployer.py:240` | Darf **dieser Zielpfad** umbenannt werden? |

`pak_order_allows` arbeitet auf einem **fertig gerouteten Zielpfad**, nicht
auf einem Plugin. Für die Anzeige braucht es die Frage eine Ebene höher:
„Was gilt für dieses **Spiel**?". Die Funktion muss **neu gebaut** werden.

Nebenbefund: `_PAK_ORDER_EXTENSIONS = _PAK_EXTENSIONS | {".sig"}` mit
`_PAK_EXTENSIONS = {".pak", ".utoc", ".ucas"}` — `anvil/core/mod_deployer.py:65-69`.
Das ist der Standardsatz, wenn ein Plugin keine eigenen Endungen nennt
(`anvil/core/mod_deployer.py:221`).

### 1.5 Wie kommt das Plugin zur Mod-Liste?

Der Weg ist heute schon vollständig da, es fehlt nur der letzte Schritt:

| Schritt | Datei:Zeile |
|---|---|
| Plugin wird geladen | `anvil/mainwindow.py:1826` (`plugin_loader.get_game(short_name)`) |
| Plugin gemerkt | `anvil/mainwindow.py:1827` (`self._current_plugin = plugin`) |
| Zeilen gebaut | `anvil/mainwindow.py:2043` (`mod_entry_to_row(...)`) |
| Modell befüllt | `anvil/mainwindow.py:2044` (`self._mod_list_view.source_model().set_mods(mod_rows)`) |
| Modell kennt schon fremde Manager | `anvil/mainwindow.py:1944` (`set_category_manager`) — genau dasselbe Muster |

Das Modell selbst hat **keinen** Zugriff auf das Plugin: `ModListModel.__init__`
(`anvil/models/mod_list_model.py:131-155`) kennt nur Zeilen, Manager und
Einstellungs-Merker. Es gibt aber bereits Setter im gleichen Stil
(`set_category_manager` — `anvil/models/mod_list_model.py:157`).

Die Panel-Seite liest die Schalter schon fürs Ausrollen:
`anvil/widgets/game_panel.py:3255-3262`, weitergereicht in
`anvil/widgets/game_panel.py:3284-3287`.

### 1.6 Der Spaltenkopf „Priorität"

- Spaltenkonstanten: `anvil/models/mod_list_model.py:42`
  (`COL_CHECK, COL_NAME, COL_CONFLICTS, COL_MARKERS, COL_CATEGORY, COL_VERSION, COL_PRIORITY = range(7)`)
- Kopftexte zur Laufzeit: `anvil/models/mod_list_model.py:773-791`,
  Schlüssel `label.header_priority` (`anvil/locales/de.json:364` = „Priorität")

**Können Spaltenköpfe dort Tooltips?** Heute **nein**:

```python
def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
    if orientation != Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
        return None
```
(`anvil/models/mod_list_model.py:773-775`)

Jede Anfrage mit `ToolTipRole` wird abgewiesen. Die Zeile muss erweitert
werden, dann funktioniert es: Der View hängt über eine Proxy am Modell
(`anvil/widgets/mod_list.py:1295-1298`), und `ModListProxyModel`
(`anvil/widgets/mod_list.py:589`) überschreibt `headerData` **nicht** —
`QSortFilterProxyModel` reicht die Anfrage unverändert an das Quellmodell
durch. Der Kopf ist sichtbar, nur das Klicken ist abgeschaltet
(`anvil/widgets/mod_list.py:1299-1300`).

Zeilen-Tooltips gibt es bereits als Vorbild: `anvil/models/mod_list_model.py:371-399`
(Konflikte, `tooltip.direct_install`, `foreign.tooltip`, `tooltip.stray_preset`).

### 1.7 Woran erkennt man ein Bethesda-Spiel?

Drei Kandidaten geprüft:

| Kandidat | Befund | taugt? |
|---|---|---|
| `GameDataPath == "Data"` | `anvil/plugins/base_game.py:62`, Wert wird auch für Routing benutzt (`anvil/core/mod_deployer.py:763-783`) | nein — reine Pfadangabe |
| `PRIMARY_PLUGINS` | `anvil/plugins/base_game.py:226`, gesetzt in `game_fallout4.py:73`, `game_skyrimse.py:86`, `game_starfield.py:78` | ginge, ist aber eine Datenliste |
| `has_plugins_txt()` | `anvil/plugins/base_game.py:571-573`: `return self.PluginLoadOrderFormat == "asterisk"` | **ja** |

`PluginLoadOrderFormat = "asterisk"` setzen genau drei Plugins:
`game_fallout4.py:82`, `game_skyrimse.py:93`, `game_starfield.py:90`.
`has_plugins_txt()` wird schon an mehreren Stellen als Bethesda-Weiche
benutzt, z. B. `anvil/widgets/game_panel.py:3308` und
`anvil/mainwindow.py:1931-1933`.

**Ein `GamePluginsFile`-Attribut existiert nicht** — gesucht über
`anvil/plugins/**/*.py`, kein Treffer. Es gibt nur die Methode
`plugins_txt_path()` (`anvil/plugins/base_game.py:575`).

### 1.8 Was Anvil dem Nutzer heute über all das sagt

Nichts in der Mod-Liste. Der einzige verwandte Text steht im
Konflikte-Bereich des Detail-Dialogs:

`anvil/locales/de.json:989` —
> „Bei gepackten Archiven zeigt Anvil nur die Anzahl gemeinsamer
> Spieldateien — die Dateinamen stehen nicht im Archiv, nur Prüfsummen.
> **Grün = dieses Archiv gewinnt.**"

Der letzte Halbsatz ist bei Spielen ohne Nummerierung **nicht belegt**:
Der Gewinner kommt allein aus der Listenposition
(`anvil/core/conflict_scanner.py:266`, `"winner": b[0]`, Kommentar Zeile
264-265) und wird eingefärbt in `anvil/dialogs/mod_detail_dialog.py:1501-1503`.
Bei Skyrim, Stellar Blade & Co. entscheidet über gepackte Archive nicht
die Position. Das ist die zweitwichtigste Stelle für den Hinweis.

---

## 2. Wo soll der Hinweis hin?

### a) Tooltip auf dem Spaltenkopf „Priorität"

| Kriterium | Bewertung |
|---|---|
| Wird es gesehen? | Ja, genau dann, wenn jemand die Spalte anschaut und sich fragt, was sie bewirkt. Nicht aufdringlich. |
| Nervt es? | Nein. Tooltips erscheinen nur auf Verlangen. |
| Codeaufwand | Klein: `headerData` um `ToolTipRole` erweitern (`anvil/models/mod_list_model.py:773`), ein Setter am Modell, ein Aufruf in `mainwindow.py`. |
| Haken | Ein Erstnutzer mit falscher Erwartung fährt gar nicht erst mit der Maus dorthin. |

### b) Zeile unter der Mod-Liste

| Kriterium | Bewertung |
|---|---|
| Wird es gesehen? | Ja, sofort und ohne Suchen. Der einzige Ort, der die falsche Erwartung von sich aus korrigiert. |
| Nervt es? | Ja, wenn sie dauerhaft steht. Muss also (1) nur erscheinen, wenn es etwas zu sagen gibt, und (2) wegklickbar sein und weggeklickt bleiben. |
| Codeaufwand | Klein bis mittel: ein `QLabel` im Wrapper unter `self._mod_list_stack` (`anvil/mainwindow.py:297-302`), plus QSS-Eintrag. |
| Haken | Braucht Platz. Die Mod-Liste hängt bereits in einem Splitter mit Presets und Frameworks (`anvil/widgets/mod_list.py:1444-1451`) — die Zeile gehört **außerhalb** des Splitters, sonst wird sie beim Ziehen zerquetscht. |

### c) Konflikte-Bereich des Mod-Detail-Dialogs

| Kriterium | Bewertung |
|---|---|
| Wird es gesehen? | Ja, im richtigen Moment: Wer dort steht, will wissen, wer gewinnt. |
| Nervt es? | Nein, der Bereich ist ohnehin voller Erklärtext (`anvil/dialogs/mod_detail_dialog.py:1512-1515`). |
| Codeaufwand | Sehr klein: der Hinweis-Label existiert bereits, es kommt ein zweiter Satz dazu. |
| Haken | Nur erreichbar über Doppelklick auf eine Mod (`anvil/mainwindow.py:289`) — erreicht niemanden, der die Liste bloß sortiert. **Aber:** hier steht heute eine unbelegte Behauptung („Grün = dieses Archiv gewinnt", `anvil/locales/de.json:989`). Das ist kein Zusatz, das ist eine Korrektur. |

### d) Diagnose-Bereich

| Kriterium | Bewertung |
|---|---|
| Wird es gesehen? | Nein. Der Bereich sitzt **im Einstellungen-Dialog** (`anvil/widgets/settings_dialog.py:1020`), nicht im Hauptfenster. Dorthin geht nur, wer schon weiß, dass etwas kaputt ist. |
| Nervt es? | Nein, hilft aber auch keinem Anwender direkt. |
| Codeaufwand | Klein, aber nicht null: `build_report` (`anvil/core/diagnostics.py:276-278`) bekommt heute nur `dict`s und kennt **kein** Plugin. Es braucht einen zusätzlichen optionalen Parameter, den `SettingsDialog._diag_build_report` (`anvil/widgets/settings_dialog.py:1531-1537`) füllt. Das Plugin ist dort beschaffbar: der Dialog hält `_plugin_loader` und `_instance_manager` (`settings_dialog.py:84-85`). |
| Nutzen | Für **Fehlerberichte**: Wenn jemand schreibt „Mod wirkt nicht trotz Platz 1", steht die Antwort im Export. |

### EMPFEHLUNG: a + b + c, d als Beigabe im Bericht

- **a) Tooltip** ist die dauerhafte, nie störende Auskunft. Pflicht.
- **b) Zeile** fängt die falsche Erwartung tatsächlich ab. Pflicht — aber
  **nur** bei Spielen, bei denen die Reihenfolge nicht ankommt, und
  **wegklickbar pro Spiel**.
- **c) Konflikte-Bereich**: der Satz „Grün = dieses Archiv gewinnt" muss
  bei nicht nummerierenden Spielen anders lauten. Korrektur einer
  falschen Aussage, kein Feature. Pflicht.
- **d) Diagnose**: eine Zeile im Bericht, damit Marc bei Rückfragen nicht
  raten muss. Billig, also mitnehmen.

Alle vier lesen **dieselbe** neue Funktion. Der Code wird an genau einer
Stelle gepflegt.

---

## 3. Was genau soll dastehen?

### 3.1 Die drei Fälle, wie sie sich aus dem Code ergeben

Einstufung ausschließlich aus dem Plugin (belegt in Abschnitt 1.3):

| Fall | Bedingung | heute betroffen |
|---|---|---|
| **VOLL** | `GamePakLoadOrderPrefix == True` **und** `GamePakLoadOrderDirs` leer | kein Spiel |
| **TEILWEISE** | `GamePakLoadOrderDirs` nicht leer | Cyberpunk 2077, Stalker 2 |
| **KEINE** | weder `Prefix` noch `Dirs` | alle übrigen |

**Wichtig — bewusste Entscheidung:** Der Vorgängerbericht stuft Cyberpunk
als „vollständig" ein. Aus dem Plugin allein lässt sich das **nicht**
belegen: Cyberpunk gibt genau einen Ordner frei (`game_cyberpunk2077.py:78`),
und REDmod-Archive unter `mods/<name>/archives/` bleiben laut Kommentar
`game_cyberpunk2077.py:76-77` ausdrücklich unberührt. Der Text nennt
deshalb **immer die Ordner beim Namen**, statt „vollständig" zu behaupten.
Das ist ehrlicher und bleibt richtig, wenn später ein Ordner dazukommt.

Zusätzlich verfügbar für den Resttext: `GameModDirs` — die Mod-Ordner des
Spiels (`anvil/plugins/base_game.py:131`). Gesetzt bei Cyberpunk
(`game_cyberpunk2077.py:149-156`, 6 Ordner), Stalker 2
(`game_stalker2.py:66-70`, 3 Ordner), Stellar Blade
(`game_stellarblade.py:34-38`), Skyrim SE (`game_skyrimse.py:50-52`),
Fallout 4 (`game_fallout4.py:49-51`), Starfield (`game_starfield.py:51-53`),
Witcher 3 (`game_witcher3.py:48-50`), RDR 2 (`game_rdr2.py:43-45`).
Die Differenz „Mod-Ordner minus freigegebene Ordner" ergibt die Liste,
für die die Reihenfolge **nicht** bei gepackten Dateien greift.

### 3.2 Textvorschläge (deutsch, verbindlich)

**Fall VOLL** — `order_scope.numbered_all`
> Deine Reihenfolge kommt im Spiel an: Anvil nummeriert die Mod-Dateien
> beim Ausrollen durch. Oben in der Liste heißt: gewinnt im Spiel.

**Fall TEILWEISE** — `order_scope.numbered_dirs`
> Deine Reihenfolge kommt in diesen Ordnern an: {dirs}. Anvil nummeriert
> die Dateien dort beim Ausrollen durch.

Dazu, wenn es weitere Mod-Ordner gibt — `order_scope.numbered_rest`
> Außerhalb davon ({rest}) gilt die Reihenfolge nur für lose Dateien.
> Gepackte Archive lädt das Spiel dort nach eigenem Verfahren.

Beispiel Cyberpunk 2077:
> Deine Reihenfolge kommt in diesen Ordnern an: archive/pc/mod. Anvil
> nummeriert die Dateien dort beim Ausrollen durch.
> Außerhalb davon (mods, bin/x64/plugins/cyber_engine_tweaks/mods,
> red4ext/plugins, r6/scripts, r6/tweaks) gilt die Reihenfolge nur für
> lose Dateien. Gepackte Archive lädt das Spiel dort nach eigenem
> Verfahren.

Beispiel Stalker 2:
> Deine Reihenfolge kommt in diesen Ordnern an:
> Stalker2/Content/Paks/~mods. Anvil nummeriert die Dateien dort beim
> Ausrollen durch.
> Außerhalb davon (Stalker2/Content/Paks/LogicMods,
> Stalker2/Binaries/Win64/plugins) gilt die Reihenfolge nur für lose
> Dateien. Gepackte Archive lädt das Spiel dort nach eigenem Verfahren.

**Fall KEINE** — `order_scope.not_numbered`
> Bei diesem Spiel entscheidet die Reihenfolge nur über lose Dateien.
> Gepackte Archive lädt das Spiel nach eigenem Verfahren — eine Mod kann
> also trotz Platz 1 verlieren.

**Bethesda-Zusatz** (immer zusätzlich, wenn `has_plugins_txt()` True) —
`order_scope.bethesda_plugins`
> Für Plugins (.esp/.esm/.esl) gilt diese Liste nicht: deren Reihenfolge
> steht im Plugins-Bereich und wird getrennt gespeichert.

**Kurzfassung für den Spaltenkopf-Tooltip** — `order_scope.tooltip_head`
> Oben = höchste Priorität. Was das im Spiel bewirkt:

Der Tooltip ist also: Kopfzeile + Falltext (+ Resttext) (+ Bethesda-Zusatz),
mit Zeilenumbrüchen verbunden.

**Zeile unter der Liste** (nur Fall KEINE, plus Bethesda-Zusatz): der
Falltext einzeilig, gefolgt von einem „×"-Knopf zum Wegklicken.

**Konflikte-Bereich, Ersatz für den Halbsatz** — `mod_detail.archive_winner_unsure`
> Wer bei gepackten Archiven gewinnt, entscheidet bei diesem Spiel nicht
> die Reihenfolge in Anvil, sondern das Spiel selbst.

Bei Spielen mit Nummerierung bleibt der heutige Satz
(`anvil/locales/de.json:989`) unverändert stehen.

---

## 4. Spec

### 4.1 Betroffene Dateien

| Datei | Änderung |
|---|---|
| `anvil/core/load_order_scope.py` | **NEU.** Dataclass `LoadOrderScope` + `describe_load_order(plugin) -> LoadOrderScope` + `scope_text(scope) -> str` und `scope_tooltip(scope) -> str`. Kein Qt-Import außer `tr`. |
| `anvil/models/mod_list_model.py:773-791` | `headerData` nimmt `ToolTipRole` an und liefert für `COL_PRIORITY` den Tooltip. Neu: `set_order_scope_tooltip(text)` (Muster wie `set_category_manager`, Zeile 157) + `headerDataChanged.emit(...)`. |
| `anvil/mainwindow.py` (~1827 / ~2044) | Nach dem Setzen von `self._current_plugin` einmal `describe_load_order(plugin)` rufen; Ergebnis an Modell (Tooltip) und an die Hinweiszeile geben. Beim Instanz-Reset (`mainwindow.py:1789-1810`) leeren. |
| `anvil/mainwindow.py:297-302` | Hinweiszeile (`QLabel` + „×") in `mod_list_layout` **unter** `self._mod_list_stack`. Bewusst hier und nicht in `ModListView`, damit **kein BG3-Code angefasst wird** und die Zeile trotzdem für beide Listen im `QStackedWidget` gilt. |
| `anvil/dialogs/mod_detail_dialog.py:1512-1515` | Hinweistext fallabhängig: bei Fall KEINE zusätzlich `mod_detail.archive_winner_unsure`. `game_plugin` liegt der Funktion bereits vor (`mod_detail_dialog.py:1341`). |
| `anvil/core/diagnostics.py:276-278` | `build_report` bekommt einen optionalen Parameter (z. B. `load_order: str \| None = None`) und schreibt daraus einen Block „[Ladereihenfolge]". |
| `anvil/widgets/settings_dialog.py:1531-1537` | `_diag_build_report` füllt den neuen Parameter mit `scope_text(describe_load_order(plugin))`; Plugin über `self._plugin_loader` / `self._instance_manager` (`settings_dialog.py:84-85`). |
| `anvil/styles/modern/anvil-modern.qss` | `#orderScopeHint` (Muster: `#welcomeHint`, Zeile 580-583). **Kein `setStyleSheet()` im Widget.** |
| `anvil/locales/{de,en,es,fr,it,pt,ru}.json` | **7 Dateien** — nachgezählt über `anvil/locales/*.json`. |
| `tests/test_load_order_scope.py` | **NEU** (siehe 4.5). |

**Nicht angefasst:** `anvil/core/mod_deployer.py`, alle Plugins in
`anvil/plugins/games/`, `anvil/models/bg3_mod_list_model.py`,
`anvil/widgets/bg3_mod_list.py`, alles rund um „Dateinamen nicht ändern
pro Mod" (Punkt 2, andere Baustelle).

### 4.2 Die neue Funktion

```
LoadOrderScope:
    kind: "all" | "dirs" | "none"
    dirs: list[str]          # aus GamePakLoadOrderDirs
    rest_dirs: list[str]     # GameModDirs minus dirs (normalisiert)
    bethesda: bool           # plugin.has_plugins_txt()
```

Regeln, 1:1 aus `anvil/core/mod_deployer.py:786`:

- `plugin is None` → `kind="none"`, alles leer, `bethesda=False`
- `GamePakLoadOrderDirs` nicht leer → `kind="dirs"`
- sonst `GamePakLoadOrderPrefix` True → `kind="all"`
- sonst → `kind="none"`

`rest_dirs`: jeder Eintrag aus `GameModDirs`, der **nicht** unter einem
Eintrag aus `dirs` liegt. Vergleich mit derselben Normalisierung wie
`pak_order_allows` (`anvil/core/mod_deployer.py:249-253`): Backslash zu
Schrägstrich, führende/schließende Schrägstriche weg, `lower()`. Für die
Anzeige wird die **Originalschreibweise** aus `GameModDirs` ausgegeben.

`bethesda` über `plugin.has_plugins_txt()` (`anvil/plugins/base_game.py:571`),
abgesichert mit `getattr(plugin, "has_plugins_txt", None)` und
`callable()` — Plugins ohne die Methode dürfen nicht abstürzen.

### 4.3 Signal-Flow

```
Instanz wird geladen
  mainwindow._apply_instance()
    plugin = self.plugin_loader.get_game(short_name)     # mainwindow.py:1826
    self._current_plugin = plugin                        # mainwindow.py:1827
        |
        v
    scope = describe_load_order(plugin)                  # NEU, core/load_order_scope.py
        |
        +--> self._mod_list_view.source_model()
        |        .set_order_scope_tooltip(scope_tooltip(scope))
        |            -> ModListModel speichert den Text
        |            -> headerDataChanged.emit(Horizontal, COL_PRIORITY, COL_PRIORITY)
        |            -> QSortFilterProxyModel reicht durch (mod_list.py:589, kein Override)
        |            -> QHeaderView fragt headerData(COL_PRIORITY, Horizontal, ToolTipRole)
        |            -> Tooltip erscheint beim Verweilen auf „PRIORITÄT"
        |
        +--> self._update_order_hint(scope)
        |        kind == "none"  -> Zeile sichtbar, Text = scope_text(scope)
        |        kind != "none"  -> Zeile unsichtbar
        |        bereits weggeklickt (QSettings "ModList/order_hint_dismissed/<GameShortName>")
        |                        -> Zeile unsichtbar
        |
        +--> Diagnose: settings_dialog._diag_build_report() ruft
                 describe_load_order() erneut (zustandslos, kein Signal nötig)

Mod-Detail-Dialog (Doppelklick, mainwindow.py:289)
  _build_conflicts_tab(mod_name, all_mods, game_plugin, ...)   # mod_detail_dialog.py:1340
    scope = describe_load_order(game_plugin)
    kind == "none" und archiv_treffer vorhanden
        -> zusätzlicher Satz unter dem bestehenden Hinweis (Zeile 1512)

Wegklicken
  „×" geklickt -> QSettings setzen -> Zeile ausblenden
  (Tooltip bleibt in jedem Fall erhalten)
```

Kein neues Qt-Signal nötig. `headerDataChanged` ist ein Standardsignal von
`QAbstractItemModel` und muss ausgelöst werden, sonst zeigt der Kopf beim
Instanzwechsel den alten Tooltip.

### 4.4 Neue tr()-Schlüssel

Alle unter einem neuen Block `order_scope`, plus einer im bestehenden
`mod_detail`-Block:

| Schlüssel | Platzhalter |
|---|---|
| `order_scope.tooltip_head` | — |
| `order_scope.numbered_all` | — |
| `order_scope.numbered_dirs` | `{dirs}` |
| `order_scope.numbered_rest` | `{rest}` |
| `order_scope.not_numbered` | — |
| `order_scope.bethesda_plugins` | — |
| `order_scope.dismiss` | — (Tooltip des „×", z. B. „Hinweis ausblenden") |
| `mod_detail.archive_winner_unsure` | — |

**8 neue Schlüssel × 7 Locale-Dateien = 56 Einträge.** Die sieben Dateien
sind nachgezählt: `anvil/locales/de.json`, `en.json`, `es.json`, `fr.json`,
`it.json`, `pt.json`, `ru.json`.

Der bestehende Test `tests/test_translations.py:8` führt genau diese
sieben Sprachen als `LANGUAGES` — er prüft aber nur, dass **vorhandene**
Zeichenketten auflösbar sind, **nicht**, dass ein Schlüssel in allen
Sprachen existiert. Dafür braucht es einen neuen Test (4.5).

Achtung Formatierung: `Translator.t()` formatiert mit `**kwargs`
(`anvil/core/translator.py:69-78`). `{dirs}` und `{rest}` müssen in **allen
sieben** Sprachen identisch heißen, sonst wirft `.format()`.

### 4.5 Tests

**Bestehende Tests, die den Bereich abdecken** (alle vorhanden, geprüft):

| Datei | Was sie sichert |
|---|---|
| `tests/test_archiv_ladereihenfolge.py:93-111` | Cyberpunk an, Unreal-Spiele aus, Bethesda ohne Zähler |
| `tests/test_archive_load_order_wiring.py:129-152` | Stalker-2-Ordnergrenze, Stellar Blade bewusst aus |
| `tests/test_pak_load_order_dirs.py:48-56, 73-74, 147-152, 182-183` | `pak_order_allows`, Standardwerte der Basisklasse |
| `tests/test_pak_load_order.py:121-128` | `GamePakLoadOrderPrefix`-Standard |
| `tests/test_archiv_drop.py:89-98` | einziges Beispiel, wie `ModListModel` im Test instanziiert wird (`QApplication.instance() or QApplication([])`) |
| `tests/test_translations.py` | die sieben Sprachen |

**Für die Mod-Liste selbst gibt es keine eigene Testdatei** — gesucht über
`tests/*mod_list*.py` und `tests/*header*.py`, kein Treffer; Treffer auf
`ModListModel` nur in `tests/test_foreign_mods.py` und
`tests/test_archiv_drop.py`.

**Neu: `tests/test_load_order_scope.py`**

1. `test_cyberpunk_nennt_seinen_archivordner` — `kind == "dirs"`,
   `dirs == ["archive/pc/mod"]`
2. `test_stalker2_nennt_nur_mods` — `dirs == ["Stalker2/Content/Paks/~mods"]`,
   `"LogicMods"` steht in `rest_dirs`
3. `test_skyrim_ist_ohne_nummerierung` — `kind == "none"`
4. `test_skyrim_ist_bethesda` — `bethesda is True`; Gegenprobe Cyberpunk
   `bethesda is False`
5. `test_ohne_plugin_kein_absturz` — `describe_load_order(None)` liefert
   `kind == "none"`
6. `test_text_nennt_die_ordner` — `scope_text` für Stalker 2 enthält
   `~mods` **und** `LogicMods`
7. `test_bethesda_satz_haengt_dran` — `scope_text` für Skyrim enthält den
   Plugins-Satz, für Cyberpunk nicht
8. `test_spaltenkopf_liefert_tooltip` — `ModListModel`, `set_order_scope_tooltip("X")`,
   dann `headerData(COL_PRIORITY, Horizontal, ToolTipRole) == "X"`
9. `test_andere_spalten_ohne_tooltip` — `headerData(COL_NAME, ..., ToolTipRole) is None`
10. `test_kopftexte_unveraendert` — `headerData(COL_PRIORITY, ..., DisplayRole)`
    liefert weiter `tr("label.header_priority")` (bzw. VERSALIEN im
    modernen Theme, `mod_list_model.py:788-789`)
11. `test_alle_neuen_schluessel_in_sieben_sprachen` — für jede der
    7 Dateien alle 8 Schlüssel vorhanden und nicht leer
12. `test_platzhalter_gleich_in_allen_sprachen` — `{dirs}`/`{rest}`
    kommen in jeder Sprache genau so vor

**Mutationsproben** (Änderung → welcher Test wird rot):

| # | Mutation | rot wird |
|---|---|---|
| 1 | In `describe_load_order` `GamePakLoadOrderDirs` ignorieren (immer `[]`) | 1, 2, 6 |
| 2 | `kind="dirs"` und `kind="all"` vertauschen | 1, 2 |
| 3 | Bedingung von `or` auf `and` ändern (wie `mod_deployer.py:786` **nicht** ist) | 1, 2 |
| 4 | `has_plugins_txt()` durch `GameDataPath == "Data"` ersetzen | 4 (Gegenprobe Cyberpunk), 7 |
| 5 | `None`-Prüfung entfernen | 5 (`AttributeError`) |
| 6 | `rest_dirs` = `GameModDirs` ohne Abzug | 2 (`~mods` stünde dann auch im Rest) |
| 7 | Normalisierung in `rest_dirs` weglassen (Groß/Klein) | 2 |
| 8 | `headerData` wieder auf `role != DisplayRole: return None` zurücksetzen | 8 |
| 9 | Tooltip auch für `COL_NAME` liefern | 9 |
| 10 | `headerData` liefert bei `ToolTipRole` den Kopftext statt des Tooltips | 8 |
| 11 | Beim Erweitern von `headerData` den `DisplayRole`-Zweig zerschießen | 10 (und praktisch die halbe GUI) |
| 12 | Einen der 8 Schlüssel in `ru.json` weglassen | 11 |
| 13 | In `fr.json` `{dirs}` als `{dossiers}` schreiben | 12 |
| 14 | Im Detail-Dialog den Zusatzsatz unabhängig vom Fall anzeigen | Handprobe, Kriterium 11 — kein automatischer Test (GUI-Dialog) |

### 4.6 Bekannte Fallen für die Umsetzung

- `QPushButton.clicked` liefert `bool` → `lambda checked=False: ...`
  (das „×" der Hinweiszeile).
- Neu ins Layout gehängte Widgets sind nicht automatisch sichtbar →
  `show()` bzw. `setVisible(True)` beim Einblenden.
- Kein `setStyleSheet()` im neuen Widget — QSS-Objektname vergeben
  (`#orderScopeHint`), Vorbild `#welcomeHint`
  (`anvil/styles/modern/anvil-modern.qss:580`).
- Die Hinweiszeile gehört **nicht** in den Splitter von `ModListView`
  (`anvil/widgets/mod_list.py:1444-1451`), sonst konkurriert sie mit
  Presets/Frameworks um Höhe.
- `headerDataChanged` nach jedem Instanzwechsel auslösen, sonst bleibt
  der Tooltip des vorigen Spiels stehen.
- `rest_dirs` kann lang werden (Cyberpunk: 5 Einträge). Im Tooltip ist das
  in Ordnung; die einzeilige Hinweiszeile erscheint nur im Fall KEINE, und
  dort ist `rest_dirs` unerheblich.

---

## 5. Verwandte Funktionen (geprüft)

| Funktion | Datei:Zeile | gleicher Hinweis nötig? |
|---|---|---|
| Konflikt-Badges in der Liste | `anvil/models/mod_list_model.py:322-343, 371-390` | **nein** — sie zeigen lose Dateikonflikte, und dort stimmt die Reihenfolge bei jedem Spiel |
| Archiv-Konflikte im Detail-Dialog | `anvil/dialogs/mod_detail_dialog.py:1469-1515`, `anvil/core/conflict_scanner.py:218-269` | **ja** — behauptet heute einen Gewinner allein aus der Position (`conflict_scanner.py:266`) |
| `_write_archive_load_order` (modlist.txt) | `anvil/core/mod_deployer.py:970` | **nein** — schreibt eine Datei, zeigt nichts an. Der Kommentar `game_cyberpunk2077.py:68-71` sagt bereits, dass sie nichts entscheidet |
| Plugins-Bereich (Bethesda) | `anvil/mainwindow.py:8929-8980`, `anvil/core/plugins_txt_writer.py` | **nein** — eigene Liste mit eigener Reihenfolge; der Hinweis geht in die **Mod**-Liste, nicht dorthin |
| BG3-Mod-Liste | `anvil/models/bg3_mod_list_model.py:220` | **nein** — Projektregel: BG3-Code nicht anfassen. Die Hinweiszeile sitzt außerhalb des `QStackedWidget` und gilt trotzdem |
| Fremde Mods („is_foreign") | `anvil/models/mod_list_model.py:393`, `anvil/locales/de.json:1435` | **nein** — eigener Tooltip, andere Aussage |
| Trenner mit eigenem Deploy-Pfad | `anvil/models/mod_list_model.py:398-399` | **offen, siehe UNSICHER Nr. 4** |

---

## 6. ✅ Akzeptanz-Kriterien

- [ ] **1.** Wenn eine Skyrim-SE-Instanz geladen ist und der Nutzer mit der
  Maus auf dem Spaltenkopf „PRIORITÄT" verweilt, erscheint ein Tooltip,
  der den Satz „nur über lose Dateien" enthält.
- [ ] **2.** Wenn eine Cyberpunk-2077-Instanz geladen ist und der Nutzer auf
  dem Spaltenkopf „PRIORITÄT" verweilt, nennt der Tooltip den Ordner
  `archive/pc/mod`.
- [ ] **3.** Wenn eine Stalker-2-Instanz geladen ist, nennt der Tooltip
  `Stalker2/Content/Paks/~mods` als freigegeben **und**
  `Stalker2/Content/Paks/LogicMods` als nicht freigegeben.
- [ ] **4.** Wenn eine Skyrim-SE-, Fallout-4- oder Starfield-Instanz geladen
  ist, enthält der Tooltip zusätzlich den Satz über die getrennte
  Plugin-Reihenfolge; bei Cyberpunk 2077 und Stalker 2 fehlt dieser Satz.
- [ ] **5.** Wenn der Nutzer von einer Skyrim-Instanz auf eine
  Cyberpunk-Instanz umschaltet, zeigt der Tooltip beim nächsten Verweilen
  den Cyberpunk-Text — nicht mehr den Skyrim-Text.
- [ ] **6.** Wenn eine Instanz ohne Nummerierung (z. B. Stellar Blade)
  geladen ist, erscheint unter der Mod-Liste eine sichtbare Hinweiszeile
  mit dem „nur lose Dateien"-Text.
- [ ] **7.** Wenn eine Cyberpunk-2077- oder Stalker-2-Instanz geladen ist,
  erscheint **keine** Hinweiszeile unter der Mod-Liste.
- [ ] **8.** Wenn der Nutzer das „×" der Hinweiszeile klickt, verschwindet
  die Zeile sofort — und bleibt nach `restart.sh` und erneutem Laden
  derselben Instanz verschwunden.
- [ ] **9.** Wenn die Zeile für ein Spiel weggeklickt wurde, erscheint sie
  bei einem **anderen** Spiel ohne Nummerierung trotzdem.
- [ ] **10.** Wenn die Hinweiszeile weggeklickt ist, liefert der
  Spaltenkopf-Tooltip weiterhin denselben Text.
- [ ] **11.** Wenn der Nutzer bei einem Spiel ohne Nummerierung eine Mod
  doppelt anklickt und der Konflikte-Bereich Archiv-Konflikte zeigt, steht
  dort der Satz, dass über gepackte Archive nicht die Anvil-Reihenfolge
  entscheidet; bei Cyberpunk 2077 steht dieser Satz nicht.
- [ ] **12.** Wenn der Nutzer im Diagnose-Bereich den Bericht exportiert,
  enthält die Textdatei einen Block zur Ladereihenfolge des aktiven Spiels.
- [ ] **13.** Wenn `describe_load_order(None)` gerufen wird (keine Instanz
  geladen), gibt es keinen Absturz und keine Hinweiszeile.
- [ ] **14.** Die Spaltenköpfe zeigen unverändert ihre bisherigen Texte;
  im modernen Theme weiterhin in VERSALIEN.
- [ ] **15.** Alle 8 neuen tr()-Schlüssel liegen in allen **7**
  Locale-Dateien (de, en, es, fr, it, pt, ru) mit nicht leerem Wert vor,
  und `{dirs}`/`{rest}` heißen überall gleich.
- [ ] **16.** `anvil/core/mod_deployer.py` und alle Dateien in
  `anvil/plugins/games/` sind unverändert (`git diff --stat` zeigt sie
  nicht).
- [ ] **17.** Kein `setStyleSheet()` im neuen Hinweis-Widget; die Optik
  kommt aus `#orderScopeHint` in der QSS.
- [ ] **18.** `tests/test_load_order_scope.py` läuft grün, und die
  Mutationsproben 1, 6, 8 und 12 aus Abschnitt 4.5 machen jeweils
  mindestens einen Test rot (nachgewiesen, nicht behauptet).
- [ ] **19.** Die bestehenden Tests `tests/test_archiv_ladereihenfolge.py`,
  `tests/test_archive_load_order_wiring.py`, `tests/test_pak_load_order_dirs.py`
  und `tests/test_translations.py` laufen unverändert grün.
- [ ] **20.** `restart.sh` startet ohne Fehler (kein Traceback, kein
  `NameError`/`ImportError`/`AttributeError` im Log).

---

## 7. Was ausdrücklich NICHT gemacht wird

- Keine Änderung am Deploy-Weg (`anvil/core/mod_deployer.py` bleibt außen vor).
- Keine Nummerierung für weitere Spiele — kein Plugin in
  `anvil/plugins/games/` wird angefasst.
- Kein BG3-Code (`anvil/models/bg3_mod_list_model.py`,
  `anvil/widgets/bg3_mod_list.py`, `anvil/plugins/games/game_baldursgate3.py`,
  `bg3_mod_handler.py`).
- Nichts rund um „Dateinamen nicht ändern pro Mod" — dort arbeitet jemand
  anderes; in dieser Analyse wurde ausschließlich gelesen.
- Keine Kopplung der Bethesda-Plugin-Reihenfolge an die Mod-Liste.

---

## 8. UNSICHER

1. **Tooltip auf dem Spaltenkopf ist nicht am laufenden Programm belegt.**
   Belegt ist nur: `headerData` weist `ToolTipRole` heute ab
   (`anvil/models/mod_list_model.py:774`) und die Proxy überschreibt
   `headerData` nicht (`anvil/widgets/mod_list.py:589` — kein `def headerData`
   in der Datei). Dass `QHeaderView` den Tooltip dann tatsächlich zeigt, ist
   Qt-Standardverhalten, aber im Projekt gibt es **kein** bestehendes
   Beispiel dafür — gesucht über `anvil/**/*.py` nach `headerData` (Treffer:
   `mod_detail_dialog.py:1083`, `mod_list_model.py:773`,
   `bg3_mod_list_model.py:220`; alle nur `DisplayRole`). **Muss beim Bauen
   als Erstes von Hand geprüft werden.** Rückfallweg, falls Qt zickt:
   `QHeaderView.setToolTip()` auf den ganzen Kopf statt pro Spalte.

2. **Cyberpunk „vollständig" vs. „nur archive/pc/mod".** Der
   Vorgängerbericht (`docs/anvil-plan-reihenfolge-ehrlich.md:78`) sagt
   „vollständig", das Plugin gibt genau einen Ordner frei
   (`game_cyberpunk2077.py:78`) und `GameModDirs` nennt sechs
   (`game_cyberpunk2077.py:149-156`). Ich habe mich für die belegbare
   Fassung entschieden (Ordner beim Namen nennen). Ob Marc lieber die
   knappe Aussage „Reihenfolge kommt an" möchte, ist eine
   Geschmacksfrage, die sich nicht aus dem Code beantworten lässt.

3. **Der Resttext für Cyberpunk könnte als Warnung missverstanden werden.**
   In `mods`, `r6/scripts`, `red4ext/plugins` usw. liegen lose Dateien —
   dort greift die Reihenfolge sehr wohl. Der Satz sagt genau das
   („gilt nur für lose Dateien"), könnte aber trotzdem beunruhigen.
   Bei Fall TEILWEISE wird deshalb **keine** Hinweiszeile gezeigt, nur
   der Tooltip.

4. **Trenner mit eigenem Deploy-Pfad.** `ModRow.deploy_path`
   (`anvil/models/mod_list_model.py:79, 398-399`) und
   `separator_deploy_paths` im Deployer
   (`anvil/core/mod_deployer.py:357, 805-807`) lenken Mods in ein anderes
   Ziel. Im Code steht die Zählervergabe **vor** der Umlenkung
   (`mod_deployer.py:786-807`: erst `pak_load_order_name`, dann
   `deploy_base`), also wird gegen den Pfad **ohne** Trennerpfad geprüft.
   Ob dadurch ein umgelenkter Trenner falsch eingestuft wird, ist
   **nicht gemessen** und nicht Teil dieses Plans — gehört als eigene
   Frage geprüft.

5. **QSettings-Schlüssel für das Wegklicken.** Vorschlag
   `ModList/order_hint_dismissed/<GameShortName>`. Eine bestehende
   Konvention für per-Spiel-Merker in QSettings habe ich nicht gefunden;
   gesehen habe ich nur einfache `ModList/`-Schlüssel wie
   `ModList/show_external_mods` (`anvil/mainwindow.py:2008`). Ob Marc den
   Merker lieber pro Instanz statt pro Spiel will, ist offen.

6. **Wie „ehrlich" der Resttext bei LogicMods sein kann.** Dass in
   `Stalker2/Content/Paks/LogicMods` gepackte `.pak` liegen, steht als
   Kommentar im Plugin (`game_stalker2.py:52-60`), ist aber im Code
   nirgends als Datum hinterlegt. Der vorgeschlagene Satz umgeht das,
   indem er beide Möglichkeiten nennt („nur lose Dateien … gepackte
   Archive nach eigenem Verfahren"). Eine feinere Aussage pro Ordner
   wäre nur mit einer neuen Plugin-Eigenschaft möglich — die will dieser
   Plan bewusst nicht einführen.
