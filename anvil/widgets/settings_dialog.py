"""Einstellungen — QDialog."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QGroupBox,
    QComboBox,
    QCheckBox,
    QPushButton,
    QScrollArea,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QFormLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QSpinBox,
)
from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Qt, QSettings

from anvil.plugins.plugin_loader import PluginLoader, ensure_user_plugin_dir
from anvil.styles.dark_theme import list_themes, load_theme, get_styles_dir, default_theme
from anvil.core.nexus_api import NexusAPI
from anvil.core.nexus_sso import NexusSSOLogin
from anvil.core.translator import Translator, tr

class SettingsDialog(QDialog):
    def __init__(self, parent=None, plugin_loader: PluginLoader | None = None,
                 instance_manager=None):
        super().__init__(parent)
        self._plugin_loader = plugin_loader
        self._instance_manager = instance_manager
        self.setWindowTitle(tr("dialog.settings_title"))
        self.setMinimumSize(960, 600)
        self.resize(960, 600)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        settings = self._settings()
        self._tabs = QTabWidget()

        # Load instance data (used by multiple tabs)
        self._idata = {}
        self._instance_path = None
        if self._instance_manager is not None:
            cur = self._instance_manager.current_instance()
            if cur:
                self._idata = self._instance_manager.load_instance(cur)
                self._instance_path = self._instance_manager.instances_path() / cur

        # Helper: Widget deaktivieren + Tooltip setzen
        def _disabled(w):
            w.setEnabled(False)
            w.setToolTip(tr("settings.coming_soon"))
            return w

        # Tab Allgemein
        allgemein = QWidget()
        ag_layout = QVBoxLayout(allgemein)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # Gruppe Sprache
        lang_grp = QGroupBox(tr("settings.language"))
        lang_layout = QVBoxLayout(lang_grp)
        self._lang_combo = QComboBox()
        # Verfügbare Sprachen aus Translator laden
        translator = Translator.instance()
        self._lang_codes: list[str] = []
        for code, name in translator.available_languages():
            self._lang_combo.addItem(name)
            self._lang_codes.append(code)
        # Gespeicherte Sprache auswählen
        saved_lang = settings.value("General/language", "de")
        self._initial_lang = saved_lang  # Für Auto-Restart bei Änderung
        if saved_lang in self._lang_codes:
            self._lang_combo.setCurrentIndex(self._lang_codes.index(saved_lang))
        lang_layout.addWidget(self._lang_combo)
        # Hinweis: Neustart erforderlich
        lang_hint = QLabel(tr("settings.language_restart_hint"))
        lang_hint.setStyleSheet("color: #808080; font-style: italic; font-size: 11px;")
        lang_layout.addWidget(lang_hint)
        scroll_layout.addWidget(lang_grp)

        # Gruppe Download Liste
        dl_grp = QGroupBox(tr("settings.download_list"))
        dl_layout = QVBoxLayout(dl_grp)
        self._cb_show_meta = QCheckBox(tr("settings.show_meta_info"))
        self._cb_show_meta.setChecked(
            settings.value("Interface/show_meta_info", False, type=bool))
        dl_layout.addWidget(self._cb_show_meta)
        self._cb_compact_list = QCheckBox(tr("settings.compact_list"))
        self._cb_compact_list.setChecked(
            settings.value("Interface/compact_list", False, type=bool))
        dl_layout.addWidget(self._cb_compact_list)
        self._cb_hide_downloads = QCheckBox(tr("settings.hide_downloads_after_install"))
        self._cb_hide_downloads.setChecked(
            settings.value("Interface/hide_downloads_after_install", False, type=bool))
        dl_layout.addWidget(self._cb_hide_downloads)

        scroll_layout.addWidget(dl_grp)

        # Gruppe Updates
        up_grp = QGroupBox(tr("settings.updates"))
        up_layout = QVBoxLayout(up_grp)
        self._cb_check_updates = QCheckBox(tr("settings.check_for_updates"))
        self._cb_check_updates.setChecked(
            settings.value("General/check_for_updates", True, type=bool))
        up_layout.addWidget(self._cb_check_updates)
        scroll_layout.addWidget(up_grp)

        # Gruppe Profil-Standardeinstellungen
        prof_grp = QGroupBox(tr("settings.profile_defaults"))
        prof_layout = QVBoxLayout(prof_grp)
        self._cb_local_inis = QCheckBox(tr("settings.local_inis"))
        self._cb_local_inis.setChecked(
            str(self._idata.get("local_inis", "true")).lower() in ("true", "1"))
        prof_layout.addWidget(self._cb_local_inis)
        self._cb_local_saves = QCheckBox(tr("settings.local_saves"))
        self._cb_local_saves.setChecked(
            str(self._idata.get("local_saves", "false")).lower() in ("true", "1"))
        prof_layout.addWidget(self._cb_local_saves)
        prof_layout.addWidget(_disabled(QCheckBox(tr("settings.auto_archive_invalidation"))))
        scroll_layout.addWidget(prof_grp)

        # Gruppe Sonstiges
        misc_grp = QGroupBox(tr("settings.misc"))
        misc_layout = QVBoxLayout(misc_grp)
        self._cb_center_dialogs = QCheckBox(tr("settings.center_dialogs"))
        self._cb_center_dialogs.setChecked(
            settings.value("Interface/center_dialogs", False, type=bool))
        misc_layout.addWidget(self._cb_center_dialogs)
        self._cb_confirm_instance = QCheckBox(tr("settings.confirm_instance_change"))
        self._cb_confirm_instance.setChecked(
            settings.value("Interface/confirm_instance_change", True, type=bool))
        misc_layout.addWidget(self._cb_confirm_instance)
        self._cb_alt_menubar = QCheckBox(tr("settings.alt_shows_menubar"))
        self._cb_alt_menubar.setChecked(
            settings.value("Interface/show_menubar_on_alt", True, type=bool))
        misc_layout.addWidget(self._cb_alt_menubar)
        cb_preview = QCheckBox(tr("settings.open_preview_dblclick"))
        cb_preview.setChecked(True)
        _disabled(cb_preview)
        misc_layout.addWidget(cb_preview)
        scroll_layout.addWidget(misc_grp)

        misc_btn_row = QHBoxLayout()
        btn_reset_dialogs = QPushButton(tr("settings.reset_dialog_options"))
        btn_reset_dialogs.clicked.connect(lambda checked=False: self._reset_dialog_options())
        misc_btn_row.addWidget(btn_reset_dialogs)
        misc_btn_row.addWidget(_disabled(QPushButton(tr("settings.edit_categories"))))
        misc_btn_row.addStretch()
        scroll_layout.addLayout(misc_btn_row)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        ag_layout.addWidget(scroll)
        self._tabs.addTab(allgemein, tr("settings.tab_general"))

        # Tab Style
        style_tab = QWidget()
        style_layout = QVBoxLayout(style_tab)
        stil_grp = QGroupBox(tr("settings.style"))
        stil_layout = QHBoxLayout(stil_grp)
        self._stil_combo = QComboBox()
        # Available themes from anvil/styles/*.qss
        themes = list_themes()
        self._stil_combo.addItems(themes)
        # Load saved theme from QSettings
        saved = settings.value("style/theme", default_theme())
        idx = self._stil_combo.findText(saved)
        if idx >= 0:
            self._stil_combo.setCurrentIndex(idx)
        self._previous_theme = self._stil_combo.currentText()
        self._stil_combo.currentTextChanged.connect(self._on_theme_changed)
        stil_layout.addWidget(self._stil_combo)
        erkunden_btn = QPushButton(tr("settings.explore"))
        erkunden_btn.clicked.connect(self._open_styles_folder)
        stil_layout.addWidget(erkunden_btn)
        style_layout.addWidget(stil_grp)
        farben_grp = QGroupBox(tr("settings.colors"))
        farben_layout = QVBoxLayout(farben_grp)
        color_table = QTableWidget(6, 4)
        color_table.setHorizontalHeaderLabels([
            tr("settings.color_description"),
            tr("settings.color_text_button"),
            tr("settings.color_icons"),
            tr("settings.color_background"),
        ])
        color_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        _rows = [
            (tr("settings.color_overwritten_loose"), "#2d5a2d"),
            (tr("settings.color_overwrites_loose"), "#5a2020"),
            (tr("settings.color_overwritten_archive"), "#006868"),
            (tr("settings.color_overwrites_archive"), "#5a2020"),
            (tr("settings.color_mod_contains_plugin"), "#4a2d5a"),
            (tr("settings.color_plugin_in_mod"), "#1a3a5a"),
        ]
        for row, (desc, bg_hex) in enumerate(_rows):
            color_table.setItem(row, 0, QTableWidgetItem(desc))
            color_table.setCellWidget(row, 1, _disabled(QPushButton(tr("settings.color_text"))))
            color_table.setItem(row, 2, QTableWidgetItem(""))
            bg_item = QTableWidgetItem("")
            bg_item.setBackground(QColor(bg_hex))
            color_table.setItem(row, 3, bg_item)
        farben_layout.addWidget(color_table)
        style_layout.addWidget(farben_grp)
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_row.addWidget(_disabled(QPushButton(tr("settings.reset_colors"))))
        reset_row.addStretch()
        style_layout.addLayout(reset_row)
        self._tabs.addTab(style_tab, tr("settings.tab_style"))

        # Tab Mod Liste
        modliste_tab = QWidget()
        ml_layout = QVBoxLayout(modliste_tab)
        self._cb_separator_colors = QCheckBox(tr("settings.show_separator_colors"))
        self._cb_separator_colors.setChecked(
            settings.value("ModList/show_separator_colors", True, type=bool))
        ml_layout.addWidget(self._cb_separator_colors)
        self._cb_external_mods = QCheckBox(tr("settings.show_external_mods"))
        self._cb_external_mods.setChecked(
            settings.value("ModList/show_external_mods", True, type=bool))
        ml_layout.addWidget(self._cb_external_mods)
        self._cb_remember_filters = QCheckBox(tr("settings.remember_filters"))
        self._cb_remember_filters.setChecked(
            settings.value("ModList/remember_filters", False, type=bool))
        ml_layout.addWidget(self._cb_remember_filters)
        self._cb_check_updates_install = QCheckBox(tr("settings.check_updates_after_install"))
        self._cb_check_updates_install.setChecked(
            settings.value("ModList/check_updates_after_install", True, type=bool))
        ml_layout.addWidget(self._cb_check_updates_install)
        self._cb_auto_collapse_drag = QCheckBox(tr("settings.auto_collapse_on_drag"))
        self._cb_auto_collapse_drag.setChecked(
            settings.value("ModList/auto_collapse_on_drag", False, type=bool))
        ml_layout.addWidget(self._cb_auto_collapse_drag)
        sep_grp = QGroupBox(tr("settings.collapsible_separators"))
        sep_layout = QVBoxLayout(sep_grp)
        sort_row = QHBoxLayout()
        sort_row.addWidget(QLabel(tr("label.enable_when_sorted")))
        self._cb_collapsible_asc = QCheckBox(tr("settings.ascending_priority"))
        self._cb_collapsible_asc.setChecked(
            settings.value("ModList/collapsible_asc", True, type=bool))
        self._cb_collapsible_dsc = QCheckBox(tr("settings.descending_priority"))
        self._cb_collapsible_dsc.setChecked(
            settings.value("ModList/collapsible_dsc", True, type=bool))
        sort_row.addWidget(self._cb_collapsible_asc)
        sort_row.addWidget(self._cb_collapsible_dsc)
        sort_row.addStretch()
        sep_layout.addLayout(sort_row)
        conflict_row = QHBoxLayout()
        conflict_row.addWidget(QLabel(tr("label.show_conflicts_plugins")))
        self._cb_conflicts_on_sep = QCheckBox(tr("settings.on_separator"))
        self._cb_conflicts_on_sep.setChecked(
            settings.value("ModList/conflicts_on_separator", True, type=bool))
        self._cb_conflicts_from_sep = QCheckBox(tr("settings.from_separator"))
        self._cb_conflicts_from_sep.setChecked(
            settings.value("ModList/conflicts_from_separator", True, type=bool))
        conflict_row.addWidget(self._cb_conflicts_on_sep)
        conflict_row.addWidget(self._cb_conflicts_from_sep)
        conflict_row.addStretch()
        sep_layout.addLayout(conflict_row)
        symbol_row = QHBoxLayout()
        symbol_row.addWidget(QLabel(tr("label.show_separator_symbols")))
        self._cb_sym_conflicts = QCheckBox(tr("settings.symbol_conflicts"))
        self._cb_sym_conflicts.setChecked(
            settings.value("ModList/symbol_conflicts", True, type=bool))
        symbol_row.addWidget(self._cb_sym_conflicts)
        self._cb_sym_flags = QCheckBox(tr("settings.symbol_flags"))
        self._cb_sym_flags.setChecked(
            settings.value("ModList/symbol_flags", True, type=bool))
        symbol_row.addWidget(self._cb_sym_flags)
        self._cb_sym_content = QCheckBox(tr("settings.symbol_content"))
        self._cb_sym_content.setChecked(
            settings.value("ModList/symbol_content", True, type=bool))
        symbol_row.addWidget(self._cb_sym_content)
        self._cb_sym_version = QCheckBox(tr("settings.symbol_version"))
        self._cb_sym_version.setChecked(
            settings.value("ModList/symbol_version", True, type=bool))
        symbol_row.addWidget(self._cb_sym_version)
        symbol_row.addStretch()
        sep_layout.addLayout(symbol_row)
        ml_layout.addWidget(sep_grp)
        self._cb_collapse_per_profile = QCheckBox(tr("settings.profile_dependent_collapse"))
        self._cb_collapse_per_profile.setChecked(
            settings.value("ModList/collapse_per_profile", False, type=bool))
        ml_layout.addWidget(self._cb_collapse_per_profile)
        # Signal-Verbindungen fuer Gruppen-Deaktivierung (MO2-Verhalten)
        self._cb_collapsible_asc.toggled.connect(self._update_separator_group)
        self._cb_collapsible_dsc.toggled.connect(self._update_separator_group)
        self._update_separator_group()  # Initialer Zustand
        ml_layout.addStretch()
        self._tabs.addTab(modliste_tab, tr("settings.tab_modlist"))

        # Tab Pfade
        pfade_tab = QWidget()
        pf_layout = QVBoxLayout(pfade_tab)
        pf_scroll = QScrollArea()
        pf_scroll.setWidgetResizable(True)
        pf_scroll.setFrameShape(QFrame.Shape.NoFrame)
        pf_content = QWidget()
        pf_content_layout = QVBoxLayout(pf_content)

        def make_browse(line_edit, title):
            def browse():
                path = QFileDialog.getExistingDirectory(self, title, line_edit.text())
                if path:
                    line_edit.setText(path)
            return browse

        def add_path_row(form, label, text_or_placeholder, is_placeholder=True, readonly=False):
            le = QLineEdit()
            if is_placeholder:
                le.setPlaceholderText(text_or_placeholder)
            else:
                le.setText(text_or_placeholder)
            le.setReadOnly(readonly)

            btn = QPushButton("...")
            btn.setFixedWidth(40)
            btn.setEnabled(not readonly)
            if not readonly:
                btn.clicked.connect(make_browse(le, label))

            row = QHBoxLayout()
            row.addWidget(le)
            row.addWidget(btn)
            form.addRow(label, row)
            return le

        # ── Resolve paths from the active instance ──────────────
        _base_dir = ""
        _downloads = ""
        _mods = ""
        _caches = ""
        _profiles = ""
        _overwrite = ""
        _game_path = ""

        if self._instance_path is not None:
            ipath = self._instance_path
            _base_dir = str(ipath)

            def _resolve(val: str) -> str:
                return val.replace("%INSTANCE_DIR%", str(ipath))

            _downloads = _resolve(self._idata.get("path_downloads_directory", ""))
            _mods = _resolve(self._idata.get("path_mods_directory", ""))
            _profiles = _resolve(self._idata.get("path_profiles_directory", ""))
            _overwrite = _resolve(self._idata.get("path_overwrite_directory", ""))
            _caches = str(ipath / ".webcache")
            _game_path = self._idata.get("game_path", "")

        pf_form = QFormLayout()
        add_path_row(pf_form, tr("settings.path_base_dir"), _base_dir, False, readonly=True)
        self._le_downloads = add_path_row(pf_form, tr("settings.path_downloads"), _downloads, False)
        self._le_mods = add_path_row(pf_form, tr("settings.path_mods"), _mods, False)
        add_path_row(pf_form, tr("settings.path_caches"), _caches, False, readonly=True)
        self._le_profiles = add_path_row(pf_form, tr("settings.path_profiles"), _profiles, False)
        self._le_overwrite = add_path_row(pf_form, tr("settings.path_overwrite"), _overwrite, False)
        pf_content_layout.addLayout(pf_form)
        pf_content_layout.addWidget(QLabel(tr("label.base_dir_hint")))
        pf_content_layout.addSpacing(16)
        pf_game_form = QFormLayout()
        self._le_game_path = add_path_row(pf_game_form, tr("settings.path_managed_game"), _game_path, False)
        pf_content_layout.addLayout(pf_game_form)
        pf_content_layout.addStretch()
        pf_content_layout.addWidget(QLabel(tr("label.writable_dirs_hint")))
        pf_scroll.setWidget(pf_content)
        pf_layout.addWidget(pf_scroll)
        self._tabs.addTab(pfade_tab, tr("settings.tab_paths"))

        # Tab Nexus
        nexus_tab = QWidget()
        nx_layout = QVBoxLayout(nexus_tab)
        nx_scroll = QScrollArea()
        nx_scroll.setWidgetResizable(True)
        nx_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nx_content = QWidget()
        nx_content_layout = QVBoxLayout(nx_content)

        # ── Nexus-Konto (read-only, populated after validation) ──────
        konto_grp = QGroupBox(tr("settings.nexus_account"))
        konto_layout = QHBoxLayout(konto_grp)
        konto_left = QFormLayout()
        self._nx_uid = QLineEdit()
        self._nx_uid.setReadOnly(True)
        self._nx_uid.setPlaceholderText("—")
        konto_left.addRow(tr("settings.nexus_user_id"), self._nx_uid)
        self._nx_name = QLineEdit()
        self._nx_name.setReadOnly(True)
        self._nx_name.setPlaceholderText("—")
        konto_left.addRow(tr("settings.nexus_name"), self._nx_name)
        self._nx_account = QLineEdit()
        self._nx_account.setReadOnly(True)
        self._nx_account.setPlaceholderText("—")
        konto_left.addRow(tr("settings.nexus_account_type"), self._nx_account)
        konto_layout.addLayout(konto_left)
        konto_layout.addSpacing(24)
        stats = QFormLayout()
        self._nx_daily = QLineEdit()
        self._nx_daily.setReadOnly(True)
        self._nx_daily.setPlaceholderText("—")
        stats.addRow(tr("settings.nexus_daily_requests"), self._nx_daily)
        self._nx_hourly = QLineEdit()
        self._nx_hourly.setReadOnly(True)
        self._nx_hourly.setPlaceholderText("—")
        stats.addRow(tr("settings.nexus_hourly_requests"), self._nx_hourly)
        konto_layout.addLayout(stats)
        nx_content_layout.addWidget(konto_grp)

        # ── Nexus-Verbindung (MO2 layout: log + 3 buttons) ────────
        verb_grp = QGroupBox(tr("settings.nexus_connection"))
        verb_layout = QHBoxLayout(verb_grp)

        # Left: buttons
        btn_col = QVBoxLayout()
        self._btn_connect = QPushButton(tr("button.connect_nexus"))
        self._btn_connect.clicked.connect(self._nx_connect_sso)
        btn_col.addWidget(self._btn_connect)
        self._btn_api_key = QPushButton(tr("settings.nexus_enter_api_key"))
        self._btn_api_key.clicked.connect(self._nx_enter_api_key)
        btn_col.addWidget(self._btn_api_key)
        self._btn_disconnect = QPushButton(tr("settings.nexus_disconnect"))
        self._btn_disconnect.clicked.connect(self._nx_disconnect)
        btn_col.addWidget(self._btn_disconnect)
        btn_col.addStretch()
        verb_layout.addLayout(btn_col)

        # Right: status label + log list
        log_col = QVBoxLayout()
        self._nx_status_label = QLabel(tr("status.not_connected"))
        log_col.addWidget(self._nx_status_label)
        self._nx_log = QListWidget()
        self._nx_log.setMaximumHeight(80)
        self._nx_log.setStyleSheet("QListWidget { font-size: 11px; }")
        log_col.addWidget(self._nx_log)
        verb_layout.addLayout(log_col, 1)

        nx_content_layout.addWidget(verb_grp)

        # ── Optionen ─────────────────────────────────────────────────
        opt_grp = QGroupBox(tr("settings.options"))
        opt_layout = QHBoxLayout(opt_grp)
        opt_left = QVBoxLayout()
        for key, checked in (
            ("settings.nexus_endorsement", True),
            ("settings.nexus_tracking", True),
            ("settings.nexus_category_mapping", True),
            ("settings.nexus_hide_api_counter", False),
        ):
            cb = QCheckBox(tr(key))
            cb.setChecked(checked)
            _disabled(cb)
            opt_left.addWidget(cb)
        opt_layout.addLayout(opt_left)
        opt_right = QVBoxLayout()
        btn_link = QPushButton(tr("settings.nexus_link_nxm"))
        btn_link.clicked.connect(self._nx_register_nxm_handler)
        _disabled(btn_link)
        opt_right.addWidget(btn_link)
        opt_right.addWidget(_disabled(QPushButton(tr("settings.nexus_clear_cache"))))
        opt_right.addStretch()
        opt_layout.addLayout(opt_right)
        nx_content_layout.addWidget(opt_grp)

        # ── Server ───────────────────────────────────────────────────
        server_grp = QGroupBox(tr("settings.nexus_server"))
        server_layout = QHBoxLayout(server_grp)
        known_lbl = QLabel(tr("label.known_servers"))
        server_left = QVBoxLayout()
        server_left.addWidget(known_lbl)
        known_list = QListWidget()
        for city in ("Amsterdam", "Prague", "Chicago", "Los Angeles", "Miami", "Dallas"):
            known_list.addItem(QListWidgetItem(city))
        _disabled(known_list)
        server_left.addWidget(known_list)
        server_layout.addLayout(server_left)
        pref_lbl = QLabel(tr("label.preferred_servers"))
        server_right = QVBoxLayout()
        server_right.addWidget(pref_lbl)
        pref_list = QListWidget()
        pref_list.addItem(QListWidgetItem("Nexus CDN (58.45 MB/s)"))
        _disabled(pref_list)
        server_right.addWidget(pref_list)
        server_layout.addLayout(server_right)
        nx_content_layout.addWidget(server_grp)

        nx_content_layout.addStretch()
        nx_scroll.setWidget(nx_content)
        nx_layout.addWidget(nx_scroll)
        self._tabs.addTab(nexus_tab, tr("settings.tab_nexus"))

        # ── Init Nexus API, SSO, and load saved key ─────────────────
        self._nexus_api = NexusAPI(self)
        self._nexus_api.user_validated.connect(self._nx_on_validated)
        self._nexus_api.request_error.connect(self._nx_on_error)
        self._nexus_api.rate_limit_updated.connect(self._nx_on_rate_limit)
        self._sso_login: NexusSSOLogin | None = None
        saved_key = settings.value("nexus/api_key", "")
        if saved_key:
            self._nexus_api.set_api_key(saved_key)
            self._nx_log_add("API-Schlüssel überprüfen...")
            self._nexus_api.validate_key()
        else:
            self._nx_log_add(tr("status.not_connected"))
        self._nx_update_button_states()

        # Tab Plugins
        plugins_tab = QWidget()
        pl_layout = QHBoxLayout(plugins_tab)

        # ── Left: Plugin tree + filter + open-folder button ────────
        pl_left = QVBoxLayout()
        self._pl_tree = QTreeWidget()
        self._pl_tree.setHeaderLabels([tr("label.header_plugin"), tr("label.header_version")])
        self._pl_tree.setMinimumWidth(280)
        self._pl_tree.setColumnWidth(0, 220)

        _italic_font = QFont()
        _italic_font.setItalic(True)

        games_root = QTreeWidgetItem(self._pl_tree, [tr("settings.plugins_games"), ""])
        games_root.setExpanded(True)

        self._plugin_items: dict[str, object] = {}  # short_name → BaseGame

        if self._plugin_loader:
            for plugin in self._plugin_loader.all_plugins():
                item = QTreeWidgetItem(games_root, [plugin.Name, plugin.Version])
                item.setCheckState(0, Qt.CheckState.Checked)
                item.setData(0, Qt.ItemDataRole.UserRole, plugin.GameShortName)
                if not plugin.isInstalled():
                    item.setFont(0, _italic_font)
                    item.setFont(1, _italic_font)
                self._plugin_items[plugin.GameShortName] = plugin

        pl_left.addWidget(self._pl_tree)
        pl_filter = QLineEdit()
        pl_filter.setPlaceholderText(tr("placeholder.filter"))
        pl_filter.textChanged.connect(self._filter_plugins)
        pl_left.addWidget(pl_filter)

        open_folder_btn = QPushButton(tr("settings.plugins_open_folder"))
        open_folder_btn.clicked.connect(self._open_plugin_folder)
        pl_left.addWidget(open_folder_btn)

        pl_layout.addLayout(pl_left)

        # ── Right: Plugin detail panel ─────────────────────────────
        pl_right = QVBoxLayout()
        self._pl_detail = QFormLayout()
        self._pl_author = QLineEdit()
        self._pl_author.setReadOnly(True)
        self._pl_detail.addRow(tr("settings.plugins_author"), self._pl_author)
        self._pl_version = QLineEdit()
        self._pl_version.setReadOnly(True)
        self._pl_detail.addRow(tr("settings.plugins_version"), self._pl_version)
        self._pl_game_name = QLineEdit()
        self._pl_game_name.setReadOnly(True)
        self._pl_detail.addRow(tr("settings.plugins_game"), self._pl_game_name)
        self._pl_store = QLineEdit()
        self._pl_store.setReadOnly(True)
        self._pl_detail.addRow(tr("settings.plugins_store"), self._pl_store)
        self._pl_path = QLineEdit()
        self._pl_path.setReadOnly(True)
        self._pl_detail.addRow(tr("settings.plugins_game_path"), self._pl_path)
        self._pl_prefix = QLineEdit()
        self._pl_prefix.setReadOnly(True)
        self._pl_detail.addRow(tr("settings.plugins_proton_prefix"), self._pl_prefix)
        self._pl_cb_active = QCheckBox(tr("settings.plugins_enabled"))
        self._pl_cb_active.setChecked(True)
        _disabled(self._pl_cb_active)
        self._pl_detail.addRow(self._pl_cb_active)
        pl_right.addLayout(self._pl_detail)

        # Nexus + Support Info
        self._pl_nexus = QLabel("")
        self._pl_nexus.setOpenExternalLinks(True)
        pl_right.addWidget(self._pl_nexus)

        pl_right.addStretch()

        # Summary
        if self._plugin_loader:
            count = self._plugin_loader.plugin_count()
            installed = self._plugin_loader.installed_count()
            summary = QLabel(tr("settings.plugins_summary", count=count, installed=installed))
        else:
            summary = QLabel(tr("label.plugin_loader_not_available"))
        summary.setStyleSheet("color: #808080; font-style: italic;")
        pl_right.addWidget(summary)

        pl_layout.addLayout(pl_right, 1)
        self._tabs.addTab(plugins_tab, tr("settings.tab_plugins"))

        # Connect selection change + select first plugin
        self._pl_tree.currentItemChanged.connect(self._on_plugin_selected)
        if self._plugin_loader and self._plugin_loader.plugin_count() > 0:
            first_child = games_root.child(0)
            if first_child:
                self._pl_tree.setCurrentItem(first_child)

        # Tab Workarounds
        workarounds_tab = QWidget()
        wa_layout = QVBoxLayout(workarounds_tab)
        wa_scroll = QScrollArea()
        wa_scroll.setWidgetResizable(True)
        wa_scroll.setFrameShape(QFrame.Shape.NoFrame)
        wa_content = QWidget()
        wa_content_layout = QVBoxLayout(wa_content)
        opt_wa_grp = QGroupBox(tr("settings.options"))
        opt_wa_layout = QVBoxLayout(opt_wa_grp)
        cb_load = QCheckBox(tr("settings.wa_force_load_game_files"))
        cb_load.setChecked(True)
        _disabled(cb_load)
        opt_wa_layout.addWidget(cb_load)
        cb_arch = QCheckBox(tr("settings.wa_archive_parsing"))
        cb_arch.setChecked(False)
        _disabled(cb_arch)
        opt_wa_layout.addWidget(cb_arch)
        cb_lock = QCheckBox(tr("settings.wa_lock_gui"))
        cb_lock.setChecked(True)
        _disabled(cb_lock)
        opt_wa_layout.addWidget(cb_lock)
        wa_content_layout.addWidget(opt_wa_grp)
        steam_grp = QGroupBox("Steam")
        steam_layout = QFormLayout(steam_grp)
        steam_layout.addRow(tr("settings.wa_steam_appid"), _disabled(QLineEdit("1091500")))
        steam_layout.addRow(tr("settings.wa_steam_username"), _disabled(QLineEdit()))
        steam_layout.addRow(tr("settings.wa_steam_password"), _disabled(QLineEdit()))
        wa_content_layout.addWidget(steam_grp)
        net_grp = QGroupBox(tr("settings.wa_network"))
        net_layout = QVBoxLayout(net_grp)
        net_layout.addWidget(_disabled(QCheckBox(tr("settings.wa_offline_mode"))))
        net_layout.addWidget(_disabled(QCheckBox(tr("settings.wa_system_proxy"))))
        browser_row = QHBoxLayout()
        cb_browser = QCheckBox(tr("settings.wa_custom_browser"))
        cb_browser.setChecked(False)
        _disabled(cb_browser)
        browser_row.addWidget(cb_browser)
        browser_row.addWidget(_disabled(QLineEdit()))
        browser_row.addWidget(_disabled(QPushButton("...")))
        net_layout.addLayout(browser_row)
        wa_content_layout.addWidget(net_grp)
        btn_row_wa = QHBoxLayout()
        btn_row_wa.addWidget(_disabled(QPushButton(tr("settings.wa_reset_geometry"))))
        btn_row_wa.addWidget(_disabled(QPushButton(tr("settings.wa_backdate_bsa"))))
        btn_row_wa.addWidget(_disabled(QPushButton(tr("settings.wa_app_blocklist"))))
        btn_row_wa.addWidget(_disabled(QPushButton(tr("settings.wa_skip_extensions"))))
        btn_row_wa.addWidget(_disabled(QPushButton(tr("settings.wa_skip_directories"))))

        wa_content_layout.addLayout(btn_row_wa)
        wa_content_layout.addStretch()
        wa_content_layout.addWidget(QLabel(tr("label.workarounds_hint")))
        wa_scroll.setWidget(wa_content)
        wa_layout.addWidget(wa_scroll)
        # self._tabs.addTab(workarounds_tab, tr("settings.tab_workarounds"))

        # Tab Diagnose
        diagnose_tab = QWidget()
        diag_layout = QVBoxLayout(diagnose_tab)
        diag_scroll = QScrollArea()
        diag_scroll.setWidgetResizable(True)
        diag_scroll.setFrameShape(QFrame.Shape.NoFrame)
        diag_content = QWidget()
        diag_content_layout = QVBoxLayout(diag_content)
        logs_grp = QGroupBox(tr("settings.diag_logs_crashes"))
        logs_layout = QFormLayout(logs_grp)
        log_combo = QComboBox()
        log_combo.addItem(tr("label.log_level_info"))
        _disabled(log_combo)
        logs_layout.addRow(tr("settings.diag_log_level"), log_combo)
        crash_combo = QComboBox()
        crash_combo.addItem(tr("label.crash_dump_mini"))
        _disabled(crash_combo)
        logs_layout.addRow(tr("settings.diag_crash_dump"), crash_combo)
        crash_spin = QSpinBox()
        crash_spin.setValue(5)
        _disabled(crash_spin)
        logs_layout.addRow(tr("settings.diag_max_crash_dumps"), crash_spin)
        diag_content_layout.addWidget(logs_grp)
        loot_grp = QGroupBox(tr("settings.diag_integrated_loot"))
        loot_layout = QFormLayout(loot_grp)
        loot_combo = QComboBox()
        loot_combo.addItem(tr("label.log_level_info"))
        _disabled(loot_combo)
        loot_layout.addRow(tr("settings.diag_loot_log_level"), loot_combo)
        diag_content_layout.addWidget(loot_grp)
        diag_hint = QLabel(tr("settings.diag_hint"))
        diag_hint.setWordWrap(True)
        diag_content_layout.addWidget(diag_hint)
        diag_content_layout.addStretch()
        diag_scroll.setWidget(diag_content)
        diag_layout.addWidget(diag_scroll)
        # self._tabs.addTab(diagnose_tab, tr("settings.tab_diagnostics"))

        layout.addWidget(self._tabs)

        # Letzten Tab-Index wiederherstellen (MO2-Pattern)
        saved_tab = settings.value("SettingsDialog/tab_index", 0, type=int)
        self._tabs.setCurrentIndex(saved_tab)

        # Unten rechts: OK, Abbrechen
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton(tr("button.ok"))
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(tr("button.cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    # ── Plugin-Tab helpers ────────────────────────────────────────────

    def _on_plugin_selected(self, current: QTreeWidgetItem | None, _previous):
        """Update the detail panel when a plugin is selected in the tree."""
        if current is None:
            return
        short = current.data(0, Qt.ItemDataRole.UserRole)
        plugin = self._plugin_items.get(short) if short else None
        if plugin is None:
            # Root node or unknown — clear fields
            for field in (
                self._pl_author, self._pl_version, self._pl_game_name,
                self._pl_store, self._pl_path, self._pl_prefix,
            ):
                field.clear()
            self._pl_nexus.clear()
            return

        self._pl_author.setText(plugin.Author)
        self._pl_version.setText(plugin.Version)
        self._pl_game_name.setText(plugin.GameName)
        self._pl_store.setText(plugin.detectedStore() or "—")
        gd = plugin.gameDirectory()
        self._pl_path.setText(str(gd) if gd else "—")
        pp = plugin.protonPrefix()
        self._pl_prefix.setText(str(pp) if pp else "—")
        self._pl_cb_active.setChecked(plugin.isInstalled())

        nexus_id = getattr(plugin, "GameNexusName", "") or getattr(plugin, "GameShortName", "")
        if nexus_id:
            url = f"https://www.nexusmods.com/{nexus_id}"
            self._pl_nexus.setText(f'<a href="{url}" style="color:#4FC3F7;">{url}</a>')
        else:
            self._pl_nexus.clear()

    def _filter_plugins(self, text: str):
        """Show/hide plugin tree items based on filter text."""
        text_lower = text.lower()
        root = self._pl_tree.topLevelItem(0)
        if root is None:
            return
        for i in range(root.childCount()):
            child = root.child(i)
            if child is None:
                continue
            name = child.text(0).lower()
            child.setHidden(bool(text_lower) and text_lower not in name)

    def _open_plugin_folder(self):
        """Open the user plugin directory in the file manager."""
        path = ensure_user_plugin_dir()
        subprocess.Popen(["xdg-open", str(path)])

    # ── Mod-Liste-Tab helpers ────────────────────────────────────────

    def _update_separator_group(self) -> None:
        """Enable/disable separator sub-widgets based on Asc/Dsc checkboxes.

        MO2-Verhalten: Wenn weder Asc noch Dsc aktiviert sind, werden die
        Konflikte- und Symbol-Checkboxen innerhalb der Separator-Gruppe
        deaktiviert, da sie ohne einklappbare Separatoren keinen Sinn haben.
        """
        enabled = (self._cb_collapsible_asc.isChecked()
                   or self._cb_collapsible_dsc.isChecked())
        for w in (self._cb_conflicts_on_sep, self._cb_conflicts_from_sep,
                  self._cb_sym_conflicts, self._cb_sym_flags,
                  self._cb_sym_content, self._cb_sym_version):
            w.setEnabled(enabled)

    # ── Style-Tab helpers ─────────────────────────────────────────────

    @staticmethod
    def _settings() -> QSettings:
        path = str(Path.home() / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf")
        return QSettings(path, QSettings.Format.IniFormat)

    def _on_theme_changed(self, theme_name: str):
        """Apply selected theme live as preview."""
        qss = load_theme(theme_name)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(qss)

    def _reset_dialog_options(self):
        """Reset all 'don't show again' dialog choices."""
        from PySide6.QtWidgets import QMessageBox
        s = self._settings()
        s.remove("DialogChoices")
        QMessageBox.information(
            self, tr("dialog.settings_title"),
            tr("settings.dialog_reset_done"))

    def _open_styles_folder(self):
        """Open the styles directory in the file manager."""
        subprocess.Popen(["xdg-open", str(get_styles_dir())])

    def accept(self):
        """Save all settings, then close."""
        settings = self._settings()
        settings.setValue("style/theme", self._stil_combo.currentText())
        # Sprache speichern
        lang_idx = self._lang_combo.currentIndex()
        new_lang = self._lang_codes[lang_idx] if 0 <= lang_idx < len(self._lang_codes) else self._initial_lang
        settings.setValue("General/language", new_lang)
        # Tab Allgemein — QSettings
        settings.setValue("General/check_for_updates", self._cb_check_updates.isChecked())
        settings.setValue("Interface/center_dialogs", self._cb_center_dialogs.isChecked())
        settings.setValue("Interface/confirm_instance_change", self._cb_confirm_instance.isChecked())
        settings.setValue("Interface/show_menubar_on_alt", self._cb_alt_menubar.isChecked())
        settings.setValue("Interface/show_meta_info", self._cb_show_meta.isChecked())
        settings.setValue("Interface/compact_list", self._cb_compact_list.isChecked())
        settings.setValue("Interface/hide_downloads_after_install", self._cb_hide_downloads.isChecked())
        # Tab Mod Liste
        settings.setValue("ModList/remember_filters", self._cb_remember_filters.isChecked())
        settings.setValue("ModList/collapsible_asc", self._cb_collapsible_asc.isChecked())
        settings.setValue("ModList/collapsible_dsc", self._cb_collapsible_dsc.isChecked())
        settings.setValue("ModList/collapse_per_profile", self._cb_collapse_per_profile.isChecked())
        # Tab Mod Liste — 10 neue Settings
        settings.setValue("ModList/show_separator_colors", self._cb_separator_colors.isChecked())
        settings.setValue("ModList/show_external_mods", self._cb_external_mods.isChecked())
        settings.setValue("ModList/check_updates_after_install", self._cb_check_updates_install.isChecked())
        settings.setValue("ModList/auto_collapse_on_drag", self._cb_auto_collapse_drag.isChecked())
        settings.setValue("ModList/conflicts_on_separator", self._cb_conflicts_on_sep.isChecked())
        settings.setValue("ModList/conflicts_from_separator", self._cb_conflicts_from_sep.isChecked())
        settings.setValue("ModList/symbol_conflicts", self._cb_sym_conflicts.isChecked())
        settings.setValue("ModList/symbol_flags", self._cb_sym_flags.isChecked())
        settings.setValue("ModList/symbol_content", self._cb_sym_content.isChecked())
        settings.setValue("ModList/symbol_version", self._cb_sym_version.isChecked())
        # Tab-Index merken
        settings.setValue("SettingsDialog/tab_index", self._tabs.currentIndex())
        settings.sync()  # Sicherstellen dass Änderungen geschrieben werden

        # Pfade in Instanz-Config speichern
        if self._instance_manager is not None:
            cur = self._instance_manager.current_instance()
            if cur:
                idata = self._instance_manager.load_instance(cur)
                ipath = str(self._instance_manager.instances_path() / cur)

                # Absolute Pfade zurück in %INSTANCE_DIR% konvertieren
                def _unresolve(val: str) -> str:
                    if val.startswith(ipath):
                        return val.replace(ipath, "%INSTANCE_DIR%", 1)
                    return val

                idata["path_downloads_directory"] = _unresolve(self._le_downloads.text())
                idata["path_mods_directory"] = _unresolve(self._le_mods.text())
                idata["path_profiles_directory"] = _unresolve(self._le_profiles.text())
                idata["path_overwrite_directory"] = _unresolve(self._le_overwrite.text())
                idata["game_path"] = self._le_game_path.text()
                idata["local_inis"] = self._cb_local_inis.isChecked()
                idata["local_saves"] = self._cb_local_saves.isChecked()
                self._instance_manager.save_instance(cur, idata)

        super().accept()

        # Sprachwechsel: Bestätigung + Neustart
        if new_lang != self._initial_lang:
            Translator.instance().load(new_lang)
            from PySide6.QtWidgets import QMessageBox
            main_win = None
            for w in QApplication.topLevelWidgets():
                if hasattr(w, 'statusBar'):
                    main_win = w
                    break
            msg = QMessageBox(main_win)
            msg.setWindowTitle(tr("settings.language_changed_title"))
            msg.setText(tr("settings.language_changed_message"))
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.Yes)
            if msg.exec() == QMessageBox.StandardButton.Yes:
                import sys
                from PySide6.QtCore import QProcess
                QProcess.startDetached(sys.executable, sys.argv)
                QApplication.quit()
                return

    def reject(self):
        """Revert theme to previous selection and close."""
        if self._stil_combo.currentText() != self._previous_theme:
            qss = load_theme(self._previous_theme)
            app = QApplication.instance()
            if app:
                app.setStyleSheet(qss)
        # Tab-Index merken auch bei Abbrechen
        s = self._settings()
        s.setValue("SettingsDialog/tab_index", self._tabs.currentIndex())
        super().reject()

    # ── Nexus-Tab helpers ─────────────────────────────────────────────

    def _nx_log_add(self, text: str) -> None:
        """Add a line to the Nexus connection log (MO2 style)."""
        for line in text.split("\n"):
            if line.strip():
                self._nx_log.addItem(line.strip())
        self._nx_log.scrollToBottom()

    def _nx_update_button_states(self) -> None:
        """Update Nexus button enabled states based on connection status."""
        has_key = bool(self._nexus_api.has_api_key())
        sso_active = bool(self._sso_login and self._sso_login.is_active())

        if sso_active:
            # SSO läuft: Connect=Abbrechen, Rest disabled
            self._btn_connect.setEnabled(True)
            self._btn_api_key.setEnabled(False)
            self._btn_disconnect.setEnabled(False)
        elif has_key and self._nx_uid.text():
            # Verbunden (Key + validiert): nur Disconnect
            self._btn_connect.setEnabled(False)
            self._btn_api_key.setEnabled(False)
            self._btn_disconnect.setEnabled(True)
        elif has_key:
            # Key gesetzt aber noch nicht validiert oder Fehler
            self._btn_connect.setEnabled(True)
            self._btn_api_key.setEnabled(True)
            self._btn_disconnect.setEnabled(True)
        else:
            # Nicht verbunden: Connect + API-Key, kein Disconnect
            self._btn_connect.setEnabled(True)
            self._btn_api_key.setEnabled(True)
            self._btn_disconnect.setEnabled(False)

        # Tooltips zurücksetzen (weg von "Noch nicht verfügbar")
        self._btn_connect.setToolTip("")
        self._btn_api_key.setToolTip("")
        self._btn_disconnect.setToolTip("")

    def _nx_connect_sso(self) -> None:
        """Start the SSO login flow via browser (MO2 style)."""
        # Cancel existing SSO if active
        if self._sso_login and self._sso_login.is_active():
            self._sso_login.cancel()
            self._btn_connect.setText(tr("button.connect_nexus"))
            self._nx_update_button_states()
            return

        self._nx_log.clear()
        self._sso_login = NexusSSOLogin(self)
        self._sso_login.state_changed.connect(self._nx_on_sso_state)
        self._sso_login.key_changed.connect(self._nx_on_sso_key)
        self._btn_connect.setText(tr("button.cancel"))
        self._sso_login.start()
        self._nx_update_button_states()

    def _nx_on_sso_state(self, state: int, detail: str) -> None:
        """Handle SSO state changes — show progress in log."""
        text = NexusSSOLogin.state_to_string(state, detail)
        self._nx_log_add(text)

        if state in (NexusSSOLogin.State.FINISHED,
                     NexusSSOLogin.State.TIMEOUT,
                     NexusSSOLogin.State.CLOSED_BY_REMOTE,
                     NexusSSOLogin.State.CANCELLED,
                     NexusSSOLogin.State.ERROR):
            self._btn_connect.setText(tr("button.connect_nexus"))
            self._nx_update_button_states()

    def _nx_on_sso_key(self, api_key: str) -> None:
        """Handle API key received from SSO."""
        self._nx_log_add(tr("settings.nexus_key_received"))
        self._nexus_api.set_api_key(api_key)
        settings = self._settings()
        settings.setValue("nexus/api_key", api_key)
        self._nx_log_add(tr("settings.nexus_key_validating"))
        self._nexus_api.validate_key()
        self._nx_update_button_states()

    def _nx_enter_api_key(self) -> None:
        """Prompt the user to enter their Nexus API key manually."""
        from anvil.core.ui_helpers import get_text_input
        key, ok = get_text_input(
            self, tr("settings.nexus_enter_key_title"),
            tr("settings.nexus_enter_key_prompt"),
        )
        if ok and key.strip():
            self._nx_log.clear()
            self._nx_log_add(tr("settings.nexus_key_manual"))
            self._nexus_api.set_api_key(key.strip())
            settings = self._settings()
            settings.setValue("nexus/api_key", key.strip())
            self._nx_log_add(tr("settings.nexus_key_validating"))
            self._nx_status_label.setStyleSheet("")
            self._nexus_api.validate_key()
            self._nx_update_button_states()

    def _nx_disconnect(self) -> None:
        """Clear the API key and reset all Nexus fields."""
        # Cancel active SSO
        if self._sso_login and self._sso_login.is_active():
            self._sso_login.cancel()
            self._btn_connect.setText(tr("button.connect_nexus"))

        settings = self._settings()
        settings.remove("nexus/api_key")
        self._nexus_api.set_api_key("")
        self._nx_uid.clear()
        self._nx_name.clear()
        self._nx_account.clear()
        self._nx_daily.clear()
        self._nx_hourly.clear()
        self._nx_log.clear()
        self._nx_log_add(tr("status.disconnected"))
        self._nx_status_label.setText(tr("status.disconnected"))
        self._nx_status_label.setStyleSheet("")
        self._nx_update_button_states()

    def _nx_on_validated(self, user_info: dict) -> None:
        """Handle successful API key validation."""
        self._nx_uid.setText(str(user_info.get("user_id", "")))
        self._nx_name.setText(user_info.get("name", ""))
        is_premium = user_info.get("is_premium", False)
        is_supporter = user_info.get("is_supporter", False)
        if is_premium:
            account_type = "Premium"
        elif is_supporter:
            account_type = "Supporter"
        else:
            account_type = "Standard"
        self._nx_account.setText(account_type)
        self._nx_log_add(tr("settings.nexus_account_received"))
        self._nx_log_add(tr("settings.nexus_connected_success"))
        self._nx_status_label.setText(tr("status.connected"))
        self._nx_status_label.setStyleSheet("color: #4CAF50;")
        self._nx_update_button_states()

    def _nx_on_error(self, tag: str, message: str) -> None:
        """Handle API request error."""
        if tag == "validate":
            self._nx_log_add(tr("settings.nexus_error", message=message))
            self._nx_status_label.setText(tr("settings.nexus_error", message=message))
            self._nx_status_label.setStyleSheet("color: #F44336;")
            self._nx_update_button_states()

    def _nx_on_rate_limit(self, daily: int, hourly: int) -> None:
        """Update rate limit display."""
        if daily >= 0:
            self._nx_daily.setText(f"{daily}")
        if hourly >= 0:
            self._nx_hourly.setText(f"{hourly}")
        # Notify parent (MainWindow) via signal if available
        parent = self.parent()
        if parent and hasattr(parent, "_update_api_status"):
            parent._update_api_status(daily, hourly)

    def _nx_register_nxm_handler(self) -> None:
        """Register Anvil Organizer as nxm:// URL handler on Linux."""
        from anvil.core.nxm_handler import register_nxm_handler
        success = register_nxm_handler()
        if success:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, tr("settings.nxm_handler_title"),
                tr("settings.nxm_handler_success"),
            )
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, tr("settings.nxm_handler_title"),
                tr("settings.nxm_handler_failed"),
            )
