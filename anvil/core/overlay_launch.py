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

# Erst trocken einhaengen. Schlaegt das fehl, startet das Spiel lieber ohne
# Mods als gar nicht -- ein exec bwrap ohne Netz wuerde den Start abbrechen.
if ! bwrap --dev-bind / / "${{ARGS[@]}}" -- /bin/true >>"$LOG" 2>&1; then
    echo "[$(date '+%F %T')] Einhaengen fehlgeschlagen -- starte ohne Mods" >> "$LOG"
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


def _block_span(text: str, key: str, von: int = 0, bis: int | None = None) -> tuple[int, int, str] | None:
    """Grenzen des Blocks ``"key" { ... }`` innerhalb von [von, bis).

    Liefert (Anfang des Inhalts, Ende des Inhalts, Einrueckung) oder None.
    Die schliessende Klammer wird ueber die Einrueckung gefunden, damit
    verschachtelte Bloecke nicht faelschlich beenden.
    """
    bis = len(text) if bis is None else bis
    muster = re.compile(r'"' + re.escape(key) + r'"\n(\t*)\{\n')
    stelle = von
    while True:
        treffer = muster.search(text, stelle, bis)
        if treffer is None:
            return None
        einrueckung = treffer.group(1)
        schluss = text.find("\n" + einrueckung + "}", treffer.end() - 1, bis)
        if schluss >= 0:
            return treffer.end(), schluss + 1, einrueckung
        stelle = treffer.end()


def _app_block(text: str, app_id: str) -> tuple[int, int, str] | None:
    """Der App-Eintrag unter UserLocalConfigStore/Software/Valve/Steam/apps.

    Die Kennung steht in derselben Datei mehrfach -- in Lizenzangaben, in
    CDN-Angaben und in einem zweiten apps-Abschnitt. Deshalb wird der Pfad
    Abschnitt fuer Abschnitt abgestiegen statt frei gesucht. Frei gesucht
    trifft man die falsche Stelle und ueberschreibt fremde Startoptionen.
    """
    spanne = (0, len(text))
    for abschnitt in ("UserLocalConfigStore", "Software", "Valve", "Steam", "apps"):
        gefunden = _block_span(text, abschnitt, spanne[0], spanne[1])
        if gefunden is None:
            return None
        spanne = (gefunden[0], gefunden[1])
    return _block_span(text, app_id, spanne[0], spanne[1])


_LAUNCH = r'"LaunchOptions"\t+"((?:[^"\\]|\\.)*)"\n'


def _unescape(value: str) -> str:
    ergebnis = []
    maskiert = False
    for zeichen in value:
        if maskiert:
            ergebnis.append(zeichen)
            maskiert = False
        elif zeichen == "\\":
            maskiert = True
        else:
            ergebnis.append(zeichen)
    return "".join(ergebnis)


def read_launch_options(app_id: str, config: Path) -> str | None:
    try:
        text = config.read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return None
    block = _app_block(text, app_id)
    if block is None:
        return None
    anfang, schluss, einrueckung = block
    gefunden = re.search(
        r'\n' + einrueckung + r'\t' + _LAUNCH,
        "\n" + text[anfang:schluss],
    )
    return _unescape(gefunden.group(1)) if gefunden else ""


def set_launch_options(app_id: str, value: str, config: Path) -> None:
    """Traegt die Startoption ein.

    Steam muss dabei beendet sein -- es haelt die Datei im Speicher und
    schreibt sie beim Beenden zurueck.
    """
    if steam_is_running():
        raise RuntimeError("Steam laeuft -- Startoption kann nicht gesetzt werden")

    text = config.read_text(encoding="utf-8", errors="surrogateescape")
    block = _app_block(text, app_id)
    if block is None:
        raise RuntimeError(f"App {app_id} steht nicht in {config}")

    anfang, schluss, einrueckung = block
    tiefe = einrueckung + "\t"
    # VDF kennt Backslash-Maskierung. Ersetzen durch einfache Anfuehrungs-
    # zeichen wuerde Pfade mit Leerzeichen zerlegen -- und Instanzordner
    # heissen nun mal "Cyberpunk 2077".
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    zeile = f'{tiefe}"LaunchOptions"\t\t"{escaped}"\n'

    inhalt = text[anfang:schluss]
    vorhanden = re.search(r'^' + re.escape(tiefe) + _LAUNCH, inhalt, re.M)
    if vorhanden:
        neuer_inhalt = inhalt[:vorhanden.start()] + zeile + inhalt[vorhanden.end():]
    else:
        neuer_inhalt = zeile + inhalt
    aktualisiert = text[:anfang] + neuer_inhalt + text[schluss:]

    sicherung = config.with_suffix(config.suffix + ".anvil-backup")
    if not sicherung.exists():
        shutil.copy2(config, sicherung)

    temporary = config.with_suffix(config.suffix + ".tmp")
    temporary.write_text(aktualisiert, encoding="utf-8", errors="surrogateescape")
    os.replace(temporary, config)
