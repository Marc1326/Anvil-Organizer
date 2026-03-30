"""Collapsible section bar: QLabel that toggles tree visibility on click."""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


_COLLAPSED_HEIGHT = 28  # label-only height (matches pane minimumHeight)
_MAX_HEIGHT = 16777215  # QWIDGETSIZE_MAX — no constraint


class CollapsibleSectionBar(QWidget):
    """A section bar that collapses/expands an associated widget on click.

    - Single click toggles the target widget's visibility.
    - Arrow indicator (▼ open / ▶ closed) is prepended to the text.
    - Collapse state is persisted via QSettings.
    - When a *container* (the QSplitter pane) is provided, its maximumHeight
      is constrained so the splitter reclaims space on collapse.
    - Optional action button on the right side via add_action_button().
    """

    toggled = Signal(bool)  # emitted on state change; True = expanded (not collapsed)

    def __init__(
        self,
        title: str,
        settings_key: str,
        target: QWidget,
        style: str,
        container: QWidget | None = None,
        parent: QWidget | None = None,
        default_collapsed: bool = False,
        max_expanded_height: int = _MAX_HEIGHT,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._settings_key = f"{settings_key}/collapsed"
        self._target = target
        self._container = container
        self._max_expanded_height = max_expanded_height
        self._count: int | None = None

        # Layout: [label .................. action_button]
        hlayout = QHBoxLayout(self)
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.setSpacing(0)

        self._label = QLabel()
        self._label.setStyleSheet(style)
        self._label.setCursor(Qt.CursorShape.PointingHandCursor)
        hlayout.addWidget(self._label, 1)

        self._action_btn: QPushButton | None = None

        self.setStyleSheet(style)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Restore persisted state (falls back to default_collapsed)
        settings = QSettings()
        self._collapsed = settings.value(self._settings_key, default_collapsed, type=bool)

        self._apply_state()

    # ── Public API ─────────────────────────────────────────────────

    def add_action_button(self, text: str, tooltip: str = "") -> QPushButton:
        """Add a small action button on the right side of the header bar.

        Returns the QPushButton so the caller can connect its clicked signal.
        """
        btn = QPushButton(text)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.ArrowCursor)
        btn.setFixedHeight(22)
        btn.setStyleSheet(
            "QPushButton { padding: 1px 8px; font-size: 11px; "
            "background: #2a4a5a; color: #ddd; border: 1px solid #3a6a7a; border-radius: 3px; }"
            "QPushButton:hover { background: #3a5a6a; }"
        )
        self.layout().addWidget(btn)
        self._action_btn = btn
        return btn

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

    def set_collapsed(self, collapsed: bool) -> None:
        """Programmatically set collapsed state, apply and persist."""
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        self._apply_state()
        self._persist()

    # ── Events ─────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Only toggle when clicking on the label area, not the action button
        child = self.childAt(event.position().toPoint())
        if child is self._action_btn:
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._collapsed = not self._collapsed
            self._apply_state()
            self._persist()
            self.toggled.emit(not self._collapsed)
        else:
            super().mousePressEvent(event)

    # ── Internals ──────────────────────────────────────────────────

    def _apply_state(self) -> None:
        """Apply collapsed/expanded state to target widget and update text."""
        self._target.setVisible(not self._collapsed)
        if self._container is not None:
            if self._collapsed:
                self._container.setMaximumHeight(_COLLAPSED_HEIGHT)
            else:
                self._container.setMaximumHeight(self._max_expanded_height)
        self._update_text()

    def _update_text(self) -> None:
        arrow = "▶" if self._collapsed else "▼"
        if self._count is not None:
            self._label.setText(f"{arrow} {self._title} ({self._count})")
        else:
            self._label.setText(f"{arrow} {self._title}")

    def _persist(self) -> None:
        settings = QSettings()
        settings.setValue(self._settings_key, self._collapsed)
