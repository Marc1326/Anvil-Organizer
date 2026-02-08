"""Statusbar — MO2-Kopie: #3D3D3D, Instanz-Info links, ▲ Benachrichtigungen | API rechts."""

from __future__ import annotations

from PySide6.QtWidgets import QStatusBar, QLabel


class StatusBarWidget(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._left_label = QLabel("")
        self.addWidget(self._left_label, 1)
        self._right_label = QLabel(
            "\u25b2 Benachrichtigungen | API: Queued: 0 | Daily: 20000 | Hourly: 500"
        )
        self.addPermanentWidget(self._right_label)

    def update_instance(
        self,
        game_name: str,
        short_name: str,
        store: str,
    ) -> None:
        """Update the status bar with the active instance info."""
        store_text = store or "unbekannt"
        self._left_label.setText(
            f"Instanz: {game_name} | Plugin: {short_name} | Store: {store_text}"
        )

    def clear_instance(self) -> None:
        """Clear the instance info."""
        self._left_label.setText("Keine Instanz ausgewählt")
