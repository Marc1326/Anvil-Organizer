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


def test_geloeschter_trenner_wird_neu_erfragt() -> None:
    start = QUELLE.index("def _preset_separator")
    block = QUELLE[start:QUELLE.index("def _ask_preset_separator")]
    assert "e.is_separator" in block
    assert 'return name if vorhanden else ""' in block


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
