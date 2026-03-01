# QA Report — Agent 2: F4SE Loading & Timing Domain
Datum: 2026-02-28

## Projekt
F4SE Proton Shim (`/home/mob/Projekte/f4se-proton-shim/`)

## Gepruefte Dateien
- `/home/mob/Projekte/f4se-proton-shim/src/main.c` (79 Zeilen)
- `/home/mob/Projekte/f4se-proton-shim/src/proxy.c` (285 Zeilen)
- `/home/mob/Projekte/f4se-proton-shim/src/proxy.h` (12 Zeilen)
- `/home/mob/Projekte/f4se-proton-shim/src/logging.c` (61 Zeilen)
- `/home/mob/Projekte/f4se-proton-shim/src/logging.h` (8 Zeilen)
- `/home/mob/Projekte/f4se-proton-shim/exports.def` (20 Zeilen)

## Referenz
- `/home/mob/Projekte/f4se_0_07_07/src/f4se-0.7.7/f4se/f4se.cpp` (F4SE 0.7.7 Quellcode)
- `/home/mob/Projekte/f4se_0_07_07/src/f4se-0.7.7/f4se/exports.def` (F4SE Export-Definition)

---

## Checklisten-Pruefung

### [x] Kriterium 7: LoadLibrary fuer f4se_1_11_191.dll -- PASS

**Code** (`main.c:30-36`):
```c
hF4SE = LoadLibraryA("f4se_1_11_191.dll");
if (!hF4SE) {
    shim_log("WARN: f4se_1_11_191.dll not found (error %lu) ...", GetLastError());
    return;
}
shim_log("f4se dll loaded successfully at %p", (void *)hF4SE);
```

**Befund:**
- DLL-Name `f4se_1_11_191.dll` ist korrekt (Next-Gen F4SE fuer Fallout 4 v1.11.191)
- LoadLibraryA wird korrekt verwendet
- Erfolgs-Log "f4se dll loaded successfully" ist vorhanden
- Fehlerbehandlung mit GetLastError() bei Fehlschlag vorhanden
- Return bei Fehler verhindert Zugriff auf NULL-Handle

---

### [x] Kriterium 8: StartF4SE per GetProcAddress -- PASS

**Code** (`main.c:25, 38-46`):
```c
typedef void (*StartF4SE_t)(void);
// ...
pfnStartF4SE = (StartF4SE_t)GetProcAddress(hF4SE, "StartF4SE");
if (!pfnStartF4SE) {
    shim_log("ERROR: StartF4SE export not found ...", GetLastError());
    return;
}
pfnStartF4SE();
shim_log("StartF4SE called successfully");
```

**Referenz-Vergleich** (`f4se.cpp:228-232`):
```cpp
extern "C" {
    void StartF4SE(void)
    {
        InstallBaseHooks();
    }
```

F4SE `exports.def`:
```
EXPORTS
StartF4SE @1
```

**Befund:**
- Typedef `void (*StartF4SE_t)(void)` stimmt EXAKT mit F4SE-Referenz ueberein
- Export-Name "StartF4SE" korrekt (Gross-/Kleinschreibung geprueft)
- GetProcAddress korrekt mit F4SE-HMODULE aufgerufen
- Fehlerbehandlung bei fehlendem Export vorhanden
- Aufruf `pfnStartF4SE()` ohne Parameter -- korrekt
- Erfolgs-Log "StartF4SE called successfully" vorhanden

---

### [x] Kriterium 9: Graceful Degradation ohne F4SE -- PASS

**Drei Fehlerszenarien geprueft:**

**A) f4se_1_11_191.dll nicht vorhanden** (`main.c:31-35`):
- `load_f4se()` loggt Warnung und kehrt mit `return` zurueck
- `DllMain` gibt `TRUE` zurueck (Zeile 77)
- Spiel laeuft weiter ohne F4SE

**B) proxy_init() schlaegt fehl** (`main.c:60-64`):
- `DllMain` gibt explizit `TRUE` zurueck mit Kommentar "so the process doesn't abort"
- `load_f4se()` wird korrekt NICHT aufgerufen
- Spiel laeuft weiter (ohne Proxy und ohne F4SE)

**C) GetProcAddress fuer StartF4SE fehlgeschlagen** (`main.c:39-42`):
- `load_f4se()` loggt Fehler und kehrt mit `return` zurueck
- `DllMain` gibt `TRUE` zurueck
- Spiel laeuft weiter

**Befund:**
- In KEINEM Fehlerfall gibt DllMain FALSE zurueck
- In KEINEM Fehlerfall wird der Prozess abgebrochen
- Alle Fehlerpfade sind sauber geloggt (WARN/ERROR mit GetLastError)
- Das Spiel startet garantiert, egal ob F4SE vorhanden ist oder nicht

---

### [x] Kriterium 14: Vollstaendiger Log-Ablauf -- PASS

**Erwartete Log-Phasen laut Kriterium:**
1. Proxy-Init
2. Original-DLL geladen
3. F4SE-DLL geladen
4. StartF4SE aufgerufen

**Tatsaechlicher Log-Ablauf (rekonstruiert aus Code):**

