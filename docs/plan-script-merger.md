# Anvil Script Merger — Intensive Feature-Spezifikation (Option B)

**Datum:** 2026-03-24
**Issue:** #61
**Entscheidung:** Option B — Eigenstaendiger Dialog innerhalb von Anvil

---

## 1. ANALYSE: SM-FAE (Script Merger - Fresh and Automated Edition)

### 1.1 Was SM-FAE ist

SM-FAE ist ein .NET 8.0 Windows Desktop-Programm (WinForms) fuer Witcher 3.
Es loest das "Last Wins"-Problem: Wenn mehrere Mods dieselbe `.ws`-Script-Datei
aendern, gewinnt nur die letzte in der Ladereihenfolge. Alle anderen Aenderungen
gehen verloren.

### 1.2 SM-FAE Architektur (aus DLL-Analyse)

**Groesse:** 12.4 MB DLL + 243 KB EXE (Launcher)
**Runtime:** .NET 8.0 + Windows Desktop Framework
**Gesamtpaket:** ~420 MB (mit allen Tools + Dependencies)

**Module (extrahiert aus DLL):**

| Modul | Funktion |
|-------|----------|
| `FileIndex` | Indiziert alle Mod-Dateien, baut Konflikttabelle |
| `Inventory` | Verwaltet bekannte Merges (was wurde schon gemerged?) |
| `MergeInventory` | Speichert Merge-Ergebnisse persistent |
| `LoadOrder` | Liest/schreibt Mod-Reihenfolge |
| `LoadOrderValidator` | Prueft ob Prioritaeten konsistent sind |
| `LoadOrderWatcher` | Ueberwacht Datei-Aenderungen an der Load Order |
| `ConflictTree` | TreeView-Widget fuer Konflikt-Darstellung |
| `FileMerger` | Kern-Logik: Fuehrt 3-Way-Merge durch |
| `MergeFile` / `MergeFlatFileNode` | Repraesentiert eine zu mergende Datei |
| `MergeBundleFileNode` | Bundle-spezifische Merge-Logik |
| `ScriptMergerFAE` | Hauptklasse mit Automatisierungs-Features |

**Forms (UI):**

| Form | Funktion |
|------|----------|
| `MainForm` | Hauptfenster mit Conflict Tree + Toolbar |
| `LoadOrderForm` | Load-Order Editor |
| `DependencyForm` | Zeigt Abhaengigkeiten zwischen Mods |
| `MergeReportForm` | Report nach Merge-Vorgang |
| `PackReportForm` | Report nach Bundle-Packing |
| `OptionsForm` | Einstellungen |
| `PriorityPromptForm` | Fragt bei Prioritaets-Konflikten |

### 1.3 SM-FAE Konfiguration (was es alles kann)

Aus `WitcherScriptMerger.dll.config`:

```
Scan-Typen:
  CheckScripts = true          Script-Dateien (.ws) scannen
  CheckXmlFiles = true         XML-Dateien scannen
  CheckBundles = 0             Bundle-Dateien NICHT scannen (opt-in)

Automatisierung:
  AutoCreateScriptMerges       Automatisch mergen ohne Bestaetigung
  AutoDeleteOldMerges          Alte Merges loeschen
  AutoOverwriteOldMerges       Bestehende Merges ueberschreiben
  AutoSkipKDiff3InfoDialogs    KDiff3 Infodialoge ueberspringen
  AutoExit                     Nach Merge beenden (CLI-Modus)

Validierung:
  ValidateMergeSources         Pruefe ob Quell-Mods noch existieren
  ValidateCustomLoadOrder      Pruefe Custom Load Order
  CheckDuplicatePrios          Warnung bei doppelten Prioritaeten

UI:
  CollapseIdenticalConflicts   Identische Konflikte zusammenfassen
  CollapseCustomLoadOrder      Custom Load Order zusammenfassen
  CollapseNotMergeable         Nicht-Mergeable zusammenfassen
  ReviewEachMerge              Jeden Merge einzeln pruefen

Output:
  MergedModName = mod0000_MergedFiles   Name des Merge-Mods
  ReportAfterMerge                      Report anzeigen
  ReportAfterPack                       Report nach Pack anzeigen
```

### 1.4 SM-FAE Tool-Abhaengigkeiten

