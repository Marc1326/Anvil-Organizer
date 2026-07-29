"""Shared path rules for Bethesda archive packing."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _path_parts(value: str | Path) -> tuple[str, ...]:
    normalized = str(value).replace("\\", "/").strip("/")
    return tuple(part.casefold() for part in normalized.split("/") if part and part != ".")


def normalized_mod_content_parts(
    rel_path: str | Path,
    data_path: str = "",
) -> tuple[str, ...]:
    """Return a mod-relative path without optional ``root/`` or data prefixes."""
    parts = _path_parts(rel_path)
    if parts and parts[0] == "root":
        parts = parts[1:]

    data_parts = _path_parts(data_path)
    if data_parts and parts[:len(data_parts)] == data_parts:
        parts = parts[len(data_parts):]
    return parts


def is_archive_loose_path(
    rel_path: str | Path,
    loose_paths: Iterable[str],
    data_path: str = "",
) -> bool:
    """Return whether *rel_path* must remain loose instead of being packed."""
    content_parts = normalized_mod_content_parts(rel_path, data_path)
    for configured_path in loose_paths:
        configured_parts = normalized_mod_content_parts(configured_path)
        if configured_parts and content_parts[:len(configured_parts)] == configured_parts:
            return True
    return False
