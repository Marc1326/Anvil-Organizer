"""Collapsible section bar: QLabel that toggles tree visibility on double-click."""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel, QWidget


_COLLAPSED_HEIGHT = 28  # label-only height (matches pane minimumHeight)
_MAX_HEIGHT = 16777215  # QWIDGETSIZE_MAX — no constraint


class CollapsibleSectionBar(QLabel):
    """A section label that collapses/expands an associated widget on double-click.

    - Single click does nothing.
    - Double click toggles the target widget's visibility.
    - Arrow indicator (▼ open / ▶ closed) is prepended to the text.
    - Collapse state is persisted via QSettings.
    - When a *container* (the QSplitter pane) is provided, its maximumHeight
      is constrained so the splitter reclaims space on collapse.
    """

    def __init__(
        self,
        title: str,
        settings_key: str,
        target: QWidget,
        style: str,
        container: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._settings_key = f"{settings_key}/collapsed"
        self._target = target
        self._container = container
        self._count: int | None = None

        self.setStyleSheet(style)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Restore persisted state
        settings = QSettings()
        self._collapsed = settings.value(self._settings_key, False, type=bool)

        self._apply_state()

    # ── Public API ─────────────────────────────────────────────────

    def set_count(self, count: int) -> None:
        """Update the count shown in parentheses."""
        self._count = count
        self._update_text()

    def set_title(self, title: str) -> None:
        """Change the base title."""
        self._title = title
        self._update_text()

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    # ── Events ─────────────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._collapsed = not self._collapsed
            self._apply_state()
            self._persist()
        else:
            super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Consume single clicks — do nothing
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        event.accept()

    # ── Internals ──────────────────────────────────────────────────

    def _apply_state(self) -> None:
        """Apply collapsed/expanded state to target widget and update text."""
        self._target.setVisible(not self._collapsed)
        if self._container is not None:
            if self._collapsed:
                self._container.setMaximumHeight(_COLLAPSED_HEIGHT)
            else:
                self._container.setMaximumHeight(_MAX_HEIGHT)
        self._update_text()

    def _update_text(self) -> None:
        arrow = "▶" if self._collapsed else "▼"
        if self._count is not None:
            self.setText(f"{arrow} {self._title} ({self._count})")
        else:
            self.setText(f"{arrow} {self._title}")

    def _persist(self) -> None:
        settings = QSettings()
        settings.setValue(self._settings_key, self._collapsed)
