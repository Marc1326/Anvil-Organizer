# Prüfbericht P1 — Bugs, Logikfehler, Randfälle

Geprüft: unkommittierte Änderungen, Stand 13.08.2026.
Testlauf: `.venv/bin/python -m pytest tests -q` → **850 passed, 1 skipped** (wie erwartet).

Geprüfte Bereiche: `deploy_rules.py`-Umbau, `keep_file_names`, `load_order_scope.py`
samt Spaltenkopf / Hinweiszeile / Konflikte-Bereich / Diagnose-Bericht.

---

## Vorab: Der Umbau selbst ist sauber

Zeile für Zeile gegen den alten Inline-Code verglichen — **kein Verhaltensunterschied gefunden.**

| Regel | alt | neu | gleich? |
|---|---|---|---|
| `root/` abziehen | mod_deployer.py (Merge-Base) | `deploy_rules.py:60-64` | ja, wörtlich |
| Archiv-Packen | `ext not in KEEP and not stays_loose → continue` | `goes_into_archive()` = `suffix.lower() in KEEP → False`, sonst `not is_archive_loose_path(...)` | ja, identische Wahrheitstafel |
| Data-Präfix + Umleitungen | Inline-Block | `apply_data_path()` `deploy_rules.py:84-114` | ja, inkl. `len(rel.parts) > 1`, `relative_to`-Schutz und `nest_under_mod_name` |

Randfälle geprüft:

- **Groß-/Kleinschreibung:** `strip_root` und `SKIP_DIRS` vergleichen weiterhin
  `lower()`; die Ordner-Umleitung (`rel.parts[0] in routes`, `deploy_rules.py:103`)
  vergleicht weiterhin **case-sensitiv** — genau wie vorher.
- **Leerer Pfad / nur ein Teil:** `strip_root` gibt bei `root` allein `rel`
  unverändert zurück (`deploy_rules.py:63`) — wie vorher. `apply_data_path`
  verlangt weiterhin `len(rel.parts) > 1` für die Umleitung.
- **`data_path` leer / `is_direct`:** früher `if self._data_path and not is_direct`,
  jetzt `if not data_path or is_direct: return rel` — logisch identisch.
- **`loose_paths=None`:** `self._ba2_loose_paths` ist schon im Konstruktor auf `[]`
  normalisiert (`mod_deployer.py:341`), das zusätzliche `or []` in
  `deploy_rules.py:81` ändert nichts.

**Reihenfolge im Deployer stimmt** (`mod_deployer.py:736-795`):
`strip_root` → Archiv-Prüfung → `is_direct` → `strip_deploy_prefixes`/`route_deploy_path`
→ `apply_data_path` → Durchnummerierung. Zielverteilung vor Data-Präfix, Nummerierung danach.

**Mutationsproben** (Code nicht angefasst, Patch nur zur Laufzeit über `PYTHONPATH`):

- `strip_root` zum No-Op gemacht → `test_root_ordner_wird_abgezogen` fällt. Test ist echt.
- `keeps_file_names` immer `False` → 6 Tests in `test_dateinamen_ausnahme.py` fallen. Tests sind echt.

---

## FUND 1 — Hartcodierter `.mods`-Pfad: „Dateinamen nicht ändern" wirkt bei verlegtem Mod-Ordner überhaupt nicht

**Schweregrad: KRITISCH**
`anvil/mainwindow.py:2230`

```python
mod_dir = self._current_instance_path / ".mods" / mod_name
if not mod_dir.is_dir():
    return
```

Der Mod-Ordner einer Instanz ist frei konfigurierbar
(`path_mods_directory`, `anvil/core/instance_paths.py:69`); er darf ein
beliebiger absoluter Pfad außerhalb der Instanz sein. Alle über 20 anderen
Stellen im Hauptfenster lesen ihn korrekt über `_active_instance_paths(self).mods`
— zum Beispiel `_fix_stray_preset` direkt daneben (`anvil/mainwindow.py:2648`)
und `_reload_mod_list` (`anvil/mainwindow.py:7944`), das in derselben Funktion
aufgerufen wird.

**Was passiert:** Liegt der Mod-Ordner nicht unter `<Instanz>/.mods`, existiert
`mod_dir` nicht, die Funktion steigt in Zeile 2232 wortlos aus. Kein Log, kein
Toast, keine Fehlermeldung. Der Menüpunkt lässt sich anklicken, das Häkchen
verschwindet beim nächsten Öffnen wieder, und niemand erfährt warum.

