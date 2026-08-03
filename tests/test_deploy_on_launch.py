"""Mods only reach the game directory while the game runs."""

from pathlib import Path
from types import SimpleNamespace

from anvil.core.mod_deployer import ModDeployer
from anvil.core.mod_list_io import write_active_mods, write_global_modlist
from anvil.core.modindex import ModIndex
from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


def _library(tmp_path: Path, framework: str = "CET Framework"):
    instance = tmp_path / "Instance"
    game = tmp_path / "Game"
    mods = instance / ".mods"
    profiles = instance / ".profiles"
    profile = profiles / "Default"
    game.mkdir(parents=True)
    profile.mkdir(parents=True)

    (mods / "Example Mod" / "Data").mkdir(parents=True)
    (mods / "Example Mod" / "Data" / "example.bin").write_bytes(b"mod")
    (mods / framework / "bin" / "x64" / "plugins").mkdir(parents=True)
    (mods / framework / "bin" / "x64" / "plugins" / "cyber_engine_tweaks.asi").write_bytes(b"fw")

    write_global_modlist(profiles, ["Example Mod", framework])
    write_active_mods(profile, {"Example Mod"})
    return instance, game, mods, profiles


class _Game(BaseGame):
    GameName = "Test Game"
    GameShortName = "test"
    GameDirectInstallMods = ["CET Framework"]

    def get_framework_mods(self):
        return [
            FrameworkMod(
                name="Cyber Engine Tweaks",
                pattern=["cyber_engine_tweaks.asi"],
                target="",
                description="",
                detect_installed=["bin/x64/plugins/cyber_engine_tweaks.asi"],
            )
        ]

    def _load_json_frameworks(self):
        return []


def test_framework_detected_without_deployment(tmp_path: Path) -> None:
    """The game directory is empty — detection still finds the framework."""
    instance, game, mods, _profiles = _library(tmp_path)
    index = ModIndex(instance, mods_path=mods)
    index.rebuild()

    plugin = _Game()
    plugin.setGamePath(game)

    assert [ins for _fw, ins in plugin.get_installed_frameworks()] == [False]

    plugin.setModIndex(index)
    assert [ins for _fw, ins in plugin.get_installed_frameworks()] == [True]
    assert plugin.managed_framework_mods() == {
        "cyber engine tweaks": ["CET Framework"]
    }


def test_hand_installed_framework_still_found(tmp_path: Path) -> None:
    """A framework the user dropped into the game folder is not overlooked."""
    instance, game, mods, _profiles = _library(tmp_path, framework="Unrelated Mod")
    (game / "bin" / "x64" / "plugins").mkdir(parents=True)
    (game / "bin" / "x64" / "plugins" / "cyber_engine_tweaks.asi").write_bytes(b"fw")

    index = ModIndex(instance, mods_path=mods)
    index.rebuild()
    plugin = _Game()
    plugin.setGamePath(game)
    plugin.setModIndex(index)

    assert [ins for _fw, ins in plugin.get_installed_frameworks()] == [True]


def test_purge_removes_framework_copies(tmp_path: Path) -> None:
    """Direct-install copies must not survive the purge."""
    instance, game, mods, profiles = _library(tmp_path)
    deployer = ModDeployer(
        instance,
        game,
        ["CET Framework"],
        profile_name="Default",
        mods_path=mods,
        profiles_path=profiles,
    )

    assert deployer.deploy().success is True
    copied = game / "bin" / "x64" / "plugins" / "cyber_engine_tweaks.asi"
    assert copied.is_file() and not copied.is_symlink()

    assert deployer.purge().success is True
    assert not copied.exists()
    assert not (game / "Data" / "example.bin").exists()


def test_inactive_framework_is_not_deployed(tmp_path: Path) -> None:
    """A framework switched off in framework_state stays out of the game."""
    instance, game, mods, profiles = _library(tmp_path)
    deployer = ModDeployer(
        instance,
        game,
        ["CET Framework"],
        profile_name="Default",
        mods_path=mods,
        profiles_path=profiles,
    )
    deployer.set_skipped_mods({"CET Framework"})

    assert deployer.deploy().success is True
    assert not (game / "bin" / "x64" / "plugins" / "cyber_engine_tweaks.asi").exists()
    # ...while normal mods are unaffected
    assert (game / "Data" / "example.bin").is_symlink()


