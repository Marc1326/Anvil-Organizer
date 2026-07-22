# QA Report — DnD + Modlist Fix (Konsolidiert)
Datum: 2026-03-14

## Gesamtbewertung: NEEDS FIXES

Agent 3 hat DENIED — daher kann kein READY FOR COMMIT vergeben werden.

---

## Agent-Ergebnisse

### Agent 1 — Multi-Mod DnD Fix in _install_archives(): ACCEPTED
- `_prev_inserted_name`-Tracking im Global-Modlist-Pfad ist korrekt
- Alle Edge Cases geprueft (0/1/5/50 Mods, Framework-continue, FOMOD-Abbruch, Duplikate)
- Ein MEDIUM-Finding im Legacy-Pfad (alter `insert_at += 1` Bug)

### Agent 2 — Mod-Loeschung Fix (remove_mod_from_global_modlist): ACCEPTED
- Neue Funktion `remove_mod_from_global_modlist()` ist korrekt implementiert
- Import, Aufruf-Reihenfolge und Edge Cases (Separator, Sonderzeichen, Multi-Select) OK
- Drei LOW-Findings (verwaiste active_mods.json-Eintraege, ungenutzter Import, Ineffizienz)

### Agent 3 — Index-Mismatch Source-Model vs. _current_mod_entries: DENIED
- **15 CRITICAL Findings**: Systematischer Architektur-Fehler
- Source-Model-Row-Indices werden als Index in `_current_mod_entries` verwendet
- `_current_mod_entries` enthaelt DirectInstall-Mods, Source-Model nicht
- Aktuell nur durch Zufall nicht sichtbar (DirectInstall am Listenende)
- Bei anderer Reihenfolge: falsche Mods werden umbenannt, geloescht, gebackupt etc.

---

## Alle Findings nach Severity

### CRITICAL (15 Findings — alle aus Agent 3)

| # | Stelle | Problem |
|---|--------|---------|
| 1 | mainwindow.py:1641-1642 | _on_mod_context_menu: falscher Mod im Kontext-Menu |
| 2 | mainwindow.py:1686 | Kontext-Menu: falscher Mod adressiert |
| 3 | mainwindow.py:1844, 1856 | Kontext-Menu: Nexus-Link/Separator auf falschen Mod |
| 4 | mainwindow.py:1963, 2004 | Separator-Farbe auf falschen Separator |
| 5 | mainwindow.py:2576-2582 | _ctx_enable_selected: falscher Mod aktiviert/deaktiviert |
| 6 | mainwindow.py:2594 | _ctx_enable_all: IndexError wenn DirectInstall nicht am Ende |
| 7 | mainwindow.py:2637 | _apply_category_changes: Kategorie am falschen Mod |
| 8 | mainwindow.py:2692 | _toggle_category: meta.ini fuer falschen Mod geschrieben |
| 9 | mainwindow.py:2741 | _set_primary_category: Primary Category am falschen Mod |
| 10 | mainwindow.py:2781 | _ctx_create_backup: falscher Mod wird gebackupt |
| 11 | mainwindow.py:2817 | _ctx_query_nexus_info: Nexus-Abfrage fuer falschen Mod |
| 12 | mainwindow.py:2949 | _ctx_visit_nexus: falsche Nexus-Seite geoeffnet |
| 13 | mainwindow.py:2967 | _ctx_rename_mod: falscher Mod umbenannt (Dateisystem!) |
| 14 | mainwindow.py:3006 | _ctx_reinstall_mod: Archiv-Suche mit falschem Namen |
| 15 | mainwindow.py:3041 | _ctx_remove_mods: **DATENVERLUST** — falscher Mod geloescht |

**Root Cause:** `_current_mod_entries` enthaelt DirectInstall-Mods, das Source-Model nicht. Bei Indexzugriff `_current_mod_entries[source_row]` wird der falsche Eintrag adressiert, sobald DirectInstall-Mods nicht am Ende der Liste stehen.

**Empfohlener Fix (Agent 3):** Name-Lookup statt Index-Zugriff (Option A), wie bereits in `_on_mod_toggled()` und `_on_mods_reordered()` korrekt umgesetzt:
```python
model = self._mod_list_view.source_model()
folder_name = model._rows[row].folder_name
entry = next(e for e in self._current_mod_entries if e.name == folder_name)
```

### MEDIUM (1 Finding — Agent 1)

