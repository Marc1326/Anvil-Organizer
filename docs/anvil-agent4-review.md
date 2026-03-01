# QA Report Agent 4 -- Logging, Safety & Code-Qualitaet
# F4SE Proton Shim Projekt
Datum: 2026-02-28

---

## Akzeptanz-Checkliste

### Kriterium 4: DLL wird NICHT geladen ohne WINEDLLOVERRIDES

**Ergebnis: PASS**

Begruendung durch Code-Analyse:

1. Unsere `version.dll` ist eine **native Windows DLL** (PE32+ executable, x86-64), gebaut mit MinGW-w64. Sie ist KEINE Wine-Builtin-DLL.
2. Wine/Proton bevorzugt standardmaessig seine eigene **Builtin** `version.dll`. Eine fremde `version.dll` im Spielverzeichnis wird von Wine **ignoriert**, solange kein expliziter DLL-Override konfiguriert ist.
3. Code-Pruefung: Es gibt in unserem Code **keinerlei Mechanismus**, der Wine's DLL-Lade-Reihenfolge umgeht:
   - Kein Registry-Eintrag wird geschrieben
   - Keine `wine.overrides`-Datei wird erzeugt
   - Kein `SetDllDirectoryA()` oder aehnliche API-Aufrufe
   - Kein Self-Injection oder Thread-Injection
   - Die DLL tut erst etwas, wenn Wine sie tatsaechlich laedt (in `DllMain` bei `DLL_PROCESS_ATTACH`)
4. Das Verhalten (Builtin bevorzugt, Native nur bei Override) ist eine dokumentierte Wine-Eigenschaft: https://wiki.winehq.org/Wine_User%27s_Guide#DLL_Overrides
5. DLL-Imports (`objdump -p`): Nur `KERNEL32.dll` und CRT-APIs -- keine Version.dll-Import-Lib, was korrekt ist (original wird per `LoadLibraryA` zur Laufzeit geladen).

**Fazit:** Ohne `WINEDLLOVERRIDES="version=n,b"` wird Wine seine Builtin-version.dll verwenden und unsere DLL im Spielordner vollstaendig ignorieren. Kein Eingriff ohne expliziten Override.

---

### Kriterium 5: Mit WINEDLLOVERRIDES wird unsere DLL geladen

**Ergebnis: PASS**

Begruendung:

1. `WINEDLLOVERRIDES="version=n,b"` weist Wine an: "Lade version.dll zuerst als **native** DLL (n), fallback auf **builtin** (b)".
2. Wine sucht native DLLs im Verzeichnis der aufrufenden EXE (`Fallout4.exe`) -- dort liegt unsere `version.dll`.
3. Unsere DLL exportiert alle 17 Standard-Exports der echten `version.dll` (verifiziert via `objdump`):
   - `GetFileVersionInfoA` (Ordinal 1)
   - `GetFileVersionInfoByHandle` (Ordinal 2)
   - `GetFileVersionInfoExA` (Ordinal 3)
   - `GetFileVersionInfoExW` (Ordinal 4)
   - `GetFileVersionInfoSizeA` (Ordinal 5)
   - `GetFileVersionInfoSizeExA` (Ordinal 6)
   - `GetFileVersionInfoSizeExW` (Ordinal 7)
   - `GetFileVersionInfoSizeW` (Ordinal 8)
   - `GetFileVersionInfoW` (Ordinal 9)
   - `VerFindFileA` (Ordinal 10)
   - `VerFindFileW` (Ordinal 11)
   - `VerInstallFileA` (Ordinal 12)
   - `VerInstallFileW` (Ordinal 13)
   - `VerLanguageNameA` (Ordinal 14)
   - `VerLanguageNameW` (Ordinal 15)
   - `VerQueryValueA` (Ordinal 16)
   - `VerQueryValueW` (Ordinal 17)
4. `exports.def` bildet die Proxy-Funktionen korrekt auf die Original-Namen ab.
5. `proxy_init()` laedt die Original-version.dll aus dem System-Verzeichnis per `LoadLibraryA` und resolved alle 17 Exports per `GetProcAddress`.
6. Alle Proxy-Wrapper leiten Aufrufe korrekt an die Originalfunktionen weiter und setzen `ERROR_PROC_NOT_FOUND` falls eine Funktion nicht aufgeloest werden konnte.

**Fazit:** Mit dem Override laedt Wine unsere native version.dll, die alle Exports korrekt an die System-DLL weiterleitet und zusaetzlich F4SE injiziert.

---

## Logging-Pruefung (src/logging.c + src/logging.h)

