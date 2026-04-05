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
from PySide6.QtCore import Qt, QRect, QSize, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QFontDatabase, QIcon, QPixmap

from anvil.core.conflict_scanner import ConflictScanner
from anvil.core.mod_metadata import write_meta_ini
from anvil.core.translator import tr
from anvil.core import _todo
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

/* Bilder-Tab */
#imagesThumbnailList {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 4px;
    padding: 4px;
}
#imagesThumbnailList::item { padding: 4px; }
#imagesThumbnailList::item:selected { background: #3D3D3D; }
#imagesThumbnailList::item:hover:!selected { background: #2A2A2A; }
#imagesPreview {
    background: #1C1C1C;
    border: 1px solid #3D3D3D;
    border-radius: 4px;
}
#imagesInfoLabel { color: #808080; padding: 4px; }

/* Nexus-Info-Tab */
#nexusInfoGrid QLabel { color: #D3D3D3; padding: 2px 4px; }
#nexusInfoGrid #nexusValueLabel { color: #A0D0D0; }
#nexusInfoGrid #nexusLinkLabel { color: #00AAAA; }
#nexusInfoGrid #nexusLinkLabel:hover { color: #00CCCC; }
#nexusDescription {
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 4px;
    padding: 8px;
}
"""


def _icon_path(name):
    """Pfad zu Icon in anvil/styles/icons/files/."""
    from anvil.core.resource_path import get_anvil_base
    return str(get_anvil_base() / "styles" / "icons" / "files" / name)


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


def _build_nexus_tab(mod_path: str):
    """Tab für Nexus-Info — liest Daten aus meta.ini."""
    from anvil.core.mod_metadata import read_meta_ini
    from pathlib import Path

    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(12)

    meta = {}
    if mod_path and os.path.isdir(mod_path):
        meta = read_meta_ini(Path(mod_path))

    mod_id = meta.get("modid", "0")
    has_nexus = mod_id and mod_id != "0"

    if not has_nexus:
        no_info = QLabel(tr("mod_detail.no_nexus_info"))
        no_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(no_info)
        return page

    # --- Info-Grid ---
    grid_widget = QWidget()
    grid_widget.setObjectName("nexusInfoGrid")
    grid = QVBoxLayout(grid_widget)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(8)

    def _add_row(label_text: str, value_text: str, is_link: bool = False):
        row = QHBoxLayout()
        row.setSpacing(12)
        lbl = QLabel(label_text)
        lbl.setMinimumWidth(140)
        row.addWidget(lbl)
        val = QLabel(value_text)
        val.setObjectName("nexusLinkLabel" if is_link else "nexusValueLabel")
        val.setWordWrap(True)
        if is_link and value_text:
            val.setOpenExternalLinks(True)
            val.setTextFormat(Qt.TextFormat.RichText)
            val.setText(f'<a href="{value_text}" style="color: #00AAAA;">{value_text}</a>')
        row.addWidget(val, 1)
        grid.addLayout(row)

    _add_row(tr("mod_detail.nexus_mod_id"), mod_id)
    _add_row(tr("mod_detail.nexus_name"), meta.get("nexusName", meta.get("name", "")))
    _add_row(tr("mod_detail.nexus_author"), meta.get("nexusAuthor", meta.get("author", "")))
    _add_row(tr("mod_detail.nexus_version"), meta.get("version", ""))

    newest = meta.get("newestversion", meta.get("newestVersion", ""))
    if newest:
        _add_row(tr("mod_detail.nexus_newest_version"), newest)

    url = meta.get("nexusURL", meta.get("url", ""))
    if url:
        _add_row(tr("mod_detail.nexus_url"), url, is_link=True)

    game_name = meta.get("gamename", meta.get("gameName", ""))
    if game_name:
        _add_row(tr("mod_detail.nexus_game"), game_name)

    category = meta.get("nexuscategory", meta.get("nexusCategory", ""))
    if category and category != "0":
        _add_row(tr("mod_detail.nexus_category"), category)

    last_query = meta.get("lastnexusquery", meta.get("lastNexusQuery", ""))
    if last_query:
        _add_row(tr("mod_detail.nexus_last_query"), last_query[:19].replace("T", " "))

    layout.addWidget(grid_widget)

    # --- Beschreibung ---
    description = meta.get("nexusSummary", meta.get("description", ""))
    nexus_desc = meta.get("nexusdescription", meta.get("nexusDescription", ""))

    if description or nexus_desc:
        desc_label = QLabel(tr("mod_detail.nexus_description"))
        layout.addWidget(desc_label)

        desc_text = QPlainTextEdit()
        desc_text.setObjectName("nexusDescription")
        desc_text.setReadOnly(True)
        # Prefer summary (clean text) over full nexus description (HTML)
        desc_text.setPlainText(description if description else nexus_desc)
        layout.addWidget(desc_text)
    else:
        layout.addStretch(1)

    return page


_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
_THUMB_SIZE = 64


def _collect_images(mod_path: str):
    """Sammelt rekursiv alle Bilddateien, ignoriert archive/."""
    images = []
    if not mod_path or not os.path.isdir(mod_path):
        return images
    for root, dirs, files in os.walk(mod_path):
        # archive/ ausschließen
        dirs[:] = [d for d in dirs if d.lower() != "archive"]
        for f in sorted(files):
            if f.lower().endswith(_IMAGE_EXTENSIONS):
                images.append(os.path.join(root, f))
    return images


def _format_file_size(size_bytes: int) -> str:
    """Dateigröße lesbar formatieren."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _build_images_tab(mod_path: str):
    """Bilder-Tab: Splitter; links Thumbnail-Liste + Filter, rechts Preview + Info."""
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    image_files = _collect_images(mod_path)

    # Fallback: keine Bilder
    if not image_files:
        no_img = QLabel(tr("mod_detail.no_images"))
        no_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(no_img)
        return page

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # --- LINKS: Filter + Thumbnail-Liste ---
    left_pane = QWidget()
    left_layout = QVBoxLayout(left_pane)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(6)

    filter_edit = QLineEdit()
    filter_edit.setPlaceholderText(tr("placeholder.filter"))
    left_layout.addWidget(filter_edit)

    thumb_list = QListWidget()
    thumb_list.setObjectName("imagesThumbnailList")
    thumb_list.setIconSize(QSize(_THUMB_SIZE, _THUMB_SIZE))
    thumb_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    thumb_list.setMinimumWidth(140)

    for img_path in image_files:
        pix = QPixmap(img_path)
        if pix.isNull():
            continue
        thumb = pix.scaled(
            _THUMB_SIZE, _THUMB_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        item = QListWidgetItem(QIcon(thumb), os.path.basename(img_path))
        item.setData(Qt.ItemDataRole.UserRole, img_path)
        thumb_list.addItem(item)

    left_layout.addWidget(thumb_list)
    splitter.addWidget(left_pane)

    # --- RECHTS: Preview + Info + Explorer-Button ---
    right_pane = QWidget()
    right_layout = QVBoxLayout(right_pane)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(6)

    preview_label = QLabel()
    preview_label.setObjectName("imagesPreview")
    preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    preview_label.setMinimumSize(200, 200)
    right_layout.addWidget(preview_label)

    # Info-Zeile
    info_label = QLabel()
    info_label.setObjectName("imagesInfoLabel")
    right_layout.addWidget(info_label)

    # Explorer-Button
    btn_explorer = QPushButton(tr("mod_detail.open_in_explorer"))
    btn_explorer.setEnabled(False)
    right_layout.addWidget(btn_explorer)

    splitter.addWidget(right_pane)
    splitter.setSizes([180, 600])
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)

    layout.addWidget(splitter)

    # --- Signale ---
    _current_path = [None]

    def _show_preview(item):
        img_path = item.data(Qt.ItemDataRole.UserRole)
        _current_path[0] = img_path
        pix = QPixmap(img_path)
        if pix.isNull():
            preview_label.clear()
            info_label.setText("")
            btn_explorer.setEnabled(False)
            return
        # Preview skalieren auf verfügbare Größe
        avail = preview_label.size()
        scaled = pix.scaled(
            avail,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        preview_label.setPixmap(scaled)
        # Info-Zeile
        file_size = _format_file_size(os.path.getsize(img_path))
        info_label.setText(
            f"{os.path.basename(img_path)} — {pix.width()}\u00d7{pix.height()} — {file_size}"
        )
        btn_explorer.setEnabled(True)

    thumb_list.currentItemChanged.connect(
        lambda current, _prev: _show_preview(current) if current else None
    )

    def _open_explorer(checked=False):
        path = _current_path[0]
        if path:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])

    btn_explorer.clicked.connect(_open_explorer)

    # Filter
    def _filter_thumbs(text):
        text_lower = text.lower()
        for i in range(thumb_list.count()):
            item = thumb_list.item(i)
            item.setHidden(text_lower not in item.text().lower())

    filter_edit.textChanged.connect(_filter_thumbs)

    # Erstes Bild automatisch anzeigen
    if thumb_list.count() > 0:
        thumb_list.setCurrentRow(0)

    return page


