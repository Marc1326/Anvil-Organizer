"""Mod-Archive kommen aus der Windows-Welt.

Dort sind "meshes" und "Meshes" derselbe Ordner, auf ext4 sind es zwei.
Gemeldet fuer XP32 Maximum Skeleton: dessen FOMOD schreibt in der Basis
klein und in einer Option gross -- im Spiel lag danach beides nebeneinander
und nur die Haelfte der Dateien wurde geladen.

Angeglichen wird beim Ausrollen, nicht beim Installieren: in ``.mods/``
bleibt alles unberuehrt, damit hier keine Datei verlorengehen kann.
"""

from pathlib import Path

import pytest

from anvil.core.case_paths import CaseIndex
from anvil.core.deploy_rules import apply_data_path
from anvil.core.mod_deployer import ModDeployer
from anvil.core.mod_list_io import write_active_mods, write_global_modlist
from anvil.core.overlay_staging import OverlayStage


def _schreibe(pfad: Path, inhalt: str = "x") -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(inhalt)


# ── CaseIndex ─────────────────────────────────────────────────────────

def test_bestehende_schreibweise_gewinnt(tmp_path: Path) -> None:
    (tmp_path / "Meshes" / "actors").mkdir(parents=True)
    assert CaseIndex(tmp_path).resolve("meshes/actors") == Path("Meshes/actors")


def test_ohne_treffer_bleibt_die_gewuenschte_schreibweise(tmp_path: Path) -> None:
    assert CaseIndex(tmp_path).resolve("Textures/neu") == Path("Textures/neu")


def test_entscheidung_gilt_auch_vor_dem_anlegen(tmp_path: Path) -> None:
    # Zwei Mods hintereinander: die zweite muss dort landen, wo die erste
    # hinwollte -- auch wenn noch keine Datei geschrieben wurde.
    index = CaseIndex(tmp_path)
    assert index.resolve("Meshes/a.nif") == Path("Meshes/a.nif")
    assert index.resolve("meshes/b.nif") == Path("Meshes/b.nif")


def test_rueckwaertsstrich_wird_verstanden(tmp_path: Path) -> None:
    (tmp_path / "meshes").mkdir()
    assert CaseIndex(tmp_path).resolve("Meshes\\actors") == Path("meshes/actors")


def test_erste_wurzel_gewinnt(tmp_path: Path) -> None:
    spiel = tmp_path / "spiel"
    schicht = tmp_path / "schicht"
    (spiel / "Data").mkdir(parents=True)
    (schicht / "data").mkdir(parents=True)
    assert CaseIndex(spiel, schicht).resolve("DATA/x.esp") == Path("Data/x.esp")


def test_kein_ausbruch_aus_dem_ziel(tmp_path: Path) -> None:
    index = CaseIndex(tmp_path)
    assert index.resolve("../../etc/passwd") == Path("etc/passwd")
    assert index.resolve("/etc/passwd") == Path("etc/passwd")


def test_unlesbarer_ordner_wirft_nicht(tmp_path: Path) -> None:
    gesperrt = tmp_path / "gesperrt"
    gesperrt.mkdir()
    gesperrt.chmod(0o000)
    try:
        assert CaseIndex(tmp_path).resolve("gesperrt/tief/a.nif") == Path(
            "gesperrt/tief/a.nif"
        )
    finally:
        gesperrt.chmod(0o755)


def test_ordner_wird_nur_einmal_gelesen(tmp_path: Path, monkeypatch) -> None:
    # Ohne Zwischenspeicher liest die Aufloesung pro Datei das komplette
    # Zielverzeichnis -- das wird quadratisch.
    (tmp_path / "meshes").mkdir()
    aufrufe = {"n": 0}
    echt = Path.iterdir

    def gezaehlt(self):
        aufrufe["n"] += 1
        return echt(self)

    monkeypatch.setattr(Path, "iterdir", gezaehlt)
    index = CaseIndex(tmp_path)
    for i in range(50):
        index.resolve(f"Meshes/datei{i}.nif")
    # Einmal die Wurzel, einmal der Unterordner -- nicht 50 mal.
    assert aufrufe["n"] == 2


