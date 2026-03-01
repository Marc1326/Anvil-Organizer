# Gesamtplan: F4SE Proton Shim

Konsolidierung der Analysen von Agent 1 (Proxy-Exports), Agent 2 (Loading & Timing) und Agent 3 (Build-System).

---

## 1. Architektur-Zusammenfassung

### Was wir bauen:
Eine **version.dll Proxy-DLL** die unter Wine/Proton als DLL-Override geladen wird und F4SE Next-Gen (0.7.7) in den Fallout-4-Prozess injiziert — ohne CreateRemoteThread.

### Datenfluss:
```
Steam startet Fallout4.exe mit WINEDLLOVERRIDES="version=n,b"
  |
  v
Wine/Proton laedt Fallout4.exe und resolvt Imports
  |
  v
version.dll wird aus dem Spielordner geladen (unsere Proxy-DLL)
  |
  v
DLL_PROCESS_ATTACH feuert:
  |
  +-- 1. Original version.dll aus system32 laden (fuer Proxy-Funktionen)
  +-- 2. Alle 17 Export-Funktionszeiger per GetProcAddress holen
  +-- 3. f4se_1_11_191.dll per LoadLibraryA laden
  +-- 4. StartF4SE() per GetProcAddress finden und aufrufen
  |       |
  |       v
  |     StartF4SE() -> InstallBaseHooks():
  |       +-- Hookt _initterm_e in EXE-IAT -> F4SE_Preinit (Trampolines, Plugin-Preload)
  |       +-- Hookt _get_narrow_winmain_command_line -> F4SE_Initialize (alle Hooks, Plugins)
  |
  v
DLL_PROCESS_ATTACH endet, EXE-Initialisierung geht weiter
  |
  v
EXE ruft _initterm_e auf -> F4SE_Preinit() feuert
  |
  v
EXE ruft _get_narrow_winmain_command_line auf -> F4SE_Initialize() feuert
  |
  v
WinMain() -> Spiel laeuft mit F4SE aktiv
```

### Komponenten:

| Datei | Funktion |
|---|---|
| `src/main.c` | DllMain, F4SE-Loading-Logik, Logging |
| `src/proxy.c` | 17 version.dll Export-Wrapper + Original-DLL-Laden |
| `src/proxy.h` | Proxy-Header mit Funktionsdeklarationen |
| `src/logging.c` | Einfaches File-Logging nach `Documents/My Games/Fallout4/F4SE/` |
| `src/logging.h` | Logging-Header |
| `exports.def` | Export-Definitionen fuer den Linker |

## 2. Implementierungsreihenfolge

### Phase 1: Grundgeruest (Tag 1)
1. **Projektverzeichnis erstellen** (`/home/mob/Projekte/f4se-proton-shim/`)
2. **MinGW-w64 installieren** (`sudo pacman -S mingw-w64-gcc`)
3. **Build-System aufsetzen** (CMakeLists.txt, toolchain-mingw64.cmake, build.sh)
4. **Minimale DLL bauen** (leere DllMain die TRUE zurueckgibt) — Build-Kette verifizieren

### Phase 2: Proxy-Exports (Tag 1-2)
5. **exports.def schreiben** (alle 17 version.dll Funktionen)
6. **proxy.c implementieren** — Original-DLL laden, Funktionszeiger holen
7. **Alle 17 Wrapper-Funktionen implementieren** — typsichere Weiterleitungen
8. **Build testen** — DLL muss alle 17 Exports haben (objdump verifizieren)

### Phase 3: F4SE-Loading (Tag 2)
9. **F4SE-Loading in main.c** — LoadLibrary + GetProcAddress("StartF4SE") + Aufruf
10. **Logging implementieren** — Alle Schritte loggen fuer Debugging
11. **Fehlerbehandlung** — Graceful Degradation wenn F4SE nicht gefunden wird

### Phase 4: Test & Debug (Tag 2-3)
12. **DLL unter Wine testen** (ohne Spiel, mit Test-EXE oder direkt mit Fallout 4)
13. **Exports verifizieren** — Alle 17 Funktionen muessen korrekt forwarden
14. **F4SE-Loading verifizieren** — Log-Datei pruefen ob F4SE initialisiert
15. **Spiel starten und F4SE-Version im Hauptmenue pruefen**

