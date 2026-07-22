"""Tests for blocking game launch when pre-deployment fails."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

from anvil.mainwindow import MainWindow


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

    def test_auto_redeploy_reports_failure_instead_of_success(self) -> None:
        timer = _Timer()
        status = _StatusBar()
        panel = SimpleNamespace(
            silent_purge=lambda: SimpleNamespace(success=True, errors=[]),
            silent_deploy_fast=lambda: SimpleNamespace(
                success=False, errors=["injected auto-deploy failure"]
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


if __name__ == "__main__":
    unittest.main()
