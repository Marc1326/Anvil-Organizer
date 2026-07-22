"""Tests for the native Ghost Recon Breakpoint Forge backend."""

from __future__ import annotations

import hashlib
import os
import struct
import sys
import tempfile
import threading
import time
import unittest
import zlib
from pathlib import Path
from unittest import mock

import anvil.core.grb_forge as grb_forge
from anvil.core.grb_forge import (
    DataContainer,
    DataContainerError,
    ForgeArchive,
    ForgeFormatError,
    ForgeImport,
    ForgePublishedError,
    _xxhash64,
    append_repoint,
)
from anvil.core.grb_oodle import (
    NativeOodle,
    OodleLibraryError,
    _apply_worker_limits,
)


CFD_MAGIC = 0x1004FA9957FBAA33
ENTITY_BUILDER = zlib.crc32(b"EntityBuilder")
MESH = zlib.crc32(b"Mesh")


def _adler0(data: bytes) -> int:
    return zlib.adler32(data, 0) & 0xFFFFFFFF


def _cfd(raw: bytes, *, algorithm: int = 3) -> bytes:
    return b"".join(
        (
            struct.pack("<QhBHH", CFD_MAGIC, 3, algorithm, 32768, 32768),
            struct.pack("<i", 1),
            struct.pack("<ii", len(raw), len(raw)),
            struct.pack("<I", _adler0(raw)),
            raw,
        )
    )


def _cfd_blocks(raw: bytes, *, crc32: bool = False, split: int = 7) -> bytes:
    chunks = [raw[index : index + split] for index in range(0, len(raw), split)]
    checksum = zlib.crc32 if crc32 else _adler0
    table = b"".join(struct.pack("<ii", len(chunk), len(chunk)) for chunk in chunks)
    blocks = b"".join(
        struct.pack("<I", checksum(chunk) & 0xFFFFFFFF) + chunk
        for chunk in chunks
    )
    return (
        struct.pack("<QhBHH", CFD_MAGIC, 3, 3, 32768, 32768)
        + struct.pack("<i", len(chunks))
        + table
        + blocks
    )


def _data_container(class_id: int, extension: int, name: str) -> bytes:
    payload = (
        struct.pack("<IiI", extension, 1 + 8 + 4, len(name))
        + name.encode("ascii")
        + b"\0"
        + b"\0"
        + struct.pack("<QI", class_id, extension)
    )
    metadata = struct.pack("<HQIH", 1, class_id, len(payload), 0)
    return _cfd(metadata) + _cfd(payload)


def _info(length: int, extension: int, name: str, index: int, count: int) -> bytes:
    record = bytearray(192)
    struct.pack_into("<I", record, 0, length)
    identity = hashlib.sha256(
        struct.pack("<III", length, extension, index) + name.encode("latin-1")
    ).digest()[:12]
    record[4:16] = identity
    struct.pack_into("<I", record, 16, extension)
    struct.pack_into("<I", record, 28, index + 1 if index + 1 < count else 0xFFFFFFFF)
    struct.pack_into("<I", record, 32, index - 1 if index else 0xFFFFFFFF)
    encoded = name.encode("latin-1")
    record[44 : 44 + len(encoded)] = encoded
    record[172:] = bytes.fromhex("04 00 00 00 00 00 00 00 00 00 00 00 04 00 00 00 00 00 00 00")
    return bytes(record)


def _forge(entries: list[tuple[int, int, str, bytes]]) -> bytes:
    header = bytearray(1094)
    header[:8] = b"scimitar"
    struct.pack_into("<I", header, 9, 27)
    struct.pack_into("<Q", header, 13, 1050)
    struct.pack_into("<I", header, 1050, len(entries))
    struct.pack_into("<I", header, 1054, 2)
    struct.pack_into("<I", header, 1082, 1)
    struct.pack_into("<q", header, 1086, 1094)

    fileset = bytearray(40)
    offset_table_at = 1094 + len(fileset)
    info_table_at = offset_table_at + len(entries) * 20
    payload_at = info_table_at + len(entries) * 192
    range_end = len(entries) - 1 if entries else 0xFFFFFFFF
    struct.pack_into(
        "<IIqqIIq",
        fileset,
        0,
        len(entries),
        2 if entries else 0,
        offset_table_at,
        -1,
        0,
        range_end,
        info_table_at,
    )

    offsets = bytearray()
    infos = bytearray()
    payloads = bytearray()
    cursor = payload_at
    for index, (class_id, extension, name, payload) in enumerate(entries):
        offsets += struct.pack("<qQI", cursor, class_id, len(payload))
        infos += _info(len(payload), extension, name, index, len(entries))
        payloads += payload
        cursor += len(payload)
    return bytes(header + fileset + offsets + infos + payloads)


class ForgeHashTests(unittest.TestCase):
    def test_xxhash64_reference_vectors(self) -> None:
        self.assertEqual(_xxhash64(b""), 0xEF46DB3751D8E999)
        self.assertEqual(_xxhash64(b"a"), 0xD24EC4F1A98C6E5B)
        self.assertEqual(_xxhash64(b"abc"), 0x44BC2CF5AD770999)


