# Prüfung P4: Das Gebaute gegen die drei Pläne

Stand: 13.08.2026 — reine Lesung, kein Code geändert.
Testlauf: `.venv/bin/python -m pytest tests -q` → **850 passed, 1 skipped** in 16,01 s.
Erwartung getroffen.

Geprüfter Arbeitsstand (`git status`): 15 geänderte Produktivdateien,
3 geänderte Testdateien, 3 neue Testdateien, 2 neue Kernmodule.

---

## 1. Plan 1 — `docs/anvil-plan-stufe1-deploy-rules.md`

Der Plan hat keine nummerierte Akzeptanzliste, sondern **Schritte 0–5**, ein
**hartes Erfolgskriterium** (Abschnitt 5) und einen Abschnitt
**„Was bewusst NICHT getan wird"** (Zeilen 311–325).

### 1.1 Die Schritte

| Schritt | Verlangt | Einstufung | Beleg |
|---|---|---|---|
| 0 — Schutztests vorab | Neue Datei `tests/test_deploy_regeln.py`, Fälle 1–6 | **ERFÜLLT** | `tests/test_deploy_regeln.py` — Fall 1: `:56`, `:73`; Fall 2: `:90`; Fall 3: `:108`, `:123`; Fall 4: `:146`, `:162`; Fall 5: `:176`, `:186`; Fall 6: `:213`, `:232`, `:251` |
| 1 — `deploy_rules.py` anlegen | Branch-Stand wörtlich, 127 Zeilen | **ERFÜLLT, mit Abweichung** | `anvil/core/deploy_rules.py` existiert, 142 Zeilen. Konstanten `:20`, `:23`, `:27`, `:34`; Funktionen `is_metadata:42`, `strip_root:60`, `goes_into_archive:67`, `apply_data_path:84`, `target_rel:117`. Länger als 127 Zeilen, weil zwei Docstrings erweitert wurden (`:44-50`, `:126-133`) — inhaltlich identisch |
| 2 — Import + Konstanten | Branch-Import mit allen vier Aliasen, alte Konstanten löschen | **ERFÜLLT** | `anvil/core/mod_deployer.py:34-42` (Import inkl. `ARCHIVE_KEEP_EXTENSIONS as _BA2_SYMLINK_EXTENSIONS`), alte Blöcke gelöscht (`git diff`, Hunk `@@ -40,22 +47,0 @@`). `is_archive_loose_path`-Import entfällt |
| 3 — `root/`-Strip ersetzen | `rel = strip_root(rel)`, Zeilen 720–727 nicht anfassen | **ERFÜLLT** | `anvil/core/mod_deployer.py:736`. Der `fehlt`-Block davor ist unberührt (Hunk beginnt erst bei `-732`) |
| 4 — Archiv-Prüfung ersetzen | `goes_into_archive(...)` | **ERFÜLLT** | `anvil/core/mod_deployer.py:740-746` |
| 5 — Data-Präfix ersetzen, Nachbarblöcke bleiben | `apply_data_path(...)`, Zielverteilung davor, Nummerierung danach | **ERFÜLLT** | `anvil/core/mod_deployer.py:762-772`. Zielverteilung steht davor (`:755-761`, unverändert), Nummerierung dahinter (`:774 ff.`) |

### 1.2 Das harte Erfolgskriterium — „vorhandene Tests UNVERÄNDERT grün"

`git diff tests/` zeigt **drei geänderte Bestandstests**. Alle drei geprüft:

| Datei | Änderung | Bewertung |
|---|---|---|
| `tests/test_bodyslide_deployment.py:131` | `_keep_file_name_mods: set = set()` in einer Panel-**Attrappe** | **legitim** — die Attrappe bildet die erweiterte Panel-Schnittstelle nach (`anvil/widgets/game_panel.py:591`). Keine Zusicherung geändert |
| `tests/test_custom_deployer_paths.py:129` | dasselbe | **legitim**, gleiche Begründung |
| `tests/test_predeploy_launch.py:78, 242, 389, 411, 699, 726, 986` | 7× `_sync_keep_file_name_mods=lambda: None` in `SimpleNamespace`-Attrappen des Hauptfensters | **legitim** — Gegenstück zum bereits vorhandenen `_sync_separator_deploy_paths=lambda: None` in derselben Zeile darüber. Ohne den Eintrag würde die Attrappe an `mainwindow.py:3760` abstürzen |

**Kein Test wurde angepasst, damit er nicht mehr rot ist.** In allen sieben
Hunks wurde nur ein Feld/Callback zu einer Attrappe hinzugefügt; keine
`assert`-Zeile, kein Erwartungswert, keine Testlogik wurde berührt.
Zusätzlich: alle drei Änderungen stammen aus **Plan 2**, nicht aus Plan 1 —
der Umbau aus Plan 1 kam ohne jede Teständerung aus.