**Auslösen:** Instanz mit `path_mods_directory` auf ein anderes Laufwerk
(z.B. `/mnt/gamingS/...`) anlegen → Rechtsklick auf eine Mod →
„Dateinamen nicht ändern" → nichts passiert.

Verstößt außerdem gegen die Projektregel „NIEMALS hardcoded Pfade".

---

## FUND 2 — Erfolgsmeldung auch wenn das Schreiben fehlschlägt

**Schweregrad: MITTEL**
`anvil/mainwindow.py:2233-2237` zusammen mit `anvil/core/mod_metadata.py:109-117`

```python
try:
    write_meta_ini(mod_dir, {"keep_file_names": ...})
except OSError as exc:
    self._log_panel.add_log("warning", f"{mod_name}: {exc}")
    return
```

`write_meta_ini` **wirft niemals** `OSError` — es fängt selbst ab und schreibt
nur nach `stderr`:

```python
except OSError as exc:
    print(f"mod_metadata: failed to write {ini}: {exc}", file=sys.stderr)
```

**Folge:** Der `except`-Zweig ist toter Code. Bei schreibgeschütztem Mod-Ordner,
vollem Datenträger oder nicht mehr gemountetem Laufwerk läuft die Funktion
weiter, schreibt `log.keep_file_names_on` ins Log und behauptet Erfolg. Der
Merker steht danach nicht in der `meta.ini`; nach dem `_reload_mod_list()` in
Zeile 2239 ist das Häkchen wieder weg — ohne Erklärung.

**Auslösen:** `chmod 500` auf einen Mod-Ordner → Menüpunkt anklicken → Log sagt
„Dateinamen bleiben unverändert", die Mod wird beim nächsten Deploy trotzdem
durchnummeriert.

---

## FUND 3 — Verschwundener Mod-Ordner wird stillschweigend geschluckt

**Schweregrad: MITTEL**
`anvil/mainwindow.py:2226-2232`

Beide Abbruchpfade (`not self._current_instance_path`, `not mod_dir.is_dir()`)
kehren ohne jede Rückmeldung zurück. Genau der Fall, für den es die
Fehlerbehandlung geben soll — Mod-Ordner extern gelöscht, Laufwerk ausgehängt,
fremde Mod (`is_foreign`), die gar nicht unter dem Mod-Ordner liegt —
sieht für den Benutzer aus wie ein wirkungsloser Klick.

Zum Vergleich: Der Menüpunkt wird für fremde Mods (`is_foreign`) nicht
ausgeblendet (`anvil/mainwindow.py:5051-5058` prüft nur `is_separator`), obwohl
er dort nie funktionieren kann.

---

## FUND 4 — Die Änderung am Konflikte-Bereich ist durch keinen Test gedeckt

**Schweregrad: MITTEL** (Testlücke, kein Laufzeitfehler)
`anvil/dialogs/mod_detail_dialog.py:1512-1521`,
`tests/test_reihenfolge_anzeige.py:242-252`

**Bewiesen per Mutationsprobe:** Beide neuen Sätze zur Laufzeit auf `""` gesetzt
(`tr("mod_detail.archive_winner_numbered")` und `..._unsure` liefern Leerstring)
→ **850 passed, 1 skipped**. Nicht ein einziger Test schlägt an.

Die beiden Tests, die im Abschnitt „Der Konflikte-Bereich" stehen, prüfen die
Änderung nicht:

- `test_falscher_gruen_satz_steht_nicht_mehr_im_grundtext` (Zeile 242) liest nur
  `de.json` und prüft, dass „Grün" nicht mehr im Grundtext steht. Sagt nichts
  darüber, ob der Dialog den richtigen Zusatzsatz anhängt.
- `test_konflikt_hinweis_haengt_am_spiel` (Zeile 248) ruft ausschließlich
  `scope_for()` auf — dieselben zwei Zusicherungen stehen schon in
  `test_cyberpunk_nummeriert_in_einem_ordner` (Zeile 35) und
  `test_stellarblade_nummeriert_nicht` (Zeile 60). Der Test bliebe grün, wenn
  man `mod_detail_dialog.py` komplett auf den alten Stand zurücksetzt.

Das ist ein Schein-Test: Er steht unter einer Überschrift, deren Gegenstand er
nicht berührt. `tests/test_konflikt_reihenfolge.py:128` ruft
`_build_conflicts_tab(...)` zwar auf, prüft aber nur die Konfliktbäume, nie das
Hinweis-Label.

---

## FUND 5 — `_toggle_keep_file_names` hat null Testabdeckung

**Schweregrad: MITTEL** (Testlücke)

