# Review: Punkte 2, 3, 5 (Auffang-Trenner, verirrte Presets, Archiv-Konflikte)

Reviewer: Kimi (Code-Review, nur lesend)
Stand: uncommitteter Arbeitsbaum, `git diff` vom 2026-08-13
Testsuite zum Review-Zeitpunkt: **5 failed, 723 passed, 1 skipped** (siehe KRITISCH 1)

**Hinweis vorab:** Der Arbeitsbaum wurde *während* des Reviews weiterverändert
(Diff wuchs von 982 auf 1034 eingefügte Zeilen; `anvil/core/instance_manager.py`
kam dazu, `_report_stray_presets` wurde auf einen Merker pro Instanz umgebaut,
`QTimer.singleShot` wurde durch `self._tidy_timer` ersetzt). Dieser Bericht
bezieht sich auf den **Endzustand**, den ich zuletzt gelesen habe.

---

## KRITISCH

### K1 — Der Arbeitsbaum ist rot: 5 Tests schlagen fehl

Konkret fehlschlagend (gelaufen mit `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q`):

- `tests/test_preset_bereich.py::test_split_nimmt_presets_aus_der_liste`
- `tests/test_preset_bereich.py::test_split_laesst_alles_stehen_wenn_es_keine_presets_gibt`
- `tests/test_preset_bereich.py::test_split_bei_spiel_ohne_presets`
- `tests/test_preset_bereich.py::test_split_ohne_index_blendet_nichts_aus`
- `tests/test_verirrte_presets.py::test_meldung_ohne_glocke_stuerzt_nicht_ab`

Ursache: `_report_stray_presets` greift jetzt auf `self.instance_manager`
(`anvil/mainwindow.py:2498`) und auf `self._stray_preset_namen` als **dict**
(`.get(inst)`, `anvil/mainwindow.py:2500`; Initialisierung als dict in
`anvil/mainwindow.py:416`). Die Test-Fixtures wurden nicht nachgezogen:
`tests/test_preset_bereich.py:400` und `tests/test_verirrte_presets.py:261`
setzen weiterhin `self._stray_preset_namen = set()` und haben kein
`instance_manager`-Attribut → `AttributeError` bzw. `'set' object has no
attribute 'get'`.

Der Produktivcode selbst ist in sich stimmig (dict-Initialisierung in
`__init__`, `mainwindow.py:416`; der alte Reset `= set()` beim Instanzwechsel
ist entfernt). Es sind die Fixtures, die hinterherhinken. Trotzdem: in diesem
Zustand darf nicht committet werden — die Suite ist rot, und ausgerechnet
`test_meldung_ohne_glocke_stuerzt_nicht_ab` dokumentiert einen früheren
Produktionsabsturz, dessen Regressionsschutz jetzt selbst bricht.

---

## WICHTIG

### W1 — Storage-Migration schreibt einen v3-Index ohne Archiv-Prüfsummen; Archiv-Konflikte fallen danach still aus

Der Reindex nach einer Instanz-Umzugsmigration baut den Index **ohne**
Spiel-Plugin:

- `anvil/mainwindow.py:1198`: `index = ModIndex(instance_path, mods_path=mods_path)` — kein `game_plugin`.

Folgekette:

1. Dieser Index schreibt `.modindex.json` mit `version: 3`, aber **ohne**
   `archives`-Schlüssel (`_save_cache` lässt leere Archive weg,
   `anvil/core/modindex.py:460-461`).
2. Beim nächsten Laden erzeugt das Hauptfenster den Index *mit* Plugin
   (`anvil/mainwindow.py:1997`-Bereich), `rebuild()` lädt den Cache und
   überspringt jede Mod mit passendem Fingerprint (`anvil/core/modindex.py:163-165`).
   Ein fehlender `archives`-Schlüssel wird beim Laden still als `{}`
   akzeptiert (`anvil/core/modindex.py:436-441`) — „nie gelesen" und „hat
   keine Archive" sind im Cache nicht unterscheidbar.
