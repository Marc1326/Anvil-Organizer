"""Glocken-Button mit Zähler-Badge und Benachrichtigungs-Popup (#14).

KEIN ``setStyleSheet`` — das Badge wird per QPainter gezeichnet (theme-unabhängig
und immun gegen die QSS-Vererbung), das Panel erbt das Theme automatisch.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QToolButton, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
)

from anvil.core.translator import tr

# Farben je Schweregrad (per QPainter/QColor, NICHT setStyleSheet).
_LEVEL_COLORS = {
    "info": "#5BC0DE",
    "warning": "#E5C07B",
    "error": "#E06C75",
}


class NotificationButton(QToolButton):
    """QToolButton, der oben rechts einen Zähler-Badge zeichnet.

    Das Zeichnen im paintEvent rechnet aus der aktuellen Button-Größe — dadurch
    bleibt der Badge bei Icon-Größenwechsel (Toolbar-Settings) korrekt platziert.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._count = 0

    def set_count(self, count: int) -> None:
        count = max(0, int(count))
        if count != self._count:
            self._count = count
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._count <= 0:
            return
        text = "99+" if self._count > 99 else str(self._count)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        d = 14
        w = max(d, 7 + 6 * len(text))
        rect = QRectF(self.width() - w - 1.0, 1.0, float(w), float(d))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#D9534F")))
        painter.drawRoundedRect(rect, d / 2.0, d / 2.0)
        f = QFont(self.font())
        f.setPointSizeF(8.0)
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.end()


class NotificationPanel(QWidget):
    """Popup-Liste der Benachrichtigungen mit Aktionen 'Alle gelesen' / 'Leeren'."""

    def __init__(self, center, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._center = center

        layout = QVBoxLayout(self)
        title = QLabel(tr("notifications.title"))
        tf = QFont(title.font())
        tf.setBold(True)
        title.setFont(tf)
        layout.addWidget(title)

        self._list = QListWidget()
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._mark_btn = QPushButton(tr("notifications.mark_all_read"))
        self._clear_btn = QPushButton(tr("notifications.clear"))
        self._mark_btn.clicked.connect(lambda checked=False: self._on_mark_read())
        self._clear_btn.clicked.connect(lambda checked=False: self._on_clear())
        btn_row.addWidget(self._mark_btn)
        btn_row.addWidget(self._clear_btn)
        layout.addLayout(btn_row)

        self.resize(380, 320)
        self._refresh()

    def _refresh(self) -> None:
        self._list.clear()
        items = self._center.items()
        if not items:
            placeholder = QListWidgetItem(tr("notifications.empty"))
            placeholder.setForeground(QColor("#808080"))
            self._list.addItem(placeholder)
            return
        for n in items:
            when = time.strftime("%H:%M", time.localtime(n.timestamp))
            text = f"[{when}] {n.title}"
            if n.message:
                text += f"\n{n.message}"
            item = QListWidgetItem(text)
            color = _LEVEL_COLORS.get(n.level)
            if color:
                item.setForeground(QColor(color))
            self._list.addItem(item)

    def _on_mark_read(self) -> None:
        self._center.mark_all_read()
        self._refresh()

    def _on_clear(self) -> None:
        self._center.clear()
        self._refresh()

    def show_under(self, button) -> None:
        """Zeigt das Panel unter dem Button und markiert alles als gelesen."""
        self._refresh()
        pos = button.mapToGlobal(button.rect().bottomLeft())
        self.move(pos)
        self.show()
        self._center.mark_all_read()
