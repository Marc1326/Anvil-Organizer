#!/usr/bin/env python3
"""Quick test: find all games managed by Heroic / Legendary."""

from anvil.stores.heroic_utils import (
    find_heroic_gog_games,
    find_heroic_epic_games,
    find_legendary_games,
    find_all_heroic_games,
)

print("=== GOG via Heroic ===")
gog = find_heroic_gog_games()
if not gog:
    print("  (keine)")
else:
    for gog_id, path in sorted(gog.items()):
        print(f"  {gog_id:>12}  {path}")

print("\n=== Epic via Heroic ===")
epic = find_heroic_epic_games()
if not epic:
    print("  (keine)")
else:
    for name, path in sorted(epic.items()):
        print(f"  {name:>30}  {path}")

print("\n=== Standalone Legendary ===")
leg = find_legendary_games()
if not leg:
    print("  (keine)")
else:
    for name, path in sorted(leg.items()):
        print(f"  {name:>30}  {path}")

print("\n=== Alles zusammen (find_all_heroic_games) ===")
all_gog, all_epic = find_all_heroic_games()
print(f"  GOG:  {len(all_gog)} Spiele")
print(f"  Epic: {len(all_epic)} Spiele")
