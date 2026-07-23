"""Activity-Log fuer wichtige User-Aktionen — Bug-Analyse-Helfer.

Schreibt in ``~/.anvil-organizer/logs/activity.log`` strukturierte Zeilen.
Wochentliche Rotation, max. 4 Wochen Aufbewahrung.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from anvil.core.base_dir import anvil_base_paths, configured_base_is_custom

_LOG_DIR = anvil_base_paths().logs
_LOG_FILE = _LOG_DIR / "activity.log"
_MAX_BACKUPS = 4
_ROTATE_AFTER_DAYS = 7


def _rotate_if_needed() -> None:
    """Rotate the active log if its first line is older than 7 days."""
    if not _LOG_FILE.is_file():
        return
    try:
        with _LOG_FILE.open("r", encoding="utf-8") as f:
            first = f.readline().strip()
        if not first:
            return
        ts = first.split("  ", 1)[0]
        first_dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        if datetime.now() - first_dt < timedelta(days=_ROTATE_AFTER_DAYS):
            return
    except (OSError, ValueError, IndexError):
        return

    for i in range(_MAX_BACKUPS, 0, -1):
        src = _LOG_FILE.with_suffix(f".log.{i}")
        if i == _MAX_BACKUPS and src.exists():
            try:
                src.unlink()
            except OSError:
                pass
            continue
        if src.exists():
            try:
                src.rename(_LOG_FILE.with_suffix(f".log.{i + 1}"))
            except OSError:
                pass
    try:
        _LOG_FILE.rename(_LOG_FILE.with_suffix(".log.1"))
    except OSError:
        pass


def log_action(category: str, message: str = "") -> None:
    """Append a line to the activity log. Never raises."""
    try:
        if configured_base_is_custom() and not _LOG_DIR.parent.is_dir():
            print(
                f"activity_log: configured base is unavailable: {_LOG_DIR.parent}",
                file=sys.stderr,
            )
            return
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts}  {category:<12} {message}\n"
        with _LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError as exc:
        print(f"activity_log: cannot write: {exc}", file=sys.stderr)
