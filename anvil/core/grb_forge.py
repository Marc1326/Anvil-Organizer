"""Native Ghost Recon Breakpoint ``.forge`` and ``.data`` primitives.

The module never loads the game's Windows Oodle DLL.  It validates raw or
natively decoded ``.data`` containers, can rebuild their algorithm-3 payload
blocks through a caller-supplied Linux codec, and stages Forge outputs without
committing them into a game installation.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import stat
import struct
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, Iterable, Sequence


FORGE_MAGIC = b"scimitar"
FORGE_VERSION = 27
CFD_MAGIC = 0x1004FA9957FBAA33
MAX_READER_FILESET_ENTRIES = 100_000
MAX_WRITER_FILESET_ENTRIES = 5000
MAX_FILESETS = 4096
MAX_TOTAL_ENTRIES = 100_000
MAX_TABLE_BYTES = 64 * 1024 * 1024
MAX_DATA_CONTAINER_BYTES = 8 * 1024 * 1024 * 1024
MAX_FORGE_BYTES = 64 * 1024 * 1024 * 1024
MAX_METADATA_BYTES = 16 * 1024 * 1024
MAX_CFD_COMPRESSED_BLOCK = 1024 * 1024
MAX_READ_PAYLOAD_BYTES = 512 * 1024 * 1024
MAX_REBUILD_PAYLOAD_BYTES = 512 * 1024 * 1024
OFFSET_RECORD_SIZE = 20
INFO_RECORD_SIZE = 192
SIDECAR_IDS = frozenset((0x10, 0x91))


class DataContainerError(ValueError):
    """Raised when a GRB ``.data`` container is malformed or unsafe."""


class ForgeFormatError(ValueError):
    """Raised when a GRB Forge archive violates the supported v27 format."""


class ForgePublishedError(ForgeFormatError):
    """Raised after the validated destination was atomically published."""

    def __init__(
        self,
        path: Path,
        message: str,
        *,
        parent_identity: tuple[int, int] | None = None,
        file_identity: tuple[int, int, int, int, int] | None = None,
    ) -> None:
        super().__init__(f"staging Forge was published at {path}, but {message}")
        self.path = path
        self.published = True
        self.parent_identity = parent_identity
        self.file_identity = file_identity


@dataclass(frozen=True)
class DataManifest:
    """Index-level facts available without Oodle decompression."""

    resource_ids: tuple[int, ...]
    resource_sizes: tuple[int, ...]
    version: int
    algorithm: int
    block_size: int
    byte_length: int
    trailer_length: int
    checksum_kind: str
    resource_extensions: tuple[int, ...]
    resource_hashes: tuple[str, ...]


@dataclass(frozen=True)
class _CompressedFileData:
    version: int
    algorithm: int
    block_size: int
    raw: bytes | None
    next_offset: int
    checksum_kinds: frozenset[str]
    uncompressed_size: int


class DataContainer:
    """Read and validate GRB's pair of CompressedFileData streams."""

    @classmethod
    def inspect(
        cls,
        path: str | Path,
        *,
        decoder: Callable[[bytes, int], bytes] | None = None,
    ) -> DataManifest:
        source = Path(path)
        try:
            descriptor = _open_regular_readonly(source, MAX_DATA_CONTAINER_BYTES, "data container")
        except (OSError, ForgeFormatError) as exc:
            raise DataContainerError(f"cannot open data container {source}: {exc}") from exc
        try:
            before = _stable_stat(descriptor)
            manifest = cls.inspect_stream(
                os.fdopen(os.dup(descriptor), "rb"), before[2], decoder=decoder
            )
            if _stable_stat(descriptor) != before:
                raise DataContainerError("data container changed while it was inspected")
            return manifest
        finally:
            os.close(descriptor)

    @classmethod
    def inspect_bytes(
        cls,
        data: bytes,
        *,
        decoder: Callable[[bytes, int], bytes] | None = None,
    ) -> DataManifest:
        import io
        return cls.inspect_stream(io.BytesIO(data), len(data), decoder=decoder)

    @classmethod
    def inspect_stream(
        cls,
        stream: BinaryIO,
        byte_length: int,
        *,
        decoder: Callable[[bytes, int], bytes] | None = None,
    ) -> DataManifest:
        """Validate incrementally and close the supplied owned stream.

        Payload bytes are spooled and never collected in RAM.
        """
        if byte_length < 0 or byte_length > MAX_DATA_CONTAINER_BYTES:
            raise DataContainerError("data container exceeds the supported size limit")
        with stream:
            metadata = cls._read_cfd_stream(
                stream, 0, byte_length, retain_raw=True, raw_limit=MAX_METADATA_BYTES
            )
            if metadata.raw is None or len(metadata.raw) < 2:
                raise DataContainerError("missing raw metadata index")
            count = struct.unpack_from("<H", metadata.raw)[0]
            required = 2 + count * 14
            if required > len(metadata.raw):
                raise DataContainerError("malformed metadata resource table")
            ids: list[int] = []
            sizes: list[int] = []
            for index in range(count):
                class_id, size, flags = struct.unpack_from("<QIH", metadata.raw, 2 + index * 14)
                if flags != 0:
                    raise DataContainerError("unsupported metadata resource flags")
                ids.append(class_id)
                sizes.append(size)
            if not ids or len(ids) != len(set(ids)):
                raise DataContainerError("data container has no resources or duplicate ClassIDs")

            with tempfile.TemporaryFile() as payload_raw:
                try:
                    payloads = cls._read_cfd_stream(
                        stream,
                        metadata.next_offset,
                        byte_length,
                        raw_sink=payload_raw,
                        decoder=decoder,
                    )
                    resource_extensions, resource_hashes = (
                        cls._validate_resource_records(payload_raw, sizes)
                    )
                except DataContainerError as exc:
                    if str(exc) != "compressed index requires the native Oodle decoder":
                        raise
                    payloads = cls._read_cfd_stream(
                        stream, metadata.next_offset, byte_length
                    )
                    resource_extensions = ()
                    resource_hashes = ()
            if sum(sizes) != payloads.uncompressed_size:
                raise DataContainerError(
                    "metadata resource sizes do not match the payload CFD"
                )
            if (metadata.version, metadata.algorithm, metadata.block_size) != (
                payloads.version, payloads.algorithm, payloads.block_size
            ):
                raise DataContainerError("metadata and payload CFD descriptors differ")
            if (metadata.version, metadata.algorithm, metadata.block_size) != (3, 3, 32768):
                raise DataContainerError("GRB data must use version 3 / algorithm 3 / 32768-byte blocks")
            candidates = metadata.checksum_kinds & payloads.checksum_kinds
            if len(candidates) != 1:
                raise DataContainerError("CFDs use mixed or ambiguous checksums")
            trailer_length = byte_length - payloads.next_offset
            if trailer_length:
                if trailer_length > 4096:
                    raise DataContainerError("data container trailer exceeds the size limit")
                stream.seek(payloads.next_offset)
                trailer = _read_data_exact(stream, trailer_length)
                if (
                    not trailer.endswith(b"\0")
                    or b"\0File created using AnvilToolkit v" not in trailer
                ):
                    raise DataContainerError("unknown bytes follow the payload CFD")
            return DataManifest(
                tuple(ids), tuple(sizes), metadata.version, metadata.algorithm,
                metadata.block_size, byte_length, trailer_length, next(iter(candidates)),
                resource_extensions, resource_hashes,
            )

    @staticmethod
    def _validate_resource_records(
        stream: BinaryIO, sizes: list[int]
    ) -> tuple[tuple[int, ...], tuple[str, ...]]:
        """Read the stable ExtensionID prefix of each metadata-delimited record.

        The bytes following that prefix are type-specific; some resources use
        additional envelope fields around the name and payload.
        """
        stream.seek(0)
        extensions: list[int] = []
        hashes: list[str] = []
        for index, expected_size in enumerate(sizes):
            if expected_size < 4:
                raise DataContainerError(f"invalid payload resource size at index {index}")
            prefix = _read_data_exact(stream, 4)
            extension = struct.unpack("<I", prefix)[0]
            extensions.append(extension)
            digest = hashlib.sha256(prefix)
            remaining = expected_size - 4
            while remaining:
                block = _read_data_exact(stream, min(1024 * 1024, remaining))
                digest.update(block)
                remaining -= len(block)
            hashes.append(digest.hexdigest())
        if stream.read(1):
            raise DataContainerError("payload bytes do not match metadata resource sizes")
        return tuple(extensions), tuple(hashes)

    @classmethod
    def append_raw_resource_bytes(
        cls, data: bytes, resource: bytes, extension: int, name: str
    ) -> bytes:
        """Append one raw typed resource while preserving old blocks and ATK bytes."""
        manifest = cls.inspect_bytes(data)
        if not resource or resource[0] != 0 or len(resource) < 13:
            raise DataContainerError("only a complete normal typed resource is supported")
        class_id, embedded_extension = struct.unpack_from("<QI", resource, 1)
        if embedded_extension != extension:
            raise DataContainerError("resource type does not match its extension")
        if class_id in manifest.resource_ids:
            raise DataContainerError(f"resource ClassID 0x{class_id:x} already exists")
        encoded_name = name.encode("latin-1")
        if not encoded_name or len(encoded_name) > 4096:
            raise DataContainerError("resource name must be 1..4096 latin-1 bytes")
        record = struct.pack("<IiI", extension, len(resource), len(encoded_name)) + encoded_name + b"\0" + resource
        if len(record) > 32768:
            raise DataContainerError("raw resource record exceeds one GRB block")

        metadata = cls._read_cfd(data, 0, retain_raw=True)
        payloads = cls._read_cfd(data, metadata.next_offset, retain_raw=False)
        checksum_kind = manifest.checksum_kind
        assert metadata.raw is not None
        count = struct.unpack_from("<H", metadata.raw)[0]
        expected_metadata_size = 2 + count * 14
        if len(metadata.raw) != expected_metadata_size:
            raise DataContainerError(
                "cannot append to a container with extended metadata"
            )
        if count == 0xFFFF:
            raise DataContainerError("metadata resource count is full")
        new_metadata = struct.pack("<H", count + 1) + metadata.raw[2:] + struct.pack("<QIH", class_id, len(record), 0)
        payload_end, payload_header, block_table, block_bytes, block_count = cls._cfd_parts(data, metadata.next_offset)
        new_payload_cfd = b"".join((
            payload_header, struct.pack("<i", block_count + 1), block_table,
            struct.pack("<ii", len(record), len(record)), block_bytes,
            struct.pack("<I", cls._checksum(record, checksum_kind)), record,
        ))
        return cls._encode_raw_cfd(new_metadata, checksum_kind) + new_payload_cfd + data[payload_end:]

    @classmethod
    def repack_raw_bytes(
        cls,
        data: bytes,
        compressor: Callable[[bytes], bytes],
    ) -> bytes:
        """Repack a raw-payload container into game-ready algorithm-3 blocks."""
        manifest = cls.inspect_bytes(data)
        if not manifest.resource_extensions or not manifest.resource_hashes:
            raise DataContainerError("repack requires a deeply validated raw container")
        metadata = cls._read_cfd(data, 0, retain_raw=True)
        payloads = cls._read_cfd(
            data,
            metadata.next_offset,
            retain_raw=True,
            raw_limit=MAX_REBUILD_PAYLOAD_BYTES,
        )
        if metadata.raw is None or payloads.raw is None:
            raise DataContainerError("repack requires raw CFD bytes")
        trailer = data[payloads.next_offset :]
        return (
            cls._encode_raw_cfd(metadata.raw, manifest.checksum_kind)
            + cls._encode_payload_cfd(
                payloads.raw, manifest.checksum_kind, compressor
            )
            + trailer
        )

    @classmethod
    def replace_resource_bytes(
        cls,
        data: bytes,
        resource: bytes,
        decoder: Callable[[bytes, int], bytes],
        compressor: Callable[[bytes], bytes],
    ) -> bytes:
        """Replace one embedded resource and rebuild its payload CFD."""
        if not resource or resource[0] != 0 or len(resource) < 13:
            raise DataContainerError("replacement is not a normal typed resource")
        class_id, extension = struct.unpack_from("<QI", resource, 1)
        manifest = cls.inspect_bytes(data, decoder=decoder)
        try:
            target_index = manifest.resource_ids.index(class_id)
        except ValueError as exc:
            raise DataContainerError(
                f"replacement ClassID 0x{class_id:x} is absent from the container"
            ) from exc
        if manifest.resource_extensions[target_index] != extension:
            raise DataContainerError("replacement type differs from the existing resource")
        if manifest.resource_sizes[target_index] < 13:
            raise DataContainerError("existing resource record is too small")

        metadata = cls._read_cfd(data, 0, retain_raw=True)
        if metadata.raw is None:
            raise DataContainerError("missing DBContainer metadata bytes")
        payload_raw = cls._decode_cfd_bytes(
            data, metadata.next_offset, decoder
        )
        if len(payload_raw) > MAX_REBUILD_PAYLOAD_BYTES:
            raise DataContainerError("decoded DBContainer exceeds the rebuild limit")
        record_offset = sum(manifest.resource_sizes[:target_index])
        old_size = manifest.resource_sizes[target_index]
        old_record = payload_raw[record_offset : record_offset + old_size]
        old_extension, _old_payload_length, name_length = struct.unpack_from(
            "<IiI", old_record, 0
        )
        name_end = 12 + name_length
        if (
            old_extension != extension
            or name_length > 4096
            or name_end >= len(old_record)
            or old_record[name_end] != 0
        ):
            raise DataContainerError("unsupported embedded resource envelope")
        name = old_record[12:name_end]
        body = resource[1:]
        new_record = (
            struct.pack("<IiI", extension, len(body), len(name))
            + name
            + b"\0"
            + body
        )
        new_payload = (
            payload_raw[:record_offset]
            + new_record
            + payload_raw[record_offset + old_size :]
        )
        metadata_raw = bytearray(metadata.raw)
        struct.pack_into(
            "<I", metadata_raw, 2 + target_index * 14 + 8, len(new_record)
        )
        payloads = cls._read_cfd(data, metadata.next_offset, retain_raw=False)
        rebuilt = (
            cls._encode_raw_cfd(bytes(metadata_raw), manifest.checksum_kind)
            + cls._encode_payload_cfd(
                new_payload, manifest.checksum_kind, compressor
            )
            + data[payloads.next_offset :]
        )
        verified = cls.inspect_bytes(rebuilt, decoder=decoder)
        verified_index = verified.resource_ids.index(class_id)
        if verified.resource_ids != manifest.resource_ids:
            raise DataContainerError("rebuilt resource IDs or order changed")
        if verified.resource_extensions != manifest.resource_extensions:
            raise DataContainerError("rebuilt resource types or order changed")
        expected_target_hash = hashlib.sha256(new_record).hexdigest()
        for index, (before_hash, after_hash) in enumerate(
            zip(manifest.resource_hashes, verified.resource_hashes)
        ):
            if index == target_index:
                if after_hash != expected_target_hash:
                    raise DataContainerError(
                        "rebuilt target resource hash failed validation"
                    )
            elif after_hash != before_hash:
                raise DataContainerError(
                    f"non-target resource {index} changed during rebuild"
                )
        if verified.resource_sizes[verified_index] != len(new_record):
            raise DataContainerError("rebuilt resource size failed validation")
        return rebuilt

    @classmethod
    def _decode_cfd_bytes(
        cls,
        data: bytes,
        offset: int,
        decoder: Callable[[bytes, int], bytes],
    ) -> bytes:
        import io

        with tempfile.TemporaryFile() as sink:
            parsed = cls._read_cfd_stream(
                io.BytesIO(data),
                offset,
                len(data),
                raw_sink=sink,
                decoder=decoder,
            )
            if parsed.uncompressed_size > MAX_REBUILD_PAYLOAD_BYTES:
                raise DataContainerError("decoded payload exceeds the rebuild limit")
            sink.seek(0)
            return _read_data_exact(sink, parsed.uncompressed_size)

    @staticmethod
    def _encode_payload_cfd(
        raw: bytes,
        checksum_kind: str,
        compressor: Callable[[bytes], bytes],
    ) -> bytes:
        chunks = [raw[index : index + 32768] for index in range(0, len(raw), 32768)]
        if not chunks:
            raise DataContainerError("cannot encode an empty payload CFD")
        table_parts: list[bytes] = []
        block_parts: list[bytes] = []
        for chunk in chunks:
            try:
                packed = compressor(chunk)
            except Exception as exc:
                raise DataContainerError(f"native Oodle compression failed: {exc}") from exc
            if not isinstance(packed, bytes) or not packed:
                raise DataContainerError("native Oodle compressor returned invalid bytes")
            stored = packed if len(packed) < len(chunk) else chunk
            if len(stored) > MAX_CFD_COMPRESSED_BLOCK:
                raise DataContainerError("compressed CFD block exceeds the size limit")
            table_parts.append(struct.pack("<ii", len(chunk), len(stored)))
            block_parts.append(
                struct.pack("<I", DataContainer._checksum(stored, checksum_kind))
                + stored
            )
        return (
            struct.pack("<QhBHH", CFD_MAGIC, 3, 3, 32768, 32768)
            + struct.pack("<i", len(chunks))
            + b"".join(table_parts)
            + b"".join(block_parts)
        )

    @staticmethod
    def _encode_raw_cfd(raw: bytes, checksum_kind: str) -> bytes:
        chunks = [raw[index:index + 32768] for index in range(0, len(raw), 32768)]
        table = b"".join(struct.pack("<ii", len(chunk), len(chunk)) for chunk in chunks)
        blocks = b"".join(struct.pack("<I", DataContainer._checksum(chunk, checksum_kind)) + chunk for chunk in chunks)
        return struct.pack("<QhBHH", CFD_MAGIC, 3, 3, 32768, 32768) + struct.pack("<i", len(chunks)) + table + blocks

    @staticmethod
    def _checksum(data: bytes, checksum_kind: str) -> int:
        if checksum_kind == "adler32-seed0":
            return zlib.adler32(data, 0) & 0xFFFFFFFF
        if checksum_kind == "crc32":
            return zlib.crc32(data) & 0xFFFFFFFF
        raise DataContainerError(f"unsupported CFD checksum kind {checksum_kind!r}")

    @staticmethod
    def _cfd_parts(data: bytes, offset: int) -> tuple[int, bytes, bytes, bytes, int]:
        parsed = DataContainer._read_cfd(data, offset, retain_raw=False)
        count = struct.unpack_from("<i", data, offset + 15)[0]
        table_at, table_end = offset + 19, offset + 19 + count * 8
        return parsed.next_offset, data[offset:offset + 15], data[table_at:table_end], data[table_end:parsed.next_offset], count

    @classmethod
    def _read_cfd(
        cls,
        data: bytes,
        offset: int,
        *,
        retain_raw: bool,
        raw_limit: int = MAX_METADATA_BYTES,
    ) -> _CompressedFileData:
        import io
        return cls._read_cfd_stream(
            io.BytesIO(data),
            offset,
            len(data),
            retain_raw=retain_raw,
            raw_limit=raw_limit,
        )

    @staticmethod
    def _read_cfd_stream(
        stream: BinaryIO, offset: int, total: int, *, retain_raw: bool = False,
        raw_limit: int = 0, raw_sink: BinaryIO | None = None,
        decoder: Callable[[bytes, int], bytes] | None = None,
    ) -> _CompressedFileData:
        if offset < 0 or offset + 19 > total:
            raise DataContainerError("truncated CompressedFileData header")
        stream.seek(offset)
        header = _read_data_exact(stream, 19)
        magic, version, algorithm, field_a, block_size = struct.unpack_from("<QhBHH", header)
        block_count = struct.unpack_from("<i", header, 15)[0]
        if magic != CFD_MAGIC or field_a != 32768:
            raise DataContainerError("invalid CFD header")
        if block_count < 1 or block_count > 1_000_000 or block_count * 8 > MAX_TABLE_BYTES:
            raise DataContainerError("invalid CFD block count")
        if stream.tell() + block_count * 8 > total:
            raise DataContainerError("truncated CFD block table")
        table = _read_data_exact(stream, block_count * 8)
        blocks: list[tuple[int, int]] = []
        raw_total = 0
        for index in range(block_count):
            uncompressed, compressed = struct.unpack_from("<ii", table, index * 8)
            if (
                uncompressed < 0
                or compressed < 0
                or uncompressed > 32768
                or compressed > MAX_CFD_COMPRESSED_BLOCK
            ):
                raise DataContainerError("invalid CFD block sizes")
            raw_total += uncompressed
            if raw_sink is not None and raw_total > MAX_REBUILD_PAYLOAD_BYTES:
                raise DataContainerError(
                    "decoded CFD payload exceeds the supported size limit"
                )
            if retain_raw and uncompressed != compressed:
                raise DataContainerError(
                    "compressed metadata requires the native Oodle decoder"
                )
            if raw_sink is not None and uncompressed != compressed and decoder is None:
                raise DataContainerError(
                    "compressed index requires the native Oodle decoder"
                )
            if retain_raw and raw_total > raw_limit:
                raise DataContainerError("CFD metadata exceeds the supported size limit")
            blocks.append((uncompressed, compressed))
        candidates = {"adler32-seed0", "crc32"}
        raw_parts: list[bytes] = []
        for uncompressed, compressed in blocks:
            if stream.tell() + 4 + compressed > total:
                raise DataContainerError("truncated CFD block data")
            expected = struct.unpack("<I", _read_data_exact(stream, 4))[0]
            block = _read_data_exact(stream, compressed)
            matches: set[str] = set()
            if zlib.adler32(block, 0) & 0xFFFFFFFF == expected:
                matches.add("adler32-seed0")
            if zlib.crc32(block) & 0xFFFFFFFF == expected:
                matches.add("crc32")
            candidates &= matches
            if not candidates:
                raise DataContainerError("CFD checksum mismatch or mixed checksum kinds")
            if retain_raw:
                raw_parts.append(block)
            if raw_sink is not None:
                if uncompressed == compressed:
                    decoded = block
                else:
                    assert decoder is not None
                    try:
                        decoded = decoder(block, uncompressed)
                    except Exception as exc:
                        raise DataContainerError(
                            f"native Oodle decompression failed: {exc}"
                        ) from exc
                    if len(decoded) != uncompressed:
                        raise DataContainerError(
                            "native Oodle decoder returned the wrong block size"
                        )
                raw_sink.write(decoded)
        return _CompressedFileData(
            version,
            algorithm,
            block_size,
            b"".join(raw_parts) if retain_raw else None,
            stream.tell(),
            frozenset(candidates),
            raw_total,
        )


