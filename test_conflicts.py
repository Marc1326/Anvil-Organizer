#!/usr/bin/env python3
"""Test: Intelligente Konflikterkennung vs. MO2-Dateiname-Matching.

Erstellt Fake-Mod-Ordner mit Testdateien und zeigt den Unterschied
zwischen echter Konflikterkennung (gleicher relativer Pfad) und
MO2-Style Matching (gleicher Dateiname).
"""

import shutil
import tempfile
from pathlib import Path

from anvil.core.conflict_scanner import ConflictScanner
from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game


def create_test_mods(base: Path) -> list[dict]:
    """Erstelle Fake-Mod-Ordner mit Testdateien."""
    mods = []

    # -- ModA: Outfit-Mod mit Archiv + Readme --------------------------------
    mod_a = base / "Outfit_Neon_Jacket"
    (mod_a / "archive/pc/mod").mkdir(parents=True)
    (mod_a / "archive/pc/mod" / "neon_jacket.archive").write_text("fake archive A")
    (mod_a / "readme.txt").write_text("Install instructions for Neon Jacket")
    (mod_a / "Item codes.txt").write_text("Spawn codes: game.AddToInventory(...)")
    (mod_a / "meta.ini").write_text("[General]\nname=Neon Jacket")
    mods.append({"name": "Outfit_Neon_Jacket", "path": str(mod_a)})

    # -- ModB: Anderer Outfit-Mod mit GLEICHEM Archiv-Pfad (ECHTER Konflikt) --
    mod_b = base / "Outfit_Cyber_Suit"
    (mod_b / "archive/pc/mod").mkdir(parents=True)
    (mod_b / "archive/pc/mod" / "neon_jacket.archive").write_text("fake archive B")  # KONFLIKT!
    (mod_b / "readme.txt").write_text("Install instructions for Cyber Suit")
    (mod_b / "Item codes.txt").write_text("Spawn codes: game.AddToInventory(...)")
    (mod_b / "credits.txt").write_text("Thanks to xyz")
    mods.append({"name": "Outfit_Cyber_Suit", "path": str(mod_b)})

    # -- ModC: Waffen-Mod mit eigenem Archiv (kein Konflikt) ------------------
    mod_c = base / "Weapon_Katana"
    (mod_c / "archive/pc/mod").mkdir(parents=True)
    (mod_c / "archive/pc/mod" / "katana_weapon.archive").write_text("fake katana")
    (mod_c / "readme.txt").write_text("Katana mod readme")
    (mod_c / "docs").mkdir()
    (mod_c / "docs" / "changelog.txt").write_text("v1.0 - Initial release")
    (mod_c / "CHANGELOG.md").write_text("# Changelog\n- v1.0")
    mods.append({"name": "Weapon_Katana", "path": str(mod_c)})

    # -- ModD: Dritter Mod mit gleichem Archiv-Pfad (3-Wege-Konflikt) ---------
    mod_d = base / "Outfit_Retro_Vest"
    (mod_d / "archive/pc/mod").mkdir(parents=True)
    (mod_d / "archive/pc/mod" / "neon_jacket.archive").write_text("fake archive D")  # KONFLIKT!
    (mod_d / "readme.txt").write_text("Retro Vest readme")
    mods.append({"name": "Outfit_Retro_Vest", "path": str(mod_d)})

    # -- ModE: CET-Mod mit Item Codes (gleicher Name, anderer Pfad = KEIN Konflikt)
    mod_e = base / "CET_Spawner"
    (mod_e / "bin/x64/plugins/cyber_engine_tweaks/mods/spawner").mkdir(parents=True)
    (mod_e / "bin/x64/plugins/cyber_engine_tweaks/mods/spawner" / "init.lua").write_text("-- lua")
    (mod_e / "bin/x64/plugins/cyber_engine_tweaks/mods/spawner" / "Item codes.txt").write_text("Other codes")
    mods.append({"name": "CET_Spawner", "path": str(mod_e)})

    # -- ModF: Gleicher relativer Pfad wie ModC's Unterordner-Datei -----------
    mod_f = base / "Weapon_Bow"
    (mod_f / "archive/pc/mod").mkdir(parents=True)
    (mod_f / "archive/pc/mod" / "bow_weapon.archive").write_text("fake bow")
    (mod_f / "docs").mkdir()
    (mod_f / "docs" / "changelog.txt").write_text("v2.0 - Updated")  # gleicher rel. Pfad wie ModC!
    mods.append({"name": "Weapon_Bow", "path": str(mod_f)})

    return mods


def mo2_style_conflicts(mods: list[dict]) -> list[dict]:
    """MO2-Style: Nur Dateinamen vergleichen (zum Vergleich)."""
    name_owners: dict[str, list[str]] = {}
    for mod in mods:
        mod_root = Path(mod["path"])
        if not mod_root.is_dir():
            continue
        for f in mod_root.rglob("*"):
            if f.is_file() and f.name != "meta.ini":
                owners = name_owners.setdefault(f.name, [])
                owners.append(mod["name"])
    return [
        {"file": name, "mods": owners}
        for name, owners in name_owners.items()
        if len(owners) >= 2
    ]


