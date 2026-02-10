"""QAbstractItemModel für Mod-Liste."""

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QMimeData, QByteArray, QDataStream, QIODevice, QSize, Signal
from PySide6.QtGui import QColor, QBrush, QFont

from anvil.core.mod_entry import ModEntry


COL_CHECK, COL_NAME, COL_CONFLICTS, COL_MARKERS, COL_CATEGORY, COL_VERSION, COL_PRIORITY = range(7)
COL_COUNT = 7
HEADERS = ["", "Mod Name", "Konflikte", "Markierungen", "Kategorie", "Version", "Priorität"]
MIME_MOD_ROWS = "application/x-anvil-mod-rows"

# Custom roles
ROLE_IS_SEPARATOR = Qt.ItemDataRole.UserRole + 1
ROLE_FOLDER_NAME = Qt.ItemDataRole.UserRole + 2


class ModRow:
    __slots__ = ("enabled", "name", "conflicts", "markers", "category", "version", "priority", "is_framework", "is_error", "is_separator", "folder_name")

    def __init__(self, enabled, name, conflicts="", markers="", category="", version="", priority=0, is_framework=False, is_error=False, is_separator=False, folder_name=""):
        self.enabled = enabled
        self.name = name
        self.conflicts = conflicts
        self.markers = markers
        self.category = category
        self.version = version
        self.priority = priority
        self.is_framework = is_framework
        self.is_error = is_error
        self.is_separator = is_separator
        self.folder_name = folder_name


def mod_entry_to_row(entry: ModEntry) -> ModRow:
    """Convert a ModEntry (data layer) to a ModRow (view layer)."""
    return ModRow(
        enabled=entry.enabled,
        name=entry.display_name or entry.name,
        conflicts="",
        markers="",
        category=entry.category,
        version=entry.version,
        priority=entry.priority,
        is_framework=entry.is_direct_install,
        is_error=False,
        is_separator=entry.is_separator,
        folder_name=entry.name,
    )


