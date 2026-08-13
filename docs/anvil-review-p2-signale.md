# Review P2 — Verkabelung (Signal/Slot, Datenfluss, Imports, Sichtbarkeit)

Geprüft: uncommittete Änderungen (`git status` / `git diff`) plus die neuen Dateien
`anvil/core/deploy_rules.py` und `anvil/core/load_order_scope.py`.
Nur gelesen, kein Code geändert.

Testlauf: `.venv/bin/python -m pytest tests -q` → **850 passed, 1 skipped** (15,96 s).
`python -m py_compile` über alle geänderten Module: fehlerfrei.

---

## KRITISCH

### K1 — `set_keep_file_name_mods` auf einem Deployer, der die Methode nicht hat (AttributeError)

- `anvil/widgets/game_panel.py:1154-1158` ruft **die Methode** auf dem laufenden Deployer:
  `self._deployer.set_keep_file_name_mods(...)`
- `anvil/widgets/game_panel.py:3244-3250` liefert für Ghost Recon Breakpoint aber **keinen**
  `ModDeployer`, sondern über `plugin.create_deployer(...)`
  (`anvil/plugins/games/game_ghostreconbreakpoint.py:64-82`) einen `GRBDeployer`.
- `anvil/core/grb_deployer.py:34-65`: `GRBDeployer` hat weder `set_keep_file_name_mods`
  noch `__getattr__`.

Belegt, nicht vermutet:

```
$ .venv/bin/python -c "from anvil.core.grb_deployer import GRBDeployer; GRBDeployer('/tmp/x','/tmp/y').set_keep_file_name_mods({'A'})"
AttributeError: 'GRBDeployer' object has no attribute 'set_keep_file_name_mods'
```

**Auswirkung:** `anvil/mainwindow.py:2090` (`_sync_keep_file_name_mods()` direkt nach
`set_instance_path`) wirft beim Wechsel auf die GRB-Instanz eine AttributeError. Der
Fehler landet im `except Exception` von `switch_instance` (`anvil/mainwindow.py:1770-1786`)
— die Instanz lädt **gar nicht mehr**, es kommt nur „Instanz konnte nicht geladen werden".
Dieselbe Zeile steht auch im Profilwechsel (`:6066`) und vor dem Spielstart (`:3760`).

Der Vorlage-Setter macht es genau deshalb anders: `set_separator_deploy_paths`
(`anvil/widgets/game_panel.py:1147-1151`) **setzt ein Feld** (`_separator_deploy_paths`),
und `GRBDeployer` hat dieses Feld eigens angelegt (`anvil/core/grb_deployer.py:65`).
Der neue Weg über einen Methodenaufruf verlässt sich auf das Protocol
`_Deployer` (`anvil/widgets/game_panel.py:102-105`) — das ist reine Typannotation und
zur Laufzeit wirkungslos.

**Auslösebedingung:** der Deployer entsteht nur, wenn ein Spielpfad existiert
(`anvil/widgets/game_panel.py:3310-3315`). Marcs GRB-Ordner
`/mnt/Gaming/SteamLibrary/steamapps/common/Ghost Recon Breakpoint` ist aktuell **nicht
vorhanden** (per `ls` geprüft), deshalb schlägt es heute bei ihm noch nicht zu — es
schlägt in dem Moment zu, in dem GRB wieder installiert ist, und bei jedem Nutzer, der
es installiert hat.

**Vorschlag:** entweder `set_keep_file_name_mods` an `GRBDeployer` ergänzen, oder im
Panel duckgetypt aufrufen:
`setter = getattr(self._deployer, "set_keep_file_name_mods", None); if callable(setter): setter(...)`.
Ein Test mit einem Deployer **ohne** die Methode fehlt — `tests/test_dateinamen_ausnahme.py:252-270`
benutzt eine Attrappe, die sie hat, und deckt den Fall daher gerade nicht ab.

### K2 — `_toggle_keep_file_names` hardcodet `.mods` und schweigt beim Scheitern

`anvil/mainwindow.py:2235`:

```python
mod_dir = self._current_instance_path / ".mods" / mod_name
if not mod_dir.is_dir():
    return
```

- Der Mod-Ordner ist pro Instanz konfigurierbar: `anvil/core/instance_paths.py:69`
  (`mods=root("path_mods_directory", ".mods")`), gemappt aus `[Paths] mods_directory`
  (`anvil/core/instance_manager.py:41`). `.mods` ist nur der **Standard**.
