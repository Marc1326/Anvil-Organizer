# Feature: F4SE Proton Shim — DLL-Proxy für F4SE Next-Gen unter Linux/Wine/Proton

## Zusammenfassung

Ein eigenständiges C-Projekt das eine `version.dll` (DLL-Proxy/Shim) baut, die F4SE Next-Gen (0.7.7) unter Wine/Proton zum Laufen bringt. Das Tool wird als separates Projekt auf NexusMods und GitHub veröffentlicht — NICHT in Anvil Organizer eingebaut.

## Problem

F4SE Next-Gen (0.7.7, für Fallout 4 v1.11.191) funktioniert nicht unter Linux/Proton/Wine:

- `f4se_loader.exe` nutzt **CreateRemoteThread + LoadLibraryA Injection** (siehe `f4se_loader_common/Inject.cpp`)
- Wine/Proton unterstützt diese Remote-Thread-Injection nicht zuverlässig
- Die alte F4SE (0.6.x) hatte `f4se_steam_loader.dll` — eine DLL die sich als Wine DLL-Override laden ließ und F4SE per `LoadLibrary()` direkt im Prozess lud. **Diese DLL existiert in Next-Gen nicht mehr als Binary.**
- Aktuell gibt es KEIN Tool/Mod das dieses Problem löst — alle Linux-Spieler downgraden auf 1.10.163

## Lösung

Eine **version.dll Proxy-DLL** die:

1. Als Wine DLL-Override geladen wird (`WINEDLLOVERRIDES="version=n,b"`)
2. Alle Exports der echten Windows `version.dll` an die Original-DLL weiterleitet (Proxy-Pattern)
3. Bei `DLL_PROCESS_ATTACH` die F4SE-DLL (`f4se_1_11_191.dll`) per `LoadLibrary()` in den Prozess lädt
4. Dabei das richtige Timing sicherstellt (nicht zu früh, F4SE braucht initialisierte Strukturen)

## Technische Referenz — F4SE Quellcode

Der komplette F4SE 0.7.7 Quellcode liegt in:
`/home/mob/Projekte/f4se_0_07_07/src/f4se-0.7.7/`

### Schlüsseldateien:

**`f4se_steam_loader/main.cpp`** — BLAUPAUSE für unseren Shim:
- Wird als DLL geladen (`DLL_PROCESS_ATTACH` → `OnAttach()`)
- Hookt IAT-Funktion `__crtGetShowWindowMode` aus `MSVCR110.dll` als Timing-Trigger
- Wenn Hook feuert → `HookMain()` → `IdentifyEXE()` → baut DLL-Pfad → `LoadLibrary(f4se_X_XX_XXX.dll)`
- **PROBLEM:** Next-Gen nutzt UCRT statt MSVCR110 → der IAT-Hook-Punkt existiert nicht mehr
- **LÖSUNG:** Anderen IAT-Hook-Punkt finden oder alternativen Timing-Mechanismus

**`f4se_loader_common/Inject.cpp`** — Das was unter Wine SCHEITERT:
- `CreateProcess(suspended)` → `VirtualAllocEx` → `WriteProcessMemory` → `CreateRemoteThread`
- Schreibt x64-Shellcode in Zielprozess der `LoadLibraryA` + `GetProcAddress` aufruft
- Wine kann `CreateRemoteThread` nicht zuverlässig → DLL wird nie geladen

**`f4se_loader/main.cpp`** — Der Loader:
- Identifiziert EXE-Version, baut DLL-Pfad, ruft `InjectDLLThread()` auf
- Startet Fallout4.exe suspended, injiziert, resumet

**`f4se/f4se.cpp`** — Die eigentliche F4SE-DLL:
- Wird per `LoadLibrary` geladen → `DllMain` → `F4SECore_Initialize`
- Muss analysiert werden um zu verstehen welche Init-Reihenfolge nötig ist

