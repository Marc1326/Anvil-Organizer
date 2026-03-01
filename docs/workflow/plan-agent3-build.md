# Plan Agent 3: Build-System & Cross-Compilation

## 1. MinGW-w64 Installation

MinGW-w64 ist NICHT auf dem System installiert. Installation unter Arch/CachyOS:

```bash
sudo pacman -S mingw-w64-gcc
# Installiert: mingw-w64-binutils, mingw-w64-crt, mingw-w64-headers, mingw-w64-winpthreads, mingw-w64-gcc
# Stellt bereit: x86_64-w64-mingw32-gcc, x86_64-w64-mingw32-g++
```

Alternativ (falls Paketname anders):
```bash
sudo pacman -S mingw-w64  # Meta-Paket
# oder einzeln:
sudo pacman -S mingw-w64-gcc mingw-w64-binutils mingw-w64-headers mingw-w64-crt
```

Verifizierung nach Installation:
```bash
which x86_64-w64-mingw32-gcc
x86_64-w64-mingw32-gcc --version
```

## 2. Projektstruktur

```
/home/mob/Projekte/f4se-proton-shim/
├── CMakeLists.txt              # Haupt-Build-Datei
├── toolchain-mingw64.cmake     # CMake Toolchain-Datei fuer Cross-Compilation
├── build.sh                    # Einfaches Build-Script
├── README.md                   # Installationsanleitung fuer Enduser
├── LICENSE                     # MIT Lizenz
├── exports.def                 # version.dll Export-Definitionen
├── src/
│   ├── main.c                  # DllMain + F4SE Loading-Logik
│   ├── proxy.c                 # version.dll Export-Forwarding
│   ├── proxy.h                 # Proxy-Header
│   ├── logging.c               # Einfaches File-Logging
│   └── logging.h               # Logging-Header
├── build/                      # CMake Build-Output (gitignored)
└── dist/                       # Release-Dateien (gitignored)
    └── version.dll             # Fertige DLL fuer Enduser
```

## 3. CMake Toolchain-Datei

```cmake
# toolchain-mingw64.cmake
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

# Cross-Compiler
set(CMAKE_C_COMPILER x86_64-w64-mingw32-gcc)
set(CMAKE_CXX_COMPILER x86_64-w64-mingw32-g++)
set(CMAKE_RC_COMPILER x86_64-w64-mingw32-windres)

# Suchpfade
set(CMAKE_FIND_ROOT_PATH /usr/x86_64-w64-mingw32)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)

# Statisch linken (keine Abhaengigkeit auf libgcc_s_seh-1.dll etc.)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -static-libgcc")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -static-libgcc -static")
```

## 4. CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.16)
project(f4se-proton-shim C)

# Windows x64 DLL
set(CMAKE_SHARED_LIBRARY_PREFIX "")  # Kein "lib" Prefix

# Quell-Dateien
set(SOURCES
    src/main.c
    src/proxy.c
    src/logging.c
)

# DLL Target
add_library(version SHARED ${SOURCES})

# Export-Definitionen (.def Datei)
set_target_properties(version PROPERTIES
    # Output-Name: version.dll
    OUTPUT_NAME "version"
    # Suffix: .dll (sollte Standard sein)
    SUFFIX ".dll"
    # .def Datei fuer Exports
    LINK_FLAGS "-Wl,--kill-at ${CMAKE_CURRENT_SOURCE_DIR}/exports.def"
    # Position-Independent Code (noetig fuer DLL)
    POSITION_INDEPENDENT_CODE ON
)

# Compiler-Flags
target_compile_options(version PRIVATE
    -Wall
    -Wextra
    -O2
    -DUNICODE
    -D_UNICODE
)

# Linker: Windows-Bibliotheken
target_link_libraries(version PRIVATE
    -lkernel32
    -luser32
    -lversion
    -lshlwapi
)

# Install-Target: Kopiert DLL nach dist/
install(TARGETS version
    RUNTIME DESTINATION ${CMAKE_CURRENT_SOURCE_DIR}/dist
    LIBRARY DESTINATION ${CMAKE_CURRENT_SOURCE_DIR}/dist
)
```

## 5. Build-Script

```bash
#!/bin/bash
# build.sh — Baut version.dll mit MinGW-w64 Cross-Compiler

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
DIST_DIR="${SCRIPT_DIR}/dist"

# Pruefen ob MinGW installiert ist
if ! command -v x86_64-w64-mingw32-gcc &> /dev/null; then
    echo "FEHLER: x86_64-w64-mingw32-gcc nicht gefunden!"
    echo "Installation: sudo pacman -S mingw-w64-gcc"
    exit 1
fi

echo "=== F4SE Proton Shim Build ==="
echo "Compiler: $(x86_64-w64-mingw32-gcc --version | head -1)"

# Build-Verzeichnis erstellen
mkdir -p "${BUILD_DIR}"
mkdir -p "${DIST_DIR}"