- Der Rest des Fensters macht es richtig: `_reload_mod_list` benutzt
  `_active_instance_paths(self).mods` (`anvil/mainwindow.py:7944`), alle anderen
  Kontextmenü-Aktionen schreiben über `entry.install_path`
  (`anvil/mainwindow.py:5319, 5383, 6804, 7676`).

**Auswirkung:** Zeigt eine Instanz auf einen eigenen Mod-Ordner (anderes Laufwerk),
ist `mod_dir` nicht vorhanden → `return` **ohne jede Meldung**. Der Nutzer klickt, das
Häkchen war gesetzt, und nichts passiert. Verstößt zusätzlich gegen die Projektregel
„NIEMALS hardcoded Pfade". (Marcs zehn Instanzen benutzen alle `%INSTANCE_DIR%/.mods`,
per `grep` über `/home/mob/.anvil-organizer/instances/*/.anvil.ini` geprüft — heute
fällt es ihm also nicht auf.)

**Zusatz — das `except OSError` ist toter Code:** `write_meta_ini` fängt den OSError
selbst ab und schreibt nur nach stderr (`anvil/core/mod_metadata.py:108-116`). Der
Block `anvil/mainwindow.py:2238-2242` kann nie greifen; stattdessen meldet
`:2247-2251` „Dateinamen bleiben unverändert", obwohl nichts geschrieben wurde.

**Vorschlag:** `_ctx_entry.install_path` mitgeben (wie bei Farbe/Deploy-Pfad) oder
`_active_instance_paths(self).mods / mod_name` verwenden, und bei `not is_dir()` eine
Warnung ins Log statt eines stillen `return`.

---

## MITTEL

### M2 — Spaltenkopf-Tooltip und Hinweiszeile überleben den Spielwechsel nicht überall

`set_load_order_plugin` und `_update_order_hint` stehen **nur** im Standard-Zweig von
`_apply_instance` (`anvil/mainwindow.py:1963-1967`). Davor gibt es drei Ausstiege:

| Ausstieg | Zeile |
|---|---|
| Instanz ohne Daten (`_apply_instance("")`) | `anvil/mainwindow.py:1810-1826` (`return False`) |
| Speicherort nicht verfügbar | `anvil/mainwindow.py:1906-1907` (`return False`) |
| BG3 | `anvil/mainwindow.py:1929-1934` (`return True`) |

`_teardown_current_instance` räumt beides nicht auf (`anvil/mainwindow.py:1676-1757`:
kein `_order_hint`, kein `set_load_order_plugin`).

**Auswirkung:** Wechsel von Cyberpunk (Hinweis sichtbar) nach BG3 → die Hinweiszeile
des Vorgängerspiels bleibt stehen, und der Prioritäts-Tooltip behauptet weiter die
Cyberpunk-Einstufung. Die Zeile hängt in `mod_list_layout`
(`anvil/mainwindow.py:322`), also **außerhalb** des `QStackedWidget` — sie steht damit
auch über der BG3-Liste.

### M3 — Menüeintrag erscheint auch bei fremden Mods, tut dort aber nichts

`anvil/mainwindow.py:5051` filtert nur Trenner heraus (`not _ctx_entry.is_separator`).
Von Hand ins Spiel kopierte Mods stehen aber ebenfalls in der Liste
(`anvil/mainwindow.py:2052`, `anvil/core/foreign_mods.py:173-180`, `is_foreign=True`)
und haben **keinen** Ordner unter `.mods` — ihr Pfad steht in `foreign_path`.
Folge: Der Eintrag ist anklickbar, `mod_dir.is_dir()` schlägt fehl, stiller No-Op
(siehe K2). Vorschlag: wie bei Trennern ausschließen (`not getattr(_ctx_entry, "is_foreign", False)`).

### M4 — Der Merker erreicht den Deployer nach einem reinen `_reload_mod_list()` nicht

`_sync_keep_file_name_mods()` läuft an vier Stellen: `:2090` (Instanzwechsel),
`:2243` (Umschalten im Kontextmenü), `:3760` (vor dem Spielstart), `:6066`
(Profilwechsel). Das deckt die vom Auftrag genannten Wege ab — **aber** `meta.ini`
kann sich auch ohne diese vier Wege ändern: eine zurückgespielte Sicherung oder eine
Neuinstallation bringt ihre `meta.ini` mit, `_reload_mod_list()`
(`anvil/mainwindow.py:7926-7947`) liest sie neu ein und zeigt das „≡" in der Liste,
gibt sie aber nicht weiter.

