from pathlib import Path

import pytest

from anvil.core.instance_paths import (
    resolve_instance_paths,
    unavailable_configured_storage,
)
from anvil.core.collection_io import CollectionManifest, apply_collection
from anvil.core.mod_deployer import ModDeployer
from anvil.core.mod_list_io import write_active_mods, write_global_modlist
from anvil.mainwindow import _first_unavailable_storage


def test_missing_custom_root_is_reported_without_creating_it(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    missing_mods = tmp_path / "missing-drive" / "Mods"
    data = {"path_mods_directory": str(missing_mods)}
    paths = resolve_instance_paths(instance, data)

    unavailable = unavailable_configured_storage(paths, data)

    assert len(unavailable) == 1
    assert unavailable[0].component == "mods"
    assert unavailable[0].path == missing_mods.absolute()
    assert unavailable[0].exists is False
    assert unavailable[0].is_directory is False
    assert unavailable[0].readable is False
    assert unavailable[0].writable is False
    assert not missing_mods.exists()
    assert not instance.exists()


def test_missing_legacy_defaults_are_not_external_offline_roots(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    data = {
        "path_mods_directory": "%INSTANCE_DIR%/.mods",
        "path_downloads_directory": "%INSTANCE_DIR%/.downloads",
        "path_profiles_directory": "%INSTANCE_DIR%/.profiles",
        "path_overwrite_directory": "%INSTANCE_DIR%/.overwrite",
    }
    paths = resolve_instance_paths(instance, data)

    assert unavailable_configured_storage(paths, data) == []
    assert not instance.exists()


@pytest.mark.parametrize("missing_component", ["mods", "profiles"])
def test_deployer_fails_closed_when_external_root_is_missing(
    tmp_path: Path,
    missing_component: str,
) -> None:
    instance = tmp_path / "Instance"
    game = tmp_path / "Game"
    mods = tmp_path / "External Mods"
    profiles = tmp_path / "External Profiles"
    profile = profiles / "Default"
    instance.mkdir()
    game.mkdir()
    if missing_component != "mods":
        (mods / "Example Mod").mkdir(parents=True)
        (mods / "Example Mod" / "example.bin").write_bytes(b"mod")
    if missing_component != "profiles":
        profile.mkdir(parents=True)
        write_global_modlist(profiles, ["Example Mod"])
        write_active_mods(profile, {"Example Mod"})

    result = ModDeployer(
        instance,
        game,
        profile_name="Default",
        mods_path=mods,
        profiles_path=profiles,
    ).deploy()

    missing_path = mods if missing_component == "mods" else profiles
    assert result.success is False
    assert any(str(missing_path) in error for error in result.errors)
    assert list(game.iterdir()) == []
    assert not (instance / ModDeployer.MANIFEST_NAME).exists()
    assert not missing_path.exists()


def test_collection_apply_does_not_create_missing_external_root(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    missing_mods = tmp_path / "missing-drive" / "Mods"
    profiles = tmp_path / "External Profiles"
    profile = profiles / "Default"
    instance.mkdir()
    profile.mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match=str(missing_mods)):
        apply_collection(
            CollectionManifest(),
            instance,
            profile,
            mods_path=missing_mods,
            profiles_path=profiles,
        )

    assert not missing_mods.exists()
    assert not (instance / ".mods").exists()


def test_mainwindow_storage_gate_reports_exact_missing_path(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    missing_profiles = tmp_path / "offline-disk" / "Profiles"
    data = {"path_profiles_directory": str(missing_profiles)}
    paths = resolve_instance_paths(instance, data)

    status = _first_unavailable_storage(paths, data)

    assert status is not None
    assert status.component == "profiles"
    assert status.path == missing_profiles.absolute()
    assert not missing_profiles.exists()


def test_profile_guard_rejects_missing_external_profiles_root(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    missing_profiles = tmp_path / "offline-disk" / "Profiles"

    with pytest.raises(ValueError, match="unavailable"):
        from anvil.core.profile_name import safe_profile_directory

        safe_profile_directory(
            instance,
            "New",
            profiles_root=missing_profiles,
        )

    assert not missing_profiles.exists()
