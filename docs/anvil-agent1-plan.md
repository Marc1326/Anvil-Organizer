# Agent 1 — Analyse bestehender Anvil-Code: BG3 laedt keine Mods + BG3SE nicht aktiv

Datum: 2026-04-21
Thema: BG3 startet, aber Mods werden nicht geladen. BG3SE wird im Hauptmenue nicht als "Script Extender loaded" angezeigt, obwohl Anvil meldet, BG3SE sei installiert. Tritt unter Hyprland UND KDE auf (also kein Compositor-Problem).

---

## Zusammenfassung — Hauptbefunde

1. **BG3SE "installiert"-Meldung ist irrefuehrend** — Anvil prueft NUR die Datei `bin/DWrite.dll`. Die DLL wird jedoch von Wine/Proton OHNE `WINEDLLOVERRIDES="DWrite.dll=n,b"` gar nicht geladen. Ergo: Datei vorhanden = Anvil sagt "installiert", aber BG3SE wird trotzdem nie aktiv.
2. **`get_proton_env_overrides()` ist bei BG3 NICHT ueberschrieben** — im Gegensatz zu Fallout 4 / Starfield / Skyrim SE, die ihre Shim-DLLs per WINEDLLOVERRIDES einschleusen, bleibt bei BG3 die Basis-Klasse-Implementierung (`return {}`) aktiv. Folge: Weder beim Steam-Launch noch beim Proton-Launch werden ENV-Variablen gesetzt.
3. **`steam_launch_options()` wird nirgends aufgerufen** — die Hilfsmethode, die den notwendigen Startparameter-String liefert, wird vom UI ignoriert. Der User bekommt KEINEN Hinweis, dass er in Steam unter Eigenschaften → Startoptionen `WINEDLLOVERRIDES="DWrite.dll=n,b" %command% --skip-launcher` eintragen muss.
4. **`--skip-launcher` fehlt in `GameLaunchArgs`** — Cyberpunk hat `GameLaunchArgs = ["--launcher-skip"]`; BG3 hat keine entsprechende Zeile. Das heisst, selbst wenn der User Anvil startet, faellt BG3 in den LariLauncher. Der LariLauncher kann beim "Play"-Klick die modsettings.lsx neu schreiben/validieren.
5. **`bg3_installer.deploy()` wird beim Spielstart NICHT aufgerufen** — `deploy()` laeuft nur beim Instance-Apply und beim manuellen Deploy-Button-Klick. Im regulaeren Start-Pfad via Steam wird die modsettings.lsx also nicht noch einmal frisch geschrieben, bevor BG3 startet.
6. **Pak-Ablage ist korrekt** — Paks werden direkt per `shutil.copy2()` in `pfx/drive_c/users/steamuser/AppData/Local/Larian Studios/Baldur's Gate 3/Mods/` kopiert. Keine Symlinks, kein Deployment-Layer. Das ist korrekt und nicht ursaechlich.
7. **Proton-Prefix-Caching ist brüchig** — `BG3ModInstaller.__init__` ruft `pak_mods_path()` EINMAL auf und cacht. Existiert der Prefix zu diesem Zeitpunkt nicht (BG3 wurde nie gestartet), bleibt `_mods_path = None` bis zum naechsten Instance-Reload — alle Installationen/Deploys sind No-Ops.

---

## 1. BG3-Plugin-Uebersicht

### Plugin-Dateien

| Datei | Rolle |
| --- | --- |
| `anvil/plugins/games/game_baldursgate3.py` | `BaldursGate3Game(BaseGame)` — Plugin-Klasse |
| `anvil/plugins/games/bg3_mod_handler.py` | modsettings.lsx I/O, `BG3ScriptExtender`, pak-Scanner |
| `anvil/core/bg3_mod_installer.py` | Installer-Lifecycle (install/activate/deactivate/reorder/deploy) |
| `anvil/models/bg3_mod_list_model.py` | (Legacy) separates Datenmodell — nicht mehr aktiv genutzt |
| `anvil/widgets/bg3_mod_list.py` | (Legacy) separate Ansicht — nicht mehr aktiv genutzt |

**Wichtig:** Seit v0.3x verwendet BG3 die NORMALE `ModListView`. Die separaten BG3-Widgets/Models existieren noch, werden aber nicht mehr gesetzt (`mainwindow.py:6005` `setCurrentWidget(self._mod_list_view)`).

