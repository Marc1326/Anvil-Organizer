"""Game-Panel — MO2-Kopie: Icon, Starten (#006868), Verknüpfung, Tabs, Downloads mit Neu laden."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QCheckBox,
    QLineEdit,
)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt


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

        # MO2: eine Zeile: Icon links, Spielname, Starten-Button RECHTS
        top_row = QHBoxLayout()
        pix = QPixmap(48, 48)
        pix.fill(QColor("#141414"))
        icon_label = QLabel()
        icon_label.setPixmap(pix)
        top_row.addWidget(icon_label)
        top_row.addWidget(QLabel("Cyberpunk 2077"))
        top_row.addStretch()
        start_btn = QPushButton("► Starten")
        start_btn.setObjectName("startButton")
        start_btn.clicked.connect(_todo("Starten"))
        top_row.addWidget(start_btn)
        layout.addLayout(top_row)

        link = QComboBox()
        link.addItem("Verknüpfung")
        link.currentTextChanged.connect(lambda t: _todo("Verknüpfung")())
        layout.addWidget(link)

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
