# QA Agent 3: mainwindow.py (Signal-Verbindung, Handler, Response-Router)
Datum: 2026-03-02

## Gepruefe Kriterien

- [x] 4: .meta modID > 0 -- direkter API-Call (kein Dialog) -- PASS
- [x] 7: Ungueltige Eingabe -- kein API-Call, Statusbar Fehlermeldung -- PASS
- [x] 8: .meta Update bei Erfolg (modID, name, modName, version, description) -- PASS (mit Einschraenkung, siehe Befunde)
- [x] 9: Downloads-Tabelle + Statusbar bei Erfolg -- PASS
- [x] 10: "Nexus-Seite oeffnen" nach Query aktiviert -- PASS
- [ ] 12: Fehlerbehandlung (404/429) -- FAIL (Pending-Feld nicht zurueckgesetzt)
- [x] 13: Separate Pending-Felder -- PASS (mit Einschraenkung)

## Code-Analyse

### Signal-Verbindung (Zeile 285)
```python
self._game_panel.dl_query_info_requested.connect(self._on_dl_query_info)
```
- Signal: `dl_query_info_requested = Signal(str)` in `game_panel.py:88`
- Handler: `_on_dl_query_info(self, archive_path: str)` in `mainwindow.py:2744`
- Verbindung korrekt, Signatur stimmt (str -> str)

### Signal-Emission (game_panel.py:1485)
```python
self.dl_query_info_requested.emit(first)
```
- `first` ist der erste selektierte Archivpfad (str), korrekt

## Handler-Logik (mainwindow.py:2744-2800)

### Fallback-Kette:

**Schritt 1 -- .meta modID (Zeile 2748-2755):**
```python
mod_id_str = self._game_panel._read_meta_mod_id(archive_path)
mod_id = 0
if mod_id_str:
    try:
        mod_id = int(mod_id_str)
    except ValueError:
        pass
```
- `_read_meta_mod_id()` gibt String oder None zurueck
- Pruefung `if mod_id_str` filtert None korrekt
- Konvertierung zu int mit ValueError-Catch korrekt
- Wenn modID > 0: Kein Dialog, direkt weiter zu Schritt 4 (API-Call)
- **Kriterium 4: PASS** -- Bei .meta mit modID > 0 wird direkt die API aufgerufen

**Schritt 2 -- Dateinamen-Parsing (Zeile 2757-2769):**
```python
if mod_id <= 0:
    filename = Path(archive_path).name
    parsed_id = extract_nexus_mod_id(filename)
    if parsed_id and parsed_id > 0:
        answer = QMessageBox.question(...)
        if answer == QMessageBox.StandardButton.Yes:
            mod_id = parsed_id
```
- Regex-Extraktion mit Bestaetigungsdialog
- Bei "Nein" im Dialog: mod_id bleibt 0, Fallthrough zu Schritt 3
- Korrekt implementiert

**Schritt 3 -- Manueller Dialog (Zeile 2771-2785):**
```python
if mod_id <= 0:
    text, ok = get_text_input(...)
    if not ok or not text.strip():
        return
    try:
        mod_id = int(text.strip())
        if mod_id <= 0:
            raise ValueError
    except ValueError:
        self.statusBar().showMessage(tr("status.nexus_query_invalid_id"), 5000)
        return
```
- Prueft: Cancel/leer -> return (kein API-Call)
- Prueft: Buchstaben -> ValueError -> Statusbar + return
- Prueft: 0 -> `mod_id <= 0 -> raise ValueError` -> Statusbar + return
- Prueft: Negative Zahl -> `mod_id <= 0 -> raise ValueError` -> Statusbar + return
- **Kriterium 7: PASS** -- Alle ungueltigen Eingaben werden abgefangen

**Schritt 4 -- API-Call (Zeile 2787-2800):**
```python
self._pending_dl_query_path = archive_path
nexus_slug = ""
if self._current_plugin:
    nexus_slug = (getattr(...) or getattr(...))
if not nexus_slug:
    return
self._nexus_api.query_mod_info(nexus_slug, mod_id)
self.statusBar().showMessage(tr("status.nexus_query_loading"), 5000)
```
- Pending-Pfad wird gesetzt BEVOR geprueft wird ob nexus_slug vorhanden
- Wenn kein Slug: `_pending_dl_query_path` bleibt gesetzt (minor leak, LOW)
- API-Aufruf mit Tag-Prefix `query_mod_info:` (korrekt, keine Kollision mit `mod_info:`)

