"""``steam -applaunch`` needs a client to forward the command to.

With Steam closed the command is accepted and then goes nowhere, so the
launch has to check first and offer to bring Steam up.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock

from anvil.stores import steam_utils
from anvil.widgets.game_panel import GamePanel


class SteamRunningTests(TestCase):
    def test_a_live_steam_process_is_detected(self) -> None:
        with mock.patch.object(steam_utils, "_read_steam_pid", return_value=4711), \
             mock.patch.object(steam_utils, "_pid_is_steam", return_value=True):
            self.assertTrue(steam_utils.is_steam_running())

    def test_no_pid_file_means_no_steam(self) -> None:
        with mock.patch.object(steam_utils, "_STEAM_PID_FILES",
                               [Path("/nonexistent/steam.pid")]):
            self.assertFalse(steam_utils.is_steam_running())

    def test_a_stale_pid_file_does_not_count_as_running(self) -> None:
        # Steam leaves its pid file behind; by the time it is read the number
        # may belong to something else entirely.
        with mock.patch.object(steam_utils, "_read_steam_pid", return_value=1), \
             mock.patch.object(steam_utils, "_pid_is_steam", return_value=False):
            self.assertFalse(steam_utils.is_steam_running())

    def test_a_garbage_pid_file_is_ignored(self) -> None:
        with mock.patch.object(Path, "read_text", return_value="not-a-number"):
            self.assertIsNone(steam_utils._read_steam_pid())


class EnsureSteamRunningTests(TestCase):
    """The dialog in front of the launch — which button leads where."""

    def _panel(self) -> SimpleNamespace:
        return SimpleNamespace()

    def test_a_running_steam_asks_nothing(self) -> None:
        with mock.patch("anvil.stores.steam_utils.is_steam_running",
                        return_value=True), \
             mock.patch("anvil.widgets.game_panel.QMessageBox") as box:
            result = GamePanel._ensure_steam_running(self._panel(), "/usr/bin/steam")

        self.assertTrue(result)
        box.assert_not_called()

    def _click(self, which: str, popen):
        """Run the dialog and let the user press *which* button."""
        buttons: dict[str, object] = {}

        class FakeBox:
            def __init__(self, _parent):
                self._clicked = None

            def setIcon(self, _icon): pass

            def setWindowTitle(self, _title): pass

            def setText(self, _text): pass

            def addButton(self, label, _role):
                button = object()
                buttons[label] = button
                return button

            def exec(self):
                self._clicked = buttons[which]

            def clickedButton(self):
                return self._clicked

        fake = mock.MagicMock()
        fake.side_effect = lambda parent: FakeBox(parent)
        fake.Icon = mock.MagicMock()
        fake.ButtonRole = mock.MagicMock()

        with mock.patch("anvil.stores.steam_utils.is_steam_running",
                        return_value=False), \
             mock.patch("anvil.widgets.game_panel.QMessageBox", fake), \
             mock.patch("anvil.core.subprocess_env.host_popen", popen), \
             mock.patch("anvil.widgets.game_panel.clean_subprocess_env",
                        return_value={}):
            return GamePanel._ensure_steam_running(self._panel(), "/usr/bin/steam")

    def test_starting_steam_spawns_it_and_continues(self) -> None:
        popen = mock.MagicMock()
        result = self._click("Steam starten", popen)

        self.assertTrue(result)
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0], ["/usr/bin/steam"])

    def test_continue_without_steam_launches_untouched(self) -> None:
        popen = mock.MagicMock()
        result = self._click("Ohne Steam weiter", popen)

        self.assertTrue(result)
        popen.assert_not_called()

    def test_cancel_stops_the_launch(self) -> None:
        popen = mock.MagicMock()
        result = self._click("Abbrechen", popen)

        self.assertFalse(result)
        popen.assert_not_called()

    def test_a_failing_steam_start_stops_the_launch(self) -> None:
        popen = mock.MagicMock(side_effect=OSError("no such file"))
        result = self._click("Steam starten", popen)

        self.assertFalse(result)
