"""Dialog zum Verwalten von Kategorien (Neu / Umbenennen / Löschen)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QVBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QPushButton,
    QInputDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, QSettings

from anvil.core.categories import CategoryManager
from anvil.core.mod_entry import ModEntry
from anvil.core.mod_metadata import write_meta_ini
from anvil.core.translator import tr


class CategoryDialog(QDialog):
    """Modal dialog for managing categories.

    Layout:
        Left:  QTreeWidget with columns ID | Name | Mods | Quelle
        Right: Buttons — Neu, Umbenennen, Löschen
        Bottom: Schließen
    """

    def __init__(
        self,
        category_manager: CategoryManager,
        mod_entries: list[ModEntry],
        default_category_ids: set[int] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.categories_title"))
        self.setMinimumSize(1380, 800)
        self.resize(1380, 800)
        self._cat_mgr = category_manager
        self._mod_entries = mod_entries
        self._default_ids: set[int] = default_category_ids or set()
        self._was_shown = False

        # ── Layout ─────────────────────────────────────────────────
        outer = QVBoxLayout(self)

        body = QHBoxLayout()

        # Left: category tree
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels([tr("label.header_id"), tr("label.name"), tr("label.header_mods"), tr("label.header_source"), tr("label.header_nexus_category")])
        self._tree.setRootIsDecorated(False)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._tree.setAllColumnsShowFocus(True)
        self._tree.setSortingEnabled(True)

        # Column widths — all Interactive (resizable by mouse), like mod_list.py
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setCascadingSectionResizes(True)
        header.setMinimumSectionSize(30)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._tree.setColumnWidth(0, 50)    # ID
        self._tree.setColumnWidth(1, 300)   # Name
        self._tree.setColumnWidth(2, 60)    # Mods
        self._tree.setColumnWidth(3, 90)    # Quelle
        self._tree.setColumnWidth(4, 150)   # Nexus Kategorie

        body.addWidget(self._tree, 1)

        # Right: action buttons
        btn_col = QVBoxLayout()
        btn_new = QPushButton(tr("button.new"))
        btn_rename = QPushButton(tr("button.rename"))
        btn_delete = QPushButton(tr("button.delete"))
        btn_col.addWidget(btn_new)
        btn_col.addWidget(btn_rename)
        btn_col.addWidget(btn_delete)
        btn_col.addStretch(1)
        body.addLayout(btn_col)

        outer.addLayout(body, 1)

        # Bottom: close button
        btn_close = QPushButton(tr("button.close"))
        btn_close.setDefault(True)
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_row.addWidget(btn_close)
        outer.addLayout(close_row)

        # ── Connections ────────────────────────────────────────────
        btn_new.clicked.connect(self._on_new)
        btn_rename.clicked.connect(self._on_rename)
        btn_delete.clicked.connect(self._on_delete)
        btn_close.clicked.connect(self.accept)

        # Initial fill
        self._refresh_table()

        # Persist column widths
        header.sectionResized.connect(self._save_column_widths)

        # Sort by name initially
        self._tree.sortByColumn(1, Qt.SortOrder.AscendingOrder)

    # ── Overrides ─────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if not self._was_shown:
            self._was_shown = True
            self.resize(1380, 800)
            # Restore saved column widths
            settings = QSettings()
            widths = settings.value("CategoryDialog/columnWidths")
            if widths and len(widths) == self._tree.columnCount():
                for i, w in enumerate(widths):
                    self._tree.setColumnWidth(i, int(w))

    # ── Helpers ────────────────────────────────────────────────────

    def _save_column_widths(self) -> None:
        """Persist current column widths to QSettings."""
        header = self._tree.header()
        widths = [header.sectionSize(i) for i in range(header.count())]
        QSettings().setValue("CategoryDialog/columnWidths", widths)

    def _mod_count(self, cat_id: int) -> int:
        """Return how many mods reference *cat_id*."""
        return sum(1 for m in self._mod_entries if cat_id in m.category_ids)

    def _refresh_table(self) -> None:
        """Rebuild the tree widget from the CategoryManager."""
        self._tree.clear()
        for cat in self._cat_mgr.all_categories():
            cat_id = cat["id"]
            count = self._mod_count(cat_id)
            source = tr("label.source_standard") if cat_id in self._default_ids else tr("label.source_custom")
            item = QTreeWidgetItem()
            item.setData(0, Qt.ItemDataRole.DisplayRole, cat_id)
            item.setText(1, cat["name"])
            item.setData(2, Qt.ItemDataRole.DisplayRole, count)
            item.setText(3, source)
            item.setText(4, "-")
            item.setData(0, Qt.ItemDataRole.UserRole, cat_id)
            item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)
            self._tree.addTopLevelItem(item)

    def _selected_id(self) -> int | None:
        """Return the category ID of the selected item, or None."""
        items = self._tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.ItemDataRole.UserRole)

    # ── Actions ────────────────────────────────────────────────────

    def _on_new(self) -> None:
        name, ok = QInputDialog.getText(
            self, tr("dialog.new_category"), tr("label.name") + ":"
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        new_id = self._cat_mgr.add_category(name)
        if new_id == 0:
            QMessageBox.warning(
                self,
                tr("dialog.category_exists"),
                tr("dialog.category_exists_message", name=name),
            )
            return
        self._refresh_table()

    def _on_rename(self) -> None:
        cat_id = self._selected_id()
        if cat_id is None:
            QMessageBox.information(
                self, tr("dialog.no_selection"), tr("dialog.select_category_first")
            )
            return
        old_name = self._cat_mgr.get_name(cat_id)
        new_name, ok = QInputDialog.getText(
            self, tr("dialog.rename_category"), tr("dialog.rename_mod_prompt"), text=old_name
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        if new_name == old_name:
            return
        # Check duplicate
        existing_id = self._cat_mgr.get_id(new_name)
        if existing_id != 0 and existing_id != cat_id:
            QMessageBox.warning(
                self,
                tr("dialog.name_taken"),
                tr("dialog.category_exists_message", name=new_name),
            )
            return
        self._cat_mgr.rename_category(cat_id, new_name)
        self._refresh_table()

    def _on_delete(self) -> None:
        cat_id = self._selected_id()
        if cat_id is None:
            QMessageBox.information(
                self, tr("dialog.no_selection"), tr("dialog.select_category_first")
            )
            return
        cat_name = self._cat_mgr.get_name(cat_id)
        count = self._mod_count(cat_id)
        msg = tr("dialog.delete_category_confirm", name=cat_name)
        if count > 0:
            msg += "\n\n" + tr("dialog.delete_category_with_mods", count=count)

        answer = QMessageBox.question(
            self,
            tr("dialog.delete_category_title"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        # Remove category ID from all mods that reference it
        for mod in self._mod_entries:
            if cat_id in mod.category_ids:
                mod.category_ids.remove(cat_id)
                if mod.primary_category == cat_id:
                    mod.primary_category = mod.category_ids[0] if mod.category_ids else 0
                # Update category string and persist to meta.ini
                mod.category = ",".join(str(cid) for cid in mod.category_ids)
                if mod.install_path is not None:
                    write_meta_ini(mod.install_path, {"category": mod.category})

        self._cat_mgr.remove_category(cat_id)
        self._refresh_table()
