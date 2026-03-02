# QA Agent 3 Report -- Nexus-Info abrufen (Daten & Persistenz)
Datum: 2026-03-02

## Checklisten-Pruefung (17 Kriterien)

### Kriterium 1: Kontextmenue "Nexus-Info abrufen" klickbar bei nexus_id > 0
- **Ergebnis:** PASS
- **Beleg:** `anvil/mainwindow.py:1759-1760` -- `act_nexus_query = menu.addAction(tr("context.nexus_query"))` mit `setEnabled(single and self._nexus_api.has_api_key())`. Der Menueeintrag ist bei jeder Mod klickbar (unabhaengig von nexus_id), solange genau eine Mod selektiert ist und ein API-Key vorhanden ist. Dies ist korrekt, da der Menueintrag sowohl bei nexus_id > 0 als auch bei nexus_id = 0 nutzbar sein soll (Kriterium 1 + 2).

### Kriterium 2: Kontextmenue "Nexus-Info abrufen" klickbar bei nexus_id = 0
- **Ergebnis:** PASS
- **Beleg:** `anvil/mainwindow.py:1759-1760` -- gleiche Bedingung wie Kriterium 1. Bei nexus_id = 0 wird statt API-Call ein Eingabe-Dialog geoeffnet (Zeile 2705-2717).

### Kriterium 3: API-Aufruf mit Tag-Prefix `query_mod_info:` (NICHT `mod_info:`), Statusbar "Lade Nexus-Info..."
- **Ergebnis:** PASS
- **Beleg:**
  - `anvil/core/nexus_api.py:120-125` -- `query_mod_info()` verwendet Tag `query_mod_info:{game}:{mod_id}`
  - `anvil/mainwindow.py:2730` -- `self._nexus_api.query_mod_info(nexus_slug, nexus_id)`
  - `anvil/mainwindow.py:2731` -- `self.statusBar().showMessage(tr("status.nexus_query_loading"), 5000)`
  - Tag-Prefix ist eindeutig `query_mod_info:`, NICHT `mod_info:`.

### Kriterium 4: Eingabe-Dialog bei nexus_id = 0 mit Titel "Nexus Mod-ID eingeben"
- **Ergebnis:** PASS
- **Beleg:** `anvil/mainwindow.py:2705-2708` -- `if nexus_id == 0:` oeffnet `get_text_input(self, tr("dialog.nexus_query_title"), tr("dialog.nexus_query_prompt"))`. Der i18n-Key `dialog.nexus_query_title` ist in de.json Zeile 231 als "Nexus Mod-ID eingeben" definiert.

### Kriterium 5: Gueltige Zahl -> API-Call mit eingegebener ID
- **Ergebnis:** PASS
- **Beleg:** `anvil/mainwindow.py:2712-2714` -- `nexus_id = int(text.strip())` und Pruefung `if nexus_id <= 0: raise ValueError`. Anschliessend wird `query_mod_info(nexus_slug, nexus_id)` in Zeile 2730 aufgerufen.

### Kriterium 6: Ungueltige Eingabe -> KEIN API-Call + Statusbar "Ungueltige Mod-ID"
- **Ergebnis:** PASS
- **Beleg:** `anvil/mainwindow.py:2715-2717` -- `except ValueError:` fuehrt zu `statusBar().showMessage(tr("status.nexus_query_invalid_id"), 5000)` und `return`. Abgedeckt: Buchstaben (ValueError bei int()), 0 und negative Zahlen (explizite Pruefung), leerer String (Zeile 2709: `if not ok or not text.strip(): return`).

### Kriterium 7: Erfolg -> meta.ini Update mit modid, version, newestVersion, name, author, description, url
- **Ergebnis:** PASS
- **Beleg:** `anvil/mainwindow.py:3056-3064`:
  ```python
  write_meta_ini(path, {
      "modid": str(data.get("mod_id", 0)),
      "version": data.get("version", ""),
      "newestVersion": data.get("version", ""),
      "name": data.get("name", ""),
      "author": data.get("author", ""),
      "description": data.get("summary", ""),
      "url": f"https://www.nexusmods.com/{nexus_slug}/mods/{data.get('mod_id', 0)}",
  })
  ```
  - Alle 7 Felder vorhanden: modid, version, newestVersion, name, author, description, url
  - `description` verwendet korrekt `data.get("summary", "")` (NICHT `data.get("description", "")`)
  - `newestVersion` wird korrekt auf den gleichen Wert wie `version` gesetzt
  - URL-Format stimmt: `https://www.nexusmods.com/{nexus_slug}/mods/{mod_id}`
  - `write_meta_ini()` in `anvil/core/mod_metadata.py:74` schreibt `modid`, `version`, `newestVersion` in `[General]` Section und `name`, `author`, `description`, `url` in `[installed]` Section -- alles korrekt.

