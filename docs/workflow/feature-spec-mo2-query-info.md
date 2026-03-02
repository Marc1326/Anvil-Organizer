# Feature: Nexus Query Info fuer Downloads-Tab (MO2-Style)
Datum: 2026-03-02

## MO2-Analyse Zusammenfassung

### Agent 1 (Dateiname-Parsing)
MO2 nutzt `interpretNexusFileName()` mit einem Regex, der Mod-Name (Gruppe 1) und Nexus-Mod-ID (Gruppe 3, mind. 2-stellig, zwischen Bindestrichen) extrahiert. File-ID wird NICHT aus Dateinamen extrahiert. Fallback: SelectionDialog, dann manueller QInputDialog.

### Agent 2 (Query Info Flow)
API-Endpunkt: GET /v1/games/{game}/mods/{modID}.json. Response: name, version, author, summary, description, category_id, uploaded_by, endorsement, updated_timestamp. Persistierung in meta.ini. Dirty-Flag Pattern. Fehlerbehandlung mit nxmRequestFailed, Rate-Limiting, 60s Timeout.

### Agent 3 (Downloads-Tab Kontextmenue)
Kontextmenue state-basiert. "Query Info" und "Visit on Nexus" gegenseitig exklusiv. isInfoIncomplete() = fileID == 0 || modID == 0. Warning-Icon bei fehlenden Infos. Tooltip mit modName (ID) version + description. MD5-Suche bevorzugt, Fallback auf Dateinamen-Parsing.

## User Stories

- Als User moechte ich im Downloads-Tab per Rechtsklick "Nexus-Info abrufen" auf einem Archiv ohne modID nutzen koennen, damit die Mod-ID automatisch aus dem Dateinamen extrahiert oder manuell eingegeben wird und die Nexus-Metadaten in der .meta-Datei gespeichert werden.
- Als User moechte ich im Downloads-Tab per Rechtsklick "Nexus-Info abrufen" auf einem Archiv mit vorhandener modID nutzen koennen, damit die Metadaten (Name, Version, Autor, Beschreibung) von Nexus aktualisiert werden.
- Als User moechte ich nach erfolgreichem Query Info einen Tooltip auf der Download-Zeile sehen, der den Mod-Namen, die Version und eine Kurzbeschreibung anzeigt.
- Als User moechte ich, dass "Query Info" und "Nexus-Seite oeffnen" sich im Downloads-Kontextmenue ergaenzen: Wenn keine modID vorhanden ist, ist "Visit Nexus" deaktiviert, und bei vorhandener modID sind beide verfuegbar.

## Ist-Zustand Anvil

### Downloads-Tab Kontextmenue (game_panel.py:1391-1516)
```
Install
---
Nexus-Seite oeffnen (enabled wenn modID vorhanden)
Oeffne Datei
Oeffne Meta Datei (enabled wenn .meta existiert)
---
Zeige im Downloadverzeichnis
---
Loeschen...
Verstecken / Einblenden
---
Loeschen: Installierte / Nicht installierte / Alle
---
Verstecken: Installierte / Nicht installierte / Alle / Alle einblenden
```

### Bestehende Nexus-API-Methoden (nexus_api.py)
- `validate_key()` -- API-Key Validierung
- `get_mod_info(game, mod_id)` -- Tag `mod_info:` (NXM-Download-Flow)
- `query_mod_info(game, mod_id)` -- Tag `query_mod_info:` (Mod-Liste Query)
- `get_mod_files(game, mod_id)` -- Dateiliste
- `get_download_links(game, mod_id, file_id)` -- Download-URLs

### Bestehende .meta Lese-Methoden (game_panel.py)
- `_read_meta_mod_id(archive_path)` -- liest modID aus .meta (Zeile 1270)
- `_get_meta_path(archive_path)` -- prueft ob .meta existiert (Zeile 1284)

### Bestehende .meta Datei-Formate

**Typ A: Anvil/MO2-generiert (via NXM-Download):**
```ini
[General]
gameName=cyberpunk2077
modID=14817
fileID=78154
url=...
name=Peachu Casual Dress - Archive XL
modName=Peachu Casual Dress - Archive XL
version=1.0.0.0
installed=true
```

