"""Charakter-Presets als eigene Mods ablegen.

Ein Preset ist keine Mod im ueblichen Sinn -- es ist eine Einstellungsdatei,
die ein Framework einliest. Trotzdem wird hier eine gewoehnliche Mod daraus
gebaut, mit dem Zielpfad schon im Ordner. Das hat zwei Gruende: Anvil kann
sie dann ohne Sonderweg ausrollen, abschalten und loeschen, und ein Update
des Frameworks wirft sie nicht weg -- was passieren wuerde, schriebe man sie
in dessen Ordner hinein.

Welche Dateiendung ein Preset hat und wohin es gehoert, weiss das
Spiel-Plugin (``GamePresetKinds``). Dieses Modul kennt nur die Regeln.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

# Geschlecht als Text, damit es unveraendert als Ordnername taugt.
FEMALE = "female"
MALE = "male"
UNKNOWN = ""


@dataclass
class PresetKind:
    """Beschreibt eine Preset-Art eines Spiels.

    Attributes:
        name:        Anzeigename, z.B. "ACU-Charakter".
        suffix:      Dateiendung inklusive Punkt, z.B. ".preset".
        target:      Zielordner im Spiel, ohne die Geschlechts-Ebene.
        variants:    Unterordner je Geschlecht. Leer = keine Aufteilung.
        markers:     Erkennungszeichen je Variante. Kommt eines davon in der
                     Datei vor, gilt die Variante als erkannt.
    """

    name: str
    suffix: str
    target: str
    variants: list[str] = field(default_factory=list)
    markers: dict[str, list[str]] = field(default_factory=dict)


def find_presets(root: Path, kind: PresetKind) -> list[Path]:
    """Alle Preset-Dateien unterhalb von *root*, nach Namen sortiert.

    Nach Namen und nicht nach Pfad, weil die Liste so beim Nachfragen
    vorgelegt wird -- dort sucht man nach dem Namen, nicht nach dem Ordner.
    """
    if not root.is_dir():
        return []
    return sorted(
        (p for p in root.rglob(f"*{kind.suffix}") if p.is_file()),
        key=lambda p: (p.name.lower(), str(p).lower()),
    )


def detect_variant(path: Path, kind: PresetKind) -> str:
    """Bestimmt die Variante einer Preset-Datei.

    Drei Stufen, von der sichersten zur unsichersten:

    1. Der Pfad im Archiv -- liegt die Datei in ``female/``, ist die Sache klar.
    2. Der Dateiname -- viele Autoren schreiben es hinein.
    3. Der Inhalt -- die Erkennungszeichen aus dem Plugin.

    Liefert ``UNKNOWN``, wenn keine Stufe greift oder zwei Varianten
    gleichauf liegen. Dann muss gefragt werden.
    """
    if not kind.variants:
        return UNKNOWN

    teile = [t.lower() for t in path.parts]
    for variante in kind.variants:
        if variante.lower() in teile:
            return variante

    name = path.stem.lower()
    treffer = [v for v in kind.variants if v.lower() in name]
    if len(treffer) == 1:
        return treffer[0]

    return _detect_by_content(path, kind)


def _detect_by_content(path: Path, kind: PresetKind) -> str:
    """Zaehlt die Erkennungszeichen je Variante im Dateiinhalt."""
    if not kind.markers:
        return UNKNOWN

    try:
        inhalt = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return UNKNOWN

    punkte = {
        v: sum(1 for m in kind.markers.get(v, []) if m in inhalt)
        for v in kind.variants
    }
    beste = max(punkte.values(), default=0)
    if beste == 0:
        return UNKNOWN

    fuehrend = [v for v, p in punkte.items() if p == beste]
    return fuehrend[0] if len(fuehrend) == 1 else UNKNOWN


def target_path(kind: PresetKind, variant: str, dateiname: str) -> Path:
    """Pfad der Preset-Datei innerhalb des Mod-Ordners."""
    ziel = Path(kind.target)
    if variant:
        ziel = ziel / variant
    return ziel / dateiname


def build_mod(
    quelle: Path,
    mods_dir: Path,
    mod_name: str,
    kind: PresetKind,
    variant: str,
) -> Path:
    """Legt aus einer Preset-Datei einen fertigen Mod-Ordner an.

    Der Zielpfad steckt im Ordner, damit der gewoehnliche Deploy-Weg ihn
    ohne Sonderbehandlung an die richtige Stelle bringt.

    Returns:
        Der angelegte Mod-Ordner.

    Raises:
        FileExistsError: Wenn es den Ordner schon gibt -- nichts wird
            ueberschrieben, der Aufrufer muss einen anderen Namen waehlen.
    """
    ziel_mod = mods_dir / mod_name
    if ziel_mod.exists():
        raise FileExistsError(mod_name)

    ziel_datei = ziel_mod / target_path(kind, variant, quelle.name)
    ziel_datei.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(quelle, ziel_datei)
    return ziel_mod


def suggest_mod_name(quelle: Path, variant: str, kind: PresetKind) -> str:
    """Vorschlag fuer den Mod-Ordnernamen.

    Das Geschlecht steht mit im Namen, sonst kollidieren zwei Presets
    gleichen Namens fuer weiblich und maennlich miteinander.
    """
    basis = quelle.stem.strip() or kind.name
    if variant:
        return f"{kind.name} - {basis} ({variant})"
    return f"{kind.name} - {basis}"
