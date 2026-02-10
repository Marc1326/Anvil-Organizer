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
    bar.setObjectName("mainToolBar")
    bar.setMovable(False)
    # Icon size and button style are set by MainWindow._restore_view_settings()

    def _add_btn(icon_name: str, tooltip: str) -> QToolButton:
        btn = QToolButton(bar)
        btn.setIcon(_icon(icon_name))
        btn.setToolTip(tooltip)
        btn.setText(tooltip)
        bar.addWidget(btn)
        return btn

    # Links: MO2-Reihenfolge mit Separatoren (Paper Dark SVGs)
    instances_btn = _add_btn("instances.svg", "Instances/Game")
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

    folder_btn = _add_btn("archives.svg", "Ordner")
    folder_btn.clicked.connect(
        lambda: subprocess.Popen(["xdg-open", os.path.expanduser("~")])
    )

    bar.addSeparator()

    profile_btn = _add_btn("profiles.svg", "Profile")
    profile_btn.clicked.connect(lambda: ProfileDialog(bar.window()).exec())

    bar.addSeparator()

    refresh_btn = _add_btn("refresh.svg", "Neu laden")
    def _on_refresh():
        win = bar.window()
        if win and hasattr(win, "_on_menu_refresh"):
            win._on_menu_refresh()

    refresh_btn.clicked.connect(_on_refresh)

    exec_btn = _add_btn("executables.svg", "Executables")
    exec_btn.clicked.connect(lambda: ExecutablesDialog(bar.window()).exec())

    tools_btn = _add_btn("tools.svg", "Tools")
    tools_btn.clicked.connect(_todo("Tools"))

    settings_btn = _add_btn("settings.svg", "Einstellungen")
    settings_btn.clicked.connect(
        lambda: SettingsDialog(
            bar.window(),
            getattr(bar.window(), "plugin_loader", None),
        ).exec()
    )

    # Spacer: rechte Icons bündig rechts
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    bar.addWidget(spacer)

    # Rechts: 4 Status-Icons
    _add_btn("endorse.svg", "Endorse").clicked.connect(_todo("Endorse"))
    _add_btn("problems.svg", "Benachrichtigungen").clicked.connect(_todo("Benachrichtigungen"))
    _add_btn("update.svg", "Update").clicked.connect(_todo("Update"))
    _add_btn("help.svg", "Info").clicked.connect(_todo("Info"))

    return bar
