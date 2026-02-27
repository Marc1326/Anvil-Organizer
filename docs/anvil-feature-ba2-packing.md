# Feature-Spec: BA2-Packing fuer Bethesda-Spiele

**Status:** Geplant
**Datum:** 2026-02-27
**Betrifft:** Fallout 4, Skyrim SE (spaeter: Starfield)

---

## 1. Problem

Bethesda-Spiele unter Proton/Linux ignorieren loose files in `Data/`.
Symlinks, Kopien und fuse-overlayfs funktionieren alle nicht.
Nur BA2-Archive werden zuverlaessig von der Game-Engine geladen.

MO2 loest das Problem via VFS (Virtual File System / DLL-Injection).
Das funktioniert unter Proton nicht. Anvil Organizer muss daher
Mod-Dateien in BA2-Archive packen.

## 2. Loesung

Beim Deploy werden Mod-Dateien in BA2-Archive gepackt statt als Symlinks deployed.

| Dateityp | Deploy-Methode |
|----------|---------------|
| .esp/.esm/.esl | Symlink nach Data/ (wie bisher) |
| .dll/.exe (F4SE/SKSE) | Copy / DirectInstall (wie bisher) |
| .ba2/.bsa (vorhandene Archive) | Symlink nach Data/ (wie bisher) |
| .ini/.cfg | Symlink (wie bisher) |
| .dds (Texturen) | BA2 packen (DX10 Format, separates Archiv) |
| .nif/.wav/.xwm/.pex/.hkx/etc. | BA2 packen (General-Archiv) |

**Tool:** BSArch (Windows CLI, laeuft via Proton)
- Download: https://www.nexusmods.com/newvegas/mods/64745
- `bsarch pack <dir> <output.ba2> -fo4 -mt` (Fallout 4)
- `bsarch pack <dir> <output.ba2> -sse -mt` (Skyrim SE)
- `bsarch pack <dir> <output.ba2> -fo4dds -mt` (FO4 Texturen, DX10)

## 3. Architektur

### 3.1 Neue Dateien

| Datei | Beschreibung |
|-------|-------------|
| `anvil/core/ba2_packer.py` | BA2Packer-Klasse: Staging, BSArch-Aufruf, Cleanup |

### 3.2 Geaenderte Dateien

| Datei | Aenderung |
|-------|-----------|
| `anvil/plugins/base_game.py` | Neue Klassen-Attribute + `ba2_ini_path()` Methode |
| `anvil/plugins/games/game_fallout4.py` | BA2-Attribute setzen |
| `anvil/plugins/games/_wip/game_skyrimse.py` | BA2-Attribute setzen |
| `anvil/core/mod_deployer.py` | Neuer Parameter `needs_ba2_packing`, Dateikategorisierung |
| `anvil/widgets/game_panel.py` | BA2Packer in silent_deploy/silent_purge einhaengen |

### 3.3 NICHT geaenderte Dateien

| Datei | Begruendung |
|-------|-------------|
| `anvil/core/plugins_txt_writer.py` | `_PLUGIN_EXTENSIONS = {".esp", ".esm", ".esl"}` filtert BA2 bereits aus |
| `game_cyberpunk2077.py` | Erbt `NeedsBa2Packing = False` (Default) |
| `game_rdr2.py` | Erbt Default |
| `game_witcher3.py` | Erbt Default |
| `game_baldursgate3.py` | Erbt Default |

## 4. Detailplan

### 4.1 base_game.py -- Neue Klassen-Attribute

```python
# Nach PRIMARY_PLUGINS (Zeile ~111):

NeedsBa2Packing: bool = False
"""If True, loose mod files are packed into BA2 archives during deploy."""

Ba2Format: str = ""
"""BSArch format flag for general assets ('fo4', 'sse')."""

Ba2TextureFormat: str = ""
"""BSArch format flag for textures ('fo4dds', 'sse')."""

Ba2IniSection: str = ""
"""INI section for archive registration ('Archive')."""

Ba2IniKey: str = ""
"""INI key for archive list ('sResourceArchive2List')."""

Ba2IniFile: str = ""
"""Custom INI filename ('Fallout4Custom.ini')."""
```

