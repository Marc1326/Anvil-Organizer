"""Toolbar — Paper Dark SVG-Icons, Separatoren, rechte Status-Icons."""

import os
import subprocess
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QToolBar, QToolButton, QWidget, QSizePolicy, QMenu
from PySide6.QtCore import Qt, QSize

from anvil.widgets.instance_manager_dialog import InstanceManagerDialog
from anvil.widgets.executables_dialog import ExecutablesDialog
from anvil.widgets.donate_dialog import DonateDialog
from anvil.widgets.notification_panel import NotificationButton, NotificationPanel
from anvil.core.translator import tr
from anvil.core.resource_path import get_anvil_base

_ICONS_DIR = get_anvil_base() / "styles" / "icons"


def _icon(name: str) -> QIcon:
    # Modern werden die monochromen Icons auf die Theme-Textfarbe gefärbt —
    # sonst sind sie im Hell-Modus unsichtbar (Icon-Ansicht).
    from anvil.styles.dark_theme import themed_icon
    return themed_icon(_ICONS_DIR / name)


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

    from anvil.widgets.modal_shell import is_modern_theme_active
    modern = is_modern_theme_active()

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

    def _call_win(method_name):
        win = bar.window()
        if win and hasattr(win, method_name):
            getattr(win, method_name)()

    # Links: Buttons (modern = Vorlage-Reihenfolge, deutsch)
    instances_btn = _add_btn(
        "instances.svg",
        tr("toolbar.instances") if modern else "Instances/Game")
    instances_btn.clicked.connect(_open_instance_manager)

    if modern:
        # Vorlage: Instanzen · Ordner · Profile · Plugins ·
        #          Aktualisieren · Sicherung · Einstellungen
        folder_btn_m = _add_btn("archives.svg", tr("toolbar.folders") + " ▾")
        folder_btn_m.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        folder_menu_m = QMenu(bar)
        folder_menu_m.addAction(tr("toolbar.open_game_folder"), lambda: _call_win("_open_game_folder"))
        folder_menu_m.addAction(tr("toolbar.open_mygames_folder"), lambda: _call_win("_open_mygames_folder"))
        folder_menu_m.addAction(tr("toolbar.open_saves_folder"), lambda: _call_win("_open_saves_folder"))
        folder_menu_m.addAction(tr("toolbar.open_ini_folder"), lambda: _call_win("_open_ini_folder"))
        folder_menu_m.addAction(tr("toolbar.open_instance_folder"), lambda: _call_win("_open_instance_folder"))
        folder_menu_m.addAction(tr("toolbar.open_mods_folder"), lambda: _call_win("_open_mods_folder"))
        folder_menu_m.addAction(tr("toolbar.open_profile_folder"), lambda: _call_win("_open_profile_folder"))
        folder_menu_m.addAction(tr("toolbar.open_downloads_folder"), lambda: _call_win("_open_downloads_folder"))
        folder_menu_m.addSeparator()
        folder_menu_m.addAction(tr("toolbar.open_ao_install_folder"), lambda: _call_win("_open_ao_install_folder"))
        folder_menu_m.addAction(tr("toolbar.open_ao_plugins_folder"), lambda: _call_win("_open_ao_plugins_folder"))
        folder_menu_m.addAction(tr("toolbar.open_ao_styles_folder"), lambda: _call_win("_open_ao_styles_folder"))
        folder_menu_m.addAction(tr("toolbar.open_ao_logs_folder"), lambda: _call_win("_open_ao_logs_folder"))
        folder_btn_m.setMenu(folder_menu_m)

        profiles_btn = _add_btn("profiles.svg", tr("toolbar.profiles"))
        def _profiles_hint():
            win = bar.window()
            if win is not None:
                from anvil.widgets.toast import Toast
                Toast(win, tr("toast.profiles_hint"))
        profiles_btn.clicked.connect(_profiles_hint)

    plugin_btn = _add_btn(
        "plugin.svg",
        tr("toolbar.plugins") + " ▾" if modern else tr("menu.plugin_menu"))
    plugin_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    plugin_menu = QMenu(bar)
    plugin_menu.addAction(tr("menu.create_plugin"), lambda: _call_win("_on_create_plugin"))
    plugin_menu.addAction(tr("menu.edit_plugin"), lambda: _call_win("_on_edit_plugin"))
    plugin_btn.setMenu(plugin_menu)

    if not modern:
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

    refresh_btn = _add_btn(
        "refresh.svg",
        tr("toolbar.refresh") if modern else tr("menu.reload"))
    def _on_refresh():
        win = bar.window()
        if win and hasattr(win, "_on_menu_refresh"):
            win._on_menu_refresh()

    refresh_btn.clicked.connect(_on_refresh)

    if modern:
        # Vorlage: Sicherung ▾ (Erstellen / Wiederherstellen)
        backup_btn = _add_btn("backup.svg", tr("toolbar.backup_menu") + " ▾")
        backup_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        backup_menu = QMenu(bar)
        backup_menu.addAction(
            tr("tooltip.create_backup"), lambda: _call_win("_create_backup"))
        backup_menu.addAction(
            tr("tooltip.restore_backup"), lambda: _call_win("_restore_backup"))
        backup_menu.addSeparator()
        backup_menu.addAction(
            tr("storage.action"), lambda: _call_win("_on_storage_migration"))
        backup_btn.setMenu(backup_menu)

    if not modern:
        exec_btn = _add_btn("executables.svg", "Executables")
        exec_btn.clicked.connect(lambda: ExecutablesDialog(bar.window()).exec())

    if not modern:
        tools_btn = _add_btn("tools.svg", "Tools")
        tools_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        tools_menu = QMenu(bar)
        tools_menu.addAction(tr("menu.executables"), lambda: _call_win("_on_menu_executables"))
        tools_menu.addSeparator()
        tools_menu.addAction(tr("menu.reshade_wizard"), lambda: _call_win("_on_reshade_wizard"))
        tools_menu.addAction(tr("storage.action"), lambda: _call_win("_on_storage_migration"))
        tools_menu.addSeparator()
        tools_menu.addAction(tr("menu.settings"), lambda: _call_win("_on_menu_settings"))
        tools_btn.setMenu(tools_menu)

    settings_btn = _add_btn(
        "settings.svg",
        tr("menu.settings").rstrip(".\u2026") if modern
        else tr("menu.settings"))

    def _on_settings():
        win = bar.window()
        if win and hasattr(win, "_on_menu_settings"):
            win._on_menu_settings()

    settings_btn.clicked.connect(_on_settings)

    # Proton Tools — externes Tool im Proton-Prefix starten (nur Steam)
    proton_btn = QToolButton(bar)
    proton_btn.setIcon(_icon("proton.svg"))
    proton_btn.setToolTip("Proton Tools")
    proton_btn.setText("Proton Tools")
    proton_action = bar.addWidget(proton_btn)
    proton_action.setVisible(False)

    def _on_proton_clicked(checked=False):
        win = bar.window()
        if win and hasattr(win, "_rebuild_proton_menu"):
            menu = QMenu(proton_btn)
            win._rebuild_proton_menu(menu)
            menu.exec(proton_btn.mapToGlobal(proton_btn.rect().bottomLeft()))

    proton_btn.clicked.connect(_on_proton_clicked)

    bar.proton_btn = proton_btn
    bar.proton_action = proton_action

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

    # Script Merger Button (Witcher 3-spezifisch, standardmäßig unsichtbar)
    merger_sep = bar.addSeparator()
    merger_sep.setVisible(False)

    merger_btn = QToolButton(bar)
    merger_btn.setIcon(_icon("tools.svg"))
    merger_btn.setToolTip(tr("toolbar.script_merger"))
    merger_btn.setText(tr("toolbar.script_merger"))
    merger_action = bar.addWidget(merger_btn)
    merger_action.setVisible(False)

    def _on_script_merger():
        win = bar.window()
        if win and hasattr(win, "_on_script_merger_clicked"):
            win._on_script_merger_clicked()

    merger_btn.clicked.connect(_on_script_merger)
    bar.merger_btn = merger_btn
    bar.merger_action = merger_action
    bar.merger_sep = merger_sep

    # Nativer Plugin-Sortierbutton (standardmäßig unsichtbar)
    plugin_sort_sep = bar.addSeparator()
    plugin_sort_sep.setVisible(False)

    plugin_sort_btn = QToolButton(bar)
    plugin_sort_btn.setIcon(_icon("sort.svg"))
    plugin_sort_btn.setToolTip(tr("toolbar.plugin_sort"))
    plugin_sort_btn.setText(tr("toolbar.plugin_sort"))
    plugin_sort_action = bar.addWidget(plugin_sort_btn)
    plugin_sort_action.setVisible(False)

    def _on_plugin_sort():
        win = bar.window()
        if win and hasattr(win, "_on_plugin_sort_clicked"):
            win._on_plugin_sort_clicked()

    plugin_sort_btn.clicked.connect(_on_plugin_sort)
    bar.plugin_sort_btn = plugin_sort_btn
    bar.plugin_sort_action = plugin_sort_action
    bar.plugin_sort_sep = plugin_sort_sep

    # Spacer: rechte Icons bündig rechts
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    bar.addWidget(spacer)

    # „＋ Mod installieren" — prominenter Akzent-Button (immer Text)
    install_btn = QToolButton(bar)
    install_btn.setObjectName("installModBtn")
    install_btn.setText("＋ " + tr("menu.install_mod").rstrip("."))
    install_btn.setToolTip(tr("menu.install_mod"))
    install_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    install_btn.clicked.connect(lambda checked=False: _call_win("_on_install_mod"))
    bar.addWidget(install_btn)
    bar.install_btn = install_btn

    # Rechts: Status-Icons (Herz/Update/Info nur klassisch — modern
    # stecken die Funktionen im Hilfe-Menü, Vorlage zeigt nur den Zähler)
    if not modern:
        donate_btn = _add_btn("endorse.svg", "Support / Donate")
        donate_btn.clicked.connect(lambda: DonateDialog(bar.window()).exec())

    notifications_btn = NotificationButton(bar)
    notifications_btn.setIcon(_icon("problems.svg"))
    notifications_btn.setToolTip(tr("status.notifications"))
    notifications_btn.setText(tr("status.notifications"))
    bar.notifications_action = bar.addWidget(notifications_btn)

    def _on_notifications_clicked(checked=False):
        win = bar.window()
        if win and hasattr(win, "_notification_center"):
            panel = NotificationPanel(win._notification_center, win)
            panel.show_under(notifications_btn)

    notifications_btn.clicked.connect(_on_notifications_clicked)
    bar.notifications_btn = notifications_btn

    if not modern:
        update_btn = _add_btn("update.svg", "Update")
        def _on_update_check():
            win = bar.window()
            if win and hasattr(win, "_update_checker"):
                win._update_checker.check()
        update_btn.clicked.connect(_on_update_check)

        info_btn = _add_btn("help.svg", "Info")
        info_btn.clicked.connect(lambda: _call_win("_on_about"))

    if modern:
        # Vorlage: Mod-Zähler rechts außen ("Aktiv:  x / y")
        from PySide6.QtWidgets import QLabel
        prefix = QLabel(tr("label.active"))
        prefix.setObjectName("toolbarActiveLabel")
        bar.addWidget(prefix)
        value = QLabel("0")
        value.setObjectName("toolbarActiveValue")
        bar.addWidget(value)
        bar.active_label = value

    return bar
