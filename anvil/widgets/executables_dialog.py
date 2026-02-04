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
        self.setWindowTitle("Ausführbare Programme ändern")
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
        prog_row.addWidget(QLabel("Programme"))
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

        fl.addRow("Name:", QLineEdit())

        exe_row = QHBoxLayout()
        exe_edit = QLineEdit()
        exe_edit.setPlaceholderText("Ausführbare Datei")
        exe_row.addWidget(exe_edit)
        exe_row.addWidget(QPushButton("..."))
        fl.addRow("Ausführbare Datei:", exe_row)

        work_row = QHBoxLayout()
        work_edit = QLineEdit()
        work_edit.setPlaceholderText("Arbeitsverzeichnis")
        work_row.addWidget(work_edit)
        work_row.addWidget(QPushButton("..."))
        fl.addRow("Arbeitsverzeichnis:", work_row)

        fl.addRow("Startparameter:", QLineEdit())

        cb_steam = QCheckBox("Überschreibt die Steam AppID")
        cb_steam.setChecked(False)
        steam_row = QHBoxLayout()
        steam_row.addWidget(cb_steam)
        steam_row.addWidget(QLineEdit())
        fl.addRow("", steam_row)

        cb_mod = QCheckBox("Erzeuge Dateien im Mod-Verzeichnis statt im Overwrite (*)")
        cb_mod.setChecked(False)
        mod_row = QHBoxLayout()
        mod_row.addWidget(cb_mod)
        mod_row.addWidget(QComboBox())
        fl.addRow("", mod_row)

        cb_archive = QCheckBox("Erzwinge das Laden der Archive (*)")
        cb_archive.setChecked(True)
        arch_row = QHBoxLayout()
        arch_row.addWidget(cb_archive)
        arch_row.addWidget(QPushButton("Archive konfigurieren"))
        fl.addRow("", arch_row)

        cb_icon = QCheckBox("Nutze das Icon der Anwendung für Desktopverknüpfungen")
        cb_icon.setChecked(True)
        fl.addRow(cb_icon)

        cb_hide = QCheckBox("In der Benutzeroberfläche verbergen")
        cb_hide.setChecked(False)
        fl.addRow(cb_hide)

        content.addWidget(form)
        layout.addLayout(content)

        layout.addWidget(QLabel("(*) Profilspezifisch"))

        # Unten rechts: OK, Abbrechen, Anwenden (ausgegraut)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        apply_btn = QPushButton("Anwenden")
        apply_btn.setEnabled(False)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)