| Tool | Funktion | Groesse | Linux-Verfuegbar? |
|------|----------|---------|-------------------|
| KDiff3 | 3-Way-Diff GUI | 18 MB | JA: `pacman -S kdiff3` |
| QuickBMS | Bundle entpacken | 20 MB | NEIN (Windows-only) |
| wcc_lite | Bundle neu packen | 302 MB | NEIN (CD Projekt Red Tool) |

**Fazit:** Bundle-Support ist auf Linux schwierig. Script- und XML-Merge sind aber
komplett ohne externe Windows-Tools moeglich.

---

## 2. ANALYSE: Witcher 3 Mod-Struktur

### 2.1 Vanilla Script-Verzeichnis

```
/mnt/gamingS/SteamLibrary/steamapps/common/The Witcher 3/
  content/content0/
    scripts/                    1.487 .ws-Dateien (RedScript)
      game/
        player/
          r4Player.ws           Haupt-Player-Klasse
          playerWitcher.ws      Witcher-spezifisch
          states/combat.ws      Kampfsystem
          combos/
          movement/
        actor.ws                Alle Akteure
        components/
          inventoryComponent.ws Inventar
        replacers/
        quests/
        explorations/
      core/
    bundles/
      blob.bundle               Grafik (POTATO70 Format)
      buffers.bundle             Buffer
      xml.bundle                 XML-Konfiguration
```

### 2.2 Mod-Ordner-Struktur

```
.mods/modBloodAndSteel (Next Gen)/
  meta.ini                      Anvil-Metadaten
  mods/
    modBloodAndSteel/
      content/
        scripts/
          game/
            actor.ws            Geaenderte Vanilla-Datei
            player/
              r4Player.ws       Geaenderte Vanilla-Datei
              states/combat.ws
          local/                Mod-eigene Scripts (KEIN Konflikt)
            bloodAndSteel.ws
            animationSystem.ws
        blob0.bundle
        buffers0.bundle
        metadata.store
        *.w3strings             Lokalisierung
  dlc/
    dlcBloodAndSteel/
      content/
        blob0.bundle
  bin/
    config/r4game/user_config_matrix/pc/
      modBloodAndSteel.xml      Menu-Konfiguration
```

### 2.3 .ws Datei-Format

- **Kodierung:** UTF-16 LE (Little Endian) mit BOM
- **Sprache:** RedScript (C-aehnlich mit Klassen/Funktionen)
- **Decorator-System fuer Mod-Kompatibilitaet:**

```witcher
// Neue Felder zu bestehenden Klassen hinzufuegen (stackbar!)
@addField(CR4Player) private var inCustomDodge : bool;

// Neue Methoden zu bestehenden Klassen
@addMethod(CR4Player) public function InCustomDodge() : bool {
    return inCustomDodge;
}

// Bestehende Methoden wrappen (ersetzen + Original aufrufen)
@wrapMethod(CR4Player) function OnSpawned(spawnData : SEntitySpawnData) {
    baSConfig = new BaSConfig in this;
    wrappedMethod(spawnData);  // Original aufrufen
}
```

### 2.4 Aktuelle Konflikte in Marcs Installation

| Datei | Mods | Schwere |
|-------|------|---------|
| `r4Player.ws` | Blood and Steel, Indestructible Items, Brothers in Arms | HOCH |
| `actor.ws` | Blood and Steel, Brothers in Arms | MITTEL |
| `playerWitcher.ws` | Blood and Steel, Brothers in Arms | MITTEL |
| `combat.ws` | Blood and Steel, Brothers in Arms | MITTEL |
| `inventoryComponent.ws` | Indestructible Items | GERING |

### 2.5 Wie Witcher 3 Mods laedt

Witcher 3 sucht Mods in `<GameDir>/Mods/` alphabetisch.
Bei Datei-Konflikten gewinnt der LETZTE Mod (alphabetisch).
SM-FAE erstellt `mod0000_MergedFiles` — das "0000" sorgt dafuer,
dass dieser Mod alphabetisch VOR allen anderen steht und die
gemergte Version alle Einzel-Versionen ueberschreibt.

**Anvils Deployer** symlinkt Mods in der modlist.txt-Reihenfolge.
Die Mod-Namen unter `Mods/` werden beibehalten (modXXX-Pattern).

---

## 3. TECHNISCHER PLAN: Option B

### 3.1 Datei-Struktur

