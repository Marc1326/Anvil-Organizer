# Dev Report: AppImage Build

**Datum:** 2026-02-25
**Feature:** AppImage Build fuer Anvil Organizer
**Status:** Abgeschlossen

## Erstellte Dateien

| Datei | Beschreibung |
|---|---|
| `anvil-organizer.spec` | PyInstaller Spec (onedir, noconsole, hidden imports, datas) |
| `build-appimage.sh` | Automatisiertes Build-Skript (PyInstaller + AppImage) |
| `release/Anvil_Organizer-0.1.0-x86_64.AppImage` | Fertiges AppImage (88 MB) |

## Geaenderte Dateien

| Datei | Aenderung |
|---|---|
| `.gitignore` | `release/`, `AnvilOrganizer.AppDir/`, `*.AppImage`, `*.spec` hinzugefuegt |

## Technische Details

### PyInstaller Spec
- **Modus:** onedir (COLLECT)
- **Console:** False (GUI-App)
- **Hidden Imports:** PySide6.QtSvg, lz4, lz4.block, xml, xml.etree, xml.etree.ElementTree
- **Datas:** locales, styles, assets, resources, plugins/games (relative Struktur beibehalten)

### AppImage
- **Tool:** appimagetool continuous build
- **Kompression:** squashfs (zstd) -- 38% der unkomprimierten Groesse
- **Architektur:** x86_64
- **Groesse:** 88 MB

### Bekannte Meldungen beim Start
1. `plugin_loader: failed to import game_baldursgate3.py: No module named 'anvil.core.bg3_mod_installer'`
   - BG3-Plugin referenziert ein Modul das nicht existiert (WIP-Code, nicht Build-bedingt)
   - Tritt auch beim normalen Start mit `.venv/bin/python main.py` auf
2. `QTabBar does not have a property named "alignment"`
   - Bekanntes Qt/QSS-Problem, dokumentiert in CLAUDE.md als ignorierbar

### xml Hidden Import
Das `xml` Modul musste als Hidden Import hinzugefuegt werden, weil PyInstaller es nicht
automatisch erkennt (es wird dynamisch vom BG3-Plugin-Handler importiert). Ohne den Import
kam: `No module named 'xml'`. Nach dem Fix bleibt nur noch der separate
`bg3_mod_installer`-Fehler (fehlendes Modul, nicht Build-bedingt).

## Akzeptanz-Checkliste

- [x] 1. PyInstaller baut ohne Fehler -> dist/anvil-organizer/
- [x] 2. dist/anvil-organizer/anvil-organizer startet (Hauptfenster oeffnet sich)
- [x] 3. AppDir korrekt (AppRun, .desktop, Icon)
- [x] 4. AppImage gebaut ohne Fehler
- [x] 5. AppImage startet (Hauptfenster oeffnet sich)
- [x] 6. AppImage in release/ mit 88 MB (Kompression effizienter als erwartet)
- [x] 7. --noconsole Flag gesetzt (console=False in spec)
- [x] 8. build-appimage.sh erstellt und funktioniert (getestet mit clean build)
- [x] 9. Hidden Imports: PySide6.QtSvg, lz4, lz4.block (plus xml fuer BG3-Plugin)
- [x] 10. Kein bestehendes anvil/**/*.py veraendert (git diff bestaetigt)
- [x] 11. restart.sh startet ohne Fehler (nur bekannte QTabBar-Warnings)
