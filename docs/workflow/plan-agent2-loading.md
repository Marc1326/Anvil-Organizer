# Plan Agent 2: F4SE Loading & Timing

## 1. Analyse der Blaupause (f4se_steam_loader/main.cpp)

### Alter Mechanismus (F4SE 0.6.x / Pre-Next-Gen):
```
DLL_PROCESS_ATTACH
  -> OnAttach()
    -> HookIAT()
      -> GetIATAddr(exe, "MSVCR110.dll", "__crtGetShowWindowMode")
      -> SafeWrite64(iat, Hook)
    
Spaeter, wenn Fallout4.exe __crtGetShowWindowMode aufruft:
  -> __crtGetShowWindowMode_Hook()
    -> HookMain()
      -> IdentifyEXE()
      -> LoadLibrary("f4se_1_10_163.dll")
```

### Problem fuer Next-Gen:
- Fallout 4 Next-Gen (v1.11.191) nutzt **UCRT** (Universal C Runtime) statt MSVCR110
- `MSVCR110.dll` wird NICHT mehr importiert
- Der IAT-Eintrag `__crtGetShowWindowMode` existiert NICHT
- Der gesamte IAT-Hook-Ansatz des alten steam_loader ist NICHT uebertragbar

## 2. Analyse von f4se.cpp — Die entscheidende Datei

### DllMain (DLL_PROCESS_ATTACH):
```cpp
case DLL_PROCESS_ATTACH:
    g_moduleHandle = (void *)hDllHandle;
    break;
```
**Erkenntnis:** DllMain speichert NUR den Module-Handle. KEINE Initialisierung findet statt.

### StartF4SE() — DER ENTSCHEIDENDE EXPORT:
```cpp
extern "C" {
    void StartF4SE(void)
    {
        InstallBaseHooks();
    }
}
```
- Exportiert als `extern "C"` — aufrufbar via GetProcAddress
- Im Original-Loader: Aufgerufen via Shellcode mit `GetProcAddress(hModule, 1)` (Ordinal 1)
- **MUSS von unserem Shim explizit aufgerufen werden!**
- `LoadLibrary` alleine reicht NICHT — ohne `StartF4SE()` passiert nichts!

### InstallBaseHooks() — Was StartF4SE tut:
```cpp
void InstallBaseHooks()
{
    // Oeffnet Log-Datei
    gLog.OpenRelative(CSIDL_MYDOCUMENTS, "\\My Games\\Fallout4\\F4SE\\f4se.log");
    
    // Hookt IAT der EXE:
    // api-ms-win-crt-runtime-l1-1-0.dll::_initterm_e -> F4SE_Preinit()
    // api-ms-win-crt-runtime-l1-1-0.dll::_get_narrow_winmain_command_line -> F4SE_Initialize()
    
    auto * initterm = GetIATAddr(exe, "api-ms-win-crt-runtime-l1-1-0.dll", "_initterm_e");
    auto * cmdline = GetIATAddr(exe, "api-ms-win-crt-runtime-l1-1-0.dll", 
                                "_get_narrow_winmain_command_line");
    
    // Schreibt Hook-Funktionen in die IAT
    SafeWrite64(initterm, __initterm_e_Hook);
    SafeWrite64(cmdline, __get_narrow_winmain_command_line_Hook);
}
```

### Timing-Kette (was F4SE intern macht):
```
1. _initterm_e wird aufgerufen (VOR globalen Initialisierern)
   -> F4SE_Preinit()
      -> BranchTrampoline erstellen
      -> Plugin-Preload
      
2. _get_narrow_winmain_command_line wird aufgerufen (NACH globalen Initialisierern)
   -> F4SE_Initialize()
      -> Alle Hooks installieren (ObScript, Papyrus, Scaleform, etc.)
      -> Plugins laden
      -> Hooks committen
```

## 3. Timing-Analyse: Wann kann LoadLibrary + StartF4SE aufgerufen werden?

### Anforderung:
- `LoadLibrary("f4se_1_11_191.dll")` muss die DLL laden
- `StartF4SE()` muss aufgerufen werden
- StartF4SE hookt `_initterm_e` und `_get_narrow_winmain_command_line` in der IAT
- Diese Hooks muessen gesetzt sein BEVOR die EXE sie aufruft
- `_initterm_e` wird SEHR FRUEH aufgerufen (CRT-Initialisierung)

### Kritische Frage: Funktioniert LoadLibrary in DLL_PROCESS_ATTACH?

**JA, mit Einschraenkungen:**
- `LoadLibrary` innerhalb `DLL_PROCESS_ATTACH` ist offiziell von Microsoft als "gefaehrlich" eingestuft wegen Loader-Lock
- ABER: In der Praxis funktioniert es zuverlaessig, solange die geladene DLL keine komplexe DllMain hat
- `f4se_1_11_191.dll` hat eine TRIVIALE DllMain (speichert nur `g_moduleHandle`)
- **FAZIT: LoadLibrary ist sicher fuer f4se_1_11_191.dll**

