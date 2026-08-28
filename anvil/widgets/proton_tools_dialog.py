"""Proton Tools — Externe Windows-Tools im Proton-Prefix starten."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QLabel,
    QFileDialog,
    QWidget,
    QFormLayout,
)
from PySide6.QtCore import Qt

from anvil.core.translator import tr
from anvil.core.tool_paths import deployed_tool_path

TOOLS_FILE = "proton_tools.json"


def load_proton_tools(instance_path: Path) -> list[dict]:
    fp = instance_path / TOOLS_FILE
    if not fp.is_file():
        return []
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    # Gegen extern verfälschte JSON absichern: nur Dict-Einträge, args als String-Liste.
    if not isinstance(data, list):
        return []
    tools = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        for key in ("name", "exe_path", "working_dir"):
            if key in entry:
                entry[key] = str(entry[key])
        raw_args = entry.get("args", [])
        entry["args"] = [str(a) for a in raw_args] if isinstance(raw_args, list) else []
        tools.append(entry)
    return tools


def save_proton_tools(instance_path: Path, tools: list[dict]) -> None:
    fp = instance_path / TOOLS_FILE
    fp.write_text(json.dumps(tools, indent=2, ensure_ascii=False), encoding="utf-8")


class ProtonToolsDialog(QDialog):
    def __init__(
        self,
        parent=None,
        instance_path: Path | None = None,
        *,
        mods_path: Path | None = None,
        game_path: Path | None = None,
        data_path: str = "",
        nest_under_mod_name: bool = False,
        multi_folder_routes: dict[str, str] | None = None,
    ):
        super().__init__(parent)
        self._parent_win = parent
        self.setWindowTitle(tr("proton_tools.manage_title"))
        self.setMinimumSize(780, 520)
        self.resize(780, 520)
        self._instance_path = instance_path
        self._mods_path = mods_path
        self._game_path = game_path
        self._data_path = data_path
        self._nest_under_mod_name = nest_under_mod_name
        self._multi_folder_routes = multi_folder_routes
        self._tools: list[dict] = []
        if instance_path:
            self._tools = load_proton_tools(instance_path)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        content = QHBoxLayout()
        content.setSpacing(12)

        # Links: Liste + Buttons
        left = QVBoxLayout()
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self._add_btn = QPushButton("+")
        self._add_btn.setFixedSize(36, 36)
        self._add_btn.setToolTip(tr("proton_tools.add_tooltip"))
        self._add_btn.clicked.connect(self._on_add)
        self._remove_btn = QPushButton("−")
        self._remove_btn.setFixedSize(36, 36)
        self._remove_btn.setObjectName("protonRemoveBtn")
        self._remove_btn.setToolTip(tr("proton_tools.remove_tooltip"))
        self._remove_btn.clicked.connect(self._on_remove)
        self._up_btn = QPushButton("▲")
        self._up_btn.setFixedSize(36, 36)
        self._up_btn.setToolTip(tr("proton_tools.move_up_tooltip"))
        self._up_btn.clicked.connect(self._on_move_up)
        self._down_btn = QPushButton("▼")
        self._down_btn.setFixedSize(36, 36)
        self._down_btn.setToolTip(tr("proton_tools.move_down_tooltip"))
        self._down_btn.clicked.connect(self._on_move_down)
        top_row.addWidget(self._add_btn)
        top_row.addWidget(self._remove_btn)
        top_row.addWidget(self._up_btn)
        top_row.addWidget(self._down_btn)
        top_row.addStretch()
        left.addLayout(top_row)

        self._list = QListWidget()
        self._list.setMinimumWidth(200)
        self._list.currentRowChanged.connect(self._on_selection_changed)
        left.addWidget(self._list)
        content.addLayout(left)

        # Rechts: Formular
        form_widget = QWidget()
        form_widget.setMinimumWidth(320)
        fl = QFormLayout(form_widget)
        fl.setSpacing(8)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(tr("proton_tools.name_placeholder"))
        self._name_edit.textChanged.connect(self._on_field_changed)
        fl.addRow(tr("proton_tools.name_label") + ":", self._name_edit)

        exe_row = QHBoxLayout()
        self._exe_edit = QLineEdit()
        self._exe_edit.setPlaceholderText(tr("proton_tools.exe_placeholder"))
        self._exe_edit.textChanged.connect(self._on_field_changed)
        exe_row.addWidget(self._exe_edit)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._on_browse_exe)
        exe_row.addWidget(browse_btn)
        fl.addRow(tr("proton_tools.exe_label") + ":", exe_row)

        self._args_edit = QLineEdit()
        self._args_edit.setPlaceholderText(tr("proton_tools.args_placeholder"))
        self._args_edit.textChanged.connect(self._on_field_changed)
        fl.addRow(tr("proton_tools.args_label") + ":", self._args_edit)

        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText(tr("proton_tools.dir_placeholder"))
        self._dir_edit.textChanged.connect(self._on_field_changed)
        dir_row.addWidget(self._dir_edit)
        dir_browse = QPushButton("...")
        dir_browse.setFixedWidth(32)
        dir_browse.clicked.connect(self._on_browse_dir)
        dir_row.addWidget(dir_browse)
        fl.addRow(tr("proton_tools.dir_label") + ":", dir_row)

        self._proton_check = QCheckBox(tr("proton_tools.run_via_proton"))
        self._proton_check.toggled.connect(self._on_field_changed)
        fl.addRow("", self._proton_check)

        content.addWidget(form_widget)
        layout.addLayout(content)

        # Unten: Buttons
        bottom = QHBoxLayout()
        bottom.addStretch()
        ok_btn = QPushButton(tr("button.ok"))
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton(tr("button.cancel"))
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(ok_btn)
        bottom.addWidget(cancel_btn)
        layout.addLayout(bottom)

        self._updating = False
        self._rebuild_list()
        self._update_form_enabled()

    def _rebuild_list(self) -> None:
        self._list.clear()
        for tool in self._tools:
            self._list.addItem(QListWidgetItem(tool.get("name", "?")))
        if self._tools:
            self._list.setCurrentRow(0)

    def _update_form_enabled(self) -> None:
        has_selection = self._list.currentRow() >= 0
        self._name_edit.setEnabled(has_selection)
        self._exe_edit.setEnabled(has_selection)
        self._args_edit.setEnabled(has_selection)
        self._dir_edit.setEnabled(has_selection)
        self._proton_check.setEnabled(has_selection)

    def _on_selection_changed(self, row: int) -> None:
        self._update_form_enabled()
        if row < 0 or row >= len(self._tools):
            self._updating = True
            self._name_edit.clear()
            self._exe_edit.clear()
            self._args_edit.clear()
            self._dir_edit.clear()
            self._proton_check.setChecked(True)
            self._updating = False
            return
        self._updating = True
        tool = self._tools[row]
        self._name_edit.setText(tool.get("name", ""))
        self._exe_edit.setText(tool.get("exe_path", ""))
        self._args_edit.setText(shlex.join(tool.get("args", [])))
        self._dir_edit.setText(tool.get("working_dir", ""))
        self._proton_check.setChecked(tool.get("proton", True))
        self._updating = False

    def _on_field_changed(self) -> None:
        if self._updating:
            return
        row = self._list.currentRow()
        if row < 0 or row >= len(self._tools):
            return
        tool = self._tools[row]
        tool["name"] = self._name_edit.text().strip()
        tool["exe_path"] = self._exe_edit.text().strip()
        args_text = self._args_edit.text().strip()
        if args_text:
            try:
                tool["args"] = shlex.split(args_text)
            except ValueError:
                # Unbalancierte Anführungszeichen während des Tippens — simpel trennen
                tool["args"] = args_text.split()
        else:
            tool["args"] = []
        tool["working_dir"] = self._dir_edit.text().strip()
        tool["proton"] = self._proton_check.isChecked()
        item = self._list.item(row)
        if item:
            item.setText(tool["name"] or "?")

    def _im_spiel(self, exe: Path) -> Path:
        """Aus ``.mods/`` auf den ausgerollten Ort umbiegen.

        Ein Werkzeug im Mod-Ordner sieht nur seine eigene Mod. Gemeint ist
        immer die Stelle im Spielverzeichnis, wo alle Mods zusammenlaufen.
        """
        return deployed_tool_path(
            exe,
            instance_path=self._instance_path,
            mods_path=self._mods_path,
            game_path=self._game_path,
            data_path=self._data_path,
            nest_under_mod_name=self._nest_under_mod_name,
            multi_folder_routes=self._multi_folder_routes,
        ) or exe

    def _start_dir(self) -> str:
        """Startordner der Dateiauswahl -- dort liegen die Mods."""
        if self._mods_path is not None and self._mods_path.is_dir():
            return str(self._mods_path)
        return ""

    def _on_add(self, checked=False) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("proton_tools.select_exe"), self._start_dir(),
            tr("proton_tools.all_files"),
        )
        if not path:
            return
        exe = self._im_spiel(Path(path))
        new_tool = {
            "name": exe.stem,
            "exe_path": str(exe),
            "args": [],
            "working_dir": str(exe.parent),
            "proton": True,
        }
        self._tools.append(new_tool)
        self._list.addItem(QListWidgetItem(new_tool["name"]))
        self._list.setCurrentRow(len(self._tools) - 1)

    def _on_remove(self, checked=False) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._tools):
            return
        self._tools.pop(row)
        self._list.takeItem(row)
        self._update_form_enabled()

    def _on_move_up(self, checked=False) -> None:
        row = self._list.currentRow()
        if row <= 0 or row >= len(self._tools):
            return
        self._tools.insert(row - 1, self._tools.pop(row))
        self._refill_list(row - 1)

    def _on_move_down(self, checked=False) -> None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._tools) - 1:
            return
        self._tools.insert(row + 1, self._tools.pop(row))
        self._refill_list(row + 1)

    def _refill_list(self, select_row: int) -> None:
        self._list.clear()
        for tool in self._tools:
            self._list.addItem(QListWidgetItem(tool.get("name", "?")))
        self._list.setCurrentRow(select_row)

    def _on_browse_exe(self) -> None:
        start_dir = self._start_dir()
        current_exe = self._exe_edit.text().strip()
        if current_exe:
            p = Path(current_exe)
            if p.parent.is_dir():
                start_dir = str(p.parent)
        path, _ = QFileDialog.getOpenFileName(
            self, tr("proton_tools.select_exe"), start_dir,
            tr("proton_tools.exe_filter"),
        )
        if path:
            exe = self._im_spiel(Path(path))
            self._exe_edit.setText(str(exe))
            if not self._dir_edit.text().strip():
                self._dir_edit.setText(str(exe.parent))
            if not self._name_edit.text().strip():
                self._name_edit.setText(exe.stem)

    def _on_browse_dir(self) -> None:
        start_dir = self._dir_edit.text().strip() or self._start_dir()
        path = QFileDialog.getExistingDirectory(
            self, tr("proton_tools.select_dir"), start_dir,
        )
        if path:
            self._dir_edit.setText(path)

    def _on_ok(self) -> None:
        if self._instance_path:
            save_proton_tools(self._instance_path, self._tools)
        self.accept()
