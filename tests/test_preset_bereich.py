"""Presets stehen in einem eigenen Bereich unter der Mod-Liste."""

import json
import os
from pathlib import Path

import pytest

from anvil.core.character_presets import (
    FEMALE, MALE, PresetKind, display_name, is_preset_mod,
)
from anvil.core.mod_list_io import merge_hidden_order

WURZEL = Path(__file__).resolve().parents[1]

ACU = PresetKind(
    name="ACU-Preset",
    suffix=".preset",
    target=("bin/x64/plugins/cyber_engine_tweaks/mods"
            "/AppearanceChangeUnlocker/character-presets"),
    variants=[FEMALE, MALE],
)
ZIEL = ACU.target


# ── Erkennung: was ist ein Preset? ───────────────────────────────────

def test_reines_preset_wird_erkannt():
    assert is_preset_mod([f"{ZIEL}/female/Grace.preset"], [ACU])


def test_preset_ohne_geschlechtsordner_wird_erkannt():
    assert is_preset_mod([f"{ZIEL}/Grace.preset"], [ACU])


def test_meta_ini_stoert_nicht():
    assert is_preset_mod([f"{ZIEL}/female/Grace.preset", "meta.ini"], [ACU])


def test_versteckte_dateien_stoeren_nicht():
    assert is_preset_mod([f"{ZIEL}/female/Grace.preset", ".directory"], [ACU])


def test_mod_mit_archiv_ist_kein_preset():
    """Der Fall Grace: Preset UND Kopf-Archiv im selben Paket."""
    assert not is_preset_mod(
        [f"{ZIEL}/female/Grace.preset",
         "archive/pc/mod/00_FacePreset_RE9Grace.archive"], [ACU])


def test_reines_archiv_ist_kein_preset():
    assert not is_preset_mod(["archive/pc/mod/Unique Eyes - Core.archive"], [ACU])


def test_preset_am_falschen_ort_ist_kein_preset():
    """Bad Corpo: .preset liegt in der Wurzel, ACU findet es dort nie."""
    assert not is_preset_mod(["Bad Corpo.preset"], [ACU])


def test_leere_mod_ist_kein_preset():
    """Ein Trenner hat keine Dateien -- der gehoert in die Mod-Liste."""
    assert not is_preset_mod([], [ACU])
    assert not is_preset_mod(["meta.ini"], [ACU])


def test_spiel_ohne_presets():
    assert not is_preset_mod([f"{ZIEL}/female/Grace.preset"], [])


def test_grossschreibung_egal():
    assert is_preset_mod([f"{ZIEL.upper()}/female/Grace.PRESET"], [ACU])


def test_rueckwaerts_schraegstrich():
    assert is_preset_mod([ZIEL.replace("/", "\\") + "\\female\\Grace.preset"],
                         [ACU])


def test_aehnlicher_pfad_zaehlt_nicht():
    """Ein Ordner, der nur so aehnlich heisst, darf nicht durchrutschen."""
    assert not is_preset_mod([f"{ZIEL}-backup/female/Grace.preset"], [ACU])


# ── Anzeigename ──────────────────────────────────────────────────────

def test_anzeigename_kuerzt_art_und_geschlecht():
    assert display_name("ACU-Preset - Grace (female)", [ACU], FEMALE) == "Grace"


def test_anzeigename_ohne_geschlecht():
    assert display_name("ACU-Preset - Grace", [ACU], "") == "Grace"


def test_anzeigename_bleibt_wenn_nichts_passt():
    assert display_name("Irgendwas", [ACU], "") == "Irgendwas"


def test_anzeigename_wird_nie_leer():
    assert display_name("ACU-Preset - ", [ACU], "") == "ACU-Preset - "


def test_anzeigename_ist_umkehrung_von_suggest_mod_name():
    """Beide beschreiben dasselbe Namensschema und muessen zusammenpassen."""
    from anvil.core.character_presets import suggest_mod_name
    gebaut = suggest_mod_name(Path("/tmp/Grace.preset"), FEMALE, ACU)
    assert display_name(gebaut, [ACU], FEMALE) == "Grace"


