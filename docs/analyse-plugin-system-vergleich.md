# Plugin-System Vergleich: MO2 vs Anvil Organizer

## Zusammenfassung

MO2 hat ein **offenes, erweiterbares Plugin-System** mit 9 verschiedenen Plugin-Typen, einem Hook/Event-System und einer API, die Plugins Zugriff auf alle Core-Funktionen gibt. Jeder User mit etwas Python-Erfahrung kann ein Plugin schreiben und in den `plugins/`-Ordner legen.

Anvil hat ein **geschlossenes Einzweck-Plugin-System** — es gibt nur Game-Plugins. Die technische Basis (dynamischer Import via `importlib`, User-Plugin-Verzeichnis) ist zwar da, aber es fehlt alles, was ein echtes offenes Plugin-System ausmacht.

---

## 1. MO2: Warum kann dort jeder User ein Plugin schreiben?

### 9 Plugin-Typen

| Interface | Zweck | Beispiel |
|-----------|-------|----------|
| `IPlugin` | Basis fuer alle Plugins | - |
| `IPluginGame` | Spiel-Support | game_skyrim, game_fallout4 |
| `IPluginTool` | Tools im Tools-Menu | INI Bakery, Configurator |
| `IPluginInstaller` | Mod-Installation | FOMOD Installer, Wizard |
| `IPluginModPage` | Mod-Seiten-Integration | Nexus Mods |
| `IPluginPreview` | Datei-Vorschau | DDS Preview, Mesh Preview |
| `IPluginDiagnose` | Diagnose/Warnungen | (Addon-Interface) |
| `IPluginFileMapper` | Datei-Mapping | (Addon-Interface) |
| `IPluginProxy` | Meta-Plugin (laedt andere) | Python-Proxy |

### Das Geheimnis: IOrganizer (die Plugin-API)

Jedes Plugin bekommt bei `init()` ein `IOrganizer`-Objekt. Damit hat es Zugriff auf:

```python
# Pfade
organizer.modsPath()
organizer.downloadsPath()
organizer.profileName()

# Mod-Liste lesen/aendern
organizer.modList()
organizer.pluginList()

# Download-Manager
organizer.downloadManager()

# Persistente Einstellungen speichern
organizer.setPersistent("meinPlugin", "key", "value")
organizer.persistent("meinPlugin", "key")

# Events abonnieren
organizer.onAboutToRun(callback)       # Bevor ein Programm startet
organizer.onFinishedRun(callback)      # Nach Programm-Ende
organizer.onProfileChanged(callback)   # Profil gewechselt
organizer.onUIInitialized(callback)    # UI fertig geladen
organizer.onNextRefresh(callback)      # Naechster Mod-Refresh
```

### Minimales Python-Plugin in MO2

```python
import mobase

class MeinTool(mobase.IPluginTool):
    def init(self, organizer):
        self._organizer = organizer
        return True

    def name(self):
        return "Mein Tool"

    def author(self):
        return "Max Mustermann"

    def version(self):
        return mobase.Version(1, 0, 0)

    def description(self):
        return "Macht coole Sachen"

    def display(self):
        # Wird aufgerufen wenn User im Tools-Menu klickt
        mods = self._organizer.modList()
        # ... mach was mit den Mods ...
```

**Das ist alles.** Datei in `plugins/` legen, MO2 neu starten, fertig.

### Warum das funktioniert

1. **Klare Interfaces** — User muss nur 5-7 Methoden implementieren
2. **API-Zugriff** — Plugin kann alles lesen und vieles steuern
3. **Events/Hooks** — Plugin reagiert auf Aktionen im Core
4. **Python-Support** — Kein Kompilieren noetig, einfach `.py` Datei
5. **Persistente Settings** — Plugin kann Daten speichern
6. **UI-Integration** — Tools erscheinen automatisch im Menu

---

## 2. Anvil: Warum haben wir das nicht?

### Was Anvil hat

- **1 Plugin-Typ:** `BaseGame` (Game-Plugins)
- **Dynamischer Loader:** `plugin_loader.py` mit `importlib` — technisch solide
- **User-Plugin-Verzeichnis:** `~/.anvil-organizer/plugins/games/` existiert bereits
- **Lose Kopplung:** Plugins kennen nur `BaseGame` und `FrameworkMod`

### Was Anvil NICHT hat

| Feature | MO2 | Anvil | Auswirkung |
|---------|-----|-------|------------|
| **Plugin-API (IOrganizer)** | Ja | Nein | Plugins koennen Core nicht nutzen |
| **Hook/Event-System** | 5+ Events | Keines | Plugins koennen nicht reagieren |
| **Tool-Plugins** | IPluginTool | Nein | User kann keine Tools bauen |
| **Installer-Plugins** | IPluginInstaller | Nein | Nur ein Installer moeglich |
| **UI-Erweiterungen** | Ja (via Events) | Nein | Plugins haben kein UI |
| **Diagnose-Plugins** | IPluginDiagnose | Nein | Keine User-Warnungen |
| **Persistente Settings** | setPersistent() | Nein | Plugins koennen nichts speichern |
| **Plugin-Abhaengigkeiten** | IPluginRequirement | Nein | Keine Abhaengigkeitskette |
| **Plugin Enable/Disable** | Ja | Nein | Alle Plugins immer aktiv |
| **Plugin-Konfiguration UI** | Ja | Nein | Keine Einstellungen |