### Log-Pfad
- **Korrekt:** `%USERPROFILE%\Documents\My Games\Fallout4\F4SE\f4se_shim.log`
- Das ist der Standard-Pfad fuer F4SE-Logs und passt zur Erwartung.

### Fallback
- **Vorhanden:** Wenn USERPROFILE nicht gesetzt ist ODER fopen fehlschlaegt, wird `f4se_shim.log` im aktuellen Verzeichnis (neben der EXE) geschrieben.
- Zeile 33: `if (!g_logFile) { g_logFile = fopen("f4se_shim.log", "w"); }`

### Verzeichnis-Erstellung
- **Vorhanden:** Vier `CreateDirectoryA()`-Aufrufe erstellen die Hierarchie schrittweise:
  1. `Documents\My Games`
  2. `Documents\My Games\Fallout4`
  3. `Documents\My Games\Fallout4\F4SE`
- Fehler bei bereits existierenden Verzeichnissen werden korrekt ignoriert (CreateDirectoryA gibt FALSE zurueck, was hier nicht gepreuft wird -- korrekt).

### fflush() nach jedem Log-Eintrag
- **Vorhanden:** Zeile 51: `fflush(g_logFile);` nach jeder Log-Zeile. Wichtig fuer Crash-Debugging, da der letzte Log-Eintrag vor einem Crash sichtbar bleibt.

### shim_log_close()
- **Korrekt:** Schreibt Abschluss-Nachricht, schliesst die Datei mit `fclose()` und setzt `g_logFile = NULL` (Schutz vor Double-Close).

### Header-Guards (logging.h)
- **Korrekt:** `#ifndef F4SE_SHIM_LOGGING_H` / `#define F4SE_SHIM_LOGGING_H` / `#endif`
- Kommentar `/* F4SE_SHIM_LOGGING_H */` am Ende -- sauber.

---

## Sicherheits- und Qualitaets-Analyse

### DisableThreadLibraryCalls()
- **Vorhanden:** `main.c` Zeile 55: `DisableThreadLibraryCalls(hinstDLL);`
- Korrekt als erster Aufruf in `DLL_PROCESS_ATTACH`.

---

## Findings

### [HIGH] Buffer Overflow in proxy_init() -- strcat auf festen Buffer

- **Datei:** `/home/mob/Projekte/f4se-proton-shim/src/proxy.c`, Zeilen 79-82
- **Problem:** 
  ```c
  char sysdir[MAX_PATH];   // MAX_PATH = 260 Bytes
  GetSystemDirectoryA(sysdir, MAX_PATH);
  strcat(sysdir, "\\version.dll");  // 13 Bytes anhaengen
  ```
  `GetSystemDirectoryA` kann bis zu `MAX_PATH-1` (259) Zeichen zurueckgeben. Plus 13 Bytes fuer `"\\version.dll"` plus Null-Terminator = maximal 273 Bytes. Der Buffer ist nur 260 Bytes gross.
  
  **Realistische Einschaetzung:** Unter Wine/Proton ist das System-Verzeichnis typischerweise `C:\windows\system32` (22 Zeichen). Ein Overflow ist extrem unwahrscheinlich, aber theoretisch moeglich bei exotischen Wine-Prefix-Konfigurationen.

- **Fix:**
  ```c
  char sysdir[MAX_PATH + 16];
  UINT len = GetSystemDirectoryA(sysdir, MAX_PATH);
  if (len == 0 || len >= MAX_PATH - 13) {
      shim_log("FATAL: system directory too long or unavailable");
      return FALSE;
  }
  strcat(sysdir, "\\version.dll");
  ```
  Oder besser: `snprintf()` wie in `logging.c` bereits verwendet.

---

### [MEDIUM] Potentieller Log-Pfad Buffer Overflow in logging.c

- **Datei:** `/home/mob/Projekte/f4se-proton-shim/src/logging.c`, Zeilen 19-28
- **Problem:**
  ```c
  char userprofile[MAX_PATH];
  char dirpath[MAX_PATH];
  char logpath[MAX_PATH];
  // ...
  snprintf(dirpath, MAX_PATH, "%s\\Documents\\My Games\\Fallout4\\F4SE", userprofile);
  snprintf(logpath, MAX_PATH, "%s\\f4se_shim.log", dirpath);
  ```
  `snprintf` truncated korrekt bei MAX_PATH, es gibt also keinen Buffer Overflow. **Aber:** Wenn `USERPROFILE` lang ist (z.B. 240+ Zeichen), wird `dirpath` abgeschnitten und `CreateDirectoryA` schlaegt fehl. Die Datei wird dann nicht erstellt, aber der Fallback greift (Zeile 33). **Kein Bug, aber ein stilles Fehlverhalten ohne Warnung.**
  
  `snprintf()` ist hier korrekt und sicher. Die Verwendung von `snprintf` statt `strcat` zeigt, dass `logging.c` besser geschrieben ist als `proxy.c`.