`grep -rn "_toggle_keep_file_names" tests/` → kein Treffer. Die einzige Stelle,
die den Merker tatsächlich schreibt, ist ungeprüft — deshalb sind FUND 1, 2 und 3
durch die Suite nicht aufgefallen. Geprüft werden nur die Nachbarn
(`_game_numbers_archives`, `_sync_keep_file_name_mods`, der Setter am Panel).

Gleiches gilt für `settings_dialog._diag_game_plugin`
(`anvil/widgets/settings_dialog.py:1539-1551`): `build_report(..., game_plugin=...)`
ist getestet, die Verkabelung dorthin nicht.

---

## FUND 6 — Das `≡`-Zeichen und sein Tooltip erscheinen auch bei Spielen, die gar nicht nummerieren

**Schweregrad: MITTEL**
`anvil/models/mod_list_model.py:112` und `:403-405`

```python
markers="≡" if keep_names else "",
```

`mod_entry_to_row` kennt das Spiel-Plugin nicht. Steht `keep_file_names=1` in
einer `meta.ini`, wird das Zeichen bei **jedem** Spiel angezeigt, samt Tooltip
`tooltip.keep_file_names`:

> „Ihre Position in der Liste wirkt dadurch nicht mehr, und eine gleichnamige
> Datei einer anderen Mod kann zusätzlich im Spiel liegen."

Bei Skyrim / Fallout / Stellar Blade (keine Nummerierung) ist beides **falsch** —
dort folgen lose Dateien weiterhin der Reihenfolge, und der Merker bewirkt
überhaupt nichts. Der Menüpunkt wird bei solchen Spielen korrekt ausgeblendet
(`anvil/mainwindow.py:5052`), das rettet aber nur den Neu-Setzen-Fall.

**Auslösen:** Mod-Ordner aus einer Cyberpunk-Instanz in eine Skyrim-Instanz
kopieren oder aus einer Sicherung zurückspielen (die `meta.ini` reist mit) →
`≡` und irreführender Tooltip in einer Liste, in der das Häkchen nicht einmal
setzbar wäre.

Dieselbe Kopplung trifft die Sammelanzeige auf eingeklappten Trennern:
`_any_child_has_markers` (`anvil/models/mod_list_model.py:232-238`) lieferte
bisher **immer** `False`, weil `markers` hartcodiert leer war. Ab jetzt ist
`keep_file_names` der einzige Auslöser für das Flaggen-Symbol aus Einstellung 8
(`anvil/models/mod_list_model.py:341-343`) — funktional in Ordnung, aber eine
Nebenwirkung, die nirgends geprüft wird.

---

## FUND 7 — `deploy_rules.is_metadata` und `target_rel` sind auf `main` toter Code

**Schweregrad: KLEIN**
`anvil/core/deploy_rules.py:42-57` und `:117-141`

`grep -rn "is_metadata\|target_rel" --include="*.py" anvil/` findet **nur die
Definitionen selbst**. `mod_deployer.py` importiert beide nicht
(`anvil/core/mod_deployer.py:34-42`) und hat die drei Prüfungen weiterhin inline
(`:702-716`). `target_rel` ruft überhaupt niemand auf, auch kein Test.

Die Docstring von `is_metadata` behauptet:

> „Der Symlink-Weg hat dieselben drei Pruefungen inline stehen"

— richtig, aber der Overlay-Weg, für den die Funktion gedacht ist, existiert auf
`main` nicht. Damit ist `test_is_metadata_stimmt_mit_dem_deploy_ueberein`
(`tests/test_deploy_regeln.py:292`) der einzige Nutzer. Das ist ein Schutznetz
für später, kein Fehler — sollte aber bewusst so gewollt sein.

---

## FUND 8 — Übersetzungsschlüssel `order_scope.hide` wird nirgends benutzt

**Schweregrad: KLEIN**
`anvil/locales/de.json:1486` (und die sechs anderen Sprachdateien)

`"hide": "Hinweis ausblenden"` ist in allen 7 Locales eingetragen, aber
`grep -rn "order_scope.hide" --include="*.py" anvil/` findet nichts. Der
×-Knopf (`anvil/mainwindow.py:314-316`) bekommt weder `setToolTip()` noch
`setAccessibleName()` — er trägt nur das Zeichen `×`. Vermutlich war der Tooltip
geplant und ist beim Bauen liegengeblieben.

---

## FUND 9 — Kommentar zur Hinweiszeile stimmt nicht

**Schweregrad: KLEIN**
`anvil/mainwindow.py:304-306`

