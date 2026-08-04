"""Baut die Mod-Schicht fuer den Overlay-Deploy.

Der Kernel nimmt keine dreihundert lowerdirs in einem Mount-Auftrag entgegen --
die Optionszeile passt nicht in eine Speicherseite.  Deshalb werden alle Mods
vorher per Hardlink zu **einer** Schicht zusammengefuehrt, von der niedrigsten
zur hoechsten Prioritaet.  Wer spaeter kommt, gewinnt; das ist dieselbe
Reihenfolge, die der Symlink-Deployer benutzt.

Hardlinks kosten keinen Platz und keine Zeit fuer Daten.  Liegt ein Mod auf
einem anderen Dateisystem als die Schicht, wird die Datei kopiert.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from anvil.core.deploy_rules import (
    SKIP_DIRS,
    apply_data_path,
    goes_into_archive,
    is_metadata,
    strip_root,
    target_rel,
)
from anvil.core.mod_list_io import read_active_mods, read_global_modlist

__all__ = ["OverlayStage", "StageResult", "is_metadata", "target_rel"]


@dataclass
class StageResult:
    success: bool = True
    mods_staged: int = 0
    files_linked: int = 0
    files_copied: int = 0
    errors: list[str] = field(default_factory=list)
    # Zielbasis -> Schicht.  Leerer Schluessel ist der Spielordner; andere
    # Schluessel sind eigene Zielpfade aus den Trenner-Einstellungen und
    # brauchen je einen eigenen Mount.
    layers: dict[str, Path] = field(default_factory=dict)


def _place(src: Path, dest: Path, result: StageResult) -> None:
    """Legt *src* als Hardlink unter *dest* ab, hoehere Prioritaet gewinnt.

    Liefert ein Mod einen Pfad als Datei, den ein anderer als Ordner belegt,
    kann hier nichts abgelegt werden. Der Symlink-Weg meldet das als Fehler
    statt abzustuerzen -- hier genauso.
    """
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except (OSError, NotADirectoryError) as exc:
        result.errors.append(f"{dest}: {exc}")
        return

    if dest.is_dir() and not dest.is_symlink():
        result.errors.append(f"{dest}: bereits als Ordner belegt")
        return

    if dest.exists() or dest.is_symlink():
        try:
            dest.unlink()
        except OSError as exc:
            result.errors.append(f"{dest}: {exc}")
            return
    try:
        os.link(src, dest)
        result.files_linked += 1
    except OSError:
        # Anderes Dateisystem oder Hardlink-Grenze erreicht
        try:
            shutil.copy2(src, dest)
            result.files_copied += 1
        except OSError as exc:
            result.errors.append(f"{src}: {exc}")


class OverlayStage:
    """Fuehrt die aktiven Mods zu einer Schicht zusammen."""

    def __init__(
        self,
        mods_path: Path,
        profiles_dir: Path,
        profile_name: str = "Default",
        *,
        data_path: str = "",
        nest_under_mod_name: bool = False,
        multi_folder_routes: dict[str, str] | None = None,
        direct_patterns: list[str] | None = None,
        lml_path: str = "",
        redmod_path: str = "",
        separator_deploy_paths: dict[str, str] | None = None,
        needs_ba2_packing: bool = False,
        ba2_loose_paths: list[str] | None = None,
        skipped_mods: set[str] | None = None,
    ) -> None:
        self._mods_path = mods_path
        self._profiles_dir = profiles_dir
        self._profile_path = profiles_dir / profile_name
        self._data_path = data_path
        self._nest = nest_under_mod_name
        self._routes = multi_folder_routes or {}
        self._direct = [p.lower() for p in (direct_patterns or [])]
        self._lml_path = lml_path
        self._redmod_path = redmod_path
        self._separator_deploy_paths = separator_deploy_paths or {}
        self._needs_ba2_packing = needs_ba2_packing
        self._ba2_loose_paths = ba2_loose_paths or []
        self._skipped = {s.lower() for s in (skipped_mods or set())}

    def set_separator_deploy_paths(self, paths: dict[str, str]) -> None:
        self._separator_deploy_paths = dict(paths or {})

    def set_ba2_packing_enabled(self, enabled: bool) -> None:
        self._needs_ba2_packing = bool(enabled)

    def _packed_away(self, src: Path, rel: Path) -> bool:
        """True, wenn der Archiv-Packer die Datei uebernimmt.

        Solche Dateien duerfen nicht zusaetzlich lose in der Schicht liegen --
        sie wuerden das Archiv ueberdecken. Geprueft wird auf dem Pfad ohne
        Data-Praefix, genau wie im Symlink-Weg.
        """
        if not self._needs_ba2_packing:
            return False
        return goes_into_archive(
            rel, src.suffix,
            loose_paths=self._ba2_loose_paths,
            data_path=self._data_path,
        )

    def is_direct_install(self, mod_name: str) -> bool:
        lower = mod_name.lower()
        return any(pat in lower for pat in self._direct)

    def enabled_mods(self) -> list[str]:
        """Aktive Mods, hoechste Prioritaet zuerst.

        Frameworks kommen immer mit, auch wenn sie im Profil nicht angehakt
        sind -- sie liegen in der Spielwurzel und das Spiel startet sonst nicht.
        """
        order = read_global_modlist(self._profiles_dir)
        active = read_active_mods(self._profile_path)
        names: list[str] = []
        for name in order:
            if name.endswith("_separator"):
                continue
            if name in active or self.is_direct_install(name):
                names.append(name)
        if self._skipped:
            names = [n for n in names if n.lower() not in self._skipped]
        return names

    def folder_mods(self, mod_dir: Path, mod_name: str) -> list[tuple[Path, Path]] | None:
        """Mods, die als ganzer Ordner an einen festen Platz gehoeren.

        Liefert Paare (Quellordner, Zielpfad) oder ``None``, wenn der Mod
        Datei fuer Datei einsortiert wird.  Deckt dieselben drei Faelle ab wie
        der Symlink-Deployer: LML, REDmod mit ``info.json`` im Wurzelver-
        zeichnis, und REDmod mit ``info.json`` in Unterordnern.
        """
        if self._lml_path and (mod_dir / "install.xml").is_file():
            return [(mod_dir, Path(self._lml_path) / mod_name)]

        if not self._redmod_path:
            return None

        # Muster A -- der ganze Mod ist ein REDmod
        if (mod_dir / "info.json").is_file():
            return [(mod_dir, Path(self._redmod_path) / mod_name)]

        # Muster B -- liegt schon unter mods/ und wird normal einsortiert
        if (mod_dir / "mods").is_dir():
            return None

        # Muster C -- ein oder mehrere REDmods in Unterordnern
        gefunden: list[tuple[Path, Path]] = []
        try:
            kinder = sorted(mod_dir.iterdir(), key=lambda p: p.name)
        except OSError:
            return None
        for kind in kinder:
            if (
                kind.is_dir()
                and kind.name.lower() not in SKIP_DIRS
                and (kind / "info.json").is_file()
            ):
                gefunden.append((kind, Path(self._redmod_path) / kind.name))
        return gefunden or None

    def _deploy_base_of(self, mod_name: str, mod_to_separator: dict[str, str]) -> str:
        """Eigener Zielpfad des Trenners, oder leer fuer den Spielordner."""
        trenner = mod_to_separator.get(mod_name, "")
        return self._separator_deploy_paths.get(trenner, "")

    def _separator_map(self) -> dict[str, str]:
        """Ordnet jeden Mod dem Trenner zu, der ueber ihm steht."""
        if not self._separator_deploy_paths:
            return {}
        zuordnung: dict[str, str] = {}
        aktueller = ""
        for name in read_global_modlist(self._profiles_dir):
            if name.endswith("_separator"):
                aktueller = name
            else:
                zuordnung[name] = aktueller
        return zuordnung

    def build(self, base_dir: Path) -> StageResult:
        """Legt die Schichten unter *base_dir* neu an.

        Eine Schicht fuer den Spielordner, je eine weitere fuer jeden eigenen
        Zielpfad aus den Trenner-Einstellungen.
        """
        result = StageResult()

        if base_dir.exists():
            shutil.rmtree(base_dir, ignore_errors=True)
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            result.success = False
            result.errors.append(f"Schicht anlegen: {exc}")
            return result

        mod_to_separator = self._separator_map()
        result.layers[""] = base_dir / "main"

        def schicht(basis: str) -> Path:
            vorhanden = result.layers.get(basis)
            if vorhanden is None:
                vorhanden = base_dir / f"extern-{len(result.layers)}"
                result.layers[basis] = vorhanden
            vorhanden.mkdir(parents=True, exist_ok=True)
            return vorhanden

        schicht("")

        # Niedrigste Prioritaet zuerst -- spaetere ueberschreiben frueheren.
        for mod_name in reversed(self.enabled_mods()):
            mod_dir = self._mods_path / mod_name
            if not mod_dir.is_dir():
                continue

            is_direct = self.is_direct_install(mod_name)
            staged_any = False

            # Ordner-Mods landen immer im Spielordner -- eigene Zielpfade
            # gelten dort auch beim Symlink-Weg nicht.
            ordner = self.folder_mods(mod_dir, mod_name)
            if ordner is not None:
                ziel_schicht = schicht("")
                for quelle, prefix in ordner:
                    for src in quelle.rglob("*"):
                        if not src.is_file():
                            continue
                        rel = src.relative_to(quelle)
                        if is_metadata(src, quelle, rel):
                            continue
                        _place(src, ziel_schicht / prefix / rel, result)
                        staged_any = True
                if staged_any:
                    result.mods_staged += 1
                continue

            ziel_schicht = schicht(self._deploy_base_of(mod_name, mod_to_separator))

            for src in mod_dir.rglob("*"):
                if not src.is_file():
                    continue
                try:
                    rel = src.relative_to(mod_dir)
                except ValueError:
                    continue
                if is_metadata(src, mod_dir, rel):
                    continue

                gestrippt = strip_root(rel)
                if self._packed_away(src, gestrippt):
                    continue
                dest_rel = apply_data_path(
                    gestrippt,
                    mod_name,
                    data_path=self._data_path,
                    is_direct=is_direct,
                    nest_under_mod_name=self._nest,
                    multi_folder_routes=self._routes,
                )
                _place(src, ziel_schicht / dest_rel, result)
                staged_any = True

            if staged_any:
                result.mods_staged += 1

        if result.errors:
            result.success = False
        return result
