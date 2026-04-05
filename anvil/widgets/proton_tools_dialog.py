"""Proton Tools — Externe Windows-Tools im Proton-Prefix starten."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QPushButton,
    QLabel,
    QFileDialog,
    QWidget,
    QFormLayout,
)
from PySide6.QtCore import Qt

from anvil.core.translator import tr

TOOLS_FILE = "proton_tools.json"


def load_proton_tools(instance_path: Path) -> list[dict]:
    fp = instance_path / TOOLS_FILE
    if not fp.is_file():
        return []
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_proton_tools(instance_path: Path, tools: list[dict]) -> None:
    fp = instance_path / TOOLS_FILE
    fp.write_text(json.dumps(tools, indent=2, ensure_ascii=False), encoding="utf-8")


class ProtonToolsDialog(QDialog):
    def __init__(self, parent=None, instance_path: Path | None = None):
        super().__init__(parent)
        self._parent_win = parent
        self.setWindowTitle(tr("proton_tools.manage_title"))
        self.setMinimumSize(780, 520)
        self.resize(780, 520)
        self._instance_path = instance_path
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
        top_row.addWidget(self._add_btn)
        top_row.addWidget(self._remove_btn)
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

    def _on_selection_changed(self, row: int) -> None:
        self._update_form_enabled()
        if row < 0 or row >= len(self._tools):
            self._updating = True
            self._name_edit.clear()
            self._exe_edit.clear()
            self._args_edit.clear()
            self._dir_edit.clear()
            self._updating = False
            return
        self._updating = True
        tool = self._tools[row]
        self._name_edit.setText(tool.get("name", ""))
        self._exe_edit.setText(tool.get("exe_path", ""))
        self._args_edit.setText(" ".join(tool.get("args", [])))
        self._dir_edit.setText(tool.get("working_dir", ""))
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
        tool["args"] = args_text.split() if args_text else []
        tool["working_dir"] = self._dir_edit.text().strip()
        item = self._list.item(row)
        if item:
            item.setText(tool["name"] or "?")

    def _on_add(self, checked=False) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("proton_tools.select_exe"), "",
            "Alle Dateien (*)",
        )
        if not path:
            return
        exe = Path(path)
        new_tool = {
            "name": exe.stem,
            "exe_path": str(exe),
            "args": [],
            "working_dir": str(exe.parent),
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

    def _on_browse_exe(self) -> None:
        start_dir = ""
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
            self._exe_edit.setText(path)
            if not self._name_edit.text().strip():
                self._name_edit.setText(Path(path).stem)

    def _on_browse_dir(self) -> None:
        start_dir = self._dir_edit.text().strip() or ""
        path = QFileDialog.getExistingDirectory(
            self, tr("proton_tools.select_dir"), start_dir,
        )
        if path:
            self._dir_edit.setText(path)

    def _on_ok(self) -> None:
        if self._instance_path:
            save_proton_tools(self._instance_path, self._tools)
        self.accept()
