"""Mod-Detail-Dialog — öffnet bei Doppelklick auf Mod in der Mod-Liste."""

import os
import subprocess

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
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QTreeWidget,
    QTreeWidgetItem,
)
from PySide6.QtCore import Qt, QRect, QSize, QTimer
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

/* INI Dateien-Tab (identisch zu Textdateien) */
#iniFileList {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 4px;
    padding: 4px;
}
#iniFileList::item { padding: 6px 8px; }
#iniFileList::item:selected { background: #3D3D3D; }
#iniFileList::item:hover:!selected { background: #2A2A2A; }
#iniFileToolbar {
    background: #1C1C1C;
    border: none;
    border-bottom: 1px solid #3D3D3D;
    max-height: 35px;
}
#iniFileToolbar #toolbarIconBtn:hover { background: #3D3D3D; }
#iniFileToolbar #toolbarIconBtn:pressed { background: #006868; }

/* Optionale ESPs-Tab */
#optionalEspList, #availableEspList {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 4px;
    padding: 4px;
}
#optionalEspList::item, #availableEspList::item { padding: 6px 8px; }
#optionalEspList::item:selected, #availableEspList::item:selected { background: #3D3D3D; }
#optionalEspList::item:hover:!selected, #availableEspList::item:hover:!selected { background: #2A2A2A; }

/* Kategorien-Tab: Radio-Liste (Zebra, großer Indikator) + Dropdown */
#categoriesScrollArea {
    background: #1C1C1C;
    border: 1px solid #3D3D3D;
    border-radius: 4px;
}
#categoriesScrollArea QRadioButton {
    color: #D3D3D3;
    padding: 0 8px;
    spacing: 10px;
    min-height: 30px;
}
#categoriesScrollArea QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #E0E0E0;
    border-radius: 8px;
    background: #1C1C1C;
}
#categoriesScrollArea QRadioButton::indicator:checked {
    background: #006868;
    border-color: #E0E0E0;
}
#catRow0 { background: #1C1C1C; }
#catRow0:hover { background: #2A2A2A; }
#catRow0:checked { background: #3D3D3D; }
#catRow1 { background: #242424; }
#catRow1:hover { background: #2A2A2A; }
#catRow1:checked { background: #3D3D3D; }
#primaryCategoryCombo {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 4px;
    padding: 6px 10px;
}
#primaryCategoryCombo:hover { background: #2A2A2A; }
#primaryCategoryCombo::drop-down { border: none; }

