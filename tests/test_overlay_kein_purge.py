"""Der globale Kernel-Overlay-Mount endet erst durch Anvils Cleanup.

Der Prozesswaechter darf erst aufraeumen, wenn das Spiel wirklich beendet
ist. Danach muss er es aber tun: Der direkte Mount auf dem Spielordner lebt
nicht in einem kurzlebigen Spiel-Namespace und blieb in drei Live-Tests nach
dem Spielende weiter aktiv.
"""

from __future__ import annotations

from anvil.mainwindow import MainWindow


class _Panel:
    def __init__(self):
        self.geraeumt = 0

    def silent_purge(self):
        self.geraeumt += 1
        return None


class _Fenster:
    """MainWindow-Ersatz mit genau dem, was das Aufraeumen anfasst."""

    _purge_after_game = MainWindow._purge_after_game
    uses_overlay = MainWindow.uses_overlay
    keeps_mods_deployed = MainWindow.keeps_mods_deployed

    def __init__(self, overlay=False, dauerhaft=False):
        self._game_panel = _Panel()
        self._daten = {
            "use_overlay": "true" if overlay else "false",
            "keep_mods_deployed": "true" if dauerhaft else "false",
        }
        self.protokolliert = 0

        fenster = self

        class _IM:
            @staticmethod
            def current_instance():
                return "Testspiel"

            @staticmethod
            def load_instance(name):
                return dict(fenster._daten)

        self.instance_manager = _IM()

    def _log_game_dir_state(self, phase):
        self.protokolliert += 1


def test_overlay_raeumt_nach_spielende_auf() -> None:
    """Der globale Mount darf nach dem Spiel nicht stehen bleiben."""
    f = _Fenster(overlay=True)
    f._purge_after_game()
    assert f._game_panel.geraeumt == 1


def test_symlink_weg_raeumt_weiterhin_auf() -> None:
    """Gegenprobe -- sonst misst der Test oben nichts."""
    f = _Fenster(overlay=False)
    f._purge_after_game()
    assert f._game_panel.geraeumt == 1


def test_overlay_protokolliert_vorher_und_nachher() -> None:
    """Die Diagnose bleibt fuer fehlgeschlagene Unmounts sichtbar."""
    f = _Fenster(overlay=True)
    f._purge_after_game()
    assert f.protokolliert == 2


def test_dauerhaft_bleibt_unberuehrt() -> None:
    """Der bestehende Schutz muss weiter greifen."""
    f = _Fenster(overlay=False, dauerhaft=True)
    f._purge_after_game()
    assert f._game_panel.geraeumt == 0


def test_dauerhaft_schuetzt_auch_overlay() -> None:
    """Der ausdrueckliche Dauerbetrieb bleibt die einzige Ausnahme."""
    f = _Fenster(overlay=True, dauerhaft=True)
    f._purge_after_game()
    assert f._game_panel.geraeumt == 0


# ── Die Abfrage selbst ───────────────────────────────────────────────


def test_uses_overlay_liest_die_instanz() -> None:
    assert _Fenster(overlay=True).uses_overlay() is True
    assert _Fenster(overlay=False).uses_overlay() is False


def test_ohne_instanz_kein_overlay() -> None:
    f = _Fenster(overlay=True)

    class _Leer:
        @staticmethod
        def current_instance():
            return ""

        @staticmethod
        def load_instance(name):
            return {}

    f.instance_manager = _Leer()
    assert f.uses_overlay() is False


def test_schreibweise_egal() -> None:
    for wert in ("true", "True", "1", "TRUE"):
        f = _Fenster()
        f._daten["use_overlay"] = wert
        assert f.uses_overlay() is True, wert
    for wert in ("false", "0", "", "nein"):
        f = _Fenster()
        f._daten["use_overlay"] = wert
        assert f.uses_overlay() is False, wert
