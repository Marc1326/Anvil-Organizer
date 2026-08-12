"""Ladereihenfolge fuer Archiv-Mods (Cyberpunk 2077).

Das Spiel haengt die Archive alphabetisch nach Dateiname ein. Liegt eine
Ladeliste im Ordner, laedt es stattdessen genau in deren Reihenfolge --
zuletzt genannt heisst zuletzt geladen und damit gewonnen.
"""

from pathlib import Path

from anvil.core.mod_deployer import ModDeployer
from anvil.core.mod_list_io import write_active_mods, write_global_modlist

LISTE = "archive/pc/mod/modlist.txt"
ORDNER = "archive/pc/mod"


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


def _mod(mods: Path, name: str, archiv: str) -> None:
    ziel = mods / name / ORDNER / archiv
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(b"x")


def _liste(profiles: Path, namen: list[str]) -> None:
    write_global_modlist(profiles, namen)
    write_active_mods(profiles / "Default", set(namen))


def _deployer(instance: Path, game: Path) -> ModDeployer:
    return ModDeployer(instance, game, archive_load_order_file=LISTE)


def _zeilen(game: Path) -> list[str]:
    return (game / LISTE).read_text(encoding="utf-8").splitlines()


# ── 8./9. Die Liste entsteht und bildet die Reihenfolge ab ─────────────

def test_ladeliste_wird_geschrieben(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "Oben", "oben.archive")
    _mod(mods, "Unten", "unten.archive")
    _liste(profiles, ["Oben", "Unten"])

    _deployer(instance, game).deploy()

    zeilen = _zeilen(game)
    assert sorted(zeilen) == ["oben.archive", "unten.archive"]
    assert len(zeilen) == len(set(zeilen))


def test_oberste_mod_steht_zuletzt(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "Oben", "aaa.archive")
    _mod(mods, "Mitte", "mmm.archive")
    _mod(mods, "Unten", "zzz.archive")
    _liste(profiles, ["Oben", "Mitte", "Unten"])

    _deployer(instance, game).deploy()

    # Nach Dateiname allein wuerde zzz gewinnen -- das waere Zufall.
    assert _zeilen(game) == ["zzz.archive", "mmm.archive", "aaa.archive"]


def test_ohne_archive_entsteht_keine_liste(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    ziel = mods / "M" / "r6" / "scripts" / "m.reds"
    ziel.parent.mkdir(parents=True)
    ziel.write_bytes(b"x")
    _liste(profiles, ["M"])

    _deployer(instance, game).deploy()

    assert not (game / LISTE).exists()


# ── 10. Fremde Archive stehen mit drin ─────────────────────────────────

def test_handkopiertes_archiv_steht_in_der_liste(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    fremd = game / ORDNER / "fremd.archive"
    fremd.parent.mkdir(parents=True)
    fremd.write_bytes(b"x")
    _mod(mods, "Oben", "oben.archive")
    _liste(profiles, ["Oben"])

    _deployer(instance, game).deploy()

    # Vorn: die fremde Datei verliert gegen jede verwaltete Mod.
    assert _zeilen(game) == ["fremd.archive", "oben.archive"]


# ── 11. Aufraeumen ─────────────────────────────────────────────────────

def test_purge_entfernt_die_liste(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "Oben", "oben.archive")
    _liste(profiles, ["Oben"])

    deployer = _deployer(instance, game)
    deployer.deploy()
    assert (game / LISTE).is_file()

    deployer.purge()

    assert not (game / LISTE).exists()


def test_liste_gilt_nicht_als_fremde_datei(tmp_path: Path) -> None:
    """Sonst meldet Anvil seine eigene Ladeliste als Fund."""
    from anvil.core.foreign_mods import scan_instance

    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "Oben", "oben.archive")
    _liste(profiles, ["Oben"])

    deployer = _deployer(instance, game)
    deployer.deploy()

    funde = scan_instance(
        game, [ORDNER], instance / ModDeployer.MANIFEST_NAME,
    )
    assert [f.rel for f in funde] == []


# ── 12. Fremde Liste wird vorher gesichert ─────────────────────────────

def test_fremde_liste_wird_gesichert(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    vorhanden = game / LISTE
    vorhanden.parent.mkdir(parents=True)
    vorhanden.write_text("eigene.archive\n", encoding="utf-8")
    _mod(mods, "Oben", "oben.archive")
    _liste(profiles, ["Oben"])

    _deployer(instance, game).deploy()

    sicherung = game / (LISTE + ".anvil_backup")
    assert sicherung.read_text(encoding="utf-8") == "eigene.archive\n"
    assert _zeilen(game) == ["oben.archive"]


def test_purge_holt_die_fremde_liste_zurueck(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    vorhanden = game / LISTE
    vorhanden.parent.mkdir(parents=True)
    vorhanden.write_text("eigene.archive\n", encoding="utf-8")
    _mod(mods, "Oben", "oben.archive")
    _liste(profiles, ["Oben"])

    deployer = _deployer(instance, game)
    deployer.deploy()
    deployer.purge()

    assert vorhanden.read_text(encoding="utf-8") == "eigene.archive\n"
    assert not (game / (LISTE + ".anvil_backup")).exists()


def test_zweiter_lauf_ueberschreibt_die_sicherung_nicht(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    vorhanden = game / LISTE
    vorhanden.parent.mkdir(parents=True)
    vorhanden.write_text("eigene.archive\n", encoding="utf-8")
    _mod(mods, "Oben", "oben.archive")
    _liste(profiles, ["Oben"])

    deployer = _deployer(instance, game)
    deployer.deploy()
    # Zweiter Lauf ohne Aufraeumen dazwischen -- so als waere Anvil
    # abgestuerzt und die eigene Liste liegengeblieben.
    (instance / ModDeployer.MANIFEST_NAME).unlink()
    deployer.deploy()

    sicherung = game / (LISTE + ".anvil_backup")
    assert sicherung.read_text(encoding="utf-8") == "eigene.archive\n"


# ── Plugin-Angaben ─────────────────────────────────────────────────────

def test_cyberpunk_kennt_die_ladeliste() -> None:
    from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game

    assert Cyberpunk2077Game.GameArchiveLoadOrderFile == LISTE


def test_vorgabe_ist_leer() -> None:
    from anvil.plugins.base_game import BaseGame

    assert BaseGame.GameArchiveLoadOrderFile == ""