class DataContainerTests(unittest.TestCase):
    def test_reads_class_ids_and_validates_seed_zero_adler(self) -> None:
        data = _data_container(0x123456789ABC, ENTITY_BUILDER, "WG_Test")
        manifest = DataContainer.inspect_bytes(data)
        self.assertEqual(manifest.resource_ids, (0x123456789ABC,))
        self.assertEqual(manifest.algorithm, 3)
        self.assertEqual(manifest.version, 3)
        self.assertEqual(manifest.block_size, 32768)

    def test_rejects_bad_block_checksum(self) -> None:
        data = bytearray(_data_container(7, ENTITY_BUILDER, "WG_Bad"))
        data[27] ^= 0xFF
        with self.assertRaises(DataContainerError):
            DataContainer.inspect_bytes(bytes(data))

    def test_rejects_compressed_size_mismatch_and_oversized_block(self) -> None:
        class_id = 0x1234
        metadata = struct.pack("<HQIH", 1, class_id, 10, 0)
        compressed = b"test"
        payload = (
            struct.pack("<QhBHH", CFD_MAGIC, 3, 3, 32768, 32768)
            + struct.pack("<i", 1)
            + struct.pack("<ii", 9, len(compressed))
            + struct.pack("<I", _adler0(compressed))
            + compressed
        )
        with self.assertRaisesRegex(DataContainerError, "resource sizes"):
            DataContainer.inspect_bytes(_cfd(metadata) + payload)

        oversized = (
            struct.pack("<QhBHH", CFD_MAGIC, 3, 3, 32768, 32768)
            + struct.pack("<i", 1)
            + struct.pack("<ii", 1, 1024 * 1024 + 1)
        )
        with self.assertRaisesRegex(DataContainerError, "block sizes"):
            DataContainer.inspect_bytes(oversized)

    def test_rejects_aggregate_decoded_payload_over_limit(self) -> None:
        block_count = 16_385
        block_size = 32_768
        expected_size = block_count * block_size
        metadata = struct.pack("<HQIH", 1, 0x1234, expected_size, 0)
        payload = (
            struct.pack("<QhBHH", CFD_MAGIC, 3, 3, block_size, block_size)
            + struct.pack("<i", block_count)
            + struct.pack("<ii", block_size, 1) * block_count
        )
        decoder_called = False

        def decoder(_packed: bytes, _raw_size: int) -> bytes:
            nonlocal decoder_called
            decoder_called = True
            return b""

        with self.assertRaisesRegex(DataContainerError, "decoded CFD payload"):
            DataContainer.inspect_bytes(_cfd(metadata) + payload, decoder=decoder)
        self.assertFalse(decoder_called)

    def test_accepts_extended_metadata_and_multiblock_crc32(self) -> None:
        class_id = 0x1234
        resource = b"\0" + struct.pack("<QI", class_id, ENTITY_BUILDER)
        name = b"WG_CRC"
        payload = (
            struct.pack("<IiI", ENTITY_BUILDER, len(resource), len(name))
            + name
            + b"\0"
            + resource
        )
        metadata = struct.pack("<HQIH", 1, class_id, len(payload), 0) + b"X" * 98
        manifest = DataContainer.inspect_bytes(
            _cfd_blocks(metadata, crc32=True) + _cfd_blocks(payload, crc32=True)
        )
        self.assertEqual(manifest.resource_ids, (class_id,))
        self.assertEqual(manifest.checksum_kind, "crc32")
        self.assertEqual(manifest.resource_extensions, (ENTITY_BUILDER,))

    def test_append_rejects_extended_metadata(self) -> None:
        class_id = 0x100
        resource = b"\0" + struct.pack("<QI", class_id, ENTITY_BUILDER)
        payload = (
            struct.pack("<IiI", ENTITY_BUILDER, len(resource), 3)
            + b"Old\0"
            + resource
        )
        metadata = struct.pack("<HQIH", 1, class_id, len(payload), 0) + b"extended"
        container = _cfd(metadata) + _cfd(payload)
        new_resource = b"\0" + struct.pack("<QI", 0x200, MESH)
        with self.assertRaisesRegex(DataContainerError, "extended metadata"):
            DataContainer.append_raw_resource_bytes(
                container, new_resource, MESH, "Mesh_New"
            )

    def test_appends_raw_resource_and_preserves_trailer(self) -> None:
        old_resource = b"\0" + struct.pack("<QI", 0x100, ENTITY_BUILDER)
        existing_payload = (
            struct.pack("<IiI", ENTITY_BUILDER, len(old_resource), 3)
            + b"Old\0" + old_resource
        )
        metadata = struct.pack("<HQIH", 1, 0x100, len(existing_payload), 0)
        trailer = b"\0File created using AnvilToolkit vTEST\0"
        original = _cfd(metadata) + _cfd(existing_payload) + trailer
        resource = b"\0" + struct.pack("<QI", 0x200, MESH) + b"mesh payload"
        updated = DataContainer.append_raw_resource_bytes(
            original, resource, MESH, "Mesh_New"
        )
        manifest = DataContainer.inspect_bytes(updated)
        self.assertEqual(manifest.resource_ids, (0x100, 0x200))
        self.assertEqual(manifest.trailer_length, len(trailer))
        self.assertTrue(updated.endswith(trailer))
        self.assertIn(resource, updated)

    def test_replaces_and_recompresses_embedded_resource(self) -> None:
        class_id = 0x200
        name = b"Weapon"
        old_body = struct.pack("<QI", class_id, MESH) + b"A" * 2048
        old_record = (
            struct.pack("<IiI", MESH, len(old_body), len(name))
            + name
            + b"\0"
            + old_body
        )
        metadata = struct.pack("<HQIH", 1, class_id, len(old_record), 0)
        original = _cfd(metadata) + _cfd(old_record)
        replacement = b"\0" + struct.pack("<QI", class_id, MESH) + b"B" * 2300

        rebuilt = DataContainer.replace_resource_bytes(
            original,
            replacement,
            lambda packed, _size: zlib.decompress(packed),
            zlib.compress,
        )
        before = DataContainer.inspect_bytes(original)
        after = DataContainer.inspect_bytes(
            rebuilt, decoder=lambda packed, _size: zlib.decompress(packed)
        )
        self.assertEqual(after.resource_ids, (class_id,))
        self.assertNotEqual(before.resource_hashes[0], after.resource_hashes[0])
        self.assertEqual(after.resource_sizes[0], 12 + len(name) + 1 + len(replacement) - 1)

    def test_rebuild_rejects_changed_non_target_resource(self) -> None:
        first_id = 0x200
        second_id = 0x201
        name1 = b"Target"
        name2 = b"Other"
        body1 = struct.pack("<QI", first_id, MESH) + b"A" * 128
        body2 = struct.pack("<QI", second_id, MESH) + b"C" * 128
        record1 = struct.pack("<IiI", MESH, len(body1), len(name1)) + name1 + b"\0" + body1
        record2 = struct.pack("<IiI", MESH, len(body2), len(name2)) + name2 + b"\0" + body2
        metadata = (
            struct.pack("<H", 2)
            + struct.pack("<QIH", first_id, len(record1), 0)
            + struct.pack("<QIH", second_id, len(record2), 0)
        )
        original = _cfd(metadata) + _cfd(record1 + record2)
        replacement = b"\0" + struct.pack("<QI", first_id, MESH) + b"B" * 128
        encoded_raw = b""

        def compressor(raw: bytes) -> bytes:
            nonlocal encoded_raw
            encoded_raw = raw
            return b"X"

        def corrupting_decoder(_packed: bytes, raw_size: int) -> bytes:
            corrupted = bytearray(encoded_raw)
            corrupted[-1] ^= 1
            self.assertEqual(len(corrupted), raw_size)
            return bytes(corrupted)

        with self.assertRaisesRegex(DataContainerError, "non-target resource"):
            DataContainer.replace_resource_bytes(
                original,
                replacement,
                corrupting_decoder,
                compressor,
            )


