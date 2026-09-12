"""Lange Optionsbeschreibungen muessen rollbar sein.

Manche Installer schreiben mehrere Absaetze in die Beschreibung einer
Option. Das Textfeld stand ohne eigenen Rollbereich im Layout -- der Text
lief unten aus dem Fenster und der Rest war nicht mehr erreichbar.
"""

from pathlib import Path

from PySide6.QtWidgets import QApplication, QScrollArea

from anvil.core.fomod_parser import (
    FomodConfig,
    FomodGroup,
    FomodPlugin,
    FomodStep,
)
from anvil.dialogs.fomod_dialog import FomodDialog

LANG = "\n\n".join(
    f"Absatz {i}: " + "Sehr langer Beschreibungstext. " * 12
    for i in range(1, 16)
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _dialog(tmp_path: Path, beschreibung: str) -> FomodDialog:
    plugin = FomodPlugin(
        name="AVX2",
        description=beschreibung,
        image_path=None,
        files=[],
        condition_flags=[],
        type_name="Optional",
    )
    config = FomodConfig(
        module_name="Testmod",
        module_image=None,
        required_files=[],
        install_steps=[
            FomodStep(
                name="AVX",
                groups=[
                    FomodGroup(
                        name="AVX",
                        group_type="SelectExactlyOne",
                        plugins=[plugin],
                    )
                ],
            )
        ],
        conditional_installs=[],
    )
    return FomodDialog(config, tmp_path)


def test_beschreibung_steckt_in_einem_rollbereich(tmp_path: Path) -> None:
    _app()
    dlg = _dialog(tmp_path, LANG)
    try:
        bereich = dlg._preview_desc.parentWidget()
        while bereich is not None and not isinstance(bereich, QScrollArea):
            bereich = bereich.parentWidget()
        assert isinstance(bereich, QScrollArea), (
            "Das Beschreibungsfeld haengt in keinem Rollbereich"
        )
    finally:
        dlg.deleteLater()


def test_langer_text_wird_nicht_abgeschnitten(tmp_path: Path) -> None:
    """Der Text muss vollstaendig da sein und der Balken benutzbar."""
    _app()
    dlg = _dialog(tmp_path, LANG)
    try:
        dlg.show()
        _app().processEvents()

        assert dlg._preview_desc.text() == LANG

        balken = dlg._preview_desc_scroll.verticalScrollBar()
        assert balken.maximum() > 0, (
            "Der Rollbalken laesst sich nicht bewegen -- Text waere abgeschnitten"
        )
        # Der gesamte Text passt in das Textfeld, nur das Fenster ist kleiner.
        sichtbar = dlg._preview_desc_scroll.viewport().height()
        assert dlg._preview_desc.height() > sichtbar
    finally:
        dlg.close()
        dlg.deleteLater()


def test_wechsel_rollt_wieder_nach_oben(tmp_path: Path) -> None:
    _app()
    dlg = _dialog(tmp_path, LANG)
    try:
        dlg.show()
        _app().processEvents()

        balken = dlg._preview_desc_scroll.verticalScrollBar()
        balken.setValue(balken.maximum())
        assert balken.value() > 0

        # Zweiter LANGER Text: bei kurzem Text faellt maximum() auf 0 und
        # Qt setzt value() von allein zurueck -- der Test wuerde dann auch
        # ohne den Reset bestehen.
        dlg._set_preview_desc(LANG.replace("Absatz", "Kapitel"))
        _app().processEvents()
        assert balken.maximum() > 0, "Der zweite Text muss auch rollbar sein"
        assert balken.value() == 0
    finally:
        dlg.close()
        dlg.deleteLater()
