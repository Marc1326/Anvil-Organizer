"""Import dialog for .anvilpack collections."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget,
    QCheckBox,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from anvil.core.translator import tr
from anvil.core.collection_io import ImportResult


class _ModCard(QFrame):
    """A card showing a missing mod with an optional Nexus link."""

    def __init__(
        self,
        display_name: str,
        nexus_url: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background: #1a1a1a; border-radius: 6px; }"
        )
        self.setMinimumHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        name_label = QLabel(display_name)
        name_label.setStyleSheet(
            "color: #D3D3D3; font-size: 13px; background: transparent;"
        )
        layout.addWidget(name_label, 1)

        if nexus_url:
            link_btn = QPushButton(tr("collection.open_nexus"))
            link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            link_btn.setFixedHeight(28)
            link_btn.setStyleSheet(
                """
                QPushButton {
                    background: #006868;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 4px;
                    padding: 0 12px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: #007878;
                }
                """
            )
            link_btn.clicked.connect(
                lambda checked=False, u=nexus_url: QDesktopServices.openUrl(
                    QUrl(u)
                )
            )
            layout.addWidget(link_btn)


class CollectionImportDialog(QDialog):
    """Dialog showing collection contents and missing mods before import."""

    def __init__(
        self,
        parent=None,
        *,
        result: ImportResult,
        current_game_short: str = "",
    ):
        super().__init__(parent)
        self._result = result
        self._game_mismatch = False

        manifest = result.manifest

        self.setWindowTitle(tr("collection.import_title"))
        self.setFixedWidth(520)
        self.setMinimumHeight(300)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ── Title ──
        title = QLabel(tr("collection.import_title"))
        title.setStyleSheet(
            "font-size: 18px; font-weight: 600; color: #D3D3D3;"
        )
        layout.addWidget(title)

        # ── Game mismatch warning ──
        if (
            current_game_short
            and manifest.game_short_name
            and current_game_short.lower() != manifest.game_short_name.lower()
        ):
            self._game_mismatch = True
            warn_frame = QFrame()
            warn_frame.setStyleSheet(
                "QFrame { background: #4a2020; border-radius: 8px; }"
            )
            warn_layout = QVBoxLayout(warn_frame)
            warn_layout.setContentsMargins(16, 12, 16, 12)
            warn_label = QLabel(
                tr(
                    "collection.game_mismatch",
                    expected=manifest.game_name or manifest.game_short_name,
                    current=current_game_short,
                )
            )
            warn_label.setWordWrap(True)
            warn_label.setStyleSheet(
                "color: #ff8888; font-size: 13px; background: transparent;"
            )
            warn_layout.addWidget(warn_label)
            layout.addWidget(warn_frame)

        # ── Info card ──
        info_frame = QFrame()
        info_frame.setStyleSheet(
            "QFrame { background: #1a1a1a; border-radius: 8px; }"
        )
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(16, 12, 16, 12)
        info_layout.setSpacing(4)

        # Collection name
        if manifest.collection_name:
            coll_label = QLabel(
                f"{tr('collection.name_label')}: "
                f"<b>{manifest.collection_name}</b>"
            )
            coll_label.setStyleSheet(
                "color: #D3D3D3; font-size: 14px; background: transparent;"
            )
            info_layout.addWidget(coll_label)

        # Game
        game_label = QLabel(
            f"{tr('collection.game')}: <b>{manifest.game_name}</b>"
        )
        game_label.setStyleSheet(
            "color: #A0A0A0; font-size: 13px; background: transparent;"
        )
        info_layout.addWidget(game_label)

        # Author
        if manifest.collection_author:
            author_label = QLabel(
                f"{tr('collection.author_label')}: "
                f"<b>{manifest.collection_author}</b>"
            )
            author_label.setStyleSheet(
                "color: #A0A0A0; font-size: 13px; background: transparent;"
            )
            info_layout.addWidget(author_label)

        # Description
        if manifest.collection_description:
            desc_label = QLabel(manifest.collection_description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet(
                "color: #808080; font-size: 12px; "
                "margin-top: 4px; background: transparent;"
            )
            info_layout.addWidget(desc_label)

        # Stats
        total_mods = len(result.installed) + len(result.missing)
        stats_text = tr(
            "collection.import_stats",
            total=total_mods,
            installed=len(result.installed),
            missing=len(result.missing),
            separators=len(result.separators),
        )
        stats_label = QLabel(stats_text)
        stats_label.setStyleSheet(
            "color: #A0A0A0; font-size: 13px; "
            "margin-top: 4px; background: transparent;"
        )
        info_layout.addWidget(stats_label)

        layout.addWidget(info_frame)

        # ── Missing mods section ──
        if result.missing:
            missing_label = QLabel(
                tr("collection.missing_mods", count=len(result.missing))
            )
            missing_label.setStyleSheet(
                "color: #ff8888; font-size: 14px; font-weight: 600;"
            )
            layout.addWidget(missing_label)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setMaximumHeight(200)
            scroll.setStyleSheet(
                """
                QScrollArea { background: transparent; border: none; }
                QScrollBar:vertical {
                    background: #242424; width: 8px; border-radius: 4px;
                }
                QScrollBar::handle:vertical {
                    background: #3D3D3D; border-radius: 4px; min-height: 20px;
                }
                QScrollBar::handle:vertical:hover { background: #006868; }
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical { height: 0; }
                """
            )

            scroll_widget = QWidget()
            scroll_widget.setStyleSheet("background: transparent;")
            scroll_layout = QVBoxLayout(scroll_widget)
            scroll_layout.setContentsMargins(0, 0, 8, 0)
            scroll_layout.setSpacing(4)

            for mod in result.missing:
                display = mod.display_name or mod.name
                nexus_url = ""
                if mod.nexus_id > 0 and manifest.game_nexus_name:
                    nexus_url = (
                        f"https://www.nexusmods.com/"
                        f"{manifest.game_nexus_name}/mods/{mod.nexus_id}"
                    )
                elif mod.url:
                    nexus_url = mod.url

                card = _ModCard(display, nexus_url, scroll_widget)
                scroll_layout.addWidget(card)

            scroll_layout.addStretch()
            scroll.setWidget(scroll_widget)
            layout.addWidget(scroll, 1)

        # ── Options ──
        self._chk_categories = QCheckBox(
            tr("collection.apply_categories")
        )
        self._chk_categories.setChecked(True)
        self._chk_categories.setStyleSheet(
            "color: #D3D3D3; font-size: 13px;"
        )
        layout.addWidget(self._chk_categories)

        # ── Buttons ──
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        btn_layout.addStretch()

        btn_cancel = QPushButton(tr("button.cancel"))
        btn_cancel.setFixedHeight(36)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(
            """
            QPushButton {
                background: #3D3D3D; color: #D3D3D3;
                border: none; border-radius: 6px;
                padding: 0 20px; font-size: 13px; font-weight: 500;
            }
            QPushButton:hover { background: #4D4D4D; }
            """
        )
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        self._btn_import = QPushButton(tr("collection.import_button"))
        self._btn_import.setFixedHeight(36)
        self._btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_import.setStyleSheet(
            """
            QPushButton {
                background: #006868; color: #FFFFFF;
                border: none; border-radius: 6px;
                padding: 0 20px; font-size: 13px; font-weight: 500;
            }
            QPushButton:hover { background: #007878; }
            QPushButton:disabled {
                background: #3D3D3D; color: #808080;
            }
            """
        )
        self._btn_import.clicked.connect(self.accept)
        btn_layout.addWidget(self._btn_import)

        # Disable import if game mismatch
        if self._game_mismatch:
            self._btn_import.setEnabled(False)

        layout.addLayout(btn_layout)

    # ── Public API ──────────────────────────────────────────────────

    def apply_categories(self) -> bool:
        """Return True if user wants to apply category assignments."""
        return self._chk_categories.isChecked()

    def has_game_mismatch(self) -> bool:
        """Return True if the collection is for a different game."""
        return self._game_mismatch