/* Verzeichnisbaum-Tab */
#directoryTreeWidget {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 4px;
}
#directoryTreeWidget::item { padding: 4px 6px; }
#directoryTreeWidget::item:selected { background: #006868; color: #D3D3D3; }
#directoryTreeWidget::item:hover:!selected { background: #2A2A2A; }
#directoryTreeWidget QHeaderView::section {
    background: #242424;
    color: #D3D3D3;
    border: none;
    border-right: 1px solid #3D3D3D;
    border-bottom: 1px solid #3D3D3D;
    padding: 6px 8px;
}
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
    toolbar_layout.addWidget(btn_save)

    btn_ordner = QPushButton("Ordner")
    toolbar_layout.addWidget(btn_ordner)

    btn_wrap = QPushButton()
    btn_wrap.setObjectName("toolbarIconBtn")
    btn_wrap.setIcon(QIcon(_icon_path("zeilenumbruch (1).png")))
    btn_wrap.setToolTip("Zeilenumbruch ein/aus")
    btn_wrap.setCheckable(True)
    toolbar_layout.addWidget(btn_wrap)

    path_edit = QLineEdit()
    path_edit.setReadOnly(True)
    path_edit.setPlaceholderText("Keine Datei ausgewählt")
    path_edit.setStyleSheet("color: #808080; background: #1C1C1C; border: none;")
    toolbar_layout.addWidget(path_edit, 1)
    right_layout.addWidget(toolbar_widget)

    editor = CodeEditor()
    editor.setFont(_code_font())
    editor.setPlaceholderText("Datei auswählen …")
    editor.setPlainText("")
    editor.setReadOnly(False)
    editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    right_layout.addWidget(editor, 1)

    current_path = [None]

    def on_file_selected():
        item = file_list.currentItem()
        if not item:
            current_path[0] = None
            path_edit.clear()
            path_edit.setPlaceholderText("Keine Datei ausgewählt")
            editor.setPlainText("")
            return
        name = item.text()
        path = os.path.join(test_mod, name)
        current_path[0] = path
        path_edit.setText(path)
        try:
            with open(path, encoding="utf-8") as f:
                editor.setPlainText(f.read())
        except Exception as e:
            editor.setPlainText(f"Fehler beim Laden: {e}")

    def on_save():
        path = current_path[0]
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            path_edit.setText("Gespeichert!")
            path_edit.setStyleSheet("color: #4CAF50; background: #1C1C1C; border: none;")
            def restore():
                path_edit.setText(path)
                path_edit.setStyleSheet("color: #808080; background: #1C1C1C; border: none;")
            QTimer.singleShot(2000, restore)
        except Exception as e:
            path_edit.setText(f"Fehler: {e}")

    def on_wrap_toggled(checked):
        mode = QPlainTextEdit.LineWrapMode.WidgetWidth if checked else QPlainTextEdit.LineWrapMode.NoWrap
        editor.setLineWrapMode(mode)

    def on_ordner():
        path = current_path[0]
        if path:
            dirpath = os.path.dirname(path)
            try:
                subprocess.Popen(["xdg-open", dirpath])
            except Exception:
                pass

    btn_ordner.clicked.connect(on_ordner)
    btn_save.clicked.connect(on_save)
    btn_wrap.toggled.connect(on_wrap_toggled)
    file_list.currentItemChanged.connect(lambda *a: on_file_selected())
    on_file_selected()
    splitter.addWidget(right_pane)
    splitter.setSizes([260, 1040])
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    layout.addWidget(splitter, 1)

    return page


