from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSettings

from anvil.core.base_dir import (
    BASE_MARKER_NAME,
    configure_base_dir,
    top_level_settings,
    write_base_marker,
)
from anvil.core.storage_migration import (
    MigrationEngine,
    MigrationProgress,
    MigrationState,
    VerificationLevel,
)


_PENDING_KEYS = (
    "Migration/base_source",
    "Migration/base_target",
    "Migration/base_verification",
)


@dataclass(frozen=True, slots=True)
class PendingBaseMigration:
    source: Path
    target: Path
    verification: VerificationLevel


def _absolute(path: Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ValueError("base migration paths must be absolute")
    return Path(os.path.abspath(os.fspath(candidate)))


def pending_base_migration(
    settings: QSettings | None = None,
) -> PendingBaseMigration | None:
    settings = settings or top_level_settings()
    source = str(settings.value("Migration/base_source", "")).strip()
    target = str(settings.value("Migration/base_target", "")).strip()
    verification = str(settings.value("Migration/base_verification", "")).strip()
    if not source and not target and not verification:
        return None
    if not source or not target:
        raise ValueError("pending base migration is incomplete")
    try:
        level = VerificationLevel(verification)
    except ValueError as exc:
        raise ValueError("pending base migration has invalid verification") from exc
    return PendingBaseMigration(
        source=_absolute(Path(source)),
        target=_absolute(Path(target)),
        verification=level,
    )


def schedule_base_migration(
    *,
    source: Path,
    target: Path,
    verification: VerificationLevel,
    settings: QSettings | None = None,
) -> PendingBaseMigration:
    settings = settings or top_level_settings()
    source = _absolute(source)
    target = _absolute(target)
    if source.is_symlink() or not source.is_dir():
        raise FileNotFoundError(f"Anvil source directory is unavailable: {source}")
    if target.is_symlink():
        raise ValueError("Anvil target directory must not be a symlink")
    if target == source or target.is_relative_to(source):
        raise ValueError("Anvil target must not be inside the source directory")
    if source.is_relative_to(target):
        raise ValueError("Anvil source must not be inside the target directory")

    existing = pending_base_migration(settings)
    request = PendingBaseMigration(source, target, verification)
    if existing is not None and existing != request:
        raise ValueError("another base migration is still pending")
    settings.setValue("Migration/base_source", str(source))
    settings.setValue("Migration/base_target", str(target))
    settings.setValue("Migration/base_verification", verification.value)
    settings.sync()
    if settings.status() != QSettings.Status.NoError:
        raise OSError(f"failed to save pending base migration: {settings.status()}")
    return request


def _journal_path(settings: QSettings) -> Path:
    config_path = Path(settings.fileName()).absolute()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    return config_path.parent / "base-migration.json"


def execute_pending_base_migration(
    *,
    settings: QSettings | None = None,
    progress: Callable[[MigrationProgress], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
) -> Path | None:
    settings = settings or top_level_settings()
    pending = pending_base_migration(settings)
    if pending is None:
        return None
    base_id = str(settings.value("General/base_id", "")).strip() or str(uuid.uuid4())
    settings.setValue("General/base_id", base_id)
    settings.sync()
    if settings.status() != QSettings.Status.NoError:
        raise OSError("failed to persist Anvil base id")

    engine = MigrationEngine(
        source=pending.source,
        target=pending.target,
        journal_path=_journal_path(settings),
        verification=pending.verification,
        progress=progress,
        cancel_requested=cancel_requested,
        excluded_relative_paths=(Path("instance.sock"), Path(BASE_MARKER_NAME)),
    )
    engine.run()
    write_base_marker(pending.target, base_id)
    configure_base_dir(pending.target, settings=settings, create=False)
    engine.mark_state(MigrationState.PATHS_SWITCHED, base_id=base_id)
    engine.mark_state(MigrationState.COMPLETE, source_retained=True)
    for key in _PENDING_KEYS:
        settings.remove(key)
    settings.sync()
    if settings.status() != QSettings.Status.NoError:
        raise OSError("failed to clear pending base migration")
    return pending.target
