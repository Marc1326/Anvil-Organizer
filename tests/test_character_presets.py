"""Presets sollen ohne Nachfragen im richtigen Ordner landen.

Ein ACU-Preset traegt sein Geschlecht nirgends als Feld. Es steckt nur in
den verwendeten Schluesseln. Erkennen wir es nicht, muss der Benutzer bei
jedem einzelnen Preset gefragt werden -- deshalb sind diese Tests wichtig.
"""

from pathlib import Path

import pytest

from anvil.core.character_presets import (
    FEMALE,
    MALE,
    UNKNOWN,
    PresetKind,
    build_mod,
    detect_variant,
    find_presets,
    suggest_mod_name,
    target_path,
)
from anvil.plugins.games.game_cyberpunk2077 import Cyberpunk2077Game

ACU = Cyberpunk2077Game().get_preset_kinds()[0]

# Echte Schluessel aus den mitgelieferten Presets.
NUR_W = "LocKey#14444638123505366956"
NUR_M = "LocKey#13707137814640364864"
GETEILT = "LocKey#898870017445300632"


def _preset(ordner: Path, name: str, zeilen: list[str]) -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    p = ordner / name
    p.write_text("\n".join(f"{z}:1" for z in zeilen), encoding="utf-8")
    return p


# ── Erkennung ────────────────────────────────────────────────────────


def test_ordner_im_archiv_entscheidet(tmp_path: Path) -> None:
    # Sicherste Stufe: liegt es in female/, ist die Sache klar -- auch wenn
    # der Inhalt nichts hergibt.
    p = _preset(tmp_path / "female", "Vivi.preset", [GETEILT])
    assert detect_variant(p, ACU) == FEMALE


def test_dateiname_entscheidet_wenn_der_ordner_nichts_sagt(tmp_path: Path) -> None:
    p = _preset(tmp_path, "male.preset", [GETEILT])
    assert detect_variant(p, ACU) == MALE


def test_inhalt_entscheidet_wenn_pfad_und_name_nichts_sagen(tmp_path: Path) -> None:
    w = _preset(tmp_path / "a", "Vivi.preset", [GETEILT, NUR_W])
    m = _preset(tmp_path / "b", "Klaus.preset", [GETEILT, NUR_M])
    assert detect_variant(w, ACU) == FEMALE
    assert detect_variant(m, ACU) == MALE


def test_gleichstand_gilt_als_unklar(tmp_path: Path) -> None:
    # Dann wird gefragt, statt zu raten.
    p = _preset(tmp_path, "Egal.preset", [NUR_W, NUR_M])
    assert detect_variant(p, ACU) == UNKNOWN


def test_ohne_erkennungszeichen_unklar(tmp_path: Path) -> None:
    p = _preset(tmp_path, "Egal.preset", [GETEILT])
    assert detect_variant(p, ACU) == UNKNOWN


def test_unlesbare_datei_stuerzt_nicht_ab(tmp_path: Path) -> None:
    p = tmp_path / "kaputt.preset"
    p.write_bytes(b"\xff\xfe\x00\x01")
    assert detect_variant(p, ACU) == UNKNOWN


def test_alle_mitgelieferten_acu_presets_werden_richtig_erkannt() -> None:
    # Gegenprobe an den echten Dateien, wenn ACU installiert ist.
    basis = Path(
        "/home/mob/.anvil-organizer/instances/Cyberpunk 2077/.mods"
        "/ACU - Character Customization/bin/x64/plugins/cyber_engine_tweaks"
        "/mods/AppearanceChangeUnlocker/character-presets",
    )
    if not basis.is_dir():
        pytest.skip("ACU nicht installiert")

    geprueft = 0
    for variante in (FEMALE, MALE):
        for datei in sorted((basis / variante).glob("*.preset")):
            # Ohne den verraeterischen Ordner pruefen -- sonst testen wir
            # nur Stufe 1 und nie die Erkennung am Inhalt.
            flach = Path(datei.name)
            inhalt = datei.read_text(encoding="utf-8", errors="replace")

            from anvil.core.character_presets import _detect_by_content

            class _Fake:
                name = datei.name
                def read_text(self, **_): return inhalt

            assert _detect_by_content(_Fake(), ACU) == variante, datei.name
            assert flach.suffix == ACU.suffix
            geprueft += 1

    assert geprueft == 6


