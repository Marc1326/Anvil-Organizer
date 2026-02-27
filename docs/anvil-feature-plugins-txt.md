# Feature-Spec: plugins.txt Generator + Plugin-Liste UI

**Datum:** 2026-02-26
**Status:** Geplant
**Betrifft:** Bethesda-Spiele (Fallout 4, künftig Skyrim SE, Starfield etc.)

---

## 1. Problem

Bethesda-Spiele (Creation Engine) laden Mod-Plugins (.esp/.esm/.esl) nur, wenn sie in der `plugins.txt` eingetragen sind. Ohne diese Datei werden Symlinks zwar korrekt deployt, aber das Spiel ignoriert die Mod-Dateien. Anvil schreibt aktuell keine `plugins.txt`.

## 2. Lösung

Nach jedem Deploy automatisch `plugins.txt` in den Proton-Prefix schreiben. Bei Purge die Datei löschen/zurücksetzen. Zusätzlich ein UI-Tab zur Anzeige und Verwaltung der Plugin-Liste.

---

## 3. plugins.txt Format (Bethesda-Standard)

```
# This file is used by the game to keep track of your downloaded content.
# Please do not modify this file.
*Fallout4.esm
*DLCRobot.esm
*DLCworkshop01.esm
*DLCCoast.esm
*DLCworkshop02.esm
*DLCworkshop03.esm
*DLCNukaWorld.esm
*DLCUltraHighResolution.esm
*UnofficalFallout4Patch.esp
*SomeMod.esp
InactiveMod.esp
*LightPlugin.esl
```

### Regeln

| Regel | Detail |
|-------|--------|
| Encoding | UTF-8 (ohne BOM) |
| Zeilenende | `\r\n` (Windows-Format, Proton erwartet das) |
| Header | 2 Kommentarzeilen mit `#` |
| Aktiv | `*PluginName.ext` (Asterisk-Prefix) |
| Inaktiv | `PluginName.ext` (ohne Prefix) |
| Reihenfolge | Primary Plugins zuerst, dann Masters (.esm), dann normale Plugins (.esp) |
| Extensions | `.esm`, `.esp`, `.esl` |

---

## 4. Architektur

### 4.1 Neue Datei: `anvil/core/plugins_txt_writer.py`

```
class PluginsTxtWriter:
    __init__(game_plugin, game_path, instance_path)

    scan_plugins() -> list[str]
        # Scannt game_path/Data/ nach .esp/.esm/.esl
        # Filtert optional/ Plugins raus (aus mod_detail_dialog)
        # Sortiert: Primary zuerst, dann .esm, dann .esp/.esl

    write(enabled_plugins: list[str] | None = None) -> Path | None
        # Header schreiben
        # Primary Plugins immer mit * (aktiv)
        # User-Plugins mit * oder ohne (je nach Status)
        # Gibt geschriebenen Pfad zurück oder None

    remove() -> bool
        # plugins.txt löschen
        # Gibt True zurück wenn erfolgreich
```

### 4.2 Hook-Architektur (im GamePanel, nicht im Deployer)

Der `ModDeployer` wird **nicht** umgebaut. Stattdessen werden die Hooks in `GamePanel.silent_deploy()` und `silent_purge()` eingefügt — dort ist `self._current_plugin` verfügbar.

```
GamePanel.silent_deploy()
    -> self._deployer.deploy()
    -> if self._current_plugin and has_plugins_txt():
           PluginsTxtWriter(plugin, game_path, instance_path).write()
           self._refresh_plugins_tab()

GamePanel.silent_purge()
    -> self._deployer.purge()
    -> if self._current_plugin and has_plugins_txt():
           PluginsTxtWriter(plugin, game_path, instance_path).remove()
           self._refresh_plugins_tab()
```

### 4.3 base_game.py Erweiterungen

Neue Defaults in `BaseGame`:

```python
PRIMARY_PLUGINS: list[str] = []

def has_plugins_txt(self) -> bool:
    """True wenn das Spiel eine plugins.txt braucht."""
    return bool(self.PRIMARY_PLUGINS)

def plugins_txt_path(self) -> Path | None:
    """Pfad zur plugins.txt im Proton-Prefix. None = nicht verfügbar."""
    return None
```

Fallout 4 hat bereits `PRIMARY_PLUGINS` und `plugins_txt_path()` — kein Umbau nötig.

### 4.4 UI: Plugins-Tab in game_panel.py

**Position:** Index 0 (erster Tab), mit `setTabVisible(0, False)` für Nicht-Bethesda-Spiele.

**Widget:** QTreeWidget mit Checkboxes

| Spalte | Inhalt | Breite |
|--------|--------|--------|
| 0 | Plugin-Name mit Checkbox | stretch |
| 1 | Typ (ESM/ESP/ESL) | 80px |
| 2 | Mod-Index (hex, 2-stellig) | 60px |

**Verhalten:**
- Primary Plugins: Checkbox disabled, immer checked, nicht verschiebbar, visuell abgehoben (italic/grau)
- User-Plugins: Checkbox frei schaltbar, Drag&Drop für Reihenfolge
- Refresh bei: `update_game()`, nach Deploy, nach Purge

