from pathlib import Path
from unittest import mock
import zipfile

from anvil.core.mod_installer import ModInstaller


def _write_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Data/example.txt", "external mods root")


def test_installer_writes_only_to_explicit_mods_root(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    instance.mkdir()
    external_mods = tmp_path / "External Mods"
    external_mods.mkdir()
    archive = tmp_path / "Example.zip"
    _write_zip(archive)

    result = ModInstaller(
        instance,
        mods_path=external_mods,
    ).install_from_archive(archive, "Example Mod")

    assert result == external_mods / "Example Mod"
    assert (external_mods / "Example Mod" / "Data" / "example.txt").read_text() == "external mods root"
    assert not (instance / ".mods").exists()


def test_installer_fails_closed_when_explicit_mods_root_is_missing(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    instance.mkdir()
    missing_mods = tmp_path / "missing-drive" / "Mods"
    archive = tmp_path / "Example.zip"
    _write_zip(archive)

    result = ModInstaller(
        instance,
        mods_path=missing_mods,
    ).install_from_archive(archive, "Example Mod")

    assert result is None
    assert not missing_mods.exists()
    assert not (instance / ".mods").exists()


def test_installer_fails_closed_when_explicit_mods_root_is_not_writable(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    instance.mkdir()
    external_mods = tmp_path / "External Mods"
    external_mods.mkdir()
    archive = tmp_path / "Example.zip"
    _write_zip(archive)

    with mock.patch("anvil.core.mod_installer.os.access", return_value=False):
        result = ModInstaller(
            instance,
            mods_path=external_mods,
        ).install_from_archive(archive, "Example Mod")

    assert result is None
    assert not (external_mods / "Example Mod").exists()


def test_installer_keeps_legacy_default_without_explicit_root(tmp_path: Path) -> None:
    instance = tmp_path / "Instance"
    instance.mkdir()
    archive = tmp_path / "Example.zip"
    _write_zip(archive)

    result = ModInstaller(instance).install_from_archive(archive, "Example Mod")

    assert result == instance / ".mods" / "Example Mod"
    assert (instance / ".mods" / "Example Mod" / "Data" / "example.txt").is_file()
