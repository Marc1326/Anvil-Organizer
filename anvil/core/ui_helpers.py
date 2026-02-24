"""Zentrale UI-Hilfsfunktionen für Dialoge."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QInputDialog


def _center_on_parent(dialog):
    """Center a QDialog on its parent if Interface/center_dialogs is enabled."""
    s = QSettings(
        str(Path.home() / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf"),
        QSettings.Format.IniFormat,
    )
    if not s.value("Interface/center_dialogs", False, type=bool):
        return
    parent = dialog.parent()
    if parent is None:
        return
    dialog.adjustSize()
    pg = parent.frameGeometry()
    x = pg.center().x() - dialog.width() // 2
    y = pg.center().y() - dialog.height() // 2
    dialog.move(x, y)


def get_text_input(parent, title: str, label: str, text: str = "") -> tuple[str, bool]:
    """QInputDialog.getText() mit Mindestgröße (450×180) und Zentrierung."""
    dlg = QInputDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setLabelText(label)
    dlg.setTextValue(text)
    dlg.setMinimumSize(450, 180)
    dlg.resize(450, 180)
    _center_on_parent(dlg)
    ok = dlg.exec() == QDialog.DialogCode.Accepted
    return dlg.textValue(), ok
