"""Mod-Liste (QTreeView) + Filter-Leiste."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeView,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QAbstractItemView,
)
from PySide6.QtCore import Qt

from anvil.models.mod_list_model import ModListModel, COL_NAME


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


class ModListView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tree = QTreeView()
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setSortingEnabled(True)
        self._tree.setUniformRowHeights(True)
        self._model = ModListModel(self)
        self._tree.setModel(self._model)
        self._tree.setColumnWidth(0, 36)
        self._tree.setColumnWidth(1, 200)
        self._tree.setColumnWidth(2, 70)
        self._tree.setColumnWidth(3, 80)
        self._tree.setColumnWidth(4, 90)
        self._tree.setColumnWidth(5, 80)
        self._tree.setColumnWidth(6, 60)
        # MO2: BrowserExtensionFramework vorselektiert (Zeile 5)
        idx = self._model.index(5, 0)
        self._tree.setCurrentIndex(idx)
        layout.addWidget(self._tree)

        filter_row = QHBoxLayout()
        self._filter_left = QLineEdit()
        self._filter_left.setPlaceholderText("Filter")
        self._filter_left.textChanged.connect(lambda t: _todo("Filter")())
        filter_row.addWidget(self._filter_left)
        btn = QPushButton("Keine Gruppen")
        btn.clicked.connect(_todo("Keine Gruppen"))
        filter_row.addWidget(btn)
        self._filter_right = QLineEdit()
        self._filter_right.setPlaceholderText("Filter")
        self._filter_right.textChanged.connect(lambda t: _todo("Filter")())
        filter_row.addWidget(self._filter_right)
        layout.addLayout(filter_row)

    def get_current_mod_name(self):
        """Liefert den Mod-Namen der aktuell gewählten Zeile oder None."""
        idx = self._tree.currentIndex()
        if not idx.isValid() or idx.row() < 0:
            return None
        name = self._model.data(self._model.index(idx.row(), COL_NAME), Qt.ItemDataRole.DisplayRole)
        return name if name is not None else None