# ── Data-Praefix ──────────────────────────────────────────────────────

@pytest.mark.parametrize("geschrieben", ["Data", "data", "DATA"])
def test_data_praefix_wird_nicht_verdoppelt(geschrieben: str) -> None:
    rel = Path(geschrieben) / "meshes" / "a.nif"
    assert apply_data_path(rel, "M", data_path="Data") == Path("Data/meshes/a.nif")


def test_data_praefix_kommt_weiterhin_davor() -> None:
    assert apply_data_path(Path("meshes/a.nif"), "M", data_path="Data") == Path(
        "Data/meshes/a.nif"
    )


def test_mehrteiliges_praefix() -> None:
    rel = Path("content/paks/x.pak")
    assert apply_data_path(rel, "M", data_path="Content/Paks") == Path(
        "Content/Paks/x.pak"
    )


def test_umleitung_greift_unabhaengig_von_der_schreibweise() -> None:
    routes = {"mods": "Mods", "dlc": "DLC"}
    rel = Path("MODS/modA/content/a.bundle")
    assert apply_data_path(
        rel, "M", data_path="Mods", multi_folder_routes=routes
    ) == Path("Mods/modA/content/a.bundle")


def test_ordner_der_nur_so_heisst_wie_das_praefix_bleibt_verschachtelt() -> None:
    # "database" faengt mit "data" an, ist aber ein anderer Ordner.
    rel = Path("database/x.txt")
    assert apply_data_path(rel, "M", data_path="Data") == Path("Data/database/x.txt")


# ── Deployer ──────────────────────────────────────────────────────────

def _instanz(tmp_path: Path, mods: dict[str, list[str]]) -> tuple[Path, Path]:
    """Instanz mit mehreren Mods; erste in der Liste = hoechste Prioritaet."""
    instanz = tmp_path / "Instance"
    spiel = tmp_path / "Game"
    profile = instanz / ".profiles"
    for pfad in (instanz, spiel, profile / "Default"):
        pfad.mkdir(parents=True, exist_ok=True)

    for name, dateien in mods.items():
        for datei in dateien:
            _schreibe(instanz / ".mods" / name / datei, f"{name}:{datei}")

    write_global_modlist(profile, list(mods))
    write_active_mods(profile / "Default", set(mods))
    return instanz, spiel


def test_zwei_mods_mit_anderer_schreibweise_teilen_einen_ordner(tmp_path: Path) -> None:
    instanz, spiel = _instanz(tmp_path, {
        "Mod A": ["meshes/actors/a.nif"],
        "Mod B": ["Meshes/actors/b.nif"],
    })
    ModDeployer(instanz, spiel, data_path="Data").deploy()

    # Welche der beiden Schreibweisen stehenbleibt, ist gleichgueltig --
    # es darf nur nicht beide geben.
    ordner = list((spiel / "Data").iterdir())
    assert len(ordner) == 1, [p.name for p in ordner]
    inhalt = sorted(p.name for p in (ordner[0] / "actors").iterdir())
    assert inhalt == ["a.nif", "b.nif"]


def test_eine_mod_mit_beiden_schreibweisen(tmp_path: Path) -> None:
    # Der gemeldete XP32-Fall.
    instanz, spiel = _instanz(tmp_path, {
        "XPMSSE": ["meshes/actors/skeleton.nif", "Meshes/actors/extra.nif"],
    })
    ModDeployer(instanz, spiel, data_path="Data").deploy()

    actors = spiel / "Data" / "meshes" / "actors"
    assert sorted(p.name for p in actors.iterdir()) == ["extra.nif", "skeleton.nif"]


def test_mod_folgt_dem_ordner_der_im_spiel_liegt(tmp_path: Path) -> None:
    instanz, spiel = _instanz(tmp_path, {"Mod A": ["meshes/a.nif"]})
    _schreibe(spiel / "Data" / "Meshes" / "vanilla.nif", "spiel")

    ModDeployer(instanz, spiel, data_path="Data").deploy()

    assert sorted(p.name for p in (spiel / "Data").iterdir()) == ["Meshes"]
    assert (spiel / "Data" / "Meshes" / "a.nif").exists()