def _build_inifiles_tab():
    """Tab wie Textdateien: Splitter; links Label + Liste + Filter, rechts Toolbar + Editor. Filter: .ini"""
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # LINKS: Label "INI Dateien", QListWidget, Filter-Feld
    left_pane = QWidget()
    left_layout = QVBoxLayout(left_pane)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(6)
    left_layout.addWidget(QLabel("INI Dateien"))
    file_list = QListWidget()
    file_list.setObjectName("iniFileList")
    file_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    file_list.setMinimumWidth(120)

    test_mod = _test_mod_dir()
    if os.path.isdir(test_mod):
        for name in sorted(os.listdir(test_mod)):
            if name.endswith(".ini"):
                file_list.addItem(QListWidgetItem(name))
    if file_list.count() == 0:
        for name in ("settings.ini", "config.ini"):
            file_list.addItem(QListWidgetItem(name))
    if file_list.count() > 0:
        file_list.setCurrentRow(0)

    left_layout.addWidget(file_list)
    filter_edit = QLineEdit()
    filter_edit.setPlaceholderText("Filter")
    filter_edit.textChanged.connect(lambda t: _todo("INI-Filter")())
    left_layout.addWidget(filter_edit)
    splitter.addWidget(left_pane)

    # RECHTS: Toolbar-Zeile oben, darunter Editor mit Zeilennummern
    right_pane = QWidget()
    right_layout = QVBoxLayout(right_pane)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(0)

    toolbar_widget = QWidget()
    toolbar_widget.setObjectName("iniFileToolbar")
    toolbar_widget.setMaximumHeight(35)
    toolbar_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    toolbar_layout = QHBoxLayout(toolbar_widget)
    toolbar_layout.setContentsMargins(6, 4, 6, 4)
    toolbar_layout.setSpacing(8)

    btn_save = QPushButton()
    btn_save.setObjectName("toolbarIconBtn")
    btn_save.setIcon(QIcon(_icon_path("diskette (1).png")))
    btn_save.setToolTip("Speichern")
    toolbar_layout.addWidget(btn_save)

    btn_ordner = QPushButton("Ordner")
    toolbar_layout.addWidget(btn_ordner)

    btn_wrap = QPushButton()
    btn_wrap.setObjectName("toolbarIconBtn")
    btn_wrap.setIcon(QIcon(_icon_path("zeilenumbruch (1).png")))
    btn_wrap.setToolTip("Zeilenumbruch ein/aus")
    btn_wrap.setCheckable(True)
    toolbar_layout.addWidget(btn_wrap)

    path_edit = QLineEdit()
    path_edit.setReadOnly(True)
    path_edit.setPlaceholderText("Keine Datei ausgewählt")
    path_edit.setStyleSheet("color: #808080; background: #1C1C1C; border: none;")
    toolbar_layout.addWidget(path_edit, 1)
    right_layout.addWidget(toolbar_widget)

    editor = CodeEditor()
    editor.setFont(_code_font())
    editor.setPlaceholderText("Datei auswählen …")
    editor.setPlainText("")
    editor.setReadOnly(False)
    editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    right_layout.addWidget(editor, 1)

    current_path = [None]

    def on_file_selected():
        item = file_list.currentItem()
        if not item:
            current_path[0] = None
            path_edit.clear()
            path_edit.setPlaceholderText("Keine Datei ausgewählt")
            editor.setPlainText("")
            return
        name = item.text()
        path = os.path.join(test_mod, name)
        current_path[0] = path
        path_edit.setText(path)
        try:
            with open(path, encoding="utf-8") as f:
                editor.setPlainText(f.read())
        except Exception as e:
            editor.setPlainText(f"Fehler beim Laden: {e}")

    def on_save():
        path = current_path[0]
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            path_edit.setText("Gespeichert!")
            path_edit.setStyleSheet("color: #4CAF50; background: #1C1C1C; border: none;")
            def restore():
                path_edit.setText(path)
                path_edit.setStyleSheet("color: #808080; background: #1C1C1C; border: none;")
            QTimer.singleShot(2000, restore)
        except Exception as e:
            path_edit.setText(f"Fehler: {e}")

    def on_wrap_toggled(checked):
        mode = QPlainTextEdit.LineWrapMode.WidgetWidth if checked else QPlainTextEdit.LineWrapMode.NoWrap
        editor.setLineWrapMode(mode)

    def on_ordner():
        path = current_path[0]
        if path:
            dirpath = os.path.dirname(path)
            try:
                subprocess.Popen(["xdg-open", dirpath])
            except Exception:
                pass

    btn_ordner.clicked.connect(on_ordner)
    btn_save.clicked.connect(on_save)
    btn_wrap.toggled.connect(on_wrap_toggled)
    file_list.currentItemChanged.connect(lambda *a: on_file_selected())
    on_file_selected()
    splitter.addWidget(right_pane)
    splitter.setSizes([260, 1040])
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    layout.addWidget(splitter, 1)

    return page