**Einstufung: ERFÜLLT.**

Zusatzbeleg für die Regel-Abdeckung: `tests/test_deploy_regeln.py:400-413`
prüft per `is`-Identität, dass `mod_deployer` die vier Mengen wirklich aus
`deploy_rules` bezieht und nicht heimlich eigene führt.

### 1.3 Die Grenzen aus „Was bewusst NICHT getan wird"

| Grenze | Eingehalten? | Beleg |
|---|---|---|
| `ba2_packer.py` unangetastet | **JA** | steht nicht in `git status` |
| `plugins_txt_writer.py` unangetastet | **JA** | steht nicht in `git status` |
| `set_separator_deploy_paths` nicht übernommen | **JA** | `grep set_separator_deploy_paths anvil/core/mod_deployer.py` → kein Treffer |
| Skip-Prüfungen bleiben inline, **kein** Umbau auf `is_metadata` | **JA** | `anvil/core/mod_deployer.py:702`, `:708`, `:715` stehen unverändert inline; `is_metadata` wird im Deployer nirgends gerufen |
| `pak_order_allows`, `load_order_index`, `pak_load_order_name`, `strip_deploy_prefixes`, `has_deploy_anchor`, `route_deploy_path` bleiben in `mod_deployer.py` | **JA** | `git diff -U0` liefert die Hunks `@@ -34`, `-40`, `-333`, `-366`, `-375`, `-732`, `-737`, `-761`, `-786`. Die Funktionen liegen bei `:201`, `:227`, `:240` bzw. `:72`, `:109`, `:153` — **kein Hunk berührt sie** |

**Keine Grenze überschritten.**

### 1.4 Abweichungen bei Plan 1

1. `deploy_rules.py` ist 142 statt 127 Zeilen. Ursache: der Docstring von
   `is_metadata` (`:44-50`) verweist neu auf `tests/test_deploy_regeln.py`,
   und `target_rel` (`:126-133`) trägt die Warnung, die Plan 1 unter
   Risiko 6 (Zeilen 402–405) „spätestens mit Stufe 2" gefordert hatte.
   Vorgezogen, nicht erfunden. Kein Verhaltensunterschied.
