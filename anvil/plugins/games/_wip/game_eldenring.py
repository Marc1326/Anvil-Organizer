"""Elden Ring game plugin for Anvil Organizer.

Elden Ring uses FromSoftware's proprietary engine. Modding requires
ModEngine2 as a mod loader. Mods are placed in Game/mod/ folder.

Features:
  - Store detection (Steam)
  - Proton prefix paths
  - ModEngine2 detection
  - regulation.bin handling

TODO:
  - ModEngine2 config parsing
  - .dcx file handling
  - Seamless Co-op detection
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class EldenRingGame(BaseGame):
    """Elden Ring support plugin."""

    Tested = False

    # -- Plugin-Metadaten ---------------------------------------------------

    Name = "Elden Ring Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # -- Spiel-Attribute ----------------------------------------------------

    GameName = "Elden Ring"
    GameShortName = "EldenRing"
    GameBinary = "eldenring.exe"
    GameDataPath = "Game"

    GameSteamId = 1245620
    GameGogId = 0  # Nicht auf GOG

    GameLauncher = "start_protected_game.exe"

    GameDocumentsDirectory = ""
    GameSavesDirectory = ""
    GameSaveExtension = "sl2"

    GameNexusId = 4017
    GameNexusName = "eldenring"

    # -- ModEngine2-spezifische Pfade ---------------------------------------

    _MOD_ENGINE_BINARY = "modengine2_launcher.exe"
    _MOD_ENGINE_CONFIG = "config_eldenring.toml"
    _MOD_DIR = "Game/mod"

    # -- Windows-Pfade (Proton-Prefix) --------------------------------------

    _WIN_SAVES = "drive_c/users/steamuser/AppData/Roaming/EldenRing"

    # -- Methoden -----------------------------------------------------------

    def gameDocumentsDirectory(self) -> Path | None:
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / "drive_c/users/steamuser/AppData/Roaming/EldenRing"
            if path.is_dir():
                return path
        return None

    def gameSavesDirectory(self) -> Path | None:
        # Elden Ring saves are in AppData/Roaming/EldenRing/<SteamID>/
        return self.gameDocumentsDirectory()

    def mod_path(self) -> Path | None:
        """Return the mod directory for ModEngine2."""
        if self._game_path is not None:
            return self._game_path / self._MOD_DIR
        return None

    def has_mod_engine(self) -> bool:
        """Check if ModEngine2 is installed."""
        if self._game_path is None:
            return False
        return (self._game_path / self._MOD_ENGINE_BINARY).exists()

    def get_framework_mods(self) -> list[FrameworkMod]:
        return [
            FrameworkMod(
                name="ModEngine2",
                pattern=["modengine2_launcher.exe", "config_eldenring.toml"],
                target="",
                description="ModEngine2 — Mod-Loader für FromSoftware-Spiele",
                detect_installed=["modengine2_launcher.exe"],
                required_by=["Die meisten Elden Ring Mods"],
                nexus_id=5998,
            ),
            FrameworkMod(
                name="Seamless Co-op",
                pattern=["elden_ring_seamless_coop.dll", "seamlesscoopsettings.ini"],
                target="Game/SeamlessCoop",
                description="Seamless Co-op — Nahtloser Koop-Modus",
                detect_installed=["elden_ring_seamless_coop.dll"],
                required_by=[],
                nexus_id=510,
            ),
        ]

    def get_conflict_ignores(self) -> list[str]:
        return [
            "**/readme*.txt",
            "**/docs/**",
        ]

    def executables(self) -> list[dict[str, str]]:
        exes = []
        if self._game_path:
            # ModEngine2
            me2 = self._game_path / self._MOD_ENGINE_BINARY
            if me2.exists():
                exes.append({
                    "title": "Elden Ring (ModEngine2)",
                    "binary": str(me2),
                    "workingDirectory": str(self._game_path),
                })
            # Vanilla (EAC)
            vanilla = self._game_path / self.GameBinary
            if vanilla.exists():
                exes.append({
                    "title": "Elden Ring",
                    "binary": str(vanilla),
                    "workingDirectory": str(self._game_path),
                })
            # EAC Launcher
            launcher = self._game_path / self.GameLauncher
            if launcher.exists():
                exes.append({
                    "title": "Elden Ring (EAC)",
                    "binary": str(launcher),
                    "workingDirectory": str(self._game_path),
                })
        return exes
