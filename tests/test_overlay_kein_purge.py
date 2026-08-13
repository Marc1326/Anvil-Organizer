"""Beim Overlay wird nach dem Spiel nichts aufgeraeumt.

Gemessen am 13.08.2026 mit Marcs Cyberpunk-Sammlung: Anvil legte 1459
Dateien in die Schicht, der Mount klappte -- und dann meldete der
Prozesswaechter „game process gone", obwohl das Spiel gerade erst
startete. Hinter dem Startwrapper und ``bwrap`` sieht der Prozessbaum
anders aus, Anvil verlor das Spiel aus den Augen.

Das folgende Aufraeumen loeschte die Schicht **waehrend** das Spiel
hochfuhr. Ein Overlay liest live aus der Schicht, also verschwanden
``version.dll`` und ``winmm.dll`` mitten im Start. Wine lud seine
eigenen (im Proton-Protokoll als ``builtin``), Cyber Engine Tweaks und
RED4ext kamen nie hoch, das Spiel stuerzte ab.

Beim Overlay gibt es ohnehin nichts aufzuraeumen: der Mount lebt im
Namespace des Spiels und endet mit ihm.
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


def test_overlay_raeumt_nicht_auf() -> None:
    """Der Kern: die Schicht bleibt stehen."""
    f = _Fenster(overlay=True)
    f._purge_after_game()
    assert f._game_panel.geraeumt == 0, (
        "die Schicht wurde geloescht -- das Spiel verliert seine Loader"
    )


def test_symlink_weg_raeumt_weiterhin_auf() -> None:
    """Gegenprobe -- sonst misst der Test oben nichts."""
    f = _Fenster(overlay=False)
    f._purge_after_game()
    assert f._game_panel.geraeumt == 1


def test_overlay_schaut_gar_nicht_erst_in_den_spielordner() -> None:
    """Kein Vorher/Nachher-Vergleich, es gibt ja nichts zu vergleichen."""
    f = _Fenster(overlay=True)
    f._purge_after_game()
    assert f.protokolliert == 0


def test_dauerhaft_bleibt_unberuehrt() -> None:
    """Der bestehende Schutz muss weiter greifen."""
    f = _Fenster(overlay=False, dauerhaft=True)
    f._purge_after_game()
    assert f._game_panel.geraeumt == 0


def test_overlay_gewinnt_gegen_dauerhaft() -> None:
    """Beides an: geraeumt wird trotzdem nicht."""
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
