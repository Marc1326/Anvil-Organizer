"""Wen der Aufraeum-Dialog anbieten darf -- und wen auf keinen Fall.

Gemessen an Marcs Cyberpunk-Instanz: unter dem Trenner "Presets" hingen
19 Eintraege. Davon sind 7 echte Presets, 10 Frameworks, eines ein
verirrtes Preset (Bad Corpo) und genau eines wirklich fehl am Platz
(Fiore -- eine Textdatei mit Einstellungen zum Nachbauen).

Frameworks duerfen niemals dabei sein: sie werden getrennt verwaltet,
stehen gar nicht in der Mod-Liste, und ihre Position in der modlist.txt
ist ihr Ladeindex. Sie zu verschieben hiesse, an der Ladereihenfolge von
RED4ext, redscript und ArchiveXL zu drehen.
"""

from __future__ import annotations

from anvil.mainwindow import MainWindow

SEP = "Presets_separator"

# So sah es bei Marc wirklich aus.
ECHTE_LISTE = [
    "a_separator", "Irgendeine Mod",
    SEP,
    "ACU-Preset - Mona Chains (female)",
    "ACU-Preset - Grace (female)",
    "Bad Corpo",
    "Fiore",
    "ArchiveXL",
    "CET 1.37.1 - Scripting fixes",
    "RED4ext",
    "redscript",
]
PRESETS = {"ACU-Preset - Mona Chains (female)", "ACU-Preset - Grace (female)"}
FRAMEWORKS = {"ArchiveXL", "CET 1.37.1 - Scripting fixes", "RED4ext", "redscript"}
VERIRRT = {"Bad Corpo": ["Bad Corpo.preset"]}


class _Eintrag:
    def __init__(self, name, is_direct_install=False):
        self.name = name
        self.is_direct_install = is_direct_install


class _Fenster:
    """Nur die Teile, die die Auswahl anfasst."""

    _sammler_kinder = MainWindow._sammler_kinder
    _tidy_kandidaten = MainWindow._tidy_kandidaten

    def __init__(self, presets=PRESETS, verirrt=VERIRRT, frameworks=FRAMEWORKS):
        self._preset_namen = set(presets)
        self._stray_presets_of = dict(verirrt)
        self._current_mod_entries = [
            _Eintrag(n, is_direct_install=n in frameworks)
            for n in ECHTE_LISTE
        ]


def test_nur_fiore_bleibt_uebrig() -> None:
    """Der Kern: von 8 Eintraegen unter dem Trenner bleibt genau einer."""
    assert _Fenster()._tidy_kandidaten(ECHTE_LISTE, SEP) == ["Fiore"]


def test_frameworks_werden_nie_angeboten() -> None:
    """Ihre Position ist ihr Ladeindex -- Verschieben waere gefaehrlich."""
    kandidaten = _Fenster()._tidy_kandidaten(ECHTE_LISTE, SEP)
    for fw in FRAMEWORKS:
        assert fw not in kandidaten, f"{fw} ist ein Framework"


def test_verirrtes_preset_wird_nicht_angeboten() -> None:
    """Bad Corpo IST ein Preset -- es liegt nur falsch.

    Es gehoert ueber "Preset einsortieren" repariert, danach steht es im
    Presets-Bereich. In den Auffang-Trenner waere es doppelt falsch.
    """
    assert "Bad Corpo" not in _Fenster()._tidy_kandidaten(ECHTE_LISTE, SEP)


def test_echte_presets_bleiben_stehen() -> None:
    kandidaten = _Fenster()._tidy_kandidaten(ECHTE_LISTE, SEP)
    for p in PRESETS:
        assert p not in kandidaten


def test_nichts_ausserhalb_des_trenners() -> None:
    """Was ueber dem Trenner steht, geht die Aufraeumung nichts an."""
    kandidaten = _Fenster()._tidy_kandidaten(ECHTE_LISTE, SEP)
    assert "Irgendeine Mod" not in kandidaten
    assert "a_separator" not in kandidaten


def test_ohne_fremdkoerper_gibt_es_nichts_zu_tun() -> None:
    order = ["a_separator", "Mod A", SEP, "ACU-Preset - Grace (female)"]
    fenster = _Fenster(presets={"ACU-Preset - Grace (female)"}, verirrt={})
    assert fenster._tidy_kandidaten(order, SEP) == []


def test_unbekannter_trenner_liefert_nichts() -> None:
    assert _Fenster()._tidy_kandidaten(ECHTE_LISTE, "GibtsNicht_separator") == []


def test_trenner_am_listenende() -> None:
    order = ["a_separator", "Mod A", SEP]
    assert _Fenster(presets=set(), verirrt={})._tidy_kandidaten(order, SEP) == []


def test_naechster_trenner_beendet_die_gruppe() -> None:
    order = [SEP, "Fiore", "z_separator", "Andere Mod"]
    fenster = _Fenster(presets=set(), verirrt={}, frameworks=set())
    assert fenster._tidy_kandidaten(order, SEP) == ["Fiore"]
