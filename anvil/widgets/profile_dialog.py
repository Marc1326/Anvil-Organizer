"""Profile — QDialog zum Verwalten von Profilen (Platzhalter)."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QCheckBox,
)
from PySide6.QtCore import Qt

_PROFILE_DIALOG_STYLE = """
QDialog {
    background: #1C1C1C;
    border: none;
}
QWidget {
    background: #1C1C1C;
    color: #D3D3D3;
    border: none;
}
QListWidget {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 4px;
}
QPushButton {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 4px;
    min-width: 80px;
}
QListWidget::item:selected { background: #3D3D3D; color: #D3D3D3; }
"""


class ProfileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Profile")
        self.setMinimumSize(520, 380)
        self.setStyleSheet(_PROFILE_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Mitte: Links Liste, rechts Buttons
        content = QHBoxLayout()
        content.setSpacing(12)

        # Links: QListWidget mit Platzhalter "aktive" (selektiert), "Default"
        profile_list = QListWidget()
        profile_list.setMinimumWidth(180)
        item_active = QListWidgetItem("aktive")
        item_default = QListWidgetItem("Default")
        profile_list.addItem(item_active)
        profile_list.addItem(item_default)
        profile_list.setCurrentItem(item_active)
        content.addWidget(profile_list)

        # Rechts: Buttons vertikal
        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)
        btn_col.addWidget(QPushButton("Neu"))
        btn_col.addWidget(QPushButton("Kopieren"))
        btn_col.addWidget(QPushButton("Löschen"))
        btn_col.addWidget(QPushButton("Umbenennen"))
        btn_col.addWidget(QPushButton("Spielstände übertragen"))
        btn_col.addStretch()
        content.addLayout(btn_col)
        layout.addLayout(content)

        # Unten: drei Checkboxen (alle aktiviert), eine ausgegraut
        cb_row = QVBoxLayout()
        cb_saves = QCheckBox("Profil-Spezifische Speicherstände benutzen")
        cb_saves.setChecked(True)
        cb_ini = QCheckBox("Profil-Spezifische INI-Dateien nutzen")
        cb_ini.setChecked(True)
        cb_archive = QCheckBox("Automatische Archiv Invalidierung")
        cb_archive.setChecked(True)
        cb_archive.setEnabled(False)
        cb_row.addWidget(cb_saves)
        cb_row.addWidget(cb_ini)
        cb_row.addWidget(cb_archive)
        layout.addLayout(cb_row)

        # Unten rechts: Auswählen, Schliessen
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        select_btn = QPushButton("Auswählen")
        close_btn = QPushButton("Schliessen")
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(select_btn)
        bottom_row.addWidget(close_btn)
        layout.addLayout(bottom_row)
