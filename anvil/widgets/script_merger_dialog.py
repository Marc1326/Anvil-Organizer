"""Script Merger Dialog — Witcher 3 Script-Konflikte scannen und auto-mergen."""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTextEdit,
    QPushButton,
    QProgressBar,
    QMessageBox,
    QWidget,
)
from PySide6.QtCore import Qt, QThread, Signal, QProcess, QSettings
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from anvil.core.translator import tr
from anvil.core.script_merger.models import (
    MergeStatus,
    MergeInventoryEntry,
    ScriptConflict,
    MergeResult,
)
from anvil.core.script_merger.scanner import ScriptScanner
from anvil.core.script_merger.merger import ScriptMerger
from anvil.core.script_merger.inventory import MergeInventory
from anvil.core.script_merger.ws_codec import write_script_file, file_hash


# ---------------------------------------------------------------------------
# Status-Icons (gemalte Kreise per QPainter, kein SVG)
# ---------------------------------------------------------------------------

def _status_icon(color: str) -> QIcon:
    """Erzeugt ein rundes farbiges Icon (16x16) fuer die Konflikt-Liste."""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(2, 2, 12, 12)
    p.end()
    return QIcon(pixmap)


_ICONS: dict[MergeStatus, QIcon] = {}


def _get_icons() -> dict[MergeStatus, QIcon]:
    """Lazy-Init der Icons (QPainter braucht laufende QApplication)."""
    global _ICONS
    if not _ICONS:
        _ICONS = {
            MergeStatus.UNSCANNED: _status_icon("#888888"),
            MergeStatus.AUTO_MERGEABLE: _status_icon("#FFD700"),
            MergeStatus.CONFLICT: _status_icon("#FF4444"),
            MergeStatus.MERGED: _status_icon("#44BB44"),
            MergeStatus.IGNORED: _status_icon("#444444"),
        }
    return _ICONS


# ---------------------------------------------------------------------------
# Worker-Threads
# ---------------------------------------------------------------------------

class _ScanWorker(QThread):
    """Fuehrt den Script-Scan im Hintergrund aus."""

    progress = Signal(int, int)           # aktuell, gesamt
    finished_signal = Signal(list)        # list[ScriptConflict]

    def __init__(self, scanner: ScriptScanner, parent: QWidget | None = None):
        super().__init__(parent)
        self._scanner = scanner

    def run(self) -> None:
        def cb(current: int, total: int) -> None:
            if self.isInterruptionRequested():
                return
            self.progress.emit(current, total)

        results = self._scanner.scan(progress_callback=cb)
        if not self.isInterruptionRequested():
            self.finished_signal.emit(results)


