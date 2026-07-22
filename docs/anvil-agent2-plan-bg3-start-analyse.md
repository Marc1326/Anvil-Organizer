# Planer-Agent 2 — Physische Analyse: BG3 Start ohne Mods / BG3SE nicht geladen

Datum: 2026-04-21
Rolle: Agent 2/4 (Physische Datei-Analyse, Proton-Prefix, Deploy-Realität)

## TL;DR — Kernbefunde

1. **BG3SE ist unvollständig installiert.** Im `bin/`-Ordner liegt nur `DWrite.dll` + `ScriptExtenderSettings.json`. Der `ScriptExtender/`-Unterordner und `bg3se_updater.exe` FEHLEN. Das ist eine halbe/unvollständige BG3SE-Installation.
2. **KEIN DllOverride für DWrite in Proton user.reg** — weder global noch für `bg3.exe` spezifisch. Unter Proton wird `DWrite.dll` somit NICHT als „native" geladen. BG3SE kann sich nicht einhaken → „Script Extender loaded" erscheint nicht.
3. **Massive Desynchronisation Anvil ↔ modsettings.lsx ↔ Mods-Ordner:**
   - Anvil `.mods/` = **8 Mods** (alle `-` deaktiviert in modlist.txt)
   - `bg3_modstate.json mod_order` = **90+ Mods** (mit detaillierten Metadaten)
   - `modsettings.lsx ModOrder` = Dutzende UUIDs (sehr viel)
   - `AppData/.../Mods/` = **~19 .pak-Dateien** (meist ALTE Mods, nicht die aus Anvil)
   - `AppData/.../Mods_Core/` = **~80 .pak-Dateien** (großer Legacy-Dump)
4. Anvil hat BG3SE NICHT als Framework-Mod installiert (kein `.mods/*Extender*`-Ordner). BG3SE liegt nur manuell in `bin/`.

## 1. BG3 Install-Pfad — gefunden

### libraryfolders.vdf (Steam)
Datei: `/home/mob/.steam/steam/steamapps/libraryfolders.vdf`

Drei Libraries:
- `0`: `/home/mob/.local/share/Steam` (BG3-Toolkit 1091500)
- `1`: `/mnt/Gaming2/SteamLibrary`
- `2`: `/mnt/gamingS/SteamLibrary` → enthält App-ID **1086940 (BG3)** mit 159 GB

### BG3-Install-Pfad
**`/mnt/gamingS/SteamLibrary/steamapps/common/Baldurs Gate 3/`** (Leerzeichen, kein Apostroph)

Desktop-Eintrag: `/home/mob/.local/share/applications/Baldur's Gate 3.desktop` → `steam://rungameid/1086940`

## 2. BG3 Game-Ordner physisch geprüft

### `bin/`-Ordner — KRITISCH

Ausgeführt: `Glob /mnt/gamingS/SteamLibrary/steamapps/common/Baldurs Gate 3/bin/*`

Relevante Files (ohne CrashDumps):
```
bin/DWrite.dll                      ← BG3SE Einstiegs-DLL (VORHANDEN)
bin/ScriptExtenderSettings.json     ← VORHANDEN
bin/bg3.exe                         ← Hauptspiel (Vulkan)
bin/bg3_dx11.exe                    ← DX11-Variante
bin/Osiris.dll                      ← Larian Osiris-Engine (nicht BG3SE)
bin/steam_api64.dll
bin/amd_ags_x64.dll
bin/SDL2.dll
bin/ChromaAppInfo.xml
... viele .dmp CrashDumps von 02-11-2026
```

### FEHLENDE BG3SE-Komponenten

- `bin/bg3se_updater.exe` — **NICHT VORHANDEN**
- `bin/ScriptExtender/` (Unterordner) — **NICHT VORHANDEN**

Ausgeführt: `Glob /bin/ScriptExtender/**` → "No files found"
Ausgeführt: `Glob /bin/bg3se*` → "No files found"

**Bedeutung:** BG3SE ist nur zur Hälfte installiert. `DWrite.dll` ist da, aber:
- Kein Updater → Anvil kann keine Version prüfen
- Kein ScriptExtender-Unterordner → BG3SE hat keine Core-Dateien zum Laden

### DWrite.dll — echte DLL
Read-Versuch liefert Fehler: *„This tool cannot read binary files. The file appears to be a binary .dll file."*

→ Es ist eine echte PE-DLL, kein Symlink. Die Datei ist da.

