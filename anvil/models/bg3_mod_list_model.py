"""QAbstractItemModel for the BG3 mod list (active / inactive)."""

from __future__ import annotations

import os

from PySide6.QtCore import (
    QAbstractItemModel,
    QByteArray,
    QModelIndex,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QIcon

from anvil.core.translator import tr
from anvil.core.resource_path import get_anvil_base

# ── Conflict icons (reuse from standard model) ──────────────────────

_ICON_DIR = str(get_anvil_base() / "styles" / "icons" / "conflicts")
_CONFLICT_ICONS: dict[str, QIcon] = {}


def _get_conflict_icon(conflict_type: str) -> QIcon | None:
    if conflict_type not in ("win", "lose", "both"):
        return None
    if conflict_type not in _CONFLICT_ICONS:
        path = os.path.join(_ICON_DIR, f"conflict_{conflict_type}.svg")
        if os.path.isfile(path):
            _CONFLICT_ICONS[conflict_type] = QIcon(path)
        else:
            return None
    return _CONFLICT_ICONS.get(conflict_type)


# ── Column definitions ───────────────────────────────────────────────

COL_CHECK, COL_NAME, COL_CONFLICTS, COL_VERSION, COL_AUTHOR = range(5)
COL_COUNT = 5
HEADERS = [" ", "Mod Name", "Konflikte", "Version", "Author"]
MIME_BG3_MOD_ROWS = "application/x-anvil-bg3-mod-rows"

# Custom roles
ROLE_UUID = Qt.ItemDataRole.UserRole + 10
ROLE_FILENAME = Qt.ItemDataRole.UserRole + 11


# ── Data row ─────────────────────────────────────────────────────────

class BG3ModRow:
    """View-layer data for a single BG3 mod entry."""

    __slots__ = (
        "uuid", "name", "folder", "author", "version", "filename",
        "enabled", "conflicts", "dependencies", "source",
    )

    def __init__(
        self,
        uuid: str = "",
        name: str = "",
        folder: str = "",
        author: str = "",
        version: str = "",
        filename: str = "",
        enabled: bool = True,
        conflicts: str | dict = "",
        dependencies: list | None = None,
        source: str = "",
    ):
        self.uuid = uuid
        self.name = name
        self.folder = folder
        self.author = author
        self.version = version
        self.filename = filename
        self.enabled = enabled
        self.conflicts = conflicts
        self.dependencies = dependencies or []
        self.source = source


# ── Model ────────────────────────────────────────────────────────────

class BG3ModListModel(QAbstractItemModel):
    """Model for one half (active or inactive) of the BG3 mod list.

    When *allow_reorder* is True, internal drag-and-drop reordering
    is supported.  When False, only selection and checkbox toggling
    work.
    """

    mod_toggled = Signal(int, bool)  # (row, new_enabled)
    mods_reordered = Signal()        # after internal DnD

    def __init__(self, allow_reorder: bool = False, parent=None):
        super().__init__(parent)
        self._rows: list[BG3ModRow] = []
        self._allow_reorder = allow_reorder
        self._drop_in_progress = False

    # ── Public API ─────────────────────────────────────────────────

    def set_mods(self, mods: list[BG3ModRow]) -> None:
        self.beginResetModel()
        self._rows = list(mods)
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()

    def get_uuid_order(self) -> list[str]:
        """Return current UUID ordering (all mods)."""
        return [r.uuid for r in self._rows]

    def get_active_uuid_order(self) -> list[str]:
        """Return UUID ordering of enabled mods only."""
        return [r.uuid for r in self._rows if r.enabled]

    def row_data(self, row: int) -> BG3ModRow | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    # ── QAbstractItemModel interface ───────────────────────────────

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

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
            if c == COL_CONFLICTS:
                return ""
            if c == COL_NAME:
                return r.name
            if c == COL_VERSION:
                return r.version
            if c == COL_AUTHOR:
                return r.author

        if role == Qt.ItemDataRole.DecorationRole and c == COL_CONFLICTS:
            if isinstance(r.conflicts, dict):
                return _get_conflict_icon(r.conflicts.get("type", ""))

        if role == Qt.ItemDataRole.SizeHintRole:
            return QSize(0, 28)

        if role == Qt.ItemDataRole.CheckStateRole and c == COL_CHECK:
            return Qt.CheckState.Checked if r.enabled else Qt.CheckState.Unchecked

        if role == Qt.ItemDataRole.ToolTipRole:
            if c == COL_CONFLICTS and isinstance(r.conflicts, dict):
                ctype = r.conflicts.get("type", "")
                wins = r.conflicts.get("wins", 0)
                losses = r.conflicts.get("losses", 0)
                win_mods = r.conflicts.get("win_mods", 0)
                lose_mods = r.conflicts.get("lose_mods", 0)
                if ctype == "win":
                    return tr("tooltip.conflict_overwrites", wins=wins, win_mods=win_mods)
                if ctype == "lose":
                    return tr("tooltip.conflict_overwritten", losses=losses, lose_mods=lose_mods)
                if ctype == "both":
                    return tr("tooltip.conflict_both", wins=wins, losses=losses)
            if c == COL_NAME and r.dependencies:
                dep_names = [d.get("name", d.get("uuid", "?")) for d in r.dependencies]
                return tr("tooltip.dependencies", deps=", ".join(dep_names))

        if role == ROLE_UUID:
            return r.uuid
        if role == ROLE_FILENAME:
            return r.filename

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
        f = (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsDragEnabled  # both models support drag
        )
        if index.column() == COL_CHECK:
            f |= Qt.ItemFlag.ItemIsUserCheckable
        return f

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return None
        # Headers mit tr() zur Laufzeit übersetzen
        headers = [
            " ",
            tr("label.header_mod_name"),
            tr("label.header_conflicts"),
            tr("label.header_version"),
            tr("label.header_author"),
        ]
        if 0 <= section < len(headers):
            return headers[section]
        return None

    # ── Drag & Drop (reorder only) ────────────────────────────────

    def supportedDropActions(self):
        # Both models must accept MoveAction for cross-tree DnD to work.
        # The view handles cross-tree drops; the model handles internal reorder.
        return Qt.DropAction.MoveAction

    def supportedDragActions(self):
        return Qt.DropAction.MoveAction  # both models support drag

    def mimeTypes(self):
        return [MIME_BG3_MOD_ROWS]

    def mimeData(self, indexes):
        from PySide6.QtCore import QMimeData
        mime = QMimeData()
        rows = sorted(set(idx.row() for idx in indexes if idx.isValid()))
        uuids = [self._rows[r].uuid for r in rows if 0 <= r < len(self._rows)]
        mime.setData(MIME_BG3_MOD_ROWS, QByteArray("\n".join(uuids).encode("utf-8")))
        return mime

    def canDropMimeData(self, data, action, row, column, parent):
        return data.hasFormat(MIME_BG3_MOD_ROWS) or data.hasUrls()

    def dropMimeData(self, data, action, row, column, parent):
        if action == Qt.DropAction.IgnoreAction:
            return True
        if not self._allow_reorder or not data.hasFormat(MIME_BG3_MOD_ROWS):
            return False

        raw = bytes(data.data(MIME_BG3_MOD_ROWS))
        uuids = [u for u in raw.decode("utf-8").split("\n") if u]
        if not uuids:
            return False

        # Find source row by UUID
        uuid = uuids[0]
        source_row = None
        for i, r in enumerate(self._rows):
            if r.uuid == uuid:
                source_row = i
                break
        if source_row is None:
            return False  # UUID not in this model (cross-tree handled by view)

        if row >= 0:
            target = row
        elif parent.isValid():
            target = parent.row()
        else:
            target = self.rowCount()

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

        self._drop_in_progress = True
        self.mods_reordered.emit()
        return True

    def removeRows(self, row, count, parent=QModelIndex()):
        """No-Op nach DnD — beginMoveRows hat die Zeile bereits verschoben.

        MUST return False so QSortFilterProxyModel does NOT call
        beginRemoveRows/endRemoveRows (which would hide rows from the view
        even though the source model still contains them).
        """
        if self._drop_in_progress:
            self._drop_in_progress = False
        return False

    # ── Sorting ────────────────────────────────────────────────────

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        if self._allow_reorder:
            return  # Active list: keep load order, no column sort
        self.layoutAboutToBeChanged.emit()
        rev = order == Qt.SortOrder.DescendingOrder
        if column == COL_NAME:
            self._rows.sort(key=lambda x: x.name.lower(), reverse=rev)
        elif column == COL_VERSION:
            self._rows.sort(key=lambda x: x.version, reverse=rev)
        elif column == COL_AUTHOR:
            self._rows.sort(key=lambda x: x.author.lower(), reverse=rev)
        self.layoutChanged.emit()