### Game-Attribute (`game_baldursgate3.py:38-87`)

- `GameShortName = "baldursgate3"` (Schluessel fuer Spezial-Pfade in `mainwindow.py:1208`).
- `GameBinary = "bin/bg3.exe"` (Vulkan).
- `GameSteamId = [1086940, 2626479850]` (Spiel + Toolkit).
- `GameLauncher = "Launcher/LariLauncher.exe"`.
- `GameDataPath = ""` — bedeutet: der generische `ModDeployer` hat bei BG3 **nichts zu tun**.
- `GameLaunchArgs` ist **nicht gesetzt** → BG3 startet mit dem LariLauncher.

---

## 2. Wie Anvil den Script Extender "erkennt"

### Funktion: `has_script_extender()` in `game_baldursgate3.py:269-273`

```python
def has_script_extender(self) -> bool:
    """Check if BG3 Script Extender is installed."""
    if self._game_path is None:
        return False
    return BG3ScriptExtender.detect(self._game_path)
```

### `BG3ScriptExtender.detect()` in `bg3_mod_handler.py:380-393`

```python
return (game_path / "bin" / "DWrite.dll").is_file()
```

**Pruefkriterium:** Nur die DATEI `bin/DWrite.dll`. Kein Process-Check, kein WINEDLLOVERRIDES-Check, keine Integritaetspruefung.

### `get_installed_frameworks()` in `base_game.py:706-737`

Verwendet die `detect_installed`-Pfade der FrameworkMod-Definition. Fuer BG3SE aus `game_baldursgate3.py:305`:

```python
detect_installed=["bin/DWrite.dll"]
```

Gleiche Pruefung — nur Dateiexistenz.

### Anzeige im UI

- `has_script_extender()` wird **nirgends** im UI aufgerufen (Grep ergibt 0 Treffer in `anvil/widgets/` und `anvil/mainwindow.py`).
- Die "installiert"-Anzeige laeuft ueber `get_installed_frameworks()`:
  - `mainwindow.py:1345` (Standard-Games) — bei BG3 irrelevant, da der Pfad bei `short_name == "baldursgate3"` vorher returned.
  - `mainwindow.py:6284` `self._mod_list_view.load_frameworks(fw_items)` — hier wird fuer BG3 die Framework-Liste in die UI gepumpt.
- In `mod_list.py:1220 load_frameworks()` setzt `installed` den Checkbox-Zustand — bei `True` erscheint ein aktiver Haken.

**Folge:** Anvil markiert BG3SE als "installiert", sobald `bin/DWrite.dll` existiert. Das beweist nicht, dass die DLL auch geladen wird.

---

## 3. Deploy bei BG3 — physische Kopie

### Mod-Typen (`bg3_mod_installer.py:42-44`)

- `MOD_TYPE_PAK = "pak"` — Paks (Standard).
- `MOD_TYPE_FRAMEWORK = "framework"` — BG3SE etc. ins Game-Verzeichnis.
- `MOD_TYPE_DATA_OVERRIDE = "data_override"` — lose Dateien ins `Data/`-Verzeichnis.

### PAK-Deploy: physische Kopie in den Prefix

`_install_pak_single()` und `_install_pak_from_dir()` in `bg3_mod_installer.py:762-797`:

```python
shutil.copy2(pak_path, dest)   # dest = Mods/<pak>
```

Die Paks werden direkt nach `pfx/drive_c/users/steamuser/AppData/Local/Larian Studios/Baldur's Gate 3/Mods/` kopiert. Kein Symlink, kein Hardlink.

### FRAMEWORK-Deploy: Kopie ins Game-Verzeichnis

`_install_framework()` in `bg3_mod_installer.py:843-894`:

```python
target_dir = self._game_path / fw.target   # z.B. self._game_path / "bin"
shutil.copy2(src_file, dest)
```

Bei BG3SE → target_dir = `<game>/bin/` → `DWrite.dll` landet in `bin/DWrite.dll`.

### DATA-OVERRIDE-Deploy

`_install_data_override()` in `bg3_mod_installer.py:896-954`: lose Dateien werden mit Path-Rewrites direkt in `<game>/Data/` bzw. `<game>/bin/NativeMods/` (siehe `get_data_override_path_rewrites` in `game_baldursgate3.py:329-339`) kopiert.

### Deploy der modsettings.lsx

