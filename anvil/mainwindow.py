"""Hauptfenster: Menü, Toolbar, Profil-Leiste, Splitter 65:35, Statusbar."""

from __future__ import annotations

from pathlib import Path

import configparser
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QToolButton,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QStackedWidget,
    QMessageBox,
    QSizePolicy,
    QFileDialog,
    QDialog,
    QMenu,
    QTextEdit,
    QDialogButtonBox,
    QLineEdit,
    QLabel,
    QPushButton,
    QFrame,
    QInputDialog,
)
from PySide6.QtCore import Qt, QModelIndex, QSettings, QThread, QTimer, QSize
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence

from anvil.core.subprocess_env import clean_subprocess_env, host_popen, host_open_url, host_open_path
from anvil.core.ui_helpers import _center_on_parent, get_text_input
from anvil.styles.dark_theme import apply_theme, load_overrides, default_theme, style_prefs
from anvil.widgets.toolbar import create_toolbar
from anvil.widgets.profile_bar import ProfileBar
from anvil.widgets.mod_list import ModListView
from anvil.widgets.collapsible_bar import CollapsibleSectionBar
from anvil.widgets.filter_panel import FilterPanel
from anvil.widgets.game_panel import GamePanel, GAME_RUNNING
from anvil.widgets.status_bar import StatusBarWidget
from anvil.widgets.toast import Toast
from anvil.dialogs import ModDetailDialog
from anvil.dialogs.quick_install_dialog import QuickInstallDialog
from anvil.dialogs.query_overwrite_dialog import QueryOverwriteDialog, OverwriteAction
from anvil.plugins.plugin_loader import PluginLoader
from anvil.core.base_dir import anvil_base_paths
from anvil.core.instance_manager import InstanceManager
from anvil.core.instance_paths import (
    InstancePaths,
    StorageComponentStatus,
    resolve_instance_paths,
    unavailable_configured_storage,
)
from anvil.core.profile_name import is_valid_profile_name, safe_profile_directory
from anvil.core.icon_manager import IconManager
from anvil.core.mod_entry import ModEntry, scan_mods_directory
from anvil.core.mod_installer import ModInstaller, SUPPORTED_EXTENSIONS
from anvil.core.fomod_parser import (
    detect_fomod, detect_fomod_script, parse_fomod, parse_fomod_info,
    collect_fomod_files, assemble_fomod_files,
    save_fomod_choices, load_fomod_choices,
)
from anvil.dialogs.fomod_dialog import FomodDialog
from anvil.core.mod_list_io import (
    add_mod_to_modlist, write_modlist, remove_mod_from_modlist,
    remove_mod_from_global_modlist,
    rename_mod_in_modlist, read_active_mods, write_active_mods,
    read_global_modlist, write_global_modlist, migrate_to_global_modlist,
    migrate_modlist_order, insert_mod_in_modlist, rename_mod_globally, remove_mod_globally,
)
from anvil.core.categories import CategoryManager, _DEFAULT_CATEGORIES
from anvil.version import APP_VERSION
from anvil.core.update_checker import UpdateChecker
from anvil.core.notification_center import NotificationCenter
from anvil.core.nexus_api import NexusAPI
from anvil.core.nxm_handler import parse_nxm_url, is_collection_nxm, get_nxm_arg
from anvil.core.desktop_shortcut import get_launch_instance_arg
from anvil.core.conflict_scanner import ConflictScanner
from anvil.core.modindex import ModIndex
from anvil.core.lspk_parser import LSPKReader
from anvil.models.mod_list_model import mod_entry_to_row, COL_COUNT, ROLE_GROUP_NAME, ROLE_IS_GROUP_HEAD
from anvil.core.mod_groups import GroupManager
from anvil.widgets.instance_wizard import CreateInstanceWizard
from anvil.widgets.instance_dropdown import InstanceDropdown, TitleBarSpan
from anvil.widgets.switch_overlay import SwitchOverlay
from anvil.widgets.notification_panel import NotificationButton, NotificationPanel
from anvil.widgets.log_panel import LogPanel
from anvil.core import _todo
from anvil.core import framework_state
from anvil.core.translator import tr


""" Anzeige und Deployer muessen dieselbe Frage gleich beantworten --
sonst zeigt die Liste eine gewoehnliche Mod und der Deployer rollt sie
trotzdem aus. Genau das war jahrelang der Fall. """
from anvil.core.mod_deployer import matches_direct_install as _matches_direct_install


def _path_matches(base: Path, rel: str) -> bool:
    """True wenn *rel* unter *base* existiert — mit Wildcard-Support."""
    if any(c in rel for c in "*?["):
        return any(base.glob(rel))
    return (base / rel).exists()


def _ensure_list(val) -> list:
    """QSettings gibt bei 1 Element einen String statt Liste zurück."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        return [val]
    return list(val)


def _server_id(entry: dict) -> str:
    """Stabiler Bezeichner für einen Nexus-CDN-Server-Eintrag.

    Bevorzugt short_name/name. Fällt auf den URL-Host zurück (die URI trägt
    pro Download key/expires-Query, daher nur der Hostname für Stabilität).
    """
    if not isinstance(entry, dict):
        return ""
    sid = entry.get("short_name") or entry.get("name")
    if sid:
        return str(sid)
    uri = entry.get("URI", "")
    if uri:
        from urllib.parse import urlparse
        host = urlparse(str(uri)).hostname
        if host:
            return host
    return ""


class _CenteredClearLineEdit(QLineEdit):
    """QLineEdit that vertically centers the built-in clear button."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        from PySide6.QtWidgets import QToolButton
        for btn in self.findChildren(QToolButton):
            g = btn.geometry()
            centered_y = (self.height() - g.height()) // 2
            if g.y() != centered_y:
                btn.setGeometry(g.x(), centered_y, g.width(), g.height())


def _first_unavailable_storage(
    paths: InstancePaths,
    instance_data: dict,
) -> StorageComponentStatus | None:
    unavailable = unavailable_configured_storage(paths, instance_data)
    return unavailable[0] if unavailable else None


