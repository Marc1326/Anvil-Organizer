# Claude Review 1 — Issue #63: Akzeptanz-Checkliste

## Phase 1: BaseGame automatisiert Proton-Pfade

- [x] Bestehende Plugins mit eigenem Override: Verhalten identisch
  → Cyberpunk, Fallout 4, Starfield, BG3, Witcher 3, RDR2 alle ueberschreiben die Methoden → MRO gewinnt
- [x] Neues Plugin mit nur `_WIN_DOCUMENTS` gesetzt: Pfad wird automatisch aufgeloest
  → Getestet: TestGame-Klasse mit _WIN_DOCUMENTS → Default-Implementierung greift
- [x] Neues Plugin ohne `_WIN_DOCUMENTS`: gibt `None` zurueck
  → Getestet: BaseGame() ohne Attribute → None
- [x] App startet ohne Fehler

## Phase 2: Framework-Definitionen aus JSON

- [x] Cyberpunk-Plugin (nur Python-Defs, keine JSON): Frameworks identisch wie bisher
  → Getestet: get=10, all=10 (keine JSON vorhanden)
- [x] Neues Plugin mit NUR JSON-Datei: Frameworks werden geladen
  → Getestet: TestJsonGame mit JSON → 1 Framework geladen
- [x] Plugin mit Python + JSON: Python gewinnt bei Namenskonflikt, JSON ergaenzt
  → Getestet: SharedFW (Python gewinnt), ExtraFW (JSON ergaenzt)
- [x] Fehlerhafte JSON: Warning auf stderr, Plugin laedt trotzdem (graceful)
  → Getestet: "INVALID JSON" → stderr Warning, leere Liste
- [x] `is_framework_mod()` erkennt Frameworks aus JSON
  → Getestet: DetectMe aus JSON → erkannt
- [x] `get_installed_frameworks()` zeigt JSON-Frameworks an
  → Intern umgestellt auf `all_framework_mods()` → zeigt alle
- [x] App startet ohne Fehler mit allen bestehenden Plugins

## Phase 3: WIP-Plugins aktivieren

- [x] WIP-Plugins werden beim Start geladen
  → 14 Plugins total (6 + 8)
- [x] WIP-Plugins mit installiertem Spiel erscheinen in der Spieleliste
  → Skyrim SE erkannt (SteamID 489830 vorhanden)
- [x] WIP-Plugins sind als "[Beta]" markiert
  → instance_wizard.py, settings_dialog.py (2 Stellen) angepasst
- [x] Bestehende Plugins: `Tested = True` (Default), kein "[Beta]"
  → Alle 6 bestehenden Plugins: Tested=True
- [x] App startet ohne Fehler

## Phase 4: Bessere User-Plugin-Dokumentation

- [x] README enthaelt vollstaendige Attribut-Referenz (Pflicht + Optional)
- [x] Steam-ID/GOG-ID/Epic-ID Erklaerung vorhanden
- [x] JSON-Framework-Beispiel vorhanden
- [x] Tested-Attribut dokumentiert
- [x] _WIN_DOCUMENTS/_WIN_SAVES dokumentiert

## Ergebnis

**ACCEPTED** — Alle Akzeptanz-Kriterien erfuellt.
