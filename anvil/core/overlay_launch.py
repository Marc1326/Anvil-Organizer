"""Startwrapper und Steam-Startoption fuer den Overlay-Deploy.

Der Mount kann nicht aus Anvil heraus passieren: er lebt in einem
Mount-Namespace und waere fuer das Spiel unsichtbar, weil Steam das Spiel in
einem eigenen Prozessbaum startet.  Also schreibt Anvil ein kleines Skript,
traegt es als Startoption ein und laesst Steam es aufrufen.  Das Skript haengt
das Overlay ein und uebergibt an das Spiel.

Endet das Spiel, endet der Namespace -- und der Mount mit ihm.  Es gibt nichts
aufzuraeumen.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

WRAPPER_NAME = "anvil-overlay-mount"

_WRAPPER = """#!/bin/bash
# Von Anvil erzeugt. Haengt die Mod-Schicht ueber den Spielordner und startet
# dann das uebergebene Kommando. Handaenderungen gehen beim naechsten Deploy
# verloren.
set -u

CONF="{conf}"
LOG="{log}"

if [ ! -r "$CONF" ]; then
    echo "[$(date '+%F %T')] keine Mount-Angaben ($CONF) -- starte ohne Mods" >> "$LOG"
    exec "$@"
fi

if ! command -v bwrap >/dev/null 2>&1; then
    echo "[$(date '+%F %T')] bwrap fehlt -- starte ohne Mods" >> "$LOG"
    exec "$@"
fi

# Eine MOUNT-Zeile je Ziel:  MOUNT=<ziel>|<schicht>:<schicht>|<upper>|<work>
ARGS=()
MOUNTS=0
while IFS= read -r line; do
    case "$line" in
        MOUNT=*) ;;
        *) continue ;;
    esac
    rest="${{line#MOUNT=}}"
    IFS='|' read -r ziel lower upper work <<< "$rest"
    [ -n "$ziel" ] && [ -n "$lower" ] && [ -n "$upper" ] && [ -n "$work" ] || continue
    [ -d "$ziel" ] || continue

    schichten=0
    teil=()
    IFS=':' read -r -a LAYERS <<< "$lower"
    # Die Liste steht in Kernel-Reihenfolge: hoechste Prioritaet zuerst.
    # bwrap versteht --overlay-src andersherum -- die zuletzt genannte Quelle
    # gewinnt. Also rueckwaerts durchlaufen, sonst schlaegt der Spielordner
    # jede Mod.
    for ((i=${{#LAYERS[@]}}-1; i>=0; i--)); do
        d="${{LAYERS[i]}}"
        [ -d "$d" ] || continue
        teil+=(--overlay-src "$d")
        schichten=$((schichten + 1))
    done

    # Unter zwei Schichten gibt es nichts zu mischen.
    [ "$schichten" -ge 2 ] || continue

    mkdir -p "$upper" "$work"
    ARGS+=("${{teil[@]}}" --overlay "$upper" "$work" "$ziel")
    MOUNTS=$((MOUNTS + 1))
    echo "[$(date '+%F %T')] Mount $MOUNTS: $schichten Schichten -> $ziel" >> "$LOG"
done < "$CONF"

if [ "$MOUNTS" -eq 0 ]; then
    echo "[$(date '+%F %T')] kein brauchbarer Mount -- starte ohne Mods" >> "$LOG"
    exec "$@"
fi

echo "[$(date '+%F %T')] uebergebe an das Spiel" >> "$LOG"

exec bwrap \\
    --dev-bind / / \\
    "${{ARGS[@]}}" \\
    -- "$@"
"""


def wrapper_path(instance_path: Path) -> Path:
    return instance_path / ".overlay" / WRAPPER_NAME


def write_wrapper(instance_path: Path, conf_path: Path, log_path: Path | None = None) -> Path:
    """Legt den Startwrapper an und macht ihn ausfuehrbar."""
    target = wrapper_path(instance_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    log = log_path or (instance_path / ".overlay" / "start.log")
    target.write_text(
        _WRAPPER.format(conf=conf_path, log=log),
        encoding="utf-8",
    )
    target.chmod(0o755)
    return target


def launch_option(wrapper: Path) -> str:
    """Der Text, der bei Steam in die Startoptionen gehoert."""
    return f'"{wrapper}" %command%'


# ── Steam-Konfiguration ────────────────────────────────────────────────

def steam_is_running() -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-x", "steam"],
            capture_output=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def localconfig_files(steam_root: Path | None = None) -> list[Path]:
    root = steam_root or (Path.home() / ".local" / "share" / "Steam")
    userdata = root / "userdata"
    if not userdata.is_dir():
        return []
    found = []
    for entry in sorted(userdata.iterdir()):
        candidate = entry / "config" / "localconfig.vdf"
        if candidate.is_file():
            found.append(candidate)
    return found


def _app_block(text: str, app_id: str) -> re.Match[str] | None:
    """Findet den App-Eintrag unter Software/Valve/Steam/apps.

    Erkennbar daran, dass direkt darin ``LastPlayed`` oder ``Playtime`` steht --
    die uebrigen Vorkommen derselben Zahl sind Lizenz- und CDN-Angaben.
    """
    pattern = re.compile(
        r'"' + re.escape(app_id) + r'"\n(\t+)\{\n'
        r'(?=(?:.*\n)*?\1\t"(?:LastPlayed|Playtime|LaunchOptions)")'
    )
    return pattern.search(text)


def read_launch_options(app_id: str, config: Path) -> str | None:
    try:
        text = config.read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return None
    match = _app_block(text, app_id)
    if match is None:
        return None
    depth = match.group(1)
    block = text[match.end():]
    found = re.search(
        r'\n' + depth + r'\t"LaunchOptions"\t+"((?:[^"\\]|\\.)*)"',
        "\n" + block[:4000],
    )
    if not found:
        return ""
    return found.group(1).replace('\\"', '"').replace("\\\\", "\\")


def set_launch_options(app_id: str, value: str, config: Path) -> None:
    """Traegt die Startoption ein.

    Steam muss dabei beendet sein -- es haelt die Datei im Speicher und
    schreibt sie beim Beenden zurueck.
    """
    if steam_is_running():
        raise RuntimeError("Steam laeuft -- Startoption kann nicht gesetzt werden")

    text = config.read_text(encoding="utf-8", errors="surrogateescape")
    match = _app_block(text, app_id)
    if match is None:
        raise RuntimeError(f"App {app_id} steht nicht in {config}")

    depth = match.group(1) + "\t"
    # VDF kennt Backslash-Maskierung. Ersetzen durch einfache Anfuehrungs-
    # zeichen wuerde Pfade mit Leerzeichen zerlegen -- und Instanzordner
    # heissen nun mal "Cyberpunk 2077".
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    line = f'{depth}"LaunchOptions"\t\t"{escaped}"\n'

    existing = re.search(
        r'\n' + re.escape(depth) + r'"LaunchOptions"\t+"(?:[^"\\]|\\.)*"\n',
        text[match.end() - 1:match.end() + 4000],
    )
    if existing:
        start = match.end() - 1 + existing.start()
        end = match.end() - 1 + existing.end()
        updated = text[:start] + "\n" + line + text[end:]
    else:
        updated = text[:match.end()] + line + text[match.end():]

    backup = config.with_suffix(config.suffix + ".anvil-backup")
    if not backup.exists():
        shutil.copy2(config, backup)

    temporary = config.with_suffix(config.suffix + ".tmp")
    temporary.write_text(updated, encoding="utf-8", errors="surrogateescape")
    os.replace(temporary, config)
