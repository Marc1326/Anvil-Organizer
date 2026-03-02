# Agent 3: MO2 Downloads-Tab Kontextmenue
Datum: 2026-03-02

## 1. Architektur-Ueberblick

| Klasse | Datei | Verantwortung |
|--------|-------|---------------|
| `DownloadsTab` | downloadstab.cpp/.h | Tab-Controller |
| `DownloadListView` | downloadlistview.cpp/.h | QTreeView: Kontextmenue, Keyboard |
| `DownloadList` | downloadlist.cpp/.h | QAbstractTableModel: Daten, Spalten, Tooltips |
| `DownloadManager` | downloadmanager.cpp/.h | Backend: States, API, Meta-Dateien |

## 2. Kontextmenu-Eintraege (nach State)

### STATE_READY / STATE_INSTALLED / STATE_UNINSTALLED

**Wenn `isInfoIncomplete(row)` == true:**
```
Install
Query Info              <- ruft issueQueryInfoMd5(row) auf
Open File
Open Meta File
Reveal in Explorer
---
Delete...
Hide / Un-Hide
```

**Wenn `isInfoIncomplete(row)` == false:**
```
Install
Visit on Nexus          <- oeffnet Browser
Visit the uploader's profile
Open File
Open Meta File
Reveal in Explorer
---
Delete...
Hide / Un-Hide
```

**WICHTIG:** "Query Info" und "Visit on Nexus" sind **gegenseitig exklusiv**.

### STATE_DOWNLOADING
```
Cancel
Pause
Reveal in Explorer
```

### STATE_PAUSED / STATE_ERROR
```
Delete...
Resume
Reveal in Explorer
```

### Globale Aktionen (nach Separator)
```
Delete Installed Downloads...
Delete Uninstalled Downloads...
Delete All Downloads...
---
Hide Installed / Uninstalled / All
Un-Hide All
```

## 3. Tooltip / Info-Anzeige

### Wenn Infos unvollstaendig:
```
[Dateiname]
Information missing, please select "Query Info" from the context menu to re-retrieve.
```

### Wenn Infos vollstaendig:
```
ModName (ID modID) version
<span>description (max 4096 Zeichen)</span>
```

### Warning-Icon
`isInfoIncomplete == true` UND state >= STATE_READY:
- `Qt::DecorationRole` liefert `QIcon(":/MO/gui/warning_16")` in COL_NAME

## 4. Download-Metadaten (Spalten)

| Spalte | Enum | Standard sichtbar |
|--------|------|-------------------|
| Name | COL_NAME (0) | Ja |
| Status | COL_STATUS (1) | Ja |
| Size | COL_SIZE (2) | Ja |
| Filetime | COL_FILETIME (3) | Ja |
| Mod name | COL_MODNAME (4) | **Nein** |
| Version | COL_VERSION (5) | **Nein** |
| Nexus ID | COL_ID (6) | **Nein** |
| Source Game | COL_SOURCEGAME (7) | **Nein** |

### Status-Farben
| State | Farbe |
|-------|-------|
| STATE_READY | `Qt::darkGreen` |
| STATE_UNINSTALLED | `Qt::darkYellow` |
| STATE_PAUSED | `Qt::darkRed` |
| Pending | `Qt::darkBlue` |

### Status-Texte
| State | Text |
|-------|------|
| STATE_FETCHINGMODINFO | "Fetching Info" |
| STATE_FETCHINGFILEINFO | "Fetching Info" |
| STATE_READY | "Downloaded" |
| STATE_INSTALLED | "Installed" |
| STATE_UNINSTALLED | "Uninstalled" |

## 5. Query-Info-Mechanismus

### Zwei Query-Methoden

**queryInfo(index)** -- Klassisch ueber Mod-ID:
1. modID <= 0? -> Dateinamen-Parsing
2. Fehlgeschlagen? -> QInputDialog
3. STATE_FETCHINGMODINFO -> requestDescription()
4. Response -> nxmDescriptionAvailable()
5. Wenn fileID unbekannt: STATE_FETCHINGFILEINFO -> requestFiles()

**queryInfoMd5(index)** -- MD5-basiert (bevorzugt):
1. MD5-Hash berechnen
2. STATE_FETCHINGMODINFO_MD5 -> requestInfoFromMd5()
3. Eindeutiger Treffer -> alle Felder setzen
4. Kein Match -> Fallback auf queryInfo()

### isInfoIncomplete()
```cpp
bool DownloadManager::isInfoIncomplete(int index) const {
    return (info->m_FileInfo->fileID == 0) || (info->m_FileInfo->modID == 0);
}
```

## 6. Signal-Flow

```
[Kontextmenue "Query Info"]
    |
    v
DownloadListView::issueQueryInfoMd5(row)
    |
    v (emit queryInfoMd5)
DownloadsTab (Signal-Routing)
    |
    v
DownloadManager::queryInfoMd5(index)
    |
    +-- MD5-Hash berechnen
    +-- STATE_FETCHINGMODINFO_MD5
    |     |
    |     v
    |   NexusInterface::requestInfoFromMd5()
    |     |
    |     v (API Response)
    |   nxmFileInfoFromMd5Available()
    |     |
    |     +-- Match -> STATE_READY -> createMetaFile()
    |     +-- Kein Match -> queryInfo() [Fallback]
    v
DownloadList::update(row) -> dataChanged -> UI refresh
```

## 7. Meta-Datei-System

Pro Download eine `.meta`-Datei (QSettings/INI-Format):
```ini
[General]
gameName=skyrimspecialedition
modID=3863
fileID=1000172397
name=SkyUI
modName=SkyUI
version=5.2SE
category=42
repository=Nexus
author=schlangster
installed=true
```

## 8. Zusammenfassung

### Kontextmenu-Design:
1. **State-basiert:** Komplett unterschiedlich je nach Download-State
2. **Info-basiert:** `isInfoIncomplete()` bestimmt ob "Query Info" oder "Visit Nexus"
3. **Hierarchisch:** Download-spezifisch -> Separator -> Bulk-Aktionen

### Query-Info-Design:
1. **MD5 bevorzugt:** Praeziser als Dateinamen-Matching
2. **Mehrstufiger Fallback:** MD5 -> Dateinamen -> manuelle Eingabe
3. **State-Machine:** READY -> FETCHINGMODINFO_MD5 -> READY

### Tooltip-Design:
1. **Zwei Modi:** Unvollstaendig -> "Query Info", Vollstaendig -> Mod-Details
2. **Warning-Icon:** Gelbes Dreieck bei fehlenden Infos
3. **HTML-Tooltip:** modName (ID) version + description