Neue Methode (nach `plugins_txt_path()`):

```python
def ba2_ini_path(self) -> Path | None:
    """Return absolute path to the BA2 registration INI file."""
    if not self.NeedsBa2Packing or not self.Ba2IniFile:
        return None
    docs = self.gameDocumentsDirectory()
    if docs is not None:
        return docs / self.Ba2IniFile
    return None
```

**Begruendung fuer Attribute statt Config-Methode:**
- Konsistent mit bestehendem Pattern (GameDataPath, GameSteamId, etc.)
- Einfacher Zugriff via `getattr(plugin, "NeedsBa2Packing", False)`
- IDE-Autocomplete, Type-Hints, statische Pruefung
- Nicht-Bethesda-Spiele erben Default ohne Codeaenderung

### 4.2 game_fallout4.py -- BA2-Config

```python
# Nach PRIMARY_PLUGINS:

NeedsBa2Packing = True
Ba2Format = "fo4"             # BSArch: -fo4 -mt
Ba2TextureFormat = "fo4dds"   # BSArch: -fo4dds -mt
Ba2IniSection = "Archive"
Ba2IniKey = "sResourceArchive2List"
Ba2IniFile = "Fallout4Custom.ini"
```

### 4.3 game_skyrimse.py -- BA2-Config

```python
NeedsBa2Packing = True
Ba2Format = "sse"             # BSArch: -sse -mt
Ba2TextureFormat = "sse"      # SSE Texturen: gleiches Flag
Ba2IniSection = "Archive"
Ba2IniKey = "sResourceArchiveList2"   # ACHTUNG: "List2" nicht "2List"!
Ba2IniFile = "SkyrimCustom.ini"
```

**Stolperstein:** Fallout 4 = `sResourceArchive2List`, Skyrim SE = `sResourceArchiveList2`.

### 4.4 ba2_packer.py -- Neue Klasse

```python
class BA2Packer:
    """Pack mod files into BA2 archives using BSArch via Proton."""

    BA2_PREFIX = "anvil_"

    SKIP_EXTENSIONS = {".esp", ".esm", ".esl", ".dll", ".exe", ".ini",
                       ".cfg", ".toml", ".ba2", ".bsa"}
    TEXTURE_EXTENSIONS = {".dds"}

    def __init__(self, game_plugin, instance_path, bsarch_path=None):
        ...

    # -- BSArch finden --
    def find_bsarch(self) -> Path | None
        # Suchorder: 1) Explizit  2) QSettings  3) Instance-Tools  4) Global-Tools

    # -- Proton-Env aufbauen --
    def _get_proton_env(self) -> tuple[Path, dict] | None
        # Nutzt game_plugin.findProtonRun()

    # -- Dateien klassifizieren --
    @staticmethod
    def _classify_file(rel_path) -> str  # "skip" | "texture" | "general"

    # -- Staging aufbauen --
    def _stage_mod_files(self, mod_dir, staging_dir) -> tuple[int, int, int, int]
        # Kopiert (nicht linkt!) Dateien in staging/general/ und staging/textures/

    # -- BSArch ausfuehren --
    def _run_bsarch(self, source_dir, output_ba2, is_textures=False) -> tuple[bool, str]
        # subprocess: proton run BSArch.exe pack <dir> <out> <format> [-mt]
        # Timeout: 300s

    # -- Oeffentliche API --
    def pack_mod(self, mod_name) -> PackResult
        # 1 Mod -> 0-2 BA2-Dateien (General + Textures)
        # Output: Data/anvil_<name>.ba2, Data/anvil_<name> - Textures.ba2

    def pack_all_mods(self, enabled_mods) -> PackAllResult
        # Alle Mods -> Pre-flight (BSArch+Proton), cleanup, pack pro Mod

    def cleanup_ba2s(self) -> int
        # Loescht NUR anvil_*.ba2 aus Data/

    def is_available(self) -> bool
        # BSArch + Proton vorhanden?
```

