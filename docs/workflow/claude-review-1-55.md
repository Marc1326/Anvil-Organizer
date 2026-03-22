# Claude Review 1 — Issue #55: SFSE Proton Shim (Architektur-Konformitaet)
Datum: 2026-03-22
Reviewer: Claude Code (Architektur + MO2-Vergleich)

## Pflicht-Dateien gelesen
- [x] ARCHITEKTUR.md gelesen
- [x] MO2-Referenz: Nicht direkt anwendbar (kein MO2-Aequivalent fuer Proton Shims)
- [x] F4SE-Proton-Shim Referenz gelesen (`/home/mob/Projekte/f4se-proton-shim/src/`)

## 7 Architektur-Regeln

1. **Mod-Dateien NICHT direkt ins Game-Verzeichnis?** -- KONFORM. Die Shim-DLL wird als `shim_copy` deployed (nicht als Mod-Datei) und beim Purge entfernt. Normale Mods nutzen Symlinks. Die version.dll ist kein Mod, sondern ein Framework-Hilfsmittel.

2. **Ordnerstruktur in .mods/ NICHT veraendert?** -- KONFORM. Shim-DLLs liegen in `anvil/data/shims/starfield/`, nicht in `.mods/`.

3. **Frameworks NICHT in .mods/ oder modlist.txt?** -- KONFORM. Die Shim-DLL ist kein Framework-Eintrag in modlist.txt. SFSE selbst wird als Framework behandelt und liegt nicht in modlist.txt.

4. **Rename/Delete: active_mods.json in ALLEN Profilen?** -- NICHT BETROFFEN. Kein Rename/Delete involviert.

5. **NUR globale API?** -- KONFORM. Keine per-Profile modlist.txt Manipulation.

6. **MO2-Referenz konsultiert?** -- MO2 hat kein Proton-Shim-Konzept (Windows-only). Das Feature ist eine bewusste Anvil-Erweiterung, dokumentiert in ARCHITEKTUR.md unter GameCopyDeployPaths/Shim-Logik.

7. **Architektur-Doku gelesen?** -- Ja.

**Ergebnis: Alle 7 Regeln bestanden.**

## Checklisten-Pruefung (docs/workflow/checkliste-sfse-shim.md)

### Anvil Plugin (game_starfield.py)

- [x] **1. Starfield (Steam ID 1716740) in Spieleliste** -- `GameSteamId = 1716740` korrekt gesetzt. detectGame() iteriert Steam-IDs. KONFORM.

- [x] **2. Game-Dir, Documents-Dir, Saves-Dir korrekt aufgeloest** -- `gameDocumentsDirectory()` und `gameSavesDirectory()` nutzen `protonPrefix()` + `_WIN_DOCUMENTS`/`_WIN_SAVES`. Muster identisch zu Fallout 4. KONFORM.

- [x] **3. 19 Starfield-spezifische Kategorien** -- `get_default_categories()` liefert 19 Kategorien (IDs 1-19), inkl. "Ships" (ID 4) und "Outposts" (ID 5). KONFORM.

- [x] **4. Deploy: version.dll kopiert wenn sfse_loader.exe vorhanden** -- `ProtonShimFiles = ["version.dll"]`. Deploy-Logik in game_panel.py (Zeile 671-682): prueft `get_installed_frameworks()` → SFSE hat `detect_installed=["sfse_loader.exe"]`. Nur wenn sfse_loader.exe existiert, wird `_deploy_proton_shims()` aufgerufen. KONFORM.

- [x] **5. Deploy: version.dll NICHT kopiert wenn sfse_loader.exe fehlt** -- Die Bedingung `any_fw_installed = any(installed for _fw, installed in fw_list)` stellt sicher, dass ohne installiertes Framework kein Shim deployed wird. KONFORM.

- [x] **6. WINEDLLOVERRIDES=version=n,b bei Proton-Start** -- `get_proton_env_overrides()` prueft `(self._game_path / "version.dll").exists()` und gibt `{"WINEDLLOVERRIDES": "version=n,b"}` zurueck. game_panel.py Zeile 1148-1154 wendet das auf die Proton-Umgebung an. KONFORM.

- [x] **7. WINEDLLOVERRIDES nicht gesetzt ohne version.dll** -- Wenn `version.dll` nicht existiert, gibt `get_proton_env_overrides()` leeres dict zurueck. KONFORM.

