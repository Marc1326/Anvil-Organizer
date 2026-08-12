"""Der Mod-Index muss Aenderungen in Unterordnern bemerken.

Geprueft wurde frueher nur die Zeit des Mod-Wurzelordners. Wird eine
Datei in ``archive/pc/mod/`` umbenannt, aendert das nur die Zeit dieses
Unterordners -- die Mod galt als unveraendert. Der Deployer arbeitete
dann mit der alten Dateiliste, fand die Quelle nicht und liess die Mod
weg. Ohne Meldung, mit "0 errors" im Log.
"""

import json
import os
from pathlib import Path

from anvil.core.mod_deployer import ModDeployer
from anvil.core.mod_list_io import write_active_mods, write_global_modlist
from anvil.core.modindex import ModIndex

TIEF = "archive/pc/mod/00_Test.archive"


def _welt(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    instance = tmp_path / "Instance"
    game = tmp_path / "Game"
    instance.mkdir()
    game.mkdir()
    mods = instance / ".mods"
    profiles = instance / ".profiles"
    (profiles / "Default").mkdir(parents=True)
    mods.mkdir()
    return instance, game, mods, profiles


def _datei(mods: Path, mod: str, rel: str, inhalt: str = "x") -> Path:
    ziel = mods / mod / rel
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(inhalt, encoding="utf-8")
    return ziel


ZEIT = (1_000_000, 1_000_000)


def _wurzelzeit_einfrieren(mod_dir: Path) -> None:
    """Haelt die Zeit der Wurzel konstant -- so wie es real passiert.

    Beim Umbenennen in einem Unterordner bleibt die Wurzel unberuehrt.
    Wird sie hier nur *irgendwie* gesetzt, sieht schon die alte, kaputte
    Pruefung eine Aenderung und der Test bestuende auch damit. Deshalb
    exakt derselbe Wert vor und nach dem Eingriff.
    """
    os.utime(mod_dir, ZEIT)
    assert os.stat(mod_dir).st_mtime == ZEIT[1], "Wurzelzeit nicht eingefroren"


# ── Index ──────────────────────────────────────────────────────────────

def test_umbenennen_im_unterordner_wird_bemerkt(tmp_path: Path) -> None:
    instance, _game, mods, _profiles = _welt(tmp_path)
    _datei(mods, "Mod", TIEF)
    _wurzelzeit_einfrieren(mods / "Mod")
    idx = ModIndex(instance)
    idx.rebuild()
    assert [f["rel"] for f in idx.get_file_list("Mod")] == [TIEF]

    neu = "archive/pc/mod/zz_Test.archive"
    (mods / "Mod" / TIEF).rename(mods / "Mod" / neu)
    _wurzelzeit_einfrieren(mods / "Mod")

    zweiter = ModIndex(instance)
    zweiter.rebuild()
    assert [f["rel"] for f in zweiter.get_file_list("Mod")] == [neu]


def test_neue_datei_im_unterordner_wird_bemerkt(tmp_path: Path) -> None:
    instance, _game, mods, _profiles = _welt(tmp_path)
    _datei(mods, "Mod", TIEF)
    _wurzelzeit_einfrieren(mods / "Mod")
    ModIndex(instance).rebuild()

    _datei(mods, "Mod", "archive/pc/mod/zweite.archive")
    _wurzelzeit_einfrieren(mods / "Mod")

    idx = ModIndex(instance)
    idx.rebuild()
    assert len(idx.get_file_list("Mod")) == 2


def test_geloeschte_datei_im_unterordner_wird_bemerkt(tmp_path: Path) -> None:
    instance, _game, mods, _profiles = _welt(tmp_path)
    _datei(mods, "Mod", TIEF)
    _wurzelzeit_einfrieren(mods / "Mod")
    ModIndex(instance).rebuild()

    (mods / "Mod" / TIEF).unlink()
    _wurzelzeit_einfrieren(mods / "Mod")

    idx = ModIndex(instance)
    idx.rebuild()
    assert idx.get_file_list("Mod") == []


# ── Deploy ─────────────────────────────────────────────────────────────

def test_umbenannte_datei_wird_trotzdem_ausgerollt(tmp_path: Path) -> None:
    """Der eigentliche Schaden: die Mod fehlte im Spiel."""
    instance, game, mods, profiles = _welt(tmp_path)
    _datei(mods, "Mod", TIEF)
    _wurzelzeit_einfrieren(mods / "Mod")
    write_global_modlist(profiles, ["Mod"])
    write_active_mods(profiles / "Default", {"Mod"})

    idx = ModIndex(instance)
    idx.rebuild()

    neu = "archive/pc/mod/zz_Test.archive"
    (mods / "Mod" / TIEF).rename(mods / "Mod" / neu)
    _wurzelzeit_einfrieren(mods / "Mod")
    idx.rebuild()

    ergebnis = ModDeployer(instance, game, mod_index=idx).deploy()

    assert (game / neu).exists(), "die umbenannte Datei fehlt im Spiel"
    assert ergebnis.missing_sources == []
    assert ergebnis.success


def test_veraltete_dateiliste_wird_gemeldet(tmp_path: Path) -> None:
    """Der Neuscan rettet den Deploy -- sagen muss Anvil es trotzdem."""
    instance, game, mods, profiles = _welt(tmp_path)
    _datei(mods, "Mod", TIEF)
    _wurzelzeit_einfrieren(mods / "Mod")
    write_global_modlist(profiles, ["Mod"])
    write_active_mods(profiles / "Default", {"Mod"})

    idx = ModIndex(instance)
    idx.rebuild()

    neu = "archive/pc/mod/zz_Test.archive"
    (mods / "Mod" / TIEF).rename(mods / "Mod" / neu)
    _wurzelzeit_einfrieren(mods / "Mod")
    # Index absichtlich NICHT neu aufbauen -- der Deployer muss es merken.

    ergebnis = ModDeployer(instance, game, mod_index=idx).deploy()

    assert ergebnis.stale_index_mods == ["Mod"]
    assert (game / neu).exists(), "Neuscan hat die Mod nicht gerettet"
    assert ergebnis.success


def test_verschwundene_quelldatei_wird_gemeldet(tmp_path: Path) -> None:
    """Stiller Ausfall: frueher stand trotzdem nichts im Log.

    Gemeldet wird sie, abgebrochen wird nicht -- eine fehlende Textur
    darf den Spielstart nicht verhindern.
    """
    instance, game, mods, profiles = _welt(tmp_path)
    _datei(mods, "Mod", TIEF)
    _wurzelzeit_einfrieren(mods / "Mod")
    write_global_modlist(profiles, ["Mod"])
    write_active_mods(profiles / "Default", {"Mod"})

    idx = ModIndex(instance)
    idx.rebuild()

    # Die Datei verschwindet, waehrend der Index steht. Ein Neuscan kann
    # sie nicht wiederfinden -- also muss Anvil es sagen.
    (mods / "Mod" / TIEF).unlink()
    _wurzelzeit_einfrieren(mods / "Mod")

    ergebnis = ModDeployer(instance, game, mod_index=idx).deploy()

    assert ergebnis.missing_sources, "verschwundene Datei blieb unbemerkt"
    assert ergebnis.success, "der Spielstart darf daran nicht scheitern"
    assert not (game / TIEF).exists()


def test_unbekannte_mod_wird_nicht_uebergangen(tmp_path: Path) -> None:
    """Steht die Mod gar nicht im Index, fiel sie frueher lautlos raus."""
    instance, game, mods, profiles = _welt(tmp_path)
    _datei(mods, "Bekannt", "archive/pc/mod/a.archive")
    write_global_modlist(profiles, ["Bekannt", "Neu"])
    write_active_mods(profiles / "Default", {"Bekannt", "Neu"})

    idx = ModIndex(instance)
    idx.rebuild()

    # Mod kommt nach dem Einlesen dazu und ist dem Index unbekannt.
    _datei(mods, "Neu", "archive/pc/mod/b.archive")

    ergebnis = ModDeployer(instance, game, mod_index=idx).deploy()

    assert (game / "archive/pc/mod/b.archive").exists(), "unbekannte Mod fehlt im Spiel"
    assert ergebnis.success


def test_zukunftsdatierter_ordner_blendet_nichts_aus(tmp_path: Path) -> None:
    """Ein Ordner aus der Zukunft darf spaetere Aenderungen nicht decken.

    Mit dem Hoechststand aller Ordnerzeiten war genau das moeglich:
    falsch datierte Archive oder ein NTFS-Zeitversatz nagelten das
    Maximum fest, jede echte Aenderung fiel darunter durch.
    """
    instance, _game, mods, _profiles = _welt(tmp_path)
    _datei(mods, "Mod", TIEF)
    _datei(mods, "Mod", "readme/liesmich.txt")
    zukunft = 4_102_444_800  # 01.01.2100
    os.utime(mods / "Mod" / "readme", (zukunft, zukunft))
    _wurzelzeit_einfrieren(mods / "Mod")

    idx = ModIndex(instance)
    idx.rebuild()
    assert len(idx.get_file_list("Mod")) == 2

    _datei(mods, "Mod", "archive/pc/mod/spaeter.archive")
    _wurzelzeit_einfrieren(mods / "Mod")

    zweiter = ModIndex(instance)
    zweiter.rebuild()
    assert len(zweiter.get_file_list("Mod")) == 3, "spaetere Aenderung uebersehen"


def test_kaputte_cachedatei_reisst_nichts_ab(tmp_path: Path) -> None:
    """Eintraege ohne 'rel' liessen frueher den Konfliktscanner abstuerzen.

    Geprueft wird der echte Weg: eine beschaedigte Datei auf der Platte,
    nicht ein von Hand verbogener Speicher.
    """
    instance, game, mods, profiles = _welt(tmp_path)
    _datei(mods, "Mod", TIEF)
    write_global_modlist(profiles, ["Mod"])
    write_active_mods(profiles / "Default", {"Mod"})
    ModIndex(instance).rebuild()

    datei = instance / ".modindex.json"
    daten = json.loads(datei.read_text(encoding="utf-8"))
    daten["mods"]["Mod"]["files"].append({"size": 1})   # kein 'rel'
    daten["mods"]["Mod"]["files"].append("Unfug")       # gar kein Eintrag
    datei.write_text(json.dumps(daten), encoding="utf-8")

    idx = ModIndex(instance)
    idx.rebuild()
    # Roher Zugriff -- genau daran riss der Konfliktscanner ab.
    assert [f["rel"] for f in idx.get_file_list("Mod")] == [TIEF]
    assert idx.get_stats("Mod") == (1, len("x"))

    ergebnis = ModDeployer(instance, game, mod_index=idx).deploy()
    assert ergebnis.success
    assert (game / TIEF).exists(), "die heile Datei muss trotzdem ankommen"


def test_falsche_typen_in_eintraegen_stuerzen_nicht_ab(tmp_path: Path) -> None:
    """Eine Zahl als Pfad und Text als Groesse rissen den Lauf ab."""
    instance, game, mods, profiles = _welt(tmp_path)
    _datei(mods, "Mod", TIEF)
    write_global_modlist(profiles, ["Mod"])
    write_active_mods(profiles / "Default", {"Mod"})
    ModIndex(instance).rebuild()
    datei = instance / ".modindex.json"

    for muell in ({"rel": TIEF, "size": "abc"}, {"rel": 123, "size": 1}):
        daten = json.loads(datei.read_text(encoding="utf-8"))
        daten["mods"]["Mod"]["files"] = [muell]
        datei.write_text(json.dumps(daten), encoding="utf-8")

        idx = ModIndex(instance)
        idx.rebuild()
        ergebnis = ModDeployer(instance, game, mod_index=idx).deploy()
        assert ergebnis.success
        assert (game / TIEF).exists(), "die heile Datei muss ankommen"


def test_typkaputte_cachedatei_stuerzt_nicht_ab(tmp_path: Path) -> None:
    """Gueltiges JSON mit falschen Typen riss den Start mit ab."""
    instance, _game, mods, _profiles = _welt(tmp_path)
    _datei(mods, "Mod", TIEF)
    ModIndex(instance).rebuild()
    datei = instance / ".modindex.json"

    for muell in ({"version": 2, "mods": [1, 2, 3]},
                  {"version": 2, "mods": {"Mod": {"files": 5}}}):
        datei.write_text(json.dumps(muell), encoding="utf-8")
        idx = ModIndex(instance)
        idx.rebuild()
        assert [f["rel"] for f in idx.get_file_list("Mod")] == [TIEF]


def test_leere_mod_loest_keinen_fehlalarm_aus(tmp_path: Path) -> None:
    """Ein leerer Ordner ist normal -- Trenner heissen nicht immer so."""
    instance, game, mods, profiles = _welt(tmp_path)
    (mods / "Kapitel_separator").mkdir()
    (mods / "Leer").mkdir()  # kein _separator im Namen, trotzdem leer
    _datei(mods, "Mod", TIEF)
    namen = ["Kapitel_separator", "Leer", "Mod"]
    write_global_modlist(profiles, namen)
    write_active_mods(profiles / "Default", set(namen))

    idx = ModIndex(instance)
    idx.rebuild()

    ergebnis = ModDeployer(instance, game, mod_index=idx).deploy()

    assert ergebnis.missing_sources == []
    assert ergebnis.stale_index_mods == []
    assert ergebnis.success


def test_fehlender_mod_ordner_wird_gemeldet(tmp_path: Path) -> None:
    """Nicht eingehaengtes Laufwerk: frueher fiel alles lautlos aus."""
    instance, game, mods, profiles = _welt(tmp_path)
    _datei(mods, "Mod", TIEF)
    write_global_modlist(profiles, ["Mod", "Verschwunden"])
    write_active_mods(profiles / "Default", {"Mod", "Verschwunden"})

    idx = ModIndex(instance)
    idx.rebuild()

    ergebnis = ModDeployer(instance, game, mod_index=idx).deploy()

    assert any("Verschwunden" in m for m in ergebnis.missing_sources)
    assert ergebnis.success


def test_datei_weg_ohne_zeitaenderung_wird_gemeldet(tmp_path: Path) -> None:
    """Der harte Fall: keine Ordnerzeit aendert sich, der Neuscan ist blind."""
    instance, game, mods, profiles = _welt(tmp_path)
    _datei(mods, "Mod", TIEF)
    _wurzelzeit_einfrieren(mods / "Mod")
    write_global_modlist(profiles, ["Mod"])
    write_active_mods(profiles / "Default", {"Mod"})

    idx = ModIndex(instance)
    idx.rebuild()

    unterordner = mods / "Mod" / "archive/pc/mod"
    vorher = os.stat(unterordner)
    (mods / "Mod" / TIEF).unlink()
    # Auf die Nanosekunde zuruecksetzen. Mit dem float-Wert aus st_mtime
    # weicht der Zeitstempel um ein paar Nanosekunden ab, der Abdruck
    # aendert sich doch, und der Test liefe ueber den Neuscan statt ueber
    # das Sicherheitsnetz.
    os.utime(unterordner, ns=(vorher.st_atime_ns, vorher.st_mtime_ns))
    _wurzelzeit_einfrieren(mods / "Mod")

    ergebnis = ModDeployer(instance, game, mod_index=idx).deploy()

    assert ergebnis.stale_index_mods == [], "Abdruck haette gleich bleiben muessen"
    assert ergebnis.missing_sources == [f"Mod/{TIEF}"]
    assert "Mod" not in idx.mod_names(), "Index behaelt die falsche Liste"
    assert ergebnis.success
