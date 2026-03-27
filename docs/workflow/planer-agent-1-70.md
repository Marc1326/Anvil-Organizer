# Planer Agent 1: Bestehender Anvil-Code Analyse
Issue: #70 — Collection/Modpack Export + Import
Datum: 2026-03-26

## Bestehende Mechanismen

### 1. Backup-System (bereits vorhanden)
- `mainwindow.py:_create_backup()` — erstellt ZIP mit modlist.txt, categories.json, meta.ini-Dateien
- `mainwindow.py:_restore_backup()` — stellt aus ZIP wieder her
- `dialogs/backup_dialog.py` — Card-basierter Auswahldialog
- Format: `.backups/backup_YYYY_MM_DD_HH_MM_SS.zip`
- ZIP-Struktur: `modlist.txt`, `categories.json`, `mods/<name>/meta.ini`

### 2. CSV-Export (bereits vorhanden)
- `mainwindow.py:_ctx_export_csv()` — exportiert Modliste als CSV (Name, Category, Version, Priority, Active)
- Signal: `export_csv_requested` in ProfileBar

### 3. Mod-Datenmodell
- `ModEntry` (mod_entry.py): name, enabled, priority, display_name, version, category, nexus_id, author, description, url, is_separator, color, category_ids
- `meta.ini` (mod_metadata.py): configparser-Format mit [General] und [installed] Sektionen
  - Wichtige Keys: modid, version, category, name, author, description, url, installDate, repository
- Scan: `scan_mods_directory()` liest global modlist + active_mods.json + meta.ini

### 4. Modlist-System
- Global: `.profiles/modlist.txt` — Reihenfolge aller Mods (v2 Format, +Name)
- Per-Profil: `.profiles/<Name>/active_mods.json` — Set von aktivierten Mods
- Separatoren: Enden mit `_separator`, stehen VOR ihren Mods
- `mod_list_io.py`: read/write_global_modlist, read/write_active_mods

### 5. Kategorien
- `categories.json` pro Instanz
- `CategoryManager` mit ID/Name-Mapping
- Mods speichern category-IDs in meta.ini als komma-separierte Liste

### 6. Nexus-Integration
- `GameNexusName` im Plugin (z.B. "cyberpunk2077")
- `nexus_id` in ModEntry (aus meta.ini "modid")
- NXM-Handler: `nxm://gameName/mods/modID/files/fileID`
- API: `NexusAPI` fuer Mod-Info-Abfragen

### 7. ProfileBar-Menue
- Existierende Menue-Punkte: Install Mod, Separator, Collapse/Expand, Enable/Disable, Reload, Export CSV, Backup, Restore
- Signal-Pattern: `Signal` -> `connect()` -> `_methode()`

## Wiederverwendbare Komponenten
1. **ZIP-Erstellung/Lesen** — Backup-Pattern kann als Vorlage dienen
2. **meta.ini lesen/schreiben** — read_meta_ini/write_meta_ini
3. **modlist.txt lesen/schreiben** — read_global_modlist/write_global_modlist
4. **active_mods.json lesen/schreiben** — read_active_mods/write_active_mods
5. **categories.json** — CategoryManager.load()/save()
6. **Toast-Benachrichtigungen** — Toast(self, message)
7. **QFileDialog** — Bereits genutzt in CSV-Export
8. **BackupDialog-Pattern** — Card-basierter Dialog als UI-Vorlage
