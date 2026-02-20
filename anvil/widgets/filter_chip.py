"""FilterChip: Toggleable chip button for the filter panel.

Styled via QSS using the object name ``filterChip``.
Active/inactive states use the ``:checked`` / default QSS pseudo-states.
"""

from PySide6.QtWidgets import QPushButton, QSizePolicy
from PySide6.QtCore import Qt

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
    """A small, checkable chip button representing one filter criterion."""

    def __init__(self, text: str, chip_id: int = 0, parent=None):
        super().__init__(text, parent)
        self.setObjectName("filterChip")
        self.setCheckable(True)
        self.chip_id = chip_id
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(26)
        # Kontextmenü wird vom Parent (_cat_container) gehandelt
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
