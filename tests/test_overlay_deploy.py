import json
from pathlib import Path

import pytest

from anvil.core.mod_list_io import write_active_mods, write_global_modlist
from anvil.core.overlay_deployer import OverlayDeployer, filesystem_of
from anvil.core.overlay_staging import OverlayStage, is_metadata, target_rel


@pytest.fixture
def ohne_umgebungspruefung(monkeypatch: pytest.MonkeyPatch) -> None:
    """Testverzeichnisse liegen auf tmpfs -- die Umgebungspruefung wuerde greifen."""
    monkeypatch.setattr(OverlayDeployer, "check_requirements", lambda self: [])


# ── Pfadregeln ─────────────────────────────────────────────────────────

def test_root_prefix_wird_entfernt() -> None:
    assert target_rel(Path("root/bin/x64/winmm.dll"), "RED4ext") == Path("bin/x64/winmm.dll")


def test_ohne_data_path_bleibt_der_pfad_stehen() -> None:
    assert target_rel(Path("archive/pc/mod/a.archive"), "M") == Path("archive/pc/mod/a.archive")


def test_data_path_wird_vorangestellt() -> None:
    assert target_rel(Path("meshes/a.nif"), "M", data_path="Data") == Path("Data/meshes/a.nif")


def test_data_path_wird_nicht_verdoppelt() -> None:
    assert target_rel(Path("Data/meshes/a.nif"), "M", data_path="Data") == Path("Data/meshes/a.nif")


def test_frameworks_landen_in_der_spielwurzel() -> None:
    got = target_rel(Path("bin/x64/winmm.dll"), "RED4ext", data_path="Data", is_direct=True)
    assert got == Path("bin/x64/winmm.dll")


def test_multi_folder_routen() -> None:
    got = target_rel(
        Path("mods/modXY/content/blob.bundle"),
        "M",
        data_path="Mods",
        multi_folder_routes={"mods": "Mods", "dlc": "DLC"},
    )
    assert got == Path("Mods/modXY/content/blob.bundle")


def test_nest_unter_modname() -> None:
    got = target_rel(Path("a.esp"), "Mein Mod", data_path="Data", nest_under_mod_name=True)
    assert got == Path("Data/Mein Mod/a.esp")


def test_metadaten_werden_erkannt(tmp_path: Path) -> None:
    mod = tmp_path / "Mod"
    (mod / "fomod").mkdir(parents=True)
    (mod / "meta.ini").write_text("x", encoding="utf-8")
    (mod / "vorschau.png").write_bytes(b"x")
    (mod / "fomod" / "info.xml").write_text("x", encoding="utf-8")
    (mod / "textures").mkdir()
    (mod / "textures" / "haut.png").write_bytes(b"x")

    assert is_metadata(mod / "meta.ini", mod, Path("meta.ini"))
    assert is_metadata(mod / "vorschau.png", mod, Path("vorschau.png"))
    assert is_metadata(mod / "fomod" / "info.xml", mod, Path("fomod/info.xml"))
    # Bilder in Unterordnern sind Spielinhalt
    assert not is_metadata(mod / "textures" / "haut.png", mod, Path("textures/haut.png"))


# ── Staging ────────────────────────────────────────────────────────────

def _library(tmp_path: Path) -> tuple[Path, Path]:
    mods = tmp_path / "mods"
    profiles = tmp_path / "profiles"
    (profiles / "Default").mkdir(parents=True)
    mods.mkdir()
    return mods, profiles


def _mod(mods: Path, name: str, files: dict[str, str]) -> None:
    for rel, text in files.items():
        target = mods / name / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def test_hoehere_prioritaet_gewinnt(tmp_path: Path) -> None:
    mods, profiles = _library(tmp_path)
    _mod(mods, "Oben", {"archive/gemeinsam.archive": "oben"})
    _mod(mods, "Unten", {"archive/gemeinsam.archive": "unten", "archive/nur_unten.archive": "u"})
    write_global_modlist(profiles, ["Oben", "Unten"])
    write_active_mods(profiles / "Default", {"Oben", "Unten"})

    stage = OverlayStage(mods, profiles)
    result = stage.build(tmp_path / "stage")

    assert result.success
    assert result.mods_staged == 2
    gemeinsam = tmp_path / "stage" / "archive" / "gemeinsam.archive"
    assert gemeinsam.read_text(encoding="utf-8") == "oben"
    assert (tmp_path / "stage" / "archive" / "nur_unten.archive").is_file()


