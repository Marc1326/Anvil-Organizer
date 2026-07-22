# Anvil Organizer — Games-Übersicht (Stand: 21.03.2026)

## Verwaltete Games

| Game | Plugin | Status | Store | Game-Pfad |
|------|--------|--------|-------|-----------|
| Cyberpunk 2077 | `game_cyberpunk2077.py` | Aktiv | Steam (lokal) | `~/.local/share/Steam/.../Cyberpunk 2077` |
| Baldur's Gate 3 | `game_baldursgate3.py` | Aktiv | Steam (extern) | `/mnt/gamingS/.../Baldurs Gate 3` |
| Fallout 4 | `game_fallout4.py` | Aktiv | Steam (extern) | `/mnt/gamingS/.../Fallout 4` |
| Red Dead Redemption 2 | `game_rdr2.py` | Aktiv | Steam (extern) | `/mnt/gamingS/.../Red Dead Redemption 2` |
| The Witcher 3 | `game_witcher3.py` | Aktiv | Steam (extern) | `/mnt/gamingS/.../The Witcher 3` |
| Skyrim SE | `game_skyrimse.py` | **WIP** (`_wip/`) | Steam (extern) | `/mnt/gamingS/.../Skyrim Special Edition` |

### WIP-Plugins (noch nicht aktiv)
`game_bannerlord.py`, `game_eldenring.py`, `game_fallout3.py`, `game_falloutnv.py`, `game_morrowind.py`, `game_oblivion_remastered.py`, `game_skyrimse.py`, `game_stardewvalley.py`, `game_starfield.py`

---

## Cyberpunk 2077

| Eigenschaft | Wert |
|-------------|------|
| **Installierte Mods** | 518 (davon 19 Separatoren) |
| **modlist.txt** | 518 Einträge (499 Mods + 19 Separatoren) |
| **Profile** | Default (169 aktiv), Profile (27), ebbp (37), ebb (27), **Vanilla (353)** |
| **Aktives Profil** | Vanilla |
| **Deployed** | 363 Mods → 1614 Dateien |
| **Deploy-Typen** | 95 copy (Frameworks), 203 shim_copy (CET-Lua), 1316 symlink (normal) |
| **GameDataPath** | `""` (Root-Verzeichnis) |
| **Downloads** | `/home/mob/Downloads/Mods/CP/resources` |
| **Proton** | Ja (Steam native Linux) |

### Spezielle Plugin-Attribute
- **GameDirectInstallMods**: Frameworks (RED4ext, CET, ArchiveXL, Codeware, RedScript, TweakXL, etc.) — werden als Kopien ins Game-Root installiert, immer deployed unabhängig von active_mods.json
- **GameCopyDeployPaths**: `bin/x64/plugins/cyber_engine_tweaks/` — CET-Lua-Dateien werden als Kopien statt Symlinks deployed (Wine/Proton kann Symlinks in CET nicht folgen)
- **GameProtonDllOverrides**: `winmm=native,builtin`, `version=native,builtin`

### Deploy-Kette
1. Frameworks → `shutil.copy2()` (copy)
2. CET-Lua-Mods → `shutil.copy2()` (shim_copy) — Dateien unter `bin/x64/plugins/cyber_engine_tweaks/`
3. Alles andere → `os.symlink()` (symlink)

**Status:** Konsistent — keine Inkonsistenzen. (Mod-Namen mit `-4x-` Prefix sind korrekt in modlist und .mods/)

---

## Baldur's Gate 3

