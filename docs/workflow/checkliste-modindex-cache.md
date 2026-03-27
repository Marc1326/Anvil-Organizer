# Feature-Spec: modindex.bin Caching (Issue #69)

## Analyse

### Problem
Bei jedem Instanz-Wechsel, Profil-Wechsel, Mod-Installation und Deploy werden
alle Mod-Ordner rekursiv gescannt (`rglob("*")`). Bei 100+ Mods mit jeweils
hunderten Dateien dauert das mehrere Sekunden.

### Hotspots (3x redundanter rglob)
1. **`mod_entry.py:_count_files()`** — zaehlt Dateien + Groesse fuer jede ModEntry
2. **`conflict_scanner.py:scan_conflicts()`** — baut file_owners dict fuer Konflikte
3. **`mod_deployer.py:deploy()`** — iteriert Mod-Dateien fuer Symlink-Erstellung

### MO2-Referenz
MO2 nutzt `DirectoryRefresher` + `DirectoryEntry` als zentrale Datenstruktur.
Alle Mod-Dateien werden einmal gescannt und in einem Tree gespeichert.
Conflict-Detection und VFS arbeiten auf diesem Tree statt erneut zu scannen.

## Design

### Neues Modul: `anvil/core/modindex.py`

**ModIndex** — zentraler Dateisystem-Cache pro Instanz.

```
modindex.bin (msgpack/JSON):
{
  "version": 1,
  "mods": {
    "ModName": {
      "mtime": 1711234567.89,     # aeltestes mtime aus dem Ordner
      "size_marker": 12345,        # Summe aller Dateigroessen
      "files": [
        {"rel": "textures/foo.dds", "size": 1024},
        {"rel": "meshes/bar.nif", "size": 2048}
      ]
    }
  }
}
```

**Invalidierung:**
- Pro Mod: `os.stat(mod_dir).st_mtime` vergleichen
- Wenn mtime gleich -> Cache-Hit, Dateiliste aus Cache
- Wenn mtime anders -> Mod neu scannen, Cache updaten
- Mod geloescht -> aus Cache entfernen
- Neuer Mod -> scannen und hinzufuegen

**Cache-Datei:** `instance_path/.modindex.json` (JSON statt binary fuer Debugging)

### Integration

1. `ModIndex.get_file_list(mod_name)` ersetzt `mod_dir.rglob("*")` ueberall
2. `ModIndex.get_file_count(mod_name)` + `get_total_size(mod_name)` fuer mod_entry
3. `ModIndex.rebuild_if_needed()` beim Instanz-Laden aufrufen
4. `ModIndex.invalidate(mod_name)` nach Install/Delete/Rename
5. `ModIndex.clear()` fuer manuelles Cache-Leeren (Settings-Button)

### Nicht anfassen:
- Game-Plugins (keine Aenderungen)
- BG3-Code
- Cover-Bilder, Icons, redprelauncher, REDmod

## Akzeptanz-Checkliste

### Kern-Funktionalitaet
- [ ] 1. Wenn User eine Instanz oeffnet, wird modindex.json geladen und nur geaenderte Mods werden neu gescannt (statt alle)
- [ ] 2. Wenn User einen neuen Mod installiert, wird der Cache fuer diesen Mod sofort aktualisiert und die Dateiliste stimmt
- [ ] 3. Wenn User einen Mod loescht, wird der Mod aus dem Cache entfernt
- [ ] 4. Wenn User einen Mod umbenennt, wird der Cache-Eintrag unter dem neuen Namen gespeichert
- [ ] 5. Wenn der Deployer deployed, nutzt er die gecachten Dateilisten statt erneut rglob aufzurufen
- [ ] 6. Wenn der ConflictScanner Konflikte berechnet, nutzt er die gecachten Dateilisten statt erneut rglob aufzurufen
- [ ] 7. Wenn die ModEntry-Liste gebaut wird (file_count/total_size), werden die Werte aus dem Cache gelesen

### Invalidierung
- [ ] 8. Wenn ein Mod-Ordner sich aendert (Datei hinzugefuegt/geloescht), erkennt der Cache beim naechsten Rebuild die Aenderung anhand des mtime
- [ ] 9. Wenn modindex.json nicht existiert (erster Start), wird ein vollstaendiger Scan durchgefuehrt und die Cache-Datei erstellt
- [ ] 10. Wenn modindex.json korrupt ist (JSON-Fehler), wird ein vollstaendiger Scan durchgefuehrt ohne Absturz

### Manuelles Leeren
- [ ] 11. Wenn User in Settings "Cache leeren" klickt, wird modindex.json geloescht und beim naechsten Laden neu aufgebaut

### Performance
- [ ] 12. Wenn alle Mods gecacht sind (kein Mod geaendert), dauert der Rebuild unter 100ms (statt mehrere Sekunden)

### Stabilitaet
- [ ] 13. restart.sh startet ohne Fehler
