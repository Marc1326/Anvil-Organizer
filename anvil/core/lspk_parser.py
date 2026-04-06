"""LSPK V18 .pak reader for Baldur's Gate 3.

Read-only parser that extracts meta.lsx / info.json from BG3 .pak files
to obtain mod metadata (UUID, name, folder, author, version, dependencies).

Format reference:
  - Norbyte/lslib PackageFormat.cs (LSPKHeader16, FileEntry18)
  - Norbyte/lslib PackageReader.cs (ReadCompressedFileList)
  - smacx250/BG3 getBg3PakMeta.pl (Perl reference implementation)

Only LSPK V18 (BG3's current format) is supported.
Dependencies: lz4 (pip install lz4)
"""

from __future__ import annotations

import json
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

try:
    import lz4.block
    _HAS_LZ4 = True
except ImportError:
    _HAS_LZ4 = False

# ── Constants ─────────────────────────────────────────────────────────

LSPK_MAGIC = b"LSPK"
LSPK_VERSION = 18

# LSPKHeader16: 36 bytes after the 4-byte magic
#   uint32  Version
#   uint64  FileListOffset
#   uint32  FileListSize
#   uint8   Flags
#   uint8   Priority
#   byte[16] MD5
#   uint16  NumParts
_HEADER_FMT = "<I Q I B B 16s H"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)  # 36

# FileEntry18: 272 bytes per entry
#   byte[256] Name (null-terminated)
#   uint32  OffsetInFile1 (lower 32 bits)
#   uint16  OffsetInFile2 (upper 16 bits)
#   uint8   ArchivePart
#   uint8   Flags (compression)
#   uint32  SizeOnDisk
#   uint32  UncompressedSize
_ENTRY_FMT = "<256s I H B B I I"
_ENTRY_SIZE = struct.calcsize(_ENTRY_FMT)  # 272

# Compression methods (lower 4 bits of Flags)
_COMPRESS_NONE = 0
_COMPRESS_ZLIB = 1
_COMPRESS_LZ4 = 2
_COMPRESS_ZSTD = 3


# ── LSPKReader ────────────────────────────────────────────────────────

