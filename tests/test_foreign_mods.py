"""Von Hand installierte Mods sind sonst unsichtbar.

Anvil raeumt nur weg, was es selbst ausgerollt hat. Eine Datei, die
jemand direkt in den Spielordner kopiert, laedt deshalb bei jedem Start
und ist ueber die Mod-Liste nicht abschaltbar. Genau solche Funde soll
dieses Modul finden -- und keine Fehlalarme produzieren.
"""

import json
from pathlib import Path

import pytest

from anvil.core.foreign_mods import (
    DISABLED_SUFFIX,
    deployed_paths,
    scan,
    scan_instance,
    set_enabled,
)

MOD_DIRS = ["archive/pc/mod", "mods"]


def _spiel(tmp_path: Path) -> Path:
    spiel = tmp_path / "game"
    (spiel / "archive/pc/mod").mkdir(parents=True)
    (spiel / "mods").mkdir(parents=True)
    return spiel


def _manifest(tmp_path: Path, links: list[str]) -> Path:
    pfad = tmp_path / ".deploy_manifest.json"
    pfad.write_text(json.dumps({
        "symlinks": [{"link": p, "mod": "x", "type": "symlink"} for p in links],
        "created_dirs": [],
    }), encoding="utf-8")
    return pfad


def test_handkopierte_datei_wird_gefunden(tmp_path: Path) -> None:
    spiel = _spiel(tmp_path)
    (spiel / "archive/pc/mod/fremd.archive").write_bytes(b"x")

    funde = scan(spiel, MOD_DIRS, deployed=set())

    assert [f.rel for f in funde] == ["archive/pc/mod/fremd.archive"]
    assert funde[0].enabled is True
    assert funde[0].is_dir is False


def test_von_anvil_ausgerollte_datei_ist_kein_fund(tmp_path: Path) -> None:
    spiel = _spiel(tmp_path)
    (spiel / "archive/pc/mod/meine.archive").write_bytes(b"x")

    funde = scan(spiel, MOD_DIRS, deployed={"archive/pc/mod/meine.archive"})

    assert funde == []


def test_ordner_mod_zaehlt_ueber_ihren_inhalt_als_verwaltet(tmp_path: Path) -> None:
    # REDmod- und CET-Mods sind Ordner. Im Manifest stehen die Dateien
    # darin, nicht der Ordner selbst -- sonst gaebe es Fehlalarme.
    spiel = _spiel(tmp_path)
    (spiel / "mods/meineredmod").mkdir()
    (spiel / "mods/meineredmod/info.json").write_text("{}")

    funde = scan(spiel, MOD_DIRS, deployed={"mods/meineredmod/info.json"})

    assert funde == []


def test_fremder_ordner_wird_gefunden(tmp_path: Path) -> None:
    spiel = _spiel(tmp_path)
    (spiel / "mods/handarbeit").mkdir()

    funde = scan(spiel, MOD_DIRS, deployed=set())

    assert [f.rel for f in funde] == ["mods/handarbeit"]
    assert funde[0].is_dir is True


def test_abgeschalteter_fund_bleibt_sichtbar(tmp_path: Path) -> None:
    spiel = _spiel(tmp_path)
    (spiel / f"archive/pc/mod/fremd.archive{DISABLED_SUFFIX}").write_bytes(b"x")

    funde = scan(spiel, MOD_DIRS, deployed=set())

    assert len(funde) == 1
    assert funde[0].rel == "archive/pc/mod/fremd.archive"
    assert funde[0].enabled is False


def test_fehlender_ordner_stoert_nicht(tmp_path: Path) -> None:
    spiel = tmp_path / "game"
    spiel.mkdir()

    assert scan(spiel, MOD_DIRS, deployed=set()) == []


def test_ohne_manifest_wird_nichts_gemeldet(tmp_path: Path) -> None:
    # Nach dem Aufraeumen bleiben Frameworks absichtlich liegen. Ohne
    # Vergleichsliste waeren sie von Handarbeit nicht zu unterscheiden --
    # dann lieber schweigen als zwei Dutzend Fehlalarme.
    spiel = _spiel(tmp_path)
    (spiel / "archive/pc/mod/framework.archive").write_bytes(b"x")

    funde = scan_instance(spiel, MOD_DIRS, tmp_path / "fehlt.json")

    assert funde == []


def test_mit_manifest_wird_gemeldet(tmp_path: Path) -> None:
    spiel = _spiel(tmp_path)
    (spiel / "archive/pc/mod/meine.archive").write_bytes(b"x")
    (spiel / "archive/pc/mod/fremd.archive").write_bytes(b"x")
    manifest = _manifest(tmp_path, ["archive/pc/mod/meine.archive"])

    funde = scan_instance(spiel, MOD_DIRS, manifest)

    assert [f.rel for f in funde] == ["archive/pc/mod/fremd.archive"]


def test_manifest_mit_windows_trennern(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, ["archive\\pc\\mod\\meine.archive"])

    assert deployed_paths(manifest) == {"archive/pc/mod/meine.archive"}


def test_kaputtes_manifest_meldet_alles_statt_abzustuerzen(tmp_path: Path) -> None:
    pfad = tmp_path / ".deploy_manifest.json"
    pfad.write_text("{kaputt", encoding="utf-8")

    assert deployed_paths(pfad) == set()


