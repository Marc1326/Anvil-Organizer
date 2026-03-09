"""QAbstractItemModel für Mod-Liste."""

import os

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QMimeData, QByteArray, QDataStream, QIODevice, QSize, Signal
from PySide6.QtGui import QColor, QBrush, QFont, QIcon

from anvil.core.mod_entry import ModEntry
from anvil.core.translator import tr
from anvil.core.resource_path import get_anvil_base

# Conflict icon paths (resolved once)
_ICON_DIR = str(get_anvil_base() / "styles" / "icons" / "conflicts")
_CONFLICT_ICONS: dict[str, QIcon] = {}


def _get_conflict_icon(conflict_type: str) -> QIcon | None:
    """Return cached QIcon for conflict type ('win', 'lose', 'both')."""
    if conflict_type not in ("win", "lose", "both"):
        return None
    if conflict_type not in _CONFLICT_ICONS:
        path = os.path.join(_ICON_DIR, f"conflict_{conflict_type}.svg")
        if os.path.isfile(path):
            _CONFLICT_ICONS[conflict_type] = QIcon(path)
        else:
            return None
    return _CONFLICT_ICONS.get(conflict_type)


COL_CHECK, COL_NAME, COL_CONFLICTS, COL_MARKERS, COL_CATEGORY, COL_VERSION, COL_PRIORITY = range(7)
COL_COUNT = 7
HEADERS = ["", "Mod Name", "Konflikte", "Markierungen", "Kategorie", "Version", "Priorität"]
MIME_MOD_ROWS = "application/x-anvil-mod-rows"

# Custom roles
ROLE_IS_SEPARATOR = Qt.ItemDataRole.UserRole + 1
ROLE_FOLDER_NAME = Qt.ItemDataRole.UserRole + 2
ROLE_IS_COLLAPSED = Qt.ItemDataRole.UserRole + 3  # Whether separator is collapsed (set by view)
ROLE_SEP_COLOR = Qt.ItemDataRole.UserRole + 4     # Separator color string (hex, e.g. "#FF0000")


class ModRow:
    __slots__ = ("enabled", "name", "conflicts", "markers", "category", "version", "priority", "is_framework", "is_error", "is_separator", "folder_name", "color", "file_count")

    def __init__(self, enabled, name, conflicts="", markers="", category="", version="", priority=0, is_framework=False, is_error=False, is_separator=False, folder_name="", color="", file_count=0):
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
        self.color = color
        self.file_count = file_count


def mod_entry_to_row(entry: ModEntry, conflict_data: dict | None = None) -> ModRow:
    """Convert a ModEntry (data layer) to a ModRow (view layer).

    Args:
        entry: The mod entry from the data layer.
        conflict_data: Optional dict mapping mod folder names to conflict
            info dicts with keys: type, wins, losses, win_mods, lose_mods.
    """
    conflicts = ""
    if conflict_data and entry.name in conflict_data:
        conflicts = conflict_data[entry.name]
    return ModRow(
        enabled=entry.enabled,
        name=entry.display_name or entry.name,
        conflicts=conflicts,
        markers="",
        category=entry.category,
        version=entry.version,
        priority=entry.priority,
        is_framework=entry.is_direct_install,
        is_error=False,
        is_separator=entry.is_separator,
        folder_name=entry.name,
        color=entry.color,
        file_count=getattr(entry, "file_count", 0),
    )


