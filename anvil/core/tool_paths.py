"""Wo ein Werkzeug aus dem Mod-Ordner im Spiel tatsaechlich liegt.

Programme wie BodySlide oder xEdit lesen ihre Daten aus dem Ordner, in dem
sie selbst liegen. Startet man sie aus ``.mods/<Mod>/``, sehen sie nur die
eigene Mod -- alle anderen liegen daneben in ihren eigenen Ordnern. Erst im
Spielverzeichnis laufen sie zusammen.

Der ausgerollte Ort wird zuerst im Deploy-Manifest gesucht: dort steht,
wohin die Datei wirklich gelegt wurde, samt Trenner-Ziel und Umleitungen.
Liegt kein Manifest vor -- etwa beim Eintragen, bevor irgendetwas ausgerollt
ist --, wird derselbe Weg gerechnet, den der Deployer geht.
"""

from __future__ import annotations

import json
from pathlib import Path

from anvil.core.case_paths import CaseIndex
from anvil.core.deploy_rules import target_rel

MANIFEST_NAME = ".deploy_manifest.json"


def _aus_manifest(exe: Path, instance_path: Path | None) -> Path | None:
    if instance_path is None:
        return None
    try:
        manifest = json.loads(
            (instance_path / MANIFEST_NAME).read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    if not isinstance(manifest, dict):
        return None
    game_path = str(manifest.get("game_path", ""))
    gesucht = str(exe)
    eintraege = manifest.get("symlinks", [])
    if not isinstance(eintraege, list):
        return None
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):
            continue
        if str(eintrag.get("target", "")) != gesucht:
            continue
        # Wie beim Aufraeumen: ein eigenes Trenner-Ziel schlaegt den Spielordner.
        basis = str(eintrag.get("deploy_base", "")) or game_path
        link = str(eintrag.get("link", ""))
        if basis and link:
            return Path(basis) / link
    return None


def _gerechnet(
    exe: Path,
    mods_path: Path,
    game_path: Path | None,
    data_path: str,
    nest_under_mod_name: bool,
    multi_folder_routes: dict[str, str] | None,
) -> Path | None:
    if game_path is None:
        return None
    rel = exe.relative_to(mods_path)
    if len(rel.parts) < 2:
        return None
    ziel = target_rel(
        Path(*rel.parts[1:]),
        rel.parts[0],
        data_path=data_path,
        nest_under_mod_name=nest_under_mod_name,
        multi_folder_routes=multi_folder_routes,
    )
    return game_path / CaseIndex(game_path).resolve(ziel)


def deployed_tool_path(
    exe: Path | str,
    *,
    instance_path: Path | None = None,
    mods_path: Path | None = None,
    game_path: Path | None = None,
    data_path: str = "",
    nest_under_mod_name: bool = False,
    multi_folder_routes: dict[str, str] | None = None,
) -> Path | None:
    """Der Ort im Spiel, an dem *exe* nach dem Ausrollen liegt.

    ``None``, sobald sich nichts Besseres sagen laesst: Die Datei liegt gar
    nicht in ``.mods/`` -- dann steht sie schon dort, wo sie hingehoert --,
    sie liegt lose in ``.mods/`` ohne Mod-Ordner darum, oder der Spielpfad
    ist unbekannt. Der Aufrufer behaelt in diesen Faellen seinen Pfad.
    """
    if mods_path is None:
        return None
    exe = Path(exe)
    if not exe.is_absolute() or not exe.is_relative_to(mods_path):
        return None
    aus_manifest = _aus_manifest(exe, instance_path)
    if aus_manifest is not None:
        return aus_manifest
    return _gerechnet(
        exe, mods_path, game_path, data_path,
        nest_under_mod_name, multi_folder_routes,
    )


def resolve_tool_entry(
    exe_path: str, working_dir: str, **kwargs
) -> tuple[str, str]:
    """Einen gespeicherten Werkzeug-Eintrag auf den ausgerollten Ort umbiegen.

    Greift auch bei Eintraegen, die vor dem Umbau angelegt wurden. Passt
    nichts, bleibt alles so, wie es war.

    Aufzurufen **nach** dem Ausrollen: Nur wenn am neuen Ort wirklich etwas
    liegt, wird umgebogen. Sonst ist die Mod abgeschaltet, und der alte Pfad
    startet wenigstens noch.
    """
    if not exe_path:
        return exe_path, working_dir
    ziel = deployed_tool_path(exe_path, **kwargs)
    if ziel is None or not ziel.is_file():
        return exe_path, working_dir
    # Ein selbst gesetzter Arbeitsordner bleibt stehen. Zeigt er auf den
    # Ordner der Datei, ist es die Vorgabe und meint denselben Ort -- der
    # wandert mit.
    if not working_dir or Path(working_dir) == Path(exe_path).parent:
        working_dir = str(ziel.parent)
    return str(ziel), working_dir
