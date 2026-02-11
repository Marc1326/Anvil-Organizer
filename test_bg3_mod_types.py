"""Tests for BG3 mod type detection and data-override manifest system.

Creates fake archives with different contents and verifies:
  - Framework detection (DWrite.dll → BG3SE)
  - Standard pak detection (.pak files)
  - Data-override detection (loose files)
  - Manifest CRUD for data-overrides
"""

import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from anvil.core.bg3_mod_installer import (
    BG3ModInstaller,
    MOD_TYPE_DATA_OVERRIDE,
    MOD_TYPE_FRAMEWORK,
    MOD_TYPE_PAK,
)
from anvil.plugins.framework_mod import FrameworkMod


# ── Fake game plugin ──────────────────────────────────────────────────

class _FakeGamePlugin:
    """Minimal game plugin stub for testing."""

    def __init__(self, game_path=None):
        self._game_path = game_path
        self._frameworks = [
            FrameworkMod(
                name="BG3 Script Extender",
                pattern=["DWrite.dll"],
                target="bin/",
                description="Script Extender fuer BG3",
                detect_installed=["bin/DWrite.dll"],
                required_by=["SE-Mods"],
            ),
        ]

    def pak_mods_path(self):
        return None

    def modsettings_path(self):
        return None

    def get_framework_mods(self):
        return self._frameworks

    def is_framework_mod(self, archive_contents):
        lower_contents = [f.lower().replace("\\", "/") for f in archive_contents]
        for fw in self._frameworks:
            for pattern in fw.pattern:
                pat = pattern.lower()
                if any(pat in entry for entry in lower_contents):
                    return fw
        return None

    def get_installed_frameworks(self):
        if self._game_path is None:
            return [(fw, False) for fw in self._frameworks]
        result = []
        for fw in self._frameworks:
            installed = any(
                (self._game_path / det).exists() for det in fw.detect_installed
            )
            result.append((fw, installed))
        return result


# ── Helper: create test archives ──────────────────────────────────────

def _create_framework_zip(path: Path) -> None:
    """Create a ZIP with DWrite.dll (framework mod)."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("DWrite.dll", b"fake DLL content")
        zf.writestr("bin/NativeMods/readme.txt", "BG3SE readme")


def _create_pak_zip(path: Path) -> None:
    """Create a ZIP with a .pak file (standard mod)."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("TestMod.pak", b"LSPK fake pak content")
        zf.writestr("info.json", '{"name": "Test Mod"}')


