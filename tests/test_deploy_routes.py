"""Stellar Blade kennt vier Mod-Arten mit vier Zielen.

Pak-Mods gehoeren nach ``Content/Paks/~mods``, Logic-Mods nach
``Content/Paks/LogicMods``, Filmsequenzen nach ``Content/Movies`` und die
CNS-Beschreibungen in ihren eigenen Unterordner.  Landet eine Datei im
falschen Ordner, wirkt die Mod nicht -- ohne Fehlermeldung.
"""

from pathlib import Path

import struct

from anvil.core.mod_deployer import (
    ModDeployer,
    has_deploy_anchor,
    route_deploy_path,
    strip_deploy_prefixes,
    unreal_mount_point,
)
from anvil.core.mod_list_io import write_active_mods, write_global_modlist
from anvil.plugins.games.game_stellarblade import StellarBladeGame

SB = StellarBladeGame


def _ziel(rel: str, mount: str = "") -> str:
    """Fahrt die Routenlogik des Plugins ueber einen Mod-Pfad."""
    p = strip_deploy_prefixes(Path(rel), SB.GameDeployStripPrefixes)
    if not has_deploy_anchor(p, SB.GameDeployAnchors):
        p = route_deploy_path(p, SB.GameDeployRoutes, mount)
    return str(p).replace("\\", "/")


def _utoc(ziel: Path, mount: str) -> None:
    """Schreibt einen IoStore-Kopf mit gesetztem Mount-Point."""
    roh = mount.encode() + b"\0"
    kopf = bytearray(144)
    kopf[0:16] = b"-==--==--==--==-"
    kopf[16] = 3
    struct.pack_into("<II", kopf, 20, 144, 0)          # Kopfgroesse, Eintraege
    struct.pack_into("<6I", kopf, 28, 0, 0, 0, 0, 0, 4 + len(roh))
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(bytes(kopf) + struct.pack("<i", len(roh)) + roh)


# ── Die Bausteine ──────────────────────────────────────────────────────

def test_mod_art_ordner_faellt_weg() -> None:
    assert strip_deploy_prefixes(Path("~mods/Foo_P.pak"), ["~mods"]) == Path("Foo_P.pak")


def test_doppelt_verpacktes_archiv() -> None:
    got = strip_deploy_prefixes(Path("~mods/~mods/Foo_P.pak"), ["~mods"])
    assert got == Path("Foo_P.pak")


def test_letzter_teil_bleibt_stehen() -> None:
    """Eine Datei, die selbst so heisst, darf nicht verschwinden."""
    assert strip_deploy_prefixes(Path("~mods"), ["~mods"]) == Path("~mods")


def test_anker_erkennt_eigene_struktur() -> None:
    assert has_deploy_anchor(Path("Content/Paks/LogicMods/X_P.pak"), ["Content"])
    assert not has_deploy_anchor(Path("X_P.pak"), ["Content"])


# ── Die vier Mod-Arten ─────────────────────────────────────────────────

def test_pak_mod_geht_in_mods() -> None:
    assert _ziel("TypeB_KITSUNE_P.pak") == "Content/Paks/~mods/TypeB_KITSUNE_P.pak"
    assert _ziel("TypeB_KITSUNE_P.utoc") == "Content/Paks/~mods/TypeB_KITSUNE_P.utoc"
    assert _ziel("TypeB_KITSUNE_P.ucas") == "Content/Paks/~mods/TypeB_KITSUNE_P.ucas"


def test_logic_mod_behaelt_seinen_ordner() -> None:
    """Die Mod-Autoren sind da eindeutig: NICHT nach ~mods."""
    rel = "Content/Paks/LogicMods/Menu_Randomiser_P.pak"
    assert _ziel(rel) == rel


def test_menue_video_geht_in_den_menu_ordner() -> None:
    """Der Video-Randomiser sucht dort nach menu_0, menu_1 und so fort."""
    assert _ziel("menu_0.bk2") == "Content/Movies/Menu/menu_0.bk2"
    assert _ziel("menu_12.webm") == "Content/Movies/Menu/menu_12.webm"


