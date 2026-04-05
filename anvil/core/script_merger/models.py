"""Datenmodell fuer den Script Merger — Enums, Dataclasses."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class MergeStatus(Enum):
    """Status eines Script-Konflikts."""
    UNSCANNED = "unscanned"
    AUTO_MERGEABLE = "auto_mergeable"   # Hunks ueberlappen nicht
    CONFLICT = "conflict"               # Hunks ueberlappen ODER kein Vanilla
    MERGED = "merged"                   # Erfolgreich zusammengefuehrt
    IGNORED = "ignored"                 # User will nicht mergen


@dataclass
class DiffHunk:
    """Ein Aenderungsblock zwischen Vanilla und Mod.

    start_line und end_line sind 0-basiert (inklusive/exklusive),
    analog zu Python-Slice-Notation.
    """
    start_line: int
    end_line: int
    vanilla_lines: list[str]
    mod_lines: list[str]

    def overlaps(self, other: "DiffHunk") -> bool:
        """Prueft ob zwei Hunks sich ueberlappen."""
        return self.start_line < other.end_line and other.start_line < self.end_line


@dataclass
class ModVersion:
    """Eine bestimmte Version einer Script-Datei aus einem Mod."""
    mod_name: str          # Anvil Mod-Name (Ordner in .mods/)
    witcher_mod_name: str  # Witcher-Mod-Name (modXXX im Unterordner)
    file_path: Path        # Absoluter Pfad zur .ws/.xml Datei
    diff_hunks: list[DiffHunk] = field(default_factory=list)
    file_hash: str = ""    # SHA256 fuer Validierung


@dataclass
class ScriptConflict:
    """Ein Konflikt: mehrere Mods aendern dieselbe Script-Datei."""
    relative_path: str          # "game/player/r4Player.ws" (ab scripts/)
    vanilla_path: Path | None   # None = kein Vanilla-Gegenstueck -> CONFLICT
    mod_versions: list[ModVersion] = field(default_factory=list)
    merge_status: MergeStatus = MergeStatus.UNSCANNED
    merged_content: str | None = None  # Ergebnis des Auto-Merge


@dataclass
class MergeResult:
    """Ergebnis eines Merge-Versuchs."""
    conflict: ScriptConflict
    success: bool
    merged_content: str | None = None
    unresolved_count: int = 0     # Anzahl ungeloester Konflikte (Phase 1: nur zaehlen)
    method: str = ""              # "auto" (Phase 1), "merge3"/"kdiff3" (Phase 2)
    error_message: str = ""


@dataclass
class MergeInventoryEntry:
    """Persistenter Eintrag fuer einen durchgefuehrten Merge."""
    relative_path: str
    mods: list[str]               # Beteiligte Mod-Namen
    method: str
    timestamp: str                # ISO 8601
    source_hashes: dict[str, str] # {"vanilla": "abc...", "modXXX": "def..."}
    merged_hash: str
