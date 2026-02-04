"""Hauptfenster: Menü, Toolbar, Profil-Leiste, Splitter 65:35, Statusbar."""

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QMessageBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt

from anvil.styles import get_stylesheet
from anvil.widgets.toolbar import create_toolbar
from anvil.widgets.profile_bar import ProfileBar
from anvil.widgets.mod_list import ModListView
from anvil.widgets.game_panel import GamePanel
from anvil.widgets.status_bar import StatusBarWidget


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cyberpunk 2077 – Anvil Organizer v0.1.0")
        self.setMinimumSize(1000, 650)
        self.resize(1200, 750)
        self.setStyleSheet(get_stylesheet())

        menubar = self.menuBar()
        fm = menubar.addMenu("Datei")
        fm.addAction("Öffnen").triggered.connect(_todo("Datei – Öffnen"))
        fm.addAction("Beenden").triggered.connect(self.close)
        menubar.addMenu("Ansicht").addAction("Ansicht").triggered.connect(_todo("Ansicht"))
        menubar.addMenu("Werkzeuge").addAction("Werkzeuge").triggered.connect(_todo("Werkzeuge"))
        menubar.addMenu("Hilfe").addAction("Über Anvil Organizer").triggered.connect(self._on_about)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, create_toolbar(self))

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # MO2: Profil-Leiste NUR über der linken Seite, nicht über die ganze Breite
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(ProfileBar(self))
        left_layout.addWidget(ModListView())
        splitter.addWidget(left_pane)
        splitter.addWidget(GamePanel())
        splitter.setSizes([780, 420])
        main_layout.addWidget(splitter)

        self.setStatusBar(StatusBarWidget(self))

    def _on_about(self):
        QMessageBox.about(self, "Über Anvil Organizer", "Anvil Organizer v0.1.0\n\nPlatzhalter-GUI.")
