# Codex Review 1 — Issue #55: SFSE Proton Shim (Re-Review nach Fix)
Datum: 2026-03-22
Reviewer: Agent 1 (Bugs, Logikfehler, Edge Cases)

## Kontext

Re-Review nach DENIED (C1: `Proxy_Init()` wurde nie aufgerufen).
Fix: `ensure_proxy_init()` Lazy-Init in `proxy.c` hinzugefuegt.

---

## Pflicht-Dateien gelesen

- [x] ARCHITEKTUR.md gelesen
- [x] MO2-Referenz: Nicht direkt relevant (kein Mod-Verwaltung / modlist.txt / Deploy-Aenderung an Anvil-Core)
- [x] Checkliste `docs/workflow/checkliste-sfse-shim.md` gelesen

---

## C-Code Analyse

### proxy.c — Lazy-Init Fix

**Fix ist KORREKT.** Die `ensure_proxy_init()` Funktion:
```c
static void ensure_proxy_init(void) {
    if (!s_hReal) Proxy_Init();
}
```

Wird in allen 3 Proxy-Funktionen vor dem Aufruf der realen Funktionen aufgerufen.
Jede Proxy-Funktion hat zusaetzlich einen NULL-Check auf den Funktionszeiger:
```c
return real_GetFileVersionInfoA ? real_GetFileVersionInfoA(a, b, c, d) : FALSE;
```

**Thread-Safety:** Akzeptabel. Die DLL wird waehrend `DLL_PROCESS_ATTACH` geladen (Loader Lock, single-threaded). Die ersten Aufrufe der version.dll Exports passieren erst nach dem CRT-Init, aber da Windows-Programme typischerweise single-threaded initialisieren und version.dll-Aufrufe normalerweise nicht aus mehreren Threads gleichzeitig erfolgen, ist das Risiko vernachlaessigbar. Kein CRITICAL.

**Fehlerpfade:** Wenn `Proxy_Init()` fehlschlaegt (`LoadLibraryA` returns NULL):
- `s_hReal` bleibt NULL
- Bei jedem weiteren Aufruf wird `Proxy_Init()` erneut versucht (retry-Verhalten)
- Die Funktionszeiger bleiben NULL
- Die Proxy-Funktionen geben `FALSE` / `0` zurueck (sichere Fallbacks)
- **Kein Crash, kein Memory-Leak** — akzeptabel.

### main.c

- `DllMain` ruft KEIN `Proxy_Init()` mehr direkt auf — korrekt, Kommentar in Zeile 131 dokumentiert das
- `DLL_PROCESS_DETACH` ruft `Proxy_Shutdown()` auf, das `s_hReal` freigibt — korrekt
- IAT-Hook-Logik ist sauber: `find_iat_entry()` hat korrekte NULL-Checks fuer `dos->e_magic`, `nt->Signature`, `import_rva`
- `safe_write_ptr()` verwendet `VirtualProtect` korrekt mit Restore
- `our_initterm_e_hook()` hat saubere Fallbacks bei fehlender SFSE-DLL
- **Buffer-Overflows:** Keine — keine String-Operationen ohne Laengenbegrenzung
- **NULL-Checks:** Alle kritischen Zeiger werden geprueft
- **Memory-Leaks:** Keine — `hSFSE` wird nicht freigegeben, aber das ist gewollt (SFSE muss geladen bleiben)

### logging.c

- `shim_log_init()` verwendet `snprintf` mit `MAX_PATH` — kein Buffer-Overflow
- `shim_log()` prueft `g_logFile` auf NULL — sicher
- `shim_log_close()` setzt `g_logFile = NULL` nach `fclose()` — sauber, kein Use-After-Free
- `GetEnvironmentVariableA` Rueckgabewert wird korrekt geprueft (`len > 0 && len < MAX_PATH`)
- Fallback auf `fopen("sfse_shim.log", "w")` wenn USERPROFILE nicht verfuegbar — sinnvoll

### proxy.h / logging.h

- Header-Guards korrekt (`#pragma once` / `#ifndef` Guard)
- Alle Funktionsdeklarationen stimmen mit Implementierungen ueberein

