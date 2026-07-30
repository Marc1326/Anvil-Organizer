import re
import shlex
import tomllib
from pathlib import Path


_REPO_ROOT = Path(__file__).parents[1]
_STABLE_PKGBUILD = _REPO_ROOT / "packaging" / "aur" / "PKGBUILD"
_GIT_PKGBUILD = _REPO_ROOT / "packaging" / "aur-git" / "PKGBUILD"


def _scalar(pkgbuild: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}=(.+)$", pkgbuild, re.MULTILINE)
    assert match is not None, f"missing {name}"
    return match.group(1).strip().strip("'\"")


def _array(pkgbuild: str, name: str) -> list[str]:
    match = re.search(
        rf"^{re.escape(name)}=\((.*?)\)",
        pkgbuild,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"missing {name}"
    return shlex.split(match.group(1), comments=True)


def test_stable_aur_package_matches_project_version_and_has_checksum() -> None:
    project = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())
    pkgbuild = _STABLE_PKGBUILD.read_text()

    assert _scalar(pkgbuild, "pkgver") == project["project"]["version"]
    checksums = _array(pkgbuild, "sha256sums")
    assert len(checksums) == 1
    assert re.fullmatch(r"[0-9a-f]{64}", checksums[0])


def test_aur_packages_declare_all_python_runtime_dependencies() -> None:
    required = {
        "pyside6",
        "python-lz4",
        "python-keyring",
        "python-cryptography",
    }

    for pkgbuild_path in (_STABLE_PKGBUILD, _GIT_PKGBUILD):
        dependencies = set(_array(pkgbuild_path.read_text(), "depends"))
        assert "python-pyside6" not in dependencies
        assert required <= dependencies


def test_project_does_not_define_duplicate_script_entry_points() -> None:
    project = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())["project"]
    console_scripts = set(project.get("scripts", {}))
    gui_scripts = set(project.get("gui-scripts", {}))

    assert console_scripts.isdisjoint(gui_scripts)
