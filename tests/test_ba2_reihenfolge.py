"""Bethesda laedt das zuletzt eingetragene Archiv zuletzt.

sResourceArchiveList2 wird von links nach rechts abgearbeitet, der letzte
Eintrag gewinnt. Die Mod-Liste ging ungedreht ins Packen, damit stand das
Archiv der untersten Mod hinten — im Spiel gewann also die schwaechste.
"""

from pathlib import Path
from types import SimpleNamespace

from anvil.core.mod_list_io import write_active_mods, write_global_modlist
from anvil.widgets.game_panel import GamePanel

REIHENFOLGE = ["Oben", "Mitte", "Unten"]


class _Packer:
    """BA2Packer-Ersatz: merkt sich Packreihenfolge und INI-Eintraege."""

    letzte: "_Packer | None" = None

    def __init__(self, plugin, instance_path, mods_path=None) -> None:
        self.gepackt: list[str] = []
        self.ini: list[str] = []
        _Packer.letzte = self

    def is_available(self) -> bool:
        return True

    def pack_all_mods(self, enabled_mods):
        self.gepackt = list(enabled_mods)
        return SimpleNamespace(
            success=True,
            errors=[],
            ba2_paths=[f"anvil_{n}.ba2" for n in self.gepackt],
        )

    def update_ini(self, ba2_names) -> bool:
        self.ini = list(ba2_names)
        return True

    def cleanup_ba2s(self) -> int:
        return 0


def _panel(tmp_path: Path) -> SimpleNamespace:
    """GamePanel-Ersatz mit genau dem, was silent_deploy() anfasst."""
    instance = tmp_path / "Instance"
    profiles = instance / ".profiles"
    (profiles / "Default").mkdir(parents=True)
    mods = instance / ".mods"
    mods.mkdir()
    write_global_modlist(profiles, REIHENFOLGE)
    write_active_mods(profiles / "Default", set(REIHENFOLGE))

    ergebnis = SimpleNamespace(
        success=True, errors=[], links_created=0, skipped_real_files=[],
    )
    deployer = SimpleNamespace(
        deploy=lambda: ergebnis,
        is_deployed=lambda: False,
        set_ba2_packing_enabled=lambda aktiv: None,
    )
    plugin = SimpleNamespace(
        GameName="Bethesda Testspiel",
        NeedsBa2Packing=True,
        RequiresForgeDeployment=False,
    )
    return SimpleNamespace(
        _current_plugin=plugin,
        _deployer=deployer,
        _current_game_path=tmp_path / "Game",
        _instance_path=instance,
        _mods_path=mods,
        _profiles_path=profiles,
        _current_profile_name="Default",
        _refresh_skipped_mods=lambda: None,
        _update_manifest_ba2=lambda *args: None,
        _apply_proton_dll_overrides=lambda: None,
    )


def test_archiv_der_obersten_mod_steht_zuletzt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("anvil.core.ba2_packer.BA2Packer", _Packer)

    GamePanel.silent_deploy(_panel(tmp_path))

    packer = _Packer.letzte
    assert packer is not None
    assert packer.gepackt == ["Unten", "Mitte", "Oben"]
    assert packer.ini == ["anvil_Unten.ba2", "anvil_Mitte.ba2", "anvil_Oben.ba2"]


def test_fremdeintraege_bleiben_vor_den_anvil_archiven(tmp_path: Path) -> None:
    from anvil.core.ba2_packer import BA2Packer

    ini = tmp_path / "Fallout4Custom.ini"
    ini.write_text(
        "[Archive]\nsResourceArchiveList2 = Fremd.ba2, NochEins.ba2\n",
        encoding="cp1252",
    )
    plugin = SimpleNamespace(
        ba2_ini_path=lambda: ini,
        Ba2IniSection="Archive",
        Ba2IniKey="sResourceArchiveList2",
        gameDirectory=lambda: tmp_path / "Game",
        GameDataPath="Data",
        Ba2LoosePaths=[],
    )
    packer = BA2Packer(plugin, tmp_path / "Instance", mods_path=tmp_path / "mods")

    assert packer.update_ini(
        ["anvil_Unten.ba2", "anvil_Mitte.ba2", "anvil_Oben.ba2"]
    ) is True

    zeile = next(
        z for z in ini.read_text(encoding="cp1252").splitlines()
        if z.startswith("sResourceArchiveList2")
    )
    werte = [w.strip() for w in zeile.split("=", 1)[1].split(",")]
    assert werte == [
        "Fremd.ba2", "NochEins.ba2",
        "anvil_Unten.ba2", "anvil_Mitte.ba2", "anvil_Oben.ba2",
    ]