**Auswirkung:** Wird danach über den Deploy-Knopf im Game-Panel ausgerollt (ohne
Spielstart, ohne Instanz-/Profilwechsel), nummeriert Anvil die Mod trotz Zeichen in
der Liste durch. Anzeige und Tat gehen auseinander. Gleiches Muster wie beim
Vorbild `_sync_separator_deploy_paths` — dort fällt es weniger auf, weil Deploy-Pfade
nur über das Kontextmenü entstehen.

---

## KLEIN

- **KL1** `anvil/core/mod_deployer.py:35` — `ARCHIVE_KEEP_EXTENSIONS as _BA2_SYMLINK_EXTENSIONS`
  wird im Modul **nirgends mehr** benutzt (die Prüfung steckt jetzt in
  `goes_into_archive`). Am Leben hält den Namen nur `tests/test_deploy_regeln.py:412`.
- **KL2** `anvil/mainwindow.py:303-304` — der Kommentar „Ausserhalb des Splitters"
  stimmt nicht: `mod_list_wrapper` wandert bei `:332` in `self._filter_splitter`.
  Die Zeile sitzt außerhalb des **Stacks**, nicht außerhalb des Splitters.
- **KL3** `order_scope.hide` ist in allen sieben Sprachdateien angelegt, wird aber
  nirgends verwendet (`grep` über `*.py` leer). Der ×-Knopf
  (`anvil/mainwindow.py:312-316`) hat weder Tooltip noch `accessibleName` — für
  Screenreader nur „×".
- **KL4** Doppelte Einstufungslogik: `_game_numbers_archives`
  (`anvil/mainwindow.py:2215-2227`) rechnet dasselbe wie
  `scope_for(...).archive_folgen_der_liste` (`anvil/core/load_order_scope.py:63-85`,
  `:42-45`). Beide stimmen heute überein, aber der Modul-Docstring
  (`load_order_scope.py:13-15`) verspricht ausdrücklich „an einer Stelle".
- **KL5** `anvil/core/diagnostics.py:288` gibt `scope.art` roh aus — im Report steht
  dann „Einstufung: teilweise" bzw. „voll"/„keine", also der interne Konstantenwert
  aus `load_order_scope.py:23-27`.
- **KL6** `anvil/models/mod_list_model.py:110` setzt `markers="≡"`. Damit greift bei
  eingeklappten Trennern die Flaggen-Anzeige (Einstellung 8):
  `_any_child_has_markers` (`:232-238`) → Flaggen-Icon (`:341-343`). Vermutlich
  gewollt, war vorher aber toter Code, weil `markers` immer leer war.
- **KL7** `anvil/widgets/settings_dialog.py:1546-1551` sucht das Plugin mit exaktem
  `==` auf `GameShortName`. `plugin_loader.get_game()` gibt es fertig und vergleicht
  `casefold()` (`anvil/plugins/plugin_loader.py:345-358`). Bei allen zehn echten
  `.anvil.ini` identisch, aber `get_game(kurz)` wäre die robustere und kürzere Fassung.
- **KL8** BG3-Zweig (`anvil/mainwindow.py:8666`) baut den Deployer neu, ohne
  `_sync_keep_file_name_mods` — das Panel behält die Namensmenge des Vorgängerspiels.
  Bei BG3 folgenlos (kein Pak-Nummerieren), aber alter Zustand.

---

## Geprüft und in Ordnung

**A) `keep_file_names` von der meta.ini bis in den Spielordner**

- `meta.ini` → `read_meta_ini` liest Groß-/Kleinschreibung unverändert
  (`anvil/core/mod_metadata.py:50`, `optionxform = str`) und flacht `[General]` mit ab
  (`:61-68`); `write_meta_ini` schreibt den Schlüssel nach `[General]`, weil er nicht
  in `_INSTALLED_KEYS` steht (`:96-107`), und **merged** (`:90-94`). Der Merker
  überlebt spätere Schreibvorgänge.
- `_build_entry` setzt ihn nur für echte Mods (`anvil/core/mod_entry.py:183-189`),
  `ModEntry.keep_file_names` (`:75-77`). Das neue Feld sitzt mitten im Dataclass —
  unkritisch, weil **alle** sechs `ModEntry(...)`-Aufrufe im Code mit Schlüsselwörtern
  arbeiten (`anvil/mainwindow.py:5222, 8752, 8768, 8796`, `anvil/core/foreign_mods.py:173`,
  `anvil/core/mod_entry.py:198`). Ebenso `ModRow` — einziger Aufruf
  `anvil/models/mod_list_model.py:106`, ebenfalls per Schlüsselwort.