class ModListModel(QAbstractItemModel):
    mod_toggled = Signal(int, bool)   # (source_row, enabled)
    mods_reordered = Signal()         # after drag & drop

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[ModRow] = []
        self._drop_in_progress = False
        self._category_manager = None  # Set by MainWindow

        # ── Settings flags (set by mainwindow._apply_modlist_settings) ──
        self._conflicts_on_separator: bool = False    # Setting 5
        self._symbol_conflicts: bool = False           # Setting 7
        self._symbol_flags: bool = False               # Setting 8
        self._symbol_content: bool = False             # Setting 9
        self._symbol_version: bool = False             # Setting 10

        # ── Highlighting for "Konflikte VON Trenner" (Setting 6) ──
        self._highlighted_rows: set[int] = set()       # Source row indices to highlight
        self._highlight_color: QColor = QColor("#3a2a14")  # Warm orange-brown tint

        # ── Conflict highlighting for selected mod ──
        self._conflict_win_rows: set[int] = set()       # Green (selected wins)
        self._conflict_lose_rows: set[int] = set()      # Red (selected loses)
        self._conflict_win_color = QColor("#1a3a1a")
        self._conflict_lose_color = QColor("#3a1a1a")

        # ── Collapsed separators reference (set by view) ──
        self._collapsed_separators: set[str] = set()

    def set_category_manager(self, manager) -> None:
        """Set CategoryManager reference for resolving category names."""
        self._category_manager = manager

    def set_highlighted_rows(self, rows: set[int]) -> None:
        """Set which source rows should be highlighted (Setting 6: conflicts from separator).

        Emits dataChanged for the full range so the view repaints.
        """
        old = self._highlighted_rows
        self._highlighted_rows = rows
        # Notify view about changed rows (union of old and new)
        changed = old | rows
        if changed and self._rows:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._rows) - 1, COL_COUNT - 1),
                [Qt.ItemDataRole.BackgroundRole],
            )

    def set_conflict_highlight(self, win_rows: set[int], lose_rows: set[int]) -> None:
        """Highlight conflict partners of the selected mod."""
        old = self._conflict_win_rows | self._conflict_lose_rows
        self._conflict_win_rows = win_rows
        self._conflict_lose_rows = lose_rows
        changed = old | win_rows | lose_rows
        if changed and self._rows:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._rows) - 1, COL_COUNT - 1),
                [Qt.ItemDataRole.BackgroundRole],
            )

    def _is_separator_collapsed(self, folder_name: str) -> bool:
        """Check if a separator is currently collapsed."""
        return folder_name in self._collapsed_separators

    def _get_separator_children(self, sep_row: int) -> list[int]:
        """Return list of source row indices that belong to the separator at sep_row.

        Children are all non-separator rows after sep_row until the next separator
        or end of list.
        """
        children = []
        for i in range(sep_row + 1, len(self._rows)):
            if self._rows[i].is_separator:
                break
            children.append(i)
        return children

    def _aggregate_separator_conflicts(self, sep_row: int) -> int:
        """Count total conflicts among children of separator at sep_row."""
        count = 0
        for child_row in self._get_separator_children(sep_row):
            r = self._rows[child_row]
            if isinstance(r.conflicts, dict) and r.conflicts.get("type", ""):
                count += 1
        return count

    def _any_child_has_conflicts(self, sep_row: int) -> bool:
        """Check if any child of separator has conflicts."""
        for child_row in self._get_separator_children(sep_row):
            r = self._rows[child_row]
            if isinstance(r.conflicts, dict) and r.conflicts.get("type", ""):
                return True
        return False

    def _any_child_has_markers(self, sep_row: int) -> bool:
        """Check if any child of separator has markers/flags."""
        for child_row in self._get_separator_children(sep_row):
            r = self._rows[child_row]
            if r.markers:
                return True
        return False

    def _any_child_has_version(self, sep_row: int) -> bool:
        """Check if any child of separator has a non-empty version."""
        for child_row in self._get_separator_children(sep_row):
            r = self._rows[child_row]
            if r.version:
                return True
        return False

    def _any_child_has_content(self, sep_row: int) -> bool:
        """Check if any child of separator has actual file content."""
        for child_row in self._get_separator_children(sep_row):
            r = self._rows[child_row]
            if r.file_count > 0:
                return True
        return False

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
                # Setting 5: Show aggregated conflict count on collapsed separators
                if r.is_separator and self._conflicts_on_separator and self._is_separator_collapsed(r.folder_name):
                    count = self._aggregate_separator_conflicts(index.row())
                    if count > 0:
                        return str(count)
                return ""  # Icon only, no text
            if c == COL_MARKERS:
                return r.markers
            if c == COL_CATEGORY:
                return self._resolve_category_name(r.category)
            if c == COL_VERSION:
                return r.version
            if c == COL_PRIORITY:
                return str(r.priority)
        if role == Qt.ItemDataRole.DecorationRole:
            # Normal mod conflict icons
            if c == COL_CONFLICTS and not r.is_separator:
                if isinstance(r.conflicts, dict):
                    return _get_conflict_icon(r.conflicts.get("type", ""))
            # Separator symbol icons (only when collapsed)
            if r.is_separator and self._is_separator_collapsed(r.folder_name):
                row_idx = index.row()
                # Setting 5 + 7: Conflict symbol on separator
                if c == COL_CONFLICTS:
                    if (self._conflicts_on_separator or self._symbol_conflicts) and self._any_child_has_conflicts(row_idx):
                        return _get_conflict_icon("both")  # Generic warning icon
                # Setting 8: Flags/markers symbol on separator
                if c == COL_MARKERS and self._symbol_flags:
                    if self._any_child_has_markers(row_idx):
                        return QIcon.fromTheme("flag")  # System theme fallback
                # Setting 9: Content symbol on separator (category column as proxy)
                if c == COL_CATEGORY and self._symbol_content:
                    if self._any_child_has_content(row_idx):
                        return QIcon.fromTheme("document-open")
                # Setting 10: Version symbol on separator
                if c == COL_VERSION and self._symbol_version:
                    if self._any_child_has_version(row_idx):
                        return QIcon.fromTheme("software-update-available")
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
            if c == COL_CONFLICTS:
                # Setting 5: Tooltip for separator showing aggregated conflict count
                if r.is_separator and self._conflicts_on_separator and self._is_separator_collapsed(r.folder_name):
                    count = self._aggregate_separator_conflicts(index.row())
                    if count > 0:
                        return f"{count} Mod(s) with conflicts"
                # Normal mod conflict tooltip
                if isinstance(r.conflicts, dict):
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
            if r.is_framework and c == COL_NAME:
                return tr("tooltip.direct_install")
        if role == Qt.ItemDataRole.BackgroundRole:
            row_idx = index.row()
            # Conflict highlighting (highest priority for temp highlights)
            # Lose (rot) hat Vorrang vor Win (grün) — Warnung > Erfolg
            if row_idx in self._conflict_lose_rows:
                return QBrush(self._conflict_lose_color)
            if row_idx in self._conflict_win_rows:
                return QBrush(self._conflict_win_color)
            # Setting 6: Highlight mods that conflict with selected separator's children
            if row_idx in self._highlighted_rows:
                return QBrush(self._highlight_color)
            # Separator custom background color (from meta.ini, dampened with alpha ~80)
            if r.is_separator and r.color:
                c = QColor(r.color)
                if c.isValid():
                    c.setAlpha(80)
                    return QBrush(c)
            if r.is_error:
                return QBrush(QColor("#3a1414"))
            if r.is_framework:
                return QBrush(QColor("#143a14"))
        if role == ROLE_IS_SEPARATOR:
            return r.is_separator
        if role == ROLE_FOLDER_NAME:
            return r.folder_name
        if role == ROLE_SEP_COLOR:
            return r.color if r.is_separator else ""
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
        """Beim Drop: Zeile verschieben mit beginMoveRows/endMoveRows.

        Wenn ein Separator verschoben wird, werden alle Mods zwischen
        diesem Separator und dem nächsten Separator (oder Listenende)
        als Block mitgenommen.
        """
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

        if len(source_rows) == 1:
            source_row = source_rows[0]
            if self._rows[source_row].is_separator:
                return self._move_separator_block(source_row, target)
            return self._move_single_row(source_row, target)
        else:
            # Mehrfachauswahl: Separatoren herausfiltern, nur Mods verschieben
            mod_rows = [r for r in source_rows if not self._rows[r].is_separator]
            if not mod_rows:
                return False
            return self._move_multiple_rows(mod_rows, target)

    def _move_single_row(self, source_row: int, target: int) -> bool:
        """Verschiebt eine einzelne Zeile."""
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
        self._update_priorities()
        return True

    def _move_multiple_rows(self, source_rows: list[int], target: int) -> bool:
        """Verschiebt mehrere nicht-zusammenhängende Zeilen an die Zielposition.

        Die relative Reihenfolge der selektierten Mods bleibt erhalten.
        Separatoren müssen vorher herausgefiltert worden sein.
        """
        if not source_rows:
            return False

        sorted_rows = sorted(source_rows)

        # Extrahiere die ModRows in Originalreihenfolge
        extracted = [self._rows[r] for r in sorted_rows]

        self.layoutAboutToBeChanged.emit()

        # Von hinten nach vorne entfernen damit Indizes stabil bleiben
        for r in reversed(sorted_rows):
            del self._rows[r]

        # Target-Position anpassen: für jeden entfernten Row < target, eins abziehen
        adjusted_target = target
        for r in sorted_rows:
            if r < target:
                adjusted_target -= 1

        # An angepasster Position einfügen (Originalreihenfolge)
        for i, row_data in enumerate(extracted):
            self._rows.insert(adjusted_target + i, row_data)

        self.layoutChanged.emit()
        self._update_priorities()
        return True

    def _move_separator_block(self, source_row: int, target: int) -> bool:
        """Verschiebt einen Separator mit allen zugehörigen Mods als Block.

        Der Block umfasst den Separator und alle Mods bis zum nächsten
        Separator (oder Listenende).
        """
        # Ende des Blocks finden (nächster Separator oder Listenende)
        end_row = source_row + 1
        while end_row < len(self._rows) and not self._rows[end_row].is_separator:
            end_row += 1

        block_size = end_row - source_row

        # Keine Verschiebung nötig wenn Block bereits an Zielposition
        if target >= source_row and target <= end_row:
            return False

        p = QModelIndex()

        # Block extrahieren
        block = self._rows[source_row:end_row]

        if source_row < target:
            # Nach UNTEN verschieben
            # Zielposition korrigieren: Nach Entfernen des Blocks verschiebt sich alles
            adjusted_target = target - block_size

            # beginMoveRows für den gesamten Block
            if not self.beginMoveRows(p, source_row, end_row - 1, p, target):
                return False

            # Block entfernen und an neuer Position einfügen
            del self._rows[source_row:end_row]
            for i, row_data in enumerate(block):
                self._rows.insert(adjusted_target + i, row_data)
        else:
            # Nach OBEN verschieben
            if not self.beginMoveRows(p, source_row, end_row - 1, p, target):
                return False

            # Block entfernen und an neuer Position einfügen
            del self._rows[source_row:end_row]
            for i, row_data in enumerate(block):
                self._rows.insert(target + i, row_data)

        self.endMoveRows()
        self._update_priorities()
        return True

    def _update_priorities(self) -> None:
        """Prioritäten neu durchnummerieren und Signal emittieren."""
        for i, mod in enumerate(self._rows):
            mod.priority = i
        self.dataChanged.emit(
            self.index(0, COL_PRIORITY),
            self.index(len(self._rows) - 1, COL_PRIORITY),
            [Qt.ItemDataRole.DisplayRole],
        )
        self._drop_in_progress = True
        self.mods_reordered.emit()

    def removeRows(self, row, count, parent=QModelIndex()):
        """No-Op nach DnD — beginMoveRows hat die Zeile bereits verschoben.

        MUST return False so QSortFilterProxyModel does NOT call
        beginRemoveRows/endRemoveRows (which would hide rows from the view
        even though the source model still contains them).
        """
        if self._drop_in_progress:
            self._drop_in_progress = False
        return False

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal or role != Qt.ItemDataRole.DisplayRole:
            return None
        # Headers mit tr() zur Laufzeit übersetzen
        headers = [
            "",
            tr("label.header_mod_name"),
            tr("label.header_conflicts"),
            tr("label.header_markers"),
            tr("label.header_category"),
            tr("label.header_version"),
            tr("label.header_priority"),
        ]
        if 0 <= section < len(headers):
            return headers[section]
        return None

    def _resolve_category_name(self, raw_category: str) -> str:
        """Resolve comma-separated category IDs to primary category name."""
        if not raw_category or not self._category_manager:
            return ""
        # Primary category = first ID in list
        first = raw_category.split(",")[0].strip()
        try:
            cat_id = int(first)
            if cat_id <= 0:
                return ""  # Keine Kategorie zugewiesen
            name = self._category_manager.get_name(cat_id)
            return name if name else ""
        except ValueError:
            return ""

    def get_all_separators(self) -> list[tuple[int, str, str]]:
        """Return list of (source_row, folder_name, display_name) for all separators."""
        result = []
        for i, row in enumerate(self._rows):
            if row.is_separator:
                result.append((i, row.folder_name, row.name))
        return result

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
