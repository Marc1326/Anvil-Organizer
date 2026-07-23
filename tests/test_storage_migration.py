import errno
import json
import os
from pathlib import Path

import pytest

from anvil.core import storage_migration
from anvil.core.instance_manager import InstanceManager
from anvil.core.storage_migration import (
    MigrationCancelled,
    MigrationEngine,
    MigrationError,
    InstanceComponentMigration,
    MigrationState,
    VerificationLevel,
)


def test_full_migration_copies_verifies_and_retains_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    journal = tmp_path / "state" / "migration.json"
    nested = source / "nested"
    nested.mkdir(parents=True)
    payload = nested / "payload.bin"
    payload.write_bytes(b"anvil-data")
    os.chmod(payload, 0o640)
    (source / "relative-link").symlink_to(Path("nested") / "payload.bin")

    result = MigrationEngine(
        source=source,
        target=target,
        journal_path=journal,
        verification=VerificationLevel.FULL,
    ).run()

    assert result.state is MigrationState.VERIFIED
    assert result.files_copied == 1
    assert result.symlinks_copied == 1
    assert payload.read_bytes() == b"anvil-data"
    assert (target / "nested" / "payload.bin").read_bytes() == b"anvil-data"
    assert (target / "relative-link").is_symlink()
    assert os.readlink(target / "relative-link") == "nested/payload.bin"
    assert (target / "nested" / "payload.bin").stat().st_mode & 0o777 == 0o640

    state = json.loads(journal.read_text(encoding="utf-8"))
    assert state["state"] == "verified"
    assert state["verification"] == "full"
    assert state["source"] == str(source)
    assert state["target"] == str(target)
    assert state["source_retained"] is True