def test_menue_video_auch_mit_eigenem_ordner() -> None:
    """Das Archiv bringt oft schon einen menu-Ordner mit."""
    assert _ziel("menu/menu_0.bk2") == "Content/Movies/Menu/menu_0.bk2"


def test_andere_filmsequenz_bleibt_in_movies() -> None:
    assert _ziel("EVE_Title.bk2") == "Content/Movies/EVE_Title.bk2"


def test_cns_beschreibung_geht_zum_framework() -> None:
    """Dort legt CNS auch seine eigenen Beschreibungen ab -- flach in
    ~mods findet es sie nicht."""
    got = _ziel("NakedLily Replacer.dekcns.json")
    assert got == "Content/Paks/~mods/CustomNanosuitSystem/NakedLily Replacer.dekcns.json"


def test_cns_animation_ebenso() -> None:
    got = _ziel("DekCNS-AnimationsEVE.dekani.json")
    assert got == "Content/Paks/~mods/CustomNanosuitSystem/DekCNS-AnimationsEVE.dekani.json"


def test_cns_behaelt_seinen_unterordner() -> None:
    """Gruppiert ein Mod seine Dateien selbst, bleibt das erhalten --
    der Ordner darf sich dabei nicht verdoppeln."""
    got = _ziel("~mods/CustomNanosuitSystem/Cosmetics/Faces.dekcns.json")
    assert got == "Content/Paks/~mods/CustomNanosuitSystem/Cosmetics/Faces.dekcns.json"


def test_cns_pak_bleibt_beim_eigenen_ordner() -> None:
    """Beim Beispiel-Mod liegen Pak und Beschreibung zusammen."""
    got = _ziel("~mods/CustomNanosuitSystem/DekCNS-SkinSuit_P.pak")
    assert got == "Content/Paks/~mods/CustomNanosuitSystem/DekCNS-SkinSuit_P.pak"


def test_ue4ss_zubehoer_behaelt_seinen_unterbau() -> None:
    """Flachlegen wuerde den Loader seine Mods nicht mehr finden lassen."""
    got = _ziel("ue4ss/Mods/DekCNS/Scripts/main.lua")
    assert got == "Binaries/Win64/ue4ss/Mods/DekCNS/Scripts/main.lua"


def test_archiv_mit_voller_struktur_bleibt_unangetastet() -> None:
    rel = "SB/Content/Paks/~mods/CustomNanosuitSystem/Cosmetics/x.dekcns.json"
    assert _ziel(rel) == rel


def test_unbekanntes_bleibt_liegen() -> None:
    """Kein Treffer heisst: nicht raten, Pfad so lassen."""
    assert _ziel("readme.txt") == "readme.txt"


# ── Logic-Mods am Mount-Point erkennen ─────────────────────────────────

def test_mount_point_wird_gelesen(tmp_path: Path) -> None:
    p = tmp_path / "X_P.utoc"
    _utoc(p, "../../../SB/Content/Mods/Menu_Randomiser_P/")
    assert unreal_mount_point(p) == "../../../SB/Content/Mods/Menu_Randomiser_P/"


def test_fremde_datei_liefert_keinen_mount_point(tmp_path: Path) -> None:
    p = tmp_path / "kein.utoc"
    p.write_bytes(b"nur text")
    assert unreal_mount_point(p) == ""


def test_blueprint_mod_geht_nach_logicmods() -> None:
    """Am Dateinamen nicht zu erkennen -- der Mount-Point verraet es."""
    got = _ziel("Menu_Randomiser_P.pak", "../../../SB/Content/Mods/Menu_Randomiser_P/")
    assert got == "Content/Paks/LogicMods/Menu_Randomiser_P.pak"


def test_textur_mod_bleibt_in_mods() -> None:
    got = _ziel("FoxEYE_P.pak", "../../../Head1/Content/Art/Character/PC/Textures/")
    assert got == "Content/Paks/~mods/FoxEYE_P.pak"


