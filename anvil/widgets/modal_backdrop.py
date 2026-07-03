"""Abdunkelung hinter modalen Dialogen (Vorlage: rgba(8,10,12,.55))."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QWidget


class ModalBackdrop(QWidget):
    """Halbtransparente Fläche über dem Hauptfenster, solange ein
    modaler Dialog offen ist. Folgt der Fenstergröße."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("modalBackdrop")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setGeometry(parent.rect())
        parent.installEventFilter(self)
        self.show()
        self.raise_()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parent().rect())
        return False

    def dismiss(self) -> None:
        if self.parent() is not None:
            self.parent().removeEventFilter(self)
        self.hide()
        self.deleteLater()
