# Feature: BG3 Konflikt-Erkennung
Datum: 2026-04-04

## Zusammenfassung

Baldur's Gate 3 Mods werden als `.pak`-Archive verwaltet (nicht als lose Dateien in `.mods/`). Der bestehende ConflictScanner erkennt daher bei BG3 keine Konflikte — er ueberspringt alle Mods, weil `.mods/<UUID>/` als Verzeichnis nicht existiert (Zeile 131 in conflict_scanner.py: `if not mod_root.is_dir(): continue`).

Dieses Feature erweitert die Konflikt-Erkennung, sodass sie die Dateilisten innerhalb von `.pak`-Archiven liest und vergleicht. Zwei Mods stehen im Konflikt, wenn sie Dateien mit identischem relativen Pfad innerhalb ihrer .pak-Archive enthalten.

## Quell-Analysen
- Agent 1: `docs/anvil-agent1-plan.md` (Anvil Code)
- Agent 2: `docs/anvil-agent2-plan-bg3-konflikt.md` (LSPKReader)
- Agent 3: `docs/anvil-agent3-plan.md` (Architektur + Signal-Flow)

## User Stories
- Als BG3-User moechte ich sehen, welche meiner .pak-Mods dieselben Dateien ueberschreiben, damit ich Konflikte erkennen und die Ladereihenfolge anpassen kann.
- Als BG3-User moechte ich Konflikt-Icons (gruen/rot/gelb) in der Mod-Liste sehen, identisch zur Darstellung bei Skyrim oder Cyberpunk.
- Als BG3-User moechte ich per Tooltip sehen, welche konkreten Dateien in Konflikt stehen und welcher Mod gewinnt.

---

## Technische Planung

### Aufgeloeste Widersprueche zwischen den Agents

**Rueckgabeformat von get_file_list():**
- Agent 2 empfiehlt `list[str]` (nur Pfade, kein dict)
- Agent 3 empfiehlt `list[dict]` mit `{"rel": str, "size": int}` (kompatibel mit ModIndex)
- **Entscheidung: `list[dict]`** — Das ModIndex-kompatible Format `{"rel": str, "size": int}` wird verwendet. Grund: Der ConflictScanner nutzt bereits das `finfo["rel"]`-Pattern (Zeile 114 in conflict_scanner.py). Einheitliches Format vermeidet Sonderfaelle. Speicher-Overhead ist vernachlaessigbar (~4 Bytes pro Entry fuer den int).

**ModIndex erweitern vs. separater Cache:**
- Agent 1 empfiehlt: ModIndex um .pak-Support erweitern (Option A)
- Agent 3 empfiehlt: KEIN ModIndex-Umbau, separater PakFileIndex (Phase 2)
- **Entscheidung: KEIN Cache in Phase 1.** Der direkte .pak-Scan dauert ~170ms (86 Mods), das ist akzeptabel. Ein PakFileIndex wird als Phase 2 nachgeliefert, wenn Performance >300ms gemessen wird.

**ConflictScanner-Erweiterung:**
- Agent 2 schlaegt Erkennung ueber game_plugin Flag vor
- Agent 3 schlaegt `pak_file_lists`-Parameter vor
- **Entscheidung: `pak_file_lists`-Parameter.** Sauberer, kein Plugin-Sniffing noetig. Der ConflictScanner bleibt plugin-agnostisch.

### Betroffene Dateien

| Datei | Aenderung | Risiko |
|-------|-----------|--------|
| `anvil/core/lspk_parser.py` | Refactoring: `_read_entries()` extrahieren, neue Methode `read_pak_full()` | Niedrig |
| `anvil/core/conflict_scanner.py` | Neuer optionaler Parameter `pak_file_lists` in `scan_conflicts()` | Niedrig |
| `anvil/plugins/games/game_baldursgate3.py` | `get_conflict_ignores()` um `**/meta.lsx` erweitern | Niedrig |
| `anvil/mainwindow.py` | Neue Methode `_build_bg3_file_lists()`, `_compute_conflict_data()` BG3-Pfad, `_bg3_reload_mod_list()` Zeile 5224 mit conflict_data | Mittel |

**NICHT betroffen (funktionieren automatisch wenn Daten korrekt befuellt):**
- `anvil/models/mod_list_model.py` — UI-Anzeige (Icons, Tooltips, Highlighting)
- `anvil/core/modindex.py` — wird fuer BG3 nicht verwendet
- `anvil/core/bg3_mod_installer.py` — Installation unveraendert

### Implementierungsplan

**Schritt 1: LSPKReader Refactoring (`anvil/core/lspk_parser.py`)**

Die bestehende `_read()` Methode wird aufgeteilt:

1.1. Neue interne Methode `_read_entries(f)`:
- Nimmt ein offenes File-Handle
- Liest Magic (4B), Header (36B), springt zu FileListOffset
- Dekomprimiert die Dateiliste mit LZ4
- Parst alle FileEntry18-Structs (je 272 Bytes)
- Gibt `list[dict]` zurueck (alle entries mit name, offset, compression, size_on_disk, uncompressed_size)
- Bei Fehler: gibt `None` zurueck

1.2. Bestehende `_read()` anpassen:
- Ruft `_read_entries(f)` auf
- Sucht danach info.json/meta.lsx wie bisher
- Verhaltensaenderung: KEINE

1.3. Neue oeffentliche Methode `read_pak_full(pak_path)`:
```python
def read_pak_full(self, pak_path: Path) -> tuple[dict | None, list[dict]]:
    """Liest Metadata UND vollstaendige Datei-Liste in einem Durchgang.
    
    Returns:
        (metadata_dict, file_list)
        metadata_dict: wie read_pak_metadata() — oder None bei Fehler
        file_list: [{"rel": "pfad/datei.ext", "size": N}, ...] — oder []
    """
```
- Oeffnet .pak, ruft `_read_entries(f)` auf
- Konvertiert ALLE entries zu `[{"rel": entry["name"], "size": entry["uncompressed_size"]}]`
- Sucht gleichzeitig info.json/meta.lsx fuer Metadata
- Gibt beides als Tuple zurueck
- Vorteil: Jede .pak wird nur EINMAL geoeffnet und gelesen

**Schritt 2: ConflictScanner erweitern (`anvil/core/conflict_scanner.py`)**

2.1. Neuer optionaler Parameter in `scan_conflicts()`:
```python
def scan_conflicts(
    self,
    mods: list[dict],
    game_plugin=None,
    mod_index: ModIndex | None = None,
    pak_file_lists: dict[str, list[dict]] | None = None,  # NEU
) -> dict:
```

2.2. Neuer Code-Block im Loop (VOR dem ModIndex-Check, Zeile 106):
```python
# Versuch 1: pak_file_lists (BG3 .pak-Archive)
if pak_file_lists is not None and mod_name in pak_file_lists:
    for finfo in pak_file_lists[mod_name]:
        rel = finfo["rel"]
        fname = rel.rsplit("/", 1)[-1] if "/" in rel else rel
        if fname in self._INTERNAL_FILES:
            continue
        dot_pos = fname.rfind(".")
        ext = fname[dot_pos:].lower() if dot_pos >= 0 else ""
        if ext in self._IGNORED_EXTENSIONS:
            continue
        owners = file_owners.setdefault(rel, [])
        owners.append(mod_name)
    continue
```

Identische Filter-Logik wie beim ModIndex-Pfad (INTERNAL_FILES, IGNORED_EXTENSIONS).
Bestehende Spiele sind nicht betroffen (pak_file_lists ist None).

**Schritt 3: BG3 Plugin erweitern (`anvil/plugins/games/game_baldursgate3.py`)**

3.1. `get_conflict_ignores()` erweitern:
```python
def get_conflict_ignores(self) -> list[str]:
    return [
        "**/info.json",
        "**/readme*.txt",
        "**/meta.lsx",        # NEU: Mod-Metadaten in jedem .pak
    ]
```

**Schritt 4: mainwindow.py — BG3 Konflikt-Daten bauen**

4.1. Neue Methode `_build_bg3_file_lists()`:
```python
def _build_bg3_file_lists(self) -> dict[str, list[dict]]:
    """Liest Datei-Listen aus allen BG3 .pak-Dateien.
    
    Returns:
        Dict: UUID -> [{"rel": "pfad", "size": N}, ...]
        Pfade sind lowercase-normalisiert (BG3 laeuft unter Proton/Windows).
    """
```
- Greift auf `self._bg3_installer._mods_path` zu (= proton-prefix Mods/ Ordner)
- Iteriert ueber alle .pak-Dateien mit `mods_path.glob("*.pak")`
- Fuer jede .pak: `LSPKReader().read_pak_full(pak)` aufrufen
- Normalisiert alle `rel`-Werte zu `.lower()` (case-insensitive Vergleich)
- Mapped UUID -> file_list
- Ueberspringt .pak ohne gueltige UUID (korrupte Dateien, Vanilla-Reste)
- Beachtet: Nur .pak im Hauptverzeichnis, NICHT aus `.disabled/`

4.2. `_compute_conflict_data()` erweitern (Zeile 1411):
- BG3-Erkennung: `if self._bg3_installer is not None:`
- BG3-Pfad: `pak_file_lists = self._build_bg3_file_lists()`
- BG3 all_mods: `{"name": e.name, "path": ""}` — path wird nicht benoetigt
- Filter: `e.enabled and not e.is_separator and not e.is_data_override`
- Uebergabe an ConflictScanner: `pak_file_lists=pak_file_lists`
- Nicht-BG3-Pfad bleibt unberuehrt