def _build_textfiles_tab(mod_path: str):
    """Textdateien-Tab: Splitter; links Label + Liste + Filter, rechts Toolbar + Editor."""
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
    left_layout.addWidget(QLabel(tr("mod_detail.label_textfiles")))
    file_list = QListWidget()
    file_list.setObjectName("textFileList")
    file_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    file_list.setMinimumWidth(120)

    if mod_path and os.path.isdir(mod_path):
        for name in sorted(os.listdir(mod_path)):
            if name.endswith(".txt"):
                file_list.addItem(QListWidgetItem(name))
    if file_list.count() == 0:
        for name in ("readme.txt", "changelog.txt", "license.txt"):
            file_list.addItem(QListWidgetItem(name))
    if file_list.count() > 0:
        file_list.setCurrentRow(0)

    left_layout.addWidget(file_list)
    filter_edit = QLineEdit()
    filter_edit.setPlaceholderText(tr("placeholder.filter"))
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
    btn_save.setToolTip(tr("tooltip.save"))
    toolbar_layout.addWidget(btn_save)

    btn_ordner = QPushButton(tr("button.folder"))
    toolbar_layout.addWidget(btn_ordner)

    btn_wrap = QPushButton()
    btn_wrap.setObjectName("toolbarIconBtn")
    btn_wrap.setIcon(QIcon(_icon_path("zeilenumbruch (1).png")))
    btn_wrap.setToolTip(tr("tooltip.word_wrap"))
    btn_wrap.setCheckable(True)
    toolbar_layout.addWidget(btn_wrap)

    path_edit = QLineEdit()
    path_edit.setReadOnly(True)
    path_edit.setPlaceholderText(tr("mod_detail.no_file_selected"))
    path_edit.setStyleSheet("color: #808080; background: #1C1C1C; border: none;")
    toolbar_layout.addWidget(path_edit, 1)
    right_layout.addWidget(toolbar_widget)

    editor = CodeEditor()
    editor.setFont(_code_font())
    editor.setPlaceholderText(tr("mod_detail.select_file"))
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
            path_edit.setPlaceholderText(tr("mod_detail.no_file_selected"))
            editor.setPlainText("")
            return
        name = item.text()
        path = os.path.join(mod_path, name)
        current_path[0] = path
        path_edit.setText(path)
        try:
            with open(path, encoding="utf-8") as f:
                editor.setPlainText(f.read())
        except Exception as e:
            editor.setPlainText(tr("mod_detail.error_loading", error=str(e)))

    def on_save():
        path = current_path[0]
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            path_edit.setText(tr("mod_detail.saved"))
            path_edit.setStyleSheet("color: #4CAF50; background: #1C1C1C; border: none;")
            def restore():
                path_edit.setText(path)
                path_edit.setStyleSheet("color: #808080; background: #1C1C1C; border: none;")
            QTimer.singleShot(2000, restore)
        except Exception as e:
            path_edit.setText(tr("mod_detail.error", error=str(e)))

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


