"""Toolbar — MO2-Kopie: Paper Dark SVG-Icons, Separatoren, rechte Status-Icons."""

import os
import subprocess
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QToolBar, QToolButton, QWidget, QSizePolicy
from PySide6.QtCore import Qt, QSize

from anvil.widgets.instance_manager_dialog import InstanceManagerDialog
from anvil.widgets.profile_dialog import ProfileDialog
from anvil.widgets.executables_dialog import ExecutablesDialog
from anvil.widgets.settings_dialog import SettingsDialog

_ICONS_DIR = Path(__file__).resolve().parent.parent / "styles" / "icons"


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
    def _open_instance_manager():
        win = bar.window()
        dlg = InstanceManagerDialog(
            win,
            getattr(win, "instance_manager", None),
            getattr(win, "plugin_loader", None),
            getattr(win, "icon_manager", None),
        )
        dlg.exec()
        if dlg.switched_to and hasattr(win, "switch_instance"):
            win.switch_instance(dlg.switched_to)

    instances_btn.clicked.connect(_open_instance_manager)
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
    profile_btn = QToolButton(bar)
    profile_btn.setIcon(_icon("profiles.svg"))
    profile_btn.setToolTip("Profil/Person")
    profile_btn.setFixedSize(44, 44)
    profile_btn.clicked.connect(lambda: ProfileDialog(bar.window()).exec())
    bar.addWidget(profile_btn)
    bar.addSeparator()
    refresh_btn = QToolButton(bar)
    refresh_btn.setIcon(_icon("refresh.svg"))
    refresh_btn.setToolTip("Refresh / Neu laden")
    refresh_btn.setFixedSize(44, 44)

    def _on_refresh():
        print("Mod-Liste wird neu geladen...")
        win = bar.window()
        if win and hasattr(win, "statusBar") and win.statusBar():
            win.statusBar().showMessage("Mod-Liste aktualisiert", 3000)

    refresh_btn.clicked.connect(_on_refresh)
    bar.addWidget(refresh_btn)
    exec_btn = QToolButton(bar)
    exec_btn.setIcon(_icon("executables.svg"))
    exec_btn.setToolTip("Executables")
    exec_btn.setFixedSize(44, 44)
    exec_btn.clicked.connect(lambda: ExecutablesDialog(bar.window()).exec())
    bar.addWidget(exec_btn)
    add_icon("tools.svg", "Tools")
    settings_btn = QToolButton(bar)
    settings_btn.setIcon(_icon("settings.svg"))
    settings_btn.setToolTip("Einstellungen")
    settings_btn.setFixedSize(44, 44)
    settings_btn.clicked.connect(
        lambda: SettingsDialog(
            bar.window(),
            getattr(bar.window(), "plugin_loader", None),
        ).exec()
    )
    bar.addWidget(settings_btn)

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
