"""Dark Theme aus Paper_Dark.qss — nur die 5 erlaubten Farben."""

COLORS = {
    "dunkel": "#141414",      # Listen, Panels, Buttons, Inputs, Header, Scrollbar-Track
    "alt_row": "#1C1C1C",     # Alternating Rows
    "mittel": "#242424",      # Hauptfenster, Toolbar, Menü, Borders
    "hell": "#3D3D3D",        # Hover, Statusbar
    "akzent": "#006868",      # Selektion, aktiver Tab, Starten-Button, Badge
    "text": "#D3D3D3",
    "text_selected": "#FFFFFF",
    "text_dim": "#808080",
    "row_error": "#3a1414",   # Fehler-Mod-Zeile
    "row_framework": "#143a14",  # Framework-Mod-Zeile
}


def get_stylesheet() -> str:
    d = COLORS
    return f"""
* {{
  background: {d["mittel"]};
  font-size: 13px;
  color: {d["text"]};
  border: 0;
}}
*:disabled {{
  color: {d["text_dim"]};
}}

QMainWindow, QWidget {{
  background: {d["mittel"]};
}}

QMenuBar {{
  background: {d["mittel"]};
  color: {d["text"]};
}}
QMenuBar::item:selected {{
  background: {d["akzent"]};
  color: {d["text_selected"]};
}}

QMenu {{
  background: transparent;
  border: 2px solid {d["mittel"]};
  border-radius: 6px;
}}
QMenu::item {{
  background: {d["dunkel"]};
  padding: 5px 24px;
}}
QMenu::item:selected {{
  background: {d["akzent"]};
  color: {d["text_selected"]};
  border-radius: 6px;
}}

QToolBar {{
  background: {d["mittel"]};
  border: none;
  border-bottom: 1px solid {d["dunkel"]};
  spacing: 2px;
  padding: 4px 8px;
}}
QToolBar::separator {{
  background: {d["hell"]};
  width: 1px;
  margin: 8px 4px;
}}
QToolBar QToolButton {{
  background: transparent;
  border: none;
  border-radius: 6px;
  padding: 6px;
  margin: 2px;
}}
QToolBar QToolButton:hover {{
  background: {d["hell"]};
}}
QToolBar QToolButton:pressed {{
  background: {d["akzent"]};
}}

QPushButton, QToolButton {{
  background: {d["dunkel"]};
  color: {d["text"]};
  min-height: 22px;
  padding: 2px 12px;
  border-radius: 6px;
}}
QPushButton:hover, QPushButton:pressed, QToolButton:hover, QToolButton:pressed {{
  background: {d["hell"]};
}}

QPushButton#startButton {{
  background: {d["akzent"]};
  color: {d["text_selected"]};
  padding: 8px 16px;
  font-weight: bold;
}}
QPushButton#startButton:hover {{
  background: {d["hell"]};
}}

QLineEdit {{
  background: {d["dunkel"]};
  min-height: 22px;
  padding-left: 5px;
  border: 2px solid {d["dunkel"]};
  border-radius: 6px;
  color: {d["text"]};
}}
QLineEdit:hover {{
  border: 2px solid {d["akzent"]};
}}

QComboBox {{
  background: {d["dunkel"]};
  min-height: 22px;
  padding-left: 5px;
  border: 2px solid {d["dunkel"]};
  border-radius: 6px;
  color: {d["text"]};
}}
QComboBox:hover {{
  border: 2px solid {d["akzent"]};
}}
QComboBox QAbstractItemView {{
  background: {d["dunkel"]};
  border: 2px solid {d["mittel"]};
  border-radius: 6px;
}}
QComboBox::drop-down {{
  width: 20px;
  border: none;
}}

QAbstractItemView {{
  background: {d["dunkel"]};
  alternate-background-color: {d["alt_row"]};
  border-radius: 6px;
  color: {d["text"]};
}}
QAbstractItemView::item {{
  min-height: 24px;
}}
QAbstractItemView::item:hover {{
  background: {d["hell"]};
}}
QAbstractItemView::item:selected {{
  background: {d["akzent"]};
  color: {d["text_selected"]};
}}

QTreeView {{
  border-radius: 6px;
}}

QHeaderView::section {{
  background: {d["dunkel"]};
  color: {d["text"]};
  padding: 0 5px;
  border: 0;
  border-bottom: 2px solid {d["mittel"]};
  border-right: 2px solid {d["mittel"]};
}}
QHeaderView::section:hover {{
  background: {d["hell"]};
}}

QScrollBar {{
  background: {d["dunkel"]};
  border: 2px solid {d["mittel"]};
}}
QScrollBar:vertical {{
  width: 20px;
}}
QScrollBar::handle:vertical {{
  background: {d["hell"]};
  border-radius: 6px;
  min-height: 32px;
  margin: 2px;
}}
QScrollBar::handle:hover, QScrollBar::handle:pressed {{
  background: {d["akzent"]};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
  height: 0;
}}

QTabWidget::pane {{
  border: 2px solid {d["mittel"]};
  border-radius: 6px;
  top: -1px;
  background: {d["dunkel"]};
}}
QTabBar::tab {{
  background: {d["dunkel"]};
  color: {d["text"]};
  padding: 8px 16px;
  border-radius: 10px;
  margin: 2px;
}}
QTabBar::tab:hover {{
  background: {d["hell"]};
}}
QTabBar::tab:selected {{
  background: {d["akzent"]};
  color: {d["text_selected"]};
}}

QTableView {{
  gridline-color: {d["mittel"]};
  border: 0;
}}

QStatusBar {{
  background: {d["hell"]};
  color: {d["text_dim"]};
}}

QLabel {{
  color: {d["text"]};
}}

#activeCount {{
  background: {d["akzent"]};
  color: {d["text_selected"]};
  padding: 2px 10px;
  border-radius: 6px;
}}

QCheckBox {{
  color: {d["text"]};
}}

QSplitter::handle {{
  background: {d["mittel"]};
  width: 6px;
}}

/* Profil-Leiste wie MO2: dunkler Streifen */
#profileBar {{
  background: {d["dunkel"]};
}}

/* Rechtes Panel: dunkler Hintergrund wie Mod-Liste */
#gamePanel {{
  background: {d["dunkel"]};
}}
"""
