"""Modliste nach Spalten sortieren (#111).

Sortieren ist nur Anzeige: Trenner bleiben stehen, sortiert wird innerhalb
ihrer Bloecke, und die echte Reihenfolge (modlist.txt) aendert sich nie.
Solange nicht nach Prioritaet aufsteigend sortiert ist, laesst sich nichts
verschieben.

Jeder Test biegt HOME auf ein Temp-Verzeichnis -- die Einstellungen
landen sonst in der echten Konfiguration.
"""

from __future__ import annotations

import ast
import inspect
import os
import textwrap
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, QRect, QSettings, QSize, QUrl, Qt
from PySide6.QtGui import QDropEvent, QFont, QFontMetrics, QImage, QStandardItemModel
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QTreeView

import anvil.styles.dark_theme as dark_theme
import anvil.widgets.mod_list as mod_list
from anvil.core.mod_entry import ModEntry
from anvil.core.persistent_header import PersistentHeader
from anvil.core.translator import Translator
from anvil.models.mod_list_model import (
    COL_ARCHIVE_SIZE, COL_CATEGORY, COL_CHECK, COL_CONFLICTS, COL_COUNT,
    COL_DOWNLOAD_DATE, COL_INSTALLED_AT, COL_MARKERS, COL_NAME, COL_PRIORITY,
    COL_SIZE, COL_VERSION, ROLE_FOLDER_NAME, ROLE_SORT_VALUE,
    ModListModel, ModRow, mod_entry_to_row,
)
from anvil.widgets.mod_list import ModListView

ASC = Qt.SortOrder.AscendingOrder
DESC = Qt.SortOrder.DescendingOrder
SIEBEN_Z = b"7z\xbc\xaf\x27\x1c" + b"\x00" * 24

# Quellreihenfolge = modlist.txt
QUELLE = ["B", "A", "Sep1", "Zeta", "Alpha", "GKopf", "Mitte", "GMitglied",
          "Sep2", "F", "GFern", "E"]

MODERN = ("Anvil Dunkel", "Anvil Hell")
SPRACHEN = ("de", "en", "es", "fr", "it", "pt", "ru")
FESTE_SPALTEN = (COL_CONFLICTS, COL_MARKERS, COL_CATEGORY, COL_VERSION, COL_PRIORITY,
                 COL_INSTALLED_AT, COL_SIZE, COL_DOWNLOAD_DATE, COL_ARCHIVE_SIZE)
ZUSATZ = (COL_INSTALLED_AT, COL_SIZE, COL_DOWNLOAD_DATE, COL_ARCHIVE_SIZE)


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
def design(request, app, home):
    """Theme fuer den Test (Parameter), danach wieder ohne Stylesheet."""
    vorher = app.styleSheet()
    if getattr(request, "param", None):
        dark_theme.apply_theme(app, request.param)
    yield getattr(request, "param", None)
    app.setStyleSheet(vorher)


@pytest.fixture
def sprache():
    """Sprache umschalten; am Ende gilt wieder die vorige."""
    uebersetzer = Translator.instance()
    vorher = uebersetzer._current_lang
    yield uebersetzer.load
    uebersetzer.load(vorher)


def _konfig(home: Path) -> Path:
    return home / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf"


def _einstellungen(home: Path) -> QSettings:
    return QSettings(str(_konfig(home)), QSettings.Format.IniFormat)


class _Kategorien:
    def get_name(self, cat_id):
        return {7: "Kat X"}.get(cat_id, "")


def _zeilen() -> list[ModRow]:
    def mod(name, version="", category="", group="", head=False):
        return ModRow(True, name, version=version, category=category,
                      folder_name=name, group_name=group, is_group_head=head)

    def sep(name):
        return ModRow(True, name, is_separator=True, folder_name=name)

    zeilen = [
        mod("B", "1.0"), mod("A", "2.0"),
        sep("Sep1"),
        mod("Zeta", "1.10", category="7"), mod("Alpha", "1.9"),
        mod("GKopf", "3.0", group="G", head=True), mod("Mitte", "0.5"),
        mod("GMitglied", "0.1", group="G"),
        sep("Sep2"),
        mod("F", ""), mod("GFern", "5.0", group="G"), mod("E", "1.0"),
    ]
    for i, z in enumerate(zeilen):
        z.priority = i
    return zeilen


def _modern() -> bool:
    return bool(dark_theme.theme_color("panel2", ""))


def _titel_soll(v: ModListView, col: int) -> int:
    """Titelbreite in der Titelschrift plus Platz fuer den Sortierpfeil.

    Klassisch: Innenabstand 2 x 5 + Pfeil 10 + 4 Rand. Modern steht der Pfeil
    neben dem Titel: Innenabstand 5 + Luft 6 + Pfeil 10 + 9 frei bis zum Rand.
    """
    h = v._tree.header()
    h.ensurePolished()
    font = QFont(h.font())
    if _modern():
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.DemiBold)
    titel = v.source_model().headerData(col, Qt.Orientation.Horizontal)
    platz = 5 + 6 + 10 + 9 if _modern() else 2 * 5 + 10 + 4
    return QFontMetrics(font).horizontalAdvance(titel) + platz


def _wert_soll(v: ModListView, col: int) -> int:
    muster = {COL_INSTALLED_AT: "2026-09-14 21:27", COL_DOWNLOAD_DATE: "2026-09-14 21:27",
              COL_SIZE: "1023.99 MB", COL_ARCHIVE_SIZE: "1023.99 MB"}.get(col)
    if not muster:
        return 0
    tree = v._tree
    opt = QStyleOptionViewItem()
    opt.initFrom(tree)
    opt.font = tree.font()
    opt.text = muster
    opt.features |= QStyleOptionViewItem.ViewItemFeature.HasDisplay
    return tree.style().sizeFromContents(
        QStyle.ContentsType.CT_ItemViewItem, opt, QSize(), tree).width()


def _soll(v: ModListView, col: int) -> int:
    return max(mod_list._DEFAULT_WIDTHS[col], _titel_soll(v, col), _wert_soll(v, col))


def _modlist_breiten_roh(home: Path) -> bytes:
    """Die Zeile column_widths aus [modlist], so wie sie in der Datei steht."""
    abschnitt = b""
    for zeile in _konfig(home).read_bytes().splitlines():
        if zeile.startswith(b"["):
            abschnitt = zeile
        elif abschnitt == b"[modlist]" and zeile.startswith(b"column_widths="):
            return zeile
    return b""


def _ruhe(app, v: ModListView) -> None:
    """Verzoegerte Layouts abarbeiten und offene Breiten sofort schreiben."""
    app.processEvents()
    app.processEvents()
    v.flush_column_widths()


def _wegraeumen(app, widget) -> None:
    """Offene Breiten-Speicherungen jetzt schreiben -- solange HOME noch
    umgebogen ist. Ein spaeter feuernder Timer landete sonst in der echten
    Konfiguration."""
    widget.flush_column_widths()
    widget.close()
    widget.deleteLater()
    app.processEvents()


@pytest.fixture
def neu(app, home):
    """Baut Widgets und raeumt sie auch dann weg, wenn der Test scheitert."""
    erzeugt = []

    def bauen(klasse=ModListView):
        widget = klasse()
        erzeugt.append(widget)
        return widget

    yield bauen
    for widget in erzeugt:
        _wegraeumen(app, widget)


@pytest.fixture
def ansicht(app, neu):
    v = neu()
    v.resize(1100, 700)
    v.source_model().set_category_manager(_Kategorien())
    v.source_model().set_mods(_zeilen())
    v.show()
    app.processEvents()
    return v


def _anzeige(v: ModListView) -> list[str]:
    px = v._proxy_model
    return [px.index(r, 0).data(ROLE_FOLDER_NAME) for r in range(px.rowCount())]


def _sortiere(v: ModListView, col: int, order) -> None:
    v._tree.header().setSortIndicator(col, order)


# ── Normalzustand ────────────────────────────────────────────────────


def test_b1_standard_ist_die_echte_reihenfolge(ansicht):
    h = ansicht._tree.header()
    assert ansicht._proxy_model.sortColumn() == -1
    assert (h.sortIndicatorSection(), h.sortIndicatorOrder()) == (COL_PRIORITY, ASC)
    assert h.isSortIndicatorShown()
    assert _anzeige(ansicht) == QUELLE
    assert ansicht.is_priority_order()


