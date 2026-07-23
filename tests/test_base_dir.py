from pathlib import Path

from PySide6.QtCore import QSettings

from anvil.core.base_dir import (
    AnvilBasePaths,
    configure_base_dir,
    resolve_base_dir,
)
from anvil.core.instance_manager import InstanceManager


def test_custom_base_dir_is_single_source_for_derived_paths(tmp_path: Path) -> None:
    config = QSettings(str(tmp_path / "AnvilOrganizer.conf"), QSettings.Format.IniFormat)
    custom = tmp_path / "External Anvil"
    config.setValue("General/base_dir", str(custom))
    config.sync()

    paths = AnvilBasePaths(resolve_base_dir(config))

    assert paths.base == custom
    assert paths.instances == custom / "instances"
    assert paths.logs == custom / "logs"
    assert paths.user_plugins == custom / "plugins" / "games"
    assert paths.credentials == custom / "credentials.json"
    assert paths.current_instance == custom / ".current"
    assert paths.socket == custom / "instance.sock"
    assert not custom.exists()


def test_relative_base_dir_falls_back_to_legacy_home(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    config = QSettings(str(tmp_path / "AnvilOrganizer.conf"), QSettings.Format.IniFormat)
    config.setValue("General/base_dir", "relative/path")
    config.sync()

    assert resolve_base_dir(config) == Path.home() / ".anvil-organizer"


def test_instance_manager_does_not_recreate_missing_custom_base(tmp_path: Path) -> None:
    config = QSettings(str(tmp_path / "AnvilOrganizer.conf"), QSettings.Format.IniFormat)
    missing = tmp_path / "Unmounted Anvil"
    config.setValue("General/base_dir", str(missing))
    config.sync()

    try:
        InstanceManager(settings=config)
    except FileNotFoundError as exc:
        assert str(missing) in str(exc)
    else:
        raise AssertionError("missing custom base was accepted")
    assert not missing.exists()


def test_configure_base_dir_can_create_intentionally_selected_target(tmp_path: Path) -> None:
    config = QSettings(str(tmp_path / "AnvilOrganizer.conf"), QSettings.Format.IniFormat)
    selected = tmp_path / "selected" / "Anvil"

    configured = configure_base_dir(selected, settings=config, create=True)

    assert configured == selected
    assert selected.is_dir()
    assert resolve_base_dir(config) == selected


def test_recovery_refuses_to_create_missing_target(tmp_path: Path) -> None:
    config = QSettings(str(tmp_path / "AnvilOrganizer.conf"), QSettings.Format.IniFormat)
    missing = tmp_path / "missing"

    try:
        configure_base_dir(missing, settings=config, create=False)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("recovery created a missing target")
    assert not missing.exists()