- **Überlebt der Merker den Deployer-Neubau? Ja.** `set_instance_path` baut neu
  (`anvil/widgets/game_panel.py:3311-3313`), `_create_deployer` gibt das **Panel-Feld**
  mit (`:3293`), und das Feld wird beim Neubau nicht zurückgesetzt (`:591` nur im
  Konstruktor). Gleiches gilt für den zweiten Neubau in `update_game`
  (`anvil/widgets/game_panel.py:683-686`) und für den Profil-Umbenennen-Pfad
  (`anvil/mainwindow.py:5945`), der keinen Sync nachschiebt — er braucht auch keinen.
- Im Deployer: `_keep_file_name_mods` wird konsequent kleingeschrieben
  (`anvil/core/mod_deployer.py:354-355, 374, 378`), das Panel gibt Originalschreibung
  weiter (`game_panel.py:1156`) — passt zusammen, `tests/test_dateinamen_ausnahme.py:109`
  deckt es ab. Es gibt genau **eine** Nummerierungsstelle
  (`anvil/core/mod_deployer.py:774-790`), kein zweiter Weg umgeht die Ausnahme.
- Die Namen stammen aus `entry.name` (Ordnername, `anvil/mainwindow.py:2179`), das
  Kontextmenü übergibt ebenfalls `entry.name` (`:5058`, aufgelöst über `_entry_for_row`
  `:2155-2166`, das über `folder_name` matcht). Deckungsgleich mit dem, was der
  Deployer als `mod_name` sieht.
- Weitere Aufrufstellen von `_sync_separator_deploy_paths` gesucht: es gibt genau drei
  (`:2089`, `:3759`, `:6065`) — an **allen** dreien steht der neue Aufruf direkt
  darunter. Zusätzlich `:2243` nach dem Umschalten. Kein Aufruf vergessen (Einschränkung
  siehe M4).

**B) Kontextmenü-Eintrag**

- Qt-Falle geprüft und empirisch belegt: eine checkbare `QAction` schaltet ihren
  Zustand **vor** der Auswertung um — `a.setChecked(False); a.trigger()` → `isChecked()`
  ist `True`, umgekehrt genauso. `setCheckable/setChecked` (`anvil/mainwindow.py:5054-5057`)
  und `isChecked()` (`:5160`) ergeben zusammen den gewünschten neuen Zustand.
- Menü ohne Auswahl geschlossen: `if not chosen: return` (`anvil/mainwindow.py:5125`),
  und der neue Zweig ist zusätzlich mit `act_keep_names is not None` abgesichert
  (`:5158`) — kein `None == None`-Treffer.
- Die `.data()` des neuen Eintrags stört die beiden vorgezogenen `.data()`-Abfragen
  nicht: beide prüfen zusätzlich `chosen.parent()` gegen ein Untermenü
  (`:5113-5117`, `:5120-5123`), der neue Eintrag hängt direkt am Hauptmenü.
- Der ×-Knopf der Hinweiszeile fängt den bool sauber ab:
  `lambda checked=False: self._hide_order_hint()` (`anvil/mainwindow.py:315-317`).

**C) Prioritäts-Tooltip durch die Proxy**

Nicht vermutet, sondern gemessen (`QT_QPA_PLATFORM=offscreen`):

```
Proxy-Tooltip: 'Oben = höchste Priorität. Was das im Spiel bewirkt:\nBei diesem Spiel …'
Proxy-Display: 'Priorität'
headerDataChanged weitergereicht: [(Orientation.Horizontal, 6, 6)]
andere Spalte: None
```

- `ModListProxyModel` (`anvil/widgets/mod_list.py:589`) überschreibt **weder**
  `headerData` **noch** `filterAcceptsColumn` (Methodenliste der Klasse geprüft), also
  reicht `QSortFilterProxyModel` 1:1 durch; der Baum hängt an der Proxy
  (`anvil/widgets/mod_list.py:1298`).
- `headerDataChanged` wird von der Proxy weitergereicht (siehe Messung oben). Die
  Bedingung `if self.columnCount()` (`anvil/models/mod_list_model.py:784`) ist immer
  wahr, `columnCount` gibt die Konstante `COL_COUNT` zurück (`:292-293`).
