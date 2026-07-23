from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QThread, Signal, Slot
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QPushButton, QVBoxLayout

from anvil.core.base_migration import execute_pending_base_migration
from anvil.core.storage_migration import MigrationProgress
from anvil.core.translator import tr


class _BaseMigrationWorker(QObject):
    progress = Signal(object)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, settings_path: Path, cancel_event: threading.Event) -> None:
        super().__init__()
        self.settings_path = settings_path
        self.cancel_event = cancel_event

    @Slot()
    def run(self) -> None:
        settings = QSettings(str(self.settings_path), QSettings.Format.IniFormat)
        try:
            target = execute_pending_base_migration(
                settings=settings,
                progress=self.progress.emit,
                cancel_requested=self.cancel_event.is_set,
            )
        except BaseException as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(str(target or ""))


class BaseMigrationProgressDialog(QDialog):
    def __init__(self, parent=None, *, settings: QSettings) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("base_dir.migration_title"))
        self.setModal(True)
        self.setMinimumWidth(600)
        self._cancel_event = threading.Event()
        self._success = False
        self._failure_message = ""

        layout = QVBoxLayout(self)
        title = QLabel(tr("base_dir.migration_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        text = QLabel(tr("base_dir.migration_text"))
        text.setWordWrap(True)
        layout.addWidget(text)
        self._bar = QProgressBar()
        self._bar.setRange(0, 1000)
        layout.addWidget(self._bar)
        self._file = QLabel("—")
        self._file.setWordWrap(True)
        layout.addWidget(self._file)
        self._counts = QLabel("—")
        layout.addWidget(self._counts)
        self._cancel = QPushButton(tr("button.cancel"))
        self._cancel.setObjectName("setCancelBtn")
        self._cancel.clicked.connect(self._request_cancel)
        layout.addWidget(self._cancel)

        self._thread = QThread(self)
        self._worker = _BaseMigrationWorker(Path(settings.fileName()), self._cancel_event)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._update_progress)
        self._worker.finished.connect(self._migration_completed)
        self._worker.failed.connect(self._migration_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread_finished)
        self._thread.finished.connect(self._thread.deleteLater)

    @property
    def succeeded(self) -> bool:
        return self._success

    def start(self) -> int:
        self._thread.start()
        return self.exec()

    @Slot(object)
    def _update_progress(self, update: MigrationProgress) -> None:
        current = update.bytes_copied + update.current_file_bytes
        total = max(1, update.total_bytes)
        self._bar.setValue(min(1000, int(current / total * 1000)))
        self._file.setText(str(update.current_path or "—"))
        self._counts.setText(
            tr(
                "storage.progress_counts",
                files=update.files_copied,
                bytes=current,
                total=update.total_bytes,
            )
        )

    @Slot(str)
    def _migration_completed(self, target: str) -> None:
        self._success = True

    @Slot(str)
    def _migration_failed(self, message: str) -> None:
        self._failure_message = message

    @Slot()
    def _thread_finished(self) -> None:
        if self._success:
            self.accept()
            return
        self._file.setText(self._failure_message)
        self._cancel.setText(tr("button.close"))
        self._cancel.setEnabled(True)
        self._cancel.clicked.disconnect()
        self._cancel.clicked.connect(self.reject)

    def _request_cancel(self, checked: bool = False) -> None:
        if self._thread.isRunning():
            self._cancel_event.set()
            self._cancel.setEnabled(False)
            self._file.setText(tr("base_dir.migration_cancelling"))
        else:
            self.reject()

    def reject(self) -> None:
        if self._thread.isRunning():
            self._request_cancel()
            return
        super().reject()
