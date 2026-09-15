"""Zwei Fehler, die beim Sortieren auffielen (#111).

N1: Nach dem Verschieben prueft der Filter die Eintraege ueber die
Quellzeile -- er bekam die neue Reihenfolge nie mit und traf die Mods, die
vorher an dieser Stelle standen.

N5: Der Doppelklick baute den Mod-Pfad aus dem Anzeigenamen. Weicht der
vom Ordnernamen ab, zeigte der Detaildialog nichts oder die falsche Mod.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from anvil.core.mod_entry import ModEntry
from anvil.models.mod_list_model import COL_NAME, ROLE_FOLDER_NAME, mod_entry_to_row
from anvil.widgets.mod_list import ModListView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import anvil.styles.dark_theme as dark_theme
    monkeypatch.setattr(dark_theme, "_current_palette", {})
    return tmp_path


@pytest.fixture
def ansicht_bauen(app, home):
    """Baut Mod-Listen und raeumt sie auch bei scheiterndem Test weg --
    offene Breiten-Speicherungen landen so noch im Temp-HOME."""
    erzeugt = []

    def bauen(eintraege):
        v = ModListView()
        erzeugt.append(v)
        v.source_model().set_mods([mod_entry_to_row(e) for e in eintraege])
        v._proxy_model.set_mod_entries(list(eintraege))
        return v

    yield bauen
    for v in erzeugt:
        v.flush_column_widths()
        v.close()
        v.deleteLater()
    app.processEvents()


def _sichtbare_mods(v):
    px = v._proxy_model
    return [px.index(r, 0).data(ROLE_FOLDER_NAME) for r in range(px.rowCount())
            if not px.index(r, 0).data(Qt.ItemDataRole.UserRole + 1)]


# ── N1 ───────────────────────────────────────────────────────────────


class _FensterUmsortieren:
    def __init__(self, view, eintraege):
        self._mod_list_view = view
        self._current_mod_entries = eintraege
        self._bg3_installer = None

    def _write_current_modlist(self):
        pass

    def _update_active_count(self):
        pass

    def _compute_conflict_data(self):
        return {}

    def _check_group_consistency_after_reorder(self, model):
        pass

    def _schedule_redeploy(self):
        pass


def test_m1_filter_folgt_nach_dem_verschieben(ansicht_bauen):
    from anvil.mainwindow import MainWindow

    eintraege = [
        ModEntry(name="Sep_separator", is_separator=True),
        ModEntry(name="alpha_mod", display_name="Alpha"),
        ModEntry(name="beta_mod", display_name="Beta"),
        ModEntry(name="gamma_mod", display_name="Gamma"),
    ]
    v = ansicht_bauen(eintraege)
    model = v.source_model()
    fenster = _FensterUmsortieren(v, list(eintraege))

    # Gamma nach ganz oben unter den Trenner ziehen
    assert model._move_single_row(3, 1)
    MainWindow._on_mods_reordered(fenster)

    px = v._proxy_model
    assert len(px._mod_entries) == model.rowCount()
    for i, zeile in enumerate(model._rows):
        assert px._mod_entries[i].name == zeile.folder_name

    px.set_filter_state("gamma", set(), set())
    assert _sichtbare_mods(v) == ["gamma_mod"]
    px.set_filter_state("beta", set(), set())
    assert _sichtbare_mods(v) == ["beta_mod"]


# ── N5 ───────────────────────────────────────────────────────────────


class _Dialog:
    RESULT_PREV = 100
    RESULT_NEXT = 101
    aufrufe: list = []
    ergebnisse: list = []

    def __init__(self, parent=None, **kwargs):
        _Dialog.aufrufe.append(kwargs)

    def exec(self):
        return _Dialog.ergebnisse.pop(0) if _Dialog.ergebnisse else 0


class _FensterDoppelklick:
    def __init__(self, view, eintraege, instanz: Path, bg3=None):
        self._mod_list_view = view
        self._current_mod_entries = eintraege
        self._current_instance_path = instanz
        self._current_instance_paths = None
        self._current_plugin = None
        self._category_manager = None
        self._mod_index = None
        self._bg3_installer = bg3

    def _conflict_mod_list(self):
        return []

    def _archive_hashes(self, mods):
        return {}


@pytest.fixture
def dialog(monkeypatch):
    import anvil.mainwindow as mw

    _Dialog.aufrufe = []
    _Dialog.ergebnisse = []
    monkeypatch.setattr(mw, "ModDetailDialog", _Dialog)
    monkeypatch.setattr(mw, "_center_on_parent", lambda dlg: None)
    return _Dialog


def _doppelklick_daten():
    return [
        ModEntry(name="Sep_separator", is_separator=True),
        ModEntry(name="schoen_v2", display_name="Schön"),
        ModEntry(name="zweite_mod", display_name="Zweite"),
    ]


def test_m2_doppelklick_nutzt_den_ordnernamen(ansicht_bauen, dialog, tmp_path):
    from anvil.mainwindow import MainWindow

    eintraege = _doppelklick_daten()
    v = ansicht_bauen(eintraege)
    fenster = _FensterDoppelklick(v, eintraege, tmp_path / "instanz")
    idx = v._proxy_model.index(1, COL_NAME)

    dialog.ergebnisse = [_Dialog.RESULT_NEXT, 0]
    MainWindow._on_mod_double_click(fenster, idx)

    erster, zweiter = dialog.aufrufe
    assert erster["mod_name"] == "schoen_v2"
    assert Path(erster["mod_path"]).name == "schoen_v2"
    assert erster["mod_entry"] is eintraege[1]
    # Weiter springt zur naechsten sichtbaren Mod -- auch ueber den Ordner
    assert zweiter["mod_name"] == "zweite_mod"
    assert zweiter["mod_entry"] is eintraege[2]
    assert v._tree.currentIndex().data(ROLE_FOLDER_NAME) == "zweite_mod"


def test_m2_dialogtitel_bleibt_der_anzeigename(app, home, tmp_path):
    from anvil.dialogs import ModDetailDialog

    ordner = tmp_path / "mods" / "schoen_v2"
    ordner.mkdir(parents=True)
    eintrag = ModEntry(name="schoen_v2", display_name="Schön", install_path=ordner)
    dlg = ModDetailDialog(None, mod_name="schoen_v2", mod_path=str(ordner),
                          mod_entry=eintrag)
    assert dlg.windowTitle() == "Schön"
    ohne = ModDetailDialog(None, mod_name="Anzeige", mod_path=str(ordner))
    assert ohne.windowTitle() == "Anzeige"
    dlg.deleteLater()
    ohne.deleteLater()
    app.processEvents()


def test_m3_bg3_bleibt_beim_anzeigenamen(ansicht_bauen, dialog, tmp_path):
    from anvil.mainwindow import MainWindow

    eintraege = _doppelklick_daten()
    v = ansicht_bauen(eintraege)
    fenster = _FensterDoppelklick(v, eintraege, tmp_path / "instanz", bg3=object())
    idx = v._proxy_model.index(1, COL_NAME)

    dialog.ergebnisse = [_Dialog.RESULT_NEXT, 0]
    MainWindow._on_mod_double_click(fenster, idx)

    erster, zweiter = dialog.aufrufe
    assert erster["mod_name"] == "Schön"
    assert Path(erster["mod_path"]).name == "Schön"
    assert zweiter["mod_name"] == "Zweite"