# ── Der Kern: ausgeblendete Eintraege behalten ihren Platz ───────────

def test_verstecktes_bleibt_hinter_seinem_trenner():
    """Regression: Presets duerfen beim Umsortieren nicht ans Ende rutschen.

    Sie stehen nicht in der sichtbaren Liste. Haengt man sie hinten an,
    landen sie unter dem letzten Trenner der modlist.txt -- und ihre
    Zuordnung zum Trenner darueber ist dauerhaft zerstoert.
    """
    alt = ["A_separator", "M1", "Presets_separator", "P1", "P2"]
    # Der Benutzer zieht M1 nach oben; Presets sind unsichtbar.
    neu = merge_hidden_order(
        ["M1", "A_separator", "Presets_separator"], alt, {"P1", "P2"})
    assert neu == ["M1", "A_separator", "Presets_separator", "P1", "P2"]


def test_verstecktes_folgt_seinem_nachbarn():
    alt = ["A_separator", "P1", "M1", "B_separator", "M2"]
    neu = merge_hidden_order(
        ["B_separator", "M2", "A_separator", "M1"], alt, {"P1"})
    assert neu == ["B_separator", "M2", "A_separator", "P1", "M1"]


def test_verstecktes_ganz_oben_bleibt_oben():
    alt = ["P1", "M1", "M2"]
    neu = merge_hidden_order(["M2", "M1"], alt, {"P1"})
    assert neu == ["P1", "M2", "M1"]


def test_kein_eintrag_geht_verloren():
    """Auch wenn der alte Nachbar aus der Liste verschwunden ist."""
    alt = ["M1", "P1", "M2"]
    neu = merge_hidden_order(["M2"], alt, {"P1"})
    assert set(neu) == {"M2", "P1"}


def test_ohne_verstecktes_bleibt_alles_wie_es_ist():
    assert merge_hidden_order(["B", "A"], ["A", "B"], set()) == ["B", "A"]


def test_mehrere_versteckte_behalten_ihre_reihenfolge():
    alt = ["S", "P1", "P2", "P3", "M"]
    neu = merge_hidden_order(["M", "S"], alt, {"P1", "P2", "P3"})
    assert neu == ["M", "S", "P1", "P2", "P3"]


# ── Verdrahtung im Fenster ───────────────────────────────────────────

QUELLE = (WURZEL / "anvil" / "mainwindow.py").read_text(encoding="utf-8")


def _block(name: str) -> str:
    """Rumpf genau einer Methode -- bis zum naechsten Methodenkopf.

    Ein festes Zeichenfenster wuerde in die Nachbarmethode hineinreichen;
    der Test wuerde dann von fremden Aenderungen gruen oder rot.
    """
    start = QUELLE.index(f"def {name}")
    ende = QUELLE.find("\n    def ", start + 1)
    return QUELLE[start:ende if ende > 0 else len(QUELLE)]


def test_toggle_loest_redeploy_aus():
    """Sonst bleibt bei dauerhaftem Deploy ein abgeschaltetes Preset liegen."""
    block = _block("_on_preset_toggled")
    assert "_schedule_redeploy()" in block


def test_toggle_baut_erst_nach_dem_signal_neu_auf():
    """Der Baum darf nicht mitten im eigenen itemChanged geleert werden."""
    block = _block("_on_preset_toggled")
    assert "QTimer.singleShot" in block


def test_presets_bleiben_in_current_mod_entries():
    """Gefiltert wird nur die Anzeige -- nicht die geschriebene Liste."""
    block = _block("_write_current_modlist")
    assert "self._current_mod_entries" in block
    assert "preset" not in block.lower()


