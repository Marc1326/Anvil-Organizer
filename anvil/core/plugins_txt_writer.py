"""plugins.txt generator for Bethesda Creation Engine games.

Scans the game's Data/ directory for .esp/.esm/.esl plugin files and
writes a plugins.txt in the correct Proton prefix location.

Format: UTF-8, \\r\\n line endings, *-prefix for active plugins.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from anvil.core.profile_name import is_valid_profile_name, safe_profile_directory

_TAG = "[PluginsTxtWriter]"

_PLUGIN_EXTENSIONS = {".esp", ".esm", ".esl"}

@dataclass(frozen=True, slots=True)
class PluginEntry:
    """One plugin in a persisted load-order sequence."""

    name: str
    active: bool = True


@dataclass(slots=True)
class PluginSortResult:
    """Native sort output plus diagnostics suitable for the UI."""

    entries: list[PluginEntry]
    missing_masters: dict[str, list[str]]
    cycles: list[list[str]]
    parse_errors: dict[str, str]
    write_error: str = ""


class PluginsTxtWriter:
    """Read, reconcile and persist profile-specific Bethesda plugin state."""

    def __init__(
        self,
        game_plugin,
        game_path: Path,
        instance_path: Path,
        profile_name: str = "Default",
        profiles_path: Path | None = None,
    ) -> None:
        if not is_valid_profile_name(profile_name):
            raise ValueError(f"invalid profile name: {profile_name!r}")
        self._game_plugin = game_plugin
        self._game_path = game_path
        # Zusaetzliche Wurzeln, die beim Plugin-Scan mitgelesen werden.
        self._extra_scan_roots: list[Path] = []
        self._instance_path = instance_path
        self._profiles_path = (
            profiles_path if profiles_path is not None else instance_path / ".profiles"
        )
        self._profile_name = profile_name
        safe_profile_directory(
            instance_path,
            profile_name,
            profiles_root=self._profiles_path,
        )
        self._primary: list[str] = getattr(game_plugin, "PRIMARY_PLUGINS", [])
        self.last_error = ""

    @property
    def profile_plugins_path(self) -> Path:
        """Return Anvil's profile-specific persistent plugin state."""
        return safe_profile_directory(
            self._instance_path,
            self._profile_name,
            profiles_root=self._profiles_path,
        ) / "plugins.txt"

    # ── Private helpers ──────────────────────────────────────────────

    def _remove_case_variants(self, txt_path: Path) -> None:
        """Remove case-variant files (e.g. Plugins.txt vs plugins.txt).

        On Linux, the filesystem is case-sensitive, so both can coexist.
        Proton/Wine gets confused when both exist. Remove any variant
        that doesn't match our exact target filename.
        """
        target_name_lower = txt_path.name.lower()
        parent = txt_path.parent
        if not parent.is_dir():
            return
        try:
            for entry in os.scandir(parent):
                if (
                    entry.is_file()
                    and entry.name.lower() == target_name_lower
                    and entry.name != txt_path.name
                ):
                    try:
                        (parent / entry.name).unlink()
                        print(f"{_TAG} Removed case-variant: {entry.name}")
                    except OSError:
                        pass
        except OSError:
            pass

    # ── Public API ────────────────────────────────────────────────────

    @staticmethod
    def _read_file(path: Path) -> list[PluginEntry]:
        """Read an asterisk-format plugin list, ignoring comments."""
        if not path.is_file():
            return []
        try:
            lines = path.read_text(
                encoding="utf-8-sig", errors="replace"
            ).splitlines()
        except OSError:
            return []

        entries: list[PluginEntry] = []
        seen: set[str] = set()
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            active = line.startswith("*")
            name = line[1:].strip() if active else line
            if Path(name).suffix.lower() not in _PLUGIN_EXTENSIONS:
                continue
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            entries.append(PluginEntry(name=name, active=active))
        return entries

    def read_entries(self) -> list[PluginEntry]:
        """Read and reconcile the current profile's persisted plugin state.

        The profile copy is authoritative. On first use, the game's existing
        plugins.txt is imported. Newly found plugins are appended while the
        order and activation state of existing entries are retained.
        """
        source = self._read_file(self.profile_plugins_path)
        if not source:
            txt_path = self._game_plugin.plugins_txt_path()
            if txt_path is not None:
                source = self._read_file(txt_path)

        scanned = self.scan_plugins()
        actual_by_key = {name.casefold(): name for name in scanned}
        force_primary = getattr(
            self._game_plugin, "ForcePrimaryPluginsActive", True
        )
        primary_keys = (
            {name.casefold() for name in self._primary} if force_primary else set()
        )
        result: list[PluginEntry] = []
        present: set[str] = set()

        for entry in source:
            key = entry.name.casefold()
            actual = actual_by_key.get(key)
            if actual is None or key in present:
                continue
            result.append(
                PluginEntry(actual, True if key in primary_keys else entry.active)
            )
            present.add(key)

        for name in scanned:
            key = name.casefold()
            if key not in present:
                result.append(PluginEntry(name, True))
                present.add(key)

        implicit = self.implicit_plugin_names(result)
        forced_active = primary_keys | {name.casefold() for name in implicit}
        activated = [
            PluginEntry(entry.name, True)
            if entry.name.casefold() in forced_active
            else entry
            for entry in result
        ]
        by_key = {entry.name.casefold(): entry for entry in activated}
        forced_order = [
            *(self._primary if force_primary else []),
            *implicit,
        ]
        ordered: list[PluginEntry] = []
        ordered_keys: set[str] = set()
        for declared in forced_order:
            key = declared.casefold()
            entry = by_key.get(key)
            if entry is not None and key not in ordered_keys:
                ordered.append(entry)
                ordered_keys.add(key)
        ordered.extend(
            entry
            for entry in activated
            if entry.name.casefold() not in ordered_keys
        )
        return ordered

    @staticmethod
    def _serialize_entries(entries: list[PluginEntry]) -> str:
        return "".join(
            f"{'*' if entry.active else ''}{entry.name}\r\n"
            for entry in entries
        )

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(
            f".{path.name}.anvil-{os.getpid()}-{uuid.uuid4().hex}.tmp"
        )
        try:
            temporary.write_text(content, encoding="utf-8", newline="")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _atomic_write_bytes(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(
            f".{path.name}.anvil-{os.getpid()}-{uuid.uuid4().hex}.rollback"
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = -1
        try:
            descriptor = os.open(temporary, flags, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(content)
            temporary.replace(path)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)

    def write_entries(self, entries: list[PluginEntry]) -> Path | None:
        """Persist an exact order to the active Anvil profile and game."""
        self.last_error = ""
        if not entries:
            self.last_error = "refusing to write an empty plugin state"
            print(f"{_TAG} Refusing to write an empty plugin state")
            return None
        txt_path = self._game_plugin.plugins_txt_path()
        if txt_path is None:
            self.last_error = "plugins.txt path is unavailable"
            print(f"{_TAG} No plugins_txt_path — skipping write_entries")
            return None

        content = self._serialize_entries(entries)
        snapshots: dict[Path, bytes | None] = {}
        try:
            for path in (self.profile_plugins_path, txt_path):
                snapshots[path] = path.read_bytes() if path.is_file() else None
            self._atomic_write(self.profile_plugins_path, content)
            self._atomic_write(txt_path, content)
            self._remove_case_variants(txt_path)
        except OSError as exc:
            self.last_error = str(exc)
            rollback_errors: list[str] = []
            for path, previous in snapshots.items():
                try:
                    if previous is None:
                        path.unlink(missing_ok=True)
                    else:
                        self._atomic_write_bytes(path, previous)
                except OSError as rollback_exc:
                    rollback_errors.append(f"{path}: {rollback_exc}")
                    print(f"{_TAG} Rollback failed for {path}: {rollback_exc}")
            if rollback_errors:
                self.last_error += "; rollback incomplete: " + "; ".join(
                    rollback_errors
                )
            print(f"{_TAG} Error writing plugin state: {exc}")
            return None
        print(f"{_TAG} Wrote {len(entries)} profile plugins to {txt_path}")
        return txt_path

    def implicit_plugin_names(self, entries: list[PluginEntry]) -> list[str]:
        """Return declared and detected implicitly loaded plugins in order."""
        from anvil.core.plugin_sorter import read_creation_club_plugins

        creation_path: Path | None = None
        get_creation_path = getattr(self._game_plugin, "creation_club_path", None)
        if callable(get_creation_path):
            configured_path = get_creation_path()
            if isinstance(configured_path, (str, Path)):
                creation_path = Path(configured_path)
        if creation_path is None:
            creation_file = getattr(self._game_plugin, "CreationClubFile", "")
            if creation_file:
                creation_path = self._plugin_file(creation_file)

        actual = {entry.name.casefold(): entry.name for entry in entries}
        implicit: list[str] = []
        seen: set[str] = set()

        def append_if_present(declared: str) -> None:
            name = actual.get(declared.casefold())
            if name is not None and name.casefold() not in seen:
                implicit.append(name)
                seen.add(name.casefold())

        manifest_present = creation_path is not None and creation_path.exists()
        manifest_plugins = read_creation_club_plugins(creation_path)
        for declared in manifest_plugins:
            append_if_present(declared)

        declared_names = {
            str(declared).casefold()
            for declared in getattr(self._game_plugin, "ImplicitPluginNames", ())
        }
        prefixes = tuple(
            str(prefix).casefold()
            for prefix in getattr(self._game_plugin, "ImplicitPluginPrefixes", ())
        )
        for entry in entries:
            key = entry.name.casefold()
            if key in declared_names or (
                not manifest_present and prefixes and key.startswith(prefixes)
            ):
                append_if_present(entry.name)
        return implicit

    def sort_entries(self, entries: list[PluginEntry]) -> PluginSortResult:
        """Sort with Anvil's native hard-constraint dependency graph."""
        from anvil.core.plugin_sorter import stable_dependency_sort

        data_dir = self._data_dirs()[0]
        native = stable_dependency_sort(
            (entry.name for entry in entries),
            data_dir,
            primary=self._primary,
            implicit=self.implicit_plugin_names(entries),
            active=(entry.name for entry in entries if entry.active),
        )
        by_key = {entry.name.casefold(): entry for entry in entries}
        sorted_entries = [
            PluginEntry(name, by_key[name.casefold()].active)
            for name in native.names
        ]
        return PluginSortResult(
            entries=sorted_entries,
            missing_masters=native.missing_masters,
            cycles=native.cycles,
            parse_errors=native.parse_errors,
        )

    def sort_and_write(self) -> PluginSortResult:
        """Sort the active profile and apply only a fully valid result."""
        entries = self.read_entries()
        if not entries:
            data_dir = self._data_dirs()[0]
            return PluginSortResult(
                entries=[],
                missing_masters={},
                cycles=[],
                parse_errors={str(data_dir): "no plugin files found"},
            )
        result = self.sort_entries(entries)
        if not result.missing_masters and not result.cycles and not result.parse_errors:
            if self.write_entries(result.entries) is None:
                result.write_error = self.last_error or "plugin state could not be written"
        return result

    def plugin_indices(self, entries: list[PluginEntry]) -> dict[str, str]:
        """Calculate regular and light load indices for supported games."""
        if getattr(self._game_plugin, "PluginIndexFormat", "") != "regular-light":
            return {entry.name.casefold(): "" for entry in entries}

        from anvil.core.plugin_sorter import parse_plugin_header

        data_dir = self._data_dirs()[0]
        regular_index = 0
        light_index = 0
        result: dict[str, str] = {}
        for entry in entries:
            key = entry.name.casefold()
            if not entry.active:
                result[key] = ""
                continue
            header = parse_plugin_header(data_dir / entry.name)
            is_light = header.is_light or entry.name.casefold().endswith(".esl")
            if is_light:
                result[key] = f"FE:{light_index:03X}"
                light_index += 1
            else:
                result[key] = f"{regular_index:02X}"
                regular_index += 1
        return result

    def set_extra_scan_roots(self, roots) -> None:
        """Weitere Wurzeln fuer den Plugin-Scan, etwa die Overlay-Schicht."""
        self._extra_scan_roots = [Path(r) for r in (roots or [])]

    def _data_dirs(self) -> list[Path]:
        """Alle Verzeichnisse, in denen Plugins liegen koennen.

        Im Overlay-Betrieb steht im Spielordner nichts von den Mods -- wer
        nur dort nachsieht, findet keine Plugins und sortiert ins Leere.
        Hoechste Prioritaet zuerst: die Schicht schlaegt den Spielordner.
        """
        sub = getattr(self._game_plugin, "GameDataPath", "Data")
        kandidaten = [extra / sub for extra in self._extra_scan_roots]
        kandidaten.append(self._game_path / sub)
        return [d for d in kandidaten if d.is_dir()] or [self._game_path / sub]

    def _plugin_file(self, name: str) -> Path:
        """Wo eine bestimmte Plugin-Datei liegt -- Schicht vor Spielordner."""
        for data_dir in self._data_dirs():
            kandidat = data_dir / name
            if kandidat.exists():
                return kandidat
        return self._data_dirs()[0] / name

    def scan_plugins(self) -> list[str]:
        """Scan game_path/Data/ for plugin files.

        Returns a sorted list: primary plugins first (only if present
        on disk), then masters (.esm), then normal plugins (.esp/.esl).
        """
        usable = [d for d in self._data_dirs() if d.is_dir()]
        if not usable:
            print(f"{_TAG} Data directory not found: {self._data_dirs()[0]}")
            return []

        # Collect all plugin files directly in Data/ (not subdirs)
        found_by_key: dict[str, str] = {}
        for data_dir in usable:
            try:
                with os.scandir(data_dir) as directory_entries:
                    ordered_entries = sorted(
                        directory_entries,
                        key=lambda entry: (entry.name.casefold(), entry.name),
                    )
                for entry in ordered_entries:
                    if entry.is_file() and Path(entry.name).suffix.lower() in _PLUGIN_EXTENSIONS:
                        found_by_key.setdefault(entry.name.casefold(), entry.name)
            except OSError as exc:
                print(f"{_TAG} Error scanning {data_dir}: {exc}")

        if not found_by_key:
            print(f"{_TAG} No plugin files found in {usable[0]}")
            return []

        # Build primary list (only plugins that actually exist on disk)
        primary_lower = {p.lower() for p in self._primary}
        found_lower_map = found_by_key

        result: list[str] = []
        for p in self._primary:
            if p.lower() in found_lower_map:
                result.append(found_lower_map[p.lower()])

        # Remaining plugins (not primary)
        remaining = [
            name for key, name in found_by_key.items() if key not in primary_lower
        ]

        # Sort remaining: .esm first, then .esp/.esl
        masters = sorted(
            [f for f in remaining if f.lower().endswith(".esm")],
            key=str.lower,
        )
        others = sorted(
            [f for f in remaining if not f.lower().endswith(".esm")],
            key=str.lower,
        )

        result.extend(masters)
        result.extend(others)
        return result

    def write(self) -> Path | None:
        """Reconcile and persist the active profile's plugin state."""
        entries = self.read_entries()
        if not entries:
            print(f"{_TAG} No plugins found — skipping write")
            return None
        return self.write_entries(entries)
