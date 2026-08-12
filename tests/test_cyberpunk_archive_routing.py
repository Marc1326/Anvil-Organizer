"""Nackte .archive-Dateien muessen nach archive/pc/mod.

Manche Nexus-Pakete enthalten nur die Archivdatei, ohne Ordner drumherum.
Anvil legte den Mod-Ordner dann 1:1 ins Spiel -- die Datei landete im
Hauptverzeichnis, wo REDengine sie nie einliest. Die Mod war installiert,
aktiv, und trotzdem im Spiel nicht vorhanden.
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


# ── Der Fehlerfall ───────────────────────────────────────────────────


def test_nackte_archive_landet_im_mod_ordner() -> None:
    # Genau der Fall aus dem RAR von 00_VTK_Gothic_Tattoo.
    assert _ziel("00_VTK_Gothic_Tattoo_by_Caz.archive") == (
        "archive/pc/mod/00_VTK_Gothic_Tattoo_by_Caz.archive"
    )


def test_archive_in_einem_beliebigen_unterordner_wird_flachgelegt() -> None:
    # Cyberpunk liest nur direkt in archive/pc/mod -- Unterordner ignoriert es.
    assert _ziel("Optional/foo.archive") == "archive/pc/mod/foo.archive"


def test_lose_xl_datei_kommt_mit() -> None:
    assert _ziel("mein_mod.archive.xl") == "archive/pc/mod/mein_mod.archive.xl"
    assert _ziel("nur_eine.xl") == "archive/pc/mod/nur_eine.xl"


# ── Was unangetastet bleiben muss ────────────────────────────────────


def test_richtig_gepackte_mod_bleibt_wie_sie_ist() -> None:
    assert _ziel("archive/pc/mod/foo.archive") == "archive/pc/mod/foo.archive"


def test_andere_bereiche_werden_nicht_umgebogen() -> None:
    for pfad in (
        "bin/x64/plugins/cyber_engine_tweaks/mods/meinmod/init.lua",
        "r6/scripts/meinmod.reds",
        "red4ext/plugins/meinplugin/plugin.dll",
        "mods/meinredmod/info.json",
        "engine/config/platform/pc/foo.ini",
    ):
        assert _ziel(pfad) == pfad, pfad


def test_fremde_dateien_bleiben_liegen_wo_sie_sind() -> None:
    # Keine Regel trifft zu -- der Deployer setzt dann sein Standardziel.
    assert _ziel("liesmich/hinweis.pdf") == "liesmich/hinweis.pdf"


# ── Zusammenspiel mit der Ladereihenfolge ────────────────────────────


def test_geroutete_archive_steht_in_der_reihenfolgedatei(tmp_path: Path) -> None:
    # Ohne das Routing landete sie im Hauptordner und tauchte in der
    # modlist.txt gar nicht auf -- also doppelt unsichtbar.
    from anvil.core.mod_deployer import ModDeployer
    from anvil.core.mod_list_io import write_active_mods, write_global_modlist

    inst = tmp_path / "instanz"
    spiel = tmp_path / "spiel"
    (spiel / "archive" / "pc" / "mod").mkdir(parents=True)
    (inst / ".mods" / "Tattoo").mkdir(parents=True)
    (inst / ".mods" / "Tattoo" / "00_VTK_Gothic_Tattoo_by_Caz.archive").write_bytes(b"\x00")
    profile = inst / ".profiles"
    (profile / "Default").mkdir(parents=True)
    write_global_modlist(profile, ["Tattoo"])
    write_active_mods(profile / "Default", {"Tattoo"})

    ModDeployer(
        inst, spiel,
        mods_path=inst / ".mods",
        profiles_path=profile,
        deploy_anchors=CP.GameDeployAnchors,
        deploy_routes=CP.GameDeployRoutes,
        archive_load_order_file=CP.GameArchiveLoadOrderFile,
    ).deploy()

    ziel = spiel / "archive" / "pc" / "mod" / "00_VTK_Gothic_Tattoo_by_Caz.archive"
    assert ziel.exists(), "die Archivdatei muss im Mod-Ordner ankommen"
    assert not (spiel / "00_VTK_Gothic_Tattoo_by_Caz.archive").exists(), (
        "und nicht im Spielhauptverzeichnis liegenbleiben"
    )

    liste = (spiel / "archive" / "pc" / "mod" / "modlist.txt").read_text(encoding="utf-8")
    assert "00_VTK_Gothic_Tattoo_by_Caz.archive" in liste
