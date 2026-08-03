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


if __name__ == "__main__":
    unittest.main()
