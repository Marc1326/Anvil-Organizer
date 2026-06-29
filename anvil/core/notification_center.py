"""Session-Benachrichtigungen — Datenmodell für den Glocken-Button (#14).

Reines Datenmodell ohne UI und ohne Persistenz: Einträge leben nur für die
laufende Sitzung. Bei jeder Änderung wird das Signal ``changed`` ausgelöst,
damit Badge und Panel sich aktualisieren können.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal


@dataclass
class Notification:
    level: str          # "info" | "warning" | "error"
    title: str
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    read: bool = False


class NotificationCenter(QObject):
    """Hält die Benachrichtigungen der Sitzung. Signal ``changed`` bei Mutation."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[Notification] = []

    def add(self, level: str, title: str, message: str = "") -> None:
        """Fügt eine Benachrichtigung (neueste zuerst) hinzu."""
        if not title:
            return
        if level not in ("info", "warning", "error"):
            level = "info"
        self._items.insert(0, Notification(level=level, title=str(title),
                                           message=str(message)))
        self.changed.emit()

    def items(self) -> list[Notification]:
        """Kopie der Einträge (neueste zuerst)."""
        return list(self._items)

    def unread_count(self) -> int:
        return sum(1 for n in self._items if not n.read)

    def mark_all_read(self) -> None:
        touched = False
        for n in self._items:
            if not n.read:
                n.read = True
                touched = True
        if touched:
            self.changed.emit()

    def clear(self) -> None:
        if self._items:
            self._items = []
            self.changed.emit()