3. `get_archives()` liefert dauerhaft `{}` (`anvil/core/modindex.py:198-206`),
   `_archive_conflicts` findet nichts — bis sich zufällig eine Mod ändert.

Vor Version 3 war das harmlos (es gab keine Archive im Index). Jetzt verliert
Punkt 2/3 nach jeder Storage-Migration lautlos seine Wirkung. Kein Test deckt
diesen Weg ab. Denkbare Gegenmittel: der Migrations-Reindex bekommt das Plugin
mit, oder der Cache vermerkt, mit welcher Archiv-Fähigkeit er gebaut wurde.

---

## A) Rückwärtskompatibilität — geprüft, überwiegend sauber

**Instanz ohne Auffang-Trenner:** sauber. `_catch_all_separator()` liefert
`""` (`anvil/mainwindow.py:2222-2231`), `catch_all_position` fällt auf
`len(order)` zurück (`anvil/core/mod_list_io.py:319-320`) — exakt das alte
Verhalten. Der Trenner entsteht erst lazy beim ersten Zugang
(`_ensure_catch_all_separator`, `anvil/mainwindow.py:2244-2285`) und wird
sowohl in die modlist als auch in `active_mods.json` und die Instanz-Konfig
geschrieben. Abgedeckt durch `test_ohne_sammler_bleibt_es_beim_alten_verhalten`
(`tests/test_auffang_trenner.py:95-102`).

**Altsystem ohne globale `.profiles/modlist.txt`:** sauber.
`_add_mod_to_order` fällt auf `add_mod_to_modlist` im Profil zurück
(`anvil/mainwindow.py:2405-2406`), der Installationspfad hat ebenfalls einen
Legacy-Zweig (`anvil/mainwindow.py:4386-4390`).
`_offer_tidy_catch_all` liest die globale Liste, die bei Fehlen `[]` liefert
(`anvil/core/mod_list_io.py:261-263`) → kein Fund → kein Dialog. Der
Auffang-Trenner wird nirgends erzwungen, wo es die globale Liste nicht gibt.

**Cache-Version 2 → 3:** sauber. Versionsungleichheit verwirft den ganzen
Cache (`anvil/core/modindex.py:407-410`) und baut neu — getestet durch
`test_alter_cache_wird_verworfen` (`tests/test_archiv_konflikte.py:257-273`).
**Halb geschriebene `.modindex.json`:** sauber. `json.JSONDecodeError` wird
gefangen, Cache verworfen, Neuaufbau (`anvil/core/modindex.py:395-405`).
Einzige verbleibende Lücke in diesem Bereich ist W1 oben.

**Instanz-Schlüssel werden persistiert:** `save_instance` hat eine
Allowlist; `catchall_separator` und `catchall_tidy_asked` sind aufgenommen
(`anvil/core/instance_manager.py:397-400`). Die Leseseite ist generisch
(`_read_ini`, `anvil/core/instance_manager.py:593-609`). Wäre das vergessen
worden, hätte die „Nein"-Antwort des Aufräum-Dialogs keinen Neustart
überlebt — im geprüften Endzustand ist es drin.

**Neue Parameter an bestehenden Funktionen — alle Aufrufer geprüft:**

