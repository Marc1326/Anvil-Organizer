"""Hauptfenster: Menü, Toolbar, Profil-Leiste, Splitter 65:35, Statusbar."""

from __future__ import annotations

from pathlib import Path

import shutil

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QStackedWidget,
    QMessageBox,
    QSizePolicy,
    QFileDialog,
    QDialog,
    QMenu,
    QInputDialog,
    QTextEdit,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, QSettings, QUrl, QSize
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence

from anvil.styles.dark_theme import load_theme, default_theme
from anvil.widgets.toolbar import create_toolbar
from anvil.widgets.profile_bar import ProfileBar
from anvil.widgets.mod_list import ModListView
from anvil.widgets.collapsible_bar import CollapsibleSectionBar
from anvil.widgets.filter_panel import FilterPanel
from anvil.widgets.game_panel import GamePanel
from anvil.widgets.status_bar import StatusBarWidget
from anvil.widgets.toast import Toast
from anvil.dialogs import ModDetailDialog
from anvil.dialogs.quick_install_dialog import QuickInstallDialog
from anvil.dialogs.query_overwrite_dialog import QueryOverwriteDialog, OverwriteAction
from anvil.plugins.plugin_loader import PluginLoader
from anvil.core.instance_manager import InstanceManager
from anvil.core.icon_manager import IconManager
from anvil.core.mod_entry import scan_mods_directory
from anvil.core.mod_installer import ModInstaller, SUPPORTED_EXTENSIONS
from anvil.core.mod_list_io import (
    add_mod_to_modlist, write_modlist, remove_mod_from_modlist,
    rename_mod_in_modlist,
)
from anvil.core.categories import CategoryManager, _DEFAULT_CATEGORIES
from anvil.core.nexus_api import NexusAPI
from anvil.core.nxm_handler import parse_nxm_url, check_cli_for_nxm
from anvil.core.conflict_scanner import ConflictScanner
from anvil.models.mod_list_model import mod_entry_to_row
from anvil.widgets.instance_wizard import CreateInstanceWizard
from anvil.widgets.category_dialog import CategoryDialog
from anvil.widgets.log_panel import LogPanel


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


