"""FilterChip: Toggleable chip button for the filter panel.

Styled via QSS using the object name ``filterChip``.
Active/inactive states use the ``:checked`` / default QSS pseudo-states.
"""

from PySide6.QtWidgets import QPushButton, QSizePolicy
from PySide6.QtCore import QSize


class FilterChip(QPushButton):
    """A small, checkable chip button representing one filter criterion."""

    def __init__(self, text: str, chip_id: int = 0, parent=None):
        super().__init__(text, parent)
        self.setObjectName("filterChip")
        self.setCheckable(True)
        self.chip_id = chip_id
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(26)
