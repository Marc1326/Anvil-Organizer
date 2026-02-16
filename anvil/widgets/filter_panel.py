"""FilterPanel: Seitenpanel mit Chip-basiertem Filtersystem.

Sections:
  - Eigenschaften (Aktiviert / Deaktiviert / Endorsed / Hat Notizen / ...)
  - Kategorien (dynamisch aus CategoryManager)

Signals:
  filter_changed() — emitted whenever any chip or the text field changes.
  panel_toggled(bool) — emitted when the toggle bar is clicked (True=open, False=close).
  category_add_requested(str) — user confirmed a new category name inline.
  category_rename_requested(int, str) — user confirmed a rename inline.
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
from PySide6.QtCore import Signal, Qt, QEvent
from PySide6.QtGui import QPainter, QFontMetrics

from anvil.widgets.flow_layout import FlowLayout
from anvil.widgets.filter_chip import FilterChip
from anvil.core.categories import get_display_name


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
    category_add_requested = Signal(str)
    category_rename_requested = Signal(int, str)
    category_delete_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("filterPanel")
        self._open = False
        self._splitter = None          # set via set_splitter()
        self._saved_sizes: list[int] | None = None
        self._inline_edit: QLineEdit | None = None  # active inline editor
        self._inline_chip: FilterChip | None = None  # chip being renamed

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
        self._search.setPlaceholderText("Mod suchen...")
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
        lbl_props = QLabel("Eigenschaften")
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

        # Eingabefeld für neue Kategorie (versteckt bis "Hinzufügen")
        self._cat_add_edit = QLineEdit()
        self._cat_add_edit.setObjectName("filterChip")
        self._cat_add_edit.setFixedHeight(26)
        self._cat_add_edit.setPlaceholderText("Kategorie-Name...")
        self._cat_add_edit.setVisible(False)
        self._cat_add_edit.returnPressed.connect(self._confirm_add)
        self._cat_add_edit.installEventFilter(self)
        self._inner_layout.addWidget(self._cat_add_edit)

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

        btn_reset = QPushButton("Abwählen")
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
            chip.toggled.disconnect(self._on_changed)
            self._cat_flow.removeWidget(chip)
            chip.deleteLater()
        self._cat_chips.clear()

        for cat in categories:
            # Display translated name, keep internal name for reference
            display_name = get_display_name(cat["name"])
            chip = FilterChip(display_name, chip_id=cat["id"])
            chip._internal_name = cat["name"]  # Store for rename/reference
            chip.toggled.connect(self._on_changed)
            chip.rename_started.connect(self._start_inline_rename)
            # Kontextmenü wird vom _cat_container gehandelt, nicht vom Chip
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
            print("[CTX-MENU] BLOCKED - bereits aktiv")
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
                # Chip-Menü (3 Einträge)
                act_add = menu.addAction("Hinzufügen")
                act_delete = menu.addAction("Löschen")
                act_nexus = menu.addAction("Nexus löschen")
                act_nexus.setEnabled(False)
                chosen = menu.exec(global_pos)
                if chosen == act_add:
                    self._add_category()
                elif chosen == act_delete:
                    self._delete_category(chip)
            else:
                # Leere Fläche (1 Eintrag)
                menu.addAction("Hinzufügen", self._add_category)
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
            menu.addAction("Hinzufügen", self._add_category)
            menu.exec(global_pos)

    def _add_category(self):
        self._start_inline_add()

    def _delete_category(self, chip):
        self.category_delete_requested.emit(chip.chip_id)

    # ── Inline editing ───────────────────────────────────────────

    def _start_inline_add(self) -> None:
        """Show the category add input field."""
        self._cat_add_edit.clear()
        self._cat_add_edit.setVisible(True)
        self._cat_add_edit.setFocus()

    def _confirm_add(self) -> None:
        """User pressed Enter in the add field."""
        name = self._cat_add_edit.text().strip()
        self._cat_add_edit.setVisible(False)
        if name:
            self.category_add_requested.emit(name)

    def _hide_add_edit(self) -> None:
        """Hide the category add input field."""
        self._cat_add_edit.setVisible(False)

    def _start_inline_rename(self, chip_id: int, current_name: str) -> None:
        """Replace a chip with a QLineEdit for renaming."""
        self._cancel_inline_edit()
        chip = self._find_chip(chip_id)
        if chip is None:
            return
        chip.setVisible(False)
        edit = QLineEdit(current_name)
        edit.setObjectName("filterChip")
        edit.setFixedHeight(26)
        edit.selectAll()
        edit.returnPressed.connect(self._confirm_inline_rename)
        # Escape und Focus-Lost handling
        edit.installEventFilter(self)
        # Insert edit at the chip's position in the layout (NOT list index!)
        idx = self._cat_flow.indexOf(chip)
        self._cat_flow.insertWidget(idx, edit)
        self._inline_edit = edit
        self._inline_chip = chip
        edit.setFocus()

    def _confirm_inline_rename(self) -> None:
        """User pressed Enter in the rename-inline editor."""
        if self._inline_edit is None or self._inline_chip is None:
            return
        new_name = self._inline_edit.text().strip()
        chip_id = self._inline_chip.chip_id
        old_name = self._inline_chip.text()
        self._inline_chip.setVisible(True)
        self._remove_inline_edit()
        if new_name and new_name != old_name:
            self.category_rename_requested.emit(chip_id, new_name)

    def _cancel_inline_edit(self) -> None:
        """Cancel any active inline edit and restore the chip."""
        if self._inline_edit is not None:
            print("[INLINE-INPUT] Escape/Cancel")
            if self._inline_chip is not None:
                self._inline_chip.setVisible(True)
            self._remove_inline_edit()

    def _remove_inline_edit(self) -> None:
        """Remove the inline QLineEdit widget."""
        if self._inline_edit is not None:
            self._cat_flow.removeWidget(self._inline_edit)
            self._inline_edit.deleteLater()
            self._inline_edit = None
            self._inline_chip = None

    def _find_chip(self, chip_id: int) -> FilterChip | None:
        for chip in self._cat_chips:
            if chip.chip_id == chip_id:
                return chip
        return None

    def eventFilter(self, obj, event) -> bool:
        """Handle Escape and Focus-Lost for inline edit fields."""
        # Kategorie-Hinzufügen Feld
        if obj is self._cat_add_edit:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape:
                    self._hide_add_edit()
                    return True
            elif event.type() == QEvent.Type.FocusOut:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._hide_add_edit)
                return False
        # Inline-Rename Feld (für Umbenennen)
        if obj is self._inline_edit:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape:
                    self._cancel_inline_edit()
                    return True
            elif event.type() == QEvent.Type.FocusOut:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._cancel_inline_edit)
                return False
        return super().eventFilter(obj, event)

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