def _build_ini_tab(mod_path: str):
    """INI-Dateien Tab: Links Liste der .ini Dateien, rechts Editor.

    Findet alle .ini Dateien im Mod-Ordner (rekursiv) und ermöglicht
    das Anzeigen und Bearbeiten.
    """
    from pathlib import Path

    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # LINKS: Label "INI Dateien", QListWidget
    left_pane = QWidget()
    left_layout = QVBoxLayout(left_pane)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(6)
    left_layout.addWidget(QLabel(tr("mod_detail.label_ini_files")))

    file_list = QListWidget()
    file_list.setObjectName("iniFileList")
    file_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    file_list.setMinimumWidth(180)

    # Alle .ini Dateien im Mod-Ordner finden (rekursiv)
    ini_files: list[tuple[str, str]] = []  # (display_name, full_path)
    if mod_path and os.path.isdir(mod_path):
        mod_root = Path(mod_path)
        for ini_path in mod_root.rglob("*.ini"):
            # Relativen Pfad für Anzeige, vollen Pfad für Zugriff
            rel_path = ini_path.relative_to(mod_root)
            ini_files.append((str(rel_path), str(ini_path)))

    # Sortieren und zur Liste hinzufügen
    ini_files.sort(key=lambda x: x[0].lower())
    for display_name, full_path in ini_files:
        item = QListWidgetItem(display_name)
        item.setData(Qt.ItemDataRole.UserRole, full_path)
        file_list.addItem(item)

    if file_list.count() > 0:
        file_list.setCurrentRow(0)

    left_layout.addWidget(file_list)

    # Info-Label für Anzahl
    info_label = QLabel(tr("mod_detail.ini_files_found", count=len(ini_files)))
    info_label.setStyleSheet("color: #808080; font-size: 11px;")
    left_layout.addWidget(info_label)

    splitter.addWidget(left_pane)

    # RECHTS: Toolbar-Zeile oben, darunter Editor
    right_pane = QWidget()
    right_layout = QVBoxLayout(right_pane)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(0)

    # Toolbar
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
    btn_save.setToolTip(tr("tooltip.save_ctrl_s"))
    toolbar_layout.addWidget(btn_save)

    btn_reload = QPushButton()
    btn_reload.setObjectName("toolbarIconBtn")
    btn_reload.setIcon(QIcon(_icon_path("aktualisieren.png")))
    btn_reload.setToolTip(tr("tooltip.reload"))
    toolbar_layout.addWidget(btn_reload)

    btn_ordner = QPushButton(tr("button.folder"))
    btn_ordner.setToolTip(tr("tooltip.open_folder"))
    toolbar_layout.addWidget(btn_ordner)

    btn_wrap = QPushButton()
    btn_wrap.setObjectName("toolbarIconBtn")
    btn_wrap.setIcon(QIcon(_icon_path("zeilenumbruch (1).png")))
    btn_wrap.setToolTip(tr("tooltip.word_wrap"))
    btn_wrap.setCheckable(True)
    toolbar_layout.addWidget(btn_wrap)

    path_edit = QLineEdit()
    path_edit.setReadOnly(True)
    path_edit.setPlaceholderText(tr("mod_detail.no_file_selected"))
    path_edit.setStyleSheet("color: #808080; background: #1C1C1C; border: none;")
    toolbar_layout.addWidget(path_edit, 1)

    right_layout.addWidget(toolbar_widget)

    # Editor
    editor = CodeEditor()
    editor.setFont(_code_font())
    editor.setPlaceholderText(tr("mod_detail.select_ini_file"))
    editor.setPlainText("")
    editor.setReadOnly(False)
    editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    right_layout.addWidget(editor, 1)

    # State
    current_path = [None]
    has_changes = [False]

    def mark_changed():
        if current_path[0] and not has_changes[0]:
            has_changes[0] = True
            # Zeige * im Pfad
            path_edit.setText(f"* {current_path[0]}")

    def on_file_selected():
        # Änderungen speichern fragen? (hier einfach überschreiben)
        item = file_list.currentItem()
        if not item:
            current_path[0] = None
            path_edit.clear()
            path_edit.setPlaceholderText(tr("mod_detail.no_file_selected"))
            editor.setPlainText("")
            has_changes[0] = False
            return

        path = item.data(Qt.ItemDataRole.UserRole)
        current_path[0] = path
        path_edit.setText(path)
        path_edit.setStyleSheet("color: #808080; background: #1C1C1C; border: none;")
        has_changes[0] = False

        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                editor.setPlainText(f.read())
        except Exception as e:
            editor.setPlainText(tr("mod_detail.error_loading", error=str(e)))

    def on_save():
        path = current_path[0]
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            has_changes[0] = False
            path_edit.setText(path)
            path_edit.setStyleSheet("color: #4CAF50; background: #1C1C1C; border: none;")

            def restore():
                path_edit.setStyleSheet("color: #808080; background: #1C1C1C; border: none;")
            QTimer.singleShot(1500, restore)
        except Exception as e:
            path_edit.setText(tr("mod_detail.error", error=str(e)))
            path_edit.setStyleSheet("color: #F44336; background: #1C1C1C; border: none;")

    def on_reload():
        on_file_selected()

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

    # Verbindungen
    btn_save.clicked.connect(on_save)
    btn_reload.clicked.connect(on_reload)
    btn_ordner.clicked.connect(on_ordner)
    btn_wrap.toggled.connect(on_wrap_toggled)
    file_list.currentItemChanged.connect(lambda *a: on_file_selected())
    editor.textChanged.connect(mark_changed)

    # Initial laden
    on_file_selected()

    splitter.addWidget(right_pane)
    splitter.setSizes([220, 1080])
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    layout.addWidget(splitter, 1)

    return page


