"""Textdateien in Unterordnern sind Spielinhalt und koennen kollidieren.

Der Konfliktscanner warf jede ``.txt`` weg, egal wo sie lag. Uebersetzungen
wie ``Interface/Translations/MCM_en.txt`` werden aber ausgerollt -- zwei Mods,
die dieselbe mitbringen, ueberschreiben sich, und Anvil schwieg dazu.

Readmes und Aenderungslisten bleiben still: die Spiel-Plugins fangen sie
ueber ihre Ignoriermuster ab, im Mod-Wurzelverzeichnis zusaetzlich die
Deploy-Regeln.
"""

from pathlib import Path

from anvil.core.conflict_scanner import ConflictScanner
from anvil.plugins.games.game_fallout4 import Fallout4Game

UEBERSETZUNG = "Interface/Translations/MCM_en.txt"


def _mods(tmp_path: Path, dateien: list[str]) -> list[dict]:
    eintraege = []
    for name in ("Erste", "Zweite"):
        for rel in dateien:
            ziel = tmp_path / name / rel
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_bytes(b"x")
        eintraege.append({"name": name, "path": str(tmp_path / name)})
    return eintraege


def test_uebersetzung_ist_ein_konflikt(tmp_path: Path) -> None:
    ergebnis = ConflictScanner().scan_conflicts(
        _mods(tmp_path, [UEBERSETZUNG]), game_plugin=Fallout4Game())

    gemeldet = [k["file"] for k in ergebnis["conflicts"]]
    assert gemeldet == [UEBERSETZUNG], gemeldet
    assert ergebnis["conflicts"][0]["winner"] == "Zweite"


def test_readme_bleibt_still(tmp_path: Path) -> None:
    """Gegenprobe -- sonst waere die Liste voller Dokumentation."""
    ergebnis = ConflictScanner().scan_conflicts(
        _mods(tmp_path, ["liesmich.txt", "docs/readme.txt", "changelog.txt"]),
        game_plugin=Fallout4Game())

    assert [k["file"] for k in ergebnis["conflicts"]] == []
