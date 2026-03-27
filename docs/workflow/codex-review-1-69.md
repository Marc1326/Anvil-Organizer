# Codex Review 1 — Issue #69: ModIndex Caching

## Reviewer: Code-Qualitaet & Logik
## Datum: 2026-03-26
## Branch: feat/issue-69

## Geprueft gegen Checkliste

### 1. Instanz oeffnen -> nur geaenderte Mods scannen
**PASS** — `ModIndex.rebuild()` laedt den Cache von Disk, vergleicht `st_mtime` pro Mod-Ordner
und re-scannt nur bei Aenderung. Bestaetigt durch Log: `[ModIndex] rebuild: 14 mods, 0.001s`
bei zweitem Aufruf (alle gecacht).

### 2. Neuer Mod -> Cache aktualisiert
**PASS** — `rebuild()` entdeckt neue Mods via `on_disk - self._index.keys()` und scannt sie.
`invalidate_and_rescan()` existiert fuer sofortige Aktualisierung.

### 3. Mod geloescht -> aus Cache entfernt
**PASS** — `invalidate(mod_name)` entfernt den Eintrag und speichert.
`mainwindow.py` ruft `self._mod_index.invalidate(name)` im Delete-Handler.
`rebuild()` entfernt auch stale entries: `stale = set(self._index.keys()) - on_disk`.

### 4. Mod umbenennt -> Cache-Eintrag uebernommen
**PASS** — `rename(old, new)` verschiebt den `_ModCache`-Eintrag.
`mainwindow.py` ruft `self._mod_index.rename(old_name, new_name)` im Rename-Handler.

### 5. Deployer nutzt Cache
**PASS** — `mod_deployer.py` hat `mod_index` Parameter, baut `file_iter` aus Cache
wenn verfuegbar, faellt auf `rglob("*")` zurueck wenn nicht.

### 6. ConflictScanner nutzt Cache
**PASS** — `conflict_scanner.py` hat `mod_index` Parameter, iteriert `cached_files`
mit inline Filename/Extension-Extraktion fuer Filter-Checks. Fallback auf `rglob("*")`.

### 7. ModEntry file_count/total_size aus Cache
**PASS** — `mod_entry.py:_build_entry()` ruft `mod_index.get_stats(name)` auf wenn
mod_index vorhanden, sonst `_count_files(mod_path)`.

### 8. mtime-Invalidierung bei Aenderung
**PASS** — `os.stat(mod_dir).st_mtime` wird pro Mod verglichen.
Neue/geloeschte Dateien aendern den Ordner-mtime auf Linux.

### 9. Erster Start ohne Cache
**PASS** — `_load_cache()` erkennt fehlende Datei: `if not self._cache_path.is_file(): return`.
Alle Mods werden dann gescannt.

### 10. Korruptes JSON -> kein Absturz
**PASS** — `_load_cache()` faengt `json.JSONDecodeError` und `ValueError`,
setzt `self._index.clear()` und `self._dirty = True`. Getestet:
"modindex: cache corrupt, will rebuild: ..."

### 11. Settings "Cache leeren"
**PASS** — Button in `settings_dialog.py`, verbunden mit `_clear_modindex_cache()` in
`mainwindow.py`, ruft `self._mod_index.clear()` auf.

### 12. Performance < 100ms bei gecachten Mods
**PASS** — Gemessen: 0.001s (1ms) fuer 14 Mods. Weit unter 100ms.

### 13. App startet ohne Fehler
**PASS** — Getestet, keine Tracebacks. Nur bekannte QTabBar-Warnings.

## Code-Qualitaet Findings

### Finding 1: `_walk_files` liefert `meta.ini` mit
Der Cache speichert ALLE Dateien inklusive `meta.ini`, `codes.txt` etc.
Das ist korrekt — der ConflictScanner filtert sie nachtraeglich.
Der Deployer filtert `_SKIP_FILES` ebenfalls eigenstaendig.
**Kein Bug**, aber gut zu dokumentieren.

### Finding 2: Keine Thread-Safety
`ModIndex` hat keine Locks. Da Anvil single-threaded (Qt main thread) arbeitet,
ist das kein Problem. Sollte aber dokumentiert sein fuer die Zukunft.
**Kein Bug**, kein Fix noetig.

### Finding 3: `cached_count` Variable in `rebuild()` ist falsch berechnet
Zeile 118: `cached_count = total_mods - len(stale)` — `stale` sind die geloeschten Mods,
nicht die neu gescannten. Die Variable wird aber nicht verwendet (nur in der
Logausgabe nicht mehr). **Kein Auswirkung**, da die Variable nie geloggt wird.

## Ergebnis

**ACCEPTED** — Alle 13 Checklisten-Punkte bestanden. Keine kritischen Findings.
