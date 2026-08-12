"""Die Ladereihenfolge muss im Spiel ankommen, nicht nur in Anvil stehen.

Cyberpunk liest ``archive/pc/mod/modlist.txt`` und laedt die Archive
genau in dieser Folge. Ohne die Datei geht es alphabetisch nach
Dateiname -- dann ist das Verschieben in der Mod-Liste reine Anzeige.

Der Deployer konnte das immer. Nur gab niemand den Dateinamen aus dem
Spiel-Plugin an ihn weiter, und ohne ihn stieg die Funktion sofort aus.
"""

from pathlib import Path

from anvil.core.mod_deployer import ModDeployer
from anvil.core.mod_list_io import write_active_mods, write_global_modlist

PANEL = Path("anvil/widgets/game_panel.py").read_text(encoding="utf-8")


# ── Verkabelung ──────────────────────────────────────────────────────


def test_panel_liest_den_dateinamen_aus_dem_plugin() -> None:
    assert 'getattr(plugin, "GameArchiveLoadOrderFile", "")' in PANEL


def test_panel_reicht_ihn_an_den_deployer_weiter() -> None:
    # Genau diese Zeile fehlte: das Plugin sagte es, der Deployer konnte
    # es, aber dazwischen kam nichts an.
    assert "archive_load_order_file=archive_order_file," in PANEL


def test_cyberpunk_kennt_seine_reihenfolgedatei() -> None:
    from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game

    assert Cyberpunk2077Game().GameArchiveLoadOrderFile == "archive/pc/mod/modlist.txt"


# ── Wirkung ──────────────────────────────────────────────────────────


def _instanz(tmp_path: Path, mods: list[tuple[str, str]]) -> tuple[Path, Path]:
    """Legt Instanz und Spielordner an. *mods* ist [(Ordner, Archivname)]."""
    inst = tmp_path / "instanz"
    spiel = tmp_path / "spiel"
    (spiel / "archive" / "pc" / "mod").mkdir(parents=True)
    mods_dir = inst / ".mods"
    profile = inst / ".profiles"
    profile.mkdir(parents=True)

    for ordner, datei in mods:
        ziel = mods_dir / ordner / "archive" / "pc" / "mod"
        ziel.mkdir(parents=True)
        (ziel / datei).write_bytes(b"\x00" * 8)

    (profile / "Default").mkdir()
    namen = [o for o, _ in mods]
    write_global_modlist(profile, namen)
    write_active_mods(profile / "Default", set(namen))
    return inst, spiel


def _deploy(inst: Path, spiel: Path, datei: str = "archive/pc/mod/modlist.txt"):
    d = ModDeployer(
        inst, spiel,
        mods_path=inst / ".mods",
        profiles_path=inst / ".profiles",
        archive_load_order_file=datei,
    )
    return d, d.deploy()


def test_datei_entsteht_mit_der_reihenfolge_aus_anvil(tmp_path: Path) -> None:
    # Oben in der Liste = hoechste Prioritaet = laedt zuletzt = gewinnt.
    inst, spiel = _instanz(tmp_path, [
        ("Oberste Mod", "zzz_unten_im_alphabet.archive"),
        ("Unterste Mod", "aaa_oben_im_alphabet.archive"),
    ])
    _deploy(inst, spiel)

    liste = spiel / "archive" / "pc" / "mod" / "modlist.txt"
    assert liste.is_file(), "ohne diese Datei laedt das Spiel alphabetisch"

    zeilen = [z for z in liste.read_text(encoding="utf-8").splitlines() if z.strip()]
    assert zeilen == [
        "aaa_oben_im_alphabet.archive",   # unterste Mod zuerst
        "zzz_unten_im_alphabet.archive",  # oberste zuletzt -> gewinnt
    ], "die Reihenfolge aus Anvil muss die alphabetische ueberstimmen"


def test_ohne_angabe_entsteht_keine_datei(tmp_path: Path) -> None:
    # Spiele ohne solche Datei duerfen keine bekommen.
    inst, spiel = _instanz(tmp_path, [("Eine Mod", "a.archive")])
    _deploy(inst, spiel, datei="")

    assert not (spiel / "archive" / "pc" / "mod" / "modlist.txt").exists()


def test_von_hand_hineingelegte_archive_bleiben_geladen(tmp_path: Path) -> None:
    # Sobald die Datei existiert, laedt das Spiel NUR noch was drinsteht.
    # Fremde Archive muessten sonst stillschweigend verschwinden.
    inst, spiel = _instanz(tmp_path, [("Eine Mod", "verwaltet.archive")])
    fremd = spiel / "archive" / "pc" / "mod" / "vonhand.archive"
    fremd.write_bytes(b"\x00")

    _deploy(inst, spiel)

    zeilen = (spiel / "archive" / "pc" / "mod" / "modlist.txt").read_text(
        encoding="utf-8").split()
    assert "vonhand.archive" in zeilen
    assert zeilen.index("vonhand.archive") < zeilen.index("verwaltet.archive"), (
        "fremde Archive gehoeren nach vorn -- verwaltete sollen sie ueberschreiben"
    )


def test_datei_verschwindet_beim_aufraeumen(tmp_path: Path) -> None:
    inst, spiel = _instanz(tmp_path, [("Eine Mod", "a.archive")])
    d, _ = _deploy(inst, spiel)
    liste = spiel / "archive" / "pc" / "mod" / "modlist.txt"
    assert liste.is_file()

    d.purge()

    assert not liste.exists(), "sonst laedt das Spiel danach gar keine Mods mehr"


# ── STALKER 2: derselbe Fehler an anderer Stelle ─────────────────────


def test_stalker2_ordnerbegrenzung_wird_weitergereicht() -> None:
    # Das Plugin schaltet das Umbenennen bewusst nur fuer ~mods frei.
    # Ohne diese Zeile kam die Begrenzung nie an -- und damit auch die
    # Reihenfolge nicht, denn ohne Ordner passiert gar nichts.
    assert 'getattr(plugin, "GamePakLoadOrderDirs", [])' in PANEL
    assert "pak_load_order_dirs=pak_order_dirs," in PANEL


def test_stalker2_nummeriert_nur_in_mods(tmp_path: Path) -> None:
    from anvil.plugins.games.game_stalker2 import Stalker2Game

    spiel = Stalker2Game()
    assert spiel.GamePakLoadOrderDirs == ["Stalker2/Content/Paks/~mods"]
    # LogicMods darf nicht mit: dort sucht UE4SS den Blueprint am Namen.
    assert not any("LogicMods" in d for d in spiel.GamePakLoadOrderDirs)


def test_stellar_blade_bleibt_bewusst_aus() -> None:
    # Die Autoren verbieten das Umbenennen ausdruecklich.
    from anvil.plugins.games.game_stellarblade import StellarBladeGame

    spiel = StellarBladeGame()
    assert spiel.GamePakLoadOrderPrefix is False
    assert not getattr(spiel, "GamePakLoadOrderDirs", [])