# ── Mod bauen ────────────────────────────────────────────────────────


def test_zielpfad_enthaelt_die_variante() -> None:
    p = target_path(ACU, FEMALE, "Vivi.preset")
    assert str(p).endswith("character-presets/female/Vivi.preset")


def test_mod_ordner_bringt_den_zielpfad_mit(tmp_path: Path) -> None:
    # Genau darum wird eine Mod daraus: der gewoehnliche Deploy-Weg bringt
    # sie ohne Sonderbehandlung an die richtige Stelle.
    quelle = _preset(tmp_path / "in", "Vivi.preset", [NUR_W])
    mods = tmp_path / ".mods"
    mods.mkdir()

    ordner = build_mod(quelle, mods, "ACU-Preset - Vivi (female)", ACU, FEMALE)

    ziel = ordner / ACU.target / "female" / "Vivi.preset"
    assert ziel.is_file()
    assert ziel.read_text(encoding="utf-8").startswith("LocKey#")


def test_bestehender_mod_wird_nicht_ueberschrieben(tmp_path: Path) -> None:
    quelle = _preset(tmp_path / "in", "Vivi.preset", [NUR_W])
    mods = tmp_path / ".mods"
    (mods / "schon da").mkdir(parents=True)

    with pytest.raises(FileExistsError):
        build_mod(quelle, mods, "schon da", ACU, FEMALE)


def test_name_traegt_das_geschlecht(tmp_path: Path) -> None:
    # Sonst kollidieren zwei Presets gleichen Namens fuer weiblich und
    # maennlich miteinander.
    quelle = Path("Vivi.preset")
    w = suggest_mod_name(quelle, FEMALE, ACU)
    m = suggest_mod_name(quelle, MALE, ACU)
    assert w != m
    assert "Vivi" in w and FEMALE in w


def test_presets_im_archiv_finden(tmp_path: Path) -> None:
    _preset(tmp_path / "x" / "female", "A.preset", [NUR_W])
    _preset(tmp_path / "x", "B.preset", [NUR_M])
    (tmp_path / "x" / "liesmich.txt").write_text("egal")

    gefunden = find_presets(tmp_path, ACU)

    assert [p.name for p in gefunden] == ["A.preset", "B.preset"]


def test_spiel_ohne_presets_liefert_leere_liste() -> None:
    from anvil.plugins.games.game_witcher3 import Witcher3Game

    assert Witcher3Game().get_preset_kinds() == []


# ── Einbau ins Hauptfenster ──────────────────────────────────────────

QUELLE = Path("anvil/mainwindow.py").read_text(encoding="utf-8")


def test_presets_werden_vor_dem_gewoehnlichen_weg_abgefangen() -> None:
    # Sonst landet die .preset-Datei als normale Mod im Spielordner und
    # ACU findet sie nie.
    assert "_install_presets_from(temp_dir, archive)" in QUELLE
    assert QUELLE.index("_install_presets_from(temp_dir, archive)") < QUELLE.index(
        "# 2. Check if this is a framework mod",
    )


def test_trenner_wird_nur_einmal_erfragt() -> None:
    # Beim zweiten Preset darf kein Fenster mehr aufgehen.
    assert "self._preset_separator() or self._ask_preset_separator()" in QUELLE


def test_trenner_kommt_ans_ende_der_liste() -> None:
    # Presets spielen in der Ladereihenfolge keine Rolle.
    start = QUELLE.index("def _ask_preset_separator")
    block = QUELLE[start:start + 1500]
    assert "order.append(folder)" in block


def test_neuer_trenner_ist_gelb() -> None:
    # Der Trenner legt sich selbst an, ohne dass jemand ihn sieht --
    # deshalb bekommt er gleich eine Farbe statt grau unterzugehen.
    from anvil.mainwindow import _PRESET_SEP_COLOR

    assert _PRESET_SEP_COLOR.lower() == "#ffd700"

    start = QUELLE.index("def _ask_preset_separator")
    block = QUELLE[start:start + 1800]
    assert 'write_meta_ini(mods_dir / folder, {"color": _PRESET_SEP_COLOR})' in block


