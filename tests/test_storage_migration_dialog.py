from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from anvil.core.instance_manager import InstanceManager
from anvil.dialogs.storage_migration_dialog import (
    StorageMigrationDialog,
    StorageMigrationRequest,
)


def _manager_with_instances(tmp_path: Path) -> InstanceManager:
    manager = InstanceManager(tmp_path / "instances")
    for name in ("Game A", "Game B"):
        instance = manager.instances_path() / name
        instance.mkdir()
        (instance / ".anvil.ini").write_text(
            "[General]\ngame_name=Test Game\nselected_profile=Default\n",
            encoding="utf-8",
        )
    return manager


def test_wizard_emits_all_instances_component_request(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    manager = _manager_with_instances(tmp_path)
    dialog = StorageMigrationDialog(
        manager=manager,
        current_instance="Game A",
    )
    requests: list[StorageMigrationRequest] = []
    dialog.migration_requested.connect(requests.append)

    dialog._scope_all.setChecked(True)
    dialog._component_boxes["mods"].setChecked(True)
    dialog._component_boxes["cache"].setChecked(True)
    dialog._target_edit.setText(str(tmp_path / "external"))
    dialog._start_migration()

    assert len(requests) == 1
    request = requests[0]
    assert request.instances == ("Game A", "Game B")
    assert request.components == ("mods", "cache")
    assert request.target_base == tmp_path / "external"
    assert dialog._stack.currentIndex() == dialog.PAGE_PROGRESS
    assert dialog._cancel_button.isEnabled()
    dialog.deleteLater()
    app.processEvents()


def test_wizard_multiple_scope_uses_checked_instances(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    manager = _manager_with_instances(tmp_path)
    dialog = StorageMigrationDialog(manager=manager, current_instance="Game A")
    dialog._scope_multiple.setChecked(True)
    for index in range(dialog._instance_list.count()):
        item = dialog._instance_list.item(index)
        item.setCheckState(
            Qt.CheckState.Checked if item.text() == "Game B" else Qt.CheckState.Unchecked
        )
    dialog._component_boxes["downloads"].setChecked(True)
    dialog._target_edit.setText(str(tmp_path / "external"))
    requests: list[StorageMigrationRequest] = []
    dialog.migration_requested.connect(requests.append)

    dialog._start_migration()

    assert requests[0].instances == ("Game B",)
    assert requests[0].components == ("downloads",)
    dialog.deleteLater()
    app.processEvents()


def test_wizard_base_directory_scope_skips_components(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    manager = _manager_with_instances(tmp_path)
    dialog = StorageMigrationDialog(manager=manager, current_instance="Game A")
    dialog._scope_base.setChecked(True)
    dialog._target_edit.setText(str(tmp_path / "new-anvil-base"))
    requests: list[StorageMigrationRequest] = []
    dialog.migration_requested.connect(requests.append)

    dialog._go_next()
    assert dialog._stack.currentIndex() == dialog.PAGE_TARGET
    dialog._start_migration()

    request = requests[0]
    assert request.base_directory is True
    assert request.instances == ()
    assert request.components == ("base",)
    assert request.target_base == tmp_path / "new-anvil-base"
    dialog.deleteLater()
    app.processEvents()