def test_dokumentation_im_wurzelverzeichnis_bleibt_draussen(tmp_path: Path) -> None:
    mods, profiles = _library(tmp_path)
    _mod(mods, "M", {"liesmich.txt": "hallo", "archive/a.archive": "gut"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    OverlayStage(mods, profiles).build(tmp_path / "stage")

    assert (tmp_path / "stage" / "archive" / "a.archive").is_file()
    assert not (tmp_path / "stage" / "liesmich.txt").exists()


def test_metadaten_kommen_nicht_in_die_schicht(tmp_path: Path) -> None:
    mods, profiles = _library(tmp_path)
    _mod(mods, "M", {"meta.ini": "x", "fomod/info.xml": "x", "a.archive": "gut"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    OverlayStage(mods, profiles).build(tmp_path / "stage")

    assert (tmp_path / "stage" / "a.archive").is_file()
    assert not (tmp_path / "stage" / "meta.ini").exists()
    assert not (tmp_path / "stage" / "fomod").exists()


def test_inaktive_mods_bleiben_draussen(tmp_path: Path) -> None:
    mods, profiles = _library(tmp_path)
    _mod(mods, "An", {"archive/an.archive": "x"})
    _mod(mods, "Aus", {"archive/aus.archive": "x"})
    write_global_modlist(profiles, ["An", "Aus"])
    write_active_mods(profiles / "Default", {"An"})

    OverlayStage(mods, profiles).build(tmp_path / "stage")

    assert (tmp_path / "stage" / "archive" / "an.archive").is_file()
    assert not (tmp_path / "stage" / "archive" / "aus.archive").exists()


def test_frameworks_kommen_auch_ohne_haken_mit(tmp_path: Path) -> None:
    mods, profiles = _library(tmp_path)
    _mod(mods, "RED4ext", {"root/bin/x64/winmm.dll": "dll"})
    write_global_modlist(profiles, ["RED4ext"])
    write_active_mods(profiles / "Default", set())

    stage = OverlayStage(mods, profiles, direct_patterns=["RED4ext"])
    stage.build(tmp_path / "stage")

    assert (tmp_path / "stage" / "bin" / "x64" / "winmm.dll").is_file()


def test_trenner_werden_uebersprungen(tmp_path: Path) -> None:
    mods, profiles = _library(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "x"})
    write_global_modlist(profiles, ["gruppe_separator", "M"])
    write_active_mods(profiles / "Default", {"gruppe_separator", "M"})

    stage = OverlayStage(mods, profiles)
    assert stage.enabled_mods() == ["M"]


def test_abgeschaltete_frameworks_bleiben_liegen(tmp_path: Path) -> None:
    mods, profiles = _library(tmp_path)
    _mod(mods, "RED4ext", {"root/bin/x64/winmm.dll": "dll"})
    write_global_modlist(profiles, ["RED4ext"])
    write_active_mods(profiles / "Default", {"RED4ext"})

    stage = OverlayStage(mods, profiles, direct_patterns=["RED4ext"])
    stage._skipped = {"red4ext"}
    assert stage.enabled_mods() == []


# ── Deployer ───────────────────────────────────────────────────────────

def _instance(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    instance = tmp_path / "Instance"
    game = tmp_path / "Game"
    instance.mkdir()
    game.mkdir()
    (game / "spiel.exe").write_text("vanilla", encoding="utf-8")
    mods = instance / ".mods"
    profiles = instance / ".profiles"
    (profiles / "Default").mkdir(parents=True)
    mods.mkdir()
    return instance, game, mods, profiles


def test_deploy_baut_schicht_und_manifest(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "inhalt"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    deployer = OverlayDeployer(instance, game)
    result = deployer.deploy()

    assert result.success, result.errors
    assert deployer.is_deployed()
    assert (deployer.stage_dir / "archive" / "a.archive").is_file()

    manifest = json.loads(deployer.manifest_path.read_text(encoding="utf-8"))
    assert manifest["mods_staged"] == 1
    assert manifest["lowerdirs"] == [str(deployer.stage_dir), str(game)]
    assert manifest["upperdir"] == str(instance / ".overwrite")


def test_deploy_laesst_den_spielordner_in_ruhe(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"spiel.exe": "vom mod"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    OverlayDeployer(instance, game).deploy()

    assert (game / "spiel.exe").read_text(encoding="utf-8") == "vanilla"
    assert sorted(p.name for p in game.iterdir()) == ["spiel.exe"]


def test_purge_raeumt_die_schicht_weg(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "x"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    deployer = OverlayDeployer(instance, game)
    deployer.deploy()
    result = deployer.purge()

    assert result.success, result.errors
    assert not deployer.is_deployed()
    assert not deployer.stage_dir.exists()
    assert (game / "spiel.exe").is_file()


def test_zweiter_deploy_baut_neu_auf(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "erst"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    deployer = OverlayDeployer(instance, game)
    deployer.deploy()
    (mods / "M" / "archive" / "a.archive").write_text("dann", encoding="utf-8")
    (mods / "M" / "archive" / "b.archive").write_text("neu", encoding="utf-8")
    result = deployer.deploy()

    assert result.success, result.errors
    assert (deployer.stage_dir / "archive" / "a.archive").read_text(encoding="utf-8") == "dann"
    assert (deployer.stage_dir / "archive" / "b.archive").is_file()


def test_deploy_ohne_mods_meldet_fehler(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    instance, game, _mods, profiles = _instance(tmp_path)
    write_global_modlist(profiles, [])
    write_active_mods(profiles / "Default", set())

    result = OverlayDeployer(instance, game).deploy()

    assert not result.success
    assert not (instance / OverlayDeployer.MANIFEST_NAME).exists()


def test_fehlender_spielordner_wird_gemeldet(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    instance.mkdir()
    (instance / ".profiles" / "Default").mkdir(parents=True)
    (instance / ".mods").mkdir()

    problems = OverlayDeployer(instance, tmp_path / "weg").check_requirements()

    assert any("Spielordner" in p for p in problems)


def test_dateisystem_wird_erkannt(tmp_path: Path) -> None:
    assert filesystem_of(tmp_path) != ""


def test_deploy_legt_den_startwrapper_an(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "x"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    deployer = OverlayDeployer(instance, game)
    deployer.deploy()

    assert deployer.wrapper.is_file()
    assert deployer.wrapper.stat().st_mode & 0o111
    assert deployer.steam_launch_option().endswith("%command%")


def test_mount_conf_enthaelt_alle_schichten(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "x"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    deployer = OverlayDeployer(instance, game)
    deployer.deploy()

    conf = dict(
        line.split("=", 1)
        for line in deployer.mount_conf_path.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    assert conf["GAME"] == str(game)
    assert conf["UPPER"] == str(instance / ".overwrite")
    assert conf["LOWER"].split(":") == [str(deployer.stage_dir), str(game)]


def test_diagnose_erkennt_den_overlay_deploy(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    from anvil.core.diagnostics import collect_deploy_status

    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "x"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    deployer = OverlayDeployer(instance, game)
    deployer.deploy()

    status = collect_deploy_status(instance)
    assert status["manifest"] is True
    assert status["mode"] == "overlay"
    assert status["total"] == 1
    assert status["broken"] == 0
    assert status["missing"] == 0


def test_diagnose_meldet_fehlende_schicht(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    import shutil as _shutil

    from anvil.core.diagnostics import collect_deploy_status

    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "x"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    deployer = OverlayDeployer(instance, game)
    deployer.deploy()
    _shutil.rmtree(deployer.stage_dir)

    assert collect_deploy_status(instance)["missing"] == 1


def test_diagnose_ohne_overlay_faellt_auf_symlinks_zurueck(tmp_path: Path) -> None:
    from anvil.core.diagnostics import collect_deploy_status

    instance, _game, _mods, _profiles = _instance(tmp_path)
    assert collect_deploy_status(instance) == {"manifest": False}


def test_purge_raeumt_auch_zugenagelte_arbeitsordner(
    tmp_path: Path, ohne_umgebungspruefung: None
) -> None:
    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "x"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    deployer = OverlayDeployer(instance, game)
    deployer.deploy()

    # So sieht das Arbeitsverzeichnis nach einem Mount aus
    gesperrt = deployer.work_dir / "work"
    gesperrt.mkdir(parents=True, exist_ok=True)
    gesperrt.chmod(0o000)

    result = deployer.purge()

    assert result.success, result.errors
    assert not deployer.work_dir.exists()