```
=== F4SE Proton Shim v1.0 ===                           [logging.c:38]
DLL_PROCESS_ATTACH -- hinstDLL=0x...                     [main.c:58]
loading original version.dll from: C:\Windows\system32\version.dll  [proxy.c:84]
original version.dll loaded at 0x...                     [proxy.c:90]
resolving 17 exports...                                  [proxy.c:92]
  OK: GetFileVersionInfoA                                [proxy.c:70, x17]
  OK: GetFileVersionInfoW
  ... (15 weitere)
proxy initialized -- original version.dll loaded         [main.c:65]
loading f4se dll...                                      [main.c:28]
f4se dll loaded successfully at 0x...                    [main.c:36]
StartF4SE found at 0x..., calling...                     [main.c:43]
StartF4SE called successfully                            [main.c:46]
--- Bei Prozessende: ---
DLL_PROCESS_DETACH                                       [main.c:71]
original version.dll unloaded                            [proxy.c:119]
=== shim unloading ===                                   [logging.c:57]
```

**Befund:**
- Alle 4 geforderten Phasen sind vollstaendig geloggt
- `fflush(g_logFile)` nach jeder Meldung (logging.c:51) -- crash-sicher
- Log-Pfad: `%USERPROFILE%\Documents\My Games\Fallout4\F4SE\f4se_shim.log`
- Fallback-Pfad: `f4se_shim.log` im Spielverzeichnis
- Log-Verzeichnis wird automatisch erstellt (CreateDirectoryA)

---

## Timing-Analyse

**Reihenfolge in DLL_PROCESS_ATTACH:**
1. `DisableThreadLibraryCalls(hinstDLL)` -- korrekt, verhindert unnoetige DLL_THREAD_ATTACH/DETACH
2. `shim_log_init()` -- Log oeffnen BEVOR irgendetwas anderes passiert
3. `proxy_init()` -- Original version.dll laden und 17 Exports aufloesen
4. `load_f4se()` -- F4SE laden und StartF4SE aufrufen

**Bewertung:**
- Die Reihenfolge ist korrekt: Proxy MUSS vor F4SE initialisiert werden, denn:
  - F4SE (StartF4SE -> InstallBaseHooks) hookt IAT-Eintraege des Spiels
  - Die Proxy-Exports muessen VORHER verfuegbar sein, falls das Spiel version.dll-Funktionen aufruft
- Log MUSS zuerst initialisiert werden, damit alle nachfolgenden Schritte geloggt werden koennen

**Vergleich mit F4SE-Referenz-Timing:**
- F4SE selbst wird in seinem `DllMain` nur `g_moduleHandle` gesetzt
- `StartF4SE()` ruft `InstallBaseHooks()` auf, das IAT-Hooks installiert
- Die eigentliche F4SE-Initialisierung passiert spaeter via `_initterm_e` und `_get_narrow_winmain_command_line` Hooks
- Der Shim ruft `StartF4SE()` waehrend DLL_PROCESS_ATTACH auf -- das ist frueh genug, damit F4SE seine Hooks installieren kann, bevor das Spiel in WinMain eintritt

---

## Zusaetzliche Findings

### [MEDIUM] Kein FreeLibrary fuer F4SE-DLL
- **Datei:** `/home/mob/Projekte/f4se-proton-shim/src/main.c`
- **Problem:** `hF4SE` ist lokal in `load_f4se()`. Die geladene F4SE-DLL wird nie explizit entladen. Windows/Wine entlaedt sie beim Prozessende automatisch.
- **Impact:** Keiner -- F4SE MUSS waehrend der gesamten Laufzeit geladen bleiben (es hookt den Prozess). Ein FreeLibrary waere sogar schaedlich.
- **Schweregrad:** Kein Fix noetig -- das Verhalten ist korrekt und beabsichtigt.

### [LOW] strcat ohne Laengenpruefung in proxy.c
- **Datei:** `/home/mob/Projekte/f4se-proton-shim/src/proxy.c:82`
- **Problem:** `strcat(sysdir, "\\version.dll")` ohne Laengenpruefung. `sysdir` ist MAX_PATH gross, GetSystemDirectoryA gibt ~20 Zeichen zurueck. Kein realistisches Overflow-Risiko.
- **Fix:** Optional `snprintf(sysdir + len, MAX_PATH - len, "\\version.dll")` verwenden.

### [LOW] Dateiname/Funktionsname-Inkonsistenz
- **Datei:** `/home/mob/Projekte/f4se-proton-shim/src/logging.c` / `logging.h`
- **Problem:** Dateien heissen `logging.*`, aber Funktionen heissen `shim_log_*()`. Kein Bug, nur kosmetisch.

---

## Ergebnis: 4/4 Punkte erfuellt

| Kriterium | Status | Zusammenfassung |
|-----------|--------|-----------------|
| 7: LoadLibrary f4se_1_11_191.dll | PASS | Korrekter DLL-Name, Fehlerbehandlung, Erfolgs-Log |
| 8: StartF4SE per GetProcAddress | PASS | Korrekte Signatur (void->void), stimmt mit F4SE-Referenz ueberein |
| 9: Graceful Degradation | PASS | DllMain gibt TRUE zurueck in allen Fehlerszenarien |
| 14: Vollstaendiger Log-Ablauf | PASS | Alle 4 Phasen geloggt, fflush nach jeder Meldung |

**READY FOR COMMIT** (aus Sicht des Loading & Timing Domains)
