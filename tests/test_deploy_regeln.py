"""Schutznetz fuer die Pfadregeln des Deployers.

Diese Regeln entscheiden, was ueberhaupt im Spielordner landet und wo.
Sie stehen heute als Inline-Bloecke in ``mod_deployer.py`` und sollen in
ein eigenes Modul wandern, damit Symlink-Weg und Overlay-Weg dieselben
Regeln benutzen.

Fuenf davon hatte bisher **kein** Test abgedeckt. Man haette sie beim
Verschieben still kaputtmachen koennen, ohne dass die Suite anschlaegt:
Bilder und Readmes waeren im Spielordner aufgetaucht, FOMOD-Mods haetten
ihren Installer-Ordner mitgeschleppt, RootBuilder-Mods waeren unter
einem falschen ``root/`` gelandet, Bethesda-Mods haetten ihr ``Data/``
verdoppelt.

Die Tests halten den **Ist-Zustand** fest, kein Wunschverhalten. Sie
muessen vor und nach dem Umbau gleich gruen sein.
"""

from __future__ import annotations

from pathlib import Path

from anvil.core.mod_deployer import ModDeployer
from anvil.core.mod_list_io import write_active_mods, write_global_modlist


def _bibliothek(tmp_path: Path, dateien: dict[str, bytes],
               mod_name: str = "Testmod") -> tuple[Path, Path, Path]:
    """Baut eine Mini-Instanz mit genau einer aktiven Mod.

    *dateien* bildet relative Pfade innerhalb des Mod-Ordners auf ihren
    Inhalt ab.
    """
    instanz = tmp_path / "Instance"
    spiel = tmp_path / "Game"
    profile = instanz / ".profiles"
    profil = profile / "Default"
    mod = instanz / ".mods" / mod_name

    for pfad in (instanz, spiel, profil, mod):
        pfad.mkdir(parents=True, exist_ok=True)

    for rel, inhalt in dateien.items():
        ziel = mod / rel
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(inhalt)

    write_global_modlist(profile, [mod_name])
    write_active_mods(profil, {mod_name})
    return instanz, spiel, mod


# ── Regel 1: Verwaltungsdateien bleiben draussen ─────────────────────


def test_meta_ini_landet_nicht_im_spiel(tmp_path: Path) -> None:
    """``meta.ini`` gehoert Anvil, nicht dem Spiel."""
    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "meta.ini": b"[General]\n",
        "textures/haut.dds": b"textur",
    })

    ergebnis = ModDeployer(instanz, spiel).deploy()

    assert ergebnis.success is True
    assert (spiel / "textures" / "haut.dds").is_symlink(), (
        "die eigentliche Mod-Datei fehlt -- der Test misst gar nichts"
    )
    assert not (spiel / "meta.ini").exists()
    assert not (spiel / "meta.ini").is_symlink()


def test_weitere_verwaltungsdateien_bleiben_draussen(tmp_path: Path) -> None:
    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "codes.txt": b"1234",
        "fomod_choices.json": b"{}",
        "textures/haut.dds": b"textur",
    })

    ModDeployer(instanz, spiel).deploy()

    assert (spiel / "textures" / "haut.dds").is_symlink()
    assert not (spiel / "codes.txt").exists()
    assert not (spiel / "fomod_choices.json").exists()


# ── Regel 2: Der Installer-Ordner bleibt draussen ────────────────────


def test_fomod_ordner_landet_nicht_im_spiel(tmp_path: Path) -> None:
    """``fomod/`` ist Installer-Beiwerk, kein Spielinhalt."""
    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "fomod/ModuleConfig.xml": b"<config/>",
        "fomod/info.xml": b"<info/>",
        "meshes/koerper.nif": b"mesh",
    })

    ModDeployer(instanz, spiel).deploy()

    assert (spiel / "meshes" / "koerper.nif").is_symlink()
    assert not (spiel / "fomod").exists()
    assert not (spiel / "fomod" / "ModuleConfig.xml").exists()


# ── Regel 3: Doku und Bilder nur in der Mod-Wurzel ueberspringen ─────


