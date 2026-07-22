# Feature: Native Script Merger fuer Witcher 3

**Datum:** 2026-03-25 (aktualisiert nach QA-Review)
**Issue:** #61
**Option:** B — Eigenstaendiger Dialog innerhalb von Anvil
**Phase:** 1 (Kern-Funktionalitaet)
**Quellen:** planer-agent-1.md, planer-agent-2.md, planer-agent-3.md, plan-script-merger.md
**QA-Reviews:** qa-review-1-61.md, qa-review-2-61.md, qa-review-3-61.md, qa-review-4-61.md

---

## Zusammenfassung

Anvil Organizer erhaelt einen nativen Script Merger fuer The Witcher 3.
Wenn mehrere Mods dieselbe `.ws`- oder `.xml`-Datei aendern, gewinnt nur der Mod
mit dem alphabetisch niedrigsten Ordnernamen — alle anderen Aenderungen gehen verloren.
Der Script Merger loest das durch:

1. **Scan:** Erkennung aller Script-Konflikte zwischen aktiven Mods
2. **3-Way-Diff:** Vergleich jeder Mod-Version gegen Vanilla
3. **Auto-Merge:** Automatisches Zusammenfuehren wenn Hunks sich nicht ueberlappen
4. **Merge-Mod:** Erstellung eines `mod0000_MergedFiles`-Mods (alphabetisch erster = gewinnt)
5. **Inventar:** Persistente Aufzeichnung aller Merges

Ersetzt SM-FAE (Windows/.NET) durch native Linux-Loesung ohne Wine.

**Witcher 3 Script-Prioritaet:** Der Script-Compiler laedt Mods aus `Mods/` alphabetisch
und nimmt fuer jede Script-Datei die Version aus dem Mod mit dem **NIEDRIGSTEN** Namen.
Der **ERSTE alphabetisch gewinnt** (nicht der letzte!). Deshalb heisst der Merge-Mod
`mod0000_MergedFiles` — er steht alphabetisch vor allen anderen.

**Hinweis:** Anvils modlist.txt-Prioritaet (Deploy-Reihenfolge) ist fuer Witcher 3 Scripts
IRRELEVANT. Der Witcher 3 Compiler hat eigene Lade-Logik. `_merged_` steht trotzdem
an Position 0 in modlist.txt, damit der Deployer die Merge-Dateien zuletzt schreibt.

---

## Scope Phase 1

1. Script-Scan (.ws + .xml)
2. 3-Way-Diff gegen Vanilla
3. Hunk-Overlap-Detection (AUTO_MERGEABLE vs. CONFLICT)
4. Auto-Merge (nicht-kollidierende Hunks)
5. Merge-Inventar (JSON)
6. Merge-Mod erstellen (_merged_/mods/mod0000_MergedFiles/)
7. Dialog UI (Konflikt-Liste + Details)
8. Toolbar-Button (nur Witcher 3)
9. Cleanup (Merges loeschen)
10. UTF-16 LE Handling (BOM-Detection, Fallback, CRLF beibehalten)
11. `local/` Ausschluss
12. Ignore-Funktion (persistent im Inventar)
13. Validierung (Hash-Vergleich ob Quell-Mods sich geaendert haben)

**Nicht in Phase 1:**
- CONFLICT-Konflikte koennen nur ignoriert werden (kein manueller Merge)
- KDiff3 / Meld / externes Merge-Tool = Phase 2
- multi_way_merge() (merge3-basiert) = Phase 2
- Bundle-Scan/Merge = Phase 3
- DLC-Konflikte = Phase 2+

---

## Betroffene Dateien

### Neue Dateien (7)

