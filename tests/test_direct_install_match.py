"""Anzeige und Deployer muessen dieselbe Frage gleich beantworten.

Der Deployer prueft, ob eine Mod ein Framework ist -- Frameworks werden
unabhaengig vom Profil ausgerollt. Lange stand dort ein blosses
"enthaelt": jede Mod mit "ArchiveXL" im Namen galt als Framework und
landete im Spiel, obwohl sie abgeschaltet war. In der Liste sah sie
normal aus, denn dort wurde bereits richtig geprueft.
"""

from anvil.core.mod_deployer import ModDeployer, matches_direct_install
from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game

MUSTER = [p.lower() for p in Cyberpunk2077Game.GameDirectInstallMods]


def test_kleidungsmod_mit_archivexl_im_namen_ist_kein_framework() -> None:
    # Der Fall aus der Praxis: beide wurden ausgerollt, obwohl im Profil
    # kein einziger echter Mod aktiviert war.
    for name in (
        "MONSTERaider - Hollow Bra ArchiveXL (Regular)",
        "Vanilla Booty Boxer Shorts - ArchiveXL",
    ):
        assert not matches_direct_install(name.lower(), MUSTER), name


def test_echte_frameworks_werden_weiter_erkannt() -> None:
    for name in ("ArchiveXL", "TweakXL 1.10.9", "CET 1.37.1 - Scripting fixes",
                 "RED4ext", "redscript", "Codeware"):
        assert matches_direct_install(name.lower(), MUSTER), name


def test_cet_npc_body_tweaks_bleibt_eine_gewoehnliche_mod() -> None:
    # Der Grund, warum die Anzeige seinerzeit auf "beginnt mit" umgestellt
    # wurde -- ohne das waere "CET" auf diesen Namen gesprungen.
    assert not matches_direct_install("cet npc body tweaks", MUSTER)


def test_jb_ist_kein_direktinstall() -> None:
    # JB steht im Framework-Bereich, aber nicht in GameDirectInstallMods.
    # Es wird also nur geladen, wenn es im Profil aktiviert ist.
    assert not matches_direct_install("jb tpp fork", MUSTER)
    assert "JB TPP Fork" not in Cyberpunk2077Game.GameDirectInstallMods


def test_deployer_nutzt_dieselbe_pruefung(tmp_path) -> None:
    deployer = ModDeployer(
        tmp_path / "inst", tmp_path / "game",
        direct_install_patterns=Cyberpunk2077Game.GameDirectInstallMods,
    )

    assert deployer.is_direct_install("ArchiveXL") is True
    assert deployer.is_direct_install("Vanilla Booty Boxer Shorts - ArchiveXL") is False


def test_anzeige_und_deployer_teilen_sich_die_funktion() -> None:
    # Zwei Kopien derselben Regel laufen frueher oder spaeter auseinander.
    import anvil.mainwindow as mw

    assert mw._matches_direct_install is matches_direct_install
