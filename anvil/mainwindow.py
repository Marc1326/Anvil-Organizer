"""Hauptfenster: Menü, Toolbar, Profil-Leiste, Splitter 65:35, Statusbar."""

from __future__ import annotations

from pathlib import Path

import shutil

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
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
from anvil.widgets.game_panel import GamePanel
from anvil.widgets.status_bar import StatusBarWidget
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
from anvil.core.categories import CategoryManager
from anvil.models.mod_list_model import mod_entry_to_row
from anvil.widgets.instance_wizard import CreateInstanceWizard


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


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
        self._profile_bar = ProfileBar(self)
        left_layout.addWidget(self._profile_bar)
        self._mod_list_view = ModListView()
        self._mod_list_view._tree.doubleClicked.connect(self._on_mod_double_click)
        self._mod_list_view.context_menu_requested.connect(self._on_mod_context_menu)
        left_layout.addWidget(self._mod_list_view)
        splitter.addWidget(left_pane)
        self._game_panel = GamePanel()
        splitter.addWidget(self._game_panel)
        splitter.setSizes([780, 420])
        main_layout.addWidget(splitter)

        # ── Log-Panel (toggleable via Ansicht → Log) ──────────────────
        self._log_panel = QTextEdit()
        self._log_panel.setReadOnly(True)
        self._log_panel.setMaximumHeight(150)
        self._log_panel.setPlaceholderText("Log-Ausgabe...")
        self._log_panel.setStyleSheet(
            "QTextEdit { font-family: monospace; font-size: 12px; }"
        )
        self._log_panel.setVisible(False)
        main_layout.addWidget(self._log_panel)

        self._status_bar = StatusBarWidget(self)
        self.setStatusBar(self._status_bar)

        # ── Restore view settings (toolbar size, visibility, etc.) ────
        self._restore_view_settings()

        # ── Right-click recovery for hidden menu bar ──────────────────
        # Install event filter on toolbar so right-click there also works
        self._toolbar.installEventFilter(self)

        # ── Category manager ────────────────────────────────────────────
        self._category_manager = CategoryManager()

        # ── Mod state ─────────────────────────────────────────────────
        self._current_mod_entries = []
        self._current_profile_path: Path | None = None
        self._current_instance_path: Path | None = None

        # Connect model signals for persistence
        model = self._mod_list_view.source_model()
        model.mod_toggled.connect(self._on_mod_toggled)
        model.mods_reordered.connect(self._on_mods_reordered)
        self._mod_list_view.archives_dropped.connect(
            self._on_archives_dropped, Qt.ConnectionType.QueuedConnection,
        )
        self._game_panel.install_requested.connect(self._on_downloads_install)
        self._game_panel.start_requested.connect(self._on_start_game)

        # ── Deferred tab header restore ──────────────────────────────
        self._pending_tab_states: dict[int, tuple] = {}
        self._game_panel._tabs.currentChanged.connect(self._on_tab_changed)

        # ── Erster Start / Instanz laden ──────────────────────────────
        self._check_first_start()

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
        act.setEnabled(False)

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

        # ── Log (Toggle) ──────────────────────────────────────────
        self._act_log = vm.addAction("Log")
        self._act_log.setCheckable(True)
        self._act_log.setChecked(False)
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

    def _on_menu_refresh(self) -> None:
        """Ansicht → Neu laden (F5)."""
        self._reload_mod_list()
        self.statusBar().showMessage("Mod-Liste neu geladen", 3000)

    def _on_toggle_log(self, checked: bool) -> None:
        """Ansicht → Log (Toggle)."""
        self._log_panel.setVisible(checked)

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
        SettingsDialog(self, self.plugin_loader).exec()

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

        log_vis = s.value("view/log_visible", False, type=bool)
        self._log_panel.setVisible(log_vis)
        self._act_log.setChecked(log_vis)

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

    def contextMenuEvent(self, event) -> None:
        """MainWindow-level right-click: show view recovery menu.

        This catches right-clicks that aren't consumed by child widgets,
        e.g. on empty areas of the central widget or margins.
        """
        self._show_view_recovery_menu(event.globalPos())

    def eventFilter(self, obj, event) -> bool:
        """Catch right-clicks on the toolbar for view recovery menu."""
        from PySide6.QtCore import QEvent
        if obj is self._toolbar and event.type() == QEvent.Type.ContextMenu:
            self._show_view_recovery_menu(event.globalPos())
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

        # 1. Title
        self.setWindowTitle(f"{game_name} \u2013 Anvil Organizer v0.1.0")

        # 2. Game panel — real directory contents + executables + icons
        self._game_panel.update_game(game_name, game_path, plugin, self.icon_manager, short_name)

        # 3. Mod list — scan filesystem and populate
        self._current_instance_path = self.instance_manager.instances_path() / instance_name
        instance_path = self._current_instance_path

        # Load categories for this instance
        self._category_manager.load(instance_path)
        self._mod_list_view.source_model().set_category_manager(self._category_manager)

        profile_name = data.get("selected_profile", "Default")
        self._current_profile_path = instance_path / ".profiles" / profile_name
        self._current_mod_entries = scan_mods_directory(instance_path, self._current_profile_path)
        # Mark direct-install (framework) mods
        direct_patterns = getattr(plugin, "GameDirectInstallMods", []) if plugin else []
        if direct_patterns:
            lp = [p.lower() for p in direct_patterns]
            for entry in self._current_mod_entries:
                name_lower = (entry.display_name or entry.name).lower()
                if any(pat in name_lower for pat in lp):
                    entry.is_direct_install = True
        mod_rows = [mod_entry_to_row(e) for e in self._current_mod_entries]
        self._mod_list_view.source_model().set_mods(mod_rows)
        self._update_active_count()

        # 4. Downloads tab
        self._game_panel.set_downloads_path(
            instance_path / ".downloads", instance_path / ".mods",
        )

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

    def _update_active_count(self) -> None:
        """Update the active mod counter in the profile bar."""
        count = sum(1 for e in self._current_mod_entries if e.enabled)
        self._profile_bar.update_active_count(count)

    # ── Mod installation ─────────────────────────────────────────────

    def _on_install_mod(self) -> None:
        """Menu: Datei → Mod installieren..."""
        if not self._current_instance_path:
            QMessageBox.warning(self, "Keine Instanz", "Bitte zuerst eine Instanz auswählen.")
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Mod-Archiv(e) auswählen",
            str(Path.home()),
            "Archive (*.zip *.rar *.7z);;Alle Dateien (*)",
        )
        if files:
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

        # Reload mod list
        self._current_mod_entries = scan_mods_directory(
            self._current_instance_path, self._current_profile_path,
        )
        mod_rows = [mod_entry_to_row(e) for e in self._current_mod_entries]
        self._mod_list_view.source_model().set_mods(mod_rows)
        self._update_active_count()

        names = ", ".join(installed)
        self.statusBar().showMessage(f"Installiert: {names}", 5000)

    # ── Other slots ───────────────────────────────────────────────────

    def _on_mod_double_click(self):
        mod_name = self._mod_list_view.get_current_mod_name()
        if mod_name:
            ModDetailDialog(self, mod_name=mod_name).exec()

    # ── Mod list context menu ──────────────────────────────────────

    def _on_mod_context_menu(self, global_pos) -> None:
        """Build and show the mod list context menu (MO2 structure)."""
        if not self._current_instance_path:
            return

        selected_rows = self._mod_list_view.get_selected_source_rows()
        has_selection = len(selected_rows) > 0
        single = len(selected_rows) == 1

        menu = QMenu(self)

        # ── Alle Mods (Submenu) ────────────────────────────────────
        all_mods_menu = menu.addMenu("Alle Mods")
        act = all_mods_menu.addAction("Installiere Mod über...")
        act.setEnabled(False)
        act = all_mods_menu.addAction("Erstelle leere Mod über...")
        act.setEnabled(False)
        act_create_sep = all_mods_menu.addAction("Erstelle Trenner über...")
        all_mods_menu.addSeparator()
        act = all_mods_menu.addAction("Alle einklappen")
        act.setEnabled(False)
        act = all_mods_menu.addAction("Alle ausklappen")
        act.setEnabled(False)
        all_mods_menu.addSeparator()
        act_enable_all = all_mods_menu.addAction("Aktiviere alle")
        act_disable_all = all_mods_menu.addAction("Deaktiviere alle")
        act = all_mods_menu.addAction("Auf Updates prüfen")
        act.setEnabled(False)
        act = all_mods_menu.addAction("Kategorien automatisch zuweisen")
        act.setEnabled(False)
        act_reload = all_mods_menu.addAction("Neu laden")
        act = all_mods_menu.addAction("Als CSV exportieren...")
        act.setEnabled(False)

        # ── Kategorien (Submenus, MO2-Pattern) ────────────────────
        andere_kat_menu = menu.addMenu("Andere Kategorien")
        primaere_kat_menu = menu.addMenu("Primäre Kategorie")
        _cat_checkboxes = []  # keep refs: (cat_id, QCheckBox)
        _primary_radios = []  # keep refs: (cat_id, QRadioButton)

        if single and selected_rows[0] < len(self._current_mod_entries):
            entry = self._current_mod_entries[selected_rows[0]]
            assigned_ids = set(entry.category_ids)

            # "Andere Kategorien" — checkboxes for all categories
            from PySide6.QtWidgets import QCheckBox, QWidgetAction, QRadioButton
            for cat in self._category_manager.all_categories():
                cb = QCheckBox(cat["name"], andere_kat_menu)
                cb.setChecked(cat["id"] in assigned_ids)
                wa = QWidgetAction(andere_kat_menu)
                wa.setDefaultWidget(cb)
                wa.setData(cat["id"])
                andere_kat_menu.addAction(wa)
                _cat_checkboxes.append((cat["id"], cb))

            # "Primäre Kategorie" — radio buttons (only assigned categories)
            if assigned_ids:
                for cat_id in entry.category_ids:
                    name = self._category_manager.get_name(cat_id)
                    if not name:
                        continue
                    rb = QRadioButton(name, primaere_kat_menu)
                    rb.setChecked(cat_id == entry.primary_category)
                    wa = QWidgetAction(primaere_kat_menu)
                    wa.setDefaultWidget(rb)
                    wa.setData(cat_id)
                    primaere_kat_menu.addAction(wa)
                    _primary_radios.append((cat_id, rb))
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

        # Apply category changes (MO2 aboutToHide pattern)
        if single and _cat_checkboxes and selected_rows[0] < len(self._current_mod_entries):
            self._apply_category_changes(
                selected_rows[0], _cat_checkboxes, _primary_radios,
            )

        if not chosen:
            return

        if chosen == act_create_sep:
            self._ctx_create_separator()
        elif chosen == act_enable_all:
            self._ctx_enable_all(True)
        elif chosen == act_disable_all:
            self._ctx_enable_all(False)
        elif chosen == act_reload:
            self._on_menu_refresh()
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
        """Reload mod list from disk and update UI."""
        self._current_mod_entries = scan_mods_directory(
            self._current_instance_path, self._current_profile_path,
        )
        mod_rows = [mod_entry_to_row(e) for e in self._current_mod_entries]
        self._mod_list_view.source_model().set_mods(mod_rows)
        self._update_active_count()

    # ── UI state persistence ───────────────────────────────────────

    @staticmethod
    def _settings() -> QSettings:
        """Return QSettings with a fixed path independent of Flatpak sandbox."""
        path = str(Path.home() / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf")
        return QSettings(path, QSettings.Format.IniFormat)

    def _save_ui_state(self) -> None:
        """Persist splitter, mod-list, downloads column widths and view settings."""
        s = self._settings()
        s.setValue("splitter/state", self._splitter.saveState())
        s.setValue("mod_list/header_state", self._mod_list_view.header().saveState())
        s.setValue("downloads/header_state",
                   self._game_panel._dl_table.horizontalHeader().saveState())
        s.setValue("data/header_state",
                   self._game_panel._data_tree.header().saveState())
        s.setValue("saves/header_state",
                   self._game_panel._saves_tree.header().saveState())
        # View settings
        s.setValue("view/menubar_visible", self.menuBar().isVisible())
        s.setValue("view/toolbar_visible", self._toolbar.isVisible())
        s.setValue("view/statusbar_visible", self._status_bar.isVisible())
        s.setValue("view/log_visible", self._log_panel.isVisible())
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
        """Restore splitter, mod-list and tab column widths.

        Tab headers (Daten/Spielstände/Downloads) are restored deferred:
        hidden tabs ignore restoreState(), so we store the bytes and
        apply them when the tab becomes visible for the first time.
        """
        s = self._settings()
        val = s.value("splitter/state")
        if val:
            self._splitter.restoreState(val)
        val = s.value("mod_list/header_state")
        if val:
            self._mod_list_view.header().restoreState(val)

        # Tab headers: deferred restore (hidden tabs ignore restoreState)
        tab_map = {
            0: ("data/header_state", lambda: self._game_panel._data_tree.header()),
            1: ("saves/header_state", lambda: self._game_panel._saves_tree.header()),
            2: ("downloads/header_state", lambda: self._game_panel._dl_table.horizontalHeader()),
        }
        self._pending_tab_states.clear()
        for tab_idx, (key, header_fn) in tab_map.items():
            val = s.value(key)
            if val:
                self._pending_tab_states[tab_idx] = (val, header_fn)

        # Restore the currently active tab immediately (it's visible)
        active = self._game_panel._tabs.currentIndex()
        if active in self._pending_tab_states:
            val, header_fn = self._pending_tab_states.pop(active)
            header_fn().restoreState(val)

    def _on_tab_changed(self, index: int) -> None:
        """Restore header state when a tab becomes visible for the first time."""
        if index in self._pending_tab_states:
            val, header_fn = self._pending_tab_states.pop(index)
            header_fn().restoreState(val)

    def closeEvent(self, event) -> None:
        # Purge deployed mods before closing
        self._game_panel.silent_purge()
        self._save_ui_state()
        super().closeEvent(event)

    # ── Other slots ───────────────────────────────────────────────────

    def _on_about(self):
        QMessageBox.about(self, "Über Anvil Organizer", "Anvil Organizer v0.1.0\n\nPlatzhalter-GUI.")
