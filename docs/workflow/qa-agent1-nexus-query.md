# QA Agent 1 — API & Netzwerk Review: Nexus-Info abrufen
Datum: 2026-03-02

## Scope
Pruefung von `anvil/core/nexus_api.py` (neue Methode `query_mod_info()`) sowie aller 17 Akzeptanzkriterien aus der Feature-Spec, soweit sie die API- und Netzwerk-Domaene betreffen.

---

## Checklisten-Pruefung (17 Akzeptanzkriterien)

### Kriterium 1: Kontextmenue "Nexus-Info abrufen" klickbar bei nexus_id > 0
- [x] PASS
- Beleg: `anvil/mainwindow.py:1759-1760` — `act_nexus_query = menu.addAction(tr("context.nexus_query"))` mit `setEnabled(single and self._nexus_api.has_api_key())`. Korrekt: Die Action ist bei jeder einzelnen Mod-Selektion klickbar, unabhaengig von der nexus_id (solange API-Key vorhanden).

### Kriterium 2: Kontextmenue "Nexus-Info abrufen" klickbar bei nexus_id = 0
- [x] PASS
- Beleg: `anvil/mainwindow.py:1760` — `setEnabled(single and self._nexus_api.has_api_key())`. Der `nexus_id`-Wert wird NICHT geprueft fuer das Enable/Disable. Damit ist der Menueeintrag auch bei nexus_id = 0 klickbar. Dies ist korrekt gemaess Spec.

### Kriterium 3: API-Aufruf mit Tag-Prefix `query_mod_info:` (NICHT `mod_info:`), Statusbar "Lade Nexus-Info..."
- [x] PASS
- Beleg API: `anvil/core/nexus_api.py:120-125` — `query_mod_info()` verwendet `tag=f"query_mod_info:{game}:{mod_id}"`. KORREKT separater Prefix.
- Beleg Statusbar: `anvil/mainwindow.py:2731` — `self.statusBar().showMessage(tr("status.nexus_query_loading"), 5000)`.

### Kriterium 4: Eingabe-Dialog bei nexus_id = 0
- [x] PASS
- Beleg: `anvil/mainwindow.py:2704-2708` — Wenn `nexus_id == 0`, wird `get_text_input()` mit `tr("dialog.nexus_query_title")` und `tr("dialog.nexus_query_prompt")` aufgerufen.

### Kriterium 5: Gueltige Zahl -> API-Call mit eingegebener ID
- [x] PASS
- Beleg: `anvil/mainwindow.py:2711-2717` — `nexus_id = int(text.strip())`, Pruefung auf `> 0`, dann weiter zu `query_mod_info()` in Zeile 2730.

### Kriterium 6: Ungueltige Eingabe -> KEIN API-Call + Statusbar-Fehler
- [x] PASS
- Beleg: `anvil/mainwindow.py:2709-2717` — Leerer String: `if not ok or not text.strip(): return`. Buchstaben/negativ/0: `ValueError`-Handler mit `return` nach Statusbar-Meldung `tr("status.nexus_query_invalid_id")`.

### Kriterium 7: Erfolg -> meta.ini Update via write_meta_ini
- [x] PASS
- Beleg: `anvil/mainwindow.py:3049-3064` — `write_meta_ini(path, {...})` mit allen geforderten Feldern: modid, version, newestVersion, name, author, description (aus `summary`), url.
- Alle Felder korrekt gemaess Spec: `data.get("summary", "")` fuer description (wie MO2).

### Kriterium 8: Erfolg -> Mod-Liste reload + Statusbar-Meldung
- [x] PASS
- Beleg: `anvil/mainwindow.py:3065-3068` — `self._reload_mod_list()` gefolgt von `self.statusBar().showMessage(tr("status.nexus_query_success", name=data.get("name", "")), 5000)`.

### Kriterium 9: Nach Erfolg -> "Nexus-Seite oeffnen" aktiviert
- NICHT IN MEINER DOMAENE (UI-Logik, wird von Agent 2 geprueft)
- Hinweis: Die Logik in `_on_nexus_response()` schreibt `modid` in die meta.ini, und `_reload_mod_list()` laedt die Entries neu. Ob `visit_nexus` dann enabled ist, haengt davon ab, ob `nexus_id` aus der meta.ini korrekt in den ModEntry uebernommen wird — das ist UI/Model-Logik.

