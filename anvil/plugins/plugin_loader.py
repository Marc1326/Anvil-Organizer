"""Dynamic game plugin loader for Anvil Organizer.

Scans built-in and user plugin directories for Python files that
define BaseGame subclasses, imports them dynamically, instantiates
each plugin, and runs store detection.

Built-in plugins:  ``anvil/plugins/games/*.py``
User plugins:      ``~/.anvil-organizer/plugins/games/*.py``

Typical usage::

    from anvil.plugins.plugin_loader import PluginLoader
    loader = PluginLoader()
    loader.load_plugins()
    for game in loader.installed_games():
        print(game.GameName, game.gameDirectory())
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

from anvil.plugins.base_game import BaseGame
from anvil.stores.store_manager import StoreManager

# ── Plugin directories ─────────────────────────────────────────────────

from anvil.core.resource_path import get_anvil_base

_BUILTIN_GAMES_DIR = get_anvil_base() / "plugins" / "games"
_USER_GAMES_DIR = Path.home() / ".anvil-organizer" / "plugins" / "games"

_USER_README = """\
# Eigene Spiel-Plugins fuer Anvil Organizer

Lege hier eigene Game-Plugin-Dateien ab (z.B. `game_meingame.py`).

## Schnellstart

1. Erstelle eine Python-Datei `game_SPIELNAME.py`
2. Importiere BaseGame und erbe davon
3. Starte Anvil Organizer neu — das Plugin wird automatisch geladen

## Minimales Plugin-Beispiel

```python
from anvil.plugins.base_game import BaseGame

class MeinGamePlugin(BaseGame):
    # -- Pflicht-Attribute --
    Name = "Mein Spiel Support Plugin"
    Author = "Dein Name"
    Version = "1.0.0"
    GameName = "Mein Spiel"
    GameShortName = "meinspiel"
    GameBinary = "bin/game.exe"
    GameDataPath = ""               # "" = Game Root, "Data" = Data-Ordner, "Mods" = Mods-Ordner
    GameSteamId = 123456            # Mindestens EINE Store-ID setzen!

    # -- Optional: Proton-Pfade (automatische Aufloesung) --
    _WIN_DOCUMENTS = "drive_c/users/steamuser/Documents/My Games/MeinSpiel"
    _WIN_SAVES = "drive_c/users/steamuser/Documents/My Games/MeinSpiel/Saves"
```

## Vollstaendige Attribut-Referenz

### Pflicht-Attribute

| Attribut        | Typ           | Beschreibung |
|-----------------|---------------|--------------|
| `Name`          | `str`         | Plugin-Anzeigename (z.B. "Skyrim SE Support Plugin") |
| `Author`        | `str`         | Autor des Plugins |
| `Version`       | `str`         | Versions-String (z.B. "1.0.0") |
| `GameName`      | `str`         | Spielname (z.B. "Skyrim Special Edition") |
| `GameShortName` | `str`         | Eindeutiger Kurzname (z.B. "SkyrimSE") — wird fuer Dateinamen verwendet |
| `GameBinary`    | `str`         | Pfad zur Spiel-EXE relativ zum Spielordner |
| `GameDataPath`  | `str`         | Mod-Verzeichnis relativ zum Spielordner ("" = Root) |

### Store-IDs (mindestens eine setzen!)

| Attribut       | Typ                | Wo finden? |
|----------------|--------------------|------------|
| `GameSteamId`  | `int` oder `list[int]` | https://store.steampowered.com/app/NUMMER |
| `GameGogId`    | `int` oder `list[int]` | https://www.gog.com/game/SPIELNAME → Seiten-Quelltext: "productId" |
| `GameEpicId`   | `str` oder `list[str]` | `legendary list-installed` oder Epic Store URL-Slug |

### Optionale Attribute

