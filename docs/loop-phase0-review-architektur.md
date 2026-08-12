# Architektur- und Konsistenz-Review — Phase 0 (Mod-Index-Aktualität)
Datum: 2026-08-12
Geprüft: `git diff HEAD` (anvil/core/modindex.py, anvil/core/mod_deployer.py,
Löschung anvil/plugins/games/game_windrose.py + game_windrose_server.py)
plus untracked `tests/test_modindex_aktualitaet.py`

Gelesen vorab: `/home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md`,
`anvil/core/modindex.py` (ganz), `anvil/core/mod_deployer.py` (relevante Teile),
`anvil/widgets/game_panel.py` (silent_deploy), `anvil/mainwindow.py` (Deploy-Pfade),
`anvil/plugins/plugin_loader.py`.

**Nicht möglich:** MO2-Referenz. `/home/mob/Projekte/mo2-referenz/` existiert auf
diesem Rechner NICHT (`ls` schlägt fehl, nur eine Windows-Installation unter
`/home/mob/modorganizer2/` mit ModOrganizer.exe, kein Quellcode). ARCHITEKTUR.md
Regel 8 („NIEMALS Code ändern ohne vorher MO2-Referenz zu lesen") kann für die
Deployer-Änderung damit von niemandem erfüllt worden sein.

---

## Findings

### [HIGH] SCHUTZREGEL berührt: mod_deployer.py wurde geändert
- Datei: anvil/core/mod_deployer.py:596-625, 872-891
- ARCHITEKTUR.md Abschnitt 5 und Regel 9.6: „Der Deploy-Mechanismus (Symlinks,
  Kopien, Manifest, Purge) darf NICHT ohne ausdrückliche Zustimmung von Marc
  geändert werden … Das schließt ein: mod_deployer.py … und alles was bestimmt
  wie Dateien ins Game-Verzeichnis gelangen."
- Die Änderung greift genau dort ein: die Dateiquelle der Deploy-Schleife und
  die Erfolgs-Semantik (`success`) werden verändert.
- Fix: GO von Marc muss belegt sein (Commit-Message/Spec), sonst zurückstellen.
  Kein Bug — aber ohne dokumentiertes GO ist die Änderung regelwidrig.

### [HIGH] `missing_sources` ist praktisch unerreichbar — der stille Ausfall bleibt
- Datei: anvil/core/mod_deployer.py:616-624, 883-891
- Problem: Die Prüfung `any(not f.is_file() ...)` löst den Neuscan aus, **bevor**
  die Schleife läuft. `invalidate_and_rescan()` baut die Liste frisch vom
  Dateisystem — sie enthält danach nur noch existierende Dateien. Die Bedingung
  `if not src_file.is_file()` in der Schleife kann folglich nur noch bei einem
  Race (Datei verschwindet zwischen Rescan und Schleife) zutreffen.
- **Gemessen** (Probelauf, Datei wirklich gelöscht, Wurzelzeit eingefroren):
  `MISSING: []`, `STALE: ['Mod']`, `ERRORS: []`, `SUCCESS: True`, Log:
  `0 symlinks, 0 copies, 0 errors`.
  Also exakt der Zustand, den der Kommentar „frueher stand trotzdem 0 errors im
  Log — der Ausfall blieb tagelang unbemerkt" zu beheben vorgibt. Er ist NICHT
  behoben.
- Fix: Die fehlenden Dateien vor dem Rescan festhalten (Differenz alte Liste ↔
  neue Liste nach dem Rescan) — das ist der Fall, den die Kommentare beschreiben.
  Oder: Feld und Kommentare entfernen, wenn nur der Race gemeint war.

### [HIGH] `test_wirklich_fehlende_quelldatei_ist_ein_fehler` prüft nicht, was der Name sagt
- Datei: tests/test_modindex_aktualitaet.py:138-156
- Problem: Name und Docstring versprechen „ist ein Fehler" / „frueher stand
  trotzdem 0 errors im Log", die Asserts prüfen aber nur `stale_index_mods` und
  dass die Datei nicht im Spiel liegt. Weder `errors` noch `success` noch
  `missing_sources` werden geprüft. Der Test ist deshalb grün, obwohl das
  beschriebene Verhalten (Fehlermeldung statt stillem Ausfall) nicht eintritt —
  siehe Finding oben. Ein grüner Test, der genau die Regression deckt, die es
  noch gibt, ist schlimmer als kein Test.
- Fix: entweder `assert not ergebnis.success` / `assert ergebnis.errors`
  ergänzen (dann fällt der Test um und deckt das echte Loch auf) oder Name und
  Docstring auf das reduzieren, was er tatsächlich prüft.

### [HIGH] Neuer benutzersichtbarer Text ohne tr() — deutscher Satz für alle 7 Sprachen
- Datei: anvil/core/mod_deployer.py:888-891
- Problem: `result.errors` landet nicht nur im Log. `mainwindow.py:2731-2737`
  und `_report_predeploy_failure()` (mainwindow.py:3058-3070) zeigen die ersten
  Einträge als `{details}` in `tr("error.deploy_failed_message")` in einer
  QMessageBox. Der neue Text „N Quelldatei(en) fehlen, z.B. …" ist damit
  benutzersichtbar, fest deutsch und erscheint so auch in en/es/fr/it/pt/ru.
- Zusätzlich stilfremd: alle übrigen `errors`-Einträge im Deployer sind kurze
  englische Technik-Strings (`write manifest: …`, `lml symlink X: …`,
  `redmod symlink X: …`), keine deutschen Prosasätze.
- Etabliertes Muster für übersetzbare Kernfehler existiert bereits:
  `PluginsTxtWriter.last_error_key` + `localized_write_error()` in
  game_panel.py:233 ff. — ein Übersetzungs-Key wandert aus dem Core in die GUI.
  Dieses Muster wird hier umgangen.
- Fix: entweder Key-Mechanik wie bei plugins.txt nutzen und
  `error.deploy_missing_sources` in **allen 7** Locales (de, en, es, fr, it, pt,
  ru) anlegen — aktuell fehlt der Key in allen — oder auf einen technischen
  englischen String im Stil der Nachbarn zurückgehen.

### [HIGH] Erfolgs-Semantik eskaliert: eine fehlende Quelldatei verhindert den Spielstart
- Datei: anvil/core/mod_deployer.py:885-891 zusammen mit :898-899
  (`if result.errors: result.success = False`)
- Problem: `missing_sources` wird nach `errors` geschrieben, damit wird
  `success = False`. Folgen in der Kette: `_predeploy_for_launch()` bricht ab
  und gibt False zurück (mainwindow.py:3054-3056) → **das Spiel startet nicht**;
  BA2-Packing und plugins.txt werden übersprungen (game_panel.py:1290 ff.).
  Bisher war eine einzelne unauffindbare Quelldatei folgenlos.
- Bewusst? Nachvollziehbar, aber es ist eine Verhaltensänderung im geschützten
  Bereich (siehe erstes Finding) und sie ist nirgends dokumentiert. Präzedenzfall
  im Code spricht sogar dagegen: bei plugins.txt wurde eigens eine Ausnahme
  eingebaut, damit ein Randfall nicht den einzigen Weg heraus versperrt
  (game_panel.py:1159-1163, Issue #103).
- Fix: entweder bewusst festhalten (CHANGELOG + ARCHITEKTUR.md) oder wie
  `skipped_real_files` behandeln: melden, aber den Start nicht blockieren.

### [MEDIUM] `stale_index_mods`/`missing_sources` folgen dem `skipped_real_files`-Muster nicht
- Dateien: anvil/core/mod_deployer.py:241-245, 872-891; anvil/widgets/game_panel.py:1279-1287
- Drei Abweichungen vom bestehenden Muster:
  1. **Ort der Ausgabe.** `skipped_real_files` wird in der GUI-Schicht
     (`game_panel.silent_deploy()`, Zeile 1280-1287) protokolliert, die neuen
     Felder direkt im Core. Damit gibt es jetzt zwei Konventionen für dasselbe
     Anliegen. Die neuen Felder tauchen in `game_panel.py` **überhaupt nicht**
     auf (verifiziert per grep: einzige Fundstellen sind mod_deployer.py und die
     neuen Tests).
  2. **Auswirkung auf `success`.** `skipped_real_files` setzt niemals einen
     Fehler — die Datei bleibt liegen, das Deploy gilt als erfolgreich.
     `missing_sources` kippt `success`. Zwei Sammelfelder, zwei Regeln.
  3. **Eintragsformat.** `skipped_real_files` enthält **spielrelative** Pfade
     (`str(target.relative_to(game_path))`, Zeilen 472, 508, 558) bzw. `str(rel)`
     (Zeile 721); `missing_sources` enthält `"<Mod>/<rel>"`, also quellseitig.
     Inhaltlich richtig, aber ohne Doku verwechselbar.
- Fix: Ausgabeort vereinheitlichen (entweder alle drei im Core oder alle drei im
  Panel) und die `success`-Regel bewusst festlegen.

### [MEDIUM] `invalidate_and_rescan()` im Deploy-Loop schreibt die Cache-Datei pro Mod neu
- Dateien: anvil/core/mod_deployer.py:607; anvil/core/modindex.py:187-204
- Problem: `invalidate_and_rescan()` ruft am Ende `_save_cache()` — ein voller
  JSON-Dump des gesamten Index. Gemessen an Marcs echter Cyberpunk-Instanz:
  `.modindex.json` = **241.650 Bytes**, 536 Mods. Sind nach einem Import/einer
  Wiederherstellung viele Mods veraltet, schreibt ein einziger Deploy die Datei
  N-mal komplett neu (N = Anzahl veralteter Mods). Die Methode war laut ihrem
  eigenen Docstring für einzelne interaktive Operationen („after install/rename")
  gedacht, nicht für eine Schleife über alle Mods.
- Fix: im Deployer eine Variante ohne Sofort-Speicherung nutzen (Rescan in den
  Speicher, einmal am Ende sichern) oder `rebuild()` einmalig vorziehen.

### [MEDIUM] Der Deploy verändert jetzt gemeinsam genutzten GUI-Zustand
- Dateien: anvil/core/mod_deployer.py:607; anvil/mainwindow.py:1980-1983
- Problem: Genau diese `ModIndex`-Instanz hängt an `mainwindow._mod_index`, wird
  per `plugin.setModIndex()` weitergereicht und speist über `scan_mods_directory`
  Dateizahl/Größe der Mod-Liste. Der Deploy war bisher **lesend**; jetzt
  überschreibt er Einträge (Dateiliste, `file_count`, `total_size`) mitten im
  Betrieb, ohne dass die Mod-Liste davon erfährt. Anzeige und Index laufen bis
  zum nächsten Instanzwechsel auseinander.
- Kein Absturz, keine Thread-Gefahr (geprüft: `silent_deploy()` läuft im
  GUI-Thread; die Migration im Worker baut mit `ModIndex(instance_path,
  mods_path=…)` eine **eigene** Instanz, mainwindow.py:1181).
- Fix: nach einem Deploy mit `stale_index_mods` die Mod-Liste auffrischen, oder
  die Korrektur bewusst als reine Innenkorrektur dokumentieren.

### [MEDIUM] Modul-Docstring von modindex.py beschreibt jetzt das falsche Verfahren
- Datei: anvil/core/modindex.py:3-6
- Problem: „On subsequent loads only mods whose directory ``st_mtime`` changed
  are re-scanned" — genau das stimmt seit `_fingerprint()` nicht mehr. Der Kopf
  des Moduls ist die erste Stelle, die ein Entwickler liest.
- Fix: einen Satz nachziehen (jüngste Änderungszeit über alle Unterordner).

### [LOW] `_fingerprint()` passt zur Modulrolle, kostet aber das 40-Fache — gemessen
- Datei: anvil/core/modindex.py:33-55
- Bewertung: Ja, die Funktion gehört hierher. Die Frische-Entscheidung ist genau
  die Aufgabe dieses Moduls, sie war vorher nur zu grob. Kapselung sauber, beide
  Aufrufer (`rebuild`, `invalidate_and_rescan`) nutzen dieselbe Funktion, ein
  dritter Pfad existiert nicht.
- Gemessen an Marcs Cyberpunk-Instanz (536 Mods, 3.520 Ordner, 2.815 Dateien):
  alt (1 `stat` je Mod) **1,1 ms**, neu (`os.walk` + `stat` je Ordner)
  **44,4 ms**, zweiter Lauf mit warmem Cache 43,8 ms.
  Absolut unkritisch auf SSD, skaliert aber linear mit der Ordnerzahl und trifft
  bei kaltem Cache/HDD/Netzlaufwerk deutlich härter. Der Zweck des Index
  („dramatically faster") wird dadurch teilweise wieder aufgezehrt: die
  Rebuild-Kosten sind jetzt O(alle Ordner) statt O(Mods).
- Zusätzlich doppelt: `os.walk` liest die Verzeichnisse bereits, danach wird
  jeder Ordner nochmals einzeln `os.stat`-t.
- Fix (optional): `os.scandir`-Rekursion mit `entry.stat()` statt `os.walk` +
  zweitem `stat`, oder Fingerprint nur bei Cache-Treffer ermitteln.

### [LOW] Semantik-Kante: Rückgabewert 0.0 heißt jetzt zweierlei
- Datei: anvil/core/modindex.py:47-48, 127-129, 195-197
- Problem: Vorher unterschied `try/except OSError` sauber zwischen „Fehler" und
  „Zeitstempel". Jetzt bedeutet `0.0` sowohl OSError als auch einen echten
  mtime von 0 (Epoch — kommt bei aus Archiven entpackten oder mit `touch -d
  @0` behandelten Ordnern vor). Ein solcher Mod würde bei `rebuild()` still
  übersprungen (nie indiziert → deployt nichts) bzw. bei
  `invalidate_and_rescan()` aus dem Index geworfen.
- Fix: `None` als Fehlerwert zurückgeben und `if mtime is None:` prüfen.

### [LOW] Was `_fingerprint()` weiterhin NICHT bemerkt, steht nirgends
- Datei: anvil/core/modindex.py:33-44
- Ordner-mtimes ändern sich beim Anlegen/Löschen/Umbenennen von Einträgen, nicht
  beim Überschreiben eines Dateiinhalts unter gleichem Namen. Wer eine Datei in
  einer Mod mit `cp` ersetzt oder eine `.ini` editiert, hat weiterhin einen
  veralteten `total_size`/`file_count` im Index. Der Docstring erweckt den
  Eindruck von Vollständigkeit.
- Fix: einen Halbsatz zur Grenze ergänzen.

### [LOW] Kommentar- und Docstring-Stil: zu erzählerisch, Bug-Historie im Code
- Dateien: anvil/core/modindex.py:34-44; anvil/core/mod_deployer.py:242-245,
  601-604, 617-619, 872-874, 883-886; tests/test_modindex_aktualitaet.py:1-8
- Bewertung gegen die Projektregel („Kommentare sparsam, nur wo Logik nicht
  selbsterklärend ist"):
  - `_fingerprint()`: 11 Zeilen Docstring für 10 Zeilen Code. Der erste Absatz
    ist Bug-Historie („Die Mod galt dann als unveraendert, der Deployer
    arbeitete mit einer veralteten Dateiliste und liess die Mod stillschweigend
    weg") — das gehört in Commit-Message und CHANGELOG, nicht in den Code. Der
    zweite Absatz („Gezaehlt werden nur Ordner, nicht jede Datei") erklärt
    dagegen echtes, nicht ableitbares Wissen und sollte bleiben.
  - mod_deployer.py:872-874 und 883-886: „bleibt eine kaputte
    Zwischenspeicherung fuer immer unentdeckt", „der Ausfall blieb tagelang
    unbemerkt" — Rechtfertigungsprosa, drei bzw. vier Zeilen für je einen
    `print`. Erklärt nicht die Logik, sondern verteidigt die Entscheidung.
    Zusätzlich behauptet der zweite Kommentar etwas, das der Code nicht liefert
    (siehe HIGH-Finding).
  - Die Feldkommentare in `DeployResult` (Zeilen 242, 244) sind knapp und
    passend — so sollte der Rest auch aussehen.
  - tests/test_modindex_aktualitaet.py:1-8: acht Zeilen Modul-Docstring mit
    kompletter Fehlergeschichte. Ein bis zwei Sätze reichen.
- KI-Sichtbarkeit: Auffällig ist das Muster „jede Stelle bekommt eine
  Was-war-vorher-kaputt-Erzählung mit `--`-Einschüben". Das ist der Duktus, den
  die Projektregel vermeiden will. Die Docstrings auf jeder Test-Hilfsfunktion
  gehen in dieselbe Richtung.
- Sprachmischung: `_fingerprint()` bringt deutschen Docstring und deutsche
  Bezeichner (`neueste`, `wurzel`) in ein durchgehend englisches Modul
  (`_ModCache`, `_scan_mod`, `_walk_files`, alle Docstrings englisch). Ebenso in
  `mod_deployer.deploy()`: `aus_cache`/`dateien` direkt neben `src_file`, `rel`,
  `file_iter`, `symlinks` — innerhalb **einer** Funktion. Neue Module auf Deutsch
  ist die Regel; ein deutsches Fragment in eine englische Funktion zu setzen ist
  keine.

### [LOW] Windrose-Entfernung: keine Code-Löcher, aber Reste und fehlende Doku
Systematisch geprüft:
- **Plugin-Loader:** sauber. `plugin_loader._scan_directory()` iteriert
  `directory.glob("*.py")` (Zeile 255) — keine Registry, keine Liste, kein
  `__init__`-Export. Verifiziert: kein einziger `import`/Namensbezug auf die
  beiden Module irgendwo im Code.
- **Tests:** kein Test nennt Windrose (grep über `tests/` leer).
- **Packaging:** keine Plugin-Aufzählung in PKGBUILD/pyproject/Flatpak-Manifest;
  Plugins werden als Paketinhalt mitgenommen. Kein Loch.
- **Instanzen:** keine Windrose-Instanz unter `~/.anvil-organizer/instances/`
  vorhanden (11 Instanzen geprüft). Falls doch jemand eine hat: `get_game()`
  liefert `None`, mainwindow.py:1805 verkraftet das ohne Absturz, die Instanz
  lädt ohne Plugin (kein Deploy, kein Start) — ohne Hinweis an den Benutzer.
- **Cover/Icons:** keine Windrose-Assets im Repo, in
  `/home/mob/Projekte/anvil-organizer-icons` oder unter `~/.anvil-organizer`.
- **Reste:** verwaiste `.pyc` in `anvil/plugins/games/__pycache__/`
  (cpython-311/313/314), außerdem Kopien in `dist/anvil-organizer/_internal/…`
  und `packaging/flatpak/build/files/…`. Das sind Build-Artefakte, sie werden
  nicht importiert (`__pycache__` ohne Quelle wird von Python nicht geladen).
  **Aber:** Marcs installiertes Flatpak enthält die Plugins weiterhin
  (`~/.local/share/flatpak/app/com.github.Marc1326.AnvilOrganizer/.../
  anvil/plugins/games/game_windrose.py`) — verschwindet erst mit dem nächsten Build.
- **Dokumentation:** `docs/nexus-changelog-v150-bbcode.txt:6` kündigt beide
  Plugins öffentlich an („Windrose (Solo) and Windrose Dedicated Server plugins
  added"). Zur Entfernung gibt es keinen CHANGELOG-Eintrag — die oberste Sektion
  ist unverändert `## [1.7.0]`. Das ist die einzige echte Lücke.
- Fix: Eintrag unter „Änderungen" in CHANGELOG.md, und dort auch die
  Index-Korrektur beschreiben (fehlt ebenfalls).

### [LOW] ModIndex kommt in ARCHITEKTUR.md gar nicht vor
- Datei: /home/mob/Projekte/anvil-wiki/dev-notes/ARCHITEKTUR.md
- Der Datei-Index ist ein zentrales Element (Deployer, Konflikt-Scanner und
  Mod-Eintrag konsumieren ihn), hat aber keinen Abschnitt. Damit lässt sich für
  keine Index-Änderung feststellen, ob sie bewusst von der Vorlage abweicht.
- Fix: kurzer Abschnitt „Datei-Index (modindex.py)" — Zweck, Frische-Kriterium,
  Cache-Version, wer schreibt.

### [LOW] Repo-Hygiene: projektfremder Ordner im Arbeitsbaum
- `001Bericht/` (untracked) enthält Fundus-Material (`DESIGN-BERICHT.md`,
  `Fundus Design Varianten.zip`, `icons/fundus-signet-*.png`). Fundus ist ein
  anderes Projekt. Gehört nicht in das Anvil-Repo.

---

## Testlauf

`.venv/bin/python -m pytest` über die betroffenen Bereiche
(test_modindex_aktualitaet, test_copy_deploy_order, test_custom_deployer_paths,
test_deploy_on_launch, test_deploy_routes, test_keep_mods_deployed,
test_custom_instance_paths, test_predeploy_launch):
**129 passed, 1 failed**.

Der Fehlschlag ist
`test_predeploy_launch.py::SandboxedProcessLookupTests::test_appid_match_stops_at_the_value_boundary`
(`scan_proc_for_game`, SteamAppId-Präfixvergleich). Er rührt nicht von diesen
Änderungen her — der Test startet echte Prozesse und prüft die
`/proc`-Auswertung, berührt weder modindex noch mod_deployer. Separat ansehen.

Die 6 neuen Tests laufen grün (0,05 s) — mit der Einschränkung aus dem
HIGH-Finding zu `test_wirklich_fehlende_quelldatei_ist_ein_fehler`.

---

## Antworten auf die gestellten Fragen

1. **Passt `_fingerprint()` zur Modulrolle?** Ja — die Frische-Entscheidung ist
   Kernaufgabe des Moduls, die Kapselung ist sauber, beide Aufrufer nutzen sie.
   Preis: Rebuild kostet jetzt O(alle Ordner) statt O(Mods), gemessen 1,1 → 44 ms.
   **Andere Stellen mit `os.stat(mod_dir).st_mtime`: keine.** Vollständig
   gesucht (`st_mtime`, `getmtime`, `.stat()` über `anvil/`): alle übrigen
   Fundstellen betreffen Dateien, nicht Mod-Ordner, und keine davon ist eine
   Cache-Frische-Prüfung (Savegame-/Download-Sortierung, Symlink-vs-Kopie-
   Vergleich im Deployer, BG3-Profile). `.modindex.json` wird ausschließlich von
   modindex.py gelesen. Kein zweiter Cache wurde inkonsistent.
2. **Konsistent zu `skipped_real_files`?** Nein — drei Abweichungen (Ausgabeort
   Core statt GUI, `success`-Kippen, Pfadformat). In `game_panel.py` kommen die
   neuen Felder **nicht** vor; sichtbar werden sie nur über den Core-`print` und
   — bei `missing_sources` — über den Fehlerdialog.
3. **Neue benutzersichtbare Texte?** Ja, einer: der Fehlerstring aus
   mod_deployer.py:888. Er erscheint in der QMessageBox
   `error.deploy_failed_message`. Kein tr()-Key vorhanden, folglich fehlt er in
   allen sieben Locales (de, en, es, fr, it, pt, ru). Die `print`-Ausgaben
   selbst sind Log und brauchen keine Übersetzung.
4. **Kommentarstil:** überwiegend zu erzählerisch, Bug-Historie und
   Rechtfertigungen im Code, Sprachmischung innerhalb einzelner Funktionen.
   Details im LOW-Finding. Die knappen Feldkommentare in `DeployResult` sind das
   richtige Maß.
5. **Windrose-Entfernung:** technisch lückenlos (dynamischer Loader, keine
   Referenzen, keine Tests, keine Packaging-Liste, keine Instanz, keine Assets).
   Offen: fehlender CHANGELOG-Eintrag trotz öffentlicher Ankündigung in
   `docs/nexus-changelog-v150-bbcode.txt`, plus verwaiste `.pyc`/Build-Kopien.

---

## Ergebnis

**NEEDS FIXES**

Blockierend:
1. Zustimmung für den Eingriff in mod_deployer.py belegen (ARCHITEKTUR.md Regel 9.6).
2. `missing_sources` erreichbar machen — sonst besteht der stille Ausfall fort,
   den die Änderung zu beheben behauptet.
3. Test 6 an seinen eigenen Anspruch anpassen.
4. Fehlertext übersetzbar machen (7 Locales) oder auf Technik-Stil zurückführen.
5. Entscheiden und dokumentieren, ob eine fehlende Quelldatei den Spielstart
   verhindern soll.
