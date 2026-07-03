"""Instanz-Dropdown in der Menüleiste (nur modernes Design).

Zeigt die aktive Instanz (Cover-Chip, Name, Store · Profil) und öffnet
per Klick eine Liste aller Instanzen. Die Auswahl ruft ausschließlich
das bestehende switch_instance() im MainWindow auf — die Wechsel-Logik
bleibt unangetastet.
"""

import json
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QPoint, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from anvil.core.translator import tr
from anvil.styles.dark_theme import theme_color

# Platzhalterfarben aus dem Design-Handoff (Spiele ohne Icon)
_CHIP_COLORS = ["#3d4a52", "#4a4238", "#3a3f4a", "#443c4a", "#464040", "#3c4644"]


def _chip_label_text(game_name: str) -> str:
    """Kurzkürzel wie „BG3"/„SSE" aus dem Spielnamen ableiten."""
    words = [w for w in game_name.replace(":", " ").split() if w]
    label = "".join(w[0] for w in words if w[0].isalnum()).upper()
    return label[:4] or "?"


def _chip_pixmap(icon: QPixmap | None, game_name: str, w: int = 26,
                 h: int = 26, color: str | None = None) -> QPixmap:
    """Runder Cover-Chip: Bild/Spiel-Icon oder Farbfeld mit Kürzel."""
    pix = QPixmap(w, h)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, w, h, 6, 6)
    p.setClipPath(path)
    if icon is not None and not icon.isNull():
        scaled = icon.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (scaled.width() - w) // 2
        y = (scaled.height() - h) // 2
        p.drawPixmap(0, 0, scaled, x, y, w, h)
    else:
        if not color:
            color = _CHIP_COLORS[hash(game_name) % len(_CHIP_COLORS)]
        p.fillRect(0, 0, w, h, QColor(color))
        p.setPen(QColor(theme_color("txt", "#E8E8E8")))
        f = QFont()
        f.setPixelSize(9)
        f.setBold(True)
        p.setFont(f)
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, _chip_label_text(game_name))
    p.end()
    return pix


def instance_chip(inst: dict, instances_base: Path, icon_manager,
                  w: int = 26, h: int = 26) -> QPixmap:
    """Chip für eine Instanz: eigenes Cover → Spiel-Icon → Farbe+Kürzel."""
    icon = None
    cover_name = inst.get("cover_image", "")
    if cover_name:
        cover_path = instances_base / inst.get("name", "") / cover_name
        if cover_path.is_file():
            loaded = QPixmap(str(cover_path))
            if not loaded.isNull():
                icon = loaded
    if icon is None and icon_manager is not None:
        icon = icon_manager.get_game_icon(inst.get("game_short_name", ""))
    color = inst.get("cover_color", "") or None
    game = inst.get("game_name", inst.get("name", "?"))
    return _chip_pixmap(icon, game, w, h, color=color)


def _mod_counts(inst: dict, instances_base: Path) -> tuple[int, int]:
    """(aktiv, gesamt) für eine Instanz aus Dateisystem + active_mods.json."""
    inst_dir = instances_base / inst.get("name", "")

    def _expand(raw: str) -> Path:
        return Path(raw.replace("%INSTANCE_DIR%", str(inst_dir)))

    total = 0
    mods_raw = inst.get("path_mods_directory", "")
    if mods_raw:
        mods_dir = _expand(mods_raw)
        if mods_dir.is_dir():
            total = sum(
                1 for c in mods_dir.iterdir()
                if c.is_dir() and not c.name.endswith("_separator")
            )

    active = 0
    profiles_raw = inst.get("path_profiles_directory", "")
    profile = inst.get("selected_profile", "")
    if profiles_raw and profile:
        active_file = _expand(profiles_raw) / profile / "active_mods.json"
        if active_file.is_file():
            try:
                names = json.loads(active_file.read_text(encoding="utf-8"))
                active = sum(
                    1 for n in names
                    if isinstance(n, str) and not n.endswith("_separator")
                )
            except (OSError, ValueError):
                active = 0
    return active, total