def _build_optional_esps_tab():
    """Tab wie MO2: Links "Optionale ESPs", rechts "Verfügbare ESPs", Mitte Buttons +/- zum Verschieben."""
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QHBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)

    # LINKS: Label "Optionale ESPs" + QListWidget
    left_pane = QWidget()
    left_layout = QVBoxLayout(left_pane)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(6)
    left_layout.addWidget(QLabel("Optionale ESPs"))
    optional_list = QListWidget()
    optional_list.setObjectName("optionalEspList")
    optional_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    left_layout.addWidget(optional_list)
    layout.addWidget(left_pane, 1)

    # MITTE: Zwei Buttons vertikal zentriert
    button_container = QWidget()
    button_layout = QVBoxLayout(button_container)
    button_layout.setContentsMargins(0, 0, 0, 0)
    button_layout.setSpacing(8)
    button_layout.addStretch()

    btn_add = QPushButton("+")
    btn_add.setMinimumSize(40, 40)
    btn_add.setMaximumSize(40, 40)
    button_layout.addWidget(btn_add)

    btn_remove = QPushButton("-")
    btn_remove.setMinimumSize(40, 40)
    btn_remove.setMaximumSize(40, 40)
    button_layout.addWidget(btn_remove)

    button_layout.addStretch()
    layout.addWidget(button_container, 0)

    # RECHTS: Label "Verfügbare ESPs" + QListWidget
    right_pane = QWidget()
    right_layout = QVBoxLayout(right_pane)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(6)
    right_layout.addWidget(QLabel("Verfügbare ESPs"))
    available_list = QListWidget()
    available_list.setObjectName("availableEspList")
    available_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    # Dummy-Daten: rechte Liste mit ein paar Einträgen
    for name in ("plugin_a.esp", "plugin_b.esp", "plugin_c.esp", "optional_feature.esp", "extra_content.esp"):
        available_list.addItem(QListWidgetItem(name))
    right_layout.addWidget(available_list)
    layout.addWidget(right_pane, 1)

    # Funktionen für Verschieben
    def on_add():
        """Verschiebt ausgewähltes Item von rechts nach links."""
        item = available_list.currentItem()
        if not item:
            return
        text = item.text()
        # Neues Item in linke Liste
        new_item = QListWidgetItem(text)
        optional_list.addItem(new_item)
        optional_list.setCurrentItem(new_item)
        # Aus rechter Liste entfernen
        row = available_list.row(item)
        available_list.takeItem(row)

    def on_remove():
        """Verschiebt ausgewähltes Item von links nach rechts."""
        item = optional_list.currentItem()
        if not item:
            return
        text = item.text()
        # Neues Item in rechte Liste (sortiert einfügen)
        new_item = QListWidgetItem(text)
        available_list.addItem(new_item)
        available_list.sortItems()
        # Aus linker Liste entfernen
        row = optional_list.row(item)
        optional_list.takeItem(row)
        # In rechter Liste selektieren
        items = available_list.findItems(text, Qt.MatchFlag.MatchExactly)
        if items:
            available_list.setCurrentItem(items[0])

    btn_add.clicked.connect(on_add)
    btn_remove.clicked.connect(on_remove)

    return page


_CATEGORIES = [
    "None",
    "Cyberpunk 2077",
    "Miscellaneous",
    "Armour and Clothing",
    "Audio",
    "Characters",
    "Crafting",
    "Gameplay",
    "User Interface",
    "Utilities",
    "Visuals and Graphics",
    "Weapons",
    "Modders Resources",
    "Appearance",
    "Vehicles",
    "Animations",
    "Locations",
    "Scripts",
]