### ScriptExtenderSettings.json — Inhalt
```json
{"CreateConsole": true, "EnableAchievements": true}
```

Minimal — typische manuelle BG3SE-Basiskonfiguration.

### Launcher-Dateien
`Glob bin/launch*` → keine Ergebnisse.
→ Kein native Linux-Launcher-Wrapper. Start erfolgt über Steam/Proton direkt auf `bg3.exe`.

## 3. Proton-Prefix gefunden

**Pfad:** `/mnt/gamingS/SteamLibrary/steamapps/compatdata/1086940/pfx/`

(nicht wie vermutet in `~/.steam/steam/steamapps/compatdata/1086940`, dort existiert kein Compatdata für 1086940)

### user.reg — AppDefaults für bg3.exe

Ausgeführt: `Grep "bg3\.exe"` und `Grep -i "Baldur|bg3"` in `/mnt/gamingS/SteamLibrary/steamapps/compatdata/1086940/pfx/user.reg`

**Ergebnis: KEINE Treffer.**

→ Es gibt **keinen AppDefaults-Eintrag** für `bg3.exe` in der user.reg. Insbesondere:
- Kein `[Software\Wine\AppDefaults\bg3.exe\DllOverrides]`-Block
- Kein `"dwrite"="native"` oder `"dwrite"="native,builtin"`

### user.reg — globale DllOverrides

Zeilen 1183–1213: Standard Proton-DllOverrides (api-ms-win-crt-*, msvcp*, msvcr*, ucrtbase). **Kein dwrite-Eintrag.**

Andere Spiele setzen spezifische Overrides (RDR2 = vulkan-1 native, ShadowOfWar = atiadlxx disabled), aber für BG3 existiert kein solcher Block.

## 4. Anvil Mod-Ordner geprüft

### Instanz-Config

Datei: `/home/mob/.anvil-organizer/instances/Baldur's Gate 3/.anvil.ini`

```ini
[%General]
created=2026-02-11T08:28:31.255405+00:00
detected_store=steam
game_name=Baldur's Gate 3
game_path=/mnt/gamingS/SteamLibrary/steamapps/common/Baldurs Gate 3
game_short_name=baldursgate3
local_inis=true
local_saves=false
selected_profile=Default

[Paths]
downloads_directory=/home/mob/Downloads/Mods/BG3
mods_directory=%INSTANCE_DIR%/.mods
overwrite_directory=%INSTANCE_DIR%/.overwrite
profiles_directory=%INSTANCE_DIR%/.profiles
```

→ Pfade zeigen korrekt auf BG3-Install. `game_path` stimmt mit physischem Fund überein.

### Installierte Mods in Anvil (`.mods/`)

Nur **8 Mod-Ordner** vorhanden:

| Ordner | pak-Datei |
|---|---|
| `Eyes of The Beholder - Main/` | EyesOfTheBeholder.pak |
| `Honey's Hair Kitchen - WIP/` | HairKitchen.pak |
| `Bags Bags Bags/` | BagsBagsBags.pak |
| `Yir'eh Head Preset (Glow Eyes)/` | Yireh Head Preset [Glow Eyes].pak |
| `Yir'eh Head Preset/` | Yireh Head Preset.pak |
| `SGT Darling face (New heads)/` | SGT_Darling face.pak |
| `Better Trade Menu (16 to 10)/` | BetterTradeMenuOneSixOneZero_....pak |
| `Vemperen's Other Heads/` | Vemperen_Heads_Fixed.pak |

**KEIN `*BG3SE*`/`*ScriptExtender*`/`*Extender*`-Ordner** in `.mods/`. BG3SE ist in Anvil NICHT als Mod registriert.

### modlist.txt (Profil Default)

Datei: `/home/mob/.anvil-organizer/instances/Baldur's Gate 3/.profiles/Default/modlist.txt`

```
# Managed by Anvil Organizer v2
-Eyes of The Beholder - Main
-Honey's Hair Kitchen - WIP
-Bags Bags Bags
-Yir'eh Head Preset (Glow Eyes)
-Yir'eh Head Preset
-SGT Darling face (New heads)
+test_separator
```

**Alle Mods sind mit `-` DEAKTIVIERT!** Nur ein Separator ist `+` aktiv. Das ist der Hauptgrund, warum Anvil beim Deploy keine Mods ins BG3-Mods-Verzeichnis schiebt.

`Better Trade Menu` und `Vemperen's Other Heads` erscheinen gar nicht in modlist.txt, obwohl sie als Mod-Ordner existieren → modlist.txt ist kaputt/veraltet.