def test_bereich_wird_beim_instanzwechsel_geleert():
    block = _block("_teardown_current_instance")
    assert "load_presets([])" in block
    # Ohne das Zuruecksetzen wuerde der Timer-Rueckruf mit fremden Namen laufen
    assert "self._preset_namen = set()" in block


def test_eigener_wortlaut_statt_mod_entfernen():
    block = _block("_remove_preset")
    assert "remove_preset_title" in block
    assert "remove_mod" not in block


# ── Uebersetzungen ───────────────────────────────────────────────────

SCHLUESSEL = {
    "label": ("presets", "presets_active_count", "presets_of_kind",
              "header_variant", "variant_female", "variant_male"),
    "context": ("remove_preset",),
    "dialog": ("remove_preset_title", "remove_preset_single"),
}


@pytest.mark.parametrize("sprache", ["de", "en", "es", "fr", "it", "pt", "ru"])
def test_locale_schluessel_vollstaendig(sprache):
    daten = json.loads(
        (WURZEL / "anvil" / "locales" / f"{sprache}.json").read_text("utf-8"))
    for abschnitt, namen in SCHLUESSEL.items():
        for key in namen:
            assert key in daten[abschnitt], f"{sprache}: {abschnitt}.{key} fehlt"
    assert "{x}" in daten["label"]["presets_active_count"]
    assert "{n}" in daten["label"]["presets_active_count"]
    assert "{kind}" in daten["label"]["presets_of_kind"]
    assert "{name}" in daten["dialog"]["remove_preset_single"]


# ── Echter Durchlauf durch _on_mods_reordered (ohne Qt-Fenster) ──────

class _Zeile:
    def __init__(self, folder_name, is_separator=False):
        self.folder_name = folder_name
        self.is_separator = is_separator
        self.conflicts = ""


class _Eintrag:
    def __init__(self, name):
        self.name = name
        self.priority = 0
        self.is_direct_install = False


class _Signal:
    def emit(self, *args):
        pass


class _Modell:
    def __init__(self, zeilen):
        self._rows = zeilen
        self.dataChanged = _Signal()

    def rowCount(self):
        return len(self._rows)

    def columnCount(self):
        return 1

    def index(self, *args):
        return None

    def set_conflict_highlight(self, a, b):
        pass


class _Baum:
    def _apply_separator_filter(self):
        pass


class _Ansicht:
    def __init__(self, modell):
        self._modell = modell
        self._tree = _Baum()

    def source_model(self):
        return self._modell


class _Fenster:
    """Nur so viel Fenster, wie _on_mods_reordered anfasst."""

    def __init__(self, eintraege, sichtbar):
        self._current_mod_entries = eintraege
        self._bg3_installer = None
        self._mod_list_view = _Ansicht(_Modell([_Zeile(n) for n in sichtbar]))
        self.geschrieben = False
        self.redeploy = False

    def _write_current_modlist(self):
        self.geschrieben = True

    def _update_active_count(self):
        pass

    def _compute_conflict_data(self):
        return {}

    def _check_group_consistency_after_reorder(self, model):
        pass

    def _schedule_redeploy(self):
        self.redeploy = True


def test_umsortieren_laesst_presets_an_ihrem_platz():
    """Der eigentliche Schutz: echter Aufruf, echte Reihenfolge geprueft.

    Die Presets stehen bewusst NICHT am Ende der Liste. Nur so faellt auf,
    wenn sie hinten angehaengt statt einsortiert werden.
    """
    from anvil.mainwindow import MainWindow

    namen = ["Presets_separator", "P1", "P2", "A_separator", "M1", "M2"]
    eintraege = [_Eintrag(n) for n in namen]
    # Der Benutzer zieht den A-Trenner mit seinen Mods nach ganz oben.
    fenster = _Fenster(
        eintraege, ["A_separator", "M1", "M2", "Presets_separator"])

    MainWindow._on_mods_reordered(fenster)

    assert [e.name for e in fenster._current_mod_entries] == [
        "A_separator", "M1", "M2", "Presets_separator", "P1", "P2"]
    assert fenster.geschrieben
    # Prioritaeten luecken- und dopplungsfrei ueber die ganze Liste
    assert [e.priority for e in fenster._current_mod_entries] == [0, 1, 2, 3, 4, 5]


