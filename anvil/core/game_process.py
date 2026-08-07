"""Findet den laufenden Spielprozess.

Eine Flatpak-Sandbox bekommt einen eigenen PID-Namespace: ``/proc`` listet
darin nur Anvil selbst, Steam und das Spiel sind unsichtbar. Die Suche muss
deshalb ueber ``flatpak-spawn --host`` auf dem Host laufen.

Jede Suche liefert ``(pid, reliable)``. Schlaegt die Suche selbst fehl, ist
``reliable`` False -- "keine PID" darf dann nicht als "Spiel beendet"
gelesen werden, sonst raeumt Anvil die Mods unter dem laufenden Spiel weg.
"""

from __future__ import annotations

import os

from anvil.core.subprocess_env import is_flatpak


def scan_proc_for_game(app_id: str | None, binary_name: str | None) -> int | None:
    """Search the *local* /proc for the watched game process.

    Detection priority:
    1. SteamAppId in /proc/<pid>/environ (reliable for Steam/Proton games)
    2. binary name in /proc/<pid>/cmdline (fallback)
    """
    if not app_id and not binary_name:
        return None
    needle = f"SteamAppId={app_id}".encode() if app_id else b""
    binary = binary_name.lower().encode() if binary_name else b""
    own_pid = str(os.getpid())
    try:
        for entry in os.scandir("/proc"):
            if not entry.name.isdigit() or entry.name == own_pid:
                continue
            pid = entry.name
            try:
                if needle:
                    with open(f"/proc/{pid}/environ", "rb") as f:
                        if needle in f.read():
                            return int(pid)
                if binary:
                    with open(f"/proc/{pid}/cmdline", "rb") as f:
                        if binary in f.read().lower():
                            return int(pid)
            except OSError:
                pass
    except OSError:
        pass
    return None


# Runs on the host via `python3 -c`.  Mirrors scan_proc_for_game() — the host
# cannot import from the sandbox, it sees nothing of /app.
#
# What to look for arrives on stdin, not in argv or the environment: anywhere
# else the binary name would end up in a command line of its own — this
# process' or flatpak-spawn's — and every scan would match the scanner
# instead of the game.
_HOST_SCAN = (
    "import os, sys\n"
    "lines = (sys.stdin.read().split('\\n') + ['', ''])\n"
    "app_id, binary = lines[0].strip(), lines[1].strip()\n"
    "needle = ('SteamAppId=' + app_id).encode() if app_id else None\n"
    "name = binary.lower().encode() if binary else None\n"
    "own = str(os.getpid())\n"
    "for entry in os.scandir('/proc'):\n"
    "    if not entry.name.isdigit() or entry.name == own:\n"
    "        continue\n"
    "    try:\n"
    "        if needle:\n"
    "            with open('/proc/' + entry.name + '/environ', 'rb') as f:\n"
    "                if needle in f.read():\n"
    "                    print(entry.name)\n"
    "                    break\n"
    "        if name:\n"
    "            with open('/proc/' + entry.name + '/cmdline', 'rb') as f:\n"
    "                if name in f.read().lower():\n"
    "                    print(entry.name)\n"
    "                    break\n"
    "    except OSError:\n"
    "        pass\n"
)

# Distinguishes "scan ran, found nothing" from "scan could not run".
_SCAN_FAILED = object()

# Der Watcher fragt im Sekundentakt — ein haengender Host-Aufruf darf ihn
# nicht ausbremsen, sonst wird aus dem Zeitlimit ein Vielfaches davon.
_HOST_SCAN_TIMEOUT = 3


def _host_scan_via_python(app_id: str, binary_name: str):
    """Run the /proc scan on the host. _SCAN_FAILED if it could not run."""
    import subprocess
    try:
        result = subprocess.run(
            ["flatpak-spawn", "--host", "python3", "-c", _HOST_SCAN],
            input=f"{app_id}\n{binary_name}\n",
            capture_output=True, text=True, timeout=_HOST_SCAN_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _SCAN_FAILED
    if result.returncode != 0:
        return _SCAN_FAILED
    out = result.stdout.strip()
    return int(out) if out.isdigit() else None


def _host_scan_via_ps(binary_name: str):
    """Fallback without host python3: match the binary name in `ps` output.

    Cannot read /proc/<pid>/environ, so the SteamAppId route is unavailable.
    """
    import subprocess
    if not binary_name:
        return _SCAN_FAILED
    try:
        result = subprocess.run(
            ["flatpak-spawn", "--host", "ps", "-eo", "pid=,args="],
            capture_output=True, text=True, timeout=_HOST_SCAN_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _SCAN_FAILED
    if result.returncode != 0:
        return _SCAN_FAILED
    needle = binary_name.lower()
    for line in result.stdout.splitlines():
        pid, _, args = line.strip().partition(" ")
        if pid.isdigit() and needle in args.lower():
            return int(pid)
    return None


def find_game_process(
    app_id: str | None, binary_name: str | None
) -> tuple[int | None, bool]:
    """Look up the watched game process.

    Returns ``(pid, reliable)``.  ``reliable`` is False when the lookup
    itself could not be performed — the caller must not read "no pid" as
    "game has stopped" in that case.
    """
    if not app_id and not binary_name:
        # Nichts zu suchen ist eine zuverlaessige Antwort, kein Fehlschlag.
        return None, True
    if not is_flatpak():
        return scan_proc_for_game(app_id, binary_name), True

    pid = _host_scan_via_python(app_id or "", binary_name or "")
    if pid is _SCAN_FAILED:
        pid = _host_scan_via_ps(binary_name or "")
    if pid is _SCAN_FAILED:
        return None, False
    return pid, True
