"""Einstellungen — QDialog."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from anvil.core.subprocess_env import host_open_path

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
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QFormLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QSpinBox,
    QPlainTextEdit,
    QToolButton,
)
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter
from PySide6.QtCore import Qt, QSettings, QTimer, QSize

from anvil.plugins.plugin_loader import PluginLoader, ensure_user_plugin_dir
from anvil.styles.dark_theme import (
    list_themes, get_styles_dir, default_theme,
    apply_theme, default_palette, load_overrides, save_overrides, COLOR_ROLES,
    is_modern_theme, style_prefs, MODERN_THEME_DARK, MODERN_THEME_LIGHT,
    MODERN_ACCENTS, theme_color,
)
from anvil.core.base_dir import anvil_base_paths
from anvil.core.instance_paths import resolve_instance_paths
from anvil.core.nexus_api import NexusAPI
from anvil.core.nexus_sso import NexusSSOLogin
from anvil.core.translator import Translator, tr

def _design_preview_pixmap(dark: bool) -> QPixmap:
    """Skeleton-Miniatur für die Design-Karten (Vorlage-Optik)."""
    from PySide6.QtGui import QPainterPath
    w, h = 222, 67
    pix = QPixmap(w, h)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    bg, bar = ("#16181d", "#2a2e35") if dark else ("#f2f3f5", "#d9dce1")
    path = QPainterPath()
    path.addRoundedRect(0.5, 0.5, w - 1, h - 1, 6, 6)
    p.fillPath(path, QColor(bg))
    p.setPen(QColor(bar))
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(bar))
    p.drawRoundedRect(10, 13, int(w * 0.6), 7, 3, 3)
    p.drawRoundedRect(10, 28, int(w * 0.4), 7, 3, 3)
    p.end()
    return pix


class SettingsDialog(QDialog):
    def __init__(self, parent=None, plugin_loader: PluginLoader | None = None,
                 instance_manager=None, on_clear_modindex=None,
                 diagnostics_provider=None, on_storage_migration=None,
                 on_locate_storage=None):
        super().__init__(parent)
        self._plugin_loader = plugin_loader
        self._instance_manager = instance_manager
        self._on_clear_modindex = on_clear_modindex
        self._diagnostics_provider = diagnostics_provider
        self._on_storage_migration = on_storage_migration
        self._on_locate_storage = on_locate_storage
        self.setWindowTitle(tr("dialog.settings_title"))
        # Modern: feste Vorlage-Größe, rahmenlos mit eigener Titelleiste,
        # Radius 12 + 1px-Rahmen (Fensterecken transparent)
        self._modern = bool(theme_color("panel2", ""))
        self._backdrop = None
        if self._modern:
            self.setObjectName("settingsDlg")
            self.setFixedSize(976, 726)
            self.setWindowFlags(
                Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        else:
            self.setMinimumSize(960, 600)
            self.resize(960, 600)

        if self._modern:
            outer = QVBoxLayout(self)
            outer.setSpacing(0)
            outer.setContentsMargins(0, 0, 0, 0)
            frame = QWidget()
            frame.setObjectName("modalFrame")
            frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            outer.addWidget(frame)
            layout = QVBoxLayout(frame)
        else:
            layout = QVBoxLayout(self)
        if self._modern:
            layout.setSpacing(0)
            layout.setContentsMargins(1, 1, 1, 1)
            title_bar = QWidget()
            title_bar.setObjectName("instTitleBar")
            title_bar.setAttribute(
                Qt.WidgetAttribute.WA_StyledBackground, True)
            title_bar.setFixedHeight(52)
            tb = QHBoxLayout(title_bar)
            tb.setContentsMargins(16, 0, 16, 0)
            t_lbl = QLabel(tr("dialog.settings_title"))
            t_lbl.setObjectName("instTitleLabel")
            tb.addWidget(t_lbl)
            tb.addStretch()
            x_btn = QPushButton("✕")
            x_btn.setObjectName("instCloseBtn")
            x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            x_btn.clicked.connect(self.reject)
            tb.addWidget(x_btn)
            layout.addWidget(title_bar)
        else:
            layout.setSpacing(10)
            layout.setContentsMargins(12, 12, 12, 12)

        settings = self._settings()
        self._tabs = QTabWidget()
        if self._modern:
            self._tabs.setObjectName("settingsTabs")

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
        dl_layout.addWidget(self._setting_row(self._cb_show_meta))
        self._cb_compact_list = QCheckBox(tr("settings.compact_list"))
        self._cb_compact_list.setChecked(
            settings.value("Interface/compact_list", False, type=bool))
        dl_layout.addWidget(self._setting_row(self._cb_compact_list))
        self._cb_hide_downloads = QCheckBox(tr("settings.hide_downloads_after_install"))
        self._cb_hide_downloads.setChecked(
            settings.value("Interface/hide_downloads_after_install", False, type=bool))
        dl_layout.addWidget(self._setting_row(self._cb_hide_downloads))

        scroll_layout.addWidget(dl_grp)

        # Gruppe Updates
        up_grp = QGroupBox(tr("settings.updates"))
        up_layout = QVBoxLayout(up_grp)
        self._cb_check_updates = QCheckBox(tr("settings.check_for_updates"))
        self._cb_check_updates.setChecked(
            settings.value("General/check_for_updates", True, type=bool))
        up_layout.addWidget(self._setting_row(self._cb_check_updates))
        scroll_layout.addWidget(up_grp)

        # Gruppe Profil-Standardeinstellungen
        prof_grp = QGroupBox(tr("settings.profile_defaults"))
        prof_layout = QVBoxLayout(prof_grp)
        self._cb_local_inis = QCheckBox(tr("settings.local_inis"))
        self._cb_local_inis.setChecked(
            str(self._idata.get("local_inis", "true")).lower() in ("true", "1"))
        prof_layout.addWidget(self._setting_row(self._cb_local_inis))
        self._cb_local_saves = QCheckBox(tr("settings.local_saves"))
        self._cb_local_saves.setChecked(
            str(self._idata.get("local_saves", "false")).lower() in ("true", "1"))
        prof_layout.addWidget(self._setting_row(self._cb_local_saves))
        prof_layout.addWidget(self._setting_row(_disabled(QCheckBox(tr("settings.auto_archive_invalidation")))))

        self._cb_use_overlay = QCheckBox(tr("settings.use_overlay"))
        self._cb_use_overlay.setToolTip(tr("settings.use_overlay_hint"))
        self._cb_use_overlay.setChecked(
            str(self._idata.get("use_overlay", "false")).lower() in ("true", "1"))
        prof_layout.addWidget(self._setting_row(self._cb_use_overlay))

        self._lbl_overlay_problems = QLabel("")
        self._lbl_overlay_problems.setWordWrap(True)
        self._lbl_overlay_problems.setVisible(False)
        prof_layout.addWidget(self._lbl_overlay_problems)
        self._check_overlay_requirements()

        scroll_layout.addWidget(prof_grp)

        # Gruppe Sonstiges
        misc_grp = QGroupBox(tr("settings.misc"))
        misc_layout = QVBoxLayout(misc_grp)
        self._cb_center_dialogs = QCheckBox(tr("settings.center_dialogs"))
        self._cb_center_dialogs.setChecked(
            settings.value("Interface/center_dialogs", False, type=bool))
        misc_layout.addWidget(self._setting_row(self._cb_center_dialogs))
        self._cb_confirm_instance = QCheckBox(tr("settings.confirm_instance_change"))
        self._cb_confirm_instance.setChecked(
            settings.value("Interface/confirm_instance_change", True, type=bool))
        misc_layout.addWidget(self._setting_row(self._cb_confirm_instance))
        self._cb_alt_menubar = QCheckBox(tr("settings.alt_shows_menubar"))
        self._cb_alt_menubar.setChecked(
            settings.value("Interface/show_menubar_on_alt", True, type=bool))
        misc_layout.addWidget(self._setting_row(self._cb_alt_menubar))
        cb_preview = QCheckBox(tr("settings.open_preview_dblclick"))
        cb_preview.setChecked(True)
        _disabled(cb_preview)
        misc_layout.addWidget(self._setting_row(cb_preview))
        self._cb_shortcut_launch_game = QCheckBox(tr("settings.shortcut_launch_game"))
        self._cb_shortcut_launch_game.setChecked(
            settings.value("Interface/shortcut_launch_game", True, type=bool))
        misc_layout.addWidget(self._setting_row(self._cb_shortcut_launch_game))
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

        # Tab Style — Inhalt in Scroll-Area (wie Allgemein-Tab), sonst wird
        # der Inhalt bei kleiner Dialoghöhe zusammengequetscht
        style_tab = QWidget()
        style_tab_layout = QVBoxLayout(style_tab)
        style_scroll = QScrollArea()
        style_scroll.setWidgetResizable(True)
        style_scroll.setFrameShape(QFrame.Shape.NoFrame)
        style_content = QWidget()
        style_layout = QVBoxLayout(style_content)

        saved_theme = settings.value("style/theme", default_theme())
        saved_accent, saved_density = style_prefs(settings)
        self._modern_active = is_modern_theme(saved_theme)
        self._previous_theme = saved_theme
        self._previous_accent = saved_accent
        self._previous_density = saved_density
        self._selected_accent = saved_accent
        self._selected_density = saved_density
        # Gewähltes Design als eigene Variable — NIE aus den Button-Zuständen
        # ableiten: checkbare Buttons togglen sich beim Klick selbst, bevor
        # der Handler läuft, und verfälschen jede Vorher/Nachher-Prüfung.
        self._selected_design = (
            saved_theme if self._modern_active else MODERN_THEME_DARK)

        # ── Design (Anvil Dunkel/Hell, Akzentfarbe, Zeilendichte) ────
        design_grp = QGroupBox(tr("settings.design"))
        design_layout = QVBoxLayout(design_grp)

        variant_row = QHBoxLayout()
        variant_row.setSpacing(10)
        if self._modern:
            # Vorlage: Preview-Karten (Skeleton-Miniatur, Label darunter)
            self._btn_design_dark = QToolButton()
            self._btn_design_dark.setText(tr("settings.design_dark"))
            self._btn_design_light = QToolButton()
            self._btn_design_light.setText(tr("settings.design_light"))
            for btn, dark in ((self._btn_design_dark, True),
                              (self._btn_design_light, False)):
                btn.setObjectName("designCard")
                btn.setToolButtonStyle(
                    Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                btn.setIcon(QIcon(_design_preview_pixmap(dark)))
                btn.setIconSize(QSize(222, 67))
                btn.setFixedSize(252, 126)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._btn_design_dark = QPushButton(tr("settings.design_dark"))
            self._btn_design_light = QPushButton(tr("settings.design_light"))
        for btn, name in ((self._btn_design_dark, MODERN_THEME_DARK),
                          (self._btn_design_light, MODERN_THEME_LIGHT)):
            btn.setCheckable(True)
            if not self._modern:
                btn.setMinimumSize(120, 36)
            btn.clicked.connect(
                lambda checked=False, n=name: self._on_design_clicked(n))
            variant_row.addWidget(btn)
        variant_row.addStretch()
        design_layout.addLayout(variant_row)

        accent_row = QHBoxLayout()
        accent_row.setSpacing(10)
        if self._modern:
            hdr = QLabel(tr("settings.accent_color").upper())
            hdr.setObjectName("sectionMiniHeader")
            design_layout.addSpacing(6)
            design_layout.addWidget(hdr)
        else:
            accent_row.addWidget(QLabel(tr("settings.accent_color")))
        self._accent_buttons: dict = {}
        accent_labels = {
            "teal": tr("settings.accent_teal"),
            "violet": tr("settings.accent_violet"),
            "blue": tr("settings.accent_blue"),
        }
        for key in MODERN_ACCENTS:
            label_txt = accent_labels.get(key, key)
            btn = QPushButton(
                " " + label_txt if self._modern else label_txt)
            btn.setCheckable(True)
            if self._modern:
                # Vorlage: Farbkreis 22px + Name (Icon malt _update_accent_icons)
                btn.setObjectName("accentCard")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setIconSize(QSize(27, 27))
            btn.clicked.connect(
                lambda checked=False, k=key: self._on_accent_clicked(k))
            self._accent_buttons[key] = btn
            accent_row.addWidget(btn)
        accent_row.addStretch()
        design_layout.addLayout(accent_row)

        density_row = QHBoxLayout()
        if self._modern:
            hdr = QLabel(tr("settings.row_density").upper())
            hdr.setObjectName("sectionMiniHeader")
            design_layout.addSpacing(6)
            design_layout.addWidget(hdr)
        else:
            density_row.addWidget(QLabel(tr("settings.row_density")))
        self._density_buttons: dict = {}
        density_labels = {
            "compact": tr("settings.density_compact"),
            "comfy": tr("settings.density_comfy"),
        }
        seg_layout = density_row
        if self._modern:
            # Vorlage: Segment-Schalter in panel2-Container
            seg = QWidget()
            seg.setObjectName("densSegment")
            seg.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            seg_layout = QHBoxLayout(seg)
            seg_layout.setContentsMargins(3, 3, 3, 3)
            seg_layout.setSpacing(4)
            density_row.addWidget(seg)
        for key, label in density_labels.items():
            btn = QPushButton(label)
            btn.setCheckable(True)
            if self._modern:
                btn.setObjectName("densBtn")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda checked=False, k=key: self._on_density_clicked(k))
            self._density_buttons[key] = btn
            seg_layout.addWidget(btn)
        density_row.addStretch()
        design_layout.addLayout(density_row)
        style_layout.addWidget(design_grp)

        if self._modern_active:
            self._btn_design_dark.setChecked(saved_theme == MODERN_THEME_DARK)
            self._btn_design_light.setChecked(saved_theme == MODERN_THEME_LIGHT)
        for k, btn in self._accent_buttons.items():
            btn.setChecked(k == saved_accent)
        for k, btn in self._density_buttons.items():
            btn.setChecked(k == saved_density)

        # ── Klassische Themes (QSS-Dateien) ──────────────────────────
        stil_grp = QGroupBox(tr("settings.classic_themes"))
        stil_layout = QHBoxLayout(stil_grp)
        self._stil_combo = QComboBox()
        # Available themes from anvil/styles/*.qss
        themes = list_themes()
        self._stil_combo.addItems(themes)
        # Gespeichertes klassisches Theme vorauswählen (modern steht nicht im Combo)
        idx = self._stil_combo.findText(saved_theme)
        if idx >= 0:
            self._stil_combo.setCurrentIndex(idx)
        self._stil_combo.currentTextChanged.connect(self._on_theme_changed)
        stil_layout.addWidget(self._stil_combo)
        erkunden_btn = QPushButton(tr("settings.explore"))
        erkunden_btn.clicked.connect(self._open_styles_folder)
        stil_layout.addWidget(erkunden_btn)
        style_layout.addWidget(stil_grp)

        # ── Theme-Farben (anpassbare Rollenfarben, nur klassische Themes) ──
        self._color_overrides = load_overrides(
            self._settings(), self._stil_combo.currentText())
        self._color_swatches: dict = {}
        self._preview_dirty = False
        self._theme_colors_grp = QGroupBox(tr("settings.theme_colors"))
        self._theme_colors_layout = QVBoxLayout(self._theme_colors_grp)
        self._rebuild_color_rows()
        style_layout.addWidget(self._theme_colors_grp)

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
        reset_btn = QPushButton(tr("settings.reset_colors"))
        reset_btn.clicked.connect(lambda checked=False: self._on_reset_colors())
        reset_row.addWidget(reset_btn)
        reset_row.addStretch()
        style_layout.addLayout(reset_row)
        style_layout.addStretch()
        style_scroll.setWidget(style_content)
        style_tab_layout.addWidget(style_scroll)
        self._update_style_states()
        self._tabs.addTab(style_tab, tr("settings.tab_style"))

        # Tab Mod Liste
        modliste_tab = QWidget()
        ml_layout = QVBoxLayout(modliste_tab)
        self._cb_separator_colors = QCheckBox(tr("settings.show_separator_colors"))
        self._cb_separator_colors.setChecked(
            settings.value("ModList/show_separator_colors", True, type=bool))
        ml_layout.addWidget(self._setting_row(self._cb_separator_colors))
        self._cb_external_mods = QCheckBox(tr("settings.show_external_mods"))
        self._cb_external_mods.setChecked(
            settings.value("ModList/show_external_mods", True, type=bool))
        ml_layout.addWidget(self._setting_row(self._cb_external_mods))
        self._cb_remember_filters = QCheckBox(tr("settings.remember_filters"))
        self._cb_remember_filters.setChecked(
            settings.value("ModList/remember_filters", False, type=bool))
        ml_layout.addWidget(self._setting_row(self._cb_remember_filters))
        self._cb_check_updates_install = QCheckBox(tr("settings.check_updates_after_install"))
        self._cb_check_updates_install.setChecked(
            settings.value("ModList/check_updates_after_install", True, type=bool))
        ml_layout.addWidget(self._setting_row(self._cb_check_updates_install))
        self._cb_auto_collapse_drag = QCheckBox(tr("settings.auto_collapse_on_drag"))
        self._cb_auto_collapse_drag.setChecked(
            settings.value("ModList/auto_collapse_on_drag", False, type=bool))
        ml_layout.addWidget(self._setting_row(self._cb_auto_collapse_drag))
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
        self._cb_conflict_highlight = QCheckBox(tr("settings.conflict_highlight_on_select"))
        self._cb_conflict_highlight.setChecked(
            settings.value("ModList/conflict_highlight_on_select", True, type=bool))
        conflict_row.addWidget(self._cb_conflict_highlight)
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
        # Signal-Verbindungen fuer Gruppen-Deaktivierung
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
        _anvil_base_dir = str(anvil_base_paths().base)
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
            resolved = resolve_instance_paths(ipath, self._idata)
            _downloads = str(resolved.downloads)
            _mods = str(resolved.mods)
            _profiles = str(resolved.profiles)
            _overwrite = str(resolved.overwrite)
            _caches = str(resolved.cache)
            _game_path = self._idata.get("game_path", "")

        pf_form = QFormLayout()
        add_path_row(
            pf_form,
            tr("settings.path_anvil_base_dir"),
            _anvil_base_dir,
            False,
            readonly=True,
        )
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

        _storage_btn = QPushButton(tr("storage.manage"))
        _storage_btn.setObjectName("setOkBtn")
        _storage_btn.setToolTip(tr("storage.manage_tooltip"))
        _storage_callback = self._on_storage_migration
        if _storage_callback is not None:
            _storage_btn.clicked.connect(
                lambda checked=False, callback=_storage_callback: callback()
            )
        else:
            _storage_btn.setEnabled(False)
        _storage_row = QHBoxLayout()
        _storage_row.addWidget(_storage_btn)
        _locate_btn = QPushButton(tr("storage.locate"))
        _locate_btn.setToolTip(tr("storage.locate_tooltip"))
        _locate_callback = self._on_locate_storage
        if _locate_callback is not None:
            _locate_btn.clicked.connect(
                lambda checked=False, callback=_locate_callback: callback()
            )
        else:
            _locate_btn.setEnabled(False)
        _storage_row.addWidget(_locate_btn)
        _storage_row.addStretch()
        pf_content_layout.addSpacing(12)
        pf_content_layout.addLayout(_storage_row)

        # Mod-Index Cache Button
        _clear_idx_btn = QPushButton(tr("settings.clear_modindex_cache"))
        _clear_idx_btn.setToolTip(tr("settings.clear_modindex_tooltip"))
        if self._on_clear_modindex is not None:
            _clear_idx_btn.clicked.connect(lambda checked=False: self._on_clear_modindex())
        else:
            _clear_idx_btn.setEnabled(False)
        _clear_row = QHBoxLayout()
        _clear_row.addWidget(_clear_idx_btn)
        _clear_row.addStretch()
        pf_content_layout.addSpacing(8)
        pf_content_layout.addLayout(_clear_row)

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

        # ── Nexus-Verbindung (Log + 3 Buttons) ───────────────────
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
        # Tracking — aktiv
        self._cb_nexus_tracking = QCheckBox(tr("settings.nexus_tracking"))
        self._cb_nexus_tracking.setChecked(
            self._settings().value("Nexus/tracking_enabled", True, type=bool))
        opt_left.addWidget(self._cb_nexus_tracking)

        # Category Mapping — aktiv
        self._cb_nexus_catmap = QCheckBox(tr("settings.nexus_category_mapping"))
        self._cb_nexus_catmap.setChecked(
            self._settings().value("Nexus/category_mapping_enabled", True, type=bool))
        opt_left.addWidget(self._cb_nexus_catmap)

        # API Counter ausblenden — aktiv
        self._cb_nexus_hide_api = QCheckBox(tr("settings.nexus_hide_api_counter"))
        self._cb_nexus_hide_api.setChecked(
            self._settings().value("Nexus/hide_api_counter", False, type=bool))
        opt_left.addWidget(self._cb_nexus_hide_api)
        opt_layout.addLayout(opt_left)
        opt_right = QVBoxLayout()
        self._btn_nxm_link = QPushButton(tr("settings.nexus_link_nxm"))
        self._btn_nxm_link.clicked.connect(self._nx_register_nxm_handler)
        opt_right.addWidget(self._btn_nxm_link)
        opt_right.addWidget(_disabled(QPushButton(tr("settings.nexus_clear_cache"))))
        opt_right.addStretch()
        opt_layout.addLayout(opt_right)
        nx_content_layout.addWidget(opt_grp)

        # ── Server ───────────────────────────────────────────────────
        server_grp = QGroupBox(tr("settings.nexus_server"))
        server_layout = QHBoxLayout(server_grp)
        # Links: bekannte Server (Info, aus Cache — wird bei Downloads aktualisiert)
        known_lbl = QLabel(tr("label.known_servers"))
        server_left = QVBoxLayout()
        server_left.addWidget(known_lbl)
        self._nexus_known_list = QListWidget()
        self._nexus_known_list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection)
        server_left.addWidget(self._nexus_known_list)
        server_layout.addLayout(server_left)
        # Rechts: bevorzugte Region (Single-Select) für Free-Downloads
        pref_lbl = QLabel(tr("label.preferred_servers"))
        server_right = QVBoxLayout()
        server_right.addWidget(pref_lbl)
        self._nexus_pref_list = QListWidget()
        server_right.addWidget(self._nexus_pref_list)
        server_layout.addLayout(server_right)
        nx_content_layout.addWidget(server_grp)
        self._nx_populate_servers()

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
        saved_key = self.load_api_key()
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
        self._pl_tree.setMinimumWidth(400)
        self._pl_tree.header().setStretchLastSection(False)
        self._pl_tree.header().setSectionResizeMode(0, self._pl_tree.header().ResizeMode.Stretch)
        self._pl_tree.header().setSectionResizeMode(1, self._pl_tree.header().ResizeMode.ResizeToContents)

        _italic_font = QFont()
        _italic_font.setItalic(True)

        # ── Installer Kategorie ──
        installer_root = QTreeWidgetItem(self._pl_tree, [tr("settings.plugins_installer"), ""])
        installer_root.setExpanded(True)
        for name, ver, enabled in [
            ("FOMOD Installer", "1.0", True),
            ("BAIN Installer", "—", False),
            ("Simple Installer", "1.0", True),
        ]:
            item = QTreeWidgetItem(installer_root, [name, ver])
            item.setData(0, Qt.ItemDataRole.UserRole, f"__installer__{name}")
            if not enabled:
                item.setFont(0, _italic_font)
                item.setFont(1, _italic_font)

        # ── Diagnose Kategorie ──
        diagnose_root = QTreeWidgetItem(self._pl_tree, [tr("settings.plugins_diagnose"), ""])
        diagnose_root.setExpanded(True)
        for name, ver, enabled in [
            ("Load Order Checker", "1.0", True),
            ("Script Extender Checker", "1.0", True),
        ]:
            item = QTreeWidgetItem(diagnose_root, [name, ver])
            item.setData(0, Qt.ItemDataRole.UserRole, f"__diagnose__{name}")

        # ── Tool Kategorie ──
        tool_root = QTreeWidgetItem(self._pl_tree, [tr("settings.plugins_tool"), ""])
        tool_root.setExpanded(True)
        for name, ver, enabled in [
            ("BA2/BSA Packer", "1.0", True),
        ]:
            item = QTreeWidgetItem(tool_root, [name, ver])
            item.setData(0, Qt.ItemDataRole.UserRole, f"__tool__{name}")

        # ── Game Kategorie ──
        games_root = QTreeWidgetItem(self._pl_tree, [tr("settings.plugins_games"), ""])
        games_root.setExpanded(True)

        self._plugin_items: dict[str, object] = {}  # short_name → BaseGame

        if self._plugin_loader:
            for plugin in self._plugin_loader.all_plugins():
                beta = " [Beta]" if not getattr(plugin, "Tested", True) else ""
                item = QTreeWidgetItem(games_root, [f"{plugin.Name}{beta}", plugin.Version])
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

        # Tab Diagnose (#23)
        diagnose_tab = QWidget()
        diag_layout = QVBoxLayout(diagnose_tab)
        diag_scroll = QScrollArea()
        diag_scroll.setWidgetResizable(True)
        diag_scroll.setFrameShape(QFrame.Shape.NoFrame)
        diag_content = QWidget()
        diag_content_layout = QVBoxLayout(diag_content)

        # Sektion Systeminfo (read-only)
        sys_grp = QGroupBox(tr("settings.diag_system_info"))
        sys_form = QFormLayout(sys_grp)
        self._diag_sys: dict = {}
        for key, label in (
            ("app_version", tr("settings.diag_app_version")),
            ("os", "OS"),
            ("distro", tr("settings.diag_distro")),
            ("kernel", tr("settings.diag_kernel")),
            ("python", "Python"),
            ("qt", "Qt"),
            ("run_mode", tr("settings.diag_run_mode")),
            ("desktop", tr("settings.diag_desktop")),
            ("session", tr("settings.diag_session")),
            ("memory", tr("settings.diag_memory")),
        ):
            le = QLineEdit()
            le.setReadOnly(True)
            le.setPlaceholderText("—")
            self._diag_sys[key] = le
            sys_form.addRow(label + ":", le)
        diag_content_layout.addWidget(sys_grp)

        # Sektion Pfad-Prüfung
        path_grp = QGroupBox(tr("settings.diag_path_checks"))
        path_layout = QVBoxLayout(path_grp)
        self._diag_path_list = QListWidget()
        self._diag_path_list.setMinimumHeight(120)
        path_layout.addWidget(self._diag_path_list)
        path_btn_row = QHBoxLayout()
        diag_open_path_btn = QPushButton(tr("settings.diag_open_path"))
        diag_open_path_btn.clicked.connect(lambda checked=False: self._diag_open_selected_path())
        path_btn_row.addWidget(diag_open_path_btn)
        path_btn_row.addStretch()
        path_layout.addLayout(path_btn_row)
        diag_content_layout.addWidget(path_grp)

        # Sektion Deploy-Status
        deploy_grp = QGroupBox(tr("settings.diag_deploy_status"))
        deploy_layout = QVBoxLayout(deploy_grp)
        self._diag_deploy_label = QLabel("—")
        self._diag_deploy_label.setWordWrap(True)
        deploy_layout.addWidget(self._diag_deploy_label)
        diag_content_layout.addWidget(deploy_grp)

        # Sektion Erkannte Probleme
        prob_grp = QGroupBox(tr("settings.diag_problems"))
        prob_layout = QVBoxLayout(prob_grp)
        self._diag_problem_list = QListWidget()
        self._diag_problem_list.setMinimumHeight(100)
        prob_layout.addWidget(self._diag_problem_list)
        diag_content_layout.addWidget(prob_grp)

        # Sektion Mod-Konflikte (Scan auf Knopfdruck)
        conf_grp = QGroupBox(tr("settings.diag_conflicts"))
        conf_layout = QVBoxLayout(conf_grp)
        self._diag_conflict_list = QListWidget()
        self._diag_conflict_list.setMinimumHeight(100)
        conf_layout.addWidget(self._diag_conflict_list)
        conf_btn_row = QHBoxLayout()
        diag_scan_btn = QPushButton(tr("settings.diag_scan_conflicts"))
        diag_scan_btn.clicked.connect(lambda checked=False: self._diag_scan_conflicts())
        conf_btn_row.addWidget(diag_scan_btn)
        conf_btn_row.addStretch()
        conf_layout.addLayout(conf_btn_row)
        diag_content_layout.addWidget(conf_grp)

        # Sektion Log-Viewer
        log_grp = QGroupBox(tr("settings.diag_logs"))
        log_layout = QVBoxLayout(log_grp)
        # State vor dem Signal-connect setzen (Robustheit gegen Reihenfolge)
        self._diag_log_sources: list = []
        self._diag_log_lines: list = []
        log_top_row = QHBoxLayout()
        self._diag_log_combo = QComboBox()
        self._diag_log_combo.currentIndexChanged.connect(lambda _i: self._diag_load_log())
        log_top_row.addWidget(self._diag_log_combo, 1)
        self._diag_log_search = QLineEdit()
        self._diag_log_search.setPlaceholderText(tr("settings.diag_search"))
        self._diag_log_search.textChanged.connect(lambda _t: self._diag_filter_log())
        log_top_row.addWidget(self._diag_log_search, 1)
        log_layout.addLayout(log_top_row)
        self._diag_log_view = QPlainTextEdit()
        self._diag_log_view.setReadOnly(True)
        self._diag_log_view.setMinimumHeight(160)
        log_layout.addWidget(self._diag_log_view)
        log_btn_row = QHBoxLayout()
        diag_log_refresh = QPushButton(tr("settings.diag_refresh"))
        diag_log_refresh.clicked.connect(lambda checked=False: self._diag_load_log())
        diag_log_open = QPushButton(tr("settings.diag_open_file"))
        diag_log_open.clicked.connect(lambda checked=False: self._diag_open_log())
        log_btn_row.addWidget(diag_log_refresh)
        log_btn_row.addWidget(diag_log_open)
        log_btn_row.addStretch()
        log_layout.addLayout(log_btn_row)
        diag_content_layout.addWidget(log_grp)

        # Export-Leiste
        export_row = QHBoxLayout()
        diag_refresh_all = QPushButton(tr("settings.diag_refresh"))
        diag_refresh_all.clicked.connect(lambda checked=False: self._diag_refresh())
        diag_copy_btn = QPushButton(tr("settings.diag_copy_report"))
        diag_copy_btn.clicked.connect(lambda checked=False: self._diag_copy_report())
        diag_export_btn = QPushButton(tr("settings.diag_export_report"))
        diag_export_btn.clicked.connect(lambda checked=False: self._diag_export())
        export_row.addWidget(diag_refresh_all)
        export_row.addStretch()
        export_row.addWidget(diag_copy_btn)
        export_row.addWidget(diag_export_btn)
        diag_content_layout.addLayout(export_row)

        diag_content_layout.addStretch()
        diag_scroll.setWidget(diag_content)
        diag_layout.addWidget(diag_scroll)
        self._tabs.addTab(diagnose_tab, tr("settings.tab_diagnostics"))

        # Diagnose-Daten initial laden (günstig; Konflikte nur auf Knopfdruck)
        self._diag_data: dict = {}
        self._diag_last_conflicts = None
        self._diag_refresh()
        self._diag_populate_log_sources()

        # Tab Script Merger
        sm_tab = QWidget()
        sm_layout = QVBoxLayout(sm_tab)
        sm_scroll = QScrollArea()
        sm_scroll.setWidgetResizable(True)
        sm_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sm_content = QWidget()
        sm_content_layout = QVBoxLayout(sm_content)

        # Gruppe: Konflikte scannen
        sm_scan_grp = QGroupBox(tr("settings.sm_scan_group"))
        sm_scan_layout = QVBoxLayout(sm_scan_grp)
        self._cb_sm_check_scripts = QCheckBox(tr("settings.sm_check_scripts"))
        self._cb_sm_check_xml = QCheckBox(tr("settings.sm_check_xml"))
        sm_scan_layout.addWidget(self._cb_sm_check_scripts)
        sm_scan_layout.addWidget(self._cb_sm_check_xml)
        sm_content_layout.addWidget(sm_scan_grp)

        # Gruppe: Merge-Tool
        sm_tool_grp = QGroupBox(tr("settings.sm_merge_tool_group"))
        sm_tool_layout = QFormLayout(sm_tool_grp)
        kdiff3_row = QHBoxLayout()
        self._le_sm_kdiff3_path = QLineEdit()
        kdiff3_row.addWidget(self._le_sm_kdiff3_path)
        sm_browse_btn = QPushButton(tr("settings.sm_browse"))
        sm_browse_btn.clicked.connect(lambda checked=False: self._browse_kdiff3())
        kdiff3_row.addWidget(sm_browse_btn)
        sm_tool_layout.addRow(tr("settings.sm_kdiff3_path"), kdiff3_row)
        self._cb_sm_review_in_kdiff3 = QCheckBox(tr("settings.sm_review_in_kdiff3"))
        sm_tool_layout.addRow(self._cb_sm_review_in_kdiff3)
        sm_content_layout.addWidget(sm_tool_grp)

        # Gruppe: Automatisierung
        sm_auto_grp = QGroupBox(tr("settings.sm_automation_group"))
        sm_auto_layout = QVBoxLayout(sm_auto_grp)
        self._cb_sm_auto_delete_stale = QCheckBox(tr("settings.sm_auto_delete_stale"))
        self._cb_sm_auto_overwrite = QCheckBox(tr("settings.sm_auto_overwrite"))
        sm_auto_layout.addWidget(self._cb_sm_auto_delete_stale)
        sm_auto_layout.addWidget(self._cb_sm_auto_overwrite)
        sm_content_layout.addWidget(sm_auto_grp)

        sm_content_layout.addStretch()
        sm_scroll.setWidget(sm_content)
        sm_layout.addWidget(sm_scroll)

        # Script Merger Settings laden
        self._cb_sm_check_scripts.setChecked(settings.value("ScriptMerger/check_scripts", True, type=bool))
        self._cb_sm_check_xml.setChecked(settings.value("ScriptMerger/check_xml", True, type=bool))
        self._le_sm_kdiff3_path.setText(settings.value("ScriptMerger/kdiff3_path", "kdiff3", type=str))
        self._cb_sm_review_in_kdiff3.setChecked(settings.value("ScriptMerger/review_in_kdiff3", False, type=bool))
        self._cb_sm_auto_delete_stale.setChecked(settings.value("ScriptMerger/auto_delete_stale", True, type=bool))
        self._cb_sm_auto_overwrite.setChecked(settings.value("ScriptMerger/auto_overwrite", True, type=bool))

        self._tabs.addTab(sm_tab, tr("settings.tab_script_merger"))

        # ── Native load-order sorting tab ─────────────────────────────
        load_order_tab = QWidget()
        load_order_tab_layout = QVBoxLayout(load_order_tab)

        description = QLabel(tr("settings.native_sort_description"))
        description.setWordWrap(True)
        load_order_tab_layout.addWidget(description)

        opts_grp = QGroupBox(tr("settings.tab_load_order"))
        opts_layout = QFormLayout(opts_grp)
        self._load_order_auto_sort = QCheckBox(tr("settings.load_order_auto_sort"))
        auto_sort = settings.value("LoadOrder/auto_sort_on_deploy", None)
        if auto_sort is None:
            auto_sort = settings.value(
                "LOOT/auto_sort_on_deploy", False, type=bool
            )
        self._load_order_auto_sort.setChecked(
            str(auto_sort).lower() in {"1", "true", "yes"}
            if not isinstance(auto_sort, bool)
            else auto_sort
        )
        opts_layout.addRow(self._load_order_auto_sort)
        load_order_tab_layout.addWidget(opts_grp)
        load_order_tab_layout.addStretch()
        self._tabs.addTab(load_order_tab, tr("settings.tab_load_order"))

        if self._modern:
            tabs_wrap = QWidget()
            tw = QVBoxLayout(tabs_wrap)
            tw.setContentsMargins(20, 14, 20, 0)
            tw.setSpacing(0)
            tw.addWidget(self._tabs)
            layout.addWidget(tabs_wrap, 1)
        else:
            layout.addWidget(self._tabs)

        # Letzten Tab-Index wiederherstellen
        saved_tab = settings.value("SettingsDialog/tab_index", 0, type=int)
        self._tabs.setCurrentIndex(saved_tab)

        # Unten: OK, Abbrechen (modern: Fußleiste wie Vorlage)
        ok_btn = QPushButton(tr("button.ok"))
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(tr("button.cancel"))
        cancel_btn.clicked.connect(self.reject)
        if self._modern:
            footer = QWidget()
            footer.setObjectName("instFooter")
            footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            footer.setFixedHeight(60)
            fr = QHBoxLayout(footer)
            fr.setContentsMargins(16, 0, 16, 0)
            fr.setSpacing(8)
            fr.addStretch()
            ok_btn.setObjectName("setOkBtn")
            ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.setObjectName("setCancelBtn")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            fr.addWidget(ok_btn)
            fr.addWidget(cancel_btn)
            layout.addWidget(footer)

            # Sektions-Überschriften wie Vorlage: VERSALIEN
            for grp in self.findChildren(QGroupBox):
                grp.setTitle(grp.title().upper())
        else:
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            btn_row.addWidget(ok_btn)
            btn_row.addWidget(cancel_btn)
            layout.addLayout(btn_row)

        # Scroll-Schutz: Rad über Combo/Spinbox verstellt sonst Werte
        for w in self.findChildren(QComboBox) + self.findChildren(QSpinBox):
            w.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            w.installEventFilter(self)

    def eventFilter(self, obj, event):  # noqa: N802
        """Mausrad über Combos/Spinboxen nur mit Fokus — sonst verstellt
        das Scrollen der Seite versehentlich Werte (Theme-Live-Preview!)."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.Wheel and not obj.hasFocus():
            return True
        return super().eventFilter(obj, event)

    def exec(self):  # noqa: A003
        """Modern: Hauptfenster abdunkeln, solange der Dialog offen ist."""
        if self._modern and self.parent() is not None:
            from anvil.widgets.modal_backdrop import ModalBackdrop
            backdrop = ModalBackdrop(self.parent().window())
            try:
                return super().exec()
            finally:
                backdrop.dismiss()
        return super().exec()

    def _check_overlay_requirements(self) -> None:
        """Zeigt an, was dem Overlay im Weg steht, und sperrt notfalls den Schalter."""
        from anvil.core.overlay_deployer import environment_problems

        overwrite = self._idata.get("path_overwrite_directory", "")
        upper = Path(overwrite) if overwrite else None
        game = self._idata.get("game_path", "")
        problems = environment_problems(upper, Path(game) if game else None)

        if not problems:
            self._lbl_overlay_problems.setVisible(False)
            return

        self._lbl_overlay_problems.setText("\n".join(f"• {p}" for p in problems))
        self._lbl_overlay_problems.setVisible(True)
        self._cb_use_overlay.setChecked(False)
        self._cb_use_overlay.setEnabled(False)

    def _setting_row(self, cb: QCheckBox) -> QWidget:
        """Modern: Checkbox als Vorlage-Zeile (Text links, Schalter rechts,
        umrandete Karte). Klassisch: Checkbox unverändert."""
        if not self._modern:
            return cb
        row = QWidget()
        row.setObjectName("settingRow")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        h = QHBoxLayout(row)
        h.setContentsMargins(15, 11, 15, 11)
        h.setSpacing(10)
        lbl = QLabel(cb.text())
        lbl.setObjectName("settingRowLabel")
        cb.setText("")
        if cb.toolTip():
            row.setToolTip(cb.toolTip())
            lbl.setToolTip(cb.toolTip())
        h.addWidget(lbl, 1)
        h.addWidget(cb)
        return row

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
        beta = " [Beta]" if not getattr(plugin, "Tested", True) else ""
        self._pl_game_name.setText(f"{plugin.GameName}{beta}")
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
        host_open_path(str(path))

    # ── Script-Merger-Tab helpers ────────────────────────────────────

    def _browse_kdiff3(self) -> None:
        """Oeffnet einen Dateidialog zum Auswaehlen der KDiff3-Executable."""
        path, _ = QFileDialog.getOpenFileName(
            self, tr("settings.sm_kdiff3_path"), self._le_sm_kdiff3_path.text(),
        )
        if path:
            self._le_sm_kdiff3_path.setText(path)

    # ── Mod-Liste-Tab helpers ────────────────────────────────────────

    def _update_separator_group(self) -> None:
        """Enable/disable separator sub-widgets based on Asc/Dsc checkboxes.

        Wenn weder Asc noch Dsc aktiviert sind, werden die
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

    # ── Diagnose-Tab (#23) ─────────────────────────────────────────────

    def _diag_refresh(self) -> None:
        """Systeminfo, Pfad-Checks, Deploy-Status und Probleme neu sammeln."""
        from anvil.core import diagnostics
        sysinfo = diagnostics.collect_system_info()
        path_checks = diagnostics.collect_path_checks(self._idata, self._instance_path)
        problems = diagnostics.detect_problems(self._idata, sysinfo, path_checks)
        deploy = diagnostics.collect_deploy_status(self._instance_path)
        self._diag_data = {
            "sysinfo": sysinfo, "path_checks": path_checks,
            "problems": problems, "deploy": deploy,
        }

        for key, le in self._diag_sys.items():
            le.setText(sysinfo.get(key, ""))

        label_map = {
            "game_path": tr("settings.path_managed_game"),
            "path_mods_directory": tr("settings.path_mods"),
            "path_downloads_directory": tr("settings.path_downloads"),
            "path_overwrite_directory": tr("settings.path_overwrite"),
            "path_profiles_directory": tr("settings.path_profiles"),
        }
        self._diag_path_list.clear()
        for chk in path_checks:
            if chk["exists"] and chk["writable"]:
                status, color = tr("label.diag_status_ok"), QColor("#98C379")
            elif chk["exists"]:
                status, color = tr("label.diag_status_not_writable"), QColor("#E5C07B")
            else:
                status, color = tr("label.diag_status_missing"), QColor("#E06C75")
            label = label_map.get(chk["key"], chk["key"])
            item = QListWidgetItem(f"{label}: {chk['path'] or '—'}  [{status}]")
            item.setForeground(color)
            item.setData(Qt.ItemDataRole.UserRole, chk["path"])
            self._diag_path_list.addItem(item)

        if deploy.get("manifest"):
            self._diag_deploy_label.setText(tr(
                "label.diag_deploy_summary",
                total=deploy.get("total", 0),
                broken=deploy.get("broken", 0),
                missing=deploy.get("missing", 0),
            ))
        else:
            self._diag_deploy_label.setText(tr("label.diag_deploy_none"))

        self._diag_problem_list.clear()
        if problems:
            sev_color = {
                "error": QColor("#E06C75"),
                "warning": QColor("#E5C07B"),
                "info": QColor("#888888"),
            }
            for p in problems:
                item = QListWidgetItem(p["message"])
                item.setForeground(sev_color.get(p["severity"], QColor("#888888")))
                self._diag_problem_list.addItem(item)
        else:
            self._diag_problem_list.addItem(QListWidgetItem(tr("settings.diag_no_problems")))

    def _diag_open_selected_path(self) -> None:
        item = self._diag_path_list.currentItem()
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            host_open_path(path)

    def _diag_scan_conflicts(self) -> None:
        self._diag_conflict_list.clear()
        if self._diagnostics_provider is None:
            self._diag_conflict_list.addItem(tr("settings.diag_conflicts_unavailable"))
            self._diag_last_conflicts = None
            return
        try:
            data = self._diagnostics_provider()
        except Exception:  # noqa: BLE001 — Diagnose darf nie crashen
            data = {"available": False, "conflicts": []}
        if not data.get("available"):
            self._diag_conflict_list.addItem(tr("settings.diag_conflicts_unavailable"))
            self._diag_last_conflicts = None
            return
        conflicts = data.get("conflicts", [])
        self._diag_last_conflicts = conflicts
        if not conflicts:
            self._diag_conflict_list.addItem(tr("settings.diag_no_conflicts"))
            return
        for c in conflicts[:500]:
            self._diag_conflict_list.addItem(f"{c.get('file', '')}  →  {c.get('winner', '')}")

    def _diag_populate_log_sources(self) -> None:
        from anvil.core import diagnostics
        self._diag_log_sources = diagnostics.log_sources()
        self._diag_log_combo.blockSignals(True)
        self._diag_log_combo.clear()
        for src in self._diag_log_sources:
            self._diag_log_combo.addItem(src["label"])
        self._diag_log_combo.blockSignals(False)
        if self._diag_log_sources:
            self._diag_load_log()

    def _diag_load_log(self) -> None:
        from anvil.core import diagnostics
        idx = self._diag_log_combo.currentIndex()
        if idx < 0 or idx >= len(self._diag_log_sources):
            self._diag_log_lines = []
            self._diag_log_view.setPlainText("")
            return
        self._diag_log_lines = diagnostics.read_log_tail(self._diag_log_sources[idx]["path"])
        self._diag_filter_log()

    def _diag_filter_log(self) -> None:
        query = self._diag_log_search.text().strip().lower()
        if query:
            lines = [ln for ln in self._diag_log_lines if query in ln.lower()]
        else:
            lines = self._diag_log_lines
        self._diag_log_view.setPlainText("\n".join(lines))

    def _diag_open_log(self) -> None:
        idx = self._diag_log_combo.currentIndex()
        if 0 <= idx < len(self._diag_log_sources):
            host_open_path(self._diag_log_sources[idx]["path"])

    def _diag_build_report(self) -> str:
        from anvil.core import diagnostics
        d = self._diag_data or {}
        return diagnostics.build_report(
            d.get("sysinfo", {}), d.get("path_checks", []), d.get("problems", []),
            deploy_status=d.get("deploy"), conflicts=self._diag_last_conflicts,
        )

    def _diag_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, tr("settings.diag_export_report"),
            "anvil-diagnose.txt", "Text (*.txt)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self._diag_build_report(), encoding="utf-8")
        except OSError:
            pass

    def _diag_copy_report(self) -> None:
        QApplication.clipboard().setText(self._diag_build_report())

    @staticmethod
    def _settings() -> QSettings:
        path = str(Path.home() / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf")
        return QSettings(path, QSettings.Format.IniFormat)

    # ── API key storage (delegates to anvil.core.secure_storage) ─────

    @staticmethod
    def save_api_key(api_key: str) -> None:
        from anvil.core.secure_storage import save_api_key
        save_api_key(api_key)

    @staticmethod
    def load_api_key() -> str:
        from anvil.core.secure_storage import load_api_key
        return load_api_key()

    @staticmethod
    def delete_api_key() -> None:
        from anvil.core.secure_storage import delete_api_key
        delete_api_key()

    def _on_theme_changed(self, theme_name: str):
        """Apply selected theme live as preview (mit Theme-eigenen Farben)."""
        # Klassisches Theme gewählt → Modern-Design deaktivieren
        self._modern_active = False
        self._update_style_states()
        # Jedes Theme behält seine eigenen gespeicherten Farben.
        self._color_overrides = load_overrides(self._settings(), theme_name)
        self._rebuild_color_rows()
        self._preview_theme()

    # ── Modern-Design (Anvil Dunkel/Hell) ─────────────────────────────
    def _selected_modern_theme(self) -> str:
        return self._selected_design or MODERN_THEME_DARK

    def _schedule_preview(self) -> None:
        """Preview gebündelt starten: schnelle Klicks fallen zu EINEM
        Restyling zusammen, und der Button-Zustand malt sich zuerst."""
        if not hasattr(self, "_preview_timer"):
            self._preview_timer = QTimer(self)
            self._preview_timer.setSingleShot(True)
            self._preview_timer.setInterval(60)
            self._preview_timer.timeout.connect(self._preview_theme)
        self._preview_timer.start()

    def _on_design_clicked(self, theme_name: str) -> None:
        changed = (not self._modern_active
                   or self._selected_design != theme_name)
        self._modern_active = True
        self._selected_design = theme_name
        self._btn_design_dark.setChecked(theme_name == MODERN_THEME_DARK)
        self._btn_design_light.setChecked(theme_name == MODERN_THEME_LIGHT)
        self._update_style_states()
        if changed:
            self._schedule_preview()

    def _on_accent_clicked(self, accent_key: str) -> None:
        changed = accent_key != self._selected_accent
        self._selected_accent = accent_key
        for key, btn in self._accent_buttons.items():
            btn.setChecked(key == accent_key)
        if changed and self._modern_active:
            self._schedule_preview()

    def _on_density_clicked(self, density_key: str) -> None:
        changed = density_key != self._selected_density
        self._selected_density = density_key
        for key, btn in self._density_buttons.items():
            btn.setChecked(key == density_key)
        if changed and self._modern_active:
            self._schedule_preview()

    def _update_style_states(self) -> None:
        """Modern aktiv → klassischer Farbeditor aus (und umgekehrt)."""
        self._theme_colors_grp.setEnabled(not self._modern_active)
        if not self._modern_active:
            self._btn_design_dark.setChecked(False)
            self._btn_design_light.setChecked(False)
        self._update_accent_icons()

    def _update_accent_icons(self) -> None:
        """Farb-Punkte der Akzent-Buttons passend zur gewählten Variante."""
        theme = self._selected_modern_theme()
        for key, btn in self._accent_buttons.items():
            if self._modern:
                # Vorlage: 22px-Farbkreis
                pix = QPixmap(27, 27)
                pix.fill(Qt.GlobalColor.transparent)
                p = QPainter(pix)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(MODERN_ACCENTS[key][theme][0]))
                p.drawEllipse(0, 0, 27, 27)
                p.end()
            else:
                pix = QPixmap(14, 14)
                pix.fill(QColor(MODERN_ACCENTS[key][theme][0]))
            btn.setIcon(QIcon(pix))

    # ── Theme-Farben (anpassbare Rollenfarben) ───────────────────────
    def _current_theme_name(self) -> str:
        return self._stil_combo.currentText()

    def _effective_color(self, role: str) -> str:
        """Aktuell wirksame Farbe einer Rolle (Override oder Theme-Default)."""
        override = self._color_overrides.get(role)
        if override:
            return override
        return default_palette(self._current_theme_name()).get(role, "#000000")

    def _make_swatch(self, hex_color: str) -> QLabel:
        # Farbfläche als gefülltes Pixmap in einem QLabel — KEIN setStyleSheet.
        # Pixmap-Inhalt liegt über dem Hintergrund und bleibt vom Theme-QSS
        # (* { background }) unberührt; QPalette würde davon überschrieben.
        swatch = QLabel()
        swatch.setFixedSize(56, 20)
        swatch.setFrameShape(QFrame.Shape.Box)
        swatch.setScaledContents(True)
        self._set_swatch_color(swatch, hex_color)
        return swatch

    def _set_swatch_color(self, swatch: QLabel, hex_color: str) -> None:
        pix = QPixmap(56, 20)
        pix.fill(QColor(hex_color))
        swatch.setPixmap(pix)

    def _rebuild_color_rows(self) -> None:
        """Baut die Farbzeilen für das aktuell gewählte Theme neu auf."""
        layout = self._theme_colors_layout
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._color_swatches = {}
        palette = default_palette(self._current_theme_name())
        role_labels = {
            "background": tr("settings.color_role_background"),
            "text": tr("settings.color_role_text"),
            "accent": tr("settings.color_role_accent"),
            "list_background": tr("settings.color_role_list_background"),
            "hover": tr("settings.color_role_hover"),
            "disabled_text": tr("settings.color_role_disabled_text"),
        }
        for role in COLOR_ROLES:
            if role not in palette:
                continue
            row = QHBoxLayout()
            row.addWidget(QLabel(role_labels.get(role, role)))
            row.addStretch()
            swatch = self._make_swatch(self._effective_color(role))
            self._color_swatches[role] = swatch
            row.addWidget(swatch)
            change_btn = QPushButton(tr("settings.color_change"))
            change_btn.clicked.connect(
                lambda checked=False, r=role: self._on_pick_color(r))
            row.addWidget(change_btn)
            container = QWidget()
            container.setLayout(row)
            layout.addWidget(container)

    def _on_pick_color(self, role: str) -> None:
        from PySide6.QtWidgets import QColorDialog
        current = QColor(self._effective_color(role))
        chosen = QColorDialog.getColor(
            current, self, tr("settings.color_pick_title"),
            QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if not chosen.isValid():
            return
        hex_value = chosen.name()
        self._color_overrides[role] = hex_value
        swatch = self._color_swatches.get(role)
        if swatch is not None:
            self._set_swatch_color(swatch, hex_value)
        self._preview_theme()

    def _preview_theme(self) -> None:
        app = QApplication.instance()
        if not app:
            return
        if self._modern_active:
            apply_theme(app, self._selected_modern_theme(), None,
                        accent=self._selected_accent,
                        density=self._selected_density)
        else:
            apply_theme(app, self._current_theme_name(), self._color_overrides)
        # Bäume cachen Zeilenhöhen — NUR bei geänderter Dichte relayouten,
        # sonst wird jeder Farbwechsel unnötig teuer
        last = getattr(self, "_last_preview_density", None)
        if self._modern_active and self._selected_density != last:
            from PySide6.QtWidgets import QTreeView
            for w in app.allWidgets():
                if isinstance(w, QTreeView):
                    w.doItemsLayout()
        self._last_preview_density = self._selected_density if self._modern_active else None
        # Theme-abhängige Widget-Details nachziehen (Schalter-Spaltenbreite,
        # Profilleisten-Farben, …) — billig im Vergleich zum App-Restyling
        for w in app.allWidgets():
            if hasattr(w, "apply_theme_metrics"):
                w.apply_theme_metrics()
        self._preview_dirty = True

    def _on_reset_colors(self) -> None:
        self._color_overrides = {}
        self._rebuild_color_rows()
        self._preview_theme()

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
        host_open_path(str(get_styles_dir()))


    def accept(self):
        """Save all settings, then close."""
        settings = self._settings()
        if self._modern_active:
            settings.setValue("style/theme", self._selected_modern_theme())
        else:
            settings.setValue("style/theme", self._stil_combo.currentText())
            # Theme-Farben pro klassischem Theme speichern
            save_overrides(settings, self._stil_combo.currentText(),
                           self._color_overrides)
        settings.setValue("style/accent", self._selected_accent)
        settings.setValue("style/density", self._selected_density)
        # Sprache speichern
        lang_idx = self._lang_combo.currentIndex()
        new_lang = self._lang_codes[lang_idx] if 0 <= lang_idx < len(self._lang_codes) else self._initial_lang
        settings.setValue("General/language", new_lang)
        # Tab Allgemein — QSettings
        settings.setValue("General/check_for_updates", self._cb_check_updates.isChecked())
        settings.setValue("Interface/center_dialogs", self._cb_center_dialogs.isChecked())
        settings.setValue("Interface/confirm_instance_change", self._cb_confirm_instance.isChecked())
        settings.setValue("Interface/show_menubar_on_alt", self._cb_alt_menubar.isChecked())
        settings.setValue("Interface/shortcut_launch_game", self._cb_shortcut_launch_game.isChecked())
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
        settings.setValue("ModList/conflict_highlight_on_select", self._cb_conflict_highlight.isChecked())
        settings.setValue("ModList/symbol_conflicts", self._cb_sym_conflicts.isChecked())
        settings.setValue("ModList/symbol_flags", self._cb_sym_flags.isChecked())
        settings.setValue("ModList/symbol_content", self._cb_sym_content.isChecked())
        settings.setValue("ModList/symbol_version", self._cb_sym_version.isChecked())
        # Tab Nexus — Optionen
        settings.setValue("Nexus/tracking_enabled", self._cb_nexus_tracking.isChecked())
        settings.setValue("Nexus/hide_api_counter", self._cb_nexus_hide_api.isChecked())
        settings.setValue("Nexus/category_mapping_enabled", self._cb_nexus_catmap.isChecked())
        # Bevorzugter Download-Server (leer = automatisch / erster verfügbarer)
        pref_item = self._nexus_pref_list.currentItem()
        pref_server = pref_item.data(Qt.ItemDataRole.UserRole) if pref_item else ""
        settings.setValue("Nexus/preferred_server", pref_server or "")
        # Tab Script Merger
        settings.setValue("ScriptMerger/check_scripts", self._cb_sm_check_scripts.isChecked())
        settings.setValue("ScriptMerger/check_xml", self._cb_sm_check_xml.isChecked())
        settings.setValue("ScriptMerger/kdiff3_path", self._le_sm_kdiff3_path.text())
        settings.setValue("ScriptMerger/review_in_kdiff3", self._cb_sm_review_in_kdiff3.isChecked())
        settings.setValue("ScriptMerger/auto_delete_stale", self._cb_sm_auto_delete_stale.isChecked())
        settings.setValue("ScriptMerger/auto_overwrite", self._cb_sm_auto_overwrite.isChecked())
        # Native load-order settings
        settings.setValue(
            "LoadOrder/auto_sort_on_deploy", self._load_order_auto_sort.isChecked()
        )
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
                idata["use_overlay"] = self._cb_use_overlay.isChecked()
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
        """Revert theme + colors to the previous saved state and close."""
        if self._preview_dirty:
            app = QApplication.instance()
            if app:
                apply_theme(app, self._previous_theme,
                            load_overrides(self._settings(), self._previous_theme),
                            accent=self._previous_accent,
                            density=self._previous_density)
                # Spaltenbreiten + Zeilenhöhen an das zurückgesetzte Theme anpassen
                from PySide6.QtWidgets import QTreeView
                for w in app.allWidgets():
                    if hasattr(w, "apply_theme_metrics"):
                        w.apply_theme_metrics()
                    if isinstance(w, QTreeView):
                        w.doItemsLayout()
        # Tab-Index merken auch bei Abbrechen
        s = self._settings()
        s.setValue("SettingsDialog/tab_index", self._tabs.currentIndex())
        super().reject()

    # ── Nexus-Tab helpers ─────────────────────────────────────────────

    def _nx_log_add(self, text: str) -> None:
        """Zeile zum Nexus-Verbindungs-Log hinzufuegen."""
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
        """SSO-Login via Browser starten."""
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
        self.save_api_key(api_key)
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
            self.save_api_key(key.strip())
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

        self.delete_api_key()
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

    def _nx_load_known_servers(self) -> list:
        """Lies die gecachte Server-Liste (JSON) aus QSettings. Wirft nie."""
        raw = self._settings().value("Nexus/known_servers", "", type=str)
        try:
            servers = json.loads(raw) if raw else []
        except (ValueError, TypeError):
            servers = []
        if not isinstance(servers, list):
            return []
        return [str(s) for s in servers if s]

    def _nx_populate_servers(self) -> None:
        """Befüllt die Server-Listen aus dem Cache und wählt die Präferenz vor."""
        servers = self._nx_load_known_servers()
        pref_saved = self._settings().value("Nexus/preferred_server", "", type=str)

        self._nexus_known_list.clear()
        for sid in servers:
            self._nexus_known_list.addItem(QListWidgetItem(sid))

        self._nexus_pref_list.clear()
        auto = QListWidgetItem(tr("settings.nexus_server_auto"))
        auto.setData(Qt.ItemDataRole.UserRole, "")
        self._nexus_pref_list.addItem(auto)
        selected = auto
        for sid in servers:
            item = QListWidgetItem(sid)
            item.setData(Qt.ItemDataRole.UserRole, sid)
            self._nexus_pref_list.addItem(item)
            if sid == pref_saved:
                selected = item
        # Gespeicherte Präferenz auch zeigen, wenn sie (noch) nicht im Cache steht
        if pref_saved and pref_saved not in servers:
            item = QListWidgetItem(pref_saved)
            item.setData(Qt.ItemDataRole.UserRole, pref_saved)
            self._nexus_pref_list.addItem(item)
            selected = item
        self._nexus_pref_list.setCurrentItem(selected)

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
