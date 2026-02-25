#!/usr/bin/env python3
"""Test LSPK parser with real BG3 .pak files.

Searches for .pak files on mounted gaming drives. If no drive is
mounted the test prints a message and exits cleanly.

Usage:
    python3 test_lspk_parser.py
    python3 test_lspk_parser.py /path/to/specific.pak
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from anvil.core.lspk_parser import LSPKReader


# ── Search paths for BG3 .pak files ──────────────────────────────────

SEARCH_PATHS = [
    Path("/mnt/gamingS/SteamLibrary/steamapps/common/Baldurs Gate 3/Data/Mods"),
    Path("/mnt/Gaming2/SteamLibrary/steamapps/common/Baldurs Gate 3/Data/Mods"),
    # Proton prefix pak mods
    Path("/mnt/gamingS/SteamLibrary/steamapps/compatdata/1086940/pfx/drive_c/users/steamuser/AppData/Local/Larian Studios/Baldur's Gate 3/Mods"),
]

MAX_PAKS = 10  # Max paks to test


def format_size(size: int) -> str:
    if size >= 1_000_000_000:
        return f"{size / 1_000_000_000:.1f} GB"
    if size >= 1_000_000:
        return f"{size / 1_000_000:.1f} MB"
    if size >= 1_000:
        return f"{size / 1_000:.1f} KB"
    return f"{size} B"


def test_single_pak(reader: LSPKReader, pak_path: Path) -> bool:
    """Test a single .pak file. Returns True if metadata was extracted."""
    size = pak_path.stat().st_size
    print(f"\n{'─' * 60}")
    print(f"  Datei:  {pak_path.name}")
    print(f"  Pfad:   {pak_path}")
    print(f"  Groesse: {format_size(size)}")

    meta = reader.read_pak_metadata(pak_path)

    if meta is None:
        print("  Ergebnis: KEINE METADATEN (meta.lsx/info.json nicht gefunden oder nicht lesbar)")
        return False

    print(f"  UUID:    {meta.get('uuid', '—')}")
    print(f"  Name:    {meta.get('name', '—')}")
    print(f"  Folder:  {meta.get('folder', '—')}")
    print(f"  Author:  {meta.get('author', '—')}")
    print(f"  Version: {meta.get('version', '—')}")
    if meta.get("description"):
        desc = meta["description"]
        if len(desc) > 80:
            desc = desc[:77] + "..."
        print(f"  Beschr.: {desc}")
    deps = meta.get("dependencies", [])
    if deps:
        print(f"  Dependencies ({len(deps)}):")
        for dep in deps[:5]:
            print(f"    - {dep.get('name', '?')} ({dep.get('uuid', '?')})")
        if len(deps) > 5:
            print(f"    ... und {len(deps) - 5} weitere")
    else:
        print("  Dependencies: keine")

    return True


def main():
    print("=" * 60)
    print("  LSPK V18 Parser Test — BG3 .pak Metadaten-Extraktion")
    print("=" * 60)

    reader = LSPKReader()

    # ── Single pak from command line ──────────────────────────
    if len(sys.argv) > 1:
        pak = Path(sys.argv[1])
        if not pak.is_file():
            print(f"\nFehler: {pak} nicht gefunden")
            sys.exit(1)
        ok = test_single_pak(reader, pak)
        print(f"\n{'─' * 60}")
        print(f"  Ergebnis: {'OK' if ok else 'FEHLGESCHLAGEN'}")
        sys.exit(0 if ok else 1)

    # ── Search for paks on gaming drives ──────────────────────
    pak_files: list[Path] = []
    for search_path in SEARCH_PATHS:
        if search_path.is_dir():
            paks = sorted(search_path.glob("*.pak"), key=lambda p: p.name.lower())
            pak_files.extend(paks)

    if not pak_files:
        print("\nKeine .pak Dateien gefunden.")
        print("Gaming-Platten nicht gemountet oder keine Mods installiert.")
        print(f"\nGesuchte Pfade:")
        for p in SEARCH_PATHS:
            print(f"  {p}")
        print("\nAlternativ: python3 test_lspk_parser.py /pfad/zur/datei.pak")
        sys.exit(0)

    print(f"\n{len(pak_files)} .pak Datei(en) gefunden.")
    if len(pak_files) > MAX_PAKS:
        print(f"Teste die ersten {MAX_PAKS}:")
        pak_files = pak_files[:MAX_PAKS]

    success = 0
    failed = 0
    for pak in pak_files:
        if test_single_pak(reader, pak):
            success += 1
        else:
            failed += 1

    print(f"\n{'═' * 60}")
    print(f"  Ergebnis: {success} OK, {failed} fehlgeschlagen, {success + failed} gesamt")
    print(f"{'═' * 60}")


if __name__ == "__main__":
    main()