@dataclass(frozen=True)
class ForgeEntry:
    class_id: int
    offset: int
    length_on_disk: int
    extension: int
    name: str
    info_record: bytes
    fileset_index: int
    local_index: int
    global_index: int


@dataclass(frozen=True)
class ForgeFileSet:
    offset: int
    count: int
    offset_table: int
    info_table: int
    next_offset: int
    range_start: int
    range_end: int


@dataclass(frozen=True)
class ForgeImport:
    path: Path
    extension: int
    name: str

    def __init__(self, path: str | Path, extension: int, name: str) -> None:
        object.__setattr__(self, "path", Path(path))
        object.__setattr__(self, "extension", extension)
        object.__setattr__(self, "name", name)


@dataclass(frozen=True)
class ForgeArchive:
    path: Path
    version: int
    header_size: int
    declared_entry_count: int
    filesets: tuple[ForgeFileSet, ...]
    entries: tuple[ForgeEntry, ...]
    byte_length: int
    identity: tuple[int, int, int, int, int]

    @classmethod
    def read(
        cls, path: str | Path, *, _descriptor: int | None = None
    ) -> "ForgeArchive":
        source = Path(path)
        descriptor: int | None = None
        try:
            if _descriptor is None:
                descriptor = _open_regular_readonly(
                    source, MAX_FORGE_BYTES, "Forge"
                )
            else:
                descriptor = os.dup(_descriptor)
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode):
                    raise ForgeFormatError("Forge descriptor is not a regular file")
                if metadata.st_size > MAX_FORGE_BYTES:
                    raise ForgeFormatError("Forge exceeds the supported size limit")
                os.lseek(descriptor, 0, os.SEEK_SET)
            identity = _stable_stat(descriptor)
            size = identity[2]
            stream = os.fdopen(descriptor, "rb")
        except (OSError, ForgeFormatError) as exc:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            raise ForgeFormatError(f"cannot open forge {source}: {exc}") from exc
        with stream:
            if _read_exact(stream, 8) != FORGE_MAGIC:
                raise ForgeFormatError("missing scimitar magic")
            if _read_exact(stream, 1) != b"\0":
                raise ForgeFormatError("invalid byte after scimitar magic")
            version = _unpack(stream, "<I")[0]
            if version != FORGE_VERSION:
                raise ForgeFormatError(f"unsupported Forge version {version}; expected 27")
            header_size = _unpack(stream, "<q")[0]
            if header_size < 21 or header_size + 44 > size:
                raise ForgeFormatError(f"invalid Forge header size {header_size}")
            stream.seek(header_size)
            declared_count = _unpack(stream, "<i")[0]
            constant = _unpack(stream, "<i")[0]
            reserved = _read_exact(stream, 12)
            _hints = _unpack(stream, "<iii")
            fileset_count = _unpack(stream, "<i")[0]
            first_fileset = _unpack(stream, "<q")[0]
            if constant != 2 or reserved != bytes(12):
                raise ForgeFormatError("unsupported Forge header constants")
            if fileset_count < 1 or fileset_count > MAX_FILESETS:
                raise ForgeFormatError(f"invalid FileSet count {fileset_count}")

            sets: list[ForgeFileSet] = []
            entries: list[ForgeEntry] = []
            visited: set[int] = set()
            fileset_at = first_fileset
            global_index = 0
            previous_nonempty_count = 0
            for set_index in range(fileset_count):
                if fileset_at == -1 or fileset_at in visited:
                    raise ForgeFormatError("broken or cyclic FileSet chain")
                visited.add(fileset_at)
                _require_range(fileset_at, 40, size, "FileSet header")
                stream.seek(fileset_at)
                count, set_constant = _unpack(stream, "<II")
                offset_table, next_offset = _unpack(stream, "<qq")
                range_start, range_end = _unpack(stream, "<II")
                info_table = _unpack(stream, "<q")[0]
                expected_set_constant = 2 if count else 0
                if set_constant != expected_set_constant:
                    raise ForgeFormatError("unsupported FileSet constants")
                if count:
                    if (
                        range_start != global_index
                        or range_end != global_index + count - 1
                    ):
                        raise ForgeFormatError(
                            "FileSet range does not match its entries"
                        )
                    previous_nonempty_count = count
                else:
                    expected_empty_end = (
                        global_index + previous_nonempty_count - 1
                        if previous_nonempty_count
                        else 0xFFFFFFFF
                    )
                    if range_start != global_index or range_end != expected_empty_end:
                        raise ForgeFormatError(
                            "empty FileSet range does not match the preceding span"
                        )
                if count > MAX_READER_FILESET_ENTRIES:
                    raise ForgeFormatError(
                        f"FileSet {set_index} exceeds the reader entry limit"
                    )
                if global_index + count > MAX_TOTAL_ENTRIES:
                    raise ForgeFormatError("Forge exceeds the global entry limit")
                if count * (OFFSET_RECORD_SIZE + INFO_RECORD_SIZE) > MAX_TABLE_BYTES:
                    raise ForgeFormatError("Forge index tables exceed the global size limit")
                _require_range(
                    offset_table, count * OFFSET_RECORD_SIZE, size, "offset table"
                )
                _require_range(info_table, count * INFO_RECORD_SIZE, size, "info table")
                sets.append(
                    ForgeFileSet(
                        fileset_at,
                        count,
                        offset_table,
                        info_table,
                        next_offset,
                        range_start,
                        range_end,
                    )
                )

                stream.seek(offset_table)
                offset_records = _read_exact(stream, count * OFFSET_RECORD_SIZE)
                stream.seek(info_table)
                info_records = _read_exact(stream, count * INFO_RECORD_SIZE)
                for local_index in range(count):
                    offset_at = local_index * OFFSET_RECORD_SIZE
                    data_offset, class_id, length = struct.unpack_from(
                        "<qQI", offset_records, offset_at
                    )
                    info_at = local_index * INFO_RECORD_SIZE
                    info = info_records[info_at : info_at + INFO_RECORD_SIZE]
                    info_length = struct.unpack_from("<I", info, 0)[0]
                    if info_length != length:
                        raise ForgeFormatError(
                            f"length mismatch for entry 0x{class_id:x}: {length} != {info_length}"
                        )
                    expected_next = local_index + 1 if local_index + 1 < count else None
                    expected_previous = local_index - 1 if local_index else 0xFFFFFFFF
                    next_link, previous_link = struct.unpack_from("<II", info, 28)
                    valid_last_links = {0xFFFFFFFF, count}
                    next_is_valid = (
                        next_link == expected_next
                        if expected_next is not None
                        else next_link in valid_last_links
                    )
                    if not next_is_valid or previous_link != expected_previous:
                        raise ForgeFormatError("broken entry Next/Previous chain")
                    extension = struct.unpack_from("<I", info, 16)[0]
                    name_raw = info[44:172].split(b"\0", 1)[0]
                    name = name_raw.decode("latin-1", "replace")
                    _require_range(data_offset, length, size, f"entry 0x{class_id:x}")
                    entries.append(
                        ForgeEntry(
                            class_id,
                            data_offset,
                            length,
                            extension,
                            name,
                            info,
                            set_index,
                            local_index,
                            global_index,
                        )
                    )
                    global_index += 1
                fileset_at = next_offset
            if fileset_at != -1:
                raise ForgeFormatError("FileSet chain is longer than declared")
            regions: list[tuple[int, int, str]] = [(0, header_size + 44, "Forge header")]
            for fileset in sets:
                regions.extend((
                    (fileset.offset, fileset.offset + 40, "FileSet header"),
                    (fileset.offset_table, fileset.offset_table + fileset.count * OFFSET_RECORD_SIZE, "offset table"),
                    (fileset.info_table, fileset.info_table + fileset.count * INFO_RECORD_SIZE, "info table"),
                ))
            regions.extend(
                (entry.offset, entry.offset + entry.length_on_disk, f"payload 0x{entry.class_id:x}")
                for entry in entries if entry.length_on_disk
            )
            regions = sorted(region for region in regions if region[0] != region[1])
            for previous, current in zip(regions, regions[1:]):
                if current[0] < previous[1]:
                    raise ForgeFormatError(f"overlapping Forge regions: {previous[2]} and {current[2]}")
            ids = [entry.class_id for entry in entries]
            if len(ids) != len(set(ids)):
                raise ForgeFormatError("duplicate ClassIDs in Forge index")
            info_keys = [entry.info_record[4:16] for entry in entries]
            if len(info_keys) != len(set(info_keys)):
                raise ForgeFormatError("duplicate 96-bit identities in Forge info records")
            if declared_count != len(entries):
                raise ForgeFormatError(
                    f"header declares {declared_count} entries, index contains {len(entries)}"
                )
            if _stable_stat(stream.fileno()) != identity:
                raise ForgeFormatError("Forge changed while it was parsed")
            return cls(
                source,
                version,
                header_size,
                declared_count,
                tuple(sets),
                tuple(entries),
                size,
                identity,
            )

    def read_payload(self, entry: ForgeEntry) -> bytes:
        if not any(candidate is entry for candidate in self.entries):
            raise ForgeFormatError("entry does not belong to this Forge archive")
        if entry.length_on_disk > MAX_READ_PAYLOAD_BYTES:
            raise ForgeFormatError("payload exceeds the in-memory read limit")
        descriptor: int | None = None
        try:
            descriptor = _open_regular_readonly(self.path, MAX_FORGE_BYTES, "Forge")
            if _stable_stat(descriptor) != self.identity:
                raise ForgeFormatError(
                    "Forge path no longer identifies the validated archive"
                )
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = None
                stream.seek(entry.offset)
                payload = _read_exact(stream, entry.length_on_disk)
                if _stable_stat(stream.fileno()) != self.identity:
                    raise ForgeFormatError("Forge changed while its payload was read")
                return payload
        except (OSError, ForgeFormatError) as exc:
            raise ForgeFormatError(f"cannot read Forge payload: {exc}") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)


