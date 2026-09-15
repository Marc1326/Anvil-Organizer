"""Die rechte Seitenleiste laesst sich im modernen Design ziehen (#112).

Modern: Griff zwischen Mod-Liste und Seitenleiste ist greifbar, die
Seitenleiste wird nie schmaler als PANEL_MIN_WIDTH, nichts klappt weg.
Der Griff am Filter-Panel bleibt fest. Klassische Themes wie bisher.

Jeder Test biegt HOME auf ein Temp-Verzeichnis -- die Einstellungen
landen sonst in der echten Konfiguration.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QColor, QHoverEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QSplitter, QVBoxLayout, QWidget

import anvil.styles.dark_theme as dark_theme
from anvil.mainwindow import MainWindow
from anvil.styles.dark_theme import apply_theme
from anvil.widgets.game_panel import PANEL_MIN_WIDTH, GamePanel

QWIDGETSIZE_MAX = 16777215


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def home(app, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(dark_theme, "_current_palette", {})
    vorher = app.styleSheet()
    yield tmp_path
    app.setStyleSheet(vorher)


class _ModListeStumm:
    def restore_column_widths(self):
        pass

    def restore_framework_widths(self):
        pass

    def restore_preset_widths(self):
        pass


class _Fenster(QWidget):
    """Nachbau des Hauptfensters: echte Splitter, echtes GamePanel."""

    _settings = staticmethod(MainWindow._settings)
    _bg3_mod_list = None

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("mainSplitter")
        self._left = QWidget()
        left_lay = QVBoxLayout(self._left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        self._filter_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._filter_panel = QWidget()
        self._filter_panel.setMaximumWidth(224)
        self._mods = QWidget()
        self._filter_splitter.addWidget(self._filter_panel)
        self._filter_splitter.addWidget(self._mods)
        self._filter_splitter.setChildrenCollapsible(False)
        left_lay.addWidget(self._filter_splitter)
        self._splitter.addWidget(self._left)
        self._game_panel = GamePanel()
        self._splitter.addWidget(self._game_panel)
        self._splitter.setSizes([780, 420])
        lay.addWidget(self._splitter)
        self._mod_list_view = _ModListeStumm()
        self._restored_tabs: set[int] = set()

    def centralWidget(self):
        return self

    def _apply_splitter_locks(self):
        MainWindow._apply_splitter_locks(cast(Any, self))

    def restore_ui_state(self):
        MainWindow._restore_ui_state(cast(Any, self))


@pytest.fixture
def fenster(app, home):
    """Baut Fenster und raeumt sie auch dann weg, wenn der Test scheitert."""
    erzeugt = []

    def bauen(theme: str, zeigen: bool = True) -> _Fenster:
        apply_theme(app, theme)
        f = _Fenster()
        erzeugt.append(f)
        f.resize(1400, 800)
        f._game_panel.apply_theme_metrics()
        if zeigen:
            f.show()
            app.processEvents()
        return f

    yield bauen
    for f in erzeugt:
        # Offene Breiten-Speicherungen schreiben, solange HOME umgebogen ist
        f._game_panel.flush_column_widths()
        f.close()
        f.deleteLater()
    app.processEvents()


def _wechsel(app, f: _Fenster, theme: str) -> None:
    """Live-Wechsel in der Reihenfolge des Hauptfensters."""
    apply_theme(app, theme)
    f._apply_splitter_locks()
    f._game_panel.apply_theme_metrics()
    app.processEvents()


def _luecken(f: _Fenster) -> tuple[int, int]:
    """(Abstand Mod-Liste -> Seitenleiste, Rest rechts neben der Seitenleiste)."""
    links = f._left.geometry()
    panel = f._game_panel.geometry()
    return panel.x() - (links.right() + 1), f._splitter.width() - (panel.right() + 1)


def _zustand_modern(f: _Fenster) -> None:
    ms, fs = f._splitter, f._filter_splitter
    assert ms.handle(1).isEnabled()
    assert ms.handleWidth() == 6
    assert not fs.handle(1).isEnabled()
    assert fs.handleWidth() == 1
    assert ms.isCollapsible(0) is False
    assert ms.isCollapsible(1) is False
    assert f._game_panel.minimumWidth() == PANEL_MIN_WIDTH
    assert f._game_panel.maximumWidth() == QWIDGETSIZE_MAX
    assert f._game_panel.width() >= PANEL_MIN_WIDTH


def _zustand_klassisch(f: _Fenster) -> None:
    ms, fs = f._splitter, f._filter_splitter
    stil = ms.style().pixelMetric(ms.style().PixelMetric.PM_SplitterWidth, None, ms)
    assert ms.handle(1).isEnabled()
    assert fs.handle(1).isEnabled()
    assert ms.handleWidth() == stil
    assert fs.handleWidth() == stil
    assert ms.isCollapsible(0) is True
    assert ms.isCollapsible(1) is True
    assert f._game_panel.minimumWidth() == 0
    assert f._game_panel.maximumWidth() == QWIDGETSIZE_MAX


def _ziehen(app, griff: QWidget, dx: int) -> None:
    start = griff.mapToGlobal(QPoint(griff.width() // 2, 5))
    lokal = QPointF(griff.width() // 2, 5)
    for art, versatz, knopf, knoepfe in (
        (QEvent.Type.MouseButtonPress, 0, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton),
        (QEvent.Type.MouseMove, dx, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton),
        (QEvent.Type.MouseButtonRelease, dx, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton),
    ):
        app.sendEvent(griff, QMouseEvent(
            art, lokal + QPointF(versatz, 0), QPointF(start.x() + versatz, start.y()),
            knopf, knoepfe, Qt.KeyboardModifier.NoModifier,
        ))
    app.processEvents()


# ── Modern ───────────────────────────────────────────────────────────


def test_a1_haupt_griff_frei_filter_griff_fest(app, fenster):
    f = fenster("Anvil Dunkel")
    f._apply_splitter_locks()
    app.processEvents()
    _zustand_modern(f)
    assert _luecken(f) == (6, 0)


def test_a2_seitenleiste_ohne_hoechstbreite(app, fenster):
    f = fenster("Anvil Dunkel")
    f._apply_splitter_locks()
    assert f._game_panel.maximumWidth() == QWIDGETSIZE_MAX
    assert f._game_panel.minimumWidth() == PANEL_MIN_WIDTH
    f._splitter.setSizes([700, 700])
    app.processEvents()
    assert abs(f._game_panel.width() - 700) <= 6


def test_k1_k3_griff_ziehen_und_mindestbreite(app, fenster):
    f = fenster("Anvil Hell")
    f._apply_splitter_locks()
    f._splitter.setSizes([900, 500])
    app.processEvents()
    griff = f._splitter.handle(1)
    assert griff.cursor().shape() == Qt.CursorShape.SplitHCursor

    _ziehen(app, griff, -200)
    assert f._game_panel.width() == 700
    assert _luecken(f) == (6, 0)

    # Nach rechts ueber das Ziel hinaus: stoppt bei der Mindestbreite
    _ziehen(app, griff, 900)
    assert f._game_panel.width() == PANEL_MIN_WIDTH
    assert f._left.width() > 0
    assert _luecken(f) == (6, 0)


def test_k4_filter_griff_bewegt_sich_nicht(app, fenster):
    f = fenster("Anvil Dunkel")
    f._apply_splitter_locks()
    app.processEvents()
    vorher = f._filter_splitter.sizes()
    _ziehen(app, f._filter_splitter.handle(1), 100)
    assert f._filter_splitter.sizes() == vorher


def test_a3_gespeicherte_breite_bleibt(app, fenster):
    f = fenster("Anvil Dunkel")
    f._apply_splitter_locks()
    f._splitter.setSizes([800, 600])
    app.processEvents()
    stand = f._splitter.saveState()
    f._splitter.setSizes([1054, 340])
    app.processEvents()

    f._splitter.restoreState(stand)
    f._apply_splitter_locks()
    app.processEvents()
    assert abs(f._game_panel.width() - 600) <= 6
    assert _luecken(f) == (6, 0)


def test_a4_schmaler_stand_wird_auf_mindestbreite_geklemmt(app, fenster):
    # Stand aus einem klassischen Theme, schmaler als die Mindestbreite
    f = fenster("Nord")
    f._apply_splitter_locks()
    f._splitter.setSizes([1300, 100])
    app.processEvents()
    assert f._splitter.sizes()[1] < PANEL_MIN_WIDTH
    stand = f._splitter.saveState()

    # Live-Wechsel: die Sperre laeuft vor apply_theme_metrics, das Panel hat
    # dort noch keine Mindestbreite -- die Klemme muss es selbst tun
    apply_theme(app, "Anvil Dunkel")
    f._splitter.restoreState(stand)
    f._apply_splitter_locks()
    assert f._game_panel.minimumWidth() == 0
    assert f._splitter.sizes()[1] == PANEL_MIN_WIDTH
    f._game_panel.apply_theme_metrics()
    app.processEvents()
    assert f._game_panel.width() == PANEL_MIN_WIDTH
    links, rechts = _luecken(f)
    assert f._left.geometry().right() + 1 + f._splitter.handleWidth() == f._game_panel.x()
    assert (links, rechts) == (6, 0)


def test_a4_schmaler_stand_beim_start_ohne_luecke(app, fenster):
    f = fenster("Nord")
    f._apply_splitter_locks()
    f._splitter.setSizes([1300, 100])
    app.processEvents()
    stand = f._splitter.saveState()

    g = fenster("Anvil Dunkel", zeigen=False)
    g._splitter.restoreState(stand)
    g._apply_splitter_locks()
    g.show()
    app.processEvents()
    assert g._game_panel.width() == PANEL_MIN_WIDTH
    assert _luecken(g) == (6, 0)


def test_a5_nichts_klappt_weg(app, fenster):
    f = fenster("Anvil Dunkel")
    # Ein klassischer Stand bringt "zusammenklappbar" mit
    f._splitter.setChildrenCollapsible(True)
    f._apply_splitter_locks()
    assert f._splitter.isCollapsible(0) is False
    assert f._splitter.isCollapsible(1) is False


def test_a10_vergroessern_waechst_nur_die_mod_liste(app, fenster):
    f = fenster("Anvil Dunkel")
    f._apply_splitter_locks()
    f._splitter.setSizes([900, 500])
    app.processEvents()
    assert f._game_panel.width() == 500
    f.resize(1800, 800)
    app.processEvents()
    assert f._game_panel.width() == 500


def test_a8_griff_zeichnet_linie_und_akzent_beim_ueberfahren(app, fenster):
    f = fenster("Anvil Dunkel")
    f._apply_splitter_locks()
    app.processEvents()
    farben = dark_theme.current_palette()
    griff = f._splitter.handle(1)

    def pixel(x: int) -> QColor:
        bild = griff.grab().toImage()
        return bild.pixelColor(x, bild.height() // 2)

    def nah(ist: QColor, soll: QColor) -> bool:
        return all(abs(a - b) <= 3 for a, b in (
            (ist.red(), soll.red()), (ist.green(), soll.green()), (ist.blue(), soll.blue())))

    assert nah(pixel(0), QColor(farben["line"]))
    assert nah(pixel(3), QColor(farben["panel"]))

    app.sendEvent(griff, QHoverEvent(
        QEvent.Type.HoverEnter, QPointF(3, 5), QPointF(3, 5), QPointF(-1, -1)))
    app.processEvents()
    # accent_soft ist halbtransparent ("rgba(r,g,b,a)") und liegt ueber dem
    # Fensterhintergrund
    r, g, b, a = re.findall(r"[\d.]+", farben["accent_soft"])
    a = float(a)
    hinten = QColor(farben["bg"])
    gemischt = QColor(
        round(int(r) * a + hinten.red() * (1 - a)),
        round(int(g) * a + hinten.green() * (1 - a)),
        round(int(b) * a + hinten.blue() * (1 - a)),
    )
    assert not nah(gemischt, QColor(farben["panel"]))
    assert nah(pixel(3), gemischt)
    assert nah(pixel(0), QColor(farben["line"]))

    app.sendEvent(griff, QHoverEvent(
        QEvent.Type.HoverLeave, QPointF(-1, -1), QPointF(-1, -1), QPointF(3, 5)))
    app.processEvents()
    assert nah(pixel(3), QColor(farben["panel"]))


def test_a8_hauptsplitter_traegt_den_namen_der_qss_regel(hauptfenster_prozess):
    ergebnis = hauptfenster_prozess("""
        ergebnis["name"] = fenster._splitter.objectName()
        ergebnis["seitenleiste_rechts"] = fenster._splitter.widget(1) is fenster._game_panel
    """)
    assert ergebnis == {"name": "mainSplitter", "seitenleiste_rechts": True}
    qss = (dark_theme.get_styles_dir() / "modern" / "anvil-modern.qss").read_text(
        encoding="utf-8")
    assert "QSplitter#mainSplitter::handle:horizontal {" in qss
    assert "QSplitter#mainSplitter::handle:horizontal:hover," in qss


def test_a9_erststart_modern_ohne_stand_ist_mindestbreite(app, fenster, home):
    f = fenster("Anvil Dunkel", zeigen=False)
    assert QSettings(str(home / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf"),
                     QSettings.Format.IniFormat).value("splitter/state") is None
    f.restore_ui_state()
    f.show()
    app.processEvents()
    assert f._game_panel.width() == PANEL_MIN_WIDTH
    assert _luecken(f) == (6, 0)


def test_k2_gespeicherte_breite_ueberlebt_den_neustart(app, fenster, home):
    f = fenster("Anvil Dunkel")
    f.restore_ui_state()
    f._splitter.setSizes([850, 550])
    app.processEvents()
    MainWindow._settings().setValue("splitter/state", f._splitter.saveState())

    g = fenster("Anvil Dunkel", zeigen=False)
    g.restore_ui_state()
    g.show()
    app.processEvents()
    assert g._game_panel.width() == 550
    assert _luecken(g) == (6, 0)


def test_klassisch_erststart_bleibt_wie_bisher(app, fenster):
    f = fenster("Nord", zeigen=False)
    f.restore_ui_state()
    f.show()
    app.processEvents()
    assert f._game_panel.width() > PANEL_MIN_WIDTH


# ── Klassisch und Live-Wechsel ───────────────────────────────────────


def test_a6_klassisch_wie_bisher(app, fenster):
    f = fenster("Nord")
    f._apply_splitter_locks()
    app.processEvents()
    _zustand_klassisch(f)
    start_klassisch = (f._splitter.handleWidth(), _luecken(f)[0])

    # Start modern, dann klassisch: gleiche Griffbreite wie beim Start klassisch
    g = fenster("Anvil Dunkel")
    g._apply_splitter_locks()
    app.processEvents()
    _wechsel(app, g, "Nord")
    _zustand_klassisch(g)
    assert (g._splitter.handleWidth(), _luecken(g)[0]) == start_klassisch


def test_a7_live_wechsel_hin_und_zurueck(app, fenster):
    f = fenster("Anvil Dunkel")
    f._apply_splitter_locks()
    app.processEvents()
    _zustand_modern(f)
    _wechsel(app, f, "Nord")
    _zustand_klassisch(f)
    _wechsel(app, f, "Anvil Hell")
    _zustand_modern(f)
    assert _luecken(f) == (6, 0)
    _wechsel(app, f, "Anvil Dunkel")
    _zustand_modern(f)


# ── Testsuite ────────────────────────────────────────────────────────


_REST_TESTS = r"""
import os
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import Shiboken

