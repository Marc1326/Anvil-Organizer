"""Neuer-Instanz-Wizard — QWizard mit 4 Seiten (MO2-Stil)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWizard,
    QWizardPage,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from anvil.core.instance_manager import InstanceManager
from anvil.plugins.plugin_loader import PluginLoader

# ── Style ─────────────────────────────────────────────────────────────

_WIZARD_STYLE = """
QWizard, QWizardPage, QWidget {
    background: #1C1C1C;
    color: #D3D3D3;
}
QLabel { background: transparent; }
QLineEdit, QListWidget {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 4px;
}
QListWidget::item { padding: 6px 4px; }
QListWidget::item:selected { background: #3D3D3D; color: #D3D3D3; }
QListWidget::item:hover { background: #2A2A2A; }
QPushButton {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 6px 16px;
}
QPushButton:hover { background: #2A2A2A; }
QCheckBox { background: transparent; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    background: #1C1C1C;
}
QCheckBox::indicator:checked { background: #4FC3F7; }
"""


# ── Page 1: Intro ─────────────────────────────────────────────────────


class _IntroPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Erstelle eine neue Instanz")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        text = QLabel(
            "Eine Instanz ist ein vollständiges Set von Mods, Downloads, "
            "Profilen und Konfigurationen für ein Spiel.\n\n"
            "Jedes Spiel muss in seiner eigenen Instanz verwaltet werden. "
            "Anvil Organizer kann problemlos zwischen Instanzen wechseln."
        )
        text.setWordWrap(True)
        text.setStyleSheet("font-size: 13px; line-height: 1.5;")
        layout.addWidget(text)

        layout.addStretch()

        self._skip_cb = QCheckBox("Zeige diese Seite nie wieder")
        layout.addWidget(self._skip_cb)


# ── Page 2: Game Select ───────────────────────────────────────────────


class _GameSelectPage(QWizardPage):
    def __init__(self, plugin_loader: PluginLoader, parent=None):
        super().__init__(parent)
        self._pl = plugin_loader
        self.setTitle("Wähle ein Spiel")

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        hint = QLabel("Wähle das Spiel für das du eine Instanz erstellen möchtest:")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self.completeChanged)
        layout.addWidget(self._list)

        self._italic_font = QFont()
        self._italic_font.setItalic(True)

    def initializePage(self) -> None:
        self._list.clear()

        # Installed games first
        for plugin in self._pl.installed_games():
            gd = plugin.gameDirectory()
            store = plugin.detectedStore() or ""
            detail = f"{store}  —  {gd}" if gd else store
            text = f"{plugin.GameName}  —  {detail}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, plugin.GameShortName)
            self._list.addItem(item)

        # Non-installed games
        for plugin in self._pl.all_plugins():
            if plugin.isInstalled():
                continue
            text = f"{plugin.GameName}  —  nicht erkannt"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, plugin.GameShortName)
            item.setFont(self._italic_font)
            item.setForeground(Qt.GlobalColor.darkGray)
            self._list.addItem(item)

        # Pre-select first
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def isComplete(self) -> bool:
        return self._list.currentItem() is not None

    def selected_short_name(self) -> str | None:
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)


# ── Page 3: Configure ─────────────────────────────────────────────────


class _ConfigPage(QWizardPage):
    def __init__(
        self,
        plugin_loader: PluginLoader,
        instance_manager: InstanceManager,
        game_select_page: _GameSelectPage,
        parent=None,
    ):
        super().__init__(parent)
        self._pl = plugin_loader
        self._im = instance_manager
        self._game_page = game_select_page
        self.setTitle("Instanz-Name und Pfade")

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(10)

        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(self._on_name_changed)
        form.addRow("Instanz-Name:", self._name_edit)

        self._path_label = QLabel("")
        self._path_label.setStyleSheet("color: #808080;")
        form.addRow("Spielpfad:", self._path_label)

        self._dir_label = QLabel("")
        self._dir_label.setStyleSheet("color: #808080;")
        form.addRow("Instanz-Ordner:", self._dir_label)

        layout.addLayout(form)

        self._warning = QLabel("")
        self._warning.setStyleSheet("color: #FF6B6B; font-weight: bold;")
        self._warning.setWordWrap(True)
        self._warning.hide()
        layout.addWidget(self._warning)

        layout.addStretch()

    def initializePage(self) -> None:
        short = self._game_page.selected_short_name()
        plugin = self._pl.get_game(short) if short else None

        if plugin:
            self._name_edit.setText(plugin.GameName)
            gd = plugin.gameDirectory()
            self._path_label.setText(str(gd) if gd else "nicht erkannt")
        else:
            self._name_edit.setText("")
            self._path_label.setText("—")

        self._update_dir_label()

    def isComplete(self) -> bool:
        name = self._name_edit.text().strip()
        if not name:
            return False
        # Check duplicate
        existing = {inst["name"] for inst in self._im.list_instances()}
        if name in existing:
            return False
        return True

    def instance_name(self) -> str:
        return self._name_edit.text().strip()

    def _on_name_changed(self, text: str) -> None:
        self._update_dir_label()

        name = text.strip()
        if not name:
            self._warning.hide()
            self.completeChanged.emit()
            return

        existing = {inst["name"] for inst in self._im.list_instances()}
        if name in existing:
            self._warning.setText(
                f'Eine Instanz mit dem Namen "{name}" existiert bereits.'
            )
            self._warning.show()
        else:
            self._warning.hide()

        self.completeChanged.emit()

    def _update_dir_label(self) -> None:
        name = self._name_edit.text().strip()
        if name:
            path = self._im.instances_path() / name
            self._dir_label.setText(str(path))
        else:
            self._dir_label.setText("—")


# ── Page 4: Summary ───────────────────────────────────────────────────


class _SummaryPage(QWizardPage):
    def __init__(
        self,
        plugin_loader: PluginLoader,
        instance_manager: InstanceManager,
        game_select_page: _GameSelectPage,
        config_page: _ConfigPage,
        parent=None,
    ):
        super().__init__(parent)
        self._pl = plugin_loader
        self._im = instance_manager
        self._game_page = game_select_page
        self._config_page = config_page
        self.setTitle("Instanz erstellen?")
        self.setCommitPage(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        hint = QLabel("Folgende Instanz wird erstellt:")
        hint.setStyleSheet("font-size: 13px;")
        layout.addWidget(hint)

        self._form = QFormLayout()
        self._form.setSpacing(8)

        self._game_label = QLabel()
        self._form.addRow("Spiel:", self._game_label)
        self._name_label = QLabel()
        self._form.addRow("Instanz-Name:", self._name_label)
        self._store_label = QLabel()
        self._form.addRow("Store:", self._store_label)
        self._path_label = QLabel()
        self._path_label.setWordWrap(True)
        self._form.addRow("Spielpfad:", self._path_label)
        self._dir_label = QLabel()
        self._dir_label.setWordWrap(True)
        self._form.addRow("Instanz-Ordner:", self._dir_label)

        layout.addLayout(self._form)

        self._dirs_label = QLabel(
            "Folgende Ordner werden erstellt:\n"
            "  .mods/  .downloads/  .profiles/Default/  .overwrite/"
        )
        self._dirs_label.setStyleSheet("color: #808080; font-size: 12px;")
        layout.addWidget(self._dirs_label)

        layout.addStretch()

    def initializePage(self) -> None:
        short = self._game_page.selected_short_name()
        plugin = self._pl.get_game(short) if short else None
        name = self._config_page.instance_name()

        if plugin:
            self._game_label.setText(plugin.GameName)
            self._store_label.setText(plugin.detectedStore() or "nicht erkannt")
            gd = plugin.gameDirectory()
            self._path_label.setText(str(gd) if gd else "nicht erkannt")
        else:
            self._game_label.setText("—")
            self._store_label.setText("—")
            self._path_label.setText("—")

        self._name_label.setText(name)
        self._dir_label.setText(str(self._im.instances_path() / name))


# ── Wizard ────────────────────────────────────────────────────────────


class CreateInstanceWizard(QWizard):
    """Multi-page wizard for creating a new game instance."""

    # Set to the instance name after successful creation, or None.
    created_instance: str | None = None

    def __init__(
        self,
        parent=None,
        instance_manager: InstanceManager | None = None,
        plugin_loader: PluginLoader | None = None,
    ):
        super().__init__(parent)
        self._im = instance_manager
        self._pl = plugin_loader
        self.created_instance = None

        self.setWindowTitle("Neue Instanz erstellen")
        self.setMinimumSize(600, 450)
        self.setStyleSheet(_WIZARD_STYLE)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        # Button text
        self.setButtonText(QWizard.WizardButton.BackButton, "< Zurück")
        self.setButtonText(QWizard.WizardButton.NextButton, "Nächster >")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Abbrechen")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Erstellen")
        self.setButtonText(QWizard.WizardButton.CommitButton, "Erstellen")

        # Pages
        self._intro_page = _IntroPage()
        self.addPage(self._intro_page)

        self._game_page = _GameSelectPage(self._pl)
        self.addPage(self._game_page)

        self._config_page = _ConfigPage(self._pl, self._im, self._game_page)
        self.addPage(self._config_page)

        self._summary_page = _SummaryPage(
            self._pl, self._im, self._game_page, self._config_page,
        )
        self.addPage(self._summary_page)

    def accept(self) -> None:
        """Create the instance when the wizard finishes."""
        if self._im is None or self._pl is None:
            super().accept()
            return

        short = self._game_page.selected_short_name()
        plugin = self._pl.get_game(short) if short else None
        name = self._config_page.instance_name()

        if not plugin or not name:
            super().accept()
            return

        try:
            self._im.create_instance(plugin, name)
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self,
                "Fehler",
                f"Instanz konnte nicht erstellt werden:\n{exc}",
            )
            return

        # Auto-set as current if first instance
        if len(self._im.list_instances()) == 1:
            self._im.set_current_instance(name)

        self.created_instance = name
        super().accept()
