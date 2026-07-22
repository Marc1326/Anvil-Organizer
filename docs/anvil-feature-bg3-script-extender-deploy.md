# Feature: BG3 Script Extender Deploy + Launch-Fix

Datum: 2026-04-21
Status: Planung (KEIN Code geschrieben)
Planer-Agent: 4/4 (Konsolidierung)

---

## Problem-Definition

BG3 startet über Anvil, aber:

1. **BG3SE ist nicht aktiv** — im Hauptmenü erscheint kein „Script Extender loaded"-Banner,
   obwohl Anvil meldet „BG3SE installiert".
2. **Keine Mods werden geladen** — Pak-Mods liegen im Proton-Prefix, erscheinen
   aber nicht ingame. modsettings.lsx wird zwischen Anvil-Deploy und bg3.exe-Launch
   vom Larian-Launcher oder BG3 selbst überschrieben.

Das Symptom tritt unter Hyprland UND KDE auf — Compositor/WM ist ausgeschlossen.
Ursache liegt in der Proton-Umgebung + Start-Mechanik, nicht in der GUI.

---

## Root Causes (nummeriert, mit Code-Belegen)

### RC-1: `WINEDLLOVERRIDES=DWrite.dll=n,b` wird NIE gesetzt

- `base_game.py:761-766` — Default `get_proton_env_overrides() -> {}`.
- `game_baldursgate3.py` — überschreibt `get_proton_env_overrides()` NICHT.
- `base_game.py:131` — `GameProtonDllOverrides: dict[str,str] = {}`.
- `game_baldursgate3.py` — setzt `GameProtonDllOverrides` NICHT (Cyberpunk2077
  macht es vor: `game_cyberpunk2077.py:53 {"winmm": "native,builtin"}`).
- Folge: Proton lädt Wine-Builtin-`DWrite.dll` statt `<GameDir>/bin/DWrite.dll`.
  BG3SE kann sich nicht einhaken.

### RC-2: BG3SE-Installation ist unvollständig

Physische Prüfung `/mnt/gamingS/SteamLibrary/steamapps/common/Baldurs Gate 3/bin/`:

| Erwartet | Vorhanden |
| --- | --- |
| `bin/DWrite.dll` | JA |
| `bin/ScriptExtenderSettings.json` | JA |
| `bin/bg3se_updater.exe` | **FEHLT** |
| `bin/ScriptExtender/` (Core-Ordner) | **FEHLT** |

- `bg3_mod_installer.py:843-894` — `_install_framework()` kopiert nur Dateien, die
  auf die `pattern`-Liste matchen plus deren Geschwister. BG3SE-FrameworkMod
  (`game_baldursgate3.py:299-308`) hat `pattern=["DWrite.dll"]` — das reicht
  NICHT, um den gesamten ScriptExtender/-Unterbaum zu übertragen.
- Der User hat BG3SE nie via Anvil installiert; die `DWrite.dll` wurde vermutlich
  manuell aus einem der drei 7z-Archive in `~/Downloads/Mods/BG3/` entpackt.

### RC-3: `steam_launch_options()` ist toter Code

- `bg3_mod_handler.py:418-425` definiert den Hilfsstring
  `WINEDLLOVERRIDES="DWrite.dll=n,b" %command% --skip-launcher`.
- Grep über gesamtes `anvil/`-Tree: **0 Aufrufe**. Der String wird dem User
  nirgends angezeigt.

### RC-4: `--skip-launcher` wird nicht als GameLaunchArg gesetzt

- `game_baldursgate3.py:38-87` — `GameLaunchArgs` nicht gesetzt.
- Cyberpunk macht es vor: `GameLaunchArgs = ["--launcher-skip"]`.
- Steam-Applaunch ignoriert CLI-Args zugunsten der localconfig.vdf-LaunchOptions
  (siehe Agent 3, Abschnitt 7 — Hinweis-Dialog ist hier der richtige Hebel,
  nicht `GameLaunchArgs`).

