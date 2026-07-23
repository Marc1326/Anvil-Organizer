from pathlib import Path

import pytest

from anvil.core.storage_markers import (
    StorageMarkerError,
    read_location_marker,
    verify_location_marker,
    write_location_marker,
)
from anvil.core.instance_manager import InstanceManager


def test_location_marker_round_trip(tmp_path: Path) -> None:
    root = tmp_path / "Mods"
    root.mkdir()

    marker_path = write_location_marker(root, instance_id="instance-123", component="mods")
    marker = read_location_marker(root)

    assert marker_path == root / ".anvil-location.json"
    assert marker.instance_id == "instance-123"
    assert marker.component == "mods"
    assert marker.version == 1
    assert verify_location_marker(root, "instance-123", "mods") == marker


def test_location_marker_rejects_wrong_instance_or_component(tmp_path: Path) -> None:
    root = tmp_path / "Mods"
    root.mkdir()
    write_location_marker(root, instance_id="instance-123", component="mods")

    with pytest.raises(StorageMarkerError, match="different instance"):
        verify_location_marker(root, "other-instance", "mods")
    with pytest.raises(StorageMarkerError, match="different component"):
        verify_location_marker(root, "instance-123", "profiles")


def test_location_marker_rejects_symlink_root(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)

    with pytest.raises(StorageMarkerError, match="symlink"):
        write_location_marker(link, instance_id="instance-123", component="mods")


def test_instance_manager_persists_stable_instance_id(tmp_path: Path) -> None:
    manager = InstanceManager(tmp_path / "instances")
    instance = manager.instances_path() / "Game"
    instance.mkdir()
    (instance / ".anvil.ini").write_text(
        "[General]\ngame_name=Game\n[Paths]\nmods_directory=%INSTANCE_DIR%/.mods\n",
        encoding="utf-8",
    )

    first = manager.ensure_instance_id("Game")
    second = manager.ensure_instance_id("Game")

    assert first == second
    assert len(first) == 36
    assert manager.load_instance("Game")["instance_id"] == first