**Typ B: Manuell heruntergeladen (nur Status):**
```ini
[General]
installed=true
uninstalled=false
```

### Echte Dateinamen-Muster (Cyberpunk 2077)
```
Peachu Casual Dress - Archive XL-14817-1-1716336327.rar     -> modID=14817
Caldos Ripper-8378-15-0-0-1760955833.zip                    -> modID=8378
Ripper Boots-5231-1-1663279901.zip                          -> modID=5231
MELUMINARY'S VIRTUAL ATELIER - FEMV-14248-15-1757310313.zip -> modID=14248
Kwek's Sartorial Omnibus Shop - REDMod Version-6779-1-1-5-1679005572.zip -> modID=6779
```

## Soll-Zustand

### 1. Nexus-ID aus Dateinamen extrahieren

**Neue Datei** `anvil/core/nexus_filename_parser.py`:

```python
import re

_NEXUS_FILENAME_RE = re.compile(
    r'^(.+?)'              # Gruppe 1: Mod-Name (non-greedy)
    r'-(\d{2,})'           # Gruppe 2: Mod-ID (mind. 2-stellig, nach Bindestrich)
    r'(?:-[\d]+)*'         # optionale Versions-/File-ID-Segmente
    r'-(\d{9,11})'         # optionale Timestamp-Gruppe (9-11 Stellen)
    r'\.(?:zip|rar|7z)$',  # Dateiendung
    re.IGNORECASE
)

def extract_nexus_mod_id(filename: str) -> int | None:
    """Versuche Nexus Mod-ID aus dem Dateinamen zu extrahieren.

    Nexus-Dateinamen: ModName-ModID-version[-extra]-timestamp.ext
    Returns: Mod-ID als int, oder None wenn nicht erkennbar.
    """
    m = _NEXUS_FILENAME_RE.match(filename)
    if m:
        try:
            return int(m.group(2))
        except ValueError:
            pass

    # Fallback: Erste Zahlengruppe >= 2 Stellen zwischen Bindestrichen
    candidates = re.findall(r'-(\d{2,})-', filename)
    if candidates:
        try:
            return int(candidates[0])
        except ValueError:
            pass

    return None
```

### 2. Downloads-Tab Kontextmenue erweitern

**Neuer Eintrag "Nexus-Info abrufen"** nach "Nexus-Seite oeffnen":

```
Install
---
Nexus-Seite oeffnen (enabled wenn modID vorhanden)
Nexus-Info abrufen  <- NEU (enabled wenn API-Key gesetzt UND Einzelselektion)
Oeffne Datei
Oeffne Meta Datei
---
...
```

**Sichtbarkeits-Logik:**
- Immer sichtbar bei Einzelselektion
- Enabled wenn API-Key gesetzt
- Disabled bei Mehr-Selektion

**MO2-Abweichung:** In MO2 sind "Query Info" und "Visit Nexus" gegenseitig exklusiv. In Anvil sind beide gleichzeitig sichtbar, da "Query Info" auch zum Aktualisieren dient.

### 3. Query-Info Flow fuer Downloads-Tab

**Neues Signal in GamePanel:**
```python
dl_query_info_requested = Signal(str)  # archive_path
```

**Separate Pending-Felder:**
```python
self._pending_dl_query_path: str | None = None   # Downloads-Tab
self._pending_query_path: Path | None = None      # Mod-Liste (existiert bereits)
```

### 4. .meta Datei aktualisieren

```python
def _update_download_meta(archive_path: str, nexus_data: dict) -> None:
    """Update .meta neben Archiv mit Nexus-Daten. Bestehende Felder bleiben erhalten."""
    meta_path = Path(archive_path + ".meta")
    cp = configparser.ConfigParser()
    cp.optionxform = str
    if meta_path.is_file():
        cp.read(str(meta_path), encoding="utf-8")
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

### 5. Tooltip auf Download-Zeilen

Nach erfolgreichem Query: Tooltip auf Name-Spalte:
```
ModName (ID: 14817) v1.0
Kurzbeschreibung aus der Nexus-API...
```

## Signal-Flow

```
                    Downloads-Tab                          MainWindow
                    -------------                          ----------
