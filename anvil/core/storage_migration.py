from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from anvil.core.instance_manager import InstanceManager
from anvil.core.instance_paths import resolve_instance_paths
from anvil.core.storage_inventory import inventory_directory, inspect_destination
from anvil.core.storage_markers import (
    MARKER_NAME,
    verify_location_marker,
    write_location_marker,
)


class MigrationState(str, Enum):
    PLANNED = "planned"
    PREFLIGHT_OK = "preflight_ok"
    PURGED = "purged"
    COPYING = "copying"
    COPIED = "copied"
    VERIFIED = "verified"
    PATHS_SWITCHED = "paths_switched"
    REINDEXED = "reindexed"
    REDEPLOYED = "redeployed"
    COMPLETE = "complete"
    ROLLBACK_REQUIRED = "rollback_required"


class VerificationLevel(str, Enum):
    FAST = "fast"
    FULL = "full"


class MigrationError(RuntimeError):
    pass


class MigrationCancelled(MigrationError):
    pass


@dataclass(frozen=True, slots=True)
class MigrationResult:
    state: MigrationState
    files_copied: int
    symlinks_copied: int
    bytes_copied: int


@dataclass(frozen=True, slots=True)
class MigrationProgress:
    state: MigrationState
    current_path: Path | None
    files_copied: int
    symlinks_copied: int
    bytes_copied: int
    total_bytes: int
    current_file_bytes: int = 0