def _build_categories_tab():
    """Tab wie MO2: Echte Radio-Buttons pro Kategorie, unten Dropdown Primäre Kategorie."""
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)

    # Radio-Button-Liste: echte QRadioButtons in ScrollArea (wie Referenzbild)
    scroll = QScrollArea()
    scroll.setObjectName("categoriesScrollArea")
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.Shape.NoFrame)

    radio_container = QWidget()
    radio_layout = QVBoxLayout(radio_container)
    radio_layout.setContentsMargins(4, 4, 4, 4)
    radio_layout.setSpacing(0)

    button_group = QButtonGroup()
    radio_buttons = []
    for i, name in enumerate(_CATEGORIES):
        rb = QRadioButton(name)
        rb.setObjectName("catRow0" if i % 2 == 0 else "catRow1")
        rb.setMinimumHeight(30)
        radio_layout.addWidget(rb)
        button_group.addButton(rb)
        radio_buttons.append(rb)
    radio_buttons[0].setChecked(True)

    radio_layout.addStretch()
    scroll.setWidget(radio_container)
    layout.addWidget(scroll, 1)

    # Unten: Label links, Dropdown "Primäre Kategorie" füllt restliche Breite
    row = QHBoxLayout()
    row.addWidget(QLabel("Primäre Kategorie"))
    primary_combo = QComboBox()
    primary_combo.setObjectName("primaryCategoryCombo")
    primary_combo.addItems(_CATEGORIES)
    row.addWidget(primary_combo, 1)
    layout.addLayout(row)

    # Synchronisation: Radio <-> Dropdown (Signale blockieren, um Rekursion zu vermeiden)
    def on_radio_toggled():
        for i, rb in enumerate(radio_buttons):
            if rb.isChecked() and primary_combo.currentIndex() != i:
                primary_combo.blockSignals(True)
                primary_combo.setCurrentIndex(i)
                primary_combo.blockSignals(False)
                break

    def on_combo_changed(idx):
        if 0 <= idx < len(radio_buttons) and not radio_buttons[idx].isChecked():
            radio_buttons[idx].blockSignals(True)
            radio_buttons[idx].setChecked(True)
            radio_buttons[idx].blockSignals(False)

    for rb in radio_buttons:
        rb.toggled.connect(lambda checked, r=rb: on_radio_toggled() if checked else None)
    primary_combo.currentIndexChanged.connect(on_combo_changed)

    return page


def _build_directory_tree_tab():
    """Tab Verzeichnisbaum: Button 'Mod im Explorer öffnen', QTreeWidget mit Name/Größe/Typ/Änderungsdatum."""
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    btn_open = QPushButton("Mod im Explorer öffnen")
    btn_open.clicked.connect(_todo("Mod im Explorer öffnen"))
    layout.addWidget(btn_open)

    tree = QTreeWidget()
    tree.setObjectName("directoryTreeWidget")
    tree.setHeaderLabels(["Name", "Größe", "Typ", "Änderungsdatum"])
    tree.setSortingEnabled(True)
    tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    tree.setColumnCount(4)
    tree.setAlternatingRowColors(False)

    # Dummy: red4ext (aufgeklappt) → plugins (zugeklappt) → Codeware (zugeklappt); meta.ini unter red4ext
    red4ext = QTreeWidgetItem(tree, ["red4ext", "", "Ordner", "25.11.2025 13:10"])
    red4ext.setExpanded(True)
    plugins = QTreeWidgetItem(red4ext, ["plugins", "", "Ordner", "25.11.2025 13:10"])
    codeware = QTreeWidgetItem(plugins, ["Codeware", "", "Ordner", "25.11.2025 13:10"])
    meta_ini = QTreeWidgetItem(red4ext, ["meta.ini", "2.96 KiB", "Einfaches Text...", "05.02.2026"])

    layout.addWidget(tree, 1)
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
        self.tab_widget.addTab(_build_inifiles_tab(), "INI Dateien")

        tab_labels = [
            ("Bilder", "Platzhalter – Bilder"),
        ]
        for tab_name, placeholder_text in tab_labels:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.addWidget(QLabel(placeholder_text))
            self.tab_widget.addTab(page, tab_name)

        self.tab_widget.addTab(_build_optional_esps_tab(), "Optionale ESPs")

        tab_labels = [
            ("Konflikte", "Platzhalter – Konflikte"),
            ("Kategorien", None),
            ("Nexus Info", "Platzhalter – Nexus Info"),
            ("Verzeichnisbaum", "Platzhalter – Verzeichnisbaum"),
        ]
        for tab_name, placeholder_text in tab_labels:
            if tab_name == "Kategorien":
                self.tab_widget.addTab(_build_categories_tab(), tab_name)
            elif tab_name == "Verzeichnisbaum":
                self.tab_widget.addTab(_build_directory_tree_tab(), tab_name)
            else:
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
