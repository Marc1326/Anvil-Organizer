"""Backup selection dialog with card-based UI."""

import zipfile
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QScrollArea, QWidget,
)
from PySide6.QtCore import Qt


CARD_STYLE_NORMAL = """
    QFrame {
        background: #141414;
        border-radius: 8px;
        border: 2px solid transparent;
    }
    QFrame:hover {
        background: #3D3D3D;
    }
"""

CARD_STYLE_SELECTED = """
    QFrame {
        background: #006868;
        border-radius: 8px;
        border: 2px solid #008888;
    }
"""


class BackupCard(QFrame):
    """A clickable card representing a backup."""

    def __init__(self, backup_path: Path, parent=None):
        super().__init__(parent)
        self.backup_path = backup_path
        self._selected = False

        self.setMinimumHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(CARD_STYLE_NORMAL)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Parse date from filename: backup_2026_02_15_14_39_20.zip
        name = backup_path.stem
        try:
            parts = name.replace("backup_", "").split("_")
            dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]),
                         int(parts[3]), int(parts[4]), int(parts[5]))
            date_str = dt.strftime("%d. %b %Y — %H:%M")
        except (ValueError, IndexError):
            date_str = name

        # Count mods and get size
        mod_count = 0
        try:
            with zipfile.ZipFile(backup_path, 'r') as zf:
                mod_count = len([n for n in zf.namelist()
                               if n.startswith("mods/") and n.endswith("/meta.ini")])
        except:
            pass

        size = backup_path.stat().st_size
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.0f} KB"
        else:
            size_str = f"{size / (1024*1024):.1f} MB"

        # Date label
        self._date_label = QLabel(date_str)
        self._date_label.setStyleSheet("""
            font-weight: 600;
            font-size: 14px;
            color: #D3D3D3;
            background: transparent;
        """)
        layout.addWidget(self._date_label)

        # Info label
        self._info_label = QLabel(f"{mod_count} Mods  ·  {size_str}")
        self._info_label.setStyleSheet("""
            font-size: 12px;
            color: #808080;
            background: transparent;
        """)
        layout.addWidget(self._info_label)

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self.setStyleSheet(CARD_STYLE_SELECTED)
            self._date_label.setStyleSheet("""
                font-weight: 600;
                font-size: 14px;
                color: #FFFFFF;
                background: transparent;
            """)
            self._info_label.setStyleSheet("""
                font-size: 12px;
                color: #B0E0E0;
                background: transparent;
            """)
        else:
            self.setStyleSheet(CARD_STYLE_NORMAL)
            self._date_label.setStyleSheet("""
                font-weight: 600;
                font-size: 14px;
                color: #D3D3D3;
                background: transparent;
            """)
            self._info_label.setStyleSheet("""
                font-size: 12px;
                color: #808080;
                background: transparent;
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            dialog = self.window()
            if hasattr(dialog, '_select_card'):
                dialog._select_card(self)
        super().mousePressEvent(event)


class BackupDialog(QDialog):
    """Card-based backup selection dialog."""

    def __init__(self, parent, backups: list[Path]):
        super().__init__(parent)
        self.setWindowTitle("Sicherung wiederherstellen")
        self.setFixedWidth(400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.setStyleSheet("""
            QDialog {
                background: #242424;
            }
        """)

        self._selected_backup: Path | None = None
        self._cards: list[BackupCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("Sicherung wiederherstellen")
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: 600;
            color: #D3D3D3;
            background: transparent;
        """)
        layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Wähle eine Sicherung zum Wiederherstellen:")
        subtitle.setStyleSheet("""
            font-size: 13px;
            color: #808080;
            background: transparent;
        """)
        layout.addWidget(subtitle)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #242424;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3D3D3D;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #006868;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        scroll.setMaximumHeight(280)

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 8, 0)
        scroll_layout.setSpacing(8)

        for backup in backups:
            card = BackupCard(backup, self)
            self._cards.append(card)
            scroll_layout.addWidget(card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        self._btn_cancel = QPushButton("Abbrechen")
        self._btn_cancel.setFixedHeight(36)
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.setStyleSheet("""
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
        """)
        self._btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_cancel)

        self._btn_restore = QPushButton("Wiederherstellen")
        self._btn_restore.setFixedHeight(36)
        self._btn_restore.setEnabled(False)
        self._btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_restore.setStyleSheet("""
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
            QPushButton:disabled {
                background: #3D3D3D;
                color: #808080;
            }
        """)
        self._btn_restore.clicked.connect(self.accept)
        btn_layout.addWidget(self._btn_restore)

        layout.addLayout(btn_layout)

        # Adjust height based on content
        self.adjustSize()

    def _select_card(self, card: BackupCard):
        """Handle card selection."""
        for c in self._cards:
            c.set_selected(c == card)
        self._selected_backup = card.backup_path
        self._btn_restore.setEnabled(True)

    def selected_backup(self) -> Path | None:
        """Return the selected backup path."""
        return self._selected_backup
