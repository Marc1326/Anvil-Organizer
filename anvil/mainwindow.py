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
    QFileDialog,
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
from anvil.core.icon_manager import IconManager
from anvil.core.mod_entry import scan_mods_directory
from anvil.core.mod_installer import ModInstaller, SUPPORTED_EXTENSIONS
from anvil.core.mod_list_io import add_mod_to_modlist, write_modlist
from anvil.models.mod_list_model import mod_entry_to_row
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
        self.icon_manager = IconManager()

        menubar = self.menuBar()
        fm = menubar.addMenu("Datei")
        fm.addAction("Mod installieren...").triggered.connect(self._on_install_mod)
        fm.addSeparator()
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
        self._profile_bar = ProfileBar(self)
        left_layout.addWidget(self._profile_bar)
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

        # ── Mod state ─────────────────────────────────────────────────
        self._current_mod_entries = []
        self._current_profile_path: Path | None = None
        self._current_instance_path: Path | None = None

        # Connect model signals for persistence
        model = self._mod_list_view.source_model()
        model.mod_toggled.connect(self._on_mod_toggled)
        model.mods_reordered.connect(self._on_mods_reordered)
        self._mod_list_view.archives_dropped.connect(self._on_archives_dropped)
        self._game_panel.install_requested.connect(self._on_downloads_install)

        # ── Erster Start / Instanz laden ──────────────────────────────
        self._check_first_start()

    # ── Instance switching ────────────────────────────────────────────

    def _check_first_start(self) -> None:
        """Open wizard on first start or load current instance."""
        if not self.instance_manager.list_instances():
            # No instances yet — open wizard directly
            wizard = CreateInstanceWizard(
                self, self.instance_manager, self.plugin_loader,
                self.icon_manager,
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
            self._current_mod_entries = []
            self._current_profile_path = None
            self._current_instance_path = None
            self._update_active_count()
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

        # 0. Preload icons in background
        exe_binaries = [e["binary"] for e in plugin.executables()] if plugin else []
        worker = self.icon_manager.preload_icons(short_name, exe_binaries) if short_name else None
        if worker is not None:
            worker.icon_ready.connect(self._on_icon_ready)
            worker.start()

        # 1. Title
        self.setWindowTitle(f"{game_name} \u2013 Anvil Organizer v0.1.0")

        # 2. Game panel — real directory contents + executables + icons
        self._game_panel.update_game(game_name, game_path, plugin, self.icon_manager, short_name)

        # 3. Mod list — scan filesystem and populate
        self._current_instance_path = self.instance_manager.instances_path() / instance_name
        instance_path = self._current_instance_path
        profile_name = data.get("selected_profile", "Default")
        self._current_profile_path = instance_path / ".profiles" / profile_name
        self._current_mod_entries = scan_mods_directory(instance_path, self._current_profile_path)
        mod_rows = [mod_entry_to_row(e) for e in self._current_mod_entries]
        self._mod_list_view.source_model().set_mods(mod_rows)
        self._update_active_count()

        # 4. Downloads tab
        self._game_panel.set_downloads_path(
            instance_path / ".downloads", instance_path / ".mods",
        )

        # 5. Status bar
        self._status_bar.update_instance(game_name, short_name, store)

    def _on_icon_ready(self, cache_key: str, pixmap) -> None:
        """Handle an icon that was downloaded in the background."""
        self.icon_manager.store_pixmap(cache_key, pixmap)
        self._game_panel.on_icon_ready(cache_key, pixmap)

    # ── Mod list persistence ─────────────────────────────────────────

    def _write_current_modlist(self) -> None:
        """Write the current mod entries to modlist.txt."""
        if self._current_profile_path is None:
            return
        mods = [(e.name, e.enabled) for e in self._current_mod_entries]
        write_modlist(self._current_profile_path, mods)

    def _on_mod_toggled(self, row: int, enabled: bool) -> None:
        """A mod checkbox was toggled — update entries and persist."""
        if 0 <= row < len(self._current_mod_entries):
            self._current_mod_entries[row].enabled = enabled
        self._write_current_modlist()
        self._update_active_count()

    def _on_mods_reordered(self) -> None:
        """Mods were reordered via drag & drop — sync entries and persist."""
        model = self._mod_list_view.source_model()
        # Rebuild _current_mod_entries from the model's new order
        new_entries = []
        for i in range(model.rowCount()):
            row_data = model._rows[i]
            # Find matching entry by display_name or folder name
            for entry in self._current_mod_entries:
                display = entry.display_name or entry.name
                if display == row_data.name and entry not in new_entries:
                    entry.priority = i
                    new_entries.append(entry)
                    break
        self._current_mod_entries = new_entries
        self._write_current_modlist()
        self._update_active_count()

    def _update_active_count(self) -> None:
        """Update the active mod counter in the profile bar."""
        count = sum(1 for e in self._current_mod_entries if e.enabled)
        self._profile_bar.update_active_count(count)

    # ── Mod installation ─────────────────────────────────────────────

    def _on_install_mod(self) -> None:
        """Menu: Datei → Mod installieren..."""
        if not self._current_instance_path:
            QMessageBox.warning(self, "Keine Instanz", "Bitte zuerst eine Instanz auswählen.")
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Mod-Archiv(e) auswählen",
            str(Path.home()),
            "Archive (*.zip *.rar *.7z);;Alle Dateien (*)",
        )
        if files:
            self._install_archives([Path(f) for f in files])

    def _on_archives_dropped(self, paths: list) -> None:
        """Handle archives dropped onto the mod list."""
        if not self._current_instance_path:
            return
        self._install_archives([Path(p) for p in paths])

    def _on_downloads_install(self, paths: list) -> None:
        """Handle install request from the Downloads tab."""
        if not self._current_instance_path:
            return
        self._install_archives([Path(p) for p in paths])
        self._game_panel.refresh_downloads()

    def _install_archives(self, archives: list[Path]) -> None:
        """Install one or more archives as mods."""
        installer = ModInstaller(self._current_instance_path)
        installed = []

        for archive in archives:
            mod_path = installer.install_from_archive(archive)
            if mod_path:
                add_mod_to_modlist(self._current_profile_path, mod_path.name)
                installed.append(mod_path.name)

        if not installed:
            QMessageBox.warning(
                self, "Installation fehlgeschlagen",
                "Kein Mod konnte installiert werden.\n"
                "Prüfe ob das Archiv gültig ist und die nötigen Tools installiert sind.",
            )
            return

        # Reload mod list
        self._current_mod_entries = scan_mods_directory(
            self._current_instance_path, self._current_profile_path,
        )
        mod_rows = [mod_entry_to_row(e) for e in self._current_mod_entries]
        self._mod_list_view.source_model().set_mods(mod_rows)
        self._update_active_count()

        names = ", ".join(installed)
        self.statusBar().showMessage(f"Installiert: {names}", 5000)

    # ── Other slots ───────────────────────────────────────────────────

    def _on_mod_double_click(self):
        mod_name = self._mod_list_view.get_current_mod_name()
        if mod_name:
            ModDetailDialog(self, mod_name=mod_name).exec()

    def _on_about(self):
        QMessageBox.about(self, "Über Anvil Organizer", "Anvil Organizer v0.1.0\n\nPlatzhalter-GUI.")