2. `tests/test_deploy_regeln.py:292` (`test_is_metadata_stimmt_mit_dem_deploy_ueberein`)
   ist **zusätzlich** zu den sechs geplanten Fällen. Es schließt genau
   Risiko 5 des Plans (Zeilen 396–401: „`is_metadata` driftet ab Tag eins ab").
   Sinnvolle Zugabe, kein Grenzübertritt.

---

## 2. Plan 2 — `docs/anvil-plan-nicht-umbenennen.md`

### 2.1 Akzeptanz-Checkliste (Abschnitt 6, 21 Punkte)

| # | Kriterium | Einstufung | Beleg |
|---|---|---|---|
| 1 | Abhakbarer Eintrag bei Mods, nicht bei Trennern | **ERFÜLLT** | `anvil/mainwindow.py:5052-5057` — `if single and _ctx_entry is not None and not _ctx_entry.is_separator:`, `setCheckable(True)` |
| 2 | Bei Spielen ohne Nummerierung fehlt der Eintrag | **ERFÜLLT** | `anvil/mainwindow.py:5053` ruft `_game_numbers_archives()` (`:2214-2224`); Test `tests/test_dateinamen_ausnahme.py:309-326` prüft alle fünf Fälle inkl. `None` |
| 3 | `keep_file_names = 1` unter `[General]` in der `meta.ini` | **ERFÜLLT** | `anvil/mainwindow.py:2237` schreibt `{"keep_file_names": "1" if an else "0"}`; `anvil/core/mod_metadata.py:96-107` legt alles außer den fünf `installed`-Schlüsseln in `[General]` |
| 4 | Abhaken → Wert leer, wird wieder nummeriert | **TEILWEISE** | Geschrieben wird `"0"`, nicht `""` (`anvil/mainwindow.py:2237`). Die **Wirkung** stimmt (`anvil/core/mod_entry.py:185-187` wertet nur `1/true/yes`; Test `tests/test_dateinamen_ausnahme.py:204-210`), der Wortlaut des Kriteriums („ist der Wert leer") nicht |
| 5 | Haken beim erneuten Öffnen sichtbar | **ERFÜLLT** | `anvil/mainwindow.py:5056` — `setChecked(getattr(_ctx_entry, "keep_file_names", False))`. Kein automatischer Test (GUI) |
| 6 | Nach Deploy: ausgenommene `.archive` ohne Präfix, andere mit | **ERFÜLLT** | `tests/test_dateinamen_ausnahme.py:66-80` (`CyberEngine.archive` ohne, `001_Textur.archive` mit) |
| 7 | Merker entfernt → wieder Präfix | **ERFÜLLT** | `tests/test_dateinamen_ausnahme.py:83-93` (Gegenprobe), `:238-249` (Setter-Weg) |
| 8 | Tooltip nennt beide Folgen | **ERFÜLLT** | `anvil/models/mod_list_model.py:403-405`; Text `anvil/locales/de.json:343`; Test `tests/test_dateinamen_ausnahme.py:350-359` prüft „Position" und „gleichnamige" |
| 9 | Zeichen in `COL_MARKERS`, sonst leer | **ERFÜLLT** | `anvil/models/mod_list_model.py:110-112` (`markers="≡" if keep_names else ""`); Test `tests/test_dateinamen_ausnahme.py:332-347` |
| 10 | Mod-Ordner umbenannt → Merker bleibt | **ERFÜLLT (durch Bauart), NICHT GETESTET** | Der Merker liegt in `.mods/<Mod>/meta.ini` und wandert mit dem Ordner. Der geplante Test T7 fehlt |
| 11 | Log-Zeile mit Mod-Namen | **ERFÜLLT** | `anvil/mainwindow.py:2245-2249`; Schlüssel `log.keep_file_names_on/off` in allen 7 Locales (nachgeprüft) |
| 12 | Mehrfachauswahl: Merker bei allen Nicht-Trenner-Zeilen | **NICHT ERFÜLLT** | Der Menüpunkt entsteht nur unter `if single …` (`anvil/mainwindow.py:5053`), und `_toggle_keep_file_names(mod_name, an)` (`:2226`) nimmt genau **einen** Namen. Bei Mehrfachauswahl erscheint der Eintrag gar nicht |
| 13 | Manifest ohne `unnumbered` | **ERFÜLLT** | `tests/test_dateinamen_ausnahme.py:143-163`, Gegenprobe `:166-179` |
| 14 | Gleichnamige Datei wird nicht gelöscht | **ERFÜLLT (durch Bauart), NICHT GETESTET** | `_drop_superseded_numbered()` springt bei leerem `unnumbered` ab (`anvil/core/mod_deployer.py:1044-1046`, unverändert) — der geplante Test T4 (nummerierte Dublette daneben) fehlt |
| 15 | Nach `purge` ist die Datei weg | **ERFÜLLT (durch Bauart), NICHT GETESTET** | `purge()` räumt über die `link`-Werte des Manifests, nicht über den Namen. Kein Test dazu |
| 16 | STALKER-2-Gespann behält alle drei Endungen | **ERFÜLLT** | `tests/test_dateinamen_ausnahme.py:119-137` |
| 17 | Alle neuen `tr()`-Schlüssel in allen 7 Locales | **ERFÜLLT** | eigene Nachzählung über alle 7 Dateien: `context.keep_file_names`, `tooltip.keep_file_names`, `log.keep_file_names_on`, `log.keep_file_names_off` → überall vorhanden. Test `tests/test_dateinamen_ausnahme.py:362-370` |
| 18 | Drei genannte Bestandstests unverändert grün | **ERFÜLLT** | `git diff tests/` zeigt keine dieser drei Dateien; alle grün im Gesamtlauf |
| 19 | Neue Tests T1–T11 grün, jede Mutationsprobe rot | **TEILWEISE** | Gebaut sind T1, T2, T3, T5, T6, T8, T10 (siehe 2.2). **T4, T7, T9 fehlen.** Mutationsprobe zu T1/T2 selbst nachgewiesen (Abschnitt 5) |
| 20 | Kein Spiel-Plugin geändert | **ERFÜLLT** | `git status` listet keine Datei aus `anvil/plugins/` |
| 21 | `./restart.sh` startet ohne Fehler | **NICHT GEPRÜFT** | Ich habe die App nicht gestartet (Prüfauftrag = nur lesen). Ersatzprüfung: `import anvil.mainwindow, anvil.core.deploy_rules, anvil.core.load_order_scope, anvil.widgets.settings_dialog, anvil.dialogs.mod_detail_dialog` → **IMPORT OK**, kein `ImportError`/`NameError` |

### 2.2 Die geplanten Tests T1–T11

| T | Inhalt | gebaut? | Stelle |
|---|---|---|---|
| T1 | Ausgenommene `.archive` ohne Präfix | ja | `tests/test_dateinamen_ausnahme.py:66` |
| T2 | Andere Mod behält ihren Zähler | ja | `:66-80`, `:96-106` |
| T3 | Kein `unnumbered` im Manifest | ja | `:143` |
| T4 | `_drop_superseded_numbered` löscht die ausgenommene Datei nicht | **nein** | — |
| T5 | `meta.ini`-Rundlauf über `scan_mods_directory` | ja | `:191` |
| T6 | `""`/fehlend/`"0"` → `False` | ja | `:201`, `:204` |
| T7 | Mod-Ordner umbenannt → Merker bleibt | **nein** | — |
| T8 | STALKER-2-Gespann gemeinsam | ja | `:119` |
| T9 | Spiel ohne Nummerierung: kein Fehler | **nein** (nur der Menü-Vorbau `:309`) | — |
| T10 | Panel reicht die Menge weiter | ja | `:252` |
| T11 | 7 Locale-Dateien | ja | `:362` |
| — | Zusatz: Groß/Kleinschreibung | über Plan hinaus | `:109` |
| — | Zusatz: Trenner bekommt den Merker nie | über Plan hinaus | `:224` |
| — | Zusatz: `write_meta_ini` mischt, Merker überlebt | über Plan hinaus | `:213` |
| — | Zusatz: Hauptfenster sammelt nur echte Mods | über Plan hinaus | `:273` |

### 2.3 Die Verbotsliste aus Plan 2 (Abschnitte 5.2 und 7)

| Verbot | Eingehalten? | Beleg |
|---|---|---|
| `pak_order_allows()` unverändert | **JA** | `anvil/core/mod_deployer.py:240-254`, von keinem Diff-Hunk berührt; die neue Bedingung steht **davor** (`:775-779`) |
| `load_order_index()` unverändert | **JA** | `:227-237`, kein Hunk |
| `pak_load_order_name()` unverändert | **JA** | `:201-224`, kein Hunk |
| `_drop_superseded_numbered()` unverändert | **JA** | `:1020 ff.`, kein Hunk |
| `_write_archive_load_order()` unverändert | **JA** | `:1079 ff.`, kein Hunk |
| Alle Spiel-Plugins unverändert | **JA** | `git status` zeigt nichts unter `anvil/plugins/` |
| Kein BG3-Code | **JA** | weder `bg3_mod_list_model.py` noch `lspk_parser.py` noch `bg3_mod_handler.py` in `git status` |
| Collections tragen den Merker nicht mit | **JA** | `anvil/core/collection_io.py` ist in **diesem** Arbeitsstand nicht geändert |

**Keine Grenze überschritten.**

---

## 3. Plan 3 — `docs/anvil-plan-reihenfolge-anzeige.md`

### 3.1 Die vier empfohlenen Anzeigen (a + b + c + d)

| Anzeige | gebaut? | Beleg |
|---|---|---|
| **a) Tooltip auf dem Spaltenkopf „Priorität"** | **JA** | `anvil/models/mod_list_model.py:782-798` (`set_load_order_plugin` + `headerData` mit `ToolTipRole`), gefüttert in `anvil/mainwindow.py:1963-1965` |
| **b) Zeile unter der Mod-Liste** | **JA** | `anvil/mainwindow.py:307-322` (Widget außerhalb des Splitters), `:2193-2208` (`_update_order_hint`), `:2188-2191` (`_hide_order_hint`) |
| **c) Konflikte-Bereich des Detail-Dialogs** | **JA** | `anvil/dialogs/mod_detail_dialog.py:1512-1522` |
| **d) Diagnose-Bereich** | **JA** | `anvil/core/diagnostics.py:278-300`, gefüttert über `anvil/widgets/settings_dialog.py:1537` + `_diag_game_plugin` (`:1540-1552`) |