4.3. `_bg3_reload_mod_list()` Zeile 5224 anpassen:
```python
# ALT:
mod_rows = [mod_entry_to_row(e) for e in entries]

# NEU:
conflict_data = self._compute_conflict_data()
mod_rows = [mod_entry_to_row(e, conflict_data) for e in entries]
```

**Schritt 5: Import pruefen**
- `from anvil.core.lspk_parser import LSPKReader` muss in mainwindow.py vorhanden sein
- `LSPKReader` ist wahrscheinlich bereits importiert (wird fuer BG3 Installation genutzt)

### Signal-Flow (BG3 Konflikt-Erkennung)

```
_bg3_reload_mod_list()
  |
  +-> self._bg3_installer.get_mod_list()
  |     -> ModEntry-Liste (UUID als name)
  |
  +-> self._compute_conflict_data()
  |     |
  |     +-> self._build_bg3_file_lists()
  |     |     |
  |     |     +-> mods_path.glob("*.pak")
  |     |     +-> LSPKReader.read_pak_full(pak) fuer jede .pak
  |     |     |     +-> _read_entries(f)  [Header + LZ4-Dekompression]
  |     |     |     +-> Metadata (UUID) + File-Liste
  |     |     +-> {UUID: [{"rel": "pfad".lower(), "size": N}]}
  |     |
  |     +-> ConflictScanner().scan_conflicts(
  |     |       all_mods,
  |     |       self._current_plugin,  [-> get_conflict_ignores()]
  |     |       pak_file_lists=bg3_files
  |     |   )
  |     |     +-> file_owners Dict aufbauen (rel_path -> [uuid1, uuid2])
  |     |     +-> Konflikte erkennen (len(owners) >= 2)
  |     |     +-> Winner = letzter in Liste (hoechste Prioritaet)
  |     |
  |     +-> per_mod Aggregation (wins/losses/type)
  |
  +-> mod_entry_to_row(entry, conflict_data) fuer jede Entry
  |     +-> conflicts = conflict_data.get(entry.name)  [UUID-basiert]
  |
  +-> model.set_mods(mod_rows)
        +-> UI zeigt Icons (gruen/rot/gelb) + Tooltips
```

### Trigger-Zeitpunkte
Alle folgenden Aktionen fuehren zu `_bg3_reload_mod_list()` und loesen damit einen Konflikt-Scan aus:
1. Instanz-Wechsel auf BG3
2. Mod aktiviert/deaktiviert
3. Mod installiert
4. Mod-Reihenfolge geaendert (Drag&Drop)
5. Profil-Wechsel

### Prioritaets-Reihenfolge bei BG3
BG3-Mods in `_current_mod_entries` haben eine definierte Reihenfolge (Index 0 = niedrigste Prio, letzter = hoechste). Diese Reihenfolge wird vom ConflictScanner genutzt: `owners[-1]` = Winner. Die Reihenfolge stammt aus `modsettings.lsx` bzw. der Anvil-Mod-Liste.

### Case-Sensitivity
BG3 .pak-Dateien stammen von Windows. Zwei Mods koennten `Public/MyMod/Content/File.lsf` und `public/mymod/content/file.lsf` haben — auf Windows waere das ein Konflikt. Daher werden alle `rel`-Werte in `_build_bg3_file_lists()` zu `.lower()` normalisiert. Diese Normalisierung betrifft NUR BG3-Daten, nicht regulaere Spiele.

### Data-Override-Mods
Data-Override-Mods (`is_data_override=True`) werden in Phase 1 NICHT in den Konflikt-Scan einbezogen. Sie haben keine .pak-Dateien und werden direkt in `<game>/Data/` installiert. Eine separate Behandlung waere moeglich, ist aber ein eigenes Feature.

---

## Verwandte Funktionen (geprueft)

| Funktion | Gleicher Fix noetig? | Begruendung |
|----------|---------------------|-------------|
| `conflict_scanner.py: _match_ignore()` | Nein | Funktioniert korrekt fuer pattern-basiertes Filtern, auch fuer .pak-interne Pfade |
| `conflict_scanner.py: scan_conflicts()` | Ja | Neuer Parameter `pak_file_lists`, neuer Code-Block im Loop |
| `modindex.py: rebuild()` | Nein | Wird fuer BG3 nicht verwendet |
| `modindex.py: get_file_list()` | Nein | Wird fuer BG3 nicht verwendet (pak_file_lists stattdessen) |
| `mod_list_model.py: mod_entry_to_row()` | Nein | Funktioniert wenn conflict_data korrekt uebergeben wird |
| `mod_list_model.py: data() DecorationRole` | Nein | Zeigt Icons wenn `r.conflicts` ein Dict ist |
| `mod_list_model.py: data() ToolTipRole` | Nein | Zeigt Tooltip wenn `r.conflicts` ein Dict ist |
| `lspk_parser.py: _read()` | Ja | Refactoring: `_read_entries()` extrahieren |
| `lspk_parser.py: read_pak_metadata()` | Nein | Aendert sich nicht (nutzt intern `_read()` wie bisher) |
| `game_baldursgate3.py: get_conflict_ignores()` | Ja | `**/meta.lsx` hinzufuegen |
| `mainwindow.py: _compute_conflict_data()` | Ja | BG3-spezifischer Pfad |
| `mainwindow.py: _bg3_reload_mod_list()` | Ja | Zeile 5224 mit conflict_data |
| `bg3_mod_installer.py` | Nein | Installation unveraendert |