- [x] **8. Purge entfernt version.dll** -- Die Shim-DLL wird im Manifest mit `type: "shim_copy"` registriert (game_panel.py Zeile 777-778). mod_deployer.py Zeile 439-444 entfernt `shim_copy`-Eintraege beim Purge mit `unlink(missing_ok=True)`. KONFORM.

### SFSE Proton Shim DLL

- [x] **9. build.sh erzeugt dist/version.dll als PE32+ x86-64** -- Build-Script nutzt `x86_64-w64-mingw32-gcc` mit `-shared -static`. Die kompilierte DLL in `anvil/data/shims/starfield/version.dll` ist: `PE32+ executable for MS Windows 5.02 (DLL), x86-64, 20 sections`. KONFORM.

- [x] **10. Export-Table: 3 Funktionen** -- objdump zeigt exakt:
  - `GetFileVersionInfoA` (Ordinal 1)
  - `GetFileVersionInfoSizeA` (Ordinal 2)
  - `VerQueryValueA` (Ordinal 3)
  KONFORM.

- [x] **11. Nur System-DLLs importiert** -- DLL-Imports:
  - `KERNEL32.dll`
  - `api-ms-win-crt-heap-l1-1-0.dll`
  - `api-ms-win-crt-private-l1-1-0.dll`
  - `api-ms-win-crt-runtime-l1-1-0.dll`
  - `api-ms-win-crt-stdio-l1-1-0.dll`
  - `api-ms-win-crt-string-l1-1-0.dll`
  Keine MinGW-Runtime-DLLs (libgcc, libstdc++, etc.). KONFORM.

- [x] **12. file zeigt PE32+ DLL** -- `PE32+ executable for MS Windows 5.02 (DLL), x86-64` -- Hinweis: `(console)` fehlt, stattdessen steht `for MS Windows 5.02`. Das ist ein Unterschied in der `file`-Ausgabe je nach Version, aber die DLL ist korrekt als PE32+ x86-64 DLL identifiziert. KONFORM.

- [x] **13. version.dll < 200KB** -- Groesse: 112.651 Bytes (110 KB). KONFORM.

### Keine Seiteneffekte

- [x] **14. F4SE-Shim funktioniert weiterhin** -- game_fallout4.py ist unveraendert. `ProtonShimFiles = ["X3DAudio1_7.dll"]` und `anvil/data/shims/fallout4/X3DAudio1_7.dll` existieren weiterhin. KONFORM.

- [x] **15. Andere Spiele unveraendert** -- Nur game_starfield.py hinzugefuegt. Andere Plugins nicht modifiziert. KONFORM.

- [x] **16. _wip/game_starfield.py nicht mehr existent** -- `ls` in `_wip/` zeigt: game_starfield.py ist dort NICHT vorhanden. Es existiert korrekt unter `anvil/plugins/games/game_starfield.py`. KONFORM.

- [ ] **17. restart.sh startet ohne Fehler** -- NICHT GEPRUEFT (kein App-Test in diesem Review-Schritt).

## Architektur-Vergleich: SFSE-Shim vs F4SE-Shim

### main.c Vergleich

| Aspekt | F4SE-Shim | SFSE-Shim | Bewertung |
|--------|-----------|-----------|-----------|
| Proxy-DLL | X3DAudio1_7.dll | version.dll | Korrekt: Starfield importiert version.dll, nicht X3DAudio |
| Ziel-DLL | f4se_1_11_191.dll | sfse_1_15_222.dll | Korrekt: SFSE Version fuer Starfield |
| Start-Funktion | StartF4SE() | StartSFSE() | Korrekt: SFSE-API |
| IAT-Hook Target | _initterm_e via api-ms-win-crt-runtime-l1-1-0.dll | Identisch | Korrekt: gleiches CRT-Pattern |
| DllMain Struktur | Identisch | Identisch | Korrekt |
| DLL_PROCESS_DETACH | proxy_cleanup() | Proxy_Shutdown() | Unterschiedliche Benennung, korrekt |

### proxy.c Vergleich

