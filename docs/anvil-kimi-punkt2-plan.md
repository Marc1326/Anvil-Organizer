# Punkt 2 — Konflikte innerhalb von Archiven anzeigen

Analyse- und Umbauplan. Stand der Untersuchung: 13.08.2026.
Auslöser: `FemV - RE9 Grace` überschreibt Augen-Dateien von
`Unique Eyes - Core` — in Anvil heute nirgends sichtbar.

---

## 1. Wie funktioniert die heutige Konfliktanzeige?

### 1.1 Berechnung

Alles läuft über eine Klasse:

- `anvil/core/conflict_scanner.py:60` — `class ConflictScanner`
- `anvil/core/conflict_scanner.py:69` — `scan_conflicts(mods, game_plugin, mod_index, pak_file_lists)`

### 1.2 Wer sammelt die Dateien pro Mod?

`scan_conflicts` kennt drei Quellen, in dieser Reihenfolge:

| Quelle | Stelle | Wann |
|---|---|---|
| `pak_file_lists` (BG3-.pak-Inhalte) | `conflict_scanner.py:113-126` | nur Baldur's Gate 3 |
| `mod_index.get_file_list(name)` (JSON-Cache) | `conflict_scanner.py:133-149` | wenn Cache gefüllt |
| `Path.rglob("*")` direkt auf dem Mod-Ordner | `conflict_scanner.py:151-172` | Fallback |

Der Cache steht in `anvil/core/modindex.py`: `get_file_list` (`modindex.py:169`),
Dateiliste als `{"rel": pfad, "size": n}` pro Datei (`modindex.py:309`),
abgelegt in `.modindex.json` im Instanzordner (`modindex.py:35`).
Cache-Gültigkeit über einen Ordner-Fingerprint (`modindex.py:38-63`).

### 1.3 Datenstruktur

Zentrale Struktur: `file_owners: dict[str, list[str]]` — relativer Pfad →
Liste der Mod-Namen in Prioritätsreihenfolge (`conflict_scanner.py:108`).
Ein Konflikt ist ein Pfad mit ≥ 2 Besitzern (`conflict_scanner.py:178-198`).

Rückgabe (`conflict_scanner.py:200-204`):

- `conflicts` — Liste von `{file, mods, winner}`
- `ignored` — gefilterte Treffer (readme etc.)
- `file_owners` — alles, was aktive Mods liefern

### 1.4 Wer gewinnt?

Regel: **der letzte Eintrag in der Besitzerliste gewinnt**
(`conflict_scanner.py:197`: `"winner": owners[-1]`).

Die Liste wird vorher gedreht, damit das zur Anzeige passt: in der Mod-Liste
steht die stärkste Mod oben, `MainWindow._conflict_mod_list` ruft
`all_mods.reverse()` auf (`anvil/mainwindow.py:2964-2978`). BG3 wird
ausdrücklich nicht gedreht (`mainwindow.py:2976`). Diese Drehung ist durch
`tests/test_konflikt_reihenfolge.py:1-9` abgesichert.

Filter vor der Konfliktentscheidung:

- `meta.ini` nie (`conflict_scanner.py:64`)
- `.txt` nie (`conflict_scanner.py:67`)
- Spiel-eigene Muster über `get_conflict_ignores()` (`conflict_scanner.py:101-104`);
  Cyberpunk liefert 5 Muster (`anvil/plugins/games/game_cyberpunk2077.py:418-426`),
  Standard ist die leere Liste (`anvil/plugins/base_game.py:921`)

### 1.5 Wo taucht das in der Oberfläche auf?

| Ort | Stelle | Form |
|---|---|---|
| Mod-Liste, Spalte „Konflikte" | `anvil/models/mod_list_model.py:776`, Icons `:25-39` und `:321-324` | SVG-Symbole `conflict_win/lose/both.svg` (`anvil/styles/icons/conflicts/`) |
| Tooltips in der Liste | `mod_list_model.py:377-388` | „überschreibt N Dateien…" |
| Farb-Highlight bei Auswahl | `anvil/widgets/mod_list.py:1106-1210`, Farben `mod_list_model.py:147-150, 401-408` | grün/rot hinterlegte Zeilen |
| Trenner-Aggregat | `mod_list_model.py:207-220, 306-331` | Summe der Konflikte im eingeklappten Trenner |
| Badge-Delegate | `mod_list.py:1308-1309` | `ConflictBadgeDelegate` auf Spalte `COL_CONFLICTS` |
| Mod-Detaildialog, Tab „Konflikte" | `anvil/dialogs/mod_detail_dialog.py:1340-1466`, eingehängt `:1879` | zwei Bäume „Überschreibt" / „Wird überschrieben" |
| Einstellungen → Diagnose | `anvil/widgets/settings_dialog.py:1089-1090, 1475-1495` | Liste, max. 500 Einträge |
| Diagnose-Report | `anvil/core/diagnostics.py:321-323` | Textreport, max. 50 Einträge |
| „Data"-Tab (virtuelles Dateisystem) | `anvil/mainwindow.py:3026-3035` → `anvil/widgets/game_panel.py:3087-3093` | bekommt `file_owners` direkt |