- **Fix:** Optional einen `shim_log`-Aufruf (auf stderr oder so) wenn der Pfad zu lang ist. Aber da der Fallback existiert, ist das kein kritischer Punkt.

---

### [MEDIUM] LOAD_PROC Makro -- C-Style Cast ueber void-Pointer

- **Datei:** `/home/mob/Projekte/f4se-proton-shim/src/proxy.c`, Zeile 66
- **Problem:**
  ```c
  p_##name = (fn_##name)(void *)GetProcAddress(g_hOriginal, #name);
  ```
  Der Cast `(fn_##name)(void *)` sieht syntaktisch ungewoehnlich aus. Tatsaechlich ist `(void *)` hier ein C-Style Cast auf den Rueckgabewert von `GetProcAddress` (FARPROC), und dann wird `(fn_##name)` darauf angewendet. Das funktioniert, weil C-Casts links-assoziativ sind. Der Code ist korrekt, aber die Absicht waere mit Klammern klarer:
  ```c
  p_##name = (fn_##name)(void *)(GetProcAddress(g_hOriginal, #name));
  ```
  Oder noch besser:
  ```c
  p_##name = (fn_##name)GetProcAddress(g_hOriginal, #name);
  ```
  Der `(void *)` Zwischen-Cast ist sowieso unnoetig, da FARPROC bereits ein Funktionspointer ist.

- **Schweregrad:** Rein kosmetisch, kein funktionaler Bug.

---

### [LOW] F4SE-DLL-Handle wird nicht gespeichert -- bewusste Design-Entscheidung?

- **Datei:** `/home/mob/Projekte/f4se-proton-shim/src/main.c`, Zeilen 22-47
- **Problem:** `hF4SE` (das Handle von `LoadLibraryA("f4se_1_11_191.dll")`) ist eine lokale Variable in `load_f4se()`. Das Handle wird nach dem Funktionsaufruf verworfen. Es wird kein `FreeLibrary(hF4SE)` in `DLL_PROCESS_DETACH` aufgerufen.
- **Bewertung:** Das ist **korrekt und beabsichtigt**. F4SE muss fuer die gesamte Lebensdauer des Prozesses geladen bleiben. Das Handle wird nie benoetigt, weil F4SE sich selbst in den Prozess hookt und nicht manuell entladen werden soll. Bei `DLL_PROCESS_DETACH` ist der Prozess sowieso am Beenden -- ein `FreeLibrary` waere hier sogar schaedlich (F4SE hat eigene Cleanup-Logik).

---

### [LOW] Keine Pruefung ob DllMain-Rueckgabewert nach proxy_init()-Fehler sinnvoll ist

- **Datei:** `/home/mob/Projekte/f4se-proton-shim/src/main.c`, Zeilen 60-63
- **Problem:**
  ```c
  if (!proxy_init()) {
      shim_log("ERROR: proxy_init failed -- proxy functions will not work");
      /* Return TRUE anyway so the process doesn't abort */
      return TRUE;
  }
  ```
  Wenn `proxy_init()` fehlschlaegt, sind alle 17 Function-Pointer NULL. Die Proxy-Wrapper setzen dann `ERROR_PROC_NOT_FOUND` und geben 0/FALSE zurueck. Das Spiel koennte abstuerzen wenn es `GetFileVersionInfoA` etc. aufruft und eine fehlende Antwort bekommt.
  
  **Bewertung:** Der Kommentar erklaert die Intention. Ein `return FALSE` wuerde den gesamten Prozess abbrechen -- schlimmer als fehlerhafte version.dll-Aufrufe. Die aktuelle Loesung ist pragmatisch korrekt. Die Proxy-Wrapper loggen nicht wenn sie mit NULL-Pointer aufgerufen werden, was das Debugging erschwert -- aber das ist ein LOW-Issue.

---

### [LOW] build.sh verwendet -Wno-format-truncation

- **Datei:** `/home/mob/Projekte/f4se-proton-shim/build.sh`, Zeile 29
- **Problem:** `CFLAGS="-O2 -Wall -Wextra -Wno-format-truncation -std=c99"`
  Das `-Wno-format-truncation` unterdrueckt Warnungen fuer `snprintf`-Truncation. Das ist hier bewusst, da `snprintf` in `logging.c` absichtlich abschneidet. Aber es unterdrueckt auch potenzielle Warnungen fuer `strcat` in `proxy.c`.
