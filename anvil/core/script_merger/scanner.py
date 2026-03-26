"""Script-Scanner — findet Konflikte zwischen aktiven Witcher-3-Mods."""

import difflib
from pathlib import Path

from anvil.core.script_merger.models import (
    MergeStatus, DiffHunk, ModVersion, ScriptConflict,
)
from anvil.core.script_merger.ws_codec import read_script_file, file_hash


class ScriptScanner:
    """Scannt aktive Mods nach .ws- und .xml-Konflikten.

    Unterstuetzt beide Mod-Patterns:
      A: .mods/<AnvilName>/mods/<WitcherMod>/content/scripts/
      B: .mods/<AnvilName>/<WitcherMod>/content/scripts/
    """

    def __init__(self, vanilla_scripts_dir: Path, mods_dir: Path,
                 active_mod_names: list[str],
                 check_scripts: bool = True, check_xml: bool = True):
        self._vanilla_dir = vanilla_scripts_dir
        self._mods_dir = mods_dir
        self._active_mods = active_mod_names
        self._check_scripts = check_scripts
        self._check_xml = check_xml

    # ------------------------------------------------------------------
    # Interne Helfer
    # ------------------------------------------------------------------

    def _find_script_dirs(self, mod_path: Path) -> list[tuple[str, Path]]:
        """Findet alle content/scripts/ Verzeichnisse in einem Mod.

        Gibt Liste von (witcher_mod_name, scripts_dir) zurueck.
        Funktioniert fuer Pattern A und B gleichermassen dank rglob.
        """
        results = []
        for content_dir in mod_path.rglob("content"):
            scripts_dir = content_dir / "scripts"
            if scripts_dir.is_dir():
                witcher_mod_name = content_dir.parent.name
                results.append((witcher_mod_name, scripts_dir))
        return results

    def _find_xml_dirs(self, mod_path: Path) -> list[tuple[str, Path]]:
        """Findet content/-Verzeichnisse die .xml-Dateien enthalten (nicht unter scripts/).

        Gibt Liste von (witcher_mod_name, content_dir) zurueck.
        Ignoriert content/scripts/ — dort liegen .ws-Dateien, keine relevanten XMLs.
        """
        results = []
        for content_dir in mod_path.rglob("content"):
            if not content_dir.is_dir():
                continue
            # Nur direkte .xml-Dateien im content/-Ordner selbst (nicht in scripts/)
            scripts_dir = content_dir / "scripts"
            xml_files = [
                f for f in content_dir.rglob("*.xml")
                if not f.is_relative_to(scripts_dir)
            ]
            if xml_files:
                witcher_mod_name = content_dir.parent.name
                results.append((witcher_mod_name, content_dir))
        return results

    # ------------------------------------------------------------------
    # Hauptscan
    # ------------------------------------------------------------------

    def scan(self, progress_callback=None) -> list[ScriptConflict]:
        """Scannt alle aktiven Mods und gibt Konflikte zurueck.

        Args:
            progress_callback: Optional, wird mit (aktuell, gesamt) aufgerufen.

        Returns:
            Liste von ScriptConflict-Objekten (nur Dateien mit >= 2 Mods).
        """
        # 1. Sammle alle Script-Dateien aller aktiven Mods
        # file_map: relative_path -> list[ModVersion]
        file_map: dict[str, list[ModVersion]] = {}

        total_mods = len(self._active_mods)
        for i, mod_name in enumerate(self._active_mods):
            if progress_callback:
                progress_callback(i, total_mods)
            mod_path = self._mods_dir / mod_name
            if not mod_path.is_dir():
                continue

            # .ws Scripts
            if self._check_scripts:
                for witcher_mod_name, scripts_dir in self._find_script_dirs(mod_path):
                    for ws_file in scripts_dir.rglob("*.ws"):
                        rel = ws_file.relative_to(scripts_dir)
                        # local/-Dateien ausschliessen (mod-eigene Scripts)
                        if rel.parts and rel.parts[0] == "local":
                            continue
                        rel_str = str(rel).replace("\\", "/")
                        mv = ModVersion(
                            mod_name=mod_name,
                            witcher_mod_name=witcher_mod_name,
                            file_path=ws_file,
                            file_hash=file_hash(ws_file),
                        )
                        file_map.setdefault(rel_str, []).append(mv)

            # .xml unter content/
            if self._check_xml:
                for witcher_mod_name, content_dir in self._find_xml_dirs(mod_path):
                    for xml_file in content_dir.rglob("*.xml"):
                        rel = xml_file.relative_to(content_dir)
                        rel_str = "xml/" + str(rel).replace("\\", "/")
                        mv = ModVersion(
                            mod_name=mod_name,
                            witcher_mod_name=witcher_mod_name,
                            file_path=xml_file,
                            file_hash=file_hash(xml_file),
                        )
                        file_map.setdefault(rel_str, []).append(mv)

        # 2. Nur Dateien behalten die von >= 2 verschiedenen Mods geaendert werden
        conflicts = []
        for rel_path, versions in sorted(file_map.items()):
            unique_mods = {v.mod_name for v in versions}
            if len(unique_mods) < 2:
                continue

            # Vanilla-Version suchen
            vanilla_path = None
            if rel_path.startswith("xml/"):
                # XML: im Vanilla content0/ suchen (ohne xml/ Prefix)
                vanilla_candidate = self._vanilla_dir.parent / rel_path[4:]
            else:
                vanilla_candidate = self._vanilla_dir / rel_path
            if vanilla_candidate.is_file():
                vanilla_path = vanilla_candidate

            conflict = ScriptConflict(
                relative_path=rel_path,
                vanilla_path=vanilla_path,
                mod_versions=versions,
            )

            # 3. Diffs berechnen und Status bestimmen
            if vanilla_path is None:
                conflict.merge_status = MergeStatus.CONFLICT
            else:
                self._compute_diffs(conflict)

            conflicts.append(conflict)

        if progress_callback:
            progress_callback(total_mods, total_mods)

        return conflicts

    # ------------------------------------------------------------------
    # Diff-Berechnung
    # ------------------------------------------------------------------

    def _compute_diffs(self, conflict: ScriptConflict) -> None:
        """Berechnet 3-Way-Diff fuer jede Mod-Version gegen Vanilla.

        Setzt merge_status auf AUTO_MERGEABLE oder CONFLICT je nachdem
        ob Hunks sich ueberlappen.
        """
        vanilla_text = read_script_file(conflict.vanilla_path)
        vanilla_lines = vanilla_text.splitlines(keepends=True)

        all_hunks = []
        for mv in conflict.mod_versions:
            mod_text = read_script_file(mv.file_path)
            mod_lines = mod_text.splitlines(keepends=True)

            hunks = self._extract_hunks(vanilla_lines, mod_lines)
            mv.diff_hunks = hunks
            all_hunks.extend(hunks)

        # Pruefe auf Ueberlappungen zwischen ALLEN Hunks ALLER Mods
        has_overlap = False
        for i, h1 in enumerate(all_hunks):
            for h2 in all_hunks[i + 1:]:
                if h1.overlaps(h2):
                    has_overlap = True
                    break
            if has_overlap:
                break

        conflict.merge_status = (
            MergeStatus.CONFLICT if has_overlap else MergeStatus.AUTO_MERGEABLE
        )

    def _extract_hunks(self, vanilla_lines: list[str],
                       mod_lines: list[str]) -> list[DiffHunk]:
        """Extrahiert Diff-Hunks zwischen Vanilla und Mod mittels SequenceMatcher."""
        sm = difflib.SequenceMatcher(None, vanilla_lines, mod_lines, autojunk=False)
        hunks = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                continue
            hunks.append(DiffHunk(
                start_line=i1,
                end_line=i2,
                vanilla_lines=vanilla_lines[i1:i2],
                mod_lines=mod_lines[j1:j2],
            ))
        return hunks
