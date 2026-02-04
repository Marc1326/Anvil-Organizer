"""Profil-Leiste: Profil-Dropdown, 5 ToolButtons, Aktiv-Badge."""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QToolButton
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


class ProfileBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("profileBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Profil:"))
        self._combo = QComboBox()
        self._combo.addItem("aktive")
        self._combo.addItem("Default")
        self._combo.currentTextChanged.connect(lambda t: _todo("Profil wechseln")())
        layout.addWidget(self._combo)

        layout.addStretch()
        style = self.style()
        sp = style.StandardPixmap
        # MO2: Herz, Warndreieck, Ordner hoch, Info, Info
        for tooltip, pix in [
            ("Endorsements", sp.SP_DialogYesButton),
            ("Benachrichtigungen", sp.SP_MessageBoxWarning),
            ("Backup / Ordner", sp.SP_ArrowUp),
            ("Info", sp.SP_MessageBoxInformation),
            ("Filter", sp.SP_FileDialogContentsView),
        ]:
            btn = QToolButton(self)
            btn.setIcon(style.standardIcon(pix))
            btn.setToolTip(tooltip)
            btn.clicked.connect(_todo(tooltip))
            layout.addWidget(btn)
        layout.addStretch()

        layout.addWidget(QLabel("Aktiv:"))
        self._active = QLabel("62")
        self._active.setObjectName("activeCount")
        layout.addWidget(self._active)
