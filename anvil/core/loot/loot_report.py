"""LOOT JSON report parser.

Parses the lootreport.json written by LOOT/lootcli and extracts
structured data for display in the LootDialog.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_TAG = "[LootReport]"


@dataclass
class DirtyInfo:
    """Dirty edit information for a plugin."""
    crc: int = 0
    itm: int = 0
    deleted_references: int = 0
    deleted_navmesh: int = 0
    cleaning_utility: str = ""


@dataclass
class PluginInfo:
    """Parsed plugin data from LOOT report."""
    name: str = ""
    is_master: bool = False
    is_light_master: bool = False
    loads_archive: bool = False
    messages: list[dict] = field(default_factory=list)
    dirty: list[DirtyInfo] = field(default_factory=list)
    missing_masters: list[str] = field(default_factory=list)
    incompatibilities: list[str] = field(default_factory=list)


@dataclass
class LootReport:
    """Parsed LOOT report with structured access to results."""
    plugins: list[PluginInfo] = field(default_factory=list)
    global_messages: list[dict] = field(default_factory=list)
    sorted_order: list[str] = field(default_factory=list)
    loot_version: str = ""
    sort_time_ms: int = 0

    @property
    def has_warnings(self) -> bool:
        return any(
            m.get("type") == "warn"
            for p in self.plugins
            for m in p.messages
        ) or any(m.get("type") == "warn" for m in self.global_messages)

    @property
    def has_errors(self) -> bool:
        return any(
            m.get("type") == "error"
            for p in self.plugins
            for m in p.messages
        ) or any(m.get("type") == "error" for m in self.global_messages)

    @property
    def dirty_plugin_count(self) -> int:
        return sum(1 for p in self.plugins if p.dirty)

    @property
    def missing_master_count(self) -> int:
        return sum(1 for p in self.plugins if p.missing_masters)

    @property
    def warning_count(self) -> int:
        return sum(
            1 for p in self.plugins
            for m in p.messages if m.get("type") == "warn"
        ) + sum(1 for m in self.global_messages if m.get("type") == "warn")

    @property
    def error_count(self) -> int:
        return sum(
            1 for p in self.plugins
            for m in p.messages if m.get("type") == "error"
        ) + sum(1 for m in self.global_messages if m.get("type") == "error")


def parse_report(report_path: str | Path) -> LootReport | None:
    """Parse a LOOT JSON report file.

    Returns LootReport on success, None on failure.
    """
    path = Path(report_path)
    if not path.is_file():
        print(f"{_TAG} Report file not found: {path}")
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"{_TAG} Failed to parse report: {exc}")
        return None

    report = LootReport()

    # Stats
    stats = raw.get("stats", {})
    report.loot_version = stats.get("lootVersion", "")
    report.sort_time_ms = stats.get("time", 0)

    # Global messages
    report.global_messages = raw.get("messages", [])

    # Plugins
    for pdata in raw.get("plugins", []):
        pi = PluginInfo(
            name=pdata.get("name", ""),
            is_master=pdata.get("isMaster", False),
            is_light_master=pdata.get("isLightMaster", False),
            loads_archive=pdata.get("loadsArchive", False),
            messages=pdata.get("messages", []),
            missing_masters=pdata.get("missingMasters", []),
            incompatibilities=[
                inc.get("displayName", inc.get("name", ""))
                for inc in pdata.get("incompatibilities", [])
            ],
        )
        for d in pdata.get("dirty", []):
            pi.dirty.append(DirtyInfo(
                crc=d.get("crc", 0),
                itm=d.get("itm", 0),
                deleted_references=d.get("deletedReferences", 0),
                deleted_navmesh=d.get("deletedNavmesh", 0),
                cleaning_utility=d.get("cleaningUtility", ""),
            ))
        report.plugins.append(pi)

    # The sorted order is the order plugins appear in the report
    report.sorted_order = [p.name for p in report.plugins if p.name]

    return report
