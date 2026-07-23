from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


MARKER_NAME = ".anvil-location.json"
_COMPONENTS = {"mods", "downloads", "profiles", "overwrite", "backups", "cache"}


class StorageMarkerError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StorageLocationMarker:
    instance_id: str
    component: str
    version: int = 1


def _validate_root(root: Path) -> Path:
    root = Path(root).absolute()
    if root.is_symlink():
        raise StorageMarkerError(f"storage root must not be a symlink: {root}")
    if not root.is_dir():
        raise StorageMarkerError(f"storage root is not a directory: {root}")
    return root


def _validate_values(instance_id: str, component: str) -> None:
    if not instance_id or "\0" in instance_id:
        raise StorageMarkerError("instance id is invalid")
    if component not in _COMPONENTS:
        raise StorageMarkerError(f"storage component is invalid: {component}")


def write_location_marker(
    root: Path,
    *,
    instance_id: str,
    component: str,
) -> Path:
    root = _validate_root(root)
    _validate_values(instance_id, component)
    marker_path = root / MARKER_NAME
    temporary = root / f"{MARKER_NAME}.tmp"
    data = {
        "version": 1,
        "instance_id": instance_id,
        "component": component,
    }
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, marker_path)
        directory_fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
    return marker_path


def read_location_marker(root: Path) -> StorageLocationMarker:
    root = _validate_root(root)
    marker_path = root / MARKER_NAME
    if marker_path.is_symlink() or not marker_path.is_file():
        raise StorageMarkerError(f"location marker is missing: {marker_path}")
    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageMarkerError(f"location marker is unreadable: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1:
        raise StorageMarkerError("location marker has an unsupported format")
    instance_id = data.get("instance_id")
    component = data.get("component")
    if not isinstance(instance_id, str) or not isinstance(component, str):
        raise StorageMarkerError("location marker fields are invalid")
    _validate_values(instance_id, component)
    return StorageLocationMarker(
        instance_id=instance_id,
        component=component,
    )


def verify_location_marker(
    root: Path,
    instance_id: str,
    component: str,
) -> StorageLocationMarker:
    marker = read_location_marker(root)
    if marker.instance_id != instance_id:
        raise StorageMarkerError("location marker belongs to a different instance")
    if marker.component != component:
        raise StorageMarkerError("location marker belongs to a different component")
    return marker
