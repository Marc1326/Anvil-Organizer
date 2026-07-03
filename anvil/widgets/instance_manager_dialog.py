"""Instanz-Manager-Dialog (feste Größe, rahmenlos, Design-Handoff)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QListView, QLineEdit, QPushButton, QLabel, QWidget,
    QAbstractItemView, QFileDialog, QMessageBox,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem,
)
from PySide6.QtGui import (
    QStandardItemModel, QStandardItem, QIcon, QColor, QPixmap,
    QPainter, QPainterPath, QFont, QFontMetrics, QPen,
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex, QSize, QRect

from anvil.core.instance_manager import InstanceManager
from anvil.core.ui_helpers import get_text_input
from anvil.core.icon_manager import IconManager, placeholder_game_icon
from anvil.plugins.plugin_loader import PluginLoader
from anvil.core.translator import tr
from anvil.core.resource_path import get_anvil_base
from anvil.styles.dark_theme import theme_color
from anvil.widgets.instance_dropdown import (
    instance_chip, _CHIP_COLORS, _chip_label_text,
)

# Platzhalterfarben aus dem Design-Handoff (Icon & Bild)
_COVER_COLORS = ["#3d4a52", "#4a4238", "#443c4a", "#3c4644", "#37455a", "#52505e"]

_ICONS_DIR = get_anvil_base() / "styles" / "icons"


def _theme_qcolor(role: str, fallback: str) -> QColor:
    """Farb-Token als QColor — versteht #hex und rgba()/rgb()-Notation."""
    val = (theme_color(role, fallback) or fallback).strip()
    if val.startswith("rgb"):
        inner = val[val.index("(") + 1:val.index(")")]
        parts = [p.strip() for p in inner.split(",")]
        r, g, b = (int(float(parts[i])) for i in range(3))
        a = int(float(parts[3]) * 255) if len(parts) > 3 else 255
        return QColor(r, g, b, a)
    return QColor(val)