#### Namenskonvention BA2:
- `anvil_<sanitized_modname>.ba2` (General: Meshes, Sounds, Scripts)
- `anvil_<sanitized_modname> - Textures.ba2` (DDS-Texturen)
- Prefix `anvil_` garantiert sicheres Cleanup (Original-BA2s unberuehrt)

#### Sanitize-Regeln:
- Windows-ungueltige Zeichen entfernen: `<>:"/\|?*`
- Mehrfach-Unterstriche/Spaces kollabieren
- Max 200 Zeichen (BA2-Pfadlaenge unter Windows)

### 4.5 mod_deployer.py -- Erweiterung

Constructor: Neuer Parameter `needs_ba2_packing: bool = False`

Deploy-Flow Aenderung (im rglob-Loop):

```python
# Wenn BA2-Packing aktiv: Dateien kategorisieren
if self._needs_ba2_packing:
    ext = src_file.suffix.lower()
    if ext not in _BA2_SYMLINK_EXTENSIONS:
        # Datei wird NICHT symlinked -- BA2Packer kuemmert sich
        continue

# _BA2_SYMLINK_EXTENSIONS = {".esp", ".esm", ".esl", ".dll", ".exe",
#                             ".ini", ".cfg", ".ba2", ".bsa"}
```

Purge-Flow Erweiterung:

```python
# Nach Symlink-Entfernung:
for ba2_rel in manifest.get("ba2_archives", []):
    ba2_path = game_path / ba2_rel
    if ba2_path.is_file():
        ba2_path.unlink()

# INI-Backup wiederherstellen
ini_backup = manifest.get("ini_backup")
if ini_backup:
    # Backup-Datei zurueck kopieren
```

Manifest-Erweiterung:

```json
{
    "deployed_at": "...",
    "game_path": "...",
    "instance_path": "...",
    "symlinks": [...],
    "created_dirs": [...],
    "ba2_archives": [
        "Data/anvil_ModA.ba2",
        "Data/anvil_ModA - Textures.ba2"
    ],
    "ini_backup": {
        "file": "Fallout4Custom.ini",
        "backup_path": "Fallout4Custom.ini.anvil_backup"
    }
}
```

### 4.6 game_panel.py -- Integration

```python
def silent_deploy(self) -> None:
    if self._deployer:
        self._deployer.deploy()

    # BA2-Packing fuer Bethesda-Spiele
    needs_ba2 = getattr(self._current_plugin, "NeedsBa2Packing", False)
    if needs_ba2 and self._current_game_path and self._instance_path:
        from anvil.core.ba2_packer import BA2Packer
        packer = BA2Packer(self._current_plugin, self._instance_path)
        if packer.is_available():
            # Enabled Mods aus Profil lesen
            result = packer.pack_all_mods(enabled_mods)
            if result.ba2_paths:
                # INI aktualisieren
                self._update_ba2_ini(result.ba2_paths)

    # plugins.txt (unveraendert)
    if has_plugins_txt:
        writer = PluginsTxtWriter(...)
        writer.write()

def silent_purge(self) -> None:
    if self._deployer:
        self._deployer.purge()

    # BA2-Cleanup
    needs_ba2 = getattr(self._current_plugin, "NeedsBa2Packing", False)
    if needs_ba2 and self._current_game_path and self._instance_path:
        from anvil.core.ba2_packer import BA2Packer
        packer = BA2Packer(self._current_plugin, self._instance_path)
        packer.cleanup_ba2s()
        # INI wiederherstellen
        self._restore_ba2_ini()

    # plugins.txt entfernen (FEHLT AKTUELL -- Bug!)
    if has_plugins_txt:
        writer = PluginsTxtWriter(...)
        writer.remove()
```

## 5. Deploy/Purge Signal-Flow

