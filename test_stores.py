#!/usr/bin/env python3
"""Quick test: scan ALL stores via StoreManager and print results."""

from anvil.stores.store_manager import StoreManager

sm = StoreManager()
print("Scanning all stores...\n")
sm.scan_all_stores()

# ── Steam ──────────────────────────────────────────────────────────────
print(f"=== Steam ({len(sm.steam_games)} Spiele) ===")
if sm.steam_games:
    for appid, path in sorted(sm.steam_games.items()):
        print(f"  {appid:>8}  {path}")
else:
    print("  (keine)")

# ── GOG ────────────────────────────────────────────────────────────────
print(f"\n=== GOG ({len(sm.gog_games)} Spiele) ===")
if sm.gog_games:
    for gog_id, path in sorted(sm.gog_games.items()):
        print(f"  {gog_id:>12}  {path}")
else:
    print("  (keine)")

# ── Epic ───────────────────────────────────────────────────────────────
print(f"\n=== Epic ({len(sm.epic_games)} Spiele) ===")
if sm.epic_games:
    for name, path in sorted(sm.epic_games.items()):
        print(f"  {name:>30}  {path}")
else:
    print("  (keine)")

# ── Bottles ────────────────────────────────────────────────────────────
print(f"\n=== Bottles ({len(sm.bottles)} Flaschen) ===")
if sm.bottles:
    for b in sm.bottles:
        print(f"  {b['name']:<25} {b['environment']:<12} {b['runner']:<20} {b['path']}")
else:
    print("  (keine)")

# ── Summary ────────────────────────────────────────────────────────────
counts = sm.all_found_games()["counts"]
total = counts["steam"] + counts["gog"] + counts["epic"]
print(f"\n=== Zusammenfassung ===")
print(f"  Steam:   {counts['steam']:>3} Spiele")
print(f"  GOG:     {counts['gog']:>3} Spiele")
print(f"  Epic:    {counts['epic']:>3} Spiele")
print(f"  Bottles: {counts['bottles']:>3} Flaschen")
print(f"  ─────────────────")
print(f"  Gesamt:  {total:>3} Spiele + {counts['bottles']} Flaschen")
print(f"\n{sm!r}")
