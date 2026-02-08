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
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex

from anvil.models.mod_list_model import ModListModel, COL_NAME


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


class ModListProxyModel(QSortFilterProxyModel):
    """Proxy-Model für Mod-Liste. Qt leitet DnD automatisch ans Source-Model weiter."""
    pass


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
        self._tree.setUniformRowHeights(True)
        self._tree.setDragEnabled(True)
        self._tree.setAcceptDrops(True)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self._tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._tree.setDropIndicatorShown(True)
        self._tree.setDragDropOverwriteMode(False)
        # Source-Model und Proxy-Model für korrektes DnD
        self._source_model = ModListModel(self)
        self._proxy_model = ModListProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)
        self._tree.setModel(self._proxy_model)
        self._tree.header().setSortIndicatorShown(True)
        self._tree.header().setSectionsClickable(True)
        self._tree.header().sortIndicatorChanged.connect(self._proxy_model.sort)
        self._model = self._proxy_model  # Für Kompatibilität
        self._tree.setColumnWidth(0, 36)
        self._tree.setColumnWidth(1, 200)
        self._tree.setColumnWidth(2, 70)
        self._tree.setColumnWidth(3, 80)
        self._tree.setColumnWidth(4, 90)
        self._tree.setColumnWidth(5, 80)
        self._tree.setColumnWidth(6, 60)
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

    def clear_mods(self) -> None:
        """Remove all mods from the list."""
        self._source_model.clear()

    def get_current_mod_name(self):
        """Liefert den Mod-Namen der aktuell gewählten Zeile oder None."""
        proxy_idx = self._tree.currentIndex()
        if not proxy_idx.isValid() or proxy_idx.row() < 0:
            return None
        source_idx = self._proxy_model.mapToSource(proxy_idx)
        name = self._source_model.data(self._source_model.index(source_idx.row(), COL_NAME), Qt.ItemDataRole.DisplayRole)
        return name if name is not None else None
