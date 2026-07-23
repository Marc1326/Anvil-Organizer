from pathlib import Path

import pytest

from anvil.core.instance_paths import resolve_instance_paths


def test_resolve_instance_paths_uses_legacy_defaults(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"

    paths = resolve_instance_paths(instance, {})

    assert paths.instance == instance.absolute()
    assert paths.mods == instance.absolute() / ".mods"
    assert paths.downloads == instance.absolute() / ".downloads"
    assert paths.profiles == instance.absolute() / ".profiles"
    assert paths.overwrite == instance.absolute() / ".overwrite"
    assert paths.backups == instance.absolute() / ".backups"
    assert paths.cache == instance.absolute() / ".webcache"


def test_resolve_instance_paths_uses_absolute_external_roots(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    external = tmp_path / "Externe Platte ü"
    data = {
        "path_mods_directory": str(external / "Meine Mods"),
        "path_downloads_directory": str(external / "Downloads"),
        "path_profiles_directory": str(external / "Profile"),
        "path_overwrite_directory": str(external / "Overwrite"),
        "path_backups_directory": str(external / "Backups"),
        "path_cache_directory": str(external / "Cache"),
    }

    paths = resolve_instance_paths(instance, data)

    assert paths.mods == (external / "Meine Mods").absolute()
    assert paths.downloads == (external / "Downloads").absolute()
    assert paths.profiles == (external / "Profile").absolute()
    assert paths.overwrite == (external / "Overwrite").absolute()
    assert paths.backups == (external / "Backups").absolute()
    assert paths.cache == (external / "Cache").absolute()


def test_resolve_instance_paths_expands_leading_instance_placeholder(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"

    paths = resolve_instance_paths(
        instance,
        {
            "path_mods_directory": "%INSTANCE_DIR%/.mods-custom",
            "path_profiles_directory": "%INSTANCE_DIR%/profiles/custom",
        },
    )

    assert paths.mods == instance.absolute() / ".mods-custom"
    assert paths.profiles == instance.absolute() / "profiles" / "custom"


def test_resolve_instance_paths_never_creates_missing_roots(tmp_path: Path) -> None:
    instance = tmp_path / "missing-instance"
    external = tmp_path / "missing-drive" / "mods"

    paths = resolve_instance_paths(
        instance,
        {"path_mods_directory": str(external)},
    )

    assert paths.mods == external.absolute()
    assert not instance.exists()
    assert not external.exists()


@pytest.mark.parametrize(
    "invalid",
    [
        "relative/mods",
        "/tmp/prefix/%INSTANCE_DIR%/mods",
        "%INSTANCE_DIR%oops",
        "%INSTANCE_DIR%/../outside",
        "bad\0path",
    ],
)
def test_resolve_instance_paths_rejects_invalid_custom_values(
    tmp_path: Path,
    invalid: str,
) -> None:
    with pytest.raises(ValueError):
        resolve_instance_paths(
            tmp_path / "Instance",
            {"path_mods_directory": invalid},
        )
