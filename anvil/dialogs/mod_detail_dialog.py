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
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QAbstractItemView,
    QHeaderView,
    QFileSystemModel,
    QComboBox,
    QMenu,
)
from PySide6.QtCore import Qt, QRect, QSize, QTimer, QDir
from PySide6.QtGui import QPainter, QColor, QFont, QFontDatabase, QIcon

from anvil.core.conflict_scanner import ConflictScanner
from anvil.core.mod_metadata import write_meta_ini
from anvil.widgets.flow_layout import FlowLayout

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

/* Verzeichnisbaum-Tab */
#filetreeView {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    alternate-background-color: #222222;
}
#filetreeView::item { padding: 2px 0; }
#filetreeView::item:selected { background: #3D3D3D; }
#filetreeView::item:hover:!selected { background: #2A2A2A; }
#filetreeView::branch:has-children:closed { image: none; }
#filetreeView::branch:has-children:open { image: none; }
#filetreeView QHeaderView::section {
    background: #242424;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    padding: 4px 8px;
}

/* Konflikte-Tab */
#conflictTree {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    alternate-background-color: #222222;
}
#conflictTree::item { padding: 2px 0; }
#conflictTree::item:selected { background: #3D3D3D; }
#conflictTree::item:hover:!selected { background: #2A2A2A; }
#conflictTree QHeaderView::section {
    background: #242424;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    padding: 4px 8px;
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


def _build_filetree_tab(mod_path: str):
    """Verzeichnisbaum-Tab wie MO2: QFileSystemModel + QTreeView.

    Shows the mod's directory structure with Name, Size, Type, Date columns.
    Based on MO2's modinfodialogfiletree.cpp implementation.
    """
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    # "Mod im Explorer öffnen" Button (wie MO2: openInExplorer)
    btn_row = QHBoxLayout()
    btn_explore = QPushButton("Mod im Explorer öffnen")
    btn_explore.clicked.connect(
        lambda: subprocess.Popen(["xdg-open", mod_path]) if os.path.isdir(mod_path) else None
    )
    btn_row.addWidget(btn_explore)
    btn_row.addStretch()
    layout.addLayout(btn_row)

    if not mod_path or not os.path.isdir(mod_path):
        layout.addWidget(QLabel("Mod-Verzeichnis nicht gefunden."))
        layout.addStretch()
        return page

    # QFileSystemModel (wie MO2: m_fs = new QFileSystemModel)
    fs_model = QFileSystemModel()
    fs_model.setRootPath(mod_path)
    fs_model.setReadOnly(True)  # MO2 uses false, we start read-only

    # QTreeView (wie MO2: ui->filetree)
    tree = QTreeView()
    tree.setObjectName("filetreeView")
    tree.setModel(fs_model)
    tree.setRootIndex(fs_model.index(mod_path))

    # Spalten-Breite (MO2: setColumnWidth(0, 300))
    tree.setColumnWidth(0, 300)  # Name

    # MO2-Einstellungen aus modinfodialog.ui
    tree.setSortingEnabled(True)
    tree.setAlternatingRowColors(True)
    tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    tree.setUniformRowHeights(True)
    tree.setAnimated(True)
    tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    # Header
    header = tree.header()
    header.setSortIndicatorShown(True)
    header.setStretchLastSection(True)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)

    # Keep model alive (prevent garbage collection)
    tree._fs_model = fs_model

    layout.addWidget(tree, 1)

    # TODO: Kontextmenü (Open, Rename, Delete, Hide/Unhide) wie MO2
    # TODO: Drag & Drop InternalMove
    # TODO: Header-State Persistenz

    return page