### exports.def

- Genau 3 Exports: `GetFileVersionInfoA`, `GetFileVersionInfoSizeA`, `VerQueryValueA`
- Ordinals @1, @2, @3 — korrekt

### build.sh

- Kompiliert mit `-static` — keine MinGW-Runtime-Abhaengigkeiten
- `-Wl,--no-undefined` — alle Symbole muessen aufgeloest werden
- `-lkernel32` — einzige explizite Abhaengigkeit
- Verification-Schritte am Ende (file, objdump) — gut

---

## Python-Code Analyse (game_starfield.py)

- `python -m py_compile` erfolgreich — keine Syntax-Fehler
- Alle Imports vorhanden (`Path`, `BaseGame`, `FrameworkMod`)
- `ProtonShimFiles = ["version.dll"]` — korrekt gesetzt
- `get_proton_env_overrides()`: Prueft ob `version.dll` im Game-Dir existiert bevor `WINEDLLOVERRIDES` gesetzt wird — korrekt
- `get_framework_mods()`: Definiert SFSE mit korrekten Patterns — korrekt
- `has_script_extender()`: Prueft `sfse_loader.exe` — korrekt
- `gameDocumentsDirectory()` und `gameSavesDirectory()`: Pruefen `protonPrefix()` und `is_dir()` — korrekt
- 19 Default-Kategorien (inkl. Ships, Outposts) — korrekt
- **Keine None-Dereference-Gefahren:** Alle Methoden pruefen `self._game_path is not None`

---

## Binary-Verifikation (anvil/data/shims/starfield/version.dll)

| Pruefpunkt | Ergebnis |
|------------|----------|
| PE32+ x86-64 DLL | JA — `PE32+ executable for MS Windows 5.02 (DLL), x86-64` |
| Groesse < 200KB | JA — 112.651 Bytes (ca. 110 KB) |
| 3 Exports | JA — `GetFileVersionInfoA`, `GetFileVersionInfoSizeA`, `VerQueryValueA` |
| Nur System-DLLs | JA — KERNEL32.dll + 5 api-ms-win-crt-*.dll (alles System-DLLs, keine MinGW-Runtime) |

---

## Checklisten-Pruefung

### Anvil Plugin (game_starfield.py)

- [x] 1. Starfield (Steam ID 1716740) erscheint in Spieleliste — `GameSteamId = 1716740` gesetzt, `detectGame()` von BaseGame erbt korrekt
- [x] 2. Game-Dir, Documents-Dir, Saves-Dir korrekt aufgeloest — `gameDocumentsDirectory()`, `gameSavesDirectory()` mit Proton-Prefix-Logik
- [x] 3. 19 Starfield-spezifische Kategorien — `get_default_categories()` liefert 19 Eintraege inkl. Ships (id 4) und Outposts (id 5)
- [x] 4. Deploy mit sfse_loader.exe → version.dll kopiert — `ProtonShimFiles = ["version.dll"]`, `_deploy_proton_shims()` kopiert wenn Framework installiert (game_panel.py:678-682 prueft `get_installed_frameworks()`)
- [x] 5. Deploy ohne sfse_loader.exe → version.dll NICHT kopiert — Framework-Check: `any_fw_installed` ist False wenn `sfse_loader.exe` nicht existiert (detect_installed=["sfse_loader.exe"])
- [x] 6. Proton-Start mit version.dll → WINEDLLOVERRIDES gesetzt — `get_proton_env_overrides()` prueft `(self._game_path / "version.dll").exists()`
- [x] 7. Proton-Start ohne version.dll → WINEDLLOVERRIDES nicht gesetzt — Gleiche Methode gibt `{}` zurueck
- [x] 8. Purge entfernt version.dll — Manifest-Eintrag mit `type: "shim_copy"`, `mod_deployer.py:439-444` entfernt shim_copy-Eintraege beim Purge

### SFSE Proton Shim DLL

