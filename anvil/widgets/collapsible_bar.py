"""Collapsible section bar: QLabel that toggles tree visibility on click."""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


# Hoehe der Leiste. Zugeklappt ist der Bereich genau so hoch -- sonst
# springt die Leiste beim Klappen um ein paar Pixel. Der Standard bleibt
# der alte Wert; nur wer ausdruecklich mehr will, bekommt mehr.
_BAR_HEIGHT = 28
_MAX_HEIGHT = 16777215  # QWIDGETSIZE_MAX — no constraint

# Ab so vielen Pixeln gilt es als Ziehen und nicht mehr als Klick.
_DRAG_SCHWELLE = 4


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
    # Die Leiste wird bei gedrueckter Maustaste gezogen. Uebergeben wird
    # die Verschiebung in Bildpunkten seit dem Aufsetzen: negativ = nach
    # oben. Wer sie empfaengt, entscheidet was groesser wird.
    dragged = Signal(int)
    drag_finished = Signal()

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
        bar_height: int = _BAR_HEIGHT,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._settings_key = f"{settings_key}/collapsed"
        self._target = target
        self._container = container
        self._max_expanded_height = max_expanded_height
        self._bar_height = bar_height
        self._count: int | None = None
        self._status: str = ""
        self._press_y: int | None = None
        self._zieht = False

        # Layout: [label .................. action_button]
        hlayout = QHBoxLayout(self)
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.setSpacing(0)

        self._label = QLabel()
        # Modern: Optik aus Theme-QSS über objectName; klassisch: Inline-Style.
        # Ohne WA_StyledBackground malt Qt background/border aus dem QSS
        # auf eigenen QWidget-Subklassen nicht.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("sectionBar")
        self._label.setObjectName("sectionBarLabel")
        self._classic_style = style
        self.apply_theme_metrics()
        self._label.setCursor(Qt.CursorShape.PointingHandCursor)
        hlayout.addWidget(self._label, 1)

        self._action_btn: QPushButton | None = None

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(self._bar_height)

        # Restore persisted state (falls back to default_collapsed)
        settings = QSettings()
        self._collapsed = settings.value(self._settings_key, default_collapsed, type=bool)

        self._apply_state()

    # ── Public API ─────────────────────────────────────────────────

    def apply_theme_metrics(self) -> None:
        """Leisten-Optik an das aktive Theme anpassen (Live-Theme-Wechsel)."""
        from anvil.styles.dark_theme import theme_color
        if theme_color("panel2", ""):
            # Modernes Theme: Inline-Style entfernen, #sectionBar-QSS greift
            self._label.setStyleSheet("")
            self.setStyleSheet("")
        elif self._classic_style:
            self._label.setStyleSheet(self._classic_style)
            self.setStyleSheet(self._classic_style)

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

    def set_status(self, status: str) -> None:
        """Status-Text hinter dem Zähler (z.B. „alle installiert")."""
        self._status = status
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

    def expand(self) -> None:
        """Klappt den Bereich auf, falls er zu ist. Offen bleibt offen."""
        if not self._collapsed:
            return
        self._collapsed = False
        self._apply_state()
        self._persist()
        self.toggled.emit(True)

    # ── Events ─────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Only toggle when clicking on the label area, not the action button
        child = self.childAt(event.position().toPoint())
        if child is self._action_btn:
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            # Hier NICHT klappen: der Benutzer haelt die Leiste
            # moeglicherweise fest, um sie zu ziehen. Entschieden wird
            # beim Loslassen.
            self._press_y = int(event.globalPosition().y())
            self._zieht = False
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_y is None:
            super().mouseMoveEvent(event)
            return
        versatz = int(event.globalPosition().y()) - self._press_y
        if not self._zieht and abs(versatz) < _DRAG_SCHWELLE:
            event.accept()
            return
        self._zieht = True
        self.dragged.emit(versatz)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._press_y is None:
            super().mouseReleaseEvent(event)
            return
        gezogen = self._zieht
        self._press_y = None
        self._zieht = False
        if gezogen:
            self.drag_finished.emit()
        else:
            # Ein Klick ohne Bewegung -- also klappen.
            self._collapsed = not self._collapsed
            self._apply_state()
            self._persist()
            self.toggled.emit(not self._collapsed)
        event.accept()

    # ── Internals ──────────────────────────────────────────────────

    def _apply_state(self) -> None:
        """Apply collapsed/expanded state to target widget and update text."""
        self._target.setVisible(not self._collapsed)
        if self._container is not None:
            if self._collapsed:
                self._container.setMaximumHeight(self._bar_height)
            else:
                self._container.setMaximumHeight(self._max_expanded_height)
        self._update_text()

    def _update_text(self) -> None:
        arrow = "▶" if self._collapsed else "▼"
        text = f"{arrow} {self._title}"
        if self._count is not None:
            text += f" ({self._count})"
        if self._status:
            text += f" — {self._status}"
        self._label.setText(text)

    def _persist(self) -> None:
        settings = QSettings()
        settings.setValue(self._settings_key, self._collapsed)
