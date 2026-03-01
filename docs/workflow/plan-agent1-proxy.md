# Plan Agent 1: version.dll Proxy-Exports

## 1. Was exportiert version.dll?

Die Windows `version.dll` (aus `C:\Windows\System32\`) exportiert genau **17 Funktionen**. Diese sind seit Windows Vista stabil und aendern sich nicht zwischen Windows-Versionen:

| # | Funktionsname | Ordinal |
|---|---|---|
| 1 | GetFileVersionInfoA | 1 |
| 2 | GetFileVersionInfoByHandle | 2 |
| 3 | GetFileVersionInfoExA | 3 |
| 4 | GetFileVersionInfoExW | 4 |
| 5 | GetFileVersionInfoSizeA | 5 |
| 6 | GetFileVersionInfoSizeExA | 6 |
| 7 | GetFileVersionInfoSizeExW | 7 |
| 8 | GetFileVersionInfoSizeW | 8 |
| 9 | GetFileVersionInfoW | 9 |
| 10 | VerFindFileA | 10 |
| 11 | VerFindFileW | 11 |
| 12 | VerInstallFileA | 12 |
| 13 | VerInstallFileW | 13 |
| 14 | VerLanguageNameA | 14 |
| 15 | VerLanguageNameW | 15 |
| 16 | VerQueryValueA | 16 |
| 17 | VerQueryValueW | 17 |

**Wichtig:** `GetFileVersionInfoByHandle` ist undokumentiert, existiert aber als Export. Muss ebenfalls weitergeleitet werden.

## 2. Export-Forwarding-Pattern

### Gewahlter Ansatz: GetProcAddress-Wrapper (Runtime Forwarding)

Wir verwenden **Runtime-Forwarding via GetProcAddress** statt `.def`-Forwarding. Gruende:

- `.def`-Forwarding (`EXPORTS GetFileVersionInfoA = C:\Windows\System32\version.GetFileVersionInfoA`) funktioniert NICHT zuverlaessig unter Wine/Proton, weil absolute Pfade im Forwarding problematisch sind
- Runtime-Forwarding ist flexibler und funktioniert identisch unter Windows und Wine

### Implementierung

```c
// proxy.c — Runtime Export Forwarding

#include <windows.h>

static HMODULE hOriginalDLL = NULL;

// Funktionszeiger fuer alle 17 Exports
typedef void (*FARPROC_GENERIC)();

static FARPROC_GENERIC pGetFileVersionInfoA = NULL;
static FARPROC_GENERIC pGetFileVersionInfoByHandle = NULL;
static FARPROC_GENERIC pGetFileVersionInfoExA = NULL;
static FARPROC_GENERIC pGetFileVersionInfoExW = NULL;
static FARPROC_GENERIC pGetFileVersionInfoSizeA = NULL;
static FARPROC_GENERIC pGetFileVersionInfoSizeExA = NULL;
static FARPROC_GENERIC pGetFileVersionInfoSizeExW = NULL;
static FARPROC_GENERIC pGetFileVersionInfoSizeW = NULL;
static FARPROC_GENERIC pGetFileVersionInfoW = NULL;
static FARPROC_GENERIC pVerFindFileA = NULL;
static FARPROC_GENERIC pVerFindFileW = NULL;
static FARPROC_GENERIC pVerInstallFileA = NULL;
static FARPROC_GENERIC pVerInstallFileW = NULL;
static FARPROC_GENERIC pVerLanguageNameA = NULL;
static FARPROC_GENERIC pVerLanguageNameW = NULL;
static FARPROC_GENERIC pVerQueryValueA = NULL;
static FARPROC_GENERIC pVerQueryValueW = NULL;

BOOL proxy_init(void) {
    char systemPath[MAX_PATH];
    GetSystemDirectoryA(systemPath, MAX_PATH);
    strcat(systemPath, "\\version.dll");
    
    hOriginalDLL = LoadLibraryA(systemPath);
    if (!hOriginalDLL) return FALSE;
    
    pGetFileVersionInfoA = (FARPROC_GENERIC)GetProcAddress(hOriginalDLL, "GetFileVersionInfoA");
    pGetFileVersionInfoByHandle = (FARPROC_GENERIC)GetProcAddress(hOriginalDLL, "GetFileVersionInfoByHandle");
    // ... alle 17 analog
    
    return TRUE;
}

void proxy_cleanup(void) {
    if (hOriginalDLL) {
        FreeLibrary(hOriginalDLL);
        hOriginalDLL = NULL;
    }
}
```

### Export-Wrapper (Naked/Trampoline)

Jede exportierte Funktion wird als **Trampoline** implementiert die direkt zur Original-Funktion springt:

```c
// Fuer MinGW-w64: Wir verwenden __attribute__((naked)) NICHT, da das
// unter x86_64 MinGW nicht zuverlaessig funktioniert.
// Stattdessen: Einfache Wrapper-Funktionen mit variadischen Signaturen.

// Da version.dll Funktionen klare Signaturen haben, koennen wir
// typsichere Wrapper verwenden:

__declspec(dllexport) BOOL WINAPI GetFileVersionInfoA(
    LPCSTR lptstrFilename, DWORD dwHandle, DWORD dwLen, LPVOID lpData)
{
    typedef BOOL (WINAPI *fn_t)(LPCSTR, DWORD, DWORD, LPVOID);
    return ((fn_t)pGetFileVersionInfoA)(lptstrFilename, dwHandle, dwLen, lpData);
}
```

### .def Datei (fuer Export-Namen)

```def
; exports.def — Stellt sicher dass unsere DLL die richtigen Export-Namen hat
LIBRARY version
EXPORTS
    GetFileVersionInfoA
    GetFileVersionInfoByHandle
    GetFileVersionInfoExA
    GetFileVersionInfoExW
    GetFileVersionInfoSizeA
    GetFileVersionInfoSizeExA
    GetFileVersionInfoSizeExW
    GetFileVersionInfoSizeW
    GetFileVersionInfoW
    VerFindFileA
    VerFindFileW
    VerInstallFileA
    VerInstallFileW
    VerLanguageNameA
    VerLanguageNameW
    VerQueryValueA
    VerQueryValueW
```

## 3. Laden der Original-DLL

### Unter Wine/Proton:
- `GetSystemDirectoryA()` gibt `C:\windows\system32\` zurueck (Wine-Mapping)
- `LoadLibraryA("C:\\windows\\system32\\version.dll")` laedt die Wine-Builtin `version.dll`
- Da wir `WINEDLLOVERRIDES="version=n,b"` setzen, wird UNSERE DLL statt der Wine-Builtin geladen
- Die Original-DLL die wir per `GetSystemDirectory` laden ist also die Wine-Builtin

### Unter nativem Windows (Fallback-Kompatibilitaet):
- `GetSystemDirectoryA()` gibt `C:\Windows\System32\` zurueck
- Laedt die echte Windows version.dll
- Unser Shim funktioniert auch unter nativem Windows (nuetzlich zum Testen)

### Rekursions-Vermeidung:
- KRITISCH: Wenn wir `LoadLibrary("version.dll")` ohne vollen Pfad aufrufen, wuerde Windows/Wine UNSERE DLL erneut laden (Endlosrekursion!)
- LOESUNG: IMMER den vollen Pfad via `GetSystemDirectoryA()` verwenden
- Zusaetzliche Sicherheit: Wir setzen ein Flag `g_proxyInitialized` das Rekursion verhindert

## 4. Edge Cases

### Original-DLL nicht gefunden:
- `LoadLibraryA(systemPath)` gibt `NULL` zurueck
- Alle Proxy-Funktionszeiger bleiben `NULL`
- Wrapper-Funktionen pruefen auf `NULL` und geben Fehlerwert zurueck
- Log-Eintrag wird geschrieben
- Spiel wird wahrscheinlich crashen, da version.dll-Funktionen gebraucht werden
- Das ist akzeptabel — ohne Original-DLL ist das System defekt

### Wine-Builtin vs. Native:
- Unter Wine: Die Original-DLL ist eine Wine-Builtin-DLL
- Wine-Builtins haben spezielle DLL-Markierungen
- `LoadLibraryA` funktioniert trotzdem korrekt
- KEIN spezieller Code noetig

### DLL-Ladereihenfolge unter Wine:
- `WINEDLLOVERRIDES="version=n,b"` bedeutet: native zuerst, dann builtin
- "native" = unsere version.dll im Spielordner
- "builtin" = Wine's eigene version.dll (Fallback)
- Wenn unsere DLL geladen wird, laedt sie die builtin per GetSystemDirectory

### Thread-Sicherheit:
- `DLL_PROCESS_ATTACH` laeuft waehrend des Loader-Locks
- Nur ein Thread kann gleichzeitig in `DLL_PROCESS_ATTACH` sein
- Proxy-Init ist daher automatisch thread-safe
- ABER: LoadLibrary innerhalb DLL_PROCESS_ATTACH kann Deadlocks verursachen!
- LOESUNG: Siehe Agent 2 (Timing-Mechanismus)

## 5. Referenz-Projekte

Existierende version.dll Proxy-Projekte als Referenz:
- **dgVoodoo2**: Nutzt version.dll Proxy fuer DirectX-Wrapping
- **Ultimate ASI Loader**: Populaerer DLL-Proxy fuer verschiedene Game-DLLs
- **DXVK**: Nutzt aehnliches Pattern fuer d3d11.dll (nicht version.dll, aber gleiches Konzept)
- **Wine-Staging**: Hat DLL-Override-Mechanismus der unser Pattern unterstuetzt

## 6. Zusammenfassung der Entscheidungen

| Entscheidung | Wahl | Begruendung |
|---|---|---|
| Forwarding-Methode | Runtime (GetProcAddress) | Zuverlaessiger unter Wine |
| Original-DLL finden | GetSystemDirectoryA + Pfad | Vermeidet Rekursion |
| Export-Definitionen | .def Datei + typsichere Wrapper | Saubere API |
| Rekursionsschutz | Flag + voller Pfad | Doppelte Sicherheit |
| Anzahl Exports | 17 | Vollstaendig, alle version.dll Funktionen |