def test_doku_in_der_wurzel_bleibt_draussen(tmp_path: Path) -> None:
    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "readme.txt": b"Anleitung",
        "vorschau.png": b"bild",
        "aenderungen.md": b"# Log",
        "meshes/koerper.nif": b"mesh",
    })

    ModDeployer(instanz, spiel).deploy()

    assert (spiel / "meshes" / "koerper.nif").is_symlink()
    for name in ("readme.txt", "vorschau.png", "aenderungen.md"):
        assert not (spiel / name).exists(), f"{name} ist im Spielordner"


def test_gleiche_endung_im_unterordner_kommt_mit(tmp_path: Path) -> None:
    """Der Kern der Regel: sie gilt NUR in der Wurzel.

    Eine ``.txt`` unter ``interface/`` kann echter Spielinhalt sein.
    """
    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "readme.txt": b"Anleitung",
        "interface/translate_de.txt": b"Uebersetzung",
        "textures/vorschau.png": b"echte Textur",
    })

    ModDeployer(instanz, spiel).deploy()

    assert not (spiel / "readme.txt").exists()
    assert (spiel / "interface" / "translate_de.txt").is_symlink(), (
        "Unterordner-Datei wurde mit der Wurzel-Regel weggeworfen"
    )
    assert (spiel / "textures" / "vorschau.png").is_symlink()


# ── Regel 4: fuehrendes root/ abziehen ───────────────────────────────


def test_root_ordner_wird_abgezogen(tmp_path: Path) -> None:
    """``root/`` ist eine Verpackung, kein Zielordner im Spiel."""
    instanz, spiel, mod = _bibliothek(tmp_path, {
        "root/meshes/koerper.nif": b"mesh",
    })

    ModDeployer(instanz, spiel).deploy()

    ziel = spiel / "meshes" / "koerper.nif"
    assert ziel.is_symlink()
    assert ziel.resolve() == mod / "root" / "meshes" / "koerper.nif"
    assert not (spiel / "root").exists(), (
        "root/ wurde mitgenommen -- die Mod wirkt im Spiel nicht"
    )


def test_root_nur_am_anfang(tmp_path: Path) -> None:
    """Ein ``root`` mitten im Pfad ist ein normaler Ordner."""
    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "meshes/root/koerper.nif": b"mesh",
    })

    ModDeployer(instanz, spiel).deploy()

    assert (spiel / "meshes" / "root" / "koerper.nif").is_symlink()


# ── Regel 5: Data-Praefix nicht verdoppeln ───────────────────────────


def test_data_praefix_wird_vorangestellt(tmp_path: Path) -> None:
    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "meshes/koerper.nif": b"mesh",
    })

    ModDeployer(instanz, spiel, data_path="Data").deploy()

    assert (spiel / "Data" / "meshes" / "koerper.nif").is_symlink()


def test_vorhandenes_data_wird_nicht_verdoppelt(tmp_path: Path) -> None:
    """Viele Mods bringen ihr ``Data/`` schon mit."""
    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "Data/meshes/koerper.nif": b"mesh",
    })

    ModDeployer(instanz, spiel, data_path="Data").deploy()

    assert (spiel / "Data" / "meshes" / "koerper.nif").is_symlink()
    assert not (spiel / "Data" / "Data").exists(), (
        "Data/Data/ -- das Spiel findet dort nichts"
    )


# ── Regel 6: Ordner-Umleitungen ──────────────────────────────────────


"""Witcher 3 faehrt ``GameDataPath = "Mods"`` (game_witcher3.py:44)
zusammen mit ``GameMultiFolderRoutes`` (:64). Die Umleitung sitzt im
Deployer **innerhalb** der Data-Praefix-Pruefung
(mod_deployer.py:763-773) -- ohne gesetztes ``data_path`` passiert sie
gar nicht. Die Tests bilden deshalb beides zusammen ab.
"""

_WITCHER_ROUTEN = {"mods": "Mods", "dlc": "DLC", "bin": "bin"}