## Response-Router (mainwindow.py:3125-3170)

```python
elif tag.startswith("query_mod_info:") and isinstance(data, dict):
    dl_path = self._pending_dl_query_path
    mod_path = self._pending_query_path

    if dl_path:
        # Downloads-Tab query
        self._pending_dl_query_path = None
        self._update_download_meta(dl_path, data)
        self._game_panel.refresh_downloads()
        # Tooltip + Statusbar...
    elif mod_path:
        # Mod-Liste query (existing logic)
        self._pending_query_path = None
        # write_meta_ini + _reload_mod_list...
```

### Routing-Prioritaet:
- `dl_path` wird ZUERST geprueft (Downloads-Tab hat Vorrang)
- `mod_path` nur wenn kein `dl_path` gesetzt
- Das ist funktional korrekt, ABER: Wenn BEIDE gleichzeitig gesetzt sind, wird nur der Downloads-Tab bedient, die Mod-Liste wird ignoriert (siehe Befunde)

## _update_download_meta (mainwindow.py:2802-2820)

```python
def _update_download_meta(self, archive_path: str, nexus_data: dict) -> None:
    meta_path = Path(archive_path + ".meta")
    cp = configparser.ConfigParser()
    cp.optionxform = str                    # Case-Preserve: KORREKT
    if meta_path.is_file():
        try:
            cp.read(str(meta_path), encoding="utf-8")
        except Exception:
            pass
    if not cp.has_section("General"):
        cp.add_section("General")
    cp.set("General", "modID", str(nexus_data.get("mod_id", 0)))
    cp.set("General", "modName", nexus_data.get("name", ""))
    cp.set("General", "name", nexus_data.get("name", ""))
    cp.set("General", "version", nexus_data.get("version", ""))
    cp.set("General", "description", nexus_data.get("summary", ""))
    with open(meta_path, "w", encoding="utf-8") as f:
        cp.write(f)
```

**Pruefung:**
- `optionxform = str` -- Case wird bewahrt (nicht zu lowercase konvertiert): KORREKT
- Bestehende Felder bleiben erhalten (liest existierende .meta zuerst): KORREKT
- Geschriebene Felder: modID, modName, name, version, description: KORREKT
- **Kriterium 8: PASS** -- Alle geforderten Felder werden geschrieben, bestehende bleiben erhalten

**Hinweis:** Die Spec fordert "modID, name, modName, version, description". Die Implementierung schreibt genau diese 5 Felder. Korrekt.

## Erfolgs-Pfad (Kriterien 8, 9, 10)

### Kriterium 9 -- Tabelle + Statusbar:
- `self._game_panel.refresh_downloads()` wird aufgerufen (Zeile 3133): KORREKT
- `self.statusBar().showMessage(tr("status.nexus_query_success", name=name), 5000)` (Zeile 3143-3144): KORREKT
- Tooltip wird gesetzt via `update_download_tooltip()` (Zeile 3142): KORREKT (Bonus)
- **Kriterium 9: PASS**

### Kriterium 10 -- "Nexus-Seite oeffnen" nach Query:
- Nach erfolgreichem Query wird `modID` in .meta geschrieben (z.B. "14817")
- Beim naechsten Rechtsklick liest `_read_meta_mod_id()` diesen Wert als "14817"
- `act_nexus.setEnabled(mod_id is not None)` -> `"14817" is not None` = True
- **Kriterium 10: PASS** -- "Nexus-Seite oeffnen" ist nach Query aktiviert

**Randnotiz:** `act_nexus.setEnabled(mod_id is not None)` ist auch True wenn modID "0" ist (String "0" is not None). Das ist ein vorbestehender Bug der Downloads-Tab Kontextmenue-Logik, aber nicht Teil dieses Features.

## Fehlerbehandlung (Kriterium 12)

### API-Fehler-Flow:
1. NexusAPI erkennt HTTP 404/429/Timeout
2. Emittiert `request_error(tag, message)` 
3. `_on_nexus_error(tag, message)` zeigt Statusbar-Meldung