def test_cancelled_copy_resumes_from_journal(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    journal = tmp_path / "state" / "migration.json"
    source.mkdir()
    (source / "a.bin").write_bytes(b"a" * 16)
    (source / "b.bin").write_bytes(b"b" * 32)
    cancel = False

    def on_progress(progress) -> None:
        nonlocal cancel
        if progress.state is MigrationState.COPYING and progress.files_copied == 1:
            cancel = True

    with pytest.raises(MigrationCancelled):
        MigrationEngine(
            source=source,
            target=target,
            journal_path=journal,
            cancel_requested=lambda: cancel,
            progress=on_progress,
        ).run()

    interrupted = json.loads(journal.read_text(encoding="utf-8"))
    assert interrupted["state"] == "copying"
    assert interrupted["files_copied"] == 1
    assert source.is_dir()

    result = MigrationEngine(
        source=source,
        target=target,
        journal_path=journal,
    ).run()

    assert result.state is MigrationState.VERIFIED
    assert result.files_copied == 2
    assert (target / "a.bin").read_bytes() == b"a" * 16
    assert (target / "b.bin").read_bytes() == b"b" * 32


def test_enospc_keeps_source_and_resumable_journal(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    journal = tmp_path / "state" / "migration.json"
    source.mkdir()
    payload = source / "large.bin"
    payload.write_bytes(b"source-is-safe")

    def no_space(*_args, **_kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(storage_migration.shutil, "copystat", no_space)
    with pytest.raises(MigrationError, match="No space left"):
        MigrationEngine(
            source=source,
            target=target,
            journal_path=journal,
        ).run()

    assert payload.read_bytes() == b"source-is-safe"
    assert not (target / "large.bin.anvil-part").exists()
    state = json.loads(journal.read_text(encoding="utf-8"))
    assert state["state"] == "copying"
    assert state["files_copied"] == 0
    assert "No space left" in state["last_error"]


def test_cancel_during_large_file_removes_partial_file(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    journal = tmp_path / "state" / "migration.json"
    source.mkdir()
    payload = source / "large.bin"
    payload.write_bytes(bytes(range(64)))
    partial = target / "large.bin.anvil-part"
    cancel = False

    def on_progress(progress) -> None:
        nonlocal cancel
        if progress.current_file_bytes >= 16:
            cancel = True

    with pytest.raises(MigrationCancelled):
        MigrationEngine(
            source=source,
            target=target,
            journal_path=journal,
            cancel_requested=lambda: cancel,
            progress=on_progress,
            copy_buffer_size=8,
        ).run()

    assert payload.read_bytes() == bytes(range(64))
    assert not partial.exists()
    assert not (target / "large.bin").exists()
    state = json.loads(journal.read_text(encoding="utf-8"))
    assert state["state"] == "copying"
    assert state["files_copied"] == 0


def test_directory_metadata_is_preserved(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    journal = tmp_path / "state" / "migration.json"
    nested = source / "nested"
    nested.mkdir(parents=True)
    (nested / "payload.bin").write_bytes(b"data")
    os.chmod(nested, 0o750)
    timestamp_ns = 1_700_000_000_123_456_789
    os.utime(nested, ns=(timestamp_ns, timestamp_ns))

    MigrationEngine(source=source, target=target, journal_path=journal).run()

    copied = target / "nested"
    assert copied.stat().st_mode & 0o777 == 0o750
    assert copied.stat().st_mtime_ns == timestamp_ns


def test_fast_verification_hashes_critical_config_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    journal = tmp_path / "state" / "migration.json"
    source.mkdir()
    (source / ".anvil.ini").write_bytes(b"good")

    def corrupt_after_copy(progress) -> None:
        if progress.state is MigrationState.COPIED:
            (target / ".anvil.ini").write_bytes(b"evil")

    with pytest.raises(MigrationError, match="hash verification"):
        MigrationEngine(
            source=source,
            target=target,
            journal_path=journal,
            verification=VerificationLevel.FAST,
            progress=corrupt_after_copy,
        ).run()

    assert (source / ".anvil.ini").read_bytes() == b"good"


def test_instance_paths_switch_atomically_and_returns_old_values(tmp_path: Path) -> None:
    manager = InstanceManager(tmp_path / "instances")
    instance = manager.instances_path() / "Game"
    instance.mkdir()
    ini = instance / ".anvil.ini"
    ini.write_text(
        "[General]\nselected_profile=Default\n"
        "[Paths]\n"
        "mods_directory=%INSTANCE_DIR%/.mods\n"
        "backups_directory=%INSTANCE_DIR%/.backups\n"
        "cache_directory=%INSTANCE_DIR%/.webcache\n",
        encoding="utf-8",
    )
    new_mods = tmp_path / "external" / "Mods"
    new_cache = tmp_path / "external" / "Cache"

    old = manager.update_instance_paths_atomic(
        "Game",
        {
            "path_mods_directory": str(new_mods),
            "path_cache_directory": str(new_cache),
        },
    )

    loaded = manager.load_instance("Game")
    assert loaded["path_mods_directory"] == str(new_mods)
    assert loaded["path_cache_directory"] == str(new_cache)
    assert loaded["path_backups_directory"] == "%INSTANCE_DIR%/.backups"
    assert old == {
        "path_mods_directory": "%INSTANCE_DIR%/.mods",
        "path_cache_directory": "%INSTANCE_DIR%/.webcache",
    }
    assert not (instance / ".anvil.ini.migration.tmp").exists()


def test_component_migration_switches_reindexes_redeploys_and_reloads(tmp_path: Path) -> None:
    manager = InstanceManager(tmp_path / "instances")
    instance = manager.instances_path() / "Game"
    source = instance / ".mods"
    source.mkdir(parents=True)
    (source / "Example Mod").mkdir()
    (source / "Example Mod" / "mod.bin").write_bytes(b"mod")
    (instance / ".anvil.ini").write_text(
        "[General]\nselected_profile=Default\n"
        "[Paths]\nmods_directory=%INSTANCE_DIR%/.mods\n",
        encoding="utf-8",
    )
    target = tmp_path / "external" / "Game" / "Mods"
    journal = tmp_path / "state" / "move-mods.json"
    calls: list[object] = []

    result = InstanceComponentMigration(
        manager=manager,
        instance_name="Game",
        component="mods",
        target=target,
        journal_path=journal,
        purge=lambda: calls.append("purge") or True,
        reindex=lambda path: calls.append(("reindex", path)),
        redeploy=lambda: calls.append("redeploy") or True,
        reload_ui=lambda: calls.append("reload"),
    ).run()

    assert result.state is MigrationState.COMPLETE
    assert calls == ["purge", ("reindex", target), "redeploy", "reload"]
    assert manager.load_instance("Game")["path_mods_directory"] == str(target)
    assert (target / "Example Mod" / "mod.bin").read_bytes() == b"mod"
    assert (source / "Example Mod" / "mod.bin").read_bytes() == b"mod"
    assert json.loads(journal.read_text(encoding="utf-8"))["state"] == "complete"


def test_component_migration_rolls_back_path_when_redeploy_fails(tmp_path: Path) -> None:
    manager = InstanceManager(tmp_path / "instances")
    instance = manager.instances_path() / "Game"
    source = instance / ".mods"
    source.mkdir(parents=True)
    (source / "mod.bin").write_bytes(b"mod")
    (instance / ".anvil.ini").write_text(
        "[General]\nselected_profile=Default\n"
        "[Paths]\nmods_directory=%INSTANCE_DIR%/.mods\n",
        encoding="utf-8",
    )
    target = tmp_path / "external" / "Mods"
    journal = tmp_path / "state" / "move-mods.json"
    redeploy_calls = 0

    def redeploy() -> bool:
        nonlocal redeploy_calls
        redeploy_calls += 1
        return redeploy_calls > 1

    with pytest.raises(MigrationError, match="redeploy failed"):
        InstanceComponentMigration(
            manager=manager,
            instance_name="Game",
            component="mods",
            target=target,
            journal_path=journal,
            purge=lambda: True,
            redeploy=redeploy,
        ).run()

    assert manager.load_instance("Game")["path_mods_directory"] == "%INSTANCE_DIR%/.mods"
    assert (source / "mod.bin").read_bytes() == b"mod"
    assert (target / "mod.bin").read_bytes() == b"mod"
    assert redeploy_calls == 2
    state = json.loads(journal.read_text(encoding="utf-8"))
    assert state["state"] == "rollback_required"
    assert state["rollback_error"] == ""


def test_multi_component_migration_switches_all_paths_together(tmp_path: Path) -> None:
    from anvil.core.storage_migration import InstanceStorageMigration

    manager = InstanceManager(tmp_path / "instances")
    instance = manager.instances_path() / "Game"
    mods = instance / ".mods"
    downloads = instance / ".downloads"
    mods.mkdir(parents=True)
    downloads.mkdir()
    (mods / "mod.bin").write_bytes(b"mod")
    (downloads / "archive.zip").write_bytes(b"zip")
    (instance / ".anvil.ini").write_text(
        "[General]\nselected_profile=Default\n"
        "[Paths]\n"
        "mods_directory=%INSTANCE_DIR%/.mods\n"
        "downloads_directory=%INSTANCE_DIR%/.downloads\n",
        encoding="utf-8",
    )
    target = tmp_path / "external" / "Game"
    calls: list[str] = []

    result = InstanceStorageMigration(
        manager=manager,
        instance_name="Game",
        components={
            "mods": target / "Mods",
            "downloads": target / "Downloads",
        },
        journal_directory=tmp_path / "state",
        purge=lambda: calls.append("purge") or True,
        reindex=lambda _path: calls.append("reindex"),
        redeploy=lambda: calls.append("redeploy") or True,
        reload_ui=lambda: calls.append("reload"),
    ).run()

    loaded = manager.load_instance("Game")
    assert result.state is MigrationState.COMPLETE
    assert loaded["path_mods_directory"] == str(target / "Mods")
    assert loaded["path_downloads_directory"] == str(target / "Downloads")
    assert calls == ["purge", "reindex", "redeploy", "reload"]
    assert (mods / "mod.bin").is_file()
    assert (downloads / "archive.zip").is_file()


def test_deferred_component_migration_completes_only_after_redeploy(tmp_path: Path) -> None:
    from anvil.core.storage_migration import InstanceStorageMigration

    manager = InstanceManager(tmp_path / "instances")
    instance = manager.instances_path() / "Game"
    source = instance / ".mods"
    source.mkdir(parents=True)
    (source / "mod.bin").write_bytes(b"mod")
    (instance / ".anvil.ini").write_text(
        "[General]\nselected_profile=Default\n"
        "[Paths]\nmods_directory=%INSTANCE_DIR%/.mods\n",
        encoding="utf-8",
    )
    migration = InstanceStorageMigration(
        manager=manager,
        instance_name="Game",
        components={"mods": tmp_path / "external" / "Mods"},
        journal_directory=tmp_path / "state",
        defer_completion=True,
    )

    prepared = migration.run()
    assert prepared.state is MigrationState.REINDEXED
    assert json.loads((tmp_path / "state" / "mods.json").read_text())["state"] == "reindexed"

    completed = migration.complete_after_redeploy(True)
    assert completed.state is MigrationState.COMPLETE


def test_engine_excludes_explicit_runtime_paths(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "data.bin").write_bytes(b"payload")
    (source / "instance.sock").write_bytes(b"runtime")

    result = MigrationEngine(
        source=source,
        target=target,
        journal_path=tmp_path / "migration.json",
        excluded_relative_paths=(Path("instance.sock"),),
    ).run()

    assert result.state is MigrationState.VERIFIED
    assert (target / "data.bin").read_bytes() == b"payload"
    assert not (target / "instance.sock").exists()
    journal = json.loads((tmp_path / "migration.json").read_text())
    assert journal["total_bytes"] == len(b"payload")
    assert journal["excluded_relative_paths"] == ["instance.sock"]
