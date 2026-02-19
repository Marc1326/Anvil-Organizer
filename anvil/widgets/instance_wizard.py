"""Neuer-Instanz-Wizard — QDialog mit QStackedWidget (8 Seiten, MO2-Stil)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QStackedWidget,
    QLabel, QLineEdit, QListView, QCheckBox, QRadioButton,
    QPushButton, QWidget, QFrame, QButtonGroup, QAbstractItemView,
)
from PySide6.QtGui import QFont, QIcon, QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, QSortFilterProxyModel, QSettings

from anvil.core.instance_manager import InstanceManager
from anvil.core.icon_manager import IconManager, placeholder_game_icon
from anvil.plugins.plugin_loader import PluginLoader
from anvil.core.translator import tr

# ── Style ─────────────────────────────────────────────────────────────

_WIZARD_STYLE = """
QDialog, QWidget {
    background: #1C1C1C;
    color: #D3D3D3;
}
QLabel { background: transparent; }
QLineEdit, QListView {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 4px;
}
QListView::item { padding: 6px 4px; }
QListView::item:selected { background: #3D3D3D; color: #D3D3D3; }
QListView::item:hover { background: #2A2A2A; }
QPushButton {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 6px 16px;
}
QPushButton:hover { background: #2A2A2A; }
QPushButton:disabled { color: #606060; }
QPushButton#createBtn {
    background: #006868;
    color: #FFF;
    font-weight: bold;
}
QPushButton#createBtn:hover { background: #008585; }
QCheckBox, QRadioButton { background: transparent; spacing: 6px; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px; height: 16px;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    background: #1C1C1C;
}
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked { background: #4FC3F7; }
QFrame#pageTitle {
    background: #141414;
    border-bottom: 1px solid #3D3D3D;
    padding: 12px;
}
QFrame#navBar {
    background: #141414;
    border-top: 1px solid #3D3D3D;
}
"""

# Page indices
PAGE_INTRO = 0
PAGE_TYPE = 1
PAGE_GAME = 2
PAGE_VARIANTS = 3
PAGE_NAME = 4
PAGE_PROFILE = 5
PAGE_PATHS = 6
PAGE_CONFIRM = 7

# Game variants - games with multiple editions
GAME_VARIANTS = {
    "skyrimse": ["Special Edition", "VR"],
    "skyrimvr": ["Special Edition", "VR"],
    "skyrim": ["Legendary Edition", "Special Edition", "VR"],
    "fallout4": ["Standard", "VR"],
    "fallout4vr": ["Standard", "VR"],
}


class CreateInstanceWizard(QDialog):
    """Multi-page wizard for creating a new game instance (QStackedWidget)."""

    created_instance: str | None = None

    def __init__(
        self,
        parent=None,
        instance_manager: InstanceManager | None = None,
        plugin_loader: PluginLoader | None = None,
        icon_manager: IconManager | None = None,
    ):
        super().__init__(parent)
        self._im = instance_manager
        self._pl = plugin_loader
        self._icons = icon_manager
        self.created_instance = None

        self.setWindowTitle(tr("wizard.title"))
        self.setMinimumSize(700, 550)
        self.setStyleSheet(_WIZARD_STYLE)

        self._current_page = PAGE_INTRO
        self._skip_intro = False

        self._setup_ui()
        self._restore_geometry()
        self._update_nav_buttons()

    def _setup_ui(self) -> None:
        """Build the wizard UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Page title bar
        self._title_frame = QFrame()
        self._title_frame.setObjectName("pageTitle")
        title_layout = QVBoxLayout(self._title_frame)
        title_layout.setContentsMargins(16, 12, 16, 12)

        self._page_title = QLabel()
        self._page_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(self._page_title)

        self._page_subtitle = QLabel()
        self._page_subtitle.setStyleSheet("font-size: 12px; color: #808080;")
        self._page_subtitle.setWordWrap(True)
        title_layout.addWidget(self._page_subtitle)

        layout.addWidget(self._title_frame)

        # Stacked widget for pages
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        # Create all pages
        self._create_intro_page()
        self._create_type_page()
        self._create_game_page()
        self._create_variants_page()
        self._create_name_page()
        self._create_profile_page()
        self._create_paths_page()
        self._create_confirm_page()

        # Navigation bar
        self._nav_frame = QFrame()
        self._nav_frame.setObjectName("navBar")
        nav_layout = QHBoxLayout(self._nav_frame)
        nav_layout.setContentsMargins(16, 12, 16, 12)
        nav_layout.setSpacing(8)

        self._back_btn = QPushButton(tr("wizard.btn_back"))
        self._back_btn.clicked.connect(self._on_back)
        nav_layout.addWidget(self._back_btn)

        nav_layout.addStretch()

        self._cancel_btn = QPushButton(tr("button.cancel"))
        self._cancel_btn.clicked.connect(self.reject)
        nav_layout.addWidget(self._cancel_btn)

        self._next_btn = QPushButton(tr("wizard.btn_next"))
        self._next_btn.clicked.connect(self._on_next)
        nav_layout.addWidget(self._next_btn)

        self._create_btn = QPushButton(tr("wizard.btn_create"))
        self._create_btn.setObjectName("createBtn")
        self._create_btn.clicked.connect(self._on_create)
        nav_layout.addWidget(self._create_btn)

        layout.addWidget(self._nav_frame)

        # Initialize first page
        self._show_page(PAGE_INTRO)

    # ── Page Creation ─────────────────────────────────────────────────

    def _create_intro_page(self) -> None:
        """Page 0: Introduction with skip checkbox."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        intro_text = QLabel(tr("wizard.intro_text"))
        intro_text.setWordWrap(True)
        intro_text.setStyleSheet("font-size: 13px; line-height: 1.6;")
        layout.addWidget(intro_text)

        layout.addStretch()

        self._skip_intro_cb = QCheckBox(tr("wizard.skip_intro"))
        layout.addWidget(self._skip_intro_cb)

        self._stack.addWidget(page)

    def _create_type_page(self) -> None:
        """Page 1: Instance type (Global/Portable)."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        hint = QLabel(tr("wizard.type_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._type_group = QButtonGroup(self)

        self._type_global = QRadioButton(tr("wizard.type_global"))
        self._type_global.setChecked(True)
        self._type_group.addButton(self._type_global, 0)
        layout.addWidget(self._type_global)

        global_desc = QLabel(tr("wizard.type_global_desc"))
        global_desc.setStyleSheet("color: #808080; margin-left: 24px;")
        global_desc.setWordWrap(True)
        layout.addWidget(global_desc)

        self._type_portable = QRadioButton(tr("wizard.type_portable"))
        self._type_group.addButton(self._type_portable, 1)
        layout.addWidget(self._type_portable)

        portable_desc = QLabel(tr("wizard.type_portable_desc"))
        portable_desc.setStyleSheet("color: #808080; margin-left: 24px;")
        portable_desc.setWordWrap(True)
        layout.addWidget(portable_desc)

        layout.addStretch()
        self._stack.addWidget(page)

    def _create_game_page(self) -> None:
        """Page 2: Game selection with filter."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        hint = QLabel(tr("wizard.game_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._game_filter = QLineEdit()
        self._game_filter.setPlaceholderText(tr("wizard.game_filter_placeholder"))
        self._game_filter.textChanged.connect(self._on_game_filter_changed)
        layout.addWidget(self._game_filter)

        self._game_model = QStandardItemModel()
        self._game_proxy = QSortFilterProxyModel()
        self._game_proxy.setSourceModel(self._game_model)
        self._game_proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._game_list = QListView()
        self._game_list.setModel(self._game_proxy)
        self._game_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._game_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._game_list.doubleClicked.connect(self._on_next)
        layout.addWidget(self._game_list, 1)

        self._stack.addWidget(page)

    def _create_variants_page(self) -> None:
        """Page 3: Game variants (e.g., Steam vs GOG)."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        hint = QLabel(tr("wizard.variants_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._variants_group = QButtonGroup(self)
        self._variants_container = QVBoxLayout()
        layout.addLayout(self._variants_container)

        layout.addStretch()
        self._stack.addWidget(page)

    def _create_name_page(self) -> None:
        """Page 4: Instance name with validation."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        hint = QLabel(tr("wizard.name_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(12)

        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(self._on_name_changed)
        form.addRow(tr("wizard.label_name"), self._name_edit)

        layout.addLayout(form)

        self._name_warning = QLabel()
        self._name_warning.setStyleSheet("color: #FF6B6B; font-weight: bold;")
        self._name_warning.setWordWrap(True)
        self._name_warning.hide()
        layout.addWidget(self._name_warning)

        self._name_path_label = QLabel()
        self._name_path_label.setStyleSheet("color: #808080; font-size: 12px;")
        self._name_path_label.setWordWrap(True)
        layout.addWidget(self._name_path_label)

        layout.addStretch()
        self._stack.addWidget(page)

    def _create_profile_page(self) -> None:
        """Page 5: Profile settings (Local INIs, Local Saves)."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        hint = QLabel(tr("wizard.profile_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._local_inis_cb = QCheckBox(tr("wizard.local_inis"))
        layout.addWidget(self._local_inis_cb)

        inis_desc = QLabel(tr("wizard.local_inis_desc"))
        inis_desc.setStyleSheet("color: #808080; margin-left: 24px;")
        inis_desc.setWordWrap(True)
        layout.addWidget(inis_desc)

        self._local_saves_cb = QCheckBox(tr("wizard.local_saves"))
        layout.addWidget(self._local_saves_cb)

        saves_desc = QLabel(tr("wizard.local_saves_desc"))
        saves_desc.setStyleSheet("color: #808080; margin-left: 24px;")
        saves_desc.setWordWrap(True)
        layout.addWidget(saves_desc)

        self._auto_archive_cb = QCheckBox(tr("wizard.auto_archive"))
        layout.addWidget(self._auto_archive_cb)

        archive_desc = QLabel(tr("wizard.auto_archive_desc"))
        archive_desc.setStyleSheet("color: #808080; margin-left: 24px;")
        archive_desc.setWordWrap(True)
        layout.addWidget(archive_desc)

        layout.addStretch()
        self._stack.addWidget(page)

    def _create_paths_page(self) -> None:
        """Page 6: Advanced paths configuration."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._advanced_paths_cb = QCheckBox(tr("wizard.advanced_paths"))
        self._advanced_paths_cb.toggled.connect(self._on_advanced_paths_toggled)
        layout.addWidget(self._advanced_paths_cb)

        self._paths_form = QWidget()
        paths_layout = QFormLayout(self._paths_form)
        paths_layout.setSpacing(12)

        self._mods_path_edit = QLineEdit()
        self._mods_path_edit.setPlaceholderText("%BASE_DIR%/.mods")
        paths_layout.addRow(tr("wizard.label_mods_path"), self._mods_path_edit)

        self._downloads_path_edit = QLineEdit()
        self._downloads_path_edit.setPlaceholderText("%BASE_DIR%/.downloads")
        paths_layout.addRow(tr("wizard.label_downloads_path"), self._downloads_path_edit)

        self._overwrite_path_edit = QLineEdit()
        self._overwrite_path_edit.setPlaceholderText("%BASE_DIR%/.overwrite")
        paths_layout.addRow(tr("wizard.label_overwrite_path"), self._overwrite_path_edit)

        self._paths_form.hide()
        layout.addWidget(self._paths_form)

        paths_hint = QLabel(tr("wizard.paths_hint"))
        paths_hint.setStyleSheet("color: #808080; font-size: 12px;")
        paths_hint.setWordWrap(True)
        layout.addWidget(paths_hint)

        layout.addStretch()
        self._stack.addWidget(page)

    def _create_confirm_page(self) -> None:
        """Page 7: Confirmation summary."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        hint = QLabel(tr("wizard.confirm_hint"))
        hint.setStyleSheet("font-size: 13px;")
        layout.addWidget(hint)

        self._summary_form = QFormLayout()
        self._summary_form.setSpacing(8)

        self._sum_game = QLabel()
        self._summary_form.addRow(tr("wizard.sum_game"), self._sum_game)

        self._sum_name = QLabel()
        self._summary_form.addRow(tr("wizard.sum_name"), self._sum_name)

        self._sum_type = QLabel()
        self._summary_form.addRow(tr("wizard.sum_type"), self._sum_type)

        self._sum_store = QLabel()
        self._summary_form.addRow(tr("wizard.sum_store"), self._sum_store)

        self._sum_game_path = QLabel()
        self._sum_game_path.setWordWrap(True)
        self._summary_form.addRow(tr("wizard.sum_game_path"), self._sum_game_path)

        self._sum_instance_path = QLabel()
        self._sum_instance_path.setWordWrap(True)
        self._summary_form.addRow(tr("wizard.sum_instance_path"), self._sum_instance_path)

        layout.addLayout(self._summary_form)

        dirs_label = QLabel(tr("wizard.dirs_created"))
        dirs_label.setStyleSheet("color: #808080; font-size: 12px; margin-top: 16px;")
        layout.addWidget(dirs_label)

        layout.addStretch()
        self._stack.addWidget(page)

    # ── Page Navigation ───────────────────────────────────────────────

    def _show_page(self, page_idx: int) -> None:
        """Show a specific page and update title/buttons."""
        self._current_page = page_idx
        self._stack.setCurrentIndex(page_idx)

        titles = {
            PAGE_INTRO: (tr("wizard.title_intro"), tr("wizard.subtitle_intro")),
            PAGE_TYPE: (tr("wizard.title_type"), tr("wizard.subtitle_type")),
            PAGE_GAME: (tr("wizard.title_game"), tr("wizard.subtitle_game")),
            PAGE_VARIANTS: (tr("wizard.title_variants"), tr("wizard.subtitle_variants")),
            PAGE_NAME: (tr("wizard.title_name"), tr("wizard.subtitle_name")),
            PAGE_PROFILE: (tr("wizard.title_profile"), tr("wizard.subtitle_profile")),
            PAGE_PATHS: (tr("wizard.title_paths"), tr("wizard.subtitle_paths")),
            PAGE_CONFIRM: (tr("wizard.title_confirm"), tr("wizard.subtitle_confirm")),
        }

        title, subtitle = titles.get(page_idx, ("", ""))
        self._page_title.setText(title)
        self._page_subtitle.setText(subtitle)

        # Initialize page-specific content
        if page_idx == PAGE_GAME:
            self._populate_game_list()
        elif page_idx == PAGE_VARIANTS:
            self._populate_variants()
        elif page_idx == PAGE_NAME:
            self._init_name_page()
        elif page_idx == PAGE_CONFIRM:
            self._populate_summary()

        self._update_nav_buttons()

    def _update_nav_buttons(self) -> None:
        """Update navigation button visibility and state."""
        is_first = self._current_page == PAGE_INTRO
        is_last = self._current_page == PAGE_CONFIRM

        self._back_btn.setVisible(not is_first)
        self._next_btn.setVisible(not is_last)
        self._create_btn.setVisible(is_last)

        # Enable/disable next based on page validation
        can_proceed = self._validate_current_page()
        self._next_btn.setEnabled(can_proceed)
        self._create_btn.setEnabled(can_proceed)

    def _validate_current_page(self) -> bool:
        """Validate the current page."""
        if self._current_page == PAGE_GAME:
            return self._game_list.currentIndex().isValid()
        elif self._current_page == PAGE_NAME:
            return self._is_name_valid()
        return True

    def _is_name_valid(self) -> bool:
        """Check if the instance name is valid."""
        name = self._name_edit.text().strip()
        if not name:
            return False
        if self._im is None:
            return True
        existing = {inst["name"] for inst in self._im.list_instances()}
        return name not in existing

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_back(self) -> None:
        """Go to previous page."""
        if self._current_page > PAGE_INTRO:
            # Skip variants page if no variants available
            new_page = self._current_page - 1
            if new_page == PAGE_VARIANTS and not self._has_variants():
                new_page = PAGE_GAME
            self._show_page(new_page)

    def _on_next(self) -> None:
        """Go to next page."""
        if self._current_page < PAGE_CONFIRM:
            # Skip variants page if no variants available
            new_page = self._current_page + 1
            if new_page == PAGE_VARIANTS and not self._has_variants():
                new_page = PAGE_NAME
            self._show_page(new_page)

    def _on_create(self) -> None:
        """Stub: Creates the instance. Backend-Dev fills."""
        if self._im is None or self._pl is None:
            self.accept()
            return

        short = self._selected_game_short_name()
        plugin = self._pl.get_game(short) if short else None
        name = self._name_edit.text().strip()

        if not plugin or not name:
            self.accept()
            return

        # Collect wizard values
        is_portable = self._type_portable.isChecked()
        local_inis = self._local_inis_cb.isChecked()
        local_saves = self._local_saves_cb.isChecked()
        auto_archive = self._auto_archive_cb.isChecked()

        # Custom paths (only if advanced is checked)
        mods_path = None
        downloads_path = None
        overwrite_path = None
        if self._advanced_paths_cb.isChecked():
            if self._mods_path_edit.text().strip():
                mods_path = self._mods_path_edit.text().strip()
            if self._downloads_path_edit.text().strip():
                downloads_path = self._downloads_path_edit.text().strip()
            if self._overwrite_path_edit.text().strip():
                overwrite_path = self._overwrite_path_edit.text().strip()

        try:
            self._im.create_instance(
                plugin,
                name,
                portable=is_portable,
                local_inis=local_inis,
                local_saves=local_saves,
                auto_archive=auto_archive,
                mods_path=mods_path,
                downloads_path=downloads_path,
                overwrite_path=overwrite_path,
            )
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                tr("error.install_failed_title"),
                tr("wizard.create_error", error=str(exc)),
            )
            return

        # Auto-set as current if first instance
        if len(self._im.list_instances()) == 1:
            self._im.set_current_instance(name)

        # Save skip preference
        if self._skip_intro_cb.isChecked():
            settings = QSettings("AnvilOrganizer", "InstanceWizard")
            settings.setValue("skip_intro", True)

        self.created_instance = name
        self.accept()

    def _on_game_filter_changed(self, text: str) -> None:
        """Filter the game list."""
        self._game_proxy.setFilterFixedString(text)

    def _on_name_changed(self, text: str) -> None:
        """Validate instance name."""
        name = text.strip()

        if not name:
            self._name_warning.hide()
            self._name_path_label.clear()
            self._update_nav_buttons()
            return

        if self._im:
            existing = {inst["name"] for inst in self._im.list_instances()}
            if name in existing:
                self._name_warning.setText(tr("wizard.name_exists", name=name))
                self._name_warning.show()
            else:
                self._name_warning.hide()

            path = self._im.instances_path() / name
            self._name_path_label.setText(tr("wizard.path_preview", path=str(path)))

        self._update_nav_buttons()

    def _on_advanced_paths_toggled(self, checked: bool) -> None:
        """Show/hide advanced path fields."""
        self._paths_form.setVisible(checked)

    # ── Helpers ───────────────────────────────────────────────────────

    def _populate_game_list(self) -> None:
        """Populate the game selection list."""
        self._game_model.clear()
        if self._pl is None or self._im is None:
            return

        existing = {inst.get("game_short_name", "") for inst in self._im.list_instances()}

        for plugin in self._pl.installed_games():
            if plugin.GameShortName in existing:
                continue

            gd = plugin.gameDirectory()
            store = plugin.detectedStore() or ""
            detail = f"{store}  \u2014  {gd}" if gd else store
            text = f"{plugin.GameName}  \u2014  {detail}"

            item = QStandardItem(text)
            item.setData(plugin.GameShortName, Qt.ItemDataRole.UserRole)
            item.setIcon(self._game_icon(plugin.GameShortName))
            self._game_model.appendRow(item)

        if self._game_model.rowCount() == 0:
            item = QStandardItem(tr("wizard.no_games"))
            item.setEnabled(False)
            self._game_model.appendRow(item)
        else:
            self._game_list.setCurrentIndex(self._game_proxy.index(0, 0))

    def _populate_variants(self) -> None:
        """Populate game variants."""
        # Clear existing
        while self._variants_container.count():
            child = self._variants_container.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Clear button group
        for btn in self._variants_group.buttons():
            self._variants_group.removeButton(btn)

        short = self._selected_game_short_name()
        if not short or short.lower() not in GAME_VARIANTS:
            return

        variants = GAME_VARIANTS[short.lower()]
        for i, variant in enumerate(variants):
            radio = QRadioButton(variant)
            if i == 0:
                radio.setChecked(True)
            self._variants_group.addButton(radio, i)
            self._variants_container.addWidget(radio)

    def _has_variants(self) -> bool:
        """Check if current game has variants."""
        short = self._selected_game_short_name()
        if not short:
            return False
        return short.lower() in GAME_VARIANTS

    def _init_name_page(self) -> None:
        """Initialize the name page with default name."""
        short = self._selected_game_short_name()
        plugin = self._pl.get_game(short) if short and self._pl else None

        if plugin and not self._name_edit.text().strip():
            self._name_edit.setText(plugin.GameName)
            self._on_name_changed(plugin.GameName)

    def _populate_summary(self) -> None:
        """Populate the confirmation summary."""
        short = self._selected_game_short_name()
        plugin = self._pl.get_game(short) if short and self._pl else None
        name = self._name_edit.text().strip()

        if plugin:
            self._sum_game.setText(plugin.GameName)
            self._sum_store.setText(plugin.detectedStore() or tr("wizard.not_detected"))
            gd = plugin.gameDirectory()
            self._sum_game_path.setText(str(gd) if gd else tr("wizard.not_detected"))
        else:
            self._sum_game.setText("\u2014")
            self._sum_store.setText("\u2014")
            self._sum_game_path.setText("\u2014")

        self._sum_name.setText(name)
        self._sum_type.setText(
            tr("wizard.type_global") if self._type_global.isChecked()
            else tr("wizard.type_portable")
        )

        if self._im:
            self._sum_instance_path.setText(str(self._im.instances_path() / name))
        else:
            self._sum_instance_path.setText("\u2014")

    def _selected_game_short_name(self) -> str | None:
        """Return the selected game's short name."""
        idx = self._game_list.currentIndex()
        if not idx.isValid():
            return None
        source_idx = self._game_proxy.mapToSource(idx)
        return source_idx.data(Qt.ItemDataRole.UserRole)

    def _game_icon(self, game_short_name: str) -> QIcon:
        """Return cached game icon or a placeholder."""
        if self._icons:
            pix = self._icons.get_game_icon(game_short_name)
            if pix is not None:
                return QIcon(pix)
        return QIcon(placeholder_game_icon(32))

    # ── Geometry Persistence ──────────────────────────────────────────

    def _restore_geometry(self) -> None:
        """Restore dialog geometry."""
        settings = QSettings("AnvilOrganizer", "InstanceWizard")
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # Check skip intro preference
        if settings.value("skip_intro", False, type=bool):
            self._skip_intro = True
            self._show_page(PAGE_TYPE)

    def closeEvent(self, event) -> None:
        """Save geometry on close."""
        settings = QSettings("AnvilOrganizer", "InstanceWizard")
        settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)
