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


# Variables a PyInstaller/AppImage bundle points at its own _internal/ dir.
# Inherited by child processes (xdg-open, kde-open, gio, host programs) they
# cause symbol-lookup errors or silent failure. Each is restored from its
# *_ORIG backup if the bootloader saved one, otherwise removed.
_BUNDLE_ENV_VARS = (
    "LD_LIBRARY_PATH",
    "QT_PLUGIN_PATH",
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    "GTK_PATH",
    "GDK_PIXBUF_MODULE_FILE",
    "GDK_PIXBUF_MODULEDIR",
    "GIO_MODULE_DIR",
    "GSETTINGS_SCHEMA_DIR",
    "PYTHONPATH",
    "PYTHONHOME",
)


def _restore_or_delete(env: dict[str, str], key: str) -> None:
    orig = os.environ.get(f"{key}_ORIG")
    if orig is not None:
        env[key] = orig
    elif key in env:
        del env[key]


def clean_subprocess_env() -> dict[str, str]:
    """Return env dict with bundler-injected variables stripped.

    Only LD_LIBRARY_PATH gets an *_ORIG backup from the PyInstaller bootloader;
    the Qt/GTK/GIO/Python variables have no backup and are simply removed so
    host defaults apply.
    """
    env = os.environ.copy()
    for key in _BUNDLE_ENV_VARS:
        _restore_or_delete(env, key)
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


def is_appimage() -> bool:
    """Return True if running from an AppImage bundle."""
    return bool(os.environ.get("APPIMAGE") or os.environ.get("APPDIR"))


def _is_bundled() -> bool:
    """True if the process environment is bundler-polluted (AppImage / raw PyInstaller).

    Flatpak is intentionally excluded: there the environment is clean and the
    xdg-desktop-portal handles opening, so the Qt-native path is used instead.
    """
    import sys
    return bool(
        getattr(sys, "frozen", False)
        or os.environ.get("APPIMAGE")
        or os.environ.get("APPDIR")
        or "LD_LIBRARY_PATH_ORIG" in os.environ
    )


def _spawn_opener(target: str) -> bool:
    """Open *target* with a host opener using a cleaned environment.

    Tries xdg-open, then kde-open5/kde-open, then ``gio open``. Returns True if
    one was spawned. Used for AppImage/PyInstaller where Qt's own opener would
    inherit the bundled LD_LIBRARY_PATH and die.
    """
    import subprocess
    env = clean_subprocess_env()
    for opener in ("xdg-open", "kde-open5", "kde-open"):
        path = shutil.which(opener)
        if not path:
            continue
        try:
            subprocess.Popen(
                [path, target], env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True
        except OSError:
            continue
    gio = shutil.which("gio")
    if gio:
        try:
            subprocess.Popen(
                [gio, "open", target], env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True
        except OSError:
            pass
    return False


def _open_failed(target: str, parent=None) -> bool:
    print(
        f"[open] Konnte Ziel nicht öffnen: {target} "
        f"(kein xdg-open/kde-open/gio gefunden oder Start fehlgeschlagen)"
    )
    if parent is not None:
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                parent, "Öffnen fehlgeschlagen",
                f"Konnte nicht geöffnet werden:\n{target}",
            )
        except Exception:
            pass
    return False


def host_open_url(url: str, parent=None) -> bool:
    """Open an http(s)/nxm URL in the host browser or scheme handler.

    AppImage/PyInstaller: spawn xdg-open with a cleaned env (Qt's opener would
    inherit the bundled libs and fail). Flatpak/source: use QDesktopServices,
    which routes through the desktop portal (Flatpak) or works natively.
    """
    if not url:
        return False
    if _is_bundled() and not is_flatpak():
        if _spawn_opener(url):
            return True
        return _open_failed(url, parent)
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if QDesktopServices.openUrl(QUrl(url)):
            return True
    except Exception:
        pass
    if _spawn_opener(url):
        return True
    return _open_failed(url, parent)


def host_open_path(path, parent=None) -> bool:
    """Open a local folder/file in the host file manager.

    Same environment handling as :func:`host_open_url`. Existence is checked
    first so a stale path yields a clear failure instead of a silent no-op.
    """
    if not path:
        return False
    target = str(path)
    if not os.path.exists(target):
        return _open_failed(target, parent)
    if _is_bundled() and not is_flatpak():
        if _spawn_opener(target):
            return True
        return _open_failed(target, parent)
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if QDesktopServices.openUrl(QUrl.fromLocalFile(target)):
            return True
    except Exception:
        pass
    if _spawn_opener(target):
        return True
    return _open_failed(target, parent)
