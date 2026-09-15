"""Sortierpfeil im modernen Design neben dem Spaltentitel (#111).

Modern haben die Spaltenköpfe keine Trennlinien. Am Spaltenrand las sich der
Pfeil als Pfeil der Nachbarspalte. Klassische Themes und Dialoge behalten
den Pfeil am Rand.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QFontMetrics, QImage
from PySide6.QtWidgets import (
    QApplication, QDialog, QHeaderView, QTableWidget, QTreeWidget, QVBoxLayout,
)

import anvil.styles.dark_theme as dark_theme
from anvil.models.mod_list_model import COL_VERSION, ModRow
from anvil.styles.header_arrow_style import (
    HeaderArrowStyle, apply_header_arrow_style, header_title_font, title_arrow_width,
)

DESC = Qt.SortOrder.DescendingOrder
MODERN = ("Anvil Dunkel", "Anvil Hell")
LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
MITTE = Qt.AlignmentFlag.AlignCenter
RECHTS = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(dark_theme, "_current_palette", {})
    return tmp_path


@pytest.fixture
def theme(request, app, home):
    vorher = app.styleSheet()
    dark_theme.apply_theme(app, request.param)
    yield request.param
    app.setStyleSheet(vorher)


@pytest.fixture
def widgets(app, home):
    """Merkt gebaute Widgets und raeumt sie weg, solange HOME noch umgebogen ist."""
    erzeugt = []

    def merken(widget):
        erzeugt.append(widget)
        return widget

    yield merken
    for widget in erzeugt:
        if hasattr(widget, "flush_column_widths"):
            widget.flush_column_widths()
        widget.close()
        widget.deleteLater()
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _bild(header: QHeaderView) -> tuple[bytes, int, int, int]:
    QApplication.processEvents()
    bild = header.viewport().grab().toImage().convertToFormat(QImage.Format.Format_RGB32)
    return bytes(bild.constBits()), bild.bytesPerLine(), bild.width(), bild.height()


def _punkt(bild, x: int, y: int) -> bytes:
    daten, zeile = bild[0], bild[1]
    return daten[y * zeile + 4 * x:y * zeile + 4 * x + 4]


def _unterschied(a, b, x0: int, x1: int) -> list[int]:
    """Pixelspalten im Bereich, in denen sich zwei Kopfbilder unterscheiden."""
    assert a[1:] == b[1:], "der Kopf hat zwischen den Bildern die Groesse geaendert"
    return [x for x in range(x0, x1)
            if any(_punkt(a, x, y) != _punkt(b, x, y) for y in range(a[3]))]


def _tinte(bild, x0: int, x1: int) -> list[int]:
    """Pixelspalten mit Schrift; der Hintergrund steht links im Innenabstand."""
    grund = _punkt(bild, x0 + 2, bild[3] // 2)
    return [x for x in range(x0, x1)
            if any(_punkt(bild, x, y) != grund for y in range(2, bild[3] - 3))]


def _titel_und_pfeil(header: QHeaderView, col: int) -> tuple[list[int], list[int]]:
    """Pixelspalten (relativ zur Spalte) von Titel und Pfeil, sortiert nach col.

    Der Titel bleibt stehen -- modern wandert der Pfeil mit ihm.
    """
    header.setSortIndicator(col, DESC)
    x, breite = header.sectionViewportPosition(col), header.sectionSize(col)
    header.setSortIndicatorShown(False)
    ohne = _bild(header)
    header.setSortIndicatorShown(True)
    mit = _bild(header)
    return ([px - x for px in _tinte(ohne, x, x + breite - 1)],
            [px - x for px in _unterschied(mit, ohne, x, x + breite)])


def _tabelle(widgets, titel, ausrichtungen, breite) -> QTableWidget:
    tabelle = widgets(QTableWidget(1, len(titel)))
    # nicht unter den Mauszeiger (10, 10): der Hover faerbt den Titel um
    tabelle.setGeometry(100, 100, 900, 120)
    tabelle.setHorizontalHeaderLabels(titel)
    header = tabelle.horizontalHeader()
    header.setStretchLastSection(False)
    for col, ausrichtung in enumerate(ausrichtungen):
        tabelle.horizontalHeaderItem(col).setTextAlignment(ausrichtung)
        header.resizeSection(col, breite)
    header.setSortIndicatorShown(True)
    tabelle.show()
    apply_header_arrow_style((header,))
    return tabelle


@pytest.mark.parametrize("theme", MODERN, indirect=True)
def test_pfeil_steht_neben_dem_titel_je_ausrichtung(app, theme, widgets):
    titel = ["LINKS", "MITTE", "RECHTS"]
    ausrichtungen = (LINKS, MITTE, RECHTS)
    tabelle = _tabelle(widgets, titel, ausrichtungen, 240)
    header = tabelle.horizontalHeader()
    for col, ausrichtung in enumerate(ausrichtungen):
        text, pfeil = _titel_und_pfeil(header, col)
        assert text and pfeil, col
        if ausrichtung is RECHTS:
            # rechtsbuendig haette der Pfeil hinter dem Titel keinen Platz: davor
            luft = min(text) - max(pfeil) - 1
        else:
            luft = min(pfeil) - max(text) - 1
        assert 2 <= luft <= 8, (col, luft)
        if ausrichtung is MITTE:
            # der Titel selbst bleibt mittig
            assert abs((min(text) + max(text)) / 2 - (240 - 1) / 2) <= 2, text

    # Kleinste berechnete Breite: Titel ganz, nichts ueberlappt, Luft zum Rand
    fm = QFontMetrics(header_title_font(header))
    for col, ausrichtung in enumerate(ausrichtungen):
        voll, _ = _titel_und_pfeil(header, col)
        breite = title_arrow_width(fm.horizontalAdvance(titel[col]), ausrichtung)
        header.resizeSection(col, breite)
        text, pfeil = _titel_und_pfeil(header, col)
        wo = (col, breite)
        assert max(text) - min(text) == max(voll) - min(voll), wo
        if ausrichtung is RECHTS:
            assert min(pfeil) >= 2 and max(pfeil) + 2 < min(text), wo
        else:
            assert max(text) + 2 < min(pfeil) and max(pfeil) <= breite - 1 - 9, wo


@pytest.mark.parametrize("theme", MODERN, indirect=True)
def test_dialoge_und_zu_schmale_spalten_behalten_die_alte_stelle(app, theme, widgets):
    titel = ["Fecha de modificación", "Kurz"]

    def baum(elter=None) -> QTreeWidget:
        tree = QTreeWidget(elter)
        tree.setColumnCount(2)
        tree.setHeaderLabels(titel)
        header = tree.header()
        header.setStretchLastSection(False)
        header.resizeSection(0, 110)
        header.resizeSection(1, 200)
        header.setSortIndicatorShown(True)
        return tree

    dialog = widgets(QDialog())
    im_dialog = baum(dialog)
    QVBoxLayout(dialog).addWidget(im_dialog)
    dialog.setGeometry(100, 100, 400, 120)
    dialog.show()
    frei = widgets(baum())
    frei.setGeometry(100, 300, 400, 120)
    frei.show()
    apply_header_arrow_style((frei.header(),))
    assert frei.header().testAttribute(Qt.WidgetAttribute.WA_SetStyle)

    # Zu schmal fuer Titel und Pfeil: der Pfeil rueckt genau an die alte Stelle
    _, pfeil_dialog = _titel_und_pfeil(im_dialog.header(), 0)
    _, pfeil_frei = _titel_und_pfeil(frei.header(), 0)
    assert pfeil_frei == pfeil_dialog
    # Breit genug: im Dialog weiter am Rand, sonst direkt hinter dem Titel
    text, pfeil = _titel_und_pfeil(im_dialog.header(), 1)
    assert 200 - 1 - max(pfeil) <= 3 and min(pfeil) - max(text) > 100
    text, pfeil = _titel_und_pfeil(frei.header(), 1)
    assert 2 <= min(pfeil) - max(text) - 1 <= 8


def _kopfbilder(app, panel, koepfe) -> list[bytes]:
    bilder = []
    for tab, header in koepfe:
        if tab is not None:
            panel._tabs.setCurrentIndex(tab)
        header.setSortIndicator(1, DESC)
        bilder.append(_bild(header)[0])
    return bilder


def test_live_wechsel_haengt_den_stil_an_und_ab(app, home, widgets):
    from anvil.widgets.game_panel import GamePanel
    from anvil.widgets.mod_list import ModListView

    vorher = app.styleSheet()
    try:
        dark_theme.apply_theme(app, "Nord")
        ansicht = widgets(ModListView())
        ansicht.setGeometry(100, 100, 1200, 300)
        ansicht.source_model().set_mods([ModRow(True, "Alpha", folder_name="a", version="1.0")])
        ansicht.show()
        panel = widgets(GamePanel())
        panel.setGeometry(100, 100, 1000, 600)
        panel.apply_theme_metrics()
        panel._tabs.setTabVisible(0, True)
        panel.show()
        app.processEvents()
        ansicht.restore_column_widths()
        koepfe = [(None, ansicht._tree.header()), *enumerate(panel._sort_headers())]
        assert not any(h.testAttribute(Qt.WidgetAttribute.WA_SetStyle) for _, h in koepfe)
        breiten = [[h.sectionSize(c) for c in range(h.count())] for _, h in koepfe]
        klassisch = _kopfbilder(app, panel, koepfe)

        for runde, modern in enumerate(MODERN):
            dark_theme.apply_theme(app, modern)
            ansicht.apply_theme_metrics()
            panel.apply_theme_metrics()
            for _, h in koepfe:
                assert h.testAttribute(Qt.WidgetAttribute.WA_SetStyle)
                # genau ein Stil, als Kind des Kopfes: er darf ihn nicht ueberleben
                stile = h.findChildren(HeaderArrowStyle)
                assert len(stile) == 1 and stile[0].parent() is h
            text, pfeil = _titel_und_pfeil(ansicht._tree.header(), COL_VERSION)
            assert 2 <= min(pfeil) - max(text) - 1 <= 8, runde

            dark_theme.apply_theme(app, "Nord")
            ansicht.apply_theme_metrics()
            panel.apply_theme_metrics()
            assert not any(h.testAttribute(Qt.WidgetAttribute.WA_SetStyle) for _, h in koepfe)
            # mit den Breiten von vorher muss jeder Kopf pixelgleich sein
            for (_, h), liste in zip(koepfe, breiten):
                for c, breite in enumerate(liste):
                    h.resizeSection(c, breite)
            assert _kopfbilder(app, panel, koepfe) == klassisch, runde
    finally:
        app.setStyleSheet(vorher)


@pytest.mark.parametrize("theme", MODERN, indirect=True)
def test_koepfe_haben_den_stil_schon_beim_start(app, theme, widgets):
    from anvil.widgets.game_panel import GamePanel
    from anvil.widgets.mod_list import ModListView

    # ohne Theme-Wechsel und ohne geladene Instanz
    koepfe = [widgets(ModListView())._tree.header(), *widgets(GamePanel())._sort_headers()]
    for header in koepfe:
        assert header.testAttribute(Qt.WidgetAttribute.WA_SetStyle)
        assert len(header.findChildren(HeaderArrowStyle)) == 1


def test_ohne_modernes_design_bleibt_der_kopf_unberuehrt(app, home, widgets):
    tree = widgets(QTreeWidget())
    tree.setColumnCount(2)
    tree.show()
    apply_header_arrow_style((tree.header(),))
    assert not tree.header().testAttribute(Qt.WidgetAttribute.WA_SetStyle)
    assert tree.header().findChildren(HeaderArrowStyle) == []