@dataclass(frozen=True)
class _PreparedImport:
    class_id: int
    extension: int
    name: str
    path: Path
    length: int
    descriptor: int
    stable_stat: tuple[int, int, int, int, int]
    info_key: bytes


@dataclass(frozen=True)
class _OutputEntry:
    class_id: int
    offset: int
    length: int
    extension: int
    name: str
    info: bytes
    import_descriptor: int | None
    info_key: bytes | None


def _prepare_append_inputs(
    source_path: Path,
    destination_path: Path,
    imports: Sequence[ForgeImport] | Iterable[ForgeImport],
    decoder: Callable[[bytes, int], bytes] | None,
) -> tuple[
    int,
    tuple[int, int, int, int, int],
    ForgeArchive,
    list[_PreparedImport],
    dict[int, _PreparedImport],
    list[_PreparedImport],
    list[ForgeEntry],
    list[ForgeEntry],
    int,
    dict[int, bytes],
    bytes,
]:
    opened: list[int] = []
    prepared: list[_PreparedImport] = []
    try:
        source_descriptor = _open_regular_readonly(
            source_path, MAX_FORGE_BYTES, "source Forge"
        )
        opened.append(source_descriptor)
        source_stat = _stable_stat(source_descriptor)
        if _path_has_inode(destination_path, source_stat[:2]):
            raise ForgeFormatError("append_repoint requires a distinct destination")
        archive = ForgeArchive.read(source_path)
        if archive.identity != source_stat or not _path_has_inode(
            source_path, source_stat[:2]
        ):
            raise ForgeFormatError("source Forge changed while it was opened")
        non_empty = [fileset for fileset in archive.filesets if fileset.count]
        if len(non_empty) != 1 or non_empty[0] != archive.filesets[0]:
            raise ForgeFormatError("writer currently requires one non-empty primary FileSet")

        existing_by_id = {entry.class_id: entry for entry in archive.entries}
        imported_ids: set[int] = set()
        container_local_inner_ids: set[int] = set()
        for request in imports:
            if request.extension < 0 or request.extension > 0xFFFFFFFF:
                raise ForgeFormatError(f"invalid extension id {request.extension}")
            encoded_name = request.name.encode("latin-1")
            if not request.name or len(encoded_name) >= 128:
                raise ForgeFormatError("Forge entry name must be 1..127 latin-1 bytes")
            descriptor = _open_regular_readonly(
                request.path, MAX_DATA_CONTAINER_BYTES, "Forge import"
            )
            opened.append(descriptor)
            stable = _stable_stat(descriptor)
            if stable[:2] == source_stat[:2] or _path_has_inode(
                destination_path, stable[:2]
            ):
                raise ForgeFormatError(
                    "source, destination, and import files must be distinct"
                )
            if any(item.stable_stat[:2] == stable[:2] for item in prepared):
                raise ForgeFormatError("the same import file was supplied more than once")
            with os.fdopen(os.dup(descriptor), "rb") as import_stream:
                manifest = DataContainer.inspect_stream(
                    import_stream, stable[2], decoder=decoder
                )
            class_id = manifest.resource_ids[0]
            if not manifest.resource_extensions:
                raise ForgeFormatError(
                    "compressed Forge import requires native deep validation first"
                )
            if request.extension != manifest.resource_extensions[0]:
                raise ForgeFormatError(
                    "Forge import extension differs from its embedded resource type"
                )
            if class_id in imported_ids:
                raise ForgeFormatError(f"duplicate imported ClassID 0x{class_id:x}")
            if class_id in container_local_inner_ids:
                raise ForgeFormatError(
                    f"outer ClassID 0x{class_id:x} collides with an inner resource"
                )
            for resource_id in manifest.resource_ids[1:]:
                if resource_id in imported_ids:
                    raise ForgeFormatError(
                        f"inner ClassID 0x{resource_id:x} collides with an imported outer entry"
                    )
                if resource_id in existing_by_id:
                    raise ForgeFormatError(
                        f"inner ClassID 0x{resource_id:x} collides with an existing Forge entry"
                    )
                # Inner IDs are scoped by their outer DataContainer. Reuse
                # across containers is valid, but an inner ID must not also
                # become a separate Forge-level entry in this import plan.
                container_local_inner_ids.add(resource_id)
            if any(resource_id in SIDECAR_IDS for resource_id in manifest.resource_ids):
                raise ForgeFormatError("reserved Sidecar ClassID cannot appear in an import")
            if class_id in SIDECAR_IDS:
                raise ForgeFormatError(
                    f"reserved Sidecar ClassID 0x{class_id:x} cannot be imported"
                )
            if manifest.byte_length > 0xFFFFFFFF:
                raise ForgeFormatError("Forge import exceeds the 32-bit entry size limit")
            info_key = (
                _xxhash64(str(request.path).encode("utf-8")).to_bytes(8, "big")
                + bytes(4)
            )
            imported_ids.add(class_id)
            prepared.append(
                _PreparedImport(
                    class_id,
                    request.extension,
                    request.name,
                    request.path,
                    manifest.byte_length,
                    descriptor,
                    stable,
                    info_key,
                )
            )
        if not prepared:
            raise ForgeFormatError("no imports supplied")

        replacements = {
            item.class_id: item for item in prepared if item.class_id in existing_by_id
        }
        additions = [item for item in prepared if item.class_id not in existing_by_id]
        regular = [
            entry for entry in archive.entries if entry.class_id not in SIDECAR_IDS
        ]
        sidecars = [entry for entry in archive.entries if entry.class_id in SIDECAR_IDS]
        final_count = len(regular) + len(additions) + len(sidecars)
        if final_count > MAX_WRITER_FILESET_ENTRIES:
            raise ForgeFormatError("import would require an additional FileSet")
        appended_bytes = sum(item.length for item in replacements.values()) + sum(
            item.length for item in additions
        )
        projected_size = (
            archive.byte_length
            + final_count * (OFFSET_RECORD_SIZE + INFO_RECORD_SIZE)
            + appended_bytes
        )
        if projected_size > MAX_FORGE_BYTES:
            raise ForgeFormatError("staged Forge would exceed the supported size limit")

        templates: dict[int, bytes] = {}
        for entry in archive.entries:
            templates.setdefault(entry.extension, entry.info_record)
        fallback_template = next(
            (
                entry.info_record
                for entry in archive.entries
                if entry.class_id not in SIDECAR_IDS
            ),
            archive.entries[0].info_record if archive.entries else bytes(INFO_RECORD_SIZE),
        )
        return (
            source_descriptor,
            source_stat,
            archive,
            prepared,
            replacements,
            additions,
            regular,
            sidecars,
            final_count,
            templates,
            fallback_template,
        )
    except BaseException:
        for descriptor in reversed(opened):
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise


