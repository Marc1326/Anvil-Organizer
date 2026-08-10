"""S.T.A.L.K.E.R. 2 kennt drei Mod-Arten mit drei Zielen.

Pak-Mods gehoeren nach ``Content/Paks/~mods``, Blueprint-Mods nach
``Content/Paks/LogicMods``, Loader und DLL-Mods nach ``Binaries/Win64``.
Landet eine Datei im falschen Ordner, wirkt die Mod nicht -- ohne
Fehlermeldung.
"""

from pathlib import Path

from anvil.core.mod_deployer import (
    has_deploy_anchor,
    route_deploy_path,
    strip_deploy_prefixes,
)
from anvil.plugins.games.game_stalker2 import Stalker2Game

S2 = Stalker2Game


def _ziel(rel: str, mount: str = "") -> str:
    """Fahrt die Routenlogik des Plugins ueber einen Mod-Pfad."""
    p = strip_deploy_prefixes(Path(rel), S2.GameDeployStripPrefixes)
    if not has_deploy_anchor(p, S2.GameDeployAnchors):
        p = route_deploy_path(p, S2.GameDeployRoutes, mount)
    return str(p).replace("\\", "/")


def test_pak_mod_landet_in_mods() -> None:
    for datei in ("MeineMod_P.pak", "MeineMod_P.ucas", "MeineMod_P.utoc"):
        assert _ziel(datei) == f"Content/Paks/~mods/{datei}"


def test_mods_ordner_im_archiv_verdoppelt_sich_nicht() -> None:
    assert _ziel("~mods/MeineMod_P.pak") == "Content/Paks/~mods/MeineMod_P.pak"


def test_blueprint_mod_am_mount_point() -> None:
    # Am Dateinamen ist ein Blueprint-Mod nicht zu erkennen -- nur der
    # Mount-Point des Containers verraet ihn.
    mount = "../../../Stalker2/Content/Mods/"
    assert _ziel("BpMod_P.pak", mount) == "Content/Paks/LogicMods/BpMod_P.pak"


def test_blueprint_mod_am_logicmods_ordner() -> None:
    assert _ziel("LogicMods/BpMod_P.pak") == "Content/Paks/LogicMods/BpMod_P.pak"


def test_loader_dll_liegt_neben_der_exe() -> None:
    assert _ziel("dwmapi.dll") == "Binaries/Win64/dwmapi.dll"
    assert _ziel("winmm.dll") == "Binaries/Win64/winmm.dll"


def test_ue4ss_behaelt_seinen_unterbau() -> None:
    assert _ziel("ue4ss/Mods/main.lua") == "Binaries/Win64/ue4ss/Mods/main.lua"


def test_dll_plugin_landet_im_plugins_ordner() -> None:
    assert _ziel("plugins/meins.dll") == "Binaries/Win64/plugins/meins.dll"


def test_eigene_struktur_bleibt_unangetastet() -> None:
    pfad = "Content/Paks/LogicMods/BpMod_P.pak"
    assert _ziel(pfad) == pfad


def test_paks_werden_kopiert_nicht_verlinkt() -> None:
    # IO Store folgt keinen Symlinks, und Proton nimmt eine verlinkte
    # DLL nicht als gueltige DLL an.
    assert "Stalker2/Content/Paks" in S2.GameCopyDeployPaths
    assert "Stalker2/Binaries/Win64" in S2.GameCopyDeployPaths


def test_kein_zaehler_vor_pak_dateien() -> None:
    # Der Zaehler wuerde auch die Paks in LogicMods treffen -- dort sucht
    # UE4SS seinen Blueprint am Dateinamen.
    assert S2.GamePakLoadOrderPrefix is False


def test_dll_overrides_fuer_die_loader() -> None:
    overrides = S2.GameProtonDllOverrides
    for dll in ("dwmapi", "winmm", "xinput1_3"):
        assert overrides.get(dll) == "native,builtin"


def test_uetools_ist_kein_framework() -> None:
    # Eingestellt mit Spiel-Patch 1.6; der Autor verweist selbst auf
    # UE4SS und den Simple BP ModLoader.
    namen = {fw.name.lower() for fw in Stalker2Game().get_framework_mods()}
    assert "uetools" not in namen
    assert {"ue4ss", "simple bp modloader", "dll plugin loader"} <= namen
