"""FOMOD installer wizard dialog.

MO2-style step-by-step installer that lets the user choose options
defined in a FOMOD ModuleConfig.xml.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QPushButton,
    QRadioButton,
    QCheckBox,
    QScrollArea,
    QWidget,
    QSplitter,
    QSizePolicy,
    QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from anvil.core.translator import tr
from anvil.core.fomod_parser import (
    FomodConfig,
    FomodPlugin,
    evaluate_conditions,
    resolve_path_ci,
)

_IMG_MAX_H = 300


class FomodDialog(QDialog):
    """FOMOD installer wizard dialog.

    Shows install steps with option groups.  The user selects options,
    then the dialog returns the selected plugins and condition flags.
    """

    def __init__(
        self,
        config: FomodConfig,
        temp_dir: Path,
        parent=None,
    ):
        super().__init__(parent)
        self._config = config
        self._temp_dir = temp_dir
        self._flags: dict[str, str] = {}
        # step_index -> {group_index: [plugin_indices]}
        self._step_selections: dict[int, dict[int, list[int]]] = {}
        self._visible_steps: list[int] = []
        self._current_vis_idx = 0
        # Current step's widgets: [(grp_idx, [widget, ...])]
        self._option_widgets: list[tuple[int, list[QRadioButton | QCheckBox]]] = []

        title = config.module_name or "FOMOD"
        self.setWindowTitle(f"{tr('fomod.title')} -- {title}")
        self.setMinimumSize(750, 500)
        self.resize(850, 580)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        # M1 fix: use objectName for QSS styling instead of setStyleSheet
        self.setObjectName("fomodDialog")

        # -- Layout --------------------------------------------------------
        main = QVBoxLayout(self)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(8)

        # Step label
        self._step_label = QLabel()
        self._step_label.setObjectName("fomodStepLabel")
        main.addWidget(self._step_label)

        # Splitter: options (left) | preview (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left -- scrollable options
        self._options_scroll = QScrollArea()
        self._options_scroll.setWidgetResizable(True)
        self._options_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        splitter.addWidget(self._options_scroll)

        # Right -- preview panel
        preview = QWidget()
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(8, 0, 0, 0)

        self._preview_image = QLabel()
        self._preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_image.setMinimumHeight(200)
        self._preview_image.setObjectName("fomodPreviewImage")
        pv.addWidget(self._preview_image)

        self._preview_desc = QLabel()
        self._preview_desc.setWordWrap(True)
        self._preview_desc.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._preview_desc.setObjectName("fomodPreviewDesc")
        self._preview_desc.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        pv.addWidget(self._preview_desc)

        splitter.addWidget(preview)
        splitter.setSizes([420, 350])
        main.addWidget(splitter, 1)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 8, 0, 0)

        self._btn_back = QPushButton(tr("fomod.back"))
        self._btn_back.clicked.connect(lambda checked=False: self._go_back())
        btn_row.addWidget(self._btn_back)

        btn_row.addStretch()

        self._btn_next = QPushButton(tr("fomod.next"))
        self._btn_next.setDefault(True)
        self._btn_next.clicked.connect(lambda checked=False: self._go_next())
        btn_row.addWidget(self._btn_next)

        self._btn_cancel = QPushButton(tr("fomod.cancel"))
        self._btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self._btn_cancel)

        main.addLayout(btn_row)

        # -- Initialise ----------------------------------------------------
        self._update_visible_steps()
        if self._visible_steps:
            self._show_step(0)
        self._update_buttons()

    # -- Public result API -------------------------------------------------

    def selected_plugins(self) -> list[FomodPlugin]:
        """Return all selected plugins across all visible steps."""
        self._save_current_step()
        result: list[FomodPlugin] = []
        for step_idx, group_sels in self._step_selections.items():
            step = self._config.install_steps[step_idx]
            for grp_idx, plugin_indices in group_sels.items():
                group = step.groups[grp_idx]
                for pi in plugin_indices:
                    if 0 <= pi < len(group.plugins):
                        result.append(group.plugins[pi])
        return result

    def flags(self) -> dict[str, str]:
        """Return the final flag state after all selections."""
        self._save_current_step()
        return dict(self._flags)

    # -- Step navigation ---------------------------------------------------

    def _update_visible_steps(self) -> None:
        """Recalculate which steps are visible based on current flags."""
        self._visible_steps = []
        for i, step in enumerate(self._config.install_steps):
            if step.visible_conditions is None:
                self._visible_steps.append(i)
            elif evaluate_conditions(
                step.visible_conditions, step.visible_operator, self._flags
            ):
                self._visible_steps.append(i)

    def _show_step(self, vis_idx: int) -> None:
        """Render the step at visible index *vis_idx*."""
        self._current_vis_idx = vis_idx
        step_idx = self._visible_steps[vis_idx]
        step = self._config.install_steps[step_idx]

        total = len(self._visible_steps)
        self._step_label.setText(
            tr("fomod.step_of", current=vis_idx + 1, total=total, name=step.name)
        )

        # -- Build option widgets ------------------------------------------
        self._option_widgets = []
        old = self._options_scroll.takeWidget()
        if old:
            old.deleteLater()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(12)

        prev_sels = self._step_selections.get(step_idx, {})
        first_plugin: FomodPlugin | None = None

        for grp_idx, group in enumerate(step.groups):
            grp_box = QGroupBox(group.name)
            grp_layout = QVBoxLayout(grp_box)
            grp_layout.setSpacing(2)

            prev = prev_sels.get(grp_idx, [])
            widgets: list[QRadioButton | QCheckBox] = []

            if group.group_type in ("SelectExactlyOne", "SelectAtMostOne"):
                self._build_radio_group(
                    group, grp_idx, grp_layout, prev, widgets
                )
            else:
                self._build_checkbox_group(
                    group, grp_idx, grp_layout, prev, widgets
                )

            self._option_widgets.append((grp_idx, widgets))
            layout.addWidget(grp_box)

            # Track the first pre-selected plugin for initial preview
            if first_plugin is None:
                for w in widgets:
                    pi = w.property("plugin_index")
                    if isinstance(pi, int) and pi >= 0:
                        if (isinstance(w, QRadioButton) and w.isChecked()) or \
                           (isinstance(w, QCheckBox) and w.isChecked()):
                            first_plugin = group.plugins[pi]
                            break

        layout.addStretch()
        self._options_scroll.setWidget(container)

        # -- Initial preview -----------------------------------------------
        if first_plugin and first_plugin.image_path:
            self._load_preview_image(first_plugin.image_path)
        elif vis_idx == 0 and self._config.module_image:
            self._load_preview_image(self._config.module_image)
        else:
            self._preview_image.clear()
            self._preview_image.setText(tr("fomod.no_image"))

        if first_plugin and first_plugin.description:
            self._preview_desc.setText(first_plugin.description)
        else:
            self._preview_desc.setText(tr("fomod.no_description"))

        self._update_buttons()

    # -- Group builders ----------------------------------------------------

    def _build_radio_group(
        self,
        group,
        grp_idx: int,
        layout: QVBoxLayout,
        prev: list[int],
        widgets: list,
    ) -> None:
        """Build radio buttons for SelectExactlyOne / SelectAtMostOne."""
        # "None" option for SelectAtMostOne
        if group.group_type == "SelectAtMostOne":
            none_rb = QRadioButton(tr("fomod.none_option"))
            none_rb.setProperty("plugin_index", -1)
            none_rb.clicked.connect(
                lambda checked=False, gi=grp_idx, pi=-1: self._on_option_clicked(gi, pi)
            )
            layout.addWidget(none_rb)
            widgets.append(none_rb)
            if not prev:
                none_rb.setChecked(True)

        # Determine which plugin to pre-select when no previous selection
        pre_idx = prev[0] if prev else None
        if pre_idx is None:
            # Prefer Required > Recommended > first non-NotUsable
            for pi, p in enumerate(group.plugins):
                if p.type_name == "Required":
                    pre_idx = pi
                    break
            if pre_idx is None:
                for pi, p in enumerate(group.plugins):
                    if p.type_name == "Recommended":
                        pre_idx = pi
                        break
            if pre_idx is None and group.group_type == "SelectExactlyOne":
                for pi, p in enumerate(group.plugins):
                    if p.type_name != "NotUsable":
                        pre_idx = pi
                        break

        for pi, plugin in enumerate(group.plugins):
            rb = QRadioButton(self._plugin_label(plugin))
            rb.setProperty("plugin_index", pi)
            rb.setEnabled(plugin.type_name != "NotUsable")
            rb.clicked.connect(
                lambda checked=False, gi=grp_idx, pi=pi: self._on_option_clicked(gi, pi)
            )
            layout.addWidget(rb)
            widgets.append(rb)

            if pi == pre_idx:
                rb.setChecked(True)

    def _build_checkbox_group(
        self,
        group,
        grp_idx: int,
        layout: QVBoxLayout,
        prev: list[int],
        widgets: list,
    ) -> None:
        """Build checkboxes for SelectAny / SelectAtLeastOne / SelectAll."""
        for pi, plugin in enumerate(group.plugins):
            cb = QCheckBox(self._plugin_label(plugin))
            cb.setProperty("plugin_index", pi)
            cb.clicked.connect(
                lambda checked=False, gi=grp_idx, pi=pi: self._on_option_clicked(gi, pi)
            )

            if group.group_type == "SelectAll":
                cb.setChecked(True)
                cb.setEnabled(False)
            elif plugin.type_name == "Required":
                cb.setChecked(True)
                cb.setEnabled(False)
            elif plugin.type_name == "NotUsable":
                cb.setEnabled(False)
            elif prev:
                cb.setChecked(pi in prev)
            elif plugin.type_name == "Recommended":
                cb.setChecked(True)

            layout.addWidget(cb)
            widgets.append(cb)

    # -- Helpers -----------------------------------------------------------

    @staticmethod
    def _plugin_label(plugin: FomodPlugin) -> str:
        """Build display label with type suffix."""
        label = plugin.name
        if plugin.type_name == "Required":
            label += f"  {tr('fomod.required')}"
        elif plugin.type_name == "Recommended":
            label += f"  {tr('fomod.recommended')}"
        elif plugin.type_name == "NotUsable":
            label += f"  {tr('fomod.not_usable')}"
        return label

    def _on_option_clicked(self, grp_idx: int, plugin_idx: int) -> None:
        """Update preview panel when an option is clicked."""
        step_idx = self._visible_steps[self._current_vis_idx]
        step = self._config.install_steps[step_idx]

        if 0 <= grp_idx < len(step.groups):
            group = step.groups[grp_idx]
            if 0 <= plugin_idx < len(group.plugins):
                plugin = group.plugins[plugin_idx]
                if plugin.image_path:
                    self._load_preview_image(plugin.image_path)
                else:
                    self._preview_image.clear()
                    self._preview_image.setText(tr("fomod.no_image"))
                self._preview_desc.setText(
                    plugin.description or tr("fomod.no_description")
                )
                return

        # "None" or invalid index
        self._preview_image.clear()
        self._preview_image.setText(tr("fomod.no_image"))
        self._preview_desc.setText("")

    def _load_preview_image(self, rel_path: str) -> None:
        """Load a preview image from the extracted archive."""
        resolved = resolve_path_ci(self._temp_dir, rel_path)
        if resolved and resolved.is_file():
            pixmap = QPixmap(str(resolved))
            if not pixmap.isNull():
                w = max(self._preview_image.width() - 10, 200)
                scaled = pixmap.scaled(
                    w,
                    _IMG_MAX_H,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._preview_image.setPixmap(scaled)
                return
        self._preview_image.clear()
        self._preview_image.setText(tr("fomod.no_image"))

    def _collect_current_selections(self) -> dict[int, list[int]]:
        """Read selections from the current step's widgets."""
        selections: dict[int, list[int]] = {}
        for grp_idx, widgets in self._option_widgets:
            selected: list[int] = []
            for w in widgets:
                pi = w.property("plugin_index")
                if not isinstance(pi, int) or pi < 0:
                    continue
                if isinstance(w, QRadioButton) and w.isChecked():
                    selected.append(pi)
                elif isinstance(w, QCheckBox) and w.isChecked():
                    selected.append(pi)
            selections[grp_idx] = selected
        return selections

    def _validate_current_step(self) -> bool:
        """Check that all required groups have valid selections (K2 fix).

        Returns *True* if the current step passes validation.
        """
        if not self._visible_steps:
            return True
        step_idx = self._visible_steps[self._current_vis_idx]
        step = self._config.install_steps[step_idx]
        selections = self._collect_current_selections()

        for grp_idx, group in enumerate(step.groups):
            sel = selections.get(grp_idx, [])

            if group.group_type == "SelectExactlyOne" and len(sel) != 1:
                QMessageBox.warning(
                    self,
                    tr("fomod.title"),
                    tr("fomod.validation_required", group=group.name),
                )
                return False

            if group.group_type == "SelectAtLeastOne" and len(sel) < 1:
                QMessageBox.warning(
                    self,
                    tr("fomod.title"),
                    tr("fomod.validation_required", group=group.name),
                )
                return False

        return True

    def _save_current_step(self) -> None:
        """Persist current step selections and rebuild flags."""
        if not self._visible_steps:
            return
        step_idx = self._visible_steps[self._current_vis_idx]
        self._step_selections[step_idx] = self._collect_current_selections()

        # Rebuild all flags from scratch (order matters)
        self._flags.clear()
        for si in sorted(self._step_selections):
            step = self._config.install_steps[si]
            for gi, plugin_indices in self._step_selections[si].items():
                if gi >= len(step.groups):
                    continue
                group = step.groups[gi]
                for pi in plugin_indices:
                    if 0 <= pi < len(group.plugins):
                        for fname, fval in group.plugins[pi].condition_flags:
                            self._flags[fname] = fval

    def _go_next(self) -> None:
        """Advance to the next visible step, or accept on the last."""
        # K2 fix: validate required selections before proceeding
        if not self._validate_current_step():
            return

        self._save_current_step()
        self._update_visible_steps()

        if self._current_vis_idx >= len(self._visible_steps) - 1:
            self.accept()
            return

        self._show_step(self._current_vis_idx + 1)

    def _go_back(self) -> None:
        """Go back to the previous visible step."""
        self._save_current_step()
        if self._current_vis_idx > 0:
            self._show_step(self._current_vis_idx - 1)

    def _update_buttons(self) -> None:
        """Update navigation button state."""
        self._btn_back.setEnabled(self._current_vis_idx > 0)
        is_last = self._current_vis_idx >= len(self._visible_steps) - 1
        self._btn_next.setText(tr("fomod.install") if is_last else tr("fomod.next"))
