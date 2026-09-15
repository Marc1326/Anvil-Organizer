"""Die Texte fuers Sortieren stehen in allen Sprachen (#111)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from anvil.core.translator import Translator

LOCALES = Path(__file__).resolve().parents[1] / "anvil" / "locales"
SPRACHEN = ("de", "en", "es", "fr", "it", "pt", "ru")
SCHLUESSEL = (
    "label.header_installed_at",
    "label.header_mod_size",
    "label.header_download_date",
    "label.header_archive_size",
    "label.sort_by_priority",
    "status.modlist_sort_locked",
    "status.plugins_sort_locked",
)


def _wert(daten: dict, schluessel: str):
    for teil in schluessel.split("."):
        if not isinstance(daten, dict):
            return None
        daten = daten.get(teil)
    return daten


@pytest.mark.parametrize("sprache", SPRACHEN)
def test_l1_schluessel_in_jeder_sprache(sprache):
    daten = json.loads((LOCALES / f"{sprache}.json").read_text(encoding="utf-8"))
    uebersetzer = Translator()
    uebersetzer._locales_dir = LOCALES
    uebersetzer.load(sprache)
    for schluessel in SCHLUESSEL:
        wert = _wert(daten, schluessel)
        assert isinstance(wert, str) and wert.strip(), f"{sprache}: {schluessel} fehlt"
        assert uebersetzer.t(schluessel) == wert
        assert uebersetzer.t(schluessel) != schluessel
