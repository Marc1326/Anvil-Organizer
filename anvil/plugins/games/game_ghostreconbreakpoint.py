"""Ghost Recon Breakpoint game plugin for Anvil Organizer.

The plugin provides installation detection and instance setup.  GRB mods use
AnvilNext ``.forge`` archives; they must not be treated as ordinary loose-file
mods.  Forge parsing and staging live in the GRB-specific core modules.
"""

from __future__ import annotations

from pathlib import Path
import os
import stat

from anvil.plugins.base_game import BaseGame


class GhostReconBreakpointGame(BaseGame):
    """Ghost Recon Breakpoint installation and instance metadata."""

    Tested = False

    Name = "Ghost Recon Breakpoint Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "0.1.0"

    GameName = "Tom Clancy's Ghost Recon Breakpoint"
    GameShortName = "ghostreconbreakpoint"
    GameBinary = "GRB.exe"
    GameDataPath = ""

    GameSteamId = 2231380

    GameSaveExtension = ""

    GameNexusId = 0
    GameNexusName = "ghostreconbreakpoint"
    GameSupportURL = "https://www.nexusmods.com/ghostreconbreakpoint"

    ForgePattern = "DataPC*.forge"
    """Game-root archive pattern used for installation validation and scans."""

    RequiresForgeDeployment = True
    """Marker for the GRB-specific archive rebuild/deployment integration."""

    @staticmethod
    def _is_regular_nofollow(path: Path) -> bool:
        """Return whether *path* itself is a regular file, never its target."""
        try:
            value = os.stat(path, follow_symlinks=False)
        except OSError:
            return False
        return stat.S_ISREG(value.st_mode)

    def looksValid(self, path: Path | str) -> bool:
        """Return whether *path* contains anchored GRB files."""
        directory = Path(path)
        if not self._is_regular_nofollow(directory / self.GameBinary):
            return False
        return any(
            self._is_regular_nofollow(candidate)
            for candidate in directory.glob(self.ForgePattern)
        )

    def create_deployer(
        self,
        instance_path: Path,
        game_path: Path,
        profile_name: str = "Default",
    ):
        """Create the native Forge deployer used by Anvil's deploy lifecycle."""
        from anvil.core.grb_deployer import GRBDeployer

        return GRBDeployer(instance_path, game_path, profile_name)

    def forgeFiles(self) -> list[Path]:
        """Return no-follow regular GRB archives from the configured root."""
        if self._game_path is None or not self._game_path.is_dir():
            return []
        return sorted(
            candidate
            for candidate in self._game_path.glob(self.ForgePattern)
            if self._is_regular_nofollow(candidate)
        )

    def executables(self) -> list[dict[str, str]]:
        """Return the main GRB executable definition."""
        return [{"name": "Ghost Recon Breakpoint", "binary": self.GameBinary}]

    def get_default_categories(self) -> list[dict] | None:
        """Return categories suited to Breakpoint's Forge-based mod ecosystem."""
        return [
            {"id": 1, "name": "Weapons"},
            {"id": 2, "name": "Attachments"},
            {"id": 3, "name": "Characters & Gear"},
            {"id": 4, "name": "Vehicles"},
            {"id": 5, "name": "Gameplay"},
            {"id": 6, "name": "Graphics & UI"},
            {"id": 7, "name": "Audio"},
            {"id": 8, "name": "Utilities & Patches"},
        ]

    def get_conflict_ignores(self) -> list[str]:
        """Ignore documentation files that do not affect Forge content."""
        return [
            "**/readme*",
            "**/README*",
            "**/docs/**",
            "**/*.txt",
            "**/LICENSE*",
            "**/changelog*",
        ]
