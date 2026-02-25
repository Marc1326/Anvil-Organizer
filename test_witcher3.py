#!/usr/bin/env python3
"""Quick test: detect The Witcher 3 via StoreManager + game plugin."""

from pathlib import Path
from anvil.stores.store_manager import StoreManager
from anvil.plugins.games.game_witcher3 import Witcher3Game

# -- Scan all stores --------------------------------------------------------
sm = StoreManager()
sm.scan_all_stores()
print(f"Stores: {sm!r}\n")

# -- Convert int keys to str (detectGame expects str keys) ------------------
steam_str = {str(k): v for k, v in sm.steam_games.items()}
gog_str = {str(k): v for k, v in sm.gog_games.items()}
epic_str = sm.epic_games

# -- Create plugin and detect -----------------------------------------------
w3 = Witcher3Game()
found = w3.detectGame(steam_str, gog_str, epic_str)

print(f"=== {w3.GameName} ===")
print(f"  Gefunden:      {found}")
print(f"  Pfad:          {w3.gameDirectory()}")
print(f"  Store:         {w3.detectedStore()}")
print(f"  Installiert:   {w3.isInstalled()}")

if found:
    path = w3.gameDirectory()
    print(f"  looksValid:    {w3.looksValid(path)}")
    print(f"  Proton-Prefix: {w3.protonPrefix()}")

    # Documents & Saves
    docs = w3.gameDocumentsDirectory()
    saves = w3.gameSavesDirectory()
    print(f"\n  Documents:     {docs}")
    print(f"    existiert:   {docs.is_dir() if docs else 'N/A'}")
    print(f"  Saves:         {saves}")
    print(f"    existiert:   {saves.is_dir() if saves else 'N/A'}")

    # Witcher 3-spezifische Pfade
    mods = w3.mods_path()
    dlc = w3.dlc_path()
    menu = w3.menu_config_path()
    print(f"\n  Mods-Ordner:   {mods}")
    print(f"    existiert:   {mods.is_dir() if mods else 'N/A'}")
    print(f"  DLC-Ordner:    {dlc}")
    print(f"    existiert:   {dlc.is_dir() if dlc else 'N/A'}")
    print(f"  Menu-Config:   {menu}")
    print(f"    existiert:   {menu.is_dir() if menu else 'N/A'}")

    # Script Merger
    print(f"\n  Script Merger: {w3.has_script_merger()}")

    # INI/Settings-Dateien
    print(f"  Settings:      {w3.iniFiles()}")
    if docs:
        for ini in w3.iniFiles():
            ini_path = docs / ini
            print(f"    {ini:<25} [{'OK' if ini_path.is_file() else 'FEHLT'}]")

    # Executables
    print(f"\n  Executables:")
    for exe in w3.executables():
        full = path / exe["binary"] if path else None
        exists = full.exists() if full else False
        print(f"    {exe['name']:<30} {exe['binary']:<35} [{'OK' if exists else 'FEHLT'}]")

    # Framework-Mods
    frameworks = w3.get_framework_mods()
    if frameworks:
        print(f"\n  Framework-Mods ({len(frameworks)}):")
        for fw, installed in w3.get_installed_frameworks():
            status = "INSTALLIERT" if installed else "NICHT INSTALLIERT"
            print(f"    {fw.name:<30} [{status}]")
    else:
        print(f"\n  Framework-Mods: keine (Witcher 3 nutzt Script Merger statt SE)")

    # Mods-Ordner Inhalt (falls vorhanden)
    if mods and mods.is_dir():
        mod_dirs = [d for d in mods.iterdir() if d.is_dir()]
        print(f"\n  Installierte Mods ({len(mod_dirs)}):")
        for d in sorted(mod_dirs)[:15]:
            has_content = (d / "content").is_dir()
            print(f"    {d.name:<40} [{'content/' if has_content else 'KEINE content/'}]")
        if len(mod_dirs) > 15:
            print(f"    ... und {len(mod_dirs) - 15} weitere")

else:
    print("\n  The Witcher 3 wurde in keinem Store gefunden.")
    print("  Moeglich: Spiel nicht installiert, Platte nicht gemountet,")
    print("  oder kein appmanifest vorhanden.")

    # Manueller Check
    for steam_id in [292030, 499450]:
        manual = Path.home() / f".local/share/Steam/steamapps/common/The Witcher 3"
        if manual.is_dir():
            print(f"\n  HINWEIS: Verzeichnis existiert: {manual}")
            print(f"  Aber kein appmanifest_{steam_id}.acf -> Steam erkennt es nicht.")
            print(f"  looksValid: {w3.looksValid(manual)}")
            break

print(f"\n{w3!r}")