class ModListModel(QAbstractItemModel):
    mod_toggled = Signal(int, bool)   # (source_row, enabled)
    mods_reordered = Signal()         # after drag & drop

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[ModRow] = []
        self._drop_in_progress = False
        self._category_manager = None  # Set by MainWindow

    def set_category_manager(self, manager) -> None:
        """Set CategoryManager reference for resolving category names."""
        self._category_manager = manager

    def clear(self) -> None:
        """Remove all mods from the model."""
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()

    def set_mods(self, mods: list[ModRow]) -> None:
        """Replace all mods with *mods*."""
        self.beginResetModel()
        self._rows = list(mods)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return COL_COUNT

    def index(self, row, column, parent=QModelIndex()):
        if parent.isValid() or row < 0 or row >= len(self._rows):
            return QModelIndex()
        return self.createIndex(row, column)

    def parent(self, index):
        return QModelIndex()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        r = self._rows[index.row()]
        c = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if c == COL_CHECK:
                return ""
            if c == COL_NAME:
                return r.name
            if c == COL_CONFLICTS:
                return r.conflicts
            if c == COL_MARKERS:
                return r.markers
            if c == COL_CATEGORY:
                return self._resolve_category_name(r.category)
            if c == COL_VERSION:
                return r.version
            if c == COL_PRIORITY:
                return str(r.priority)
        if role == Qt.ItemDataRole.SizeHintRole:
            return QSize(0, 28)
        if role == Qt.ItemDataRole.CheckStateRole and c == COL_CHECK:
            if r.is_separator:
                return None  # No checkbox for separators
            return Qt.CheckState.Checked if r.enabled else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if r.is_separator and c == COL_NAME:
                return Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            if c == COL_PRIORITY:
                return Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.FontRole:
            if r.is_separator and c == COL_NAME:
                font = QFont()
                font.setBold(True)
                font.setItalic(True)
                return font
        if role == Qt.ItemDataRole.ToolTipRole:
            if r.is_framework and c == COL_NAME:
                return "Direkt-Install: Wird ins Spielverzeichnis kopiert"
        if role == Qt.ItemDataRole.BackgroundRole:
            if r.is_error:
                return QBrush(QColor("#3a1414"))
            if r.is_framework:
                return QBrush(QColor("#143a14"))
        if role == ROLE_IS_SEPARATOR:
            return r.is_separator
        if role == ROLE_FOLDER_NAME:
            return r.folder_name
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return False
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == COL_CHECK:
            new_enabled = value == Qt.CheckState.Checked.value
            self._rows[index.row()].enabled = new_enabled
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            self.mod_toggled.emit(index.row(), new_enabled)
            return True
        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        f = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled
        r = self._rows[index.row()]
        if index.column() == COL_CHECK and not r.is_separator:
            f |= Qt.ItemFlag.ItemIsUserCheckable
        return f

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction

    def supportedDragActions(self):
        return Qt.DropAction.MoveAction

    def mimeTypes(self):
        return [MIME_MOD_ROWS, "text/uri-list"]

    def mimeData(self, indexes):
        """Beim Drag: Mod-Indices serialisieren."""
        mime = QMimeData()
        rows = sorted(set(idx.row() for idx in indexes if idx.isValid()))
        data = QByteArray()
        stream = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
        for row in rows:
            stream.writeInt32(row)
        mime.setData(MIME_MOD_ROWS, data)
        return mime

    def canDropMimeData(self, data, action, row, column, parent):
        if data.hasFormat(MIME_MOD_ROWS):
            return True
        if data.hasUrls():
            from anvil.core.mod_installer import SUPPORTED_EXTENSIONS
            return any(
                url.toLocalFile().lower().endswith(tuple(SUPPORTED_EXTENSIONS))
                for url in data.urls() if url.isLocalFile()
            )
        return False

    def dropMimeData(self, data, action, row, column, parent):
        """Beim Drop: Zeile verschieben mit beginMoveRows/endMoveRows."""
        if action == Qt.DropAction.IgnoreAction:
            return True
        if not data.hasFormat(MIME_MOD_ROWS):
            return False  # URL-Drops werden von _DropTreeView.dropEvent() behandelt

        # Source-Rows dekodieren
        raw = data.data(MIME_MOD_ROWS)
        stream = QDataStream(raw, QIODevice.OpenModeFlag.ReadOnly)
        source_rows = []
        while not stream.atEnd():
            source_rows.append(stream.readInt32())
        if not source_rows:
            return False

        # Ziel-Position bestimmen
        if row >= 0:
            target = row
        elif parent.isValid():
            target = parent.row()
        else:
            target = self.rowCount()

        source_row = source_rows[0]

        # beginMoveRows gibt False zurück wenn Zeile bereits an der Stelle ist
        p = QModelIndex()
        if source_row < target:
            if not self.beginMoveRows(p, source_row, source_row, p, target):
                return False
            row_data = self._rows.pop(source_row)
            self._rows.insert(target - 1, row_data)
        else:
            if not self.beginMoveRows(p, source_row, source_row, p, target):
                return False
            row_data = self._rows.pop(source_row)
            self._rows.insert(target, row_data)
        self.endMoveRows()

        # Prioritäten neu durchnummerieren
        for i, mod in enumerate(self._rows):
            mod.priority = i
        self.dataChanged.emit(
            self.index(0, COL_PRIORITY),
            self.index(len(self._rows) - 1, COL_PRIORITY),
            [Qt.ItemDataRole.DisplayRole],
        )

        self._drop_in_progress = True
        self.mods_reordered.emit()
        return True

    def removeRows(self, row, count, parent=QModelIndex()):
        """No-Op nach DnD — beginMoveRows hat die Zeile bereits verschoben."""
        if self._drop_in_progress:
            self._drop_in_progress = False
            return True
        return False

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return None
        if 0 <= section < len(HEADERS):
            return HEADERS[section]
        return None

    def _resolve_category_name(self, raw_category: str) -> str:
        """Resolve comma-separated category IDs to primary category name."""
        if not raw_category or not self._category_manager:
            return raw_category
        # Primary category = first ID in list
        first = raw_category.split(",")[0].strip()
        try:
            cat_id = int(first)
            if cat_id > 0:
                name = self._category_manager.get_name(cat_id)
                if name:
                    return name
        except ValueError:
            pass
        return raw_category

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        self.layoutAboutToBeChanged.emit()
        rev = order == Qt.SortOrder.DescendingOrder
        if column == COL_NAME:
            self._rows.sort(key=lambda x: x.name.lower(), reverse=rev)
        elif column == COL_PRIORITY:
            self._rows.sort(key=lambda x: x.priority, reverse=rev)
        elif column == COL_VERSION:
            self._rows.sort(key=lambda x: x.version, reverse=rev)
        elif column == COL_CATEGORY:
            self._rows.sort(key=lambda x: self._resolve_category_name(x.category).lower(), reverse=rev)
        self.layoutChanged.emit()