`bg3_installer.deploy()` in `bg3_mod_installer.py:402-452` schreibt die modsettings.lsx in das aktive Profil (via `modsettings_path()`).

**Aufruf-Stellen:**
- `mainwindow.py:6082` — beim Instance-Apply (nach `_apply_bg3_instance`).
- `mainwindow.py:6402` — beim manuellen Deploy-Button (`_on_bg3_deploy`).

**NICHT aufgerufen:**
- Beim Spielstart via `_launch_via_steam()`.
- Beim Installieren/Deaktivieren (dort laeuft `_write_modsettings()` als Auto-Deploy direkt).

---

## 4. BG3SE-Deploy-Pfad

### Framework-Definition (`game_baldursgate3.py:299-308`)

```python
FrameworkMod(
    name="BG3 Script Extender",
    pattern=["DWrite.dll"],
    target="bin/",
    description="Script Extender fuer BG3 (Native Mod Support)",
    detect_installed=["bin/DWrite.dll"],
    required_by=["SE-Mods", "Native Mods"],
    nexus_id=2172,
)
```

### Ziel: `<GameDir>/bin/DWrite.dll`

Also landet `DWrite.dll` korrekt im BG3-Game-Ordner neben `bg3.exe`. Das ist der richtige Ablageort — Wine laedt DLLs aus dem EXE-Verzeichnis, sobald das DLL-Loading-Verhalten per Override auf "native first" gesetzt ist.

---

## 5. DWrite.dll / bg3se_updater.exe Deploy

- `DWrite.dll` wird im Framework-Install-Pfad `_install_framework()` ins `<game>/bin/` kopiert (korrekt).
- `bg3se_updater.exe` wird ebenfalls kopiert, wenn es im Archiv enthalten ist — `_install_framework()` kopiert ALLE Dateien, die die Pattern-Liste matchen PLUS Geschwister-Dateien im selben Verzeichnis (`bg3_mod_installer.py:869-883`). Fuer das offizielle BG3SE-ZIP bedeutet das: `DWrite.dll` + `bg3se_updater.exe` + evtl. `ScriptExtenderSettings.json`-Template.

Die Datei-Ablage ist korrekt. Das Problem ist die **Aktivierung unter Proton** — Wine ignoriert die DLL ohne WINEDLLOVERRIDES.

---

## 6. Proton-Prefix-Ermittlung

### `protonPrefix()` in `game_baldursgate3.py:90-126`

BG3 hat einen eigenen Override, weil es ZWEI Steam-IDs besitzt (Spiel 1086940 + Toolkit 2626479850):

1. Steam-Root via `find_steam_path()` ermitteln.
2. Library-Liste aus `libraryfolders.vdf` lesen.
3. Fuer jede Steam-ID → fuer jede Library → pruefen, ob `steamapps/compatdata/<id>/pfx` existiert.
4. Erste gefundene Kombi zurueckgeben.

### Prefix-ID

Primaere ID `1086940` zuerst (darum der Override). Toolkit-ID 2626479850 nur als Fallback.

### Schwachstelle

`BG3ModInstaller.__init__` (`bg3_mod_installer.py:50-56`) cached den Prefix-Pfad:

```python
self._mods_path: Path | None = game_plugin.pak_mods_path()
self._modsettings_path: Path | None = game_plugin.modsettings_path()
```

Wenn `pak_mods_path()` zu diesem Zeitpunkt None liefert (Prefix noch nicht erstellt, weil BG3 nie gestartet wurde), bleibt `_mods_path = None` fuer die gesamte Lebensdauer des Installer-Objekts.

- In `mainwindow.py:6044-6048` wird dann eine Status-Message `status.bg3_proton_missing` angezeigt — aber es gibt keinen automatischen Retry.
- Install-, Activate-, Deploy-Operationen laufen still ins Leere (`if self._mods_path is None: return None`).

---

## 7. modsettings.lsx-Handhabung

### Aktives Profil (`game_baldursgate3.py:183-208`)

```python
candidates = list(profiles.glob("*/modsettings.lsx"))
# Most recently modified = active profile
best = max(candidates, key=lambda p: p.stat().st_mtime)
```

Heuristik ueber mtime — nicht ideal, aber vernuenftig fuer Single-Profile-User.

Fallback: `Public/modsettings.lsx`, falls keine Kandidaten.

### Schreiben in `_write_modsettings()` (`bg3_mod_installer.py:1175-1302`)

