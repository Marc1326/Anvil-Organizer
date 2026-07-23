from pathlib import Path

import pytest

from anvil.core import storage_inventory
from anvil.core.instance_paths import InstancePaths
from anvil.core.storage_inventory import (
    InventoryCancelled,
    InventoryProgress,
    inspect_destination,
    inventory_components,
    inventory_directory,
)


def test_inventory_counts_files_and_symlinks_without_following_them(tmp_path: Path) -> None:
    source = tmp_path / "source"
    external = tmp_path / "external"
    (source / "nested").mkdir(parents=True)
    external.mkdir()
    (source / "one.bin").write_bytes(b"1234")
    (source / "nested" / "two.bin").write_bytes(b"123456")
    (external / "must-not-count.bin").write_bytes(b"x" * 100)
    (source / "external-link").symlink_to(external, target_is_directory=True)

    result = inventory_directory(source)

    assert result.root == source
    assert result.file_count == 2
    assert result.directory_count == 1
    assert result.symlink_count == 1
    assert result.total_bytes == 10
    assert result.unreadable == []
    assert result.device_id == source.stat().st_dev


def test_inventory_can_be_cancelled(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for index in range(10):
        (source / f"file-{index}.bin").write_bytes(b"data")

    checks = 0

    def cancel_requested() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 3

    with pytest.raises(InventoryCancelled):
        inventory_directory(source, cancel_requested=cancel_requested)


def test_inventory_selected_instance_components(tmp_path: Path) -> None:
    instance = tmp_path / "instance"
    external = tmp_path / "external"
    roots = {
        "mods": external / "Mods",
        "downloads": external / "Downloads",
        "profiles": external / "Profiles",
        "overwrite": external / "Overwrite",
        "backups": external / "Backups",
        "cache": external / "Cache",
    }
    instance.mkdir()
    for name, root in roots.items():
        root.mkdir(parents=True)
        (root / f"{name}.bin").write_bytes(name.encode())

    paths = InstancePaths(instance=instance, **roots)
    results = inventory_components(paths, ["mods", "cache", "instance"])

    assert list(results) == ["mods", "cache", "instance"]
    assert results["mods"].root == roots["mods"]
    assert results["mods"].total_bytes == len(b"mods")
    assert results["cache"].root == roots["cache"]
    assert results["instance"].root == instance


def test_inventory_reports_immutable_progress_snapshots(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "one.bin").write_bytes(b"1234")
    (source / "two.bin").write_bytes(b"123456")
    updates: list[InventoryProgress] = []

    result = inventory_directory(source, progress=updates.append)

    assert updates
    assert updates[-1].file_count == result.file_count == 2
    assert updates[-1].total_bytes == result.total_bytes == 10
    assert updates[-1].current_path in {source / "one.bin", source / "two.bin"}


def test_destination_inspection_uses_nearest_existing_parent(tmp_path: Path) -> None:
    target = tmp_path / "new" / "nested" / "Mods"

    result = inspect_destination(target)

    usage = __import__("shutil").disk_usage(tmp_path)
    assert result.path == target
    assert result.existing_parent == tmp_path
    assert result.device_id == tmp_path.stat().st_dev
    assert result.total_bytes == usage.total
    assert result.free_bytes <= usage.free
    assert result.free_bytes > 0


def test_inventory_rejects_symlink_as_component_root(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        inventory_directory(link)


def test_inventory_reports_unreadable_directories(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    blocked = source / "blocked"
    blocked.mkdir(parents=True)
    original_scandir = storage_inventory.os.scandir

    def fail_for_blocked(path):
        if Path(path) == blocked:
            raise PermissionError("blocked for test")
        return original_scandir(path)

    monkeypatch.setattr(storage_inventory.os, "scandir", fail_for_blocked)
    result = inventory_directory(source)

    assert len(result.unreadable) == 1
    assert str(blocked) in result.unreadable[0]
    assert "blocked for test" in result.unreadable[0]