| Funktion | Aufrufer | Stand |
|---|---|---|
| `scan_mods_directory(..., catch_all="")` | `anvil/mainwindow.py:2010-2016` (mit `instance_name`-Übergabe), `anvil/mainwindow.py:7779-7785`, `tests/test_custom_instance_paths.py:36` (Default) | ok |
| `ModIndex(..., game_plugin=None)` | `anvil/mainwindow.py:1198` (siehe **W1**), `anvil/mainwindow.py:1997`-Bereich (mit Plugin), alle Tests mit Default | ok bis auf W1 |
| `scan_conflicts(..., archive_hashes=None)` | `anvil/mainwindow.py:3343-3346` (BG3-Zweig, bewusst ohne — BG3 kennt keine `GameArchiveSuffixes`), `anvil/mainwindow.py:3353-3356` (mit), `anvil/dialogs/mod_detail_dialog.py:1363-1366` (mit) | ok |
| `ModDetailDialog.__init__(..., mod_index=None, archive_hashes=None)` | einziger Aufrufer `anvil/mainwindow.py:4581-4592` | ok |
| `apply_collection(..., catch_all="")` | `anvil/mainwindow.py:6483`, `tests/test_instance_storage_offline.py:93`, `tests/test_custom_instance_paths.py:123` (Default = altes Verhalten) | ok |
| `ModRow.__init__(..., has_stray_preset=False)` | `__slots__` erweitert (`anvil/models/mod_list_model.py:59`), `mod_entry_to_row` reicht durch (`:123`) | ok |

Alle neuen Parameter stehen am Ende und haben Defaults — kein bestehender
Aufruf bricht.

---

## B) Die Prioritätsregel — nachgerechnet, stimmig

CLAUDE.md (Zeilen 149-156): erste Mod in modlist.txt = höchste Priorität;
der Deployer dreht intern um, „last wins".

**Durchgerechnetes Beispiel.** modlist.txt / GUI: `[A, B]` — A oben, A hat
höchste Priorität und muss im Spiel gewinnen. Beide Mods bringen ein Archiv
mit, beide Archive enthalten dieselbe Spieldatei (Prüfsumme `h`).

1. `_conflict_mod_list` baut `[A, B]` und dreht um → `[B, A]`
   (`anvil/mainwindow.py:3308-3322`, `all_mods.reverse()` auf `:3321`).
2. `_archive_conflicts` füllt die Besitzerliste in dieser Reihenfolge:
   `besitzer[h] = [("B", archB), ("A", archA)]`
   (`anvil/core/conflict_scanner.py:237-241`).
3. Paarbildung: `a = (B, …)` (früher), `b = (A, …)` (später) →
   `winner = b[0] = "A"` (`anvil/core/conflict_scanner.py:248-261`).
4. Dieselbe Datei als lose Datei: `winner = owners[-1] = "A"`
   (`anvil/core/conflict_scanner.py:207`).
5. Deployer rollt umgekehrt aus, A zuletzt → A liegt im Spiel.

Anzeige (lose + Archiv) und Deploy nennen denselben Gewinner. **Stimmt.**
Belegt auch durch `test_reihenfolge_entscheidet_den_gewinner`
(`tests/test_archiv_konflikte.py:90-99`) und
`test_konfliktanzeige_nennt_die_obere_mod`
(`tests/test_konflikt_reihenfolge.py:94-97`).

Nebenbefund: `mod_list_io.py:99` — der Docstring von `add_mod_to_modlist`
sagte fälschlich „highest priority", wurde auf „lowest priority" korrigiert.
Guter Fang, die alte Aussage widersprach CLAUDE.md.

---

## C) Wechselwirkungen der drei Punkte — geprüft, keine Beißerei gefunden

- **Auffang-Trenner × Presets-Bereich:** Der Presets-Bereich ist
  inhaltsbasiert (`_split_presets`, `anvil/mainwindow.py:2624-2643`), nicht
  positionsbasiert — wohin der Auffang-Trenner Neuzugänge setzt, ändert am
  Presets-Bereich nichts. Umgekehrt stört der Presets-Bereich die
  Auffang-Logik nicht: `catch_all_position` arbeitet auf der rohen
  Namensliste.
- **Aufräum-Dialog:** verschiebt nur Einträge, die weder Presets
  (`_preset_namen`) noch Frameworks (`is_direct_install`) sind
  (`anvil/mainwindow.py:2317-2330`). Die Verschiebung selbst geht über
  `catch_all_position` (`anvil/mainwindow.py:2364-2368`) — Ziel und
  Dialogtext nutzen denselben Trennernamen (`separator_label`,
  `anvil/core/mod_list_io.py:294-302`).