def _build_optional_esps_tab(mod_path: str):
    """Optionale ESPs Tab: Links deaktivierte Plugins, rechts aktive.

    Plugins können zwischen den Listen verschoben werden:
    - Nach links (←): Plugin wird in 'optional/' Unterordner verschoben (deaktiviert)
    - Nach rechts (→): Plugin wird zurück in Mod-Root verschoben (aktiviert)
    """
    from pathlib import Path
    import shutil

    PLUGIN_EXTENSIONS = {".esp", ".esm", ".esl"}

    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QHBoxLayout(page)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    # State
    mod_root = Path(mod_path) if mod_path else None
    optional_dir = mod_root / "optional" if mod_root else None

    # --- LINKE SPALTE: Optionale (deaktivierte) Plugins ---
    left_pane = QWidget()
    left_layout = QVBoxLayout(left_pane)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(6)

    left_label = QLabel(tr("mod_detail.optional_esps_disabled"))
    left_label.setStyleSheet("font-weight: bold;")
    left_layout.addWidget(left_label)

    optional_list = QListWidget()
    optional_list.setObjectName("optionalEspList")
    optional_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
    optional_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    left_layout.addWidget(optional_list)

    optional_count = QLabel(tr("mod_detail.plugins_count", count=0))
    optional_count.setStyleSheet("color: #808080; font-size: 11px;")
    left_layout.addWidget(optional_count)

    layout.addWidget(left_pane, 1)

    # --- MITTE: Buttons ---
    button_pane = QWidget()
    button_layout = QVBoxLayout(button_pane)
    button_layout.setContentsMargins(0, 0, 0, 0)
    button_layout.setSpacing(8)
    button_layout.addStretch()

    btn_to_optional = QPushButton("←")
    btn_to_optional.setFixedSize(40, 30)
    btn_to_optional.setToolTip(tr("tooltip.move_to_optional"))
    button_layout.addWidget(btn_to_optional)

    btn_to_active = QPushButton("→")
    btn_to_active.setFixedSize(40, 30)
    btn_to_active.setToolTip(tr("tooltip.move_to_active"))
    button_layout.addWidget(btn_to_active)

    button_layout.addStretch()
    layout.addWidget(button_pane)

    # --- RECHTE SPALTE: Aktive Plugins ---
    right_pane = QWidget()
    right_layout = QVBoxLayout(right_pane)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(6)

    right_label = QLabel(tr("mod_detail.active_esps"))
    right_label.setStyleSheet("font-weight: bold;")
    right_layout.addWidget(right_label)

    active_list = QListWidget()
    active_list.setObjectName("activeEspList")
    active_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
    active_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    right_layout.addWidget(active_list)

    active_count = QLabel(tr("mod_detail.plugins_count", count=0))
    active_count.setStyleSheet("color: #808080; font-size: 11px;")
    right_layout.addWidget(active_count)

    layout.addWidget(right_pane, 1)

    # --- Hilfsfunktionen ---
    def scan_plugins():
        """Scannt Mod-Ordner und optional/-Unterordner nach Plugins."""
        optional_list.clear()
        active_list.clear()

        if not mod_root or not mod_root.is_dir():
            optional_count.setText(tr("mod_detail.no_mod_folder"))
            active_count.setText(tr("mod_detail.no_mod_folder"))
            return

        # Aktive Plugins (nur Root-Ebene, nicht rekursiv)
        active_plugins = []
        for f in mod_root.iterdir():
            if f.is_file() and f.suffix.lower() in PLUGIN_EXTENSIONS:
                active_plugins.append(f.name)

        active_plugins.sort(key=str.lower)
        for name in active_plugins:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, str(mod_root / name))
            active_list.addItem(item)

        # Optionale Plugins (im optional/ Unterordner)
        opt_plugins = []
        if optional_dir and optional_dir.is_dir():
            for f in optional_dir.iterdir():
                if f.is_file() and f.suffix.lower() in PLUGIN_EXTENSIONS:
                    opt_plugins.append(f.name)

        opt_plugins.sort(key=str.lower)
        for name in opt_plugins:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, str(optional_dir / name))
            optional_list.addItem(item)

        # Counts aktualisieren
        optional_count.setText(tr("mod_detail.plugins_count", count=len(opt_plugins)))
        active_count.setText(tr("mod_detail.plugins_count", count=len(active_plugins)))

    def move_to_optional():
        """Verschiebt ausgewählte aktive Plugins nach optional/."""
        if not mod_root or not optional_dir:
            return

        selected = active_list.selectedItems()
        if not selected:
            return

        # optional/ Ordner erstellen falls nötig
        optional_dir.mkdir(exist_ok=True)

        for item in selected:
            src = Path(item.data(Qt.ItemDataRole.UserRole))
            dst = optional_dir / src.name
            try:
                shutil.move(str(src), str(dst))
            except OSError:
                pass  # Fehler ignorieren

        scan_plugins()

    def move_to_active():
        """Verschiebt ausgewählte optionale Plugins zurück in Mod-Root."""
        if not mod_root:
            return

        selected = optional_list.selectedItems()
        if not selected:
            return

        for item in selected:
            src = Path(item.data(Qt.ItemDataRole.UserRole))
            dst = mod_root / src.name
            try:
                shutil.move(str(src), str(dst))
            except OSError:
                pass  # Fehler ignorieren

        scan_plugins()

    # Buttons verbinden
    btn_to_optional.clicked.connect(move_to_optional)
    btn_to_active.clicked.connect(move_to_active)

    # Doppelklick zum schnellen Verschieben
    def on_optional_double_click(item):
        optional_list.setCurrentItem(item)
        move_to_active()

    def on_active_double_click(item):
        active_list.setCurrentItem(item)
        move_to_optional()

    optional_list.itemDoubleClicked.connect(on_optional_double_click)
    active_list.itemDoubleClicked.connect(on_active_double_click)

    # Initial scannen
    scan_plugins()

    return page


