"""Ladereihenfolge fuer Unreal-Spiele mit ~mods-Ordner.

Das Spiel haengt die Paks alphabetisch nach Dateiname ein und laesst die
zuletzt eingehaengte gewinnen. Ohne Zaehler im Namen waere die Reihenfolge
in Anvil fuer diese Spiele reine Anzeige ohne Wirkung.
"""

from pathlib import Path

from anvil.core.mod_deployer import ModDeployer, pak_load_order_name
from anvil.core.mod_list_io import write_active_mods, write_global_modlist


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


def _mod(mods: Path, name: str, dateien: list[str]) -> None:
    for rel in dateien:
        ziel = mods / name / rel
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"x")


# ── Die Namensregel ────────────────────────────────────────────────────

def test_pak_bekommt_zaehler() -> None:
    assert pak_load_order_name(Path("FoxEYE_P.pak"), 3) == Path("003_FoxEYE_P.pak")


def test_alle_drei_endungen_bekommen_denselben_zaehler() -> None:
    """Sonst findet das Spiel das Dreiergespann nicht mehr zusammen."""
    namen = [
        pak_load_order_name(Path(f"FoxEYE_P{ext}"), 7).name
        for ext in (".pak", ".utoc", ".ucas")
    ]
    assert namen == ["007_FoxEYE_P.pak", "007_FoxEYE_P.utoc", "007_FoxEYE_P.ucas"]


def test_andere_dateien_bleiben_unberuehrt() -> None:
    assert pak_load_order_name(Path("readme.txt"), 1) == Path("readme.txt")
    assert pak_load_order_name(Path("UE4SS/main.lua"), 1) == Path("UE4SS/main.lua")


def test_unterordner_bleibt_erhalten() -> None:
    got = pak_load_order_name(Path("SB/Content/Paks/~mods/a_P.pak"), 12)
    assert got == Path("SB/Content/Paks/~mods/012_a_P.pak")


# ── Im Deploy ──────────────────────────────────────────────────────────

def test_anvil_reihenfolge_bestimmt_die_ladereihenfolge(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "Gewinner", ["Zebra_P.pak", "Zebra_P.utoc", "Zebra_P.ucas"])
    _mod(mods, "Verlierer", ["Alpha_P.pak", "Alpha_P.utoc", "Alpha_P.ucas"])
    # In Anvil steht "Gewinner" oben, hat also die hoechste Prioritaet --
    # nach Dateiname allein wuerde "Zebra" gewinnen, das waere Zufall.
    write_global_modlist(profiles, ["Gewinner", "Verlierer"])
    write_active_mods(profiles / "Default", {"Gewinner", "Verlierer"})

    ModDeployer(
        instance, game,
        data_path="SB/Content/Paks/~mods",
        pak_load_order_prefix=True,
    ).deploy()

    ordner = game / "SB" / "Content" / "Paks" / "~mods"
    namen = sorted(p.name for p in ordner.iterdir())
    # Der Zaehler des Gewinners muss groesser sein -- er wird zuletzt
    # eingehaengt und schlaegt damit den Verlierer.
    gewinner = next(n for n in namen if "Zebra" in n)
    verlierer = next(n for n in namen if "Alpha" in n)
    assert gewinner > verlierer, f"{gewinner} muss nach {verlierer} kommen"
    assert gewinner.startswith("001_")
    assert verlierer.startswith("000_")


def test_dreiergespann_bleibt_zusammen(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "M", ["FoxEYE_P.pak", "FoxEYE_P.utoc", "FoxEYE_P.ucas"])
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    ModDeployer(
        instance, game,
        data_path="SB/Content/Paks/~mods",
        pak_load_order_prefix=True,
    ).deploy()

    ordner = game / "SB" / "Content" / "Paks" / "~mods"
    stamm = {p.stem for p in ordner.iterdir()}
    assert len(stamm) == 1, f"Namen laufen auseinander: {sorted(p.name for p in ordner.iterdir())}"


def test_ohne_die_eigenschaft_bleibt_alles_wie_vorher(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "M", ["FoxEYE_P.pak"])
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    ModDeployer(instance, game, data_path="SB/Content/Paks/~mods").deploy()

    ordner = game / "SB" / "Content" / "Paks" / "~mods"
    assert [p.name for p in ordner.iterdir()] == ["FoxEYE_P.pak"]


def test_stellar_blade_plugin_hat_es_eingeschaltet() -> None:
    from anvil.plugins.games.game_stellarblade import StellarBladeGame

    assert StellarBladeGame.GamePakLoadOrderPrefix is True
    assert StellarBladeGame.GameDataPath == "SB/Content/Paks/~mods"


def test_vorgabe_ist_aus() -> None:
    from anvil.plugins.base_game import BaseGame

    assert BaseGame.GamePakLoadOrderPrefix is False
