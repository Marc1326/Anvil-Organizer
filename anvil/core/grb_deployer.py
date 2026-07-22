"""Deterministic native deployment for Ghost Recon Breakpoint Forge mods."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from anvil.core.grb_forge import (
    DataContainer,
    ForgeArchive,
    ForgeFormatError,
    ForgeImport,
    append_repoint,
)
from anvil.core.mod_list_io import read_active_mods, read_global_modlist


_MOD_FILE = re.compile(r"^(?P<extension>\d+)_-_(?P<name>.+?)(?:\.data)+$")


@dataclass
class GRBDeployResult:
    success: bool = True
    archives_written: int = 0
    imports_applied: int = 0
    errors: list[str] = field(default_factory=list)


class GRBDeployer:
    """Rebuild GRB Forge targets from pristine backups and active profile mods."""

    MANIFEST_NAME = ".grb_deploy_manifest.json"

    def __init__(
        self,
        instance_path: str | Path,
        game_path: str | Path,
        profile_name: str = "Default",
        *,
        process_root: str | Path = "/proc",
    ) -> None:
        self.instance_path = Path(instance_path)
        self.game_path = Path(game_path)
        self.profile_name = profile_name
        self.mods_path = self.instance_path / ".mods"
        self.profiles_path = self.instance_path / ".profiles"
        self.profile_path = self.profiles_path / profile_name
        self.state_path = self.instance_path / ".anvil"
        self.backup_path = self.state_path / "grb_backups"
        self.backup_manifest_path = self.backup_path / "manifest.json"
        self.staging_path = self.state_path / "grb_staging"
        self.manifest_path = self.instance_path / self.MANIFEST_NAME
        self.process_root = Path(process_root)
        self._separator_deploy_paths: dict[str, str] = {}

    def is_deployed(self) -> bool:
        return self.manifest_path.is_file()

    def _game_process_running(self) -> bool:
        names = {"grb.exe", "grb_vulkan.exe"}
        try:
            processes = self.process_root.iterdir()
        except OSError:
            return False
        for process in processes:
            if not process.name.isdigit():
                continue
            try:
                name = (process / "comm").read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if name.casefold() in names:
                return True
        return False

    def _require_game_stopped(self) -> None:
        if self._game_process_running():
            raise ForgeFormatError(
                "Ghost Recon Breakpoint game process is running; deployment is blocked"
            )

    def purge(self) -> GRBDeployResult:
        result = GRBDeployResult()
        staged_paths: list[Path] = []
        try:
            self._require_game_stopped()
            manifest = self._read_manifest()
            raw_archives = manifest.get("archives", [])
            if not isinstance(raw_archives, list):
                raise ForgeFormatError("GRB deploy manifest archives are not a list")
            operations: list[tuple[Path, Path]] = []
            for item in raw_archives:
                if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                    raise ForgeFormatError("GRB deploy manifest contains an invalid archive")
                target_name = item["name"]
                backup = self._verified_backup(target_name)
                target = self.game_path / target_name
                staged = self._staging_file(target_name)
                staged_paths.append(staged)
                self._copy_pristine(backup, staged)
                ForgeArchive.read(staged)
                operations.append((staged, target))
            self._commit_operations(operations, None)
            result.archives_written = len(operations)
        except (OSError, ValueError, ForgeFormatError) as exc:
            result.success = False
            result.errors.append(str(exc))
        finally:
            for staged in staged_paths:
                try:
                    staged.unlink(missing_ok=True)
                except OSError:
                    pass
        return result

    def deploy(self) -> GRBDeployResult:
        result = GRBDeployResult()
        staged_paths: list[Path] = []
        try:
            self._require_game_stopped()
            active_mods = self._ordered_active_mods()
            plans = self._collect_imports(active_mods)
            previous_manifest = self._read_manifest()
            raw_previous_archives = previous_manifest.get("archives", [])
            if not isinstance(raw_previous_archives, list):
                raise ForgeFormatError("GRB deploy manifest archives are not a list")
            previous_archives = {
                item["name"]
                for item in raw_previous_archives
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            }
            archives: list[dict[str, object]] = []
            operations: list[tuple[Path, Path]] = []
            self.backup_path.mkdir(parents=True, exist_ok=True)

            for target_name in sorted(previous_archives - plans.keys()):
                backup = self._verified_backup(target_name)
                game_forge = self.game_path / target_name
                restored = self._staging_file(target_name)
                staged_paths.append(restored)
                self._copy_pristine(backup, restored)
                ForgeArchive.read(restored)
                operations.append((restored, game_forge))

            for target_name, imports in sorted(plans.items()):
                game_forge = self.game_path / target_name
                if not game_forge.is_file():
                    raise ForgeFormatError(f"target Forge is missing: {game_forge}")
                backup = self._ensure_pristine_backup(target_name, game_forge)

                staged = self._staging_file(target_name)
                staged_paths.append(staged)
                append_repoint(backup, staged, list(imports.values()))
                ForgeArchive.read(staged)
                before_hash = self._sha256(backup)
                after_hash = self._sha256(staged)
                operations.append((staged, game_forge))
                archives.append(
                    {
                        "name": target_name,
                        "backup_sha256": before_hash,
                        "deployed_sha256": after_hash,
                        "imports": len(imports),
                    }
                )
                result.imports_applied += len(imports)

            manifest = {
                "version": 1,
                "profile": self.profile_name,
                "active_mods": active_mods,
                "archives": archives,
            }
            self._commit_operations(operations, manifest)
            result.archives_written = len(operations)
        except (OSError, ValueError, ForgeFormatError) as exc:
            result.success = False
            result.errors.append(str(exc))
        finally:
            for staged in staged_paths:
                try:
                    staged.unlink(missing_ok=True)
                except OSError:
                    pass
        return result

    @staticmethod
    def _validate_target_name(target_name: str) -> str:
        if (
            not target_name
            or target_name in {".", ".."}
            or Path(target_name).name != target_name
            or "/" in target_name
            or "\\" in target_name
            or "\0" in target_name
            or not target_name.lower().endswith(".forge")
        ):
            raise ForgeFormatError(
                f"invalid GRB Forge target name: {target_name!r}"
            )
        return target_name

    def _staging_file(self, target_name: str) -> Path:
        target_name = self._validate_target_name(target_name)
        return self.game_path / f".anvil-grb-{os.getpid()}-{target_name}.staged"

    def _commit_operations(
        self,
        operations: list[tuple[Path, Path]],
        manifest: dict[str, object] | None,
    ) -> None:
        self._require_game_stopped()
        rollbacks: list[tuple[Path, Path]] = []
        previous_manifest = (
            self.manifest_path.read_bytes() if self.manifest_path.is_file() else None
        )
        try:
            for _staged, target in operations:
                rollback = target.parent / (
                    f".anvil-grb-{os.getpid()}-{target.name}.rollback"
                )
                rollback.unlink(missing_ok=True)
                os.link(target, rollback, follow_symlinks=False)
                rollbacks.append((rollback, target))
            for staged, target in operations:
                os.replace(staged, target)
            if operations:
                self._fsync_directory(self.game_path)
            if manifest is None:
                self.manifest_path.unlink(missing_ok=True)
                self._fsync_directory(self.manifest_path.parent)
            else:
                self._write_manifest(manifest)
        except BaseException as original:
            rollback_errors: list[str] = []
            for rollback, target in reversed(rollbacks):
                if not rollback.exists():
                    continue
                try:
                    os.replace(rollback, target)
                except OSError as exc:
                    rollback_errors.append(f"{target.name}: {exc}")
            if rollbacks:
                try:
                    self._fsync_directory(self.game_path)
                except OSError as exc:
                    rollback_errors.append(f"directory sync: {exc}")
            try:
                self._restore_manifest(previous_manifest)
            except OSError as exc:
                rollback_errors.append(f"manifest restore: {exc}")
            if rollback_errors:
                raise ForgeFormatError(
                    "GRB commit failed and rollback was incomplete: "
                    + "; ".join(rollback_errors)
                ) from original
            raise
        finally:
            for rollback, _target in rollbacks:
                try:
                    rollback.unlink(missing_ok=True)
                except OSError:
                    pass

    def _restore_manifest(self, previous: bytes | None) -> None:
        if previous is None:
            self.manifest_path.unlink(missing_ok=True)
            self._fsync_directory(self.manifest_path.parent)
            return
        temporary = self.manifest_path.with_name(self.manifest_path.name + ".rollback")
        with temporary.open("wb") as stream:
            stream.write(previous)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.manifest_path)
        self._fsync_directory(self.manifest_path.parent)

    def _ordered_active_mods(self) -> list[str]:
        active = read_active_mods(self.profile_path)
        order = read_global_modlist(self.profiles_path)
        if not order:
            return sorted(active)
        return [name for name in order if name in active]

    @staticmethod
    def _validate_mod_name(mod_name: str) -> str:
        if (
            not mod_name
            or mod_name in {".", ".."}
            or Path(mod_name).name != mod_name
            or "/" in mod_name
            or "\\" in mod_name
            or "\0" in mod_name
        ):
            raise ForgeFormatError(f"invalid active mod name: {mod_name!r}")
        return mod_name

    def _collect_imports(
        self, active_mods: list[str]
    ) -> dict[str, dict[int, ForgeImport]]:
        plans: dict[str, dict[int, ForgeImport]] = {}
        # Global mod list is highest priority first. Process low to high so the
        # final assignment implements Anvil's established "higher wins" rule.
        for mod_name in reversed(active_mods):
            mod_name = self._validate_mod_name(mod_name)
            mod_path = self.mods_path / mod_name
            if not mod_path.is_dir():
                raise ForgeFormatError(f"active mod directory is missing: {mod_name}")
            for target in sorted(mod_path.glob("*.forge")):
                if not target.is_dir():
                    continue
                target_imports = plans.setdefault(target.name, {})
                for data_path in sorted(target.iterdir()):
                    if not data_path.is_file():
                        continue
                    match = _MOD_FILE.match(data_path.name)
                    if match is None:
                        raise ForgeFormatError(
                            f"unsupported GRB mod filename: {data_path.name}"
                        )
                    name = match.group("name")
                    manifest = DataContainer.inspect(data_path)
                    if not manifest.resource_extensions:
                        raise ForgeFormatError(
                            f"GRB mod container lacks deep extension validation: {data_path.name}"
                        )
                    extension = manifest.resource_extensions[0]
                    class_id = manifest.resource_ids[0]
                    target_imports[class_id] = ForgeImport(
                        data_path, extension, name
                    )
        return plans

    def _read_backup_registry(self) -> dict[str, object]:
        if not self.backup_manifest_path.is_file():
            return {"version": 1, "archives": {}}
        try:
            data = json.loads(self.backup_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ForgeFormatError(f"cannot read GRB backup registry: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("archives"), dict):
            raise ForgeFormatError("GRB backup registry is invalid")
        return data

    def _write_backup_registry(self, registry: dict[str, object]) -> None:
        self.backup_path.mkdir(parents=True, exist_ok=True)
        temporary = self.backup_manifest_path.with_name(
            self.backup_manifest_path.name + ".tmp"
        )
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(registry, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.backup_manifest_path)
        self._fsync_directory(self.backup_path)

    def _ensure_pristine_backup(self, target_name: str, source: Path) -> Path:
        target_name = self._validate_target_name(target_name)
        backup = self.backup_path / target_name
        if backup.exists():
            return self._verified_backup(target_name)
        registry = self._read_backup_registry()
        archives = registry["archives"]
        assert isinstance(archives, dict)
        if target_name in archives:
            raise ForgeFormatError(
                f"registered pristine backup is missing: {target_name}"
            )
        self._copy_pristine(source, backup)
        try:
            ForgeArchive.read(backup)
            archives[target_name] = {
                "sha256": self._sha256(backup),
                "size": backup.stat().st_size,
            }
            self._write_backup_registry(registry)
        except BaseException:
            backup.unlink(missing_ok=True)
            raise
        return backup

    def _verified_backup(self, target_name: str) -> Path:
        target_name = self._validate_target_name(target_name)
        backup = self.backup_path / target_name
        if not backup.is_file():
            raise ForgeFormatError(f"pristine backup is missing: {target_name}")
        registry = self._read_backup_registry()
        archives = registry["archives"]
        assert isinstance(archives, dict)
        record = archives.get(target_name)
        if not isinstance(record, dict):
            raise ForgeFormatError(
                f"pristine backup is not registered: {target_name}"
            )
        expected_hash = record.get("sha256")
        expected_size = record.get("size")
        if not isinstance(expected_hash, str) or not isinstance(expected_size, int):
            raise ForgeFormatError(
                f"pristine backup registry entry is invalid: {target_name}"
            )
        if backup.stat().st_size != expected_size or self._sha256(backup) != expected_hash:
            raise ForgeFormatError(
                f"pristine backup integrity check failed: {target_name}"
            )
        ForgeArchive.read(backup)
        return backup

    @staticmethod
    def _copy_pristine(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".tmp")
        if temporary.exists():
            temporary.unlink()
        with source.open("rb") as reader, temporary.open("xb") as writer:
            shutil.copyfileobj(reader, writer, 8 * 1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        shutil.copystat(source, temporary, follow_symlinks=False)
        os.replace(temporary, destination)
        GRBDeployer._fsync_directory(destination.parent)

    def _read_manifest(self) -> dict[str, object]:
        if not self.manifest_path.is_file():
            return {}
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ForgeFormatError(f"cannot read GRB deploy manifest: {exc}") from exc
        if not isinstance(data, dict):
            raise ForgeFormatError("GRB deploy manifest is not an object")
        return data

    def _write_manifest(self, manifest: dict[str, object]) -> None:
        temporary = self.manifest_path.with_name(self.manifest_path.name + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.manifest_path)
        self._fsync_directory(self.manifest_path.parent)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
