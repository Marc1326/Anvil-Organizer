"""Schnellinstallation-Dialog — MO2-Style mit editierbarer ComboBox.

Ported from MO2's ``simpleinstalldialog.cpp/ui`` (installer_quick plugin).
"""

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

_ARROW_SVG = str(Path(__file__).resolve().parent.parent / "resources" / "arrow_down.svg").replace("\\", "/")

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
    """MO2-style Quick Install dialog with editable QComboBox for mod name.

    The combo box is populated with name variants (like MO2's
    ``GuessedValue::variants()``).  The best guess is pre-selected.
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
        self.setWindowTitle("Schnellinstallation")
        self.setMinimumWidth(420)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setStyleSheet(_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Name row (like MO2: Label "Name" + editable ComboBox)
        name_row = QHBoxLayout()
        name_row.setContentsMargins(7, 7, 7, 7)
        name_row.setSpacing(6)
        label = QLabel("Name")
        name_row.addWidget(label)

        self._name_combo = QComboBox()
        self._name_combo.setEditable(True)
        self._name_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._name_combo.setMinimumContentsLength(30)

        # Populate with variants (like MO2 iterating GuessedValue::variants())
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

        # Case-sensitive completer (like MO2)
        completer = self._name_combo.completer()
        if completer:
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)

        name_row.addWidget(self._name_combo, 1)
        layout.addLayout(name_row)

        # Buttons (like MO2: Manual | spacer | OK | Cancel)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(7, 7, 7, 7)
        btn_row.setSpacing(6)

        btn_manual = QPushButton("Manuell")
        btn_manual.setEnabled(False)
        btn_manual.setToolTip(
            "Öffnet einen Dialog für manuelle Anpassungen."
        )
        btn_row.addWidget(btn_manual)

        btn_row.addStretch()

        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)

        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        layout.addLayout(btn_row)

    def mod_name(self) -> str:
        """Return the user-entered/selected mod name, stripped."""
        return self._name_combo.currentText().strip()

    def set_name(self, name: str) -> None:
        """Update the combo box text (used when returning from Rename)."""
        self._name_combo.setCurrentText(name)
