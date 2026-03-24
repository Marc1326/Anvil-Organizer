# Anvil Organizer v0.3.0 — Changelog

## Starfield — New Game Support

- **Full Starfield support added** — New game plugin with store detection (Steam/GOG), Proton prefix paths, save game directory, and all MO2-equivalent attributes.
- **SFSE (Starfield Script Extender)** — Proton Shim for automatic SFSE injection via `version.dll` proxy. Address Library detection and installation supported.
- **Steam & Proton launch** — Starfield launches correctly through Steam with Proton compatibility.

---

## Deployer — Cyberpunk Frameworks (broken since v0.1.0)

- **Frameworks are always deployed** — Frameworks were no longer deployed after the migration to `active_mods.json` because they were not listed there. Fix: `GameDirectInstallMods` are now always deployed regardless of `active_mods.json`.
- **Deployer priority order fixed** — `enabled_mods` list was not reversed for "last wins" logic, causing wrong mod priority during deploy.
- **`root/` prefix is stripped** — RED4ext archives contain a `root/` directory (MO2 RootBuilder pattern). Fix: `root/` prefix is automatically removed.
- **Frameworks can overwrite real files** — The safety check was blocking frameworks. Fix: `GameDirectInstallMods` bypass the check.
- **CET folder structure repaired** — `_flatten_single_subfolder()` was flattening `bin/x64/` to `x64/`. Protected game folders from being flattened.
- **RedData leftover scripts removed** — After uninstallation, `.reds` scripts remained in the game directory.

---

## New Features

- **Game Running Lock** — UI is locked while a game is running, preventing accidental changes to the mod list during gameplay.
- **GameCopyDeployPaths** — CET Lua mods are deployed as copies instead of symlinks (CET's Lua VM cannot follow symlinks through Wine's `S:` drive). For Cyberpunk: `bin/x64/plugins/cyber_engine_tweaks/`.
- **Image tab in mod detail dialog** — View mod screenshots and images directly in the mod detail view.
- **Deploy filter for root files** — Root-level files in mod archives are filtered correctly during deployment.
- **Framework update dialog** — Confirmation prompt when a framework is already installed.
- **Separator counter fix** — No longer counts separators, only real mods.
- **New instance creates global modlist.txt (v2)** — New instances now use the v2 modlist format instead of the legacy Default/modlist.txt.
- **Repair script for broken mod folders** — Automatically detects and repairs corrupted mod folder structures.

---

## Nexus Integration

- **Fetch Nexus info (right-click)** — Now works automatically. Finds the mod ID through 3 methods:
  1. `installationFile` from `meta.ini` → recursively search for `.meta` file in downloads folder
  2. Fallback: Parse `modID` from the archive filename (e.g. `Sweaty 25-874-1-5-...` → `874`)
  3. Fallback 2: Search archive filenames in downloads folder + parent directories that contain the mod name
  - No dialog, no window — fully automatic
- **Nexus data no longer overwrites mod names** — Nexus data is stored as `nexusName`, `nexusAuthor`, `nexusURL` (instead of `name`, `author`, `url`). The mod folder name in the `[installed]` section remains unchanged.
- **Nexus info on install from download** — When installing from a Nexus download, `modID` + `installationFile` are automatically transferred from the `.meta` file to the mod's `meta.ini`.
- **Nexus info tab in mod detail dialog** — Was previously a disabled placeholder. Now shows: Mod ID, name, author, version, URL (clickable), game, endorsement status, category, last query, description. Translations in all 7 languages (de, en, es, fr, it, pt, ru).
- **Next/Previous navigation in mod detail dialog** — Buttons navigate through the mod list (separators are skipped). Selection in the mod list follows along. Wrap-around at start/end.

---

## BG3 (Baldur's Gate 3) — Complete Overhaul

- **Unified mod list** — Active/inactive split removed, all mods in a single list.
- **Auto-Deploy** — Every change (enable, disable, reorder) is immediately written to `modsettings.lsx`.
- **All Anvil features now available for BG3** — Separators, drag & drop, profiles, context menu, double-click.
- **Dedicated data source** — BG3 uses `bg3_modstate.json` as master state, independent from other games.
- **Profiles separated per game** — No more mixing between games.
- **BG3WASD recognized as framework** — Drag & drop installation directly to `bin/NativeMods/`.
- **NativeModLoader correctly installed** — Now installed to `bin/` instead of incorrectly to `Data/`.
- **BG3 mod search** — Main search field now works for BG3 mods.
- **BG3 download tab** — Installation from downloads + drag & drop indicator working correctly.
- **BG3 downloads marked as installed** — Downloaded mods are correctly marked after installation.
- **BG3 Proton prefix fix** — Prefers primary Steam ID (1086940) over Toolkit ID for correct prefix detection.

---

## Fallout 4 — F4SE Proton Shim

- **Automatic F4SE injection** — F4SE is automatically injected via the `X3DAudio1_7.dll` proxy shim.
- **No manual launching** of `f4se_loader.exe` required — just click Start.
- **Requires Steam launch option:** `WINEDLLOVERRIDES="X3DAudio1_7=n,b" %command%`

---

## Framework Reverse-Sync

- **No more version downgrades** — Frameworks (e.g. F4SE, TweakXL) are no longer reset to old versions when switching games.
- **Newer version detection** — Anvil detects when the installed version is newer and does not overwrite it.

---

## Bug Fixes

- **Framework context menu** — "Open in File Manager" now opens the folder where the mod actually lives (e.g. `red4ext/plugins/TweakXL/`), not the game root directory.
- **Framework DnD validation** — Drag & drop onto the framework list now validates correctly. Reinstall uses configured downloads path.
- **Broken data override manifests cleaned up** — Mods were shown as "installed" even though the files were missing.
- **Framework warning on game start removed** — Unnecessary `shim_steam_hint` dialog was removed.
- **Separator filter AttributeError fixed** — `_apply_separator_filter` no longer crashes on edge cases.

---

## Diagnostics (no code changes)

- `protontricks` for Proton prefix: `protontricks 1091500 d3dcompiler_47 vcrun2022`
- TweakXL update: Equipment-EX required TweakXL 1.11.3, installed was 1.11.0.