def test_ordner_umleitung_greift(tmp_path: Path) -> None:
    """``mods/`` der Mod gehoert nach ``Mods/`` -- ohne zweites Mods/."""
    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "mods/modBesserePferde/content/blob.bundle": b"daten",
    })

    ModDeployer(
        instanz, spiel,
        data_path="Mods",
        multi_folder_routes=_WITCHER_ROUTEN,
    ).deploy()

    ziel = spiel / "Mods" / "modBesserePferde" / "content" / "blob.bundle"
    assert ziel.is_symlink()
    assert not (spiel / "Mods" / "mods").exists(), (
        "Umleitung uebersprungen -- Ordner liegt flach unter Mods/"
    )


def test_umleitung_zeigt_woandershin_als_das_data_verzeichnis(
    tmp_path: Path,
) -> None:
    """``dlc/`` geht nach ``DLC/``, NICHT unter ``Mods/``."""
    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "dlc/dlcPferd/content/blob.bundle": b"daten",
    })

    ModDeployer(
        instanz, spiel,
        data_path="Mods",
        multi_folder_routes=_WITCHER_ROUTEN,
    ).deploy()

    assert (spiel / "DLC" / "dlcPferd" / "content" / "blob.bundle").is_symlink()
    assert not (spiel / "Mods" / "dlc").exists()
    assert not (spiel / "Mods" / "DLC").exists()


def test_ordner_ohne_umleitung_bekommt_das_data_verzeichnis(
    tmp_path: Path,
) -> None:
    """Was keine Route hat, faellt auf den normalen Weg zurueck."""
    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "textures/haut.dds": b"textur",
    })

    ModDeployer(
        instanz, spiel,
        data_path="Mods",
        multi_folder_routes=_WITCHER_ROUTEN,
    ).deploy()

    assert (spiel / "Mods" / "textures" / "haut.dds").is_symlink()


# ── Beide Seiten muessen dieselbe Antwort geben ──────────────────────

_VERWALTUNG_FAELLE = [
    "meta.ini",
    "codes.txt",
    "fomod_choices.json",
    "fomod/ModuleConfig.xml",
    "FOMOD/info.xml",
    "readme.txt",
    "vorschau.png",
    "aenderungen.md",
    "Thumbs.db",
]

_INHALT_FAELLE = [
    "meshes/koerper.nif",
    "textures/haut.dds",
    "interface/translate_de.txt",
    "textures/vorschau.png",
    "unterordner/meta.ini.bak",
    "scripts/foo.pex",
]


def test_is_metadata_stimmt_mit_dem_deploy_ueberein(tmp_path: Path) -> None:
    """Der Overlay-Weg benutzt ``is_metadata``, der Symlink-Weg hat die
    drei Pruefungen inline. Laufen sie auseinander, sehen beide Wege
    unterschiedliche Spielordner -- und kein anderer Test merkt es.
    """
    from anvil.core.deploy_rules import is_metadata

    alle = {rel: b"x" for rel in _VERWALTUNG_FAELLE + _INHALT_FAELLE}
    instanz, spiel, mod = _bibliothek(tmp_path, alle)

    ModDeployer(instanz, spiel).deploy()

    for rel in _VERWALTUNG_FAELLE:
        quelle = mod / rel
        assert is_metadata(quelle, mod, Path(rel)) is True, (
            f"is_metadata laesst {rel} durch"
        )
        assert not (spiel / rel).exists(), (
            f"der Deployer hat {rel} ins Spiel gelegt"
        )

    for rel in _INHALT_FAELLE:
        quelle = mod / rel
        assert is_metadata(quelle, mod, Path(rel)) is False, (
            f"is_metadata wirft {rel} weg"
        )
        assert (spiel / rel).is_symlink(), (
            f"der Deployer hat {rel} weggeworfen"
        )


# ── Reihenfolge: Zielverteilung ZUERST, dann Data-Praefix ────────────