```
anvil/core/script_merger/
  __init__.py
  scanner.py                    Scannt Mods nach Konflikten
  merger.py                     3-Way-Merge Algorithmus
  inventory.py                  Merge-Inventar (was ist gemerged?)
  models.py                     Datenklassen (Conflict, MergeResult, etc.)

anvil/widgets/
  script_merger_dialog.py       PySide6 Dialog (Option B UI)

anvil/styles/icons/
  script_merger.svg             Toolbar-Icon
```

### 3.2 Datenmodell

```python
@dataclass
class ScriptConflict:
    """Ein Konflikt = eine Datei die von mehreren Mods geaendert wird."""
    relative_path: str          # z.B. "content/scripts/game/player/r4Player.ws"
    vanilla_path: Path          # Pfad zur Original-Vanilla-Datei
    mod_versions: list[ModVersion]  # Alle Mod-Versionen dieser Datei
    merge_status: MergeStatus   # UNSCANNED, AUTO_MERGEABLE, CONFLICT, MERGED

@dataclass
class ModVersion:
    """Eine bestimmte Version einer Datei aus einem bestimmten Mod."""
    mod_name: str               # z.B. "modBloodAndSteel"
    file_path: Path             # Absoluter Pfad zur Mod-Datei
    diff_hunks: list[DiffHunk]  # Aenderungen gegenueber Vanilla

@dataclass
class DiffHunk:
    """Ein Aenderungsblock gegenueber Vanilla."""
    start_line: int
    end_line: int
    vanilla_lines: list[str]
    mod_lines: list[str]

class MergeStatus(Enum):
    UNSCANNED = "unscanned"
    AUTO_MERGEABLE = "auto_mergeable"    # Keine Zeilen-Kollisionen
    CONFLICT = "conflict"                # Zeilen kollidieren
    MERGED = "merged"                    # Erfolgreich gemerged
    IGNORED = "ignored"                  # User will nicht mergen

@dataclass
class MergeResult:
    """Ergebnis eines Merge-Vorgangs."""
    conflict: ScriptConflict
    success: bool
    merged_content: str | None   # Gemergter Datei-Inhalt
    unresolved_hunks: list[DiffHunk]  # Offene Konflikte
    method: str                  # "auto" oder "kdiff3" oder "manual"
```

### 3.3 Scanner (scanner.py)

```
ALGORITHMUS: scan_conflicts()

Input:
  - vanilla_dir: Path        (z.B. content/content0/scripts/)
  - mods_dir: Path           (.mods/ Verzeichnis)
  - active_mods: list[str]   (aus modlist.txt, nur aktive)
  - file_types: list[str]    ([".ws", ".xml"])

Ablauf:
  1. Baue Index aller Vanilla-Dateien:
     vanilla_files = {relative_path: absolute_path}

  2. Fuer jeden aktiven Mod:
     a. Suche in mod_path/mods/*/content/scripts/ nach .ws Dateien
     b. Suche in mod_path/mods/*/content/ nach .xml Dateien
     c. Berechne relative_path fuer jede Datei
     d. Trage in file_to_mods[relative_path] = [mod_name, ...] ein

  3. Filtern:
     a. Nur Dateien behalten die in >= 2 Mods vorkommen
        ODER die eine Vanilla-Version ueberschreiben
     b. "local/" Verzeichnisse ignorieren (mod-eigene Scripts)

  4. Fuer jeden Konflikt:
     a. Lade Vanilla-Version (UTF-16 LE!)
     b. Lade alle Mod-Versionen
     c. Berechne Diffs (difflib.unified_diff)
     d. Pruefe ob Hunks kollidieren:
        - Wenn KEINE Hunks sich ueberlappen: AUTO_MERGEABLE
        - Wenn Hunks sich ueberlappen: CONFLICT

Output:
  list[ScriptConflict] sortiert nach Schwere
```

### 3.4 Merger (merger.py)

