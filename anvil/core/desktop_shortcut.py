"""Erzeugt .desktop-Verknüpfungen, die ein Spiel über Anvil starten (#24).

Wiederverwendet die Exec-Erkennung aus nxm_handler (Flatpak/AppImage/PyInstaller/Dev),
damit kein Pfad hartkodiert wird. Die Verknüpfung ruft Anvil mit ``--launch-instance``;
ob danach das Spiel startet oder nur Anvil öffnet, entscheidet ein globaler Schalter
in den Einstellungen.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

from anvil.core.nxm_handler import build_exec_command

LAUNCH_ARG = "--launch-instance"


def _slugify(name: str) -> str:
    """Dateinamen-tauglicher Slug aus einem Instanznamen."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "instanz"


def get_launch_instance_arg(argv: list[str] | None = None) -> str | None:
    """Return the value of ``--launch-instance`` from argv, or None.

    Akzeptiert ``--launch-instance NAME`` und ``--launch-instance=NAME``.
    """
    args = argv if argv is not None else sys.argv
    rest = args[1:]  # Skriptnamen überspringen
    for i, arg in enumerate(rest):
        if arg == LAUNCH_ARG:
            return rest[i + 1] if i + 1 < len(rest) else None
        if arg.startswith(LAUNCH_ARG + "="):
            return arg.split("=", 1)[1]
    return None


def create_game_shortcut(
    instance_name: str,
    display_name: str,
    icon: str = "anvil-organizer",
    target_dir: Path | None = None,
) -> Path | None:
    """Schreibt eine ``.desktop``-Verknüpfung für die angegebene Instanz.

    Gibt den Pfad der erzeugten Datei zurück oder ``None`` bei Fehler.
    """
    if not instance_name:
        return None
    exec_cmd = build_exec_command()
    if not exec_cmd:
        return None

    target = Path(target_dir) if target_dir else (
        Path.home() / ".local" / "share" / "applications"
    )
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    name = display_name or instance_name
    # Anführungszeichen im Instanznamen entschärfen, damit die Exec-Zeile gültig bleibt
    safe_instance = instance_name.replace('"', "")
    exec_line = f'{exec_cmd} {LAUNCH_ARG} "{safe_instance}"'

    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name}\n"
        f"Comment={name} — Anvil Organizer\n"
        f"Exec={exec_line}\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=Game;\n"
    )

    # Hash-Suffix, damit verschiedene Instanznamen mit gleichem Slug nicht kollidieren
    # (gleicher Name → gleiche Datei → idempotentes Aktualisieren).
    digest = hashlib.sha1(instance_name.encode("utf-8")).hexdigest()[:8]
    desktop_file = target / f"anvil-game-{_slugify(instance_name)}-{digest}.desktop"
    try:
        desktop_file.write_text(content, encoding="utf-8")
        desktop_file.chmod(0o755)
    except OSError:
        return None
    return desktop_file
