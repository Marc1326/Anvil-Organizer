"""Schnellinstallation-Dialog mit editierbarer ComboBox."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QCompleter,
)
from PySide6.QtCore import Qt
from pathlib import Path

from anvil.core.translator import tr
from anvil.core.resource_path import get_anvil_base

_ARROW_SVG = str(get_anvil_base() / "resources" / "arrow_down.svg").replace("\\", "/")

_STYLE = f"""
QDialog {{ background: #1C1C1C; color: #D3D3D3; }}
QLabel {{ color: #D3D3D3; }}
QComboBox {{
    background: #242424;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 4px 6px;
    selection-background-color: #006868;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: url({_ARROW_SVG});
    width: 10px;
    height: 6px;
}}
QComboBox QAbstractItemView {{
    background: #242424;
    color: #D3D3D3;
    selection-background-color: #006868;
    border: 1px solid #3D3D3D;
}}
QPushButton {{
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 6px 16px;
    min-width: 70px;
}}
QPushButton:hover {{ background: #3D3D3D; }}
QPushButton:pressed {{ background: #006868; }}
QPushButton:disabled {{ color: #666666; border-color: #2A2A2A; }}
"""


class QuickInstallDialog(QDialog):
    """Quick-Install-Dialog mit editierbarer ComboBox für den Mod-Namen.

    Die ComboBox wird mit Namensvarianten befüllt. Der beste Vorschlag
    ist vorausgewählt.
    """

    def __init__(
        self,
        variants: list[str],
        selected: str | None = None,
        parent=None,
    ):
        """
        Args:
            variants: List of name suggestions for the combo box.
            selected: Which variant to pre-select.  Defaults to first.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.quick_install"))
        self.setMinimumWidth(420)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setStyleSheet(_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Name-Zeile: Label "Name" + editierbare ComboBox
        name_row = QHBoxLayout()
        name_row.setContentsMargins(7, 7, 7, 7)
        name_row.setSpacing(6)
        label = QLabel(tr("label.name"))
        name_row.addWidget(label)

        self._name_combo = QComboBox()
        self._name_combo.setEditable(True)
        self._name_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._name_combo.setMinimumContentsLength(30)

        # Varianten einfügen
        for v in variants:
            self._name_combo.addItem(v)

        # Pre-select the best guess
        if selected:
            idx = self._name_combo.findText(selected)
            if idx >= 0:
                self._name_combo.setCurrentIndex(idx)
            else:
                self._name_combo.setCurrentText(selected)
        elif variants:
            self._name_combo.setCurrentIndex(0)

        # Groß-/Kleinschreibung-sensitiver Completer
        completer = self._name_combo.completer()
        if completer:
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)

        name_row.addWidget(self._name_combo, 1)
        layout.addLayout(name_row)

        # Buttons: Manual | Spacer | OK | Cancel
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(7, 7, 7, 7)
        btn_row.setSpacing(6)

        btn_manual = QPushButton(tr("button.manual"))
        btn_manual.setEnabled(False)
        btn_manual.setToolTip(tr("tooltip.manual_install"))
        btn_row.addWidget(btn_manual)

        btn_row.addStretch()

        btn_ok = QPushButton(tr("button.ok"))
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)

        btn_cancel = QPushButton(tr("button.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        layout.addLayout(btn_row)

    def mod_name(self) -> str:
        """Return the user-entered/selected mod name, stripped."""
        return self._name_combo.currentText().strip()

    def set_name(self, name: str) -> None:
        """Update the combo box text (used when returning from Rename)."""
        self._name_combo.setCurrentText(name)
