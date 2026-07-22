# Changelog seit v1.2.6

## Fixes

### Doppelter Nexus-Query-Button entfernt
- Der "Nexus abfragen"-Button im Frameworks-Header war doppelt — die Funktion existiert bereits im Rechtsklick-Kontextmenü

### BG3 Drag-and-Drop — .pak Support + Duplikat-Erkennung
- Standard ModListView akzeptiert jetzt .pak-Dateien beim Drop (vorher nur .zip/.rar/.7z)
- Duplikat-Dialog wenn eine Mod mit gleicher UUID bereits installiert ist
- Neue Mods starten immer deaktiviert — User aktiviert manuell

### BG3 Deaktivierung repariert
- Auto-Repair das deaktivierte Mods wieder aktivierte wurde entfernt
- Mods werden in gespeicherter Reihenfolge angezeigt (nicht aktive-zuerst)
- DnD Reorder aktualisiert die Mod-Liste sofort

### Locked Mods Feature entfernt
- Komplettes Feature entfernt (war nicht gewünscht): UI, Filter, Übersetzungen in allen 7 Sprachen
