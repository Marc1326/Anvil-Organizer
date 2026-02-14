"""FlowLayout: Qt-Layout that wraps widgets like text in a paragraph.

Based on the official Qt FlowLayout example, adapted for PySide6.
Used by FilterPanel to arrange FilterChip widgets in a wrapping grid.
"""

from PySide6.QtWidgets import QLayout, QSizePolicy
from PySide6.QtCore import Qt, QRect, QSize, QPoint


class FlowLayout(QLayout):
    """A layout that arranges child widgets left-to-right, wrapping to the next
    row when the available width is exceeded."""

    def __init__(self, parent=None, margin=-1, h_spacing=4, v_spacing=4):
        super().__init__(parent)
        self._h_space = h_spacing
        self._v_space = v_spacing
        self._items = []
        if margin >= 0:
            self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def insertWidget(self, index: int, widget) -> None:
        """Insert a widget at a specific position in the layout."""
        from PySide6.QtWidgets import QWidgetItem
        self.addChildWidget(widget)
        item = QWidgetItem(widget)
        index = max(0, min(index, len(self._items)))
        self._items.insert(index, item)
        # Geometry speichern VOR invalidate (wird sonst zurückgesetzt)
        current_geo = QRect(self.geometry())
        self.invalidate()
        # Sofort Layout neu berechnen mit gespeicherter geometry
        if current_geo.isValid():
            self._do_layout(current_geo, test_only=False)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only):
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            wid = item.widget()
            if wid and not wid.isVisible():
                continue
            space_x = self._h_space
            space_y = self._v_space
            sz = item.sizeHint()
            next_x = x + sz.width() + space_x
            if next_x - space_x > effective.right() + 1 and line_height > 0:
                x = effective.x()
                y = y + line_height + space_y
                next_x = x + sz.width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), sz))
            x = next_x
            line_height = max(line_height, sz.height())

        return y + line_height - rect.y() + m.bottom()