def _build_conflicts_tab(mod_name: str, all_mods, game_plugin):
    """Konflikte-Tab wie MO2: Gewinnt/Verliert-Bereiche mit ConflictScanner.

    Based on MO2's modinfodialogconflicts.cpp — two QTreeWidgets
    (Overwrite / Overwritten) with file path and competing mod name.
    """
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)

    # Fallback: keine Mod-Daten verfügbar
    if not all_mods or not mod_name:
        layout.addWidget(QLabel("Konflikterkennung nicht verfügbar."))
        layout.addStretch()
        return page

    # ConflictScanner ausführen
    scanner = ConflictScanner()
    result = scanner.scan_conflicts(all_mods, game_plugin)

    # Konflikte filtern die DIESE Mod betreffen
    wins = []   # Dateien die diese Mod gewinnt
    losses = []  # Dateien die diese Mod verliert
    for conflict in result["conflicts"]:
        if mod_name not in conflict["mods"]:
            continue
        if conflict["winner"] == mod_name:
            # Diese Mod gewinnt — zeige welche Mods überschrieben werden
            losers = [m for m in conflict["mods"] if m != mod_name]
            wins.append({"file": conflict["file"], "mods": losers})
        else:
            # Diese Mod verliert — zeige wer gewinnt
            losses.append({"file": conflict["file"], "winner": conflict["winner"]})

    # Keine Konflikte
    if not wins and not losses:
        no_conflict = QLabel("Keine Konflikte gefunden")
        no_conflict.setStyleSheet("color: #4CAF50; font-size: 14px; padding: 20px;")
        no_conflict.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(no_conflict)
        layout.addStretch()
        ignored_count = len(result["ignored"])
        if ignored_count > 0:
            info = QLabel(f"{ignored_count} harmlose Übereinstimmungen ignoriert")
            info.setStyleSheet("color: #808080; font-size: 11px;")
            info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(info)
        return page

    # --- Gewinnt Konflikte (oben) ---
    win_label = QLabel(f"Gewinnt Konflikte: ({len(wins)})")
    win_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px;")
    layout.addWidget(win_label)

    win_tree = QTreeWidget()
    win_tree.setObjectName("conflictTree")
    win_tree.setHeaderLabels(["Datei", "Überschreibt Mod"])
    win_tree.setColumnCount(2)
    win_tree.setAlternatingRowColors(True)
    win_tree.setRootIsDecorated(False)
    win_tree.setSortingEnabled(True)
    win_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    for entry in wins:
        item = QTreeWidgetItem([entry["file"], ", ".join(entry["mods"])])
        item.setForeground(0, QColor("#4CAF50"))
        win_tree.addTopLevelItem(item)
    header = win_tree.header()
    header.setStretchLastSection(True)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
    win_tree.setColumnWidth(0, 500)
    layout.addWidget(win_tree, 1)

    # --- Verliert Konflikte (unten) ---
    lose_label = QLabel(f"Verliert Konflikte: ({len(losses)})")
    lose_label.setStyleSheet("color: #F44336; font-weight: bold; font-size: 12px;")
    layout.addWidget(lose_label)

    lose_tree = QTreeWidget()
    lose_tree.setObjectName("conflictTree")
    lose_tree.setHeaderLabels(["Datei", "Überschrieben von Mod"])
    lose_tree.setColumnCount(2)
    lose_tree.setAlternatingRowColors(True)
    lose_tree.setRootIsDecorated(False)
    lose_tree.setSortingEnabled(True)
    lose_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    for entry in losses:
        item = QTreeWidgetItem([entry["file"], entry["winner"]])
        item.setForeground(0, QColor("#F44336"))
        lose_tree.addTopLevelItem(item)
    header = lose_tree.header()
    header.setStretchLastSection(True)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
    lose_tree.setColumnWidth(0, 500)
    layout.addWidget(lose_tree, 1)

    # --- Info-Zeile ---
    total = len(wins) + len(losses)
    ignored = len(result["ignored"])
    info_text = f"{total} Konflikte"
    if ignored > 0:
        info_text += f", {ignored} ignoriert"
    info = QLabel(info_text)
    info.setStyleSheet("color: #808080; font-size: 11px;")
    layout.addWidget(info)

    return page


# Chip-Stylesheet für Kategorien-Tab (wie FilterPanel)
_CATEGORY_CHIP_STYLE = """
QPushButton#catChip {
    background: #363636;
    color: #b0b0b0;
    border: 1px solid #505050;
    border-radius: 13px;
    padding: 4px 12px;
    font-size: 12px;
}
QPushButton#catChip:hover {
    background: #454545;
    color: #d0d0d0;
    border-color: #606060;
}
QPushButton#catChip:checked {
    background: #006868;
    color: #ffffff;
    border-color: #008888;
}
QPushButton#catChip:checked:hover {
    background: #008888;
}
/* Primary-Markierung */
QPushButton#catChipPrimary {
    background: #006868;
    color: #ffffff;
    border: 2px solid #00aaaa;
    border-radius: 13px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: bold;
}
QPushButton#catChipPrimary:hover {
    background: #008888;
}
"""

_CATEGORY_TAB_CONTEXT_MENU_STYLE = """
QMenu {
    background: #2b2b2b;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 4px 0;
}
QMenu::item {
    background: transparent;
    padding: 6px 20px;
    color: #e0e0e0;
}
QMenu::item:selected {
    background: #4de0d0;
    color: #1a1a1a;
}
"""


