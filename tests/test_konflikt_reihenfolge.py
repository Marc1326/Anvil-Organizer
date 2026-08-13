"""Die Konfliktanzeige muss die Mod nennen, die auch im Spiel gewinnt.

Der ConflictScanner laesst den letzten Listeneintrag gewinnen, in der
Mod-Liste steht die staerkste Mod aber oben. Die ungedrehte Liste fuehrte
dazu, dass Anvil die unterste Mod als Gewinner meldete, waehrend das
Deploy die oberste ausrollte.

BG3 ist ausgenommen und muss sich exakt wie vorher verhalten.
"""

from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PySide6.QtWidgets import QApplication, QTreeWidget

from anvil.core.conflict_scanner import ConflictScanner
from anvil.core.translator import tr
from anvil.dialogs.mod_detail_dialog import _build_conflicts_tab
from anvil.mainwindow import MainWindow
from anvil.widgets.game_panel import GamePanel

GETEILT = "Data/shared.esp"


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _eintrag(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        enabled=True,
        is_foreign=False,
        is_separator=False,
        is_data_override=False,
    )


def _bibliothek(tmp_path: Path) -> Path:
    """Zwei aktive Mods, beide liefern dieselbe Datei."""
    mods = tmp_path / ".mods"
    for name in ("Oben", "Unten"):
        (mods / name / "Data").mkdir(parents=True)
        (mods / name / "Data" / "shared.esp").write_bytes(name.encode())
    (mods / "Unten" / "Data" / "nur_unten.esp").write_bytes(b"x")
    return mods


def _fenster(tmp_path: Path, bg3=None, namen=("Oben", "Unten")) -> SimpleNamespace:
    """MainWindow-Ersatz mit genau den Teilen, die der Scan anfasst."""
    mods = _bibliothek(tmp_path)
    fenster = SimpleNamespace(
        _current_mod_entries=[_eintrag(n) for n in namen],
        _current_instance_path=tmp_path,
        _current_instance_paths=SimpleNamespace(mods=mods),
        _current_plugin=None,
        _mod_index=None,
        _bg3_installer=bg3,
        _game_panel=mock.MagicMock(),
    )
    for methode in (
        "_conflict_mod_list", "_run_conflict_scan", "_push_virtual_files",
        "_archive_hashes",
    ):
        setattr(
            fenster, methode,
            partial(getattr(MainWindow, methode), fenster),
        )
    return fenster


def _baeume(seite):
    """Gewinnt-Baum und Verliert-Baum aus dem Konflikte-Tab holen."""
    baeume = seite.findChildren(QTreeWidget)
    assert len(baeume) == 2
    nach_kopf = {b.headerItem().text(1): b for b in baeume}
    return (
        nach_kopf[tr("mod_detail.overwrites_mod")],
        nach_kopf[tr("mod_detail.overwritten_by_mod")],
    )


def _zeilen(baum) -> list[tuple[str, str]]:
    return [
        (baum.topLevelItem(i).text(0), baum.topLevelItem(i).text(1))
        for i in range(baum.topLevelItemCount())
    ]


# ── Kriterium 4: Konfliktanzeige in der Mod-Liste ────────────────────

def test_konfliktanzeige_nennt_die_obere_mod(tmp_path: Path) -> None:
    ergebnis = MainWindow._run_conflict_scan(_fenster(tmp_path))

    assert [k["winner"] for k in ergebnis["conflicts"]] == ["Oben"]


def test_mod_liste_bucht_den_gewinn_bei_der_oberen_mod(tmp_path: Path) -> None:
    daten = MainWindow._compute_conflict_data(_fenster(tmp_path))

    assert daten["Oben"]["type"] == "win"
    assert daten["Unten"]["type"] == "lose"
    assert daten["Unten"]["lose_mods_list"] == ["Oben"]


# ── Kriterium 5: Daten-Tab ───────────────────────────────────────────

def test_daten_tab_nennt_denselben_gewinner(tmp_path: Path) -> None:
    fenster = _fenster(tmp_path)

    MainWindow._compute_conflict_data(fenster)

    (owners,), _ = fenster._game_panel.set_virtual_files.call_args
    assert owners[GETEILT] == ["Unten", "Oben"]
    assert GamePanel._owner_label(owners[GETEILT]) == "Oben (+1)"


# ── Kriterium 6: Konflikte-Tab im Detailfenster ──────────────────────

def test_detailfenster_zeigt_die_obere_mod_als_gewinner(tmp_path: Path) -> None:
    _app()
    fenster = _fenster(tmp_path)
    alle = MainWindow._conflict_mod_list(fenster)

    # Die Seite muss am Leben bleiben, sonst raeumt Qt die Baeume weg
    seite_oben = _build_conflicts_tab("Oben", alle, None)
    gewinnt, verliert = _baeume(seite_oben)
    assert _zeilen(gewinnt) == [(GETEILT, "Unten")]
    assert _zeilen(verliert) == []

    seite_unten = _build_conflicts_tab("Unten", alle, None)
    gewinnt, verliert = _baeume(seite_unten)
    assert _zeilen(gewinnt) == []
    assert _zeilen(verliert) == [(GETEILT, "Oben")]


# ── Kriterium 7: BG3 bleibt, wie es war ──────────────────────────────

def test_bg3_scan_liefert_exakt_das_alte_ergebnis(tmp_path: Path) -> None:
    paks = {
        "oben-uuid": [{"rel": "mods/shared.lsx", "size": 1}],
        "unten-uuid": [{"rel": "mods/shared.lsx", "size": 2}],
    }
    fenster = _fenster(
        tmp_path, bg3=SimpleNamespace(), namen=("oben-uuid", "unten-uuid")
    )
    fenster._build_bg3_file_lists = lambda: paks

    ergebnis = MainWindow._run_conflict_scan(fenster)

    # Referenz: derselbe Aufruf, den der Code vor der Aenderung gemacht hat
    vorher = ConflictScanner().scan_conflicts(
        [{"name": "oben-uuid", "path": ""}, {"name": "unten-uuid", "path": ""}],
        None,
        pak_file_lists=paks,
    )
    assert ergebnis == vorher
    assert [k["winner"] for k in ergebnis["conflicts"]] == ["unten-uuid"]
    assert ergebnis["file_owners"]["mods/shared.lsx"] == [
        "oben-uuid", "unten-uuid",
    ]


def test_bg3_detailfenster_behaelt_die_reihenfolge(tmp_path: Path) -> None:
    fenster = _fenster(tmp_path, bg3=SimpleNamespace())

    namen = [m["name"] for m in MainWindow._conflict_mod_list(fenster)]

    assert namen == ["Oben", "Unten"]


def test_ohne_bg3_geht_die_liste_gedreht_in_den_scanner(tmp_path: Path) -> None:
    fenster = _fenster(tmp_path)

    namen = [m["name"] for m in MainWindow._conflict_mod_list(fenster)]

    assert namen == ["Unten", "Oben"]
