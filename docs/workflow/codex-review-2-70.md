# Codex Review 2 — Issue #70 (Collection Export/Import)
Datum: 2026-03-26
Reviewer: Codex-Agent 2 (Issue-Verifikation + Edge Cases)

## Pruefumfang
Verifikation dass Issue #70 vollstaendig geloest ist. Edge-Case-Analyse.

## Issue #70 Anforderung
"Collection/Modpack Export+Import — Mod-Setups als .anvilpack exportieren und importieren."

### Kern-Anforderungen aus dem Issue:
1. Export modlist.txt/meta.ini/Aktivierungsstatus/Separator-Struktur als JSON/ZIP
2. Import stellt Struktur wieder her (Mods werden separat heruntergeladen)
3. Format enthaelt Nexus-Mod-IDs
4. Keine Game-Plugin Aenderungen

## Verifikation

| Anforderung | Status | Beleg |
|-------------|--------|-------|
| modlist.txt Reihenfolge exportiert | OK | build_manifest liest read_global_modlist und iteriert in Reihenfolge |
| meta.ini Daten exportiert | OK | read_meta_ini pro Mod: modid, version, author, url, category, name |
| Aktivierungsstatus exportiert | OK | `enabled=name in active_mods` (Zeile 217) |
| Separator-Struktur exportiert | OK | `is_separator=is_sep` + color aus meta.ini |
| JSON/ZIP Format | OK | .anvilpack = ZIP mit manifest.json |
| Import stellt Reihenfolge her | OK | apply_collection iteriert manifest.mods in Reihenfolge |
| Import erstellt Separatoren | OK | apply_collection:403-418 erstellt fehlende Separator-Ordner |
| Fehlende Mods angezeigt | OK | Import-Dialog zeigt missing Mods mit Nexus-Links |
| Nexus-Mod-IDs enthalten | OK | CollectionMod.nexus_id + URL-Generierung |
| Keine Game-Plugin Aenderungen | OK | Kein Plugin-Code geaendert |

## Edge-Case-Analyse

### 1. Leere Instanz (keine Mods)
- Export: build_manifest mit leerer mod_order -> leere mods-Liste -> gueltig
- Import: apply_collection mit leerer manifest.mods -> keine Aenderungen -> korrekt

### 2. Mods mit Sonderzeichen im Namen
- Werden als String in JSON gespeichert -> `ensure_ascii=False` korrekt
- Ordner-Namen bleiben unveraendert -> kein Problem

### 3. Mehrere Kategorien pro Mod
- `category_ids` ist eine Liste -> korrekt serialisiert/deserialisiert
- Komma-separiert in meta.ini: `",".join(str(cid) for cid in mod.category_ids)` -> korrekt

### 4. Mod ohne meta.ini
- `read_meta_ini` liefert leeres dict -> alle Felder bekommen Defaults -> korrekt

### 5. Korrupte .anvilpack Datei
- BadZipFile wird gefangen in mainwindow.py:3121
- Fehlerhaftes JSON wird gefangen in collection_io.py:294
- Fehlendes manifest.json wird gefangen in collection_io.py:288-289

### 6. Doppelter Import derselben Collection
- apply_collection ueberschreibt global modlist und active_mods
- Mods die schon in der Collection stehen werden nicht dupliziert
- Mods auf Disk aber nicht in Collection werden am Ende angehaengt
- Idempotent -> korrekt

### 7. Import mit game_mismatch
- Dialog erkennt Mismatch, deaktiviert Import-Button
- Vergleich case-insensitive (.lower()) -> korrekt

### 8. Collection mit categories.json
- Optional eingebettet beim Export (wenn Datei existiert)
- Optional gelesen beim Import (apply_categories Checkbox)
- Wenn nicht vorhanden: cats_data = None -> categories nicht ueberschrieben

### 9. Separator ohne Color
- `sep_color = meta.get("color", "")` -> leerer String -> kein Problem
- CollectionMod.color = "" -> wird nicht in meta.ini geschrieben (Zeile 413: `if mod.color:`)

### 10. Kein aktives Profil/Instanz
- Beide Methoden pruefen `if not self._current_instance_path or not self._current_profile_path: return`

## Keine Findings

## Ergebnis: ACCEPTED

Issue #70 ist vollstaendig geloest. Alle Edge Cases sind korrekt behandelt.