| Datei | Zeilen | Komplexitaet |
|-------|--------|--------------|
| `anvil/core/script_merger/__init__.py` | 20 | Niedrig |
| `anvil/core/script_merger/models.py` | 80 | Niedrig |
| `anvil/core/script_merger/ws_codec.py` | 50 | Mittel |
| `anvil/core/script_merger/scanner.py` | 200 | Hoch |
| `anvil/core/script_merger/merger.py` | 250 | Hoch |
| `anvil/core/script_merger/inventory.py` | 120 | Mittel |
| `anvil/widgets/script_merger_dialog.py` | 400 | Hoch |

### Geaenderte Dateien (3)

| Datei | Aenderung | Zeilen |
|-------|-----------|--------|
| `anvil/widgets/toolbar.py` | Script-Merger-Button | +20 |
| `anvil/mainwindow.py` | Handler + Sichtbarkeit | +50 |
| `anvil/plugins/games/game_witcher3.py` | `vanilla_scripts_dir()` | +10 |

### NICHT geaendert

- `conflict_scanner.py` — anderer Abstraktionslevel
- `mod_deployer.py` — Multi-Folder-Routes reichen
- `mod_list_io.py` — bestehende Funktionen genuegen (`read_global_modlist`, `write_global_modlist`, `remove_mod_globally`)
- `instance_manager.py` — Pfade ableitbar

---

## Scanner — KRITISCH: Zwei Mod-Patterns

Witcher 3 Mods in Anvils `.mods/` haben ZWEI verschiedene Ordner-Strukturen:

**Pattern A** (mit `mods/` Unterordner):
```
.mods/<AnvilName>/mods/<WitcherMod>/content/scripts/
Beispiel: .mods/modBloodAndSteel (Next Gen)/mods/modBloodAndSteel/content/scripts/
```

**Pattern B** (OHNE `mods/` Unterordner):
```
.mods/<AnvilName>/<WitcherMod>/content/scripts/
Beispiel: .mods/Indestructible Items (4.03)/modUnlimitedDurability/content/scripts/
```

**Auf Marcs System nutzen 4 von 6 Mods Pattern B!** Der Scanner MUSS beide Patterns
unterstuetzen, sonst werden die meisten Mods uebersehen.

### Scanner-Algorithmus

```python
def _find_script_dirs(self, mod_path: Path) -> list[tuple[str, Path]]:
    """Findet alle content/scripts/ Verzeichnisse in einem Mod.
    Gibt Liste von (witcher_mod_name, scripts_dir) zurueck."""
    results = []
    for content_dir in mod_path.rglob("content"):
        scripts_dir = content_dir / "scripts"
        if scripts_dir.is_dir():
            witcher_mod_name = content_dir.parent.name
            results.append((witcher_mod_name, scripts_dir))
    return results
```

### Konflikt-Definition

Ein Konflikt = eine Datei die von **>= 2 verschiedenen aktiven Mods** geaendert wird.

**NICHT als Konflikt zaehlen:**
- Datei die nur von EINER Mod geaendert wird (kein Merge noetig)
- Dateien unter `local/` (mod-eigene Scripts, kein Vanilla-Override)
- Dateien ohne Vanilla-Gegenstueck: Status = CONFLICT (keine gemeinsame Basis)

### Relativer Pfad

Basis fuer den relativen Pfad ist `scripts/` (OHNE `content/` prefix):
```
Vanilla:  content/content0/scripts/game/player/r4Player.ws
                            ^--- relative_path = "game/player/r4Player.ws"
Mod:      <WitcherMod>/content/scripts/game/player/r4Player.ws
                               ^--- relative_path = "game/player/r4Player.ws"
```

### XML-Scan

XML-Dateien werden unter `<WitcherMod>/content/` gesucht (nicht unter `scripts/`).
In der aktuellen Installation gibt es keine XML-Konflikte in `content/` — die
existierenden XML-Dateien liegen unter `bin/config/` (Menu-Konfiguration, kein Script).
Der Scanner unterstuetzt XML trotzdem fuer zukuenftige Mods.

---

## Signal-Flow

