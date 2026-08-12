"""Cyberpunk: der Dateiname entscheidet, nicht die modlist.txt.

An drei Spielstarts gemessen laedt REDengine die Archive alphabetisch nach
Dateiname und ignoriert ``archive/pc/mod/modlist.txt``. Deshalb bekommen die
Archive beim Ausrollen einen Zaehler -- und zwar umgekehrt herum als bei
Unreal, wo die zuletzt eingehaengte Datei gewinnt.
"""

from pathlib import Path

from anvil.core.mod_deployer import (
    load_order_index, pak_load_order_name, pak_order_allows,
)
from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game as Cyberpunk

ARCHIV = {".archive"}


# ── Richtung ─────────────────────────────────────────────────────────

def test_erste_gewinnt_hoechste_prioritaet_kleinste_zahl():
    """Der Deploy laeuft von unten nach oben: Index 0 ist die schwaechste."""
    gesamt = 10
    schwaechste = load_order_index(0, gesamt, first_wins=True)
    staerkste = load_order_index(gesamt - 1, gesamt, first_wins=True)
    assert staerkste == 0
    assert schwaechste == 9
    assert staerkste < schwaechste


def test_letzte_gewinnt_bleibt_wie_bisher():
    """Unreal: unveraendert, sonst braechen Stellar Blade und STALKER."""
    assert load_order_index(0, 10, first_wins=False) == 0
    assert load_order_index(9, 10, first_wins=False) == 9


def test_leere_liste_bricht_nicht():
    assert load_order_index(0, 0, first_wins=True) == 0


# ── Benennung ────────────────────────────────────────────────────────

def test_archiv_bekommt_zaehler():
    rel = Path("archive/pc/mod/Grace.archive")
    assert pak_load_order_name(rel, 7, ARCHIV).name == "007_Grace.archive"


def test_xl_bleibt_unberuehrt():
    """38 von 85 .xl heissen anders als ihr Archiv -- keine Namensbindung."""
    rel = Path("archive/pc/mod/ib_nipple_shape.archive.xl")
    assert pak_load_order_name(rel, 7, ARCHIV) == rel


def test_breite_wird_eingehalten():
    """"1000_" sortiert vor "999_" -- zu schmal kehrt die Reihenfolge um."""
    rel = Path("archive/pc/mod/A.archive")
    assert pak_load_order_name(rel, 5, ARCHIV, breite=4).name == "0005_A.archive"


def test_zaehler_sortiert_richtig():
    namen = sorted(
        pak_load_order_name(Path(f"a/x{i}.archive"), i, ARCHIV, breite=4).name
        for i in (0, 9, 10, 99, 100, 999, 1000)
    )
    assert namen[0].startswith("0000_")
    assert namen[-1].startswith("1000_")


def test_pak_endungen_ohne_angabe_unveraendert():
    rel = Path("Paks/~mods/Foo_P.pak")
    assert pak_load_order_name(rel, 3).name == "003_Foo_P.pak"


def test_fremde_endung_bleibt():
    rel = Path("archive/pc/mod/liesmich.txt")
    assert pak_load_order_name(rel, 3, ARCHIV) == rel


# ── Nur im richtigen Ordner ──────────────────────────────────────────

def test_nur_der_archivordner():
    erlaubt = Cyberpunk.GamePakLoadOrderDirs
    assert pak_order_allows(Path("archive/pc/mod/A.archive"), erlaubt)
    # REDmod bringt seine eigene Reihenfolge mit
    assert not pak_order_allows(Path("mods/Foo/archives/A.archive"), erlaubt)
    # Loader suchen ihre Dateien am Namen
    assert not pak_order_allows(Path("bin/x64/plugins/A.archive"), erlaubt)
    assert not pak_order_allows(Path("r6/scripts/A.reds"), erlaubt)


# ── Plugin-Einstellungen ─────────────────────────────────────────────

def test_cyberpunk_ist_eingeschaltet():
    assert Cyberpunk.GamePakLoadOrderDirs == ["archive/pc/mod"]
    assert Cyberpunk.GamePakLoadOrderExtensions == [".archive"]
    assert Cyberpunk.GamePakLoadOrderFirstWins is True


def test_unreal_spiele_unveraendert():
    """Ein versehentliches Umschalten wuerde dort die Reihenfolge drehen."""
    from anvil.plugins.games.game_stalker2 import Stalker2Game as Stalker
    from anvil.plugins.games.game_stellarblade import StellarBladeGame as StellarBlade
    for spiel in (Stalker, StellarBlade):
        assert getattr(spiel, "GamePakLoadOrderFirstWins", False) is False


