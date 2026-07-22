# Feature: GameValidModFolders — Deploy-Filter (Issue #53)

Datum: 2026-03-19

## Problem
Der Deployer in `mod_deployer.py` iteriert mit `rglob("*")` ueber ALLE Dateien in jedem Mod-Ordner. Einziger Filter: `_SKIP_FILES` (meta.ini, codes.txt). PNGs, READMEs, fomod/, banner.png, Thumbs.db werden per Symlink ins Game-Verzeichnis deployed.

## Loesung: GameValidModFolders (Whitelist)
Neues Klassenattribut in `BaseGame`: Liste erlaubter Top-Level-Ordner. Nur Dateien in diesen Ordnern werden deployed.

## Technische Planung

### Betroffene Dateien
| Datei | Aenderung |
|-------|-----------|
| `anvil/plugins/base_game.py` | `GameValidModFolders: list[str] = []` |
| `anvil/plugins/games/game_cyberpunk2077.py` | Whitelist setzen |
| `anvil/plugins/games/game_witcher3.py` | Whitelist setzen |
| `anvil/plugins/games/game_rdr2.py` | Whitelist setzen |
| `anvil/core/mod_deployer.py` | Neuer Parameter + Filter in Deploy-Schleife |
| `anvil/widgets/game_panel.py` | Attribut an Deployer durchreichen (2 Stellen) |
| ARCHITEKTUR.md | Dokumentation |

### Whitelist-Werte
- Cyberpunk 2077: `["archive", "bin", "r6", "red4ext", "engine", "mods", "scripts", "tweaks", "tools"]`
- Witcher 3: `["mods", "dlc", "bin", "content"]`
- RDR2: `["lml", "scripts", "x64"]`
- Fallout 4: `[]` (leer, hat GameDataPath="Data")
- BG3: NICHT ANFASSEN

### Einfuegestelle in mod_deployer.py
Nach Zeile 214 (`is_direct` berechnet), vor Zeile 218 (data_path Logik):
```python
# Whitelist filter: skip files in unknown top-level folders
if self._valid_mod_folders and not is_direct:
    if len(rel.parts) > 1:
        if rel.parts[0].lower() not in self._valid_mod_folders:
            continue
```

### Signal-Flow
```
BaseGame.GameValidModFolders (Klassenattribut)
  -> game_panel.py: getattr(game_plugin, "GameValidModFolders", [])
  -> ModDeployer.__init__(valid_mod_folders=...)
  -> self._valid_mod_folders = [f.lower() for f in ...]
  -> deploy(): Filter nach rel-Berechnung
```

### Edge Cases (alle geprueft)
- Direct-install Mods: Ausgenommen (is_direct Check)
- LML-Mods: Vor Datei-Schleife abgefangen (Z.167-190)
- BA2-Packing: Fallout 4 hat leere Whitelist, kein Konflikt
- Root-Dateien (len(rel.parts)==1): Nicht gefiltert
- Leere Whitelist: Altes Verhalten (abwaertskompatibel)
- Multi-Folder-Routes: Filter auf originalen Ordnernamen (vor Routing)

## Akzeptanz-Checkliste
- [ ] `base_game.py` hat Attribut `GameValidModFolders: list[str] = []`
- [ ] `game_cyberpunk2077.py` hat Whitelist mit 9 Eintraegen
- [ ] `game_witcher3.py` hat Whitelist mit 4 Eintraegen
- [ ] `game_rdr2.py` hat Whitelist mit 3 Eintraegen
- [ ] `game_fallout4.py` hat KEINE Whitelist (leer, Standard)
- [ ] `game_baldursgate3.py` wurde NICHT veraendert
- [ ] `mod_deployer.py` hat neuen Parameter `valid_mod_folders` im Konstruktor
- [ ] `mod_deployer.py` filtert Dateien in unbekannten Top-Level-Ordnern
- [ ] `mod_deployer.py` ueberspringt Filter fuer direct-install Mods
- [ ] `mod_deployer.py` ueberspringt Filter wenn Whitelist leer ist
- [ ] `mod_deployer.py` ueberspringt Filter fuer Root-Dateien (len(rel.parts)==1)
- [ ] `game_panel.py` reicht `GameValidModFolders` an Deployer durch (update_game)
- [ ] `game_panel.py` reicht `GameValidModFolders` an Deployer durch (set_instance_path)
- [ ] Keine hardcoded Pfade
- [ ] Keine neuen Imports noetig (nur list[str])
- [ ] ARCHITEKTUR.md dokumentiert GameValidModFolders
- [ ] `python -m py_compile` fuer alle geaenderten Dateien erfolgreich
- [ ] `restart.sh` startet ohne Fehler