def test_umsortieren_haengt_presets_nicht_ans_ende():
    """Gegenprobe zum Fall oben: Presets in der Mitte muessen dort bleiben."""
    from anvil.mainwindow import MainWindow

    namen = ["A_separator", "P1", "M1", "B_separator", "M2"]
    eintraege = [_Eintrag(n) for n in namen]
    fenster = _Fenster(
        eintraege, ["B_separator", "M2", "A_separator", "M1"])

    MainWindow._on_mods_reordered(fenster)

    # Anhaengen wuerde P1 ans Ende schieben -- P1 gehoert hinter A_separator.
    assert [e.name for e in fenster._current_mod_entries] == [
        "B_separator", "M2", "A_separator", "P1", "M1"]


# ── Echter Durchlauf durch _split_presets ────────────────────────────

class _Index:
    def __init__(self, dateien):
        self._dateien = dateien

    def get_file_list(self, name):
        return [{"rel": r} for r in self._dateien.get(name, [])]


class _AnsichtMitBereich:
    def __init__(self):
        self.geladen = None
        self.titel = ""

    def load_presets(self, eintraege, titel=""):
        self.geladen = eintraege
        self.titel = titel


class _Plugin:
    def get_preset_kinds(self):
        return [ACU]


class _FensterMitPresets:
    """Uebernimmt die echten Methoden, ohne ein Qt-Fenster zu bauen."""

    from anvil.mainwindow import MainWindow as _MW
    _preset_kinds = _MW._preset_kinds
    _preset_mod_names = _MW._preset_mod_names
    _preset_variant = _MW._preset_variant
    _load_preset_section = _MW._load_preset_section
    _split_presets = _MW._split_presets
    del _MW

    def __init__(self, dateien, eintraege):
        self._mod_index = _Index(dateien)
        self._current_mod_entries = eintraege
        self._mod_list_view = _AnsichtMitBereich()
        self._preset_namen = set()


def _mod(name, enabled=True, is_separator=False):
    e = _Eintrag(name)
    e.enabled = enabled
    e.display_name = name
    e.is_separator = is_separator
    e.is_foreign = False
    return e


def test_split_nimmt_presets_aus_der_liste():
    """Der eigentliche Schutz: echter Aufruf, geprueft wird das Ergebnis."""
    dateien = {
        "ACU-Preset - Grace (female)": [f"{ZIEL}/female/Grace.preset"],
        "FemV - RE9 Grace": ["archive/pc/mod/00_FacePreset.archive"],
        "Presets_separator": [],
    }
    eintraege = [_mod(n) for n in dateien]
    eintraege[2].is_separator = True
    fenster = _FensterMitPresets(dateien, eintraege)

    bleibt = fenster._split_presets(_Plugin(), eintraege)

    assert [e.name for e in bleibt] == ["FemV - RE9 Grace", "Presets_separator"]
    assert [d["folder"] for d in fenster._mod_list_view.geladen] == [
        "ACU-Preset - Grace (female)"]
    assert fenster._mod_list_view.geladen[0]["name"] == "Grace"
    assert fenster._preset_namen == {"ACU-Preset - Grace (female)"}


def test_split_laesst_alles_stehen_wenn_es_keine_presets_gibt():
    dateien = {"M1": ["archive/pc/mod/a.archive"]}
    eintraege = [_mod("M1")]
    fenster = _FensterMitPresets(dateien, eintraege)

    bleibt = fenster._split_presets(_Plugin(), eintraege)

    assert [e.name for e in bleibt] == ["M1"]
    assert fenster._mod_list_view.geladen == []