- Backup wird angelegt (`modsettings.lsx.backup`, `modsettings.lsx.deploy_backup`).
- Schreibt ModOrder + Mods-Nodes korrekt, mit Gustav/GustavDev als erster Eintrag.

### Schreib-Zeitpunkte

- Nach `install_mod()`, `activate_mod()`, `deactivate_mod()`, `reorder_mods()` — via `_write_state()` → `_write_modsettings()` (Auto-Deploy, siehe `bg3_mod_installer.py:176-177, 237, 293, 399`).
- `bg3_installer.deploy()` explizit (`mainwindow.py:6082`, `6402`).

### Problem: Timing zwischen LariLauncher und modsettings.lsx

- Wenn BG3 mit Launcher startet und der User im Launcher "Mods/Load Order" oeffnet und dann Play klickt, ueberschreibt der Launcher selber die modsettings.lsx.
- Ohne `--skip-launcher` und ohne `bg3_installer.deploy()` direkt vor Start ist das Zeitfenster zu gross, bis BG3 tatsaechlich die Datei liest.

---

## 8. Launch-Button fuer BG3

### Start-Pfad (`widgets/game_panel.py:1107-1118`)

```python
def _do_launch(self, plugin, binary: str, is_steam: bool) -> None:
    if is_steam:
        force_proton = getattr(plugin, "GameLaunchViaProton", False)
        is_main_binary = (
            hasattr(plugin, "GameBinary") and binary == plugin.GameBinary
        )
        if is_main_binary and not force_proton:
            self._launch_via_steam(plugin)
        else:
            self._launch_via_proton(plugin, binary)
```

BG3 hat **nicht** `GameLaunchViaProton = True`, also geht der Main-Binary-Start ueber `_launch_via_steam()`.

### `_launch_via_steam()` (`game_panel.py:1622-1666`)

```python
args = ["-applaunch", str(steam_id)]
if hasattr(plugin, "GameLaunchArgs"):
    args.extend(plugin.GameLaunchArgs)   # BG3: leere Liste
proc = host_popen([steam_bin, *args], env=clean_subprocess_env())
...
if hasattr(plugin, "get_proton_env_overrides"):
    overrides = plugin.get_proton_env_overrides()   # BG3: {} (base default)
    if "WINEDLLOVERRIDES" in overrides:
        QMessageBox.information(...)   # NIE ausgeloest fuer BG3
```

**Resultat:**

- ENV-Variablen koennen via Steam-Applaunch ohnehin nicht gesetzt werden (Steam starten, Steam setzt die Umgebung).
- Der "Hinweis"-Dialog feuert nur, wenn das Plugin `get_proton_env_overrides()` mit `WINEDLLOVERRIDES` zurueckgibt — BG3 liefert das nicht.
- Kein Aufruf von `BG3ScriptExtender.steam_launch_options()`.

### `_launch_via_proton()` (`game_panel.py:1707-1749`)

Wuerde nur greifen, wenn eine Nicht-Hauptbinary gestartet wird (z.B. LariLauncher direkt) oder `GameLaunchViaProton = True` gesetzt waere. Hier setzt `_build_proton_env()` (Zeile 1668-1705) zwar `WINEDLLOVERRIDES` — aber nur wenn das Plugin es via `get_proton_env_overrides()` liefert (macht BG3 nicht).

### Kein separater BG3-Launch-Button

BG3 verwendet die generischen Start-Mechanismen. Es gibt keinen dedizierten Button, der z.B. den Prefix prueft oder die modsettings.lsx vor Start noch einmal flusht.

---

## 9. modlist.txt / active_mods.json bei BG3

**BG3 verwendet dieses System NICHT.** Beweis:

- `bg3_mod_installer.py` importiert weder `read_global_modlist` noch `read_active_mods`.
- `game_baldursgate3.py` hat `GameDataPath = ""` → `ModDeployer` ignoriert die Instanz.
- BG3-Mods landen NICHT unter `<instance>/.mods/`, sondern direkt im Proton-Prefix (siehe Abschnitt 3).
- Zustand wird in `<instance>/bg3_modstate.json` + Proton-Prefix modsettings.lsx gehalten (`bg3_mod_installer.py:1022-1025`).

Das ist sauber getrennt — keine modlist.txt-Datei fuer BG3.

---

## 10. Vergleich mit anderen Games