### RC-5: modsettings.lsx wird NICHT auf `chmod 444` gesetzt

- `bg3_mod_handler.py:214-371` — `ModsettingsWriter.write()` setzt keine
  Dateirechte.
- `bg3_mod_installer.py:402-452` — `deploy()` ruft Writer auf, setzt danach
  keine Rechte.
- Grep `anvil/` auf `chmod`: nur `secure_storage.py:131` (Keyring 0o600).
- Folge: Larian-Launcher und BG3 selbst können modsettings.lsx zwischen
  Deploy und Start überschreiben — alle fremden Mod-Einträge verschwinden.

### RC-6: `_mods_path`-Cache wird bei fehlendem Prefix None und nie invalidiert

- `bg3_mod_installer.py:50-56` — `__init__` cached
  `self._mods_path = game_plugin.pak_mods_path()`.
- Ist der Prefix zum Instanz-Load-Zeitpunkt nicht existent (BG3 wurde nie
  gestartet), bleibt `_mods_path = None` bis zum nächsten Instance-Reload.
- Alle `install_mod()`/`activate_mod()`/`deploy()`-Aufrufe werden stille
  No-Ops: `if self._mods_path is None: return None`.

### RC-7: Drei-Wege-Desynchronisation Anvil ↔ bg3_modstate.json ↔ Prefix

Physisch geprüft in Instanz `Baldur's Gate 3`:

| Quelle | Anzahl Mods |
| --- | --- |
| `.mods/` (Anvil-Ordner) | 8 |
| `modlist.txt` | 6 mit `-` deaktiviert, 1 Separator `+` |
| `active_mods.json` | ~90 UUIDs |
| `bg3_modstate.json mod_order` | 90 |
| `modsettings.lsx ModOrder` | ~80 UUIDs |
| `<prefix>/Mods/*.pak` | 19 (+ 4 in `.disabled/`) |
| `<prefix>/Mods_Core/*.pak` | ~80 (FREMD, kein Anvil-Deploy-Target) |

Nur **1 von 8** Anvil-Mods (Vemperen) liegt im aktiv gelesenen `Mods/`-Ordner.
`Mods_Core/` ist kein Standard-BG3-Pfad — Legacy-Dump eines anderen Managers.

### RC-8: `has_script_extender()` und `detect_installed` prüfen nur DLL-Existenz

- `game_baldursgate3.py:269-273` → `BG3ScriptExtender.detect()`.
- `bg3_mod_handler.py:380-393` → nur `(game_path / "bin" / "DWrite.dll").is_file()`.
- Kein Check auf Core-Ordner, keinen Updater, keinen Proton-Override.
- UI meldet „installiert", obwohl SE unter Proton nicht aktivierbar ist.

### RC-9: `bg3_installer.deploy()` läuft nicht vor Spielstart

- `mainwindow.py:6082` — Deploy beim Instance-Apply (Initial).
- `mainwindow.py:6402` — Deploy beim manuellen Deploy-Button.
- `_launch_via_steam` (`game_panel.py:1622-1666`) — KEIN Aufruf.
- Zeitfenster zwischen letzter Änderung und Spielstart: modsettings.lsx kann
  bereits vom Launcher überschrieben worden sein.

---

## Lösungs-Plan (welche Änderungen in welchen Dateien)

**WICHTIG:** KEINE Änderung darf im Rahmen dieser Spec implementiert werden.
Alle Pfad-Angaben sind Architektur-Vorgaben für den Workflow-Agenten.

### Datei-Übersicht

