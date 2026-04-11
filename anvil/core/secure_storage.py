"""Secure credential storage for API keys.

Uses the system keyring (KWallet, GNOME Keyring, etc.) as primary storage.
Falls back to an encrypted local file when no keyring service is available.
The file is encrypted with Fernet using a device-bound key derived from
/etc/machine-id, so credentials are only readable on the same machine.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

_SERVICE = "AnvilOrganizer"
_ACCOUNT = "nexus_api_key"
_CRED_FILE = "credentials.bin"
_SALT = b"anvil-organizer-credential-store"

_keyring_available: bool | None = None


def _config_dir() -> Path:
    return Path.home() / ".anvil-organizer"


def _cred_path() -> Path:
    return _config_dir() / _CRED_FILE


# ── Keyring probe ────────────────────────────────────────────────────

def _check_keyring() -> bool:
    """Test once whether the system keyring is usable."""
    global _keyring_available
    if _keyring_available is not None:
        return _keyring_available
    try:
        import keyring
        import keyring.errors
        # Some backends accept set_password but silently fail on get.
        # A quick get_password call is the safest probe.
        keyring.get_password(_SERVICE, "__probe__")
        _keyring_available = True
    except Exception:
        _keyring_available = False
    return _keyring_available


# ── Encrypted file backend ───────────────────────────────────────────

def _device_key() -> bytes:
    """Derive a Fernet key tied to this machine."""
    import base64
    mid = ""
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            mid = Path(p).read_text().strip()
            if mid:
                break
        except OSError:
            continue
    if not mid:
        mid = "anvil-fallback-id"
    dk = hashlib.pbkdf2_hmac("sha256", mid.encode(), _SALT, 200_000)
    return base64.urlsafe_b64encode(dk)


def _read_file() -> str:
    """Read the API key from the encrypted credential file."""
    p = _cred_path()
    if not p.is_file():
        return ""
    try:
        from cryptography.fernet import Fernet
        cipher = Fernet(_device_key())
        data = json.loads(cipher.decrypt(p.read_bytes()))
        return data.get("key", "").strip()
    except Exception:
        return ""


def _write_file(key: str) -> None:
    """Write the API key to the encrypted credential file."""
    from cryptography.fernet import Fernet
    p = _cred_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    cipher = Fernet(_device_key())
    p.write_bytes(cipher.encrypt(json.dumps({"key": key}).encode()))
    os.chmod(p, 0o600)


def _delete_file() -> None:
    """Remove the encrypted credential file."""
    try:
        p = _cred_path()
        if p.is_file():
            p.unlink()
    except OSError:
        pass


# ── QSettings migration (from pre-1.4.8 plaintext storage) ──────────

def _migrate_qsettings() -> str:
    """Move a legacy plaintext key from QSettings to secure storage."""
    from PySide6.QtCore import QSettings
    path = str(Path.home() / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf")
    settings = QSettings(path, QSettings.Format.IniFormat)
    old = settings.value("nexus/api_key", "")
    if not old:
        return ""
    # Store securely, then remove plaintext
    save_api_key(old)
    settings.remove("nexus/api_key")
    print("credentials: migrated API key from config to secure storage",
          file=sys.stderr)
    return old


# ── Public API ───────────────────────────────────────────────────────

def load_api_key() -> str:
    """Load the Nexus API key from keyring or encrypted file."""
    if _check_keyring():
        try:
            import keyring
            key = keyring.get_password(_SERVICE, _ACCOUNT)
            if key:
                return key.strip()
        except Exception as e:
            print(f"credentials: keyring read failed: {e}", file=sys.stderr)

    # Encrypted file fallback
    key = _read_file()
    if key:
        return key

    # Legacy migration from QSettings plaintext
    return _migrate_qsettings()


def save_api_key(key: str) -> None:
    """Persist the API key to keyring or encrypted file."""
    key = key.strip()
    if _check_keyring():
        try:
            import keyring
            keyring.set_password(_SERVICE, _ACCOUNT, key)
            return
        except Exception as e:
            print(f"credentials: keyring write failed: {e}", file=sys.stderr)

    # Fallback to encrypted file
    try:
        _write_file(key)
    except Exception as e:
        print(f"credentials: encrypted file write failed: {e}", file=sys.stderr)


def delete_api_key() -> None:
    """Remove the API key from all storage backends."""
    _delete_file()
    if _check_keyring():
        try:
            import keyring
            keyring.delete_password(_SERVICE, _ACCOUNT)
        except Exception:
            pass
    # Clean up legacy QSettings entry
    try:
        from PySide6.QtCore import QSettings
        path = str(Path.home() / ".config" / "AnvilOrganizer" / "AnvilOrganizer.conf")
        settings = QSettings(path, QSettings.Format.IniFormat)
        settings.remove("nexus/api_key")
    except Exception:
        pass