```
ALGORITHMUS: auto_merge()

Fuer AUTO_MERGEABLE Konflikte (Hunks ueberlappen nicht):

  1. Starte mit Vanilla-Inhalt als Basis
  2. Sortiere alle Hunks aller Mods nach start_line ABSTEIGEND
     (rueckwaerts anwenden, damit Zeilennummern stabil bleiben)
  3. Fuer jeden Hunk:
     a. Ersetze vanilla_lines durch mod_lines an der richtigen Stelle
  4. Ergebnis: Merged Content mit allen Aenderungen

ALGORITHMUS: multi_way_merge()

Fuer CONFLICT Konflikte (Hunks ueberlappen):

  Python stdlib: merge3.Merge3(vanilla, mod_a, mod_b)
  - Merge3 ist ein 3-Way-Merge-Algorithmus (wie git merge)
  - Eingebaut in Python seit 3.x (aus bzrlib/breezy)
  - Kann automatisch mergen wenn Aenderungen kompatibel sind
  - Markiert echte Konflikte mit <<<<<<<  =======  >>>>>>> Markern

  Fuer >2 Mods: Iterativ mergen:
    merged = vanilla
    for mod in mods_sorted_by_priority:
        merged = merge3(vanilla, merged, mod_version)
    # Prioritaets-Reihenfolge bestimmt wer bei Konflikt "gewinnt"

ALGORITHMUS: kdiff3_merge()

Fuer manuelle Konflikte:

  1. Schreibe 3 temporaere Dateien:
     /tmp/anvil_merge/vanilla.ws
     /tmp/anvil_merge/mod_a.ws
     /tmp/anvil_merge/mod_b.ws
  2. Starte: kdiff3 --merge vanilla.ws mod_a.ws mod_b.ws -o merged.ws
  3. Warte auf KDiff3-Beendigung
  4. Lese merged.ws zurueck
  5. Aufraeumen
```

### 3.5 UTF-16 LE Handling

**KRITISCH:** Witcher 3 .ws Dateien sind UTF-16 LE kodiert!

```python
def read_ws_file(path: Path) -> str:
    """Liest .ws Datei mit korrekter Kodierung."""
    raw = path.read_bytes()
    # BOM-Detection
    if raw[:2] == b'\xff\xfe':
        return raw.decode('utf-16-le')
    elif raw[:2] == b'\xfe\xff':
        return raw.decode('utf-16-be')
    else:
        # Fallback: versuche utf-8, dann latin-1
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError:
            return raw.decode('latin-1')

def write_ws_file(path: Path, content: str) -> None:
    """Schreibt .ws Datei in UTF-16 LE (Witcher 3 Standard)."""
    path.write_bytes(b'\xff\xfe' + content.encode('utf-16-le'))
```

### 3.6 Merge-Inventar (inventory.py)

SM-FAE speichert welche Merges durchgefuehrt wurden.
Wir machen das auch — als JSON:

```json
{
  "version": 1,
  "merged_mod_name": "mod0000_MergedFiles",
  "merges": [
    {
      "relative_path": "content/scripts/game/player/r4Player.ws",
      "mods": ["modBloodAndSteel", "modIndestructibleItems", "modBrothersInArms"],
      "method": "auto",
      "timestamp": "2026-03-24T15:30:00",
      "hash": "abc123..."
    }
  ]
}
```

Gespeichert in: `.anvil-organizer/instances/The Witcher 3/.merge_inventory.json`

Bei erneutem Scan: Pruefe ob sich Quell-Dateien geaendert haben (Hash-Vergleich).
Wenn nicht → Merge ist noch gueltig. Wenn ja → Merge muss aktualisiert werden.

### 3.7 Merge-Mod Erstellung

```
ALGORITHMUS: create_merge_mod()

1. Erstelle Ordner-Struktur:
   .mods/_merged_/
     mods/
       mod0000_MergedFiles/
         content/
           scripts/
             game/
               player/
                 r4Player.ws    (gemergter Inhalt)
               actor.ws

2. Fuer jede gemergte Datei:
   a. Schreibe merged_content in die richtige relative Position
   b. Kodierung: UTF-16 LE (wie Vanilla!)

3. Trage _merged_ in modlist.txt ein (ganz oben, hoechste Prio)

4. Die Original-Mods behalten ihre Script-Dateien —
   der Merge-Mod ueberschreibt sie durch hoechste Prioritaet
```

**Witcher 3 Besonderheit:** Der Merge-Mod heisst `mod0000_MergedFiles`
(im Unterordner mods/), damit Witcher 3 ihn alphabetisch zuerst laedt.
Anvils Deployer symlinkt ihn dann nach `<GameDir>/Mods/mod0000_MergedFiles/`.

### 3.8 Dialog UI (script_merger_dialog.py)

