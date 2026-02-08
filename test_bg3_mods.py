#!/usr/bin/env python3
"""Quick test: BG3 mod handler — modsettings.lsx, SE, pak scanner."""

from pathlib import Path
from anvil.plugins.plugin_loader import PluginLoader
from anvil.plugins.games.bg3_mod_handler import is_base_game_mod

# ── Find BG3 ───────────────────────────────────────────────────────────
loader = PluginLoader()
loader.load_plugins()

bg3 = loader.get_game("baldursgate3")
if bg3 is None:
    print("ERROR: BG3 plugin not loaded!")
    raise SystemExit(1)

print(f"=== {bg3.GameName} ===")
print(f"  Installiert:   {bg3.isInstalled()}")
print(f"  Pfad:          {bg3.gameDirectory()}")
print(f"  Store:         {bg3.detectedStore()}")
print(f"  Proton-Prefix: {bg3.protonPrefix()}")

# ── Check if BG3 is available ──────────────────────────────────────────
if not bg3.isInstalled():
    # Try manual path (second drive)
    candidates = [
        Path("/mnt/Gaming2/SteamLibrary/steamapps/common/Baldurs Gate 3"),
        Path("/mnt/Gaming2/SteamLibrary/steamapps/common/Baldur's Gate 3"),
        Path.home() / ".local/share/Steam/steamapps/common/Baldurs Gate 3",
    ]
    manual = None
    for c in candidates:
        if c.is_dir():
            manual = c
            break

    if manual:
        print(f"\n  HINWEIS: Verzeichnis gefunden: {manual}")
        print(f"  Aber kein Store-Eintrag → setze manuell...")
        bg3.setGamePath(manual, store="steam")
    else:
        print("\n  BG3 nicht verfügbar. Teste mit Dummy-Daten...\n")

# ── modsettings.lsx ───────────────────────────────────────────────────
ms_path = bg3.modsettings_path()
print(f"\n=== modsettings.lsx ===")
print(f"  Pfad:      {ms_path}")
print(f"  existiert: {ms_path.is_file() if ms_path else 'N/A'}")

if ms_path and ms_path.is_file():
    mod_list = bg3.read_mod_list()
    version = mod_list["version"]
    print(f"  Version:   {version.get('major')}.{version.get('minor')}"
          f".{version.get('revision')}.{version.get('build')}")

    print(f"\n  ModOrder ({len(mod_list['mod_order'])} Einträge):")
    for i, uuid in enumerate(mod_list["mod_order"]):
        gustav = " ← BASE GAME" if is_base_game_mod(uuid) else ""
        print(f"    {i:>3}. {uuid}{gustav}")

    print(f"\n  Mods ({len(mod_list['mods'])} Einträge):")
    for mod in mod_list["mods"]:
        gustav = " [BASE]" if is_base_game_mod(mod["uuid"]) else ""
        print(f"    {mod['name']:<35} {mod['folder']:<25} {mod['uuid'][:20]}...{gustav}")
else:
    print("  → Datei nicht vorhanden, überspringe.")
    mod_list = bg3.read_mod_list()
    print(f"  Default-Ergebnis: {mod_list}")

# ── pak-Mods ──────────────────────────────────────────────────────────
pak_path = bg3.pak_mods_path()
print(f"\n=== pak-Mods ===")
print(f"  Pfad:      {pak_path}")
print(f"  existiert: {pak_path.is_dir() if pak_path else 'N/A'}")

pak_mods = bg3.scan_mods()
if pak_mods:
    print(f"  Gefunden:  {len(pak_mods)} .pak Dateien")
    for pak in pak_mods:
        size_mb = pak["size"] / (1024 * 1024)
        print(f"    {pak['filename']:<45} {size_mb:>8.1f} MB")
else:
    print("  Keine .pak Dateien gefunden.")

# ── Nicht-registrierte Mods ───────────────────────────────────────────
new_mods = bg3.find_new_mods()
print(f"\n=== Nicht-registrierte Mods ===")
if new_mods:
    print(f"  {len(new_mods)} Mods nicht in modsettings.lsx:")
    for mod in new_mods:
        print(f"    {mod['filename']}")
else:
    print("  Alle Mods sind registriert (oder keine vorhanden).")

# ── Script Extender ───────────────────────────────────────────────────
print(f"\n=== Script Extender ===")
print(f"  Installiert: {bg3.has_script_extender()}")
if bg3.gameDirectory():
    from anvil.plugins.games.bg3_mod_handler import BG3ScriptExtender
    se_settings = BG3ScriptExtender.settings(bg3.gameDirectory())
    if se_settings:
        print(f"  Settings:    {se_settings}")
    print(f"  Launch-Opts: {BG3ScriptExtender.steam_launch_options()}")

# ── Data-Mods ─────────────────────────────────────────────────────────
data_path = bg3.data_mods_path()
print(f"\n=== Data-Mods ===")
print(f"  Pfad:      {data_path}")
print(f"  existiert: {data_path.is_dir() if data_path else 'N/A'}")

print(f"\n{bg3!r}")
