"""Eine Log-Meldung darf die Anwendung nicht umbringen.

`add_log("warn", ...)` hat frueher einen `KeyError` ausgeloest -- die
Stufe heisst "warning". Der Aufruf steckte in der Meldung ueber von Hand
kopierte Mods, also mitten im Aufbau des Hauptfensters: Anvil startete
nicht mehr, sobald es eine fremde Datei im Spielordner fand.
"""

import re
from pathlib import Path

from anvil.widgets.log_panel import LEVEL_CONFIG, normalize_level

QUELLE = Path(__file__).resolve().parents[1] / "anvil"


def test_warn_wird_zu_warning():
    assert normalize_level("warn") == "warning"


def test_bekannte_stufen_bleiben():
    for stufe in LEVEL_CONFIG:
        assert normalize_level(stufe) == stufe


def test_unbekannte_stufe_faellt_nicht_um():
    assert normalize_level("gibtsnicht") in LEVEL_CONFIG


def test_jede_gemeldete_stufe_ist_darstellbar():
    """Was normalize_level liefert, muss LEVEL_CONFIG auch kennen."""
    for stufe in ("warn", "err", "critical", "", "WARNING"):
        assert normalize_level(stufe) in LEVEL_CONFIG


def test_jeder_add_log_aufruf_nennt_eine_echte_stufe():
    """Die falsche Schreibweise soll nicht zurueckkommen.

    ``warn`` ist anderswo ein Themenfarben-Name -- gesucht wird deshalb
    nur die Stufe im Aufruf selbst, auch ueber Zeilenumbruch hinweg.
    """
    muster = re.compile(r"add_log\(\s*[\"'](\w+)[\"']")
    treffer = [
        f"{pfad.relative_to(QUELLE)}: {stufe}"
        for pfad in QUELLE.rglob("*.py")
        for stufe in muster.findall(pfad.read_text(encoding="utf-8"))
        if stufe not in LEVEL_CONFIG
    ]
    assert not treffer, f"unbekannte Log-Stufe im Aufruf: {treffer}"
