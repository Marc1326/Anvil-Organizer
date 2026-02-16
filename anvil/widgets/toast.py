"""Toast notification widget - shows brief messages that auto-disappear."""

from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect
from PySide6.QtCore import QTimer, QPropertyAnimation, Qt, QEasingCurve, Signal


class Toast(QLabel):
    """A toast notification that appears briefly and fades out.

    Supports optional click handling via the `clicked` signal.
    """

    clicked = Signal()

    def __init__(self, parent, message: str, duration: int = 3000, clickable: bool = False):
        super().__init__(message, parent)
        self._clickable = clickable

        style = """
            background: #006868;
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 12px;
        """
        self.setStyleSheet(style)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.adjustSize()

        # Position: bottom right of parent
        self.move(
            parent.width() - self.width() - 20,
            parent.height() - self.height() - 40
        )

        # Fade-in effect
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.effect.setOpacity(0)

        self.anim = QPropertyAnimation(self.effect, b"opacity")
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.start()

        # Auto-hide after duration
        QTimer.singleShot(duration, self._fade_out)
        self.show()
        self.raise_()

    def mousePressEvent(self, event):
        """Handle click on toast."""
        if self._clickable:
            self.clicked.emit()
            self._fade_out()
        super().mousePressEvent(event)

    def _fade_out(self):
        """Fade out and delete the toast."""
        self.anim.setDuration(300)
        self.anim.setStartValue(1)
        self.anim.setEndValue(0)
        self.anim.finished.connect(self.deleteLater)
        self.anim.start()
