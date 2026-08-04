import subprocess
from pathlib import Path

import pytest

from anvil.core.overlay_deployer import force_rmtree
from anvil.core.overlay_launch import (
    launch_option,
    localconfig_files,
    read_launch_options,
    set_launch_options,
    wrapper_path,
    write_wrapper,
)

VDF = '''"UserLocalConfigStore"
{
\t"Software"
\t{
\t\t"Valve"
\t\t{
\t\t\t"Steam"
\t\t\t{
\t\t\t\t"apps"
\t\t\t\t{
\t\t\t\t\t"1091500"
\t\t\t\t\t{
\t\t\t\t\t\t"LastPlayed"\t\t"1785782916"
\t\t\t\t\t\t"Playtime"\t\t"1167"
\t\t\t\t\t}
\t\t\t\t\t"1234567"
\t\t\t\t\t{
\t\t\t\t\t\t"LastPlayed"\t\t"1"
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
\t}
\t"depots"
\t{
\t\t"1091500"
\t\t{
\t\t\t"CDN"
\t\t\t{
\t\t\t}
\t\t}
\t}
}
'''


@pytest.fixture
def steam_aus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("anvil.core.overlay_launch.steam_is_running", lambda: False)


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "localconfig.vdf"
    path.write_text(VDF, encoding="utf-8")
    return path


# ── Wrapper ────────────────────────────────────────────────────────────

def test_wrapper_wird_ausfuehrbar_angelegt(tmp_path: Path) -> None:
    conf = tmp_path / "mount.conf"
    target = write_wrapper(tmp_path, conf)

    assert target == wrapper_path(tmp_path)
    assert target.is_file()
    assert target.stat().st_mode & 0o111


def test_wrapper_ist_gueltiges_bash(tmp_path: Path) -> None:
    target = write_wrapper(tmp_path, tmp_path / "mount.conf")
    geprueft = subprocess.run(["bash", "-n", str(target)], capture_output=True)
    assert geprueft.returncode == 0, geprueft.stderr.decode()


def test_wrapper_startet_ohne_mount_angaben_trotzdem(tmp_path: Path) -> None:
    target = write_wrapper(tmp_path, tmp_path / "fehlt.conf")
    lauf = subprocess.run([str(target), "/bin/echo", "gestartet"], capture_output=True)
    assert lauf.returncode == 0
    assert b"gestartet" in lauf.stdout


def test_startoption_enthaelt_command_platzhalter(tmp_path: Path) -> None:
    option = launch_option(tmp_path / "wrapper")
    assert option.endswith("%command%")
    assert str(tmp_path) in option


# ── Steam-Konfiguration ────────────────────────────────────────────────

def test_startoption_wird_gesetzt(tmp_path: Path, steam_aus: None) -> None:
    config = _config(tmp_path)
    set_launch_options("1091500", "/pfad/wrapper %command%", config)

    assert read_launch_options("1091500", config) == "/pfad/wrapper %command%"
    text = config.read_text(encoding="utf-8")
    assert text.count("{") == text.count("}")


def test_vorhandene_startoption_wird_ersetzt(tmp_path: Path, steam_aus: None) -> None:
    config = _config(tmp_path)
    set_launch_options("1091500", "erst %command%", config)
    set_launch_options("1091500", "dann %command%", config)

    assert read_launch_options("1091500", config) == "dann %command%"
    assert config.read_text(encoding="utf-8").count("LaunchOptions") == 1


def test_sicherung_wird_angelegt(tmp_path: Path, steam_aus: None) -> None:
    config = _config(tmp_path)
    set_launch_options("1091500", "x %command%", config)

    backup = config.with_suffix(config.suffix + ".anvil-backup")
    assert backup.is_file()
    assert backup.read_text(encoding="utf-8") == VDF


def test_andere_app_bleibt_unberuehrt(tmp_path: Path, steam_aus: None) -> None:
    config = _config(tmp_path)
    set_launch_options("1091500", "x %command%", config)

    assert read_launch_options("1234567", config) == ""


def test_depots_block_wird_nicht_getroffen(tmp_path: Path, steam_aus: None) -> None:
    config = _config(tmp_path)
    set_launch_options("1091500", "x %command%", config)

    text = config.read_text(encoding="utf-8")
    depots = text.index('"depots"')
    assert "LaunchOptions" not in text[depots:]


def test_unbekannte_app_meldet_fehler(tmp_path: Path, steam_aus: None) -> None:
    config = _config(tmp_path)
    with pytest.raises(RuntimeError):
        set_launch_options("999999", "x", config)


def test_laufendes_steam_blockiert(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("anvil.core.overlay_launch.steam_is_running", lambda: True)
    config = _config(tmp_path)
    with pytest.raises(RuntimeError):
        set_launch_options("1091500", "x", config)


def test_localconfig_wird_gefunden(tmp_path: Path) -> None:
    user = tmp_path / "userdata" / "42" / "config"
    user.mkdir(parents=True)
    (user / "localconfig.vdf").write_text(VDF, encoding="utf-8")

    assert localconfig_files(tmp_path) == [user / "localconfig.vdf"]


def test_ohne_userdata_leere_liste(tmp_path: Path) -> None:
    assert localconfig_files(tmp_path) == []


def test_wrapper_zaehlt_schichten_richtig(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    game = tmp_path / "game"
    stage.mkdir()
    game.mkdir()
    conf = tmp_path / "mount.conf"
    conf.write_text(
        f"MOUNT={game}|{stage}:{game}|{tmp_path / 'upper'}|{tmp_path / 'work'}\n",
        encoding="utf-8",
    )
    log = tmp_path / "start.log"
    target = write_wrapper(tmp_path, conf, log)

    subprocess.run([str(target), "/bin/true"], capture_output=True)

    inhalt = log.read_text(encoding="utf-8")
    assert "Mount 1: 2 Schichten" in inhalt
    assert "uebergebe an das Spiel" in inhalt
    force_rmtree(tmp_path / "work")


def test_wrapper_startet_bei_einer_schicht_ohne_mods(tmp_path: Path) -> None:
    game = tmp_path / "game"
    game.mkdir()
    conf = tmp_path / "mount.conf"
    conf.write_text(
        f"MOUNT={game}|{tmp_path / 'fehlt'}:{game}|{tmp_path / 'upper'}|{tmp_path / 'work'}\n",
        encoding="utf-8",
    )
    log = tmp_path / "start.log"
    target = write_wrapper(tmp_path, conf, log)

    lauf = subprocess.run([str(target), "/bin/echo", "trotzdem"], capture_output=True)

    assert b"trotzdem" in lauf.stdout
    assert "kein brauchbarer Mount" in log.read_text(encoding="utf-8")
