# QA Agent 1 — plugins_txt_writer.py Review

Datum: 2026-03-01
Reviewer: QA Agent 1 (Bugs, Symlinks, Edge Cases)

## Geprufte Datei

`anvil/core/plugins_txt_writer.py` (175 Zeilen)
Klasse: `PluginsTxtWriter`
Methoden: `__init__`, `_remove_case_variants`, `scan_plugins`, `write`, `remove`

---

## Methode: scan_plugins() (Zeilen 68-122)

### Symlink-Handling

**Befund: KEIN BUG — Symlinks werden korrekt erkannt.**

`scan_plugins()` verwendet `os.scandir()` mit `entry.is_file()` (Zeile 85). Die Python-Dokumentation bestaetigt:

> `DirEntry.is_file(*, follow_symlinks=True)` — Default folgt Symlinks.

Das bedeutet:
- **Gueltige Symlinks** (z.B. deployed `.esp` -> `.mods/mod/plugin.esp`): `is_file()` gibt `True` zurueck. **KORREKT.**
- **Broken Symlinks** (Ziel geloescht/verschoben): `is_file()` gibt `False` zurueck. **KORREKT** — broken Symlinks werden still ignoriert.
- **Symlinks auf Verzeichnisse**: `is_file()` gibt `False` zurueck. **KORREKT.**

Verifiziert durch Python-Tests:
```python
# Gueltiger Symlink
entry.is_file()  # -> True (follow_symlinks=True default)

# Broken Symlink
entry.is_file()  # -> False (Ziel existiert nicht)
```

**Kontext:** Der `ModDeployer` (mod_deployer.py:36-37) deployed `.esp`, `.esm`, `.esl` Dateien IMMER als Symlinks in das Data/-Verzeichnis:
```python
_BA2_SYMLINK_EXTENSIONS = {".esp", ".esm", ".esl", ...}
```
Daher ist es absolut kritisch, dass `scan_plugins()` Symlinks korrekt als Dateien erkennt — und das tut es.

**`follow_symlinks` wird nicht explizit gesetzt**, aber der Default `True` ist hier das gewuenschte Verhalten. Ein explizites `entry.is_file(follow_symlinks=True)` waere zwar dokumentierend, aber funktional identisch.

---

### Edge Cases

#### 1. Leeres Data/-Verzeichnis
**Befund: KEIN BUG — korrekt behandelt.**

Zeile 94-96: Wenn `found` leer ist, wird eine Log-Meldung ausgegeben und `[]` zurueckgegeben.
```python
if not found:
    print(f"{_TAG} No plugin files found in {data_dir}")
    return []
```

#### 2. Data/-Verzeichnis existiert nicht
**Befund: KEIN BUG — korrekt behandelt.**

Zeile 77-79: `data_dir.is_dir()` prueft Existenz. Log-Meldung und `[]` bei Fehlen.

#### 3. Nur Symlinks im Data/-Verzeichnis
**Befund: KEIN BUG.** Symlinks werden wie oben beschrieben korrekt als Dateien erkannt.

#### 4. Gemischte reale + Symlink-Dateien
**Befund: KEIN BUG.** Beide werden gleichermassen von `is_file()` erkannt. Keine Unterscheidung noetig.

#### 5. Nur Broken Symlinks im Data/-Verzeichnis
**Befund: KEIN BUG.** Broken Symlinks werden von `is_file()` als `False` erkannt und uebersprungen. Das `found`-Set bleibt leer, Zeile 94-96 greift. Funktional korrekt.

#### 6. OSError beim Scannen
**Befund: KEIN BUG.** Zeile 90-92: `OSError` wird gefangen, Log-Meldung, `[]` zurueck.

#### 7. Case-Kollision bei Dateinamen (MEDIUM)
**Befund: POTENTIELLER DATENVERLUST — aber nur in Theorie.**

Zeile 100:
```python
found_lower_map = {f.lower(): f for f in found}
```

Wenn im Data/-Verzeichnis zwei Dateien mit gleichem Namen in unterschiedlicher Gross-/Kleinschreibung existieren (z.B. `MyMod.esp` UND `mymod.esp`), geht eine der beiden im `found_lower_map` Dictionary verloren. Nur die zuletzt iterierte wird behalten.

**Praktische Relevanz:** GERING. Auf einem Linux-Dateisystem koennen solche Duplikate existieren, aber:
- Bethesda-Spiele (Windows-nativ) sind case-insensitive
- Proton emuliert Case-Insensitivitaet
- Das waere ein Mod-Installations-Fehler, kein Anvil-Bug
- MO2 behandelt diesen Fall auch nicht explizit

**Empfehlung:** OPTIONAL — Ein Warning-Log bei Kollision waere hilfreich fuer Debugging:
```python
if f.lower() in found_lower_map:
    print(f"{_TAG} WARNING: case-variant collision: {f} vs {found_lower_map[f.lower()]}")
```

#### 8. `_primary` ist None statt leerer Liste
**Befund: KEIN BUG.** Zeile 36 verwendet `getattr(game_plugin, "PRIMARY_PLUGINS", [])` mit Fallback `[]`. Sicher.

---

## Methode: write() (Zeilen 124-158)