class _InstanceRow(QFrame):
    """Eine Zeile im Popup: Chip, Name, Unterzeile, ●-Marker bei aktiv."""

    clicked = Signal(str)

    def __init__(self, inst: dict, chip: QPixmap, sub_text: str,
                 is_current: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("instanceRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._name = inst.get("name", "")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        chip_lbl = QLabel()
        chip_lbl.setPixmap(chip)
        chip_lbl.setFixedSize(32, 32)
        lay.addWidget(chip_lbl)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        name_lbl = QLabel(self._name)
        name_lbl.setObjectName("instRowName")
        col.addWidget(name_lbl)
        sub_lbl = QLabel(sub_text)
        sub_lbl.setObjectName("instRowSub")
        col.addWidget(sub_lbl)
        lay.addLayout(col)
        lay.addStretch()

        if is_current:
            dot = QLabel("●")
            dot.setObjectName("instRowDot")
            lay.addWidget(dot)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._name)
        super().mousePressEvent(event)


class _InstancePopup(QFrame):
    """Aufklappliste unter dem Dropdown-Knopf."""

    def __init__(self, dropdown: "InstanceDropdown"):
        super().__init__(dropdown, Qt.WindowType.Popup)
        self.setObjectName("instancePopup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._dropdown = dropdown

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(2)

        hint = QLabel(tr("instance.switch_hint"))
        hint.setObjectName("instPopupHint")
        lay.addWidget(hint)
        lay.addSpacing(4)

        im = dropdown._instance_manager
        base = im.instances_path()
        current = im.current_instance() or ""
        for inst in im.list_instances():
            active, total = _mod_counts(inst, base)
            store = (inst.get("detected_store", "") or "?").capitalize()
            if active > total:
                # z.B. BG3: Mods liegen nicht als Ordner in .mods —
                # Gesamtzahl wäre falsch, nur die aktiven anzeigen
                mods_txt = tr("instance.mods_active_simple", count=active)
            else:
                mods_txt = tr("instance.mods_active", active=active, total=total)
            sub = f"{mods_txt} · {store}"
            chip = instance_chip(inst, base, dropdown._icon_manager, w=32, h=32)
            row = _InstanceRow(inst, chip, sub,
                               inst.get("name", "") == current)
            row.clicked.connect(self._on_row_clicked)
            lay.addWidget(row)

        lay.addSpacing(4)
        new_btn = QPushButton("＋ " + tr("instance.new_instance"))
        new_btn.setObjectName("instNewBtn")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._on_new_clicked)
        lay.addWidget(new_btn)

        mgr_btn = QPushButton(tr("instance.open_manager"))
        mgr_btn.setObjectName("instManagerBtn")
        mgr_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mgr_btn.clicked.connect(self._on_manager_clicked)
        lay.addWidget(mgr_btn)

        self.setMinimumWidth(max(340, dropdown.width()))

    def _on_row_clicked(self, name: str) -> None:
        self.close()
        if name != (self._dropdown._instance_manager.current_instance() or ""):
            self._dropdown.instance_selected.emit(name)

    def _on_new_clicked(self, checked: bool = False) -> None:
        self.close()
        self._dropdown.new_instance_requested.emit()

    def _on_manager_clicked(self, checked: bool = False) -> None:
        self.close()
        self._dropdown.manager_requested.emit()


class TitleBarSpan(QWidget):
    """Titelzeilen-Aufsatz: legt sich rechts der Menütexte über die
    Menüleiste (freies Kind, kein Corner-Widget — das kämpft mit dem
    QMenuBar-Layout und bricht die Leiste zweizeilig um).

    Layout wie im Handoff: Instanz-Dropdown mittig im freien Bereich,
    Benachrichtigungen-Button rechts. Nur im modernen Theme sichtbar;
    klassisch bleibt die Glocke in der Toolbar.
    """

    def __init__(self, menubar, dropdown: QWidget, notif_btn: QWidget):
        super().__init__(menubar)
        self._menubar = menubar
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 2, 10, 2)
        lay.setSpacing(8)
        lay.addStretch(1)
        lay.addWidget(dropdown)
        lay.addStretch(1)
        lay.addWidget(notif_btn)
        menubar.installEventFilter(self)
        self.apply_theme_metrics()

    def apply_theme_metrics(self) -> None:
        """Modern: sichtbar, Toolbar-Glocke aus; klassisch umgekehrt."""
        modern = bool(theme_color("panel2", ""))
        self.setVisible(modern)
        win = self.window()
        toolbar = getattr(win, "_toolbar", None)
        action = getattr(toolbar, "notifications_action", None)
        if action is not None:
            action.setVisible(not modern)
        if modern:
            self._sync_geometry()

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self._menubar and event.type() in (
                QEvent.Type.Resize, QEvent.Type.Show):
            self._sync_geometry()
        return super().eventFilter(obj, event)

    def _sync_geometry(self) -> None:
        """Füllt den Bereich rechts der Menütexte über die volle Höhe."""
        mb = self._menubar
        right = 0
        for a in mb.actions():
            r = mb.actionGeometry(a).right()
            if r > right:
                right = r
        if right <= 0:
            # Menü-Actions noch nicht gelayoutet — gleich nochmal versuchen
            QTimer.singleShot(0, self._sync_geometry)
            return
        self.setGeometry(right + 4, 0,
                         max(0, mb.width() - right - 4), mb.height())
        self.raise_()