| Datei | Änderung |
| --- | --- |
| `anvil/plugins/games/game_baldursgate3.py` | `GameProtonDllOverrides = {"DWrite": "native,builtin"}` ergänzen. Methode `get_proton_env_overrides()` überschreiben (gibt `{"WINEDLLOVERRIDES": "DWrite.dll=n,b"}` zurück). Methode `get_required_steam_launch_options()` (neu, siehe Plugin-Basis) implementieren. `has_script_extender()` erweitern auf (a) `bin/DWrite.dll` UND (b) `bin/bg3se_updater.exe` UND (c) `bin/ScriptExtender/`-Ordner. |
| `anvil/plugins/base_game.py` | Neue Methode `get_required_steam_launch_options(self) -> str \| None` mit Default `None`. Dient als generischer Mechanismus für Skyrim SE / Fallout 4 / BG3. |
| `anvil/plugins/games/bg3_mod_handler.py` | BG3SE-FrameworkMod-Definition in `game_baldursgate3.py:299-308` so anpassen, dass `_install_framework` die GESAMTE Archiv-Struktur (DWrite.dll + ScriptExtender/**/* + bg3se_updater.exe + ScriptExtenderSettings.json falls nicht schon vorhanden) nach `bin/` kopiert. `BG3ScriptExtender.detect()` auf dreifache Prüfung erweitern. `steam_launch_options()` bleibt — wird endlich benutzt. |
| `anvil/core/bg3_mod_installer.py` | `_install_framework()` (Zeile 843-894) so erweitern, dass bei BG3SE der komplette Archiv-Inhalt inkl. Unterordner deployed wird (analog F4SE/SKSE). `deploy()` (402-452) nach Schreibvorgang `os.chmod(modsettings, 0o444)` aufrufen. Vor jedem Schreibvorgang `_ensure_writable()` (chmod 0o644) aufrufen. `_mods_path` + `_modsettings_path` bei jedem Zugriff lazy neu auflösen (statt im `__init__` cachen). Neue Methode `verify_foreign_mods_core()` die `<prefix>/Mods_Core/` scannt und als Anzeige-Liste zurückgibt (nicht löschen, nicht deployen, nur sichtbar machen). |
| `anvil/widgets/game_panel.py` | `_launch_via_steam()` (1622-1666) vor `steam -applaunch` prüfen: falls Plugin `get_required_steam_launch_options()` != None → in localconfig.vdf prüfen, ob der String dort steht. Falls nicht → Hinweis-Dialog mit „In Zwischenablage kopieren"-Button + „Steam öffnen"-Button + „Trotzdem starten"/„Abbrechen". QSettings-Flag `bg3_skip_launch_options_warning` respektieren. Für BG3-spezifisch vor Start `self._bg3_installer.deploy()` triggern (analog `silent_deploy()` bei anderen Games). |
| `anvil/mainwindow.py` | `_on_start_game` (1856-1883) — BG3-Branch ergänzen: vor Start `bg3_installer.deploy()` + `_apply_proton_dll_overrides()`. |
| `anvil/widgets/mod_list.py` (`load_frameworks`) | Framework-Anzeige zweistufig: (1) „Datei vorhanden" grün/rot (wie bisher), (2) NEU: „Proton-Override aktiv" grün/rot, abgeleitet aus `GameProtonDllOverrides` + user.reg-Scan. |
| `anvil/widgets/bg3_conflict_view.py` oder ähnliches | Neuer read-only-Tab/Bereich „Fremde Mods im Prefix (Mods_Core/)" zeigt den Legacy-Dump. Keine Löschung durch Anvil — nur Anzeige mit Warnhinweis. |

---

## Signal-Flow (wie Deploy + Launch MUSS ablaufen)