### active_mods.json

Datei: `/home/mob/.anvil-organizer/instances/Baldur's Gate 3/.profiles/Default/active_mods.json`

Enthält **~90 UUIDs und einige Nexus-IDs + 1 Separator-Namen** (`Test Trenner_separator`, `Dwarves-652-...`, etc.).

**Diskrepanz:** active_mods.json listet massenhaft Mods, von denen die meisten NICHT in `.mods/` als Ordner existieren!

### bg3_modstate.json

Datei: `/home/mob/.anvil-organizer/instances/Baldur's Gate 3/bg3_modstate.json`

- `mod_order`: **90 UUIDs**
- `mods`: **90 detaillierte Mod-Einträge** (uuid, name, folder, md5, version64, pak_file)

Beispiele: GustavX (cb555efe-…), BG3AF, BG3SX, SweatySex, MaeveHead, Vemperen, CommunityLibrary, Expansion, HairKitchen, Silver_HairPack, etc.

**Kritisch:** Die Metadaten in bg3_modstate.json beschreiben Mods, für die es **keine Ordner in Anvils `.mods/`** gibt. Das sind „Phantom-Mods", die aus früheren Deploys oder Imports übriggeblieben sind.

## 5. pak-Dateien im Proton-Prefix

### `Mods/`-Ordner (was BG3 beim Start tatsächlich lädt)

Pfad: `/mnt/gamingS/.../compatdata/1086940/pfx/drive_c/users/steamuser/AppData/Local/Larian Studios/Baldur's Gate 3/Mods/`

**~19 .pak-Dateien** (+ `.disabled/` Unterordner mit 4 paks):

```
Vemperen_Heads_Fixed.pak             ← einzige die mit Anvil übereinstimmt
MaeveHead.pak                        ← nicht in Anvil .mods/
Leila Preset.pak                     ← nicht in Anvil .mods/
Silver_HairPack.pak                  ← nicht in Anvil .mods/
Silver_HairPack2.pak
jerinski_piercingedits.pak
DynamicSidebar169AH_5474a353-….pak
UnlockLevelCurve_Patch_5eSpells.pak
UnlockLevelCurve.pak
Unshar_Your_Shart_ReplacerA_Style2.pak
EasyCheat.pak
UnlockLevelCurve_Patch_XP_x0.5.pak
AppearanceEditOrigins.pak
UnlockLevelCurve_Patch_Improvement_Lv2.pak
ModFixer.pak
.disabled/Unshar_Your_Shart_ReplacerA_Style3.pak
.disabled/UnlockLevelCurve_Patch_XP_NewScale.pak
.disabled/Ultimate_Cheat_Spells.pak
```

**Befund:** Nur **1 von 8** Anvil-Mods liegt tatsächlich hier (Vemperen). Der Rest (Eyes of The Beholder, Honey's Hair Kitchen, Bags Bags Bags, Yir'eh, SGT Darling, Better Trade Menu) FEHLT im Deploy-Target.

### `Mods_Core/`-Ordner — nicht-standard

Pfad: `…/AppData/Local/Larian Studios/Baldur's Gate 3/Mods_Core/`

**~80 .pak-Dateien** inkl. GustavX-Fragmente, BG3AF, BG3SX, CommunityLibrary, Expansion, viele Hair-/Head-Mods usw.

→ Das ist **kein Standard-BG3-Ordner**. Entweder von einem anderen Tool oder einem früheren Anvil-Deploy-Bug erzeugt. BG3 lädt aus `Mods_Core/` regulär NICHT.

## 6. modsettings.lsx

Datei: `/mnt/gamingS/.../PlayerProfiles/Public/modsettings.lsx`

- XML-Version 4.8.0.700
- `<node id="ModOrder">` enthält **Dutzende** `<node id="Module" UUID="..."/>` Einträge (~ Zeilen 7–27306, Datei zu groß zum vollständigen Lesen)

Beispiel-UUIDs (ersten 10):
```
cb555efe-2d9e-131f-8195-a89329d218ea   (GustavX)
e641c689-4da2-42d0-a286-aeb962618556   (BG3AF)
df8b9877-5662-4411-9d08-9ee2ec4d8d9e   (BG3SX)
6db3c660-a33d-49ee-aaaa-a16c18e75f3e   (BG3SX AnimAddon)
14bb099a-6a83-45de-a688-b333babd5d72   (SweatySex)
8cebc804-b1ff-4c68-86fa-ffac9f4c191f   (Maeve Head)
633c5be8-1044-4408-aa4f-531a733f9e9e   (Leila Head Preset)
ef0fb0e3-a4e1-4672-84b3-bc63260e12af   (Vemperen's Other Heads)
56f43956-b1cb-43c6-badc-782c1e0def0f   (Myky's Heads)
4cd3ad72-b261-9f3d-6191-f4af18d069ca   (Mantis' Face Preset II)
```

