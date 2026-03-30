"""Red Dead Redemption 2 game plugin for Anvil Organizer.

Features implemented:
  - Store detection (Steam)
  - Proton prefix paths for documents and saves
  - Executable list
  - Framework mods (Script Hook RDR2, ASI Loader, LML)

TODO (future):
  - LML mod scanning (lml/ subfolders with install.xml)
  - ASI mod scanning (*.asi in game root, excluding framework ASIs)
  - Script mod scanning (Scripts/ folder)
  - LML stream mod detection (.ytd/.ymt without install.xml)
  - Save game metadata parsing
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class RDR2Game(BaseGame):
    """Red Dead Redemption 2 support plugin."""

    # ── Plugin-Metadaten ───────────────────────────────────────────────

    Name = "Red Dead Redemption 2 Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # ── Spiel-Attribute ────────────────────────────────────────────────

    GameName = "Red Dead Redemption 2"
    GameShortName = "reddeadredemption2"
    GameBinary = "RDR2.exe"
    GameDataPath = ""  # Mods go into the game root directory

    GameSteamId = 1174180

    GameDocumentsDirectory = ""  # resolved dynamically via gameDocumentsDirectory()
    GameSavesDirectory = ""     # resolved dynamically via gameSavesDirectory()
    GameSaveExtension = ""

    GameNexusId = 0  # TODO: set when known
    GameNexusName = "reddeadredemption2"

    GameDirectInstallMods = [
        "ScriptHookRDR2",
        "ASI Loader",

        "Lenny's Mod Loader",
        "LML",
    ]

    GameLMLPath = "lml"  # LML-Mods werden nach <game>/lml/<modname>/ deployt

    # ── Windows-Pfade (innerhalb Proton-Prefix) ────────────────────────

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/Documents"
        "/Rockstar Games/Red Dead Redemption 2"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/Documents"
        "/Rockstar Games/Red Dead Redemption 2/Profiles"
    )

    # ── Ueberschriebene Methoden ──────────────────────────────────────

    def gameDocumentsDirectory(self) -> Path | None:
        """Return the game's documents directory.

        For Steam (Proton): derived from the Proton prefix.
        Returns None if no prefix is found.
        """
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_DOCUMENTS
            if path.is_dir():
                return path
        return None

    def gameSavesDirectory(self) -> Path | None:
        """Return the save game directory.

        For Steam (Proton): derived from the Proton prefix.
        Returns None if no prefix is found.
        """
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_SAVES
            if path.is_dir():
                return path
        return None

    def listSaves(self, folder: Path) -> list[Path]:
        """Find RDR2 save files (SRDR3* pattern, no extension).

        Saves live inside profile sub-folders under the Profiles directory,
        e.g. Profiles/A9B1B2C2/SRDR30000.
        """
        if not folder.is_dir():
            return []
        results: list[Path] = []
        for profile_dir in folder.iterdir():
            if not profile_dir.is_dir():
                continue
            for f in profile_dir.iterdir():
                if f.is_file() and f.name.startswith("SRDR3"):
                    results.append(f)
        return sorted(results, key=lambda p: p.stat().st_mtime, reverse=True)

    def executables(self) -> list[dict[str, str]]:
        """Return executable definitions for Red Dead Redemption 2."""
        return [
            {"name": "Red Dead Redemption 2", "binary": self.GameBinary},
        ]

    def get_framework_mods(self) -> list[FrameworkMod]:
        """Return known framework mods for Red Dead Redemption 2."""
        return [
            FrameworkMod(
                name="Script Hook RDR2",
                pattern=["ScriptHookRDR2.dll"],
                target="",
                description="Ermoeglicht ASI-Plugins und Scripte",
                detect_installed=["ScriptHookRDR2.dll"],
                required_by=["ASI-Mods", "Script-Mods"],
                nexus_id=56,
            ),
            FrameworkMod(
                name="ASI Loader",
                pattern=["dinput8.dll"],
                target="",
                description="Laedt .asi Plugins beim Spielstart",
                detect_installed=["dinput8.dll", "version.dll"],
                required_by=["ASI-Mods"],
            ),
            FrameworkMod(
                name="Lenny's Mod Loader (LML)",
                pattern=["vfs.asi"],
                target="",
                description="Mod Loader fuer Datei-Replacements und LML-Mods",
                detect_installed=["vfs.asi", "lml"],
                required_by=["LML-Mods", "Stream-Mods"],
            ),
        ]

    def get_conflict_ignores(self) -> list[str]:
        """Return patterns for harmless files in RDR2 mods."""
        return [
            "**/readme*.txt",
            "**/changelog*.txt",
            "**/*.md",
        ]

    def iniFiles(self) -> list[str]:
        """Return config files managed by Red Dead Redemption 2."""
        return ["system.xml"]
