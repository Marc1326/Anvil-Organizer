"""Cyberpunk 2077 game plugin for Anvil Organizer.

Adapted for Linux with Proton prefix support.

Features implemented:
  - Store detection (Steam, GOG, Epic)
  - Proton prefix paths for documents and saves
  - Executable list (game, REDmod, launcher)
  - INI file list

TODO (future):
  - REDmod deployment (redMod.exe deploy)
  - Archive load order management
  - CrashReporter handling (dummy mod)
  - Cache file mapping after game updates
  - Forced DLL loads (version.dll, winmm.dll)
  - Save game metadata parsing (playtime, level, character)
  - Mod data validation (CyberpunkModDataChecker)
  - RootBuilder conversion dialog
"""

from __future__ import annotations

from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.plugins.framework_mod import FrameworkMod


class Cyberpunk2077Game(BaseGame):
    """Cyberpunk 2077 support plugin."""

    # ── Plugin-Metadaten ───────────────────────────────────────────────

    Name = "Cyberpunk 2077 Support Plugin"
    Author = "Anvil Organizer Team"
    Version = "1.0.0"

    # ── Spiel-Attribute ────────────────────────────────────────────────

    GameName = "Cyberpunk 2077"
    GameShortName = "cyberpunk2077"
    GameBinary = "bin/x64/Cyberpunk2077.exe"
    GameDataPath = ""  # Mods go into the game root directory

    GameSteamId = 1091500
    GameGogId = 1423049311
    GameEpicId = "77f2b98e2cef40c8a7437518bf420e47"

    GameLauncher = "REDprelauncher.exe"
    GameLaunchArgs = ["--launcher-skip"]

    GameProtonDllOverrides = {
        "winmm": "native,builtin",      # RED4ext loader
        "version": "native,builtin",     # CET (Ultimate ASI Loader)
    }

    GameCopyDeployPaths = [
        "bin/x64/plugins/cyber_engine_tweaks",
        # RED4ext lädt seine Plugins über den Windows-DLL-Loader. Ein Symlink
        # auf einen Pfad außerhalb des Spielordners kommt dort nicht als
        # gültige DLL an — das Plugin wird mit "unsupported API version"
        # abgewiesen. Ruft eine Mod die fehlenden nativen Funktionen dann aus
        # ihren Skripten auf, bricht RED4ext den Spielstart ab.
        "red4ext/plugins",
    ]

    # Ohne diese Datei haengt das Spiel die Archive alphabetisch nach
    # Dateiname ein -- die Reihenfolge aus Anvil waere reine Anzeige.
    # Liegt sie im Ordner, laedt das Spiel genau in dieser Reihenfolge.
    GameArchiveLoadOrderFile = "archive/pc/mod/modlist.txt"

    # Ordner, an denen eine Mod ihre Zielstruktur schon selbst mitbringt.
    # Beginnt ihr Pfad damit, bleibt er unangetastet.
    GameDeployAnchors = [
        "archive", "bin", "engine", "mods", "r6", "red4ext", "tools",
    ]

    # Manche Pakete enthalten nur die nackte .archive, ohne Ordner drumherum.
    # Ohne Regel landet sie im Spielhauptverzeichnis, wo das Spiel sie nie
    # liest -- die Mod schien dann spurlos zu verschwinden.
    GameDeployRoutes: list[dict] = [
        {
            "dest": "archive/pc/mod",
            "suffixes": [".archive", ".xl", ".archive.xl"],
            "flatten": True,
        },
        # redscript, TweakXL, Tastenbelegungen und Skript-Einstellungen
        # wohnen unter r6. Viele Pakete bringen diesen Ordner aber nicht
        # mit und beginnen direkt mit scripts/ oder tweaks/ -- ohne die
        # Regel landet der Inhalt im Spielhauptverzeichnis und wird von
        # keinem Loader gelesen. Unterordner bleiben erhalten, die
        # Skripte referenzieren sich gegenseitig ueber ihren Pfad.
        {
            "dest": "r6",
            "first_folder": ["scripts", "tweaks", "input", "config"],
        },
    ]

    GameDirectInstallMods = [
        "TweakXL",
        "ArchiveXL",
        "Cyber Engine Tweaks",
        "CET 1.37.1",
        "Codeware",
        "RED4ext",
        "RedData",
        "RedFileSystem",
        "redscript",
        "Native Settings UI",
        "mod_settings",
    ]

    GameDocumentsDirectory = ""  # resolved dynamically via gameDocumentsDirectory()
    GameSavesDirectory = ""     # resolved dynamically via gameSavesDirectory()
    GameSaveExtension = "dat"

    GameNexusId = 3333
    GameNexusName = "cyberpunk2077"

    GameSupportURL = "https://github.com/Marc1326/anvil-wiki"

    # ── Windows-Pfade (innerhalb Proton-Prefix) ────────────────────────

    _WIN_DOCUMENTS = (
        "drive_c/users/steamuser/AppData/Local"
        "/CD Projekt Red/Cyberpunk 2077"
    )
    _WIN_SAVES = (
        "drive_c/users/steamuser/Saved Games"
        "/CD Projekt Red/Cyberpunk 2077"
    )

    # Reine Mod-Ordner. Keiner davon gehoert zur Auslieferung -- das Spiel
    # legt sie nicht an, sie entstehen erst durch Mods. Was dort ohne
    # Anvil auftaucht, wurde von Hand hineinkopiert, laedt bei jedem Start
    # und ueberschreibt notfalls verwaltete Mods.
    GameModDirs: list[str] = [
        "archive/pc/mod",
        "mods",
        "bin/x64/plugins/cyber_engine_tweaks/mods",
        "red4ext/plugins",
        "r6/scripts",
        "r6/tweaks",
    ]

    def get_preset_kinds(self) -> list:
        """Charakter-Presets, die dieses Spiel kennt.

        Eine ``.preset``-Datei von ACU ist eine Liste ``LocKey#<Zahl>:<Wert>``
        ohne Geschlechtsangabe. Die Schluessel unterscheiden sich aber: elf
        kommen nur bei weiblichen, achtzehn nur bei maennlichen Presets vor.
        Ermittelt aus den sechs mitgelieferten Presets von ACU 2.x, dort an
        allen sechs gegengeprueft und ohne Fehltreffer.

        Reicht das nicht, wird gefragt -- die Zeichen sind eine Abkuerzung,
        keine Garantie.
        """
        from anvil.core.character_presets import FEMALE, MALE, PresetKind

        return [
            PresetKind(
                name="ACU-Preset",
                short="ACU",
                suffix=".preset",
                target=(
                    "bin/x64/plugins/cyber_engine_tweaks/mods"
                    "/AppearanceChangeUnlocker/character-presets"
                ),
                variants=[FEMALE, MALE],
                markers={
                    FEMALE: [
                        "LocKey#14413106849035572218",
                        "LocKey#14444638123505366956",
                        "LocKey#16755396525998114880",
                        "LocKey#1741780623366758979",
                        "LocKey#1742638242436574334",
                        "LocKey#2149255562299693265",
                        "LocKey#4311284794113424988",
                        "LocKey#5901792339822971396",
                        "LocKey#6131936511989184869",
                        "LocKey#6273276747880532262",
                        "LocKey#9222375131461895478",
                    ],
                    MALE: [
                        "LocKey#11868211319013669770",
                        "LocKey#13707137814640364864",
                        "LocKey#13707143312198505919",
                        "LocKey#13707144411710134130",
                        "LocKey#14413099152454174741",
                        "LocKey#14413101351477431163",
                        "LocKey#16223900489692860646",
                        "LocKey#1741788319948156456",
                        "LocKey#1741791618483041089",
                        "LocKey#1742636043413317912",
                        "LocKey#2149256661811321476",
                        "LocKey#2149257761322949687",
                        "LocKey#5229311434501341836",
                        "LocKey#5939674011469594817",
                        "LocKey#6270481789322187575",
                        "LocKey#6272437820508396494",
                        "LocKey#7053978468823785611",
                        "LocKey#7487713073032863221",
                    ],
                },
            ),
        ]

    # ── REDmod ─────────────────────────────────────────────────────────

    GameRedmodPath: str = "mods"
    """REDmod mods are deployed as directory symlinks into game_root/mods/."""

    NeedsRedmodDeploy: bool = True
    """Enable automatic ``redMod.exe deploy`` before game launch."""

    _REDMOD_BINARY = "tools/redmod/bin/redMod.exe"

    # ── Überschriebene Methoden ────────────────────────────────────────

    def gameDocumentsDirectory(self) -> Path | None:
        """Return the game's documents directory.

        For Steam (Proton): derived from the Proton prefix.
        For GOG/Epic: may be in a Wine prefix managed by Heroic/Lutris.
        Returns None if no prefix is found.
        """
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_DOCUMENTS
            if path.is_dir():
                return path
        # Fallback: check game directory itself (native Linux, unlikely)
        if self._game_path is not None:
            path = self._game_path / "AppData" / "Local" / "CD Projekt Red" / "Cyberpunk 2077"
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
        """Return save-game folders (Cyberpunk stores saves as directories)."""
        if not folder.is_dir():
            return []
        return sorted(
            [d for d in folder.iterdir() if d.is_dir() and (d / "sav.dat").exists()],
            key=lambda p: p.stat().st_mtime, reverse=True,
        )

    def executables(self) -> list[dict[str, str]]:
        """Return executable definitions for Cyberpunk 2077.

        Includes the main game binary, the REDprelauncher, and
        REDmod if the tools directory exists.
        """
        result: list[dict[str, str]] = [
            {"name": "Cyberpunk 2077", "binary": self.GameBinary},
            {"name": "REDprelauncher", "binary": self.GameLauncher},
        ]

        # Add REDmod if available
        if self._game_path is not None:
            redmod = self._game_path / self._REDMOD_BINARY
            if redmod.exists():
                result.append({"name": "REDmod", "binary": self._REDMOD_BINARY})

        return result

    def get_framework_mods(self) -> list[FrameworkMod]:
        """Return known framework mods for Cyberpunk 2077."""
        return [
            FrameworkMod(
                name="Cyber Engine Tweaks",
                pattern=["bin/x64/version.dll", "bin/x64/plugins/cyber_engine_tweaks.asi"],
                target="",
                description="Scripting-Framework, In-Game-Konsole und Mod-Loader",
                detect_installed=["bin/x64/version.dll"],
                required_by=["CET-Mods", "Lua-Scripts"],
                nexus_id=107,
                essential=True,
            ),
            FrameworkMod(
                name="RED4ext",
                pattern=["red4ext/RED4ext.dll", "bin/x64/winmm.dll"],
                target="",
                description="Native Plugin-Loader fuer REDengine 4",
                detect_installed=["bin/x64/winmm.dll", "red4ext/RED4ext.dll"],
                required_by=["ArchiveXL", "TweakXL", "Codeware"],
                nexus_id=2380,
                essential=True,
            ),
            FrameworkMod(
                name="redscript",
                pattern=["engine/tools/scc.exe", "engine/config/base/scripts.ini"],
                target="",
                description="Script-Compiler fuer REDscript-Mods",
                detect_installed=["engine/tools/scc.exe"],
                required_by=["REDscript-Mods"],
                nexus_id=1511,
                essential=True,
            ),
            FrameworkMod(
                name="ArchiveXL",
                pattern=["red4ext/plugins/ArchiveXL/"],
                target="",
                description="Ermoeglicht Laden zusaetzlicher .archive-Dateien",
                detect_installed=["red4ext/plugins/ArchiveXL/ArchiveXL.dll"],
                required_by=["Custom-Items", "Custom-Appearances"],
                nexus_id=4198,
                essential=True,
            ),
            FrameworkMod(
                name="TweakXL",
                pattern=["red4ext/plugins/TweakXL/"],
                target="",
                description="Ermoeglicht Laden zusaetzlicher TweakDB-Eintraege",
                detect_installed=["red4ext/plugins/TweakXL/TweakXL.dll"],
                required_by=["Custom-Items", "Gameplay-Tweaks"],
                nexus_id=4197,
                essential=True,
            ),
            FrameworkMod(
                name="Codeware",
                pattern=["red4ext/plugins/Codeware/"],
                target="",
                description="Shared Library fuer RED4ext-Plugins",
                detect_installed=["red4ext/plugins/Codeware/Codeware.dll"],
                nexus_id=7780,
            ),
            FrameworkMod(
                name="RedFileSystem",
                pattern=["red4ext/plugins/RedFileSystem/"],
                target="",
                description="Dateisystem-Zugriff fuer RED4ext-Plugins",
                detect_installed=["red4ext/plugins/RedFileSystem/RedFileSystem.dll"],
                nexus_id=13378,
            ),
            FrameworkMod(
                name="RedData",
                pattern=["red4ext/plugins/RedData/"],
                target="",
                description="JSON-Parsing Library fuer RED4ext-Plugins",
                detect_installed=["red4ext/plugins/RedData/RedData.dll"],
                nexus_id=14139,
            ),
            FrameworkMod(
                name="Native Settings UI",
                pattern=["bin/x64/plugins/cyber_engine_tweaks/mods/nativeSettings/"],
                target="",
                description="UI-Framework fuer Mod-Einstellungen (CET)",
                detect_installed=["bin/x64/plugins/cyber_engine_tweaks/mods/nativeSettings/init.lua"],
                required_by=["Mods mit Einstellungs-Menues"],
                nexus_id=3518,
            ),
            FrameworkMod(
                name="Mod Settings",
                pattern=["red4ext/plugins/mod_settings/"],
                target="",
                description="Einstellungs-Framework fuer RED4ext-Mods",
                detect_installed=["red4ext/plugins/mod_settings/mod_settings.dll"],
                nexus_id=4885,
            ),
            FrameworkMod(
                name="JB - TPP MOD WIP third person",
                pattern=["bin/x64/plugins/cyber_engine_tweaks/mods/jb_third_person_mod/"],
                target="",
                description="Third-Person-Perspektive (CET-basiert)",
                detect_installed=["bin/x64/plugins/cyber_engine_tweaks/mods/jb_third_person_mod/init.lua"],
                nexus_id=669,
            ),
        ]

    def get_default_categories(self) -> list[dict] | None:
        """Return Cyberpunk 2077 specific default categories."""
        return [
            {"id": 1, "name": "Gameplay"},
            {"id": 2, "name": "Waffen"},
            {"id": 3, "name": "Kleidung & Rüstung"},
            {"id": 4, "name": "Fahrzeuge"},
            {"id": 5, "name": "Cyberware"},
            {"id": 6, "name": "Grafik & Visuals"},
            {"id": 7, "name": "UI"},
            {"id": 8, "name": "Audio"},
            {"id": 9, "name": "NPC & Companions"},
            {"id": 10, "name": "Umgebung"},
            {"id": 11, "name": "Frisuren & Gesicht"},
            {"id": 12, "name": "Körper"},
            {"id": 13, "name": "Foto-Modus"},
            {"id": 14, "name": "Bug Fixes"},
            {"id": 15, "name": "Utilities"},
            {"id": 16, "name": "Frameworks"},
            {"id": 17, "name": "Patches"},
        ]

    def get_conflict_ignores(self) -> list[str]:
        """Return patterns for harmless files in Cyberpunk 2077 mods."""
        return [
            "**/Item codes*.txt",   # CET spawn codes, each mod has own
            "**/readme*.txt",       # readme files
            "**/changelog*.txt",    # changelogs
            "**/*.md",              # markdown documentation
            "**/credits*.txt",      # credits files
        ]

    def iniFiles(self) -> list[str]:
        """Return config files managed by Cyberpunk 2077."""
        return ["UserSettings.json"]
