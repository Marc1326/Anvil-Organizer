"""Mods normally leave the game directory the moment the game ends.

With keep-deployed on they stay, so the game runs modded through Steam or
any other launcher while Anvil is closed.  The flag belongs to one instance
and is lifted on a game switch — Anvil watches one game at a time, and mods
left in a directory it no longer manages would go stale unnoticed.
"""
from types import SimpleNamespace
from unittest import TestCase, mock

from anvil.mainwindow import MainWindow


def _window(keep: bool, deployed: bool = True, running: bool = False):
    """A MainWindow stand-in with just the parts the purge paths touch."""
    panel = mock.MagicMock()
    panel.has_deployment.return_value = deployed
    panel.is_game_running.return_value = running
    panel.silent_purge.return_value = SimpleNamespace(success=True, errors=[])
    panel.silent_deploy.return_value = SimpleNamespace(success=True, errors=[])

    window = SimpleNamespace(
        _game_panel=panel,
        _game_running=running,
        _redeploy_timer=mock.MagicMock(),
        _current_instance_path="/tmp/instance",
        _bg3_installer=None,
        _log_game_dir_state=mock.MagicMock(),
        keeps_mods_deployed=lambda: keep,
    )
    return window, panel


class PurgeAfterGameTests(TestCase):
    def test_mods_are_removed_after_the_game_by_default(self) -> None:
        window, panel = _window(keep=False)
        MainWindow._purge_after_game(window)
        panel.silent_purge.assert_called_once()

    def test_keep_deployed_leaves_the_mods_in_place(self) -> None:
        window, panel = _window(keep=True)
        MainWindow._purge_after_game(window)
        panel.silent_purge.assert_not_called()


class PurgeOnCloseTests(TestCase):
    def test_closing_cleans_up_by_default(self) -> None:
        window, panel = _window(keep=False)
        MainWindow._purge_on_close(window)
        panel.silent_purge.assert_called_once()

    def test_keep_deployed_survives_closing(self) -> None:
        window, panel = _window(keep=True, deployed=True)
        MainWindow._purge_on_close(window)
        panel.silent_purge.assert_not_called()
        panel.silent_deploy.assert_not_called()

    def test_closing_deploys_if_nothing_is_out_there_yet(self) -> None:
        # Without this the user closes Anvil, starts through Steam and finds
        # a vanilla game — the whole point of the setting missed.
        window, panel = _window(keep=True, deployed=False)
        MainWindow._purge_on_close(window)
        panel.silent_deploy.assert_called_once()

    def test_a_running_game_is_never_touched(self) -> None:
        window, panel = _window(keep=False, running=True)
        MainWindow._purge_on_close(window)
        panel.silent_purge.assert_not_called()


class RedeployTests(TestCase):
    def test_a_mod_change_only_cleans_up_by_default(self) -> None:
        window, panel = _window(keep=False)
        MainWindow._do_redeploy(window)
        panel.silent_purge.assert_called_once()
        panel.silent_deploy.assert_not_called()

    def test_keep_deployed_puts_the_changed_list_back_out(self) -> None:
        window, panel = _window(keep=True)
        MainWindow._do_redeploy(window)
        panel.silent_purge.assert_called_once()
        panel.silent_deploy.assert_called_once()

    def test_keep_deployed_deploys_even_with_nothing_deployed_yet(self) -> None:
        window, panel = _window(keep=True, deployed=False)
        MainWindow._do_redeploy(window)
        panel.silent_deploy.assert_called_once()

    def test_a_failed_purge_does_not_deploy_on_top(self) -> None:
        window, panel = _window(keep=True)
        panel.silent_purge.return_value = SimpleNamespace(
            success=False, errors=["nope"])
        with mock.patch("anvil.mainwindow.QMessageBox"):
            MainWindow._do_redeploy(window)
        panel.silent_deploy.assert_not_called()


