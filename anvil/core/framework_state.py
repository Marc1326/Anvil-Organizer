"""Persist lock/active/version state for framework mods per instance."""

from __future__ import annotations

import json
import sys
from pathlib import Path


DISABLED_SUFFIX = ".anvil-disabled"


def _state_file(instance_path: Path) -> Path:
    return instance_path / ".profiles" / "framework_state.json"


def load(instance_path: Path) -> dict[str, dict]:
    """Return the framework state dict keyed by framework name.

    Each entry: ``{"locked": bool, "active": bool, "version": str}``.
    Missing file -> empty dict.
    """
    path = _state_file(instance_path)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError) as exc:
        print(f"framework_state: cannot read {path}: {exc}", file=sys.stderr)
    return {}


def save(instance_path: Path, state: dict[str, dict]) -> None:
    """Write the whole state dict."""
    path = _state_file(instance_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"framework_state: cannot write {path}: {exc}", file=sys.stderr)


def get(instance_path: Path, fw_name: str) -> dict:
    """Return the state of one framework (defaults filled in)."""
    entry = load(instance_path).get(fw_name, {})
    return {
        "locked": bool(entry.get("locked", False)),
        "active": bool(entry.get("active", True)),
        "version": str(entry.get("version", "")),
    }


def set_entry(instance_path: Path, fw_name: str, **fields) -> None:
    """Update one framework's entry. Only given fields are overwritten."""
    state = load(instance_path)
    entry = state.get(fw_name, {})
    entry.update({k: v for k, v in fields.items() if v is not None})
    state[fw_name] = entry
    save(instance_path, state)


def remove(instance_path: Path, fw_name: str) -> None:
    """Drop a framework entry (e.g. after uninstall)."""
    state = load(instance_path)
    if fw_name in state:
        del state[fw_name]
        save(instance_path, state)


def read_meta_version(archive_path: Path) -> str:
    """Extract ``version`` from a Nexus ``.meta`` file next to an archive.

    Returns empty string if no meta file or no version field.
    """
    import configparser
    meta = archive_path.with_suffix(archive_path.suffix + ".meta")
    if not meta.is_file():
        return ""
    try:
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.read(meta, encoding="utf-8")
        if cp.has_option("General", "version"):
            return cp.get("General", "version").strip()
    except (OSError, configparser.Error):
        pass
    return ""
