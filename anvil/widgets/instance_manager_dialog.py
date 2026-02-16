"""Instanz Manager — QDialog zum Verwalten von Instanzen."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QPushButton,
    QLabel,
    QWidget,
    QFrame,
    QMessageBox,
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from anvil.core.instance_manager import InstanceManager
from anvil.core.icon_manager import IconManager, placeholder_game_icon
from anvil.plugins.plugin_loader import PluginLoader
from anvil.widgets.instance_wizard import CreateInstanceWizard
from anvil.core.translator import tr

_ICONS_DIR = Path(__file__).resolve().parent.parent / "styles" / "icons"

_DIALOG_STYLE = """
QDialog { background: #1C1C1C; }
QWidget { background: #1C1C1C; color: #D3D3D3; }
QLineEdit, QListWidget, QPushButton, QComboBox {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 4px;
}
QListWidget::item:selected { background: #3D3D3D; color: #D3D3D3; }
QPushButton#deleteInstance { background: #5a2020; color: #D3D3D3; }
QPushButton#deleteInstance:hover { background: #7a2828; }
QPushButton#linkButton { background: transparent; color: #6ab; border: none; text-align: left; }
QPushButton#linkButton:hover { color: #8cd; }
"""


def _icon(name: str) -> QIcon:
    path = _ICONS_DIR / name
    if path.exists():
        return QIcon(str(path))
    return QIcon()


class InstanceManagerDialog(QDialog):
    """Dialog for creating, switching, and deleting game instances."""

    # Set to the instance name the user switched to (or None).
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
        self.switched_to = None

        self.setWindowTitle(tr("dialog.instance_manager_title"))
        self.setMinimumSize(720, 480)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── Welcome hint (first start) ────────────────────────────────
        if welcome:
            hint = QLabel(tr("dialog.welcome_hint"))
            hint.setStyleSheet(
                "color: #4FC3F7; font-size: 13px; padding: 6px 0;"
            )
            hint.setWordWrap(True)
            layout.addWidget(hint)

        # ── Top row: create + info ────────────────────────────────────
        top_row = QHBoxLayout()
        new_btn = QPushButton(tr("dialog.create_new_instance"))
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._on_create)
        top_row.addWidget(new_btn)

        link_btn = QPushButton(tr("dialog.what_is_instance"))
        link_btn.setObjectName("linkButton")
        link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        link_btn.clicked.connect(self._on_info)
        top_row.addWidget(link_btn)
        top_row.addStretch()
        layout.addLayout(top_row)

        # ── Middle: list left, detail right ───────────────────────────
        content = QHBoxLayout()
        content.setSpacing(12)

        self._list = QListWidget()
        self._list.setMinimumWidth(200)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.doubleClicked.connect(self._on_switch)
        content.addWidget(self._list)

        # Right: detail form
        form = QFrame()
        form.setFrameShape(QFrame.Shape.NoFrame)
        form_layout = QFormLayout(form)
        form_layout.setSpacing(8)

        self._name_edit = QLineEdit()
        self._name_edit.setReadOnly(True)
        form_layout.addRow(tr("label.name") + ":", self._name_edit)

        self._game_edit = QLineEdit()
        self._game_edit.setReadOnly(True)
        form_layout.addRow(tr("label.game"), self._game_edit)

        self._store_edit = QLineEdit()
        self._store_edit.setReadOnly(True)
        form_layout.addRow(tr("label.store"), self._store_edit)

        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        form_layout.addRow(tr("label.game_path"), self._path_edit)

        self._profile_edit = QLineEdit()
        self._profile_edit.setReadOnly(True)
        form_layout.addRow(tr("label.profile"), self._profile_edit)

        self._dir_edit = QLineEdit()
        self._dir_edit.setReadOnly(True)
        form_layout.addRow(tr("label.instance_folder"), self._dir_edit)

        self._created_edit = QLineEdit()
        self._created_edit.setReadOnly(True)
        form_layout.addRow(tr("label.created"), self._created_edit)

        content.addWidget(form, 1)
        layout.addLayout(content)

        # ── Bottom row: filter + action buttons ───────────────────────
        bottom_row = QHBoxLayout()
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText(tr("placeholder.filter"))
        self._filter_edit.setMaximumWidth(200)
        self._filter_edit.textChanged.connect(self._on_filter)
        bottom_row.addWidget(self._filter_edit)
        bottom_row.addStretch()

        open_ini_btn = QPushButton(tr("dialog.open_ini"))
        open_ini_btn.clicked.connect(self._on_open_ini)

        delete_btn = QPushButton(tr("dialog.delete_instance"))
        delete_btn.setObjectName("deleteInstance")
        delete_btn.clicked.connect(self._on_delete)

        switch_btn = QPushButton(tr("dialog.switch_to_instance"))
        switch_btn.clicked.connect(self._on_switch)

        close_btn = QPushButton(tr("button.close"))
        close_btn.clicked.connect(self.accept)

        bottom_row.addWidget(open_ini_btn)
        bottom_row.addWidget(delete_btn)
        bottom_row.addWidget(switch_btn)
        bottom_row.addWidget(close_btn)
        layout.addLayout(bottom_row)

        # Populate list
        self._refresh_list()

    # ── List management ───────────────────────────────────────────────

    def _refresh_list(self) -> None:
        """Reload the instance list from disk."""
        self._list.clear()
        if self._im is None:
            return

        current = self._im.current_instance()

        for inst in self._im.list_instances():
            name = inst["name"]
            label = name
            if name == current:
                label = f"{name}  {tr('dialog.active_suffix')}"
            item = QListWidgetItem(label)
            # Game-specific icon from cache, fallback to placeholder
            gsn = inst.get("game_short_name", "")
            icon_pix = self._icons.get_game_icon(gsn) if self._icons and gsn else None
            if icon_pix is not None:
                item.setIcon(QIcon(icon_pix))
            else:
                item.setIcon(QIcon(placeholder_game_icon(32)))
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._list.addItem(item)

        # Select current or first
        if self._list.count() > 0:
            for i in range(self._list.count()):
                it = self._list.item(i)
                if it and it.data(Qt.ItemDataRole.UserRole) == current:
                    self._list.setCurrentItem(it)
                    return
            self._list.setCurrentRow(0)

    def _selected_name(self) -> str | None:
        """Return the instance name of the selected list item."""
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_selection_changed(self, current: QListWidgetItem | None, _prev):
        """Update the detail form when a list item is selected."""
        if current is None or self._im is None:
            for field in (
                self._name_edit, self._game_edit, self._store_edit,
                self._path_edit, self._profile_edit, self._dir_edit,
                self._created_edit,
            ):
                field.clear()
            return

        name = current.data(Qt.ItemDataRole.UserRole)
        data = self._im.load_instance(name)
        if not data:
            return

        self._name_edit.setText(name)
        self._game_edit.setText(data.get("game_name", ""))
        self._store_edit.setText(data.get("detected_store", "") or "—")
        self._path_edit.setText(data.get("game_path", "") or "—")
        self._profile_edit.setText(data.get("selected_profile", ""))
        self._dir_edit.setText(str(self._im.instances_path() / name))
        self._created_edit.setText(data.get("created", ""))

    def _on_create(self) -> None:
        """Open the create-instance wizard."""
        if self._im is None or self._pl is None:
            QMessageBox.warning(
                self, tr("error.install_failed_title"),
                tr("dialog.plugin_loader_error"),
            )
            return

        wizard = CreateInstanceWizard(self, self._im, self._pl, self._icons)
        if wizard.exec() == QDialog.DialogCode.Accepted and wizard.created_instance:
            self._refresh_list()
            # Auto-switch to the newly created instance
            self._im.set_current_instance(wizard.created_instance)
            self.switched_to = wizard.created_instance

    def _on_switch(self) -> None:
        """Switch to the selected instance."""
        name = self._selected_name()
        if name is None or self._im is None:
            return

        self._im.set_current_instance(name)
        self.switched_to = name
        self.accept()

    def _on_delete(self) -> None:
        """Delete the selected instance after confirmation."""
        name = self._selected_name()
        if name is None or self._im is None:
            return

        reply = QMessageBox.warning(
            self,
            tr("dialog.delete_instance_title"),
            tr("dialog.delete_instance_confirm", name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._im.delete_instance(name)
        self._refresh_list()

    def _on_open_ini(self) -> None:
        """Open the .anvil.ini in the default text editor."""
        name = self._selected_name()
        if name is None or self._im is None:
            return
        ini = self._im.instances_path() / name / ".anvil.ini"
        if ini.is_file():
            subprocess.Popen(["xdg-open", str(ini)])

    def _on_filter(self, text: str) -> None:
        """Show/hide list items based on filter text."""
        text_lower = text.lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is None:
                continue
            name = (item.data(Qt.ItemDataRole.UserRole) or "").lower()
            item.setHidden(bool(text_lower) and text_lower not in name)

    def _on_info(self) -> None:
        """Show a brief explanation of instances."""
        QMessageBox.information(
            self,
            tr("dialog.what_is_instance"),
            tr("dialog.what_is_instance_text"),
        )

