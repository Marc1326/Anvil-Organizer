"""Entsperren gibt die Oberflaeche frei -- und sonst nichts.

Frueher fragte der Knopf: „Die Mods liegen noch im Spielordner. Jetzt
entfernen?" Der Knopf heisst Entsperren, das Fenster hiess „Spiel
entsperren", und „Ja" las sich wie „ja, entsperren" -- gemeint war „ja,
loeschen". Wer nur nachschauen wollte, riss dem laufenden Spiel die Mods
weg: gemessen 1440 Dateien in einem Zug.

Schlimmer noch: der Weg vergass danach den beobachteten Prozess
(``clear_watch_target``). ``game_state()`` liefert ohne Prozessnamen
``STOPPED``, also hielt Anvil das Spiel fuer beendet -- und **jede**
spaetere Aenderung an einer Mod schlug sofort in den Spielordner durch,
obwohl das Spiel lief.
"""

from __future__ import annotations

from unittest import mock

import pytest

from anvil.mainwindow import MainWindow


class _Spielleiste:
    def __init__(self, laeuft=True):
        self._laeuft = laeuft
        self.vergessen = 0
        self.deployment = True

    def is_game_running(self):
        return self._laeuft

    def has_deployment(self):
        return self.deployment

    def clear_watch_target(self):
        self.vergessen += 1


class _Fenster:
    """MainWindow-Ersatz mit genau dem, was das Entsperren anfasst."""

    _on_unlock_clicked = MainWindow._on_unlock_clicked

    def __init__(self, laeuft=True):
        self._game_running = laeuft
        self._game_panel = _Spielleiste(laeuft)
        self.aufgeraeumt = 0
        self.freigegeben = 0

    def _purge_after_game(self):
        self.aufgeraeumt += 1

    def _release_ui_lock(self):
        self.freigegeben += 1


@pytest.fixture
def fenster():
    return _Fenster()


# ── Was Entsperren tut ───────────────────────────────────────────────


def test_gibt_die_oberflaeche_frei(fenster) -> None:
    fenster._on_unlock_clicked()
    assert fenster.freigegeben == 1


def test_raeumt_nichts_auf(fenster) -> None:
    """Der Kern: die Mods bleiben im Spielordner."""
    fenster._on_unlock_clicked()
    assert fenster.aufgeraeumt == 0, "das Deployment wurde entfernt"


def test_fragt_nicht(fenster) -> None:
    """Entsperren ist eine bewusste Handlung -- keine zweite Rueckfrage."""
    with mock.patch("anvil.mainwindow.QMessageBox") as box:
        fenster._on_unlock_clicked()
    box.question.assert_not_called()
    box.assert_not_called()


def test_vergisst_das_spiel_nicht(fenster) -> None:
    """Sonst faellt der Schutz gegen Aenderungen bei laufendem Spiel weg."""
    fenster._on_unlock_clicked()
    assert fenster._game_panel.vergessen == 0, (
        "clear_watch_target aufgerufen -- Anvil haelt das Spiel jetzt fuer "
        "beendet"
    )


def test_spiel_gilt_weiterhin_als_laufend(fenster) -> None:
    fenster._on_unlock_clicked()
    assert fenster._game_running is True, (
        "_game_running zurueckgesetzt -- der Schutz in _do_redeploy greift "
        "nicht mehr"
    )


def test_auch_ohne_deployment_nur_freigeben() -> None:
    f = _Fenster()
    f._game_panel.deployment = False
    f._on_unlock_clicked()
    assert (f.freigegeben, f.aufgeraeumt, f._game_panel.vergessen) == (1, 0, 0)


# ── Der Schutz bleibt danach aktiv ───────────────────────────────────


def test_schutz_greift_nach_dem_entsperren(fenster) -> None:
    """Zusammenspiel: nach dem Entsperren darf _do_redeploy nichts tun.

    Der Schutz haengt an ``self._game_running`` oder
    ``_game_panel.is_game_running()``. Entsperren darf beides in Ruhe
    lassen.
    """
    fenster._on_unlock_clicked()
    laeuft_noch = (fenster._game_running
                   or fenster._game_panel.is_game_running())
    assert laeuft_noch, "Anvil wuerde jetzt im Spielordner arbeiten"


def test_quelltext_ohne_purge_und_ohne_dialog() -> None:
    import inspect

    quelle = inspect.getsource(MainWindow._on_unlock_clicked)
    for verboten in ("_purge_after_game", "clear_watch_target",
                     "QMessageBox", "unlock_purge"):
        assert verboten not in quelle, f"{verboten} ist zurueck"


def test_aufraeumen_beim_spielende_bleibt() -> None:
    """Wenn das Spiel wirklich endet, wird weiterhin aufgeraeumt."""
    import inspect

    quelle = inspect.getsource(MainWindow._unlock_ui)
    assert "_purge_after_game" in quelle
    assert "clear_watch_target" in quelle