def append_repoint(
    source: str | Path,
    destination: str | Path,
    imports: Sequence[ForgeImport] | Iterable[ForgeImport],
    *,
    decoder: Callable[[bytes, int], bytes] | None = None,
) -> ForgeArchive:
    """Build and validate a new v27 Forge staging artifact.

    Existing payloads remain where they are.  New parallel index tables and all
    replacement/addition payloads are appended.  The source is never modified,
    and an existing destination is never replaced.
    """

    source_path = Path(source)
    destination_path = Path(destination)
    destination_name = destination_path.name
    if not destination_name or destination_name in {".", ".."}:
        raise ForgeFormatError("invalid staging Forge filename")
    (
        source_descriptor,
        source_stat,
        archive,
        prepared,
        replacements,
        additions,
        regular,
        sidecars,
        final_count,
        templates,
        fallback_template,
    ) = _prepare_append_inputs(source_path, destination_path, imports, decoder)

    parent_descriptor: int | None = None
    temp_fd: int | None = None
    try:
        parent_descriptor = _open_or_create_directory_nofollow(
            destination_path.parent
        )
        parent_stat = os.fstat(parent_descriptor)
        tmpfile_flag = getattr(os, "O_TMPFILE", 0)
        if not tmpfile_flag:
            raise OSError("O_TMPFILE is unavailable on this Linux system")
        temp_fd = os.open(
            ".",
            os.O_RDWR | tmpfile_flag | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=parent_descriptor,
        )
    except BaseException as exc:
        for descriptor in (
            temp_fd,
            parent_descriptor,
            source_descriptor,
            *(item.descriptor for item in prepared),
        ):
            if descriptor is None:
                continue
            try:
                os.close(descriptor)
            except BaseException:
                pass
        if isinstance(exc, OSError):
            raise ForgeFormatError(
                f"cannot create unnamed staging Forge in {destination_path.parent}: {exc}"
            ) from exc
        raise
    published = False
    result: ForgeArchive | None = None
    failure: BaseException | None = None
    parent_identity = (parent_stat.st_dev, parent_stat.st_ino)
    staging_identity: tuple[int, int, int, int, int] | None = None
    published_identity: tuple[int, int, int, int, int] | None = None
    try:
        with os.fdopen(os.dup(source_descriptor), "rb") as source_stream, os.fdopen(
            os.dup(temp_fd), "wb", closefd=True
        ) as temp_stream:
            _copy_exact(source_stream, temp_stream, archive.byte_length)
            temp_stream.flush()
        if _stable_stat(source_descriptor) != source_stat:
            raise ForgeFormatError("source Forge changed while it was copied")
        table_start = archive.byte_length
        output_table_size = final_count * OFFSET_RECORD_SIZE
        info_table_start = table_start + output_table_size
        payload_cursor = info_table_start + final_count * INFO_RECORD_SIZE

        output: list[_OutputEntry] = []
        for old_entry in regular:
            replacement = replacements.get(old_entry.class_id)
            if replacement is None:
                output.append(
                    _OutputEntry(
                        old_entry.class_id,
                        old_entry.offset,
                        old_entry.length_on_disk,
                        old_entry.extension,
                        old_entry.name,
                        old_entry.info_record,
                        None,
                        None,
                    )
                )
            else:
                output.append(
                    _OutputEntry(
                        replacement.class_id,
                        payload_cursor,
                        replacement.length,
                        replacement.extension,
                        replacement.name,
                        old_entry.info_record,
                        replacement.descriptor,
                        None,
                    )
                )
                payload_cursor += replacement.length
        for addition in additions:
            output.append(
                _OutputEntry(
                    addition.class_id,
                    payload_cursor,
                    addition.length,
                    addition.extension,
                    addition.name,
                    templates.get(addition.extension, fallback_template),
                    addition.descriptor,
                    addition.info_key,
                )
            )
            payload_cursor += addition.length
        for sidecar in sidecars:
            output.append(
                _OutputEntry(
                    sidecar.class_id,
                    sidecar.offset,
                    sidecar.length_on_disk,
                    sidecar.extension,
                    sidecar.name,
                    sidecar.info_record,
                    None,
                    None,
                )
            )

        offset_table = bytearray()
        info_table = bytearray()
        for index, entry in enumerate(output):
            offset_table += struct.pack("<qQI", entry.offset, entry.class_id, entry.length)
            info_table += _updated_info_record(entry, index, final_count)

        with os.fdopen(os.dup(temp_fd), "r+b") as stream:
            stream.seek(table_start)
            stream.write(offset_table)
            stream.write(info_table)
            prepared_by_fd = {item.descriptor: item for item in prepared}
            for entry in output:
                if entry.import_descriptor is None:
                    continue
                item = prepared_by_fd[entry.import_descriptor]
                os.lseek(item.descriptor, 0, os.SEEK_SET)
                with os.fdopen(os.dup(item.descriptor), "rb") as payload:
                    _copy_exact(payload, stream, item.length)
                if _stable_stat(item.descriptor) != item.stable_stat:
                    raise ForgeFormatError(f"import changed while it was copied: {item.path}")
            stream.seek(archive.header_size)
            stream.write(struct.pack("<i", final_count))
            stream.seek(archive.header_size + 20)
            stream.write(struct.pack("<iii", -1, final_count, final_count))
            primary = archive.filesets[0]
            stream.seek(archive.header_size + 32)
            stream.write(struct.pack("<iq", 1, primary.offset))
            stream.seek(primary.offset)
            stream.write(
                struct.pack(
                    "<IIqqIIq",
                    final_count,
                    2,
                    table_start,
                    -1,
                    0,
                    final_count - 1,
                    info_table_start,
                )
            )
            stream.flush()
            os.fsync(stream.fileno())

        staging_identity = _stable_stat(temp_fd)
        if not _path_has_directory_inode(destination_path.parent, parent_identity):
            raise ForgeFormatError("staging parent directory changed during validation")
        staged = ForgeArchive.read(destination_path, _descriptor=temp_fd)
        if staged.identity != staging_identity:
            raise ForgeFormatError("unnamed staging file changed during validation")
        expected_ids = [entry.class_id for entry in output]
        if [entry.class_id for entry in staged.entries] != expected_ids:
            raise ForgeFormatError("staged Forge index does not match the import plan")
        try:
            _publish_unnamed_file(
                temp_fd, parent_descriptor, destination_name
            )
        except OSError as exc:
            raise ForgeFormatError(
                f"cannot publish exclusive staging Forge {destination_path}: {exc}"
            ) from exc
        published = True
        os.fsync(parent_descriptor)
        published_identity = _stable_stat(temp_fd)
        if not _dir_entry_has_inode(
            parent_descriptor, destination_name, published_identity[:2]
        ) or not _path_has_directory_inode(destination_path.parent, parent_identity):
            raise ForgeFormatError(
                "published Forge no longer resolves through the requested parent"
            )
        result = ForgeArchive(
            destination_path,
            staged.version,
            staged.header_size,
            staged.declared_entry_count,
            staged.filesets,
            staged.entries,
            staged.byte_length,
            published_identity,
        )
    except BaseException as exc:
        failure = exc
    finally:
        if failure is not None and staging_identity is not None:
            try:
                published = os.fstat(temp_fd).st_nlink > 0
            except BaseException:
                # If fstat itself is interrupted, the anchored directory entry
                # still proves that this exact staging inode was published.
                try:
                    published = published or _dir_entry_has_inode(
                        parent_descriptor, destination_name, staging_identity[:2]
                    )
                except BaseException:
                    # Both kernel-state probes failed while handling another
                    # failure.  Preserve cleanup and fail closed: publication
                    # may have happened, so callers must take the recovery path.
                    published = True
        for descriptor in (
            temp_fd,
            parent_descriptor,
            source_descriptor,
            *(item.descriptor for item in prepared),
        ):
            try:
                os.close(descriptor)
            except BaseException as exc:
                if failure is None:
                    failure = exc
    if failure is not None:
        if published:
            identity = published_identity or staging_identity
            raise ForgePublishedError(
                destination_path,
                str(failure),
                parent_identity=parent_identity,
                file_identity=identity,
            ) from failure
        raise failure
    if result is None:
        raise ForgeFormatError("staging Forge build produced no result")
    return result