### .meta bei Fehler:
- Bei Fehlern wird `request_error` emittiert, NICHT `request_finished`
- `_on_nexus_response` wird also NICHT aufgerufen
- `_update_download_meta` wird NICHT aufgerufen
- **.meta bleibt bei Fehler unberuehrt: KORREKT**

### Problem: Pending-Feld bei Fehler:
```python
def _on_nexus_error(self, tag: str, message: str) -> None:
    self.statusBar().showMessage(tr("status.nexus_error", message=message), 5000)
    # KEIN Reset von _pending_dl_query_path oder _pending_query_path!
```
- `_pending_dl_query_path` wird bei API-Fehler NICHT auf None zurueckgesetzt
- Szenario: User macht Query auf Archiv A -> 404 -> `_pending_dl_query_path = "/path/to/A.zip"`
  Danach macht User Query auf Mod in Mod-Liste -> Erfolg -> Response-Router findet `dl_path` noch gesetzt -> schreibt faelschlicherweise .meta fuer Archiv A mit den Daten der Mod-Liste-Query
- **Kriterium 12: FAIL** -- Pending-Feld wird bei Fehler nicht zurueckgesetzt, was zu Ghost-State fuehren kann

### Statusbar bei spezifischen Fehlern:
- 404: `request_error` mit "HTTP 404" -> `tr("status.nexus_error", message="HTTP 404")`: KORREKT
- 429: `request_error` mit "Rate Limit erreicht. Bitte warten." -> Statusbar zeigt Warnung: KORREKT
- Timeout/Netzwerk: Exception-Handler in `_ApiWorker.run()` -> `error.emit(tag, str(exc))` -> `_on_nexus_error`: KORREKT

## Separate Pending-Felder (Kriterium 13)

### Deklaration:
```python
self._pending_query_path: Path | None = None       # Zeile 266 (Mod-Liste)
self._pending_dl_query_path: str | None = None      # Zeile 267 (Downloads-Tab)
```
- Zwei separate Felder: KORREKT
- Verschiedene Typen (Path vs str): KORREKT (konsistent mit jeweiliger Nutzung)

### Gleichzeitige Nutzung:
- Beide koennen unabhaengig gesetzt werden
- ABER im Response-Router (Zeile 3125-3170): `if dl_path:` hat Vorrang ueber `elif mod_path:`
- Wenn BEIDE gesetzt sind und eine `query_mod_info:` Response eintrifft, wird NUR der Downloads-Tab bedient
- Die Mod-Liste-Query bleibt "haengen" bis eine ZWEITE Response kommt
- Da beide den gleichen Tag-Prefix `query_mod_info:` nutzen, kann der Router nicht unterscheiden welche Response fuer welchen Flow bestimmt ist
- **Kriterium 13: PASS (bedingt)** -- Die Felder sind separat, aber der Router kann bei gleichzeitigen Queries nicht korrekt zuordnen. In der Praxis ist gleichzeitige Nutzung selten, da der User explizit Rechtsklick machen muss.

## i18n-Keys Pruefung

Alle 3 neuen Keys fuer Downloads-Tab Query in allen 6 Locales vorhanden:
- `game_panel.query_nexus_info`: de/en/es/fr/it/pt -- VORHANDEN
- `game_panel.query_nexus_enter_id`: de/en/es/fr/it/pt -- VORHANDEN
- `game_panel.query_nexus_parsed_id`: de/en/es/fr/it/pt -- VORHANDEN

Bestehende Keys die mitgenutzt werden:
- `status.nexus_query_loading`: de/en/es/fr/it/pt -- VORHANDEN
- `status.nexus_query_success`: de/en/es/fr/it/pt -- VORHANDEN
- `status.nexus_query_invalid_id`: de/en/es/fr/it/pt -- VORHANDEN
- `status.nexus_error`: de/en/es/fr/it/pt -- VORHANDEN (in zwei Varianten: status und game_panel Namespace)

## Befunde