def test_dreiergespann_folgt_seiner_utoc(tmp_path: Path) -> None:
    """pak und ucas kennen keinen Mount-Point -- sie muessen trotzdem
    dorthin, wo ihr Inhaltsverzeichnis hingeht."""
    instance, game, mods, profiles = _welt(tmp_path)
    ordner = mods / "Logik"
    ordner.mkdir()
    _utoc(ordner / "Menu_Randomiser_P.utoc", "../../../SB/Content/Mods/Menu_Randomiser_P/")
    (ordner / "Menu_Randomiser_P.pak").write_bytes(b"x")
    (ordner / "Menu_Randomiser_P.ucas").write_bytes(b"x")
    write_global_modlist(profiles, ["Logik"])
    write_active_mods(profiles / "Default", {"Logik"})

    _deployer(instance, game).deploy()

    ziel = game / "SB/Content/Paks/LogicMods"
    assert sorted(p.name for p in ziel.iterdir()) == [
        "Menu_Randomiser_P.pak", "Menu_Randomiser_P.ucas", "Menu_Randomiser_P.utoc",
    ]
    assert not (game / "SB/Content/Paks/~mods").exists()


# ── Im echten Deploy ───────────────────────────────────────────────────

def _welt(tmp_path: Path):
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


def _deployer(instance: Path, game: Path) -> ModDeployer:
    return ModDeployer(
        instance, game,
        data_path=SB.GameDataPath,
        deploy_strip_prefixes=SB.GameDeployStripPrefixes,
        deploy_anchors=SB.GameDeployAnchors,
        deploy_routes=SB.GameDeployRoutes,
        pak_load_order_prefix=SB.GamePakLoadOrderPrefix,
    )


def test_jede_mod_art_landet_richtig(tmp_path: Path) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "Outfit", ["Kitsune_P.pak", "Kitsune_P.utoc", "Kitsune_P.ucas"])
    _mod(mods, "MenueVideo", ["menu_0.bk2"])
    _mod(mods, "MenueLogik", ["Content/Paks/LogicMods/Menu_Randomiser_P.pak"])
    _mod(mods, "CNSOutfit", ["~mods/CustomNanosuitSystem/Suit.dekcns.json"])
    namen = ["Outfit", "MenueVideo", "MenueLogik", "CNSOutfit"]
    write_global_modlist(profiles, namen)
    write_active_mods(profiles / "Default", set(namen))

    _deployer(instance, game).deploy()

    sb = game / "SB"
    assert (sb / "Content/Paks/~mods/Kitsune_P.pak").exists()
    assert (sb / "Content/Paks/~mods/Kitsune_P.utoc").exists()
    assert (sb / "Content/Movies/Menu/menu_0.bk2").exists()
    assert (sb / "Content/Paks/LogicMods/Menu_Randomiser_P.pak").exists()
    assert (sb / "Content/Paks/~mods/CustomNanosuitSystem/Suit.dekcns.json").exists()


def test_keine_zaehler_mehr_vor_den_dateinamen(tmp_path: Path) -> None:
    """Die Mod-Autoren verbieten das Umbenennen ausdruecklich."""
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "A", ["Alpha_P.pak"])
    _mod(mods, "B", ["Beta_P.pak"])
    write_global_modlist(profiles, ["A", "B"])
    write_active_mods(profiles / "Default", {"A", "B"})

    _deployer(instance, game).deploy()

    namen = sorted(p.name for p in (game / "SB/Content/Paks/~mods").iterdir())
    assert namen == ["Alpha_P.pak", "Beta_P.pak"]


def test_kein_verschachtelter_mods_ordner_mehr(tmp_path: Path) -> None:
    """Frueher wurde SB/Content/Paks/~mods vor einen Pfad gehaengt, der
    Content/Paks/~mods schon enthielt."""
    instance, game, mods, profiles = _welt(tmp_path)
    _mod(mods, "CNS", ["Content/Paks/~mods/CustomNanosuitSystem/Suit_P.pak"])
    write_global_modlist(profiles, ["CNS"])
    write_active_mods(profiles / "Default", {"CNS"})

    _deployer(instance, game).deploy()

    ziel = game / "SB/Content/Paks/~mods/CustomNanosuitSystem/Suit_P.pak"
    assert ziel.exists()
    assert not (game / "SB/Content/Paks/~mods/Content").exists()


def test_plugin_setzt_den_dll_override() -> None:
    """Ohne dwmapi-Override startet UE4SS unter Proton nie."""
    assert SB.GameProtonDllOverrides.get("dwmapi") == "native,builtin"