def _updated_info_record(entry: _OutputEntry, index: int, count: int) -> bytes:
    record = bytearray(entry.info)
    if len(record) != INFO_RECORD_SIZE:
        raise ForgeFormatError("invalid Forge info template size")
    struct.pack_into("<I", record, 0, entry.length)
    if entry.info_key is not None:
        if len(entry.info_key) != 12:
            raise ForgeFormatError("invalid Forge info identity size")
        record[4:16] = entry.info_key
    struct.pack_into("<I", record, 16, entry.extension)
    struct.pack_into("<I", record, 28, index + 1 if index + 1 < count else 0xFFFFFFFF)
    struct.pack_into("<I", record, 32, index - 1 if index else 0xFFFFFFFF)
    record[44:172] = bytes(128)
    encoded = entry.name.encode("latin-1")
    record[44 : 44 + len(encoded)] = encoded
    return bytes(record)


def _xxhash64(data: bytes, seed: int = 0) -> int:
    mask = 0xFFFFFFFFFFFFFFFF
    prime1 = 11400714785074694791
    prime2 = 14029467366897019727
    prime3 = 1609587929392839161
    prime4 = 9650029242287828579
    prime5 = 2870177450012600261

    def rotate_left(value: int, count: int) -> int:
        return ((value << count) | (value >> (64 - count))) & mask

    def round_value(accumulator: int, value: int) -> int:
        accumulator = (accumulator + value * prime2) & mask
        accumulator = rotate_left(accumulator, 31)
        return (accumulator * prime1) & mask

    offset = 0
    length = len(data)
    if length >= 32:
        value1 = (seed + prime1 + prime2) & mask
        value2 = (seed + prime2) & mask
        value3 = seed & mask
        value4 = (seed - prime1) & mask
        limit = length - 32
        while offset <= limit:
            value1 = round_value(value1, struct.unpack_from("<Q", data, offset)[0])
            value2 = round_value(value2, struct.unpack_from("<Q", data, offset + 8)[0])
            value3 = round_value(value3, struct.unpack_from("<Q", data, offset + 16)[0])
            value4 = round_value(value4, struct.unpack_from("<Q", data, offset + 24)[0])
            offset += 32
        result = (
            rotate_left(value1, 1)
            + rotate_left(value2, 7)
            + rotate_left(value3, 12)
            + rotate_left(value4, 18)
        ) & mask
        for value in (value1, value2, value3, value4):
            result ^= round_value(0, value)
            result = (result * prime1 + prime4) & mask
    else:
        result = (seed + prime5) & mask

    result = (result + length) & mask
    while offset + 8 <= length:
        lane = round_value(0, struct.unpack_from("<Q", data, offset)[0])
        result ^= lane
        result = (rotate_left(result, 27) * prime1 + prime4) & mask
        offset += 8
    if offset + 4 <= length:
        result ^= struct.unpack_from("<I", data, offset)[0] * prime1
        result &= mask
        result = (rotate_left(result, 23) * prime2 + prime3) & mask
        offset += 4
    while offset < length:
        result ^= data[offset] * prime5
        result &= mask
        result = (rotate_left(result, 11) * prime1) & mask
        offset += 1

    result ^= result >> 33
    result = (result * prime2) & mask
    result ^= result >> 29
    result = (result * prime3) & mask
    result ^= result >> 32
    return result & mask


