"""Anvil sagt, wofuer die Reihenfolge im Spiel ueberhaupt gilt.

Oben in der Liste heisst hoechste Prioritaet -- bei losen Dateien immer,
bei gepackten Archiven nur dort, wo Anvil beim Ausrollen durchnummeriert.
Bisher sah die Prioritaets-Spalte bei jedem Spiel gleich aus, auch wo sie
fuer Archive nichts bewirkt.

Der Konflikte-Bereich behauptete sogar „Gruen = dieses Archiv gewinnt" --
bei Spielen ohne Nummerierung ist das schlicht falsch.
"""

from __future__ import annotations

import json
from pathlib import Path

from anvil.core.load_order_scope import (
    KEINE,
    TEILWEISE,
    VOLL,
    OrderScope,
    scope_for,
    scope_saetze,
    scope_tooltip,
)
from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game
from anvil.plugins.games.game_skyrimse import SkyrimSEGame
from anvil.plugins.games.game_stalker2 import Stalker2Game
from anvil.plugins.games.game_stellarblade import StellarBladeGame

# Nicht vom Arbeitsverzeichnis abhaengen: pytest laesst sich aus jedem
# Ordner starten.
_WURZEL = Path(__file__).resolve().parent.parent


# ── Die Einstufung ───────────────────────────────────────────────────


def test_cyberpunk_nummeriert_in_einem_ordner() -> None:
    s = scope_for(Cyberpunk2077Game)
    assert s.art == TEILWEISE
    assert "archive/pc/mod" in s.ordner
    assert s.archive_folgen_der_liste is True


def test_cyberpunk_nennt_die_uebrigen_ordner() -> None:
    """Der Bericht sagte „vollstaendig" -- das Plugin gibt genau einen
    Ordner frei. REDmod-Archive bleiben ausdruecklich unberuehrt.
    """
    s = scope_for(Cyberpunk2077Game)
    assert s.rest, "kein einziger Ordner ohne Nummerierung genannt"
    assert "archive/pc/mod" not in s.rest


def test_stalker2_nummeriert_nur_in_mods() -> None:
    s = scope_for(Stalker2Game)
    assert s.art == TEILWEISE
    assert s.ordner == ["Stalker2/Content/Paks/~mods"]
    assert any("LogicMods" in r for r in s.rest), (
        f"LogicMods fehlt in der Restliste: {s.rest}"
    )


def test_stellarblade_nummeriert_nicht() -> None:
    s = scope_for(StellarBladeGame)
    assert s.art == KEINE
    assert s.archive_folgen_der_liste is False


def test_skyrim_hat_eine_eigene_plugin_liste() -> None:
    s = scope_for(SkyrimSEGame)
    assert s.art == KEINE
    assert s.eigene_plugin_liste is True


def test_cyberpunk_hat_keine_plugin_liste() -> None:
    assert scope_for(Cyberpunk2077Game).eigene_plugin_liste is False


def test_ohne_plugin_wird_nichts_behauptet() -> None:
    """Vorsichtige Annahme -- lieber zu wenig versprechen."""
    s = scope_for(None)
    assert s.art == KEINE
    assert s.archive_folgen_der_liste is False


def test_unterordner_gilt_als_abgedeckt() -> None:
    class _Spiel:
        GamePakLoadOrderDirs = ["Content/Paks"]
        GameModDirs = ["Content/Paks/~mods", "Binaries/Win64"]

    s = scope_for(_Spiel)
    assert s.rest == ["Binaries/Win64"], (
        f"~mods liegt unter Content/Paks und ist abgedeckt: {s.rest}"
    )


def test_prefix_ohne_ordner_gilt_ueberall() -> None:
    class _Spiel:
        GamePakLoadOrderPrefix = True

    assert scope_for(_Spiel).art == VOLL


def test_backslashes_werden_vereinheitlicht() -> None:
    class _Spiel:
        GamePakLoadOrderDirs = ["Content\\Paks\\~mods"]

    assert scope_for(_Spiel).ordner == ["Content/Paks/~mods"]


# ── Die Saetze ───────────────────────────────────────────────────────


def test_ohne_nummerierung_wird_gewarnt() -> None:
    text = " ".join(scope_saetze(scope_for(StellarBladeGame)))
    assert "lose" in text.lower()


def test_bei_nummerierung_werden_die_ordner_genannt() -> None:
    text = " ".join(scope_saetze(scope_for(Cyberpunk2077Game)))
    assert "archive/pc/mod" in text


def test_bethesda_bekommt_den_plugin_hinweis() -> None:
    text = " ".join(scope_saetze(scope_for(SkyrimSEGame)))
    assert ".esp" in text


def test_cyberpunk_bekommt_den_plugin_hinweis_nicht() -> None:
    text = " ".join(scope_saetze(scope_for(Cyberpunk2077Game)))
    assert ".esp" not in text


