"""Profile-Dialog zum Verwalten von Profilen."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QCheckBox,
    QInputDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from anvil.core.translator import tr


class ProfileDialog(QDialog):
    """Dialog zum Verwalten von Profilen (Neu, Kopieren, Löschen, Umbenennen, Auswählen)."""

    profile_selected = Signal(str)
    profile_created = Signal(str)
    profile_renamed = Signal(str, str)  # old, new
    profile_deleted = Signal(str)

    def __init__(self, parent=None, *, instance_path: Path | None = None, active_profile: str = ""):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.profiles_title"))
        self.setMinimumSize(520, 380)

        self._instance_path = instance_path
        self._active_profile = active_profile

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Mitte: Links Liste, rechts Buttons
        content = QHBoxLayout()
        content.setSpacing(12)

        # Links: QListWidget
        self._profile_list = QListWidget()
        self._profile_list.setMinimumWidth(180)
        self._profile_list.itemDoubleClicked.connect(self._on_rename)
        content.addWidget(self._profile_list)

        # Rechts: Buttons vertikal
        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)

        self._btn_new = QPushButton(tr("button.new"))
        self._btn_copy = QPushButton(tr("button.copy"))
        self._btn_delete = QPushButton(tr("button.delete"))
        self._btn_rename = QPushButton(tr("button.rename"))

        self._btn_new.clicked.connect(lambda checked=False: self._on_new())
        self._btn_copy.clicked.connect(lambda checked=False: self._on_copy())
        self._btn_delete.clicked.connect(lambda checked=False: self._on_delete())
        self._btn_rename.clicked.connect(lambda checked=False: self._on_rename())

        btn_col.addWidget(self._btn_new)
        btn_col.addWidget(self._btn_copy)
        btn_col.addWidget(self._btn_delete)
        btn_col.addWidget(self._btn_rename)
        btn_col.addStretch()
        content.addLayout(btn_col)
        layout.addLayout(content)

        # Unten: Checkboxen
        cb_row = QVBoxLayout()
        cb_saves = QCheckBox(tr("label.profile_saves"))
        cb_saves.setChecked(True)
        cb_ini = QCheckBox(tr("label.profile_ini"))
        cb_ini.setChecked(True)
        cb_archive = QCheckBox(tr("label.auto_archive_invalidation"))
        cb_archive.setChecked(True)
        cb_archive.setEnabled(False)
        cb_row.addWidget(cb_saves)
        cb_row.addWidget(cb_ini)
        cb_row.addWidget(cb_archive)
        layout.addLayout(cb_row)

        # Unten rechts: Auswählen, Schließen
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        select_btn = QPushButton(tr("button.select"))
        close_btn = QPushButton(tr("button.close"))
        select_btn.clicked.connect(lambda checked=False: self._on_select())
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(select_btn)
        bottom_row.addWidget(close_btn)
        layout.addLayout(bottom_row)

        self._load_profiles()

    def _load_profiles(self) -> None:
        """Profile von Disk lesen und Liste füllen."""
        self._profile_list.clear()
        if not self._instance_path:
            return

        profiles_dir = self._instance_path / ".profiles"
        if not profiles_dir.is_dir():
            return

        profile_folders = sorted([d.name for d in profiles_dir.iterdir() if d.is_dir()])
        if not profile_folders:
            return

        # Gespeicherte Reihenfolge anwenden
        order_file = profiles_dir / "profiles_order.json"
        if order_file.exists():
            try:
                saved_order = json.loads(order_file.read_text())
                ordered = [p for p in saved_order if p in profile_folders]
                ordered += [p for p in profile_folders if p not in saved_order]
                profile_folders = ordered
            except (json.JSONDecodeError, TypeError):
                pass

        for name in profile_folders:
            item = QListWidgetItem(name)
            self._profile_list.addItem(item)
            if name == self._active_profile:
                item.setSelected(True)
                self._profile_list.setCurrentItem(item)

    def _selected_name(self) -> str | None:
        """Aktuell ausgewählter Profilname."""
        item = self._profile_list.currentItem()
        return item.text() if item else None

    def _on_new(self) -> None:
        """Neues Profil erstellen."""
        name, ok = QInputDialog.getText(self, tr("dialog.profiles_title"), tr("placeholder.profile_name"))
        name = name.strip() if name else ""
        if not ok or not name:
            return

        existing = [self._profile_list.item(i).text() for i in range(self._profile_list.count())]
        if name in existing:
            return

        self.profile_created.emit(name)
        self._load_profiles()
        # Neu erstelltes Profil auswählen
        self._active_profile = name
        self._load_profiles()

    def _on_copy(self) -> None:
        """Ausgewähltes Profil kopieren."""
        src = self._selected_name()
        if not src or not self._instance_path:
            return

        name, ok = QInputDialog.getText(
            self, tr("dialog.profiles_title"),
            tr("placeholder.profile_name"),
            text=f"{src} (2)",
        )
        name = name.strip() if name else ""
        if not ok or not name:
            return

        existing = [self._profile_list.item(i).text() for i in range(self._profile_list.count())]
        if name in existing:
            return

        profiles_dir = self._instance_path / ".profiles"
        src_path = profiles_dir / src
        dst_path = profiles_dir / name
        if src_path.is_dir() and not dst_path.exists():
            shutil.copytree(src_path, dst_path)

        self._load_profiles()

    def _on_delete(self) -> None:
        """Ausgewähltes Profil löschen."""
        name = self._selected_name()
        if not name or name == "Default":
            return
        if self._profile_list.count() <= 1:
            return

        self.profile_deleted.emit(name)
        # Nach Löschen: Default oder erstes Profil aktiv
        if self._active_profile == name:
            self._active_profile = "Default"
        self._load_profiles()

    def _on_rename(self, item: QListWidgetItem | None = None) -> None:
        """Ausgewähltes Profil umbenennen."""
        if item is not None:
            old_name = item.text()
        else:
            old_name = self._selected_name()
        if not old_name or old_name == "Default":
            return

        new_name, ok = QInputDialog.getText(
            self, tr("dialog.profiles_title"),
            tr("button.rename"),
            text=old_name,
        )
        new_name = new_name.strip() if new_name else ""
        if not ok or not new_name or new_name == old_name:
            return

        existing = [self._profile_list.item(i).text() for i in range(self._profile_list.count())]
        if new_name in existing:
            return

        self.profile_renamed.emit(old_name, new_name)
        if self._active_profile == old_name:
            self._active_profile = new_name
        self._load_profiles()

    def _on_select(self) -> None:
        """Profil auswählen und wechseln."""
        name = self._selected_name()
        if not name or name == self._active_profile:
            return
        self._active_profile = name
        self.profile_selected.emit(name)
        self._load_profiles()