class LiftOnGameSwitchTests(TestCase):
    def _manager(self, keep: bool):
        manager = mock.MagicMock()
        manager.load_instance.return_value = {
            "keep_mods_deployed": "true" if keep else "false",
            "game_name": "Cyberpunk 2077",
        }
        return manager

    def test_switching_games_lifts_the_flag_and_says_so(self) -> None:
        manager = self._manager(keep=True)
        window = SimpleNamespace(instance_manager=manager)

        with mock.patch("anvil.mainwindow.QTimer") as timer, \
             mock.patch("anvil.mainwindow.QMessageBox"):
            MainWindow._lift_keep_deployed(window, "Cyberpunk 2077")

        saved = manager.save_instance.call_args.args[1]
        self.assertFalse(saved["keep_mods_deployed"])
        timer.singleShot.assert_called_once()

    def test_an_instance_without_the_flag_says_nothing(self) -> None:
        manager = self._manager(keep=False)
        window = SimpleNamespace(instance_manager=manager)

        with mock.patch("anvil.mainwindow.QTimer") as timer:
            MainWindow._lift_keep_deployed(window, "Cyberpunk 2077")

        manager.save_instance.assert_not_called()
        timer.singleShot.assert_not_called()


class FlagStorageTests(TestCase):
    def _window(self, stored):
        manager = mock.MagicMock()
        manager.current_instance.return_value = "Cyberpunk 2077"
        manager.load_instance.return_value = stored
        return SimpleNamespace(instance_manager=manager), manager

    def test_the_flag_is_off_unless_stored(self) -> None:
        window, _ = self._window({})
        self.assertFalse(MainWindow.keeps_mods_deployed(window))

    def test_a_stored_true_is_read_back(self) -> None:
        window, _ = self._window({"keep_mods_deployed": "true"})
        self.assertTrue(MainWindow.keeps_mods_deployed(window))

    def test_no_instance_means_off(self) -> None:
        window, manager = self._window({})
        manager.current_instance.return_value = None
        self.assertFalse(MainWindow.keeps_mods_deployed(window))

    def test_the_flag_is_written_to_the_instance(self) -> None:
        window, manager = self._window({"game_name": "Cyberpunk 2077"})
        MainWindow.set_keeps_mods_deployed(window, True)
        saved = manager.save_instance.call_args.args[1]
        self.assertTrue(saved["keep_mods_deployed"])


class SettingsSwitchTests(TestCase):
    """What happens right after the switch is flipped in the settings."""

    def _window(self, keeping: bool, deployed: bool = False):
        panel = mock.MagicMock()
        panel.has_deployment.return_value = deployed
        panel.is_game_running.return_value = False
        window = SimpleNamespace(
            _game_panel=panel,
            _game_running=False,
            keeps_mods_deployed=lambda: keeping,
            set_keeps_mods_deployed=mock.MagicMock(),
        )
        return window, panel

    def test_switching_on_deploys_after_the_warning_is_accepted(self) -> None:
        window, panel = self._window(keeping=True)
        with mock.patch("anvil.mainwindow.QMessageBox") as box:
            box.warning.return_value = box.StandardButton.Ok
            MainWindow._apply_keep_deployed_change(window, False)
        panel.silent_deploy.assert_called_once()

    def test_declining_the_warning_switches_the_flag_back_off(self) -> None:
        window, panel = self._window(keeping=True)
        with mock.patch("anvil.mainwindow.QMessageBox") as box:
            box.warning.return_value = box.StandardButton.Cancel
            MainWindow._apply_keep_deployed_change(window, False)
        window.set_keeps_mods_deployed.assert_called_once_with(False)
        panel.silent_deploy.assert_not_called()

    def test_switching_off_cleans_the_game_directory(self) -> None:
        window, panel = self._window(keeping=False)
        MainWindow._apply_keep_deployed_change(window, True)
        panel.silent_purge.assert_called_once()

    def test_an_unchanged_switch_does_nothing(self) -> None:
        window, panel = self._window(keeping=True)
        MainWindow._apply_keep_deployed_change(window, True)
        panel.silent_purge.assert_not_called()
        panel.silent_deploy.assert_not_called()


class SettingsSwitchLookTests(TestCase):
    """The switch has to look like every other one, not like a stray checkbox."""

    def test_the_switch_goes_through_the_same_row_helper(self) -> None:
        from PySide6.QtWidgets import QApplication, QCheckBox

        from anvil.widgets.settings_dialog import SettingsDialog

        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)

        dialog = SettingsDialog.__new__(SettingsDialog)
        dialog._modern = True
        row = SettingsDialog._setting_row(dialog, QCheckBox("Test"))

        # #settingRow QCheckBox::indicator is what turns the box into the
        # slide switch — without the object name it stays a plain checkbox.
        self.assertEqual(row.objectName(), "settingRow")
