"""Profil-Dialoge — „Neues Profil" nach Vorlage."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QCheckBox,
    QInputDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from anvil.core.translator import tr
from anvil.widgets.modal_shell import (
    is_modern_theme_active, wrap_modal, exec_with_backdrop,
)


class ProfileNameDialog(QDialog):
    """Vorlage „Neues Profil": Namensfeld + Hinweis, Modal-Hülle."""

    def __init__(self, parent=None, *, title: str = "",
                 initial: str = "", hint: str = ""):
        super().__init__(parent)
        self._modern = is_modern_theme_active()
        self.setWindowTitle(title)

        ok_btn = QPushButton(tr("button.ok"))
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(tr("button.cancel"))
        cancel_btn.clicked.connect(self.reject)

        if self._modern:
            self.setFixedWidth(525)
            ok_btn.setObjectName("setOkBtn")
            cancel_btn.setObjectName("setCancelBtn")
            layout = wrap_modal(self, title, [cancel_btn, ok_btn])
        else:
            layout = QVBoxLayout(self)

        lbl = QLabel(tr("profile.name_label"))
        layout.addWidget(lbl)
        self._name_edit = QLineEdit(initial)
        self._name_edit.setPlaceholderText(tr("placeholder.profile_name"))
        self._name_edit.returnPressed.connect(self.accept)
        layout.addWidget(self._name_edit)
        if hint:
            hint_lbl = QLabel(hint)
            hint_lbl.setObjectName("installHint")
            hint_lbl.setWordWrap(True)
            layout.addWidget(hint_lbl)
        if not self._modern:
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(ok_btn)
            row.addWidget(cancel_btn)
            layout.addLayout(row)

    def exec(self):  # noqa: A003
        return exec_with_backdrop(self, self._modern)

    def name(self) -> str:
        return self._name_edit.text().strip()
