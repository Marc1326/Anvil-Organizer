#!/usr/bin/env python3
"""Quick test: load all game plugins and detect installed games."""

from anvil.plugins.plugin_loader import PluginLoader

loader = PluginLoader()
print("Loading plugins + scanning stores...\n")
loader.load_plugins()

# ── All plugins ────────────────────────────────────────────────────────
print(f"=== Alle Plugins ({loader.plugin_count()}) ===")
for p in loader.all_plugins():
    status = "INSTALLIERT" if p.isInstalled() else "nicht gefunden"
    print(f"  {p.GameName:<25} v{p.Version:<8} von {p.Author:<25} [{status}]")

# ── Installed games ────────────────────────────────────────────────────
print(f"\n=== Erkannte Spiele ({loader.installed_count()}) ===")
for g in loader.installed_games():
    print(f"  {g.GameName}")
    print(f"    Pfad:          {g.gameDirectory()}")
    print(f"    Store:         {g.detectedStore()}")
    print(f"    Proton-Prefix: {g.protonPrefix()}")
    print(f"    looksValid:    {g.looksValid(g.gameDirectory())}")
    print()

# ── Lookup by short name ──────────────────────────────────────────────
cp = loader.get_game("cyberpunk2077")
if cp:
    print(f"=== Lookup: get_game('cyberpunk2077') ===")
    print(f"  {cp!r}")

# ── Summary ────────────────────────────────────────────────────────────
print(f"\n{loader!r}")
