from pathlib import Path
from typing import Any, cast

from anvil.core.mod_deployer import ModDeployer
from anvil.core.overlay_deployer import OverlayDeployer
from anvil.widgets.game_panel import GamePanel


class FakePlugin:
    GameDataPath = "Data"
    GameDirectInstallMods = ["RED4ext"]
    GameMultiFolderRoutes: dict[str, str] = {}
    GameRedmodPath = "mods"


class FakePanel:
    """Nur die Felder, die die Deployer-Fabrik anfasst."""

    _current_plugin = FakePlugin()
    _separator_deploy_paths: dict[str, str] = {}
    _mod_index = None
    _mods_path: Path | None = None
    _profiles_path: Path | None = None

    _create_deployer = GamePanel._create_deployer


def test_fabrik_liefert_ohne_schalter_den_symlink_deployer(tmp_path: Path) -> None:
    panel = cast(Any, FakePanel())
    deployer = panel._create_deployer(tmp_path / "i", tmp_path / "g", "Default")
    assert isinstance(deployer, ModDeployer)


def test_fabrik_liefert_mit_schalter_den_overlay_deployer(tmp_path: Path) -> None:
    panel = cast(Any, FakePanel())
    panel._use_overlay = True
    deployer = panel._create_deployer(tmp_path / "i", tmp_path / "g", "Default")
    assert isinstance(deployer, OverlayDeployer)


def test_overlay_deployer_bekommt_die_plugin_angaben(tmp_path: Path) -> None:
    panel = cast(Any, FakePanel())
    panel._use_overlay = True
    deployer = panel._create_deployer(tmp_path / "i", tmp_path / "g", "Vanilla")

    assert deployer.is_direct_install("RED4ext")
    assert not deployer.is_direct_install("Irgendein Mod")
    assert deployer._profile_name == "Vanilla"


def test_plugin_mit_eigenem_deployer_hat_vorrang(tmp_path: Path) -> None:
    marker = object()

    class MitEigenem(FakePlugin):
        @staticmethod
        def create_deployer(instance_path, game_path, profile_name):
            return marker

    panel = cast(Any, FakePanel())
    panel._current_plugin = MitEigenem()
    panel._use_overlay = True

    assert panel._create_deployer(tmp_path / "i", tmp_path / "g", "Default") is marker