def test_b2_echter_klick_sortiert_und_zweiter_dreht(ansicht, app):
    h = ansicht._tree.header()
    x = h.sectionViewportPosition(COL_NAME) + h.sectionSize(COL_NAME) // 2
    punkt = QPoint(x, h.height() // 2)
    QTest.mouseClick(h.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, punkt)
    app.processEvents()
    assert (h.sortIndicatorSection(), h.sortIndicatorOrder()) == (COL_NAME, ASC)
    assert ansicht._proxy_model.sortColumn() == COL_NAME
    assert _anzeige(ansicht)[:2] == ["A", "B"]
    QTest.mouseClick(h.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, punkt)
    app.processEvents()
    assert (h.sortIndicatorSection(), h.sortIndicatorOrder()) == (COL_NAME, DESC)
    assert ansicht._proxy_model.sortOrder() == DESC


def test_b2_klick_auf_neue_spalte_ist_aufsteigend(ansicht, app):
    h = ansicht._tree.header()
    _sortiere(ansicht, COL_NAME, DESC)
    x = h.sectionViewportPosition(COL_VERSION) + h.sectionSize(COL_VERSION) // 2
    QTest.mouseClick(h.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, QPoint(x, h.height() // 2))
    app.processEvents()
    assert (h.sortIndicatorSection(), h.sortIndicatorOrder()) == (COL_VERSION, ASC)


def test_b2_klick_auf_schalterspalte_aendert_nichts(ansicht, app):
    h = ansicht._tree.header()
    x = h.sectionViewportPosition(COL_CHECK) + h.sectionSize(COL_CHECK) // 2
    QTest.mouseClick(h.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, QPoint(x, h.height() // 2))
    app.processEvents()
    assert (h.sortIndicatorSection(), h.sortIndicatorOrder()) == (COL_PRIORITY, ASC)
    assert ansicht.is_priority_order()
    assert _anzeige(ansicht) == QUELLE


# ── Bloecke, Richtung, Gruppen ───────────────────────────────────────


def test_b3_name_aufsteigend_innerhalb_der_bloecke(ansicht):
    _sortiere(ansicht, COL_NAME, ASC)
    anzeige = _anzeige(ansicht)
    assert anzeige == ["A", "B", "Sep1", "Alpha", "GKopf", "GMitglied", "Mitte",
                       "Zeta", "Sep2", "E", "F", "GFern"]
    # Jeder Trenner steht auf seiner Quellposition -- die Scrollleisten-
    # Marken rechnen damit.
    assert anzeige.index("Sep1") == QUELLE.index("Sep1")
    assert anzeige.index("Sep2") == QUELLE.index("Sep2")


def test_b4_name_absteigend_trenner_bleiben_oben(ansicht):
    _sortiere(ansicht, COL_NAME, DESC)
    assert _anzeige(ansicht) == ["B", "A", "Sep1", "Zeta", "Mitte", "GKopf",
                                 "GMitglied", "Alpha", "Sep2", "GFern", "F", "E"]


def test_b5_quellmodell_bleibt_unberuehrt(ansicht):
    src = ansicht.source_model()
    ordner = [r.folder_name for r in src._rows]
    prio = [r.priority for r in src._rows]
    # mods_reordered ist der einzige Weg zum Schreiben der modlist.txt
    geschrieben = []
    src.mods_reordered.connect(lambda: geschrieben.append(1))
    for col in (COL_NAME, COL_VERSION, COL_CATEGORY, COL_CONFLICTS, COL_PRIORITY,
                COL_INSTALLED_AT, COL_SIZE, COL_DOWNLOAD_DATE, COL_ARCHIVE_SIZE):
        for order in (ASC, DESC):
            _sortiere(ansicht, col, order)
            assert [r.folder_name for r in src._rows] == ordner, (col, order)
            assert [r.priority for r in src._rows] == prio, (col, order)
    _sortiere(ansicht, COL_PRIORITY, ASC)
    assert _anzeige(ansicht) == QUELLE
    assert geschrieben == []


def test_b6_gruppe_bleibt_hinter_ihrem_kopf(ansicht):
    for col in (COL_NAME, COL_VERSION, COL_CATEGORY, COL_PRIORITY, COL_SIZE):
        for order in (ASC, DESC):
            if (col, order) == (COL_PRIORITY, ASC):
                continue  # echte Reihenfolge, dort wird nichts gruppiert
            _sortiere(ansicht, col, order)
            anzeige = _anzeige(ansicht)
            assert anzeige.index("GMitglied") == anzeige.index("GKopf") + 1, (col, order)
    # Mitglied in einem anderen Block: nach eigenem Wert
    _sortiere(ansicht, COL_VERSION, ASC)
    assert _anzeige(ansicht)[9:] == ["E", "GFern", "F"]
    _sortiere(ansicht, COL_VERSION, DESC)
    assert _anzeige(ansicht)[9:] == ["GFern", "E", "F"]


def test_b7_version_natuerlich_und_leer_immer_unten(ansicht):
    _sortiere(ansicht, COL_VERSION, ASC)
    assert _anzeige(ansicht) == ["B", "A", "Sep1", "Mitte", "Alpha", "Zeta", "GKopf",
                                 "GMitglied", "Sep2", "E", "GFern", "F"]
    _sortiere(ansicht, COL_VERSION, DESC)
    assert _anzeige(ansicht) == ["A", "B", "Sep1", "GKopf", "GMitglied", "Zeta",
                                 "Alpha", "Mitte", "Sep2", "GFern", "E", "F"]


def test_kategorie_leere_unten_in_quellreihenfolge(ansicht):
    for order in (ASC, DESC):
        _sortiere(ansicht, COL_CATEGORY, order)
        assert _anzeige(ansicht)[2:8] == ["Sep1", "Zeta", "Alpha", "GKopf",
                                          "GMitglied", "Mitte"]


def test_b10_prioritaet_absteigend_dreht_nur_die_mods(ansicht):
    _sortiere(ansicht, COL_PRIORITY, DESC)
    assert not ansicht.is_priority_order()
    assert _anzeige(ansicht) == ["A", "B", "Sep1", "Mitte", "GKopf", "GMitglied",
                                 "Alpha", "Zeta", "Sep2", "E", "GFern", "F"]


# ── Sperre fuer Verschieben ──────────────────────────────────────────


def test_b8_ziehen_ist_sortiert_gesperrt(ansicht, monkeypatch):
    gerufen = []
    monkeypatch.setattr(QTreeView, "startDrag",
                        lambda self, actions: gerufen.append(actions))
    gemeldet = []
    ansicht.reorder_blocked.connect(lambda: gemeldet.append(1))
    tree = ansicht._tree

    _sortiere(ansicht, COL_NAME, ASC)
    tree._pending_separator_toggle = "Sep1"
    tree._pending_group_toggle = "G"
    tree.startDrag(Qt.DropAction.MoveAction)
    assert gemeldet == [1]
    assert gerufen == []
    assert tree._pending_separator_toggle is None
    assert tree._pending_group_toggle is None

    # Priorität aufsteigend: Ziehen laeuft wie bisher
    _sortiere(ansicht, COL_PRIORITY, ASC)
    tree.startDrag(Qt.DropAction.MoveAction)
    assert len(gerufen) == 1
    assert gemeldet == [1]


def _mime_zeile(src: ModListModel, row: int) -> QMimeData:
    return src.mimeData([src.index(row, 0)])


def test_b9_proxy_nimmt_sortiert_keinen_internen_drop_an(ansicht):
    src = ansicht.source_model()
    px = ansicht._proxy_model
    ordner = [r.folder_name for r in src._rows]

    _sortiere(ansicht, COL_NAME, ASC)
    mime = _mime_zeile(src, QUELLE.index("E"))
    assert not px.canDropMimeData(mime, Qt.DropAction.MoveAction, 3, 0, px.index(-1, -1))
    assert not px.dropMimeData(mime, Qt.DropAction.MoveAction, 3, 0, px.index(-1, -1))
    assert [r.folder_name for r in src._rows] == ordner

    _sortiere(ansicht, COL_PRIORITY, ASC)
    mime = _mime_zeile(src, QUELLE.index("E"))
    assert px.canDropMimeData(mime, Qt.DropAction.MoveAction, 3, 0, px.index(-1, -1))
    assert px.dropMimeData(mime, Qt.DropAction.MoveAction, 3, 0, px.index(-1, -1))
    assert [r.folder_name for r in src._rows] != ordner
    assert [r.folder_name for r in src._rows][3] == "E"


def test_b22_archiv_drop_sortiert_ohne_position(ansicht, app, tmp_path):
    archiv = tmp_path / "neu.7z"
    archiv.write_bytes(SIEBEN_Z)
    ohne, mit = [], []
    ansicht._tree.archives_dropped.connect(lambda p: ohne.append(p))
    ansicht._tree.archives_dropped_at.connect(lambda p, r: mit.append((p, r)))

    def fallen_lassen():
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(archiv))])
        px = ansicht._proxy_model
        rect = ansicht._tree.visualRect(px.index(4, COL_NAME))
        ansicht._tree.dropEvent(QDropEvent(
            QPointF(rect.center()), Qt.DropAction.CopyAction, mime,
            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
        ))

    _sortiere(ansicht, COL_NAME, ASC)
    fallen_lassen()
    assert ohne == [[str(archiv)]]
    assert mit == []

    # Gegenprobe: in Prioritaetsordnung zaehlt die Zielzeile weiter
    _sortiere(ansicht, COL_PRIORITY, ASC)
    fallen_lassen()
    assert len(mit) == 1 and mit[0][1] == 4


class _Statusleiste:
    def __init__(self):
        self.meldungen = []

    def showMessage(self, text, ms=0):
        self.meldungen.append(text)


class _FensterVerschieben:
    def __init__(self, view):
        self._mod_list_view = view
        self.leiste = _Statusleiste()

    def statusBar(self):
        return self.leiste


def test_b23_in_trenner_verschieben_ist_sortiert_gesperrt(ansicht):
    from anvil.core.translator import tr
    from anvil.mainwindow import MainWindow

    src = ansicht.source_model()
    ordner = [r.folder_name for r in src._rows]
    fenster = _FensterVerschieben(ansicht)

    _sortiere(ansicht, COL_NAME, ASC)
    MainWindow._ctx_move_to_separator(fenster, [QUELLE.index("A")], "Sep2")
    assert [r.folder_name for r in src._rows] == ordner
    assert fenster.leiste.meldungen == [tr("status.modlist_sort_locked")]

    _sortiere(ansicht, COL_PRIORITY, ASC)
    MainWindow._ctx_move_to_separator(fenster, [QUELLE.index("A")], "Sep2")
    assert [r.folder_name for r in src._rows] != ordner


# ── Einklappen, Filter, Cache ────────────────────────────────────────


def test_b11_einklappen_folgt_der_einstellung(ansicht):
    tree = ansicht._tree
    tree._collapsed_separators.add("Sep1")

    _sortiere(ansicht, COL_NAME, ASC)
    tree._collapsible_asc = True
    tree._collapsible_dsc = False
    tree._apply_separator_filter()
    assert _anzeige(ansicht) == ["A", "B", "Sep1", "Sep2", "E", "F", "GFern"]

    tree._collapsed_separators.discard("Sep1")
    tree._apply_separator_filter()
    assert _anzeige(ansicht) == ["A", "B", "Sep1", "Alpha", "GKopf", "GMitglied",
                                 "Mitte", "Zeta", "Sep2", "E", "F", "GFern"]

    tree._collapsed_separators.add("Sep1")
    tree._collapsible_asc = False
    tree._collapsible_dsc = True
    tree._apply_separator_filter()
    assert len(_anzeige(ansicht)) == len(QUELLE)

    _sortiere(ansicht, COL_PRIORITY, DESC)
    tree._collapsible_asc = True
    tree._collapsible_dsc = False
    tree._apply_separator_filter()
    assert len(_anzeige(ansicht)) == len(QUELLE)


def test_b12_filter_und_sortierung_zusammen(ansicht):
    src = ansicht.source_model()
    eintraege = [ModEntry(name=r.folder_name, display_name=r.name,
                          is_separator=r.is_separator) for r in src._rows]
    px = ansicht._proxy_model
    px.set_mod_entries(eintraege)

    _sortiere(ansicht, COL_NAME, ASC)
    px.set_filter_state("a", set(), set())
    assert _anzeige(ansicht) == ["A", "Sep1", "Alpha", "Zeta", "Sep2"]

    px.set_filter_state("", set(), set())
    assert _anzeige(ansicht) == ["A", "B", "Sep1", "Alpha", "GKopf", "GMitglied",
                                 "Mitte", "Zeta", "Sep2", "E", "F", "GFern"]


def _einfach(namen):
    return [ModRow(True, n, folder_name=n, is_separator=n.startswith("Sep")) for n in namen]


def test_b13_cache_folgt_den_daten(ansicht, app):
    src = ansicht.source_model()
    px = ansicht._proxy_model
    src.set_mods(_einfach(["b", "a", "c"]))
    _sortiere(ansicht, COL_NAME, ASC)
    assert _anzeige(ansicht) == ["a", "b", "c"]

    src.set_mods(_einfach(["z", "x", "y"]))
    assert _anzeige(ansicht) == ["x", "y", "z"]

    src._rows[1].name = "zzz"
    src.dataChanged.emit(src.index(1, COL_NAME), src.index(1, COL_NAME),
                         [Qt.ItemDataRole.DisplayRole])
    app.processEvents()
    assert _anzeige(ansicht) == ["y", "z", "x"]

    # Auswahl/Hervorhebung sendet BackgroundRole -- das darf nichts ausloesen
    raenge = px._ranks
    src.set_highlighted_rows({0})
    src.set_conflict_highlight({1}, {2})
    assert px._ranks is raenge
    assert not px._resort_timer.isActive()


def test_b14_schnell_und_ohne_plattenzugriff(app, neu, home, monkeypatch):
    v = neu()
    zeilen = []
    for i in range(2000):
        if i % 25 == 0:
            zeilen.append(ModRow(True, f"S{i}", is_separator=True, folder_name=f"S{i}"))
        else:
            n = f"mod{(i * 7919) % 2003:05d}"
            zeilen.append(ModRow(True, n, folder_name=f"{n}_{i}", version=f"1.{i % 13}"))
    v.source_model().set_mods(zeilen)

    zugriffe = []
    werte = []
    sort_value = ModListModel.sort_value

    def stat_verboten(*args, **kwargs):
        zugriffe.append(args)
        raise OSError("kein Plattenzugriff beim Sortieren")

    def gezaehlt(self, row, col):
        werte.append(row)
        return sort_value(self, row, col)

    # context() statt undo(): undo() hoebe auch das umgebogene HOME auf
    with monkeypatch.context() as mp:
        mp.setattr(os, "stat", stat_verboten)
        mp.setattr(Path, "stat", stat_verboten)
        mp.setattr(ModListModel, "sort_value", gezaehlt)
        _sortiere(v, COL_NAME, ASC)
        nach_name = len(werte)
        _sortiere(v, COL_VERSION, DESC)
    assert zugriffe == []
    # Ein Sortierwert je Zeile, nicht je Vergleich
    mods = sum(1 for z in zeilen if not z.is_separator)
    assert nach_name == mods
    assert len(werte) == 2 * mods
    assert v._proxy_model.sortColumn() == COL_VERSION
    # Der Abbau schreibt offene Breiten noch -- ins Temp-HOME
    assert Path.home() == home


# ── Speichern und Spaltenwahl ────────────────────────────────────────


def test_b15_sortierung_ueberlebt_den_neustart(ansicht, neu, home):
    _sortiere(ansicht, COL_VERSION, DESC)
    s = _einstellungen(home)
    assert s.value("modlist/sort_column") == "version"
    assert s.value("modlist/sort_order") == "desc"

    zweite = neu()
    zweite.source_model().set_mods(_zeilen())
    assert zweite.is_priority_order(), "der Konstruktor liest keine Einstellungen"
    zweite.restore_column_widths()
    h = zweite._tree.header()
    assert (h.sortIndicatorSection(), h.sortIndicatorOrder()) == (COL_VERSION, DESC)
    assert zweite._proxy_model.sortColumn() == COL_VERSION
    assert zweite._proxy_model.sortOrder() == DESC


@pytest.mark.parametrize("design", ["Nord", "Anvil Dunkel"], indirect=True)
def test_b16_neue_spalten_und_breitenschutz(app, design, neu, home):
    ansicht = neu()
    ansicht.resize(1100, 700)
    ansicht.source_model().set_mods(_zeilen())
    ansicht.show()
    app.processEvents()
    tree = ansicht._tree
    for col in (COL_INSTALLED_AT, COL_SIZE, COL_DOWNLOAD_DATE, COL_ARCHIVE_SIZE):
        assert tree.isColumnHidden(col)
    for col in range(COL_NAME, COL_PRIORITY + 1):
        assert not tree.isColumnHidden(col)

    # Ein alter Stand hat versteckte Spalten mit Breite 0 gespeichert
    _einstellungen(home).setValue("modlist/column_widths",
                                  [36, 300, 80, 80, 100, 80, 90, 0, 0, 0, 0])
    ansicht.restore_column_widths()
    # Archivgroesse und Markierungen: der Titel ist breiter als die Grundbreite
    ansicht.set_column_visible(COL_ARCHIVE_SIZE, True)
    assert not tree.isColumnHidden(COL_ARCHIVE_SIZE)
    soll = _soll(ansicht, COL_ARCHIVE_SIZE)
    assert tree.header().sectionSize(COL_ARCHIVE_SIZE) == soll > mod_list._DEFAULT_WIDTHS[COL_ARCHIVE_SIZE]
    assert _einstellungen(home).value("modlist/column_visible/archive_size", type=bool) is True

    ansicht.set_column_visible(COL_MARKERS, False)
    assert tree.isColumnHidden(COL_MARKERS)
    assert _einstellungen(home).value("modlist/column_visible/markers", type=bool) is False

    ansicht.set_column_visible(COL_NAME, False)
    ansicht.set_column_visible(COL_PRIORITY, False)
    ansicht.set_column_visible(COL_CHECK, False)
    assert not tree.isColumnHidden(COL_NAME)
    assert not tree.isColumnHidden(COL_PRIORITY)
    assert not tree.isColumnHidden(COL_CHECK)
    _ruhe(app, ansicht)

    # Neustart: Wahl bleibt, und die ausgeblendeten Markierungen kommen beim
    # Einblenden lesbar zurueck
    zweite = neu()
    zweite.source_model().set_mods(_zeilen())
    zweite.restore_column_widths()
    h = zweite._tree.header()
    assert not zweite._tree.isColumnHidden(COL_ARCHIVE_SIZE)
    assert h.sectionSize(COL_ARCHIVE_SIZE) == _soll(zweite, COL_ARCHIVE_SIZE)
    assert zweite._tree.isColumnHidden(COL_MARKERS)
    zweite.set_column_visible(COL_MARKERS, True)
    soll = _soll(zweite, COL_MARKERS)
    assert h.sectionSize(COL_MARKERS) == soll > mod_list._DEFAULT_WIDTHS[COL_MARKERS]


def test_b17_sortierte_spalte_ausblenden_springt_auf_prioritaet(ansicht):
    _sortiere(ansicht, COL_VERSION, ASC)
    assert not ansicht.is_priority_order()
    ansicht.set_column_visible(COL_VERSION, False)
    h = ansicht._tree.header()
    assert (h.sortIndicatorSection(), h.sortIndicatorOrder()) == (COL_PRIORITY, ASC)
    assert ansicht.is_priority_order()
    assert _anzeige(ansicht) == QUELLE


def test_kopfzeilen_menue(ansicht):
    from anvil.core.translator import tr

    menu = ansicht._build_header_menu()
    aktionen = [a for a in menu.actions() if not a.isSeparator()]
    assert aktionen[0].text() == tr("label.sort_by_priority")
    assert not aktionen[0].isEnabled(), "schon nach Priorität sortiert"
    spalten = {a.data(): a for a in aktionen[1:]}
    assert COL_CHECK not in spalten
    assert set(spalten) == set(range(COL_NAME, COL_COUNT))
    for col in (COL_NAME, COL_PRIORITY):
        assert spalten[col].isChecked() and not spalten[col].isEnabled()
    assert spalten[COL_CATEGORY].isChecked() and spalten[COL_CATEGORY].isEnabled()
    assert not spalten[COL_INSTALLED_AT].isChecked()
    assert spalten[COL_INSTALLED_AT].text() == tr("label.header_installed_at")

    spalten[COL_INSTALLED_AT].setChecked(True)
    assert not ansicht._tree.isColumnHidden(COL_INSTALLED_AT)
    spalten[COL_CATEGORY].setChecked(False)
    assert ansicht._tree.isColumnHidden(COL_CATEGORY)
    menu.deleteLater()

    _sortiere(ansicht, COL_NAME, ASC)
    menu = ansicht._build_header_menu()
    zurueck = [a for a in menu.actions() if not a.isSeparator()][0]
    assert zurueck.isEnabled()
    zurueck.trigger()
    assert ansicht.is_priority_order()
    menu.deleteLater()


def test_kopfzeile_meldet_rechtsklick_in_viewport_koordinaten(ansicht, app):
    from PySide6.QtGui import QContextMenuEvent

    h = ansicht._tree.header()
    gemeldet = []
    h.customContextMenuRequested.disconnect()
    h.customContextMenuRequested.connect(lambda pos: gemeldet.append(pos))
    punkt = QPoint(123, 7)
    app.sendEvent(h.viewport(), QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse, punkt, h.viewport().mapToGlobal(punkt)))
    assert gemeldet == [punkt]


@pytest.mark.parametrize("design", ["Nord", "Anvil Dunkel"], indirect=True)
def test_b18_bg3_schalter_aendert_nichts_an_der_konfiguration(app, design, neu, home):
    gespeichert = [36, 300, 80, 80, 0, 80, 90, 130, 80, 130, 90]
    s = _einstellungen(home)
    s.setValue("modlist/sort_column", "name")
    s.setValue("modlist/sort_order", "asc")
    s.setValue("modlist/column_visible/size", True)
    # Kategorie war ausgeblendet und steht deshalb mit Breite 0 in der Liste
    s.setValue("modlist/column_visible/category", False)
    s.setValue("modlist/column_widths", gespeichert)
    s.sync()
    del s

    def breiten_passen(sichtbar):
        h = v._tree.header()
        for col in sichtbar:
            assert not v._tree.isColumnHidden(col), col
            if _modern():
                soll = _soll(v, col)
            elif gespeichert[col] > 0:
                soll = gespeichert[col]
            else:
                soll = _soll(v, col)
            assert h.sectionSize(col) == soll, col

    v = neu()
    v.resize(1100, 700)
    v.source_model().set_mods(_zeilen())
    v.show()
    v.restore_column_widths()
    _ruhe(app, v)
    assert v._proxy_model.sortColumn() == COL_NAME
    assert not v._tree.isColumnHidden(COL_SIZE)
    assert v._tree.isColumnHidden(COL_CATEGORY)
    breiten_passen([COL_CONFLICTS, COL_MARKERS, COL_VERSION, COL_PRIORITY, COL_SIZE])
    vorher = _konfig(home).read_bytes()

    v.set_view_features_enabled(False)
    _ruhe(app, v)
    h = v._tree.header()
    assert not h.sectionsClickable()
    assert not h.isSortIndicatorShown()
    assert h.contextMenuPolicy() == Qt.ContextMenuPolicy.NoContextMenu
    # Rechtsklick auf den Kopf tut nichts
    from PySide6.QtGui import QContextMenuEvent
    menues = []
    v.context_menu_requested.connect(lambda pos: menues.append(pos))
    h.customContextMenuRequested.connect(lambda pos: menues.append(pos))
    punkt = QPoint(40, 5)
    app.sendEvent(h.viewport(), QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse, punkt, h.viewport().mapToGlobal(punkt)))
    assert menues == []
    assert v._header_menu is None
    assert v._proxy_model.sortColumn() == -1
    assert _anzeige(v) == QUELLE
    for col in (COL_INSTALLED_AT, COL_SIZE, COL_DOWNLOAD_DATE, COL_ARCHIVE_SIZE):
        assert v._tree.isColumnHidden(col)
    # Standardspalten lesbar breit -- auch die mit gespeicherter Breite 0
    breiten_passen(range(COL_CONFLICTS, COL_PRIORITY + 1))
    # Auch ein Laden der Instanz wendet nichts an
    v.restore_column_widths()
    breiten_passen(range(COL_CONFLICTS, COL_PRIORITY + 1))
    v._on_sort_indicator_changed(COL_NAME, ASC)
    v.set_column_visible(COL_SIZE, True)
    # Fenstergroesse aendern: modern dehnt sich die Name-Spalte neu
    v.resize(900, 700)
    _ruhe(app, v)
    assert v._proxy_model.sortColumn() == -1
    assert v._tree.isColumnHidden(COL_SIZE)
    assert _konfig(home).read_bytes() == vorher

    # Zurueck in eine normale Instanz: wie _apply_instance + _restore_ui_state
    v.set_view_features_enabled(True)
    v.restore_column_widths()
    assert h.sectionsClickable() and h.isSortIndicatorShown()
    assert h.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
    assert v._proxy_model.sortColumn() == COL_NAME
    assert not v._tree.isColumnHidden(COL_SIZE)
    assert v._tree.isColumnHidden(COL_CATEGORY)
    breiten_passen([COL_CONFLICTS, COL_MARKERS, COL_VERSION, COL_PRIORITY, COL_SIZE])