def test_tooltip_hat_kopf_und_inhalt() -> None:
    t = scope_tooltip(Cyberpunk2077Game)
    assert "\n" in t
    assert "archive/pc/mod" in t


def test_kein_schluessel_bleibt_unuebersetzt() -> None:
    """tr() gibt bei fehlendem Schluessel den Schluessel zurueck."""
    for plugin in (Cyberpunk2077Game, Stalker2Game, StellarBladeGame,
                   SkyrimSEGame, None):
        t = scope_tooltip(plugin)
        assert "order_scope." not in t, f"unuebersetzt bei {plugin}: {t}"


def test_alle_sprachen_kennen_die_texte() -> None:
    noetig = {"tooltip_head", "numbered_all", "numbered_dirs",
              "numbered_rest", "not_numbered", "bethesda_plugins"}
    for datei in sorted((_WURZEL / "anvil/locales").glob("*.json")):
        d = json.loads(datei.read_text(encoding="utf-8"))
        fehlt = noetig - set(d.get("order_scope", {}))
        assert not fehlt, f"{datei.name}: {fehlt}"
        assert "archive_winner_unsure" in d["mod_detail"], datei.name
        assert "archive_winner_numbered" in d["mod_detail"], datei.name


def test_platzhalter_stimmen_in_allen_sprachen() -> None:
    """Ein fehlendes {dirs} wuerde den Ordner still verschlucken."""
    for datei in sorted((_WURZEL / "anvil/locales").glob("*.json")):
        os_ = json.loads(datei.read_text(encoding="utf-8"))["order_scope"]
        assert "{dirs}" in os_["numbered_dirs"], datei.name
        assert "{rest}" in os_["numbered_rest"], datei.name


# ── Der Spaltenkopf ──────────────────────────────────────────────────


def test_spaltenkopf_liefert_einen_tooltip() -> None:
    from PySide6.QtCore import Qt

    from anvil.models.mod_list_model import COL_PRIORITY, ModListModel

    m = ModListModel()
    m.set_load_order_plugin(StellarBladeGame)
    text = m.headerData(COL_PRIORITY, Qt.Orientation.Horizontal,
                        Qt.ItemDataRole.ToolTipRole)

    assert text, "kein Tooltip auf der Prioritaets-Spalte"
    assert "lose" in text.lower()


def test_andere_spalten_haben_keinen_tooltip() -> None:
    from PySide6.QtCore import Qt

    from anvil.models.mod_list_model import COL_NAME, ModListModel

    m = ModListModel()
    m.set_load_order_plugin(StellarBladeGame)
    assert m.headerData(COL_NAME, Qt.Orientation.Horizontal,
                        Qt.ItemDataRole.ToolTipRole) is None


def test_spaltenkopf_zeigt_weiterhin_seinen_namen() -> None:
    """Die Erweiterung darf die Beschriftung nicht verschlucken."""
    from PySide6.QtCore import Qt

    from anvil.models.mod_list_model import COL_PRIORITY, ModListModel

    m = ModListModel()
    text = m.headerData(COL_PRIORITY, Qt.Orientation.Horizontal,
                        Qt.ItemDataRole.DisplayRole)
    assert text


def test_tooltip_folgt_dem_spielwechsel() -> None:
    from PySide6.QtCore import Qt

    from anvil.models.mod_list_model import COL_PRIORITY, ModListModel

    m = ModListModel()
    m.set_load_order_plugin(StellarBladeGame)
    ohne = m.headerData(COL_PRIORITY, Qt.Orientation.Horizontal,
                        Qt.ItemDataRole.ToolTipRole)
    m.set_load_order_plugin(Cyberpunk2077Game)
    mit = m.headerData(COL_PRIORITY, Qt.Orientation.Horizontal,
                       Qt.ItemDataRole.ToolTipRole)

    assert ohne != mit
    assert "archive/pc/mod" in mit


# ── Der Diagnose-Bericht ─────────────────────────────────────────────


def test_bericht_nennt_die_einstufung() -> None:
    from anvil.core.diagnostics import build_report

    text = build_report({}, [], [], game_plugin=Cyberpunk2077Game)

    assert "[Ladereihenfolge]" in text
    assert "archive/pc/mod" in text


def test_bericht_ohne_plugin_bleibt_wie_bisher() -> None:
    from anvil.core.diagnostics import build_report

    assert "[Ladereihenfolge]" not in build_report({}, [], [])


# ── Der Konflikte-Bereich ────────────────────────────────────────────


def test_falscher_gruen_satz_steht_nicht_mehr_im_grundtext() -> None:
    """„Gruen = dieses Archiv gewinnt" stimmt nur mit Nummerierung."""
    d = json.loads((_WURZEL / "anvil/locales/de.json").read_text(encoding="utf-8"))
    assert "Grün" not in d["mod_detail"]["archive_conflicts_hint"]


