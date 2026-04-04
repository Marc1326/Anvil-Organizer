"""Overwrite-Dialog — Zusammenführen / Ersetzen / Umbenennen / Abbrechen."""

from enum import Enum

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt

from anvil.core.translator import tr

_STYLE = """
QDialog { background: #1C1C1C; color: #D3D3D3; }
QLabel { color: #D3D3D3; }
QFrame#contentFrame {
    background: #242424;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
}
QPushButton {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 6px 16px;
    min-width: 90px;
}
QPushButton:hover { background: #3D3D3D; }
QPushButton:pressed { background: #006868; }
QPushButton#renameBtn { border-color: #006868; }
"""


class OverwriteAction(Enum):
    NONE = 0
    MERGE = 1
    REPLACE = 2
    RENAME = 3


class QueryOverwriteDialog(QDialog):
    """Dialog wenn ein Mod mit gleichem Namen bereits existiert."""

    def __init__(self, mod_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.mod_exists"))
        self.setMinimumWidth(460)
        self.setStyleSheet(_STYLE)
        self._action = OverwriteAction.NONE

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Content frame
        frame = QFrame()
        frame.setObjectName("contentFrame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(16, 14, 16, 14)
        frame_layout.setSpacing(10)

        msg = QLabel(tr("dialog.mod_exists_message", name=mod_name))
        msg.setWordWrap(True)
        frame_layout.addWidget(msg)

        desc = QLabel(tr("dialog.mod_exists_description"))
        desc.setWordWrap(True)
        frame_layout.addWidget(desc)

        layout.addWidget(frame)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(8, 8, 8, 8)
        btn_row.setSpacing(6)

        btn_row.addStretch()

        btn_merge = QPushButton(tr("button.merge"))
        btn_merge.clicked.connect(self._on_merge)
        btn_row.addWidget(btn_merge)

        btn_replace = QPushButton(tr("button.replace"))
        btn_replace.clicked.connect(self._on_replace)
        btn_row.addWidget(btn_replace)

        btn_rename = QPushButton(tr("button.rename"))
        btn_rename.setObjectName("renameBtn")
        btn_rename.setDefault(True)
        btn_rename.clicked.connect(self._on_rename)
        btn_row.addWidget(btn_rename)

        btn_cancel = QPushButton(tr("button.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        layout.addLayout(btn_row)

    def action(self) -> OverwriteAction:
        return self._action

    def _on_merge(self) -> None:
        self._action = OverwriteAction.MERGE
        self.accept()

    def _on_replace(self) -> None:
        self._action = OverwriteAction.REPLACE
        self.accept()

    def _on_rename(self) -> None:
        self._action = OverwriteAction.RENAME
        self.accept()
