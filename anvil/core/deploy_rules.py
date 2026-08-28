"""Die Regeln, nach denen aus einem Mod-Pfad ein Spiel-Pfad wird.

Beide Deploy-Wege -- Symlinks und overlayfs -- muessen dieselbe Sicht
erzeugen. Solange die Regeln zweimal dastanden, sind sie auseinandergelaufen:
die Archiv-Pruefung lief einmal vor und einmal nach dem Data-Praefix.

Die Umrechnung ist bewusst in zwei Schritte geteilt. Die Archiv-Pruefung
gehoert dazwischen -- sie arbeitet auf dem Pfad **ohne** Data-Praefix, weil
ein eingeschobener Modname oder eine umgeschriebene erste Ebene sie sonst
ins Leere laufen laesst.
"""

from __future__ import annotations

from pathlib import Path

from anvil.core.archive_packing import is_archive_loose_path

# Dateien im Mod-Ordner, die zur Verwaltung gehoeren.
SKIP_FILES = {"meta.ini", "codes.txt", "fomod_choices.json"}

# Installer-Verzeichnisse.
SKIP_DIRS = {"fomod"}

# Endungen, die nur im Wurzelverzeichnis eines Mods ausgelassen werden --
# in Unterordnern sind das Spielinhalte.
SKIP_ROOT_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
    ".txt", ".md", ".pdf", ".log", ".readme",
    ".db",
}

# Endungen, die auch bei aktivem Archiv-Packen einzeln liegen bleiben.
ARCHIVE_KEEP_EXTENSIONS = {
    ".esp", ".esm", ".esl",   # Plugins
    ".dll", ".exe",           # Script Extender, Programme
    ".ini", ".cfg", ".toml",  # Konfiguration
    ".ba2", ".bsa",           # fertige Archive
}


def is_metadata(src: Path, mod_dir: Path, rel: Path) -> bool:
    """True fuer Dateien, die zur Mod-Verwaltung gehoeren.

    Der Symlink-Weg hat dieselben drei Pruefungen inline stehen
    (``mod_deployer.py``, Schleife ueber ``file_iter``) -- dort wird
    ``rel`` erst danach berechnet, deshalb ist der Aufruf nicht
    austauschbar. ``tests/test_deploy_regeln.py`` haelt beide Seiten
    auf denselben Faellen gleich.
    """
    if src.name in SKIP_FILES:
        return True
    if rel.parts and rel.parts[0].lower() in SKIP_DIRS:
        return True
    if src.parent == mod_dir and src.suffix.lower() in SKIP_ROOT_EXTENSIONS:
        return True
    return False


def strip_root(rel: Path) -> Path:
    """Entfernt ein fuehrendes ``root/`` (RootBuilder-Muster)."""
    if rel.parts and rel.parts[0].lower() == "root":
        return Path(*rel.parts[1:]) if len(rel.parts) > 1 else rel
    return rel


def goes_into_archive(
    rel: Path,
    suffix: str,
    *,
    loose_paths: list[str] | None = None,
    data_path: str = "",
) -> bool:
    """True, wenn der Archiv-Packer die Datei uebernimmt.

    *rel* muss der Pfad **ohne** Data-Praefix sein, so wie ``strip_root()``
    ihn liefert.
    """
    if suffix.lower() in ARCHIVE_KEEP_EXTENSIONS:
        return False
    return not is_archive_loose_path(rel, loose_paths or [], data_path)


def apply_data_path(
    rel: Path,
    mod_name: str,
    *,
    data_path: str = "",
    is_direct: bool = False,
    nest_under_mod_name: bool = False,
    multi_folder_routes: dict[str, str] | None = None,
) -> Path:
    """Setzt das Data-Praefix davor und wendet die Ordner-Umleitungen an.

    Frameworks bleiben in der Spielwurzel -- sie bringen Loader mit, die
    dort liegen muessen.

    Praefix und Umleitungen werden ohne Ruecksicht auf die Schreibweise
    erkannt: ein Archiv mit ``data/meshes`` meint dasselbe wie ``Data/meshes``,
    sonst kaeme ein zweites ``Data`` davor. Die Schreibweise aus der
    Spiel-Konfiguration gewinnt dabei, damit alle Mods im selben Ordner
    landen.
    """
    if not data_path or is_direct:
        return rel

    prefix = Path(data_path)
    routes = multi_folder_routes or {}
    if routes and len(rel.parts) > 1:
        gesucht = rel.parts[0].lower()
        for schluessel, ziel in routes.items():
            if schluessel.lower() == gesucht:
                return Path(ziel) / Path(*rel.parts[1:])

    # Echt laenger, nicht gleich lang: eine Datei, die im Wurzelverzeichnis
    # zufaellig "data" heisst, ist nicht der Data-Ordner.
    tiefe = len(prefix.parts)
    if len(rel.parts) > tiefe and all(
        a.lower() == b.lower() for a, b in zip(rel.parts[:tiefe], prefix.parts)
    ):
        return prefix.joinpath(*rel.parts[tiefe:])

    if nest_under_mod_name:
        return prefix / mod_name / rel
    return prefix / rel


def target_rel(
    rel: Path,
    mod_name: str,
    *,
    data_path: str = "",
    is_direct: bool = False,
    nest_under_mod_name: bool = False,
    multi_folder_routes: dict[str, str] | None = None,
) -> Path:
    """Beide Schritte auf einmal, fuer Aufrufer ohne Archiv-Packen.

    ACHTUNG -- das ist **nicht** der vollstaendige Deploy-Pfad. Zwischen
    beiden Schritten sitzt im Symlink-Weg die Zielverteilung
    (``strip_deploy_prefixes`` + ``route_deploy_path``), danach die
    Durchnummerierung der Archive (``pak_load_order_name``). Wer diese
    Funktion als "die" Zielrechnung liest, verliert beides.
    """
    return apply_data_path(
        strip_root(rel),
        mod_name,
        data_path=data_path,
        is_direct=is_direct,
        nest_under_mod_name=nest_under_mod_name,
        multi_folder_routes=multi_folder_routes,
    )
