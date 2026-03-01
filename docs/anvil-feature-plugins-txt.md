# Feature-Spec: plugins.txt bleibt leer nach Deploy -- Konsolidierter Report

**Datum:** 2026-03-01
**Konsolidiert aus:** Agent 1, 2, 3 Reports
**Status:** Analyse abgeschlossen -- Fix-Plan erstellt

---

## 1. Problembeschreibung

Nach dem Deploy von 4 Mods (CBBE, GCM, LooksMenu, Undressed Character Creation) fuer Fallout 4 soll `plugins.txt` mindestens 12 Eintraege enthalten (8 PRIMARY + 4 Mod-ESPs). Marc berichtet, dass die Datei LEER bleibt.

---

## 2. Ist-Zustand (verifiziert am 2026-03-01)

### 2.1 Data-Verzeichnis

Im Verzeichnis `/mnt/gamingS/SteamLibrary/steamapps/common/Fallout 4/Data/` liegen:

| Typ | Dateien | Status |
|-----|---------|--------|
| PRIMARY ESMs | 8 Stueck (Fallout4.esm + 7 DLCs) | Originale Dateien (kein Symlink) |
| Mod ESPs | CBBE.esp, GCM.esp, LooksMenu.esp, Undressed_Character_Creation.esp | Symlinks nach `.mods/` -- KORREKT |
| CC ESLs | 9 Stueck (ccBGS..., ccFSV..., ccOTM..., ccSBJ...) | Originale Dateien |
| **Gesamt** | **21 Plugin-Dateien** | Alle werden von scan_plugins() erkannt |

### 2.2 plugins.txt-Dateien im Proton-Prefix

Es existieren **ZWEI** Dateien im selben Verzeichnis:
`/mnt/gamingS/SteamLibrary/steamapps/compatdata/377160/pfx/drive_c/users/steamuser/AppData/Local/Fallout4/`

| Datei | Groesse | Erstellt | Inhalt |
|-------|---------|----------|--------|
| `plugins.txt` (klein-p) | 588 Bytes | 07:19 | **21 Eintraege -- KORREKT** |
| `Plugins.txt` (gross-P) | 109 Bytes | 07:03 | **NUR Header-Kommentare -- LEER** |

### 2.3 scan_plugins() Direkttest

```
$ python3 -c "... PluginsTxtWriter.scan_plugins() ..."
Scanned plugins: 21
  Fallout4.esm, DLCRobot.esm, ... (8 PRIMARY)
  CBBE.esp, GCM.esp, LooksMenu.esp, Undressed_Character_Creation.esp (4 Mod-ESPs)
  ccBGS...esl (9 CC-ESLs)
```

Ergebnis: scan_plugins() funktioniert einwandfrei. Alle 21 Plugins werden erkannt, inklusive aller 4 Mod-ESP-Symlinks.

---

## 3. Root-Cause-Analyse

### 3.1 Hauptursache: Case-Sensitivity-Problem (Wahrscheinlichkeit: 90%)

**Das Problem:** Auf Linux (ext4/btrfs) sind `plugins.txt` und `Plugins.txt` zwei verschiedene Dateien. Unter Windows (NTFS) waeren sie identisch.

- **Anvil** schreibt nach `plugins.txt` (klein-p) -- via `_WIN_PLUGINS_TXT = "...Fallout4/plugins.txt"`
- **Fallout 4** (via Proton/Wine) erstellt `Plugins.txt` (gross-P) beim ersten Start
- **Ergebnis:** Auf dem Dateisystem existieren BEIDE nebeneinander. Das Spiel liest moeglicherweise die leere `Plugins.txt` statt Anvils korrekte `plugins.txt`

**Evidenz:**
- `Plugins.txt` (gross-P) wurde um 07:03 erstellt (vom Spiel beim Start via Proton)
- `plugins.txt` (klein-p) wurde um 07:19 erstellt (von Anvil beim Deploy)
- Beide koexistieren -- auf Windows unmoeglich, auf Linux normal

**Wie Proton/Wine mit Case-Sensitivity umgeht:**
- Proton hat ein casefold-System das normalerweise `plugins.txt` == `Plugins.txt` behandelt
- ABER: Wenn beide Dateien physisch existieren, kann Proton nicht entscheiden welche "die richtige" ist
- Je nach Wine/Proton-Version und casefold-Einstellung wird eine der beiden gewaehlt
- Fallout 4 erwartet intern `Plugins.txt` (Windows-Standard mit grossem P)

### 3.2 Ablauf des Problems

```
1. User startet Fallout 4 zum ersten Mal via Steam/Proton
   -> Spiel erstellt "Plugins.txt" (gross-P, Windows-Konvention)
   -> Inhalt: nur Header-Kommentare (keine Mods installiert)

2. User oeffnet Anvil Organizer, deployed Mods
   -> PluginsTxtWriter.write() erstellt NEUE Datei "plugins.txt" (klein-p)
   -> Inhalt: 21 Plugins (korrekt)
   -> "Plugins.txt" (gross-P) bleibt UNVERAENDERT daneben liegen

3. User startet Fallout 4 erneut via Steam/Proton
   -> Proton findet ZWEI Dateien: "plugins.txt" UND "Plugins.txt"
   -> Proton waehlt (je nach Version/casefold) die falsche: "Plugins.txt"
   -> Spiel sieht: leere plugins.txt -> keine Mod-Plugins geladen
   -> Marc beobachtet: "plugins.txt bleibt LEER"
```