### Kriterium 8: Erfolg -> Mod-Liste reload + Statusbar "Nexus-Info aktualisiert: {name}"
- **Ergebnis:** PASS
- **Beleg:**
  - `anvil/mainwindow.py:3065` -- `self._reload_mod_list()` nach `write_meta_ini`
  - `anvil/mainwindow.py:3066-3068` -- `statusBar().showMessage(tr("status.nexus_query_success", name=data.get("name", "")), 5000)`

### Kriterium 9: Nach Erfolg -> "Nexus-Seite oeffnen" aktiviert
- **Ergebnis:** PASS (logisch korrekt)
- **Beleg:** `anvil/mainwindow.py:1763` -- `has_nexus = single and selected_rows[0] < len(self._current_mod_entries) and self._current_mod_entries[selected_rows[0]].nexus_id > 0`. Nach dem Query wird `modid` in die meta.ini geschrieben (Zeile 3057). Wenn `_reload_mod_list()` die Mod-Entries neu laedt, wird `nexus_id` aus der meta.ini gelesen. Beim naechsten Rechtsklick wird `has_nexus` True sein, da `nexus_id > 0`.

### Kriterium 10: Kein API-Key -> Kontextmenue ausgegraut
- **Ergebnis:** PASS
- **Beleg:** `anvil/mainwindow.py:1760` -- `act_nexus_query.setEnabled(single and self._nexus_api.has_api_key())`. Ohne API-Key liefert `has_api_key()` False, Menueeintrag ist disabled.

### Kriterium 11: API-Fehler (404, 429, Timeout) -> Statusbar-Fehler, meta.ini NICHT veraendert
- **Ergebnis:** PASS
- **Beleg:**
  - `anvil/core/nexus_api.py:210-219` -- Bei HTTP 429, 401, >=400 wird `request_error.emit()` aufgerufen, NICHT `request_finished.emit()`.
  - `anvil/core/nexus_api.py:58-59` -- Bei Netzwerk-Fehlern (Timeout, DNS) wird `self.error.emit()` -> `_on_worker_error` -> `request_error.emit()`.
  - `anvil/mainwindow.py:3070-3072` -- `_on_nexus_error()` zeigt nur eine Statusbar-Meldung, ruft NICHT `write_meta_ini` auf.
  - Da `_on_nexus_response()` nur bei `request_finished` aufgerufen wird und `request_finished` bei Fehlern nicht emitted wird, bleibt meta.ini unveraendert.
  - **Hinweis (WARN):** `_pending_query_path` wird bei einem API-Fehler NICHT zurueckgesetzt. Es bleibt gesetzt bis zum naechsten erfolgreichen Query. Das ist kein Crash-Risiko (da beim naechsten Query ohnehin ueberschrieben wird), aber unsauber.

### Kriterium 12: GamePanel-Button bei genau 1 Selektion -> Query starten
- **Ergebnis:** PASS
- **Beleg:**
  - `anvil/widgets/game_panel.py:87` -- `nexus_query_requested = Signal()`
  - `anvil/widgets/game_panel.py:161-166` -- Button mit `clicked.connect(lambda checked=False: self.nexus_query_requested.emit())`
  - `anvil/mainwindow.py:282` -- `self._game_panel.nexus_query_requested.connect(self._on_nexus_query_from_panel)`
  - `anvil/mainwindow.py:2733-2739` -- `_on_nexus_query_from_panel()` prueft `len(selected_rows) != 1` und ruft dann `_ctx_query_nexus_info(selected_rows[0])` auf.

### Kriterium 13: GamePanel-Button bei 0 Selektionen -> Statusbar-Meldung
- **Ergebnis:** PASS
- **Beleg:** `anvil/mainwindow.py:2736-2738` -- `if len(selected_rows) != 1: self.statusBar().showMessage(tr("dialog.no_selection"), 3000); return`

### Kriterium 14: Row-Verschiebung -> install_path statt Row-Index (richtige meta.ini)
- **Ergebnis:** PASS
- **Beleg:**
  - `anvil/mainwindow.py:265` -- `self._pending_query_path: Path | None = None` (Typ ist Path, nicht int)
  - `anvil/mainwindow.py:2719` -- `self._pending_query_path = entry.install_path` (Path-Objekt, kein Index)
  - `anvil/mainwindow.py:3045-3048` -- `path = self._pending_query_path` mit `path.exists()` Pruefung
  - `anvil/mainwindow.py:3056` -- `write_meta_ini(path, {...})` schreibt direkt in den Path, unabhaengig von der aktuellen Zeilen-Position.