| Eigenschaft | Wert |
|-------------|------|
| **Installierte Mods** | 3 (Eyes of The Beholder, Honey's Hair Kitchen, Bags Bags Bags) |
| **modlist.txt** | In `Default/modlist.txt` (pro Profil, nicht global!) — 3 Mods, alle deaktiviert (`-`) |
| **Profile** | Default |
| **Deployed** | Nein (kein Manifest) |
| **GameDataPath** | `""` (verschiedene Pfade je nach Mod-Typ) |
| **Downloads** | `/home/mob/Downloads/Mods/BG3` |
| **Spezielles** | Eigener `bg3_mod_handler.py` für PAK-Mods |

### Data Overrides (direkt installierte Mods)
- **WASD** (BG3WASD.dll + BG3WASD.toml) → `Data/NativeMods/`
- **NativeModLoader** (bink2w64.dll) → `Data/`

**Hinweis:** BG3 hat kein globales modlist.txt — die modlist.txt liegt pro Profil in `.profiles/Default/modlist.txt`. Kein active_mods.json vorhanden.

---

## Fallout 4

| Eigenschaft | Wert |
|-------------|------|
| **Installierte Mods** | 12 Mods + 1 Separator |
| **modlist.txt** | 13 Mods + 1 Separator — alle mit `+` markiert |
| **active_mods.json** | Nur 1 Eintrag (der Separator) — **0 Mods aktiviert** |
| **Profile** | Default |
| **Deployed** | Nein (kein Manifest) |
| **GameDataPath** | `Data` (Mods → `<GameDir>/Data/`) |
| **Downloads** | `/mnt/gamingS/Mods-test/Fallout 4` |
| **Spezielles** | F4SE Proton Shim (eigenes Agent-System), BA2-Packing Support |

### Installierte Mods
Game Configuration Menu, Better Console, Mod Configuration Menu 1.43, LooksMenu, CBBE, Mentats - F4SE, Undressed Character Creation, Lacy Underwear, Orgasm BodySlide Preset, Unlimited Survival Mode - F4SE, Ponytail Hairstyles, Freyna Outfit

### Inkonsistenz
- modlist.txt hat alle 13 Einträge als `+` (aktiviert), aber active_mods.json enthält **nur den Separator** → 0 Mods werden deployed

---

## Red Dead Redemption 2

| Eigenschaft | Wert |
|-------------|------|
| **Installierte Mods** | 4 |
| **modlist.txt** | 2 Mods (VESTIGIA, the spoils of conquest) |
| **active_mods.json** | 2 Mods aktiv |
| **Profile** | Default |
| **Deployed** | Nein (kein Manifest) |
| **GameDataPath** | `""` (Root-Verzeichnis) |
| **Downloads** | `/mnt/gamingS/Mods-test/RDR2` |
| **Spezielles** | Hat GameDirectInstallMods (Frameworks direkt ins Root) |

### Inkonsistenz
- 4 Mods installiert, aber nur 2 in modlist.txt
- **Nicht in modlist:** "Ped Damage Overhaul Reloaded", "Ped Damage Overhaul - With Optional Files"

---

## The Witcher 3: Wild Hunt

| Eigenschaft | Wert |
|-------------|------|
| **Installierte Mods** | 6 |
| **modlist.txt** | 6 Mods — alle mit `+` markiert |
| **active_mods.json** | 6 Mods aktiv |
| **Profile** | Default |
| **Deployed** | Nein (kein Manifest) |
| **GameDataPath** | `Mods` (Mods → `<GameDir>/Mods/`) |
| **Downloads** | `/mnt/gamingS/Mods-test/Witcher` |

### Installierte Mods
Better Trophies, Brothers In Arms - Ultimate Edition, Indestructible Items (4.03), modBloodAndSteel (Next Gen), modAutoApplyOilsMenu cn, Over

**Status:** Konsistent — alle Mods installiert, in modlist, und aktiviert.

---

## Skyrim Special Edition

| Eigenschaft | Wert |
|-------------|------|
| **Installierte Mods** | 5 |
| **modlist.txt** | 6 Einträge |
| **active_mods.json** | 5 Mods aktiv |
| **Profile** | Default |
| **Deployed** | Nein (kein Manifest) |
| **GameDataPath** | (Plugin in `_wip/`) |
| **Downloads** | `/mnt/gamingS/Mods-test` |

### Inkonsistenzen
- **In modlist aber kein Ordner:** "Unofficial Skyrim Special Edition Patch", "skse" — Mods gelöscht oder nie richtig installiert
- **Ordner existiert aber nicht in modlist:** "SkyUI 5 2 SE" — installiert aber nicht in modlist eingetragen
- Plugin `game_skyrimse.py` liegt in `_wip/` — nicht produktiv

---

## Laufwerke

| Pfad | Beschreibung |
|------|-------------|
| `/home/mob/.local/share/Steam/` | Steam lokal (Cyberpunk) |
| `/mnt/gamingS/SteamLibrary/` | Externes Gaming-Laufwerk (alle anderen Games) |
| `/home/mob/.anvil-organizer/instances/` | Anvil Instanz-Daten |

---

## Zusammenfassung Inkonsistenzen

| Game | Problem |
|------|---------|
| **Cyberpunk 2077** | Keine Probleme — alles konsistent |
| **BG3** | Kein globales modlist.txt, kein active_mods.json — anderes System als die anderen Games |
| **Fallout 4** | 0 Mods aktiv obwohl 12 installiert und alle `+` in modlist — active_mods.json fast leer |
| **RDR2** | 2 von 4 installierten Mods fehlen in modlist.txt |
| **Skyrim** | 2 Mods in modlist ohne Ordner + 1 Ordner nicht in modlist + Plugin = WIP |
| **Witcher 3** | Keine Probleme — alles konsistent |