def main():
    tmp = Path(tempfile.mkdtemp(prefix="anvil_conflict_test_"))
    print(f"Test-Verzeichnis: {tmp}\n")

    try:
        mods = create_test_mods(tmp)
        plugin = Cyberpunk2077Game()
        scanner = ConflictScanner()

        # ── MO2-Style (nur Dateinamen) ────────────────────────────────
        mo2_results = mo2_style_conflicts(mods)

        print("=" * 70)
        print("  MO2-STYLE KONFLIKTE (nur Dateinamen)")
        print("=" * 70)
        for c in mo2_results:
            print(f"  {c['file']:<30} Mods: {', '.join(c['mods'])}")
        print(f"\n  Total: {len(mo2_results)} Konflikte")

        # ── Anvil: Intelligente Erkennung ─────────────────────────────
        result = scanner.scan_conflicts(mods, plugin)

        print(f"\n{'=' * 70}")
        print("  ANVIL: ECHTE KONFLIKTE (gleicher relativer Pfad)")
        print("=" * 70)
        if result["conflicts"]:
            for c in result["conflicts"]:
                print(f"  {c['file']}")
                print(f"    Mods:   {', '.join(c['mods'])}")
                print(f"    Winner: {c['winner']}")
        else:
            print("  Keine echten Konflikte gefunden.")
        print(f"\n  Total: {len(result['conflicts'])} echte Konflikte")

        print(f"\n{'=' * 70}")
        print("  ANVIL: IGNORIERTE MATCHES (harmlose Dateien)")
        print("=" * 70)
        if result["ignored"]:
            for c in result["ignored"]:
                print(f"  {c['file']:<40} Mods: {', '.join(c['mods'])}")
        else:
            print("  Keine ignorierten Matches.")
        print(f"\n  Total: {len(result['ignored'])} ignoriert")

        # ── Vergleich ─────────────────────────────────────────────────
        print(f"\n{'=' * 70}")
        print("  VERGLEICH")
        print("=" * 70)
        print(f"  MO2-Style:  {len(mo2_results)} Konflikte (viele falsch-positiv)")
        print(f"  Anvil:      {len(result['conflicts'])} echte Konflikte")
        print(f"  Ignoriert:  {len(result['ignored'])} (durch Game-Plugin gefiltert)")
        reduction = len(mo2_results) - len(result["conflicts"])
        print(f"  Reduktion:  {reduction} falsche Konflikte eliminiert")

        # ── Assertions ────────────────────────────────────────────────
        print(f"\n{'=' * 70}")
        print("  ASSERTIONS")
        print("=" * 70)

        # 1. Echter Konflikt: neon_jacket.archive bei 3 Mods
        archive_conflict = [c for c in result["conflicts"] if "neon_jacket.archive" in c["file"]]
        assert len(archive_conflict) == 1, "neon_jacket.archive sollte genau 1 Konflikt sein"
        assert len(archive_conflict[0]["mods"]) == 3, "neon_jacket.archive: 3 Mods beteiligt"
        assert archive_conflict[0]["winner"] == "Outfit_Retro_Vest", "Letzter Mod gewinnt"
        print("  [OK] neon_jacket.archive: 3-Wege-Konflikt, Winner = Outfit_Retro_Vest")

        # 2. readme.txt wird ignoriert (nicht als Konflikt gemeldet)
        readme_conflicts = [c for c in result["conflicts"] if "readme.txt" in c["file"]]
        assert len(readme_conflicts) == 0, "readme.txt sollte ignoriert werden"
        readme_ignored = [c for c in result["ignored"] if "readme.txt" in c["file"]]
        assert len(readme_ignored) >= 1, "readme.txt sollte in ignored sein"
        print("  [OK] readme.txt: ignoriert (kein falscher Konflikt)")

        # 3. Item codes.txt auf verschiedenen Pfaden = kein Konflikt
        item_codes_conflicts = [c for c in result["conflicts"] if "Item codes.txt" in c["file"]]
        assert len(item_codes_conflicts) == 0, "Item codes.txt (verschiedene Pfade) = kein Konflikt"
        print("  [OK] Item codes.txt: verschiedene Pfade = kein Konflikt")

        # 4. Item codes.txt gleicher Pfad (ModA + ModB) wird ignoriert durch Pattern
        item_codes_ignored = [c for c in result["ignored"] if c["file"] == "Item codes.txt"]
        assert len(item_codes_ignored) == 1, "Item codes.txt (gleicher Pfad) sollte ignoriert werden"
        print("  [OK] Item codes.txt: gleicher Pfad wird durch Pattern ignoriert")

        # 5. docs/changelog.txt (ModC + ModF) wird ignoriert
        docs_conflicts = [c for c in result["conflicts"] if "docs/changelog.txt" in c["file"]]
        assert len(docs_conflicts) == 0, "docs/changelog.txt sollte ignoriert werden"
        print("  [OK] docs/changelog.txt: ignoriert durch Pattern")

        # 6. CHANGELOG.md wird nicht als Konflikt gemeldet (nur in 1 Mod)
        md_conflicts = [c for c in result["conflicts"] if ".md" in c["file"]]
        assert len(md_conflicts) == 0, ".md Dateien sollten keine Konflikte haben"
        print("  [OK] .md Dateien: kein Konflikt")

        # 7. meta.ini wird komplett uebersprungen
        meta_any = [c for c in result["conflicts"] + result["ignored"] if "meta.ini" in c["file"]]
        assert len(meta_any) == 0, "meta.ini sollte komplett uebersprungen werden"
        print("  [OK] meta.ini: komplett uebersprungen (Anvil-intern)")

        # 8. MO2 hat mehr Konflikte als Anvil
        assert len(mo2_results) > len(result["conflicts"]), "MO2 meldet mehr Konflikte als Anvil"
        print(f"  [OK] MO2 ({len(mo2_results)}) > Anvil ({len(result['conflicts'])}) Konflikte")

        print(f"\n  Alle Assertions bestanden!")

    finally:
        shutil.rmtree(tmp)
        print(f"\nTest-Verzeichnis aufgeraeumt: {tmp}")


if __name__ == "__main__":
    main()