class NativeOodleTests(unittest.TestCase):
    def test_rejects_windows_dll(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp, "oo2core_7_win64.dll")
            path.write_bytes(b"MZ" + b"\0" * 62)
            with self.assertRaisesRegex(OodleLibraryError, "Windows Oodle DLLs"):
                NativeOodle(path)

    def test_rejects_non_elf_codec(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp, "liboo2corelinux64.so.9")
            path.write_bytes(b"not an ELF library")
            with self.assertRaisesRegex(OodleLibraryError, "not a Linux ELF"):
                NativeOodle(path)

    def test_rejects_oversized_elf_before_hash_or_load(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp, "liboo2corelinux64.so.9")
            with path.open("wb") as stream:
                stream.write(b"\x7fELF")
                stream.truncate(512 * 1024 * 1024 + 1)
            path.chmod(0o600)
            with self.assertRaisesRegex(OodleLibraryError, "invalid size"):
                NativeOodle(path, trusted_sha256="0" * 64)

    def test_requires_hash_and_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp, "liboo2corelinux64.so.9")
            target.write_bytes(b"\x7fELF" + b"\0" * 60)
            target.chmod(0o600)
            with self.assertRaisesRegex(OodleLibraryError, "trusted_sha256"):
                NativeOodle(target)
            link = Path(temp, "link.so.9")
            os.symlink(target, link)
            with self.assertRaises(OodleLibraryError):
                NativeOodle(link, trusted_sha256="0" * 64)

    def test_rejects_oversized_ipc_before_worker_access(self) -> None:
        codec = object.__new__(NativeOodle)
        oversized = bytes(NativeOodle.MAX_IPC_PAYLOAD + 1)
        with self.assertRaisesRegex(OodleLibraryError, "IPC payload"):
            codec.compress_mermaid(oversized)
        with self.assertRaisesRegex(OodleLibraryError, "IPC raw size"):
            codec.decompress_mermaid(b"x", NativeOodle.MAX_IPC_RAW_SIZE + 1)

    def test_worker_limits_fail_closed(self) -> None:
        with mock.patch("resource.setrlimit", side_effect=OSError("denied")):
            with self.assertRaisesRegex(OodleLibraryError, "worker limits"):
                _apply_worker_limits()

    def test_oversized_raw_response_is_rejected_by_transport(self) -> None:
        class Connection:
            closed = False
            maxlength = 0

            def recv_bytes(self, maxlength: int) -> bytes:
                self.maxlength = maxlength
                raise OSError("frame exceeds maxlength")

            def close(self) -> None:
                self.closed = True

        class Process:
            exitcode = None
            alive = True
            closed = False

            def is_alive(self) -> bool:
                return self.alive

            def terminate(self) -> None:
                self.alive = False

            def join(self, timeout: float) -> None:
                del timeout

            def close(self) -> None:
                self.closed = True

        codec = object.__new__(NativeOodle)
        connection = Connection()
        process = Process()
        codec._lock = threading.RLock()
        codec._closed = False
        setattr(codec, "_connection", connection)
        setattr(codec, "_process", process)
        with self.assertRaisesRegex(OodleLibraryError, "connection failed"):
            codec._receive(1)
        self.assertGreater(connection.maxlength, 0)
        self.assertTrue(connection.closed)
        self.assertTrue(process.closed)

    def test_send_timeout_invalidates_nonreading_worker(self) -> None:
        class Connection:
            def __init__(self) -> None:
                self.release = threading.Event()
                self.send_exited = threading.Event()
                self.closed = False

            def send_bytes(self, _message: bytes) -> None:
                try:
                    self.release.wait(10)
                finally:
                    self.send_exited.set()

            def close(self) -> None:
                self.closed = True
                self.release.set()

        class Process:
            exitcode = None
            alive = True
            terminated = False
            killed = False
            closed = False

            def is_alive(self) -> bool:
                return self.alive

            def terminate(self) -> None:
                self.terminated = True

            def kill(self) -> None:
                self.killed = True
                self.alive = False

            def join(self, timeout: float) -> None:
                del timeout

            def close(self) -> None:
                self.closed = True

        codec = object.__new__(NativeOodle)
        connection = Connection()
        process = Process()
        codec._lock = threading.RLock()
        codec._closed = False
        setattr(codec, "_connection", connection)
        setattr(codec, "_process", process)
        codec.OPERATION_TIMEOUT = 0.02
        started = time.monotonic()
        with self.assertRaisesRegex(OodleLibraryError, "send timed out"):
            codec._request("compress", b"data", 4)
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertTrue(connection.closed)
        self.assertTrue(process.terminated)
        self.assertTrue(process.killed)
        self.assertTrue(process.closed)
        self.assertTrue(connection.send_exited.is_set())

    def test_timeout_permanently_invalidates_worker(self) -> None:
        class Connection:
            def __init__(self) -> None:
                self.release = threading.Event()
                self.closed = False

            def recv_bytes(self, maxlength: int) -> bytes:
                del maxlength
                self.release.wait(10)
                return bytes([0]) + b"late"

            def close(self) -> None:
                self.closed = True
                self.release.set()

        class Process:
            exitcode = None
            alive = True
            terminated = False
            closed = False

            def is_alive(self) -> bool:
                return self.alive

            def terminate(self) -> None:
                self.terminated = True
                self.alive = False

            def join(self, timeout: float) -> None:
                del timeout

            def close(self) -> None:
                self.closed = True

        codec = object.__new__(NativeOodle)
        connection = Connection()
        process = Process()
        codec._lock = threading.RLock()
        codec._closed = False
        setattr(codec, "_connection", connection)
        setattr(codec, "_process", process)
        with self.assertRaisesRegex(OodleLibraryError, "timed out"):
            codec._receive(0)
        self.assertTrue(codec._closed)
        self.assertTrue(connection.closed)
        self.assertTrue(process.terminated)
        self.assertTrue(process.closed)
        with self.assertRaisesRegex(OodleLibraryError, "no longer usable"):
            codec._request("compress", b"data", 4)

    @unittest.skipUnless(
        os.environ.get("ANVIL_TEST_OODLE_LIBRARY")
        and os.environ.get("ANVIL_TEST_OODLE_SHA256"),
        "native Oodle integration library is not configured",
    )
    def test_positive_isolated_native_roundtrip(self) -> None:
        path = Path(os.environ["ANVIL_TEST_OODLE_LIBRARY"])
        trusted = os.environ["ANVIL_TEST_OODLE_SHA256"]
        raw = (b"positive isolated Oodle unittest\n" * 1200)[:32768]
        with NativeOodle(path, trusted_sha256=trusted) as codec:
            process = codec._process
            packed = codec.compress_mermaid(raw)
            decoded = codec.decompress_mermaid(packed, len(raw))
            self.assertEqual(decoded, raw)
        with self.assertRaises(ValueError):
            process.is_alive()
        self.assertNotEqual(hashlib.sha256(packed).digest(), hashlib.sha256(raw).digest())