def test_b19_frameworks_und_presets_nicht_sortierbar(ansicht):
    assert not ansicht._fw_tree.header().sectionsClickable()
    assert not ansicht._ps_tree.header().sectionsClickable()
    assert not ansicht._fw_tree.isSortingEnabled()
    assert not ansicht._ps_tree.isSortingEnabled()


@pytest.mark.parametrize("design", [None, "Nord", "Anvil Dunkel"], indirect=True)
def test_b25_konstruktor_schreibt_keine_breiten(app, design, neu, home):
    v = neu()
    v.resize(1000, 600)
    v.show()
    app.processEvents()
    app.processEvents()
    assert not v._persistent_header._save_timer.isActive()
    v.flush_column_widths()
    konfig = _konfig(home)
    if konfig.exists():
        assert _einstellungen(home).value("modlist/column_widths") is None


# ── Zusatzspalten ────────────────────────────────────────────────────


def test_b20_zusatzspalten_zeigen_daten_ohne_platte(home):
    from datetime import datetime

    eintrag = ModEntry(name="mod_a", display_name="Mod A",
                       install_date="2026-02-08T15:00:00.123456+00:00",
                       installation_file="C:\\Downloads\\Mod-A-123.7z",
                       total_size=1234567)
    zeile = mod_entry_to_row(eintrag)
    erwartet_ts = datetime.fromisoformat("2026-02-08T15:00:00.123456+00:00").timestamp()
    assert zeile.install_ts == pytest.approx(erwartet_ts)
    assert zeile.archive_key == "mod-a-123.7z"
    assert zeile.total_size == 1234567

    ohne_datum = mod_entry_to_row(ModEntry(name="mod_b", install_date="kaputt"))
    rueckfall = mod_entry_to_row(ModEntry(name="Mod_C"))
    trenner = mod_entry_to_row(ModEntry(name="X_separator", is_separator=True))

    m = ModListModel()
    m.set_mods([zeile, ohne_datum, rueckfall, trenner])

    def zelle(row, col):
        return m.data(m.index(row, col), Qt.ItemDataRole.DisplayRole)

    assert zelle(0, COL_INSTALLED_AT) == datetime.fromtimestamp(erwartet_ts).strftime("%Y-%m-%d %H:%M")
    assert zelle(0, COL_SIZE) == "1.18 MB"
    assert zelle(1, COL_INSTALLED_AT) == ""
    assert zelle(3, COL_SIZE) == ""
    assert zelle(0, COL_DOWNLOAD_DATE) == ""

    geaendert = []
    m.dataChanged.connect(lambda tl, br, roles: geaendert.append((tl.column(), br.column())))
    mtime = datetime(2026, 1, 2, 3, 4).timestamp()
    m.set_archive_stats({"mod-a-123.7z": (2048, mtime)}, {"mod_c": (10, mtime)})
    assert geaendert == [(COL_DOWNLOAD_DATE, COL_ARCHIVE_SIZE)]
    assert zelle(0, COL_DOWNLOAD_DATE) == "2026-01-02 03:04"
    assert zelle(0, COL_ARCHIVE_SIZE) == "2.00 KB"
    assert zelle(2, COL_ARCHIVE_SIZE) == "10 B", "Rueckfall ueber den Mod-Ordner"
    assert zelle(1, COL_DOWNLOAD_DATE) == "" and zelle(1, COL_ARCHIVE_SIZE) == ""
    assert zelle(3, COL_DOWNLOAD_DATE) == "" and zelle(3, COL_ARCHIVE_SIZE) == ""
    assert m.data(m.index(0, COL_ARCHIVE_SIZE), Qt.ItemDataRole.TextAlignmentRole) & Qt.AlignmentFlag.AlignRight

    # Sortierwerte ueber die Rolle
    assert m.data(m.index(0, COL_ARCHIVE_SIZE), ROLE_SORT_VALUE) == (True, 2048)
    assert m.data(m.index(1, COL_ARCHIVE_SIZE), ROLE_SORT_VALUE)[0] is False
    assert m.data(m.index(1, COL_INSTALLED_AT), ROLE_SORT_VALUE)[0] is False
    assert m.data(m.index(3, COL_SIZE), ROLE_SORT_VALUE)[0] is False

    # Tabellen ueberleben den Neuaufbau
    m.set_mods([mod_entry_to_row(eintrag)])
    assert zelle(0, COL_ARCHIVE_SIZE) == "2.00 KB"


