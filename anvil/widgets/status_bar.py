"""Statusbar — MO2-Kopie: Instanz-Info links, Benachrichtigungen + API rechts."""

from __future__ import annotations

from PySide6.QtWidgets import QStatusBar, QLabel

from anvil.core.translator import tr


class StatusBarWidget(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._left_label = QLabel("")
        self.addWidget(self._left_label, 1)

        self._notifications_label = QLabel(tr("status.notifications"))
        self.addPermanentWidget(self._notifications_label)

        self._api_label = QLabel(tr("status.api_not_logged_in"))
        self._api_label.setStyleSheet(
            "QLabel { padding: 2px 6px; }"
        )
        self.addPermanentWidget(self._api_label)

    def update_instance(
        self,
        game_name: str,
        short_name: str,
        store: str,
    ) -> None:
        """Update the status bar with the active instance info."""
        store_text = store or tr("status.unknown")
        self._left_label.setText(
            tr("status.instance_info", game=game_name, plugin=short_name, store=store_text)
        )

    def clear_instance(self) -> None:
        """Clear the instance info."""
        self._left_label.setText(tr("status.no_instance"))

    def update_api_status(
        self,
        daily_remaining: int = -1,
        hourly_remaining: int = -1,
        queued: int = 0,
        logged_in: bool = True,
    ) -> None:
        """Update the API rate limit display (MO2 style with color coding).

        Color scheme (from MO2 statusbar.cpp):
        - Green: remaining > 500
        - Yellow: 200..500
        - Red: < 200
        """
        if not logged_in or (daily_remaining < 0 and hourly_remaining < 0):
            self._api_label.setText(tr("status.api_not_logged_in"))
            self._api_label.setStyleSheet("QLabel { padding: 2px 6px; }")
            return

        text = f"API  Queued: {queued} | Daily: {daily_remaining} | Hourly: {hourly_remaining}"
        self._api_label.setText(text)

        self._api_label.setStyleSheet("QLabel { padding: 2px 6px; }")
