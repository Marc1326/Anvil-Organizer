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
from PySide6.QtCore import QSize, Signal

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
    collapse_all_requested = Signal()
    expand_all_requested = Signal()
    reload_requested = Signal()
    export_csv_requested = Signal()
    open_game_requested = Signal()
    open_mygames_requested = Signal()
    open_ini_requested = Signal()
    open_instance_requested = Signal()
    open_mods_requested = Signal()
    open_profile_requested = Signal()
    open_downloads_requested = Signal()
    open_ao_install_requested = Signal()
    open_ao_plugins_requested = Signal()
    open_ao_styles_requested = Signal()
    open_ao_logs_requested = Signal()
    backup_requested = Signal()
    restore_requested = Signal()

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
        menu1.addAction(QAction("Alle einklappen", self, triggered=lambda checked: self.collapse_all_requested.emit()))
        menu1.addAction(QAction("Alle ausklappen", self, triggered=lambda checked: self.expand_all_requested.emit()))
        menu1.addSeparator()
        menu1.addAction(QAction("Aktiviere alle", self, triggered=_todo("Aktiviere alle")))
        menu1.addAction(QAction("Deaktiviere alle", self, triggered=_todo("Deaktiviere alle")))
        menu1.addSeparator()
        act_updates = QAction("Auf Updates prüfen", self, triggered=_todo("Auf Updates prüfen"))
        act_updates.setEnabled(False)
        menu1.addAction(act_updates)
        act_auto_cat = QAction("Kategorien automatisch zuweisen", self, triggered=_todo("Kategorien automatisch zuweisen"))
        act_auto_cat.setEnabled(False)
        menu1.addAction(act_auto_cat)
        menu1.addAction(QAction("Neu laden", self, triggered=lambda checked: self.reload_requested.emit()))
        menu1.addSeparator()
        menu1.addAction(QAction("Als CSV exportieren...", self, triggered=lambda checked: self.export_csv_requested.emit()))
        menu1.addSeparator()
        menu1.addAction(QAction("Sicherung erstellen", self, triggered=lambda checked: (print("[MENU] Sicherung erstellen geklickt"), self.backup_requested.emit())))
        menu1.addAction(QAction("Aus Sicherung wiederherstellen...", self, triggered=lambda checked: self.restore_requested.emit()))
        btn_menu = QToolButton(self)
        _set_icon(btn_menu, "dots.png")
        btn_menu.setToolTip("Menü")
        btn_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn_menu.setMenu(menu1)
        btn_menu.setFixedSize(48, 32)
        btn_menu.clicked.connect(_todo("Menü"))

        menu2 = QMenu(self)
        menu2.addAction(QAction("Spielverzeichnis öffnen", self, triggered=lambda checked: self.open_game_requested.emit()))
        menu2.addAction(QAction("MyGames Ordner öffnen", self, triggered=lambda checked: self.open_mygames_requested.emit()))
        menu2.addAction(QAction("INI Ordner öffnen", self, triggered=lambda checked: self.open_ini_requested.emit()))
        menu2.addAction(QAction("Instanz Ordner öffnen", self, triggered=lambda checked: self.open_instance_requested.emit()))
        menu2.addAction(QAction("Mods Ordner öffnen", self, triggered=lambda checked: self.open_mods_requested.emit()))
        menu2.addAction(QAction("Profil Ordner öffnen", self, triggered=lambda checked: self.open_profile_requested.emit()))
        menu2.addAction(QAction("Downloads Ordner öffnen", self, triggered=lambda checked: self.open_downloads_requested.emit()))
        menu2.addSeparator()
        menu2.addAction(QAction("AO Installationsordner öffnen", self, triggered=lambda checked: self.open_ao_install_requested.emit()))
        menu2.addAction(QAction("AO Plugins Ordner öffnen", self, triggered=lambda checked: self.open_ao_plugins_requested.emit()))
        menu2.addAction(QAction("AO Stylesheets Ordner öffnen", self, triggered=lambda checked: self.open_ao_styles_requested.emit()))
        menu2.addAction(QAction("AO Log Ordner öffnen", self, triggered=lambda checked: self.open_ao_logs_requested.emit()))
        btn_view = QToolButton(self)
        _set_icon(btn_view, "archives.png")
        btn_view.setToolTip("Ansicht")
        btn_view.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn_view.setMenu(menu2)
        btn_view.setFixedSize(48, 32)
        btn_view.clicked.connect(_todo("Ansicht"))

        btn_restore = QToolButton(self)
        _set_icon(btn_restore, "restore.png")
        btn_restore.setToolTip("Aus Sicherung wiederherstellen")
        btn_restore.setFixedSize(36, 32)
        btn_restore.clicked.connect(lambda: self.restore_requested.emit())

        btn_backup = QToolButton(self)
        _set_icon(btn_backup, "backup.png")
        btn_backup.setToolTip("Sicherung erstellen")
        btn_backup.setFixedSize(36, 32)
        btn_backup.clicked.connect(lambda: (print("[BTN] 💾 geklickt"), self.backup_requested.emit()))

        for btn in [btn_menu, btn_view, btn_restore, btn_backup]:
            btn.setStyleSheet(BUTTON_STYLE)
            layout.addWidget(btn)

        layout.addWidget(QLabel("Aktiv:"))
        self._active = QLabel("<b>0</b>")
        self._active.setObjectName("activeCount")
        layout.addWidget(self._active)

    def update_active_count(self, active: int, total: int | None = None) -> None:
        """Update the active mod counter badge.

        Args:
            active: Number of active/enabled mods.
            total:  Total number of mods (if given, displays "active / total").
                    If None, displays only the active count (used by BG3).
        """
        if total is not None:
            self._active.setText(f"<b>{active} / {total}</b>")
        else:
            self._active.setText(f"<b>{active}</b>")
