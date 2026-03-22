# SFSE Proton Shim — Entwicklungsbericht

## Datum
2026-03-22

## Issue
GitHub Issue #55, Teil 2

## Erstellte Dateien

Verzeichnis: `/home/mob/Projekte/sfse-proton-shim/`

| Datei | Beschreibung |
|---|---|
| `src/main.c` | SFSE Shim Entry Point — IAT-Hook fuer _initterm_e, laedt sfse_1_15_222.dll |
| `src/proxy.c` | version.dll Export-Forwarding (3 Exports: GetFileVersionInfoA, GetFileVersionInfoSizeA, VerQueryValueA) |
| `src/proxy.h` | Header fuer proxy.c |
| `src/logging.c` | Logging nach `My Games\Starfield\SFSE\sfse_shim.log` |
| `src/logging.h` | Header fuer logging.c (Include-Guard: SFSE_SHIM_LOGGING_H) |
| `exports.def` | DEF-Datei mit 3 Exports fuer version.dll |
| `build.sh` | Build-Script mit MinGW x86_64, `-static` Linking |

## Aenderungen gegenueber F4SE-Shim

| Aspekt | F4SE | SFSE |
|---|---|---|
| Proxy-DLL | X3DAudio1_7.dll | version.dll |
| SKSE-DLL | f4se_1_11_191.dll | sfse_1_15_222.dll |
| Entry-Point | StartF4SE | StartSFSE |
| Exports | X3DAudioInitialize, X3DAudioCalculate (2) | GetFileVersionInfoA, GetFileVersionInfoSizeA, VerQueryValueA (3) |
| Log-Pfad | My Games\Fallout4\F4SE\f4se_shim.log | My Games\Starfield\SFSE\sfse_shim.log |
| Linker-Flags | -lversion (X3DAudio brauchte es) | kein -lversion (dynamisch geladen) |
| Proxy-Init | Deferred (beim ersten Call) | Direkt in Proxy_Init() |

## Kompiler-Output

```
=== SFSE Proton Shim Build ===
[1/3] Compiling...
(3 Warnungen zu FARPROC-Casts — harmlos, standard bei GetProcAddress)
[2/3] Linking...
[3/3] Copying to dist/...
=== Build complete ===
Output: dist/version.dll
```

## Validierung

### file dist/version.dll
```
PE32+ executable for MS Windows 5.02 (DLL), x86-64, 20 sections
```
PASS — Korrekte Architektur.

### Export Table (objdump)
```
[Ordinal/Name Pointer] Table -- Ordinal Base 1
    [   0] +base[   1]  0000 GetFileVersionInfoA
    [   1] +base[   2]  0001 GetFileVersionInfoSizeA
    [   2] +base[   3]  0002 VerQueryValueA
```
PASS — 3 Exports korrekt.

### DLL Imports
```
DLL Name: KERNEL32.dll
DLL Name: api-ms-win-crt-heap-l1-1-0.dll
DLL Name: api-ms-win-crt-private-l1-1-0.dll
DLL Name: api-ms-win-crt-runtime-l1-1-0.dll
DLL Name: api-ms-win-crt-stdio-l1-1-0.dll
DLL Name: api-ms-win-crt-string-l1-1-0.dll
```
PASS — Nur System-DLLs, KEINE MinGW-Runtime (libgcc_s, libwinpthread).

### Dateigroesse
```
111K
```
PASS — Unter 200KB.

## Deployment

DLL kopiert nach:
```
anvil/data/shims/starfield/version.dll (111KB)
```

## Status
FERTIG — Alle Validierungen bestanden.
