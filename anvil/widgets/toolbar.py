"""Toolbar — MO2-Kopie: Paper Dark SVG-Icons, Separatoren, rechte Status-Icons."""

import os
import subprocess
from pathlib import Path

from PySide6.QtGui import QIcon, QDesktopServices
from PySide6.QtWidgets import QToolBar, QToolButton, QWidget, QSizePolicy
from PySide6.QtCore import Qt, QSize, QUrl

from anvil.widgets.instance_manager_dialog import InstanceManagerDialog

_ICONS_DIR = Path(__file__).resolve().parent.parent / "styles" / "icons"

NEXUS_GAME_URLS = {
    "Cyberpunk 2077": "https://www.nexusmods.com/cyberpunk2077",
    "Baldur's Gate 3": "https://www.nexusmods.com/baldursgate3",
    "Skyrim Special Edition": "https://www.nexusmods.com/skyrimspecialedition",
}
NEXUS_FALLBACK_URL = "https://www.nexusmods.com"


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


def _icon(name: str) -> QIcon:
    path = _ICONS_DIR / name
    if path.exists():
        return QIcon(str(path))
    return QIcon()


def create_toolbar(parent=None):
    bar = QToolBar(parent)
    bar.setMovable(False)
    bar.setIconSize(QSize(32, 32))
    bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    bar.setFixedHeight(52)

    def add_icon(icon_name: str, tooltip: str):
        btn = QToolButton(bar)
        btn.setIcon(_icon(icon_name))
        btn.setToolTip(tooltip)
        btn.setFixedSize(44, 44)
        btn.clicked.connect(_todo(tooltip))
        bar.addWidget(btn)

    # Links: MO2-Reihenfolge mit Separatoren (Paper Dark SVGs)
    instances_btn = QToolButton(bar)
    instances_btn.setIcon(_icon("instances.svg"))
    instances_btn.setToolTip("Instances/Game")
    instances_btn.setFixedSize(44, 44)
    instances_btn.clicked.connect(lambda: InstanceManagerDialog(bar.window()).exec())
    bar.addWidget(instances_btn)
    folder_btn = QToolButton(bar)
    folder_btn.setIcon(_icon("archives.svg"))
    folder_btn.setToolTip("Ordner")
    folder_btn.setFixedSize(44, 44)
    folder_btn.clicked.connect(
        lambda: subprocess.Popen(["xdg-open", os.path.expanduser("~")])
    )
    bar.addWidget(folder_btn)
    bar.addSeparator()
    nexus_btn = QToolButton(bar)
    nexus_btn.setIcon(_icon("nexus.svg"))
    nexus_btn.setToolTip("Nexus/Web")
    nexus_btn.setFixedSize(44, 44)

    def _open_nexus_for_game():
        win = bar.window()
        current_game = getattr(win, "current_game", "Cyberpunk 2077")
        url = NEXUS_GAME_URLS.get(current_game, NEXUS_FALLBACK_URL)
        QDesktopServices.openUrl(QUrl(url))

    nexus_btn.clicked.connect(_open_nexus_for_game)
    bar.addWidget(nexus_btn)
    add_icon("globe.svg", "Ansicht")
    add_icon("profiles.svg", "Profil/Person")
    bar.addSeparator()
    add_icon("refresh.svg", "Refresh")
    add_icon("executables.svg", "Executables")
    add_icon("tools.svg", "Tools")
    add_icon("settings.svg", "Einstellungen")

    # Spacer: rechte Icons bündig rechts
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    bar.addWidget(spacer)

    # Rechts: 4 Status-Icons
    add_icon("endorse.svg", "Endorse")
    add_icon("problems.svg", "Benachrichtigungen")
    add_icon("update.svg", "Update")
    add_icon("help.svg", "Info")

    return bar
