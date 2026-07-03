"""Benutzerdefinierte Eigenschaften (frei vergebbare Marker) pro Instanz.

Jede Instanz hat eine eigene properties.json. Eigenschaften sind flach und
werden über ganzzahlige IDs referenziert. Mods speichern ihre Eigenschaften
als Komma-Liste in meta.ini (Feld ``properties``).

Die sieben eingebauten Filter-Eigenschaften (Aktiviert, Deaktiviert, ...)
sind fest im Filter-Panel verdrahtet (negative IDs) und tauchen hier nicht
auf — dieser Manager verwaltet ausschließlich vom Nutzer angelegte.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PropertyManager:
    """Verwaltet die benutzerdefinierten Eigenschaften einer Instanz."""

    FILENAME = "properties.json"

    def __init__(self) -> None:
        self._properties: list[dict[str, Any]] = []
        self._path: Path | None = None

    # ── Load / Save ────────────────────────────────────────────────

    def load(self, instance_path: Path) -> None:
        """Lädt *instance_path*/properties.json (leer, wenn nicht vorhanden)."""
        self._path = instance_path / self.FILENAME
        self._properties = []
        if self._path.is_file():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._properties = data
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._properties, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    # ── Query ──────────────────────────────────────────────────────

    def all_properties(self) -> list[dict[str, Any]]:
        return sorted(self._properties, key=lambda p: p["name"].lower())

    def get_name(self, prop_id: int) -> str:
        for p in self._properties:
            if p["id"] == prop_id:
                return p["name"]
        return ""

    def get_id(self, name: str) -> int:
        lower = name.lower()
        for p in self._properties:
            if p["name"].lower() == lower:
                return p["id"]
        return 0

    def exists(self, prop_id: int) -> bool:
        return any(p["id"] == prop_id for p in self._properties)

    # ── Mutate ─────────────────────────────────────────────────────

    def _next_id(self) -> int:
        if not self._properties:
            return 1
        return max(p["id"] for p in self._properties) + 1

    def add_property(self, name: str) -> int:
        """Legt eine Eigenschaft an; 0 wenn der Name schon existiert."""
        if self.get_id(name) != 0:
            return 0
        new_id = self._next_id()
        self._properties.append({"id": new_id, "name": name})
        self.save()
        return new_id

    def rename_property(self, prop_id: int, new_name: str) -> bool:
        for p in self._properties:
            if p["id"] == prop_id:
                p["name"] = new_name
                self.save()
                return True
        return False

    def remove_property(self, prop_id: int) -> bool:
        before = len(self._properties)
        self._properties = [p for p in self._properties if p["id"] != prop_id]
        if len(self._properties) < before:
            self.save()
            return True
        return False
