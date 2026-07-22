"""Native Bethesda plugin header parsing and dependency sorting.

This module intentionally starts with hard load-order constraints only:
primary/implicit plugins and TES4 MAST dependencies. Optional metadata rules
can be layered on top without weakening these constraints.
"""

from __future__ import annotations

import heapq
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

_PLUGIN_EXTENSIONS = {".esm", ".esp", ".esl"}
_RECORD_HEADER = struct.Struct("<4sIIIIHH")
_SUBRECORD_HEADER = struct.Struct("<4sH")
_MASTER_FLAG = 0x00000001
_LIGHT_FLAG = 0x00000200
_MAX_TES4_HEADER_SIZE = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class PluginHeader:
    name: str
    masters: tuple[str, ...] = ()
    is_master: bool = False
    is_light: bool = False
    error: str = ""


@dataclass(slots=True)
class NativeSortResult:
    names: list[str]
    missing_masters: dict[str, list[str]] = field(default_factory=dict)
    cycles: list[list[str]] = field(default_factory=list)
    parse_errors: dict[str, str] = field(default_factory=dict)


def parse_plugin_header(path: Path) -> PluginHeader:
    """Read TES4 flags and MAST subrecords from one Bethesda plugin."""
    try:
        with path.open("rb") as stream:
            raw_header = stream.read(_RECORD_HEADER.size)
            if len(raw_header) != _RECORD_HEADER.size:
                raise ValueError("plugin header is truncated")
            signature, data_size, flags, _form_id, _stamp, _vc1, _vc2 = (
                _RECORD_HEADER.unpack(raw_header)
            )
            if signature != b"TES4":
                raise ValueError("first record is not TES4")
            remaining_size = path.stat().st_size - stream.tell()
            if data_size > remaining_size:
                raise ValueError("TES4 payload is truncated")
            if data_size > _MAX_TES4_HEADER_SIZE:
                raise ValueError("TES4 payload is implausibly large")
            payload = stream.read(data_size)
            if len(payload) != data_size:
                raise ValueError("TES4 payload is truncated")
    except (OSError, ValueError, struct.error) as exc:
        return PluginHeader(name=path.name, error=str(exc))

    masters: list[str] = []
    offset = 0
    extended_size: int | None = None
    while offset < len(payload):
        if offset + _SUBRECORD_HEADER.size > len(payload):
            return PluginHeader(
                name=path.name,
                masters=tuple(masters),
                is_master=bool(flags & _MASTER_FLAG),
                is_light=bool(flags & _LIGHT_FLAG),
                error="trailing bytes after TES4 subrecords",
            )
        signature, short_size = _SUBRECORD_HEADER.unpack_from(payload, offset)
        offset += _SUBRECORD_HEADER.size
        if signature == b"XXXX":
            if extended_size is not None or short_size != 4:
                return PluginHeader(
                    name=path.name,
                    masters=tuple(masters),
                    is_master=bool(flags & _MASTER_FLAG),
                    is_light=bool(flags & _LIGHT_FLAG),
                    error="invalid XXXX extended-size subrecord",
                )
            if offset + 4 > len(payload):
                return PluginHeader(
                    name=path.name,
                    masters=tuple(masters),
                    is_master=bool(flags & _MASTER_FLAG),
                    is_light=bool(flags & _LIGHT_FLAG),
                    error="XXXX payload is truncated",
                )
            extended_size = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            continue
        size = extended_size if extended_size is not None else short_size
        extended_size = None
        if offset + size > len(payload):
            return PluginHeader(
                name=path.name,
                masters=tuple(masters),
                is_master=bool(flags & _MASTER_FLAG),
                is_light=bool(flags & _LIGHT_FLAG),
                error="subrecord payload is truncated",
            )
        data = payload[offset : offset + size]
        offset += size
        if signature == b"MAST":
            master = data.rstrip(b"\0").decode("cp1252", errors="replace").strip()
            if master:
                masters.append(master)

    if extended_size is not None:
        return PluginHeader(
            name=path.name,
            masters=tuple(masters),
            is_master=bool(flags & _MASTER_FLAG),
            is_light=bool(flags & _LIGHT_FLAG),
            error="XXXX subrecord has no following subrecord",
        )

    return PluginHeader(
        name=path.name,
        masters=tuple(masters),
        is_master=bool(flags & _MASTER_FLAG),
        is_light=bool(flags & _LIGHT_FLAG),
    )


def read_creation_club_plugins(path: Path | None) -> list[str]:
    """Read a Skyrim/Fallout Creation Club manifest in declared order."""
    if path is None or not path.is_file():
        return []
    try:
        lines = path.read_text(
            encoding="utf-8-sig", errors="replace"
        ).splitlines()
    except OSError:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for raw in lines:
        name = raw.strip().lstrip("*")
        if not name or name.startswith("#"):
            continue
        if Path(name).suffix.lower() not in _PLUGIN_EXTENSIONS:
            continue
        key = name.casefold()
        if key not in seen:
            result.append(name)
            seen.add(key)
    return result