User Rechtsklick
  -> "Nexus-Info abrufen"
  -> dl_query_info_requested.emit(archive_path) -----> _on_dl_query_info(path)
                                                           |
                                                     +-----+------+
                                                     | .meta hat   |
                                                     | modID?      |
                                                     +-----+------+
                                                    Ja     |    Nein
                                                    |      |      |
                                                    |      |  Dateinamen-
                                                    |      |  Parsing
                                                    |      |      |
                                                    |      |  Gefunden?
                                                    |      |  Nein -> QInputDialog
                                                    |      |      |
                                                    +------+------+
                                                           |
                                                     mod_id (int)
                                                           |
                                                     _pending_dl_query_path = path
                                                           |
                                            NexusAPI.query_mod_info(slug, mod_id)
                                                           |
                                                    --- async ---
                                                           |
                                            _on_nexus_response("query_mod_info:...")
                                                           |
                                                +----------+----------+
                                                | _pending_dl_query   |
                                                | oder _pending_query?|
                                                +----------+----------+
                                              Downloads-Tab|     Mod-Liste
                                                    |              |
                                            _update_download_meta  write_meta_ini
                                                    |              |
                                            refresh_downloads()    _reload_mod_list()
                                                    |
                                            Statusbar: "Nexus-Info aktualisiert: {name}"
