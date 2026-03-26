"""Dialog zum Erstellen und Bearbeiten von Game-Plugins.

Bietet ein Formular in dem der User alle Daten eines Game-Plugins
sehen, bearbeiten und neue Plugins erstellen kann — ohne Python-Code
schreiben zu muessen.

Im Edit-Modus (bestehendes Plugin) werden Frameworks in JSON gespeichert
und das Bild kann geaendert werden.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
    """Dialog zum Erstellen und Bearbeiten von Game-Plugins."""

    def __init__(self, parent=None, plugin=None, icon_manager=None):
        super().__init__(parent)
        self._plugin = plugin  # None = Erstellen, gesetzt = Bearbeiten
        self._icon_manager = icon_manager
        self._new_icon_path: Path | None = None  # User hat neues Bild gewaehlt

        if plugin:
            self.setWindowTitle(
                tr("plugin_creator.title_edit", name=plugin.GameName)
            )
        else:
            self.setWindowTitle(tr("plugin_creator.title"))

        self.setMinimumWidth(640)
        self.setMinimumHeight(580)
        self._build_ui()

        if plugin:
            self._fill_from_plugin(plugin)

    # ── UI aufbauen ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ── Obere Zeile: Bild + Pflichtfelder ────────────────────
        top_row = QHBoxLayout()

        # Bild-Vorschau
        img_group = QVBoxLayout()
        self._img_label = QLabel()
        self._img_label.setFixedSize(140, 140)
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setStyleSheet(
            "background: #242424; border: 1px solid #444; border-radius: 4px;"
        )
        self._img_label.setText("Kein Bild")
        img_group.addWidget(self._img_label)

        btn_img = QPushButton(tr("plugin_creator.select_image"))
        btn_img.clicked.connect(lambda checked=False: self._on_select_image())
        img_group.addWidget(btn_img)
        img_group.addStretch()

        top_row.addLayout(img_group)

        # Pflichtfelder
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

        top_row.addWidget(game_group, 1)
        layout.addLayout(top_row)

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

        self._fw_table = QTableWidget(0, 5)
        self._fw_table.setHorizontalHeaderLabels([
            tr("plugin_creator.fw_name"),
            tr("plugin_creator.fw_target"),
            tr("plugin_creator.fw_nexus_id"),
            tr("plugin_creator.fw_detect"),
            tr("plugin_creator.fw_source"),
        ])
        header = self._fw_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._fw_table.setMinimumHeight(140)
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
        if self._plugin:
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
                tr("plugin_creator.save")
            )
        else:
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
                tr("plugin_creator.create")
            )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Auto-fill short name when game name changes (nur im Erstellen-Modus)
        if not self._plugin:
            self._game_name.textChanged.connect(self._auto_short_name)

    # ── Plugin-Daten laden ───────────────────────────────────────

    def _fill_from_plugin(self, plugin) -> None:
        """Felder mit Daten des aktuellen Plugins fuellen."""
        self._game_name.setText(getattr(plugin, "GameName", ""))
        self._game_short.setText(getattr(plugin, "GameShortName", ""))
        self._game_binary.setText(getattr(plugin, "GameBinary", ""))

        steam_id = getattr(plugin, "GameSteamId", "")
        if isinstance(steam_id, (list, tuple)):
            steam_id = steam_id[0] if steam_id else ""
        self._steam_id.setText(str(steam_id) if steam_id else "")

        data_path = getattr(plugin, "GameDataPath", "")
        idx = self._data_path.findText(data_path)
        if idx >= 0:
            self._data_path.setCurrentIndex(idx)
        else:
            self._data_path.setCurrentText(data_path)

        self._win_documents.setText(getattr(plugin, "_WIN_DOCUMENTS", ""))
        self._win_saves.setText(getattr(plugin, "_WIN_SAVES", ""))
        self._save_ext.setText(getattr(plugin, "GameSaveExtension", ""))
        self._nexus_id.setText(
            str(getattr(plugin, "GameNexusId", "")) if getattr(plugin, "GameNexusId", 0) else ""
        )

        # Im Edit-Modus: Felder die im Code stehen read-only machen
        self._game_name.setReadOnly(True)
        self._game_short.setReadOnly(True)
        self._game_binary.setReadOnly(True)
        self._steam_id.setReadOnly(True)

        # Bild laden
        short = plugin.GameShortName
        if self._icon_manager:
            pix = self._icon_manager.get_game_banner(short)
            if pix is None:
                pix = self._icon_manager.get_game_icon(short)
            if pix is not None:
                self._set_preview(pix)

        # Frameworks laden
        self._load_frameworks(plugin)

    def _load_frameworks(self, plugin) -> None:
        """Alle Frameworks (Python + JSON) in die Tabelle laden."""
        # Python-Frameworks
        python_fws = plugin.get_framework_mods()
        python_names = {fw.name.lower() for fw in python_fws}

        for fw in python_fws:
            self._add_fw_to_table(
                fw.name,
                fw.target,
                "",
                ", ".join(fw.detect_installed),
                "Built-in",
            )

        # JSON-Frameworks (nur die die nicht schon in Python sind)
        json_fws = plugin._load_json_frameworks()
        for fw in json_fws:
            if fw.name.lower() not in python_names:
                self._add_fw_to_table(
                    fw.name,
                    fw.target,
                    "",
                    ", ".join(fw.detect_installed),
                    "JSON",
                )

    def _add_fw_to_table(
        self, name: str, target: str, nexus_id: str, detect: str, source: str,
    ) -> None:
        """Eine Framework-Zeile zur Tabelle hinzufuegen."""
        row = self._fw_table.rowCount()
        self._fw_table.insertRow(row)
        self._fw_table.setItem(row, 0, QTableWidgetItem(name))
        self._fw_table.setItem(row, 1, QTableWidgetItem(target))
        self._fw_table.setItem(row, 2, QTableWidgetItem(nexus_id))
        self._fw_table.setItem(row, 3, QTableWidgetItem(detect))

        source_item = QTableWidgetItem(source)
        source_item.setFlags(source_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._fw_table.setItem(row, 4, source_item)

        # Built-in Zeilen: Name nicht editierbar
        if source == "Built-in":
            name_item = self._fw_table.item(row, 0)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    # ── Bild-Auswahl ─────────────────────────────────────────────

    def _on_select_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("plugin_creator.select_image"),
            "",
            "Bilder (*.png *.jpg *.jpeg *.webp);;Alle Dateien (*)",
        )
        if not path:
            return
        pix = QPixmap(path)
        if pix.isNull():
            return
        self._new_icon_path = Path(path)
        self._set_preview(pix)

    def _set_preview(self, pix: QPixmap) -> None:
        """Bild-Vorschau setzen."""
        scaled = pix.scaled(
            QSize(140, 140),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._img_label.setPixmap(scaled)
        self._img_label.setText("")

    # ── Framework-Tabelle ────────────────────────────────────────

    def _add_fw_row(self) -> None:
        self._add_fw_to_table("", "", "", "", "JSON")

    def _remove_fw_row(self) -> None:
        row = self._fw_table.currentRow()
        if row < 0:
            return
        source = (self._fw_table.item(row, 4) or QTableWidgetItem("")).text()
        if source == "Built-in":
            QMessageBox.information(
                self,
                tr("plugin_creator.error_title"),
                tr("plugin_creator.cannot_delete_builtin"),
            )
            return
        self._fw_table.removeRow(row)

    # ── Auto-Fill ────────────────────────────────────────────────

    def _auto_short_name(self, text: str) -> None:
        if self._game_short.isModified():
            return
        short = re.sub(r"[^a-zA-Z0-9]", "", text)
        self._game_short.setText(short)

    # ── Speichern / Erstellen ────────────────────────────────────

    def _on_accept(self) -> None:
        if self._plugin:
            self._on_save()
        else:
            self._on_create()

    def _on_save(self) -> None:
        """Edit-Modus: JSON-Frameworks und Bild speichern."""
        short = self._plugin.GameShortName

        # JSON-Frameworks sammeln (nur nicht-Built-in)
        frameworks = self._collect_frameworks()
        json_path = _USER_PLUGINS_DIR / f"game_{short.lower()}.json"
        _USER_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

        if frameworks:
            json_path.write_text(
                json.dumps({"frameworks": frameworks}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        elif json_path.exists():
            # Keine JSON-Frameworks mehr → Datei loeschen
            json_path.unlink()

        # Bild speichern
        if self._new_icon_path:
            self._save_icon(short, self._new_icon_path)

        QMessageBox.information(
            self,
            tr("plugin_creator.success_title"),
            tr("plugin_creator.saved_message"),
        )
        self.accept()

    def _on_create(self) -> None:
        """Erstellen-Modus: Plugin-Datei + JSON + Bild generieren."""
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

        file_name = f"game_{short_name.lower()}.py"
        file_path = _USER_PLUGINS_DIR / file_name

        if file_path.exists():
            QMessageBox.warning(
                self,
                tr("plugin_creator.error_title"),
                tr("plugin_creator.error_exists", name=file_name),
            )
            return

        data_path = self._data_path.currentText().strip()
        win_docs = self._win_documents.text().strip()
        win_saves = self._win_saves.text().strip()
        save_ext = self._save_ext.text().strip() or "save"
        nexus_game_id = self._nexus_id.text().strip()

        code = self._generate_plugin(
            game_name, short_name, binary, steam_id,
            data_path, win_docs, win_saves, save_ext, nexus_game_id,
        )

        frameworks = self._collect_frameworks()

        _USER_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        file_path.write_text(code, encoding="utf-8")

        if frameworks:
            json_path = _USER_PLUGINS_DIR / f"game_{short_name.lower()}.json"
            json_path.write_text(
                json.dumps({"frameworks": frameworks}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        if self._new_icon_path:
            self._save_icon(short_name, self._new_icon_path)

        QMessageBox.information(
            self,
            tr("plugin_creator.success_title"),
            tr("plugin_creator.success_message", path=str(file_path)),
        )
        self.accept()

    # ── Hilfsfunktionen ──────────────────────────────────────────

    def _save_icon(self, short_name: str, source: Path) -> None:
        """Bild nach anvil/assets/icons/{short_name}/game.png kopieren."""
        from anvil.core.resource_path import get_anvil_base
        icon_dir = get_anvil_base() / "assets" / "icons" / short_name
        icon_dir.mkdir(parents=True, exist_ok=True)
        dest = icon_dir / "game.png"
        shutil.copy2(str(source), str(dest))

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
        """Liest nur JSON-Framework-Eintraege aus der Tabelle."""
        result = []
        for row in range(self._fw_table.rowCount()):
            source = (self._fw_table.item(row, 4) or QTableWidgetItem("")).text()
            if source == "Built-in":
                continue  # Python-Frameworks nicht in JSON speichern

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
