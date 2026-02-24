"""Instanz Manager Dialog — MO2-Stil mit QSplitter."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QListView, QLineEdit, QPushButton, QLabel, QWidget, QFrame,
    QAbstractItemView, QMessageBox, QStyle,
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon, QDesktopServices
from PySide6.QtCore import Qt, QSortFilterProxyModel, QSettings, QModelIndex, QUrl, QSize

from anvil.core.instance_manager import InstanceManager
from anvil.core.ui_helpers import get_text_input
from anvil.core.icon_manager import IconManager, placeholder_game_icon
from anvil.plugins.plugin_loader import PluginLoader
from anvil.core.translator import tr

_ICONS_DIR = Path(__file__).resolve().parent.parent / "styles" / "icons"

_DIALOG_STYLE = """
QDialog { background: #1C1C1C; }
QWidget { background: #1C1C1C; color: #D3D3D3; }
QLineEdit, QPushButton {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 4px;
}
QListView {
    background: #141414;
    alternate-background-color: #1C1C1C;
    border-radius: 6px;
    border: none;
    color: #D3D3D3;
}
QListView::item { padding: 4px; }
QListView::item:selected { background: #3D3D3D; color: #D3D3D3; }
QPushButton#deleteInstance { background: #5a2020; color: #D3D3D3; }
QPushButton#deleteInstance:hover { background: #7a2828; }
QPushButton#exploreBtn {
    background: transparent;
    border: none;
    padding: 2px;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    font-size: 18px;
    color: #E8B84B;
}
QPushButton#exploreBtn:hover { background: #3D3D3D; }
QSplitter::handle { background: #3D3D3D; }
QSplitter::handle:horizontal { width: 3px; }
QPushButton#createBtn {
    background: #006868;
    color: #FFF;
    font-weight: bold;
}
QPushButton#createBtn:hover { background: #008585; }
"""


class InstanceManagerDialog(QDialog):
    """Dialog for managing game instances (MO2-style)."""

    switched_to: str | None = None

    def __init__(
        self,
        parent=None,
        instance_manager: InstanceManager | None = None,
        plugin_loader: PluginLoader | None = None,
        icon_manager: IconManager | None = None,
        *,
        welcome: bool = False,
    ):
        super().__init__(parent)
        self._im = instance_manager
        self._pl = plugin_loader
        self._icons = icon_manager
        self._welcome = welcome
        self.switched_to = None

        self.setWindowTitle(tr("instance.manager_title"))
        self.setMinimumSize(800, 500)
        self.setStyleSheet(_DIALOG_STYLE)

        self._setup_ui()
        self._restore_geometry()
        self._refresh_list()

    def _setup_ui(self) -> None:
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Welcome hint
        if self._welcome:
            self._welcome_label = QLabel(tr("instance.welcome_hint"))
            self._welcome_label.setStyleSheet("color: #4FC3F7; font-size: 13px; padding: 6px 0;")
            self._welcome_label.setWordWrap(True)
            layout.addWidget(self._welcome_label)

        # Top bar with "New Instance" button (above splitter)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        self._new_btn = QPushButton("+ " + tr("instance.btn_new"))
        self._new_btn.setObjectName("createBtn")
        self._new_btn.clicked.connect(self._on_new_instance)
        top_bar.addWidget(self._new_btn)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Main splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: List + Filter
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self._model = QStandardItemModel()
        self._proxy_model = QSortFilterProxyModel()
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._list_view = QListView()
        self._list_view.setModel(self._proxy_model)
        self._list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._list_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list_view.selectionModel().currentChanged.connect(self._on_selection_changed)
        self._list_view.doubleClicked.connect(self._on_switch)
        left_layout.addWidget(self._list_view)

        # Filter field (below list)
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText(tr("instance.filter_placeholder"))
        self._filter_edit.textChanged.connect(self._on_filter_changed)
        left_layout.addWidget(self._filter_edit)

        self._splitter.addWidget(left_widget)

        # Right panel: Details
        right_widget = QFrame()
        right_widget.setFrameShape(QFrame.Shape.NoFrame)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(12, 0, 0, 0)

        self._details_label = QLabel(tr("instance.details_header"))
        self._details_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 8px;")
        right_layout.addWidget(self._details_label)

        form = QGridLayout()
        form.setSpacing(8)
        form.setColumnStretch(1, 1)  # Spalte 1 (LineEdits) stretcht

        # Zeile 0: Name
        name_label = QLabel(tr("instance.label_name"))
        form.addWidget(name_label, 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._name_edit = QLineEdit()
        self._name_edit.setReadOnly(True)
        form.addWidget(self._name_edit, 0, 1)
        self._rename_btn = QPushButton(tr("instance.btn_rename"))
        self._rename_btn.clicked.connect(self._on_rename)
        form.addWidget(self._rename_btn, 0, 2)

        # Zeile 1: Speicherort
        loc_label = QLabel(tr("instance.label_location"))
        form.addWidget(loc_label, 1, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._location_edit = QLineEdit()
        self._location_edit.setReadOnly(True)
        form.addWidget(self._location_edit, 1, 1)
        self._location_btn = QPushButton()
        self._location_btn.setIcon(QIcon("anvil/assets/icons/ui/ordner.png"))
        self._location_btn.setIconSize(QSize(24, 24))
        self._location_btn.setObjectName("exploreBtn")
        self._location_btn.setToolTip(tr("instance.explore_location"))
        self._location_btn.clicked.connect(lambda: self._on_explore("location"))
        form.addWidget(self._location_btn, 1, 2)

        # Zeile 2: Basisverzeichnis
        base_label = QLabel(tr("instance.label_base"))
        form.addWidget(base_label, 2, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._base_edit = QLineEdit()
        self._base_edit.setReadOnly(True)
        form.addWidget(self._base_edit, 2, 1)
        self._base_btn = QPushButton()
        self._base_btn.setIcon(QIcon("anvil/assets/icons/ui/ordner.png"))
        self._base_btn.setIconSize(QSize(24, 24))
        self._base_btn.setObjectName("exploreBtn")
        self._base_btn.setToolTip(tr("instance.explore_base"))
        self._base_btn.clicked.connect(lambda: self._on_explore("base"))
        form.addWidget(self._base_btn, 2, 2)

        # Zeile 3: Spielpfad
        game_label = QLabel(tr("instance.label_game_path"))
        form.addWidget(game_label, 3, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._game_path_edit = QLineEdit()
        self._game_path_edit.setReadOnly(True)
        form.addWidget(self._game_path_edit, 3, 1)
        self._game_path_btn = QPushButton()
        self._game_path_btn.setIcon(QIcon("anvil/assets/icons/ui/ordner.png"))
        self._game_path_btn.setIconSize(QSize(24, 24))
        self._game_path_btn.setObjectName("exploreBtn")
        self._game_path_btn.setToolTip(tr("instance.explore_game"))
        self._game_path_btn.clicked.connect(lambda: self._on_explore("game"))
        form.addWidget(self._game_path_btn, 3, 2)

        right_layout.addLayout(form)

        # Delete button at bottom of details section
        actions_row = QHBoxLayout()
        self._delete_btn = QPushButton("\u2715 " + tr("instance.btn_delete"))
        self._delete_btn.setObjectName("deleteInstance")
        self._delete_btn.clicked.connect(self._on_delete)
        actions_row.addWidget(self._delete_btn)
        actions_row.addStretch()
        right_layout.addLayout(actions_row)

        right_layout.addStretch()

        self._splitter.addWidget(right_widget)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 2)

        layout.addWidget(self._splitter, 1)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_layout.addStretch()

        self._switch_btn = QPushButton(tr("instance.btn_switch"))
        self._switch_btn.setMinimumHeight(32)
        self._switch_btn.setMinimumWidth(100)
        self._switch_btn.clicked.connect(self._on_switch)
        btn_layout.addWidget(self._switch_btn)

        self._ok_btn = QPushButton(tr("button.ok"))
        self._ok_btn.setObjectName("createBtn")
        self._ok_btn.setMinimumHeight(32)
        self._ok_btn.setMinimumWidth(80)
        self._ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self._ok_btn)

        layout.addLayout(btn_layout)

    # ── List Management ───────────────────────────────────────────────

    def _refresh_list(self) -> None:
        """Reload instance list from disk."""
        self._model.clear()
        if self._im is None:
            return

        current = self._im.current_instance()

        for inst in self._im.list_instances():
            name = inst["name"]
            label = f"\u25CF {name}" if name == current else name

            item = QStandardItem(label)
            item.setData(name, Qt.ItemDataRole.UserRole)

            # Game icon
            gsn = inst.get("game_short_name", "")
            icon_pix = self._icons.get_game_icon(gsn) if self._icons and gsn else None
            if icon_pix is not None:
                item.setIcon(QIcon(icon_pix))
            else:
                item.setIcon(QIcon(placeholder_game_icon(32)))

            self._model.appendRow(item)

        # Select current instance
        if self._model.rowCount() > 0:
            for row in range(self._model.rowCount()):
                idx = self._model.index(row, 0)
                if idx.data(Qt.ItemDataRole.UserRole) == current:
                    proxy_idx = self._proxy_model.mapFromSource(idx)
                    self._list_view.setCurrentIndex(proxy_idx)
                    return
            self._list_view.setCurrentIndex(self._proxy_model.index(0, 0))

    def _selected_name(self) -> str | None:
        """Return selected instance name."""
        idx = self._list_view.currentIndex()
        if not idx.isValid():
            return None
        source_idx = self._proxy_model.mapToSource(idx)
        return source_idx.data(Qt.ItemDataRole.UserRole)

    def _is_active_selected(self) -> bool:
        """Check if the selected instance is the active one."""
        name = self._selected_name()
        if name is None or self._im is None:
            return False
        return name == self._im.current_instance()

    def _update_button_states(self) -> None:
        """Enable/disable buttons based on selection."""
        is_active = self._is_active_selected()
        has_selection = self._selected_name() is not None

        self._rename_btn.setEnabled(has_selection and not is_active)
        self._delete_btn.setEnabled(has_selection and not is_active)
        self._switch_btn.setEnabled(has_selection and not is_active)

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_filter_changed(self, text: str) -> None:
        """Filter the instance list."""
        self._proxy_model.setFilterFixedString(text)

    def _on_selection_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        """Update details panel when selection changes."""
        self._update_button_states()

        if not current.isValid() or self._im is None:
            self._clear_details()
            return

        source_idx = self._proxy_model.mapToSource(current)
        name = source_idx.data(Qt.ItemDataRole.UserRole)
        data = self._im.load_instance(name)
        if not data:
            self._clear_details()
            return

        self._name_edit.setText(name)
        self._name_edit.setReadOnly(self._is_active_selected())

        self._location_edit.setText(str(self._im.instances_path() / name))
        self._base_edit.setText(str(self._im.instances_path() / name))
        self._game_path_edit.setText(data.get("game_path", "") or "\u2014")

    def _clear_details(self) -> None:
        """Clear the details panel."""
        self._name_edit.clear()
        self._location_edit.clear()
        self._base_edit.clear()
        self._game_path_edit.clear()

    def _on_new_instance(self) -> None:
        """Stub: Opens CreateInstanceWizard. Backend-Dev fills."""
        from anvil.widgets.instance_wizard import CreateInstanceWizard
        wizard = CreateInstanceWizard(self, self._im, self._pl, self._icons)
        if wizard.exec() == QDialog.DialogCode.Accepted and wizard.created_instance:
            self._refresh_list()
            self._select_instance(wizard.created_instance)
            self.switched_to = wizard.created_instance

    def _select_instance(self, name: str) -> None:
        """Select an instance by name in the list."""
        for row in range(self._model.rowCount()):
            idx = self._model.index(row, 0)
            if idx.data(Qt.ItemDataRole.UserRole) == name:
                proxy_idx = self._proxy_model.mapFromSource(idx)
                self._list_view.setCurrentIndex(proxy_idx)
                return

    def _on_rename(self) -> None:
        """Renames inactive instance."""
        name = self._selected_name()
        if name is None or self._im is None or self._is_active_selected():
            return

        new_name, ok = get_text_input(
            self,
            tr("instance.btn_rename"),
            tr("instance.label_name"),
            text=name,
        )

        if not ok or not new_name.strip() or new_name.strip() == name:
            return

        new_name = new_name.strip()

        # Check if name exists
        existing = {inst["name"] for inst in self._im.list_instances()}
        if new_name in existing:
            QMessageBox.warning(
                self,
                tr("instance.btn_rename"),
                tr("wizard.name_exists", name=new_name),
            )
            return

        if self._im.rename_instance(name, new_name):
            self._refresh_list()

    def _on_delete(self) -> None:
        """Opens delete confirmation dialog."""
        name = self._selected_name()
        if name is None or self._im is None or self._is_active_selected():
            return

        objects = self._im.get_objects_for_deletion(name)

        # Build message with file list
        lines = []
        total_size = 0
        for path, size in objects:
            total_size += size
            size_str = self._format_size(size)
            lines.append(f"  - {Path(path).name}  ({size_str})")

        msg = tr("instance.delete_confirm", name=name) + "\n\n"
        msg += "\n".join(lines)
        msg += f"\n\n{tr('instance.delete_total', size=self._format_size(total_size))}"

        reply = QMessageBox.warning(
            self,
            tr("instance.btn_delete"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self._im.delete_instance(name):
                self._refresh_list()

    def _format_size(self, size: int) -> str:
        """Format bytes as human-readable string."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"

    def _on_switch(self) -> None:
        """Stub: Switches to selected instance. Backend-Dev fills."""
        name = self._selected_name()
        if name is None or self._im is None:
            return
        self.switched_to = name
        self.accept()

    def _on_explore(self, path_type: str) -> None:
        """Opens folder in file manager."""
        if path_type == "location":
            path = self._location_edit.text()
        elif path_type == "base":
            path = self._base_edit.text()
        elif path_type == "game":
            path = self._game_path_edit.text()
        else:
            return

        if path and path != "\u2014":
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # ── Geometry Persistence ──────────────────────────────────────────

    def _restore_geometry(self) -> None:
        """Restore dialog geometry and splitter state."""
        settings = QSettings("AnvilOrganizer", "InstanceManager")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        splitter_state = settings.value("splitter_state")
        if splitter_state:
            self._splitter.restoreState(splitter_state)

    def closeEvent(self, event) -> None:
        """Save geometry on close."""
        settings = QSettings("AnvilOrganizer", "InstanceManager")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("splitter_state", self._splitter.saveState())
        super().closeEvent(event)
