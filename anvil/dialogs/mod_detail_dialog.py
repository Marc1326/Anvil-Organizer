"""Mod-Detail-Dialog — öffnet bei Doppelklick auf Mod in der Mod-Liste."""

import os

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QFrame,
    QSizePolicy,
    QScrollArea,
    QLineEdit,
)
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QFontDatabase, QIcon

_MOD_DETAIL_DIALOG_STYLE = """
QDialog, QWidget { background: #1C1C1C; color: #D3D3D3; border: none; }
QTabWidget { padding: 0; margin: 0; }
QTabWidget::pane {
    background: #1C1C1C;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    margin-top: 0;
    padding: 0;
    border-top: none;
}
QTabBar::tab { background: #242424; color: #D3D3D3; padding: 8px 16px; margin-right: 2px; }
QTabBar::tab:selected { background: #006868; color: #D3D3D3; }
QTabBar::tab:hover:!selected { background: #3D3D3D; }
QPushButton {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 6px 12px;
}
QPushButton:hover { background: #3D3D3D; }
QPushButton:pressed { background: #006868; }
QLabel { color: #D3D3D3; }

/* Textdateien-Tab */
#textFileList {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 4px;
    padding: 4px;
}
#textFileList::item { padding: 6px 8px; }
#textFileList::item:selected { background: #3D3D3D; }
#textFileList::item:hover:!selected { background: #2A2A2A; }
#textFileEditor {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 4px;
    padding: 8px;
    font-family: "Fira Code", "Source Code Pro", monospace;
}
#lineNumberArea {
    background: #252525;
    color: #808080;
    border: none;
    border-right: 1px solid #3D3D3D;
    padding: 8px 4px;
}
#textFileToolbar {
    background: #1C1C1C;
    border: none;
    border-bottom: 1px solid #3D3D3D;
    max-height: 35px;
}
/* Toolbar-Icon-Buttons: Icons weiss auf transparent, nicht einfärben/invertieren */
#textFileToolbar #toolbarIconBtn:hover { background: #3D3D3D; }
#textFileToolbar #toolbarIconBtn:pressed { background: #006868; }
"""


def _todo(name):
    def _():
        print(f"TODO: {name}")
    return _


def _icon_path(name):
    """Pfad zu Icon in anvil/styles/icons/files/."""
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "..", "styles", "icons", "files", name)


def _test_mod_dir():
    """Pfad zu anvil/test_mod/ (Testdateien für Textdateien-Tab)."""
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "..", "test_mod")


def _code_font():
    """Fira Code oder Source Code Pro mit Fallback auf System-Monospace."""
    for name in ("Fira Code", "Source Code Pro"):
        if QFontDatabase.hasFamily(name):
            return QFont(name, 12)
    f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    if f.pointSize() <= 0:
        f.setPointSize(12)
    return f


