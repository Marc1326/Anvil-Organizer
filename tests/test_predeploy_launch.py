"""Tests for blocking game launch when pre-deployment fails."""

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

from PySide6.QtWidgets import QApplication

from anvil.mainwindow import MainWindow
from anvil.widgets.game_panel import GamePanel


class _Timer:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _StatusBar:
    def __init__(self) -> None:
        self.messages: list[tuple[str, int]] = []

    def showMessage(self, text: str, timeout: int = 0) -> None:
        self.messages.append((text, timeout))


class _Widget:
    """Stand-in for the Qt widgets _unlock_ui touches."""

    def __init__(self) -> None:
        self.visible = True
        self.enabled = False

    def setVisible(self, value: bool) -> None:
        self.visible = value

    def setEnabled(self, value: bool) -> None:
        self.enabled = value


class PredeployLaunchTests(unittest.TestCase):
    def test_failed_deploy_returns_false_to_block_launch(self) -> None:
        timer = _Timer()
        panel = SimpleNamespace(
            silent_purge=lambda: SimpleNamespace(success=True, errors=[]),
            silent_deploy=lambda: SimpleNamespace(
                success=False, errors=["injected deploy failure"]
            ),
        )
        window: Any = SimpleNamespace(
            _redeploy_timer=timer,
            _current_instance_path=Path("/tmp/instance"),
            _auto_relock_instance=lambda _path, _reason: None,
            _game_panel=panel,
            _sync_separator_deploy_paths=lambda: None,
            _log_game_dir_state=lambda _phase: None,
        )

        success = MainWindow._predeploy_for_launch(window, "game_start")

        self.assertIs(success, False)
        self.assertTrue(timer.stopped)

    def test_direct_launch_stops_when_predeploy_fails(self) -> None:
        window: Any = SimpleNamespace(
            _predeploy_for_launch=lambda _reason: False,
        )

        with mock.patch("anvil.mainwindow.host_popen") as popen, mock.patch(
            "anvil.mainwindow.QMessageBox.warning"
        ) as warning:
            MainWindow._on_start_game(window, "/game/GRB.exe", "/game")

        popen.assert_not_called()
        warning.assert_called_once()

    def test_custom_tool_stops_when_predeploy_fails(self) -> None:
        panel = SimpleNamespace(run_with_proton=mock.Mock())
        window: Any = SimpleNamespace(
            _predeploy_for_launch=lambda _reason: False,
            _game_panel=panel,
        )

        with mock.patch("anvil.mainwindow.host_popen") as popen:
            MainWindow._on_custom_tool_start(
                window,
                "/tools/xedit.exe",
                [],
                "/tools",
                True,
            )

        panel.run_with_proton.assert_not_called()
        popen.assert_not_called()

    def test_toolbar_proton_tool_stops_when_predeploy_fails(self) -> None:
        predeploy = mock.Mock(return_value=False)
        panel = SimpleNamespace(run_with_proton=mock.Mock())
        window: Any = SimpleNamespace(
            _current_instance_path=Path("/tmp/instance"),
            _predeploy_for_launch=predeploy,
            _game_panel=panel,
        )
        tools = [
            {
                "name": "BodySlide",
                "exe_path": "/tools/BodySlide.exe",
                "args": [],
                "working_dir": "/tools",
            }
        ]

        with mock.patch(
            "anvil.widgets.proton_tools_dialog.load_proton_tools",
            return_value=tools,
        ):
            MainWindow._run_proton_tool(window, 0)

        predeploy.assert_called_once_with("proton_tool_start")
        panel.run_with_proton.assert_not_called()

    def test_failed_predeploy_does_not_emit_game_started(self) -> None:
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as temp:
            game_path = Path(temp)
            (game_path / "game.exe").touch()
            panel = GamePanel()
            panel._current_game_path = game_path
            panel._game_label.setText("Test Game")
            window: Any = SimpleNamespace(
                _predeploy_for_launch=lambda _reason: False,
            )
            panel.start_requested.connect(
                lambda binary, working: MainWindow._on_start_game(
                    window, binary, working
                )
            )
            started: list[tuple[str, int]] = []
            panel.game_started.connect(
                lambda name, pid: started.append((name, pid))
            )

            with mock.patch("anvil.mainwindow.QMessageBox.warning"):
                panel._do_launch(None, "game.exe", False)

            self.assertEqual(started, [])
            panel.deleteLater()
            app.processEvents()

    def test_successful_direct_launch_emits_real_pid(self) -> None:
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as temp:
            game_path = Path(temp)
            (game_path / "game.exe").touch()
            panel = GamePanel()
            panel._current_game_path = game_path
            panel._game_label.setText("Test Game")
            window: Any = SimpleNamespace(
                _predeploy_for_launch=lambda _reason: True,
                _game_panel=panel,
            )
            panel.start_requested.connect(
                lambda binary, working: MainWindow._on_start_game(
                    window, binary, working
                )
            )
            started: list[tuple[str, int]] = []
            panel.game_started.connect(
                lambda name, pid: started.append((name, pid))
            )

            with mock.patch(
                "anvil.mainwindow.host_popen",
                return_value=SimpleNamespace(pid=12345),
            ):
                panel._do_launch(None, "game.exe", False)

            self.assertEqual(started, [("Test Game", 12345)])
            panel.deleteLater()
            app.processEvents()

    def test_auto_redeploy_reports_failure_instead_of_success(self) -> None:
        timer = _Timer()
        status = _StatusBar()
        panel = SimpleNamespace(
            has_deployment=lambda: True,
            silent_purge=lambda: SimpleNamespace(
                success=False, errors=["injected purge failure"]
            ),
        )
        window: Any = SimpleNamespace(
            _redeploy_timer=timer,
            _current_instance_path=Path("/tmp/instance"),
            _bg3_installer=None,
            _game_panel=panel,
            _sync_separator_deploy_paths=lambda: None,
            statusBar=lambda: status,
        )

        with mock.patch("anvil.mainwindow.QMessageBox.warning") as warning:
            success = MainWindow._do_redeploy(window)

        self.assertIs(success, False)
        warning.assert_called_once()
        self.assertFalse(any("deployed" in text.lower() for text, _ in status.messages))

    def test_unlock_keeps_deployment_while_game_runs(self) -> None:
        """Pulling the mods out from under a running game crashes it."""
        calls: list[str] = []
        panel = SimpleNamespace(
            is_game_running=lambda: True,
            silent_purge=lambda: calls.append("purge"),
        )
        window: Any = SimpleNamespace(
            _game_panel=panel,
            _game_running=True,
            _lock_overlay=_Widget(),
            _splitter=_Widget(),
            _log_container=_Widget(),
            _toolbar=_Widget(),
            menuBar=lambda: _Widget(),
            _log_game_dir_state=lambda _phase: None,
        )

        MainWindow._unlock_ui(window)

        self.assertEqual(calls, [])
        self.assertIs(window._game_running, False)

    def test_unlock_cleans_up_once_the_game_is_gone(self) -> None:
        calls: list[str] = []
        panel = SimpleNamespace(
            is_game_running=lambda: False,
            silent_purge=lambda: (
                calls.append("purge"), SimpleNamespace(success=True, errors=[])
            )[1],
        )
        window: Any = SimpleNamespace(
            _game_panel=panel,
            _game_running=True,
            _lock_overlay=_Widget(),
            _splitter=_Widget(),
            _log_container=_Widget(),
            _toolbar=_Widget(),
            menuBar=lambda: _Widget(),
            _log_game_dir_state=lambda _phase: None,
        )

        MainWindow._unlock_ui(window)

        self.assertEqual(calls, ["purge"])

    def test_full_cycle_against_a_stand_in_process(self) -> None:
        """Drive the whole cycle against a process that looks like the game.

        The searched name is assembled at runtime so neither this file nor
        the shell running it carries it in a command line -- the /proc scan
        would otherwise match the test itself.
        """
        import subprocess
        import time

        binary = "".join(["stand", "in", "game", "42", ".exe"])
        panel_state: Any = SimpleNamespace(_watch_binary=binary, _watch_app_id=None)
        panel_state.find_game_pid = lambda: GamePanel.find_game_pid(panel_state)
        running = lambda: GamePanel.is_game_running(panel_state)

        self.assertFalse(running(), "nothing should match before the process exists")

        stand_in = subprocess.Popen(
            ["python3", "-c", "import time; time.sleep(30)", "/game/" + binary]
        )
        try:
            deadline = time.monotonic() + 10
            while not running() and time.monotonic() < deadline:
                time.sleep(0.2)
            self.assertTrue(running(), "the stand-in process was not detected")

            purges: list[str] = []
            window: Any = SimpleNamespace(
                _game_panel=SimpleNamespace(
                    is_game_running=running,
                    silent_purge=lambda: purges.append("purge"),
                ),
                _game_running=True,
                _lock_overlay=_Widget(),
                _splitter=_Widget(),
                _log_container=_Widget(),
                _toolbar=_Widget(),
                menuBar=lambda: _Widget(),
                _log_game_dir_state=lambda _phase: None,
            )

            MainWindow._unlock_ui(window)
            self.assertEqual(purges, [], "must not purge while the game runs")
        finally:
            stand_in.terminate()
            stand_in.wait()

        deadline = time.monotonic() + 10
        while running() and time.monotonic() < deadline:
            time.sleep(0.2)
        self.assertFalse(running(), "process gone, but still reported as running")

        MainWindow._unlock_ui(window)
        self.assertEqual(purges, ["purge"], "should clean up once the game is gone")

    def test_auto_redeploy_never_deploys(self) -> None:
        """Toggling a mod must not put anything into the game directory."""
        calls: list[str] = []
        panel = SimpleNamespace(
            has_deployment=lambda: True,
            silent_purge=lambda: (
                calls.append("purge"), SimpleNamespace(success=True, errors=[])
            )[1],
            silent_deploy=lambda: calls.append("deploy"),
            silent_deploy_fast=lambda: calls.append("deploy_fast"),
        )
        window: Any = SimpleNamespace(
            _redeploy_timer=_Timer(),
            _current_instance_path=Path("/tmp/instance"),
            _bg3_installer=None,
            _game_panel=panel,
            _sync_separator_deploy_paths=lambda: None,
            statusBar=lambda: _StatusBar(),
        )

        self.assertIs(MainWindow._do_redeploy(window), True)
        self.assertEqual(calls, ["purge"])

    def test_auto_redeploy_skips_purge_when_nothing_deployed(self) -> None:
        """No manifest, nothing to clean — and no warning popup either."""
        calls: list[str] = []
        panel = SimpleNamespace(
            has_deployment=lambda: False,
            silent_purge=lambda: calls.append("purge"),
        )
        window: Any = SimpleNamespace(
            _redeploy_timer=_Timer(),
            _current_instance_path=Path("/tmp/instance"),
            _bg3_installer=None,
            _game_panel=panel,
            _sync_separator_deploy_paths=lambda: None,
            statusBar=lambda: _StatusBar(),
        )

        with mock.patch("anvil.mainwindow.QMessageBox.warning") as warning:
            self.assertIs(MainWindow._do_redeploy(window), True)
        self.assertEqual(calls, [])
        warning.assert_not_called()


    def test_steam_launch_runs_predeploy_hook(self) -> None:
        """Steam main-binary launches deploy via the hook, not start_requested."""
        app = QApplication.instance() or QApplication([])
        panel = GamePanel()
        panel._game_label.setText("Steam Game")
        panel._executables = [{"name": "Steam Game", "binary": "bin/game.exe"}]
        panel._selected_exe_index = 0
        panel._current_plugin = SimpleNamespace(
            GameSteamId=3489700,
            detectedStore=lambda: "steam",
            GameBinary="bin/game.exe",
            NeedsRedmodDeploy=False,
        )
        hook = mock.Mock(return_value=True)
        panel.set_predeploy_hook(hook)
        panel._do_launch = mock.Mock()

        panel._on_start_clicked()

        hook.assert_called_once_with("game_start")
        panel._do_launch.assert_called_once()
        panel.deleteLater()
        app.processEvents()

    def test_steam_launch_aborts_when_predeploy_fails(self) -> None:
        app = QApplication.instance() or QApplication([])
        panel = GamePanel()
        panel._game_label.setText("Steam Game")
        panel._executables = [{"name": "Steam Game", "binary": "bin/game.exe"}]
        panel._selected_exe_index = 0
        panel._current_plugin = SimpleNamespace(
            GameSteamId=3489700,
            detectedStore=lambda: "steam",
            GameBinary="bin/game.exe",
            NeedsRedmodDeploy=False,
        )
        panel.set_predeploy_hook(mock.Mock(return_value=False))
        panel._do_launch = mock.Mock()

        with mock.patch(
            "anvil.widgets.game_panel.QMessageBox.warning"
        ) as warning:
            panel._on_start_clicked()

        panel._do_launch.assert_not_called()
        warning.assert_called_once()
        panel.deleteLater()
        app.processEvents()

    def test_non_steam_launch_skips_predeploy_hook(self) -> None:
        """GOG/Epic starts go through start_requested, which deploys already."""
        app = QApplication.instance() or QApplication([])
        panel = GamePanel()
        panel._game_label.setText("GOG Game")
        panel._executables = [{"name": "GOG Game", "binary": "bin/game.exe"}]
        panel._selected_exe_index = 0
        panel._current_plugin = SimpleNamespace(
            GameSteamId=0,
            detectedStore=lambda: "gog",
            GameBinary="bin/game.exe",
            NeedsRedmodDeploy=False,
        )
        hook = mock.Mock(return_value=True)
        panel.set_predeploy_hook(hook)
        panel._do_launch = mock.Mock()

        panel._on_start_clicked()

        hook.assert_not_called()
        panel._do_launch.assert_called_once()
        panel.deleteLater()
        app.processEvents()

    def test_forge_branch_deploys_without_predeploy_hook(self) -> None:
        """GRB keeps its own deploy branch and never touches the hook."""
        app = QApplication.instance() or QApplication([])
        panel = GamePanel()
        panel._game_label.setText("GRB")
        panel._executables = [{"name": "GRB", "binary": "grb.exe"}]
        panel._selected_exe_index = 0
        panel._current_plugin = SimpleNamespace(
            GameSteamId=123,
            detectedStore=lambda: "steam",
            GameBinary="grb.exe",
            NeedsRedmodDeploy=False,
            RequiresForgeDeployment=True,
        )
        hook = mock.Mock(return_value=True)
        panel.set_predeploy_hook(hook)
        panel.silent_deploy = mock.Mock(
            return_value=SimpleNamespace(success=True, errors=[])
        )
        panel._do_launch = mock.Mock()

        panel._on_start_clicked()

        hook.assert_not_called()
        panel.silent_deploy.assert_called_once()
        panel._do_launch.assert_called_once()
        panel.deleteLater()
        app.processEvents()

    def test_steam_launch_without_hook_still_launches(self) -> None:
        """No hook connected (e.g. tests, tools) must not block the launch."""
        app = QApplication.instance() or QApplication([])
        panel = GamePanel()
        panel._game_label.setText("Steam Game")
        panel._executables = [{"name": "Steam Game", "binary": "bin/game.exe"}]
        panel._selected_exe_index = 0
        panel._current_plugin = SimpleNamespace(
            GameSteamId=3489700,
            detectedStore=lambda: "steam",
            GameBinary="bin/game.exe",
            NeedsRedmodDeploy=False,
        )
        panel._do_launch = mock.Mock()

        panel._on_start_clicked()

        panel._do_launch.assert_called_once()
        panel.deleteLater()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