def test_mod_mit_data_praefix_landet_nicht_doppelt(tmp_path: Path) -> None:
    instanz, spiel = _instanz(tmp_path, {"Mod A": ["data/meshes/a.nif"]})
    ModDeployer(instanz, spiel, data_path="Data").deploy()

    assert (spiel / "Data" / "meshes" / "a.nif").exists()
    assert not (spiel / "Data" / "data").exists()


def test_aufraeumen_laesst_nichts_liegen(tmp_path: Path) -> None:
    # Der heikle Teil: das Manifest muss den angeglichenen Pfad kennen,
    # sonst findet der Rueckbau die Datei nicht wieder.
    instanz, spiel = _instanz(tmp_path, {
        "Mod A": ["meshes/a.nif"],
        "Mod B": ["Meshes/b.nif"],
    })
    deployer = ModDeployer(instanz, spiel, data_path="Data")
    deployer.deploy()
    gelegt = sorted(p.name for p in spiel.rglob("*") if p.is_symlink())
    assert gelegt == ["a.nif", "b.nif"], "der Test misst sonst nichts"

    deployer.purge()
    uebrig = [p for p in spiel.rglob("*") if p.is_file() or p.is_symlink()]
    assert uebrig == []


# ── Overlay-Schicht ───────────────────────────────────────────────────

def test_schicht_richtet_sich_nach_dem_spielordner(tmp_path: Path) -> None:
    # OverlayFS legt nur buchstabengleiche Ordner zusammen. Baut die
    # Schicht "Data/meshes", waehrend im Spiel "Data/Meshes" liegt, sieht
    # das Spiel im Mount zwei Ordner statt einem.
    mods = tmp_path / ".mods"
    profiles = tmp_path / ".profiles"
    (profiles / "Default").mkdir(parents=True)
    _schreibe(mods / "Mod A" / "meshes" / "a.nif")
    write_global_modlist(profiles, ["Mod A"])
    write_active_mods(profiles / "Default", {"Mod A"})

    spiel = tmp_path / "Game"
    _schreibe(spiel / "Data" / "Meshes" / "vanilla.nif")

    OverlayStage(
        mods, profiles, game_path=spiel, data_path="Data",
    ).build(tmp_path / "stage")

    data = tmp_path / "stage" / "main" / "Data"
    assert sorted(p.name for p in data.iterdir()) == ["Meshes"]
    assert (data / "Meshes" / "a.nif").is_file()


def test_schicht_legt_zwei_mods_in_einen_ordner(tmp_path: Path) -> None:
    mods = tmp_path / ".mods"
    profiles = tmp_path / ".profiles"
    (profiles / "Default").mkdir(parents=True)
    _schreibe(mods / "Mod A" / "meshes" / "a.nif")
    _schreibe(mods / "Mod B" / "Meshes" / "b.nif")
    write_global_modlist(profiles, ["Mod A", "Mod B"])
    write_active_mods(profiles / "Default", {"Mod A", "Mod B"})

    spiel = tmp_path / "Game"
    spiel.mkdir()

    OverlayStage(
        mods, profiles, game_path=spiel, data_path="Data",
    ).build(tmp_path / "stage")

    ordner = list((tmp_path / "stage" / "main" / "Data").iterdir())
    assert len(ordner) == 1, [p.name for p in ordner]
    assert sorted(p.name for p in ordner[0].iterdir()) == ["a.nif", "b.nif"]


# ── Grenzen der Angleichung ───────────────────────────────────────────

def test_frameworks_werden_nicht_angeglichen(tmp_path: Path) -> None:
    # Frameworks duerfen echte Spieldateien ueberschreiben. Wuerde ein
    # "version.dll" auf ein vorhandenes "Version.dll" gezogen, kostet der
    # Rueckbau die Originaldatei des Spiels.
    instanz, spiel = _instanz(tmp_path, {"RED4ext": ["version.dll"]})
    _schreibe(spiel / "Version.dll", "spiel")

    ModDeployer(
        instanz, spiel, direct_install_patterns=["RED4ext"], data_path="Data",
    ).deploy()

    assert (spiel / "Version.dll").read_text() == "spiel"
    assert (spiel / "version.dll").exists()