class MigrationEngine:
    def __init__(
        self,
        *,
        source: Path,
        target: Path,
        journal_path: Path,
        verification: VerificationLevel = VerificationLevel.FULL,
        cancel_requested: Callable[[], bool] | None = None,
        progress: Callable[[MigrationProgress], None] | None = None,
        before_copy: Callable[[], bool | None] | None = None,
        copy_buffer_size: int = 4 * 1024 * 1024,
        excluded_relative_paths: tuple[Path, ...] = (),
    ) -> None:
        self.source = Path(source).absolute()
        self.target = Path(target).absolute()
        self.journal_path = Path(journal_path).absolute()
        self.verification = verification
        self.cancel_requested = cancel_requested
        self.progress = progress
        self.before_copy = before_copy
        self.excluded_relative_paths = tuple(
            sorted((Path(path) for path in excluded_relative_paths), key=lambda path: path.as_posix())
        )
        if any(
            path.is_absolute() or ".." in path.parts
            for path in self.excluded_relative_paths
        ):
            raise ValueError("migration exclusions must be safe relative paths")
        if copy_buffer_size <= 0:
            raise ValueError("copy_buffer_size must be positive")
        self.copy_buffer_size = copy_buffer_size
        self._journal: dict[str, object] = {}

    def run(self) -> MigrationResult:
        inventory = inventory_directory(
            self.source,
            cancel_requested=self.cancel_requested,
            excluded_relative_paths=self.excluded_relative_paths,
        )
        resuming = self._load_resumable_journal()
        if not resuming:
            self._journal = {
                "version": 1,
                "state": MigrationState.PLANNED.value,
                "source": str(self.source),
                "target": str(self.target),
                "verification": self.verification.value,
                "excluded_relative_paths": [
                    path.as_posix() for path in self.excluded_relative_paths
                ],
                "source_retained": True,
                "total_bytes": inventory.total_bytes,
                "files_copied": 0,
                "symlinks_copied": 0,
                "bytes_copied": 0,
                "completed": {},
                "last_error": "",
            }
            self._write_journal()
        elif self._journal_int("total_bytes", -1) != inventory.total_bytes:
            raise MigrationError("source changed since migration was interrupted")

        self._preflight(inventory.total_bytes, resuming=resuming)
        if not resuming:
            self._set_state(MigrationState.PREFLIGHT_OK)
            if self.before_copy is not None:
                try:
                    if self.before_copy() is False:
                        raise MigrationError("pre-copy operation failed")
                except BaseException as exc:
                    self._journal["last_error"] = str(exc)
                    self._write_journal()
                    raise
            self._set_state(MigrationState.PURGED)
            self.target.mkdir(parents=True, exist_ok=False)
        self._set_state(MigrationState.COPYING)
        try:
            self._copy_tree()
            self._copy_directory_metadata()
            self._set_state(MigrationState.COPIED)
            self._verify_tree()
            self._set_state(MigrationState.VERIFIED)
        except BaseException as exc:
            self._journal["last_error"] = str(exc)
            self._write_journal()
            raise
        return self._result()

    def mark_state(
        self,
        state: MigrationState,
        **metadata: object,
    ) -> MigrationResult:
        if not self._journal and not self._load_resumable_journal():
            raise MigrationError("migration journal is unavailable")
        self._journal.update(metadata)
        self._set_state(state)
        return self._result()

    def _load_resumable_journal(self) -> bool:
        if not self.journal_path.is_file():
            return False
        try:
            journal = json.loads(self.journal_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MigrationError(f"migration journal is unreadable: {exc}") from exc
        if not isinstance(journal, dict) or journal.get("version") != 1:
            raise MigrationError("migration journal has an unsupported format")
        if journal.get("source") != str(self.source) or journal.get("target") != str(self.target):
            raise MigrationError("an unresolved migration journal belongs to another path")
        if journal.get("verification") != self.verification.value:
            raise MigrationError("verification level differs from the migration journal")
        expected_exclusions = [path.as_posix() for path in self.excluded_relative_paths]
        if journal.get("excluded_relative_paths", []) != expected_exclusions:
            raise MigrationError("excluded paths differ from the migration journal")
        try:
            state = MigrationState(str(journal.get("state")))
        except ValueError as exc:
            raise MigrationError("migration journal has an invalid state") from exc
        if state is MigrationState.COMPLETE:
            raise MigrationError("migration journal is already complete")
        if state is MigrationState.PLANNED and not self.target.exists():
            return False
        self._journal = journal
        return True

    def _preflight(self, total_bytes: int, *, resuming: bool) -> None:
        source = self.source.resolve(strict=True)
        target = self.target.resolve(strict=False)
        if source == target:
            raise MigrationError("source and target are identical")
        if target.is_relative_to(source) or source.is_relative_to(target):
            raise MigrationError("source and target must not overlap")
        if self.target.exists():
            if not resuming:
                raise MigrationError("target must not exist")
            if self.target.is_symlink() or not self.target.is_dir():
                raise MigrationError("resumable target must be a real directory")
        elif resuming:
            raise MigrationError("resumable target is missing")
        if self.journal_path == self.source or self.journal_path.is_relative_to(self.source):
            raise MigrationError("journal must be outside the source")
        if self.journal_path == self.target or self.journal_path.is_relative_to(self.target):
            raise MigrationError("journal must be outside the target")
        destination = inspect_destination(self.target)
        if destination.free_bytes < total_bytes:
            raise MigrationError("insufficient free space")
        if not os.access(destination.existing_parent, os.W_OK | os.X_OK):
            raise MigrationError(f"destination is not writable: {destination.existing_parent}")

    def _copy_tree(self) -> None:
        for path in self._iter_entries(self.source):
            self._check_cancelled()
            relative = path.relative_to(self.source)
            destination = self.target / relative
            if self._completed_entry_is_valid(relative, path, destination):
                self._emit_progress(path)
                continue
            if path.is_symlink():
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(os.readlink(path))
                self._journal["symlinks_copied"] = self._journal_int("symlinks_copied") + 1
                self._record_completed(relative, "symlink", 0, os.readlink(path))
            elif path.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            elif path.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                self._copy_file(path, destination)
                size = path.stat(follow_symlinks=False).st_size
                self._journal["files_copied"] = self._journal_int("files_copied") + 1
                self._journal["bytes_copied"] = self._journal_int("bytes_copied") + size
                self._record_completed(relative, "file", size, self._sha256(path))
            self._write_journal()
            self._emit_progress(path)

    def _copy_directory_metadata(self) -> None:
        directories = [self.source]
        directories.extend(
            path
            for path in self._iter_entries(self.source)
            if path.is_dir() and not path.is_symlink()
        )
        directories.sort(key=lambda path: len(path.parts), reverse=True)
        for source in directories:
            self._check_cancelled()
            destination = self.target / source.relative_to(self.source)
            try:
                shutil.copystat(source, destination, follow_symlinks=False)
            except OSError as exc:
                raise MigrationError(
                    f"directory metadata copy failed for {source}: {exc}"
                ) from exc

    def _copy_file(self, source: Path, destination: Path) -> None:
        temporary = destination.with_name(destination.name + ".anvil-part")
        temporary.unlink(missing_ok=True)
        try:
            with source.open("rb") as source_stream, temporary.open("wb") as target_stream:
                current_file_bytes = 0
                while True:
                    self._check_cancelled()
                    block = source_stream.read(self.copy_buffer_size)
                    if not block:
                        break
                    target_stream.write(block)
                    current_file_bytes += len(block)
                    self._emit_progress(source, current_file_bytes=current_file_bytes)
                target_stream.flush()
                os.fsync(target_stream.fileno())
            shutil.copystat(source, temporary, follow_symlinks=False)
            os.replace(temporary, destination)
        except BaseException as exc:
            temporary.unlink(missing_ok=True)
            if isinstance(exc, OSError):
                raise MigrationError(f"copy failed for {source}: {exc}") from exc
            raise

    def _verify_tree(self) -> None:
        source_entries = {
            path.relative_to(self.source): path
            for path in self._iter_entries(self.source)
        }
        target_entries = {
            path.relative_to(self.target): path
            for path in self._iter_entries(self.target)
        }
        if set(source_entries) != set(target_entries):
            raise MigrationError("source and target path sets differ")
        for relative, source in source_entries.items():
            self._check_cancelled()
            target = target_entries[relative]
            if source.is_symlink():
                if not target.is_symlink() or os.readlink(source) != os.readlink(target):
                    raise MigrationError(f"symlink verification failed: {relative}")
            elif source.is_dir():
                if not target.is_dir() or target.is_symlink():
                    raise MigrationError(f"directory verification failed: {relative}")
            elif source.is_file():
                if not target.is_file() or target.is_symlink():
                    raise MigrationError(f"file verification failed: {relative}")
                source_stat = source.stat(follow_symlinks=False)
                target_stat = target.stat(follow_symlinks=False)
                if source_stat.st_size != target_stat.st_size:
                    raise MigrationError(f"file size verification failed: {relative}")
                if (
                    self.verification is VerificationLevel.FULL
                    or self._requires_fast_hash(relative)
                ) and self._sha256(source) != self._sha256(target):
                    raise MigrationError(f"file hash verification failed: {relative}")

    @staticmethod
    def _requires_fast_hash(relative: Path) -> bool:
        name = relative.name.lower()
        return (
            name in {
                ".anvil.ini",
                ".current",
                ".anvil-location.json",
                "modlist.txt",
                "plugins.txt",
                "loadorder.txt",
            }
            or name.endswith(".json")
        )

    def _iter_entries(self, root: Path):
        pending = [root]
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as entries:
                ordered = sorted(entries, key=lambda entry: entry.name)
            for entry in ordered:
                path = Path(entry.path)
                relative = path.relative_to(root)
                if any(
                    relative == excluded or excluded in relative.parents
                    for excluded in self.excluded_relative_paths
                ):
                    continue
                yield path
                if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                    pending.append(path)

    def _completed_entry_is_valid(
        self,
        relative: Path,
        source: Path,
        destination: Path,
    ) -> bool:
        completed = self._journal.get("completed")
        if not isinstance(completed, dict):
            raise MigrationError("migration journal completed map is invalid")
        record = completed.get(relative.as_posix())
        if not isinstance(record, dict):
            return False

        kind = record.get("kind")
        fingerprint = record.get("fingerprint")
        valid = False
        if kind == "file" and source.is_file() and destination.is_file():
            valid = (
                self._sha256(source) == fingerprint
                and self._sha256(destination) == fingerprint
            )
        elif kind == "symlink" and source.is_symlink() and destination.is_symlink():
            valid = os.readlink(source) == fingerprint == os.readlink(destination)
        if valid:
            return True

        if kind == "file":
            self._journal["files_copied"] = max(0, self._journal_int("files_copied") - 1)
            record_size = record.get("size", 0)
            size = record_size if isinstance(record_size, int) else 0
            self._journal["bytes_copied"] = max(
                0,
                self._journal_int("bytes_copied") - size,
            )
        elif kind == "symlink":
            self._journal["symlinks_copied"] = max(
                0,
                self._journal_int("symlinks_copied") - 1,
            )
        completed.pop(relative.as_posix(), None)
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        elif destination.exists():
            raise MigrationError(f"resumable target type changed: {relative}")
        return False

    def _record_completed(
        self,
        relative: Path,
        kind: str,
        size: int,
        fingerprint: str,
    ) -> None:
        completed = self._journal.get("completed")
        if not isinstance(completed, dict):
            raise MigrationError("migration journal completed map is invalid")
        completed[relative.as_posix()] = {
            "kind": kind,
            "size": size,
            "fingerprint": fingerprint,
        }

    def _set_state(self, state: MigrationState) -> None:
        self._journal["state"] = state.value
        self._write_journal()
        self._emit_progress(None)

    def _emit_progress(
        self,
        current_path: Path | None,
        *,
        current_file_bytes: int = 0,
    ) -> None:
        if self.progress is None:
            return
        self.progress(
            MigrationProgress(
                state=MigrationState(str(self._journal["state"])),
                current_path=current_path,
                files_copied=self._journal_int("files_copied"),
                symlinks_copied=self._journal_int("symlinks_copied"),
                bytes_copied=self._journal_int("bytes_copied"),
                total_bytes=self._journal_int("total_bytes"),
                current_file_bytes=current_file_bytes,
            )
        )

    def _check_cancelled(self) -> None:
        if self.cancel_requested is not None and self.cancel_requested():
            raise MigrationCancelled("migration cancelled")

    def _write_journal(self) -> None:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.journal_path.with_name(self.journal_path.name + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(self._journal, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.journal_path)
        directory_fd = os.open(self.journal_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _journal_int(self, key: str, default: int = 0) -> int:
        value = self._journal.get(key, default)
        if not isinstance(value, int):
            raise MigrationError(f"migration journal field is not an integer: {key}")
        return value

    def _result(self) -> MigrationResult:
        return MigrationResult(
            state=MigrationState(str(self._journal["state"])),
            files_copied=self._journal_int("files_copied"),
            symlinks_copied=self._journal_int("symlinks_copied"),
            bytes_copied=self._journal_int("bytes_copied"),
        )


_COMPONENT_PATH_KEYS = {
    "mods": "path_mods_directory",
    "downloads": "path_downloads_directory",
    "profiles": "path_profiles_directory",
    "overwrite": "path_overwrite_directory",
    "backups": "path_backups_directory",
    "cache": "path_cache_directory",
}

_COMPONENT_DEFAULT_NAMES = {
    "mods": ".mods",
    "downloads": ".downloads",
    "profiles": ".profiles",
    "overwrite": ".overwrite",
    "backups": ".backups",
    "cache": ".webcache",
}


class InstanceComponentMigration:
    def __init__(
        self,
        *,
        manager: InstanceManager,
        instance_name: str,
        component: str,
        target: Path,
        journal_path: Path,
        purge: Callable[[], bool | None] | None = None,
        reindex: Callable[[Path], None] | None = None,
        redeploy: Callable[[], bool | None] | None = None,
        reload_ui: Callable[[], None] | None = None,
        verification: VerificationLevel = VerificationLevel.FULL,
        cancel_requested: Callable[[], bool] | None = None,
        progress: Callable[[MigrationProgress], None] | None = None,
    ) -> None:
        if component not in _COMPONENT_PATH_KEYS:
            raise ValueError(f"unsupported storage component: {component}")
        self.manager = manager
        self.instance_name = instance_name
        self.component = component
        self.target = Path(target).absolute()
        self.journal_path = Path(journal_path).absolute()
        self.purge = purge
        self.reindex = reindex
        self.redeploy = redeploy
        self.reload_ui = reload_ui
        self.verification = verification
        self.cancel_requested = cancel_requested
        self.progress = progress

    def run(self) -> MigrationResult:
        instance = self.manager.instances_path() / self.instance_name
        data = self.manager.load_instance(self.instance_name)
        if not data:
            raise MigrationError(f"instance does not exist: {self.instance_name}")
        source = getattr(resolve_instance_paths(instance, data), self.component)
        key = _COMPONENT_PATH_KEYS[self.component]
        engine = MigrationEngine(
            source=source,
            target=self.target,
            journal_path=self.journal_path,
            verification=self.verification,
            cancel_requested=self.cancel_requested,
            progress=self.progress,
            before_copy=self.purge,
        )
        engine.run()

        old_values: dict[str, str | None] | None = None
        switched = False
        try:
            old_values = self.manager.update_instance_paths_atomic(
                self.instance_name,
                {key: str(self.target)},
            )
            switched = True
            resolved = resolve_instance_paths(
                instance,
                self.manager.load_instance(self.instance_name),
            )
            if getattr(resolved, self.component) != self.target or not self.target.is_dir():
                raise MigrationError("path switch verification failed")
            engine.mark_state(
                MigrationState.PATHS_SWITCHED,
                old_path_values=old_values,
                new_path_values={key: str(self.target)},
            )

            if self.reindex is not None:
                self.reindex(self.target)
            engine.mark_state(MigrationState.REINDEXED)

            if self.redeploy is not None and self.redeploy() is False:
                raise MigrationError("redeploy failed")
            engine.mark_state(MigrationState.REDEPLOYED)

            if self.reload_ui is not None:
                self.reload_ui()
            return engine.mark_state(MigrationState.COMPLETE)
        except BaseException as exc:
            rollback_error = ""
            if switched and old_values is not None:
                try:
                    self.manager.update_instance_paths_atomic(
                        self.instance_name,
                        old_values,
                    )
                    if self.redeploy is not None:
                        self.redeploy()
                    if self.reload_ui is not None:
                        self.reload_ui()
                except BaseException as rollback_exc:
                    rollback_error = str(rollback_exc)
            engine.mark_state(
                MigrationState.ROLLBACK_REQUIRED,
                last_error=str(exc),
                rollback_error=rollback_error,
            )
            if isinstance(exc, MigrationError):
                raise
            raise MigrationError(f"migration finalization failed: {exc}") from exc


class InstanceStorageMigration:
    def __init__(
        self,
        *,
        manager: InstanceManager,
        instance_name: str,
        components: dict[str, Path],
        journal_directory: Path,
        purge: Callable[[], bool | None] | None = None,
        reindex: Callable[[Path], None] | None = None,
        redeploy: Callable[[], bool | None] | None = None,
        reload_ui: Callable[[], None] | None = None,
        verification: VerificationLevel = VerificationLevel.FULL,
        cancel_requested: Callable[[], bool] | None = None,
        progress: Callable[[str, MigrationProgress], None] | None = None,
        defer_completion: bool = False,
    ) -> None:
        if not components:
            raise ValueError("at least one storage component is required")
        unknown = set(components) - set(_COMPONENT_PATH_KEYS)
        if unknown:
            raise ValueError(f"unsupported storage components: {sorted(unknown)}")
        self.manager = manager
        self.instance_name = instance_name
        self.components = {
            component: Path(target).absolute()
            for component, target in components.items()
        }
        self.journal_directory = Path(journal_directory).absolute()
        self.purge = purge
        self.reindex = reindex
        self.redeploy = redeploy
        self.reload_ui = reload_ui
        self.verification = verification
        self.cancel_requested = cancel_requested
        self.progress = progress
        self.defer_completion = defer_completion
        self._pending_engines: dict[str, MigrationEngine] = {}
        self._pending_old_values: dict[str, str | None] | None = None

    def run(self) -> MigrationResult:
        instance = self.manager.instances_path() / self.instance_name
        data = self.manager.load_instance(self.instance_name)
        if not data:
            raise MigrationError(f"instance does not exist: {self.instance_name}")
        instance_id = self.manager.ensure_instance_id(self.instance_name)
        paths = resolve_instance_paths(instance, data)
        engines: dict[str, MigrationEngine] = {}

        for component, target in self.components.items():
            source = getattr(paths, component)
            if not source.exists():
                expected_default = instance / _COMPONENT_DEFAULT_NAMES[component]
                if source != expected_default:
                    raise MigrationError(f"configured source is unavailable: {source}")
                source.mkdir()
            target_marker = target / MARKER_NAME
            if target_marker.is_file() and not (source / MARKER_NAME).exists():
                verify_location_marker(target, instance_id, component)
                target_marker.unlink()
            inventory = inventory_directory(source, cancel_requested=self.cancel_requested)
            probe = MigrationEngine(
                source=source,
                target=target,
                journal_path=self.journal_directory / f"{component}.json",
                verification=self.verification,
            )
            resuming = probe._load_resumable_journal()
            probe._preflight(inventory.total_bytes, resuming=resuming)
            engines[component] = MigrationEngine(
                source=source,
                target=target,
                journal_path=self.journal_directory / f"{component}.json",
                verification=self.verification,
                cancel_requested=self.cancel_requested,
                progress=(
                    (lambda update, name=component: self.progress(name, update))
                    if self.progress is not None
                    else None
                ),
            )

        if self.purge is not None and self.purge() is False:
            raise MigrationError("purge failed")
        for engine in engines.values():
            engine.run()
        for component, target in self.components.items():
            write_location_marker(
                target,
                instance_id=instance_id,
                component=component,
            )

        updates = {
            _COMPONENT_PATH_KEYS[component]: str(target)
            for component, target in self.components.items()
        }
        old_values: dict[str, str | None] | None = None
        switched = False
        try:
            old_values = self.manager.update_instance_paths_atomic(
                self.instance_name,
                updates,
            )
            switched = True
            resolved = resolve_instance_paths(
                instance,
                self.manager.load_instance(self.instance_name),
            )
            for component, target in self.components.items():
                if getattr(resolved, component) != target or not target.is_dir():
                    raise MigrationError(f"path switch verification failed: {component}")
            for engine in engines.values():
                engine.mark_state(
                    MigrationState.PATHS_SWITCHED,
                    old_path_values=old_values,
                    new_path_values=updates,
                )

            if "mods" in self.components and self.reindex is not None:
                self.reindex(self.components["mods"])
            result: MigrationResult | None = None
            for engine in engines.values():
                result = engine.mark_state(MigrationState.REINDEXED)
            assert result is not None
            self._pending_engines = engines
            self._pending_old_values = old_values
            if self.defer_completion:
                return result

            if self.redeploy is not None and self.redeploy() is False:
                raise MigrationError("redeploy failed")
            for engine in engines.values():
                engine.mark_state(MigrationState.REDEPLOYED)

            if self.reload_ui is not None:
                self.reload_ui()
            result: MigrationResult | None = None
            for engine in engines.values():
                result = engine.mark_state(MigrationState.COMPLETE)
            assert result is not None
            return result
        except BaseException as exc:
            rollback_error = ""
            if switched and old_values is not None:
                try:
                    self.manager.update_instance_paths_atomic(
                        self.instance_name,
                        old_values,
                    )
                    if self.redeploy is not None:
                        self.redeploy()
                    if self.reload_ui is not None:
                        self.reload_ui()
                except BaseException as rollback_exc:
                    rollback_error = str(rollback_exc)
            for engine in engines.values():
                engine.mark_state(
                    MigrationState.ROLLBACK_REQUIRED,
                    last_error=str(exc),
                    rollback_error=rollback_error,
                )
            if isinstance(exc, MigrationError):
                raise
            raise MigrationError(f"migration finalization failed: {exc}") from exc

    def complete_after_redeploy(self, deploy_success: bool) -> MigrationResult:
        if not self._pending_engines or self._pending_old_values is None:
            raise MigrationError("no deferred migration is waiting for redeploy")
        if not deploy_success:
            rollback_error = ""
            try:
                self.manager.update_instance_paths_atomic(
                    self.instance_name,
                    self._pending_old_values,
                )
            except BaseException as exc:
                rollback_error = str(exc)
            for engine in self._pending_engines.values():
                engine.mark_state(
                    MigrationState.ROLLBACK_REQUIRED,
                    last_error="redeploy failed",
                    rollback_error=rollback_error,
                )
            raise MigrationError("redeploy failed")

        result: MigrationResult | None = None
        for engine in self._pending_engines.values():
            engine.mark_state(MigrationState.REDEPLOYED)
            result = engine.mark_state(MigrationState.COMPLETE)
        assert result is not None
        return result
