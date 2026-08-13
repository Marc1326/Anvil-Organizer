"""Der Auffang-Trenner: wo Zugaenge landen, wenn niemand sie einsortiert.

Frueher haengte Anvil alles ans Ende der Datei -- und damit unter den
letzten Trenner, egal wie der hiess. Bei Marc war das der Presets-Trenner,
der dadurch 10 Frameworks und zwei fremde Mods eingesammelt hat.
"""

from __future__ import annotations

import json
from pathlib import Path

from anvil.core.mod_entry import scan_mods_directory
from anvil.core.mod_list_io import (
    catch_all_position,
    read_global_modlist,
    write_global_modlist,
)

SAMMLER = "Nicht einsortiert_separator"


# ── catch_all_position ───────────────────────────────────────────────


def test_ohne_trenner_ans_ende() -> None:
    order = ["a_separator", "Mod A", "b_separator", "Mod B"]
    assert catch_all_position(order, "") == 4


def test_unbekannter_trenner_ans_ende() -> None:
    order = ["a_separator", "Mod A"]
    assert catch_all_position(order, SAMMLER) == 2


def test_hinter_den_trenner_wenn_er_leer_ist() -> None:
    order = ["a_separator", "Mod A", SAMMLER]
    assert catch_all_position(order, SAMMLER) == 3


def test_hinter_die_bisherigen_kinder() -> None:
    order = [SAMMLER, "Neu 1", "Neu 2", "z_separator", "Mod Z"]
    assert catch_all_position(order, SAMMLER) == 3


def test_nicht_ueber_den_naechsten_trenner_hinaus() -> None:
    """Der Sammler steht mitten in der Liste -- Zugaenge bleiben bei ihm."""
    order = ["a_separator", "Mod A", SAMMLER, "Neu 1", "z_separator", "Mod Z"]
    pos = catch_all_position(order, SAMMLER)
    assert pos == 4
    order.insert(pos, "Zugang")
    assert order.index("Zugang") < order.index("z_separator")


# ── scan_mods_directory ──────────────────────────────────────────────


def _instanz(tmp_path: Path, ordner: list[str], liste: list[str]) -> tuple[Path, Path]:
    mods = tmp_path / ".mods"
    profiles = tmp_path / ".profiles"
    profil = profiles / "Default"
    profil.mkdir(parents=True)
    for name in ordner:
        (mods / name).mkdir(parents=True)
    write_global_modlist(profiles, liste)
    (profil / "active_mods.json").write_text(
        json.dumps(sorted(liste)), encoding="utf-8",
    )
    return tmp_path, profil


def _namen(tmp_path: Path, profil: Path, catch_all: str = "") -> list[str]:
    eintraege = scan_mods_directory(
        tmp_path, profil,
        mods_path=tmp_path / ".mods",
        profiles_path=tmp_path / ".profiles",
        catch_all=catch_all,
    )
    return [e.name for e in eintraege]


def test_zugang_landet_beim_sammler_statt_beim_letzten_trenner(tmp_path: Path) -> None:
    """Der eigentliche Fall: ein Ordner ohne Listeneintrag."""
    inst, profil = _instanz(
        tmp_path,
        ordner=["a_separator", "Mod A", SAMMLER, "Presets_separator", "Preset 1", "Zugang"],
        liste=["a_separator", "Mod A", SAMMLER, "Presets_separator", "Preset 1"],
    )
    namen = _namen(inst, profil, catch_all=SAMMLER)

    assert namen.index("Zugang") == namen.index(SAMMLER) + 1
    assert namen.index("Zugang") < namen.index("Presets_separator")


def test_ohne_sammler_bleibt_es_beim_alten_verhalten(tmp_path: Path) -> None:
    inst, profil = _instanz(
        tmp_path,
        ordner=["a_separator", "Mod A", "Presets_separator", "Preset 1", "Zugang"],
        liste=["a_separator", "Mod A", "Presets_separator", "Preset 1"],
    )
    namen = _namen(inst, profil)
    assert namen[-1] == "Zugang"


def test_mutationsprobe_sammler_ignorieren_faellt_auf(tmp_path: Path) -> None:
    """Ersetzt man die Zielposition durch len(order), muss es auffallen.

    Ohne diese Probe koennte die Zielposition still auf "ans Ende"
    zurueckfallen und alle uebrigen Tests blieben gruen.
    """
    inst, profil = _instanz(
        tmp_path,
        ordner=[SAMMLER, "Presets_separator", "Preset 1", "Zugang"],
        liste=[SAMMLER, "Presets_separator", "Preset 1"],
    )
    mit = _namen(inst, profil, catch_all=SAMMLER)
    ohne = _namen(inst, profil)

    assert mit != ohne
    assert mit[-1] == "Preset 1"
    assert ohne[-1] == "Zugang"


