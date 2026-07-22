"""Validation shared by profile UI and persistence paths."""

from pathlib import Path


def is_valid_profile_name(name: str) -> bool:
    """Return whether *name* is one safe directory component."""
    return bool(
        name
        and name == name.strip()
        and name not in {".", ".."}
        and "/" not in name
        and "\\" not in name
        and "\0" not in name
    )


def safe_profile_directory(instance_path: Path, name: str) -> Path:
    """Return a profile directory only when no path component is a symlink."""
    if not is_valid_profile_name(name):
        raise ValueError(f"invalid profile name: {name!r}")
    profiles_root = instance_path / ".profiles"
    candidate = profiles_root / name
    if profiles_root.is_symlink() or candidate.is_symlink():
        raise ValueError(f"unsafe profile path: {candidate}")
    if candidate.exists():
        try:
            if candidate.resolve().parent != profiles_root.resolve():
                raise ValueError(f"unsafe profile path: {candidate}")
        except OSError as exc:
            raise ValueError(f"unsafe profile path: {candidate}") from exc
    return candidate
