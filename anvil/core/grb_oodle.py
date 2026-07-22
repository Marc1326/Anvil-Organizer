"""Native Linux Oodle adapter for Ghost Recon Breakpoint resources.

The proprietary library is never bundled or downloaded.  Loading native code cannot
be made safe by inspecting ELF metadata: constructors execute during ``dlopen``.
Consequently a caller must provide the SHA-256 of a library it explicitly trusts.
The descriptor/hash checks below prevent path substitution, but cannot establish the
authenticity of an otherwise untrusted binary.
"""

from __future__ import annotations

import ctypes
import fcntl
import hashlib
import multiprocessing
import os
import re
import stat
import struct
import sys
import threading
import time
from pathlib import Path


class OodleLibraryError(RuntimeError):
    """Raised when a native Oodle codec cannot be used safely."""


_MFD_CLOEXEC = 0x0001
_MFD_ALLOW_SEALING = 0x0002
_F_ADD_SEALS = 1033
_F_GET_SEALS = 1034
_F_SEAL_SEAL = 0x0001
_F_SEAL_SHRINK = 0x0002
_F_SEAL_GROW = 0x0004
_F_SEAL_WRITE = 0x0008
_MAX_ELF_SIZE = 512 * 1024 * 1024
_MAX_IPC_PAYLOAD = 1024 * 1024
_MAX_IPC_FRAME = _MAX_IPC_PAYLOAD + 5
_MAX_IPC_RESPONSE = 2 * _MAX_IPC_PAYLOAD + 65537
_MAX_ERROR_TEXT = 4096
_OP_COMPRESS = 1
_OP_DECOMPRESS = 2
_OP_CLOSE = 3
_STATUS_OK = 0
_STATUS_ERROR = 1
_STATUS_READY = 2


def _create_sealable_memfd() -> int:
    if hasattr(os, "memfd_create"):
        return os.memfd_create(
            "anvil-oodle", _MFD_CLOEXEC | _MFD_ALLOW_SEALING
        )
    libc = ctypes.CDLL(None, use_errno=True)
    memfd_create = libc.memfd_create
    memfd_create.argtypes = [ctypes.c_char_p, ctypes.c_uint]
    memfd_create.restype = ctypes.c_int
    descriptor = memfd_create(
        b"anvil-oodle", _MFD_CLOEXEC | _MFD_ALLOW_SEALING
    )
    if descriptor < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return descriptor


class _OodleConfigValues(ctypes.Structure):
    _fields_ = [
        ("lrm_step", ctypes.c_int32),
        ("lrm_hash_length", ctypes.c_int32),
        ("lrm_jump_bits", ctypes.c_int32),
        ("decoder_max_stack_size", ctypes.c_int32),
        ("small_buffer_fallback_unused", ctypes.c_int32),
        ("backwards_compatible_major_version", ctypes.c_int32),
        ("oodle_header_version", ctypes.c_uint32),
    ]