### 5.1 Deploy (Bethesda mit BA2)

```
GamePanel.silent_deploy()
    |
    +-> ModDeployer.deploy()
    |       ESP/ESM/ESL -> Symlink nach Data/
    |       DLL/EXE     -> Copy (DirectInstall)
    |       BA2/BSA     -> Symlink nach Data/
    |       Rest        -> wird uebersprungen (needs_ba2_packing=True)
    |
    +-> BA2Packer.pack_all_mods()
    |       cleanup alte anvil_*.ba2
    |       Fuer jede Mod:
    |           _stage_mod_files() -> staging/general/ + staging/textures/
    |           _run_bsarch()      -> anvil_ModName.ba2
    |           _run_bsarch()      -> anvil_ModName - Textures.ba2
    |
    +-> INI aktualisieren
    |       Backup: Fallout4Custom.ini -> .anvil_backup
    |       [Archive] sResourceArchive2List += anvil_*.ba2
    |
    +-> Manifest speichern (Symlinks + BA2s + INI-Backup)
    |
    +-> PluginsTxtWriter.write()  (unveraendert)
```

### 5.2 Purge (Bethesda mit BA2)

```
GamePanel.silent_purge()
    |
    +-> ModDeployer.purge()           Symlinks entfernen
    +-> BA2Packer.cleanup_ba2s()      anvil_*.ba2 loeschen
    +-> INI-Backup wiederherstellen
    +-> PluginsTxtWriter.remove()     plugins.txt entfernen
    +-> Manifest loeschen
```

### 5.3 Nicht-Bethesda-Spiele

Exakt wie bisher. `NeedsBa2Packing = False` (Default) -> alle BA2-Guards inaktiv.

## 6. INI-Management

### 6.1 Fallout 4

**Datei:** `[ProtonPrefix]/drive_c/users/steamuser/Documents/My Games/Fallout4/Fallout4Custom.ini`

```ini
[Archive]
sResourceArchive2List=anvil_WeaponMod.ba2, anvil_WeaponMod - Textures.ba2, anvil_ArmorMod.ba2
```

### 6.2 Skyrim SE

**Datei:** `[ProtonPrefix]/drive_c/users/steamuser/Documents/My Games/Skyrim Special Edition/SkyrimCustom.ini`

```ini
[Archive]
sResourceArchiveList2=anvil_WeaponMod.bsa, anvil_ArmorMod.bsa
```

### 6.3 INI-Regeln

1. Bestehende Eintraege in der INI NICHT ueberschreiben
2. Nur `anvil_*` Eintraege hinzufuegen
3. Bei Purge: Nur `anvil_*` Eintraege entfernen ODER Backup wiederherstellen
4. Vor jeder Aenderung: `.anvil_backup` erstellen
5. Wenn Custom.ini nicht existiert: Erstellen mit nur dem [Archive]-Abschnitt
6. Encoding: Bethesda-INIs sind ANSI/CP1252, NICHT UTF-8

## 7. BSArch-Management

### 7.1 Speicherort

Global: `~/.local/share/anvil-organizer/tools/BSArch.exe`
Oder via QSettings: `Tools/bsarch_path`
Oder pro Instance: `instance_path/.tools/BSArch.exe`

### 7.2 Suchorder

1. Expliziter Pfad (Constructor-Parameter)
2. QSettings `Tools/bsarch_path`
3. Instance-Tools: `.tools/BSArch.exe`
4. Global-Tools: `~/.local/share/anvil-organizer/tools/BSArch.exe`

### 7.3 BSArch-Aufruf

```bash
# Via Proton:
STEAM_COMPAT_DATA_PATH=/path/to/compatdata \
STEAM_COMPAT_CLIENT_INSTALL_PATH=/path/to/steam \
SteamAppId=377160 \
/path/to/proton run /path/to/BSArch.exe pack \
    /path/to/staging/ \
    /path/to/Data/anvil_ModName.ba2 \
    -fo4 -mt
```