### [MEDIUM] Pending-Feld wird bei API-Fehler nicht zurueckgesetzt
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:3172-3174`
- **Problem:** `_on_nexus_error()` setzt weder `_pending_dl_query_path` noch `_pending_query_path` auf None zurueck. Bei einem API-Fehler (404, 429, Timeout) bleibt der Pending-Pfad gesetzt. Wenn danach ein ANDERER Query erfolgreich ist, koennte der Response-Router den alten Pending-Pfad faelschlicherweise verwenden.
- **Reproduktion:** 1) Query auf Archiv A -> 404-Fehler. 2) Query auf Mod B in Mod-Liste -> Erfolg. 3) Router findet `dl_path` (Archiv A) noch gesetzt -> schreibt .meta fuer A mit Daten von Mod B.
- **Fix:** In `_on_nexus_error()` pruefen ob der Tag mit `query_mod_info:` beginnt und dann beide Pending-Felder zuruecksetzen:
```python
def _on_nexus_error(self, tag: str, message: str) -> None:
    if tag.startswith("query_mod_info:"):
        self._pending_dl_query_path = None
        self._pending_query_path = None
    self.statusBar().showMessage(tr("status.nexus_error", message=message), 5000)
```

### [LOW] Pending-Feld gesetzt bevor nexus_slug geprueft wird
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:2788-2797`
- **Problem:** `_pending_dl_query_path` wird in Zeile 2788 gesetzt, aber in Zeile 2796 kann die Methode ohne API-Call returnen wenn kein `nexus_slug` vorhanden ist. Der Pending-Pfad bleibt dann gesetzt.
- **Fix:** `_pending_dl_query_path` erst nach dem Slug-Check setzen (Zeilen 2788 und 2790-2797 tauschen).

### [LOW] Response-Router kann bei gleichzeitigen Queries nicht korrekt zuordnen
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:3125-3170`
- **Problem:** Wenn sowohl `_pending_dl_query_path` als auch `_pending_query_path` gesetzt sind, wird bei einer `query_mod_info:` Response immer der Downloads-Tab-Pfad bevorzugt. Die Mod-Liste-Query wird erst bei einer ZWEITEN Response bedient. Da der Tag-Prefix identisch ist, kann nicht unterschieden werden welche Response zu welchem Flow gehoert.
- **Impact:** Gering, da gleichzeitige Queries in der Praxis selten sind (User muesste extrem schnell zwischen Mod-Liste und Downloads-Tab wechseln).
- **Fix (langfristig):** Unterschiedliche Tag-Prefixes verwenden, z.B. `dl_query_mod_info:` vs `query_mod_info:`.

### [LOW] "Nexus-Seite oeffnen" auch bei modID=0 aktiviert (vorbestehend)
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py:1431`
- **Problem:** `act_nexus.setEnabled(mod_id is not None)` -- wenn .meta modID=0 enthaelt, gibt `_read_meta_mod_id` den String "0" zurueck, `"0" is not None` ist True. "Nexus-Seite oeffnen" ist aktiviert, fuehrt aber zu einer ungueltigen URL.
- **Hinweis:** Dies ist ein vorbestehender Bug, nicht durch dieses Feature eingefuehrt.
- **Fix:** `act_nexus.setEnabled(mod_id is not None and mod_id != "0")`

## Bewertung

| Kriterium | Status | Kommentar |
|-----------|--------|-----------|
| 4 | PASS | .meta modID > 0 -> direkter API-Call ohne Dialog |
| 7 | PASS | Alle ungueltigen Eingaben (leer, Buchstaben, 0, negativ) abgefangen |
| 8 | PASS | modID, name, modName, version, description geschrieben; bestehende Felder bleiben |
| 9 | PASS | refresh_downloads() + Statusbar "Nexus-Info aktualisiert: {name}" |
| 10 | PASS | modID in .meta -> "Nexus-Seite oeffnen" wird aktiviert |
| 12 | FAIL | .meta bei Fehler unberuehrt (KORREKT), ABER Pending-Feld nicht zurueckgesetzt (BUG) |
| 13 | PASS (bedingt) | Separate Felder vorhanden, aber Routing-Prioritaet bei Gleichzeitigkeit problematisch |

## Ergebnis: 6/7 Punkte erfuellt

**NEEDS FIXES**

Der MEDIUM-Befund (Pending-Feld bei Fehler nicht zurueckgesetzt) muss behoben werden bevor Kriterium 12 als erfuellt gelten kann. Die .meta wird zwar korrekt NICHT veraendert bei Fehlern, aber der verbleibende Ghost-State im Pending-Feld kann zu fehlerhaftem Routing bei nachfolgenden Queries fuehren.
