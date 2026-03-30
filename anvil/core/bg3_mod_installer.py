"""BG3 Mod Installer — install, activate, deactivate, reorder, uninstall.

Manages the full lifecycle of BG3 mods across three types:
  - STANDARD (pak): .pak files → Mods folder + modsettings.lsx
  - FRAMEWORK: Script Extender etc. → game directory (bin/, root)
  - DATA_OVERRIDE: Loose files → Data/ directory

Uses ModsettingsParser for reading and a custom XML writer that
supports inactive mods (in Mods node but not in ModOrder).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime
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

# Mod types
MOD_TYPE_PAK = "pak"
MOD_TYPE_FRAMEWORK = "framework"
MOD_TYPE_DATA_OVERRIDE = "data_override"


class BG3ModInstaller:
    """Full mod lifecycle manager for Baldur's Gate 3."""

    def __init__(self, game_plugin, instance_path: Path | None = None) -> None:
        self._plugin = game_plugin
        self._mods_path: Path | None = game_plugin.pak_mods_path()
        self._modsettings_path: Path | None = game_plugin.modsettings_path()
        self._game_path: Path | None = getattr(game_plugin, "_game_path", None)
        self._instance_path = instance_path
        self._lspk = LSPKReader()

    # ── Public API ─────────────────────────────────────────────────────

    def check_pak_duplicate(self, archive_path: Path) -> dict | None:
        """Check if a .pak (or archive containing .pak) has a UUID already installed.

        Returns dict with 'name', 'uuid', 'pak_file' of the existing mod, or None.
        """
        if archive_path.suffix.lower() == ".pak":
            meta = self._lspk.read_pak_metadata(archive_path)
            if meta and meta.get("uuid"):
                return self._find_existing_by_uuid(meta["uuid"])
            return None

        # Archive — extract, scan paks, clean up
        extracted = self._extract_archive(archive_path)
        if extracted is None:
            return None
        try:
            for pak in Path(extracted).rglob("*.pak"):
                meta = self._lspk.read_pak_metadata(pak)
                if meta and meta.get("uuid"):
                    existing = self._find_existing_by_uuid(meta["uuid"])
                    if existing:
                        return existing
        finally:
            shutil.rmtree(extracted, ignore_errors=True)
        return None

    def _find_existing_by_uuid(self, uuid: str) -> dict | None:
        """Return existing mod info if UUID is already in state, else None."""
        data = self._read_state()
        for m in data["mods"]:
            if m["uuid"].lower() == uuid.lower():
                return {"name": m.get("name", ""), "uuid": m["uuid"],
                        "pak_file": m.get("pak_file", "")}
        return None

    def install_mod(self, archive_path: Path) -> dict | None:
        """Install a mod from an archive (ZIP/RAR/7z) or a single .pak.

        Detects mod type automatically:
          - Framework (BG3SE etc.): files copied to game directory
          - Standard (pak): .pak to Mods folder + modsettings.lsx entry
          - Data-Override: loose files to Data/ directory

        Returns:
            Dict with name, type, status — or None on error.
        """
        # Single .pak — always standard pak type
        if archive_path.suffix.lower() == ".pak":
            return self._install_pak_single(archive_path)

        # Archive — extract first, then detect type
        extracted = self._extract_archive(archive_path)
        if extracted is None:
            return None

        try:
            return self._install_from_extracted(Path(extracted), archive_path.stem)
        finally:
            shutil.rmtree(extracted, ignore_errors=True)

    def activate_mod(self, uuid: str) -> bool:
        """Move a mod from inactive to active (add to ModOrder)."""
        if self._state_file_path() is None and self._modsettings_path is None:
            return False

        data = self._read_state()
        mod_order = data["mod_order"]
        mods = data["mods"]

        # Check mod exists in Mods node
        if not any(m["uuid"].lower() == uuid.lower() for m in mods):
            # Not in Mods node — try to find metadata from .pak file
            meta = self._find_pak_metadata(uuid)
            if meta is None:
                print(f"bg3_installer: UUID {uuid} not found in Mods or pak files",
                      file=sys.stderr)
                return False
            # Add to Mods node
            mods.append({
                "uuid": meta["uuid"],
                "name": meta.get("name", ""),
                "folder": meta.get("folder", ""),
                "md5": "",
                "version64": meta.get("version", "0") or "0",
                "publish_handle": "0",
            })
            print(f"bg3_installer: added '{meta.get('name', uuid)}' to Mods node",
                  file=sys.stderr)

        # Already active?
        if any(u.lower() == uuid.lower() for u in mod_order):
            return True

        # Add to end of ModOrder
        mod_order.append(uuid)
        self._write_state(mod_order, mods)
        # Auto-deploy: immediately write modsettings.lsx
        self._write_modsettings(mod_order, mods)
        return True

    def insert_mod_at(self, uuid: str, before_uuid: str, activate: bool = True) -> bool:
        """Position a newly installed mod before a reference mod.

        If activate is True, add to ModOrder before before_uuid.
        If activate is False, reposition in the inactive section of the mods list.
        """
        data = self._read_state()
        mod_order = data["mod_order"]
        mods = data["mods"]

        if activate:
            # Ensure mod is in Mods node
            if not any(m["uuid"].lower() == uuid.lower() for m in mods):
                meta = self._find_pak_metadata(uuid)
                if meta is None:
                    return False
                mods.append({
                    "uuid": meta["uuid"],
                    "name": meta.get("name", ""),
                    "folder": meta.get("folder", ""),
                    "md5": "",
                    "version64": meta.get("version", "0") or "0",
                    "publish_handle": "0",
                })

            # Remove from mod_order if already there
            mod_order = [u for u in mod_order if u.lower() != uuid.lower()]

            # Find position of before_uuid in mod_order
            pos = len(mod_order)
            for i, u in enumerate(mod_order):
                if u.lower() == before_uuid.lower():
                    pos = i
                    break

            mod_order.insert(pos, uuid)
            self._write_state(mod_order, mods)
            self._write_modsettings(mod_order, mods)
        else:
            # Reposition in mods list (inactive section ordering)
            entry = None
            remaining = []
            for m in mods:
                if m["uuid"].lower() == uuid.lower() and entry is None:
                    entry = m
                else:
                    remaining.append(m)

            if entry is None:
                return False

            new_mods = []
            inserted = False
            for m in remaining:
                if m["uuid"].lower() == before_uuid.lower() and not inserted:
                    new_mods.append(entry)
                    inserted = True
                new_mods.append(m)
            if not inserted:
                new_mods.append(entry)

            self._write_state(mod_order, new_mods)

        return True

    def deactivate_mod(self, uuid: str) -> bool:
        """Move a mod from active to inactive (remove from ModOrder).

        The mod entry stays in the Mods node so it is not lost.
        """
        if self._state_file_path() is None and self._modsettings_path is None:
            return False

        if is_base_game_mod(uuid):
            print("bg3_installer: cannot deactivate Gustav/GustavDev", file=sys.stderr)
            return False

        data = self._read_state()
        mod_order = data["mod_order"]
        mods = data["mods"]

        # Remove from ModOrder (case-insensitive)
        new_order = [u for u in mod_order if u.lower() != uuid.lower()]
        if len(new_order) == len(mod_order):
            # Was not active
            return True

        self._write_state(new_order, mods)
        # Auto-deploy: immediately write modsettings.lsx
        self._write_modsettings(new_order, mods)
        return True

    def reorder_mods(self, uuid_order: list[str]) -> bool:
        """Set the load order of active mods.

        Preserves the "header" of the current ModOrder — everything up
        to and including the last Gustav/GustavDev entry stays fixed.
        The user-provided uuid_order replaces only the mods after that.
        """
        if self._state_file_path() is None and self._modsettings_path is None:
            return False

        data = self._read_state()
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
        self._write_state(final_order, mods)
        # Auto-deploy: immediately write modsettings.lsx
        self._write_modsettings(final_order, mods)
        return True

    def deploy(self) -> bool:
        """Export bg3_modstate.json to modsettings.lsx for BG3.

        Reads the master state and writes a fresh modsettings.lsx that
        BG3 can read.  BG3 may overwrite it on next launch — that's OK,
        the master state in bg3_modstate.json is unaffected.
        """
        if self._modsettings_path is None:
            print("bg3_installer: modsettings.lsx path not available", file=sys.stderr)
            return False

        data = self._read_state()
        mod_order = data["mod_order"]
        mods = data["mods"]

        if not mod_order and not mods:
            print("bg3_installer: no mods in state, nothing to deploy", file=sys.stderr)
            return False

        # Validate: Gustav/GustavDev must be present in active mods
        has_gustav = any(is_base_game_mod(u) for u in mod_order)
        if not has_gustav:
            print("bg3_installer: Gustav/GustavDev not in active mods!", file=sys.stderr)
            return False

        # Validate: all ModOrder UUIDs have a Mods entry
        mods_uuids = {m["uuid"].lower() for m in mods}
        missing = [u for u in mod_order if u.lower() not in mods_uuids]
        for uuid in missing:
            print(f"bg3_installer: WARNING — UUID {uuid} in ModOrder but not in Mods",
                  file=sys.stderr)

        # Backup existing modsettings.lsx before overwriting
        if self._modsettings_path.is_file():
            backup = self._modsettings_path.parent / "modsettings.lsx.deploy_backup"
            try:
                shutil.copy2(self._modsettings_path, backup)
            except OSError as exc:
                print(f"bg3_installer: backup failed: {exc}", file=sys.stderr)

        # Write modsettings.lsx from master state
        self._write_modsettings(mod_order, mods)

        active_count = len([u for u in mod_order if not is_base_game_mod(u)])
        total_count = len(mods)
        print(
            f"bg3_installer: deploy OK — {active_count} active mods, "
            f"{total_count} total written to modsettings.lsx",
            file=sys.stderr,
        )
        return True

    def repair_modsettings(self) -> dict:
        """Repair the mod state by rescanning all .pak files.

        Reads bg3_modstate.json (or modsettings.lsx as fallback),
        scans the Mods/ folder, merges missing paks, ensures Gustav
        is present, removes duplicates, and rewrites the state.

        Returns:
            Dict with 'backup_path', 'mod_count', 'had_mod_order',
            'gustav_uuid' — or empty dict on error.
        """
        # ── Read current state ────────────────────────────────────
        data = self._read_state()
        had_mod_order = bool(data["mod_order"])
        mods = list(data["mods"])

        # ── Backup state file ────────────────────────────────────
        state_path = self._state_file_path()
        backup = ""
        if state_path and state_path.is_file():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = state_path.parent / f"bg3_modstate.json.repair_backup_{ts}"
            shutil.copy2(state_path, backup_path)
            backup = str(backup_path)
            print(f"bg3_installer: repair backup → {backup_path}", file=sys.stderr)

        # ── Rescan all .pak files in Mods/ folder ─────────────────
        known_uuids = {m["uuid"].lower() for m in mods}
        if self._mods_path and self._mods_path.is_dir():
            for pak in self._mods_path.glob("*.pak"):
                meta = self._lspk.read_pak_metadata(pak)
                if meta and meta.get("uuid"):
                    pak_uuid = meta["uuid"].lower()
                    if pak_uuid not in known_uuids:
                        mods.append({
                            "uuid": meta["uuid"],
                            "name": meta.get("name", pak.stem),
                            "folder": meta.get("folder", ""),
                            "md5": "",
                            "version64": meta.get("version", "0") or "0",
                            "publish_handle": "0",
                            "pak_file": pak.name,
                        })
                        known_uuids.add(pak_uuid)

        # ── Deduplicate mods ──────────────────────────────────────
        unique_mods: list[dict] = []
        seen: set[str] = set()
        for m in mods:
            key = m["uuid"].lower()
            if key not in seen:
                seen.add(key)
                unique_mods.append(m)

        # ── Build ModOrder: Gustav first, then all others ─────────
        gustav_uuid = None
        other_uuids: list[str] = []

        for m in unique_mods:
            if is_base_game_mod(m["uuid"]):
                gustav_uuid = m["uuid"]
            else:
                other_uuids.append(m["uuid"])

        if gustav_uuid is None:
            gustav_uuid = GUSTAVX_UUID

        final_order = [gustav_uuid] + other_uuids

        # ── Write repaired state ──────────────────────────────────
        self._write_state(final_order, unique_mods)

        print(f"bg3_installer: repair done — {len(unique_mods)} mods, "
              f"ModOrder {'reconstructed' if not had_mod_order else 'deduplicated'}",
              file=sys.stderr)

        return {
            "backup_path": backup,
            "mod_count": len(unique_mods),
            "had_mod_order": had_mod_order,
            "gustav_uuid": gustav_uuid,
        }

    def get_mod_list(self) -> dict:
        """Return a unified mod list, data_overrides, and frameworks.

        Every mod has an 'enabled' field (True = in ModOrder / active).
        Active mods come first (in mod_order sequence), then inactive.

        Returns:
            Dict with 'mods' (unified list), 'active_count', 'total_count',
            'data_overrides', 'frameworks'.
        """
        data = self._read_state()
        mod_order = data["mod_order"]
        mods = data["mods"]

        # Build set of active UUIDs (from ModOrder)
        active_uuids = {u.lower() for u in mod_order}

        # Build UUID->mod-info map from state
        mods_by_uuid: dict[str, dict] = {}
        for m in mods:
            mods_by_uuid[m["uuid"].lower()] = m

        # Unified list: active mods first (in mod_order sequence), then inactive
        unified: list[dict] = []

        # Active mods (from ModOrder, preserving order)
        for uuid in mod_order:
            if uuid.lower() in _HIDDEN_UUIDS:
                continue
            info = mods_by_uuid.get(uuid.lower(), {"uuid": uuid, "name": uuid})
            unified.append({**info, "enabled": True})

        # Inactive mods: in Mods node but NOT in ModOrder
        for m in mods:
            m_uuid = m["uuid"].lower()
            if m_uuid in _HIDDEN_UUIDS:
                continue
            if m_uuid in active_uuids:
                continue
            unified.append({**m, "enabled": False})

        active_count = len([u for u in mod_order if u.lower() not in _HIDDEN_UUIDS])
        total_count = len(unified)

        # Data overrides and frameworks
        data_overrides = self.get_data_overrides()
        frameworks = self._get_frameworks()

        return {
            "mods": unified,
            "active_count": active_count,
            "total_count": total_count,
            "data_overrides": data_overrides,
            "frameworks": frameworks,
        }

    def uninstall_mod(self, uuid: str, pak_filename: str) -> bool:
        """Uninstall a mod completely.

        Removes from ModOrder, removes from Mods node, deletes .pak file.
        """
        if self._state_file_path() is None and self._modsettings_path is None:
            return False

        if is_base_game_mod(uuid):
            print("bg3_installer: cannot uninstall Gustav/GustavDev", file=sys.stderr)
            return False

        data = self._read_state()
        mod_order = data["mod_order"]
        mods = data["mods"]

        # Remove from ModOrder
        new_order = [u for u in mod_order if u.lower() != uuid.lower()]

        # Remove from Mods list
        new_mods = [m for m in mods if m["uuid"].lower() != uuid.lower()]

        self._write_state(new_order, new_mods)

        # Delete .pak file
        if self._mods_path and pak_filename:
            pak_path = self._mods_path / pak_filename
            if pak_path.is_file():
                pak_path.unlink()
                print(f"bg3_installer: deleted {pak_path}")

        return True

    # ── Data-Override Management ───────────────────────────────────────

    def get_data_overrides(self) -> list[dict]:
        """Return list of installed data-override mods from manifests."""
        manifest_dir = self._override_manifest_dir()
        if manifest_dir is None or not manifest_dir.is_dir():
            return []
        result: list[dict] = []
        for json_file in sorted(manifest_dir.glob("*.json")):
            manifest = self._load_override_manifest(json_file.stem)
            if manifest:
                result.append(manifest)
        return result

    def uninstall_data_override(self, mod_name: str) -> bool:
        """Remove a data-override mod: delete files from Data/ + manifest."""
        manifest = self._load_override_manifest(mod_name)
        if manifest is None:
            print(f"bg3_installer: no manifest for '{mod_name}'", file=sys.stderr)
            return False

        if self._game_path is None:
            print("bg3_installer: game path not set", file=sys.stderr)
            return False

        # Delete each file
        for rel_path in manifest.get("files", []):
            full = self._game_path / rel_path
            if full.is_file():
                full.unlink()
                print(f"bg3_installer: deleted {full}")

        # Clean up empty directories (bottom-up), stop at game_path
        for rel_path in reversed(manifest.get("files", [])):
            parent = (self._game_path / rel_path).parent
            while parent != self._game_path and parent.is_dir():
                try:
                    parent.rmdir()  # only removes if empty
                except OSError:
                    break
                parent = parent.parent

        # Delete manifest
        manifest_dir = self._override_manifest_dir()
        if manifest_dir:
            json_path = manifest_dir / f"{mod_name}.json"
            if json_path.is_file():
                json_path.unlink()
                print(f"bg3_installer: manifest deleted {json_path}")

        return True

    # ── Mod-Type Detection ─────────────────────────────────────────────

    def detect_mod_type(self, file_list: list[str]) -> tuple[str, object]:
        """Detect mod type from extracted archive contents.

        Args:
            file_list: Relative file paths in the extracted archive.

        Returns:
            Tuple of (mod_type, extra_data):
              - ("framework", FrameworkMod) if framework match found
              - ("pak", None) if .pak files present
              - ("data_override", None) otherwise
        """
        # 1. Check framework patterns
        fw = self._plugin.is_framework_mod(file_list)
        if fw is not None:
            return (MOD_TYPE_FRAMEWORK, fw)

        # 2. Check for .pak files
        has_pak = any(f.lower().endswith(".pak") for f in file_list)
        if has_pak:
            return (MOD_TYPE_PAK, None)

        # 3. Everything else is a data override
        return (MOD_TYPE_DATA_OVERRIDE, None)

    # ── Private: install dispatchers ───────────────────────────────────

    def _install_from_extracted(self, temp_dir: Path, archive_name: str) -> dict | None:
        """Detect type and dispatch to the right installer."""
        # Collect all relative paths in the extracted archive
        file_list = [
            str(f.relative_to(temp_dir))
            for f in temp_dir.rglob("*")
            if f.is_file()
        ]

        if not file_list:
            print("bg3_installer: archive is empty", file=sys.stderr)
            return None

        mod_type, extra = self.detect_mod_type(file_list)

        if mod_type == MOD_TYPE_FRAMEWORK:
            return self._install_framework(temp_dir, extra)
        elif mod_type == MOD_TYPE_PAK:
            return self._install_pak_from_dir(temp_dir)
        else:
            return self._install_data_override(temp_dir, archive_name)

    def _install_pak_single(self, pak_path: Path) -> dict | None:
        """Install a single .pak file (no extraction needed)."""
        if self._mods_path is None:
            print("bg3_installer: Mods folder not found", file=sys.stderr)
            return None

        self._mods_path.mkdir(parents=True, exist_ok=True)

        dest = self._mods_path / pak_path.name
        shutil.copy2(pak_path, dest)

        return self._register_pak_files([dest])

    def _install_pak_from_dir(self, temp_dir: Path) -> dict | None:
        """Install .pak files from an extracted archive."""
        if self._mods_path is None:
            print("bg3_installer: Mods folder not found", file=sys.stderr)
            return None

        self._mods_path.mkdir(parents=True, exist_ok=True)

        pak_files: list[Path] = []
        for pak in temp_dir.rglob("*.pak"):
            dest = self._mods_path / pak.name
            shutil.copy2(pak, dest)
            pak_files.append(dest)

        if not pak_files:
            print("bg3_installer: no .pak files found in archive", file=sys.stderr)
            return None

        result = self._register_pak_files(pak_files)
        if result:
            result["type"] = MOD_TYPE_PAK
        return result

    def _register_pak_files(self, pak_files: list[Path]) -> dict | None:
        """Read metadata from paks and register in state (inactive)."""
        result_name = ""
        result_uuid = ""
        pak_names: list[str] = []

        data = self._read_state()
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
                    "pak_file": pak.name,
                })
                existing_uuids.add(meta["uuid"].lower())

        # Write back — mod is in Mods but NOT in ModOrder (inactive)
        self._write_state(mod_order, mods)

        result = {
            "name": result_name or pak_names[0],
            "type": MOD_TYPE_PAK,
            "uuid": result_uuid,
            "pak_files": pak_names,
            "status": "inactive",
        }
        return result

    def _install_framework(self, temp_dir: Path, fw) -> dict | None:
        """Install a framework mod (e.g. BG3SE) into the game directory."""
        if self._game_path is None:
            print("bg3_installer: game path not set, cannot install framework", file=sys.stderr)
            return None

        target_dir = self._game_path / fw.target if fw.target else self._game_path
        target_dir.mkdir(parents=True, exist_ok=True)

        # Find the framework files using the pattern
        installed_files: list[str] = []
        for src_file in temp_dir.rglob("*"):
            if not src_file.is_file():
                continue
            # Match against framework patterns (case-insensitive)
            rel = str(src_file.relative_to(temp_dir))
            name_lower = src_file.name.lower()

            # Copy files that match the pattern or are in the same directory
            # as a matching file
            matched = any(
                pat.lower() in name_lower or name_lower == pat.lower()
                for pat in fw.pattern
            )
            if matched:
                dest = target_dir / src_file.name
                shutil.copy2(src_file, dest)
                installed_files.append(str(dest.relative_to(self._game_path)))
            else:
                # Also copy sibling files (e.g. .ini configs next to DWrite.dll)
                for pat in fw.pattern:
                    pat_files = list(temp_dir.rglob(pat))
                    if pat_files:
                        pat_parent = pat_files[0].parent
                        if src_file.parent == pat_parent:
                            dest = target_dir / src_file.name
                            shutil.copy2(src_file, dest)
                            installed_files.append(
                                str(dest.relative_to(self._game_path))
                            )
                            break

        print(f"bg3_installer: framework '{fw.name}' installed → {target_dir} "
              f"({len(installed_files)} files)")

        return {
            "name": fw.name,
            "type": MOD_TYPE_FRAMEWORK,
            "target": fw.target,
            "files": installed_files,
            "status": "installed",
        }

    def _install_data_override(self, temp_dir: Path, mod_name: str) -> dict | None:
        """Install a data-override mod: copy loose files to Data/ (or rewritten path)."""
        if self._game_path is None:
            print("bg3_installer: game path not set, cannot install data override", file=sys.stderr)
            return None

        data_dir = self._game_path / "Data"
        data_dir.mkdir(parents=True, exist_ok=True)

        # Path rewrites: some archive paths need to go to bin/ etc. instead of Data/
        rewrites = self._plugin.get_data_override_path_rewrites() if self._plugin else {}

        # Detect common root — if archive has a single top-level folder,
        # strip it so files go directly into Data/
        top_entries = list(temp_dir.iterdir())
        content_root = temp_dir
        if len(top_entries) == 1 and top_entries[0].is_dir():
            content_root = top_entries[0]

        installed_files: list[str] = []
        for src_file in content_root.rglob("*"):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(content_root)
            rel_str = str(rel)

            # Check if this path matches a rewrite rule
            rewritten = False
            for prefix, target in rewrites.items():
                if rel_str.startswith(prefix) or rel_str.replace("\\", "/").startswith(prefix):
                    dest = self._game_path / target / rel_str[len(prefix):]
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest)
                    installed_files.append(str(Path(target) / rel_str[len(prefix):]))
                    rewritten = True
                    break

            if not rewritten:
                dest = data_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest)
                installed_files.append(str(Path("Data") / rel))

        if not installed_files:
            print("bg3_installer: no files to install as data override", file=sys.stderr)
            return None

        # Save manifest for later uninstall
        self._save_override_manifest(mod_name, installed_files)

        print(f"bg3_installer: data override '{mod_name}' installed "
              f"({len(installed_files)} files)")

        return {
            "name": mod_name,
            "type": MOD_TYPE_DATA_OVERRIDE,
            "files": installed_files,
            "status": "installed",
        }

    # ── Data-Override Manifest I/O ─────────────────────────────────────

    def _override_manifest_dir(self) -> Path | None:
        """Return the directory for data-override manifests."""
        if self._instance_path is not None:
            return self._instance_path / ".data_overrides"
        return None

    def _save_override_manifest(self, mod_name: str, files: list[str]) -> None:
        """Write a JSON manifest for a data-override mod."""
        manifest_dir = self._override_manifest_dir()
        if manifest_dir is None:
            print("bg3_installer: no instance_path, cannot save manifest", file=sys.stderr)
            return
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "name": mod_name,
            "files": files,
            "installed_at": str(date.today()),
        }
        json_path = manifest_dir / f"{mod_name}.json"
        json_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_override_manifest(self, mod_name: str) -> dict | None:
        """Read a JSON manifest for a data-override mod."""
        manifest_dir = self._override_manifest_dir()
        if manifest_dir is None:
            return None
        json_path = manifest_dir / f"{mod_name}.json"
        if not json_path.is_file():
            return None
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"bg3_installer: manifest read error: {exc}", file=sys.stderr)
            return None

    # ── Framework helpers ──────────────────────────────────────────────

    def _get_frameworks(self) -> list[dict]:
        """Return installed/available framework mods."""
        result: list[dict] = []
        for fw, installed in self._plugin.get_installed_frameworks():
            result.append({
                "name": fw.name,
                "type": MOD_TYPE_FRAMEWORK,
                "description": fw.description,
                "installed": installed,
                "target": fw.target,
            })
        return result

    # ── Private helpers ────────────────────────────────────────────────

    def _find_pak_metadata(self, uuid: str) -> dict | None:
        """Find metadata for a UUID by scanning .pak files in the Mods folder."""
        if self._mods_path is None or not self._mods_path.is_dir():
            return None
        for pak in self._mods_path.glob("*.pak"):
            meta = self._lspk.read_pak_metadata(pak)
            if meta and meta.get("uuid", "").lower() == uuid.lower():
                return meta
        return None

    # ── State file (bg3_modstate.json) — Master for all mod data ─────

    def _state_file_path(self) -> Path | None:
        """Return path to bg3_modstate.json in the instance directory."""
        if self._instance_path is not None:
            return self._instance_path / "bg3_modstate.json"
        return None

    def _read_state(self) -> dict:
        """Read mod state from bg3_modstate.json (auto-migrates on first use).

        Returns same format as _read_modsettings():
            {"version": {...}, "mod_order": [...], "mods": [...]}
        """
        state_path = self._state_file_path()
        if state_path is None:
            # No instance path — fall back to modsettings.lsx directly
            return self._read_modsettings()

        if not state_path.is_file():
            # First time: migrate from modsettings.lsx + pak scan
            return self._migrate_state()

        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
            mod_order = raw.get("mod_order", [])
            mods = raw.get("mods", [])

            # Fix: ensure all mods are in mod_order (auto-repair)
            mod_order_uuids = {u.lower() for u in mod_order}
            repaired = False
            for m in mods:
                m_uuid = m["uuid"].lower()
                if m_uuid in _HIDDEN_UUIDS or is_base_game_mod(m["uuid"]):
                    continue
                if m_uuid not in mod_order_uuids:
                    mod_order.append(m["uuid"])
                    mod_order_uuids.add(m_uuid)
                    repaired = True
                    print(
                        f"bg3_installer: auto-repair — added missing UUID to mod_order: "
                        f"{m.get('name', '?')} ({m['uuid']})",
                        file=sys.stderr,
                    )
            if repaired:
                self._write_state(mod_order, mods)

            return {
                "version": raw.get("xml_version", {
                    "major": "4", "minor": "7", "revision": "1", "build": "3",
                }),
                "mod_order": mod_order,
                "mods": mods,
            }
        except (json.JSONDecodeError, OSError) as exc:
            print(f"bg3_installer: state read error: {exc}", file=sys.stderr)
            return self._migrate_state()

    def _write_state(
        self,
        mod_order: list[str],
        all_mods: list[dict],
    ) -> None:
        """Write mod state to bg3_modstate.json."""
        state_path = self._state_file_path()
        if state_path is None:
            # No instance path — fall back to modsettings.lsx directly
            self._write_modsettings(mod_order, all_mods)
            return

        # Preserve xml_version from existing state
        xml_version = {"major": "4", "minor": "7", "revision": "1", "build": "3"}
        if state_path.is_file():
            try:
                existing = json.loads(state_path.read_text(encoding="utf-8"))
                xml_version = existing.get("xml_version", xml_version)
            except (json.JSONDecodeError, OSError):
                pass

        state = {
            "format_version": 1,
            "xml_version": xml_version,
            "mod_order": mod_order,
            "mods": all_mods,
        }
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _migrate_state(self) -> dict:
        """Migrate from modsettings.lsx + pak scan to bg3_modstate.json.

        Called automatically on first _read_state() when no state file exists.
        Reads modsettings.lsx, scans the Mods/ folder for unregistered .pak
        files, and creates bg3_modstate.json as the new master.
        """
        # Read whatever is in modsettings.lsx
        data = self._read_modsettings()
        mod_order = list(data["mod_order"])
        mods = list(data["mods"])
        version = data["version"]

        # Build UUID lookup
        known_uuids = {m["uuid"].lower() for m in mods}

        # Build set of UUIDs already in mod_order for quick lookup
        mod_order_uuids = {u.lower() for u in mod_order}

        # Scan Mods/ folder for .pak files not yet registered
        if self._mods_path and self._mods_path.is_dir():
            uuid_to_pak: dict[str, str] = {}
            for pak in self._mods_path.glob("*.pak"):
                meta = self._lspk.read_pak_metadata(pak)
                if meta and meta.get("uuid"):
                    pak_uuid = meta["uuid"].lower()
                    uuid_to_pak[pak_uuid] = pak.name

                    if pak_uuid not in known_uuids:
                        mods.append({
                            "uuid": meta["uuid"],
                            "name": meta.get("name", pak.stem),
                            "folder": meta.get("folder", ""),
                            "md5": "",
                            "version64": meta.get("version", "0") or "0",
                            "publish_handle": "0",
                            "pak_file": pak.name,
                        })
                        known_uuids.add(pak_uuid)
                        # Also add to mod_order so the mod appears as active
                        if pak_uuid not in _HIDDEN_UUIDS and not is_base_game_mod(meta["uuid"]):
                            mod_order.append(meta["uuid"])
                            mod_order_uuids.add(pak_uuid)
                        print(
                            f"bg3_installer: migration — found unregistered pak: "
                            f"{pak.name} ({meta.get('name', '?')})",
                            file=sys.stderr,
                        )

            # Fill in pak_file for existing mods that don't have it
            for m in mods:
                if not m.get("pak_file"):
                    m["pak_file"] = uuid_to_pak.get(m["uuid"].lower(), "")

        # Fix: ensure ALL mods in state are also in mod_order
        # (fixes the 21-missing-UUIDs bug from previous versions)
        for m in mods:
            m_uuid = m["uuid"].lower()
            if m_uuid in _HIDDEN_UUIDS or is_base_game_mod(m["uuid"]):
                continue
            if m_uuid not in mod_order_uuids:
                mod_order.append(m["uuid"])
                mod_order_uuids.add(m_uuid)
                print(
                    f"bg3_installer: migration — added missing UUID to mod_order: "
                    f"{m.get('name', '?')} ({m['uuid']})",
                    file=sys.stderr,
                )

        # Write the new state file
        self._write_state(mod_order, mods)

        count_active = len(mod_order)
        count_total = len(mods)
        print(
            f"bg3_installer: migrated to bg3_modstate.json — "
            f"{count_total} mods, {count_active} active",
            file=sys.stderr,
        )

        return {"version": version, "mod_order": mod_order, "mods": mods}

    # ── Legacy modsettings.lsx I/O (used by migration + deploy) ───────

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

        # ── Deduplicate ModOrder ──────────────────────────────────
        final_order: list[str] = []
        seen_order: set[str] = set()
        for uuid in mod_order:
            key = uuid.strip().lower()
            if key not in seen_order:
                seen_order.add(key)
                final_order.append(uuid.strip())

        # ── Ensure Gustav is in all_mods ──────────────────────────
        all_mods_by_uuid: dict[str, dict] = {}
        for m in all_mods:
            key = m["uuid"].lower()
            if key not in all_mods_by_uuid:  # first wins, no dupes
                all_mods_by_uuid[key] = m
        for uuid in final_order:
            if is_base_game_mod(uuid) and uuid.lower() not in all_mods_by_uuid:
                entry = {
                    "uuid": uuid,
                    "name": "Gustav",
                    "folder": "GustavDev",
                    "md5": "",
                    "version64": "144115207403209032",
                    "publish_handle": "0",
                }
                all_mods_by_uuid[uuid.lower()] = entry

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
            key = uuid.lower()
            if key in written_uuids:
                continue
            attrs = all_mods_by_uuid.get(key)
            if attrs is None:
                attrs = {
                    "uuid": uuid, "name": uuid, "folder": "",
                    "md5": "", "version64": "0", "publish_handle": "0",
                }
            mods_lines.append(self._mod_xml(attrs))
            written_uuids.add(key)

        # Inactive mods (in Mods node but not in ModOrder)
        for mod in all_mods:
            key = mod["uuid"].lower()
            if key not in written_uuids:
                mods_lines.append(self._mod_xml(mod))
                written_uuids.add(key)

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
    def _validate_extracted_paths(target_dir: str, fmt: str) -> None:
        """Post-extraction validation: remove files outside target dir."""
        real_dest = os.path.realpath(target_dir)
        for root, dirs, files in os.walk(real_dest):
            for fname in files:
                fpath = os.path.join(root, fname)
                resolved = os.path.realpath(fpath)
                if not resolved.startswith(real_dest + os.sep) and resolved != real_dest:
                    print(
                        f"bg3_installer: SECURITY — removing {fmt} entry "
                        f"with path traversal: {resolved!r}",
                        file=sys.stderr,
                    )
                    try:
                        os.remove(resolved)
                    except OSError:
                        pass

    @staticmethod
    def _extract_archive(archive_path: Path) -> str | None:
        """Extract an archive to a temp directory. Returns temp dir path."""
        tmp = tempfile.mkdtemp(prefix="bg3_mod_")
        suffix = archive_path.suffix.lower()

        try:
            if suffix == ".zip":
                real_tmp = os.path.realpath(tmp)
                with zipfile.ZipFile(archive_path, "r") as zf:
                    for member in zf.infolist():
                        resolved = os.path.realpath(
                            os.path.join(real_tmp, member.filename)
                        )
                        if not resolved.startswith(real_tmp + os.sep) and resolved != real_tmp:
                            print(
                                f"bg3_installer: SECURITY — skipping zip entry "
                                f"with path traversal: {member.filename!r}",
                                file=sys.stderr,
                            )
                            continue
                        zf.extract(member, tmp)
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
                BG3ModInstaller._validate_extracted_paths(tmp, "RAR")
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
                BG3ModInstaller._validate_extracted_paths(tmp, "7z")
                return tmp

            print(f"bg3_installer: unsupported archive format: {suffix}", file=sys.stderr)
            shutil.rmtree(tmp, ignore_errors=True)
            return None

        except (zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
            print(f"bg3_installer: extraction failed: {exc}", file=sys.stderr)
            shutil.rmtree(tmp, ignore_errors=True)
            return None
