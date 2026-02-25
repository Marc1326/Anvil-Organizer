#!/usr/bin/env python3
"""Quick test: detect Baldur's Gate 3 via StoreManager + game plugin."""

from pathlib import Path
from anvil.stores.store_manager import StoreManager
from anvil.plugins.games.game_baldursgate3 import BaldursGate3Game

# ── Scan all stores ────────────────────────────────────────────────────
sm = StoreManager()
sm.scan_all_stores()
print(f"Stores: {sm!r}\n")

# ── Convert int keys to str (detectGame expects str keys) ─────────────
steam_str = {str(k): v for k, v in sm.steam_games.items()}
gog_str = {str(k): v for k, v in sm.gog_games.items()}
epic_str = sm.epic_games

# ── Create plugin and detect ──────────────────────────────────────────
bg3 = BaldursGate3Game()
found = bg3.detectGame(steam_str, gog_str, epic_str)

print(f"=== {bg3.GameName} ===")
print(f"  Gefunden:      {found}")
print(f"  Pfad:          {bg3.gameDirectory()}")
print(f"  Store:         {bg3.detectedStore()}")
print(f"  Installiert:   {bg3.isInstalled()}")

if found:
    path = bg3.gameDirectory()
    print(f"  looksValid:    {bg3.looksValid(path)}")
    print(f"  Proton-Prefix: {bg3.protonPrefix()}")

    # Documents & Saves
    docs = bg3.gameDocumentsDirectory()
    saves = bg3.gameSavesDirectory()
    print(f"\n  Documents:     {docs}")
    print(f"    existiert:   {docs.is_dir() if docs else 'N/A'}")
    print(f"  Saves:         {saves}")
    print(f"    existiert:   {saves.is_dir() if saves else 'N/A'}")

    # BG3-spezifische Pfade
    ms = bg3.modsettings_path()
    pak = bg3.pak_mods_path()
    data = bg3.data_mods_path()
    print(f"\n  modsettings:   {ms}")
    print(f"    existiert:   {ms.is_file() if ms else 'N/A'}")
    print(f"  pak_mods:      {pak}")
    print(f"    existiert:   {pak.is_dir() if pak else 'N/A'}")
    print(f"  data_mods:     {data}")
    print(f"    existiert:   {data.is_dir() if data else 'N/A'}")

    # Executables
    print(f"\n  Executables:")
    for exe in bg3.executables():
        full = path / exe["binary"] if path else None
        exists = full.exists() if full else False
        print(f"    {exe['name']:<30} {exe['binary']:<35} [{'OK' if exists else 'FEHLT'}]")
else:
    print("\n  BG3 wurde in keinem Store gefunden.")
    print("  Mögliche Ursache: Spiel nicht installiert, Platte nicht gemountet,")
    print("  oder kein appmanifest vorhanden.")

    # Manueller Check: existiert das Verzeichnis trotzdem?
    manual = Path.home() / ".local/share/Steam/steamapps/common/Baldurs Gate 3"
    if manual.is_dir():
        print(f"\n  HINWEIS: Verzeichnis existiert: {manual}")
        print(f"  Aber kein appmanifest_1086940.acf → Steam erkennt es nicht.")
        print(f"  looksValid: {bg3.looksValid(manual)}")

print(f"\n{bg3!r}")