def test_zusatzspalten_leere_stehen_in_beiden_richtungen_unten(ansicht):
    src = ansicht.source_model()
    for r in src._rows:
        if r.folder_name in ("Alpha", "Mitte"):
            r.archive_key = f"{r.folder_name.lower()}.7z"
    src.set_archive_stats({"alpha.7z": (5, 100.0), "mitte.7z": (9, 50.0)}, {})
    for order in (ASC, DESC):
        _sortiere(ansicht, COL_ARCHIVE_SIZE, order)
        block = _anzeige(ansicht)[3:8]
        erwartet = ["Alpha", "Mitte"] if order == ASC else ["Mitte", "Alpha"]
        assert block[:2] == erwartet, (order, block)
        assert block[2:] == ["Zeta", "GKopf", "GMitglied"]


def test_downloads_scan_liefert_archivdaten(app, neu, tmp_path):
    from anvil.widgets.game_panel import GamePanel

    downloads = tmp_path / "downloads"
    (downloads / "Ordner").mkdir(parents=True)
    (downloads / "Wurzel.7z").write_bytes(SIEBEN_Z)
    (downloads / "Wurzel.7z.meta").write_text(
        "[General]\ninstalled=true\ninstallationFile=Mein Mod\n", encoding="utf-8")
    (downloads / "Ordner" / "Innen.7z").write_bytes(SIEBEN_Z * 2)

    panel = neu(GamePanel)
    erhalten = []
    panel.downloads_scanned.connect(lambda a, b: erhalten.append((a, b)))
    panel.set_downloads_path(downloads, tmp_path / "mods", tmp_path / "profiles",
                             tmp_path / "overwrite")
    assert erhalten, "kein Signal nach dem Scan"
    by_file, by_mod = erhalten[-1]
    assert by_file["wurzel.7z"][0] == len(SIEBEN_Z)
    assert by_file["innen.7z"][0] == len(SIEBEN_Z) * 2
    assert by_mod == {"mein mod": by_file["wurzel.7z"]}

    erhalten.clear()
    panel.set_downloads_path(tmp_path / "gibt-es-nicht", tmp_path / "mods",
                             tmp_path / "profiles", tmp_path / "overwrite")
    assert erhalten == [({}, {})]


