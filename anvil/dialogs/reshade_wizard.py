"""ReShade Wizard — guided ReShade installation and preset management.

Provides a multi-page dialog (QStackedWidget) that allows the user to:
1. See current ReShade status and select the Render API
2. Install / uninstall ReShade
3. Manage presets (add, remove, activate)
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QWidget,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QFrame,
    QMessageBox,
)
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtCore import Qt, QUrl, QSettings

from anvil.core.reshade_manager import ReshadeManager, API_DLL_MAP, API_LABELS
from anvil.core.translator import tr

# Page indices
_PAGE_STATUS = 0
_PAGE_PRESETS = 1


class ReshadeWizard(QDialog):
    """ReShade configuration wizard.

    Args:
        game_path: Absolute path to the game root directory.
        game_binary: Relative path to the game executable.
        instance_name: Name of the current Anvil instance (for QSettings).
        parent: Parent widget.
    """

    def __init__(
        self,
        game_path: Path,
        game_binary: str,
        instance_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._game_path = game_path
        self._game_binary = game_binary
        self._instance_name = instance_name
        self._manager = ReshadeManager(game_path, game_binary)

        self.setWindowTitle(tr("reshade.title"))
        self.setMinimumSize(620, 480)
        self.resize(620, 520)

        self._build_ui()
        self._load_settings()
        self._refresh_status()
        self._refresh_presets()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("reshadeHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 12, 16, 12)
        title = QLabel(tr("reshade.title"))
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        hl.addWidget(title)
        hl.addStretch()

        # Navigation buttons in header
        self._btn_status = QPushButton(tr("reshade.tab_status"))
        self._btn_presets = QPushButton(tr("reshade.tab_presets"))
        self._btn_status.setCheckable(True)
        self._btn_presets.setCheckable(True)
        self._btn_status.setChecked(True)
        self._btn_status.clicked.connect(lambda: self._switch_page(_PAGE_STATUS))
        self._btn_presets.clicked.connect(lambda: self._switch_page(_PAGE_PRESETS))
        hl.addWidget(self._btn_status)
        hl.addWidget(self._btn_presets)
        root.addWidget(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        # Stacked pages
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_status_page())
        self._stack.addWidget(self._build_presets_page())
        root.addWidget(self._stack, 1)

        # Bottom bar
        bottom = QHBoxLayout()
        bottom.setContentsMargins(16, 8, 16, 12)
        bottom.addStretch()
        close_btn = QPushButton(tr("reshade.close"))
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        root.addLayout(bottom)

    def _build_status_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        # Status indicator
        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        status_font = QFont()
        status_font.setPointSize(11)
        self._status_label.setFont(status_font)
        lay.addWidget(self._status_label)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)

        # API selection
        api_row = QHBoxLayout()
        api_row.addWidget(QLabel(tr("reshade.api_label")))
        self._api_combo = QComboBox()
        for key, label in API_LABELS.items():
            self._api_combo.addItem(f"{label} ({API_DLL_MAP[key]})", key)
        self._api_combo.setCurrentIndex(1)  # Default: DX10/11
        api_row.addWidget(self._api_combo, 1)
        lay.addLayout(api_row)

        # DLL source path
        dll_row = QHBoxLayout()
        dll_row.addWidget(QLabel(tr("reshade.dll_label")))
        self._dll_edit = QLineEdit()
        self._dll_edit.setPlaceholderText(tr("reshade.dll_placeholder"))
        dll_row.addWidget(self._dll_edit, 1)
        browse_btn = QPushButton(tr("reshade.browse"))
        browse_btn.clicked.connect(self._browse_dll)
        dll_row.addWidget(browse_btn)
        lay.addLayout(dll_row)

        # Download link
        link_btn = QPushButton(tr("reshade.download_link"))
        link_btn.setFlat(True)
        link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        link_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://reshade.me"))
        )
        lay.addWidget(link_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # Action buttons
        btn_row = QHBoxLayout()
        self._install_btn = QPushButton(tr("reshade.install"))
        self._install_btn.clicked.connect(self._on_install)
        btn_row.addWidget(self._install_btn)

        self._uninstall_btn = QPushButton(tr("reshade.uninstall"))
        self._uninstall_btn.clicked.connect(self._on_uninstall)
        btn_row.addWidget(self._uninstall_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        lay.addStretch()
        return page

    def _build_presets_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        lay.addWidget(QLabel(tr("reshade.presets_title")))

        self._preset_list = QListWidget()
        lay.addWidget(self._preset_list, 1)

        # Active preset label
        self._active_preset_label = QLabel()
        lay.addWidget(self._active_preset_label)

        # Buttons
        btn_row = QHBoxLayout()
        add_btn = QPushButton(tr("reshade.preset_add"))
        add_btn.clicked.connect(self._on_add_preset)
        btn_row.addWidget(add_btn)

        self._activate_btn = QPushButton(tr("reshade.preset_activate"))
        self._activate_btn.clicked.connect(self._on_activate_preset)
        btn_row.addWidget(self._activate_btn)

        self._remove_btn = QPushButton(tr("reshade.preset_remove"))
        self._remove_btn.clicked.connect(self._on_remove_preset)
        btn_row.addWidget(self._remove_btn)

        btn_row.addStretch()
        lay.addLayout(btn_row)

        return page

    # ── Page navigation ───────────────────────────────────────────────

    def _switch_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._btn_status.setChecked(index == _PAGE_STATUS)
        self._btn_presets.setChecked(index == _PAGE_PRESETS)

    # ── Status refresh ────────────────────────────────────────────────

    def _refresh_status(self) -> None:
        info = self._manager.detect_installed()
        if info is not None:
            api_label = API_LABELS.get(info["api"], info["api"])
            self._status_label.setText(
                tr("reshade.status_installed").format(
                    api=api_label, dll=info["dll_name"]
                )
            )
            self._status_label.setStyleSheet("color: #4CAF50;")
            self._install_btn.setEnabled(False)
            self._uninstall_btn.setEnabled(True)
        else:
            self._status_label.setText(tr("reshade.status_not_installed"))
            self._status_label.setStyleSheet("color: #F44336;")
            self._install_btn.setEnabled(True)
            self._uninstall_btn.setEnabled(False)

    def _refresh_presets(self) -> None:
        self._preset_list.clear()
        active = self._manager.get_active_preset()
        for p in self._manager.list_presets():
            item = QListWidgetItem(p.name)
            if active and p.name.lower() == active.lower():
                item.setText(f"{p.name}  [aktiv]")
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            self._preset_list.addItem(item)

        if active:
            self._active_preset_label.setText(
                tr("reshade.active_preset").format(name=active)
            )
        else:
            self._active_preset_label.setText(tr("reshade.no_active_preset"))

    # ── Settings persistence ──────────────────────────────────────────

    def _settings_key(self, key: str) -> str:
        return f"reshade/{self._instance_name}/{key}"

    def _load_settings(self) -> None:
        s = QSettings("AnvilOrganizer", "AnvilOrganizer")
        dll = s.value(self._settings_key("dll_source"), "")
        if dll:
            self._dll_edit.setText(dll)
        api = s.value(self._settings_key("api"), "dx11")
        idx = self._api_combo.findData(api)
        if idx >= 0:
            self._api_combo.setCurrentIndex(idx)

    def _save_settings(self) -> None:
        s = QSettings("AnvilOrganizer", "AnvilOrganizer")
        s.setValue(self._settings_key("dll_source"), self._dll_edit.text())
        s.setValue(self._settings_key("api"), self._api_combo.currentData())

    # ── Action handlers ───────────────────────────────────────────────

    def _browse_dll(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("reshade.select_dll"),
            str(Path.home()),
            "DLL Files (*.dll);;All Files (*)",
        )
        if path:
            self._dll_edit.setText(path)

    def _on_install(self) -> None:
        dll_text = self._dll_edit.text().strip()
        if not dll_text:
            QMessageBox.warning(
                self,
                tr("reshade.title"),
                tr("reshade.error_no_dll"),
            )
            return

        dll_path = Path(dll_text)
        if not dll_path.is_file() or dll_path.suffix.lower() != ".dll":
            QMessageBox.warning(
                self,
                tr("reshade.title"),
                tr("reshade.error_invalid_dll"),
            )
            return

        api = self._api_combo.currentData()
        ok, msg = self._manager.install(dll_path, api)
        if ok:
            self._save_settings()
            self._refresh_status()
            self._refresh_presets()
            QMessageBox.information(self, tr("reshade.title"), msg)
        else:
            QMessageBox.warning(self, tr("reshade.title"), msg)

    def _on_uninstall(self) -> None:
        reply = QMessageBox.question(
            self,
            tr("reshade.title"),
            tr("reshade.confirm_uninstall"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ok, msg = self._manager.uninstall()
        if ok:
            self._refresh_status()
            self._refresh_presets()
        QMessageBox.information(self, tr("reshade.title"), msg)

    def _on_add_preset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("reshade.select_preset"),
            str(Path.home()),
            "Preset Files (*.ini *.txt);;All Files (*)",
        )
        if not path:
            return

        ok, msg = self._manager.add_preset(Path(path))
        if ok:
            self._refresh_presets()
        else:
            QMessageBox.warning(self, tr("reshade.title"), msg)

    def _on_activate_preset(self) -> None:
        item = self._preset_list.currentItem()
        if item is None:
            return

        # Strip " [aktiv]" suffix if present
        name = item.text().replace("  [aktiv]", "").strip()
        ok, msg = self._manager.set_active_preset(name)
        if ok:
            self._refresh_presets()
        else:
            QMessageBox.warning(self, tr("reshade.title"), msg)

    def _on_remove_preset(self) -> None:
        item = self._preset_list.currentItem()
        if item is None:
            return

        name = item.text().replace("  [aktiv]", "").strip()
        reply = QMessageBox.question(
            self,
            tr("reshade.title"),
            tr("reshade.confirm_remove_preset").format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        ok, msg = self._manager.remove_preset(name)
        if ok:
            self._refresh_presets()
        else:
            QMessageBox.warning(self, tr("reshade.title"), msg)