def test_abschalten_benennt_um_statt_zu_loeschen(tmp_path: Path) -> None:
    datei = tmp_path / "fremd.archive"
    datei.write_bytes(b"inhalt")

    neu = set_enabled(datei, False)

    assert not datei.exists()
    assert neu.name == f"fremd.archive{DISABLED_SUFFIX}"
    assert neu.read_bytes() == b"inhalt"


def test_wieder_einschalten(tmp_path: Path) -> None:
    datei = tmp_path / f"fremd.archive{DISABLED_SUFFIX}"
    datei.write_bytes(b"inhalt")

    neu = set_enabled(datei, True)

    assert neu.name == "fremd.archive"
    assert neu.read_bytes() == b"inhalt"


def test_umschalten_auf_den_gleichen_stand_tut_nichts(tmp_path: Path) -> None:
    datei = tmp_path / "fremd.archive"
    datei.write_bytes(b"x")

    assert set_enabled(datei, True) == datei
    assert datei.exists()


def test_bestehende_gegenstelle_wird_nicht_ueberschrieben(tmp_path: Path) -> None:
    # Sonst waere eine der beiden Fassungen unwiederbringlich weg.
    aktiv = tmp_path / "fremd.archive"
    aktiv.write_bytes(b"neu")
    (tmp_path / f"fremd.archive{DISABLED_SUFFIX}").write_bytes(b"alt")

    with pytest.raises(OSError):
        set_enabled(aktiv, False)

    assert aktiv.read_bytes() == b"neu"


def test_plugins_liefern_reine_mod_ordner() -> None:
    from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game
    from anvil.plugins.games.game_stalker2 import Stalker2Game

    assert "archive/pc/mod" in Cyberpunk2077Game.GameModDirs
    assert "Stalker2/Content/Paks/~mods" in Stalker2Game.GameModDirs


def test_fremde_eintraege_landen_nicht_in_der_modliste(tmp_path: Path) -> None:
    # Sonst wuerde Anvil Mods verwalten wollen, die es gar nicht besitzt --
    # und beim naechsten Ausrollen nach .mods/<pfad> suchen.
    import re

    quelle = Path("anvil/mainwindow.py").read_text(encoding="utf-8")

    # Jede Stelle, die aktive Mods einsammelt, muss fremde ausnehmen.
    treffer = re.findall(
        r"for e in self\._current_mod_entries if e\.enabled(?! and not e\.is_foreign)",
        quelle,
    )
    assert treffer == [], f"{len(treffer)} Stelle(n) ohne is_foreign-Filter"

    assert "eigene = [e for e in self._current_mod_entries if not e.is_foreign]" in quelle


def test_kein_mod_ordner_enthaelt_auslieferungsdateien() -> None:
    # Ein Ordner mit Vanilla-Dateien wuerde jede davon als Fund melden.
    # Diese Pfade sind gemischt und duerfen deshalb nie in GameModDirs
    # stehen -- weder als Ganzes noch als Wurzel eines Eintrags.
    from anvil.plugins.plugin_loader import PluginLoader

    verboten = {
        "data", "mods/../data", "sb/content/paks", "archive/pc",
        "stalker2/content/paks", "r5/content/paks", "dlc",
        "bin/x64", "", ".",
    }

    loader = PluginLoader()
    loader.load_plugins()
    plugins = loader.get_games() if hasattr(loader, "get_games") else loader._plugins

    for plugin in plugins:
        for ordner in getattr(plugin, "GameModDirs", []):
            norm = str(ordner).replace("\\", "/").strip("/").lower()
            assert norm not in verboten, (
                f"{plugin.GameShortName}: '{ordner}' enthaelt auch "
                f"Auslieferungsdateien"
            )
            assert norm, f"{plugin.GameShortName}: leerer Eintrag"


def test_stellar_blade_meldet_nicht_die_vanilla_paks() -> None:
    # Der Regressionsfall: Paks/ enthaelt die pakchunks des Spiels, nur
    # die Unterordner sind reine Mod-Ablagen.
    from anvil.plugins.games.game_stellarblade import StellarBladeGame

    assert "SB/Content/Paks" not in StellarBladeGame.GameModDirs
    assert "SB/Content/Paks/~mods" in StellarBladeGame.GameModDirs


def test_massen_umschaltung_fasst_fremde_mods_wirklich_an() -> None:
    # "Alle deaktivieren" lief ueber _ctx_enable_selected und setzte dort
    # nur das Haekchen. Die Datei im Spielordner blieb aktiv, und beim
    # naechsten Laden stand wieder der alte Stand da -- der Haken log.
    quelle = Path("anvil/mainwindow.py").read_text(encoding="utf-8")

    start = quelle.index("def _ctx_enable_selected")
    ende = quelle.index("def _ctx_enable_all")
    block = quelle[start:ende]

    assert "_toggle_foreign_mod" in block, (
        "_ctx_enable_selected schaltet fremde Mods nicht ueber die Datei"
    )


def test_alle_umschalten_erfasst_jede_zeile() -> None:
    # Das Modell ist flach: rowCount() liefert alle Zeilen, auch die unter
    # eingeklappten Trennern. Wuerde es ein Baum, griffe "Alle" nur noch
    # auf die oberste Ebene.
    quelle = Path("anvil/models/mod_list_model.py").read_text(encoding="utf-8")

    assert "return len(self._rows)" in quelle
    assert "def parent(self, index):\n        return QModelIndex()" in quelle