### Phase 5: Polish & Release (Tag 3)
16. **README.md schreiben** — Installationsanleitung
17. **Edge Cases testen** — Fehlende F4SE-DLL, falsche Version, etc.
18. **Release-Paket erstellen** (dist/version.dll + README)

## 3. Abhaengigkeiten zwischen den Teilen

```
Build-System (Phase 1) ──────> Proxy-Exports (Phase 2) ──────> F4SE-Loading (Phase 3)
     |                                |                               |
     |                                |                               |
     v                                v                               v
CMakeLists.txt              proxy.c braucht                 main.c braucht
muss .def einbinden         exports.def fuer                proxy_init() von
                            Linker-Export-Namen              proxy.c
                                                            
                                                            StartF4SE braucht
                                                            dass IAT existiert
                                                            (immer gegeben in
                                                            DLL_PROCESS_ATTACH)
```

**Kritischer Pfad:** Build-System -> exports.def -> proxy.c -> main.c -> Test

**Keine zirkulaeren Abhaengigkeiten.** Jede Phase kann unabhaengig getestet werden:
- Phase 2 testbar mit `objdump` (Exports vorhanden?)
- Phase 3 testbar mit Log-Datei (F4SE geladen?)

## 4. Risiken und Fallback-Strategien

### Risiko 1: version.dll wird von Fallout 4 NICHT importiert
- **Wahrscheinlichkeit:** NIEDRIG (GetFileVersionInfo wird ueblicherweise benoetigt)
- **Impact:** HOCH (unsere DLL wuerde nie geladen)
- **Erkennung:** `objdump -p Fallout4.exe | grep version.dll` — vor Implementierung pruefen!
- **Fallback:** Alternative Proxy-DLL: `winmm.dll` (18 Exports, wird fast immer importiert) oder `dinput8.dll` (1 Export: DirectInput8Create)
- **Aufwand Fallback:** exports.def anpassen + proxy.c anpassen (2-3 Stunden)

### Risiko 2: LoadLibrary schlaegt fehl in DLL_PROCESS_ATTACH (Loader-Lock)
- **Wahrscheinlichkeit:** SEHR NIEDRIG (F4SE hat triviale DllMain)
- **Impact:** HOCH (F4SE wird nicht geladen)
- **Erkennung:** LoadLibrary gibt NULL zurueck, Log zeigt Fehler
- **Fallback A:** Thread starten: `CreateThread(NULL, 0, LoadF4SEThread, NULL, 0, NULL)` — aber Race Condition mit _initterm_e moeglich
- **Fallback B:** DllMain-Hook auf eine UCRT-DLL setzen, die nach version.dll geladen wird
- **Aufwand Fallback:** 4-6 Stunden

### Risiko 3: StartF4SE() crasht (IAT-Patching schlaegt fehl)
- **Wahrscheinlichkeit:** NIEDRIG (IAT-Patching ist Standard-Technik, Wine unterstuetzt es)
- **Impact:** HOCH (Crash)
- **Erkennung:** SEH-Handler um StartF4SE-Aufruf, Log vor/nach jedem Schritt
- **Fallback:** Keine — wenn IAT-Patching nicht funktioniert, funktioniert F4SE grundsaetzlich nicht unter Wine
- **Mitigation:** Sicherstellen dass GE-Proton/Wine-Staging verwendet wird (wine-hackery Patches)

### Risiko 4: BranchTrampoline findet keinen Speicher
- **Wahrscheinlichkeit:** MITTEL (bekanntes Wine-Problem)
- **Impact:** HOCH (F4SE Preinit schlaegt fehl)
- **Erkennung:** F4SE-Log zeigt "couldn't create branch trampoline"
- **Fallback:** GE-Proton verwenden (enthaelt hdmap-Patches)
- **Mitigation:** In README dokumentieren: "GE-Proton 7.x oder neuer erforderlich"

