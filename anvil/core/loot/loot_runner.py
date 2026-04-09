"""LOOT process runner — starts LOOT binary and captures output.

LOOT GUI mode: launches LOOT with --auto-sort, user applies in LOOT GUI,
Anvil re-reads plugins.txt after LOOT closes.
Supports native binary and Flatpak wrapper.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QSettings, Signal

from anvil.core.subprocess_env import clean_subprocess_env

_TAG = "[LootRunner]"


def find_loot_binary() -> str | None:
    """Resolve the LOOT binary path from settings or system PATH.

    Priority:
      1. User-configured path in QSettings
      2. 'loot' in $PATH (AUR install)
      3. Flatpak wrapper command
    """
    settings = QSettings()
    user_path = settings.value("LOOT/binary_path", "", type=str)
    if user_path:
        # Could be a direct path or a command like "flatpak run ..."
        if Path(user_path).is_file() or user_path.startswith("flatpak"):
            return user_path

    # Try system PATH
    system_loot = shutil.which("loot")
    if system_loot:
        return system_loot

    # Try Flatpak
    flatpak = shutil.which("flatpak")
    if flatpak:
        # Check if LOOT flatpak is installed
        import subprocess
        try:
            result = subprocess.run(
                ["flatpak", "info", "io.github.loot.loot"],
                capture_output=True, timeout=5,
                env=clean_subprocess_env(),
            )
            if result.returncode == 0:
                return "flatpak run io.github.loot.loot"
        except (OSError, subprocess.TimeoutExpired):
            pass

    return None


class LootRunner(QObject):
    """Async LOOT process wrapper using QProcess.

    Launches LOOT GUI with --auto-sort. User sorts and applies in LOOT,
    then closes it. Anvil detects process exit and re-reads plugins.txt.

    Signals:
        output_line(str)    — stdout/stderr line for progress display
        finished_ok(str)    — empty string on normal exit (user applied in LOOT)
        finished_error(str) — error message on failure
    """

    output_line = Signal(str)
    finished_ok = Signal(str)
    finished_error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None

    @property
    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    def start(
        self,
        loot_game_name: str,
        game_path: Path,
    ) -> None:
        """Start LOOT GUI with auto-sort.

        Args:
            loot_game_name: LOOT --game value (e.g. "Skyrim Special Edition")
            game_path: Absolute path to the game installation directory
        """
        binary = find_loot_binary()
        if not binary:
            self.finished_error.emit(
                "LOOT nicht gefunden. Bitte in Einstellungen konfigurieren."
            )
            return

        # Build argument list — only options LOOT actually supports
        # Do NOT pass --game-path: LOOT stores paths in its own settings.toml
        # and --game-path override can fail ("failed to override game path").
        args = [
            "--game", loot_game_name,
            "--auto-sort",
        ]

        self._process = QProcess(self)
        # Clean LD_LIBRARY_PATH for AppImage compatibility
        qenv = QProcessEnvironment.systemEnvironment()
        orig = os.environ.get("LD_LIBRARY_PATH_ORIG")
        if orig is not None:
            qenv.insert("LD_LIBRARY_PATH", orig)
        elif qenv.contains("LD_LIBRARY_PATH"):
            qenv.remove("LD_LIBRARY_PATH")
        self._process.setProcessEnvironment(qenv)
        self._process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.finished.connect(self._on_finished)

        # Handle "flatpak run ..." as split command
        # Grant filesystem access so LOOT can reach game paths on /mnt, /run etc.
        if binary.startswith("flatpak"):
            parts = binary.split()
            program = parts[0]  # "flatpak"
            run_args = parts[1:]  # ["run", "io.github.loot.loot"]
            if "run" in run_args:
                idx = run_args.index("run") + 1
                # host covers ~, /run/media; add /mnt explicitly for mount points
                run_args.insert(idx, "--filesystem=host")
                run_args.insert(idx + 1, "--filesystem=/mnt")
            args = run_args + args
        else:
            program = binary

        print(f"{_TAG} Starting: {program} {' '.join(args)}")
        self._process.start(program, args)

    def kill(self) -> None:
        """Terminate the running LOOT process."""
        if self._process and self.is_running:
            self._process.kill()
            print(f"{_TAG} Process killed")

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        data = self._process.readAllStandardOutput().data()
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = str(data)
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                self.output_line.emit(stripped)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if exit_status == QProcess.ExitStatus.CrashExit:
            self.finished_error.emit("LOOT-Prozess abgestuerzt.")
            return

        if exit_code != 0:
            err = ""
            if self._process:
                err = (
                    self._process.readAllStandardError()
                    .data()
                    .decode("utf-8", errors="replace")
                    .strip()
                )
            self.finished_error.emit(
                f"LOOT beendet mit Code {exit_code}"
                + (f":\n{err}" if err else "")
            )
            return

        # LOOT closed normally — user sorted and applied in LOOT GUI
        self.finished_ok.emit("")