def _active_instance_paths(window) -> InstancePaths:
    """Return active roots, with legacy defaults for lightweight test doubles."""
    paths = getattr(window, "_current_instance_paths", None)
    if paths is not None:
        return paths
    instance_path = getattr(window, "_current_instance_path", None)
    if instance_path is None:
        raise RuntimeError("no active instance paths")
    return resolve_instance_paths(instance_path, {})


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Anvil Organizer v{APP_VERSION}")
        from anvil.core.resource_path import get_anvil_base
        logo_path = get_anvil_base() / "resources" / "logo.svg"
        self.setWindowIcon(QIcon(str(logo_path)))
        self.setMinimumSize(1000, 650)
        self.resize(1200, 750)
        # Theme aus QSettings laden — auf QApplication-Ebene, NICHT aufs Fenster:
        # ein Fenster-Stylesheet würde die Live-Vorschau (App-Ebene) überdecken.
        saved_theme = self._settings().value("style/theme", default_theme())
        overrides = load_overrides(self._settings(), saved_theme)
        accent, density = style_prefs(self._settings())
        apply_theme(QApplication.instance(), saved_theme, overrides,
                    accent=accent, density=density)

        # ── Plugin-System ─────────────────────────────────────────────
        self.plugin_loader = PluginLoader()
        self.plugin_loader.load_plugins()

        # ── Instanz-System ────────────────────────────────────────────
        self.instance_manager = InstanceManager()
        self.icon_manager = IconManager()

        self._toolbar = create_toolbar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._toolbar)
        self._toolbar.installEventFilter(self)
        self.installEventFilter(self)  # Alt-key recovery for menubar
        self._build_menu_bar()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Profil-Leiste NUR ueber der linken Seite, nicht ueber die ganze Breite
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
        self._profile_bar.export_import_requested.connect(self._open_export_import)
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
        self._profile_bar.install_mod_requested.connect(self._on_install_mod)
        self._profile_bar.create_separator_requested.connect(self._ctx_create_separator)
        self._profile_bar.enable_all_requested.connect(lambda: self._ctx_enable_all(True))
        self._profile_bar.disable_all_requested.connect(lambda: self._ctx_enable_all(False))
        # export_import_requested ist oben verbunden
        self._profile_bar.profile_create_confirmed.connect(self._on_profile_created)
        self._profile_bar.profile_create_rejected.connect(
            self._on_profile_create_rejected
        )
        self._profile_bar.profile_renamed.connect(self._on_profile_renamed)
        self._profile_bar.profile_changed.connect(self._on_profile_changed)
        self._profile_bar.profile_delete_requested.connect(self._on_profile_deleted)
        self._profile_bar.profiles_reordered.connect(self._on_profiles_reordered)
        left_layout.addWidget(self._profile_bar)

        # ── Mod-Suche ──
        self._mod_search = _CenteredClearLineEdit()
        self._mod_search.setPlaceholderText(tr("filter.search_placeholder"))
        self._mod_search.setClearButtonEnabled(True)
        self._mod_search.textChanged.connect(self._on_filter_changed)

        self._mod_list_view = ModListView()
        self._mod_list_view._tree.doubleClicked.connect(self._on_mod_double_click)
        self._mod_list_view.context_menu_requested.connect(self._on_mod_context_menu)

        # Stacked widget: standard mod list (index 0) / BG3 mod list (index 1)
        self._mod_list_stack = QStackedWidget()
        self._mod_list_stack.addWidget(self._mod_list_view)

        # Wrapper: Suche + ModList (nur über Mod-Liste, nicht über FilterPanel)
        mod_list_wrapper = QWidget()
        mod_list_layout = QVBoxLayout(mod_list_wrapper)
        mod_list_layout.setContentsMargins(0, 0, 0, 0)
        mod_list_layout.setSpacing(4)
        mod_list_layout.addWidget(self._mod_search)
        mod_list_layout.addWidget(self._mod_list_stack)

        # ── FilterPanel + ModList ────────────────────────────────────
        self._filter_panel = FilterPanel()
        self._filter_panel.filter_changed.connect(self._on_filter_changed)
        self._filter_panel.panel_toggled.connect(self._on_filter_panel_toggled)
        self._filter_panel.nexus_load_requested.connect(self._on_nexus_load_requested)

        self._filter_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._filter_splitter.addWidget(self._filter_panel)
        self._filter_splitter.addWidget(mod_list_wrapper)
        self._filter_splitter.setStretchFactor(0, 0)
        self._filter_splitter.setStretchFactor(1, 1)
        self._filter_splitter.setSizes([220, 560])
        self._filter_splitter.setChildrenCollapsible(False)
        self._filter_panel.set_splitter(self._filter_splitter)

        left_layout.addWidget(self._filter_splitter)

        # BG3 mod list (lazy-created when needed)
        self._bg3_mod_list: None = None  # BG3ModListView, created on demand
        self._bg3_installer = None       # BG3ModInstaller, cached
        self._mod_index: ModIndex | None = None  # Central file index cache
        splitter.addWidget(left_pane)
        self._game_panel = GamePanel()
        splitter.addWidget(self._game_panel)
        splitter.setSizes([780, 420])
        main_layout.addWidget(splitter)

        # ── Lock-Overlay (Game Running Lock) ─────────────────────────
        # Overlay-Widget as child of central — NOT in the layout.
        # Floats centered over the UI without shifting anything.
        self._lock_overlay = QFrame(central)
        self._lock_overlay.setObjectName("game_lock_overlay")
        self._lock_overlay.setFixedSize(420, 120)
        overlay_layout = QVBoxLayout(self._lock_overlay)
        overlay_layout.setContentsMargins(20, 16, 20, 16)
        overlay_layout.setSpacing(12)
        self._lock_label = QLabel()
        self._lock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lock_label.setWordWrap(True)
        overlay_layout.addWidget(self._lock_label)
        self._unlock_btn = QPushButton(tr("status.game_lock.unlock_button"))
        self._unlock_btn.setFixedWidth(160)
        self._unlock_btn.clicked.connect(lambda checked=False: self._on_unlock_clicked())
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self._unlock_btn)
        btn_layout.addStretch()
        overlay_layout.addLayout(btn_layout)
        self._lock_overlay.setVisible(False)
        self._lock_overlay.raise_()

        # ── Log-Panel (collapsible section with card-style panel) ───────
        self._log_container = QWidget()
        self._log_container.setMinimumHeight(28)
        self._log_container.setMaximumHeight(232)  # 28 bar + 204 LogPanel
        log_layout = QVBoxLayout(self._log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(0)

        self._log_panel = LogPanel()
        self._log_panel.setMaximumHeight(204)

        # Klassik-Style mitgeben — die Bar wählt selbst je nach aktivem Theme
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
        self._filter_panel.set_category_manager(self._category_manager)
        from anvil.core.properties import PropertyManager
        self._property_manager = PropertyManager()
        self._filter_panel.set_property_manager(self._property_manager)

        # ── Group manager ──────────────────────────────────────────────
        self._group_manager = GroupManager()
        self._mod_list_view.set_group_manager(self._group_manager)

        # ── Nexus API ────────────────────────────────────────────────
        self._nexus_api = NexusAPI(self)
        from anvil.widgets.settings_dialog import SettingsDialog
        saved_key = SettingsDialog.load_api_key()
        if saved_key:
            self._nexus_api.set_api_key(saved_key)
            self._status_bar.update_api_status(logged_in=True)
        hidden = self._settings().value("Nexus/hide_api_counter", False, type=bool)
        self._status_bar.set_api_counter_visible(not hidden)
        self._nexus_api.request_finished.connect(self._on_nexus_response)
        self._nexus_api.request_error.connect(self._on_nexus_error)
        self._nexus_api.rate_limit_updated.connect(self._update_api_status)
        self._game_panel.set_nexus_api_available(self._nexus_api.has_api_key())

        # ── Mod state ─────────────────────────────────────────────────
        self._current_mod_entries = []
        self._pending_query_path: Path | None = None
        self._pending_dl_query_path: str | None = None
        self._fw_query_queue: list[tuple[str, int]] = []
        self._update_check_queue: list = []
        self._update_check_slug: str = ""
        self._pending_update_check = None
        self._fw_query_slug: str = ""
        self._fw_query_total: int = 0
        self._fw_query_done: int = 0
        self._fw_query_success: int = 0
        self._fw_query_errors: int = 0
        self._fw_query_active: bool = False
        self._pending_fw_query_name: str = ""
        self._current_profile_path: Path | None = None
        self._current_instance_path: Path | None = None
        self._current_instance_paths: InstancePaths | None = None
        self._current_downloads_path: Path | None = None
        self._current_plugin = None  # Active game plugin
        self._current_game_path: Path | None = None

        # Connect model signals for persistence
        model = self._mod_list_view.source_model()
        model.mod_toggled.connect(self._on_mod_toggled)
        model.mods_reordered.connect(self._on_mods_reordered)
        self._mod_list_view.archives_dropped.connect(
            self._on_archives_dropped, Qt.ConnectionType.QueuedConnection,
        )
        self._mod_list_view.archives_dropped_at.connect(
            self._on_archives_dropped_at, Qt.ConnectionType.QueuedConnection,
        )
        self._mod_list_view.fw_context_menu_requested.connect(self._on_fw_context_menu)
        self._mod_list_view.fw_archives_dropped.connect(self._on_fw_archives_dropped)
        self._mod_list_view.fw_active_toggle.connect(self._on_fw_active_toggle)
        self._game_panel.install_requested.connect(self._on_downloads_install)
        self._game_panel.start_requested.connect(self._on_start_game)
        self._game_panel.custom_start_requested.connect(self._on_custom_tool_start)
        self._game_panel.game_started.connect(self._on_game_started)
        self._game_panel.game_stopped.connect(self._unlock_ui)
        self._game_panel.set_predeploy_hook(self._predeploy_for_launch)

        self._game_panel.dl_query_info_requested.connect(self._on_dl_query_info)

        # ── Deferred tab column restore ───────────────────────────────
        self._restored_tabs: set[int] = set()
        self._game_panel._tabs.currentChanged.connect(self._on_tab_changed)

        # Debounce timer for auto-redeploy after mod changes
        self._redeploy_timer = QTimer()
        self._redeploy_timer.setSingleShot(True)
        self._redeploy_timer.setInterval(500)
        self._redeploy_timer.timeout.connect(self._do_redeploy)

        # ── Game Running Lock ─────────────────────────────────────────
        self._game_running: bool = False
        self._unlock_pending: bool = False

        # ── Framework Auto-Re-Lock (5-min unlock-box) ─────────────────
        self._fw_relock_timer = QTimer(self)
        self._fw_relock_timer.setInterval(30_000)  # 30s check interval
        self._fw_relock_timer.timeout.connect(self._fw_relock_tick)
        self._fw_relock_timer.start()

        # ── Erster Start / Instanz laden ──────────────────────────────
        # Locke Frameworks in ALLEN Instanzen bevor die aktuelle geladen wird
        self._fw_relock_startup_scan()
        self._check_first_start()

        # App-weiter Event-Filter für ContextMenu-Events (Wayland-Kompatibilität)
        QApplication.instance().installEventFilter(self)

        # ── Benachrichtigungen (Glocken-Button) ─────────────────────
        self._notification_center = NotificationCenter(self)
        self._notification_center.changed.connect(self._on_notifications_changed)
        # Download-Ereignisse als Quellen anbinden (zusätzlich zur game_panel-Logik)
        dm = self._game_panel.download_manager()
        dm.download_finished.connect(self._on_notify_download_finished)
        dm.download_error.connect(self._on_notify_download_error)

        # ── Update-Check (im Hintergrund, 3s nach Start) ────────────
        self._update_checker = UpdateChecker(self)
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.update_applied.connect(self._on_update_applied)
        self._update_checker.update_progress.connect(self._on_update_progress)
        QTimer.singleShot(3000, self._update_checker.check)

    # ── Menu bar ───────────────────────────────────────────────────

    def _build_menu_bar(self) -> None:
        """Build the full menu bar."""
        menubar = self.menuBar()

        # ════════════════════════════════════════════════════════════════
        # 1. DATEI
        # ════════════════════════════════════════════════════════════════
        fm = menubar.addMenu(tr("menu.file"))

        act = fm.addAction(tr("menu.manage_instances"))
        act.triggered.connect(self._on_manage_instances)

        act = fm.addAction(tr("menu.install_mod"))
        act.setShortcut(QKeySequence("Ctrl+M"))
        act.triggered.connect(self._on_install_mod)

        act = fm.addAction(tr("menu.visit_nexus"))
        act.setShortcut(QKeySequence("Ctrl+N"))
        act.triggered.connect(self._on_menu_visit_nexus)

        fm.addSeparator()

        act = fm.addAction(tr("export_import.menu_entry"))
        act.triggered.connect(self._open_export_import)

        fm.addSeparator()

        plugin_menu = fm.addMenu(tr("menu.plugin_menu"))
        act = plugin_menu.addAction(tr("menu.create_plugin"))
        act.triggered.connect(self._on_create_plugin)
        act = plugin_menu.addAction(tr("menu.edit_plugin"))
        act.triggered.connect(self._on_edit_plugin)

        fm.addSeparator()

        act = fm.addAction(tr("menu.quit"))
        act.triggered.connect(self.close)

        # ════════════════════════════════════════════════════════════════
        # 2. ANSICHT
        # ════════════════════════════════════════════════════════════════
        vm = menubar.addMenu(tr("menu.view"))

        act = vm.addAction(tr("menu.reload"))
        act.setShortcut(QKeySequence("F5"))
        act.triggered.connect(self._on_menu_refresh)

        # ── Toolbars (Submenu) ─────────────────────────────────────
        self._tb_menu = vm.addMenu("Toolbars")

        # Visibility toggles
        self._act_menubar = self._tb_menu.addAction(tr("menu.menubar"))
        self._act_menubar.setCheckable(True)
        self._act_menubar.triggered.connect(self._on_toggle_menubar)

        self._act_toolbar = self._tb_menu.addAction(tr("menu.toolbar"))
        self._act_toolbar.setCheckable(True)
        self._act_toolbar.triggered.connect(self._on_toggle_toolbar)

        self._act_statusbar = self._tb_menu.addAction(tr("menu.statusbar"))
        self._act_statusbar.setCheckable(True)
        self._act_statusbar.triggered.connect(self._on_toggle_statusbar)

        self._tb_menu.addSeparator()

        # Icon size (radio group)
        size_group = QActionGroup(self)
        self._act_small_icons = self._tb_menu.addAction(tr("menu.small_icons"))
        self._act_small_icons.setCheckable(True)
        self._act_small_icons.setActionGroup(size_group)
        self._act_small_icons.triggered.connect(lambda: self._set_toolbar_icon_size(0))

        self._act_medium_icons = self._tb_menu.addAction(tr("menu.medium_icons"))
        self._act_medium_icons.setCheckable(True)
        self._act_medium_icons.setActionGroup(size_group)
        self._act_medium_icons.triggered.connect(lambda: self._set_toolbar_icon_size(1))

        self._act_large_icons = self._tb_menu.addAction(tr("menu.large_icons"))
        self._act_large_icons.setCheckable(True)
        self._act_large_icons.setActionGroup(size_group)
        self._act_large_icons.triggered.connect(lambda: self._set_toolbar_icon_size(2))

        self._tb_menu.addSeparator()

        # Button style (radio group)
        style_group = QActionGroup(self)
        self._act_icons_only = self._tb_menu.addAction(tr("menu.icons_only"))
        self._act_icons_only.setCheckable(True)
        self._act_icons_only.setActionGroup(style_group)
        self._act_icons_only.triggered.connect(
            lambda: self._set_toolbar_button_style(Qt.ToolButtonStyle.ToolButtonIconOnly))

        self._act_text_only = self._tb_menu.addAction(tr("menu.text_only"))
        self._act_text_only.setCheckable(True)
        self._act_text_only.setActionGroup(style_group)
        self._act_text_only.triggered.connect(
            lambda: self._set_toolbar_button_style(Qt.ToolButtonStyle.ToolButtonTextOnly))

        self._act_icons_text = self._tb_menu.addAction(tr("menu.icons_and_text"))
        self._act_icons_text.setCheckable(True)
        self._act_icons_text.setActionGroup(style_group)
        self._act_icons_text.triggered.connect(
            lambda: self._set_toolbar_button_style(Qt.ToolButtonStyle.ToolButtonTextUnderIcon))

        # Sync checkmarks when menu is about to show
        self._tb_menu.aboutToShow.connect(self._update_toolbar_menu)

        # ── Filter-Panel (Toggle) ─────────────────────────────────
        self._act_filter_panel = vm.addAction(tr("menu.filter_panel"))
        self._act_filter_panel.setCheckable(True)
        self._act_filter_panel.setChecked(False)
        self._act_filter_panel.setShortcut(QKeySequence("Ctrl+F"))
        self._act_filter_panel.triggered.connect(self._on_toggle_filter_panel)

        # ── Log (Toggle) ──────────────────────────────────────────
        self._act_log = vm.addAction(tr("menu.log"))
        self._act_log.setCheckable(True)
        self._act_log.setChecked(False)  # default_collapsed=True
        self._act_log.triggered.connect(self._on_toggle_log)

        vm.addSeparator()

        act = vm.addAction(tr("menu.notifications"))
        act.setEnabled(False)

        # ════════════════════════════════════════════════════════════════
        # 3. WERKZEUGE
        # ════════════════════════════════════════════════════════════════
        tm = menubar.addMenu(tr("menu.tools"))

        act = tm.addAction(tr("menu.executables"))
        act.setShortcut(QKeySequence("Ctrl+E"))
        act.triggered.connect(self._on_menu_executables)

        tm.addSeparator()

        act = tm.addAction(tr("menu.tool_plugins"))
        act.setShortcut(QKeySequence("Ctrl+I"))
        act.setEnabled(False)

        self._act_reshade = tm.addAction(tr("menu.reshade_wizard"))
        self._act_reshade.triggered.connect(self._on_reshade_wizard)

        tm.addSeparator()

        act = tm.addAction(tr("menu.settings"))
        act.setShortcut(QKeySequence("Ctrl+S"))
        act.triggered.connect(self._on_menu_settings)

        # ════════════════════════════════════════════════════════════════
        # 4. HILFE
        # ════════════════════════════════════════════════════════════════
        hm = menubar.addMenu(tr("menu.help"))

        act = hm.addAction(tr("menu.help_item"))
        act.setShortcut(QKeySequence("Ctrl+H"))
        act.triggered.connect(self._on_menu_help)

        act = hm.addAction(tr("menu.ui_help"))
        act.setEnabled(False)

        act = hm.addAction(tr("menu.documentation"))
        act.triggered.connect(
            lambda: host_open_url("https://github.com/Marc1326/Anvil-Organizer/wiki")
        )

        act = hm.addAction(tr("menu.discord"))
        act.setEnabled(False)

        act = hm.addAction(tr("menu.report_issue"))
        act.triggered.connect(
            lambda: host_open_url("https://github.com/Marc1326/Anvil-Organizer/issues")
        )

        tutorials_menu = hm.addMenu("Tutorials")
        tutorials_menu.setEnabled(False)

        hm.addSeparator()

        act = hm.addAction(tr("menu.about_anvil"))
        act.triggered.connect(self._on_about)

        act = hm.addAction(tr("menu.about_qt"))
        act.triggered.connect(self._on_about_qt)

        # Titelzeile wie im Handoff: Instanz-Dropdown mittig,
        # Benachrichtigungen rechts (nur modernes Design)
        self._instance_dropdown = InstanceDropdown(
            self.instance_manager, self.icon_manager)
        self._instance_dropdown.instance_selected.connect(
            self._switch_instance_with_overlay)
        self._instance_dropdown.new_instance_requested.connect(
            self._on_dropdown_new_instance)
        self._instance_dropdown.manager_requested.connect(
            self._on_manage_instances)
        self._title_notif_btn = NotificationButton()
        self._title_notif_btn.setObjectName("titleNotifBtn")
        self._title_notif_btn.setText(tr("status.notifications"))
        self._title_notif_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._title_notif_btn.clicked.connect(
            self._on_title_notifications_clicked)
        self._title_theme_btn = QToolButton()
        self._title_theme_btn.setObjectName("titleThemeBtn")
        self._title_theme_btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._title_theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._title_theme_btn.clicked.connect(self._on_title_theme_toggle)
        self._update_title_theme_btn()
        self._title_span = TitleBarSpan(
            menubar, self._instance_dropdown, self._title_notif_btn,
            self._title_theme_btn)
        self._switch_overlay = SwitchOverlay(self)

    # ── Icon size constants ─────────────────────────────────────────

    _ICON_SIZES = [QSize(24, 24), QSize(32, 32), QSize(42, 36)]

    # ── Menu action handlers ──────────────────────────────────────────

    def _on_manage_instances(self) -> None:
        """Datei → Instanzen verwalten..."""
        from anvil.widgets.instance_manager_dialog import InstanceManagerDialog
        dlg = InstanceManagerDialog(
            self, self.instance_manager, self.plugin_loader,
            self.icon_manager,
        )
        _center_on_parent(dlg)
        dlg.exec()
        self.update()
        if dlg.switched_to:
            self.switch_instance(dlg.switched_to)
        elif hasattr(self, "_instance_dropdown"):
            # Cover könnte geändert worden sein — Chip und GamePanel aktualisieren
            self._instance_dropdown.refresh_current()
            if hasattr(self, "_game_panel"):
                self._game_panel._update_game_button_icon(
                    self._game_panel._last_game_name)

    def _switch_instance_with_overlay(self, name: str) -> None:
        """Instanzwechsel aus dem Dropdown: Overlay-Sequenz um das
        bestehende switch_instance() herum — die Logik bleibt unberührt."""
        old = self.instance_manager.current_instance() or ""
        if name == old:
            return
        ovl = self._switch_overlay
        if old:
            ovl.start(tr("instance.closing", name=old))
        else:
            ovl.start(tr("instance.opening", name=name))

        def _phase2() -> None:
            ovl.set_phase(tr("instance.opening", name=name))
            QTimer.singleShot(60, _do_switch)

        def _do_switch() -> None:
            try:
                self.switch_instance(name)
            finally:
                ovl.finish()
                Toast(self, tr("toast.instance_loaded", name=name))

        QTimer.singleShot(650, _phase2)

    def _on_dropdown_new_instance(self) -> None:
        """＋ Neue Instanz… aus dem Dropdown — öffnet den Assistenten."""
        wizard = CreateInstanceWizard(
            self, self.instance_manager, self.plugin_loader,
            self.icon_manager,
        )
        _center_on_parent(wizard)
        wizard.exec()
        if wizard.created_instance:
            self._switch_instance_with_overlay(wizard.created_instance)

    def _on_create_plugin(self) -> None:
        """Datei → Game Plugin erstellen (leerer Dialog)."""
        from anvil.widgets.plugin_creator_dialog import PluginCreatorDialog
        dlg = PluginCreatorDialog(
            self,
            plugin=None,
            icon_manager=self._game_panel._icon_manager if self._game_panel else None,
        )
        if dlg.exec() == PluginCreatorDialog.DialogCode.Accepted:
            QMessageBox.information(
                self, "Neustart",
                tr("plugin_creator.restart_hint"),
            )

    def _on_edit_plugin(self) -> None:
        """Datei → Game Plugin ändern (aktuelles Plugin)."""
        from anvil.widgets.plugin_creator_dialog import PluginCreatorDialog
        dlg = PluginCreatorDialog(
            self,
            plugin=self._current_plugin,
            icon_manager=self._game_panel._icon_manager if self._game_panel else None,
        )
        if dlg.exec() == PluginCreatorDialog.DialogCode.Accepted:
            QMessageBox.information(
                self, "Neustart",
                tr("plugin_creator.restart_hint"),
            )

    def _on_menu_visit_nexus(self) -> None:
        """Datei → Nexus besuchen."""
        nexus_slug = ""
        if self._current_plugin:
            nexus_slug = getattr(self._current_plugin, "GameNexusName", "") or getattr(self._current_plugin, "GameShortName", "")
        if nexus_slug:
            host_open_url(f"https://www.nexusmods.com/{nexus_slug}")
        else:
            host_open_url("https://www.nexusmods.com")

    def _on_menu_refresh(self) -> None:
        """Ansicht → Neu laden (F5)."""
        self._reload_mod_list()
        self.statusBar().showMessage(tr("status.mod_list_reloaded"), 3000)

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

    @staticmethod
    def _toolbar_style_key_and_default() -> tuple:
        """Settings-Schlüssel + Default für den Toolbar-Stil der aktiven Welt."""
        from anvil.styles.dark_theme import theme_color
        if theme_color("panel2", ""):  # modernes Theme
            return ("view/toolbar_button_style_v2",
                    Qt.ToolButtonStyle.ToolButtonTextOnly)
        return ("view/toolbar_button_style",
                Qt.ToolButtonStyle.ToolButtonIconOnly)

    def _set_toolbar_button_style(self, style: Qt.ToolButtonStyle) -> None:
        """Set toolbar button style."""
        self._toolbar.setToolButtonStyle(style)
        # Qt propagiert den Stil nur auf addAction()-Buttons — unsere
        # Buttons kommen per addWidget() und brauchen ihn einzeln.
        install_btn = getattr(self._toolbar, "install_btn", None)
        for btn in self._toolbar.findChildren(QToolButton):
            if btn is install_btn or btn.objectName().startswith("qt_"):
                continue
            btn.setToolButtonStyle(style)

    def _update_toolbar_menu(self) -> None:
        """Sync checkmarks with actual widget state."""
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

    def keyPressEvent(self, event):
        """Forward to super (Alt handling moved to eventFilter)."""
        super().keyPressEvent(event)


    def _on_menu_executables(self) -> None:
        """Werkzeuge → Executables... (Strg+E)."""
        from anvil.widgets.executables_dialog import ExecutablesDialog
        dlg = ExecutablesDialog(self)
        _center_on_parent(dlg)
        dlg.exec()

    def _on_menu_settings(self) -> None:
        """Werkzeuge → Einstellungen... (Strg+S)."""
        from anvil.widgets.settings_dialog import SettingsDialog
        dlg = SettingsDialog(
            self,
            self.plugin_loader,
            self.instance_manager,
            on_clear_modindex=self._clear_modindex_cache,
            diagnostics_provider=self.collect_diagnostics_conflicts,
            on_storage_migration=self._on_storage_migration,
            on_locate_storage=self._on_locate_storage,
        )
        _center_on_parent(dlg)
        was_keeping = self.keeps_mods_deployed()
        accepted = dlg.exec() == SettingsDialog.DialogCode.Accepted
        if accepted:
            self._apply_keep_deployed_change(was_keeping)
        # Re-read API key (SSO/manual entry saves immediately, even before OK)
        new_key = SettingsDialog.load_api_key()
        if new_key:
            self._nexus_api.set_api_key(new_key)
            self._status_bar.update_api_status(logged_in=True)
        else:
            self._nexus_api.set_api_key("")
            self._status_bar.update_api_status(logged_in=False)
        if accepted:
            # Theme + Farben final anwenden — konsequent auf App-Ebene,
            # damit Vorschau und finaler Zustand identisch wirken.
            saved_theme = self._settings().value("style/theme", default_theme())
            accent, density = style_prefs(self._settings())
            apply_theme(QApplication.instance(), saved_theme,
                        load_overrides(self._settings(), saved_theme),
                        accent=accent, density=density)
            # Altes Fenster-Stylesheet entfernen — es würde das App-QSS überdecken
            self.setStyleSheet("")
            # Ansichts-Einstellungen der (evtl. gewechselten) Welt anwenden,
            # z.B. Toolbar-Stil modern=Text / klassisch=Icons
            self._restore_view_settings()
            # Apply API counter visibility immediately
            hidden = self._settings().value("Nexus/hide_api_counter", False, type=bool)
            self._status_bar.set_api_counter_visible(not hidden)
            # Reload current instance to apply changed paths
            if self.instance_manager.current_instance():
                self.switch_instance(self.instance_manager.current_instance())

    def _on_locate_storage(self) -> None:
        name = self.instance_manager.current_instance()
        if not name:
            QMessageBox.warning(self, tr("storage.title"), tr("storage.error_no_instances"))
            return
        data = self.instance_manager.load_instance(name)
        instance = self.instance_manager.instances_path() / name
        paths = resolve_instance_paths(instance, data)
        unavailable = unavailable_configured_storage(paths, data)
        if not unavailable:
            QMessageBox.information(
                self,
                tr("storage.title"),
                tr("storage.locate_none_missing"),
            )
            return
        components = [status.component for status in unavailable]
        labels = [tr(f"storage.component_{component}") for component in components]
        label, accepted = QInputDialog.getItem(
            self,
            tr("storage.locate"),
            tr("storage.locate_choose_component"),
            labels,
            0,
            False,
        )
        if not accepted:
            return
        component = components[labels.index(label)]
        candidate = QFileDialog.getExistingDirectory(
            self,
            tr("storage.locate"),
            str(instance),
        )
        if not candidate:
            return
        from anvil.core.storage_markers import verify_location_marker

        try:
            instance_id = self.instance_manager.ensure_instance_id(name)
            verify_location_marker(Path(candidate), instance_id, component)
            key = {
                "mods": "path_mods_directory",
                "downloads": "path_downloads_directory",
                "profiles": "path_profiles_directory",
                "overwrite": "path_overwrite_directory",
                "backups": "path_backups_directory",
                "cache": "path_cache_directory",
            }[component]
            old_values = self.instance_manager.update_instance_paths_atomic(
                name,
                {key: candidate},
            )
            if not self.switch_instance(name):
                self.instance_manager.update_instance_paths_atomic(name, old_values)
                self.switch_instance(name)
                raise RuntimeError(tr("storage.error_load_instance", name=name))
        except Exception as exc:
            QMessageBox.warning(self, tr("storage.title"), str(exc))
            return
        Toast(self, tr("storage.locate_success", path=candidate))

    def _on_storage_migration(self) -> None:
        thread = getattr(self, "_storage_thread", None)
        if thread is not None and thread.isRunning():
            Toast(self, tr("storage.already_running"))
            return
        from anvil.dialogs.storage_migration_dialog import StorageMigrationDialog

        dialog = StorageMigrationDialog(
            self,
            manager=self.instance_manager,
            current_instance=self.instance_manager.current_instance(),
        )
        self._storage_dialog = dialog
        dialog.migration_requested.connect(self._begin_storage_migration)
        dialog.cancel_requested.connect(self._cancel_storage_migration)
        _center_on_parent(dialog)
        dialog.exec()
        if getattr(self, "_storage_dialog", None) is dialog:
            self._storage_dialog = None

    def _schedule_base_directory_migration(self, request) -> None:
        if self._game_running or self._game_panel.is_game_running():
            self._storage_fail(tr("storage.error_game_running"))
            return
        source = anvil_base_paths().base
        target = request.target_base / source.name
        if target.exists():
            self._storage_fail(tr("base_dir.error_target_exists", path=str(target)))
            return
        answer = QMessageBox.question(
            self,
            tr("base_dir.migration_title"),
            tr(
                "base_dir.migration_confirm",
                source=str(source),
                target=str(target),
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            dialog = getattr(self, "_storage_dialog", None)
            if dialog is not None:
                dialog._running = False
                dialog._show_page(dialog.PAGE_REVIEW)
            return

        for data in self.instance_manager.list_instances():
            name = str(data["name"])
            if not self.switch_instance(name):
                self._storage_fail(tr("storage.error_load_instance", name=name))
                return
            if self._game_panel.is_game_running():
                self._storage_fail(tr("storage.error_game_running"))
                return
            purge_result = self._game_panel.silent_purge()
            if purge_result is not None and not getattr(purge_result, "success", False):
                errors = getattr(purge_result, "errors", [])
                self._storage_fail("\n".join(str(error) for error in errors))
                return

        from anvil.core.base_migration import schedule_base_migration
        from anvil.core.storage_migration import VerificationLevel

        try:
            schedule_base_migration(
                source=source,
                target=target,
                verification=(
                    VerificationLevel.FULL
                    if request.verification == "full"
                    else VerificationLevel.FAST
                ),
            )
        except Exception as exc:
            self._storage_fail(str(exc))
            return
        dialog = getattr(self, "_storage_dialog", None)
        if dialog is not None:
            dialog.accept()
        QTimer.singleShot(0, self._restart_app)

    def _begin_storage_migration(self, request) -> None:
        if request.base_directory:
            self._schedule_base_directory_migration(request)
            return
        if self._game_running or self._game_panel.is_game_running():
            self._storage_fail(tr("storage.error_game_running"))
            return
        for name in request.instances:
            data = self.instance_manager.load_instance(name)
            if not data:
                self._storage_fail(tr("storage.error_instance_missing", name=name))
                return
            if data.get("game_short_name") == "baldursgate3":
                self._storage_fail(tr("storage.error_bg3_excluded", name=name))
                return

        self._storage_request = request
        self._storage_queue = list(request.instances)
        self._storage_original_instance = self.instance_manager.current_instance()
        self._storage_cancel_event = threading.Event()
        self._storage_started_at = time.monotonic()
        self._storage_completed_instances = 0
        self._storage_failed = False
        self._start_next_storage_instance()

    def _start_next_storage_instance(self) -> None:
        if self._storage_failed:
            return
        if not self._storage_queue:
            original = self._storage_original_instance
            if original and self.instance_manager.current_instance() != original:
                self.switch_instance(original)
            dialog = getattr(self, "_storage_dialog", None)
            if dialog is not None:
                dialog.show_result(
                    success=True,
                    message=tr(
                        "storage.complete_message",
                        count=self._storage_completed_instances,
                    ),
                )
            return

        from anvil.core.storage_migration import (
            InstanceStorageMigration,
            VerificationLevel,
        )
        from anvil.dialogs.storage_migration_dialog import StorageMigrationWorker

        name = self._storage_queue.pop(0)
        self._storage_active_instance = name
        if not self.switch_instance(name):
            self._storage_fail(tr("storage.error_load_instance", name=name))
            return
        if self._game_panel.is_game_running():
            self._storage_fail(tr("storage.error_game_running"))
            return
        purge_result = self._game_panel.silent_purge()
        if purge_result is not None and not getattr(purge_result, "success", False):
            errors = getattr(purge_result, "errors", [])
            self._storage_fail("\n".join(str(error) for error in errors))
            return

        folder_names = {
            "mods": "Mods",
            "downloads": "Downloads",
            "profiles": "Profiles",
            "overwrite": "Overwrite",
            "backups": "Backups",
            "cache": "Cache",
        }
        base = self._storage_request.target_base / name
        components = {
            component: base / folder_names[component]
            for component in self._storage_request.components
        }
        journal_directory = (
            self.instance_manager.instances_path().parent
            / ".migration-journals"
            / "active"
            / name
        )
        instance_path = self.instance_manager.instances_path() / name

        def reindex(mods_path: Path) -> None:
            index = ModIndex(instance_path, mods_path=mods_path)
            index.rebuild()

        migration = InstanceStorageMigration(
            manager=self.instance_manager,
            instance_name=name,
            components=components,
            journal_directory=journal_directory,
            reindex=reindex,
            verification=(
                VerificationLevel.FULL
                if self._storage_request.verification == "full"
                else VerificationLevel.FAST
            ),
            cancel_requested=self._storage_cancel_event.is_set,
            defer_completion=True,
        )
        thread = QThread(self)
        worker = StorageMigrationWorker(migration)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_storage_progress)
        worker.finished.connect(self._on_storage_worker_finished)
        worker.failed.connect(self._on_storage_worker_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._on_storage_thread_finished)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._storage_thread = thread
        self._storage_worker = worker
        self._storage_pending_next = False
        thread.start()

    def _on_storage_progress(self, component: str, progress) -> None:
        dialog = getattr(self, "_storage_dialog", None)
        if dialog is None:
            return
        current = progress.bytes_copied + progress.current_file_bytes
        total = max(1, progress.total_bytes)
        fraction = min(1.0, current / total)
        elapsed = max(0.001, time.monotonic() - self._storage_started_at)
        speed = current / elapsed
        remaining = max(0, total - current)
        eta = remaining / speed if speed > 0 else 0
        current_file = str(progress.current_path) if progress.current_path else "—"
        dialog.update_progress(
            fraction=fraction,
            component=tr(f"storage.component_{component}"),
            current_file=current_file,
            counts=tr(
                "storage.progress_counts",
                files=progress.files_copied,
                bytes=current,
                total=progress.total_bytes,
            ),
            timing=tr(
                "storage.progress_timing",
                speed=f"{speed / (1024 * 1024):.1f} MiB/s",
                elapsed=f"{elapsed:.1f}s",
                eta=f"{eta:.1f}s",
            ),
        )

    def _on_storage_worker_finished(self, migration) -> None:
        name = self._storage_active_instance
        deploy_ok = self.switch_instance(name)
        try:
            migration.complete_after_redeploy(deploy_ok)
        except Exception as exc:
            self.switch_instance(name)
            self._storage_fail(str(exc))
            return

        active_journal = migration.journal_directory
        if active_journal.is_dir():
            history = (
                active_journal.parent.parent
                / "history"
                / f"{name}-{time.time_ns()}"
            )
            history.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(active_journal), str(history))
        self._storage_completed_instances += 1
        self._storage_pending_next = True

    def _on_storage_worker_failed(self, message: str) -> None:
        self.switch_instance(self._storage_active_instance)
        self._storage_fail(message)

    def _on_storage_thread_finished(self) -> None:
        self._storage_thread = None
        self._storage_worker = None
        if getattr(self, "_storage_pending_next", False) and not self._storage_failed:
            QTimer.singleShot(0, self._start_next_storage_instance)

    def _cancel_storage_migration(self) -> None:
        event = getattr(self, "_storage_cancel_event", None)
        if event is not None:
            event.set()

    def _storage_fail(self, message: str) -> None:
        self._storage_failed = True
        if hasattr(self, "_storage_queue"):
            self._storage_queue.clear()
        dialog = getattr(self, "_storage_dialog", None)
        if dialog is not None:
            dialog.show_result(success=False, message=message)

    def _on_reshade_wizard(self) -> None:
        """Werkzeuge → ReShade Wizard."""
        from anvil.dialogs.reshade_wizard import ReshadeWizard

        game_path = self._current_game_path
        if game_path is None:
            return

        plugin = self._current_plugin
        game_binary = getattr(plugin, "GameBinary", "") if plugin else ""
        instance_name = self.instance_manager.current_instance() or ""

        dlg = ReshadeWizard(game_path, game_binary, instance_name, self)
        _center_on_parent(dlg)
        dlg.exec()

    # ── Proton Tools ─────────────────────────────────────────────────
    def _rebuild_proton_menu(self, menu) -> None:
        from anvil.widgets.proton_tools_dialog import load_proton_tools
        menu.clear()
        tools = []
        if self._current_instance_path:
            tools = load_proton_tools(self._current_instance_path)
        for i, tool in enumerate(tools):
            name = tool.get("name", "?")
            act = menu.addAction(name)
            act.triggered.connect(
                lambda checked=False, idx=i: self._run_proton_tool(idx)
            )
        if tools:
            menu.addSeparator()
        manage_act = menu.addAction(tr("proton_tools.manage"))
        manage_act.triggered.connect(lambda checked=False: self._on_proton_manage())

    def _run_proton_tool(self, idx: int) -> None:
        from anvil.widgets.proton_tools_dialog import load_proton_tools
        if not self._current_instance_path:
            return
        tools = load_proton_tools(self._current_instance_path)
        if idx < 0 or idx >= len(tools):
            return
        tool = tools[idx]
        exe_path = tool.get("exe_path", "")
        if not exe_path:
            return
        if not self._game_panel.confirm_start_while_running():
            return
        predeploy = self._predeploy_for_launch("proton_tool_start")
        if not predeploy:
            self._report_predeploy_failure(predeploy)
            return
        args = tool.get("args", [])
        wdir = tool.get("working_dir", "")
        self._game_panel.run_with_proton(exe_path, args, wdir or None)

    def _on_proton_manage(self) -> None:
        from anvil.widgets.proton_tools_dialog import ProtonToolsDialog
        dlg = ProtonToolsDialog(self, instance_path=self._current_instance_path)
        dlg.exec()

    def _on_menu_help(self) -> None:
        """Hilfe → Hilfe (Strg+H)."""
        host_open_url("https://github.com/Marc1326/Anvil-Organizer")

    def _clear_modindex_cache(self) -> None:
        """Clear the mod file index cache and trigger a full re-scan."""
        if self._mod_index is not None:
            self._mod_index.clear()
            self.statusBar().showMessage(tr("status.modindex_cleared"), 3000)

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

        # Button style — getrennte Merker pro Welt: modern = Textbuttons
        # (Handoff-Default), klassisch = Icons. User-Wahl gilt je Welt.
        key, default_style = self._toolbar_style_key_and_default()
        raw_style = s.value(key)
        if raw_style is None:
            self._set_toolbar_button_style(default_style)
        else:
            self._set_toolbar_button_style(Qt.ToolButtonStyle(int(raw_style)))

        # Visibility (default: all visible except log)
        if s.value("view/menubar_visible") is not None:
            self.menuBar().setVisible(s.value("view/menubar_visible", True, type=bool))
        if s.value("view/toolbar_visible") is not None:
            self._toolbar.setVisible(s.value("view/toolbar_visible", True, type=bool))
        if s.value("view/statusbar_visible") is not None:
            self._status_bar.setVisible(s.value("view/statusbar_visible", True, type=bool))

        # Safety net: if both menubar AND toolbar are hidden, force menubar visible
        if not self.menuBar().isVisible() and not self._toolbar.isVisible():
            self.menuBar().setVisible(True)
            if hasattr(self, "_act_menubar"):
                self._act_menubar.setChecked(True)

        # Filter panel
        fp_open = s.value("view/filter_panel_open", False, type=bool)
        self._filter_panel.set_open(fp_open)
        self._act_filter_panel.setChecked(fp_open)
        fp_splitter = s.value("view/filter_splitter_state")
        if fp_splitter:
            self._filter_splitter.restoreState(fp_splitter)

        # Log: CollapsibleSectionBar restores its own state; sync menu check
        self._act_log.setChecked(not self._log_bar.collapsed)

        # Modern: Seiten-Splitter verriegeln — Panelbreiten sind fest
        self._apply_splitter_locks()

    def _apply_splitter_locks(self) -> None:
        """Modern: Filter-/Game-Panel-Schieber nicht ziehbar (feste Breiten),
        Griff = 1-px-Trennlinie; klassisch: frei ziehbar in Standard-Breite."""
        from anvil.styles.dark_theme import theme_color
        locked = bool(theme_color("panel2", ""))
        if not hasattr(self, "_default_handle_width"):
            self._default_handle_width = self._splitter.handleWidth()
        for sp in (self._filter_splitter, self._splitter):
            sp.setHandleWidth(1 if locked else self._default_handle_width)
            for i in range(1, sp.count()):
                h = sp.handle(i)
                if h is not None:
                    h.setEnabled(not locked)
        # Modern: kein Abstand zwischen Splittern und Log-Leiste —
        # die 1-px-Linien enden direkt an der Leiste (wie in der Vorlage)
        lay = self.centralWidget().layout()
        if not hasattr(self, "_default_layout_spacing"):
            self._default_layout_spacing = lay.spacing()
        lay.setSpacing(0 if locked else self._default_layout_spacing)
        if not locked:
            return
        # Restaurierte Splitter-Stände an die festen Breiten angleichen —
        # der Splitter klemmt das Panel zwar auf min/max, positioniert den
        # Nachbarn aber nach dem alten Stand: die Differenz bleibt als
        # unsichtbare Lücke stehen (gleiche Hintergrundfarbe).
        fp_w = self._filter_panel.maximumWidth()
        total = sum(self._filter_splitter.sizes())
        if total > fp_w:
            self._filter_splitter.setSizes([fp_w, total - fp_w])
        gp_w = self._game_panel.maximumWidth()
        total = sum(self._splitter.sizes())
        if total > gp_w:
            self._splitter.setSizes([total - gp_w, gp_w])

    # ── Mod-Liste Settings (Backend-Logik) ──────────────────────────

    def _apply_modlist_settings(self) -> None:
        """Read all 10 ModList/ QSettings keys and apply them to Model/View.

        Called after Settings-Dialog OK and after instance load.
        Settings 1-3 have full backend logic; settings 4-10 set
        attributes on Model/View for the parallel dev-agent.
        """
        s = self._settings()
        tree = self._mod_list_view._tree
        model = self._mod_list_view.source_model()

        # Setting 1: Separator colors on scrollbar
        show_sep_colors = s.value("ModList/show_separator_colors", True, type=bool)
        self._mod_list_view.set_scrollbar_marking_enabled(show_sep_colors)

        # Setting 2: Show external mods (applied during scan, stored for re-scan)
        # The actual filtering happens in scan_mods_directory(include_external=...)
        # which is called from _apply_instance and _reload_mod_list.

        # Setting 3: Check updates after install (flag read in _install_archives)
        # No runtime attribute needed — read directly from QSettings at install time.

        # Setting 4: Auto-expand on drag (attribute for drag handler)
        tree._auto_expand_on_drag = s.value(
            "ModList/auto_collapse_on_drag", False, type=bool)

        # Setting 5: Conflicts ON separator (aggregated in collapsed separator row)
        model._conflicts_on_separator = s.value(
            "ModList/conflicts_on_separator", True, type=bool)

        # Setting 6: Conflicts FROM separator (highlight external conflicting mods)
        # Note: This flag is checked in _DropTreeView.selectionChanged(), not in the model
        tree._conflicts_from_separator = s.value(
            "ModList/conflicts_from_separator", True, type=bool)

        # Conflict highlighting on mod selection
        tree._conflict_highlight_on_select = s.value(
            "ModList/conflict_highlight_on_select", True, type=bool)

        # Settings 7-10: Symbol icons on collapsed separators
        model._symbol_conflicts = s.value(
            "ModList/symbol_conflicts", True, type=bool)
        model._symbol_flags = s.value(
            "ModList/symbol_flags", True, type=bool)
        model._symbol_content = s.value(
            "ModList/symbol_content", True, type=bool)
        model._symbol_version = s.value(
            "ModList/symbol_version", True, type=bool)

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

        # Alt-key toggles menubar (robust recovery, works even when hidden)
        if (obj is self
                and event.type() == QEvent.Type.KeyRelease
                and event.key() == Qt.Key.Key_Alt
                and not event.isAutoRepeat()
                and not event.modifiers() & ~Qt.KeyboardModifier.AltModifier):
            s = self._settings()
            if s.value("Interface/show_menubar_on_alt", True, type=bool):
                mb = self.menuBar()
                mb.setVisible(not mb.isVisible())
                if hasattr(self, "_act_menubar"):
                    self._act_menubar.setChecked(mb.isVisible())
                return True

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
            _center_on_parent(wizard)
            wizard.exec()
            if wizard.created_instance:
                self.switch_instance(wizard.created_instance)
                return

        # Load current instance (if any) — switch_instance kapselt Fehler selbst ab
        current = self.instance_manager.current_instance()
        if current:
            self.switch_instance(current)
        else:
            self._status_bar.clear_instance()

        # Check for nxm:// URL passed via command line (mod or collection)
        nxm_raw = get_nxm_arg()
        if nxm_raw:
            self.handle_nxm_url(nxm_raw)

        # Check for --launch-instance passed via command line (Shortcut-Button, #24)
        launch_inst = get_launch_instance_arg()
        if launch_inst:
            QTimer.singleShot(0, lambda n=launch_inst: self.launch_instance_shortcut(n))

    def _crash_recovery_purge(self) -> None:
        """Clean every game directory before anything is loaded.

        Mods only belong in the game directory while the game runs.  If
        the app crashed or was killed, links may still be sitting there
        — purge what a manifest covers, then sweep up anything an older
        run left behind without one.

        A game started from an earlier Anvil session may still be running,
        so every directory with a live deployment is checked first: the
        watch target does not survive a restart, and this purge would
        otherwise pull the files out from under it.
        """
        from anvil.core.mod_deployer import ModDeployer
        from anvil.core.game_process import find_game_process, plugin_watch_target
        for entry in self.instance_manager.list_instances():
            name = entry.get("name", "") if isinstance(entry, dict) else str(entry)
            if not name:
                continue
            instance_path = self.instance_manager.instances_path() / name
            data = self.instance_manager.load_instance(name)
            game_path_str = data.get("game_path", "") if data else ""
            if not game_path_str:
                continue
            game_path = Path(game_path_str)
            if not game_path.is_dir():
                continue
            short_name = data.get("game_short_name", "") if data else ""
            plugin = self.plugin_loader.get_game(short_name) if short_name else None
            # Ohne Plugin kann Anvil das Spiel gar nicht gestartet haben —
            # dann bleibt es beim Aufräumen wie bisher.
            app_id, binary = plugin_watch_target(plugin)
            if app_id or binary:
                pid, reliable = find_game_process(app_id, binary)
                if pid is not None or not reliable:
                    print(
                        f"[PURGE] {name}: game may still be running — "
                        "deployment kept",
                        flush=True,
                    )
                    continue
            has_manifest = (instance_path / ModDeployer.MANIFEST_NAME).is_file()
            paths = resolve_instance_paths(instance_path, data)
            deployer = ModDeployer(
                instance_path,
                game_path,
                mods_path=paths.mods,
                profiles_path=paths.profiles,
            )
            if has_manifest:
                deployer.purge()
            orphans = deployer.remove_orphaned_links()
            if orphans:
                print(
                    f"[PURGE] {name}: removed {orphans} leftover link(s)",
                    flush=True,
                )

    def _teardown_current_instance(self) -> None:
        """Phase 1: Alten Instance-State sichern und leeren.

        Reihenfolge ist KRITISCH:
        - Timer stoppen VOR Purge (sonst deployed Timer nach Purge nochmal)
        - Async-Queues leeren VOR State-Nullung (Callbacks pruefen Queues)
        - State speichern VOR Model-Clearing (sonst werden leere Daten gespeichert)
        - Purge VOR State-Nullung (braucht _deployer und _current_plugin)
        """
        # ── Schritt 1: Timer stoppen ──
        self._redeploy_timer.stop()

        # ── Schritt 2: Asynchrone Operationen abbrechen ──
        # Nexus-API Queues leeren + active-Flags auf False
        self._fw_query_queue.clear()
        self._fw_query_active = False
        if hasattr(self, "_batch_query_queue"):
            self._batch_query_queue.clear()
        if hasattr(self, "_batch_query_active"):
            self._batch_query_active = False
        self._update_check_queue.clear()
        self._pending_update_check = None
        # REDmod-Prozess abbrechen falls aktiv
        self._game_panel.cancel_redmod_if_running()

        # ── Schritt 3: State speichern (VOR Daten-Clearing!) ──
        # Nur wenn eine aktive Instanz existiert (nicht beim ersten Start)
        if self._current_instance_path is not None:
            # Mod-Reihenfolge sichern (non-BG3)
            if self._bg3_installer is None and self._current_mod_entries:
                self._write_current_modlist()
            # BG3-Trenner sichern
            if self._bg3_installer is not None:
                self._bg3_save_separators()
            # Collapsed Separators + Splitter + Filter-State sichern
            self._save_ui_state()
            # Frameworks der verlassenen Instanz locken (Game-Switch)
            framework_state.lock_all(self._current_instance_path)

        # ── Schritt 4: Deploy purgen ──
        # silent_purge() braucht _deployer und _current_plugin (noch nicht None!)
        # Läuft das Spiel noch, bleibt alles liegen — der nächste Start räumt auf.
        if self._game_running or self._game_panel.is_game_running():
            print("[PURGE] instance switch while the game may run — "
                  "deployment kept", flush=True)
        else:
            # Keep-deployed belongs to one game only: the mods go out and the
            # flag drops, so the choice has to be made again per game.
            leaving = self.instance_manager.current_instance()
            self._game_panel.silent_purge()
            if leaving:
                self._lift_keep_deployed(leaving)

        # ── Schritt 5: Model leeren ──
        self._mod_list_view.clear_mods()

        # Collapsed Separators leeren (KERN-FIX fuer den gemeldeten Bug)
        self._mod_list_view._tree._collapsed_separators.clear()

        # Highlighted/Conflict Rows leeren (Indices werden im neuen Game ungueltig)
        model = self._mod_list_view.source_model()
        model._highlighted_rows.clear()
        model._conflict_win_rows.clear()
        model._conflict_lose_rows.clear()

        # ── Schritt 6: Filter + Suche zuruecksetzen ──
        self._filter_panel.reset_all()
        self._mod_search.clear()

        # ── Schritt 7: State-Variablen nullen ──
        self._current_mod_entries = []
        self._current_profile_path = None
        self._current_instance_path = None
        self._current_instance_paths = None
        self._current_downloads_path = None
        self._current_plugin = None
        self._current_game_path = None
        self._bg3_installer = None
        self._mod_index = None

    def switch_instance(self, instance_name: str) -> bool:
        """Switch to a different instance and update all UI components.

        Called by the toolbar after the instance manager dialog closes.
        2-phase approach: teardown old state, then apply new state.

        Args:
            instance_name: Name of the instance to switch to.
        """
        self._teardown_current_instance()
        try:
            deploy_ok = self._apply_instance(instance_name)
        except Exception as e:  # noqa: BLE001 — kaputte Instanz darf die App nicht abschießen
            import traceback
            self._log_panel.add_log(
                "error",
                f"Instanz '{instance_name}' konnte nicht geladen werden: {e}",
            )
            print(
                f"[MainWindow] Instanz-Load fehlgeschlagen ({instance_name}):\n"
                f"{traceback.format_exc()}"
            )
            # Vollständiger "Kein Spiel"-Reset, damit kein halb-geladener UI-Zustand bleibt.
            try:
                self._apply_instance("")
            except Exception:  # noqa: BLE001
                self._status_bar.clear_instance()
            if hasattr(self, "_instance_dropdown"):
                self._instance_dropdown.refresh_current()
            return False
        # Erst nach erfolgreichem Laden persistieren — sonst zeigt .current bei
        # einem Fehler auf eine kaputte Instanz und die App startet nicht mehr.
        self.instance_manager.set_current_instance(instance_name)
        if hasattr(self, "_instance_dropdown"):
            self._instance_dropdown.refresh_current()
        return deploy_ok

    def _apply_instance(self, instance_name: str) -> bool:
        """Load instance data and update all widgets.

        Phase 2 of instance switching: builds new state.
        Expects _teardown_current_instance() to have been called first
        (via switch_instance) so the model/state is already clean.

        Args:
            instance_name: Name of the instance to apply.
        """
        data = self.instance_manager.load_instance(instance_name)
        if not data:
            self.setWindowTitle(f"Anvil Organizer v{APP_VERSION}")
            self._game_panel.update_game("Kein Spiel ausgewählt", None)
            self._mod_list_view.clear_mods()
            self._current_mod_entries = []
            self._current_profile_path = None
            self._current_instance_path = None
            self._current_downloads_path = None
            self._current_plugin = None
            self._current_game_path = None
            self._mod_index = None
            self._bg3_installer = None
            self._mod_list_view.set_extra_drop_extensions(set())
            self._toolbar.deploy_sep.setVisible(False)
            self._toolbar.deploy_action.setVisible(False)
            self._toolbar.proton_action.setVisible(False)
            self._toolbar.merger_sep.setVisible(False)
            self._toolbar.merger_action.setVisible(False)
            self._toolbar.plugin_sort_sep.setVisible(False)
            self._toolbar.plugin_sort_action.setVisible(False)
            self._mod_list_stack.setCurrentWidget(self._mod_list_view)
            self._update_active_count()
            self._status_bar.clear_instance()
            self._act_reshade.setEnabled(False)
            return False

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
            elif p.is_file() and p.suffix.lower() == ".exe":
                game_path = p.parent

        plugin = self.plugin_loader.get_game(short_name) if short_name else None
        self._current_plugin = plugin
        self._current_game_path = game_path

        # Sync plugin game path with instance config (instance may store a
        # different path than what detectGame() found via store detection)
        if plugin is not None and game_path is not None:
            plugin.setGamePath(game_path, store=store if store else None)

        # ReShade menu item: enable when game path is available
        self._act_reshade.setEnabled(game_path is not None)

        # Spielpfad war konfiguriert, ist aber aktuell nicht verfügbar (Laufwerk
        # nicht gemountet / Spiel deinstalliert). Instanz lädt trotzdem, damit der
        # Pfad in den Einstellungen korrigiert werden kann.
        if game_path is None and game_path_str:
            Toast(self, tr("toast.game_path_missing"))

        # 1. Title
        self.setWindowTitle(f"{game_name} \u2013 Anvil Organizer v{APP_VERSION}")
        self._log_panel.add_log("info", f"Instanz geladen: {game_name}")

        # 2. Game panel — real directory contents + executables + icons
        inst_dir = self.instance_manager.instances_path() / instance_name
        self._game_panel.update_game(
            game_name, game_path, plugin, self.icon_manager, short_name,
            instance_dir=inst_dir,
            instance_cover_image=data.get("cover_image", ""),
            instance_cover_color=data.get("cover_color", ""),
        )

        # 3. Instance path
        self._current_instance_path = self.instance_manager.instances_path() / instance_name
        instance_path = self._current_instance_path
        self._current_instance_paths = resolve_instance_paths(instance_path, data)
        instance_paths = self._current_instance_paths
        unavailable_storage = _first_unavailable_storage(instance_paths, data)
        if unavailable_storage is not None:
            self._current_profile_path = None
            self._current_downloads_path = instance_paths.downloads
            self._current_mod_entries = []
            self._mod_index = None
            self._game_panel.set_downloads_path(
                instance_paths.downloads,
                instance_paths.mods,
                instance_paths.profiles,
            )
            self._toolbar.deploy_sep.setVisible(False)
            self._toolbar.deploy_action.setVisible(False)
            self._toolbar.proton_action.setVisible(False)
            self._toolbar.merger_sep.setVisible(False)
            self._toolbar.merger_action.setVisible(False)
            self._toolbar.plugin_sort_sep.setVisible(False)
            self._toolbar.plugin_sort_action.setVisible(False)
            message = tr(
                "toast.storage_path_unavailable",
                path=str(unavailable_storage.path),
            )
            Toast(self, message)
            self._log_panel.add_log("error", message)
            self._status_bar.update_instance(game_name, short_name, store)
            return False
        # Falls in dieser Instanz noch Frameworks unlocked sind, locken.
        if framework_state.has_unlocked(instance_path):
            framework_state.lock_all(instance_path)

        # 4. Downloads tab — zentral aufgelöste Pfade verwenden
        downloads_dir = instance_paths.downloads
        mods_dir = instance_paths.mods

        self._current_downloads_path = downloads_dir
        self._game_panel.set_downloads_path(
            downloads_dir,
            mods_dir,
            instance_paths.profiles,
        )
        self._game_panel.download_manager().set_downloads_dir(downloads_dir)

        # ── BG3-specific path ─────────────────────────────────────
        if short_name == "baldursgate3":
            self._apply_bg3_instance(instance_name, data, plugin, game_path)
            self._status_bar.update_instance(game_name, short_name, store)
            self._restore_ui_state()
            return True

        # ── Standard path (non-BG3) ──────────────────────────────
        # Hide BG3 deploy button, switch to standard mod list
        self._toolbar.deploy_sep.setVisible(False)
        self._toolbar.deploy_action.setVisible(False)
        _BETHESDA_GAMES = {
            "SkyrimSE", "Fallout4", "Fallout3", "FalloutNV",
            "Starfield", "Morrowind", "OblivionRemastered",
        }
        self._toolbar.proton_action.setVisible(
            store == "steam" and short_name in _BETHESDA_GAMES
        )

        # Witcher 3: Script Merger Button einblenden
        is_witcher3 = short_name == "witcher3"
        self._toolbar.merger_sep.setVisible(is_witcher3)
        self._toolbar.merger_action.setVisible(is_witcher3)

        # Native load-order button visibility
        has_plugin_sort = (
            plugin is not None
            and hasattr(plugin, "has_plugins_txt")
            and plugin.has_plugins_txt()
            and getattr(plugin, "SupportsNativePluginSorting", False)
        )
        self._toolbar.plugin_sort_sep.setVisible(has_plugin_sort)
        self._toolbar.plugin_sort_action.setVisible(has_plugin_sort)

        self._mod_list_stack.setCurrentWidget(self._mod_list_view)
        self._bg3_installer = None
        self._mod_list_view.set_extra_drop_extensions(set())

        # Load categories for this instance
        self._category_manager.load(instance_path)
        self._mod_list_view.source_model().set_category_manager(self._category_manager)
        self._mod_list_view._proxy_model.set_category_manager(self._category_manager)

        # Eigene Eigenschaften der Instanz laden
        self._property_manager.load(instance_path)

        # Populate FilterPanel with categories
        self._filter_panel.set_categories(self._category_manager.all_categories())
        self._filter_panel.set_properties(self._property_manager.all_properties())
        self._filter_panel.reset_all()

        # Load Nexus categories cache (lazy API call if expired)
        self._load_nexus_categories(instance_path)

        # Load available profiles from disk
        profiles_dir = instance_paths.profiles
        profiles_dir.mkdir(parents=True, exist_ok=True)

        # Migrate legacy per-profile modlist.txt to global modlist + active_mods.json
        migrate_to_global_modlist(profiles_dir)

        # Migrate modlist order: separators before their mods (v1 → v2)
        migrate_modlist_order(profiles_dir)

        profile_folders = sorted([d.name for d in profiles_dir.iterdir() if d.is_dir() and not d.is_symlink()])
        if not profile_folders:
            (profiles_dir / "Default").mkdir(exist_ok=True)
            profile_folders = ["Default"]

        # Apply saved order if available
        order_file = profiles_dir / "profiles_order.json"
        if order_file.exists():
            try:
                saved_order = json.loads(order_file.read_text())
                # Sortiere nach gespeicherter Reihenfolge, neue Profile ans Ende
                ordered = [p for p in saved_order if p in profile_folders]
                ordered += [p for p in profile_folders if p not in saved_order]
                profile_folders = ordered
            except (json.JSONDecodeError, TypeError):
                pass  # Bei Fehler: Standard-Sortierung beibehalten

        profile_name = data.get("selected_profile", "Default")
        if profile_name not in profile_folders:
            profile_name = profile_folders[0]

        self._profile_bar.set_profiles(profile_folders, active=profile_name)
        self._current_profile_path = profiles_dir / profile_name

        # Load groups for this profile
        self._group_manager.load(self._current_profile_path)
        # Cleanup orphaned group members
        mods_dir = instance_paths.mods
        if mods_dir.is_dir():
            existing_folders = {d.name for d in mods_dir.iterdir() if d.is_dir()}
            self._group_manager.cleanup_orphans(existing_folders)

        # Rebuild mod file index (only re-scans changed mods)
        self._mod_index = ModIndex(instance_path, mods_path=instance_paths.mods)
        self._mod_index.rebuild()
        if plugin is not None:
            plugin.setModIndex(self._mod_index)

        include_ext = self._settings().value("ModList/show_external_mods", True, type=bool)
        self._current_mod_entries = scan_mods_directory(
            instance_path, self._current_profile_path,
            include_external=include_ext,
            mod_index=self._mod_index,
            mods_path=instance_paths.mods,
            profiles_path=instance_paths.profiles,
        )
        # Mark direct-install (framework) mods
        direct_patterns = getattr(plugin, "GameDirectInstallMods", []) if plugin else []
        if direct_patterns:
            lp = [p.lower() for p in direct_patterns]
            for entry in self._current_mod_entries:
                name_lower = (entry.display_name or entry.name).lower()
                if _matches_direct_install(name_lower, lp):
                    entry.is_direct_install = True
        # Von Hand in den Spielordner kopierte Mods anhaengen. Sie laden
        # bei jedem Start mit, stehen aber in keiner Liste -- deshalb
        # gehoeren sie sichtbar dorthin, wo man Mods sucht.
        self._current_mod_entries += self._scan_foreign_entries(plugin, instance_path)

        conflict_data = self._compute_conflict_data()
        # Nur GESPERRTE Frameworks bleiben aus der Liste heraus. Genau dafuer
        # gibt es das Schloss: gesperrt heisst unantastbar. Ist es offen, ist
        # das Framework eine gewoehnliche Mod und muss sich verschieben,
        # umbenennen und loeschen lassen -- vorher war es dauerhaft
        # ausgeblendet und damit gar nicht zu bearbeiten.
        offen = self._unlocked_framework_mods()
        visible_entries = [
            e for e in self._current_mod_entries
            if not e.is_direct_install or e.name in offen
        ]
        mod_rows = [mod_entry_to_row(e, conflict_data, self._group_manager) for e in visible_entries]
        self._mod_list_view.source_model().set_mods(mod_rows)
        # Provide visible entries to proxy for filter logic
        self._mod_list_view._proxy_model.set_mod_entries(visible_entries)
        self._update_active_count()

        # Log mod count
        active_count = sum(1 for e in visible_entries if e.enabled)
        self._log_panel.add_log("info", f"{len(visible_entries)} Mods geladen ({active_count} aktiv)")

        # 5. Mod deployer — mods are deployed on game start, not here
        from anvil.widgets.game_panel import _dlog
        _dlog(f"[APPLY-INSTANCE] Setting instance path: {instance_path}")
        _dlog(f"[APPLY-INSTANCE] Profile: {profile_name}")
        _dlog(f"[APPLY-INSTANCE] Plugin: {getattr(plugin, 'GameName', None)}")
        _dlog(f"[APPLY-INSTANCE] Game path: {game_path}")
        self._game_panel.set_mod_index(self._mod_index)
        self._game_panel.set_instance_path(instance_path, profile_name=profile_name)
        self._sync_separator_deploy_paths()
        if plugin is not None:
            detected = plugin.get_installed_frameworks()
            managed = getattr(plugin, "managed_framework_mods", lambda: {})()
            for fw, installed in detected:
                if not installed:
                    continue
                folders = managed.get(fw.name.lower(), [])
                origin = f".mods/ {folders}" if folders else "game directory (hand-installed)"
                print(f"[FRAMEWORK] {fw.name}: found in {origin}", flush=True)
            fw_list = [self._build_fw_dict(fw, installed) for fw, installed in detected]
            self._mod_list_view.load_frameworks(fw_list)
        else:
            self._mod_list_view.load_frameworks([])

        # 6. Status bar
        self._status_bar.update_instance(game_name, short_name, store)

        # 7. Restore saved column widths / splitter (after data is populated)
        self._restore_ui_state()

        # 8. Mod-Liste Settings anwenden
        s = self._settings()

        # Collapsible asc/dsc flags
        tree = self._mod_list_view._tree
        tree._collapsible_asc = s.value("ModList/collapsible_asc", True, type=bool)
        tree._collapsible_dsc = s.value("ModList/collapsible_dsc", True, type=bool)

        # Collapsed separators wiederherstellen
        if s.value("ModList/collapse_per_profile", False, type=bool) and self._current_profile_path:
            ui_state_file = self._current_profile_path / "ui_state.json"
            if ui_state_file.is_file():
                try:
                    ui_state = json.loads(ui_state_file.read_text())
                    saved_collapsed = ui_state.get("collapsed_separators", [])
                except (json.JSONDecodeError, OSError):
                    saved_collapsed = []
            else:
                saved_collapsed = []
        else:
            saved_collapsed = _ensure_list(s.value("ModList/collapsed_separators", []))

        if isinstance(saved_collapsed, list) and saved_collapsed:
            tree._collapsed_separators = set(str(x) for x in saved_collapsed)
        else:
            tree._collapsed_separators.clear()
        tree._apply_separator_filter()

        # Apply all 10 ModList settings (scrollbar markings, flags, etc.)
        self._apply_modlist_settings()

        # Filter-Chips wiederherstellen
        if s.value("ModList/remember_filters", False, type=bool):
            saved_props = _ensure_list(s.value("ModList/saved_filter_props", []))
            saved_cats = _ensure_list(s.value("ModList/saved_filter_cats", []))
            saved_nexus = _ensure_list(s.value("ModList/saved_filter_nexus_cats", []))
            prop_set = {int(x) for x in saved_props if x != "" and x is not None}
            cat_set = {int(x) for x in saved_cats if x != "" and x is not None}
            nexus_set = {int(x) for x in saved_nexus if x != "" and x is not None}
            if prop_set or cat_set or nexus_set:
                self._filter_panel.restore_state(prop_set, cat_set, nexus_set)

        return True

    def _entry_for_row(self, source_row: int):
        """Resolve a source-model row to the matching ModEntry by folder name.

        Returns None if the row is out of range or no match is found.
        """
        model = self._mod_list_view.source_model()
        if 0 <= source_row < len(model._rows):
            folder = model._rows[source_row].folder_name
            for entry in self._current_mod_entries:
                if entry.name == folder:
                    return entry
        return None

    def _sync_separator_deploy_paths(self) -> None:
        """Extract custom deploy paths from separator ModEntries and sync to GamePanel."""
        paths: dict[str, str] = {}
        for entry in self._current_mod_entries:
            if entry.is_separator and entry.deploy_path:
                paths[entry.name] = entry.deploy_path
        self._game_panel.set_separator_deploy_paths(paths)

    # ── Charakter-Presets ────────────────────────────────────────────

    _PRESET_SEP_KEY = "preset_separator"

    def _preset_separator(self) -> str:
        """Der vom Benutzer benannte Trenner, oder leer.

        Wurde er inzwischen geloescht oder umbenannt, gilt er als nicht
        vorhanden -- dann wird beim naechsten Preset neu gefragt.
        """
        inst = self.instance_manager.current_instance()
        if not inst:
            return ""
        data = self.instance_manager.load_instance(inst) or {}
        name = str(data.get(self._PRESET_SEP_KEY, ""))
        if not name:
            return ""
        vorhanden = any(
            e.name == name for e in self._current_mod_entries if e.is_separator
        )
        return name if vorhanden else ""

    def _ask_preset_separator(self) -> str:
        """Fragt einmalig nach dem Namen und legt den Trenner ganz unten an.

        Ganz unten, weil Presets in der Ladereihenfolge nichts zu suchen
        haben -- sie werden nur als Datei gelesen.
        """
        name, ok = get_text_input(
            self,
            tr("preset.separator_title"),
            tr("preset.separator_prompt"),
            text=tr("preset.separator_default"),
        )
        if not ok or not name.strip():
            return ""

        folder = f"{name.strip()}_separator"
        profiles_dir = _active_instance_paths(self).profiles
        mods_dir = _active_instance_paths(self).mods

        (mods_dir / folder).mkdir(parents=True, exist_ok=True)

        order = read_global_modlist(profiles_dir)
        if folder not in order:
            order.append(folder)
            write_global_modlist(profiles_dir, order)

        if self._current_profile_path:
            aktiv = read_active_mods(self._current_profile_path)
            aktiv.add(folder)
            write_active_mods(self._current_profile_path, aktiv)

        inst = self.instance_manager.current_instance()
        if inst:
            data = self.instance_manager.load_instance(inst) or {}
            data[self._PRESET_SEP_KEY] = folder
            self.instance_manager.save_instance(inst, data)

        return folder

    def _ask_preset_variant(self, dateiname: str, kind) -> str:
        """Fragt, fuer welche Figur das Preset ist. Leer = abgebrochen."""
        from anvil.core.character_presets import FEMALE

        box = QMessageBox(self)
        box.setWindowTitle(tr("preset.variant_title"))
        box.setText(tr("preset.variant_prompt", name=dateiname))
        knoepfe = {}
        for variante in kind.variants:
            schl = tr(f"preset.variant_{variante}")
            knoepfe[box.addButton(schl, QMessageBox.ButtonRole.AcceptRole)] = variante
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        return knoepfe.get(box.clickedButton(), "" if kind.variants else FEMALE)

    def _install_presets_from(self, temp_dir: Path, archive: Path) -> bool:
        """Legt gefundene Presets als eigene Mods an.

        Returns:
            True, wenn das Archiv als Preset-Paket behandelt wurde. Dann
            laeuft der gewoehnliche Installationsweg nicht mehr an.
        """
        from anvil.core import character_presets as cp

        plugin = self._current_plugin
        if plugin is None or self._current_instance_path is None:
            return False

        arten = plugin.get_preset_kinds()
        if not arten:
            return False

        mods_dir = _active_instance_paths(self).mods
        profiles_dir = _active_instance_paths(self).profiles
        angelegt: list[str] = []
        separator = ""

        for kind in arten:
            for datei in cp.find_presets(temp_dir, kind):
                variante = cp.detect_variant(datei, kind)
                if not variante and kind.variants:
                    variante = self._ask_preset_variant(datei.name, kind)
                    if not variante:
                        continue  # abgebrochen, dieses Preset ueberspringen

                if not separator:
                    separator = self._preset_separator() or self._ask_preset_separator()
                    if not separator:
                        return bool(angelegt)

                name = cp.suggest_mod_name(datei, variante, kind)
                if (mods_dir / name).exists():
                    name = f"{name} ({datei.stat().st_size})"
                try:
                    cp.build_mod(datei, mods_dir, name, kind, variante)
                except (OSError, FileExistsError) as exc:
                    self._log_panel.add_log("warn", f"{datei.name}: {exc}")
                    continue

                # Direkt hinter den Trenner, damit alle Presets beisammen
                # bleiben statt ans Listenende zu rutschen.
                order = read_global_modlist(profiles_dir)
                if name not in order:
                    pos = order.index(separator) + 1 if separator in order else len(order)
                    order.insert(pos, name)
                    write_global_modlist(profiles_dir, order)
                if self._current_profile_path:
                    aktiv = read_active_mods(self._current_profile_path)
                    aktiv.add(name)
                    write_active_mods(self._current_profile_path, aktiv)
                angelegt.append(name)

        if not angelegt:
            return False

        self._reload_mod_list()
        self.statusBar().showMessage(
            tr("preset.installed", count=len(angelegt), name=archive.name), 6000,
        )
        return True

    # ── Frameworks: Schloss auf = gewoehnliche Mod ───────────────────

    def _framework_mod_folders(self) -> dict[str, str]:
        """Ordnet jedem verwalteten Mod-Ordner seinen Framework-Namen zu."""
        plugin = self._current_plugin
        if plugin is None:
            return {}
        get_managed = getattr(plugin, "managed_framework_mods", None)
        if not callable(get_managed):
            return {}
        # Einmal abfragen. Der Aufruf laeuft ueber die Dateilisten aller
        # Mods -- in der Schleife waere er pro Framework einmal faellig.
        managed = get_managed()
        zuordnung: dict[str, str] = {}
        for fw in plugin.all_framework_mods():
            for ordner in managed.get(fw.name.lower(), []):
                zuordnung[ordner] = fw.name
        return zuordnung

    def _unlocked_framework_mods(self) -> set[str]:
        """Mod-Ordner, deren Framework offen ist -- nur die kommen in die Liste.

        Bewusst andersherum gedacht: aufgezaehlt wird, was sichtbar sein
        darf. Laesst sich die Zuordnung nicht bilden, bleibt ein Framework
        verborgen. Lieber unsichtbar als versehentlich veraenderbar.

        Ein Framework ohne Eintrag im Zustand gilt als gesperrt. ``get()``
        wuerde dort ``locked=False`` liefern, und ``lock_all()`` fasst nur
        vorhandene Eintraege an -- ArchiveXL, TweakXL und CET haben naemlich
        gar keinen. Die waeren sonst von sich aus offen.
        """
        if self._current_instance_path is None:
            return set()

        # Einmal laden statt pro Framework -- get() liest jedes Mal die Datei.
        zustand = framework_state.load(self._current_instance_path)

        offen: set[str] = set()
        for ordner, fw_name in self._framework_mod_folders().items():
            eintrag = zustand.get(fw_name)
            if isinstance(eintrag, dict) and not eintrag.get("locked", False):
                offen.add(ordner)
        return offen

    def _framework_for_mod(self, mod_name: str) -> str:
        """Framework-Name zu einem Mod-Ordner, oder leer."""
        return self._framework_mod_folders().get(mod_name, "")

    def _sync_framework_active(self, mod_name: str, enabled: bool) -> None:
        """Haelt den Framework-Schalter mit dem Haken in der Liste gleich."""
        if self._current_instance_path is None:
            return
        fw_name = self._framework_for_mod(mod_name)
        if fw_name:
            framework_state.set_entry(
                self._current_instance_path, fw_name, active=enabled,
            )

    # ── Von Hand installierte Mods ───────────────────────────────────

    def _scan_foreign_entries(self, plugin, instance_path) -> list:
        """Sucht Mods, die ohne Anvil im Spielordner gelandet sind.

        Anvil entfernt beim Aufraeumen nur Eigenes -- handkopierte Mods
        bleiben dauerhaft aktiv und tauchen in keiner Liste auf. Genau
        das hat schon einen Fehler tagelang verschleiert.
        """
        from anvil.core import foreign_mods

        mod_dirs = getattr(plugin, "GameModDirs", []) if plugin else []
        if not mod_dirs:
            return []

        game_dir = plugin.gameDirectory() if plugin else None
        if game_dir is None:
            return []

        try:
            funde = foreign_mods.scan_instance(
                game_dir, mod_dirs, instance_path / ".deploy_manifest.json",
            )
        except OSError:
            return []

        if not funde:
            return []

        self._log_panel.add_log(
            "warn",
            tr("foreign.found", count=len(funde)),
        )
        return foreign_mods.to_entries(funde, len(self._current_mod_entries))

    def _toggle_foreign_mod(self, row_data, enabled: bool) -> None:
        """Schaltet eine handkopierte Mod ueber ihren Dateinamen um."""
        from anvil.core import foreign_mods

        eintrag = next(
            (e for e in self._current_mod_entries
             if e.is_foreign and e.name == row_data.folder_name),
            None,
        )
        if eintrag is None or eintrag.foreign_path is None:
            return

        try:
            eintrag.foreign_path = foreign_mods.set_enabled(
                eintrag.foreign_path, enabled,
            )
        except OSError as exc:
            QMessageBox.warning(
                self,
                tr("foreign.title"),
                tr("foreign.rename_failed", error=str(exc)),
            )
            self._reload_mod_list()
            return

        eintrag.enabled = enabled
        self._update_active_count()

    # ── Mod list persistence ─────────────────────────────────────────

    def _write_current_modlist(self) -> None:
        """Write mod order globally and active state to profile.

        - Global modlist.txt in .profiles/ contains load order only
        - Profile-specific active_mods.json contains enabled mod names
        """
        if self._current_profile_path is None or self._current_instance_path is None:
            return

        profiles_dir = _active_instance_paths(self).profiles

        # Fremde Eintraege liegen ausserhalb von .mods/ und werden ueber
        # ihren Dateinamen geschaltet. Kaemen sie hier mit hinein, wuerde
        # Anvil Mods verwalten wollen, die es gar nicht besitzt.
        eigene = [e for e in self._current_mod_entries if not e.is_foreign]

        # 1. Write global load order (all mod names)
        mod_names = [e.name for e in eigene]
        write_global_modlist(profiles_dir, mod_names)

        # 2. Write active mods to current profile
        active_mods = {e.name for e in eigene if e.enabled}
        write_active_mods(self._current_profile_path, active_mods)

    def _on_mod_toggled(self, row: int, enabled: bool) -> None:
        """A mod checkbox was toggled — update entries and persist."""
        model = self._mod_list_view.source_model()
        if not (0 <= row < len(model._rows)):
            return
        row_data = model._rows[row]

        # ── BG3-Weiche: Toggle + Installer-State updaten ──
        if self._bg3_installer is not None:
            uuid = row_data.folder_name  # folder_name = UUID bei BG3
            if not uuid or row_data.is_separator:
                return
            # Nur .pak-Mods: modsettings.lsx aktualisieren
            if not row_data.is_data_override and not row_data.is_framework:
                if enabled:
                    self._bg3_installer.activate_mod(uuid)
                else:
                    self._bg3_installer.deactivate_mod(uuid)
            for entry in self._current_mod_entries:
                if entry.name == uuid:
                    entry.enabled = enabled
                    break
            self._update_active_count()
            # Recompute conflicts (enabled state changed → conflicts may differ)
            conflict_data = self._compute_conflict_data()
            for mod_row in model._rows:
                mod_row.conflicts = conflict_data.get(mod_row.folder_name, "")
            model.dataChanged.emit(
                model.index(0, 0),
                model.index(model.rowCount() - 1, model.columnCount() - 1),
            )
            return

        # ── Fremde Mods: nicht speichern, sondern umbenennen ──
        if getattr(row_data, "is_foreign", False):
            self._toggle_foreign_mod(row_data, enabled)
            return

        # ── Standard path ──
        # Find matching entry by unique folder name
        for entry in self._current_mod_entries:
            if entry.name == row_data.folder_name:
                entry.enabled = enabled
                break

        # Frameworks werden unabhaengig von active_mods ausgerollt -- ueber
        # sie entscheidet allein der Schalter im Framework-Zustand. Ohne
        # diesen Abgleich waere der Haken in der Liste wirkungslos.
        self._sync_framework_active(row_data.folder_name, enabled)

        self._write_current_modlist()
        self._update_active_count()
        self._schedule_redeploy()
        # ── Konflikte neu berechnen ──
        conflict_data = self._compute_conflict_data()
        for mod_row in model._rows:
            folder = mod_row.folder_name
            mod_row.conflicts = conflict_data.get(folder, "")
        model.dataChanged.emit(
            model.index(0, 0),
            model.index(model.rowCount() - 1, model.columnCount() - 1),
        )

    def _on_mods_reordered(self) -> None:
        """Mods were reordered via drag & drop — sync entries and persist."""
        model = self._mod_list_view.source_model()

        # ── BG3-Weiche: Reihenfolge über Installer speichern ──
        if self._bg3_installer is not None:
            # Only include ACTIVE mod UUIDs — inactive mods must stay out
            # of mod_order, otherwise their .pak in .disabled/ causes BG3
            # to reset modsettings.lsx (can't find referenced paks).
            bg3_active_uuids = {
                m["uuid"].lower()
                for m in (self._bg3_installer.get_mod_list().get("mods", []))
                if m.get("enabled", False)
            }
            uuid_order = [
                r.folder_name for r in model._rows
                if not r.is_separator and r.folder_name
                and r.folder_name.lower() in bg3_active_uuids
            ]
            self._bg3_installer.reorder_mods(uuid_order)
            # Save separator positions
            self._bg3_save_separators(model)
            # Rebuild _current_mod_entries in new order (needed for correct
            # conflict winners — ConflictScanner uses list order as priority)
            new_entries = []
            for row_data in model._rows:
                for entry in self._current_mod_entries:
                    if entry.name == row_data.folder_name and entry not in new_entries:
                        entry.priority = len(new_entries)
                        new_entries.append(entry)
                        break
            self._current_mod_entries = new_entries
            # Recompute conflicts (priority changed → winner may differ)
            conflict_data = self._compute_conflict_data()
            for row_data in model._rows:
                row_data.conflicts = conflict_data.get(row_data.folder_name, "")
            model.dataChanged.emit(
                model.index(0, 0),
                model.index(model.rowCount() - 1, model.columnCount() - 1),
            )
            return

        # ── Standard path ──
        # Clear stale conflict highlights (row indices changed)
        model.set_conflict_highlight(set(), set())
        # Rebuild visible entries from the model's new order
        new_entries = []
        for i in range(model.rowCount()):
            row_data = model._rows[i]
            # Find matching entry by unique folder name
            for entry in self._current_mod_entries:
                if entry.name == row_data.folder_name and entry not in new_entries:
                    entry.priority = i
                    new_entries.append(entry)
                    break
        # Preserve framework/direct-install mods (not in model)
        framework_entries = [e for e in self._current_mod_entries if e.is_direct_install]
        self._current_mod_entries = new_entries + framework_entries
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
        # Check group consistency after DnD
        self._check_group_consistency_after_reorder(model)
        self._mod_list_view._tree._apply_separator_filter()
        self._schedule_redeploy()

    def _check_group_consistency_after_reorder(self, model) -> None:
        """After DnD, check if any group members were moved out of their group.

        If a single member is no longer contiguous with its group, remove it.
        If a member crossed a separator boundary, remove it from the group.
        """
        changed = False
        for gname in list(self._group_manager.all_groups().keys()):
            members = self._group_manager.get_members(gname)
            if not members:
                continue

            # Find rows for each member
            member_rows: dict[str, int] = {}
            for i, r in enumerate(model._rows):
                if r.folder_name in members:
                    member_rows[r.folder_name] = i

            # Find separator for each member
            member_seps: dict[str, str] = {}
            for folder_name, row_idx in member_rows.items():
                sep = ""
                for j in range(row_idx, -1, -1):
                    if j < len(model._rows) and model._rows[j].is_separator:
                        sep = model._rows[j].folder_name
                        break
                member_seps[folder_name] = sep

            # All members must be in the same separator
            seps = set(member_seps.values())
            if len(seps) > 1:
                from collections import Counter
                sep_counts = Counter(member_seps.values())
                main_sep = sep_counts.most_common(1)[0][0]
                for folder_name, sep in member_seps.items():
                    if sep != main_sep:
                        self._group_manager.remove_member(folder_name)
                        changed = True

            # Check contiguity
            rows_list = sorted(member_rows.values())
            if len(rows_list) >= 2:
                expected_span = rows_list[-1] - rows_list[0] + 1
                if expected_span != len(rows_list):
                    blocks: list[list[int]] = []
                    current_block = [rows_list[0]]
                    for ri in range(1, len(rows_list)):
                        if rows_list[ri] == current_block[-1] + 1:
                            current_block.append(rows_list[ri])
                        else:
                            blocks.append(current_block)
                            current_block = [rows_list[ri]]
                    blocks.append(current_block)

                    largest = max(blocks, key=len)
                    largest_set = set(largest)

                    row_to_folder = {v: k for k, v in member_rows.items()}
                    for row_idx in rows_list:
                        if row_idx not in largest_set:
                            folder = row_to_folder.get(row_idx, "")
                            if folder:
                                self._group_manager.remove_member(folder)
                                changed = True

        if changed:
            conflict_data = self._compute_conflict_data()
            for i, r in enumerate(model._rows):
                gname = self._group_manager.get_group_for_mod(r.folder_name)
                r.group_name = gname
                r.is_group_head = bool(gname and self._group_manager.is_group_head(r.folder_name))
            model.dataChanged.emit(
                model.index(0, 0),
                model.index(model.rowCount() - 1, model.columnCount() - 1),
            )

    def _update_active_count(self) -> None:
        """Update the active mod counter in the profile bar."""
        mods = [e for e in self._current_mod_entries if not e.is_separator]
        active = sum(1 for e in mods if e.enabled)
        self._profile_bar.update_active_count(active, len(mods))
        bar_value = getattr(self._toolbar, "active_label", None)
        if bar_value is not None:
            bar_value.setText(f"{active} / {len(mods)}")

    # ── Auto-redeploy helpers ────────────────────────────────────────

    def _schedule_redeploy(self) -> None:
        """Schedule the debounced cleanup after a mod list change (500ms)."""
        if not self._current_instance_path:
            return
        self.statusBar().showMessage(tr("status.pending_launch"), 3000)
        self._redeploy_timer.start()

    def _do_redeploy(self) -> bool:
        """Clean up any leftover deployment.

        Mods go into the game directory on game start, so nothing is
        deployed here — this only removes what an earlier run left
        behind.  The exception is keep-deployed: there the game directory
        has to follow every change right away, because the user may never
        launch through Anvil again.
        """
        self._redeploy_timer.stop()
        if not self._current_instance_path:
            return False
        # BG3: kein Symlink-Deploy — Auto-Deploy läuft über den Installer
        if self._bg3_installer is not None:
            return True
        keep = self.keeps_mods_deployed()
        if not keep and not self._game_panel.has_deployment():
            return True
        if self._game_running or self._game_panel.is_game_running():
            print("[PURGE] game may still be running — leftover kept",
                  flush=True)
            return True
        print("[PURGE] Cleaning up leftover deployment", flush=True)
        purge_result = self._game_panel.silent_purge()
        if keep and (purge_result is None
                     or getattr(purge_result, "success", False)):
            print("[PURGE] keep-deployed is on — putting the mods back out",
                  flush=True)
            deploy_result = self._game_panel.silent_deploy()
            if deploy_result is not None and not getattr(
                    deploy_result, "success", False):
                errors = getattr(deploy_result, "errors", [])
                QMessageBox.warning(
                    self,
                    tr("error.deploy_failed_title"),
                    tr("error.deploy_failed_message",
                       details="\n".join(str(e) for e in errors[:5])),
                )
                return False
        if purge_result is not None and not getattr(purge_result, "success", False):
            errors = getattr(purge_result, "errors", [])
            details = "\n".join(str(error) for error in errors[:5])
            QMessageBox.warning(
                self,
                tr("error.deploy_failed_title"),
                tr("error.deploy_failed_message", details=details),
            )
            return False
        return True

    def _on_filter_changed(self) -> None:
        """Mod search or FilterPanel chip changed — update proxy filter."""
        text = self._mod_search.text().strip()
        # BG3 nutzt jetzt das normale ModListView — kein Sonderpfad nötig
        proxy = self._mod_list_view._proxy_model
        proxy.set_filter_state(
            text.lower(),
            self._filter_panel.active_property_ids(),
            self._filter_panel.active_category_ids(),
            self._filter_panel.active_nexus_category_ids(),
        )

    def _build_bg3_file_lists(self) -> dict[str, list[dict]]:
        """Read file lists from all BG3 .pak files.

        Returns:
            Dict: UUID -> [{"rel": "path", "size": N}, ...]
            Paths are lowercase-normalized (BG3 runs under Proton/Windows).
        """
        result: dict[str, list[dict]] = {}
        if self._bg3_installer is None or self._bg3_installer._mods_path is None:
            return result
        mods_path = self._bg3_installer._mods_path
        if not mods_path.is_dir():
            return result

        reader = LSPKReader()
        for pak in mods_path.glob("*.pak"):
            metadata, file_list = reader.read_pak_full(pak)
            if metadata is None or not metadata.get("uuid"):
                continue
            uuid = metadata["uuid"].lower()
            # Normalize to lowercase for case-insensitive comparison
            normalized = [
                {"rel": f["rel"].lower(), "size": f["size"]}
                for f in file_list
            ]
            result[uuid] = normalized
        return result

    def _run_conflict_scan(self) -> dict:
        """Gemeinsamer roher Konflikt-Scan (BG3 + normale Spiele).

        Liefert das rohe ConflictScanner-Ergebnis (``conflicts``/``ignored``)
        oder ``{}`` wenn nichts zu scannen ist.
        """
        if not self._current_mod_entries:
            return {}

        # BG3: use pak_file_lists instead of filesystem scan
        if self._bg3_installer is not None:
            pak_file_lists = self._build_bg3_file_lists()
            all_mods = [
                {"name": e.name, "path": ""}
                for e in self._current_mod_entries
                if e.enabled and not e.is_separator and not e.is_data_override
            ]
            if not all_mods:
                return {}
            return ConflictScanner().scan_conflicts(
                all_mods, self._current_plugin, pak_file_lists=pak_file_lists,
            )

        # Regular games: filesystem-based scan
        if not self._current_instance_path:
            return {}
        all_mods = [
            {"name": e.name, "path": str(_active_instance_paths(self).mods / e.name)}
            for e in self._current_mod_entries if e.enabled and not e.is_foreign
        ]
        if not all_mods:
            return {}
        return ConflictScanner().scan_conflicts(
            all_mods, self._current_plugin, mod_index=self._mod_index,
        )

    def collect_diagnostics_conflicts(self) -> dict:
        """Für den Diagnose-Tab: Datei-Konflikte der aktiven Mods (read-only).

        Liefert {available: bool, conflicts: [{file, mods, winner}, ...]}.
        """
        if not self._current_mod_entries or self._current_plugin is None:
            return {"available": False, "conflicts": []}
        try:
            result = self._run_conflict_scan()
        except Exception:  # noqa: BLE001 — Diagnose darf nie crashen
            return {"available": False, "conflicts": []}
        return {"available": True, "conflicts": result.get("conflicts", []) if result else []}

    def _push_virtual_files(self, scan_result: dict) -> None:
        """Feed the Data tab what the mods would deploy.

        BG3 keeps its own installer view — it is left untouched.
        """
        if self._bg3_installer is not None:
            return
        setter = getattr(self._game_panel, "set_virtual_files", None)
        if callable(setter):
            setter((scan_result or {}).get("file_owners", {}))

    def _compute_conflict_data(self) -> dict:
        """Run ConflictScanner and return per-mod conflict info.

        Returns a dict mapping mod folder name to a conflict info dict:
        ``{"type": "win"|"lose"|"both", "wins": N, "losses": N,
           "win_mods": N, "lose_mods": N}``
        """
        result = self._run_conflict_scan()
        self._push_virtual_files(result)
        if not result:
            return {}

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
                "win_mods_list": list(info["win_mods"]),
                "lose_mods_list": list(info["lose_mods"]),
            }
        return result_data

    # ── Mod installation ─────────────────────────────────────────────

    def _on_install_mod(self) -> None:
        """Menu: Datei → Mod installieren..."""
        if not self._current_instance_path:
            QMessageBox.warning(self, tr("dialog.no_instance_title"), tr("dialog.no_instance_message"))
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

        # Pre-filter: detect framework mods before normal/BG3 install
        remaining = [f for f in files if not self._try_install_as_framework(Path(f))]
        if not remaining:
            self._game_panel.refresh_downloads()
            return

        # BG3: use BG3ModInstaller
        if self._bg3_installer is not None:
            self._on_bg3_archives_dropped(remaining)
            return

        self._install_archives([Path(f) for f in remaining])
        self._game_panel.refresh_downloads()

    def _on_archives_dropped(self, paths: list) -> None:
        """Handle archives dropped onto the mod list."""
        if not self._current_instance_path:
            return
        # Pre-filter: detect framework mods before normal/BG3 install
        remaining = [p for p in paths if not self._try_install_as_framework(Path(p))]
        if not remaining:
            self._game_panel.refresh_downloads()
            return
        if self._bg3_installer is not None:
            self._on_bg3_archives_dropped(remaining)
            self._game_panel.refresh_downloads()
            return
        self._install_archives([Path(p) for p in remaining])
        self._game_panel.refresh_downloads()

    def _on_archives_dropped_at(self, paths: list, target_row: int) -> None:
        """Handle archives dropped onto the mod list at a specific position."""
        if not self._current_instance_path:
            return
        # Pre-filter: detect framework mods before normal/BG3 install
        remaining = [p for p in paths if not self._try_install_as_framework(Path(p))]
        if not remaining:
            self._game_panel.refresh_downloads()
            return
        if self._bg3_installer is not None:
            self._on_bg3_archives_dropped(remaining, insert_at=target_row)
            self._game_panel.refresh_downloads()
            return
        self._install_archives([Path(p) for p in remaining], insert_at=target_row)
        self._game_panel.refresh_downloads()

    def _log_game_dir_state(self, phase: str) -> None:
        """Write a headcount of the game directory to the log.

        Makes the deploy-on-launch cycle traceable: empty before the
        game starts, filled while it runs, empty again afterwards.
        """
        game_path = self._current_game_path
        if game_path is None or not game_path.is_dir():
            print(f"[LAUNCH] {phase}: no game directory", flush=True)
            return
        links = files = 0
        try:
            for root, _dirs, names in os.walk(str(game_path)):
                for name in names:
                    if (Path(root) / name).is_symlink():
                        links += 1
                    else:
                        files += 1
        except OSError as exc:
            print(f"[LAUNCH] {phase}: cannot scan: {exc}", flush=True)
            return
        print(
            f"[LAUNCH] {phase}: {links} symlink(s), {files} real file(s) "
            f"in {game_path}",
            flush=True,
        )

    def _predeploy_for_launch(self, reason: str) -> bool | None:
        """Relock frameworks and purge/deploy for a launch.

        Returns True on success, False if the deploy failed, and None if
        the launch was refused because a game is running — the caller
        must not show a deploy error on top of the message already shown.
        """
        self._redeploy_timer.stop()
        self._last_deploy_errors: list[str] = []
        forced = self._game_panel.take_forced_launch()
        running = self._game_running or self._game_panel.game_state() == GAME_RUNNING
        if running and not forced:
            # Purge + Deploy würden dem laufenden Spiel die Dateien wegziehen.
            print("[LAUNCH] a game is still running — refused", flush=True)
            QMessageBox.warning(
                self, tr("game_panel.start"),
                tr("error.game_already_running"),
            )
            return None
        if self._current_instance_path:
            print(f"[LAUNCH] pre-launch deploy, reason={reason}", flush=True)
            self._log_game_dir_state("before deploy")
            # Vor dem Start: alle Frameworks dieser Instanz locken
            self._auto_relock_instance(self._current_instance_path, reason)
            print("[PURGE] Pre-launch purge", flush=True)
            purge_result = self._game_panel.silent_purge()
            if purge_result is not None and not getattr(purge_result, "success", False):
                errors = getattr(purge_result, "errors", [])
                print(f"[LAUNCH] pre-launch purge FAILED: {errors[:5]}", flush=True)
                self._last_deploy_errors = list(errors)[:3]
                return False
            print("[DEPLOY] Pre-launch full deploy (with BA2)", flush=True)
            self._sync_separator_deploy_paths()
            deploy_result = self._game_panel.silent_deploy()
            if deploy_result is not None:
                print(
                    f"[LAUNCH] deploy result: success="
                    f"{getattr(deploy_result, 'success', None)}, "
                    f"links={getattr(deploy_result, 'links_created', 0)}, "
                    f"copies={getattr(deploy_result, 'files_copied', 0)}, "
                    f"errors={len(getattr(deploy_result, 'errors', []))}",
                    flush=True,
                )
                for err in getattr(deploy_result, "errors", [])[:5]:
                    print(f"[LAUNCH]   ERROR: {err}", flush=True)
            if deploy_result is not None and not getattr(deploy_result, "success", False):
                self._last_deploy_errors = list(getattr(deploy_result, "errors", []))[:3]
                return False
            self._log_game_dir_state("after deploy")
        return True

    def _report_predeploy_failure(self, result: bool | None) -> None:
        """Sagen, warum der Start nicht zustande kam.

        Bei None ist der Grund schon gemeldet (Spiel laeuft noch).
        """
        if result is None:
            return
        QMessageBox.warning(
            self,
            tr("error.deploy_failed_title"),
            tr("error.deploy_failed_message",
               details="\n".join(self._last_deploy_errors)),
        )

    def _on_start_game(self, binary_path: str, working_dir: str) -> None:
        """Launch the selected game executable."""
        result = self._predeploy_for_launch("game_start")
        if not result:
            self._report_predeploy_failure(result)
            return
        success, pid = True, -1
        try:
            proc = host_popen(
                [binary_path],
                cwd=working_dir,
                env=clean_subprocess_env(),
            )
            pid = proc.pid
        except OSError:
            success = False
        if not success:
            QMessageBox.warning(
                self, tr("error.start_failed_title"),
                tr("error.start_failed_message", path=binary_path),
            )
            return
        self._game_panel.notify_game_started(pid)

    def _on_custom_tool_start(
        self, exe_path: str, args: list, working_dir: str, use_proton: bool
    ) -> None:
        """Launch a user-defined program — mods are deployed first, like a game start.

        Bewusst KEIN game_started/UI-Lock: eigene Tools (xEdit, BodySlide, LOOT) laufen
        neben Anvil, man soll währenddessen weiterarbeiten können. Nur das Spiel sperrt
        die UI.
        """
        if not self._game_panel.confirm_start_while_running():
            return
        predeploy = self._predeploy_for_launch("custom_tool_start")
        if not predeploy:
            self._report_predeploy_failure(predeploy)
            return
        if use_proton:
            self._game_panel.run_with_proton(exe_path, list(args), working_dir or None)
            return
        # Direktstart ohne Proton (native Linux-Tools/Skripte), inklusive Argumente
        exe = Path(exe_path)
        if not exe_path or not exe.is_file():
            QMessageBox.warning(
                self, tr("error.start_failed_title"),
                tr("error.start_failed_message", path=exe_path),
            )
            return
        try:
            host_popen(
                [exe_path, *args],
                cwd=working_dir or str(exe.parent),
                env=clean_subprocess_env(),
            )
        except OSError:
            QMessageBox.warning(
                self, tr("error.start_failed_title"),
                tr("error.start_failed_message", path=exe_path),
            )

    def _on_game_started(self, game_name: str, pid: int) -> None:
        """Lock the UI when a game has been started."""
        msg = tr("status.game_started", name=game_name)
        self.statusBar().showMessage(msg, 5000)
        self._lock_ui(game_name)

    # ── Game Running Lock ─────────────────────────────────────────────

    def _lock_ui(self, game_name: str) -> None:
        """Disable the UI while a game is running."""
        self._game_running = True
        self._lock_label.setText(tr("status.game_lock.running_label", name=game_name))
        self._lock_overlay.setVisible(True)
        self._lock_overlay.raise_()
        self._center_lock_overlay()
        self._splitter.setEnabled(False)
        self._log_container.setEnabled(False)
        self._toolbar.setEnabled(False)
        self.menuBar().setEnabled(False)

    def _on_unlock_clicked(self) -> None:
        """Unlock button: ask before removing the deployment.

        Anvil cannot always tell whether the game is still running, so the
        decision belongs to the user rather than to a guess — and it is
        carried out as given, without a second opinion from the lookup.
        """
        if not self._game_panel.has_deployment():
            print("[LAUNCH] unlock: nothing deployed", flush=True)
            self._unlock_ui(False)
            return
        # Der Dialog dreht eine eigene Event-Schleife: ohne die Sperre kann
        # game_stopped dazwischenfunken und schon aufraeumen, waehrend der
        # Nutzer noch ueberlegt.
        self._unlock_pending = True
        try:
            answer = QMessageBox.question(
                self,
                tr("dialog.unlock_purge_title"),
                tr("dialog.unlock_purge_text"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
        finally:
            self._unlock_pending = False
        if answer != QMessageBox.StandardButton.Yes:
            self._unlock_ui(False)
            return
        self._game_running = False
        print("[LAUNCH] unlock: user asked to remove the deployment",
              flush=True)
        self._purge_after_game()
        self._game_panel.clear_watch_target()
        self._release_ui_lock()

    def _unlock_ui(self, stopped: bool = True) -> None:
        """Re-enable the UI after a game has stopped or user clicks Unlock.

        Never removes anything while the game is still running — pulling
        the mods out from under a running game crashes it.  ``stopped``
        is False when the game state could not be established; leftovers
        are then cleaned up on the next game start.
        """
        if self._unlock_pending:
            # Der Nutzer entscheidet gerade selbst — seiner Antwort nicht
            # vorgreifen.
            return
        self._game_running = False
        if not stopped:
            print("[LAUNCH] game state unknown — keeping the deployment",
                  flush=True)
        elif self._game_panel.is_game_running():
            print("[LAUNCH] unlock requested, but the game is still "
                  "running — keeping the deployment", flush=True)
        else:
            print("[LAUNCH] game stopped — cleaning up", flush=True)
            self._purge_after_game()
            self._game_panel.clear_watch_target()
        self._release_ui_lock()

    def _refuse_while_game_runs(self, title: str) -> bool:
        """Block deletions in the game directory while the game is up."""
        if not (self._game_running or self._game_panel.is_game_running()):
            return False
        QMessageBox.warning(self, title, tr("error.game_already_running"))
        return True

    def keeps_mods_deployed(self) -> bool:
        """Whether the current instance leaves its mods in the game directory.

        Off by default, and only ever on for one instance: switching games
        lifts it again (see ``_lift_keep_deployed``).
        """
        name = self.instance_manager.current_instance()
        if not name:
            return False
        data = self.instance_manager.load_instance(name) or {}
        return str(data.get("keep_mods_deployed", "false")).lower() in ("true", "1")

    def set_keeps_mods_deployed(self, enabled: bool) -> None:
        """Write the flag back to the current instance."""
        name = self.instance_manager.current_instance()
        if not name:
            return
        data = self.instance_manager.load_instance(name)
        if not data:
            return
        data["keep_mods_deployed"] = bool(enabled)
        self.instance_manager.save_instance(name, data)

    def _apply_keep_deployed_change(self, was_keeping: bool) -> None:
        """Act on the keep-deployed switch right after the settings close.

        Switching it on has to put the mods out now and switching it off has
        to take them back — otherwise the game directory would only catch up
        on the next launch, which in this mode may never come.
        """
        keeping = self.keeps_mods_deployed()
        if keeping == was_keeping:
            return
        if self._game_running or self._game_panel.is_game_running():
            print("[PURGE] keep-deployed changed while the game runs — "
                  "game directory left alone", flush=True)
            return

        if keeping:
            answer = QMessageBox.warning(
                self,
                tr("game_panel.keep_on_title"),
                tr("game_panel.keep_on_text"),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Ok:
                self.set_keeps_mods_deployed(False)
                print("[PURGE] keep-deployed cancelled by user", flush=True)
                return
            print("[PURGE] keep-deployed switched on — deploying now", flush=True)
            if self._game_panel.has_deployment():
                self._game_panel.silent_purge()
            self._game_panel.silent_deploy()
            return

        print("[PURGE] keep-deployed switched off — cleaning up", flush=True)
        self._game_panel.silent_purge()

    def _lift_keep_deployed(self, instance_name: str) -> None:
        """Turn the flag off for the instance being left behind and say so.

        Anvil manages one game at a time; mods left in a game directory it no
        longer watches would go stale without anybody noticing.
        """
        data = self.instance_manager.load_instance(instance_name)
        if not data:
            return
        if str(data.get("keep_mods_deployed", "false")).lower() not in ("true", "1"):
            return
        data["keep_mods_deployed"] = False
        self.instance_manager.save_instance(instance_name, data)
        print(f"[PURGE] keep-deployed lifted for {instance_name}", flush=True)
        game = data.get("game_name") or instance_name
        # The switch is still running and the overlay is up — the message
        # waits for the new instance to be on screen.
        QTimer.singleShot(0, lambda: QMessageBox.information(
            self,
            tr("game_panel.keep_lifted_title"),
            tr("game_panel.keep_lifted_text", game=game),
        ))

    def _purge_after_game(self) -> None:
        """Remove the deployment and log what went out."""
        if self.keeps_mods_deployed():
            print("[LAUNCH] keep-deployed is on — mods stay in the game dir",
                  flush=True)
            return
        self._log_game_dir_state("before cleanup")
        purge_result = self._game_panel.silent_purge()
        if purge_result is not None:
            print(
                f"[LAUNCH] purge result: success="
                f"{getattr(purge_result, 'success', None)}, "
                f"removed={getattr(purge_result, 'links_removed', 0)}, "
                f"errors={len(getattr(purge_result, 'errors', []))}",
                flush=True,
            )
            for err in getattr(purge_result, "errors", [])[:5]:
                print(f"[LAUNCH]   ERROR: {err}", flush=True)
        self._log_game_dir_state("after cleanup")

    def _release_ui_lock(self) -> None:
        """Hide the lock overlay and hand the UI back to the user."""
        self._lock_overlay.setVisible(False)
        self._splitter.setEnabled(True)
        self._log_container.setEnabled(True)
        self._toolbar.setEnabled(True)
        self.menuBar().setEnabled(True)

    def _center_lock_overlay(self) -> None:
        """Center the lock overlay on the central widget."""
        cw = self.centralWidget()
        if cw is None:
            return
        x = (cw.width() - self._lock_overlay.width()) // 2
        y = (cw.height() - self._lock_overlay.height()) // 2
        self._lock_overlay.move(x, y)

    def _on_downloads_install(self, paths: list) -> None:
        """Handle install request from the Downloads tab."""
        if not self._current_instance_path:
            return
        # BG3 uses its own installer
        if self._bg3_installer is not None:
            self._on_bg3_archives_dropped(paths)
            self._game_panel.refresh_downloads()
            return
        self._install_archives([Path(p) for p in paths])
        self._game_panel.refresh_downloads()

    def _auto_install_companion_frameworks(
        self,
        installed_name: str,
        game_path: "Path",
        frameworks_installed: list[str],
    ) -> None:
        """Auto-install bundled companion frameworks (e.g. F4SE Proton Shim when F4SE is installed).

        Checks all FrameworkMods for the current game and installs any
        companion whose ``required_by`` list contains *installed_name*.
        The source files come from ``anvil/data/shims/<GameShortName>/``.
        """
        if self._current_plugin is None:
            return

        from anvil.core.resource_path import get_anvil_base
        short_name = getattr(self._current_plugin, "GameShortName", "").lower()
        shim_dir = get_anvil_base() / "data" / "shims" / short_name

        for companion in self._current_plugin.all_framework_mods():
            if installed_name not in companion.required_by:
                continue
            # Already there?  Covers both the managed .mods/ copy and a
            # hand-installed one in the game directory.
            already = any(
                fw.name == companion.name and installed
                for fw, installed in self._current_plugin.get_installed_frameworks()
            )
            if already:
                continue
            # Copy bundled shim files to game_path
            copied = []
            for fname in companion.detect_installed:
                src = shim_dir / fname
                if src.is_file():
                    import shutil
                    shutil.copy2(src, game_path / fname)
                    copied.append(fname)
            if copied:
                frameworks_installed.append(companion.name)
                print(
                    f"[auto-companion] installed {companion.name}: {copied}",
                    flush=True,
                )

    def _try_install_as_framework(self, archive: Path) -> bool:
        """Check if an archive is a framework mod and install it if confirmed.

        Returns True if the archive was handled as a framework, False otherwise.
        Used as a pre-filter before the BG3/normal install paths.
        """
        if self._current_plugin is None or not self._current_game_path:
            return False

        flatten = getattr(self._current_plugin, "GameFlattenArchive", True)
        se_dir = getattr(self._current_plugin, "ScriptExtenderDir", "")
        installer = ModInstaller(
            self._current_instance_path, flatten=flatten,
            script_extender_dir=se_dir,
            mods_path=_active_instance_paths(self).mods,
        )
        temp_dir = installer.extract_to_temp(archive)
        if temp_dir is None:
            return False

        file_list = [
            str(f.relative_to(temp_dir))
            for f in temp_dir.rglob("*") if f.is_file()
        ]

        # 1. Known framework?
        fw = self._current_plugin.is_framework_mod(file_list)
        if fw is not None:
            game_path = self._current_game_path
            already_installed = any(
                _path_matches(game_path, dp) for dp in fw.detect_installed
            )
            if already_installed:
                answer = QMessageBox.question(
                    self,
                    tr("status.framework_update_title"),
                    tr("status.framework_update_message", name=fw.name),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return True  # handled (user declined update)
            result = installer.install_framework(
                temp_dir, fw, game_path, archive_path=archive,
            )
            if result:
                self.statusBar().showMessage(
                    tr("status.framework_installed", names=result["name"]), 5000,
                )
                self._reload_mod_list()
            return True

        # Not a framework
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False

    def _install_archives(self, archives: list[Path], insert_at: int | None = None,
                          reinstall_mod_path: Path | None = None) -> None:
        """Install one or more archives as mods.

        Duplikat-Pruefung:
        - Name berechnen, pruefen ob .mods/{name} existiert
        - NEIN → direkt installieren, kein Dialog
        - JA  → QuickInstallDialog → QueryOverwriteDialog falls nötig

        Framework mods are detected and installed directly into the game directory.
        """
        flatten = getattr(self._current_plugin, "GameFlattenArchive", True) if self._current_plugin else True
        se_dir = getattr(self._current_plugin, "ScriptExtenderDir", "") if self._current_plugin else ""
        installer = ModInstaller(
            self._current_instance_path,
            flatten=flatten,
            script_extender_dir=se_dir,
            mods_path=_active_instance_paths(self).mods,
        )
        installed = []
        frameworks_installed = []
        _prev_inserted_name: str | None = None  # Track last inserted mod for multi-DnD

        for archive in archives:
            print(f"DEBUG _install_archives: archive={archive.name}", flush=True)
            # 1. Extract to temp
            temp_dir = installer.extract_to_temp(archive)
            if temp_dir is None:
                self.statusBar().showMessage(
                    tr("error.extract_failed", name=archive.name), 8000,
                )
                continue
            print(f"DEBUG _install_archives: temp_dir={temp_dir}", flush=True)

            # 1b. Charakter-Presets: keine gewoehnliche Mod, sondern eine
            # Einstellungsdatei. Aus jeder wird eine eigene kleine Mod mit
            # dem Zielpfad im Ordner -- dann traegt der normale Deploy-Weg
            # sie an die richtige Stelle, und ein Update des Frameworks
            # wirft sie nicht weg.
            if self._install_presets_from(temp_dir, archive):
                shutil.rmtree(temp_dir, ignore_errors=True)
                continue

            # 2. Check if this is a framework mod
            if self._current_plugin is not None:
                file_list = [
                    str(f.relative_to(temp_dir))
                    for f in temp_dir.rglob("*") if f.is_file()
                ]
                print(f"DEBUG _install_archives: file_list={file_list[:10]}", flush=True)
                fw = self._current_plugin.is_framework_mod(file_list)
                print(f"DEBUG _install_archives: fw={fw}", flush=True)
                if fw is not None:
                    game_path = self._current_game_path
                    print(f"DEBUG _install_archives: game_path={game_path}", flush=True)
                    if game_path:
                        # Check if framework is already installed
                        already_installed = any(
                            _path_matches(game_path, dp)
                            for dp in fw.detect_installed
                        )
                        if already_installed:
                            answer = QMessageBox.question(
                                self,
                                tr("status.framework_update_title"),
                                tr("status.framework_update_message", name=fw.name),
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.Yes,
                            )
                            if answer != QMessageBox.StandardButton.Yes:
                                shutil.rmtree(temp_dir, ignore_errors=True)
                                continue
                        result = installer.install_framework(
                            temp_dir, fw, game_path, archive_path=archive,
                        )
                        if result:
                            frameworks_installed.append(result["name"])
                            self._auto_install_companion_frameworks(
                                result["name"], game_path, frameworks_installed
                            )
                        continue
                    else:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        continue

            # 2b. Heuristic: detect possible unknown framework
            if self._current_plugin is not None and self._current_game_path:
                detection = self._current_plugin.detect_possible_framework(file_list)
                if detection is not None:
                    from anvil.widgets.framework_detect_dialog import FrameworkDetectDialog
                    dlg = FrameworkDetectDialog(
                        self,
                        archive_name=archive.stem,
                        score=detection["score"],
                        reasons=detection["reasons"],
                        detected_files=detection["detected_files"],
                    )
                    _center_on_parent(dlg)
                    if dlg.exec() == QDialog.DialogCode.Accepted:
                        fw_name = dlg.framework_name()
                        fw_target = dlg.framework_target()
                        fw_detect = dlg.framework_detect_installed()
                        # Build pattern from detected files for future recognition
                        fw_pattern = [
                            Path(f).name for f in detection["detected_files"]
                        ]
                        # Create temporary FrameworkMod for installation
                        from anvil.plugins.framework_mod import FrameworkMod
                        new_fw = FrameworkMod(
                            name=fw_name,
                            pattern=fw_pattern,
                            target=fw_target,
                            description="",
                            detect_installed=fw_detect or fw_pattern,
                        )
                        game_path = self._current_game_path
                        result = installer.install_framework(
                            temp_dir, new_fw, game_path,
                            archive_path=archive,
                        )
                        if result:
                            frameworks_installed.append(result["name"])
                            # Persist to plugin JSON
                            self._current_plugin.save_framework_to_json(
                                fw_name, fw_target,
                                fw_detect or fw_pattern,
                                fw_pattern,
                            )
                        continue
                    # User declined — install as normal mod (fall through)

            # 3. FOMOD installer check
            fomod_name_override = None
            fomod_config_for_save = None   # held for post-install choices save
            fomod_selections_for_save = None
            fomod_flags_for_save = None
            fomod_xml = detect_fomod(temp_dir)
            if fomod_xml is not None:
                print(f"DEBUG _install_archives: FOMOD detected: {fomod_xml}", flush=True)
                config = parse_fomod(fomod_xml)
                if config is not None and config.install_steps:
                    # FOMOD Selection Memory: try to load previous choices
                    previous_choices = None
                    # Priority 1: explicit reinstall path (from context menu)
                    if reinstall_mod_path and reinstall_mod_path.is_dir():
                        previous_choices = load_fomod_choices(reinstall_mod_path, config)
                    # Priority 2: check by FOMOD info name
                    if previous_choices is None:
                        candidate_name = None
                        info_pre = parse_fomod_info(fomod_xml.parent)
                        if "name" in info_pre:
                            candidate_name = info_pre["name"]
                        elif config.module_name and config.module_name != "FOMOD Package":
                            candidate_name = config.module_name
                        if candidate_name:
                            candidate_path = installer.mods_path / candidate_name
                            if candidate_path.is_dir():
                                previous_choices = load_fomod_choices(candidate_path, config)
                    # Priority 3: check by archive stem name
                    if previous_choices is None:
                        stem_name = installer.suggest_name(archive)
                        stem_path = installer.mods_path / stem_name
                        if stem_path.is_dir():
                            previous_choices = load_fomod_choices(stem_path, config)

                    dlg = FomodDialog(config, temp_dir, parent=self,
                                      previous_choices=previous_choices)
                    _center_on_parent(dlg)
                    if dlg.exec() != QDialog.DialogCode.Accepted:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        continue
                    # Save choices data for post-install persistence
                    fomod_config_for_save = config
                    fomod_selections_for_save = dlg.step_selections()
                    fomod_flags_for_save = dlg.flags()
                    all_files = collect_fomod_files(
                        config, dlg.selected_plugins(), dlg.flags()
                    )
                    # Read FOMOD info BEFORE deleting temp_dir (K3 fix)
                    info = parse_fomod_info(fomod_xml.parent)
                    new_temp = assemble_fomod_files(temp_dir, all_files)
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    if new_temp is None:
                        continue
                    temp_dir = new_temp
                    # Use FOMOD name for suggestion
                    if "name" in info:
                        fomod_name_override = info["name"]
                    elif config.module_name and config.module_name != "FOMOD Package":
                        fomod_name_override = config.module_name
                elif config is not None and config.required_files:
                    # No steps but required files — install them directly
                    # Read FOMOD info BEFORE deleting temp_dir (K3 fix)
                    info = parse_fomod_info(fomod_xml.parent)
                    new_temp = assemble_fomod_files(temp_dir, config.required_files)
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    if new_temp is None:
                        continue
                    temp_dir = new_temp
                    if "name" in info:
                        fomod_name_override = info["name"]
            else:
                # Kein XML-FOMOD — evtl. ein Script-FOMOD (C#), das Anvil nicht ausführen kann
                if detect_fomod_script(temp_dir) is not None:
                    reply = QMessageBox.question(
                        self, tr("fomod.script_title"), tr("fomod.script_message"),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        continue

            # 4. Normal mod installation
            best, variants = installer.suggest_names(archive)
            if fomod_name_override:
                best = fomod_name_override
                if best not in variants:
                    variants.insert(0, best)
            mod_name = best
            dest = installer.mods_path / mod_name

            # Modern (Vorlage): Dialog bei JEDER Installation — Name +
            # Kategorie bestätigen. Klassisch: nur bei Namens-Duplikat.
            from anvil.styles.dark_theme import theme_color as _tc
            modern_install = bool(_tc("panel2", ""))
            install_category_id = 0
            if modern_install or dest.exists():
                try:
                    archive_size = Path(archive).stat().st_size
                except OSError:
                    archive_size = 0
                cats = [
                    (c["id"], c["name"])
                    for c in self._category_manager.all_categories()
                ] if modern_install else []
                while True:
                    dlg = QuickInstallDialog(
                        variants, mod_name, self,
                        archive_name=Path(archive).name,
                        archive_size=archive_size,
                        fomod=fomod_xml is not None,
                        categories=cats,
                    )
                    _center_on_parent(dlg)
                    if dlg.exec() != QDialog.DialogCode.Accepted:
                        mod_name = None
                        break
                    mod_name = dlg.mod_name()
                    install_category_id = dlg.category_id()
                    if not mod_name:
                        continue  # empty name → show dialog again
                    dest = installer.mods_path / mod_name
                    if not dest.exists():
                        break  # neuer Name, kein Konflikt mehr
                    # Immer noch Duplikat → QueryOverwriteDialog
                    ovr = QueryOverwriteDialog(mod_name, self)
                    _center_on_parent(ovr)
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
                shutil.rmtree(temp_dir, ignore_errors=True)
                continue  # user cancelled

            # Install from extracted temp dir
            mod_path = installer.install_from_extracted(temp_dir, mod_name)
            if mod_path:
                # Kategorie aus dem Install-Dialog übernehmen
                if install_category_id:
                    from anvil.core.mod_metadata import write_meta_ini
                    write_meta_ini(
                        mod_path, {"category": str(install_category_id)})

                # FOMOD Selection Memory: save choices after installation
                if fomod_config_for_save and fomod_selections_for_save is not None:
                    save_fomod_choices(
                        mod_path, fomod_config_for_save,
                        fomod_selections_for_save, fomod_flags_for_save or {},
                    )

                # Transfer Nexus info from download .meta to mod meta.ini
                meta_file = Path(str(archive) + ".meta")
                if meta_file.is_file():
                    cp_meta = configparser.ConfigParser()
                    try:
                        cp_meta.read(str(meta_file), encoding="utf-8")
                        if cp_meta.has_section("General"):
                            dl_mod_id = cp_meta.get("General", "modID", fallback="0")
                            dl_name = cp_meta.get("General", "name", fallback="")
                            dl_version = cp_meta.get("General", "version", fallback="")
                            dl_game = cp_meta.get("General", "gameName", fallback="")
                            if dl_mod_id and dl_mod_id != "0":
                                from anvil.core.mod_metadata import write_meta_ini
                                nexus_data = {
                                    "modid": dl_mod_id,
                                    "installationFile": Path(archive).name,
                                    "version": dl_version,
                                    "newestVersion": dl_version,
                                    "gameName": dl_game,
                                    "repository": "Nexus",
                                }
                                if dl_name:
                                    nexus_data["nexusName"] = dl_name
                                if dl_game:
                                    nexus_data["nexusURL"] = f"https://www.nexusmods.com/{dl_game}/mods/{dl_mod_id}"
                                write_meta_ini(mod_path, nexus_data)
                    except (configparser.Error, OSError):
                        pass
                else:
                    # Fallback: parse modID from Nexus filename (manual download)
                    from anvil.core.nexus_filename_parser import extract_nexus_mod_id
                    parsed_id = extract_nexus_mod_id(Path(archive).name)
                    if parsed_id:
                        from anvil.core.mod_metadata import write_meta_ini
                        write_meta_ini(mod_path, {
                            "modid": str(parsed_id),
                            "installationFile": Path(archive).name,
                            "repository": "Nexus",
                        })

                profiles_dir = _active_instance_paths(self).profiles
                global_modlist = profiles_dir / "modlist.txt"
                if global_modlist.is_file():
                    # Global system: write to .profiles/modlist.txt
                    mod_names = read_global_modlist(profiles_dir)
                    if mod_path.name not in mod_names:
                        if insert_at is not None:
                            if _prev_inserted_name and _prev_inserted_name in mod_names:
                                # 2nd+ mod: insert right after the previously
                                # installed mod (stays in same separator)
                                pos = mod_names.index(_prev_inserted_name) + 1
                            else:
                                # 1st mod: map source-model row to modlist
                                # position via folder name lookup
                                model = self._mod_list_view.source_model()
                                rows = model._rows
                                if insert_at < len(rows):
                                    ref_name = rows[insert_at].folder_name
                                else:
                                    ref_name = None
                                if ref_name and ref_name in mod_names:
                                    pos = mod_names.index(ref_name)
                                else:
                                    pos = len(mod_names)
                            mod_names.insert(pos, mod_path.name)
                            _prev_inserted_name = mod_path.name
                        else:
                            mod_names.append(mod_path.name)
                        write_global_modlist(profiles_dir, mod_names)
                    # enabled=False → do NOT add to active_mods.json (default = disabled)
                else:
                    # Legacy system: per-profile modlist.txt
                    if insert_at is not None:
                        insert_mod_in_modlist(self._current_profile_path, mod_path.name, insert_at, enabled=False)
                        insert_at += 1
                    else:
                        add_mod_to_modlist(self._current_profile_path, mod_path.name, enabled=False)
                installed.append(mod_path.name)
                # Mark as installed in .meta
                downloads_dir = _active_instance_paths(self).downloads
                if archive.parent == downloads_dir:
                    self._write_install_meta(archive, mod_path.name)
                    # Auto-hide: removed=true in Meta wenn Setting aktiv
                    s = self._settings()
                    if s.value("Interface/hide_downloads_after_install", False, type=bool):
                        meta_path = Path(str(archive) + ".meta")
                        cp = configparser.ConfigParser()
                        cp.optionxform = str  # CamelCase-Keys beibehalten
                        if meta_path.is_file():
                            try:
                                cp.read(str(meta_path), encoding="utf-8")
                            except Exception as exc:
                                print(f"[META] parse failed: {meta_path}: {exc}", flush=True)
                        if not cp.has_section("General"):
                            cp.add_section("General")
                        cp.set("General", "removed", "true")
                        try:
                            with open(meta_path, "w", encoding="utf-8") as f:
                                cp.write(f)
                        except OSError:
                            pass
            else:
                shutil.rmtree(temp_dir, ignore_errors=True)
                QMessageBox.warning(
                    self, tr("error.install_failed_title"),
                    tr("error.install_failed_message", name=mod_name),
                )

        # Show status messages
        if frameworks_installed:
            names = ", ".join(frameworks_installed)
            self.statusBar().showMessage(tr("status.framework_installed", names=names), 5000)

        if not installed and not frameworks_installed:
            return

        # Reload mod list (reuses _reload_mod_list which handles framework filtering)
        self._reload_mod_list()

        # Setting 3: Update-Check after installation
        s = self._settings()
        if (
            installed
            and s.value("ModList/check_updates_after_install", True, type=bool)
            and s.value("Nexus/tracking_enabled", True, type=bool)
            and self._nexus_api.has_api_key()
            and self._current_plugin
        ):
            nexus_slug = (
                getattr(self._current_plugin, "GameNexusName", "")
                or getattr(self._current_plugin, "GameShortName", "")
            )
            if nexus_slug:
                queue = []
                for mod_folder_name in installed:
                    for entry in self._current_mod_entries:
                        if entry.name == mod_folder_name and entry.nexus_id > 0:
                            queue.append((
                                entry.display_name or entry.name,
                                entry.nexus_id,
                                entry.version,
                                entry.install_path,
                            ))
                            break
                if queue:
                    already_running = bool(self._pending_update_check)
                    self._update_check_queue.extend(queue)
                    self._update_check_slug = nexus_slug
                    if not already_running:
                        self._update_check_next()

        if installed:
            names = ", ".join(installed)
            self.statusBar().showMessage(tr("status.installed", names=names), 5000)
            self._schedule_redeploy()

    def _update_check_next(self) -> None:
        """Send the next update-check request from the queue."""
        if not self._update_check_queue:
            return
        if not self._update_check_slug:
            self._update_check_queue.clear()
            return
        name, nexus_id, version, mod_path = self._update_check_queue.pop(0)
        self._pending_update_check = (name, nexus_id, version, mod_path)
        self._nexus_api.update_check_mod(self._update_check_slug, nexus_id)

    def _write_install_meta(self, archive: Path, mod_name: str) -> None:
        """Write installed=true and installationFile=mod_name to the archive's .meta file."""
        meta_path = Path(str(archive) + ".meta")
        cp = configparser.ConfigParser()
        cp.optionxform = str  # CamelCase-Keys beibehalten
        if meta_path.is_file():
            try:
                cp.read(str(meta_path), encoding="utf-8")
            except Exception as exc:
                print(f"[META] parse failed: {meta_path}: {exc}", flush=True)
        if not cp.has_section("General"):
            cp.add_section("General")
        cp.set("General", "installed", "true")
        cp.set("General", "installationFile", mod_name)
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                cp.write(f)
        except OSError:
            pass

    def _clear_install_meta(self, mod_name: str) -> None:
        """Find the .meta file that references mod_name and set installed=false."""
        if not self._current_instance_path:
            return
        downloads_path = _active_instance_paths(self).downloads
        if not downloads_path.is_dir():
            return
        for meta_file in downloads_path.glob("*.meta"):
            cp = configparser.ConfigParser()
            cp.optionxform = str  # CamelCase-Keys beibehalten
            try:
                cp.read(str(meta_file), encoding="utf-8")
            except Exception:
                continue
            if cp.get("General", "installationFile", fallback="") == mod_name:
                cp.set("General", "installed", "false")
                try:
                    with open(meta_file, "w", encoding="utf-8") as f:
                        cp.write(f)
                except OSError:
                    pass
                break

    def _update_install_meta_name(self, old_name: str, new_name: str) -> None:
        """Update installationFile in the .meta file when a mod is renamed."""
        if not self._current_instance_path:
            return
        downloads_path = _active_instance_paths(self).downloads
        if not downloads_path.is_dir():
            return
        for meta_file in downloads_path.glob("*.meta"):
            cp = configparser.ConfigParser()
            cp.optionxform = str  # CamelCase-Keys beibehalten
            try:
                cp.read(str(meta_file), encoding="utf-8")
            except Exception as exc:
                print(f"[META] parse failed: {meta_file}: {exc}", flush=True)
                continue
            if cp.get("General", "installationFile", fallback="") == old_name:
                cp.set("General", "installationFile", new_name)
                try:
                    with open(meta_file, "w", encoding="utf-8") as f:
                        cp.write(f)
                except OSError:
                    pass
                break

    # ── Other slots ───────────────────────────────────────────────────

    def _on_mod_double_click(self, index=None):
        # Index aus dem doubleClicked Signal verwenden (falls vorhanden)
        if index is not None and index.isValid():
            mod_name = self._mod_list_view.get_mod_name_from_index(index)
        else:
            mod_name = self._mod_list_view.get_current_mod_name()
        if not mod_name:
            return

        # Sichtbare Mod-Reihenfolge aus dem Proxy-Model (ohne Separatoren)
        mod_names = self._mod_list_view.get_visible_mod_names()

        while mod_name:
            mod_path = str(_active_instance_paths(self).mods / mod_name)
            all_mods = [
                {"name": e.name, "path": str(_active_instance_paths(self).mods / e.name)}
                for e in self._current_mod_entries if e.enabled and not e.is_foreign
            ]
            mod_entry = next(
                (e for e in self._current_mod_entries if e.name == mod_name),
                None
            )
            dlg = ModDetailDialog(
                self, mod_name=mod_name, mod_path=mod_path,
                all_mods=all_mods, game_plugin=self._current_plugin,
                category_manager=self._category_manager,
                mod_entry=mod_entry,
            )
            _center_on_parent(dlg)
            result = dlg.exec()

            if result == ModDetailDialog.RESULT_PREV:
                idx = mod_names.index(mod_name) if mod_name in mod_names else -1
                if idx > 0:
                    mod_name = mod_names[idx - 1]
                else:
                    mod_name = mod_names[-1]  # wrap around
                self._mod_list_view.select_mod_by_name(mod_name)
            elif result == ModDetailDialog.RESULT_NEXT:
                idx = mod_names.index(mod_name) if mod_name in mod_names else -1
                if idx < len(mod_names) - 1:
                    mod_name = mod_names[idx + 1]
                else:
                    mod_name = mod_names[0]  # wrap around
                self._mod_list_view.select_mod_by_name(mod_name)
            else:
                break  # Schliessen

    # ── Mod list context menu ──────────────────────────────────────

    def _on_mod_context_menu(self, global_pos) -> None:
        """Build and show the mod list context menu."""
        if not self._current_instance_path:
            return

        selected_rows = self._mod_list_view.get_selected_source_rows()
        has_selection = len(selected_rows) > 0
        single = len(selected_rows) == 1

        menu = QMenu(self)

        # Vorlage: Mod-Name als Kopfzeile (nur modern, bei Einzelauswahl)
        from anvil.styles.dark_theme import theme_color as _ctx_tc
        if single and bool(_ctx_tc("panel2", "")):
            _hdr_name = self._mod_list_view.get_current_mod_name()
            if _hdr_name:
                _hdr = menu.addAction(_hdr_name)
                _hdr.setEnabled(False)
                menu.addSeparator()

        # ── Alle Mods (Submenu) ────────────────────────────────────
        all_mods_menu = menu.addMenu(tr("context.all_mods"))
        act_install_mod = all_mods_menu.addAction(tr("context.install_mod"))
        act_create_empty = all_mods_menu.addAction(tr("context.create_empty_mod"))
        act_create_sep = all_mods_menu.addAction(tr("context.create_separator"))
        all_mods_menu.addSeparator()
        act_collapse_all = all_mods_menu.addAction(tr("context.collapse_all"))
        act_expand_all = all_mods_menu.addAction(tr("context.expand_all"))
        all_mods_menu.addSeparator()
        act_enable_all = all_mods_menu.addAction(tr("context.enable_all"))
        act_disable_all = all_mods_menu.addAction(tr("context.disable_all"))
        act = all_mods_menu.addAction(tr("context.check_updates"))
        act.setEnabled(False)
        act = all_mods_menu.addAction(tr("context.auto_assign_categories"))
        act.setEnabled(False)
        act_reload = all_mods_menu.addAction(tr("context.reload"))
        act_export_csv = all_mods_menu.addAction(tr("context.export_csv"))

        # ── Kategorien (Submenus) ─────────────────────────────────
        andere_kat_menu = menu.addMenu(tr("context.other_categories"))
        primaere_kat_menu = menu.addMenu(tr("label.primary_category"))
        # Kein eigenes Stylesheet - globales Paper Dark.qss greift

        _cat_buttons = []  # keep refs: (cat_id, QPushButton)

        _ctx_entry = self._entry_for_row(selected_rows[0]) if single else None
        if single and _ctx_entry:
            entry = _ctx_entry
            row = selected_rows[0]
            assigned_ids = set(entry.category_ids)

            from PySide6.QtWidgets import QWidgetAction, QPushButton

            def _cat_btn_style(assigned: bool) -> str:
                from anvil.styles.dark_theme import theme_color
                if theme_color("panel2", ""):
                    color = theme_color("accent") if assigned else theme_color("txt")
                    hover = theme_color("hov")
                else:
                    color = "#00d4aa" if assigned else "#e0e0e0"
                    hover = "#2d2d2d"
                weight = "font-weight: bold;" if assigned else ""
                return f"""
                    QPushButton {{
                        color: {color};
                        {weight}
                        text-align: left;
                        padding: 6px 12px;
                        border: none;
                        background: transparent;
                    }}
                    QPushButton:hover {{ background: {hover}; }}
                """

            # "Andere Kategorien" — toggle buttons (Menü bleibt offen)
            for cat in self._category_manager.all_categories():
                cat_id = cat["id"]
                is_assigned = cat_id in assigned_ids
                prefix = "●  " if is_assigned else "    "

                btn = QPushButton(f"{prefix}{cat['name']}")
                btn.setFlat(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                # Styling: türkis wenn zugewiesen
                btn.setStyleSheet(_cat_btn_style(is_assigned))

                # Click-Handler: Toggle und UI aktualisieren
                def make_toggle_handler(cid, button, cats_menu, prim_menu):
                    def handler():
                        self._toggle_category(row, cid)
                        entry = self._entry_for_row(row)
                        # UI aktualisieren ohne Menü zu schließen
                        new_assigned = cid in entry.category_ids
                        new_prefix = "●  " if new_assigned else "    "
                        cat_name = self._category_manager.get_name(cid)
                        button.setText(f"{new_prefix}{cat_name}")
                        button.setStyleSheet(_cat_btn_style(new_assigned))
                        if new_assigned:
                            # Erste Kategorie zugewiesen → automatisch als Primary
                            if len(entry.category_ids) == 1:
                                self._set_primary_category(row, cid)
                        else:
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

        # ── Eigene Eigenschaften (Submenu, nur wenn welche angelegt) ──
        _all_props = self._property_manager.all_properties()
        if _all_props:
            props_menu = menu.addMenu(tr("context.properties"))
            if single and _ctx_entry:
                _assigned_props = set(_ctx_entry.property_ids)
                for prop in _all_props:
                    act_p = props_menu.addAction(prop["name"])
                    act_p.setCheckable(True)
                    act_p.setChecked(prop["id"] in _assigned_props)
                    act_p.triggered.connect(
                        lambda checked, pid=prop["id"], r=selected_rows[0]:
                        self._toggle_property(r, pid))
            else:
                props_menu.setEnabled(False)
        menu.addSeparator()

        # ── Updates / Aktivieren ──────────────────────────────────
        act = menu.addAction(tr("context.force_update_check"))
        act.setEnabled(False)
        act = menu.addAction(tr("context.ignore_update"))
        act.setEnabled(False)
        act_enable = menu.addAction(tr("context.enable_selected"))
        act_enable.setEnabled(has_selection)
        act_disable = menu.addAction(tr("context.disable_selected"))
        act_disable.setEnabled(has_selection)

        menu.addSeparator()

        # ── Gruppen ───────────────────────────────────────────────
        act_create_group = None
        act_dissolve_group = None
        act_rename_group = None
        act_add_to_group = None
        act_remove_from_group = None
        act_group_color = None
        _selected_group_name = ""

        # Check if any selected row is a separator
        model = self._mod_list_view.source_model()
        has_separator_in_selection = any(
            0 <= r < len(model._rows) and model._rows[r].is_separator
            for r in selected_rows
        )

        if has_selection and not has_separator_in_selection:
            if len(selected_rows) >= 2:
                act_create_group = menu.addAction(tr("context.create_group"))

            if single:
                row = selected_rows[0]
                if 0 <= row < len(model._rows):
                    row_data = model._rows[row]
                    if row_data.group_name:
                        _selected_group_name = row_data.group_name
                        if row_data.is_group_head:
                            act_dissolve_group = menu.addAction(tr("context.dissolve_group"))
                            act_rename_group = menu.addAction(tr("context.rename_group"))
                            act_group_color = menu.addAction(tr("context.group_color"))
                        else:
                            act_remove_from_group = menu.addAction(tr("context.remove_from_group"))
                    else:
                        group_names = self._group_manager.group_names()
                        if group_names:
                            add_group_menu = menu.addMenu(tr("context.add_to_group"))
                            for gn in group_names:
                                act_g = add_group_menu.addAction(gn)
                                act_g.setData(gn)
                            act_add_to_group = add_group_menu
            elif len(selected_rows) >= 2:
                has_grouped = any(
                    0 <= r < len(model._rows) and model._rows[r].group_name
                    for r in selected_rows
                )
                if has_grouped:
                    act_remove_from_group = menu.addAction(tr("context.remove_from_group"))

        menu.addSeparator()

        # ── Senden / Mod-Aktionen ────────────────────────────────
        send_to_menu = menu.addMenu(tr("context.send_to"))
        send_to_menu.setEnabled(False)
        move_to_sep_menu = menu.addMenu(tr("context.move_to_separator"))
        separators = self._mod_list_view.source_model().get_all_separators()
        if separators and has_selection:
            for sep_row, sep_folder, sep_name in separators:
                act_sep = move_to_sep_menu.addAction(sep_name)
                act_sep.setData(sep_folder)
        else:
            move_to_sep_menu.setEnabled(False)
        act_rename = menu.addAction(tr("context.rename_mod"))
        act_rename.setEnabled(single)
        act_reinstall = menu.addAction(tr("context.reinstall_mod"))
        act_reinstall.setEnabled(single)
        act_remove = menu.addAction(tr("context.remove_mod"))
        act_remove.setEnabled(has_selection)
        menu.addSeparator()

        # ── Sicherung / Nexus / Explorer ─────────────────────────
        act_backup = menu.addAction(tr("context.create_backup"))
        act_backup.setEnabled(single)

        # Category reassign (Nexus)
        act_reassign_cat = menu.addAction(tr("context.reassign_category"))
        act_reassign_cat.setEnabled(
            single and _ctx_entry is not None
            and _ctx_entry.nexus_id > 0
            and self._nexus_api.has_api_key()
        )

        act = menu.addAction(tr("context.start_tracking"))
        act.setEnabled(False)
        nexus_info_menu = menu.addMenu(tr("context.nexus_info_menu"))
        nexus_info_menu.setEnabled(self._nexus_api.has_api_key())
        act_nexus_query = nexus_info_menu.addAction(tr("context.nexus_query"))
        act_nexus_query.setEnabled(single and self._nexus_api.has_api_key())
        act_nexus_query_all = nexus_info_menu.addAction(tr("context.nexus_query_all"))
        act_nexus_query_all.setEnabled(self._nexus_api.has_api_key() and bool(self._current_mod_entries))
        # Nexus: nur aktiviert wenn Mod eine Nexus-ID hat
        act_nexus = menu.addAction(tr("context.visit_nexus"))
        has_nexus = single and _ctx_entry is not None and _ctx_entry.nexus_id > 0
        act_nexus.setEnabled(has_nexus)
        act_explorer = menu.addAction(tr("context.open_explorer"))
        act_explorer.setEnabled(single)
        act_info = menu.addAction(tr("context.information"))
        act_info.setEnabled(single)

        # ── Separator-Farbe ──────────────────────────────────────
        act_select_color = None
        act_reset_color = None
        act_set_deploy_path = None
        act_reset_deploy_path = None
        _sep_entry = None
        if single and _ctx_entry:
            _sep_entry = _ctx_entry
            if _sep_entry.is_separator:
                menu.addSeparator()
                act_select_color = menu.addAction(tr("context.select_color"))
                if _sep_entry.color:
                    act_reset_color = menu.addAction(tr("context.reset_color"))
                menu.addSeparator()
                act_set_deploy_path = menu.addAction(tr("context.set_deploy_path"))
                if _sep_entry.deploy_path:
                    act_reset_deploy_path = menu.addAction(tr("context.reset_deploy_path"))

        # ── Execute ───────────────────────────────────────────────
        chosen = menu.exec(global_pos)

        # Handle "Primäre Kategorie" actions
        if chosen and single and selected_rows[0] < len(self._current_mod_entries):
            row = selected_rows[0]
            # Prüfe ob Action aus "Primäre Kategorie" (via .data())
            if chosen.data() is not None and chosen.parent() == primaere_kat_menu:
                cat_id = chosen.data()
                self._set_primary_category(row, cat_id)

        # Handle "In Trenner verschieben" actions
        if chosen and chosen.data() is not None and chosen.parent() == move_to_sep_menu:
            self._ctx_move_to_separator(selected_rows, chosen.data())
            return

        if not chosen:
            return

        if chosen == act_install_mod:
            self._ctx_install_mod()
        elif chosen == act_create_empty:
            self._ctx_create_empty_mod()
        elif chosen == act_create_sep:
            self._ctx_create_separator()
        elif chosen == act_export_csv:
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
        elif chosen == act_reassign_cat:
            self._ctx_reassign_category(selected_rows[0])
        elif chosen == act_nexus:
            self._ctx_visit_nexus(selected_rows[0])
        elif chosen == act_nexus_query:
            self._ctx_query_nexus_info(selected_rows[0])
        elif chosen == act_nexus_query_all:
            self._ctx_query_all_nexus_info()
        elif chosen == act_explorer:
            self._ctx_open_explorer(selected_rows[0])
        elif chosen == act_info:
            self._ctx_show_info(selected_rows[0])
        elif chosen is not None and chosen == act_select_color and act_select_color:
            self._ctx_select_separator_color(selected_rows[0])
        elif chosen is not None and chosen == act_reset_color and act_reset_color:
            self._ctx_reset_separator_color(selected_rows[0])
        elif chosen is not None and chosen == act_set_deploy_path and act_set_deploy_path:
            self._ctx_set_deploy_path(selected_rows[0])
        elif chosen is not None and chosen == act_reset_deploy_path and act_reset_deploy_path:
            self._ctx_reset_deploy_path(selected_rows[0])
        elif act_create_group is not None and chosen == act_create_group:
            self._ctx_create_group(selected_rows)
        elif act_dissolve_group is not None and chosen == act_dissolve_group:
            self._ctx_dissolve_group(_selected_group_name)
        elif act_rename_group is not None and chosen == act_rename_group:
            self._ctx_rename_group(_selected_group_name)
        elif act_group_color is not None and chosen == act_group_color:
            self._ctx_group_color(_selected_group_name)
        elif act_remove_from_group is not None and chosen == act_remove_from_group:
            self._ctx_remove_from_group(selected_rows)
        elif act_add_to_group is not None and isinstance(act_add_to_group, QMenu):
            if chosen and chosen.data() is not None and chosen.parent() == act_add_to_group:
                self._ctx_add_to_group(selected_rows[0], chosen.data())

    # ── Context menu actions ───────────────────────────────────────

    def _ctx_create_separator(self) -> None:
        """Create a new separator in the mod list."""
        name, ok = get_text_input(
            self, tr("dialog.create_separator_title"), tr("dialog.create_separator_prompt"),
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        folder_name = f"{name}_separator"

        # ── BG3-Weiche: Separator direkt ins Model + bg3_separators.json ──
        if self._bg3_installer is not None:
            model = self._mod_list_view.source_model()
            # Duplikat-Prüfung gegen bestehende Separatoren im Model
            for r in model._rows:
                if r.is_separator and r.folder_name == folder_name:
                    QMessageBox.warning(
                        self, tr("dialog.create_separator_title"),
                        tr("dialog.separator_exists", name=name),
                    )
                    return

            sep_entry = ModEntry(
                name=folder_name,
                enabled=True,
                priority=0,
                is_separator=True,
                display_name=name,
            )
            sep_row = mod_entry_to_row(sep_entry)
            # Insert at current selection or at the top
            tree = self._mod_list_view._tree
            sel_indexes = tree.selectionModel().selectedRows()
            if sel_indexes:
                proxy_row = sel_indexes[0].row()
                source_idx = self._mod_list_view._proxy_model.mapToSource(sel_indexes[0])
                insert_pos = source_idx.row()
            else:
                insert_pos = 0

            model.beginInsertRows(QModelIndex(), insert_pos, insert_pos)
            model._rows.insert(insert_pos, sep_row)
            model.endInsertRows()

            # Update internal entries list
            self._current_mod_entries.insert(insert_pos, sep_entry)
            for i, e in enumerate(self._current_mod_entries):
                e.priority = i
            self._mod_list_view._proxy_model.set_mod_entries(self._current_mod_entries)

            self._bg3_save_separators(model)
            self._mod_list_view._tree._apply_separator_filter()
            self.statusBar().showMessage(tr("status.separator_created", name=name), 5000)
            return

        # ── Standard path: Ordner in .mods/ + modlist.txt ──
        mods_dir = _active_instance_paths(self).mods
        sep_path = mods_dir / folder_name

        if sep_path.exists():
            QMessageBox.warning(
                self, tr("dialog.create_separator_title"),
                tr("dialog.separator_exists", name=name),
            )
            return

        try:
            sep_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(
                self, tr("dialog.create_separator_title"), str(exc),
            )
            return

        # Globale Modlist aktualisieren (nicht Legacy per-Profile)
        profiles_dir = _active_instance_paths(self).profiles
        global_list = read_global_modlist(profiles_dir)
        # Position: vor der aktuellen Auswahl, oder ganz oben
        tree = self._mod_list_view._tree
        sel_indexes = tree.selectionModel().selectedRows()
        if sel_indexes:
            source_idx = self._mod_list_view._proxy_model.mapToSource(sel_indexes[0])
            insert_pos = source_idx.row()
        else:
            insert_pos = 0
        global_list.insert(insert_pos, folder_name)
        write_global_modlist(profiles_dir, global_list)

        # Separator als aktiv markieren
        active = read_active_mods(self._current_profile_path)
        active.add(folder_name)
        write_active_mods(self._current_profile_path, active)

        self._reload_mod_list()
        self.statusBar().showMessage(tr("status.separator_created", name=name), 5000)

    def _ctx_select_separator_color(self, source_row: int) -> None:
        """Open QColorDialog for separator and save chosen color."""
        if source_row >= len(self._current_mod_entries):
            return
        entry = self._current_mod_entries[source_row]
        if not entry.is_separator:
            return

        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor

        initial = QColor(entry.color) if entry.color else QColor(Qt.GlobalColor.white)
        if not initial.isValid():
            initial = QColor(Qt.GlobalColor.white)

        # Qt-eigener Dialog — der native GTK-Portal-Dialog ist unzuverlässig
        color = QColorDialog.getColor(
            initial, self, tr("context.select_color"),
            QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if not color.isValid():
            return  # User cancelled

        hex_color = color.name()  # e.g. "#ff0000"

        # Persist to meta.ini
        from anvil.core.mod_metadata import write_meta_ini
        write_meta_ini(entry.install_path, {"color": hex_color})

        # Update in-memory data
        entry.color = hex_color

        # Update ModRow in model
        model = self._mod_list_view.source_model()
        rows = model._rows
        if source_row < len(rows):
            rows[source_row].color = hex_color
            model.dataChanged.emit(
                model.index(source_row, 0),
                model.index(source_row, COL_COUNT - 1),
                [Qt.ItemDataRole.BackgroundRole],
            )
        # Repaint scrollbar
        self._mod_list_view._tree.verticalScrollBar().update()

    def _ctx_reset_separator_color(self, source_row: int) -> None:
        """Remove custom color from separator."""
        if source_row >= len(self._current_mod_entries):
            return
        entry = self._current_mod_entries[source_row]
        if not entry.is_separator:
            return

        # Persist empty color to meta.ini
        from anvil.core.mod_metadata import write_meta_ini
        write_meta_ini(entry.install_path, {"color": ""})

        # Update in-memory data
        entry.color = ""

        # Update ModRow in model
        model = self._mod_list_view.source_model()
        rows = model._rows
        if source_row < len(rows):
            rows[source_row].color = ""
            model.dataChanged.emit(
                model.index(source_row, 0),
                model.index(source_row, COL_COUNT - 1),
                [Qt.ItemDataRole.BackgroundRole],
            )
        # Repaint scrollbar
        self._mod_list_view._tree.verticalScrollBar().update()

    # ── Deploy path context menu actions ─────────────────────────────

    def _ctx_set_deploy_path(self, source_row: int) -> None:
        """Open QFileDialog for separator and save chosen deploy path."""
        if source_row >= len(self._current_mod_entries):
            return
        entry = self._entry_for_row(source_row)
        if entry is None or not entry.is_separator:
            return

        chosen_path = QFileDialog.getExistingDirectory(
            self,
            tr("dialog.deploy_path_title"),
            entry.deploy_path or str(Path.home()),
        )
        if not chosen_path:
            return  # User cancelled

        # Persist to meta.ini
        from anvil.core.mod_metadata import write_meta_ini
        write_meta_ini(entry.install_path, {"deploy_path": chosen_path})

        # Update in-memory data
        entry.deploy_path = chosen_path

        # Update ModRow tooltip in model
        model = self._mod_list_view.source_model()
        rows = model._rows
        if source_row < len(rows):
            rows[source_row].deploy_path = chosen_path
            model.dataChanged.emit(
                model.index(source_row, 0),
                model.index(source_row, COL_COUNT - 1),
                [Qt.ItemDataRole.ToolTipRole],
            )

        # Log
        sep_name = entry.display_name or entry.name
        self._log_panel.add_log(
            "info",
            tr("dialog.deploy_path_set", name=sep_name, path=chosen_path),
        )

    def _ctx_reset_deploy_path(self, source_row: int) -> None:
        """Remove custom deploy path from separator."""
        if source_row >= len(self._current_mod_entries):
            return
        entry = self._entry_for_row(source_row)
        if entry is None or not entry.is_separator:
            return

        # Persist empty deploy_path to meta.ini
        from anvil.core.mod_metadata import write_meta_ini
        write_meta_ini(entry.install_path, {"deploy_path": ""})

        # Update in-memory data
        entry.deploy_path = ""

        # Update ModRow tooltip in model
        model = self._mod_list_view.source_model()
        rows = model._rows
        if source_row < len(rows):
            rows[source_row].deploy_path = ""
            model.dataChanged.emit(
                model.index(source_row, 0),
                model.index(source_row, COL_COUNT - 1),
                [Qt.ItemDataRole.ToolTipRole],
            )

        # Log
        sep_name = entry.display_name or entry.name
        self._log_panel.add_log(
            "info",
            tr("dialog.deploy_path_reset", name=sep_name),
        )

    # ── Group context menu actions ──────────────────────────────────

    def _get_separator_for_row(self, source_row: int) -> str:
        """Find the separator folder_name that contains the given row."""
        model = self._mod_list_view.source_model()
        for i in range(source_row, -1, -1):
            if i < len(model._rows) and model._rows[i].is_separator:
                return model._rows[i].folder_name
        return ""

    def _ctx_create_group(self, source_rows: list[int]) -> None:
        """Create a new group from selected mods."""
        if len(source_rows) < 2:
            return

        model = self._mod_list_view.source_model()

        # Validate: all mods must be in the same separator
        sep_names = set()
        folder_names = []
        for row in source_rows:
            if row >= len(model._rows):
                return
            if model._rows[row].is_separator:
                return
            sep = self._get_separator_for_row(row)
            sep_names.add(sep)
            folder_names.append(model._rows[row].folder_name)

        if len(sep_names) > 1:
            QMessageBox.warning(
                self, tr("dialog.create_group_title"),
                tr("dialog.group_cross_separator"),
            )
            return

        name, ok = get_text_input(
            self, tr("dialog.create_group_title"), tr("dialog.create_group_prompt"),
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        if self._group_manager.group_exists(name):
            QMessageBox.warning(
                self, tr("dialog.create_group_title"),
                tr("dialog.group_name_exists"),
            )
            return

        self._group_manager.create_group(name, folder_names)
        self._reload_mod_list()
        self.statusBar().showMessage(tr("context.create_group").replace("...", f": {name}"), 5000)

    def _ctx_dissolve_group(self, group_name: str) -> None:
        """Dissolve a group, keeping mods in place."""
        if not group_name:
            return

        reply = QMessageBox.question(
            self, tr("context.dissolve_group"),
            tr("dialog.dissolve_confirm", name=group_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._group_manager.dissolve_group(group_name)
        self._reload_mod_list()

    def _ctx_rename_group(self, group_name: str) -> None:
        """Rename a group."""
        if not group_name:
            return

        new_name, ok = get_text_input(
            self, tr("dialog.rename_group_title"), tr("dialog.rename_group_prompt"),
            text=group_name,
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()

        if new_name == group_name:
            return

        if self._group_manager.group_exists(new_name):
            QMessageBox.warning(
                self, tr("dialog.rename_group_title"),
                tr("dialog.group_name_exists"),
            )
            return

        self._group_manager.rename_group(group_name, new_name)
        self._reload_mod_list()

    def _ctx_group_color(self, group_name: str) -> None:
        """Change group color."""
        if not group_name:
            return

        from PySide6.QtWidgets import QColorDialog

        current = QColor(self._group_manager.get_group_color(group_name))
        color = QColorDialog.getColor(
            current, self, tr("context.group_color"),
            QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if color.isValid():
            self._group_manager.set_color(group_name, color.name())
            self._reload_mod_list()

    def _ctx_add_to_group(self, source_row: int, group_name: str) -> None:
        """Add a mod to an existing group."""
        model = self._mod_list_view.source_model()
        if source_row >= len(model._rows):
            return
        folder_name = model._rows[source_row].folder_name

        current_group = self._group_manager.get_group_for_mod(folder_name)
        if current_group == group_name:
            QMessageBox.information(
                self, tr("context.add_to_group"),
                tr("dialog.group_already_member", mod=folder_name, group=group_name),
            )
            return

        # Validate same separator as group head
        members = self._group_manager.get_members(group_name)
        if members:
            head_folder = members[0]
            mod_sep = self._get_separator_for_row(source_row)
            head_sep = ""
            for i, r in enumerate(model._rows):
                if r.folder_name == head_folder:
                    head_sep = self._get_separator_for_row(i)
                    break
            if head_sep != mod_sep:
                QMessageBox.warning(
                    self, tr("context.add_to_group"),
                    tr("dialog.group_cross_separator"),
                )
                return

        self._group_manager.add_member(group_name, folder_name)
        self._reload_mod_list()

    def _ctx_remove_from_group(self, source_rows: list[int]) -> None:
        """Remove mods from their groups."""
        model = self._mod_list_view.source_model()
        for row in source_rows:
            if row < len(model._rows):
                folder_name = model._rows[row].folder_name
                self._group_manager.remove_member(folder_name)
        self._reload_mod_list()

    def _open_mods_folder(self) -> None:
        """Open the mods folder in file manager."""
        if not self._current_instance_path:
            return
        path = _active_instance_paths(self).mods
        if path.is_dir():
            host_open_path(str(path))

    def _open_game_folder(self) -> None:
        """Open the game installation folder in file manager."""
        if not self._current_game_path:
            return
        if self._current_game_path.is_dir():
            host_open_path(str(self._current_game_path))

    def _open_mygames_folder(self) -> None:
        """Open the My Games folder in file manager."""
        if not self._current_plugin:
            return
        if hasattr(self._current_plugin, "gameDocumentsDirectory"):
            path = self._current_plugin.gameDocumentsDirectory()
            if path and path.is_dir():
                host_open_path(str(path))

    def _open_saves_folder(self) -> None:
        """Open the save game directory in file manager."""
        if not self._current_plugin:
            return
        if hasattr(self._current_plugin, "gameSavesDirectory"):
            path = self._current_plugin.gameSavesDirectory()
            if path and path.is_dir():
                host_open_path(str(path))
            else:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, tr("dialog.saves_not_found_title"),
                    tr("dialog.saves_not_found_message"),
                )

    def _open_ini_folder(self) -> None:
        """Open the INI folder in file manager (same as My Games for most games)."""
        if not self._current_plugin:
            return
        if hasattr(self._current_plugin, "gameDocumentsDirectory"):
            path = self._current_plugin.gameDocumentsDirectory()
            if path and path.is_dir():
                host_open_path(str(path))

    def _open_instance_folder(self) -> None:
        """Open the instance folder in file manager."""
        if not self._current_instance_path:
            return
        if self._current_instance_path.is_dir():
            host_open_path(str(self._current_instance_path))

    def _open_profile_folder(self) -> None:
        """Open the profile folder in file manager."""
        print(f"DEBUG _open_profile_folder: profile={self._current_profile_path}")
        if not self._current_profile_path:
            print("DEBUG _open_profile_folder: No profile path, returning")
            return
        if self._current_profile_path.is_dir():
            host_open_path(str(self._current_profile_path))

    def _open_downloads_folder(self) -> None:
        """Open the downloads folder in file manager."""
        if not self._current_instance_path:
            return
        path = _active_instance_paths(self).downloads
        if path.is_dir():
            host_open_path(str(path))

    def _open_ao_install_folder(self) -> None:
        """Open the Anvil Organizer installation folder in file manager."""
        from anvil.core.resource_path import get_anvil_base
        path = get_anvil_base().parent
        if path.is_dir():
            host_open_path(str(path))

    def _open_ao_plugins_folder(self) -> None:
        """Open the Anvil Organizer plugins folder in file manager."""
        from anvil.core.resource_path import get_anvil_base
        path = get_anvil_base() / "plugins"
        if path.is_dir():
            host_open_path(str(path))

    def _open_ao_styles_folder(self) -> None:
        """Open the Anvil Organizer styles folder in file manager."""
        from anvil.core.resource_path import get_anvil_base
        path = get_anvil_base() / "styles"
        if path.is_dir():
            host_open_path(str(path))

    def _open_ao_logs_folder(self) -> None:
        """Open the Anvil Organizer logs folder in file manager."""
        path = anvil_base_paths().logs
        if path.is_dir():
            host_open_path(str(path))
            return
        QMessageBox.warning(
            self,
            tr("dialog.warning"),
            tr("storage.base_unavailable", path=str(path.parent)),
        )

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
            backups_dir = _active_instance_paths(self).backups
            backups_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            zip_path = backups_dir / f"backup_{timestamp}.zip"
            mods_dir = _active_instance_paths(self).mods
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

            Toast(self, tr("toast.backup_created", count=mod_count, name=zip_path.name, size=size_str))
            print("[BACKUP] Toast gezeigt")
            self.statusBar().showMessage(tr("status.backup_created", name=zip_path.name), 5000)

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

        backups_dir = _active_instance_paths(self).backups
        backups = sorted(backups_dir.glob("backup_*.zip"), reverse=True)

        if not backups:
            QMessageBox.information(self, tr("dialog.no_backups_title"), tr("dialog.backup_none"))
            return

        # Show card-based dialog
        dialog = BackupDialog(self, backups)
        _center_on_parent(dialog)
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
            mods_dir = _active_instance_paths(self).mods
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
        self._do_redeploy()
        Toast(self, tr("toast.backup_restored", name=zip_path.name))

    def _on_profile_create_rejected(self, message_key: str, name: str) -> None:
        """Show why the profile bar refused a name."""
        Toast(self, tr(message_key, name=name))

    def _profile_creation_failed(self, name: str, reason: str) -> None:
        """Report a failed creation and drop the tab the bar added early.

        The profile bar inserts the new tab before this handler runs, so
        on failure the bar would keep showing a profile that does not
        exist on disk.
        """
        print(f"[Profiles] Could not create profile {name!r}: {reason}")
        # Longer than the default so the technical reason stays readable.
        Toast(self, tr("toast.profile_create_failed", error=reason), duration=8000)
        active = self._current_profile_path.name if self._current_profile_path else "Default"
        self._profile_bar.set_profiles(self._get_profile_list(), active=active)

    def _on_profile_created(self, name: str) -> None:
        """Handle new profile creation - create folder and copy Default's active_mods."""
        if not self._current_instance_path:
            self._profile_creation_failed(name, tr("toast.profile_no_instance"))
            return
        if not is_valid_profile_name(name):
            self._profile_creation_failed(name, tr("toast.profile_invalid_name"))
            return

        profiles_dir = _active_instance_paths(self).profiles
        try:
            new_profile_dir = safe_profile_directory(
                self._current_instance_path, name,
                profiles_root=profiles_dir,
            )
            new_profile_dir.mkdir(parents=True, exist_ok=True)
        except (ValueError, OSError) as exc:
            self._profile_creation_failed(name, str(exc))
            return

        # ── BG3-Weiche: bg3_modstate.json kopieren statt active_mods.json ──
        if self._bg3_installer is not None:
            try:
                state_src = self._bg3_installer._state_file_path()
                if state_src and state_src.is_file():
                    shutil.copy2(state_src, new_profile_dir / "bg3_modstate.json")
                # Copy separators too
                if self._current_profile_path:
                    sep_src = self._current_profile_path / "bg3_separators.json"
                    if sep_src.is_file():
                        shutil.copy2(sep_src, new_profile_dir / "bg3_separators.json")
            except OSError as exc:
                self._profile_creation_failed(name, str(exc))
                return
            self._on_profile_changed(name)
            Toast(self, tr("toast.profile_created", name=name))
            return

        # ── Standard path ──
        # Copy active_mods.json from Default profile (basis template)
        default_profile = profiles_dir / "Default"
        default_active = default_profile / "active_mods.json"
        try:
            if default_active.exists():
                shutil.copy(default_active, new_profile_dir / "active_mods.json")
            else:
                # If Default has no active_mods.json yet, create one with current state
                active_mods = {e.name for e in self._current_mod_entries if e.enabled and not e.is_foreign}
                write_active_mods(new_profile_dir, active_mods)

            # Plugin activation and order are profile-specific too.
            default_plugins = default_profile / "plugins.txt"
            if default_plugins.is_file():
                shutil.copy2(default_plugins, new_profile_dir / "plugins.txt")
        except OSError as exc:
            self._profile_creation_failed(name, str(exc))
            return

        # Switch to new profile
        self._on_profile_changed(name)
        Toast(self, tr("toast.profile_created", name=name))

    def _on_profile_renamed(self, old_name: str, new_name: str) -> None:
        """Handle profile rename - rename folder on disk."""
        if (
            not self._current_instance_path
            or not is_valid_profile_name(old_name)
            or not is_valid_profile_name(new_name)
        ):
            return

        profiles_dir = _active_instance_paths(self).profiles
        try:
            old_path = safe_profile_directory(
                self._current_instance_path, old_name,
                profiles_root=profiles_dir,
            )
            new_path = safe_profile_directory(
                self._current_instance_path, new_name,
                profiles_root=profiles_dir,
            )
        except ValueError:
            return

        def reject_rename(message: str) -> None:
            names = [tab.text() for tab in self._profile_bar._tabs]
            restored = [
                old_name if name == new_name else name for name in names
            ]
            active = (
                old_name
                if self._profile_bar._active_profile == new_name
                else self._profile_bar._active_profile
            )
            self._profile_bar.set_profiles(restored, active=active)
            QMessageBox.warning(
                self, tr("error.rename_failed_title"), message
            )

        if not old_path.exists() or new_path.exists():
            reject_rename(tr("error.rename_failed_title"))
            return
        try:
            old_path.rename(new_path)
        except OSError as exc:
            reject_rename(str(exc))
            return

        # Update every active-profile consumer together.
        if self._current_profile_path and self._current_profile_path.name == old_name:
            self._current_profile_path = new_path
            current_instance = self.instance_manager.current_instance()
            if current_instance:
                data = self.instance_manager.load_instance(current_instance)
                if data:
                    data["selected_profile"] = new_name
                    self.instance_manager.save_instance(current_instance, data)
            self._game_panel.set_instance_path(
                self._current_instance_path, profile_name=new_name
            )

        Toast(self, tr("toast.profile_renamed", old=old_name, new=new_name))

    def _on_profile_changed(self, name: str) -> None:
        """Handle profile switch - update checkboxes only, keep order.

        The global modlist.txt (load order) is shared across profiles.
        Only active_mods.json differs per profile.
        """
        if not self._current_instance_path or not is_valid_profile_name(name):
            return

        profiles_dir = _active_instance_paths(self).profiles
        try:
            new_profile_path = safe_profile_directory(
                self._current_instance_path, name,
                profiles_root=profiles_dir,
            )
        except ValueError:
            return
        new_profile_path.mkdir(parents=True, exist_ok=True)

        # ── BG3-Weiche: bg3_modstate.json pro Profil ──
        if self._bg3_installer is not None:
            # Save current state to OLD profile
            if self._current_profile_path and self._current_profile_path != new_profile_path:
                self._bg3_save_separators()
                state_src = self._bg3_installer._state_file_path()
                if state_src and state_src.is_file():
                    shutil.copy2(state_src, self._current_profile_path / "bg3_modstate.json")

            # Update profile path
            self._current_profile_path = new_profile_path

            # Restore state from NEW profile (if it has one)
            saved_state = new_profile_path / "bg3_modstate.json"
            state_dst = self._bg3_installer._state_file_path()
            if saved_state.is_file() and state_dst:
                shutil.copy2(saved_state, state_dst)

            # Save selected profile
            current_instance = self.instance_manager.current_instance()
            if current_instance:
                data = self.instance_manager.load_instance(current_instance)
                if data:
                    data["selected_profile"] = name
                    self.instance_manager.save_instance(current_instance, data)

            self._bg3_reload_mod_list()
            self._game_panel.set_instance_path(self._current_instance_path, profile_name=name)
            return

        # ── Standard path ──
        # 1. Save current active mods to OLD profile before switching
        if self._current_profile_path and self._current_profile_path != new_profile_path:
            active_mods = {e.name for e in self._current_mod_entries if e.enabled and not e.is_foreign}
            write_active_mods(self._current_profile_path, active_mods)

        # 1b. Save collapsed separators to OLD profile before switching
        s = self._settings()
        if s.value("ModList/collapse_per_profile", False, type=bool) and self._current_profile_path:
            collapsed_list = sorted(self._mod_list_view._tree._collapsed_separators)
            old_ui_state = self._current_profile_path / "ui_state.json"
            try:
                old_ui_state.write_text(json.dumps({"collapsed_separators": collapsed_list}))
            except OSError:
                pass

        # 2. Update profile path
        self._current_profile_path = new_profile_path

        # 2b. Load groups for new profile
        self._group_manager.load(self._current_profile_path)
        if self._current_instance_path:
            mods_dir = _active_instance_paths(self).mods
            if mods_dir.is_dir():
                existing_folders = {d.name for d in mods_dir.iterdir() if d.is_dir()}
                self._group_manager.cleanup_orphans(existing_folders)

        # 3. Save selected profile to instance data
        current_instance = self.instance_manager.current_instance()
        if current_instance:
            data = self.instance_manager.load_instance(current_instance)
            if data:
                data["selected_profile"] = name
                self.instance_manager.save_instance(current_instance, data)

        # 4. Load active mods from new profile and update checkboxes only
        new_active = read_active_mods(self._current_profile_path)
        self._apply_active_state(new_active)

        # 5. Collapsed separators für neues Profil laden
        if s.value("ModList/collapse_per_profile", False, type=bool) and self._current_profile_path:
            ui_state_file = self._current_profile_path / "ui_state.json"
            if ui_state_file.is_file():
                try:
                    ui_state = json.loads(ui_state_file.read_text())
                    saved_collapsed = ui_state.get("collapsed_separators", [])
                except (json.JSONDecodeError, OSError):
                    saved_collapsed = []
            else:
                saved_collapsed = []
            tree = self._mod_list_view._tree
            if isinstance(saved_collapsed, list) and saved_collapsed:
                tree._collapsed_separators = set(str(x) for x in saved_collapsed)
            else:
                tree._collapsed_separators.clear()
            tree._apply_separator_filter()

        # 6. Clean up the old profile's deployment — the new one goes out on game start
        self._redeploy_timer.stop()
        if self._game_running or self._game_panel.is_game_running():
            print("[PURGE] profile switch while the game may run — "
                  "deployment kept", flush=True)
        else:
            self._game_panel.silent_purge()
        self._game_panel.set_instance_path(self._current_instance_path, profile_name=name)
        self._sync_separator_deploy_paths()
        # The new profile has to reach the game directory now: with
        # keep-deployed on, the user may never launch through Anvil again.
        # Runs after the separator routes are synced, or it would deploy
        # the new profile along the old paths.
        if self.keeps_mods_deployed() and not (
                self._game_running or self._game_panel.is_game_running()):
            print("[PURGE] keep-deployed is on — deploying the new profile",
                  flush=True)
            self._game_panel.silent_deploy()

    def _apply_active_state(self, active_mods: set[str]) -> None:
        """Update checkbox state for all mods without reloading.

        Args:
            active_mods: Set of mod names that should be enabled.
        """
        # Update internal entries
        for entry in self._current_mod_entries:
            entry.enabled = entry.name in active_mods

        # Update model rows to reflect new state
        model = self._mod_list_view.source_model()
        for i, row_data in enumerate(model._rows):
            folder = row_data.folder_name
            new_enabled = folder in active_mods
            if row_data.enabled != new_enabled:
                row_data.enabled = new_enabled

        # Notify view that data changed
        model.dataChanged.emit(
            model.index(0, 0),
            model.index(model.rowCount() - 1, model.columnCount() - 1),
        )

        self._update_active_count()

    def _on_profile_deleted(self, name: str) -> None:
        """Handle profile deletion request."""
        if not self._current_instance_path or not is_valid_profile_name(name):
            return

        profiles_dir = _active_instance_paths(self).profiles
        try:
            profile_path = safe_profile_directory(
                self._current_instance_path, name,
                profiles_root=profiles_dir,
            )
        except ValueError:
            return

        # Profil-Ordner löschen
        if profile_path.exists():
            try:
                shutil.rmtree(profile_path)
            except OSError as e:
                Toast(self, tr("toast.delete_error", error=e.strerror))
                return

        # Gelöschtes Profil aus Order-Datei entfernen
        order_file = profiles_dir / "profiles_order.json"
        if order_file.exists():
            try:
                saved_order = json.loads(order_file.read_text())
                if name in saved_order:
                    saved_order.remove(name)
                    order_file.write_text(json.dumps(saved_order, indent=2))
            except (json.JSONDecodeError, TypeError):
                pass

        # Profile neu laden
        profile_folders = sorted([d.name for d in profiles_dir.iterdir() if d.is_dir() and not d.is_symlink()])
        if not profile_folders:
            (profiles_dir / "Default").mkdir(exist_ok=True)
            profile_folders = ["Default"]

        # Gespeicherte Reihenfolge anwenden
        if order_file.exists():
            try:
                saved_order = json.loads(order_file.read_text())
                ordered = [p for p in saved_order if p in profile_folders]
                ordered += [p for p in profile_folders if p not in saved_order]
                profile_folders = ordered
            except (json.JSONDecodeError, TypeError):
                pass

        # Wenn gelöschtes Profil aktiv war → erstes verbleibendes wählen
        was_active = self._current_profile_path and self._current_profile_path.name == name
        new_active = profile_folders[0] if was_active else self._profile_bar._active_profile

        self._profile_bar.set_profiles(profile_folders, active=new_active)

        if was_active:
            self._on_profile_changed(new_active)

        Toast(self, tr("toast.profile_deleted", name=name))

    def _on_dialog_profile_selected(self, name: str) -> None:
        """Handle profile selection from ProfileDialog."""
        if not is_valid_profile_name(name):
            return
        self._profile_bar.set_profiles(self._get_profile_list(), active=name)
        self._on_profile_changed(name)

    def _get_profile_list(self) -> list[str]:
        """Profil-Liste von Disk lesen (mit gespeicherter Reihenfolge)."""
        if not self._current_instance_path:
            return ["Default"]
        profiles_dir = _active_instance_paths(self).profiles
        if not profiles_dir.is_dir():
            return ["Default"]
        profile_folders = sorted([d.name for d in profiles_dir.iterdir() if d.is_dir() and not d.is_symlink()])
        if not profile_folders:
            return ["Default"]
        order_file = profiles_dir / "profiles_order.json"
        if order_file.exists():
            try:
                saved_order = json.loads(order_file.read_text())
                ordered = [p for p in saved_order if p in profile_folders]
                ordered += [p for p in profile_folders if p not in saved_order]
                profile_folders = ordered
            except (json.JSONDecodeError, TypeError):
                pass
        return profile_folders

    def _on_profiles_reordered(self, order: list[str]) -> None:
        """Handle profile reorder via drag & drop."""
        if not self._current_instance_path:
            return

        profiles_dir = _active_instance_paths(self).profiles
        order_file = profiles_dir / "profiles_order.json"
        order_file.write_text(json.dumps(order, indent=2))

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
        self.statusBar().showMessage(tr("status.separators_collapsed", count=len(separator_folders)), 3000)

    def _expand_all_separators(self) -> None:
        """Expand all separators in the mod list."""
        tree = self._mod_list_view._tree
        tree._collapsed_separators.clear()
        tree._apply_separator_filter()
        self.statusBar().showMessage(tr("status.separators_expanded"), 3000)

    def _ctx_install_mod(self) -> None:
        """Install a mod from an archive file."""
        from anvil.core.mod_installer import ModInstaller

        # Mit "Alle Dateien" als zweitem Filter -- Nexus-CDN-Downloads
        # heissen nach ihrer UUID und tragen keine Endung.
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("dialog.select_mod_archive_single"),
            str(Path.home()),
            tr("dialog.archive_filter"),
        )
        if not path:
            return

        archive_path = Path(path)
        flatten = getattr(self._current_plugin, "GameFlattenArchive", True) if self._current_plugin else True
        se_dir = getattr(self._current_plugin, "ScriptExtenderDir", "") if self._current_plugin else ""
        installer = ModInstaller(
            self._current_instance_path,
            flatten=flatten,
            script_extender_dir=se_dir,
            mods_path=_active_instance_paths(self).mods,
        )
        result = installer.install_from_archive(archive_path)

        if result:
            add_mod_to_modlist(self._current_profile_path, result.name, False)
            self._reload_mod_list()
            self.statusBar().showMessage(tr("status.mod_installed", name=result.name), 5000)
        else:
            QMessageBox.warning(
                self,
                tr("error.install_failed_title"),
                tr("error.install_failed_archive", name=archive_path.name),
            )

    def _ctx_create_empty_mod(self) -> None:
        """Create a new empty mod folder."""
        from anvil.core.mod_metadata import create_default_meta_ini

        name, ok = get_text_input(
            self, tr("dialog.create_empty_mod_title"), tr("dialog.create_empty_mod_prompt"),
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        mods_dir = _active_instance_paths(self).mods
        mod_path = mods_dir / name

        if mod_path.exists():
            QMessageBox.warning(
                self, tr("error.mod_create_error"),
                tr("dialog.mod_exists_message", name=name),
            )
            return

        try:
            mod_path.mkdir(parents=True, exist_ok=True)
            create_default_meta_ini(mod_path, name)
        except OSError as exc:
            QMessageBox.warning(
                self, tr("error.mod_create_error"), str(exc),
            )
            return

        add_mod_to_modlist(self._current_profile_path, name, False)
        self._reload_mod_list()
        self.statusBar().showMessage(tr("status.empty_mod_created", name=name), 5000)

    def _open_export_import(self) -> None:
        """Zeigt den Export/Import-Auswahldialog und leitet weiter."""
        from anvil.dialogs.export_import_dialog import ExportImportDialog

        dialog = ExportImportDialog(self)
        _center_on_parent(dialog)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        action = dialog.action()
        fmt = dialog.format_type()

        if action == "export" and fmt == "csv":
            self._ctx_export_csv()
        elif action == "export" and fmt == "anvilpack":
            self._export_collection()
        elif action == "import" and fmt == "csv":
            self._import_csv()
        elif action == "import" and fmt == "anvilpack":
            self._import_collection()
        elif action == "backup":
            bak = dialog.backup_action()
            if bak == "create":
                self._create_backup()
            else:
                self._restore_backup()

    def _import_csv(self) -> None:
        """CSV importieren: Mods aktivieren/deaktivieren basierend auf CSV."""
        import csv

        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("export_import.import_csv_title"),
            str(Path.home()),
            tr("dialog.csv_filter"),
        )
        if not path:
            return

        if not self._current_profile_path:
            QMessageBox.warning(
                self,
                tr("error.import_failed_title"),
                tr("export_import.import_no_profile"),
            )
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()

            if not raw.strip():
                QMessageBox.warning(
                    self,
                    tr("error.import_failed_title"),
                    tr("export_import.import_empty_csv"),
                )
                return

            # Delimiter auto-erkennen: erste Zeile prüfen
            first_line = raw.split("\n", 1)[0]
            if first_line.count(";") >= first_line.count(","):
                delimiter = ";"
            else:
                delimiter = ","

            reader = csv.reader(raw.strip().splitlines(), delimiter=delimiter)
            header = next(reader, None)
            if not header:
                QMessageBox.warning(
                    self,
                    tr("error.import_failed_title"),
                    tr("export_import.import_empty_csv"),
                )
                return

            # Spalten per Header-Name finden (case-insensitive)
            header_lower = [h.strip().lower() for h in header]
            name_col = None
            active_col = None
            for i, h in enumerate(header_lower):
                if h in ("name", "mod", "mod name", "modname"):
                    name_col = i
                elif h in ("active", "enabled", "aktiv"):
                    active_col = i

            if name_col is None:
                # Fallback: erste Spalte = Name
                name_col = 0
            if active_col is None:
                # Fallback: letzte Spalte oder Spalte 4
                active_col = min(4, len(header) - 1)

            csv_mods: dict[str, bool] = {}
            skipped = 0
            for row in reader:
                if len(row) <= max(name_col, active_col):
                    skipped += 1
                    continue
                mod_name = row[name_col].strip()
                if not mod_name:
                    skipped += 1
                    continue
                active_val = row[active_col].strip().lower()
                active = active_val in ("yes", "1", "true", "ja", "on")
                csv_mods[mod_name] = active

            if not csv_mods:
                QMessageBox.warning(
                    self,
                    tr("error.import_failed_title"),
                    tr("export_import.import_no_mods"),
                )
                return

            # Lookup-Map für case-insensitive Matching
            csv_lower: dict[str, bool] = {k.lower(): v for k, v in csv_mods.items()}

            # Auf aktuelle Modliste anwenden
            changed = 0
            matched = 0
            for entry in self._current_mod_entries:
                if entry.is_separator:
                    continue
                display = entry.display_name or entry.name
                # Exakt → case-insensitive → Ordnername als Fallback
                if display in csv_mods:
                    new_state = csv_mods[display]
                elif display.lower() in csv_lower:
                    new_state = csv_lower[display.lower()]
                elif entry.name in csv_mods:
                    new_state = csv_mods[entry.name]
                elif entry.name.lower() in csv_lower:
                    new_state = csv_lower[entry.name.lower()]
                else:
                    continue
                matched += 1
                if entry.enabled != new_state:
                    entry.enabled = new_state
                    changed += 1

            if changed > 0:
                active_mods = {e.name for e in self._current_mod_entries if e.enabled and not e.is_foreign}
                write_active_mods(self._current_profile_path, active_mods)
                self._reload_mod_list()
                self._do_redeploy()

            not_found = len(csv_mods) - matched
            msg = tr("export_import.import_csv_result",
                      changed=changed, matched=matched,
                      total=len(csv_mods), not_found=not_found)
            QMessageBox.information(self, tr("export_import.import_csv_title"), msg)

        except OSError as exc:
            QMessageBox.warning(
                self,
                tr("error.import_failed_title"),
                str(exc),
            )

    def _ctx_export_csv(self) -> None:
        """Export the mod list as CSV file."""
        import csv

        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("dialog.export_modlist_title"),
            str(Path.home() / "modlist.csv"),
            tr("dialog.csv_filter"),
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["Name", "Category", "Version", "Priority", "Active"])

                for entry in self._current_mod_entries:
                    if entry.is_separator:
                        continue
                    cat_name = ""
                    if entry.category_ids:
                        cat_name = self._category_manager.get_name(entry.category_ids[0]) or ""
                    writer.writerow([
                        entry.display_name or entry.name,
                        cat_name,
                        entry.version,
                        entry.priority,
                        "Yes" if entry.enabled else "No",
                    ])

            self.statusBar().showMessage(tr("status.modlist_exported", path=path), 5000)
        except OSError as exc:
            QMessageBox.warning(
                self, tr("error.export_failed_title"), str(exc),
            )

    # ── Collection Export / Import ──────────────────────────────────

    def _export_collection(self) -> None:
        """Export the current mod setup as a .anvilpack collection."""
        from anvil.core.collection_io import build_manifest, export_collection

        if not self._current_instance_path or not self._current_profile_path:
            return

        # Gather info
        game_name = ""
        game_short = ""
        game_nexus = ""
        if self._current_plugin:
            game_name = getattr(self._current_plugin, "GameName", "")
            game_short = getattr(self._current_plugin, "GameShortName", "")
            game_nexus = (
                getattr(self._current_plugin, "GameNexusName", "")
                or game_short
            )

        # Choose save location — nativer Dialog
        suggested = str(Path.home() / f"{game_name}.anvilpack")
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("collection.save_dialog_title"),
            suggested,
            tr("collection.file_filter"),
        )
        if not path:
            return

        # Ensure extension
        if not path.endswith(".anvilpack"):
            path += ".anvilpack"

        # Dateiname als Collection-Name
        coll_name = Path(path).stem

        # Build manifest
        manifest = build_manifest(
            instance_path=self._current_instance_path,
            profile_path=self._current_profile_path,
            game_name=game_name,
            game_short_name=game_short,
            game_nexus_name=game_nexus,
            collection_name=coll_name,
            mods_path=_active_instance_paths(self).mods,
            profiles_path=_active_instance_paths(self).profiles,
        )

        try:
            cats_path = self._current_instance_path / "categories.json"
            export_collection(manifest, Path(path), cats_path)

            from anvil.widgets.toast import Toast
            Toast(
                self,
                tr(
                    "collection.export_success",
                    name=coll_name,
                    count=len(manifest.mods),
                ),
            )
            self.statusBar().showMessage(
                tr("collection.export_status", path=path), 5000,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                tr("collection.export_error_title"),
                str(exc),
            )

    def _import_collection(self) -> None:
        """Import a .anvilpack collection into the current instance."""
        import zipfile
        from anvil.core.collection_io import (
            read_collection,
            read_collection_categories,
            analyze_collection,
            apply_collection,
        )
        from anvil.dialogs.collection_import_dialog import CollectionImportDialog

        if not self._current_instance_path or not self._current_profile_path:
            return

        # Choose file
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("collection.open_dialog_title"),
            str(Path.home()),
            tr("collection.file_filter"),
        )
        if not path:
            return

        zip_path = Path(path)

        # Read manifest
        try:
            manifest = read_collection(zip_path)
        except (ValueError, zipfile.BadZipFile) as exc:
            QMessageBox.warning(
                self,
                tr("collection.import_error_title"),
                str(exc),
            )
            return

        # Analyze against installed mods
        result = analyze_collection(
            manifest,
            self._current_instance_path,
            mods_path=_active_instance_paths(self).mods,
        )

        # Get current game short name
        current_game_short = ""
        if self._current_plugin:
            current_game_short = getattr(
                self._current_plugin, "GameShortName", ""
            )

        # Show import dialog
        dialog = CollectionImportDialog(
            self,
            result=result,
            current_game_short=current_game_short,
        )
        _center_on_parent(dialog)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Read categories from archive if needed
        cats_data = None
        if dialog.apply_categories():
            cats_data = read_collection_categories(zip_path)

        # Apply collection
        try:
            missing = apply_collection(
                manifest=manifest,
                instance_path=self._current_instance_path,
                profile_path=self._current_profile_path,
                apply_categories=dialog.apply_categories(),
                categories_data=cats_data,
                mods_path=_active_instance_paths(self).mods,
                profiles_path=_active_instance_paths(self).profiles,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                tr("collection.import_error_title"),
                str(exc),
            )
            return

        # Reload
        self._reload_mod_list()
        self._do_redeploy()

        from anvil.widgets.toast import Toast
        Toast(
            self,
            tr(
                "collection.import_success",
                name=manifest.collection_name,
                missing=missing,
            ),
        )

    def _ctx_enable_selected(self, rows: list[int], enabled: bool) -> None:
        """Enable or disable selected mods."""
        model = self._mod_list_view.source_model()
        for row in rows:
            if 0 <= row < len(model._rows):
                r = model._rows[row]
                if r.is_separator:
                    continue
                # Fremde Mods liegen im Spielordner und werden ueber ihren
                # Dateinamen geschaltet. Ohne das hier wuerde der Haken
                # umspringen, die Datei aber aktiv bleiben -- und beim
                # naechsten Laden stuende wieder der alte Stand da.
                if getattr(r, "is_foreign", False):
                    self._toggle_foreign_mod(r, enabled)
                    r.enabled = enabled
                    continue
                r.enabled = enabled
                # BG3: persist via installer (skip frameworks + data-overrides)
                if self._bg3_installer is not None and r.folder_name:
                    if not r.is_data_override and not r.is_framework:
                        if enabled:
                            self._bg3_installer.activate_mod(r.folder_name)
                        else:
                            self._bg3_installer.deactivate_mod(r.folder_name)
            entry = self._entry_for_row(row)
            if entry:
                entry.enabled = enabled
        model.dataChanged.emit(
            model.index(0, 0),
            model.index(model.rowCount() - 1, 0),
            [Qt.ItemDataRole.CheckStateRole],
        )
        if self._bg3_installer is None:
            self._write_current_modlist()
            self._schedule_redeploy()
        self._update_active_count()

    def _ctx_enable_all(self, enabled: bool) -> None:
        """Enable or disable ALL mods."""
        model = self._mod_list_view.source_model()
        all_rows = list(range(model.rowCount()))
        self._ctx_enable_selected(all_rows, enabled)
        msg = tr("status.all_mods_enabled") if enabled else tr("status.all_mods_disabled")
        self.statusBar().showMessage(msg, 3000)

    def _ctx_move_to_separator(self, source_rows: list[int], separator_folder: str) -> None:
        """Move selected mods to the end of the given separator's children."""
        model = self._mod_list_view.source_model()

        # Separator-Position im Model finden
        sep_row = None
        for i, row in enumerate(model._rows):
            if row.is_separator and row.folder_name == separator_folder:
                sep_row = i
                break
        if sep_row is None:
            return

        # Kinder des Ziel-Separators ermitteln
        children = model._get_separator_children(sep_row)
        if children:
            target = children[-1] + 1  # Nach dem letzten Kind
        else:
            target = sep_row + 1  # Direkt nach dem Separator

        # Separatoren und bereits im Ziel-Trenner befindliche Mods herausfiltern
        child_set = set(children)
        filtered = [r for r in source_rows
                    if not model._rows[r].is_separator and r not in child_set]
        if not filtered:
            return

        # Track source separators for child_count updates
        source_sep_counts: dict[str, int] = {}
        for r in filtered:
            src = model._find_parent_separator(r)
            if src:
                source_sep_counts[src] = source_sep_counts.get(src, 0) + 1

        model._move_multiple_rows(filtered, target)

        # Update child_counts: source separators lose mods, target gains them
        for sep_folder, count in source_sep_counts.items():
            if sep_folder != separator_folder:
                model._adjust_child_count(sep_folder, -count)
        model._adjust_child_count(separator_folder, len(filtered))

    def _apply_category_changes(
        self,
        row: int,
        cat_checkboxes: list[tuple[int, object]],
        primary_radios: list[tuple[int, object]],
    ) -> None:
        """Read checkbox/radio state from the closed menu and persist changes."""
        from anvil.core.mod_metadata import write_meta_ini

        entry = self._entry_for_row(row)
        if not entry:
            return

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

        # Build category string (primary first)
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
            tr("status.categories_updated", name=entry.display_name or entry.name), 3000,
        )

    def _toggle_category(self, row: int, cat_id: int) -> None:
        """Toggle a category assignment for a mod."""
        from anvil.core.mod_metadata import write_meta_ini

        entry = self._entry_for_row(row)
        if not entry:
            return
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

        name = self._category_manager.get_name(cat_id) or str(cat_id)
        msg = tr("status.category_added", name=name) if cat_id in ordered else tr("status.category_removed", name=name)
        self.statusBar().showMessage(msg, 3000)

    def _toggle_property(self, row: int, prop_id: int) -> None:
        """Eigene Eigenschaft für einen Mod an-/abwählen (meta.ini)."""
        from anvil.core.mod_metadata import write_meta_ini

        entry = self._entry_for_row(row)
        if not entry:
            return
        current_ids = list(entry.property_ids)
        if prop_id in current_ids:
            current_ids.remove(prop_id)
        else:
            current_ids.append(prop_id)

        entry.property_ids = current_ids
        if entry.install_path:
            write_meta_ini(entry.install_path, {
                "properties": ",".join(str(i) for i in current_ids)})

        # Aktiver Eigenschafts-Filter ggf. neu anwenden
        self._on_filter_changed()

    def _set_primary_category(self, row: int, cat_id: int) -> None:
        """Set a category as primary for a mod."""
        from anvil.core.mod_metadata import write_meta_ini

        entry = self._entry_for_row(row)
        if not entry:
            return

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
        self.statusBar().showMessage(tr("status.primary_category_set", name=name), 3000)

    def _ctx_create_backup(self, row: int) -> None:
        """Create a ZIP backup of the mod folder in .backups/."""
        import zipfile
        entry = self._entry_for_row(row)
        if not entry:
            return
        mod_path = _active_instance_paths(self).mods / entry.name

        if not mod_path.is_dir():
            return

        backups_dir = _active_instance_paths(self).backups
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
                tr("status.backup_created", name=zip_name), 5000,
            )
        except OSError as exc:
            QMessageBox.warning(
                self, tr("error.backup_failed_title"), str(exc),
            )

    def _ctx_query_nexus_info(self, row: int) -> None:
        """Context menu / panel button: Query Nexus Info for a mod."""
        entry = self._entry_for_row(row)
        if not entry:
            return

        nexus_id = entry.nexus_id

        # Step 2: Try to find modID from meta.ini or .meta files
        if nexus_id <= 0:
            from anvil.core.mod_metadata import read_meta_ini
            meta_data = read_meta_ini(Path(entry.install_path))
            inst_file = meta_data.get("installationFile", "")
            downloads_path = self._current_downloads_path

            # 2a: Find .meta file by installationFile name (recursive)
            if inst_file and downloads_path and downloads_path.is_dir():
                for meta_candidate in downloads_path.rglob(inst_file + ".meta"):
                    cp_meta = configparser.ConfigParser()
                    cp_meta.optionxform = str
                    try:
                        cp_meta.read(str(meta_candidate), encoding="utf-8")
                        mid = int(cp_meta.get("General", "modID", fallback="0"))
                        if mid > 0:
                            nexus_id = mid
                            break
                    except (configparser.Error, OSError, ValueError):
                        pass

            # 2b: Fallback — parse modID from installationFile filename
            if nexus_id <= 0 and inst_file:
                from anvil.core.nexus_filename_parser import extract_nexus_mod_id
                parsed_id = extract_nexus_mod_id(inst_file)
                if parsed_id and parsed_id > 0:
                    nexus_id = parsed_id

            # 2c: Search archive filenames matching mod name → get modID from .meta or filename
            if nexus_id <= 0 and downloads_path and downloads_path.is_dir():
                from anvil.core.nexus_filename_parser import extract_nexus_mod_id as _parse_id
                mod_folder = Path(entry.install_path).name
                mod_lower = mod_folder.lower()
                # Search downloads path and its parent (archives may be one level up)
                search_dirs = [downloads_path]
                if downloads_path.parent != downloads_path:
                    search_dirs.append(downloads_path.parent)
                for search_dir in search_dirs:
                    if not search_dir.is_dir():
                        continue
                    for f in search_dir.rglob("*"):
                        if not f.is_file():
                            continue
                        if f.suffix.lower() not in ('.zip', '.rar', '.7z', '.meta'):
                            continue
                        # Check if mod name appears in archive filename
                        fname_lower = f.stem.lower()
                        if f.suffix.lower() == '.meta':
                            fname_lower = Path(f.stem).stem.lower()  # strip .zip from .zip.meta
                        if re.sub(r'[^a-z0-9]', '', mod_lower) not in re.sub(r'[^a-z0-9]', '', fname_lower):
                            continue
                        # Try .meta file first for modID
                        meta_path = f if f.suffix.lower() == '.meta' else Path(str(f) + ".meta")
                        if meta_path.is_file():
                            cp_meta = configparser.ConfigParser()
                            cp_meta.optionxform = str
                            try:
                                cp_meta.read(str(meta_path), encoding="utf-8")
                                mid = int(cp_meta.get("General", "modID", fallback="0"))
                                if mid > 0:
                                    nexus_id = mid
                                    break
                            except (configparser.Error, OSError, ValueError):
                                pass
                        # Fallback: parse modID from archive filename
                        archive_name = f.name if f.suffix.lower() != '.meta' else f.stem
                        parsed = _parse_id(archive_name)
                        if parsed and parsed > 0:
                            nexus_id = parsed
                            break
                    if nexus_id > 0:
                        break

        # Step 3: No ID found → ask user for Nexus URL or mod ID
        if nexus_id <= 0:
            from PySide6.QtWidgets import QInputDialog
            text, ok = QInputDialog.getText(
                self,
                tr("dialog.nexus_query_title"),
                tr("dialog.nexus_query_prompt"),
            )
            if not ok or not text.strip():
                return
            text = text.strip()
            # Parse: full URL (nexusmods.com/.../mods/123) or plain number
            m = re.search(r'/mods/(\d+)', text)
            if m:
                nexus_id = int(m.group(1))
            elif text.isdigit():
                nexus_id = int(text)
            else:
                self.statusBar().showMessage(tr("status.nexus_query_invalid_id"), 5000)
                return
            if nexus_id <= 0:
                return

        self._pending_query_path = entry.install_path
        self._pending_dl_query_path = None

        nexus_slug = ""
        if self._current_plugin:
            nexus_slug = (
                getattr(self._current_plugin, "GameNexusName", "")
                or getattr(self._current_plugin, "GameShortName", "")
            )
        if not nexus_slug:
            self._pending_query_path = None
            self.statusBar().showMessage(tr("status.nexus_no_game_slug"), 5000)
            return

        self._nexus_api.query_mod_info(nexus_slug, nexus_id)
        self.statusBar().showMessage(tr("status.nexus_query_loading"), 5000)

    # ── Batch Query All Nexus Info ────────────────────────────────

    def _ctx_query_all_nexus_info(self) -> None:
        """Query Nexus info for ALL mods in the mod list (batch)."""
        if not self._nexus_api.has_api_key():
            return

        nexus_slug = ""
        if self._current_plugin:
            nexus_slug = (
                getattr(self._current_plugin, "GameNexusName", "")
                or getattr(self._current_plugin, "GameShortName", "")
            )
        if not nexus_slug:
            self.statusBar().showMessage(tr("status.nexus_no_game_slug"), 5000)
            return

        # Collect all non-separator mods with their resolved nexus_id
        queue: list[tuple[Path, int]] = []  # (mod_path, nexus_id)
        skipped: list[str] = []  # display names of mods without nexus_id

        downloads_path = self._current_downloads_path

        for entry in self._current_mod_entries:
            if entry.is_separator:
                continue

            mod_path = Path(entry.install_path)
            nexus_id = entry.nexus_id
            inst_file = ""

            # Fallback 1: meta.ini modid + read installationFile for later
            if nexus_id <= 0:
                from anvil.core.mod_metadata import read_meta_ini
                meta_data = read_meta_ini(mod_path)
                try:
                    nexus_id = int(meta_data.get("modid", "0"))
                except (ValueError, TypeError):
                    nexus_id = 0
                inst_file = meta_data.get("installationFile", "")

            # Fallback 2: .meta file via installationFile
                if inst_file and downloads_path and downloads_path.is_dir():
                    for meta_candidate in downloads_path.rglob(inst_file + ".meta"):
                        cp_meta = configparser.ConfigParser()
                        cp_meta.optionxform = str
                        try:
                            cp_meta.read(str(meta_candidate), encoding="utf-8")
                            mid = int(cp_meta.get("General", "modID", fallback="0"))
                            if mid > 0:
                                nexus_id = mid
                                break
                        except (configparser.Error, OSError, ValueError):
                            pass

            # Fallback 3: parse modID from installationFile filename
            if nexus_id <= 0 and inst_file:
                from anvil.core.nexus_filename_parser import extract_nexus_mod_id
                parsed_id = extract_nexus_mod_id(inst_file)
                if parsed_id and parsed_id > 0:
                    nexus_id = parsed_id

            # Fallback 4: search downloads for matching archive
            if nexus_id <= 0 and downloads_path and downloads_path.is_dir():
                from anvil.core.nexus_filename_parser import extract_nexus_mod_id as _parse_id
                mod_folder = mod_path.name
                mod_lower = mod_folder.lower()
                search_dirs = [downloads_path]
                if downloads_path.parent != downloads_path:
                    search_dirs.append(downloads_path.parent)
                for search_dir in search_dirs:
                    if not search_dir.is_dir():
                        continue
                    for f in search_dir.rglob("*"):
                        if not f.is_file():
                            continue
                        if f.suffix.lower() not in ('.zip', '.rar', '.7z', '.meta'):
                            continue
                        fname_lower = f.stem.lower()
                        if f.suffix.lower() == '.meta':
                            fname_lower = Path(f.stem).stem.lower()
                        if re.sub(r'[^a-z0-9]', '', mod_lower) not in re.sub(r'[^a-z0-9]', '', fname_lower):
                            continue
                        meta_path = f if f.suffix.lower() == '.meta' else Path(str(f) + ".meta")
                        if meta_path.is_file():
                            cp_meta = configparser.ConfigParser()
                            cp_meta.optionxform = str
                            try:
                                cp_meta.read(str(meta_path), encoding="utf-8")
                                mid = int(cp_meta.get("General", "modID", fallback="0"))
                                if mid > 0:
                                    nexus_id = mid
                                    break
                            except (configparser.Error, OSError, ValueError):
                                pass
                        archive_name = f.name if f.suffix.lower() != '.meta' else f.stem
                        parsed = _parse_id(archive_name)
                        if parsed and parsed > 0:
                            nexus_id = parsed
                            break
                    if nexus_id > 0:
                        break

            if nexus_id > 0:
                queue.append((mod_path, nexus_id))
            else:
                skipped.append(entry.display_name or entry.name)

        if not queue and skipped:
            QMessageBox.information(
                self,
                tr("batch_query.title"),
                tr("batch_query.no_ids_found", count=len(skipped)),
            )
            return

        if not queue:
            self.statusBar().showMessage(tr("batch_query.no_mods"), 3000)
            return

        total = len(queue)

        # Initialize batch state
        self._batch_query_queue = queue
        self._batch_query_slug = nexus_slug
        self._batch_query_total = total
        self._batch_query_done = 0
        self._batch_query_success = 0
        self._batch_query_errors = 0
        self._batch_query_skipped = skipped
        self._batch_query_active = True

        self.statusBar().showMessage(
            tr("batch_query.starting", total=total, skipped=len(skipped)), 5000,
        )
        Toast(self, tr("batch_query.starting", total=total, skipped=len(skipped)), duration=5000)

        # Start first request
        self._batch_query_next()

    def _batch_query_next(self) -> None:
        """Send the next request from the batch queue."""
        # Guard: Teardown setzt _batch_query_active auf False.
        # Ohne diesen Guard wuerde Queue-Clearing → _batch_query_finished() →
        # _reload_mod_list() einen ungewollten Reload ausloesen.
        if not getattr(self, "_batch_query_active", False):
            return
        if self._batch_query_queue:
            mod_path, nexus_id = self._batch_query_queue.pop(0)
            self._pending_batch_query_path = mod_path
        else:
            self._batch_query_finished()
            return

        self._nexus_api.query_mod_info(self._batch_query_slug, nexus_id)

        done = self._batch_query_done
        total = self._batch_query_total
        self.statusBar().showMessage(
            tr("batch_query.progress", current=done + 1, total=total), 0,
        )

    def _batch_query_finished(self) -> None:
        """Show results dialog when batch query completes."""
        self._batch_query_active = False
        self._reload_mod_list()

        success = self._batch_query_success
        errors = self._batch_query_errors
        skipped = self._batch_query_skipped
        total_attempted = self._batch_query_total

        Toast(self, tr("batch_query.result_updated", count=success, total=total_attempted), duration=5000)

        msg_parts = [tr("batch_query.result_updated", count=success, total=total_attempted)]

        if errors > 0:
            msg_parts.append(tr("batch_query.result_errors", count=errors))

        if skipped:
            msg_parts.append(tr("batch_query.result_skipped", count=len(skipped)))
            # Show max 20 mod names
            show_names = skipped[:20]
            msg_parts.append("\n".join(f"  • {n}" for n in show_names))
            if len(skipped) > 20:
                msg_parts.append(f"  ... +{len(skipped) - 20}")

        QMessageBox.information(
            self,
            tr("batch_query.title"),
            "\n\n".join(msg_parts),
        )

    def _save_framework_cache(self, fw_name: str, data: dict, slug: str = "") -> None:
        """Save Nexus query result for a framework to framework_cache.json."""
        if not self._current_instance_path:
            return
        import json
        from datetime import datetime, timezone

        cache_path = self._current_instance_path / "framework_cache.json"
        cache: dict = {}
        if cache_path.is_file():
            try:
                cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        nexus_slug = slug or getattr(self, "_batch_query_slug", "")
        cache[fw_name] = {
            "nexus_id": data.get("mod_id", 0),
            "nexus_name": data.get("name", ""),
            "nexus_version": data.get("version", ""),
            "nexus_author": data.get("author", ""),
            "nexus_summary": data.get("summary", ""),
            "nexus_category": data.get("category_id", 0),
            "nexus_url": f"https://www.nexusmods.com/{nexus_slug}/mods/{data.get('mod_id', 0)}",
            "last_query": datetime.now(timezone.utc).isoformat(),
        }

        try:
            cache_path.write_text(
                json.dumps(cache, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass

    # ── Separate framework Nexus query ──────────────────────────

    def _query_framework_nexus(self) -> None:
        """Query installed frameworks on NexusMods (separate from mod batch query)."""
        if not self._nexus_api.has_api_key():
            Toast(self, tr("fw.query_no_apikey"), duration=3000)
            return

        if self._batch_query_active or self._fw_query_active:
            return

        nexus_slug = ""
        if self._current_plugin:
            nexus_slug = (
                getattr(self._current_plugin, "GameNexusName", "")
                or getattr(self._current_plugin, "GameShortName", "")
            )
        if not nexus_slug:
            self.statusBar().showMessage(tr("status.nexus_no_game_slug"), 5000)
            return

        fw_queue: list[tuple[str, int]] = []
        if self._current_plugin:
            for fw, installed in self._current_plugin.get_installed_frameworks():
                if fw.nexus_id > 0 and installed:
                    fw_queue.append((fw.name, fw.nexus_id))

        if not fw_queue:
            Toast(self, tr("fw.query_no_frameworks"), duration=3000)
            return

        self._fw_query_queue = fw_queue
        self._fw_query_slug = nexus_slug
        self._fw_query_total = len(fw_queue)
        self._fw_query_done = 0
        self._fw_query_success = 0
        self._fw_query_errors = 0
        self._fw_query_active = True
        self._pending_fw_query_name = ""

        Toast(self, tr("fw.query_starting", total=len(fw_queue)), duration=3000)
        self.statusBar().showMessage(
            tr("fw.query_starting", total=len(fw_queue)), 5000,
        )
        self._fw_query_next()

    def _fw_query_next(self) -> None:
        """Send the next framework query request."""
        # Guard: Teardown setzt _fw_query_active auf False und leert die Queue.
        # Ohne diesen Guard wuerde Queue-Clearing → _fw_query_finished() →
        # _reload_mod_list() einen ungewollten Reload ausloesen.
        if not self._fw_query_active:
            return
        if not self._fw_query_queue:
            self._fw_query_finished()
            return

        fw_name, nexus_id = self._fw_query_queue.pop(0)
        self._pending_fw_query_name = fw_name

        self._nexus_api.query_mod_info(self._fw_query_slug, nexus_id)

        done = self._fw_query_done
        total = self._fw_query_total
        self.statusBar().showMessage(
            tr("fw.query_progress", current=done + 1, total=total), 0,
        )

    def _fw_query_finished(self) -> None:
        """Show results when framework query completes."""
        self._fw_query_active = False
        self._reload_mod_list()

        success = self._fw_query_success
        errors = self._fw_query_errors
        total = self._fw_query_total

        msg = tr("fw.query_result", count=success, total=total)
        if errors > 0:
            msg += "\n" + tr("fw.query_errors", count=errors)

        Toast(self, msg, duration=5000)
        self.statusBar().showMessage(msg, 5000)

    def _on_dl_query_info(self, archive_path: str) -> None:
        """Handle 'Query Nexus Info' from Downloads tab context menu."""
        from anvil.core.nexus_filename_parser import extract_nexus_mod_id

        # 1. Try .meta modID
        mod_id_str = self._game_panel._read_meta_mod_id(archive_path)
        mod_id = 0
        if mod_id_str:
            try:
                mod_id = int(mod_id_str)
            except ValueError:
                pass

        # 2. Filename parsing
        if mod_id <= 0:
            filename = Path(archive_path).name
            parsed_id = extract_nexus_mod_id(filename)
            if parsed_id and parsed_id > 0:
                answer = QMessageBox.question(
                    self,
                    tr("game_panel.query_nexus_info"),
                    tr("game_panel.query_nexus_parsed_id", id=parsed_id),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    mod_id = parsed_id

        # 3. Manual input
        if mod_id <= 0:
            text, ok = get_text_input(
                self, tr("game_panel.query_nexus_info"),
                tr("game_panel.query_nexus_enter_id"),
            )
            if not ok or not text.strip():
                return
            try:
                mod_id = int(text.strip())
                if mod_id <= 0:
                    raise ValueError
            except ValueError:
                self.statusBar().showMessage(tr("status.nexus_query_invalid_id"), 5000)
                return

        # 4. Fire API request
        self._pending_dl_query_path = archive_path
        self._pending_query_path = None

        nexus_slug = ""
        if self._current_plugin:
            nexus_slug = (
                getattr(self._current_plugin, "GameNexusName", "")
                or getattr(self._current_plugin, "GameShortName", "")
            )
        if not nexus_slug:
            return

        self._nexus_api.query_mod_info(nexus_slug, mod_id)
        self.statusBar().showMessage(tr("status.nexus_query_loading"), 5000)

    def _update_download_meta(self, archive_path: str, nexus_data: dict) -> None:
        """Update .meta neben Archiv mit Nexus-Daten. Bestehende Felder bleiben erhalten."""
        meta_path = Path(archive_path + ".meta")
        cp = configparser.ConfigParser()
        cp.optionxform = str
        if meta_path.is_file():
            try:
                cp.read(str(meta_path), encoding="utf-8")
            except Exception as exc:
                print(f"[META] parse failed: {meta_path}: {exc}", flush=True)
        if not cp.has_section("General"):
            cp.add_section("General")
        cp.set("General", "modID", str(nexus_data.get("mod_id", 0)))
        cp.set("General", "modName", nexus_data.get("name", ""))
        cp.set("General", "name", nexus_data.get("name", ""))
        cp.set("General", "version", nexus_data.get("version", ""))
        cp.set("General", "description", nexus_data.get("summary", ""))
        with open(meta_path, "w", encoding="utf-8") as f:
            cp.write(f)

    def _load_nexus_categories(self, instance_path: Path) -> None:
        """Load Nexus categories from cache or trigger API call if expired."""
        s = self._settings()
        if not s.value("Nexus/category_mapping_enabled", True, type=bool):
            return
        if not self._nexus_api.has_api_key() or not self._current_plugin:
            return
        from anvil.core.nexus_categories import NexusCategoryCache
        cache = NexusCategoryCache(instance_path)
        if cache.load() and not cache.is_expired():
            self._populate_nexus_filter_chips(cache)
            return  # Cache valid
        nexus_slug = (
            getattr(self._current_plugin, "GameNexusName", "")
            or getattr(self._current_plugin, "GameShortName", "")
        )
        if nexus_slug:
            self._nexus_api.get_game_info(nexus_slug)

    def _populate_nexus_filter_chips(self, cache=None) -> None:
        """Build Nexus category chips from cache + current mod entries."""
        if cache is None:
            _name = self.instance_manager.current_instance()
            idata = self.instance_manager.load_instance(_name) if _name else None
            if not idata:
                return
            from anvil.core.nexus_categories import NexusCategoryCache
            inst_path = self.instance_manager.instances_path() / _name
            cache = NexusCategoryCache(inst_path)
            if not cache.load():
                return

        # Collect unique nexus_category IDs actually used by mods
        used_ids: set[int] = set()
        for entry in self._current_mod_entries:
            if entry.nexus_category > 0:
                used_ids.add(entry.nexus_category)

        # Build chip list: only categories that mods actually use
        chips: list[dict] = []
        seen: set[int] = set()
        for cid in sorted(used_ids):
            if cid in seen:
                continue
            seen.add(cid)
            name = cache.find_nexus_category(cid)
            if name:
                chips.append({"id": cid, "name": name})

        # Skip rebuild if chip set is unchanged — avoids visible re-layout flash
        new_ids = frozenset(c["id"] for c in chips)
        if getattr(self, "_last_nexus_chip_ids", None) == new_ids:
            return
        self._last_nexus_chip_ids = new_ids
        self._filter_panel.set_nexus_categories(chips)

    def _on_nexus_load_requested(self) -> None:
        """User clicked 'Laden' in filter panel — force-refresh Nexus categories."""
        if not self._nexus_api.has_api_key() or not self._current_plugin:
            self.statusBar().showMessage(tr("status.nexus_api_key_missing"), 5000)
            return
        nexus_slug = (
            getattr(self._current_plugin, "GameNexusName", "")
            or getattr(self._current_plugin, "GameShortName", "")
        )
        if nexus_slug:
            self.statusBar().showMessage(tr("status.nexus_categories_loading"), 3000)
            self._nexus_api.get_game_info(nexus_slug)

    def _ctx_auto_assign_categories(self) -> None:
        """Batch-assign Nexus categories to all mods."""
        _name = self.instance_manager.current_instance()
        idata = self.instance_manager.load_instance(_name) if _name else None
        if not idata:
            return
        inst_path = self.instance_manager.instances_path() / _name
        from anvil.core.nexus_categories import NexusCategoryCache, assign_nexus_categories
        cache = NexusCategoryCache(inst_path)
        if not cache.load():
            self.statusBar().showMessage(tr("status.no_nexus_category"), 5000)
            return
        cat_mgr = self._filter_panel._category_manager
        if not cat_mgr:
            return
        count = 0
        for entry in self._current_mod_entries:
            if entry.is_separator or entry.nexus_category <= 0:
                continue
            added = assign_nexus_categories(
                entry.install_path, entry.nexus_category, cache, cat_mgr)
            if added:
                count += 1
        self.statusBar().showMessage(
            tr("status.categories_assigned", count=count), 5000)
        if count > 0:
            self._filter_panel.set_categories(cat_mgr.all_categories())
            self._reload_mod_list()

    def _ctx_reassign_category(self, row: int) -> None:
        """Assign Nexus category to mod (merge, not overwrite)."""
        entry = self._entry_for_row(row)
        if not entry or entry.nexus_id <= 0:
            return
        _name = self.instance_manager.current_instance()
        idata = self.instance_manager.load_instance(_name) if _name else None
        if not idata:
            return
        inst_path = self.instance_manager.instances_path() / _name
        from anvil.core.nexus_categories import NexusCategoryCache, assign_nexus_categories
        cache = NexusCategoryCache(inst_path)
        if not cache.load():
            self.statusBar().showMessage(
                tr("status.no_nexus_category"), 5000)
            return
        nexus_cat = entry.nexus_category
        if nexus_cat <= 0:
            self.statusBar().showMessage(
                tr("status.no_nexus_category"), 5000)
            return
        cat_mgr = self._filter_panel._category_manager
        if not cat_mgr:
            return
        added = assign_nexus_categories(entry.install_path, nexus_cat, cache, cat_mgr)
        if added:
            cat_name = cat_mgr.get_name(added[0]) if added else ""
            self.statusBar().showMessage(
                tr("status.category_assigned_single",
                   category=cat_name, name=entry.display_name or entry.name), 5000)
            self._filter_panel.set_categories(cat_mgr.all_categories())
            self._reload_mod_list()
        else:
            self.statusBar().showMessage(
                tr("status.category_assigned_single",
                   category="—", name=entry.display_name or entry.name), 5000)

    def _ctx_visit_nexus(self, row: int) -> None:
        """Open the mod's Nexus Mods page in the browser."""
        entry = self._entry_for_row(row)
        if not entry:
            return
        if entry.nexus_id <= 0:
            return

        # Get Nexus game slug from plugin (self._current_plugin, NOT _game_panel)
        nexus_slug = ""
        if self._current_plugin:
            nexus_slug = getattr(self._current_plugin, "GameNexusName", "") or getattr(self._current_plugin, "GameShortName", "")
        if not nexus_slug:
            nexus_slug = "site"

        url = f"https://www.nexusmods.com/{nexus_slug}/mods/{entry.nexus_id}"
        host_open_url(url)

    def _ctx_rename_mod(self, row: int) -> None:
        """Rename a mod (folder + modlist.txt)."""
        entry = self._entry_for_row(row)
        if not entry:
            return
        old_name = entry.name
        display = entry.display_name or old_name

        new_name, ok = get_text_input(
            self, tr("dialog.rename_mod_title"), tr("dialog.rename_mod_prompt"), text=display,
        )
        if not ok or not new_name.strip() or new_name.strip() == display:
            return
        new_name = new_name.strip()

        old_path = _active_instance_paths(self).mods / old_name
        new_path = _active_instance_paths(self).mods / new_name

        if new_path.exists():
            QMessageBox.warning(
                self, tr("error.rename_failed_title"),
                tr("dialog.mod_exists_message", name=new_name),
            )
            return

        try:
            old_path.rename(new_path)
        except OSError as exc:
            QMessageBox.warning(
                self, tr("error.rename_failed_title"), str(exc),
            )
            return

        profiles_dir = _active_instance_paths(self).profiles
        rename_mod_globally(profiles_dir, old_name, new_name)
        self._update_install_meta_name(old_name, new_name)
        # Anzeigename (meta.ini "name") nachziehen, sonst zeigt die Liste den alten Namen
        from anvil.core.mod_metadata import write_meta_ini
        write_meta_ini(new_path, {"name": new_name})
        # Update mod index cache for the renamed mod
        if self._mod_index is not None:
            self._mod_index.rename(old_name, new_name)
        self._reload_mod_list()
        self._do_redeploy()
        self._game_panel.refresh_downloads()
        self.statusBar().showMessage(tr("status.renamed", old=old_name, new=new_name), 5000)

    def _ctx_reinstall_mod(self, row: int) -> None:
        """Reinstall a mod from its archive in the configured downloads folder."""
        entry = self._entry_for_row(row)
        if not entry:
            return
        downloads_path = _active_instance_paths(self).downloads
        print(f"DEBUG reinstall: _current_downloads_path={self._current_downloads_path}, downloads_path={downloads_path}", flush=True)

        if not downloads_path.is_dir():
            QMessageBox.warning(
                self, tr("dialog.reinstall_title"),
                tr("status.no_downloads_folder"),
            )
            return

        # Find matching archive by mod name or installationFile from meta.ini
        archive = None
        mod_lower = entry.name.lower()

        # 1. Try exact match from meta.ini installationFile
        from anvil.core.mod_metadata import read_meta_ini
        mod_dir = _active_instance_paths(self).mods / entry.name
        meta = read_meta_ini(mod_dir)
        inst_file = meta.get("installationFile", "")
        if inst_file:
            candidate = downloads_path / inst_file
            if candidate.is_file():
                archive = candidate

        # 2. Fuzzy match: all mod name words must appear in archive name
        if not archive:
            mod_words = [w for w in mod_lower.replace("-", " ").replace("_", " ").split() if len(w) > 1]
            best_score = 0
            for f in downloads_path.iterdir():
                if f.is_file() and f.suffix.lower() in ('.zip', '.rar', '.7z'):
                    stem = f.stem.lower()
                    # Exact substring match (original behavior)
                    if mod_lower in stem:
                        archive = f
                        break
                    # Word match: count how many mod words appear in filename
                    matches = sum(1 for w in mod_words if w in stem)
                    if matches > best_score and matches >= len(mod_words) * 0.6:
                        best_score = matches
                        archive = f

        if not archive:
            QMessageBox.information(
                self, tr("dialog.reinstall_title"),
                tr("dialog.no_matching_archive", name=entry.name, path=str(downloads_path)),
            )
            return

        # Pass existing mod path for FOMOD Selection Memory
        mod_path = _active_instance_paths(self).mods / entry.name
        self._install_archives([archive], reinstall_mod_path=mod_path)
        self._game_panel.refresh_downloads()
        self._do_redeploy()

    def _ctx_remove_mods(self, rows: list[int]) -> None:
        """Remove selected mods (folder + modlist.txt entry)."""
        if self._refuse_while_game_runs(tr("dialog.remove_mod_title")):
            return
        entries = []
        for row in rows:
            entry = self._entry_for_row(row)
            if entry:
                entries.append(entry)
        if not entries:
            return

        # BG3 mode: entry.name is UUID, use bg3_installer.uninstall_mod()
        if self._bg3_installer is not None:
            display_names = [e.display_name or e.name for e in entries]
            if len(display_names) == 1:
                msg = tr("dialog.uninstall_mod_message", name=display_names[0])
            else:
                names_list = "\n".join(f"  • {n}" for n in display_names)
                msg = tr("dialog.remove_mod_multi", count=len(display_names), list=names_list)

            reply = QMessageBox.question(
                self, tr("dialog.uninstall_mod_title"), msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            for entry in entries:
                self._bg3_installer.uninstall_mod(entry.name, "")
            self._bg3_reload_mod_list()
            self.statusBar().showMessage(
                tr("status.uninstalled", name=", ".join(display_names)), 5000)
            return

        names = [e.name for e in entries]

        if len(names) == 1:
            msg = tr("dialog.remove_mod_single", name=names[0])
        else:
            names_list = "\n".join(f"  • {n}" for n in names)
            msg = tr("dialog.remove_mod_multi", count=len(names), list=names_list)

        reply = QMessageBox.question(
            self, tr("dialog.remove_mod_title"), msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        profiles_dir = _active_instance_paths(self).profiles
        # Einmal vor der Schleife: die Zuordnung liest die Dateilisten aller
        # Mods, und nach dem ersten rmtree stimmt sie ohnehin nicht mehr.
        fw_zuordnung = self._framework_mod_folders()
        for name in names:
            # Remove from group before deleting
            self._group_manager.remove_member(name)
            # Gehoerte die Mod zu einem Framework, muss auch dessen Eintrag
            # weg. Sonst steht das Framework weiter im Zustand, waehrend der
            # Ordner laengst geloescht ist -- und Anvil meldet es als
            # installiert, obwohl nichts mehr da ist.
            fw_name = fw_zuordnung.get(name, "")
            mod_path = _active_instance_paths(self).mods / name
            if mod_path.is_dir():
                shutil.rmtree(mod_path)
            remove_mod_globally(profiles_dir, name)
            if fw_name and self._current_instance_path:
                framework_state.remove(self._current_instance_path, fw_name)
            self._clear_install_meta(name)
            # Remove deleted mod from index cache
            if self._mod_index is not None:
                self._mod_index.invalidate(name)

        self._reload_mod_list()
        self._do_redeploy()
        self._game_panel.refresh_downloads()
        self.statusBar().showMessage(tr("status.removed", names=", ".join(names)), 5000)

    def _ctx_open_explorer(self, row: int) -> None:
        """Open the mod folder in the file manager."""
        entry = self._entry_for_row(row)
        if not entry:
            return
        mod_path = _active_instance_paths(self).mods / entry.name
        if mod_path.is_dir():
            host_open_path(str(mod_path))

    def _ctx_show_info(self, row: int) -> None:
        """Show mod information dialog."""
        entry = self._entry_for_row(row)
        if not entry:
            return
        mod_path = _active_instance_paths(self).mods / entry.name

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
        dlg.setWindowTitle(tr("dialog.info_title", name=entry.display_name or entry.name))
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
        _center_on_parent(dlg)
        dlg.exec()

    def _reload_mod_list(self) -> None:
        """Reload mod list from disk and update UI.

        Dispatches to BG3-specific reload when a BG3 instance is active.
        """
        if self._bg3_installer is not None:
            self._bg3_reload_mod_list()
            return

        # Rebuild mod file index (only re-scans changed mods)
        if self._mod_index is not None:
            self._mod_index.rebuild()

        include_ext = self._settings().value("ModList/show_external_mods", True, type=bool)
        self._current_mod_entries = scan_mods_directory(
            self._current_instance_path, self._current_profile_path,
            include_external=include_ext,
            mod_index=self._mod_index,
            mods_path=_active_instance_paths(self).mods,
            profiles_path=_active_instance_paths(self).profiles,
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
        # Cleanup orphaned group members
        if self._current_instance_path:
            mods_dir = _active_instance_paths(self).mods
            if mods_dir.is_dir():
                existing_folders = {d.name for d in mods_dir.iterdir() if d.is_dir()}
                self._group_manager.cleanup_orphans(existing_folders)
        conflict_data = self._compute_conflict_data()
        # Wie oben: nur gesperrte Frameworks bleiben verborgen.
        offen = self._unlocked_framework_mods()
        visible_entries = [
            e for e in self._current_mod_entries
            if not e.is_direct_install or e.name in offen
        ]
        mod_rows = [mod_entry_to_row(e, conflict_data, self._group_manager) for e in visible_entries]
        self._mod_list_view.source_model().set_mods(mod_rows)
        self._mod_list_view._proxy_model.set_mod_entries(visible_entries)
        self._mod_list_view._tree._apply_separator_filter()
        self._update_active_count()
        self._populate_nexus_filter_chips()

        # Refresh framework status (nach Framework-Installation)
        if self._current_plugin is not None:
            fw_list = [
                self._build_fw_dict(fw, installed)
                for fw, installed in self._current_plugin.get_installed_frameworks()
            ]
            self._mod_list_view.load_frameworks(fw_list)

    # ── Nexus API integration ─────────────────────────────────────────

    def _handle_nxm_link(self, nxm_link) -> None:
        """Process an nxm:// link: request download URLs from Nexus API."""
        if not self._nexus_api.has_api_key():
            QMessageBox.warning(
                self, "Nexus API",
                tr("status.nexus_api_key_missing"),
            )
            return

        self.statusBar().showMessage(
            tr("status.nexus_loading", id=nxm_link.mod_id), 5000,
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

        # Store nxm link keyed by (mod_id, file_id) so rapid clicks don't overwrite
        if not hasattr(self, "_pending_nxm_links"):
            self._pending_nxm_links = {}
        self._pending_nxm_links[(nxm_link.mod_id, nxm_link.file_id)] = {
            "nxm": nxm_link,
            "mod_name": "",
            "mod_version": "",
        }

    def _cache_known_servers(self, data: list) -> None:
        """Merkt die von Nexus gelieferten Server-Bezeichner (für die Settings-Auswahl).

        Defensiv: Caching darf einen Download niemals stören.
        """
        try:
            ids = []
            for entry in data:
                sid = _server_id(entry)
                if sid and sid not in ids:
                    ids.append(sid)
            if not ids:
                return
            settings = self._settings()
            raw = settings.value("Nexus/known_servers", "", type=str)
            try:
                existing = json.loads(raw) if raw else []
            except (ValueError, TypeError):
                existing = []
            merged = [str(s) for s in existing if s] if isinstance(existing, list) else []
            for sid in ids:
                if sid not in merged:
                    merged.append(sid)
            merged = merged[-20:]
            settings.setValue("Nexus/known_servers", json.dumps(merged))
        except Exception:  # noqa: BLE001 — Caching darf den Download nie killen
            pass

    def _select_download_server(self, data: list) -> str:
        """Wählt die Download-URL aus der Server-Liste.

        Premium/Einzel-Server-Antworten nutzen den einzigen Eintrag. Bei mehreren
        Servern (Free-Accounts) wird der bevorzugte Server gematcht; ohne Treffer
        oder Präferenz fällt es auf den ersten Eintrag zurück (= bisheriges Verhalten).
        """
        if not data:
            return ""
        if len(data) <= 1:
            return data[0].get("URI", "") if isinstance(data[0], dict) else ""
        pref = self._settings().value("Nexus/preferred_server", "", type=str)
        if pref:
            for entry in data:
                if isinstance(entry, dict) and _server_id(entry) == pref:
                    uri = entry.get("URI", "")
                    if uri:
                        return uri
        first = data[0]
        return first.get("URI", "") if isinstance(first, dict) else ""

    def _on_nexus_response(self, tag: str, data: object) -> None:
        """Handle Nexus API responses."""
        if tag.startswith("download_link:") and isinstance(data, list) and data:
            # Download link response — start download
            # Parse tag: "download_link:{game}:{mod_id}:{file_id}"
            parts = tag.split(":")
            if len(parts) < 4:
                return
            try:
                tag_mod_id = int(parts[2])
                tag_file_id = int(parts[3])
            except (ValueError, IndexError):
                return

            pending = getattr(self, "_pending_nxm_links", {})
            entry = pending.get((tag_mod_id, tag_file_id))
            if not entry:
                return
            nxm = entry["nxm"]

            # Gelieferte Server für die Settings-Auswahl merken
            self._cache_known_servers(data)
            # Bevorzugten Server wählen (Fallback: erster Eintrag)
            url = self._select_download_server(data)
            if not url:
                self.statusBar().showMessage(tr("status.nexus_no_link"), 5000)
                return

            # Determine filename from URL
            from urllib.parse import urlparse
            parsed = urlparse(url)
            file_name = Path(parsed.path).name or f"mod_{nxm.mod_id}_{nxm.file_id}.zip"

            dm = self._game_panel.download_manager()
            dl_id = dm.enqueue(
                url=url,
                file_name=file_name,
                game=nxm.game,
                mod_id=nxm.mod_id,
                file_id=nxm.file_id,
                mod_name=entry["mod_name"],
                mod_version=entry["mod_version"],
            )
            self.statusBar().showMessage(
                tr("status.nexus_download_started", name=file_name), 5000,
            )

            # Switch to Downloads tab
            self._game_panel._tabs.setCurrentIndex(3)
            pending.pop((tag_mod_id, tag_file_id), None)

        elif tag.startswith("mod_info:") and isinstance(data, dict):
            # Store mod name/version — match by mod_id to correct pending entry
            parts = tag.split(":")
            if len(parts) >= 3:
                try:
                    tag_mod_id = int(parts[2])
                except (ValueError, IndexError):
                    tag_mod_id = None
                if tag_mod_id is not None:
                    pending = getattr(self, "_pending_nxm_links", {})
                    for key, entry in pending.items():
                        if key[0] == tag_mod_id:
                            entry["mod_name"] = data.get("name", "")
                            entry["mod_version"] = data.get("version", "")

        elif tag.startswith("update_check:") and isinstance(data, dict):
            # ── Post-install update check ─────────────────────────
            pending = getattr(self, "_pending_update_check", None)
            if pending:
                name, nexus_id, installed_version, mod_path = pending
                self._pending_update_check = None
                newest_version = data.get("version", "")
                if mod_path and mod_path.exists() and newest_version:
                    from anvil.core.mod_metadata import write_meta_ini
                    write_meta_ini(mod_path, {"newestVersion": newest_version})
                    if installed_version and installed_version != newest_version:
                        msg = tr(
                            "status.update_available_mod",
                            name=name,
                            current=installed_version,
                            newest=newest_version,
                        )
                        self._log_panel.add_log("info", msg)
                        self.statusBar().showMessage(msg, 8000)
            # Schedule next check with 1s delay
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1000, self._update_check_next)

        elif tag.startswith("fw_update:") and isinstance(data, dict):
            name = tag.split(":", 1)[1]
            current = getattr(self, "_fw_update_check_current", "") or ""
            newest = str(data.get("version", "") or "")
            if newest and self._current_instance_path:
                if not current:
                    framework_state.set_entry(
                        self._current_instance_path, name, version=newest,
                    )
                    current = newest
            if newest and current and newest != current:
                txt = tr("status.fw_update_available",
                         name=name, current=current, newest=newest)
                self._log_panel.add_log("info", txt)
                QMessageBox.information(
                    self, tr("dialog.fw_update_title"), txt,
                )
            else:
                txt = tr("status.fw_no_update",
                         name=name, version=newest or current or "?")
                self._log_panel.add_log("info", txt)
                QMessageBox.information(
                    self, tr("dialog.fw_update_title"), txt,
                )
            self._fw_update_check_name = ""
            self._fw_update_check_current = ""
            self._reload_mod_list()

        elif tag.startswith("game_categories:") and isinstance(data, dict):
            # Category cache update
            categories = data.get("categories", [])
            if categories and self._current_plugin:
                from anvil.core.nexus_categories import NexusCategoryCache
                _name = self.instance_manager.current_instance()
                idata = self.instance_manager.load_instance(_name) if _name else None
                if idata:
                    inst_path = self.instance_manager.instances_path() / _name
                    if inst_path.exists():
                        cache = NexusCategoryCache(inst_path)
                        game_slug = tag.split(":", 1)[1]
                        cache.save(game_slug, categories)
                        self._log_panel.add_log("info",
                            tr("status.nexus_categories_loaded", count=len(categories)))
                        self._populate_nexus_filter_chips(cache)

        elif tag.startswith("query_mod_info:") and isinstance(data, dict):
            # ── Separate framework query mode ─────────────────────
            fw_qname = self._pending_fw_query_name
            if self._fw_query_active and fw_qname:
                self._pending_fw_query_name = ""
                self._save_framework_cache(fw_qname, data, slug=self._fw_query_slug)
                self._fw_query_success += 1
                self._fw_query_done += 1
                from PySide6.QtCore import QTimer
                QTimer.singleShot(1000, self._fw_query_next)
                return

            # ── Batch query mode ──────────────────────────────────
            batch_path = getattr(self, "_pending_batch_query_path", None)
            if getattr(self, "_batch_query_active", False) and batch_path:
                self._pending_batch_query_path = None

                if batch_path.exists():
                    from anvil.core.mod_metadata import write_meta_ini
                    from datetime import datetime, timezone
                    nexus_slug = self._batch_query_slug

                    # SAFE fields only — NEVER touch name, version, description
                    write_meta_ini(batch_path, {
                        "modid": str(data.get("mod_id", 0)),
                        "newestVersion": data.get("version", ""),
                        "nexusName": data.get("name", ""),
                        "nexusAuthor": data.get("author", ""),
                        "nexusSummary": data.get("summary", ""),
                        "nexusCategory": str(data.get("category_id", 0)),
                        "gameName": nexus_slug,
                        "repository": "Nexus",
                        "lastNexusQuery": datetime.now(timezone.utc).isoformat(),
                        "nexusURL": f"https://www.nexusmods.com/{nexus_slug}/mods/{data.get('mod_id', 0)}",
                    })
                    self._batch_query_success += 1

                self._batch_query_done += 1
                # Delay next request by 1s to respect rate limits
                from PySide6.QtCore import QTimer
                QTimer.singleShot(1000, self._batch_query_next)
                return

            # ── Single query mode (existing) ──────────────────────
            dl_path = self._pending_dl_query_path
            mod_path = self._pending_query_path

            if dl_path:
                # Downloads-Tab query
                self._pending_dl_query_path = None
                self._update_download_meta(dl_path, data)
                self._game_panel.refresh_downloads()
                # Set tooltip
                name = data.get("name", "")
                mod_id_val = data.get("mod_id", 0)
                version = data.get("version", "")
                summary = data.get("summary", "")
                tooltip = f"{name} (ID: {mod_id_val}) v{version}"
                if summary:
                    tooltip += f"\n{summary}"
                self._game_panel.update_download_tooltip(dl_path, tooltip)
                self.statusBar().showMessage(
                    tr("status.nexus_query_success", name=name), 5000,
                )
            elif mod_path:
                # Mod-Liste query (existing logic)
                self._pending_query_path = None
                if not mod_path.exists():
                    return
                from anvil.core.mod_metadata import write_meta_ini
                nexus_slug = ""
                if self._current_plugin:
                    nexus_slug = (
                        getattr(self._current_plugin, "GameNexusName", "")
                        or getattr(self._current_plugin, "GameShortName", "")
                    )

                from datetime import datetime, timezone
                write_meta_ini(mod_path, {
                    "modid": str(data.get("mod_id", 0)),
                    "newestVersion": data.get("version", ""),
                    "nexusName": data.get("name", ""),
                    "nexusAuthor": data.get("author", ""),
                    "nexusSummary": data.get("summary", ""),
                    "nexusDescription": data.get("description", ""),
                    "nexusCategory": str(data.get("category_id", 0)),
                    "gameName": nexus_slug,
                    "repository": "Nexus",
                    "lastNexusQuery": datetime.now(timezone.utc).isoformat(),
                    "nexusURL": f"https://www.nexusmods.com/{nexus_slug}/mods/{data.get('mod_id', 0)}",
                })
                self._reload_mod_list()
                self.statusBar().showMessage(
                    tr("status.nexus_query_success", name=data.get("name", "")), 5000,
                )

    def _on_nexus_error(self, tag: str, message: str) -> None:
        """Handle Nexus API errors."""
        if tag.startswith("game_categories:"):
            self._log_panel.add_log("error", f"Nexus categories: {message}")
            return
        if tag.startswith("fw_update:"):
            name = tag.split(":", 1)[1]
            txt = tr("status.fw_update_error", name=name, reason=message)
            self._log_panel.add_log("error", txt)
            QMessageBox.warning(self, tr("dialog.fw_update_title"), txt)
            self._fw_update_check_name = ""
            self._fw_update_check_current = ""
            return
        if tag.startswith("update_check:"):
            self._pending_update_check = None
            from PySide6.QtCore import QTimer
            if "429" in message or "Rate Limit" in message:
                QTimer.singleShot(60000, self._update_check_next)
            else:
                QTimer.singleShot(1000, self._update_check_next)
            return
        if tag.startswith("query_mod_info:"):
            # Separate framework query mode
            if self._fw_query_active and self._pending_fw_query_name:
                self._pending_fw_query_name = ""
                self._fw_query_done += 1
                self._fw_query_errors += 1
                if "429" in message or "Rate Limit" in message:
                    from PySide6.QtCore import QTimer
                    self.statusBar().showMessage(tr("fw.query_rate_limit_wait"), 0)
                    QTimer.singleShot(60000, self._fw_query_next)
                else:
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(1000, self._fw_query_next)
                return
            # Batch mode: count error and continue with next
            if getattr(self, "_batch_query_active", False):
                self._pending_batch_query_path = None
                self._batch_query_done += 1
                self._batch_query_errors += 1
                # Rate limit hit → wait 60s before retry
                if "429" in message or "Rate Limit" in message:
                    from PySide6.QtCore import QTimer
                    self.statusBar().showMessage(
                        tr("batch_query.rate_limit_wait"), 0,
                    )
                    QTimer.singleShot(60000, self._batch_query_next)
                else:
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(1000, self._batch_query_next)
                return
            self._pending_dl_query_path = None
            self._pending_query_path = None
        self.statusBar().showMessage(tr("status.nexus_error", message=message), 5000)

    def _update_api_status(self, daily: int, hourly: int) -> None:
        """Update status bar API rate limit display."""
        hidden = self._settings().value("Nexus/hide_api_counter", False, type=bool)
        self._status_bar.set_api_counter_visible(not hidden)
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
        if is_collection_nxm(url):
            QMessageBox.information(
                self, tr("nxm.collection_title"), tr("nxm.collection_message"),
            )
            return
        nxm_link = parse_nxm_url(url)
        if nxm_link:
            self._handle_nxm_link(nxm_link)

    def handle_ipc_message(self, message: str) -> None:
        """Dispatch an IPC message from a second instance.

        ``anvil-launch:<Instanz>`` stammt von einer Spiel-Verknüpfung (#24),
        alles andere wird als nxm:// behandelt.
        """
        prefix = "anvil-launch:"
        if message.startswith(prefix):
            self.launch_instance_shortcut(message[len(prefix):])
        else:
            self.handle_nxm_url(message)

    def launch_instance_shortcut(self, name: str) -> None:
        """Zur Instanz wechseln; Spiel starten, falls der globale Schalter es erlaubt.

        Aufgerufen über eine .desktop-Verknüpfung (#24) — beim eigenen Start
        (``--launch-instance``) oder per IPC von einer zweiten Instanz weitergereicht.
        """
        name = (name or "").strip()
        if not name:
            return
        # list_instances() liefert dicts mit Key "name" — gegen die Namen prüfen
        names = [d.get("name", "") for d in self.instance_manager.list_instances()]
        if name not in names:
            self._log_panel.add_log(
                "error", f"Verknüpfung: Instanz '{name}' nicht gefunden"
            )
            return
        # Fenster nach vorn holen (Doppelklick auf die Verknüpfung)
        self.show()
        self.raise_()
        self.activateWindow()
        if self.instance_manager.current_instance() != name:
            self.switch_instance(name)
        # Globaler Schalter: Spiel starten oder nur Anvil öffnen
        if self._settings().value("Interface/shortcut_launch_game", True, type=bool):
            QTimer.singleShot(0, self._game_panel.start_selected)

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
        menubar_vis = self.menuBar().isVisible()
        toolbar_vis = self._toolbar.isVisible()
        # Safety net: never persist both-hidden state (dead end)
        if not menubar_vis and not toolbar_vis:
            menubar_vis = True
        s.setValue("view/menubar_visible", menubar_vis)
        s.setValue("view/toolbar_visible", toolbar_vis)
        s.setValue("view/statusbar_visible", self._status_bar.isVisible())
        # Log state is persisted by CollapsibleSectionBar (log/collapsed)
        s.setValue("view/filter_panel_open", self._filter_panel.is_open())
        s.setValue("view/filter_splitter_state", self._filter_splitter.saveState())

        # Collapsed separators
        try:
            collapsed_list = sorted(self._mod_list_view._tree._collapsed_separators)
        except AttributeError:
            collapsed_list = []
        if s.value("ModList/collapse_per_profile", False, type=bool) and self._current_profile_path:
            ui_state_file = self._current_profile_path / "ui_state.json"
            ui_state_file.write_text(json.dumps({"collapsed_separators": collapsed_list}))
        else:
            s.setValue("ModList/collapsed_separators", collapsed_list)

        # Filter merken
        if s.value("ModList/remember_filters", False, type=bool):
            prop_ids = [int(x) for x in self._filter_panel.active_property_ids()]
            cat_ids = [int(x) for x in self._filter_panel.active_category_ids()]
            nexus_ids = [int(x) for x in self._filter_panel.active_nexus_category_ids()]
            s.setValue("ModList/saved_filter_props", prop_ids)
            s.setValue("ModList/saved_filter_cats", cat_ids)
            s.setValue("ModList/saved_filter_nexus_cats", nexus_ids)
        else:
            s.remove("ModList/saved_filter_props")
            s.remove("ModList/saved_filter_cats")
            s.remove("ModList/saved_filter_nexus_cats")

        # Icon size → index (0=small, 1=medium, 2=large)
        cur_size = self._toolbar.iconSize()
        size_idx = 1  # default medium
        for i, sz in enumerate(self._ICON_SIZES):
            if cur_size == sz:
                size_idx = i
                break
        s.setValue("view/toolbar_icon_size", size_idx)
        style_key, _ = self._toolbar_style_key_and_default()
        s.setValue(style_key, self._toolbar.toolButtonStyle().value)
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
        # Modern: feste Panelbreiten erzwingen — ein alter Stand darf
        # keine Lücke neben Mod-Liste/Game-Panel hinterlassen
        self._apply_splitter_locks()

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

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._game_running:
            self._center_lock_overlay()

    def closeEvent(self, event) -> None:
        self._redeploy_timer.stop()
        self._purge_on_close()
        self._save_ui_state()
        super().closeEvent(event)

    def _purge_on_close(self) -> None:
        """Clean up on exit — never out from under a running game.

        The next start purges instead.
        """
        if self._game_running or self._game_panel.is_game_running():
            print("[LAUNCH] closing while the game runs — keeping the "
                  "deployment", flush=True)
            return
        if self.keeps_mods_deployed():
            # Closing is the last chance to put the current mod list out —
            # without Anvil running, nothing else will.
            if not self._game_panel.has_deployment():
                print("[PURGE] keep-deployed is on — deploying before exit",
                      flush=True)
                self._game_panel.silent_deploy()
            else:
                print("[PURGE] keep-deployed is on — deployment stays",
                      flush=True)
            return
        self._game_panel.silent_purge()

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
        """Load a BG3 instance using the NORMAL ModListView.

        BG3 mods are converted to ModEntry objects so the standard
        mod list view, context menu, separators, and profile system
        all work automatically.  The BG3 installer handles the
        backend (bg3_modstate.json, modsettings.lsx, auto-deploy).
        """
        # Use normal mod list view — NOT the BG3-specific one
        self._mod_list_stack.setCurrentWidget(self._mod_list_view)
        # BG3 uses .pak files — tell the drop handler to accept them
        self._mod_list_view.set_extra_drop_extensions({".pak"})
        # BG3: Auto-Deploy — kein Deploy-Button noetig
        self._toolbar.deploy_sep.setVisible(False)
        self._toolbar.deploy_action.setVisible(False)
        self._toolbar.proton_action.setVisible(False)
        self._toolbar.merger_sep.setVisible(False)
        self._toolbar.merger_action.setVisible(False)
        # BG3 has no native Creation Engine plugin sorting
        self._toolbar.plugin_sort_sep.setVisible(False)
        self._toolbar.plugin_sort_action.setVisible(False)
        # Enable conflict highlighting on mod click
        s = self._settings()
        self._mod_list_view._tree._conflict_highlight_on_select = s.value(
            "ModList/conflict_highlight_on_select", True, type=bool)

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
                tr("status.bg3_proton_missing"), 8000,
            )

        # ── BG3 Profile laden (eigene, getrennt von anderen Games) ──
        profiles_dir = instance_path / ".profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)

        profile_folders = sorted(
            [d.name for d in profiles_dir.iterdir() if d.is_dir() and not d.is_symlink()],
        ) if profiles_dir.is_dir() else ["Default"]
        if not profile_folders:
            (profiles_dir / "Default").mkdir(exist_ok=True)
            profile_folders = ["Default"]

        order_file = profiles_dir / "profiles_order.json"
        if order_file.is_file():
            try:
                saved_order = json.loads(order_file.read_text())
                ordered = [p for p in saved_order if p in profile_folders]
                ordered += [p for p in profile_folders if p not in saved_order]
                profile_folders = ordered
            except (json.JSONDecodeError, TypeError):
                pass

        profile_name = data.get("selected_profile", "Default")
        if profile_name not in profile_folders:
            profile_name = profile_folders[0]

        self._profile_bar.set_profiles(profile_folders, active=profile_name)
        self._current_profile_path = instance_path / ".profiles" / profile_name

        # Load BG3 mods into the normal mod list view
        self._bg3_reload_mod_list()

        # Initial deploy: modsettings.lsx schreiben (BG3 überschreibt sie bei jedem Spielstart)
        self._bg3_installer.deploy()

        self._game_panel.set_instance_path(instance_path, profile_name=profile_name)

    def _bg3_save_separators(self, model=None) -> None:
        """Save BG3 separator positions to the current profile.

        Stores the UUID of the first mod AFTER the separator as anchor,
        so positions survive mod additions/removals.
        """
        if model is None:
            model = self._mod_list_view.source_model()
        if self._current_profile_path is None:
            return
        seps = []
        rows = model._rows
        for i, row in enumerate(rows):
            if row.is_separator:
                display = row.name  # display name
                raw_name = row.folder_name  # e.g. "My Group_separator"
                # Find the first non-separator mod after this separator
                before_uuid = ""
                for j in range(i + 1, len(rows)):
                    if not rows[j].is_separator:
                        before_uuid = rows[j].folder_name
                        break
                seps.append({
                    "name": raw_name.replace("_separator", "") if raw_name.endswith("_separator") else raw_name,
                    "display_name": display,
                    "color": row.color,
                    "before_uuid": before_uuid,
                    "child_count": row.child_count,
                })
        sep_file = self._current_profile_path / "bg3_separators.json"
        try:
            sep_file.write_text(
                json.dumps(seps, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"bg3: failed to save separators: {exc}", file=sys.stderr)

    def _bg3_mark_dirty(self) -> None:
        """Show and highlight the Deploy button (unsaved changes)."""
        from anvil.styles.dark_theme import theme_color
        self._toolbar.deploy_sep.setVisible(True)
        self._toolbar.deploy_action.setVisible(True)
        self._toolbar.deploy_btn.setStyleSheet(
            "QToolButton { color: %s; font-weight: bold; }"
            % theme_color("accent", "#4DE0D0")
        )

    def _bg3_mark_clean(self) -> None:
        """Remove highlight from Deploy button (no unsaved changes)."""
        self._toolbar.deploy_btn.setStyleSheet("")

    def _bg3_reload_mod_list(self) -> None:
        """Reload BG3 mods into the normal ModListView via ModEntry bridge."""
        print("bg3_sep: _bg3_reload_mod_list() CALLED", file=sys.stderr)
        if self._bg3_installer is None:
            print("bg3_sep: ABORT — no installer", file=sys.stderr)
            return

        # ── Capture live separator state from model before rebuild ──
        model = self._mod_list_view.source_model()
        live_seps = []
        rows = model._rows
        for i, row in enumerate(rows):
            if row.is_separator:
                before_uuid = ""
                for j in range(i + 1, len(rows)):
                    if not rows[j].is_separator:
                        before_uuid = rows[j].folder_name
                        break
                live_seps.append({
                    "name": row.folder_name.replace("_separator", "") if row.folder_name.endswith("_separator") else row.folder_name,
                    "display_name": row.name,
                    "color": getattr(row, "color", ""),
                    "before_uuid": before_uuid,
                    "child_count": row.child_count,
                })

        mod_list = self._bg3_installer.get_mod_list()

        # ── Convert BG3 mods to ModEntry objects ──
        entries: list[ModEntry] = []
        priority = 0
        for mod in mod_list["mods"]:
            entry = ModEntry(
                name=mod.get("uuid", ""),           # folder_name = UUID
                enabled=mod.get("enabled", False),
                priority=priority,
                display_name=mod.get("name", ""),
                version=mod.get("version64", mod.get("version", "")),
                author=mod.get("author", ""),
            )
            entries.append(entry)
            priority += 1

        # ── Add data-override mods BEFORE separator reinsertion ──
        # Data overrides must be in entries before separators are placed,
        # so separator anchors and "end of list" positions account for them.
        for ov in mod_list.get("data_overrides", []):
            ov_name = ov.get("name", "?")
            entry = ModEntry(
                name=ov_name,
                enabled=True,
                priority=priority,
                display_name=ov_name,
                is_direct_install=False,
                is_data_override=True,
            )
            entries.append(entry)
            priority += 1

        # ── Reinsert separators ──
        # Use live model data if available, fall back to file for initial load
        seps_to_use = live_seps
        print(f"bg3_sep: live_seps={len(live_seps)}, profile_path={self._current_profile_path}", file=sys.stderr)
        if not seps_to_use:
            sep_file = (self._current_profile_path / "bg3_separators.json") if self._current_profile_path else None
            if sep_file is not None and sep_file.is_file():
                try:
                    seps_to_use = json.loads(sep_file.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    seps_to_use = []

        if seps_to_use:
            uuid_to_idx = {e.name: i for i, e in enumerate(entries)}
            print(f"bg3_sep: {len(seps_to_use)} seps, {len(entries)} mods, source={'live' if live_seps else 'file'}", file=sys.stderr)
            offset = 0
            for sep in seps_to_use:
                sep_entry = ModEntry(
                    name=sep.get("name", "separator") + "_separator",
                    enabled=True,
                    priority=0,
                    is_separator=True,
                    display_name=sep.get("display_name", ""),
                    color=sep.get("color", ""),
                )
                anchor = sep.get("before_uuid", "")
                print(f"bg3_sep: '{sep.get('display_name')}' anchor='{anchor[:20]}' found={anchor in uuid_to_idx if anchor else 'no-anchor'}", file=sys.stderr)
                if anchor and anchor in uuid_to_idx:
                    pos = uuid_to_idx[anchor] + offset
                elif "position" in sep:
                    # Fallback for old format (absolute position)
                    pos = min(sep["position"], len(entries) + offset)
                else:
                    pos = len(entries) + offset
                entries.insert(pos, sep_entry)
                offset += 1
            for i, e in enumerate(entries):
                e.priority = i

        self._current_mod_entries = entries

        # ── Feed into normal model ──
        conflict_data = self._compute_conflict_data()
        mod_rows = [mod_entry_to_row(e, conflict_data) for e in entries]
        source_model = self._mod_list_view.source_model()
        source_model.set_mods(mod_rows)

        # ── Restore saved child_counts ──
        # set_mods() recalculates child_counts blindly (counts ALL mods
        # between separators).  Restore the user's intended grouping.
        if seps_to_use:
            sep_child_counts = {}
            for sep in seps_to_use:
                sep_name = sep.get("name", "separator") + "_separator"
                if "child_count" in sep:
                    sep_child_counts[sep_name] = sep["child_count"]
                elif not sep.get("before_uuid"):
                    # No anchor + no saved child_count = separator at end
                    # with no intended children (e.g. before data overrides)
                    sep_child_counts[sep_name] = 0
            if sep_child_counts:
                for row in source_model._rows:
                    if row.is_separator and row.folder_name in sep_child_counts:
                        row.child_count = sep_child_counts[row.folder_name]

        self._mod_list_view._proxy_model.set_mod_entries(entries)
        self._mod_list_view._tree._apply_separator_filter()
        self._update_active_count()

        # ── Update frameworks in the framework panel ──
        fw_list = mod_list.get("frameworks", [])
        # Data overrides that install into game dir (e.g. bin/NativeMods/)
        fw_items = list(fw_list)
        for ov in mod_list.get("data_override_frameworks", []):
            fw_items.append({
                "name": ov.get("name", "?"),
                "description": f"Data Override — {len(ov.get('files', []))} Dateien",
                "installed": True,
                **ov,
            })
        # Enrich with per-instance state (lock/active/version)
        if self._current_instance_path:
            for fw in fw_items:
                st = framework_state.get(
                    self._current_instance_path, fw.get("name", ""),
                )
                fw.setdefault("locked", st.get("locked", False))
                fw.setdefault("active", st.get("active", True))
                fw.setdefault("version", st.get("version", ""))
        self._mod_list_view.load_frameworks(fw_items)

    def _on_bg3_mod_activated(self, uuid: str) -> None:
        """Activate a BG3 mod (add to ModOrder + auto-deploy)."""
        if self._bg3_installer is None:
            return
        ok = self._bg3_installer.activate_mod(uuid)
        if ok:
            self._bg3_reload_mod_list()
            self.statusBar().showMessage(tr("status.mod_activated"), 3000)
        else:
            self.statusBar().showMessage(tr("status.mod_activation_failed"), 5000)

    def _on_bg3_mod_deactivated(self, uuid: str) -> None:
        """Deactivate a BG3 mod (remove from ModOrder + auto-deploy)."""
        if self._bg3_installer is None:
            return
        ok = self._bg3_installer.deactivate_mod(uuid)
        if ok:
            self._bg3_reload_mod_list()
            self.statusBar().showMessage(tr("status.mod_deactivated"), 3000)
        else:
            self.statusBar().showMessage(tr("status.mod_deactivation_failed"), 5000)

    def _on_bg3_mods_reordered(self, uuid_order: list[str]) -> None:
        """Reorder BG3 active mods (auto-deploy)."""
        if self._bg3_installer is None:
            return
        ok = self._bg3_installer.reorder_mods(uuid_order)
        if ok:
            self.statusBar().showMessage(tr("status.load_order_updated"), 3000)
        else:
            self.statusBar().showMessage(tr("status.load_order_failed"), 5000)
            self._bg3_reload_mod_list()

    def _on_bg3_archives_dropped(self, paths: list, insert_at: int | None = None) -> None:
        """Install BG3 mods from dropped archives/paks."""
        if self._bg3_installer is None:
            return

        # Capture reference entry for positioning before state changes
        ref_uuid = None
        ref_active = True
        if insert_at is not None and self._current_mod_entries:
            entries = self._current_mod_entries
            idx = insert_at
            while idx < len(entries) and getattr(entries[idx], "is_separator", False):
                idx += 1
            if idx < len(entries):
                ref_uuid = entries[idx].name  # UUID for BG3 entries
                ref_active = entries[idx].enabled

        installed = []
        for path_str in paths:
            archive_path = Path(path_str)

            # Check for duplicate (same UUID already installed)
            existing = self._bg3_installer.check_pak_duplicate(archive_path)
            if existing:
                reply = QMessageBox.question(
                    self,
                    tr("dialog.mod_exists"),
                    tr("bg3.mod_already_installed", name=existing["name"]),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    continue
                # Remove old version before reinstalling
                self._bg3_installer.uninstall_mod(
                    existing["uuid"], existing.get("pak_file", ""),
                )

            result = self._bg3_installer.install_mod(archive_path)
            if result:
                mod_type = result.get("type", "pak")
                name = result.get("name", archive_path.name)
                uuid = result.get("uuid", "")
                installed.append((name, mod_type, uuid))
                # Mark download as installed in .meta file
                try:
                    meta_path = Path(str(path_str) + ".meta")
                    cp = configparser.ConfigParser()
                    cp.optionxform = str
                    if meta_path.is_file():
                        cp.read(str(meta_path), encoding="utf-8")
                    if not cp.has_section("General"):
                        cp.add_section("General")
                    cp.set("General", "installed", "true")
                    with open(meta_path, "w", encoding="utf-8") as f:
                        cp.write(f)
                except Exception as exc:
                    print(f"[BG3-META] Failed to write .meta: {exc}", flush=True)
            else:
                self.statusBar().showMessage(
                    tr("status.install_failed", name=archive_path.name), 5000,
                )

        # Position newly installed mods at drop target (always inactive)
        if ref_uuid and installed:
            for _name, mod_type, uuid in installed:
                if uuid and mod_type == "pak":
                    self._bg3_installer.insert_mod_at(uuid, ref_uuid, activate=False)

        if installed:
            self._bg3_reload_mod_list()
            names = ", ".join(n for n, _, _ in installed)
            types = set(t for _, t, _ in installed)
            if types == {"pak"}:
                self.statusBar().showMessage(tr("status.installed_inactive", names=names), 5000)
            else:
                self.statusBar().showMessage(tr("status.installed", names=names), 5000)

    def _on_bg3_deploy(self) -> None:
        """Deploy: validate and backup modsettings.lsx."""
        if self._bg3_installer is None:
            self.statusBar().showMessage(tr("status.no_bg3_installer"), 5000)
            return
        ok = self._bg3_installer.deploy()
        if ok:
            self._bg3_mark_clean()
            self.statusBar().showMessage(tr("status.modlist_exported_check"), 5000)
        else:
            self.statusBar().showMessage(tr("status.deploy_failed"), 5000)

    # ── Script Merger (Witcher 3) ────────────────────────────────

    def _on_script_merger_clicked(self) -> None:
        """Oeffnet den Script Merger Dialog fuer Witcher 3."""
        plugin = self._current_plugin
        if plugin is None or getattr(plugin, "GameShortName", "") != "witcher3":
            return

        vanilla_dir = plugin.vanilla_scripts_dir()
        if vanilla_dir is None:
            QMessageBox.warning(
                self,
                tr("script_merger.title"),
                tr("script_merger.no_vanilla_dir"),
            )
            return

        instance_path = self._current_instance_path
        mods_dir = instance_path / ".mods"
        profiles_dir = instance_path / ".profiles"

        # Aktive Mods aus aktuellem Profil lesen
        active = read_active_mods(
            profiles_dir / self._profile_bar.current_profile()
        )
        active_names = [
            n for n in read_global_modlist(profiles_dir)
            if n in active and n != "_merged_"
        ]

        from anvil.widgets.script_merger_dialog import ScriptMergerDialog
        dlg = ScriptMergerDialog(
            parent=self,
            vanilla_scripts_dir=vanilla_dir,
            mods_dir=mods_dir,
            active_mod_names=active_names,
            profiles_dir=profiles_dir,
            instance_path=instance_path,
        )
        dlg.exec()

        if dlg.has_changes:
            self._reload_mod_list()

    # ── Native plugin sorting (Bethesda) ─────────────────────────

    def _on_plugin_sort_clicked(self) -> None:
        """Run Anvil's native dependency sorter for the current profile."""
        plugin = self._current_plugin
        if (
            plugin is None
            or not plugin.has_plugins_txt()
            or not getattr(plugin, "SupportsNativePluginSorting", False)
        ):
            self.statusBar().showMessage(tr("load_order.not_bethesda"), 5000)
            return

        result = self._game_panel.sort_plugins_native()
        if result is None:
            self.statusBar().showMessage(tr("load_order.sorting_failed"), 5000)
            return

        problems: list[str] = []
        if result.missing_masters:
            lines = [
                f"{name}: {', '.join(masters)}"
                for name, masters in result.missing_masters.items()
            ]
            problems.append(
                tr("load_order.missing_masters_title") + ":\n" + "\n".join(lines)
            )
        if result.cycles:
            problems.append(
                tr("load_order.cycles_title") + ":\n"
                + "\n".join(" → ".join(cycle) for cycle in result.cycles)
            )
        if result.parse_errors:
            lines = [
                f"{name}: {error}"
                for name, error in result.parse_errors.items()
            ]
            problems.append(
                tr("load_order.parse_errors_title") + ":\n" + "\n".join(lines)
            )

        if result.write_error:
            from anvil.widgets.game_panel import localized_write_error
            problems.append(
                tr("load_order.write_error_title") + ":\n" + localized_write_error(
                    result.write_error, getattr(result, "write_error_key", "")
                )
            )

        if problems:
            QMessageBox.warning(
                self,
                tr("load_order.sorting_failed"),
                "\n\n".join(problems),
            )
            return

        self.statusBar().showMessage(tr("load_order.sorting_complete"), 5000)
        QMessageBox.information(
            self,
            tr("toolbar.plugin_sort"),
            tr("load_order.sorting_complete"),
        )

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

        act_activate = None
        act_deactivate = None
        if has_mod:
            # Unified list: show activate/deactivate based on mod's enabled state
            is_enabled = mod_data.get("enabled", False)
            if is_enabled:
                act_deactivate = menu.addAction(tr("context.deactivate"))
            else:
                act_activate = menu.addAction(tr("context.activate"))

            menu.addSeparator()
            act_uninstall = menu.addAction(tr("context.uninstall"))
        else:
            act_uninstall = None

        menu.addSeparator()
        act_explorer = menu.addAction(tr("context.open_file_manager"))
        act_explorer.setEnabled(has_mod)
        menu.addSeparator()
        act_reload = menu.addAction(tr("context.reload"))

        chosen = menu.exec(global_pos)
        if not chosen:
            return

        uuid = mod_data.get("uuid", "")
        filename = mod_data.get("filename", "")

        if chosen == act_reload:
            self._bg3_reload_mod_list()
            self.statusBar().showMessage(tr("status.mod_list_reloaded"), 3000)
        elif act_activate is not None and chosen == act_activate:
            self._on_bg3_mod_activated(uuid)
        elif act_deactivate is not None and chosen == act_deactivate:
            self._on_bg3_mod_deactivated(uuid)
        elif chosen == act_uninstall and uuid:
            name = mod_data.get("name", uuid)
            reply = QMessageBox.question(
                self, tr("dialog.uninstall_mod_title"),
                tr("dialog.uninstall_mod_message", name=name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                ok = self._bg3_installer.uninstall_mod(uuid, filename)
                if ok:
                    self._bg3_reload_mod_list()
                    self.statusBar().showMessage(tr("status.uninstalled", name=name), 5000)
                else:
                    self.statusBar().showMessage(tr("status.uninstall_failed"), 5000)
        elif chosen == act_explorer:
            mods_path = self._bg3_installer._mods_path
            if mods_path and mods_path.is_dir():
                host_open_path(str(mods_path))

    # ── Framework context menu + handlers ──────────────────────────

    def _build_fw_dict(self, fw, installed: bool) -> dict:
        """Build a framework UI-dict enriched with per-instance state."""
        raw = framework_state.load(self._current_instance_path) \
            if self._current_instance_path else {}
        entry = raw.get(fw.name)
        if entry is None:
            locked = True
            active = True
            version = ""
        else:
            locked = bool(entry.get("locked", False))
            active = bool(entry.get("active", True))
            version = str(entry.get("version", ""))
        critical = bool(getattr(fw, "essential", False))
        return {
            "name": fw.name,
            "description": fw.description,
            "installed": installed,
            "locked": locked,
            "active": active,
            "version": version,
            "is_critical": critical,
            "nexus_id": int(getattr(fw, "nexus_id", 0) or 0),
        }

    def _on_fw_context_menu(self, global_pos, fw_data: dict) -> None:
        """Context menu for framework mods."""
        menu = QMenu(self)
        name = fw_data.get("name", "")
        installed = fw_data.get("installed", False)
        critical = bool(fw_data.get("is_critical", False))
        nexus_id = int(fw_data.get("nexus_id", 0) or 0)

        locked = bool(fw_data.get("locked", False))
        act_toggle_lock = menu.addAction(
            tr("context.fw_unlock" if locked else "context.fw_lock"),
        )
        act_toggle_lock.setEnabled(installed)

        menu.addSeparator()

        act_reinstall = menu.addAction(tr("context.reinstall_framework"))
        act_uninstall = menu.addAction(tr("context.uninstall_framework"))
        act_uninstall.setEnabled(installed and not locked)

        menu.addSeparator()

        act_nexus_query_fw = menu.addAction(tr("context.nexus_query_frameworks"))
        _has_fw = bool(self._current_plugin and any(
            fw.nexus_id > 0 and inst for fw, inst in self._current_plugin.get_installed_frameworks()
        ))
        act_nexus_query_fw.setEnabled(self._nexus_api.has_api_key() and _has_fw)

        act_check_update = menu.addAction(tr("context.fw_check_update"))
        act_check_update.setEnabled(
            installed and nexus_id > 0 and self._nexus_api.has_api_key(),
        )

        menu.addSeparator()
        act_explorer = menu.addAction(tr("context.open_file_manager"))
        menu.addSeparator()
        act_info = menu.addAction(tr("context.fw_info"))
        act_info.setEnabled(installed)

        chosen = menu.exec(global_pos)
        if not chosen:
            return

        if chosen == act_info:
            self._fw_show_info(fw_data)
        elif chosen == act_toggle_lock:
            self._fw_toggle_lock(name)
        elif chosen == act_nexus_query_fw:
            self._query_framework_nexus()
        elif chosen == act_check_update:
            self._fw_check_update(fw_data)
        elif chosen == act_reinstall:
            self._fw_reinstall(name)
        elif chosen == act_uninstall:
            self._fw_uninstall(name)
        elif chosen == act_explorer:
            if self._current_game_path and self._current_game_path.is_dir():
                # Open the directory where the framework is actually installed
                target_dir = self._current_game_path
                if self._current_plugin:
                    for fw in self._current_plugin.all_framework_mods():
                        if fw.name == name:
                            # Use last existing detect_installed path (most specific)
                            for det in fw.detect_installed:
                                candidate = (self._current_game_path / det).parent
                                if candidate.is_dir():
                                    target_dir = candidate
                            break
                host_open_path(str(target_dir))

    def _fw_reinstall(self, fw_name: str) -> None:
        """Reinstall a framework from its archive in the downloads directory."""
        if not self._current_instance_path or not self._current_plugin:
            return
        downloads_path = self._current_downloads_path
        if not downloads_path or not downloads_path.is_dir():
            QMessageBox.warning(
                self, tr("dialog.reinstall_title"),
                tr("status.no_downloads_folder"),
            )
            return

        fw_obj = None
        for fw in self._current_plugin.all_framework_mods():
            if fw.name == fw_name:
                fw_obj = fw
                break

        archive = self._find_framework_archive(downloads_path, fw_obj, fw_name)
        if not archive:
            QMessageBox.information(
                self, tr("dialog.reinstall_title"),
                tr("dialog.no_matching_archive", name=fw_name),
            )
            return
        self._install_archives([archive])
        self._game_panel.refresh_downloads()

    def _find_framework_archive(
        self,
        downloads_path: Path,
        fw_obj,
        fw_name: str,
    ) -> Path | None:
        """Find the archive for a framework in the downloads directory.

        Match strategies (first winner wins, newest mtime per strategy):
          1. Nexus .meta file with matching modID (language-independent)
          2. Nexus mod-ID pattern in filename (``-{id}-`` / ``-{id}.``)
          3. Content match: extract and run ``is_framework_mod``
          4. Legacy substring match on the display name
        """
        candidates = [
            f for f in downloads_path.rglob("*")
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        if not candidates:
            return None

        nexus_id = getattr(fw_obj, "nexus_id", 0) if fw_obj else 0

        def newest(files: list[Path]) -> Path | None:
            if not files:
                return None
            return max(files, key=lambda p: p.stat().st_mtime)

        # 1. Nexus .meta file with matching modID
        if nexus_id > 0:
            meta_hits: list[Path] = []
            for f in candidates:
                meta = f.with_suffix(f.suffix + ".meta")
                if not meta.is_file():
                    continue
                try:
                    cp = configparser.ConfigParser(interpolation=None, strict=False)
                    cp.read(meta, encoding="utf-8")
                    if cp.has_option("General", "modID"):
                        try:
                            if int(cp.get("General", "modID")) == nexus_id:
                                meta_hits.append(f)
                        except ValueError:
                            pass
                except (OSError, configparser.Error):
                    continue
            hit = newest(meta_hits)
            if hit:
                return hit

        # 2. Nexus ID pattern in filename
        if nexus_id > 0:
            id_str = str(nexus_id)
            id_hits = [
                f for f in candidates
                if f"-{id_str}-" in f.stem or f.stem.endswith(f"-{id_str}")
            ]
            hit = newest(id_hits)
            if hit:
                return hit

        # 3. Content match via extraction
        if fw_obj is not None:
            flatten = getattr(self._current_plugin, "GameFlattenArchive", True)
            se_dir = getattr(self._current_plugin, "ScriptExtenderDir", "")
            installer = ModInstaller(
                self._current_instance_path, flatten=flatten,
                script_extender_dir=se_dir,
                mods_path=_active_instance_paths(self).mods,
            )
            content_hits: list[Path] = []
            for f in candidates:
                temp_dir = installer.extract_to_temp(f)
                if temp_dir is None:
                    continue
                try:
                    file_list = [
                        str(p.relative_to(temp_dir))
                        for p in temp_dir.rglob("*") if p.is_file()
                    ]
                    detected = self._current_plugin.is_framework_mod(file_list)
                    if detected is not None and detected.name == fw_obj.name:
                        content_hits.append(f)
                finally:
                    shutil.rmtree(temp_dir, ignore_errors=True)
            hit = newest(content_hits)
            if hit:
                return hit

        # 4. Legacy substring fallback
        fw_lower = fw_name.lower()
        substr_hits = [f for f in candidates if fw_lower in f.stem.lower()]
        return newest(substr_hits)

    def _fw_uninstall(self, fw_name: str) -> None:
        """Uninstall a framework by removing its detect_installed files from game dir."""
        if not self._current_plugin or not self._current_game_path:
            return
        if self._refuse_while_game_runs(tr("dialog.uninstall_framework_title")):
            return
        # Lock-Guard
        if self._current_instance_path:
            st = framework_state.get(self._current_instance_path, fw_name)
            if st.get("locked"):
                QMessageBox.information(
                    self, tr("dialog.uninstall_framework_title"),
                    tr("status.fw_locked_cant_uninstall", name=fw_name),
                )
                return
        fw_obj = None
        for fw in self._current_plugin.all_framework_mods():
            if fw.name == fw_name:
                fw_obj = fw
                break
        if not fw_obj:
            return
        reply = QMessageBox.warning(
            self, tr("dialog.uninstall_framework_title"),
            tr("dialog.uninstall_framework_warning", name=fw_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        game_path = self._current_game_path
        removed = 0

        # Managed framework: drop its mod folder from .mods/
        get_managed = getattr(self._current_plugin, "managed_framework_mods", None)
        if callable(get_managed) and self._current_instance_path:
            mods_dir = _active_instance_paths(self).mods
            for folder in get_managed().get(fw_name.lower(), []):
                mod_dir = mods_dir / folder
                if mod_dir.is_dir():
                    shutil.rmtree(mod_dir, ignore_errors=True)
                    removed += 1
                    if self._mod_index is not None:
                        self._mod_index.invalidate(folder)

        # Hand-installed copy in the game directory
        for det_path in fw_obj.detect_installed:
            full = game_path / det_path
            disabled = full.with_name(full.name + framework_state.DISABLED_SUFFIX)
            for target in (full, disabled):
                if target.is_file():
                    target.unlink()
                    removed += 1
                elif target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                    removed += 1
        if removed:
            if self._current_instance_path:
                framework_state.remove(self._current_instance_path, fw_name)
            self.statusBar().showMessage(tr("status.framework_uninstalled", name=fw_name), 5000)
        else:
            self.statusBar().showMessage(tr("status.uninstall_failed"), 5000)
        self._reload_mod_list()

    def _fw_show_info(self, fw_data: dict) -> None:
        """Show info dialog for a single framework."""
        name = fw_data.get("name", "?")
        lines = [
            f"Name: {name}",
            f"{tr('label.header_description')}: {fw_data.get('description', '') or '—'}",
            f"{tr('game_panel.header_status')}: "
            f"{tr('game_panel.installed') if fw_data.get('installed') else tr('game_panel.not_installed')}",
            f"{tr('label.header_version')}: {fw_data.get('version') or '—'}",
            f"{tr('context.fw_lock')}: "
            f"{tr('common.yes') if fw_data.get('locked') else tr('common.no')}",
            f"{tr('context.fw_activate')}: "
            f"{tr('common.yes') if fw_data.get('active', True) else tr('common.no')}",
            f"Nexus-ID: {fw_data.get('nexus_id') or '—'}",
        ]
        # Collect detect-paths from plugin
        if self._current_plugin and self._current_game_path:
            for fw in self._current_plugin.all_framework_mods():
                if fw.name == name:
                    paths = []
                    get_managed = getattr(
                        self._current_plugin, "managed_framework_mods", None,
                    )
                    if callable(get_managed) and self._current_instance_path:
                        mods_dir = _active_instance_paths(self).mods
                        paths.extend(
                            str(mods_dir / folder)
                            for folder in get_managed().get(name.lower(), [])
                        )
                    for det in fw.detect_installed:
                        p = self._current_game_path / det
                        disabled = p.with_name(p.name + framework_state.DISABLED_SUFFIX)
                        if p.exists():
                            paths.append(str(p))
                        elif disabled.exists():
                            paths.append(str(disabled))
                    if paths:
                        lines.append("")
                        lines.append("Dateien:")
                        lines.extend(f"  {p}" for p in paths)
                    break

        dlg = QDialog(self)
        dlg.setObjectName("InfoDialog")
        dlg.setWindowTitle(tr("dialog.info_title", name=name))
        layout = QVBoxLayout(dlg)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText("\n".join(lines))
        layout.addWidget(text_edit)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)
        dlg.setMinimumSize(600, 400)
        dlg.resize(600, 400)
        _center_on_parent(dlg)
        dlg.exec()

    def _fw_toggle_lock(self, fw_name: str) -> None:
        """Toggle lock state of a framework."""
        if not self._current_instance_path:
            return
        st = framework_state.get(self._current_instance_path, fw_name)
        new_locked = not bool(st.get("locked", False))
        framework_state.set_entry(
            self._current_instance_path, fw_name, locked=new_locked,
        )
        # Shared unlock-box: every unlock resets the 5-min timer;
        # when nothing is unlocked anymore, drop the box.
        if not new_locked:
            from datetime import datetime, timedelta, timezone
            framework_state.set_box_expiry(
                self._current_instance_path,
                datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        elif not framework_state.has_unlocked(self._current_instance_path):
            framework_state.clear_box(self._current_instance_path)
        self.statusBar().showMessage(
            tr("status.fw_locked" if new_locked else "status.fw_unlocked", name=fw_name),
            3000,
        )
        QTimer.singleShot(0, self._reload_mod_list)

    # ── Framework Auto-Re-Lock ────────────────────────────────────────

    def _auto_relock_instance(self, instance_path: Path, reason: str) -> list[str]:
        """Lock all frameworks in ``instance_path`` and show a status
        message. Refreshes the framework panel when the current instance
        is affected. Returns the list of framework names that changed."""
        if not instance_path or not instance_path.is_dir():
            return []
        changed = framework_state.lock_all(instance_path)
        if not changed:
            return []
        if self._current_instance_path == instance_path:
            self.statusBar().showMessage(
                tr("status.fw_auto_relocked", count=len(changed), reason=tr(f"status.fw_auto_reason_{reason}")),
                5000,
            )
            QTimer.singleShot(0, self._reload_mod_list)
        return changed

    def _fw_relock_tick(self) -> None:
        """Periodic check: if the shared unlock-box of the current
        instance has expired, lock everything."""
        inst = self._current_instance_path
        if not inst:
            return
        expires = framework_state.get_box_expiry(inst)
        if expires is None:
            return
        from datetime import datetime, timezone
        if datetime.now(timezone.utc) >= expires:
            self._auto_relock_instance(inst, "timeout")

    def _fw_relock_startup_scan(self) -> None:
        """On Anvil start, lock all frameworks in all instances across
        all games that still have unlocked entries."""
        try:
            inst_root = self.instance_manager.instances_path()
        except Exception:
            return
        if not inst_root or not inst_root.is_dir():
            return
        for inst in inst_root.iterdir():
            if inst.is_dir() and framework_state.has_unlocked(inst):
                framework_state.lock_all(inst)

    def _fw_toggle_active(self, fw_name: str) -> None:
        """Activate/deactivate a framework.

        Only flips the ``active`` flag in framework_state.json — the
        deployer skips inactive frameworks on the next game start.
        Frameworks the user installed into the game directory by hand
        are not touched.
        """
        if not self._current_plugin or not self._current_instance_path:
            return
        if not any(fw.name == fw_name for fw in self._current_plugin.all_framework_mods()):
            return

        entry = framework_state.get(self._current_instance_path, fw_name)
        new_active = not entry.get("active", True)
        framework_state.set_entry(
            self._current_instance_path, fw_name, active=new_active,
        )
        self.statusBar().showMessage(
            tr("status.fw_activated" if new_active else "status.fw_deactivated", name=fw_name),
            3000,
        )
        QTimer.singleShot(0, self._reload_mod_list)

    def _on_fw_active_toggle(self, fw_data: dict) -> None:
        """Click on the status column toggles active/inactive."""
        name = fw_data.get("name", "")
        if not name or not fw_data.get("installed"):
            return
        if fw_data.get("locked"):
            return
        self._fw_toggle_active(name)

    def _fw_check_update(self, fw_data: dict) -> None:
        """Check Nexus for a newer version of this framework."""
        name = fw_data.get("name", "")
        nexus_id = int(fw_data.get("nexus_id", 0) or 0)
        if nexus_id <= 0 or not self._current_plugin:
            QMessageBox.information(
                self, tr("dialog.fw_update_title"),
                tr("status.fw_no_nexus_id", name=name),
            )
            return
        slug = getattr(self._current_plugin, "NexusSlug", "")
        if not slug:
            return
        if not self._nexus_api.has_api_key():
            QMessageBox.warning(
                self, tr("dialog.fw_update_title"),
                tr("status.nexus_api_key_missing"),
            )
            return
        self._fw_update_check_name = name
        self._fw_update_check_current = str(fw_data.get("version", ""))
        msg = tr("status.fw_checking", name=name)
        self._log_panel.add_log("info", msg)
        self.statusBar().showMessage(msg, 3000)
        self._nexus_api.update_check_framework(slug, nexus_id, name)

    def _on_fw_archives_dropped(self, paths: list) -> None:
        """Handle archives dropped onto the framework tree."""
        if not self._current_instance_path or not self._current_plugin:
            return

        # Filter: only install archives that are actually framework mods
        flatten = getattr(self._current_plugin, "GameFlattenArchive", True)
        se_dir = getattr(self._current_plugin, "ScriptExtenderDir", "")
        installer = ModInstaller(
            self._current_instance_path,
            flatten=flatten,
            script_extender_dir=se_dir,
            mods_path=_active_instance_paths(self).mods,
        )
        fw_archives: list[Path] = []
        rejected: list[str] = []

        for p in paths:
            archive = Path(p)
            temp_dir = installer.extract_to_temp(archive)
            if temp_dir is None:
                continue
            file_list = [
                str(f.relative_to(temp_dir))
                for f in temp_dir.rglob("*") if f.is_file()
            ]
            fw = self._current_plugin.is_framework_mod(file_list)
            shutil.rmtree(temp_dir, ignore_errors=True)
            if fw is not None:
                fw_archives.append(archive)
            else:
                rejected.append(archive.name)

        if rejected:
            QMessageBox.warning(
                self,
                tr("dialog.not_a_framework_title"),
                tr("dialog.not_a_framework_message",
                   names="\n".join(rejected)),
            )

        if fw_archives:
            self._install_archives(fw_archives)
        self._game_panel.refresh_downloads()

    def _on_bg3_extras_context_menu(self, global_pos, mod_data: dict) -> None:
        """Context menu for data-overrides and frameworks."""
        menu = QMenu(self)
        mod_type = mod_data.get("type", "")
        name = mod_data.get("name", "")

        act_uninstall = None
        if mod_type == "data_override" and name:
            act_uninstall = menu.addAction(tr("context.uninstall"))

        menu.addSeparator()
        act_reload = menu.addAction(tr("context.reload"))

        chosen = menu.exec(global_pos)
        if not chosen:
            return

        if chosen == act_reload:
            self._bg3_reload_mod_list()
            self.statusBar().showMessage(tr("status.mod_list_reloaded"), 3000)
        elif chosen == act_uninstall and name:
            reply = QMessageBox.question(
                self, tr("dialog.uninstall_data_override_title"),
                tr("dialog.uninstall_data_override_message", name=name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                ok = self._bg3_installer.uninstall_data_override(name)
                if ok:
                    self._bg3_reload_mod_list()
                    self.statusBar().showMessage(tr("status.data_override_uninstalled", name=name), 5000)
                else:
                    self.statusBar().showMessage(tr("status.uninstall_failed"), 5000)

    # ── Other slots ───────────────────────────────────────────────────

    def _on_about(self):
        QMessageBox.about(self, tr("menu.about_anvil"), tr("dialog.about_text", version=APP_VERSION))

    def _on_about_qt(self):
        """Hilfe → Über Qt (vollständig übersetzt)."""
        from PySide6.QtCore import qVersion
        text = tr("dialog.about_qt_text", version=qVersion())
        QMessageBox.about(self, tr("menu.about_qt"), text)

    # ── Self-Update (Git-basiert) ──────────────────────────────────

    # ── Benachrichtigungen (Glocken-Button) ──────────────────────────
    def _on_notifications_changed(self) -> None:
        """Aktualisiert den Zähler-Badge am Glocken-Button."""
        count = self._notification_center.unread_count()
        btn = getattr(self._toolbar, "notifications_btn", None)
        if btn is not None:
            btn.set_count(count)
        if hasattr(self, "_title_notif_btn"):
            self._title_notif_btn.set_count(count)

    def _on_title_notifications_clicked(self, checked: bool = False) -> None:
        """Benachrichtigungen-Button in der Titelzeile (modernes Design)."""
        panel = NotificationPanel(self._notification_center, self)
        panel.show_under(self._title_notif_btn)

    # ── Hell/Dunkel-Umschalter (Titelzeile) ──────────────────────────
    def _update_title_theme_btn(self) -> None:
        """Button zeigt das ZIEL-Design: dunkel aktiv → „Hell" und umgekehrt."""
        if not hasattr(self, "_title_theme_btn"):
            return
        from anvil.styles.dark_theme import MODERN_THEME_DARK, is_modern_theme
        cur = self._settings().value("style/theme", default_theme())
        self._title_theme_btn.setVisible(is_modern_theme(cur))
        if cur == MODERN_THEME_DARK:
            self._title_theme_btn.setText(tr("settings.design_light"))
        else:
            self._title_theme_btn.setText(tr("settings.design_dark"))

    def _on_title_theme_toggle(self, checked: bool = False) -> None:
        """Wechselt zwischen Anvil Dunkel und Anvil Hell (wie Settings-Accept)."""
        from anvil.styles.dark_theme import (
            MODERN_THEME_DARK, MODERN_THEME_LIGHT, is_modern_theme)
        s = self._settings()
        cur = s.value("style/theme", default_theme())
        if not is_modern_theme(cur):
            return
        new = (MODERN_THEME_LIGHT if cur == MODERN_THEME_DARK
               else MODERN_THEME_DARK)
        s.setValue("style/theme", new)
        s.sync()
        accent, density = style_prefs(s)
        apply_theme(QApplication.instance(), new,
                    load_overrides(s, new), accent=accent, density=density)
        self.setStyleSheet("")
        self._restore_view_settings()
        from PySide6.QtWidgets import QTreeView
        app = QApplication.instance()
        for w in app.allWidgets():
            if hasattr(w, "apply_theme_metrics"):
                w.apply_theme_metrics()
            if isinstance(w, QTreeView):
                w.doItemsLayout()
        if self.instance_manager.current_instance():
            self.switch_instance(self.instance_manager.current_instance())
        self._update_title_theme_btn()

    def _on_notify_download_finished(self, download_id: int, save_path: str) -> None:
        name = Path(save_path).name if save_path else ""
        self._notification_center.add(
            "info", tr("notifications.download_done"), name)

    def _on_notify_download_error(self, download_id: int, message: str) -> None:
        self._notification_center.add(
            "error", tr("notifications.download_error"), str(message))

    def _on_update_available(self, count: int, changelog: str):
        """Show clickable toast when new commits are available."""
        self._pending_count = count
        self._pending_changelog = changelog
        self._notification_center.add(
            "info", tr("notifications.update_available"),
            tr("update.commits_available", count=count))
        toast = Toast(
            self,
            tr("update.commits_available", count=count),
            duration=8000,
            clickable=True,
        )
        toast.clicked.connect(
            lambda checked=False: self._show_update_dialog(count, changelog)
        )

    def _show_update_dialog(self, count: int, changelog: str):
        """Show QMessageBox with changelog, buttons Aktualisieren / Spaeter."""
        msg = QMessageBox(self)
        msg.setWindowTitle(tr("update.changelog_title"))
        msg.setText(
            tr("update.changelog_message", count=count, changelog=changelog)
        )
        msg.setIcon(QMessageBox.Icon.Information)

        btn_update = msg.addButton(
            tr("update.button_update"), QMessageBox.ButtonRole.AcceptRole
        )
        msg.addButton(
            tr("update.button_later"), QMessageBox.ButtonRole.RejectRole
        )

        msg.exec()

        if msg.clickedButton() == btn_update:
            self._on_perform_update()

    def _on_perform_update(self):
        """Trigger the git-based update via update_checker.apply_update()."""
        self.statusBar().showMessage(tr("update.updating"), 0)
        self._update_checker.apply_update()

    def _on_update_progress(self, message: str):
        """Show update progress in status bar; handle dirty-tree warning."""
        if message == "dirty_tree":
            self.statusBar().clearMessage()
            Toast(self, tr("update.dirty_tree"), duration=8000)
            return
        self.statusBar().showMessage(message, 0)

    def _on_update_applied(self, success: bool, pip_ran: bool):
        """Handle update result -- restart on success, toast on failure."""
        if success:
            if pip_ran:
                Toast(self, tr("update.pip_updated"), duration=3000)
            Toast(self, tr("update.restart_required"), duration=3000)
            QTimer.singleShot(1500, self._restart_app)
        else:
            self.statusBar().clearMessage()
            Toast(self, tr("update.failed", error="git pull"), duration=8000)

    def _restart_app(self):
        """Restart the application via os.execv."""
        os.execv(sys.executable, [sys.executable] + sys.argv)