def _build_categories_tab(category_manager, mod_entry, mod_path):
    """Kategorien-Tab: Chips für alle Kategorien, Checked = Mod gehört dazu.

    Features:
    - Klick auf Chip = Toggle (zuweisen/entfernen)
    - Rechtsklick auf aktiven Chip = "Als Primär setzen"
    - ComboBox unten für Primär-Auswahl
    - Änderungen werden sofort in meta.ini gespeichert
    """
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    page.setStyleSheet(_CATEGORY_CHIP_STYLE)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(12)

    # Fallback wenn keine Daten
    if not category_manager:
        layout.addWidget(QLabel("Kategorien nicht verfügbar."))
        layout.addStretch()
        return page

    # Aktuell zugewiesene Kategorien (kopieren um Original nicht zu ändern)
    assigned_ids = list(mod_entry.category_ids) if mod_entry else []
    primary_id = mod_entry.primary_category if mod_entry else 0

    # Container-Widget für Chips
    chip_container = QWidget()
    chip_layout = FlowLayout(chip_container, margin=0, h_spacing=8, v_spacing=8)

    # Dict: cat_id -> chip widget
    chips: dict[int, QPushButton] = {}

    def update_primary_combo():
        """ComboBox aktualisieren mit nur aktiven Kategorien."""
        nonlocal primary_id
        primary_combo.blockSignals(True)
        primary_combo.clear()
        primary_combo.addItem("— Keine —", 0)
        for cat_id in assigned_ids:
            name = category_manager.get_name(cat_id)
            if name:
                primary_combo.addItem(name, cat_id)
        # Aktuelle Primär-Auswahl setzen
        idx = primary_combo.findData(primary_id)
        if idx >= 0:
            primary_combo.setCurrentIndex(idx)
        elif assigned_ids:
            # Primär nicht mehr zugewiesen - erste nehmen
            primary_id = assigned_ids[0]
            primary_combo.setCurrentIndex(1)
        else:
            primary_id = 0
            primary_combo.setCurrentIndex(0)
        primary_combo.blockSignals(False)

    def update_chip_styles():
        """Chip-Styles basierend auf Primary-Status aktualisieren."""
        for cat_id, chip in chips.items():
            if cat_id == primary_id and chip.isChecked():
                chip.setObjectName("catChipPrimary")
                chip.setText(f"★ {category_manager.get_name(cat_id)}")
            else:
                chip.setObjectName("catChip")
                chip.setText(category_manager.get_name(cat_id))
            # Force style refresh
            chip.style().unpolish(chip)
            chip.style().polish(chip)

    def save_to_meta_ini():
        """Speichert Kategorien in meta.ini."""
        if not mod_path:
            return
        from pathlib import Path
        # Primär zuerst, dann Rest
        cat_ids = []
        if primary_id and primary_id in assigned_ids:
            cat_ids.append(primary_id)
        for cid in assigned_ids:
            if cid != primary_id:
                cat_ids.append(cid)
        cat_str = ",".join(str(c) for c in cat_ids)
        write_meta_ini(Path(mod_path), {"category": cat_str})
        # ModEntry aktualisieren
        if mod_entry:
            mod_entry.category_ids = cat_ids
            mod_entry.primary_category = primary_id
            mod_entry.category = cat_str

    def on_chip_toggled(cat_id: int, checked: bool):
        """Chip wurde an/abgewählt."""
        nonlocal primary_id
        if checked:
            if cat_id not in assigned_ids:
                assigned_ids.append(cat_id)
                # Wenn erstes zugewiesenes, automatisch Primary
                if len(assigned_ids) == 1:
                    primary_id = cat_id
        else:
            if cat_id in assigned_ids:
                assigned_ids.remove(cat_id)
            # Wenn Primary entfernt, neues setzen
            if cat_id == primary_id:
                primary_id = assigned_ids[0] if assigned_ids else 0
        update_primary_combo()
        update_chip_styles()
        save_to_meta_ini()

    def on_chip_context_menu(chip: QPushButton, cat_id: int, pos):
        """Rechtsklick-Menü auf Chip."""
        nonlocal primary_id
        if not chip.isChecked():
            return  # Nur für aktive Chips
        menu = QMenu(chip)
        menu.setStyleSheet(_CATEGORY_TAB_CONTEXT_MENU_STYLE)
        act = menu.addAction("★ Als Primär setzen")
        act.setEnabled(cat_id != primary_id)
        action = menu.exec(chip.mapToGlobal(pos))
        if action == act:
            primary_id = cat_id
            update_primary_combo()
            update_chip_styles()
            save_to_meta_ini()

    def on_primary_changed(index: int):
        """ComboBox Primär-Auswahl geändert."""
        nonlocal primary_id
        new_primary = primary_combo.itemData(index)
        if new_primary != primary_id:
            primary_id = new_primary
            update_chip_styles()
            save_to_meta_ini()

    # Chips erstellen
    for cat in category_manager.all_categories():
        cat_id = cat["id"]
        name = cat["name"]
        chip = QPushButton(name)
        chip.setObjectName("catChip")
        chip.setCheckable(True)
        chip.setChecked(cat_id in assigned_ids)
        chip.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        chip.setFixedHeight(26)
        chip.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        chip.toggled.connect(lambda checked, cid=cat_id: on_chip_toggled(cid, checked))
        chip.customContextMenuRequested.connect(
            lambda pos, ch=chip, cid=cat_id: on_chip_context_menu(ch, cid, pos)
        )
        chip_layout.addWidget(chip)
        chips[cat_id] = chip

    # ScrollArea für viele Kategorien
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(chip_container)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet("QScrollArea { background: transparent; }")
    layout.addWidget(scroll, 1)

    # WICHTIG: Layout-Update NACH dem Hinzufügen zur ScrollArea
    chip_container.show()
    chip_layout.invalidate()
    chip_layout.activate()
    chip_container.updateGeometry()
    chip_container.adjustSize()
    scroll.updateGeometry()

    # Separator
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet("background: #3a3a3a;")
    layout.addWidget(sep)

    # Primär-ComboBox
    primary_row = QHBoxLayout()
    primary_label = QLabel("Primäre Kategorie:")
    primary_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
    primary_row.addWidget(primary_label)

    primary_combo = QComboBox()
    primary_combo.setMinimumWidth(200)
    primary_combo.setStyleSheet("""
        QComboBox {
            background: #2b2b2b;
            color: #e0e0e0;
            border: 1px solid #3a3a3a;
            border-radius: 4px;
            padding: 6px 12px;
        }
        QComboBox:hover { border-color: #006868; }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QComboBox QAbstractItemView {
            background: #2b2b2b;
            color: #e0e0e0;
            selection-background-color: #006868;
        }
    """)
    primary_combo.currentIndexChanged.connect(on_primary_changed)
    primary_row.addWidget(primary_combo)
    primary_row.addStretch()
    layout.addLayout(primary_row)

    # Initiale Werte setzen
    update_primary_combo()
    update_chip_styles()

    # Widgets auf page speichern für späteren Zugriff beim Tab-Wechsel
    page._chip_container = chip_container
    page._chip_layout = chip_layout
    page._scroll = scroll
    page._chips = chips

    return page