```
Toolbar: script_merger_btn.clicked
  -> mainwindow: _on_script_merger_clicked()
    -> Pruefe: vanilla_scripts_dir existiert? Wenn nein: Warnung, return
    -> active_mods via read_global_modlist() + read_active_mods()
    -> ScriptMergerDialog(...).exec()

Dialog intern:
  scan_btn -> _ScanWorker(QThread) -> progress/finished -> conflict_list
    Bei 0 Konflikten: Meldung "Keine Script-Konflikte gefunden"
  conflict_list.currentItemChanged -> detail_panel update
  auto_merge_btn -> ScriptMerger().auto_merge() -> status update
  auto_merge_all_btn -> _AutoMergeWorker(QThread) -> batch merge
  create_merge_mod_btn -> write files + modlist + inventory
    Button DEAKTIVIERT solange kein Merge mit Status MERGED existiert
    Wenn _merged_ bereits existiert: alten ueberschreiben (kein Duplikat)
  cleanup_btn -> Bestaetigung -> rmtree + remove_mod_globally (alle Profile)

Dialog schliesst:
  -> Worker-Threads sauber beenden (QThread.requestInterruption + wait)
  -> NUR wenn has_changes:
     -> mainwindow: _reload_mod_list() + _schedule_redeploy()
```

---

## Datenmodell (models.py)

```python
class MergeStatus(Enum):
    UNSCANNED = "unscanned"
    AUTO_MERGEABLE = "auto_mergeable"   # Hunks ueberlappen nicht
    CONFLICT = "conflict"               # Hunks ueberlappen ODER kein Vanilla
    MERGED = "merged"                   # Erfolgreich zusammengefuehrt
    IGNORED = "ignored"                 # User will nicht mergen

@dataclass
class DiffHunk:
    start_line: int        # 0-basiert, inklusive
    end_line: int          # 0-basiert, exklusive
    vanilla_lines: list[str]
    mod_lines: list[str]

    def overlaps(self, other: "DiffHunk") -> bool:
        return self.start_line < other.end_line and other.start_line < self.end_line

@dataclass
class ModVersion:
    mod_name: str          # Anvil Mod-Name (Ordner in .mods/)
    witcher_mod_name: str  # Witcher-Mod-Name (modXXX im Unterordner)
    file_path: Path        # Absoluter Pfad zur .ws/.xml Datei
    diff_hunks: list[DiffHunk] = field(default_factory=list)
    file_hash: str = ""    # SHA256 fuer Validierung

@dataclass
class ScriptConflict:
    relative_path: str     # "game/player/r4Player.ws" (ab scripts/)
    vanilla_path: Path | None  # None = kein Vanilla-Gegenstueck -> CONFLICT
    mod_versions: list[ModVersion] = field(default_factory=list)
    merge_status: MergeStatus = MergeStatus.UNSCANNED

@dataclass
class MergeResult:
    conflict: ScriptConflict
    success: bool
    merged_content: str | None = None
    unresolved_count: int = 0     # Anzahl ungeloester Konflikte (Phase 1: nur zaehlen)
    method: str = ""              # "auto" (Phase 1), "merge3"/"kdiff3" (Phase 2)
    error_message: str = ""

@dataclass
class MergeInventoryEntry:
    relative_path: str
    mods: list[str]               # Beteiligte Mod-Namen
    method: str
    timestamp: str                # ISO 8601
    source_hashes: dict[str, str] # {"vanilla": "abc...", "modXXX": "def..."}
    merged_hash: str
```

### Merge-Inventar JSON

```json
{
  "version": 1,
  "merged_mod_name": "mod0000_MergedFiles",
  "merges": [
    {
      "relative_path": "game/player/r4Player.ws",
      "mods": ["modBloodAndSteel", "modUnlimitedDurability"],
      "method": "auto",
      "timestamp": "2026-03-25T15:30:00",
      "source_hashes": {
        "vanilla": "abc123...",
        "modBloodAndSteel": "def456...",
        "modUnlimitedDurability": "ghi789..."
      },
      "merged_hash": "final012..."
    }
  ],
  "ignored": [
    "game/actor.ws"
  ]
}
```

