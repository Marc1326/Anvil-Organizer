#!/usr/bin/env python3
"""Quick test: find all installed Steam games and print them."""

from anvil.stores.steam_utils import find_steam_path, find_steam_games

steam = find_steam_path()
print(f"Steam path: {steam}\n")

games = find_steam_games()
if not games:
    print("No Steam games found.")
else:
    print(f"Found {len(games)} games:\n")
    for appid, path in sorted(games.items()):
        print(f"  {appid:>8}  {path}")