def _konflikt_hinweis(plugin) -> str:
    """Baut den Hinweistext genau so zusammen wie der Dialog.

    Der Dialog selbst braucht einen laufenden Qt-Stack; die Zusammen-
    setzung ist aber genau die Stelle, an der frueher eine falsche
    Aussage stand -- die wird hier gemessen.
    """
    import re

    from anvil.core.load_order_scope import scope_for as sf
    from anvil.core.translator import tr

    quelle = (_WURZEL / "anvil/dialogs/mod_detail_dialog.py").read_text(
        encoding="utf-8",
    )
    assert "archive_winner_numbered" in quelle, (
        "der Dialog unterscheidet nicht mehr nach Spiel"
    )
    assert re.search(r"scope_for\(game_plugin\)", quelle), (
        "der Dialog fragt das Spiel nicht mehr"
    )

    nummeriert = sf(plugin).archive_folgen_der_liste
    return (tr("mod_detail.archive_conflicts_hint") + " "
            + tr("mod_detail.archive_winner_numbered" if nummeriert
                 else "mod_detail.archive_winner_unsure"))


def test_konflikt_hinweis_bei_nummerierung() -> None:
    text = _konflikt_hinweis(Cyberpunk2077Game)
    assert "Grün" in text, f"der Gewinner-Satz fehlt: {text}"


def test_konflikt_hinweis_ohne_nummerierung_behauptet_nichts() -> None:
    """Frueher stand hier „Grün = dieses Archiv gewinnt" -- bei diesen
    Spielen ist das falsch.
    """
    text = _konflikt_hinweis(StellarBladeGame)
    assert "Grün" not in text, f"falsche Aussage steht wieder da: {text}"
    assert "Spiel selbst" in text


def test_beide_konflikt_saetze_sind_uebersetzt() -> None:
    for plugin in (Cyberpunk2077Game, StellarBladeGame, SkyrimSEGame):
        text = _konflikt_hinweis(plugin)
        assert "mod_detail." not in text, f"unuebersetzt: {text}"
        assert text.strip()


# ── Die Hinweiszeile unter der Liste ─────────────────────────────────


class _Zeile:
    def __init__(self):
        self.sichtbar = None

    def setVisible(self, an):
        self.sichtbar = an


class _Text:
    def __init__(self):
        self.text = ""

    def setText(self, t):
        self.text = t


class _Einstellungen:
    def __init__(self, versteckt=False):
        self.werte = {}
        self.versteckt = versteckt

    def value(self, key, default=None, type=None):
        return self.werte.get(key, self.versteckt)

    def setValue(self, key, wert):
        self.werte[key] = wert


def _fenster(plugin, versteckt=False):
    from anvil.mainwindow import MainWindow

    class _F:
        _update_order_hint = MainWindow._update_order_hint
        _hide_order_hint = MainWindow._hide_order_hint
        _order_hint_key = MainWindow._order_hint_key

        def __init__(self):
            self._current_plugin = plugin
            self._order_hint = _Zeile()
            self._order_hint_label = _Text()
            self._einst = _Einstellungen(versteckt)

        def _settings(self):
            return self._einst

    return _F()


def test_zeile_erscheint_wo_die_reihenfolge_nicht_ankommt() -> None:
    f = _fenster(StellarBladeGame)
    f._update_order_hint()

    assert f._order_hint.sichtbar is True
    assert "lose" in f._order_hint_label.text.lower()


def test_zeile_bleibt_weg_wo_nummeriert_wird() -> None:
    """Bei Cyberpunk kommt die Reihenfolge an -- kein Grund zu warnen."""
    f = _fenster(Cyberpunk2077Game)
    f._update_order_hint()

    assert f._order_hint.sichtbar is False


def test_zeile_bleibt_weg_wenn_weggeklickt() -> None:
    f = _fenster(StellarBladeGame, versteckt=True)
    f._update_order_hint()

    assert f._order_hint.sichtbar is False


def test_wegklicken_wird_pro_spiel_gemerkt() -> None:
    f = _fenster(StellarBladeGame)
    f._hide_order_hint()

    assert f._order_hint.sichtbar is False
    schluessel = list(f._einst.werte)[0]
    assert getattr(StellarBladeGame, "GameShortName", "") in schluessel, (
        f"Schluessel ohne Spielkennung: {schluessel}"
    )


def test_zwei_spiele_stoeren_sich_nicht() -> None:
    a = _fenster(StellarBladeGame)._order_hint_key()
    b = _fenster(SkyrimSEGame)._order_hint_key()
    assert a != b


# ── Die Datenklasse ──────────────────────────────────────────────────


def test_scope_ist_unveraenderlich() -> None:
    """Sonst koennte eine Anzeige die Einstufung fuer alle anderen
    verstellen -- genau das soll das Modul verhindern.
    """
    import dataclasses

    s = OrderScope()
    try:
        s.art = VOLL
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("OrderScope laesst sich veraendern")
