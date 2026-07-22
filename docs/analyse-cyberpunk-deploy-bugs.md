# Analyse: Cyberpunk 2077 Deploy-Fehler — v0.1.0 vs. v1.0.8

**Datum:** 2026-03-20
**Betrifft:** Anvil Organizer, Cyberpunk 2077 Instanz
**Symptome:** Spiel startet nicht / Mods fehlen / Framework-Fehler
**Profil:** Vanilla (371 aktive Mods von 528)

---

## 1. Ausgangslage: Was geht kaputt?

Vier Fehlermeldungen beim Starten von Cyberpunk 2077:

| Screenshot | Fehlermeldung | Bedeutung |
|------------|--------------|-----------|
| Bild 1 (07:33) | ASI Loader: "Unable to load cyber_engine_tweaks.asi. Error: 998" | CET kann nicht geladen werden |
| Bild 2 (07:34) | "Kein Zugriff auf Speicherort: S:\common\Cyberpunk 2077\red\host\REDNext.dll" | REDmod-Pfad existiert nicht |
| Bild 3 (09:34) | Compilation Error | redscript-Kompilierung schlägt fehl |
| Bild 4 (09:35) | REDAlert: "invalid native definitions — RedData.reds" | RedData Script/DLL Versions-Mismatch |

Alle Frameworks (CET, RED4ext, redscript, Codeware, TweakXL, ArchiveXL, RedData, RedFileSystem, Native Settings UI, Mod Settings) wurden zuerst über Anvils Framework-Installer und danach nochmal manuell ins Game-Verzeichnis installiert. Die Fehler blieben trotzdem bestehen.

---

## 2. Gefundene Bugs

### Bug 1: `valid_mod_folders` Whitelist-Filter (HAUPTURSACHE)

**Status:** Uncommitted — existiert nur in der Working Copy, nicht in einem Release.

#### Was ist das?

Ein neuer Filter in `mod_deployer.py` (Zeile 215-222), der Mod-Dateien anhand ihres ersten Ordnernamens gegen eine Whitelist prüft. Dateien in unbekannten Ordnern werden **still übersprungen** — kein Fehler, keine Warnung, kein Log.

#### Der Code

```python
# mod_deployer.py, deploy() Methode
if self._valid_mod_folders and not is_direct:
    if len(rel.parts) > 1:
        first_part = rel.parts[0].lower()
        if first_part not in self._valid_mod_folders:
            continue   # ← Datei wird STILL übersprungen
```

#### Die Whitelist für Cyberpunk

```python
# game_cyberpunk2077.py (ebenfalls uncommitted)
GameValidModFolders = [
    "archive", "bin", "r6", "red4ext", "engine",
    "mods", "scripts", "tweaks", "tools",
]
```

#### Was wird blockiert?

Simulation mit allen 371 aktiven Mods des Vanilla-Profils:

| Blockierter Ordner | Dateien | Betroffene Mods | Problem |
|--------------------|---------|-----------------|---------|
| `x64/` | 61 | 12 CET-Mods (SmootherDodgeAndDash, React To Horn, CoolCam 2.0, BetterLootMarkers, Chop Shops, Conflict Begone, Dismemberment Settings, ImprovedSlide, Organic Hair, Player underwear removal, Rebel V Preset) | `bin/` wurde durch Flatten-Bug entfernt, `x64` ist nicht in Whitelist |
| `4k/` | 42 | Named NPCs AIO 4K | Verschachtelte 4K-Variante |
| `mod_Sweaty25_*` (12 Ordner) | 13 | Sweaty 25 | REDmod-Ordnerstruktur |
| `NCPDPPE/` | 14 | NCPDPPE V2.7 ARCADE | REDmod-Ordnerstruktur |
| `config/` | 2 | Status Bar Bug Fixes, Cyberware-EX | Konfigurationsdateien |
| `input/` | 2 | Mark To Sell, Immersive Timeskip | Input-Mapping-Dateien |
| `source/` | 3 | BrowserExtensionWKitSrc | WKit-Quelldateien |
| `archives/` | 1 | Material and Texture Override | REDmod-Archive |
| Wrapper-Ordner | 4 | Veegee Jewelry Atelier, VEHICLE REPAIR COST | Mod-Name als Ordner (Flatten-Bug) |
| `fomod/` | 6 | Named NPCs, Any Gun Any Attachment, Sweaty 25 | FOMOD-Installer-Reste |
| `V2077/` | 2 | Wizzo's Boots | ItemCodes |

**Gesamt: 150 Dateien von 1561 (ca. 10%) werden still verschluckt.**

#### Warum existiert der Filter?

Er sollte verhindern, dass Junk-Dateien (FOMOD-Installer, README-Ordner) ins Game-Verzeichnis deployed werden. Die Idee war sinnvoll, aber die Umsetzung hat zwei kritische Fehler:

1. **Die Whitelist ist unvollständig.** Cyberpunk-Mods nutzen Ordner wie `config/`, `input/`, REDmod-spezifische Ordner, und `4k/`-Varianten. Diese fehlen alle in der Whitelist.
2. **Keine Warnung bei Filterung.** Der `continue` überspringt die Datei ohne jede Meldung. Es gibt keinen Log-Eintrag, keine Zählung, keine Zusammenfassung am Ende. Der Benutzer sieht nur, dass Mods nicht funktionieren, aber nicht warum.

#### Vergleich mit v0.1.0

In v0.1.0 gab es weder `GameValidModFolders` noch den Filter im Deployer. **Jede Datei** aus einem aktivierten Mod wurde deployed. Das war "dreckiger" (FOMOD-Dateien landeten im Game-Dir), aber alle Mods funktionierten.

---

### Bug 2: `_flatten_single_subfolder()` hat `bin/` entfernt

**Status:** Fix committed in `2db7a72`, aber Schaden an 12 bestehenden Mods bereits angerichtet.

#### Was ist passiert?

Der Mod-Installer hat beim Entpacken von Archiven geprüft, ob der extrahierte Ordner genau einen Unterordner enthält. Falls ja, wurde der Inhalt eine Ebene hochgezogen ("geflattened"). Das Problem: Wenn ein Mod die Struktur `bin/x64/plugins/...` hatte, wurde `bin/` als Wrapper-Ordner interpretiert und entfernt.

#### Vorher (korrekt):

```
.mods/SmootherDodgeAndDash/
  bin/
    x64/
      plugins/
        cyber_engine_tweaks/
          mods/
            SmootherDodgeAndDash/
              init.lua
```

#### Nachher (falsch geflattened):

```
.mods/SmootherDodgeAndDash/
  x64/                        ← bin/ fehlt!
    plugins/
      cyber_engine_tweaks/
        mods/
          SmootherDodgeAndDash/
            init.lua
```

#### Betroffene Mods (12 Stück):

1. BetterLootMarkers-1.3.2
2. CET 1.37.1 - Scripting fixes
3. Chop Shops
4. Conflict Begone
5. CoolCam 2.0
6. Dismemberment Settings
7. ImprovedSlide
8. Organic Hair
9. Player underwear removal extended CET
10. React To Horn
11. Rebel V Preset (Appearence Change Unlocke)
12. SmootherDodgeAndDash

#### Zusammenspiel mit Bug 1

Diese 12 Mods werden **doppelt bestraft**:

1. `bin/` wurde entfernt → Dateien liegen unter `x64/`
2. `x64/` ist nicht in der Whitelist → Dateien werden blockiert

Selbst ohne den Whitelist-Filter (Bug 1) wären diese Mods falsch deployed worden: Die Dateien würden unter `game_path/x64/` statt `game_path/bin/x64/` landen.

#### Der Fix

Commit `2db7a72` hat eine Blacklist `_GAME_FOLDERS` eingeführt:

```python
_GAME_FOLDERS = {
    "archive", "bin", "r6", "red4ext", "mods",
    "engine", "data", "pc", "dlc",
    "tools", "lml", "content",
}
```

Ordner in dieser Blacklist werden nicht mehr geflattened. Aber die 12 bereits falsch installierten Mods müssen **manuell neu installiert** werden, damit die korrekte Ordnerstruktur wiederhergestellt wird.

---

### Bug 3: Ungeflattente Wrapper-Ordner

**Status:** Bestehend, nicht durch Anvil-Code verursacht sondern durch Mod-Archiv-Struktur.

3 Mods haben einen Wrapper-Ordner der nicht geflattened wurde (weil er mehr als einen Unterordner hatte oder der Name in der `_GAME_FOLDERS`-Blacklist steht):

| Mod | Wrapper-Ordner | Effekt |
|-----|---------------|--------|
| NCPDPPE V2.7 ARCADE | `NCPDPPE/` | REDmod-Struktur, Whitelist blockiert |
| Veegee Jewelry Atelier | `Veegee Jewelry Atelier/` | Mod-Name als Ordner, Whitelist blockiert |
| VEHICLE REPAIR COST | `VEHICLE REPAIR COST/` | Mod-Name als Ordner, Whitelist blockiert |

---

## 3. Zusätzliches Problem: RedData Versions-Mismatch

**Kein Anvil-Bug**, sondern ein Installations-Problem.

```
r6/scripts/RedData/RedData.reds    → Kommentar: "// RedData v0.10.0" (deklariert native struct UUID)
red4ext/plugins/RedData/RedData.dll → Dateidatum: 30. Dez 2025 (v0.9.0 laut RED4ext-Log)
```

