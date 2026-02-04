"""Toolbar — MO2-Kopie: große Icons, Separatoren, rechte Status-Icons."""

from PySide6.QtWidgets import QToolBar, QToolButton, QWidget, QStyle, QSizePolicy
from PySide6.QtCore import Qt, QSize


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


def create_toolbar(parent=None):
    bar = QToolBar(parent)
    bar.setMovable(False)
    bar.setIconSize(QSize(32, 32))
    bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    bar.setFixedHeight(52)
    style = bar.style()

    def add_icon(pixmap, tooltip):
        btn = QToolButton(bar)
        btn.setIcon(style.standardIcon(pixmap))
        btn.setToolTip(tooltip)
        btn.setFixedSize(44, 44)
        btn.clicked.connect(_todo(tooltip))
        bar.addWidget(btn)

    # Links: MO2-Reihenfolge mit Separatoren
    add_icon(QStyle.StandardPixmap.SP_ComputerIcon, "Instances/Game")
    add_icon(QStyle.StandardPixmap.SP_DirIcon, "Ordner")
    bar.addSeparator()
    add_icon(QStyle.StandardPixmap.SP_DriveNetIcon, "Nexus/Web")
    add_icon(QStyle.StandardPixmap.SP_FileDialogDetailedView, "Ansicht")
    add_icon(QStyle.StandardPixmap.SP_DialogApplyButton, "Profil/Person")
    bar.addSeparator()
    add_icon(QStyle.StandardPixmap.SP_BrowserReload, "Refresh")
    add_icon(QStyle.StandardPixmap.SP_MediaSeekForward, "Executables")
    add_icon(QStyle.StandardPixmap.SP_FileDialogContentsView, "Tools")
    add_icon(QStyle.StandardPixmap.SP_DialogHelpButton, "Einstellungen")

    # Spacer: rechte Icons bündig rechts
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    bar.addWidget(spacer)

    # Rechts: 4 Status-Icons (32x32)
    add_icon(QStyle.StandardPixmap.SP_DialogYesButton, "Endorse")
    add_icon(QStyle.StandardPixmap.SP_MessageBoxWarning, "Benachrichtigungen")
    add_icon(QStyle.StandardPixmap.SP_DesktopIcon, "Update")
    add_icon(QStyle.StandardPixmap.SP_MessageBoxInformation, "Info")

    return bar