def test_kopier_pfad_greift_trotz_anderer_schreibweise(tmp_path: Path) -> None:
    # Verlinkte DLLs kommen unter Proton nicht als gueltige DLL an --
    # unter "RED4ext/plugins" muss kopiert werden, nicht verlinkt.
    instanz, spiel = _instanz(tmp_path, {"Plugin": ["red4ext/plugins/a.dll"]})
    _schreibe(spiel / "RED4ext" / "plugins" / "vorhanden.dll", "x")

    ModDeployer(
        instanz, spiel, copy_deploy_paths=["red4ext/plugins"],
    ).deploy()

    gelegt = [p for p in spiel.rglob("a.dll")]
    assert len(gelegt) == 1
    assert not gelegt[0].is_symlink(), "muss kopiert werden, nicht verlinkt"


def test_datei_in_zwei_schreibweisen_hinterlaesst_keinen_geisterteintrag(
    tmp_path: Path,
) -> None:
    # Beide zeigen nach dem Angleichen auf dasselbe Ziel -- im Abdruck darf
    # der Eintrag nur einmal stehen, sonst raeumt der Rueckbau daneben.
    instanz, spiel = _instanz(tmp_path, {
        "M": ["paks/x.pak", "Paks/x.pak"],
    })
    deployer = ModDeployer(
        instanz, spiel,
        pak_load_order_prefix=True,
        pak_load_order_dirs=["paks"],
        pak_load_order_extensions=[".pak"],
    )
    deployer.deploy()

    vorhanden = [p for p in spiel.rglob("*x.pak")]
    assert len(vorhanden) == 1, [str(p) for p in vorhanden]

    deployer.purge()
    assert [p for p in spiel.rglob("*") if p.is_file() or p.is_symlink()] == []


def test_wurzeldatei_namens_data_wird_nicht_zum_praefix() -> None:
    assert apply_data_path(Path("data"), "M", data_path="Data") == Path("Data/data")


# ── Befunde der zweiten Pruefrunde ────────────────────────────────────

def test_overlay_verliert_keine_datei_bei_zwei_schreibweisen(tmp_path: Path) -> None:
    # Beide zeigen nach dem Angleichen auf dieselbe Zieldatei. Wurde sie
    # zweimal verbucht, raeumte die Zaehler-Bereinigung sie danach weg.
    mods = tmp_path / ".mods"
    profiles = tmp_path / ".profiles"
    (profiles / "Default").mkdir(parents=True)
    _schreibe(mods / "M" / "paks" / "x.pak")
    _schreibe(mods / "M" / "Paks" / "x.pak")
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})
    spiel = tmp_path / "Game"
    spiel.mkdir()

    ergebnis = OverlayStage(
        mods, profiles, game_path=spiel,
        pak_load_order_prefix=True,
        pak_load_order_dirs=["paks"],
        pak_load_order_extensions=[".pak"],
    ).build(tmp_path / "stage")

    vorhanden = [p for p in (tmp_path / "stage").rglob("*.pak")]
    assert len(vorhanden) == 1, [str(p) for p in vorhanden]
    assert len(ergebnis.placed) == 1, ergebnis.placed


def test_konflikt_scanner_meldet_mod_nicht_gegen_sich_selbst() -> None:
    from anvil.core.conflict_scanner import ConflictScanner

    ergebnis = ConflictScanner().scan_conflicts(
        [{"name": "A", "path": ""}],
        mod_index=_FesterIndex({"A": ["meshes/x.nif", "Meshes/x.nif"]}),
    )

    assert ergebnis["conflicts"] == []
    assert list(ergebnis["file_owners"].values()) == [["A"]]


def test_konflikt_zwischen_zwei_mods_wird_weiter_gemeldet() -> None:
    from anvil.core.conflict_scanner import ConflictScanner

    ergebnis = ConflictScanner().scan_conflicts(
        [{"name": "A", "path": ""}, {"name": "B", "path": ""}],
        mod_index=_FesterIndex({"A": ["meshes/x.nif"], "B": ["Meshes/x.nif"]}),
    )

    assert len(ergebnis["conflicts"]) == 1
    assert ergebnis["conflicts"][0]["mods"] == ["A", "B"]
    assert ergebnis["conflicts"][0]["winner"] == "B"


