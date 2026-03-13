# Changelog

## [1.0.7] — 2026-03-13

### Fixes
- **Kritisch: modlist.txt Migration verschiebt Mods bei jedem Start** — `migrate_modlist_order()` hat bei jedem Anvil-Start die Mod-Reihenfolge verschoben, wenn der Header noch v1 war aber die Daten bereits im v2-Format vorlagen. Jede Mod-Gruppe rutschte um einen Separator nach unten. Die Reordering-Logik wurde komplett entfernt — die Migration aktualisiert jetzt nur noch den Header.
- Legacy `write_modlist()` schreibt jetzt ebenfalls den v2-Header, damit keine Funktion mehr den alten v1-Header erzeugt.

## [1.0.6] — 2026-03-09

### Fixes
- Separator verschwindet bei Multi-Select DnD: Wenn mehrere Mods gleichzeitig in einen Separator gezogen wurden, verschwand der Separator. Gefixt.
- Mods verschwinden nach Neustart: Neu installierte Mods waren nach einem Neustart nicht mehr sichtbar (falsches Name-Matching). Gefixt.
- Mod-Toggle und Reorder: Checkbox-Toggle und Drag & Drop nutzen jetzt den eindeutigen Ordnernamen statt Display-Namen (verhindert Datenverlust bei doppelten Namen).

### Visuelles
- Ordner-Icon bei Separatoren in der Kategorie-Spalte entfernt
- Ja/Nein-Icons in Bestätigungsdialogen entfernt (Paper Dark & 1809 Dark Mode Theme)

### modlist.txt Format-Korrektur
- Die globale modlist.txt wurde bisher invertiert geschrieben (Separator stand nach seinen Mods statt davor). Format korrigiert und automatische Migration beim ersten Start.
- Bestehende Dateien werden gesichert (modlist.txt.bak) bevor die Migration durchgeführt wird.

## [1.0.5] — 2026-03-08

### Fixes
- Separator-Drag & Drop: Trenner lässt sich wieder per DnD verschieben ohne sich zu schließen
- Separator-Klick: Gesamte Zeile öffnet/schließt Trenner (nicht nur Dreieck)
- Mehrfachauswahl DnD: Mehrere Mods gleichzeitig per Drag & Drop verschieben
- Kontextmenü "In Trenner verschieben": Rechtsklick → ausgewählte Mods in Trenner verschieben
- Kategorie-Spalte: Kein Ordner-Icon mehr bei Trennern
- Dialoge: Keine Icons mehr in Ja/Nein/Ok Buttons

## [1.0.0] — 2026-02-xx
- Erste öffentliche Version