class ModDetailDialog(QDialog):
    def __init__(self, parent=None, mod_name="", mod_path="",
                 all_mods=None, game_plugin=None,
                 category_manager=None, mod_entry=None):
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

        pre_conflict_tabs = [
            ("INI Dateien", "Platzhalter – INI Dateien"),
            ("Bilder", "Platzhalter – Bilder"),
            ("Optionale ESPs", "Platzhalter – Optionale ESPs"),
        ]
        for tab_name, placeholder_text in pre_conflict_tabs:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.addWidget(QLabel(placeholder_text))
            self.tab_widget.addTab(page, tab_name)

        # Konflikte-Tab (wie MO2: ConflictsTab)
        self.tab_widget.addTab(
            _build_conflicts_tab(mod_name, all_mods, game_plugin), "Konflikte",
        )

        # Kategorien-Tab
        self._categories_page = _build_categories_tab(category_manager, mod_entry, mod_path)
        self.tab_widget.addTab(self._categories_page, "Kategorien")

        # Layout-Update wenn Kategorien-Tab sichtbar wird
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Nexus Info (noch Platzhalter)
        nexus_page = QWidget()
        nexus_layout = QVBoxLayout(nexus_page)
        nexus_layout.addWidget(QLabel("Platzhalter – Nexus Info"))
        self.tab_widget.addTab(nexus_page, "Nexus Info")

        # Verzeichnisbaum-Tab (wie MO2: FileTreeTab)
        self.tab_widget.addTab(_build_filetree_tab(mod_path), "Verzeichnisbaum")

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

    def _on_tab_changed(self, index: int):
        """Layout-Update wenn Kategorien-Tab sichtbar wird."""
        current_widget = self.tab_widget.widget(index)
        if current_widget is self._categories_page:
            # Tab ist jetzt sichtbar - Layout mit echter Breite aktualisieren
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._refresh_categories_layout)

    def _refresh_categories_layout(self):
        """Aktualisiert das FlowLayout der Kategorien-Chips."""
        page = self._categories_page
        if not hasattr(page, '_scroll'):
            return

        scroll = page._scroll
        chip_container = page._chip_container
        chip_layout = page._chip_layout
        chips = page._chips

        width = scroll.viewport().width()
        if width > 100:
            # Chips sichtbar machen für heightForWidth()
            for chip in chips.values():
                chip.show()
            container_width = width - 20
            chip_container.setMinimumWidth(container_width)
            # Höhe mit heightForWidth() berechnen und setzen
            height = chip_layout.heightForWidth(container_width)
            chip_container.setMinimumHeight(height)
            chip_layout.invalidate()
            chip_layout.activate()
            chip_container.updateGeometry()
            chip_container.repaint()
            scroll.updateGeometry()
