from __future__ import annotations

from pathlib import Path
import struct
from typing import Any, cast

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QMessageBox,
    QTreeWidgetItem,
)

from anvil.core.plugin_sorter import parse_plugin_header, stable_dependency_sort
from anvil.core.plugins_txt_writer import (
    PluginEntry,
    PluginSortResult,
    PluginsTxtWriter,
)
from anvil.plugins.games._wip.game_morrowind import MorrowindGame
from anvil.plugins.games.game_fallout4 import Fallout4Game
from anvil.plugins.games.game_skyrimse import SkyrimSEGame
from anvil.plugins.games.game_starfield import StarfieldGame
from anvil.widgets.game_panel import GamePanel, _PluginOrderTree
from anvil.widgets.profile_bar import ProfileBar
from anvil.mainwindow import MainWindow


class FakeSkyrimGame:
    GameDataPath = "Data"
    PRIMARY_PLUGINS = [
        "Skyrim.esm",
        "Update.esm",
        "Dawnguard.esm",
        "HearthFires.esm",
        "Dragonborn.esm",
    ]
    PluginLoadOrderFormat = "asterisk"
    SupportsNativePluginSorting = True
    PluginIndexFormat = "regular-light"
    RequiresForgeDeployment = False
    NeedsBa2Packing = False
    ProtonDllOverrides: list[str] = []
    ImplicitPluginPrefixes = ("cc",)
    ImplicitPluginNames = ("_ResourcePack.esl",)

    def __init__(
        self, plugins_txt: Path, creation_club: Path | None = None,
    ) -> None:
        self._plugins_txt = plugins_txt
        self._creation_club = creation_club

    def plugins_txt_path(self) -> Path:
        return self._plugins_txt

    def has_plugins_txt(self) -> bool:
        return True

    def creation_club_path(self) -> Path | None:
        return self._creation_club


