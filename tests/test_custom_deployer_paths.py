import json
from pathlib import Path

from anvil.core.grb_deployer import GRBDeployer
from typing import Any, cast

import pytest

from anvil.core.ba2_packer import BA2Packer
from anvil.core.mod_deployer import ModDeployer
from anvil.core.mod_list_io import write_active_mods, write_global_modlist
from anvil.widgets.game_panel import GamePanel


def _deployment_library(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    instance = tmp_path / "Instance"
    game = tmp_path / "Game"
    mods = tmp_path / "External Mods"
    profiles = tmp_path / "External Profiles"
    profile = profiles / "Default"
    instance.mkdir()
    game.mkdir()
    (mods / "Example Mod" / "Data").mkdir(parents=True)
    (mods / "Example Mod" / "Data" / "example.bin").write_bytes(b"mod")
    profile.mkdir(parents=True)
    write_global_modlist(profiles, ["Example Mod"])
    write_active_mods(profile, {"Example Mod"})
    return instance, game, mods, profiles, profile


def test_deployer_uses_external_mods_and_profiles_roots(tmp_path: Path) -> None:
    instance, game, mods, profiles, _profile = _deployment_library(tmp_path)
    deployer = ModDeployer(
        instance,
        game,
        profile_name="Default",
        mods_path=mods,
        profiles_path=profiles,
    )

    result = deployer.deploy()

    deployed = game / "Data" / "example.bin"
    assert result.success is True
    assert deployed.is_symlink()
    assert deployed.resolve() == mods / "Example Mod" / "Data" / "example.bin"
    assert (instance / ModDeployer.MANIFEST_NAME).is_file()
    assert not (instance / ".mods").exists()
    assert not (instance / ".profiles").exists()

    purge = deployer.purge()

    assert purge.success is True
    assert not deployed.exists()
    assert not deployed.is_symlink()
    assert not (instance / ModDeployer.MANIFEST_NAME).exists()


def test_grb_deployer_accepts_resolved_mods_and_profiles_roots(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    game = tmp_path / "Game"
    mods = tmp_path / "External Mods"
    profiles = tmp_path / "External Profiles"
    for path in (instance, game, mods, profiles / "Default"):
        path.mkdir(parents=True, exist_ok=True)

    deployer = GRBDeployer(
        instance,
        game,
        "Default",
        mods_path=mods,
        profiles_path=profiles,
    )

    assert deployer.mods_path == mods
    assert deployer.profiles_path == profiles
    assert deployer.profile_path == profiles / "Default"


@pytest.mark.parametrize("deploy_type", ["symlink", "dir_symlink"])
def test_purge_preserves_links_outside_external_mods_root(
    tmp_path: Path,
    deploy_type: str,
) -> None:
    instance, game, mods, profiles, _profile = _deployment_library(tmp_path)
    foreign_root = tmp_path / "External Mods Evil"
    foreign_root.mkdir()
    target = foreign_root / "foreign"
    if deploy_type == "dir_symlink":
        target.mkdir()
    else:
        target.write_bytes(b"foreign")
    link = game / "foreign-link"
    link.symlink_to(target, target_is_directory=deploy_type == "dir_symlink")
    manifest = {
        "game_path": str(game),
        "symlinks": [
            {
                "link": link.name,
                "target": str(target),
                "mod": "Foreign",
                "type": deploy_type,
            }
        ],
        "created_dirs": [],
    }
    (instance / ModDeployer.MANIFEST_NAME).write_text(json.dumps(manifest))
    deployer = ModDeployer(
        instance,
        game,
        mods_path=mods,
        profiles_path=profiles,
    )

    result = deployer.purge()

    assert link.is_symlink()
    assert result.links_removed == 0
    assert result.errors


def test_game_panel_factory_passes_external_roots_to_standard_deployer(tmp_path: Path) -> None:
    instance, game, mods, profiles, _profile = _deployment_library(tmp_path)

    class FakePanel:
        _current_plugin = None
        _mod_index = None
        _separator_deploy_paths: dict[str, str] = {}
        _keep_file_name_mods: set = set()
        _mods_path = mods
        _profiles_path = profiles

    deployer = GamePanel._create_deployer(
        cast(Any, FakePanel()),
        instance,
        game,
        "Default",
    )

    assert isinstance(deployer, ModDeployer)
    assert deployer._mods_path == mods
    assert deployer._profiles_dir == profiles


def test_ba2_packer_uses_external_mods_root(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    mods = tmp_path / "External Mods"

    class GamePlugin:
        GameDataPath = "Data"

        @staticmethod
        def gameDirectory() -> None:
            return None

    packer = BA2Packer(
        GamePlugin(),
        instance,
        mods_path=mods,
    )

    assert packer._mods_path == mods