### Der Kern des Problems

Anvils Plugin-System wurde **nur fuer Game-Support gebaut**. Es beantwortet eine einzige Frage: "Wie fuege ich ein neues Spiel hinzu?" — aber nicht: "Wie erweitere ich Anvil?"

**Konkret fehlt:**

1. **Kein generisches `IPlugin` Interface** — nur `BaseGame`
2. **Kein `AnvilProxy`/`IOrganizer`** — Plugins haben null Zugriff auf Core-Funktionen (Mod-Liste, Profile, Downloads, Deployer)
3. **Kein Event-Bus** — Plugins koennen auf nichts reagieren (Mod installiert, Profil gewechselt, Spiel gestartet, Deploy ausgefuehrt)
4. **Kein Extension Point im UI** — es gibt keine Stelle wo Plugins Menu-Eintraege, Tabs oder Toolbar-Buttons hinzufuegen koennten

---

## 3. Kann man das nachbauen? — Ja.

Anvil hat sogar Vorteile gegenueber MO2:
- **Reines Python** — kein C++/DLL-Kompilieren noetig
- **PySide6/Qt** — selbes Widget-System wie MO2
- **importlib-Loader existiert bereits** — muss nur erweitert werden
- **Lose Kopplung** — Core ist nicht mit Plugins verflochten

### Architektur-Vorschlag

```
anvil/plugins/
    __init__.py
    base_plugin.py          NEU — Generisches Plugin-Interface
    base_game.py            Existiert (erbt von base_plugin)
    base_tool.py            NEU — Tool-Plugins
    base_installer.py       NEU — Installer-Plugins
    base_diagnose.py        NEU — Diagnose-Plugins
    plugin_loader.py        Erweitern (alle Typen laden)
    plugin_api.py           NEU — AnvilProxy (API fuer Plugins)
    plugin_events.py        NEU — Event-Bus
    framework_mod.py        Existiert
    games/                  Existiert
    tools/                  NEU
    installers/             NEU
```

### Phase 1: Generisches Plugin-Interface + API

```python
# base_plugin.py — NEU
class BasePlugin:
    """Basis fuer ALLE Plugin-Typen"""
    Name: str = ""
    Author: str = ""
    Version: str = "1.0.0"
    Description: str = ""

    def init(self, api: "AnvilAPI") -> bool:
        """Wird beim Laden aufgerufen. API gibt Zugriff auf Core."""
        self._api = api
        return True

    def name(self) -> str:
        return self.Name

    def enabled_by_default(self) -> bool:
        return True
```

```python
# plugin_api.py — NEU (das Herzstueck)
class AnvilAPI:
    """Gibt Plugins kontrollierten Zugriff auf Anvil-Funktionen"""

    def __init__(self, main_window):
        self._mw = main_window

    # --- Pfade ---
    def mods_path(self) -> Path:
        return self._mw.instance_manager.current_mods_path()

    def downloads_path(self) -> Path:
        return self._mw.instance_manager.current_downloads_path()

    def profile_name(self) -> str:
        return self._mw.instance_manager.current_profile()

    # --- Mod-Liste ---
    def mod_list(self) -> list[str]:
        return self._mw.mod_list_manager.get_mod_names()

    def is_mod_enabled(self, name: str) -> bool:
        return self._mw.mod_list_manager.is_enabled(name)

    def enable_mod(self, name: str, enabled: bool = True):
        self._mw.mod_list_manager.set_enabled(name, enabled)

    # --- Events abonnieren ---
    def on_game_started(self, callback):
        self._mw.game_started.connect(callback)

    def on_profile_changed(self, callback):
        self._mw.profile_changed.connect(callback)

    def on_mod_installed(self, callback):
        self._mw.mod_installed.connect(callback)

    def on_deploy_finished(self, callback):
        self._mw.deploy_finished.connect(callback)

    # --- Persistente Settings ---
    def get_setting(self, plugin_name: str, key: str, default=None):
        ...

    def set_setting(self, plugin_name: str, key: str, value):
        ...
```

### Phase 2: Tool-Plugins

```python
# base_tool.py — NEU
class BaseTool(BasePlugin):
    """Plugin das im Tools-Menu erscheint"""
    Icon: str = ""  # Icon-Pfad oder Theme-Icon-Name

    def display(self):
        """Wird aufgerufen wenn User im Menu klickt"""
        raise NotImplementedError
```

**Beispiel: Ein User schreibt ein Conflict-Report-Tool:**

