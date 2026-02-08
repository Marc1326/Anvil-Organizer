"""Hauptfenster: Menü, Toolbar, Profil-Leiste, Splitter 65:35, Statusbar."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QMessageBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt

from anvil.styles import get_stylesheet
from anvil.widgets.toolbar import create_toolbar
from anvil.widgets.profile_bar import ProfileBar
from anvil.widgets.mod_list import ModListView
from anvil.widgets.game_panel import GamePanel
from anvil.widgets.status_bar import StatusBarWidget
from anvil.dialogs import ModDetailDialog
from anvil.plugins.plugin_loader import PluginLoader
from anvil.core.instance_manager import InstanceManager
from anvil.widgets.instance_wizard import CreateInstanceWizard


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anvil Organizer v0.1.0")
        self.setMinimumSize(1000, 650)
        self.resize(1200, 750)
        self.setStyleSheet(get_stylesheet())

        # ── Plugin-System ─────────────────────────────────────────────
        self.plugin_loader = PluginLoader()
        self.plugin_loader.load_plugins()

        # ── Instanz-System ────────────────────────────────────────────
        self.instance_manager = InstanceManager()

        menubar = self.menuBar()
        fm = menubar.addMenu("Datei")
        fm.addAction("Öffnen").triggered.connect(_todo("Datei – Öffnen"))
        fm.addAction("Beenden").triggered.connect(self.close)
        menubar.addMenu("Ansicht").addAction("Ansicht").triggered.connect(_todo("Ansicht"))
        menubar.addMenu("Werkzeuge").addAction("Werkzeuge").triggered.connect(_todo("Werkzeuge"))
        menubar.addMenu("Hilfe").addAction("Über Anvil Organizer").triggered.connect(self._on_about)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, create_toolbar(self))

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # MO2: Profil-Leiste NUR über der linken Seite, nicht über die ganze Breite
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(ProfileBar(self))
        self._mod_list_view = ModListView()
        self._mod_list_view._tree.doubleClicked.connect(self._on_mod_double_click)
        left_layout.addWidget(self._mod_list_view)
        splitter.addWidget(left_pane)
        self._game_panel = GamePanel()
        splitter.addWidget(self._game_panel)
        splitter.setSizes([780, 420])
        main_layout.addWidget(splitter)

        self._status_bar = StatusBarWidget(self)
        self.setStatusBar(self._status_bar)

        # ── Erster Start / Instanz laden ──────────────────────────────
        self._check_first_start()

    # ── Instance switching ────────────────────────────────────────────

    def _check_first_start(self) -> None:
        """Open wizard on first start or load current instance."""
        if not self.instance_manager.list_instances():
            # No instances yet — open wizard directly
            wizard = CreateInstanceWizard(
                self, self.instance_manager, self.plugin_loader,
            )
            wizard.exec()
            if wizard.created_instance:
                self.switch_instance(wizard.created_instance)
                return

        # Load current instance (if any)
        current = self.instance_manager.current_instance()
        if current:
            self._apply_instance(current)
        else:
            self._status_bar.clear_instance()

    def switch_instance(self, instance_name: str) -> None:
        """Switch to a different instance and update all UI components.

        Called by the toolbar after the instance manager dialog closes.

        Args:
            instance_name: Name of the instance to switch to.
        """
        self.instance_manager.set_current_instance(instance_name)
        self._apply_instance(instance_name)

    def _apply_instance(self, instance_name: str) -> None:
        """Load instance data and update all widgets.

        Args:
            instance_name: Name of the instance to apply.
        """
        data = self.instance_manager.load_instance(instance_name)
        if not data:
            self.setWindowTitle("Anvil Organizer v0.1.0")
            self._game_panel.update_game("Kein Spiel ausgewählt", None)
            self._mod_list_view.clear_mods()
            self._status_bar.clear_instance()
            return

        game_name = data.get("game_name", instance_name)
        short_name = data.get("game_short_name", "")
        store = data.get("detected_store", "")
        game_path_str = data.get("game_path", "")

        # Find the game plugin and path
        game_path: Path | None = None
        if game_path_str:
            p = Path(game_path_str)
            if p.is_dir():
                game_path = p

        plugin = self.plugin_loader.get_game(short_name) if short_name else None

        # 1. Title
        self.setWindowTitle(f"{game_name} \u2013 Anvil Organizer v0.1.0")

        # 2. Game panel — real directory contents + executables
        self._game_panel.update_game(game_name, game_path, plugin)

        # 3. Mod list — clear (real mods come in Phase 3)
        self._mod_list_view.clear_mods()

        # 4. Status bar
        self._status_bar.update_instance(game_name, short_name, store)

    # ── Other slots ───────────────────────────────────────────────────

    def _on_mod_double_click(self):
        mod_name = self._mod_list_view.get_current_mod_name()
        if mod_name:
            ModDetailDialog(self, mod_name=mod_name).exec()

    def _on_about(self):
        QMessageBox.about(self, "Über Anvil Organizer", "Anvil Organizer v0.1.0\n\nPlatzhalter-GUI.")
