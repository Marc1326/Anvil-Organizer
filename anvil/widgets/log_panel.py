"""Log Panel: Card-style log viewer with level filtering."""

from datetime import datetime
from typing import Literal

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QMenu,
    QApplication,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from anvil.core.translator import tr

LogLevel = Literal["debug", "info", "warning", "error"]

LEVEL_CONFIG = {
    "debug": {"icon": "\u2699", "color": "#666666", "bg": "transparent"},
    "info": {"icon": "\u2139", "color": "#00a8a8", "bg": "rgba(0,168,168,0.06)"},
    "warning": {"icon": "\u26a0", "color": "#e6a817", "bg": "rgba(230,168,23,0.06)"},
    "error": {"icon": "\u2715", "color": "#e05555", "bg": "rgba(224,85,85,0.08)"},
}

MAX_ENTRIES = 1000


class LogEntry(QFrame):
    """Single log entry widget."""

    def __init__(self, level: LogLevel, message: str, timestamp: str, parent=None):
        super().__init__(parent)
        self.level = level
        self.message = message
        self.timestamp = timestamp

        config = LEVEL_CONFIG[level]

        self.setStyleSheet(f"""
            QFrame {{
                background: {config["bg"]};
                border-left: 3px solid {config["color"]};
                border-radius: 4px;
                padding: 0;
                margin: 0;
            }}
            QFrame:hover {{
                background: #3D3D3D;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Icon
        icon_label = QLabel(config["icon"])
        icon_label.setFixedWidth(16)
        icon_label.setStyleSheet(f"color: {config['color']}; font-size: 12px; background: transparent;")
        layout.addWidget(icon_label)

        # Message
        msg_label = QLabel(message)
        msg_label.setWordWrap(False)
        text_color = config["color"] if level == "error" else "#D3D3D3"
        msg_label.setStyleSheet(f"""
            color: {text_color};
            font-size: 12px;
            font-family: monospace;
            background: transparent;
        """)
        layout.addWidget(msg_label, 1)

        # Timestamp
        time_label = QLabel(timestamp)
        time_label.setStyleSheet("""
            color: #555555;
            font-size: 10px;
            font-family: monospace;
            background: transparent;
        """)
        layout.addWidget(time_label)


class LevelBadge(QPushButton):
    """Clickable badge for filtering by log level."""

    def __init__(self, level: LogLevel, parent=None):
        super().__init__(parent)
        self.level = level
        self._count = 0
        self._active = False

        config = LEVEL_CONFIG[level]
        self._color = config["color"]
        self._icon = config["icon"]

        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(22)
        self._update_style()

    def set_count(self, count: int):
        self._count = count
        self._update_style()

    def _update_style(self):
        if self.isChecked():
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {self._color};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: 600;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.05);
                    color: {self._color};
                    border: none;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background: rgba(255,255,255,0.1);
                }}
            """)
        self.setText(f"{self._icon} {self._count}")


class LogPanel(QWidget):
    """Card-style log panel with level filtering."""

    log_added = Signal(str, str)  # level, message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[dict] = []
        self._active_filter: LogLevel | None = None

        self.setMinimumHeight(120)
        self.setMaximumHeight(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self._header = QWidget()
        self._header.setFixedHeight(32)
        self._header.setStyleSheet("""
            QWidget {
                background: #242424;
                border-bottom: 1px solid #333333;
            }
        """)

        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        header_layout.setSpacing(8)

        header_layout.addStretch()

        # Level badges
        self._badges: dict[LogLevel, LevelBadge] = {}
        for level in ["debug", "info", "warning", "error"]:
            badge = LevelBadge(level)
            badge.clicked.connect(lambda checked, lv=level: self._on_badge_clicked(lv))
            self._badges[level] = badge
            header_layout.addWidget(badge)

        layout.addWidget(self._header)

        # Scroll area for entries
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet("""
            QScrollArea {
                background: #1a1a1a;
                border: none;
            }
            QScrollBar:vertical {
                background: #1a1a1a;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3D3D3D;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #006868;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self._entries_widget = QWidget()
        self._entries_widget.setStyleSheet("background: #1a1a1a;")
        self._entries_layout = QVBoxLayout(self._entries_widget)
        self._entries_layout.setContentsMargins(8, 8, 8, 8)
        self._entries_layout.setSpacing(2)
        self._entries_layout.addStretch()

        self._scroll_area.setWidget(self._entries_widget)
        layout.addWidget(self._scroll_area)

        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def add_log(self, level: LogLevel, message: str):
        """Add a new log entry."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Store entry data
        entry_data = {"level": level, "message": message, "timestamp": timestamp}
        self._entries.append(entry_data)

        # Trim old entries
        while len(self._entries) > MAX_ENTRIES:
            self._entries.pop(0)
            # Remove first widget (after stretch is at end)
            item = self._entries_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        # Create widget if not filtered out
        if self._active_filter is None or self._active_filter == level:
            entry_widget = LogEntry(level, message, timestamp)
            # Insert before stretch
            self._entries_layout.insertWidget(self._entries_layout.count() - 1, entry_widget)

        # Update badge counts
        self._update_counts()

        # Scroll to bottom
        self._scroll_area.verticalScrollBar().setValue(
            self._scroll_area.verticalScrollBar().maximum()
        )

        self.log_added.emit(level, message)

    def _update_counts(self):
        """Update badge counts."""
        counts = {"debug": 0, "info": 0, "warning": 0, "error": 0}
        for entry in self._entries:
            counts[entry["level"]] += 1
        for level, badge in self._badges.items():
            badge.set_count(counts[level])

    def _on_badge_clicked(self, level: LogLevel):
        """Handle badge click for filtering."""
        badge = self._badges[level]

        # If already active, deactivate (show all)
        if self._active_filter == level:
            self._active_filter = None
            badge.setChecked(False)
        else:
            # Deactivate other badges
            for lv, b in self._badges.items():
                b.setChecked(lv == level)
            self._active_filter = level

        self._rebuild_entries()

    def _rebuild_entries(self):
        """Rebuild entry widgets based on current filter."""
        # Clear all entry widgets
        while self._entries_layout.count() > 1:  # Keep stretch
            item = self._entries_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        # Re-add filtered entries
        for entry in self._entries:
            if self._active_filter is None or entry["level"] == self._active_filter:
                entry_widget = LogEntry(entry["level"], entry["message"], entry["timestamp"])
                self._entries_layout.insertWidget(self._entries_layout.count() - 1, entry_widget)

    def clear(self):
        """Clear all log entries."""
        self._entries.clear()
        self._rebuild_entries()
        self._update_counts()

    def copy_all(self):
        """Copy all log entries to clipboard."""
        lines = []
        for entry in self._entries:
            lines.append(f"[{entry['timestamp']}] [{entry['level'].upper()}] {entry['message']}")
        QApplication.clipboard().setText("\n".join(lines))

    def _show_context_menu(self, pos):
        """Show context menu."""
        menu = QMenu(self)

        copy_action = menu.addAction(tr("context.copy"))
        copy_action.triggered.connect(self.copy_all)

        copy_all_action = menu.addAction(tr("context.copy_all"))
        copy_all_action.triggered.connect(self.copy_all)

        menu.addSeparator()

        clear_action = menu.addAction(tr("context.clear_all"))
        clear_action.triggered.connect(self.clear)

        menu.exec(self.mapToGlobal(pos))
