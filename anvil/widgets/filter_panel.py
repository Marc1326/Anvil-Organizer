"""FilterPanel: Seitenpanel mit Chip-basiertem Filtersystem.

Sections:
  - Eigenschaften (Aktiviert / Deaktiviert / Endorsed / Hat Notizen / ...)
  - Kategorien (dynamisch aus CategoryManager)

Signals:
  filter_changed() — emitted whenever any chip or the text field changes.
  panel_toggled(bool) — emitted when the toggle bar is clicked (True=open, False=close).
  category_delete_requested(int) — user chose "Loeschen" in context menu.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QScrollArea,
    QMenu,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPainter, QFontMetrics

from anvil.widgets.flow_layout import FlowLayout
from anvil.widgets.filter_chip import FilterChip
from anvil.core.categories import get_display_name
from anvil.core.translator import tr


# Property chip IDs (negative to avoid clash with category IDs)
PROP_ENABLED = -1
PROP_DISABLED = -2
PROP_ENDORSED = -3
PROP_HAS_NOTES = -4
PROP_HAS_CATEGORY = -5
PROP_NO_CATEGORY = -6
PROP_CONFLICT_WIN = -7
PROP_CONFLICT_LOSE = -8

def _get_property_chips():
    """Return property chips with translated labels."""
    return [
        (PROP_ENABLED, tr("filter.prop_enabled")),
        (PROP_DISABLED, tr("filter.prop_disabled")),
        (PROP_ENDORSED, tr("filter.prop_endorsed")),
        (PROP_HAS_NOTES, tr("filter.prop_has_notes")),
        (PROP_HAS_CATEGORY, tr("filter.prop_has_category")),
        (PROP_NO_CATEGORY, tr("filter.prop_no_category")),
        (PROP_CONFLICT_WIN, tr("filter.prop_conflict_win")),
        (PROP_CONFLICT_LOSE, tr("filter.prop_conflict_lose")),
    ]


class FilterPanel(QWidget):
    """Sidebar panel with chip-based filter controls.

    Layout: HBox [ _content_widget | FilterToggleBar ]

    Closed: content hidden, panel is ~20px wide (only toggle bar visible).
    Open: content + bar visible, width controlled by parent splitter.
    """

    filter_changed = Signal()
    panel_toggled = Signal(bool)  # True = open request, False = close request
    category_delete_requested = Signal(int)

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
        self._content_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(4)

        # ── Search field ──────────────────────────────────────────
        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("filter.search_placeholder"))
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_changed)
        content_layout.addWidget(self._search)

        # ── Scrollable chip area ──────────────────────────────────
        self._scroll_area = QScrollArea()
        self._scroll_area.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(self._scroll_area.Shape.NoFrame)
        self._inner = QWidget()
        # Leere Fläche unterhalb der Chips auch für Kontextmenü
        self._inner.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._inner.customContextMenuRequested.connect(self._on_inner_context_menu)
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(8)

        # ── Eigenschaften section ─────────────────────────────────
        lbl_props = QLabel(tr("filter.properties"))
        lbl_props.setObjectName("filterSectionLabel")
        lbl_props.setStyleSheet(
            "QLabel { font-weight: bold; padding: 2px 0; }"
        )
        self._inner_layout.addWidget(lbl_props)

        self._prop_flow = FlowLayout(h_spacing=4, v_spacing=4)
        prop_container = QWidget()
        prop_container.setLayout(self._prop_flow)
        # Verhindere Event-Bubbling von Property-Chips (kein Menü für Properties)
        prop_container.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        prop_container.customContextMenuRequested.connect(lambda pos: None)
        self._inner_layout.addWidget(prop_container)

        self._prop_chips: list[FilterChip] = []
        for chip_id, label in _get_property_chips():
            chip = FilterChip(label, chip_id=chip_id)
            chip.toggled.connect(self._on_changed)
            self._prop_flow.addWidget(chip)
            self._prop_chips.append(chip)

        # ── Kategorien section ────────────────────────────────────
        lbl_cats = QLabel(tr("filter.categories"))
        lbl_cats.setObjectName("filterSectionLabel")
        lbl_cats.setStyleSheet(
            "QLabel { font-weight: bold; padding: 2px 0; }"
        )
        self._inner_layout.addWidget(lbl_cats)

        self._cat_flow = FlowLayout(h_spacing=4, v_spacing=4)
        self._cat_container = QWidget()
        self._cat_container.setLayout(self._cat_flow)
        # CustomContextMenu für leere Fläche im Kategorien-Bereich
        self._cat_container.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._cat_container.customContextMenuRequested.connect(self._on_cat_area_context_menu)
        # Expandieren um den gesamten restlichen Platz zu füllen (für Kontextmenü)
        self._cat_container.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding
        )
        self._inner_layout.addWidget(self._cat_container, 1)  # stretch=1
        self._cat_chips: list[FilterChip] = []

        self._scroll_area.setWidget(self._inner)
        content_layout.addWidget(self._scroll_area, 1)

        # ── Bottom buttons ────────────────────────────────────────
        btn_row = QHBoxLayout()

        btn_reset = QPushButton(tr("filter.deselect"))
        btn_reset.setObjectName("filterResetBtn")
        btn_reset.clicked.connect(self.reset_all)
        btn_row.addWidget(btn_reset)

        btn_row.addStretch(1)
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
            try:
                chip.toggled.disconnect(self._on_changed)
            except (RuntimeError, TypeError):
                pass  # Signal war bereits getrennt
            chip.hide()  # SOFORT verstecken vor deleteLater
            self._cat_flow.removeWidget(chip)
            chip.setParent(None)
            chip.deleteLater()
        self._cat_chips.clear()

        for cat in categories:
            # Display translated name, keep internal name for reference
            display_name = get_display_name(cat["name"])
            chip = FilterChip(display_name, chip_id=cat["id"])
            chip._internal_name = cat["name"]  # Store for rename/reference
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

    # ── Context menu (für Kategorien-Bereich) ───────────────────────

    _ctx_in_progress = False

    def _on_cat_area_context_menu(self, pos):
        """Handle context menu for entire category area (chip or empty space)."""
        # Re-Entry Guard
        if FilterPanel._ctx_in_progress:
            return
        FilterPanel._ctx_in_progress = True

        try:
            from PySide6.QtWidgets import QApplication
            from anvil.widgets.filter_chip import FilterChip, CONTEXT_MENU_STYLE

            global_pos = self._cat_container.mapToGlobal(pos)
            widget = QApplication.widgetAt(global_pos)

            # Finde Chip unter Cursor (könnte auch child sein)
            chip = None
            w = widget
            while w is not None:
                if isinstance(w, FilterChip) and w.chip_id > 0:
                    chip = w
                    break
                if w is self._cat_container:
                    break
                w = w.parent()

            menu = QMenu(self)
            menu.setStyleSheet(CONTEXT_MENU_STYLE)

            if chip:
                # Chip-Menü (2 Einträge - Umbenennen kommt in Phase 3)
                act_add = menu.addAction(tr("context.add"))
                act_delete = menu.addAction(tr("context.delete"))
                chosen = menu.exec(global_pos)
                if chosen == act_add:
                    self._add_category()
                elif chosen == act_delete:
                    self._delete_category(chip)
            else:
                # Leere Fläche (1 Eintrag)
                menu.addAction(tr("context.add"), self._add_category)
                menu.exec(global_pos)
        finally:
            FilterPanel._ctx_in_progress = False

    def _on_inner_context_menu(self, pos):
        """Handle context menu for empty space below chips (in _inner widget)."""
        # Prüfe ob Klick unterhalb des Kategorien-Containers ist
        cat_container_bottom = self._cat_container.mapTo(self._inner,
            self._cat_container.rect().bottomLeft()).y()

        if pos.y() > cat_container_bottom:
            # Klick ist unterhalb der Chips - zeige "Hinzufügen" Menü
            from anvil.widgets.filter_chip import CONTEXT_MENU_STYLE
            global_pos = self._inner.mapToGlobal(pos)
            menu = QMenu(self)
            menu.setStyleSheet(CONTEXT_MENU_STYLE)
            menu.addAction(tr("context.add"), self._add_category)
            menu.exec(global_pos)

    def _add_category(self):
        """Platzhalter für Phase 3 (Dialog)."""
        pass

    def _delete_category(self, chip):
        """Emit delete signal for MainWindow to handle."""
        self.category_delete_requested.emit(chip.chip_id)

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

        label = f"\u25c0 {tr('label.filter')}" if self._open else f"{tr('label.filter')} \u25b6"

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
