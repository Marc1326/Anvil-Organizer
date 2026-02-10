"""Game-Panel — MO2-Kopie: großes Game-Icon, Tabs, Downloads mit Neu laden."""

from __future__ import annotations

import configparser
import os
import subprocess
from pathlib import Path

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
from PySide6.QtCore import Qt, QSize, QPoint, Signal, QUrl, QMimeData

from anvil.core.mod_installer import SUPPORTED_EXTENSIONS
from anvil.core.mod_deployer import ModDeployer


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


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
        _exec_icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "styles", "icons", "executables.svg")
        if os.path.exists(_exec_icon):
            link_btn.setIcon(QIcon(_exec_icon))
        link_btn.setIconSize(QSize(20, 20))
        link_btn.setToolTip("Verknüpfung")
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

        self._game_label = QLabel("Kein Spiel ausgewählt")
        self._game_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(self._game_label)

        # Start-Button
        self._start_btn = QPushButton()
        self._start_btn.setObjectName("startButton")
        _play_icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "styles", "icons", "files", "play.png")
        if os.path.exists(_play_icon):
            self._start_btn.setIcon(QIcon(_play_icon))
            self._start_btn.setIconSize(QSize(24, 24))
        self._start_btn.setMinimumWidth(140)
        self._start_btn.setFixedHeight(36)
        self._start_btn.setToolTip("Starten")
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

        # ── Daten-Tab ─────────────────────────────────────────────────
        data = QWidget()
        data_layout = QVBoxLayout(data)
        data_reload_btn = QPushButton("Neu laden")
        _refresh_icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "styles", "icons", "refresh.svg")
        if os.path.exists(_refresh_icon):
            data_reload_btn.setIcon(QIcon(_refresh_icon))
        data_reload_btn.setIconSize(QSize(20, 20))
        data_reload_btn.clicked.connect(self._on_reload_data)
        data_layout.addWidget(data_reload_btn)
        self._data_tree = QTreeWidget()
        self._data_tree.setColumnCount(5)
        self._data_tree.setHeaderLabels(["Name", "Mod", "Type", "Größe", "Datum modifiziert"])
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
        data_layout.addWidget(self._data_tree)
        data_bar = QHBoxLayout()
        data_bar.addWidget(QCheckBox("Nur Konflikte"))
        data_bar.addWidget(QCheckBox("Archive"))
        data_filter_edit = QLineEdit()
        data_filter_edit.setPlaceholderText("Filter")
        data_bar.addWidget(data_filter_edit)
        data_bar.addStretch()
        data_layout.addLayout(data_bar)
        tabs.addTab(data, "Daten")

        # ── Spielstände-Tab ───────────────────────────────────────────
        saves = QWidget()
        saves_layout = QVBoxLayout(saves)
        self._saves_tree = QTreeWidget()
        self._saves_tree.setColumnCount(2)
        self._saves_tree.setHeaderLabels(["Name", "Datei"])
        saves_header = self._saves_tree.header()
        saves_header.setStretchLastSection(False)
        saves_header.setCascadingSectionResizes(True)
        saves_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        saves_layout.addWidget(self._saves_tree)
        tabs.addTab(saves, "Spielstände")

        # ── Downloads-Tab ─────────────────────────────────────────────
        downloads = QWidget()
        dl_layout = QVBoxLayout(downloads)
        reload_btn = QPushButton("Neu laden")
        _refresh_icon2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "styles", "icons", "refresh.svg")
        if os.path.exists(_refresh_icon2):
            reload_btn.setIcon(QIcon(_refresh_icon2))
        reload_btn.setIconSize(QSize(20, 20))
        reload_btn.clicked.connect(self.refresh_downloads)
        dl_layout.addWidget(reload_btn)
        self._dl_table = _DraggableDownloadTable()
        self._dl_table.setColumnCount(4)
        self._dl_table.setHorizontalHeaderLabels(["Name", "Größe", "Status", "Dateizeit"])
        dl_header = self._dl_table.horizontalHeader()
        dl_header.setStretchLastSection(False)
        dl_header.setCascadingSectionResizes(True)
        dl_header.setMinimumSectionSize(40)
        dl_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._dl_table.setColumnWidth(0, 250)
        self._dl_table.setColumnWidth(1, 90)
        self._dl_table.setColumnWidth(2, 120)
        self._dl_table.setColumnWidth(3, 140)
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
        self._dl_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._dl_table.customContextMenuRequested.connect(self._on_dl_context_menu)
        dl_layout.addWidget(self._dl_table)
        cb = QCheckBox("versteckte Dateien")
        cb.stateChanged.connect(lambda s: _todo("versteckte Dateien")())
        dl_layout.addWidget(cb)
        fe = QLineEdit()
        fe.setPlaceholderText("Filter")
        fe.textChanged.connect(lambda t: _todo("Filter Downloads")())
        dl_layout.addWidget(fe)
        tabs.addTab(downloads, "Downloads")

        layout.addWidget(tabs)

        # Track current state for reload / icon updates
        self._current_game_path: Path | None = None
        self._current_short_name: str = ""
        self._current_plugin = None
        self._icon_manager = None
        self._downloads_path: Path | None = None
        self._mods_path: Path | None = None
        self._instance_path: Path | None = None
        self._deployer: ModDeployer | None = None
        # Map row index → archive Path for installation
        self._dl_archives: list[Path] = []

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
        if self._instance_path and game_path:
            self._deployer = ModDeployer(self._instance_path, game_path)

        # Update label
        self._game_label.setText(game_name or "Kein Spiel ausgewählt")

        # Update game button icon (banner or placeholder)
        self._update_game_button_icon(game_name)

        # Rebuild executables menu (in game button)
        self._rebuild_executables_menu(game_plugin)

        # Update data tree with real directory contents
        self._populate_data_tree(game_path)

        # Downloads are populated via set_downloads_path() from MainWindow

    # ── Internal helpers ──────────────────────────────────────────────

    def _update_game_button_icon(self, game_name: str) -> None:
        """Set the game button to the cached banner or a placeholder."""
        size = 140
        banner = None
        if self._icon_manager and self._current_short_name:
            banner = self._icon_manager.get_game_banner(self._current_short_name)

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
        edit_action = self._exe_menu.addAction("<Bearbeiten...>")
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
            if game_name:
                skip_action = self._exe_menu.addAction(cover_icon, f"{game_name} - skip REDmod deploy")
                skip_action.setEnabled(False)
                deploy_action = self._exe_menu.addAction("Manually deploy REDmod")
                deploy_action.setEnabled(False)

            # Explore Virtual Folder
            self._exe_menu.addSeparator()
            explore_action = self._exe_menu.addAction(
                self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon),
                "Explore Virtual Folder",
            )
            explore_action.triggered.connect(self._on_explore_virtual_folder)

        # Select first executable by default
        if self._executables:
            self._selected_exe_index = 0
            self._start_btn.setToolTip(f"Starten: {self._executables[0]['name']}")

    def _get_small_game_icon(self) -> QIcon:
        """Return small (24x24) game banner icon (cover art), or placeholder."""
        if self._icon_manager and self._current_short_name:
            pix = self._icon_manager.get_game_banner(self._current_short_name)
            if pix is not None:
                return QIcon(pix.scaled(
                    QSize(24, 24),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
        return self._placeholder_icon()

    def _get_small_redmod_icon(self) -> QIcon:
        """Return small (24x24) game icon (game.png / Red Bird), or placeholder."""
        if self._icon_manager and self._current_short_name:
            pix = self._icon_manager.get_game_icon(self._current_short_name)
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

    def silent_purge(self) -> None:
        """Purge deployed mods silently.  Called automatically by MainWindow."""
        if self._deployer:
            self._deployer.purge()

    def _on_exe_selected(self, index: int) -> None:
        """Handle executable selection from the menu."""
        self._selected_exe_index = index
        name = self._executables[index]["name"]
        self._start_btn.setToolTip(f"Starten: {name}")

    def _on_start_clicked(self) -> None:
        """Start the currently selected executable (deploy already happened)."""
        idx = self._selected_exe_index
        if idx < 0 or idx >= len(self._executables):
            return

        exe = self._executables[idx]
        binary = exe.get("binary", "")
        if not binary:
            return

        # Steam-Launch für das Hauptspiel (erster Eintrag mit SteamId)
        plugin = self._current_plugin
        if plugin and hasattr(plugin, "GameSteamId") and plugin.GameSteamId:
            # Hauptspiel (GameBinary) → über Steam CLI starten
            if hasattr(plugin, "GameBinary") and binary == plugin.GameBinary:
                import shutil
                steam_bin = shutil.which("steam")
                if steam_bin:
                    from PySide6.QtCore import QProcess
                    args = ["-applaunch", str(plugin.GameSteamId)]
                    if hasattr(plugin, "GameLaunchArgs"):
                        args.extend(plugin.GameLaunchArgs)
                    QProcess.startDetached(steam_bin, args)
                else:
                    QMessageBox.warning(
                        self, "Starten",
                        "Steam wurde nicht im PATH gefunden.\n"
                        "Bitte Steam installieren oder den PATH anpassen.",
                    )
                return

        # Direkter Start für alle anderen Executables
        game_path = self._current_game_path
        if game_path is None:
            QMessageBox.warning(
                self, "Starten",
                "Spielverzeichnis nicht gefunden.",
            )
            return

        binary_path = game_path / binary
        if not binary_path.exists():
            QMessageBox.warning(
                self, "Starten",
                f"Executable nicht gefunden:\n{binary_path}",
            )
            return

        working_dir = str(binary_path.parent)
        self.start_requested.emit(str(binary_path), working_dir)

    def _populate_data_tree(self, game_path: Path | None) -> None:
        """Scan game_path and show top-level entries in the data tree."""
        self._data_tree.clear()

        if game_path is None or not game_path.is_dir():
            item = QTreeWidgetItem(self._data_tree, ["(Spielverzeichnis nicht verfügbar)", "", "", "", ""])
            return

        try:
            entries = sorted(game_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            item = QTreeWidgetItem(self._data_tree, ["(Fehler beim Lesen)", "", "", "", ""])
            return

        for entry in entries:
            try:
                if entry.is_dir():
                    QTreeWidgetItem(self._data_tree, [entry.name, "", "Folder", "-", "-"])
                else:
                    stat = entry.stat()
                    size = self._format_size(stat.st_size)
                    QTreeWidgetItem(self._data_tree, [entry.name, "<Unmanaged>", "", size, ""])
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

    def set_instance_path(self, instance_path: Path) -> None:
        """Set instance path and initialize the deployer."""
        self._instance_path = instance_path
        if self._current_game_path and instance_path:
            self._deployer = ModDeployer(instance_path, self._current_game_path)
        else:
            self._deployer = None

    def set_downloads_path(self, downloads_path: Path, mods_path: Path) -> None:
        """Set paths and populate the downloads table."""
        self._downloads_path = downloads_path
        self._mods_path = mods_path
        self.refresh_downloads()

    def refresh_downloads(self) -> None:
        """Scan .downloads/ and populate the table."""
        self._dl_table.setRowCount(0)
        self._dl_archives.clear()

        if not self._downloads_path or not self._downloads_path.is_dir():
            return

        import re
        from datetime import datetime

        archives: list[tuple[str, int, float, Path]] = []
        for entry in self._downloads_path.iterdir():
            if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    stat = entry.stat()
                    archives.append((entry.name, stat.st_size, stat.st_mtime, entry))
                except OSError:
                    continue

        archives.sort(key=lambda t: t[0].lower())

        # Build set of installed mod folder names for status check
        installed_names: set[str] = set()
        if self._mods_path and self._mods_path.is_dir():
            installed_names = {d.name.lower() for d in self._mods_path.iterdir() if d.is_dir()}

        self._dl_table.setSortingEnabled(False)
        self._dl_table.setRowCount(len(archives))
        for row, (name, size, mtime, path) in enumerate(archives):
            self._dl_archives.append(path)

            # Name — store archive path in UserRole for install after sort
            item_name = QTableWidgetItem(name)
            item_name.setData(Qt.ItemDataRole.UserRole, str(path))
            self._dl_table.setItem(row, 0, item_name)

            # Size — numeric sort via _NumericSortItem
            item_size = _NumericSortItem()
            item_size.setText(self._format_size(size))
            item_size.setData(Qt.ItemDataRole.UserRole, size)
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._dl_table.setItem(row, 1, item_size)

            # Status — check if a mod folder derived from this archive name exists
            stem = path.stem
            # Strip Nexus suffixes like "-12128-1-0-1704653004"
            clean = re.sub(r"-\d+(-\d+)*$", "", stem).strip()
            is_installed = clean.lower() in installed_names or stem.lower() in installed_names
            status_text = "Installiert" if is_installed else "Nicht installiert"
            item_status = QTableWidgetItem(status_text)
            if is_installed:
                item_status.setForeground(QColor("#4CAF50"))
            self._dl_table.setItem(row, 2, item_status)

            # Date
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            self._dl_table.setItem(row, 3, QTableWidgetItem(date_str))

        self._dl_table.setSortingEnabled(True)

    def _get_dl_archive_path(self, row: int) -> str | None:
        """Get archive path from the name column's UserRole data."""
        item = self._dl_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_dl_double_click(self, row: int, _col: int) -> None:
        """Double-click on a download row → install it."""
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
        paths: list[str] = []
        for row in range(self._dl_table.rowCount()):
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
        if filter_status == "Installiert":
            msg = f"{count} installierte(s) Archiv(e) wirklich löschen?"
        elif filter_status == "Nicht installiert":
            msg = f"{count} deinstallierte(s) Archiv(e) wirklich löschen?"
        else:
            msg = f"Alle {count} Archive wirklich löschen?"
        answer = QMessageBox.question(
            self, "Löschen bestätigen", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            for p in paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
            self.refresh_downloads()

    def _on_dl_context_menu(self, pos) -> None:
        """Right-click context menu on downloads table (MO2 style)."""
        # Collect all selected archive paths
        selected_rows = sorted({idx.row() for idx in self._dl_table.selectedIndexes()})
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
        act_install = menu.addAction("Installieren")

        menu.addSeparator()

        # ── Group 2: Open / Nexus ──
        act_nexus = menu.addAction("Auf Nexus besuchen")
        act_nexus.setEnabled(mod_id is not None)
        act_open = menu.addAction("Öffne Datei")
        act_meta = menu.addAction("Öffne Meta Datei")
        act_meta.setEnabled(meta_path is not None)

        menu.addSeparator()

        # ── Group 3: Show in folder ──
        act_show = menu.addAction("Zeige im Downloadverzeichnis")

        menu.addSeparator()

        # ── Group 4: Delete / Hide ──
        act_delete = menu.addAction("Löschen...")
        act_hide = menu.addAction("Verstecken")
        act_hide.setEnabled(False)

        menu.addSeparator()

        # ── Group 5: Bulk delete ──
        act_del_installed = menu.addAction("Lösche installierte Downloads...")
        act_del_uninstalled = menu.addAction("Lösche deinstallierte Downloads")
        act_del_all = menu.addAction("Lösche alle Downloads")

        menu.addSeparator()

        # ── Group 6: Bulk hide (placeholder) ──
        act_hide_installed = menu.addAction("Verstecke Installierte")
        act_hide_installed.setEnabled(False)
        act_hide_uninstalled = menu.addAction("Verstecke Deinstallierte")
        act_hide_uninstalled.setEnabled(False)
        act_hide_all = menu.addAction("Verstecke Alle")
        act_hide_all.setEnabled(False)

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
                msg = f"Archiv \"{Path(first).name}\" wirklich löschen?"
            else:
                msg = f"{count} Archive wirklich löschen?"
            answer = QMessageBox.question(
                self, "Löschen bestätigen", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                for p in paths:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                self.refresh_downloads()
        elif chosen == act_del_installed:
            self._bulk_delete_by_status("Installiert")
        elif chosen == act_del_uninstalled:
            self._bulk_delete_by_status("Nicht installiert")
        elif chosen == act_del_all:
            self._bulk_delete_by_status(None)
