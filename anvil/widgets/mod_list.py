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
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex, QSize, QRect, Signal, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

from anvil.core.mod_installer import SUPPORTED_EXTENSIONS
from anvil.core.translator import tr
from anvil.core.persistent_header import PersistentHeader
from anvil.widgets.collapsible_bar import CollapsibleSectionBar
from anvil.models.mod_list_model import ModListModel, COL_CHECK, COL_NAME, ROLE_IS_SEPARATOR, ROLE_FOLDER_NAME


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
                # ▸ pointing right
                tri = QPolygonF([
                    QPointF(cx - 3, cy - size // 2),
                    QPointF(cx - 3, cy + size // 2),
                    QPointF(cx + size // 2 - 1, cy),
                ])
            else:
                # ▾ pointing down
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
            # Separator: toggle on Press, consume Release/DblClick
            if event.type() == event.Type.MouseButtonPress:
                folder = index.data(ROLE_FOLDER_NAME) or ""
                view = option.widget
                if view and hasattr(view, '_collapsed_separators'):
                    if folder in view._collapsed_separators:
                        view._collapsed_separators.discard(folder)
                    else:
                        view._collapsed_separators.add(folder)
                    view._apply_separator_filter()
                return True
            if event.type() in (event.Type.MouseButtonRelease, event.Type.MouseButtonDblClick):
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
        self._mod_entries: list = []  # Reference to MainWindow._current_mod_entries
        self._category_manager = None

    def set_hidden_rows(self, rows: set[int]):
        """Set which source rows should be hidden (collapsed under a separator)."""
        self.beginResetModel()
        self._hidden_rows = rows
        self.endResetModel()

    def set_filter_state(self, text: str, prop_ids: set[int], cat_ids: set[int]):
        """Update filter criteria from FilterPanel and re-filter."""
        self._filter_text = text
        self._filter_prop_ids = prop_ids
        self._filter_cat_ids = cat_ids
        self.invalidateFilter()

    def set_mod_entries(self, entries: list):
        """Set reference to the current mod entries for filter logic."""
        self._mod_entries = entries

    def set_category_manager(self, manager):
        """Set CategoryManager reference for category name lookup."""
        self._category_manager = manager

    def filterAcceptsRow(self, source_row, source_parent):
        if source_row in self._hidden_rows:
            return False

        # If no filters active, accept all
        if not self._filter_text and not self._filter_prop_ids and not self._filter_cat_ids:
            return True

        # Separators always visible (they structure the list)
        source = self.sourceModel()
        if source:
            from anvil.models.mod_list_model import ROLE_IS_SEPARATOR
            idx = source.index(source_row, 0)
            if source.data(idx, ROLE_IS_SEPARATOR):
                return True

        # Get corresponding ModEntry (visible_entries index = source_row)
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
                PROP_ENABLED, PROP_DISABLED, PROP_HAS_CATEGORY,
                PROP_NO_CATEGORY, PROP_CONFLICT_WIN, PROP_CONFLICT_LOSE,
            )
            match = False
            if PROP_ENABLED in self._filter_prop_ids and entry.enabled:
                match = True
            if PROP_DISABLED in self._filter_prop_ids and not entry.enabled:
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

        return True


class _DropTreeView(QTreeView):
    """QTreeView that accepts external archive file drops in addition to internal DnD."""

    archives_dropped = Signal(list)  # list of file path strings

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed_separators: set[str] = set()

    def _apply_separator_filter(self):
        """Recalculate which rows to hide based on collapsed separators."""
        proxy = self.model()
        if not isinstance(proxy, ModListProxyModel):
            return
        source = proxy.sourceModel()
        if not source:
            return

        hidden: set[int] = set()
        current_sep_collapsed = False

        for row in range(source.rowCount()):
            idx = source.index(row, 0)
            is_sep = source.data(idx, ROLE_IS_SEPARATOR)
            folder = source.data(idx, ROLE_FOLDER_NAME) or ""

            if is_sep:
                current_sep_collapsed = folder in self._collapsed_separators
            elif current_sep_collapsed:
                hidden.add(row)

        proxy.set_hidden_rows(hidden)

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
    context_menu_requested = Signal(QPoint)  # global pos for context menu
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tree = _DropTreeView()
        self._tree.archives_dropped.connect(self.archives_dropped)
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
        self._persistent_header = PersistentHeader(
            header, "modlist", fixed_columns=frozenset({COL_CHECK}),
        )

        # ── Frameworks section (below mod list) ──────────────────
        fw_container = QWidget()
        fw_layout = QVBoxLayout(fw_container)
        fw_layout.setContentsMargins(0, 0, 0, 0)
        fw_layout.setSpacing(0)

        self._fw_tree = QTreeWidget()

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
            self._fw_tree.addTopLevelItem(item)

    def restore_framework_widths(self) -> None:
        """Restore saved column widths for the frameworks tree."""
        self._ph_frameworks.restore()

    def get_current_mod_name(self):
        """Liefert den Mod-Namen der aktuell gewählten Zeile oder None."""
        proxy_idx = self._tree.currentIndex()
        if not proxy_idx.isValid() or proxy_idx.row() < 0:
            return None
        source_idx = self._proxy_model.mapToSource(proxy_idx)
        name = self._source_model.data(self._source_model.index(source_idx.row(), COL_NAME), Qt.ItemDataRole.DisplayRole)
        return name if name is not None else None

    def get_selected_source_rows(self) -> list[int]:
        """Return sorted list of selected source-model row indices."""
        rows = set()
        for proxy_idx in self._tree.selectionModel().selectedRows():
            source_idx = self._proxy_model.mapToSource(proxy_idx)
            rows.add(source_idx.row())
        return sorted(rows)
