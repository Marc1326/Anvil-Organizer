"""Pure path resolution for Anvil instances."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class StorageComponentStatus:
    """Availability of one configured instance storage component."""

    component: str
    path: Path
    exists: bool
    is_directory: bool
    readable: bool
    writable: bool


@dataclass(frozen=True)
class InstancePaths:
    """Absolute storage roots used by one Anvil instance."""

    instance: Path
    mods: Path
    downloads: Path
    profiles: Path
    overwrite: Path
    backups: Path
    cache: Path


def resolve_instance_paths(
    instance_path: Path,
    instance_data: Mapping[str, Any],
) -> InstancePaths:
    """Resolve an instance's storage roots without touching the filesystem."""
    def absolute(path: Path) -> Path:
        return Path(os.path.abspath(os.fspath(path)))

    instance = absolute(instance_path)

    def root(key: str, default_name: str) -> Path:
        raw = str(instance_data.get(key, "")).strip()
        if not raw:
            return instance / default_name
        marker = "%INSTANCE_DIR%"
        if "\0" in raw:
            raise ValueError(f"invalid NUL in {key}")
        if raw == marker:
            return instance
        if raw.startswith((marker + "/", marker + "\\")):
            candidate = absolute(instance / raw[len(marker):].lstrip("/\\"))
            if candidate != instance and not candidate.is_relative_to(instance):
                raise ValueError(f"{key} escapes the instance directory")
            return candidate
        if marker in raw:
            raise ValueError(f"invalid {marker} placement in {key}")
        path = Path(raw).expanduser()
        if not path.is_absolute():
            raise ValueError(f"relative path is not allowed for {key}")
        return absolute(path)

    return InstancePaths(
        instance=instance,
        mods=root("path_mods_directory", ".mods"),
        downloads=root("path_downloads_directory", ".downloads"),
        profiles=root("path_profiles_directory", ".profiles"),
        overwrite=root("path_overwrite_directory", ".overwrite"),
        backups=root("path_backups_directory", ".backups"),
        cache=root("path_cache_directory", ".webcache"),
    )


_STORAGE_COMPONENTS = (
    ("mods", "path_mods_directory", ".mods"),
    ("downloads", "path_downloads_directory", ".downloads"),
    ("profiles", "path_profiles_directory", ".profiles"),
    ("overwrite", "path_overwrite_directory", ".overwrite"),
    ("backups", "path_backups_directory", ".backups"),
    ("cache", "path_cache_directory", ".webcache"),
)


def unavailable_configured_storage(
    paths: InstancePaths,
    instance_data: Mapping[str, Any],
) -> list[StorageComponentStatus]:
    """Return unavailable non-default roots without creating anything."""
    unavailable: list[StorageComponentStatus] = []
    for component, key, default_name in _STORAGE_COMPONENTS:
        path = getattr(paths, component)
        if path == paths.instance / default_name:
            continue
        exists = path.exists()
        is_directory = path.is_dir()
        readable = is_directory and os.access(path, os.R_OK | os.X_OK)
        writable = is_directory and os.access(path, os.W_OK | os.X_OK)
        status = StorageComponentStatus(
            component=component,
            path=path,
            exists=exists,
            is_directory=is_directory,
            readable=readable,
            writable=writable,
        )
        if not (exists and is_directory and readable):
            unavailable.append(status)
    return unavailable