### 1.6 Wann wird gerechnet?

Alles synchron im GUI-Thread, kein Worker:

- Instanz laden: `mainwindow.py:2016`
- Drag & Drop / Umsortieren: `mainwindow.py:2644, 2674, 2716, 2767, 2846`
- weitere Stellen: `mainwindow.py:7394, 8252`
- Detaildialog rechnet **bei jedem Öffnen neu** und zwar **ohne** `mod_index`
  (`mod_detail_dialog.py:1359-1360`) — dort läuft also jedes Mal der
  `rglob`-Fallback über alle Mod-Ordner.

---

## 2. Was kann redengine_archive.py heute?

Datei: `anvil/core/redengine_archive.py` (137 Zeilen, komplett gelesen).

### 2.1 Öffentliche Schnittstelle

| Name | Signatur | Zweck |
|---|---|---|
| `ArchiveError` | `class ArchiveError(RuntimeError)` (`:42`) | Fehler bei unlesbaren Archiven |
| `ArchiveInfo` | `@dataclass(frozen=True)` mit `path: Path`, `hashes: frozenset[int]`, `version: int` (`:46-61`) | Ergebnis |
| `is_archive` | `(path: Path) -> bool` (`:64`) | Magic-Check `RDAR`, liest 4 Bytes |
| `read_archive` | `(path: Path) -> ArchiveInfo` (`:73`) | liest Kopf + Indextabelle |
| `shared_hashes` | `(a, b) -> frozenset[int]` (`:116`) | Schnittmenge zweier Archive |
| `find_overlaps` | `(archive: list[ArchiveInfo]) -> list[tuple[ArchiveInfo, ArchiveInfo, int]]` (`:121`) | alle Paare mit Überschneidung, größte zuerst |

### 2.2 Was kommt zurück?

**Nur 64-Bit-Prüfsummen der enthaltenen Spieldatei-Pfade, keine Dateinamen.**
Das steht ausdrücklich im Modul-Docstring (`redengine_archive.py:8-11`):
„Diese Pruefsummen genuegen: gleiche Pruefsumme = gleiche Spieldatei. Der
Klartextpfad wird dafuer nicht gebraucht." Aus dem Hash lässt sich der
Pfad nicht zurückrechnen. Gelesen werden nur Kopf und Tabelle, ein paar
Kilobyte pro Archiv (`:13-14`, `:79-94`).

### 2.3 Caching

**Keins.** Jeder `read_archive`-Aufruf öffnet die Datei neu (`:80`).
Es gibt keinen Speicher, keine Invalidierung, keinen Zeitstempel-Vergleich.

### 2.4 Aufrufer

**Nur der Test.** `tests/test_redengine_archive.py:14-20` importiert alle
fünf Symbole. Eine Suche nach `redengine_archive`, `read_archive`,
`find_overlaps`, `shared_hashes` über das ganze Repo findet im
Produktivcode keinen einzigen Aufruf. Der Gegenprobe-Test läuft gegen ein
echtes Archiv von `Unique Eyes - Core` mit 43 bekannten Dateien
(`tests/test_redengine_archive.py:23-27, 154-161`).

---

## 3. Die Lücke

### 3.1 Warum der Grace-Fall unsichtbar ist

Der Scanner sieht eine `.archive`-Datei als **einen** relativen Pfad, z. B.
`archive/pc/mod/foo.archive`. Zwei Mods mit unterschiedlich benannten
Archiven erzeugen zwei verschiedene Pfade → kein Eintrag in `file_owners`
mit zwei Besitzern → kein Konflikt. Was *im* Archiv steckt, wird nirgends
aufgerufen (siehe 2.4). Genau das bestätigt der Modul-Docstring selbst
(`redengine_archive.py:4-6`).

### 3.2 Stellen, die geändert werden müssten

