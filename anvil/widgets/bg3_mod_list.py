"""BG3-specific mod list widget: unified mod list + extras with QSplitter."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QSplitter,
    QStyledItemDelegate,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QPoint, QRect, QSize, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen

from anvil.core.persistent_header import PersistentHeader
from anvil.core.translator import tr
from anvil.widgets.collapsible_bar import CollapsibleSectionBar
from anvil.models.bg3_mod_list_model import (
    BG3ModListModel,
    BG3ModRow,
    COL_AUTHOR,
    COL_CHECK,
    COL_CONFLICTS,
    COL_NAME,
    COL_VERSION,
    MIME_BG3_MOD_ROWS,
)

# Extensions accepted for external drops
_DROP_EXTENSIONS = {".pak", ".zip", ".rar", ".7z"}


# -- Checkbox delegate (same style as standard mod list) ----------------------

class _BG3CheckboxDelegate(QStyledItemDelegate):
    """Green circle+check (enabled) / gray circle (disabled)."""

    _COLOR_ON = QColor("#4CAF50")
    _COLOR_OFF = QColor("#666666")

    def paint(self, painter: QPainter, option, index):
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else None
        if style:
            style.drawPrimitive(
                style.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget,
            )

        check = index.data(Qt.ItemDataRole.CheckStateRole)
        enabled = check == Qt.CheckState.Checked

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

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
        if event.type() == event.Type.MouseButtonRelease:
            current = index.data(Qt.ItemDataRole.CheckStateRole)
            new_val = (
                Qt.CheckState.Unchecked
                if current == Qt.CheckState.Checked
                else Qt.CheckState.Checked
            )
            model.setData(index, new_val.value, Qt.ItemDataRole.CheckStateRole)
            return True
        if event.type() == event.Type.MouseButtonDblClick:
            return True
        return False


# -- Drop-enabled QTreeView --------------------------------------------------

class _BG3DropTreeView(QTreeView):
    """QTreeView that accepts external archives and internal DnD reorder."""

    archives_dropped = Signal(list)   # list of file path strings

    def dragEnterEvent(self, event):
        super().dragEnterEvent(event)
        md = event.mimeData()
        if md.hasFormat(MIME_BG3_MOD_ROWS):
            event.acceptProposedAction()
            return
        if md.hasUrls():
            for url in md.urls():
                if url.isLocalFile():
                    if Path(url.toLocalFile()).suffix.lower() in _DROP_EXTENSIONS:
                        event.acceptProposedAction()
                        return

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        md = event.mimeData()
        if md.hasFormat(MIME_BG3_MOD_ROWS):
            event.acceptProposedAction()
            return
        if md.hasUrls():
            event.acceptProposedAction()
            return

    def dropEvent(self, event):
        md = event.mimeData()
        # External archives
        if md.hasUrls():
            paths = []
            for url in md.urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if Path(path).suffix.lower() in _DROP_EXTENSIONS:
                        paths.append(path)
            if paths:
                event.acceptProposedAction()
                self.archives_dropped.emit(paths)
                return
        # Internal DnD (reorder within same tree)
        super().dropEvent(event)


# -- Helper: configure a tree view -------------------------------------------

def _setup_tree(
    tree: _BG3DropTreeView,
    model: BG3ModListModel,
    settings_key: str,
) -> PersistentHeader:
    """Apply common settings to a BG3 mod tree view.

    Returns the PersistentHeader so the caller can keep a reference.
    """
    proxy = QSortFilterProxyModel(tree)
    proxy.setSourceModel(model)
    tree.setModel(proxy)

    tree.setRootIsDecorated(False)
    tree.setAlternatingRowColors(True)
    tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    tree.setUniformRowHeights(True)
    tree.setAcceptDrops(True)
    tree.setDragEnabled(True)
    tree.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
    tree.setDefaultDropAction(Qt.DropAction.MoveAction)
    tree.setDropIndicatorShown(True)
    tree.setDragDropOverwriteMode(False)

    # Context menu
    tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    # Delegate for checkbox column
    delegate = _BG3CheckboxDelegate(tree)
    tree.setItemDelegateForColumn(COL_CHECK, delegate)

    # Column widths
    header = tree.header()
    header.setStretchLastSection(False)
    header.setCascadingSectionResizes(True)
    header.setMinimumSectionSize(30)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setSectionResizeMode(COL_CHECK, QHeaderView.ResizeMode.Fixed)
    tree.setColumnWidth(COL_CHECK, 36)
    tree.setColumnWidth(COL_CONFLICTS, 60)
    tree.setColumnWidth(COL_NAME, 280)
    tree.setColumnWidth(COL_VERSION, 120)
    tree.setColumnWidth(COL_AUTHOR, 140)

    ph = PersistentHeader(header, settings_key, fixed_columns=frozenset({COL_CHECK}))

    return ph


# -- Main widget -------------------------------------------------------------

class BG3ModListView(QWidget):
    """BG3 mod list with unified mods + extras.

    Signals:
        archives_dropped(list): External archive paths dropped.
        mod_activated(str): UUID of mod to activate.
        mod_deactivated(str): UUID of mod to deactivate.
        mods_reordered(list): New UUID order for active mods.
        context_menu_requested(QPoint, str, dict): (global_pos, section, mod_data)
            section is 'mods' or 'extras'.
            mod_data is a dict with uuid, name, filename or empty if no selection.
        data_override_uninstall(str): mod_name to uninstall.
    """

    archives_dropped = Signal(list)
    mod_activated = Signal(str)
    mod_deactivated = Signal(str)
    mods_reordered = Signal(list)
    context_menu_requested = Signal(QPoint, str, dict)
    data_override_uninstall = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # -- Splitter -------------------------------------------------
        self._splitter = QSplitter(Qt.Orientation.Vertical)

        # -- Unified mod list section ---------------------------------
        mods_pane = QWidget()
        mods_layout = QVBoxLayout(mods_pane)
        mods_layout.setContentsMargins(0, 0, 0, 0)
        mods_layout.setSpacing(0)

        self._mod_model = BG3ModListModel(allow_reorder=True)
        self._mod_tree = _BG3DropTreeView()

        self._ph_mods = _setup_tree(
            self._mod_tree, self._mod_model,
            settings_key="bg3_mods",
        )
        mods_layout.addWidget(self._mod_tree)

        self._splitter.addWidget(mods_pane)

        # -- Extras section (Data-Overrides & Frameworks) -- UNCHANGED
        extras_pane = QWidget()
        extras_layout = QVBoxLayout(extras_pane)
        extras_layout.setContentsMargins(0, 0, 0, 0)
        extras_layout.setSpacing(0)

        self._extras_tree = QTreeWidget()

        self._extras_label = CollapsibleSectionBar(
            tr("label.section_extras"), "bg3_extras", self._extras_tree,
            style="QLabel { font-weight: bold; padding: 4px 6px; "
                  "background: #1a2a3a; border-bottom: 1px solid #333; }",
            container=extras_pane,
        )
        self._extras_label.set_count(0)
        extras_layout.addWidget(self._extras_label)
        self._extras_tree.setHeaderLabels([tr("label.name"), tr("game_panel.header_type"), tr("game_panel.header_status")])
        self._extras_tree.setRootIsDecorated(False)
        self._extras_tree.setAlternatingRowColors(True)
        self._extras_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._extras_tree.setUniformRowHeights(True)
        self._extras_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        extras_hdr = self._extras_tree.header()
        extras_hdr.setStretchLastSection(False)
        extras_hdr.setCascadingSectionResizes(True)
        extras_hdr.setMinimumSectionSize(30)
        extras_hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._extras_tree.setColumnWidth(0, 280)
        self._extras_tree.setColumnWidth(1, 100)
        self._ph_extras = PersistentHeader(extras_hdr, "bg3_extras")
        self._extras_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._extras_tree.customContextMenuRequested.connect(self._on_extras_context_menu)
        extras_layout.addWidget(self._extras_tree)

        extras_pane.setMinimumHeight(28)
        self._extras_pane = extras_pane
        self._splitter.addWidget(extras_pane)

        # Default splitter proportions: 85% mods, 15% extras
        self._splitter.setSizes([600, 100])
        self._splitter.setChildrenCollapsible(False)
        self._splitter.splitterMoved.connect(self._on_extras_splitter_moved)

        layout.addWidget(self._splitter)

        # -- Connect signals ------------------------------------------
        self._mod_tree.archives_dropped.connect(self.archives_dropped)

        # Checkbox toggle: emit mod_activated or mod_deactivated
        self._mod_model.mod_toggled.connect(self._on_mod_toggled)

        # Reorder in mod list
        self._mod_model.mods_reordered.connect(self._on_reorder)

        # Context menu
        self._mod_tree.customContextMenuRequested.connect(
            lambda pos: self._emit_context_menu(self._mod_tree, pos, "mods"),
        )

    # -- Public API ---------------------------------------------------

    def load_mods(
        self,
        mods: list[dict],
        data_overrides: list[dict] | None = None,
        frameworks: list[dict] | None = None,
    ) -> None:
        """Populate unified mod list and extras from installer data.

        Each mod dict must have an 'enabled' field.
        """
        rows = [self._dict_to_row(m) for m in mods]
        self._mod_model.set_mods(rows)

        # Extras section
        overrides = data_overrides or []
        fws = frameworks or []
        self._load_extras(overrides, fws)

    def get_active_uuid_order(self) -> list[str]:
        """Return UUID list of active (enabled) mods in current order."""
        return self._mod_model.get_active_uuid_order()

    def mod_header(self) -> QHeaderView:
        """Return the mod tree header for state persistence."""
        return self._mod_tree.header()

    def extras_header(self) -> QHeaderView:
        """Return the extras tree header for state persistence."""
        return self._extras_tree.header()

    def restore_column_widths(self) -> None:
        """Restore saved column widths for both trees."""
        self._ph_mods.restore()
        self._ph_extras.restore()

    def flush_column_widths(self) -> None:
        """Flush any pending debounced column-width writes."""
        self._ph_mods.flush()
        self._ph_extras.flush()

    def get_selected_mod(self, section: str = "mods") -> dict:
        """Return data for the selected mod in the given section."""
        if section == "extras":
            return self._get_selected_extra()
        tree = self._mod_tree
        model = self._mod_model
        proxy = tree.model()

        proxy_idx = tree.currentIndex()
        if not proxy_idx.isValid():
            return {}

        source_idx = proxy.mapToSource(proxy_idx)
        row = model.row_data(source_idx.row())
        if row is None:
            return {}

        return {
            "uuid": row.uuid,
            "name": row.name,
            "filename": row.filename,
            "folder": row.folder,
            "enabled": row.enabled,
        }

    def get_selected_source_rows(self, section: str = "mods") -> list[int]:
        """Return sorted source row indices for the mod tree."""
        tree = self._mod_tree
        proxy = tree.model()
        rows = set()
        for proxy_idx in tree.selectionModel().selectedRows():
            source_idx = proxy.mapToSource(proxy_idx)
            rows.add(source_idx.row())
        return sorted(rows)

    # -- Private: extras section --------------------------------------

    def _load_extras(self, data_overrides: list[dict], frameworks: list[dict]) -> None:
        """Populate the extras tree with data-overrides and frameworks."""
        self._extras_tree.clear()
        total = len(data_overrides) + len(frameworks)
        self._extras_label.set_count(total)

        # Frameworks first
        for fw in frameworks:
            item = QTreeWidgetItem()
            item.setText(0, fw.get("name", "?"))
            item.setText(1, tr("label.type_framework"))
            installed = fw.get("installed", False)
            item.setText(2, tr("game_panel.installed") if installed else tr("game_panel.not_installed"))
            item.setData(0, Qt.ItemDataRole.UserRole, {"type": "framework", **fw})
            if installed:
                item.setForeground(2, QBrush(QColor("#4CAF50")))
            else:
                item.setForeground(2, QBrush(QColor("#F44336")))
            self._extras_tree.addTopLevelItem(item)

        # Data overrides
        for ov in data_overrides:
            item = QTreeWidgetItem()
            item.setText(0, ov.get("name", "?"))
            item.setText(1, tr("label.type_data_override"))
            file_count = len(ov.get("files", []))
            item.setText(2, tr("label.files_count", count=file_count))
            item.setData(0, Qt.ItemDataRole.UserRole, {"type": "data_override", **ov})
            item.setForeground(1, QBrush(QColor("#64B5F6")))
            self._extras_tree.addTopLevelItem(item)

    def _get_selected_extra(self) -> dict:
        """Return data for the selected extras item."""
        item = self._extras_tree.currentItem()
        if item is None:
            return {}
        return item.data(0, Qt.ItemDataRole.UserRole) or {}

    def _on_extras_context_menu(self, pos) -> None:
        """Emit context menu for extras section."""
        global_pos = self._extras_tree.viewport().mapToGlobal(pos)
        item = self._extras_tree.itemAt(pos)
        mod_data: dict = {}
        if item:
            mod_data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        self.context_menu_requested.emit(global_pos, "extras", mod_data)

    # -- Private slots ------------------------------------------------

    def _on_mod_toggled(self, row: int, enabled: bool) -> None:
        """Mod checkbox toggled: emit activate or deactivate signal."""
        rd = self._mod_model.row_data(row)
        if rd and rd.uuid:
            if enabled:
                self.mod_activated.emit(rd.uuid)
            else:
                self.mod_deactivated.emit(rd.uuid)

    def _on_reorder(self) -> None:
        """Mods reordered via DnD."""
        self.mods_reordered.emit(self._mod_model.get_uuid_order())

    def _emit_context_menu(self, tree: QTreeView, pos, section: str) -> None:
        """Emit context_menu_requested with mod data."""
        global_pos = tree.viewport().mapToGlobal(pos)
        proxy = tree.model()
        model = self._mod_model

        proxy_idx = tree.indexAt(pos)
        mod_data: dict = {}
        if proxy_idx.isValid():
            source_idx = proxy.mapToSource(proxy_idx)
            rd = model.row_data(source_idx.row())
            if rd:
                mod_data = {
                    "uuid": rd.uuid,
                    "name": rd.name,
                    "filename": rd.filename,
                    "folder": rd.folder,
                    "enabled": rd.enabled,
                }

        self.context_menu_requested.emit(global_pos, section, mod_data)

    def _on_extras_splitter_moved(self) -> None:
        """Hide/show extras tree based on available space (respects collapsed state)."""
        if not self._extras_label.collapsed:
            self._extras_tree.setVisible(self._extras_pane.height() > 60)

    def _on_filter_changed(self, text: str) -> None:
        """Apply text filter to the mod proxy model."""
        proxy = self._mod_tree.model()
        if isinstance(proxy, QSortFilterProxyModel):
            proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            proxy.setFilterKeyColumn(COL_NAME)
            proxy.setFilterFixedString(text)

    # -- Helpers ------------------------------------------------------

    @staticmethod
    def _dict_to_row(mod: dict) -> BG3ModRow:
        """Convert an installer dict to a BG3ModRow."""
        return BG3ModRow(
            uuid=mod.get("uuid", ""),
            name=mod.get("name", ""),
            folder=mod.get("folder", ""),
            author=mod.get("author", ""),
            version=mod.get("version", mod.get("version64", "")),
            filename=mod.get("filename", ""),
            enabled=mod.get("enabled", False),
            conflicts=mod.get("conflicts", ""),
            dependencies=mod.get("dependencies", []),
            source=mod.get("source", ""),
        )
