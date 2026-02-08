#!/usr/bin/env python3
"""Quick test: detect Cyberpunk 2077 via StoreManager + game plugin."""

from anvil.stores.store_manager import StoreManager
from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game

# ── Scan all stores ────────────────────────────────────────────────────
sm = StoreManager()
sm.scan_all_stores()

print(f"Stores: {sm!r}\n")

# ── Convert int keys to str (detectGame expects str keys) ─────────────
steam_str = {str(k): v for k, v in sm.steam_games.items()}
gog_str = {str(k): v for k, v in sm.gog_games.items()}
epic_str = sm.epic_games  # already str keys

# ── Create plugin and detect ──────────────────────────────────────────
cp = Cyberpunk2077Game()
found = cp.detectGame(steam_str, gog_str, epic_str)

print(f"=== {cp.GameName} ===")
print(f"  Gefunden:    {found}")
print(f"  Pfad:        {cp.gameDirectory()}")
print(f"  Store:       {cp.detectedStore()}")
print(f"  Installiert: {cp.isInstalled()}")

if found:
    print(f"  Proton-Prefix: {cp.protonPrefix()}")
    print(f"  Documents:     {cp.gameDocumentsDirectory()}")
    print(f"  Saves:         {cp.gameSavesDirectory()}")
    print(f"  INI-Dateien:   {cp.iniFiles()}")

    path = cp.gameDirectory()
    print(f"  looksValid:    {cp.looksValid(path)}")

    print(f"\n  Executables:")
    for exe in cp.executables():
        print(f"    {exe['name']:<20} {exe['binary']}")

print(f"\n{cp!r}")
