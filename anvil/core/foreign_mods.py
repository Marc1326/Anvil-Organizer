"""Fremde Dateien im Spielordner erkennen und abschalten.

Anvil entfernt beim Aufraeumen nur, was im Deploy-Manifest steht. Alles
andere bleibt unangetastet -- das muss so sein, sonst wuerde es fremdes
Eigentum loeschen. Die Kehrseite: Wer eine Mod von Hand in den Spielordner
kopiert, hat sie dauerhaft aktiv. Sie laedt bei jedem Start, ueberschreibt
verwaltete Mods und taucht in keiner Liste auf. Ein Haken in Anvil aendert
daran nichts, weil Anvil sie gar nicht kennt.

Gesucht wird nur in Ordnern, die das Spiel-Plugin als reine Mod-Ordner
ausweist (``GameModDirs``). Dort ist alles, was nicht von Anvil stammt,
zwangslaeufig fremd. In Ordnern mit echten Spieldateien waere die Frage
nicht entscheidbar -- deshalb wird dort nicht gesucht.

Abgeschaltet wird durch Umbenennen, nie durch Loeschen: die Datei bekommt
die Endung ``.anvil-disabled`` und laesst sich jederzeit zurueckholen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DISABLED_SUFFIX = ".anvil-disabled"


@dataclass
class ForeignFile:
    """Ein Fund im Spielordner, den Anvil nicht ausgerollt hat.

    Attributes:
        rel:     Pfad ab Spielwurzel, ohne die Abschalt-Endung.
        path:    Die Datei, wie sie gerade heisst.
        enabled: False, wenn sie bereits abgeschaltet ist.
        is_dir:  True bei Ordner-Mods (REDmod, CET).
        size:    Groesse in Bytes, 0 bei Ordnern.
    """

    rel: str
    path: Path
    enabled: bool
    is_dir: bool = False
    size: int = 0

    @property
    def name(self) -> str:
        return Path(self.rel).name


def deployed_paths(manifest_path: Path) -> set[str]:
    """Relative Pfade, die Anvil zuletzt ausgerollt hat.

    Liest ``.deploy_manifest.json``. Fehlt die Datei oder ist sie
    unlesbar, kommt eine leere Menge zurueck -- dann gilt alles im
    Spielordner als fremd, was bei nicht ausgerolltem Stand auch stimmt.
    """
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()

    pfade: set[str] = set()
    for eintrag in data.get("symlinks", []):
        link = str(eintrag.get("link", "")).replace("\\", "/").strip("/")
        if link:
            pfade.add(link)
    for ordner in data.get("created_dirs", []):
        ordner = str(ordner).replace("\\", "/").strip("/")
        if ordner:
            pfade.add(ordner)
    return pfade


def _ist_verwaltet(rel: str, deployed: set[str]) -> bool:
    """True, wenn *rel* selbst oder etwas darunter von Anvil stammt."""
    if rel in deployed:
        return True
    prefix = rel + "/"
    return any(p.startswith(prefix) for p in deployed)


def scan_instance(
    game_path: Path,
    mod_dirs: list[str],
    manifest_path: Path,
) -> list[ForeignFile]:
    """Sucht fremde Eintraege, aber nur bei ausgerolltem Stand.

    Ohne Manifest laesst sich die Frage nicht beantworten: Frameworks und
    direkt installierte Mods bleiben beim Aufraeumen absichtlich liegen,
    und ohne Vergleichsliste waeren sie von einer handkopierten Mod nicht
    zu unterscheiden. In dem Fall kommt eine leere Liste zurueck --
    lieber nichts melden als zwei Dutzend Fehlalarme.
    """
    if not manifest_path.is_file():
        return []

    return scan(game_path, mod_dirs, deployed_paths(manifest_path))


def scan(
    game_path: Path,
    mod_dirs: list[str],
    deployed: set[str],
) -> list[ForeignFile]:
    """Durchsucht die Mod-Ordner des Spiels nach fremden Eintraegen.

    Geprueft wird nur die oberste Ebene jedes Ordners: eine Mod ist dort
    entweder eine Datei (``.archive``, ``.pak``) oder ein Ordner (REDmod,
    CET). Tiefer zu suchen wuerde eine Mod in ihre Einzelteile zerlegen.

    Args:
        game_path: Wurzel der Spielinstallation.
        mod_dirs:  Reine Mod-Ordner relativ zur Wurzel.
        deployed:  Was Anvil ausgerollt hat, aus :func:`deployed_paths`.

    Returns:
        Gefundene Eintraege, nach Pfad sortiert.
    """
    funde: list[ForeignFile] = []

    for mod_dir in mod_dirs:
        basis = game_path / mod_dir
        if not basis.is_dir():
            continue

        try:
            eintraege = sorted(basis.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue

        for eintrag in eintraege:
            name = eintrag.name
            aktiv = not name.endswith(DISABLED_SUFFIX)
            klarname = name[: -len(DISABLED_SUFFIX)] if not aktiv else name

            rel = f"{str(mod_dir).replace(chr(92), '/').strip('/')}/{klarname}"

            if _ist_verwaltet(rel, deployed):
                continue

            try:
                ist_ordner = eintrag.is_dir()
                groesse = 0 if ist_ordner else eintrag.stat().st_size
            except OSError:
                ist_ordner, groesse = False, 0

            funde.append(ForeignFile(
                rel=rel,
                path=eintrag,
                enabled=aktiv,
                is_dir=ist_ordner,
                size=groesse,
            ))

    funde.sort(key=lambda f: f.rel.lower())
    return funde


def to_entries(funde: list[ForeignFile], start_priority: int) -> list:
    """Macht aus den Funden Eintraege fuer die Mod-Liste.

    Sie erscheinen ganz unten, weil sie in der Ladereihenfolge nicht
    mitspielen -- sie stehen in keiner modlist.txt und werden von Anvil
    auch nicht dorthin geschrieben.
    """
    from anvil.core.mod_entry import ModEntry
    from anvil.core.translator import tr

    eintraege = []
    for i, fund in enumerate(funde):
        eintraege.append(ModEntry(
            name=fund.rel,
            display_name=fund.name,
            category=tr("foreign.marker"),
            enabled=fund.enabled,
            priority=start_priority + i,
            is_foreign=True,
            foreign_path=fund.path,
            file_count=0,
            total_size=fund.size,
        ))
    return eintraege


def set_enabled(path: Path, enabled: bool) -> Path:
    """Schaltet einen Fund um, indem die Endung gesetzt oder entfernt wird.

    Gibt den neuen Pfad zurueck. Steht die Datei schon richtig, passiert
    nichts. Geloescht wird nie.

    Raises:
        OSError: Wenn das Umbenennen fehlschlaegt.
    """
    ist_aktiv = not path.name.endswith(DISABLED_SUFFIX)
    if ist_aktiv == enabled:
        return path

    if enabled:
        ziel = path.with_name(path.name[: -len(DISABLED_SUFFIX)])
    else:
        ziel = path.with_name(path.name + DISABLED_SUFFIX)

    if ziel.exists():
        # Beide Fassungen vorhanden -- nichts ueberschreiben, sonst ist
        # eine davon unwiederbringlich weg.
        raise OSError(f"{ziel.name} existiert bereits")

    path.rename(ziel)
    return ziel