**Alle vier gebaut. Keine fehlt.**

### 3.2 Akzeptanz-Kriterien (Abschnitt 6, 20 Punkte)

| # | Kriterium | Einstufung | Beleg |
|---|---|---|---|
| 1 | Skyrim SE: Tooltip enthält „nur über lose Dateien" | **ERFÜLLT** | `anvil/core/load_order_scope.py:110` → `order_scope.not_numbered` (`anvil/locales/de.json:1484`); Test `tests/test_reihenfolge_anzeige.py:167-178` prüft „lose" |
| 2 | Cyberpunk: Tooltip nennt `archive/pc/mod` | **ERFÜLLT** | Tests `:35-39`, `:116-118`, `:131-134` |
| 3 | Stalker 2: `~mods` freigegeben **und** `LogicMods` als nicht freigegeben | **ERFÜLLT** | `anvil/core/load_order_scope.py:68-81` (`rest`); Test `:51-57` |
| 4 | Bethesda-Satz bei Skyrim/FO4/Starfield, nicht bei CP/Stalker | **ERFÜLLT** | `anvil/core/load_order_scope.py:66`, `:112-113`; Tests `:66-73`, `:121-128` |
| 5 | Spielwechsel → Tooltip wechselt mit | **ERFÜLLT** | `set_load_order_plugin` + `headerDataChanged.emit` (`anvil/models/mod_list_model.py:782-789`); Test `:204-218` |
| 6 | Stellar Blade: Hinweiszeile sichtbar | **ERFÜLLT** | `anvil/mainwindow.py:2199-2208`; Test `:306-311` |
| 7 | Cyberpunk/Stalker 2: keine Hinweiszeile | **ERFÜLLT** | `anvil/mainwindow.py:2200-2202` über `archive_folgen_der_liste` (`load_order_scope.py:42-45`); Test `:314-319` |
| 8 | „×" blendet aus und bleibt nach Neustart aus | **ERFÜLLT** | `anvil/mainwindow.py:2188-2191` schreibt in `QSettings`; `:2204-2206` liest zurück; Tests `:322-326`, `:329-337` |
| 9 | Weggeklickt bei Spiel A, erscheint trotzdem bei Spiel B | **ERFÜLLT** | Schlüssel enthält `GameShortName` (`anvil/mainwindow.py:2184-2186`); Test `:340-343` |
| 10 | Tooltip bleibt, auch wenn die Zeile weg ist | **ERFÜLLT** | Getrennte Wege: `headerData` liest das Plugin, nicht den QSettings-Merker (`mod_list_model.py:791-795`) |
| 11 | Detail-Dialog: Zusatzsatz nur ohne Nummerierung | **ERFÜLLT** | `anvil/dialogs/mod_detail_dialog.py:1517-1521`; Test `:248-252` prüft die Weiche (GUI-Dialog selbst nicht automatisiert — so vom Plan vorgesehen) |
| 12 | Diagnose-Export enthält einen Ladereihenfolge-Block | **ERFÜLLT** | `anvil/core/diagnostics.py:284-299` (`[Ladereihenfolge]`); Tests `:224-236` |
| 13 | `describe_load_order(None)` ohne Absturz, keine Hinweiszeile | **ERFÜLLT** | `anvil/core/load_order_scope.py:60-61`; Test `:76-80`. **Namensabweichung:** die Funktion heißt gebaut `scope_for` |
| 14 | Spaltenköpfe unverändert, VERSALIEN im modernen Theme | **ERFÜLLT** | `DisplayRole`-Zweig unangetastet (`mod_list_model.py:796-798` fällt in den alten Code); Test `:192-201` |
| 15 | 8 neue Schlüssel in allen 7 Locales, `{dirs}`/`{rest}` überall gleich | **TEILWEISE** | 6 `order_scope`-Schlüssel + `mod_detail.archive_winner_unsure` sind in allen 7 Dateien (Tests `:145-161`, eigene Nachzählung bestätigt). **Aber:** der geplante 8. Schlüssel `order_scope.dismiss` heißt gebaut `order_scope.hide` und wird **nirgends benutzt** — siehe 4.2 |
| 16 | `anvil/core/mod_deployer.py` und `anvil/plugins/games/` unverändert | **TEILWEISE** | `anvil/plugins/games/` unverändert ✅. `mod_deployer.py` **ist** geändert — aber ausschließlich durch Plan 1 (Regelumzug) und Plan 2 (Merker). **Keine** Zeile der Anzeige-Arbeit steht darin: `load_order_scope` wird im Deployer nirgends importiert. Formal verletzt, sachlich sauber getrennt |
| 17 | Kein `setStyleSheet()` im neuen Hinweis-Widget, Optik aus `#orderScopeHint` | **TEILWEISE** | Kein `setStyleSheet()` im Hinweis-Widget ✅ (`anvil/mainwindow.py:307-322`). **Aber:** es wird **kein `setObjectName("orderScopeHint")`** vergeben und es gibt **keinen QSS-Eintrag** — `grep -rn orderScopeHint anvil/styles/ anvil/mainwindow.py` → kein Treffer. Die Zeile erbt nur das allgemeine Aussehen |
| 18 | Mutationsproben 1, 6, 8, 12 machen je einen Test rot | **TEILWEISE** | Probe 8 (`headerData` zurückgesetzt) von mir **nachgewiesen rot** (Abschnitt 5.3). Proben 1, 6, 12 nicht ausgeführt; die zugehörigen Tests existieren (`:35`, `:83`, `:145`) und würden greifen — belegt ist das nicht |
| 19 | Vier Bestandstests unverändert grün | **ERFÜLLT** | keine der vier Dateien steht in `git diff tests/`; alle grün im Gesamtlauf |
| 20 | `restart.sh` ohne Fehler | **NICHT GEPRÜFT** | wie Plan 2 #21 — Ersatz: Import-Check bestanden |

