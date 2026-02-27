"""Game-Panel — MO2-Kopie: großes Game-Icon, Tabs, Downloads mit Neu laden."""

from __future__ import annotations

import configparser
import os
import subprocess
from pathlib import Path

from anvil.core.resource_path import get_anvil_base

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QCheckBox,
    QLineEdit,
    QMenu,
    QFrame,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QAbstractItemView,
)

from PySide6.QtGui import QPixmap, QIcon, QColor, QAction, QPainter, QFont, QDesktopServices
from PySide6.QtCore import Qt, QSize, QPoint, Signal, QUrl, QMimeData, QSettings

from anvil.core.mod_installer import SUPPORTED_EXTENSIONS
from anvil.core.mod_deployer import ModDeployer
from anvil.core.download_manager import DownloadManager
from anvil.core.persistent_header import PersistentHeader
from anvil.core.plugins_txt_writer import PluginsTxtWriter
from anvil.core import _todo
from anvil.core.translator import tr


class _NumericSortItem(QTableWidgetItem):
    """QTableWidgetItem that sorts by UserRole data (numeric) instead of text."""
    def __lt__(self, other):
        val = self.data(Qt.ItemDataRole.UserRole)
        other_val = other.data(Qt.ItemDataRole.UserRole)
        if val is not None and other_val is not None:
            return val < other_val
        return super().__lt__(other)