- **Fremde Mods (`is_foreign`):** stehen nicht in der modlist (werden beim
  Schreiben ausgefiltert, `anvil/mainwindow.py:2954`), der Aufräum-Dialog
  kann sie daher gar nicht anfassen. Sie werden optisch ans Ende gehängt
  (`anvil/mainwindow.py:2029`) und landen damit unter dem letzten Trenner —
  jetzt „Nicht einsortiert" statt „Presets". Gewollter Nebeneffekt.
- **Verirrte Presets × Trenner:** Eine Mod mit verirrtem Preset ist per
  `is_preset_mod` *kein* Preset-Mod, bleibt also in der Hauptliste, bekommt
  Tooltip und Kontextmenü. Nach `fix_stray_path` wird sie beim nächsten
  Scan zur Preset-Mod und wandert in den Bereich — nachgewiesen durch
  `test_nach_der_reparatur_ist_es_ein_preset_mod`
  (`tests/test_verirrte_presets.py:141-155`). Kohärent.
- **Glocke vor Instanzaufbau:** `NotificationCenter` steht vor
  `_check_first_start()` (`anvil/mainwindow.py:485-486` vs `:497`), per Test
  abgesichert (`test_glocke_steht_vor_dem_instanz_aufbau`,
  `tests/test_verirrte_presets.py:270-281`).
- **Dialog-Stapelung:** der Aufräum-Dialog läuft über einen einzigen
  Single-Shot-Timer (`anvil/mainwindow.py:490-492`, gestartet auf `:2056`) —
  zwei schnelle Instanzwechsel stapeln keine zwei Dialoge.

---

## D) Was fehlt — Schreibstellen der modlist.txt, alle geprüft

| Stelle | Auffang-Trenner beachtet? |
|---|---|
| Installation, globales System (`anvil/mainwindow.py:4353`, `:4378-4381`) | ja — Trenner wird vor dem Lesen angelegt, Einfügung via `catch_all_position` |
| Kontextmenü „Mod installieren" / leere Mod (`_add_mod_to_order`, `anvil/mainwindow.py:2398-2406`) | ja (bzw. Legacy-Fallback ohne globale Liste) |
| Sammlungs-Import (`anvil/core/collection_io.py:454-460`) | ja, getestet (`tests/test_auffang_trenner.py:199-227`) |
| Preset-Import (`anvil/mainwindow.py:2755-2759`) | bewusst nein — geht direkt hinter den Preset-Trenner |
| Script-Merger (`anvil/widgets/script_merger_dialog.py:537-540`) | bewusst nein — `_merged_` gehört an Position 0 (höchste Priorität) |
| `_write_current_modlist` (`anvil/mainwindow.py:2940-2958`) | schreibt die sichtbare Reihenfolge komplett — Position des Trenners bleibt erhalten |
| Neuer Trenner per Kontextmenü (`anvil/mainwindow.py:5114-5122`-Bereich) | Nutzerposition, kein Neuzugang |
| Scan erkennt Ordner ohne Listeneintrag (`anvil/core/mod_entry.py:296-310`) | ja, via `catch_all_position` |

Keine Stelle gefunden, die noch von der alten Annahme „neue Mods stehen am
Ende" ausgeht und jetzt falsch läge. Keine vergessene Aufrufstelle gefunden.

---

## E) Die Tests — echte Tests, mit konkreten Löchern

**Das ist keine Attrappe.** Alle drei Dateien testen Verhalten über das
Dateisystem bzw. echte Objekte, nicht nur Existenz. Stärken:

- `tests/test_auffang_trenner.py:105-121` enthält eine explizite
  **Mutationsprobe** (`test_mutationsprobe_sammler_ignorieren_faellt_auf`).
- `tests/test_verirrte_presets.py:183-206` beweist den Fehler und die
  Reparatur **durch den echten Deployer** hindurch (Ende-zu-Ende).
- `tests/test_archiv_konflikte.py:90-99` dreht die Liste und verlangt, dass
  sich der Gewinner mitdreht.