**Tab-Sichtbarkeit:**
```python
# In update_game():
has_plugins = (game_plugin and hasattr(game_plugin, 'has_plugins_txt')
               and game_plugin.has_plugins_txt())
self._tabs.setTabVisible(0, has_plugins)
```

**Index-Anpassung:** `restore_tab_column_widths()` und `_on_tab_changed()` in mainwindow.py müssen von hart-kodierten Indizes auf Tab-Referenzen umgestellt werden (z.B. `self._tabs.indexOf(widget)`).

---

## 5. Datenfluss

```
Mod-Ordner (.mods/<name>/Data/*.esp)
        |
        v
ModDeployer.deploy() — Symlinks nach game_path/Data/
        |
        v
PluginsTxtWriter.scan_plugins() — scannt game_path/Data/ nach .esp/.esm/.esl
        |
        v
PluginsTxtWriter.write() — schreibt plugins.txt in Proton-Prefix
        |
        v
PluginsTab.refresh() — zeigt Plugin-Liste in UI
```

---

## 6. Betroffene Dateien

| Datei | Änderung | Risiko |
|-------|----------|--------|
| `anvil/core/plugins_txt_writer.py` | **NEU** — scan, write, remove | Niedrig |
| `anvil/plugins/base_game.py` | Neue Defaults: `has_plugins_txt()`, `PRIMARY_PLUGINS` | Niedrig |
| `anvil/widgets/game_panel.py` | Plugins-Tab (Index 0), Hooks in silent_deploy/purge | Mittel |
| `anvil/mainwindow.py` | Index-Anpassung restore_tab_column_widths | Mittel |
| `anvil/locales/*.json` (6 Dateien) | Neue tr()-Keys | Niedrig |

**NICHT ändern:**
- `anvil/plugins/games/game_fallout4.py` — hat bereits alles was nötig ist
- `anvil/core/mod_deployer.py` — Hooks gehen über GamePanel, nicht Deployer
- Cover-Bilder, Icons, REDmod

---

## 7. Edge Cases und Risiken

| Edge Case | Lösung |
|-----------|--------|
| Proton-Prefix nicht gefunden | `plugins_txt_path()` gibt None → write() wird übersprungen, Tab zeigt Hinweis |
| AppData/Local/Fallout4/ existiert nicht | `os.makedirs(parent, exist_ok=True)` vor dem Schreiben |
| Mehrere .esp pro Mod | Alle werden aufgenommen, in der Reihenfolge des Mod |
| Optional-ESPs (in optional/ verschoben) | Nicht in plugins.txt aufnehmen — nur Dateien direkt in Data/ |
| DLC nicht installiert | Primary Plugins nur schreiben wenn .esm in game_path/Data/ existiert |
| `_crash_recovery_purge()` ohne game_plugin | plugins.txt bleibt bestehen — wird beim nächsten normalen Purge aufgeräumt |
| Groß-/Kleinschreibung | Case-insensitive Vergleich für .esp/.esm/.esl Extensions |
| Nicht-Bethesda-Spiele | `has_plugins_txt()` gibt False → Tab unsichtbar, keine Hooks |

---

## 8. Akzeptanz-Kriterien

- [ ] `plugins.txt` wird nach Deploy im korrekten Proton-Prefix geschrieben
- [ ] `plugins.txt` wird bei Purge gelöscht
- [ ] Format: UTF-8, `\r\n`, Header-Kommentare, `*`-Prefix für aktive Plugins
- [ ] Primary Plugins (Fallout4.esm + DLCs) immer oben, immer aktiv
- [ ] Nur vorhandene Primary Plugins werden geschrieben (DLC-Check)
- [ ] User-Mod-Plugins (.esp/.esm/.esl) werden nach Primary Plugins gelistet
- [ ] Masters (.esm) werden vor normalen Plugins (.esp) sortiert
- [ ] Optional-ESPs werden NICHT in plugins.txt geschrieben
- [ ] Plugins-Tab ist nur bei Bethesda-Spielen sichtbar
- [ ] Plugins-Tab zeigt alle Plugins mit Checkbox und Typ-Markierung
- [ ] Primary Plugins im Tab: Checkbox disabled, immer checked
- [ ] Tab refresht sich nach Deploy/Purge
- [ ] Keine Regression: Nicht-Bethesda-Spiele (CP2077, Witcher3, BG3, RDR2) unverändert
- [ ] Keine Crashes bei fehlenden Proton-Prefix
- [ ] `./restart.sh` startet ohne Fehler
- [ ] Alle 6 Locale-Dateien haben die neuen Keys

---

## 9. Phase 2 (Später)

- Drag&Drop für Plugin-Reihenfolge im Tab
- ESP-Header-Parsing (Master-Flag, Light-Flag erkennen)
- Master-Dependency-Validierung (fehlende Masters warnen)
- LOOT-Integration für automatische Sortierung
- loadorder.txt für ältere Bethesda-Spiele (Oblivion, FO3, FNV)
- Plugin-Index-Berechnung (FE:xxx für Light Plugins)
- Weitere Bethesda-Plugins (Skyrim SE, Starfield)