class TranslatedFileSystemModel(QFileSystemModel):
    """QFileSystemModel mit übersetzten Spalten-Headers."""

    _HEADERS = {
        0: "filetree.name",
        1: "filetree.size",
        2: "filetree.type",
        3: "filetree.date_modified",
    }

    def headerData(self, section: int, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section in self._HEADERS:
                return tr(self._HEADERS[section])
        return super().headerData(section, orientation, role)


def _build_filetree_tab(mod_path: str):
    """Verzeichnisbaum-Tab: QFileSystemModel + QTreeView.

    Zeigt die Verzeichnisstruktur des Mods mit Name, Größe, Typ, Datum.
    """
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    # "Mod im Explorer öffnen" Button
    btn_row = QHBoxLayout()
    btn_explore = QPushButton(tr("button.open_in_explorer"))
    btn_explore.clicked.connect(
        lambda: subprocess.Popen(["xdg-open", mod_path]) if os.path.isdir(mod_path) else None
    )
    btn_row.addWidget(btn_explore)
    btn_row.addStretch()
    layout.addLayout(btn_row)

    if not mod_path or not os.path.isdir(mod_path):
        layout.addWidget(QLabel(tr("mod_detail.mod_dir_not_found")))
        layout.addStretch()
        return page

    # QFileSystemModel für Verzeichnisstruktur
    fs_model = TranslatedFileSystemModel()
    fs_model.setRootPath(mod_path)
    fs_model.setReadOnly(True)

    # QTreeView für Dateibaum
    tree = QTreeView()
    tree.setObjectName("filetreeView")
    tree.setModel(fs_model)
    tree.setRootIndex(fs_model.index(mod_path))

    # Spalten-Breite
    tree.setColumnWidth(0, 300)  # Name

    # TreeView-Einstellungen
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

    # TODO: Kontextmenü (Open, Rename, Delete, Hide/Unhide)
    # TODO: Drag & Drop InternalMove
    # TODO: Header-State Persistenz

    return page


def _build_conflicts_tab(mod_name: str, all_mods, game_plugin):
    """Konflikte-Tab: Gewinnt/Verliert-Bereiche mit ConflictScanner.

    Zwei QTreeWidgets (Überschreibt / Wird überschrieben) mit Dateipfad
    und konkurrierendem Mod-Namen.
    """
    page = QWidget()
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)

    # Fallback: keine Mod-Daten verfügbar
    if not all_mods or not mod_name:
        layout.addWidget(QLabel(tr("mod_detail.conflict_detection_unavailable")))
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
        no_conflict = QLabel(tr("mod_detail.no_conflicts"))
        no_conflict.setStyleSheet("color: #4CAF50; font-size: 14px; padding: 20px;")
        no_conflict.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(no_conflict)
        layout.addStretch()
        ignored_count = len(result["ignored"])
        if ignored_count > 0:
            info = QLabel(tr("mod_detail.ignored_matches", count=ignored_count))
            info.setStyleSheet("color: #808080; font-size: 11px;")
            info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(info)
        return page

    # --- Gewinnt Konflikte (oben) ---
    win_label = QLabel(tr("mod_detail.wins_conflicts", count=len(wins)))
    win_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px;")
    layout.addWidget(win_label)

    win_tree = QTreeWidget()
    win_tree.setObjectName("conflictTree")
    win_tree.setHeaderLabels([tr("label.file"), tr("mod_detail.overwrites_mod")])
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
    lose_label = QLabel(tr("mod_detail.loses_conflicts", count=len(losses)))
    lose_label.setStyleSheet("color: #F44336; font-weight: bold; font-size: 12px;")
    layout.addWidget(lose_label)

    lose_tree = QTreeWidget()
    lose_tree.setObjectName("conflictTree")
    lose_tree.setHeaderLabels([tr("label.file"), tr("mod_detail.overwritten_by_mod")])
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
    if ignored > 0:
        info_text = tr("mod_detail.conflicts_with_ignored", total=total, ignored=ignored)
    else:
        info_text = tr("mod_detail.conflicts_count", count=total)
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
        layout.addWidget(QLabel(tr("mod_detail.categories_unavailable")))
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
        primary_combo.addItem(tr("mod_detail.no_primary"), 0)
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
    primary_label = QLabel(tr("mod_detail.primary_category"))
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
    # Custom result codes for navigation
    RESULT_PREV = 100
    RESULT_NEXT = 101

    def __init__(self, parent=None, mod_name="", mod_path="",
                 all_mods=None, game_plugin=None,
                 category_manager=None, mod_entry=None):
        super().__init__(parent)
        self._all_mods = all_mods or []
        self.setWindowTitle(mod_name or tr("dialog.mod_details"))
        self.setMinimumSize(1280, 720)
        self.resize(1300, 750)
        self.setStyleSheet(_MOD_DETAIL_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(12, 12, 12, 12)

        self.tab_widget = QTabWidget()

        # Tab 0: Textdateien
        self.tab_widget.addTab(_build_textfiles_tab(mod_path), tr("mod_detail.tab_textfiles"))
        # Tab 1: INI Dateien
        self.tab_widget.addTab(_build_ini_tab(mod_path), tr("mod_detail.tab_ini"))

        # Tab 2: Bilder
        self.tab_widget.addTab(_build_images_tab(mod_path), tr("mod_detail.tab_images"))

        # Tab 3: Optionale ESPs
        self.tab_widget.addTab(_build_optional_esps_tab(mod_path), tr("mod_detail.tab_optional_esps"))

        # Tab 4: Konflikte
        self.tab_widget.addTab(
            _build_conflicts_tab(mod_name, all_mods, game_plugin), tr("mod_detail.tab_conflicts"),
        )

        # Tab 5: Kategorien
        self._categories_page = _build_categories_tab(category_manager, mod_entry, mod_path)
        self.tab_widget.addTab(self._categories_page, tr("mod_detail.tab_categories"))

        # Layout-Update wenn Kategorien-Tab sichtbar wird
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Tab 6: Nexus Info
        self.tab_widget.addTab(_build_nexus_tab(mod_path), tr("mod_detail.tab_nexus"))

        # Tab 7: Verzeichnisbaum
        self.tab_widget.addTab(_build_filetree_tab(mod_path), tr("mod_detail.tab_filetree"))

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
        btn_back = QPushButton(tr("button.back"))
        btn_back.clicked.connect(lambda checked=False: self.done(self.RESULT_PREV))
        btn_next = QPushButton(tr("button.next"))
        btn_next.clicked.connect(lambda checked=False: self.done(self.RESULT_NEXT))
        btn_row.addWidget(btn_back)
        btn_row.addWidget(btn_next)
        btn_row.addStretch()
        btn_close = QPushButton(tr("button.close"))
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