### 3.3 Die Verbotsliste aus Plan 3 (Abschnitt 7)

| Verbot | Eingehalten? |
|---|---|
| Keine Änderung am Deploy-Weg | **formal nein, sachlich ja** — siehe Kriterium 16 |
| Kein Plugin in `anvil/plugins/games/` | **JA** |
| Kein BG3-Code | **JA** — `bg3_mod_list_model.py`, `bg3_mod_list.py`, `game_baldursgate3.py`, `bg3_mod_handler.py` stehen nicht in `git status`; die Hinweiszeile sitzt außerhalb des `QStackedWidget` (`anvil/mainwindow.py:322`), genau wie geplant |
| Nichts rund um „Dateinamen nicht ändern" | **formal nein** — das wurde gebaut, aber als **Plan 2**, nicht als Plan-3-Arbeit. Die Dateien überschneiden sich nur in `mod_list_model.py` und `mainwindow.py`, an getrennten Stellen |
| Keine Kopplung der Bethesda-Plugin-Reihenfolge an die Mod-Liste | **JA** — `load_order_scope.py` liest `PluginLoadOrderFormat` nur, um einen Satz auszugeben |

---

## 4. Lücken und Funde

### 4.1 Nicht gebaut, obwohl geplant

1. **Mehrfachauswahl beim Merker** (Plan 2, Kriterium 12; Abschnitt 4.2 Zeilen 424–428).
   Der Menüpunkt entsteht nur bei `single` (`anvil/mainwindow.py:5053`);
   `_toggle_keep_file_names` (`:2226`) verarbeitet genau einen Namen.
   Wer mehrere Mods markiert, sieht den Eintrag gar nicht.
   **Größte inhaltliche Lücke der drei Pläne.**
