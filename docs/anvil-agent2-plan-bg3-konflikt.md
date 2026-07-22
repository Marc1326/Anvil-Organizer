# Agent 2: LSPKReader-Analyse fuer BG3 Konflikt-Erkennung

**Datum:** 2026-04-04
**Feature:** BG3 Konflikt-Erkennung (Datei-Konflikte innerhalb von .pak-Archiven)

---

## 1. Aktuelle Situation: Warum BG3 keine Konflikt-Erkennung hat

### Problem
Der bestehende `ConflictScanner` (`anvil/core/conflict_scanner.py`) arbeitet auf **loose Dateien** im `.mods/`-Verzeichnis. Er iteriert ueber Dateien auf dem Dateisystem per `rglob("*")` oder ueber den gecachten `ModIndex`.

BG3-Mods hingegen werden als **.pak-Dateien** direkt in den BG3-Mods-Ordner kopiert (z.B. `~/.local/share/Larian Studios/Baldur's Gate 3/Mods/MyMod.pak`). Sie landen **NICHT** im Anvil `.mods/`-Verzeichnis als loose Dateien. Daher erkennt der ConflictScanner bei BG3 keine Konflikte — er sieht nur die .pak-Dateien als opake Blob-Dateien, nicht deren Inhalt.

### Loesung
Der `LSPKReader` muss um eine `get_file_list()`-Methode erweitert werden, die alle Dateinamen innerhalb eines .pak-Archivs zurueckgibt — ohne die Dateien selbst zu extrahieren. Diese Liste kann dann vom ConflictScanner verglichen werden.

---

## 2. LSPKReader: Detaillierte Format-Analyse

### Datei: `anvil/core/lspk_parser.py` (259 Zeilen)

### 2.1 Unterstuetzte Formate

