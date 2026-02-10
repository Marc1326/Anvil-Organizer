"""Icon-Manager: Lädt Game-/Executable-Icons aus anvil/assets/icons/.

Ordnerstruktur::

    anvil/assets/icons/{game_short_name}/game.png
    anvil/assets/icons/{game_short_name}/game_wide.jpg
    anvil/assets/icons/{game_short_name}/executables/{exe_name}.png
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


# ── Placeholder generators ────────────────────────────────────────────


def placeholder_game_icon(size: int = 128) -> QPixmap:
    """Grey square with a controller-style icon."""
    pix = QPixmap(size, size)
    pix.fill(QColor("#2A2A2A"))
    p = QPainter(pix)
    p.setPen(QColor("#555555"))
    f = QFont()
    f.setPixelSize(size // 3)
    p.setFont(f)
    p.drawText(pix.rect(), 0x0084, "\U0001f3ae")  # AlignCenter
    p.end()
    return pix


def placeholder_banner(width: int = 280, height: int = 140, text: str = "") -> QPixmap:
    """Grey rectangle with game name as text."""
    pix = QPixmap(width, height)
    pix.fill(QColor("#242424"))
    if text:
        p = QPainter(pix)
        p.setPen(QColor("#808080"))
        f = QFont()
        f.setPixelSize(14)
        p.setFont(f)
        p.drawText(pix.rect(), 0x0084, text)  # AlignCenter
        p.end()
    return pix


# ── IconManager ───────────────────────────────────────────────────────


class IconManager:
    """Loads game/executable icons from local assets directory."""

    def __init__(self) -> None:
        self._assets_dir = _ASSETS_DIR
        self._mem: dict[str, QPixmap] = {}

    def get_game_icon(self, game_short_name: str) -> QPixmap | None:
        """Return game icon (game.png), or None if not found."""
        return self._load(game_short_name, "game.png")

    def get_game_banner(self, game_short_name: str) -> QPixmap | None:
        """Return game banner (game_wide.jpg), or None if not found."""
        return self._load(game_short_name, "game_wide.jpg")

    def get_executable_icon(
        self, game_short_name: str, exe_binary: str,
    ) -> QPixmap | None:
        """Return executable icon, or None if not found.

        Args:
            game_short_name: e.g. ``cyberpunk2077``
            exe_binary: Binary path from plugin, e.g. ``bin/x64/Cyberpunk2077.exe``
                        Only the basename is used for lookup.
        """
        basename = Path(exe_binary).name
        return self._load(game_short_name, f"executables/{basename}.png")

    def _load(self, game_short_name: str, rel_path: str) -> QPixmap | None:
        """Load from memory cache or disk."""
        key = f"{game_short_name}/{rel_path}"
        if key in self._mem:
            return self._mem[key]

        disk_path = self._assets_dir / game_short_name / rel_path
        if disk_path.is_file():
            pix = QPixmap(str(disk_path))
            if not pix.isNull():
                self._mem[key] = pix
                return pix

        return None
