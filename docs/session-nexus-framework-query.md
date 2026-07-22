# Anvil Organizer — Session 2026-03-30

## Zusammenfassung

Heute wurde das Nexus-Mods-API-Query-System um zwei neue Funktionen erweitert: Batch-Abfrage für die gesamte Mod-Liste per Kontextmenü sowie eine vollständig eigenständige Nexus-Abfrage für Frameworks mit eigenem Lifecycle. Abgeschlossen wurde die Session mit drei Bugfixes, die UI-Refresh, i18n-Key und fehlende Variablen-Initialisierung behoben haben.

## Commits

| Hash | Message |
|------|---------|
| `7bfaba5` | feat: batch Nexus query with submenu, toast notifications, and name normalization |
| `e61e036` | feat: add nexus_id to FrameworkMod for batch Nexus queries |
| `8caf700` | feat: separate framework Nexus query with header button and context menu |
| `7bfc586` | fix: framework Nexus query — UI refresh, proper init, correct i18n key |

## Gelöste Bugs / Neue Features

| Was | Status |
|-----|--------|
| Batch Nexus Query via Kontextmenü (Einzeln + Alle) | Neu |
| Toast-Benachrichtigungen bei Batch-Start/-Ende | Neu |
| Archiv-Namen-Matching normalisiert (Leerzeichen, Unterstriche, Sonderzeichen) | Fix |
| `nexus_id`-Feld in FrameworkMod Dataclass | Neu |
| 35 Frameworks in 13 Game-Plugins mit Nexus-IDs versehen | Neu |
| `framework_cache.json` Speicherung pro Instanz | Neu |
| Eigenstandiger Framework Query Lifecycle (getrennt von Mod-Batch) | Neu |
| "Nexus prüfen" Button in Framework-Header-Bar | Neu |
| "Nexus-Info abrufen" im Framework-Rechtsklick-Kontextmenü | Neu |
| CollapsibleSectionBar von QLabel auf QWidget refactored | Refactor |
| KRITISCH: UI nach Framework-Query nicht aktualisiert (`_reload_mod_list()` fehlte) | Fix |
| MITTEL: Falscher i18n-Key bei Rate-Limit (`fw.query_rate_limit_wait` korrigiert) | Fix |
| MITTEL: Framework-Query-Variablen nicht in `__init__()` initialisiert | Fix |
| Alle 7 Locale-Dateien aktualisiert (de, en, es, fr, it, pt, ru) | Neu |

## QA Ergebnis

Kein formaler QA-Report vorhanden. Die 3 Bugs aus Commit `7bfc586` wurden intern identifiziert und direkt behoben:
- 1 kritischer Bug (kein UI-Refresh nach Query)
- 2 mittlere Bugs (falscher i18n-Key, fehlende Variable-Initialisierung)

## Offene Punkte

- [ ] `framework_cache.json` wird gespeichert, aber nirgends gelesen — Daten haben keinen Effekt
- [ ] Kein UI für manuelles Eintragen von Framework Nexus-IDs
- [ ] MD5-Fallback für Nexus-ID-Auflösung noch nicht implementiert

## Nächste Schritte

1. `framework_cache.json` beim Start lesen und gecachte Nexus-Daten in Framework-Anzeige einbinden
2. UI-Element zum manuellen Setzen einer Nexus-ID pro Framework einbauen (z.B. im Framework-Kontextmenü)
3. MD5-Fallback implementieren: Mod-Archiv per MD5-Hash gegen Nexus-API auflösen wenn Namens-Matching fehlschlägt
