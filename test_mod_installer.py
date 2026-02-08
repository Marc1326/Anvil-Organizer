"""Tests für ModInstaller: ZIP entpacken, Ordnerstruktur, Duplikate, Sanitize."""

import shutil
import tempfile
import zipfile
from pathlib import Path

from anvil.core.mod_installer import ModInstaller
from anvil.core.mod_metadata import read_meta_ini


def _setup_instance(tmp: Path) -> Path:
    """Create a minimal instance structure and return instance_path."""
    instance = tmp / "TestInstance"
    (instance / ".mods").mkdir(parents=True)
    (instance / ".profiles" / "Default").mkdir(parents=True)
    return instance


def _create_test_zip(zip_path: Path, files: dict[str, str]) -> None:
    """Create a ZIP archive with the given files."""
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="anvil_test_installer_"))
    print(f"=== Test-Verzeichnis: {tmp} ===\n")

    try:
        _test_basic_zip(tmp)
        _test_flatten_subfolder(tmp)
        _test_unique_name(tmp)
        _test_sanitize_name(tmp)
        _test_empty_archive(tmp)
        _test_check_tools(tmp)
        _test_missing_file(tmp)
    finally:
        shutil.rmtree(tmp)

    print("\n" + "=" * 50)
    print("ALLE TESTS BESTANDEN!")
    print("=" * 50)


# ── Basic ZIP ────────────────────────────────────────────────────────


def _test_basic_zip(tmp: Path):
    print("=== Basic ZIP Install ===")

    instance = _setup_instance(tmp / "basic")
    installer = ModInstaller(instance)

    # Create a ZIP with files at top level
    zip_path = tmp / "CoolMod-v1.2.zip"
    _create_test_zip(zip_path, {
        "data.esp": "plugin data",
        "textures/diffuse.dds": "texture data",
        "meshes/model.nif": "mesh data",
    })

    result = installer.install_from_archive(zip_path)

    assert result is not None, "install_from_archive returned None"
    assert result.name == "CoolMod-v1.2", f"folder name: {result.name}"
    assert result.is_dir(), "mod folder not created"
    assert (result / "data.esp").is_file(), "data.esp missing"
    assert (result / "textures" / "diffuse.dds").is_file(), "texture missing"
    assert (result / "meta.ini").is_file(), "meta.ini missing"
    print(f"  Mod installiert: {result.name} OK")

    # Check meta.ini
    meta = read_meta_ini(result)
    assert meta.get("name") == "CoolMod-v1.2", f"meta name: {meta.get('name')}"
    print(f"  meta.ini name={meta['name']} OK")

    print()


# ── Flatten Single Subfolder ─────────────────────────────────────────


def _test_flatten_subfolder(tmp: Path):
    print("=== Flatten Single Subfolder ===")

    instance = _setup_instance(tmp / "flatten")
    installer = ModInstaller(instance)

    # ZIP with single subfolder: ModName/ → files
    zip_path = tmp / "NestedMod.zip"
    _create_test_zip(zip_path, {
        "NestedMod/plugin.esp": "plugin",
        "NestedMod/data/config.ini": "config",
    })

    result = installer.install_from_archive(zip_path)

    assert result is not None
    # Files should be flattened — no NestedMod/NestedMod/
    assert (result / "plugin.esp").is_file(), "plugin.esp should be at top level"
    assert (result / "data" / "config.ini").is_file(), "config.ini should be under data/"
    assert not (result / "NestedMod").exists(), "NestedMod subfolder should be flattened"
    print(f"  Flattened: {result.name}, plugin.esp at top level OK")

    print()


# ── Unique Name ──────────────────────────────────────────────────────


def _test_unique_name(tmp: Path):
    print("=== Unique Name (Duplikate) ===")

    instance = _setup_instance(tmp / "unique")
    installer = ModInstaller(instance)

    zip1 = tmp / "TestMod.zip"
    _create_test_zip(zip1, {"file1.txt": "v1"})
    zip2 = tmp / "TestMod2.zip"  # Different file, but will use same name
    _create_test_zip(zip2, {"file2.txt": "v2"})

    r1 = installer.install_from_archive(zip1)
    assert r1 is not None
    assert r1.name == "TestMod", f"First: {r1.name}"

    # Install with explicit same name
    r2 = installer.install_from_archive(zip2, mod_name="TestMod")
    assert r2 is not None
    assert r2.name == "TestMod (2)", f"Second: {r2.name}"

    # Third one
    zip3 = tmp / "TestMod3.zip"
    _create_test_zip(zip3, {"file3.txt": "v3"})
    r3 = installer.install_from_archive(zip3, mod_name="TestMod")
    assert r3 is not None
    assert r3.name == "TestMod (3)", f"Third: {r3.name}"

    print(f"  Duplikate: {r1.name}, {r2.name}, {r3.name} OK")

    print()


# ── Sanitize Name ────────────────────────────────────────────────────


def _test_sanitize_name(tmp: Path):
    print("=== Sanitize Name ===")

    instance = _setup_instance(tmp / "sanitize")
    installer = ModInstaller(instance)

    assert installer._sanitize_name("Cool:Mod?v1") == "Cool_Mod_v1"
    assert installer._sanitize_name('He"llo<>World') == "He_llo_World"
    assert installer._sanitize_name("...leading") == "leading"
    assert installer._sanitize_name("") == "Unnamed Mod"
    assert installer._sanitize_name("Normal Mod Name") == "Normal Mod Name"
    print("  Sanitize: alle Fälle OK")

    print()


# ── Empty Archive ────────────────────────────────────────────────────


def _test_empty_archive(tmp: Path):
    print("=== Empty Archive ===")

    instance = _setup_instance(tmp / "empty")
    installer = ModInstaller(instance)

    zip_path = tmp / "Empty.zip"
    with zipfile.ZipFile(zip_path, "w"):
        pass  # Empty ZIP

    result = installer.install_from_archive(zip_path)
    assert result is None, "Empty archive should return None"
    print("  Leeres Archiv → None OK")

    print()


# ── Check Tools ──────────────────────────────────────────────────────


def _test_check_tools(tmp: Path):
    print("=== Check Tools ===")

    tools = ModInstaller.check_tools()
    assert tools["zip"] is True, "ZIP should always be available"
    print(f"  zip={tools['zip']}, rar={tools['rar']}, 7z={tools['7z']} OK")

    print()


# ── Missing File ─────────────────────────────────────────────────────


def _test_missing_file(tmp: Path):
    print("=== Missing File ===")

    instance = _setup_instance(tmp / "missing")
    installer = ModInstaller(instance)

    result = installer.install_from_archive(tmp / "nonexistent.zip")
    assert result is None, "Missing file should return None"
    print("  Fehlende Datei → None OK")

    print()


if __name__ == "__main__":
    main()
