"""Vollflächen-Overlay beim Instanzwechsel (nur modernes Design).

Legt sich über das MainWindow, zeigt Spinner + Phasentext
(„… wird geschlossen" → „… wird geöffnet") und verschwindet wieder.
Die Wechsel-Logik selbst (switch_instance) bleibt unangetastet.
"""

from PySide6.QtCore import QEvent, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from anvil.core.translator import tr
from anvil.styles.dark_theme import theme_color


class SwitchOverlay(QWidget):
    """Abdunkelndes Overlay mit Spinner und zweizeiligem Text."""

    _SPINNER_SIZE = 40

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setVisible(False)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(10)
        # Platz für den gemalten Spinner oberhalb des Textes
        lay.addSpacing(self._SPINNER_SIZE + 16)
        self._phase_lbl = QLabel("")
        self._phase_lbl.setObjectName("ovlPhase")
        self._phase_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._phase_lbl)
        self._sub_lbl = QLabel(tr("instance.separated"))
        self._sub_lbl.setObjectName("ovlSub")
        self._sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._sub_lbl)

        parent.installEventFilter(self)

    # ── Ablauf ────────────────────────────────────────────────────────

    def start(self, phase_text: str) -> None:
        self._phase_lbl.setText(phase_text)
        self._sub_lbl.setText(tr("instance.separated"))
        self.resize(self.parentWidget().size())
        self.raise_()
        self.show()
        self._timer.start()

    def set_phase(self, phase_text: str) -> None:
        self._phase_lbl.setText(phase_text)

    def finish(self) -> None:
        self._timer.stop()
        self.hide()

    # ── Intern ────────────────────────────────────────────────────────

    def _on_tick(self) -> None:
        self._angle = (self._angle + 8) % 360
        self.update()

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.parentWidget() and event.type() == QEvent.Type.Resize:
            if self.isVisible():
                self.resize(self.parentWidget().size())
        return super().eventFilter(obj, event)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(8, 10, 12, 158))
        # Spinner: offener Kreisbogen in Akzentfarbe, mittig über dem Text
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(theme_color("accent", "#33b3a8")))
        pen.setWidth(4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        size = self._SPINNER_SIZE
        rect = QRectF(
            (self.width() - size) / 2,
            self.height() / 2 - size - 10,
            size, size,
        )
        p.drawArc(rect, -self._angle * 16, 100 * 16)
        p.end()
