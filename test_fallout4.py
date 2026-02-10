#!/usr/bin/env python3
"""Quick test: detect Fallout 4 via StoreManager + game plugin."""

from pathlib import Path
from anvil.stores.store_manager import StoreManager
from anvil.plugins.games.game_fallout4 import Fallout4Game

# -- Scan all stores --------------------------------------------------------
sm = StoreManager()
sm.scan_all_stores()
print(f"Stores: {sm!r}\n")

# -- Convert int keys to str (detectGame expects str keys) ------------------
steam_str = {str(k): v for k, v in sm.steam_games.items()}
gog_str = {str(k): v for k, v in sm.gog_games.items()}
epic_str = sm.epic_games

# -- Create plugin and detect -----------------------------------------------
fo4 = Fallout4Game()
found = fo4.detectGame(steam_str, gog_str, epic_str)

print(f"=== {fo4.GameName} ===")
print(f"  Gefunden:      {found}")
print(f"  Pfad:          {fo4.gameDirectory()}")
print(f"  Store:         {fo4.detectedStore()}")
print(f"  Installiert:   {fo4.isInstalled()}")

if found:
    path = fo4.gameDirectory()
    print(f"  looksValid:    {fo4.looksValid(path)}")
    print(f"  Proton-Prefix: {fo4.protonPrefix()}")

    # Documents & Saves
    docs = fo4.gameDocumentsDirectory()
    saves = fo4.gameSavesDirectory()
    print(f"\n  Documents:     {docs}")
    print(f"    existiert:   {docs.is_dir() if docs else 'N/A'}")
    print(f"  Saves:         {saves}")
    print(f"    existiert:   {saves.is_dir() if saves else 'N/A'}")

    # Fallout 4-spezifische Pfade
    ptxt = fo4.plugins_txt_path()
    data = fo4.data_path()
    print(f"\n  plugins.txt:   {ptxt}")
    print(f"    existiert:   {ptxt.is_file() if ptxt else 'N/A'}")
    print(f"  Data (Game):   {data}")
    print(f"    existiert:   {data.is_dir() if data else 'N/A'}")

    # F4SE
    print(f"\n  F4SE:          {fo4.has_script_extender()}")

    # INI-Dateien
    print(f"  INI-Dateien:   {fo4.iniFiles()}")
    if docs:
        for ini in fo4.iniFiles():
            ini_path = docs / ini
            print(f"    {ini:<30} [{'OK' if ini_path.is_file() else 'FEHLT'}]")

    # Executables
    print(f"\n  Executables:")
    for exe in fo4.executables():
        full = path / exe["binary"] if path else None
        exists = full.exists() if full else False
        print(f"    {exe['name']:<25} {exe['binary']:<30} [{'OK' if exists else 'FEHLT'}]")

    # Primary Plugins
    print(f"\n  Primary Plugins:")
    data_path = fo4.data_path()
    for esm in fo4.PRIMARY_PLUGINS:
        if data_path:
            esm_path = data_path / esm
            exists = esm_path.is_file()
        else:
            exists = False
        print(f"    {esm:<40} [{'OK' if exists else 'FEHLT'}]")

    # DLC Plugins
    print(f"\n  DLC Plugins:")
    for esm in fo4.DLC_PLUGINS:
        if data_path:
            esm_path = data_path / esm
            exists = esm_path.is_file()
        else:
            exists = False
        print(f"    {esm:<40} [{'OK' if exists else 'FEHLT'}]")

else:
    print("\n  Fallout 4 wurde in keinem Store gefunden.")
    print("  Moeglich: Spiel nicht installiert, Platte nicht gemountet,")
    print("  oder kein appmanifest vorhanden.")

    # Manueller Check
    manual = Path.home() / ".local/share/Steam/steamapps/common/Fallout 4"
    if manual.is_dir():
        print(f"\n  HINWEIS: Verzeichnis existiert: {manual}")
        print(f"  Aber kein appmanifest_377160.acf -> Steam erkennt es nicht.")
        print(f"  looksValid: {fo4.looksValid(manual)}")

print(f"\n{fo4!r}")