- `headerData` gibt für andere Spalten unter `ToolTipRole` `None` zurück und den
  Anzeigenamen unverändert (`anvil/models/mod_list_model.py:790-802`).
- Beim Instanzwechsel kommt der Tooltip an — **außer** auf den drei Frühausstiegen,
  siehe M2.

**Weiteres**

- **Imports:** `QLabel` (`anvil/mainwindow.py:35`), `QToolButton` (`:21`),
  `QHBoxLayout` (`:24`) sind vorhanden. Alle neuen Modul-Importe von
  `load_order_scope` stehen bewusst in der Funktion
  (`mainwindow.py:2204`, `diagnostics.py:281`, `mod_detail_dialog.py:1515`,
  `mod_list_model.py:797`).
- **Zirkuläre Importe: keine.** `load_order_scope` importiert außer `dataclasses`
  nichts auf Modulebene; `translator` selbst zieht nur `json`/`pathlib`
  (`anvil/core/translator.py:14-16`). Der funktionsinterne `tr`-Import ist im Modul
  konsequent (beide Stellen: `:96`, `:119`) und entspricht einem im Projekt schon
  vorhandenen Muster (`anvil/core/foreign_mods.py:169`) — technisch nötig ist er
  nicht, schadet aber nicht.
- **settings_dialog:** `self._idata` (`:145`, gefüllt `:150`) und `self._plugin_loader`
  (`:84`) existieren, `all_plugins()` gibt es (`anvil/plugins/plugin_loader.py:337`).
  `game_short_name` ist der richtige Schlüssel — in allen zehn `.anvil.ini` unter
  `/home/mob/.anvil-organizer/instances/` vorhanden (`SkyrimSE`, `cyberpunk2077`,
  `Stalker2`, …). Siehe KL7 für die kürzere Variante.
- **mod_detail_dialog:** `game_plugin` ist Parameter von `_build_conflicts_tab`
  (`:1340-1343`) und wird vom einzigen Aufrufer durchgereicht (`:1952-1954`);
  `scope_for(None)` ist abgesichert (`load_order_scope.py:60-61`) und führt zum
  vorsichtigen „das Spiel entscheidet"-Satz.
- **Kein `setStyleSheet()` in den neuen Widgets.** Die Hinweiszeile
  (`anvil/mainwindow.py:305-322`) setzt keine Styles. Das einzige `setStyleSheet` im
  Diff steht in `anvil/dialogs/mod_detail_dialog.py:1521` und ist eine **unveränderte
  Bestandszeile** (`hinweis.setStyleSheet(_dim_info_style())`), nur der Text davor
  wurde ersetzt. Regel eingehalten.
- **Übersetzungen:** alle zwölf neuen Schlüssel (`context.keep_file_names`,
  `tooltip.keep_file_names`, `log.keep_file_names_on/off`,
  `mod_detail.archive_winner_numbered/unsure`, `order_scope.*`) sind in **allen sieben**
  Sprachdateien (de, en, es, fr, it, pt, ru) vorhanden, die Platzhalter `{dirs}`,
  `{rest}`, `{name}` stimmen überall überein (per Skript geprüft).

---

## UNSICHER

1. **Altlasten im Spielordner beim Umschalten.** Wird eine bereits ausgerollte Mod
   nachträglich ausgenommen, liegt die alte durchnummerierte Datei noch im Spiel, bis
   der nächste Purge läuft. Ob das Manifest sie sauber wegräumt
   (`_drop_superseded_numbered`), habe ich nicht nachvollzogen — das gehört zur
   Deploy-Logik, nicht zur Verkabelung.
2. **`_game_numbers_archives()` bei `GamePakLoadOrderDirs`.** Der Menüeintrag
   erscheint für jede Mod, sobald das Spiel *irgendeinen* nummerierten Ordner hat.
   Liegt die konkrete Mod außerhalb dieser Ordner, ändert das Umschalten nichts
   (`pak_order_allows`, `anvil/core/mod_deployer.py:780`). Ob das gewollt ist oder ob
   der Eintrag pro Mod ausgegraut gehören würde, ist eine Produktentscheidung.
3. **Optik der Hinweiszeile.** Ob der Text ohne eigenes Styling im QSS-Theme als
   Hinweis erkennbar ist (Farbe, Abstand) und wie er bei schmalem Fenster umbricht,
   lässt sich nur am laufenden Programm beurteilen — ich habe die App nicht gestartet.