Speicherort: `<instance_path>/.merge_inventory.json`

---

## UTF-16 LE Handling (ws_codec.py)

```
Lesen:  BOM-Detection: FF FE = UTF-16 LE, FE FF = UTF-16 BE,
        EF BB BF = UTF-8, sonst UTF-8 mit Latin-1 Fallback

Diff:   Python str -> difflib (arbeitet nativ mit str)

Schreiben: UTF-16 LE mit BOM (FF FE), CRLF Zeilenenden beibehalten
```

---

## Auto-Merge Algorithmus (merger.py)

```
Voraussetzung: conflict.merge_status == AUTO_MERGEABLE

1. Starte mit Vanilla-Inhalt als Basis (Zeilen-Liste)
2. Sammle ALLE Hunks von ALLEN Mods
3. Sortiere Hunks nach start_line ABSTEIGEND
   (Bottom-Up-Anwendung: spaetrere Zeilen zuerst, damit
   Zeilennummern fuer fruehere Hunks stabil bleiben)
4. Fuer jeden Hunk:
   Ersetze basis[start_line:end_line] durch hunk.mod_lines
5. Ergebnis: Merged Content mit allen Aenderungen aller Mods

Fuer 3+ Mods: Gleicher Algorithmus — alle Hunks aller Mods werden
gesammelt und Bottom-Up angewendet. Funktioniert weil die Hunks
per Definition nicht ueberlappen (AUTO_MERGEABLE).

CONFLICT-Konflikte: In Phase 1 NUR erkennen, NICHT auto-resolven.
User kann sie ignorieren. Manueller Merge (KDiff3 etc.) = Phase 2.
```

---

## Akzeptanz-Checkliste

### Toolbar + Dialog

- [ ] **AK-01:** Wenn User eine Witcher-3-Instanz laedt, wird der "Script Merger"-Button in der Toolbar sichtbar; bei allen anderen Games ist er unsichtbar
- [ ] **AK-02:** Wenn User auf "Script Merger" klickt, oeffnet sich der Dialog mit Pfad-Informationen (Vanilla-Dir, Anzahl aktiver Mods)
- [ ] **AK-03:** Wenn kein Vanilla-Scripts-Verzeichnis existiert, erscheint eine Warn-Meldung statt des Dialogs

### Scan

- [ ] **AK-04:** Wenn User auf "Scan starten" klickt, werden alle .ws-Konflikte zwischen aktiven Mods gefunden — sowohl Pattern A (mods/<WitcherMod>/content/scripts/) als auch Pattern B (<WitcherMod>/content/scripts/) werden erkannt
- [ ] **AK-05:** Wenn User auf "Scan starten" klickt, werden auch .xml-Konflikte unter content/ erkannt
- [ ] **AK-06:** Waehrend des Scans zeigt ein Fortschrittsbalken den Stand an und die GUI bleibt bedienbar
- [ ] **AK-07:** Dateien in `local/`-Unterverzeichnissen werden NICHT als Konflikt gezaehlt
- [ ] **AK-08:** Wenn der Scan 0 Konflikte findet, zeigt der Dialog eine Meldung "Keine Script-Konflikte gefunden"
- [ ] **AK-09:** Wenn User waehrend des Scans den Dialog schliesst, wird der Scan-Thread sauber beendet ohne Crash

### Konflikt-Details

- [ ] **AK-10:** Wenn User einen Konflikt auswaehlt, zeigt das Detail-Panel: relativen Pfad, beteiligte Mods mit Witcher-Mod-Name, und Hunk-Uebersicht (Zeilenbereiche pro Mod)
- [ ] **AK-11:** Wenn Hunks sich NICHT ueberlappen, wird die Datei als AUTO_MERGEABLE markiert (gelbes Icon)
- [ ] **AK-12:** Wenn Hunks sich ueberlappen ODER keine Vanilla-Version existiert, wird die Datei als CONFLICT markiert (rotes Icon)

