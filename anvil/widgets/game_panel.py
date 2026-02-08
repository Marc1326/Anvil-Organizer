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

from PySide6.QtGui import QPixmap, QIcon, QColor, QAction
from PySide6.QtCore import Qt, QSize, QPoint


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


class GamePanel(QWidget):
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
        self._data_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
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
        saves_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        saves_layout.addWidget(saves_tree)
        tabs.addTab(saves, "Spielstände")

        # ── Downloads-Tab ─────────────────────────────────────────────
        downloads = QWidget()
        dl_layout = QVBoxLayout(downloads)
        reload_btn = QPushButton("Neu laden")
        reload_btn.clicked.connect(_todo("Downloads neu laden"))
        dl_layout.addWidget(reload_btn)
        self._dl_table = QTableWidget()
        self._dl_table.setColumnCount(4)
        self._dl_table.setHorizontalHeaderLabels(["Name", "Größe", "Status", "Dateizeit"])
        self._dl_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._dl_table.setAlternatingRowColors(True)
        self._dl_table.setRowCount(0)
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

        # Track current game path for reload
        self._current_game_path: Path | None = None

    # ── Public API ────────────────────────────────────────────────────

    def update_game(self, game_name: str, game_path: Path | None) -> None:
        """Update the panel to reflect the active game instance.

        Args:
            game_name: Display name of the game.
            game_path: Path to the game installation directory,
                       or None if not detected.
        """
        self._current_game_path = game_path

        # Update label
        self._game_label.setText(game_name or "Kein Spiel ausgewählt")

        # Update data tree with real directory contents
        self._populate_data_tree(game_path)

        # Clear downloads (real downloads come from instance .downloads/ in Phase 3)
        self._dl_table.setRowCount(0)

    # ── Internal helpers ──────────────────────────────────────────────

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