- Dass die Verdrahtungstests etwas taugen, hat sich live gezeigt: der Umbau
  von `_report_stray_presets` auf den Instanz-Merker ließ 5 Tests sofort rot
  werden (K1).

**Mutationen, die rot würden (Stichprobe):**

- `catch_all_position` → immer `len(order)`: `test_mutationsprobe…` +
  `test_zugang_landet_beim_sammler…` (`tests/test_auffang_trenner.py:82-92`).
- `while`-Schleife entfernt (über nächsten Trenner hinaus):
  `test_nicht_ueber_den_naechsten_trenner_hinaus` (`:46-52`).
- Neuzugänge `enabled=False`: `test_zugang_bleibt_aktiv` (`:124-138`).
- `winner = a[0]` statt `b[0]`: `test_gemeinsame_datei_wird_zum_konflikt`
  und `test_reihenfolge_entscheidet_den_gewinner`
  (`tests/test_archiv_konflikte.py:36-49, 90-99`).
- Cache-Version nicht erhöht: `test_alter_cache_wird_verworfen` (`:257-273`).
- `fix_stray_path` überschreibt statt `FileExistsError`:
  `test_belegtes_ziel_laesst_die_quelle_in_ruhe`
  (`tests/test_verirrte_presets.py:120-131`).

**Mutationen, die UNBEMERKT durchgehen:**

1. **Alle GUI-Helfer des Auffang-Trenners sind ungetestet:**
   `_ensure_catch_all_separator` (`anvil/mainwindow.py:2244-2285`),
   `_add_mod_to_order` (`:2398-2406`), `_offer_tidy_catch_all`
   (`:2299-2376`), `_follow_separator_rename` (`:2395-Bereich`) und der
   Installationspfad (`:4353-4381`). Eine Mutation wie „Trenner beim Anlegen
   oben statt unten einfügen" oder „`save_instance` vergessen" bliebe grün.
2. **Quelltext-String-Tests statt Verhaltenstests:**
   `test_hauptfenster_reicht_die_archivdaten_durch`
   (`tests/test_archiv_konflikte.py:294-305`) prüft nur
   `"archive_hashes=" in quelle` — eine Mutation zu `archive_hashes={}`
   **bleibt grün**, der String steht ja noch da. Ebenso
   `test_split_presets_ruft_die_erkennung_auf`
   (`tests/test_verirrte_presets.py:238-245`) und
   `test_kontextmenue_haengt_am_richtigen_schluessel` (`:284-291`).
3. **Die Zählung der Archiv-Konflikte in `_compute_conflict_data`
   (`anvil/mainwindow.py:3424-3446`-Bereich) ist nur per String-Test
   abgesichert.** Vertauschte wins/losses im Archiv-Zweig gingen durch —
   `test_mod_liste_bucht_den_gewinn_bei_der_oberen_mod`
   (`tests/test_konflikt_reihenfolge.py:100-105`) läuft mit
   `_mod_index=None`, also ohne Archivdaten.
4. **Der Archiv-Baum im Detaildialog ist ungetestet.** Im Gegenteil:
   `_baeume` (`tests/test_konflikt_reihenfolge.py:74-82`) besteht auf exakt
   zwei `QTreeWidget`s — ein Test mit Archiv-Konflikten (drei Bäume) müsste
   diesen Helfer erst umbauen.
5. **W1 (Migrations-Reindex ohne Plugin)** hat keinen Test.
6. `test_glocke_steht_vor_dem_instanz_aufbau` und `test_index_bekommt_das_plugin`
   sind Positions-/String-Vergleiche auf Quelltext — sie fangen Löschungen,
   aber keine inhaltlichen Fehler.

---

## KLEINIGKEITEN

- `anvil/core/conflict_scanner.py:96`: Docstring sagt „Dict with two keys" —
  tatsächlich sind es vier (`conflicts`, `ignored`, `file_owners`,
  `archive_conflicts`). War vorher schon falsch (drei), jetzt falscher.
