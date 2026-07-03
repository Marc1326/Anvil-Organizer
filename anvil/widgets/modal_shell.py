"""Moderne Modal-Hülle: Titelleiste + Fußleiste + Backdrop für Dialoge."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from anvil.styles.dark_theme import theme_color


def is_modern_theme_active() -> bool:
    """True wenn das moderne Theme (Anvil Dunkel/Hell) aktiv ist."""
    return bool(theme_color("panel2", ""))


def wrap_modal(dialog: QDialog, title: str,
               footer_buttons: list[QPushButton] | None = None,
               *, close_slot=None) -> QVBoxLayout:
    """Rahmenlose Modal-Hülle (Titelleiste 52px + ✕, Fußleiste 60px).

    Gibt das Inhalts-Layout zurück, das der Aufrufer füllt.
    Fußleisten-Buttons müssen ihre objectNames bereits tragen.
    """
    dialog.setWindowFlags(
        Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)

    outer = QVBoxLayout(dialog)
    outer.setSpacing(0)
    outer.setContentsMargins(0, 0, 0, 0)
    frame = QWidget()
    frame.setObjectName("modalFrame")
    frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    outer.addWidget(frame)
    shell = QVBoxLayout(frame)
    shell.setSpacing(0)
    shell.setContentsMargins(1, 1, 1, 1)

    title_bar = QWidget()
    title_bar.setObjectName("instTitleBar")
    title_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    title_bar.setFixedHeight(52)
    tb = QHBoxLayout(title_bar)
    tb.setContentsMargins(16, 0, 16, 0)
    tb.setSpacing(10)
    t_lbl = QLabel(title)
    t_lbl.setObjectName("instTitleLabel")
    tb.addWidget(t_lbl)
    tb.addStretch()
    x_btn = QPushButton("✕")
    x_btn.setObjectName("instCloseBtn")
    x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    x_btn.clicked.connect(close_slot or dialog.reject)
    tb.addWidget(x_btn)
    shell.addWidget(title_bar)

    body = QWidget()
    content = QVBoxLayout(body)
    content.setContentsMargins(16, 14, 16, 14)
    content.setSpacing(10)
    shell.addWidget(body, 1)

    if footer_buttons:
        footer = QWidget()
        footer.setObjectName("instFooter")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        footer.setFixedHeight(60)
        fr = QHBoxLayout(footer)
        fr.setContentsMargins(16, 0, 16, 0)
        fr.setSpacing(8)
        fr.addStretch()
        for btn in footer_buttons:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            fr.addWidget(btn)
        shell.addWidget(footer)

    return content


def exec_with_backdrop(dialog: QDialog, modern: bool):
    """QDialog.exec mit abgedunkeltem Hauptfenster (nur modern)."""
    if modern and dialog.parent() is not None:
        from anvil.widgets.modal_backdrop import ModalBackdrop
        backdrop = ModalBackdrop(dialog.parent().window())
        try:
            return QDialog.exec(dialog)
        finally:
            backdrop.dismiss()
    return QDialog.exec(dialog)