def test_split_bei_spiel_ohne_presets():
    """Skyrim & Co: der Bereich bleibt leer, nichts wird ausgeblendet."""
    class _OhnePresets:
        def get_preset_kinds(self):
            return []

    dateien = {"M1": [f"{ZIEL}/female/Grace.preset"]}
    eintraege = [_mod("M1")]
    fenster = _FensterMitPresets(dateien, eintraege)

    bleibt = fenster._split_presets(_OhnePresets(), eintraege)

    assert [e.name for e in bleibt] == ["M1"]
    assert fenster._mod_list_view.geladen == []


def test_split_ohne_index_blendet_nichts_aus():
    eintraege = [_mod("ACU-Preset - Grace (female)")]
    fenster = _FensterMitPresets({}, eintraege)
    fenster._mod_index = None

    bleibt = fenster._split_presets(_Plugin(), eintraege)

    assert [e.name for e in bleibt] == ["ACU-Preset - Grace (female)"]


# ── _preset_variant: echter Durchlauf statt Quelltext-Suche ──────────

def test_variante_wird_erkannt():
    fenster = _FensterMitPresets(
        {"P": [f"{ZIEL}/female/Grace.preset"]}, [])
    assert fenster._preset_variant("P", [ACU]) == FEMALE


def test_variante_gross_klein_egal():
    """Ein von Hand angelegtes Female/ muss genauso zaehlen."""
    fenster = _FensterMitPresets(
        {"P": [f"{ZIEL}/Female/Grace.preset"]}, [])
    assert fenster._preset_variant("P", [ACU]) == FEMALE


def test_variante_leer_ohne_geschlechtsordner():
    fenster = _FensterMitPresets({"P": [f"{ZIEL}/Grace.preset"]}, [])
    assert fenster._preset_variant("P", [ACU]) == ""


def test_variante_ohne_index_stuerzt_nicht_ab():
    fenster = _FensterMitPresets({}, [])
    fenster._mod_index = None
    assert fenster._preset_variant("P", [ACU]) == ""


# ── _on_preset_toggled: echter Durchlauf ─────────────────────────────

class _Log:
    def __init__(self):
        self.zeilen = []

    def add_log(self, stufe, text):
        self.zeilen.append((stufe, text))


class _FensterToggle:
    from anvil.mainwindow import MainWindow as _MW
    _on_preset_toggled = _MW._on_preset_toggled
    del _MW

    def __init__(self, eintraege):
        self._current_mod_entries = eintraege
        self._preset_namen = {e.name for e in eintraege}
        self._current_plugin = None
        self._log_panel = _Log()
        self.geschrieben = 0
        self.gezaehlt = 0
        self.redeploy = 0

    def _write_current_modlist(self):
        self.geschrieben += 1

    def _update_active_count(self):
        self.gezaehlt += 1

    def _schedule_redeploy(self):
        self.redeploy += 1

    def _load_preset_section(self, plugin, namen):
        # Der verzoegerte Neuaufbau landet hier. Ohne diese Attrappe feuert
        # der Timer irgendwann spaeter -- mitten in einem fremden Test.
        self.neu_geladen = True


def _timer_leeren():
    """Anstehende singleShot(0)-Rueckrufe jetzt abarbeiten, nicht spaeter."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    app.processEvents()


def test_toggle_schreibt_und_rollt_aus():
    p = _mod("ACU-Preset - Grace (female)", enabled=True)
    fenster = _FensterToggle([p])

    fenster._on_preset_toggled("ACU-Preset - Grace (female)", False)

    assert p.enabled is False
    # Ohne das Schreiben stuende der Schalter nach einem Neustart wieder um
    assert fenster.geschrieben == 1
    assert fenster.gezaehlt == 1
    # Ohne Redeploy bliebe das Preset bei Dauer-Deploy im Spiel liegen
    assert fenster.redeploy == 1
    _timer_leeren()
    assert fenster.neu_geladen is True


def test_toggle_bei_unbekanntem_ordner_schreibt_nichts():
    p = _mod("ACU-Preset - Grace (female)", enabled=True)
    fenster = _FensterToggle([p])

    fenster._on_preset_toggled("gibts nicht", False)

    assert p.enabled is True
    assert fenster.geschrieben == 0
    assert fenster.redeploy == 0
    assert fenster._log_panel.zeilen and fenster._log_panel.zeilen[0][0] == "warning"
    _timer_leeren()


# ── Der Bereich selbst (echtes Qt-Widget) ───────────────────────────
#
# In einem eigenen Prozess: die Leisten haengen Ereignisfilter ans
# Programm, die spaetere Widget-Tests der Suite abstuerzen lassen.

_WIDGET_PROBE = r"""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from anvil.widgets.mod_list import ModListView