> „Ausserhalb des Splitters, damit ihn das Ziehen der Bereichsleisten nicht
> zerquetscht."

Die Zeile wird in `mod_list_layout` gehängt (`anvil/mainwindow.py:322`), und
`mod_list_wrapper` steckt genau **im** Splitter (`anvil/mainwindow.py:332`:
`self._filter_splitter.addWidget(mod_list_wrapper)`). Funktional harmlos — der
Splitter ist horizontal, die Zeile wird also nicht vertikal gequetscht — aber
der Kommentar behauptet das Gegenteil dessen, was der Code tut.

---

## FUND 10 — Ohne Plugin teilen sich alle Instanzen einen „weggeklickt"-Schalter

**Schweregrad: KLEIN**
`anvil/mainwindow.py:2184-2186`

```python
kurz = getattr(self._current_plugin, "GameShortName", "") or "?"
return f"ModList/order_hint_hidden/{kurz}"
```

Bei fehlendem Plugin (Instanz ohne erkanntes Spiel, `anvil/mainwindow.py:1846`
liefert dann `None`) lautet der Schlüssel für **alle** solchen Instanzen
`ModList/order_hint_hidden/?`. Einmal weggeklickt gilt es für alle. Da bei
`plugin is None` ohnehin `scope.art == KEINE` gilt und der Hinweis der einzig
mögliche ist, ist die Auswirkung gering.

Der Rest der Hinweiszeile ist sauber: `_update_order_hint` sichert sich mit
`getattr(self, "_order_hint", None)` gegen den Aufruf vor dem Aufbau ab
(`anvil/mainwindow.py:2195-2197`), wird beim Spielwechsel in `_apply_instance`
nach dem Setzen von `self._current_plugin` (Zeile 1847) aufgerufen (Zeile 1967)
und schaltet bei einem Spiel mit Nummerierung wieder auf unsichtbar
(Zeile 2201-2203). Ein Sprachwechsel erfordert laut
`settings.language_restart_hint` einen Neustart, der statische Labeltext ist
also unkritisch.

---

## FUND 11 — Zwei neue Tests hängen am Arbeitsverzeichnis

**Schweregrad: KLEIN**
`tests/test_dateinamen_ausnahme.py:355` und `:365`,
`tests/test_reihenfolge_anzeige.py:148`, `:158`, `:244`

```python
Path("anvil/locales/de.json").read_text(encoding="utf-8")
```

Relativer Pfad statt einer Ableitung aus `__file__`. Aus dem Projektstamm
gestartet grün, aus einem Unterverzeichnis (`pytest ../tests`) `FileNotFoundError`.

---

## Was ich geprüft und in Ordnung gefunden habe

**`keep_file_names` — gleichnamige Dateien.** Ist eine Mod ausgenommen und trägt
ihre Datei denselben Namen wie die einer nummerierten Mod, liegen danach beide im
Spielordner: `_drop_superseded_numbered` überspringt Einträge ohne
`unnumbered`-Schlüssel (`anvil/core/mod_deployer.py:1037-1039`), und der Merker
sorgt dafür, dass genau dieser Schlüssel nicht gesetzt wird
(`:774-795`). Das ist beabsichtigt und im Tooltip als Preis benannt; ein Test
sichert es ab (`tests/test_dateinamen_ausnahme.py:143`). Sind **beide** Mods
ausgenommen, überschreibt die höher stehende die niedrigere wie vor der
Nummerierung.

**Purge.** Läuft über die `link`-Pfade aus dem Manifest
(`anvil/core/mod_deployer.py:1210-1215`) — die stehen für ausgenommene Mods ohne
Zähler drin, werden also korrekt wieder entfernt. Kein Rest im Spielordner.

**Manifest.** `unnumbered` fehlt bei ausgenommenen Mods, `link`/`target`/`mod`/`type`
sind unverändert. Getestet in beide Richtungen
(`tests/test_dateinamen_ausnahme.py:143` und `:166`).

**Zähler der übrigen Mods.** Die ausgenommene Mod verbraucht weiterhin ihren
`load_index` (`anvil/core/mod_deployer.py:784-787`), die Nummern der anderen
verschieben sich nicht. Getestet (`tests/test_dateinamen_ausnahme.py:96`).

**Menü und Deployer stimmen überein.** `_game_numbers_archives`
(`anvil/mainwindow.py:2219-2222`) prüft `GamePakLoadOrderDirs or
GamePakLoadOrderPrefix` — dieselbe Bedingung wie `nummerieren` im Deployer
(`anvil/core/mod_deployer.py:775-778`), gespeist aus denselben Plugin-Attributen
(`anvil/widgets/game_panel.py:3264-3265`).