**Befund:** modsettings.lsx listet massenhaft Mods, deren pak-Dateien in `Mods_Core/` liegen, aber **nicht im aktiven `Mods/`**-Ordner. Der User-Wunsch laut modsettings.lsx ist, dass diese Mods aktiv sind — aber BG3 findet die pak-Dateien nicht am erwarteten Ort, also werden sie beim Start ignoriert.

Nur `Vemperen's Other Heads` (UUID `ef0fb0e3-…`) hat sowohl einen modsettings-Eintrag ALS AUCH eine pak in `Mods/` → vermutlich die einzige Mod, die aktuell wirklich lädt.

## 7. BG3SE-Mod in Downloads

Nexus-ID 2172 (BG3 Script Extender) liegt in `/home/mob/Downloads/Mods/BG3/`:
```
Norbyte's Baldur's Gate 3 Beta Script Extender-2172-2024April-30-1715333040.7z
Norbyte's Baldur's Gate 3 Beta Script Extender-2172-2024April-30-1715333040_1.7z
Norbyte's Baldur's Gate 3 Beta Script Extender-2172-2024April-30-1715333040_2.7z
```

→ Heruntergeladen, aber **nicht installiert über Anvil** (kein Mod-Ordner in `.mods/`). Das `bin/DWrite.dll` ist vermutlich manuell aus einem dieser 7z entpackt worden, wobei nur die DLL herausgenommen wurde und der restliche ScriptExtender/-Inhalt fehlt.

## 8. Warum „Script Extender loaded" nicht erscheint — Ursachen-Analyse

### Ursache 1 (PRIMÄR): Proton lädt DWrite.dll nicht als native

Ohne `[Software\Wine\AppDefaults\bg3.exe\DllOverrides]` mit `"dwrite"="native"` wird Wine/Proton die eigene builtin-dwrite.dll laden, NICHT die BG3SE-DWrite.dll im bin/-Ordner. → BG3SE hooked nie.

**Fix-Richtung (Referenz für Agent 3):**
- Vor BG3-Start muss Anvil `WINEDLLOVERRIDES="dwrite=n,b"` setzen, ODER
- Anvil muss einmalig in die Proton user.reg einen AppDefault-Block für `bg3.exe` schreiben.

### Ursache 2: BG3SE ist unvollständig

Nur `DWrite.dll` + `ScriptExtenderSettings.json` sind da. Es fehlen:
- `ScriptExtender/`-Ordner (mit ScriptExtenderCore-Dateien)
- `bg3se_updater.exe`

Selbst mit korrektem DllOverride würde BG3SE vermutlich nicht voll laden, weil die Core-Dateien fehlen.

### Ursache 3 (NEBEN): Mods werden nicht deployed

Alle 8 Anvil-Mods sind in modlist.txt mit `-` deaktiviert → mod_deployer kopiert keine in `Mods/`. Das erklärt „keine Mods werden geladen", aber nicht direkt BG3SE.

### Ursache 4: modsettings.lsx und Mods-Ordner divergieren stark

modsettings.lsx enthält Dutzende Mods, deren paks in `Mods_Core/` liegen, nicht in `Mods/`. BG3 ignoriert sie. Der User hat vermutlich historisch mit einem anderen Manager gearbeitet und modsettings.lsx ist nie aufgeräumt worden.

## 9. Physische Befunde — Zusammenfassung