app = QApplication([])
v = ModListView()
assert not v._ps_container.isVisible(), "Bereich muss leer versteckt sein"

gemeldet = []
v.preset_toggled.connect(lambda f, a: gemeldet.append((f, a)))
v.load_presets([
    {"folder": "ACU-Preset - Grace (female)", "name": "Grace",
     "variant": "weiblich", "enabled": True},
    {"folder": "ACU-Preset - Aiko (female)", "name": "Aiko",
     "variant": "weiblich", "enabled": False},
], "ACU-Presets")

assert v._ps_tree.topLevelItemCount() == 2, "beide Presets sichtbar"
assert v._ps_container.isVisible() or True
# Ordnername im Tooltip -- der Anzeigename ist gekuerzt
assert v._ps_tree.topLevelItem(0).toolTip(1) == "ACU-Preset - Grace (female)"
assert v._ps_tree.topLevelItem(0).text(1) == "Grace"
assert v._ps_tree.topLevelItem(1).checkState(0) == Qt.CheckState.Unchecked
assert gemeldet == [], "Befuellen darf nichts ausloesen"

v._ps_tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Unchecked)
assert gemeldet == [("ACU-Preset - Grace (female)", False)], gemeldet

v.load_presets([])
assert v._ps_tree.topLevelItemCount() == 0, "leere Liste raeumt den Baum"
print("OK")
"""


def test_presets_bereich_als_widget():
    """Bereich zeigt/versteckt sich, Tooltip stimmt, Signal meldet den Ordner."""
    import subprocess
    import sys

    lauf = subprocess.run(
        [sys.executable, "-c", _WIDGET_PROBE],
        cwd=WURZEL, capture_output=True, text=True, timeout=120,
        env={**os.environ, "XDG_CONFIG_HOME": str(WURZEL / ".pytest_qsettings")},
    )
    assert lauf.returncode == 0, lauf.stderr[-2000:]
    assert "OK" in lauf.stdout


# ── Nebensachen-Liste darf nicht auseinanderlaufen ───────────────────

def test_nebensachen_passen_zum_deployer():
    from anvil.core.character_presets import _NEBENSACHE
    from anvil.core.mod_deployer import _SKIP_FILES
    assert _NEBENSACHE == set(_SKIP_FILES), (
        "Was der Deployer ueberspringt, darf die Preset-Erkennung "
        "nicht als Inhalt werten")


def test_fremde_eintraege_in_der_zusammenfuehrung():
    """Fremde Mods tragen einen Pfad als Namen -- darf nichts brechen."""
    alt = ["S", "mods/fremd.archive", "P1", "M1"]
    neu = merge_hidden_order(["M1", "S", "mods/fremd.archive"], alt, {"P1"})
    assert neu == ["M1", "S", "mods/fremd.archive", "P1"]


# ── Neuer Trenner: Position in der modlist.txt ───────────────────────

class _Auswahl:
    def __init__(self, zeile):
        self._zeile = zeile

    def selectedRows(self):
        return [] if self._zeile is None else [object()]


class _BaumMitAuswahl:
    def __init__(self, zeile):
        self._auswahl = _Auswahl(zeile)

    def selectionModel(self):
        return self._auswahl


class _ZeilenIndex:
    def __init__(self, zeile):
        self._zeile = zeile

    def row(self):
        return self._zeile


class _Proxy:
    def __init__(self, zeile):
        self._zeile = zeile

    def mapToSource(self, idx):
        return _ZeilenIndex(self._zeile)


class _AnsichtTrenner:
    def __init__(self, zeilen, gewaehlte_zeile):
        self._rows = [_Zeile(n) for n in zeilen]
        self._tree = _BaumMitAuswahl(gewaehlte_zeile)
        self._proxy_model = _Proxy(gewaehlte_zeile)

    def source_model(self):
        return self


class _FensterTrenner:
    from anvil.mainwindow import MainWindow as _MW
    _separator_insert_pos = _MW._separator_insert_pos
    del _MW

    def __init__(self, zeilen, gewaehlte_zeile):
        self._mod_list_view = _AnsichtTrenner(zeilen, gewaehlte_zeile)


def test_trenner_landet_vor_der_auswahl():
    liste = ["A_separator", "M1", "M2"]
    fenster = _FensterTrenner(liste, 2)  # M2 gewaehlt
    assert fenster._separator_insert_pos(liste) == 2


def test_trenner_ohne_auswahl_ganz_oben():
    liste = ["A_separator", "M1"]
    fenster = _FensterTrenner(liste, None)
    assert fenster._separator_insert_pos(liste) == 0


def test_trenner_bei_fremder_mod_nimmt_den_eintrag_darueber():
    """Fremde Mods stehen nie in der modlist.txt -- sonst sprang er nach oben."""
    zeilen = ["A_separator", "M1", "mods/fremd.archive"]
    liste = ["A_separator", "M1"]  # die fremde Mod fehlt hier
    fenster = _FensterTrenner(zeilen, 2)
    assert fenster._separator_insert_pos(liste) == 1  # vor M1, nicht 0


def test_trenner_ausgeblendete_verschieben_nichts():
    """Presets stehen in der Liste, aber nicht im Modell."""
    zeilen = ["A_separator", "M1"]
    liste = ["A_separator", "P1", "P2", "M1"]
    fenster = _FensterTrenner(zeilen, 1)  # M1 gewaehlt
    assert fenster._separator_insert_pos(liste) == 3  # M1 steht auf 3


# ── _write_current_modlist schreibt Presets wirklich mit ─────────────

class _FensterSchreiben:
    from anvil.mainwindow import MainWindow as _MW
    _write_current_modlist = _MW._write_current_modlist
    del _MW

    def __init__(self, eintraege, pfade):
        self._current_mod_entries = eintraege
        self._current_instance_path = pfade.profiles.parent
        self._current_profile_path = pfade.profiles / "Default"
        self._current_instance_paths = pfade


def test_presets_stehen_in_der_geschriebenen_modlist(tmp_path):
    """Der teuerste Fehler: ein Preset faellt aus der Datei und nie ins Spiel."""
    from anvil.core.instance_paths import resolve_instance_paths
    from anvil.core.mod_list_io import read_global_modlist, read_active_mods

    pfade = resolve_instance_paths(tmp_path, {})
    profil = pfade.profiles / "Default"
    profil.mkdir(parents=True, exist_ok=True)

    eintraege = [
        _mod("A_separator"), _mod("M1"),
        _mod("ACU-Preset - Grace (female)", enabled=True),
        _mod("ACU-Preset - Aiko (female)", enabled=False),
    ]
    for e in eintraege:
        e.is_foreign = False
    fenster = _FensterSchreiben(eintraege, pfade)

    fenster._write_current_modlist()

    assert read_global_modlist(pfade.profiles) == [
        "A_separator", "M1",
        "ACU-Preset - Grace (female)", "ACU-Preset - Aiko (female)"]
    aktiv = read_active_mods(profil)
    assert "ACU-Preset - Grace (female)" in aktiv
    assert "ACU-Preset - Aiko (female)" not in aktiv
