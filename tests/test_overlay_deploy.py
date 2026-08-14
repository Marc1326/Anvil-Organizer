import json
from pathlib import Path

import pytest

from anvil.core.mod_list_io import write_active_mods, write_global_modlist
from anvil.core.overlay_deployer import OverlayDeployer, filesystem_of
from anvil.core.overlay_staging import OverlayStage, is_metadata, target_rel


@pytest.fixture
def ohne_umgebungspruefung(monkeypatch: pytest.MonkeyPatch) -> None:
    """Testverzeichnisse liegen auf tmpfs -- die Umgebungspruefung wuerde greifen.

    Der Mount selbst bleibt aus: pkexec hat in Tests nichts zu suchen.
    """
    monkeypatch.setattr(OverlayDeployer, "check_requirements", lambda self: [])
    monkeypatch.setattr(
        "anvil.core.overlay_deployer.mount", lambda *a, **k: (True, "")
    )
    monkeypatch.setattr(
        "anvil.core.overlay_deployer.unmount", lambda *a, **k: (True, "")
    )
    monkeypatch.setattr(
        "anvil.core.overlay_deployer.purge_mounts", lambda *a, **k: (True, "")
    )


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
    gemeinsam = tmp_path / "stage" / "main" / "archive" / "gemeinsam.archive"
    assert gemeinsam.read_text(encoding="utf-8") == "oben"
    assert (tmp_path / "stage" / "main" / "archive" / "nur_unten.archive").is_file()