| Aspekt | F4SE-Shim | SFSE-Shim | Bewertung |
|--------|-----------|-----------|-----------|
| Lazy-Init Pattern | g_proxyInitDone Flag + proxy_init_deferred() | ensure_proxy_init() checkt s_hReal | SFSE-Variante korrekter (kein extra Flag noetig) |
| Proxy-Exports | X3DAudioInitialize, X3DAudioCalculate (2 Exporte) | GetFileVersionInfoA, GetFileVersionInfoSizeA, VerQueryValueA (3 Exporte) | Korrekt: version.dll hat 3 Exporte |
| NULL-Safety | Prueft Funktionspointer vor Aufruf | Prueft Funktionspointer vor Aufruf | Korrekt |
| System-DLL Laden | GetSystemDirectoryA + LoadLibrary | GetSystemDirectoryA + LoadLibrary | Identisches Pattern |
| Shutdown | FreeLibrary in proxy_cleanup() | FreeLibrary in Proxy_Shutdown() | Korrekt |

### Lazy-Init Bewertung (Fix fuer Issue #55)

Der Fix verschiebt `Proxy_Init()` von `DllMain(DLL_PROCESS_ATTACH)` zu `ensure_proxy_init()` (lazy, beim ersten Proxy-Funktionsaufruf). Das ist **architektonisch korrekt** weil:

1. **Windows Loader Lock:** `LoadLibraryA()` in `DllMain` ist gegen die Microsoft-Dokumentation (kann zu Deadlocks fuehren). Lazy-Init vermeidet das.
2. **Proton-Kompatibilitaet:** Wine/Proton hat strengere Loader-Lock-Enforcement als nativer Windows.
3. **Identisches Pattern wie F4SE:** Beide Shims nutzen jetzt Lazy-Init (F4SE mit Flag, SFSE mit NULL-Check).
4. **Thread-Safety:** In diesem Kontext kein Problem, da die Proxy-Funktionen erst aufgerufen werden wenn der CRT-Init abgeschlossen ist. Mehrfach-Init durch NULL-Check auf `s_hReal` verhindert.

## Observations (kein Finding, nur Information)

### [INFO] Hardcoded SFSE-DLL-Version
- Datei: `/home/mob/Projekte/sfse-proton-shim/src/main.c:90`
- `sfse_1_15_222.dll` ist hart kodiert. Bei SFSE-Updates muss die DLL neu kompiliert werden.
- Das ist identisch zum F4SE-Shim (`f4se_1_11_191.dll`). Bekanntes Muster, kein Bug.

### [INFO] SFSE-Pattern Mismatch in game_starfield.py
- Datei: `anvil/plugins/games/game_starfield.py:188`
- FrameworkMod pattern enthaelt `sfse_1_0_0.dll` -- das ist ein Archiv-Erkennungs-Pattern, nicht die Runtime-DLL.
- Kein Bug: Das Pattern wird zum Erkennen von SFSE-Archiven bei der Installation verwendet, nicht zum Laden der DLL.

### [INFO] Naming Convention Unterschied
- F4SE-Shim: `proxy_cleanup()`, `proxy_init()` (lowercase)
- SFSE-Shim: `Proxy_Shutdown()`, `Proxy_Init()` (CamelCase)
- Kein funktionaler Bug, aber stilistisch inkonsistent. Kosmetisch.

## Findings

Keine CRITICAL, HIGH oder MEDIUM Findings.

### [LOW] Punkt 17 der Checkliste nicht geprueft
- Problem: `restart.sh` wurde nicht ausgefuehrt (kein App-Test in diesem Review-Durchlauf)
- Empfehlung: Muss im separaten Funktionstest geprueft werden

## Ergebnis

**ACCEPTED**

Alle 16 von 17 Checklisten-Punkten bestanden. Punkt 17 (restart.sh) ist ein Laufzeit-Test, der in einem separaten Durchlauf geprueft werden muss.

Die SFSE-Shim-Implementierung ist eine korrekte Adaption des bewaehrten F4SE-Shims:
- Identische IAT-Hook-Strategie
- Korrekte Proxy-Exports fuer version.dll (3 Funktionen)
- Lazy-Init in proxy.c behebt den Issue-#55-Crash (LoadLibrary waehrend Loader Lock)
- game_starfield.py folgt exakt dem Muster von game_fallout4.py
- Deploy/Purge-Logik korrekt integriert ueber ProtonShimFiles + shim_copy Manifest
- Keine Seiteneffekte auf bestehende Spiel-Plugins