### [LOW] Kein BOM (Byte Order Mark) geschrieben

Zeile 153:
```python
txt_path.write_text("".join(lines), encoding="utf-8")
```

Die Datei wird als UTF-8 OHNE BOM geschrieben. Aeltere Bethesda-Spiele (Skyrim LE) erwarteten UTF-8 mit BOM (`utf-8-sig`).

**Verifizierung:** Die aktuell auf dem System existierende `plugins.txt` (von Anvil geschrieben) hat KEIN BOM und wird von Fallout 4 via Proton korrekt gelesen (bestaetigt durch Hex-Dump). Fallout 4 akzeptiert UTF-8 ohne BOM.

**Empfehlung:** Kein Fix noetig fuer Fallout 4. Wenn zukuenftig Skyrim-Support hinzukommt, sollte BOM konfigurierbar sein.

### [OK] CRLF Line Endings

Die `_HEADER` Konstante und die Plugin-Zeilen verwenden `\r\n`. `write_text()` auf Linux konvertiert dies NICHT — die Bytes `0d 0a` werden korrekt geschrieben. Verifiziert durch Hex-Dump der existierenden Datei.

### [OK] Parent-Directory Erstellung

Zeile 141: `os.makedirs(txt_path.parent, exist_ok=True)` — korrekt, erstellt fehlende Verzeichnisse.

### [OK] Error Handling

Zeile 156-158: `OSError` wird gefangen, `None` zurueckgegeben.

---

## Methode: _remove_case_variants() (Zeilen 40-64)

### [OK] Korrekte Implementierung

Die Methode entfernt Case-Varianten (z.B. `Plugins.txt` wenn Anvil `plugins.txt` schreiben will). Wichtig fuer Linux, wo beides koexistieren kann.

- `os.scandir` statt `iterdir()` — performanter
- Doppelter try/except — robust gegen Permission-Fehler
- `entry.name != txt_path.name` — der eigene Zielname wird NICHT geloescht
- `entry.is_file()` — Verzeichnisse mit aehnlichem Namen werden ignoriert

### [LOW] Stilles Verschlucken von OSError beim Loeschen

Zeile 61-62:
```python
except OSError:
    pass
```

Wenn eine Case-Variante nicht geloescht werden kann (z.B. Permission denied), wird der Fehler still verschluckt. Ein Warning-Log waere hilfreicher.

---

## Methode: remove() (Zeilen 160-174)

### [OK] Korrekte Implementierung

- Ruft `_remove_case_variants()` VOR dem eigenen `unlink()` auf
- `txt_path.exists()` prueft ob die Datei ueberhaupt existiert
- Error Handling vorhanden
- Gibt `True` zurueck wenn Datei bereits abwesend ist

---

## Weitere Findings

### [LOW] Logging ueber print() statt logging-Modul

Die gesamte Datei verwendet `print()` fuer Log-Ausgaben. Das ist konsistent mit dem Rest der Codebase (Anvil verwendet kein `logging`-Modul), aber erschwert spaetere Log-Level-Filterung.

### [OK] Keine hardcoded Pfade

Alle Pfade werden aus `game_plugin` und den uebergebenen `Path`-Objekten abgeleitet.

### [OK] Keine fehlenden Imports

`os`, `Path` aus `pathlib` — beide werden verwendet und sind korrekt importiert.

### [OK] Typisierung

Rueckgabetypen sind annotiert (`list[str]`, `Path | None`, `bool`). `__future__.annotations` ist importiert.

---

## Zusammenfassung der Findings

| # | Severity | Beschreibung | Zeile | Status |
|---|----------|-------------|-------|--------|
| 1 | OK | Symlink-Handling via is_file() | 85 | Korrekt — Default follow_symlinks=True |
| 2 | OK | Broken Symlinks werden ignoriert | 85 | Korrekt — is_file() gibt False |
| 3 | OK | Leeres Data/ | 94-96 | Korrekt behandelt |
| 4 | OK | Fehlendes Data/ | 77-79 | Korrekt behandelt |
| 5 | MEDIUM | Case-Kollision in found_lower_map | 100 | Theoretischer Datenverlust, praktisch irrelevant |
| 6 | LOW | Kein BOM fuer plugins.txt | 153 | Korrekt fuer Fallout 4, ggf. Problem fuer Skyrim |
| 7 | LOW | Stille OSError in _remove_case_variants | 61-62 | Warning-Log empfohlen |
| 8 | LOW | print() statt logging-Modul | div. | Konsistent mit Codebase |

---

## Fazit

**KEINE CRITICAL oder HIGH Findings.**

Die `scan_plugins()`-Methode behandelt Symlinks korrekt. Python's `os.DirEntry.is_file()` folgt standardmaessig Symlinks (`follow_symlinks=True`), was genau dem gewuenschten Verhalten entspricht: deployed Mod-Plugins (als Symlinks) werden als regulaere Dateien erkannt.

Die einzige nennenswerte Schwaeche ist die theoretische Case-Kollision (Finding #5), die in der Praxis aber nicht auftreten sollte, da Bethesda-Spiele case-insensitiv arbeiten und Proton dies emuliert.

**Gesamtbewertung: SOLIDE IMPLEMENTIERUNG — keine Blocker.**
