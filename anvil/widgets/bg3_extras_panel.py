"""BG3 Extras panel: Frameworks + Data-Overrides (read-only display)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QBrush, QColor

from anvil.core.persistent_header import PersistentHeader
from anvil.core.translator import tr
from anvil.widgets.collapsible_bar import CollapsibleSectionBar


class BG3ExtrasPanel(QWidget):
    """Shows BG3 Frameworks and Data-Overrides.

    Signals:
        context_menu_requested(QPoint, dict): (global_pos, item_data)
    """

    context_menu_requested = Signal(QPoint, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._extras_tree = QTreeWidget()

        self._extras_label = CollapsibleSectionBar(
            tr("label.section_extras"), "bg3_extras", self._extras_tree,
            style="QLabel { font-weight: bold; padding: 4px 6px; "
                  "background: #1a2a3a; border-bottom: 1px solid #333; }",
            container=self,
        )
        self._extras_label.set_count(0)
        layout.addWidget(self._extras_label)

        self._extras_tree.setHeaderLabels([
            tr("label.name"),
            tr("game_panel.header_type"),
            tr("game_panel.header_status"),
        ])
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
        self._extras_tree.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._extras_tree)

    # -- Public API ---------------------------------------------------

    def load_extras(
        self,
        data_overrides: list[dict] | None = None,
        frameworks: list[dict] | None = None,
    ) -> None:
        """Populate the extras tree with data-overrides and frameworks."""
        self._extras_tree.clear()
        overrides = data_overrides or []
        fws = frameworks or []
        total = len(overrides) + len(fws)
        self._extras_label.set_count(total)

        # Frameworks first
        for fw in fws:
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
        for ov in overrides:
            item = QTreeWidgetItem()
            item.setText(0, ov.get("name", "?"))
            item.setText(1, tr("label.type_data_override"))
            file_count = len(ov.get("files", []))
            item.setText(2, tr("label.files_count", count=file_count))
            item.setData(0, Qt.ItemDataRole.UserRole, {"type": "data_override", **ov})
            item.setForeground(1, QBrush(QColor("#64B5F6")))
            self._extras_tree.addTopLevelItem(item)

    def flush_column_widths(self) -> None:
        """Flush pending column width writes."""
        self._ph_extras.flush()

    def restore_column_widths(self) -> None:
        """Restore saved column widths."""
        self._ph_extras.restore()

    # -- Private ------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        """Emit context menu for extras section."""
        global_pos = self._extras_tree.viewport().mapToGlobal(pos)
        item = self._extras_tree.itemAt(pos)
        mod_data: dict = {}
        if item:
            mod_data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        self.context_menu_requested.emit(global_pos, mod_data)
