#!/usr/bin/env python3
"""Test BG3 Mod Installer — read-only by default, --write for changes.

Usage:
    python test_bg3_installer.py          # Read-only: show mod list
    python test_bg3_installer.py --write  # Interactive: activate/deactivate/reorder
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────

PROTON_PREFIX = Path.home() / (
    ".local/share/Steam/steamapps/compatdata/2626479850/pfx"
)
MODS_PATH = PROTON_PREFIX / (
    "drive_c/users/steamuser/AppData/Local"
    "/Larian Studios/Baldur's Gate 3/Mods"
)
MODSETTINGS_PATH = PROTON_PREFIX / (
    "drive_c/users/steamuser/AppData/Local"
    "/Larian Studios/Baldur's Gate 3"
    "/PlayerProfiles/Public/modsettings.lsx"
)

# ── Minimal game plugin stub ──────────────────────────────────────────

class _FakeGamePlugin:
    """Minimal stub providing the paths BG3ModInstaller needs."""

    def pak_mods_path(self) -> Path | None:
        if MODS_PATH.is_dir():
            return MODS_PATH
        return None

    def modsettings_path(self) -> Path | None:
        return MODSETTINGS_PATH


# ── Helpers ───────────────────────────────────────────────────────────

def _size_str(size: int) -> str:
    if size >= 1_073_741_824:
        return f"{size / 1_073_741_824:.1f} GB"
    if size >= 1_048_576:
        return f"{size / 1_048_576:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def _print_mod(idx: int, mod: dict, prefix: str = "") -> None:
    name = mod.get("name", "???")
    uuid = mod.get("uuid", "???")
    folder = mod.get("folder", "")
    author = mod.get("author", "")
    version = mod.get("version", mod.get("version64", ""))
    filename = mod.get("filename", "")
    deps = mod.get("dependencies", [])

    print(f"  {prefix}{idx + 1}. {name}")
    print(f"     UUID:   {uuid}")
    if folder:
        print(f"     Folder: {folder}")
    if author:
        print(f"     Author: {author}")
    if version:
        print(f"     Version: {version}")
    if filename:
        print(f"     File:   {filename}")
    if deps:
        dep_names = [d.get("name", d.get("uuid", "?")) for d in deps]
        print(f"     Deps:   {', '.join(dep_names)}")
    print()


# ── Read-only test ────────────────────────────────────────────────────

def test_read_only(installer) -> None:
    """Display active and inactive mods (no changes)."""
    print("=" * 60)
    print("BG3 Mod Installer — Read-Only Test")
    print("=" * 60)

    # Check paths
    print(f"\nMods path:        {MODS_PATH}")
    print(f"  exists:         {MODS_PATH.is_dir()}")
    print(f"modsettings.lsx:  {MODSETTINGS_PATH}")
    print(f"  exists:         {MODSETTINGS_PATH.is_file()}")

    if not MODS_PATH.is_dir():
        print("\n[ERROR] Mods directory not found!")
        return

    # Count .pak files
    paks = list(MODS_PATH.glob("*.pak"))
    total_size = sum(p.stat().st_size for p in paks)
    print(f"\n.pak files found: {len(paks)} ({_size_str(total_size)} total)")

    # Get mod list
    print("\nLoading mod list...")
    mod_list = installer.get_mod_list()

    active = mod_list["active"]
    inactive = mod_list["inactive"]

    print(f"\n{'─' * 60}")
    print(f"ACTIVE MODS ({len(active)})  — in ModOrder (load order)")
    print(f"{'─' * 60}")
    if active:
        for i, mod in enumerate(active):
            _print_mod(i, mod, prefix="[ACTIVE] ")
    else:
        print("  (none)")

    print(f"\n{'─' * 60}")
    print(f"INACTIVE MODS ({len(inactive)})  — .pak present, not in ModOrder")
    print(f"{'─' * 60}")
    if inactive:
        for i, mod in enumerate(inactive):
            _print_mod(i, mod, prefix="[INACTIVE] ")
    else:
        print("  (none)")

    # Deploy validation
    print(f"\n{'─' * 60}")
    print("DEPLOY VALIDATION")
    print(f"{'─' * 60}")
    ok = installer.deploy()
    print(f"  Result: {'OK' if ok else 'FAILED'}")
    print()


# ── Interactive write test ────────────────────────────────────────────

def test_write(installer) -> None:
    """Interactive mode: activate, deactivate, reorder mods."""
    print("=" * 60)
    print("BG3 Mod Installer — WRITE MODE (changes modsettings.lsx!)")
    print("=" * 60)
    print("\nA backup will be created before every change.\n")

    while True:
        mod_list = installer.get_mod_list()
        active = mod_list["active"]
        inactive = mod_list["inactive"]

        print(f"\nActive ({len(active)}):")
        for i, m in enumerate(active):
            print(f"  {i + 1}. {m.get('name', '???')}  [{m.get('uuid', '?')[:8]}...]")

        print(f"\nInactive ({len(inactive)}):")
        for i, m in enumerate(inactive):
            print(f"  {i + 1}. {m.get('name', '???')}  [{m.get('uuid', '?')[:8]}...]")

        print("\nOptions:")
        print("  a <nr>  — activate inactive mod #nr")
        print("  d <nr>  — deactivate active mod #nr")
        print("  r       — reorder active mods")
        print("  q       — quit")

        try:
            choice = input("\n> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice == "q":
            break

        if choice.startswith("a "):
            try:
                nr = int(choice.split()[1]) - 1
                mod = inactive[nr]
            except (IndexError, ValueError):
                print("Invalid number.")
                continue

            uuid = mod.get("uuid", "")
            if not uuid:
                print("This mod has no UUID — cannot activate.")
                continue

            confirm = input(f"Activate '{mod.get('name')}'? (j/n) ").strip().lower()
            if confirm == "j":
                ok = installer.activate_mod(uuid)
                print(f"  -> {'OK' if ok else 'FAILED'}")

        elif choice.startswith("d "):
            try:
                nr = int(choice.split()[1]) - 1
                mod = active[nr]
            except (IndexError, ValueError):
                print("Invalid number.")
                continue

            uuid = mod.get("uuid", "")
            confirm = input(f"Deactivate '{mod.get('name')}'? (j/n) ").strip().lower()
            if confirm == "j":
                ok = installer.deactivate_mod(uuid)
                print(f"  -> {'OK' if ok else 'FAILED'}")

        elif choice == "r":
            print("\nCurrent load order:")
            for i, m in enumerate(active):
                print(f"  {i + 1}. {m.get('name', '???')}")

            print("\nEnter new order as comma-separated numbers (e.g. 3,1,2):")
            try:
                order_input = input("> ").strip()
                indices = [int(x.strip()) - 1 for x in order_input.split(",")]
                new_order = [active[i]["uuid"] for i in indices]
            except (IndexError, ValueError):
                print("Invalid input.")
                continue

            confirm = input("Apply new order? (j/n) ").strip().lower()
            if confirm == "j":
                ok = installer.reorder_mods(new_order)
                print(f"  -> {'OK' if ok else 'FAILED'}")

        else:
            print("Unknown command.")

    print("\nDone.")


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="BG3 Mod Installer Test")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Enable interactive write mode (changes modsettings.lsx)",
    )
    args = parser.parse_args()

    # Check Proton prefix
    if not PROTON_PREFIX.is_dir():
        print(f"[ERROR] Proton prefix not found: {PROTON_PREFIX}")
        print("Is BG3 installed via Steam with this Proton prefix?")
        sys.exit(1)

    # Import and create installer
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from anvil.core.bg3_mod_installer import BG3ModInstaller

    plugin = _FakeGamePlugin()
    installer = BG3ModInstaller(plugin)

    if args.write:
        test_write(installer)
    else:
        test_read_only(installer)


if __name__ == "__main__":
    main()
