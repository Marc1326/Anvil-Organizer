"""Presets, die im Mod-Ordner am falschen Platz liegen.

Der Fall "Bad Corpo": die Preset-Datei liegt in der Ordnerwurzel statt
unter dem ACU-Zielpfad. Beim Ausrollen landet sie im Spielhauptordner,
wo das Framework nie danach sucht -- die Mod ist aktiv und wirkt doch
nicht. Anvil soll das erkennen und auf Zuruf geraderuecken.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.core.character_presets import (
    FEMALE,
    detect_variant,
    fix_stray_path,
    is_preset_mod,
    kind_for,
    stray_presets,
)
from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game as CP

ARTEN = CP().get_preset_kinds()
ACU = ARTEN[0]
ZIEL = ACU.target


# ── Erkennung ────────────────────────────────────────────────────────


def test_bad_corpo_wird_gefunden() -> None:
    assert stray_presets(
        ["Bad Corpo.preset", "meta.ini"], ARTEN,
    ) == ["Bad Corpo.preset"]


def test_richtig_einsortiertes_preset_ist_kein_fund() -> None:
    assert stray_presets([f"{ZIEL}/female/Grace.preset", "meta.ini"], ARTEN) == []


def test_femv_re9_grace_wird_nicht_gemeldet() -> None:
    """Der Mod heisst nur "FacePreset" -- drin ist ein Archiv.

    Wuerde er gemeldet, schickte Anvil Marc hinter einem Fehler her,
    den es nicht gibt.
    """
    assert stray_presets(
        ["archive/pc/mod/00_FacePreset_RE9Grace_xBaebsae.archive", "meta.ini"],
        ARTEN,
    ) == []


def test_nebensachen_loesen_nichts_aus() -> None:
    assert stray_presets(
        ["meta.ini", "codes.txt", "fomod_choices.json", ".hidden"], ARTEN,
    ) == []


def test_grossschreibung_und_backslash() -> None:
    assert stray_presets(["Ordner\\BAD CORPO.PRESET"], ARTEN) == [
        "Ordner/BAD CORPO.PRESET"]


def test_spiel_ohne_presets_findet_nie_etwas() -> None:
    assert stray_presets(["Bad Corpo.preset"], []) == []


def test_aehnlich_benannter_ordner_zaehlt_als_verirrt() -> None:
    """Nur der echte Zielpfad zaehlt, kein Ordner der so aehnlich heisst."""
    assert stray_presets([f"{ZIEL}-backup/female/x.preset"], ARTEN) == [
        f"{ZIEL}-backup/female/x.preset"]


def test_mehrere_funde_bleiben_in_reihenfolge() -> None:
    assert stray_presets(["b.preset", "unterordner/a.preset"], ARTEN) == [
        "b.preset", "unterordner/a.preset"]


def test_kind_for_findet_die_art() -> None:
    assert kind_for("Bad Corpo.preset", ARTEN) is ACU
    assert kind_for("irgendwas.archive", ARTEN) is None


# ── Variante aus dem Inhalt ──────────────────────────────────────────


def _weiblich_datei(tmp_path: Path) -> Path:
    """Zwei weibliche Marker, kein maennlicher -- wie bei Bad Corpo."""
    marker = ACU.markers[FEMALE][:2]
    p = tmp_path / "Bad Corpo.preset"
    p.write_text("\n".join(f"{m}:0" for m in marker), encoding="utf-8")
    return p


def test_variante_kommt_aus_dem_inhalt(tmp_path: Path) -> None:
    assert detect_variant(_weiblich_datei(tmp_path), ACU) == FEMALE


# ── Geraderuecken ────────────────────────────────────────────────────


def test_datei_landet_am_zielpfad(tmp_path: Path) -> None:
    mod = tmp_path / "Bad Corpo"
    mod.mkdir()
    (mod / "meta.ini").write_text("[General]\n", encoding="utf-8")
    (mod / "Bad Corpo.preset").write_text("x", encoding="utf-8")

    neu = fix_stray_path(mod, "Bad Corpo.preset", ACU, FEMALE)

    assert neu == mod / ZIEL / "female" / "Bad Corpo.preset"
    assert neu.is_file()
    assert not (mod / "Bad Corpo.preset").exists()
    assert sorted(p.name for p in mod.iterdir()) == ["bin", "meta.ini"]


def test_belegtes_ziel_laesst_die_quelle_in_ruhe(tmp_path: Path) -> None:
    mod = tmp_path / "Bad Corpo"
    (mod / ZIEL / "female").mkdir(parents=True)
    (mod / ZIEL / "female" / "Bad Corpo.preset").write_text("alt", encoding="utf-8")
    (mod / "Bad Corpo.preset").write_text("neu", encoding="utf-8")

    with pytest.raises(FileExistsError):
        fix_stray_path(mod, "Bad Corpo.preset", ACU, FEMALE)

    assert (mod / "Bad Corpo.preset").read_text(encoding="utf-8") == "neu"
    assert (mod / ZIEL / "female" / "Bad Corpo.preset").read_text(
        encoding="utf-8") == "alt"


def test_fehlende_quelle_meldet_sich(tmp_path: Path) -> None:
    mod = tmp_path / "Bad Corpo"
    mod.mkdir()
    with pytest.raises(FileNotFoundError):
        fix_stray_path(mod, "gibtsnicht.preset", ACU, FEMALE)


def test_nach_der_reparatur_ist_es_ein_preset_mod(tmp_path: Path) -> None:
    """Erst dann wandert die Mod wirklich in den Presets-Bereich."""
    mod = tmp_path / "Bad Corpo"
    mod.mkdir()
    (mod / "Bad Corpo.preset").write_text("x", encoding="utf-8")
    (mod / "meta.ini").write_text("[General]\n", encoding="utf-8")

    assert not is_preset_mod(["Bad Corpo.preset", "meta.ini"], ARTEN)

    fix_stray_path(mod, "Bad Corpo.preset", ACU, FEMALE)
    danach = [
        str(p.relative_to(mod)) for p in mod.rglob("*") if p.is_file()
    ]
    assert is_preset_mod(danach, ARTEN)
    assert stray_presets(danach, ARTEN) == []


# ── Durchstich mit dem echten Deployer ───────────────────────────────


def _rolle_aus(tmp_path: Path, mod_name: str) -> Path:
    from anvil.core.mod_deployer import ModDeployer
    from anvil.core.mod_list_io import write_active_mods, write_global_modlist

    inst = tmp_path / "instanz"
    spiel = tmp_path / "spiel"
    spiel.mkdir(parents=True, exist_ok=True)
    profile = inst / ".profiles"
    (profile / "Default").mkdir(parents=True, exist_ok=True)
    write_global_modlist(profile, [mod_name])
    write_active_mods(profile / "Default", {mod_name})

    ModDeployer(
        inst, spiel,
        mods_path=inst / ".mods",
        profiles_path=profile,
        deploy_anchors=CP.GameDeployAnchors,
        deploy_routes=CP.GameDeployRoutes,
    ).deploy()
    return spiel


def test_vor_der_reparatur_landet_es_im_spielhauptordner(tmp_path: Path) -> None:
    """Der Beweis, dass es wirklich kaputt ist -- nicht nur theoretisch."""
    mod = tmp_path / "instanz" / ".mods" / "Bad Corpo"
    mod.mkdir(parents=True)
    (mod / "Bad Corpo.preset").write_text("x", encoding="utf-8")

    spiel = _rolle_aus(tmp_path, "Bad Corpo")

    assert (spiel / "Bad Corpo.preset").exists(), (
        "dort schaut ACU nie hin -- genau das ist der Fehler"
    )
    assert not (spiel / ZIEL / "female" / "Bad Corpo.preset").exists()


def test_nach_der_reparatur_landet_es_bei_acu(tmp_path: Path) -> None:
    mod = tmp_path / "instanz" / ".mods" / "Bad Corpo"
    mod.mkdir(parents=True)
    (mod / "Bad Corpo.preset").write_text("x", encoding="utf-8")

    fix_stray_path(mod, "Bad Corpo.preset", ACU, FEMALE)
    spiel = _rolle_aus(tmp_path, "Bad Corpo")

    assert (spiel / ZIEL / "female" / "Bad Corpo.preset").exists()
    assert not (spiel / "Bad Corpo.preset").exists()


# ── Sprachen ─────────────────────────────────────────────────────────

SPRACHEN = ("de", "en", "es", "fr", "it", "pt", "ru")
SCHLUESSEL = {
    ("preset", "stray_title"): (),
    ("preset", "stray_prompt"): ("{file}", "{mod}", "{kind}", "{von}", "{nach}"),
    ("preset", "stray_moved"): ("{name}",),
    ("preset", "stray_failed"): ("{error}",),
    ("preset", "stray_exists"): ("{name}",),
    ("context", "fix_preset"): (),
    ("notifications", "stray_presets"): ("{count}",),
    ("tooltip", "stray_preset"): (),
}


def test_alle_schluessel_in_allen_sprachen() -> None:
    ordner = Path(__file__).parents[1] / "anvil" / "locales"
    for sprache in SPRACHEN:
        daten = json.loads((ordner / f"{sprache}.json").read_text(encoding="utf-8"))
        for (gruppe, schluessel), platzhalter in SCHLUESSEL.items():
            text = daten.get(gruppe, {}).get(schluessel)
            assert text, f"{sprache}: {gruppe}.{schluessel} fehlt"
            for p in platzhalter:
                assert p in text, f"{sprache}: {gruppe}.{schluessel} ohne {p}"


# ── Einbau im Hauptfenster ───────────────────────────────────────────


def test_split_presets_ruft_die_erkennung_auf() -> None:
    import inspect

    from anvil.mainwindow import MainWindow

    quelle = inspect.getsource(MainWindow._split_presets)
    assert "_stray_preset_mods" in quelle
    assert "_report_stray_presets" in quelle


def test_meldung_ohne_glocke_stuerzt_nicht_ab() -> None:
    """Beim ersten Start steht die Glocke noch nicht.

    Genau daran ist der Instanz-Aufbau schon einmal gescheitert: die
    Meldung warf einen AttributeError, der Aufbau brach ab, und die
    Mod-Liste blieb leer.
    """
    from anvil.mainwindow import MainWindow

    class _Instanzen:
        def current_instance(self):
            return "Testinstanz"

    class _OhneGlocke:
        _report_stray_presets = MainWindow._report_stray_presets

        def __init__(self):
            self._stray_preset_namen = {}
            self.instance_manager = _Instanzen()

    fenster = _OhneGlocke()
    fenster._report_stray_presets({"Bad Corpo": ["Bad Corpo.preset"]})

    # Nichts gemerkt -- sonst kaeme die Meldung nie mehr.
    assert fenster._stray_preset_namen == {}


def test_glocke_steht_vor_dem_instanz_aufbau() -> None:
    """Reihenfolge im Aufbau, nicht nur Absturzsicherheit."""
    import inspect

    from anvil.mainwindow import MainWindow

    quelle = inspect.getsource(MainWindow.__init__)
    glocke = quelle.index("self._notification_center = NotificationCenter")
    laden = quelle.index("self._check_first_start()")
    assert glocke < laden, (
        "Die Glocke muss stehen, bevor die erste Instanz geladen wird"
    )


def test_kontextmenue_haengt_am_richtigen_schluessel() -> None:
    import inspect

    from anvil.mainwindow import MainWindow

    quelle = inspect.getsource(MainWindow)
    assert 'tr("context.fix_preset")' in quelle
    assert "_fix_stray_preset" in quelle
