"""Ein entsperrtes Framework muss sich bearbeiten lassen.

Das Schloss hat einen Zweck: solange es zu ist, darf niemand die Mod
verschieben, umbenennen oder loeschen. Ist es offen, ist das Framework
eine gewoehnliche Mod -- genau dafuer laesst es sich oeffnen.

Vorher waren Frameworks dauerhaft aus der Mod-Liste gefiltert. Damit gab
es fuer sie ueberhaupt keinen Weg zu diesen Funktionen, offen oder nicht.
"""

import re
from pathlib import Path

QUELLE = Path("anvil/mainwindow.py").read_text(encoding="utf-8")


def test_frameworks_sind_nicht_mehr_pauschal_ausgeblendet() -> None:
    # Der alte Filter warf jede Direktinstall-Mod raus, ohne das Schloss
    # auch nur anzusehen.
    assert "if not e.is_direct_install]" not in QUELLE, (
        "irgendwo filtert noch der alte pauschale Ausschluss"
    )


def test_beide_ladepfade_beruecksichtigen_das_schloss() -> None:
    treffer = re.findall(
        r"if not e\.is_direct_install or e\.name in offen", QUELLE,
    )
    assert len(treffer) == 2, f"{len(treffer)} von 2 Ladepfaden angepasst"


def test_im_zweifel_bleibt_ein_framework_verborgen() -> None:
    # Aufgezaehlt wird, was sichtbar sein DARF. Faellt die Zuordnung aus,
    # ist die Menge leer und es bleibt alles verborgen -- nicht umgekehrt.
    start = QUELLE.index("def _unlocked_framework_mods")
    ende = QUELLE.index("def _framework_for_mod")
    block = QUELLE[start:ende]

    # Aufgezaehlt wird, was offen ist -- nicht, was gesperrt ist.
    assert "offen: set[str] = set()" in block
    assert "offen.add(ordner)" in block
    # Ohne Instanz gibt es nichts zu zeigen.
    assert "return set()" in block


def test_loeschen_entfernt_auch_den_framework_eintrag() -> None:
    # Sonst meldet Anvil das Framework weiter als installiert, obwohl der
    # Ordner weg ist -- die Mod war "geloescht" und doch noch da.
    start = QUELLE.index("fw_zuordnung = self._framework_mod_folders()")
    block = QUELLE[start:start + 1400]

    assert "framework_state.remove(" in block
    assert "remove_mod_globally(profiles_dir, name)" in block
    assert "shutil.rmtree(mod_path)" in block
    # Die Zuordnung muss VOR der Schleife stehen: nach dem ersten rmtree
    # liest sie Dateilisten, die es nicht mehr gibt.
    assert block.index("fw_zuordnung = ") < block.index("for name in names:")


def test_haken_schaltet_auch_den_framework_zustand() -> None:
    # Frameworks werden unabhaengig von active_mods ausgerollt. Ohne
    # Abgleich waere der Haken in der Liste wirkungslos.
    assert "_sync_framework_active(row_data.folder_name, enabled)" in QUELLE

    start = QUELLE.index("def _sync_framework_active")
    block = QUELLE[start:start + 600]
    assert "framework_state.set_entry(" in block
    assert "active=enabled" in block


def test_framework_ohne_eintrag_gilt_als_gesperrt() -> None:
    # get() liefert fuer einen fehlenden Eintrag locked=False, und
    # lock_all() fasst nur vorhandene Eintraege an. ArchiveXL, TweakXL und
    # CET haben gar keinen -- die waeren sonst von sich aus offen und
    # damit loesch- und umbenennbar, ohne dass jemand das Schloss oeffnet.
    start = QUELLE.index("def _unlocked_framework_mods")
    ende = QUELLE.index("def _framework_for_mod")
    block = QUELLE[start:ende]

    assert "isinstance(eintrag, dict)" in block, (
        "fehlender Eintrag wird nicht als gesperrt behandelt"
    )
    assert "framework_state.load(" in block, (
        "Zustand sollte einmal geladen werden, nicht pro Framework"
    )
