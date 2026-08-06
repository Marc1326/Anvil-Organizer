"""Der Drop auf die Mod-Liste, ausgeloest wie im Betrieb.

Frueher haben drei Stellen unabhaengig voneinander nur auf die
Dateiendung geschaut. Ein Nexus-CDN-Download ohne Endung wurde dadurch
still verworfen -- der Mauszeiger zeigte "verboten", und niemand erfuhr,
warum.
"""

from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QPointF, QUrl, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication

from anvil.models.mod_list_model import ModListModel
from anvil.widgets.mod_list import _DropTreeView

SIEBEN_Z = b"7z\xbc\xaf\x27\x1c" + b"\x00" * 24


def _urls(*pfade: Path) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in pfade])
    return mime


def _drop(view: _DropTreeView, mime: QMimeData) -> tuple[bool, list]:
    """Zieht ueber die Liste und laesst los. Gibt (angenommen, Pfade) zurueck."""
    angekommen: list = []
    view.archives_dropped.connect(lambda p: angekommen.extend(p))
    view.archives_dropped_at.connect(lambda p, _r: angekommen.extend(p))

    enter = QDragEnterEvent(
        QPoint(50, 50), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    view.dragEnterEvent(enter)
    view.dropEvent(QDropEvent(
        QPointF(50, 50), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    ))
    return enter.isAccepted(), angekommen


def _view() -> _DropTreeView:
    QApplication.instance() or QApplication([])
    view = _DropTreeView()
    view.resize(400, 300)
    return view


def test_uuid_ohne_endung_wird_angenommen(tmp_path: Path) -> None:
    archiv = tmp_path / "4c85f1da-33b2-438e-9e9a-9df94039c224"
    archiv.write_bytes(SIEBEN_Z)

    angenommen, pfade = _drop(_view(), _urls(archiv))
    assert angenommen
    assert pfade == [str(archiv)]


def test_zip_mit_endung_geht_weiter_wie_bisher(tmp_path: Path) -> None:
    archiv = tmp_path / "KITSUNE-FACE-866-0-1-1751048914.zip"
    archiv.write_bytes(b"PK\x03\x04" + b"\x00" * 26)

    angenommen, pfade = _drop(_view(), _urls(archiv))
    assert angenommen
    assert pfade == [str(archiv)]


def test_bild_wird_weiter_abgelehnt(tmp_path: Path) -> None:
    bild = tmp_path / "cover.png"
    bild.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 24)

    angenommen, pfade = _drop(_view(), _urls(bild))
    assert not angenommen
    assert pfade == []


def test_gemischter_wurf_nimmt_nur_die_archive(tmp_path: Path) -> None:
    archiv = tmp_path / "580ab29e-4839-4ee6-9eee-5ef78d13b3ee"
    archiv.write_bytes(SIEBEN_Z)
    bild = tmp_path / "vorschau.png"
    bild.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 24)

    _, pfade = _drop(_view(), _urls(bild, archiv))
    assert pfade == [str(archiv)]


def test_modell_laesst_die_uuid_durch(tmp_path: Path) -> None:
    """canDropMimeData ist die dritte Sperre -- ohne sie zeigt der
    Mauszeiger schon waehrend des Ziehens "verboten"."""
    QApplication.instance() or QApplication([])
    archiv = tmp_path / "7d992d6d-58cc-4ca3-a335-b442eed3a958"
    archiv.write_bytes(SIEBEN_Z)

    modell = ModListModel()
    assert modell.canDropMimeData(
        _urls(archiv), Qt.DropAction.CopyAction, -1, -1, modell.index(-1, -1))