### Kritische Frage: Funktioniert StartF4SE in DLL_PROCESS_ATTACH?

**JA:**
- `StartF4SE()` ruft `InstallBaseHooks()` auf
- `InstallBaseHooks()` oeffnet eine Log-Datei und schreibt IAT-Eintraege
- Log-Datei: `SHGetFolderPath` + `CreateFile` — funktioniert waehrend Loader-Lock
- IAT-Schreiben: `VirtualProtect` + direkte Speicherschreibzugriffe — funktioniert waehrend Loader-Lock
- `GetModuleHandle(NULL)` — funktioniert waehrend Loader-Lock
- **FAZIT: StartF4SE ist sicher waehrend DLL_PROCESS_ATTACH**

### Entscheidende Erkenntnis: REIHENFOLGE

Die DLL-Ladereihenfolge bei einem Prozessstart:
```
1. Kernel32.dll + ntdll.dll laden
2. Import-DLLs laden (laut PE Import Table der EXE)
   - version.dll wird hier geladen (falls von EXE importiert)
   - UCRT-DLLs werden hier geladen
3. EXE-Einstiegspunkt (mainCRTStartup) wird aufgerufen
4. _initterm_e wird aufgerufen (CRT init)
5. _get_narrow_winmain_command_line wird aufgerufen
6. WinMain wird aufgerufen
```

**WICHTIG:** Fallout 4 importiert `version.dll` direkt (fuer GetFileVersionInfo). Unsere Proxy-DLL wird also in Schritt 2 geladen — VOR `_initterm_e`.

Das heisst: Wenn wir in unserem `DLL_PROCESS_ATTACH`:
1. F4SE-DLL laden (`LoadLibrary`)
2. `StartF4SE()` aufrufen (hookt `_initterm_e` und `_get_narrow_winmain_command_line`)

...dann sind die IAT-Hooks gesetzt BEVOR die EXE `_initterm_e` aufruft. **Das Timing ist perfekt!**

## 4. Gewahlter Loading-Mechanismus: DIREKT in DLL_PROCESS_ATTACH

### Begruendung:
- Kein IAT-Hook noetig (wir SIND frueher als _initterm_e)
- Kein separater Thread noetig (vermeidet Race Conditions)
- Kein Timer/Polling noetig
- Einfachste und zuverlaessigste Loesung
- Der alte steam_loader brauchte einen IAT-Hook weil er als DLL-Override einer ANDEREN DLL geladen wurde und sicherstellen musste, dass die EXE bereits gemapped war. Wir laden als version.dll — die EXE ist garantiert bereits gemapped.

### Implementierung:
```c
// main.c — F4SE Loading in DLL_PROCESS_ATTACH

#include <windows.h>

typedef void (*StartF4SE_t)(void);

static HMODULE g_f4seModule = NULL;

BOOL load_f4se(void) {
    // F4SE DLL Name — hardcoded fuer Next-Gen v1.11.191
    const char* f4seDllName = "f4se_1_11_191.dll";
    
    // F4SE DLL laden
    g_f4seModule = LoadLibraryA(f4seDllName);
    if (!g_f4seModule) {
        // Log schreiben — F4SE DLL nicht gefunden
        // Kein Crash — Spiel laeuft ohne F4SE weiter
        return FALSE;
    }
    
    // StartF4SE aufrufen — DAS ist der entscheidende Schritt!
    StartF4SE_t pfnStartF4SE = (StartF4SE_t)GetProcAddress(g_f4seModule, "StartF4SE");
    if (!pfnStartF4SE) {
        // Fallback: Ordinal 1
        pfnStartF4SE = (StartF4SE_t)GetProcAddress(g_f4seModule, (LPCSTR)1);
    }
    
    if (pfnStartF4SE) {
        pfnStartF4SE();
        return TRUE;
    }
    
    return FALSE;
}
```

## 5. Warum KEIN IAT-Hook noetig ist

Der alte `f4se_steam_loader` brauchte einen IAT-Hook aus einem spezifischen Grund:
- Er wurde als `winmm.dll`-Override oder aehnliche System-DLL geladen
- Er musste WARTEN bis die EXE fertig geladen war
- `__crtGetShowWindowMode` war ein spaeter Aufruf der als Trigger diente

**Unser Fall ist anders:**
- Wir sind `version.dll` — eine DLL die von der EXE direkt importiert wird
- Unser `DLL_PROCESS_ATTACH` laeuft waehrend der Import-Resolution der EXE
- Die IAT der EXE existiert und ist beschreibbar
- `_initterm_e` wurde noch NICHT aufgerufen
- F4SE's `InstallBaseHooks()` kann die IAT-Eintraege direkt patchen

