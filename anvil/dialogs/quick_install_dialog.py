"""Schnellinstallation-Dialog mit editierbarer ComboBox.

Modern (Vorlage Screen "Mod installieren"): Titelleiste mit FOMOD-Badge,
Archiv-Zeile, Mod-Name + Kategorie, Fußleiste Abbrechen/Installieren.
Klassisch: alte kompakte Optik unverändert.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QWidget,
    QLabel,
    QComboBox,
    QPushButton,
    QCompleter,
)
from PySide6.QtCore import Qt
from pathlib import Path

from anvil.core.translator import tr
from anvil.core.resource_path import get_anvil_base
from anvil.styles.dark_theme import theme_color

_ARROW_SVG = str(get_anvil_base() / "resources" / "arrow_down.svg").replace("\\", "/")

_STYLE = f"""
QDialog {{ background: #1C1C1C; color: #D3D3D3; }}
QLabel {{ color: #D3D3D3; }}
QComboBox {{
    background: #242424;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 4px 6px;
    selection-background-color: #006868;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: url({_ARROW_SVG});
    width: 10px;
    height: 6px;
}}
QComboBox QAbstractItemView {{
    background: #242424;
    color: #D3D3D3;
    selection-background-color: #006868;
    border: 1px solid #3D3D3D;
}}
QPushButton {{
    background: #1C1C1C;
    color: #D3D3D3;
    border: 1px solid #3D3D3D;
    border-radius: 2px;
    padding: 6px 16px;
    min-width: 70px;
}}
QPushButton:hover {{ background: #3D3D3D; }}
QPushButton:pressed {{ background: #006868; }}
QPushButton:disabled {{ color: #666666; border-color: #2A2A2A; }}
"""


def _format_size(num_bytes: int) -> str:
    """Dateigröße menschenlesbar (wie Vorlage: „38,4 MB")."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}".replace(".", ",")
        size /= 1024
    return ""


class QuickInstallDialog(QDialog):
    """Install-Dialog mit editierbarer ComboBox für den Mod-Namen.

    Die ComboBox wird mit Namensvarianten befüllt. Der beste Vorschlag
    ist vorausgewählt. Modern zusätzlich: Archiv-Info, Kategorie-Auswahl
    und FOMOD-Badge (Vorlage-Optik).
    """

    def __init__(
        self,
        variants: list[str],
        selected: str | None = None,
        parent=None,
        *,
        archive_name: str = "",
        archive_size: int = 0,
        fomod: bool = False,
        categories: list[tuple[int, str]] | None = None,
    ):
        """
        Args:
            variants: List of name suggestions for the combo box.
            selected: Which variant to pre-select.  Defaults to first.
            parent: Parent widget.
            archive_name: Dateiname des Archivs (Anzeige, nur modern).
            archive_size: Archivgröße in Bytes (Anzeige, nur modern).
            fomod: True → „FOMOD erkannt"-Badge in der Titelleiste.
            categories: (id, name)-Paare für die Kategorie-Auswahl.
        """
        super().__init__(parent)
        self._modern = bool(theme_color("panel2", ""))
        self._category_combo: QComboBox | None = None
        self.setWindowTitle(tr("dialog.quick_install"))
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        if self._modern:
            self._setup_modern(
                variants, selected, archive_name, archive_size,
                fomod, categories or [])
        else:
            self.setMinimumWidth(420)
            self.setStyleSheet(_STYLE)
            self._setup_classic(variants, selected)

    # ── Modern (Vorlage) ──────────────────────────────────────────────

    def _setup_modern(
        self, variants, selected, archive_name, archive_size,
        fomod, categories,
    ) -> None:
        self.setObjectName("settingsDlg")
        self.setFixedWidth(775)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)

        outer = QVBoxLayout(self)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QWidget()
        frame.setObjectName("modalFrame")
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer.addWidget(frame)
        root = QVBoxLayout(frame)
        root.setSpacing(0)
        root.setContentsMargins(1, 1, 1, 1)

        # Titelleiste
        title_bar = QWidget()
        title_bar.setObjectName("instTitleBar")
        title_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        title_bar.setFixedHeight(52)
        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(16, 0, 16, 0)
        tb.setSpacing(10)
        t_lbl = QLabel(tr("install.title"))
        t_lbl.setObjectName("instTitleLabel")
        tb.addWidget(t_lbl)
        if fomod:
            badge = QLabel(tr("install.fomod_badge"))
            badge.setObjectName("fomodBadge")
            tb.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        tb.addStretch()
        x_btn = QPushButton("✕")
        x_btn.setObjectName("instCloseBtn")
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.clicked.connect(self.reject)
        tb.addWidget(x_btn)
        root.addWidget(title_bar)

        # Inhalt
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 18, 20, 18)
        bl.setSpacing(16)

        if archive_name:
            arch_row = QWidget()
            arch_row.setObjectName("archiveRow")
            arch_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            ar = QHBoxLayout(arch_row)
            ar.setContentsMargins(15, 11, 15, 11)
            ar.setSpacing(10)
            a_lbl = QLabel(tr("install.archive"))
            a_lbl.setObjectName("archiveLabel")
            ar.addWidget(a_lbl)
            a_name = QLabel(archive_name)
            a_name.setObjectName("archiveName")
            ar.addWidget(a_name)
            ar.addStretch()
            if archive_size > 0:
                a_size = QLabel(_format_size(archive_size))
                a_size.setObjectName("archiveSize")
                ar.addWidget(a_size)
            bl.addWidget(arch_row)

        form = QGridLayout()
        form.setSpacing(12)
        form.setColumnMinimumWidth(0, 138)
        form.setColumnStretch(1, 1)

        name_label = QLabel(tr("install.mod_name"))
        name_label.setObjectName("instFormLabel")
        form.addWidget(
            name_label, 0, 0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._name_combo = QComboBox()
        self._name_combo.setEditable(True)
        self._fill_names(variants, selected)
        form.addWidget(self._name_combo, 0, 1)

        cat_label = QLabel(tr("install.category"))
        cat_label.setObjectName("instFormLabel")
        form.addWidget(
            cat_label, 1, 0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._category_combo = QComboBox()
        self._category_combo.addItem(tr("install.no_category"), 0)
        for cat_id, cat_name in categories:
            self._category_combo.addItem(cat_name, cat_id)
        form.addWidget(self._category_combo, 1, 1)
        bl.addLayout(form)

        hint = QLabel(tr("install.deploy_hint"))
        hint.setObjectName("installHint")
        bl.addWidget(hint)
        root.addWidget(body, 1)

        # Fußleiste: Abbrechen · Installieren (Akzent)
        footer = QWidget()
        footer.setObjectName("instFooter")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        footer.setFixedHeight(60)
        fr = QHBoxLayout(footer)
        fr.setContentsMargins(16, 0, 16, 0)
        fr.setSpacing(8)
        fr.addStretch()
        cancel_btn = QPushButton(tr("button.cancel"))
        cancel_btn.setObjectName("setCancelBtn")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        fr.addWidget(cancel_btn)
        install_btn = QPushButton(tr("fomod.install"))
        install_btn.setObjectName("setOkBtn")
        install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        install_btn.setDefault(True)
        install_btn.clicked.connect(self.accept)
        fr.addWidget(install_btn)
        root.addWidget(footer)

    # ── Klassisch (unverändert) ───────────────────────────────────────

    def _setup_classic(self, variants, selected) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Name-Zeile: Label "Name" + editierbare ComboBox
        name_row = QHBoxLayout()
        name_row.setContentsMargins(7, 7, 7, 7)
        name_row.setSpacing(6)
        label = QLabel(tr("label.name"))
        name_row.addWidget(label)

        self._name_combo = QComboBox()
        self._name_combo.setEditable(True)
        self._name_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._name_combo.setMinimumContentsLength(30)
        self._fill_names(variants, selected)
        name_row.addWidget(self._name_combo, 1)
        layout.addLayout(name_row)

        # Buttons: Manual | Spacer | OK | Cancel
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(7, 7, 7, 7)
        btn_row.setSpacing(6)

        btn_manual = QPushButton(tr("button.manual"))
        btn_manual.setEnabled(False)
        btn_manual.setToolTip(tr("tooltip.manual_install"))
        btn_row.addWidget(btn_manual)

        btn_row.addStretch()

        btn_ok = QPushButton(tr("button.ok"))
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)

        btn_cancel = QPushButton(tr("button.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        layout.addLayout(btn_row)

    # ── Gemeinsame Helfer ─────────────────────────────────────────────

    def _fill_names(self, variants, selected) -> None:
        for v in variants:
            self._name_combo.addItem(v)
        if selected:
            idx = self._name_combo.findText(selected)
            if idx >= 0:
                self._name_combo.setCurrentIndex(idx)
            else:
                self._name_combo.setCurrentText(selected)
        elif variants:
            self._name_combo.setCurrentIndex(0)
        completer = self._name_combo.completer()
        if completer:
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)

    def exec(self):  # noqa: A003
        """Modern: Hauptfenster abdunkeln, solange der Dialog offen ist."""
        if self._modern and self.parent() is not None:
            from anvil.widgets.modal_backdrop import ModalBackdrop
            backdrop = ModalBackdrop(self.parent().window())
            try:
                return super().exec()
            finally:
                backdrop.dismiss()
        return super().exec()

    def mod_name(self) -> str:
        """Return the user-entered/selected mod name, stripped."""
        return self._name_combo.currentText().strip()

    def set_name(self, name: str) -> None:
        """Update the combo box text (used when returning from Rename)."""
        self._name_combo.setCurrentText(name)

    def category_id(self) -> int:
        """Gewählte Kategorie-ID (0 = ohne Kategorie)."""
        if self._category_combo is None:
            return 0
        return int(self._category_combo.currentData() or 0)
