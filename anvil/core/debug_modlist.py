"""Debug-Logging für modlist.txt und GUI-Model Analyse.

Schreibt nach /tmp/anvil_modlist_debug.log mit Timestamps.
Entfernen: grep -r "debug_modlist" anvil/ und diese Datei löschen.
"""

from __future__ import annotations

import time
import traceback
from pathlib import Path

_LOG_PATH = Path("/tmp/anvil_modlist_debug.log")
_start_time = time.monotonic()


def _init_log() -> None:
    """Log-Datei beim ersten Aufruf leeren und Header schreiben."""
    global _initialized
    if not getattr(_init_log, "_done", False):
        _LOG_PATH.write_text(
            f"=== Anvil Modlist Debug Log — gestartet {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n\n",
            encoding="utf-8",
        )
        _init_log._done = True


def _ts() -> str:
    """Relative Sekunden seit App-Start."""
    return f"[{time.monotonic() - _start_time:8.3f}s]"


def _caller() -> str:
    """Aufrufer (2 Frames hoch) für Kontext."""
    frame = traceback.extract_stack(limit=3)[0]
    return f"{Path(frame.filename).name}:{frame.lineno} {frame.name}"


def log(tag: str, message: str) -> None:
    """Eine Zeile ins Debug-Log schreiben."""
    _init_log()
    line = f"{_ts()} [{tag}] {message}\n"
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)


def log_modlist_write(caller: str, profiles_dir, mod_names: list[str]) -> None:
    """Kompletten modlist.txt-Inhalt nach Write loggen."""
    _init_log()
    seps = [n for n in mod_names if n.endswith("_separator")]
    mods = [n for n in mod_names if not n.endswith("_separator")]
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n{_ts()} [MODLIST_WRITE] caller={caller}\n")
        f.write(f"  path={profiles_dir}/modlist.txt\n")
        f.write(f"  total={len(mod_names)} (seps={len(seps)}, mods={len(mods)})\n")
        f.write("  --- INHALT ---\n")
        for i, name in enumerate(mod_names):
            marker = " [SEP]" if name.endswith("_separator") else ""
            f.write(f"  {i:4d}: {name}{marker}\n")
        f.write("  --- ENDE ---\n\n")


def log_model_state(caller: str, rows) -> None:
    """Kompletten GUI-Model-State loggen (nach set_mods oder reload)."""
    _init_log()
    seps = [r for r in rows if r.is_separator]
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n{_ts()} [MODEL_STATE] caller={caller}\n")
        f.write(f"  total_rows={len(rows)} (separators={len(seps)})\n")
        f.write("  --- ROWS ---\n")
        current_sep = "(kein Trenner)"
        for i, r in enumerate(rows):
            if r.is_separator:
                current_sep = r.folder_name
                f.write(f"  {i:4d}: [SEP] {r.name} (folder={r.folder_name})\n")
            else:
                f.write(f"  {i:4d}:       {r.name} (folder={r.folder_name}, enabled={r.enabled}) -> {current_sep}\n")
        f.write("  --- ENDE ---\n\n")


def log_separator_filter(caller: str, collapsed: set, hidden: set, total_rows: int) -> None:
    """Hidden-Rows und Collapsed-Separatoren loggen."""
    _init_log()
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n{_ts()} [SEP_FILTER] caller={caller}\n")
        f.write(f"  total_rows={total_rows}\n")
        f.write(f"  collapsed_separators ({len(collapsed)}): {sorted(collapsed)}\n")
        f.write(f"  hidden_rows ({len(hidden)}): {sorted(hidden)}\n\n")


def log_install_step(archive_name: str, mod_name: str, step: str, details: str = "") -> None:
    """Einen Install-Schritt loggen."""
    _init_log()
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{_ts()} [INSTALL] archive={archive_name} mod={mod_name} step={step}")
        if details:
            f.write(f" | {details}")
        f.write("\n")
