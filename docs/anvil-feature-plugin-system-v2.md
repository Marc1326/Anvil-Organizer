# Feature-Spec: Plugin-System v2 — Offenes Plugin-System fuer Anvil

## Ziel

Jeder User mit etwas Ahnung soll ein Game-Plugin erstellen koennen — auch OHNE das Spiel installiert zu haben. Framework-Mod-Definitionen werden von Python-Code in einfache JSON-Dateien ausgelagert, sodass auch Nicht-Programmierer Frameworks ergaenzen koennen. Bestehende Spiele (Cyberpunk, Witcher 3, Fallout 4, Starfield, BG3, RDR2) duerfen NICHT kaputt gehen.

---

## Grundregeln

1. **Null Regression** — Alle 6 aktiven Game-Plugins funktionieren exakt wie bisher
2. **Additiv** — Neue Features sind optional, nichts wird entfernt oder ersetzt
3. **Abwaertskompatibel** — `get_framework_mods()` in Python funktioniert weiter
4. **Kein Flag-Day** — Bestehende Plugins werden NICHT umgeschrieben

---

## Phase 1: BaseGame automatisiert Proton-Pfade

### Problem

Jedes Plugin hat die gleiche Copy-Paste-Methode:

```python
def gameDocumentsDirectory(self) -> Path | None:
    prefix = self.protonPrefix()
    if prefix is not None:
        path = prefix / self._WIN_DOCUMENTS
        if path.is_dir():
            return path
    return None
```

Cyberpunk, Witcher 3, Skyrim SE, Fallout 4, Starfield — alle identisch.

### Loesung

`BaseGame` bekommt Default-Implementierungen die automatisch greifen wenn `_WIN_DOCUMENTS` / `_WIN_SAVES` gesetzt sind:

```python
# base_game.py — NEUE Default-Implementierungen

_WIN_DOCUMENTS: str = ""   # Neues Klassenattribut
_WIN_SAVES: str = ""       # Neues Klassenattribut

def gameDocumentsDirectory(self) -> Path | None:
    if not self._WIN_DOCUMENTS:
        return None
    prefix = self.protonPrefix()
    if prefix is not None:
        path = prefix / self._WIN_DOCUMENTS
        if path.is_dir():
            return path
    return None

def gameSavesDirectory(self) -> Path | None:
    if not self._WIN_SAVES:
        return None
    prefix = self.protonPrefix()
    if prefix is not None:
        path = prefix / self._WIN_SAVES
        if path.is_dir():
            return path
    return None
```

### Auswirkung auf bestehende Plugins

- Cyberpunk, Witcher 3 etc. ueberschreiben `gameDocumentsDirectory()` bereits → **Python MRO sorgt dafuer dass der Override weiter gewinnt**
- Plugins die `_WIN_DOCUMENTS` setzen aber die Methode NICHT ueberschreiben → bekommen die Funktionalitaet automatisch
- Plugins die weder Attribut noch Methode haben → `None` wie bisher

### Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `anvil/plugins/base_game.py` | Default-Implementierungen fuer `gameDocumentsDirectory()`, `gameSavesDirectory()` |

### Akzeptanz-Kriterien

- [ ] Bestehende Plugins mit eigenem Override: Verhalten identisch
- [ ] Neues Plugin mit nur `_WIN_DOCUMENTS` gesetzt: Pfad wird automatisch aufgeloest
- [ ] Neues Plugin ohne `_WIN_DOCUMENTS`: gibt `None` zurueck
- [ ] `./restart.sh` startet ohne Fehler

---

## Phase 2: Framework-Definitionen aus JSON

### Problem

Framework-Mods sind als Python-Code im Plugin hardcoded (z.B. Cyberpunk: 80 Zeilen FrameworkMod-Objekte). Ein Community-User der kein Python kann, kann keine Frameworks ergaenzen.

### Loesung

`BaseGame.get_framework_mods()` laedt zusaetzlich eine JSON-Datei. Die JSON ist optional und ergaenzend.

### JSON-Format

Dateiname: `game_<GameShortName>.json` (lowercase), liegt neben der `.py`-Datei.

```json
{
  "frameworks": [
    {
      "name": "Cyber Engine Tweaks",
      "pattern": ["bin/x64/version.dll", "bin/x64/plugins/cyber_engine_tweaks.asi"],
      "target": "",
      "description": "Scripting-Framework, In-Game-Konsole und Mod-Loader",
      "detect_installed": ["bin/x64/version.dll"],
      "required_by": ["CET-Mods", "Lua-Scripts"]
    }
  ]
}
```

