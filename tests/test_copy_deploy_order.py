"""Ladereihenfolge bei kopierten Dateien.

Ausgerollt wird von der niedrigsten zur hoechsten Prioritaet. Wer eine
schon geschriebene Kopie fuer eine echte Spieldatei haelt, ueberspringt
die staerkere Mod -- dann gewinnt die unterste statt der obersten.
"""

import os
from pathlib import Path

from anvil.core.mod_deployer import ModDeployer
from anvil.core.mod_list_io import write_active_mods, write_global_modlist

KOPIERPFADE = ["red4ext/plugins"]
DATEI = "red4ext/plugins/foo/foo.dll"


def _welt(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    instance = tmp_path / "Instance"
    game = tmp_path / "Game"
    instance.mkdir()
    game.mkdir()
    mods = instance / ".mods"
    profiles = instance / ".profiles"
    (profiles / "Default").mkdir(parents=True)
    mods.mkdir()
    return instance, game, mods, profiles


def _mod(mods: Path, name: str, rel: str, inhalt: str) -> Path:
    ziel = mods / name / rel
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(inhalt, encoding="utf-8")
    return ziel


def _liste(profiles: Path, namen: list[str]) -> None:
    write_global_modlist(profiles, namen)
    write_active_mods(profiles / "Default", set(namen))


# ── 1. Oberste Mod gewinnt ─────────────────────────────────────────────

def test_oberste_mod_gewinnt_bei_kopierten_dateien(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "Oben", DATEI, "oben")
    _mod(mods, "Unten", DATEI, "unten")
    _liste(profiles, ["Oben", "Unten"])

    ergebnis = ModDeployer(
        instance, game, copy_deploy_paths=KOPIERPFADE,
    ).deploy()

    assert (game / DATEI).read_text(encoding="utf-8") == "oben"
    assert ergebnis.skipped_real_files == []


# ── 2. Echte Spieldateien bleiben geschuetzt ───────────────────────────

def test_vorgefundene_spieldatei_wird_nicht_ueberschrieben(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    original = game / DATEI
    original.parent.mkdir(parents=True)
    original.write_text("spiel", encoding="utf-8")
    _mod(mods, "Oben", DATEI, "oben")
    _liste(profiles, ["Oben"])

    ergebnis = ModDeployer(
        instance, game, copy_deploy_paths=KOPIERPFADE,
    ).deploy()

    assert original.read_text(encoding="utf-8") == "spiel"
    assert str(Path(DATEI)) in ergebnis.skipped_real_files


def test_geschuetzt_bleibt_auch_bei_mehreren_mods(tmp_path: Path) -> None:
    """Die Sperre darf nicht durch eine zweite Mod aufweichen."""
    instance, game, mods, profiles = _welt(tmp_path)
    original = game / DATEI
    original.parent.mkdir(parents=True)
    original.write_text("spiel", encoding="utf-8")
    _mod(mods, "Oben", DATEI, "oben")
    _mod(mods, "Unten", DATEI, "unten")
    _liste(profiles, ["Oben", "Unten"])

    ergebnis = ModDeployer(
        instance, game, copy_deploy_paths=KOPIERPFADE,
    ).deploy()

    assert original.read_text(encoding="utf-8") == "spiel"
    assert ergebnis.skipped_real_files.count(str(Path(DATEI))) == 2


# ── 3. Frameworks duerfen weiterhin ueberschreiben ─────────────────────

def test_framework_ueberschreibt_echte_spieldatei(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    original = game / "red4ext" / "RED4ext.dll"
    original.parent.mkdir(parents=True)
    original.write_text("spiel", encoding="utf-8")
    _mod(mods, "RED4ext", "red4ext/RED4ext.dll", "framework")
    _liste(profiles, ["RED4ext"])

    ModDeployer(
        instance, game, ["RED4ext"], copy_deploy_paths=KOPIERPFADE,
    ).deploy()

    assert original.read_text(encoding="utf-8") == "framework"


def test_hoeheres_framework_wird_nicht_zurueckgeschrieben(tmp_path: Path) -> None:
    """Der Abgleich mit dem Spielordner darf nicht nach hinten losgehen.

    Ist die Datei der untersten Mod juenger, hielte der Abgleich die
    gerade geschriebene Kopie fuer ein Update aus dem Spiel und wuerde
    sie in die obere Mod zurueckschreiben.
    """
    instance, game, mods, profiles = _welt(tmp_path)
    oben = _mod(mods, "FW-Oben", "red4ext/RED4ext.dll", "oben")
    _mod(mods, "FW-Unten", "red4ext/RED4ext.dll", "unten")
    alt = oben.stat().st_mtime - 10_000
    os.utime(oben, (alt, alt))
    _liste(profiles, ["FW-Oben", "FW-Unten"])

    ModDeployer(
        instance, game, ["fw"], copy_deploy_paths=KOPIERPFADE,
    ).deploy()

    assert oben.read_text(encoding="utf-8") == "oben"
    ziel = game / "red4ext" / "RED4ext.dll"
    assert ziel.read_text(encoding="utf-8") == "oben"