```python
# ~/.anvil-organizer/plugins/tools/conflict_report.py
from anvil.plugins.base_tool import BaseTool

class ConflictReportTool(BaseTool):
    Name = "Konflikt-Bericht"
    Author = "Community User"
    Version = "1.0.0"
    Description = "Exportiert alle Mod-Konflikte als HTML"

    def display(self):
        mods = self._api.mod_list()
        conflicts = self._api.get_conflicts()
        # ... HTML generieren und speichern ...
```

### Phase 3: Diagnose-Plugins

```python
# base_diagnose.py — NEU
class BaseDiagnose(BasePlugin):
    """Plugin das Warnungen/Hinweise anzeigt"""

    def active_problems(self) -> list[dict]:
        """Return [{severity, short, long}, ...]"""
        return []
```

**Beispiel: Ein User schreibt einen Mod-Order-Checker:**

```python
# ~/.anvil-organizer/plugins/tools/load_order_check.py
from anvil.plugins.base_diagnose import BaseDiagnose

class LoadOrderChecker(BaseDiagnose):
    Name = "Load-Order Pruefung"
    Author = "Community User"
    Version = "1.0.0"

    def active_problems(self):
        problems = []
        mods = self._api.mod_list()
        # Pruefe ob bestimmte Mods in falscher Reihenfolge sind
        if "LOOT" in mods and mods.index("LOOT") > mods.index("USSEP"):
            problems.append({
                "severity": "warning",
                "short": "LOOT sollte vor USSEP stehen",
                "long": "Empfohlene Reihenfolge: LOOT -> USSEP"
            })
        return problems
```

### Phase 4: Event-Bus (fuer fortgeschrittene Plugins)

```python
# plugin_events.py — NEU
from PySide6.QtCore import QObject, Signal

class PluginEventBus(QObject):
    """Zentraler Event-Bus — Plugins koennen sich registrieren"""

    # Core-Events
    game_starting = Signal(str)          # executable path
    game_finished = Signal(str, int)     # executable, exit code
    profile_changed = Signal(str, str)   # old, new
    mod_installed = Signal(str)          # mod name
    mod_removed = Signal(str)            # mod name
    deploy_started = Signal()
    deploy_finished = Signal(bool)       # success
    mod_enabled = Signal(str, bool)      # mod name, enabled
    mod_order_changed = Signal()
```

---

## 4. Aufwand-Schaetzung

| Phase | Was | Umfang | Abhaengigkeiten |
|-------|-----|--------|-----------------|
| **Phase 1** | BasePlugin + AnvilAPI + Loader erweitern | ~300 Zeilen | Keine |
| **Phase 2** | BaseTool + Menu-Integration | ~150 Zeilen | Phase 1 |
| **Phase 3** | BaseDiagnose + Statusbar-Integration | ~100 Zeilen | Phase 1 |
| **Phase 4** | Event-Bus + Signal-Verdrahtung | ~200 Zeilen | Phase 1 |
| **Phase 5** | BaseGame von BasePlugin erben lassen | ~50 Zeilen (Refactor) | Phase 1 |
| **Phase 6** | Plugin-Settings UI | ~200 Zeilen | Phase 1 |
| **Phase 7** | Plugin Enable/Disable + Abhaengigkeiten | ~150 Zeilen | Phase 1 |
| **Phase 8** | Dokumentation + Beispiel-Plugins | ~500 Zeilen Docs | Phase 1-4 |

**Phase 1 + 2 sind der groesste Hebel** — damit koennen User sofort eigene Tools schreiben.

---

## 5. Fazit

### Warum MO2 das hat und Anvil nicht

MO2 wurde von Anfang an als **Plugin-Host** designed — der Core ist bewusst duenn, fast alles ist ein Plugin (sogar Game-Support, Installer, Preview). Anvil wurde als **monolithische App** gebaut, in der Game-Plugins nachtraeglich eingefuegt wurden.

### Was Anvil schon hat

- Dynamischer Plugin-Loader (importlib) — **funktioniert**
- User-Plugin-Verzeichnis — **existiert**
- BaseGame als Plugin-Interface — **stabil**
- Lose Kopplung zwischen Core und Plugins — **gut**

### Was fehlt (in Prioritaetsreihenfolge)

1. **AnvilAPI** — DAS fehlende Stueck. Ohne API koennen Plugins nichts.
2. **Generisches BasePlugin** — Basis fuer alle Plugin-Typen
3. **Tool-Plugin-Typ** — Der einfachste Weg fuer User, Anvil zu erweitern
4. **Event-Bus** — Damit Plugins auf Aktionen reagieren koennen

### Machbarkeit

**Hoch.** Die technische Basis ist da. Der Aufwand ist ueberschaubar (Phase 1+2 ca. 450 Zeilen). Anvils Python-Stack macht es sogar einfacher als MO2s C++/Python-Hybrid. Ein User muesste nur eine `.py` Datei schreiben und 3-5 Methoden implementieren — genau wie bei MO2, aber ohne den Umweg ueber einen Python-Proxy.