### Kriterium 10: Kein API-Key -> Kontextmenue ausgegraut
- [x] PASS
- Beleg: `anvil/mainwindow.py:1760` — `act_nexus_query.setEnabled(single and self._nexus_api.has_api_key())`. Ohne API-Key gibt `has_api_key()` False zurueck.
- Zusaetzliche Absicherung: `anvil/core/nexus_api.py:163-165` — `_get()` prueft `if not self._api_key:` und emittiert `request_error` statt HTTP-Request.

### Kriterium 11: API-Fehler (404, 429, Timeout) -> Statusbar-Fehler, meta.ini unveraendert
- [x] PASS
- Beleg Error-Routing: `anvil/core/nexus_api.py:211-218` — HTTP 429 ("Rate Limit erreicht"), 401 ("Ungueltiger API-Schluessel"), >= 400 ("HTTP {status}") emittieren alle `request_error`.
- Beleg Timeout: `anvil/core/nexus_api.py:58-59` — `except Exception` faengt Timeouts (urllib hat `timeout=30` in Zeile 44).
- Beleg Statusbar: `anvil/mainwindow.py:3070-3072` — `_on_nexus_error()` zeigt `tr("status.nexus_error", message=message)`.
- meta.ini wird NUR bei Erfolg geschrieben (innerhalb des `tag.startswith("query_mod_info:")` Blocks in `_on_nexus_response`). Bei Fehler wird `_on_nexus_error` aufgerufen, nicht `_on_nexus_response`.

### Kriterium 12: GamePanel-Button bei genau 1 Selektion -> Query starten
- NICHT IN MEINER DOMAENE (Widget/Signal-Flow, wird von Agent 2 geprueft)
- Hinweis: Signal-Kette ist vorhanden: `nexus_query_requested` Signal -> `_on_nexus_query_from_panel()`.

### Kriterium 13: GamePanel-Button bei 0 Selektionen -> Statusbar-Meldung
- NICHT IN MEINER DOMAENE (Widget/Signal-Flow, wird von Agent 2 geprueft)
- Hinweis: `_on_nexus_query_from_panel()` prueft `len(selected_rows) != 1` und zeigt `tr("dialog.no_selection")`.

### Kriterium 14: Row-Verschiebung -> install_path statt Row-Index
- [x] PASS
- Beleg: `anvil/mainwindow.py:265` — `self._pending_query_path: Path | None = None` als Instanzvariable.
- Beleg: `anvil/mainwindow.py:2719` — `self._pending_query_path = entry.install_path` wird VOR dem API-Call gesetzt.
- Beleg: `anvil/mainwindow.py:3045-3048` — Response liest `self._pending_query_path` und prueft `path.exists()`.
- KEIN Row-Index wird gespeichert. Korrekt gemaess Spec.

### Kriterium 15: NXM-Download + Query gleichzeitig -> getrennte Tag-Prefixes
- [x] PASS
- Beleg NXM-Flow: `anvil/core/nexus_api.py:118` — `get_mod_info()` verwendet `tag=f"mod_info:{game}:{mod_id}"`.
- Beleg Query-Flow: `anvil/core/nexus_api.py:124-125` — `query_mod_info()` verwendet `tag=f"query_mod_info:{game}:{mod_id}"`.
- Beleg Response-Routing: `anvil/mainwindow.py:3039` vs `3044` — Separate `elif`-Zweige: `tag.startswith("mod_info:")` vs `tag.startswith("query_mod_info:")`.
- KEINE Kollisionsgefahr: `query_mod_info:` beginnt NICHT mit `mod_info:`.
- Beleg: `"query_mod_info:".startswith("mod_info:")` ist `False` in Python. KORREKT.

### Kriterium 16: Alle 6 i18n-Keys in allen 6 Locale-Dateien
- [x] PASS
- 6 Keys geprueft in allen 6 Locales (de, en, es, fr, it, pt):
  - `context.nexus_query` — vorhanden in allen 6 Dateien (Zeile 98 jeweils)
  - `dialog.nexus_query_title` — vorhanden in allen 6 Dateien
  - `dialog.nexus_query_prompt` — vorhanden in allen 6 Dateien
  - `status.nexus_query_loading` — vorhanden in allen 6 Dateien (Zeile 442 jeweils)
  - `status.nexus_query_success` — vorhanden in allen 6 Dateien (Zeile 443 jeweils)
  - `status.nexus_query_invalid_id` — vorhanden in allen 6 Dateien (Zeile 444 jeweils)