class _FesterIndex:
    """Mod-Index mit fest verdrahteten Dateilisten."""

    def __init__(self, listen: dict[str, list[str]]) -> None:
        self._listen = listen

    def get_file_list(self, mod_name: str):
        return [{"rel": r} for r in self._listen.get(mod_name, [])]


def test_framework_folgt_dem_ordner_aber_nicht_der_spieldatei(tmp_path: Path) -> None:
    # Ordner angleichen ja -- sonst liegen bei Cyberpunk RED4ext/ und
    # red4ext/ nebeneinander. Eine echte Spieldatei ueberschreiben nein.
    instanz, spiel = _instanz(tmp_path, {
        "RED4ext": ["red4ext/plugins/a.dll", "version.dll"],
    })
    _schreibe(spiel / "RED4ext" / "plugins" / "vorhanden.dll", "x")
    _schreibe(spiel / "Version.dll", "spiel")

    ModDeployer(
        instanz, spiel, direct_install_patterns=["RED4ext"],
    ).deploy()

    assert (spiel / "RED4ext" / "plugins" / "a.dll").exists()
    assert not (spiel / "red4ext").exists()
    assert (spiel / "Version.dll").read_text() == "spiel"


def test_archiv_ladeliste_folgt_der_angeglichenen_schreibweise(tmp_path: Path) -> None:
    # Legt die erste Mod "Archive/pc/mod" an, muss die Ladeliste dort
    # landen -- sonst wird sie gar nicht geschrieben.
    # Beide Mods schreiben gross, die Konfiguration nennt den Ordner klein.
    instanz, spiel = _instanz(tmp_path, {
        "Mod A": ["Archive/pc/mod/a.archive"],
        "Mod B": ["Archive/pc/mod/b.archive"],
    })
    ModDeployer(
        instanz, spiel, archive_load_order_file="archive/pc/mod/modlist.txt",
    ).deploy()

    listen = [p for p in spiel.rglob("modlist.txt")]
    assert len(listen) == 1, [str(p) for p in listen]
    assert listen[0].parent == spiel / "Archive" / "pc" / "mod"
    zeilen = listen[0].read_text(encoding="utf-8").split()
    assert sorted(zeilen) == ["a.archive", "b.archive"]


def test_fomod_ausbruch_wird_abgelehnt_statt_bereinigt(tmp_path: Path) -> None:
    from anvil.core.fomod_parser import FomodFile, assemble_fomod_files

    quelle = tmp_path / "archiv"
    _schreibe(quelle / "opt" / "boese.txt", "x")

    ziel = assemble_fomod_files(quelle, [
        FomodFile(source="opt/boese.txt", destination="../../entkommen.txt",
                  is_folder=False, priority=0),
    ])

    assert ziel is None, "der Eintrag haette abgelehnt werden muessen"
    assert not (tmp_path.parent / "entkommen.txt").exists()


def test_platzhalter_mit_schraegstrich_am_ende_wirft_nicht(tmp_path: Path) -> None:
    from anvil.mainwindow import _path_matches

    assert _path_matches(tmp_path, "Data/*/") is False


# ── Befunde der dritten Pruefrunde ────────────────────────────────────

def test_framework_ordner_bleibt_zusammen_trotz_vorhandener_datei(
    tmp_path: Path,
) -> None:
    # Zurueck weicht nur der Dateiname, nie der Ordner -- sonst zerreisst
    # es das Framework auf "RED4ext/" und "red4ext/". Eine gleichnamige
    # Datei im selben Ordner darf ein Framework ueberschreiben, das ist
    # sein Zweck (Update einer aelteren Fassung).
    instanz, spiel = _instanz(tmp_path, {
        "RED4ext": ["red4ext/plugins/foo.dll", "red4ext/plugins/bar.dll"],
    })
    _schreibe(spiel / "RED4ext" / "plugins" / "alt.dll", "x")

    ModDeployer(instanz, spiel, direct_install_patterns=["RED4ext"]).deploy()

    ordner = [p.name for p in spiel.iterdir() if p.is_dir()]
    assert ordner == ["RED4ext"], ordner
    plugins = spiel / "RED4ext" / "plugins"
    assert sorted(p.name for p in plugins.iterdir()) == [
        "alt.dll", "bar.dll", "foo.dll",
    ]


