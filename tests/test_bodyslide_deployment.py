from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from anvil.core.archive_packing import is_archive_loose_path
from anvil.core.ba2_packer import BA2Packer
from anvil.core.mod_deployer import ModDeployer
from anvil.core.mod_list_io import write_active_mods, write_global_modlist
from anvil.plugins.games.game_fallout4 import Fallout4Game
from anvil.plugins.games.game_skyrimse import SkyrimSEGame
from anvil.widgets.game_panel import GamePanel


def _bodyslide_library(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    instance = tmp_path / "Instance"
    game = tmp_path / "Game"
    mods = instance / ".mods"
    profiles = instance / ".profiles"
    profile = profiles / "Default"
    mod = mods / "BodySlide Assets"

    for path in (instance, game, profile):
        path.mkdir(parents=True, exist_ok=True)
    (mod / "CalienteTools" / "BodySlide" / "SliderSets").mkdir(
        parents=True
    )
    (mod / "CalienteTools" / "BodySlide" / "SliderPresets").mkdir(
        parents=True
    )
    (mod / "meshes" / "actors" / "character").mkdir(parents=True)
    (mod / "CalienteTools" / "BodySlide" / "SliderSets" / "TestBody.osp").write_text(
        "project",
        encoding="utf-8",
    )
    (mod / "CalienteTools" / "BodySlide" / "SliderPresets" / "Test.xml").write_text(
        "preset",
        encoding="utf-8",
    )
    (mod / "meshes" / "actors" / "character" / "body.nif").write_bytes(b"mesh")
    (mod / "BodySlide.esp").write_bytes(b"plugin")
    write_global_modlist(profiles, ["BodySlide Assets"])
    write_active_mods(profile, {"BodySlide Assets"})
    return instance, game, mods, mod


def test_bodyslide_tool_files_stay_loose_during_ba2_deployment(
    tmp_path: Path,
) -> None:
    instance, game, _mods, mod = _bodyslide_library(tmp_path)
    deployer = ModDeployer(
        instance,
        game,
        data_path="Data",
        needs_ba2_packing=True,
        ba2_loose_paths=["CalienteTools"],
    )

    result = deployer.deploy()

    project = game / "Data" / "CalienteTools" / "BodySlide" / "SliderSets" / "TestBody.osp"
    preset = game / "Data" / "CalienteTools" / "BodySlide" / "SliderPresets" / "Test.xml"
    mesh = game / "Data" / "meshes" / "actors" / "character" / "body.nif"
    plugin = game / "Data" / "BodySlide.esp"
    assert result.success is True
    assert project.is_symlink()
    assert project.resolve() == mod / "CalienteTools" / "BodySlide" / "SliderSets" / "TestBody.osp"
    assert preset.is_symlink()
    assert not mesh.exists()
    assert plugin.is_symlink()

    purge = deployer.purge()

    assert purge.success is True
    assert not project.exists()
    assert not project.is_symlink()
    assert (
        mod / "CalienteTools" / "BodySlide" / "SliderSets" / "TestBody.osp"
    ).is_file()


def test_ba2_staging_excludes_bodyslide_tool_files(tmp_path: Path) -> None:
    instance, game, mods, _mod = _bodyslide_library(tmp_path)

    class SkyrimPlugin:
        GameDataPath = "Data"
        Ba2LoosePaths = ["CalienteTools"]

        @staticmethod
        def gameDirectory() -> Path:
            return game

    staging = tmp_path / "staging"
    packer = BA2Packer(SkyrimPlugin(), instance, mods_path=mods)
    general, textures, skipped = packer._stage_mod_files(
        mods / "BodySlide Assets",
        staging,
    )

    assert (general, textures, skipped) == (1, 0, 3)
    assert (staging / "general" / "meshes" / "actors" / "character" / "body.nif").is_file()
    assert not (staging / "general" / "CalienteTools").exists()


def test_bethesda_plugins_keep_calientetools_loose() -> None:
    assert SkyrimSEGame.Ba2LoosePaths == ["CalienteTools"]
    assert Fallout4Game.Ba2LoosePaths == ["CalienteTools"]


def test_bodyslide_loose_path_matching_normalizes_common_mod_roots() -> None:
    for rel_path in (
        "CalienteTools/BodySlide/Test.osp",
        "Data/calientetools/BodySlide/Test.osp",
        "root/DATA/CALIENTETOOLS/BodySlide/Test.osp",
    ):
        assert is_archive_loose_path(
            rel_path,
            ["CalienteTools"],
            "Data",
        )


def test_game_panel_passes_ba2_loose_paths_to_standard_deployer(
    tmp_path: Path,
) -> None:
    instance, game, mods, _mod = _bodyslide_library(tmp_path)

    class Panel:
        _current_plugin = SkyrimSEGame()
        _mod_index = None
        _separator_deploy_paths: dict[str, str] = {}
        _mods_path = mods
        _profiles_path = instance / ".profiles"

    deployer = GamePanel._create_deployer(
        cast(Any, Panel()),
        instance,
        game,
        "Default",
    )

    assert isinstance(deployer, ModDeployer)
    assert deployer._ba2_loose_paths == ["CalienteTools"]


def _ba2_panel(instance: Path, game: Path, mods: Path) -> Any:
    class Plugin:
        NeedsBa2Packing = True
        GameDataPath = "Data"
        Ba2LoosePaths = ["CalienteTools"]
        ProtonShimFiles: list[str] = []

        @staticmethod
        def gameDirectory() -> Path:
            return game

        @staticmethod
        def has_plugins_txt() -> bool:
            return False

    deployer = ModDeployer(
        instance,
        game,
        data_path="Data",
        needs_ba2_packing=True,
        ba2_loose_paths=["CalienteTools"],
    )
    return SimpleNamespace(
        _current_plugin=Plugin(),
        _current_game_path=game,
        _instance_path=instance,
        _mods_path=mods,
        _profiles_path=instance / ".profiles",
        _current_profile_name="Default",
        _deployer=deployer,
        _apply_proton_dll_overrides=lambda: None,
        _refresh_skipped_mods=lambda: None,
    )


def test_missing_bsarch_falls_back_to_complete_loose_deployment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    instance, game, mods, _mod = _bodyslide_library(tmp_path)
    panel = _ba2_panel(instance, game, mods)
    monkeypatch.setattr(BA2Packer, "is_available", lambda self: False)

    result = cast(Any, GamePanel.silent_deploy(panel))

    mesh = game / "Data" / "meshes" / "actors" / "character" / "body.nif"
    assert result.success is True
    assert mesh.is_symlink()


def test_fast_redeploy_is_always_complete_loose_deployment(
    tmp_path: Path,
) -> None:
    instance, game, mods, _mod = _bodyslide_library(tmp_path)
    panel = _ba2_panel(instance, game, mods)

    result = cast(Any, GamePanel.silent_deploy_fast(panel))

    mesh = game / "Data" / "meshes" / "actors" / "character" / "body.nif"
    assert result.success is True
    assert mesh.is_symlink()


def test_ba2_pack_failure_marks_deployment_failed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    instance, game, mods, _mod = _bodyslide_library(tmp_path)
    panel = _ba2_panel(instance, game, mods)
    monkeypatch.setattr(BA2Packer, "is_available", lambda self: True)
    monkeypatch.setattr(
        BA2Packer,
        "pack_all_mods",
        lambda self, enabled: SimpleNamespace(
            success=False,
            errors=["injected packing failure"],
            ba2_paths=[],
        ),
    )

    result = cast(Any, GamePanel.silent_deploy(panel))

    assert result.success is False
    assert "injected packing failure" in result.errors
