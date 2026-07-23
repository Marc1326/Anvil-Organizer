from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from anvil.core.base_dir import configure_base_dir, legacy_base_dir
from anvil.core.translator import tr


class BaseDirSetupDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        settings: QSettings | None = None,
        recovery: bool = False,
        missing_path: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._recovery = recovery
        self._selected_path: Path | None = None
        self.setWindowTitle(
            tr("base_dir.recovery_title") if recovery else tr("base_dir.setup_title")
        )
        self.setModal(True)
        self.resize(620, 330)

        layout = QVBoxLayout(self)
        title = QLabel(
            tr("base_dir.recovery_title") if recovery else tr("base_dir.setup_title")
        )
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        description = QLabel(
            tr("base_dir.recovery_text", path=str(missing_path or ""))
            if recovery
            else tr("base_dir.setup_text")
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self._default_radio = QRadioButton(
            tr("base_dir.default_option", path=str(legacy_base_dir()))
        )
        self._custom_radio = QRadioButton(tr("base_dir.custom_option"))
        if recovery:
            self._default_radio.hide()
            self._custom_radio.setChecked(True)
        else:
            self._default_radio.setChecked(True)
        layout.addWidget(self._default_radio)
        layout.addWidget(self._custom_radio)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        self._path_edit.setPlaceholderText(tr("base_dir.path_placeholder"))
        browse = QPushButton(tr("button.browse"))
        browse.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(browse)
        layout.addLayout(path_row)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton(tr("button.cancel"))
        cancel.setObjectName("setCancelBtn")
        cancel.clicked.connect(self.reject)
        confirm = QPushButton(tr("button.continue"))
        confirm.setObjectName("setOkBtn")
        confirm.clicked.connect(self._accept_selection)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)

    @property
    def selected_path(self) -> Path | None:
        return self._selected_path

    def _browse(self, checked: bool = False) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            tr("base_dir.choose_folder"),
            str(self._selected_path or Path.home()),
        )
        if selected:
            self._selected_path = Path(selected)
            self._path_edit.setText(selected)
            self._custom_radio.setChecked(True)

    def _accept_selection(self, checked: bool = False) -> None:
        if self._recovery or self._custom_radio.isChecked():
            target = self._selected_path
            if target is None:
                QMessageBox.warning(
                    self,
                    tr("dialog.warning"),
                    tr("base_dir.error_no_path"),
                )
                return
        else:
            target = legacy_base_dir()
        try:
            self._selected_path = configure_base_dir(
                target,
                settings=self._settings,
                create=not self._recovery,
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr("dialog.warning"), str(exc))
            return
        self.accept()
