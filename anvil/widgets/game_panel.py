"""Game-Panel — MO2-Kopie: großes Game-Icon, Tabs, Downloads mit Neu laden."""

from __future__ import annotations

import os
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
)

from PySide6.QtGui import QPixmap, QIcon, QColor, QAction, QPainter, QFont
from PySide6.QtCore import Qt, QSize, QPoint, Signal

from anvil.core.mod_installer import SUPPORTED_EXTENSIONS


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


class GamePanel(QWidget):
    install_requested = Signal(list)  # list of archive path strings

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
        link_btn.setIconSize(QSize(24, 24))
        link_btn.setToolTip("Verknüpfung")
        link_btn.clicked.connect(_todo("Verknüpfung"))
        link_btn_row = QHBoxLayout()
        link_btn_row.addStretch()
        link_btn_row.addWidget(link_btn)
        top_layout.addLayout(link_btn_row)

        pix = QPixmap(140, 140)
        pix.fill(QColor("#242424"))
        self._game_btn = QToolButton(self)
        self._game_btn.setIcon(QIcon(pix))
        self._game_btn.setIconSize(pix.size())
        self._game_btn.setFixedSize(140, 140)
        self._game_btn.setStyleSheet(
            "QToolButton { background: #242424; border: 2px solid #3D3D3D; border-radius: 4px; }"
            "QToolButton:hover { background: #2a2a2a; }"
        )
        self._game_menu = QMenu(self)
        self._game_menu.setStyleSheet("QMenu { min-width: 350px; padding: 6px; font-size: 14px; }")
        self._game_menu.addAction(QAction("<Bearbeiten...>", self, triggered=_todo("<Bearbeiten...>")))
        self._game_menu.addSeparator()
        self._game_menu.addAction(QAction("Explore Virtual Folder", self, triggered=_todo("Explore Virtual Folder")))
        self._game_btn.clicked.connect(
            lambda: self._game_menu.exec(
                self._game_btn.mapToGlobal(QPoint(self._game_btn.width() // 2 - self._game_menu.sizeHint().width() // 2, self._game_btn.height()))
            )
        )
        top_layout.addWidget(self._game_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        self._game_label = QLabel("Kein Spiel ausgewählt")
        self._game_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(self._game_label)
        start_btn = QPushButton()
        start_btn.setObjectName("startButton")
        _play_icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "styles", "icons", "files", "play.png")
        if os.path.exists(_play_icon):
            start_btn.setIcon(QIcon(_play_icon))
            start_btn.setIconSize(QSize(24, 24))
        start_btn.setMinimumWidth(140)
        start_btn.setFixedHeight(36)
        start_btn.setToolTip("Starten")
        start_btn.clicked.connect(_todo("Starten"))
        top_layout.addWidget(start_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(top_frame)

        tabs = QTabWidget()
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
        saves_tree = QTreeWidget()
        saves_tree.setColumnCount(2)
        saves_tree.setHeaderLabels(["Name", "Datei"])
        saves_header = saves_tree.header()
        saves_header.setStretchLastSection(False)
        saves_header.setCascadingSectionResizes(True)
        saves_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        saves_layout.addWidget(saves_tree)
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
        self._dl_table = QTableWidget()
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

        # Update label
        self._game_label.setText(game_name or "Kein Spiel ausgewählt")

        # Update game button icon (banner or placeholder)
        self._update_game_button_icon(game_name)

        # Rebuild executables dropdown (with icons)
        self._rebuild_game_menu(game_plugin)

        # Update data tree with real directory contents
        self._populate_data_tree(game_path)

        # Downloads are populated via set_downloads_path() from MainWindow

    def on_icon_ready(self, cache_key: str, pixmap: QPixmap) -> None:
        """Called when a background icon download completes."""
        gsn = self._current_short_name
        if not gsn:
            return

        if cache_key == f"{gsn}/banner":
            scaled = pixmap.scaled(
                QSize(140, 140),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._game_btn.setIcon(QIcon(scaled))
            self._game_btn.setIconSize(scaled.size())
        elif cache_key.startswith(f"{gsn}/exe/"):
            # Update matching menu action icon
            exe_name = cache_key.split("/exe/", 1)[1]
            for action in self._game_menu.actions():
                binary = action.data()
                if binary and Path(binary).name == exe_name:
                    action.setIcon(QIcon(pixmap.scaled(
                        QSize(24, 24),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )))
                    break

    # ── Internal helpers ──────────────────────────────────────────────

    def _update_game_button_icon(self, game_name: str) -> None:
        """Set the game button to the cached banner or a placeholder."""
        banner = None
        if self._icon_manager and self._current_short_name:
            banner = self._icon_manager.get_game_banner(self._current_short_name)

        if banner is not None:
            scaled = banner.scaled(
                QSize(140, 140),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._game_btn.setIcon(QIcon(scaled))
            self._game_btn.setIconSize(scaled.size())
        else:
            # Placeholder: grey box with game name
            pix = QPixmap(140, 140)
            pix.fill(QColor("#242424"))
            if game_name:
                p = QPainter(pix)
                p.setPen(QColor("#808080"))
                f = QFont()
                f.setPixelSize(13)
                p.setFont(f)
                p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, game_name)
                p.end()
            self._game_btn.setIcon(QIcon(pix))
            self._game_btn.setIconSize(pix.size())

    def _rebuild_game_menu(self, game_plugin) -> None:
        """Rebuild the game button dropdown with executables from the plugin."""
        self._game_menu.clear()
        self._game_menu.addAction(QAction("<Bearbeiten...>", self, triggered=_todo("<Bearbeiten...>")))
        self._game_menu.addSeparator()

        if game_plugin is not None:
            for exe in game_plugin.executables():
                name = exe.get("name", "")
                binary = exe.get("binary", "")
                if not name:
                    continue
                action = QAction(name, self, triggered=_todo(name))
                action.setData(binary)  # store binary for icon matching
                # Try cached exe icon
                if self._icon_manager and self._current_short_name and binary:
                    icon_pix = self._icon_manager.get_executable_icon(
                        self._current_short_name, binary,
                    )
                    if icon_pix is not None:
                        action.setIcon(QIcon(icon_pix.scaled(
                            QSize(24, 24),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )))
                self._game_menu.addAction(action)
            self._game_menu.addSeparator()

        self._game_menu.addAction(QAction("Explore Virtual Folder", self, triggered=_todo("Explore Virtual Folder")))

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

    def _on_dl_context_menu(self, pos) -> None:
        """Right-click context menu on downloads table."""
        row = self._dl_table.rowAt(pos.y())
        path = self._get_dl_archive_path(row) if row >= 0 else None
        if not path:
            return
        menu = QMenu(self)
        act_install = menu.addAction("Installieren")
        chosen = menu.exec(self._dl_table.viewport().mapToGlobal(pos))
        if chosen == act_install:
            self.install_requested.emit([path])
