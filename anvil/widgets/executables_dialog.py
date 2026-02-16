"""Ausführbare Programme ändern — QDialog (Platzhalter)."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QPushButton,
    QLabel,
    QCheckBox,
    QComboBox,
    QWidget,
)
from PySide6.QtCore import Qt

from anvil.core.translator import tr

_EXEC_DIALOG_STYLE = """
QDialog, QWidget { background: #1C1C1C; color: #D3D3D3; border: none; }
QLineEdit, QListWidget, QPushButton, QComboBox {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 4px;
}
QListWidget::item:selected { background: #3D3D3D; color: #D3D3D3; }
QPushButton:disabled { color: #808080; }
"""


class ExecutablesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dialog.executables_title"))
        self.setMinimumSize(680, 520)
        self.setStyleSheet(_EXEC_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        content = QHBoxLayout()
        content.setSpacing(12)

        # Links: "Programme" + 4 kleine Buttons, darunter Liste
        left = QVBoxLayout()
        prog_row = QHBoxLayout()
        prog_row.addWidget(QLabel(tr("label.programs")))
        for _ in ("+", "-", "Stern", "Pfeil"):
            b = QPushButton(_)
            b.setFixedSize(28, 28)
            prog_row.addWidget(b)
        prog_row.addStretch()
        left.addLayout(prog_row)
        prog_list = QListWidget()
        prog_list.setMinimumWidth(220)
        for name in (
            "Cyberpunk 2077",
            "Cyberpunk 2077 - skip REDmod deploy",
            "Manually deploy REDmod",
            "REDprelauncher",
            "Explore Virtual Folder",
        ):
            prog_list.addItem(QListWidgetItem(name))
        left.addWidget(prog_list)
        content.addLayout(left)

        # Rechts: Formular
        form = QWidget()
        form.setMinimumWidth(360)
        fl = QFormLayout(form)
        fl.setSpacing(8)

        fl.addRow(tr("label.name") + ":", QLineEdit())

        exe_row = QHBoxLayout()
        exe_edit = QLineEdit()
        exe_edit.setPlaceholderText(tr("label.executable_file"))
        exe_row.addWidget(exe_edit)
        exe_row.addWidget(QPushButton("..."))
        fl.addRow(tr("label.executable_file") + ":", exe_row)

        work_row = QHBoxLayout()
        work_edit = QLineEdit()
        work_edit.setPlaceholderText(tr("label.working_dir"))
        work_row.addWidget(work_edit)
        work_row.addWidget(QPushButton("..."))
        fl.addRow(tr("label.working_dir") + ":", work_row)

        fl.addRow(tr("label.start_params") + ":", QLineEdit())

        cb_steam = QCheckBox(tr("label.overrides_steam_appid"))
        cb_steam.setChecked(False)
        steam_row = QHBoxLayout()
        steam_row.addWidget(cb_steam)
        steam_row.addWidget(QLineEdit())
        fl.addRow("", steam_row)

        cb_mod = QCheckBox(tr("label.create_files_in_mod"))
        cb_mod.setChecked(False)
        mod_row = QHBoxLayout()
        mod_row.addWidget(cb_mod)
        mod_row.addWidget(QComboBox())
        fl.addRow("", mod_row)

        cb_archive = QCheckBox(tr("label.force_load_archives"))
        cb_archive.setChecked(True)
        arch_row = QHBoxLayout()
        arch_row.addWidget(cb_archive)
        arch_row.addWidget(QPushButton(tr("label.configure_archives")))
        fl.addRow("", arch_row)

        cb_icon = QCheckBox(tr("label.use_app_icon"))
        cb_icon.setChecked(True)
        fl.addRow(cb_icon)

        cb_hide = QCheckBox(tr("label.hide_in_ui"))
        cb_hide.setChecked(False)
        fl.addRow(cb_hide)

        content.addWidget(form)
        layout.addLayout(content)

        layout.addWidget(QLabel(tr("label.profile_specific")))

        # Unten rechts: OK, Abbrechen, Anwenden (ausgegraut)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton(tr("button.ok"))
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(tr("button.cancel"))
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton(tr("button.apply"))
        apply_btn.setEnabled(False)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)