def test_farbe_waehlen_zaehlt_nicht_in_der_falschen_liste() -> None:
    # Die Liste blendet gesperrte Frameworks aus. Wer die Zeilennummer
    # direkt als Index nimmt, landet auf einer anderen Mod und bricht
    # kommentarlos ab -- genau so war die Farbe nicht zu aendern.
    for name in ("_ctx_select_separator_color", "_ctx_reset_separator_color"):
        start = QUELLE.index(f"def {name}")
        block = QUELLE[start:start + 500]
        assert "self._current_mod_entries[source_row]" not in block, name
        assert "self._entry_for_row(source_row)" in block, name


def test_geloeschter_trenner_wird_neu_erfragt() -> None:
    start = QUELLE.index("def _preset_separator")
    block = QUELLE[start:QUELLE.index("def _ask_preset_separator")]
    assert "e.is_separator" in block
    assert 'return name if vorhanden else ""' in block


def test_trennername_ueberlebt_den_neustart(tmp_path: Path) -> None:
    # save_instance schreibt nur bekannte Schluessel. Fehlte der hier,
    # ginge bei jedem Preset erneut das Trenner-Fenster auf.
    from anvil.core.instance_manager import InstanceManager

    basis = tmp_path / "instances"
    (basis / "Spiel").mkdir(parents=True)
    (basis / "Spiel" / ".anvil.ini").write_text(
        "[%General]\ngame_path=/irgendwo\n", encoding="utf-8",
    )

    im = InstanceManager(basis)
    im.save_instance("Spiel", {"preset_separator": "Meine Presets_separator"})

    assert im.load_instance("Spiel").get("preset_separator") == "Meine Presets_separator"


def test_beiwerk_zaehlt_nicht_als_mod(tmp_path: Path) -> None:
    # Bleibt nach dem Herausloesen der Presets nur noch eine Liesmich-Datei
    # uebrig, waere eine Mod daraus reiner Ballast.
    from anvil.mainwindow import _has_installable_content

    (tmp_path / "readme.txt").write_text("hallo", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "anleitung.md").write_text("x", encoding="utf-8")
    assert _has_installable_content(tmp_path) is False

    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "gesicht.archive").write_bytes(b"\x00")
    assert _has_installable_content(tmp_path) is True


def test_gemischtes_paket_verliert_seinen_inhalt_nicht() -> None:
    # Gesichts-Presets bringen fast immer ein .archive mit -- das Gesicht
    # selbst. Frueher warf Anvil es weg.
    start = QUELLE.index("def _install_presets_from")
    block = QUELLE[start:QUELLE.index("def _write_preset_origin")]
    assert "return not _has_installable_content(temp_dir)" in block
    assert "datei.unlink(missing_ok=True)" in block, (
        "uebernommene Presets muessen aus dem Temp-Ordner verschwinden, "
        "sonst liegt dieselbe Datei zweimal da"
    )


def test_preset_mod_merkt_sich_ihre_herkunft() -> None:
    # Ohne Nexus-Nummer gaebe es bei den Voraussetzungen nichts abzufragen.
    assert "self._write_preset_origin(mods_dir / name, archive)" in QUELLE
    start = QUELLE.index("def _write_preset_origin")
    block = QUELLE[start:start + 1200]
    assert "extract_nexus_mod_id(archive.name)" in block


def test_alle_dialogtexte_in_allen_sprachen() -> None:
    import glob
    import json as _json

    schluessel = {
        "separator_title", "separator_prompt", "separator_default",
        "variant_title", "variant_prompt", "variant_female",
        "variant_male", "installed",
    }
    dateien = sorted(glob.glob("anvil/locales/*.json"))
    assert len(dateien) >= 6

    for f in dateien:
        d = _json.loads(Path(f).read_text(encoding="utf-8"))
        fehlt = schluessel - set(d.get("preset", {}))
        assert not fehlt, f"{f}: {sorted(fehlt)}"
