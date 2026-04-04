"""Toolbar — Paper Dark SVG-Icons, Separatoren, rechte Status-Icons."""

import os
import subprocess
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QToolBar, QToolButton, QWidget, QSizePolicy, QMenu
from PySide6.QtCore import Qt, QSize

from anvil.widgets.instance_manager_dialog import InstanceManagerDialog
from anvil.widgets.profile_dialog import ProfileDialog
from anvil.widgets.executables_dialog import ExecutablesDialog
from anvil.widgets.donate_dialog import DonateDialog
from anvil.core.translator import tr
from anvil.core.resource_path import get_anvil_base

_ICONS_DIR = get_anvil_base() / "styles" / "icons"


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

    # Links: Buttons mit Separatoren (Paper Dark SVGs)
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

    def _call_win(method_name):
        win = bar.window()
        if win and hasattr(win, method_name):
            getattr(win, method_name)()

    plugin_btn = _add_btn("plugin.svg", tr("menu.plugin_menu"))
    plugin_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    plugin_menu = QMenu(bar)
    plugin_menu.addAction(tr("menu.create_plugin"), lambda: _call_win("_on_create_plugin"))
    plugin_menu.addAction(tr("menu.edit_plugin"), lambda: _call_win("_on_edit_plugin"))
    plugin_btn.setMenu(plugin_menu)

    folder_btn = _add_btn("archives.svg", "Folders")
    folder_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    folder_menu = QMenu(bar)
    folder_menu.addAction(tr("toolbar.open_game_folder"), lambda: _call_win("_open_game_folder"))
    folder_menu.addAction(tr("toolbar.open_mygames_folder"), lambda: _call_win("_open_mygames_folder"))
    folder_menu.addAction(tr("toolbar.open_saves_folder"), lambda: _call_win("_open_saves_folder"))
    folder_menu.addAction(tr("toolbar.open_ini_folder"), lambda: _call_win("_open_ini_folder"))
    folder_menu.addAction(tr("toolbar.open_instance_folder"), lambda: _call_win("_open_instance_folder"))
    folder_menu.addAction(tr("toolbar.open_mods_folder"), lambda: _call_win("_open_mods_folder"))
    folder_menu.addAction(tr("toolbar.open_profile_folder"), lambda: _call_win("_open_profile_folder"))
    folder_menu.addAction(tr("toolbar.open_downloads_folder"), lambda: _call_win("_open_downloads_folder"))
    folder_menu.addSeparator()
    folder_menu.addAction(tr("toolbar.open_ao_install_folder"), lambda: _call_win("_open_ao_install_folder"))
    folder_menu.addAction(tr("toolbar.open_ao_plugins_folder"), lambda: _call_win("_open_ao_plugins_folder"))
    folder_menu.addAction(tr("toolbar.open_ao_styles_folder"), lambda: _call_win("_open_ao_styles_folder"))
    folder_menu.addAction(tr("toolbar.open_ao_logs_folder"), lambda: _call_win("_open_ao_logs_folder"))
    folder_btn.setMenu(folder_menu)

    bar.addSeparator()

    profile_btn = _add_btn("profiles.svg", "Profiles")
    profile_btn.clicked.connect(lambda: ProfileDialog(bar.window()).exec())

    bar.addSeparator()

    refresh_btn = _add_btn("refresh.svg", tr("menu.reload"))
    def _on_refresh():
        win = bar.window()
        if win and hasattr(win, "_on_menu_refresh"):
            win._on_menu_refresh()

    refresh_btn.clicked.connect(_on_refresh)

    exec_btn = _add_btn("executables.svg", "Executables")
    exec_btn.clicked.connect(lambda: ExecutablesDialog(bar.window()).exec())

    tools_btn = _add_btn("tools.svg", "Tools")
    tools_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    tools_menu = QMenu(bar)
    tools_menu.addAction(tr("menu.profiles"), lambda: _call_win("_on_menu_profiles"))
    tools_menu.addAction(tr("menu.executables"), lambda: _call_win("_on_menu_executables"))
    tools_menu.addSeparator()
    tools_menu.addAction(tr("menu.settings"), lambda: _call_win("_on_menu_settings"))
    tools_btn.setMenu(tools_menu)

    settings_btn = _add_btn("settings.svg", tr("menu.settings"))

    def _on_settings():
        win = bar.window()
        if win and hasattr(win, "_on_menu_settings"):
            win._on_menu_settings()

    settings_btn.clicked.connect(_on_settings)

    deploy_sep = bar.addSeparator()
    deploy_sep.setVisible(False)

    # Deploy-Button (BG3-spezifisch, standardmäßig unsichtbar)
    deploy_btn = QToolButton(bar)
    deploy_btn.setIcon(_icon("check.svg"))
    deploy_btn.setToolTip(tr("toolbar.deploy"))
    deploy_btn.setText(tr("toolbar.deploy"))
    deploy_action = bar.addWidget(deploy_btn)
    deploy_action.setVisible(False)

    def _on_deploy():
        win = bar.window()
        if win and hasattr(win, "_on_bg3_deploy"):
            win._on_bg3_deploy()

    deploy_btn.clicked.connect(_on_deploy)
    bar.deploy_btn = deploy_btn      # For styling
    bar.deploy_action = deploy_action  # For visibility
    bar.deploy_sep = deploy_sep        # Separator tied to deploy

    # Spacer: rechte Icons bündig rechts
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    bar.addWidget(spacer)

    # Rechts: 4 Status-Icons
    donate_btn = _add_btn("endorse.svg", "Support / Donate")
    donate_btn.clicked.connect(lambda: DonateDialog(bar.window()).exec())

    notifications_btn = _add_btn("problems.svg", "Benachrichtigungen")
    notifications_btn.setEnabled(False)
    update_btn = _add_btn("update.svg", "Update")
    def _on_update_check():
        win = bar.window()
        if win and hasattr(win, "_update_checker"):
            win._update_checker.check()
    update_btn.clicked.connect(_on_update_check)

    info_btn = _add_btn("help.svg", "Info")
    info_btn.clicked.connect(lambda: _call_win("_on_about"))

    return bar
