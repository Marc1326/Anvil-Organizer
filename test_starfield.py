#!/usr/bin/env python3
"""Quick test: detect Starfield via StoreManager + game plugin."""

from pathlib import Path
from anvil.stores.store_manager import StoreManager
from anvil.plugins.games.game_starfield import StarfieldGame

# -- Scan all stores --------------------------------------------------------
sm = StoreManager()
sm.scan_all_stores()
print(f"Stores: {sm!r}\n")

# -- Convert int keys to str (detectGame expects str keys) ------------------
steam_str = {str(k): v for k, v in sm.steam_games.items()}
gog_str = {str(k): v for k, v in sm.gog_games.items()}
epic_str = sm.epic_games

# -- Create plugin and detect -----------------------------------------------
sf = StarfieldGame()
found = sf.detectGame(steam_str, gog_str, epic_str)

print(f"=== {sf.GameName} ===")
print(f"  Gefunden:      {found}")
print(f"  Pfad:          {sf.gameDirectory()}")
print(f"  Store:         {sf.detectedStore()}")
print(f"  Installiert:   {sf.isInstalled()}")

if found:
    path = sf.gameDirectory()
    print(f"  looksValid:    {sf.looksValid(path)}")
    print(f"  Proton-Prefix: {sf.protonPrefix()}")

    # Documents & Saves
    docs = sf.gameDocumentsDirectory()
    saves = sf.gameSavesDirectory()
    print(f"\n  Documents:     {docs}")
    print(f"    existiert:   {docs.is_dir() if docs else 'N/A'}")
    print(f"  Saves:         {saves}")
    print(f"    existiert:   {saves.is_dir() if saves else 'N/A'}")

    # Starfield-spezifische Pfade
    ptxt = sf.plugins_txt_path()
    data = sf.data_path()
    gdata = sf.game_data_path()
    print(f"\n  plugins.txt:   {ptxt}")
    print(f"    existiert:   {ptxt.is_file() if ptxt else 'N/A'}")
    print(f"  Data (Docs):   {data}")
    print(f"    existiert:   {data.is_dir() if data else 'N/A'}")
    print(f"  Data (Game):   {gdata}")
    print(f"    existiert:   {gdata.is_dir() if gdata else 'N/A'}")

    # SFSE
    print(f"\n  SFSE:          {sf.has_script_extender()}")

    # INI-Dateien
    print(f"  INI-Dateien:   {sf.iniFiles()}")
    if docs:
        for ini in sf.iniFiles():
            ini_path = docs / ini
            print(f"    {ini:<30} [{'OK' if ini_path.is_file() else 'FEHLT'}]")

    # Executables
    print(f"\n  Executables:")
    for exe in sf.executables():
        full = path / exe["binary"] if path else None
        exists = full.exists() if full else False
        print(f"    {exe['name']:<20} {exe['binary']:<30} [{'OK' if exists else 'FEHLT'}]")

    # Primary Plugins
    print(f"\n  Primary Plugins:")
    gdata_path = sf.game_data_path()
    for esm in sf.PRIMARY_PLUGINS:
        if gdata_path:
            esm_path = gdata_path / esm
            exists = esm_path.is_file()
        else:
            exists = False
        print(f"    {esm:<40} [{'OK' if exists else 'FEHLT'}]")

else:
    print("\n  Starfield wurde in keinem Store gefunden.")
    print("  Moeglich: Spiel nicht installiert, Platte nicht gemountet,")
    print("  oder kein appmanifest vorhanden.")

    # Manueller Check
    manual = Path.home() / ".local/share/Steam/steamapps/common/Starfield"
    if manual.is_dir():
        print(f"\n  HINWEIS: Verzeichnis existiert: {manual}")
        print(f"  Aber kein appmanifest_1716740.acf -> Steam erkennt es nicht.")
        print(f"  looksValid: {sf.looksValid(manual)}")

print(f"\n{sf!r}")