def _cyclic_components(
    unresolved: list[str],
    outgoing: dict[str, set[str]],
    rank: dict[str, int],
) -> list[list[str]]:
    """Return cyclic strongly connected components without recursion."""
    unresolved_set = set(unresolved)
    reverse: dict[str, set[str]] = {node: set() for node in unresolved}
    for node in unresolved:
        for dependent in outgoing[node]:
            if dependent in unresolved_set:
                reverse[dependent].add(node)

    visited: set[str] = set()
    finish_order: list[str] = []
    for start in sorted(unresolved, key=rank.__getitem__):
        if start in visited:
            continue
        stack: list[tuple[str, bool]] = [(start, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                finish_order.append(node)
                continue
            if node in visited:
                continue
            visited.add(node)
            stack.append((node, True))
            neighbours = sorted(
                (
                    dependent
                    for dependent in outgoing[node]
                    if dependent in unresolved_set and dependent not in visited
                ),
                key=rank.__getitem__,
                reverse=True,
            )
            stack.extend((dependent, False) for dependent in neighbours)

    assigned: set[str] = set()
    components: list[list[str]] = []
    for start in reversed(finish_order):
        if start in assigned:
            continue
        component: list[str] = []
        stack = [(start, False)]
        assigned.add(start)
        while stack:
            node, _expanded = stack.pop()
            component.append(node)
            for predecessor in reverse[node]:
                if predecessor not in assigned:
                    assigned.add(predecessor)
                    stack.append((predecessor, False))
        if len(component) > 1 or start in outgoing[start]:
            component.sort(key=rank.__getitem__)
            components.append(component)

    components.sort(key=lambda component: min(rank[node] for node in component))
    return components


def stable_dependency_sort(
    names: Iterable[str],
    data_dir: Path,
    *,
    primary: Iterable[str] = (),
    implicit: Iterable[str] = (),
    active: Iterable[str] | None = None,
) -> NativeSortResult:
    """Sort plugins by hard constraints while preserving prior order as a tie-breaker."""
    original: list[str] = []
    seen_names: set[str] = set()
    for name in names:
        key = name.casefold()
        if key not in seen_names:
            original.append(name)
            seen_names.add(key)
    actual_by_key = {name.casefold(): name for name in original}
    rank = {name.casefold(): index for index, name in enumerate(original)}
    keys = list(actual_by_key)
    active_keys = (
        set(keys) if active is None else {name.casefold() for name in active}
    )
    outgoing: dict[str, set[str]] = {key: set() for key in keys}
    indegree: dict[str, int] = {key: 0 for key in keys}

    def add_edge(before: str, after: str) -> None:
        before_key = before.casefold()
        after_key = after.casefold()
        if before_key == after_key:
            return
        if before_key not in outgoing or after_key not in outgoing:
            return
        if after_key not in outgoing[before_key]:
            outgoing[before_key].add(after_key)
            indegree[after_key] += 1

    prefix: list[str] = []
    prefix_seen: set[str] = set()
    for declared in (*tuple(primary), *tuple(implicit)):
        actual = actual_by_key.get(declared.casefold())
        if actual is not None and actual.casefold() not in prefix_seen:
            prefix.append(actual)
            prefix_seen.add(actual.casefold())

    for before, after in zip(prefix, prefix[1:]):
        add_edge(before, after)
    if prefix:
        last_prefix = prefix[-1]
        for name in original:
            if name.casefold() not in prefix_seen:
                add_edge(last_prefix, name)

    missing: dict[str, list[str]] = {}
    parse_errors: dict[str, str] = {}
    headers: dict[str, PluginHeader] = {}
    for name in original:
        key = name.casefold()
        header = parse_plugin_header(data_dir / name)
        headers[key] = header
        if header.error and key in active_keys:
            parse_errors[name] = header.error
        for master in header.masters:
            master_actual = actual_by_key.get(master.casefold())
            if key in active_keys and (
                master_actual is None
                or master_actual.casefold() not in active_keys
            ):
                missing.setdefault(name, []).append(master)
            if master_actual is not None:
                add_edge(master_actual, name)

    master_keys = [
        key
        for key in keys
        if headers[key].is_master or actual_by_key[key].casefold().endswith(".esm")
    ]
    master_key_set = set(master_keys)
    nonmaster_keys = [key for key in keys if key not in master_key_set]
    for master_key in master_keys:
        for nonmaster_key in nonmaster_keys:
            add_edge(actual_by_key[master_key], actual_by_key[nonmaster_key])

    available: list[tuple[int, str]] = [
        (rank[key], key) for key, degree in indegree.items() if degree == 0
    ]
    heapq.heapify(available)
    sorted_keys: list[str] = []
    while available:
        _position, key = heapq.heappop(available)
        sorted_keys.append(key)
        for dependent in outgoing[key]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heapq.heappush(available, (rank[dependent], dependent))

    cycles: list[list[str]] = []
    if len(sorted_keys) != len(keys):
        unresolved = [key for key in keys if indegree[key] > 0]
        unresolved.sort(key=rank.__getitem__)
        cycles = [
            [actual_by_key[key] for key in component]
            for component in _cyclic_components(unresolved, outgoing, rank)
            if any(key in active_keys for key in component)
        ]
        sorted_keys.extend(unresolved)

    return NativeSortResult(
        names=[actual_by_key[key] for key in sorted_keys],
        missing_masters=missing,
        cycles=cycles,
        parse_errors=parse_errors,
    )