Alle Felder entsprechen 1:1 den `FrameworkMod`-Dataclass-Feldern.

### Lade-Reihenfolge

```
1. Python: plugin.get_framework_mods()          → Liste A (bestehend)
2. JSON:   game_<shortname>.json laden           → Liste B (neu)
3. Merge:  A + B, bei Namenskonflikt gewinnt A   → Ergebnis
```

**Python hat IMMER Vorrang.** JSON ergaenzt nur was in Python nicht definiert ist.

### Wo JSON-Dateien liegen koennen

```
Built-in:  anvil/plugins/games/game_cyberpunk2077.json
User:      ~/.anvil-organizer/plugins/games/game_cyberpunk2077.json
```

Beide werden geladen und zusammengefuehrt (Built-in zuerst, User ergaenzt).

### Implementierung in BaseGame

```python
# base_game.py — get_framework_mods() erweitern

def get_framework_mods(self) -> list[FrameworkMod]:
    """Laedt Frameworks aus Python UND JSON.

    Subklassen ueberschreiben diese Methode fuer Python-Defs.
    JSON-Defs werden automatisch dazugeladen.
    """
    return []  # Subklassen ueberschreiben dies

def _load_json_frameworks(self) -> list[FrameworkMod]:
    """Laedt FrameworkMod-Eintraege aus JSON-Dateien."""
    results = []
    short = self.GameShortName.lower()
    json_name = f"game_{short}.json"

    for directory in self._framework_json_dirs():
        json_path = directory / json_name
        if not json_path.is_file():
            continue
        try:
            import json
            data = json.loads(json_path.read_text(encoding="utf-8"))
            for entry in data.get("frameworks", []):
                results.append(FrameworkMod(
                    name=entry["name"],
                    pattern=entry.get("pattern", []),
                    target=entry.get("target", ""),
                    description=entry.get("description", ""),
                    detect_installed=entry.get("detect_installed", []),
                    required_by=entry.get("required_by", []),
                ))
        except Exception as exc:
            print(f"plugin: failed to load {json_path}: {exc}", file=sys.stderr)
    return results

def _framework_json_dirs(self) -> list[Path]:
    """Verzeichnisse in denen nach JSON-Framework-Dateien gesucht wird."""
    from anvil.core.resource_path import get_anvil_base
    return [
        get_anvil_base() / "plugins" / "games",
        Path.home() / ".anvil-organizer" / "plugins" / "games",
    ]

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
```

### Core-Aufrufe umstellen

Alle Stellen die `get_framework_mods()` aufrufen muessen auf `all_framework_mods()` umgestellt werden:

| Datei | Zeilen | Alter Aufruf | Neuer Aufruf |
|-------|--------|-------------|-------------|
| `mainwindow.py` | 1430 | `get_framework_mods()` | `all_framework_mods()` |
| `mainwindow.py` | 4188, 4230 | `get_framework_mods()` | `all_framework_mods()` |
| `mainwindow.py` | 1486 | `is_framework_mod()` | bleibt (nutzt intern `all_framework_mods()`) |
| `mainwindow.py` | 4286 | `is_framework_mod()` | bleibt |
| `game_panel.py` | 679 | `get_installed_frameworks()` | bleibt |
| `bg3_mod_installer.py` | 472, 744 | `is_framework_mod()` / `get_installed_frameworks()` | bleibt |

`is_framework_mod()` und `get_installed_frameworks()` muessen intern `all_framework_mods()` statt `get_framework_mods()` aufrufen.

### Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `anvil/plugins/base_game.py` | `all_framework_mods()`, `_load_json_frameworks()`, `_framework_json_dirs()` hinzufuegen. `is_framework_mod()` und `get_installed_frameworks()` auf `all_framework_mods()` umstellen. |
| `anvil/mainwindow.py` | 3 Stellen: `get_framework_mods()` → `all_framework_mods()` |

### Akzeptanz-Kriterien