### 3.3 Alle moeglichen Fehlerquellen (sortiert nach Wahrscheinlichkeit)

| # | Fehlerquelle | Wahrsch. | Status | Begruendung |
|---|-------------|----------|--------|-------------|
| 1 | **Case-Sensitivity:** Zwei Dateien `plugins.txt` + `Plugins.txt` koexistieren | 90% | BESTAETIGT | Beide Dateien physisch vorhanden, unterschiedlicher Inhalt |
| 2 | **Timing:** Purge loeschte plugins.txt vor Neuschreibung | 5% | GEFIXT | Commit 69521fc entfernte das Loeschen bei Purge |
| 3 | **protonPrefix() gibt None zurueck** | 2% | WIDERLEGT | Test zeigt korrekten Pfad, Store=steam |
| 4 | **scan_plugins() findet keine Dateien** | 1% | WIDERLEGT | Test zeigt 21 Plugins |
| 5 | **Schreibberechtigung fehlt** | 1% | WIDERLEGT | Datei wird geschrieben (588 Bytes) |
| 6 | **_current_plugin ist None bei silent_deploy()** | 0.5% | UNWAHRSCHEINLICH | update_game() wird vor set_instance_path() aufgerufen |
| 7 | **Data/-Verzeichnis existiert nicht** | 0.5% | WIDERLEGT | Verzeichnis existiert mit 21 Plugin-Dateien |

---

## 4. Loesungsplan

### 4.1 Fix: Case-Varianten bereinigen (PRIMAER)

**Datei: `anvil/core/plugins_txt_writer.py`**

Neue private Methode hinzufuegen:

```python
def _remove_case_variants(self, txt_path: Path) -> None:
    """Remove case-variant files (e.g. Plugins.txt vs plugins.txt).

    On Linux, the filesystem is case-sensitive, so both can coexist.
    Proton/Wine gets confused when both exist. Remove any variant
    that doesn't match our exact target filename.
    """
    target_name_lower = txt_path.name.lower()
    parent = txt_path.parent
    if not parent.is_dir():
        return
    try:
        for entry in os.scandir(parent):
            if (
                entry.is_file()
                and entry.name.lower() == target_name_lower
                and entry.name != txt_path.name
            ):
                try:
                    (parent / entry.name).unlink()
                    print(f"{_TAG} Removed case-variant: {entry.name}")
                except OSError:
                    pass
    except OSError:
        pass
```

In `write()` aufrufen -- VOR dem Schreiben:
```python
# Remove case-variants before writing
self._remove_case_variants(txt_path)
```

In `remove()` aufrufen -- Case-Varianten ebenfalls loeschen:
```python
# Also remove case-variants
self._remove_case_variants(txt_path)
```

### 4.2 Verbesserung: Diagnostik-Logging (SEKUNDAER)

**Datei: `anvil/core/plugins_txt_writer.py`**

In `scan_plugins()` differenziertes Logging:
- Data/ nicht vorhanden -> Log "Data directory not found: {data_dir}"
- Data/ vorhanden aber keine Plugins -> Log "No .esp/.esm/.esl files in {data_dir}"
- OSError -> Log bereits vorhanden

### 4.3 Verbesserung: write()-Rueckgabe pruefen (OPTIONAL)

**Datei: `anvil/widgets/game_panel.py`**

In `silent_deploy()` den Rueckgabewert von `write()` pruefen:
```python
result_path = writer.write()
if result_path is None:
    print("[GamePanel] plugins.txt write failed or skipped", flush=True)
```

---

## 5. Betroffene Dateien

| Datei | Aenderungstyp | Risiko |
|-------|---------------|--------|
| `anvil/core/plugins_txt_writer.py` | Case-Varianten-Handling + Diagnostik | Niedrig |
| `anvil/widgets/game_panel.py` | Rueckgabe-Handling (optional) | Niedrig |
| `anvil/plugins/games/game_fallout4.py` | **Keine Aenderung noetig** | - |
| `anvil/plugins/base_game.py` | **Keine Aenderung noetig** | - |
| Locale-Dateien | **Keine Aenderung noetig** (nur Logging, kein UI-Text) | - |

---

## 6. Akzeptanz-Kriterien (ALLE muessen erfuellt sein)