| Aspekt | Skyrim SE / Fallout 4 / Starfield | Cyberpunk 2077 | BG3 |
| --- | --- | --- | --- |
| Mod-Deployment | Symlinks via `ModDeployer` → `Data/` | Symlinks via `ModDeployer` → `archive/pc/mod`, `r6/mods`, ... | **Physische Kopie** direkt in Proton-Prefix `Mods/` |
| modlist.txt | Ja (global + profil) | Ja | Nein, nutzt `bg3_modstate.json` + `modsettings.lsx` |
| Script Extender Detection | `has_script_extender()` prueft Exe (z.B. `f4se_loader.exe`, `sfse_loader.exe`) | n/a | Prueft **DLL** (`bin/DWrite.dll`) — unzureichend unter Wine |
| `get_proton_env_overrides()` | Ueberschrieben (z.B. F4SE-Shim liefert `version=n,b`) | Ueberschrieben fuer winmm/version | **NICHT ueberschrieben** |
| `GameLaunchArgs` | teilweise | `["--launcher-skip"]` | Leer → LariLauncher laeuft |
| Launcher-Binary | typ. direkter Exe-Start | `REDprelauncher` als Option | LariLauncher als Option (ohne Skip) |
| Deploy vor Spielstart | `silent_deploy()` in `_on_start_game` | `silent_deploy()` + REDmod-Deploy | **Kein** Deploy-Call vor Spielstart |
| User-Hinweis fuer WINEDLLOVERRIDES | Via `shim_steam_hint`-MessageBox | n/a | **Keiner** — `steam_launch_options()` nicht aufgerufen |

---

## 11. Warum BG3SE im Menue nicht erscheint — Ursachenkette

