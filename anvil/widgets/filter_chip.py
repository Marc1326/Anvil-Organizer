"""FilterChip: Toggleable chip button for the filter panel.

Styled via QSS using the object name ``filterChip``.
Active/inactive states use the ``:checked`` / default QSS pseudo-states.
"""

from PySide6.QtWidgets import QPushButton, QSizePolicy
from PySide6.QtCore import QSize, QPoint, Signal, Qt

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

    def contextMenuEvent(self, event):
        # Nicht selbst handlen — an Parent weitergeben
        event.ignore()

    def mouseDoubleClickEvent(self, event):
        if self.chip_id <= 0:
            return super().mouseDoubleClickEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.rename_started.emit(self.chip_id, self.text())
        else:
            super().mouseDoubleClickEvent(event)
