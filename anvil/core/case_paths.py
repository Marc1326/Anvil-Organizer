"""Zielordner an die Schreibweise angleichen, die schon im Spiel liegt.

Mod-Archive kommen aus der Windows-Welt, wo ``meshes`` und ``Meshes``
derselbe Ordner sind. Auf ext4 sind es zwei -- eine Mod mit beiden
Schreibweisen wird nur zur Haelfte geladen, und zwei Mods mit
unterschiedlicher Schreibweise gehen sich gegenseitig aus dem Weg.

Angeglichen wird ausschliesslich beim Ausrollen. Die Mod selbst bleibt
unangetastet: in ``.mods/`` wird nichts verschoben, umbenannt oder
geloescht, damit ein Fehler hier keine Dateien kosten kann.

``CaseIndex`` haelt die Namen jedes besuchten Ordners im Speicher. Ohne
das laeuft die Aufloesung quadratisch -- pro Datei einmal durch das
gesamte Zielverzeichnis.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath


class CaseIndex:
    """Merkt sich je Ordner, welche Namen dort in welcher Schreibweise liegen.

    Args:
        roots: Orte, an denen nach einer bestehenden Schreibweise gesucht
            wird -- der erste Treffer gewinnt. Beim Overlay steht hier der
            echte Spielordner **vor** der Stapelschicht: der Kernel legt nur
            buchstabengleiche Ordner zusammen, also muss sich die Schicht
            nach dem Spiel richten und nicht umgekehrt.
    """

    def __init__(self, *roots: Path) -> None:
        self._roots = [r for r in roots if r is not None]
        # Schluessel ist (Nummer der Wurzel, Pfadteile) statt eines Path --
        # das spart bei jedem Deploy Hunderttausende Wegwerf-Objekte.
        self._cache: dict[tuple[int, tuple[str, ...]], dict[str, str]] = {}

    def _names(self, nr: int, teile: tuple[str, ...]) -> dict[str, str]:
        bekannt = self._cache.get((nr, teile))
        if bekannt is None:
            bekannt = {}
            try:
                for kind in self._roots[nr].joinpath(*teile).iterdir():
                    bekannt.setdefault(kind.name.lower(), kind.name)
            except OSError:
                pass
            self._cache[(nr, teile)] = bekannt
        return bekannt

    def resolve(self, rel: Path | str) -> Path:
        """*rel* mit der Schreibweise zurueckgeben, die bereits existiert.

        Gibt es sie noch nirgends, bleibt die gewuenschte Schreibweise
        stehen und wird vorgemerkt -- die naechste Mod trifft dann auf
        dieselbe Entscheidung, auch wenn der Ordner noch gar nicht auf der
        Platte liegt.

        Absolute Angaben und ``..`` werden verworfen: die Funktion baut
        Zielpfade und darf nirgends hinausfuehren.
        """
        teile: tuple[str, ...] = ()
        for teil in PurePosixPath(str(rel).replace("\\", "/")).parts:
            if not teil or teil in (".", "..", "/"):
                continue
            klein = teil.lower()
            gefunden = None
            for nr in range(len(self._roots)):
                gefunden = self._names(nr, teile).get(klein)
                if gefunden is not None:
                    break
            if gefunden is None and self._roots:
                # Im Schreibziel vormerken -- das ist die letzte Wurzel.
                self._names(len(self._roots) - 1, teile)[klein] = teil
            teile += (gefunden or teil,)
        return Path(*teile) if teile else Path()
