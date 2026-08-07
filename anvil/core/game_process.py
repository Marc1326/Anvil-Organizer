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

# Der Suchbegriff endet auf dem Nulltrenner von environ, sonst wuerde
# SteamAppId=1091500 auch SteamAppId=10915000 treffen.
#
# Anvil startet Tools (xEdit, BodySlide, redMod.exe) mit der SteamAppId des
# Spiels, weil Proton sie braucht. Ohne diese Markierung haelt die Suche
# jedes laufende Tool fuer das Spiel selbst.
TOOL_ENV_MARKER = "ANVIL_TOOL"
_TOOL_NEEDLE = b"ANVIL_TOOL=1"


def scan_proc_for_game(app_id: str | None, binary_name: str | None) -> int | None:
    """Search the *local* /proc for the watched game process.

    Detection priority:
    1. SteamAppId in /proc/<pid>/environ (reliable for Steam/Proton games)
    2. binary name in /proc/<pid>/cmdline (fallback)
    """
    if not app_id and not binary_name:
        return None
    needle = f"SteamAppId={app_id}\0".encode() if app_id else b""
    binary = binary_name.lower().encode() if binary_name else b""
    own_pid = str(os.getpid())
    try:
        for entry in os.scandir("/proc"):
            if not entry.name.isdigit() or entry.name == own_pid:
                continue
            pid = entry.name
            try:
                with open(f"/proc/{pid}/environ", "rb") as f:
                    environ = f.read()
                if _TOOL_NEEDLE in environ:
                    continue
                if needle and needle in environ:
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
    "needle = ('SteamAppId=' + app_id + chr(0)).encode() if app_id else None\n"
    "name = binary.lower().encode() if binary else None\n"
    "own = str(os.getpid())\n"
    "for entry in os.scandir('/proc'):\n"
    "    if not entry.name.isdigit() or entry.name == own:\n"
    "        continue\n"
    "    try:\n"
    "        with open('/proc/' + entry.name + '/environ', 'rb') as f:\n"
    "            environ = f.read()\n"
    "        if b'ANVIL_TOOL=1' in environ:\n"
    "            continue\n"
    "        if needle and needle in environ:\n"
    "            print(entry.name)\n"
    "            break\n"
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
_SCAN_TIMEOUT = object()

# Der Watcher fragt im Sekundentakt — ein haengender Host-Aufruf darf ihn
# nicht ausbremsen, sonst wird aus dem Zeitlimit ein Vielfaches davon.
_HOST_SCAN_TIMEOUT = 3


def _host_scan_via_python(app_id: str, binary_name: str):
    """Run the /proc scan on the host.

    Returns the PID, None if nothing matched, or a sentinel telling the
    caller why no answer could be produced.
    """
    import subprocess
    try:
        result = subprocess.run(
            ["flatpak-spawn", "--host", "python3", "-c", _HOST_SCAN],
            input=f"{app_id}\n{binary_name}\n",
            capture_output=True, text=True, timeout=_HOST_SCAN_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return _SCAN_TIMEOUT
    except OSError:
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
    except subprocess.TimeoutExpired:
        return _SCAN_TIMEOUT
    except OSError:
        return _SCAN_FAILED
    if result.returncode != 0:
        return _SCAN_FAILED
    needle = binary_name.lower()
    for line in result.stdout.splitlines():
        pid, _, args = line.strip().partition(" ")
        if pid.isdigit() and needle in args.lower():
            return int(pid)
    return None


def plugin_watch_target(plugin) -> tuple[str | None, str | None]:
    """SteamAppId und Binaername eines Plugins als Suchmerkmale.

    Der Spielpfad taugt nicht: er steht in jeder Shell, die ihn erwaehnt,
    und in Steams verwaisten Hilfsprozessen.
    """
    if plugin is None:
        return None, None
    app_id = getattr(plugin, "GameSteamId", None)
    if isinstance(app_id, list):
        app_id = app_id[0] if app_id else None
    binary = getattr(plugin, "GameBinary", "") or ""
    return (str(app_id) if app_id else None), (os.path.basename(binary).lower() or None)


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
    if pid is _SCAN_TIMEOUT:
        # Ein zweiter Anlauf mit anderem Werkzeug hilft nicht, wenn der Host
        # schon zu langsam war — er verdoppelt nur die Wartezeit.
        return None, False
    if pid is _SCAN_FAILED:
        pid = _host_scan_via_ps(binary_name or "")
    if pid in (_SCAN_FAILED, _SCAN_TIMEOUT):
        return None, False
    return pid, True