```
+-------- Anvil Script Merger -- Witcher 3 --------+------+
|                                                    |  X   |
|  Pfade:                                            |      |
|  Vanilla: /mnt/gamingS/.../content/content0/scripts|      |
|  Mods:    6 aktiv, 4 mit Scripts                   |      |
|                                                    |      |
|  [Scan starten]  [Alle auto-mergen]  [Aufraeumen]  |      |
|                                                    |      |
|  +-- Konflikte --+-- Details ----------------------+      |
|  |               |                                  |      |
|  | ! r4Player.ws | Datei: scripts/game/player/      |      |
|  | ! actor.ws    |        r4Player.ws               |      |
|  | ! combat.ws   |                                  |      |
|  | V playerW.ws  | Mods (3):                        |      |
|  |               |   1. modBloodAndSteel     [Prio 1]|     |
|  |               |   2. modIndestructibleItems[Prio 3]|     |
|  |               |   3. modBrothersInArms    [Prio 4]|     |
|  |               |                                  |      |
|  |               | Aenderungen:                      |      |
|  |               |   modBlood: 3 Hunks (Z. 12-45,   |      |
|  |               |             Z. 120-135, Z. 300+)  |      |
|  |               |   modIndest: 1 Hunk (Z. 200-210)  |      |
|  |               |   modBrothers: 5 Hunks            |      |
|  |               |                                  |      |
|  |               | Status: AUTO-MERGEABLE            |      |
|  |               |                                  |      |
|  |               | [Auto-Merge] [KDiff3] [Ignorieren]|      |
|  +---------------+----------------------------------+      |
|                                                    |      |
|  -- Statistik ------------------------------------ |      |
|  5 Konflikte | 3 auto-mergeable | 2 manuell | 0 gemerged  |
|                                                    |      |
|  [Merge-Mod erstellen]              [Schliessen]   |      |
+----------------------------------------------------+------+
```

**Widget-Struktur:**

```python
class ScriptMergerDialog(QDialog):
    # Links: QListWidget mit Konflikten (Icon + Dateiname)
    # Rechts: QWidget-Stack mit Details pro Konflikt
    #   - Pfad-Info (QLabel)
    #   - Mod-Liste (QListWidget mit Prioritaet)
    #   - Hunk-Uebersicht (QTreeWidget)
    #   - Status-Label
    #   - Action-Buttons (Auto-Merge, KDiff3, Ignorieren)
    # Unten: Statistik-Leiste + Hauptbuttons
```

### 3.9 Toolbar-Integration

In `toolbar.py` / `mainwindow.py`:

```python
# Button nur sichtbar wenn Game = Witcher 3
if game_plugin and game_plugin.GameShortName == "witcher3":
    script_merger_btn.setVisible(True)
else:
    script_merger_btn.setVisible(False)

# Klick:
def _on_script_merger_clicked(self):
    dialog = ScriptMergerDialog(
        vanilla_dir=game_plugin.vanilla_scripts_dir(),
        mods_dir=instance_path / ".mods",
        active_mods=modlist_manager.get_active_mods(),
        game_path=game_plugin.game_path(),
        parent=self,
    )
    dialog.exec()
    # Nach Schliessen: Mod-Liste aktualisieren (wegen _merged_ Mod)
    self._refresh_mod_list()
```

---

## 4. FEATURE-VERGLEICH: SM-FAE vs. Anvil Script Merger

| Feature | SM-FAE | Anvil (Phase 1) | Anvil (Phase 2) | Anvil (Phase 3) |
|---------|--------|-----------------|-----------------|-----------------|
| **Script-Scan (.ws)** | Ja | Ja | Ja | Ja |
| **XML-Scan** | Ja | Ja | Ja | Ja |
| **Bundle-Scan** | Ja (QuickBMS) | Nein | Nein | Moeglich* |
| **Auto-Merge** | Ja | Ja | Ja | Ja |
| **KDiff3 Integration** | Ja (Windows) | Nein | Ja (nativ!) | Ja |
| **Diff-Vorschau** | Nein | Nein | Ja | Ja |
| **Merge-Inventar** | Ja | Ja | Ja | Ja |
| **Alte Merges aufr.** | Ja | Ja | Ja | Ja |
| **Mod-Reihenfolge** | Ja (extern) | Ja (kennt modlist!) | Ja | Ja |
| **Mods ignorieren** | Ja | Ja | Ja | Ja |
| **Merge validieren** | Ja | Nein | Ja | Ja |
| **Load Order Watch** | Ja | Nein | Nein | Moeglich |
| **Nativ Linux** | Nein (Wine) | Ja | Ja | Ja |
| **Dark Theme** | Ja (eigen) | Ja (Anvil) | Ja (Anvil) | Ja (Anvil) |
| **Automatischer Mode** | Ja (CLI) | Nein | Moeglich | Moeglich |

