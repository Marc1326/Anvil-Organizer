"""Read and write MO2-compatible meta.ini files for individual mods.

Each mod folder under ``.mods/<name>/`` may contain a ``meta.ini``
with metadata such as display name, version, author, etc.

Format (INI, configparser-compatible)::

    [General]
    modid=0
    version=1.0
    newestVersion=
    category=
    nexusFileStatus=1
    installationFile=
    repository=Nexus

    [installed]
    name=Mein Mod Name
    author=Modder123
    description=Beschreibung
    url=https://www.nexusmods.com/...
    installDate=2026-02-08T15:00:00
"""

from __future__ import annotations

import configparser
import sys
from datetime import datetime, timezone
from pathlib import Path


def read_meta_ini(mod_path: Path) -> dict[str, str]:
    """Read ``meta.ini`` from *mod_path* and return a flat dict.

    Missing keys are **not** added; the caller must handle defaults.

    Args:
        mod_path: Path to a mod folder (e.g. ``.mods/MyMod/``).

    Returns:
        Dict with all key/value pairs found.  Empty dict on error.
    """
    ini = mod_path / "meta.ini"
    if not ini.is_file():
        return {}

    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str  # preserve case

    try:
        cp.read(str(ini), encoding="utf-8")
    except (configparser.Error, OSError) as exc:
        print(
            f"mod_metadata: failed to read {ini}: {exc}",
            file=sys.stderr,
        )
        return {}

    data: dict[str, str] = {}

    for section in cp.sections():
        for key, value in cp.items(section):
            # Flatten: prefix with section name for [installed], keep
            # [General] keys as-is to match MO2 conventions.
            if section == "General":
                data[key] = value
            else:
                data[key] = value

    return data


def write_meta_ini(mod_path: Path, data: dict[str, str]) -> None:
    """Write or update ``meta.ini`` in *mod_path*.

    Reads the existing file first (if any) and merges *data* on top.

    Args:
        mod_path: Path to a mod folder.
        data: Key/value pairs to write.  Keys that belong to the
              ``[installed]`` section: name, author, description,
              url, installDate.  Everything else goes into ``[General]``.
    """
    ini = mod_path / "meta.ini"

    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str

    if ini.is_file():
        try:
            cp.read(str(ini), encoding="utf-8")
        except (configparser.Error, OSError):
            pass  # start fresh

    _INSTALLED_KEYS = {"name", "author", "description", "url", "installDate"}

    if not cp.has_section("General"):
        cp.add_section("General")
    if not cp.has_section("installed"):
        cp.add_section("installed")

    for key, value in data.items():
        if key in _INSTALLED_KEYS:
            cp.set("installed", key, str(value))
        else:
            cp.set("General", key, str(value))

    try:
        mod_path.mkdir(parents=True, exist_ok=True)
        with open(ini, "w", encoding="utf-8") as fh:
            cp.write(fh)
    except OSError as exc:
        print(
            f"mod_metadata: failed to write {ini}: {exc}",
            file=sys.stderr,
        )


def create_default_meta_ini(mod_path: Path, mod_name: str) -> None:
    """Create a minimal ``meta.ini`` for a newly installed mod.

    Args:
        mod_path: Path to the mod folder.
        mod_name: Display name for the mod.
    """
    data = {
        "modid": "0",
        "version": "",
        "newestVersion": "",
        "category": "",
        "nexusFileStatus": "1",
        "installationFile": "",
        "repository": "Nexus",
        "name": mod_name,
        "author": "",
        "description": "",
        "url": "",
        "installDate": datetime.now(timezone.utc).isoformat(),
    }
    write_meta_ini(mod_path, data)
