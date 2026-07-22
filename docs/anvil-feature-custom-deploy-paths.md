# Feature: Custom Deploy Paths pro Separator (Issue #67)
Datum: 2026-03-26

## Zusammenfassung

Separatoren koennen optional einen eigenen Deploy-Pfad haben. Mods innerhalb eines Separators werden dann in diesen Pfad statt in den globalen Game-Pfad deployed. Separatoren ohne eigenen Pfad nutzen den globalen Deploy-Pfad (Fallback). Dies ermoeglicht z.B. verschiedene Mod-Gruppen in verschiedene Zielordner zu deployen.

**Alleinstellungsmerkmal:** MO2 hat KEIN Per-Separator Deploy-Path Feature. MO2 nutzt USVFS und `getModMappings()` auf Game-Plugin-Ebene. Anvils Custom Deploy Paths waere ein echtes Unterscheidungsmerkmal.

## User Stories

- Als User moechte ich per Rechtsklick auf einen Separator einen eigenen Deploy-Pfad setzen koennen.
- Als User moechte ich, dass Mods innerhalb dieses Separators in den Custom-Pfad deployed werden statt ins Game-Verzeichnis.
- Als User moechte ich den Custom-Pfad eines Separators zuruecksetzen koennen (Fallback auf globalen Pfad).
- Als User moechte ich im Kontextmenue sehen, welcher Separator einen Custom-Pfad hat.
- Als User moechte ich, dass Purge korrekt funktioniert — auch bei Custom-Pfaden.

## Technische Planung

### Design-Entscheidung: Deploy-Pfad in meta.ini

Analog zum Separator-Color-Pattern wird der Deploy-Pfad in der `meta.ini` des Separators gespeichert:

```ini
[General]
color=#4FC3F7
deploy_path=/mnt/games/custom-mods/
```

**Regeln:**
- `deploy_path` ist nur fuer Separatoren relevant
- Leerer oder fehlender Wert = globaler Game-Pfad (Fallback)
- Der Pfad muss ein existierendes Verzeichnis sein (Validierung bei Setzen)
- Cross-Filesystem-Symlinks sind unter Linux unterstuetzt (ext4, btrfs), aber NICHT auf NTFS/FAT32 Mount-Points

### Geaenderte Dateien

| Datei | Aenderung | Aufwand |
|-------|-----------|---------|
| `anvil/core/mod_deployer.py` | Neuer Parameter `separator_deploy_paths: dict[str, str]`, Separator-Tracking in deploy-Loop, `deploy_base` pro Manifest-Eintrag, Purge-Erweiterung | HOCH |
| `anvil/core/mod_entry.py` | Neues Feld `deploy_path: str = ""` (nur Separatoren) | MINIMAL |
| `anvil/mainwindow.py` | Kontextmenue: "Deploy-Pfad setzen..." + "Deploy-Pfad zuruecksetzen", Handler (Pattern von Separator-Color) | MITTEL |
| `anvil/widgets/game_panel.py` | Separator-Deploy-Paths aus ModEntries extrahieren, an Deployer uebergeben | MITTEL |
| 7 Locale-Dateien | ~5 neue tr()-Keys | KLEIN |

**NICHT betroffen:** mod_list_io.py, conflict_scanner.py, Game-Plugins, mod_groups.py

### Signal-Flow

#### Deploy-Pfad setzen
```
User rechtsklickt auf Separator → "Deploy-Pfad setzen..."
  → MainWindow._ctx_set_deploy_path()
    → QFileDialog.getExistingDirectory()
    → write_meta_ini(separator_path, {"deploy_path": chosen_path})
    → ModEntry.deploy_path = chosen_path
    → ModRow.deploy_path aktualisieren
```

#### Deploy-Pfad zuruecksetzen
```
User rechtsklickt auf Separator → "Deploy-Pfad zuruecksetzen"
  → MainWindow._ctx_reset_deploy_path()
    → write_meta_ini(separator_path, {"deploy_path": ""})
    → ModEntry.deploy_path = ""
```

#### Deploy mit Custom Paths
```
silent_deploy()
  → game_panel extrahiert separator_deploy_paths aus ModEntries:
    {separator_name: deploy_path}
  → ModDeployer(... separator_deploy_paths=separator_deploy_paths)
  → deploy():
    → Iteriert enabled_mods
    → Trackt aktuellen Separator
    → Wenn Separator deploy_path hat: target = deploy_path / rel
    → Sonst: target = game_path / rel (Fallback)
    → Manifest-Eintrag erhaelt "deploy_base" Feld
```

#### Purge mit Custom Paths
```
purge()
  → Liest Manifest
  → Pro Eintrag: deploy_base bestimmt den Basis-Pfad
  → Wenn deploy_base leer/fehlend: game_path (Fallback)
  → Sonst: deploy_base als Basis fuer link_path-Aufloesung
  → Leere Verzeichnisse nur in den jeweiligen deploy_base aufräumen
```

