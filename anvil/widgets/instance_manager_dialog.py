"""Instanz Manager — QDialog zum Verwalten von Instanzen (Platzhalter)."""

from pathlib import Path

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
    QWidget,
    QFrame,
    QSizePolicy,
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

_ICONS_DIR = Path(__file__).resolve().parent.parent / "styles" / "icons"

_DIALOG_STYLE = """
QDialog { background: #1C1C1C; }
QWidget { background: #1C1C1C; color: #D3D3D3; }
QLineEdit, QListWidget, QPushButton {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 4px;
}
QListWidget::item:selected { background: #3D3D3D; color: #D3D3D3; }
QPushButton#deleteInstance { background: #5a2020; color: #D3D3D3; }
QPushButton#deleteInstance:hover { background: #7a2828; }
QPushButton#linkButton { background: transparent; color: #6ab; border: none; text-align: left; }
QPushButton#linkButton:hover { color: #8cd; }
"""


def _icon(name: str) -> QIcon:
    path = _ICONS_DIR / name
    if path.exists():
        return QIcon(str(path))
    return QIcon()


class InstanceManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Instanz Manager")
        self.setMinimumSize(720, 480)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Oben: "+ Erstelle neue Instanz" und "Was ist eine Instanz?" Link
        top_row = QHBoxLayout()
        new_btn = QPushButton("+ Erstelle neue Instanz")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        top_row.addWidget(new_btn)
        link_btn = QPushButton("Was ist eine Instanz?")
        link_btn.setObjectName("linkButton")
        link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        top_row.addWidget(link_btn)
        top_row.addStretch()
        layout.addLayout(top_row)

        # Mitte: Links Liste, rechts Formular
        content = QHBoxLayout()
        content.setSpacing(12)

        # Links: QListWidget mit Platzhalter
        instance_list = QListWidget()
        instance_list.setMinimumWidth(200)
        item = QListWidgetItem("Cyberpunk 2077")
        item.setIcon(_icon("instances.svg"))
        instance_list.addItem(item)
        content.addWidget(instance_list)

        # Rechts: Formular
        form = QFrame()
        form.setFrameShape(QFrame.Shape.NoFrame)
        form_layout = QFormLayout(form)
        form_layout.setSpacing(8)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Name")
        form_layout.addRow("Name:", name_edit)

        ort_row = QHBoxLayout()
        ort_edit = QLineEdit()
        ort_edit.setPlaceholderText("Ort")
        ort_btn = QPushButton("Suche")
        ort_row.addWidget(ort_edit)
        ort_row.addWidget(ort_btn)
        form_layout.addRow("Ort:", ort_row)

        basis_row = QHBoxLayout()
        basis_edit = QLineEdit()
        basis_edit.setPlaceholderText("Basis Ordner")
        basis_btn = QPushButton("Suche")
        basis_row.addWidget(basis_edit)
        basis_row.addWidget(basis_btn)
        form_layout.addRow("Basis Ordner:", basis_row)

        spiel_edit = QLineEdit()
        spiel_edit.setPlaceholderText("Spiel")
        form_layout.addRow("Spiel:", spiel_edit)

        spiel_dir_row = QHBoxLayout()
        spiel_dir_edit = QLineEdit()
        spiel_dir_edit.setPlaceholderText("Spiel Verzeichnis")
        spiel_dir_btn = QPushButton("Suche")
        spiel_dir_row.addWidget(spiel_dir_edit)
        spiel_dir_row.addWidget(spiel_dir_btn)
        form_layout.addRow("Spiel Verzeichnis:", spiel_dir_row)

        content.addWidget(form, 1)
        layout.addLayout(content)

        # Unten: Filter links, Buttons rechts
        bottom_row = QHBoxLayout()
        filter_edit = QLineEdit()
        filter_edit.setPlaceholderText("Filter")
        filter_edit.setMaximumWidth(200)
        bottom_row.addWidget(filter_edit)
        bottom_row.addStretch()

        open_ini_btn = QPushButton("Öffne INI")
        delete_btn = QPushButton("Lösche Instanz")
        delete_btn.setObjectName("deleteInstance")
        switch_btn = QPushButton("Wechsle zu dieser Instanz")
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(open_ini_btn)
        bottom_row.addWidget(delete_btn)
        bottom_row.addWidget(switch_btn)
        bottom_row.addWidget(close_btn)
        layout.addLayout(bottom_row)