def test_zugang_bleibt_aktiv(tmp_path: Path) -> None:
    """Zugaenge waren schon immer standardmaessig aktiv -- das bleibt."""
    inst, profil = _instanz(
        tmp_path,
        ordner=[SAMMLER, "Zugang"],
        liste=[SAMMLER],
    )
    eintraege = scan_mods_directory(
        inst, profil,
        mods_path=inst / ".mods",
        profiles_path=inst / ".profiles",
        catch_all=SAMMLER,
    )
    zugang = next(e for e in eintraege if e.name == "Zugang")
    assert zugang.enabled


def test_ausgeblendete_zugaenge_bleiben_draussen(tmp_path: Path) -> None:
    """include_external=False darf der Sammler nicht aushebeln."""
    inst, profil = _instanz(
        tmp_path,
        ordner=[SAMMLER, "Zugang"],
        liste=[SAMMLER],
    )
    eintraege = scan_mods_directory(
        inst, profil,
        include_external=False,
        mods_path=inst / ".mods",
        profiles_path=inst / ".profiles",
        catch_all=SAMMLER,
    )
    assert [e.name for e in eintraege] == [SAMMLER]


def test_kein_eintrag_geht_verloren(tmp_path: Path) -> None:
    ordner = [
        "a_separator", "Mod A", "Mod B", SAMMLER,
        "Presets_separator", "Preset 1", "Zugang 1", "Zugang 2",
    ]
    inst, profil = _instanz(
        tmp_path, ordner=ordner,
        liste=["a_separator", "Mod A", "Mod B", SAMMLER, "Presets_separator", "Preset 1"],
    )
    namen = _namen(inst, profil, catch_all=SAMMLER)
    assert sorted(namen) == sorted(ordner)
    assert len(namen) == len(set(namen))


def test_geloeschte_mods_fallen_weiter_raus(tmp_path: Path) -> None:
    inst, profil = _instanz(
        tmp_path,
        ordner=[SAMMLER, "Mod A"],
        liste=[SAMMLER, "Mod A", "Von der Platte weg"],
    )
    assert "Von der Platte weg" not in _namen(inst, profil, catch_all=SAMMLER)


def test_prioritaet_bleibt_luecklos(tmp_path: Path) -> None:
    inst, profil = _instanz(
        tmp_path,
        ordner=["a_separator", "Mod A", SAMMLER, "Zugang"],
        liste=["a_separator", "Mod A", SAMMLER],
    )
    eintraege = scan_mods_directory(
        inst, profil,
        mods_path=inst / ".mods",
        profiles_path=inst / ".profiles",
        catch_all=SAMMLER,
    )
    assert [e.priority for e in eintraege] == list(range(len(eintraege)))


# ── Sammlungs-Import ─────────────────────────────────────────────────


def test_sammlung_haengt_uebriges_an_den_sammler(tmp_path: Path) -> None:
    """Was die Sammlung nicht kennt, gehoert nicht unter den Preset-Trenner."""
    from anvil.core.collection_io import CollectionManifest, CollectionMod, apply_collection

    inst, profil = _instanz(
        tmp_path,
        ordner=[SAMMLER, "Presets_separator", "Preset 1", "Eigene Mod"],
        liste=[SAMMLER, "Presets_separator", "Preset 1", "Eigene Mod"],
    )
    manifest = CollectionManifest(
        collection_name="Test",
        mods=[
            CollectionMod(name=SAMMLER, enabled=True, is_separator=True),
            CollectionMod(name="Presets_separator", enabled=True, is_separator=True),
            CollectionMod(name="Preset 1", enabled=True),
        ],
    )
    apply_collection(
        manifest=manifest,
        instance_path=inst,
        profile_path=profil,
        apply_categories=False,
        mods_path=inst / ".mods",
        profiles_path=inst / ".profiles",
        catch_all=SAMMLER,
    )
    order = read_global_modlist(inst / ".profiles")
    assert order.index("Eigene Mod") < order.index("Presets_separator")
    assert order.index("Eigene Mod") == order.index(SAMMLER) + 1