2. **Drei geplante Tests fehlen** (Plan 2, Abschnitt 5.5):
   T4 (`_drop_superseded_numbered` räumt die ausgenommene Datei nicht weg),
   T7 (Ordner umbenannt → Merker bleibt), T9 (Spiel ohne Nummerierung, kein
   Fehler im Deploy-Weg). Damit sind Kriterium 14 und 15 (purge) nur
   „durch Bauart" belegt, nicht gemessen.
3. **QSS-Objektname `#orderScopeHint` fehlt** (Plan 3, Kriterium 17,
   Abschnitt 4.1 und 4.6). Kein `setObjectName`, kein Eintrag in
   `anvil/styles/`. Das Verbot `setStyleSheet()` ist eingehalten, die
   vorgeschriebene Optik-Quelle existiert aber nicht.
4. **`order_scope.hide` (geplant: `dismiss`) ist eine tote Übersetzung.**
   Der Schlüssel liegt in allen 7 Locales, wird aber nirgends gelesen
   (`grep -rn "order_scope.hide" anvil/` → kein Treffer). Der „×"-Knopf
   (`anvil/mainwindow.py:314-316`) bekommt **kein** `setToolTip`.
   Plan 3 Abschnitt 4.4 hatte ihn als Tooltip vorgesehen.
