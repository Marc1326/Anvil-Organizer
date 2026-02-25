#!/usr/bin/env python3
"""Quick test: detect Skyrim Special Edition via StoreManager + game plugin."""

from pathlib import Path
from anvil.stores.store_manager import StoreManager
from anvil.plugins.games.game_skyrimse import SkyrimSEGame

# -- Scan all stores --------------------------------------------------------
sm = StoreManager()
sm.scan_all_stores()
print(f"Stores: {sm!r}\n")

# -- Convert int keys to str (detectGame expects str keys) ------------------
steam_str = {str(k): v for k, v in sm.steam_games.items()}
gog_str = {str(k): v for k, v in sm.gog_games.items()}
epic_str = sm.epic_games

# -- Create plugin and detect -----------------------------------------------
sse = SkyrimSEGame()
found = sse.detectGame(steam_str, gog_str, epic_str)

print(f"=== {sse.GameName} ===")
print(f"  Gefunden:      {found}")
print(f"  Pfad:          {sse.gameDirectory()}")
print(f"  Store:         {sse.detectedStore()}")
print(f"  Installiert:   {sse.isInstalled()}")

if found:
    path = sse.gameDirectory()
    print(f"  looksValid:    {sse.looksValid(path)}")
    print(f"  Proton-Prefix: {sse.protonPrefix()}")

    # Documents & Saves
    docs = sse.gameDocumentsDirectory()
    saves = sse.gameSavesDirectory()
    print(f"\n  Documents:     {docs}")
    print(f"    existiert:   {docs.is_dir() if docs else 'N/A'}")
    print(f"  Saves:         {saves}")
    print(f"    existiert:   {saves.is_dir() if saves else 'N/A'}")

    # Skyrim SE-spezifische Pfade
    ptxt = sse.plugins_txt_path()
    data = sse.data_path()
    print(f"\n  plugins.txt:   {ptxt}")
    print(f"    existiert:   {ptxt.is_file() if ptxt else 'N/A'}")
    print(f"  Data (Game):   {data}")
    print(f"    existiert:   {data.is_dir() if data else 'N/A'}")

    # SKSE64
    print(f"\n  SKSE64:        {sse.has_script_extender()}")

    # INI-Dateien
    print(f"  INI-Dateien:   {sse.iniFiles()}")
    if docs:
        for ini in sse.iniFiles():
            ini_path = docs / ini
            print(f"    {ini:<25} [{'OK' if ini_path.is_file() else 'FEHLT'}]")

    # Executables
    print(f"\n  Executables:")
    for exe in sse.executables():
        full = path / exe["binary"] if path else None
        exists = full.exists() if full else False
        print(f"    {exe['name']:<30} {exe['binary']:<30} [{'OK' if exists else 'FEHLT'}]")

    # Primary Plugins
    print(f"\n  Primary Plugins:")
    data_path = sse.data_path()
    for esm in sse.PRIMARY_PLUGINS:
        if data_path:
            esm_path = data_path / esm
            exists = esm_path.is_file()
        else:
            exists = False
        print(f"    {esm:<30} [{'OK' if exists else 'FEHLT'}]")

    # DLC Plugins
    print(f"\n  DLC Plugins:")
    for esm in sse.DLC_PLUGINS:
        if data_path:
            esm_path = data_path / esm
            exists = esm_path.is_file()
        else:
            exists = False
        print(f"    {esm:<30} [{'OK' if exists else 'FEHLT'}]")

    # Framework-Mods
    print(f"\n  Framework-Mods:")
    for fw, installed in sse.get_installed_frameworks():
        status = "INSTALLIERT" if installed else "NICHT INSTALLIERT"
        print(f"    {fw.name:<30} [{status}]")

else:
    print("\n  Skyrim SE wurde in keinem Store gefunden.")
    print("  Moeglich: Spiel nicht installiert, Platte nicht gemountet,")
    print("  oder kein appmanifest vorhanden.")

    # Manueller Check
    manual = Path.home() / ".local/share/Steam/steamapps/common/Skyrim Special Edition"
    if manual.is_dir():
        print(f"\n  HINWEIS: Verzeichnis existiert: {manual}")
        print(f"  Aber kein appmanifest_489830.acf -> Steam erkennt es nicht.")
        print(f"  looksValid: {sse.looksValid(manual)}")

print(f"\n{sse!r}")
