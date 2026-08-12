"""In die .archive hineinschauen, statt Dateinamen zu vergleichen.

Zwei Mods koennen dieselbe Spieldatei liefern, ohne dass man es ihnen von
aussen ansieht. Die Konflikterkennung vergleicht Pfade im Mod-Ordner --
was im Archiv steckt, sieht sie nicht. Damit bleiben genau die Konflikte
unsichtbar, die im Spiel wehtun.
"""

import struct
from pathlib import Path

import pytest

from anvil.core.redengine_archive import (
    ArchiveError,
    ArchiveInfo,
    find_overlaps,
    is_archive,
    read_archive,
    shared_hashes,
)

ECHT = Path(
    "/home/mob/.anvil-organizer/instances/Cyberpunk 2077/.mods"
    "/Unique Eyes - Core/archive/pc/mod"
    "/00_Halvkyrie_UniqueEyes_Core_Default_V2.5.archive",
)


def _archiv(pfad: Path, hashes: list[int], version: int = 12) -> Path:
    """Baut ein Archiv mit genau diesen Pruefsummen im Verzeichnis."""
    tabelle = b"".join(struct.pack("<Q", h) + b"\x00" * 48 for h in hashes)
    index = struct.pack("<IIQIII", 8, len(tabelle) + 8, 0, len(hashes), 0, 0) + tabelle

    daten = b"\x00" * 64                      # Platzhalter fuer Nutzdaten
    idx_pos = 48 + len(daten)
    kopf = struct.pack("<4sIQQQQ", b"RDAR", version, idx_pos, len(index), 0, 0)
    kopf += b"\x00" * (48 - len(kopf))

    pfad.write_bytes(kopf + daten + index)
    return pfad


# ── Format lesen ─────────────────────────────────────────────────────


def test_liest_die_pruefsummen(tmp_path: Path) -> None:
    p = _archiv(tmp_path / "a.archive", [0x1111, 0x2222, 0x3333])
    info = read_archive(p)

    assert info.hashes == {0x1111, 0x2222, 0x3333}
    assert len(info) == 3
    assert info.version == 12


def test_leeres_archiv_ist_kein_fehler(tmp_path: Path) -> None:
    info = read_archive(_archiv(tmp_path / "leer.archive", []))
    assert info.hashes == frozenset()


def test_magic_wird_geprueft(tmp_path: Path) -> None:
    p = tmp_path / "kein.archive"
    p.write_bytes(b"PK\x03\x04" + b"\x00" * 100)

    assert is_archive(p) is False
    with pytest.raises(ArchiveError):
        read_archive(p)


def test_erkennt_ein_echtes_archiv_am_magic(tmp_path: Path) -> None:
    assert is_archive(_archiv(tmp_path / "a.archive", [1])) is True


# ── Was nicht abstuerzen darf ────────────────────────────────────────


def test_abgeschnittene_datei(tmp_path: Path) -> None:
    p = _archiv(tmp_path / "a.archive", [1, 2, 3])
    roh = p.read_bytes()
    p.write_bytes(roh[:len(roh) // 2])

    with pytest.raises(ArchiveError):
        read_archive(p)


def test_index_zeigt_ins_leere(tmp_path: Path) -> None:
    p = _archiv(tmp_path / "a.archive", [1])
    roh = bytearray(p.read_bytes())
    struct.pack_into("<Q", roh, 8, 999_999_999)   # Index weit hinter dem Ende
    p.write_bytes(bytes(roh))

    with pytest.raises(ArchiveError):
        read_archive(p)


def test_unglaubwuerdige_dateizahl(tmp_path: Path) -> None:
    # Aus Zufallsbytes wuerde sonst eine Milliarde Eintraege gelesen und
    # der Rechner haengt.
    p = _archiv(tmp_path / "a.archive", [1])
    roh = bytearray(p.read_bytes())
    idx_pos = struct.unpack_from("<Q", roh, 8)[0]
    struct.pack_into("<I", roh, idx_pos + 16, 900_000_000)
    p.write_bytes(bytes(roh))

    with pytest.raises(ArchiveError):
        read_archive(p)


def test_fehlende_datei(tmp_path: Path) -> None:
    with pytest.raises(ArchiveError):
        read_archive(tmp_path / "gibtsnicht.archive")

    assert is_archive(tmp_path / "gibtsnicht.archive") is False


# ── Ueberschneidungen finden ─────────────────────────────────────────


def _info(name: str, hashes: set[int]) -> ArchiveInfo:
    return ArchiveInfo(path=Path(name), hashes=frozenset(hashes), version=12)


def test_gemeinsame_dateien(tmp_path: Path) -> None:
    a = _info("a", {1, 2, 3})
    b = _info("b", {3, 4})

    assert shared_hashes(a, b) == frozenset({3})


def test_ohne_ueberschneidung_leer() -> None:
    assert shared_hashes(_info("a", {1}), _info("b", {2})) == frozenset()


def test_paare_nach_schwere_sortiert() -> None:
    # Wer sich viele Dateien teilt, faellt im Spiel am meisten auf.
    a = _info("a", {1, 2, 3, 4})
    b = _info("b", {3, 4, 5})
    c = _info("c", {4})

    paare = find_overlaps([a, b, c])

    assert [n for _, _, n in paare] == [2, 1, 1]
    assert paare[0][0].path.name == "a"
    assert paare[0][1].path.name == "b"


def test_ohne_treffer_keine_paare() -> None:
    assert find_overlaps([_info("a", {1}), _info("b", {2})]) == []


# ── Gegenprobe an einer echten Datei ─────────────────────────────────


@pytest.mark.skipif(not ECHT.is_file(), reason="Cyberpunk-Mod nicht installiert")
def test_echtes_archiv_liefert_die_bekannte_dateizahl() -> None:
    # Unique Eyes Core enthaelt 43 Spieldateien -- unabhaengig gemessen.
    # Kaeme hier etwas anderes heraus, laege der Kopf falsch.
    info = read_archive(ECHT)

    assert len(info) == 43
    assert info.version == 12