**Aktuell: NUR LSPK V18** (BG3's einziges Format)

```python
LSPK_MAGIC = b"LSPK"
LSPK_VERSION = 18
```

Zeile 102-103: Wenn `version != LSPK_VERSION`, wird `None` zurueckgegeben mit Fehlermeldung. Andere Versionen (v13, v15) werden **nicht** unterstuetzt und sind fuer BG3 auch nicht relevant.

### 2.2 Header-Format (LSPKHeader16)

**Offset:** Byte 4 (nach 4-Byte-Magic "LSPK")
**Groesse:** 36 Bytes

```python
_HEADER_FMT = "<I Q I B B 16s H"
_HEADER_SIZE = 36  # struct.calcsize Ergebnis
```

| Offset (rel. zu Byte 4) | Typ | Groesse | Feld | Beschreibung |
|---|---|---|---|---|
| 0 | uint32 | 4 | Version | Muss 18 sein |
| 4 | uint64 | 8 | FileListOffset | Absoluter Offset der Dateiliste im .pak |
| 12 | uint32 | 4 | FileListSize | Groesse der komprimierten Dateiliste |
| 16 | uint8 | 1 | Flags | Paket-Flags |
| 17 | uint8 | 1 | Priority | Paket-Prioritaet |
| 18 | byte[16] | 16 | MD5 | MD5-Checksumme |
| 34 | uint16 | 2 | NumParts | Anzahl Teile (Multi-Part-Archiv) |
| **Total** | | **36** | | |

### 2.3 FileEntry18-Format (pro Datei)

**Groesse:** 272 Bytes pro Eintrag

```python
_ENTRY_FMT = "<256s I H B B I I"
_ENTRY_SIZE = 272  # struct.calcsize Ergebnis
```

| Offset (rel.) | Typ | Groesse | Feld | Beschreibung |
|---|---|---|---|---|
| 0 | byte[256] | 256 | Name | Null-terminierter Dateiname (UTF-8) |
| 256 | uint32 | 4 | OffsetInFile1 | Untere 32 Bits des Datei-Offsets |
| 260 | uint16 | 2 | OffsetInFile2 | Obere 16 Bits des Datei-Offsets |
| 262 | uint8 | 1 | ArchivePart | Teil-Index bei Multi-Part-Archiven |
| 263 | uint8 | 1 | Flags | Kompression (untere 4 Bits) |
| 264 | uint32 | 4 | SizeOnDisk | Komprimierte Groesse |
| 268 | uint32 | 4 | UncompressedSize | Unkomprimierte Groesse |
| **Total** | | **272** | | |

**Name-Feld (256 Bytes):** Enthaelt den vollstaendigen relativen Pfad innerhalb des .pak, null-terminiert. Beispiele:
- `Public/MyMod/RootTemplates/merged.lsf`
- `Mods/MyMod/meta.lsx`
- `Generated/Public/MyMod/Assets/texture.dds`

### 2.4 Komprimierte Dateiliste

Die Dateiliste selbst ist LZ4-komprimiert gespeichert. Der Lesevorgang (Zeilen 107-116):

```
1. f.seek(file_list_offset)         ← Springe zum Offset aus dem Header
2. num_files = read uint32           ← Anzahl der Dateien (4 Bytes)
3. compressed_size = read uint32     ← Groesse der komprimierten Daten (4 Bytes)
4. compressed_data = read(compressed_size)
5. expected_size = 272 * num_files   ← Erwartete unkomprimierte Groesse
6. decompressed = lz4.block.decompress(compressed_data, uncompressed_size=expected_size)
```

Nach Dekompression: Ein fortlaufender Byte-Buffer mit `num_files * 272` Bytes, der sequentiell in 272-Byte-Chunks geparst wird.

### 2.5 Aktueller _read()-Ablauf (Zeilen 87-164)

```
_read(pak_path):
  1. Oeffne Datei im Binaer-Modus
  2. Lese 4 Bytes Magic → Pruefe "LSPK"
  3. Lese 36 Bytes Header → Pruefe Version == 18
  4. Springe zu FileListOffset
  5. Lese num_files (uint32) und compressed_size (uint32)
  6. Lese compressed_data
  7. Dekomprimiere mit LZ4
  8. Parse ALLE FileEntry18-Eintraege in eine entries-Liste  ← HIER liegt die Dateiliste
  9. Suche nach info.json und meta.lsx in entries
  10. Extrahiere und parse nur die Metadaten-Datei
  11. Gebe Metadaten-Dict zurueck
  12. Die entries-Liste wird verworfen (GC)         ← HIER geht die Dateiliste verloren
```

**Entscheidend:** In Schritt 8 wird die KOMPLETTE Dateiliste bereits geparst. In Schritt 12 wird sie verworfen, weil `_read()` nur die Metadaten zurueckgibt. Fuer `get_file_list()` muss dieser Schritt beibehalten werden.

---

## 3. Vorschlag: get_file_list() Methode

### 3.1 Interface-Design

```python
def get_file_list(self, pak_path: Path) -> list[str] | None:
    """Alle relativen Pfade innerhalb eines .pak zurueckgeben.
    
    Returns:
        Liste von relativen Pfaden (Strings) oder None bei Fehler.
        Beispiel: ["Public/MyMod/RootTemplates/merged.lsf",
                   "Mods/MyMod/meta.lsx", ...]
    """
```

**Warum `list[str]` statt `list[dict]`:**
- Fuer Konflikt-Erkennung reichen die Dateinamen/Pfade
- Kein Bedarf an Offset/Size/Compression-Infos fuer diesen Use-Case
- Deutlich weniger Speicherverbrauch (wichtig bei 86+ .pak Dateien)

### 3.2 Alternatives Interface (wenn mehr Infos benoetigt)

```python
def get_file_list_detailed(self, pak_path: Path) -> list[dict] | None:
    """Alle Dateien mit Details zurueckgeben.
    
    Returns:
        Liste von Dicts: {"name": str, "size": int}
        oder None bei Fehler.
    """
```

### 3.3 Implementierungsstrategie

Die Methode kann den bestehenden Code WIEDERVERWENDEN. Der Parsing-Code in `_read()` (Zeilen 107-140) liest bereits alle Eintraege. Es gibt zwei Ansaetze:

**Ansatz A: Refactoring von _read() (empfohlen)**

`_read()` wird in zwei Teile zerlegt:
1. `_parse_entries(pak_path) -> list[dict]` — Gibt die rohe entries-Liste zurueck
2. `_read()` ruft `_parse_entries()` auf und extrahiert daraus die Metadaten
3. `get_file_list()` ruft `_parse_entries()` auf und gibt nur die Namen zurueck

Vorteil: Kein duplizierter Code, saubere Trennung.

**Ansatz B: Eigene lightweight Methode**

Komplett eigene Methode, die nur Header + Dateiliste liest und sofort nach dem Parsen der Entry-Namen zurueckgibt (ohne Datei-Extraktion). Gleicher Code wie in `_read()` Zeilen 87-140, aber ohne die Zeilen 142-164 (Metadaten-Extraktion).

Vorteil: Noch minimaler (kein `_extract_file` noetig).

**Empfehlung: Ansatz A** — weniger Code-Duplikation, einfacher wartbar.

---

## 4. Performance-Analyse

### 4.1 Aktuelles Szenario: 86+ .pak Dateien

Typische BG3-Installation hat 60-200 Mods. Jedes Mod = 1 .pak Datei.

**Pro .pak-Datei benoetigt get_file_list():**
1. `open()` — 1 Datei-Handle
2. `read(4)` — Magic (4 Bytes)
3. `read(36)` — Header (36 Bytes)
4. `seek(file_list_offset)` — 1 Seek
5. `read(8)` — num_files + compressed_size (8 Bytes)
6. `read(compressed_size)` — Komprimierte Dateiliste (variabel, typisch 1-100 KB)
7. `lz4.block.decompress()` — LZ4-Dekompression
8. `struct.unpack()` — Pro Entry (272 Bytes, davon 256 Bytes Name)

**Geschaetzte Zeit pro .pak:** 1-5 ms (IO-dominiert, LZ4 ist extrem schnell)
**Geschaetzte Gesamtzeit fuer 100 .pak:** 100-500 ms

### 4.2 Speicherverbrauch

Pro .pak-Datei wird die komplette Entry-Liste in den Speicher geladen:
- 100 Dateien im .pak: 100 * 272 = 27.200 Bytes dekomprimiert
- 1000 Dateien im .pak: 272.000 Bytes dekomprimiert
- Als Python-String-Liste: ~100 Bytes pro Pfad * 1000 = 100 KB

Fuer 100 .pak mit je 200 Dateien: ~2 MB String-Daten = vernachlaessigbar.

### 4.3 Caching-Strategie

**Empfehlung: JSON-Cache analog zu ModIndex**

```
.pak-conflict-cache.json:
{
    "version": 1,
    "paks": {
        "MyMod.pak": {
            "mtime": 1712345678.0,
            "size": 12345678,
            "files": ["Public/MyMod/file1.lsf", "Mods/MyMod/meta.lsx", ...]
        }
    }
}
```

- Auf Basis von `mtime` + `size` (gleicher Ansatz wie ModIndex)
- Nur geaenderte .pak Dateien neu scannen
- Cache im Instanz-Verzeichnis speichern

**Ohne Cache:** 100-500 ms bei jedem Start (akzeptabel)
**Mit Cache:** <10 ms nach dem ersten Scan (optimal)

---

## 5. Edge Cases und Fehlerbehandlung

### 5.1 Leere .pak Dateien
- `num_files = 0` → `get_file_list()` gibt leere Liste zurueck `[]`
- Kein Fehler, aber auch keine Konflikte moeglich

### 5.2 Korrupte .pak Dateien
- Falsches Magic → `None` zurueckgeben
- Header zu kurz → `None` zurueckgeben
- LZ4-Dekompression fehlschlaegt → Exception wird von `read_pak_metadata()` gefangen, `None` zurueckgeben
- `get_file_list()` sollte dasselbe try/except Pattern verwenden
- **Wichtig:** Korrupte .pak darf NICHT den gesamten Scan abbrechen

### 5.3 Verschiedene LSPK-Versionen
- V13, V15 kommen in BG3 **nicht** vor — BG3 verwendet ausschliesslich V18
- Falls ein User eine V13/V15-Datei hat (z.B. aus Divinity: Original Sin 2), wird sie sauber uebersprungen (Zeile 102-103)
- Fuer Zukunftssicherheit: Fehlermeldung loggen, aber nicht abstuerzen

### 5.4 Sehr grosse .pak Dateien
- BG3 Shared.pak (Vanilla) ist ~60 GB — MUSS ignoriert werden (Vanilla-Datei)
- Mod-spezifische .pak sind typisch 1 MB - 500 MB
- Die Dateiliste ist auch bei grossen .pak-Dateien klein (<1 MB unkomprimiert)
- **Kein Problem:** Nur die Dateiliste wird gelesen, nicht die Dateiinhalte

### 5.5 Multi-Part-Pakete
- Das `ArchivePart`-Feld (Byte 262) zeigt an, in welchem Teil die Dateidaten liegen
- Fuer `get_file_list()` irrelevant — wir lesen nur die Namen, nicht die Daten
- Die Dateiliste selbst ist immer im Haupt-.pak

### 5.6 Doppelte Pfade innerhalb eines .pak
- Theoretisch moeglich, aber in der Praxis nicht vorkommend
- `get_file_list()` sollte die rohe Liste zurueckgeben (keine Deduplikation noetig)

### 5.7 Pfad-Normalisierung
- .pak-Eintraege verwenden Forward-Slashes (Linux-kompatibel)
- `name_raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace")` — bestehendes Parsing korrekt
- Fuer Konflikt-Vergleich: Case-insensitive Vergleich empfohlen (BG3 ist Windows-Origin)

---

## 6. Integration in den ConflictScanner

### 6.1 Aktueller Flow (Nicht-BG3)

```
ConflictScanner.scan_conflicts(mods=[...])
  └─ Fuer jeden Mod:
       └─ ModIndex.get_file_list(mod_name)  oder  rglob("*")
            └─ Vergleiche relative Pfade
```

### 6.2 Neuer Flow (BG3)

Der ConflictScanner muss fuer BG3 anders arbeiten:

```
ConflictScanner.scan_conflicts(mods=[...], game_plugin=bg3_plugin)
  └─ BG3-Erkennung: game_plugin hat Methode "get_pak_file_list()" oder Flag
  └─ Fuer jeden Mod:
       └─ Finde zugehoerige .pak-Datei(en)
       └─ LSPKReader.get_file_list(pak_path)
            └─ Vergleiche relative Pfade innerhalb der .pak-Dateien
```

### 6.3 Mapping: Mod-Name → .pak-Datei(en)

Das ist die eigentliche Herausforderung. Aktuell:
- Anvil kennt Mod-Namen aus modlist.txt / modsettings.lsx
- Die .pak-Dateien liegen im BG3-Mods-Ordner (nicht in .mods/)
- Die Zuordnung laeuft ueber UUID (bg3_mod_state.json)

**Loesung:** Der BG3-Installer speichert bereits `pak_file` im State:
```python
mods.append({
    "uuid": meta["uuid"],
    "name": meta.get("name", ""),
    "pak_file": pak.name,    # ← Diese Zuordnung existiert bereits
})
```

---

## 7. Welche Dateien in .pak sind fuer Konflikte relevant?

### 7.1 Typische BG3 .pak Struktur

```
Public/<ModFolder>/
    RootTemplates/merged.lsf        ← HOCH: Ueberschreibt Item/NPC-Definitionen
    Stats/Generated/Data/*.txt       ← HOCH: Ueberschreibt Gameplay-Stats
    Content/Assets/[textures].dds    ← MITTEL: Texturen
    GUI/Assets/[icons].dds           ← MITTEL: UI-Icons
    Localization/*.loca              ← NIEDRIG: Uebersetzungen (oft gewollt)
Mods/<ModFolder>/
    meta.lsx                         ← IGNORIEREN: Mod-Metadaten, immer einzigartig
    ScriptExtender/                  ← NIEDRIG: SE-Lua-Scripts (selten Konflikt)
Generated/
    Public/<ModFolder>/             ← HOCH: Generierte Game-Daten
```

### 7.2 Ignore-Patterns fuer BG3-Pak-Konflikte

Zusaetzlich zu den bestehenden `get_conflict_ignores()`:
```python
"**/meta.lsx",       # Mod-Metadaten (immer einzigartig pro Mod)
"**/info.json",      # Mod-Info (bereits ignoriert)
```

### 7.3 Wann ist ein Dateikonflikt in BG3 real?

Zwei .pak-Dateien haben eine Datei mit **exakt dem gleichen relativen Pfad**.
Beispiel:
- Mod A: `Public/Shared/Stats/Generated/Data/Armor.txt`
- Mod B: `Public/Shared/Stats/Generated/Data/Armor.txt`
→ ECHTER KONFLIKT: Beide ueberschreiben die gleiche Vanilla-Datei.

BG3 laedt .pak-Dateien in alphabetischer Reihenfolge (oder nach Prioritaet in modsettings.lsx). Die zuletzt geladene Datei gewinnt.

---

## 8. Zusammenfassung der Implementierungs-Empfehlungen

| Aspekt | Empfehlung |
|---|---|
| **Neue Methode** | `LSPKReader.get_file_list(pak_path) -> list[str] \| None` |
| **Code-Wiederverwendung** | Refactoring: `_parse_entries()` als gemeinsame Basis fuer `_read()` und `get_file_list()` |
| **Rueckgabeformat** | `list[str]` — nur relative Pfade, keine weiteren Metadaten |
| **Fehlerbehandlung** | `None` bei Fehler, gleiche try/except Struktur wie `read_pak_metadata()` |
| **Caching** | Separater Cache (`.pak-conflict-cache.json`) mit mtime+size als Key |
| **Performance** | 100-500 ms ohne Cache, <10 ms mit Cache, fuer 100 .pak akzeptabel |
| **Versionen** | Nur V18 (BG3), andere uebersprungen mit Warnung |
| **Edge Cases** | Leere .pak → [], korrupte → None, grosse Vanilla → ignorieren |
| **ConflictScanner-Integration** | Neuer BG3-Pfad im Scanner, nutzt .pak-Dateiliste statt Dateisystem |
| **Pfad-Vergleich** | Case-insensitive (BG3 stammt von Windows) |