app = QApplication.instance() or QApplication([])
REST = []
TIMER = []


def test_anlegen(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    w = QWidget()
    w.show()
    app.processEvents()
    w.close()
    w.deleteLater()
    app.processEvents()
    REST.append(w)
    # Nachzuegler: laeuft erst nach dem Test, wenn HOME wieder echt ist
    def spaet():
        TIMER.append(Shiboken.isValid(w))
        (Path.home() / "nachzuegler.txt").write_text("x")
    QTimer.singleShot(0, spaet)


def test_weg():
    assert TIMER == [True]              # erst die Timer, dann geloescht
    assert not Shiboken.isValid(REST[0])
    assert not (Path(os.environ["HOME"]) / "nachzuegler.txt").exists()
"""


def test_z1_suite_loescht_abgeraeumte_widgets(tmp_path):
    # Eigene kleine Pytest-Sitzung mit der echten conftest
    conftest = Path(__file__).with_name("conftest.py")
    (tmp_path / "conftest.py").write_text(conftest.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "test_rest.py").write_text(_REST_TESTS, encoding="utf-8")
    heim = tmp_path / "heim"
    heim.mkdir()
    env = dict(os.environ, HOME=str(heim), XDG_CONFIG_HOME=str(heim / ".config"),
               QT_QPA_PLATFORM="offscreen")
    env.pop("PYTEST_ADDOPTS", None)
    lauf = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         f"--basetemp={tmp_path / 'basis'}", "test_rest.py"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
    assert lauf.returncode == 0, lauf.stdout[-3000:] + lauf.stderr[-2000:]
    assert "2 passed" in lauf.stdout
