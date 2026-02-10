"""nxm:// URL handler for Nexus Mods download links.

Parses nxm:// URLs into structured data and provides Linux desktop
integration for registering Anvil Organizer as the nxm:// handler.

nxm:// format:
    nxm://gameName/mods/modID/files/fileID?key=...&expires=...
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, parse_qs


@dataclass
class NxmLink:
    """Parsed nxm:// download link."""

    game: str          # e.g. "cyberpunk2077"
    mod_id: int        # Nexus mod ID
    file_id: int       # Nexus file ID
    key: str = ""      # Download key (for free users)
    expires: str = ""  # Expiry timestamp
    user_id: str = ""  # Optional user ID
    raw_url: str = ""  # Original URL


def parse_nxm_url(url: str) -> NxmLink | None:
    """Parse an nxm:// URL into an NxmLink.

    Returns None if the URL is malformed.

    Expected format:
        nxm://gameName/mods/modID/files/fileID?key=...&expires=...
    """
    if not url.startswith("nxm://"):
        return None

    try:
        parsed = urlparse(url)
    except Exception:
        return None

    game = parsed.hostname or ""
    if not game:
        return None

    # Path: /mods/{modID}/files/{fileID}
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 4 or parts[0] != "mods" or parts[2] != "files":
        return None

    try:
        mod_id = int(parts[1])
        file_id = int(parts[3])
    except (ValueError, IndexError):
        return None

    # Query params
    query = parse_qs(parsed.query)
    key = query.get("key", [""])[0]
    expires = query.get("expires", [""])[0]
    user_id = query.get("user_id", [""])[0]

    return NxmLink(
        game=game,
        mod_id=mod_id,
        file_id=file_id,
        key=key,
        expires=expires,
        user_id=user_id,
        raw_url=url,
    )


def register_nxm_handler() -> bool:
    """Register Anvil Organizer as the nxm:// URL handler on Linux.

    Creates a .desktop file and registers it via xdg-mime.

    Returns True on success.
    """
    # Find the main entry point
    main_script = _find_main_script()
    if not main_script:
        return False

    desktop_dir = Path.home() / ".local" / "share" / "applications"
    desktop_dir.mkdir(parents=True, exist_ok=True)

    desktop_file = desktop_dir / "anvil-organizer.desktop"
    content = f"""[Desktop Entry]
Type=Application
Name=Anvil Organizer
Comment=Mod Organizer for Linux
Exec=python3 {main_script} %u
Icon=anvil-organizer
Terminal=false
Categories=Game;
MimeType=x-scheme-handler/nxm;
NoDisplay=true
"""
    try:
        desktop_file.write_text(content, encoding="utf-8")
    except OSError:
        return False

    # Register as nxm handler
    try:
        subprocess.run(
            ["xdg-mime", "default", "anvil-organizer.desktop", "x-scheme-handler/nxm"],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

    return True


def _find_main_script() -> str | None:
    """Find the main.py entry point for Anvil Organizer."""
    # Try relative to this file
    core_dir = Path(__file__).resolve().parent       # anvil/core/
    anvil_dir = core_dir.parent                       # anvil/
    project_dir = anvil_dir.parent                    # project root
    main_py = project_dir / "main.py"
    if main_py.is_file():
        return str(main_py)

    # Fallback: sys.argv[0]
    if sys.argv and sys.argv[0]:
        p = Path(sys.argv[0]).resolve()
        if p.is_file():
            return str(p)

    return None


def check_cli_for_nxm(argv: list[str] | None = None) -> NxmLink | None:
    """Check command-line arguments for an nxm:// URL.

    Args:
        argv: Command-line arguments (defaults to sys.argv).

    Returns:
        Parsed NxmLink if found, None otherwise.
    """
    args = argv if argv is not None else sys.argv
    for arg in args[1:]:  # skip script name
        if arg.startswith("nxm://"):
            return parse_nxm_url(arg)
    return None
