"""BG3-specific mod handling: modsettings.lsx, Script Extender, pak scanning.

Ported from the Rust implementation in ~/Projekte/.bg3-mod-manager/
(src-tauri/src/lib.rs).  Uses only stdlib (xml.etree.ElementTree, json)
plus lz4 for LSPK pak parsing.

Features:
  - modsettings.lsx reading and writing (load order)
  - Script Extender detection
  - pak mod scanning with LSPK metadata extraction
  - Unregistered mod detection (by UUID + filename)
"""

from __future__ import annotations

import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# ── Gustav / Base-Game Constants ───────────────────────────────────────

GUSTAV_UUID = "991c9c7a-fb80-40cb-8f0d-b92d4e80e9b1"
GUSTAVX_UUID = "cb555efe-2d9e-131f-8195-a89329d218ea"

GUSTAVDEV_DEFAULT: dict[str, str] = {
    "uuid": GUSTAVX_UUID,
    "name": "Gustav",
    "folder": "GustavDev",
    "md5": "",
    "version64": "144115207403209032",
    "publish_handle": "0",
}

_GUSTAV_UUIDS = {GUSTAV_UUID.lower(), GUSTAVX_UUID.lower()}


def is_base_game_mod(uuid: str) -> bool:
    """Return True if *uuid* is Gustav or GustavDev (base game entry).

    These entries must always be first in the load order and are
    typically hidden from the user in the mod list UI.
    """
    return uuid.strip().lower() in _GUSTAV_UUIDS


# ── XML helpers ────────────────────────────────────────────────────────

