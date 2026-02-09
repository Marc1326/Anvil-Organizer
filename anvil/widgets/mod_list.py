"""Mod-Liste (QTreeView) + Filter-Leiste."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeView,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QAbstractItemView,
    QStyledItemDelegate,
    QHeaderView,
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex, QSize, QRect, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

from anvil.core.mod_installer import SUPPORTED_EXTENSIONS
from anvil.models.mod_list_model import ModListModel, COL_CHECK, COL_NAME


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


class CheckboxDelegate(QStyledItemDelegate):
    """Custom delegate for COL_CHECK: green circle+check (enabled), gray circle (disabled)."""

    _COLOR_ON = QColor("#4CAF50")
    _COLOR_OFF = QColor("#666666")

    def paint(self, painter: QPainter, option, index):
        # Draw background (selection, alternating rows)
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else None
        if style:
            style.drawPrimitive(style.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)

        check = index.data(Qt.ItemDataRole.CheckStateRole)
        enabled = check == Qt.CheckState.Checked

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Center a 16x16 icon area in the cell
        size = 16
        x = option.rect.x() + (option.rect.width() - size) // 2
        y = option.rect.y() + (option.rect.height() - size) // 2
        rect = QRect(x, y, size, size)

        if enabled:
            # Filled green circle
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._COLOR_ON))
            painter.drawEllipse(rect)
            # White checkmark
            painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
            painter.drawLine(x + 3, y + 8, x + 6, y + 12)
            painter.drawLine(x + 6, y + 12, x + 12, y + 4)
        else:
            # Empty gray circle
            painter.setPen(QPen(self._COLOR_OFF, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(36, 28)

    def editorEvent(self, event, model, option, index):
        if event.type() in (event.Type.MouseButtonRelease, event.Type.MouseButtonDblClick):
            current = index.data(Qt.ItemDataRole.CheckStateRole)
            new_val = Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
            model.setData(index, new_val.value, Qt.ItemDataRole.CheckStateRole)
            return True
        return False


class ModListProxyModel(QSortFilterProxyModel):
    """Proxy-Model für Mod-Liste. Qt leitet DnD automatisch ans Source-Model weiter."""
    pass


class _DropTreeView(QTreeView):
    """QTreeView that accepts external archive file drops in addition to internal DnD."""

    archives_dropped = Signal(list)  # list of file path strings

    def dragEnterEvent(self, event):
        super().dragEnterEvent(event)
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if any(path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                        event.acceptProposedAction()
                        return

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if any(path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                        paths.append(path)
            if paths:
                event.acceptProposedAction()
                self.archives_dropped.emit(paths)
                return
        # Internal DnD (mod reorder)
        super().dropEvent(event)


class ModListView(QWidget):
    archives_dropped = Signal(list)  # forwarded from _DropTreeView
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tree = _DropTreeView()
        self._tree.archives_dropped.connect(self.archives_dropped)
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
        # Custom delegate for checkbox column
        self._check_delegate = CheckboxDelegate(self._tree)
        self._tree.setItemDelegateForColumn(COL_CHECK, self._check_delegate)
        # Column widths — all Interactive (resizable by mouse)
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setCascadingSectionResizes(True)
        header.setMinimumSectionSize(30)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_CHECK, QHeaderView.ResizeMode.Fixed)
        self._tree.setColumnWidth(COL_CHECK, 36)
        self._tree.setColumnWidth(COL_NAME, 300)
        self._tree.setColumnWidth(2, 80)
        self._tree.setColumnWidth(3, 80)
        self._tree.setColumnWidth(4, 100)
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

    def source_model(self) -> ModListModel:
        """Return the underlying ModListModel."""
        return self._source_model

    def clear_mods(self) -> None:
        """Remove all mods from the list."""
        self._source_model.clear()

    def header(self) -> QHeaderView:
        """Return the tree header for state save/restore."""
        return self._tree.header()

    def get_current_mod_name(self):
        """Liefert den Mod-Namen der aktuell gewählten Zeile oder None."""
        proxy_idx = self._tree.currentIndex()
        if not proxy_idx.isValid() or proxy_idx.row() < 0:
            return None
        source_idx = self._proxy_model.mapToSource(proxy_idx)
        name = self._source_model.data(self._source_model.index(source_idx.row(), COL_NAME), Qt.ItemDataRole.DisplayRole)
        return name if name is not None else None
