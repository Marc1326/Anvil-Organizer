from pathlib import Path

from PySide6.QtWidgets import QApplication

from anvil.plugins.games.game_skyrimse import SkyrimSEGame
from anvil.widgets.game_panel import GamePanel


_SHIM_BINARY = (
    Path(__file__).parents[1]
    / "anvil"
    / "data"
    / "shims"
    / "skyrimse"
    / "winhttp.dll"
)


def test_skyrim_skse_configuration_is_runtime_independent() -> None:
    game = SkyrimSEGame()
    framework = next(fw for fw in game.get_framework_mods() if fw.name == "SKSE64")

    assert game.GameProtonDllOverrides == {"winhttp": "native,builtin"}
    assert "skse64_*.dll" in framework.pattern
    assert "skse64_*.dll" in framework.detect_installed
    assert "skse64_1_6_1170.dll" not in framework.pattern


def test_skyrim_winhttp_override_is_written_to_proton_prefix(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    prefix = tmp_path / "pfx"
    prefix.mkdir()
    user_reg = prefix / "user.reg"
    user_reg.write_text("WINE REGISTRY Version 2\n", encoding="utf-8")

    game = SkyrimSEGame()
    game.protonPrefix = lambda: prefix
    panel = GamePanel()
    panel._current_plugin = game

    panel._apply_proton_dll_overrides()

    registry = user_reg.read_text(encoding="utf-8")
    assert "[Software\\\\Wine\\\\AppDefaults\\\\SkyrimSE.exe\\\\DllOverrides]" in registry
    assert '"winhttp"="native,builtin"' in registry
    panel.deleteLater()
    app.processEvents()


def test_skse_shim_binary_discovers_the_installed_runtime_dll() -> None:
    binary = _SHIM_BINARY.read_bytes()
    pe_offset = int.from_bytes(binary[0x3C:0x40], "little")
    machine = int.from_bytes(binary[pe_offset + 4:pe_offset + 6], "little")
    characteristics = int.from_bytes(
        binary[pe_offset + 22:pe_offset + 24], "little"
    )

    assert binary[:2] == b"MZ"
    assert binary[pe_offset:pe_offset + 4] == b"PE\0\0"
    assert machine == 0x8664
    assert characteristics & 0x2000
    assert b"skse64_*.dll" in binary
    assert b"skse64_1_6_1170.dll" not in binary


def test_skyrim_shim_binary_is_deployed_to_the_game_root(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    game_root = tmp_path / "Skyrim Special Edition"
    game_root.mkdir()

    panel = GamePanel()
    panel._current_plugin = SkyrimSEGame()
    panel._current_game_path = game_root
    panel._instance_path = tmp_path / "instance"
    panel._deploy_proton_shims(["winhttp.dll"])

    assert (game_root / "winhttp.dll").read_bytes() == _SHIM_BINARY.read_bytes()
    panel.deleteLater()
    app.processEvents()
