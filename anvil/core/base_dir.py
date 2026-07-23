from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings


@dataclass(frozen=True, slots=True)
class AnvilBasePaths:
    base: Path

    @property
    def instances(self) -> Path:
        return self.base / "instances"

    @property
    def logs(self) -> Path:
        return self.base / "logs"

    @property
    def plugins(self) -> Path:
        return self.base / "plugins"

    @property
    def user_plugins(self) -> Path:
        return self.plugins / "games"

    @property
    def credentials(self) -> Path:
        return self.base / "credentials.json"

    @property
    def current_instance(self) -> Path:
        return self.base / ".current"

    @property
    def socket(self) -> Path:
        return self.base / "instance.sock"

    @property
    def migration_journals(self) -> Path:
        return self.base / ".migration-journals"


def top_level_settings() -> QSettings:
    return QSettings("AnvilOrganizer", "AnvilOrganizer")


def legacy_base_dir() -> Path:
    return Path(os.path.abspath(os.fspath(Path.home() / ".anvil-organizer")))


def resolve_base_dir(settings: QSettings | None = None) -> Path:
    settings = settings or top_level_settings()
    raw = str(settings.value("General/base_dir", "")).strip()
    if not raw or "\0" in raw:
        return legacy_base_dir()
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        return legacy_base_dir()
    return Path(os.path.abspath(os.fspath(candidate)))


def anvil_base_paths(settings: QSettings | None = None) -> AnvilBasePaths:
    return AnvilBasePaths(resolve_base_dir(settings))


BASE_MARKER_NAME = ".anvil-base.json"


def write_base_marker(path: Path, base_id: str) -> None:
    marker = path / BASE_MARKER_NAME
    temporary = path / f"{BASE_MARKER_NAME}.tmp"
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump({"version": 1, "base_id": base_id}, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, marker)
        directory_fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def verify_base_marker(
    path: Path,
    *,
    settings: QSettings | None = None,
) -> str:
    settings = settings or top_level_settings()
    expected = str(settings.value("General/base_id", "")).strip()
    marker = Path(path) / BASE_MARKER_NAME
    if marker.is_symlink() or not marker.is_file():
        raise ValueError(f"Anvil base marker is missing: {marker}")
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Anvil base marker is unreadable: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Anvil base marker has an unsupported format")
    actual = data.get("base_id")
    if not isinstance(actual, str) or not actual:
        raise ValueError("Anvil base marker has an invalid id")
    if expected and actual != expected:
        raise ValueError("Anvil base marker belongs to another installation")
    return actual


def configure_base_dir(
    path: Path,
    *,
    settings: QSettings | None = None,
    create: bool,
) -> Path:
    settings = settings or top_level_settings()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ValueError("Anvil base directory must be absolute")
    candidate = Path(os.path.abspath(os.fspath(candidate)))
    if candidate.is_symlink():
        raise ValueError("Anvil base directory must not be a symlink")
    if create:
        candidate.mkdir(parents=True, exist_ok=True)
    elif not candidate.is_dir():
        raise FileNotFoundError(candidate)
    if not candidate.is_dir() or not os.access(
        candidate,
        os.R_OK | os.W_OK | os.X_OK,
    ):
        raise PermissionError(candidate)
    if create:
        base_id = str(settings.value("General/base_id", "")).strip() or str(uuid.uuid4())
        settings.setValue("General/base_id", base_id)
        write_base_marker(candidate, base_id)
    else:
        base_id = verify_base_marker(candidate, settings=settings)
        settings.setValue("General/base_id", base_id)
    settings.setValue("General/base_dir", str(candidate))
    settings.sync()
    if settings.status() != QSettings.Status.NoError:
        raise OSError(f"failed to save Anvil base directory: {settings.status()}")
    if resolve_base_dir(settings) != candidate:
        raise OSError("failed to verify configured Anvil base directory")
    return candidate


def configured_base_is_custom(settings: QSettings | None = None) -> bool:
    return resolve_base_dir(settings) != legacy_base_dir()


def base_dir_available(settings: QSettings | None = None) -> bool:
    base = resolve_base_dir(settings)
    return base.is_dir() and os.access(base, os.R_OK | os.W_OK | os.X_OK)
