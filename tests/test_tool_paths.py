"""Werkzeuge aus dem Mod-Ordner auf ihren ausgerollten Ort umbiegen.

Hintergrund: BodySlide und Co. lesen ihre Daten neben sich. Aus
``.mods/<Mod>/`` gestartet sehen sie nur die eigene Mod.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.core.tool_paths import deployed_tool_path, resolve_tool_entry


BODYSLIDE = "CalienteTools/BodySlide/BodySlide.exe"


@pytest.fixture
def welt(tmp_path: Path):
    inst = tmp_path / "instanz"
    mods = inst / ".mods"
    game = tmp_path / "Skyrim Special Edition"
    (mods / "BodySlide" / "CalienteTools" / "BodySlide").mkdir(parents=True)
    (mods / "BodySlide" / BODYSLIDE).write_text("x")
    (game / "Data").mkdir(parents=True)
    return inst, mods, game


def _args(inst, mods, game, **extra):
    basis = {
        "instance_path": inst,
        "mods_path": mods,
        "game_path": game,
        "data_path": "Data",
    }
    basis.update(extra)
    return basis


def _manifest(inst: Path, eintraege: list[dict], game: Path) -> None:
    (inst / ".deploy_manifest.json").write_text(
        json.dumps({"game_path": str(game), "symlinks": eintraege}),
        encoding="utf-8",
    )


# ── Der Regelfall ────────────────────────────────────────────────────


def test_bethesda_werkzeug_landet_unter_data(welt):
    inst, mods, game = welt
    exe = mods / "BodySlide" / BODYSLIDE
    assert deployed_tool_path(exe, **_args(inst, mods, game)) == (
        game / "Data" / BODYSLIDE
    )


def test_ohne_datenordner_bleibt_der_pfad_flach(welt):
    """Cyberpunk & Co. haben kein Data/ -- da darf nichts eingeschoben werden."""
    inst, mods, game = welt
    exe = mods / "BodySlide" / "bin" / "x64" / "werkzeug.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("x")
    ziel = deployed_tool_path(exe, **_args(inst, mods, game, data_path=""))
    assert ziel == game / "bin" / "x64" / "werkzeug.exe"


def test_umleitung_aus_dem_plugin_wird_angewendet(welt):
    """Witcher 3: ``bin/`` geht an ``Mods/`` vorbei, direkt in die Spielwurzel."""
    inst, mods, game = welt
    exe = mods / "Werkzeuge" / "bin" / "loot.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("x")
    ziel = deployed_tool_path(
        exe,
        **_args(
            inst, mods, game,
            data_path="Mods",
            multi_folder_routes={"mods": "Mods", "dlc": "DLC", "bin": "bin"},
        ),
    )
    assert ziel == game / "bin" / "loot.exe"


# ── Schreibweise (haengt an #106) ────────────────────────────────────


def test_vorhandene_schreibweise_im_spiel_gewinnt(welt):
    """Liegt im Spiel schon ``data/calientetools``, muss das Werkzeug dorthin."""
    inst, mods, game = welt
    (game / "Data").rmdir()
    (game / "data" / "calientetools" / "BodySlide").mkdir(parents=True)
    exe = mods / "BodySlide" / BODYSLIDE
    ziel = deployed_tool_path(exe, **_args(inst, mods, game))
    assert ziel == game / "data" / "calientetools" / "BodySlide" / "BodySlide.exe"


# ── Grenzen: hier wird nichts angefasst ──────────────────────────────


def test_datei_ausserhalb_der_mods_bleibt_unberuehrt(welt):
    inst, mods, game = welt
    exe = game / "Data" / "fremd.exe"
    exe.write_text("x")
    assert deployed_tool_path(exe, **_args(inst, mods, game)) is None


def test_datei_lose_in_mods_ohne_modordner(welt):
    inst, mods, game = welt
    exe = mods / "einzeln.exe"
    exe.write_text("x")
    assert deployed_tool_path(exe, **_args(inst, mods, game)) is None


def test_ohne_mods_pfad_passiert_nichts(welt):
    inst, mods, game = welt
    exe = mods / "BodySlide" / BODYSLIDE
    assert deployed_tool_path(exe, instance_path=inst, mods_path=None, game_path=game) is None


def test_ohne_spielpfad_passiert_nichts(welt):
    inst, mods, game = welt
    exe = mods / "BodySlide" / BODYSLIDE
    assert deployed_tool_path(exe, instance_path=inst, mods_path=mods, game_path=None) is None


def test_relativer_pfad_wird_nicht_angefasst(welt):
    inst, mods, game = welt
    assert deployed_tool_path(Path("BodySlide/x.exe"), **_args(inst, mods, game)) is None


# ── Das Manifest schlaegt die Rechnung ───────────────────────────────


def test_manifest_gewinnt_gegen_die_rechnung(welt):
    """Im Manifest steht, wo die Datei wirklich liegt -- inklusive Sonderwege."""
    inst, mods, game = welt
    exe = mods / "BodySlide" / BODYSLIDE
    _manifest(inst, [{"target": str(exe), "link": "Anderswo/BodySlide.exe"}], game)
    assert deployed_tool_path(exe, **_args(inst, mods, game)) == (
        game / "Anderswo" / "BodySlide.exe"
    )


def test_eigenes_trennerziel_schlaegt_den_spielordner(welt, tmp_path):
    inst, mods, game = welt
    anderes = tmp_path / "woanders"
    exe = mods / "BodySlide" / BODYSLIDE
    _manifest(
        inst,
        [{"target": str(exe), "link": "x.exe", "deploy_base": str(anderes)}],
        game,
    )
    assert deployed_tool_path(exe, **_args(inst, mods, game)) == anderes / "x.exe"


def test_fremder_eintrag_im_manifest_wird_uebergangen(welt):
    inst, mods, game = welt
    exe = mods / "BodySlide" / BODYSLIDE
    _manifest(inst, [{"target": "/ganz/woanders.exe", "link": "falsch.exe"}], game)
    assert deployed_tool_path(exe, **_args(inst, mods, game)) == (
        game / "Data" / BODYSLIDE
    )


def test_kaputtes_manifest_faellt_auf_die_rechnung_zurueck(welt):
    inst, mods, game = welt
    (inst / ".deploy_manifest.json").write_text("{kein json", encoding="utf-8")
    exe = mods / "BodySlide" / BODYSLIDE
    assert deployed_tool_path(exe, **_args(inst, mods, game)) == (
        game / "Data" / BODYSLIDE
    )


def test_manifest_als_liste_statt_objekt(welt):
    inst, mods, game = welt
    (inst / ".deploy_manifest.json").write_text("[]", encoding="utf-8")
    exe = mods / "BodySlide" / BODYSLIDE
    assert deployed_tool_path(exe, **_args(inst, mods, game)) == (
        game / "Data" / BODYSLIDE
    )


# ── Der gespeicherte Eintrag ─────────────────────────────────────────


def _rolle_aus(game: Path) -> Path:
    """Das Werkzeug so ins Spiel legen, wie der Deployer es taete."""
    ziel = game / "Data" / BODYSLIDE
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text("x")
    return ziel


def test_arbeitsordner_wandert_mit(welt):
    inst, mods, game = welt
    ziel = _rolle_aus(game)
    exe = mods / "BodySlide" / BODYSLIDE
    neu, cwd = resolve_tool_entry(str(exe), str(exe.parent), **_args(inst, mods, game))
    assert neu == str(ziel)
    assert cwd == str(ziel.parent)


def test_leerer_arbeitsordner_wird_gefuellt(welt):
    inst, mods, game = welt
    ziel = _rolle_aus(game)
    exe = mods / "BodySlide" / BODYSLIDE
    _neu, cwd = resolve_tool_entry(str(exe), "", **_args(inst, mods, game))
    assert cwd == str(ziel.parent)


def test_selbst_gesetzter_arbeitsordner_bleibt_stehen(welt, tmp_path):
    inst, mods, game = welt
    _rolle_aus(game)
    exe = mods / "BodySlide" / BODYSLIDE
    eigener = str(tmp_path / "eigener")
    _neu, cwd = resolve_tool_entry(str(exe), eigener, **_args(inst, mods, game))
    assert cwd == eigener


def test_nicht_ausgerollt_bleibt_beim_alten_pfad(welt):
    """Mod abgeschaltet: dann startet wenigstens noch der Pfad in .mods/."""
    inst, mods, game = welt
    exe = mods / "BodySlide" / BODYSLIDE
    assert not (game / "Data" / BODYSLIDE).exists()
    assert resolve_tool_entry(str(exe), "", **_args(inst, mods, game)) == (str(exe), "")


def test_eintrag_ausserhalb_der_mods_bleibt_unveraendert(welt):
    inst, mods, game = welt
    fremd = str(game / "Data" / "fremd.exe")
    assert resolve_tool_entry(fremd, "", **_args(inst, mods, game)) == (fremd, "")


def test_leerer_eintrag_stuerzt_nicht_ab(welt):
    inst, mods, game = welt
    assert resolve_tool_entry("", "", **_args(inst, mods, game)) == ("", "")
