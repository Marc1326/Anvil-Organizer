"""QAbstractItemModel für Mod-Liste mit 20 Dummy-Mods."""

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QMimeData, QByteArray, QDataStream, QIODevice
from PySide6.QtGui import QColor, QBrush


COL_CHECK, COL_NAME, COL_CONFLICTS, COL_MARKERS, COL_CATEGORY, COL_VERSION, COL_PRIORITY = range(7)
COL_COUNT = 7
HEADERS = ["", "Mod Name", "Konflikte", "Markierungen", "Kategorie", "Version", "Priorität"]
MIME_MOD_ROWS = "application/x-anvil-mod-rows"


class ModRow:
    __slots__ = ("enabled", "name", "conflicts", "markers", "category", "version", "priority", "is_framework", "is_error")

    def __init__(self, enabled, name, conflicts="", markers="", category="", version="", priority=0, is_framework=False, is_error=False):
        self.enabled = enabled
        self.name = name
        self.conflicts = conflicts
        self.markers = markers
        self.category = category
        self.version = version
        self.priority = priority
        self.is_framework = is_framework
        self.is_error = is_error


def _dummy_mods():
    return [
        ModRow(True, "Limited HUD", "", "✓", "UI", "1.0", 10),
        ModRow(True, "Realistic Map 4K", "⚠", "", "Maps", "1.4.5", 15),
        ModRow(True, "SkyUI", "", "✓", "UI", "5.2", 16),
        ModRow(True, "SKSE64", "", "", "Framework", "2.0.20", 20, is_framework=True),
        ModRow(True, "Unofficial Patch", "", "✓", "Bugfix", "4.2.5", 25),
        ModRow(True, "BrowserExtensionFramework", "", "✓", "Framework", "1.4c", 27, is_framework=True),
        ModRow(True, "Preem Menu (No Blur)", "", "", "UI", "2.0", 28),
        ModRow(True, "Smarter Scrapper", "⚠", "⚠", "Gameplay", "11/25/...", 35, is_error=True),
        ModRow(True, "3D World Map Explorer", "", "", "Maps", "1.1", 36),
        ModRow(True, "Equipment-EX", "", "", "Gameplay", "2.2.1", 38),
        ModRow(True, "ENBSeries", "", "", "Visuals", "0.488", 40),
        ModRow(True, "Immersive Armors", "", "✓", "Equipment", "8.1", 42),
        ModRow(True, "Mod Settings Patch", "", "", "Tweaks", "1.1", 44),
        ModRow(True, "Conflict Begone", "", "", "Tweaks", "1.0", 46),
        ModRow(True, "Load Begone", "", "", "Tweaks", "1.2", 48, is_error=True),
        ModRow(True, "BetterLootMarkers", "", "", "UI", "1.0", 50),
        ModRow(True, "Stand Still Please", "", "", "Tweaks", "1.0", 52),
        ModRow(True, "Status Bar Bug Fixes", "", "", "Bugfix", "1.1", 54),
        ModRow(True, "Survival System", "", "", "Gameplay", "2.0", 56),
        ModRow(True, "Custom Quickslots", "", "", "UI", "1.3", 58),
    ]


class ModListModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = _dummy_mods()
        self._drop_in_progress = False

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
                return r.category
            if c == COL_VERSION:
                return r.version
            if c == COL_PRIORITY:
                return str(r.priority) if r.priority else ""
        if role == Qt.ItemDataRole.CheckStateRole and c == COL_CHECK:
            return Qt.CheckState.Checked if r.enabled else Qt.CheckState.Unchecked
        if role == Qt.ItemDataRole.TextAlignmentRole and c == COL_PRIORITY:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.BackgroundRole:
            if r.is_error:
                return QBrush(QColor("#3a1414"))
            if r.is_framework:
                return QBrush(QColor("#143a14"))
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return False
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == COL_CHECK:
            self._rows[index.row()].enabled = value == Qt.CheckState.Checked.value
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True
        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        f = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled
        if index.column() == COL_CHECK:
            f |= Qt.ItemFlag.ItemIsUserCheckable
        return f

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction

    def supportedDragActions(self):
        return Qt.DropAction.MoveAction

    def mimeTypes(self):
        return [MIME_MOD_ROWS]

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
        return data.hasFormat(MIME_MOD_ROWS)

    def dropMimeData(self, data, action, row, column, parent):
        """Beim Drop: Zeile verschieben mit beginMoveRows/endMoveRows."""
        if action == Qt.DropAction.IgnoreAction:
            return True
        if not data.hasFormat(MIME_MOD_ROWS):
            return False

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
            self._rows.sort(key=lambda x: x.category.lower(), reverse=rev)
        self.layoutChanged.emit()
