"""BG3 Mod Installer — install, activate, deactivate, reorder, uninstall.

Manages the full lifecycle of BG3 pak mods:
  - Install from archive (ZIP/RAR/7z) or single .pak
  - Activate / deactivate (ModOrder management)
  - Reorder load order
  - Uninstall (remove from modsettings.lsx + delete .pak)
  - Deploy with validation

Uses ModsettingsParser for reading and a custom XML writer that
supports inactive mods (in Mods node but not in ModOrder).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from anvil.core.lspk_parser import LSPKReader
from anvil.plugins.games.bg3_mod_handler import (
    GUSTAV_UUID,
    GUSTAVX_UUID,
    ModsettingsParser,
    _get_attr_value,
    _get_module_attrs,
    _xml_escape,
    is_base_game_mod,
)

# UUIDs to hide from the user
_HIDDEN_UUIDS = {GUSTAV_UUID.lower(), GUSTAVX_UUID.lower()}


class BG3ModInstaller:
    """Full mod lifecycle manager for Baldur's Gate 3."""

    def __init__(self, game_plugin) -> None:
        self._plugin = game_plugin
        self._mods_path: Path | None = game_plugin.pak_mods_path()
        self._modsettings_path: Path | None = game_plugin.modsettings_path()
        self._lspk = LSPKReader()

    # ── Public API ─────────────────────────────────────────────────────

    def install_mod(self, archive_path: Path) -> dict | None:
        """Install a mod from an archive (ZIP/RAR/7z) or a single .pak.

        The mod is added to modsettings.lsx as INACTIVE (Mods node only,
        not in ModOrder).

        Returns:
            Dict with name, uuid, pak_files, status — or None on error.
        """
        if self._mods_path is None or self._modsettings_path is None:
            print("bg3_installer: Proton prefix not found", file=sys.stderr)
            return None

        self._mods_path.mkdir(parents=True, exist_ok=True)

        # ── Collect .pak files ────────────────────────────────────
        pak_files: list[Path] = []

        if archive_path.suffix.lower() == ".pak":
            # Single .pak — copy directly
            dest = self._mods_path / archive_path.name
            shutil.copy2(archive_path, dest)
            pak_files.append(dest)
        else:
            # Archive — extract, find .pak files, copy them
            extracted = self._extract_archive(archive_path)
            if extracted is None:
                return None
            try:
                for pak in Path(extracted).rglob("*.pak"):
                    dest = self._mods_path / pak.name
                    shutil.copy2(pak, dest)
                    pak_files.append(dest)
            finally:
                shutil.rmtree(extracted, ignore_errors=True)

        if not pak_files:
            print("bg3_installer: no .pak files found in archive", file=sys.stderr)
            return None

        # ── Read metadata + register in modsettings.lsx ───────────
        result_name = ""
        result_uuid = ""
        pak_names: list[str] = []

        data = self._read_modsettings()
        mod_order = data["mod_order"]
        mods = data["mods"]
        existing_uuids = {m["uuid"].lower() for m in mods}

        for pak in pak_files:
            pak_names.append(pak.name)
            meta = self._lspk.read_pak_metadata(pak)
            if meta is None or not meta.get("uuid"):
                continue

            result_name = result_name or meta.get("name", "")
            result_uuid = result_uuid or meta.get("uuid", "")

            # Add to Mods node if not already there
            if meta["uuid"].lower() not in existing_uuids:
                mods.append({
                    "uuid": meta["uuid"],
                    "name": meta.get("name", ""),
                    "folder": meta.get("folder", ""),
                    "md5": "",
                    "version64": meta.get("version", "0") or "0",
                    "publish_handle": "0",
                })
                existing_uuids.add(meta["uuid"].lower())

        # Write back — mod is in Mods but NOT in ModOrder (inactive)
        self._write_modsettings(mod_order, mods)

        return {
            "name": result_name or pak_names[0],
            "uuid": result_uuid,
            "pak_files": pak_names,
            "status": "inactive",
        }

    def activate_mod(self, uuid: str) -> bool:
        """Move a mod from inactive to active (add to ModOrder)."""
        if self._modsettings_path is None:
            return False

        data = self._read_modsettings()
        mod_order = data["mod_order"]
        mods = data["mods"]

        # Check mod exists in Mods node
        if not any(m["uuid"].lower() == uuid.lower() for m in mods):
            print(f"bg3_installer: UUID {uuid} not found in Mods", file=sys.stderr)
            return False

        # Already active?
        if any(u.lower() == uuid.lower() for u in mod_order):
            return True

        # Add to end of ModOrder
        mod_order.append(uuid)
        self._write_modsettings(mod_order, mods)
        return True

    def deactivate_mod(self, uuid: str) -> bool:
        """Move a mod from active to inactive (remove from ModOrder).

        The mod entry stays in the Mods node so it is not lost.
        """
        if self._modsettings_path is None:
            return False

        if is_base_game_mod(uuid):
            print("bg3_installer: cannot deactivate Gustav/GustavDev", file=sys.stderr)
            return False

        data = self._read_modsettings()
        mod_order = data["mod_order"]
        mods = data["mods"]

        # Remove from ModOrder (case-insensitive)
        new_order = [u for u in mod_order if u.lower() != uuid.lower()]
        if len(new_order) == len(mod_order):
            # Was not active
            return True

        self._write_modsettings(new_order, mods)
        return True

    def reorder_mods(self, uuid_order: list[str]) -> bool:
        """Set the load order of active mods.

        Preserves the "header" of the current ModOrder — everything up
        to and including the last Gustav/GustavDev entry stays fixed.
        The user-provided uuid_order replaces only the mods after that.
        """
        if self._modsettings_path is None:
            return False

        data = self._read_modsettings()
        mods = data["mods"]
        current = data["mod_order"]

        # Find the last Gustav position — everything up to there is "header"
        last_gustav_idx = -1
        for i, u in enumerate(current):
            if is_base_game_mod(u):
                last_gustav_idx = i

        header = current[:last_gustav_idx + 1] if last_gustav_idx >= 0 else []

        # User-provided order: filter out any Gustav UUIDs (safety)
        user_mods = [u for u in uuid_order if not is_base_game_mod(u)]

        final_order = header + user_mods
        self._write_modsettings(final_order, mods)
        return True

    def deploy(self) -> bool:
        """Validate and create a final backup of modsettings.lsx."""
        if self._modsettings_path is None:
            print("bg3_installer: modsettings.lsx path not available", file=sys.stderr)
            return False

        if not self._modsettings_path.is_file():
            print("bg3_installer: modsettings.lsx does not exist", file=sys.stderr)
            return False

        data = self._read_modsettings()
        mod_order = data["mod_order"]
        mods = data["mods"]

        # Validate: Gustav/GustavDev must be present in ModOrder
        has_gustav = any(is_base_game_mod(u) for u in mod_order)
        if not has_gustav:
            print("bg3_installer: Gustav/GustavDev not found in ModOrder!", file=sys.stderr)
            return False

        # Validate: all ModOrder UUIDs have a Mods entry
        mods_uuids = {m["uuid"].lower() for m in mods}
        missing = [u for u in mod_order if u.lower() not in mods_uuids]
        for uuid in missing:
            print(f"bg3_installer: WARNING — UUID {uuid} in ModOrder but not in Mods", file=sys.stderr)

        # Final backup
        backup = self._modsettings_path.parent / "modsettings.lsx.deploy_backup"
        shutil.copy2(self._modsettings_path, backup)
        print(f"bg3_installer: deploy OK — backup at {backup}")
        return True

    def get_mod_list(self) -> dict:
        """Return active and inactive mods.

        Active = in ModOrder. Inactive = .pak in Mods folder but not
        in ModOrder. Gustav/GustavDev are filtered out.

        Returns:
            Dict with 'active' and 'inactive' lists.
        """
        data = self._read_modsettings()
        mod_order = data["mod_order"]
        mods = data["mods"]

        # Build set of active UUIDs (from ModOrder)
        active_uuids = {u.lower() for u in mod_order}

        # Build UUID→mod-info map from modsettings
        mods_by_uuid: dict[str, dict] = {}
        for m in mods:
            mods_by_uuid[m["uuid"].lower()] = m

        # Active mods (from ModOrder, with metadata)
        active: list[dict] = []
        for uuid in mod_order:
            if uuid.lower() in _HIDDEN_UUIDS:
                continue
            info = mods_by_uuid.get(uuid.lower(), {"uuid": uuid, "name": uuid})
            active.append(info)

        # Scan Mods folder for all .pak files
        inactive: list[dict] = []
        if self._mods_path and self._mods_path.is_dir():
            for pak in sorted(self._mods_path.glob("*.pak"), key=lambda p: p.name.lower()):
                meta = self._lspk.read_pak_metadata(pak)
                if meta is None or not meta.get("uuid"):
                    # .pak without metadata — show by filename
                    inactive.append({
                        "uuid": "",
                        "name": pak.stem,
                        "folder": "",
                        "filename": pak.name,
                        "source": "pak_only",
                    })
                    continue

                pak_uuid = meta["uuid"].lower()

                # Skip Gustav/GustavDev
                if pak_uuid in _HIDDEN_UUIDS:
                    continue

                # Skip if already active
                if pak_uuid in active_uuids:
                    continue

                # Also skip if registered in Mods node and active
                if pak_uuid in mods_by_uuid and pak_uuid in active_uuids:
                    continue

                inactive.append({
                    "uuid": meta["uuid"],
                    "name": meta.get("name", pak.stem),
                    "folder": meta.get("folder", ""),
                    "author": meta.get("author", ""),
                    "version": meta.get("version", ""),
                    "description": meta.get("description", ""),
                    "filename": pak.name,
                    "dependencies": meta.get("dependencies", []),
                    "source": "pak",
                })

        # Also add mods from Mods node that are not active and not in pak scan
        inactive_uuids = {m.get("uuid", "").lower() for m in inactive if m.get("uuid")}
        for m in mods:
            m_uuid = m["uuid"].lower()
            if m_uuid in _HIDDEN_UUIDS:
                continue
            if m_uuid in active_uuids:
                continue
            if m_uuid in inactive_uuids:
                continue
            inactive.append({
                **m,
                "source": "modsettings_only",
            })

        return {"active": active, "inactive": inactive}

    def uninstall_mod(self, uuid: str, pak_filename: str) -> bool:
        """Uninstall a mod completely.

        Removes from ModOrder, removes from Mods node, deletes .pak file.
        """
        if self._modsettings_path is None:
            return False

        if is_base_game_mod(uuid):
            print("bg3_installer: cannot uninstall Gustav/GustavDev", file=sys.stderr)
            return False

        data = self._read_modsettings()
        mod_order = data["mod_order"]
        mods = data["mods"]

        # Remove from ModOrder
        new_order = [u for u in mod_order if u.lower() != uuid.lower()]

        # Remove from Mods list
        new_mods = [m for m in mods if m["uuid"].lower() != uuid.lower()]

        self._write_modsettings(new_order, new_mods)

        # Delete .pak file
        if self._mods_path and pak_filename:
            pak_path = self._mods_path / pak_filename
            if pak_path.is_file():
                pak_path.unlink()
                print(f"bg3_installer: deleted {pak_path}")

        return True

    # ── Private helpers ────────────────────────────────────────────────

    def _read_modsettings(self) -> dict:
        """Read modsettings.lsx, return defaults if missing."""
        if self._modsettings_path is None or not self._modsettings_path.is_file():
            return {
                "version": {"major": "4", "minor": "7", "revision": "1", "build": "3"},
                "mod_order": [],
                "mods": [],
            }
        return ModsettingsParser.read(self._modsettings_path)

    def _write_modsettings(
        self,
        mod_order: list[str],
        all_mods: list[dict],
    ) -> None:
        """Write modsettings.lsx with separate ModOrder and Mods nodes.

        Unlike ModsettingsWriter.write(), this method supports inactive
        mods: mods that are in the Mods node but NOT in ModOrder.

        Args:
            mod_order: UUIDs for ModOrder (active mods, load order).
            all_mods: ALL mod entries for the Mods node (active + inactive).
        """
        if self._modsettings_path is None:
            return

        path = self._modsettings_path

        # ── Read version from existing file ───────────────────────
        version = {"major": "4", "minor": "7", "revision": "1", "build": "3"}
        if path.is_file():
            existing = ModsettingsParser.read(path)
            version = existing["version"]

        # ── Ensure Gustav is present in ModOrder ───────────────────
        # Respect existing order (some mods like BG3AF must be before Gustav)
        has_gustav = any(is_base_game_mod(u) for u in mod_order)
        if not has_gustav:
            # No Gustav in order — prepend default
            mod_order = [GUSTAVX_UUID] + list(mod_order)

        final_order = list(mod_order)

        # ── Ensure Gustav is in all_mods ──────────────────────────
        all_mods_by_uuid = {m["uuid"].lower(): m for m in all_mods}
        for uuid in final_order:
            if is_base_game_mod(uuid) and uuid.lower() not in all_mods_by_uuid:
                all_mods.insert(0, {
                    "uuid": uuid,
                    "name": "Gustav",
                    "folder": "GustavDev",
                    "md5": "",
                    "version64": "144115207403209032",
                    "publish_handle": "0",
                })
                all_mods_by_uuid[uuid.lower()] = all_mods[0]

        # ── Build ModOrder XML ────────────────────────────────────
        mod_order_lines: list[str] = []
        for uuid in final_order:
            mod_order_lines.append(
                f'            <node id="Module">\n'
                f'              <attribute id="UUID" type="FixedString" '
                f'value="{_xml_escape(uuid.strip())}"/>\n'
                f'            </node>'
            )

        # ── Build Mods XML (all mods: active first, then inactive) ─
        mods_lines: list[str] = []
        written_uuids: set[str] = set()

        # Active mods first (in load order)
        for uuid in final_order:
            attrs = all_mods_by_uuid.get(uuid.lower())
            if attrs is None:
                attrs = {
                    "uuid": uuid, "name": uuid, "folder": "",
                    "md5": "", "version64": "0", "publish_handle": "0",
                }
            mods_lines.append(self._mod_xml(attrs))
            written_uuids.add(uuid.lower())

        # Inactive mods (in Mods node but not in ModOrder)
        for mod in all_mods:
            if mod["uuid"].lower() not in written_uuids:
                mods_lines.append(self._mod_xml(mod))
                written_uuids.add(mod["uuid"].lower())

        # ── Assemble full XML ─────────────────────────────────────
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

        # ── Backup ────────────────────────────────────────────────
        if path.is_file():
            backup = path.parent / "modsettings.lsx.backup"
            try:
                shutil.copy2(path, backup)
            except OSError as exc:
                print(f"bg3_installer: backup failed: {exc}", file=sys.stderr)

        # ── Write ─────────────────────────────────────────────────
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(xml, encoding="utf-8")

    @staticmethod
    def _mod_xml(attrs: dict) -> str:
        """Build XML for a single ModuleShortDesc node."""
        folder = _xml_escape(attrs.get("folder", "").strip())
        md5 = _xml_escape(attrs.get("md5", "").strip())
        name = _xml_escape(attrs.get("name", "").strip())
        pub_handle = attrs.get("publish_handle", "0") or "0"
        uuid_esc = _xml_escape(attrs.get("uuid", "").strip())
        ver64 = attrs.get("version64", "0") or "0"

        return (
            f'            <node id="ModuleShortDesc">\n'
            f'              <attribute id="Folder" type="LSString" value="{folder}"/>\n'
            f'              <attribute id="MD5" type="LSString" value="{md5}"/>\n'
            f'              <attribute id="Name" type="LSString" value="{name}"/>\n'
            f'              <attribute id="PublishHandle" type="uint64" value="{pub_handle}"/>\n'
            f'              <attribute id="UUID" type="FixedString" value="{uuid_esc}"/>\n'
            f'              <attribute id="Version64" type="int64" value="{ver64}"/>\n'
            f'            </node>'
        )

    @staticmethod
    def _extract_archive(archive_path: Path) -> str | None:
        """Extract an archive to a temp directory. Returns temp dir path."""
        tmp = tempfile.mkdtemp(prefix="bg3_mod_")
        suffix = archive_path.suffix.lower()

        try:
            if suffix == ".zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(tmp)
                return tmp

            if suffix == ".rar":
                unrar = shutil.which("unrar")
                if unrar is None:
                    print("bg3_installer: 'unrar' not found — install unrar", file=sys.stderr)
                    shutil.rmtree(tmp, ignore_errors=True)
                    return None
                subprocess.run(
                    [unrar, "x", "-o+", str(archive_path), tmp + "/"],
                    check=True, capture_output=True,
                )
                return tmp

            if suffix == ".7z":
                p7z = shutil.which("7z") or shutil.which("7za")
                if p7z is None:
                    print("bg3_installer: '7z' not found — install p7zip", file=sys.stderr)
                    shutil.rmtree(tmp, ignore_errors=True)
                    return None
                subprocess.run(
                    [p7z, "x", f"-o{tmp}", str(archive_path), "-y"],
                    check=True, capture_output=True,
                )
                return tmp

            print(f"bg3_installer: unsupported archive format: {suffix}", file=sys.stderr)
            shutil.rmtree(tmp, ignore_errors=True)
            return None

        except (zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
            print(f"bg3_installer: extraction failed: {exc}", file=sys.stderr)
            shutil.rmtree(tmp, ignore_errors=True)
            return None
