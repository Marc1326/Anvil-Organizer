"""Dialog for confirming auto-detected framework mods."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QGroupBox,
    QFormLayout,
    QPushButton,
    QListWidget,
)
from PySide6.QtCore import Qt

from anvil.core.translator import tr


class FrameworkDetectDialog(QDialog):
    """Asks the user to confirm a possible framework mod detection."""

    def __init__(
        self,
        parent=None,
        *,
        archive_name: str = "",
        score: int = 0,
        reasons: list[str] | None = None,
        detected_files: list[str] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("fw_detect.title"))
        self.setMinimumWidth(500)

        self._accepted_as_framework = False
        reasons = reasons or []
        detected_files = detected_files or []

        layout = QVBoxLayout(self)

        # Header
        header = QLabel(tr("fw_detect.header", name=archive_name))
        header.setWordWrap(True)
        layout.addWidget(header)

        # Reasons
        reason_texts = {
            "executable_files": tr("fw_detect.reason_executables"),
            "keyword_match": tr("fw_detect.reason_keywords"),
            "config_beside_dll": tr("fw_detect.reason_config"),
            "no_mod_files": tr("fw_detect.reason_no_mod_files"),
            "outside_data_dir": tr("fw_detect.reason_outside_data"),
        }
        if reasons:
            reason_group = QGroupBox(tr("fw_detect.reasons_title"))
            reason_layout = QVBoxLayout(reason_group)
            for r in reasons:
                text = reason_texts.get(r, r)
                reason_layout.addWidget(QLabel(f"  • {text}"))
            layout.addWidget(reason_group)

        # Detected files
        if detected_files:
            files_group = QGroupBox(tr("fw_detect.files_title"))
            files_layout = QVBoxLayout(files_group)
            file_list = QListWidget()
            file_list.setMaximumHeight(120)
            for f in detected_files[:20]:
                file_list.addItem(f)
            files_layout.addWidget(file_list)
            layout.addWidget(files_group)

        # Editable fields
        edit_group = QGroupBox(tr("fw_detect.settings_title"))
        form = QFormLayout(edit_group)

        self._name_edit = QLineEdit()
        self._name_edit.setText(archive_name)
        form.addRow(tr("fw_detect.name"), self._name_edit)

        self._target_edit = QLineEdit()
        self._target_edit.setPlaceholderText(tr("fw_detect.target_hint"))
        form.addRow(tr("fw_detect.target"), self._target_edit)

        self._detect_edit = QLineEdit()
        # Pre-fill with first detected file as detect_installed hint
        if detected_files:
            self._detect_edit.setText(detected_files[0])
        self._detect_edit.setPlaceholderText(tr("fw_detect.detect_hint"))
        form.addRow(tr("fw_detect.detect_path"), self._detect_edit)

        layout.addWidget(edit_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton(tr("fw_detect.btn_cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_accept = QPushButton(tr("fw_detect.btn_install"))
        btn_accept.setDefault(True)
        btn_accept.clicked.connect(self._on_accept)
        btn_layout.addWidget(btn_accept)

        layout.addLayout(btn_layout)

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            return
        self._accepted_as_framework = True
        self.accept()

    def framework_name(self) -> str:
        return self._name_edit.text().strip()

    def framework_target(self) -> str:
        return self._target_edit.text().strip()

    def framework_detect_installed(self) -> list[str]:
        text = self._detect_edit.text().strip()
        if not text:
            return []
        return [d.strip() for d in text.split(",")]
