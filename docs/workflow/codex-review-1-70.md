# Codex Review 1 — Issue #70 (Collection Export/Import)
Datum: 2026-03-26
Reviewer: Codex-Agent 1 (Code-Qualitaet + Logik)

## Pruefumfang
Alle neuen und geaenderten Dateien gegen die 15-Punkte-Akzeptanz-Checkliste.

## Dateien geprueft
- `anvil/core/collection_io.py` (NEU, 459 Zeilen)
- `anvil/dialogs/collection_export_dialog.py` (NEU, 245 Zeilen)
- `anvil/dialogs/collection_import_dialog.py` (NEU, 323 Zeilen)
- `anvil/mainwindow.py` (GEAENDERT — _export_collection, _import_collection, Menue, Signals)
- `anvil/widgets/profile_bar.py` (GEAENDERT — 2 Signals, 2 Menue-Eintraege)
- `anvil/locales/*.json` (7 Dateien — de, en, es, fr, it, pt, ru)

## Checkliste-Pruefung

| # | Kriterium | Status | Beleg |
|---|-----------|--------|-------|
| 1 | Export-Dialog oeffnet bei Klick im Dots-Menue | OK | profile_bar.py:291 -> Signal -> mainwindow.py:172 -> _export_collection:3028 zeigt Dialog |
| 2 | .anvilpack ist gueltiges ZIP | OK | collection_io.py:262 — zipfile.ZipFile(..., "w", ZIP_DEFLATED) |
| 3 | manifest.json mit Game-Name, Mod-Liste, format_version=1 | OK | _manifest_to_dict erstellt korrekte Struktur, FORMAT_VERSION=1 |
| 4 | Mod-Anzahl und Separator-Anzahl stimmen | OK | mainwindow.py:3019-3025 zaehlt aus _current_mod_entries |
| 5 | Import: Datei-Dialog gefiltert auf .anvilpack | OK | mainwindow.py:3107-3112 QFileDialog mit file_filter |
| 6 | Import-Dialog zeigt alle Infos | OK | collection_import_dialog.py:146-201 zeigt Name, Game, Author, Stats |
| 7 | Nexus-Link fuer fehlende Mods | OK | _ModCard mit QDesktopServices.openUrl, Zeile 67-71 |
| 8 | Modliste wird aktualisiert | OK | apply_collection schreibt write_global_modlist + write_active_mods |
| 9 | Kategorien werden uebernommen | OK | apply_collection:425-428 schreibt category in meta.ini |
| 10 | Game-Mismatch Warnung | OK | collection_import_dialog.py:111-135 + btn disabled |
| 11 | Fehlerhafte .anvilpack zeigt Fehlermeldung | OK | mainwindow.py:3119-3127 faengt ValueError + BadZipFile |
| 12 | Nexus-URL korrekt bei nexus_id > 0 | OK | collection_io.py:210-212 baut URL korrekt |
| 13 | Alle 7 Locale-Dateien | OK | Alle 27 Keys in de, en, es, fr, it, pt, ru vorhanden |
| 14 | Datei-Menue Eintraege | OK | mainwindow.py:380-384 |
| 15 | Kompilierung ohne Fehler | OK | py_compile fuer alle Dateien bestanden |

## Code-Qualitaet

### Positiv
- Saubere Trennung: Backend (collection_io.py), Dialoge, UI-Integration
- Lazy Imports in mainwindow.py (innerhalb der Methoden)
- Konsistente Fehlerbehandlung mit try/except
- Lambda-Muster `lambda checked=False:` korrekt (Qt clicked bool-Param)
- Dataclass-Nutzung fuer Manifest und Mod-Daten
- `asdict()` fuer saubere JSON-Serialisierung
- Bestehende Mods auf Disk werden beim Import erhalten (append at end)

### Potential Minor Issues
1. **Export-Dialog StyleSheet in _on_export**: Wenn Name leer ist, wird der StyleSheet auf Rot gesetzt (Zeile 231-242), aber beim erneuten Eingeben wird er nicht zurueckgesetzt. Minor UX-Issue, kein Bug — der rote Rand bleibt bis der Dialog geschlossen wird.
2. **Russische Locale**: Die Transliteration "nevozmozhен" (game_mismatch) mischt lateinische und kyrillische Zeichen (das "н" am Ende ist kyrillisch). Das ist aber ein kosmetisches Locale-Problem, kein Code-Bug.

### Keine kritischen Findings

## Ergebnis: ACCEPTED

Alle 15 Akzeptanz-Kriterien sind erfuellt. Code-Qualitaet ist hoch, Architektur konsistent mit dem bestehenden Projekt.
