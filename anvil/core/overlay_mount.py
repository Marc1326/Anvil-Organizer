"""Einhaengen der Mod-Schicht per Kernel-Overlay.

Der Mount haengt direkt am Spielordner im normalen System-Namespace.
Darum braucht es Root-Rechte: Anvil ruft ein kleines Helferskript ueber
pkexec auf.  Es gibt keinen Startwrapper und keinen Eingriff in Steam --
jeder Startweg (Anvil, Steam, Verknuepfung) sieht dieselbe Sicht.

Endet das Spiel, bleibt der Mount bewusst stehen: Der Spielordner ist
ueberdeckt, aber unveraendert.  Abgebaut wird er beim Purge oder wenn
der Nutzer auf Symlinks zurueckschaltet.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

HELPER_NAME = ".overlay-mount-helper"
# Systemweite, root-eigene Variante -- erst dann darf polkit das
# Passwort weglassen. Ein Skript im Home liesse sich vom Nutzer selbst
# umschreiben und waere ein offenes Root-Tor.
SYSTEM_HELPER = Path("/usr/local/libexec/anvil-overlay-mount")
POLKIT_RULE = Path("/etc/polkit-1/rules.d/50-anvil-overlay.rules")

_HELPER = """#!/bin/bash
# Von Anvil erzeugt. Handaenderungen gehen beim naechsten Deploy verloren.
# Aufruf: <aktion> <mount.conf>
set -u

AKTION="${1:-}"
CONF="${2:-}"

[ -r "$CONF" ] || { echo "keine Mount-Angaben: $CONF" >&2; exit 1; }

einhaengen() {
    local ziel lower upper work
    while IFS= read -r line; do
        case "$line" in
            MOUNT=*) ;;
            *) continue ;;
        esac
        IFS='|' read -r ziel lower upper work <<< "${line#MOUNT=}"
        [ -n "$ziel" ] && [ -n "$lower" ] && [ -n "$upper" ] && [ -n "$work" ] || continue
        [ -d "$ziel" ] || continue
        mkdir -p "$upper" "$work"
        # Schon gemountet? Dann liegt ein Stapel vor -- erst abnehmen.
        while findmnt -T "$ziel" -o FSTYPE -n | grep -qx overlay; do
            umount "$ziel" || break
        done
        mount -t overlay overlay -o "lowerdir=$lower,upperdir=$upper,workdir=$work" "$ziel" \
            || { echo "Mount fehlgeschlagen: $ziel" >&2; exit 1; }
        echo "gemountet: $ziel"
    done < "$CONF"
}

abhaengen() {
    local ziel
    while IFS= read -r line; do
        case "$line" in
            MOUNT=*) ;;
            *) continue ;;
        esac
        IFS='|' read -r ziel _rest <<< "${line#MOUNT=}"
        [ -n "$ziel" ] || continue
        while findmnt -T "$ziel" -o FSTYPE -n | grep -qx overlay; do
            umount "$ziel" || { echo "Unmount fehlgeschlagen: $ziel" >&2; exit 1; }
            echo "abgehaengt: $ziel"
        done
    done < "$CONF"
}

case "$AKTION" in
    mount)   einhaengen ;;
    umount)  abhaengen ;;
    purge)
        abhaengen
        # Das Arbeitsverzeichnis gehoert nach einem Mount root.
        while IFS= read -r line; do
            case "$line" in
                MOUNT=*) ;;
                *) continue ;;
            esac
            IFS='|' read -r _ziel _lower _upper work <<< "${line#MOUNT=}"
            [ -n "$work" ] && rm -rf "$work"
        done < "$CONF"
        ;;
    *) echo "Aufruf: $0 mount|umount|purge <mount.conf>" >&2; exit 1 ;;
