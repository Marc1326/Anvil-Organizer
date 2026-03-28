"""Auswahldialog fuer Export/Import/Backup — waehlt Aktion und Format."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt

from anvil.core.translator import tr

_CARD_NORMAL = """
    QFrame {
        background: #1a1a1a;
        border: 1px solid #3D3D3D;
        border-radius: 8px;
    }
"""
_CARD_SELECTED = """
    QFrame {
        background: #1a1a1a;
        border: 1px solid #006868;
        border-radius: 8px;
    }
"""
_BTN_CANCEL = """
    QPushButton {
        background: #3D3D3D;
        color: #D3D3D3;
        border: none;
        border-radius: 6px;
        padding: 0 20px;
        font-size: 13px;
        font-weight: 500;
    }
    QPushButton:hover {
        background: #4D4D4D;
    }
"""
_BTN_PRIMARY = """
    QPushButton {
        background: #006868;
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        padding: 0 20px;
        font-size: 13px;
        font-weight: 500;
    }
    QPushButton:hover {
        background: #007878;
    }
"""
_TAB_NORMAL = """
    QPushButton {
        background: transparent;
        color: #808080;
        border: none;
        border-bottom: 2px solid transparent;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 500;
    }
    QPushButton:hover {
        color: #D3D3D3;
    }
"""
_TAB_ACTIVE = """
    QPushButton {
        background: transparent;
        color: #D3D3D3;
        border: none;
        border-bottom: 2px solid #006868;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 600;
    }
"""


class _OptionCard(QFrame):
    """Klickbare Karte fuer eine Auswahloption."""

    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_CARD_NORMAL)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._selected = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        self._title = QLabel(title)
        self._title.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #D3D3D3; background: transparent; border: none;"
        )
        layout.addWidget(self._title)

        self._desc = QLabel(description)
        self._desc.setStyleSheet(
            "font-size: 11px; color: #808080; background: transparent; border: none;"
        )
        self._desc.setWordWrap(True)
        layout.addWidget(self._desc)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setStyleSheet(_CARD_SELECTED if selected else _CARD_NORMAL)

    def mousePressEvent(self, event):
        # Dialog finden (kann mehrere Parent-Ebenen hoch sein)
        w = self.parent()
        while w and not isinstance(w, QDialog):
            w = w.parent()
        if w and hasattr(w, "_card_clicked"):
            w._card_clicked(self)
        super().mousePressEvent(event)


class ExportImportDialog(QDialog):
    """Dialog zur Auswahl von Aktion und Format."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("export_import.title"))
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.resize(700, 600)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self.setStyleSheet("QDialog { background: #242424; }")

        self._current_tab = "export"
        self._selected_format = "csv"
        self._selected_backup = "create"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # -- Titel --
        title = QLabel(tr("export_import.title"))
        title.setStyleSheet(
            "font-size: 18px; font-weight: 600; color: #D3D3D3; background: transparent;"
        )
        layout.addWidget(title)

        # -- Tab-Leiste --
        tab_layout = QHBoxLayout()
        tab_layout.setSpacing(0)

        self._tab_export = QPushButton(tr("export_import.export_radio"))
        self._tab_import = QPushButton(tr("export_import.import_radio"))
        self._tab_backup = QPushButton(tr("export_import.backup_radio"))

        for btn in (self._tab_export, self._tab_import, self._tab_backup):
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._tab_export.setStyleSheet(_TAB_ACTIVE)
        self._tab_import.setStyleSheet(_TAB_NORMAL)
        self._tab_backup.setStyleSheet(_TAB_NORMAL)

        self._tab_export.clicked.connect(lambda: self._switch_tab("export"))
        self._tab_import.clicked.connect(lambda: self._switch_tab("import"))
        self._tab_backup.clicked.connect(lambda: self._switch_tab("backup"))

        tab_layout.addWidget(self._tab_export)
        tab_layout.addWidget(self._tab_import)
        tab_layout.addWidget(self._tab_backup)
        tab_layout.addStretch()

        layout.addLayout(tab_layout)

        # -- Trennlinie --
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #3D3D3D;")
        layout.addWidget(sep)

        # -- Format-Cards --
        self._format_container = QFrame()
        self._format_container.setStyleSheet("background: transparent; border: none;")
        fmt_layout = QVBoxLayout(self._format_container)
        fmt_layout.setContentsMargins(0, 0, 0, 0)
        fmt_layout.setSpacing(12)

        self._card_csv = _OptionCard(
            tr("export_import.csv_radio"),
            tr("export_import.csv_desc"),
            self,
        )
        self._card_csv.set_selected(True)
        fmt_layout.addWidget(self._card_csv)

        self._card_anvilpack = _OptionCard(
            tr("export_import.anvilpack_radio"),
            tr("export_import.anvilpack_desc"),
            self,
        )
        fmt_layout.addWidget(self._card_anvilpack)

        self._format_cards = [self._card_csv, self._card_anvilpack]
        layout.addWidget(self._format_container)

        # -- Backup-Cards --
        self._backup_container = QFrame()
        self._backup_container.setStyleSheet("background: transparent; border: none;")
        bak_layout = QVBoxLayout(self._backup_container)
        bak_layout.setContentsMargins(0, 0, 0, 0)
        bak_layout.setSpacing(12)

        self._card_backup_create = _OptionCard(
            tr("export_import.backup_create"),
            tr("export_import.backup_create_desc"),
            self,
        )
        self._card_backup_create.set_selected(True)
        bak_layout.addWidget(self._card_backup_create)

        self._card_backup_restore = _OptionCard(
            tr("export_import.backup_restore"),
            tr("export_import.backup_restore_desc"),
            self,
        )
        bak_layout.addWidget(self._card_backup_restore)

        self._backup_cards = [self._card_backup_create, self._card_backup_restore]
        layout.addWidget(self._backup_container)
        self._backup_container.setVisible(False)

        # -- Spacer --
        layout.addStretch()

        # -- Buttons --
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        btn_cancel = QPushButton(tr("button.cancel"))
        btn_cancel.setFixedHeight(36)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(_BTN_CANCEL)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_next = QPushButton(tr("export_import.next_button"))
        btn_next.setFixedHeight(36)
        btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_next.setStyleSheet(_BTN_PRIMARY)
        btn_next.clicked.connect(self.accept)
        btn_layout.addWidget(btn_next)

        layout.addLayout(btn_layout)

    # -- Tab-Wechsel --

    def _switch_tab(self, tab: str) -> None:
        self._current_tab = tab
        self._tab_export.setStyleSheet(_TAB_ACTIVE if tab == "export" else _TAB_NORMAL)
        self._tab_import.setStyleSheet(_TAB_ACTIVE if tab == "import" else _TAB_NORMAL)
        self._tab_backup.setStyleSheet(_TAB_ACTIVE if tab == "backup" else _TAB_NORMAL)
        self._format_container.setVisible(tab != "backup")
        self._backup_container.setVisible(tab == "backup")

    # -- Card-Klick --

    def _card_clicked(self, card: _OptionCard) -> None:
        if card in self._format_cards:
            for c in self._format_cards:
                c.set_selected(c is card)
            self._selected_format = "csv" if card is self._card_csv else "anvilpack"
        elif card in self._backup_cards:
            for c in self._backup_cards:
                c.set_selected(c is card)
            self._selected_backup = "create" if card is self._card_backup_create else "restore"

    # -- Getter --

    def action(self) -> str:
        return self._current_tab

    def format_type(self) -> str:
        return self._selected_format

    def backup_action(self) -> str:
        return self._selected_backup
