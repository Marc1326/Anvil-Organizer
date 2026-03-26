# Feature: Collection/Modpack Export + Import
Datum: 2026-03-26
Issue: #70

## User Stories
- Als Modder moechte ich mein komplettes Mod-Setup als .anvilpack exportieren, damit ich es mit anderen teilen kann
- Als Modder moechte ich ein geteiltes Modpack importieren und die gleiche Struktur (Separatoren, Reihenfolge, Kategorien) erhalten
- Als Modder moechte ich beim Import sehen welche Mods fehlen und diese ueber Nexus-Links herunterladen

## Technische Planung

### Neue Dateien
| Datei | Zweck |
|---|---|
| `anvil/core/collection_io.py` | Backend: export/import Logik, Manifest-Dataclass |
| `anvil/dialogs/collection_export_dialog.py` | Export-Dialog: Name, Beschreibung, Zusammenfassung |
| `anvil/dialogs/collection_import_dialog.py` | Import-Dialog: Manifest-Info, fehlende Mods, Optionen |

### Geaenderte Dateien
| Datei | Aenderung |
|---|---|
| `anvil/widgets/profile_bar.py` | 2 neue Signals + 2 Menue-Eintraege im Dots-Menue |
| `anvil/mainwindow.py` | 2 neue Methoden + Signal-Verbindungen + Datei-Menue-Eintraege |
| `anvil/locales/de.json` | Neue Keys fuer Collection-Feature |
| `anvil/locales/en.json` | Neue Keys fuer Collection-Feature |
| `anvil/locales/es.json` | Neue Keys fuer Collection-Feature |
| `anvil/locales/fr.json` | Neue Keys fuer Collection-Feature |
| `anvil/locales/it.json` | Neue Keys fuer Collection-Feature |
| `anvil/locales/pt.json` | Neue Keys fuer Collection-Feature |
| `anvil/locales/ru.json` | Neue Keys fuer Collection-Feature |

### .anvilpack Format
- Dateiendung: `.anvilpack`
- Technisch: ZIP-Archiv
- Inhalt: `manifest.json` + optional `categories.json`
- KEINE Mod-Dateien — nur Metadaten + Nexus-IDs

### manifest.json Struktur
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
    "description": "",
    "author": "",
    "created": "2026-03-26T12:00:00Z"
  },
  "mods": [
    {
      "name": "FolderName",
      "display_name": "Anzeigename",
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

### Signal-Flow

#### Export:
```
ProfileBar Dots-Menue -> "Collection exportieren"
  -> export_collection_requested Signal
  -> MainWindow._export_collection()
  -> CollectionExportDialog oeffnen (Name, Beschreibung)
  -> collection_io.export_collection() -> ZIP erstellen
  -> QFileDialog.getSaveFileName() fuer Speicherort
  -> Toast "Collection exportiert"
```

#### Import:
```
ProfileBar Dots-Menue -> "Collection importieren"
  -> import_collection_requested Signal
  -> MainWindow._import_collection()
  -> QFileDialog.getOpenFileName() -> .anvilpack auswaehlen
  -> collection_io.read_collection_manifest() -> Manifest lesen
  -> CollectionImportDialog oeffnen (Info + fehlende Mods)
  -> User bestaetigt
  -> collection_io.apply_collection() -> Modliste + Kategorien anwenden
  -> _reload_mod_list() + _do_redeploy()
  -> Toast "Collection importiert"
```

### MO2-Vergleich
MO2 hat kein eingebautes Collection-Feature. Wabbajack ist ein externes Tool.
Anvil's Ansatz ist simpler: Metadaten + Nexus-IDs exportieren, User laedt Mods selbst.

## Verwandte Funktionen (geprueft)
- `_create_backup()` -> Gleiches ZIP-Pattern, kann als Vorlage dienen
- `_ctx_export_csv()` -> QFileDialog-Pattern wiederverwendbar
- `BackupDialog` -> UI-Pattern fuer Import-Dialog wiederverwendbar

## Akzeptanz-Checkliste

- [ ] 1. Wenn User im Dots-Menue "Collection exportieren" klickt, oeffnet sich ein Export-Dialog mit Eingabefeldern fuer Name und Beschreibung
- [ ] 2. Wenn User im Export-Dialog "Exportieren" klickt und einen Speicherort waehlt, wird eine .anvilpack-Datei erstellt die ein gueltiges ZIP-Archiv ist
- [ ] 3. Wenn User die .anvilpack-Datei entpackt, enthaelt sie eine manifest.json mit korrektem Game-Name, Mod-Liste (inkl. Reihenfolge, Nexus-IDs, Separator-Struktur) und format_version=1
- [ ] 4. Wenn User im Export-Dialog die Mod-Anzahl und Separator-Anzahl sieht, stimmen diese mit der aktuellen Modliste ueberein
- [ ] 5. Wenn User im Dots-Menue "Collection importieren" klickt, oeffnet sich ein Datei-Dialog gefiltert auf .anvilpack-Dateien
- [ ] 6. Wenn User eine gueltige .anvilpack auswaehlt, oeffnet sich ein Import-Dialog der Game-Name, Collection-Name, Ersteller, Mod-Anzahl und fehlende Mods anzeigt
- [ ] 7. Wenn User im Import-Dialog auf einen fehlenden Mod klickt der eine Nexus-ID hat, oeffnet sich die Nexus-Mod-Seite im Browser
- [ ] 8. Wenn User im Import-Dialog "Importieren" bestaetigt, wird die Modliste (Reihenfolge + Separatoren) gemaess der Collection aktualisiert
- [ ] 9. Wenn User eine Collection importiert die Kategorien enthaelt, werden die Kategorie-Zuweisungen der vorhandenen Mods aktualisiert
- [ ] 10. Wenn User eine Collection fuer ein anderes Game importiert, erscheint eine Warnung und der Import wird nicht durchgefuehrt
- [ ] 11. Wenn die .anvilpack-Datei kein gueltiges manifest.json enthaelt, erscheint eine Fehlermeldung statt eines Absturzes
- [ ] 12. Wenn User eine Collection exportiert, enthaelt die manifest.json fuer jeden Mod mit nexus_id > 0 die korrekte Nexus-URL
- [ ] 13. Alle neuen UI-Texte sind in allen 7 Locale-Dateien (de, en, es, fr, it, pt, ru) vorhanden
- [ ] 14. Export und Import sind ueber das Datei-Menue in der Menueleiste erreichbar
- [ ] 15. `./restart.sh` startet ohne Fehler