## 8. PluginsTxtWriter Kompatibilitaet

**Ergebnis: KEINE Aenderung noetig.**

- `_PLUGIN_EXTENSIONS = {".esp", ".esm", ".esl"}` -- BA2 wird bereits gefiltert
- `os.scandir(data_dir)` scannt nur direkte Kinder von Data/
- ESP/ESM bleiben Symlinks -> werden gefunden
- anvil_*.ba2 in Data/ -> werden ignoriert

### Edge-Cases (alle OK):

| Fall | Ergebnis |
|------|----------|
| Mod hat NUR Texturen (kein ESP) | Kein plugins.txt Eintrag, nur BA2 |
| anvil_*.ba2 in Data/ | Ignoriert (Extension-Filter) |
| Symlinks zu ESPs nach Deploy | Gefunden (scandir folgt Symlinks) |

## 9. Bekannter Bug: silent_purge() fehlt PluginsTxtWriter.remove()

In `game_panel.py:563-566` fehlt der Aufruf von `PluginsTxtWriter.remove()`.
Die Feature-Spec `docs/anvil-feature-plugins-txt.md` dokumentiert diesen Aufruf.

**MUSS vor BA2-Packing gefixt werden!**

## 10. Risiko-Analyse

| Risiko | Schwere | Mitigation |
|--------|---------|-----------|
| BSArch fehlt | Mittel | Fallback auf Symlinks + Warnung |
| BSArch erkennt Proton-Pfade nicht (Z: Drive) | Hoch | Testen; ggf. `_to_wine_path()` |
| Proton nicht gefunden | Hoch | Nur Steam-Spiele, Fehlermeldung |
| INI-Manipulation bricht Spiel | Hoch | Backup + atomares Schreiben |
| Grosse Mods (100+ MB Texturen) | Mittel | Progress-Feedback, 300s Timeout |
| Staging braucht viel /tmp Space | Mittel | Staging in Instance statt /tmp |
| User bricht Deploy ab | Hoch | Atomare Ops (temp -> move) |
| Purge loescht fremde BA2s | Hoch | `anvil_` Prefix + Manifest |
| Symlink-Logic Regression | Hoch | `needs_ba2_packing=False` Default |
| Bethesda-INI Encoding (CP1252) | Mittel | Explicit encoding parameter |

## 11. Offene Fragen

1. **Wine-Pfad-Konvertierung:** Braucht BSArch unter Proton Windows-Pfade (`Z:\home\...`) oder akzeptiert es Linux-Pfade? -> Muss getestet werden.

2. **BSArch Multithreading:** `-mt` Flag fuer Texturen-Archive? SSE Texturen verwenden anderes Format.

3. **BSA vs. BA2:** Skyrim SE nutzt BSA-Format, nicht BA2. BSArch kann beides. Output-Extension `.bsa` statt `.ba2`?

4. **Starfield BA2v2:** Starfield nutzt ein neueres BA2-Format (v2). BSArch-Unterstuetzung muss geprueft werden.

5. **Fallback-Strategie:** Wenn BSArch fehlt -- Symlinks als Fallback (funktioniert nicht unter Proton) oder Fehlermeldung?

6. **Settings-UI:** BSArch-Pfad in Settings-Dialog konfigurieren? Oder automatische Erkennung?

## 12. Implementierungsreihenfolge

1. **Bug-Fix:** `silent_purge()` + `PluginsTxtWriter.remove()`
2. **base_game.py:** Neue Attribute (NeedsBa2Packing, Ba2Format, etc.)
3. **game_fallout4.py + game_skyrimse.py:** BA2-Attribute setzen
4. **ba2_packer.py:** Neue Datei, Klasse BA2Packer
5. **mod_deployer.py:** Parameter + Dateikategorisierung
6. **game_panel.py:** BA2-Integration in silent_deploy/silent_purge
7. **INI-Management** in ba2_packer.py oder separate Klasse
8. **Testen:** Fallout 4 + Skyrim SE mit echten Mods
