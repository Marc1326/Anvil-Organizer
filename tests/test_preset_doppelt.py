"""Dasselbe Preset darf nicht zweimal als Mod entstehen.

Wird ein Preset-Paket ein zweites Mal installiert, war der Name schon
vergeben. Anvil haengte dann stumpf die Dateigroesse an::

    ACU-Preset - Bad Corpo (female)
    ACU-Preset - Bad Corpo (female) (1155)

Beide Ordner enthielten dieselbe Datei, byteweise identisch, und rollten
sie an dieselbe Stelle aus. Geprueft wurde nie, ob es dasselbe Preset
ist -- nur, ob der Name frei war.

Verglichen wird ueber den **Inhalt**: dasselbe Preset wandert unter
verschiedenen Dateinamen durch die Nexus-Pakete.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from anvil.core.character_presets import (
    FEMALE,
    build_mod,
    installed_presets,
    preset_fingerprint,
    target_path,
)
from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game

ACU = Cyberpunk2077Game().get_preset_kinds()[0]


def _preset(pfad: Path, inhalt: str = "LocKey#123:0\n") -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(inhalt, encoding="utf-8")
    return pfad


# ── Fingerabdruck ────────────────────────────────────────────────────


def test_gleicher_inhalt_gleicher_abdruck(tmp_path: Path) -> None:
    a = _preset(tmp_path / "a.preset")
    b = _preset(tmp_path / "anders_benannt.preset")
    assert preset_fingerprint(a) == preset_fingerprint(b), (
        "der Name darf keine Rolle spielen"
    )


def test_anderer_inhalt_anderer_abdruck(tmp_path: Path) -> None:
    a = _preset(tmp_path / "a.preset", "LocKey#1:0\n")
    b = _preset(tmp_path / "b.preset", "LocKey#2:0\n")
    assert preset_fingerprint(a) != preset_fingerprint(b)


def test_fehlende_datei_liefert_leer(tmp_path: Path) -> None:
    assert preset_fingerprint(tmp_path / "gibtsnicht.preset") == ""


# ── Was schon installiert ist ────────────────────────────────────────


def test_findet_installiertes_preset(tmp_path: Path) -> None:
    mods = tmp_path / ".mods"
    quelle = _preset(tmp_path / "Bad Corpo.preset")
    build_mod(quelle, mods, "ACU-Preset - Bad Corpo (female)", ACU, FEMALE)

    bekannt = installed_presets(mods, ACU)
    assert bekannt.get(preset_fingerprint(quelle)) == "ACU-Preset - Bad Corpo (female)"


def test_gleiches_preset_unter_anderem_dateinamen_wird_erkannt(tmp_path: Path) -> None:
    """Der wichtige Fall: Nexus benennt Dateien gern um."""
    mods = tmp_path / ".mods"
    build_mod(_preset(tmp_path / "BadCorpo_v2.preset"), mods,
              "ACU-Preset - BadCorpo_v2 (female)", ACU, FEMALE)

    neue = _preset(tmp_path / "neu" / "Bad Corpo.preset")
    bekannt = installed_presets(mods, ACU)
    assert preset_fingerprint(neue) in bekannt


def test_anderes_preset_gilt_nicht_als_doppelt(tmp_path: Path) -> None:
    mods = tmp_path / ".mods"
    build_mod(_preset(tmp_path / "eins.preset", "LocKey#1:0\n"), mods,
              "ACU-Preset - eins (female)", ACU, FEMALE)

    anderes = _preset(tmp_path / "zwei.preset", "LocKey#2:0\n")
    assert preset_fingerprint(anderes) not in installed_presets(mods, ACU)


def test_leerer_mod_ordner_liefert_nichts(tmp_path: Path) -> None:
    assert installed_presets(tmp_path / "gibtsnicht", ACU) == {}


def test_presets_ausserhalb_des_zielpfads_zaehlen_nicht(tmp_path: Path) -> None:
    """Ein verirrtes Preset ist noch nicht einsortiert -- es zaehlt nicht."""
    mods = tmp_path / ".mods"
    mod = mods / "Bad Corpo"
    mod.mkdir(parents=True)
    _preset(mod / "Bad Corpo.preset")

    assert installed_presets(mods, ACU) == {}


def test_mehrere_presets_werden_alle_erfasst(tmp_path: Path) -> None:
    mods = tmp_path / ".mods"
    for i in range(3):
        build_mod(_preset(tmp_path / f"p{i}.preset", f"LocKey#{i}:0\n"), mods,
                  f"ACU-Preset - p{i} (female)", ACU, FEMALE)
    assert len(installed_presets(mods, ACU)) == 3


def test_liegt_wirklich_am_zielpfad(tmp_path: Path) -> None:
    """Gegenprobe zum Aufbau, den build_mod anlegt."""
    mods = tmp_path / ".mods"
    build_mod(_preset(tmp_path / "x.preset"), mods,
              "ACU-Preset - x (female)", ACU, FEMALE)
    erwartet = mods / "ACU-Preset - x (female)" / target_path(ACU, FEMALE, "x.preset")
    assert erwartet.is_file()


# ── Einbau im Hauptfenster ───────────────────────────────────────────


def test_installationsweg_prueft_auf_doppelte() -> None:
    import inspect

    from anvil.mainwindow import MainWindow

    quelle = inspect.getsource(MainWindow._install_presets_from)
    assert "installed_presets" in quelle
    assert "preset_fingerprint" in quelle
    assert "already_installed" in quelle


def test_neu_angelegtes_wird_sofort_mitgezaehlt() -> None:
    """Ein Paket mit zweimal demselben Preset darf es nur einmal anlegen."""
    import inspect

    from anvil.mainwindow import MainWindow

    quelle = inspect.getsource(MainWindow._install_presets_from)
    assert "bekannt[abdruck] = name" in quelle, (
        "sonst legt ein Paket mit zwei gleichen Presets beide an"
    )


def test_schluessel_in_allen_sprachen() -> None:
    ordner = Path(__file__).parents[1] / "anvil" / "locales"
    for sprache in ("de", "en", "es", "fr", "it", "pt", "ru"):
        daten = json.loads((ordner / f"{sprache}.json").read_text(encoding="utf-8"))
        eins = daten["preset"]["already_installed"]
        alle = daten["preset"]["all_already_installed"]
        assert "{file}" in eins and "{mod}" in eins, sprache
        assert "{count}" in alle, sprache


# ── Der echte Installationsweg ───────────────────────────────────────


class _Protokoll:
    def __init__(self):
        self.zeilen = []

    def add_log(self, art, text):
        self.zeilen.append((art, text))


class _Leiste:
    def __init__(self):
        self.texte = []

    def showMessage(self, text, _ms=0):
        self.texte.append(text)


class _Fenster:
    """MainWindow-Ersatz mit genau dem, was die Installation anfasst."""

    from anvil.mainwindow import MainWindow as _MW
    _install_presets_from = _MW._install_presets_from
    del _MW

    def __init__(self, tmp_path):
        from anvil.core.instance_paths import resolve_instance_paths

        self._current_instance_path = tmp_path
        self._current_instance_paths = resolve_instance_paths(tmp_path, {})
        (tmp_path / ".mods").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".profiles" / "Default").mkdir(parents=True, exist_ok=True)
        self._current_profile_path = tmp_path / ".profiles" / "Default"
        self._current_plugin = Cyberpunk2077Game()
        self._log_panel = _Protokoll()
        self._leiste = _Leiste()
        self._neu_geladen = 0

    def _preset_separator(self):
        return "Presets_separator"

    def _ask_preset_separator(self):
        return "Presets_separator"

    def _ask_preset_variant(self, _name, _kind):
        return FEMALE

    def _write_preset_origin(self, _mod_dir, _archive):
        pass

    def _reload_mod_list(self):
        self._neu_geladen += 1

    def statusBar(self):
        return self._leiste


def _paket(tmp_path: Path, name: str, inhalt: str = "LocKey#123:0\n") -> Path:
    """Ein entpacktes Paket mit genau einer Preset-Datei."""
    temp = tmp_path / f"temp_{name}"
    _preset(temp / f"{name}.preset", inhalt)
    return temp


def _preset_mods(fenster) -> list[str]:
    mods = fenster._current_instance_paths.mods
    return sorted(d.name for d in mods.iterdir() if d.is_dir())


def test_zweite_installation_legt_keinen_zweiten_ordner_an(tmp_path: Path) -> None:
    """Der gemeldete Fall, Ende zu Ende."""
    fenster = _Fenster(tmp_path)

    fenster._install_presets_from(
        _paket(tmp_path, "Bad Corpo"), Path("Bad Corpo-5277.zip"))
    nach_erstem = _preset_mods(fenster)
    assert len(nach_erstem) == 1, nach_erstem

    fenster._install_presets_from(
        _paket(tmp_path, "Bad Corpo"), Path("Bad Corpo-5277.zip"))
    nach_zweitem = _preset_mods(fenster)

    assert nach_zweitem == nach_erstem, (
        f"zweiter Ordner entstanden: {nach_zweitem}"
    )
    # Gezielt auf das Zahlen-Anhaengsel pruefen -- "(female)" gehoert
    # zum normalen Namen.
    assert not any(re.search(r"\(\d+\)$", n) for n in nach_zweitem), (
        f"Groessen-Anhaengsel wie (1155) ist zurueck: {nach_zweitem}"
    )


def test_zweite_installation_sagt_es_im_protokoll(tmp_path: Path) -> None:
    fenster = _Fenster(tmp_path)
    fenster._install_presets_from(_paket(tmp_path, "Bad Corpo"), Path("a.zip"))
    fenster._log_panel.zeilen.clear()

    fenster._install_presets_from(_paket(tmp_path, "Bad Corpo"), Path("a.zip"))

    texte = " ".join(t for _, t in fenster._log_panel.zeilen)
    assert "Bad Corpo.preset" in texte and "bereits installiert" in texte, texte


def test_anderes_preset_wird_weiterhin_installiert(tmp_path: Path) -> None:
    """Die Bremse darf nicht zu viel bremsen."""
    fenster = _Fenster(tmp_path)
    fenster._install_presets_from(
        _paket(tmp_path, "Bad Corpo", "LocKey#1:0\n"), Path("a.zip"))
    fenster._install_presets_from(
        _paket(tmp_path, "Fiore", "LocKey#2:0\n"), Path("b.zip"))

    assert len(_preset_mods(fenster)) == 2, _preset_mods(fenster)


def test_gleiches_preset_unter_anderem_dateinamen(tmp_path: Path) -> None:
    fenster = _Fenster(tmp_path)
    fenster._install_presets_from(_paket(tmp_path, "Bad Corpo"), Path("a.zip"))
    # Gleicher Inhalt, anderer Dateiname -- Nexus benennt gern um.
    fenster._install_presets_from(_paket(tmp_path, "BadCorpo_v2"), Path("b.zip"))

    assert len(_preset_mods(fenster)) == 1, _preset_mods(fenster)


def test_paket_mit_zweimal_demselben_preset(tmp_path: Path) -> None:
    """Zwei gleiche Presets in EINEM Paket -- nur eines darf entstehen."""
    fenster = _Fenster(tmp_path)
    temp = tmp_path / "temp_doppelt"
    _preset(temp / "Bad Corpo.preset")
    _preset(temp / "unterordner" / "Bad Corpo Kopie.preset")

    fenster._install_presets_from(temp, Path("a.zip"))

    assert len(_preset_mods(fenster)) == 1, _preset_mods(fenster)


def test_doppeltes_preset_bleibt_nicht_im_temp_liegen(tmp_path: Path) -> None:
    """Sonst wandert es als gewoehnliche Mod mit."""
    fenster = _Fenster(tmp_path)
    fenster._install_presets_from(_paket(tmp_path, "Bad Corpo"), Path("a.zip"))

    temp = _paket(tmp_path, "Bad Corpo")
    fenster._install_presets_from(temp, Path("a.zip"))

    assert not list(temp.rglob("*.preset")), "Preset liegt noch im Temp-Ordner"
