"""Die vorausgesetzten Mods eines Presets.

Ein Preset beschreibt nur Zahlenwerte. Fehlt die Mod, auf die sie sich
beziehen, sieht die Figur anders aus -- ohne dass irgendwo ein Fehler
erschiene. Deshalb muss diese Liste stimmen.
"""

from pathlib import Path

import pytest

from anvil.core.nexus_requirements import (
    Requirement,
    RequirementsError,
    _parse,
    load_cache,
    save_cache,
)

# Ausschnitt einer echten Antwort (Bad Corpo, Cyberpunk 2077).
ANTWORT = {
    "data": {"legacyModsByDomain": {"nodes": [{
        "modId": 5277,
        "modRequirements": {"nexusRequirements": {"nodes": [
            {"modId": "107", "modName": "Cyber Engine Tweaks",
             "notes": "Required", "url": "", "externalRequirement": False},
            {"modId": "3328", "modName": "Moderately Thicc Body",
             "notes": "", "url": "", "externalRequirement": False},
            {"modId": None, "modName": "Irgendwas anderes",
             "notes": "optional", "url": "https://example.org/x",
             "externalRequirement": True},
        ]}},
    }]}},
}


def test_liest_die_liste_aus_der_antwort() -> None:
    r = _parse(ANTWORT, "cyberpunk2077")
    assert [x.name for x in r] == [
        "Cyber Engine Tweaks", "Moderately Thicc Body", "Irgendwas anderes",
    ]


def test_adresse_wird_ergaenzt_wenn_nexus_keine_liefert() -> None:
    # Nexus laesst url bei eigenen Mods leer -- ohne Ergaenzung waere die
    # Zeile nicht anklickbar.
    r = _parse(ANTWORT, "cyberpunk2077")
    assert r[0].url == "https://www.nexusmods.com/cyberpunk2077/mods/107"


def test_fremde_voraussetzung_behaelt_ihre_adresse() -> None:
    r = _parse(ANTWORT, "cyberpunk2077")[2]
    assert r.external is True
    assert r.mod_id == 0
    assert r.url == "https://example.org/x"


def test_pflicht_wird_an_der_notiz_erkannt() -> None:
    r = _parse(ANTWORT, "cyberpunk2077")
    assert r[0].required is True
    assert r[1].required is False


@pytest.mark.parametrize("notiz,pflicht", [
    ("Required", True),
    ("required", True),
    ("Required - hard requirement", True),
    ("optional - *Strongly Recommended", False),
    ("", False),
    ("not required", False),
])
def test_pflichtangabe_ist_freitext(notiz: str, pflicht: bool) -> None:
    # Nexus hat kein Feld dafuer, nur den getippten Text des Autors.
    r = Requirement(mod_id=1, name="x", notes=notiz, url="", external=False)
    assert r.required is pflicht


def test_leere_antwort_ergibt_leere_liste() -> None:
    assert _parse({"data": {"legacyModsByDomain": {"nodes": []}}}, "x") == []


def test_antwort_ohne_voraussetzungen() -> None:
    leer = {"data": {"legacyModsByDomain": {"nodes": [
        {"modId": 1, "modRequirements": None},
    ]}}}
    assert _parse(leer, "x") == []


# ── Zwischenspeicher ─────────────────────────────────────────────────


def test_speichern_und_zurueckholen(tmp_path: Path) -> None:
    datei = tmp_path / "reqs.json"
    posten = _parse(ANTWORT, "cyberpunk2077")

    save_cache(datei, "cyberpunk2077", 5277, posten)

    assert load_cache(datei, "cyberpunk2077", 5277) == posten


def test_zwei_mods_kommen_sich_nicht_ins_gehege(tmp_path: Path) -> None:
    datei = tmp_path / "reqs.json"
    a = [Requirement(1, "A", "", "", False)]
    b = [Requirement(2, "B", "", "", False)]

    save_cache(datei, "cyberpunk2077", 111, a)
    save_cache(datei, "cyberpunk2077", 222, b)

    assert load_cache(datei, "cyberpunk2077", 111) == a
    assert load_cache(datei, "cyberpunk2077", 222) == b