### Auto-Merge

- [ ] **AK-13:** Wenn User bei AUTO_MERGEABLE auf "Auto-Merge" klickt, wird die Datei gemergt und Status wechselt zu MERGED (gruenes Icon)
- [ ] **AK-14:** Wenn 3+ Mods dieselbe Datei aendern und die Hunks sich NICHT ueberlappen, werden alle Aenderungen korrekt zusammengefuehrt (nicht nur 2 Mods)
- [ ] **AK-15:** Wenn User "Alle auto-mergen" klickt, werden alle AUTO_MERGEABLE gemergt; CONFLICT und IGNORED werden uebersprungen; Zusammenfassung am Ende
- [ ] **AK-16:** Wenn Auto-Merge fehlschlaegt, zeigt das Detail-Panel eine Fehlermeldung und der Status bleibt unveraendert

### Merge-Mod + Inventar

- [ ] **AK-17:** Der Button "Merge-Mod erstellen" ist DEAKTIVIERT (grau) solange kein Merge mit Status MERGED existiert
- [ ] **AK-18:** Wenn User "Merge-Mod erstellen" klickt, wird `.mods/_merged_/mods/mod0000_MergedFiles/content/scripts/` mit allen gemergten Dateien erstellt
- [ ] **AK-19:** Wenn `_merged_` bereits existiert und User erneut "Merge-Mod erstellen" klickt, wird der alte Merge-Mod ueberschrieben (kein Duplikat in modlist.txt)
- [ ] **AK-20:** Gemergte .ws-Dateien werden in UTF-16 LE mit BOM und CRLF Zeilenenden geschrieben
- [ ] **AK-21:** `_merged_` erscheint in modlist.txt an Position 0 (via `write_global_modlist`) und ist in active_mods.json ALLER Profile aktiviert
- [ ] **AK-22:** `.merge_inventory.json` speichert alle Merge-Details (relative Pfade, Mod-Namen, Methode, Zeitstempel, Quell-Hashes, Merge-Hash)
- [ ] **AK-23:** Nach Dialog-Schliessung aktualisiert sich die Mod-Liste und Redeploy wird ausgeloest — NUR wenn tatsaechlich Aenderungen gemacht wurden

### Cleanup

- [ ] **AK-24:** Wenn User "Aufraeumen" klickt und bestaetigt, werden _merged_-Ordner, modlist-Eintrag (via `remove_mod_globally` = alle Profile), und Inventar-Datei entfernt
- [ ] **AK-25:** Nach Cleanup zeigt erneuter Scan alle Konflikte mit Status UNSCANNED

### Ignore

- [ ] **AK-26:** Wenn User "Ignorieren" klickt, wechselt Status zu IGNORED und wird bei "Alle auto-mergen" uebersprungen
- [ ] **AK-27:** Ignorierte Konflikte bleiben nach Dialog-Schliessung und erneutem Oeffnen ignoriert (persistent im Inventar-JSON)

### Validierung

- [ ] **AK-28:** Wenn Quell-Mods sich seit letztem Merge geaendert haben (Hash-Mismatch), wird der Merge beim Oeffnen des Dialogs als "veraltet" markiert und der User informiert

### UTF-16 LE + Encoding

- [ ] **AK-29:** Mod-Dateien in UTF-8 statt UTF-16 LE werden trotzdem korrekt gelesen (BOM-Detection mit Fallback)

### Stabilitaet

- [ ] **AK-30:** Bei IO-Fehlern (fehlende Datei, Permission denied) stuerzt der Dialog nicht ab sondern zeigt Fehlermeldung
- [ ] **AK-31:** `restart.sh` startet ohne Fehler
