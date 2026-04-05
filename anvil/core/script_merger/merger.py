"""Script-Merger — Auto-Merge fuer nicht-kollidierende Hunks."""

from anvil.core.script_merger.models import (
    MergeStatus, MergeResult, ScriptConflict,
)
from anvil.core.script_merger.ws_codec import read_script_file


class ScriptMerger:
    """Fuehrt Auto-Merges fuer AUTO_MERGEABLE Konflikte durch.

    Algorithmus:
      1. Starte mit Vanilla-Inhalt als Basis (Zeilen-Liste)
      2. Sammle ALLE Hunks von ALLEN Mods
      3. Sortiere Hunks nach start_line ABSTEIGEND (Bottom-Up)
      4. Ersetze basis[start_line:end_line] durch hunk.mod_lines
      5. Ergebnis: Merged Content mit allen Aenderungen
    """

    def auto_merge(self, conflict: ScriptConflict) -> MergeResult:
        """Auto-Merge fuer einen einzelnen AUTO_MERGEABLE Konflikt.

        Wendet alle Hunks Bottom-Up an, damit Zeilennummern stabil bleiben.
        """
        if conflict.merge_status != MergeStatus.AUTO_MERGEABLE:
            return MergeResult(
                conflict=conflict, success=False, method="auto",
                error_message="Nicht auto-mergebar",
            )
        if conflict.vanilla_path is None:
            return MergeResult(
                conflict=conflict, success=False, method="auto",
                error_message="Keine Vanilla-Referenz vorhanden",
            )
        try:
            vanilla_text = read_script_file(conflict.vanilla_path)
            basis = vanilla_text.splitlines(keepends=True)

            # Alle Hunks aller Mods sammeln
            all_hunks = []
            for mv in conflict.mod_versions:
                for hunk in mv.diff_hunks:
                    all_hunks.append(hunk)

            # Sortiere ABSTEIGEND nach start_line (Bottom-Up-Anwendung)
            all_hunks.sort(key=lambda h: h.start_line, reverse=True)

            # Jeden Hunk anwenden
            for hunk in all_hunks:
                basis[hunk.start_line:hunk.end_line] = hunk.mod_lines

            merged = "".join(basis)
            conflict.merge_status = MergeStatus.MERGED
            return MergeResult(
                conflict=conflict, success=True,
                merged_content=merged, method="auto",
            )
        except Exception as e:
            return MergeResult(
                conflict=conflict, success=False,
                method="auto", error_message=str(e),
            )

    def auto_merge_all(self, conflicts: list[ScriptConflict],
                       progress_callback=None) -> list[MergeResult]:
        """Batch Auto-Merge fuer alle AUTO_MERGEABLE Konflikte.

        Ueberspringt CONFLICT, IGNORED, MERGED und UNSCANNED.

        Args:
            conflicts: Liste aller Konflikte.
            progress_callback: Optional, wird mit (aktuell, gesamt) aufgerufen.

        Returns:
            Liste der MergeResult-Objekte (nur fuer tatsaechlich versuchte Merges).
        """
        results = []
        mergeable = [c for c in conflicts
                     if c.merge_status == MergeStatus.AUTO_MERGEABLE]
        for i, conflict in enumerate(mergeable):
            if progress_callback:
                progress_callback(i, len(mergeable))
            results.append(self.auto_merge(conflict))
        if progress_callback:
            progress_callback(len(mergeable), len(mergeable))
        return results
