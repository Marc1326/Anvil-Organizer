"""Mod-Liste (QTreeView) + Filter-Leiste."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QSplitter,
    QAbstractItemView,
    QStyledItemDelegate,
    QHeaderView,
    QScrollBar,
    QStyleOptionSlider,
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex, QSize, QRect, Signal, QPoint, QTimer, QItemSelection
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

from anvil.core.mod_installer import SUPPORTED_EXTENSIONS
from anvil.core.translator import tr
from anvil.core.persistent_header import PersistentHeader
from anvil.widgets.collapsible_bar import CollapsibleSectionBar
from anvil.models.mod_list_model import ModListModel, COL_CHECK, COL_NAME, ROLE_IS_SEPARATOR, ROLE_FOLDER_NAME, ROLE_SEP_COLOR, ROLE_IS_DATA_OVERRIDE, ROLE_GROUP_NAME, ROLE_IS_GROUP_HEAD


class SeparatorMarkingScrollBar(QScrollBar):
    """Custom vertical scrollbar that draws colored markers at separator positions.

    When enabled, iterates over the source model to find separator rows,
    reads their color (ROLE_SEP_COLOR), and paints small rectangles on top
    of the normal scrollbar at proportional positions.  Respects the QSS
    theme by only painting markers, not the scrollbar background.
    """

    _DEFAULT_COLOR = QColor("#4FC3F7")

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Vertical, parent)
        self._marking_enabled: bool = False
        self._tree_view = None  # Set by _DropTreeView after init

    def set_tree_view(self, tree_view):
        """Store a reference to the tree view (needed to access the model)."""
        self._tree_view = tree_view

    def set_marking_enabled(self, enabled: bool) -> None:
        """Enable or disable separator color markings on the scrollbar."""
        self._marking_enabled = enabled
        self.update()

    def paintEvent(self, event):
        """Paint the normal scrollbar first, then overlay separator markers."""
        super().paintEvent(event)

        if not self._marking_enabled or self._tree_view is None:
            return

        proxy = self._tree_view.model()
        if proxy is None:
            return

        # Get source model through proxy
        source = None
        if hasattr(proxy, "sourceModel"):
            source = proxy.sourceModel()
        if source is None:
            return

        total_rows = source.rowCount()
        if total_rows == 0:
            return

        # Calculate the groove area (where the scrollbar handle moves)
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        style = self.style()
        groove_rect = style.subControlRect(
            style.ComplexControl.CC_ScrollBar, opt,
            style.SubControl.SC_ScrollBarGroove, self,
        )

        if groove_rect.height() <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        marker_height = max(3, groove_rect.height() // max(total_rows, 1))
        marker_height = min(marker_height, 6)

        for row in range(total_rows):
            idx = source.index(row, 0)
            if not source.data(idx, ROLE_IS_SEPARATOR):
                continue

            # Get separator color
            color_str = source.data(idx, ROLE_SEP_COLOR) or ""
            if color_str:
                color = QColor(color_str)
                if not color.isValid():
                    color = self._DEFAULT_COLOR
            else:
                color = self._DEFAULT_COLOR

            # Calculate Y position proportional to row position
            y = groove_rect.y() + int(
                (row / total_rows) * groove_rect.height()
            )

            # Draw marker rectangle
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRect(
                groove_rect.x() + 2,
                y,
                groove_rect.width() - 4,
                marker_height,
            )

        painter.end()


class CheckboxDelegate(QStyledItemDelegate):
    """Custom delegate for COL_CHECK: green circle+check (enabled), gray circle (disabled).
    Separators get a collapse/expand triangle (▾/▸) instead."""

    _COLOR_ON = QColor("#4CAF50")
    _COLOR_OFF = QColor("#666666")
    _COLOR_SEP = QColor("#D3D3D3")

    def paint(self, painter: QPainter, option, index):
        # Draw background (selection, alternating rows)
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else None
        if style:
            style.drawPrimitive(style.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)

        is_sep = index.data(ROLE_IS_SEPARATOR)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if is_sep:
            # Draw collapse/expand triangle for separators
            folder = index.data(ROLE_FOLDER_NAME) or ""
            view = option.widget
            collapsed = False
            if view and hasattr(view, '_collapsed_separators'):
                collapsed = folder in view._collapsed_separators

            size = 10
            cx = option.rect.x() + option.rect.width() // 2
            cy = option.rect.y() + option.rect.height() // 2

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._COLOR_SEP))

            from PySide6.QtGui import QPolygonF
            from PySide6.QtCore import QPointF
            if collapsed:
                # pointing right
                tri = QPolygonF([
                    QPointF(cx - 3, cy - size // 2),
                    QPointF(cx - 3, cy + size // 2),
                    QPointF(cx + size // 2 - 1, cy),
                ])
            else:
                # pointing down
                tri = QPolygonF([
                    QPointF(cx - size // 2, cy - 3),
                    QPointF(cx + size // 2, cy - 3),
                    QPointF(cx, cy + size // 2 - 1),
                ])
            painter.drawPolygon(tri)
        else:
            # Normal mod: circle + check
            check = index.data(Qt.ItemDataRole.CheckStateRole)
            enabled = check == Qt.CheckState.Checked

            size = 16
            x = option.rect.x() + (option.rect.width() - size) // 2
            y = option.rect.y() + (option.rect.height() - size) // 2
            rect = QRect(x, y, size, size)

            if enabled:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(self._COLOR_ON))
                painter.drawEllipse(rect)
                painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
                painter.drawLine(x + 3, y + 8, x + 6, y + 12)
                painter.drawLine(x + 6, y + 12, x + 12, y + 4)
            else:
                painter.setPen(QPen(self._COLOR_OFF, 1.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(rect)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(36, 28)

    def editorEvent(self, event, model, option, index):
        is_sep = index.data(ROLE_IS_SEPARATOR)
        if is_sep:
            # Separator in COL_CHECK: let Press through for DnD, toggle on Release
            if event.type() == event.Type.MouseButtonPress:
                return False  # Don't consume — Qt needs this for DnD start
            if event.type() == event.Type.MouseButtonRelease:
                view = option.widget
                if view and hasattr(view, '_collapsed_separators'):
                    # Only toggle if no drag occurred
                    if view.state() != QAbstractItemView.State.DraggingState:
                        folder = index.data(ROLE_FOLDER_NAME) or ""
                        if folder in view._collapsed_separators:
                            view._collapsed_separators.discard(folder)
                        else:
                            view._collapsed_separators.add(folder)
                        view._apply_separator_filter()
                return True
            if event.type() == event.Type.MouseButtonDblClick:
                return True
            return False
        # Normal mod: toggle checkbox on Release, consume DblClick
        if event.type() == event.Type.MouseButtonRelease:
            current = index.data(Qt.ItemDataRole.CheckStateRole)
            new_val = Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
            model.setData(index, new_val.value, Qt.ItemDataRole.CheckStateRole)
            return True
        if event.type() == event.Type.MouseButtonDblClick:
            return True
        return False


class GroupNameDelegate(QStyledItemDelegate):
    """Custom delegate for COL_NAME that draws group indentation and color bar.

    - Group-head: single indent + collapse triangle + group name suffix
    - Group member: double indent + vertical color bar on the left
    - Normal mod: no change
    """

    _INDENT_GROUP_HEAD = 20   # px indent for group head
    _INDENT_GROUP_MEMBER = 32  # px indent for group members
    _BAR_WIDTH = 3             # px width of color bar

    def __init__(self, parent=None):
        super().__init__(parent)
        self._group_manager = None  # Set by ModListView

    def set_group_manager(self, manager) -> None:
        self._group_manager = manager

    def paint(self, painter: QPainter, option, index):
        group_name = index.data(ROLE_GROUP_NAME) or ""
        is_head = index.data(ROLE_IS_GROUP_HEAD)
        is_sep = index.data(ROLE_IS_SEPARATOR)

        if is_sep or not group_name:
            # Normal separator or non-grouped mod — default painting
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background (selection, alternating rows)
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else None
        if style:
            style.drawPrimitive(style.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)

        # Get group color
        color_str = ""
        if self._group_manager:
            color_str = self._group_manager.get_group_color(group_name)
        group_color = QColor(color_str) if color_str else QColor("#4FC3F7")
        if not group_color.isValid():
            group_color = QColor("#4FC3F7")

        rect = option.rect

        if is_head:
            # Draw color bar on left
            bar_rect = QRect(rect.x() + 2, rect.y() + 2, self._BAR_WIDTH, rect.height() - 4)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(group_color))
            painter.drawRect(bar_rect)

            # Draw collapse/expand triangle
            collapsed = False
            if self._group_manager:
                collapsed = self._group_manager.is_collapsed(group_name)

            tri_x = rect.x() + 10
            tri_cy = rect.y() + rect.height() // 2
            tri_size = 8

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#D3D3D3")))

            from PySide6.QtGui import QPolygonF
            from PySide6.QtCore import QPointF
            if collapsed:
                tri = QPolygonF([
                    QPointF(tri_x, tri_cy - tri_size // 2),
                    QPointF(tri_x, tri_cy + tri_size // 2),
                    QPointF(tri_x + tri_size // 2, tri_cy),
                ])
            else:
                tri = QPolygonF([
                    QPointF(tri_x - tri_size // 4, tri_cy - 2),
                    QPointF(tri_x + tri_size // 2 + tri_size // 4, tri_cy - 2),
                    QPointF(tri_x + tri_size // 4, tri_cy + tri_size // 2 - 1),
                ])
            painter.drawPolygon(tri)

            # Draw text with indent
            text_rect = QRect(rect.x() + self._INDENT_GROUP_HEAD, rect.y(), rect.width() - self._INDENT_GROUP_HEAD, rect.height())
            display_text = index.data(Qt.ItemDataRole.DisplayRole) or ""

            # If collapsed, append member count
            if collapsed and self._group_manager:
                members = self._group_manager.get_members(group_name)
                count = len(members)
                count_text = tr("tooltip.group_collapsed", count=count)
                display_text = f"{display_text}  [{count_text}]"

            text_color = option.palette.highlightedText().color() if option.state & option.widget.style().StateFlag.State_Selected else option.palette.text().color()
            painter.setPen(QPen(text_color))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, display_text)
        else:
            # Group member: draw color bar + indented text
            bar_rect = QRect(rect.x() + 2, rect.y(), self._BAR_WIDTH, rect.height())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(group_color))
            painter.drawRect(bar_rect)

            # Draw text with double indent
            text_rect = QRect(rect.x() + self._INDENT_GROUP_MEMBER, rect.y(), rect.width() - self._INDENT_GROUP_MEMBER, rect.height())
            display_text = index.data(Qt.ItemDataRole.DisplayRole) or ""
            text_color = option.palette.highlightedText().color() if option.state & option.widget.style().StateFlag.State_Selected else option.palette.text().color()
            painter.setPen(QPen(text_color))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, display_text)

        painter.restore()

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        return QSize(hint.width(), max(hint.height(), 28))


class ModListProxyModel(QSortFilterProxyModel):
    """Proxy-Model für Mod-Liste. Qt leitet DnD automatisch ans Source-Model weiter.
    Supports hiding mods under collapsed separators and chip-based filtering."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hidden_rows: set[int] = set()
        # Filter state (set by FilterPanel via MainWindow)
        self._filter_text: str = ""
        self._filter_prop_ids: set[int] = set()
        self._filter_cat_ids: set[int] = set()
        self._filter_nexus_cat_ids: set[int] = set()
        self._mod_entries: list = []  # Reference to MainWindow._current_mod_entries
        self._category_manager = None
        self._group_manager = None  # Set by MainWindow for group-head visibility

    def set_group_manager(self, manager):
        """Set GroupManager reference for group-head filter logic."""
        self._group_manager = manager

    def set_hidden_rows(self, rows: set[int]):
        """Set which source rows should be hidden (collapsed under a separator)."""
        self.beginResetModel()
        self._hidden_rows = rows
        self.endResetModel()

    def set_filter_state(self, text: str, prop_ids: set[int], cat_ids: set[int],
                         nexus_cat_ids: set[int] | None = None):
        """Update filter criteria from FilterPanel and re-filter."""
        self._filter_text = text
        self._filter_prop_ids = prop_ids
        self._filter_cat_ids = cat_ids
        self._filter_nexus_cat_ids = nexus_cat_ids or set()
        self.invalidateFilter()

    def set_mod_entries(self, entries: list):
        """Set reference to the current mod entries for filter logic."""
        self._mod_entries = entries

    def set_category_manager(self, manager):
        """Set CategoryManager reference for category name lookup."""
        self._category_manager = manager

    def filterAcceptsRow(self, source_row, source_parent):
        has_filter = (self._filter_text or self._filter_prop_ids
                      or self._filter_cat_ids or self._filter_nexus_cat_ids)
        if source_row in self._hidden_rows:
            # When search/filter is active, show mods even in collapsed separators
            if not has_filter:
                return False

        # If no filters active, accept all
        if not has_filter:
            return True

        # Separators always visible (they structure the list)
        source = self.sourceModel()
        if source:
            from anvil.models.mod_list_model import ROLE_IS_SEPARATOR, ROLE_IS_GROUP_HEAD, ROLE_GROUP_NAME
            idx = source.index(source_row, 0)
            if source.data(idx, ROLE_IS_SEPARATOR):
                return True

            # Group-head: visible if ANY member passes the filter
            if source.data(idx, ROLE_IS_GROUP_HEAD) and self._group_manager:
                group_name = source.data(idx, ROLE_GROUP_NAME) or ""
                if group_name:
                    members = self._group_manager.get_members(group_name)
                    for member_folder in members:
                        for sr in range(source.rowCount()):
                            sr_idx = source.index(sr, 0)
                            if source.data(sr_idx, ROLE_FOLDER_NAME) == member_folder:
                                if sr != source_row and self._entry_matches_filter(sr):
                                    return True
                                break

        # Get corresponding ModEntry (visible_entries index = source_row)
        return self._entry_matches_filter(source_row)

    def _entry_matches_filter(self, source_row: int) -> bool:
        """Check if the entry at source_row matches current filters."""
        source = self.sourceModel()

        if source_row >= len(self._mod_entries):
            return True
        entry = self._mod_entries[source_row]

        # Text filter (AND: all words must match name, author, or category)
        if self._filter_text:
            words = self._filter_text.split()
            search_name = (entry.display_name or entry.name).lower()
            search_author = (entry.author or "").lower()
            # Resolve category name for text search
            cat_name = ""
            if self._category_manager and entry.primary_category:
                cat_name = self._category_manager.get_name(entry.primary_category).lower()
            search_target = f"{search_name} {search_author} {cat_name}"
            for word in words:
                if word not in search_target:
                    return False

        # Property filters (OR within properties: show if ANY checked property matches)
        if self._filter_prop_ids:
            from anvil.widgets.filter_panel import (
                PROP_ENABLED, PROP_DISABLED, PROP_HAS_NOTES,
                PROP_HAS_CATEGORY, PROP_NO_CATEGORY,
                PROP_CONFLICT_WIN, PROP_CONFLICT_LOSE,
            )
            match = False
            if PROP_ENABLED in self._filter_prop_ids and entry.enabled:
                match = True
            if PROP_DISABLED in self._filter_prop_ids and not entry.enabled:
                match = True
            if PROP_HAS_NOTES in self._filter_prop_ids and getattr(entry, "notes", ""):
                match = True
            if PROP_HAS_CATEGORY in self._filter_prop_ids and entry.category_ids:
                match = True
            if PROP_NO_CATEGORY in self._filter_prop_ids and not entry.category_ids:
                match = True
            # Conflict filters need conflict data from model row
            if source and source_row < source.rowCount():
                row_data = source._rows[source_row] if source_row < len(source._rows) else None
                if row_data and isinstance(row_data.conflicts, dict):
                    ctype = row_data.conflicts.get("type", "")
                    if PROP_CONFLICT_WIN in self._filter_prop_ids and ctype in ("win", "both"):
                        match = True
                    if PROP_CONFLICT_LOSE in self._filter_prop_ids and ctype in ("lose", "both"):
                        match = True
            if not match:
                return False

        # Category filters (OR: show if mod has ANY of the checked categories)
        if self._filter_cat_ids:
            mod_cats = set(entry.category_ids)
            if not mod_cats.intersection(self._filter_cat_ids):
                return False

        # Nexus category filters (OR: show if mod's nexus_category matches ANY chip)
        if self._filter_nexus_cat_ids:
            if entry.nexus_category not in self._filter_nexus_cat_ids:
                return False

        return True


