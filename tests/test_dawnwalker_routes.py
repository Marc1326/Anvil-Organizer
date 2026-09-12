"""The Blood of Dawnwalker kennt vier Mod-Arten mit vier Zielen.

Pak-Mods gehoeren nach ``Content/Paks/~mods``, Blueprint-Mods nach
``Content/Paks/LogicMods``, UE4SS samt Lua-Mods nach ``Binaries/Win64``,
und der SML-Loader direkt nach ``Content/Paks``. Landet eine Datei im
falschen Ordner, wirkt die Mod nicht -- ohne Fehlermeldung.
"""

from pathlib import Path

from anvil.core.deploy_rules import is_metadata_rel
from anvil.core.mod_deployer import (
    has_deploy_anchor,
    route_deploy_path,
    strip_deploy_prefixes,
)
from anvil.plugins.games.game_dawnwalker import DawnwalkerGame

DW = DawnwalkerGame


def _ziel(rel: str, mount: str = "") -> str:
    """Faehrt die Routenlogik des Plugins ueber einen Mod-Pfad."""
    p = strip_deploy_prefixes(Path(rel), DW.GameDeployStripPrefixes)
    if not has_deploy_anchor(p, DW.GameDeployAnchors):
        p = route_deploy_path(p, DW.GameDeployRoutes, mount)
    return str(p).replace("\\", "/")


def test_pak_mod_landet_in_mods() -> None:
    for datei in ("MeineMod_P.pak", "MeineMod_P.ucas", "MeineMod_P.utoc"):
        assert _ziel(datei) == f"Content/Paks/~mods/{datei}"


def test_mods_ordner_im_archiv_verdoppelt_sich_nicht() -> None:
    assert _ziel("~mods/MeineMod_P.pak") == "Content/Paks/~mods/MeineMod_P.pak"


def test_blueprint_mod_am_mount_point() -> None:
    mount = "../../../Dawnwalker/Content/Mods/"
    assert _ziel("BpMod_P.pak", mount) == "Content/Paks/LogicMods/BpMod_P.pak"


def test_blueprint_mod_am_logicmods_ordner() -> None:
    assert _ziel("LogicMods/BpMod_P.pak") == "Content/Paks/LogicMods/BpMod_P.pak"


def test_sml_loader_liegt_direkt_in_paks() -> None:
    # In ~mods wuerde der Loader nicht geladen.
    for datei in ("SML.pak", "SML.utoc", "SML.ucas"):
        assert _ziel(datei) == f"Content/Paks/{datei}"


def test_ue4ss_paket_wie_von_nexus() -> None:
    # Genau die Struktur des Nexus-Pakets: dwmapi.dll neben der Exe,
    # alles Weitere unter ue4ss/. Die Textdateien im Wurzelverzeichnis
    # bleiben draussen.
    assert _ziel("dwmapi.dll") == "Binaries/Win64/dwmapi.dll"
    assert _ziel("ue4ss/UE4SS.dll") == "Binaries/Win64/ue4ss/UE4SS.dll"
    assert _ziel("ue4ss/UE4SS-settings.ini") == "Binaries/Win64/ue4ss/UE4SS-settings.ini"
    assert (
        _ziel("ue4ss/Mods/BPModLoaderMod/Scripts/main.lua")
        == "Binaries/Win64/ue4ss/Mods/BPModLoaderMod/Scripts/main.lua"
    )
    for txt in ("README.txt", "SHA256SUMS.txt", "THIRD_PARTY_NOTICES.txt"):
        assert is_metadata_rel(txt)


def test_lua_mod_ohne_praefix_landet_bei_ue4ss() -> None:
    assert (
        _ziel("Mods/DawnWALKING/Scripts/main.lua")
        == "Binaries/Win64/ue4ss/Mods/DawnWALKING/Scripts/main.lua"
    )


def test_sml_mod_bringt_seine_struktur_mit() -> None:
    # Nexus liefert SML-Mods als Dawnwalker/Mods/<Name>/ -- der Anker
    # sorgt dafuer, dass ihre Paks nicht in ~mods umsortiert werden.
    # Eine .ini allein beweist das nicht, die faellt durch jede Route.
    for pfad in (
        "Dawnwalker/Mods/ForceFPS/ForceFPS_P.pak",
        "Dawnwalker/Mods/ForceFPS/config/Engine.ini",
    ):
        assert _ziel(pfad) == pfad


def test_eigene_struktur_bleibt_unangetastet() -> None:
    pfad = "Content/Paks/LogicMods/BpMod_P.pak"
    assert _ziel(pfad) == pfad


def test_paks_werden_kopiert_nicht_verlinkt() -> None:
    # IO Store folgt keinen Symlinks, und Proton nimmt eine verlinkte
    # DLL nicht als gueltige DLL an. Mods/ gehoert dazu: die Paks der
    # SML-Mods liegen dort und werden genauso geladen.
    for pfad in (
        "Dawnwalker/Content/Paks",
        "Dawnwalker/Binaries/Win64",
        "Dawnwalker/Mods",
    ):
        assert pfad in DW.GameCopyDeployPaths


def test_zaehler_nur_in_mods() -> None:
    # Ohne Zaehler waere die Sortierung aus Anvil in ~mods wirkungslos.
    # Ueberall sonst wuerde er die Loader unbrauchbar machen: UE4SS sucht
    # seinen Blueprint am Dateinamen, SML heisst fest SML.*.
    assert DW.GamePakLoadOrderPrefix is False
    assert DW.GamePakLoadOrderDirs == ["Dawnwalker/Content/Paks/~mods"]


def test_dll_override_fuer_ue4ss() -> None:
    assert DW.GameProtonDllOverrides.get("dwmapi") == "native,builtin"


def test_frameworks_und_ihre_ziele() -> None:
    fws = {fw.name: fw for fw in DawnwalkerGame().get_framework_mods()}
    assert fws["UE4SS"].target == "Dawnwalker/Binaries/Win64"
    assert "Dawnwalker/Binaries/Win64/dwmapi.dll" in fws["UE4SS"].detect_installed
    sml = fws["Console Enabler and Mod Loader"]
    assert sml.target == "Dawnwalker/Content/Paks"
    assert "Dawnwalker/Content/Paks/SML.pak" in sml.detect_installed


def test_mod_ordner_sind_reine_mod_ablagen() -> None:
    # Paks selbst enthaelt die Spieldaten und darf nie dabei sein.
    assert "Dawnwalker/Content/Paks" not in DW.GameModDirs
    assert "Dawnwalker/Mods" in DW.GameModDirs
    assert "Dawnwalker/Binaries/Win64/ue4ss/Mods" in DW.GameModDirs