def test_unbekannte_mod_liefert_none(tmp_path: Path) -> None:
    # None heisst "nie abgefragt" -- leere Liste hiesse "abgefragt, nichts
    # dabei". Der Tab zeigt zwei verschiedene Texte dafuer.
    datei = tmp_path / "reqs.json"
    save_cache(datei, "cyberpunk2077", 111, [])
    assert load_cache(datei, "cyberpunk2077", 999) is None
    assert load_cache(datei, "cyberpunk2077", 111) == []


def test_kaputter_zwischenspeicher_stuerzt_nicht_ab(tmp_path: Path) -> None:
    datei = tmp_path / "reqs.json"
    datei.write_text("kein json", encoding="utf-8")

    assert load_cache(datei, "x", 1) is None

    # und laesst sich ueberschreiben statt dauerhaft zu blockieren
    save_cache(datei, "x", 1, [Requirement(1, "A", "", "", False)])
    assert load_cache(datei, "x", 1) is not None


def test_fehlende_datei_stuerzt_nicht_ab(tmp_path: Path) -> None:
    assert load_cache(tmp_path / "gibtsnicht.json", "x", 1) is None


def test_fehlermeldung_von_nexus_wird_durchgereicht() -> None:
    from anvil.core import nexus_requirements as nr

    def _antwort(*_a, **_k):
        raise OSError("Netz weg")

    class _Fake:
        def __enter__(self): raise OSError("Netz weg")
        def __exit__(self, *a): return False

    import urllib.request
    alt = urllib.request.urlopen
    urllib.request.urlopen = lambda *a, **k: _Fake()
    try:
        with pytest.raises(RequirementsError):
            nr.fetch("cyberpunk2077", 1)
    finally:
        urllib.request.urlopen = alt


# ── Einbau in die Oberflaeche ────────────────────────────────────────

DIALOG = Path("anvil/dialogs/mod_detail_dialog.py").read_text(encoding="utf-8")


def test_tab_erscheint_nur_bei_presets() -> None:
    assert "if mod_has_presets(mod_path, game_plugin):" in DIALOG


def test_liste_kommt_ohne_knopfdruck() -> None:
    # Wer ein Preset oeffnet, will die Liste sehen und nicht erst einen
    # Knopf suchen.
    start = DIALOG.index("def _build_presets_tab")
    block = DIALOG[start:DIALOG.index("def _build_conflicts_tab")]
    assert "QTimer.singleShot(0, _laden)" in block


def test_zwischenspeicher_spart_den_abruf() -> None:
    # Sonst ginge bei jedem Oeffnen eine Anfrage raus.
    start = DIALOG.index("def _build_presets_tab")
    block = DIALOG[start:DIALOG.index("def _build_conflicts_tab")]
    assert "if zwischen is not None:" in block


def test_abruf_laeuft_nicht_im_hauptfaden() -> None:
    # Sonst steht das Fenster, solange Nexus antwortet.
    assert "class _RequirementsLoader(QThread)" in DIALOG
    start = DIALOG.index("def _build_presets_tab")
    block = DIALOG[start:DIALOG.index("def _build_conflicts_tab")]
    assert "lader.start()" in block
    assert "page._lader = lader" in block, "Thread muss referenziert bleiben"


def test_alle_texte_in_allen_sprachen() -> None:
    import glob
    import json as _json

    schluessel = {
        "refresh", "col_state", "col_mod", "col_note", "state_installed",
        "state_missing", "loading", "none", "no_nexus",
        "summary_missing", "summary_complete", "error", "open_hint",
    }
    dateien = sorted(glob.glob("anvil/locales/*.json"))
    assert len(dateien) >= 6

    for f in dateien:
        d = _json.loads(Path(f).read_text(encoding="utf-8"))
        fehlt = schluessel - set(d.get("preset_reqs", {}))
        assert not fehlt, f"{f}: {sorted(fehlt)}"
        assert d.get("mod_detail", {}).get("tab_preset_reqs"), f