*Bundle-Support braucht QuickBMS/wcc_lite unter Wine oder eigenen Bundle-Parser

---

## 5. PHASEN-PLAN

### Phase 1 — Kern (Script-Scan + Auto-Merge)

**Dateien:**
- `anvil/core/script_merger/__init__.py`
- `anvil/core/script_merger/scanner.py`
- `anvil/core/script_merger/merger.py`
- `anvil/core/script_merger/inventory.py`
- `anvil/core/script_merger/models.py`
- `anvil/widgets/script_merger_dialog.py`

**Features:**
- [x] Scan: Finde alle .ws-Konflikte zwischen aktiven Mods
- [x] Scan: Finde alle .xml-Konflikte
- [x] Diff: Berechne Hunks pro Mod gegenueber Vanilla
- [x] Auto-Merge: Automatisch mergen wenn Hunks nicht kollidieren
- [x] Output: Merge-Mod (`_merged_/mods/mod0000_MergedFiles/`) erstellen
- [x] Inventar: Speichere was gemerged wurde
- [x] UI: Dialog mit Konflikt-Liste und Detail-Ansicht
- [x] UI: Toolbar-Button (nur bei Witcher 3)
- [x] Cleanup: Alte Merges loeschen koennen
- [x] UTF-16 LE: Korrekte Kodierung lesen/schreiben

**Akzeptanz-Kriterien Phase 1:**
1. Dialog oeffnet sich ueber Toolbar-Button
2. Scan findet r4Player.ws Konflikt (Blood and Steel + Indestructible Items)
3. Auto-Merge erstellt korrekten Merge wenn Hunks nicht kollidieren
4. Merge-Mod wird in .mods/_merged_ angelegt
5. Merge-Mod erscheint in modlist.txt an Position 1
6. Cleanup entfernt _merged_ und den Inventar-Eintrag
7. UTF-16 LE Dateien werden korrekt gelesen und geschrieben

### Phase 2 — KDiff3 + Diff-Vorschau

**Features:**
- [ ] KDiff3: Externes Merge-Tool starten fuer manuelle Konflikte
- [ ] KDiff3: Ergebnis zuruecklesen nach Beendigung
- [ ] Vorschau: Inline-Diff im Dialog anzeigen (farbig)
- [ ] Validierung: Pruefe ob Merge-Quellen noch aktuell sind
- [ ] Ignorieren: Einzelne Konflikte auf Ignore setzen

**Akzeptanz-Kriterien Phase 2:**
1. KDiff3 startet mit 3 Dateien (Vanilla, Mod A, Mod B)
2. Nach KDiff3-Beendigung wird Ergebnis als Merge uebernommen
3. Diff-Vorschau zeigt gruene/rote Zeilen im Dialog
4. Aenderung an einer Mod → Warnung "Merge veraltet"

### Phase 3 — Bundle-Support (optional)

**Features:**
- [ ] Bundle entpacken (eigener POTATO70 Parser in Python)
- [ ] Bundle-Dateien vergleichen
- [ ] Bundle-Konflikte anzeigen
- [ ] Bundle neu packen (zlib/lz4/snappy)

**Anmerkung:** Das Bundle-Format ist dokumentiert (witcher3.bms Script).
Ein Python-Parser fuer POTATO70 Bundles ist machbar — zlib, lz4 und snappy
sind als Python-Pakete verfuegbar. Kein QuickBMS oder wcc_lite noetig.

```
Bundle-Format (POTATO70):
  Header: "POTATO70" + bundle_size + data_offset
  File-Table: Name(256B) + Hash(16B) + Size + ZSize + Offset + Compression
  Kompression: 0=keine, 1=zlib, 2=snappy, 3=doboz, 4-5=lz4
```

---

## 6. ABHAENGIGKEITEN

### Keine neuen Pakete noetig (Phase 1 + 2):