def _read_data_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise DataContainerError(f"unexpected end of data container (wanted {size}, got {len(data)})")
    return data


def _open_regular_readonly(path: Path, maximum: int, label: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ForgeFormatError(f"{label} is not a regular file")
        if metadata.st_size < 0 or metadata.st_size > maximum:
            raise ForgeFormatError(f"{label} exceeds the supported size limit")
        return descriptor
    except BaseException:
        try:
            os.close(descriptor)
        except BaseException:
            pass
        raise


def _stable_stat(descriptor: int) -> tuple[int, int, int, int, int]:
    value = os.fstat(descriptor)
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def _publish_unnamed_file(
    descriptor: int, parent_descriptor: int, name: str
) -> None:
    linkat = ctypes.CDLL(None, use_errno=True).linkat
    linkat.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    linkat.restype = ctypes.c_int
    if linkat(
        descriptor,
        b"",
        parent_descriptor,
        os.fsencode(name),
        0x1000,  # AT_EMPTY_PATH
    ) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), name)


def _open_or_create_directory_nofollow(path: Path) -> int:
    absolute = Path(os.path.abspath(path))
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(os.sep, flags)
    try:
        for component in absolute.parts[1:]:
            try:
                next_descriptor = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
                next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _dir_entry_has_inode(
    parent_descriptor: int, name: str, inode: tuple[int, int]
) -> bool:
    try:
        value = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except (FileNotFoundError, OSError):
        return False
    return stat.S_ISREG(value.st_mode) and (value.st_dev, value.st_ino) == inode


