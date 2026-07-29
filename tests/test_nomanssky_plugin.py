import json
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from anvil.plugins.games._wip.game_nomanssky import NoMansSkyGame
from anvil.plugins.plugin_loader import PluginLoader
import anvil.plugins.plugin_loader as plugin_loader_module
from anvil.widgets.plugin_creator_dialog import PluginCreatorDialog
import anvil.widgets.plugin_creator_dialog as plugin_creator_module


def test_nomanssky_uses_current_mod_directory() -> None:
    assert NoMansSkyGame.GameDataPath == "GAMEDATA/MODS"


def test_user_plugin_replaces_builtin_ignoring_short_name_case(
    tmp_path: Path,
) -> None:
    custom_plugin = tmp_path / "game_custom_nomanssky.py"
    custom_plugin.write_text(
        "from anvil.plugins.base_game import BaseGame\n"
        "class CustomNoMansSkyGame(BaseGame):\n"
        "    GameName = \"No Man's Sky\"\n"
        "    GameShortName = \"NoMansSky\"\n"
        "    GameBinary = \"Binaries/NMS.exe\"\n"
        "    GameDataPath = \"CustomNMSMods\"\n"
        "    GameSteamId = 275850\n",
        encoding="utf-8",
    )

    loader = PluginLoader()
    loader._plugins = [NoMansSkyGame()]
    loader._scan_directory(tmp_path)

    assert loader.plugin_count() == 1
    plugin = loader.get_game("nomanssky")
    assert plugin is not None
    assert plugin is loader.get_game("NoMansSky")
    assert plugin.GameDataPath == "CustomNMSMods"


def test_plugin_editor_data_path_override_is_applied_after_reload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = QApplication.instance() or QApplication([])
    user_plugins = tmp_path / "user_plugins"
    user_plugins.mkdir()
    monkeypatch.setattr(plugin_creator_module, "_USER_PLUGINS_DIR", user_plugins)
    monkeypatch.setattr(plugin_loader_module, "_USER_GAMES_DIR", user_plugins)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    json_path = user_plugins / "game_nomanssky.json"
    json_path.write_text('{"customKey": "preserved"}', encoding="utf-8")

    dialog = PluginCreatorDialog(plugin=NoMansSkyGame())
    dialog._data_path.setCurrentText("Custom/NMS/MODS")
    dialog._on_save()

    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["customKey"] == "preserved"
    assert saved["overrides"]["GameDataPath"] == "Custom/NMS/MODS"

    builtin_plugins = tmp_path / "builtin_plugins"
    builtin_plugins.mkdir()
    (builtin_plugins / "game_nomanssky.py").write_text(
        "from anvil.plugins.base_game import BaseGame\n"
        "class BuiltinNoMansSkyGame(BaseGame):\n"
        "    GameName = \"No Man's Sky\"\n"
        "    GameShortName = \"nomanssky\"\n"
        "    GameBinary = \"Binaries/NMS.exe\"\n"
        "    GameDataPath = \"GAMEDATA/MODS\"\n"
        "    GameSteamId = 275850\n",
        encoding="utf-8",
    )

    loader = PluginLoader()
    loader._scan_directory(builtin_plugins)

    plugin = loader.get_game("nomanssky")
    assert plugin is not None
    assert plugin.GameDataPath == "Custom/NMS/MODS"
    dialog.deleteLater()
    app.processEvents()