1. Anvil kopiert `DWrite.dll` nach `<game>/bin/DWrite.dll`. Datei-Check sagt: **installiert**.
2. Anvil startet BG3 via `steam -applaunch 1086940` ohne zusaetzliche ENV-Variablen.
3. Steam loest das konfigurierte Proton auf, spawnt den LariLauncher (weil `--skip-launcher` fehlt).
4. Wine/Proton laedt die **eingebaute** `DWrite.dll` aus `C:\windows\system32\` — denn KEIN `WINEDLLOVERRIDES="DWrite.dll=n,b"` ist gesetzt.
5. BG3SE-Hook wird nie injiziert → Script Extender zeigt nichts im Menue → SE-abhaengige Mods laden nicht.
6. pak-basierte Mods (die kein SE brauchen) laden nur, wenn die modsettings.lsx zum Startzeitpunkt sauber ist. Da der LariLauncher sie ggf. vor Play ueberschreibt, koennen auch die verloren gehen.

---

## 12. Warum Mods allgemein nicht geladen werden — Ursachenkette

Selbst fuer pak-Mods ohne SE-Abhaengigkeit:

1. Anvil kopiert `<mod>.pak` in den Prefix-Mods-Ordner (korrekt).
2. Anvil schreibt modsettings.lsx beim Instance-Load (`_apply_bg3_instance` → `deploy()`).
3. BETWEEN Load und Spielstart: User installiert/aktiviert/deaktiviert Mods → modsettings.lsx wird live geschrieben.
4. User klickt "Start" — LariLauncher startet.
5. LariLauncher liest modsettings.lsx, zeigt eigene Mod-Liste an.
6. Falls der User im LariLauncher etwas in der Liste aendert oder sie neu sortiert, schreibt der Launcher die modsettings.lsx selbst neu — ggf. OHNE die von Anvil hinzugefuegten Eintraege.
7. User klickt "Play" im Launcher → BG3 startet mit der LariLauncher-Variante der modsettings.lsx.

**Vermeidbar:** Anvil sollte `--skip-launcher` im Launch-Kommando anfuegen und zusaetzlich vor Start `bg3_installer.deploy()` noch einmal aufrufen.

---

## 13. Zusaetzlich entdeckte Fundstellen (Referenz-Tabelle)

| Datei:Zeile | Beobachtung |
| --- | --- |
| `game_baldursgate3.py:57` | `GameLauncher = "Launcher/LariLauncher.exe"` — kein Skip-Arg |
| `game_baldursgate3.py:269-273` | `has_script_extender()` → nur Datei-Pruefung |
| `game_baldursgate3.py:297-308` | FrameworkMod "BG3 Script Extender" — nur `detect_installed=["bin/DWrite.dll"]` |
| `bg3_mod_handler.py:380-393` | `BG3ScriptExtender.detect()` — nur Datei-Pruefung |
| `bg3_mod_handler.py:419-425` | `steam_launch_options()` definiert — nirgends genutzt |
| `base_game.py:761-767` | `get_proton_env_overrides()` Default `{}` — von BG3 NICHT ueberschrieben |
| `bg3_mod_installer.py:50-56` | `_mods_path` + `_modsettings_path` im `__init__` gecached, keine Invalidierung |
| `bg3_mod_installer.py:402-452` | `deploy()` — nur beim Instance-Apply und manuellem Deploy-Button aufgerufen |
| `widgets/game_panel.py:1622-1666` | `_launch_via_steam()` — prueft `get_proton_env_overrides()` → bei BG3 leer, kein Hinweis |
| `widgets/game_panel.py:1107-1118` | `_do_launch()` — BG3 landet in `_launch_via_steam`, nicht in `_launch_via_proton` |
| `mainwindow.py:6082` | `_apply_bg3_instance` ruft `deploy()` ein Mal auf (Initial) |
| `mainwindow.py:1856-1883` | `_on_start_game` — wird bei BG3 gar nicht erreicht (kein `start_requested`-Emit) |

---

## 14. Reparatur-Stellschrauben (Dokumentation nur, KEIN Fix)

Die folgenden Stellen muessten angefasst werden, um das Problem zu beheben:

| Stelle | Notwendige Aenderung |
| --- | --- |
| `game_baldursgate3.py` | `GameLaunchArgs = ["--skip-launcher"]` hinzufuegen |
| `game_baldursgate3.py` | `get_proton_env_overrides()` ueberschreiben → `{"WINEDLLOVERRIDES": "DWrite.dll=n,b"}` wenn `has_script_extender()` True |
| `game_baldursgate3.py` | optional: `GameLaunchViaProton = True`, um ueber den Proton-Launch-Pfad (`_launch_via_proton`) zu gehen, wo `WINEDLLOVERRIDES` via ENV gesetzt werden kann (statt nur als Hinweis fuer Steam-Startoptionen) |
| `widgets/game_panel.py:_launch_via_steam` | Wenn Plugin `steam_launch_options()` hat, diesen String im "Hinweis"-Dialog anzeigen — oder direkt pruefen, ob die Steam-Startoptionen bereits gesetzt sind |
| `mainwindow.py` | Vor Spielstart bei BG3: `self._bg3_installer.deploy()` aufrufen, analog zum Pre-Launch-Flow der Standard-Games (`silent_deploy()`) |
| `bg3_mod_installer.py` | `_mods_path` / `_modsettings_path` bei jedem Zugriff neu aufloesen (oder Invalidierung nach Spielstart), damit ein spaeter erzeugter Prefix auffindbar wird |
| `bg3_mod_handler.py:BG3ScriptExtender.detect()` | Zusatz: pruefen, ob die "installation" unter Proton tatsaechlich nutzbar ist (z.B. Startoption gesetzt) — oder UI-Label entsprechend zweistufig ("Datei vorhanden / Override gesetzt") |

---

## 15. Relevante Code-Pfade fuer Agent 2 (MO2) und Agent 3 (Architektur)

- MO2 kennt BG3 nicht nativ (Windows-only Mod-Order via Larian-Datei). MO2-Referenz-Vergleich dient nur fuer das **BG3SE-Hinweis-UX** — wie MO2 unter Windows den Hinweis "bitte Launcher-Parameter setzen" vermittelt.
- Architektur-Agent sollte klaeren:
  - Wo genau im Start-Flow wird `bg3_installer.deploy()` zusaetzlich aufgerufen (idealerweise in `mainwindow._on_start_game` analog zu Bethesda-Games).
  - Wie `GameLaunchViaProton` fuer BG3 funktioniert (Folge: keine ENV-Variablen via Steam noetig).
  - Wie die UI zweistufig signalisiert: (a) Datei vorhanden, (b) Override aktiv / Launch-Option gesetzt.

---

## 16. Keine Aenderungen vorgenommen

Gemaess CLAUDE.md-Regel: NIEMALS BG3-Code anfassen. Dieser Report ist rein analytisch. Es wurde keine Zeile Code modifiziert. Es wurde nur gelesen via Read/Grep.