- `anvil/core/mod_list_model.py:395-396`: ein verirrtes Preset erzeugt nur
  einen Tooltip — kein Zeichen in der Zeile selbst. Nach dem Wegklicken der
  Glocken-Meldung bleibt der Hinweis nur per Mouse-over auffindbar.
- `anvil/mainwindow.py:2531`: `_fix_stray_preset` repariert nur `pfade[0]`.
  Bei mehreren verirrten Presets in derselben Mod muss der Nutzer den
  Kontextmenüpunkt wiederholt aufrufen; der Dialog nennt jeweils nur die
  erste Datei. (Funktional korrekt, aber umständlich.)
- Diagnose-Tab: `collect_diagnostics_conflicts` (`anvil/mainwindow.py:3373-3384`)
  reicht nur `conflicts` durch — Archiv-Konflikte tauchen dort nicht auf.
  Inkonsistent zur Mod-Liste, die sie seit diesem Umbau mitzählt.
- `anvil/core/modindex.py:441`: `isinstance(w, int)` akzeptiert auch
  `True`/`False` (bool ist int) — akademisch.
- `anvil/core/modindex.py:470-473`: `_save_cache` schreibt nicht atomar.
  Der Leser fängt die halbe Datei ab (`:398-405`), daher nur eine
  Kleinigkeit — und kein neues Muster.
- Der Ordnername des Auffang-Trenners hängt von der Sprache zum
  Erstellungszeitpunkt ab (`anvil/mainwindow.py:2269`). Dank Instanz-Schlüssel
  und `_follow_separator_rename` stabil, aber zwei Instanzen in zwei
  Sprachen bekommen zwei verschiedene Trennernamen — wie bei allen
  übersetzten Trennern.

---

## UNSICHER

- **Der Baum hat sich während des Reviews verändert.** Der erste
  Diff-Snapshot (982 eingefügte Zeilen) unterschied sich vom letzten
  (1034): `instance_manager.py` kam hinzu, `_report_stray_presets` wurde auf
  den Merker pro Instanz umgebaut, `QTimer.singleShot` wurde zum
  `_tidy_timer`, der Aufräum-Dialog bekam den Framework-Ausschluss und
  `separator_label`, `_catch_all_separator` bekam den `instanz`-Parameter.
  Alle Befunde beziehen sich auf den Endzustand; Zeilennummern können durch
  weitere Edits wandern. Die 5 roten Tests (K1) können beim Lesen dieses
  Berichts bereits behoben sein.
- **Echte REDengine-Archive** konnte ich nicht prüfen — die Tests bauen
  synthetische Archive (`tests/test_redengine_archive.py:_archiv`). Ob
  `read_archive` die Prüfsummen echter Spieldateien so liest, dass zwei
  reale Mods mit derselben Datei wirklich matchen, ist hier unbelegt.
- **GUI-Abläufe** (Aufräum-Dialog, Varianten-Rückfrage, Kontextmenü) konnte
  ich headless nicht durchklicken — nur statisch gelesen.
- Ob Frameworks jemals tatsächlich in der modlist.txt unter dem
  Preset-Trenner stehen (Marcs Fall: „10 Frameworks"), konnte ich nicht
  verifizieren — der Ausschluss in `_offer_tidy_catch_all`
  (`anvil/mainwindow.py:2320-2323`) wirkt defensiv; im Kommentar heißt es,
  Frameworks stünden gar nicht in der Liste.
- **Performance** des Archiv-Lesens beim ersten v3-Aufbau (einmalig Kopf +
  Indextabelle je `.archive`) ist plausibel, aber nicht gemessen.
- `docs/anvil-agent4-review.md`, `docs/anvil-kimi-punkt2-plan.md`,
  `docs/anvil-plan-punkt3-verirrte-presets.md`,
  `docs/anvil-plan-punkt5-presets-trenner.md` und `001Bericht/` liegen
  untracked im Repo — nicht Teil dieses Reviews.
