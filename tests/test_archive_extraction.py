"""RAR und 7z muessen auch ohne unrar und p7zip ankommen.

Im Flatpak liegt keins von beiden. Ohne Rueckfallebene liess sich dort
kein einziges RAR- und kein 7z-Archiv installieren -- und zwar lautlos:
die Mod fehlte danach einfach in der Liste.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from anvil.core.mod_installer import ModInstaller

QUELLE = Path("anvil/core/mod_installer.py").read_text(encoding="utf-8")


def _befehle(monkeypatch, vorhanden: set[str]) -> list[list[str]]:
    """Taeuscht die Werkzeugliste vor und protokolliert die Aufrufe."""
    gerufen: list[list[str]] = []

    monkeypatch.setattr(
        shutil, "which", lambda name: f"/usr/bin/{name}" if name in vorhanden else None,
    )

    def _run(befehl, **_kw):
        gerufen.append(list(befehl))
        return subprocess.CompletedProcess(befehl, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", _run)
    monkeypatch.setattr(ModInstaller, "_validate_extracted_paths", staticmethod(lambda *a: None))
    return gerufen


# ── RAR ──────────────────────────────────────────────────────────────


def test_unrar_wird_bevorzugt(monkeypatch, tmp_path: Path) -> None:
    gerufen = _befehle(monkeypatch, {"unrar", "bsdtar"})

    assert ModInstaller._extract_rar(tmp_path / "x.rar", tmp_path) is True
    assert gerufen[0][0] == "unrar"


def test_ohne_unrar_springt_bsdtar_ein(monkeypatch, tmp_path: Path) -> None:
    # Genau die Lage im Flatpak.
    gerufen = _befehle(monkeypatch, {"bsdtar"})

    assert ModInstaller._extract_rar(tmp_path / "x.rar", tmp_path) is True
    assert gerufen[0][0] == "bsdtar"
    assert "-C" in gerufen[0], "Zielordner muss mitgegeben werden"


def test_ohne_jedes_werkzeug_scheitert_es_sauber(monkeypatch, tmp_path: Path) -> None:
    _befehle(monkeypatch, set())
    assert ModInstaller._extract_rar(tmp_path / "x.rar", tmp_path) is False


# ── 7z ───────────────────────────────────────────────────────────────


def test_7z_wird_bevorzugt(monkeypatch, tmp_path: Path) -> None:
    gerufen = _befehle(monkeypatch, {"7z", "bsdtar"})

    assert ModInstaller._extract_7z(tmp_path / "x.7z", tmp_path) is True
    assert gerufen[0][0] == "7z"


def test_ohne_7z_springt_bsdtar_ein(monkeypatch, tmp_path: Path) -> None:
    gerufen = _befehle(monkeypatch, {"bsdtar"})

    assert ModInstaller._extract_7z(tmp_path / "x.7z", tmp_path) is True
    assert gerufen[0][0] == "bsdtar"


def test_7z_ohne_werkzeug_scheitert_sauber(monkeypatch, tmp_path: Path) -> None:
    _befehle(monkeypatch, set())
    assert ModInstaller._extract_7z(tmp_path / "x.7z", tmp_path) is False


# ── Fehlerbehandlung ─────────────────────────────────────────────────


def test_fehlgeschlagener_entpacker_meldet_false(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/bsdtar" if n == "bsdtar" else None)

    def _run(befehl, **_kw):
        raise subprocess.CalledProcessError(1, befehl, stderr=b"kaputt")

    monkeypatch.setattr(subprocess, "run", _run)
    assert ModInstaller._extract_rar(tmp_path / "x.rar", tmp_path) is False


def test_fehlendes_programm_stuerzt_nicht_ab(monkeypatch, tmp_path: Path) -> None:
    # which() kann luegen -- z.B. wenn das Programm zwischen Pruefung und
    # Aufruf verschwindet. Ein OSError darf die Installation nicht sprengen.
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/bsdtar" if n == "bsdtar" else None)

    def _run(befehl, **_kw):
        raise OSError("No such file or directory")

    monkeypatch.setattr(subprocess, "run", _run)
    assert ModInstaller._extract_rar(tmp_path / "x.rar", tmp_path) is False


# ── Echte Archive ────────────────────────────────────────────────────


@pytest.mark.skipif(not shutil.which("bsdtar"), reason="bsdtar nicht vorhanden")
def test_bsdtar_entpackt_ein_echtes_7z(tmp_path: Path) -> None:
    if not shutil.which("7z"):
        pytest.skip("7z zum Erzeugen des Testarchivs noetig")

    quelle = tmp_path / "quelle"
    quelle.mkdir()
    (quelle / "mod.archive").write_bytes(b"\x00" * 64)
    archiv = tmp_path / "test.7z"
    subprocess.run(["7z", "a", str(archiv), str(quelle / "mod.archive")],
                   check=True, capture_output=True)

    ziel = tmp_path / "ziel"
    ziel.mkdir()
    # bsdtar erzwingen, auch wenn 7z vorhanden ist
    subprocess.run(["bsdtar", "-x", "-f", str(archiv), "-C", str(ziel)],
                   check=True, capture_output=True)

    assert (ziel / "mod.archive").is_file()


# ── Sichtbare Meldung ────────────────────────────────────────────────

FENSTER = Path("anvil/mainwindow.py").read_text(encoding="utf-8")


def test_fehlschlag_wird_nicht_nur_in_die_statuszeile_geschrieben() -> None:
    # Die Statuszeile blendet nach Sekunden aus -- die Mod fehlte danach
    # kommentarlos, und genau so ging eine verloren.
    start = FENSTER.index('tr("error.extract_failed", name=archive.name)')
    block = FENSTER[start:start + 400]
    assert "QMessageBox.warning" in block
    assert "error.extract_failed_detail" in block


def test_meldungstexte_in_allen_sprachen() -> None:
    import glob
    import json

    for f in sorted(glob.glob("anvil/locales/*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        fehler = d.get("error", {})
        assert fehler.get("extract_failed_title"), f
        assert "{name}" in fehler.get("extract_failed_detail", ""), f


def test_beide_wege_stehen_im_modulkopf() -> None:
    kopf = QUELLE[:QUELLE.index('"""', 3) + 3]
    assert "bsdtar" in kopf