def _touch_plugins(data_dir: Path, names: list[str]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        (data_dir / name).touch()


def _write_tes4_plugin(
    path: Path, *, masters: tuple[str, ...] = (), flags: int = 0,
) -> None:
    payload = b""
    for master in masters:
        encoded = master.encode("cp1252") + b"\0"
        payload += b"MAST" + struct.pack("<H", len(encoded)) + encoded
        payload += b"DATA" + struct.pack("<H", 8) + b"\0" * 8
    header = struct.pack(
        "<4sIIIIHH", b"TES4", len(payload), flags, 0, 0, 0, 0
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + payload)


def test_existing_profile_order_and_activation_survive_write(tmp_path: Path) -> None:
    game_path = tmp_path / "game"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"

    names = [
        "Skyrim.esm",
        "Update.esm",
        "Dawnguard.esm",
        "HearthFires.esm",
        "Dragonborn.esm",
        "UIExtensions.esp",
        "Alternate Start - Live Another Life.esp",
    ]
    _touch_plugins(game_path / "Data", names)
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text(
        "*Skyrim.esm\n"
        "*Update.esm\n"
        "*Dawnguard.esm\n"
        "*HearthFires.esm\n"
        "*Dragonborn.esm\n"
        "UIExtensions.esp\n"
        "*Alternate Start - Live Another Life.esp\n",
        encoding="utf-8",
    )

    writer = PluginsTxtWriter(
        FakeSkyrimGame(external_txt),
        game_path,
        instance_path,
        profile_name="Default",
    )

    entries = writer.read_entries()
    writer.write_entries(entries)

    persisted = profile_txt.read_text(encoding="utf-8").splitlines()
    assert persisted == [
        "*Skyrim.esm",
        "*Update.esm",
        "*Dawnguard.esm",
        "*HearthFires.esm",
        "*Dragonborn.esm",
        "UIExtensions.esp",
        "*Alternate Start - Live Another Life.esp",
    ]
    assert external_txt.read_text(encoding="utf-8").splitlines() == persisted


def test_deploy_write_uses_profile_order_instead_of_alphabetical_scan(
    tmp_path: Path,
) -> None:
    game_path = tmp_path / "game"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"

    names = [
        "Skyrim.esm",
        "Update.esm",
        "Dawnguard.esm",
        "HearthFires.esm",
        "Dragonborn.esm",
        "UIExtensions.esp",
        "Alternate Start - Live Another Life.esp",
    ]
    _touch_plugins(game_path / "Data", names)
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text(
        "*Skyrim.esm\n"
        "*Update.esm\n"
        "*Dawnguard.esm\n"
        "*HearthFires.esm\n"
        "*Dragonborn.esm\n"
        "*UIExtensions.esp\n"
        "*Alternate Start - Live Another Life.esp\n",
        encoding="utf-8",
    )

    writer = PluginsTxtWriter(
        FakeSkyrimGame(external_txt),
        game_path,
        instance_path,
        profile_name="Default",
    )
    writer.write()

    assert external_txt.read_text(encoding="utf-8").splitlines() == [
        "*Skyrim.esm",
        "*Update.esm",
        "*Dawnguard.esm",
        "*HearthFires.esm",
        "*Dragonborn.esm",
        "*UIExtensions.esp",
        "*Alternate Start - Live Another Life.esp",
    ]


def test_silent_purge_does_not_delete_persistent_plugin_state(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    panel = GamePanel()

    class Purged:
        success = True

    class FakeDeployer:
        _separator_deploy_paths: dict[str, str] = {}

        def deploy(self):
            return Purged()

        def purge(self):
            return Purged()

        def is_deployed(self) -> bool:
            return True

    game = FakeSkyrimGame(tmp_path / "prefix" / "plugins.txt")
    panel._current_plugin = game
    panel._current_game_path = tmp_path / "game"
    panel._instance_path = tmp_path / "instance"
    panel._deployer = FakeDeployer()

    external_txt = game.plugins_txt_path()
    external_txt.parent.mkdir(parents=True)
    external_txt.write_text("*KeepMe.esp\n", encoding="utf-8")

    purge_result = panel.silent_purge()

    assert purge_result is not None
    assert bool(getattr(purge_result, "success", False))
    assert external_txt.read_text(encoding="utf-8") == "*KeepMe.esp\n"
    panel.deleteLater()
    app.processEvents()


def test_failed_deploy_does_not_change_plugin_state(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])

    class Failed:
        success = False
        links_created = 0
        errors = ["simulated deployment failure"]

    class FakeDeployer:
        _separator_deploy_paths: dict[str, str] = {}

        def deploy(self):
            return Failed()

        def purge(self):
            return Failed()

        def is_deployed(self) -> bool:
            return False

    game_path = tmp_path / "game"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    _touch_plugins(game_path / "Data", [*FakeSkyrimGame.PRIMARY_PLUGINS, "New.esp"])
    external_txt.parent.mkdir(parents=True)
    external_txt.write_text("*LastKnownGood.esp\n", encoding="utf-8")
    panel = GamePanel()
    panel._current_plugin = FakeSkyrimGame(external_txt)
    panel._current_game_path = game_path
    panel._instance_path = instance_path
    panel._deployer = FakeDeployer()

    panel.silent_deploy()

    assert external_txt.read_text(encoding="utf-8") == "*LastKnownGood.esp\n"
    assert not (instance_path / ".profiles" / "Default" / "plugins.txt").exists()
    panel.deleteLater()
    app.processEvents()


def test_plugin_state_write_failure_marks_deploy_failed(
    tmp_path: Path, monkeypatch,
) -> None:
    app = QApplication.instance() or QApplication([])

    class Result:
        success = True
        links_created = 1
        errors: list[str] = []

    class FakeDeployer:
        _separator_deploy_paths: dict[str, str] = {}

        def deploy(self):
            return Result()

        def purge(self):
            return Result()

        def is_deployed(self) -> bool:
            return True

    def fail_write(writer: PluginsTxtWriter):
        writer.last_error = "simulated plugin-state failure"
        return None

    panel = GamePanel()
    panel._current_plugin = FakeSkyrimGame(tmp_path / "plugins.txt")
    panel._current_game_path = tmp_path / "game"
    panel._instance_path = tmp_path / "instance"
    panel._deployer = FakeDeployer()
    monkeypatch.setattr(PluginsTxtWriter, "write", fail_write)

    result = panel.silent_deploy()

    assert result is not None
    assert not bool(getattr(result, "success", True))
    assert "simulated plugin-state failure" in getattr(result, "errors", [])
    panel.deleteLater()
    app.processEvents()


def test_auto_sort_write_failure_marks_deploy_failed(
    tmp_path: Path, monkeypatch,
) -> None:
    app = QApplication.instance() or QApplication([])

    class Result:
        def __init__(self):
            self.success = True
            self.links_created = 1
            self.errors: list[str] = []

    class FakeDeployer:
        _separator_deploy_paths: dict[str, str] = {}

        def deploy(self):
            return Result()

        def purge(self):
            return Result()

        def is_deployed(self) -> bool:
            return True

    monkeypatch.setattr(
        PluginsTxtWriter,
        "write",
        lambda _writer: tmp_path / "plugins.txt",
    )
    monkeypatch.setattr(
        PluginsTxtWriter,
        "sort_and_write",
        lambda _writer: PluginSortResult(
            entries=[],
            missing_masters={},
            cycles=[],
            parse_errors={},
            write_error="simulated auto-sort write failure",
        ),
    )
    monkeypatch.setattr(
        GamePanel,
        "_auto_plugin_sort_enabled",
        staticmethod(lambda: True),
    )
    panel = GamePanel()
    panel._current_plugin = FakeSkyrimGame(tmp_path / "plugins.txt")
    panel._current_game_path = tmp_path / "game"
    panel._instance_path = tmp_path / "instance"
    panel._deployer = FakeDeployer()

    result = panel.silent_deploy()

    assert result is not None
    assert not bool(getattr(result, "success", True))
    assert "simulated auto-sort write failure" in getattr(result, "errors", [])
    panel.deleteLater()
    app.processEvents()


def test_auto_sort_diagnostics_mark_deploy_failed(
    tmp_path: Path, monkeypatch,
) -> None:
    app = QApplication.instance() or QApplication([])

    class Result:
        def __init__(self):
            self.success = True
            self.links_created = 1
            self.errors: list[str] = []

    class FakeDeployer:
        _separator_deploy_paths: dict[str, str] = {}

        def deploy(self):
            return Result()

        def purge(self):
            return Result()

        def is_deployed(self) -> bool:
            return True

    monkeypatch.setattr(
        PluginsTxtWriter, "write", lambda _writer: tmp_path / "plugins.txt"
    )
    monkeypatch.setattr(
        PluginsTxtWriter,
        "sort_and_write",
        lambda _writer: PluginSortResult(
            entries=[],
            missing_masters={"Patch.esp": ["Missing.esm"]},
            cycles=[],
            parse_errors={},
        ),
    )
    monkeypatch.setattr(
        GamePanel, "_auto_plugin_sort_enabled", staticmethod(lambda: True)
    )
    panel = GamePanel()
    panel._current_plugin = FakeSkyrimGame(tmp_path / "plugins.txt")
    panel._current_game_path = tmp_path / "game"
    panel._instance_path = tmp_path / "instance"
    panel._deployer = FakeDeployer()

    result = panel.silent_deploy()

    assert result is not None
    assert not bool(getattr(result, "success", True))
    assert getattr(result, "errors", [])
    panel.deleteLater()
    app.processEvents()


def test_native_sort_places_creation_club_before_mods_and_honours_masters(
    tmp_path: Path,
) -> None:
    game_path = tmp_path / "game"
    data_dir = game_path / "Data"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    ccc_path = game_path / "Skyrim.ccc"
    ccc_path.parent.mkdir(parents=True)
    ccc_path.write_text("ccBGSSSE001-Fish.esm\nccQDRSSE001-SurvivalMode.esl\n")

    primary = FakeSkyrimGame.PRIMARY_PLUGINS
    for name in primary:
        _write_tes4_plugin(data_dir / name, flags=1)
    _write_tes4_plugin(data_dir / "ccBGSSSE001-Fish.esm", flags=1)
    _write_tes4_plugin(data_dir / "ccQDRSSE001-SurvivalMode.esl", flags=0x200)
    _write_tes4_plugin(data_dir / "UIExtensions.esp")
    _write_tes4_plugin(
        data_dir / "Alternate Start - Live Another Life.esp",
        masters=("Skyrim.esm", "Update.esm"),
    )
    _write_tes4_plugin(
        data_dir / "Alternate Start Patch.esp",
        masters=("Alternate Start - Live Another Life.esp",),
    )

    writer = PluginsTxtWriter(
        FakeSkyrimGame(external_txt, ccc_path),
        game_path,
        tmp_path / "instance",
    )
    current = [
        *(PluginEntry(name) for name in primary),
        PluginEntry("ccBGSSSE001-Fish.esm"),
        PluginEntry("Alternate Start Patch.esp"),
        PluginEntry("Alternate Start - Live Another Life.esp"),
        PluginEntry("UIExtensions.esp"),
        PluginEntry("ccQDRSSE001-SurvivalMode.esl"),
    ]

    result = writer.sort_entries(current)

    assert [entry.name for entry in result.entries] == [
        *primary,
        "ccBGSSSE001-Fish.esm",
        "ccQDRSSE001-SurvivalMode.esl",
        "Alternate Start - Live Another Life.esp",
        "Alternate Start Patch.esp",
        "UIExtensions.esp",
    ]
    assert result.missing_masters == {}
    assert result.cycles == []


def test_native_sort_does_not_apply_when_a_master_is_missing(tmp_path: Path) -> None:
    game_path = tmp_path / "game"
    data_dir = game_path / "Data"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    instance_path = tmp_path / "instance"
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"

    _write_tes4_plugin(data_dir / "Skyrim.esm", flags=1)
    _write_tes4_plugin(
        data_dir / "Broken Patch.esp", masters=("Missing Master.esm",)
    )
    external_txt.parent.mkdir(parents=True)
    external_txt.write_text("*Skyrim.esm\n", encoding="utf-8")
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text("*Skyrim.esm\n*Broken Patch.esp\n", encoding="utf-8")

    writer = PluginsTxtWriter(
        FakeSkyrimGame(external_txt), game_path, instance_path
    )

    result = writer.sort_and_write()

    assert result.missing_masters == {
        "Broken Patch.esp": ["Missing Master.esm"]
    }
    assert external_txt.read_text(encoding="utf-8").splitlines() == ["*Skyrim.esm"]


def test_inactive_broken_plugin_does_not_block_active_order(tmp_path: Path) -> None:
    game_path = tmp_path / "game"
    data_dir = game_path / "Data"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    instance_path = tmp_path / "instance"
    _write_tes4_plugin(data_dir / "Skyrim.esm", flags=1)
    _write_tes4_plugin(
        data_dir / "InactiveBroken.esp", masters=("Missing.esm",)
    )
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text("*Skyrim.esm\nInactiveBroken.esp\n", encoding="utf-8")
    writer = PluginsTxtWriter(
        FakeSkyrimGame(external_txt), game_path, instance_path
    )

    result = writer.sort_and_write()

    assert result.missing_masters == {}
    assert not result.write_error
    assert external_txt.is_file()


def test_active_plugin_requires_its_installed_master_to_be_active(
    tmp_path: Path,
) -> None:
    game_path = tmp_path / "game"
    data_dir = game_path / "Data"
    _write_tes4_plugin(data_dir / "OptionalMaster.esm", flags=1)
    _write_tes4_plugin(
        data_dir / "ActivePatch.esp", masters=("OptionalMaster.esm",)
    )
    writer = PluginsTxtWriter(
        FakeSkyrimGame(tmp_path / "plugins.txt"), game_path, tmp_path / "instance"
    )

    result = writer.sort_entries(
        [PluginEntry("OptionalMaster.esm", False), PluginEntry("ActivePatch.esp")]
    )

    assert result.missing_masters == {"ActivePatch.esp": ["OptionalMaster.esm"]}


def test_games_declare_their_load_order_format_explicitly() -> None:
    assert SkyrimSEGame.PluginLoadOrderFormat == "asterisk"
    assert SkyrimSEGame.CreationClubFile == "Skyrim.ccc"
    assert Fallout4Game.PluginLoadOrderFormat == "asterisk"
    assert StarfieldGame.PluginLoadOrderFormat == "asterisk"
    assert SkyrimSEGame.SupportsNativePluginSorting
    assert Fallout4Game.SupportsNativePluginSorting
    assert not StarfieldGame.SupportsNativePluginSorting
    assert SkyrimSEGame.PluginIndexFormat == "regular-light"
    assert Fallout4Game.PluginIndexFormat == "regular-light"
    assert StarfieldGame.PluginIndexFormat == ""
    assert "DLCUltraHighResolution.esm" not in Fallout4Game.PRIMARY_PLUGINS
    assert not StarfieldGame.ForcePrimaryPluginsActive
    assert SkyrimSEGame().has_plugins_txt()
    assert not MorrowindGame().has_plugins_txt()


def test_plugins_tab_displays_profile_order_and_activation(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    game_path = tmp_path / "game"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"
    names = [*FakeSkyrimGame.PRIMARY_PLUGINS, "UIExtensions.esp", "Alternate Start.esp"]
    _touch_plugins(game_path / "Data", names)
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text(
        "".join(f"*{name}\n" for name in FakeSkyrimGame.PRIMARY_PLUGINS)
        + "UIExtensions.esp\n"
        + "*Alternate Start.esp\n",
        encoding="utf-8",
    )

    panel = GamePanel()
    panel._current_plugin = FakeSkyrimGame(external_txt)
    panel._current_game_path = game_path
    panel._instance_path = instance_path
    panel._current_profile_name = "Default"

    panel._refresh_plugins_tab()

    displayed = []
    for index in range(panel._plugins_tree.topLevelItemCount()):
        item = panel._plugins_tree.topLevelItem(index)
        assert item is not None
        displayed.append(item)
    assert [item.text(0) for item in displayed] == names
    assert displayed[-2].checkState(0).value == 0
    assert displayed[-1].checkState(0).value == 2
    panel.deleteLater()
    app.processEvents()


def test_plugin_checkbox_persists_activation_to_profile_and_game(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    game_path = tmp_path / "game"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"
    names = [*FakeSkyrimGame.PRIMARY_PLUGINS, "UIExtensions.esp"]
    _touch_plugins(game_path / "Data", names)
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text(
        "".join(f"*{name}\n" for name in FakeSkyrimGame.PRIMARY_PLUGINS)
        + "UIExtensions.esp\n",
        encoding="utf-8",
    )

    panel = GamePanel()
    panel._current_plugin = FakeSkyrimGame(external_txt)
    panel._current_game_path = game_path
    panel._instance_path = instance_path
    panel._current_profile_name = "Default"
    panel._refresh_plugins_tab()

    plugin_item = panel._plugins_tree.topLevelItem(len(FakeSkyrimGame.PRIMARY_PLUGINS))
    assert plugin_item is not None
    plugin_item.setCheckState(0, Qt.CheckState.Checked)
    app.processEvents()

    assert profile_txt.read_text(encoding="utf-8").splitlines()[-1] == "*UIExtensions.esp"
    assert external_txt.read_text(encoding="utf-8").splitlines()[-1] == "*UIExtensions.esp"
    panel.deleteLater()
    app.processEvents()


def test_plugin_checkbox_write_failure_warns_and_restores_state(
    tmp_path: Path, monkeypatch,
) -> None:
    app = QApplication.instance() or QApplication([])
    game_path = tmp_path / "game"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"
    names = [*FakeSkyrimGame.PRIMARY_PLUGINS, "Optional.esp"]
    _touch_plugins(game_path / "Data", names)
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text(
        "".join(f"*{name}\n" for name in FakeSkyrimGame.PRIMARY_PLUGINS)
        + "Optional.esp\n",
        encoding="utf-8",
    )
    panel = GamePanel()
    panel._current_plugin = FakeSkyrimGame(external_txt)
    panel._current_game_path = game_path
    panel._instance_path = instance_path
    panel._refresh_plugins_tab()
    warnings: list[str] = []

    def fail_write(writer: PluginsTxtWriter, _entries: list[PluginEntry]):
        writer.last_error = "simulated checkbox write failure"
        return None

    monkeypatch.setattr(PluginsTxtWriter, "write_entries", fail_write)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    item = panel._plugins_tree.topLevelItem(len(FakeSkyrimGame.PRIMARY_PLUGINS))
    assert item is not None

    item.setCheckState(0, Qt.CheckState.Checked)
    app.processEvents()

    restored = panel._plugins_tree.topLevelItem(len(FakeSkyrimGame.PRIMARY_PLUGINS))
    assert warnings == ["simulated checkbox write failure"]
    assert restored is not None
    assert restored.checkState(0) == Qt.CheckState.Unchecked
    panel.deleteLater()
    app.processEvents()


def test_manual_plugin_reorder_is_persisted_after_primary_plugins(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    game_path = tmp_path / "game"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"
    names = [*FakeSkyrimGame.PRIMARY_PLUGINS, "First.esp", "Second.esp"]
    _touch_plugins(game_path / "Data", names)
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text(
        "".join(f"*{name}\n" for name in names), encoding="utf-8"
    )

    panel = GamePanel()
    panel._current_plugin = FakeSkyrimGame(external_txt)
    panel._current_game_path = game_path
    panel._instance_path = instance_path
    panel._current_profile_name = "Default"
    panel._refresh_plugins_tab()

    second = panel._plugins_tree.takeTopLevelItem(len(names) - 1)
    assert second is not None
    panel._plugins_tree.insertTopLevelItem(len(FakeSkyrimGame.PRIMARY_PLUGINS), second)
    for index in range(panel._plugins_tree.topLevelItemCount()):
        item = panel._plugins_tree.topLevelItem(index)
        assert item is not None
        assert not (item.flags() & Qt.ItemFlag.ItemIsDropEnabled)
    panel._plugins_tree.order_dropped.emit()
    app.processEvents()

    assert profile_txt.read_text(encoding="utf-8").splitlines() == [
        *(f"*{name}" for name in FakeSkyrimGame.PRIMARY_PLUGINS),
        "*Second.esp",
        "*First.esp",
    ]
    panel.deleteLater()
    app.processEvents()


def test_plugin_reorder_write_failure_warns(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    game_path = tmp_path / "game"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    names = [*FakeSkyrimGame.PRIMARY_PLUGINS, "First.esp", "Second.esp"]
    _touch_plugins(game_path / "Data", names)
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text(
        "".join(f"*{name}\n" for name in names), encoding="utf-8"
    )
    panel = GamePanel()
    panel._current_plugin = FakeSkyrimGame(external_txt)
    panel._current_game_path = game_path
    panel._instance_path = instance_path
    panel._refresh_plugins_tab()
    warnings: list[str] = []

    def fail_write(writer: PluginsTxtWriter, _entries: list[PluginEntry]):
        writer.last_error = "simulated reorder write failure"
        return None

    monkeypatch.setattr(PluginsTxtWriter, "write_entries", fail_write)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )

    persisted = panel._persist_plugin_tree_order()

    assert not persisted
    assert warnings == ["simulated reorder write failure"]
    panel.deleteLater()
    app.processEvents()


def test_game_panel_runs_native_sort_and_applies_valid_result(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    game_path = tmp_path / "game"
    data_dir = game_path / "Data"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    ccc_path = game_path / "Skyrim.ccc"
    ccc_path.parent.mkdir(parents=True)
    ccc_path.write_text("ccContent.esl\n", encoding="utf-8")

    for name in FakeSkyrimGame.PRIMARY_PLUGINS:
        _write_tes4_plugin(data_dir / name, flags=1)
    _write_tes4_plugin(data_dir / "ccContent.esl", flags=0x200)
    _write_tes4_plugin(
        data_dir / "Alternate Start.esp", masters=("Skyrim.esm",)
    )
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text(
        "".join(f"*{name}\n" for name in FakeSkyrimGame.PRIMARY_PLUGINS)
        + "*Alternate Start.esp\n*ccContent.esl\n",
        encoding="utf-8",
    )

    panel = GamePanel()
    panel._current_plugin = FakeSkyrimGame(external_txt, ccc_path)
    panel._current_game_path = game_path
    panel._instance_path = instance_path
    panel._current_profile_name = "Default"

    result = panel.sort_plugins_native()

    assert result is not None
    assert result.missing_masters == {}
    assert external_txt.read_text(encoding="utf-8").splitlines() == [
        *(f"*{name}" for name in FakeSkyrimGame.PRIMARY_PLUGINS),
        "*ccContent.esl",
        "*Alternate Start.esp",
    ]
    panel.deleteLater()
    app.processEvents()


def test_native_sort_recognises_skyrim_cc_files_without_ccc_manifest(
    tmp_path: Path,
) -> None:
    game_path = tmp_path / "game"
    data_dir = game_path / "Data"
    for name in FakeSkyrimGame.PRIMARY_PLUGINS:
        _write_tes4_plugin(data_dir / name, flags=1)
    _write_tes4_plugin(data_dir / "ccBGSSSE001-Fish.esm", flags=1)
    _write_tes4_plugin(data_dir / "_ResourcePack.esl", flags=0x200)
    _write_tes4_plugin(data_dir / "Alternate Start.esp")

    writer = PluginsTxtWriter(
        FakeSkyrimGame(tmp_path / "prefix" / "plugins.txt"),
        game_path,
        tmp_path / "instance",
    )
    current = [
        *(PluginEntry(name) for name in FakeSkyrimGame.PRIMARY_PLUGINS),
        PluginEntry("Alternate Start.esp"),
        PluginEntry("ccBGSSSE001-Fish.esm"),
        PluginEntry("_ResourcePack.esl"),
    ]

    result = writer.sort_entries(current)

    assert [entry.name for entry in result.entries][-3:] == [
        "ccBGSSSE001-Fish.esm",
        "_ResourcePack.esl",
        "Alternate Start.esp",
    ]


def test_creation_club_items_are_locked_in_plugins_tab(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    game_path = tmp_path / "game"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    names = [
        *FakeSkyrimGame.PRIMARY_PLUGINS,
        "ccBGSSSE001-Fish.esm",
        "Alternate Start.esp",
    ]
    _touch_plugins(game_path / "Data", names)
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text(
        "".join(f"*{name}\n" for name in names), encoding="utf-8"
    )

    panel = GamePanel()
    panel._current_plugin = FakeSkyrimGame(external_txt)
    panel._current_game_path = game_path
    panel._instance_path = instance_path
    panel._current_profile_name = "Default"
    panel._refresh_plugins_tab()

    cc_item = panel._plugins_tree.topLevelItem(len(FakeSkyrimGame.PRIMARY_PLUGINS))
    assert cc_item is not None
    assert not (cc_item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
    assert not (cc_item.flags() & Qt.ItemFlag.ItemIsDragEnabled)
    panel.deleteLater()
    app.processEvents()


def test_light_plugins_use_separate_fe_indices(tmp_path: Path) -> None:
    game_path = tmp_path / "game"
    data_dir = game_path / "Data"
    _write_tes4_plugin(data_dir / "Skyrim.esm", flags=1)
    _write_tes4_plugin(data_dir / "Regular.esp")
    _write_tes4_plugin(data_dir / "Light.esl", flags=0x200)
    _write_tes4_plugin(data_dir / "LightFlagged.esp", flags=0x200)
    _write_tes4_plugin(data_dir / "Disabled.esp")
    writer = PluginsTxtWriter(
        FakeSkyrimGame(tmp_path / "prefix" / "plugins.txt"),
        game_path,
        tmp_path / "instance",
    )
    entries = [
        PluginEntry("Skyrim.esm"),
        PluginEntry("Regular.esp"),
        PluginEntry("Light.esl"),
        PluginEntry("LightFlagged.esp"),
        PluginEntry("Disabled.esp", active=False),
    ]

    assert writer.plugin_indices(entries) == {
        "skyrim.esm": "00",
        "regular.esp": "01",
        "light.esl": "FE:000",
        "lightflagged.esp": "FE:001",
        "disabled.esp": "",
    }


def test_dependency_cycle_is_reported_and_not_applied(tmp_path: Path) -> None:
    game_path = tmp_path / "game"
    data_dir = game_path / "Data"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    instance_path = tmp_path / "instance"
    _write_tes4_plugin(data_dir / "CycleA.esp", masters=("CycleB.esp",))
    _write_tes4_plugin(data_dir / "CycleB.esp", masters=("CycleA.esp",))
    _write_tes4_plugin(data_dir / "Downstream.esp", masters=("CycleB.esp",))
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text(
        "*CycleA.esp\n*CycleB.esp\n*Downstream.esp\n", encoding="utf-8"
    )
    external_txt.parent.mkdir(parents=True)
    external_txt.write_text("*Original.esp\n", encoding="utf-8")
    writer = PluginsTxtWriter(
        FakeSkyrimGame(external_txt), game_path, instance_path
    )

    result = writer.sort_and_write()

    assert result.cycles == [["CycleA.esp", "CycleB.esp"]]
    assert external_txt.read_text(encoding="utf-8") == "*Original.esp\n"


def test_profiles_keep_independent_plugin_orders(tmp_path: Path) -> None:
    game_path = tmp_path / "game"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    _touch_plugins(game_path / "Data", ["First.esp", "Second.esp"])
    game = FakeSkyrimGame(external_txt)
    default_writer = PluginsTxtWriter(
        game, game_path, instance_path, profile_name="Default"
    )
    alternate_writer = PluginsTxtWriter(
        game, game_path, instance_path, profile_name="Alternate"
    )

    default_writer.write_entries(
        [PluginEntry("First.esp"), PluginEntry("Second.esp")]
    )
    alternate_writer.write_entries(
        [PluginEntry("Second.esp"), PluginEntry("First.esp", active=False)]
    )

    assert [entry.name for entry in default_writer.read_entries()] == [
        "First.esp", "Second.esp"
    ]
    alternate = alternate_writer.read_entries()
    assert [entry.name for entry in alternate] == ["Second.esp", "First.esp"]
    assert not alternate[-1].active


def test_implicit_creation_content_is_always_active(tmp_path: Path) -> None:
    game_path = tmp_path / "game"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    _touch_plugins(game_path / "Data", ["ccContent.esl", "Normal.esp"])
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text("ccContent.esl\n*Normal.esp\n", encoding="utf-8")
    writer = PluginsTxtWriter(
        FakeSkyrimGame(external_txt), game_path, instance_path
    )

    entries = writer.read_entries()

    assert entries[0] == PluginEntry("ccContent.esl", active=True)


def test_creation_manifest_disables_broad_cc_prefix_fallback(tmp_path: Path) -> None:
    game_path = tmp_path / "game"
    ccc_path = game_path / "Skyrim.ccc"
    ccc_path.parent.mkdir(parents=True)
    ccc_path.write_text("ccOfficial.esl\n", encoding="utf-8")
    entries = [
        PluginEntry("ccOfficial.esl"),
        PluginEntry("ccThirdParty.esp"),
    ]
    writer = PluginsTxtWriter(
        FakeSkyrimGame(tmp_path / "plugins.txt", ccc_path),
        game_path,
        tmp_path / "instance",
    )

    assert writer.implicit_plugin_names(entries) == ["ccOfficial.esl"]


def test_existing_empty_creation_manifest_does_not_enable_cc_prefix_fallback(
    tmp_path: Path,
) -> None:
    game_path = tmp_path / "game"
    ccc_path = game_path / "Skyrim.ccc"
    ccc_path.parent.mkdir(parents=True)
    ccc_path.write_text("", encoding="utf-8")
    writer = PluginsTxtWriter(
        FakeSkyrimGame(tmp_path / "plugins.txt", ccc_path),
        game_path,
        tmp_path / "instance",
    )

    implicit = writer.implicit_plugin_names([PluginEntry("ccThirdParty.esp")])

    assert implicit == []


def test_reconcile_places_forced_plugins_before_normal_mods(tmp_path: Path) -> None:
    game_path = tmp_path / "game"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    names = [*FakeSkyrimGame.PRIMARY_PLUGINS, "Normal.esp"]
    _touch_plugins(game_path / "Data", names)
    external_txt.parent.mkdir(parents=True)
    external_txt.write_text("*Normal.esp\n", encoding="utf-8")
    writer = PluginsTxtWriter(
        FakeSkyrimGame(external_txt), game_path, tmp_path / "instance"
    )

    entries = writer.read_entries()

    assert [entry.name for entry in entries] == [
        *FakeSkyrimGame.PRIMARY_PLUGINS,
        "Normal.esp",
    ]


def test_empty_or_unavailable_data_never_overwrites_existing_state(
    tmp_path: Path,
) -> None:
    game_path = tmp_path / "missing-game"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    external_txt.parent.mkdir(parents=True)
    external_txt.write_text("*KeepMe.esp\n", encoding="utf-8")
    writer = PluginsTxtWriter(
        FakeSkyrimGame(external_txt), game_path, instance_path
    )

    result = writer.sort_and_write()

    assert result.parse_errors
    assert external_txt.read_text(encoding="utf-8") == "*KeepMe.esp\n"


def test_failed_game_write_keeps_existing_case_variant(
    tmp_path: Path, monkeypatch,
) -> None:
    game_path = tmp_path / "game"
    instance_path = tmp_path / "instance"
    target = tmp_path / "prefix" / "plugins.txt"
    variant = target.with_name("Plugins.txt")
    variant.parent.mkdir(parents=True)
    variant.write_text("*LastKnownGood.esp\n", encoding="utf-8")
    writer = PluginsTxtWriter(FakeSkyrimGame(target), game_path, instance_path)
    original_atomic_write = writer._atomic_write

    def fail_only_game_path(path: Path, content: str) -> None:
        if path == target:
            raise PermissionError("simulated read-only prefix")
        original_atomic_write(path, content)

    monkeypatch.setattr(writer, "_atomic_write", fail_only_game_path)

    assert writer.write_entries([PluginEntry("New.esp")]) is None
    assert variant.read_text(encoding="utf-8") == "*LastKnownGood.esp\n"
    assert not writer.profile_plugins_path.exists()


def test_sort_result_reports_write_failure(tmp_path: Path, monkeypatch) -> None:
    game_path = tmp_path / "game"
    data_dir = game_path / "Data"
    _write_tes4_plugin(data_dir / "Only.esp")
    writer = PluginsTxtWriter(
        FakeSkyrimGame(tmp_path / "plugins.txt"),
        game_path,
        tmp_path / "instance",
    )

    def fail_write(_entries: list[PluginEntry]) -> None:
        writer.last_error = "simulated write failure"
        return None

    monkeypatch.setattr(writer, "write_entries", fail_write)

    result = writer.sort_and_write()

    assert result.write_error == "simulated write failure"


def test_rollback_never_follows_precreated_symlink(
    tmp_path: Path, monkeypatch,
) -> None:
    game_path = tmp_path / "game"
    instance_path = tmp_path / "instance"
    target = tmp_path / "prefix" / "plugins.txt"
    target.parent.mkdir(parents=True)
    target.write_text("*GameOld.esp\n", encoding="utf-8")
    writer = PluginsTxtWriter(FakeSkyrimGame(target), game_path, instance_path)
    profile = writer.profile_plugins_path
    profile.parent.mkdir(parents=True)
    profile.write_text("*ProfileOld.esp\n", encoding="utf-8")
    victim = tmp_path / "victim.txt"
    victim.write_text("DO NOT TOUCH\n", encoding="utf-8")
    rollback = profile.with_name(profile.name + ".anvil-rollback")
    rollback.symlink_to(victim)
    original_atomic_write = writer._atomic_write

    def fail_game_write(path: Path, content: str) -> None:
        if path == target:
            raise PermissionError("simulated game write failure")
        original_atomic_write(path, content)

    monkeypatch.setattr(writer, "_atomic_write", fail_game_write)

    assert writer.write_entries([PluginEntry("New.esp")]) is None
    assert victim.read_text(encoding="utf-8") == "DO NOT TOUCH\n"
    assert not profile.is_symlink()
    assert profile.read_text(encoding="utf-8") == "*ProfileOld.esp\n"


def test_profile_writer_rejects_symlinked_profile_directory(tmp_path: Path) -> None:
    instance_path = tmp_path / "instance"
    profiles_dir = instance_path / ".profiles"
    external = tmp_path / "external-profile"
    profiles_dir.mkdir(parents=True)
    external.mkdir()
    (profiles_dir / "Evil").symlink_to(external, target_is_directory=True)

    try:
        PluginsTxtWriter(
            FakeSkyrimGame(tmp_path / "plugins.txt"),
            tmp_path / "game",
            instance_path,
            profile_name="Evil",
        )
    except ValueError as exc:
        assert "profile path" in str(exc)
    else:
        raise AssertionError("symlinked profile directory was accepted")

    assert not (external / "plugins.txt").exists()


def test_profile_list_ignores_symlinked_directories(tmp_path: Path) -> None:
    instance_path = tmp_path / "instance"
    profiles_dir = instance_path / ".profiles"
    external = tmp_path / "external-profile"
    (profiles_dir / "Default").mkdir(parents=True)
    external.mkdir()
    (profiles_dir / "Evil").symlink_to(external, target_is_directory=True)

    class FakeWindow:
        _current_instance_path = instance_path

    profiles = MainWindow._get_profile_list(cast(Any, FakeWindow()))

    assert profiles == ["Default"]


def test_master_flagged_plugins_precede_nonmasters(tmp_path: Path) -> None:
    data_dir = tmp_path / "Data"
    _write_tes4_plugin(data_dir / "Regular.esp")
    _write_tes4_plugin(data_dir / "FlaggedMaster.esp", flags=0x00000001)

    result = stable_dependency_sort(
        ["Regular.esp", "FlaggedMaster.esp"], data_dir
    )

    assert result.names == ["FlaggedMaster.esp", "Regular.esp"]


def test_parser_rejects_trailing_and_invalid_extended_subrecords(
    tmp_path: Path,
) -> None:
    trailing = tmp_path / "Trailing.esp"
    trailing.write_bytes(struct.pack("<4sIIIIHH", b"TES4", 1, 0, 0, 0, 0, 0) + b"x")
    invalid_xxxx = tmp_path / "InvalidXXXX.esp"
    payload = struct.pack("<4sH", b"XXXX", 3) + b"bad"
    invalid_xxxx.write_bytes(
        struct.pack("<4sIIIIHH", b"TES4", len(payload), 0, 0, 0, 0, 0)
        + payload
    )
    valid_xxxx = tmp_path / "ValidXXXX.esp"
    valid_payload = (
        struct.pack("<4sH", b"XXXX", 4)
        + struct.pack("<I", 10)
        + struct.pack("<4sH", b"DATA", 0)
        + b"0123456789"
    )
    valid_xxxx.write_bytes(
        struct.pack("<4sIIIIHH", b"TES4", len(valid_payload), 0, 0, 0, 0, 0)
        + valid_payload
    )

    assert parse_plugin_header(trailing).error
    assert parse_plugin_header(invalid_xxxx).error
    assert not parse_plugin_header(valid_xxxx).error


def test_active_profile_rename_updates_game_panel_and_instance_metadata(
    tmp_path: Path, monkeypatch,
) -> None:
    app = QApplication.instance() or QApplication([])
    instance_path = tmp_path / "instance"
    old_path = instance_path / ".profiles" / "Old"
    old_path.mkdir(parents=True)

    class FakeInstanceManager:
        saved: dict | None = None

        def current_instance(self):
            return "instance-id"

        def load_instance(self, _instance_id):
            return {"selected_profile": "Old"}

        def save_instance(self, _instance_id, data):
            self.saved = data

    class FakeGamePanel:
        called_with: tuple[Path, str] | None = None

        def set_instance_path(self, path: Path, profile_name: str = "Default"):
            self.called_with = (path, profile_name)

    class FakeWindow:
        _current_instance_path = instance_path
        _current_profile_path = old_path
        instance_manager = FakeInstanceManager()
        _game_panel = FakeGamePanel()
        _profile_bar: ProfileBar

    monkeypatch.setattr("anvil.mainwindow.Toast", lambda *_args, **_kwargs: None)
    window = FakeWindow()
    bar = ProfileBar()
    bar.set_profiles(["Default", "Old"], active="Old")
    window._profile_bar = bar
    bar.profile_renamed.connect(
        lambda old, new: MainWindow._on_profile_renamed(
            cast(Any, window), old, new
        )
    )
    tab = next(tab for tab in bar._tabs if tab.text() == "Old")
    edit = QLineEdit()
    edit.setText("New")
    bar._rename_input = edit
    bar._rename_tab = tab
    tab.hide()

    bar._finish_inline_rename(edit, tab, "Old")

    assert window._current_profile_path == instance_path / ".profiles" / "New"
    assert window.instance_manager.saved == {"selected_profile": "New"}
    assert window._game_panel.called_with == (instance_path, "New")
    assert tab.text() == "New"
    bar.deleteLater()
    app.processEvents()


def test_inactive_plugin_cycle_does_not_block_active_load_order(
    tmp_path: Path,
) -> None:
    game_path = tmp_path / "game"
    data_dir = game_path / "Data"
    _write_tes4_plugin(data_dir / "Active.esp")
    _write_tes4_plugin(data_dir / "DisabledA.esp", masters=("DisabledB.esp",))
    _write_tes4_plugin(data_dir / "DisabledB.esp", masters=("DisabledA.esp",))
    writer = PluginsTxtWriter(
        FakeSkyrimGame(tmp_path / "plugins.txt"), game_path, tmp_path / "instance"
    )

    result = writer.sort_entries(
        [
            PluginEntry("Active.esp", True),
            PluginEntry("DisabledA.esp", False),
            PluginEntry("DisabledB.esp", False),
        ]
    )

    assert result.cycles == []


def test_large_cycle_is_reported_without_recursion_error(tmp_path: Path) -> None:
    data_dir = tmp_path / "Data"
    names = [f"Plugin{index:04d}.esp" for index in range(1100)]
    for index, name in enumerate(names):
        _write_tes4_plugin(
            data_dir / name,
            masters=(names[(index + 1) % len(names)],),
        )

    result = stable_dependency_sort(names, data_dir)

    assert len(result.cycles) == 1
    assert len(result.cycles[0]) == len(names)


def test_profile_bar_rejects_path_traversal_before_rename_signal() -> None:
    app = QApplication.instance() or QApplication([])
    bar = ProfileBar()
    bar.set_profiles(["Default", "Old"], active="Old")
    tab = next(tab for tab in bar._tabs if tab.text() == "Old")
    edit = QLineEdit()
    edit.setText("../Escaped")
    bar._rename_input = edit
    bar._rename_tab = tab
    tab.hide()
    active_before = bar._active_profile
    emitted: list[tuple[str, str]] = []
    bar.profile_renamed.connect(lambda old, new: emitted.append((old, new)))

    bar._finish_inline_rename(edit, tab, "Old")

    assert emitted == []
    assert tab.text() == "Old"
    assert bar._active_profile == active_before
    bar.deleteLater()
    app.processEvents()


def test_plugin_tree_ignored_drop_does_not_emit_order_changed() -> None:
    app = QApplication.instance() or QApplication([])
    tree = _PluginOrderTree()
    tree.setDragDropMode(tree.DragDropMode.InternalMove)
    tree.resize(300, 200)
    tree.show()
    for name in ("A", "B", "C"):
        tree.addTopLevelItem(QTreeWidgetItem([name]))
    app.processEvents()
    source_item = tree.topLevelItem(2)
    target_item = tree.topLevelItem(0)
    assert source_item is not None and target_item is not None
    source_index = tree.indexFromItem(source_item)
    mime = tree.model().mimeData([source_index])
    target = QPointF(tree.visualItemRect(target_item).center())
    event = QDropEvent(
        target,
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    emitted: list[bool] = []
    tree.order_dropped.connect(lambda: emitted.append(True))

    tree.dropEvent(event)
    app.processEvents()

    assert not event.isAccepted()
    assert emitted == []
    tree.deleteLater()
    app.processEvents()


def test_fallout4_real_game_class_sorts_ccc_and_profile_state(
    tmp_path: Path, monkeypatch,
) -> None:
    game_path = tmp_path / "Fallout 4"
    data_dir = game_path / "Data"
    instance_path = tmp_path / "instance"
    external_txt = tmp_path / "prefix" / "plugins.txt"
    ccc_path = game_path / "Fallout4.ccc"
    _write_tes4_plugin(data_dir / "Fallout4.esm", flags=1)
    _write_tes4_plugin(data_dir / "ccOfficial.esl", flags=0x200)
    _write_tes4_plugin(
        data_dir / "UserPatch.esp", masters=("Fallout4.esm",)
    )
    ccc_path.write_text("ccOfficial.esl\n", encoding="utf-8")
    profile_txt = instance_path / ".profiles" / "Default" / "plugins.txt"
    profile_txt.parent.mkdir(parents=True)
    profile_txt.write_text(
        "*UserPatch.esp\n*ccOfficial.esl\n*Fallout4.esm\n",
        encoding="utf-8",
    )
    game = Fallout4Game()
    monkeypatch.setattr(game, "plugins_txt_path", lambda: external_txt)
    monkeypatch.setattr(
        game, "creation_club_path", lambda: ccc_path, raising=False
    )
    writer = PluginsTxtWriter(game, game_path, instance_path)

    result = writer.sort_and_write()

    assert not result.missing_masters
    assert not result.cycles
    assert not result.parse_errors
    assert not result.write_error
    assert external_txt.read_text(encoding="utf-8").splitlines() == [
        "*Fallout4.esm",
        "*ccOfficial.esl",
        "*UserPatch.esp",
    ]


def test_profile_delete_rejects_path_traversal(tmp_path: Path, monkeypatch) -> None:
    instance_path = tmp_path / "instance"
    profiles_dir = instance_path / ".profiles"
    default_path = profiles_dir / "Default"
    victim = instance_path / "victim"
    default_path.mkdir(parents=True)
    victim.mkdir()

    class FakeBar:
        _active_profile = "Default"

        def set_profiles(self, _profiles, active=None):
            self._active_profile = active or self._active_profile

    class FakeWindow:
        _current_instance_path = instance_path
        _current_profile_path = default_path
        _profile_bar = FakeBar()

    monkeypatch.setattr("anvil.mainwindow.Toast", lambda *_args, **_kwargs: None)

    MainWindow._on_profile_deleted(cast(Any, FakeWindow()), "../victim")

    assert victim.is_dir()


def test_profile_rename_collision_rolls_back_ui_and_metadata(
    tmp_path: Path, monkeypatch,
) -> None:
    app = QApplication.instance() or QApplication([])
    instance_path = tmp_path / "instance"
    profiles_dir = instance_path / ".profiles"
    old_path = profiles_dir / "Old"
    new_path = profiles_dir / "New"
    old_path.mkdir(parents=True)
    new_path.mkdir()

    class FakeInstanceManager:
        saved = None

        def current_instance(self):
            return "instance-id"

        def load_instance(self, _instance_id):
            return {"selected_profile": "Old"}

        def save_instance(self, _instance_id, data):
            self.saved = data

    class FakeGamePanel:
        called_with = None

        def set_instance_path(self, path, profile_name="Default"):
            self.called_with = (path, profile_name)

    bar = ProfileBar()
    bar.set_profiles(["Default", "New"], active="New")
    bar._active_profile = "New"

    class FakeWindow:
        _current_instance_path = instance_path
        _current_profile_path = old_path
        instance_manager = FakeInstanceManager()
        _game_panel = FakeGamePanel()
        _profile_bar = bar

    warnings: list[str] = []
    monkeypatch.setattr("anvil.mainwindow.Toast", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    window = FakeWindow()

    MainWindow._on_profile_renamed(cast(Any, window), "Old", "New")

    assert window._current_profile_path == old_path
    assert window.instance_manager.saved is None
    assert window._game_panel.called_with is None
    assert [tab.text() for tab in bar._tabs] == ["Default", "Old"]
    assert warnings
    bar.deleteLater()
    app.processEvents()
