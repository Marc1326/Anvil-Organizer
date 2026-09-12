"""Verwaltungsdateien duerfen nicht mit ins BA2-Archiv.

Der Packer fuehrte eine eigene, kuerzere Liste als der Deployer und liess
nur ``meta.ini`` und ``codes.txt`` aus. ``fomod_choices.json``, der
``fomod``-Ordner, Vorschaubilder und Readmes landeten damit im Archiv --
Dateien, die im Spiel ohnehin nichts zu suchen haben.
"""

from pathlib import Path
from types import SimpleNamespace

from anvil.core.ba2_packer import BA2Packer

VERWALTUNG = [
    "meta.ini",
    "codes.txt",
    "fomod_choices.json",
    "fomod/ModuleConfig.xml",
    "FOMOD/info.xml",
    "vorschau.png",
    "liesmich.txt",
    "Thumbs.db",
]

INHALT = [
    "meshes/koerper.nif",
    "scripts/foo.pex",
    "sound/stimme.wav",
]

TEXTUREN = ["textures/haut.dds"]


def _packer(tmp_path: Path) -> BA2Packer:
    plugin = SimpleNamespace(
        GameDataPath="Data",
        Ba2LoosePaths=[],
        gameDirectory=lambda: tmp_path / "Spiel",
    )
    return BA2Packer(plugin, tmp_path / "Instanz")


def _mod(tmp_path: Path) -> Path:
    mod = tmp_path / "Mod"
    for rel in VERWALTUNG + INHALT + TEXTUREN:
        ziel = mod / rel
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"x")
    return mod


def test_verwaltungsdateien_landen_nicht_im_archiv(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    allgemein, texturen, uebersprungen = _packer(tmp_path)._stage_mod_files(
        _mod(tmp_path), staging)

    gepackt = sorted(
        p.relative_to(staging).as_posix()
        for p in staging.rglob("*") if p.is_file()
    )
    for rel in VERWALTUNG:
        assert not any(rel.lower() in g.lower() for g in gepackt), (
            f"{rel} ist im Archiv gelandet: {gepackt}"
        )

    assert allgemein == len(INHALT), gepackt
    assert texturen == len(TEXTUREN), gepackt
    assert uebersprungen == len(VERWALTUNG)


def test_spielinhalt_wird_weiter_gepackt(tmp_path: Path) -> None:
    """Gegenprobe -- ein zu breiter Filter wuerde sonst nicht auffallen."""
    staging = tmp_path / "staging"
    _packer(tmp_path)._stage_mod_files(_mod(tmp_path), staging)

    for rel in INHALT:
        assert (staging / "general" / rel).is_file(), f"{rel} fehlt im Archiv"
    for rel in TEXTUREN:
        assert (staging / "textures" / rel).is_file(), f"{rel} fehlt im Archiv"