5. **Kein Leeren beim Instanz-Reset** (Plan 3, Abschnitt 4.1:
   „Beim Instanz-Reset (`mainwindow.py:1789-1810`) leeren").
   Der Fehlzweig `if not data:` (`anvil/mainwindow.py:1806-1825`) setzt
   `self._current_plugin = None` (`:1814`), ruft aber weder
   `set_load_order_plugin(None)` noch `_update_order_hint()`.
   Folge: Nach einer fehlgeschlagenen Instanz bleiben Tooltip und
   Hinweiszeile des **vorigen** Spiels stehen.
6. **`meta.ini` bekommt `"0"` statt `""`** (Plan 2, Kriterium 4).
   Wirkung korrekt, Wortlaut nicht.

### 4.2 Gebaut, aber in keinem Plan so vorgesehen

1. **`mod_detail.archive_winner_numbered`** — ein **neunter** Schlüssel, den
   kein Plan nennt (`anvil/locales/de.json:996`). Zugleich wurde der
   Bestandsschlüssel `mod_detail.archive_conflicts_hint` **gekürzt**: der
   Halbsatz „Grün = dieses Archiv gewinnt." ist herausgelöst
   (`de.json:994`). Plan 3 Abschnitt 3.2 sagte ausdrücklich: „Bei Spielen
   mit Nummerierung bleibt der heutige Satz unverändert stehen."
   Sichtbar für den Nutzer ist das Ergebnis identisch (beide Teile werden
   in `mod_detail_dialog.py:1518-1521` wieder zusammengesetzt), aber der
   Bestandstext wurde entgegen dem Plan angefasst.
   **Bewertung: saubere Lösung, aber ungeplant.**
2. **Namensabweichungen zu Plan 3, Abschnitt 4.1/4.2** — geplant war
   `LoadOrderScope`, `describe_load_order()`, `scope_text()` und
   `tests/test_load_order_scope.py`; gebaut wurde `OrderScope`,
   `scope_for()`, `scope_saetze()`, `scope_tooltip()` und
   `tests/test_reihenfolge_anzeige.py`. Rein kosmetisch, aber wer nach den
   Plannamen sucht, findet nichts.
3. **Bethesda-Erkennung anders als geplant.** Plan 3 Abschnitt 4.2
   verlangte `plugin.has_plugins_txt()` mit `getattr`/`callable`-Absicherung.
   Gebaut ist der direkte Attributvergleich
   `getattr(plugin, "PluginLoadOrderFormat", "") == "asterisk"`
   (`anvil/core/load_order_scope.py:66`). Wertgleich (die Methode tut in
   `base_game.py:571-573` genau das), aber die Kapselung ist umgangen:
   überschriebe ein Plugin `has_plugins_txt()`, ginge das hier verloren.
4. **`ModDeployer.keeps_file_names()`** (`anvil/core/mod_deployer.py:376-378`)
   — öffentliche Methode, die Plan 2, Abschnitt 5.2, nicht aufführt
   (dort standen nur Feld und Setter). Harmlos, wird von
   `tests/test_dateinamen_ausnahme.py:244` genutzt.
5. **Tooltip auch auf `COL_MARKERS`** (`anvil/models/mod_list_model.py:403-405`).
   Plan 2, Abschnitt 4.4, sah ihn nur auf `COL_NAME` vor. Sinnvolle
   Erweiterung — wer auf das Zeichen zeigt, will wissen, was es bedeutet.
6. **`_liste()`-Normalisierung mit `strip("/")`** (`load_order_scope.py:48-51`)
   verändert die Anzeige gegenüber Plan 3 Abschnitt 4.2 („Für die Anzeige
   wird die **Originalschreibweise** aus `GameModDirs` ausgegeben"):
   Backslashes werden zu Schrägstrichen umgeschrieben, auch im Rest-Text.
   Bei den heutigen Plugins folgenlos (alle nutzen Schrägstriche).

### 4.3 Was ausdrücklich sauber ist

- **Kein einziger Test wurde weichgeklopft.** Alle 9 Test-Hunks sind
  Attrappen-Erweiterungen; keine Zusicherung wurde gelockert oder entfernt.
- **Keine der fünf durch Plan 2 geschützten Funktionen** wurde angefasst.
- **Kein Spiel-Plugin**, **kein BG3-Code**, **kein `ba2_packer.py`**,
  **kein `plugins_txt_writer.py`**, **kein `set_separator_deploy_paths`**.
- Die kritische Reihenfolge aus Plan 1 (Zielverteilung **vor**
  Data-Präfix) ist eingehalten **und** durch einen neuen Test festgenagelt
  (`tests/test_deploy_regeln.py:326-354`) — genau die Lücke, die Plan 1
  als Hauptrisiko benannte.

---

## 5. Mutationsproben (drei, selbst ausgeführt)

Vorgehen: Datei gesichert nach `/home/mob/.claude/jobs/ddce5997/tmp/`,
mutiert, Test gefahren, Original zurückkopiert, Prüfsumme verglichen.

### 5.1 Probe A — Plan 1, `strip_root` (die ungeschützteste Regel des Umbaus)

Mutation: in `anvil/core/deploy_rules.py:62-64` den `root/`-Abzug entfernen,
`strip_root` gibt `rel` unverändert zurück.

```
FAILED tests/test_deploy_regeln.py::test_root_ordner_wird_abgezogen
1 failed, 16 passed
```

**Ergebnis: rot.** Genau der Fall, den Plan 1, Abschnitt 5, als
„**ungeschützt** → Schritt 0, Fall 4" führte, ist jetzt abgesichert.
Datei danach wiederhergestellt (`md5 0091a674…`, unverändert).

### 5.2 Probe B — Plan 2, die eine neue Bedingung im Deployer

Mutation: in `anvil/core/mod_deployer.py:775-779` den Zusatz
`and not self.keeps_file_names(mod_name)` streichen — also der Zustand
vor dem Feature.

```
FAILED test_ausgenommene_mod_behaelt_ihren_namen
FAILED test_die_zahlen_der_anderen_verschieben_sich_nicht
FAILED test_gross_und_kleinschreibung_egal
FAILED test_gespann_wird_gemeinsam_ausgenommen
FAILED test_kein_unnumbered_im_manifest
FAILED test_setter_erreicht_einen_laufenden_deployer
6 failed, 12 passed
```

**Ergebnis: rot, sechsfach.** Deckt die Plan-Proben zu T1, T2, T3 und T8 ab.
Datei wiederhergestellt (`md5 1c70d014…`).

### 5.3 Probe C — Plan 3, Mutationsprobe Nr. 8 aus Abschnitt 4.5

Mutation: in `anvil/models/mod_list_model.py:791-795` den
`ToolTipRole`-Zweig auf `return None` zurücksetzen (alter Zustand).

```
FAILED test_spaltenkopf_liefert_einen_tooltip
FAILED test_tooltip_folgt_dem_spielwechsel
2 failed, 30 passed
```

**Ergebnis: rot.** Plan 3, Kriterium 18, verlangt genau diesen Nachweis für
Probe 8 — hiermit erbracht. Datei wiederhergestellt (`md5 81972c35…`).

### 5.4 Nachweis der Wiederherstellung

`git status --short` nach den Proben ist **zeichengleich** mit dem Stand vor
den Proben: dieselben 18 geänderten und 9 unverfolgten Einträge, keine
zusätzliche Datei, keine fehlende. Alle drei Prüfsummen stimmen mit den
vor der Mutation gezogenen überein.

---

## 6. Gesamtbild

| Plan | Kriterien | ERFÜLLT | TEILWEISE | NICHT ERFÜLLT | nicht geprüft |
|---|---|---|---|---|---|
| 1 — deploy_rules | 6 Schritte + Erfolgskriterium + 5 Grenzen | 12 | 0 | 0 | 0 |
| 2 — Dateinamen | 21 | 16 | 3 | 1 | 1 |
| 3 — Anzeige | 20 | 14 | 5 | 0 | 1 |

**Plan 1 ist vollständig und diszipliniert umgesetzt** — inklusive des harten
Kriteriums „vorhandene Tests unverändert grün". Der KRITISCHE Fund, nach dem
gesucht werden sollte (ein Test, der angepasst wurde, damit er nicht mehr rot
ist), **existiert nicht**.

**Plan 2 hat eine echte Funktionslücke:** die Mehrfachauswahl (Kriterium 12).
Dazu fehlen drei geplante Tests.

**Plan 3 hat alle vier Anzeigen gebaut**, lässt aber drei kleine
Zusagen offen: QSS-Objektname, der tote `hide`-Schlüssel samt fehlendem
Tooltip am „×", und das Leeren beim Instanz-Reset.

---

## UNSICHER

1. **`restart.sh` wurde nicht ausgeführt.** Plan 2, Kriterium 21, und Plan 3,
   Kriterium 20, verlangen einen fehlerfreien Start. Ich habe stattdessen nur
   die Module importiert (`IMPORT OK`). Ein Fehler, der erst beim Aufbau der
   Oberfläche auftritt — etwa ein Layout-Problem der neuen Hinweiszeile in
   `mainwindow.py:307-322` — bliebe dabei unsichtbar. **Muss von Hand
   nachgeholt werden.**
2. **Die drei GUI-Kriterien sind nicht am laufenden Programm belegt:**
   Plan 3, Kriterium 1–5 (zeigt `QHeaderView` den Tooltip wirklich an?) und
   Plan 2, Kriterium 1/5 (erscheint der Haken?). Der Plan selbst nannte das
   unter „UNSICHER Nr. 1" als **erste** Handprobe. Belegt ist nur, dass
   `headerData` den Text liefert.
3. **Kriterium 15 (purge) und 14 (`_drop_superseded_numbered`)** habe ich
   nicht selbst gefahren, sondern aus dem unveränderten Code gefolgert
   (`mod_deployer.py:1044-1046`). Ein Test dazu fehlt in beiden Richtungen.
4. **Plan-3-Mutationsproben 1, 6 und 12** habe ich nicht ausgeführt, nur
   Probe 8. Kriterium 18 verlangt „nachgewiesen, nicht behauptet" für alle
   vier — für drei davon steht der Nachweis aus.
5. **`001Bericht/` und `docs/anvil-plan-reihenfolge-ehrlich.md`** liegen als
   unverfolgte Einträge im Arbeitsstand. Ob sie zu dieser Arbeit gehören
   oder Altbestand sind, habe ich nicht geklärt — Code enthalten sie nicht.
6. **Ob `order_scope.hide` bewusst ohne Nutzer eingebaut wurde** (etwa als
   Vorbereitung) oder schlicht vergessen ist, steht nirgends. Ich habe nur
   belegt, dass ihn kein Code liest.
7. **Die Wirkung von `_liste()`s Normalisierung auf die Anzeige** habe ich
   nur am heutigen Plugin-Bestand geprüft (alle nutzen Schrägstriche). Ob
   ein künftiges Plugin mit Backslashes dadurch einen entstellten Ordner
   angezeigt bekäme, ist ungetestet.
