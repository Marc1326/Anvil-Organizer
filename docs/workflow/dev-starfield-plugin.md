# Dev-Report: Starfield Plugin aktivieren (Issue #55, Teil 1)

## Durchgefuehrte Aenderungen

### 1. Datei verschoben
- `anvil/plugins/games/_wip/game_starfield.py` -> `anvil/plugins/games/game_starfield.py`
- Das Plugin wird nun beim naechsten Start automatisch vom Plugin-Loader erkannt

### 2. Drei Ergaenzungen in game_starfield.py

**a) ProtonShimFiles Klassen-Attribut (Zeile 69)**
```python
ProtonShimFiles = ["version.dll"]
```
- Analog zu Fallout 4 (`X3DAudio1_7.dll`)
- Wird vom Deployer/Launcher verwendet um Shim-DLLs ins Game-Verzeichnis zu kopieren

**b) get_proton_env_overrides() Methode (Zeile 196-202)**
```python
def get_proton_env_overrides(self) -> dict[str, str]:
    """Return WINEDLLOVERRIDES for SFSE Proton shim."""
    if self._game_path is None:
        return {}
    if (self._game_path / "version.dll").exists():
        return {"WINEDLLOVERRIDES": "version=n,b"}
    return {}
```
- Setzt WINEDLLOVERRIDES wenn version.dll vorhanden ist
- Analog zu Fallout 4 mit X3DAudio1_7.dll
- Notwendig damit SFSE unter Proton/Wine korrekt geladen wird

**c) get_default_categories() Methode (Zeile 214-234)**
- 19 Starfield-spezifische Kategorien (Gameplay, Weapons, Ships, Outposts, etc.)
- Direkter String-Vergleich (kein tr()), analog zu Fallout 4
- Starfield-spezifisch: "Ships" und "Outposts" statt "Settlements" und "Power Armor"

## Validierung

| Check | Ergebnis |
|-------|----------|
| `python -m py_compile` | OK - keine Syntax-Fehler |
| `_wip/game_starfield.py` entfernt | OK - existiert nicht mehr |
| `game_starfield.py` am neuen Ort | OK - vorhanden |
| ProtonShimFiles Attribut | OK - Zeile 69 |
| get_proton_env_overrides() | OK - Zeile 196 |
| get_default_categories() | OK - Zeile 214 |

## Keine anderen Dateien geaendert
- Nur `game_starfield.py` wurde bearbeitet (wie vorgegeben)
