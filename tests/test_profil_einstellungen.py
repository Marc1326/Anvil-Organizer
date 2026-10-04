"""Spiel-Einstellungen pro Profil (#114).

Die Checkbox "Lokale INIs" wurde nur gespeichert -- beim Profilwechsel
blieben die Optionen des Spiels einfach liegen. Jetzt wandern die
Einstellungsdateien mit dem Profil.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from anvil.core.profile_settings import (
    OWNER_MARKER,
    SETTINGS_DIR,
    local_inis_enabled,
    read_owner,
    rename_owner,
    switch_profile_settings,
)
from anvil.plugins.games.game_baldursgate3 import BaldursGate3Game
from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game
from anvil.plugins.games.game_fallout4 import Fallout4Game
from anvil.plugins.games.game_skyrimse import SkyrimSEGame
from anvil.plugins.games.game_starfield import StarfieldGame


def _spiel(tmp_path: Path) -> tuple[list[Path], Path, Path]:
    live = tmp_path / "Spiel"
    live.mkdir()
    dateien = [live / "Prefs.ini", live / "config.lsf"]
    for d in dateien:
        d.write_text("Original")
    a = tmp_path / "profiles" / "Default"
    b = tmp_path / "profiles" / "Neu"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    return dateien, a, b


def test_szenario_aus_dem_issue(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    prefs = dateien[0]

    prefs.write_text("A: an")
    switch_profile_settings(dateien, a, b)
    # Neues Profil startet mit den aktuellen Einstellungen
    assert prefs.read_text() == "A: an"
    assert (a / SETTINGS_DIR / "Prefs.ini").read_text() == "A: an"
    assert (b / SETTINGS_DIR / "Prefs.ini").read_text() == "A: an"

    prefs.write_text("B: aus")
    switch_profile_settings(dateien, b, a)
    assert prefs.read_text() == "A: an"
    assert (b / SETTINGS_DIR / "Prefs.ini").read_text() == "B: aus"

    switch_profile_settings(dateien, a, b)
    assert prefs.read_text() == "B: aus"


def test_gleiches_profil_tauscht_nichts(tmp_path):
    dateien, a, _ = _spiel(tmp_path)
    # Beim echten Wechsel sind es verschiedene Path-Objekte
    switch_profile_settings(dateien, a, Path(str(a)) / ".." / a.name)
    assert not (a / SETTINGS_DIR).exists()


def test_besitzer_wird_gemerkt(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    switch_profile_settings(dateien, a, b)
    assert read_owner(dateien) == b.resolve()


def test_uebersprungener_tausch_legt_nichts_falsch_ab(tmp_path):
    """Wechsel A->B wurde uebersprungen (Spiel lief): live gehoert noch A."""
    dateien, a, b = _spiel(tmp_path)
    c = tmp_path / "profiles" / "Drei"
    c.mkdir()
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B-eigen")
    switch_profile_settings(dateien, None, a)  # A besitzt live
    dateien[0].write_text("A-neu")
    # Anvil steht jetzt auf B, der Tausch dorthin fand nie statt
    switch_profile_settings(dateien, b, c)
    assert (b / SETTINGS_DIR / "Prefs.ini").read_text() == "B-eigen"
    assert (a / SETTINGS_DIR / "Prefs.ini").read_text() == "A-neu"


def test_besitzer_ist_schon_das_ziel(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    switch_profile_settings(dateien, a, b)
    dateien[0].write_text("B-im-Spiel")
    # Spielstart: aktives Profil B besitzt live schon
    switch_profile_settings(dateien, b, b)
    assert dateien[0].read_text() == "B-im-Spiel"


def test_start_holt_fremde_einstellungen_zurueck(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    switch_profile_settings(dateien, a, b)     # B besitzt
    dateien[0].write_text("B-im-Spiel")
    (a / SETTINGS_DIR / "Prefs.ini").write_text("A-eigen")
    # Start in Profil A (z. B. andere Instanz desselben Spiels)
    switch_profile_settings(dateien, a, a)
    assert dateien[0].read_text() == "A-eigen"
    assert (b / SETTINGS_DIR / "Prefs.ini").read_text() == "B-im-Spiel"
    assert read_owner(dateien) == a.resolve()


def test_umbenennen_folgt_dem_besitzer(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    switch_profile_settings(dateien, a, b)
    neu = b.with_name("Umbenannt")
    b.rename(neu)
    rename_owner(dateien, b, neu)
    assert read_owner(dateien) == neu.resolve()
    dateien[0].write_text("B-geaendert")
    switch_profile_settings(dateien, neu, a)
    assert (neu / SETTINGS_DIR / "Prefs.ini").read_text() == "B-geaendert"


def test_umbenennen_fremder_profile_aendert_nichts(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    switch_profile_settings(dateien, a, b)
    rename_owner(dateien, a, a.with_name("X"))
    assert read_owner(dateien) == b.resolve()


def test_fehlende_livedatei_ist_kein_fehler(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    dateien[1].unlink()
    assert switch_profile_settings(dateien, a, b) == []
    assert not (a / SETTINGS_DIR / "config.lsf").exists()


def test_fehlender_spielordner_ist_kein_fehler(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "x.ini").write_text("B")
    weg = tmp_path / "gibtsnicht" / "x.ini"
    assert switch_profile_settings([dateien[0], weg], a, b) == []


def test_teilfehler_beim_laden_rollt_zurueck(tmp_path, monkeypatch):
    dateien, a, b = _spiel(tmp_path)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")
    (b / SETTINGS_DIR / "config.lsf").write_text("B")
    switch_profile_settings(dateien, None, a)  # A besitzt

    import anvil.core.profile_settings as ps
    echtes_copy2 = ps.shutil.copy2

    def copy2(src, dst, *k, **kw):
        if Path(dst).name.startswith("config.lsf") and Path(dst).parent == dateien[1].parent:
            raise OSError("schreibgeschuetzt")
        return echtes_copy2(src, dst, *k, **kw)

    monkeypatch.setattr(ps.shutil, "copy2", copy2)
    assert switch_profile_settings(dateien, a, b)
    # Kein Mischsatz: alles wieder wie vorher, A bleibt Besitzer
    assert dateien[0].read_text() == "Original"
    assert dateien[1].read_text() == "Original"
    assert read_owner(dateien) == a.resolve()
    assert not list(dateien[0].parent.glob("*.anvil_tmp"))


def test_marker_fehler_entfernt_alten_besitzer(tmp_path, monkeypatch):
    dateien, a, b = _spiel(tmp_path)
    switch_profile_settings(dateien, None, a)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")

    import anvil.core.profile_settings as ps

    def kaputt(_files, _profile):
        raise OSError("Rechte")

    monkeypatch.setattr(ps, "_write_owner", kaputt)
    assert switch_profile_settings(dateien, a, b)
    assert dateien[0].read_text() == "B"
    # A darf nicht mehr als Besitzer gelten, sonst bekaeme A B's Werte
    assert not (dateien[0].parent / OWNER_MARKER).exists()


def test_geloeschtes_profil_kommt_nicht_zurueck(tmp_path):
    import shutil

    dateien, a, b = _spiel(tmp_path)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")
    shutil.rmtree(a)
    assert switch_profile_settings(dateien, a, b) == []
    assert not a.exists()
    assert dateien[0].read_text() == "B"


def test_ohne_dateien_passiert_nichts(tmp_path):
    _, a, b = _spiel(tmp_path)
    assert switch_profile_settings([], a, b) == []
    assert not (a / SETTINGS_DIR).exists()
    assert not (b / SETTINGS_DIR).exists()


def test_ohne_altes_profil_wird_nur_geladen(tmp_path):
    dateien, _, b = _spiel(tmp_path)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")
    switch_profile_settings(dateien, None, b)
    assert dateien[0].read_text() == "B"


def test_datei_die_das_profil_nie_hatte_wird_entfernt(tmp_path):
    """Sonst wandert z. B. eine erst spaeter angelegte Custom.ini ins fremde Profil."""
    dateien, a, b = _spiel(tmp_path)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")
    switch_profile_settings(dateien, a, b)
    assert dateien[0].read_text() == "B"
    assert not dateien[1].exists()
    # A behaelt seine Datei und bekommt sie beim Zurueckwechseln wieder
    assert (a / SETTINGS_DIR / "config.lsf").read_text() == "Original"
    switch_profile_settings(dateien, b, a)
    assert dateien[1].read_text() == "Original"
    assert not (b / SETTINGS_DIR / "config.lsf").exists()


def test_custom_ini_aus_b_landet_nicht_in_a(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    c = tmp_path / "profiles" / "Drei"
    c.mkdir()
    dateien[1].unlink()
    switch_profile_settings(dateien, None, a)
    switch_profile_settings(dateien, a, b)
    dateien[1].write_text("B-custom")
    switch_profile_settings(dateien, b, a)
    switch_profile_settings(dateien, a, c)
    assert not (a / SETTINGS_DIR / "config.lsf").exists()
    assert (b / SETTINGS_DIR / "config.lsf").read_text() == "B-custom"


def test_verlinkte_datei_ohne_kopie_bleibt(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    echt = tmp_path / "woanders.lsf"
    echt.write_text("verlinkt")
    dateien[1].unlink()
    dateien[1].symlink_to(echt)
    (b / SETTINGS_DIR).mkdir()
    switch_profile_settings(dateien, a, b)
    assert echt.read_text() == "verlinkt"
    assert dateien[1].is_symlink()


def test_symlink_bleibt_erhalten(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    echt = tmp_path / "woanders.ini"
    echt.write_text("Original")
    dateien[0].unlink()
    dateien[0].symlink_to(echt)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")
    switch_profile_settings(dateien, a, b)
    assert dateien[0].is_symlink()
    assert echt.read_text() == "B"


def test_speicherfehler_laedt_nichts_neues(tmp_path, monkeypatch):
    dateien, a, b = _spiel(tmp_path)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")

    import anvil.core.profile_settings as ps
    echtes_copy2 = ps.shutil.copy2

    def copy2(src, dst, *k, **kw):
        # Nur das Sichern nach A scheitert, Laden aus B wuerde klappen
        if Path(dst).parent == a / SETTINGS_DIR:
            raise OSError("Platte voll")
        return echtes_copy2(src, dst, *k, **kw)

    monkeypatch.setattr(ps.shutil, "copy2", copy2)
    fehler = switch_profile_settings(dateien, a, b)
    assert fehler
    # Ungesicherte Aenderungen duerfen nicht ueberschrieben werden
    assert dateien[0].read_text() == "Original"
    assert read_owner(dateien) is None
    assert not list((a / SETTINGS_DIR).glob("*.anvil_tmp"))


def test_halb_geschriebene_datei_bleibt_unberuehrt(tmp_path, monkeypatch):
    dateien, a, b = _spiel(tmp_path)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")

    import anvil.core.profile_settings as ps
    echtes_replace = ps.os.replace

    def replace(src, dst):
        if Path(dst).parent == dateien[0].parent:
            raise OSError("Rechte")
        return echtes_replace(src, dst)

    monkeypatch.setattr(ps.os, "replace", replace)
    fehler = switch_profile_settings(dateien, a, b)
    assert fehler
    assert dateien[0].read_text() == "Original"
    assert not list(dateien[0].parent.glob("*.anvil_tmp"))


@pytest.mark.parametrize("wert, erwartet", [
    (None, True), ("true", True), (True, True), ("1", True),
    ("false", False), (False, False), ("0", False),
])
def test_checkbox(wert, erwartet):
    idata = {} if wert is None else {"local_inis": wert}
    assert local_inis_enabled(idata) is erwartet


def test_ohne_instanzdaten_gilt_die_anzeige():
    assert local_inis_enabled(None) is True


# ── Welche Dateien die Spiele melden ──────────────────────────────────


def _mit_dokumenten(cls, docs: Path):
    plugin = cls.__new__(cls)
    plugin.gameDocumentsDirectory = lambda: docs
    return plugin


@pytest.mark.parametrize("cls, namen", [
    (SkyrimSEGame, ["Skyrim.ini", "SkyrimPrefs.ini", "SkyrimCustom.ini"]),
    (Fallout4Game, ["Fallout4.ini", "Fallout4Prefs.ini", "Fallout4Custom.ini"]),
    (StarfieldGame, ["StarfieldPrefs.ini", "StarfieldCustom.ini"]),
])
def test_bethesda_ini_im_dokumente_ordner(tmp_path, cls, namen):
    plugin = _mit_dokumenten(cls, tmp_path)
    assert plugin.profileSettingsFiles() == [tmp_path / n for n in namen]


def test_bethesda_ohne_prefix(tmp_path):
    plugin = _mit_dokumenten(SkyrimSEGame, None)
    assert plugin.profileSettingsFiles() == []


def test_bg3_nur_optionen_nie_modliste(tmp_path):
    docs = tmp_path / "Baldur's Gate 3"
    profil = docs / "PlayerProfiles" / "Public"
    profil.mkdir(parents=True)
    plugin = _mit_dokumenten(BaldursGate3Game, docs)
    plugin.modsettings_path = lambda: profil / "modsettings.lsx"
    dateien = plugin.profileSettingsFiles()
    assert dateien == [
        docs / "graphicSettings.lsx",
        profil / "config.lsf",
        profil / "inputconfig_p1.json",
    ]
    namen = {d.name for d in dateien}
    assert "modsettings.lsx" not in namen
    assert "profile8.lsf" not in namen
    assert not any("Savegames" in str(d) for d in dateien)


def test_bg3_ohne_prefix(tmp_path):
    plugin = _mit_dokumenten(BaldursGate3Game, None)
    plugin.modsettings_path = lambda: None
    assert plugin.profileSettingsFiles() == []


def test_andere_spiele_tauschen_nichts(tmp_path):
    plugin = _mit_dokumenten(Cyberpunk2077Game, tmp_path)
    assert plugin.profileSettingsFiles() == []


# ── Einbindung in den Profilwechsel ───────────────────────────────────


def _fenster(tmp_path, *, laeuft=False, laeuft_extern=False, local_inis="true",
             dateien=None):
    from anvil.mainwindow import MainWindow

    meldungen = []
    fenster = SimpleNamespace(
        _current_plugin=SimpleNamespace(profileSettingsFiles=lambda: dateien or []),
        _game_running=laeuft,
        _game_panel=SimpleNamespace(is_game_running=lambda: laeuft_extern,
                                    ini_restored=lambda: True),
        instance_manager=SimpleNamespace(
            current_instance=lambda: "Spiel",
            load_instance=lambda _n: {"local_inis": local_inis},
        ),
        statusBar=lambda: SimpleNamespace(
            showMessage=lambda text, _ms: meldungen.append(text)),
    )
    fenster._profile_settings_files = lambda: MainWindow._profile_settings_files(fenster)
    fenster._purge_left_clean_settings = (
        lambda p: MainWindow._purge_left_clean_settings(fenster, p))
    fenster._swap = lambda alt, neu: MainWindow._swap_profile_settings(fenster, alt, neu)
    return fenster, meldungen


def test_fenster_tauscht(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")
    fenster, _ = _fenster(tmp_path, dateien=dateien)
    fenster._swap(a, b)
    assert dateien[0].read_text() == "B"


def test_fenster_checkbox_aus(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")
    fenster, _ = _fenster(tmp_path, local_inis="false", dateien=dateien)
    fenster._swap(a, b)
    assert dateien[0].read_text() == "Original"
    assert not (a / SETTINGS_DIR).exists()


def test_fenster_spiel_laeuft(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")
    fenster, _ = _fenster(tmp_path, laeuft=True, dateien=dateien)
    fenster._swap(a, b)
    assert dateien[0].read_text() == "Original"


def test_fenster_meldet_fehler(tmp_path, monkeypatch):
    dateien, a, b = _spiel(tmp_path)
    import anvil.core.profile_settings as ps

    def kaputt(*_a, **_k):
        raise OSError("Platte voll")

    monkeypatch.setattr(ps.shutil, "copy2", kaputt)
    fenster, meldungen = _fenster(tmp_path, dateien=dateien)
    fenster._swap(a, b)
    assert len(meldungen) == 1


class _Einstellungen:
    def value(self, *_a, **_k):
        return False


def _wechsel_fenster(tmp_path, dateien, *, purge, bg3=False, laeuft=False,
                     ini_ok=True, plugin=True):
    from anvil.mainwindow import MainWindow

    instanz = tmp_path / "Instanz"
    (instanz / ".profiles" / "Default").mkdir(parents=True)
    (instanz / ".profiles" / "Neu").mkdir(parents=True)
    ablauf = []

    def silent_purge():
        ablauf.append("purge")
        return purge

    def swap(alt, neu, purge=None):
        ablauf.append("swap")
        MainWindow._swap_profile_settings(fenster, alt, neu, purge=purge)

    fenster = SimpleNamespace(
        _current_instance_path=instanz,
        _current_profile_path=instanz / ".profiles" / "Default",
        _bg3_installer=SimpleNamespace(_state_file_path=lambda: None) if bg3 else None,
        _bg3_save_separators=lambda: None,
        _bg3_reload_mod_list=lambda: None,
        _current_mod_entries=[],
        _settings=lambda: _Einstellungen(),
        _group_manager=SimpleNamespace(load=lambda _p: None,
                                       cleanup_orphans=lambda _f: None),
        instance_manager=SimpleNamespace(
            current_instance=lambda: "Spiel",
            load_instance=lambda _n: {"local_inis": "true"},
            save_instance=lambda _n, _d: None,
        ),
        _apply_active_state=lambda _a: None,
        _redeploy_timer=SimpleNamespace(stop=lambda: None),
        _game_running=laeuft,
        _game_panel=SimpleNamespace(
            is_game_running=lambda: False,
            silent_purge=silent_purge,
            ini_restored=lambda: ini_ok,
            set_instance_path=lambda *_a, **_k: None,
            silent_deploy=lambda: ablauf.append("deploy"),
            take_forced_launch=lambda: False,
            game_state=lambda: None,
        ),
        _sync_separator_deploy_paths=lambda: None,
        _sync_keep_file_name_mods=lambda: None,
        _auto_relock_instance=lambda *_a: None,
        _log_game_dir_state=lambda _t: None,
        keeps_mods_deployed=lambda: True,
        _current_plugin=(SimpleNamespace(profileSettingsFiles=lambda: dateien)
                         if plugin else None),
        statusBar=lambda: SimpleNamespace(showMessage=lambda *_a: None),
    )
    fenster._swap_profile_settings = swap
    fenster._profile_settings_files = lambda: MainWindow._profile_settings_files(fenster)
    fenster._purge_left_clean_settings = (
        lambda p: MainWindow._purge_left_clean_settings(fenster, p))
    neu = instanz / ".profiles" / "Neu"
    (neu / SETTINGS_DIR).mkdir()
    (neu / SETTINGS_DIR / "Prefs.ini").write_text("Neu")
    return fenster, ablauf, MainWindow._on_profile_changed


def test_wechsel_tauscht_nach_purge_und_vor_deploy(tmp_path):
    dateien, _, _ = _spiel(tmp_path)
    fenster, ablauf, wechsel = _wechsel_fenster(
        tmp_path, dateien, purge=SimpleNamespace(success=True))
    wechsel(fenster, "Neu")
    assert ablauf == ["purge", "swap", "deploy"]
    assert dateien[0].read_text() == "Neu"
    alt = tmp_path / "Instanz" / ".profiles" / "Default" / SETTINGS_DIR / "Prefs.ini"
    assert alt.read_text() == "Original"


def test_wechsel_ohne_deployer(tmp_path):
    dateien, _, _ = _spiel(tmp_path)
    fenster, _, wechsel = _wechsel_fenster(tmp_path, dateien, purge=None)
    wechsel(fenster, "Neu")
    assert dateien[0].read_text() == "Neu"


def test_wechsel_purge_fehlgeschlagen(tmp_path):
    dateien, _, _ = _spiel(tmp_path)
    fenster, ablauf, wechsel = _wechsel_fenster(
        tmp_path, dateien, purge=SimpleNamespace(success=False))
    wechsel(fenster, "Neu")
    assert dateien[0].read_text() == "Original"
    assert read_owner(dateien) is None


def test_wechsel_custom_ini_nicht_zurueckgestellt(tmp_path):
    dateien, _, _ = _spiel(tmp_path)
    fenster, ablauf, wechsel = _wechsel_fenster(
        tmp_path, dateien, purge=SimpleNamespace(success=True), ini_ok=False)
    wechsel(fenster, "Neu")
    assert dateien[0].read_text() == "Original"
    assert read_owner(dateien) is None


def test_wechsel_aufs_selbe_profil(tmp_path):
    dateien, _, _ = _spiel(tmp_path)
    fenster, _, wechsel = _wechsel_fenster(tmp_path, dateien, purge=None)
    wechsel(fenster, "Neu")
    dateien[0].write_text("im Spiel geaendert")
    wechsel(fenster, "Neu")
    assert dateien[0].read_text() == "im Spiel geaendert"


def test_wechsel_nach_loeschen_des_aktiven_profils(tmp_path):
    import shutil

    dateien, _, _ = _spiel(tmp_path)
    fenster, _, wechsel = _wechsel_fenster(tmp_path, dateien, purge=None)
    alt = fenster._current_profile_path
    shutil.rmtree(alt)
    wechsel(fenster, "Neu")
    assert not alt.exists()
    assert dateien[0].read_text() == "Neu"


def test_wechsel_ohne_plugin(tmp_path):
    dateien, _, _ = _spiel(tmp_path)
    fenster, _, wechsel = _wechsel_fenster(tmp_path, dateien, purge=None, plugin=False)
    wechsel(fenster, "Neu")
    assert dateien[0].read_text() == "Original"


def test_plugin_fehler_bricht_nicht_ab(tmp_path):
    from anvil.mainwindow import MainWindow

    def kaputt():
        raise OSError("Prefix weg")

    fenster = SimpleNamespace(_current_plugin=SimpleNamespace(profileSettingsFiles=kaputt))
    assert MainWindow._profile_settings_files(fenster) == []


def test_wechsel_bg3(tmp_path):
    dateien, _, _ = _spiel(tmp_path)
    fenster, ablauf, wechsel = _wechsel_fenster(tmp_path, dateien, purge=None, bg3=True)
    wechsel(fenster, "Neu")
    assert ablauf == ["swap"]
    assert dateien[0].read_text() == "Neu"


def test_wechsel_bg3_spiel_laeuft(tmp_path):
    dateien, _, _ = _spiel(tmp_path)
    fenster, _, wechsel = _wechsel_fenster(
        tmp_path, dateien, purge=None, bg3=True, laeuft=True)
    wechsel(fenster, "Neu")
    assert dateien[0].read_text() == "Original"


def test_fenster_spiel_ausserhalb_gestartet(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")
    fenster, _ = _fenster(tmp_path, laeuft_extern=True, dateien=dateien)
    fenster._swap(a, b)
    assert dateien[0].read_text() == "Original"


# ── Spielstart ────────────────────────────────────────────────────────


def _start(fenster):
    from anvil.mainwindow import MainWindow
    return MainWindow._predeploy_for_launch(fenster, "test")


def test_start_gibt_dem_aktiven_profil_seine_einstellungen(tmp_path):
    dateien, _, _ = _spiel(tmp_path)
    fenster, ablauf, _ = _wechsel_fenster(tmp_path, dateien, purge=None)
    neu = fenster._current_instance_path / ".profiles" / "Neu"
    alt = fenster._current_profile_path
    switch_profile_settings(dateien, None, alt)  # Default besitzt live
    # Anvil steht auf "Neu", der Tausch dorthin wurde uebersprungen
    fenster._current_profile_path = neu
    assert _start(fenster) is True
    assert ablauf == ["purge", "swap", "deploy"]
    assert dateien[0].read_text() == "Neu"
    assert (alt / SETTINGS_DIR / "Prefs.ini").read_text() == "Original"


def test_start_ohne_besitzer_aendert_nichts(tmp_path):
    dateien, _, _ = _spiel(tmp_path)
    fenster, _, _ = _wechsel_fenster(tmp_path, dateien, purge=None)
    fenster._current_profile_path = fenster._current_instance_path / ".profiles" / "Neu"
    dateien[0].write_text("im Spiel geaendert")
    assert _start(fenster) is True
    # Ohne Marker gehoert live dem aktiven Profil -- nichts ueberschreiben
    assert dateien[0].read_text() == "im Spiel geaendert"


def test_start_custom_ini_nicht_zurueckgestellt(tmp_path):
    dateien, _, _ = _spiel(tmp_path)
    fenster, ablauf, _ = _wechsel_fenster(tmp_path, dateien, purge=None, ini_ok=False)
    switch_profile_settings(dateien, None, fenster._current_profile_path)
    fenster._current_profile_path = fenster._current_instance_path / ".profiles" / "Neu"
    _start(fenster)
    assert dateien[0].read_text() == "Original"


# ── Runde-2-Luecken ───────────────────────────────────────────────────


def test_geloeschte_instanz_landet_nicht_im_fremden_profil(tmp_path):
    import shutil

    live = tmp_path / "Spiel"
    live.mkdir()
    dateien = [live / "Prefs.ini"]
    dateien[0].write_text("X-Werte")
    x = tmp_path / "SkyrimX" / ".profiles" / "Default"
    y = tmp_path / "SkyrimY" / ".profiles" / "Default"
    zwei = tmp_path / "SkyrimY" / ".profiles" / "Zwei"
    for d in (x, y, zwei):
        d.mkdir(parents=True)
    (y / SETTINGS_DIR).mkdir()
    (y / SETTINGS_DIR / "Prefs.ini").write_text("Y-eigene")
    switch_profile_settings(dateien, None, x)
    shutil.rmtree(tmp_path / "SkyrimX")
    switch_profile_settings(dateien, y, y)  # Start aus Y
    assert dateien[0].read_text() == "Y-eigene"
    switch_profile_settings(dateien, y, zwei)
    assert (y / SETTINGS_DIR / "Prefs.ini").read_text() == "Y-eigene"


def test_spielende_sichert_ins_profil(tmp_path):
    from anvil.core.profile_settings import save_to_owner

    dateien, a, b = _spiel(tmp_path)
    switch_profile_settings(dateien, None, a)
    dateien[0].write_text("im Spiel geaendert")
    assert save_to_owner(dateien) == []
    assert (a / SETTINGS_DIR / "Prefs.ini").read_text() == "im Spiel geaendert"
    # Danach darf die Instanz umziehen, ohne dass etwas verloren geht
    a.parent.rename(tmp_path / "verschoben")
    a2 = tmp_path / "verschoben" / a.name
    switch_profile_settings(dateien, a2, a2)
    assert dateien[0].read_text() == "im Spiel geaendert"


def test_spielende_ohne_besitzer_sichert_nichts(tmp_path):
    from anvil.core.profile_settings import save_to_owner

    dateien, a, _ = _spiel(tmp_path)
    assert save_to_owner(dateien) == []
    assert not (a / SETTINGS_DIR).exists()


def test_rollback_entfernt_neu_angelegte_datei(tmp_path, monkeypatch):
    dateien, a, b = _spiel(tmp_path)
    dateien[0].unlink()
    switch_profile_settings(dateien, None, a)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")
    (b / SETTINGS_DIR / "config.lsf").write_text("B")

    import anvil.core.profile_settings as ps
    echtes_copy2 = ps.shutil.copy2

    def copy2(src, dst, *k, **kw):
        if Path(dst).name.startswith("config.lsf") and Path(dst).parent == dateien[1].parent:
            raise OSError("schreibgeschuetzt")
        return echtes_copy2(src, dst, *k, **kw)

    monkeypatch.setattr(ps.shutil, "copy2", copy2)
    assert switch_profile_settings(dateien, a, b)
    assert not dateien[0].exists()
    assert dateien[1].read_text() == "Original"


def test_rollback_bringt_entfernte_datei_zurueck(tmp_path, monkeypatch):
    dateien, a, b = _spiel(tmp_path)
    switch_profile_settings(dateien, None, a)
    (b / SETTINGS_DIR).mkdir()
    # B hat nur config.lsf: Prefs.ini wird entfernt, dann scheitert config.lsf
    (b / SETTINGS_DIR / "config.lsf").write_text("B")

    import anvil.core.profile_settings as ps
    echtes_copy2 = ps.shutil.copy2

    def copy2(src, dst, *k, **kw):
        if Path(dst).name.startswith("config.lsf") and Path(dst).parent == dateien[1].parent:
            raise OSError("schreibgeschuetzt")
        return echtes_copy2(src, dst, *k, **kw)

    monkeypatch.setattr(ps.shutil, "copy2", copy2)
    assert switch_profile_settings(dateien, a, b)
    assert dateien[0].read_text() == "Original"


def test_ohne_dokumente_ordner_kein_fehler(tmp_path):
    _, a, b = _spiel(tmp_path)
    weg = tmp_path / "nie-gestartet"
    assert switch_profile_settings([weg / "Prefs.ini"], a, b) == []
    assert not weg.exists()


def test_sichern_raeumt_tmp_auf(tmp_path, monkeypatch):
    dateien, a, b = _spiel(tmp_path)
    import anvil.core.profile_settings as ps
    echtes_replace = ps.os.replace

    def replace(src, dst):
        if Path(dst).parent == a / SETTINGS_DIR:
            raise OSError("Rechte")
        return echtes_replace(src, dst)

    monkeypatch.setattr(ps.os, "replace", replace)
    assert switch_profile_settings(dateien, a, b)
    assert not list((a / SETTINGS_DIR).glob("*.anvil_tmp"))
    assert dateien[0].read_text() == "Original"


# ── Custom-INI nach dem Purge ─────────────────────────────────────────


def _panel(ini: Path | None, ba2=True):
    from anvil.widgets.game_panel import GamePanel
    plugin = SimpleNamespace(
        NeedsBa2Packing=ba2,
        ba2_ini_path=lambda: ini,
        Ba2IniKey="sResourceArchiveList2",
    )
    return lambda: GamePanel.ini_restored(SimpleNamespace(_current_plugin=plugin))


def test_ini_mit_anvil_eintraegen_sperrt(tmp_path):
    ini = tmp_path / "SkyrimCustom.ini"
    ini.write_text("[Archive]\nsResourceArchiveList2 = eigen.bsa, anvil_textures.ba2\n",
                   encoding="cp1252")
    assert _panel(ini)() is False


def test_ini_ohne_anvil_eintraege_ist_sauber(tmp_path):
    ini = tmp_path / "SkyrimCustom.ini"
    # Doppelter Schluessel: ConfigParser scheitert, der Inhalt ist trotzdem sauber
    ini.write_text("[Display]\nfGamma=1\nfGamma=2\n[Archive]\nsResourceArchiveList2=eigen.bsa\n",
                   encoding="cp1252")
    assert _panel(ini)() is True


def test_ini_fehlt_oder_kein_bethesda(tmp_path):
    assert _panel(tmp_path / "gibtsnicht.ini")() is True
    assert _panel(None)() is True
    ini = tmp_path / "x.ini"
    ini.write_text("[Archive]\nsResourceArchiveList2=anvil_x.ba2\n")
    assert _panel(ini, ba2=False)() is True


def test_gesperrte_ini_meldet_sich(tmp_path):
    dateien, _, _ = _spiel(tmp_path)
    fenster, _, wechsel = _wechsel_fenster(tmp_path, dateien, purge=None, ini_ok=False)
    meldungen = []
    fenster.statusBar = lambda: SimpleNamespace(
        showMessage=lambda text, _ms: meldungen.append(text))
    wechsel(fenster, "Neu")
    assert dateien[0].read_text() == "Original"
    assert len(meldungen) == 1


# ── Profil umbenennen ─────────────────────────────────────────────────


def test_umbenennen_im_fenster_zieht_den_marker_mit(tmp_path, monkeypatch):
    from anvil.mainwindow import MainWindow

    dateien, _, _ = _spiel(tmp_path)
    fenster, _, _ = _wechsel_fenster(tmp_path, dateien, purge=None)
    alt = fenster._current_profile_path
    switch_profile_settings(dateien, None, alt)
    monkeypatch.setattr("anvil.mainwindow.Toast", lambda *_a, **_k: None)
    MainWindow._on_profile_renamed(fenster, "Default", "Haupt")
    assert read_owner(dateien) == (alt.parent / "Haupt").resolve()


# ── Runde-3-Luecken ───────────────────────────────────────────────────


def test_geloeschter_besitzer_landet_nicht_beim_aktiven(tmp_path):
    import shutil

    dateien, a, b = _spiel(tmp_path)
    c = tmp_path / "profiles" / "Drei"
    c.mkdir()
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B-eigen")
    switch_profile_settings(dateien, None, a)
    dateien[0].write_text("A-geaendert")
    # A->B uebersprungen (Spiel lief), dann A geloescht, dann B->C
    shutil.rmtree(a)
    switch_profile_settings(dateien, b, c)
    assert (b / SETTINGS_DIR / "Prefs.ini").read_text() == "B-eigen"


def test_start_nach_geloeschtem_besitzer_laedt_eigene(tmp_path):
    import shutil

    dateien, a, b = _spiel(tmp_path)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B-eigen")
    switch_profile_settings(dateien, None, a)
    dateien[0].write_text("A-geaendert")
    shutil.rmtree(a)
    switch_profile_settings(dateien, b, b)
    assert dateien[0].read_text() == "B-eigen"
    assert read_owner(dateien) == b.resolve()


def test_geloeschte_livedatei_kommt_nicht_zurueck(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    switch_profile_settings(dateien, None, a)
    switch_profile_settings(dateien, a, b)
    switch_profile_settings(dateien, b, a)
    dateien[1].unlink()  # z. B. Tastenbelegung zuruecksetzen
    switch_profile_settings(dateien, a, b)
    assert not (a / SETTINGS_DIR / "config.lsf").exists()
    switch_profile_settings(dateien, b, a)
    assert not dateien[1].exists()


def test_gleichnamige_profile_verschiedener_instanzen(tmp_path):
    live = tmp_path / "Spiel"
    live.mkdir()
    dateien = [live / "Prefs.ini"]
    dateien[0].write_text("X")
    x = tmp_path / "InstanzX" / ".profiles" / "Default"
    y = tmp_path / "InstanzY" / ".profiles" / "Default"
    x.mkdir(parents=True)
    y.mkdir(parents=True)
    (y / SETTINGS_DIR).mkdir()
    (y / SETTINGS_DIR / "Prefs.ini").write_text("Y")
    switch_profile_settings(dateien, None, x)
    switch_profile_settings(dateien, y, y)  # Start aus Instanz Y
    assert dateien[0].read_text() == "Y"
    assert (x / SETTINGS_DIR / "Prefs.ini").read_text() == "X"


def test_option_aus_vergisst_den_besitzer(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    switch_profile_settings(dateien, None, a)
    fenster, _ = _fenster(tmp_path, local_inis="false", dateien=dateien)
    fenster._swap(a, b)
    assert read_owner(dateien) is None
    assert dateien[0].read_text() == "Original"


def test_rechtefehler_bricht_nicht_ab(tmp_path, monkeypatch):
    dateien, a, b = _spiel(tmp_path)
    (b / SETTINGS_DIR).mkdir()
    (b / SETTINGS_DIR / "Prefs.ini").write_text("B")
    echtes_is_dir = Path.is_dir

    def is_dir(self):
        # Spielordner nicht durchsuchbar
        if self == dateien[0].parent:
            raise PermissionError(13, "Keine Rechte")
        return echtes_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", is_dir)
    fehler = switch_profile_settings(dateien, a, b)
    assert fehler


def test_ini_nicht_lesbar_sperrt(tmp_path, monkeypatch):
    ini = tmp_path / "SkyrimCustom.ini"
    ini.write_text("[Archive]\nsResourceArchiveList2=eigen.bsa\n")
    echtes_read_text = Path.read_text

    def read_text(self, *a, **k):
        if self == ini:
            raise OSError("gesperrt")
        return echtes_read_text(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", read_text)
    assert _panel(ini)() is False


def test_umbenennen_bei_schreibschutz_bricht_nicht_ab(tmp_path, monkeypatch):
    dateien, a, b = _spiel(tmp_path)
    switch_profile_settings(dateien, None, a)
    import anvil.core.profile_settings as ps

    def kaputt(_files, _profile):
        raise OSError("schreibgeschuetzt")

    monkeypatch.setattr(ps, "_write_owner", kaputt)
    rename_owner(dateien, a, a.with_name("Neu2"))


# ── Runde-4-Luecken ───────────────────────────────────────────────────


def test_neuer_prefix_loescht_keine_profilkopien(tmp_path):
    import shutil

    dateien, a, b = _spiel(tmp_path)
    switch_profile_settings(dateien, None, a)
    switch_profile_settings(dateien, a, b)
    switch_profile_settings(dateien, b, a)
    # compatdata geloescht, Steam legt nur den Ordner neu an
    shutil.rmtree(dateien[0].parent)
    dateien[0].parent.mkdir()
    switch_profile_settings(dateien, a, b)
    assert (a / SETTINGS_DIR / "Prefs.ini").read_text() == "Original"
    assert (a / SETTINGS_DIR / "config.lsf").read_text() == "Original"


def test_option_aus_in_anderer_instanz(tmp_path):
    dateien, a, b = _spiel(tmp_path)
    switch_profile_settings(dateien, None, a)
    (a / SETTINGS_DIR / "Prefs.ini").write_text("A-eigen")
    dateien[0].write_text("A-eigen")
    # Instanz Y mit ausgeschalteter Option startet und aendert global
    fenster, _ = _fenster(tmp_path, local_inis="false", dateien=dateien)
    fenster._swap(a, a)
    dateien[0].write_text("Y-global")
    # Zurueck in X: Start in A, dann Wechsel nach B
    switch_profile_settings(dateien, a, a)
    assert dateien[0].read_text() == "A-eigen"
    switch_profile_settings(dateien, a, b)
    assert (a / SETTINGS_DIR / "Prefs.ini").read_text() == "A-eigen"


def test_leerer_marker_speichert_nirgends(tmp_path, monkeypatch):
    dateien, a, b = _spiel(tmp_path)
    (dateien[0].parent / OWNER_MARKER).write_text("")
    monkeypatch.chdir(tmp_path)
    switch_profile_settings(dateien, a, b)
    assert not (tmp_path / SETTINGS_DIR).exists()
    assert not (a / SETTINGS_DIR).exists()


def test_marker_tmp_wird_aufgeraeumt(tmp_path, monkeypatch):
    dateien, a, b = _spiel(tmp_path)
    import anvil.core.profile_settings as ps
    echtes_replace = ps.os.replace

    def replace(src, dst):
        if Path(dst).name == OWNER_MARKER:
            raise OSError("Rechte")
        return echtes_replace(src, dst)

    monkeypatch.setattr(ps.os, "replace", replace)
    assert switch_profile_settings(dateien, a, b)
    assert not list(dateien[0].parent.glob("*.anvil_tmp"))


def test_bg3_ohne_larian_profil(tmp_path):
    plugin = _mit_dokumenten(BaldursGate3Game, tmp_path)
    plugin.modsettings_path = lambda: None
    assert plugin.profileSettingsFiles() == []


def test_spielende_im_fenster(tmp_path):
    from anvil.mainwindow import MainWindow

    dateien, _, _ = _spiel(tmp_path)
    fenster, _, _ = _wechsel_fenster(tmp_path, dateien, purge=None)
    fenster.keeps_mods_deployed = lambda: False
    fenster._store_profile_settings = (
        lambda p: MainWindow._store_profile_settings(fenster, p))
    alt = fenster._current_profile_path
    switch_profile_settings(dateien, None, alt)
    dateien[0].write_text("im Spiel geaendert")
    MainWindow._purge_after_game(fenster)
    assert (alt / SETTINGS_DIR / "Prefs.ini").read_text() == "im Spiel geaendert"


def test_spielende_mit_schmutziger_ini_sichert_nicht(tmp_path):
    from anvil.mainwindow import MainWindow

    dateien, _, _ = _spiel(tmp_path)
    fenster, _, _ = _wechsel_fenster(tmp_path, dateien, purge=None, ini_ok=False)
    fenster.keeps_mods_deployed = lambda: False
    fenster._store_profile_settings = (
        lambda p: MainWindow._store_profile_settings(fenster, p))
    alt = fenster._current_profile_path
    switch_profile_settings(dateien, None, alt)
    dateien[0].write_text("mit anvil-Eintraegen")
    MainWindow._purge_after_game(fenster)
    assert (alt / SETTINGS_DIR / "Prefs.ini").read_text() == "Original"