- [ ] Kriterium 1: Wenn Anvil plugins.txt schreibt und eine `Plugins.txt` (gross-P) im selben Verzeichnis existiert, wird die gross-P-Variante VOR dem Schreiben geloescht, sodass nur EINE Datei mit dem korrekten Namen (`plugins.txt`) verbleibt
- [ ] Kriterium 2: Wenn User silent_deploy() ausfuehrt und 4 Mod-ESPs deployed sind, enthaelt die resultierende plugins.txt mindestens 12 Eintraege (8 PRIMARY + 4 Mod-ESPs) -- nicht 0
- [ ] Kriterium 3: Wenn User silent_deploy() ausfuehrt und Creation Club ESLs im Data-Verzeichnis liegen, werden diese ebenfalls in plugins.txt aufgefuehrt (aktuell 21 total)
- [ ] Kriterium 4: Wenn User silent_purge() ausfuehrt, werden ALLE Case-Varianten von plugins.txt entfernt (sowohl `plugins.txt` als auch `Plugins.txt` als auch andere Varianten wie `PLUGINS.TXT`)
- [ ] Kriterium 5: Wenn scan_plugins() eine leere Liste zurueckgibt, wird im Log der Grund ausgegeben ("Data directory not found" vs. "No plugin files found" vs. OSError-Details)
- [ ] Kriterium 6: Wenn write() fehlschlaegt (return None), wird in silent_deploy() eine Warnung ins Log geschrieben
- [ ] Kriterium 7: Wenn write() erfolgreich ist, wird im Log die Anzahl der geschriebenen Plugins UND der Ziel-Pfad ausgegeben (bereits implementiert -- sicherstellen dass es bestehen bleibt)
- [ ] Kriterium 8: Wenn die Proton-Prefix-Verzeichnisstruktur nicht existiert, wird sie von write() automatisch erstellt (bereits implementiert via makedirs -- sicherstellen dass es bestehen bleibt)
- [ ] Kriterium 9: Nicht-Bethesda-Spiele (Cyberpunk 2077, Witcher 3, BG3, RDR2) sind von den Aenderungen nicht betroffen -- kein veraendertes Verhalten
- [ ] Kriterium 10: restart.sh startet ohne Fehler

---

## 7. Zusammenfassung der 3 Agent-Reports

### Agent 1: plugins_txt_writer.py Analyse
- Code ist solide und defensiv geschrieben
- Symlink-Handling ist korrekt (follow_symlinks=True Default erkennt Symlinks als Dateien)
- Kein Bug im Writer selbst -- Scan und Write funktionieren korrekt
- **Luecke:** Rueckgabewert von write() wird vom Aufrufer ignoriert

### Agent 2: Aufrufpfad silent_deploy() Analyse
- plugins.txt-Block wird UNABHAENGIG vom Deploy-Ergebnis ausgefuehrt
- 7 Bedingungen muessen erfuellt sein (alle verifiziert als True fuer Fallout 4 Steam)
- Purge loescht plugins.txt NICHT MEHR (seit Commit 69521fc)
- Kein Redeploy bei Mod-Toggle (beabsichtigt -- Deploy erst bei Profil-/Instanzwechsel oder App-Start)

### Agent 3: MO2-Vergleich + Fallout 4 Plugin
- Kritischer Unterschied: MO2 scannt VFS, Anvil scannt physisches Data/ (korrekt fuer Symlink-Deploy)
- Mod-Index-Berechnung fuer ESL-Plugins ist falsch (fortlaufend statt FE:xxx) -- Phase-2-Problem
- GOG-Support fehlt (protonPrefix gibt None zurueck) -- bekannte Einschraenkung
- Plugin-Aktivierung/-Deaktivierung nicht implementiert (Phase 1: alle aktiv mit `*`-Prefix)

### Agent 4 (Konsolidierung -- dieses Dokument)
- **Root Cause identifiziert:** Case-Sensitivity auf Linux -- `plugins.txt` und `Plugins.txt` existieren als zwei getrennte Dateien nebeneinander
- Die Schreib-Logik funktioniert korrekt (verifiziert: 21 Plugins in `plugins.txt`)
- Das Problem: Fallout 4 via Proton liest moeglicherweise die ANDERE (leere) Datei `Plugins.txt`
- **Fix:** Case-Varianten bereinigen bevor geschrieben wird

---

## 8. Risiken und Einschraenkungen

| Risiko | Bewertung | Mitigation |
|--------|-----------|------------|
| Proton-casefold aendert sich in Zukunft | Niedrig | Unser Fix ist defensiv -- loescht nur "falsche" Varianten |
| Spiel erstellt `Plugins.txt` bei jedem Start neu | Mittel | Anvil muesste plugins.txt bei jedem Deploy neu schreiben (bereits der Fall) |
| Andere Bethesda-Spiele haben andere Case-Konventionen | Niedrig | _remove_case_variants ist generisch und funktioniert fuer alle Varianten |
| GOG-Spiele haben kein Proton-Prefix | Bekannt | Separate Feature-Anforderung -- nicht Teil dieses Fixes |

---

## 9. Phase 2 (Spaeter, nicht Teil dieses Fixes)

- Drag-and-Drop fuer Plugin-Reihenfolge im Plugins-Tab
- Plugin-Aktivierung/-Deaktivierung per Checkbox (mit/ohne `*`-Prefix)
- ESL-Index-Berechnung (FE:xxx statt fortlaufend)
- Master-Dependency-Validierung
- GOG/Heroic/Lutris Wine-Prefix Support
- LOOT-Integration fuer automatische Sortierung
