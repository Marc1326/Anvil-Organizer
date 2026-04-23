"""Clean subprocess environment for PyInstaller/AppImage/Flatpak builds.

PyInstaller sets LD_LIBRARY_PATH to its _internal/ directory at startup.
Child processes (xdg-open, flatpak, git, 7z, etc.) inherit this and load
bundled libs instead of system libs, causing crashes and symbol errors.

Flatpak sandboxes isolate the app from host binaries (steam, loot, proton).
Use flatpak-spawn --host to break out and call host programs.

This module provides helpers to restore the original environment before
spawning child processes.
"""

from __future__ import annotations

import os
import shutil


def is_flatpak() -> bool:
    """Return True if running inside a Flatpak sandbox."""
    return os.path.isfile("/.flatpak-info")


def host_which(binary: str) -> str | None:
    """Find a binary, checking the host system if inside Flatpak."""
    if not is_flatpak():
        return shutil.which(binary)
    # In Flatpak: check sandbox first, then ask host
    found = shutil.which(binary)
    if found:
        return found
    import subprocess
    try:
        result = subprocess.run(
            ["flatpak-spawn", "--host", "which", binary],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def host_popen(cmd: list[str], **kwargs) -> "subprocess.Popen":
    """Popen wrapper that uses flatpak-spawn --host inside Flatpak.

    When inside Flatpak and ``env`` is provided, each variable is forwarded
    to the host process via ``--env=KEY=VALUE``. Without this, tools like
    Proton see a minimal host environment and fail with errors like
    "No compat data path?" because STEAM_COMPAT_* is missing.
    """
    import subprocess
    if is_flatpak():
        spawn = ["flatpak-spawn", "--host"]
        env = kwargs.get("env")
        if env is not None:
            for k, v in env.items():
                spawn.append(f"--env={k}={v}")
        cmd = spawn + cmd
    return subprocess.Popen(cmd, **kwargs)


def clean_subprocess_env() -> dict[str, str]:
    """Return env dict with LD_LIBRARY_PATH restored to pre-PyInstaller state.

    PyInstaller saves the original value as LD_LIBRARY_PATH_ORIG.
    If that exists, restore it.  Otherwise remove LD_LIBRARY_PATH entirely.
    """
    env = os.environ.copy()
    orig = env.get("LD_LIBRARY_PATH_ORIG")
    if orig is not None:
        env["LD_LIBRARY_PATH"] = orig
    elif "LD_LIBRARY_PATH" in env:
        del env["LD_LIBRARY_PATH"]
    return env


def clean_env(env: dict[str, str]) -> dict[str, str]:
    """Clean LD_LIBRARY_PATH in an existing env dict (e.g. for Wine/Proton).

    Same logic as clean_subprocess_env() but operates on a provided dict
    instead of os.environ.
    """
    orig = os.environ.get("LD_LIBRARY_PATH_ORIG")
    if orig is not None:
        env["LD_LIBRARY_PATH"] = orig
    elif "LD_LIBRARY_PATH" in env:
        del env["LD_LIBRARY_PATH"]
    return env
