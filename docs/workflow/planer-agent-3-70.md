# Planer Agent 3: Architektur + Signal-Flow
Issue: #70 — Collection/Modpack Export + Import
Datum: 2026-03-26

## Neue Dateien

### 1. `anvil/core/collection_io.py` — Backend-Logik
- `export_collection()` — Erstellt .anvilpack ZIP
- `import_collection()` — Liest .anvilpack und gibt Manifest + fehlende Mods zurueck
- `CollectionManifest` — Dataclass mit Metadaten

### 2. `anvil/dialogs/collection_export_dialog.py` — Export-Dialog
- Zeigt Zusammenfassung: Anzahl Mods, Separatoren, Game-Info
- Optional: Notizen/Beschreibung eingeben
- Datei-Speichern-Dialog

### 3. `anvil/dialogs/collection_import_dialog.py` — Import-Dialog
- Zeigt Manifest-Info: Game, Ersteller, Datum, Mod-Anzahl
- Liste fehlender Mods mit Nexus-Links (klickbar)
- Liste vorhandener Mods (bereits installiert)
- Optionen: "Reihenfolge uebernehmen", "Kategorien uebernehmen"
- Best/Confirm-Buttons

## .anvilpack Format (ZIP-Archiv)

```
collection.anvilpack (ZIP)
+-- manifest.json          # Metadaten, Game-Info, Mod-Liste
+-- categories.json        # Kategorie-Definitionen (optional)
```

### manifest.json Struktur:
```json
{
  "anvil_version": "1.1.0",
  "format_version": 1,
  "game": {
    "name": "Cyberpunk 2077",
    "short_name": "cyberpunk2077",
    "nexus_name": "cyberpunk2077"
  },
  "collection": {
    "name": "Mein Modpack",
    "description": "Beschreibung...",
    "author": "Username",
    "created": "2026-03-26T12:00:00Z"
  },
  "mods": [
    {
      "name": "FolderName",
      "display_name": "Hübscher Name",
      "enabled": true,
      "is_separator": false,
      "nexus_id": 12345,
      "version": "1.2.3",
      "author": "ModAuthor",
      "url": "https://...",
      "category_ids": [6, 10],
      "color": ""
    }
  ]
}
```

## Signal-Flow

### Export:
```
ProfileBar-Menue "Collection exportieren"
  -> export_collection_requested Signal
  -> MainWindow._export_collection()
  -> CollectionExportDialog (Name, Beschreibung eingeben)
  -> collection_io.export_collection(instance_path, profile_path, manifest)
  -> QFileDialog.getSaveFileName()
  -> ZIP erstellen -> Toast "Collection exportiert"
```

### Import:
```
ProfileBar-Menue "Collection importieren"
  -> import_collection_requested Signal
  -> MainWindow._import_collection()
  -> QFileDialog.getOpenFileName()
  -> collection_io.read_collection_manifest(zip_path)
  -> CollectionImportDialog (Zusammenfassung, fehlende Mods)
  -> User bestaetigt
  -> collection_io.apply_collection(...)
  -> Modliste + Kategorien ueberschreiben
  -> _reload_mod_list() + _do_redeploy()
  -> Toast "Collection importiert, N Mods fehlen"
```

## Integration in bestehendes UI
- ProfileBar: 2 neue Signal-Eintraege im Dots-Menue (nach "Export CSV")
- MainWindow: 2 neue Methoden (_export_collection, _import_collection)
- Menue-Bar (Datei): 2 neue Eintraege

## Betroffene Dateien (Aenderungen)
| Datei | Aenderung |
|---|---|
| `anvil/core/collection_io.py` | NEU — Backend-Logik |
| `anvil/dialogs/collection_export_dialog.py` | NEU — Export-Dialog |
| `anvil/dialogs/collection_import_dialog.py` | NEU — Import-Dialog |
| `anvil/widgets/profile_bar.py` | 2 neue Signals + Menue-Eintraege |
| `anvil/mainwindow.py` | 2 neue Methoden + Signal-Verbindungen + Menue |
| `anvil/locales/*.json` (7 Dateien) | Neue Uebersetzungs-Keys |
