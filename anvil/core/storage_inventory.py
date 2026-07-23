from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from anvil.core.instance_paths import InstancePaths


class InventoryCancelled(Exception):
    pass


@dataclass(frozen=True, slots=True)
class InventoryProgress:
    current_path: Path
    file_count: int
    directory_count: int
    symlink_count: int
    total_bytes: int


@dataclass(slots=True)
class StorageInventory:
    root: Path
    file_count: int = 0
    directory_count: int = 0
    symlink_count: int = 0
    total_bytes: int = 0
    device_id: int = 0
    unreadable: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class DestinationCapacity:
    path: Path
    existing_parent: Path
    device_id: int
    total_bytes: int
    free_bytes: int


def inventory_directory(
    root: Path,
    *,
    cancel_requested: Callable[[], bool] | None = None,
    progress: Callable[[InventoryProgress], None] | None = None,
    excluded_relative_paths: tuple[Path, ...] = (),
) -> StorageInventory:
    root = Path(root)
    excluded = {Path(path) for path in excluded_relative_paths}
    if any(path.is_absolute() or ".." in path.parts for path in excluded):
        raise ValueError("inventory exclusions must be safe relative paths")
    if root.is_symlink():
        raise ValueError(f"storage root must not be a symlink: {root}")
    root_stat = root.stat()
    if not root.is_dir():
        raise NotADirectoryError(root)

    result = StorageInventory(root=root, device_id=root_stat.st_dev)
    pending = [root]

    while pending:
        if cancel_requested is not None and cancel_requested():
            raise InventoryCancelled
        directory = pending.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            result.unreadable.append(f"{directory}: {exc}")
            continue

        for entry in entries:
            if cancel_requested is not None and cancel_requested():
                raise InventoryCancelled
            entry_path = Path(entry.path)
            relative = entry_path.relative_to(root)
            if any(relative == path or path in relative.parents for path in excluded):
                continue
            try:
                if entry.is_symlink():
                    result.symlink_count += 1
                elif entry.is_dir(follow_symlinks=False):
                    result.directory_count += 1
                    pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    result.file_count += 1
                    result.total_bytes += entry.stat(follow_symlinks=False).st_size
                if progress is not None:
                    progress(
                        InventoryProgress(
                            current_path=Path(entry.path),
                            file_count=result.file_count,
                            directory_count=result.directory_count,
                            symlink_count=result.symlink_count,
                            total_bytes=result.total_bytes,
                        )
                    )
            except OSError as exc:
                result.unreadable.append(f"{entry.path}: {exc}")

    return result


_COMPONENTS = {
    "mods",
    "downloads",
    "profiles",
    "overwrite",
    "backups",
    "cache",
    "instance",
}


def inventory_components(
    paths: InstancePaths,
    components: list[str],
    *,
    cancel_requested: Callable[[], bool] | None = None,
    progress: Callable[[InventoryProgress], None] | None = None,
) -> dict[str, StorageInventory]:
    results: dict[str, StorageInventory] = {}
    for component in components:
        if component not in _COMPONENTS:
            raise ValueError(f"unknown storage component: {component}")
        results[component] = inventory_directory(
            getattr(paths, component),
            cancel_requested=cancel_requested,
            progress=progress,
        )
    return results


def inspect_destination(path: Path) -> DestinationCapacity:
    path = Path(path).absolute()
    existing_parent = path
    while not existing_parent.exists():
        parent = existing_parent.parent
        if parent == existing_parent:
            raise FileNotFoundError(path)
        existing_parent = parent
    if not existing_parent.is_dir():
        raise NotADirectoryError(existing_parent)
    usage = shutil.disk_usage(existing_parent)
    return DestinationCapacity(
        path=path,
        existing_parent=existing_parent,
        device_id=existing_parent.stat().st_dev,
        total_bytes=usage.total,
        free_bytes=usage.free,
    )