### Kriterium 17: restart.sh startet ohne Fehler
- NICHT IN MEINER DOMAENE (Runtime-Test, wird von Agent 3 oder manuell geprueft)

---

## Zusaetzliche API-spezifische Pruefungen

### API-Endpunkt korrekt?
- [x] PASS — `anvil/core/nexus_api.py:124` — `/games/{game}/mods/{mod_id}.json` entspricht der Nexus v1 API-Spezifikation.

### `_get()` korrekt aufgerufen?
- [x] PASS — `query_mod_info()` ruft `self._get(path, tag=...)` auf, genau wie `get_mod_info()`. Headers (apikey, User-Agent) werden automatisch in `_get()` gesetzt.

### Worker-Lifecycle korrekt?
- [x] PASS — `anvil/core/nexus_api.py:174-180` — Worker wird in `self._workers` gespeichert (GC-Schutz), mit `parent=self` erzeugt, und nach Abschluss via `_cleanup_worker()` (Zeile 182-186) entfernt und `deleteLater()` aufgerufen.

### Rate-Limit-Tracking?
- [x] PASS — `anvil/core/nexus_api.py:195-208` — Rate-Limit-Headers werden aus jeder Response gelesen und via `rate_limit_updated` Signal emittiert.

---

## Findings

### [LOW] Keine Warnung bei fehlendem nexus_slug
- Datei: `anvil/mainwindow.py:2727-2728`
- Problem: Wenn `nexus_slug` leer ist (kein Plugin oder Plugin ohne `GameNexusName`/`GameShortName`), wird die Methode stumm mit `return` beendet. Der User erhaelt keine Rueckmeldung warum nichts passiert.
- Fix-Vorschlag: Statusbar-Meldung vor dem `return` hinzufuegen, z.B. "Nexus-Slug nicht verfuegbar fuer dieses Spiel".
- Severity: LOW — Tritt nur auf wenn ein Game-Plugin unvollstaendig konfiguriert ist.

### [LOW] _pending_query_path Race-Condition bei schnellen Doppelklicks
- Datei: `anvil/mainwindow.py:2719`, `anvil/mainwindow.py:3045`
- Problem: Wenn der User zwei Queries schnell hintereinander startet, wird `_pending_query_path` beim zweiten Aufruf ueberschrieben. Der erste Response wuerde dann die meta.ini der zweiten Mod updaten.
- Fix-Vorschlag: Den Pfad im Tag kodieren (z.B. `query_mod_info:{game}:{mod_id}:{path_hash}`) oder Query-Button waehrend laufender Query deaktivieren.
- Severity: LOW — Unwahrscheinliches User-Verhalten, da API-Antwort typischerweise < 1 Sekunde dauert.

---

## Zusammenfassung

| Kriterium | Status | Anmerkung |
|-----------|--------|-----------|
| 1  | PASS | Kontextmenue korrekt |
| 2  | PASS | Kontextmenue korrekt bei nexus_id=0 |
| 3  | PASS | Tag `query_mod_info:` korrekt |
| 4  | PASS | Eingabe-Dialog korrekt |
| 5  | PASS | Gueltige ID -> API-Call |
| 6  | PASS | Ungueltige ID -> kein API-Call |
| 7  | PASS | meta.ini Update korrekt |
| 8  | PASS | Reload + Statusbar korrekt |
| 9  | NICHT GEPRUEFT | UI-Domaene (Agent 2) |
| 10 | PASS | Kein Key -> ausgegraut |
| 11 | PASS | Fehlerbehandlung korrekt |
| 12 | NICHT GEPRUEFT | Widget-Domaene (Agent 2) |
| 13 | NICHT GEPRUEFT | Widget-Domaene (Agent 2) |
| 14 | PASS | install_path statt Row-Index |
| 15 | PASS | Getrennte Tag-Prefixes |
| 16 | PASS | Alle 6 Keys in 6 Locales |
| 17 | NICHT GEPRUEFT | Runtime-Test |

## Ergebnis: 13/13 gepruefte Punkte PASS (4 nicht in meiner Domaene)

Keine CRITICAL oder HIGH Findings. 2x LOW (stummes Return bei fehlendem Slug, theoretische Race-Condition).

Die API-Implementierung in `nexus_api.py` ist korrekt, sauber getrennt vom NXM-Download-Flow, und folgt den Vorgaben der Feature-Spec.
