"""Spiegelt stdout/stderr zusaetzlich in ``<base>/logs/debug.log``.

Beim Start ueber Menueeintrag, .desktop-Datei oder Flatpak gibt es kein
Terminal — dort landet jede print()-Ausgabe auf /dev/null und ist im
Fehlerfall verloren. Beim Start aus der Konsole bleibt die Ausgabe
zusaetzlich sichtbar.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_MAX_BYTES = 2 * 1024 * 1024
_MAX_BACKUPS = 2

_log_path: Path | None = None
_handle = None


def debug_log_path() -> Path | None:
    """Pfad der aktiven Logdatei, oder None wenn nicht aktiviert."""
    return _log_path


def _rotate(path: Path) -> None:
    try:
        if not path.is_file() or path.stat().st_size < _MAX_BYTES:
            return
    except OSError:
        return
    oldest = path.with_suffix(f".log.{_MAX_BACKUPS}")
    try:
        if oldest.exists():
            oldest.unlink()
    except OSError:
        pass
    for i in range(_MAX_BACKUPS - 1, 0, -1):
        src = path.with_suffix(f".log.{i}")
        if src.exists():
            try:
                src.rename(path.with_suffix(f".log.{i + 1}"))
            except OSError:
                pass
    try:
        path.rename(path.with_suffix(".log.1"))
    except OSError:
        pass


class _Tee:
    """Schreibt in den Originalstream und in die Logdatei."""

    def __init__(self, stream, handle) -> None:
        self._stream = stream
        self._handle = handle

    def write(self, data: str) -> int:
        if self._stream is not None:
            try:
                self._stream.write(data)
            except (OSError, ValueError):
                pass
        try:
            self._handle.write(data)
            self._handle.flush()
        except (OSError, ValueError):
            pass
        return len(data)

    def writelines(self, lines) -> None:
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        for target in (self._stream, self._handle):
            if target is None:
                continue
            try:
                target.flush()
            except (OSError, ValueError):
                pass

    @property
    def encoding(self) -> str:
        return getattr(self._stream, "encoding", None) or "utf-8"

    def isatty(self) -> bool:
        return bool(self._stream is not None and self._stream.isatty())

    def fileno(self) -> int:
        # Subprozesse erben weiterhin den echten Descriptor, nicht die Datei.
        if self._stream is None:
            raise OSError("no underlying stream")
        return self._stream.fileno()


def start_debug_log(version: str = "") -> Path | None:
    """stdout/stderr in die Logdatei spiegeln. Wirft nie."""
    global _log_path, _handle
    if _handle is not None:
        return _log_path
    try:
        from anvil.core.base_dir import anvil_base_paths
        log_dir = anvil_base_paths().logs
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "debug.log"
        _rotate(path)
        handle = path.open("a", encoding="utf-8", errors="replace")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"debug_log: cannot write: {exc}", file=sys.stderr)
        return None

    _log_path = path
    _handle = handle
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    handle.write(f"\n===== {stamp}  Anvil {version} =====\n")
    handle.flush()
    sys.stdout = _Tee(sys.__stdout__, handle)
    sys.stderr = _Tee(sys.__stderr__, handle)
    return path