class ForgeArchiveTests(unittest.TestCase):
    def test_reads_v27_index_and_payload(self) -> None:
        payload = _data_container(0x111, ENTITY_BUILDER, "WG_Old")
        raw = _forge([(0x111, ENTITY_BUILDER, "WG_Old", payload)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.forge"
            path.write_bytes(raw)
            archive = ForgeArchive.read(path)
            self.assertEqual(archive.version, 27)
            self.assertEqual(archive.entries[0].class_id, 0x111)
            self.assertEqual(archive.read_payload(archive.entries[0]), payload)

    def test_read_payload_rejects_replaced_path(self) -> None:
        payload = _data_container(0x111, ENTITY_BUILDER, "WG_Old")
        raw = _forge([(0x111, ENTITY_BUILDER, "WG_Old", payload)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "test.forge")
            old_path = Path(tmp, "old.forge")
            path.write_bytes(raw)
            archive = ForgeArchive.read(path)
            path.rename(old_path)
            path.write_bytes(raw)
            with self.assertRaisesRegex(ForgeFormatError, "no longer identifies"):
                archive.read_payload(archive.entries[0])

    def test_rejects_duplicate_ids(self) -> None:
        payload = _data_container(0x111, ENTITY_BUILDER, "WG_Old")
        raw = _forge(
            [
                (0x111, ENTITY_BUILDER, "WG_A", payload),
                (0x111, ENTITY_BUILDER, "WG_B", payload),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate.forge"
            path.write_bytes(raw)
            with self.assertRaises(ForgeFormatError):
                ForgeArchive.read(path)

    def test_rejects_broken_entry_chain(self) -> None:
        payload = _data_container(0x111, ENTITY_BUILDER, "WG_Old")
        raw = bytearray(_forge([(0x111, ENTITY_BUILDER, "WG_Old", payload)]))
        info_table = 1094 + 40 + 20
        struct.pack_into("<I", raw, info_table + 28, 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "broken.forge")
            path.write_bytes(raw)
            with self.assertRaisesRegex(ForgeFormatError, "Next/Previous"):
                ForgeArchive.read(path)

    def test_rejects_broken_fileset_range(self) -> None:
        payload = _data_container(0x111, ENTITY_BUILDER, "WG_Old")
        raw = bytearray(_forge([(0x111, ENTITY_BUILDER, "WG_Old", payload)]))
        struct.pack_into("<II", raw, 1094 + 24, 0, 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "broken-range.forge")
            path.write_bytes(raw)
            with self.assertRaisesRegex(ForgeFormatError, "FileSet range"):
                ForgeArchive.read(path)

    def test_rejects_noncanonical_empty_fileset_range(self) -> None:
        raw = bytearray(_forge([]))
        struct.pack_into("<II", raw, 1094 + 24, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "broken-empty-range.forge")
            path.write_bytes(raw)
            with self.assertRaisesRegex(ForgeFormatError, "empty FileSet range"):
                ForgeArchive.read(path)

    def test_rejects_same_destination_and_reserved_sidecar(self) -> None:
        old = _data_container(0x111, ENTITY_BUILDER, "WG_Old")
        source_bytes = _forge([(0x111, ENTITY_BUILDER, "WG_Old", old)])
        sidecar = _data_container(0x10, ENTITY_BUILDER, "Reserved")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.forge"
            sidecar_path = root / "sidecar.data"
            source.write_bytes(source_bytes)
            sidecar_path.write_bytes(sidecar)
            with self.assertRaisesRegex(ForgeFormatError, "distinct destination"):
                append_repoint(
                    source,
                    source,
                    [ForgeImport(sidecar_path, ENTITY_BUILDER, "Reserved")],
                )
            self.assertEqual(source.read_bytes(), source_bytes)
            with self.assertRaisesRegex(ForgeFormatError, "reserved Sidecar"):
                append_repoint(
                    source,
                    root / "output.forge",
                    [ForgeImport(sidecar_path, ENTITY_BUILDER, "Reserved")],
                )

            valid_path = root / "valid.data"
            valid_path.write_bytes(_data_container(0x222, ENTITY_BUILDER, "Valid"))
            existing = root / "existing.forge"
            existing.write_bytes(b"do not replace")
            with self.assertRaisesRegex(ForgeFormatError, "exclusive staging Forge"):
                append_repoint(
                    source,
                    existing,
                    [ForgeImport(valid_path, ENTITY_BUILDER, "Valid")],
                )
            self.assertEqual(existing.read_bytes(), b"do not replace")

            real_parent = root / "real-parent"
            real_parent.mkdir()
            linked_parent = root / "linked-parent"
            os.symlink(real_parent, linked_parent)
            with self.assertRaisesRegex(ForgeFormatError, "unnamed staging Forge"):
                append_repoint(
                    source,
                    linked_parent / "created-through-link" / "output.forge",
                    [ForgeImport(valid_path, ENTITY_BUILDER, "Valid")],
                )
            self.assertFalse((real_parent / "created-through-link").exists())

    def test_creates_missing_parents_with_anchored_mkdir(self) -> None:
        source_payload = _data_container(0x999, ENTITY_BUILDER, "Existing")
        addition = _data_container(0x100, ENTITY_BUILDER, "Added")
        source_bytes = _forge(
            [(0x999, ENTITY_BUILDER, "Existing", source_payload)]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.forge"
            addition_path = root / "addition.data"
            output = root / "new" / "nested" / "staged.forge"
            source.write_bytes(source_bytes)
            addition_path.write_bytes(addition)
            staged = append_repoint(
                source,
                output,
                [ForgeImport(addition_path, ENTITY_BUILDER, "Added")],
            )
            self.assertTrue(output.is_file())
            self.assertEqual(staged.path, output)
            self.assertEqual(
                [entry.class_id for entry in staged.entries], [0x999, 0x100]
            )

    def test_post_publish_failure_is_reported_as_committed(self) -> None:
        source_payload = _data_container(0x999, ENTITY_BUILDER, "Existing")
        addition = _data_container(0x100, ENTITY_BUILDER, "Added")
        source_bytes = _forge(
            [(0x999, ENTITY_BUILDER, "Existing", source_payload)]
        )
        real_fsync = os.fsync
        calls = 0

        def fail_parent_fsync(descriptor: int) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected parent fsync failure")
            real_fsync(descriptor)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.forge"
            addition_path = root / "addition.data"
            output = root / "staged.forge"
            source.write_bytes(source_bytes)
            addition_path.write_bytes(addition)
            with mock.patch("os.fsync", side_effect=fail_parent_fsync):
                with self.assertRaises(ForgePublishedError) as caught:
                    append_repoint(
                        source,
                        output,
                        [ForgeImport(addition_path, ENTITY_BUILDER, "Added")],
                    )
            self.assertTrue(caught.exception.published)
            self.assertEqual(caught.exception.path, output)
            self.assertTrue(output.is_file())
            self.assertEqual(len(ForgeArchive.read(output).entries), 2)

    def test_input_preparation_closes_descriptors_on_baseexception(self) -> None:
        source_payload = _data_container(0x999, ENTITY_BUILDER, "Existing")
        addition = _data_container(0x100, ENTITY_BUILDER, "Added")
        source_bytes = _forge(
            [(0x999, ENTITY_BUILDER, "Existing", source_payload)]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.forge"
            addition_path = root / "addition.data"
            output = root / "staged.forge"
            source.write_bytes(source_bytes)
            addition_path.write_bytes(addition)
            before = len(os.listdir("/proc/self/fd"))

            with mock.patch.object(
                DataContainer,
                "inspect_stream",
                side_effect=KeyboardInterrupt("injected during preparation"),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    append_repoint(
                        source,
                        output,
                        [ForgeImport(addition_path, ENTITY_BUILDER, "Added")],
                    )

            self.assertEqual(len(os.listdir("/proc/self/fd")), before)
            self.assertFalse(output.exists())

    def test_open_validation_closes_descriptor_on_baseexception(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "container.data"
            path.write_bytes(b"not inspected")
            before = len(os.listdir("/proc/self/fd"))

            with mock.patch(
                "os.fstat", side_effect=KeyboardInterrupt("injected open validation")
            ):
                with self.assertRaises(KeyboardInterrupt):
                    DataContainer.inspect(path)

            self.assertEqual(len(os.listdir("/proc/self/fd")), before)

    def test_parent_validation_closes_all_owned_descriptors(self) -> None:
        source_payload = _data_container(0x999, ENTITY_BUILDER, "Existing")
        addition = _data_container(0x100, ENTITY_BUILDER, "Added")
        source_bytes = _forge(
            [(0x999, ENTITY_BUILDER, "Existing", source_payload)]
        )
        real_open_parent = grb_forge._open_or_create_directory_nofollow
        real_fstat = os.fstat
        parent_descriptors: list[int] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.forge"
            addition_path = root / "addition.data"
            output = root / "target" / "staged.forge"
            source.write_bytes(source_bytes)
            addition_path.write_bytes(addition)
            before = len(os.listdir("/proc/self/fd"))

            def record_parent(path: Path) -> int:
                descriptor = real_open_parent(path)
                parent_descriptors.append(descriptor)
                return descriptor

            def interrupt_parent_fstat(descriptor: int):
                if parent_descriptors and descriptor == parent_descriptors[0]:
                    raise KeyboardInterrupt("injected parent fstat")
                return real_fstat(descriptor)

            with mock.patch(
                "anvil.core.grb_forge._open_or_create_directory_nofollow",
                side_effect=record_parent,
            ), mock.patch("os.fstat", side_effect=interrupt_parent_fstat):
                with self.assertRaises(KeyboardInterrupt):
                    append_repoint(
                        source,
                        output,
                        [ForgeImport(addition_path, ENTITY_BUILDER, "Added")],
                    )

            self.assertFalse(output.exists())
            self.assertEqual(len(os.listdir("/proc/self/fd")), before)

    def test_baseexception_before_link_is_not_reported_as_committed(self) -> None:
        source_payload = _data_container(0x999, ENTITY_BUILDER, "Existing")
        addition = _data_container(0x100, ENTITY_BUILDER, "Added")
        source_bytes = _forge(
            [(0x999, ENTITY_BUILDER, "Existing", source_payload)]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.forge"
            addition_path = root / "addition.data"
            output = root / "staged.forge"
            source.write_bytes(source_bytes)
            addition_path.write_bytes(addition)

            with mock.patch(
                "anvil.core.grb_forge._publish_unnamed_file",
                side_effect=KeyboardInterrupt("injected before linkat"),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    append_repoint(
                        source,
                        output,
                        [ForgeImport(addition_path, ENTITY_BUILDER, "Added")],
                    )
            self.assertFalse(output.exists())

    def test_baseexception_after_link_is_reported_as_committed(self) -> None:
        source_payload = _data_container(0x999, ENTITY_BUILDER, "Existing")
        addition = _data_container(0x100, ENTITY_BUILDER, "Added")
        source_bytes = _forge(
            [(0x999, ENTITY_BUILDER, "Existing", source_payload)]
        )
        real_publish = grb_forge._publish_unnamed_file
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.forge"
            addition_path = root / "addition.data"
            output = root / "staged.forge"
            source.write_bytes(source_bytes)
            addition_path.write_bytes(addition)

            def publish_then_interrupt(
                descriptor: int, parent_descriptor: int, name: str
            ) -> None:
                real_publish(descriptor, parent_descriptor, name)
                raise KeyboardInterrupt("injected after linkat")

            with mock.patch(
                "anvil.core.grb_forge._publish_unnamed_file",
                side_effect=publish_then_interrupt,
            ):
                with self.assertRaises(ForgePublishedError) as caught:
                    append_repoint(
                        source,
                        output,
                        [ForgeImport(addition_path, ENTITY_BUILDER, "Added")],
                    )
            self.assertTrue(caught.exception.published)
            self.assertTrue(output.is_file())
            self.assertEqual(len(ForgeArchive.read(output).entries), 2)

    def test_baseexception_after_publish_helper_return_is_committed(self) -> None:
        source_payload = _data_container(0x999, ENTITY_BUILDER, "Existing")
        addition = _data_container(0x100, ENTITY_BUILDER, "Added")
        source_bytes = _forge(
            [(0x999, ENTITY_BUILDER, "Existing", source_payload)]
        )
        real_publish = grb_forge._publish_unnamed_file
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.forge"
            addition_path = root / "addition.data"
            output = root / "staged.forge"
            source.write_bytes(source_bytes)
            addition_path.write_bytes(addition)

            def publish_then_arm_trace(
                descriptor: int, parent_descriptor: int, name: str
            ) -> None:
                real_publish(descriptor, parent_descriptor, name)

                def interrupt_on_caller_line(frame, event, arg):
                    del arg
                    if frame.f_code is append_repoint.__code__ and event == "line":
                        sys.settrace(None)
                        raise KeyboardInterrupt("injected after helper return")
                    return interrupt_on_caller_line

                caller = sys._getframe(1)
                while caller is not None and caller.f_code is not append_repoint.__code__:
                    caller = caller.f_back
                if caller is None:
                    raise AssertionError("append_repoint frame not found")
                caller.f_trace = interrupt_on_caller_line
                sys.settrace(interrupt_on_caller_line)

            try:
                with mock.patch(
                    "anvil.core.grb_forge._publish_unnamed_file",
                    side_effect=publish_then_arm_trace,
                ):
                    with self.assertRaises(ForgePublishedError) as caught:
                        append_repoint(
                            source,
                            output,
                            [ForgeImport(addition_path, ENTITY_BUILDER, "Added")],
                        )
            finally:
                sys.settrace(None)
            self.assertTrue(caught.exception.published)
            self.assertTrue(output.is_file())
            self.assertEqual(len(ForgeArchive.read(output).entries), 2)

    def test_commit_probe_interruptions_preserve_cleanup_and_published_error(self) -> None:
        source_payload = _data_container(0x999, ENTITY_BUILDER, "Existing")
        addition = _data_container(0x100, ENTITY_BUILDER, "Added")
        source_bytes = _forge(
            [(0x999, ENTITY_BUILDER, "Existing", source_payload)]
        )
        real_publish = grb_forge._publish_unnamed_file
        real_fstat = os.fstat
        linked_descriptor: list[int] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.forge"
            addition_path = root / "addition.data"
            output = root / "staged.forge"
            source.write_bytes(source_bytes)
            addition_path.write_bytes(addition)
            before = len(os.listdir("/proc/self/fd"))

            def publish_then_fail(
                descriptor: int, parent_descriptor: int, name: str
            ) -> None:
                real_publish(descriptor, parent_descriptor, name)
                linked_descriptor.append(descriptor)
                raise RuntimeError("original post-link failure")

            def fail_staging_fstat(descriptor: int):
                if linked_descriptor and descriptor == linked_descriptor[0]:
                    raise KeyboardInterrupt("injected fstat interruption")
                return real_fstat(descriptor)

            with mock.patch(
                "anvil.core.grb_forge._publish_unnamed_file",
                side_effect=publish_then_fail,
            ), mock.patch("os.fstat", side_effect=fail_staging_fstat), mock.patch(
                "anvil.core.grb_forge._dir_entry_has_inode",
                side_effect=KeyboardInterrupt("injected directory probe interruption"),
            ):
                with self.assertRaises(ForgePublishedError) as caught:
                    append_repoint(
                        source,
                        output,
                        [ForgeImport(addition_path, ENTITY_BUILDER, "Added")],
                    )

            self.assertTrue(caught.exception.published)
            self.assertIsInstance(caught.exception.__cause__, RuntimeError)
            self.assertTrue(output.is_file())
            self.assertEqual(len(ForgeArchive.read(output).entries), 2)
            self.assertEqual(len(os.listdir("/proc/self/fd")), before)

    def test_parent_rename_after_publish_reports_anchored_commit(self) -> None:
        source_payload = _data_container(0x999, ENTITY_BUILDER, "Existing")
        addition = _data_container(0x100, ENTITY_BUILDER, "Added")
        source_bytes = _forge(
            [(0x999, ENTITY_BUILDER, "Existing", source_payload)]
        )
        real_publish = grb_forge._publish_unnamed_file
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.forge"
            addition_path = root / "addition.data"
            parent = root / "target"
            moved_parent = root / "moved-target"
            output = parent / "staged.forge"
            parent.mkdir()
            source.write_bytes(source_bytes)
            addition_path.write_bytes(addition)

            def publish_then_rename(
                descriptor: int, parent_descriptor: int, name: str
            ) -> None:
                real_publish(descriptor, parent_descriptor, name)
                parent.rename(moved_parent)
                parent.mkdir()

            with mock.patch(
                "anvil.core.grb_forge._publish_unnamed_file",
                side_effect=publish_then_rename,
            ):
                with self.assertRaises(ForgePublishedError) as caught:
                    append_repoint(
                        source,
                        output,
                        [ForgeImport(addition_path, ENTITY_BUILDER, "Added")],
                    )
            actual = moved_parent / "staged.forge"
            self.assertTrue(caught.exception.published)
            self.assertFalse(output.exists())
            self.assertTrue(actual.is_file())
            self.assertEqual(
                caught.exception.parent_identity,
                (moved_parent.stat().st_dev, moved_parent.stat().st_ino),
            )
            file_identity = caught.exception.file_identity
            self.assertIsNotNone(file_identity)
            assert file_identity is not None
            self.assertEqual(
                file_identity[:2],
                (actual.stat().st_dev, actual.stat().st_ino),
            )

    def test_rejects_outer_id_colliding_with_other_import_inner_id(self) -> None:
        source_payload = _data_container(0x999, ENTITY_BUILDER, "Existing")
        source_bytes = _forge(
            [(0x999, ENTITY_BUILDER, "Existing", source_payload)]
        )
        first = DataContainer.append_raw_resource_bytes(
            _data_container(0x100, ENTITY_BUILDER, "Outer_A"),
            b"\0" + struct.pack("<QI", 0x200, MESH),
            MESH,
            "Inner_B",
        )
        second = _data_container(0x200, MESH, "Outer_B")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.forge"
            first_path = root / "first.data"
            second_path = root / "second.data"
            source.write_bytes(source_bytes)
            first_path.write_bytes(first)
            second_path.write_bytes(second)
            with self.assertRaisesRegex(ForgeFormatError, "collides with an inner"):
                append_repoint(
                    source,
                    root / "staged.forge",
                    [
                        ForgeImport(first_path, ENTITY_BUILDER, "Outer_A"),
                        ForgeImport(second_path, MESH, "Outer_B"),
                    ],
                )

    def test_allows_container_local_inner_id_reuse(self) -> None:
        source_payload = _data_container(0x999, ENTITY_BUILDER, "Existing")
        source_bytes = _forge(
            [(0x999, ENTITY_BUILDER, "Existing", source_payload)]
        )
        first = DataContainer.append_raw_resource_bytes(
            _data_container(0x100, ENTITY_BUILDER, "Outer_A"),
            b"\0" + struct.pack("<QI", 0x777, MESH) + b"A",
            MESH,
            "Local",
        )
        second = DataContainer.append_raw_resource_bytes(
            _data_container(0x101, ENTITY_BUILDER, "Outer_B"),
            b"\0" + struct.pack("<QI", 0x777, MESH) + b"B",
            MESH,
            "Local",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.forge"
            first_path = root / "first.data"
            second_path = root / "second.data"
            output = root / "staged.forge"
            source.write_bytes(source_bytes)
            first_path.write_bytes(first)
            second_path.write_bytes(second)
            staged = append_repoint(
                source,
                output,
                [
                    ForgeImport(first_path, ENTITY_BUILDER, "Outer_A"),
                    ForgeImport(second_path, ENTITY_BUILDER, "Outer_B"),
                ],
            )
            self.assertEqual(
                [entry.class_id for entry in staged.entries],
                [0x999, 0x100, 0x101],
            )

    def test_append_repoint_adds_and_replaces_without_touching_source(self) -> None:
        old = _data_container(0x111, ENTITY_BUILDER, "WG_Old")
        sidecar = b"global-meta"
        replacement = _data_container(0x111, ENTITY_BUILDER, "WG_New")
        addition = _data_container(0x222, MESH, "Mesh_New")
        source_bytes = _forge(
            [
                (0x111, ENTITY_BUILDER, "WG_Old", old),
                (0x10, 0, "GlobalMetaFile", sidecar),
            ]
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.forge"
            output = root / "staged.forge"
            replacement_path = root / "replacement.data"
            addition_path = root / "addition.data"
            source.write_bytes(source_bytes)
            replacement_path.write_bytes(replacement)
            addition_path.write_bytes(addition)

            append_repoint(
                source,
                output,
                [
                    ForgeImport(replacement_path, ENTITY_BUILDER, "WG_New"),
                    ForgeImport(addition_path, MESH, "Mesh_New"),
                ],
            )

            self.assertEqual(source.read_bytes(), source_bytes)
            staged = ForgeArchive.read(output)
            self.assertEqual(len(staged.filesets), 1)
            self.assertEqual(
                struct.unpack_from("<II", output.read_bytes(), 1094 + 24),
                (0, 2),
            )
            self.assertEqual([entry.class_id for entry in staged.entries], [0x111, 0x222, 0x10])
            info_keys = [entry.info_record[4:16] for entry in staged.entries]
            self.assertEqual(len(info_keys), len(set(info_keys)))
            expected_umac = _xxhash64(str(addition_path).encode("utf-8")).to_bytes(
                8, "big"
            )
            by_id = {entry.class_id: entry for entry in staged.entries}
            self.assertEqual(by_id[0x222].info_record[4:12], expected_umac)
            self.assertEqual(by_id[0x222].info_record[12:16], bytes(4))
            self.assertEqual(staged.entries[-1].name, "GlobalMetaFile")
            self.assertEqual(staged.read_payload(by_id[0x111]), replacement)
            self.assertEqual(staged.read_payload(by_id[0x222]), addition)
            self.assertEqual(staged.read_payload(by_id[0x10]), sidecar)


if __name__ == "__main__":
    unittest.main()