### Risiko 5: MinGW-kompilierte DLL hat ABI-Inkompatibilitaeten
- **Wahrscheinlichkeit:** NIEDRIG (wir nutzen nur C, keine C++-ABI-Probleme)
- **Impact:** MITTEL (Crashes bei Funktionsaufrufen)
- **Erkennung:** Crashes beim Aufruf von Proxy-Funktionen
- **Fallback:** Calling-Convention explizit auf `WINAPI` (__stdcall auf x86, __fastcall auf x64) setzen
- **Mitigation:** Alle Proxy-Funktionen mit korrekter Signatur deklarieren

### Risiko 6: Wine/Proton-Version zu alt
- **Wahrscheinlichkeit:** MITTEL
- **Impact:** Verschiedene Symptome (Crashes, fehlende Features)
- **Erkennung:** Verschiedene Fehler je nach fehlender Wine-Funktionalitaet
- **Mitigation:** Mindest-Version dokumentieren (Wine 7.0+ / GE-Proton 7.x+)

## 5. Designentscheidungen

| Entscheidung | Wahl | Alternative | Begruendung |
|---|---|---|---|
| Sprache | C | C++ | Einfacher, kein ABI-Problem, MinGW-freundlich |
| Proxy-DLL | version.dll | winmm.dll, dinput8.dll | Gaengigste Wahl, wird von Spielen importiert |
| Export-Forwarding | Runtime (GetProcAddress) | .def Forwarding | Zuverlaessiger unter Wine |
| F4SE-Timing | DLL_PROCESS_ATTACH direkt | IAT-Hook, Thread | Einfachste Loesung, frueh genug |
| Build-System | CMake + Toolchain | Makefile | Erweiterbar, Toolchain-Handling |
| Linking | Statisch | Dynamisch | Keine MinGW-Runtime-Abhaengigkeiten |
| Logging | Eigenes File-Log | Kein Logging | Essentiell fuer Debugging |

## 6. Dateigroessen-Schaetzung

| Datei | Geschaetzte Zeilen |
|---|---|
| main.c | 80-120 |
| proxy.c | 200-250 |
| proxy.h | 30-40 |
| logging.c | 50-80 |
| logging.h | 15-20 |
| exports.def | 20-25 |
| CMakeLists.txt | 40-50 |
| toolchain-mingw64.cmake | 15-20 |
| build.sh | 40-50 |
| README.md | 100-150 |
| **Gesamt** | **~600-800 Zeilen** |

Das ist ein KLEINES Projekt. Die gesamte Logik passt in weniger als 500 Zeilen C-Code.

## 7. Test-Strategie

### Stufe 1: Build-Verifizierung (ohne Spiel)
```bash
./build.sh
file dist/version.dll                    # PE32+ executable (DLL) x86-64
x86_64-w64-mingw32-objdump -p dist/version.dll | grep "Export Table" -A 50
# Muss alle 17 version.dll Funktionen zeigen
x86_64-w64-mingw32-objdump -p dist/version.dll | grep "DLL Name"
# Darf NUR kernel32.dll, version.dll, msvcrt.dll/ucrt zeigen
```

### Stufe 2: Wine-Test (ohne Spiel)
```bash
# Einfacher Test: DLL unter Wine laden
WINEDLLOVERRIDES="version=n,b" wine64 cmd.exe /c "echo test"
# Sollte ohne Fehler durchlaufen
# Log-Datei pruefen
```

### Stufe 3: Fallout 4 Test
```bash
# Steam Launch-Optionen:
WINEDLLOVERRIDES="version=n,b" %command%

# Pruefpunkte:
# 1. Log-Datei: Documents/My Games/Fallout4/F4SE/f4se_shim.log
# 2. F4SE-Log: Documents/My Games/Fallout4/F4SE/f4se.log
# 3. Hauptmenue zeigt F4SE-Version
# 4. F4SE-Plugins geladen (Konsole oeffnen, GetF4SEVersion)
```

### Stufe 4: Stabilitaetstest
- Neues Spiel starten
- 10 Minuten spielen
- Speichern und Laden
- Quicksave/Quickload
- Kein Crash = Erfolg

## 8. Mindest-Anforderungen an die Umgebung

- **Wine:** 7.0+ oder GE-Proton 7.x+ (fuer BranchTrampoline/hdmap-Patches)
- **Fallout 4:** Next-Gen Update v1.11.191 (Steam-Version)
- **F4SE:** Version 0.7.7 (fuer Fallout 4 v1.11.191)
- **Betriebssystem:** Linux mit Wine/Proton

