"""Tests for blocking game launch when pre-deployment fails."""

from __future__ import annotations

import time
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


def _bind_unlock_helpers(window: Any) -> Any:
    """Wire the real MainWindow helpers _unlock_ui delegates to."""
    window._purge_after_game = lambda: MainWindow._purge_after_game(window)
    window._release_ui_lock = lambda: MainWindow._release_ui_lock(window)
    if not hasattr(window, "uses_overlay"):
        window.uses_overlay = lambda: False
    window._unlock_pending = False
    panel = window._game_panel
    if not hasattr(panel, "clear_watch_target"):
        panel.clear_watch_target = lambda: None
    return window


class PredeployLaunchTests(unittest.TestCase):
    def test_failed_deploy_returns_false_to_block_launch(self) -> None:
        timer = _Timer()
        panel = SimpleNamespace(
            game_state=lambda: "stopped",
            take_forced_launch=lambda: False,
            silent_purge=lambda: SimpleNamespace(success=True, errors=[]),
            silent_deploy=lambda: SimpleNamespace(
                success=False, errors=["injected deploy failure"]
            ),
        )
        window: Any = SimpleNamespace(
            _redeploy_timer=timer,
            _game_running=False,
            _current_instance_path=Path("/tmp/instance"),
            _auto_relock_instance=lambda _path, _reason: None,
            _game_panel=panel,
            _sync_separator_deploy_paths=lambda: None,
            _sync_keep_file_name_mods=lambda: None,
            _log_game_dir_state=lambda _phase: None,
            keeps_mods_deployed=lambda: False,
            uses_overlay=lambda: False,
        )

        success = MainWindow._predeploy_for_launch(window, "game_start")

        self.assertIs(success, False)
        self.assertTrue(timer.stopped)

    def test_direct_launch_stops_when_predeploy_fails(self) -> None:
        window: Any = SimpleNamespace(
            _predeploy_for_launch=lambda _reason: False,
            _last_deploy_errors=["injected deploy failure"],
        )
        window._report_predeploy_failure = (
            lambda result: MainWindow._report_predeploy_failure(window, result)
        )

        with mock.patch("anvil.mainwindow.host_popen") as popen, mock.patch(
            "anvil.mainwindow.QMessageBox.warning"
        ) as warning:
            MainWindow._on_start_game(window, "/game/GRB.exe", "/game")

        popen.assert_not_called()
        warning.assert_called_once()

    def test_custom_tool_stops_when_predeploy_fails(self) -> None:
        panel = SimpleNamespace(
            run_with_proton=mock.Mock(),
            confirm_start_while_running=lambda: True,
        )
        window: Any = SimpleNamespace(
            _predeploy_for_launch=lambda _reason: False,
            _last_deploy_errors=[],
            _report_predeploy_failure=lambda _result: None,
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
        panel = SimpleNamespace(
            run_with_proton=mock.Mock(),
            confirm_start_while_running=lambda: True,
        )
        window: Any = SimpleNamespace(
            _current_instance_path=Path("/tmp/instance"),
            _predeploy_for_launch=predeploy,
            _last_deploy_errors=[],
            _report_predeploy_failure=lambda _result: None,
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
                _last_deploy_errors=[],
                _report_predeploy_failure=lambda _result: None,
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
                _last_deploy_errors=[],
                _report_predeploy_failure=lambda _result: None,
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
            is_game_running=lambda: False,
            silent_purge=lambda: SimpleNamespace(
                success=False, errors=["injected purge failure"]
            ),
        )
        window: Any = SimpleNamespace(
            _redeploy_timer=timer,
            _current_instance_path=Path("/tmp/instance"),
            _bg3_installer=None,
            keeps_mods_deployed=lambda: False,
            uses_overlay=lambda: False,
            _game_running=False,
            _game_panel=panel,
            _sync_separator_deploy_paths=lambda: None,
            _sync_keep_file_name_mods=lambda: None,
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
            game_state=lambda: "running",
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
            keeps_mods_deployed=lambda: False,
            uses_overlay=lambda: False,
        )

        MainWindow._unlock_ui(_bind_unlock_helpers(window))

        self.assertEqual(calls, [])
        self.assertIs(window._game_running, False)

    def test_unlock_cleans_up_once_the_game_is_gone(self) -> None:
        calls: list[str] = []
        panel = SimpleNamespace(
            is_game_running=lambda: False,
            game_state=lambda: "stopped",
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
            keeps_mods_deployed=lambda: False,
            uses_overlay=lambda: False,
        )

        MainWindow._unlock_ui(_bind_unlock_helpers(window))

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
        panel_state._game_state = None
        panel_state._current_plugin = None
        panel_state._watch_generation = 0
        panel_state._search_terms = lambda: GamePanel._search_terms(panel_state)
        panel_state.lookup_game_pid = lambda: GamePanel.lookup_game_pid(panel_state)
        panel_state.game_state = lambda: GamePanel.game_state(panel_state)
        panel_state._note_game_state = (
            lambda pid, ok, ttl=15: GamePanel._note_game_state(
                panel_state, pid, ok, ttl
            )
        )
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
                keeps_mods_deployed=lambda: False,
            )

            MainWindow._unlock_ui(_bind_unlock_helpers(window))
            self.assertEqual(purges, [], "must not purge while the game runs")
        finally:
            stand_in.terminate()
            stand_in.wait()

        deadline = time.monotonic() + 10
        while running() and time.monotonic() < deadline:
            time.sleep(0.2)
        self.assertFalse(running(), "process gone, but still reported as running")

        MainWindow._unlock_ui(_bind_unlock_helpers(window))
        self.assertEqual(purges, ["purge"], "should clean up once the game is gone")

    def test_auto_redeploy_never_deploys(self) -> None:
        """Toggling a mod must not put anything into the game directory."""
        calls: list[str] = []
        panel = SimpleNamespace(
            has_deployment=lambda: True,
            is_game_running=lambda: False,
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
            keeps_mods_deployed=lambda: False,
            uses_overlay=lambda: False,
            _game_running=False,
            _game_panel=panel,
            _sync_separator_deploy_paths=lambda: None,
            _sync_keep_file_name_mods=lambda: None,
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
            keeps_mods_deployed=lambda: False,
            uses_overlay=lambda: False,
            _game_running=False,
            _game_panel=panel,
            _sync_separator_deploy_paths=lambda: None,
            _sync_keep_file_name_mods=lambda: None,
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


class SandboxedProcessLookupTests(unittest.TestCase):
    """A blind process lookup must not be read as "the game has stopped"."""

    def _window(self, purges: list[str], running: bool) -> Any:
        return SimpleNamespace(
            _game_panel=SimpleNamespace(
                is_game_running=lambda: running,
                silent_purge=lambda: (
                    purges.append("purge"),
                    SimpleNamespace(success=True, errors=[]),
                )[1],
            ),
            _game_running=True,
            _lock_overlay=_Widget(),
            _splitter=_Widget(),
            _log_container=_Widget(),
            _toolbar=_Widget(),
            menuBar=lambda: _Widget(),
            _log_game_dir_state=lambda _phase: None,
            keeps_mods_deployed=lambda: False,
            uses_overlay=lambda: False,
        )

    def test_unknown_state_keeps_the_deployment(self) -> None:
        purges: list[str] = []
        window = self._window(purges, running=False)

        MainWindow._unlock_ui(_bind_unlock_helpers(window), False)

        self.assertEqual(purges, [], "unknown state must not trigger a purge")
        self.assertIs(window._game_running, False, "the UI still has to unlock")

    @staticmethod
    def _panel(binary: str, app_id: str | None, lookup) -> Any:
        panel: Any = SimpleNamespace(
            _watch_binary=binary, _watch_app_id=app_id, _game_state=None,
            _current_plugin=None, _watch_generation=0,
        )
        panel._search_terms = lambda: GamePanel._search_terms(panel)
        panel.lookup_game_pid = lookup or (
            lambda: GamePanel.lookup_game_pid(panel)
        )
        panel._note_game_state = (
            lambda pid, ok, ttl=15: GamePanel._note_game_state(panel, pid, ok, ttl)
        )
        panel.game_state = lambda: GamePanel.game_state(panel)
        return panel

    def test_failed_lookup_reports_the_game_as_running(self) -> None:
        panel = self._panel("game.exe", "1091500", lambda: (None, False))

        self.assertEqual(panel.game_state(), "unknown")
        self.assertTrue(
            GamePanel.is_game_running(panel),
            "a failed lookup must not clear the way for a purge",
        )

    def test_nothing_launched_is_not_running(self) -> None:
        panel = self._panel("", None, None)

        self.assertEqual(panel.lookup_game_pid(), (None, True))
        self.assertEqual(panel.game_state(), "stopped")
        self.assertFalse(GamePanel.is_game_running(panel))

    def test_lookup_without_target_is_reliable(self) -> None:
        """"Nothing to look for" is an answer, not a failed lookup."""
        from anvil.core.game_process import find_game_process

        self.assertEqual(find_game_process(None, None), (None, True))

    @staticmethod
    def _run_host_snippet(binary: str) -> str:
        import subprocess
        import sys
        from anvil.core.game_process import _HOST_SCAN

        result = subprocess.run(
            [sys.executable, "-c", _HOST_SCAN],
            input=f"\n{binary}\n",
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def test_host_scan_snippet_matches_the_local_scan(self) -> None:
        """The host snippet is a copy — it has to find the same process."""
        import subprocess
        import sys
        import time
        from anvil.core.game_process import scan_proc_for_game

        binary = "".join(["host", "scan", "probe", "77", ".exe"])
        stand_in = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)", "/game/" + binary]
        )
        try:
            deadline = time.monotonic() + 10
            local = None
            while local is None and time.monotonic() < deadline:
                local = scan_proc_for_game(None, binary)
                if local is None:
                    time.sleep(0.2)
            self.assertEqual(local, stand_in.pid)
            self.assertEqual(self._run_host_snippet(binary), str(stand_in.pid))
        finally:
            stand_in.terminate()
            stand_in.wait()

    def test_unlock_only_frees_the_ui(self) -> None:
        """Entsperren raeumt nichts mehr auf.

        Frueher fragte der Knopf, ob die Mods entfernt werden sollen --
        und "Ja" las sich wie "ja, entsperren". Wer nur nachschauen
        wollte, riss dem laufenden Spiel die Dateien weg.
        """
        purges: list[str] = []
        window = self._window(purges, running=True)
        window._game_panel.has_deployment = lambda: True
        _bind_unlock_helpers(window)

        with mock.patch("anvil.mainwindow.QMessageBox") as box:
            MainWindow._on_unlock_clicked(window)

        self.assertEqual(purges, [], "the deployment has to stay")
        box.question.assert_not_called()

    def test_unlock_keeps_the_game_marked_as_running(self) -> None:
        """Sonst schlaegt jede spaetere Aenderung in den Spielordner durch."""
        purges: list[str] = []
        window = self._window(purges, running=True)
        window._game_panel.has_deployment = lambda: True
        vergessen: list[str] = []
        window._game_panel.clear_watch_target = lambda: vergessen.append("x")
        _bind_unlock_helpers(window)

        MainWindow._on_unlock_clicked(window)

        self.assertIs(window._game_running, True)
        self.assertEqual(vergessen, [], "the watcher has to keep running")

    def test_running_game_blocks_a_second_launch(self) -> None:
        """Pre-launch purge would rip the files from the running game."""
        calls: list[str] = []
        window: Any = SimpleNamespace(
            _redeploy_timer=_Timer(),
            _current_instance_path=Path("/tmp/instance"),
            _game_running=False,
            _game_panel=SimpleNamespace(
                game_state=lambda: "running",
                take_forced_launch=lambda: False,
                silent_purge=lambda: calls.append("purge"),
                silent_deploy=lambda: calls.append("deploy"),
            ),
            _auto_relock_instance=lambda _p, _r: None,
            _sync_separator_deploy_paths=lambda: None,
            _sync_keep_file_name_mods=lambda: None,
            _log_game_dir_state=lambda _phase: None,
            keeps_mods_deployed=lambda: False,
            uses_overlay=lambda: False,
        )

        with mock.patch("anvil.mainwindow.QMessageBox.warning") as warning:
            success = MainWindow._predeploy_for_launch(window, "game_start")

        self.assertIsNone(success, "None = Grund wurde bereits gemeldet")
        self.assertEqual(calls, [])
        warning.assert_called_once()

    def test_redeploy_keeps_files_while_the_game_may_run(self) -> None:
        """The 500 ms debounce purge is reachable once the UI is unlocked."""
        calls: list[str] = []
        window: Any = SimpleNamespace(
            _redeploy_timer=_Timer(),
            _current_instance_path=Path("/tmp/instance"),
            _bg3_installer=None,
            keeps_mods_deployed=lambda: False,
            uses_overlay=lambda: False,
            _game_running=False,
            _game_panel=SimpleNamespace(
                has_deployment=lambda: True,
                is_game_running=lambda: True,
                silent_purge=lambda: calls.append("purge"),
            ),
            _sync_separator_deploy_paths=lambda: None,
            _sync_keep_file_name_mods=lambda: None,
            statusBar=lambda: _StatusBar(),
        )

        self.assertIs(MainWindow._do_redeploy(window), True)
        self.assertEqual(calls, [])

    def test_watcher_gives_up_only_after_the_grace_period(self) -> None:
        """One failed host call is noise — the game is not gone."""
        panel = self._panel("game.exe", "1091500", lambda: (None, False))
        panel._GAME_LOOKUP_GRACE = GamePanel._GAME_LOOKUP_GRACE

        self.assertEqual(panel.game_state(), "unknown")
        self.assertTrue(GamePanel.is_game_running(panel))

    def test_confirmed_stop_forgets_the_target(self) -> None:
        """Otherwise nothing is ever cleaned up again in this session."""
        panel = self._panel("game.exe", "1091500", lambda: (None, True))

        GamePanel.clear_watch_target(panel)

        self.assertEqual(panel.game_state(), "stopped")
        self.assertFalse(GamePanel.is_game_running(panel))

    def test_appear_timeout_leaves_the_target_in_place(self) -> None:
        """A slow start must stay findable by MainWindow's re-check."""
        app = QApplication.instance() or QApplication([])
        panel = GamePanel()
        panel._GAME_APPEAR_TIMEOUT = 0  # sofort in den Timeout laufen
        seen: list[bool] = []
        panel.game_stopped.connect(seen.append)
        panel._start_process_watcher("slowgame.exe", app_id="4242")

        deadline = time.monotonic() + 10
        while not seen and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.05)

        self.assertEqual(
            seen, [False],
            "a slow start is no proof the game is gone — do not purge",
        )
        self.assertEqual(
            panel._watch_binary, "slowgame.exe",
            "the target must survive so is_game_running() stays meaningful",
        )
        panel.deleteLater()
        app.processEvents()

    def test_an_old_watcher_does_not_report_for_a_new_launch(self) -> None:
        """Otherwise the stale thread purges the freshly started game."""
        app = QApplication.instance() or QApplication([])
        panel = GamePanel()
        panel._GAME_APPEAR_TIMEOUT = 0
        seen: list[bool] = []

        panel.game_stopped.connect(seen.append)
        panel._start_process_watcher("firstgame.exe", app_id="1111")
        panel._start_process_watcher("secondgame.exe", app_id="2222")

        deadline = time.monotonic() + 10
        while len(seen) < 1 and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.05)
        time.sleep(0.5)
        app.processEvents()

        self.assertEqual(len(seen), 1, "only the current watcher may report")
        self.assertEqual(panel._watch_binary, "secondgame.exe")
        panel.deleteLater()
        app.processEvents()

    def test_declining_the_start_launches_nothing(self) -> None:
        """Every start path runs the pre-launch purge, so ask first."""
        launched: list[tuple] = []
        panel: Any = SimpleNamespace(
            _selected_exe_index=0,
            _executables=[{"binary": "CP.exe"}],
            _current_plugin=None,
            _forced_launch=False,
            _predeploy_hook=lambda _r: True,
            game_state=lambda: "running",
            silent_deploy=lambda: launched.append(("deploy",)),
            _needs_redmod_deploy=lambda _p: False,
            _do_launch=lambda *a: launched.append(a),
        )
        panel.confirm_start_while_running = (
            lambda: GamePanel.confirm_start_while_running(panel)
        )

        with mock.patch(
            "anvil.widgets.game_panel.QMessageBox.question",
            return_value=mock.sentinel.no,
        ), mock.patch(
            "anvil.widgets.game_panel.QMessageBox.StandardButton"
        ) as buttons:
            buttons.Yes = mock.sentinel.yes
            GamePanel._on_start_clicked(panel)

        self.assertEqual(launched, [], "declining must not deploy or launch")

    def test_clearing_the_target_retires_the_running_watcher(self) -> None:
        """A watcher left running reads the empty target as "game gone"."""
        panel = self._panel("game.exe", "1091500", lambda: (None, True))
        panel._watch_generation = 7
        panel.clear_watch_target = lambda: GamePanel.clear_watch_target(panel)

        panel.clear_watch_target()

        self.assertEqual(
            panel._watch_generation, 8,
            "the old watcher has to be retired, or it reports a false stop",
        )

    def test_state_falls_back_to_the_current_game(self) -> None:
        """Without a watch target, fall back to the current game."""
        plugin = SimpleNamespace(GameSteamId=1091500, GameBinary="bin/x64/CP.exe")
        panel: Any = SimpleNamespace(
            _watch_binary="", _watch_app_id=None, _game_state=None,
            _current_plugin=plugin, _watch_generation=0,
        )
        panel._search_terms = lambda: GamePanel._search_terms(panel)

        self.assertEqual(panel._search_terms(), ("1091500", "cp.exe"))

        panel.lookup_game_pid = lambda: (4711, True)
        panel._note_game_state = (
            lambda pid, ok, ttl=15: GamePanel._note_game_state(panel, pid, ok, ttl)
        )
        panel.game_state = lambda: GamePanel.game_state(panel)

        self.assertEqual(panel.game_state(), "running")
        self.assertTrue(GamePanel.is_game_running(panel))

    def test_crash_recovery_keeps_files_while_the_game_runs(self) -> None:
        """Anvil restarting must not purge under a game from the old session."""
        purges: list[str] = []

        class _Deployer:
            MANIFEST_NAME = "manifest.json"

            def __init__(self, *a, **kw) -> None:
                pass

            def purge(self):
                purges.append("purge")

            def remove_orphaned_links(self):
                purges.append("orphans")
                return 0

        plugin = SimpleNamespace(GameSteamId=1091500, GameBinary="bin/CP.exe")
        window: Any = SimpleNamespace(
            instance_manager=SimpleNamespace(
                list_instances=lambda: [{"name": "CP"}],
                instances_path=lambda: Path("/tmp/instances"),
                load_instance=lambda _n: {
                    "game_path": "/tmp", "game_short_name": "cp2077",
                },
            ),
            plugin_loader=SimpleNamespace(get_game=lambda _s: plugin),
        )

        with mock.patch("anvil.core.mod_deployer.ModDeployer", _Deployer), \
                mock.patch(
                    "anvil.core.game_process.find_game_process",
                    return_value=(1234, True),
                ):
            MainWindow._crash_recovery_purge(window)

        self.assertEqual(purges, [], "nothing may be removed while it runs")

    def test_own_tools_are_not_mistaken_for_the_game(self) -> None:
        """Anvil starts xEdit and redMod.exe with the game's SteamAppId.

        Without the marker every running tool answered "the game is up".
        """
        import os
        import subprocess
        import sys
        from anvil.core.game_process import scan_proc_for_game, TOOL_ENV_MARKER

        app_id = "".join(["99", "1147"])
        tool = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            env=dict(os.environ, SteamAppId=app_id, **{TOOL_ENV_MARKER: "1"}),
        )
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if scan_proc_for_game(app_id, None) is not None:
                    self.fail("a marked tool must not count as the game")
                time.sleep(0.2)
        finally:
            tool.terminate()
            tool.wait()

        game = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            env=dict(os.environ, SteamAppId=app_id),
        )
        try:
            deadline, found = time.monotonic() + 5, None
            while found is None and time.monotonic() < deadline:
                found = scan_proc_for_game(app_id, None)
                if found is None:
                    time.sleep(0.2)
            self.assertEqual(found, game.pid, "the real game must still be found")
        finally:
            game.terminate()
            game.wait()

    def test_blind_lookup_never_reports_stopped(self) -> None:
        """The one answer that leads to deletion must be earned."""
        from anvil.widgets.game_panel import _state_of

        self.assertEqual(_state_of(None, False), "unknown")
        self.assertEqual(_state_of(None, True), "stopped")
        self.assertEqual(_state_of(4711, False), "running")

    def test_stopped_is_never_answered_from_the_cache(self) -> None:
        """A stale "stopped" would authorise a purge on old information."""
        panel = self._panel("game.exe", "1091500", lambda: (99, True))
        panel._game_state = (time.monotonic() + 60, "stopped")

        self.assertEqual(
            panel.game_state(), "running", "stale STOPPED must be re-measured"
        )

    def test_closing_keeps_files_while_the_game_runs(self) -> None:
        calls: list[str] = []
        window: Any = SimpleNamespace(
            _redeploy_timer=_Timer(),
            _game_running=False,
            _game_panel=SimpleNamespace(
                is_game_running=lambda: True,
                silent_purge=lambda: calls.append("purge"),
            ),
            _save_ui_state=lambda: None,
        )

        MainWindow._purge_on_close(window)

        self.assertEqual(calls, [], "closing must not purge under a running game")

    def test_start_is_refused_while_the_ui_reports_a_game(self) -> None:
        """`_game_running` is the only signal the shortcut path has."""
        calls: list[str] = []
        window: Any = SimpleNamespace(
            _redeploy_timer=_Timer(),
            _game_running=True,
            _current_instance_path=Path("/tmp/instance"),
            _game_panel=SimpleNamespace(
                game_state=lambda: "stopped",
                take_forced_launch=lambda: False,
                silent_purge=lambda: calls.append("purge"),
                silent_deploy=lambda: calls.append("deploy"),
            ),
            _auto_relock_instance=lambda _p, _r: None,
            _sync_separator_deploy_paths=lambda: None,
            _sync_keep_file_name_mods=lambda: None,
            _log_game_dir_state=lambda _phase: None,
            keeps_mods_deployed=lambda: False,
            uses_overlay=lambda: False,
        )

        with mock.patch("anvil.mainwindow.QMessageBox.warning"):
            result = MainWindow._predeploy_for_launch(window, "game_start")

        self.assertIsNone(result)
        self.assertEqual(calls, [])

    def test_game_stopped_cleans_up_as_before(self) -> None:
        """Endet das Spiel wirklich, wird weiterhin aufgeraeumt."""
        calls: list[str] = []
        window: Any = SimpleNamespace(
            _game_running=True,
            _game_panel=SimpleNamespace(
                is_game_running=lambda: False,
                silent_purge=lambda: calls.append("purge"),
                clear_watch_target=lambda: calls.append("forget"),
            ),
            _log_game_dir_state=lambda _phase: None,
            keeps_mods_deployed=lambda: False,
            uses_overlay=lambda: False,
            _purge_after_game=lambda: calls.append("purge"),
            _release_ui_lock=lambda: None,
        )

        MainWindow._unlock_ui(window, True)

        self.assertIn("purge", calls)
        self.assertIs(window._game_running, False)

    def test_appid_match_stops_at_the_value_boundary(self) -> None:
        """A short SteamAppId must not match a longer one starting with it."""
        import os
        import subprocess
        import sys
        from anvil.core.game_process import scan_proc_for_game

        # A made-up id: a real one would make the second assertion claim
        # that game is not running, and the test breaks once someone plays
        # it.  The pid keeps two concurrent test runs apart.
        short = f"99{os.getpid()}"
        longer = short + "0"
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            env=dict(os.environ, SteamAppId=longer),
        )
        try:
            deadline, found = time.monotonic() + 5, None
            while found is None and time.monotonic() < deadline:
                found = scan_proc_for_game(longer, None)
                if found is None:
                    time.sleep(0.2)
            self.assertEqual(found, proc.pid)
            self.assertIsNone(
                scan_proc_for_game(short, None), "prefix must not match"
            )
        finally:
            proc.terminate()
            proc.wait()

    def test_proton_launch_watches_the_app_id_too(self) -> None:
        """A GameBinary that is only a launcher never matches the real process."""
        panel: Any = SimpleNamespace(
            _current_game_path=Path("/tmp"),
            _game_label=SimpleNamespace(text=lambda: "Game"),
            game_started=SimpleNamespace(emit=lambda *a: None),
        )
        plugin = SimpleNamespace(
            GameSteamId=1091500, GameBinary="bin/x64/Real-Shipping.exe"
        )
        watched: list[tuple] = []
        panel._start_process_watcher = (
            lambda binary, proc=None, app_id=None: watched.append((binary, app_id))
        )
        panel._build_proton_env = lambda _p: (
            {}, Path("/tmp/proton"), Path("/tmp/compat"), Path("/tmp/steam")
        )

        with mock.patch("pathlib.Path.exists", return_value=True), \
                mock.patch(
                    "anvil.core.subprocess_env.host_popen",
                    return_value=SimpleNamespace(pid=1),
                ):
            GamePanel._launch_via_proton(panel, plugin, "launcher.exe")

        self.assertEqual(watched, [("real-shipping.exe", "1091500")])

    def test_deleting_mods_is_refused_while_the_game_runs(self) -> None:
        """Removing a mod folder leaves dead links in the game directory."""
        window: Any = SimpleNamespace(
            _game_running=False,
            _game_panel=SimpleNamespace(is_game_running=lambda: True),
        )

        with mock.patch("anvil.mainwindow.QMessageBox.warning") as warning:
            refused = MainWindow._refuse_while_game_runs(window, "Title")

        self.assertTrue(refused)
        warning.assert_called_once()

    def test_switching_games_drops_the_remembered_state(self) -> None:
        """Otherwise the new game inherits the old one's "running"."""
        app = QApplication.instance() or QApplication([])
        panel = GamePanel()
        panel._game_state = (time.monotonic() + 60, "running")

        panel.update_game("Other Game", None)

        self.assertIsNone(panel._game_state)
        panel.deleteLater()
        app.processEvents()

    def test_unknown_state_asks_before_starting(self) -> None:
        """A broken lookup must not wave the pre-launch purge through."""
        panel: Any = SimpleNamespace(_forced_launch=None)
        panel.game_state = lambda: "unknown"
        panel.confirm_start_while_running = (
            lambda: GamePanel.confirm_start_while_running(panel)
        )

        with mock.patch(
            "anvil.widgets.game_panel.QMessageBox.question",
            return_value=mock.sentinel.no,
        ) as question, mock.patch(
            "anvil.widgets.game_panel.QMessageBox.StandardButton"
        ) as buttons:
            buttons.Yes = mock.sentinel.yes
            allowed = panel.confirm_start_while_running()

        self.assertFalse(allowed)
        question.assert_called_once()

    def test_forced_launch_expires(self) -> None:
        """A branch that never reads the flag must not disarm the guards."""
        panel: Any = SimpleNamespace(_forced_launch=time.monotonic() - 1)

        self.assertFalse(
            GamePanel.take_forced_launch(panel), "stale consent must not count"
        )

        panel._forced_launch = time.monotonic() + 60
        self.assertTrue(GamePanel.take_forced_launch(panel))
        self.assertFalse(
            GamePanel.take_forced_launch(panel), "reads once, then it is gone"
        )

    def test_scan_does_not_find_itself(self) -> None:
        """The name being searched for must not come back as a hit."""
        from anvil.core.game_process import scan_proc_for_game

        binary = "".join(["no", "such", "process", "31", ".exe"])

        self.assertIsNone(scan_proc_for_game(None, binary))
        self.assertEqual(self._run_host_snippet(binary), "")


if __name__ == "__main__":
    unittest.main()
