"""Verwaltungsdateien duerfen nicht als Konflikt erscheinen.

``fomod_choices.json`` merkt sich, was der Nutzer im FOMOD-Installer
angeklickt hat. Die Datei liegt in jeder so installierten Mod und wird
beim Ausrollen uebersprungen -- sie kommt im Spiel also nie an. Trotzdem
zaehlte der Konfliktscanner sie mit, weil er eine eigene, kuerzere Liste
fuehrte als die Deploy-Regeln.
"""

from pathlib import Path, PurePosixPath

from anvil.core.conflict_scanner import ConflictScanner
from anvil.core.deploy_rules import _segmente
from anvil.core.modindex import ModIndex


VERWALTUNG = [
    "meta.ini",
    "codes.txt",
    "fomod_choices.json",
    "fomod/ModuleConfig.xml",
    "FOMOD/info.xml",
    "vorschau.png",
    "Thumbs.db",
]

INHALT = [
    "meshes/koerper.nif",
    "textures/haut.dds",
    "scripts/foo.pex",
]


def _mods(tmp_path: Path, dateien: list[str]) -> list[dict]:
    """Zwei Mods, die alle *dateien* unter demselben Pfad mitbringen."""
    eintraege = []
    for name in ("Erste", "Zweite"):
        wurzel = tmp_path / name
        for rel in dateien:
            ziel = wurzel / rel
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(b"x")
        eintraege.append({"name": name, "path": str(wurzel)})
    return eintraege


def test_verwaltungsdateien_sind_kein_konflikt(tmp_path: Path) -> None:
    ergebnis = ConflictScanner().scan_conflicts(_mods(tmp_path, VERWALTUNG))

    gemeldet = [k["file"] for k in ergebnis["conflicts"]]
    assert gemeldet == [], f"Verwaltungsdateien als Konflikt gemeldet: {gemeldet}"
    assert ergebnis["file_owners"] == {}


def test_echte_dateien_bleiben_konflikt(tmp_path: Path) -> None:
    """Die Gegenprobe -- sonst wuerde ein zu breiter Filter nicht auffallen."""
    ergebnis = ConflictScanner().scan_conflicts(_mods(tmp_path, INHALT))

    gemeldet = sorted(k["file"] for k in ergebnis["conflicts"])
    assert gemeldet == sorted(INHALT)
    for konflikt in ergebnis["conflicts"]:
        assert konflikt["winner"] == "Zweite"


def test_auch_ueber_den_zwischenspeicher(tmp_path: Path) -> None:
    """In der App laeuft die Pruefung ueber den ModIndex, nicht ueber die Platte.

    Der Scanner hat fuer beide Wege eigenen Code -- ein Test, der nur den
    Rueckfall auf das Dateisystem trifft, deckt den produktiven Zweig nicht ab.
    """
    mods = tmp_path / ".mods"
    for name in ("Erste", "Zweite"):
        for rel in VERWALTUNG + INHALT:
            ziel = mods / name / rel
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(b"x")

    index = ModIndex(tmp_path, mods_path=mods)
    index.rebuild()
    assert index.get_file_list("Erste"), "ModIndex hat nichts eingelesen"

    eintraege = [
        {"name": "Erste", "path": str(mods / "Erste")},
        {"name": "Zweite", "path": str(mods / "Zweite")},
    ]
    ergebnis = ConflictScanner().scan_conflicts(eintraege, mod_index=index)

    gemeldet = sorted(k["file"] for k in ergebnis["conflicts"])
    assert gemeldet == sorted(INHALT), (
        f"ueber den Zwischenspeicher kam etwas anderes heraus: {gemeldet}"
    )


def test_segmente_wie_purePosixPath() -> None:
    """``_segmente`` ersetzt ``PurePosixPath.parts`` aus Geschwindigkeitsgruenden.

    Weicht es ab, aendert sich stillschweigend, was ausgerollt wird.
    """
    faelle = [
        "", ".", "..", "a", "a/b", "a//b.png", "./a/b", "../a", "a/./b",
        "/", "/a/b", "//", "//a/b", "///", "///a/b", "////x",
        "/fomod/x.xml", "fomod", "fomod/x", "a/b/",
        ".hidden", "readme.", "a..txt", "  .png",
    ]
    for rel in faelle:
        assert _segmente(rel) == list(PurePosixPath(rel).parts), (
            f"{rel!r}: {_segmente(rel)} statt {list(PurePosixPath(rel).parts)}"
        )

