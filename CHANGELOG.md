# Changelog

## [1.0.8] — 2026-03-14

### Fixes
- **Multi-Mod DnD aus Download-Tab:** Beim Ziehen von mehreren Mods gleichzeitig (z.B. 5 Stück) landeten ab dem 3. Mod alle im falschen Separator. Ursache: `insert_at` verwies auf veraltete Source-Model-Zeilen. Fix: Jeder Mod wird jetzt direkt nach dem vorherigen eingefügt.
- **DnD aus Download-Tab (Single):** Mods landeten im falschen Separator, weil Direct-Install Mods den Index verschoben haben. Position wird jetzt korrekt über den Ordnernamen aufgelöst.
- **Mod-Löschung:** Gelöschte Mods wurden nicht aus der globalen modlist.txt entfernt — tote Einträge sammelten sich an. Jetzt wird der Eintrag korrekt aus `.profiles/modlist.txt` entfernt.
- **Index-Mismatch bei Context-Menu:** 15+ Funktionen (Löschen, Umbenennen, Aktivieren, Backup, Nexus, Kategorien) griffen bei DirectInstall-Mods auf den falschen Mod zu. Alle verwenden jetzt sicheren Name-Lookup statt Index-Zugriff.
- **Suche findet Mods in eingeklappten Separatoren:** Wenn ein Separator eingeklappt war, wurden seine Mods auch von der Suche ignoriert. Jetzt werden bei aktiver Suche/Filter alle Mods durchsucht — unabhängig vom Separator-Status.

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