Die `.reds`-Script-Datei ist v0.10.0 und deklariert `native struct UUID`, aber die DLL ist v0.9.0 und implementiert diese Klasse nicht. Das führt zu:

```
[error] Script validation error: Missing native class 'RedData.UUID'
        at ...r6/scripts/RedData/RedData.reds:4
```

**Lösung:** RedData komplett neu installieren — entweder v0.10.0 DLL oder v0.9.0 .reds-Dateien, aber beide müssen die gleiche Version haben.

---

## 4. Vergleich v0.1.0 vs. aktuell (v1.0.8+uncommitted)

### Deployer-Änderungen seit v0.1.0

| Änderung | Commit | Auswirkung auf Cyberpunk |
|----------|--------|------------------------|
| Migration von per-profile modlist.txt auf globale modlist + active_mods.json | `a5ee918` | Kein direkter Bug, aber Framework-Mods tauchen nicht in active_mods.json auf (beabsichtigt) |
| `enabled_mods.reverse()` | `743ccee` | Prioritäts-Reihenfolge korrekt (höchste Prio gewinnt) |
| `data_path` Parameter | `60a3adf` | Für Cyberpunk leer → kein Effekt |
| `valid_mod_folders` Whitelist | uncommitted | **150 Dateien still blockiert** |
| `_flatten_single_subfolder` Fix | `2db7a72` | Fix korrekt, aber 12 Mods bereits beschädigt |
| LML-Support, multi_folder_routes | `d8ff441` | Nur für Witcher 3 relevant |
| BA2-Packing | `5415a01` | Nur für Bethesda-Spiele relevant |

### Prioritäts-Logik: Korrekt in beiden Versionen

| | v0.1.0 | Aktuell | MO2 |
|---|--------|---------|-----|
| modlist.txt Reihenfolge | Erste Zeile = niedrigste Prio | Erste Zeile = höchste Prio | Erste Zeile = höchste Prio (wie aktuell) |
| Deployer-Iteration | Direkt (niedrig → hoch) | Reversed (hoch → niedrig → reversed = niedrig → hoch) | Sortiert aufsteigend (niedrig → hoch) |
| Ergebnis | Höchste Prio wird zuletzt verarbeitet → gewinnt | Gleich | Gleich |

### modlist.txt Synchronisation: Korrekt

```
Ordner in .mods:                528
Einträge in globaler modlist:   528
Differenz:                        0
```

Alle Mods sind gelistet, keine fehlen, keine Geister-Einträge.

---

## 5. Zusammenfassung der Root Causes

```
Fehler beim Spielstart
├── Bug 1: valid_mod_folders Whitelist (UNCOMMITTED)
│   ├── 150 Dateien still blockiert
│   ├── Whitelist unvollständig (x64, config, input, 4k, REDmod-Ordner fehlen)
│   └── Keine Warnung/Log bei Filterung
│
├── Bug 2: _flatten_single_subfolder hat bin/ entfernt
│   ├── 12 CET-Mods haben x64/ statt bin/x64/
│   ├── Fix existiert seit 2db7a72, aber Schaden bereits angerichtet
│   └── Betroffene Mods müssen neu installiert werden
│
├── Bug 3: 3 Mods mit Wrapper-Ordner
│   ├── NCPDPPE, Veegee Jewelry, VEHICLE REPAIR COST
│   └── Werden durch Whitelist blockiert
│
└── Kein Anvil-Bug: RedData Versions-Mismatch
    ├── .reds v0.10.0 vs. DLL v0.9.0
    └── Manuelle Neuinstallation nötig
```

---

## 6. Empfohlene Maßnahmen

### Sofort

1. **`valid_mod_folders` Whitelist-Filter entfernen oder deaktivieren** — Der Filter verursacht mehr Schaden als Nutzen. In v0.1.0 funktionierte alles ohne ihn.
2. **12 falsch geflattente Mods neu installieren** — Damit `bin/x64/` statt `x64/` als Struktur vorliegt.
3. **RedData komplett neu installieren** — Gleiche Version für DLL und .reds-Dateien.

### Mittelfristig

4. Falls der Whitelist-Filter gewünscht bleibt: **Warnung/Log** wenn Dateien gefiltert werden, damit das Problem sichtbar wird.
5. Die Whitelist müsste dann deutlich erweitert werden: `config`, `input`, `x64`, `4k`, `source`, und beliebige REDmod-Ordnernamen.
6. Alternativ: Statt Whitelist eine **Blacklist** (nur `fomod/`, `__MACOSX/`, `.git/` etc. ausschließen) — das ist sicherer, weil unbekannte Ordner dann deployed statt blockiert werden.

### Langfristig

7. Ein **"Mod Health Check"**-Feature das vor dem Deploy prüft ob Mod-Strukturen korrekt aussehen und Probleme meldet.
