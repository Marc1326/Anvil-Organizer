"""Konflikte INNERHALB gepackter Archive.

Anvil verglich bisher nur lose Dateien. Zwei Archive mit verschiedenen
Namen ergaben nie einen Konflikt -- auch wenn beide dieselbe Spieldatei
mitbrachten und im Spiel eines das andere ueberschrieb.

Der Ausloeser: ``FemV - RE9 Grace`` und ``Unique Eyes - Core`` teilen
sich genau eine Datei. In Anvil war davon nichts zu sehen.
"""

from __future__ import annotations

import json
from pathlib import Path

from anvil.core.conflict_scanner import ConflictScanner
from anvil.core.modindex import ModIndex
from anvil.plugins.base_game import BaseGame
from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game


def _mods(*namen):
    """Erster Name = niedrigste Prioritaet, letzter gewinnt."""
    return [{"name": n, "path": ""} for n in namen]


# ── Der Scanner ──────────────────────────────────────────────────────


def test_ohne_archivdaten_bleibt_alles_beim_alten() -> None:
    erg = ConflictScanner().scan_conflicts(_mods("A", "B"))
    assert erg["archive_conflicts"] == []


def test_gemeinsame_datei_wird_zum_konflikt() -> None:
    erg = ConflictScanner().scan_conflicts(
        _mods("Unique Eyes - Core", "FemV - RE9 Grace"),
        archive_hashes={
            "Unique Eyes - Core": {"archive/pc/mod/eyes.archive": frozenset({1, 2, 3})},
            "FemV - RE9 Grace": {"archive/pc/mod/grace.archive": frozenset({3, 9})},
        },
    )
    treffer = erg["archive_conflicts"]
    assert len(treffer) == 1
    e = treffer[0]
    assert e["count"] == 1
    assert {e["mod_a"], e["mod_b"]} == {"Unique Eyes - Core", "FemV - RE9 Grace"}
    assert e["winner"] == "FemV - RE9 Grace", "der spaetere Eintrag gewinnt"


def test_ohne_ueberschneidung_kein_konflikt() -> None:
    erg = ConflictScanner().scan_conflicts(
        _mods("A", "B"),
        archive_hashes={
            "A": {"a.archive": frozenset({1, 2})},
            "B": {"b.archive": frozenset({3, 4})},
        },
    )
    assert erg["archive_conflicts"] == []


def test_zwei_archive_derselben_mod_streiten_nicht() -> None:
    erg = ConflictScanner().scan_conflicts(
        _mods("A"),
        archive_hashes={
            "A": {
                "eins.archive": frozenset({1, 2}),
                "zwei.archive": frozenset({2, 3}),
            },
        },
    )
    assert erg["archive_conflicts"] == []


def test_groesster_konflikt_steht_oben() -> None:
    erg = ConflictScanner().scan_conflicts(
        _mods("A", "B", "C"),
        archive_hashes={
            "A": {"a.archive": frozenset({1, 2, 3, 4})},
            "B": {"b.archive": frozenset({1})},
            "C": {"c.archive": frozenset({1, 2, 3})},
        },
    )
    zaehler = [e["count"] for e in erg["archive_conflicts"]]
    assert zaehler == sorted(zaehler, reverse=True)
    assert zaehler[0] == 3


def test_reihenfolge_entscheidet_den_gewinner() -> None:
    """Dreht man die Liste, dreht sich der Gewinner mit."""
    hashes = {
        "A": {"a.archive": frozenset({7})},
        "B": {"b.archive": frozenset({7})},
    }
    vorne = ConflictScanner().scan_conflicts(_mods("A", "B"), archive_hashes=hashes)
    hinten = ConflictScanner().scan_conflicts(_mods("B", "A"), archive_hashes=hashes)
    assert vorne["archive_conflicts"][0]["winner"] == "B"
    assert hinten["archive_conflicts"][0]["winner"] == "A"


def test_ohne_pfad_wird_nichts_von_der_platte_gelesen() -> None:
    """Path("") ist das Arbeitsverzeichnis, nicht "kein Ordner".

    Ohne diese Bremse las der Scanner bei einem leeren Pfad den ganzen
    aktuellen Ordner ein -- in einem Test also das halbe Repo.
    """
    erg = ConflictScanner().scan_conflicts([{"name": "A", "path": ""}])
    assert erg["file_owners"] == {}


def test_lose_dateien_bleiben_getrennt() -> None:
    """Pruefsummen duerfen nicht als Dateipfade auftauchen.

    ``file_owners`` fliesst unveraendert in den Data-Tab -- dort waeren
    Pruefsummen sinnlos.
    """
    erg = ConflictScanner().scan_conflicts(
        _mods("A", "B"),
        archive_hashes={
            "A": {"a.archive": frozenset({1})},
            "B": {"b.archive": frozenset({1})},
        },
    )
    assert erg["file_owners"] == {}
    assert erg["conflicts"] == []
    assert len(erg["archive_conflicts"]) == 1