def test_dokumentation_im_wurzelverzeichnis_bleibt_draussen(tmp_path: Path) -> None:
    mods, profiles = _library(tmp_path)
    _mod(mods, "M", {"liesmich.txt": "hallo", "archive/a.archive": "gut"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    OverlayStage(mods, profiles).build(tmp_path / "stage")

    assert (tmp_path / "stage" / "main" / "archive" / "a.archive").is_file()
    assert not (tmp_path / "stage" / "main" / "liesmich.txt").exists()


def test_ausgeschlossene_pfade_kommen_nicht_in_die_schicht(tmp_path: Path) -> None:
    """Spieleigene Live-Dateien duerfen das Original nicht ueberdecken."""
    mods, profiles = _library(tmp_path)
    _mod(mods, "M", {
        "r6/config/settings/platform/pc/options.json": "{}",
        "r6/scripts/laeuft.reds": "// ok",
    })
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    stage = OverlayStage(
        mods, profiles,
        stage_exclude_paths=["r6/config/settings/platform/pc/options.json"],
    )
    stage.build(tmp_path / "stage")

    assert not (tmp_path / "stage" / "main" / "r6/config/settings/platform/pc/options.json").exists()
    assert (tmp_path / "stage" / "main" / "r6/scripts/laeuft.reds").is_file()


def test_metadaten_kommen_nicht_in_die_schicht(tmp_path: Path) -> None:
    mods, profiles = _library(tmp_path)
    _mod(mods, "M", {"meta.ini": "x", "fomod/info.xml": "x", "a.archive": "gut"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    OverlayStage(mods, profiles).build(tmp_path / "stage")

    assert (tmp_path / "stage" / "main" / "a.archive").is_file()
    assert not (tmp_path / "stage" / "main" / "meta.ini").exists()
    assert not (tmp_path / "stage" / "main" / "fomod").exists()


def test_inaktive_mods_bleiben_draussen(tmp_path: Path) -> None:
    mods, profiles = _library(tmp_path)
    _mod(mods, "An", {"archive/an.archive": "x"})
    _mod(mods, "Aus", {"archive/aus.archive": "x"})
    write_global_modlist(profiles, ["An", "Aus"])
    write_active_mods(profiles / "Default", {"An"})

    OverlayStage(mods, profiles).build(tmp_path / "stage")

    assert (tmp_path / "stage" / "main" / "archive" / "an.archive").is_file()
    assert not (tmp_path / "stage" / "main" / "archive" / "aus.archive").exists()


def test_frameworks_kommen_auch_ohne_haken_mit(tmp_path: Path) -> None:
    mods, profiles = _library(tmp_path)
    _mod(mods, "RED4ext", {"root/bin/x64/winmm.dll": "dll"})
    write_global_modlist(profiles, ["RED4ext"])
    write_active_mods(profiles / "Default", set())

    stage = OverlayStage(mods, profiles, direct_patterns=["RED4ext"])
    stage.build(tmp_path / "stage")

    assert (tmp_path / "stage" / "main" / "bin" / "x64" / "winmm.dll").is_file()


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
    assert manifest["mounts"] == [
        {"target": str(game), "lowerdirs": [str(deployer.stage_dir), str(game)]}
    ]
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


def test_deploy_legt_das_helferskript_an(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    from anvil.core.overlay_mount import helper_path

    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "x"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    deployer = OverlayDeployer(instance, game)
    deployer.deploy()

    helfer = helper_path(instance)
    assert helfer.is_file()
    assert helfer.stat().st_mode & 0o111


def test_mount_conf_enthaelt_alle_schichten(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "x"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    deployer = OverlayDeployer(instance, game)
    deployer.deploy()

    zeilen = [
        z for z in deployer.mount_conf_path.read_text(encoding="utf-8").splitlines()
        if z.startswith("MOUNT=")
    ]
    assert len(zeilen) == 1
    ziel, lower, upper, work = zeilen[0][len("MOUNT="):].split("|")
    assert ziel == str(game)
    assert lower.split(":") == [str(deployer.stage_dir), str(game)]
    assert upper == str(instance / ".overwrite")
    assert work.startswith(str(deployer.work_dir))


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


def test_alter_symlink_deploy_wird_weggeraeumt(
    tmp_path: Path, ohne_umgebungspruefung: None
) -> None:
    from anvil.core.mod_deployer import ModDeployer

    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "x"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    symlink = ModDeployer(instance, game)
    symlink.deploy()
    assert (game / "archive" / "a.archive").is_symlink()

    OverlayDeployer(instance, game).deploy()

    assert not (game / "archive" / "a.archive").exists()
    assert not (instance / ModDeployer.MANIFEST_NAME).exists()
    assert sorted(p.name for p in game.iterdir()) == ["spiel.exe"]


def test_ohne_alten_deploy_wird_der_spielordner_nicht_durchsucht(
    tmp_path: Path, ohne_umgebungspruefung: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from anvil.core import mod_deployer as md

    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "x"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    gerufen = []
    monkeypatch.setattr(
        md.ModDeployer, "remove_orphaned_links",
        lambda self: gerufen.append(1) or 0,
    )

    OverlayDeployer(instance, game).deploy()

    assert gerufen == []


def test_ba2_schalter_wird_durchgereicht(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"meshes/a.nif": "x", "b.esp": "x"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    deployer = OverlayDeployer(instance, game, data_path="Data")
    deployer.set_ba2_packing_enabled(True)
    deployer.deploy()

    assert (deployer.stage_dir / "Data" / "b.esp").is_file()
    assert not (deployer.stage_dir / "Data" / "meshes" / "a.nif").exists()


def test_trennerpfade_nach_dem_konstruktor_wirken(
    tmp_path: Path, ohne_umgebungspruefung: None
) -> None:
    """Die Oberflaeche setzt die Trennerpfade erst nach dem Bau des Deployers."""
    instance, game, mods, profiles = _instance(tmp_path)
    anderswo = tmp_path / "Anderswo"
    anderswo.mkdir()
    _mod(mods, "Woanders", {"archive/a.archive": "x"})
    write_global_modlist(profiles, ["extern_separator", "Woanders"])
    write_active_mods(profiles / "Default", {"extern_separator", "Woanders"})

    deployer = OverlayDeployer(instance, game)
    deployer.set_separator_deploy_paths({"extern_separator": str(anderswo)})
    deployer.deploy()

    assert str(anderswo) in deployer.stage_dirs()
    ziele = [str(z) for z, _ in deployer.mounts()]
    assert str(anderswo) in ziele


def test_datei_gegen_ordner_stuerzt_nicht_ab(
    tmp_path: Path, ohne_umgebungspruefung: None
) -> None:
    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "Unten", {"archive/x/tief.archive": "ordner"})
    _mod(mods, "Oben", {"archive/x": "datei"})
    write_global_modlist(profiles, ["Oben", "Unten"])
    write_active_mods(profiles / "Default", {"Oben", "Unten"})

    result = OverlayDeployer(instance, game).deploy()

    assert not result.success
    assert any("Ordner" in e or "belegt" in e for e in result.errors), result.errors


def test_abschalten_raeumt_mount_und_schicht_weg(
    tmp_path: Path, ohne_umgebungspruefung: None
) -> None:
    """Nach dem Purge gibt es weder Mount-Angaben noch Schicht noch Manifest."""
    instance, game, mods, profiles = _instance(tmp_path)
    _mod(mods, "M", {"archive/a.archive": "x"})
    write_global_modlist(profiles, ["M"])
    write_active_mods(profiles / "Default", {"M"})

    deployer = OverlayDeployer(instance, game)
    deployer.deploy()
    assert deployer.mount_conf_path.is_file()

    deployer.purge()

    assert not deployer.mount_conf_path.exists()
    assert not deployer.is_deployed()
    assert not deployer.stage_root.exists()


def test_plugin_scan_findet_die_schicht(tmp_path: Path) -> None:
    """Im Overlay stehen die Plugins nicht im Spielordner, sondern in der Schicht."""
    from anvil.core.plugins_txt_writer import PluginsTxtWriter

    class Plugin:
        GameDataPath = "Data"
        GamePrimaryPlugins: list[str] = []

    game = tmp_path / "Game"
    stage = tmp_path / "stage"
    instance = tmp_path / "Instance"
    (game / "Data").mkdir(parents=True)
    (stage / "Data").mkdir(parents=True)
    (instance / ".profiles" / "Default").mkdir(parents=True)
    (game / "Data" / "Vanilla.esm").write_bytes(b"x")
    (stage / "Data" / "AusDerMod.esp").write_bytes(b"x")

    writer = PluginsTxtWriter(Plugin(), game, instance, profile_name="Default")
    ohne = writer.scan_plugins()
    writer.set_extra_scan_roots([stage])
    mit = writer.scan_plugins()

    assert "AusDerMod.esp" not in ohne
    assert "AusDerMod.esp" in mit
    assert "Vanilla.esm" in mit