---

## MO2-Vergleich

MO2 unterstuetzt BG3 nicht nativ (kein .pak-Parsing). Die BG3-Unterstuetzung in MO2 laeuft ueber Community-Plugins, die .pak-Dateien als opake Blobs behandeln. Anvil wird damit die ERSTE Implementierung sein, die echte .pak-interne Konflikte erkennt.

Der bestehende ConflictScanner in Anvil ist bereits besser als MO2's Standard-Ansatz (relative Pfade statt Dateinamen). Die Erweiterung um `pak_file_lists` ist eine natuerliche Ergaenzung.

---

## Phase 2: PakFileIndex (spaeter, wenn Performance >300ms)

Separater Cache `anvil/core/pak_file_index.py` mit JSON-Datei `.bg3_pakindex.json` im Instanz-Verzeichnis. Invalidierung ueber mtime der .pak-Datei. Erster Scan ~170ms, danach <10ms. Wird NUR implementiert wenn Phase 1 Performance-Probleme zeigt.

---

## Akzeptanz-Checkliste

- [ ] Wenn User eine BG3-Instanz oeffnet mit 2+ Mods die gleiche .pak-interne Dateipfade haben, erscheinen Konflikt-Icons (gruen/rot/gelb) in der Conflicts-Spalte der Mod-Liste
- [ ] Wenn User ueber ein Konflikt-Icon hovert, zeigt der Tooltip die Anzahl gewonnener/verlorener Konflikte und die beteiligten Mod-Namen
- [ ] Wenn User die Mod-Reihenfolge per Drag&Drop aendert, aktualisieren sich die Konflikt-Icons entsprechend (der Mod weiter unten in der Liste gewinnt)
- [ ] Wenn User einen BG3-Mod deaktiviert, verschwindet er aus den Konflikten der anderen Mods
- [ ] Wenn User einen BG3-Mod aktiviert, werden seine Konflikte mit allen anderen aktiven Mods berechnet
- [ ] Wenn User eine Skyrim/Cyberpunk/Witcher-Instanz oeffnet, funktioniert die Konflikt-Erkennung identisch wie vor dieser Aenderung (Regression-Test)
- [ ] Wenn eine .pak-Datei korrupt ist (falsches Magic, zu kurzer Header, LZ4-Fehler), wird sie uebersprungen ohne Crash — die restlichen .pak werden normal gescannt
- [ ] Wenn eine .pak-Datei nur `meta.lsx` und `info.json` enthaelt, werden diese durch `get_conflict_ignores()` als harmlos gefiltert und erscheinen NICHT als Konflikte
- [ ] Wenn zwei .pak-Dateien `Public/Shared/Stats/Generated/Data/Armor.txt` enthalten (eine in Grossbuchstaben, eine in Kleinbuchstaben), wird das als Konflikt erkannt (case-insensitive Vergleich)
- [ ] Wenn eine BG3-Instanz keine .pak-Mods hat (leerer Mods-Ordner oder kein Proton-Prefix), zeigt die Mod-Liste keine Konflikt-Icons und es gibt keinen Fehler
- [ ] Wenn der BG3 Mods-Ordner 86+ .pak-Dateien enthaelt, dauert der Konflikt-Scan weniger als 500ms (gemessen von Beginn `_build_bg3_file_lists()` bis Ende `_compute_conflict_data()`)
- [ ] Wenn User das Profil wechselt, werden die Konflikte fuer das neue Profil (mit dessen aktiven Mods) neu berechnet
- [ ] Separatoren und Data-Override-Mods erscheinen NICHT im Konflikt-Scan
- [ ] `LSPKReader.read_pak_full()` gibt ein Tuple `(metadata, file_list)` zurueck — metadata ist ein Dict oder None, file_list ist eine Liste von `{"rel": str, "size": int}`
- [ ] `LSPKReader.read_pak_metadata()` funktioniert weiterhin unveraendert (keine Regression durch das _read_entries()-Refactoring)
- [ ] Alle .pak in `.disabled/` werden NICHT gescannt (nur aktive .pak im Hauptordner)
- [ ] `restart.sh` startet ohne Fehler
