"""Resource path resolver — works in dev and PyInstaller frozen mode.

In dev mode, paths resolve via __file__ relative navigation.
In PyInstaller frozen mode, data files live under sys._MEIPASS.
"""

import sys
from pathlib import Path


def get_anvil_base() -> Path:
    """Return the anvil package root directory.

    Dev:        /home/.../Anvil Organizer/anvil/
    Frozen:     /tmp/.mount_xxx/_internal/anvil/
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "anvil"
    return Path(__file__).resolve().parent.parent
