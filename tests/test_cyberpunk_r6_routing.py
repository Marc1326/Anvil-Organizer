"""Skript-Mods ohne r6-Ordner muessen trotzdem ankommen.

redscript, TweakXL und die Tastenbelegung lesen ausschliesslich unter
``r6``. Viele Nexus-Pakete beginnen aber direkt mit ``scripts/`` oder
``tweaks/`` -- Anvil legte sie dann 1:1 ins Spielhauptverzeichnis, wo kein
Loader hinschaut. Die Mods waren installiert, aktiv, sichtbar, und im
Spiel trotzdem wirkungslos.

Gemessen an Marcs Installation: 20 von 356 aktiven Mods traf das.
"""

from pathlib import Path

from anvil.core.mod_deployer import (
    has_deploy_anchor,
    route_deploy_path,
    strip_deploy_prefixes,
)
from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game

CP = Cyberpunk2077Game()


def _ziel(pfad: str) -> str:
    """Bildet den Weg des Deployers nach: Anker pruefen, sonst routen."""
    rel = strip_deploy_prefixes(Path(pfad), CP.GameDeployStripPrefixes)
    if has_deploy_anchor(rel, CP.GameDeployAnchors):
        return str(rel)
    return str(route_deploy_path(rel, CP.GameDeployRoutes))


# ── Die Fehlerfaelle aus Marcs Mod-Liste ─────────────────────────────


def test_redscript_kommt_unter_r6() -> None:
    # Hacking Gets Tedious, Smarter Scrapper, LawlessAreas ...
    assert _ziel("scripts/smarterScrapper.reds") == "r6/scripts/smarterScrapper.reds"


def test_unterordner_bleiben_erhalten() -> None:
    # Kiroshi Crowd Scanner: die Skripte importieren sich ueber ihren
    # Pfad. Flachlegen wuerde die Mod zerlegen.
    assert _ziel("scripts/backgroundScanner/Util/String.reds") == (
        "r6/scripts/backgroundScanner/Util/String.reds"
    )


def test_tweaks_kommen_unter_r6() -> None:
    # Unlock Me The Mods, Existing Consumable, Realistic - FuturFit 2077
    assert _ziel("tweaks/MoreInventoryFilters.yaml") == "r6/tweaks/MoreInventoryFilters.yaml"
    assert _ziel("tweaks/Tduality/retrievable_scopes.tweak") == (
        "r6/tweaks/Tduality/retrievable_scopes.tweak"
    )


def test_tastenbelegung_kommt_unter_r6() -> None:
    # Immersive Timeskip, Mark To Sell
    assert _ziel("input/MarkToSell.xml") == "r6/input/MarkToSell.xml"


def test_skript_einstellungen_kommen_unter_r6() -> None:
    # Status Bar Bug Fixes bringt alle drei Sorten auf einmal mit.
    assert _ziel("config/redsUserHints/StatusBarBugFixes.toml") == (
        "r6/config/redsUserHints/StatusBarBugFixes.toml"
    )


# ── Was unangetastet bleiben muss ────────────────────────────────────


def test_richtig_gepacktes_paket_bleibt_wie_es_ist() -> None:
    # r6 ist Anker -- die Regel darf kein zweites r6 davorsetzen.
    for pfad in (
        "r6/scripts/meinmod.reds",
        "r6/tweaks/meinmod.yaml",
        "r6/input/meinmod.xml",
        "r6/config/redsUserHints/meinmod.toml",
    ):
        assert _ziel(pfad) == pfad, pfad


def test_gleichnamiger_ordner_weiter_unten_zaehlt_nicht() -> None:
    # Das Archiv bringt seine Struktur selbst mit; ein "scripts" tief
    # darin darf den Pfad nicht nach r6 umbiegen.
    assert _ziel("archive/pc/mod/scripts/foo.archive") == "archive/pc/mod/scripts/foo.archive"


def test_ordner_ohne_anker_und_ohne_kopftreffer_bleibt_liegen() -> None:
    # Ein Unterordner namens scripts unterhalb eines Mod-Ordners ist kein
    # fehlendes r6 -- da griff frueher das lose "folders"-Kriterium.
    assert _ziel("MeinPaket/scripts/foo.reds") == "MeinPaket/scripts/foo.reds"


def test_datei_die_scripts_heisst_ist_kein_ordner() -> None:
    assert _ziel("scripts") == "scripts"


def test_archivregel_gilt_weiterhin() -> None:
    assert _ziel("00_VTK_Gothic_Tattoo_by_Caz.archive") == (
        "archive/pc/mod/00_VTK_Gothic_Tattoo_by_Caz.archive"
    )


def test_andere_bereiche_werden_nicht_umgebogen() -> None:
    for pfad in (
        "bin/x64/plugins/cyber_engine_tweaks/mods/meinmod/init.lua",
        "red4ext/plugins/meinplugin/plugin.dll",
        "mods/meinredmod/info.json",
        "engine/config/platform/pc/foo.ini",
    ):
        assert _ziel(pfad) == pfad, pfad


# ── Zusammenspiel mit dem Deployer ───────────────────────────────────


def test_deployer_legt_das_skript_wirklich_unter_r6(tmp_path: Path) -> None:
    from anvil.core.mod_deployer import ModDeployer
    from anvil.core.mod_list_io import write_active_mods, write_global_modlist

    inst = tmp_path / "instanz"
    spiel = tmp_path / "spiel"
    spiel.mkdir(parents=True)
    quelle = inst / ".mods" / "Smarter Scrapper" / "scripts"
    quelle.mkdir(parents=True)
    (quelle / "smarterScrapper.reds").write_text("// mod", encoding="utf-8")

    profile = inst / ".profiles"
    (profile / "Default").mkdir(parents=True)
    write_global_modlist(profile, ["Smarter Scrapper"])
    write_active_mods(profile / "Default", {"Smarter Scrapper"})

    ModDeployer(
        inst, spiel,
        mods_path=inst / ".mods",
        profiles_path=profile,
        deploy_anchors=CP.GameDeployAnchors,
        deploy_routes=CP.GameDeployRoutes,
    ).deploy()

    assert (spiel / "r6" / "scripts" / "smarterScrapper.reds").exists(), (
        "redscript liest nur unter r6"
    )
    assert not (spiel / "scripts").exists(), (
        "im Hauptverzeichnis schaut kein Loader nach"
    )
