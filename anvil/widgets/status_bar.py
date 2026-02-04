"""Statusbar — MO2-Kopie: #3D3D3D, Log links, ▲ Benachrichtigungen | API rechts."""

from PySide6.QtWidgets import QStatusBar, QLabel


class StatusBarWidget(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.addWidget(
            QLabel("Log 09:40:37.515 using game plugin 'Cyberpunk 2077' ('cyberpunk2077') - aktive"),
            1,
        )
        self.addPermanentWidget(
            QLabel("▲ Benachrichtigungen | API: Queued: 0 | Daily: 20000 | Hourly: 500")
        )