class _DraggableDownloadTable(QTableWidget):
    """QTableWidget that supports dragging archive rows as file URIs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)

    def mimeData(self, items):
        mime = QMimeData()
        urls = []
        rows_seen = set()
        for item in items:
            r = item.row()
            if r in rows_seen:
                continue
            rows_seen.add(r)
            name_item = self.item(r, 0)
            if name_item and name_item.data(Qt.ItemDataRole.UserRole + 2):
                continue  # Separator-Zeile überspringen
            if name_item:
                path = name_item.data(Qt.ItemDataRole.UserRole)
                if path:
                    urls.append(QUrl.fromLocalFile(str(path)))
        if urls:
            mime.setUrls(urls)
        return mime


class GamePanel(QWidget):
    install_requested = Signal(list)  # list of archive path strings
    start_requested = Signal(str, str)  # (binary_path, working_dir)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gamePanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Rechte Seite oben: Game-Button (140x140) mit Dropdown + Label, Starten; Verknüpfung-Button oben rechts
        top_frame = QFrame()
        top_layout = QVBoxLayout(top_frame)
        top_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Verknüpfung-Button oben rechts
        link_btn = QPushButton()
        link_btn.setObjectName("linkButton")
        _exec_icon = str(get_anvil_base() / "styles" / "icons" / "executables.svg")
        if os.path.exists(_exec_icon):
            link_btn.setIcon(QIcon(_exec_icon))
        link_btn.setIconSize(QSize(20, 20))
        link_btn.setToolTip(tr("tooltip.link"))
        link_btn.setFixedWidth(32)
        link_btn.clicked.connect(_todo("Verknüpfung"))
        link_btn_row = QHBoxLayout()
        link_btn_row.addStretch()
        link_btn_row.addWidget(link_btn)
        top_layout.addLayout(link_btn_row)

        # Game-Icon (Banner) — Klick öffnet Executable-Menü
        pix = QPixmap(140, 140)
        pix.fill(QColor("#242424"))
        self._game_btn = QToolButton(self)
        self._game_btn.setIcon(QIcon(pix))
        self._game_btn.setIconSize(QSize(140, 140))
        self._game_btn.setFixedSize(140, 140)
        self._game_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._exe_menu = QMenu(self)
        self._game_btn.setMenu(self._exe_menu)
        self._game_btn.setStyleSheet(
            "QToolButton { background: #242424; border: 2px solid #3D3D3D; border-radius: 4px;"
            "             padding: 0; margin: 0; }"
            "QToolButton:hover { background: #2a2a2a; }"
            "QToolButton::menu-indicator { image: none; width: 0; height: 0; }"
        )
        # ▾ Dropdown-Pfeil unten rechts als Overlay
        arrow_label = QLabel("▾", self._game_btn)
        arrow_label.setStyleSheet(
            "background: rgba(0,0,0,150); color: #FFF; font-size: 16px;"
            "padding: 1px 4px; border-radius: 3px; border: none;"
        )
        arrow_label.adjustSize()
        arrow_label.move(140 - arrow_label.width() - 4, 140 - arrow_label.height() - 4)
        arrow_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        top_layout.addWidget(self._game_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        self._game_label = QLabel(tr("game_panel.no_game_selected"))
        self._game_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(self._game_label)

        # Start-Button
        self._start_btn = QPushButton()
        self._start_btn.setObjectName("startButton")
        _play_icon = str(get_anvil_base() / "styles" / "icons" / "files" / "play.png")
        if os.path.exists(_play_icon):
            self._start_btn.setIcon(QIcon(_play_icon))
            self._start_btn.setIconSize(QSize(24, 24))
        self._start_btn.setMinimumWidth(140)
        self._start_btn.setFixedHeight(36)
        self._start_btn.setToolTip(tr("game_panel.start"))
        self._start_btn.clicked.connect(self._on_start_clicked)
        top_layout.addWidget(self._start_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        # (Deploy-UI entfernt — Deploy/Purge läuft jetzt automatisch)

        # Executables data: list of {"name", "binary"} dicts
        self._executables: list[dict[str, str]] = []
        self._selected_exe_index: int = 0

        layout.addWidget(top_frame)

        self._tabs = QTabWidget()
        tabs = self._tabs  # local alias for existing code
        tabs.tabBar().setExpanding(False)
        tabs.tabBar().setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        tabs.setStyleSheet("QTabBar { qproperty-alignment: AlignCenter; }"
                           "QTabWidget::tab-bar { alignment: center; }")

        # ── Plugins-Tab (Index 0) ──────────────────────────────────────
        plugins_w = QWidget()
        plugins_layout = QVBoxLayout(plugins_w)
        self._plugins_tree = QTreeWidget()
        self._plugins_tree.setColumnCount(3)
        self._plugins_tree.setHeaderLabels([
            tr("game_panel.plugins_col_name"),
            tr("game_panel.plugins_col_type"),
            tr("game_panel.plugins_col_index"),
        ])
        self._plugins_tree.setAlternatingRowColors(True)
        self._plugins_tree.setRootIsDecorated(False)
        plugins_header = self._plugins_tree.header()
        plugins_header.setStretchLastSection(False)
        plugins_header.setCascadingSectionResizes(True)
        plugins_header.setMinimumSectionSize(40)
        plugins_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        plugins_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        plugins_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._plugins_tree.setColumnWidth(1, 80)
        self._plugins_tree.setColumnWidth(2, 60)
        self._ph_plugins = PersistentHeader(plugins_header, "plugins")
        plugins_layout.addWidget(self._plugins_tree)
        tabs.addTab(plugins_w, tr("game_panel.plugins_tab"))
        tabs.setTabVisible(0, False)  # hidden until Bethesda game detected

        # ── Daten-Tab ─────────────────────────────────────────────────
        data = QWidget()
        data_layout = QVBoxLayout(data)
        data_reload_btn = QPushButton(tr("game_panel.reload"))
        _refresh_icon = str(get_anvil_base() / "styles" / "icons" / "refresh.svg")
        if os.path.exists(_refresh_icon):
            data_reload_btn.setIcon(QIcon(_refresh_icon))
        data_reload_btn.setIconSize(QSize(20, 20))
        data_reload_btn.clicked.connect(self._on_reload_data)
        data_layout.addWidget(data_reload_btn)
        self._data_tree = QTreeWidget()
        self._data_tree.setColumnCount(5)
        self._data_tree.setHeaderLabels([tr("game_panel.header_name"), tr("game_panel.header_mod"), tr("game_panel.header_type"), tr("game_panel.header_size"), tr("game_panel.header_date")])
        self._data_tree.setAlternatingRowColors(True)
        data_header = self._data_tree.header()
        data_header.setStretchLastSection(False)
        data_header.setCascadingSectionResizes(True)
        data_header.setMinimumSectionSize(40)
        data_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._data_tree.setColumnWidth(0, 200)
        self._data_tree.setColumnWidth(1, 100)
        self._data_tree.setColumnWidth(2, 70)
        self._data_tree.setColumnWidth(3, 80)
        self._data_tree.setColumnWidth(4, 130)
        self._ph_data = PersistentHeader(data_header, "data")
        data_layout.addWidget(self._data_tree)
        data_bar = QHBoxLayout()
        data_bar.addWidget(QCheckBox(tr("game_panel.conflicts_only")))
        data_bar.addWidget(QCheckBox(tr("game_panel.archives")))
        data_filter_edit = QLineEdit()
        data_filter_edit.setPlaceholderText(tr("placeholder.filter"))
        data_bar.addWidget(data_filter_edit)
        data_bar.addStretch()
        data_layout.addLayout(data_bar)
        tabs.addTab(data, tr("game_panel.data_tab"))

        # ── Spielstände-Tab ───────────────────────────────────────────
        saves = QWidget()
        saves_layout = QVBoxLayout(saves)
        self._saves_tree = QTreeWidget()
        self._saves_tree.setColumnCount(2)
        self._saves_tree.setHeaderLabels([tr("game_panel.header_name"), tr("game_panel.header_file")])
        saves_header = self._saves_tree.header()
        saves_header.setStretchLastSection(False)
        saves_header.setCascadingSectionResizes(True)
        saves_header.setMinimumSectionSize(40)
        saves_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._ph_saves = PersistentHeader(saves_header, "saves")
        saves_layout.addWidget(self._saves_tree)
        tabs.addTab(saves, tr("game_panel.saves_tab"))
        tabs.setTabEnabled(2, False)  # Saves tab — coming soon

        # ── Downloads-Tab ─────────────────────────────────────────────
        downloads = QWidget()
        dl_layout = QVBoxLayout(downloads)
        reload_btn = QPushButton(tr("game_panel.reload"))
        _refresh_icon2 = str(get_anvil_base() / "styles" / "icons" / "refresh.svg")
        if os.path.exists(_refresh_icon2):
            reload_btn.setIcon(QIcon(_refresh_icon2))
        reload_btn.setIconSize(QSize(20, 20))
        reload_btn.clicked.connect(self.refresh_downloads)
        dl_layout.addWidget(reload_btn)
        self._dl_table = _DraggableDownloadTable()
        self._dl_table.setColumnCount(4)
        self._dl_table.setHorizontalHeaderLabels([tr("game_panel.header_name"), tr("game_panel.header_size"), tr("game_panel.header_status"), tr("game_panel.header_filetime")])
        dl_header = self._dl_table.horizontalHeader()
        dl_header.setStretchLastSection(False)
        dl_header.setCascadingSectionResizes(True)
        dl_header.setMinimumSectionSize(40)
        dl_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._dl_table.setColumnWidth(0, 250)
        self._dl_table.setColumnWidth(1, 90)
        self._dl_table.setColumnWidth(2, 120)
        self._dl_table.setColumnWidth(3, 140)
        self._ph_downloads = PersistentHeader(dl_header, "downloads")
        self._dl_table.verticalHeader().setDefaultSectionSize(46)
        self._dl_table.verticalHeader().setVisible(False)
        self._dl_table.setStyleSheet("QTableWidget { font-size: 14px; }")
        self._dl_table.setSortingEnabled(True)
        self._dl_table.setAlternatingRowColors(True)
        self._dl_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._dl_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._dl_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._dl_table.setRowCount(0)
        self._dl_table.cellDoubleClicked.connect(self._on_dl_double_click)
        self._dl_table.cellClicked.connect(self._on_dl_cell_clicked)
        self._dl_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._dl_table.customContextMenuRequested.connect(self._on_dl_context_menu)
        dl_layout.addWidget(self._dl_table)
        self._cb_hidden = QCheckBox(tr("game_panel.hidden_files"))
        self._cb_hidden.stateChanged.connect(self._on_toggle_hidden)
        dl_layout.addWidget(self._cb_hidden)
        self._dl_filter_edit = fe = QLineEdit()
        fe.setPlaceholderText(tr("placeholder.filter"))
        fe.textChanged.connect(self._on_dl_filter_changed)
        dl_layout.addWidget(fe)
        tabs.addTab(downloads, tr("game_panel.downloads_tab"))

        layout.addWidget(tabs)

        # Track current state for reload / icon updates
        self._current_game_path: Path | None = None
        self._current_short_name: str = ""
        self._current_plugin = None
        self._icon_manager = None
        self._downloads_path: Path | None = None
        self._mods_path: Path | None = None
        self._instance_path: Path | None = None
        self._current_profile_name: str = "Default"
        self._deployer: ModDeployer | None = None
        # Map row index → archive Path for installation
        self._dl_archives: list[Path] = []
        # Hidden downloads toggle (MO2: showHidden)
        self._show_hidden: bool = False
        # Collapsed folder separators in downloads tab
        self._dl_collapsed: set[str] = set()

        # Download manager for active Nexus downloads
        self._download_manager = DownloadManager(self)
        self._download_manager.download_started.connect(self._on_dm_started)
        self._download_manager.download_progress.connect(self._on_dm_progress)
        self._download_manager.download_finished.connect(self._on_dm_finished)
        self._download_manager.download_error.connect(self._on_dm_error)
        # Track active download rows: download_id → dl_table row
        self._active_dl_rows: dict[int, int] = {}

    # ── Column persistence ─────────────────────────────────────────────

    def restore_tab_column_widths(self, tab_index: int) -> None:
        """Restore column widths for a specific tab (0=plugins, 1=data, 2=saves, 3=downloads)."""
        if tab_index == 0:
            self._ph_plugins.restore()
        elif tab_index == 1:
            self._ph_data.restore()
        elif tab_index == 2:
            self._ph_saves.restore()
        elif tab_index == 3:
            self._ph_downloads.restore()

    def restore_all_column_widths(self) -> None:
        """Restore column widths for all tabs."""
        self._ph_plugins.restore()
        self._ph_data.restore()
        self._ph_saves.restore()
        self._ph_downloads.restore()

    def flush_column_widths(self) -> None:
        """Flush any pending debounced column-width writes."""
        self._ph_plugins.flush()
        self._ph_data.flush()
        self._ph_saves.flush()
        self._ph_downloads.flush()

    # ── Public API ────────────────────────────────────────────────────

    def update_game(
        self,
        game_name: str,
        game_path: Path | None,
        game_plugin=None,
        icon_manager=None,
        game_short_name: str = "",
    ) -> None:
        """Update the panel to reflect the active game instance.

        Args:
            game_name: Display name of the game.
            game_path: Path to the game installation directory,
                       or None if not detected.
            game_plugin: The BaseGame plugin instance, or None.
            icon_manager: IconManager for loading icons.
            game_short_name: Short name for icon lookups.
        """
        self._current_game_path = game_path
        self._current_short_name = game_short_name
        self._current_plugin = game_plugin
        self._icon_manager = icon_manager

        # Re-init deployer if instance_path already set
        direct_patterns = getattr(game_plugin, "GameDirectInstallMods", []) if game_plugin else []
        data_path = getattr(game_plugin, "GameDataPath", "") if game_plugin else ""
        nest = getattr(game_plugin, "GameNestModsUnderName", False) if game_plugin else False
        lml_path = getattr(game_plugin, "GameLMLPath", "") if game_plugin else ""
        multi_routes = getattr(game_plugin, "GameMultiFolderRoutes", {}) if game_plugin else {}
        if self._instance_path and game_path:
            self._deployer = ModDeployer(self._instance_path, game_path, direct_patterns, profile_name=self._current_profile_name, data_path=data_path, nest_under_mod_name=nest, lml_path=lml_path, multi_folder_routes=multi_routes)

        # Update label
        self._game_label.setText(game_name or tr("game_panel.no_game_selected"))

        # Update game button icon (banner or placeholder)
        self._update_game_button_icon(game_name)

        # Rebuild executables menu (in game button)
        self._rebuild_executables_menu(game_plugin)

        # Update data tree with real directory contents
        self._populate_data_tree(game_path)

        # Plugins-Tab visibility
        has_plugins = (
            game_plugin is not None
            and hasattr(game_plugin, "has_plugins_txt")
            and game_plugin.has_plugins_txt()
        )
        self._tabs.setTabVisible(0, has_plugins)
        if has_plugins:
            self._refresh_plugins_tab()

        # Downloads are populated via set_downloads_path() from MainWindow

    # ── Internal helpers ──────────────────────────────────────────────

    def _update_game_button_icon(self, game_name: str) -> None:
        """Set the game button to the cached banner or a placeholder."""
        size = 140
        banner = None
        if self._icon_manager and self._current_short_name:
            banner = self._icon_manager.get_game_banner(self._current_short_name)
            if banner is None:
                banner = self._icon_manager.get_game_icon(self._current_short_name)

        if banner is not None:
            scaled = banner.scaled(
                QSize(size, size),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._game_btn.setIcon(QIcon(scaled))
            self._game_btn.setIconSize(QSize(size, size))
        else:
            # Placeholder: grey box with game name
            pix = QPixmap(size, size)
            pix.fill(QColor("#242424"))
            if game_name:
                p = QPainter(pix)
                p.setPen(QColor("#808080"))
                f = QFont()
                f.setPixelSize(14)
                p.setFont(f)
                p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, game_name)
                p.end()
            self._game_btn.setIcon(QIcon(pix))
            self._game_btn.setIconSize(QSize(size, size))

    def _rebuild_executables_menu(self, game_plugin) -> None:
        """Rebuild the executable menu in the game button."""
        self._exe_menu.clear()
        self._executables.clear()
        self._selected_exe_index = 0

        # 1. <Bearbeiten...> — kein Icon, disabled
        edit_action = self._exe_menu.addAction(tr("game_panel.edit_executables"))
        edit_action.setEnabled(False)
        self._exe_menu.addSeparator()

        # Cover Art (game_wide.jpg) für Spiel-Einträge, Red Bird (game.png) für REDmod/REDprelauncher
        cover_icon = self._get_small_game_icon()
        redmod_icon = self._get_small_redmod_icon()

        if game_plugin is not None:
            game_name = game_plugin.GameName if hasattr(game_plugin, "GameName") else ""

            for exe in game_plugin.executables():
                name = exe.get("name", "")
                binary = exe.get("binary", "")
                if not name:
                    continue
                idx = len(self._executables)
                # REDprelauncher / REDmod → Red Bird (game.png), Spiel → Cover Art
                if "prelauncher" in binary.lower() or "redmod" in binary.lower():
                    icon = redmod_icon
                else:
                    icon = cover_icon
                action = self._exe_menu.addAction(icon, name)
                action.triggered.connect(lambda checked, i=idx: self._on_exe_selected(i))
                self._executables.append({"name": name, "binary": binary})

            # Disabled-Platzhalter: "skip REDmod deploy", "Manually deploy REDmod"
            has_redmod = any(
                "redmod" in e.get("binary", "").lower() or "prelauncher" in e.get("binary", "").lower()
                for e in game_plugin.executables()
            )
            if game_name and has_redmod:
                skip_action = self._exe_menu.addAction(cover_icon, tr("game_panel.skip_redmod", name=game_name))
                skip_action.setEnabled(False)
                deploy_action = self._exe_menu.addAction(tr("game_panel.deploy_redmod"))
                deploy_action.setEnabled(False)

            # Explore Virtual Folder
            self._exe_menu.addSeparator()
            explore_action = self._exe_menu.addAction(
                self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon),
                tr("game_panel.explore_virtual"),
            )
            explore_action.triggered.connect(self._on_explore_virtual_folder)

        # Select first executable by default
        if self._executables:
            self._selected_exe_index = 0
            self._start_btn.setToolTip(tr("game_panel.start_with_name", name=self._executables[0]['name']))

    def _get_small_game_icon(self) -> QIcon:
        """Return small (24x24) game banner icon (cover art), or placeholder."""
        if self._icon_manager and self._current_short_name:
            pix = self._icon_manager.get_game_banner(self._current_short_name)
            if pix is None:
                pix = self._icon_manager.get_game_icon(self._current_short_name)
            if pix is not None:
                return QIcon(pix.scaled(
                    QSize(24, 24),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
        return self._placeholder_icon()

    def _get_small_redmod_icon(self) -> QIcon:
        """Return small (24x24) REDmod icon (red bird), or placeholder."""
        if self._icon_manager and self._current_short_name:
            pix = self._icon_manager.get_executable_icon(
                self._current_short_name, "redMod.exe"
            )
            if pix is not None:
                return QIcon(pix.scaled(
                    QSize(24, 24),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
        return self._placeholder_icon()

    @staticmethod
    def _placeholder_icon() -> QIcon:
        """Small grey placeholder icon."""
        pix = QPixmap(24, 24)
        pix.fill(QColor("#3D3D3D"))
        return QIcon(pix)

    def _on_explore_virtual_folder(self) -> None:
        """Open the .mods/ directory in the file manager."""
        mods_path = getattr(self, "_mods_path", None)
        if mods_path and mods_path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(mods_path)))

    # ── Silent deploy / purge (called from MainWindow) ──────────────

    def silent_deploy(self) -> None:
        """Deploy mods silently.  Called automatically by MainWindow."""
        if self._deployer:
            self._deployer.deploy()
        # Write plugins.txt for Bethesda games
        if (
            self._current_plugin is not None
            and hasattr(self._current_plugin, "has_plugins_txt")
            and self._current_plugin.has_plugins_txt()
            and self._current_game_path is not None
            and self._instance_path is not None
        ):
            writer = PluginsTxtWriter(
                self._current_plugin, self._current_game_path, self._instance_path
            )
            writer.write()
            self._refresh_plugins_tab()

    def silent_purge(self) -> None:
        """Purge deployed mods silently.  Called automatically by MainWindow."""
        if self._deployer:
            self._deployer.purge()

    def _refresh_plugins_tab(self) -> None:
        """Populate the plugins tree with scanned plugin files."""
        self._plugins_tree.clear()

        if (
            self._current_plugin is None
            or self._current_game_path is None
            or self._instance_path is None
            or not hasattr(self._current_plugin, "has_plugins_txt")
            or not self._current_plugin.has_plugins_txt()
        ):
            return

        writer = PluginsTxtWriter(
            self._current_plugin, self._current_game_path, self._instance_path
        )
        plugins = writer.scan_plugins()

        primary_lower = {
            p.lower()
            for p in getattr(self._current_plugin, "PRIMARY_PLUGINS", [])
        }

        for idx, name in enumerate(plugins):
            ext = Path(name).suffix.lower()
            is_primary = name.lower() in primary_lower

            item = QTreeWidgetItem()
            # Column 0: Plugin name
            item.setText(0, name)
            item.setCheckState(0, Qt.CheckState.Checked)
            if is_primary:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                font = item.font(0)
                font.setItalic(True)
                item.setFont(0, font)
                item.setForeground(0, QColor("#808080"))

            # Column 1: Type
            type_label = ext.lstrip(".").upper()
            item.setText(1, type_label)

            # Column 2: Mod index (hex, 2-digit)
            item.setText(2, f"{idx:02X}")

            self._plugins_tree.addTopLevelItem(item)

    def _on_exe_selected(self, index: int) -> None:
        """Handle executable selection from the menu."""
        self._selected_exe_index = index
        name = self._executables[index]["name"]
        self._start_btn.setToolTip(tr("game_panel.start_with_name", name=name))

    def _on_start_clicked(self) -> None:
        """Start the currently selected executable (deploy already happened)."""
        idx = self._selected_exe_index
        if idx < 0 or idx >= len(self._executables):
            return

        exe = self._executables[idx]
        binary = exe.get("binary", "")
        if not binary:
            return

        plugin = self._current_plugin
        is_steam = (
            plugin
            and hasattr(plugin, "GameSteamId")
            and plugin.GameSteamId
            and hasattr(plugin, "detectedStore")
            and plugin.detectedStore() == "steam"
        )

        if is_steam:
            is_main_binary = (
                hasattr(plugin, "GameBinary") and binary == plugin.GameBinary
            )
            if is_main_binary:
                # Main game binary -> launch via steam -applaunch
                self._launch_via_steam(plugin)
            else:
                # Non-primary executable (F4SE, REDmod, etc.) -> launch via proton run
                self._launch_via_proton(plugin, binary)
            return

        # Non-Steam game: direct start (GOG, Epic, etc.)
        game_path = self._current_game_path
        if game_path is None:
            QMessageBox.warning(
                self, tr("game_panel.start"),
                tr("game_panel.game_dir_not_found"),
            )
            return

        binary_path = game_path / binary
        if not binary_path.exists():
            QMessageBox.warning(
                self, tr("game_panel.start"),
                tr("game_panel.exe_not_found", path=str(binary_path)),
            )
            return

        working_dir = str(binary_path.parent)
        self.start_requested.emit(str(binary_path), working_dir)

    def _launch_via_steam(self, plugin) -> None:
        """Launch the main game binary via steam -applaunch."""
        import shutil
        steam_bin = shutil.which("steam")
        if not steam_bin:
            QMessageBox.warning(
                self, tr("game_panel.start"),
                tr("game_panel.steam_not_found"),
            )
            return

        from PySide6.QtCore import QProcess
        steam_id = plugin.GameSteamId
        if isinstance(steam_id, list):
            steam_id = steam_id[0]
        args = ["-applaunch", str(steam_id)]
        if hasattr(plugin, "GameLaunchArgs"):
            args.extend(plugin.GameLaunchArgs)
        success, pid = QProcess.startDetached(steam_bin, args)
        if not success:
            QMessageBox.warning(
                self, tr("game_panel.start"),
                tr("game_panel.steam_not_found"),
            )

    def _launch_via_proton(self, plugin, binary: str) -> None:
        """Launch a non-primary executable via Proton for Steam games.

        Uses ``proton run <exe>`` with the correct environment variables
        (STEAM_COMPAT_DATA_PATH, STEAM_COMPAT_CLIENT_INSTALL_PATH) so
        that tools like F4SE, REDmod, DX12 variants, etc. run inside
        the game's Proton prefix.
        """
        game_path = self._current_game_path
        if game_path is None:
            QMessageBox.warning(
                self, tr("game_panel.start"),
                tr("game_panel.game_dir_not_found"),
            )
            return

        binary_path = game_path / binary
        if not binary_path.exists():
            QMessageBox.warning(
                self, tr("game_panel.start"),
                tr("game_panel.exe_not_found", path=str(binary_path)),
            )
            return

        # Find the Proton runner for this game
        proton_info = plugin.findProtonRun()
        if proton_info is None:
            QMessageBox.warning(
                self, tr("game_panel.start"),
                tr("game_panel.proton_not_found"),
            )
            return

        proton_script, compat_data, steam_root = proton_info

        # Build environment for proton run
        env = os.environ.copy()
        env["STEAM_COMPAT_DATA_PATH"] = str(compat_data)
        env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(steam_root)

        # Set SteamAppId so Proton knows which game context to use
        steam_id = plugin.GameSteamId
        if isinstance(steam_id, list):
            steam_id = steam_id[0]
        env["SteamAppId"] = str(steam_id)
        env["SteamGameId"] = str(steam_id)

        working_dir = str(binary_path.parent)

        try:
            subprocess.Popen(
                [str(proton_script), "run", str(binary_path)],
                cwd=working_dir,
                env=env,
            )
        except OSError as exc:
            QMessageBox.warning(
                self, tr("game_panel.start"),
                tr("game_panel.proton_launch_failed", error=str(exc)),
            )

    def _populate_data_tree(self, game_path: Path | None) -> None:
        """Scan game_path and show top-level entries in the data tree."""
        self._data_tree.clear()

        if game_path is None or not game_path.is_dir():
            item = QTreeWidgetItem(self._data_tree, [tr("game_panel.dir_not_available"), "", "", "", ""])
            return

        try:
            entries = sorted(game_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            item = QTreeWidgetItem(self._data_tree, [tr("game_panel.read_error"), "", "", "", ""])
            return

        for entry in entries:
            try:
                if entry.is_dir():
                    QTreeWidgetItem(self._data_tree, [entry.name, "", tr("game_panel.folder"), "-", "-"])
                else:
                    stat = entry.stat()
                    size = self._format_size(stat.st_size)
                    QTreeWidgetItem(self._data_tree, [entry.name, tr("game_panel.unmanaged"), "", size, ""])
            except OSError:
                continue

    def _on_reload_data(self) -> None:
        """Reload the data tree from the current game path."""
        self._populate_data_tree(self._current_game_path)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format file size in human-readable form."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        if size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    # ── Downloads-Tab ──────────────────────────────────────────────

    def set_instance_path(self, instance_path: Path, profile_name: str = "Default") -> None:
        """Set instance path and initialize the deployer."""
        self._instance_path = instance_path
        self._current_profile_name = profile_name
        direct_patterns = getattr(self._current_plugin, "GameDirectInstallMods", []) if self._current_plugin else []
        data_path = getattr(self._current_plugin, "GameDataPath", "") if self._current_plugin else ""
        nest = getattr(self._current_plugin, "GameNestModsUnderName", False) if self._current_plugin else False
        lml_path = getattr(self._current_plugin, "GameLMLPath", "") if self._current_plugin else ""
        multi_routes = getattr(self._current_plugin, "GameMultiFolderRoutes", {}) if self._current_plugin else {}
        if self._current_game_path and instance_path:
            self._deployer = ModDeployer(instance_path, self._current_game_path, direct_patterns, profile_name=profile_name, data_path=data_path, nest_under_mod_name=nest, lml_path=lml_path, multi_folder_routes=multi_routes)
        else:
            self._deployer = None

    def set_downloads_path(self, downloads_path: Path, mods_path: Path) -> None:
        """Set paths and populate the downloads table."""
        self._downloads_path = downloads_path
        self._mods_path = mods_path
        self.refresh_downloads()

    def _is_separator_row(self, row: int) -> bool:
        """Check if a row is a folder separator."""
        item = self._dl_table.item(row, 0)
        return bool(item and item.data(Qt.ItemDataRole.UserRole + 2))

    def _scan_archives(self, folder: Path) -> list[tuple[str, int, float, Path, bool, bool, str]]:
        """Scan a folder for archives and return metadata tuples."""
        results = []
        for entry in folder.rglob("*"):
            if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    stat = entry.stat()
                    is_hidden = False
                    meta_installed = False
                    meta_install_file = ""
                    meta = Path(str(entry) + ".meta")
                    if meta.is_file():
                        cp = configparser.ConfigParser()
                        cp.optionxform = str
                        try:
                            cp.read(str(meta), encoding="utf-8")
                            is_hidden = cp.getboolean("General", "removed", fallback=False)
                            meta_installed = cp.getboolean("General", "installed", fallback=False)
                            meta_install_file = cp.get("General", "installationFile", fallback="")
                        except Exception:
                            pass
                    results.append((entry.name, stat.st_size, stat.st_mtime, entry, is_hidden, meta_installed, meta_install_file))
                except OSError:
                    continue
        results.sort(key=lambda t: t[0].lower())
        return results

    def refresh_downloads(self) -> None:
        """Scan .downloads/ recursively (1 level deep) and populate the table with folder separators."""
        self._dl_table.setRowCount(0)
        self._dl_archives.clear()

        if not self._downloads_path or not self._downloads_path.is_dir():
            return

        import re
        from datetime import datetime

        # 1. Root-Dateien sammeln (direkte Kinder, keine Rekursion)
        root_archives = []
        for entry in self._downloads_path.iterdir():
            if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    stat = entry.stat()
                    is_hidden = False
                    meta_installed = False
                    meta_install_file = ""
                    meta = Path(str(entry) + ".meta")
                    if meta.is_file():
                        cp = configparser.ConfigParser()
                        cp.optionxform = str
                        try:
                            cp.read(str(meta), encoding="utf-8")
                            is_hidden = cp.getboolean("General", "removed", fallback=False)
                            meta_installed = cp.getboolean("General", "installed", fallback=False)
                            meta_install_file = cp.get("General", "installationFile", fallback="")
                        except Exception:
                            pass
                    root_archives.append((entry.name, stat.st_size, stat.st_mtime, entry, is_hidden, meta_installed, meta_install_file))
                except OSError:
                    continue
        root_archives.sort(key=lambda t: t[0].lower())

        # 2. Unterordner sammeln (1 Ebene), Archive darin rekursiv
        subfolders: list[tuple[str, list]] = []
        for entry in sorted(self._downloads_path.iterdir(), key=lambda e: e.name.lower()):
            if entry.is_dir():
                folder_archives = self._scan_archives(entry)
                if folder_archives:  # Leere Ordner ignorieren
                    subfolders.append((entry.name, folder_archives))

        # 3. Gesamtzahl Zeilen berechnen (Root + pro Ordner: 1 Separator + Archive)
        total_rows = len(root_archives)
        for folder_name, folder_archives in subfolders:
            total_rows += 1 + len(folder_archives)  # 1 Separator + Archive

        # Build set of installed mod folder names for status check
        installed_names: set[str] = set()
        if self._mods_path and self._mods_path.is_dir():
            installed_names = {d.name.lower() for d in self._mods_path.iterdir() if d.is_dir()}

        s = QSettings(
            str(Path.home() / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf"),
            QSettings.Format.IniFormat,
        )

        self._dl_table.setSortingEnabled(False)
        self._dl_table.setRowCount(total_rows)

        row = 0

        def _insert_archive_row(row_idx, name, size, mtime, path, is_hidden, meta_installed, meta_install_file, folder_name_for_filter=""):
            """Insert a single archive row into the table."""
            self._dl_archives.append(path)

            # Name — store archive path in UserRole
            item_name = QTableWidgetItem(name)
            item_name.setData(Qt.ItemDataRole.UserRole, str(path))
            # Ordnername für Filter speichern (UserRole + 3)
            if folder_name_for_filter:
                item_name.setData(Qt.ItemDataRole.UserRole + 3, folder_name_for_filter)
            self._dl_table.setItem(row_idx, 0, item_name)

            # Size
            item_size = _NumericSortItem()
            item_size.setText(self._format_size(size))
            item_size.setData(Qt.ItemDataRole.UserRole, size)
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._dl_table.setItem(row_idx, 1, item_size)

            # Status (MO2-Muster)
            if meta_installed:
                is_installed = True
            elif meta_install_file:
                is_installed = meta_install_file.lower() in installed_names
            else:
                stem = path.stem
                clean = re.sub(r"-\d+(-\d+)*$", "", stem).strip()
                clean = clean.replace("_", " ")
                clean = clean.strip(". ")
                clean = re.sub(r"\s*\(\d+\)$", "", clean)
                clean = re.sub(r"\.zip$", "", clean, flags=re.I)
                is_installed = clean.lower() in installed_names or stem.lower() in installed_names
            status_text = tr("game_panel.installed") if is_installed else tr("game_panel.not_installed")
            item_status = QTableWidgetItem(status_text)
            if is_installed:
                item_status.setForeground(QColor("#4CAF50"))
            self._dl_table.setItem(row_idx, 2, item_status)

            # Auto-hide installed
            if is_installed and not is_hidden:
                hide_after = s.value("Interface/hide_downloads_after_install", False, type=bool)
                if hide_after and not self._show_hidden:
                    self._dl_table.setRowHidden(row_idx, True)

            # Date
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            self._dl_table.setItem(row_idx, 3, QTableWidgetItem(date_str))

            # Hidden: grey text + hide row
            if is_hidden:
                grey = QColor("#808080")
                for col in range(4):
                    ci = self._dl_table.item(row_idx, col)
                    if ci:
                        ci.setForeground(grey)
                if not self._show_hidden:
                    self._dl_table.setRowHidden(row_idx, True)

            # Base-Hidden-Flag für Text-Filter-Interop
            item_name.setData(Qt.ItemDataRole.UserRole + 1, self._dl_table.isRowHidden(row_idx))

        # 4. Root-Archive einfügen (ohne Separator)
        for (name, size, mtime, path, is_hidden, meta_installed, meta_install_file) in root_archives:
            _insert_archive_row(row, name, size, mtime, path, is_hidden, meta_installed, meta_install_file)
            row += 1

        # 5. Pro Unterordner: Separator + Archive
        for folder_name, folder_archives in subfolders:
            # Separator-Zeile — Pfeil je nach Collapse-State
            collapsed = folder_name in self._dl_collapsed
            count = len(folder_archives)
            if collapsed:
                sep_text = f"\u25B6 \U0001F4C1 {folder_name} ({count})"
            else:
                sep_text = f"\u25BC \U0001F4C1 {folder_name}"
            sep_item = QTableWidgetItem(sep_text)
            sep_item.setData(Qt.ItemDataRole.UserRole + 2, True)  # Separator-Marker
            sep_item.setData(Qt.ItemDataRole.UserRole + 3, folder_name)  # Ordnername für Collapse
            sep_item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # Klickbar aber nicht selektierbar/editierbar
            sep_item.setBackground(QColor("#1a2a3a"))
            sep_item.setForeground(QColor("#FFFFFF"))
            font = sep_item.font()
            font.setBold(True)
            sep_item.setFont(font)
            self._dl_table.setItem(row, 0, sep_item)
            # Leere Items für restliche Spalten mit gleichem Hintergrund
            for col in range(1, 4):
                empty = QTableWidgetItem()
                empty.setFlags(Qt.ItemFlag.NoItemFlags)
                empty.setBackground(QColor("#1a2a3a"))
                self._dl_table.setItem(row, col, empty)
            self._dl_table.setSpan(row, 0, 1, 4)
            row += 1

            # Archive in diesem Ordner
            for (name, size, mtime, path, is_hidden, meta_installed, meta_install_file) in folder_archives:
                _insert_archive_row(row, name, size, mtime, path, is_hidden, meta_installed, meta_install_file, folder_name)
                row += 1

        # Sorting bleibt deaktiviert — manuelle Ordnung durch Ordner-Gruppen
        # self._dl_table.setSortingEnabled(True)

        # Setting: show/hide meta columns (Size + Date)
        show_meta = s.value("Interface/show_meta_info", False, type=bool)
        self._dl_table.setColumnHidden(1, not show_meta)   # Size
        self._dl_table.setColumnHidden(3, not show_meta)   # Date

        # Setting: compact list (smaller row height)
        if s.value("Interface/compact_list", False, type=bool):
            self._dl_table.verticalHeader().setDefaultSectionSize(24)
        else:
            self._dl_table.verticalHeader().setDefaultSectionSize(46)

        # Text-Filter erneut anwenden nach Tabellen-Rebuild
        self._on_dl_filter_changed(self._dl_filter_edit.text())
        # Collapse-State anwenden (bleibt über Refresh erhalten)
        self._apply_dl_collapse()

    def _get_dl_archive_path(self, row: int) -> str | None:
        """Get archive path from the name column's UserRole data."""
        item = self._dl_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_dl_cell_clicked(self, row: int, col: int) -> None:
        """Toggle collapse/expand when clicking a separator row."""
        if not self._is_separator_row(row):
            return
        item = self._dl_table.item(row, 0)
        if item is None:
            return
        folder_name = item.data(Qt.ItemDataRole.UserRole + 3)
        if not folder_name:
            return

        if folder_name in self._dl_collapsed:
            self._dl_collapsed.discard(folder_name)
        else:
            self._dl_collapsed.add(folder_name)

        self._apply_dl_collapse()

    def _apply_dl_collapse(self) -> None:
        """Zentrale Visibility-Steuerung: base-hidden, collapse, filter.
        Eine Zeile ist nur sichtbar wenn alle 3 Ebenen 'sichtbar' sagen.
        """
        needle = self._dl_filter_edit.text().strip().lower()
        current_folder = ""
        current_collapsed = False

        for row in range(self._dl_table.rowCount()):
            item = self._dl_table.item(row, 0)
            if item is None:
                continue

            if item.data(Qt.ItemDataRole.UserRole + 2):
                # Separator-Zeile — State + Text aktualisieren
                folder_name = item.data(Qt.ItemDataRole.UserRole + 3) or ""
                current_folder = folder_name
                current_collapsed = folder_name in self._dl_collapsed

                # Kinder zählen
                child_count = 0
                for peek in range(row + 1, self._dl_table.rowCount()):
                    peek_item = self._dl_table.item(peek, 0)
                    if peek_item and peek_item.data(Qt.ItemDataRole.UserRole + 2):
                        break
                    child_count += 1

                if current_collapsed:
                    item.setText(f"\u25B6 \U0001F4C1 {folder_name} ({child_count})")
                else:
                    item.setText(f"\u25BC \U0001F4C1 {folder_name}")

                # Separator sichtbar wenn ≥1 Kind nicht base-hidden (+ Filter-Match)
                has_any_child = False
                for peek in range(row + 1, self._dl_table.rowCount()):
                    peek_item = self._dl_table.item(peek, 0)
                    if peek_item is None:
                        continue
                    if peek_item.data(Qt.ItemDataRole.UserRole + 2):
                        break
                    if peek_item.data(Qt.ItemDataRole.UserRole + 1):
                        continue  # base-hidden
                    if needle:
                        name = peek_item.text().lower()
                        folder = (peek_item.data(Qt.ItemDataRole.UserRole + 3) or "").lower()
                        if needle in name or (folder and needle in folder):
                            has_any_child = True
                            break
                    else:
                        has_any_child = True
                        break
                self._dl_table.setRowHidden(row, not has_any_child)
                continue

            # ── Archiv-Zeile: 3 Ebenen prüfen ──

            # Ebene 1: Base-hidden (meta-hidden, auto-hide installed)
            if item.data(Qt.ItemDataRole.UserRole + 1):
                continue  # bleibt versteckt, nicht anfassen

            # Ebene 2: Collapse (nur wenn kein Filter aktiv)
            if current_collapsed and not needle:
                self._dl_table.setRowHidden(row, True)
                continue

            # Ebene 3: Filter
            if needle:
                name = item.text().lower()
                folder = (item.data(Qt.ItemDataRole.UserRole + 3) or "").lower()
                visible = needle in name or (folder and needle in folder)
                self._dl_table.setRowHidden(row, not visible)
            else:
                # Nicht base-hidden, nicht collapsed, kein Filter → SICHTBAR
                self._dl_table.setRowHidden(row, False)

    def _on_dl_double_click(self, row: int, _col: int) -> None:
        """Double-click on a download row → install it."""
        if self._is_separator_row(row):
            return
        path = self._get_dl_archive_path(row)
        if path:
            self.install_requested.emit([path])

    def _read_meta_mod_id(self, archive_path: str) -> str | None:
        """Read modID from the .meta file next to an archive."""
        meta = Path(archive_path + ".meta")
        if not meta.is_file():
            return None
        cp = configparser.ConfigParser()
        try:
            cp.read(str(meta), encoding="utf-8")
        except Exception:
            return None
        mod_id = cp.get("General", "modID", fallback=None)
        if mod_id and mod_id.strip():
            return mod_id.strip()
        return None

    def _get_meta_path(self, archive_path: str) -> Path | None:
        """Return the .meta file path if it exists."""
        meta = Path(archive_path + ".meta")
        return meta if meta.is_file() else None

    def _bulk_delete_by_status(self, filter_status: str | None) -> None:
        """Delete archives filtered by status column. None = all."""
        installed_text = tr("game_panel.installed")
        not_installed_text = tr("game_panel.not_installed")
        paths: list[str] = []
        for row in range(self._dl_table.rowCount()):
            if self._is_separator_row(row):
                continue
            if filter_status is not None:
                status_item = self._dl_table.item(row, 2)
                if not status_item or status_item.text() != filter_status:
                    continue
            p = self._get_dl_archive_path(row)
            if p:
                paths.append(p)
        if not paths:
            return
        count = len(paths)
        if filter_status == installed_text:
            msg = tr("game_panel.delete_confirm_installed", count=count)
        elif filter_status == not_installed_text:
            msg = tr("game_panel.delete_confirm_uninstalled", count=count)
        else:
            msg = tr("game_panel.delete_confirm_all", count=count)
        answer = QMessageBox.question(
            self, tr("game_panel.delete_confirm_title"), msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            for p in paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
                # Also remove .meta file
                meta = p + ".meta"
                try:
                    os.remove(meta)
                except OSError:
                    pass
            self.refresh_downloads()

    # ── Hide/Un-Hide (MO2 style) ─────────────────────────────────

    def _on_dl_filter_changed(self, text: str) -> None:
        """Filter-Änderung → _apply_dl_collapse() steuert alle Visibility-Ebenen."""
        self._apply_dl_collapse()

    def _on_toggle_hidden(self, state: int) -> None:
        """Toggle visibility of hidden downloads."""
        self._show_hidden = bool(state)
        self.refresh_downloads()

    def _is_row_hidden(self, row: int) -> bool:
        """Check if a download row is marked as hidden in its .meta file."""
        path = self._get_dl_archive_path(row)
        if not path:
            return False
        meta = Path(path + ".meta")
        if not meta.is_file():
            return False
        cp = configparser.ConfigParser()
        try:
            cp.read(str(meta), encoding="utf-8")
            return cp.getboolean("General", "removed", fallback=False)
        except Exception:
            return False

    def _set_hidden(self, row: int, hidden: bool) -> None:
        """Write removed=true/false to .meta file and update row visibility."""
        path = self._get_dl_archive_path(row)
        if not path:
            return
        meta_path = Path(path + ".meta")
        cp = configparser.ConfigParser()
        cp.optionxform = str  # CamelCase-Keys beibehalten (MO2-Kompatibilitaet)
        if meta_path.is_file():
            try:
                cp.read(str(meta_path), encoding="utf-8")
            except Exception:
                pass
        if not cp.has_section("General"):
            cp.add_section("General")
        cp.set("General", "removed", str(hidden).lower())
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                cp.write(f)
        except OSError:
            pass

    def _bulk_hide_by_status(self, filter_status: str | None, hidden: bool) -> None:
        """Batch hide/unhide downloads filtered by status column."""
        for row in range(self._dl_table.rowCount()):
            if self._is_separator_row(row):
                continue
            if filter_status is not None:
                status_item = self._dl_table.item(row, 2)
                if not status_item or status_item.text() != filter_status:
                    continue
            self._set_hidden(row, hidden)
        self.refresh_downloads()

    def _on_dl_context_menu(self, pos) -> None:
        """Right-click context menu on downloads table (MO2 style)."""
        # Collect all selected archive paths (Separator-Zeilen filtern)
        selected_rows = sorted({idx.row() for idx in self._dl_table.selectedIndexes()})
        selected_rows = [r for r in selected_rows if not self._is_separator_row(r)]
        paths: list[str] = []
        for r in selected_rows:
            p = self._get_dl_archive_path(r)
            if p:
                paths.append(p)
        if not paths:
            return

        first = paths[0]
        meta_path = self._get_meta_path(first)
        mod_id = self._read_meta_mod_id(first)

        menu = QMenu(self)

        # ── Group 1: Install ──
        act_install = menu.addAction(tr("game_panel.install"))

        menu.addSeparator()

        # ── Group 2: Open / Nexus ──
        act_nexus = menu.addAction(tr("game_panel.visit_nexus"))
        act_nexus.setEnabled(mod_id is not None)
        act_open = menu.addAction(tr("game_panel.open_file"))
        act_meta = menu.addAction(tr("game_panel.open_meta"))
        act_meta.setEnabled(meta_path is not None)

        menu.addSeparator()

        # ── Group 3: Show in folder ──
        act_show = menu.addAction(tr("game_panel.show_in_downloads"))

        menu.addSeparator()

        # ── Group 4: Delete / Hide/Un-Hide ──
        act_delete = menu.addAction(tr("game_panel.delete"))
        first_hidden = self._is_row_hidden(selected_rows[0])
        act_hide = act_unhide = None
        if first_hidden:
            act_unhide = menu.addAction(tr("game_panel.unhide"))
        else:
            act_hide = menu.addAction(tr("game_panel.hide"))

        menu.addSeparator()

        # ── Group 5: Bulk delete ──
        act_del_installed = menu.addAction(tr("game_panel.delete_installed"))
        act_del_uninstalled = menu.addAction(tr("game_panel.delete_uninstalled"))
        act_del_all = menu.addAction(tr("game_panel.delete_all"))

        menu.addSeparator()

        # ── Group 6: Bulk hide/unhide ──
        act_hide_installed = act_hide_uninstalled = act_hide_all = None
        act_unhide_all = None
        if self._show_hidden:
            act_unhide_all = menu.addAction(tr("game_panel.unhide_all"))
        act_hide_installed = menu.addAction(tr("game_panel.hide_installed"))
        act_hide_uninstalled = menu.addAction(tr("game_panel.hide_uninstalled"))
        act_hide_all = menu.addAction(tr("game_panel.hide_all"))

        chosen = menu.exec(self._dl_table.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen == act_install:
            self.install_requested.emit(paths)
        elif chosen == act_nexus:
            game = self._current_short_name or "site"
            QDesktopServices.openUrl(
                QUrl(f"https://www.nexusmods.com/{game}/mods/{mod_id}"))
        elif chosen == act_open:
            subprocess.Popen(["xdg-open", first])
        elif chosen == act_meta:
            subprocess.Popen(["xdg-open", str(meta_path)])
        elif chosen == act_show:
            subprocess.Popen(["xdg-open", str(Path(first).parent)])
        elif chosen == act_delete:
            count = len(paths)
            if count == 1:
                msg = tr("game_panel.delete_confirm_single", name=Path(first).name)
            else:
                msg = tr("game_panel.delete_confirm_multi", count=count)
            answer = QMessageBox.question(
                self, tr("game_panel.delete_confirm_title"), msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                for p in paths:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                    # Also remove .meta file
                    meta = p + ".meta"
                    try:
                        os.remove(meta)
                    except OSError:
                        pass
                self.refresh_downloads()
        elif chosen == act_hide:
            for r in selected_rows:
                self._set_hidden(r, True)
            self.refresh_downloads()
        elif chosen == act_unhide:
            for r in selected_rows:
                self._set_hidden(r, False)
            self.refresh_downloads()
        elif chosen == act_del_installed:
            self._bulk_delete_by_status(tr("game_panel.installed"))
        elif chosen == act_del_uninstalled:
            self._bulk_delete_by_status(tr("game_panel.not_installed"))
        elif chosen == act_del_all:
            self._bulk_delete_by_status(None)
        elif chosen == act_hide_installed:
            self._bulk_hide_by_status(tr("game_panel.installed"), True)
        elif chosen == act_hide_uninstalled:
            self._bulk_hide_by_status(tr("game_panel.not_installed"), True)
        elif chosen == act_hide_all:
            self._bulk_hide_by_status(None, True)
        elif chosen == act_unhide_all:
            self._bulk_hide_by_status(None, False)

    # ── Download manager integration ──────────────────────────────────

    def download_manager(self) -> DownloadManager:
        """Return the DownloadManager instance."""
        return self._download_manager

    def _on_dm_started(self, download_id: int) -> None:
        """Insert a new row at the top of the downloads table for an active download."""
        task = self._download_manager.get_task(download_id)
        if not task:
            return

        self._dl_table.setSortingEnabled(False)
        row = 0
        self._dl_table.insertRow(row)

        item_name = QTableWidgetItem(task.file_name)
        item_name.setData(Qt.ItemDataRole.UserRole, str(task.save_path))
        self._dl_table.setItem(row, 0, item_name)

        item_size = QTableWidgetItem("—")
        item_size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._dl_table.setItem(row, 1, item_size)

        item_status = QTableWidgetItem(tr("game_panel.downloading"))
        item_status.setForeground(QColor("#42A5F5"))
        self._dl_table.setItem(row, 2, item_status)

        self._dl_table.setItem(row, 3, QTableWidgetItem("—"))

        # Shift existing active row mappings down
        new_map = {}
        for did, r in self._active_dl_rows.items():
            new_map[did] = r + 1
        self._active_dl_rows = new_map
        self._active_dl_rows[download_id] = row
        self._dl_table.setSortingEnabled(True)

    def _on_dm_progress(self, download_id: int, percent: float, speed_str: str) -> None:
        """Update progress for an active download row."""
        row = self._active_dl_rows.get(download_id)
        if row is None:
            return
        task = self._download_manager.get_task(download_id)
        if not task:
            return

        status_item = self._dl_table.item(row, 2)
        if status_item:
            status_item.setText(f"{percent:.0f}% — {speed_str}")

        size_item = self._dl_table.item(row, 1)
        if size_item and task.bytes_total > 0:
            size_item.setText(self._format_size(task.bytes_total))

    def _on_dm_finished(self, download_id: int, save_path: str) -> None:
        """Mark a download as finished and refresh the downloads table."""
        row = self._active_dl_rows.pop(download_id, None)
        if row is not None:
            status_item = self._dl_table.item(row, 2)
            if status_item:
                status_item.setText(tr("game_panel.not_installed"))
                status_item.setForeground(QColor("#FFFFFF"))

            # Update date column
            from datetime import datetime
            date_item = self._dl_table.item(row, 3)
            if date_item:
                date_item.setText(datetime.now().strftime("%Y-%m-%d %H:%M"))

    def _on_dm_error(self, download_id: int, message: str) -> None:
        """Mark a download as failed."""
        row = self._active_dl_rows.pop(download_id, None)
        if row is not None:
            status_item = self._dl_table.item(row, 2)
            if status_item:
                status_item.setText(tr("game_panel.error_prefix", message=message))
                status_item.setForeground(QColor("#F44336"))