# ── PersistentHeader und das alte sort() ─────────────────────────────


def test_b21_kuerzere_gespeicherte_breiten_werden_uebernommen(app, home):
    modell = QStandardItemModel(0, 11)
    view = QTreeView()
    view.setModel(modell)
    h = view.header()
    h.setStretchLastSection(False)
    for i in range(11):
        view.setColumnWidth(i, 90)
    ph = PersistentHeader(h, "probe")
    try:
        _einstellungen(home).setValue("probe/column_widths", [61, 62, 63, 64, 65, 66, 67])
        assert ph.restore() is True
        assert [h.sectionSize(i) for i in range(11)] == [61, 62, 63, 64, 65, 66, 67, 90, 90, 90, 90]

        _einstellungen(home).setValue("probe/column_widths", [70] * 12)
        assert ph.restore() is False
        assert h.sectionSize(0) == 61
    finally:
        ph.flush()
        view.deleteLater()


def test_b24_modell_hat_kein_eigenes_sort_mehr():
    assert "sort" not in ModListModel.__dict__


def test_d1_persistent_header_nullen_und_ausgeschaltet(app, home):
    modell = QStandardItemModel(0, 4)
    view = QTreeView()
    view.setModel(modell)
    h = view.header()
    h.setStretchLastSection(False)
    for i in range(4):
        view.setColumnWidth(i, 90)
    ph = PersistentHeader(h, "probe")
    try:
        # 0 = war ausgeblendet, -1 = gestreckt: beides nicht uebernehmen
        _einstellungen(home).setValue("probe/column_widths", [0, -1, 55, 66])
        assert ph.restore() is True
        assert [h.sectionSize(i) for i in range(4)] == [90, 90, 55, 66]

        # Ausgeschaltet: weder lesen noch schreiben -- auch nicht, wenn die
        # Speicherung schon lief
        view.setColumnWidth(2, 77)
        assert ph._save_timer.isActive()
        ph.enabled = False
        ph.flush()
        ph._write_widths()
        gelesen = _einstellungen(home).value("probe/column_widths")
        assert [int(w) for w in gelesen] == [0, -1, 55, 66]
        _einstellungen(home).setValue("probe/column_widths", [11, 22, 33, 44])
        assert ph.restore() is False
        assert h.sectionSize(0) == 90
    finally:
        ph.enabled = False
        view.deleteLater()


# ── Breiten: modern reine Anzeige, Titel + Pfeil passen (D1) ──────────


def _kopfbild(h, col) -> QImage:
    x = h.sectionViewportPosition(col)
    bild = h.viewport().grab(QRect(x, 0, h.sectionSize(col), h.height())).toImage()
    return bild.convertToFormat(QImage.Format.Format_RGB32)


