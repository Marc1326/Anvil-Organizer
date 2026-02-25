#!/usr/bin/env python3
"""Test: Framework-Mod-Erkennung fuer alle Game-Plugins."""

from anvil.stores.store_manager import StoreManager
from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game
from anvil.plugins.games.game_baldursgate3 import BaldursGate3Game
from anvil.plugins.games.game_fallout4 import Fallout4Game
from anvil.plugins.games.game_starfield import StarfieldGame

# -- Scan all stores --------------------------------------------------------
sm = StoreManager()
sm.scan_all_stores()

steam_str = {str(k): v for k, v in sm.steam_games.items()}
gog_str = {str(k): v for k, v in sm.gog_games.items()}
epic_str = sm.epic_games

# -- Alle Spiele ------------------------------------------------------------
games = [Cyberpunk2077Game(), BaldursGate3Game(), Fallout4Game(), StarfieldGame()]

for game in games:
    game.detectGame(steam_str, gog_str, epic_str)

    print(f"\n{'=' * 60}")
    print(f"  {game.GameName}")
    print(f"  Installiert: {game.isInstalled()}  |  Store: {game.detectedStore() or '-'}")
    print(f"{'=' * 60}")

    frameworks = game.get_framework_mods()
    if not frameworks:
        print("  Keine Framework-Mods definiert.")
        continue

    print(f"\n  Framework-Mods ({len(frameworks)}):")
    for fw in frameworks:
        print(f"    {fw.name}")
        print(f"      Beschreibung:  {fw.description}")
        print(f"      Pattern:       {fw.pattern}")
        print(f"      Ziel:          {fw.target or '(Game Root)'}")
        print(f"      Erkennung:     {fw.detect_installed}")
        if fw.required_by:
            print(f"      Benoetigt von: {fw.required_by}")

    # Installed check (nur wenn Spiel installiert)
    if game.isInstalled():
        print(f"\n  Installations-Status:")
        for fw, installed in game.get_installed_frameworks():
            status = "INSTALLIERT" if installed else "NICHT INSTALLIERT"
            print(f"    {fw.name:<30} [{status}]")

# -- is_framework_mod() Test mit Beispiel-Archiven --------------------------
print(f"\n{'=' * 60}")
print("  is_framework_mod() — Archiv-Erkennung")
print(f"{'=' * 60}")

cp = Cyberpunk2077Game()

# Simuliere CET-Archiv
cet_archive = [
    "bin/x64/version.dll",
    "bin/x64/global.ini",
    "bin/x64/LICENSE",
    "bin/x64/plugins/cyber_engine_tweaks.asi",
    "bin/x64/plugins/cyber_engine_tweaks/scripts/autoexec.lua",
]
result = cp.is_framework_mod(cet_archive)
print(f"\n  CET-Archiv:        {result.name if result else 'None'}")

# Simuliere RED4ext-Archiv
red4ext_archive = [
    "bin/x64/winmm.dll",
    "red4ext/RED4ext.dll",
    "red4ext/LICENSE",
]
result = cp.is_framework_mod(red4ext_archive)
print(f"  RED4ext-Archiv:    {result.name if result else 'None'}")

# Simuliere redscript-Archiv
redscript_archive = [
    "engine/tools/scc.exe",
    "engine/config/base/scripts.ini",
]
result = cp.is_framework_mod(redscript_archive)
print(f"  redscript-Archiv:  {result.name if result else 'None'}")

# Simuliere ArchiveXL-Archiv
archivexl_archive = [
    "red4ext/plugins/ArchiveXL/ArchiveXL.dll",
]
result = cp.is_framework_mod(archivexl_archive)
print(f"  ArchiveXL-Archiv:  {result.name if result else 'None'}")

# Simuliere normales Mod-Archiv (kein Framework)
normal_archive = [
    "archive/pc/mod/my_cool_mod.archive",
    "archive/pc/mod/my_cool_mod.xl",
]
result = cp.is_framework_mod(normal_archive)
print(f"  Normales Archiv:   {result.name if result else 'None (korrekt)'}")

# BG3 Script Extender
bg3 = BaldursGate3Game()
bg3se_archive = ["DWrite.dll", "README.md"]
result = bg3.is_framework_mod(bg3se_archive)
print(f"\n  BG3SE-Archiv:      {result.name if result else 'None'}")

# F4SE
fo4 = Fallout4Game()
f4se_archive = ["f4se_loader.exe", "f4se_1_10_163.dll", "f4se_steam_loader.dll"]
result = fo4.is_framework_mod(f4se_archive)
print(f"  F4SE-Archiv:       {result.name if result else 'None'}")

# SFSE
sf = StarfieldGame()
sfse_archive = ["sfse_loader.exe", "sfse_1_0_0.dll"]
result = sf.is_framework_mod(sfse_archive)
print(f"  SFSE-Archiv:       {result.name if result else 'None'}")

# Skyrim: SKSE kommt mit Skyrim-Plugin

print("\n  Alle Tests abgeschlossen.")
