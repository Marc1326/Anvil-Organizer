"""Issue #103: a missing Proton prefix locked the user out completely.

plugins.txt can only be written once the prefix exists, and the prefix
only appears after the game has been launched once.  A failed write
marked the whole deploy as failed, which in turn refused the launch - so
the one way out was the one thing that was blocked.

The reporter runs Anvil as a flatpak.  ``--filesystem=home`` deliberately
excludes ``~/.var/app``, so a flatpak Steam library is invisible to it and
no prefix is ever found.
"""
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import TestCase, mock

from anvil.mainwindow import MainWindow
from anvil.widgets.game_panel import GamePanel

MANIFEST = (Path(__file__).parents[1] / "packaging" / "flatpak"
            / "com.github.Marc1326.AnvilOrganizer.yml")


class MissingPrefixTests(TestCase):
    def test_a_missing_prefix_does_not_fail_the_deploy(self) -> None:
        result = SimpleNamespace(success=True, errors=[])
        writer = SimpleNamespace(
            last_error="plugins.txt path is unavailable (Proton prefix not found)",
            last_error_key="game_panel.plugins_no_prefix",
        )

        GamePanel._record_plugin_write_failure(result, writer)

        self.assertTrue(result.success, "the launch would be blocked forever")
        self.assertTrue(result.errors, "the reason still has to be reported")

    def test_any_other_write_error_still_fails_the_deploy(self) -> None:
        result = SimpleNamespace(success=True, errors=[])
        writer = SimpleNamespace(last_error="disk full", last_error_key="")

        GamePanel._record_plugin_write_failure(result, writer)

        self.assertFalse(result.success)


class LaunchFailureMessageTests(TestCase):
    def test_the_dialog_names_the_reason(self) -> None:
        """It used to pass details="" and told the user nothing."""
        window: Any = SimpleNamespace(
            _predeploy_for_launch=lambda _reason: False,
            _last_deploy_errors=["plugins.txt path is unavailable"],
        )
        window._report_predeploy_failure = (
            lambda result: MainWindow._report_predeploy_failure(window, result)
        )

        with mock.patch("anvil.mainwindow.host_popen"), mock.patch(
            "anvil.mainwindow.QMessageBox.warning"
        ) as warning:
            MainWindow._on_start_game(window, "/game/Game.exe", "/game")

        warning.assert_called_once()
        self.assertIn("plugins.txt", warning.call_args[0][2])

    def test_a_running_game_is_not_reported_twice(self) -> None:
        """None means the reason was already shown."""
        window: Any = SimpleNamespace(_last_deploy_errors=[])

        with mock.patch("anvil.mainwindow.QMessageBox.warning") as warning:
            MainWindow._report_predeploy_failure(window, None)

        warning.assert_not_called()


class FlatpakSandboxTests(TestCase):
    def test_the_manifest_reaches_flatpak_steam_and_heroic(self) -> None:
        """--filesystem=home excludes ~/.var/app on purpose."""
        text = MANIFEST.read_text(encoding="utf-8")

        self.assertIn("--filesystem=~/.var/app/com.valvesoftware.Steam", text)
        self.assertIn("--filesystem=~/.var/app/com.heroicgameslauncher.hgl", text)

    def test_steam_lookup_covers_the_flatpak_location(self) -> None:
        """The path was always searched - the sandbox just hid it."""
        from anvil.stores.steam_utils import _STEAM_PATHS

        flatpak = Path.home() / ".var" / "app" / "com.valvesoftware.Steam"
        self.assertTrue(
            any(flatpak in candidate.parents or candidate == flatpak
                for candidate in _STEAM_PATHS),
            "the flatpak Steam library is not in the search list",
        )