| # | Stelle | Problem |
|---|--------|---------|
| 1 | mainwindow.py:1445 | Legacy-Pfad nutzt noch `insert_at += 1` statt `_prev_inserted_name`-Tracking. Bei Duplikat-Erkennung in `insert_mod_in_modlist()` verschiebt sich `insert_at` falsch. Geringe reale Auswirkung da Legacy-Pfad selten genutzt. |

### LOW (3 Findings — Agent 2)

| # | Stelle | Problem |
|---|--------|---------|
| 1 | mainwindow.py:3058-3068 | active_mods.json wird bei Mod-Loeschung nicht explizit bereinigt (heilt sich selbst) |
| 2 | mainwindow.py:55 | `remove_mod_from_modlist` importiert aber ungenutzt (toter Import) |
| 3 | mainwindow.py:3059-3064 | Multi-Loeschung: 50 Mods = 50x Datei lesen/schreiben (ineffizient, aber korrekt) |

---

## Issues die vor Release gefixt werden MUESSEN (CRITICAL + HIGH)

1. **Index-Mismatch an 15+ Stellen fixen** — ueberall wo `_current_mod_entries[source_row]` steht, muss ein Name-Lookup eingefuehrt werden. Betrifft mindestens:
   - `_on_mod_context_menu()`
   - `_ctx_enable_selected()`
   - `_ctx_enable_all()`
   - `_apply_category_changes()`
   - `_toggle_category()`
   - `_set_primary_category()`
   - `_ctx_create_backup()`
   - `_ctx_query_nexus_info()`
   - `_ctx_visit_nexus()`
   - `_ctx_rename_mod()`
   - `_ctx_reinstall_mod()`
   - `_ctx_remove_mods()`
   - `_ctx_open_explorer()`
   - `_ctx_show_info()`
   - `_ctx_select_separator_color()` / `_ctx_reset_separator_color()`

**Hinweis:** Dieser Bug ist aktuell nur latent (DirectInstall-Mods stehen am Ende). Er wird aber zum aktiven Bug sobald ein Game-Plugin DirectInstall-Mods hat die alphabetisch nicht am Ende sortieren, oder wenn die modlist.txt manuell bearbeitet wird.

---

## Optionale Verbesserungen (MEDIUM + LOW)

1. Legacy-Pfad auf `_prev_inserted_name`-Tracking umstellen (MEDIUM)
2. active_mods.json bei Mod-Loeschung explizit bereinigen (LOW)
3. Ungenutzten Import `remove_mod_from_modlist` entfernen (LOW)
4. Multi-Loeschung: Batch-Operation statt einzelne Datei-Lese/Schreibvorgaenge (LOW)

---

## Checklisten-Pruefung

### Checkliste: DnD Download-Tab Position Fix (9 Kriterien)

- [x] 1: Source-Model-Index wird in modlist.txt-Index umgerechnet (via `_prev_inserted_name` + Name-Lookup) ✅
- [x] 2: Umrechnung beruecksichtigt DirectInstall-Ausschluss ✅
- [x] 3: Neuer Mod wird relativ zum Referenz-Mod eingefuegt ✅
- [x] 4: Multi-DnD: alle Mods landen korrekt hintereinander ✅
- [x] 5: Fix nur in `_install_archives()` ✅
- [x] 6: `_apply_separator_filter()` unveraendert ✅
- [x] 7: Ohne DnD (insert_at=None) wird append verwendet ✅
- [x] 8: Fallback wenn Referenz-Mod nicht gefunden ✅
- [ ] 9: `./restart.sh` startet ohne Fehler — ZU PRUEFEN (kein App-Test durch QA-Agents durchgefuehrt)

**Ergebnis: 8/9 Punkte erfuellt** (1 nicht geprueft)

### Checkliste: Modlist Bug-Fixes (13 Kriterien)

Nicht vollstaendig pruefbar ohne App-Test. Die Code-Analyse durch die Agents deckt die logische Korrektheit ab, aber K1-K5, K13 erfordern manuelle Tests.

---

## Ergebnis

**NEEDS FIXES**

Der DnD-Fix selbst (`_prev_inserted_name`-Tracking) und der Mod-Loeschungs-Fix (`remove_mod_from_global_modlist`) sind korrekt implementiert. Jedoch hat Agent 3 einen systematischen Index-Mismatch-Bug an 15+ Stellen identifiziert, der bei bestimmten Konstellationen zu Datenverlust fuehren kann (falscher Mod wird geloescht/umbenannt). Dieser CRITICAL-Befund verhindert ein READY FOR COMMIT.

**Naechster Schritt:** Index-Mismatch an allen betroffenen Stellen durch Name-Lookup ersetzen (siehe Agent 3, Option A).