**`f4se_common/BranchTrampoline.cpp`** — Memory-Allocation:
- Alloziert Trampolines VOR der exe image base
- hdmap/wine-hackery Patches fixen dies für Wine (bereits in GE-Proton integriert)

### version.dll Proxy-Pattern:

```c
// Pseudo-Code
#include <windows.h>

// Echte version.dll laden und alle Exports forwarden
HMODULE hOriginal = NULL;

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpReserved) {
    if (fdwReason == DLL_PROCESS_ATTACH) {
        // 1. Original version.dll aus system32 laden
        char path[MAX_PATH];
        GetSystemDirectory(path, MAX_PATH);
        strcat(path, "\\version.dll");
        hOriginal = LoadLibrary(path);
        
        // 2. F4SE DLL laden (Timing beachten!)
        // Entweder direkt hier oder verzögert über IAT-Hook/Thread
        LoadLibrary("f4se_1_11_191.dll");
    }
    return TRUE;
}

// Alle version.dll Exports als Forwards:
// GetFileVersionInfoA, GetFileVersionInfoW, GetFileVersionInfoSizeA, etc.
```

## Projektstruktur (Vorschlag)

```
f4se-proton-shim/
├── CMakeLists.txt          # Cross-compile mit MinGW für Windows x64
├── README.md               # Installationsanleitung
├── LICENSE                  # MIT oder passend zu F4SE
├── src/
│   ├── main.c              # DllMain + F4SE Loading-Logik
│   ├── proxy.c             # version.dll Export-Forwarding
│   ├── proxy.h
│   ├── timing.c            # IAT-Hook oder alternativer Timing-Mechanismus
│   └── timing.h
├── exports.def             # version.dll Export-Definitionen
├── build/                  # Build-Output
└── dist/                   # Release-Dateien für NexusMods
```

## Build-Anforderungen

- **Cross-Compilation unter Linux** mit MinGW-w64 (`x86_64-w64-mingw32-gcc`)
- Output: `version.dll` (Windows x64 DLL)
- Kein Visual Studio nötig — muss unter Linux baubar sein!

## Installation für Enduser

1. `version.dll` in den Fallout 4-Ordner kopieren (neben `Fallout4.exe`)
2. `f4se_1_11_191.dll` + `f4se_loader.exe` + `Data/` aus F4SE 0.7.7 wie gewohnt installieren
3. Steam Launch-Optionen: `WINEDLLOVERRIDES="version=n,b" %command%`
4. Spiel über Steam starten (NICHT über f4se_loader.exe!)
5. F4SE-Version im Hauptmenü prüfen

## Akzeptanz-Kriterien (Grundlage)

- version.dll wird unter Wine/Proton geladen wenn WINEDLLOVERRIDES gesetzt ist
- Alle version.dll Exports funktionieren (Spiel crasht nicht wegen fehlender Funktionen)
- f4se_1_11_191.dll wird erfolgreich geladen (LoadLibrary Rückgabe != NULL)
- F4SE initialisiert sich korrekt (Versionstext im Hauptmenü sichtbar)
- F4SE-Plugins in Data/F4SE/Plugins/ werden geladen
- Spiel läuft stabil (kein Crash beim Laden, Spielen, Speichern)
- Build funktioniert unter Linux mit MinGW-w64
- Projekt ist eigenständig (keine Abhängigkeit zu Anvil Organizer)

## Wichtige Hinweise

- Der F4SE-Quellcode darf nur als REFERENZ verwendet werden — wir nutzen NICHT den F4SE-Code direkt
- Unsere DLL ist ein reiner Proxy/Loader — das Reverse Engineering macht F4SE selbst
- Lizenz muss F4SE-kompatibel sein (F4SE verbietet Redistribution, wir laden nur deren DLL)
- GE-Proton enthält bereits die wine-hackery Memory-Patches für Trampolines
- UCRT (Universal C Runtime) statt MSVCR110 in Next-Gen — IAT-Hook muss angepasst werden!