esac
"""

_POLKIT_RULE = """// Von Anvil eingerichtet: das Overlay-Helferskript ohne Passwort.
polkit.addRule(function(action, subject) {
    if (action.id === "org.freedesktop.policykit.exec" &&
        action.lookup("program") === "{helper}" &&
        subject.user === "{user}") {
        return polkit.Result.YES;
    }
});
"""


def helper_path(base_path: Path) -> Path:
    """Ein Helfer fuer alle Instanzen dieser Anvil-Basis."""
    return base_path / HELPER_NAME


def write_helper(base_path: Path) -> Path:
    """Schreibt das Helferskript frisch und macht es ausfuehrbar."""
    ziel = helper_path(base_path)
    ziel.write_text(_HELPER, encoding="utf-8")
    ziel.chmod(0o755)
    return ziel


def is_mounted(target: Path) -> bool:
    """Haengt an diesem Pfad gerade ein Overlay?"""
    try:
        ausgabe = subprocess.run(
            ["findmnt", "-T", str(target), "-o", "FSTYPE", "-n"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return ausgabe.stdout.strip() == "overlay"


def _helfer_fuer_aufruf(base_path: Path) -> Path:
    """Systemweiter Helfer, wenn eingerichtet -- sonst frisch schreiben."""
    if polkit_rule_installed(base_path, _aktueller_user()) and SYSTEM_HELPER.is_file():
        return SYSTEM_HELPER
    return write_helper(base_path)


def _aktueller_user() -> str:
    import getpass
    return getpass.getuser()


def _rufe_helfer(aktion: str, base_path: Path, mount_conf: Path) -> tuple[bool, str]:
    """Fuehrt das Helferskript ueber pkexec aus.

    Liefert (True, Protokoll) bei Erfolg.  Bricht der Nutzer den
    Passwort-Dialog ab, kommt (False, "") zurueck -- das ist kein
    Fehler des Systems, nur ein Nein.
    """
    helfer = _helfer_fuer_aufruf(base_path)
    try:
        lauf = subprocess.run(
            ["pkexec", str(helfer), aktion, str(mount_conf)],
            capture_output=True, text=True, timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if lauf.returncode in (126, 127) and not lauf.stderr:
        # 126: Dialog abgebrochen / nicht autorisiert.
        return False, ""
    if lauf.returncode != 0:
        return False, (lauf.stderr or lauf.stdout or "").strip()
    return True, lauf.stdout.strip()


def mount(base_path: Path, mount_conf: Path) -> tuple[bool, str]:
    """Haengt alle Schichten aus der mount.conf ein."""
    return _rufe_helfer("mount", base_path, mount_conf)


def unmount(base_path: Path, mount_conf: Path) -> tuple[bool, str]:
    """Nimmt alle Schichten aus der mount.conf ab (auch Stapel)."""
    return _rufe_helfer("umount", base_path, mount_conf)


def purge_mounts(base_path: Path, mount_conf: Path) -> tuple[bool, str]:
    """Unmount plus Aufraeumen der root-eigenen Arbeitsverzeichnisse."""
    return _rufe_helfer("purge", base_path, mount_conf)


def polkit_rule_installed(base_path: Path, user: str) -> bool:
    del base_path  # Die Regel gilt systemweit, nicht pro Basis.
    try:
        # /etc/polkit-1/rules.d ist fuer Normalnutzer nicht lesbar.
        if not POLKIT_RULE.is_file():
            return False
        inhalt = POLKIT_RULE.read_text(encoding="utf-8")
    except OSError:
        return False
    return str(SYSTEM_HELPER) in inhalt and f'"{user}"' in inhalt


def install_polkit_rule(base_path: Path, user: str) -> tuple[bool, str]:
    """Richtet einmalig ein, dass der Mount ohne Passwort laeuft.

    Installiert das Helferskript root-eigen unter /usr/local/libexec
    und schreibt eine polkit-Regel, die genau dieses Skript fuer
    genau diesen Nutzer freigibt.
    """
    helfer = write_helper(base_path)
    einrichten = (
        "install -D -m 755 " + _q(str(helfer)) + " " + _q(str(SYSTEM_HELPER))
        + " && cat > " + _q(str(POLKIT_RULE))
    )
    regel = _POLKIT_RULE.format(helper=SYSTEM_HELPER, user=user)
    lauf = subprocess.run(
        ["pkexec", "sh", "-c", einrichten],
        input=regel, capture_output=True, text=True, timeout=120,
    )
    if lauf.returncode != 0:
        return False, (lauf.stderr or "").strip()
    return True, ""


def _q(pfad: str) -> str:
    import shlex
    return shlex.quote(pfad)


def mount_requirements() -> list[str]:
    """Was diesem Weg auf dem System im Weg stehen kann."""
    from anvil.core.translator import tr

    probleme: list[str] = []
    try:
        arten = Path("/proc/filesystems").read_text(encoding="utf-8")
    except OSError:
        arten = ""
    if "overlay" not in arten:
        probleme.append(tr("overlay.no_kernel_overlay"))
    import shutil
    if shutil.which("pkexec") is None:
        probleme.append(tr("overlay.no_pkexec"))
    return probleme