class LineNumberArea(QWidget):
    """Schmaler Bereich links vom Editor, zeichnet Zeilennummern."""

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        self.setObjectName("lineNumberArea")

    def sizeHint(self):
        return QSize(self._editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self._editor.lineNumberAreaPaintEvent(event)


class CodeEditor(QPlainTextEdit):
    """QPlainTextEdit mit Zeilennummern (LineNumberArea links)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("textFileEditor")
        self._line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._on_update_request)
        self._update_line_number_area_width(0)

    def _update_line_number_area_width(self, _count):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)
        self._line_number_area.setFixedWidth(self.lineNumberAreaWidth())

    def _on_update_request(self, rect, dy):
        if dy != 0:
            self._line_number_area.scroll(0, dy)
        self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaWidth(self):
        digits = 1
        n = max(1, self.blockCount())
        while n >= 10:
            n //= 10
            digits += 1
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor("#252525"))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#808080"))
                painter.drawText(0, top, self._line_number_area.width() - 4, self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight, str(block_number + 1))
            block = block.next()
            block_number += 1
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
        painter.end()


def _build_textfiles_tab():
    """Tab wie MO2: Splitter; links Label + Liste + Filter, rechts Toolbar + Editor."""
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # LINKS: Label "Textdateien", QListWidget, Filter-Feld
    left_pane = QWidget()
    left_layout = QVBoxLayout(left_pane)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(6)
    left_layout.addWidget(QLabel("Textdateien"))
    file_list = QListWidget()
    file_list.setObjectName("textFileList")
    file_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    file_list.setMinimumWidth(120)

    test_mod = _test_mod_dir()
    if os.path.isdir(test_mod):
        for name in sorted(os.listdir(test_mod)):
            if name.endswith(".txt"):
                file_list.addItem(QListWidgetItem(name))
    if file_list.count() == 0:
        for name in ("readme.txt", "changelog.txt", "license.txt"):
            file_list.addItem(QListWidgetItem(name))
    if file_list.count() > 0:
        file_list.setCurrentRow(0)

    left_layout.addWidget(file_list)
    filter_edit = QLineEdit()
    filter_edit.setPlaceholderText("Filter")
    filter_edit.textChanged.connect(lambda t: _todo("Textdateien-Filter")())
    left_layout.addWidget(filter_edit)
    splitter.addWidget(left_pane)

    # RECHTS: Toolbar-Zeile oben, darunter Editor mit Zeilennummern
    right_pane = QWidget()
    right_layout = QVBoxLayout(right_pane)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(0)

    toolbar_widget = QWidget()
    toolbar_widget.setObjectName("textFileToolbar")
    toolbar_widget.setMaximumHeight(35)
    toolbar_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    toolbar_layout = QHBoxLayout(toolbar_widget)
    toolbar_layout.setContentsMargins(6, 4, 6, 4)
    toolbar_layout.setSpacing(8)

    btn_save = QPushButton()
    btn_save.setObjectName("toolbarIconBtn")
    btn_save.setIcon(QIcon(_icon_path("diskette (1).png")))
    btn_save.setToolTip("Speichern")
    btn_save.clicked.connect(_todo("Textdatei Speichern"))
    toolbar_layout.addWidget(btn_save)

    btn_listview = QPushButton()
    btn_listview.setObjectName("toolbarIconBtn")
    btn_listview.setIcon(QIcon(_icon_path("dots.png")))
    btn_listview.setToolTip("Listenansicht")
    btn_listview.clicked.connect(_todo("Listenansicht"))
    toolbar_layout.addWidget(btn_listview)

    btn_explorer = QPushButton("Explorer")
    btn_explorer.clicked.connect(_todo("Explorer öffnen"))
    toolbar_layout.addWidget(btn_explorer)

    path_label = QLabel("Keine Datei ausgewählt")
    path_label.setStyleSheet("color: #808080;")
    toolbar_layout.addWidget(path_label, 1)
    right_layout.addWidget(toolbar_widget)

    editor = CodeEditor()
    editor.setFont(_code_font())
    editor.setPlaceholderText("Datei auswählen …")
    editor.setPlainText("")
    editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    right_layout.addWidget(editor, 1)

    def on_file_selected():
        item = file_list.currentItem()
        if not item:
            path_label.setText("Keine Datei ausgewählt")
            editor.setPlainText("")
            return
        name = item.text()
        path = os.path.join(test_mod, name)
        path_label.setText(path)
        try:
            with open(path, encoding="utf-8") as f:
                editor.setPlainText(f.read())
        except Exception as e:
            editor.setPlainText(f"Fehler beim Laden: {e}")

    file_list.currentItemChanged.connect(lambda *a: on_file_selected())
    on_file_selected()
    splitter.addWidget(right_pane)
    splitter.setSizes([260, 1040])
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    layout.addWidget(splitter, 1)

    return page


class ModDetailDialog(QDialog):
    def __init__(self, parent=None, mod_name=""):
        super().__init__(parent)
        self.setWindowTitle(mod_name or "Mod-Details")
        self.setMinimumSize(1280, 720)
        self.resize(1300, 750)
        self.setStyleSheet(_MOD_DETAIL_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(12, 12, 12, 12)

        self.tab_widget = QTabWidget()

        self.tab_widget.addTab(_build_textfiles_tab(), "Textdateien")

        tab_labels = [
            ("INI Dateien", "Platzhalter – INI Dateien"),
            ("Bilder", "Platzhalter – Bilder"),
            ("Optionale ESPs", "Platzhalter – Optionale ESPs"),
            ("Konflikte", "Platzhalter – Konflikte"),
            ("Kategorien", "Platzhalter – Kategorien"),
            ("Nexus Info", "Platzhalter – Nexus Info"),
            ("Verzeichnisbaum", "Platzhalter – Verzeichnisbaum"),
        ]
        for tab_name, placeholder_text in tab_labels:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.addWidget(QLabel(placeholder_text))
            self.tab_widget.addTab(page, tab_name)

        tab_bar = self.tab_widget.tabBar()
        tab_bar.setExpanding(False)
        tab_bar.setParent(None)

        tab_bar_container = QHBoxLayout()
        tab_bar_container.addStretch(1)
        tab_bar_container.addWidget(tab_bar)
        tab_bar_container.addStretch(1)
        tab_bar_container.setContentsMargins(0, 0, 0, 0)
        tab_bar_container.setSpacing(0)

        layout.addLayout(tab_bar_container)
        layout.addWidget(self.tab_widget)
        layout.addSpacing(10)

        # Unten: Zurück/Weiter links, Schliessen rechts
        btn_row = QHBoxLayout()
        btn_back = QPushButton("Zurück")
        btn_back.clicked.connect(_todo("Mod-Navigation Zurück"))
        btn_next = QPushButton("Weiter")
        btn_next.clicked.connect(_todo("Mod-Navigation Weiter"))
        btn_row.addWidget(btn_back)
        btn_row.addWidget(btn_next)
        btn_row.addStretch()
        btn_close = QPushButton("Schliessen")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)