class _AutoMergeWorker(QThread):
    """Fuehrt Batch-Auto-Merge im Hintergrund aus."""

    progress = Signal(int, int)           # aktuell, gesamt
    finished_signal = Signal(list)        # list[MergeResult]

    def __init__(self, merger: ScriptMerger, conflicts: list[ScriptConflict],
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._merger = merger
        self._conflicts = conflicts

    def run(self) -> None:
        def cb(current: int, total: int) -> None:
            if self.isInterruptionRequested():
                return
            self.progress.emit(current, total)

        results = self._merger.auto_merge_all(
            self._conflicts, progress_callback=cb,
        )
        if not self.isInterruptionRequested():
            self.finished_signal.emit(results)


# ---------------------------------------------------------------------------
# Hauptdialog
# ---------------------------------------------------------------------------

class ScriptMergerDialog(QDialog):
    """Dialog zum Scannen und Auto-Mergen von Witcher-3-Script-Konflikten.

    Layout:
        Oben:    Info-Zeile (Vanilla-Dir, aktive Mods)
        Mitte:   Splitter — links Konflikt-Liste, rechts Detail-Panel
        Unten:   Aktions-Buttons + Fortschrittsbalken
    """

    def __init__(
        self,
        parent: QWidget | None,
        vanilla_scripts_dir: Path,
        mods_dir: Path,
        active_mod_names: list[str],
        profiles_dir: Path,
        instance_path: Path,
    ):
        super().__init__(parent)
        self._vanilla_dir = vanilla_scripts_dir
        self._mods_dir = mods_dir
        self._active_mods = active_mod_names
        self._profiles_dir = profiles_dir
        self._instance_path = instance_path

        self._conflicts: list[ScriptConflict] = []
        self._has_changes = False
        self._scan_worker: _ScanWorker | None = None
        self._merge_worker: _AutoMergeWorker | None = None
        self._inventory = MergeInventory(instance_path / ".merge_inventory.json")
        self._inventory.load()
        self._merger = ScriptMerger()
        self._kdiff3_process: QProcess | None = None
        self._kdiff3_conflict: ScriptConflict | None = None
        self._kdiff3_output_path: Path | None = None

        self._setup_ui()
        self._connect_signals()
        self._update_buttons()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Baut die gesamte Dialog-Oberflaeche auf."""
        self.setWindowTitle(tr("script_merger.title"))
        self.resize(900, 600)
        self.setMinimumSize(700, 400)

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)

        # -- Info-Zeile ---------------------------------------------------
        self._info_label = QLabel(
            tr(
                "script_merger.info",
                vanilla_dir=str(self._vanilla_dir),
                active_count=len(self._active_mods),
            )
        )
        self._info_label.setWordWrap(True)
        root.addWidget(self._info_label)

        # -- Splitter (Konflikt-Liste | Detail-Panel) ---------------------
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Links: Konflikt-Liste
        self._conflict_list = QListWidget()
        self._conflict_list.setMinimumWidth(200)
        self._splitter.addWidget(self._conflict_list)

        # Rechts: Detail-Panel (monospace, read-only)
        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        mono_font = QFont("Monospace")
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self._detail_text.setFont(mono_font)
        self._splitter.addWidget(self._detail_text)

        self._splitter.setStretchFactor(0, 4)
        self._splitter.setStretchFactor(1, 6)
        root.addWidget(self._splitter, 1)

        # -- Button-Zeilen ------------------------------------------------
        btn_row_1 = QHBoxLayout()
        btn_row_1.setSpacing(6)

        self._scan_btn = QPushButton(tr("script_merger.scan"))
        self._merge_btn = QPushButton(tr("script_merger.auto_merge"))
        self._merge_all_btn = QPushButton(tr("script_merger.merge_all"))

        self._kdiff3_btn = QPushButton(tr("script_merger.kdiff3"))

        btn_row_1.addWidget(self._scan_btn)
        btn_row_1.addWidget(self._merge_btn)
        btn_row_1.addWidget(self._merge_all_btn)
        btn_row_1.addWidget(self._kdiff3_btn)
        btn_row_1.addStretch()
        root.addLayout(btn_row_1)

        btn_row_2 = QHBoxLayout()
        btn_row_2.setSpacing(6)

        self._create_mod_btn = QPushButton(tr("script_merger.create_mod"))
        self._cleanup_btn = QPushButton(tr("script_merger.cleanup"))
        self._ignore_btn = QPushButton(tr("script_merger.ignore"))
        self._close_btn = QPushButton(tr("script_merger.close"))

        btn_row_2.addWidget(self._create_mod_btn)
        btn_row_2.addWidget(self._cleanup_btn)
        btn_row_2.addWidget(self._ignore_btn)
        btn_row_2.addStretch()
        btn_row_2.addWidget(self._close_btn)
        root.addLayout(btn_row_2)

        # -- Fortschrittsbalken -------------------------------------------
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setTextVisible(True)
        root.addWidget(self._progress_bar)

    # ------------------------------------------------------------------
    # Signal-Verbindungen
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Verbindet Buttons und Liste mit Slots."""
        self._scan_btn.clicked.connect(lambda checked=False: self._on_scan())
        self._merge_btn.clicked.connect(lambda checked=False: self._on_auto_merge())
        self._merge_all_btn.clicked.connect(lambda checked=False: self._on_auto_merge_all())
        self._create_mod_btn.clicked.connect(lambda checked=False: self._on_create_merge_mod())
        self._cleanup_btn.clicked.connect(lambda checked=False: self._on_cleanup())
        self._ignore_btn.clicked.connect(lambda checked=False: self._on_ignore())
        self._kdiff3_btn.clicked.connect(lambda checked=False: self._on_kdiff3())
        self._close_btn.clicked.connect(self.close)
        self._conflict_list.currentItemChanged.connect(self._on_conflict_selected)

    # ------------------------------------------------------------------
    # Slots — Scan
    # ------------------------------------------------------------------

    def _on_scan(self) -> None:
        """Startet den Script-Scan im Hintergrund-Thread."""
        settings = QSettings()
        check_scripts = settings.value("ScriptMerger/check_scripts", True, type=bool)
        check_xml = settings.value("ScriptMerger/check_xml", True, type=bool)
        scanner = ScriptScanner(self._vanilla_dir, self._mods_dir, self._active_mods,
                                check_scripts=check_scripts, check_xml=check_xml)
        self._scan_worker = _ScanWorker(scanner, self)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished_signal.connect(self._on_scan_finished)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._scan_btn.setEnabled(False)
        self._scan_worker.start()

    def _on_scan_progress(self, current: int, total: int) -> None:
        """Aktualisiert den Fortschrittsbalken waehrend des Scans."""
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(current)
        self._progress_bar.setFormat(
            tr("script_merger.scanning", current=current, total=total)
        )

    def _on_scan_finished(self, conflicts: list[ScriptConflict]) -> None:
        """Verarbeitet die Scan-Ergebnisse."""
        self._conflicts = conflicts
        self._progress_bar.setVisible(False)
        self._scan_btn.setEnabled(True)

        # Inventar anwenden: IGNORED-Status wiederherstellen
        ignored = self._inventory.get_ignored()
        for c in self._conflicts:
            if c.relative_path in ignored:
                c.merge_status = MergeStatus.IGNORED

        # Veraltete Merges pruefen
        stale = self._inventory.validate(self._conflicts)
        if stale:
            stale_list = "\n".join(f"  - {s}" for s in stale)
            QMessageBox.warning(
                self,
                tr("script_merger.title"),
                tr("script_merger.stale_merges", count=len(stale), files=stale_list),
            )

        # Liste fuellen
        self._populate_conflict_list()

        if not conflicts:
            QMessageBox.information(
                self,
                tr("script_merger.title"),
                tr("script_merger.no_conflicts"),
            )

        self._update_buttons()

    # ------------------------------------------------------------------
    # Slots — Konflikt-Auswahl
    # ------------------------------------------------------------------

    def _on_conflict_selected(self, current: QListWidgetItem | None,
                              previous: QListWidgetItem | None) -> None:
        """Zeigt Details des ausgewaehlten Konflikts im rechten Panel."""
        if current is None:
            self._detail_text.clear()
            self._update_buttons()
            return

        idx = self._conflict_list.row(current)
        if idx < 0 or idx >= len(self._conflicts):
            self._detail_text.clear()
            self._update_buttons()
            return

        conflict = self._conflicts[idx]
        lines: list[str] = []

        # Datei-Info
        lines.append(tr("script_merger.detail_file", path=conflict.relative_path))
        lines.append(
            tr("script_merger.detail_status", status=conflict.merge_status.value)
        )
        lines.append("")

        # Beteiligte Mods
        lines.append(tr("script_merger.detail_mods"))
        lines.append("-" * 40)
        for mv in conflict.mod_versions:
            lines.append(
                tr(
                    "script_merger.detail_mod_entry",
                    anvil_name=mv.mod_name,
                    witcher_name=mv.witcher_mod_name,
                )
            )
            if mv.diff_hunks:
                for hunk in mv.diff_hunks:
                    lines.append(
                        tr(
                            "script_merger.detail_hunk",
                            start=hunk.start_line,
                            end=hunk.end_line,
                            vanilla_count=len(hunk.vanilla_lines),
                            mod_count=len(hunk.mod_lines),
                        )
                    )
            else:
                lines.append(tr("script_merger.detail_no_hunks"))
        lines.append("")

        # Vanilla-Info
        if conflict.vanilla_path is None:
            lines.append(tr("script_merger.detail_no_vanilla"))
        else:
            lines.append(
                tr("script_merger.detail_vanilla", path=str(conflict.vanilla_path))
            )

        self._detail_text.setPlainText("\n".join(lines))
        self._update_buttons()

    # ------------------------------------------------------------------
    # Slots — Merge (einzeln)
    # ------------------------------------------------------------------

    def _on_auto_merge(self) -> None:
        """Fuehrt Auto-Merge fuer den ausgewaehlten Konflikt durch."""
        idx = self._conflict_list.currentRow()
        if idx < 0 or idx >= len(self._conflicts):
            return

        conflict = self._conflicts[idx]
        if conflict.merge_status != MergeStatus.AUTO_MERGEABLE:
            return

        try:
            result = self._merger.auto_merge(conflict)
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("script_merger.title"),
                tr("script_merger.merge_error", error=str(e)),
            )
            return

        if result.success:
            # Merged Content auf dem Conflict-Objekt speichern (dynamisch)
            conflict.merged_content = result.merged_content
            self._update_list_item(idx)
            # Detail-Panel aktualisieren
            self._on_conflict_selected(
                self._conflict_list.currentItem(), None,
            )
        else:
            QMessageBox.warning(
                self,
                tr("script_merger.title"),
                tr("script_merger.merge_failed", error=result.error_message),
            )

        self._update_buttons()

    # ------------------------------------------------------------------
    # Slots — Merge (alle)
    # ------------------------------------------------------------------

    def _on_auto_merge_all(self) -> None:
        """Startet Batch-Auto-Merge fuer alle AUTO_MERGEABLE Konflikte."""
        self._merge_worker = _AutoMergeWorker(
            self._merger, self._conflicts, self,
        )
        self._merge_worker.progress.connect(self._on_merge_progress)
        self._merge_worker.finished_signal.connect(self._on_merge_all_finished)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._merge_all_btn.setEnabled(False)
        self._merge_btn.setEnabled(False)
        self._merge_worker.start()

    def _on_merge_progress(self, current: int, total: int) -> None:
        """Aktualisiert den Fortschrittsbalken waehrend des Batch-Merge."""
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(current)
        self._progress_bar.setFormat(
            tr("script_merger.merging", current=current, total=total)
        )

    def _on_merge_all_finished(self, results: list[MergeResult]) -> None:
        """Verarbeitet die Batch-Merge-Ergebnisse."""
        self._progress_bar.setVisible(False)

        # Merged Content auf den Conflict-Objekten speichern
        for result in results:
            if result.success and result.merged_content is not None:
                result.conflict.merged_content = result.merged_content

        # Liste komplett neu aufbauen
        self._populate_conflict_list()

        # Zusammenfassung
        success_count = sum(1 for r in results if r.success)
        fail_count = sum(1 for r in results if not r.success)
        QMessageBox.information(
            self,
            tr("script_merger.title"),
            tr(
                "script_merger.merge_all_done",
                success=success_count,
                failed=fail_count,
            ),
        )

        self._update_buttons()

    # ------------------------------------------------------------------
    # Slots — Merge-Mod erstellen
    # ------------------------------------------------------------------

    def _on_create_merge_mod(self) -> None:
        """Erstellt den _merged_-Mod mit allen gemergten Dateien."""
        merged_dir = self._mods_dir / "_merged_" / "mods" / "mod0000_MergedFiles"

        merged_count = 0
        for conflict in self._conflicts:
            if conflict.merge_status != MergeStatus.MERGED:
                continue
            content = conflict.merged_content
            if content is None:
                continue
            # XML-Konflikte haben "xml/" Prefix → nach content/ (ohne scripts/)
            if conflict.relative_path.startswith("xml/"):
                target = merged_dir / "content" / conflict.relative_path[4:]
            else:
                target = merged_dir / "content" / "scripts" / conflict.relative_path
            try:
                write_script_file(target, content)
                merged_count += 1
            except OSError as e:
                QMessageBox.warning(
                    self,
                    tr("script_merger.title"),
                    tr("script_merger.write_error", path=str(target), error=str(e)),
                )
                return

        if merged_count == 0:
            QMessageBox.information(
                self,
                tr("script_merger.title"),
                tr("script_merger.nothing_to_write"),
            )
            return

        # modlist.txt aktualisieren: _merged_ an Position 0
        try:
            from anvil.core.mod_list_io import (
                read_global_modlist,
                write_global_modlist,
                read_active_mods,
                write_active_mods,
            )

            order = read_global_modlist(self._profiles_dir)
            order = [n for n in order if n != "_merged_"]
            order.insert(0, "_merged_")
            write_global_modlist(self._profiles_dir, order)

            # In ALLEN Profilen aktivieren
            for profile_dir in self._profiles_dir.iterdir():
                if profile_dir.is_dir():
                    active = read_active_mods(profile_dir)
                    active.add("_merged_")
                    write_active_mods(profile_dir, active)
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("script_merger.title"),
                tr("script_merger.modlist_error", error=str(e)),
            )
            return

        # Inventar aktualisieren und speichern
        self._record_merges()
        self._inventory.save()
        self._has_changes = True

        QMessageBox.information(
            self,
            tr("script_merger.title"),
            tr("script_merger.mod_created", count=merged_count),
        )

    def _record_merges(self) -> None:
        """Erzeugt MergeInventoryEntry fuer jeden MERGED-Konflikt und speichert."""
        now = datetime.now(timezone.utc).isoformat()
        for conflict in self._conflicts:
            if conflict.merge_status != MergeStatus.MERGED:
                continue
            source_hashes: dict[str, str] = {}
            if conflict.vanilla_path is not None:
                source_hashes["vanilla"] = file_hash(conflict.vanilla_path)
            for mv in conflict.mod_versions:
                source_hashes[mv.mod_name] = mv.file_hash
            merged_base = (
                self._mods_dir / "_merged_" / "mods" / "mod0000_MergedFiles"
            )
            if conflict.relative_path.startswith("xml/"):
                merged_path = merged_base / "content" / conflict.relative_path[4:]
            else:
                merged_path = merged_base / "content" / "scripts" / conflict.relative_path
            merged_h = file_hash(merged_path) if merged_path.is_file() else ""
            entry = MergeInventoryEntry(
                relative_path=conflict.relative_path,
                mods=[mv.mod_name for mv in conflict.mod_versions],
                method="auto",
                timestamp=now,
                source_hashes=source_hashes,
                merged_hash=merged_h,
            )
            self._inventory.add_merge(entry)

    # ------------------------------------------------------------------
    # Slots — Aufraeumen
    # ------------------------------------------------------------------

    def _on_cleanup(self) -> None:
        """Loescht den _merged_-Mod, Inventar und setzt alle Konflikte zurueck."""
        reply = QMessageBox.question(
            self,
            tr("script_merger.cleanup_title"),
            tr("script_merger.cleanup_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # _merged_-Ordner loeschen
        merged_path = self._mods_dir / "_merged_"
        if merged_path.exists():
            try:
                shutil.rmtree(merged_path)
            except OSError as e:
                QMessageBox.warning(
                    self,
                    tr("script_merger.title"),
                    tr("script_merger.cleanup_error", error=str(e)),
                )
                return

        # Aus modlist.txt und active_mods.json aller Profile entfernen
        try:
            from anvil.core.mod_list_io import remove_mod_globally
            remove_mod_globally(self._profiles_dir, "_merged_")
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("script_merger.title"),
                tr("script_merger.modlist_error", error=str(e)),
            )

        # Inventar loeschen
        self._inventory.clear()
        inv_path = self._instance_path / ".merge_inventory.json"
        inv_path.unlink(missing_ok=True)

        self._has_changes = True

        # Alle Konflikte zuruecksetzen
        for c in self._conflicts:
            c.merge_status = MergeStatus.UNSCANNED
            c.merged_content = None

        self._populate_conflict_list()
        self._update_buttons()

    # ------------------------------------------------------------------
    # Slots — Ignorieren
    # ------------------------------------------------------------------

    def _on_ignore(self) -> None:
        """Toggled IGNORED/UNSCANNED fuer den ausgewaehlten Konflikt."""
        idx = self._conflict_list.currentRow()
        if idx < 0 or idx >= len(self._conflicts):
            return

        conflict = self._conflicts[idx]
        if conflict.merge_status == MergeStatus.IGNORED:
            # Zuruecksetzen — Vanilla pruefen um korrekten Status zu setzen
            conflict.merge_status = MergeStatus.UNSCANNED
            self._inventory.unset_ignored(conflict.relative_path)
        else:
            conflict.merge_status = MergeStatus.IGNORED
            self._inventory.set_ignored(conflict.relative_path)

        self._inventory.save()
        self._update_list_item(idx)
        self._on_conflict_selected(self._conflict_list.currentItem(), None)
        self._update_buttons()

    # ------------------------------------------------------------------
    # Helfer — Liste
    # ------------------------------------------------------------------

    def _populate_conflict_list(self) -> None:
        """Fuellt die Konflikt-Liste mit allen gefundenen Konflikten."""
        self._conflict_list.clear()
        icons = _get_icons()
        for conflict in self._conflicts:
            item = QListWidgetItem()
            item.setText(conflict.relative_path)
            icon = icons.get(conflict.merge_status)
            if icon:
                item.setIcon(icon)
            # Status als Tooltip
            item.setToolTip(
                tr("script_merger.tooltip_status", status=conflict.merge_status.value)
            )
            self._conflict_list.addItem(item)

    def _update_list_item(self, idx: int) -> None:
        """Aktualisiert Icon und Tooltip eines einzelnen Listen-Eintrags."""
        if idx < 0 or idx >= self._conflict_list.count():
            return
        item = self._conflict_list.item(idx)
        if item is None:
            return
        conflict = self._conflicts[idx]
        icons = _get_icons()
        icon = icons.get(conflict.merge_status)
        if icon:
            item.setIcon(icon)
        item.setToolTip(
            tr("script_merger.tooltip_status", status=conflict.merge_status.value)
        )

    # ------------------------------------------------------------------
    # Helfer — Button-Zustand
    # ------------------------------------------------------------------

    def _update_buttons(self) -> None:
        """Aktiviert/deaktiviert Buttons basierend auf dem aktuellen Zustand."""
        has_selected = self._conflict_list.currentRow() >= 0
        selected_conflict: ScriptConflict | None = None
        if has_selected:
            idx = self._conflict_list.currentRow()
            if 0 <= idx < len(self._conflicts):
                selected_conflict = self._conflicts[idx]

        has_mergeable = any(
            c.merge_status == MergeStatus.AUTO_MERGEABLE for c in self._conflicts
        )
        has_merged = any(
            c.merge_status == MergeStatus.MERGED for c in self._conflicts
        )

        # Merge-Button: nur wenn ausgewaehlt UND AUTO_MERGEABLE
        self._merge_btn.setEnabled(
            selected_conflict is not None
            and selected_conflict.merge_status == MergeStatus.AUTO_MERGEABLE
        )
        self._merge_all_btn.setEnabled(has_mergeable)
        self._create_mod_btn.setEnabled(has_merged)
        self._cleanup_btn.setEnabled(True)
        self._ignore_btn.setEnabled(has_selected)

        # KDiff3: nur bei CONFLICT oder AUTO_MERGEABLE und wenn kein KDiff3 laeuft
        kdiff3_running = (
            self._kdiff3_process is not None
            and self._kdiff3_process.state() != QProcess.ProcessState.NotRunning
        )
        self._kdiff3_btn.setEnabled(
            selected_conflict is not None
            and selected_conflict.merge_status in (MergeStatus.CONFLICT, MergeStatus.AUTO_MERGEABLE)
            and not kdiff3_running
        )

    # ------------------------------------------------------------------
    # Oeffentliche Eigenschaft
    # ------------------------------------------------------------------

    @property
    def has_changes(self) -> bool:
        """True wenn Aenderungen gemacht wurden (Merge-Mod erstellt/geloescht)."""
        return self._has_changes

    # ------------------------------------------------------------------
    # Slots — KDiff3
    # ------------------------------------------------------------------

    def _on_kdiff3(self) -> None:
        """Oeffnet den ausgewaehlten Konflikt in KDiff3 fuer manuellen 3-Way-Merge."""
        idx = self._conflict_list.currentRow()
        if idx < 0 or idx >= len(self._conflicts):
            return

        conflict = self._conflicts[idx]
        if conflict.merge_status not in (MergeStatus.CONFLICT, MergeStatus.AUTO_MERGEABLE):
            return

        # KDiff3-Pfad aus Settings
        settings = QSettings()
        kdiff3_path = settings.value("ScriptMerger/kdiff3_path", "kdiff3", type=str)

        # Pruefen ob kdiff3 existiert
        import shutil as _shutil
        resolved = _shutil.which(kdiff3_path)
        if resolved is None and not Path(kdiff3_path).is_file():
            QMessageBox.warning(
                self, tr("script_merger.title"),
                tr("script_merger.kdiff3_not_found"),
            )
            return

        # Warnung bei >2 Mods
        if len(conflict.mod_versions) > 2:
            QMessageBox.information(
                self, tr("script_merger.title"),
                tr("script_merger.kdiff3_too_many_mods"),
            )

        # Temp-Dateien erstellen
        from anvil.core.script_merger.ws_codec import read_script_file
        tmp_dir = Path(tempfile.mkdtemp(prefix="anvil_merge_"))

        files = []
        # Vanilla
        if conflict.vanilla_path is not None:
            vanilla_tmp = tmp_dir / "vanilla.ws"
            vanilla_tmp.write_text(read_script_file(conflict.vanilla_path), encoding="utf-8")
            files.append(str(vanilla_tmp))

        # Mod-Versionen (max 2 fuer KDiff3)
        for i, mv in enumerate(conflict.mod_versions[:2]):
            mod_tmp = tmp_dir / f"mod{i}_{mv.mod_name}.ws"
            mod_tmp.write_text(read_script_file(mv.file_path), encoding="utf-8")
            files.append(str(mod_tmp))

        # Output
        output_path = tmp_dir / "merged_output.ws"

        self._kdiff3_conflict = conflict
        self._kdiff3_output_path = output_path
        self._kdiff3_btn.setEnabled(False)
        self._kdiff3_btn.setText(tr("script_merger.kdiff3_running"))

        # QProcess starten
        self._kdiff3_process = QProcess(self)
        self._kdiff3_process.finished.connect(self._on_kdiff3_finished)

        args = files + ["-o", str(output_path)]
        effective_path = resolved or kdiff3_path
        self._kdiff3_process.start(effective_path, args)

    def _on_kdiff3_finished(self, exit_code: int, exit_status) -> None:
        """Callback wenn KDiff3 beendet wird."""
        self._kdiff3_btn.setText(tr("script_merger.kdiff3"))
        self._kdiff3_btn.setEnabled(True)

        if self._kdiff3_output_path is None or self._kdiff3_conflict is None:
            return

        if self._kdiff3_output_path.is_file() and self._kdiff3_output_path.stat().st_size > 0:
            # Ergebnis einlesen
            merged_text = self._kdiff3_output_path.read_text(encoding="utf-8")
            self._kdiff3_conflict.merged_content = merged_text
            self._kdiff3_conflict.merge_status = MergeStatus.MERGED

            # Liste aktualisieren
            idx = self._conflicts.index(self._kdiff3_conflict)
            self._update_list_item(idx)
            self._on_conflict_selected(self._conflict_list.currentItem(), None)

            QMessageBox.information(
                self, tr("script_merger.title"),
                tr("script_merger.kdiff3_finished"),
            )
        else:
            QMessageBox.information(
                self, tr("script_merger.title"),
                tr("script_merger.kdiff3_no_output"),
            )

        # Temp-Dateien aufraeumen
        import shutil as _shutil
        tmp_dir = self._kdiff3_output_path.parent
        _shutil.rmtree(tmp_dir, ignore_errors=True)

        self._kdiff3_conflict = None
        self._kdiff3_output_path = None
        self._update_buttons()

    # ------------------------------------------------------------------
    # closeEvent
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Beendet laufende Worker-Threads und KDiff3 sauber beim Schliessen."""
        for worker in (self._scan_worker, self._merge_worker):
            if worker is not None and worker.isRunning():
                worker.requestInterruption()
                worker.wait(3000)
        if self._kdiff3_process is not None and self._kdiff3_process.state() != QProcess.ProcessState.NotRunning:
            self._kdiff3_process.kill()
            self._kdiff3_process.waitForFinished(2000)
        super().closeEvent(event)