---

## ✅ Akzeptanz-Kriterien (ALLE muessen erfuellt sein)

- [ ] Kriterium 1: Wenn `./build.sh` ausgefuehrt wird, entsteht `dist/version.dll` als PE32+ x86-64 DLL ohne Fehler
- [ ] Kriterium 2: Wenn `objdump -p dist/version.dll` ausgefuehrt wird, zeigt die Export Table alle 17 version.dll-Funktionen (GetFileVersionInfoA, GetFileVersionInfoW, VerQueryValueA, VerQueryValueW, etc.)
- [ ] Kriterium 3: Wenn `objdump -p dist/version.dll | grep "DLL Name"` ausgefuehrt wird, erscheinen NUR Windows-System-DLLs (KERNEL32.dll, VERSION.dll, msvcrt.dll/ucrt) — KEINE MinGW-Runtime-DLLs (libgcc, libwinpthread)
- [ ] Kriterium 4: Wenn die version.dll in den Fallout-4-Ordner kopiert wird und das Spiel OHNE `WINEDLLOVERRIDES` gestartet wird, wird unsere DLL NICHT geladen (kein Eingriff ohne expliziten Override)
- [ ] Kriterium 5: Wenn `WINEDLLOVERRIDES="version=n,b"` gesetzt wird, laedt Wine unsere version.dll statt der Builtin-Version
- [ ] Kriterium 6: Wenn unsere version.dll geladen wird, laedt sie die Original version.dll aus system32 und alle 17 Proxy-Funktionen funktionieren (kein Crash durch fehlende Exports)
- [ ] Kriterium 7: Wenn `f4se_1_11_191.dll` im Spielordner liegt, wird sie per LoadLibrary erfolgreich geladen (Log zeigt "f4se dll loaded successfully" oder aehnlich)
- [ ] Kriterium 8: Wenn `f4se_1_11_191.dll` geladen wurde, wird `StartF4SE()` per GetProcAddress gefunden und aufgerufen (Log zeigt "StartF4SE called successfully")
- [ ] Kriterium 9: Wenn `f4se_1_11_191.dll` NICHT im Spielordner liegt, startet das Spiel trotzdem (Graceful Degradation — Spiel laeuft ohne F4SE)
- [ ] Kriterium 10: Wenn F4SE initialisiert wurde, zeigt die Log-Datei `f4se.log` die Meldungen "preinit complete" und "init complete"
- [ ] Kriterium 11: Wenn F4SE korrekt initialisiert wurde, zeigt das Hauptmenue von Fallout 4 die F4SE-Versionsnummer
- [ ] Kriterium 12: Wenn F4SE-Plugins in `Data/F4SE/Plugins/` liegen, werden sie beim Start geladen (pruefbar ueber F4SE-Konsole oder Plugin-Logs)
- [ ] Kriterium 13: Wenn ein Spiel geladen wird (Save/Load), crasht das Spiel nicht durch unseren Shim
- [ ] Kriterium 14: Wenn der Shim-Log (`f4se_shim.log`) geoeffnet wird, zeigt er den vollstaendigen Ablauf: Proxy-Init, Original-DLL geladen, F4SE-DLL geladen, StartF4SE aufgerufen
- [ ] Kriterium 15: Wenn das Projekt unter Linux mit `./build.sh` gebaut wird, sind keine Windows-Tools (MSVC, Visual Studio) erforderlich — nur MinGW-w64
- [ ] Kriterium 16: Wenn GE-Proton 7.x oder neuer verwendet wird, funktioniert F4SE's BranchTrampoline ohne zusaetzliche Patches
- [ ] Kriterium 17: Wenn das Spiel 30 Minuten gespielt wird (Laden, Laufen, Speichern, Menu), tritt kein Crash auf der auf unseren Shim zurueckzufuehren ist
- [ ] Kriterium 18: Wenn der User Fallout 4 ueber Steam mit `WINEDLLOVERRIDES="version=n,b" %command%` startet, erscheint die F4SE-Version im Hauptmenue