class _NativeOodleCodec:
    """In-process Linux Oodle binding used only inside the worker process.

    ``trusted_sha256`` is mandatory for an ELF library.  It authenticates exactly
    the inode loaded through ``/proc/self/fd``; it does not prove who produced that
    inode.  All Oodle users in a process must share this class lock because Oodle's
    compatibility configuration is process-global.
    """

    MERMAID = 9
    NORMAL_LEVEL = 4
    GRB_COMPATIBILITY_MAJOR = 7
    MAX_INPUT_SIZE = 1024 * 1024 * 1024
    MAX_OUTPUT_SIZE = 2 * 1024 * 1024 * 1024
    SUPPORTED_VERSIONS = frozenset({(2, 7), (2, 8), (2, 9)})
    _lock = threading.RLock()

    def __init__(self, library_path: str | Path, *, trusted_sha256: str | None = None) -> None:
        self.path = Path(library_path).expanduser()
        descriptor = self._open_trusted_elf(self.path, trusted_sha256)
        try:
            with self._lock:
                try:
                    self._library = ctypes.CDLL(f"/proc/self/fd/{descriptor}")
                except (OSError, OverflowError, MemoryError) as exc:
                    raise OodleLibraryError(
                        f"cannot load native Oodle library: {exc}"
                    ) from exc
                self._bind_and_validate_version()
                self._configure_grb_compatibility()
        finally:
            os.close(descriptor)

    @staticmethod
    def _open_trusted_elf(path: Path, trusted_sha256: str | None) -> int:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        try:
            source_descriptor = os.open(path, flags)
        except OSError as exc:
            raise OodleLibraryError(f"cannot open native Oodle library: {exc}") from exc
        sealed_descriptor: int | None = None
        try:
            metadata = os.fstat(source_descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise OodleLibraryError("native Oodle library is not a regular file")
            if metadata.st_size <= 0 or metadata.st_size > _MAX_ELF_SIZE:
                raise OodleLibraryError("native Oodle library has an invalid size")
            if metadata.st_uid not in (0, os.geteuid()) or metadata.st_mode & 0o022:
                raise OodleLibraryError(
                    "native Oodle library has an untrusted owner or writable permissions"
                )
            magic = os.pread(source_descriptor, 4, 0)
            if magic[:2] == b"MZ":
                raise OodleLibraryError(
                    "Windows Oodle DLLs are forbidden; provide a Linux ELF library"
                )
            if magic != b"\x7fELF":
                raise OodleLibraryError("Oodle codec is not a Linux ELF library")
            if trusted_sha256 is None or not re.fullmatch(
                r"[0-9a-fA-F]{64}", trusted_sha256
            ):
                raise OodleLibraryError(
                    "a valid trusted_sha256 is required before loading native code"
                )

            sealed_descriptor = _create_sealable_memfd()
            digest = hashlib.sha256()
            os.lseek(source_descriptor, 0, os.SEEK_SET)
            while True:
                block = os.read(source_descriptor, 1024 * 1024)
                if not block:
                    break
                digest.update(block)
                view = memoryview(block)
                while view:
                    written = os.write(sealed_descriptor, view)
                    if written <= 0:
                        raise OodleLibraryError("cannot copy native Oodle library")
                    view = view[written:]
            after = os.fstat(source_descriptor)
            source_identity = (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_size,
                metadata.st_mtime_ns,
                metadata.st_ctime_ns,
            )
            after_identity = (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            if source_identity != after_identity:
                raise OodleLibraryError(
                    "native Oodle library changed while it was authenticated"
                )
            if digest.hexdigest() != trusted_sha256.lower():
                raise OodleLibraryError(
                    "native Oodle library SHA-256 does not match trusted_sha256"
                )
            seals = _F_SEAL_WRITE | _F_SEAL_GROW | _F_SEAL_SHRINK | _F_SEAL_SEAL
            fcntl.fcntl(sealed_descriptor, _F_ADD_SEALS, seals)
            installed_seals = fcntl.fcntl(sealed_descriptor, _F_GET_SEALS)
            if installed_seals & seals != seals:
                raise OodleLibraryError("native Oodle library memfd was not fully sealed")
            os.lseek(sealed_descriptor, 0, os.SEEK_SET)
            result = sealed_descriptor
            sealed_descriptor = None
            return result
        except OodleLibraryError:
            raise
        except (OSError, OverflowError, MemoryError) as exc:
            raise OodleLibraryError(
                f"cannot authenticate native Oodle library: {exc}"
            ) from exc
        finally:
            os.close(source_descriptor)
            if sealed_descriptor is not None:
                os.close(sealed_descriptor)

    def _bind_and_validate_version(self) -> None:
        version_match = re.search(r"\.so\.(7|8|9)$", self.path.name)
        if version_match is None:
            raise OodleLibraryError(
                "native Oodle library must have a supported versioned Linux SONAME"
            )
        self._sdk_version = (2, int(version_match.group(1)))
        if self._sdk_version not in self.SUPPORTED_VERSIONS:
            raise OodleLibraryError("unsupported native Oodle version/ABI")
        try:
            get_config = self._library.Oodle_GetConfigValues
            set_config = self._library.Oodle_SetConfigValues
            buffer_size = self._library.OodleLZ_GetCompressedBufferSizeNeeded
            compress = self._library.OodleLZ_Compress
            decompress = self._library.OodleLZ_Decompress
        except AttributeError as exc:
            raise OodleLibraryError(f"native Oodle ABI symbol is missing: {exc}") from exc

        get_config.argtypes = [ctypes.POINTER(_OodleConfigValues)]
        get_config.restype = None
        set_config.argtypes = [ctypes.POINTER(_OodleConfigValues)]
        set_config.restype = None
        buffer_size.argtypes = [ctypes.c_int32, ctypes.c_ssize_t]
        buffer_size.restype = ctypes.c_ssize_t
        compress.argtypes = [ctypes.c_int32, ctypes.c_void_p, ctypes.c_ssize_t, ctypes.c_void_p,
                             ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                             ctypes.c_void_p, ctypes.c_ssize_t]
        compress.restype = ctypes.c_ssize_t
        decompress.argtypes = [
            ctypes.c_void_p,   # compBuf
            ctypes.c_ssize_t,  # compBufSize
            ctypes.c_void_p,   # rawBuf
            ctypes.c_ssize_t,  # rawLen
            ctypes.c_int32,    # fuzzSafe
            ctypes.c_int32,    # checkCRC
            ctypes.c_int32,    # verbosity
            ctypes.c_void_p,   # decBufBase
            ctypes.c_ssize_t,  # decBufSize
            ctypes.c_void_p,   # fpCallback
            ctypes.c_void_p,   # callbackUserData
            ctypes.c_void_p,   # decoderMemory
            ctypes.c_ssize_t,  # decoderMemorySize
            ctypes.c_int32,    # threadPhase
        ]
        decompress.restype = ctypes.c_ssize_t
        self._get_config, self._set_config = get_config, set_config
        self._buffer_size, self._compress = buffer_size, compress
        self._decompress = decompress

    def _configure_grb_compatibility(self) -> None:
        values = _OodleConfigValues()
        try:
            self._get_config(ctypes.byref(values))
            if values.oodle_header_version == 0:
                raise OodleLibraryError("Oodle reported an invalid header/ABI version")
            values.backwards_compatible_major_version = self.GRB_COMPATIBILITY_MAJOR
            self._set_config(ctypes.byref(values))
            check = _OodleConfigValues()
            self._get_config(ctypes.byref(check))
        except OodleLibraryError:
            raise
        except (ctypes.ArgumentError, ValueError, OverflowError, MemoryError) as exc:
            raise OodleLibraryError(f"Oodle configuration failed: {exc}") from exc
        if check.oodle_header_version != values.oodle_header_version:
            raise OodleLibraryError("Oodle header/ABI version changed unexpectedly")
        if check.backwards_compatible_major_version != self.GRB_COMPATIBILITY_MAJOR:
            raise OodleLibraryError("Oodle refused GRB 2.7 bitstream compatibility mode")

    def compress_mermaid(self, raw: bytes, *, level: int = NORMAL_LEVEL) -> bytes:
        """Compress one buffer after atomically reasserting global GRB compatibility."""
        if not isinstance(raw, bytes) or not raw:
            raise OodleLibraryError("cannot Oodle-compress an empty or non-bytes buffer")
        if not 1 <= level <= 9:
            raise OodleLibraryError(f"invalid Oodle compression level {level}")
        if len(raw) > min(sys.maxsize, self.MAX_INPUT_SIZE):
            raise OodleLibraryError("Oodle input exceeds the supported size limit")
        with self._lock:
            self._configure_grb_compatibility()
            try:
                output_size = int(self._buffer_size(self.MERMAID, len(raw)))
                plausible = min(self.MAX_OUTPUT_SIZE, max(len(raw) * 2, len(raw) + 65536), sys.maxsize)
                if output_size <= 0 or output_size > plausible:
                    raise OodleLibraryError("Oodle returned an invalid output buffer size")
                source = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
                output = ctypes.create_string_buffer(output_size)
                written = int(self._compress(
                    self.MERMAID, source, len(raw), output, level,
                    None, None, None, None, 0,
                ))
            except OodleLibraryError:
                raise
            except (ctypes.ArgumentError, TypeError, ValueError, OverflowError, MemoryError) as exc:
                raise OodleLibraryError(f"Oodle compression failed safely: {exc}") from exc
            if written <= 0 or written > output_size:
                raise OodleLibraryError(f"Oodle Mermaid compression failed: {written}")
            try:
                return output.raw[:written]
            except (OverflowError, MemoryError) as exc:
                raise OodleLibraryError(f"cannot materialize Oodle output: {exc}") from exc

    def decompress_mermaid(self, packed: bytes, raw_size: int) -> bytes:
        """Decompress one Mermaid stream with strict output-size validation."""
        if not isinstance(packed, bytes) or not packed:
            raise OodleLibraryError(
                "cannot Oodle-decompress an empty or non-bytes buffer"
            )
        if raw_size <= 0 or raw_size > min(sys.maxsize, self.MAX_INPUT_SIZE):
            raise OodleLibraryError("invalid Oodle decompressed size")
        if len(packed) > self.MAX_OUTPUT_SIZE:
            raise OodleLibraryError("Oodle input exceeds the supported size limit")
        with self._lock:
            try:
                source = (ctypes.c_ubyte * len(packed)).from_buffer_copy(packed)
                output = ctypes.create_string_buffer(raw_size)
                written = int(
                    self._decompress(
                        source,
                        len(packed),
                        output,
                        raw_size,
                        1,
                        0,
                        0,
                        None,
                        0,
                        None,
                        None,
                        None,
                        0,
                        0,
                    )
                )
            except (
                ctypes.ArgumentError,
                TypeError,
                ValueError,
                OverflowError,
                MemoryError,
            ) as exc:
                raise OodleLibraryError(
                    f"Oodle decompression failed safely: {exc}"
                ) from exc
            if written != raw_size:
                raise OodleLibraryError(
                    f"Oodle Mermaid decompression returned {written}, expected {raw_size}"
                )
            return output.raw[:written]


def _apply_worker_limits() -> None:
    try:
        import resource

        memory_limit = 3 * 1024 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ImportError, OSError, ValueError) as exc:
        raise OodleLibraryError(f"cannot apply Oodle worker limits: {exc}") from exc


def _oodle_worker(
    connection, library_path: str, trusted_sha256: str | None
) -> None:
    try:
        _apply_worker_limits()
        codec = _NativeOodleCodec(
            library_path, trusted_sha256=trusted_sha256
        )
        connection.send_bytes(
            bytes([_STATUS_READY]) + struct.pack("<HH", *codec._sdk_version)
        )
        while True:
            request = connection.recv_bytes(_MAX_IPC_FRAME)
            if request == bytes([_OP_CLOSE]):
                return
            if len(request) < 6:
                raise OodleLibraryError("truncated Oodle worker request")
            operation = request[0]
            value = struct.unpack_from("<i", request, 1)[0]
            payload = request[5:]
            if operation == _OP_COMPRESS:
                result = codec.compress_mermaid(payload, level=value)
            elif operation == _OP_DECOMPRESS:
                result = codec.decompress_mermaid(payload, value)
            else:
                raise OodleLibraryError(
                    f"unknown Oodle worker operation {operation!r}"
                )
            connection.send_bytes(bytes([_STATUS_OK]) + result)
    except EOFError:
        return
    except BaseException as exc:
        try:
            text = f"{type(exc).__name__}: {exc}".encode(
                "utf-8", "replace"
            )[:_MAX_ERROR_TEXT]
            connection.send_bytes(bytes([_STATUS_ERROR]) + text)
        except BaseException:
            pass
    finally:
        connection.close()


class NativeOodle:
    """Process-isolated native Linux Oodle codec."""

    NORMAL_LEVEL = 4
    START_TIMEOUT = 30.0
    OPERATION_TIMEOUT = 120.0
    MAX_IPC_PAYLOAD = 1024 * 1024
    MAX_IPC_RAW_SIZE = 1024 * 1024

    def __init__(self, library_path: str | Path, *, trusted_sha256: str | None = None) -> None:
        self.path = Path(library_path).expanduser()
        self._lock = threading.RLock()
        self._closed = False
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=True)
        self._connection = parent
        self._process = context.Process(
            target=_oodle_worker,
            args=(child, str(self.path), trusted_sha256),
            name="anvil-oodle-worker",
            daemon=True,
        )
        try:
            self._process.start()
            child.close()
            status, value = self._receive(self.START_TIMEOUT)
            if status != "ready":
                raise OodleLibraryError(
                    f"native Oodle worker initialization failed: {value}"
                )
            self._sdk_version = tuple(value)
        except BaseException as original:
            self._closed = True
            cleanup_failure: BaseException | None = None
            try:
                child.close()
            except OSError as exc:
                cleanup_failure = exc
            try:
                self._terminate_and_reap_worker()
            except BaseException as exc:
                cleanup_failure = exc
            try:
                parent.close()
            except OSError as exc:
                cleanup_failure = exc
            try:
                self._process.close()
            except (OSError, ValueError) as exc:
                if cleanup_failure is None:
                    cleanup_failure = exc
            if cleanup_failure is not None:
                raise OodleLibraryError(
                    "native Oodle worker initialization cleanup failed"
                ) from cleanup_failure
            raise original

    def _terminate_and_reap_worker(self) -> None:
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=2.0)
        if self._process.is_alive():
            self._process.kill()
            self._process.join(timeout=2.0)
        if self._process.is_alive():
            raise OodleLibraryError("native Oodle worker could not be reaped")

    def _invalidate_worker(self) -> None:
        if self._closed:
            return
        self._closed = True
        failure: BaseException | None = None
        try:
            self._terminate_and_reap_worker()
        except BaseException as exc:
            failure = exc
        try:
            self._connection.close()
        except OSError as exc:
            if failure is None:
                failure = exc
        try:
            self._process.close()
        except (OSError, ValueError) as exc:
            if failure is None:
                failure = exc
        if failure is not None:
            raise OodleLibraryError("native Oodle worker containment failed") from failure

    def _receive(self, timeout: float):
        completed = threading.Event()
        messages: list[bytes] = []
        failures: list[BaseException] = []

        def receive() -> None:
            try:
                messages.append(
                    self._connection.recv_bytes(_MAX_IPC_RESPONSE)
                )
            except BaseException as exc:
                failures.append(exc)
            finally:
                completed.set()

        receiver = threading.Thread(
            target=receive,
            name="anvil-oodle-ipc-receive",
            daemon=True,
        )
        receiver.start()
        timed_out = not completed.wait(timeout)
        exit_code = self._process.exitcode if timed_out else None
        invalidation_failure: BaseException | None = None
        if timed_out:
            try:
                self._invalidate_worker()
            except BaseException as exc:
                invalidation_failure = exc
        receiver.join(timeout=2.0)
        if receiver.is_alive():
            raise OodleLibraryError("native Oodle receiver thread did not stop")
        if invalidation_failure is not None:
            raise OodleLibraryError("native Oodle receive containment failed") from invalidation_failure
        if timed_out:
            if exit_code is not None:
                raise OodleLibraryError(
                    f"native Oodle worker exited with code {exit_code}"
                )
            raise OodleLibraryError("native Oodle worker timed out")
        if failures:
            self._invalidate_worker()
            raise OodleLibraryError("native Oodle worker connection failed") from failures[0]
        message = messages[0]
        if not message:
            self._invalidate_worker()
            raise OodleLibraryError("native Oodle worker returned an empty response")
        status = message[0]
        body = message[1:]
        if status == _STATUS_READY and len(body) == 4:
            return "ready", struct.unpack("<HH", body)
        if status == _STATUS_OK:
            return "ok", body
        if status == _STATUS_ERROR and len(body) <= _MAX_ERROR_TEXT:
            return "error", body.decode("utf-8", "replace")
        self._invalidate_worker()
        raise OodleLibraryError("native Oodle worker returned an invalid response")

    def _send_with_deadline(self, message: bytes, timeout: float) -> None:
        completed = threading.Event()
        failures: list[BaseException] = []

        def send() -> None:
            try:
                self._connection.send_bytes(message)
            except BaseException as exc:
                failures.append(exc)
            finally:
                completed.set()

        sender = threading.Thread(
            target=send,
            name="anvil-oodle-ipc-send",
            daemon=True,
        )
        sender.start()
        timed_out = not completed.wait(timeout)
        invalidation_failure: BaseException | None = None
        if timed_out:
            try:
                self._invalidate_worker()
            except BaseException as exc:
                invalidation_failure = exc
        sender.join(timeout=2.0)
        if sender.is_alive():
            raise OodleLibraryError("native Oodle sender thread did not stop")
        if invalidation_failure is not None:
            raise OodleLibraryError("native Oodle send containment failed") from invalidation_failure
        if timed_out:
            raise OodleLibraryError("native Oodle worker send timed out")
        if failures:
            self._invalidate_worker()
            raise OodleLibraryError("native Oodle worker request failed") from failures[0]

    def _request(self, operation: str, payload: bytes, value: int) -> bytes:
        if operation not in {"compress", "decompress"}:
            raise OodleLibraryError(f"invalid Oodle operation {operation!r}")
        if not isinstance(payload, bytes) or not payload:
            raise OodleLibraryError("Oodle IPC payload must be non-empty bytes")
        if len(payload) > self.MAX_IPC_PAYLOAD:
            raise OodleLibraryError("Oodle IPC payload exceeds the size limit")
        if operation == "compress" and not 1 <= value <= 9:
            raise OodleLibraryError(f"invalid Oodle compression level {value}")
        if operation == "decompress" and not 1 <= value <= self.MAX_IPC_RAW_SIZE:
            raise OodleLibraryError("Oodle IPC raw size exceeds the size limit")
        with self._lock:
            if self._closed:
                raise OodleLibraryError("native Oodle worker is no longer usable")
            if not self._process.is_alive():
                exit_code = self._process.exitcode
                self._invalidate_worker()
                raise OodleLibraryError(
                    f"native Oodle worker exited with code {exit_code}"
                )
            deadline = time.monotonic() + self.OPERATION_TIMEOUT
            opcode = (
                _OP_COMPRESS if operation == "compress" else _OP_DECOMPRESS
            )
            request = bytes([opcode]) + struct.pack("<i", value) + payload
            self._send_with_deadline(request, self.OPERATION_TIMEOUT)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._invalidate_worker()
                raise OodleLibraryError("native Oodle worker timed out")
            status, result = self._receive(remaining)
            if status != "ok":
                self._invalidate_worker()
                raise OodleLibraryError(f"native Oodle worker failed: {result}")
            if not isinstance(result, bytes):
                self._invalidate_worker()
                raise OodleLibraryError("native Oodle worker returned non-bytes output")
            if operation == "decompress" and len(result) != value:
                self._invalidate_worker()
                raise OodleLibraryError(
                    "native Oodle worker returned the wrong decompressed size"
                )
            if operation == "compress" and not result:
                self._invalidate_worker()
                raise OodleLibraryError("native Oodle worker returned empty output")
            return result

    def compress_mermaid(self, raw: bytes, *, level: int = NORMAL_LEVEL) -> bytes:
        return self._request("compress", raw, level)

    def decompress_mermaid(self, packed: bytes, raw_size: int) -> bytes:
        return self._request("decompress", packed, raw_size)

    def close(self) -> None:
        with self._lock:
            if getattr(self, "_closed", True):
                return
            failure: BaseException | None = None
            try:
                self._terminate_and_reap_worker()
            except BaseException as exc:
                failure = exc
            try:
                self._connection.close()
            except OSError as exc:
                if failure is None:
                    failure = exc
            try:
                self._process.close()
            except (OSError, ValueError) as exc:
                if failure is None:
                    failure = exc
            self._closed = True
            if failure is not None:
                raise OodleLibraryError("native Oodle worker close failed") from failure

    def __enter__(self) -> "NativeOodle":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except BaseException:
            pass