class _InstanceListDelegate(QStyledItemDelegate):
    """Zeichnet jede Instanz-Zeile selbst: weicher Auswahl-Balken, Farbchip
    mit Kürzel, Name und Aktiv-Marker. Kein QSS-Icon — auf Wayland zeichnen
    Delegate-Chips zuverlässiger als ``QStandardItem.setIcon()``.

    Rollen: UserRole+1 = Chip-Farbe (hex), UserRole+2 = Marker ("●"/""),
    UserRole+3 = Kürzel, DisplayRole = Name (ohne Marker).
    """

    def __init__(self, view):
        super().__init__(view)
        self._view = view

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index: QModelIndex) -> None:  # noqa: N802
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = option.rect

        # Auswahl-Highlight (weicher Akzent, 8px eingerückt wie Vorlage)
        if option.state & QStyle.StateFlag.State_Selected:
            hl = QPainterPath()
            hl.addRoundedRect(
                rect.x() + 8, rect.y() + 1,
                rect.width() - 16, rect.height() - 2, 7, 7)
            painter.fillPath(
                hl, _theme_qcolor("accent_soft", "rgba(51,179,168,0.16)"))

        # Chip 26×26: fertiges Pixmap (Cover/Spiel-Icon) — sonst Farbe+Kürzel
        chip = 26
        cx = rect.x() + 18
        cy = rect.y() + (rect.height() - chip) // 2
        pix = index.data(Qt.ItemDataRole.UserRole + 4)
        if isinstance(pix, QPixmap) and not pix.isNull():
            painter.drawPixmap(cx, cy, pix)
        else:
            color = index.data(Qt.ItemDataRole.UserRole + 1) or "#3d4a52"
            cp = QPainterPath()
            cp.addRoundedRect(cx, cy, chip, chip, 5, 5)
            painter.fillPath(cp, QColor(str(color)))

            initials = str(index.data(Qt.ItemDataRole.UserRole + 3) or "")
            cf = QFont()
            cf.setPixelSize(9)
            cf.setBold(True)
            painter.setFont(cf)
            painter.setPen(QColor(255, 255, 255, 217))
            painter.drawText(
                QRect(cx, cy, chip, chip),
                Qt.AlignmentFlag.AlignCenter, initials)

        # Aktiv-Marker "●" rechts (Akzent, 9px)
        mark = str(index.data(Qt.ItemDataRole.UserRole + 2) or "")
        mark_w = 0
        if mark:
            mf = QFont()
            mf.setPixelSize(9)
            painter.setFont(mf)
            painter.setPen(_theme_qcolor("accent", "#33b3a8"))
            painter.drawText(
                QRect(rect.x(), rect.y(), rect.width() - 18, rect.height()),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                mark)
            mark_w = QFontMetrics(mf).horizontalAdvance(mark) + 8

        # Name (12px, medium)
        name = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        nf = QFont()
        nf.setPixelSize(12)
        nf.setWeight(QFont.Weight.Medium)
        painter.setFont(nf)
        painter.setPen(_theme_qcolor("txt", "#e7e9ed"))
        nx = cx + chip + 10
        nright = rect.right() - 18 - mark_w
        painter.drawText(
            QRect(nx, rect.y(), max(0, nright - nx), rect.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem,
                 index: QModelIndex) -> QSize:  # noqa: N802
        width = self._view.viewport().width() if self._view else option.rect.width()
        return QSize(width, 42)


_DIALOG_STYLE = """
QDialog { background: #1C1C1C; }
QWidget { background: #1C1C1C; color: #D3D3D3; }
QLineEdit, QPushButton {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 4px;
}
QListView {
    background: #141414;
    alternate-background-color: #1C1C1C;
    border-radius: 6px;
    border: none;
    color: #D3D3D3;
}
QListView::item { padding: 4px; }
QListView::item:selected { background: #3D3D3D; color: #D3D3D3; }
QPushButton#deleteInstance { background: #5a2020; color: #D3D3D3; }
QPushButton#deleteInstance:hover { background: #7a2828; }
QPushButton#exploreBtn {
    background: transparent;
    border: none;
    padding: 2px;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    font-size: 18px;
    color: #E8B84B;
}
QPushButton#exploreBtn:hover { background: #3D3D3D; }
QSplitter::handle { background: #3D3D3D; }
QSplitter::handle:horizontal { width: 3px; }
QPushButton#createBtn {
    background: #006868;
    color: #FFF;
    font-weight: bold;
}
QPushButton#createBtn:hover { background: #008585; }
"""


class InstanceManagerDialog(QDialog):
    """Dialog zur Verwaltung von Game-Instanzen."""

    switched_to: str | None = None

    def __init__(
        self,
        parent=None,
        instance_manager: InstanceManager | None = None,
        plugin_loader: PluginLoader | None = None,
        icon_manager: IconManager | None = None,
        *,
        welcome: bool = False,
    ):
        super().__init__(parent)
        self._im = instance_manager
        self._pl = plugin_loader
        self._icons = icon_manager
        self._welcome = welcome
        self.switched_to = None

        self.setWindowTitle(tr("instance.manager_title"))
        self.setFixedSize(860, 560)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)

        self._modern = bool(theme_color("panel2", ""))
        if not self._modern:
            # Klassisch: alte Dialog-Optik; modern erbt das App-QSS
            self.setStyleSheet(_DIALOG_STYLE)

        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Titelleiste (44px) ───────────────────────────────────────
        title_bar = QWidget()
        title_bar.setObjectName("instTitleBar")
        title_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        title_bar.setFixedHeight(44)
        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(16, 0, 16, 0)
        tb.setSpacing(0)
        lbl = QLabel(tr("instance.manager_title"))
        lbl.setObjectName("instTitleLabel")
        tb.addWidget(lbl)
        tb.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("instCloseBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        tb.addWidget(close_btn)
        root.addWidget(title_bar)

        # ── Body (linke Spalte 300px · rechte Spalte flex) ──────────
        body = QWidget()
        body_l = QHBoxLayout(body)
        body_l.setSpacing(0)
        body_l.setContentsMargins(0, 0, 0, 0)

        # Linke Spalte
        left_panel = QWidget()
        left_panel.setObjectName("instLeftPanel")
        left_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left_panel.setFixedWidth(300)
        lp = QVBoxLayout(left_panel)
        lp.setSpacing(0)
        lp.setContentsMargins(0, 0, 0, 0)

        # Neue-Instanz-Button mit 12px Rand ringsum
        new_container = QWidget()
        nc = QVBoxLayout(new_container)
        nc.setContentsMargins(12, 12, 12, 12)
        nc.setSpacing(0)
        self._new_btn = QPushButton("＋ " + tr("instance.btn_new"))
        self._new_btn.setObjectName("createBtn")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.clicked.connect(self._on_new_instance)
        nc.addWidget(self._new_btn)
        lp.addWidget(new_container)

        # Instanzliste
        self._model = QStandardItemModel()
        self._proxy_model = QSortFilterProxyModel()
        self._proxy_model.setSourceModel(self._model)
        self._proxy_model.setFilterCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive)

        self._list_view = QListView()
        self._list_view.setObjectName("instanceList")
        self._list_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list_view.setItemDelegate(_InstanceListDelegate(self._list_view))
        self._list_view.setModel(self._proxy_model)
        self._list_view.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self._list_view.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self._list_view.selectionModel().currentChanged.connect(
            self._on_selection_changed)
        self._list_view.doubleClicked.connect(self._on_switch)
        lp.addWidget(self._list_view, 1)

        # Filterfeld unten (border-top)
        filter_container = QWidget()
        filter_container.setObjectName("instFilterBox")
        filter_container.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True)
        fc = QVBoxLayout(filter_container)
        fc.setContentsMargins(12, 10, 12, 10)
        fc.setSpacing(0)
        self._filter_edit = QLineEdit()
        self._filter_edit.setObjectName("instFilter")
        self._filter_edit.setPlaceholderText(tr("instance.filter_placeholder"))
        self._filter_edit.textChanged.connect(self._on_filter_changed)
        fc.addWidget(self._filter_edit)
        lp.addWidget(filter_container)

        body_l.addWidget(left_panel)

        # Rechte Spalte: Details
        right_panel = QWidget()
        right_panel.setObjectName("instRightPanel")
        rp = QVBoxLayout(right_panel)
        rp.setContentsMargins(24, 20, 24, 20)
        rp.setSpacing(14)

        self._details_label = QLabel(tr("instance.details_header"))
        self._details_label.setObjectName("detailsHeader")
        rp.addWidget(self._details_label)

        form = QGridLayout()
        form.setSpacing(10)
        form.setColumnMinimumWidth(0, 130)
        form.setColumnStretch(1, 1)

        # Zeile 0: Name + Umbenennen
        name_label = QLabel(tr("instance.label_name"))
        name_label.setObjectName("instFormLabel")
        form.addWidget(
            name_label, 0, 0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(8)
        self._name_edit = QLineEdit()
        self._name_edit.setReadOnly(True)
        name_row.addWidget(self._name_edit, 1)
        self._rename_btn = QPushButton(tr("instance.btn_rename"))
        self._rename_btn.setObjectName("instActionBtn")
        self._rename_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rename_btn.clicked.connect(self._on_rename)
        name_row.addWidget(self._rename_btn)
        form.addLayout(name_row, 0, 1)

        # Zeile 1: Speicherort
        loc_label = QLabel(tr("instance.label_location"))
        loc_label.setObjectName("instFormLabel")
        form.addWidget(
            loc_label, 1, 0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._location_edit = QLineEdit()
        self._location_edit.setReadOnly(True)
        form.addWidget(self._location_edit, 1, 1)

        # Zeile 2: Basisverzeichnis
        base_label = QLabel(tr("instance.label_base"))
        base_label.setObjectName("instFormLabel")
        form.addWidget(
            base_label, 2, 0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._base_edit = QLineEdit()
        self._base_edit.setReadOnly(True)
        form.addWidget(self._base_edit, 2, 1)

        # Zeile 3: Spielpfad
        game_label = QLabel(tr("instance.label_game_path"))
        game_label.setObjectName("instFormLabel")
        form.addWidget(
            game_label, 3, 0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._game_path_edit = QLineEdit()
        self._game_path_edit.setReadOnly(True)
        form.addWidget(self._game_path_edit, 3, 1)

        # Zeile 4: Icon & Bild (Cover pro Instanz — Bild oder Farbe)
        cover_label = QLabel(tr("instance.label_icon"))
        cover_label.setObjectName("instFormLabel")
        form.addWidget(
            cover_label, 4, 0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        cover_row = QHBoxLayout()
        cover_row.setContentsMargins(0, 0, 0, 0)
        cover_row.setSpacing(6)

        self._cover_preview = QLabel()
        self._cover_preview.setObjectName("instCoverPreview")
        self._cover_preview.setFixedSize(40, 54)
        cover_row.addWidget(self._cover_preview)

        # Zweizeilig wie in der Vorlage — sonst passt die Zeile nicht
        self._pick_image_btn = QPushButton(
            tr("instance.pick_image").replace(" ", "\n", 1))
        self._pick_image_btn.setObjectName("instActionBtn")
        self._pick_image_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pick_image_btn.clicked.connect(self._on_pick_image)
        cover_row.addWidget(self._pick_image_btn)

        swatches_row = QHBoxLayout()
        swatches_row.setContentsMargins(0, 0, 0, 0)
        swatches_row.setSpacing(6)
        self._swatch_btns = []
        self._swatch_colors = list(_COVER_COLORS)
        for color in self._swatch_colors:
            sw = QPushButton()
            sw.setObjectName("coverSwatch")
            sw.setCursor(Qt.CursorShape.PointingHandCursor)
            sw.setFixedSize(22, 22)
            sw.setIcon(QIcon(self._swatch_pixmap(color, False)))
            sw.setIconSize(QSize(22, 22))
            sw.setToolTip(color)
            sw.clicked.connect(
                lambda checked=False, c=color: self._on_pick_color(c))
            swatches_row.addWidget(sw)
            self._swatch_btns.append(sw)
        cover_row.addLayout(swatches_row)

        self._reset_cover_btn = QPushButton(tr("instance.reset_cover"))
        self._reset_cover_btn.setObjectName("instResetBtn")
        self._reset_cover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_cover_btn.clicked.connect(self._on_reset_cover)
        cover_row.addWidget(self._reset_cover_btn)
        cover_row.addStretch()
        form.addLayout(cover_row, 4, 1)

        rp.addLayout(form)

        # Löschen (nur Rahmen + Warnfarbe, links ausgerichtet)
        self._delete_btn = QPushButton("✕ " + tr("instance.btn_delete"))
        self._delete_btn.setObjectName("deleteInstance")
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.clicked.connect(self._on_delete)
        rp.addWidget(self._delete_btn, 0, Qt.AlignmentFlag.AlignLeft)

        rp.addStretch()

        # Hinweistext
        self._switch_note = QLabel(tr("instance.switch_note"))
        self._switch_note.setObjectName("switchNote")
        self._switch_note.setWordWrap(True)
        rp.addWidget(self._switch_note)

        body_l.addWidget(right_panel, 1)

        root.addWidget(body, 1)

        # ── Fußleiste (52px, Panel-BG, border-top) ──────────────────
        footer = QWidget()
        footer.setObjectName("instFooter")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        footer.setFixedHeight(52)
        ft = QHBoxLayout(footer)
        ft.setContentsMargins(16, 0, 16, 0)
        ft.setSpacing(8)
        ft.addStretch()

        self._switch_btn = QPushButton(tr("instance.btn_switch"))
        self._switch_btn.setObjectName("switchBtn")
        self._switch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._switch_btn.clicked.connect(self._on_switch)
        ft.addWidget(self._switch_btn)

        self._ok_btn = QPushButton(tr("button.ok"))
        self._ok_btn.setObjectName("okBtn")
        self._ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ok_btn.clicked.connect(self.accept)
        ft.addWidget(self._ok_btn)

        root.addWidget(footer)

    # ── List Management ───────────────────────────────────────────────

    def _refresh_list(self) -> None:
        """Reload instance list from disk."""
        self._model.clear()
        if self._im is None:
            return

        current = self._im.current_instance()

        for inst in self._im.list_instances():
            name = inst["name"]

            # DisplayRole = nur der Name (Marker zeichnet der Delegate)
            item = QStandardItem(name)
            item.setData(name, Qt.ItemDataRole.UserRole)

            # Chip-Farbe: eigenes Cover-Color → sonst Spielfarbe aus Namens-Hash
            game = inst.get("game_name", inst.get("name", "?"))
            color = inst.get("cover_color", "") or \
                _CHIP_COLORS[hash(game) % len(_CHIP_COLORS)]
            item.setData(color, Qt.ItemDataRole.UserRole + 1)
            item.setData(
                "●" if name == current else "", Qt.ItemDataRole.UserRole + 2)
            item.setData(_chip_label_text(game), Qt.ItemDataRole.UserRole + 3)
            # Fertiger Chip wie im Dropdown: Cover → Spiel-Icon → Farbe+Kürzel
            item.setData(
                instance_chip(inst, self._im.instances_path(),
                              self._icons, 26, 26),
                Qt.ItemDataRole.UserRole + 4)

            self._model.appendRow(item)

        # Select current instance
        if self._model.rowCount() > 0:
            for row in range(self._model.rowCount()):
                idx = self._model.index(row, 0)
                if idx.data(Qt.ItemDataRole.UserRole) == current:
                    proxy_idx = self._proxy_model.mapFromSource(idx)
                    self._list_view.setCurrentIndex(proxy_idx)
                    return
            self._list_view.setCurrentIndex(self._proxy_model.index(0, 0))

    def _selected_name(self) -> str | None:
        """Return selected instance name."""
        idx = self._list_view.currentIndex()
        if not idx.isValid():
            return None
        source_idx = self._proxy_model.mapToSource(idx)
        return source_idx.data(Qt.ItemDataRole.UserRole)

    def _is_active_selected(self) -> bool:
        """Check if the selected instance is the active one."""
        name = self._selected_name()
        if name is None or self._im is None:
            return False
        return name == self._im.current_instance()

    def _update_button_states(self) -> None:
        """Enable/disable buttons based on selection."""
        is_active = self._is_active_selected()
        has_selection = self._selected_name() is not None

        self._rename_btn.setEnabled(has_selection and not is_active)
        self._delete_btn.setEnabled(has_selection and not is_active)
        self._switch_btn.setEnabled(has_selection and not is_active)
        self._pick_image_btn.setEnabled(has_selection)
        self._reset_cover_btn.setEnabled(has_selection)
        for sw in self._swatch_btns:
            sw.setEnabled(has_selection)

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_filter_changed(self, text: str) -> None:
        """Filter the instance list."""
        self._proxy_model.setFilterFixedString(text)

    def _on_selection_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        """Update details panel when selection changes."""
        self._update_button_states()

        if not current.isValid() or self._im is None:
            self._clear_details()
            return

        source_idx = self._proxy_model.mapToSource(current)
        name = source_idx.data(Qt.ItemDataRole.UserRole)
        data = self._im.load_instance(name)
        if not data:
            self._clear_details()
            return

        self._name_edit.setText(name)
        self._name_edit.setReadOnly(self._is_active_selected())

        self._location_edit.setText(str(self._im.instances_path() / name))
        self._base_edit.setText(str(self._im.instances_path() / name))
        self._game_path_edit.setText(data.get("game_path", "") or "—")
        # Lange Pfade: Anfang zeigen statt Ende
        for edit in (self._location_edit, self._base_edit,
                     self._game_path_edit):
            edit.setCursorPosition(0)
        self._update_cover_preview(name)

    @staticmethod
    def _swatch_pixmap(color: str, selected: bool) -> QPixmap:
        """Farbfeld 22×22 (volle Farbfläche); gewählt = Akzent-Rahmen."""
        pix = QPixmap(22, 22)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0.5, 0.5, 21, 21, 5, 5)
        p.fillPath(path, QColor(color))
        if selected:
            p.setPen(QPen(_theme_qcolor("accent", "#33b3a8"), 2))
            p.drawRoundedRect(1, 1, 20, 20, 5, 5)
        p.end()
        return pix

    def _update_swatch_selection(self, cover_color: str) -> None:
        """Gewähltes Farbfeld mit Akzent-Rahmen markieren."""
        cur = (cover_color or "").lower()
        for sw, col in zip(self._swatch_btns, self._swatch_colors):
            sw.setIcon(QIcon(self._swatch_pixmap(col, col.lower() == cur)))

    def _update_cover_preview(self, name: str) -> None:
        """Cover-Vorschau (40×54) für die gewählte Instanz aktualisieren."""
        inst = next(
            (i for i in self._im.list_instances() if i.get("name") == name),
            None,
        ) if self._im else None
        if inst is None:
            self._cover_preview.clear()
            self._update_swatch_selection("")
            return
        self._cover_preview.setPixmap(instance_chip(
            inst, self._im.instances_path(), self._icons, w=40, h=54))
        self._update_swatch_selection(inst.get("cover_color", ""))

    def _clear_details(self) -> None:
        """Clear the details panel."""
        self._name_edit.clear()
        self._location_edit.clear()
        self._base_edit.clear()
        self._game_path_edit.clear()
        self._cover_preview.clear()
        self._update_swatch_selection("")

    def _on_new_instance(self) -> None:
        """Stub: Opens CreateInstanceWizard. Backend-Dev fills."""
        from anvil.widgets.instance_wizard import CreateInstanceWizard
        wizard = CreateInstanceWizard(self, self._im, self._pl, self._icons)
        if wizard.exec() == QDialog.DialogCode.Accepted and wizard.created_instance:
            self._refresh_list()
            self._select_instance(wizard.created_instance)
            self.switched_to = wizard.created_instance

    def _select_instance(self, name: str) -> None:
        """Select an instance by name in the list."""
        for row in range(self._model.rowCount()):
            idx = self._model.index(row, 0)
            if idx.data(Qt.ItemDataRole.UserRole) == name:
                proxy_idx = self._proxy_model.mapFromSource(idx)
                self._list_view.setCurrentIndex(proxy_idx)
                return

    def _on_rename(self) -> None:
        """Renames inactive instance."""
        name = self._selected_name()
        if name is None or self._im is None or self._is_active_selected():
            return

        new_name, ok = get_text_input(
            self,
            tr("instance.btn_rename"),
            tr("instance.label_name"),
            text=name,
        )

        if not ok or not new_name.strip() or new_name.strip() == name:
            return

        new_name = new_name.strip()

        # Check if name exists
        existing = {inst["name"] for inst in self._im.list_instances()}
        if new_name in existing:
            QMessageBox.warning(
                self,
                tr("instance.btn_rename"),
                tr("wizard.name_exists", name=new_name),
            )
            return

        if self._im.rename_instance(name, new_name):
            self._refresh_list()

    def _on_delete(self) -> None:
        """Opens delete confirmation dialog."""
        name = self._selected_name()
        if name is None or self._im is None or self._is_active_selected():
            return

        objects = self._im.get_objects_for_deletion(name)

        # Build message with file list
        lines = []
        total_size = 0
        for path, size in objects:
            total_size += size
            size_str = self._format_size(size)
            lines.append(f"  - {Path(path).name}  ({size_str})")

        msg = tr("instance.delete_confirm", name=name) + "\n\n"
        msg += "\n".join(lines)
        msg += f"\n\n{tr('instance.delete_total', size=self._format_size(total_size))}"

        reply = QMessageBox.warning(
            self,
            tr("instance.btn_delete"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self._im.delete_instance(name):
                self._refresh_list()

    def _format_size(self, size: int) -> str:
        """Format bytes as human-readable string."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"

    # ── Icon & Bild ───────────────────────────────────────────────────

    def _on_pick_image(self) -> None:
        """Bilddatei als Instanz-Cover wählen."""
        name = self._selected_name()
        if name is None or self._im is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, tr("instance.pick_image"), str(Path.home()),
            "Bilder (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not path:
            return
        if self._im.set_cover(name, image=path):
            self._after_cover_change(name)

    def _on_pick_color(self, color: str) -> None:
        """Platzhalterfarbe als Instanz-Cover setzen."""
        name = self._selected_name()
        if name is None or self._im is None:
            return
        if self._im.set_cover(name, color=color):
            self._after_cover_change(name)

    def _on_reset_cover(self) -> None:
        """Cover der Instanz zurücksetzen (Spiel-Icon/Kürzel)."""
        name = self._selected_name()
        if name is None or self._im is None:
            return
        if self._im.set_cover(name):
            self._after_cover_change(name)

    def _after_cover_change(self, name: str) -> None:
        """Vorschau + Liste nach Cover-Änderung aktualisieren."""
        self._update_cover_preview(name)
        self._refresh_list()
        self._select_instance(name)

    def _on_switch(self) -> None:
        """Stub: Switches to selected instance. Backend-Dev fills."""
        name = self._selected_name()
        if name is None or self._im is None:
            return
        self.switched_to = name
        self.accept()