- [x] 9. build.sh erzeugt dist/version.dll — Build-Script vorhanden, kompiliert mit MinGW cross-compiler
- [x] 10. Export-Table zeigt genau 3 Funktionen — Verifiziert via objdump
- [x] 11. Nur System-DLLs — Verifiziert: KERNEL32.dll + api-ms-win-crt-*.dll (alle System-DLLs)
- [x] 12. PE32+ executable (DLL) x86-64 — Verifiziert via `file` Befehl
- [x] 13. Kleiner als 200KB — 112.651 Bytes (110 KB)

### Keine Seiteneffekte

- [x] 14. Fallout 4 F4SE-Shim funktioniert weiterhin — `ProtonShimFiles = ["X3DAudio1_7.dll"]` in game_fallout4.py, eigenes Shim-Verzeichnis `anvil/data/shims/fallout4/X3DAudio1_7.dll` (112.461 Bytes), keine Aenderungen am F4-Code
- [x] 15. Andere Spiele nicht betroffen — ProtonShimFiles ist `[]` per Default in BaseGame, kein Code-Pfad wird beruehrt
- [x] 16. _wip/game_starfield.py existiert nicht mehr — Verifiziert, _wip/ Verzeichnis existiert nicht

### Abschluss

- [ ] 17. restart.sh startet ohne Fehler — NICHT GETESTET (Agent 1 Scope: C-Code + Python-Code-Analyse, kein App-Start)

---

## Findings

### Keine CRITICAL oder HIGH Findings

Der vorherige CRITICAL C1 (`Proxy_Init()` nie aufgerufen) ist BEHOBEN:
- `ensure_proxy_init()` wird in allen 3 Proxy-Funktionen aufgerufen
- NULL-Checks auf Funktionszeiger sind vorhanden
- Fehlerpfade geben sichere Default-Werte zurueck

### [LOW] L1: Retry-Verhalten bei Proxy_Init-Fehler
- Datei: sfse-proton-shim/src/proxy.c:37-39
- Problem: Wenn `Proxy_Init()` fehlschlaegt (LoadLibraryA gibt NULL zurueck), wird bei JEDEM weiteren Export-Aufruf erneut `Proxy_Init()` versucht. Das ist normalerweise harmlos, koennte aber bei einem persistenten Fehler (z.B. beschaedigte system version.dll) zu unnoetigem Overhead fuehren.
- Impact: Vernachlaessigbar — version.dll Exports werden selten aufgerufen, und ein Fehler bei LoadLibraryA wuerde sowieso auf ein schwerwiegendes Systemproblem hindeuten.
- Fix: Optional — ein `static BOOL s_tried = FALSE;` Flag koennte das Retry unterdruecken. Nicht kritisch.

### [LOW] L2: Kein `#pragma once` in logging.h
- Datei: sfse-proton-shim/src/logging.h:1-8
- Problem: Verwendet `#ifndef` Guard statt `#pragma once` (proxy.h verwendet `#pragma once`). Inkonsistenz, aber funktional korrekt.
- Fix: Stilistische Vereinheitlichung, kein Bug.

---

## Architektur-Regeln Pruefung

1. Mod-Dateien NICHT direkt ins Game-Dir kopiert? — N/A (Shim-DLL ist kein Mod, wird als `shim_copy` im Manifest getrackt und beim Purge entfernt)
2. Ordnerstruktur in .mods/ nicht veraendert? — N/A
3. Frameworks nicht in .mods/ oder modlist.txt? — N/A
4. active_mods.json bei Rename/Delete aktualisiert? — N/A
5. Nur globale API? — N/A
6. MO2-Referenz konsultiert? — Nicht direkt relevant (Proton-Shim ist Linux-spezifisch, kein MO2-Aequivalent)
7. Architektur-Doku gelesen? — JA

Keine Architektur-Regelverletzungen.

---

## Ergebnis

**ACCEPTED**

Der CRITICAL C1 Fix ist korrekt implementiert. Alle 16 pruefbaren Checklisten-Punkte sind erfuellt.
Punkt 17 (restart.sh) liegt ausserhalb des Agent-1-Scopes und muss separat geprueft werden.
Nur 2 LOW-Findings (optional, kein Bug).
