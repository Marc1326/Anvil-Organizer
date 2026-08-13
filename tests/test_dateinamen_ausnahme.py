"""Eine einzelne Mod von der Durchnummerierung ausnehmen.

Anvil stellt den Archiven eine Zahl voran, damit die Reihenfolge aus der
Mod-Liste im Spiel ankommt. Manche Mods bringen aber einen Loader mit,
der seine Dateien am exakten Namen sucht -- fuer die muss der Zaehler
abschaltbar sein.

Der Preis steht im Tooltip: die Position dieser Mod wirkt dann nicht
mehr, und eine gleichnamige Datei einer anderen Mod kann zusaetzlich im
Spielordner liegen.
"""

from __future__ import annotations

import json
from pathlib import Path

from anvil.core.mod_deployer import ModDeployer
from anvil.core.mod_entry import scan_mods_directory
from anvil.core.mod_list_io import write_active_mods, write_global_modlist
from anvil.core.mod_metadata import write_meta_ini
# Nicht vom Arbeitsverzeichnis abhaengen: pytest laesst sich aus jedem
# Ordner starten.
_WURZEL = Path(__file__).resolve().parent.parent


ORDNER = "archive/pc/mod"


def _welt(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    instanz = tmp_path / "Instance"
    spiel = tmp_path / "Game"
    mods = instanz / ".mods"
    profile = instanz / ".profiles"
    (profile / "Default").mkdir(parents=True)
    mods.mkdir(parents=True)
    spiel.mkdir()
    return instanz, spiel, mods, profile


def _mod(mods: Path, name: str, dateien: list[str]) -> None:
    for rel in dateien:
        ziel = mods / name / rel
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(b"x")


def _liste(profile: Path, namen: list[str]) -> None:
    write_global_modlist(profile, namen)
    write_active_mods(profile / "Default", set(namen))


def _namen(ordner: Path) -> list[str]:
    return sorted(p.name for p in ordner.iterdir())


def _deployer(instanz: Path, spiel: Path, ausgenommen=None) -> ModDeployer:
    return ModDeployer(
        instanz, spiel,
        pak_load_order_dirs=[ORDNER],
        pak_load_order_extensions=[".archive"],
        pak_load_order_first_wins=True,
        keep_file_name_mods=ausgenommen or set(),
    )


# ── Die Wirkung ──────────────────────────────────────────────────────


def test_ausgenommene_mod_behaelt_ihren_namen(tmp_path: Path) -> None:
    instanz, spiel, mods, profile = _welt(tmp_path)
    _mod(mods, "Loader", [f"{ORDNER}/CyberEngine.archive"])
    _mod(mods, "Normal", [f"{ORDNER}/Textur.archive"])
    _liste(profile, ["Loader", "Normal"])

    _deployer(instanz, spiel, {"Loader"}).deploy()

    namen = _namen(spiel / ORDNER)
    assert "CyberEngine.archive" in namen, (
        f"Loader-Datei wurde umbenannt: {namen}"
    )
    assert "001_Textur.archive" in namen, (
        f"die andere Mod wurde nicht mehr nummeriert: {namen}"
    )


def test_ohne_ausnahme_bekommen_beide_eine_zahl(tmp_path: Path) -> None:
    """Gegenprobe -- sonst misst der Test oben nichts."""
    instanz, spiel, mods, profile = _welt(tmp_path)
    _mod(mods, "Loader", [f"{ORDNER}/CyberEngine.archive"])
    _mod(mods, "Normal", [f"{ORDNER}/Textur.archive"])
    _liste(profile, ["Loader", "Normal"])

    _deployer(instanz, spiel).deploy()

    assert _namen(spiel / ORDNER) == ["000_CyberEngine.archive",
                                      "001_Textur.archive"]


def test_die_zahlen_der_anderen_verschieben_sich_nicht(tmp_path: Path) -> None:
    """Die Ausnahme darf die Reihenfolge der uebrigen nicht verwuerfeln."""
    instanz, spiel, mods, profile = _welt(tmp_path)
    for name in ("A", "B", "C"):
        _mod(mods, name, [f"{ORDNER}/{name}.archive"])
    _liste(profile, ["A", "B", "C"])

    _deployer(instanz, spiel, {"B"}).deploy()

    assert _namen(spiel / ORDNER) == ["000_A.archive", "002_C.archive",
                                      "B.archive"]


def test_gross_und_kleinschreibung_egal(tmp_path: Path) -> None:
    instanz, spiel, mods, profile = _welt(tmp_path)
    _mod(mods, "Loader", [f"{ORDNER}/x.archive"])
    _liste(profile, ["Loader"])

    _deployer(instanz, spiel, {"LOADER"}).deploy()

    assert _namen(spiel / ORDNER) == ["x.archive"]


def test_gespann_wird_gemeinsam_ausgenommen(tmp_path: Path) -> None:
    """Die Entscheidung faellt pro Mod, nicht pro Datei."""
    instanz, spiel, mods, profile = _welt(tmp_path)
    _mod(mods, "Unreal", [
        "Stalker2/Content/Paks/~mods/a_P.pak",
        "Stalker2/Content/Paks/~mods/a_P.utoc",
        "Stalker2/Content/Paks/~mods/a_P.ucas",
    ])
    _liste(profile, ["Unreal"])

    ModDeployer(
        instanz, spiel,
        pak_load_order_dirs=["Stalker2/Content/Paks/~mods"],
        keep_file_name_mods={"Unreal"},
    ).deploy()

    assert _namen(spiel / "Stalker2/Content/Paks/~mods") == [
        "a_P.pak", "a_P.ucas", "a_P.utoc",
    ]


# ── Das Manifest ─────────────────────────────────────────────────────


def test_kein_unnumbered_im_manifest(tmp_path: Path) -> None:
    """Ohne Zaehler gibt es keinen Originalnamen zu merken.

    Sonst wuerde ``_drop_superseded_numbered()`` die Datei fuer eine
    schwaechere Dublette halten und wegraeumen.
    """
    instanz, spiel, mods, profile = _welt(tmp_path)
    _mod(mods, "Loader", [f"{ORDNER}/x.archive"])
    _liste(profile, ["Loader"])

    _deployer(instanz, spiel, {"Loader"}).deploy()

    manifest = json.loads(
        (instanz / ModDeployer.MANIFEST_NAME).read_text(encoding="utf-8"),
    )
    treffer = [e for e in manifest["symlinks"]
               if "x.archive" in str(e.get("link", ""))]
    assert treffer, f"kein Eintrag gefunden: {manifest['symlinks']}"
    assert not treffer[0].get("unnumbered"), (
        "unnumbered gesetzt, obwohl nicht umbenannt wurde"
    )


def test_nummerierte_mod_bekommt_sehr_wohl_unnumbered(tmp_path: Path) -> None:
    """Gegenprobe zum Test darueber."""
    instanz, spiel, mods, profile = _welt(tmp_path)
    _mod(mods, "Normal", [f"{ORDNER}/x.archive"])
    _liste(profile, ["Normal"])

    _deployer(instanz, spiel).deploy()

    manifest = json.loads(
        (instanz / ModDeployer.MANIFEST_NAME).read_text(encoding="utf-8"),
    )
    treffer = [e for e in manifest["symlinks"]
               if "x.archive" in str(e.get("link", ""))]
    assert treffer[0].get("unnumbered")


# ── Der Merker in der meta.ini ───────────────────────────────────────


def _eintraege(instanz: Path, profile: Path):
    return {
        e.name: e for e in scan_mods_directory(instanz, profile / "Default")
    }


def test_merker_wird_gelesen(tmp_path: Path) -> None:
    instanz, _spiel, mods, profile = _welt(tmp_path)
    _mod(mods, "Loader", [f"{ORDNER}/x.archive"])
    _mod(mods, "Normal", [f"{ORDNER}/y.archive"])
    _liste(profile, ["Loader", "Normal"])
    write_meta_ini(mods / "Loader", {"keep_file_names": "1"})

    eintraege = _eintraege(instanz, profile)

    assert eintraege["Loader"].keep_file_names is True
    assert eintraege["Normal"].keep_file_names is False


def test_null_schaltet_wieder_ab(tmp_path: Path) -> None:
    instanz, _spiel, mods, profile = _welt(tmp_path)
    _mod(mods, "Loader", [f"{ORDNER}/x.archive"])
    _liste(profile, ["Loader"])
    write_meta_ini(mods / "Loader", {"keep_file_names": "0"})

    assert _eintraege(instanz, profile)["Loader"].keep_file_names is False


def test_merker_ueberlebt_weitere_meta_schreibvorgaenge(tmp_path: Path) -> None:
    """write_meta_ini mischt -- der Merker darf nicht verlorengehen."""
    instanz, _spiel, mods, profile = _welt(tmp_path)
    _mod(mods, "Loader", [f"{ORDNER}/x.archive"])
    _liste(profile, ["Loader"])
    write_meta_ini(mods / "Loader", {"keep_file_names": "1"})
    write_meta_ini(mods / "Loader", {"version": "2.0"})

    assert _eintraege(instanz, profile)["Loader"].keep_file_names is True


def test_trenner_bekommt_den_merker_nie(tmp_path: Path) -> None:
    instanz, _spiel, mods, profile = _welt(tmp_path)
    (mods / "Gruppe_separator").mkdir()
    _liste(profile, ["Gruppe_separator"])
    write_meta_ini(mods / "Gruppe_separator", {"keep_file_names": "1"})

    eintrag = _eintraege(instanz, profile)["Gruppe_separator"]
    assert eintrag.is_separator is True
    assert eintrag.keep_file_names is False


# ── Verkabelung ──────────────────────────────────────────────────────


def test_setter_erreicht_einen_laufenden_deployer(tmp_path: Path) -> None:
    instanz, spiel, mods, profile = _welt(tmp_path)
    _mod(mods, "Loader", [f"{ORDNER}/x.archive"])
    _liste(profile, ["Loader"])
    d = _deployer(instanz, spiel)

    assert d.keeps_file_names("Loader") is False
    d.set_keep_file_name_mods({"Loader"})
    assert d.keeps_file_names("Loader") is True

    d.deploy()
    assert _namen(spiel / ORDNER) == ["x.archive"]


def test_panel_reicht_den_merker_weiter() -> None:
    """Ohne diese Kette bliebe der Merker in der meta.ini stecken."""
    from anvil.widgets.game_panel import GamePanel

    class _Deployer:
        def __init__(self):
            self.bekommen = None

        def set_keep_file_name_mods(self, namen):
            self.bekommen = set(namen)

    panel = GamePanel.__new__(GamePanel)
    panel._keep_file_name_mods = set()
    panel._deployer = _Deployer()

    GamePanel.set_keep_file_name_mods(panel, {"Loader"})

    assert panel._keep_file_name_mods == {"Loader"}
    assert panel._deployer.bekommen == {"Loader"}


def test_hauptfenster_sammelt_nur_echte_mods() -> None:
    from anvil.mainwindow import MainWindow

    class _Eintrag:
        def __init__(self, name, sep, keep):
            self.name = name
            self.is_separator = sep
            self.keep_file_names = keep

    class _Panel:
        def __init__(self):
            self.bekommen = None

        def set_keep_file_name_mods(self, namen):
            self.bekommen = set(namen)

    class _Fenster:
        _sync_keep_file_name_mods = MainWindow._sync_keep_file_name_mods

        def __init__(self):
            self._current_mod_entries = [
                _Eintrag("Loader", False, True),
                _Eintrag("Normal", False, False),
                _Eintrag("Gruppe_separator", True, True),
            ]
            self._game_panel = _Panel()

    f = _Fenster()
    f._sync_keep_file_name_mods()

    assert f._game_panel.bekommen == {"Loader"}


# ── Das Umschalten selbst ────────────────────────────────────────────


class _Log:
    def __init__(self):
        self.zeilen: list[tuple[str, str]] = []

    def add_log(self, art, text):
        self.zeilen.append((art, text))

    @property
    def warnungen(self):
        return [t for a, t in self.zeilen if a == "warning"]


def _schalter(instanz: Path, mods: Path, eintraege=()):
    """MainWindow-Ersatz mit genau dem, was das Umschalten anfasst."""
    from anvil.mainwindow import MainWindow

    class _Pfade:
        def __init__(self, m):
            self.mods = m

    class _Panel:
        def __init__(self):
            self.bekommen = None

        def set_keep_file_name_mods(self, namen):
            self.bekommen = set(namen)

    class _F:
        _toggle_keep_file_names = MainWindow._toggle_keep_file_names
        _sync_keep_file_name_mods = MainWindow._sync_keep_file_name_mods

        def __init__(self):
            self._current_instance_path = instanz
            self._current_mod_entries = list(eintraege)
            self._log_panel = _Log()
            self._game_panel = _Panel()
            self.neu_geladen = 0

        def _reload_mod_list(self):
            self.neu_geladen += 1

    f = _F()
    import anvil.mainwindow as mw
    f._pfade = _Pfade(mods)
    return f, _Pfade(mods)


def _mit_pfaden(f, mods: Path):
    """Setzt _active_instance_paths fuer die Dauer eines Aufrufs."""
    import anvil.mainwindow as mw

    class _Pfade:
        def __init__(self, m):
            self.mods = m

    alt = mw._active_instance_paths
    mw._active_instance_paths = lambda self: _Pfade(mods)
    return alt


def test_umschalten_schreibt_die_meta_ini(tmp_path: Path) -> None:
    instanz, _spiel, mods, profile = _welt(tmp_path)
    _mod(mods, "Loader", [f"{ORDNER}/x.archive"])
    _liste(profile, ["Loader"])
    f, _ = _schalter(instanz, mods)

    import anvil.mainwindow as mw
    alt = _mit_pfaden(f, mods)
    try:
        f._toggle_keep_file_names("Loader", True)
    finally:
        mw._active_instance_paths = alt

    from anvil.core.mod_metadata import read_meta_ini
    assert read_meta_ini(mods / "Loader").get("keep_file_names") == "1"
    assert f.neu_geladen == 1


def test_umschalten_nimmt_auch_zurueck(tmp_path: Path) -> None:
    instanz, _spiel, mods, profile = _welt(tmp_path)
    _mod(mods, "Loader", [f"{ORDNER}/x.archive"])
    _liste(profile, ["Loader"])
    write_meta_ini(mods / "Loader", {"keep_file_names": "1"})
    f, _ = _schalter(instanz, mods)

    import anvil.mainwindow as mw
    alt = _mit_pfaden(f, mods)
    try:
        f._toggle_keep_file_names("Loader", False)
    finally:
        mw._active_instance_paths = alt

    from anvil.core.mod_metadata import read_meta_ini
    assert read_meta_ini(mods / "Loader").get("keep_file_names") == "0"


def test_mehrere_mods_auf_einmal(tmp_path: Path) -> None:
    instanz, _spiel, mods, profile = _welt(tmp_path)
    for n in ("A", "B", "C"):
        _mod(mods, n, [f"{ORDNER}/{n}.archive"])
    _liste(profile, ["A", "B", "C"])
    f, _ = _schalter(instanz, mods)

    import anvil.mainwindow as mw
    alt = _mit_pfaden(f, mods)
    try:
        f._toggle_keep_file_names(["A", "C"], True)
    finally:
        mw._active_instance_paths = alt

    from anvil.core.mod_metadata import read_meta_ini
    assert read_meta_ini(mods / "A").get("keep_file_names") == "1"
    assert read_meta_ini(mods / "C").get("keep_file_names") == "1"
    assert read_meta_ini(mods / "B").get("keep_file_names", "") != "1"
    assert f.neu_geladen == 1, "die Liste wurde mehrfach neu geladen"


def test_verlegter_mod_ordner_wird_gefunden(tmp_path: Path) -> None:
    """Der Mod-Ordner heisst nicht immer ``.mods``.

    Frueher stand der Name hart im Code -- bei einer Instanz mit eigenem
    Speicherort passierte gar nichts, ohne jede Meldung.
    """
    instanz, _spiel, _mods, profile = _welt(tmp_path)
    woanders = tmp_path / "ganz-woanders"
    (woanders / "Loader").mkdir(parents=True)
    f, _ = _schalter(instanz, woanders)

    import anvil.mainwindow as mw
    alt = _mit_pfaden(f, woanders)
    try:
        f._toggle_keep_file_names("Loader", True)
    finally:
        mw._active_instance_paths = alt

    from anvil.core.mod_metadata import read_meta_ini
    assert read_meta_ini(woanders / "Loader").get("keep_file_names") == "1"
    assert not f._log_panel.warnungen, f._log_panel.warnungen


def test_verschwundener_ordner_wird_gemeldet(tmp_path: Path) -> None:
    """Frueher ein stiller Ausstieg -- niemand erfuhr davon."""
    instanz, _spiel, mods, _profile = _welt(tmp_path)
    f, _ = _schalter(instanz, mods)

    import anvil.mainwindow as mw
    alt = _mit_pfaden(f, mods)
    try:
        f._toggle_keep_file_names("GibtEsNicht", True)
    finally:
        mw._active_instance_paths = alt

    assert f._log_panel.warnungen, "kein Hinweis im Log"
    assert "GibtEsNicht" in f._log_panel.warnungen[0]
    assert f.neu_geladen == 0


def test_schreibgeschuetzter_ordner_meldet_fehler(tmp_path: Path) -> None:
    """write_meta_ini schluckt Schreibfehler -- ohne Nachlesen wuerde
    das Log Erfolg behaupten, obwohl nichts geschrieben wurde.
    """
    import os

    instanz, _spiel, mods, profile = _welt(tmp_path)
    _mod(mods, "Loader", [f"{ORDNER}/x.archive"])
    _liste(profile, ["Loader"])
    f, _ = _schalter(instanz, mods)

    os.chmod(mods / "Loader", 0o500)
    import anvil.mainwindow as mw
    alt = _mit_pfaden(f, mods)
    try:
        f._toggle_keep_file_names("Loader", True)
    finally:
        mw._active_instance_paths = alt
        os.chmod(mods / "Loader", 0o700)

    assert f._log_panel.warnungen, "Fehler wurde verschwiegen"
    assert f.neu_geladen == 0


def test_leere_auswahl_tut_nichts(tmp_path: Path) -> None:
    instanz, _spiel, mods, _profile = _welt(tmp_path)
    f, _ = _schalter(instanz, mods)
    f._toggle_keep_file_names([], True)
    assert f.neu_geladen == 0


# ── Der Menuepunkt erscheint nur, wo er wirkt ────────────────────────


def test_menue_nur_bei_spielen_die_nummerieren() -> None:
    from anvil.mainwindow import MainWindow
    from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game
    from anvil.plugins.games.game_stalker2 import Stalker2Game
    from anvil.plugins.games.game_stellarblade import StellarBladeGame
    from anvil.plugins.games.game_skyrimse import SkyrimSEGame

    class _Fenster:
        _game_numbers_archives = MainWindow._game_numbers_archives

        def __init__(self, plugin):
            self._current_plugin = plugin

    assert _Fenster(Cyberpunk2077Game)._game_numbers_archives() is True
    assert _Fenster(Stalker2Game)._game_numbers_archives() is True
    assert _Fenster(StellarBladeGame)._game_numbers_archives() is False
    assert _Fenster(SkyrimSEGame)._game_numbers_archives() is False
    assert _Fenster(None)._game_numbers_archives() is False


# ── Anzeige in der Liste ─────────────────────────────────────────────


def test_zeile_bekommt_ein_zeichen_und_einen_tooltip() -> None:
    from anvil.core.mod_entry import ModEntry
    from anvil.models.mod_list_model import mod_entry_to_row

    aus = mod_entry_to_row(
        ModEntry(name="Loader", enabled=True, priority=0,
                 install_path=Path("/tmp/Loader"), keep_file_names=True),
    )
    normal = mod_entry_to_row(
        ModEntry(name="Normal", enabled=True, priority=1,
                 install_path=Path("/tmp/Normal")),
    )

    assert aus.keep_file_names is True
    assert aus.markers, "kein Zeichen in der Marker-Spalte"
    assert normal.markers == ""


def test_zeichen_bleibt_weg_wo_es_nichts_bedeutet() -> None:
    """Eine aus einer Cyberpunk-Instanz kopierte meta.ini bringt den
    Merker mit. Bei Skyrim waeren Zeichen und Tooltip eine
    Falschaussage -- dort wird gar nicht nummeriert.
    """
    from PySide6.QtCore import Qt

    from anvil.core.mod_entry import ModEntry
    from anvil.models.mod_list_model import (
        COL_MARKERS, COL_NAME, ModListModel, mod_entry_to_row,
    )
    from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game
    from anvil.plugins.games.game_skyrimse import SkyrimSEGame

    zeile = mod_entry_to_row(
        ModEntry(name="Loader", enabled=True, priority=0,
                 install_path=Path("/tmp/Loader"), keep_file_names=True),
    )

    def _zeigt(plugin):
        m = ModListModel()
        m.set_load_order_plugin(plugin)
        m.set_mods([zeile])
        idx = m.index(0, COL_MARKERS)
        name = m.index(0, COL_NAME)
        return (m.data(idx, Qt.ItemDataRole.DisplayRole),
                m.data(name, Qt.ItemDataRole.ToolTipRole))

    zeichen_cp, tip_cp = _zeigt(Cyberpunk2077Game)
    zeichen_sky, tip_sky = _zeigt(SkyrimSEGame)

    assert zeichen_cp, "bei Cyberpunk fehlt das Zeichen"
    assert tip_cp
    assert not zeichen_sky, "bei Skyrim steht ein Zeichen, das nichts bedeutet"
    assert not tip_sky


def test_tooltip_nennt_beide_folgen() -> None:
    """Position wirkt nicht mehr UND die Datei kann doppelt vorliegen."""
    import json as _json

    texte = _json.loads(
        (_WURZEL / "anvil/locales/de.json").read_text(encoding="utf-8"),
    )
    text = texte["tooltip"]["keep_file_names"]
    assert "Position" in text
    assert "gleichnamige" in text


def test_alle_sprachen_kennen_die_schluessel() -> None:
    import json as _json

    for datei in sorted((_WURZEL / "anvil/locales").glob("*.json")):
        d = _json.loads(datei.read_text(encoding="utf-8"))
        assert "keep_file_names" in d["context"], datei.name
        assert "keep_file_names" in d["tooltip"], datei.name
        assert "keep_file_names_on" in d["log"], datei.name
        assert "keep_file_names_off" in d["log"], datei.name