1. **`anvil/core/conflict_scanner.py:69-204`** — Archiv-Inhalte müssen als
   zusätzliche „virtuelle Dateien" in die Besitzer-Struktur einfließen
   (oder als separates Ergebnisfeld, siehe Vorschlag).
2. **`anvil/core/modindex.py:294-323`** (`_scan_mod`) — naheliegender Ort,
   um beim ohnehin laufenden Scan die Hashes jeder `.archive` mitzulesen
   und im Cache abzulegen. Sonst wird bei jedem Umsortieren neu vom
   Datenträger gelesen.
3. **`anvil/mainwindow.py:2964-3011`** (`_conflict_mod_list`,
   `_run_conflict_scan`) — müsste die Archiv-Daten an den Scanner
   durchreichen, analog zum BG3-`pak_file_lists`-Weg (`:2936-2962`).
4. **`anvil/dialogs/mod_detail_dialog.py:1359-1360`** — der Dialog scannt
   heute ohne Cache; mit Archiv-Lesen würde das jedes Öffnen spürbar
   teurer. Muss denselben Datenweg wie das Hauptfenster bekommen.
5. Anzeige: `mod_list_model.py` (Tooltip-Texte), `mod_detail_dialog.py`
   (Konflikte-Tab) — siehe 5.3 zum Darstellungsproblem.

### 3.3 Nur Cyberpunk?

Nein, aber unterschiedlich weit:

- **Baldur's Gate 3: schon gelöst.** `.pak`-Inhalte fließen über
  `LSPKReader.read_pak_full` (`anvil/core/lspk_parser.py:182`) und
  `_build_bg3_file_lists` (`mainwindow.py:2936-2962`) als `pak_file_lists`
  in denselben Scanner. Dort zeigt die Konfliktanzeige bereits echte
  Archiv-Inhalte mit Klartextpfaden.
- **Cyberpunk 2077:** Werkzeug vorhanden, nicht angeschlossen (dieser Punkt).
- **Fallout 4 / Starfield / Skyrim SE (BA2):** `anvil/core/ba2_packer.py`
  kann nur **packen** (`pack_mod` `:330`, `pack_all_mods` `:406`) — ein
  Leser für BA2-Inhalte existiert im Repo nicht. Dieselbe Lücke, aber ohne
  fertiges Werkzeug.
- **Stalker 2** ist das einzige andere Spiel mit `GamePakLoadOrderDirs`
  (`anvil/plugins/games/game_stalker2.py:61`, Standard leer in
  `base_game.py:151`); ein Inhalts-Leser für seine `.pak`-Dateien wurde
  nicht gefunden.
- Alle übrigen Spiele vergleichen weiterhin nur lose Dateipfade.

Empfehlung: die Archiv-Inhalte spielneutral über einen Hook am Plugin
anbinden (Muster: `get_conflict_ignores`), nicht als Cyberpunk-Sonderweg
im Scanner.

---

## 4. Gefahren

### 4.1 Geschwindigkeit

- Der Scan läuft **synchron im GUI-Thread** — beim Instanz-Load
  (`mainwindow.py:2016`) und bei **jedem** Drag & Drop
  (`mainwindow.py:2716, 2767`). Jede neue Datenträger-Arbeit bremst direkt
  die Oberfläche.
- Die Angabe „374 Archive in 0,1 s" steht in `docs/stand-2026-08-12.md:92`;
  einen Benchmark im Repo habe ich nicht gefunden (siehe UNSICHER). Selbst
  wenn sie stimmt: ohne Cache wird sie bei jedem Umsortieren erneut fällig.
- `find_overlaps` (`redengine_archive.py:121-137`) ist O(n²) über alle
  Archivpaare: 500 Mods → ~125.000 Set-Schnitte. Messbar, aber eine
  Hash→Mods-Map (wie `file_owners`) ist linear und ohnehin die
  Scanner-Datenstruktur.
- Der Detaildialog scannt heute schon ohne Cache (`mod_detail_dialog.py:1360`);
  mit Archiv-Lesen würde jeder Dialog-Öffnen Vollkosten verursachen.

### 4.2 Speicher

Unkritisch. Pro Archiv ein `frozenset[int]` (`redengine_archive.py:57,
109-113`). Selbst 10.000 Dateien je Archiv × 500 Mods sind nur ein paar
hundert MB im schlimmsten denkbaren Fall; realistisch (43 Dateien im
Referenzarchiv, `tests/test_redengine_archive.py:160`) einstellige
MB-Beträge. Kein Vergleich zu dem, was `file_owners` heute schon hält.