class InstanceDropdown(QWidget):
    """Dropdown-Knopf mit aktiver Instanz; Popup zum Wechseln."""

    instance_selected = Signal(str)
    new_instance_requested = Signal()
    manager_requested = Signal()

    def __init__(self, instance_manager, icon_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("instanceDropdown")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._instance_manager = instance_manager
        self._icon_manager = icon_manager

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 3, 10, 3)
        lay.setSpacing(8)

        self._chip = QLabel()
        self._chip.setFixedSize(32, 32)
        lay.addWidget(self._chip)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self._name_lbl = QLabel("")
        self._name_lbl.setObjectName("instDropName")
        col.addWidget(self._name_lbl)
        self._sub_lbl = QLabel("")
        self._sub_lbl.setObjectName("instDropSub")
        col.addWidget(self._sub_lbl)
        lay.addLayout(col, 1)

        arrow = QLabel("▾")
        arrow.setObjectName("instDropArrow")
        lay.addWidget(arrow)

        self.setMinimumWidth(290)
        self.setMinimumHeight(54)
        self.refresh_current()
        self.apply_theme_metrics()

    # ── Daten ─────────────────────────────────────────────────────────

    def refresh_current(self) -> None:
        """Anzeige aus der aktuell geladenen Instanz aktualisieren."""
        current = self._instance_manager.current_instance() or ""
        if not current:
            self._name_lbl.setText(tr("instance.none"))
            self._sub_lbl.setText("")
            self._chip.setPixmap(_chip_pixmap(None, "?", 32, 32))
            return
        inst = next(
            (i for i in self._instance_manager.list_instances()
             if i.get("name") == current),
            None,
        )
        if inst is None:
            self._name_lbl.setText(current)
            self._sub_lbl.setText("")
            self._chip.setPixmap(_chip_pixmap(None, current, 32, 32))
            return
        store = (inst.get("detected_store", "") or "?").capitalize()
        profile = inst.get("selected_profile", "") or "—"
        self._name_lbl.setText(current)
        self._sub_lbl.setText(f"{store} · {tr('instance.profile_prefix')} {profile}")
        self._chip.setPixmap(instance_chip(
            inst, self._instance_manager.instances_path(), self._icon_manager,
            w=32, h=32))

    # ── Theme ─────────────────────────────────────────────────────────

    def apply_theme_metrics(self) -> None:
        """Nur im modernen Theme sichtbar; Chip-Farben neu zeichnen."""
        modern = bool(theme_color("panel2", ""))
        self.setVisible(modern)
        if modern:
            self.refresh_current()

    # ── Popup ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.refresh_current()
            popup = _InstancePopup(self)
            popup.adjustSize()
            pos = self.mapToGlobal(QPoint(self.width() - popup.width(), self.height() + 4))
            popup.move(pos)
            popup.show()
        super().mousePressEvent(event)