class LSPKReader:
    """Read-only LSPK V18 parser for BG3 .pak files."""

    def read_pak_metadata(self, pak_path: Path) -> dict | None:
        """Extract mod metadata from a .pak file.

        Looks for info.json first (simpler), falls back to meta.lsx.

        Returns:
            Dict with uuid, name, folder, author, version, description,
            dependencies — or None on any error.
        """
        if not _HAS_LZ4:
            print("lspk_parser: lz4 not installed (pip install lz4)", file=sys.stderr)
            return None

        try:
            return self._read(pak_path)
        except Exception as exc:
            print(f"lspk_parser: failed to read {pak_path.name}: {exc}", file=sys.stderr)
            return None

    def _read_entries(self, f) -> list[dict] | None:
        """Read and parse all file entries from an open LSPK V18 file.

        Args:
            f: Open file handle, positioned at the start of the .pak.

        Returns:
            List of entry dicts (name, offset, compression, size_on_disk,
            uncompressed_size) — or None on any format error.
        """
        # ── Magic ─────────────────────────────────────────
        magic = f.read(4)
        if magic != LSPK_MAGIC:
            return None

        # ── Header (36 bytes) ─────────────────────────────
        header_data = f.read(_HEADER_SIZE)
        if len(header_data) < _HEADER_SIZE:
            return None

        version, file_list_offset, file_list_size, flags, priority, md5, num_parts = \
            struct.unpack(_HEADER_FMT, header_data)

        if version != LSPK_VERSION:
            return None

        # ── File list (LZ4-compressed) ────────────────────
        f.seek(file_list_offset)
        num_files = struct.unpack("<I", f.read(4))[0]
        compressed_size = struct.unpack("<I", f.read(4))[0]
        compressed_data = f.read(compressed_size)

        if len(compressed_data) < compressed_size:
            return None

        expected_size = _ENTRY_SIZE * num_files
        decompressed = lz4.block.decompress(compressed_data, uncompressed_size=expected_size)

        # ── Parse file entries ────────────────────────────
        entries = []
        for i in range(num_files):
            offset = i * _ENTRY_SIZE
            chunk = decompressed[offset:offset + _ENTRY_SIZE]
            if len(chunk) < _ENTRY_SIZE:
                break

            name_raw, off_low, off_high, arch_part, entry_flags, size_on_disk, uncompressed_size = \
                struct.unpack(_ENTRY_FMT, chunk)

            # Null-terminated name
            name = name_raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
            file_offset = off_low | (off_high << 32)
            compression = entry_flags & 0x0F

            entries.append({
                "name": name,
                "offset": file_offset,
                "compression": compression,
                "size_on_disk": size_on_disk,
                "uncompressed_size": uncompressed_size,
            })

        return entries

    def _read(self, pak_path: Path) -> dict | None:
        with open(pak_path, "rb") as f:
            entries = self._read_entries(f)
            if entries is None:
                return None

            # ── Find target file ──────────────────────────────
            info_json = None
            meta_lsx = None
            for entry in entries:
                lower = entry["name"].lower()
                if lower.endswith("info.json"):
                    info_json = entry
                elif lower.endswith("meta.lsx"):
                    meta_lsx = entry

            target = info_json or meta_lsx
            if target is None:
                return None

            # ── Extract file data ─────────────────────────────
            raw = self._extract_file(f, target)
            if raw is None:
                return None

            # ── Parse metadata ────────────────────────────────
            if target is info_json and info_json is not None:
                return self._parse_info_json(raw)
            return self._parse_meta_lsx(raw)

    def read_pak_full(self, pak_path: Path) -> tuple[dict | None, list[dict]]:
        """Read metadata AND full file list in a single pass.

        Returns:
            (metadata_dict, file_list)
            metadata_dict: like read_pak_metadata() — or None on error
            file_list: [{"rel": "path/file.ext", "size": N}, ...] — or []
        """
        if not _HAS_LZ4:
            return None, []

        try:
            with open(pak_path, "rb") as f:
                entries = self._read_entries(f)
                if entries is None:
                    return None, []

                # Build full file list
                file_list = [
                    {"rel": e["name"], "size": e["uncompressed_size"]}
                    for e in entries
                ]

                # Find metadata (info.json or meta.lsx)
                info_json = None
                meta_lsx = None
                for entry in entries:
                    lower = entry["name"].lower()
                    if lower.endswith("info.json"):
                        info_json = entry
                    elif lower.endswith("meta.lsx"):
                        meta_lsx = entry

                target = info_json or meta_lsx
                metadata = None
                if target is not None:
                    raw = self._extract_file(f, target)
                    if raw is not None:
                        if target is info_json:
                            metadata = self._parse_info_json(raw)
                        else:
                            metadata = self._parse_meta_lsx(raw)

                return metadata, file_list
        except Exception as exc:
            print(f"lspk_parser: read_pak_full failed for {pak_path.name}: {exc}", file=sys.stderr)
            return None, []

    def _extract_file(self, f, entry: dict) -> bytes | None:
        """Read and decompress a single file entry."""
        f.seek(entry["offset"])
        data = f.read(entry["size_on_disk"])
        if len(data) < entry["size_on_disk"]:
            return None

        compression = entry["compression"]
        if compression == _COMPRESS_NONE:
            return data
        if compression == _COMPRESS_ZLIB:
            return zlib.decompress(data)
        if compression == _COMPRESS_LZ4:
            return lz4.block.decompress(data, uncompressed_size=entry["uncompressed_size"])
        print(f"lspk_parser: unsupported compression {compression} for {entry['name']}", file=sys.stderr)
        return None

    @staticmethod
    def _parse_info_json(data: bytes) -> dict | None:
        """Parse BG3 info.json mod metadata."""
        try:
            obj = json.loads(data.decode("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

        # info.json has a "Mods" array with module entries
        mods = obj.get("Mods", [])
        if not mods:
            return None

        mod = mods[0]
        return {
            "uuid": mod.get("UUID", ""),
            "name": mod.get("Name", ""),
            "folder": mod.get("Folder", ""),
            "author": mod.get("Author", ""),
            "version": mod.get("Version", ""),
            "description": mod.get("Description", ""),
            "dependencies": _parse_info_deps(obj),
        }

    @staticmethod
    def _parse_meta_lsx(data: bytes) -> dict | None:
        """Parse BG3 meta.lsx XML (same structure as modsettings.lsx)."""
        try:
            root = ET.fromstring(data.decode("utf-8-sig"))
        except (ET.ParseError, UnicodeDecodeError):
            return None

        # Find ModuleInfo node
        module_info = None
        for node in root.iter("node"):
            if node.get("id") == "ModuleInfo":
                module_info = node
                break
        if module_info is None:
            return None

        def attr_val(parent: ET.Element, attr_id: str) -> str:
            for child in parent:
                if child.tag == "attribute" and child.get("id") == attr_id:
                    return child.get("value", "")
            return ""

        # Dependencies
        deps = []
        for node in root.iter("node"):
            if node.get("id") == "ModuleShortDesc":
                dep_uuid = attr_val(node, "UUID")
                dep_name = attr_val(node, "Name")
                if dep_uuid:
                    deps.append({"uuid": dep_uuid, "name": dep_name})

        return {
            "uuid": attr_val(module_info, "UUID"),
            "name": attr_val(module_info, "Name"),
            "folder": attr_val(module_info, "Folder"),
            "author": attr_val(module_info, "Author"),
            "version": attr_val(module_info, "Version64") or attr_val(module_info, "Version"),
            "description": attr_val(module_info, "Description"),
            "dependencies": deps,
        }


def _parse_info_deps(obj: dict) -> list[dict]:
    """Extract dependencies from info.json MD5 structure."""
    deps = []
    for dep in obj.get("Dependencies", []):
        if isinstance(dep, dict):
            deps.append({
                "uuid": dep.get("UUID", ""),
                "name": dep.get("Name", ""),
            })
    return deps