## 6. Fallback-Strategien

### Falls DLL_PROCESS_ATTACH zu frueh ist (unwahrscheinlich):

**Fallback A: Thread-basiertes Laden**
```c
DWORD WINAPI LoadF4SEThread(LPVOID param) {
    // Kurz warten bis EXE-Initialisierung weiter ist
    Sleep(0);  // Yield, kein echtes Warten
    load_f4se();
    return 0;
}

// In DLL_PROCESS_ATTACH:
CreateThread(NULL, 0, LoadF4SEThread, NULL, 0, NULL);
```
PROBLEM: Race Condition — Thread koennte zu spaet sein fuer _initterm_e-Hook.

**Fallback B: IAT-Hook auf UCRT-Funktion**
```c
// Hookt eine fruehe UCRT-Funktion als Trigger
// Kandidaten:
// - api-ms-win-crt-runtime-l1-1-0.dll::_initterm_e (ZU SPAET — das ist was F4SE selbst hookt)
// - api-ms-win-crt-runtime-l1-1-0.dll::_initialize_onexit_table (FRUEHER)
// - api-ms-win-crt-heap-l1-1-0.dll::malloc (SEHR FRUEH, aber hochfrequent)
```
Empfehlung: Fallback B nur implementieren wenn Tests zeigen dass DLL_PROCESS_ATTACH nicht funktioniert.

### Falls Fallout 4 version.dll NICHT importiert:

- Unwahrscheinlich, da `GetFileVersionInfo*` fuer Version-Checks gebraucht wird
- Falls doch: Alternative Proxy-DLL waehlen (z.B. `winmm.dll`, `dinput8.dll`)
- Muss zur Laufzeit getestet werden

## 7. Wine/Proton-spezifische Ueberlegungen

### Loader-Lock unter Wine:
- Wine implementiert den Loader-Lock anders als Windows
- `LoadLibrary` innerhalb `DLL_PROCESS_ATTACH` funktioniert unter Wine generell besser als unter Windows
- Wine hat weniger strikte Loader-Lock-Restriktionen
- **Kein Problem erwartet**

### IAT-Patching unter Wine:
- Wine's PE-Loader erstellt eine vollstaendige IAT
- `GetIATAddr()` (F4SE's Funktion) funktioniert identisch
- `VirtualProtect` + `SafeWrite64` funktionieren unter Wine
- **Kein Problem erwartet**

### GetProcAddress unter Wine:
- Funktioniert identisch fuer native PE-DLLs
- `GetProcAddress(hModule, "StartF4SE")` — kein Problem
- `GetProcAddress(hModule, (LPCSTR)1)` (Ordinal) — funktioniert unter Wine
- **Kein Problem erwartet**

### BranchTrampoline unter Wine:
- Dies ist ein BEKANNTES Problem das aber bereits geloest ist
- GE-Proton (7.x+) enthaelt wine-hackery/hdmap Patches
- Diese Patches erlauben VirtualAlloc in der naehen Region der EXE
- **Keine Aktion unsererseits noetig — F4SE handhabt das intern**

## 8. Verifizierung dass version.dll von Fallout 4 importiert wird

Dies muss vor der Implementierung verifiziert werden:
```bash
# Auf dem System mit Fallout 4 installiert:
# (unter Wine/Proton oder mit PE-Tools unter Linux)
x86_64-w64-mingw32-objdump -p Fallout4.exe | grep -i "DLL Name"

# Oder mit Python:
# python3 -c "import pefile; pe = pefile.PE('Fallout4.exe'); [print(e.dll) for e in pe.DIRECTORY_ENTRY_IMPORT]"
```

Falls `version.dll` NICHT importiert wird, muessen wir auf eine andere DLL ausweichen. Kandidaten:
- `winmm.dll` (wird fast immer importiert)
- `dinput8.dll` (wird von Spielen oft importiert)

## 9. Zusammenfassung

| Aspekt | Entscheidung |
|---|---|
| Loading-Zeitpunkt | DLL_PROCESS_ATTACH (direkt) |
| LoadLibrary-Aufruf | Direkt in DLL_PROCESS_ATTACH |
| StartF4SE-Aufruf | Direkt nach LoadLibrary, per GetProcAddress |
| IAT-Hook noetig? | NEIN — wir sind frueh genug |
| Thread noetig? | NEIN — synchroner Aufruf |
| Fallback | Thread-basiert oder UCRT-IAT-Hook |
| Wine-Kompatibilitaet | Keine Probleme erwartet |
| Risiko | NIEDRIG — der Ansatz ist einfacher als der alte steam_loader |
