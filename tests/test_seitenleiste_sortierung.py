"""Seitenleiste nach Spalten sortieren (#111).

Spielstaende und Daten sortieren nach Rohwerten (Zeitstempel, Bytes).
Downloads werden nur innerhalb ihrer Ordner-Gruppe umgestellt, laufende
Downloads bleiben in ihrer Zeile. Plugins: eine sortierte Ansicht ist nicht
die Ladereihenfolge -- plugins.txt wird daraus nie geschrieben.

Jeder Test biegt HOME auf ein Temp-Verzeichnis -- die Einstellungen
landen sonst in der echten Konfiguration.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QRect, QSettings, Qt
from PySide6.QtGui import QDropEvent, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QHeaderView, QTreeWidget,
)

import anvil.styles.dark_theme as dark_theme
from anvil.core.download_manager import DownloadTask
from anvil.core.translator import Translator, tr
from anvil.styles.dark_theme import apply_theme
from anvil.widgets.game_panel import GamePanel

ASC = Qt.SortOrder.AscendingOrder
DESC = Qt.SortOrder.DescendingOrder
SIEBEN_Z = b"7z\xbc\xaf\x27\x1c" + b"\x00" * 24


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    # Vorige Tests koennen ein modernes Theme geladen haben
    monkeypatch.setattr(dark_theme, "_current_palette", {})
    return tmp_path


@pytest.fixture
def panel(app, home):
    p = GamePanel()
    p.resize(500, 700)
    p.show()
    app.processEvents()
    yield p
    # Offene Breiten-Speicherungen schreiben, solange HOME umgebogen ist
    p.flush_column_widths()
    p.close()
    p.deleteLater()
    app.processEvents()


def _klick(app, header: QHeaderView, section: int) -> None:
    # Nur der sichtbare Reiter hat eine anklickbare Kopfzeile
    seite = header.parentWidget().parentWidget()
    tabs = seite.parentWidget().parentWidget()
    tabs.setCurrentWidget(seite)
    app.processEvents()
    assert header.isVisible()
    x = header.sectionViewportPosition(section) + header.sectionSize(section) // 2
    QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, QPoint(x, header.height() // 2))
    app.processEvents()


def _baum(tree) -> list[str]:
    return [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]


# ── Spielstaende ─────────────────────────────────────────────────────


class _SpielMitSaves:
    def listSaves(self, folder: Path) -> list[Path]:
        return sorted(folder.glob("*.sav"), key=lambda p: p.stat().st_mtime, reverse=True)


def _save(ordner: Path, name: str, wann: datetime, groesse: int) -> None:
    pfad = ordner / name
    pfad.write_bytes(b"x" * groesse)
    ts = wann.timestamp()
    os.utime(pfad, (ts, ts))


def test_c1_spielstaende_nach_datum_chronologisch(app, panel, tmp_path):
    saves = tmp_path / "saves"
    saves.mkdir()
    _save(saves, "herbst.sav", datetime(2025, 12, 10, 9, 0), 300)
    _save(saves, "winter.sav", datetime(2026, 1, 2, 9, 0), 100)
    _save(saves, "sommer.sav", datetime(2025, 6, 15, 9, 0), 200)
    tree = panel._saves_tree
    header = tree.header()

    panel._populate_saves_tree(saves, _SpielMitSaves())
    # Standard: neueste zuerst, wie listSaves
    assert (header.sortIndicatorSection(), header.sortIndicatorOrder()) == (1, DESC)
    assert header.isSortIndicatorShown()
    assert _baum(tree) == ["winter.sav", "herbst.sav", "sommer.sav"]

    # Erster Klick auf "Datum" dreht: aelteste zuerst -- nicht nach dem Text
    # ("02.01.2026" < "10.12.2025" < "15.06.2025")
    _klick(app, header, 1)
    assert (header.sortIndicatorSection(), header.sortIndicatorOrder()) == (1, ASC)
    assert _baum(tree) == ["sommer.sav", "herbst.sav", "winter.sav"]
    _klick(app, header, 1)
    assert _baum(tree) == ["winter.sav", "herbst.sav", "sommer.sav"]

    # Neu laden behaelt die gewaehlte Sortierung
    _klick(app, header, 2)
    assert _baum(tree) == ["winter.sav", "sommer.sav", "herbst.sav"]
    panel._populate_saves_tree(saves, _SpielMitSaves())
    assert _baum(tree) == ["winter.sav", "sommer.sav", "herbst.sav"]
    assert tree.isSortingEnabled()


def test_c1_keine_spielstaende_laesst_die_sortierung_an(app, panel, tmp_path):
    leer = tmp_path / "leer"
    leer.mkdir()
    panel._populate_saves_tree(leer, _SpielMitSaves())
    assert panel._saves_tree.topLevelItemCount() == 1
    assert panel._saves_tree.isSortingEnabled()


# ── Daten ────────────────────────────────────────────────────────────


def test_c2_daten_standard_und_groesse_nach_bytes(app, panel, tmp_path):
    spiel = tmp_path / "spiel"
    (spiel / "Data").mkdir(parents=True)
    (spiel / "b_neun.txt").write_bytes(b"x" * 9)
    (spiel / "a_zwei_kb.bin").write_bytes(b"x" * 2048)
    (spiel / "c_zehn.txt").write_bytes(b"x" * 10)
    panel._virtual_files = {"zzz_ordner/datei.txt": ["Mod"], "erst.esp": ["Mod"]}
    tree = panel._data_tree
    header = tree.header()

    panel._populate_data_tree(spiel)
    # Standard: heutige Einfuege-Reihenfolge (Ordner, Dateien, erst nach Deploy)
    assert tree.sortColumn() == -1
    assert _baum(tree) == ["Data", "a_zwei_kb.bin", "b_neun.txt", "c_zehn.txt",
                           "erst.esp", "zzz_ordner"]

    _klick(app, header, 3)
    assert (header.sortIndicatorSection(), header.sortIndicatorOrder()) == (3, ASC)
    groessen = [tree.topLevelItem(i).text(3) for i in range(tree.topLevelItemCount())]
    # "-" (Ordner, erst nach Deploy) zuerst, dann nach Bytes: 9 B, 10 B, 2.00 KB
    assert groessen[3:] == ["9 B", "10 B", "2.00 KB"]
    assert set(groessen[:3]) == {"-"}

    # Name: Ordner vor Dateien
    _klick(app, header, 0)
    assert _baum(tree) == ["Data", "zzz_ordner", "a_zwei_kb.bin", "b_neun.txt",
                           "c_zehn.txt", "erst.esp"]
    panel._populate_data_tree(spiel)
    assert _baum(tree) == ["Data", "zzz_ordner", "a_zwei_kb.bin", "b_neun.txt",
                           "c_zehn.txt", "erst.esp"]

    # Auch absteigend stehen die Ordner oben
    _klick(app, header, 0)
    assert (header.sortIndicatorSection(), header.sortIndicatorOrder()) == (0, DESC)
    assert _baum(tree) == ["zzz_ordner", "Data", "erst.esp", "c_zehn.txt",
                           "b_neun.txt", "a_zwei_kb.bin"]
    header.setSortIndicator(3, DESC)
    assert _baum(tree)[2:5] == ["a_zwei_kb.bin", "c_zehn.txt", "b_neun.txt"]


def test_c2_daten_ordner_immer_vor_dateien(app, panel, tmp_path):
    spiel = tmp_path / "spiel"
    (spiel / "Data").mkdir(parents=True)
    (spiel / "textures").mkdir()
    (spiel / "a.txt").write_bytes(b"x" * 5)
    (spiel / "zeta.dll").write_bytes(b"x" * 50)
    panel._virtual_files = {
        "a.txt": ["Zulu-Mod"], "bin/x.dll": ["Alpha-Mod"], "erst.esp": ["Mitte-Mod"],
    }
    tree = panel._data_tree
    header = tree.header()
    ordner = tr("game_panel.folder")
    panel._populate_data_tree(spiel)

    for spalte in range(tree.columnCount()):
        for richtung in (ASC, DESC):
            header.setSortIndicator(spalte, richtung)
            arten = [tree.topLevelItem(i).text(2) == ordner
                     for i in range(tree.topLevelItemCount())]
            assert arten == [True] * 3 + [False] * 3, (spalte, richtung, _baum(tree))


def test_c2_fehlender_spielordner_laesst_die_sortierung_an(panel, tmp_path):
    panel._populate_data_tree(tmp_path / "gibt-es-nicht")
    assert panel._data_tree.topLevelItemCount() == 1
    assert panel._data_tree.isSortingEnabled()


# ── Downloads ────────────────────────────────────────────────────────


def _archiv(pfad: Path, groesse: int, tag: int, versteckt: bool = False,
            installiert: bool = False) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(SIEBEN_Z + b"\x00" * groesse)
    ts = datetime(2026, 3, tag, 12, 0).timestamp()
    os.utime(pfad, (ts, ts))
    if versteckt or installiert:
        Path(str(pfad) + ".meta").write_text(
            f"[General]\nremoved={str(versteckt).lower()}\n"
            f"installed={str(installiert).lower()}\n", encoding="utf-8")


@pytest.fixture
def downloads(panel, tmp_path):
    dl = tmp_path / "downloads"
    _archiv(dl / "wurzel_klein.7z", 10, 1, installiert=True)
    _archiv(dl / "wurzel_gross.7z", 5000, 9)
    _archiv(dl / "Alpha" / "a_gross.7z", 3000, 2)
    _archiv(dl / "Alpha" / "a_klein.7z", 100, 8)
    _archiv(dl / "Alpha" / "a_mittel.7z", 900, 5, versteckt=True)
    _archiv(dl / "Beta" / "b_eins.7z", 50, 7)
    _archiv(dl / "Beta" / "b_zwei.7z", 70, 3)
    panel.set_downloads_path(dl, tmp_path / "mods", tmp_path / "profiles",
                             tmp_path / "overwrite")
    return dl


def _zeilen(panel) -> list[str]:
    table = panel._dl_table
    namen = []
    for r in range(table.rowCount()):
        item = table.item(r, 0)
        if panel._is_separator_row(r):
            namen.append("#" + item.data(Qt.ItemDataRole.UserRole + 3))
        else:
            namen.append(item.text())
    return namen


def _laufender_download(panel, tmp_path, download_id: int = 42) -> DownloadTask:
    task = DownloadTask(download_id, "https://example.invalid/x", "laeuft.7z",
                        tmp_path / "downloads" / "laeuft.7z", mod_name="Laeuft gerade")
    panel._download_manager._downloads[download_id] = task
    task.status = "downloading"  # wie DownloadManager._start_download
    panel._on_dm_started(download_id)
    return task


STANDARD = ["wurzel_gross.7z", "wurzel_klein.7z", "#Alpha", "a_gross.7z",
            "a_klein.7z", "a_mittel.7z", "#Beta", "b_eins.7z", "b_zwei.7z"]
GROESSE_AB = ["wurzel_gross.7z", "wurzel_klein.7z", "#Alpha", "a_gross.7z",
              "a_mittel.7z", "a_klein.7z", "#Beta", "b_zwei.7z", "b_eins.7z"]


def test_c3_downloads_innerhalb_der_ordner_sortiert(app, panel, downloads):
    table = panel._dl_table
    header = table.horizontalHeader()
    assert (header.sortIndicatorSection(), header.sortIndicatorOrder()) == (0, ASC)
    assert header.isSortIndicatorShown()
    assert _zeilen(panel) == STANDARD

    header.setSortIndicator(1, DESC)
    assert _zeilen(panel) == GROESSE_AB
    for r in (2, 6):
        assert table.columnSpan(r, 0) == 4

    # Echter Klick auf "Name": aufsteigend, zweiter Klick absteigend
    _klick(app, header, 0)
    assert _zeilen(panel) == STANDARD
    _klick(app, header, 0)
    assert (header.sortIndicatorSection(), header.sortIndicatorOrder()) == (0, DESC)
    assert _zeilen(panel) == ["wurzel_klein.7z", "wurzel_gross.7z", "#Alpha",
                              "a_mittel.7z", "a_klein.7z", "a_gross.7z", "#Beta",
                              "b_zwei.7z", "b_eins.7z"]
    for r in (2, 6):
        assert table.columnSpan(r, 0) == 4

    # Archivpfad und Datum reisen mit
    for r in range(table.rowCount()):
        if panel._is_separator_row(r):
            continue
        pfad = Path(table.item(r, 0).data(Qt.ItemDataRole.UserRole))
        assert pfad.name == table.item(r, 0).text()
        assert table.item(r, 1).data(Qt.ItemDataRole.UserRole) == pfad.stat().st_size
        assert table.item(r, 3).data(Qt.ItemDataRole.UserRole) == pfad.stat().st_mtime


def test_c3_dateizeit_und_status_innerhalb_der_ordner(app, panel, downloads):
    header = panel._dl_table.horizontalHeader()
    header.setSortIndicator(3, ASC)
    assert _zeilen(panel) == ["wurzel_klein.7z", "wurzel_gross.7z", "#Alpha",
                              "a_gross.7z", "a_mittel.7z", "a_klein.7z", "#Beta",
                              "b_zwei.7z", "b_eins.7z"]
    # Installiert steht vor "nicht installiert", sonst nach Name
    header.setSortIndicator(2, ASC)
    assert _zeilen(panel) == ["wurzel_klein.7z", "wurzel_gross.7z", *STANDARD[2:]]
    header.setSortIndicator(2, DESC)
    assert _zeilen(panel)[:2] == ["wurzel_gross.7z", "wurzel_klein.7z"]


def test_c3_auswahl_bleibt_beim_archiv(app, panel, downloads):
    table = panel._dl_table
    table.selectRow(4)  # a_klein.7z
    table.horizontalHeader().setSortIndicator(1, DESC)
    gewaehlt = {idx.row() for idx in table.selectedIndexes()}
    assert gewaehlt == {5}
    assert table.item(5, 0).text() == "a_klein.7z"


def test_c4_laufender_download_bleibt_in_seiner_zeile(app, panel, downloads, tmp_path):
    table = panel._dl_table
    task = _laufender_download(panel, tmp_path)
    assert panel._active_dl_rows == {42: 0}
    status_vorher = {r: table.item(r, 2).text() for r in range(1, table.rowCount())
                     if not panel._is_separator_row(r)}

    table.horizontalHeader().setSortIndicator(1, DESC)
    assert panel._active_dl_rows == {42: 0}
    assert table.item(0, 0).data(Qt.ItemDataRole.UserRole) == str(task.save_path)
    assert _zeilen(panel)[1:] == GROESSE_AB

    panel._on_dm_progress(42, 37.0, "1.0 MB/s")
    assert table.item(0, 2).text().startswith("37%")
    status_nachher = {r: table.item(r, 2).text() for r in range(1, table.rowCount())
                      if not panel._is_separator_row(r)}
    assert sorted(status_nachher.values()) == sorted(status_vorher.values())
    assert not any(t.startswith("37%") for t in status_nachher.values())


def test_c5_versteckte_und_eingeklappte_bleiben(app, panel, downloads):
    table = panel._dl_table
    panel._dl_collapsed.add("Beta")
    panel.refresh_downloads()

    def sichtbar() -> dict[str, bool]:
        return {name: not table.isRowHidden(r) for r, name in enumerate(_zeilen(panel))}

    vorher = sichtbar()
    assert vorher["a_mittel.7z"] is False     # .meta removed=true
    assert vorher["a_klein.7z"] is True
    assert vorher["b_eins.7z"] is False       # Ordner eingeklappt

    table.horizontalHeader().setSortIndicator(1, DESC)
    assert _zeilen(panel) == GROESSE_AB
    assert sichtbar() == vorher
    table.horizontalHeader().setSortIndicator(0, ASC)
    assert _zeilen(panel) == STANDARD
    assert sichtbar() == vorher


def test_c6_neuaufbau_behaelt_pfeil_und_sortierung(app, panel, downloads):
    header = panel._dl_table.horizontalHeader()
    header.setSortIndicator(1, DESC)
    panel.refresh_downloads()
    assert header.isSortIndicatorShown()
    assert (header.sortIndicatorSection(), header.sortIndicatorOrder()) == (1, DESC)
    assert _zeilen(panel) == GROESSE_AB
    for r in (2, 6):
        assert panel._dl_table.columnSpan(r, 0) == 4


def test_c9_neuaufbau_waehrend_eines_downloads(app, panel, downloads, tmp_path):
    table = panel._dl_table
    task = _laufender_download(panel, tmp_path)
    anderer = _laufender_download(panel, tmp_path, 43)
    assert panel._active_dl_rows == {43: 0, 42: 1}

    panel.refresh_downloads()  # z. B. Haken "versteckte Dateien" oder Neu laden
    assert panel._active_dl_rows == {43: 0, 42: 1}
    assert table.item(1, 0).data(Qt.ItemDataRole.UserRole) == str(task.save_path)
    assert table.item(0, 0).data(Qt.ItemDataRole.UserRole) == str(anderer.save_path)
    assert _zeilen(panel)[2:] == STANDARD
    for r in (4, 8):
        assert table.columnSpan(r, 0) == 4

    status_vorher = [table.item(r, 2).text() for r in range(table.rowCount())
                     if not panel._is_separator_row(r)]
    panel._on_dm_progress(42, 55.0, "2.0 MB/s")
    status_nachher = [table.item(r, 2).text() for r in range(table.rowCount())
                      if not panel._is_separator_row(r)]
    geaendert = [i for i, (a, b) in enumerate(zip(status_vorher, status_nachher)) if a != b]
    assert geaendert == [1]
    assert status_nachher[1].startswith("55%")

    # Beendete Downloads kommen beim Neuaufbau nicht zurueck, wartende haben
    # noch keine Zeile (die kommt mit download_started)
    anderer.status = "finished"
    wartend = DownloadTask(44, "https://example.invalid/y", "wartet.7z",
                           tmp_path / "downloads" / "wartet.7z")
    panel._download_manager._downloads[44] = wartend
    panel.refresh_downloads()
    assert panel._active_dl_rows == {42: 0}
    assert _zeilen(panel)[1:] == STANDARD


def _pfade(panel) -> list[Path]:
    table = panel._dl_table
    return [Path(table.item(r, 0).data(Qt.ItemDataRole.UserRole))
            for r in range(table.rowCount()) if not panel._is_separator_row(r)]


def test_c9_laufender_download_bleibt_in_seiner_instanz(app, panel, downloads, tmp_path):
    table = panel._dl_table
    task = _laufender_download(panel, tmp_path)
    andere = tmp_path / "instanz_b" / "downloads"
    _archiv(andere / "b_mod.7z", 10, 4)

    # Instanzwechsel waehrend des Downloads: in der fremden Liste keine Zeile
    # -- dort waere sein Archiv installier- und loeschbar
    panel.set_downloads_path(andere, tmp_path / "instanz_b" / "mods")
    assert panel._active_dl_rows == {}
    assert _zeilen(panel) == ["b_mod.7z"]
    assert all(pfad.parent == andere for pfad in _pfade(panel))
    status_b = [table.item(r, 2).text() for r in range(table.rowCount())]
    panel._on_dm_progress(42, 70.0, "1.0 MB/s")
    assert [table.item(r, 2).text() for r in range(table.rowCount())] == status_b

    # Zurueck: laeuft er noch, ist seine Zeile wieder oben und bekommt den Fortschritt
    panel.set_downloads_path(downloads, tmp_path / "mods")
    assert panel._active_dl_rows == {42: 0}
    assert table.item(0, 0).data(Qt.ItemDataRole.UserRole) == str(task.save_path)
    assert _zeilen(panel)[1:] == STANDARD
    panel._on_dm_progress(42, 70.0, "1.0 MB/s")
    assert table.item(0, 2).text().startswith("70%")

    # In der anderen Instanz fertig geworden: zurueck ohne Download-Zeile
    panel.set_downloads_path(andere, tmp_path / "instanz_b" / "mods")
    task.status = "finished"
    panel._on_dm_finished(42, str(task.save_path))
    assert _zeilen(panel) == ["b_mod.7z"]
    panel.set_downloads_path(downloads, tmp_path / "mods")
    assert panel._active_dl_rows == {}
    assert _zeilen(panel) == STANDARD

    # Ohne Download-Ordner gibt es keine Zeile
    task.status = "downloading"
    panel.set_downloads_path(tmp_path / "weg", tmp_path / "mods")
    assert panel._active_dl_rows == {}
    assert table.rowCount() == 0


def test_c9_wartender_download_startet_nach_dem_wechsel_ohne_zeile(app, panel, downloads, tmp_path):
    table = panel._dl_table
    # In Instanz A wartet ein Download, waehrend schon zwei laufen
    wartend = DownloadTask(45, "https://example.invalid/z", "drei.7z",
                           downloads / "drei.7z", mod_name="Drei")
    panel._download_manager._downloads[45] = wartend
    andere = tmp_path / "instanz_b" / "downloads"
    _archiv(andere / "b_mod.7z", 10, 4)
    panel.set_downloads_path(andere, tmp_path / "instanz_b" / "mods")

    # In B wird ein Platz frei, der wartende A-Download startet
    wartend.status = "downloading"
    panel._download_manager.download_started.emit(45)
    assert panel._active_dl_rows == {}
    assert _zeilen(panel) == ["b_mod.7z"]
    assert all(pfad.parent == andere for pfad in _pfade(panel))

    # Ein Download dieser Instanz bekommt seine Zeile wie gehabt
    eigener = DownloadTask(46, "https://example.invalid/b", "b_neu.7z", andere / "b_neu.7z")
    panel._download_manager._downloads[46] = eigener
    eigener.status = "downloading"
    panel._download_manager.download_started.emit(46)
    assert panel._active_dl_rows == {46: 0}
    assert table.item(0, 0).data(Qt.ItemDataRole.UserRole) == str(eigener.save_path)
    eigener.status = "finished"

    # Zurueck nach A: die Zeile ist oben und bekommt den Fortschritt
    panel.set_downloads_path(downloads, tmp_path / "mods")
    assert panel._active_dl_rows == {45: 0}
    assert table.item(0, 0).data(Qt.ItemDataRole.UserRole) == str(wartend.save_path)
    assert _zeilen(panel)[1:] == STANDARD
    panel._on_dm_progress(45, 12.0, "1.0 MB/s")
    assert table.item(0, 2).text().startswith("12%")


# ── Plugins ──────────────────────────────────────────────────────────


PRIMAER = ["Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm",
           "Dragonborn.esm"]


class _Skyrim:
    GameDataPath = "Data"
    PRIMARY_PLUGINS = PRIMAER
    PluginLoadOrderFormat = "asterisk"
    SupportsNativePluginSorting = True
    PluginIndexFormat = "regular-light"
    RequiresForgeDeployment = False
    NeedsBa2Packing = False
    ProtonDllOverrides: list[str] = []
    ImplicitPluginPrefixes = ("cc",)
    ImplicitPluginNames = ("_ResourcePack.esl",)

    def __init__(self, plugins_txt: Path) -> None:
        self._plugins_txt = plugins_txt

    def plugins_txt_path(self) -> Path:
        return self._plugins_txt

    def has_plugins_txt(self) -> bool:
        return True

    def creation_club_path(self) -> Path | None:
        return None


@pytest.fixture
def plugins(panel, tmp_path):
    spiel = tmp_path / "spiel"
    instanz = tmp_path / "instanz"
    extern = tmp_path / "prefix" / "plugins.txt"
    profil = instanz / ".profiles" / "Default" / "plugins.txt"
    namen = [*PRIMAER, "Zeta.esp", "Alpha.esp", "Mitte.esp", "Beta.esp"]
    (spiel / "Data").mkdir(parents=True)
    for name in namen:
        (spiel / "Data" / name).touch()
    profil.parent.mkdir(parents=True)
    profil.write_text(
        "".join(f"*{n}\n" for n in PRIMAER)
        + "*Zeta.esp\n*Alpha.esp\n*Mitte.esp\nBeta.esp\n", encoding="utf-8")
    panel._tabs.setTabVisible(0, True)  # wie bei einem Bethesda-Spiel
    panel._current_plugin = _Skyrim(extern)
    panel._current_game_path = spiel
    panel._instance_path = instanz
    panel._current_profile_name = "Default"
    panel._refresh_plugins_tab()
    return profil, extern


def _dateien(profil: Path, extern: Path) -> tuple[bytes, bytes | None]:
    return profil.read_bytes(), extern.read_bytes() if extern.exists() else None


def _verschiebe_letztes_nach_oben(panel) -> None:
    """Wie ein Drop: Baum-Reihenfolge von Hand aendern, dann melden."""
    tree = panel._plugins_tree
    letztes = tree.takeTopLevelItem(tree.topLevelItemCount() - 1)
    tree.insertTopLevelItem(len(PRIMAER), letztes)
    tree.order_dropped.emit()
    QApplication.processEvents()


LADEREIHENFOLGE = [*PRIMAER, "Zeta.esp", "Alpha.esp", "Mitte.esp", "Beta.esp"]


def test_c7_sortierte_plugins_schreiben_nie_die_plugins_txt(app, panel, plugins):
    profil, extern = plugins
    tree = panel._plugins_tree
    header = tree.header()
    assert (header.sortIndicatorSection(), header.sortIndicatorOrder()) == (2, ASC)
    assert header.isSortIndicatorShown()
    assert _baum(tree) == LADEREIHENFOLGE
    vorher = _dateien(profil, extern)

    # Echter Klick auf "Name": sortiert, Pfeil, Datei unberuehrt
    _klick(app, header, 0)
    assert (header.sortIndicatorSection(), header.sortIndicatorOrder()) == (0, ASC)
    _klick(app, header, 0)
    assert (header.sortIndicatorSection(), header.sortIndicatorOrder()) == (0, DESC)
    assert _baum(tree) == sorted(LADEREIHENFOLGE, key=str.casefold, reverse=True)
    assert tree.order_locked
    assert _dateien(profil, extern) == vorher

    # Wie ein Drop im sortierten Baum: plugins.txt bleibt byte-gleich
    _verschiebe_letztes_nach_oben(panel)
    assert _dateien(profil, extern) == vorher
    assert panel._persist_plugin_tree_order() is False
    assert _dateien(profil, extern) == vorher
    # Neuaufbau (z. B. nach dem Drop) behaelt die Sortierung
    panel._refresh_plugins_tab()
    assert _baum(tree) == sorted(LADEREIHENFOLGE, key=str.casefold, reverse=True)
    assert _dateien(profil, extern) == vorher

    # Index absteigend ist auch nicht die Ladereihenfolge
    header.setSortIndicator(2, DESC)
    assert _baum(tree) == list(reversed(LADEREIHENFOLGE))
    assert panel._persist_plugin_tree_order() is False
    assert _dateien(profil, extern) == vorher

    # Zurueck auf Index aufsteigend: Ladereihenfolge, Ziehen speichert wieder
    header.setSortIndicator(2, ASC)
    assert _baum(tree) == LADEREIHENFOLGE
    assert not tree.order_locked
    _verschiebe_letztes_nach_oben(panel)
    assert profil.read_text(encoding="utf-8").splitlines() == [
        *(f"*{n}" for n in PRIMAER), "Beta.esp", "*Zeta.esp", "*Alpha.esp", "*Mitte.esp",
    ]


def test_c8_haekchen_im_sortierten_zustand_aendert_nur_aktiv(app, panel, plugins):
    profil, _extern = plugins
    tree = panel._plugins_tree
    tree.header().setSortIndicator(0, ASC)
    beta = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                if tree.topLevelItem(i).text(0) == "Beta.esp")
    beta.setCheckState(0, Qt.CheckState.Checked)
    app.processEvents()

    assert profil.read_text(encoding="utf-8").splitlines() == [
        *(f"*{n}" for n in PRIMAER), "*Zeta.esp", "*Alpha.esp", "*Mitte.esp", "*Beta.esp",
    ]
    assert _baum(tree) == sorted(LADEREIHENFOLGE, key=str.casefold)


def test_c10_ziehen_im_sortierten_zustand_startet_nicht(app, panel, plugins, monkeypatch):
    gerufen = []
    monkeypatch.setattr(QAbstractItemView, "startDrag",
                        lambda self, actions: gerufen.append(actions))
    gemeldet = []
    panel.reorder_blocked.connect(lambda: gemeldet.append(1))
    tree = panel._plugins_tree

    tree.header().setSortIndicator(0, ASC)
    tree.startDrag(Qt.DropAction.MoveAction)
    assert gemeldet == [1]
    assert gerufen == []

    # Ablegen wird im sortierten Zustand abgewiesen, bevor der Baum etwas
    # verschiebt (ein kuenstliches Drop-Ereignis nimmt InternalMove ohnehin
    # nicht an -- deshalb zaehlt hier der Aufruf der Basisklasse)
    abgelegt = []

    def basis_drop(self, event):
        abgelegt.append(1)
        event.accept()

    monkeypatch.setattr(QTreeWidget, "dropEvent", basis_drop)
    quelle = tree.topLevelItem(tree.topLevelItemCount() - 1)
    ziel = tree.topLevelItem(len(PRIMAER))
    mime = tree.model().mimeData([tree.indexFromItem(quelle)])

    def drop() -> QDropEvent:
        event = QDropEvent(QPointF(tree.visualItemRect(ziel).center()),
                           Qt.DropAction.MoveAction, mime, Qt.MouseButton.LeftButton,
                           Qt.KeyboardModifier.NoModifier)
        tree.dropEvent(event)
        app.processEvents()
        return event

    assert not drop().isAccepted()
    assert abgelegt == []

    tree.header().setSortIndicator(2, ASC)
    tree.startDrag(Qt.DropAction.MoveAction)
    assert len(gerufen) == 1
    assert gemeldet == [1]
    assert drop().isAccepted()
    assert abgelegt == [1]


def test_k25_hinweis_landet_in_der_statusleiste(hauptfenster_prozess):
    ergebnis = hauptfenster_prozess("""
        tree = fenster._game_panel._plugins_tree
        ergebnis["vorher"] = fenster.statusBar().currentMessage()
        tree.header().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        tree.startDrag(Qt.DropAction.MoveAction)
        ergebnis["nachher"] = fenster.statusBar().currentMessage()
        ergebnis["soll"] = tr("status.plugins_sort_locked")
        ergebnis["modliste"] = tr("status.modlist_sort_locked")
    """)
    assert ergebnis["vorher"] == ""
    assert ergebnis["nachher"] == ergebnis["soll"]
    assert ergebnis["soll"] != ergebnis["modliste"]


# ── Texte und Kopfzeilen ─────────────────────────────────────────────


SPRACHEN = ("de", "en", "es", "fr", "it", "pt", "ru")


@pytest.mark.parametrize("sprache, richtung", [
    ("de", "(aufsteigend)"), ("en", "(ascending)"), ("es", "(ascendente)"),
    ("fr", "(croissant)"), ("it", "(crescente)"), ("pt", "(crescente)"),
    ("ru", "(по возрастанию)"),
])
def test_k25_hinweis_nennt_die_richtung(sprache, richtung):
    # Index absteigend ist auch gesperrt -- "nach Index sortiert" allein stimmt dann nicht
    daten = json.loads((Path(__file__).resolve().parents[1] / "anvil" / "locales"
                        / f"{sprache}.json").read_text(encoding="utf-8"))
    text = daten["status"]["plugins_sort_locked"]
    assert richtung in text
    assert daten["status"]["modlist_sort_locked"].count("(") == text.count("(") == 1


def _bild(header: QHeaderView, col: int) -> QImage:
    QApplication.processEvents()
    x = header.sectionViewportPosition(col)
    return header.grab(QRect(x, 0, header.sectionSize(col), header.height())).toImage(
    ).convertToFormat(QImage.Format.Format_RGB32)


def _spalten_mit_unterschied(a: QImage, b: QImage) -> list[int]:
    breite, hoehe = a.width(), a.height()
    pa, pb = bytes(a.constBits()), bytes(b.constBits())
    zeile = a.bytesPerLine()
    return [x for x in range(breite)
            if any(pa[y * zeile + 4 * x:y * zeile + 4 * x + 4]
                   != pb[y * zeile + 4 * x:y * zeile + 4 * x + 4] for y in range(hoehe))]


def _titel_setzen(view, col: int, text: str) -> None:
    if isinstance(view, QTreeWidget):
        view.headerItem().setText(col, text)
    else:
        view.horizontalHeaderItem(col).setText(text)


def _titel_und_pfeil(view, header: QHeaderView, col: int) -> tuple[list[int], list[int]]:
    """(Pixelspalten des Titels, Pixelspalten des Pfeils) bei der aktuellen Breite.

    Modern wandert der Pfeil mit dem Titel -- beides deshalb beim echten Titel
    messen: den Titel ohne Pfeil, den Pfeil als Unterschied dazu.
    """
    titel = view.headerItem().text(col) if isinstance(view, QTreeWidget) \
        else view.horizontalHeaderItem(col).text()
    header.setSortIndicatorShown(False)
    ohne_pfeil = _bild(header, col)
    _titel_setzen(view, col, "")
    leer = _bild(header, col)
    _titel_setzen(view, col, titel)
    header.setSortIndicatorShown(True)
    mit_pfeil = _bild(header, col)
    return _spalten_mit_unterschied(ohne_pfeil, leer), _spalten_mit_unterschied(mit_pfeil, ohne_pfeil)


def _feste_spalten_pruefen(app, p: GamePanel, ort: tuple) -> int:
    geprueft = 0
    for tab, view in ((0, p._plugins_tree), (2, p._saves_tree), (3, p._dl_table)):
        p._tabs.setCurrentIndex(tab)
        app.processEvents()
        header = view.header() if isinstance(view, QTreeWidget) else view.horizontalHeader()
        for col in range(header.count()):
            if (header.isSectionHidden(col)
                    or header.sectionResizeMode(col) != QHeaderView.ResizeMode.Fixed):
                continue
            header.setSortIndicator(col, ASC)
            breite = header.sectionSize(col)
            text, pfeil = _titel_und_pfeil(view, header, col)
            header.resizeSection(col, 400)
            voll, _ = _titel_und_pfeil(view, header, col)
            header.resizeSection(col, breite)
            wo = (*ort, type(view).__name__, col, breite)
            assert text and pfeil and voll, wo
            # Titel ganz sichtbar (1 px Kantenglaettung), links nicht
            # abgeschnitten, rechts vor dem Pfeil
            assert abs((max(text) - min(text)) - (max(voll) - min(voll))) <= 1, wo
            assert min(text) > 0, wo
            assert max(text) < min(pfeil), wo
            geprueft += 1
    return geprueft


def _pfeil_neben_dem_titel_pruefen(app, p: GamePanel, ort: tuple) -> int:
    """Modern steht der Pfeil hinter dem eigenen Titel, klassisch am Spaltenrand."""
    modern = bool(dark_theme.theme_color("panel2", ""))
    geprueft = 0
    for tab, view in ((0, p._plugins_tree), (1, p._data_tree), (2, p._saves_tree), (3, p._dl_table)):
        p._tabs.setCurrentIndex(tab)
        app.processEvents()
        header = view.header() if isinstance(view, QTreeWidget) else view.horizontalHeader()
        sichtbar = [c for c in range(header.count()) if not header.isSectionHidden(c)]
        for col in sichtbar:
            header.setSortIndicator(col, ASC)
            x, breite = header.sectionViewportPosition(col), header.sectionSize(col)
            text, pfeil = _titel_und_pfeil(view, header, col)
            wo = (*ort, type(view).__name__, col, breite)
            assert text and pfeil and x + breite <= header.viewport().width(), wo
            if modern:
                luft = min(pfeil) - max(text) - 1
                assert 2 <= luft <= 8, (wo, luft)
                assert breite - 1 - max(pfeil) >= 3, wo
                rechts = [c for c in sichtbar if c > col]
                # Ziehbare Spalten (Daten-Tab) behalten ihre Breite -- ist es dort
                # eng, rueckt der Pfeil an den Rand statt auf den Titel
                if rechts and header.sectionResizeMode(col) != QHeaderView.ResizeMode.Interactive:
                    nachbar, _ = _titel_und_pfeil(view, header, rechts[0])
                    zum_nachbarn = (header.sectionViewportPosition(rechts[0]) + min(nachbar)
                                    - (x + max(pfeil)) - 1)
                    assert zum_nachbarn >= luft + 6, (wo, luft, zum_nachbarn)
            else:
                assert breite - 1 - max(pfeil) <= 5, wo
            geprueft += 1
    return geprueft


def _langer_mittiger_titel_pruefen(app, p: GamePanel, ort: tuple) -> None:
    # Mittig ausgerichtet braucht der Pfeil rechts neben dem Titel mehr Platz
    table = p._dl_table
    header = table.horizontalHeader()
    p._tabs.setCurrentIndex(3)
    table.horizontalHeaderItem(2).setText("Statusstatusstatus")
    p._fit_sort_titles()
    header.setSortIndicator(2, ASC)
    breite = header.sectionSize(2)
    text, pfeil = _titel_und_pfeil(table, header, 2)
    header.resizeSection(2, 400)
    voll, _ = _titel_und_pfeil(table, header, 2)
    header.resizeSection(2, breite)
    wo = (*ort, breite)
    assert abs((max(text) - min(text)) - (max(voll) - min(voll))) <= 1, wo
    # Wie in jeder Spalte, deren Breite Anvil festlegt: Luft zum Titel und Platz
    # bis zum Rand -- nicht bloss knapp daneben gequetscht
    assert 5 <= min(pfeil) - max(text) - 1 <= 8, wo
    assert breite - 1 - max(pfeil) >= 9, wo


@pytest.mark.parametrize("theme", ["Anvil Dunkel", "Anvil Hell", "Nord"])
def test_c11_feste_spalten_zeigen_titel_und_pfeil(app, home, monkeypatch, theme):
    vorher = app.styleSheet()
    monkeypatch.setattr(Translator, "_instance", None)
    apply_theme(app, theme)
    geprueft = neben = 0
    try:
        for sprache in SPRACHEN:
            Translator.instance().load(sprache)
            p = GamePanel()
            try:
                # Breit genug, dass auch die 400-px-Vergleichsspalte ganz sichtbar ist
                p.resize(1000, 700)
                p.apply_theme_metrics()
                p._tabs.setTabVisible(0, True)
                p.show()
                app.processEvents()
                geprueft += _feste_spalten_pruefen(app, p, (theme, sprache, "Theme"))
                # Ein alter Stand mit 60 px fuer "Index" darf den Pfeil nicht zurueckbringen
                QSettings(str(home / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf"),
                          QSettings.Format.IniFormat).setValue(
                    "plugins/column_widths", [200, 80, 60])
                p.restore_tab_column_widths(0)
                geprueft += _feste_spalten_pruefen(app, p, (theme, sprache, "Stand"))
                neben += _pfeil_neben_dem_titel_pruefen(app, p, (theme, sprache))
                if theme != "Nord":
                    _langer_mittiger_titel_pruefen(app, p, (theme, sprache))
            finally:
                p.flush_column_widths()
                p.close()
                p.deleteLater()
                app.processEvents()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    finally:
        app.setStyleSheet(vorher)
    # modern: Typ, Index, Datum, Status -- klassisch nur Typ und Index; je zweimal
    assert geprueft == 2 * len(SPRACHEN) * (2 if theme == "Nord" else 4)
    # alle sichtbaren Spalten: Plugins 3, Daten 5, Spielstaende 2/3, Downloads 2
    assert neben == len(SPRACHEN) * (13 if theme == "Nord" else 12)
