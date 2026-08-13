"""Die Leiste ist der Griff: festhalten und ziehen.

So war es gedacht und so soll es sich anfuehlen:

* Linke Maustaste auf der Leiste **halten** -- dabei darf sie sich
  **nicht** zuklappen.
* Ziehen macht den Bereich groesser oder kleiner.
* Loslassen **ohne** Bewegung klappt auf oder zu, wie vorher.

Bis dahin klappte schon das Druecken um. Wer festhalten und ziehen
wollte, hatte den Bereich sofort zu.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget

from anvil.widgets.collapsible_bar import _BAR_HEIGHT, CollapsibleSectionBar
from anvil.widgets.mod_list import _SECTION_BAR_HEIGHT, ModListView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _maus(art, global_y):
    return QMouseEvent(
        art, QPointF(10, 5), QPointF(10, global_y),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _ansicht(app, ps_zu=False, fw_zu=False):
    v = ModListView()
    v.resize(1200, 800)
    v.show()
    v.load_presets([
        {"folder": f"P{i}", "name": f"P{i}", "variant": "weiblich",
         "enabled": True} for i in range(7)
    ])
    v.load_frameworks([
        {"name": f"FW{i}", "description": "x", "installed": True,
         "locked": True, "active": True} for i in range(11)
    ])
    v._ps_label._collapsed = ps_zu
    v._ps_label._apply_state()
    v._fw_label._collapsed = fw_zu
    v._fw_label._apply_state()
    app.processEvents()
    return v


def _ziehen(app, leiste, von, bis):
    app.sendEvent(leiste, _maus(QEvent.Type.MouseButtonPress, von))
    app.processEvents()
    schritt = -10 if bis < von else 10
    for y in range(von, bis, schritt):
        app.sendEvent(leiste, _maus(QEvent.Type.MouseMove, y))
        app.processEvents()
    app.sendEvent(leiste, _maus(QEvent.Type.MouseButtonRelease, bis))
    app.processEvents()


# ── Halten klappt nicht ──────────────────────────────────────────────


def test_druecken_allein_klappt_nicht(app) -> None:
    """Der Kern: gedrueckt halten heisst festhalten, nicht klappen."""
    v = _ansicht(app)
    try:
        assert not v._fw_label.collapsed
        app.sendEvent(v._fw_label, _maus(QEvent.Type.MouseButtonPress, 500))
        app.processEvents()
        assert not v._fw_label.collapsed, (
            "die Leiste hat beim Druecken zugeklappt -- Festhalten unmoeglich"
        )
    finally:
        v.deleteLater()


def test_klick_ohne_bewegung_klappt_weiterhin(app) -> None:
    v = _ansicht(app)
    try:
        app.sendEvent(v._fw_label, _maus(QEvent.Type.MouseButtonPress, 500))
        app.sendEvent(v._fw_label, _maus(QEvent.Type.MouseButtonRelease, 500))
        app.processEvents()
        assert v._fw_label.collapsed, "Klick klappt nicht mehr"
    finally:
        v.deleteLater()


def test_ziehen_klappt_nicht(app) -> None:
    v = _ansicht(app)
    try:
        _ziehen(app, v._fw_label, 500, 340)
        assert not v._fw_label.collapsed, (
            "nach dem Ziehen war der Bereich zu -- das Loslassen hat "
            "zusaetzlich geklappt"
        )
    finally:
        v.deleteLater()


# ── Ziehen veraendert die Groesse ────────────────────────────────────


def test_nach_oben_ziehen_macht_groesser(app) -> None:
    v = _ansicht(app)
    try:
        vorher = list(v._splitter.sizes())
        _ziehen(app, v._fw_label, 500, 340)
        nachher = list(v._splitter.sizes())
        assert nachher[2] > vorher[2], (
            f"Frameworks nicht gewachsen: {vorher[2]} -> {nachher[2]}"
        )
    finally:
        v.deleteLater()


def test_nach_unten_ziehen_macht_kleiner(app) -> None:
    v = _ansicht(app)
    try:
        vorher = list(v._splitter.sizes())
        _ziehen(app, v._fw_label, 500, 620)
        assert v._splitter.sizes()[2] < vorher[2]
    finally:
        v.deleteLater()


def test_platz_kommt_aus_der_mod_liste(app) -> None:
    """Nicht vom Nachbarbereich -- sonst schrumpft der beim Aufziehen."""
    v = _ansicht(app)
    try:
        vorher = list(v._splitter.sizes())
        _ziehen(app, v._fw_label, 500, 340)
        nachher = list(v._splitter.sizes())
        assert nachher[1] == vorher[1], (
            f"Presets haben Platz abgegeben: {vorher[1]} -> {nachher[1]}"
        )
        assert nachher[0] < vorher[0], "die Mod-Liste hat nichts abgegeben"
    finally:
        v.deleteLater()


def test_presets_leiste_zieht_ebenso(app) -> None:
    v = _ansicht(app)
    try:
        vorher = list(v._splitter.sizes())
        _ziehen(app, v._ps_label, 400, 250)
        assert v._splitter.sizes()[1] > vorher[1]
    finally:
        v.deleteLater()


def test_zugeklappte_leiste_klappt_beim_ziehen_auf(app) -> None:
    """Wer einen zugeklappten Bereich zieht, will ihn offensichtlich sehen."""
    v = _ansicht(app, fw_zu=True)
    try:
        assert v._fw_label.collapsed
        vorher = list(v._splitter.sizes())
        _ziehen(app, v._fw_label, 700, 500)
        assert not v._fw_label.collapsed
        assert v._splitter.sizes()[2] > vorher[2]
    finally:
        v.deleteLater()


def test_mod_liste_behaelt_einen_rest(app) -> None:
    """Man darf sich die Liste nicht komplett wegziehen."""
    v = _ansicht(app)
    try:
        _ziehen(app, v._fw_label, 700, 20)
        assert v._splitter.sizes()[0] >= 100
    finally:
        v.deleteLater()


# ── Hoehe der Leisten ────────────────────────────────────────────────


def test_bereichsleisten_sind_hoeher(app) -> None:
    v = _ansicht(app)
    try:
        for name, leiste in (("Presets", v._ps_label),
                             ("Frameworks", v._fw_label)):
            assert leiste.height() >= _SECTION_BAR_HEIGHT, (
                f"{name}: nur {leiste.height()}px"
            )
        assert _SECTION_BAR_HEIGHT > 28, "das war der alte Wert"
    finally:
        v.deleteLater()


def test_andere_leisten_bleiben_wie_sie_waren(app) -> None:
    """Log-Leiste und BG3 wurden nicht mitverändert."""
    leiste = CollapsibleSectionBar("Test", "test_bar", QWidget(), style="")
    try:
        assert leiste.minimumHeight() == _BAR_HEIGHT
        assert _BAR_HEIGHT == 28
    finally:
        leiste.deleteLater()


def test_leistenhoehe_bleibt_beim_klappen_gleich(app) -> None:
    """Zugeklappt war der Bereich 28 hoch, die Leiste aber 30 -- sie sprang."""
    v = _ansicht(app)
    try:
        leiste = v._fw_label
        leiste._collapsed = False
        leiste._apply_state()
        app.processEvents()
        auf = leiste.height()

        leiste._collapsed = True
        leiste._apply_state()
        app.processEvents()
        zu = v._fw_container.maximumHeight()

        assert zu == auf, f"Leiste springt beim Klappen: auf={auf}, zu={zu}"
    finally:
        v.deleteLater()