| Attribut               | Typ           | Default | Beschreibung |
|------------------------|---------------|---------|--------------|
| `GameLauncher`         | `str`         | `""`    | Alternativer Launcher relativ zum Spielordner |
| `GameDocumentsDirectory` | `str`       | `""`    | Dokument-Pfad (unterstuetzt ~) |
| `GameSavesDirectory`   | `str`         | `""`    | Savegame-Pfad (Fallback: GameDocumentsDirectory) |
| `GameSaveExtension`    | `str`         | `"save"` | Dateiendung fuer Savegames (ohne Punkt) |
| `GameNexusId`          | `int`         | `0`     | Nexus Mods Game-ID |
| `GameNexusName`        | `str`         | `""`    | Nexus Mods URL-Slug (Fallback: GameShortName) |
| `GameSupportURL`       | `str`         | `""`    | Link zu Wiki/Modding-Anleitung |
| `GameLaunchArgs`       | `list[str]`   | `[]`    | Extra Startargumente (z.B. `['--launcher-skip']`) |
| `GameDirectInstallMods` | `list[str]`  | `[]`    | Framework-Mods die direkt kopiert werden |
| `GameLMLPath`          | `str`         | `""`    | LML-Mod-Pfad (z.B. "lml" fuer RDR2) |
| `GameCopyDeployPaths`  | `list[str]`   | `[]`    | Pfade wo Kopien statt Symlinks noetig sind |

### Proton-Pfade (automatische Aufloesung)

| Attribut          | Typ   | Beschreibung |
|-------------------|-------|--------------|
| `_WIN_DOCUMENTS`  | `str` | Windows-Pfad relativ zum Proton-Prefix (z.B. "drive_c/users/steamuser/Documents/My Games/MeinSpiel") |
| `_WIN_SAVES`      | `str` | Windows-Pfad fuer Savegames relativ zum Proton-Prefix |

Wenn gesetzt, werden `gameDocumentsDirectory()` und `gameSavesDirectory()` automatisch aufgeloest.
Du kannst die Methoden auch manuell ueberschreiben — dein Override gewinnt immer.

### Bethesda-spezifisch (optional)

| Attribut           | Typ           | Beschreibung |
|--------------------|---------------|--------------|
| `PRIMARY_PLUGINS`  | `list[str]`   | Immer aktive Plugin-Dateien (.esm) |
| `NeedsBa2Packing`  | `bool`        | Loose Files in BA2-Archive packen |
| `Ba2Format`        | `str`         | BSArch-Format ("fo4", "sse") |
| `Ba2IniFile`       | `str`         | Custom-INI Dateiname |
| `ScriptExtenderDir`| `str`         | SE-Unterordner in Data/ ("F4SE", "SFSE") |

### Beta-Markierung

| Attribut  | Typ    | Default | Beschreibung |
|-----------|--------|---------|--------------|
| `Tested`  | `bool` | `True`  | Auf `False` setzen fuer ungetestete Plugins → zeigt "[Beta]" in der UI |

## Framework-Mods per JSON definieren

Statt Python-Code kannst du Frameworks auch per JSON-Datei definieren.
Dateiname: `game_<GameShortName>.json` (lowercase), in diesem Ordner.

```json
{
  "frameworks": [
    {
      "name": "Mein Framework",
      "pattern": ["framework.dll", "framework_*.dll"],
      "target": "",
      "description": "Was das Framework macht",
      "detect_installed": ["framework.dll"],
      "required_by": ["Framework-Mods"]
    }
  ]
}
```

JSON-Frameworks werden mit Python-Frameworks zusammengefuehrt.
Bei gleichem Namen gewinnt die Python-Definition.

## Tipps