class _DropTreeView(QTreeView):
    """QTreeView that accepts external archive file drops in addition to internal DnD."""

    archives_dropped = Signal(list)  # list of file path strings
    archives_dropped_at = Signal(list, int)  # list of file paths + target source row

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed_separators: set[str] = set()
        self._collapsible_asc: bool = True
        self._collapsible_dsc: bool = True
        self._extra_extensions: set[str] = set()

        # Install custom scrollbar for separator markings
        self._sep_scrollbar = SeparatorMarkingScrollBar(self)
        self._sep_scrollbar.set_tree_view(self)
        self.setVerticalScrollBar(self._sep_scrollbar)

        # ── Setting 4: Auto-Expand bei Drag & Drop ──
        self._auto_expand_on_drag: bool = False
        self._expand_timer = QTimer(self)
        self._expand_timer.setSingleShot(True)
        self._expand_timer.setInterval(500)
        self._expand_timer.timeout.connect(self._on_expand_timer)
        self._expand_hover_index: QModelIndex = QModelIndex()

        # Auto-scroll during drag & drop
        self._auto_scroll_timer = QTimer(self)
        self._auto_scroll_timer.setInterval(50)
        self._auto_scroll_timer.timeout.connect(self._do_auto_scroll)
        self._auto_scroll_speed: int = 0

        # ── Deferred separator toggle (allows DnD to start) ──
        self._pending_separator_toggle: str | None = None

        # ── Setting 6: Konflikte VON Trenner ──
        self._conflicts_from_separator: bool = False

        # ── Conflict highlighting for selected mod ──
        self._conflict_highlight_on_select: bool = False

        # ── Group manager reference ──
        self._group_manager = None

    def _apply_separator_filter(self):
        """Recalculate which rows to hide based on collapsed separators and groups."""
        proxy = self.model()
        if not isinstance(proxy, ModListProxyModel):
            return
        source = proxy.sourceModel()
        if not source:
            return

        # Sync collapsed state to source model for data() queries (Settings 5, 7-10)
        source._collapsed_separators = set(self._collapsed_separators)

        # Guard: Collapsible nur bei Prioritäts-Sortierung (COL_CHECK)
        sort_col = proxy.sortColumn()
        if sort_col > COL_CHECK:
            proxy.set_hidden_rows(set())
            return

        sort_order = proxy.sortOrder()
        if sort_order == Qt.SortOrder.AscendingOrder and not self._collapsible_asc:
            proxy.set_hidden_rows(set())
            return
        if sort_order == Qt.SortOrder.DescendingOrder and not self._collapsible_dsc:
            proxy.set_hidden_rows(set())
            return

        hidden: set[int] = set()
        current_sep_collapsed = False

        for row in range(source.rowCount()):
            idx = source.index(row, 0)
            is_sep = source.data(idx, ROLE_IS_SEPARATOR)
            if is_sep:
                folder = source.data(idx, ROLE_FOLDER_NAME) or ""
                current_sep_collapsed = folder in self._collapsed_separators
                continue
            if current_sep_collapsed:
                hidden.add(row)
            else:
                # Group collapse: hide non-head members of collapsed groups
                if self._group_manager:
                    group_name = source.data(idx, ROLE_GROUP_NAME) or ""
                    is_head = source.data(idx, ROLE_IS_GROUP_HEAD)
                    if group_name and not is_head and self._group_manager.is_collapsed(group_name):
                        hidden.add(row)

        proxy.set_hidden_rows(hidden)

    # ── Separator click on any column ────────────────────────────

    def mousePressEvent(self, event):
        """Klick auf Separator/Group-Head merken — Toggle erst in mouseReleaseEvent (damit DnD starten kann)."""
        self._pending_separator_toggle = None
        self._pending_group_toggle = None
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self.indexAt(event.pos())
            if idx.isValid():
                proxy = self.model()
                if isinstance(proxy, ModListProxyModel):
                    source = proxy.sourceModel()
                    source_idx = proxy.mapToSource(idx)
                    if source and source_idx.isValid():
                        is_sep = source.data(source.index(source_idx.row(), 0), ROLE_IS_SEPARATOR)
                        if is_sep and idx.column() != COL_CHECK:
                            folder = source.data(source.index(source_idx.row(), 0), ROLE_FOLDER_NAME) or ""
                            self._pending_separator_toggle = folder
                        elif not is_sep and idx.column() == COL_NAME:
                            # Check if this is a group head click
                            is_head = source.data(source.index(source_idx.row(), 0), ROLE_IS_GROUP_HEAD)
                            if is_head:
                                group_name = source.data(source.index(source_idx.row(), 0), ROLE_GROUP_NAME) or ""
                                if group_name:
                                    self._pending_group_toggle = group_name
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Toggle Separator/Group nur wenn KEIN Drag stattfand."""
        if self._pending_separator_toggle is not None:
            folder = self._pending_separator_toggle
            self._pending_separator_toggle = None
            if self.state() != QAbstractItemView.State.DraggingState:
                if folder in self._collapsed_separators:
                    self._collapsed_separators.discard(folder)
                else:
                    self._collapsed_separators.add(folder)
                self._apply_separator_filter()
        if self._pending_group_toggle is not None:
            group_name = self._pending_group_toggle
            self._pending_group_toggle = None
            if self.state() != QAbstractItemView.State.DraggingState:
                if self._group_manager:
                    self._group_manager.toggle_collapsed(group_name)
                    self._apply_separator_filter()
        super().mouseReleaseEvent(event)

    # ── Setting 4: Auto-Expand timer logic ──────────────────────

    def _on_expand_timer(self) -> None:
        """Timer fired: expand the separator we've been hovering over."""
        if not self._expand_hover_index.isValid():
            return
        proxy = self.model()
        if not isinstance(proxy, ModListProxyModel):
            return
        source = proxy.sourceModel()
        if not source:
            return
        source_idx = proxy.mapToSource(self._expand_hover_index)
        if not source_idx.isValid():
            return
        folder = source.data(source.index(source_idx.row(), 0), ROLE_FOLDER_NAME) or ""
        if folder and folder in self._collapsed_separators:
            self._collapsed_separators.discard(folder)
            self._apply_separator_filter()
        self._expand_hover_index = QModelIndex()

    def _stop_expand_timer(self) -> None:
        """Stop the auto-expand timer and clear the hover index."""
        self._expand_timer.stop()
        self._expand_hover_index = QModelIndex()

    # ── Auto-scroll during drag ─────────────────────────────────

    def _do_auto_scroll(self) -> None:
        """Scroll the view during drag based on cursor proximity to edges."""
        if self._auto_scroll_speed == 0:
            self._auto_scroll_timer.stop()
            return
        sb = self.verticalScrollBar()
        sb.setValue(sb.value() + self._auto_scroll_speed)

    def _stop_auto_scroll(self) -> None:
        """Stop the auto-scroll timer."""
        self._auto_scroll_speed = 0
        self._auto_scroll_timer.stop()

    # ── Drag & Drop events ────────────────────────────────────────

    def startDrag(self, supportedActions):
        """Hide selection highlight during drag, restore + reselect after drop."""
        from PySide6.QtGui import QPalette
        # Save dragged mod names for reselection after drop
        self._dragged_mod_names = []
        proxy = self.model()
        if isinstance(proxy, ModListProxyModel):
            source = proxy.sourceModel()
            if source:
                for idx in self.selectedIndexes():
                    if idx.column() == 0:
                        src_idx = proxy.mapToSource(idx)
                        if src_idx.isValid():
                            self._dragged_mod_names.append(source._rows[src_idx.row()].name)
        # Make highlight transparent AFTER pixmap is created (QTimer fires inside drag event loop)
        self._orig_highlight = self.palette().color(QPalette.ColorRole.Highlight)
        QTimer.singleShot(0, self._hide_drag_highlight)
        super().startDrag(supportedActions)  # blocks until drag ends
        # Restore highlight color
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Highlight, self._orig_highlight)
        self.setPalette(pal)
        # Reselect moved mods at new positions
        names = getattr(self, "_dragged_mod_names", [])
        if names and isinstance(proxy, ModListProxyModel):
            source = proxy.sourceModel()
            if source:
                from PySide6.QtCore import QItemSelectionModel
                sel = self.selectionModel()
                sel.clearSelection()
                for i, row_data in enumerate(source._rows):
                    if row_data.name in names:
                        for col in range(source.columnCount()):
                            proxy_idx = proxy.mapFromSource(source.index(i, col))
                            if proxy_idx.isValid():
                                sel.select(proxy_idx, QItemSelectionModel.SelectionFlag.Select)
        self._dragged_mod_names = []

    def _hide_drag_highlight(self):
        """Called via QTimer.singleShot(0) inside drag event loop — after pixmap is rendered."""
        from PySide6.QtGui import QPalette
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Highlight, QColor(0, 0, 0, 0))
        self.setPalette(pal)
        self.viewport().update()

    def dragEnterEvent(self, event):
        super().dragEnterEvent(event)
        if event.mimeData().hasUrls():
            accepted = SUPPORTED_EXTENSIONS | self._extra_extensions
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if any(path.lower().endswith(ext) for ext in accepted):
                        event.acceptProposedAction()
                        return

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

        # Auto-scroll when dragging near edges
        EDGE_SIZE = 40
        pos = event.position().toPoint()
        viewport_height = self.viewport().height()
        y = pos.y()

        if y < EDGE_SIZE:
            ratio = 1.0 - (y / EDGE_SIZE)
            self._auto_scroll_speed = -max(1, int(ratio * 5))
            if not self._auto_scroll_timer.isActive():
                self._auto_scroll_timer.start()
        elif y > viewport_height - EDGE_SIZE:
            ratio = 1.0 - ((viewport_height - y) / EDGE_SIZE)
            self._auto_scroll_speed = max(1, int(ratio * 5))
            if not self._auto_scroll_timer.isActive():
                self._auto_scroll_timer.start()
        else:
            self._stop_auto_scroll()

        # Setting 4: Auto-Expand logic
        if not self._auto_expand_on_drag:
            return

        proxy_idx = self.indexAt(event.position().toPoint())
        if not proxy_idx.isValid():
            self._stop_expand_timer()
            return

        proxy = self.model()
        if not isinstance(proxy, ModListProxyModel):
            return
        source = proxy.sourceModel()
        if not source:
            return
        source_idx = proxy.mapToSource(proxy_idx)
        if not source_idx.isValid():
            self._stop_expand_timer()
            return

        is_sep = source.data(source.index(source_idx.row(), 0), ROLE_IS_SEPARATOR)
        if not is_sep:
            self._stop_expand_timer()
            return

        folder = source.data(source.index(source_idx.row(), 0), ROLE_FOLDER_NAME) or ""
        # Only trigger for collapsed separators (expand them on hover)
        if folder not in self._collapsed_separators:
            self._stop_expand_timer()
            return

        # Check if we're still hovering over the same separator
        if self._expand_hover_index.isValid() and self._expand_hover_index == proxy_idx:
            # Timer already running for this separator, keep going
            return

        # New separator: start timer
        self._stop_expand_timer()
        self._expand_hover_index = proxy_idx
        self._expand_timer.start()

    def dragLeaveEvent(self, event):
        self._stop_auto_scroll()
        self._stop_expand_timer()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._stop_auto_scroll()
        self._stop_expand_timer()
        if event.mimeData().hasUrls():
            accepted = SUPPORTED_EXTENSIONS | self._extra_extensions
            paths = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if any(path.lower().endswith(ext) for ext in accepted):
                        paths.append(path)
            if paths:
                event.acceptProposedAction()
                # Compute drop target source row
                proxy_idx = self.indexAt(event.position().toPoint())
                if proxy_idx.isValid():
                    proxy = self.model()
                    if isinstance(proxy, ModListProxyModel):
                        source_idx = proxy.mapToSource(proxy_idx)
                        source = proxy.sourceModel()
                        if source_idx.isValid() and source:
                            target_row = source_idx.row()
                            is_sep = source.data(source.index(target_row, 0), ROLE_IS_SEPARATOR)
                            if is_sep:
                                folder = source.data(source.index(target_row, 0), ROLE_FOLDER_NAME) or ""
                                if folder in self._collapsed_separators:
                                    # K3: Collapsed separator → last child + 1
                                    children = source._get_separator_children(target_row)
                                    target_row = children[-1] + 1 if children else target_row + 1
                                else:
                                    # K1: Expanded separator → after separator row
                                    target_row = target_row + 1
                            # K2: Normal mod → insert at that position
                            self.archives_dropped_at.emit(paths, target_row)
                            return
                # No valid target → append at end (K4 / file manager drop)
                self.archives_dropped.emit(paths)
                return
        # Internal DnD (mod reorder)
        # Detect if a separator is being moved — auto-collapse after drop
        _sep_to_collapse = None
        from anvil.models.mod_list_model import MIME_MOD_ROWS
        if event.mimeData().hasFormat(MIME_MOD_ROWS):
            from PySide6.QtCore import QDataStream, QIODevice, QByteArray
            raw = event.mimeData().data(MIME_MOD_ROWS)
            stream = QDataStream(raw, QIODevice.OpenModeFlag.ReadOnly)
            rows = []
            while not stream.atEnd():
                rows.append(stream.readInt32())
            if len(rows) == 1:
                proxy = self.model()
                if isinstance(proxy, ModListProxyModel):
                    source = proxy.sourceModel()
                    if source and 0 <= rows[0] < source.rowCount():
                        is_sep = source.data(source.index(rows[0], 0), ROLE_IS_SEPARATOR)
                        if is_sep:
                            _sep_to_collapse = source.data(source.index(rows[0], 0), ROLE_FOLDER_NAME) or ""

        super().dropEvent(event)

        # Auto-collapse the moved separator (Anforderung 4)
        if _sep_to_collapse and _sep_to_collapse not in self._collapsed_separators:
            self._collapsed_separators.add(_sep_to_collapse)
            self._apply_separator_filter()

    # ── Setting 6: Selection-based conflict highlighting ──────────

    def selectionChanged(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        """Handle Setting 6 (separator conflict highlighting) and mod conflict highlighting."""
        super().selectionChanged(selected, deselected)

        if not self._conflicts_from_separator and not self._conflict_highlight_on_select:
            return

        proxy = self.model()
        if not isinstance(proxy, ModListProxyModel):
            return
        source = proxy.sourceModel()
        if not source:
            return

        sel_model = self.selectionModel()
        if sel_model is None:
            return
        selected_indexes = sel_model.selectedRows()

        # Multi-select or no selection → clear all highlights
        if len(selected_indexes) != 1:
            source.set_highlighted_rows(set())
            source.set_conflict_highlight(set(), set())
            return

        proxy_idx = selected_indexes[0]
        source_idx = proxy.mapToSource(proxy_idx)
        if not source_idx.isValid():
            source.set_highlighted_rows(set())
            source.set_conflict_highlight(set(), set())
            return

        row = source_idx.row()
        if row >= len(source._rows):
            source.set_highlighted_rows(set())
            source.set_conflict_highlight(set(), set())
            return

        r = source._rows[row]

        if r.is_separator:
            # Separator selected → clear mod conflict highlights, apply Setting 6
            source.set_conflict_highlight(set(), set())

            if not self._conflicts_from_separator:
                source.set_highlighted_rows(set())
                return

            # Only for collapsed separators
            if r.folder_name not in self._collapsed_separators:
                source.set_highlighted_rows(set())
                return

            # Collect folder_names of mods that conflict with children
            child_conflict_mods: set[str] = set()
            children = source._get_separator_children(row)
            for child_row in children:
                child = source._rows[child_row]
                if isinstance(child.conflicts, dict) and child.conflicts.get("type", ""):
                    for mod_name in child.conflicts.get("win_mods_list", []):
                        child_conflict_mods.add(mod_name)
                    for mod_name in child.conflicts.get("lose_mods_list", []):
                        child_conflict_mods.add(mod_name)

            if not child_conflict_mods:
                source.set_highlighted_rows(set())
                return

            # Find source rows outside this separator that match conflicting mod names
            children_set = set(children)
            children_set.add(row)  # Exclude the separator itself
            highlighted: set[int] = set()
            for i, mod_row in enumerate(source._rows):
                if i in children_set:
                    continue
                if mod_row.folder_name in child_conflict_mods:
                    highlighted.add(i)
            source.set_highlighted_rows(highlighted)
        else:
            # Normal mod selected → clear Setting 6, apply conflict highlighting
            source.set_highlighted_rows(set())

            if not self._conflict_highlight_on_select:
                source.set_conflict_highlight(set(), set())
                return

            if not isinstance(r.conflicts, dict) or not r.conflicts.get("type", ""):
                source.set_conflict_highlight(set(), set())
                return

            # Build win/lose row sets from conflict data
            win_names = set(r.conflicts.get("win_mods_list", []))
            lose_names = set(r.conflicts.get("lose_mods_list", []))

            win_rows: set[int] = set()
            lose_rows: set[int] = set()
            for i, mod_row in enumerate(source._rows):
                if mod_row.folder_name in lose_names:
                    lose_rows.add(i)   # Lose takes priority (criterion 10)
                elif mod_row.folder_name in win_names:
                    win_rows.add(i)

            source.set_conflict_highlight(win_rows, lose_rows)


class _DropFrameworkTree(QTreeWidget):
    """QTreeWidget that accepts external archive file drops for framework installation."""

    archives_dropped = Signal(list)  # list of file path strings

    def dragEnterEvent(self, event):
        print(f"[FW-TREE] dragEnterEvent: hasUrls={event.mimeData().hasUrls()}", flush=True)
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    print(f"[FW-TREE] dragEnter url: {path}", flush=True)
                    if any(path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                        event.acceptProposedAction()
                        return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        print(f"[FW-TREE] dropEvent: hasUrls={event.mimeData().hasUrls()}", flush=True)
        if event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    print(f"[FW-TREE] drop url: {path}", flush=True)
                    if any(path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                        paths.append(path)
            if paths:
                print(f"[FW-TREE] emitting archives_dropped: {paths}", flush=True)
                event.acceptProposedAction()
                self.archives_dropped.emit(paths)
                return
        super().dropEvent(event)


class ModListView(QWidget):
    archives_dropped = Signal(list)  # forwarded from _DropTreeView
    archives_dropped_at = Signal(list, int)  # forwarded from _DropTreeView (with position)
    context_menu_requested = Signal(QPoint)  # global pos for context menu
    fw_context_menu_requested = Signal(QPoint, dict)  # global pos + fw_data for framework context menu
    fw_archives_dropped = Signal(list)  # archive paths dropped on framework tree
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tree = _DropTreeView()
        self._tree.archives_dropped.connect(self.archives_dropped)
        self._tree.archives_dropped_at.connect(self.archives_dropped_at)
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.setUniformRowHeights(True)
        self._tree.setDragEnabled(True)
        self._tree.setAcceptDrops(True)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self._tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._tree.setDropIndicatorShown(True)
        self._tree.setDragDropOverwriteMode(False)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(
            lambda pos: self.context_menu_requested.emit(self._tree.viewport().mapToGlobal(pos))
        )
        # Source-Model und Proxy-Model für korrektes DnD
        self._source_model = ModListModel(self)
        self._proxy_model = ModListProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)
        self._tree.setModel(self._proxy_model)
        self._tree.header().setSortIndicatorShown(False)
        self._tree.header().setSectionsClickable(False)
        self._model = self._proxy_model  # Für Kompatibilität

        # Connect model signals to update scrollbar separator markings
        self._source_model.dataChanged.connect(self._update_scrollbar_markings)
        self._source_model.layoutChanged.connect(self._update_scrollbar_markings)
        self._source_model.modelReset.connect(self._update_scrollbar_markings)
        self._source_model.rowsMoved.connect(self._update_scrollbar_markings)

        # Custom delegate for checkbox column
        self._check_delegate = CheckboxDelegate(self._tree)
        self._tree.setItemDelegateForColumn(COL_CHECK, self._check_delegate)
        # Custom delegate for name column (group indentation + color bar)
        self._name_delegate = GroupNameDelegate(self._tree)
        self._tree.setItemDelegateForColumn(COL_NAME, self._name_delegate)
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
        self._persistent_header = PersistentHeader(
            header, "modlist", fixed_columns=frozenset({COL_CHECK}),
        )

        # ── Frameworks section (below mod list) ──────────────────
        fw_container = QWidget()
        fw_layout = QVBoxLayout(fw_container)
        fw_layout.setContentsMargins(0, 0, 0, 0)
        fw_layout.setSpacing(0)

        self._fw_tree = _DropFrameworkTree()

        self._fw_label = CollapsibleSectionBar(
            tr("label.type_framework") + "s", "frameworks", self._fw_tree,
            style="QLabel { font-weight: bold; padding: 4px 6px; "
                  "background: #1a2a3a; border-bottom: 1px solid #333; }",
            container=fw_container,
            default_collapsed=True,
        )
        self._fw_label.set_count(0)
        fw_layout.addWidget(self._fw_label)
        self._fw_tree.setHeaderLabels([tr("label.name"), tr("label.header_description"), tr("game_panel.header_status")])
        self._fw_tree.setRootIsDecorated(False)
        self._fw_tree.setAlternatingRowColors(True)
        self._fw_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._fw_tree.setUniformRowHeights(True)
        self._fw_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._fw_tree.setAcceptDrops(True)
        self._fw_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._fw_tree.customContextMenuRequested.connect(self._on_fw_context_menu)
        self._fw_tree.archives_dropped.connect(self.fw_archives_dropped)
        fw_hdr = self._fw_tree.header()
        fw_hdr.setStretchLastSection(False)
        fw_hdr.setCascadingSectionResizes(True)
        fw_hdr.setMinimumSectionSize(30)
        fw_hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._fw_tree.setColumnWidth(0, 180)
        self._fw_tree.setColumnWidth(1, 280)
        self._fw_tree.setColumnWidth(2, 100)
        self._ph_frameworks = PersistentHeader(fw_hdr, "frameworks")
        fw_layout.addWidget(self._fw_tree)

        # Minimum height = label only (~28px), tree hides when collapsed
        fw_container.setMinimumHeight(28)

        # Splitter: mod list (top) + frameworks (bottom)
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.addWidget(self._tree)
        self._splitter.addWidget(fw_container)
        self._splitter.setStretchFactor(0, 85)
        self._splitter.setStretchFactor(1, 15)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.splitterMoved.connect(self._on_fw_splitter_moved)
        # Hide frameworks section by default (shown when load_frameworks is called)
        fw_container.setVisible(False)
        self._fw_container = fw_container
        layout.addWidget(self._splitter)

    def _on_fw_splitter_moved(self) -> None:
        """Hide/show the framework tree based on available space (respects collapsed state)."""
        if not self._fw_label.collapsed:
            h = self._fw_container.height()
            self._fw_tree.setVisible(h > 60)

    def source_model(self) -> ModListModel:
        """Return the underlying ModListModel."""
        return self._source_model

    def set_group_manager(self, manager) -> None:
        """Set GroupManager reference for group display and filtering."""
        self._tree._group_manager = manager
        self._name_delegate.set_group_manager(manager)
        self._proxy_model.set_group_manager(manager)

    def clear_mods(self) -> None:
        """Remove all mods from the list."""
        self._source_model.clear()

    def header(self) -> QHeaderView:
        """Return the tree header for state save/restore."""
        return self._tree.header()

    def restore_column_widths(self) -> None:
        """Restore saved column widths (call after data is populated)."""
        self._persistent_header.restore()

    def flush_column_widths(self) -> None:
        """Flush any pending debounced column-width write."""
        self._persistent_header.flush()
        self._ph_frameworks.flush()

    # ── Frameworks section ────────────────────────────────────────

    def load_frameworks(self, frameworks: list[dict]) -> None:
        """Populate the frameworks tree.

        Each dict should have: name, description, installed (bool).
        If the list is empty the section is hidden.
        """
        self._fw_tree.clear()
        if not frameworks:
            self._fw_container.setVisible(False)
            return

        self._fw_container.setVisible(True)
        self._fw_label.set_count(len(frameworks))

        for fw in frameworks:
            item = QTreeWidgetItem()
            item.setText(0, fw.get("name", "?"))
            item.setText(1, fw.get("description", ""))
            installed = fw.get("installed", False)
            item.setText(2, tr("game_panel.installed") if installed else tr("game_panel.not_installed"))
            if installed:
                item.setForeground(2, QBrush(QColor("#4CAF50")))
            else:
                item.setForeground(2, QBrush(QColor("#F44336")))
            item.setData(0, Qt.ItemDataRole.UserRole, fw)
            self._fw_tree.addTopLevelItem(item)

    def restore_framework_widths(self) -> None:
        """Restore saved column widths for the frameworks tree."""
        self._ph_frameworks.restore()

    def _on_fw_context_menu(self, pos) -> None:
        """Forward framework context menu request with item data."""
        item = self._fw_tree.itemAt(pos)
        if item is None:
            return
        fw_data = item.data(0, Qt.ItemDataRole.UserRole)
        if fw_data:
            self.fw_context_menu_requested.emit(
                self._fw_tree.viewport().mapToGlobal(pos), fw_data,
            )

    def get_current_mod_name(self):
        """Liefert den Mod-Namen der aktuell gewählten Zeile oder None."""
        proxy_idx = self._tree.currentIndex()
        if not proxy_idx.isValid() or proxy_idx.row() < 0:
            return None
        source_idx = self._proxy_model.mapToSource(proxy_idx)
        name = self._source_model.data(self._source_model.index(source_idx.row(), COL_NAME), Qt.ItemDataRole.DisplayRole)
        return name if name is not None else None

    def get_mod_name_from_index(self, proxy_idx):
        """Liefert den Mod-Namen für einen gegebenen Proxy-Index oder None."""
        if not proxy_idx.isValid() or proxy_idx.row() < 0:
            return None
        source_idx = self._proxy_model.mapToSource(proxy_idx)
        name = self._source_model.data(self._source_model.index(source_idx.row(), COL_NAME), Qt.ItemDataRole.DisplayRole)
        return name if name is not None else None

    def select_mod_by_name(self, mod_name: str) -> None:
        """Selektiert einen Mod in der Liste anhand seines Namens."""
        for row in range(self._proxy_model.rowCount()):
            proxy_idx = self._proxy_model.index(row, COL_NAME)
            name = self._proxy_model.data(proxy_idx, Qt.ItemDataRole.DisplayRole)
            if name == mod_name:
                self._tree.setCurrentIndex(proxy_idx)
                self._tree.scrollTo(proxy_idx)
                return

    def get_visible_mod_names(self) -> list[str]:
        """Liefert die sichtbare Mod-Reihenfolge (ohne Separatoren) aus dem Proxy-Model."""
        names = []
        for row in range(self._proxy_model.rowCount()):
            proxy_idx = self._proxy_model.index(row, 0)
            source_idx = self._proxy_model.mapToSource(proxy_idx)
            is_sep = self._source_model.data(source_idx, ROLE_IS_SEPARATOR)
            if is_sep:
                continue
            name_idx = self._proxy_model.index(row, COL_NAME)
            name = self._proxy_model.data(name_idx, Qt.ItemDataRole.DisplayRole)
            if name:
                names.append(name)
        return names

    def get_selected_source_rows(self) -> list[int]:
        """Return sorted list of selected source-model row indices."""
        rows = set()
        for proxy_idx in self._tree.selectionModel().selectedRows():
            source_idx = self._proxy_model.mapToSource(proxy_idx)
            rows.add(source_idx.row())
        return sorted(rows)

    # ── Scrollbar separator markings ─────────────────────────────────

    def set_extra_drop_extensions(self, extensions: set[str]) -> None:
        """Add extra accepted file extensions for drag-and-drop (e.g. {'.pak'} for BG3)."""
        self._tree._extra_extensions = extensions

    def set_scrollbar_marking_enabled(self, enabled: bool) -> None:
        """Enable or disable separator color markings on the scrollbar."""
        self._tree._sep_scrollbar.set_marking_enabled(enabled)

    def _update_scrollbar_markings(self, *args) -> None:
        """Trigger a repaint of the scrollbar separator markings."""
        self._tree._sep_scrollbar.update()
