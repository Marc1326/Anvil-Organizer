# Feature: Starfield Plugin aktivieren + SFSE Proton Shim
Datum: 2026-03-22
GitHub Issue: #55

## User Stories
- Als User moechte ich Starfield als unterstuetztes Spiel in Anvil sehen, damit ich Starfield-Mods verwalten kann.
- Als User moechte ich, dass SFSE (Starfield Script Extender) unter Proton/Wine funktioniert, ohne manuell DLLs kopieren zu muessen.
- Als User moechte ich, dass beim Deploy automatisch die SFSE Proton Shim (version.dll) ins Spielverzeichnis kopiert wird, wenn SFSE installiert ist.
- Als User moechte ich, dass WINEDLLOVERRIDES automatisch gesetzt werden, wenn ich Starfield ueber Proton starte.

## Technische Analyse

### Bestehender Code: game_starfield.py (_wip)
Das Plugin existiert bereits vollstaendig in `anvil/plugins/games/_wip/game_starfield.py`:
- Klasse `StarfieldGame(BaseGame)` mit allen Basis-Attributen
- `GameSteamId = 1716740`, `GameNexusId = 4187`
- `GameShortName = "Starfield"` (wird zu `"starfield"` via `.lower()` fuer Shim-Pfad)
- Documents/Saves/plugins.txt Pfade korrekt definiert
- SFSE-Erkennung (`_SFSE_BINARY = "sfse_loader.exe"`)
- `executables()`, `iniFiles()`, `get_framework_mods()`, `get_conflict_ignores()` implementiert
- **FEHLT:** `ProtonShimFiles`, `get_proton_env_overrides()`, `get_default_categories()`

### Referenz: game_fallout4.py
Fallout 4 hat alle drei fehlenden Features implementiert:
- `ProtonShimFiles = ["X3DAudio1_7.dll"]`
- `get_proton_env_overrides()`: Prueft ob Shim-DLL im Spielordner existiert, gibt WINEDLLOVERRIDES zurueck
- `get_default_categories()`: 19 Kategorien

### Referenz: F4SE Proton Shim Projekt
Das Projekt `/home/mob/Projekte/f4se-proton-shim/` dient als Vorlage:
- **main.c**: IAT-Hook fuer `_initterm_e`, laedt F4SE-DLL, ruft StartF4SE() auf
- **proxy.c**: Laedt original X3DAudio1_7.dll aus system32, forwarded 2 Exports
- **exports.def**: LIBRARY + 2 Exports
- **logging.c/h**: Logfile in My Games/Fallout4/F4SE/f4se_shim.log
- **build.sh**: MinGW-w64 Cross-Compilation

### Shim-Deployment Mechanismus in Anvil
Der bestehende Mechanismus in `game_panel.py` funktioniert generisch:
1. `silent_deploy()` prueft `plugin.ProtonShimFiles`
2. Prueft ob ein Framework installiert ist (`get_installed_frameworks()`)
3. Kopiert DLLs aus `anvil/data/shims/<GameShortName.lower()>/` ins Spielverzeichnis
4. Traegt Eintraege im Deploy-Manifest ein (Typ `shim_copy`)
5. Beim Launch setzt `_launch_via_proton()` die `WINEDLLOVERRIDES` via `get_proton_env_overrides()`

## Technische Planung

### Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `anvil/plugins/games/game_starfield.py` | VERSCHOBEN von `_wip/`, ergaenzt um `ProtonShimFiles`, `get_proton_env_overrides()`, `get_default_categories()` |
| `anvil/data/shims/starfield/version.dll` | NEU: Kompilierte SFSE Proton Shim DLL |
| `/home/mob/Projekte/sfse-proton-shim/src/main.c` | NEU: IAT-Hook, laedt `sfse_1_15_222.dll`, ruft `StartSFSE()` |
| `/home/mob/Projekte/sfse-proton-shim/src/proxy.c` | NEU: Laedt original `version.dll`, forwarded 3 Exports |
| `/home/mob/Projekte/sfse-proton-shim/src/proxy.h` | NEU: Header fuer proxy.c |
| `/home/mob/Projekte/sfse-proton-shim/src/logging.c` | NEU: Logging nach `My Games/Starfield/SFSE/sfse_shim.log` |
| `/home/mob/Projekte/sfse-proton-shim/src/logging.h` | NEU: Header fuer logging.c |
| `/home/mob/Projekte/sfse-proton-shim/exports.def` | NEU: `LIBRARY version.dll` + 3 Exports |
| `/home/mob/Projekte/sfse-proton-shim/build.sh` | NEU: MinGW-w64 Build, Output `dist/version.dll` |

### Unterschiede F4SE Shim vs SFSE Shim

| Aspekt | F4SE Shim | SFSE Shim |
|--------|-----------|-----------|
| Proxy-DLL | X3DAudio1_7.dll | version.dll |
| Proxy-Exports | 2 | 3 (GetFileVersionInfoA, GetFileVersionInfoSizeA, VerQueryValueA) |
| SE-DLL | f4se_1_11_191.dll | sfse_1_15_222.dll |
| SE-Startfunktion | StartF4SE | StartSFSE |
| Log-Verzeichnis | My Games/Fallout4/F4SE/ | My Games/Starfield/SFSE/ |
| Log-Datei | f4se_shim.log | sfse_shim.log |
| IAT-DLL | api-ms-win-crt-runtime-l1-1-0.dll | api-ms-win-crt-runtime-l1-1-0.dll (gleich) |
| IAT-Funktion | _initterm_e | _initterm_e (gleich) |

### Aenderungen an game_starfield.py (Detail)

**1. Neues Klassen-Attribut:**
```python
ProtonShimFiles = ["version.dll"]
```

**2. get_proton_env_overrides():**
```python
def get_proton_env_overrides(self) -> dict[str, str]:
    if self._game_path is None:
        return {}
    if (self._game_path / "version.dll").exists():
        return {"WINEDLLOVERRIDES": "version=n,b"}
    return {}
```

**3. get_default_categories():** 19 Starfield-spezifische Kategorien (Ships, Outposts, etc.)

### Signal-Flow

```
silent_deploy()
  -> prueft plugin.ProtonShimFiles = ["version.dll"]
  -> prueft get_installed_frameworks() -> SFSE installiert?
  -> _deploy_proton_shims(["version.dll"])
     -> kopiert anvil/data/shims/starfield/version.dll -> game_path/version.dll
     -> manifest-Eintrag (type: shim_copy)

_launch_via_proton()
  -> plugin.get_proton_env_overrides()
     -> prueft game_path/version.dll existiert
     -> return {"WINEDLLOVERRIDES": "version=n,b"}
  -> env["WINEDLLOVERRIDES"] = "version=n,b"
```

## Akzeptanz-Kriterien

Siehe `docs/workflow/checkliste-sfse-shim.md`
