"""Merge-Inventar — persistente Aufzeichnung aller durchgefuehrten Merges."""

import json
from pathlib import Path

from anvil.core.script_merger.models import (
    MergeInventoryEntry, ScriptConflict,
)


class MergeInventory:
    """Verwaltet das Merge-Inventar als JSON-Datei.

    Speichert:
      - Alle durchgefuehrten Merges mit Quell-Hashes
      - Ignorierte Konflikte (persistent)
      - Name des Merge-Mods (Standard: mod0000_MergedFiles)
    """

    def __init__(self, inventory_path: Path):
        self._path = inventory_path
        self._merges: list[MergeInventoryEntry] = []
        self._ignored: list[str] = []
        self._merged_mod_name = "mod0000_MergedFiles"

    def load(self) -> None:
        """Laedt das Inventar aus der JSON-Datei."""
        if not self._path.is_file():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._merged_mod_name = data.get("merged_mod_name", "mod0000_MergedFiles")
            self._ignored = data.get("ignored", [])
            self._merges = []
            for m in data.get("merges", []):
                self._merges.append(MergeInventoryEntry(
                    relative_path=m["relative_path"],
                    mods=m["mods"],
                    method=m["method"],
                    timestamp=m["timestamp"],
                    source_hashes=m["source_hashes"],
                    merged_hash=m["merged_hash"],
                ))
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    def save(self) -> None:
        """Speichert das Inventar als JSON-Datei."""
        data = {
            "version": 1,
            "merged_mod_name": self._merged_mod_name,
            "merges": [
                {
                    "relative_path": e.relative_path,
                    "mods": e.mods,
                    "method": e.method,
                    "timestamp": e.timestamp,
                    "source_hashes": e.source_hashes,
                    "merged_hash": e.merged_hash,
                }
                for e in self._merges
            ],
            "ignored": self._ignored,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add_merge(self, entry: MergeInventoryEntry) -> None:
        """Fuegt einen Merge-Eintrag hinzu oder ersetzt einen vorhandenen."""
        self._merges = [
            m for m in self._merges if m.relative_path != entry.relative_path
        ]
        self._merges.append(entry)

    def get_ignored(self) -> list[str]:
        """Gibt Liste der ignorierten relativen Pfade zurueck."""
        return list(self._ignored)

    def set_ignored(self, relative_path: str) -> None:
        """Markiert einen Konflikt als ignoriert."""
        if relative_path not in self._ignored:
            self._ignored.append(relative_path)

    def unset_ignored(self, relative_path: str) -> None:
        """Entfernt die Ignorierung eines Konflikts."""
        self._ignored = [p for p in self._ignored if p != relative_path]

    def validate(self, conflicts: list[ScriptConflict]) -> list[str]:
        """Prueft ob Quell-Mods sich seit letztem Merge geaendert haben.

        Returns:
            Liste der relative_paths deren Quell-Hashes nicht mehr stimmen.
        """
        stale = []
        merge_map = {m.relative_path: m for m in self._merges}
        for conflict in conflicts:
            if conflict.relative_path not in merge_map:
                continue
            entry = merge_map[conflict.relative_path]
            for mv in conflict.mod_versions:
                expected = entry.source_hashes.get(mv.mod_name, "")
                if expected and expected != mv.file_hash:
                    stale.append(conflict.relative_path)
                    break
        return stale

    def clear(self) -> None:
        """Loescht alle Merges und Ignorierungen."""
        self._merges.clear()
        self._ignored.clear()

    @property
    def merges(self) -> list[MergeInventoryEntry]:
        """Gibt eine Kopie der Merge-Eintraege zurueck."""
        return list(self._merges)