| Was | Woher | Bemerkung |
|-----|-------|-----------|
| `difflib` | Python stdlib | Unified Diff Berechnung |
| `merge3` | `pip install merge3` ODER eigene Impl. | 3-Way-Merge |
| KDiff3 | `pacman -S kdiff3` | Optional, Phase 2 |

**merge3:** Das Paket `merge3` (aus breezy/bzrlib) ist ~200 Zeilen Python.
Alternative: Eigene Implementierung basierend auf difflib — noch einfacher
und ohne externe Abhaengigkeit.

### Phase 3 (optional):

| Was | Woher | Bemerkung |
|-----|-------|-----------|
| `lz4` | `pip install lz4` | Bundle-Dekompression |
| `python-snappy` | `pip install python-snappy` | Bundle-Dekompression |
| `zlib` | Python stdlib | Bundle-Dekompression |

---

## 7. BEKANNTE HERAUSFORDERUNGEN

### 7.1 UTF-16 LE + difflib

Python `difflib` arbeitet mit Strings, nicht Bytes.
Loesung: Datei als UTF-16 LE lesen → Python-String → difflib → UTF-16 LE schreiben.
Die Konvertierung ist transparent.

### 7.2 Redscript Decorators (@addField, @addMethod, @wrapMethod)

Diese Annotationen sind STACKBAR — mehrere Mods koennen @addField
auf dieselbe Klasse anwenden ohne Konflikt, solange die Feldnamen
unterschiedlich sind.

**Intelligentes Merging:**
- `@addField(Klasse) var xyz` von Mod A + `@addField(Klasse) var abc` von Mod B
  → KEIN Konflikt, beide werden uebernommen
- `@wrapMethod(Klasse) function OnSpawned(...)` von Mod A + Mod B
  → Potentieller Konflikt, muss analysiert werden

### 7.3 Witcher 3 Mod-Naming-Convention

Mods folgen dem Pattern `modXXX/content/scripts/`.
Der Script Merger muss in der richtigen Tiefe suchen:
`.mods/<AnvilModName>/mods/<WitcherModName>/content/scripts/`

### 7.4 Merge-Mod in Deployer integrieren

Der Merge-Mod `_merged_` muss:
1. In modlist.txt an Position 1 stehen (hoechste Prioritaet)
2. Vom Deployer als normaler Mod symlinkt werden
3. Den Unterordner `mods/mod0000_MergedFiles/content/` haben
4. Korrekt nach `<GameDir>/Mods/mod0000_MergedFiles/` deployt werden

### 7.5 DLC-Konflikte

Witcher 3 DLCs (Hearts of Stone, Blood and Wine) haben eigene Scripts
unter `<GameDir>/DLC/*/content/scripts/`. Diese koennen auch mit Mods
kollidieren. Fuer Phase 1 ignorieren wir DLC-Konflikte.

---

## 8. VERGLEICH MIT BESTEHENDER KONFLIKT-ERKENNUNG

Anvil hat bereits einen `ConflictScanner` (`anvil/core/conflict_scanner.py`).
Dieser arbeitet auf Datei-Ebene: "welche Mods haben denselben relativen Pfad?"

**Der Script Merger geht weiter:**
- Nicht nur "diese Dateien kollidieren" sondern "WELCHE ZEILEN kollidieren"
- 3-Way-Diff gegen Vanilla (ConflictScanner kennt kein Vanilla)
- Automatisches Zusammenfuehren wenn moeglich
- Merge-Output als neuer Mod

Der bestehende ConflictScanner wird NICHT ersetzt — er bleibt fuer
allgemeine Datei-Konflikte. Der Script Merger ist ein Witcher-3-spezifisches
Feature das auf Zeilen-Ebene arbeitet.

---

## 9. RISIKEN UND MITIGATIONEN

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| UTF-16 LE Handling fehlerhaft | Mittel | Extensive Tests mit echten .ws Dateien |
| Merge-Ergebnis bricht Spiel | Hoch | Backup der Original-Dateien + Undo |
| Performance bei vielen Mods | Gering | Lazy Loading, nur bei Bedarf scannen |
| KDiff3 nicht installiert | Mittel | Graceful Fallback, Hinweis installieren |
| Bundle-Support gewuenscht | Hoch | Phase 3 klar kommunizieren |
| Decorator-Konflikte falsch erkannt | Mittel | Redscript-aware Hunk-Analyse |
