import configparser
from pathlib import Path

from anvil.core.mod_installer import ModInstaller
from anvil.plugins.framework_mod import FrameworkMod


def test_framework_install_marks_source_download_as_installed(tmp_path: Path) -> None:
    instance_path = tmp_path / "instance"
    game_path = tmp_path / "game"
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    (extracted / "skse64_loader.exe").write_bytes(b"loader")

    archive = tmp_path / "SKSE64.zip"
    archive.write_bytes(b"archive")
    meta_path = Path(str(archive) + ".meta")
    meta_path.write_text("[General]\nmodID=30379\n", encoding="utf-8")

    framework = FrameworkMod(
        name="SKSE64",
        pattern=["skse64_loader.exe"],
        target="",
        description="",
        detect_installed=["skse64_loader.exe"],
    )

    result = ModInstaller(instance_path).install_framework(
        extracted,
        framework,
        game_path,
        archive_path=archive,
    )

    assert result is not None
    assert (game_path / "skse64_loader.exe").read_bytes() == b"loader"

    metadata = configparser.ConfigParser()
    metadata.read(meta_path, encoding="utf-8")
    assert metadata.get("General", "modID") == "30379"
    assert metadata.getboolean("General", "installed") is True
    assert metadata.get("General", "installationFile") == "SKSE64"
