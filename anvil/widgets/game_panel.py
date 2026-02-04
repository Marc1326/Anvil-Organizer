"""Game-Panel — MO2-Kopie: großes Game-Icon, Tabs, Downloads mit Neu laden."""

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
import os

from PySide6.QtGui import QPixmap, QIcon, QColor, QAction
from PySide6.QtCore import Qt, QSize, QPoint


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


def _dummy_downloads():
    return [
        ("Peachu Casual Dress - Archive XL...", "177.29 MB", "Ins.", "1/18/2026 10:"),
        ("Ruffles Outfit - Core...", "76.18 MB", "De.", "11/27/2025 1:"),
        ("Mesh Replacer - EBBN...", "45.0 MB", "Ins.", "2/1/2026 14:"),
        ("Microblend Resource...", "120 MB", "Ins.", "2/2/2026 09:"),
        ("zz_NLD_Morph_and_AnimRig_Additions...", "88 MB", "Ins.", "2/3/2026 11:"),
        ("CubxLeBronze Ruffle Crop...", "5.1 MB", "Wartend", "2/3/2026 12:"),
        ("Chain Halter...", "3.0 MB", "Ins.", "2/3/2026 13:"),
        ("Texture Pack A...", "22 MB", "Ins.", "2/4/2026 08:"),
        ("Animation Fix...", "1.2 MB", "De.", "2/4/2026 08:"),
        ("UI Overhaul...", "15 MB", "Ins.", "2/4/2026 09:"),
        ("Sound Mod...", "32 MB", "Ins.", "2/4/2026 09:"),
        ("Script Fix...", "0.5 MB", "Ins.", "2/4/2026 10:"),
    ]


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
        game_btn = QToolButton(self)
        game_btn.setIcon(QIcon(pix))
        game_btn.setIconSize(pix.size())
        game_btn.setFixedSize(140, 140)
        game_btn.setStyleSheet(
            "QToolButton { background: #242424; border: 2px solid #3D3D3D; border-radius: 4px; }"
            "QToolButton:hover { background: #2a2a2a; }"
        )
        game_menu = QMenu(self)
        game_menu.setStyleSheet("QMenu { min-width: 350px; padding: 6px; font-size: 14px; }")
        game_menu.addAction(QAction("<Bearbeiten...>", self, triggered=_todo("<Bearbeiten...>")))
        game_menu.addSeparator()
        game_menu.addAction(QAction("Cyberpunk 2077", self, triggered=_todo("Cyberpunk 2077")))
        game_menu.addAction(QAction("Cyberpunk 2077 - skip REDmod deploy", self, triggered=_todo("Cyberpunk 2077 - skip REDmod deploy")))
        game_menu.addAction(QAction("Manually deploy REDmod", self, triggered=_todo("Manually deploy REDmod")))
        game_menu.addAction(QAction("REDprelauncher", self, triggered=_todo("REDprelauncher")))
        game_menu.addSeparator()
        game_menu.addAction(QAction("Explore Virtual Folder", self, triggered=_todo("Explore Virtual Folder")))
        game_btn.clicked.connect(
            lambda: game_menu.exec(
                game_btn.mapToGlobal(QPoint(game_btn.width() // 2 - game_menu.sizeHint().width() // 2, game_btn.height()))
            )
        )
        top_layout.addWidget(game_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        game_label = QLabel("Cyberpunk 2077")
        game_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(game_label)
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
        # Daten-Tab: Dateibrowser
        data = QWidget()
        data_layout = QVBoxLayout(data)
        data_reload_btn = QPushButton("Neu laden")
        _refresh_icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "styles", "icons", "refresh.svg")
        if os.path.exists(_refresh_icon):
            data_reload_btn.setIcon(QIcon(_refresh_icon))
        data_reload_btn.setIconSize(QSize(20, 20))
        data_reload_btn.clicked.connect(_todo("Daten neu laden"))
        data_layout.addWidget(data_reload_btn)
        data_tree = QTreeWidget()
        data_tree.setColumnCount(5)
        data_tree.setHeaderLabels(["Name", "Mod", "Type", "Größe", "Datum modifiziert"])
        data_tree.setAlternatingRowColors(True)
        data_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        # Dummy: Ordner
        for folder_name in ("archive", "bin", "engine", "mods", "r6", "red4ext", "root", "tools"):
            folder_item = QTreeWidgetItem(data_tree, [folder_name, "", "Folder", "-", "-"])
        # Dummy: Dateien
        for file_name, size in (
            ("launcher-configuration.json", "111 B"),
            ("libcrypto-1_1-x64.dll", "3.11 MB"),
            ("libssl-1_1-x64.dll", "647.57 KB"),
        ):
            file_item = QTreeWidgetItem(data_tree, [file_name, "<Unmanaged>", "", size, "2/4/2026 10:00"])
        data_layout.addWidget(data_tree)
        data_bar = QHBoxLayout()
        data_bar.addWidget(QCheckBox("Nur Konflikte"))
        data_bar.addWidget(QCheckBox("Archive"))
        data_filter_edit = QLineEdit()
        data_filter_edit.setPlaceholderText("Filter")
        data_bar.addWidget(data_filter_edit)
        data_bar.addStretch()
        data_layout.addLayout(data_bar)
        tabs.addTab(data, "Daten")
        saves = QWidget()
        saves_layout = QVBoxLayout(saves)
        saves_tree = QTreeWidget()
        saves_tree.setColumnCount(2)
        saves_tree.setHeaderLabels(["Name", "Datei"])
        saves_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        saves_layout.addWidget(saves_tree)
        tabs.addTab(saves, "Spielstände")

        downloads = QWidget()
        dl_layout = QVBoxLayout(downloads)
        reload_btn = QPushButton("Neu laden")
        reload_btn.clicked.connect(_todo("Downloads neu laden"))
        dl_layout.addWidget(reload_btn)
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Name", "Größe", "Status", "Dateizeit"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        rows = _dummy_downloads()
        table.setRowCount(len(rows))
        for i, (name, size, status, date) in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(name))
            table.setItem(i, 1, QTableWidgetItem(size))
            table.setItem(i, 2, QTableWidgetItem(status))
            table.setItem(i, 3, QTableWidgetItem(date))
        dl_layout.addWidget(table)
        cb = QCheckBox("versteckte Dateien")
        cb.stateChanged.connect(lambda s: _todo("versteckte Dateien")())
        dl_layout.addWidget(cb)
        fe = QLineEdit()
        fe.setPlaceholderText("Filter")
        fe.textChanged.connect(lambda t: _todo("Filter Downloads")())
        dl_layout.addWidget(fe)
        tabs.addTab(downloads, "Downloads")

        layout.addWidget(tabs)