def test_bethesda_bekommt_keinen_zaehler():
    """Dort entscheidet die Plugin-Reihenfolge, nicht der Dateiname."""
    from anvil.plugins.games.game_fallout4 import Fallout4Game as Fallout
    assert not getattr(Fallout, "GamePakLoadOrderDirs", [])
    assert not getattr(Fallout, "GamePakLoadOrderExtensions", [])


# ── Gleichnamige Archive ─────────────────────────────────────────────

class _Ergebnis:
    def __init__(self):
        self.errors = []


def _deployer(tmp_path):
    from anvil.core.mod_deployer import ModDeployer
    spiel = tmp_path / "spiel"
    spiel.mkdir()
    return ModDeployer(
        tmp_path / "inst", spiel,
        pak_load_order_dirs=["archive/pc/mod"],
        pak_load_order_extensions=[".archive"],
        pak_load_order_first_wins=True,
    ), spiel


def test_gleichnamiges_archiv_nur_einmal(tmp_path):
    """Vorher ueberschrieb die hoehere Mod die niedrigere -- eine Datei.

    Mit Zaehler heissen beide anders. Ohne Aufraeumen laegen beide da und
    die schwaechere braechte ihre Inhalte zusaetzlich mit.
    """
    deployer, spiel = _deployer(tmp_path)
    ordner = spiel / "archive/pc/mod"
    ordner.mkdir(parents=True)
    (ordner / "005_Topless.archive").write_text("hoch")
    (ordner / "009_Topless.archive").write_text("niedrig")

    symlinks = [
        {"link": "archive/pc/mod/005_Topless.archive", "type": "symlink",
         "mod": "Hoch", "target": "x",
         "unnumbered": "archive/pc/mod/Topless.archive"},
        {"link": "archive/pc/mod/009_Topless.archive", "type": "symlink",
         "mod": "Niedrig", "target": "y",
         "unnumbered": "archive/pc/mod/Topless.archive"},
    ]
    bleibt = deployer._drop_superseded_numbered(symlinks, _Ergebnis())

    assert [e["mod"] for e in bleibt] == ["Hoch"]
    assert (ordner / "005_Topless.archive").exists()
    assert not (ordner / "009_Topless.archive").exists()


def test_verschiedene_namen_bleiben_beide(tmp_path):
    deployer, spiel = _deployer(tmp_path)
    ordner = spiel / "archive/pc/mod"
    ordner.mkdir(parents=True)
    (ordner / "005_A.archive").write_text("a")
    (ordner / "009_B.archive").write_text("b")

    symlinks = [
        {"link": "archive/pc/mod/005_A.archive", "type": "symlink",
         "mod": "A", "target": "x",
         "unnumbered": "archive/pc/mod/A.archive"},
        {"link": "archive/pc/mod/009_B.archive", "type": "symlink",
         "mod": "B", "target": "y",
         "unnumbered": "archive/pc/mod/B.archive"},
    ]
    bleibt = deployer._drop_superseded_numbered(symlinks, _Ergebnis())
    assert len(bleibt) == 2


def test_ohne_zaehler_wird_nichts_angefasst(tmp_path):
    from anvil.core.mod_deployer import ModDeployer
    spiel = tmp_path / "spiel"
    spiel.mkdir()
    deployer = ModDeployer(tmp_path / "inst", spiel)   # Zaehler aus
    symlinks = [
        {"link": "archive/pc/mod/005_A.archive", "type": "symlink",
         "mod": "A", "target": "x"},
    ]
    assert deployer._drop_superseded_numbered(symlinks, _Ergebnis()) == symlinks


def test_fremde_datei_mit_ziffern_wird_nicht_verwechselt(tmp_path):
    """Eine fremde "00_Foo.archive" ist kein Zaehler und darf nicht weg.

    Am Dateinamen allein waere sie von "005_Foo.archive" nicht zu
    unterscheiden -- deshalb steht der Originalname im Eintrag.
    """
    deployer, spiel = _deployer(tmp_path)
    ordner = spiel / "archive/pc/mod"
    ordner.mkdir(parents=True)
    (ordner / "00_Foo.archive").write_text("fremd")
    (ordner / "005_Foo.archive").write_text("verwaltet")
    symlinks = [
        # ohne "unnumbered": von Hand hineingelegt, nicht von Anvil benannt
        {"link": "archive/pc/mod/00_Foo.archive", "type": "symlink",
         "mod": "A", "target": "x"},
        {"link": "archive/pc/mod/005_Foo.archive", "type": "symlink",
         "mod": "B", "target": "y",
         "unnumbered": "archive/pc/mod/Foo.archive"},
    ]
    bleibt = deployer._drop_superseded_numbered(symlinks, _Ergebnis())
    assert len(bleibt) == 2
    assert (ordner / "00_Foo.archive").exists()
