"""Das Inhaltsverzeichnis einer Cyberpunk-``.archive`` lesen.

Zwei Mods koennen dieselbe Spieldatei liefern, ohne dass man es ihnen von
aussen ansieht: die Archive heissen verschieden, und was drinsteckt,
verraet weder Dateiname noch Ordner. Genau daran scheitert die
Konflikterkennung -- sie vergleicht Pfade im Mod-Ordner, nicht Inhalte.

REDengine legt am Ende jedes Archivs eine Tabelle ab, in der jede
enthaltene Spieldatei mit einer 64-Bit-Pruefsumme ihres Pfades steht.
Diese Pruefsummen genuegen: gleiche Pruefsumme = gleiche Spieldatei.
Der Klartextpfad wird dafuer nicht gebraucht.

Gelesen werden nur der Kopf und die Tabelle -- ein paar Kilobyte, egal
wie gross das Archiv ist. Kein Auspacken, kein fremdes Programm.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"RDAR"

# Kopf: Magic(4) Version(4) IndexPos(8) IndexSize(8) DebugPos(8) DebugSize(8)
_HEADER_INDEX_POS = 8
_HEADER_INDEX_SIZE = 16

# Index: FileTableOffset(4) FileTableSize(4) Crc(8) Dateien(4) Segmente(4)
# Abhaengigkeiten(4) -- danach beginnt die Dateitabelle.
_INDEX_HEADER_LEN = 28

# Ein Eintrag: Hash(8) Zeitstempel(8) InlineSegmente(4) SegmentStart(4)
# SegmentEnde(4) AbhStart(4) AbhEnde(4) SHA1(20)
_ENTRY_LEN = 56

# Ein Archiv mit mehr Eintraegen ist keins mehr -- dann stimmt der Kopf
# nicht und die Zahl stammt aus Zufallsbytes.
_MAX_ENTRIES = 2_000_000


class ArchiveError(RuntimeError):
    """Datei ist kein lesbares REDengine-Archiv."""


@dataclass(frozen=True)
class ArchiveInfo:
    """Was in einem Archiv steckt.

    Attributes:
        path:    Die gelesene Datei.
        hashes:  Pruefsummen aller enthaltenen Spieldateien.
        version: Formatversion aus dem Kopf.
    """

    path: Path
    hashes: frozenset[int]
    version: int

    def __len__(self) -> int:
        return len(self.hashes)


def is_archive(path: Path) -> bool:
    """Schnelle Vorpruefung am Magic -- ohne die Datei ganz zu lesen."""
    try:
        with path.open("rb") as f:
            return f.read(4) == MAGIC
    except OSError:
        return False


def read_archive(path: Path) -> ArchiveInfo:
    """Liest das Inhaltsverzeichnis.

    Raises:
        ArchiveError: Kein Archiv, oder der Kopf ist unbrauchbar.
    """
    try:
        with path.open("rb") as f:
            kopf = f.read(48)
            if len(kopf) < 48 or kopf[:4] != MAGIC:
                raise ArchiveError(f"kein RDAR-Archiv: {path.name}")

            version, = struct.unpack_from("<I", kopf, 4)
            idx_pos, = struct.unpack_from("<Q", kopf, _HEADER_INDEX_POS)
            idx_size, = struct.unpack_from("<Q", kopf, _HEADER_INDEX_SIZE)

            groesse = path.stat().st_size
            if not (0 < idx_pos < groesse) or not (0 < idx_size <= groesse - idx_pos):
                raise ArchiveError(f"Index liegt ausserhalb der Datei: {path.name}")

            f.seek(idx_pos)
            index = f.read(idx_size)
    except OSError as exc:
        raise ArchiveError(str(exc)) from exc

    if len(index) < _INDEX_HEADER_LEN:
        raise ArchiveError(f"Index zu kurz: {path.name}")

    anzahl, = struct.unpack_from("<I", index, 16)
    if anzahl > _MAX_ENTRIES:
        raise ArchiveError(f"unglaubwuerdige Dateizahl ({anzahl}): {path.name}")

    noetig = _INDEX_HEADER_LEN + anzahl * _ENTRY_LEN
    if noetig > len(index):
        raise ArchiveError(f"Dateitabelle abgeschnitten: {path.name}")

    hashes = {
        struct.unpack_from("<Q", index, _INDEX_HEADER_LEN + i * _ENTRY_LEN)[0]
        for i in range(anzahl)
    }
    return ArchiveInfo(path=path, hashes=frozenset(hashes), version=version)


def shared_hashes(a: ArchiveInfo, b: ArchiveInfo) -> frozenset[int]:
    """Spieldateien, die beide Archive liefern."""
    return frozenset(a.hashes & b.hashes)


def find_overlaps(
    archive: list[ArchiveInfo],
) -> list[tuple[ArchiveInfo, ArchiveInfo, int]]:
    """Alle Paare, die sich Spieldateien teilen.

    Returns:
        (a, b, Anzahl gemeinsamer Dateien), die groessten Ueberschneidungen
        zuerst -- dort tut ein Konflikt am meisten weh.
    """
    paare: list[tuple[ArchiveInfo, ArchiveInfo, int]] = []
    for i, a in enumerate(archive):
        for b in archive[i + 1:]:
            gemeinsam = len(a.hashes & b.hashes)
            if gemeinsam:
                paare.append((a, b, gemeinsam))
    paare.sort(key=lambda p: p[2], reverse=True)
    return paare
