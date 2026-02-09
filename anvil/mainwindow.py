"""Hauptfenster: Menü, Toolbar, Profil-Leiste, Splitter 65:35, Statusbar."""

from __future__ import annotations

from pathlib import Path

import shutil

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QMessageBox,
    QSizePolicy,
    QFileDialog,
    QDialog,
    QMenu,
    QInputDialog,
    QTextEdit,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction

from anvil.styles import get_stylesheet
from anvil.widgets.toolbar import create_toolbar
from anvil.widgets.profile_bar import ProfileBar
from anvil.widgets.mod_list import ModListView
from anvil.widgets.game_panel import GamePanel
from anvil.widgets.status_bar import StatusBarWidget
from anvil.dialogs import ModDetailDialog
from anvil.dialogs.quick_install_dialog import QuickInstallDialog
from anvil.dialogs.query_overwrite_dialog import QueryOverwriteDialog, OverwriteAction
from anvil.plugins.plugin_loader import PluginLoader
from anvil.core.instance_manager import InstanceManager
from anvil.core.icon_manager import IconManager
from anvil.core.mod_entry import scan_mods_directory
from anvil.core.mod_installer import ModInstaller, SUPPORTED_EXTENSIONS
from anvil.core.mod_list_io import (
    add_mod_to_modlist, write_modlist, remove_mod_from_modlist,
    rename_mod_in_modlist,
)
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
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter = self._splitter
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._profile_bar = ProfileBar(self)
        left_layout.addWidget(self._profile_bar)
        self._mod_list_view = ModListView()
        self._mod_list_view._tree.doubleClicked.connect(self._on_mod_double_click)
        self._mod_list_view.context_menu_requested.connect(self._on_mod_context_menu)
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
        self._mod_list_view.archives_dropped.connect(
            self._on_archives_dropped, Qt.ConnectionType.QueuedConnection,
        )
        self._game_panel.install_requested.connect(self._on_downloads_install)

        # ── Deferred tab header restore ──────────────────────────────
        self._pending_tab_states: dict[int, tuple] = {}
        self._game_panel._tabs.currentChanged.connect(self._on_tab_changed)

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

        # 6. Restore saved column widths / splitter (after data is populated)
        self._restore_ui_state()

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
        """Install one or more archives as mods.

        MO2-Pattern (testOverwrite):
        - Name berechnen, prüfen ob .mods/{name} existiert
        - NEIN → direkt installieren, kein Dialog
        - JA  → QuickInstallDialog → QueryOverwriteDialog falls nötig
        """
        installer = ModInstaller(self._current_instance_path)
        installed = []

        for archive in archives:
            best, variants = installer.suggest_names(archive)
            mod_name = best
            dest = installer.mods_path / mod_name

            # Nur bei Duplikat: Dialog zeigen (MO2 testOverwrite-Pattern)
            if dest.exists():
                while True:
                    dlg = QuickInstallDialog(variants, mod_name, self)
                    if dlg.exec() != QDialog.DialogCode.Accepted:
                        mod_name = None
                        break
                    mod_name = dlg.mod_name()
                    if not mod_name:
                        continue  # empty name → show dialog again
                    dest = installer.mods_path / mod_name
                    if not dest.exists():
                        break  # neuer Name, kein Konflikt mehr
                    # Immer noch Duplikat → QueryOverwriteDialog
                    ovr = QueryOverwriteDialog(mod_name, self)
                    if ovr.exec() != QDialog.DialogCode.Accepted:
                        mod_name = None
                        break
                    action = ovr.action()
                    if action == OverwriteAction.RENAME:
                        continue  # zurück zum QuickInstallDialog
                    elif action == OverwriteAction.REPLACE:
                        shutil.rmtree(dest)
                    # MERGE: dest bleibt, Dateien werden reingeschrieben
                    break

            if not mod_name:
                continue  # user cancelled

            # Install
            mod_path = installer.install_from_archive(archive, mod_name)
            if mod_path:
                add_mod_to_modlist(self._current_profile_path, mod_path.name)
                installed.append(mod_path.name)
            else:
                QMessageBox.warning(
                    self, "Installation fehlgeschlagen",
                    f"Mod \"{mod_name}\" konnte nicht installiert werden.\n"
                    "Prüfe ob das Archiv gültig ist und die nötigen Tools installiert sind.",
                )

        if not installed:
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

    # ── Mod list context menu ──────────────────────────────────────

    def _on_mod_context_menu(self, global_pos) -> None:
        """Build and show the mod list context menu (MO2 structure)."""
        if not self._current_instance_path:
            return

        selected_rows = self._mod_list_view.get_selected_source_rows()
        has_selection = len(selected_rows) > 0
        single = len(selected_rows) == 1

        menu = QMenu(self)

        # ── Alle Mods (Submenu) ────────────────────────────────────
        all_mods_menu = menu.addMenu("Alle Mods")
        all_mods_menu.setEnabled(False)
        menu.addSeparator()

        # ── Kategorie ─────────────────────────────────────────────
        act = menu.addAction("Kategorie ändern")
        act.setEnabled(False)
        act = menu.addAction("Primäre Kategorie")
        act.setEnabled(False)
        menu.addSeparator()

        # ── Updates ───────────────────────────────────────────────
        act = menu.addAction("Versionsschema ändern")
        act.setEnabled(False)
        act = menu.addAction("Update-Prüfung erzwingen")
        act.setEnabled(False)
        act = menu.addAction("Update ignorieren")
        act.setEnabled(False)
        menu.addSeparator()

        # ── Aktivieren / Deaktivieren ─────────────────────────────
        act_enable = menu.addAction("Aktiviere Ausgewählte")
        act_enable.setEnabled(has_selection)
        act_disable = menu.addAction("Deaktiviere Ausgewählte")
        act_disable.setEnabled(has_selection)
        menu.addSeparator()

        # ── Senden an (Submenu) ───────────────────────────────────
        send_to_menu = menu.addMenu("Senden an...")
        send_to_menu.setEnabled(False)
        menu.addSeparator()

        # ── Mod-Aktionen ──────────────────────────────────────────
        act_rename = menu.addAction("Mod umbenennen...")
        act_rename.setEnabled(single)
        act_reinstall = menu.addAction("Mod neu installieren")
        act_reinstall.setEnabled(single)
        act_remove = menu.addAction("Mod entfernen...")
        act_remove.setEnabled(has_selection)
        act = menu.addAction("Backup erstellen")
        act.setEnabled(False)
        menu.addSeparator()

        # ── Farbe ─────────────────────────────────────────────────
        act = menu.addAction("Farbe wählen...")
        act.setEnabled(False)
        menu.addSeparator()

        # ── Nexus / Explorer ──────────────────────────────────────
        act = menu.addAction("Auf Nexus besuchen")
        act.setEnabled(False)
        act_explorer = menu.addAction("Im Explorer öffnen")
        act_explorer.setEnabled(single)
        menu.addSeparator()

        # ── Informationen ─────────────────────────────────────────
        act_info = menu.addAction("Informationen...")
        act_info.setEnabled(single)

        # ── Execute ───────────────────────────────────────────────
        chosen = menu.exec(global_pos)
        if not chosen:
            return

        if chosen == act_enable:
            self._ctx_enable_selected(selected_rows, True)
        elif chosen == act_disable:
            self._ctx_enable_selected(selected_rows, False)
        elif chosen == act_rename:
            self._ctx_rename_mod(selected_rows[0])
        elif chosen == act_reinstall:
            self._ctx_reinstall_mod(selected_rows[0])
        elif chosen == act_remove:
            self._ctx_remove_mods(selected_rows)
        elif chosen == act_explorer:
            self._ctx_open_explorer(selected_rows[0])
        elif chosen == act_info:
            self._ctx_show_info(selected_rows[0])

    # ── Context menu actions ───────────────────────────────────────

    def _ctx_enable_selected(self, rows: list[int], enabled: bool) -> None:
        """Enable or disable selected mods."""
        model = self._mod_list_view.source_model()
        for row in rows:
            if 0 <= row < len(self._current_mod_entries):
                self._current_mod_entries[row].enabled = enabled
                model._rows[row].enabled = enabled
        model.dataChanged.emit(
            model.index(0, 0),
            model.index(model.rowCount() - 1, 0),
            [Qt.ItemDataRole.CheckStateRole],
        )
        self._write_current_modlist()
        self._update_active_count()

    def _ctx_rename_mod(self, row: int) -> None:
        """Rename a mod (folder + modlist.txt)."""
        if row >= len(self._current_mod_entries):
            return
        entry = self._current_mod_entries[row]
        old_name = entry.name

        new_name, ok = QInputDialog.getText(
            self, "Mod umbenennen", "Neuer Name:", text=old_name,
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()

        old_path = self._current_instance_path / ".mods" / old_name
        new_path = self._current_instance_path / ".mods" / new_name

        if new_path.exists():
            QMessageBox.warning(
                self, "Umbenennen fehlgeschlagen",
                f"Ein Mod mit dem Namen \"{new_name}\" existiert bereits.",
            )
            return

        try:
            old_path.rename(new_path)
        except OSError as exc:
            QMessageBox.warning(
                self, "Umbenennen fehlgeschlagen", str(exc),
            )
            return

        rename_mod_in_modlist(self._current_profile_path, old_name, new_name)
        self._reload_mod_list()
        self.statusBar().showMessage(f"Umbenannt: {old_name} → {new_name}", 5000)

    def _ctx_reinstall_mod(self, row: int) -> None:
        """Reinstall a mod from its archive in .downloads/."""
        if row >= len(self._current_mod_entries):
            return
        entry = self._current_mod_entries[row]
        downloads_path = self._current_instance_path / ".downloads"

        if not downloads_path.is_dir():
            QMessageBox.warning(
                self, "Neu installieren",
                "Kein Downloads-Ordner gefunden.",
            )
            return

        # Find matching archive by mod name
        archive = None
        mod_lower = entry.name.lower()
        for f in downloads_path.iterdir():
            if f.is_file() and f.suffix.lower() in ('.zip', '.rar', '.7z'):
                if mod_lower in f.stem.lower():
                    archive = f
                    break

        if not archive:
            QMessageBox.information(
                self, "Neu installieren",
                f"Kein passendes Archiv für \"{entry.name}\" in .downloads/ gefunden.",
            )
            return

        self._install_archives([archive])

    def _ctx_remove_mods(self, rows: list[int]) -> None:
        """Remove selected mods (folder + modlist.txt entry)."""
        names = []
        for row in rows:
            if row < len(self._current_mod_entries):
                names.append(self._current_mod_entries[row].name)
        if not names:
            return

        if len(names) == 1:
            msg = f"Mod \"{names[0]}\" wirklich löschen?\n\nDer Mod-Ordner wird unwiderruflich gelöscht."
        else:
            msg = f"{len(names)} Mods wirklich löschen?\n\n" + "\n".join(f"  • {n}" for n in names) + "\n\nDie Mod-Ordner werden unwiderruflich gelöscht."

        reply = QMessageBox.question(
            self, "Mod entfernen", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for name in names:
            mod_path = self._current_instance_path / ".mods" / name
            if mod_path.is_dir():
                shutil.rmtree(mod_path)
            remove_mod_from_modlist(self._current_profile_path, name)

        self._reload_mod_list()
        self.statusBar().showMessage(f"Entfernt: {', '.join(names)}", 5000)

    def _ctx_open_explorer(self, row: int) -> None:
        """Open the mod folder in the file manager."""
        import subprocess
        if row >= len(self._current_mod_entries):
            return
        mod_path = self._current_instance_path / ".mods" / self._current_mod_entries[row].name
        if mod_path.is_dir():
            subprocess.Popen(["xdg-open", str(mod_path)])

    def _ctx_show_info(self, row: int) -> None:
        """Show mod information dialog."""
        if row >= len(self._current_mod_entries):
            return
        entry = self._current_mod_entries[row]
        mod_path = self._current_instance_path / ".mods" / entry.name

        # Collect info
        info_lines = [
            f"Name: {entry.display_name or entry.name}",
            f"Ordner: {entry.name}",
            f"Pfad: {mod_path}",
            f"Aktiviert: {'Ja' if entry.enabled else 'Nein'}",
            f"Version: {entry.version or '—'}",
            f"Kategorie: {entry.category or '—'}",
            f"Priorität: {entry.priority}",
        ]

        # Folder size
        if mod_path.is_dir():
            total = sum(f.stat().st_size for f in mod_path.rglob("*") if f.is_file())
            if total < 1024 * 1024:
                size_str = f"{total / 1024:.1f} KB"
            else:
                size_str = f"{total / (1024 * 1024):.1f} MB"
            info_lines.append(f"Größe: {size_str}")

        # meta.ini content
        meta_ini = mod_path / "meta.ini"
        if meta_ini.is_file():
            try:
                meta_text = meta_ini.read_text(encoding="utf-8")
                info_lines.append(f"\n── meta.ini ──\n{meta_text}")
            except OSError:
                pass

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Informationen: {entry.display_name or entry.name}")
        dlg.setMinimumSize(700, 550)
        dlg.resize(750, 600)
        layout = QVBoxLayout(dlg)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("QTextEdit { font-size: 15px; font-family: monospace; }")
        text_edit.setPlainText("\n".join(info_lines))
        layout.addWidget(text_edit)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)
        dlg.exec()

    def _reload_mod_list(self) -> None:
        """Reload mod list from disk and update UI."""
        self._current_mod_entries = scan_mods_directory(
            self._current_instance_path, self._current_profile_path,
        )
        mod_rows = [mod_entry_to_row(e) for e in self._current_mod_entries]
        self._mod_list_view.source_model().set_mods(mod_rows)
        self._update_active_count()

    # ── UI state persistence ───────────────────────────────────────

    @staticmethod
    def _settings() -> QSettings:
        """Return QSettings with a fixed path independent of Flatpak sandbox."""
        path = str(Path.home() / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf")
        return QSettings(path, QSettings.Format.IniFormat)

    def _save_ui_state(self) -> None:
        """Persist splitter, mod-list and downloads column widths."""
        s = self._settings()
        s.setValue("splitter/state", self._splitter.saveState())
        s.setValue("mod_list/header_state", self._mod_list_view.header().saveState())
        s.setValue("downloads/header_state",
                   self._game_panel._dl_table.horizontalHeader().saveState())
        s.setValue("data/header_state",
                   self._game_panel._data_tree.header().saveState())
        s.setValue("saves/header_state",
                   self._game_panel._saves_tree.header().saveState())
        s.sync()

    def _restore_ui_state(self) -> None:
        """Restore splitter, mod-list and tab column widths.

        Tab headers (Daten/Spielstände/Downloads) are restored deferred:
        hidden tabs ignore restoreState(), so we store the bytes and
        apply them when the tab becomes visible for the first time.
        """
        s = self._settings()
        val = s.value("splitter/state")
        if val:
            self._splitter.restoreState(val)
        val = s.value("mod_list/header_state")
        if val:
            self._mod_list_view.header().restoreState(val)

        # Tab headers: deferred restore (hidden tabs ignore restoreState)
        tab_map = {
            0: ("data/header_state", lambda: self._game_panel._data_tree.header()),
            1: ("saves/header_state", lambda: self._game_panel._saves_tree.header()),
            2: ("downloads/header_state", lambda: self._game_panel._dl_table.horizontalHeader()),
        }
        self._pending_tab_states.clear()
        for tab_idx, (key, header_fn) in tab_map.items():
            val = s.value(key)
            if val:
                self._pending_tab_states[tab_idx] = (val, header_fn)

        # Restore the currently active tab immediately (it's visible)
        active = self._game_panel._tabs.currentIndex()
        if active in self._pending_tab_states:
            val, header_fn = self._pending_tab_states.pop(active)
            header_fn().restoreState(val)

    def _on_tab_changed(self, index: int) -> None:
        """Restore header state when a tab becomes visible for the first time."""
        if index in self._pending_tab_states:
            val, header_fn = self._pending_tab_states.pop(index)
            header_fn().restoreState(val)

    def closeEvent(self, event) -> None:
        self._save_ui_state()
        super().closeEvent(event)

    # ── Other slots ───────────────────────────────────────────────────

    def _on_about(self):
        QMessageBox.about(self, "Über Anvil Organizer", "Anvil Organizer v0.1.0\n\nPlatzhalter-GUI.")
