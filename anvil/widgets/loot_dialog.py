"""LOOT Sort Dialog — launches LOOT GUI with auto-sort.

LOOT opens as a GUI, auto-sorts the load order. The user reviews and
applies in LOOT, then closes it. Anvil re-reads plugins.txt afterwards.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
)

from anvil.core.loot.loot_runner import LootRunner, find_loot_binary
from anvil.core.translator import tr


class LootDialog(QDialog):
    """Dialog for launching LOOT and re-reading plugins.txt after."""

    def __init__(
        self,
        parent,
        game_plugin,
        game_path: Path,
        instance_path: Path,
    ) -> None:
        super().__init__(parent)
        self._game_plugin = game_plugin
        self._game_path = game_path
        self._instance_path = instance_path
        self._runner = LootRunner(self)
        self._loot_was_run = False

        game_name = getattr(game_plugin, "GameName", "")
        self.setWindowTitle(
            tr("loot.dialog_title") + f" — {game_name}"
        )
        self.setMinimumSize(500, 300)
        self.resize(600, 350)

        self._build_ui()
        self._connect_signals()

        # Auto-start LOOT after dialog is shown
        QTimer.singleShot(0, self._on_sort)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Status label
        self._status_label = QLabel(tr("loot.loot_running"))
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # Progress bar (indeterminate while LOOT runs)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(True)
        layout.addWidget(self._progress)

        # Log output
        self._log_area = QPlainTextEdit()
        self._log_area.setReadOnly(True)
        self._log_area.setMaximumHeight(120)
        self._log_area.setVisible(False)
        layout.addWidget(self._log_area)

        layout.addStretch()

        # Button row
        btn_row = QHBoxLayout()

        self._restart_btn = QPushButton(tr("loot.restart_button"))
        self._restart_btn.clicked.connect(self._on_sort)
        self._restart_btn.setVisible(False)
        btn_row.addWidget(self._restart_btn)

        btn_row.addStretch()

        self._status_info = QLabel("")
        btn_row.addWidget(self._status_info)

        btn_row.addStretch()

        self._close_btn = QPushButton(tr("loot.close_button"))
        self._close_btn.clicked.connect(self._on_close)
        btn_row.addWidget(self._close_btn)

        layout.addLayout(btn_row)

    def _connect_signals(self) -> None:
        self._runner.output_line.connect(self._on_output)
        self._runner.finished_ok.connect(self._on_loot_closed)
        self._runner.finished_error.connect(self._on_sort_error)

    # ── Actions ────────────────────────────────────────────────────────

    def _on_sort(self) -> None:
        """Launch LOOT GUI with auto-sort."""
        binary = find_loot_binary()
        if not binary:
            self._status_label.setText(tr("loot.no_binary"))
            self._progress.setVisible(False)
            self._restart_btn.setVisible(False)
            return

        loot_name = getattr(self._game_plugin, "LootGameName", "")
        if not loot_name:
            self._status_label.setText(tr("loot.not_bethesda"))
            self._progress.setVisible(False)
            self._restart_btn.setVisible(False)
            return

        self._restart_btn.setVisible(False)
        self._log_area.clear()
        self._log_area.setVisible(True)
        self._progress.setVisible(True)
        self._status_label.setText(tr("loot.loot_running"))
        self._status_info.setText("")

        self._runner.start(loot_name, self._game_path)

    def _on_close(self) -> None:
        """Cancel running LOOT or close dialog."""
        if self._runner.is_running:
            self._runner.kill()
            self._status_label.setText(tr("button.cancel"))
            self._progress.setVisible(False)
            self._restart_btn.setVisible(True)
        else:
            if self._loot_was_run:
                self.accept()
            else:
                self.reject()

    # ── Signal handlers ────────────────────────────────────────────────

    def _on_output(self, line: str) -> None:
        self._log_area.appendPlainText(line)

    def _on_loot_closed(self, _unused: str) -> None:
        """LOOT GUI closed normally — re-read plugins.txt."""
        self._progress.setVisible(False)
        self._restart_btn.setVisible(True)
        self._loot_was_run = True
        self._status_label.setText(tr("loot.loot_closed"))
        self._status_info.setText(tr("loot.plugins_reloaded"))

        # Refresh parent's plugins tab
        parent = self.parent()
        if parent and hasattr(parent, "_game_panel"):
            parent._game_panel._refresh_plugins_tab()

    def _on_sort_error(self, error: str) -> None:
        self._progress.setVisible(False)
        self._restart_btn.setVisible(True)
        self._status_label.setText(tr("loot.sorting_failed"))
        self._log_area.appendPlainText(f"ERROR: {error}")
