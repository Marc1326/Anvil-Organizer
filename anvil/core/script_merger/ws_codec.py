"""Witcher-Script Codec — BOM-Detection, UTF-16 LE Schreiben, Hashing."""

import hashlib
from pathlib import Path


def read_script_file(path: Path) -> str:
    """Liest eine Script-Datei mit BOM-Detection.

    Erkennt: FF FE = UTF-16 LE, FE FF = UTF-16 BE, EF BB BF = UTF-8.
    Fallback: UTF-8, dann Latin-1.
    """
    raw = path.read_bytes()
    if raw[:2] == b'\xff\xfe':
        return raw.decode('utf-16-le').lstrip('\ufeff')
    elif raw[:2] == b'\xfe\xff':
        return raw.decode('utf-16-be').lstrip('\ufeff')
    elif raw[:3] == b'\xef\xbb\xbf':
        return raw[3:].decode('utf-8')
    else:
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError:
            return raw.decode('latin-1')


def write_script_file(path: Path, content: str) -> None:
    """Schreibt eine Script-Datei in UTF-16 LE mit BOM und CRLF Zeilenenden."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Normalisiere Zeilenenden zu CRLF
    text = content.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
    raw = b'\xff\xfe' + text.encode('utf-16-le')
    path.write_bytes(raw)


def file_hash(path: Path) -> str:
    """SHA256-Hash der rohen Datei-Bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
