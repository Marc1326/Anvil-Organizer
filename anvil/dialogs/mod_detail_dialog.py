"""Mod-Detail-Dialog — öffnet bei Doppelklick auf Mod in der Mod-Liste."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Qt

_MOD_DETAIL_DIALOG_STYLE = """
QDialog, QWidget { background: #1C1C1C; color: #D3D3D3; border: none; }
QTabWidget { padding: 0; margin: 0; }
QTabWidget::pane {
    background: #1C1C1C;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    margin-top: 0;
    padding: 0;
    border-top: none;
}
QTabBar::tab { background: #242424; color: #D3D3D3; padding: 8px 16px; margin-right: 2px; }
QTabBar::tab:selected { background: #006868; color: #D3D3D3; }
QTabBar::tab:hover:!selected { background: #3D3D3D; }
QPushButton {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 6px 12px;
}
QPushButton:hover { background: #3D3D3D; }
QPushButton:pressed { background: #006868; }
QLabel { color: #D3D3D3; }
"""


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


class ModDetailDialog(QDialog):
    def __init__(self, parent=None, mod_name=""):
        super().__init__(parent)
        self.setWindowTitle(mod_name or "Mod-Details")
        self.setMinimumSize(1280, 720)
        self.resize(1300, 750)
        self.setStyleSheet(_MOD_DETAIL_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(12, 12, 12, 12)

        self.tab_widget = QTabWidget()

        tab_labels = [
            ("Textdateien", "Platzhalter – Textdateien"),
            ("INI Dateien", "Platzhalter – INI Dateien"),
            ("Bilder", "Platzhalter – Bilder"),
            ("Optionale ESPs", "Platzhalter – Optionale ESPs"),
            ("Konflikte", "Platzhalter – Konflikte"),
            ("Kategorien", "Platzhalter – Kategorien"),
            ("Nexus Info", "Platzhalter – Nexus Info"),
            ("Verzeichnisbaum", "Platzhalter – Verzeichnisbaum"),
        ]
        for tab_name, placeholder_text in tab_labels:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.addWidget(QLabel(placeholder_text))
            self.tab_widget.addTab(page, tab_name)

        tab_bar = self.tab_widget.tabBar()
        tab_bar.setExpanding(False)
        tab_bar.setParent(None)

        tab_bar_container = QHBoxLayout()
        tab_bar_container.addStretch(1)
        tab_bar_container.addWidget(tab_bar)
        tab_bar_container.addStretch(1)
        tab_bar_container.setContentsMargins(0, 0, 0, 0)
        tab_bar_container.setSpacing(0)

        layout.addLayout(tab_bar_container)
        layout.addWidget(self.tab_widget)
        layout.addSpacing(10)

        # Unten: Zurück/Weiter links, Schliessen rechts
        btn_row = QHBoxLayout()
        btn_back = QPushButton("Zurück")
        btn_back.clicked.connect(_todo("Mod-Navigation Zurück"))
        btn_next = QPushButton("Weiter")
        btn_next.clicked.connect(_todo("Mod-Navigation Weiter"))
        btn_row.addWidget(btn_back)
        btn_row.addWidget(btn_next)
        btn_row.addStretch()
        btn_close = QPushButton("Schliessen")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)
