# Agent 1: MO2 Dateiname-Parsing Analyse
Datum: 2026-03-02

## Kern-Funktion: `NexusInterface::interpretNexusFileName()`

**Datei:** `/home/mob/Projekte/mo2-referenz/src/nexusinterface.cpp` (Zeile 328-393)
**Header:** `/home/mob/Projekte/mo2-referenz/src/nexusinterface.h` (Zeile 522-529)

### Signatur

```cpp
static void interpretNexusFileName(const QString& fileName, QString& modName,
                                   int& modID, bool query);
```

### Parameter
- `fileName` -- der Dateiname (NUR Dateiname, nicht der volle Pfad)
- `modName` -- Output: extrahierter Mod-Name
- `modID` -- Output: extrahierte Nexus-Mod-ID (oder -1 wenn nicht gefunden)
- `query` -- wenn `true`, wird bei Misserfolg ein Dialog angezeigt

## Gefundene Regex-Patterns

### Complex Regex (Haupt-Pattern)

```regex
^([a-zA-Z0-9_'"\-.() ]*?)([-_ ][VvRr]+[0-9]+(?:(?:[\.][0-9]+){0,2}|(?:[_][0-9]+){0,2}|(?:[-.][0-9]+){0,2})?[ab]?)??-([1-9][0-9]+)?-.*?\.(zip|rar|7z)
```

**Gruppen-Erklaerung:**
| Gruppe | Inhalt | Beispiel |
|--------|--------|----------|
| Gruppe 1 | Mod-Name | `infrab Nipple Shapes - Eve` |
| Gruppe 2 | Optionale Version (beginnt mit V/v/R/r) | `-V1.0.0` (meistens leer) |
| Gruppe 3 | **Nexus-Mod-ID** (umgeben von `-`) | `27881` |
| Gruppe 4 | Dateiendung | `zip`, `rar`, `7z` |

**Wichtige Design-Entscheidungen:**
- Die Mod-ID beginnt IMMER mit `[1-9]`, also mindestens zweistellig
- Die ID ist in Bindestriche eingerahmt: `-27881-`
- Der Rest nach der ID (`1-0-0-1772183732`) wird NICHT weiter geparst

### Simple Regex (Fallback)

```regex
^[^a-zA-Z]*([a-zA-Z_ ]+)
```

Wird nur verwendet wenn Complex-Pattern nicht matcht. Extrahiert nur den Mod-Namen, keine ID.

### Anwendungsbeispiel

Dateiname: `infrab Nipple Shapes - Eve-27881-1-0-0-1772183732.zip`

| Element | Wert |
|---------|------|
| Gruppe 1 (modName) | `infrab Nipple Shapes - Eve` |
| Gruppe 2 (version) | (leer) |
| Gruppe 3 (modID) | `27881` |
| Dateiendung | `zip` |

## Code-Stellen: Wo wird das Parsing aufgerufen?

### 1. Download Manager -- `queryInfo()` (primaerer Aufruf)

**Datei:** `downloadmanager.cpp` (Zeile 1068-1131)

```cpp
if (info->m_FileInfo->modID <= 0) {
    QString fileName = getFileName(index);
    QString ignore;
    NexusInterface::interpretNexusFileName(fileName, ignore, info->m_FileInfo->modID,
                                           info->m_AskIfNotFound);
    if (info->m_FileInfo->modID < 0) {
        bool ok = false;
        int modId = QInputDialog::getInt(nullptr, tr("Please enter the Nexus mod ID"),
                                         tr("Mod ID:"), 1, 1, INT_MAX, 1, &ok);
        if (ok)
            m_ActiveDownloads[index]->m_FileInfo->modID = modId;
        return;
    }
}
```

### 2. Installation Manager -- `install()` (sekundaerer Aufruf)

**Datei:** `installationmanager.cpp` (Zeile 699-711)

```cpp
{  // guess the mod name and mod if from the file name
    QString guessedModName;
    int guessedModID = modID;
    NexusInterface::interpretNexusFileName(QFileInfo(fileName).fileName(),
                                           guessedModName, guessedModID, false);
    if ((modID == 0) && (guessedModID != -1)) {
        modID = guessedModID;
    }
    modName.update(guessedModName, GUESS_GOOD);
}
```

## Gesamter Workflow: Dateiname bis Nexus-API

```
Dateiname (z.B. "infrab Nipple Shapes - Eve-27881-1-0-0-1772183732.zip")
    |
    v
interpretNexusFileName()
    |-- Complex Regex matched? --> modName, modID
    |-- Nicht matched? --> Simple Regex --> nur modName
    |-- query=true? --> Dialog: User waehlt aus allen Zahlen
    |
    v
modID bekannt?
    |-- Ja --> requestDescription() --> Nexus API
    |-- Nein --> QInputDialog fuer manuelle Eingabe
```

## Was wird NICHT aus dem Dateinamen extrahiert?

| Information | Extrahiert? | Quelle |
|-------------|-------------|--------|
| Mod-Name | Ja (Gruppe 1) | Regex |
| Nexus-Mod-ID | Ja (Gruppe 3) | Regex |
| Version | Teilweise (Gruppe 2, selten) | Meist API |
| File-ID | **NEIN** | NXM-Link oder API |
| Game-Name | **NEIN** | NXM-Link oder User-Auswahl |

## Beteiligte Klassen

| Klasse | Methode | Rolle |
|--------|---------|-------|
| `NexusInterface` | `interpretNexusFileName()` | Regex-Parsing |
| `DownloadManager` | `queryInfo()` | Trigger: Parsing + API |
| `DownloadManager` | `queryInfoMd5()` | Alternative: MD5-Suche |
| `InstallationManager` | `install()` | Sekundaer: Parsing bei Install |

## Python-Equivalent fuer Anvil

```python
import re

NEXUS_FILENAME_PATTERN = re.compile(
    r'^([a-zA-Z0-9_\'".\-() ]*?)'
    r'(?:[-_ ][VvRr]+[0-9]+(?:(?:[.][0-9]+){0,2}|(?:[_][0-9]+){0,2}|(?:[-][0-9]+){0,2})?[ab]?)??'
    r'-([1-9][0-9]+)?'
    r'-.*?'
    r'\.(zip|rar|7z)$'
)

def extract_nexus_id(filename: str) -> tuple[str | None, int | None]:
    m = NEXUS_FILENAME_PATTERN.match(filename)
    if m:
        mod_name = m.group(1).strip() if m.group(1) else None
        mod_id = int(m.group(2)) if m.group(2) else None
        return mod_name, mod_id
    return None, None
```

## Zusammenfassung

MO2 verwendet einen einzigen statischen Regex in `interpretNexusFileName()`. Das Pattern extrahiert Mod-Name (Gruppe 1) und Nexus-ID (Gruppe 3, mind. 2-stellig, zwischen Bindestrichen). File-ID wird NICHT aus dem Dateinamen extrahiert. Fallback-Kette: Regex -> SelectionDialog -> QInputDialog -> MD5-Suche.
