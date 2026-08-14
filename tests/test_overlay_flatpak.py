"""Flatpak-Zweig des Mount-Moduls: Host-Aufrufe per flatpak-spawn."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from anvil.core import overlay_mount


def _lauf(rc: int = 0, out: str = "", err: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=out, stderr=err)


def _conf(tmp_path: Path) -> Path:
    conf = tmp_path / "mount.conf"
    conf.write_text(
        f"MOUNT={tmp_path}/game|{tmp_path}/stage|{tmp_path}/upper|{tmp_path}/work\n",
        encoding="utf-8",
    )
    return conf


def test_mount_läuft_im_flatpak_auf_dem_host(tmp_path: Path) -> None:
    with (
        patch.object(overlay_mount, "is_flatpak", return_value=True),
        patch.object(overlay_mount, "SYSTEM_HELPER", tmp_path / "fehlt"),
        patch.object(overlay_mount.subprocess, "run", return_value=_lauf()) as run,
    ):
        ok, _ = overlay_mount.mount(tmp_path, _conf(tmp_path))
    assert ok
    cmd = run.call_args[0][0]
    assert cmd[:3] == ["flatpak-spawn", "--host", "pkexec"]


def test_umount_läuft_im_flatpak_auf_dem_host(tmp_path: Path) -> None:
    with (
        patch.object(overlay_mount, "is_flatpak", return_value=True),
        patch.object(overlay_mount, "SYSTEM_HELPER", tmp_path / "fehlt"),
        patch.object(overlay_mount.subprocess, "run", return_value=_lauf()) as run,
    ):
        ok, _ = overlay_mount.unmount(tmp_path, _conf(tmp_path))
    assert ok
    cmd = run.call_args[0][0]
    assert cmd[:3] == ["flatpak-spawn", "--host", "pkexec"]


def test_is_mounted_fragt_den_host(tmp_path: Path) -> None:
    with (
        patch.object(overlay_mount, "is_flatpak", return_value=True),
        patch.object(overlay_mount.subprocess, "run", return_value=_lauf(out="overlay\n")) as run,
    ):
        assert overlay_mount.is_mounted(tmp_path) is True
    cmd = run.call_args[0][0]
    assert cmd[:3] == ["flatpak-spawn", "--host", "findmnt"]


def test_polkit_regel_prueft_host_pfade(tmp_path: Path) -> None:
    with (
        patch.object(overlay_mount, "is_flatpak", return_value=True),
        patch.object(overlay_mount.subprocess, "run", return_value=_lauf()) as run,
    ):
        assert overlay_mount.polkit_rule_installed(tmp_path, "marc") is True
    cmd = run.call_args[0][0]
    assert cmd[:2] == ["flatpak-spawn", "--host"]
    assert "stat -c %u" in cmd[4]

    with (
        patch.object(overlay_mount, "is_flatpak", return_value=True),
        patch.object(overlay_mount.subprocess, "run", return_value=_lauf(rc=1)),
    ):
        assert overlay_mount.polkit_rule_installed(tmp_path, "marc") is False


def test_polkit_einrichtung_läuft_auf_dem_host(tmp_path: Path) -> None:
    with (
        patch.object(overlay_mount, "is_flatpak", return_value=True),
        patch.object(overlay_mount.subprocess, "run", return_value=_lauf()) as run,
    ):
        ok, _ = overlay_mount.install_polkit_rule(tmp_path, "marc")
    assert ok
    cmd = run.call_args[0][0]
    assert cmd[:3] == ["flatpak-spawn", "--host", "pkexec"]


def test_anforderungen_pruefen_pkexec_auf_dem_host() -> None:
    with (
        patch.object(overlay_mount, "is_flatpak", return_value=True),
        patch.object(overlay_mount, "host_which", return_value=None),
        patch.object(Path, "read_text", return_value="nodev\ttmpfs\nnodev\toverlay\n"),
    ):
        assert len(overlay_mount.mount_requirements()) == 1

    with (
        patch.object(overlay_mount, "is_flatpak", return_value=True),
        patch.object(overlay_mount, "host_which", return_value="/usr/bin/pkexec"),
        patch.object(Path, "read_text", return_value="nodev\ttmpfs\nnodev\toverlay\n"),
    ):
        assert overlay_mount.mount_requirements() == []


def test_kernelmodul_wird_auf_dem_host_geprueft() -> None:
    with (
        patch.object(overlay_mount, "is_flatpak", return_value=True),
        patch.object(overlay_mount, "host_which", return_value="/usr/bin/pkexec"),
        patch.object(Path, "read_text", return_value="nodev\ttmpfs\n"),
        patch.object(overlay_mount.subprocess, "run", return_value=_lauf(rc=1)),
    ):
        assert len(overlay_mount.mount_requirements()) == 1

    with (
        patch.object(overlay_mount, "is_flatpak", return_value=True),
        patch.object(overlay_mount, "host_which", return_value="/usr/bin/pkexec"),
        patch.object(Path, "read_text", return_value="nodev\ttmpfs\n"),
        patch.object(overlay_mount.subprocess, "run", return_value=_lauf(rc=0)),
    ):
        assert overlay_mount.mount_requirements() == []
