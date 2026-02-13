"""FilterPanel: Seitenpanel mit Chip-basiertem Filtersystem.

Sections:
  - Eigenschaften (Aktiviert / Deaktiviert / Endorsed / Hat Notizen / ...)
  - Kategorien (dynamisch aus CategoryManager)

Signals:
  filter_changed() — emitted whenever any chip or the text field changes.
  panel_toggled(bool) — emitted when the toggle bar is clicked (True=open, False=close).
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPainter, QFontMetrics, QMouseEvent

from anvil.widgets.flow_layout import FlowLayout
from anvil.widgets.filter_chip import FilterChip


# Property chip IDs (negative to avoid clash with category IDs)
PROP_ENABLED = -1
PROP_DISABLED = -2
PROP_ENDORSED = -3
PROP_HAS_NOTES = -4
PROP_HAS_CATEGORY = -5
PROP_NO_CATEGORY = -6
PROP_CONFLICT_WIN = -7
PROP_CONFLICT_LOSE = -8

_PROPERTY_CHIPS = [
    (PROP_ENABLED, "Aktiviert"),
    (PROP_DISABLED, "Deaktiviert"),
    (PROP_ENDORSED, "Endorsed"),
    (PROP_HAS_NOTES, "Hat Notizen"),
    (PROP_HAS_CATEGORY, "Hat Kategorie"),
    (PROP_NO_CATEGORY, "Ohne Kategorie"),
    (PROP_CONFLICT_WIN, "Konflikte (Gewinner)"),
    (PROP_CONFLICT_LOSE, "Konflikte (Verlierer)"),
]


class FilterPanel(QWidget):
    """Sidebar panel with chip-based filter controls.

    Layout: HBox [ _content_widget | FilterToggleBar ]

    Closed: content hidden, panel is ~20px wide (only toggle bar visible).
    Open: content + bar visible, width controlled by parent splitter.
    """

    filter_changed = Signal()
    panel_toggled = Signal(bool)  # True = open request, False = close request
    manage_categories_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("filterPanel")
        self._open = False
        self._splitter = None          # set via set_splitter()
        self._saved_sizes: list[int] | None = None

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Content area (everything except the toggle bar) ────────
        self._content_widget = QWidget()
        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(4)

        # ── Search field ──────────────────────────────────────────
        self._search = QLineEdit()
        self._search.setPlaceholderText("Mod suchen...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_changed)
        content_layout.addWidget(self._search)

        # ── Scrollable chip area ──────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        inner = QWidget()
        self._inner_layout = QVBoxLayout(inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(8)

        # ── Eigenschaften section ─────────────────────────────────
        lbl_props = QLabel("Eigenschaften")
        lbl_props.setObjectName("filterSectionLabel")
        lbl_props.setStyleSheet(
            "QLabel { font-weight: bold; padding: 2px 0; }"
        )
        self._inner_layout.addWidget(lbl_props)

        self._prop_flow = FlowLayout(h_spacing=4, v_spacing=4)
        prop_container = QWidget()
        prop_container.setLayout(self._prop_flow)
        self._inner_layout.addWidget(prop_container)

        self._prop_chips: list[FilterChip] = []
        for chip_id, label in _PROPERTY_CHIPS:
            chip = FilterChip(label, chip_id=chip_id)
            chip.toggled.connect(self._on_changed)
            self._prop_flow.addWidget(chip)
            self._prop_chips.append(chip)

        # ── Kategorien section ────────────────────────────────────
        lbl_cats = QLabel("Kategorien")
        lbl_cats.setObjectName("filterSectionLabel")
        lbl_cats.setStyleSheet(
            "QLabel { font-weight: bold; padding: 2px 0; }"
        )
        self._inner_layout.addWidget(lbl_cats)

        self._cat_flow = FlowLayout(h_spacing=4, v_spacing=4)
        cat_container = QWidget()
        cat_container.setLayout(self._cat_flow)
        self._inner_layout.addWidget(cat_container)
        self._cat_chips: list[FilterChip] = []

        # Spacer at bottom
        self._inner_layout.addStretch(1)

        scroll.setWidget(inner)
        content_layout.addWidget(scroll, 1)

        # ── Bottom buttons ────────────────────────────────────────
        btn_row = QHBoxLayout()

        btn_reset = QPushButton("Abwählen")
        btn_reset.setObjectName("filterResetBtn")
        btn_reset.clicked.connect(self.reset_all)
        btn_row.addWidget(btn_reset)

        btn_row.addStretch(1)

        btn_manage = QPushButton("Bearbeiten")
        btn_manage.setObjectName("filterManageBtn")
        btn_manage.clicked.connect(self.manage_categories_requested.emit)
        btn_row.addWidget(btn_manage)

        content_layout.addLayout(btn_row)

        outer.addWidget(self._content_widget, 1)

        # ── Toggle bar at right edge ──────────────────────────────
        self._toggle_bar = FilterToggleBar()
        self._toggle_bar.clicked.connect(self._on_bar_clicked)
        outer.addWidget(self._toggle_bar)

        # Start closed
        self._apply_state()

    # ── Public API ────────────────────────────────────────────────

    def is_open(self) -> bool:
        return self._open

    def set_open(self, open_: bool) -> None:
        if self._open == open_:
            return
        self._open = open_
        self._apply_state()

    def set_splitter(self, splitter) -> None:
        """Store reference to the parent QSplitter for size sync."""
        self._splitter = splitter

    def set_categories(self, categories: list[dict]) -> None:
        """Populate category chips from a list of ``{'id': int, 'name': str}``."""
        for chip in self._cat_chips:
            chip.toggled.disconnect(self._on_changed)
            self._cat_flow.removeWidget(chip)
            chip.deleteLater()
        self._cat_chips.clear()

        for cat in categories:
            chip = FilterChip(cat["name"], chip_id=cat["id"])
            chip.toggled.connect(self._on_changed)
            self._cat_flow.addWidget(chip)
            self._cat_chips.append(chip)

    def search_text(self) -> str:
        """Return current search text (lowered, stripped)."""
        return self._search.text().strip().lower()

    def active_property_ids(self) -> set[int]:
        """Return set of checked property chip IDs."""
        return {c.chip_id for c in self._prop_chips if c.isChecked()}

    def active_category_ids(self) -> set[int]:
        """Return set of checked category chip IDs."""
        return {c.chip_id for c in self._cat_chips if c.isChecked()}

    def has_active_filters(self) -> bool:
        """Return True if any filter is active."""
        if self._search.text().strip():
            return True
        if any(c.isChecked() for c in self._prop_chips):
            return True
        if any(c.isChecked() for c in self._cat_chips):
            return True
        return False

    def reset_all(self) -> None:
        """Uncheck all chips and clear the search field."""
        self._search.blockSignals(True)
        self._search.clear()
        self._search.blockSignals(False)
        for chip in self._prop_chips + self._cat_chips:
            chip.blockSignals(True)
            chip.setChecked(False)
            chip.blockSignals(False)
        self.filter_changed.emit()

    # ── Internal ──────────────────────────────────────────────────

    def _on_changed(self):
        self.filter_changed.emit()

    def _on_bar_clicked(self):
        new_state = not self._open
        self._open = new_state
        self._apply_state()
        self.panel_toggled.emit(new_state)

    def _apply_state(self):
        """Show/hide content, update toggle bar arrow, sync splitter sizes."""
        bar_w = FilterToggleBar._WIDTH
        self._content_widget.setVisible(self._open)
        self._toggle_bar.set_open(self._open)
        if self._open:
            self.setMinimumWidth(180)
            self.setMaximumWidth(16777215)  # QWIDGETSIZE_MAX
            if self._splitter and self._saved_sizes:
                self._splitter.setSizes(self._saved_sizes)
        else:
            if self._splitter:
                self._saved_sizes = self._splitter.sizes()
            # Constraints first, then splitter sizes
            self.setMinimumWidth(bar_w)
            self.setMaximumWidth(bar_w)
            if self._splitter:
                total = sum(self._splitter.sizes())
                self._splitter.setSizes([bar_w, total - bar_w])


class FilterToggleBar(QWidget):
    """Narrow vertical bar at the right edge of FilterPanel.

    Always visible. Displays rotated text with directional arrow:
      - Closed: 'Filter ▶'  (click to open)
      - Open:   '◀ Filter'  (click to close)

    Styled via QSS ``#filterToggleBar``.
    """

    clicked = Signal()

    _WIDTH = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("filterToggleBar")
        self.setFixedWidth(self._WIDTH)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open = False

    def set_open(self, open_: bool) -> None:
        self._open = open_
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event):
        from PySide6.QtWidgets import QStyleOption, QStyle
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        label = "\u25c0 Filter" if self._open else "Filter \u25b6"

        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)

        painter.setPen(self.palette().windowText().color())

        painter.save()
        painter.translate(self._WIDTH - 3, self.height() // 2 + QFontMetrics(font).horizontalAdvance(label) // 2)
        painter.rotate(-90)
        painter.drawText(0, 0, label)
        painter.restore()
