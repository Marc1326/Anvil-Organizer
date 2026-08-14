from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from anvil.widgets.settings_dialog import SettingsDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _InstanceManager:
    def __init__(self, root: Path, data: dict) -> None:
        self._root = root
        self._data = dict(data)
        self.saved: dict | None = None
        (root / "Test").mkdir(parents=True)

    def current_instance(self) -> str:
        return "Test"

    def load_instance(self, _name: str) -> dict:
        return dict(self._data)

    def save_instance(self, _name: str, data: dict) -> None:
        self.saved = dict(data)
        self._data = dict(data)

    def instances_path(self) -> Path:
        return self._root


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        return QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.fixture
def dialog_factory(app: QApplication, monkeypatch, tmp_path: Path):
    settings_path = tmp_path / "settings.ini"
    monkeypatch.setattr(
        SettingsDialog,
        "_settings",
        staticmethod(lambda: QSettings(str(settings_path), QSettings.Format.IniFormat)),
    )
    monkeypatch.setattr(SettingsDialog, "load_api_key", staticmethod(lambda: ""))
    monkeypatch.setattr(
        "anvil.core.overlay_deployer.environment_problems",
        lambda _upper, _game: [],
    )

    dialogs: list[SettingsDialog] = []

    def create(*, overlay: bool, keep: bool = True):
        game = tmp_path / "game"
        game.mkdir(exist_ok=True)
        manager = _InstanceManager(
            tmp_path / "instances",
            {
                "game_path": str(game),
                "path_overwrite_directory": str(tmp_path / "overwrite"),
                "use_overlay": overlay,
                "keep_mods_deployed": keep,
            },
        )
        dialog = SettingsDialog(instance_manager=manager)
        dialog.show()
        app.processEvents()
        dialogs.append(dialog)
        return dialog, manager

    yield create

    for dialog in dialogs:
        dialog.close()


def test_overlay_blendet_dauerbetrieb_beim_oeffnen_aus(dialog_factory) -> None:
    dialog, _manager = dialog_factory(overlay=True)

    assert dialog._keep_deployed_group.isHidden()


def test_deploymethode_aktualisiert_dauerbetrieb_sofort(
    app: QApplication, dialog_factory
) -> None:
    dialog, _manager = dialog_factory(overlay=False)
    assert not dialog._keep_deployed_group.isHidden()

    dialog._radio_overlay.setChecked(True)
    app.processEvents()
    assert dialog._keep_deployed_group.isHidden()

    dialog._radio_symlink.setChecked(True)
    app.processEvents()
    assert not dialog._keep_deployed_group.isHidden()


def test_overlay_speichert_dauerbetrieb_immer_als_false(dialog_factory) -> None:
    dialog, manager = dialog_factory(overlay=False, keep=True)
    dialog._radio_overlay.setChecked(True)

    dialog.accept()

    assert manager.saved is not None
    assert manager.saved["use_overlay"] is True
    assert manager.saved["keep_mods_deployed"] is False


def test_expertenbereich_verlinkt_das_github_wiki(dialog_factory) -> None:
    dialog, _manager = dialog_factory(overlay=True)

    link = dialog._deployment_wiki_link
    assert link.openExternalLinks()
    assert 'href="https://github.com/Marc1326/Anvil-Organizer/wiki/' in link.text()
