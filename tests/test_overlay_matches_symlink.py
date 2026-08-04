"""Vergleicht den Overlay-Weg mit dem Symlink-Weg.

Beide muessen dieselbe Sicht erzeugen. Weicht ein Zielpfad ab, ist eine
Pfadregel im Staging vergessen worden -- genau die Fehlerklasse, die sich
sonst erst im Spiel zeigt.

Bezugspunkt ist der Symlink-Deployer: was der ins Spiel legt, muss der
Overlay in seine Schichten legen.
"""

from pathlib import Path

import pytest

from anvil.core.mod_deployer import ModDeployer
from anvil.core.mod_list_io import write_active_mods, write_global_modlist
from anvil.core.overlay_deployer import OverlayDeployer


@pytest.fixture
def ohne_umgebungspruefung(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(OverlayDeployer, "check_requirements", lambda self: [])


def _schreibe(base: Path, rel: str, text: str = "x") -> None:
    target = base / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _welt(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    instance = tmp_path / "Instance"
    game = tmp_path / "Game"
    instance.mkdir()
    game.mkdir()
    mods = instance / ".mods"
    profiles = instance / ".profiles"
    (profiles / "Default").mkdir(parents=True)
    mods.mkdir()
    return instance, game, mods, profiles


def symlink_ziele(deployer: ModDeployer, mods: Path) -> set[str]:
    """Was der Symlink-Deployer ins Spiel legen wuerde, als Pfadmenge.

    Ordner-Symlinks (LML, REDmod) werden auf ihre Dateien aufgeklappt --
    der Overlay legt dort einzelne Dateien ab, nicht einen Ordner.
    """
    import json

    manifest = json.loads(deployer._manifest_path.read_text(encoding="utf-8"))
    ziele: set[str] = set()
    for entry in manifest.get("symlinks", []):
        link = entry.get("link", "")
        basis = entry.get("deploy_base", "")
        praefix = f"{basis}::" if basis else ""
        if entry.get("type") == "dir_symlink":
            quelle = Path(entry["target"])
            for datei in quelle.rglob("*"):
                if datei.is_file():
                    ziele.add(praefix + str(Path(link) / datei.relative_to(quelle)))
        else:
            ziele.add(praefix + link)
    return ziele


def overlay_ziele(deployer: OverlayDeployer) -> set[str]:
    """Was der Overlay in seine Schichten gelegt hat, als Pfadmenge."""
    ziele: set[str] = set()
    for basis, schicht in deployer.stage_dirs().items():
        praefix = f"{basis}::" if basis else ""
        for datei in schicht.rglob("*"):
            if datei.is_file():
                ziele.add(praefix + str(datei.relative_to(schicht)))
    return ziele


def _vergleiche(
    tmp_path: Path,
    mod_dateien: dict[str, list[str]],
    aktiv: set[str] | None = None,
    reihenfolge: list[str] | None = None,
    **plugin_angaben,
) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    for name, dateien in mod_dateien.items():
        for rel in dateien:
            _schreibe(mods / name, rel)

    namen = reihenfolge or list(mod_dateien)
    write_global_modlist(profiles, namen)
    write_active_mods(profiles / "Default", aktiv if aktiv is not None else set(namen))

    symlink = ModDeployer(instance, game, **plugin_angaben)
    symlink.deploy()
    erwartet = symlink_ziele(symlink, mods)

    overlay = OverlayDeployer(instance, game, **plugin_angaben)
    overlay.deploy()
    bekommen = overlay_ziele(overlay)

    fehlend = erwartet - bekommen
    zuviel = bekommen - erwartet
    assert not fehlend, f"im Overlay fehlen: {sorted(fehlend)}"
    assert not zuviel, f"im Overlay zu viel: {sorted(zuviel)}"


# ── Die Pfadregeln, einzeln ────────────────────────────────────────────

def test_einfache_mod(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    _vergleiche(tmp_path, {"M": ["archive/pc/mod/a.archive"]})


def test_root_praefix(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    _vergleiche(
        tmp_path,
        {"RED4ext": ["root/bin/x64/winmm.dll", "red4ext/RED4ext.dll"]},
        direct_install_patterns=["RED4ext"],
    )


def test_data_path(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    _vergleiche(tmp_path, {"M": ["meshes/a.nif", "Data/textures/b.dds"]}, data_path="Data")


def test_frameworks_neben_normalen_mods(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    _vergleiche(
        tmp_path,
        {"SKSE64": ["root/skse64_loader.exe"], "Normal": ["meshes/a.nif"]},
        data_path="Data",
        direct_install_patterns=["SKSE64"],
    )


def test_nest_unter_modname(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    _vergleiche(
        tmp_path,
        {"Mein Mod": ["a.esp"]},
        data_path="Data",
        nest_under_mod_name=True,
    )


def test_multi_folder_routen(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    _vergleiche(
        tmp_path,
        {"W3": ["mods/modXY/content/blob.bundle", "dlc/dlcXY/content/blob.bundle"]},
        data_path="Mods",
        multi_folder_routes={"mods": "Mods", "dlc": "DLC", "bin": "bin"},
    )


def test_metadaten_bleiben_beidseitig_draussen(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    _vergleiche(
        tmp_path,
        {"M": ["meta.ini", "liesmich.txt", "vorschau.png", "fomod/info.xml", "archive/a.archive"]},
    )


def test_lml_ordner(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    _vergleiche(
        tmp_path,
        {"LennysMod": ["install.xml", "content/a.bin", "unter/b.bin"]},
        lml_path="lml",
    )


def test_redmod_muster_a(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    _vergleiche(
        tmp_path,
        {"EinRedmod": ["info.json", "archives/a.archive"]},
        redmod_path="mods",
    )


def test_redmod_muster_c(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    _vergleiche(
        tmp_path,
        {"Sammlung": ["TeilA/info.json", "TeilA/archives/a.archive",
                      "TeilB/info.json", "TeilB/archives/b.archive"]},
        redmod_path="mods",
    )


def test_redmod_muster_b_bleibt_normal(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    _vergleiche(
        tmp_path,
        {"MitModsOrdner": ["mods/Name/info.json", "mods/Name/archives/a.archive"]},
        redmod_path="mods",
    )


def test_separator_zielpfad(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    anderswo = tmp_path / "Anderswo"
    anderswo.mkdir()

    _schreibe(mods / "Woanders", "archive/a.archive")
    _schreibe(mods / "Normal", "archive/b.archive")
    write_global_modlist(profiles, ["extern_separator", "Woanders", "haupt_separator", "Normal"])
    write_active_mods(
        profiles / "Default",
        {"extern_separator", "Woanders", "haupt_separator", "Normal"},
    )

    pfade = {"extern_separator": str(anderswo)}

    symlink = ModDeployer(instance, game, separator_deploy_paths=pfade)
    symlink.deploy()
    erwartet = symlink_ziele(symlink, mods)

    overlay = OverlayDeployer(instance, game, separator_deploy_paths=pfade)
    overlay.deploy()
    bekommen = overlay_ziele(overlay)

    assert erwartet == bekommen, (
        f"fehlt: {sorted(erwartet - bekommen)}  zu viel: {sorted(bekommen - erwartet)}"
    )


def test_prioritaet_gleicher_pfad(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    instance, game, mods, profiles = _welt(tmp_path)
    _schreibe(mods / "Oben", "archive/a.archive", "oben")
    _schreibe(mods / "Unten", "archive/a.archive", "unten")
    write_global_modlist(profiles, ["Oben", "Unten"])
    write_active_mods(profiles / "Default", {"Oben", "Unten"})

    symlink = ModDeployer(instance, game)
    symlink.deploy()
    gewinner_symlink = (game / "archive" / "a.archive").read_text(encoding="utf-8")

    overlay = OverlayDeployer(instance, game)
    overlay.deploy()
    gewinner_overlay = (overlay.stage_dir / "archive" / "a.archive").read_text(encoding="utf-8")

    assert gewinner_symlink == "oben"
    assert gewinner_overlay == gewinner_symlink


def test_ba2_filter_wie_beim_symlink_weg(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    """Bei aktivem Archiv-Packen laesst auch der Overlay dieselben Dateien weg."""
    _vergleiche(
        tmp_path,
        {"M": [
            "meshes/a.nif",          # wird gepackt
            "textures/b.dds",        # wird gepackt
            "a.esp",                 # bleibt lose
            "SKSE/Plugins/c.dll",    # bleibt lose
            "d.ini",                 # bleibt lose
        ]},
        data_path="Data",
        needs_ba2_packing=True,
    )


def test_ohne_packen_bleibt_alles_lose(tmp_path: Path, ohne_umgebungspruefung: None) -> None:
    _vergleiche(
        tmp_path,
        {"M": ["meshes/a.nif", "textures/b.dds", "a.esp"]},
        data_path="Data",
        needs_ba2_packing=False,
    )