### Kriterium 15: NXM-Download + Query gleichzeitig -> getrennte Tag-Prefixes
- **Ergebnis:** PASS
- **Beleg:**
  - `anvil/core/nexus_api.py:118` -- `get_mod_info()` verwendet Tag `mod_info:{game}:{mod_id}`
  - `anvil/core/nexus_api.py:124-125` -- `query_mod_info()` verwendet Tag `query_mod_info:{game}:{mod_id}`
  - `anvil/mainwindow.py:3039` -- `elif tag.startswith("mod_info:")` (NXM-Download-Flow)
  - `anvil/mainwindow.py:3044` -- `elif tag.startswith("query_mod_info:")` (Query-Flow)
  - Beide Flows sind vollstaendig getrennt und beeinflussen sich nicht.

### Kriterium 16: Alle 6 neuen i18n-Keys in allen 6 Locale-Dateien
- **Ergebnis:** PASS
- **Beleg:** Alle 6 Keys sind in allen 6 Locale-Dateien vorhanden:

| Key | de | en | es | fr | it | pt |
|-----|----|----|----|----|----|----|
| `context.nexus_query` | de:98 | en:98 | es:98 | fr:98 | it:98 | pt:98 |
| `dialog.nexus_query_title` | de:231 | en:231 | es:231 | fr:231 | it:231 | pt:190 |
| `dialog.nexus_query_prompt` | de:232 | en:232 | es:232 | fr:232 | it:232 | pt:191 |
| `status.nexus_query_loading` | de:442 | en:442 | es:442 | fr:442 | it:442 | pt:442 |
| `status.nexus_query_success` | de:443 | en:443 | es:443 | fr:443 | it:443 | pt:443 |
| `status.nexus_query_invalid_id` | de:444 | en:444 | es:444 | fr:444 | it:444 | pt:444 |

### Kriterium 17: restart.sh startet ohne Fehler
- **Ergebnis:** NICHT IN MEINER DOMAENE
- **Hinweis:** Wird von Agent 1 oder im manuellen Test geprueft.

---

## Zusaetzliche Findings

### [LOW] _pending_query_path wird bei API-Fehler nicht zurueckgesetzt
- **Datei:** `anvil/mainwindow.py:3070-3072`
- **Problem:** Wenn `_on_nexus_error()` fuer einen `query_mod_info:` Tag aufgerufen wird, bleibt `_pending_query_path` auf dem alten Wert stehen, da nur `_on_nexus_response()` es zuruecksetzt (Zeile 3046). Dies ist kein funktionaler Bug, da:
  1. Beim naechsten Query wird `_pending_query_path` ueberschrieben (Zeile 2719)
  2. Bei Fehler wird kein `write_meta_ini` aufgerufen
  3. Es gibt keine Race-Condition, da alles im Main-Thread laeuft
- **Auswirkung:** Minimal -- nur unsauberer State, kein funktionales Problem.
- **Fix-Vorschlag:** Optional in `_on_nexus_error()` pruefen ob der Tag mit `query_mod_info:` beginnt und dann `self._pending_query_path = None` setzen.

---

## Zusammenfassung

| # | Kriterium | Ergebnis |
|---|-----------|----------|
| 1 | Kontextmenue klickbar bei nexus_id > 0 | PASS |
| 2 | Kontextmenue klickbar bei nexus_id = 0 | PASS |
| 3 | API-Aufruf mit `query_mod_info:` Tag + Statusbar | PASS |
| 4 | Eingabe-Dialog bei nexus_id = 0 | PASS |
| 5 | Gueltige Zahl -> API-Call | PASS |
| 6 | Ungueltige Eingabe -> kein API-Call + Statusbar | PASS |
| 7 | meta.ini Update mit allen 7 Feldern | PASS |
| 8 | Mod-Liste reload + Statusbar Erfolg | PASS |
| 9 | Nexus-Seite oeffnen nach Query aktiviert | PASS |
| 10 | Kein API-Key -> ausgegraut | PASS |
| 11 | API-Fehler -> Statusbar + meta.ini unveraendert | PASS |
| 12 | GamePanel-Button bei 1 Selektion | PASS |
| 13 | GamePanel-Button bei 0 Selektionen | PASS |
| 14 | install_path statt Row-Index | PASS |
| 15 | Getrennte Tag-Prefixes fuer NXM/Query | PASS |
| 16 | Alle i18n-Keys in allen 6 Locales | PASS |
| 17 | restart.sh ohne Fehler | NICHT IN MEINER DOMAENE |

## Ergebnis: 16/16 Punkte erfuellt (1 ausserhalb der Domaene)

**READY FOR COMMIT** (aus Sicht Daten & Persistenz)
