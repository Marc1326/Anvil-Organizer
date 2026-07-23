import json
from pathlib import Path

from PySide6.QtCore import QSettings

from anvil.core.base_migration import (
    execute_pending_base_migration,
    pending_base_migration,
    schedule_base_migration,
)
from anvil.core.storage_migration import VerificationLevel


def test_pending_base_migration_copies_switches_and_retains_source(tmp_path: Path) -> None:
    settings = QSettings(str(tmp_path / "config" / "Anvil.conf"), QSettings.Format.IniFormat)
    source = tmp_path / "old-base"
    target = tmp_path / "new-base"
    (source / "instances" / "Game").mkdir(parents=True)
    (source / "instances" / "Game" / ".anvil.ini").write_text("[General]\n")
    (source / "credentials.json").write_text('{"token": "fixture"}')
    (source / "instance.sock").write_text("runtime")

    schedule_base_migration(
        source=source,
        target=target,
        verification=VerificationLevel.FULL,
        settings=settings,
    )
    result = execute_pending_base_migration(settings=settings)

    assert result == target
    assert (target / "instances" / "Game" / ".anvil.ini").is_file()
    assert json.loads((target / "credentials.json").read_text()) == {"token": "fixture"}
    assert not (target / "instance.sock").exists()
    assert (target / ".anvil-base.json").is_file()
    assert (source / "credentials.json").is_file()
    assert (source / "instance.sock").is_file()
    assert settings.value("General/base_dir") == str(target)
    assert pending_base_migration(settings) is None


def test_base_migration_rejects_nested_target(tmp_path: Path) -> None:
    settings = QSettings(str(tmp_path / "Anvil.conf"), QSettings.Format.IniFormat)
    source = tmp_path / "base"
    source.mkdir()

    try:
        schedule_base_migration(
            source=source,
            target=source / "nested",
            verification=VerificationLevel.FULL,
            settings=settings,
        )
    except ValueError as exc:
        assert "inside" in str(exc)
    else:
        raise AssertionError("nested base migration target was accepted")
