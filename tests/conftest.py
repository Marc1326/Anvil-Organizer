"""Tests laufen ohne sichtbare Fenster.

Mehrere Tests bauen echte Qt-Widgets und rufen show(). Ohne diese Zeile
poppen sie waehrend der Suite auf dem Desktop auf und stoeren die Arbeit.
Zum Debuggen mit sichtbaren Fenstern: ANVIL_TEST_SHOW_WINDOWS=1 setzen.
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

if os.environ.get("ANVIL_TEST_SHOW_WINDOWS") != "1":
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Pixel-Tests messen in logischen Pixeln -- eine Skalierung aus der
# Umgebung verschiebt sonst jede Messung
for _name in ("QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS", "QT_FONT_DPI",
              "QT_ENABLE_HIGHDPI_SCALING", "QT_AUTO_SCREEN_SCALE_FACTOR",
              "QT_USE_PHYSICAL_DPI"):
    os.environ.pop(_name, None)


@pytest.fixture(scope="session")
def _aufraeum_home(tmp_path_factory):
    return tmp_path_factory.mktemp("qt-aufraeumen")


@pytest.fixture(autouse=True)
def _qt_widgets_wirklich_loeschen(_aufraeum_home):
    """deleteLater() wirkt ohne laufende Ereignisschleife nie.

    Die Reste bleiben sonst bis zum Ende der Suite am Leben, und jedes
    apply_theme() stylt sie alle neu -- die Suite wurde dadurch minutenlang.
    """
    yield
    qtcore = sys.modules.get("PySide6.QtCore")
    if qtcore is None or qtcore.QCoreApplication.instance() is None:
        return
    # Laeuft nach dem Abbau der Test-Fixtures: HOME zeigt wieder auf das
    # echte Verzeichnis. Was beim Aufraeumen noch schreibt, landet im Temp.
    gemerkt = {name: os.environ.get(name) for name in ("HOME", "XDG_CONFIG_HOME")}
    os.environ["HOME"] = str(_aufraeum_home)
    os.environ["XDG_CONFIG_HOME"] = str(_aufraeum_home / ".config")
    try:
        # Reihenfolge wichtig: erst ausstehende Timer der Widgets, dann loeschen.
        # Nur loeschen stuerzt ab, wenn ein Timer auf ein geloeschtes Widget zeigt.
        qtcore.QCoreApplication.processEvents()
        qtcore.QCoreApplication.sendPostedEvents(None, qtcore.QEvent.Type.DeferredDelete)
    finally:
        for name, wert in gemerkt.items():
            if wert is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = wert


_HAUPTFENSTER_VORSPANN = """
import json, os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
app = QApplication([])
from anvil.core.translator import tr
from anvil.mainwindow import MainWindow
MainWindow._check_first_start = lambda self: None  # Assistent wartet auf Eingaben
fenster = MainWindow()
ergebnis = {}
"""


@pytest.fixture
def hauptfenster_prozess(tmp_path):
    """Fuehrt Code mit einem echten MainWindow (``fenster``) in einem eigenen Prozess aus.

    HOME und XDG zeigen dort von Anfang an ins Temp-Verzeichnis, D-Bus ist aus
    (kein Schluesselbund). Der Code fuellt das Dict ``ergebnis``.
    """
    repo = Path(__file__).resolve().parents[1]

    def ausfuehren(code: str) -> dict:
        heim = tmp_path / "hauptfenster-heim"
        heim.mkdir(exist_ok=True)
        env = dict(os.environ)
        env.update(
            HOME=str(heim),
            XDG_CONFIG_HOME=str(heim / ".config"),
            XDG_DATA_HOME=str(heim / ".local" / "share"),
            XDG_CACHE_HOME=str(heim / ".cache"),
            DBUS_SESSION_BUS_ADDRESS="disabled:",
            QT_QPA_PLATFORM="offscreen",
            PYTHONPATH=os.pathsep.join(filter(None, [str(repo), env.get("PYTHONPATH")])),
        )
        skript = (_HAUPTFENSTER_VORSPANN + textwrap.dedent(code)
                  + '\nprint("ERGEBNIS " + json.dumps(ergebnis), flush=True)\nos._exit(0)\n')
        lauf = subprocess.run([sys.executable, "-c", skript], cwd=repo, env=env,
                              capture_output=True, text=True, timeout=120)
        zeile = next((z for z in lauf.stdout.splitlines() if z.startswith("ERGEBNIS ")), None)
        assert zeile, lauf.stdout[-2000:] + lauf.stderr[-2000:]
        return json.loads(zeile.removeprefix("ERGEBNIS "))

    return ausfuehren
