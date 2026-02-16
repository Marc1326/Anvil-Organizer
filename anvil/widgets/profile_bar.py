"""Profil-Leiste: Segmented Tabs mit Horizontal Scroll, Action-Buttons, Aktiv-Badge."""

import os

from PySide6.QtGui import QIcon, QAction, QPainter, QLinearGradient, QColor
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QToolButton,
    QPushButton,
    QSizePolicy,
    QMenu,
    QScrollArea,
    QFrame,
    QButtonGroup,
    QLineEdit,
)
from PySide6.QtCore import QSize, Signal, Qt, QTimer

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "styles", "icons", "files")


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


BUTTON_STYLE = """
    QToolButton {
        background: #2a2a2a;
        border: 1px solid #3D3D3D;
        border-radius: 3px;
        color: #D3D3D3;
        font-size: 16px;
        font-weight: bold;
        padding: 2px 6px;
    }
    QToolButton:hover {
        background: #3D3D3D;
    }
    QToolButton::menu-indicator {
        subcontrol-position: right center;
        width: 12px;
    }
"""

TAB_STYLE_NORMAL = """
    QPushButton#profileTab {
        background: transparent;
        color: #888888;
        border: none;
        border-radius: 6px;
        padding: 6px 16px;
        font-size: 13px;
        font-weight: normal;
    }
    QPushButton#profileTab:hover {
        background: rgba(255, 255, 255, 0.05);
    }
"""

TAB_STYLE_SELECTED = """
    QPushButton#profileTab {
        background: #006868;
        color: #FFFFFF;
        border: none;
        border-radius: 6px;
        padding: 6px 16px;
        font-size: 13px;
        font-weight: 600;
    }
"""

ADD_BUTTON_STYLE = """
    #profileAddButton {
        background: #242424;
        color: #888888;
        border: 1px solid #3D3D3D;
        border-radius: 6px;
        font-size: 18px;
        font-weight: bold;
    }
    #profileAddButton:hover {
        background: #006868;
        border-color: #006868;
        color: #FFFFFF;
    }
"""


class FadeEdge(QWidget):
    """Gradient fade overlay for scroll indication."""

    def __init__(self, parent=None, direction: str = "left"):
        super().__init__(parent)
        self._direction = direction  # "left" or "right"
        self.setFixedWidth(32)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        gradient = QLinearGradient(0, 0, self.width(), 0)
        base_color = QColor("#141414")

        if self._direction == "left":
            gradient.setColorAt(0.0, base_color)
            gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        else:  # right
            gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
            gradient.setColorAt(1.0, base_color)

        painter.fillRect(self.rect(), gradient)


