"""Baldur's Gate 3 game plugin for Anvil Organizer.

Based on the MO2 basic_games plugin by daescha, adapted for
Linux with Proton prefix support.

Features implemented:
  - Store detection (Steam, GOG)
  - Proton prefix paths for documents, saves, modsettings, pak mods
  - Executable list (Vulkan, DX11, Larian Launcher)
  - BG3-specific path helpers for mod management

TODO (future):
  - pak-Scanner — .pak Dateien lesen, info.json extrahieren (UUID, Name, Dependencies)
  - modsettings.lsx Parser/Writer — Load-Order verwalten
  - Dependency-Resolver — Mods nach Dependencies sortieren
  - GustavX Filter — Basegame-Eintrag nicht als Mod anzeigen
  - Mod-Typen unterscheiden — pak-Mods vs Data-Mods vs Script Extender
  - Forced DLL loads (DWrite.dll for Script Extender)
  - Post-update cache cleanup
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame


class BaldursGate3Game(BaseGame):
    """Baldur's Gate 3 support plugin."""

    # ── Plugin-Metadaten ───────────────────────────────────────────────

    Name = "Baldur's Gate 3 Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # ── Spiel-Attribute ────────────────────────────────────────────────

    GameName = "Baldur's Gate 3"
    GameShortName = "baldursgate3"
    GameBinary = "bin/bg3.exe"
    GameDataPath = ""  # Mods go to various locations depending on type

    GameSteamId = 1086940
    GameGogId = 1456460669

    GameLauncher = "Launcher/LariLauncher.exe"

    GameDocumentsDirectory = ""  # resolved dynamically via gameDocumentsDirectory()
    GameSavesDirectory = ""     # resolved dynamically via gameSavesDirectory()
    GameSaveExtension = "lsv"

    GameNexusId = 3474
    GameNexusName = "baldursgate3"

    GameSupportURL = (
        "https://github.com/ModOrganizer2/modorganizer-basic_games/wiki/"
        "Game:-Baldur's-Gate-3"
    )

    # ── Windows-Pfade (innerhalb Proton-Prefix) ────────────────────────

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/AppData/Local"
        "/Larian Studios/Baldur's Gate 3"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/AppData/Local"
        "/Larian Studios/Baldur's Gate 3"
        "/PlayerProfiles/Public/Savegames/Story"
    )
    _WIN_MODSETTINGS = (
        "drive_c/users/steamuser/AppData/Local"
        "/Larian Studios/Baldur's Gate 3"
        "/PlayerProfiles/Public/modsettings.lsx"
    )
    _WIN_PAK_MODS = (
        "drive_c/users/steamuser/AppData/Local"
        "/Larian Studios/Baldur's Gate 3/Mods"
    )

    # ── DX11-Binary ────────────────────────────────────────────────────

    _DX11_BINARY = "bin/bg3_dx11.exe"

    # ── Überschriebene Methoden ────────────────────────────────────────

    def gameDocumentsDirectory(self) -> Path | None:
        """Return the game's documents directory.

        For Steam (Proton): derived from the Proton prefix.
        For GOG: may be in a Wine prefix managed by Heroic/Lutris.
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

    # ── BG3-spezifische Pfade (Grundlage für Teil 2) ──────────────────

    def modsettings_path(self) -> Path | None:
        """Return the path to modsettings.lsx.

        This file controls the mod load order in BG3.  Located at
        ``<prefix>/.../PlayerProfiles/Public/modsettings.lsx``.

        Returns:
            Absolute path to modsettings.lsx, or None if the
            Proton prefix is not available.
        """
        # TODO: modsettings.lsx Parser/Writer — Load-Order verwalten
        prefix = self.protonPrefix()
        if prefix is not None:
            return prefix / self._WIN_MODSETTINGS
        return None

    def pak_mods_path(self) -> Path | None:
        """Return the directory where .pak mod files are stored.

        BG3 pak mods go into the ``Mods/`` folder inside the game's
        documents directory in the Proton prefix.

        Returns:
            Absolute path to the Mods directory, or None.
        """
        # TODO: pak-Scanner — .pak Dateien lesen, info.json extrahieren (UUID, Name, Dependencies)
        prefix = self.protonPrefix()
        if prefix is not None:
            return prefix / self._WIN_PAK_MODS
        return None

    def data_mods_path(self) -> Path | None:
        """Return the Data directory in the game root for data mods.

        Some BG3 mods install directly into ``<game>/Data/``.

        Returns:
            Absolute path to the Data directory, or None if game
            path is not set.
        """
        # TODO: Mod-Typen unterscheiden — pak-Mods vs Data-Mods vs Script Extender
        if self._game_path is not None:
            return self._game_path / "Data"
        return None

    def executables(self) -> list[dict[str, str]]:
        """Return executable definitions for Baldur's Gate 3.

        Includes the Vulkan renderer (default), DX11 renderer
        (if available), and the Larian Launcher.
        """
        result: list[dict[str, str]] = [
            {"name": "Baldur's Gate 3 (Vulkan)", "binary": self.GameBinary},
        ]

        # Add DX11 variant if available
        if self._game_path is not None:
            dx11 = self._game_path / self._DX11_BINARY
            if dx11.exists() or (self._game_path / "bin" / "bg3_dx11").exists():
                result.append(
                    {"name": "Baldur's Gate 3 (DX11)", "binary": self._DX11_BINARY}
                )

        result.append(
            {"name": "Larian Launcher", "binary": self.GameLauncher}
        )

        return result

    def iniFiles(self) -> list[str]:
        """Return config files managed by Baldur's Gate 3."""
        return []
