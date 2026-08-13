"""Prueft das Mount-Modul: Helferskript, Erkennung, Fehlerfaelle."""

import subprocess
from pathlib import Path

import pytest

from anvil.core.overlay_mount import (
    _rufe_helfer,
    helper_path,
    is_mounted,
    mount,
    mount_requirements,
    polkit_rule_installed,
    unmount,
    write_helper,
)


def _conf(tmp_path: Path) -> Path:
    conf = tmp_path / "mount.conf"
    conf.write_text(
        f"MOUNT={tmp_path}/game|{tmp_path}/stage:{tmp_path}/game|"
        f"{tmp_path}/upper|{tmp_path}/work\n",
        encoding="utf-8",
    )
    return conf


def test_helfer_wird_ausfuehrbar_angelegt(tmp_path: Path) -> None:
    ziel = write_helper(tmp_path)
    assert ziel == helper_path(tmp_path)
    assert ziel.is_file()
    assert ziel.stat().st_mode & 0o111


def test_helfer_ist_gueltiges_bash(tmp_path: Path) -> None:
    ziel = write_helper(tmp_path)
    lauf = subprocess.run(["bash", "-n", str(ziel)], capture_output=True)
    assert lauf.returncode == 0, lauf.stderr.decode()


def test_helfer_bricht_ohne_conf_ab(tmp_path: Path) -> None:
    ziel = write_helper(tmp_path)
    lauf = subprocess.run(
        ["bash", str(ziel), "mount", str(tmp_path / "fehlt.conf")],
        capture_output=True,
    )
    assert lauf.returncode != 0


def test_is_mounted_erkennt_nicht_mounts(tmp_path: Path) -> None:
    assert not is_mounted(tmp_path)


def test_mount_uebergibt_aktion_und_conf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    aufrufe: list[list[str]] = []

    class Lauf:
        returncode = 0
        stdout = "gemountet"
        stderr = ""

    def fake_run(cmd, **kwargs):
        aufrufe.append(cmd)
        return Lauf()

    monkeypatch.setattr(subprocess, "run", fake_run)
    ok, _ = mount(tmp_path, _conf(tmp_path))
    assert ok
    assert aufrufe[0][0] == "pkexec"
    assert "mount" in aufrufe[0]


def test_passwort_abbruch_ist_kein_fehler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Lauf:
        returncode = 126
        stdout = ""
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Lauf())
    ok, meldung = unmount(tmp_path, _conf(tmp_path))
    assert not ok
    assert meldung == ""


def test_echter_fehler_kommt_als_meldung(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Lauf:
        returncode = 1
        stdout = ""
        stderr = "mount fehlgeschlagen"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Lauf())
    ok, meldung = unmount(tmp_path, _conf(tmp_path))
    assert not ok
    assert "fehlgeschlagen" in meldung


def test_polkit_regel_fehlt_standardmaessig(tmp_path: Path) -> None:
    assert not polkit_rule_installed(tmp_path, "niemand")


def test_umgebung_hier_ist_tauglich() -> None:
    """Auf diesem System: Kernel-Overlay und pkexec vorhanden."""
    assert mount_requirements() == []
