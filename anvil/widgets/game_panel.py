"""Game-Panel — MO2-Kopie: großes Game-Icon, Tabs, Downloads mit Neu laden."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QComboBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QCheckBox,
    QLineEdit,
    QMenu,
    QFrame,
)
import os

from PySide6.QtGui import QPixmap, QIcon, QColor, QAction
from PySide6.QtCore import Qt, QSize


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

        # Rechte Seite oben: Game-Button (96x96) mit Dropdown + Label, Starten, Verknüpfung
        top_frame = QFrame()
        top_layout = QVBoxLayout(top_frame)
        top_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = QPixmap(96, 96)
        pix.fill(QColor("#242424"))
        game_btn = QToolButton(self)
        game_btn.setIcon(QIcon(pix))
        game_btn.setIconSize(pix.size())
        game_btn.setFixedSize(96, 96)
        game_btn.setStyleSheet(
            "QToolButton { background: #242424; border: 2px solid #3D3D3D; border-radius: 4px; }"
            "QToolButton:hover { background: #2a2a2a; }"
        )
        game_menu = QMenu(self)
        game_menu.setStyleSheet("QMenu { min-width: 300px; font-size: 14px; }")
        game_menu.addAction(QAction("<Bearbeiten...>", self, triggered=_todo("<Bearbeiten...>")))
        game_menu.addSeparator()
        game_menu.addAction(QAction("Cyberpunk 2077", self, triggered=_todo("Cyberpunk 2077")))
        game_menu.addAction(QAction("Cyberpunk 2077 - skip REDmod deploy", self, triggered=_todo("Cyberpunk 2077 - skip REDmod deploy")))
        game_menu.addAction(QAction("Manually deploy REDmod", self, triggered=_todo("Manually deploy REDmod")))
        game_menu.addAction(QAction("REDprelauncher", self, triggered=_todo("REDprelauncher")))
        game_menu.addSeparator()
        game_menu.addAction(QAction("Explore Virtual Folder", self, triggered=_todo("Explore Virtual Folder")))
        game_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        game_btn.setMenu(game_menu)
        top_layout.addWidget(game_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        game_label = QLabel("Cyberpunk 2077")
        game_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(game_label)
        start_btn = QPushButton()
        start_btn.setObjectName("startButton")
        _play_icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "styles", "icons", "files", "play.png")
        if os.path.exists(_play_icon):
            start_btn.setIcon(QIcon(_play_icon))
            start_btn.setIconSize(QSize(32, 32))
        start_btn.setMinimumWidth(180)
        start_btn.setToolTip("Starten")
        start_btn.clicked.connect(_todo("Starten"))
        top_layout.addWidget(start_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        link_combo = QComboBox()
        link_combo.addItem("Verknüpfung")
        link_combo.setMinimumWidth(180)
        link_combo.currentTextChanged.connect(lambda t: _todo("Verknüpfung")())
        top_layout.addWidget(link_combo, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(top_frame)

        tabs = QTabWidget()
        data = QWidget()
        data.setLayout(QVBoxLayout())
        data.layout().addWidget(QLabel("Daten (Platzhalter)"))
        tabs.addTab(data, "Daten")
        saves = QWidget()
        saves.setLayout(QVBoxLayout())
        saves.layout().addWidget(QLabel("Spielstände (Platzhalter)"))
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
