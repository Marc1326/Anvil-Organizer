"""Toolbar — MO2-Kopie: 9 Icon-Buttons + rechts Info/Benachrichtigungen (Platzhalter)."""

from PySide6.QtWidgets import QToolBar, QToolButton, QWidget, QStyle, QSizePolicy
from PySide6.QtCore import Qt


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


def create_toolbar(parent=None):
    bar = QToolBar(parent)
    bar.setMovable(False)
    style = bar.style()

    def add_icon(pixmap, tooltip):
        btn = QToolButton(bar)
        btn.setIcon(style.standardIcon(pixmap))
        btn.setToolTip(tooltip)
        btn.clicked.connect(_todo(tooltip))
        bar.addWidget(btn)

    # MO2: linke Gruppe (über Mod-Liste)
    add_icon(QStyle.StandardPixmap.SP_DirOpenIcon, "Ordner öffnen")
    add_icon(QStyle.StandardPixmap.SP_DirIcon, "Ordner / Neu")
    add_icon(QStyle.StandardPixmap.SP_ComputerIcon, "Profil")
    add_icon(QStyle.StandardPixmap.SP_BrowserReload, "Refresh")
    add_icon(QStyle.StandardPixmap.SP_ArrowBack, "Rückgängig")
    add_icon(QStyle.StandardPixmap.SP_ArrowForward, "Wiederholen")
    add_icon(QStyle.StandardPixmap.SP_DialogApplyButton, "Werkzeuge")
    add_icon(QStyle.StandardPixmap.SP_FileDialogDetailedView, "Einstellungen")
    # Stretch: rechte Gruppe bündig rechts wie in MO2
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    bar.addWidget(spacer)
    add_icon(QStyle.StandardPixmap.SP_DialogYesButton, "Endorsements")
    add_icon(QStyle.StandardPixmap.SP_MessageBoxWarning, "Benachrichtigungen")
    add_icon(QStyle.StandardPixmap.SP_ArrowDown, "Downloads")
    add_icon(QStyle.StandardPixmap.SP_MessageBoxInformation, "Info")

    return bar
