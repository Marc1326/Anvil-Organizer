# Planer Agent 2: MO2-Referenz Analyse
Issue: #70 — Collection/Modpack Export + Import
Datum: 2026-03-26

## MO2 Collection-Feature

MO2 hat kein eingebautes Collection/Modpack-Export-Feature im engeren Sinne.
Die Nexus Mods "Collections" sind eine Nexus-Website-Funktion, nicht Teil von MO2 selbst.

### Was MO2 bietet:
1. **Profile kopieren** — Profil duplizieren mit gleicher Modliste + Aktivierungsstatus
2. **modlist.txt + meta.ini** — Standardisiertes Format, von externen Tools lesbar
3. **Wabbajack** — Externer Mod-List-Installer der MO2-modlist.txt liest und Mods automatisch installiert

### Nexus Collections:
- Kuratierte Modlisten auf der Nexus-Website
- Enthalten: Mod-IDs, Reihenfolge, Konfiguration
- Nutzer laden Collection -> Vortex installiert automatisch
- Anvil muss das NICHT 1:1 nachbauen, aber das Konzept "Modliste + Links teilen" ist sinnvoll

## Relevanz fuer Anvil
- Das Backup-System von Anvil ist bereits nah an einem Export-Format
- Erweiterung: Nexus-IDs + Game-Info + Versionen in das ZIP packen
- Import: Modliste wiederherstellen + fehlende Mods als Download-Links anzeigen
- Eigenes Format: `.anvilpack` (umbenanntes ZIP) fuer Wiedererkennbarkeit

## Empfehlungen
1. Eigene Dateiendung `.anvilpack` (ist ein ZIP)
2. JSON-Manifest mit Metadaten (Game, Version, Ersteller, Datum)
3. Separator-Struktur beibehalten
4. Nexus-Links fuer fehlende Mods generieren
5. KEIN automatischer Download — nur Links anzeigen
