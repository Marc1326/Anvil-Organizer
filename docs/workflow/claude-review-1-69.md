# Claude Review 1 — Issue #69: ModIndex Caching

## Reviewer: Architektur & Code-Review
## Datum: 2026-03-26
## Branch: feat/issue-69

## Architektur-Bewertung

### Neues Modul: anvil/core/modindex.py
- **Kapselung**: Gut — ModIndex ist eine eigenstaendige Klasse mit klarem API
- **Dependency Direction**: Korrekt — modindex.py hat keine Abhaengigkeiten zu
  anderen Anvil-Modulen (nur stdlib). Consumers importieren ModIndex via TYPE_CHECKING.
- **MO2-Inspiration**: Folgt dem MO2-Pattern (DirectoryRefresher als zentrale
  Datenquelle) ohne es blind zu kopieren.

### Pattern: Optional Parameter mit Fallback
Alle drei Consumer (mod_entry, conflict_scanner, mod_deployer) haben
`mod_index: ModIndex | None = None` als optionalen Parameter.
Das ist das richtige Pattern:
- Rueckwaerts-kompatibel
- Keine harten Abhaengigkeiten
- Testbar ohne ModIndex

### TYPE_CHECKING Imports
Korrekt eingesetzt in mod_entry.py, conflict_scanner.py, mod_deployer.py.
Verhindert zirkulaere Imports zur Laufzeit.

## Code-Review Findings

### Finding 1: `_walk_files` koennte effizienter sein (Minor)
`_walk_files` liefert `Path`-Objekte, die dann in `_scan_mod` wieder
`relative_to` und `as_posix()` aufgerufen werden. Man koennte direkt
Strings liefern. Aber: Der Code ist klar und die Performance ist
bereits excellent (1ms fuer 14 Mods). **Kein Fix noetig**.

### Finding 2: `cached_count` Variable in rebuild() (Cosmetic)
Zeile 117-118:
```python
total_mods = len(self._index)
cached_count = total_mods - len(stale)
```
`cached_count` wird berechnet aber nie verwendet. Wurde vermutlich
aus der Log-Ausgabe entfernt. Kosmetisch, **kein Fix noetig**.

### Finding 3: Doppelte Speicherung bei invalidate/rename (Design Decision)
`invalidate()`, `invalidate_and_rescan()` und `rename()` rufen jeweils
direkt `_save_cache()` auf. Bei Batch-Operationen (mehrere Mods loeschen)
wird der Cache mehrfach geschrieben. Das ist akzeptabel da:
- Delete-Operationen selten sind
- JSON-Serialisierung fuer 14 Mods minimal ist
- Korrektheit > Performance bei seltenen Operationen
**Kein Fix noetig**.

### Finding 4: ConflictScanner Cache-Path skippt game_plugin Ignores nicht frueher
Im Cache-Pfad des ConflictScanners werden `_INTERNAL_FILES` und
`_IGNORED_EXTENSIONS` gefiltert, aber die `ignore_patterns` vom
Game-Plugin werden erst spaeter in der gemeinsamen Schleife angewendet.
Das ist **korrekt** — die Plugin-Ignores werden am Ende auf alle
file_owners angewendet, egal ob aus Cache oder Filesystem.

### Finding 5: Deployer file_iter enthaelt auch Directories (Abgefangen)
Im Deployer:
```python
file_iter = (mod_dir / finfo["rel"] for finfo in cached_files)
for src_file in file_iter:
    if not src_file.is_file():
        continue
```
Die `cached_files` enthalten nur Files (nicht Dirs), da `_walk_files`
nur Files yielded. Der `is_file()` Check ist ein zusaetzlicher Safety-Net.
**Korrekt**.

## Checkliste-Pruefung (Kurzform)

| Nr | Kriterium | Status |
|----|-----------|--------|
| 1  | Instanz oeffnen -> nur geaenderte Mods | PASS |
| 2  | Neuer Mod -> Cache aktualisiert | PASS |
| 3  | Mod geloescht -> aus Cache entfernt | PASS |
| 4  | Mod umbenennt -> Cache-Eintrag uebernommen | PASS |
| 5  | Deployer nutzt Cache | PASS |
| 6  | ConflictScanner nutzt Cache | PASS |
| 7  | ModEntry aus Cache | PASS |
| 8  | mtime-Invalidierung | PASS |
| 9  | Erster Start ohne Cache | PASS |
| 10 | Korruptes JSON -> kein Crash | PASS |
| 11 | Settings "Cache leeren" | PASS |
| 12 | Performance < 100ms | PASS (1ms) |
| 13 | App startet ohne Fehler | PASS |

## Ergebnis

**ACCEPTED** — Saubere Architektur, keine kritischen Findings.
Alle 13 Checklisten-Punkte bestanden.