- [ ] Cyberpunk-Plugin (nur Python-Defs, keine JSON): Frameworks identisch wie bisher
- [ ] Neues Plugin mit NUR JSON-Datei: Frameworks werden geladen
- [ ] Plugin mit Python + JSON: Python gewinnt bei Namenskonflikt, JSON ergaenzt
- [ ] Fehlerhafte JSON: Warning auf stderr, Plugin laedt trotzdem (graceful)
- [ ] `is_framework_mod()` erkennt Frameworks aus JSON
- [ ] `get_installed_frameworks()` zeigt JSON-Frameworks an
- [ ] `./restart.sh` startet ohne Fehler mit allen bestehenden Plugins

---

## Phase 3: WIP-Plugins aktivieren

### Problem

8 fertige Plugins liegen in `_wip/` und werden nie geladen:
- game_skyrimse.py (321 Zeilen, komplett)
- game_eldenring.py (144 Zeilen, komplett)
- game_fallout3.py
- game_falloutnv.py
- game_morrowind.py
- game_oblivion_remastered.py
- game_bannerlord.py
- game_stardewvalley.py

### Loesung

1. `BaseGame` bekommt ein Attribut `Tested: bool = True`
2. WIP-Plugins setzen `Tested = False`
3. Plugin-Loader laedt ALLE Plugins (auch `_wip/`)
4. UI zeigt bei untested Plugins einen Hinweis (z.B. "[Beta]" im Namen)

### Aenderungen

| Datei | Aenderung |
|-------|-----------|
| `anvil/plugins/base_game.py` | `Tested: bool = True` Attribut |
| `anvil/plugins/plugin_loader.py` | `_scan_directory()` auch fuer `_wip/` aufrufen |
| WIP-Plugins | `Tested = False` setzen |

### Akzeptanz-Kriterien

- [ ] WIP-Plugins werden beim Start geladen
- [ ] WIP-Plugins mit installiertem Spiel erscheinen in der Spieleliste
- [ ] WIP-Plugins sind als "[Beta]" oder aehnlich markiert
- [ ] Bestehende Plugins: `Tested = True` (Default), kein "[Beta]"
- [ ] `./restart.sh` startet ohne Fehler

---

## Phase 4: Bessere User-Plugin-Dokumentation

### Problem

Die README in `~/.anvil-organizer/plugins/games/` ist minimal. Ein User weiss nicht welche Attribute es gibt und was sie bewirken.

### Loesung

README erweitern mit:
- Vollstaendige Attribut-Referenz (Pflicht + Optional)
- Wo man Steam-IDs, GOG-IDs etc. findet
- Beispiel fuer JSON-Framework-Datei
- Link zum Wiki

### Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `anvil/plugins/plugin_loader.py` | `_USER_README` erweitern |

---

## Umsetzungsreihenfolge

```
Phase 1 (BaseGame Proton-Pfade)
  → Kein oeffentliches API-Break
  → Bestehende Overrides gewinnen via MRO
  → Sofort testbar

Phase 2 (JSON-Frameworks)
  → Neues Feature, nichts aendert sich fuer bestehende Plugins
  → Core-Aufrufe umstellen (get_framework_mods → all_framework_mods)
  → is_framework_mod() und get_installed_frameworks() intern umstellen

Phase 3 (WIP-Plugins)
  → Abhaengig von Phase 1 (Proton-Pfade automatisch)
  → Low-Risk: Plugins werden nur geladen wenn Spiel installiert ist

Phase 4 (Dokumentation)
  → Abhaengig von Phase 1+2 (damit Doku vollstaendig ist)
```

---

## Risiko-Analyse

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| Bestehende Plugins brechen | Sehr niedrig | Hoch | Python MRO garantiert Override-Vorrang. Keine bestehende Datei wird geaendert. |
| JSON-Parse-Fehler crasht App | Niedrig | Mittel | try/except mit stderr-Warning, Plugin laedt trotzdem |
| WIP-Plugin crasht bei Spiel-Erkennung | Niedrig | Niedrig | detectGame() ist bereits in try/except (plugin_loader.py:128) |
| `all_framework_mods()` wird nicht ueberall aufgerufen | Mittel | Mittel | Checkliste aller Aufrufstellen (siehe Phase 2 Tabelle) |

---

## NICHT im Scope

- Andere Plugin-Typen (Tool-Plugins, Diagnose-Plugins) — spaetere Version
- Plugin-API (AnvilProxy/IOrganizer) — spaetere Version
- Plugin-Marketplace — spaetere Version
- Bestehende Plugins auf JSON umschreiben — bewusst NICHT