```

## Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `anvil/core/nexus_filename_parser.py` | **NEU** -- `extract_nexus_mod_id()` |
| `anvil/widgets/game_panel.py` | Signal, Kontextmenue, Tooltip |
| `anvil/mainwindow.py` | Signal-Verbindung, Handler, Response-Router |
| `anvil/core/nexus_api.py` | KEINE Aenderung (query_mod_info existiert) |
| `anvil/locales/de.json` | 3 neue Keys |
| `anvil/locales/en.json` | 3 neue Keys |
| `anvil/locales/es.json` | 3 neue Keys |
| `anvil/locales/fr.json` | 3 neue Keys |
| `anvil/locales/it.json` | 3 neue Keys |
| `anvil/locales/pt.json` | 3 neue Keys |

## MO2-Vergleich

| Feature | MO2 | Anvil (geplant) |
|---------|-----|-----------------|
| Kontextmenue-Position | Eigene Gruppe, state-basiert | Nach "Visit Nexus" |
| ID-Quelle Prioritaet | MD5 -> Regex -> Dialog | .meta -> Regex -> Dialog |
| MD5-Suche | Ja (bevorzugt) | Nein (bewusst) |
| Dateinamen-Regex | MO2-eigener Regex | MO2-kompatibler Regex |
| .meta Update | DownloadInfo-Objekt | configparser merge |
| Warning-Icon | Ja (gelbes Dreieck) | Nein (Phase 2) |
| Versteckte Spalten | 4 (Mod Name, Version, ID, Game) | Nein (Phase 2) |
| Tooltip | HTML mit Description | Plaintext mit Summary |
| Query + Visit exklusiv | Ja | Nein (beide gleichzeitig) |

## Neue i18n-Keys

| Key | DE | EN |
|-----|----|----|
| `game_panel.query_nexus_info` | "Nexus-Info abrufen" | "Query Nexus Info" |
| `game_panel.query_nexus_enter_id` | "Nexus Mod-ID eingeben (aus der URL):" | "Enter Nexus Mod ID (from URL):" |
| `game_panel.query_nexus_parsed_id` | "Aus Dateiname erkannt: Mod-ID {id}. Verwenden?" | "Detected from filename: Mod ID {id}. Use it?" |

## Abhaengigkeiten

1. Nexus API-Key muss gesetzt sein
2. Game-Plugin muss Nexus-Slug liefern
3. Bestehende `query_mod_info()` in nexus_api.py wird wiederverwendet
4. Bestehende `_on_nexus_response()` Routing wird erweitert
5. Feature-Spec nexus-query (Mod-Liste) sollte implementiert sein

## Risiken

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Pending-Kollision (Mod-Liste + Downloads gleichzeitig) | Mittel | Zwei separate Pending-Felder |
| Regex matcht falsch (Version statt Mod-ID) | Mittel | Bestaetigungs-Dialog |
| Archive ohne Nexus-Herkunft | Mittel | Manueller ID-Dialog als Fallback |
| Rate-Limit | Mittel | Kein Batch, Statusbar-Warnung bei 429 |

## Zentrale Code-Stellen

- **Kontextmenue**: `anvil/widgets/game_panel.py:1391-1516`
- **modID lesen**: `anvil/widgets/game_panel.py:1270-1282`
- **Nexus-Response Router**: `anvil/mainwindow.py:2996-3072`
- **Mod-Liste Query**: `anvil/mainwindow.py:2698-2731`
- **API Methode**: `anvil/core/nexus_api.py:120-125`

## Akzeptanz-Kriterien (ALLE muessen erfuellt sein)

- [ ] 1. Wenn User Rechtsklick auf ein Archiv im Downloads-Tab macht (Einzelselektion), erscheint "Nexus-Info abrufen" im Kontextmenue zwischen "Nexus-Seite oeffnen" und "Oeffne Datei"
- [ ] 2. Wenn User Rechtsklick auf mehrere Archive macht (Mehrselektion), ist "Nexus-Info abrufen" NICHT sichtbar oder disabled
- [ ] 3. Wenn kein Nexus API-Key gesetzt ist, ist "Nexus-Info abrufen" ausgegraut
- [ ] 4. Wenn User "Nexus-Info abrufen" klickt und .meta bereits modID > 0 enthaelt, wird die Nexus-API direkt mit dieser ID aufgerufen (kein Dialog)
- [ ] 5. Wenn User "Nexus-Info abrufen" klickt und keine modID in .meta existiert, aber Dateiname eine Nexus-ID enthaelt (z.B. "Peachu Casual Dress-14817-1-1716336327.rar"), wird die erkannte ID im Bestaetigungs-Dialog vorgeschlagen
- [ ] 6. Wenn User "Nexus-Info abrufen" klickt und weder .meta noch Dateiname eine ID liefern, oeffnet sich ein QInputDialog zur manuellen Eingabe
- [ ] 7. Wenn User im manuellen Dialog ungueltigen Wert eingibt (leer, Buchstaben, 0, negativ), wird KEIN API-Call ausgeloest und Statusbar zeigt Fehlermeldung
- [ ] 8. Wenn Nexus-API erfolgreich antwortet, wird .meta neben dem Archiv mit modID, name, modName, version, description aktualisiert (bestehende Felder bleiben erhalten)
- [ ] 9. Wenn Nexus-API erfolgreich antwortet, wird Downloads-Tabelle aktualisiert und Statusbar zeigt "Nexus-Info aktualisiert: {name}"
- [ ] 10. Wenn nach erfolgreichem Query User erneut Rechtsklick macht, ist "Nexus-Seite oeffnen" jetzt aktiviert
- [ ] 11. Wenn nach erfolgreichem Query User Mauszeiger ueber Download-Zeile bewegt, erscheint Tooltip mit Mod-Name, ID und Beschreibung
- [ ] 12. Wenn Nexus-API Fehler zurueckgibt (404, 429, Timeout), wird .meta NICHT veraendert und Statusbar zeigt Fehlermeldung
- [ ] 13. Wenn gleichzeitig Query fuer Mod-Liste UND Downloads-Tab laeuft, interferieren die Flows NICHT (separate Pending-Felder)
- [ ] 14. `extract_nexus_mod_id("Peachu Casual Dress - Archive XL-14817-1-1716336327.rar")` gibt 14817 zurueck
- [ ] 15. `extract_nexus_mod_id("random_mod_without_id.zip")` gibt None zurueck
- [ ] 16. Alle 3 neuen i18n-Keys existieren in allen 6 Locale-Dateien (de, en, es, fr, it, pt)
- [ ] 17. restart.sh startet ohne Fehler