def test_staerkere_mod_steht_zuletzt_in_der_overlay_ladeliste(tmp_path: Path) -> None:
    # Das Duplikat-Set gilt je Mod. Ueber Mods hinweg gewinnt die hoehere,
    # und ihr Eintrag muss der letzte sein -- die Ladeliste liest von hinten.
    mods = tmp_path / ".mods"
    profiles = tmp_path / ".profiles"
    (profiles / "Default").mkdir(parents=True)
    _schreibe(mods / "Stark" / "archive" / "streit.archive", "stark")
    _schreibe(mods / "Schwach" / "archive" / "streit.archive", "schwach")
    _schreibe(mods / "Schwach" / "archive" / "eigen.archive", "s")
    write_global_modlist(profiles, ["Stark", "Schwach"])
    write_active_mods(profiles / "Default", {"Stark", "Schwach"})
    spiel = tmp_path / "Game"
    spiel.mkdir()

    ergebnis = OverlayStage(
        mods, profiles, game_path=spiel,
    ).build(tmp_path / "stage")

    # Jede Mod, die die Datei ablegt, gehoert einmal in die Liste -- die
    # Ladeliste liest von hinten und braucht die staerkste zuletzt.
    streit = [z for _, z in ergebnis.placed if z.name == "streit.archive"]
    assert len(streit) == 2, [str(z) for _, z in ergebnis.placed]
    assert ergebnis.placed[-1][1].name == "streit.archive"


def test_redmod_ordner_folgt_der_schreibweise_im_spiel(tmp_path: Path) -> None:
    instanz, spiel = _instanz(tmp_path, {"Mod A": ["info.json"]})
    (spiel / "Mods").mkdir()

    ModDeployer(instanz, spiel, redmod_path="mods").deploy()

    assert sorted(p.name for p in spiel.iterdir()) == ["Mods"]
    assert (spiel / "Mods" / "Mod A").is_symlink()


def test_lml_ordner_folgt_der_schreibweise_im_spiel(tmp_path: Path) -> None:
    instanz, spiel = _instanz(tmp_path, {"Mod A": ["install.xml"]})
    (spiel / "LML").mkdir()

    ModDeployer(instanz, spiel, lml_path="lml").deploy()

    assert sorted(p.name for p in spiel.iterdir()) == ["LML"]
    assert (spiel / "LML" / "Mod A").is_symlink()


def test_ordner_mod_laesst_sich_wieder_aufraeumen(tmp_path: Path) -> None:
    instanz, spiel = _instanz(tmp_path, {"Mod A": ["info.json"]})
    (spiel / "Mods").mkdir()

    deployer = ModDeployer(instanz, spiel, redmod_path="mods")
    deployer.deploy()
    assert (spiel / "Mods" / "Mod A").is_symlink()

    deployer.purge()
    assert not (spiel / "Mods" / "Mod A").exists()


def test_framework_weicht_nur_im_dateinamen_zurueck(tmp_path: Path) -> None:
    # Spiel hat "RED4ext/plugins/Foo.dll" als echte Datei, die Mod bringt
    # "red4ext/plugins/foo.dll". Der Ordner folgt dem Spiel, der Dateiname
    # bleibt der des Archivs -- sonst waere die Spieldatei ueberschrieben.
    instanz, spiel = _instanz(tmp_path, {"RED4ext": ["red4ext/plugins/foo.dll"]})
    _schreibe(spiel / "RED4ext" / "plugins" / "Foo.dll", "spiel")

    ModDeployer(instanz, spiel, direct_install_patterns=["RED4ext"]).deploy()

    assert [p.name for p in spiel.iterdir() if p.is_dir()] == ["RED4ext"]
    plugins = spiel / "RED4ext" / "plugins"
    assert sorted(p.name for p in plugins.iterdir()) == ["Foo.dll", "foo.dll"]
    assert (plugins / "Foo.dll").read_text() == "spiel"
