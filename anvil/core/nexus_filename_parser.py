"""Extract Nexus Mod-ID from archive filenames (MO2-compatible regex)."""

import re

_NEXUS_FILENAME_RE = re.compile(
    r'^(.+?)'              # Gruppe 1: Mod-Name (non-greedy)
    r'-(\d{2,})'           # Gruppe 2: Mod-ID (mind. 2-stellig, nach Bindestrich)
    r'(?:-[\d]+)*'         # optionale Versions-/File-ID-Segmente
    r'-(\d{9,11})'         # optionale Timestamp-Gruppe (9-11 Stellen)
    r'\.(?:zip|rar|7z)$',  # Dateiendung
    re.IGNORECASE
)


def extract_nexus_mod_id(filename: str) -> int | None:
    """Versuche Nexus Mod-ID aus dem Dateinamen zu extrahieren.

    Nexus-Dateinamen: ModName-ModID-version[-extra]-timestamp.ext
    Returns: Mod-ID als int, oder None wenn nicht erkennbar.
    """
    m = _NEXUS_FILENAME_RE.match(filename)
    if m:
        try:
            return int(m.group(2))
        except ValueError:
            pass

    # Fallback: Erste Zahlengruppe >= 2 Stellen zwischen Bindestrichen
    candidates = re.findall(r'-(\d{2,})-', filename)
    if candidates:
        try:
            return int(candidates[0])
        except ValueError:
            pass

    return None
