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
    """Vor dem Start wird nicht mehr gefragt.

    Frueher kamen zwei Fenster: „Steam jetzt starten?" mit drei Knoepfen
    und danach „warte auf die Anmeldung" zum Wegklicken. Beide sagten
    nichts, was der Benutzer nicht schon wusste -- den Startknopf hatte er
    ja gerade gedrueckt. Jetzt startet Anvil Steam und wartet still.
    """

    def _panel(self) -> SimpleNamespace:
        panel = SimpleNamespace()
        panel._STEAM_WARTEN_S = 0
        panel._warte_auf_steam = lambda: True
        return panel

    def test_ein_laufendes_steam_fragt_nichts(self) -> None:
        with mock.patch("anvil.stores.steam_utils.is_steam_running",
                        return_value=True), \
             mock.patch("anvil.widgets.game_panel.QMessageBox") as box:
            result = GamePanel._ensure_steam_running(self._panel(), "/usr/bin/steam")

        self.assertTrue(result)
        box.assert_not_called()

    def _starten(self, popen, warten=True):
        panel = self._panel()
        panel._warte_auf_steam = lambda: warten
        with mock.patch("anvil.stores.steam_utils.is_steam_running",
                        return_value=False), \
             mock.patch("anvil.widgets.game_panel.QMessageBox") as box, \
             mock.patch("anvil.core.subprocess_env.host_popen", popen), \
             mock.patch("anvil.widgets.game_panel.clean_subprocess_env",
                        return_value={}):
            ergebnis = GamePanel._ensure_steam_running(panel, "/usr/bin/steam")
            return ergebnis, box

    def test_steam_wird_ohne_rueckfrage_gestartet(self) -> None:
        """Der Kern: kein Fenster, Steam laeuft einfach an."""
        popen = mock.MagicMock()
        ergebnis, box = self._starten(popen)

        self.assertTrue(ergebnis)
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0], ["/usr/bin/steam"])
        box.assert_not_called()
        box.question.assert_not_called()
        box.information.assert_not_called()

    def test_kein_wartefenster_nach_dem_start(self) -> None:
        popen = mock.MagicMock()
        _, box = self._starten(popen)
        box.information.assert_not_called()

    def test_start_geht_auch_weiter_wenn_steam_lange_braucht(self) -> None:
        """Anmeldung kann dauern -- abbrechen waere auch nur geraten."""
        popen = mock.MagicMock()
        ergebnis, box = self._starten(popen, warten=False)

        self.assertTrue(ergebnis)
        box.assert_not_called()

    def test_ein_fehlgeschlagener_start_stoppt_und_meldet_sich(self) -> None:
        """Das ist keine Rueckfrage, sondern ein echter Fehler."""
        popen = mock.MagicMock(side_effect=OSError("no such file"))
        ergebnis, box = self._starten(popen)

        self.assertFalse(ergebnis)
        box.warning.assert_called_once()

    def test_die_alten_dialog_schluessel_werden_nicht_mehr_benutzt(self) -> None:
        import inspect

        quelle = inspect.getsource(GamePanel._ensure_steam_running)
        for schluessel in ("steam_not_running_text", "steam_start_now",
                           "steam_continue_without", "steam_cancel",
                           "steam_wait_title", "steam_wait_text"):
            self.assertNotIn(schluessel, quelle, f"{schluessel} ist zurueck")
