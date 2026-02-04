"""Profil-Leiste: Profil-Dropdown, 4 ToolButtons, Aktiv-Badge — wie MO2."""

import os

from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QToolButton,
    QSizePolicy,
    QMenu,
)
from PySide6.QtCore import QSize

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "styles", "icons", "files")


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


BUTTON_STYLE = """
    QToolButton {
        background: #2a2a2a;
        border: 1px solid #3D3D3D;
        border-radius: 3px;
        color: #D3D3D3;
        font-size: 16px;
        font-weight: bold;
        padding: 2px 6px;
    }
    QToolButton:hover {
        background: #3D3D3D;
    }
    QToolButton::menu-indicator {
        subcontrol-position: right center;
        width: 12px;
    }
"""


class ProfileBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("profileBar")
        self.setFixedHeight(44)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # Profil-Label + ComboBox (Expanding)
        layout.addWidget(QLabel("Profil:"))
        self._combo = QComboBox()
        self._combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._combo.addItem("aktive")
        self._combo.addItem("Default")
        self._combo.currentTextChanged.connect(lambda t: _todo("Profil wechseln")())
        layout.addWidget(self._combo, 1)

        # 4 Buttons: Icons aus profile/ (dots, archives, restore, backup)
        def _set_icon(btn, filename):
            path = os.path.join(ICON_DIR, filename)
            if os.path.exists(path):
                btn.setIcon(QIcon(path))
                btn.setIconSize(QSize(20, 20))

        menu1 = QMenu(self)
        menu1.addAction(QAction("Installiere Mod...", self, triggered=_todo("Installiere Mod...")))
        menu1.addAction(QAction("Leere Mod erstellen", self, triggered=_todo("Leere Mod erstellen")))
        menu1.addAction(QAction("Erstelle Trenner", self, triggered=_todo("Erstelle Trenner")))
        menu1.addSeparator()
        menu1.addAction(QAction("Alle einklappen", self, triggered=_todo("Alle einklappen")))
        menu1.addAction(QAction("Alle ausklappen", self, triggered=_todo("Alle ausklappen")))
        menu1.addSeparator()
        menu1.addAction(QAction("Aktiviere alle", self, triggered=_todo("Aktiviere alle")))
        menu1.addAction(QAction("Deaktiviere alle", self, triggered=_todo("Deaktiviere alle")))
        menu1.addSeparator()
        menu1.addAction(QAction("Auf Updates prüfen", self, triggered=_todo("Auf Updates prüfen")))
        menu1.addAction(QAction("Kategorien automatisch zuweisen", self, triggered=_todo("Kategorien automatisch zuweisen")))
        menu1.addAction(QAction("Neu laden", self, triggered=_todo("Neu laden")))
        menu1.addSeparator()
        menu1.addAction(QAction("Als CSV exportieren...", self, triggered=_todo("Als CSV exportieren...")))
        btn_menu = QToolButton(self)
        _set_icon(btn_menu, "dots.png")
        btn_menu.setToolTip("Menü")
        btn_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn_menu.setMenu(menu1)
        btn_menu.setFixedSize(48, 32)
        btn_menu.clicked.connect(_todo("Menü"))

        menu2 = QMenu(self)
        menu2.addAction(QAction("Spielverzeichnis öffnen", self, triggered=_todo("Spielverzeichnis öffnen")))
        menu2.addAction(QAction("MyGames Ordner öffnen", self, triggered=_todo("MyGames Ordner öffnen")))
        menu2.addAction(QAction("INI Ordner öffnen", self, triggered=_todo("INI Ordner öffnen")))
        menu2.addAction(QAction("Instanz Ordner öffnen", self, triggered=_todo("Instanz Ordner öffnen")))
        menu2.addAction(QAction("Mods Ordner öffnen", self, triggered=_todo("Mods Ordner öffnen")))
        menu2.addAction(QAction("Profil Ordner öffnen", self, triggered=_todo("Profil Ordner öffnen")))
        menu2.addAction(QAction("Downloads Ordner öffnen", self, triggered=_todo("Downloads Ordner öffnen")))
        menu2.addSeparator()
        menu2.addAction(QAction("AO Installationsordner öffnen", self, triggered=_todo("AO Installationsordner öffnen")))
        menu2.addAction(QAction("AO Plugins Ordner öffnen", self, triggered=_todo("AO Plugins Ordner öffnen")))
        menu2.addAction(QAction("AO Stylesheets Ordner öffnen", self, triggered=_todo("AO Stylesheets Ordner öffnen")))
        menu2.addAction(QAction("AO Log Ordner öffnen", self, triggered=_todo("AO Log Ordner öffnen")))
        btn_view = QToolButton(self)
        _set_icon(btn_view, "archives.png")
        btn_view.setToolTip("Ansicht")
        btn_view.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn_view.setMenu(menu2)
        btn_view.setFixedSize(48, 32)
        btn_view.clicked.connect(_todo("Ansicht"))

        btn_undo = QToolButton(self)
        _set_icon(btn_undo, "restore.png")
        btn_undo.setToolTip("Zurücksetzen")
        btn_undo.setFixedSize(36, 32)
        btn_undo.clicked.connect(_todo("Zurücksetzen"))

        btn_filter = QToolButton(self)
        _set_icon(btn_filter, "backup.png")
        btn_filter.setToolTip("Filter")
        btn_filter.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn_filter.setMenu(QMenu())
        btn_filter.setFixedSize(48, 32)
        btn_filter.clicked.connect(_todo("Filter"))

        for btn in [btn_menu, btn_view, btn_undo, btn_filter]:
            btn.setStyleSheet(BUTTON_STYLE)
            layout.addWidget(btn)

        layout.addWidget(QLabel("Aktiv:"))
        self._active = QLabel("62")
        self._active.setObjectName("activeCount")
        layout.addWidget(self._active)
