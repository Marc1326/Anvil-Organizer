"""Der Unreal-Zaehler wird pro Spiel auf einzelne Ordner begrenzt.

In ~mods entscheidet der Dateiname ueber die Ladereihenfolge, dort ist der
Zaehler noetig. In LogicMods, CNS und neben der Spiel-Exe suchen die Loader
ihre Dateien am Namen -- dort darf nichts umbenannt werden.
"""

from pathlib import Path

from anvil.core.mod_deployer import ModDeployer, pak_load_order_name, pak_order_allows
from anvil.core.mod_list_io import write_active_mods, write_global_modlist

MODS_ORDNER = "Stalker2/Content/Paks/~mods"
LOGIC_ORDNER = "Stalker2/Content/Paks/LogicMods"


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


def _liste(profiles: Path, namen: list[str]) -> None:
    write_global_modlist(profiles, namen)
    write_active_mods(profiles / "Default", set(namen))


def _namen(ordner: Path) -> list[str]:
    return sorted(p.name for p in ordner.iterdir())


# ── Die Freigabe-Regel ─────────────────────────────────────────────────

def test_ohne_freigabe_gilt_keine_begrenzung() -> None:
    assert pak_order_allows(Path("egal/x.pak"), []) is True


def test_nur_unterhalb_der_freigegebenen_ordner() -> None:
    frei = [MODS_ORDNER]
    assert pak_order_allows(Path(f"{MODS_ORDNER}/a_P.pak"), frei) is True
    assert pak_order_allows(Path(f"{MODS_ORDNER}/Unter/a_P.pak"), frei) is True
    assert pak_order_allows(Path(f"{LOGIC_ORDNER}/bp_P.pak"), frei) is False
    assert pak_order_allows(Path("Stalker2/Binaries/Win64/x.dll"), frei) is False


def test_signatur_bekommt_denselben_zaehler() -> None:
    """Sie wird ueber den Basisnamen zugeordnet und liefe sonst ins Leere."""
    namen = [
        pak_load_order_name(Path(f"a_P{ext}"), 4).name
        for ext in (".pak", ".utoc", ".ucas", ".sig")
    ]
    assert namen == ["004_a_P.pak", "004_a_P.utoc", "004_a_P.ucas", "004_a_P.sig"]


# ── 13. Vorgabe ist aus ────────────────────────────────────────────────

def test_vorgabe_ist_leer() -> None:
    from anvil.plugins.base_game import BaseGame

    assert BaseGame.GamePakLoadOrderDirs == []
    assert BaseGame.GamePakLoadOrderPrefix is False


def test_ohne_freigabe_wird_nichts_umbenannt(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "M", [f"{MODS_ORDNER}/a_P.pak"])
    _liste(profiles, ["M"])

    ModDeployer(instance, game).deploy()

    assert _namen(game / MODS_ORDNER) == ["a_P.pak"]


# ── 14. Nur die freigegebenen Ordner ───────────────────────────────────

def test_nur_freigegebene_ordner_bekommen_den_zaehler(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "M", [
        f"{MODS_ORDNER}/a_P.pak",
        f"{LOGIC_ORDNER}/bp_P.pak",
        "Stalker2/Binaries/Win64/ue4ss/UE4SS.dll",
    ])
    _liste(profiles, ["M"])

    ModDeployer(
        instance, game, pak_load_order_dirs=[MODS_ORDNER],
    ).deploy()

    assert _namen(game / MODS_ORDNER) == ["000_a_P.pak"]
    assert _namen(game / LOGIC_ORDNER) == ["bp_P.pak"]
    assert _namen(game / "Stalker2/Binaries/Win64/ue4ss") == ["UE4SS.dll"]


# ── 15. Das Gespann bleibt zusammen ────────────────────────────────────

def test_gespann_bekommt_denselben_zaehler(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "M", [
        f"{MODS_ORDNER}/a_P.pak",
        f"{MODS_ORDNER}/a_P.utoc",
        f"{MODS_ORDNER}/a_P.ucas",
        f"{MODS_ORDNER}/a_P.sig",
    ])
    _liste(profiles, ["M"])

    ModDeployer(
        instance, game, pak_load_order_dirs=[MODS_ORDNER],
    ).deploy()

    stamm = {p.stem for p in (game / MODS_ORDNER).iterdir()}
    assert stamm == {"000_a_P"}


# ── 16. Der Zaehler bildet die Reihenfolge ab ──────────────────────────

def test_oberste_mod_bekommt_die_groesste_zahl(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "Oben", [f"{MODS_ORDNER}/aaa_P.pak"])
    _mod(mods, "Unten", [f"{MODS_ORDNER}/zzz_P.pak"])
    _liste(profiles, ["Oben", "Unten"])

    ModDeployer(
        instance, game, pak_load_order_dirs=[MODS_ORDNER],
    ).deploy()

    assert _namen(game / MODS_ORDNER) == ["000_zzz_P.pak", "001_aaa_P.pak"]


# ── Am Plugin ──────────────────────────────────────────────────────────

def test_stalker2_gibt_nur_mods_frei() -> None:
    from anvil.plugins.games.game_stalker2 import Stalker2Game

    assert Stalker2Game.GamePakLoadOrderDirs == [MODS_ORDNER]
    # Der unbegrenzte Schalter bleibt aus -- sonst traefe der Zaehler
    # auch LogicMods und die Loader neben der Spiel-Exe.
    assert Stalker2Game.GamePakLoadOrderPrefix is False


def test_stalker2_verteilung_mit_zaehler(tmp_path: Path) -> None:
    """Mit den echten Plugin-Angaben durchgespielt."""
    from anvil.plugins.games.game_stalker2 import Stalker2Game as S2

    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "Oben", ["~mods/aaa_P.pak"])
    _mod(mods, "Unten", ["~mods/zzz_P.pak"])
    _mod(mods, "Blueprint", ["LogicMods/bp_P.pak"])
    _liste(profiles, ["Oben", "Unten", "Blueprint"])

    ModDeployer(
        instance, game,
        data_path=S2.GameDataPath,
        copy_deploy_paths=S2.GameCopyDeployPaths,
        pak_load_order_prefix=S2.GamePakLoadOrderPrefix,
        pak_load_order_dirs=S2.GamePakLoadOrderDirs,
        deploy_strip_prefixes=S2.GameDeployStripPrefixes,
        deploy_anchors=S2.GameDeployAnchors,
        deploy_routes=S2.GameDeployRoutes,
    ).deploy()

    assert _namen(game / MODS_ORDNER) == ["001_zzz_P.pak", "002_aaa_P.pak"]
    assert _namen(game / LOGIC_ORDNER) == ["bp_P.pak"]


def test_stellar_blade_bleibt_aus() -> None:
    """Die Mod-Autoren verbieten das Umbenennen ausdruecklich."""
    from anvil.plugins.games.game_stellarblade import StellarBladeGame

    assert StellarBladeGame.GamePakLoadOrderDirs == []
    assert StellarBladeGame.GamePakLoadOrderPrefix is False