# CMake konfigurieren
cmake -B "${BUILD_DIR}" \
    -DCMAKE_TOOLCHAIN_FILE="${SCRIPT_DIR}/toolchain-mingw64.cmake" \
    -DCMAKE_BUILD_TYPE=Release \
    "${SCRIPT_DIR}"

# Bauen
cmake --build "${BUILD_DIR}" --config Release -j$(nproc)

# DLL nach dist/ kopieren
cp "${BUILD_DIR}/version.dll" "${DIST_DIR}/"

echo ""
echo "=== Build erfolgreich ==="
echo "Output: ${DIST_DIR}/version.dll"
echo ""

# Verifizierung
echo "=== DLL-Info ==="
file "${DIST_DIR}/version.dll"
x86_64-w64-mingw32-objdump -p "${DIST_DIR}/version.dll" | grep -A 50 "Export Table" || true
echo ""
echo "Groesse: $(du -h "${DIST_DIR}/version.dll" | cut -f1)"
```

## 6. .def Datei Einbindung in MinGW

MinGW unterstuetzt `.def`-Dateien direkt ueber den Linker:

```
# Variante 1: Via Linker-Flag (empfohlen)
x86_64-w64-mingw32-gcc -shared -o version.dll src/*.c exports.def -lversion -lkernel32

# Variante 2: Via CMake (wie oben gezeigt)
set_target_properties(version PROPERTIES
    LINK_FLAGS "-Wl,--kill-at ${CMAKE_CURRENT_SOURCE_DIR}/exports.def"
)
```

`--kill-at` ist WICHTIG: Entfernt die `@`-Dekoration von stdcall-Funktionen (nur relevant fuer x86, aber schadet nicht bei x64).

Die `.def`-Datei wird dem Linker als Input-Datei uebergeben. MinGW's `ld` versteht das `.def`-Format nativ.

## 7. Statisches Linking

KRITISCH: Die DLL darf KEINE Abhaengigkeiten auf MinGW-Runtime-DLLs haben:
- `libgcc_s_seh-1.dll` — DARF NICHT benoetigt werden
- `libwinpthread-1.dll` — DARF NICHT benoetigt werden

Loesung: Statisches Linking via Compiler/Linker-Flags:
```
-static-libgcc -static
```

Verifizierung nach dem Build:
```bash
x86_64-w64-mingw32-objdump -p dist/version.dll | grep "DLL Name"
# Sollte NUR zeigen:
#   KERNEL32.dll
#   VERSION.dll (die originale)
#   (evtl. msvcrt.dll oder api-ms-win-crt-*.dll)
```

## 8. Alternatives Build-System: Reines Makefile

Falls CMake nicht gewuenscht (einfacher fuer ein so kleines Projekt):

```makefile
# Makefile
CC = x86_64-w64-mingw32-gcc
CFLAGS = -Wall -Wextra -O2 -DUNICODE -D_UNICODE
LDFLAGS = -shared -static-libgcc -static -lkernel32 -luser32 -lversion -lshlwapi

SOURCES = src/main.c src/proxy.c src/logging.c
OBJECTS = $(SOURCES:.c=.o)

all: dist/version.dll

dist/version.dll: $(OBJECTS) exports.def
	mkdir -p dist
	$(CC) $(OBJECTS) exports.def -o $@ $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJECTS) dist/version.dll

.PHONY: all clean
```

Empfehlung: CMake verwenden, da es das Toolchain-File sauber handhabt und spaeter erweiterbar ist.

## 9. Continous Integration (optional, spaeter)

GitHub Actions Workflow fuer automatischen Build:
```yaml
# .github/workflows/build.yml
name: Build
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get install -y gcc-mingw-w64-x86-64
      - run: ./build.sh
      - uses: actions/upload-artifact@v4
        with:
          name: version-dll
          path: dist/version.dll
```

## 10. Zusammenfassung

| Aspekt | Entscheidung |
|---|---|
| Compiler | x86_64-w64-mingw32-gcc (MinGW-w64) |
| Build-System | CMake + Toolchain-Datei |
| Build-Script | build.sh (Wrapper um CMake) |
| Linking | Statisch (-static-libgcc -static) |
| Export-Definition | exports.def (native MinGW-Unterstuetzung) |
| Output | build/version.dll -> dist/version.dll |
| Abhaengigkeiten | NUR Windows System-DLLs (kernel32, version) |
| Sprache | C (kein C++ noetig — unser Code ist rein C) |
| OS | Linux (Arch/CachyOS) — kein Windows/MSVC |

## 11. Offene Punkte / Risiken

1. **MinGW muss erst installiert werden** — `sudo pacman -S mingw-w64-gcc`
2. **Statisches Linking testen** — sicherstellen dass keine MinGW-DLLs benoetigt werden
3. **Export-Ordinals** — muessen mit der Original version.dll uebereinstimmen (testen!)
4. **Unicode** — Wir kompilieren mit UNICODE, aber version.dll hat sowohl A- als auch W-Varianten
5. **`-Wl,--kill-at`** — Muss getestet werden ob es unter x64 Probleme macht (sollte harmlos sein)