- **Bewertung:** Akzeptabel, da `strcat` sowieso keine Format-Truncation-Warnung erzeugt (das ist nur fuer `*printf`-Funktionen). Trotzdem waere es besser, die Warnung nur fuer `logging.c` zu unterdruecken.

---

### [LOW] Keine Versionsinformation in der DLL

- **Datei:** Gesamtes Projekt
- **Problem:** Die DLL hat keine VERSIONINFO-Resource. Tools wie `file` oder der Windows Explorer zeigen keine Version, Autor oder Beschreibung an. Das ist fuer ein Release-Produkt unueblich.
- **Fix:** Eine `.rc`-Datei mit VERSIONINFO-Block hinzufuegen und in `build.sh`/`CMakeLists.txt` einbinden.

---

## Memory Leaks

- **Keine gefunden.** 
  - `g_hOriginal` wird in `proxy_cleanup()` mit `FreeLibrary()` freigegeben.
  - `g_logFile` wird in `shim_log_close()` mit `fclose()` geschlossen.
  - Alle lokalen Variablen sind Stack-alloziert (kein `malloc`/`HeapAlloc` im gesamten Code).

## Race Conditions

- **Keine gefunden.**
  - `DisableThreadLibraryCalls()` wird aufgerufen, sodass `DllMain` nicht fuer Thread-Attach/Detach aufgerufen wird.
  - Alle globalen Variablen (`g_hOriginal`, `g_logFile`) werden nur in `DLL_PROCESS_ATTACH` (einmal) und `DLL_PROCESS_DETACH` (einmal) geschrieben.
  - Die Proxy-Funktionen lesen nur -- keine Write-Zugriffe auf globale Variablen.

## Unsafe String-Funktionen

| Funktion | Datei | Zeile | Sicher? |
|----------|-------|-------|---------|
| `strcat(sysdir, "\\version.dll")` | proxy.c | 82 | **NEIN** -- siehe HIGH-Finding oben |
| `snprintf(dirpath, MAX_PATH, ...)` | logging.c | 19-28 | JA -- bounds-checked |
| `snprintf(logpath, MAX_PATH, ...)` | logging.c | 28 | JA -- bounds-checked |
| `vfprintf(g_logFile, fmt, args)` | logging.c | 48 | JA -- schreibt in Datei, nicht in Buffer |

---

## Zusammenfassung

| Aspekt | Status |
|--------|--------|
| Kriterium 4 (keine Ladung ohne Override) | PASS |
| Kriterium 5 (Ladung mit Override) | PASS |
| Log-Pfad korrekt | PASS |
| Fallback vorhanden | PASS |
| Verzeichnis-Erstellung | PASS |
| fflush nach jedem Eintrag | PASS |
| shim_log_close korrekt | PASS |
| Header-Guards sauber | PASS |
| DisableThreadLibraryCalls | PASS |
| Buffer Overflows | 1x HIGH (proxy.c:82) |
| Memory Leaks | Keine |
| Race Conditions | Keine |
| Sicherheitsluecken | Keine (ausser Buffer Overflow) |

## Findings-Zusammenfassung nach Schweregrad

| Schweregrad | Anzahl | Details |
|-------------|--------|---------|
| CRITICAL | 0 | -- |
| HIGH | 1 | Buffer Overflow in proxy.c strcat |
| MEDIUM | 2 | Log-Pfad stille Truncation, Makro-Cast-Stil |
| LOW | 3 | F4SE-Handle nicht gespeichert, proxy_init-Fehlerbehandlung, keine VERSIONINFO |

---

## Ergebnis

### Akzeptanz-Checkliste:

- [x] Kriterium 4: DLL wird NICHT geladen ohne WINEDLLOVERRIDES -- PASS
- [x] Kriterium 5: DLL wird geladen MIT WINEDLLOVERRIDES -- PASS

### Gesamt-Bewertung: 2/2 Akzeptanz-Kriterien erfuellt

### Code-Qualitaet: NEEDS FIX (1 HIGH Finding)

Der Buffer Overflow in `proxy.c:82` (`strcat` auf `MAX_PATH`-Buffer) sollte vor einem Release gefixt werden. Alle anderen Findings sind MEDIUM/LOW und koennen als Follow-up behandelt werden.

**Empfehlung:** `strcat` durch `snprintf` ersetzen (konsistent mit `logging.c`), dann ist der Code release-ready.
