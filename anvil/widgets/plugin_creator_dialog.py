"""Dialog zum Erstellen neuer Game-Plugins.

Bietet ein einfaches Formular in dem der User alle Daten eintraegt
die fuer ein Game-Plugin noetig sind — ohne Python-Code schreiben
zu muessen.  Der Dialog generiert die .py-Datei und optional eine
JSON-Datei fuer Framework-Definitionen.
"""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QComboBox,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from anvil.core.translator import tr


# Pfad fuer User-Plugins
_USER_PLUGINS_DIR = Path.home() / ".anvil-organizer" / "plugins" / "games"


class PluginCreatorDialog(QDialog):
    """Wizard-Dialog zum Erstellen eines neuen Game-Plugins."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("plugin_creator.title"))
        self.setMinimumWidth(620)
        self.setMinimumHeight(520)
        self._build_ui()

    # ── UI aufbauen ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Pflichtfelder ────────────────────────────────────────
        game_group = QGroupBox(tr("plugin_creator.game_info"))
        form = QFormLayout(game_group)

        self._game_name = QLineEdit()
        self._game_name.setPlaceholderText("Skyrim Special Edition")
        form.addRow(tr("plugin_creator.game_name"), self._game_name)

        self._game_short = QLineEdit()
        self._game_short.setPlaceholderText("SkyrimSE")
        form.addRow(tr("plugin_creator.short_name"), self._game_short)

        self._game_binary = QLineEdit()
        self._game_binary.setPlaceholderText("SkyrimSE.exe")
        form.addRow(tr("plugin_creator.binary"), self._game_binary)

        self._steam_id = QLineEdit()
        self._steam_id.setPlaceholderText("489830")
        form.addRow(tr("plugin_creator.steam_id"), self._steam_id)

        self._data_path = QComboBox()
        self._data_path.setEditable(True)
        self._data_path.addItems(["", "Data", "Mods"])
        self._data_path.setCurrentIndex(0)
        form.addRow(tr("plugin_creator.data_path"), self._data_path)

        layout.addWidget(game_group)

        # ── Optionale Felder ─────────────────────────────────────
        opt_group = QGroupBox(tr("plugin_creator.optional"))
        opt_form = QFormLayout(opt_group)

        self._win_documents = QLineEdit()
        self._win_documents.setPlaceholderText(
            "drive_c/users/steamuser/Documents/My Games/..."
        )
        opt_form.addRow(tr("plugin_creator.documents"), self._win_documents)

        self._win_saves = QLineEdit()
        self._win_saves.setPlaceholderText(
            "drive_c/users/steamuser/Documents/My Games/.../Saves"
        )
        opt_form.addRow(tr("plugin_creator.saves"), self._win_saves)

        self._save_ext = QLineEdit()
        self._save_ext.setPlaceholderText("save")
        opt_form.addRow(tr("plugin_creator.save_ext"), self._save_ext)

        self._nexus_id = QLineEdit()
        self._nexus_id.setPlaceholderText("1704")
        opt_form.addRow(tr("plugin_creator.nexus_game_id"), self._nexus_id)

        layout.addWidget(opt_group)

        # ── Frameworks ───────────────────────────────────────────
        fw_group = QGroupBox(tr("plugin_creator.frameworks"))
        fw_layout = QVBoxLayout(fw_group)

        self._fw_table = QTableWidget(0, 4)
        self._fw_table.setHorizontalHeaderLabels([
            tr("plugin_creator.fw_name"),
            tr("plugin_creator.fw_target"),
            tr("plugin_creator.fw_nexus_id"),
            tr("plugin_creator.fw_detect"),
        ])
        header = self._fw_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._fw_table.setMinimumHeight(120)
        fw_layout.addWidget(self._fw_table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton(tr("plugin_creator.fw_add"))
        btn_add.clicked.connect(lambda checked=False: self._add_fw_row())
        btn_row.addWidget(btn_add)

        btn_remove = QPushButton(tr("plugin_creator.fw_remove"))
        btn_remove.clicked.connect(lambda checked=False: self._remove_fw_row())
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()
        fw_layout.addLayout(btn_row)

        layout.addWidget(fw_group)

        # ── Buttons ──────────────────────────────────────────────
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            tr("plugin_creator.create")
        )
        buttons.accepted.connect(self._on_create)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Auto-fill short name when game name changes
        self._game_name.textChanged.connect(self._auto_short_name)

    # ── Framework-Tabelle ────────────────────────────────────────

    def _add_fw_row(self) -> None:
        row = self._fw_table.rowCount()
        self._fw_table.insertRow(row)
        for col in range(4):
            self._fw_table.setItem(row, col, QTableWidgetItem(""))

    def _remove_fw_row(self) -> None:
        row = self._fw_table.currentRow()
        if row >= 0:
            self._fw_table.removeRow(row)

    # ── Auto-Fill ────────────────────────────────────────────────

    def _auto_short_name(self, text: str) -> None:
        if self._game_short.isModified():
            return
        # "Skyrim Special Edition" → "SkyrimSpecialEdition"
        short = re.sub(r"[^a-zA-Z0-9]", "", text)
        self._game_short.setText(short)

    # ── Erstellen ────────────────────────────────────────────────

    def _on_create(self) -> None:
        # Validierung
        game_name = self._game_name.text().strip()
        short_name = self._game_short.text().strip()
        binary = self._game_binary.text().strip()
        steam_id = self._steam_id.text().strip()

        if not game_name or not short_name or not binary or not steam_id:
            QMessageBox.warning(
                self,
                tr("plugin_creator.error_title"),
                tr("plugin_creator.error_required"),
            )
            return

        if not steam_id.isdigit():
            QMessageBox.warning(
                self,
                tr("plugin_creator.error_title"),
                tr("plugin_creator.error_steam_id"),
            )
            return

        # Dateiname
        file_name = f"game_{short_name.lower()}.py"
        file_path = _USER_PLUGINS_DIR / file_name

        if file_path.exists():
            QMessageBox.warning(
                self,
                tr("plugin_creator.error_title"),
                tr("plugin_creator.error_exists", name=file_name),
            )
            return

        # Plugin-Datei generieren
        data_path = self._data_path.currentText().strip()
        win_docs = self._win_documents.text().strip()
        win_saves = self._win_saves.text().strip()
        save_ext = self._save_ext.text().strip() or "save"
        nexus_game_id = self._nexus_id.text().strip()

        code = self._generate_plugin(
            game_name, short_name, binary, steam_id,
            data_path, win_docs, win_saves, save_ext, nexus_game_id,
        )

        # Frameworks als JSON speichern
        frameworks = self._collect_frameworks()

        # Dateien schreiben
        _USER_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        file_path.write_text(code, encoding="utf-8")

        if frameworks:
            json_path = _USER_PLUGINS_DIR / f"game_{short_name.lower()}.json"
            json_path.write_text(
                json.dumps({"frameworks": frameworks}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        QMessageBox.information(
            self,
            tr("plugin_creator.success_title"),
            tr("plugin_creator.success_message", path=str(file_path)),
        )
        self.accept()

    def _generate_plugin(
        self,
        game_name: str,
        short_name: str,
        binary: str,
        steam_id: str,
        data_path: str,
        win_docs: str,
        win_saves: str,
        save_ext: str,
        nexus_game_id: str,
    ) -> str:
        """Generiert den Python-Code fuer das Game-Plugin."""
        class_name = re.sub(r"[^a-zA-Z0-9]", "", game_name) + "Game"

        lines = [
            f'"""Game plugin for {game_name} — auto-generated by Anvil Organizer."""',
            "",
            "from __future__ import annotations",
            "",
            "from anvil.plugins.base_game import BaseGame",
            "",
            "",
            f"class {class_name}(BaseGame):",
            f'    """Support plugin for {game_name}."""',
            "",
            f'    Name = "{game_name} Support Plugin"',
            f'    Author = "Anvil User"',
            f'    Version = "1.0.0"',
            "",
            f'    GameName = "{game_name}"',
            f'    GameShortName = "{short_name}"',
            f'    GameBinary = "{binary}"',
            f'    GameDataPath = "{data_path}"',
            f"    GameSteamId = {steam_id}",
        ]

        if save_ext and save_ext != "save":
            lines.append(f'    GameSaveExtension = "{save_ext}"')

        if nexus_game_id and nexus_game_id.isdigit():
            lines.append(f"    GameNexusId = {nexus_game_id}")

        if win_docs:
            lines.append(f'    _WIN_DOCUMENTS = "{win_docs}"')
        if win_saves:
            lines.append(f'    _WIN_SAVES = "{win_saves}"')

        lines.append("")

        return "\n".join(lines)

    def _collect_frameworks(self) -> list[dict]:
        """Liest die Framework-Eintraege aus der Tabelle."""
        result = []
        for row in range(self._fw_table.rowCount()):
            name = (self._fw_table.item(row, 0) or QTableWidgetItem("")).text().strip()
            target = (self._fw_table.item(row, 1) or QTableWidgetItem("")).text().strip()
            nexus_id = (self._fw_table.item(row, 2) or QTableWidgetItem("")).text().strip()
            detect = (self._fw_table.item(row, 3) or QTableWidgetItem("")).text().strip()

            if not name:
                continue

            entry: dict = {"name": name}
            if target:
                entry["target"] = target
            if nexus_id and nexus_id.isdigit():
                entry["nexus_id"] = int(nexus_id)
            if detect:
                entry["detect_installed"] = [d.strip() for d in detect.split(",")]

            result.append(entry)
        return result