| Prüfung | Befund | Ausführung |
|---|---|---|
| BG3-Install-Pfad | `/mnt/gamingS/SteamLibrary/steamapps/common/Baldurs Gate 3/` | `Glob /mnt/gamingS/SteamLibrary/steamapps/common/**` + libraryfolders.vdf Read |
| Proton-Prefix | `/mnt/gamingS/SteamLibrary/steamapps/compatdata/1086940/pfx/` | `Glob /mnt/gamingS/.../compatdata/1086940/**` |
| bin/DWrite.dll existiert | JA, echte PE-DLL (kein Symlink) | `Glob bin/*` + Binary-Read-Fehler |
| bin/ScriptExtender/ | FEHLT | `Glob bin/ScriptExtender/**` |
| bin/bg3se_updater.exe | FEHLT | `Glob bin/bg3se*` |
| DllOverride dwrite in user.reg | FEHLT | `Grep dwrite` in user.reg |
| AppDefaults für bg3.exe | FEHLT | `Grep bg3\.exe` in user.reg |
| Anvil `.mods/` BG3SE-Ordner | FEHLT | `Glob .mods/*Extender*`/`*Script*` |
| Anvil Instanz BG3 vorhanden | JA, `/home/mob/.anvil-organizer/instances/Baldur's Gate 3/` | `Glob .anvil.ini` |
| Anvil game_path korrekt | JA | Read `.anvil.ini` |
| `.mods/`-Ordner Anzahl | 8 Mod-Ordner | `Glob .mods/*` |
| modlist.txt Active/Inactive | Alle 8 Mods `-` deaktiviert, 1 Separator `+` | Read modlist.txt |
| active_mods.json | ~90 UUIDs (diverge!) | Read active_mods.json |
| bg3_modstate.json mods | 90 Einträge | Read bg3_modstate.json |
| Proton `Mods/`-Ordner paks | 19 paks (+4 `.disabled/`) | `Glob .../Mods/*` |
| Proton `Mods_Core/`-Ordner | 80 paks — Legacy-Dump | `Glob .../Mods_Core/*` |
| modsettings.lsx vorhanden | JA (Public-Profil) | `Glob .../modsettings.lsx` |
| modsettings.lsx Mods aktiv | Dutzende UUIDs | Read modsettings.lsx (limit=80) |
| BG3SE-Download in Anvil | JA, 3× 7z in Downloads/Mods/BG3/ | `Glob Downloads/Mods/BG3/*Extender*` |

## 10. Kernaussage für Agent 4 (Feature-Spec-Autor)

### Bug-Kategorien

1. **BG3SE wird nicht von Proton geladen** — zentraler Bug: Anvil muss `WINEDLLOVERRIDES=dwrite=n,b` setzen oder den Proton-Registry-Eintrag schreiben, bevor BG3 startet.
2. **BG3SE-Installation unvollständig** — Anvil hat BG3SE nicht korrekt als Framework-Mod installiert; nur DWrite.dll liegt manuell im bin/. Die Core-Dateien (ScriptExtender/, Updater) fehlen.
3. **modlist.txt vs. bg3_modstate.json divergieren** — modlist.txt deaktiviert alle Mods, aber bg3_modstate.json und modsettings.lsx zeigen Dutzende aktive Mods. Deploy-Logik weiß nicht, was gelten soll.
4. **Anvil deployed die eigenen Mods nicht in den Proton-Prefix** — von 8 Mods liegt nur 1 im aktiven `Mods/`-Ordner. Deploy-Code für BG3 bricht offenbar ab oder schreibt nach `Mods_Core/` statt `Mods/`.
5. **Legacy-Dump in `Mods_Core/`** — aufräumen nötig, oder Anvil muss erkennen, dass BG3 auf `Mods/` schaut, nicht `Mods_Core/`.

### Empfehlungen an Agent 3 (Architektur)

- Neue Start-Logik für BG3: Proton-DllOverrides injizieren (Environment-Variable oder user.reg Patch).
- BG3SE-Installer überarbeiten: muss die VOLLSTÄNDIGEN Archiv-Inhalte nach `bin/` entpacken, nicht nur DWrite.dll.
- Deploy-Code prüfen: warum landen die Mods nicht im korrekten `Mods/`-Ordner? Und wer hat `Mods_Core/` erzeugt?
- Sync-Logik für modlist.txt/bg3_modstate.json/active_mods.json klären — aktuell eine drei-Wege-Inkonsistenz.
- `has_script_extender()` verbessern: nicht nur DWrite.dll prüfen, sondern auch `ScriptExtender/`-Ordner und `ScriptExtenderSettings.json` und ob der DllOverride gesetzt ist.

## 11. Nicht geprüft (außerhalb Scope)

- Genauer Inhalt der modsettings.lsx > 80 Zeilen (zu groß für einen Read-Call, aber aus Zeilen 1–80 ist die Struktur klar und die Divergenz offensichtlich).
- Direkter Inhalt der paks (Hash, Version) — nicht nötig für diese Bug-Analyse.
- BG3-Toolkit 1091500 Prefix — nicht relevant für BG3-Start.
