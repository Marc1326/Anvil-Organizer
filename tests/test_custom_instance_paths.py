from pathlib import Path

from anvil.core import framework_state
from anvil.core.collection_io import (
    CollectionManifest,
    CollectionMod,
    analyze_collection,
    apply_collection,
    build_manifest,
)
from anvil.core.mod_entry import scan_mods_directory
from anvil.core.mod_list_io import write_active_mods, write_global_modlist
from anvil.core.mod_metadata import write_meta_ini
from anvil.core.modindex import ModIndex
from anvil.core.profile_name import safe_profile_directory
from anvil.core.plugins_txt_writer import PluginsTxtWriter


def _external_library(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    instance = tmp_path / "Instance"
    instance.mkdir()
    mods = tmp_path / "External Mods"
    profiles = tmp_path / "External Profiles"
    profile = profiles / "Default"
    (mods / "Example Mod").mkdir(parents=True)
    (mods / "Example Mod" / "example.txt").write_text("indexed", encoding="utf-8")
    profile.mkdir(parents=True)
    write_global_modlist(profiles, ["Example Mod"])
    write_active_mods(profile, {"Example Mod"})
    return instance, mods, profiles, profile


def test_scan_mods_uses_external_mods_and_profiles_roots(tmp_path: Path) -> None:
    instance, mods, profiles, profile = _external_library(tmp_path)

    entries = scan_mods_directory(
        instance,
        profile,
        mods_path=mods,
        profiles_path=profiles,
    )

    assert [entry.name for entry in entries] == ["Example Mod"]
    assert entries[0].enabled is True
    assert entries[0].install_path == mods / "Example Mod"
    assert not (instance / ".mods").exists()
    assert not (instance / ".profiles").exists()


def test_mod_index_uses_external_mods_root(tmp_path: Path) -> None:
    instance, mods, _profiles, _profile = _external_library(tmp_path)

    index = ModIndex(instance, mods_path=mods)
    index.rebuild()

    assert index.get_stats("Example Mod") == (1, len("indexed"))
    assert (instance / ".modindex.json").is_file()
    assert not (instance / ".mods").exists()


def test_safe_profile_directory_accepts_external_profiles_root(tmp_path: Path) -> None:
    instance, _mods, profiles, profile = _external_library(tmp_path)

    result = safe_profile_directory(
        instance,
        "Default",
        profiles_root=profiles,
    )

    assert result == profile


def test_collection_manifest_reads_external_mods_and_profiles(tmp_path: Path) -> None:
    instance, mods, profiles, profile = _external_library(tmp_path)
    write_meta_ini(
        mods / "Example Mod",
        {"name": "External Example", "version": "1.2", "modid": "42"},
    )

    manifest = build_manifest(
        instance,
        profile,
        "Game",
        "game",
        "game-nexus",
        "Collection",
        mods_path=mods,
        profiles_path=profiles,
    )

    assert [mod.name for mod in manifest.mods] == ["Example Mod"]
    assert manifest.mods[0].display_name == "External Example"
    assert manifest.mods[0].version == "1.2"
    assert manifest.mods[0].nexus_id == 42


def test_collection_analysis_uses_external_mods_root(tmp_path: Path) -> None:
    instance, mods, _profiles, _profile = _external_library(tmp_path)
    manifest = CollectionManifest(
        mods=[CollectionMod(name="Example Mod")],
    )

    result = analyze_collection(
        manifest,
        instance,
        mods_path=mods,
    )

    assert [mod.name for mod in result.installed] == ["Example Mod"]
    assert result.missing == []
    assert not (instance / ".mods").exists()


def test_apply_collection_writes_external_mods_and_profiles_roots(tmp_path: Path) -> None:
    instance, mods, profiles, profile = _external_library(tmp_path)
    manifest = CollectionManifest(
        mods=[
            CollectionMod(name="Section_separator", is_separator=True, enabled=True),
            CollectionMod(name="Example Mod", enabled=True),
        ],
    )

    missing = apply_collection(
        manifest,
        instance,
        profile,
        mods_path=mods,
        profiles_path=profiles,
    )

    assert missing == 0
    assert (mods / "Section_separator").is_dir()
    assert (profiles / "modlist.txt").is_file()
    assert not (instance / ".mods").exists()
    assert not (instance / ".profiles").exists()


def test_plugins_writer_uses_external_profiles_root(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    game = tmp_path / "Game"
    profiles = tmp_path / "External Profiles"
    profile = profiles / "Default"
    instance.mkdir()
    game.mkdir()
    profile.mkdir(parents=True)

    class GamePlugin:
        PRIMARY_PLUGINS: list[str] = []

    writer = PluginsTxtWriter(
        GamePlugin(),
        game,
        instance,
        profile_name="Default",
        profiles_path=profiles,
    )

    assert writer.profile_plugins_path == profile / "plugins.txt"
    assert not (instance / ".profiles").exists()


def test_framework_state_uses_profiles_root_from_instance_config(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    profiles = tmp_path / "External Profiles"
    instance.mkdir()
    profiles.mkdir()
    (instance / ".anvil.ini").write_text(
        "[Paths]\n"
        f"profiles_directory={profiles}\n",
        encoding="utf-8",
    )

    framework_state.save(instance, {"Framework": {"locked": True}})

    assert (profiles / "framework_state.json").is_file()
    assert not (instance / ".profiles").exists()
