"""Clean subprocess environment for PyInstaller/AppImage builds.

PyInstaller sets LD_LIBRARY_PATH to its _internal/ directory at startup.
Child processes (xdg-open, flatpak, git, 7z, etc.) inherit this and load
bundled libs instead of system libs, causing crashes and symbol errors.

This module provides helpers to restore the original environment before
spawning child processes.
"""

from __future__ import annotations

import os


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