### 4.3 Absturzstellen

- Kaputte/fremde `.archive`-Dateien: `read_archive` wirft `ArchiveError`
  bei falschem Magic (`:83`), Index außerhalb der Datei (`:91`), zu
  kurzem Index (`:99`), unglaubwürdiger Dateizahl (`:102-103`),
  abgeschnittener Tabelle (`:106-107`). Das ist sauber designt — **aber
  der Aufrufer muss es fangen.**
- Fehlende Leserechte: `OSError` wird in `ArchiveError` umverpackt
  (`:95-96`). Beim Magic-Check gibt `is_archive` still `False` zurück
  (`:69-70`).
- Kritische Stelle: `ModIndex._scan_mod` fängt nur `OSError`
  (`modindex.py:312-316`). `ArchiveError` ist ein `RuntimeError`
  (`redengine_archive.py:42`) und würde dort **durchschlagen** — ein
  einziges kaputtes Archiv würde den ganzen Index-Scan abbrechen, wenn
  die Integration dort ohne `except ArchiveError` landet.
- Die Diagnose-Wege sind abgesichert (`mainwindow.py:3022`,
  `settings_dialog.py:1483`: „Diagnose darf nie crashen").

---

## 5. Vorschlag

### 5.1 Das Darstellungsproblem zuerst

`ArchiveInfo` liefert nur Hashes, keine Pfade (2.2). Die heutige Anzeige
zeigt überall Dateipfade (`mod_detail_dialog.py:1414, 1446`). Für
Archiv-Konflikte kann Anvil also **nicht** sagen „Grace überschreibt
`base/characters/.../eyes.mesh`", sondern nur: „Grace' Archiv X und
Unique Eyes' Archiv Y liefern **N identische Spieldateien** — X gewinnt."
Jede Variante muss damit leben; Klartext gäbe es nur über eine externe
Hash-Tabelle (Known-Hashes-Liste), die nicht Teil dieses Punktes ist.

### 5.2 Variante A — Archiv-Hashes in ModIndex + Scanner erweitern (empfohlen)

1. `modindex.py:_scan_mod` (`:294-323`): für jede Datei mit Endung
   `.archive` zusätzlich `read_archive` aufrufen, Hashes im Cache-Eintrag
   ablegen (neues Feld, `_CACHE_VERSION` `:34` hochziehen).
   `except ArchiveError` pro Datei, Mod bleibt nutzbar.
2. `conflict_scanner.py:scan_conflicts`: neuer Parameter
   `archive_hashes: dict[str, dict[str, frozenset[int]]]`
   (Mod → Archivpfad → Hashes), geliefert über den ModIndex.
   Daraus eine eigene Struktur `hash_owners: dict[int, list[str]]`
   aufbauen — dieselbe „letzter gewinnt"-Regel (`:197`) gilt unverändert,
   weil die Mod-Reihenfolge bereits stimmt.
3. Ergebnis um ein viertes Feld `archive_conflicts` erweitern:
   `{archiv_a, archiv_b, mod_a, mod_b, winner, anzahl}`.
   **Bewusst getrennt von `conflicts`/`file_owners`**, weil `file_owners`
   unverändert in den Data-Tab fließt (`mainwindow.py:3035`) — Hashes
   dürften dort nicht als Dateien auftauchen.
4. `mainwindow.py:_run_conflict_scan` (`:2980-3011`): Archiv-Daten aus
   `self._mod_index` durchreichen; `_compute_conflict_data` (`:3037-3084`)
   zählt Archiv-Treffer in `wins`/`losses` mit ein — damit bekommen
   Listen-Icons, Tooltips, Highlight und Trenner-Aggregat die Konflikte
   **automatisch**, ohne die Widgets anzufassen.
5. `mod_detail_dialog.py:1340-1466`: zusätzlicher Abschnitt im
   Konflikte-Tab („Konflikte in Archiven"), und der Dialog bekommt
   endlich den `mod_index` übergeben statt selbst zu `rglob`en (`:1360`).
6. Spielneutralität: Hook am Plugin, z. B. `get_archive_conflict_reader()`,
   den nur Cyberpunk mit `redengine_archive` befüllt (Muster wie
   `get_conflict_ignores`, `base_game.py:921`). BA2/andere können später
   denselben Weg nutzen.

Aufwand: mittel. Nutzt den vorhandenen Cache, behebt das Sync-Problem
strukturell, alle Anzeigen ziehen mit.

### 5.3 Variante B — separater Archiv-Scan, nur Cyberpunk, nur Detaildialog

`find_overlaps` (`redengine_archive.py:121`) direkt im Konflikte-Tab des
Detaildialogs aufrufen: beim Öffnen alle `.archive` der aktiven Mods
lesen, Paare berechnen, als eigene Tabelle zeigen. Kein Eingriff in
Scanner, ModIndex oder Mod-Liste.

Aufwand: klein. Aber: Listen-Icons bleiben blind (der Grace-Fall wäre
weiterhin nur im Dialog sichtbar), kein Cache (jeder Dialog liest alles
neu), und es entsteht ein zweiter Konfliktmechanismus neben dem
bestehenden. **Nicht empfohlen** — höchstens als Zwischenschritt.

### 5.4 Tests

Bestehende Tests in `tests/`:

- `tests/test_redengine_archive.py` — Reader, inkl. Gegenprobe am echten
  Archiv (`:154-161`). Hierher gehören Tests für kaputte Archive im
  ModIndex-Kontext.
- `tests/test_konflikt_reihenfolge.py` — Gewinner-Regel und Dialog-Tab.
  Hierher gehört ein Fall „Archiv-Konflikt: oberste Mod gewinnt".
- **Es gibt keinen Test, der `ConflictScanner` direkt prüft** (Suche nach
  `scan_conflicts` in `tests/` findet nur die beiden oben). Eine
  Scanner-Änderung braucht zuerst einen direkten Test der heutigen
  `conflicts`/`file_owners`-Ausgabe als Sicherungsnetz.
- `tests/test_modindex_aktualitaet.py` — Cache-Verhalten; hierher der
  Test „neues/verändertes Archiv invalidiert den Hash-Eintrag".

Neu nötig: Scanner-Test mit zwei Mods, je ein `.archive` mit gemeinsamen
Hashes → Konflikt mit richtigem Gewinner; Test mit kaputtem Archiv →
kein Absturz, Mod bleibt im Ergebnis; Dialog-Test für den neuen Abschnitt.

### 5.5 Neue tr()-Schlüssel

Locale-Dateien im Repo: **7**, nicht 6 — `anvil/locales/` enthält
`de, en, es, fr, it, pt` **und `ru`**. Jeder neue Schlüssel muss in alle
7 Dateien.

Voraussichtlich neu (Namen als Vorschlag):

- `mod_detail.archive_conflicts` — Überschrift des neuen Abschnitts
- `mod_detail.archive_conflict_row` — „{archiv_a} ↔ {archiv_b} ({count} Dateien)"
- `tooltip.conflict_archive` — Tooltip-Zusatz in der Mod-Liste
- `settings.diag_archive_conflicts` — falls die Diagnose sie mit ausgibt

---

## UNSICHER

- **„374 Archive in 0,1 s"**: steht nur in `docs/stand-2026-08-12.md:92`.
  Einen Benchmark oder Messcode im Repo habe ich nicht gefunden. Die
  Größenordnung ist plausibel (nur Kopf + Tabelle werden gelesen,
  `redengine_archive.py:13-14`), aber nicht von mir nachgemessen.
- **Ob `Unique Eyes - Core` und `FemV - RE9 Grace` sich wirklich
  überschneiden**: der Test belegt nur, dass `Unique Eyes - Core` 43
  Dateien enthält (`tests/test_redengine_archive.py:154-161`). Einen
  Lauf von `find_overlaps` über beide Mods habe ich nicht ausgeführt
  (nur Lesezugriff erlaubt, kein Produktivcode-Aufruf).
- **Ob REDmod-Archive** (unter `mods/<name>/archives/`, laut
  `game_cyberpunk2077.py:76-77` von der Namenszählung ausgenommen)
  in diese Konfliktanzeige gehören: ihre Laderreihenfolge habe ich
  nicht untersucht.
- **Ob der Data-Tab** (`game_panel.py:3087-3093`) Archiv-Inhalte
  überhaupt darstellen *soll* — fachliche Entscheidung, kein Code-Befund.
- **Hash-Kollisionen**: 64-Bit-Hashes können theoretisch kollidieren;
  welcher Hash-Algorithmus in REDengine steckt und wie kollisionsfest
  er ist, steht nicht im Repo.
- **Ob es in `anvil/widgets/filter_panel.py` Konflikt-Filterchips gibt**,
  die bei Variante A mitgezogen werden müssten: die Datei matched auf
  „conflict" (`mod_list.py:705-709` zeigt Konflikt-Filterlogik im
  Proxy-Modell), die Details habe ich nicht gelesen.
