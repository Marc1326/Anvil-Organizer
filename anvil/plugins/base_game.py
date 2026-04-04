"""Base class for Anvil Organizer game plugins.

Every game plugin inherits from BaseGame and sets class-level attributes
to describe the game. The store-detection logic in detectGame() works
automatically as long as the plugin provides at least one store ID.

Adapted for Linux (no Windows registry, Proton prefix support,
.exe-agnostic binary lookup).
"""

from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path
from typing import Any

from anvil.plugins.framework_mod import FrameworkMod


def _as_list(value: Any) -> list:
    """Normalize a scalar or list value into a list.

    Falsy scalars (0, "", None) become an empty list.
    """
    if isinstance(value, list):
        return value
    if value:
        return [value]
    return []


class BaseGame:
    """Base class that every game plugin must inherit from.

    Subclasses override class-level attributes to describe a game.
    The default method implementations should work for most games;
    override individual methods for game-specific behaviour.
    """

    # ── Pflicht-Attribute (Subklasse MUSS diese setzen) ──────────────

    Name: str = ""
    """Plugin display name, e.g. 'Cyberpunk 2077 Support Plugin'."""

    Author: str = ""
    """Plugin author."""

    Version: str = ""
    """Plugin version string."""

    GameName: str = ""
    """Human-readable game name, e.g. 'Cyberpunk 2077'."""

    GameShortName: str = ""
    """Unique short identifier, e.g. 'cyberpunk2077'."""

    GameBinary: str = ""
    """Main executable relative to the game directory, e.g. 'bin/x64/Cyberpunk2077.exe'."""

    GameDataPath: str = ""
    """Directory for mods relative to the game directory.  Empty string means game root."""

    # ── Optional-Attribute ────────────────────────────────────────────

    GameSteamId: int | list[int] = 0
    """One or more Steam App-IDs.  Use a list for games with multiple editions."""

    GameGogId: int | list[int] = 0
    """One or more GOG product IDs."""

    GameEpicId: str | list[str] = ""
    """One or more Epic/Legendary app name identifiers."""

    GameLauncher: str = ""
    """Alternative launcher binary relative to the game directory."""

    GameDocumentsDirectory: str = ""
    """Path to the game's documents folder.  Supports ~ for home."""

    GameSavesDirectory: str = ""
    """Path to the save-game folder.  Falls back to GameDocumentsDirectory."""

    GameSaveExtension: str = "save"
    """File extension for save-game files (without dot)."""

    GameNexusId: int = 0
    """Nexus Mods game ID."""

    GameNexusName: str = ""
    """Nexus Mods URL slug.  Falls back to GameShortName."""

    GameSupportURL: str = ""
    """Wiki or support URL for modding instructions."""

    GameLaunchArgs: list[str] = []
    """Extra arguments passed to the game binary on launch (e.g. ['--launcher-skip'])."""

    GameDirectInstallMods: list[str] = []
    """Mod name patterns for framework mods that must be copied (not symlinked) into the game directory.

    Matching is case-insensitive and uses 'contains' logic.
    These mods are NOT removed during purge.
    """

    GameLMLPath: str = ""
    """If set, mods containing install.xml are deployed as directory
    symlinks into this path (e.g. 'lml' for RDR2).  Empty = disabled."""

    GameRedmodPath: str = ""
    """If set, mods containing info.json (REDmod) are deployed as directory
    symlinks into this path (e.g. 'mods' for Cyberpunk 2077).  Empty = disabled."""

    NeedsRedmodDeploy: bool = False
    """If True, ``redMod.exe deploy`` is run before game launch to compile
    REDmod mods.  Only relevant for Cyberpunk 2077."""

    ProtonShimFiles: list[str] = []
    """DLL filenames shipped in anvil/data/shims/<GameShortName>/ that are
    copied into the game root during deploy and removed during purge.
    Only deployed when the corresponding framework is installed."""

    GameCopyDeployPaths: list[str] = []
    """Relative paths (from game root) where files must be deployed as
    copies instead of symlinks.  Used when a tool (e.g. CET's Lua VM)
    cannot follow symlinks through Wine/Proton drive mappings.
    Files deployed this way use manifest type ``shim_copy`` and are
    removed during purge."""

    GameProtonDllOverrides: dict[str, str] = {}
    """Wine DLL overrides written to the Proton prefix user.reg during deploy.

    Keys are DLL names (without .dll), values are override modes
    (e.g. 'native,builtin'). Written under
    ``[Software\\\\Wine\\\\AppDefaults\\\\<GameBinary>\\\\DllOverrides]``
    and removed during purge.

    Example: ``{"winmm": "native,builtin", "version": "native,builtin"}``
    """

    ScriptExtenderDir: str = ""
    """Name of the Script Extender subdirectory inside Data/ (e.g. 'F4SE',
    'SFSE').  Used by the mod installer to fix archives that ship a bare
    ``Plugins/`` folder instead of ``<SE>/Plugins/``."""

    PRIMARY_PLUGINS: list[str] = []
    """Primary/DLC plugin files (.esm) that are always active.
    Only relevant for Bethesda Creation Engine games."""

    # ── BA2-Packing (Bethesda-Spiele unter Proton) ─────────────────────

    NeedsBa2Packing: bool = False
    """If True, loose mod files are packed into BA2 archives during deploy."""

    Ba2Format: str = ""
    """BSArch format flag for general assets ('fo4', 'sse')."""

    Ba2TextureFormat: str = ""
    """BSArch format flag for textures ('fo4dds', 'sse')."""

    Ba2IniSection: str = ""
    """INI section for archive registration ('Archive')."""

    Ba2IniKey: str = ""
    """INI key for archive list ('sResourceArchive2List')."""

    Ba2IniFile: str = ""
    """Custom INI filename ('Fallout4Custom.ini')."""

    # ── Proton-Pfade (fuer automatische Aufloesung) ──────────────────

    _WIN_DOCUMENTS: str = ""
    """Windows-Pfad relativ zum Proton-Prefix fuer das Documents-Verzeichnis.

    Beispiel: 'drive_c/users/steamuser/Documents/My Games/Skyrim Special Edition'
    Wenn gesetzt und die Methode gameDocumentsDirectory() NICHT ueberschrieben wird,
    wird der Pfad automatisch aufgeloest.
    """

    _WIN_SAVES: str = ""
    """Windows-Pfad relativ zum Proton-Prefix fuer das Saves-Verzeichnis.

    Beispiel: 'drive_c/users/steamuser/Documents/My Games/Skyrim Special Edition/Saves'
    Wenn gesetzt und die Methode gameSavesDirectory() NICHT ueberschrieben wird,
    wird der Pfad automatisch aufgeloest.
    """

    # ── Beta-Markierung ───────────────────────────────────────────────

    Tested: bool = True
    """Ob das Plugin vollstaendig getestet ist.

    WIP-Plugins setzen dies auf False. Die UI zeigt dann '[Beta]' im Namen.
    """

    # ── Interner State ────────────────────────────────────────────────

    def __init__(self) -> None:
        self._game_path: Path | None = None
        self._detected_store: str | None = None

    # ── Store-Erkennung ───────────────────────────────────────────────

    def detectGame(
        self,
        steam_games: dict[str, Path],
        gog_games: dict[str, Path],
        epic_games: dict[str, Path],
    ) -> bool:
        """Try to find this game in the provided store dictionaries.

        Each dictionary maps a store ID (as string) to an install path.
        Iterates Steam -> GOG -> Epic and stops at the first match.
        Sets ``_game_path`` and ``_detected_store`` on success.

        Returns:
            True if the game was found in any store.
        """
        for steam_id in _as_list(self.GameSteamId):
            key = str(steam_id)
            if key in steam_games:
                self.setGamePath(steam_games[key], store="steam")
                return True

        for gog_id in _as_list(self.GameGogId):
            key = str(gog_id)
            if key in gog_games:
                self.setGamePath(gog_games[key], store="gog")
                return True

        for epic_id in _as_list(self.GameEpicId):
            key = str(epic_id)
            if key in epic_games:
                self.setGamePath(epic_games[key], store="epic")
                return True

        return False

    def setGamePath(self, path: Path | str, store: str | None = None) -> None:
        """Manually set the game installation path.

        Args:
            path:  Absolute path to the game directory.
            store: Which store this path came from ('steam', 'gog', 'epic')
                   or None for manual selection.
        """
        self._game_path = Path(path)
        self._detected_store = store

    def looksValid(self, path: Path | str) -> bool:
        """Check whether *path* looks like a valid installation of this game.

        Tests for the presence of ``GameBinary``.  On Linux the binary may
        or may not have a .exe extension (native vs. Proton), so both
        variants are checked.

        Args:
            path: Directory to validate.

        Returns:
            True if the game binary was found.
        """
        directory = Path(path)
        binary = Path(self.GameBinary)

        if (directory / binary).exists():
            return True

        # Try without .exe suffix (native Linux build)
        if binary.suffix.lower() == ".exe":
            if (directory / binary.with_suffix("")).exists():
                return True

        return False

    # ── Getter ────────────────────────────────────────────────────────

    def gameDirectory(self) -> Path | None:
        """Return the game installation path, or None if not detected."""
        return self._game_path

    def isInstalled(self) -> bool:
        """Return True if the game has been detected and the path is set."""
        return self._game_path is not None

    def detectedStore(self) -> str | None:
        """Return which store the game was found in ('steam', 'gog', 'epic', or None)."""
        return self._detected_store

    def protonPrefix(self) -> Path | None:
        """Return the Proton prefix path for this game, or None."""
        if self._detected_store != "steam":
            return None

        from anvil.stores.steam_utils import find_steam_path
        steam_root = find_steam_path()
        if steam_root is None:
            return None

        # Alle Steam Library Folders sammeln (inkl. externe Platten)
        libraries = [steam_root]
        vdf = steam_root / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            try:
                import re
                text = vdf.read_text(encoding="utf-8")
                for match in re.finditer(r'"path"\s+"([^"]+)"', text):
                    lib = Path(match.group(1))
                    if lib.is_dir() and lib not in libraries:
                        libraries.append(lib)
            except OSError:
                pass

        # In allen Libraries nach Compatdata suchen
        for lib in libraries:
            for steam_id in _as_list(self.GameSteamId):
                prefix = lib / "steamapps" / "compatdata" / str(steam_id) / "pfx"
                if prefix.is_dir():
                    return prefix

        return None

    def findProtonRun(self) -> tuple[Path, Path, Path] | None:
        """Find the Proton runner for this Steam game.

        Locates the ``proton`` script and compat-data directory needed
        to launch arbitrary .exe files via ``proton run <exe>``.

        Returns:
            Tuple of (proton_script, compat_data_dir, steam_root) or
            None if any component is missing.  *proton_script* is the
            absolute path to the ``proton`` Python script,
            *compat_data_dir* is the game's compatdata directory
            (containing ``pfx/``), and *steam_root* is the Steam
            installation root.
        """
        if self._detected_store != "steam":
            return None

        from anvil.stores.steam_utils import find_steam_path
        steam_root = find_steam_path()
        if steam_root is None:
            return None

        # Collect all Steam library folders (including external drives)
        libraries = [steam_root]
        vdf = steam_root / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            try:
                import re as _re
                text = vdf.read_text(encoding="utf-8")
                for match in _re.finditer(r'"path"\s+"([^"]+)"', text):
                    lib = Path(match.group(1))
                    if lib.is_dir() and lib not in libraries:
                        libraries.append(lib)
            except OSError:
                pass

        # Find the compat-data directory for this game
        compat_data: Path | None = None
        for lib in libraries:
            for steam_id in _as_list(self.GameSteamId):
                candidate = lib / "steamapps" / "compatdata" / str(steam_id)
                if candidate.is_dir():
                    compat_data = candidate
                    break
            if compat_data is not None:
                break

        if compat_data is None:
            return None

        # Read config_info to find the Proton installation path.
        # Line 1 = version string, line 2 = path to fonts dir inside Proton.
        # From the fonts path we can derive the Proton root.
        config_info = compat_data / "config_info"
        proton_script: Path | None = None
        if config_info.is_file():
            try:
                lines = config_info.read_text(encoding="utf-8").splitlines()
                if len(lines) >= 2:
                    # Line 2 is e.g. /path/to/Proton - Experimental/files/share/fonts/
                    fonts_path = Path(lines[1])
                    # Walk up to the Proton root (contains the "proton" script)
                    candidate = fonts_path
                    for _ in range(6):  # max depth to search upward
                        candidate = candidate.parent
                        if (candidate / "proton").is_file():
                            proton_script = candidate / "proton"
                            break
            except OSError:
                pass

        # Fallback: search for Proton in all libraries by newest version
        if proton_script is None:
            for lib in libraries:
                common = lib / "steamapps" / "common"
                if not common.is_dir():
                    continue
                proton_dirs = sorted(
                    [d for d in common.iterdir()
                     if d.name.startswith("Proton") and (d / "proton").is_file()],
                    key=lambda d: d.name,
                    reverse=True,
                )
                if proton_dirs:
                    proton_script = proton_dirs[0] / "proton"
                    break

        if proton_script is None:
            return None

        return proton_script, compat_data, steam_root

    def icon(self) -> str | None:
        """Return path to a game icon, or None.

        Subclasses can override this to provide a custom icon.
        """
        return None

    # ── Proton-Pfad-Aufloesung (Default-Implementierungen) ───────────

    def gameDocumentsDirectory(self) -> Path | None:
        """Return the game's documents directory, or None.

        Default: Wenn ``_WIN_DOCUMENTS`` gesetzt ist, wird der Pfad
        automatisch ueber den Proton-Prefix aufgeloest.
        Subklassen koennen diese Methode ueberschreiben — der Override
        gewinnt via Python MRO.
        """
        if not self._WIN_DOCUMENTS:
            return None
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_DOCUMENTS
            if path.is_dir():
                return path
        return None

    def gameSavesDirectory(self) -> Path | None:
        """Return the save game directory, or None.

        Default: Wenn ``_WIN_SAVES`` gesetzt ist, wird der Pfad
        automatisch ueber den Proton-Prefix aufgeloest.
        Subklassen koennen diese Methode ueberschreiben — der Override
        gewinnt via Python MRO.
        """
        if not self._WIN_SAVES:
            return None
        prefix = self.protonPrefix()
        if prefix is not None:
            path = prefix / self._WIN_SAVES
            if path.is_dir():
                return path
        return None

    # ── Plugin-Liste (Bethesda) ──────────────────────────────────────

    def has_plugins_txt(self) -> bool:
        """Return True if this game uses a plugins.txt load order file."""
        return bool(self.PRIMARY_PLUGINS)

    def plugins_txt_path(self) -> Path | None:
        """Return path to plugins.txt in the Proton prefix, or None."""
        return None

    def ba2_ini_path(self) -> Path | None:
        """Return absolute path to the BA2 registration INI file."""
        if not self.NeedsBa2Packing or not self.Ba2IniFile:
            return None
        get_docs = getattr(self, "gameDocumentsDirectory", None)
        if get_docs is not None:
            docs = get_docs()
            if docs is not None:
                return docs / self.Ba2IniFile
        return None

    # ── Framework-Mod-Erkennung ──────────────────────────────────────

    def get_framework_mods(self) -> list[FrameworkMod]:
        """Return the list of known framework mods for this game.

        Subclasses override this to declare their framework mods.
        Default: empty list.
        """
        return []

    def all_framework_mods(self) -> list[FrameworkMod]:
        """Kombiniert Python- und JSON-Framework-Definitionen.

        Dies ist die Methode die der Core aufrufen soll.
        Python-Defs haben Vorrang bei Namenskonflikten.
        """
        python_fws = self.get_framework_mods()
        json_fws = self._load_json_frameworks()

        # Merge: Python gewinnt bei gleichem Namen
        known_names = {fw.name.lower() for fw in python_fws}
        for jfw in json_fws:
            if jfw.name.lower() not in known_names:
                python_fws.append(jfw)
                known_names.add(jfw.name.lower())

        return python_fws

    def _load_json_frameworks(self) -> list[FrameworkMod]:
        """Laedt FrameworkMod-Eintraege aus JSON-Dateien."""
        results: list[FrameworkMod] = []
        short = self.GameShortName.lower()
        json_name = f"game_{short}.json"

        for directory in self._framework_json_dirs():
            json_path = directory / json_name
            if not json_path.is_file():
                continue
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                for entry in data.get("frameworks", []):
                    results.append(FrameworkMod(
                        name=entry["name"],
                        pattern=entry.get("pattern", []),
                        target=entry.get("target", ""),
                        description=entry.get("description", ""),
                        detect_installed=entry.get("detect_installed", []),
                        required_by=entry.get("required_by", []),
                        nexus_id=int(entry.get("nexus_id", 0)),
                    ))
            except Exception as exc:
                print(
                    f"plugin: failed to load {json_path}: {exc}",
                    file=sys.stderr,
                )
        return results

    def _framework_json_dirs(self) -> list[Path]:
        """Verzeichnisse in denen nach JSON-Framework-Dateien gesucht wird."""
        from anvil.core.resource_path import get_anvil_base
        return [
            get_anvil_base() / "plugins" / "games",
            Path.home() / ".anvil-organizer" / "plugins" / "games",
        ]

    def is_framework_mod(self, archive_contents: list[str]) -> FrameworkMod | None:
        """Check if an archive contains a known framework mod.

        Compares the file paths in *archive_contents* against the
        patterns declared by ``all_framework_mods()``.  Returns the
        first matching FrameworkMod, or None.

        Args:
            archive_contents: List of file paths inside the archive
                              (e.g. from zipfile.namelist()).
        """
        lower_contents = [f.lower().replace("\\", "/") for f in archive_contents]
        for fw in self.all_framework_mods():
            for pattern in fw.pattern:
                pat = pattern.lower().replace("\\", "/")
                if '*' in pat or '?' in pat:
                    if any(
                        fnmatch.fnmatch(entry, pat)
                        or fnmatch.fnmatch(entry.split("/")[-1], pat)
                        for entry in lower_contents
                    ):
                        return fw
                elif any(pat in entry for entry in lower_contents):
                    return fw
        return None

    # ── Heuristik: Unbekannte Frameworks erkennen ──────────────────────

    # Dateitypen die auf Framework hindeuten
    _FW_EXTENSIONS = {".dll", ".exe", ".so", ".asi"}
    # Dateitypen die auf normale Mods hindeuten
    _MOD_EXTENSIONS = {
        ".esp", ".esm", ".esl", ".pak", ".archive", ".dds",
        ".nif", ".mesh", ".gr2", ".bsa", ".ba2", ".pex",
    }
    # Keywords in Dateinamen die auf Framework hindeuten
    _FW_KEYWORDS = {
        "loader", "extender", "hook", "injector", "bridge",
        "patcher", "proxy", "launcher", "shim",
    }
    # Config-Dateitypen neben DLLs
    _CONFIG_EXTENSIONS = {".ini", ".toml", ".cfg", ".xml", ".json"}

    def detect_possible_framework(
        self, archive_contents: list[str]
    ) -> dict | None:
        """Score-based heuristic to detect if an archive might be a framework.

        Returns a dict with score, reasons, and detected files if the score
        reaches the threshold (60), or None.
        """
        lower_contents = [f.lower().replace("\\", "/") for f in archive_contents]
        score = 0
        reasons: list[str] = []
        fw_files: list[str] = []

        # Criterion 1: Contains .dll/.exe/.so/.asi (+30)
        has_fw_ext = False
        for entry in lower_contents:
            ext = Path(entry).suffix
            if ext in self._FW_EXTENSIONS:
                has_fw_ext = True
                fw_files.append(entry)
        if has_fw_ext:
            score += 30
            reasons.append("executable_files")

        if not has_fw_ext:
            return None  # No point checking further without executables

        # Criterion 2: Keywords in filename (+25)
        for entry in lower_contents:
            name_lower = Path(entry).stem.lower()
            if any(kw in name_lower for kw in self._FW_KEYWORDS):
                score += 25
                reasons.append("keyword_match")
                break

        # Criterion 3: Config file next to DLL (+15)
        dll_dirs = {str(Path(e).parent) for e in lower_contents
                    if Path(e).suffix in self._FW_EXTENSIONS}
        for entry in lower_contents:
            if Path(entry).suffix in self._CONFIG_EXTENSIONS:
                if str(Path(entry).parent) in dll_dirs:
                    score += 15
                    reasons.append("config_beside_dll")
                    break

        # Criterion 4: No typical mod files (+20)
        has_mod_files = any(
            Path(e).suffix in self._MOD_EXTENSIONS for e in lower_contents
        )
        if not has_mod_files:
            score += 20
            reasons.append("no_mod_files")

        # Criterion 5: Files at root level, not in Data/ (+10)
        all_outside_data = all(
            not e.startswith("data/") for e in lower_contents
            if Path(e).suffix in self._FW_EXTENSIONS
        )
        if all_outside_data:
            score += 10
            reasons.append("outside_data_dir")

        if score >= 60:
            return {
                "score": score,
                "reasons": reasons,
                "detected_files": fw_files,
            }
        return None

    def save_framework_to_json(
        self,
        name: str,
        target: str,
        detect_installed: list[str],
        pattern: list[str] | None = None,
    ) -> None:
        """Save a new framework entry to the user's plugin JSON file."""
        short = self.GameShortName.lower()
        json_path = (
            Path.home() / ".anvil-organizer" / "plugins" / "games"
            / f"game_{short}.json"
        )
        json_path.parent.mkdir(parents=True, exist_ok=True)

        data: dict = {"frameworks": []}
        if json_path.is_file():
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                data = {"frameworks": []}

        # Check if framework with same name already exists
        existing = data.get("frameworks", [])
        for entry in existing:
            if entry.get("name", "").lower() == name.lower():
                return  # Already exists, don't duplicate

        new_entry: dict = {"name": name}
        if target:
            new_entry["target"] = target
        if detect_installed:
            new_entry["detect_installed"] = detect_installed
        if pattern:
            new_entry["pattern"] = pattern

        existing.append(new_entry)
        data["frameworks"] = existing

        json_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_installed_frameworks(self) -> list[tuple[FrameworkMod, bool]]:
        """Check which framework mods are installed in the game directory.

        Returns a list of (FrameworkMod, is_installed) tuples.
        A framework is considered installed if *any* of its
        ``detect_installed`` paths exist in the game directory.
        """
        print(f"[get_installed_frameworks] _game_path={self._game_path}", flush=True)
        result: list[tuple[FrameworkMod, bool]] = []
        for fw in self.all_framework_mods():
            installed = False
            if self._game_path is not None:
                for det_path in fw.detect_installed:
                    if '*' in det_path or '?' in det_path:
                        parent = (self._game_path / det_path).parent
                        pattern = Path(det_path).name
                        if parent.is_dir() and any(
                            fnmatch.fnmatch(f.name, pattern)
                            for f in parent.iterdir()
                        ):
                            installed = True
                            break
                    else:
                        if (self._game_path / det_path).exists():
                            installed = True
                            break
            print(f"[get_installed_frameworks]   fw={fw.name} installed={installed}", flush=True)
            result.append((fw, installed))
        return result

    # ── Konflikterkennung ───────────────────────────────────────────────

    def get_data_override_path_rewrites(self) -> dict[str, str]:
        """Return path prefix rewrites for data-override installation.

        Keys are prefixes found in archives, values are the correct
        target prefix relative to the game root.  Subclasses override
        this when some archive paths should not go into ``Data/``.

        Example: ``{"NativeMods/": "bin/NativeMods/"}`` maps
        ``NativeMods/BG3WASD.dll`` → ``bin/NativeMods/BG3WASD.dll``.
        """
        return {}

    def get_default_categories(self) -> list[dict] | None:
        """Return game-specific default categories, or None to use global defaults.

        Each entry: ``{"id": int, "name": str}``.
        Subclasses override this for game-specific category sets.
        """
        return None

    def get_proton_env_overrides(self) -> dict[str, str]:
        """Return extra environment variables for Proton launch when shim DLLs are deployed.

        Subclasses override this to provide game-specific overrides
        (e.g. WINEDLLOVERRIDES for F4SE shim).  Default: empty dict.
        """
        return {}

    def get_conflict_ignores(self) -> list[str]:
        """Return glob patterns for files to ignore during conflict detection.

        Subclasses override this to declare game-specific patterns for
        files that commonly share names across mods but are harmless
        (e.g. readme files, per-mod metadata).

        Patterns use fnmatch syntax with ``**`` for directory wildcards.
        Matching is case-insensitive.

        Default: empty list (nothing ignored).
        """
        return []

    # ── Override-Punkte (Subklassen können diese überschreiben) ───────

    def executables(self) -> list[dict[str, str]]:
        """Return a list of executable definitions for this game.

        Each entry is a dict with:
          - ``name``:   Display name
          - ``binary``: Path relative to the game directory

        The default implementation returns the main binary and,
        if set, the launcher.
        """
        result: list[dict[str, str]] = [
            {"name": self.GameName, "binary": self.GameBinary},
        ]
        if self.GameLauncher:
            result.append({"name": f"{self.GameName} Launcher", "binary": self.GameLauncher})
        return result

    def iniFiles(self) -> list[str]:
        """Return a list of INI/config filenames managed by this game.

        Default: empty list.
        """
        return []

    def listSaves(self, folder: Path) -> list[Path]:
        """Find save-game files inside *folder*.

        Default: globs for ``*.{GameSaveExtension}``.

        Args:
            folder: Directory to search for saves.

        Returns:
            Sorted list of save-game file paths.
        """
        if not folder.is_dir():
            return []
        ext = self.GameSaveExtension
        return sorted(folder.glob(f"*.{ext}"), key=lambda p: p.stat().st_mtime, reverse=True)

    # ── Repr ──────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        installed = self._game_path or "not found"
        return f"<{self.__class__.__name__} '{self.GameName}' [{installed}]>"