def _matches_direct_install(name_lower: str, patterns: list[str]) -> bool:
    """Check if a mod name matches any direct-install pattern.

    The name must start with the pattern AND the character after the
    pattern (if any) must be non-alphabetic (space, digit, dash, dot, etc.).
    This prevents 'CET' from matching 'CET NPC Body Tweaks' while still
    matching 'CET 1.37.1 - Scripting fixes'.
    """
    for pat in patterns:
        if not name_lower.startswith(pat):
            continue
        # Exact match or rest starts with a non-alpha char (version, suffix)
        rest = name_lower[len(pat):]
        if not rest or not rest[0].isalpha():
            return True
    return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anvil Organizer v0.1.0")
        self.setMinimumSize(1000, 650)
        self.resize(1200, 750)
        # Theme aus QSettings laden
        saved_theme = self._settings().value("style/theme", default_theme())
        self.setStyleSheet(load_theme(saved_theme))

        # ── Plugin-System ─────────────────────────────────────────────
        self.plugin_loader = PluginLoader()
        self.plugin_loader.load_plugins()

        # ── Instanz-System ────────────────────────────────────────────
        self.instance_manager = InstanceManager()
        self.icon_manager = IconManager()

        self._toolbar = create_toolbar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._toolbar)
        self._toolbar.installEventFilter(self)
        self._build_menu_bar()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # MO2: Profil-Leiste NUR über der linken Seite, nicht über die ganze Breite
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter = self._splitter
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        self._profile_bar = ProfileBar(self)
        self._profile_bar.collapse_all_requested.connect(self._collapse_all_separators)
        self._profile_bar.expand_all_requested.connect(self._expand_all_separators)
        self._profile_bar.reload_requested.connect(self._on_menu_refresh)
        self._profile_bar.export_csv_requested.connect(self._ctx_export_csv)
        self._profile_bar.open_game_requested.connect(self._open_game_folder)
        self._profile_bar.open_mygames_requested.connect(self._open_mygames_folder)
        self._profile_bar.open_ini_requested.connect(self._open_ini_folder)
        self._profile_bar.open_instance_requested.connect(self._open_instance_folder)
        self._profile_bar.open_mods_requested.connect(self._open_mods_folder)
        self._profile_bar.open_profile_requested.connect(self._open_profile_folder)
        self._profile_bar.open_downloads_requested.connect(self._open_downloads_folder)
        self._profile_bar.open_ao_install_requested.connect(self._open_ao_install_folder)
        self._profile_bar.open_ao_plugins_requested.connect(self._open_ao_plugins_folder)
        self._profile_bar.open_ao_styles_requested.connect(self._open_ao_styles_folder)
        self._profile_bar.open_ao_logs_requested.connect(self._open_ao_logs_folder)
        self._profile_bar.backup_requested.connect(self._create_backup)
        self._profile_bar.restore_requested.connect(self._restore_backup)
        self._profile_bar.profile_create_confirmed.connect(self._on_profile_created)
        self._profile_bar.profile_renamed.connect(self._on_profile_renamed)
        self._profile_bar.profile_changed.connect(self._on_profile_changed)
        self._profile_bar.profile_delete_requested.connect(self._on_profile_deleted)
        left_layout.addWidget(self._profile_bar)
        self._mod_list_view = ModListView()
        self._mod_list_view._tree.doubleClicked.connect(self._on_mod_double_click)
        self._mod_list_view.context_menu_requested.connect(self._on_mod_context_menu)

        # Stacked widget: standard mod list (index 0) / BG3 mod list (index 1)
        self._mod_list_stack = QStackedWidget()
        self._mod_list_stack.addWidget(self._mod_list_view)

        # ── FilterPanel + ModList ────────────────────────────────────
        self._filter_panel = FilterPanel()
        self._filter_panel.filter_changed.connect(self._on_filter_changed)
        self._filter_panel.panel_toggled.connect(self._on_filter_panel_toggled)
        self._filter_panel.category_add_requested.connect(self._on_category_add)
        self._filter_panel.category_rename_requested.connect(self._on_category_rename)
        self._filter_panel.category_delete_requested.connect(self._on_category_delete)

        self._filter_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._filter_splitter.addWidget(self._filter_panel)
        self._filter_splitter.addWidget(self._mod_list_stack)
        self._filter_splitter.setStretchFactor(0, 0)
        self._filter_splitter.setStretchFactor(1, 1)
        self._filter_splitter.setSizes([220, 560])
        self._filter_splitter.setChildrenCollapsible(False)
        self._filter_panel.set_splitter(self._filter_splitter)

        left_layout.addWidget(self._filter_splitter)

        # BG3 mod list (lazy-created when needed)
        self._bg3_mod_list: None = None  # BG3ModListView, created on demand
        self._bg3_installer = None       # BG3ModInstaller, cached
        splitter.addWidget(left_pane)
        self._game_panel = GamePanel()
        splitter.addWidget(self._game_panel)
        splitter.setSizes([780, 420])
        main_layout.addWidget(splitter)

        # ── Log-Panel (collapsible section with card-style panel) ───────
        self._log_container = QWidget()
        self._log_container.setMinimumHeight(28)
        self._log_container.setMaximumHeight(232)  # 28 bar + 204 LogPanel
        log_layout = QVBoxLayout(self._log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(0)

        self._log_panel = LogPanel()
        self._log_panel.setMaximumHeight(204)

        self._log_bar = CollapsibleSectionBar(
            "Log",
            "log",
            self._log_panel,
            style="QLabel { font-weight: bold; padding: 4px 6px; "
                  "background: #1a2a3a; border-bottom: 1px solid #333; }",
            container=self._log_container,
            default_collapsed=True,
            max_expanded_height=232,
        )
        self._log_bar.toggled.connect(self._on_log_bar_toggled)
        log_layout.addWidget(self._log_bar)
        log_layout.addWidget(self._log_panel)
        main_layout.addWidget(self._log_container)

        self._status_bar = StatusBarWidget(self)
        self.setStatusBar(self._status_bar)

        # ── Restore view settings (toolbar size, visibility, etc.) ────
        self._restore_view_settings()

        # ── Category manager ────────────────────────────────────────────
        self._category_manager = CategoryManager()

        # ── Nexus API ────────────────────────────────────────────────
        self._nexus_api = NexusAPI(self)
        saved_key = self._settings().value("nexus/api_key", "")
        if saved_key:
            self._nexus_api.set_api_key(saved_key)
            self._status_bar.update_api_status(logged_in=True)
        self._nexus_api.request_finished.connect(self._on_nexus_response)
        self._nexus_api.request_error.connect(self._on_nexus_error)
        self._nexus_api.rate_limit_updated.connect(self._update_api_status)

        # ── Mod state ─────────────────────────────────────────────────
        self._current_mod_entries = []
        self._current_profile_path: Path | None = None
        self._current_instance_path: Path | None = None
        self._current_plugin = None  # Active game plugin
        self._current_game_path: Path | None = None

        # Connect model signals for persistence
        model = self._mod_list_view.source_model()
        model.mod_toggled.connect(self._on_mod_toggled)
        model.mods_reordered.connect(self._on_mods_reordered)
        self._mod_list_view.archives_dropped.connect(
            self._on_archives_dropped, Qt.ConnectionType.QueuedConnection,
        )
        self._game_panel.install_requested.connect(self._on_downloads_install)
        self._game_panel.start_requested.connect(self._on_start_game)

        # ── Deferred tab column restore ───────────────────────────────
        self._restored_tabs: set[int] = set()
        self._game_panel._tabs.currentChanged.connect(self._on_tab_changed)

        # ── Erster Start / Instanz laden ──────────────────────────────
        self._check_first_start()

        # App-weiter Event-Filter für ContextMenu-Events (Wayland-Kompatibilität)
        from PySide6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

    # ── Menu bar (MO2-Struktur) ─────────────────────────────────────

    def _build_menu_bar(self) -> None:
        """Build the full MO2-style menu bar."""
        menubar = self.menuBar()

        # ════════════════════════════════════════════════════════════════
        # 1. DATEI
        # ════════════════════════════════════════════════════════════════
        fm = menubar.addMenu("Datei")

        act = fm.addAction("Instanzen verwalten...")
        act.triggered.connect(self._on_manage_instances)

        act = fm.addAction("Mod installieren...")
        act.setShortcut(QKeySequence("Ctrl+M"))
        act.triggered.connect(self._on_install_mod)

        act = fm.addAction("Nexus besuchen")
        act.setShortcut(QKeySequence("Ctrl+N"))
        act.triggered.connect(self._on_menu_visit_nexus)

        fm.addSeparator()

        act = fm.addAction("Beenden")
        act.triggered.connect(self.close)

        # ════════════════════════════════════════════════════════════════
        # 2. ANSICHT
        # ════════════════════════════════════════════════════════════════
        vm = menubar.addMenu("Ansicht")

        act = vm.addAction("Neu laden")
        act.setShortcut(QKeySequence("F5"))
        act.triggered.connect(self._on_menu_refresh)

        # ── Toolbars (Submenu) ─────────────────────────────────────
        self._tb_menu = vm.addMenu("Toolbars")

        # Visibility toggles
        self._act_menubar = self._tb_menu.addAction("Menüleiste")
        self._act_menubar.setCheckable(True)
        self._act_menubar.triggered.connect(self._on_toggle_menubar)

        self._act_toolbar = self._tb_menu.addAction("Hauptleiste")
        self._act_toolbar.setCheckable(True)
        self._act_toolbar.triggered.connect(self._on_toggle_toolbar)

        self._act_statusbar = self._tb_menu.addAction("Statusleiste")
        self._act_statusbar.setCheckable(True)
        self._act_statusbar.triggered.connect(self._on_toggle_statusbar)

        self._tb_menu.addSeparator()

        # Icon size (radio group)
        size_group = QActionGroup(self)
        self._act_small_icons = self._tb_menu.addAction("Kleine Icons")
        self._act_small_icons.setCheckable(True)
        self._act_small_icons.setActionGroup(size_group)
        self._act_small_icons.triggered.connect(lambda: self._set_toolbar_icon_size(0))

        self._act_medium_icons = self._tb_menu.addAction("Mittlere Icons")
        self._act_medium_icons.setCheckable(True)
        self._act_medium_icons.setActionGroup(size_group)
        self._act_medium_icons.triggered.connect(lambda: self._set_toolbar_icon_size(1))

        self._act_large_icons = self._tb_menu.addAction("Große Icons")
        self._act_large_icons.setCheckable(True)
        self._act_large_icons.setActionGroup(size_group)
        self._act_large_icons.triggered.connect(lambda: self._set_toolbar_icon_size(2))

        self._tb_menu.addSeparator()

        # Button style (radio group)
        style_group = QActionGroup(self)
        self._act_icons_only = self._tb_menu.addAction("Nur Icons")
        self._act_icons_only.setCheckable(True)
        self._act_icons_only.setActionGroup(style_group)
        self._act_icons_only.triggered.connect(
            lambda: self._set_toolbar_button_style(Qt.ToolButtonStyle.ToolButtonIconOnly))

        self._act_text_only = self._tb_menu.addAction("Nur Text")
        self._act_text_only.setCheckable(True)
        self._act_text_only.setActionGroup(style_group)
        self._act_text_only.triggered.connect(
            lambda: self._set_toolbar_button_style(Qt.ToolButtonStyle.ToolButtonTextOnly))

        self._act_icons_text = self._tb_menu.addAction("Icons und Text")
        self._act_icons_text.setCheckable(True)
        self._act_icons_text.setActionGroup(style_group)
        self._act_icons_text.triggered.connect(
            lambda: self._set_toolbar_button_style(Qt.ToolButtonStyle.ToolButtonTextUnderIcon))

        # Sync checkmarks when menu is about to show
        self._tb_menu.aboutToShow.connect(self._update_toolbar_menu)

        # ── Filter-Panel (Toggle) ─────────────────────────────────
        self._act_filter_panel = vm.addAction("Filter-Panel")
        self._act_filter_panel.setCheckable(True)
        self._act_filter_panel.setChecked(False)
        self._act_filter_panel.setShortcut(QKeySequence("Ctrl+F"))
        self._act_filter_panel.triggered.connect(self._on_toggle_filter_panel)

        # ── Log (Toggle) ──────────────────────────────────────────
        self._act_log = vm.addAction("Log")
        self._act_log.setCheckable(True)
        self._act_log.setChecked(False)  # default_collapsed=True
        self._act_log.triggered.connect(self._on_toggle_log)

        vm.addSeparator()

        act = vm.addAction("Benachrichtigungen...")
        act.setEnabled(False)

        # ════════════════════════════════════════════════════════════════
        # 3. WERKZEUGE
        # ════════════════════════════════════════════════════════════════
        tm = menubar.addMenu("Werkzeuge")

        act = tm.addAction("Profile...")
        act.setShortcut(QKeySequence("Ctrl+P"))
        act.triggered.connect(self._on_menu_profiles)

        act = tm.addAction("Executables...")
        act.setShortcut(QKeySequence("Ctrl+E"))
        act.triggered.connect(self._on_menu_executables)

        tm.addSeparator()

        act = tm.addAction("Tool-Plugins")
        act.setShortcut(QKeySequence("Ctrl+I"))
        act.setEnabled(False)

        tm.addSeparator()

        act = tm.addAction("Einstellungen...")
        act.setShortcut(QKeySequence("Ctrl+S"))
        act.triggered.connect(self._on_menu_settings)

        # ════════════════════════════════════════════════════════════════
        # 4. HILFE
        # ════════════════════════════════════════════════════════════════
        hm = menubar.addMenu("Hilfe")

        act = hm.addAction("Hilfe")
        act.setShortcut(QKeySequence("Ctrl+H"))
        act.triggered.connect(self._on_menu_help)

        act = hm.addAction("UI-Hilfe")
        act.setEnabled(False)

        act = hm.addAction("Dokumentation")
        act.setEnabled(False)

        act = hm.addAction("Chat auf Discord")
        act.setEnabled(False)

        act = hm.addAction("Problem melden")
        act.setEnabled(False)

        tutorials_menu = hm.addMenu("Tutorials")
        tutorials_menu.setEnabled(False)

        hm.addSeparator()

        act = hm.addAction("Über Anvil Organizer")
        act.triggered.connect(self._on_about)

        act = hm.addAction("Über Qt")
        act.setEnabled(False)

    # ── MO2 icon size constants ─────────────────────────────────────

    _ICON_SIZES = [QSize(24, 24), QSize(32, 32), QSize(42, 36)]

    # ── Menu action handlers ──────────────────────────────────────────

    def _on_manage_instances(self) -> None:
        """Datei → Instanzen verwalten..."""
        from anvil.widgets.instance_manager_dialog import InstanceManagerDialog
        dlg = InstanceManagerDialog(
            self, self.instance_manager, self.plugin_loader,
            self.icon_manager,
        )
        dlg.exec()
        if dlg.switched_to:
            self.switch_instance(dlg.switched_to)

    def _on_menu_visit_nexus(self) -> None:
        """Datei → Nexus besuchen."""
        nexus_slug = ""
        if self._current_plugin:
            nexus_slug = getattr(self._current_plugin, "GameNexusName", "") or getattr(self._current_plugin, "GameShortName", "")
        if nexus_slug:
            QDesktopServices.openUrl(QUrl(f"https://www.nexusmods.com/{nexus_slug}"))
        else:
            QDesktopServices.openUrl(QUrl("https://www.nexusmods.com"))

    def _on_menu_refresh(self) -> None:
        """Ansicht → Neu laden (F5)."""
        self._reload_mod_list()
        self.statusBar().showMessage("Mod-Liste neu geladen", 3000)

    def _on_toggle_filter_panel(self, checked: bool) -> None:
        """Ansicht → Filter-Panel (Menu action / Strg+F)."""
        self._filter_panel.set_open(checked)
        self._act_filter_panel.blockSignals(True)
        self._act_filter_panel.setChecked(checked)
        self._act_filter_panel.blockSignals(False)

    def _on_filter_panel_toggled(self, is_open: bool) -> None:
        """FilterPanel toggle bar was clicked — sync menu action."""
        self._act_filter_panel.blockSignals(True)
        self._act_filter_panel.setChecked(is_open)
        self._act_filter_panel.blockSignals(False)

    def _on_category_add(self, name: str) -> None:
        """Inline add: create a new category and refresh chips."""
        if not self._current_instance_path:
            return
        self._category_manager.add_category(name)
        self._filter_panel.set_categories(self._category_manager.all_categories())
        self.statusBar().showMessage(f"Kategorie erstellt: {name}", 3000)

    def _on_category_rename(self, cat_id: int, new_name: str) -> None:
        """Inline rename: rename an existing category and refresh chips."""
        if not self._current_instance_path:
            return
        self._category_manager.rename_category(cat_id, new_name)
        self._filter_panel.set_categories(self._category_manager.all_categories())
        self.statusBar().showMessage(f"Kategorie umbenannt: {new_name}", 3000)

    def _on_category_delete(self, cat_id: int) -> None:
        """Delete a category after confirmation and refresh chips."""
        if not self._current_instance_path:
            return
        name = self._category_manager.get_name(cat_id) or str(cat_id)
        reply = QMessageBox.question(
            self, "Kategorie löschen",
            f"Kategorie \"{name}\" wirklich löschen?\n\n"
            "Die Kategorie wird von allen Mods entfernt.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._category_manager.remove_category(cat_id)
        self._filter_panel.set_categories(self._category_manager.all_categories())
        self.statusBar().showMessage(f"Kategorie gelöscht: {name}", 3000)

    def _on_toggle_log(self, checked: bool) -> None:
        """Ansicht → Log (Toggle) — sync with CollapsibleSectionBar."""
        self._log_bar.set_collapsed(not checked)

    def _on_log_bar_toggled(self, is_open: bool) -> None:
        """Log bar was clicked — sync menu action."""
        self._act_log.blockSignals(True)
        self._act_log.setChecked(is_open)
        self._act_log.blockSignals(False)

    def _on_toggle_menubar(self, checked: bool) -> None:
        """Ansicht → Toolbars → Menüleiste (Toggle)."""
        self.menuBar().setVisible(checked)

    def _on_toggle_toolbar(self, checked: bool) -> None:
        """Ansicht → Toolbars → Hauptleiste (Toggle)."""
        self._toolbar.setVisible(checked)

    def _on_toggle_statusbar(self, checked: bool) -> None:
        """Ansicht → Toolbars → Statusleiste (Toggle)."""
        self._status_bar.setVisible(checked)

    def _set_toolbar_icon_size(self, idx: int) -> None:
        """Set toolbar icon size: 0=small, 1=medium, 2=large."""
        size = self._ICON_SIZES[idx]
        self._toolbar.setIconSize(size)

    def _set_toolbar_button_style(self, style: Qt.ToolButtonStyle) -> None:
        """Set toolbar button style."""
        self._toolbar.setToolButtonStyle(style)

    def _update_toolbar_menu(self) -> None:
        """Sync checkmarks with actual widget state (MO2 pattern)."""
        self._act_menubar.setChecked(self.menuBar().isVisible())
        self._act_toolbar.setChecked(self._toolbar.isVisible())
        self._act_statusbar.setChecked(self._status_bar.isVisible())

        cur_size = self._toolbar.iconSize()
        self._act_small_icons.setChecked(cur_size == self._ICON_SIZES[0])
        self._act_medium_icons.setChecked(cur_size == self._ICON_SIZES[1])
        self._act_large_icons.setChecked(cur_size == self._ICON_SIZES[2])

        cur_style = self._toolbar.toolButtonStyle()
        self._act_icons_only.setChecked(cur_style == Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._act_text_only.setChecked(cur_style == Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._act_icons_text.setChecked(cur_style == Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

    def _on_menu_profiles(self) -> None:
        """Werkzeuge → Profile... (Strg+P)."""
        from anvil.widgets.profile_dialog import ProfileDialog
        ProfileDialog(self).exec()

    def _on_menu_executables(self) -> None:
        """Werkzeuge → Executables... (Strg+E)."""
        from anvil.widgets.executables_dialog import ExecutablesDialog
        ExecutablesDialog(self).exec()

    def _on_menu_settings(self) -> None:
        """Werkzeuge → Einstellungen... (Strg+S)."""
        from anvil.widgets.settings_dialog import SettingsDialog
        SettingsDialog(
            self,
            self.plugin_loader,
            self.instance_manager,
        ).exec()

    def _on_menu_help(self) -> None:
        """Hilfe → Hilfe (Strg+H)."""
        QDesktopServices.openUrl(
            QUrl("https://github.com/Marc1326/Anvil-Organizer")
        )

    # ── View settings persistence ────────────────────────────────────

    def _restore_view_settings(self) -> None:
        """Restore toolbar icon size, button style, and visibility from QSettings."""
        s = self._settings()

        # Icon size (default: 1 = medium = 32x32)
        size_idx = int(s.value("view/toolbar_icon_size", 1))
        if 0 <= size_idx < len(self._ICON_SIZES):
            self._toolbar.setIconSize(self._ICON_SIZES[size_idx])
        else:
            self._toolbar.setIconSize(self._ICON_SIZES[1])

        # Button style (default: ToolButtonIconOnly = 0)
        style_val = int(s.value("view/toolbar_button_style", 0))
        self._toolbar.setToolButtonStyle(Qt.ToolButtonStyle(style_val))

        # Visibility (default: all visible except log)
        if s.value("view/menubar_visible") is not None:
            self.menuBar().setVisible(s.value("view/menubar_visible", True, type=bool))
        if s.value("view/toolbar_visible") is not None:
            self._toolbar.setVisible(s.value("view/toolbar_visible", True, type=bool))
        if s.value("view/statusbar_visible") is not None:
            self._status_bar.setVisible(s.value("view/statusbar_visible", True, type=bool))

        # Filter panel
        fp_open = s.value("view/filter_panel_open", False, type=bool)
        self._filter_panel.set_open(fp_open)
        self._act_filter_panel.setChecked(fp_open)
        fp_splitter = s.value("view/filter_splitter_state")
        if fp_splitter:
            self._filter_splitter.restoreState(fp_splitter)

        # Log: CollapsibleSectionBar restores its own state; sync menu check
        self._act_log.setChecked(not self._log_bar.collapsed)

    def _show_view_recovery_menu(self, global_pos) -> None:
        """Show the view/toolbar recovery context menu at *global_pos*.

        This allows recovering the menu bar when it's hidden.
        """
        menu = QMenu(self)
        for action in self._tb_menu.actions():
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction(self._act_log)
        self._update_toolbar_menu()
        menu.exec(global_pos)

    def eventFilter(self, obj, event):
        from PySide6.QtWidgets import QToolBar
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QCursor

        if event.type() == QEvent.Type.ContextMenu:
            # Toolbar: View-Recovery-Menü
            if isinstance(obj, QToolBar):
                self._show_view_recovery_menu(QCursor.pos())
                return True
            # FilterPanel und Chips handlen ihre Kontextmenüs selbst
            # via CustomContextMenu + customContextMenuRequested Signal

        return super().eventFilter(obj, event)

    # ── Instance switching ────────────────────────────────────────────

    def _check_first_start(self) -> None:
        """Open wizard on first start or load current instance.

        Also performs crash-recovery: if a stale deploy manifest
        exists from a previous session that didn't shut down cleanly,
        purge it before loading.
        """
        # Crash-recovery: purge stale deployments from previous sessions
        self._crash_recovery_purge()

        if not self.instance_manager.list_instances():
            # No instances yet — open wizard directly
            wizard = CreateInstanceWizard(
                self, self.instance_manager, self.plugin_loader,
                self.icon_manager,
            )
            wizard.exec()
            if wizard.created_instance:
                self.switch_instance(wizard.created_instance)
                return

        # Load current instance (if any)
        current = self.instance_manager.current_instance()
        if current:
            self._apply_instance(current)
        else:
            self._status_bar.clear_instance()

        # Check for nxm:// URL passed via command line
        nxm_link = check_cli_for_nxm()
        if nxm_link:
            self._handle_nxm_link(nxm_link)

    def _crash_recovery_purge(self) -> None:
        """Purge stale deploy manifests from all instances.

        If the app crashed or was killed, symlinks may still exist in
        the game directory.  Scan all instances for leftover manifests
        and purge them.
        """
        from anvil.core.mod_deployer import ModDeployer

        for entry in self.instance_manager.list_instances():
            name = entry.get("name", "") if isinstance(entry, dict) else str(entry)
            if not name:
                continue
            instance_path = self.instance_manager.instances_path() / name
            manifest = instance_path / ModDeployer.MANIFEST_NAME
            if manifest.is_file():
                data = self.instance_manager.load_instance(name)
                game_path_str = data.get("game_path", "") if data else ""
                if game_path_str:
                    game_path = Path(game_path_str)
                    if game_path.is_dir():
                        deployer = ModDeployer(instance_path, game_path)
                        deployer.purge()

    def switch_instance(self, instance_name: str) -> None:
        """Switch to a different instance and update all UI components.

        Called by the toolbar after the instance manager dialog closes.

        Args:
            instance_name: Name of the instance to switch to.
        """
        self.instance_manager.set_current_instance(instance_name)
        self._apply_instance(instance_name)

    def _apply_instance(self, instance_name: str) -> None:
        """Load instance data and update all widgets.

        Purges any previous deployment before switching, then
        auto-deploys after the new instance is fully loaded.

        Args:
            instance_name: Name of the instance to apply.
        """
        # Purge old deployment before switching
        self._game_panel.silent_purge()

        data = self.instance_manager.load_instance(instance_name)
        if not data:
            self.setWindowTitle("Anvil Organizer v0.1.0")
            self._game_panel.update_game("Kein Spiel ausgewählt", None)
            self._mod_list_view.clear_mods()
            self._current_mod_entries = []
            self._current_profile_path = None
            self._current_instance_path = None
            self._bg3_installer = None
            self._toolbar.deploy_sep.setVisible(False)
            self._toolbar.deploy_action.setVisible(False)
            self._mod_list_stack.setCurrentWidget(self._mod_list_view)
            self._update_active_count()
            self._status_bar.clear_instance()
            return

        game_name = data.get("game_name", instance_name)
        short_name = data.get("game_short_name", "")
        store = data.get("detected_store", "")
        game_path_str = data.get("game_path", "")

        # Find the game plugin and path
        game_path: Path | None = None
        if game_path_str:
            p = Path(game_path_str)
            if p.is_dir():
                game_path = p

        plugin = self.plugin_loader.get_game(short_name) if short_name else None
        self._current_plugin = plugin
        self._current_game_path = game_path

        # 1. Title
        self.setWindowTitle(f"{game_name} \u2013 Anvil Organizer v0.1.0")
        self._log_panel.add_log("info", f"Instanz geladen: {game_name}")

        # 2. Game panel — real directory contents + executables + icons
        self._game_panel.update_game(game_name, game_path, plugin, self.icon_manager, short_name)

        # 3. Instance path
        self._current_instance_path = self.instance_manager.instances_path() / instance_name
        instance_path = self._current_instance_path

        # 4. Downloads tab
        self._game_panel.set_downloads_path(
            instance_path / ".downloads", instance_path / ".mods",
        )
        self._game_panel.download_manager().set_downloads_dir(instance_path / ".downloads")

        # ── BG3-specific path ─────────────────────────────────────
        if short_name == "baldursgate3":
            self._apply_bg3_instance(instance_name, data, plugin, game_path)
            self._status_bar.update_instance(game_name, short_name, store)
            self._restore_ui_state()
            return

        # ── Standard path (non-BG3) ──────────────────────────────
        # Hide BG3 deploy button, switch to standard mod list
        self._toolbar.deploy_sep.setVisible(False)
        self._toolbar.deploy_action.setVisible(False)
        self._mod_list_stack.setCurrentWidget(self._mod_list_view)
        self._bg3_installer = None

        # Load categories for this instance
        self._category_manager.load(instance_path)
        self._mod_list_view.source_model().set_category_manager(self._category_manager)
        self._mod_list_view._proxy_model.set_category_manager(self._category_manager)

        # Populate FilterPanel with categories
        self._filter_panel.set_categories(self._category_manager.all_categories())
        self._filter_panel.reset_all()

        # Load available profiles from disk
        profiles_dir = instance_path / ".profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        profile_folders = sorted([d.name for d in profiles_dir.iterdir() if d.is_dir()])
        if not profile_folders:
            (profiles_dir / "Default").mkdir(exist_ok=True)
            profile_folders = ["Default"]

        profile_name = data.get("selected_profile", "Default")
        if profile_name not in profile_folders:
            profile_name = profile_folders[0]

        self._profile_bar.set_profiles(profile_folders, active=profile_name)
        self._current_profile_path = instance_path / ".profiles" / profile_name
        self._current_mod_entries = scan_mods_directory(instance_path, self._current_profile_path)
        # Mark direct-install (framework) mods
        direct_patterns = getattr(plugin, "GameDirectInstallMods", []) if plugin else []
        if direct_patterns:
            lp = [p.lower() for p in direct_patterns]
            for entry in self._current_mod_entries:
                name_lower = (entry.display_name or entry.name).lower()
                if _matches_direct_install(name_lower, lp):
                    entry.is_direct_install = True
        conflict_data = self._compute_conflict_data()
        # Filter out framework (direct-install) mods from the main list
        visible_entries = [e for e in self._current_mod_entries if not e.is_direct_install]
        mod_rows = [mod_entry_to_row(e, conflict_data) for e in visible_entries]
        self._mod_list_view.source_model().set_mods(mod_rows)
        # Provide visible entries to proxy for filter logic
        self._mod_list_view._proxy_model.set_mod_entries(visible_entries)
        self._update_active_count()

        # Log mod count
        active_count = sum(1 for e in visible_entries if e.enabled)
        self._log_panel.add_log("info", f"{len(visible_entries)} Mods geladen ({active_count} aktiv)")

        # Framework detection (Cyberpunk, etc.)
        if plugin is not None:
            fw_list = []
            for fw, installed in plugin.get_installed_frameworks():
                fw_list.append({
                    "name": fw.name,
                    "description": fw.description,
                    "installed": installed,
                })
            self._mod_list_view.load_frameworks(fw_list)
        else:
            self._mod_list_view.load_frameworks([])

        # 5. Mod deployer + auto-deploy
        self._game_panel.set_instance_path(instance_path)
        self._game_panel.silent_deploy()

        # 6. Status bar
        self._status_bar.update_instance(game_name, short_name, store)

        # 7. Restore saved column widths / splitter (after data is populated)
        self._restore_ui_state()

    # ── Mod list persistence ─────────────────────────────────────────

    def _write_current_modlist(self) -> None:
        """Write the current mod entries to modlist.txt."""
        if self._current_profile_path is None:
            return
        mods = [(e.name, e.enabled) for e in self._current_mod_entries]
        write_modlist(self._current_profile_path, mods)

    def _on_mod_toggled(self, row: int, enabled: bool) -> None:
        """A mod checkbox was toggled — update entries and persist."""
        if 0 <= row < len(self._current_mod_entries):
            self._current_mod_entries[row].enabled = enabled
        self._write_current_modlist()
        self._update_active_count()

    def _on_mods_reordered(self) -> None:
        """Mods were reordered via drag & drop — sync entries and persist."""
        model = self._mod_list_view.source_model()
        # Rebuild _current_mod_entries from the model's new order
        new_entries = []
        for i in range(model.rowCount()):
            row_data = model._rows[i]
            # Find matching entry by display_name or folder name
            for entry in self._current_mod_entries:
                display = entry.display_name or entry.name
                if display == row_data.name and entry not in new_entries:
                    entry.priority = i
                    new_entries.append(entry)
                    break
        self._current_mod_entries = new_entries
        self._write_current_modlist()
        self._update_active_count()
        # Recompute conflict icons (priorities changed → winner may differ)
        conflict_data = self._compute_conflict_data()
        for row_data in model._rows:
            folder = row_data.folder_name
            row_data.conflicts = conflict_data.get(folder, "")
        model.dataChanged.emit(
            model.index(0, 0),
            model.index(model.rowCount() - 1, model.columnCount() - 1),
        )

    def _update_active_count(self) -> None:
        """Update the active mod counter in the profile bar."""
        active = sum(1 for e in self._current_mod_entries if e.enabled)
        total = len(self._current_mod_entries)
        self._profile_bar.update_active_count(active, total)

    def _on_filter_changed(self) -> None:
        """FilterPanel chip/text changed — update proxy filter."""
        proxy = self._mod_list_view._proxy_model
        proxy.set_filter_state(
            self._filter_panel.search_text(),
            self._filter_panel.active_property_ids(),
            self._filter_panel.active_category_ids(),
        )

    def _compute_conflict_data(self) -> dict:
        """Run ConflictScanner and return per-mod conflict info.

        Returns a dict mapping mod folder name to a conflict info dict:
        ``{"type": "win"|"lose"|"both", "wins": N, "losses": N,
           "win_mods": N, "lose_mods": N}``
        """
        if not self._current_instance_path or not self._current_mod_entries:
            return {}
        all_mods = [
            {"name": e.name, "path": str(self._current_instance_path / ".mods" / e.name)}
            for e in self._current_mod_entries if e.enabled
        ]
        if not all_mods:
            return {}
        result = ConflictScanner().scan_conflicts(all_mods, self._current_plugin)
        # Build per-mod conflict counts
        per_mod: dict[str, dict] = {}
        for conflict in result["conflicts"]:
            winner = conflict["winner"]
            for mod_name in conflict["mods"]:
                if mod_name not in per_mod:
                    per_mod[mod_name] = {"wins": 0, "losses": 0, "win_mods": set(), "lose_mods": set()}
                if mod_name == winner:
                    per_mod[mod_name]["wins"] += 1
                    for other in conflict["mods"]:
                        if other != mod_name:
                            per_mod[mod_name]["win_mods"].add(other)
                else:
                    per_mod[mod_name]["losses"] += 1
                    per_mod[mod_name]["lose_mods"].add(winner)
        # Convert sets to counts and determine type
        result_data: dict[str, dict] = {}
        for mod_name, info in per_mod.items():
            wins = info["wins"]
            losses = info["losses"]
            if wins > 0 and losses > 0:
                ctype = "both"
            elif wins > 0:
                ctype = "win"
            else:
                ctype = "lose"
            result_data[mod_name] = {
                "type": ctype,
                "wins": wins,
                "losses": losses,
                "win_mods": len(info["win_mods"]),
                "lose_mods": len(info["lose_mods"]),
            }
        return result_data

    # ── Mod installation ─────────────────────────────────────────────

    def _on_install_mod(self) -> None:
        """Menu: Datei → Mod installieren..."""
        if not self._current_instance_path:
            QMessageBox.warning(self, "Keine Instanz", "Bitte zuerst eine Instanz auswählen.")
            return

        # BG3: also accept .pak files
        if self._bg3_installer is not None:
            file_filter = "Mod-Dateien (*.zip *.rar *.7z *.pak);;Alle Dateien (*)"
        else:
            file_filter = "Archive (*.zip *.rar *.7z);;Alle Dateien (*)"

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Mod-Archiv(e) auswählen",
            str(Path.home()),
            file_filter,
        )
        if not files:
            return

        # BG3: use BG3ModInstaller
        if self._bg3_installer is not None:
            self._on_bg3_archives_dropped(files)
            return

        self._install_archives([Path(f) for f in files])

    def _on_archives_dropped(self, paths: list) -> None:
        """Handle archives dropped onto the mod list."""
        if not self._current_instance_path:
            return
        self._install_archives([Path(p) for p in paths])

    def _on_start_game(self, binary_path: str, working_dir: str) -> None:
        """Launch the selected game executable."""
        from PySide6.QtCore import QProcess
        success = QProcess.startDetached(binary_path, [], working_dir)
        if success:
            self.statusBar().showMessage(
                f"Gestartet: {Path(binary_path).name}", 5000,
            )
        else:
            QMessageBox.warning(
                self, "Starten fehlgeschlagen",
                f"Konnte nicht gestartet werden:\n{binary_path}",
            )

    def _on_downloads_install(self, paths: list) -> None:
        """Handle install request from the Downloads tab."""
        if not self._current_instance_path:
            return
        self._install_archives([Path(p) for p in paths])
        self._game_panel.refresh_downloads()

    def _install_archives(self, archives: list[Path]) -> None:
        """Install one or more archives as mods.

        MO2-Pattern (testOverwrite):
        - Name berechnen, prüfen ob .mods/{name} existiert
        - NEIN → direkt installieren, kein Dialog
        - JA  → QuickInstallDialog → QueryOverwriteDialog falls nötig
        """
        installer = ModInstaller(self._current_instance_path)
        installed = []

        for archive in archives:
            best, variants = installer.suggest_names(archive)
            mod_name = best
            dest = installer.mods_path / mod_name

            # Nur bei Duplikat: Dialog zeigen (MO2 testOverwrite-Pattern)
            if dest.exists():
                while True:
                    dlg = QuickInstallDialog(variants, mod_name, self)
                    if dlg.exec() != QDialog.DialogCode.Accepted:
                        mod_name = None
                        break
                    mod_name = dlg.mod_name()
                    if not mod_name:
                        continue  # empty name → show dialog again
                    dest = installer.mods_path / mod_name
                    if not dest.exists():
                        break  # neuer Name, kein Konflikt mehr
                    # Immer noch Duplikat → QueryOverwriteDialog
                    ovr = QueryOverwriteDialog(mod_name, self)
                    if ovr.exec() != QDialog.DialogCode.Accepted:
                        mod_name = None
                        break
                    action = ovr.action()
                    if action == OverwriteAction.RENAME:
                        continue  # zurück zum QuickInstallDialog
                    elif action == OverwriteAction.REPLACE:
                        shutil.rmtree(dest)
                    # MERGE: dest bleibt, Dateien werden reingeschrieben
                    break

            if not mod_name:
                continue  # user cancelled

            # Install
            mod_path = installer.install_from_archive(archive, mod_name)
            if mod_path:
                add_mod_to_modlist(self._current_profile_path, mod_path.name)
                installed.append(mod_path.name)
            else:
                QMessageBox.warning(
                    self, "Installation fehlgeschlagen",
                    f"Mod \"{mod_name}\" konnte nicht installiert werden.\n"
                    "Prüfe ob das Archiv gültig ist und die nötigen Tools installiert sind.",
                )

        if not installed:
            return

        # Reload mod list (reuses _reload_mod_list which handles framework filtering)
        self._reload_mod_list()

        names = ", ".join(installed)
        self.statusBar().showMessage(f"Installiert: {names}", 5000)

    # ── Other slots ───────────────────────────────────────────────────

    def _on_mod_double_click(self):
        mod_name = self._mod_list_view.get_current_mod_name()
        if mod_name:
            mod_path = str(self._current_instance_path / ".mods" / mod_name)
            all_mods = [
                {"name": e.name, "path": str(self._current_instance_path / ".mods" / e.name)}
                for e in self._current_mod_entries if e.enabled
            ]
            # ModEntry für diesen Mod finden
            mod_entry = next(
                (e for e in self._current_mod_entries if e.name == mod_name),
                None
            )
            ModDetailDialog(
                self, mod_name=mod_name, mod_path=mod_path,
                all_mods=all_mods, game_plugin=self._current_plugin,
                category_manager=self._category_manager,
                mod_entry=mod_entry,
            ).exec()

    # ── Mod list context menu ──────────────────────────────────────

    def _on_mod_context_menu(self, global_pos) -> None:
        """Build and show the mod list context menu (MO2 structure)."""
        print("[DEBUG] _on_mod_context_menu() aufgerufen!")
        if not self._current_instance_path:
            return

        selected_rows = self._mod_list_view.get_selected_source_rows()
        has_selection = len(selected_rows) > 0
        single = len(selected_rows) == 1

        menu = QMenu(self)

        # ── Alle Mods (Submenu) ────────────────────────────────────
        all_mods_menu = menu.addMenu("Alle Mods")
        act_install_mod = all_mods_menu.addAction("Installiere Mod...")
        act_create_empty = all_mods_menu.addAction("Erstelle leere Mod...")
        act_create_sep = all_mods_menu.addAction("Erstelle Trenner...")
        all_mods_menu.addSeparator()
        act_collapse_all = all_mods_menu.addAction("Alle einklappen")
        act_expand_all = all_mods_menu.addAction("Alle ausklappen")
        all_mods_menu.addSeparator()
        act_enable_all = all_mods_menu.addAction("Aktiviere alle")
        act_disable_all = all_mods_menu.addAction("Deaktiviere alle")
        act = all_mods_menu.addAction("Auf Updates prüfen")
        act.setEnabled(False)
        act = all_mods_menu.addAction("Kategorien automatisch zuweisen")
        act.setEnabled(False)
        act_reload = all_mods_menu.addAction("Neu laden")
        act_export_csv = all_mods_menu.addAction("Als CSV exportieren...")

        # ── Kategorien (Submenus) ─────────────────────────────────
        andere_kat_menu = menu.addMenu("Andere Kategorien")
        primaere_kat_menu = menu.addMenu("Primäre Kategorie")
        # Kein eigenes Stylesheet - globales Paper Dark.qss greift

        _cat_buttons = []  # keep refs: (cat_id, QPushButton)

        if single and selected_rows[0] < len(self._current_mod_entries):
            entry = self._current_mod_entries[selected_rows[0]]
            row = selected_rows[0]
            assigned_ids = set(entry.category_ids)

            from PySide6.QtWidgets import QWidgetAction, QPushButton

            # "Andere Kategorien" — toggle buttons (Menü bleibt offen)
            for cat in self._category_manager.all_categories():
                cat_id = cat["id"]
                is_assigned = cat_id in assigned_ids
                prefix = "●  " if is_assigned else "    "

                btn = QPushButton(f"{prefix}{cat['name']}")
                btn.setFlat(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                # Styling: türkis wenn zugewiesen
                if is_assigned:
                    btn.setStyleSheet("""
                        QPushButton {
                            color: #00d4aa;
                            font-weight: bold;
                            text-align: left;
                            padding: 6px 12px;
                            border: none;
                            background: transparent;
                        }
                        QPushButton:hover { background: #2d2d2d; }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            color: #e0e0e0;
                            text-align: left;
                            padding: 6px 12px;
                            border: none;
                            background: transparent;
                        }
                        QPushButton:hover { background: #2d2d2d; }
                    """)

                # Click-Handler: Toggle und UI aktualisieren
                def make_toggle_handler(cid, button, cats_menu, prim_menu):
                    def handler():
                        self._toggle_category(row, cid)
                        entry = self._current_mod_entries[row]
                        # UI aktualisieren ohne Menü zu schließen
                        new_assigned = cid in entry.category_ids
                        new_prefix = "●  " if new_assigned else "    "
                        cat_name = self._category_manager.get_name(cid)
                        button.setText(f"{new_prefix}{cat_name}")
                        if new_assigned:
                            button.setStyleSheet("""
                                QPushButton {
                                    color: #00d4aa;
                                    font-weight: bold;
                                    text-align: left;
                                    padding: 6px 12px;
                                    border: none;
                                    background: transparent;
                                }
                                QPushButton:hover { background: #2d2d2d; }
                            """)
                            # Erste Kategorie zugewiesen → automatisch als Primary
                            if len(entry.category_ids) == 1:
                                self._set_primary_category(row, cid)
                        else:
                            button.setStyleSheet("""
                                QPushButton {
                                    color: #e0e0e0;
                                    text-align: left;
                                    padding: 6px 12px;
                                    border: none;
                                    background: transparent;
                                }
                                QPushButton:hover { background: #2d2d2d; }
                            """)
                            # Letzte Kategorie entfernt → Primary auf 0
                            if not entry.category_ids:
                                self._set_primary_category(row, 0)
                            # Entfernte Kategorie war Primary → neue Primary setzen
                            elif entry.primary_category == cid or entry.primary_category not in entry.category_ids:
                                self._set_primary_category(row, entry.category_ids[0])

                        # "Primäre Kategorie" Menü NEU befüllen (mit gelbem Stern-Icon)
                        from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
                        prim_menu.clear()
                        if entry.category_ids:
                            prim_menu.setEnabled(True)
                            # Gelbes Stern-Icon erstellen
                            px = QPixmap(16, 16)
                            px.fill(Qt.GlobalColor.transparent)
                            p = QPainter(px)
                            p.setRenderHint(QPainter.RenderHint.Antialiasing)
                            f = QFont()
                            f.setPixelSize(16)
                            p.setFont(f)
                            p.setPen(QColor('#FFD700'))
                            p.drawText(0, 0, 16, 16, Qt.AlignmentFlag.AlignCenter, '★')
                            p.end()
                            s_icon = QIcon(px)

                            for cat_id_p in entry.category_ids:
                                name_p = self._category_manager.get_name(cat_id_p)
                                if not name_p:
                                    continue
                                is_prim = cat_id_p == entry.primary_category
                                if is_prim:
                                    act_p = prim_menu.addAction(s_icon, name_p)
                                else:
                                    act_p = prim_menu.addAction(f"    {name_p}")
                                act_p.setData(cat_id_p)
                        else:
                            prim_menu.setEnabled(False)
                    return handler

                btn.clicked.connect(make_toggle_handler(cat_id, btn, andere_kat_menu, primaere_kat_menu))

                wa = QWidgetAction(andere_kat_menu)
                wa.setDefaultWidget(btn)
                andere_kat_menu.addAction(wa)
                _cat_buttons.append((cat_id, btn))

            # "Primäre Kategorie" — QActions mit gelbem Stern-Icon
            from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont

            def create_star_icon(size=16):
                """Erstellt ein gelbes Stern-Icon."""
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                font = QFont()
                font.setPixelSize(size)
                painter.setFont(font)
                painter.setPen(QColor('#FFD700'))  # Gold
                painter.drawText(0, 0, size, size, Qt.AlignmentFlag.AlignCenter, '★')
                painter.end()
                return QIcon(pixmap)

            star_icon = create_star_icon()

            if assigned_ids:
                for cat_id in entry.category_ids:
                    name = self._category_manager.get_name(cat_id)
                    if not name:
                        continue
                    is_primary = cat_id == entry.primary_category
                    if is_primary:
                        act = primaere_kat_menu.addAction(star_icon, name)
                    else:
                        act = primaere_kat_menu.addAction(f"    {name}")
                    act.setData(cat_id)
            else:
                primaere_kat_menu.setEnabled(False)
        else:
            andere_kat_menu.setEnabled(False)
            primaere_kat_menu.setEnabled(False)
        menu.addSeparator()

        # ── Updates / Aktivieren ──────────────────────────────────
        act = menu.addAction("Update-Prüfung erzwingen")
        act.setEnabled(False)
        act = menu.addAction("Ignoriere Update")
        act.setEnabled(False)
        act_enable = menu.addAction("Aktiviere Ausgewählte")
        act_enable.setEnabled(has_selection)
        act_disable = menu.addAction("Deaktiviere Ausgewählte")
        act_disable.setEnabled(has_selection)
        menu.addSeparator()

        # ── Senden / Mod-Aktionen ────────────────────────────────
        send_to_menu = menu.addMenu("Sende zu...")
        send_to_menu.setEnabled(False)
        act_rename = menu.addAction("Mod umbenennen...")
        act_rename.setEnabled(single)
        act_reinstall = menu.addAction("Mod neu installieren")
        act_reinstall.setEnabled(single)
        act_remove = menu.addAction("Mod entfernen...")
        act_remove.setEnabled(has_selection)
        menu.addSeparator()

        # ── Sicherung / Nexus / Explorer ─────────────────────────
        act_backup = menu.addAction("Erstelle eine Sicherung")
        act_backup.setEnabled(single)
        act = menu.addAction("Endorsement entfernen")
        act.setEnabled(False)
        act = menu.addAction("Kategorie neu zuordnen (von Nexus)")
        act.setEnabled(False)
        act = menu.addAction("Beginne Beobachtung")
        act.setEnabled(False)
        # Nexus: nur aktiviert wenn Mod eine Nexus-ID hat
        act_nexus = menu.addAction("Besuche auf NexusMods")
        has_nexus = single and selected_rows[0] < len(self._current_mod_entries) and self._current_mod_entries[selected_rows[0]].nexus_id > 0
        act_nexus.setEnabled(has_nexus)
        act_explorer = menu.addAction("Öffne im Explorer")
        act_explorer.setEnabled(single)
        act_info = menu.addAction("Informationen...")
        act_info.setEnabled(single)

        # ── Execute ───────────────────────────────────────────────
        chosen = menu.exec(global_pos)

        # Handle "Primäre Kategorie" actions
        if chosen and single and selected_rows[0] < len(self._current_mod_entries):
            row = selected_rows[0]
            # Prüfe ob Action aus "Primäre Kategorie" (via .data())
            if chosen.data() is not None and chosen.parent() == primaere_kat_menu:
                cat_id = chosen.data()
                self._set_primary_category(row, cat_id)

        if not chosen:
            return

        print(f"[DEBUG] chosen = {chosen}, text = {chosen.text() if chosen else 'None'}")
        print(f"[DEBUG] act_install_mod = {act_install_mod}, text = {act_install_mod.text()}")
        print(f"[DEBUG] chosen == act_install_mod: {chosen == act_install_mod}")

        if chosen == act_install_mod:
            print("[MENU] Installiere Mod clicked")
            self._ctx_install_mod()
        elif chosen == act_create_empty:
            print("[MENU] Leere Mod clicked")
            self._ctx_create_empty_mod()
        elif chosen == act_create_sep:
            print("[MENU] Trenner clicked")
            self._ctx_create_separator()
        elif chosen == act_export_csv:
            print("[MENU] CSV Export clicked")
            self._ctx_export_csv()
        elif chosen == act_enable_all:
            self._ctx_enable_all(True)
        elif chosen == act_disable_all:
            self._ctx_enable_all(False)
        elif chosen == act_reload:
            self._on_menu_refresh()
        elif chosen == act_collapse_all:
            self._collapse_all_separators()
        elif chosen == act_expand_all:
            self._expand_all_separators()
        elif chosen == act_enable:
            self._ctx_enable_selected(selected_rows, True)
        elif chosen == act_disable:
            self._ctx_enable_selected(selected_rows, False)
        elif chosen == act_rename:
            self._ctx_rename_mod(selected_rows[0])
        elif chosen == act_reinstall:
            self._ctx_reinstall_mod(selected_rows[0])
        elif chosen == act_remove:
            self._ctx_remove_mods(selected_rows)
        elif chosen == act_backup:
            self._ctx_create_backup(selected_rows[0])
        elif chosen == act_nexus:
            self._ctx_visit_nexus(selected_rows[0])
        elif chosen == act_explorer:
            self._ctx_open_explorer(selected_rows[0])
        elif chosen == act_info:
            self._ctx_show_info(selected_rows[0])

    # ── Context menu actions ───────────────────────────────────────

    def _ctx_create_separator(self) -> None:
        """Create a new separator in the mod list."""
        name, ok = QInputDialog.getText(
            self, "Trenner erstellen", "Name des Trenners:",
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        folder_name = f"{name}_separator"

        mods_dir = self._current_instance_path / ".mods"
        sep_path = mods_dir / folder_name

        if sep_path.exists():
            QMessageBox.warning(
                self, "Trenner erstellen",
                f"Ein Trenner mit dem Namen \"{name}\" existiert bereits.",
            )
            return

        try:
            sep_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(
                self, "Trenner erstellen", str(exc),
            )
            return

        add_mod_to_modlist(self._current_profile_path, folder_name, True)
        self._reload_mod_list()
        self.statusBar().showMessage(f"Trenner erstellt: {name}", 5000)

    def _open_mods_folder(self) -> None:
        """Open the mods folder in file manager."""
        import subprocess
        print(f"DEBUG _open_mods_folder: instance={self._current_instance_path}")
        if not self._current_instance_path:
            print("DEBUG _open_mods_folder: No instance path, returning")
            return
        path = self._current_instance_path / ".mods"
        print(f"DEBUG _open_mods_folder: mods_path={path}, is_dir={path.is_dir()}")
        if path.is_dir():
            subprocess.Popen(["xdg-open", str(path)])

    def _open_game_folder(self) -> None:
        """Open the game installation folder in file manager."""
        import subprocess
        if not self._current_game_path:
            return
        if self._current_game_path.is_dir():
            subprocess.Popen(["xdg-open", str(self._current_game_path)])

    def _open_mygames_folder(self) -> None:
        """Open the My Games folder in file manager."""
        import subprocess
        if not self._current_plugin:
            return
        if hasattr(self._current_plugin, "gameDocumentsDirectory"):
            path = self._current_plugin.gameDocumentsDirectory()
            if path and path.is_dir():
                subprocess.Popen(["xdg-open", str(path)])

    def _open_ini_folder(self) -> None:
        """Open the INI folder in file manager (same as My Games for most games)."""
        import subprocess
        if not self._current_plugin:
            return
        if hasattr(self._current_plugin, "gameDocumentsDirectory"):
            path = self._current_plugin.gameDocumentsDirectory()
            if path and path.is_dir():
                subprocess.Popen(["xdg-open", str(path)])

    def _open_instance_folder(self) -> None:
        """Open the instance folder in file manager."""
        import subprocess
        if not self._current_instance_path:
            return
        if self._current_instance_path.is_dir():
            subprocess.Popen(["xdg-open", str(self._current_instance_path)])

    def _open_profile_folder(self) -> None:
        """Open the profile folder in file manager."""
        import subprocess
        print(f"DEBUG _open_profile_folder: profile={self._current_profile_path}")
        if not self._current_profile_path:
            print("DEBUG _open_profile_folder: No profile path, returning")
            return
        if self._current_profile_path.is_dir():
            subprocess.Popen(["xdg-open", str(self._current_profile_path)])

    def _open_downloads_folder(self) -> None:
        """Open the downloads folder in file manager."""
        import subprocess
        if not self._current_instance_path:
            return
        path = self._current_instance_path / ".downloads"
        if path.is_dir():
            subprocess.Popen(["xdg-open", str(path)])

    def _open_ao_install_folder(self) -> None:
        """Open the Anvil Organizer installation folder in file manager."""
        import subprocess
        path = Path(__file__).parent.parent
        if path.is_dir():
            subprocess.Popen(["xdg-open", str(path)])

    def _open_ao_plugins_folder(self) -> None:
        """Open the Anvil Organizer plugins folder in file manager."""
        import subprocess
        path = Path(__file__).parent / "plugins"
        if path.is_dir():
            subprocess.Popen(["xdg-open", str(path)])

    def _open_ao_styles_folder(self) -> None:
        """Open the Anvil Organizer styles folder in file manager."""
        import subprocess
        path = Path(__file__).parent / "styles"
        if path.is_dir():
            subprocess.Popen(["xdg-open", str(path)])

    def _open_ao_logs_folder(self) -> None:
        """Open the Anvil Organizer logs folder in file manager."""
        import subprocess
        path = Path.home() / ".anvil-organizer" / "logs"
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            subprocess.Popen(["xdg-open", str(path)])

    def _create_backup(self) -> None:
        """Create a ZIP backup of modlist, categories, and all meta.ini files."""
        try:
            import zipfile
            from datetime import datetime
            print("[BACKUP] Start")

            if not self._current_instance_path or not self._current_profile_path:
                print("[BACKUP] Keine Instanz/Profil")
                return

            # Paths
            backups_dir = self._current_instance_path / ".backups"
            backups_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            zip_path = backups_dir / f"backup_{timestamp}.zip"
            mods_dir = self._current_instance_path / ".mods"
            print(f"[BACKUP] ZIP: {zip_path}")

            # Create ZIP
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # modlist.txt
                modlist = self._current_profile_path / "modlist.txt"
                if modlist.exists():
                    zf.write(modlist, "modlist.txt")

                # categories.json
                cats = self._current_instance_path / "categories.json"
                if cats.exists():
                    zf.write(cats, "categories.json")

                # All meta.ini files
                for meta in mods_dir.glob("*/meta.ini"):
                    arcname = f"mods/{meta.parent.name}/meta.ini"
                    zf.write(meta, arcname)

            print("[BACKUP] ZIP erstellt")

            # Keep max 10 backups
            backups = sorted(backups_dir.glob("backup_*.zip"))
            while len(backups) > 10:
                backups[0].unlink()
                backups.pop(0)

            # Show confirmation with details
            mod_count = len(list(mods_dir.glob("*/meta.ini")))
            zip_size = zip_path.stat().st_size
            size_str = f"{zip_size / 1024:.1f} KB"
            print(f"[BACKUP] {mod_count} Mods, {size_str}")

            Toast(self, f"{mod_count} Mods gesichert | {zip_path.name} | {size_str}")
            print("[BACKUP] Toast gezeigt")
            self.statusBar().showMessage(f"Sicherung erstellt: {zip_path.name}", 5000)

        except Exception as e:
            print(f"[BACKUP] FEHLER: {e}")
            import traceback
            traceback.print_exc()

    def _restore_backup(self) -> None:
        """Restore from a ZIP backup using the card-based dialog."""
        import zipfile
        from anvil.dialogs.backup_dialog import BackupDialog

        if not self._current_instance_path or not self._current_profile_path:
            return

        backups_dir = self._current_instance_path / ".backups"
        backups = sorted(backups_dir.glob("backup_*.zip"), reverse=True)

        if not backups:
            QMessageBox.information(self, "Keine Sicherungen", "Es gibt keine Sicherungen zum Wiederherstellen.")
            return

        # Show card-based dialog
        dialog = BackupDialog(self, backups)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        zip_path = dialog.selected_backup()
        if not zip_path:
            return

        with zipfile.ZipFile(zip_path, 'r') as zf:
            # modlist.txt
            if "modlist.txt" in zf.namelist():
                data = zf.read("modlist.txt")
                (self._current_profile_path / "modlist.txt").write_bytes(data)

            # categories.json
            if "categories.json" in zf.namelist():
                data = zf.read("categories.json")
                (self._current_instance_path / "categories.json").write_bytes(data)

            # meta.ini files
            mods_dir = self._current_instance_path / ".mods"
            for name in zf.namelist():
                if name.startswith("mods/") and name.endswith("/meta.ini"):
                    parts = name.split("/")
                    if len(parts) >= 3:
                        mod_name = parts[1]
                        target_dir = mods_dir / mod_name
                        if target_dir.exists():
                            data = zf.read(name)
                            (target_dir / "meta.ini").write_bytes(data)

        # Reload and show toast
        self._reload_mod_list()
        Toast(self, f"Sicherung wiederhergestellt: {zip_path.name}")

    def _on_profile_created(self, name: str) -> None:
        """Handle new profile creation - create folder on disk."""
        if not self._current_instance_path:
            return

        profiles_dir = self._current_instance_path / ".profiles"
        new_profile_dir = profiles_dir / name
        new_profile_dir.mkdir(parents=True, exist_ok=True)

        # Copy modlist.txt from current profile if exists
        if self._current_profile_path:
            current_modlist = self._current_profile_path / "modlist.txt"
            if current_modlist.exists():
                shutil.copy(current_modlist, new_profile_dir / "modlist.txt")

        # Switch to new profile
        self._on_profile_changed(name)
        Toast(self, f"Profil '{name}' erstellt")

    def _on_profile_renamed(self, old_name: str, new_name: str) -> None:
        """Handle profile rename - rename folder on disk."""
        if not self._current_instance_path:
            return

        profiles_dir = self._current_instance_path / ".profiles"
        old_path = profiles_dir / old_name
        new_path = profiles_dir / new_name

        if old_path.exists() and not new_path.exists():
            old_path.rename(new_path)

        # Update current profile path if this was the active profile
        if self._current_profile_path and self._current_profile_path.name == old_name:
            self._current_profile_path = new_path

        Toast(self, f"Profil umbenannt: {old_name} → {new_name}")

    def _on_profile_changed(self, name: str) -> None:
        """Handle profile switch - load different modlist."""
        if not self._current_instance_path:
            return

        # Update profile path
        self._current_profile_path = self._current_instance_path / ".profiles" / name
        self._current_profile_path.mkdir(parents=True, exist_ok=True)

        # Save selected profile to instance data
        current_instance = self.instance_manager.current_instance()
        if current_instance:
            data = self.instance_manager.load_instance(current_instance)
            if data:
                data["selected_profile"] = name
                self.instance_manager.save_instance(current_instance, data)

        # Reload mod list with new profile
        self._reload_mod_list()

    def _on_profile_deleted(self, name: str) -> None:
        """Handle profile deletion request."""
        if not self._current_instance_path:
            return

        profiles_dir = self._current_instance_path / ".profiles"
        profile_path = profiles_dir / name

        # Profil-Ordner löschen
        if profile_path.exists():
            shutil.rmtree(profile_path)

        # Profile neu laden
        profile_folders = sorted([d.name for d in profiles_dir.iterdir() if d.is_dir()])
        if not profile_folders:
            (profiles_dir / "Default").mkdir(exist_ok=True)
            profile_folders = ["Default"]

        # Wenn gelöschtes Profil aktiv war → erstes verbleibendes wählen
        was_active = self._current_profile_path and self._current_profile_path.name == name
        new_active = profile_folders[0] if was_active else self._profile_bar._active_profile

        self._profile_bar.set_profiles(profile_folders, active=new_active)

        if was_active:
            self._on_profile_changed(new_active)

        Toast(self, f"Profil '{name}' gelöscht")

    def _collapse_all_separators(self) -> None:
        """Collapse all separators in the mod list."""
        tree = self._mod_list_view._tree
        source = self._mod_list_view.source_model()

        # Collect all separator folder names
        separator_folders: set[str] = set()
        for row in range(source.rowCount()):
            row_data = source._rows[row]
            if row_data.is_separator:
                separator_folders.add(row_data.folder_name)

        # Add all to collapsed set
        tree._collapsed_separators = separator_folders
        tree._apply_separator_filter()
        self.statusBar().showMessage(f"Alle Trenner eingeklappt ({len(separator_folders)})", 3000)

    def _expand_all_separators(self) -> None:
        """Expand all separators in the mod list."""
        tree = self._mod_list_view._tree
        tree._collapsed_separators.clear()
        tree._apply_separator_filter()
        self.statusBar().showMessage("Alle Trenner ausgeklappt", 3000)

    def _ctx_install_mod(self) -> None:
        """Install a mod from an archive file."""
        print("[DEBUG] _ctx_install_mod() CALLED")
        from anvil.core.mod_installer import ModInstaller, SUPPORTED_EXTENSIONS

        exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Mod-Archiv auswählen",
            str(Path.home()),
            f"Archive ({exts})",
        )
        if not path:
            return

        archive_path = Path(path)
        installer = ModInstaller(self._current_instance_path)
        result = installer.install_from_archive(archive_path)

        if result:
            add_mod_to_modlist(self._current_profile_path, result.name, True)
            self._reload_mod_list()
            self.statusBar().showMessage(f"Mod installiert: {result.name}", 5000)
        else:
            QMessageBox.warning(
                self,
                "Installation fehlgeschlagen",
                f"Die Mod konnte nicht installiert werden:\n{archive_path.name}",
            )

    def _ctx_create_empty_mod(self) -> None:
        """Create a new empty mod folder."""
        print("[DEBUG] _ctx_create_empty_mod() CALLED")
        from anvil.core.mod_metadata import create_default_meta_ini

        name, ok = QInputDialog.getText(
            self, "Leere Mod erstellen", "Name der Mod:",
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        mods_dir = self._current_instance_path / ".mods"
        mod_path = mods_dir / name

        if mod_path.exists():
            QMessageBox.warning(
                self, "Mod erstellen",
                f"Eine Mod mit dem Namen \"{name}\" existiert bereits.",
            )
            return

        try:
            mod_path.mkdir(parents=True, exist_ok=True)
            create_default_meta_ini(mod_path, name)
        except OSError as exc:
            QMessageBox.warning(
                self, "Mod erstellen", str(exc),
            )
            return

        add_mod_to_modlist(self._current_profile_path, name, True)
        self._reload_mod_list()
        self.statusBar().showMessage(f"Leere Mod erstellt: {name}", 5000)

    def _ctx_export_csv(self) -> None:
        """Export the mod list as CSV file."""
        import csv

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Modliste exportieren",
            str(Path.home() / "modlist.csv"),
            "CSV-Dateien (*.csv)",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["Name", "Kategorie", "Version", "Priorität", "Aktiv"])

                for entry in self._current_mod_entries:
                    if entry.is_separator:
                        continue  # Trenner nicht exportieren
                    cat_name = ""
                    if entry.category_ids:
                        cat_name = self._category_manager.get_name(entry.category_ids[0]) or ""
                    writer.writerow([
                        entry.display_name or entry.name,
                        cat_name,
                        entry.version,
                        entry.priority,
                        "Ja" if entry.enabled else "Nein",
                    ])

            self.statusBar().showMessage(f"Modliste exportiert: {path}", 5000)
        except OSError as exc:
            QMessageBox.warning(
                self, "Export fehlgeschlagen", str(exc),
            )

    def _ctx_enable_selected(self, rows: list[int], enabled: bool) -> None:
        """Enable or disable selected mods."""
        model = self._mod_list_view.source_model()
        for row in rows:
            if 0 <= row < len(self._current_mod_entries):
                self._current_mod_entries[row].enabled = enabled
                model._rows[row].enabled = enabled
        model.dataChanged.emit(
            model.index(0, 0),
            model.index(model.rowCount() - 1, 0),
            [Qt.ItemDataRole.CheckStateRole],
        )
        self._write_current_modlist()
        self._update_active_count()

    def _ctx_enable_all(self, enabled: bool) -> None:
        """Enable or disable ALL mods."""
        all_rows = list(range(len(self._current_mod_entries)))
        self._ctx_enable_selected(all_rows, enabled)
        label = "aktiviert" if enabled else "deaktiviert"
        self.statusBar().showMessage(f"Alle Mods {label}", 3000)

    def _apply_category_changes(
        self,
        row: int,
        cat_checkboxes: list[tuple[int, object]],
        primary_radios: list[tuple[int, object]],
    ) -> None:
        """Read checkbox/radio state from the closed menu and persist changes."""
        from anvil.core.mod_metadata import write_meta_ini

        entry = self._current_mod_entries[row]

        # Collect checked category IDs
        new_ids = [cid for cid, cb in cat_checkboxes if cb.isChecked()]

        # Determine primary: check radio buttons, fall back to first
        new_primary = 0
        for cid, rb in primary_radios:
            if rb.isChecked():
                new_primary = cid
                break
        # If primary not in new_ids, pick first (or 0)
        if new_primary not in new_ids:
            new_primary = new_ids[0] if new_ids else 0

        # Build category string (primary first, like MO2)
        old_ids = set(entry.category_ids)
        old_primary = entry.primary_category
        if set(new_ids) == old_ids and new_primary == old_primary:
            return  # nothing changed

        # Primary first, then rest
        ordered = []
        if new_primary:
            ordered.append(new_primary)
        for cid in new_ids:
            if cid != new_primary:
                ordered.append(cid)

        cat_str = ",".join(str(i) for i in ordered)

        # Update in-memory
        entry.category = cat_str
        entry.category_ids = ordered
        entry.primary_category = new_primary

        # Persist to meta.ini
        if entry.install_path:
            write_meta_ini(entry.install_path, {"category": cat_str})

        # Update model row
        model = self._mod_list_view.source_model()
        if row < len(model._rows):
            model._rows[row].category = cat_str
            idx = model.index(row, 4)  # COL_CATEGORY
            model.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])

        self.statusBar().showMessage(
            f"Kategorien aktualisiert: {entry.display_name or entry.name}", 3000,
        )

    def _toggle_category(self, row: int, cat_id: int) -> None:
        """Toggle a category assignment for a mod."""
        from anvil.core.mod_metadata import write_meta_ini

        entry = self._current_mod_entries[row]
        current_ids = list(entry.category_ids)

        if cat_id in current_ids:
            # Remove category
            current_ids.remove(cat_id)
            # If removed was primary, set new primary
            if cat_id == entry.primary_category:
                entry.primary_category = current_ids[0] if current_ids else 0
        else:
            # Add category
            current_ids.append(cat_id)
            # If first category, make it primary
            if len(current_ids) == 1:
                entry.primary_category = cat_id

        # Reorder: primary first
        ordered = []
        if entry.primary_category and entry.primary_category in current_ids:
            ordered.append(entry.primary_category)
        for cid in current_ids:
            if cid != entry.primary_category:
                ordered.append(cid)

        cat_str = ",".join(str(i) for i in ordered)

        # Update in-memory
        entry.category = cat_str
        entry.category_ids = ordered

        # Persist to meta.ini
        if entry.install_path:
            write_meta_ini(entry.install_path, {"category": cat_str})

        # Update model row
        model = self._mod_list_view.source_model()
        if row < len(model._rows):
            model._rows[row].category = cat_str
            idx = model.index(row, 4)  # COL_CATEGORY
            model.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])

        action = "hinzugefügt" if cat_id in ordered else "entfernt"
        name = self._category_manager.get_name(cat_id) or str(cat_id)
        self.statusBar().showMessage(f"Kategorie {action}: {name}", 3000)

    def _set_primary_category(self, row: int, cat_id: int) -> None:
        """Set a category as primary for a mod."""
        from anvil.core.mod_metadata import write_meta_ini

        entry = self._current_mod_entries[row]

        if cat_id not in entry.category_ids:
            return  # Can only set assigned categories as primary

        if cat_id == entry.primary_category:
            return  # Already primary

        # Reorder: new primary first
        ordered = [cat_id]
        for cid in entry.category_ids:
            if cid != cat_id:
                ordered.append(cid)

        cat_str = ",".join(str(i) for i in ordered)

        # Update in-memory
        entry.category = cat_str
        entry.category_ids = ordered
        entry.primary_category = cat_id

        # Persist to meta.ini
        if entry.install_path:
            write_meta_ini(entry.install_path, {"category": cat_str})

        # Update model row
        model = self._mod_list_view.source_model()
        if row < len(model._rows):
            model._rows[row].category = cat_str
            idx = model.index(row, 4)  # COL_CATEGORY
            model.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])

        name = self._category_manager.get_name(cat_id) or str(cat_id)
        self.statusBar().showMessage(f"Primäre Kategorie: {name}", 3000)

    def _ctx_create_backup(self, row: int) -> None:
        """Create a ZIP backup of the mod folder in .backups/."""
        import zipfile
        if row >= len(self._current_mod_entries):
            return
        entry = self._current_mod_entries[row]
        mod_path = self._current_instance_path / ".mods" / entry.name

        if not mod_path.is_dir():
            return

        backups_dir = self._current_instance_path / ".backups"
        backups_dir.mkdir(parents=True, exist_ok=True)

        zip_name = f"{entry.name}.zip"
        zip_path = backups_dir / zip_name

        # Avoid overwriting existing backup
        counter = 1
        while zip_path.exists():
            zip_name = f"{entry.name}_{counter}.zip"
            zip_path = backups_dir / zip_name
            counter += 1

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in mod_path.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(mod_path))
            self.statusBar().showMessage(
                f"Sicherung erstellt: {zip_name}", 5000,
            )
        except OSError as exc:
            QMessageBox.warning(
                self, "Sicherung fehlgeschlagen", str(exc),
            )

    def _ctx_visit_nexus(self, row: int) -> None:
        """Open the mod's Nexus Mods page in the browser."""
        if row >= len(self._current_mod_entries):
            return
        entry = self._current_mod_entries[row]
        if entry.nexus_id <= 0:
            return

        # Get Nexus game slug from plugin
        nexus_slug = ""
        if hasattr(self, '_game_panel') and hasattr(self._game_panel, '_current_plugin'):
            plugin = self._game_panel._current_plugin
            if plugin:
                nexus_slug = getattr(plugin, "GameNexusName", "") or getattr(plugin, "GameShortName", "")
        if not nexus_slug:
            nexus_slug = "site"  # fallback: generic Nexus URL

        url = f"https://www.nexusmods.com/{nexus_slug}/mods/{entry.nexus_id}"
        QDesktopServices.openUrl(QUrl(url))

    def _ctx_rename_mod(self, row: int) -> None:
        """Rename a mod (folder + modlist.txt)."""
        if row >= len(self._current_mod_entries):
            return
        entry = self._current_mod_entries[row]
        old_name = entry.name

        new_name, ok = QInputDialog.getText(
            self, "Mod umbenennen", "Neuer Name:", text=old_name,
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()

        old_path = self._current_instance_path / ".mods" / old_name
        new_path = self._current_instance_path / ".mods" / new_name

        if new_path.exists():
            QMessageBox.warning(
                self, "Umbenennen fehlgeschlagen",
                f"Ein Mod mit dem Namen \"{new_name}\" existiert bereits.",
            )
            return

        try:
            old_path.rename(new_path)
        except OSError as exc:
            QMessageBox.warning(
                self, "Umbenennen fehlgeschlagen", str(exc),
            )
            return

        rename_mod_in_modlist(self._current_profile_path, old_name, new_name)
        self._reload_mod_list()
        self.statusBar().showMessage(f"Umbenannt: {old_name} → {new_name}", 5000)

    def _ctx_reinstall_mod(self, row: int) -> None:
        """Reinstall a mod from its archive in .downloads/."""
        if row >= len(self._current_mod_entries):
            return
        entry = self._current_mod_entries[row]
        downloads_path = self._current_instance_path / ".downloads"

        if not downloads_path.is_dir():
            QMessageBox.warning(
                self, "Neu installieren",
                "Kein Downloads-Ordner gefunden.",
            )
            return

        # Find matching archive by mod name
        archive = None
        mod_lower = entry.name.lower()
        for f in downloads_path.iterdir():
            if f.is_file() and f.suffix.lower() in ('.zip', '.rar', '.7z'):
                if mod_lower in f.stem.lower():
                    archive = f
                    break

        if not archive:
            QMessageBox.information(
                self, "Neu installieren",
                f"Kein passendes Archiv für \"{entry.name}\" in .downloads/ gefunden.",
            )
            return

        self._install_archives([archive])

    def _ctx_remove_mods(self, rows: list[int]) -> None:
        """Remove selected mods (folder + modlist.txt entry)."""
        names = []
        for row in rows:
            if row < len(self._current_mod_entries):
                names.append(self._current_mod_entries[row].name)
        if not names:
            return

        if len(names) == 1:
            msg = f"Mod \"{names[0]}\" wirklich löschen?\n\nDer Mod-Ordner wird unwiderruflich gelöscht."
        else:
            msg = f"{len(names)} Mods wirklich löschen?\n\n" + "\n".join(f"  • {n}" for n in names) + "\n\nDie Mod-Ordner werden unwiderruflich gelöscht."

        reply = QMessageBox.question(
            self, "Mod entfernen", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for name in names:
            mod_path = self._current_instance_path / ".mods" / name
            if mod_path.is_dir():
                shutil.rmtree(mod_path)
            remove_mod_from_modlist(self._current_profile_path, name)

        self._reload_mod_list()
        self.statusBar().showMessage(f"Entfernt: {', '.join(names)}", 5000)

    def _ctx_open_explorer(self, row: int) -> None:
        """Open the mod folder in the file manager."""
        import subprocess
        if row >= len(self._current_mod_entries):
            return
        mod_path = self._current_instance_path / ".mods" / self._current_mod_entries[row].name
        if mod_path.is_dir():
            subprocess.Popen(["xdg-open", str(mod_path)])

    def _ctx_show_info(self, row: int) -> None:
        """Show mod information dialog."""
        if row >= len(self._current_mod_entries):
            return
        entry = self._current_mod_entries[row]
        mod_path = self._current_instance_path / ".mods" / entry.name

        # Collect info
        info_lines = [
            f"Name: {entry.display_name or entry.name}",
            f"Ordner: {entry.name}",
            f"Pfad: {mod_path}",
            f"Aktiviert: {'Ja' if entry.enabled else 'Nein'}",
            f"Version: {entry.version or '—'}",
            f"Kategorie: {entry.category or '—'}",
            f"Priorität: {entry.priority}",
        ]

        # Folder size
        if mod_path.is_dir():
            total = sum(f.stat().st_size for f in mod_path.rglob("*") if f.is_file())
            if total < 1024 * 1024:
                size_str = f"{total / 1024:.1f} KB"
            else:
                size_str = f"{total / (1024 * 1024):.1f} MB"
            info_lines.append(f"Größe: {size_str}")

        # meta.ini content
        meta_ini = mod_path / "meta.ini"
        if meta_ini.is_file():
            try:
                meta_text = meta_ini.read_text(encoding="utf-8")
                info_lines.append(f"\n── meta.ini ──\n{meta_text}")
            except OSError:
                pass

        dlg = QDialog(self)
        dlg.setObjectName("InfoDialog")
        dlg.setWindowTitle(f"Informationen: {entry.display_name or entry.name}")
        layout = QVBoxLayout(dlg)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText("\n".join(info_lines))
        layout.addWidget(text_edit)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)
        # Größe NACH Layout setzen — Wayland braucht das vor exec()
        dlg.setMinimumSize(750, 600)
        dlg.resize(750, 600)
        dlg.exec()

    def _reload_mod_list(self) -> None:
        """Reload mod list from disk and update UI.

        Dispatches to BG3-specific reload when a BG3 instance is active.
        """
        if self._bg3_installer is not None:
            self._bg3_reload_mod_list()
            return
        self._current_mod_entries = scan_mods_directory(
            self._current_instance_path, self._current_profile_path,
        )
        # Re-mark direct-install mods
        plugin = self._current_plugin
        direct_patterns = getattr(plugin, "GameDirectInstallMods", []) if plugin else []
        if direct_patterns:
            lp = [p.lower() for p in direct_patterns]
            for entry in self._current_mod_entries:
                name_lower = (entry.display_name or entry.name).lower()
                if _matches_direct_install(name_lower, lp):
                    entry.is_direct_install = True
        conflict_data = self._compute_conflict_data()
        visible_entries = [e for e in self._current_mod_entries if not e.is_direct_install]
        mod_rows = [mod_entry_to_row(e, conflict_data) for e in visible_entries]
        self._mod_list_view.source_model().set_mods(mod_rows)
        self._mod_list_view._proxy_model.set_mod_entries(visible_entries)
        self._update_active_count()

    # ── Nexus API integration ─────────────────────────────────────────

    def _handle_nxm_link(self, nxm_link) -> None:
        """Process an nxm:// link: request download URLs from Nexus API."""
        if not self._nexus_api.has_api_key():
            QMessageBox.warning(
                self, "Nexus API",
                "Kein Nexus API-Schlüssel konfiguriert.\n"
                "Bitte unter Werkzeuge → Einstellungen → Nexus einen API-Schlüssel eingeben.",
            )
            return

        self.statusBar().showMessage(
            f"Nexus: Lade Download-Links für Mod {nxm_link.mod_id}...", 5000,
        )

        # First get mod info (for name/version), then download links
        self._nexus_api.get_mod_info(nxm_link.game, nxm_link.mod_id)
        self._nexus_api.get_download_links(
            nxm_link.game,
            nxm_link.mod_id,
            nxm_link.file_id,
            key=nxm_link.key or None,
            expires=nxm_link.expires or None,
        )

        # Store nxm link for when download links arrive
        self._pending_nxm = nxm_link

    def _on_nexus_response(self, tag: str, data: object) -> None:
        """Handle Nexus API responses."""
        if tag.startswith("download_link:") and isinstance(data, list) and data:
            # Download link response — start download
            nxm = getattr(self, "_pending_nxm", None)
            if not nxm:
                return

            # Use first available download URL
            url = data[0].get("URI", "")
            if not url:
                self.statusBar().showMessage("Nexus: Kein Download-Link erhalten.", 5000)
                return

            # Determine filename from URL
            from urllib.parse import urlparse
            parsed = urlparse(url)
            file_name = Path(parsed.path).name or f"mod_{nxm.mod_id}_{nxm.file_id}.zip"

            # Get mod info from cache if available
            mod_name = getattr(self, "_pending_nxm_mod_name", "")
            mod_version = getattr(self, "_pending_nxm_mod_version", "")

            dm = self._game_panel.download_manager()
            dl_id = dm.enqueue(
                url=url,
                file_name=file_name,
                game=nxm.game,
                mod_id=nxm.mod_id,
                file_id=nxm.file_id,
                mod_name=mod_name,
                mod_version=mod_version,
            )
            self.statusBar().showMessage(
                f"Nexus: Download gestartet — {file_name}", 5000,
            )

            # Switch to Downloads tab
            self._game_panel._tabs.setCurrentIndex(2)
            self._pending_nxm = None
            self._pending_nxm_mod_name = ""
            self._pending_nxm_mod_version = ""

        elif tag.startswith("mod_info:") and isinstance(data, dict):
            # Store mod name/version for when download starts
            self._pending_nxm_mod_name = data.get("name", "")
            self._pending_nxm_mod_version = data.get("version", "")

    def _on_nexus_error(self, tag: str, message: str) -> None:
        """Handle Nexus API errors."""
        self.statusBar().showMessage(f"Nexus Fehler: {message}", 5000)

    def _update_api_status(self, daily: int, hourly: int) -> None:
        """Update status bar API rate limit display (MO2 style)."""
        self._status_bar.update_api_status(
            daily_remaining=daily,
            hourly_remaining=hourly,
            queued=0,
            logged_in=self._nexus_api.has_api_key(),
        )

    def handle_nxm_url(self, url: str) -> None:
        """Public method to handle an nxm:// URL string.

        Can be called from external IPC when a second instance
        receives an nxm:// link.
        """
        nxm_link = parse_nxm_url(url)
        if nxm_link:
            self._handle_nxm_link(nxm_link)

    # ── UI state persistence ───────────────────────────────────────

    @staticmethod
    def _settings() -> QSettings:
        """Return QSettings with a fixed path independent of Flatpak sandbox."""
        path = str(Path.home() / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf")
        return QSettings(path, QSettings.Format.IniFormat)

    def _save_ui_state(self) -> None:
        """Persist splitter proportions and view settings.

        Column widths are saved live by PersistentHeader (debounced).
        Flush any pending writes so nothing is lost on shutdown.
        """
        # Flush debounced column-width writes
        self._mod_list_view.flush_column_widths()
        self._game_panel.flush_column_widths()
        if self._bg3_mod_list is not None:
            self._bg3_mod_list.flush_column_widths()

        s = self._settings()
        s.setValue("splitter/state", self._splitter.saveState())
        # View settings
        s.setValue("view/menubar_visible", self.menuBar().isVisible())
        s.setValue("view/toolbar_visible", self._toolbar.isVisible())
        s.setValue("view/statusbar_visible", self._status_bar.isVisible())
        # Log state is persisted by CollapsibleSectionBar (log/collapsed)
        s.setValue("view/filter_panel_open", self._filter_panel.is_open())
        s.setValue("view/filter_splitter_state", self._filter_splitter.saveState())
        # Icon size → index (0=small, 1=medium, 2=large)
        cur_size = self._toolbar.iconSize()
        size_idx = 1  # default medium
        for i, sz in enumerate(self._ICON_SIZES):
            if cur_size == sz:
                size_idx = i
                break
        s.setValue("view/toolbar_icon_size", size_idx)
        s.setValue("view/toolbar_button_style", self._toolbar.toolButtonStyle().value)
        s.sync()

    def _restore_ui_state(self) -> None:
        """Restore splitter and column widths.

        Column widths are restored via PersistentHeader.restore().
        Tab column restores are deferred until the tab becomes visible
        for the first time (hidden widgets may not layout correctly).
        """
        s = self._settings()
        val = s.value("splitter/state")
        if val:
            self._splitter.restoreState(val)

        # Standard mod list — always visible
        self._mod_list_view.restore_column_widths()
        self._mod_list_view.restore_framework_widths()

        # BG3 mod list — visible when BG3 instance is active
        if self._bg3_mod_list is not None:
            self._bg3_mod_list.restore_column_widths()

        # Game-panel tabs — only restore the currently visible tab;
        # hidden tabs are restored on first switch via _on_tab_changed()
        self._restored_tabs.clear()
        active = self._game_panel._tabs.currentIndex()
        self._game_panel.restore_tab_column_widths(active)
        self._restored_tabs.add(active)

    def _on_tab_changed(self, index: int) -> None:
        """Restore column widths when a tab becomes visible for the first time."""
        if index not in self._restored_tabs:
            self._game_panel.restore_tab_column_widths(index)
            self._restored_tabs.add(index)

    def closeEvent(self, event) -> None:
        # Purge deployed mods before closing
        self._game_panel.silent_purge()
        self._save_ui_state()
        super().closeEvent(event)

    # ── BG3-specific methods ─────────────────────────────────────────

    def _ensure_bg3_mod_list(self) -> None:
        """Lazily create the BG3ModListView and add it to the stack."""
        if self._bg3_mod_list is not None:
            return
        from anvil.widgets.bg3_mod_list import BG3ModListView
        self._bg3_mod_list = BG3ModListView()
        self._mod_list_stack.addWidget(self._bg3_mod_list)

        # Connect signals
        self._bg3_mod_list.mod_activated.connect(self._on_bg3_mod_activated)
        self._bg3_mod_list.mod_deactivated.connect(self._on_bg3_mod_deactivated)
        self._bg3_mod_list.mods_reordered.connect(self._on_bg3_mods_reordered)
        self._bg3_mod_list.archives_dropped.connect(self._on_bg3_archives_dropped)
        self._bg3_mod_list.context_menu_requested.connect(self._on_bg3_context_menu)

    def _apply_bg3_instance(
        self, instance_name: str, data: dict, plugin, game_path,
    ) -> None:
        """Load a BG3 instance with the BG3ModInstaller flow."""
        self._ensure_bg3_mod_list()
        self._mod_list_stack.setCurrentWidget(self._bg3_mod_list)
        self._toolbar.deploy_sep.setVisible(True)
        self._toolbar.deploy_action.setVisible(True)
        self._toolbar.deploy_btn.setStyleSheet("")

        # Instance path
        instance_path = self._current_instance_path

        # Get the installer from the game plugin
        if plugin is None or not hasattr(plugin, "get_mod_installer"):
            self.statusBar().showMessage(
                "BG3: Game-Plugin nicht gefunden!", 5000,
            )
            return

        # Ensure plugin knows its store + path (may not be auto-detected
        # if the game drive is not mounted during startup)
        if not plugin.isInstalled():
            store = data.get("detected_store", "")
            if game_path and store:
                plugin.setGamePath(game_path, store=store)
            elif store:
                plugin.setGamePath(Path("/"), store=store)

        self._bg3_installer = plugin.get_mod_installer()
        self._bg3_installer._instance_path = instance_path

        # Check if Proton prefix exists
        if self._bg3_installer._mods_path is None:
            self.statusBar().showMessage(
                "BG3: Proton-Prefix nicht gefunden — Mods-Ordner fehlt", 8000,
            )

        # Load mod list
        self._bg3_reload_mod_list()

        # Profile path (for compatibility with shared code)
        profile_name = data.get("selected_profile", "Default")
        self._current_profile_path = instance_path / ".profiles" / profile_name

        # No auto-deploy for BG3 (user deploys manually)
        self._game_panel.set_instance_path(instance_path)

    def _bg3_mark_dirty(self) -> None:
        """Show and highlight the Deploy button (unsaved changes)."""
        self._toolbar.deploy_sep.setVisible(True)
        self._toolbar.deploy_action.setVisible(True)
        self._toolbar.deploy_btn.setStyleSheet(
            "QToolButton { color: #4DE0D0; font-weight: bold; }"
        )

    def _bg3_mark_clean(self) -> None:
        """Remove highlight from Deploy button (no unsaved changes)."""
        self._toolbar.deploy_btn.setStyleSheet("")

    def _bg3_reload_mod_list(self) -> None:
        """Reload the BG3 mod list from the installer."""
        if self._bg3_installer is None or self._bg3_mod_list is None:
            return
        mod_list = self._bg3_installer.get_mod_list()
        self._bg3_mod_list.load_mods(
            mod_list["active"],
            mod_list["inactive"],
            data_overrides=mod_list.get("data_overrides", []),
            frameworks=mod_list.get("frameworks", []),
        )
        self._profile_bar.update_active_count(len(mod_list["active"]))

    def _on_bg3_mod_activated(self, uuid: str) -> None:
        """Activate a BG3 mod (add to ModOrder)."""
        if self._bg3_installer is None:
            return
        ok = self._bg3_installer.activate_mod(uuid)
        if ok:
            self._bg3_reload_mod_list()
            self._bg3_mark_dirty()
            self.statusBar().showMessage("Mod aktiviert", 3000)
        else:
            self.statusBar().showMessage("Mod konnte nicht aktiviert werden", 5000)

    def _on_bg3_mod_deactivated(self, uuid: str) -> None:
        """Deactivate a BG3 mod (remove from ModOrder)."""
        if self._bg3_installer is None:
            return
        ok = self._bg3_installer.deactivate_mod(uuid)
        if ok:
            self._bg3_reload_mod_list()
            self._bg3_mark_dirty()
            self.statusBar().showMessage("Mod deaktiviert", 3000)
        else:
            self.statusBar().showMessage("Mod konnte nicht deaktiviert werden", 5000)

    def _on_bg3_mods_reordered(self, uuid_order: list[str]) -> None:
        """Reorder BG3 active mods."""
        if self._bg3_installer is None:
            return
        ok = self._bg3_installer.reorder_mods(uuid_order)
        if ok:
            self._bg3_mark_dirty()
            self.statusBar().showMessage("Load-Order aktualisiert", 3000)
        else:
            self.statusBar().showMessage("Load-Order konnte nicht geändert werden", 5000)
            self._bg3_reload_mod_list()

    def _on_bg3_archives_dropped(self, paths: list) -> None:
        """Install BG3 mods from dropped archives/paks."""
        if self._bg3_installer is None:
            return
        installed = []
        for path_str in paths:
            result = self._bg3_installer.install_mod(Path(path_str))
            if result:
                mod_type = result.get("type", "pak")
                name = result.get("name", Path(path_str).name)
                installed.append((name, mod_type))
            else:
                self.statusBar().showMessage(
                    f"Installation fehlgeschlagen: {Path(path_str).name}", 5000,
                )
        if installed:
            self._bg3_reload_mod_list()
            # Only mark dirty for pak mods (framework/data don't need deploy)
            if any(t == "pak" for _, t in installed):
                self._bg3_mark_dirty()
            names = ", ".join(n for n, _ in installed)
            types = set(t for _, t in installed)
            if types == {"pak"}:
                self.statusBar().showMessage(f"Installiert (inaktiv): {names}", 5000)
            else:
                self.statusBar().showMessage(f"Installiert: {names}", 5000)

    def _on_bg3_deploy(self) -> None:
        """Deploy: validate and backup modsettings.lsx."""
        if self._bg3_installer is None:
            self.statusBar().showMessage("Kein BG3-Installer aktiv", 5000)
            return
        ok = self._bg3_installer.deploy()
        if ok:
            self._bg3_mark_clean()
            self.statusBar().showMessage("Mod-Liste exportiert \u2713", 5000)
        else:
            self.statusBar().showMessage("Deploy fehlgeschlagen — siehe Konsole", 5000)

    def _on_bg3_context_menu(self, global_pos, section: str, mod_data: dict) -> None:
        """BG3-specific context menu."""
        if self._bg3_installer is None:
            return

        # Extras section has its own menu
        if section == "extras":
            self._on_bg3_extras_context_menu(global_pos, mod_data)
            return

        has_mod = bool(mod_data.get("uuid"))
        menu = QMenu(self)

        if has_mod:
            if section == "inactive":
                act_activate = menu.addAction("Aktivieren")
            else:
                act_activate = None
                act_deactivate = menu.addAction("Deaktivieren")

            menu.addSeparator()
            act_uninstall = menu.addAction("Deinstallieren...")
        else:
            act_activate = None
            act_deactivate = None
            act_uninstall = None

        menu.addSeparator()
        act_explorer = menu.addAction("Im Dateimanager öffnen")
        act_explorer.setEnabled(has_mod)
        menu.addSeparator()
        act_reload = menu.addAction("Neu laden")

        chosen = menu.exec(global_pos)
        if not chosen:
            return

        uuid = mod_data.get("uuid", "")
        filename = mod_data.get("filename", "")

        if chosen == act_reload:
            self._bg3_reload_mod_list()
            self.statusBar().showMessage("Mod-Liste neu geladen", 3000)
        elif act_activate is not None and chosen == act_activate:
            self._on_bg3_mod_activated(uuid)
        elif act_deactivate is not None and chosen == act_deactivate:
            self._on_bg3_mod_deactivated(uuid)
        elif chosen == act_uninstall and uuid:
            name = mod_data.get("name", uuid)
            reply = QMessageBox.question(
                self, "Mod deinstallieren",
                f"Mod \"{name}\" wirklich deinstallieren?\n\n"
                "Die .pak-Datei wird gelöscht und der Eintrag aus\n"
                "modsettings.lsx entfernt.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                ok = self._bg3_installer.uninstall_mod(uuid, filename)
                if ok:
                    self._bg3_reload_mod_list()
                    self._bg3_mark_dirty()
                    self.statusBar().showMessage(f"Deinstalliert: {name}", 5000)
                else:
                    self.statusBar().showMessage("Deinstallation fehlgeschlagen", 5000)
        elif chosen == act_explorer:
            import subprocess
            mods_path = self._bg3_installer._mods_path
            if mods_path and mods_path.is_dir():
                subprocess.Popen(["xdg-open", str(mods_path)])

    def _on_bg3_extras_context_menu(self, global_pos, mod_data: dict) -> None:
        """Context menu for data-overrides and frameworks."""
        menu = QMenu(self)
        mod_type = mod_data.get("type", "")
        name = mod_data.get("name", "")

        act_uninstall = None
        if mod_type == "data_override" and name:
            act_uninstall = menu.addAction("Deinstallieren...")

        menu.addSeparator()
        act_reload = menu.addAction("Neu laden")

        chosen = menu.exec(global_pos)
        if not chosen:
            return

        if chosen == act_reload:
            self._bg3_reload_mod_list()
            self.statusBar().showMessage("Mod-Liste neu geladen", 3000)
        elif chosen == act_uninstall and name:
            reply = QMessageBox.question(
                self, "Data-Override deinstallieren",
                f"Data-Override \"{name}\" wirklich deinstallieren?\n\n"
                f"Alle zugehörigen Dateien werden aus Data/ gelöscht.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                ok = self._bg3_installer.uninstall_data_override(name)
                if ok:
                    self._bg3_reload_mod_list()
                    self.statusBar().showMessage(f"Data-Override deinstalliert: {name}", 5000)
                else:
                    self.statusBar().showMessage("Deinstallation fehlgeschlagen", 5000)

    # ── Other slots ───────────────────────────────────────────────────

    def _on_about(self):
        QMessageBox.about(self, "Über Anvil Organizer", "Anvil Organizer v0.1.0\n\nPlatzhalter-GUI.")