def _xml_escape(s: str) -> str:
    """Escape XML special characters in a string."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _get_attr_value(node: ET.Element, attr_id: str) -> str:
    """Find a child ``<attribute id="..." value="..."/>`` and return value."""
    for child in node:
        if child.tag == "attribute" and child.get("id") == attr_id:
            return child.get("value", "")
    return ""


def _get_module_attrs(node: ET.Element) -> dict[str, str]:
    """Extract all ModuleShortDesc attributes from a node."""
    return {
        "uuid": _get_attr_value(node, "UUID"),
        "name": _get_attr_value(node, "Name"),
        "folder": _get_attr_value(node, "Folder"),
        "md5": _get_attr_value(node, "MD5"),
        "version64": _get_attr_value(node, "Version64") or "0",
        "publish_handle": _get_attr_value(node, "PublishHandle") or "0",
    }


def _find_node(root: ET.Element, node_id: str) -> ET.Element | None:
    """Recursively find a ``<node id="...">`` element."""
    for elem in root.iter("node"):
        if elem.get("id") == node_id:
            return elem
    return None


def _get_child_nodes(parent: ET.Element) -> list[ET.Element]:
    """Get ``<node>`` children, handling the ``<children>`` wrapper."""
    # Direct <node> children
    direct = [c for c in parent if c.tag == "node"]
    if direct:
        return direct
    # Wrapped in <children>
    children_elem = parent.find("children")
    if children_elem is not None:
        return [c for c in children_elem if c.tag == "node"]
    return []


# ── ModsettingsParser ─────────────────────────────────────────────────

class ModsettingsParser:
    """Reads modsettings.lsx and extracts mod order + mod metadata."""

    @staticmethod
    def read(path: Path) -> dict:
        """Parse a modsettings.lsx file.

        Tries ``path`` directly, then ``path.parent / modsettings.lsx``
        as fallback (supports both ``Public/modsettings.lsx`` and
        root-level ``modsettings.lsx``).

        Args:
            path: Path to the modsettings.lsx file.

        Returns:
            Dict with keys:
              - ``version``: dict with major, minor, revision, build
              - ``mod_order``: list of UUID strings (load order)
              - ``mods``: list of dicts with uuid, name, folder, md5,
                version64, publish_handle
        """
        default = {
            "version": {"major": "4", "minor": "7", "revision": "1", "build": "3"},
            "mod_order": [],
            "mods": [],
        }

        if not path.is_file():
            return default

        try:
            tree = ET.parse(path)  # noqa: S314
        except (ET.ParseError, OSError) as exc:
            print(f"bg3_mod_handler: cannot parse {path}: {exc}", file=sys.stderr)
            return default

        root = tree.getroot()

        # ── Version ────────────────────────────────────────────────
        version = {"major": "4", "minor": "7", "revision": "1", "build": "3"}
        ver_elem = root.find(".//version")
        if ver_elem is not None:
            for key in ("major", "minor", "revision", "build"):
                val = ver_elem.get(key)
                if val is not None:
                    version[key] = val

        # ── Build UUID → metadata map from all ModuleShortDesc ─────
        by_uuid: dict[str, dict[str, str]] = {}
        for node in root.iter("node"):
            node_id = node.get("id", "")
            if node_id == "ModuleShortDesc":
                attrs = _get_module_attrs(node)
                if attrs["uuid"]:
                    by_uuid[attrs["uuid"]] = attrs

        # ── ModOrder: extract UUID list ────────────────────────────
        mod_order: list[str] = []
        mod_order_node = _find_node(root, "ModOrder")
        if mod_order_node is not None:
            for child in _get_child_nodes(mod_order_node):
                child_id = child.get("id", "")
                if child_id in ("Module", "ModuleShortDesc"):
                    uuid = _get_attr_value(child, "UUID")
                    if uuid:
                        mod_order.append(uuid)

        # Fallback: if no ModOrder, use all ModuleShortDesc in order
        if not mod_order and by_uuid:
            mod_order = list(by_uuid.keys())

        # ── Mods: build ordered list with full metadata ────────────
        # Active mods first (from ModOrder), then remaining inactive mods
        mods: list[dict[str, str]] = []
        seen_uuids: set[str] = set()

        for uuid in mod_order:
            key = uuid.lower()
            if key in seen_uuids:
                continue  # skip duplicates
            seen_uuids.add(key)
            if uuid in by_uuid:
                mods.append(by_uuid[uuid])
            else:
                # UUID in ModOrder but not in Mods — create minimal entry
                name = "Gustav" if is_base_game_mod(uuid) else uuid
                mods.append({
                    "uuid": uuid,
                    "name": name,
                    "folder": "",
                    "md5": "",
                    "version64": "0",
                    "publish_handle": "0",
                })

        # Append mods NOT in ModOrder (inactive) so they aren't lost
        for uuid, attrs in by_uuid.items():
            if uuid.lower() not in seen_uuids:
                mods.append(attrs)
                seen_uuids.add(uuid.lower())

        return {
            "version": version,
            "mod_order": mod_order,
            "mods": mods,
        }


# ── ModsettingsWriter ─────────────────────────────────────────────────

class ModsettingsWriter:
    """Writes modsettings.lsx with proper XML structure and backup."""

    @staticmethod
    def write(path: Path, mod_order: list[str], mods: list[dict]) -> None:
        """Write a modsettings.lsx file.

        Creates a backup of the existing file before overwriting.
        Ensures Gustav/GustavDev is always the first entry.

        Args:
            path: Target path for modsettings.lsx.
            mod_order: List of UUIDs defining load order.
            mods: List of mod dicts (uuid, name, folder, md5,
                  version64, publish_handle).
        """
        # ── Read existing file for version + preserved metadata ────
        version = {"major": "4", "minor": "7", "revision": "1", "build": "3"}
        existing_by_uuid: dict[str, dict[str, str]] = {}

        if path.is_file():
            existing = ModsettingsParser.read(path)
            version = existing["version"]
            for mod in existing["mods"]:
                existing_by_uuid[mod["uuid"]] = mod

        # ── Build mod lookup from provided mods ────────────────────
        mods_by_uuid: dict[str, dict[str, str]] = {}
        for mod in mods:
            mods_by_uuid[mod["uuid"]] = mod

        # ── Ensure Gustav is first ─────────────────────────────────
        gustav_entry: dict[str, str] | None = None
        filtered_order: list[str] = []
        seen: set[str] = set()

        for uuid in mod_order:
            key = uuid.strip().lower()
            if key in seen:
                continue  # skip duplicates
            seen.add(key)
            if is_base_game_mod(uuid):
                # Use provided data, fall back to existing, then defaults
                gustav_entry = (
                    mods_by_uuid.get(uuid)
                    or existing_by_uuid.get(uuid)
                    or dict(GUSTAVDEV_DEFAULT)
                )
            else:
                filtered_order.append(uuid)

        if gustav_entry is None:
            gustav_entry = (
                existing_by_uuid.get(GUSTAVX_UUID)
                or dict(GUSTAVDEV_DEFAULT)
            )

        final_order = [gustav_entry["uuid"]] + filtered_order

        # ── Build ModOrder XML (deduplicated) ──────────────────────
        mod_order_lines: list[str] = []
        written_order: set[str] = set()
        for uuid in final_order:
            key = uuid.strip().lower()
            if key in written_order:
                continue
            written_order.add(key)
            mod_order_lines.append(
                f'            <node id="Module">\n'
                f'              <attribute id="UUID" type="FixedString" '
                f'value="{_xml_escape(uuid.strip())}"/>\n'
                f'            </node>'
            )

        # ── Build Mods XML (deduplicated) ──────────────────────────
        mods_lines: list[str] = []
        written_mods: set[str] = set()
        for uuid in final_order:
            key = uuid.strip().lower()
            if key in written_mods:
                continue
            written_mods.add(key)

            # Priority: provided mods → existing file → defaults
            attrs = (
                mods_by_uuid.get(uuid)
                or existing_by_uuid.get(uuid)
            )
            if attrs is None:
                if is_base_game_mod(uuid):
                    attrs = dict(GUSTAVDEV_DEFAULT)
                else:
                    attrs = {
                        "uuid": uuid,
                        "name": uuid,
                        "folder": uuid,
                        "md5": "",
                        "version64": "0",
                        "publish_handle": "0",
                    }

            folder = _xml_escape(attrs.get("folder", "").strip())
            md5 = _xml_escape(attrs.get("md5", "").strip())
            name = _xml_escape(attrs.get("name", "").strip())
            pub_handle = attrs.get("publish_handle", "0") or "0"
            uuid_esc = _xml_escape(attrs.get("uuid", uuid).strip())
            ver64 = attrs.get("version64", "0") or "0"

            mods_lines.append(
                f'            <node id="ModuleShortDesc">\n'
                f'              <attribute id="Folder" type="LSString" value="{folder}"/>\n'
                f'              <attribute id="MD5" type="LSString" value="{md5}"/>\n'
                f'              <attribute id="Name" type="LSString" value="{name}"/>\n'
                f'              <attribute id="PublishHandle" type="uint64" value="{pub_handle}"/>\n'
                f'              <attribute id="UUID" type="FixedString" value="{uuid_esc}"/>\n'
                f'              <attribute id="Version64" type="int64" value="{ver64}"/>\n'
                f'            </node>'
            )

        # ── Assemble full XML ──────────────────────────────────────
        xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<save>\n'
            f'  <version major="{version["major"]}" minor="{version["minor"]}" '
            f'revision="{version["revision"]}" build="{version["build"]}"/>\n'
            f'  <region id="ModuleSettings">\n'
            f'    <node id="root">\n'
            f'      <children>\n'
            f'        <node id="ModOrder">\n'
            f'          <children>\n'
            f'{chr(10).join(mod_order_lines)}\n'
            f'          </children>\n'
            f'        </node>\n'
            f'        <node id="Mods">\n'
            f'          <children>\n'
            f'{chr(10).join(mods_lines)}\n'
            f'          </children>\n'
            f'        </node>\n'
            f'      </children>\n'
            f'    </node>\n'
            f'  </region>\n'
            f'</save>\n'
        )

        # ── Backup existing file ───────────────────────────────────
        if path.is_file():
            backup = path.parent / "modsettings.lsx.backup"
            try:
                shutil.copy2(path, backup)
            except OSError as exc:
                print(
                    f"bg3_mod_handler: backup failed: {exc}",
                    file=sys.stderr,
                )

        # ── Write ──────────────────────────────────────────────────
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(xml, encoding="utf-8")


# ── BG3 Script Extender ───────────────────────────────────────────────

class BG3ScriptExtender:
    """Detection and configuration for BG3 Script Extender (BG3SE)."""

    @staticmethod
    def detect(game_path: Path) -> bool:
        """Check if BG3 Script Extender is installed.

        Both ``bin/DWrite.dll`` and ``bin/ScriptExtenderSettings.json``
        must exist.

        Args:
            game_path: BG3 game installation directory.

        Returns:
            True if SE is installed.
        """
        bin_dir = game_path / "bin"
        dll = bin_dir / "DWrite.dll"
        settings = bin_dir / "ScriptExtenderSettings.json"
        return dll.is_file() and settings.is_file()

    @staticmethod
    def settings(game_path: Path) -> dict | None:
        """Read ScriptExtenderSettings.json.

        Args:
            game_path: BG3 game installation directory.

        Returns:
            Parsed JSON dict, or None if the file doesn't exist
            or can't be parsed.
        """
        settings_path = game_path / "bin" / "ScriptExtenderSettings.json"
        if not settings_path.is_file():
            return None
        try:
            return json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"bg3_mod_handler: cannot read SE settings: {exc}",
                file=sys.stderr,
            )
            return None

    @staticmethod
    def steam_launch_options() -> str:
        """Return the Steam launch options string for BG3SE on Linux.

        This must be set in Steam → Game Properties → Launch Options
        for the Script Extender to work under Proton.
        """
        return 'WINEDLLOVERRIDES="DWrite.dll=n,b" %command% --skip-launcher'


# ── Pak Mod Scanner ───────────────────────────────────────────────────

def read_pak_info(pak_path: Path) -> dict | None:
    """Read mod metadata from a .pak file via LSPK parser.

    Args:
        pak_path: Path to a BG3 .pak file.

    Returns:
        Dict with uuid, name, folder, author, version, description,
        dependencies — or None if parsing fails.
    """
    from anvil.core.lspk_parser import LSPKReader
    reader = LSPKReader()
    return reader.read_pak_metadata(pak_path)


def scan_pak_mods(mods_path: Path) -> list[dict]:
    """Scan the Mods directory for .pak files with metadata extraction.

    For each .pak, attempts to read LSPK metadata (UUID, name, folder,
    author, version, dependencies) from info.json or meta.lsx inside
    the archive.

    Args:
        mods_path: Path to the BG3 Mods directory.

    Returns:
        Sorted list of dicts with filename, path, size, last_modified,
        and metadata (dict or None).
    """
    if not mods_path.is_dir():
        return []

    result: list[dict] = []

    for pak in sorted(mods_path.glob("*.pak"), key=lambda p: p.name.lower()):
        try:
            stat = pak.stat()
            entry = {
                "filename": pak.name,
                "path": pak,
                "size": stat.st_size,
                "last_modified": int(stat.st_mtime),
                "metadata": read_pak_info(pak),
            }
            result.append(entry)
        except OSError:
            continue

    return result


def find_unregistered_mods(
    pak_mods: list[dict],
    modsettings_mods: list[dict],
) -> list[dict]:
    """Find .pak files that are not registered in modsettings.lsx.

    Uses UUID from pak metadata (if available) for accurate matching,
    with filename-based fallback.

    Args:
        pak_mods: Result from :func:`scan_pak_mods`.
        modsettings_mods: The ``mods`` list from :meth:`ModsettingsParser.read`.

    Returns:
        List of pak_mod dicts that have no matching modsettings entry.
    """
    # Build sets of known identifiers (lowercase for comparison)
    known_uuids = {
        mod.get("uuid", "").strip().lower()
        for mod in modsettings_mods
        if mod.get("uuid")
    }
    known_folders = {
        mod.get("folder", "").lower()
        for mod in modsettings_mods
        if mod.get("folder")
    }
    known_names = {
        mod.get("name", "").lower()
        for mod in modsettings_mods
        if mod.get("name")
    }

    unregistered: list[dict] = []
    for pak in pak_mods:
        # Try UUID match first (most reliable)
        meta = pak.get("metadata")
        if meta and meta.get("uuid"):
            if meta["uuid"].strip().lower() in known_uuids:
                continue
            if meta.get("folder", "").lower() in known_folders:
                continue

        # Fallback: filename stem
        stem = Path(pak["filename"]).stem.lower()
        if stem in known_folders or stem in known_names:
            continue

        unregistered.append(pak)

    return unregistered
