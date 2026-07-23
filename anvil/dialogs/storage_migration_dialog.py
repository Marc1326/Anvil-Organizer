from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from anvil.core.instance_manager import InstanceManager
from anvil.core.storage_migration import InstanceStorageMigration, MigrationProgress
from anvil.core.translator import tr


_COMPONENT_ORDER = (
    "mods",
    "downloads",
    "profiles",
    "overwrite",
    "backups",
    "cache",
)


@dataclass(frozen=True, slots=True)
class StorageMigrationRequest:
    instances: tuple[str, ...]
    components: tuple[str, ...]
    target_base: Path
    verification: str
    base_directory: bool = False


class StorageMigrationWorker(QObject):
    progress = Signal(str, object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, migration: InstanceStorageMigration) -> None:
        super().__init__()
        self.migration = migration
        self.migration.progress = self._report_progress

    def _report_progress(self, component: str, update: MigrationProgress) -> None:
        self.progress.emit(component, update)

    @Slot()
    def run(self) -> None:
        try:
            self.migration.run()
        except BaseException as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(self.migration)


class StorageMigrationDialog(QDialog):
    migration_requested = Signal(object)
    cancel_requested = Signal()

    PAGE_SCOPE = 0
    PAGE_COMPONENTS = 1
    PAGE_TARGET = 2
    PAGE_REVIEW = 3
    PAGE_PROGRESS = 4
    PAGE_RESULT = 5

    def __init__(
        self,
        parent=None,
        *,
        manager: InstanceManager,
        current_instance: str | None,
    ) -> None:
        super().__init__(parent)
        self.manager = manager
        self.current_instance = current_instance
        self.setWindowTitle(tr("storage.title"))
        self.setMinimumSize(680, 500)
        self.resize(780, 600)
        self.setModal(True)
        self.setObjectName("storageMigrationDialog")
        self._running = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("instHeader")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 14)
        title = QLabel(tr("storage.title"))
        title.setObjectName("instTitle")
        self._subtitle = QLabel(tr("storage.subtitle"))
        self._subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(self._subtitle)
        root.addWidget(header)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_scope_page())
        self._stack.addWidget(self._build_components_page())
        self._stack.addWidget(self._build_target_page())
        self._stack.addWidget(self._build_review_page())
        self._stack.addWidget(self._build_progress_page())
        self._stack.addWidget(self._build_result_page())
        root.addWidget(self._stack, 1)

        footer = QWidget()
        footer.setObjectName("instFooter")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 8, 16, 8)
        self._back_button = QPushButton(tr("button.back"))
        self._back_button.setObjectName("setCancelBtn")
        self._back_button.clicked.connect(lambda checked=False: self._go_back())
        self._cancel_button = QPushButton(tr("button.cancel"))
        self._cancel_button.setObjectName("setCancelBtn")
        self._cancel_button.clicked.connect(lambda checked=False: self._cancel())
        self._next_button = QPushButton(tr("button.next"))
        self._next_button.setObjectName("setOkBtn")
        self._next_button.clicked.connect(lambda checked=False: self._go_next())
        self._start_button = QPushButton(tr("storage.start"))
        self._start_button.setObjectName("setOkBtn")
        self._start_button.clicked.connect(lambda checked=False: self._start_migration())
        self._close_button = QPushButton(tr("button.close"))
        self._close_button.setObjectName("setOkBtn")
        self._close_button.clicked.connect(lambda checked=False: self.accept())
        footer_layout.addWidget(self._back_button)
        footer_layout.addStretch()
        footer_layout.addWidget(self._cancel_button)
        footer_layout.addWidget(self._next_button)
        footer_layout.addWidget(self._start_button)
        footer_layout.addWidget(self._close_button)
        root.addWidget(footer)
        self._show_page(self.PAGE_SCOPE)

    @staticmethod
    def _page(title_key: str, text_key: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        title = QLabel(tr(title_key))
        title.setObjectName("sectionTitle")
        description = QLabel(tr(text_key))
        description.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(description)
        return page, layout

    def _build_scope_page(self) -> QWidget:
        page, layout = self._page("storage.scope_title", "storage.scope_text")
        self._scope_group = QButtonGroup(self)
        self._scope_current = QRadioButton(tr("storage.scope_current"))
        self._scope_multiple = QRadioButton(tr("storage.scope_multiple"))
        self._scope_all = QRadioButton(tr("storage.scope_all"))
        self._scope_base = QRadioButton(tr("storage.scope_base"))
        for button in (
            self._scope_current,
            self._scope_multiple,
            self._scope_all,
            self._scope_base,
        ):
            self._scope_group.addButton(button)
            layout.addWidget(button)
        if self.current_instance:
            self._scope_current.setText(
                tr("storage.scope_current_named", name=self.current_instance)
            )
            self._scope_current.setChecked(True)
        else:
            self._scope_current.setEnabled(False)
            self._scope_multiple.setChecked(True)

        self._instance_list = QListWidget()
        self._instance_list.setObjectName("storageInstanceList")
        for data in self.manager.list_instances():
            item = QListWidgetItem(str(data["name"]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._instance_list.addItem(item)
        self._scope_multiple.toggled.connect(self._instance_list.setEnabled)
        self._instance_list.setEnabled(self._scope_multiple.isChecked())
        layout.addWidget(self._instance_list, 1)
        return page

    def _build_components_page(self) -> QWidget:
        page, layout = self._page("storage.components_title", "storage.components_text")
        self._whole_instance = QCheckBox(tr("storage.component_whole_instance"))
        self._whole_instance.setObjectName("storageWholeInstance")
        layout.addWidget(self._whole_instance)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(separator)
        self._component_boxes: dict[str, QCheckBox] = {}
        for component in _COMPONENT_ORDER:
            box = QCheckBox(tr(f"storage.component_{component}"))
            box.setObjectName(f"storageComponent_{component}")
            self._component_boxes[component] = box
            layout.addWidget(box)
        self._whole_instance.toggled.connect(self._toggle_whole_instance)
        layout.addStretch()
        return page

    def _build_target_page(self) -> QWidget:
        page, layout = self._page("storage.target_title", "storage.target_text")
        target_row = QHBoxLayout()
        self._target_edit = QLineEdit()
        self._target_edit.setObjectName("storageTargetEdit")
        self._target_edit.setPlaceholderText(tr("storage.target_placeholder"))
        browse = QPushButton("...")
        browse.clicked.connect(lambda checked=False: self._browse_target())
        target_row.addWidget(self._target_edit, 1)
        target_row.addWidget(browse)
        layout.addLayout(target_row)
        verification_label = QLabel(tr("storage.verification"))
        self._verification_combo = QComboBox()
        self._verification_combo.addItem(tr("storage.verification_full"), "full")
        self._verification_combo.addItem(tr("storage.verification_fast"), "fast")
        layout.addWidget(verification_label)
        layout.addWidget(self._verification_combo)
        warning = QLabel(tr("storage.source_retained"))
        warning.setWordWrap(True)
        warning.setObjectName("installHint")
        layout.addWidget(warning)
        layout.addStretch()
        return page

    def _build_review_page(self) -> QWidget:
        page, layout = self._page("storage.review_title", "storage.review_text")
        self._review_label = QLabel()
        self._review_label.setWordWrap(True)
        self._review_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._review_label)
        layout.addStretch()
        return page

    def _build_progress_page(self) -> QWidget:
        page, layout = self._page("storage.progress_title", "storage.progress_text")
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setValue(0)
        self._progress_component = QLabel("—")
        self._progress_file = QLabel("—")
        self._progress_counts = QLabel("—")
        self._progress_timing = QLabel("—")
        for widget in (
            self._progress_bar,
            self._progress_component,
            self._progress_file,
            self._progress_counts,
            self._progress_timing,
        ):
            layout.addWidget(widget)
        layout.addStretch()
        return page

    def _build_result_page(self) -> QWidget:
        page, layout = self._page("storage.result_title", "storage.result_text")
        self._result_label = QLabel()
        self._result_label.setWordWrap(True)
        self._result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._result_label)
        self._open_target_button = QPushButton(tr("storage.open_target"))
        self._open_target_button.setEnabled(False)
        layout.addWidget(self._open_target_button)
        layout.addStretch()
        return page

    def _toggle_whole_instance(self, checked: bool) -> None:
        for box in self._component_boxes.values():
            box.setChecked(checked)
            box.setEnabled(not checked)

    def _selected_instances(self) -> tuple[str, ...]:
        if self._scope_current.isChecked():
            return (self.current_instance,) if self.current_instance else ()
        all_names = tuple(
            self._instance_list.item(index).text()
            for index in range(self._instance_list.count())
        )
        if self._scope_all.isChecked():
            return all_names
        return tuple(
            self._instance_list.item(index).text()
            for index in range(self._instance_list.count())
            if self._instance_list.item(index).checkState() is Qt.CheckState.Checked
        )

    def _selected_components(self) -> tuple[str, ...]:
        return tuple(
            component
            for component in _COMPONENT_ORDER
            if self._component_boxes[component].isChecked()
        )

    def request(self) -> StorageMigrationRequest | None:
        base_directory = self._scope_base.isChecked()
        instances = self._selected_instances()
        components = self._selected_components()
        if base_directory:
            components = ("base",)
        target_text = self._target_edit.text().strip()
        if (not base_directory and not instances) or not components or not target_text:
            return None
        return StorageMigrationRequest(
            instances=instances,
            components=components,
            target_base=Path(target_text).expanduser().absolute(),
            verification=str(self._verification_combo.currentData()),
            base_directory=base_directory,
        )

    def _browse_target(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            tr("storage.target_title"),
            self._target_edit.text(),
        )
        if path:
            self._target_edit.setText(path)

    def _go_next(self) -> None:
        page = self._stack.currentIndex()
        base_directory = self._scope_base.isChecked()
        if page == self.PAGE_SCOPE and not base_directory and not self._selected_instances():
            self._warn(tr("storage.error_no_instances"))
            return
        if page == self.PAGE_COMPONENTS and not self._selected_components():
            self._warn(tr("storage.error_no_components"))
            return
        if page == self.PAGE_TARGET and not self._target_edit.text().strip():
            self._warn(tr("storage.error_no_target"))
            return
        if page == self.PAGE_TARGET:
            self._update_review()
        if page == self.PAGE_SCOPE and base_directory:
            self._show_page(self.PAGE_TARGET)
            return
        self._show_page(min(self.PAGE_REVIEW, page + 1))

    def _go_back(self) -> None:
        if self._running:
            return
        if self._stack.currentIndex() == self.PAGE_TARGET and self._scope_base.isChecked():
            self._show_page(self.PAGE_SCOPE)
            return
        self._show_page(max(self.PAGE_SCOPE, self._stack.currentIndex() - 1))

    def _update_review(self) -> None:
        request = self.request()
        if request is None:
            self._review_label.clear()
            return
        self._review_label.setText(
            tr(
                "storage.review_summary",
                instances=(
                    tr("storage.scope_base")
                    if request.base_directory
                    else "\n".join(request.instances)
                ),
                components=", ".join(
                    tr(f"storage.component_{component}")
                    for component in request.components
                ),
                target=str(request.target_base),
                verification=request.verification,
            )
        )

    def _start_migration(self) -> None:
        request = self.request()
        if request is None:
            self._warn(tr("storage.error_incomplete"))
            return
        self._running = True
        self._show_page(self.PAGE_PROGRESS)
        self.migration_requested.emit(request)

    def _cancel(self) -> None:
        if self._running:
            self._cancel_button.setEnabled(False)
            self.cancel_requested.emit()
        else:
            self.reject()

    def update_progress(
        self,
        *,
        fraction: float,
        component: str,
        current_file: str,
        counts: str,
        timing: str,
    ) -> None:
        self._progress_bar.setValue(max(0, min(1000, int(fraction * 1000))))
        self._progress_component.setText(component)
        self._progress_file.setText(current_file)
        self._progress_counts.setText(counts)
        self._progress_timing.setText(timing)

    def show_result(self, *, success: bool, message: str) -> None:
        self._running = False
        self._result_label.setText(message)
        self._result_label.setObjectName("successLabel" if success else "errorLabel")
        self._show_page(self.PAGE_RESULT)

    def _show_page(self, page: int) -> None:
        self._stack.setCurrentIndex(page)
        self._back_button.setVisible(page in {1, 2, 3})
        self._next_button.setVisible(page in {0, 1, 2})
        self._start_button.setVisible(page == self.PAGE_REVIEW)
        self._close_button.setVisible(page == self.PAGE_RESULT)
        self._cancel_button.setVisible(page != self.PAGE_RESULT)
        self._cancel_button.setEnabled(True)

    def _warn(self, text: str) -> None:
        QMessageBox.warning(self, tr("storage.title"), text)

    def reject(self) -> None:
        if self._running:
            self._cancel()
            return
        super().reject()
