"""Export dialog for creating a .anvilpack collection."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt

from anvil.core.translator import tr


class CollectionExportDialog(QDialog):
    """Dialog for entering collection name and description before export."""

    def __init__(
        self,
        parent=None,
        *,
        game_name: str = "",
        mod_count: int = 0,
        separator_count: int = 0,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("collection.export_title"))
        self.setFixedWidth(480)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ── Title ──
        title = QLabel(tr("collection.export_title"))
        title.setStyleSheet(
            "font-size: 18px; font-weight: 600; color: #D3D3D3;"
        )
        layout.addWidget(title)

        # ── Info card ──
        info_frame = QFrame()
        info_frame.setStyleSheet(
            "QFrame { background: #1a1a1a; border-radius: 8px; }"
        )
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(16, 12, 16, 12)
        info_layout.setSpacing(4)

        game_label = QLabel(f"{tr('collection.game')}: <b>{game_name}</b>")
        game_label.setStyleSheet("color: #A0A0A0; font-size: 13px;")
        info_layout.addWidget(game_label)

        stats_text = tr(
            "collection.export_stats",
            mods=mod_count,
            separators=separator_count,
        )
        stats_label = QLabel(stats_text)
        stats_label.setStyleSheet("color: #A0A0A0; font-size: 13px;")
        info_layout.addWidget(stats_label)

        layout.addWidget(info_frame)

        # ── Collection name ──
        name_label = QLabel(tr("collection.name_label"))
        name_label.setStyleSheet("color: #D3D3D3; font-size: 13px;")
        layout.addWidget(name_label)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText(
            tr("collection.name_placeholder")
        )
        self._name_input.setStyleSheet(
            """
            QLineEdit {
                background: #1a1a1a;
                border: 1px solid #3D3D3D;
                border-radius: 6px;
                color: #D3D3D3;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #006868;
            }
            """
        )
        layout.addWidget(self._name_input)

        # ── Description (optional) ──
        desc_label = QLabel(tr("collection.description_label"))
        desc_label.setStyleSheet("color: #D3D3D3; font-size: 13px;")
        layout.addWidget(desc_label)

        self._desc_input = QTextEdit()
        self._desc_input.setPlaceholderText(
            tr("collection.description_placeholder")
        )
        self._desc_input.setMaximumHeight(80)
        self._desc_input.setStyleSheet(
            """
            QTextEdit {
                background: #1a1a1a;
                border: 1px solid #3D3D3D;
                border-radius: 6px;
                color: #D3D3D3;
                padding: 8px 12px;
                font-size: 13px;
            }
            QTextEdit:focus {
                border-color: #006868;
            }
            """
        )
        layout.addWidget(self._desc_input)

        # ── Author (optional) ──
        author_label = QLabel(tr("collection.author_label"))
        author_label.setStyleSheet("color: #D3D3D3; font-size: 13px;")
        layout.addWidget(author_label)

        self._author_input = QLineEdit()
        self._author_input.setPlaceholderText(
            tr("collection.author_placeholder")
        )
        self._author_input.setStyleSheet(
            """
            QLineEdit {
                background: #1a1a1a;
                border: 1px solid #3D3D3D;
                border-radius: 6px;
                color: #D3D3D3;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #006868;
            }
            """
        )
        layout.addWidget(self._author_input)

        # ── Buttons ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        btn_cancel = QPushButton(tr("button.cancel"))
        btn_cancel.setFixedHeight(36)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(
            """
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
        )
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        self._btn_export = QPushButton(tr("collection.export_button"))
        self._btn_export.setFixedHeight(36)
        self._btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_export.setStyleSheet(
            """
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
            """
        )
        self._btn_export.clicked.connect(self._on_export)
        btn_layout.addWidget(self._btn_export)

        layout.addLayout(btn_layout)

        # Focus on name input
        self._name_input.setFocus()

    # ── Public API ──────────────────────────────────────────────────

    def collection_name(self) -> str:
        """Return the entered collection name."""
        return self._name_input.text().strip()

    def collection_description(self) -> str:
        """Return the entered description."""
        return self._desc_input.toPlainText().strip()

    def collection_author(self) -> str:
        """Return the entered author name."""
        return self._author_input.text().strip()

    # ── Slots ───────────────────────────────────────────────────────

    def _on_export(self) -> None:
        """Validate and accept."""
        if not self._name_input.text().strip():
            self._name_input.setFocus()
            self._name_input.setStyleSheet(
                """
                QLineEdit {
                    background: #1a1a1a;
                    border: 1px solid #ff4444;
                    border-radius: 6px;
                    color: #D3D3D3;
                    padding: 8px 12px;
                    font-size: 13px;
                }
                """
            )
            return
        self.accept()