### Deployer-Aenderungen im Detail

**Neuer Parameter:**
```python
def __init__(self, ..., separator_deploy_paths: dict[str, str] | None = None):
    self._separator_deploy_paths = separator_deploy_paths or {}
```

**Separator-Tracking in deploy():**
```python
current_separator = ""
for mod_name, _priority in enabled_mods:
    if mod_name.endswith("_separator"):
        current_separator = mod_name
        continue

    # Bestimme deploy_base fuer diesen Mod
    sep_path = self._separator_deploy_paths.get(current_separator, "")
    deploy_base = Path(sep_path) if sep_path else self._game_path

    # ... rest der deploy-Logik, aber mit deploy_base statt self._game_path
    target = deploy_base / rel
```

**Manifest-Erweiterung:**
```json
{
  "symlinks": [
    {
      "link": "Data/textures/mod.dds",
      "target": "/home/user/.mods/MyMod/textures/mod.dds",
      "mod": "MyMod",
      "type": "symlink",
      "deploy_base": "/mnt/games/custom-mods/"
    }
  ]
}
```

### GUI-Darstellung

Separator mit Custom Deploy-Pfad zeigt den Pfad als Tooltip:
```
[Weapons_separator]           ← Tooltip: "Deploy → /mnt/games/custom-mods/"
  Cool Armor Mod
  Cool Armor Patch
[Other_separator]             ← Kein Custom-Pfad, nutzt Game-Pfad
  Another Mod
```

## Risiken

| # | Risiko | Schwere | Mitigation |
|---|--------|---------|------------|
| R1 | Cross-FS Symlinks (NTFS/FAT32) | HOCH | Warnung bei Setzen, symlink-Test vor Deploy |
| R2 | Purge bei geaendertem deploy_path | HOCH | Manifest speichert deploy_base — Purge nutzt Manifest-Werte |
| R3 | Separator geloescht mit Custom-Pfad | MITTEL | Manifest-basiertes Purge funktioniert unabhaengig |
| R4 | data_path / multi_folder_routes mit Custom-Path | MITTEL | Custom deploy_path ersetzt NUR game_path, data_path/routes gelten weiter |
| R5 | BA2-Packing mit Custom-Paths | NIEDRIG | BA2-Packing ignoriert Custom-Paths (nur game_path) |

## Locale-Keys (alle 7 Sprachen)

| Key | DE | EN |
|-----|----|-----|
| `context.set_deploy_path` | "Deploy-Pfad setzen..." | "Set deploy path..." |
| `context.reset_deploy_path` | "Deploy-Pfad zuruecksetzen" | "Reset deploy path" |
| `dialog.deploy_path_title` | "Deploy-Pfad waehlen" | "Choose deploy path" |
| `dialog.deploy_path_set` | "Deploy-Pfad fuer '{name}' gesetzt: {path}" | "Deploy path for '{name}' set: {path}" |
| `dialog.deploy_path_reset` | "Deploy-Pfad fuer '{name}' zurueckgesetzt." | "Deploy path for '{name}' reset." |

## Akzeptanz-Kriterien

- [ ] 1. Wenn User auf einen Separator rechtsklickt, erscheint "Deploy-Pfad setzen..." im Kontextmenue.
- [ ] 2. Wenn User "Deploy-Pfad setzen..." waehlt, oeffnet sich ein QFileDialog zur Verzeichnisauswahl.
- [ ] 3. Wenn User einen Pfad waehlt, wird dieser in der meta.ini des Separators gespeichert.
- [ ] 4. Wenn User deployed, werden Mods innerhalb des Separators in den Custom-Pfad deployed statt ins Game-Verzeichnis.
- [ ] 5. Wenn User deployed und der Separator KEINEN Custom-Pfad hat, wird der globale Game-Pfad verwendet (Fallback).
- [ ] 6. Wenn User purged, werden Symlinks korrekt aus dem Custom-Pfad entfernt (Manifest-basiert).
- [ ] 7. Wenn User "Deploy-Pfad zuruecksetzen" waehlt, wird der Custom-Pfad entfernt und der globale Pfad wiederverwendet.
- [ ] 8. Wenn User Anvil schliesst und oeffnet, ist der Custom-Pfad erhalten (meta.ini).
- [ ] 9. Wenn Kontextmenue auf einem Nicht-Separator geoeffnet wird, sind die Deploy-Pfad-Optionen NICHT sichtbar.
- [ ] 10. Wenn ein Separator einen Custom-Pfad hat, zeigt der Tooltip den Pfad an.
- [ ] 11. Wenn data_path gesetzt ist, wird dieser AUCH bei Custom-Deploy-Pfad angewendet (deploy_base / data_path / rel).
- [ ] 12. Alle 5 Locale-Keys sind in allen 7 Sprach-Dateien vorhanden.
- [ ] 13. `restart.sh` startet ohne Fehler.