# ── Der Plugin-Haken ─────────────────────────────────────────────────


def test_basisspiel_liest_keine_archive() -> None:
    assert BaseGame.GameArchiveSuffixes == []
    assert BaseGame().read_archive_hashes(Path("egal.archive")) is None


def test_cyberpunk_kennt_die_endung() -> None:
    assert Cyberpunk2077Game.GameArchiveSuffixes == [".archive"]


def test_kaputtes_archiv_wirft_nicht(tmp_path: Path) -> None:
    """Ein einziges beschaedigtes Archiv darf nichts abbrechen."""
    p = tmp_path / "kaputt.archive"
    p.write_bytes(b"NICHTRDAR" + b"\x00" * 50)
    assert Cyberpunk2077Game().read_archive_hashes(p) is None


def test_fehlende_datei_wirft_nicht(tmp_path: Path) -> None:
    assert Cyberpunk2077Game().read_archive_hashes(tmp_path / "weg.archive") is None


def test_echtes_archiv_wird_gelesen(tmp_path: Path) -> None:
    """Der Positivpfad -- vorher war nur geprueft, dass es NICHT wirft."""
    from tests.test_redengine_archive import _archiv

    p = _archiv(tmp_path / "gut.archive", [11, 22, 33])
    assert Cyberpunk2077Game().read_archive_hashes(p) == frozenset({11, 22, 33})


# ── Der Mod-Index ────────────────────────────────────────────────────


class _SpielMitArchiven:
    GameArchiveSuffixes = [".archive"]

    def __init__(self, tabelle):
        self._tabelle = tabelle
        self.gelesen = []

    def read_archive_hashes(self, path):
        self.gelesen.append(path.name)
        return self._tabelle.get(path.name)


def _index(tmp_path: Path, plugin=None) -> ModIndex:
    return ModIndex(tmp_path, mods_path=tmp_path / ".mods", game_plugin=plugin)


def test_index_merkt_sich_die_pruefsummen(tmp_path: Path) -> None:
    mod = tmp_path / ".mods" / "A"
    mod.mkdir(parents=True)
    (mod / "eins.archive").write_bytes(b"x")

    plugin = _SpielMitArchiven({"eins.archive": frozenset({4, 8, 15})})
    idx = _index(tmp_path, plugin)
    idx.rebuild()

    assert idx.get_archives("A") == {"eins.archive": frozenset({4, 8, 15})}


def test_ohne_plugin_wird_nichts_gelesen(tmp_path: Path) -> None:
    mod = tmp_path / ".mods" / "A"
    mod.mkdir(parents=True)
    (mod / "eins.archive").write_bytes(b"x")

    idx = _index(tmp_path)
    idx.rebuild()

    assert idx.get_archives("A") == {}


def test_unlesbares_archiv_faellt_still_weg(tmp_path: Path) -> None:
    """Die Mod bleibt vollstaendig im Index -- nur ohne Pruefsummen."""
    mod = tmp_path / ".mods" / "A"
    mod.mkdir(parents=True)
    (mod / "gut.archive").write_bytes(b"x")
    (mod / "kaputt.archive").write_bytes(b"x")
    (mod / "textur.dds").write_bytes(b"x")

    plugin = _SpielMitArchiven({"gut.archive": frozenset({1})})
    idx = _index(tmp_path, plugin)
    idx.rebuild()

    assert idx.get_archives("A") == {"gut.archive": frozenset({1})}
    assert len(idx.get_file_list("A")) == 3, "keine Datei darf verlorengehen"


def test_werfender_leser_bricht_den_scan_nicht_ab(tmp_path: Path) -> None:
    mod = tmp_path / ".mods" / "A"
    mod.mkdir(parents=True)
    (mod / "boom.archive").write_bytes(b"x")
    (mod / "datei.txt").write_bytes(b"x")

    class _Boesartig:
        GameArchiveSuffixes = [".archive"]

        def read_archive_hashes(self, path):
            raise RuntimeError("kaputt")

    idx = _index(tmp_path, _Boesartig())
    idx.rebuild()

    assert idx.get_archives("A") == {}
    assert len(idx.get_file_list("A")) == 2


