"""Die Instanz-Konfiguration muss die neuen Schluessel wirklich behalten.

``save_instance()`` fuehrt eine Weissliste. Ein Schluessel, der dort
fehlt, wird beim Speichern still verworfen -- im Speicher sieht alles
richtig aus, auf der Platte kommt nichts an. Genau daran war der
Auffang-Trenner wirkungslos: ``_catch_all_separator()`` lieferte immer
leer, und das "schon gefragt"-Kennzeichen des Aufraeum-Dialogs
ueberlebte keinen Neustart.
"""

from __future__ import annotations

from pathlib import Path

from anvil.core.instance_manager import InstanceManager

NEUE_SCHLUESSEL = {
    "catchall_separator": "Nicht einsortiert_separator",
    "catchall_tidy_asked": "true",
}


def _instanz(tmp_path: Path, name: str = "Testspiel") -> InstanceManager:
    ordner = tmp_path / name
    ordner.mkdir(parents=True)
    (ordner / ".anvil.ini").write_text(
        "[General]\ngame_name=Testspiel\nselected_profile=Default\n",
        encoding="utf-8",
    )
    return InstanceManager(tmp_path)


def test_neue_schluessel_ueberleben_das_speichern(tmp_path: Path) -> None:
    m = _instanz(tmp_path)
    daten = m.load_instance("Testspiel") or {}
    daten.update(NEUE_SCHLUESSEL)
    m.save_instance("Testspiel", daten)

    frisch = InstanceManager(tmp_path).load_instance("Testspiel") or {}
    for schluessel, wert in NEUE_SCHLUESSEL.items():
        assert frisch.get(schluessel) == wert, (
            f"{schluessel} faellt beim Speichern unter den Tisch -- "
            f"save_instance() fuehrt eine Weissliste"
        )


def test_preset_trenner_bleibt_ebenfalls(tmp_path: Path) -> None:
    """Gegenprobe: der bestehende Schluessel funktioniert weiter."""
    m = _instanz(tmp_path)
    daten = m.load_instance("Testspiel") or {}
    daten["preset_separator"] = "Presets_separator"
    m.save_instance("Testspiel", daten)

    frisch = InstanceManager(tmp_path).load_instance("Testspiel") or {}
    assert frisch.get("preset_separator") == "Presets_separator"


def test_umbenennen_wird_gemerkt(tmp_path: Path) -> None:
    """Nach dem Umbenennen darf kein zweiter Trenner entstehen."""
    m = _instanz(tmp_path)
    daten = m.load_instance("Testspiel") or {}
    daten["catchall_separator"] = "Alt_separator"
    m.save_instance("Testspiel", daten)

    daten = m.load_instance("Testspiel") or {}
    daten["catchall_separator"] = "Neu_separator"
    m.save_instance("Testspiel", daten)

    frisch = InstanceManager(tmp_path).load_instance("Testspiel") or {}
    assert frisch.get("catchall_separator") == "Neu_separator"