def _create_data_override_zip(path: Path) -> None:
    """Create a ZIP with loose texture files (data override)."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Maps/texture1.dds", b"fake texture 1")
        zf.writestr("Maps/texture2.dds", b"fake texture 2")
        zf.writestr("Meshes/model.gr2", b"fake model")


# ── Tests ─────────────────────────────────────────────────────────────

def test_detect_framework():
    """DWrite.dll in file list → detected as framework."""
    plugin = _FakeGamePlugin()
    installer = BG3ModInstaller(plugin)

    file_list = ["DWrite.dll", "bin/NativeMods/readme.txt"]
    mod_type, extra = installer.detect_mod_type(file_list)

    assert mod_type == MOD_TYPE_FRAMEWORK, f"Expected framework, got {mod_type}"
    assert extra is not None, "Expected FrameworkMod object"
    assert extra.name == "BG3 Script Extender"
    print(f"  PASS: Framework detected → {extra.name}")


def test_detect_pak():
    """File list with .pak → detected as standard pak."""
    plugin = _FakeGamePlugin()
    installer = BG3ModInstaller(plugin)

    file_list = ["TestMod.pak", "info.json"]
    mod_type, extra = installer.detect_mod_type(file_list)

    assert mod_type == MOD_TYPE_PAK, f"Expected pak, got {mod_type}"
    assert extra is None
    print("  PASS: Pak mod detected")


def test_detect_data_override():
    """File list with only loose files → detected as data override."""
    plugin = _FakeGamePlugin()
    installer = BG3ModInstaller(plugin)

    file_list = ["Maps/texture1.dds", "Maps/texture2.dds", "Meshes/model.gr2"]
    mod_type, extra = installer.detect_mod_type(file_list)

    assert mod_type == MOD_TYPE_DATA_OVERRIDE, f"Expected data_override, got {mod_type}"
    assert extra is None
    print("  PASS: Data override detected")


def test_framework_priority():
    """Framework detection takes priority over pak."""
    plugin = _FakeGamePlugin()
    installer = BG3ModInstaller(plugin)

    # Archive with both DWrite.dll AND a .pak
    file_list = ["DWrite.dll", "SomeMod.pak"]
    mod_type, extra = installer.detect_mod_type(file_list)

    assert mod_type == MOD_TYPE_FRAMEWORK, f"Expected framework (priority), got {mod_type}"
    print("  PASS: Framework takes priority over pak")


def test_manifest_crud():
    """Test save/load/list/delete of data-override manifests."""
    tmp = Path(tempfile.mkdtemp(prefix="bg3_test_"))
    try:
        plugin = _FakeGamePlugin()
        installer = BG3ModInstaller(plugin, instance_path=tmp)

        # Save
        test_files = ["Data/Maps/tex1.dds", "Data/Maps/tex2.dds"]
        installer._save_override_manifest("BetterMaps", test_files)

        manifest_path = tmp / ".data_overrides" / "BetterMaps.json"
        assert manifest_path.is_file(), "Manifest file not created"
        print("  PASS: Manifest saved")

        # Load
        loaded = installer._load_override_manifest("BetterMaps")
        assert loaded is not None, "Manifest not loaded"
        assert loaded["name"] == "BetterMaps"
        assert loaded["files"] == test_files
        assert "installed_at" in loaded
        print(f"  PASS: Manifest loaded — {loaded['name']}, {len(loaded['files'])} files")

        # List
        overrides = installer.get_data_overrides()
        assert len(overrides) == 1
        assert overrides[0]["name"] == "BetterMaps"
        print(f"  PASS: get_data_overrides() → {len(overrides)} entries")

        # Delete (nonexistent)
        loaded_none = installer._load_override_manifest("NonExistent")
        assert loaded_none is None
        print("  PASS: Nonexistent manifest returns None")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_get_mod_list_includes_extras():
    """get_mod_list() returns data_overrides and frameworks keys."""
    tmp = Path(tempfile.mkdtemp(prefix="bg3_test_"))
    try:
        plugin = _FakeGamePlugin(game_path=tmp)
        installer = BG3ModInstaller(plugin, instance_path=tmp)

        # Save a manifest
        installer._save_override_manifest("TestOverride", ["Data/test.dds"])

        mod_list = installer.get_mod_list()

        assert "data_overrides" in mod_list, "Missing data_overrides key"
        assert "frameworks" in mod_list, "Missing frameworks key"
        assert len(mod_list["data_overrides"]) == 1
        assert mod_list["data_overrides"][0]["name"] == "TestOverride"
        assert len(mod_list["frameworks"]) == 1
        assert mod_list["frameworks"][0]["name"] == "BG3 Script Extender"
        assert mod_list["frameworks"][0]["installed"] is False
        print(f"  PASS: get_mod_list() includes {len(mod_list['data_overrides'])} overrides, "
              f"{len(mod_list['frameworks'])} frameworks")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_extract_and_detect_framework_zip():
    """Full flow: extract framework ZIP and detect type."""
    tmp = Path(tempfile.mkdtemp(prefix="bg3_test_"))
    try:
        zip_path = tmp / "bg3se.zip"
        _create_framework_zip(zip_path)

        # Extract
        extracted = BG3ModInstaller._extract_archive(zip_path)
        assert extracted is not None, "Extraction failed"

        file_list = [
            str(f.relative_to(extracted))
            for f in Path(extracted).rglob("*") if f.is_file()
        ]

        plugin = _FakeGamePlugin()
        installer = BG3ModInstaller(plugin)
        mod_type, extra = installer.detect_mod_type(file_list)
        assert mod_type == MOD_TYPE_FRAMEWORK
        print(f"  PASS: Framework ZIP extracted and detected ({len(file_list)} files)")

        shutil.rmtree(extracted, ignore_errors=True)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_extract_and_detect_pak_zip():
    """Full flow: extract pak ZIP and detect type."""
    tmp = Path(tempfile.mkdtemp(prefix="bg3_test_"))
    try:
        zip_path = tmp / "modpack.zip"
        _create_pak_zip(zip_path)

        extracted = BG3ModInstaller._extract_archive(zip_path)
        assert extracted is not None

        file_list = [
            str(f.relative_to(extracted))
            for f in Path(extracted).rglob("*") if f.is_file()
        ]

        plugin = _FakeGamePlugin()
        installer = BG3ModInstaller(plugin)
        mod_type, _ = installer.detect_mod_type(file_list)
        assert mod_type == MOD_TYPE_PAK
        print(f"  PASS: Pak ZIP extracted and detected ({len(file_list)} files)")

        shutil.rmtree(extracted, ignore_errors=True)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_extract_and_detect_data_override_zip():
    """Full flow: extract data override ZIP and detect type."""
    tmp = Path(tempfile.mkdtemp(prefix="bg3_test_"))
    try:
        zip_path = tmp / "BetterMapAssets.zip"
        _create_data_override_zip(zip_path)

        extracted = BG3ModInstaller._extract_archive(zip_path)
        assert extracted is not None

        file_list = [
            str(f.relative_to(extracted))
            for f in Path(extracted).rglob("*") if f.is_file()
        ]

        plugin = _FakeGamePlugin()
        installer = BG3ModInstaller(plugin)
        mod_type, _ = installer.detect_mod_type(file_list)
        assert mod_type == MOD_TYPE_DATA_OVERRIDE
        print(f"  PASS: Data override ZIP extracted and detected ({len(file_list)} files)")

        shutil.rmtree(extracted, ignore_errors=True)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== BG3 Mod Type Detection Tests ===\n")

    print("1. Type detection:")
    test_detect_framework()
    test_detect_pak()
    test_detect_data_override()
    test_framework_priority()

    print("\n2. Manifest CRUD:")
    test_manifest_crud()

    print("\n3. get_mod_list() with extras:")
    test_get_mod_list_includes_extras()

    print("\n4. Full ZIP extraction + detection:")
    test_extract_and_detect_framework_zip()
    test_extract_and_detect_pak_zip()
    test_extract_and_detect_data_override_zip()

    print("\n=== ALL TESTS PASSED ===")