def test_pruefsummen_ueberleben_den_cache(tmp_path: Path) -> None:
    mod = tmp_path / ".mods" / "A"
    mod.mkdir(parents=True)
    (mod / "eins.archive").write_bytes(b"x")

    plugin = _SpielMitArchiven({"eins.archive": frozenset({2, 4})})
    _index(tmp_path, plugin).rebuild()
    assert plugin.gelesen == ["eins.archive"]

    # Zweiter Lauf: unveraendert, also nichts neu lesen.
    plugin2 = _SpielMitArchiven({"eins.archive": frozenset({2, 4})})
    zweiter = _index(tmp_path, plugin2)
    zweiter.rebuild()

    assert plugin2.gelesen == [], "unveraenderte Mod darf nicht neu gelesen werden"
    assert zweiter.get_archives("A") == {"eins.archive": frozenset({2, 4})}


def _alten_cache_schreiben(tmp_path: Path, mod: Path, version: int,
                           endungen=None) -> None:
    """Cache mit dem ECHTEN Fingerabdruck ablegen.

    Mit einem erfundenen Abdruck wird die Mod ohnehin neu eingelesen --
    dann prueft der Test die Version gar nicht.
    """
    from anvil.core.modindex import _fingerprint

    daten = {
        "version": version,
        "mods": {"A": {
            "fingerprint": _fingerprint(mod),
            "files": [{"rel": "eins.archive", "size": 1}],
            "file_count": 1, "total_size": 1,
        }},
    }
    if endungen is not None:
        daten["archive_suffixes"] = endungen
    (tmp_path / ".modindex.json").write_text(
        json.dumps(daten), encoding="utf-8")


def test_alter_cache_wird_verworfen(tmp_path: Path) -> None:
    """Version 2 kannte keine Archive -- er darf nicht als aktuell gelten."""
    mod = tmp_path / ".mods" / "A"
    mod.mkdir(parents=True)
    (mod / "eins.archive").write_bytes(b"x")
    # Endungen passend eintragen, damit WIRKLICH nur die Version
    # abweicht -- sonst greift die Faehigkeits-Pruefung und der Test
    # sagt nichts ueber die Versionsnummer aus.
    _alten_cache_schreiben(tmp_path, mod, version=2, endungen=[".archive"])

    plugin = _SpielMitArchiven({"eins.archive": frozenset({5})})
    idx = _index(tmp_path, plugin)
    idx.rebuild()

    assert plugin.gelesen == ["eins.archive"], "der alte Cache galt als aktuell"
    assert idx.get_archives("A") == {"eins.archive": frozenset({5})}


def test_cache_ohne_archiv_leser_wird_verworfen(tmp_path: Path) -> None:
    """Nach einem Umzug baut Anvil den Index ohne Spiel-Plugin.

    Der schreibt einen Cache der richtigen Version, aber ohne
    Pruefsummen. "Nie gelesen" sieht darin aus wie "hat keine Archive" --
    die Archiv-Konflikte fielen danach still aus.
    """
    from anvil.core.modindex import _CACHE_VERSION

    mod = tmp_path / ".mods" / "A"
    mod.mkdir(parents=True)
    (mod / "eins.archive").write_bytes(b"x")
    _alten_cache_schreiben(tmp_path, mod, version=_CACHE_VERSION, endungen=[])

    plugin = _SpielMitArchiven({"eins.archive": frozenset({7})})
    idx = _index(tmp_path, plugin)
    idx.rebuild()

    assert plugin.gelesen == ["eins.archive"], (
        "ein Cache ohne Archiv-Leser darf nicht als vollstaendig gelten"
    )
    assert idx.get_archives("A") == {"eins.archive": frozenset({7})}


# ── Sprachen ─────────────────────────────────────────────────────────


def test_alle_schluessel_in_allen_sprachen() -> None:
    ordner = Path(__file__).parents[1] / "anvil" / "locales"
    schluessel = (
        "archive_conflicts", "col_archive_own", "col_archive_other",
        "col_archive_count", "archive_conflicts_hint",
    )
    for sprache in ("de", "en", "es", "fr", "it", "pt", "ru"):
        daten = json.loads((ordner / f"{sprache}.json").read_text(encoding="utf-8"))
        for s in schluessel:
            assert daten["mod_detail"].get(s), f"{sprache}: mod_detail.{s} fehlt"


# ── Einbau ───────────────────────────────────────────────────────────


def test_hauptfenster_reicht_die_archivdaten_durch() -> None:
    import inspect

    from anvil.mainwindow import MainWindow

    scan = inspect.getsource(MainWindow._run_conflict_scan)
    assert "archive_hashes=" in scan

    zaehlung = inspect.getsource(MainWindow._compute_conflict_data)
    assert "archive_conflicts" in zaehlung, (
        "sonst bleiben die Symbole in der Mod-Liste blind"
    )


def test_index_bekommt_das_plugin() -> None:
    import inspect

    from anvil.mainwindow import MainWindow

    quelle = inspect.getsource(MainWindow)
    assert "game_plugin=plugin" in quelle
