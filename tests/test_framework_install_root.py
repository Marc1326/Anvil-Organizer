"""Frameworks, die ihre Zielstruktur selbst mitbringen.

Manche Loader werden ab Spielwurzel gepackt und verteilen sich ueber
mehrere Zweige -- UE4SS und CNS legen sowohl nach ``SB/Binaries/Win64``
als auch nach ``SB/Content/Paks`` ab.  Wer nur in den Ordner mit der
Musterdatei einsteigt, laesst den zweiten Zweig liegen.
"""

from pathlib import Path

from anvil.core.mod_installer import ModInstaller
from anvil.plugins.games.game_stellarblade import StellarBladeGame


def _dateien(basis: Path, pfade: list[str]) -> None:
    for p in pfade:
        ziel = basis / p
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text("x")


# ── Die Wurzelsuche ────────────────────────────────────────────────────

def test_zielpfad_liegt_an_der_archivwurzel(tmp_path: Path) -> None:
    _dateien(tmp_path, ["SB/Binaries/Win64/dwmapi.dll"])
    assert ModInstaller._root_holding_target(tmp_path, "SB/Binaries/Win64") == tmp_path


def test_zielpfad_steckt_in_einem_verpackungsordner(tmp_path: Path) -> None:
    _dateien(tmp_path, ["UE4SS v1.3/SB/Binaries/Win64/dwmapi.dll"])
    got = ModInstaller._root_holding_target(tmp_path, "SB/Binaries/Win64")
    assert got == tmp_path / "UE4SS v1.3"


def test_grossschreibung_bleibt_erhalten(tmp_path: Path) -> None:
    """Der Vergleich laeuft kleingeschrieben -- der Pfad darf es nicht."""
    _dateien(tmp_path, ["Wrapper/sb/binaries/WIN64/dwmapi.dll"])
    got = ModInstaller._root_holding_target(tmp_path, "SB/Binaries/Win64")
    assert got == tmp_path / "Wrapper"
    assert got.is_dir()


def test_ohne_zielpfad_im_archiv_kein_treffer(tmp_path: Path) -> None:
    _dateien(tmp_path, ["bin/ScriptHook.dll"])
    assert ModInstaller._root_holding_target(tmp_path, "SB/Binaries/Win64") is None


def test_leeres_ziel_wird_nicht_gesucht(tmp_path: Path) -> None:
    _dateien(tmp_path, ["irgendwas.dll"])
    assert ModInstaller._root_holding_target(tmp_path, "") is None


def test_wurzelnaechster_kandidat_gewinnt(tmp_path: Path) -> None:
    """Ein zweiter Ordner gleichen Namens tiefer im Baum darf nicht siegen."""
    _dateien(tmp_path, [
        "SB/Binaries/Win64/dwmapi.dll",
        "SB/Binaries/Win64/ue4ss/Mods/Beispiel/SB/Binaries/Win64/nichts.txt",
    ])
    assert ModInstaller._root_holding_target(tmp_path, "SB/Binaries/Win64") == tmp_path


# ── Die Installation ───────────────────────────────────────────────────

def _instanz(tmp_path: Path) -> tuple[ModInstaller, Path]:
    instance = tmp_path / "Instance"
    (instance / ".profiles").mkdir(parents=True)
    game = tmp_path / "Game"
    game.mkdir()
    return ModInstaller(instance), game


def test_zweiter_zweig_geht_nicht_verloren(tmp_path: Path) -> None:
    """Der Fall UE4SS/CNS: Binaries und Content im selben Archiv."""
    installer, game = _instanz(tmp_path)
    temp = tmp_path / "temp"
    _dateien(temp, [
        "SB/Binaries/Win64/dwmapi.dll",
        "SB/Binaries/Win64/ue4ss/UE4SS.dll",
        "SB/Binaries/Win64/ue4ss/Mods/DekCNS/Scripts/main.lua",
        "SB/Content/Paks/LogicMods/DekCNS_P.pak",
    ])
    fw = StellarBladeGame().get_framework_mods()[0]

    installer.install_framework(temp, fw, game)

    assert (game / "SB/Binaries/Win64/dwmapi.dll").is_file(), "Loader fehlt"
    assert (game / "SB/Binaries/Win64/ue4ss/UE4SS.dll").is_file(), "ue4ss/ wurde flachgelegt"
    assert (game / "SB/Content/Paks/LogicMods/DekCNS_P.pak").is_file(), "zweiter Zweig fehlt"


def test_archiv_ohne_zielstruktur_landet_trotzdem_richtig(tmp_path: Path) -> None:
    """Ohne ``SB/Binaries/Win64`` im Archiv greift der bisherige Weg --
    der ``ue4ss``-Ordner muss dabei erhalten bleiben, dort sucht der
    Loader seine Dateien."""
    installer, game = _instanz(tmp_path)
    temp = tmp_path / "temp"
    _dateien(temp, ["ue4ss/UE4SS.dll", "ue4ss/UE4SS-settings.ini"])
    fw = StellarBladeGame().get_framework_mods()[0]

    installer.install_framework(temp, fw, game)

    assert (game / "SB/Binaries/Win64/ue4ss/UE4SS.dll").is_file()


# ── Die Erkennung ──────────────────────────────────────────────────────

def test_cns_gilt_nicht_mehr_als_ue4ss() -> None:
    """CNS bringt eine UE4SS-settings.ini mit -- das reicht nicht."""
    inhalt = [
        "SB/Binaries/Win64/ue4ss/UE4SS-settings.ini",
        "SB/Binaries/Win64/ue4ss/Mods/DekCNS/Scripts/main.lua",
        "SB/Content/Paks/LogicMods/DekCNS_P.pak",
    ]
    fw = StellarBladeGame().is_framework_mod(inhalt)
    assert fw is not None
    assert fw.name == "Custom Nanosuit System"


def test_ue4ss_wird_an_der_dll_erkannt() -> None:
    inhalt = [
        "SB/Binaries/Win64/dwmapi.dll",
        "SB/Binaries/Win64/ue4ss/UE4SS.dll",
    ]
    fw = StellarBladeGame().is_framework_mod(inhalt)
    assert fw is not None
    assert fw.name == "UE4SS"


def test_cns_beispielmod_bleibt_eine_normale_mod() -> None:
    inhalt = [
        "Content/Paks/~mods/CustomNanosuitSystem/DekCNS-SkinSuit_P.pak",
        "Content/Paks/~mods/CustomNanosuitSystem/DekCNS-SkinSuit.dekcns.json",
    ]
    assert StellarBladeGame().is_framework_mod(inhalt) is None