**`scope_for`.** Unterordner-Erkennung (`load_order_scope.py:71-74`),
Backslash-Normalisierung (`:51`), `plugin is None` (`:60-61`) — alles abgedeckt
und korrekt. Cyberpunk liefert `TEILWEISE` mit `archive/pc/mod` und nennt
`mods`, `r6/scripts` usw. als Rest.

**Verkabelung `keep_file_names`.** meta.ini → `ModEntry.keep_file_names`
(`anvil/core/mod_entry.py:183-188`) → `_sync_keep_file_name_mods`
(`anvil/mainwindow.py:2176-2182`) → `GamePanel.set_keep_file_name_mods`
(`anvil/widgets/game_panel.py:1154-1158`) → `ModDeployer`. Groß-/Kleinschreibung
wird erst im Deployer vereinheitlicht (`:354-356`, `:378`), das ist konsistent.
Trenner bekommen den Merker nie (`anvil/core/mod_entry.py:184`).

**Kontextmenü.** `act_keep_names.isChecked()` liefert nach dem Klick den **neuen**
Zustand (Qt schaltet `checkable` Actions beim Auslösen um) — der Aufruf in
`anvil/mainwindow.py:5158-5161` ist damit richtig herum.

**Spaltenkopf.** `headerData` gibt für andere Rollen als Display/ToolTip weiterhin
`None` zurück und verschluckt die Beschriftung nicht
(`anvil/models/mod_list_model.py:790-800`). `set_load_order_plugin` ruft
`columnCount()` ohne Argument auf — zulässig, der Parameter hat einen Default
(`anvil/models/mod_list_model.py:292`).

**Übersetzungen.** Alle neuen Schlüssel liegen in allen 7 Locale-Dateien
(de, en, es, fr, it, pt, ru); Platzhalter `{dirs}` / `{rest}` / `{name}` sind
überall vorhanden. Zwei Tests sichern das ab.

---

## UNSICHER — nicht belegt

1. **Sortieren nach der Marker-Spalte.** `ModListProxyModel`
   (`anvil/widgets/mod_list.py:589`) hat kein eigenes `lessThan`, sortiert also
   nach dem Anzeigetext. Bisher war die Spalte für jede Zeile leer, jetzt nicht
   mehr — ein Klick auf den Spaltenkopf ordnet die Liste dadurch anders. Ob das
   praktisch stört, konnte ich ohne laufende GUI nicht beurteilen; das Einklappen
   von Trennern ist bei Sortierung nach dieser Spalte ohnehin schon abgeschaltet
   (`anvil/widgets/mod_list.py:798-801`). Ich habe **nicht** geprüft, ob eine
   anschließende Drag-and-Drop-Aktion in sortiertem Zustand die echte
   Ladereihenfolge verfälscht — das wäre ein Altlast-Thema, kein neues.

2. **Rohe Einstufung im Diagnose-Bericht.** `anvil/core/diagnostics.py:288`
   schreibt `f"Einstufung: {scope.art}"`, also die interne Konstante
   `voll` / `teilweise` / `keine` ungefiltert in einen Text, den Benutzer
   verschicken. Ob das gewollt ist (Support liest es) oder ein Ausrutscher, kann
   ich nicht entscheiden.

3. **`_sync_keep_file_name_mods` nach externem Eingriff.** Die Funktion wird an
   denselben vier Stellen aufgerufen wie `_sync_separator_deploy_paths`
   (`anvil/mainwindow.py:2089/2090`, `2243`, `3759/3760`, `6065/6066`), nicht
   aber nach einem gewöhnlichen `_reload_mod_list()`. Wird eine `meta.ini` von
   außen geändert und die Liste nur aktualisiert, arbeitet ein manueller
   Deploy mit dem alten Stand. Da der bestehende Trenner-Mechanismus dieselbe
   Lücke hat und der Start-Deploy-Pfad synchronisiert, halte ich das für
   bewusste Parität — belegen kann ich es nicht.

4. **`GamePakLoadOrderDirs = [""]`.** Eine Liste aus leeren Einträgen wäre für
   `_game_numbers_archives` wahr (Menü erscheint), für `scope_for` dagegen leer
   (`load_order_scope.py:51`, `:68`) und für `pak_order_allows` wirkungslos
   (`mod_deployer.py:236-239`). Kein ausgeliefertes Plugin macht das, ich habe
   den Fall daher nur theoretisch betrachtet.
