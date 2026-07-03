"""Dialog für Kategorie-Namen (Neu / Umbenennen im FilterPanel)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
)

from anvil.core.translator import tr
from anvil.widgets.modal_shell import is_modern_theme_active, wrap_modal


class CategoryNameDialog(QDialog):
    """Einfacher Dialog für Kategorie-Name Eingabe (Add/Rename im FilterPanel)."""

    def __init__(
        self,
        parent=None,
        title: str = "",
        label_text: str = "",
        existing_names: set[str] | None = None,
        initial_text: str = "",
    ):
        super().__init__(parent)
        self._modern = is_modern_theme_active()
        self.setWindowTitle(title)
        self.setModal(True)

        self._existing_names = existing_names or set()
        self._initial_text = initial_text.lower()

        from PySide6.QtWidgets import QLabel, QLineEdit

        self._cancel_btn = QPushButton(tr("button.cancel"))
        self._cancel_btn.clicked.connect(self.reject)
        self._ok_btn = QPushButton(tr("button.ok"))
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self.accept)

        if self._modern:
            self.setFixedWidth(525)
            self._ok_btn.setObjectName("setOkBtn")
            self._cancel_btn.setObjectName("setCancelBtn")
            layout = wrap_modal(self, title, [self._cancel_btn, self._ok_btn])
        else:
            self.setMinimumWidth(300)
            layout = QVBoxLayout(self)

        # Label
        lbl = QLabel(label_text)
        layout.addWidget(lbl)

        # Name-Eingabe
        self._name_edit = QLineEdit()
        self._name_edit.setText(initial_text)
        self._name_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._name_edit)

        # Hinweistext für Duplikate
        self._hint_label = QLabel()
        self._hint_label.setObjectName("dialogHintLabel")
        self._hint_label.setVisible(False)
        layout.addWidget(self._hint_label)

        # Buttons (klassisch unten; modern in der Fußleiste)
        btn_layout = QHBoxLayout()
        if not self._modern:
            self._ok_btn.setObjectName("createBtn")  # Teal-Farbe aus QSS
            btn_layout.addStretch(1)
            btn_layout.addWidget(self._cancel_btn)
            btn_layout.addWidget(self._ok_btn)

        layout.addLayout(btn_layout)

        # Initial validation
        self._on_text_changed(initial_text)

    def _on_text_changed(self, text: str) -> None:
        """Validate input and enable/disable OK button."""
        name = text.strip().lower()

        # Leer?
        if not name:
            self._ok_btn.setEnabled(False)
            self._hint_label.setVisible(False)
            return

        # Duplikat? (aber nicht der eigene Name beim Rename)
        if name in self._existing_names and name != self._initial_text:
            self._ok_btn.setEnabled(False)
            self._hint_label.setText(tr("dialog.category_exists"))
            self._hint_label.setVisible(True)
            return

        self._ok_btn.setEnabled(True)
        self._hint_label.setVisible(False)

    def get_name(self) -> str:
        """Return the entered name (stripped)."""
        return self._name_edit.text().strip()