class ProfileBar(QWidget):
    # Existing signals
    collapse_all_requested = Signal()
    expand_all_requested = Signal()
    reload_requested = Signal()
    export_csv_requested = Signal()
    open_game_requested = Signal()
    open_mygames_requested = Signal()
    open_ini_requested = Signal()
    open_instance_requested = Signal()
    open_mods_requested = Signal()
    open_profile_requested = Signal()
    open_downloads_requested = Signal()
    open_ao_install_requested = Signal()
    open_ao_plugins_requested = Signal()
    open_ao_styles_requested = Signal()
    open_ao_logs_requested = Signal()
    backup_requested = Signal()
    restore_requested = Signal()

    # New signals for tabs
    profile_changed = Signal(str)
    profile_create_confirmed = Signal(str)  # Emits profile name
    profile_renamed = Signal(str, str)  # (old_name, new_name)
    profile_delete_requested = Signal(str)  # Profilname

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("profileBar")
        self.setFixedHeight(44)

        self._tabs: list[QPushButton] = []
        self._active_profile: str = ""
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._inline_input: QLineEdit | None = None
        self._inline_confirmed = False
        self._rename_input: QLineEdit | None = None
        self._rename_tab: QPushButton | None = None
        self._rename_confirmed = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # ── Tab Container ─────────────────────────────────────────────
        self._tab_container = QFrame()
        self._tab_container.setStyleSheet("""
            QFrame {
                background: #141414;
                border-radius: 8px;
            }
        """)
        self._tab_container.setFixedHeight(36)

        container_layout = QHBoxLayout(self._tab_container)
        container_layout.setContentsMargins(3, 3, 3, 3)
        container_layout.setSpacing(0)

        # Scroll area for tabs
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet("background: transparent;")
        self._scroll_area.viewport().setAutoFillBackground(False)

        # Inner widget for tabs
        self._tabs_widget = QWidget()
        self._tabs_widget.setStyleSheet("background: transparent;")
        self._tabs_layout = QHBoxLayout(self._tabs_widget)
        self._tabs_layout.setContentsMargins(0, 0, 0, 0)
        self._tabs_layout.setSpacing(4)
        self._tabs_layout.addStretch()

        self._scroll_area.setWidget(self._tabs_widget)
        container_layout.addWidget(self._scroll_area)

        # Fade edges
        self._fade_left = FadeEdge(self._tab_container, "left")
        self._fade_right = FadeEdge(self._tab_container, "right")
        self._fade_left.hide()
        self._fade_right.hide()

        layout.addWidget(self._tab_container, 1)

        # ── Add Profile Button ────────────────────────────────────────
        self._btn_add = QPushButton("+")
        self._btn_add.setObjectName("profileAddButton")
        self._btn_add.setFixedSize(30, 30)
        self._btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_add.setStyleSheet(ADD_BUTTON_STYLE)
        self._btn_add.setToolTip("Neues Profil erstellen")
        self._btn_add.clicked.connect(self._start_inline_create)
        layout.addWidget(self._btn_add)

        # ── Action Buttons ────────────────────────────────────────────
        def _set_icon(btn, filename):
            path = os.path.join(ICON_DIR, filename)
            if os.path.exists(path):
                btn.setIcon(QIcon(path))
                btn.setIconSize(QSize(20, 20))

        menu1 = QMenu(self)
        menu1.addAction(QAction("Installiere Mod...", self, triggered=_todo("Installiere Mod...")))
        menu1.addAction(QAction("Leere Mod erstellen", self, triggered=_todo("Leere Mod erstellen")))
        menu1.addAction(QAction("Erstelle Trenner", self, triggered=_todo("Erstelle Trenner")))
        menu1.addSeparator()
        menu1.addAction(QAction("Alle einklappen", self, triggered=lambda checked: self.collapse_all_requested.emit()))
        menu1.addAction(QAction("Alle ausklappen", self, triggered=lambda checked: self.expand_all_requested.emit()))
        menu1.addSeparator()
        menu1.addAction(QAction("Aktiviere alle", self, triggered=_todo("Aktiviere alle")))
        menu1.addAction(QAction("Deaktiviere alle", self, triggered=_todo("Deaktiviere alle")))
        menu1.addSeparator()
        act_updates = QAction("Auf Updates prüfen", self, triggered=_todo("Auf Updates prüfen"))
        act_updates.setEnabled(False)
        menu1.addAction(act_updates)
        act_auto_cat = QAction("Kategorien automatisch zuweisen", self, triggered=_todo("Kategorien automatisch zuweisen"))
        act_auto_cat.setEnabled(False)
        menu1.addAction(act_auto_cat)
        menu1.addAction(QAction("Neu laden", self, triggered=lambda checked: self.reload_requested.emit()))
        menu1.addSeparator()
        menu1.addAction(QAction("Als CSV exportieren...", self, triggered=lambda checked: self.export_csv_requested.emit()))
        menu1.addSeparator()
        menu1.addAction(QAction("Sicherung erstellen", self, triggered=lambda checked: self.backup_requested.emit()))
        menu1.addAction(QAction("Aus Sicherung wiederherstellen...", self, triggered=lambda checked: self.restore_requested.emit()))

        btn_menu = QToolButton(self)
        _set_icon(btn_menu, "dots.png")
        btn_menu.setToolTip("Menü")
        btn_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn_menu.setMenu(menu1)
        btn_menu.setFixedSize(48, 32)

        menu2 = QMenu(self)
        menu2.addAction(QAction("Spielverzeichnis öffnen", self, triggered=lambda checked: self.open_game_requested.emit()))
        menu2.addAction(QAction("MyGames Ordner öffnen", self, triggered=lambda checked: self.open_mygames_requested.emit()))
        menu2.addAction(QAction("INI Ordner öffnen", self, triggered=lambda checked: self.open_ini_requested.emit()))
        menu2.addAction(QAction("Instanz Ordner öffnen", self, triggered=lambda checked: self.open_instance_requested.emit()))
        menu2.addAction(QAction("Mods Ordner öffnen", self, triggered=lambda checked: self.open_mods_requested.emit()))
        menu2.addAction(QAction("Profil Ordner öffnen", self, triggered=lambda checked: self.open_profile_requested.emit()))
        menu2.addAction(QAction("Downloads Ordner öffnen", self, triggered=lambda checked: self.open_downloads_requested.emit()))
        menu2.addSeparator()
        menu2.addAction(QAction("AO Installationsordner öffnen", self, triggered=lambda checked: self.open_ao_install_requested.emit()))
        menu2.addAction(QAction("AO Plugins Ordner öffnen", self, triggered=lambda checked: self.open_ao_plugins_requested.emit()))
        menu2.addAction(QAction("AO Stylesheets Ordner öffnen", self, triggered=lambda checked: self.open_ao_styles_requested.emit()))
        menu2.addAction(QAction("AO Log Ordner öffnen", self, triggered=lambda checked: self.open_ao_logs_requested.emit()))

        btn_view = QToolButton(self)
        _set_icon(btn_view, "archives.png")
        btn_view.setToolTip("Ansicht")
        btn_view.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn_view.setMenu(menu2)
        btn_view.setFixedSize(48, 32)

        btn_restore = QToolButton(self)
        _set_icon(btn_restore, "restore.png")
        btn_restore.setToolTip("Aus Sicherung wiederherstellen")
        btn_restore.setFixedSize(36, 32)
        btn_restore.clicked.connect(lambda: self.restore_requested.emit())

        btn_backup = QToolButton(self)
        _set_icon(btn_backup, "backup.png")
        btn_backup.setToolTip("Sicherung erstellen")
        btn_backup.setFixedSize(36, 32)
        btn_backup.clicked.connect(lambda: self.backup_requested.emit())

        for btn in [btn_menu, btn_view, btn_restore, btn_backup]:
            btn.setStyleSheet(BUTTON_STYLE)
            layout.addWidget(btn)

        # ── Active Badge ──────────────────────────────────────────────
        layout.addWidget(QLabel("Aktiv:"))
        self._active = QLabel("<b>0</b>")
        self._active.setObjectName("activeCount")
        layout.addWidget(self._active)

        # Connect scroll for fade updates
        self._scroll_area.horizontalScrollBar().valueChanged.connect(self._update_fade_visibility)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_fade_edges()
        self._update_fade_visibility()

    def wheelEvent(self, event):
        """Handle mouse wheel for horizontal scrolling."""
        scrollbar = self._scroll_area.horizontalScrollBar()
        delta = event.angleDelta().y()
        scrollbar.setValue(scrollbar.value() - delta)
        event.accept()

    def _position_fade_edges(self):
        """Position fade edges at container edges."""
        h = self._tab_container.height() - 6
        self._fade_left.setFixedHeight(h)
        self._fade_right.setFixedHeight(h)
        self._fade_left.move(3, 3)
        self._fade_right.move(self._tab_container.width() - 35, 3)

    def _update_fade_visibility(self):
        """Show/hide fade edges based on scroll position."""
        scrollbar = self._scroll_area.horizontalScrollBar()
        at_start = scrollbar.value() <= scrollbar.minimum()
        at_end = scrollbar.value() >= scrollbar.maximum()

        self._fade_left.setVisible(not at_start and scrollbar.maximum() > 0)
        self._fade_right.setVisible(not at_end and scrollbar.maximum() > 0)

    def set_profiles(self, profiles: list[str], active: str = ""):
        """Set available profiles and optionally select one."""
        print(f"[DEBUG] SET_PROFILES: {profiles}, active={active}")
        # Clear existing tabs
        for tab in self._tabs:
            self._button_group.removeButton(tab)
            tab.deleteLater()
        self._tabs.clear()

        # Remove stretch
        while self._tabs_layout.count():
            item = self._tabs_layout.takeAt(0)
            if item.widget():
                pass  # Already deleted above

        # Create new tabs
        for profile in profiles:
            tab = QPushButton(profile)
            tab.setObjectName("profileTab")
            tab.setCheckable(True)
            tab.setCursor(Qt.CursorShape.PointingHandCursor)
            tab.setStyleSheet(TAB_STYLE_NORMAL)
            tab.clicked.connect(lambda checked, p=profile: self._on_tab_clicked(p))
            tab.mouseDoubleClickEvent = lambda event, t=tab: self._start_inline_rename(t)
            tab.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            tab.customContextMenuRequested.connect(
                lambda pos, t=tab: self._show_tab_context_menu(t, pos)
            )
            self._button_group.addButton(tab)
            self._tabs_layout.addWidget(tab)
            self._tabs.append(tab)

        self._tabs_layout.addStretch()

        # Select active profile AFTER layout is computed
        def _delayed_select():
            if active and active in profiles:
                self._select_profile(active, animate=False)
            elif profiles:
                self._select_profile(profiles[0], animate=False)
            self._update_fade_visibility()

        QTimer.singleShot(100, _delayed_select)

    def _on_tab_clicked(self, profile_name: str):
        """Handle tab click."""
        print(f"[DEBUG] TAB CLICKED: {profile_name}")
        if profile_name != self._active_profile:
            self._select_profile(profile_name, animate=True)
            self.profile_changed.emit(profile_name)

    def _show_tab_context_menu(self, tab: QPushButton, pos):
        """Show context menu for profile tab."""
        if len(self._tabs) <= 1:
            return  # Letztes Profil nicht löschbar
        menu = QMenu(self)
        delete_action = menu.addAction("Profil löschen")
        action = menu.exec(tab.mapToGlobal(pos))
        if action == delete_action:
            self.profile_delete_requested.emit(tab.text())

    def _select_profile(self, profile_name: str, animate: bool = True):
        """Select a profile tab."""
        self._active_profile = profile_name

        for tab in self._tabs:
            if tab.text() == profile_name:
                tab.setChecked(True)
                tab.setStyleSheet(TAB_STYLE_SELECTED)
                self._scroll_to_tab(tab)
            else:
                tab.setChecked(False)
                tab.setStyleSheet(TAB_STYLE_NORMAL)

    def _scroll_to_tab(self, tab: QPushButton):
        """Ensure tab is visible in scroll area."""
        self._scroll_area.ensureWidgetVisible(tab, 50, 0)

    def update_active_count(self, active: int, total: int | None = None) -> None:
        """Update the active mod counter badge."""
        if total is not None:
            self._active.setText(f"<b>{active} / {total}</b>")
        else:
            self._active.setText(f"<b>{active}</b>")

    def current_profile(self) -> str:
        """Return the currently selected profile name."""
        return self._active_profile

    def _start_inline_create(self):
        """Show inline input for new profile name."""
        if self._inline_input is not None:
            return  # Already open

        self._inline_confirmed = False

        edit = QLineEdit()
        edit.setObjectName("profileInlineInput")
        edit.setPlaceholderText("Profilname...")
        edit.setFixedWidth(140)
        edit.setStyleSheet("""
            QLineEdit#profileInlineInput {
                background: #141414;
                border: 1px solid #006868;
                border-radius: 6px;
                color: #D3D3D3;
                padding: 6px 12px;
                font-size: 13px;
            }
        """)

        # Insert before the stretch (last item)
        stretch_index = self._tabs_layout.count() - 1
        self._tabs_layout.insertWidget(stretch_index, edit)

        edit.setFocus()
        edit.returnPressed.connect(lambda: self._finish_inline_create(edit))
        edit.editingFinished.connect(lambda: self._cancel_inline_create(edit))

        self._inline_input = edit

    def _finish_inline_create(self, edit: QLineEdit):
        """Handle Enter press - create the profile."""
        name = edit.text().strip()
        if not name:
            self._cancel_inline_create(edit)
            return

        self._inline_confirmed = True

        # Remove input
        edit.setParent(None)
        edit.deleteLater()
        self._inline_input = None

        # Add new profile tab
        current_profiles = [tab.text() for tab in self._tabs]
        if name not in current_profiles:
            current_profiles.append(name)
            self.set_profiles(current_profiles, active=name)
            self.profile_create_confirmed.emit(name)

    def _cancel_inline_create(self, edit: QLineEdit):
        """Handle Escape or focus loss - cancel creation."""
        if self._inline_confirmed:
            return  # Already confirmed via Enter

        if self._inline_input is None:
            return  # Already cleaned up

        edit.setParent(None)
        edit.deleteLater()
        self._inline_input = None

    def _start_inline_rename(self, tab: QPushButton):
        """Show inline input for renaming a profile."""
        if self._rename_input is not None:
            return  # Already renaming

        self._rename_confirmed = False
        old_name = tab.text()

        # Hide the tab
        tab_index = self._tabs_layout.indexOf(tab)
        tab.hide()

        # Create input
        edit = QLineEdit()
        edit.setObjectName("profileInlineInput")
        edit.setText(old_name)
        edit.setFixedWidth(max(140, tab.width()))
        edit.setStyleSheet("""
            QLineEdit#profileInlineInput {
                background: #141414;
                border: 1px solid #006868;
                border-radius: 6px;
                color: #D3D3D3;
                padding: 6px 12px;
                font-size: 13px;
            }
        """)

        # Insert at the tab's position
        self._tabs_layout.insertWidget(tab_index, edit)

        edit.setFocus()
        edit.selectAll()
        edit.returnPressed.connect(lambda: self._finish_inline_rename(edit, tab, old_name))
        edit.editingFinished.connect(lambda: self._cancel_inline_rename(edit, tab))

        self._rename_input = edit
        self._rename_tab = tab

    def _finish_inline_rename(self, edit: QLineEdit, tab: QPushButton, old_name: str):
        """Handle Enter press - rename the profile."""
        new_name = edit.text().strip()

        # If empty or same name, cancel
        if not new_name or new_name == old_name:
            self._cancel_inline_rename(edit, tab)
            return

        # Check if name already exists
        existing = [t.text() for t in self._tabs if t != tab]
        if new_name in existing:
            self._cancel_inline_rename(edit, tab)
            return

        self._rename_confirmed = True

        # Remove input
        edit.setParent(None)
        edit.deleteLater()
        self._rename_input = None
        self._rename_tab = None

        # Update tab
        tab.setText(new_name)
        tab.show()

        # Update active profile if needed
        if self._active_profile == old_name:
            self._active_profile = new_name

        # Emit signal
        self.profile_renamed.emit(old_name, new_name)

    def _cancel_inline_rename(self, edit: QLineEdit, tab: QPushButton):
        """Handle Escape or focus loss - cancel rename."""
        if self._rename_confirmed:
            return  # Already confirmed via Enter

        if self._rename_input is None:
            return  # Already cleaned up

        edit.setParent(None)
        edit.deleteLater()
        tab.show()
        self._rename_input = None
        self._rename_tab = None