def _path_has_directory_inode(path: Path, inode: tuple[int, int]) -> bool:
    try:
        value = path.stat()
    except (FileNotFoundError, OSError):
        return False
    return stat.S_ISDIR(value.st_mode) and (value.st_dev, value.st_ino) == inode


def _path_has_inode(path: Path, inode: tuple[int, int]) -> bool:
    try:
        value = path.lstat()
    except (FileNotFoundError, OSError):
        return False
    return stat.S_ISREG(value.st_mode) and (value.st_dev, value.st_ino) == inode


def _copy_exact(source: BinaryIO, destination: BinaryIO, length: int) -> None:
    remaining = length
    while remaining:
        block = source.read(min(1024 * 1024, remaining))
        if not block:
            raise ForgeFormatError("input file shrank while it was copied")
        destination.write(block)
        remaining -= len(block)
    if source.read(1):
        raise ForgeFormatError("input file grew while it was copied")


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise ForgeFormatError(f"unexpected end of file (wanted {size}, got {len(data)})")
    return data


def _unpack(stream: BinaryIO, fmt: str) -> tuple[int, ...]:
    return struct.unpack(fmt, _read_exact(stream, struct.calcsize(fmt)))


def _require_range(offset: int, length: int, total: int, label: str) -> None:
    if offset < 0 or length < 0 or offset > total or length > total - offset:
        raise ForgeFormatError(
            f"{label} points outside Forge: offset={offset}, length={length}, size={total}"
        )