def test_purge_cleans_up_symlinked_mod_folders(tmp_path: Path) -> None:
    """A mod folder that is itself a symlink must still get purged.

    resolve() follows the folder symlink out of .mods/, which used to
    trip the safety check and leave the link behind forever.
    """
    instance, game, mods, profiles = _library(tmp_path)
    external = tmp_path / "Checkout"
    (external / "Data").mkdir(parents=True)
    (external / "Data" / "external.bin").write_bytes(b"ext")
    (mods / "Linked Mod").symlink_to(external, target_is_directory=True)
    write_global_modlist(profiles, ["Example Mod", "Linked Mod"])
    write_active_mods(profiles / "Default", {"Example Mod", "Linked Mod"})

    deployer = ModDeployer(
        instance,
        game,
        profile_name="Default",
        mods_path=mods,
        profiles_path=profiles,
    )
    assert deployer.deploy().success is True
    deployed = game / "Data" / "external.bin"
    assert deployed.is_symlink()

    result = deployer.purge()
    assert result.errors == []
    assert not deployed.exists()


def test_orphaned_links_are_swept_up(tmp_path: Path) -> None:
    """Links from a run whose manifest is gone still get cleaned."""
    instance, game, mods, profiles = _library(tmp_path)
    deployer = ModDeployer(
        instance,
        game,
        profile_name="Default",
        mods_path=mods,
        profiles_path=profiles,
    )
    assert deployer.deploy().success is True
    deployed = game / "Data" / "example.bin"
    assert deployed.is_symlink()

    # Manifest lost — a purge can no longer know about the link
    (instance / ModDeployer.MANIFEST_NAME).unlink()

    assert deployer.remove_orphaned_links() == 1
    assert not deployed.exists()


def test_sweep_leaves_foreign_files_alone(tmp_path: Path) -> None:
    """Real game files and links pointing elsewhere must survive."""
    instance, game, mods, profiles = _library(tmp_path)
    elsewhere = tmp_path / "Elsewhere"
    elsewhere.mkdir()
    (elsewhere / "other.bin").write_bytes(b"other")
    (game / "vanilla.exe").write_bytes(b"game")
    (game / "foreign.bin").symlink_to(elsewhere / "other.bin")

    deployer = ModDeployer(
        instance,
        game,
        profile_name="Default",
        mods_path=mods,
        profiles_path=profiles,
    )

    assert deployer.remove_orphaned_links() == 0
    assert (game / "vanilla.exe").is_file()
    assert (game / "foreign.bin").is_symlink()


def test_scanner_reports_every_file_not_just_conflicts(tmp_path: Path) -> None:
    """The Data tab needs the full picture, not only the collisions."""
    from anvil.core.conflict_scanner import ConflictScanner

    lo = tmp_path / "Low"
    hi = tmp_path / "High"
    (lo / "Data").mkdir(parents=True)
    (hi / "Data").mkdir(parents=True)
    (lo / "Data" / "shared.esp").write_bytes(b"a")
    (hi / "Data" / "shared.esp").write_bytes(b"b")
    (lo / "Data" / "only_low.esp").write_bytes(b"c")

    result = ConflictScanner().scan_conflicts(
        [{"name": "Low", "path": str(lo)}, {"name": "High", "path": str(hi)}]
    )

    owners = result["file_owners"]
    assert owners["Data/shared.esp"] == ["Low", "High"]  # last one wins
    assert owners["Data/only_low.esp"] == ["Low"]
    assert [c["winner"] for c in result["conflicts"]] == ["High"]


def test_owner_label_marks_the_winner(tmp_path: Path) -> None:
    from anvil.widgets.game_panel import GamePanel

    assert GamePanel._owner_label([]) == ""
    assert GamePanel._owner_label(["Solo"]) == "Solo"
    # highest priority is last — it wins and gets named
    assert GamePanel._owner_label(["Low", "Mid", "High"]) == "High (+2)"


def test_skipped_mods_matching_is_case_insensitive(tmp_path: Path) -> None:
    instance, game, mods, profiles = _library(tmp_path)
    deployer = ModDeployer(
        instance,
        game,
        ["CET Framework"],
        profile_name="Default",
        mods_path=mods,
        profiles_path=profiles,
    )
    deployer.set_skipped_mods({"cet framework"})

    assert deployer.deploy().success is True
    assert not (game / "bin" / "x64" / "plugins" / "cyber_engine_tweaks.asi").exists()