```
Start-Button in GUI
   |
   v
_on_start_clicked (game_panel.py:180)
   |
   v
_do_launch(plugin=BG3, binary="bin/bg3.exe", is_steam=True)
   |
   v
_launch_via_steam
   |
   +---> NEU 1: if plugin.short_name == "baldursgate3":
   |               bg3_installer.deploy()           # modsettings.lsx frisch schreiben
   |               |
   |               +---> _ensure_writable()        # chmod 644
   |               |
   |               +---> ModsettingsWriter.write() # Gustav + aktive Mods
   |               |
   |               +---> _set_readonly()           # chmod 444  (SCHUTZ VOR LARI-LAUNCHER)
   |
   +---> NEU 2: _apply_proton_dll_overrides(plugin)
   |               |
   |               +---> Liest GameProtonDllOverrides = {"DWrite": "native,builtin"}
   |               |
   |               +---> Schreibt in <prefix>/user.reg
   |                     [Software\\Wine\\AppDefaults\\bg3.exe\\DllOverrides]
   |                     "dwrite"="native,builtin"
   |
   +---> NEU 3: required = plugin.get_required_steam_launch_options()
   |           if required and required not in read_steam_launch_options():
   |               Dialog: "Steam-Launch-Options fehlen"
   |               [Kopieren] [Steam öffnen] [Trotzdem starten] [Abbrechen]
   |               (QSettings-Flag "bg3_skip_launch_options_warning" respektieren)
   |
   +---> steam -applaunch 1086940
           |
           v
         (Proton liest user.reg → DWrite.dll wird als "native" geladen)
           |
           v
         (BG3 liest modsettings.lsx — kann aber nicht schreiben, weil 444)
           |
           v
         BG3SE-Hook greift → "Script Extender loaded" im Hauptmenü
         Pak-Mods werden aus <prefix>/Mods/ geladen
```

### Deploy-Flow für BG3SE (Framework-Install)

```
User zieht BG3SE-Archiv in Anvil
   |
   v
bg3_installer.install_mod(archive)
   |
   v
_detect_framework_from_archive(archive) → FrameworkMod "BG3 Script Extender"
   |
   v
_install_framework(fw, archive_root, game_path)
   |
   +---> target_dir = game_path / "bin"
   |
   +---> NEU: FULL-TREE-COPY (statt nur Pattern-Match + Geschwister)
   |           alle Dateien aus archive_root → target_dir erhalten Struktur:
   |             archive_root/DWrite.dll          → bin/DWrite.dll
   |             archive_root/bg3se_updater.exe   → bin/bg3se_updater.exe
   |             archive_root/ScriptExtender/**/* → bin/ScriptExtender/**/*
   |             archive_root/ScriptExtenderSettings.json (nur wenn nicht existiert)
   |
   +---> after install:
           detect_installed prüft jetzt:
             (a) bin/DWrite.dll exists
             (b) bin/bg3se_updater.exe exists
             (c) bin/ScriptExtender/ ist ein Verzeichnis
```

### Prefix-Cache Invalidierung (Lazy-Lookup)

```
bg3_installer.__init__
   |
   v
  KEIN Cache mehr — nur Referenz auf game_plugin
   |
   v
jede Methode die _mods_path/_modsettings_path braucht:
   path = self._game_plugin.pak_mods_path()
   if path is None:
       log warning, status.bg3_proton_missing
       return
```

---

## Verwandte Bereiche (geprüft)

| Bereich | Gleicher Fix nötig? | Begründung |
| --- | --- | --- |
| Cyberpunk 2077 Launch | nein | setzt bereits `GameProtonDllOverrides = {"winmm": "native,builtin", "version": "native,builtin"}` + `GameLaunchArgs = ["--launcher-skip"]`. Als Referenz für BG3 nutzen. |
| Skyrim SE Launch (SKSE) | ja, teilweise | SKSE braucht ebenfalls Steam-Launch-Option. Neue generische Methode `get_required_steam_launch_options()` sollte Skyrim SE und Fallout 4 mitabdecken. |
| Fallout 4 Launch (F4SE) | ja, teilweise | F4SE-Proton-Shim via `get_proton_env_overrides`. Dialog-Hinweis-Logik neu generisch verwenden. |
| Starfield Launch (SFSE) | ja, teilweise | SFSE ähnlich, hat eigenen Shim. Dialog-Hinweis generisch. |
| Witcher 3 Launch | nein | kein Script Extender erforderlich. |
| `_apply_proton_dll_overrides()` in `game_panel.py:845-924` | bereits vorhanden | Bestehende Funktion wird einfach durch neuen `GameProtonDllOverrides`-Wert aktiviert. Keine Code-Änderung an der Funktion selbst nötig. |
| `silent_deploy()`-Pfad | nein | BG3 verwendet ihn nicht (`GameDataPath = ""`). BG3-Branch in `_launch_via_steam` ruft stattdessen `bg3_installer.deploy()` direkt auf. |

