from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog

from anvil.core.base_migration import schedule_base_migration
from anvil.core.storage_migration import VerificationLevel
from anvil.widgets.base_migration_dialog import BaseMigrationProgressDialog


def test_startup_base_migration_dialog_runs_worker_to_completion(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "config.ini"), QSettings.Format.IniFormat)
    source = tmp_path / "old-base"
    target = tmp_path / "new-base"
    (source / "instances" / "Fixture").mkdir(parents=True)
    (source / "instances" / "Fixture" / ".anvil.ini").write_text("[General]\n")
    schedule_base_migration(
        source=source,
        target=target,
        verification=VerificationLevel.FULL,
        settings=settings,
    )

    dialog = BaseMigrationProgressDialog(settings=settings)
    result = dialog.start()

    assert result == QDialog.DialogCode.Accepted
    assert dialog.succeeded
    assert (target / "instances" / "Fixture" / ".anvil.ini").is_file()
    assert settings.value("General/base_dir") == str(target)
    assert not dialog._thread.isRunning()
    dialog.deleteLater()
    app.processEvents()
