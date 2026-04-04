"""Persistent column-width helper for QHeaderView.

Hooks into ``sectionResized`` so every user resize is saved automatically.
Avoids Qt's ``saveState()``/``restoreState()`` which store the *current*
width of a stretched last column instead of the user-chosen width
(see Qt bug QTBUG-52436).

Writes are debounced (300 ms) so dragging a column border produces at most
one disk write instead of hundreds.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QHeaderView

_DEBOUNCE_MS = 300


def _settings() -> QSettings:
    path = str(Path.home() / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf")
    return QSettings(path, QSettings.Format.IniFormat)


class PersistentHeader:
    """Track and persist column widths for a single QHeaderView.

    Parameters
    ----------
    header:
        The QHeaderView to track.
    settings_key:
        Unique key in QSettings, e.g. ``"modlist"`` or ``"bg3_active"``.
        Widths are stored under ``<key>/column_widths``.
    fixed_columns:
        Column indices whose width is fixed (e.g. checkbox columns).
        These are saved/restored but resize events from them are
        still recorded.
    """

    def __init__(
        self,
        header: QHeaderView,
        settings_key: str,
        fixed_columns: frozenset[int] | None = None,
    ) -> None:
        self._header = header
        self._key = settings_key
        self._fixed = fixed_columns or frozenset()
        self._restoring = False

        # Debounce timer — fires once after the last resize event settles
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._write_widths)

        header.sectionResized.connect(self._on_section_resized)

    # ── live save (debounced) ─────────────────────────────────────

    def _on_section_resized(self, logical_index: int, _old: int, _new: int) -> None:
        if self._restoring:
            return

        # Don't save the stretched last column — its width is layout-dependent
        if (self._header.stretchLastSection()
                and logical_index == self._header.count() - 1):
            return

        # (Re)start the debounce timer; the actual write happens in
        # _write_widths once the user stops dragging for _DEBOUNCE_MS.
        self._save_timer.start()

    def _write_widths(self) -> None:
        """Snapshot all non-stretch column widths to QSettings."""
        h = self._header
        widths: list[int] = []
        last = h.count() - 1
        for i in range(h.count()):
            if h.stretchLastSection() and i == last:
                widths.append(-1)          # sentinel: "let Qt stretch"
            else:
                widths.append(h.sectionSize(i))
        s = _settings()
        s.setValue(f"{self._key}/column_widths", widths)

    def flush(self) -> None:
        """Force any pending debounced write to disk immediately.

        Call this from ``closeEvent`` so no resize is lost on shutdown.
        """
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._write_widths()

    # ── restore ────────────────────────────────────────────────────

    def restore(self) -> bool:
        """Apply previously saved widths.  Returns True if widths existed."""
        s = _settings()
        raw = s.value(f"{self._key}/column_widths")
        if not raw:
            return False

        widths: list[int]
        if isinstance(raw, list):
            widths = [int(v) for v in raw]
        else:
            return False

        h = self._header
        if not widths or len(widths) != h.count():
            return False            # column count changed — ignore stale data

        self._restoring = True
        try:
            for i, w in enumerate(widths):
                if w == -1:
                    continue        # stretch sentinel — leave alone
                if i < h.count():
                    h.resizeSection(i, w)
        finally:
            self._restoring = False
        return True