- GameShortName muss EINDEUTIG sein — kein anderes Plugin darf denselben verwenden
- Teste mit `Tested = False` bis du sicher bist, dass alles funktioniert
- Lies die bestehenden Plugins als Vorlage: `anvil/plugins/games/`
- Wiki: https://github.com/Marc1326/Anvil-Organizer/wiki
"""


def ensure_user_plugin_dir() -> Path:
    """Create the user plugin directory and README if they don't exist.

    Returns:
        Path to ``~/.anvil-organizer/plugins/games/``.
    """
    _USER_GAMES_DIR.mkdir(parents=True, exist_ok=True)

    readme = _USER_GAMES_DIR / "README.md"
    if not readme.exists():
        readme.write_text(_USER_README, encoding="utf-8")

    return _USER_GAMES_DIR


class PluginLoader:
    """Loads game plugins and runs store detection.

    Call :meth:`load_plugins` once to scan directories, import
    plugin files, instantiate BaseGame subclasses, and detect
    installed games via the StoreManager.
    """

    def __init__(self) -> None:
        self._plugins: list[BaseGame] = []
        self._store_manager: StoreManager = StoreManager()
        self._loaded: bool = False

    # ── Loading ────────────────────────────────────────────────────────

    def load_plugins(self) -> None:
        """Scan plugin directories, load plugins, and detect games.

        1. Scans all stores via StoreManager
        2. Imports built-in plugins from ``anvil/plugins/games/``
        3. Imports user plugins from ``~/.anvil-organizer/plugins/games/``
        4. Calls ``detectGame()`` on each plugin

        Safe to call multiple times — clears previous results first.
        """
        self._plugins.clear()

        # Step 1: Scan stores
        self._store_manager.scan_all_stores()

        # Step 2+3: Load plugin files (inkl. _wip/ Unterverzeichnis)
        self._scan_directory(_BUILTIN_GAMES_DIR)
        self._scan_directory(_BUILTIN_GAMES_DIR / "_wip")
        ensure_user_plugin_dir()
        self._scan_directory(_USER_GAMES_DIR)

        # Step 4: Detect games — convert int keys to str for detectGame()
        steam_str = {str(k): v for k, v in self._store_manager.steam_games.items()}
        gog_str = {str(k): v for k, v in self._store_manager.gog_games.items()}
        epic_str = self._store_manager.epic_games  # already str keys

        for plugin in self._plugins:
            try:
                plugin.detectGame(steam_str, gog_str, epic_str)
            except Exception as exc:
                print(
                    f"plugin_loader: detectGame() failed for "
                    f"{plugin.GameName!r}: {exc}",
                    file=sys.stderr,
                )

        self._loaded = True

    def _scan_directory(self, directory: Path) -> None:
        """Import all plugin files from *directory*.

        Each ``.py`` file (except ``__init__.py``) is loaded via
        importlib.  All classes that inherit from BaseGame (but are
        not BaseGame itself) are instantiated and added to the
        plugin list.

        Errors during import or instantiation are logged and skipped.
        """
        if not directory.is_dir():
            return

        for py_file in sorted(directory.glob("*.py")):
            if py_file.name == "__init__.py":
                continue

            module_name = f"anvil_plugin_{py_file.stem}"

            try:
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec is None or spec.loader is None:
                    print(
                        f"plugin_loader: cannot create spec for {py_file}",
                        file=sys.stderr,
                    )
                    continue

                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

            except Exception as exc:
                print(
                    f"plugin_loader: failed to import {py_file.name}: {exc}",
                    file=sys.stderr,
                )
                continue

            # Find all BaseGame subclasses in this module
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if not issubclass(cls, BaseGame) or cls is BaseGame:
                    continue

                try:
                    instance = cls()
                    # Duplikat-Check: User-Plugin ersetzt Built-in
                    short = instance.GameShortName
                    replaced = False
                    for i, existing in enumerate(self._plugins):
                        if existing.GameShortName == short:
                            print(
                                f"plugin_loader: {name} ({py_file.name}) "
                                f"ersetzt {existing.__class__.__name__} "
                                f"(gleicher GameShortName: {short})",
                            )
                            self._plugins[i] = instance
                            replaced = True
                            break
                    if not replaced:
                        self._plugins.append(instance)
                except Exception as exc:
                    print(
                        f"plugin_loader: failed to instantiate {name}: {exc}",
                        file=sys.stderr,
                    )

    # ── Getters ────────────────────────────────────────────────────────

    def all_plugins(self) -> list[BaseGame]:
        """Return all loaded plugins (installed or not)."""
        return list(self._plugins)

    def installed_games(self) -> list[BaseGame]:
        """Return only plugins whose game was detected as installed."""
        return [p for p in self._plugins if p.isInstalled()]

    def get_game(self, short_name: str) -> BaseGame | None:
        """Find a plugin by its GameShortName.

        Args:
            short_name: The short name to search for (e.g. ``cyberpunk2077``).

        Returns:
            The matching plugin, or None if not found.
        """
        for plugin in self._plugins:
            if plugin.GameShortName == short_name:
                return plugin
        return None

    def plugin_count(self) -> int:
        """Return the total number of loaded plugins."""
        return len(self._plugins)

    def installed_count(self) -> int:
        """Return the number of detected/installed games."""
        return sum(1 for p in self._plugins if p.isInstalled())

    @property
    def store_manager(self) -> StoreManager:
        """Access the internal StoreManager (e.g. for Bottles data)."""
        return self._store_manager

    # ── Repr ───────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        if not self._loaded:
            return "<PluginLoader (not loaded)>"
        return (
            f"<PluginLoader plugins={self.plugin_count()} "
            f"installed={self.installed_count()}>"
        )
