# QA Agent 1: nexus_filename_parser.py + nexus_api.py
Datum: 2026-03-02

## Geprueftes Feature
"Nexus Query Info fuer Downloads-Tab" -- Akzeptanzkriterien 14 und 15

## Gepruefte Kriterien

- [x] 14: `extract_nexus_mod_id("Peachu Casual Dress - Archive XL-14817-1-1716336327.rar")` gibt 14817 zurueck
- [x] 15: `extract_nexus_mod_id("random_mod_without_id.zip")` gibt None zurueck

## Test-Ergebnisse

### Haupt-Tests (alle aus der Feature-Spec)

| Dateiname | Erwartet | Ergebnis | Status |
|-----------|----------|----------|--------|
| `Peachu Casual Dress - Archive XL-14817-1-1716336327.rar` | 14817 | 14817 | PASS |
| `Caldos Ripper-8378-15-0-0-1760955833.zip` | 8378 | 8378 | PASS |
| `Ripper Boots-5231-1-1663279901.zip` | 5231 | 5231 | PASS |
| `MELUMINARY'S VIRTUAL ATELIER - FEMV-14248-15-1757310313.zip` | 14248 | 14248 | PASS |
| `Kwek's Sartorial Omnibus Shop - REDMod Version-6779-1-1-5-1679005572.zip` | 6779 | 6779 | PASS |
| `random_mod_without_id.zip` | None | None | PASS |
| (leerer String) | None | None | PASS |
| `mod.zip` | None | None | PASS |
| `mod-1-1234567890.zip` | None | None | PASS (einstellige Zahl korrekt ignoriert) |

### Erweiterte Edge-Cases

| Dateiname | Erwartet | Ergebnis | Status | Anmerkung |
|-----------|----------|----------|--------|-----------|
| `mod-.zip` | None | None | PASS | Bindestrich ohne Zahl |
| `SomeMod-999999-1-1234567890.zip` | 999999 | 999999 | PASS | Grosse Mod-ID |
| `OldMod-10-1-1234567890.zip` | 10 | 10 | PASS | Zweistellige Mod-ID |
| `Cool Mod (v2) - Special Ed!-54321-2-1-1234567890.zip` | 54321 | 54321 | PASS | Sonderzeichen |
| `SomeMod-12345-1-1234567890.7z` | 12345 | 12345 | PASS | .7z Extension |
| `SomeMod-12345-1-1234567890.ZIP` | 12345 | 12345 | PASS | Gross-Endung |
| `SomeMod-12345-1-1234567890.exe` | (offen) | 12345 | INFO | Fallback-Regex greift (s.u.) |
| `SomeMod-12345-1.zip` | (offen) | 12345 | INFO | Fallback-Regex greift (s.u.) |
| `SomeMod-12345-1-1234567890` | (offen) | 12345 | INFO | Fallback-Regex greift (s.u.) |
| `None` (Python None) | -- | TypeError | INFO | Kein Crash-Guard (s.u.) |

## Edge Cases -- Detail-Analyse

### Fallback-Regex ist aggressiver als Haupt-Regex

Der Haupt-Regex (`_NEXUS_FILENAME_RE`) verlangt:
- Dateiendung `.zip`, `.rar` oder `.7z`
- Einen Timestamp mit 9-11 Stellen am Ende

Der Fallback-Regex (`r'-(\d{2,})-'`) matcht JEDE Zahl mit 2+ Stellen zwischen Bindestrichen,
unabhaengig von Dateiendung, Timestamp oder Dateistruktur.

**Bewertung:** Das ist **akzeptabel** fuer den Downloads-Tab-Kontext, da:
1. Die Fallback-Erkennung wird nur bei Nexus-kompatiblen Archiven aufgerufen
2. Der User bekommt einen Bestaetigungs-Dialog vorgeschlagen (Kriterium 5 der Spec)
3. Im schlimmsten Fall wird eine falsche ID vorgeschlagen, die der User ablehnen kann

**Severity: LOW** -- Kein Bug, aber zu beachten.

### None-Input wirft TypeError

`extract_nexus_mod_id(None)` wirft `TypeError: expected string or bytes-like object`.

**Bewertung:** Die Funktion hat Type-Hint `filename: str`, also ist None ein Programmierfehler
beim Aufrufer. Trotzdem waere ein Guard defensiver.

**Severity: LOW** -- Der Aufrufer-Code sollte sicherstellen, dass filename immer ein String ist.

## nexus_api.py Pruefung

### Aenderung gegenueber letztem Commit
- EINE Aenderung: Neue Methode `query_mod_info()` (Zeilen 120-125)
- Identisch mit Feature-Spec-Vorgabe
- Tag-Prefix `query_mod_info:` korrekt separiert von `mod_info:`
- Kein Kollisionsrisiko: `"query_mod_info:".startswith("mod_info:")` = False

### Routing in mainwindow.py
- Zeile 3120: `tag.startswith("mod_info:")` -- fuer NXM-Download-Flow
- Zeile 3125: `tag.startswith("query_mod_info:")` -- fuer Query-Info-Flow
- Reihenfolge korrekt: kein Prefix-Overlap

### query_mod_info() Methode
- Signatur: `query_mod_info(self, game: str, mod_id: int) -> None`
- Ruft intern `self._get()` auf mit Tag `f"query_mod_info:{game}:{mod_id}"`
- Verwendet denselben API-Endpunkt wie `get_mod_info()` (`/games/{game}/mods/{mod_id}.json`)
- Nur der Tag ist unterschiedlich -- korrekt, wie in der Spec beschrieben

## Befunde

### [LOW] Fallback-Regex matcht auch bei unerwarteten Dateiendungen
- Datei: `anvil/core/nexus_filename_parser.py:29`
- Problem: Fallback-Regex `r'-(\d{2,})-'` hat keine Endungs-Pruefung
- Auswirkung: .exe, .pdf etc. wuerden auch gematcht
- Bewertung: Im Downloads-Tab-Kontext irrelevant, da nur Archive vorliegen
- Fix (optional): Endungs-Pruefung auch im Fallback

### [LOW] Kein None-Guard in extract_nexus_mod_id
- Datei: `anvil/core/nexus_filename_parser.py:21`
- Problem: `None`-Input wirft TypeError statt None zurueckzugeben
- Auswirkung: Aufrufer muss sicherstellen, dass filename ein String ist
- Fix (optional): `if not filename: return None` am Anfang

## Bewertung

**PASS**

Beide Akzeptanzkriterien (14 und 15) sind erfuellt:
- Kriterium 14: `extract_nexus_mod_id("Peachu Casual Dress - Archive XL-14817-1-1716336327.rar")` gibt korrekt 14817 zurueck -- VERIFIZIERT durch echten Python-Test
- Kriterium 15: `extract_nexus_mod_id("random_mod_without_id.zip")` gibt korrekt None zurueck -- VERIFIZIERT durch echten Python-Test

Alle 5 Dateinamen-Muster aus der Feature-Spec werden korrekt erkannt. Die Regex-Logik (Haupt-Regex + Fallback) ist MO2-kompatibel. Die `query_mod_info()`-Methode in `nexus_api.py` ist korrekt implementiert mit separatem Tag-Prefix.

Die zwei LOW-Findings sind keine Blocker und betreffen defensives Coding.

**Ergebnis: 2/2 Punkte erfuellt**