def test_zielverteilung_laeuft_vor_dem_data_praefix(tmp_path: Path) -> None:
    """Stalker 2 hat beides: Routen UND ein Data-Verzeichnis.

    Die Verteilung arbeitet auf dem Pfad **ohne** Praefix. Liefe sie
    danach, saehe sie ``Stalker2/foo.pak`` statt ``foo.pak`` und wuerde
    nicht mehr greifen -- die Mod landete flach im Spielordner statt in
    ``Content/Paks/~mods``. Ohne Fehlermeldung, sie wirkt nur nicht.
    """
    from anvil.plugins.games.game_stalker2 import Stalker2Game

    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "~mods/BesseresWetter.pak": b"pak",
    })

    ModDeployer(
        instanz, spiel,
        data_path=Stalker2Game.GameDataPath,
        deploy_strip_prefixes=Stalker2Game.GameDeployStripPrefixes,
        deploy_anchors=Stalker2Game.GameDeployAnchors,
        deploy_routes=Stalker2Game.GameDeployRoutes,
    ).deploy()

    ziel = (spiel / "Stalker2" / "Content" / "Paks" / "~mods"
            / "BesseresWetter.pak")
    assert ziel.is_symlink(), (
        "Pak-Mod nicht im ~mods-Ordner -- Reihenfolge vertauscht?"
    )
    assert not (spiel / "Stalker2" / "BesseresWetter.pak").exists()
    assert not (spiel / "Stalker2" / "Stalker2").exists()


def test_dll_route_mit_data_praefix(tmp_path: Path) -> None:
    """Zweite Route, damit nicht nur ein Sonderfall abgedeckt ist."""
    from anvil.plugins.games.game_stalker2 import Stalker2Game

    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "loader/dsound.dll": b"binaer",
    })

    ModDeployer(
        instanz, spiel,
        data_path=Stalker2Game.GameDataPath,
        deploy_strip_prefixes=Stalker2Game.GameDeployStripPrefixes,
        deploy_anchors=Stalker2Game.GameDeployAnchors,
        deploy_routes=Stalker2Game.GameDeployRoutes,
    ).deploy()

    assert (spiel / "Stalker2" / "Binaries" / "Win64"
            / "dsound.dll").is_symlink()


def test_eigene_struktur_bleibt_unangetastet(tmp_path: Path) -> None:
    """Bringt der Mod einen Ankerordner mit, wird nicht umsortiert --
    und das Data-Praefix darf sich trotzdem nicht verdoppeln.
    """
    from anvil.plugins.games.game_stalker2 import Stalker2Game

    instanz, spiel, _mod = _bibliothek(tmp_path, {
        "Stalker2/Content/Paks/~mods/Fertig.pak": b"pak",
    })

    ModDeployer(
        instanz, spiel,
        data_path=Stalker2Game.GameDataPath,
        deploy_strip_prefixes=Stalker2Game.GameDeployStripPrefixes,
        deploy_anchors=Stalker2Game.GameDeployAnchors,
        deploy_routes=Stalker2Game.GameDeployRoutes,
    ).deploy()

    assert (spiel / "Stalker2" / "Content" / "Paks" / "~mods"
            / "Fertig.pak").is_symlink()
    assert not (spiel / "Stalker2" / "Stalker2").exists()


def test_konstanten_sind_nicht_doppelt_definiert() -> None:
    """``mod_deployer`` muss die Regeln aus ``deploy_rules`` beziehen.

    Waeren es zwei eigene Mengen, koennte eine geaendert werden, ohne
    dass die andere folgt -- genau der Zustand, den der Umbau beendet.
    """
    from anvil.core import deploy_rules, mod_deployer

    assert mod_deployer._SKIP_FILES is deploy_rules.SKIP_FILES
    assert mod_deployer._SKIP_DIRS is deploy_rules.SKIP_DIRS
    assert (mod_deployer._SKIP_ROOT_EXTENSIONS
            is deploy_rules.SKIP_ROOT_EXTENSIONS)
    assert (mod_deployer._BA2_SYMLINK_EXTENSIONS
            is deploy_rules.ARCHIVE_KEEP_EXTENSIONS)
