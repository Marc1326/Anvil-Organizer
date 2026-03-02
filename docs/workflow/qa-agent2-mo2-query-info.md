# Agent 2: MO2 Query Info Flow
Datum: 2026-03-02

## API-Aufrufe

### Haupt-Endpunkt: Mod-Beschreibung

```
GET https://api.nexusmods.com/v1/games/{gameName}/mods/{modID}
```

**Quellcode:** `nexusinterface.cpp` (Zeile 886-891)

**Request-Headers:**
```
APIKEY: {user_api_key}
User-Agent: {custom_user_agent}
Content-Type: application/json
```

### Weitere Endpunkte

| Typ | URL | Verwendung |
|-----|-----|------------|
| `TYPE_CHECKUPDATES` | `/v1/games/{game}/mods/updated?period={1d/1w/1m}` | Batch-Update-Check |
| `TYPE_FILES` | `/v1/games/{game}/mods/{modID}/files` | Datei-Liste eines Mods |
| `TYPE_FILEINFO` | `/v1/games/{game}/mods/{modID}/files/{fileID}` | Einzelne Datei-Info |
| `TYPE_FILEINFO_MD5` | `/v1/games/{game}/mods/md5_search/{hash_hex}` | MD5-basierte Suche |

## Response-Verarbeitung

### Weg A: ModInfoRegular (installierte Mods)

**Ausloeser:** `ModInfoRegular::updateNXMInfo()` (modinforegular.cpp:422-430)

**Response-Handler:** `nxmDescriptionAvailable()` (modinforegular.cpp:349-373)

| Response-Feld | Lokales Feld | Beschreibung |
|---------------|--------------|--------------|
| `description` | `m_NexusDescription` | HTML-Beschreibung |
| `endorsement.endorse_status` | `m_EndorsedState` | Endorsed/Abstained |
| `updated_timestamp` | `m_NexusLastModified` | Letztes Update |
| (implizit) | `m_LastNexusQuery` | Zeitpunkt der Abfrage |

### Weg B: MainWindow (Update-Check, ausfuehrlicher)

**Handler:** `MainWindow::nxmModInfoAvailable()` (mainwindow.cpp:3342-3409)

| Response-Feld | Setter-Methode | meta.ini Key |
|---------------|----------------|--------------|
| `version` | `setNewestVersion()` | `newestVersion` |
| `description` | `setNexusDescription()` | `nexusDescription` |
| `category_id` | `setNexusCategory()` | `nexusCategory` |
| `author` | `setAuthor()` | `author` |
| `uploaded_by` | `setUploader()` | `uploader` |
| `uploaded_users_profile_url` | `setUploaderUrl()` | `uploaderUrl` |
| `endorsement.endorse_status` | `setIsEndorsed()` | `endorsed` |
| `updated_timestamp` | `setNexusLastModified()` | `nexusLastModified` |

### Weg C: DownloadManager (Downloads)

Zweistufige Abfrage:
1. **STATE_FETCHINGMODINFO:** `requestDescription()` -> Mod-Name, Author, Category
2. **STATE_FETCHINGFILEINFO:** `requestFiles()` -> Datei-Details (Name, Version, FileID)

## Persistierung

### meta.ini (Pro Mod-Ordner)

Alle Nexus-Metadaten in `{mod_path}/meta.ini` (QSettings/INI-Format):

| INI-Key | Typ | Standard |
|---------|-----|----------|
| `modid` | int | -1 |
| `version` | VersionInfo | "" |
| `newestVersion` | VersionInfo | "" |
| `name` | QString | "" |
| `author` | QString | "" |
| `uploader` | QString | "" |
| `uploaderUrl` | QString | "" |
| `nexusDescription` | QString | "" |
| `nexusCategory` | int | 0 |
| `repository` | QString | "Nexus" |
| `gameName` | QString | managed game |
| `lastNexusQuery` | QDateTime ISO | "" |
| `lastNexusUpdate` | QDateTime ISO | "" |
| `endorsed` | int/enum | unknown |

### Dirty-Flag Pattern

MO2 nutzt `m_MetaInfoChanged` Boolean:
- Setter setzt auf `true`
- `saveMeta()` schreibt nur wenn `true`
- Nach Schreiben zurueck auf `false`

## Fehlerbehandlung

### nxmRequestFailed Signal

Emittiert bei:
1. HTTP-Statuscode != 2xx
2. Leere Response (`data.isNull()`)
3. JSON-Parse-Fehler
4. Timeout (60 Sekunden)
5. Netzwerk-Fehler

### Rate-Limiting

- `shouldThrottle()` -- wenn wenige Requests uebrig, nur Downloads erlaubt
- `exhausted()` -- Queue leeren + Warnmeldung
- Max 6 gleichzeitige Requests
- 5-Minuten-Cooldown pro Mod (`canBeUpdated()`)

### Validierung

- Login-Validierung: `getAccessManager()->validated()`
- API-Key als Header
- `isValidModID(int id) { return (id > 0); }`

## Zusammenfassung

MO2 nutzt zwei getrennte Wege fuer Query Info: Mod-Liste (updateNXMInfo -> requestDescription) und Downloads (queryInfo -> zweistufig: Description + Files). Beide landen am gleichen API-Endpunkt `/v1/games/{game}/mods/{modID}`, aber mit verschiedenen Response-Handlern. Persistierung ueber meta.ini mit Dirty-Flag. Robuste Fehlerbehandlung mit Rate-Limiting und Timeout.
