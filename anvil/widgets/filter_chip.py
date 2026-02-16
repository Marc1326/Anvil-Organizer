"""FilterChip: Toggleable chip button for the filter panel.

Styled via QSS using the object name ``filterChip``.
Active/inactive states use the ``:checked`` / default QSS pseudo-states.
"""

from PySide6.QtWidgets import QPushButton, QSizePolicy
from PySide6.QtCore import QSize, QPoint, Signal, Qt, QTimer

# Kontextmenü-Stylesheet (identisch zu mod_list.py / Paper Dark)
CONTEXT_MENU_STYLE = """
QMenu {
    background: #2b2b2b;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 4px 0;
}
QMenu::item {
    background: transparent;
    padding: 6px 20px;
    color: #e0e0e0;
}
QMenu::item:selected {
    background: #4de0d0;
    color: #1a1a1a;
}
QMenu::item:disabled {
    color: #666666;
}
"""


class FilterChip(QPushButton):
    """A small, checkable chip button representing one filter criterion.

    Category chips (chip_id > 0) support:
      - Right-click context menu (shown directly by chip)
      - Double-click to start inline renaming (handled by parent)
    """

    add_requested = Signal()            # user wants to add a new category
    delete_requested = Signal(int)      # user wants to delete this chip's category
    rename_started = Signal(int, str)   # user double-clicked; (chip_id, current_name)
    context_menu_requested = Signal(int, QPoint)  # chip_id, global_pos (legacy)

    def __init__(self, text: str, chip_id: int = 0, parent=None):
        super().__init__(text, parent)
        self.setObjectName("filterChip")
        self.setCheckable(True)
        self.chip_id = chip_id
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(26)
        # Event zum Parent durchlassen — wird vom _cat_container gehandelt
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

        # Double-click detection: delay toggle to detect double-click
        self._pending_toggle = False
        self._pre_click_state = False
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(200)  # ms to wait for double-click
        self._click_timer.timeout.connect(self._on_click_timer_timeout)

    def contextMenuEvent(self, event):
        # Nicht selbst handlen — an Parent weitergeben
        event.ignore()

    def mousePressEvent(self, event):
        """Store state before click for potential rollback on double-click."""
        if event.button() == Qt.MouseButton.LeftButton and self.chip_id > 0:
            self._pre_click_state = self.isChecked()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Delay toggle for category chips to detect double-click."""
        if event.button() == Qt.MouseButton.LeftButton and self.chip_id > 0:
            # Let QPushButton handle visual feedback but we'll control the actual toggle
            self._pending_toggle = True
            self._click_timer.start()
            # Don't call super - we handle toggle ourselves
            # But we need to release the button visually
            self.setDown(False)
            return
        super().mouseReleaseEvent(event)

    def _on_click_timer_timeout(self):
        """Timer expired - no double-click, perform the toggle now."""
        if self._pending_toggle:
            self._pending_toggle = False
            # Now actually toggle
            new_state = not self._pre_click_state
            self.setChecked(new_state)
            self.toggled.emit(new_state)

    def mouseDoubleClickEvent(self, event):
        if self.chip_id <= 0:
            return super().mouseDoubleClickEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            # Cancel pending toggle - double-click should NOT toggle
            self._click_timer.stop()
            self._pending_toggle = False
            # Restore pre-click state (undo any visual toggle)
            self.setChecked(self._pre_click_state)
            # Emit rename signal
            self.rename_started.emit(self.chip_id, self.text())
        else:
            super().mouseDoubleClickEvent(event)