def _titel_ende_und_pfeil(h, col) -> tuple[int, int]:
    """Letzte Pixelspalte des Titels und erste des Sortierpfeils."""
    h.setSortIndicator(COL_NAME, ASC)
    QApplication.processEvents()
    ohne = _kopfbild(h, col)
    h.setSortIndicator(col, DESC)
    QApplication.processEvents()
    mit = _kopfbild(h, col)
    hoehe, breite = ohne.height(), ohne.width()
    grund = ohne.pixel(2, hoehe // 2)
    # Rand unten/rechts (klassisch 2 px) auslassen
    titel = [x for x in range(breite - 3)
             if any(ohne.pixel(x, y) != grund for y in range(2, hoehe - 3))]
    pfeil = [x for x in range(breite)
             if any(ohne.pixel(x, y) != mit.pixel(x, y) for y in range(hoehe))]
    assert titel and pfeil
    return max(titel), min(pfeil)


def _zusatzspalten_ansicht(app, neu) -> ModListView:
    v = neu()
    v.resize(2400, 300)
    ts = datetime(2026, 9, 14, 21, 27).timestamp()
    zeile = ModRow(True, "a", folder_name="a", install_ts=ts,
                   total_size=int(1023.99 * 1024 * 1024))
    v.source_model().set_mods([zeile])
    v.show()
    app.processEvents()
    v.restore_column_widths()
    for col in ZUSATZ:
        v.set_column_visible(col, True)
    app.processEvents()
    return v


def _ganzer_kopf(h) -> tuple[bytes, int, int]:
    QApplication.processEvents()
    bild = h.viewport().grab().toImage().convertToFormat(QImage.Format.Format_RGB32)
    return bytes(bild.constBits()), bild.bytesPerLine(), bild.height()


def _pixel(kopf, x, y) -> bytes:
    daten, zeile, _ = kopf
    return daten[y * zeile + 4 * x:y * zeile + 4 * x + 4]


def _luft_um_den_pfeil(h, col) -> tuple[int, int | None]:
    """(Luft Titel -> Pfeil, Luft Pfeil -> Titel der naechsten sichtbaren Spalte).

    Beides im ganzen Kopf gemessen, der Pfeil als Unterschied zum Kopf ohne Pfeil.
    """
    h.setSortIndicatorShown(False)
    ohne = _ganzer_kopf(h)
    h.setSortIndicatorShown(True)
    h.setSortIndicator(col, DESC)
    mit = _ganzer_kopf(h)
    hoehe = ohne[2]

    def titel(c):
        x, breite = h.sectionViewportPosition(c), h.sectionSize(c)
        grund = _pixel(ohne, x + 2, hoehe // 2)
        return [px for px in range(x, x + breite - 3)
                if any(_pixel(ohne, px, y) != grund for y in range(2, hoehe - 3))]

    x, breite = h.sectionViewportPosition(col), h.sectionSize(col)
    pfeil = [px for px in range(x, x + breite)
             if any(_pixel(ohne, px, y) != _pixel(mit, px, y) for y in range(hoehe))]
    eigener = titel(col)
    assert eigener and pfeil, col
    rechts = [c for c in range(col + 1, h.count()) if not h.isSectionHidden(c)]
    nachbar = titel(rechts[0]) if rechts else []
    return (min(pfeil) - max(eigener) - 1,
            min(nachbar) - max(pfeil) - 1 if nachbar else None)


@pytest.mark.parametrize("lang", SPRACHEN)
@pytest.mark.parametrize("design", [*MODERN, "Nord"], indirect=True)
def test_d1_titel_und_pfeil_passen_in_jeder_sprache(app, design, sprache, neu, lang):
    sprache(lang)
    v = _zusatzspalten_ansicht(app, neu)
    h = v._tree.header()
    # Modern ist jede feste Spalte betroffen, klassisch die frisch eingeblendeten
    for col in (FESTE_SPALTEN if _modern() else ZUSATZ):
        assert h.sectionSize(col) == _soll(v, col), col
        ende, pfeil = _titel_ende_und_pfeil(h, col)
        assert ende + 2 < pfeil, (col, ende, pfeil)
    if not _modern():
        return
    # Modern ohne Trennlinien: der Pfeil gehoert sichtbar zum eigenen Titel,
    # nicht zum Titel der Nachbarspalte
    for col in (COL_NAME, *FESTE_SPALTEN):
        luft, zum_nachbarn = _luft_um_den_pfeil(h, col)
        assert 2 <= luft <= 8, (col, luft)
        if zum_nachbarn is not None:
            assert zum_nachbarn >= luft + 6, (col, luft, zum_nachbarn)


@pytest.mark.parametrize("design", [*MODERN, "Nord"], indirect=True)
def test_d1_zusatzspalten_zeigen_den_wert_ganz(app, design, neu, monkeypatch):
    # Standardbreiten kleiner als der Wert: dann muss der Wert die Breite geben
    for col in (COL_INSTALLED_AT, COL_SIZE):
        monkeypatch.setitem(mod_list._DEFAULT_WIDTHS, col, 30)
    v = _zusatzspalten_ansicht(app, neu)
    tree = v._tree
    tree.header().setSortIndicator(COL_PRIORITY, ASC)

    def text_breite(col):
        idx = v._proxy_model.index(0, col)
        bild = tree.viewport().grab(tree.visualRect(idx)).toImage()
        grund = bild.pixel(1, 1)
        xs = [x for x in range(bild.width())
              if any(bild.pixel(x, y) != grund for y in range(bild.height()))]
        return max(xs) - min(xs) + 1

    for col in (COL_INSTALLED_AT, COL_SIZE):
        standard = tree.header().sectionSize(col)
        assert standard >= _wert_soll(v, col) > 30
        gezeigt = text_breite(col)
        tree.header().resizeSection(col, 400)
        app.processEvents()
        assert gezeigt == text_breite(col), col
        tree.header().resizeSection(col, standard)


@pytest.mark.parametrize("design", MODERN, indirect=True)
def test_d1_modern_liest_und_schreibt_keine_breiten(app, design, neu, home):
    gespeichert = [36, 300, 80, 80, 100, 80, 60, 130, 80, 130, 90]
    s = _einstellungen(home)
    s.setValue("modlist/column_widths", gespeichert)
    s.setValue("modlist/column_visible/size", True)
    s.sync()
    del s
    vorher = _modlist_breiten_roh(home)
    assert vorher

    v = neu()
    v.resize(1100, 700)
    v.source_model().set_mods(_zeilen())
    v.show()
    app.processEvents()
    v.restore_column_widths()
    h = v._tree.header()
    sichtbar = [c for c in FESTE_SPALTEN if not v._tree.isColumnHidden(c)]
    assert COL_SIZE in sichtbar and COL_PRIORITY in sichtbar
    for col in sichtbar:
        assert h.sectionSize(col) == _soll(v, col), col
    assert h.sectionSize(COL_PRIORITY) != 60
    # Name dehnt sich beim Anzeigen und beim Vergroessern neu
    v.resize(1400, 700)
    _ruhe(app, v)
    assert _modlist_breiten_roh(home) == vorher

    # Live nach klassisch: die gespeicherten Breiten sind wieder da
    dark_theme.apply_theme(app, "Nord")
    v.apply_theme_metrics()
    _ruhe(app, v)
    assert [h.sectionSize(c) for c in range(COL_NAME, COL_PRIORITY + 1)] == gespeichert[1:7]
    assert h.sectionSize(COL_SIZE) == 80
    assert _modlist_breiten_roh(home) == vorher

    # Und wieder modern
    dark_theme.apply_theme(app, design)
    v.apply_theme_metrics()
    _ruhe(app, v)
    for col in sichtbar:
        assert h.sectionSize(col) == _soll(v, col), col
    assert _modlist_breiten_roh(home) == vorher


@pytest.mark.parametrize("design", MODERN, indirect=True)
def test_d1_modern_breiten_folgen_der_sprache(app, design, sprache, neu):
    sprache("de")
    v = _zusatzspalten_ansicht(app, neu)
    h = v._tree.header()
    deutsch = h.sectionSize(COL_ARCHIVE_SIZE)
    assert deutsch == _soll(v, COL_ARCHIVE_SIZE)
    # Nach dem Sprachwechsel laedt das Hauptfenster die Instanz neu
    sprache("es")
    v.restore_column_widths()
    assert h.sectionSize(COL_ARCHIVE_SIZE) == _soll(v, COL_ARCHIVE_SIZE) > deutsch
    # Auch in einer BG3-Instanz (Sortieren aus) folgen die festen Spalten
    v.set_view_features_enabled(False)
    sprache("ru")
    v.restore_column_widths()
    assert h.sectionSize(COL_CONFLICTS) == _soll(v, COL_CONFLICTS) > 80


@pytest.mark.parametrize("design", ["Nord"], indirect=True)
def test_d1_klassisch_zusatzspalten_mindestens_standardbreite(app, design, neu, home):
    # So stand es nach dem ersten Bau in der Konfiguration: 30 px je Zusatzspalte
    s = _einstellungen(home)
    s.setValue("modlist/column_widths", [36, 300, 80, 80, 100, 80, 90, 30, 30, 30, 30])
    for col in ZUSATZ:
        s.setValue(f"modlist/column_visible/{mod_list._COLUMN_KEYS[col]}", True)
    s.sync()
    del s

    v = neu()
    v.resize(1400, 700)
    v.source_model().set_mods(_zeilen())
    v.show()
    app.processEvents()
    v.restore_column_widths()
    h = v._tree.header()
    for col in ZUSATZ:
        assert h.sectionSize(col) == _soll(v, col), col

    # Selbst breiter gezogen: bleibt beim Aus- und Einblenden
    h.resizeSection(COL_SIZE, 200)
    v.set_column_visible(COL_SIZE, False)
    v.set_column_visible(COL_SIZE, True)
    assert h.sectionSize(COL_SIZE) == 200
    # Schmaler als der Standard: beim Einblenden wieder lesbar
    h.resizeSection(COL_ARCHIVE_SIZE, 50)
    v.set_column_visible(COL_ARCHIVE_SIZE, False)
    v.set_column_visible(COL_ARCHIVE_SIZE, True)
    assert h.sectionSize(COL_ARCHIVE_SIZE) == _soll(v, COL_ARCHIVE_SIZE)


def _gespeicherte_breiten(home: Path) -> list[int]:
    return [int(w) for w in _einstellungen(home).value("modlist/column_widths")]


@pytest.mark.parametrize("design", ["Nord"], indirect=True)
def test_c3_ausgeblendete_spalte_behaelt_ihre_breite(app, design, neu, home):
    v = neu()
    v.resize(1400, 700)
    v.source_model().set_mods(_zeilen())
    v.show()
    app.processEvents()
    v.restore_column_widths()
    h = v._tree.header()
    v.set_column_visible(COL_ARCHIVE_SIZE, True)
    h.resizeSection(COL_ARCHIVE_SIZE, 200)
    _ruhe(app, v)
    assert _gespeicherte_breiten(home)[COL_ARCHIVE_SIZE] == 200

    # Ausblenden, danach eine andere Spalte ziehen: die eigene Breite bleibt stehen
    v.set_column_visible(COL_ARCHIVE_SIZE, False)
    _ruhe(app, v)
    h.resizeSection(COL_NAME, 320)
    _ruhe(app, v)
    breiten = _gespeicherte_breiten(home)
    assert (breiten[COL_NAME], breiten[COL_ARCHIVE_SIZE]) == (320, 200)

    # Neustart, wieder einblenden: mit der eigenen Breite
    zweite = neu()
    zweite.source_model().set_mods(_zeilen())
    zweite.restore_column_widths()
    assert zweite._tree.isColumnHidden(COL_ARCHIVE_SIZE)
    zweite.set_column_visible(COL_ARCHIVE_SIZE, True)
    assert zweite._tree.header().sectionSize(COL_ARCHIVE_SIZE) == 200


@pytest.mark.parametrize("design", ["Nord"], indirect=True)
def test_c3_bg3_ziehen_ueberschreibt_keine_zusatzspalten(app, design, sprache, neu, home):
    sprache("es")
    s = _einstellungen(home)
    # Groesse selbst auf 180 gezogen; Archivgroesse steht aus einem alten Stand mit 0 da
    s.setValue("modlist/column_widths", [36, 300, 80, 80, 0, 80, 90, 0, 180, 0, 0])
    s.setValue("modlist/column_visible/size", True)
    s.setValue("modlist/column_visible/archive_size", True)
    s.setValue("modlist/column_visible/category", False)
    s.sync()
    del s

    v = neu()
    v.resize(1400, 700)
    v.source_model().set_mods(_zeilen())
    v.show()
    app.processEvents()
    v.restore_column_widths()
    h = v._tree.header()
    assert h.sectionSize(COL_SIZE) == 180
    # Ohne brauchbare gespeicherte Breite gilt die Standardbreite, nicht die Grundbreite
    soll = _soll(v, COL_ARCHIVE_SIZE)
    assert h.sectionSize(COL_ARCHIVE_SIZE) == soll > mod_list._DEFAULT_WIDTHS[COL_ARCHIVE_SIZE]
    _ruhe(app, v)

    # BG3-Instanz: Zusatzspalten aus, die Name-Spalte breiter ziehen
    v.set_view_features_enabled(False)
    h.resizeSection(COL_NAME, 350)
    _ruhe(app, v)
    breiten = _gespeicherte_breiten(home)
    assert breiten[COL_NAME] == 350
    assert breiten[COL_SIZE] == 180

    # Neustart in der normalen Instanz
    zweite = neu()
    zweite.source_model().set_mods(_zeilen())
    zweite.restore_column_widths()
    h2 = zweite._tree.header()
    assert not zweite._tree.isColumnHidden(COL_SIZE)
    assert h2.sectionSize(COL_SIZE) == 180
    assert h2.sectionSize(COL_ARCHIVE_SIZE) == _soll(zweite, COL_ARCHIVE_SIZE) == soll


@pytest.mark.parametrize("design", ["Nord"], indirect=True)
def test_c3_kurze_alte_liste_gibt_der_zusatzspalte_die_standardbreite(app, design, sprache, neu, home):
    sprache("es")
    s = _einstellungen(home)
    s.setValue("modlist/column_widths", [36, 300, 80, 80, 100, 80, 90])
    s.setValue("modlist/column_visible/archive_size", True)
    s.sync()
    del s
    v = neu()
    v.source_model().set_mods(_zeilen())
    v.restore_column_widths()
    h = v._tree.header()
    soll = _soll(v, COL_ARCHIVE_SIZE)
    assert h.sectionSize(COL_ARCHIVE_SIZE) == soll > mod_list._DEFAULT_WIDTHS[COL_ARCHIVE_SIZE]
    # Die gespeicherten Standardspalten bleiben, wie sie sind
    assert [h.sectionSize(c) for c in range(COL_NAME, COL_PRIORITY + 1)] == [300, 80, 80, 100, 80, 90]


# ── Nachsortieren und Versionen ──────────────────────────────────────


def _mitzaehlen(monkeypatch, px):
    zaehler = {"invalidate": 0, "raenge": 0}
    invalidate, raenge = px.invalidate, px._build_ranks

    def gezaehlt_invalidate():
        zaehler["invalidate"] += 1
        invalidate()

    def gezaehlt_raenge():
        zaehler["raenge"] += 1
        return raenge()

    monkeypatch.setattr(px, "invalidate", gezaehlt_invalidate)
    monkeypatch.setattr(px, "_build_ranks", gezaehlt_raenge)
    return zaehler


def test_a3_umschalten_sortiert_nicht_doppelt(ansicht, app, monkeypatch):
    px = ansicht._proxy_model
    _sortiere(ansicht, COL_NAME, ASC)
    vorher = _anzeige(ansicht)
    zaehler = _mitzaehlen(monkeypatch, px)
    src = ansicht.source_model()
    # So meldet das Hauptfenster das Umschalten einer Mod: alle Zellen, ohne Rollen
    src._rows[3].enabled = False
    src.dataChanged.emit(src.index(0, 0), src.index(src.rowCount() - 1, COL_COUNT - 1))
    app.processEvents()
    app.processEvents()
    assert not px._resort_timer.isActive()
    assert zaehler == {"invalidate": 0, "raenge": 1}
    assert _anzeige(ansicht) == vorher


def test_a3_liegengebliebene_zeilen_werden_nachsortiert(ansicht, app, monkeypatch):
    px = ansicht._proxy_model
    _sortiere(ansicht, COL_NAME, ASC)
    zaehler = _mitzaehlen(monkeypatch, px)
    src = ansicht.source_model()
    # Nur der Gruppenkopf aendert sich -- sein Mitglied muss mitwandern
    kopf = QUELLE.index("GKopf")
    src._rows[kopf].name = "Zzz"
    src.dataChanged.emit(src.index(kopf, COL_NAME), src.index(kopf, COL_NAME),
                         [Qt.ItemDataRole.DisplayRole])
    app.processEvents()
    app.processEvents()
    assert _anzeige(ansicht) == ["A", "B", "Sep1", "Alpha", "Mitte", "Zeta", "GKopf",
                                 "GMitglied", "Sep2", "E", "F", "GFern"]
    assert zaehler["invalidate"] == 1


def test_a4_v_vor_der_versionsnummer_zaehlt_nicht(app, neu):
    v = neu()
    versionen = ["2.0", "v1.6.0", "1.5", "V10", "1.10", "", "v0.91b"]
    zeilen = [ModRow(True, "Sep", is_separator=True, folder_name="Sep")]
    zeilen += [ModRow(True, f"m{i}", folder_name=ver or "leer", version=ver)
               for i, ver in enumerate(versionen)]
    v.source_model().set_mods(zeilen)
    _sortiere(v, COL_VERSION, ASC)
    assert _anzeige(v) == ["Sep", "v0.91b", "1.5", "v1.6.0", "1.10", "2.0", "V10", "leer"]
    _sortiere(v, COL_VERSION, DESC)
    assert _anzeige(v) == ["Sep", "V10", "2.0", "1.10", "v1.6.0", "1.5", "v0.91b", "leer"]


# ── Verdrahtung im Hauptfenster ──────────────────────────────────────


def _verbindungen_aus_dem_hauptfenster(*signale: str):
    """Die connect-Zeilen des Konstruktors als eigene Funktion ausfuehrbar machen.

    Nur Anweisungen direkt im Konstruktor zaehlen, nichts aus Zweigen.
    """
    import anvil.mainwindow as mw

    baum = ast.parse(textwrap.dedent(inspect.getsource(mw.MainWindow.__init__)))
    gefunden: dict[str, list[ast.stmt]] = {}
    for anweisung in baum.body[0].body:
        aufruf = getattr(anweisung, "value", None)
        if (isinstance(anweisung, ast.Expr) and isinstance(aufruf, ast.Call)
                and isinstance(aufruf.func, ast.Attribute) and aufruf.func.attr == "connect"):
            signal = ast.unparse(aufruf.func.value)
            if signal in signale:
                gefunden.setdefault(signal, []).append(anweisung)
    assert {s: len(a) for s, a in gefunden.items()} == {s: 1 for s in signale}
    quelle = "def verdrahten(self):\n" + "\n".join(
        textwrap.indent(ast.unparse(gefunden[s][0]), "    ") for s in signale)
    namensraum = dict(vars(mw))
    exec(compile(quelle, mw.__file__, "exec"), namensraum)
    return namensraum["verdrahten"]


def test_a6_hauptfenster_leitet_hinweis_und_archivdaten_weiter(app, neu, tmp_path):
    from anvil.core.translator import tr
    from anvil.widgets.game_panel import GamePanel

    verdrahten = _verbindungen_aus_dem_hauptfenster(
        "self._mod_list_view.reorder_blocked",
        "self._game_panel.downloads_scanned",
    )
    ansicht = neu()
    eintrag = ModEntry(name="mod_a", display_name="Mod A", installation_file="Mein-Archiv.7z")
    ansicht.source_model().set_mods([mod_entry_to_row(eintrag),
                                     ModRow(True, "B", folder_name="B")])
    panel = neu(GamePanel)
    fenster = _FensterVerschieben(ansicht)
    fenster._game_panel = panel
    verdrahten(fenster)

    # Ziehversuch im sortierten Zustand -> Hinweis in der Statusleiste
    _sortiere(ansicht, COL_NAME, ASC)
    ansicht._tree.startDrag(Qt.DropAction.MoveAction)
    assert fenster.leiste.meldungen == [tr("status.modlist_sort_locked")]

    # Downloads-Scan -> Archivspalten der Mod-Liste
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "Mein-Archiv.7z").write_bytes(SIEBEN_Z * 3)
    panel.set_downloads_path(downloads, tmp_path / "mods", tmp_path / "profiles",
                             tmp_path / "overwrite")
    m = ansicht.source_model()
    assert m.data(m.index(0, COL_ARCHIVE_SIZE)) == f"{len(SIEBEN_Z) * 3} B"
    assert m.data(m.index(1, COL_ARCHIVE_SIZE)) == ""


class _Nichts:
    """Nimmt jeden Zugriff und Aufruf an und tut nichts."""

    def __getattr__(self, name):
        return self

    def __call__(self, *args, **kwargs):
        return self


class _FensterInstanz(_Nichts):
    def __init__(self, view, instanzen: Path):
        self._mod_list_view = view
        self.bg3_geladen = []
        self.ui_wiederhergestellt = 0
        self.instance_manager = _Nichts()
        self.instance_manager.load_instance = lambda name: {
            "game_name": "Baldur's Gate 3", "game_short_name": "baldursgate3"}
        self.instance_manager.instances_path = lambda: instanzen
        self.plugin_loader = _Nichts()
        self.plugin_loader.get_game = lambda short_name: None

    def _apply_bg3_instance(self, name, data, plugin, game_path):
        h = self._mod_list_view._tree.header()
        self.bg3_geladen.append((self._mod_list_view._view_features, h.sectionsClickable(),
                                 self._mod_list_view._proxy_model.sortColumn()))

    def _restore_ui_state(self):
        self.ui_wiederhergestellt += 1


def test_a6_bg3_zweig_schaltet_sortieren_vor_dem_laden_aus(app, neu, home, tmp_path):
    from anvil.mainwindow import MainWindow

    s = _einstellungen(home)
    s.setValue("modlist/sort_column", "name")
    s.sync()
    del s
    ansicht = neu()
    ansicht.source_model().set_mods(_zeilen())
    ansicht.restore_column_widths()
    assert ansicht._proxy_model.sortColumn() == COL_NAME

    fenster = _FensterInstanz(ansicht, tmp_path / "instanzen")
    assert MainWindow._apply_instance(fenster, "BG3") is True
    assert fenster.bg3_geladen == [(False, False, -1)]
    assert fenster.ui_wiederhergestellt == 1
    assert _anzeige(ansicht) == QUELLE


def test_c4_nach_bg3_kommen_sortieren_und_spaltenwahl_zurueck(hauptfenster_prozess):
    # Echtes Hauptfenster: BG3 -> normale Instanz und BG3 -> keine Instanz
    ergebnis = hauptfenster_prozess("""
        from pathlib import Path
        from PySide6.QtCore import QPoint, QSettings
        from PySide6.QtGui import QContextMenuEvent
        from PySide6.QtWidgets import QMenu
        import anvil.widgets.mod_list as mod_list
        from anvil.models.mod_list_model import COL_NAME

        class Menue(QMenu):
            def exec(self, *args, **kwargs):  # sonst wartet das Menue auf einen Klick
                return None

        mod_list.QMenu = Menue
        # Nur die Weiche zaehlt -- kein Spiel-Plugin, BG3-Laden selbst nicht noetig
        fenster.plugin_loader.get_game = lambda kurz: None
        fenster._apply_bg3_instance = lambda *args, **kwargs: None
        basis = fenster.instance_manager.instances_path()
        for name, kurz in (("Probe", "probe"), ("BG3", "baldursgate3")):
            ordner = basis / name
            (ordner / ".profiles" / "Default").mkdir(parents=True)
            ini = QSettings(str(ordner / ".anvil.ini"), QSettings.Format.IniFormat)
            ini.beginGroup("General")
            ini.setValue("game_name", name)
            ini.setValue("game_short_name", kurz)
            ini.setValue("selected_profile", "Default")
            ini.endGroup()
            ini.sync()
        s = QSettings(str(Path.home() / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf"),
                      QSettings.Format.IniFormat)
        s.setValue("modlist/sort_column", "name")
        s.sync()

        ansicht = fenster._mod_list_view
        kopf = ansicht._tree.header()

        def zustand():
            ansicht._header_menu = None
            if kopf.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu:
                punkt = QPoint(40, 5)
                app.sendEvent(kopf.viewport(), QContextMenuEvent(
                    QContextMenuEvent.Reason.Mouse, punkt, kopf.viewport().mapToGlobal(punkt)))
            return [ansicht._view_features, kopf.sectionsClickable(), kopf.isSortIndicatorShown(),
                    ansicht._header_menu is not None and bool(ansicht._header_menu.actions()),
                    ansicht._proxy_model.sortColumn() == COL_NAME]

        for weg, ziel in (("normal", "Probe"), ("ohne", "gibt es nicht")):
            ergebnis[weg + "_bg3"] = [fenster._apply_instance("BG3"), *zustand()]
            ergebnis[weg] = [fenster._apply_instance(ziel), *zustand()]
    """)
    aus, an = [False] * 5, [True] * 5
    assert ergebnis["normal_bg3"] == [True, *aus]
    assert ergebnis["normal"] == [True, *an]
    assert ergebnis["ohne_bg3"] == [True, *aus]
    assert ergebnis["ohne"] == [False, *an]
