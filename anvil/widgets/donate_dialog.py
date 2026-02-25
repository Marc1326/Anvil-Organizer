"""Donate dialog — Ko-fi, Bitcoin, Monero with QR codes."""

from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QWidget, QApplication,
)

from anvil.core.resource_path import get_anvil_base

_ICONS_DIR = get_anvil_base() / "styles" / "icons"
_DONATE_DIR = _ICONS_DIR / "donate"

BTC_ADDR = "bc1q6ghal7tewh38gdggt8z8qeqr99u3y5ehmruwk9"
XMR_ADDR = "4AGPyk5G4NwZboyQJcWQKwMFLTjs3fmoG9CFVBrkE3UFcpCaQyEmC93PgaeW1uuL65aLW1qKa8sd4Wo6NSu4HkvF117n5km"
KOFI_URL = "https://ko-fi.com/marc1326"


class DonateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Support / Donate")
        self.setMinimumWidth(420)
        self.setMaximumWidth(500)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header = QLabel("Thank you for considering a donation! ❤️")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px;")
        layout.addWidget(header)

        # Tab buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self._btn_kofi = QPushButton("☕  Ko-fi")
        self._btn_btc = QPushButton("₿  Bitcoin")
        self._btn_xmr = QPushButton("ɱ  Monero")

        for btn in (self._btn_kofi, self._btn_btc, self._btn_xmr):
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(36)
            btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #555;
                    border-radius: 4px;
                    padding: 6px 16px;
                    font-size: 13px;
                }
                QPushButton:checked {
                    background-color: #3a6ea5;
                    color: white;
                    border-color: #3a6ea5;
                }
                QPushButton:hover:!checked {
                    background-color: #3a3a3a;
                }
            """)
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)

        # Stacked pages
        self._stack = QStackedWidget()
        self._stack.addWidget(self._create_kofi_page())
        self._stack.addWidget(self._create_crypto_page("Bitcoin", BTC_ADDR, "btc_qr.png"))
        self._stack.addWidget(self._create_crypto_page("Monero", XMR_ADDR, "xmr_qr.png"))
        layout.addWidget(self._stack)

        # Wire buttons
        self._btn_kofi.clicked.connect(lambda: self._switch(0))
        self._btn_btc.clicked.connect(lambda: self._switch(1))
        self._btn_xmr.clicked.connect(lambda: self._switch(2))

        # Default: Ko-fi
        self._switch(0)

    def _switch(self, idx: int):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate((self._btn_kofi, self._btn_btc, self._btn_xmr)):
            btn.setChecked(i == idx)

    def _create_kofi_page(self) -> QWidget:
        page = QWidget()
        vbox = QVBoxLayout(page)
        vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.setSpacing(16)

        desc = QLabel("Support the project on Ko-fi.\nOne-time donations or monthly support.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("font-size: 13px; color: #ccc;")
        vbox.addWidget(desc)

        open_btn = QPushButton("☕  Open Ko-fi Page")
        open_btn.setMinimumHeight(44)
        open_btn.setEnabled(False)
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: #888;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 24px;
            }
        """)
        vbox.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        note = QLabel("Coming soon — payment method not yet configured.")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet("font-size: 11px; color: #888;")
        vbox.addWidget(note)

        return page

    def _create_crypto_page(self, name: str, addr: str, qr_file: str) -> QWidget:
        page = QWidget()
        vbox = QVBoxLayout(page)
        vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.setSpacing(12)

        # QR code image
        qr_path = _DONATE_DIR / qr_file
        qr_label = QLabel()
        qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if qr_path.exists():
            pixmap = QPixmap(str(qr_path))
            qr_label.setPixmap(pixmap.scaled(
                QSize(200, 200),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        else:
            qr_label.setText(f"[QR code not found]\nRun generate_qr.py first")
            qr_label.setStyleSheet("color: #ff5555; font-size: 12px; padding: 20px;")

        vbox.addWidget(qr_label)

        # Address label (selectable)
        addr_label = QLabel(f"<b>{name} Address:</b>")
        addr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        addr_label.setStyleSheet("font-size: 12px;")
        vbox.addWidget(addr_label)

        # Address text (word-wrapped, selectable)
        addr_text = QLabel(addr)
        addr_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        addr_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        addr_text.setWordWrap(True)
        addr_text.setStyleSheet("""
            font-size: 11px;
            font-family: monospace;
            color: #aaa;
            padding: 4px 12px;
            background: #2a2a2a;
            border-radius: 4px;
        """)
        vbox.addWidget(addr_text)

        # Copy button
        copy_btn = QPushButton("📋  Copy Address")
        copy_btn.setMinimumHeight(36)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #555;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)

        def _copy():
            clipboard = QGuiApplication.clipboard()
            if clipboard:
                clipboard.setText(addr)
                copy_btn.setText("✓  Copied!")
                # Reset after 2s
                from PySide6.QtCore import QTimer
                QTimer.singleShot(2000, lambda: copy_btn.setText("📋  Copy Address"))

        copy_btn.clicked.connect(_copy)
        vbox.addWidget(copy_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        return page