### Umgang mit `Mods_Core/` (Fremd-Ordner)

**Kein Löschen**, **kein Verschieben**, **kein Ignorieren**.

- Ordner wird in einem neuen read-only Hinweis-Bereich im BG3-Tab angezeigt.
- Liste der paks als nicht-editierbare Tabelle: Dateiname, Größe, mtime.
- Einmaliger Info-Dialog beim ersten Erkennen: „Anvil hat einen fremden
  Mods_Core/-Ordner im Proton-Prefix gefunden. BG3 lädt diese Dateien NICHT.
  Anvil rührt den Ordner nicht an. Du kannst ihn manuell löschen, falls
  gewünscht."
- QSettings-Flag `bg3_mods_core_dialog_seen` verhindert Wiederholung.

### Konsistenz-Repair für drei-Wege-Desync

Nicht Teil dieser Spec — separates Feature. Hier nur ERKENNUNG und ANZEIGE,
kein automatischer Fix. Zukünftige Spec: `anvil-feature-bg3-state-repair.md`.

---

## Akzeptanz-Kriterien

Alle Kriterien sind funktional testbar. Format: „Wenn User X tut, passiert Y."

- [ ] **AC-01:** Wenn User ein offizielles BG3SE-Archiv (Norbyte 7z) in Anvil
      installiert, enthält `<GameDir>/bin/` nach Deploy **alle drei**:
      `DWrite.dll` UND `bg3se_updater.exe` UND Verzeichnis `ScriptExtender/`.
- [ ] **AC-02:** Wenn `bg3se_updater.exe` ODER `ScriptExtender/` im Game-Dir
      fehlt, meldet `has_script_extender()` False — auch wenn `DWrite.dll`
      vorhanden ist.
- [ ] **AC-03:** Wenn User in der Framework-Liste auf BG3SE schaut und der
      Installationsstatus unvollständig ist, zeigt die UI zwei getrennte
      Status-Indikatoren („Datei vorhanden: ja" / „Proton-Override aktiv: nein").
- [ ] **AC-04:** Wenn Anvil `bg3_installer.deploy()` zum ersten Mal ausführt,
      steht nach Deploy in `<prefix>/user.reg` unter
      `[Software\\Wine\\AppDefaults\\bg3.exe\\DllOverrides]` der Eintrag
      `"dwrite"="native,builtin"`.
- [ ] **AC-05:** Wenn User in Anvil auf Start klickt und
      `WINEDLLOVERRIDES="DWrite.dll=n,b" %command% --skip-launcher` NICHT in
      den Steam-Launch-Options (`localconfig.vdf`) steht, erscheint ein
      Hinweis-Dialog mit „In Zwischenablage kopieren"-Button und „Steam öffnen"-Button.
- [ ] **AC-06:** Wenn User im Hinweis-Dialog „Nicht mehr anzeigen" aktiviert
      und auf Start klickt, erscheint der Dialog beim nächsten Start NICHT
      mehr (QSettings-Flag `bg3_skip_launch_options_warning=True`).
- [ ] **AC-07:** Nach Abschluss von `bg3_installer.deploy()` hat
      `modsettings.lsx` die Unix-Rechte `0o444` (read-only). Prüfbar via
      `stat -c %a <modsettings.lsx>` → Ausgabe `444`.
- [ ] **AC-08:** Wenn Anvil selbst danach erneut `deploy()` aufruft, wird
      `modsettings.lsx` kurzfristig wieder schreibbar (`0o644`), neu geschrieben,
      und am Ende wieder auf `0o444` gesetzt. Kein `PermissionError` im Log.
