#!/usr/bin/env python3
"""Einmaliges Reparatur-Script für kaputte Mod-Ordnerstrukturen.

Prüft alle Mods in .mods/ einer Anvil-Instanz und repariert:
1. pc/mod/ ohne archive/ → archive/pc/mod/ einfügen
2. .archive-Dateien direkt im Root → nach archive/pc/mod/ verschieben
3. .zip im Ordnernamen → Extension entfernen + modlist/active_mods aktualisieren

Standardmäßig Dry-Run (nur Anzeige). Mit --apply werden Änderungen durchgeführt.
Backup wird VOR jeder Änderung erstellt.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

DEFAULT_INSTANCE = Path(
    "/home/mob/.anvil-organizer/instances/Cyberpunk 2077"
)


def backup_mod(mod_dir: Path, backup_path: Path) -> bool:
    """Erstelle Backup eines Mod-Ordners."""
    backup_dir = backup_path / mod_dir.name
    if backup_dir.exists():
        print(f"  SKIP backup (existiert bereits): {backup_dir}")
        return True
    try:
        shutil.copytree(mod_dir, backup_dir)
        return True
    except OSError as exc:
        print(f"  FEHLER backup: {exc}", file=sys.stderr)
        return False


def fix_pc_without_archive(mod_dir: Path, backup_path: Path, apply: bool) -> bool:
    """Fix: pc/mod/ → archive/pc/mod/"""
    pc_dir = mod_dir / "pc"
    if not pc_dir.is_dir():
        return False
    if (mod_dir / "archive").is_dir():
        return False

    print(f"  FIX: pc/ → archive/pc/ in {mod_dir.name}")
    if not apply:
        return True

    if not backup_mod(mod_dir, backup_path):
        return False

    archive_dir = mod_dir / "archive"
    archive_dir.mkdir(exist_ok=True)
    shutil.move(str(pc_dir), str(archive_dir / "pc"))
    return True


def fix_archive_in_root(mod_dir: Path, backup_path: Path, apply: bool) -> bool:
    """Fix: .archive direkt im Root → archive/pc/mod/"""
    archive_files = [
        f for f in mod_dir.iterdir()
        if f.is_file() and f.suffix == ".archive"
    ]
    if not archive_files:
        return False

    if (mod_dir / "archive" / "pc" / "mod").is_dir():
        return False

    print(f"  FIX: {len(archive_files)} .archive-Dateien → archive/pc/mod/ in {mod_dir.name}")
    if not apply:
        return True

    if not backup_mod(mod_dir, backup_path):
        return False

    target = mod_dir / "archive" / "pc" / "mod"
    target.mkdir(parents=True, exist_ok=True)

    for f in archive_files:
        shutil.move(str(f), str(target / f.name))
    return True


def rename_in_modlist(profiles_dir: Path, old_name: str, new_name: str) -> None:
    """Rename in globaler modlist.txt (zeilenweises Matching)."""
    modlist_file = profiles_dir / "modlist.txt"
    if not modlist_file.is_file():
        return
    lines = modlist_file.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = False
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n\r")
        if stripped == f"+{old_name}" or stripped == f"-{old_name}":
            prefix = stripped[0]
            lines[i] = f"{prefix}{new_name}\n"
            changed = True
    if changed:
        modlist_file.write_text("".join(lines), encoding="utf-8")
        print(f"    → modlist.txt aktualisiert")


def rename_in_active_mods(profiles_dir: Path, old_name: str, new_name: str) -> None:
    """Rename in active_mods.json aller Profile."""
    for profile_dir in sorted(profiles_dir.iterdir()):
        if not profile_dir.is_dir():
            continue
        json_file = profile_dir / "active_mods.json"
        if not json_file.is_file():
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                continue
            if old_name in data:
                data = [new_name if n == old_name else n for n in data]
                json_file.write_text(
                    json.dumps(sorted(data), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                print(f"    → active_mods.json in {profile_dir.name} aktualisiert")
        except (OSError, json.JSONDecodeError):
            pass


def update_meta_ini(mod_dir: Path, old_name: str, new_name: str) -> None:
    """Aktualisiere name= in meta.ini nach Rename."""
    meta_file = mod_dir / "meta.ini"
    if not meta_file.is_file():
        return
    try:
        text = meta_file.read_text(encoding="utf-8")
        updated = text.replace(f"name={old_name}", f"name={new_name}")
        if updated != text:
            meta_file.write_text(updated, encoding="utf-8")
            print(f"    → meta.ini aktualisiert")
    except OSError:
        pass


def fix_zip_in_name(
    mod_dir: Path, profiles_dir: Path, backup_path: Path, apply: bool,
) -> bool:
    """Fix: .zip im Ordnernamen → entfernen + modlist/active_mods aktualisieren."""
    name = mod_dir.name
    if ".zip" not in name.lower():
        return False

    new_name = name
    # Case-insensitive .zip entfernen
    lower = new_name.lower()
    while ".zip" in lower:
        idx = lower.index(".zip")
        new_name = new_name[:idx] + new_name[idx + 4:]
        lower = new_name.lower()
    new_name = new_name.strip(" .")

    if new_name == name:
        return False

    new_path = mod_dir.parent / new_name
    if new_path.exists():
        print(f"  SKIP: Ziel existiert bereits: {new_name}")
        return False

    print(f"  FIX: '{name}' → '{new_name}'")
    if not apply:
        return True

    if not backup_mod(mod_dir, backup_path):
        return False

    mod_dir.rename(new_path)
    rename_in_modlist(profiles_dir, name, new_name)
    rename_in_active_mods(profiles_dir, name, new_name)
    update_meta_ini(new_path, name, new_name)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="Änderungen wirklich durchführen (Standard: Dry-Run)",
    )
    parser.add_argument(
        "--path", type=Path, default=DEFAULT_INSTANCE,
        help="Pfad zur Anvil-Instanz (Standard: Cyberpunk 2077)",
    )
    args = parser.parse_args()

    instance_path: Path = args.path
    mods_path = instance_path / ".mods"
    profiles_dir = instance_path / ".profiles"
    backup_path = instance_path / ".mods_backup_repair"

    if not mods_path.is_dir():
        print(f"FEHLER: {mods_path} existiert nicht!", file=sys.stderr)
        sys.exit(1)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== Mod-Reparatur ({mode}) ===")
    print(f"Instanz: {instance_path}")
    print(f"Mods:    {mods_path}\n")

    if args.apply:
        backup_path.mkdir(parents=True, exist_ok=True)
        print(f"Backup:  {backup_path}\n")

    stats = {"pc_fix": 0, "archive_fix": 0, "zip_fix": 0, "total": 0}

    for mod_dir in sorted(mods_path.iterdir()):
        if not mod_dir.is_dir():
            continue
        if mod_dir.name.endswith("_separator"):
            continue

        stats["total"] += 1

        if fix_pc_without_archive(mod_dir, backup_path, args.apply):
            stats["pc_fix"] += 1

        if fix_archive_in_root(mod_dir, backup_path, args.apply):
            stats["archive_fix"] += 1

        if fix_zip_in_name(mod_dir, profiles_dir, backup_path, args.apply):
            stats["zip_fix"] += 1

    print(f"\n=== Ergebnis ===")
    print(f"Mods geprüft:              {stats['total']}")
    print(f"pc/ → archive/pc/ :        {stats['pc_fix']}")
    print(f".archive → archive/pc/mod/: {stats['archive_fix']}")
    print(f".zip im Namen entfernt:    {stats['zip_fix']}")
    total_fixes = stats["pc_fix"] + stats["archive_fix"] + stats["zip_fix"]
    print(f"Gesamt-Fixes:              {total_fixes}")

    if not args.apply and total_fixes > 0:
        print(f"\nDry-Run! Zum Anwenden: python3 {__file__} --apply")


if __name__ == "__main__":
    main()