- [ ] **AC-09:** Wenn User Anvil startet BEVOR BG3 jemals gestartet wurde
      (Prefix existiert nicht), wird nach dem ersten BG3-Start der Prefix
      automatisch erkannt und Deploy greift ohne Instance-Reload (Lazy-Lookup
      von `_mods_path`).
- [ ] **AC-10:** Wenn User BG3 via Anvil-Start-Button startet und Steam-Launch-Options
      korrekt gesetzt sind, erscheint nach dem Laden des Hauptmenüs der
      „Script Extender loaded"-Banner ingame.
- [ ] **AC-11:** Wenn User in Anvil 3 Pak-Mods aktiviert und BG3 startet,
      liegen diese 3 Paks physisch in
      `<prefix>/drive_c/users/steamuser/AppData/Local/Larian Studios/Baldur's Gate 3/Mods/`
      und erscheinen ingame im BG3-Mod-Menü.
- [ ] **AC-12:** Wenn der Proton-Prefix einen Ordner `Mods_Core/` enthält,
      zeigt Anvil einen read-only Hinweis-Bereich im BG3-Tab mit der Liste
      der dortigen Paks. Anvil löscht oder ändert NICHTS in diesem Ordner.
- [ ] **AC-13:** Wenn User BG3 via Anvil startet und der Larian-Launcher
      trotzdem aufgeht (weil `--skip-launcher` in Steam-Launch-Options fehlt)
      und auf „Play" klickt, bleibt `modsettings.lsx` durch `chmod 444`
      unverändert — aktive Mods sind nach dem Launcher-Schritt weiterhin
      in der Datei.
- [ ] **AC-14:** Wenn User BG3SE über Anvil deinstalliert, werden
      `bin/DWrite.dll`, `bin/bg3se_updater.exe` UND `bin/ScriptExtender/`
      entfernt. `has_script_extender()` meldet danach False.
- [ ] **AC-15:** Wenn Anvil den `WINEDLLOVERRIDES`-Dialog anzeigt, enthält
      der dargestellte String 1:1 `WINEDLLOVERRIDES="DWrite.dll=n,b" %command% --skip-launcher`
      — identisch zur Rückgabe von `BG3ScriptExtender.steam_launch_options()`.
- [ ] **AC-16:** Wenn User den Copy-Button im Hinweis-Dialog klickt, ist der
      oben genannte String über `xclip`/Qt-Clipboard in der Zwischenablage
      verfügbar.
- [ ] **AC-17:** Wenn User BG3 ohne installiertes BG3SE startet und nur
      Pak-Mods aktiv sind, startet das Spiel, die Paks werden geladen,
      und KEIN DllOverride-Dialog erscheint (da `has_script_extender()` False
      und Plugin `get_required_steam_launch_options()` bei fehlender BG3SE-Installation
      None zurückgeben darf).
- [ ] **AC-18:** `restart.sh` startet ohne Fehler.

---

## Offene Punkte (für Workflow-Agent zu klären)

1. `_apply_proton_dll_overrides()` modifiziert `user.reg` — ist der Prefix
   beim ersten Start eventuell noch leer? Prüfen, ob der Prefix vor dem
   Override-Schreiben existiert; falls nicht: auf Post-Launch-Apply verlegen
   (einmaliger zweiter Start nötig).
2. `/mnt/gamingS/` ist ext4/btrfs — `chmod 444` funktioniert. Bei NTFS-Mounts
   (theoretisch möglich bei fremden Steam-Libraries) fallbacken auf
   `chattr +i` oder Hinweis-Dialog.
3. Soll die neue Plugin-Methode `get_required_steam_launch_options()` auch
   von Skyrim SE / Fallout 4 / Starfield in diesem Sprint umgesetzt werden?
   → Empfehlung: nur Interface + BG3-Implementation in diesem Feature;
   andere Games in separatem Folge-Feature.
