# Plugins.txt Generator + Plugin-Liste UI — 3 Prompts

---

## Prompt 1: /pa-planer

```
/pa-planer
Feature: plugins.txt Generator + Plugin-Liste UI für Bethesda-Spiele.
Spawne 4 parallele Planungs-Agents.

Problem: Ohne plugins.txt laden Bethesda-Spiele keine .esp/.esm Mods.
Lösung: Nach Deploy automatisch plugins.txt schreiben + UI-Tab dafür.

Analysiere diese Dateien:
- anvil/core/mod_deployer.py (wo Hooks rein müssen)
- anvil/plugins/games/game_fallout4.py (hat schon PRIMARY_PLUGINS + plugins_txt_path)
- anvil/plugins/base_game.py (braucht Default-Methoden)
- anvil/widgets/game_panel.py (neuer Plugins-Tab als Index 0)
- anvil/mainwindow.py (game_plugin an Deployer durchreichen)
- mo2-referenz/src/pluginlist.cpp (MO2-Verhalten)

Neue Datei: anvil/core/plugins_txt_writer.py
- scan_plugins(): .esp/.esm/.esl im Data/ finden
- write(): plugins.txt in Proton-Prefix schreiben
- remove(): plugins.txt bei Purge löschen

Feature-Spec nach: docs/anvil-feature-plugins-txt.md
```

---

## Prompt 2: /workflow

```
/workflow
Implementiere plugins.txt Generator + Plugin-Liste UI.
Lies zuerst: docs/anvil-feature-plugins-txt.md

5 Aufgaben:

1. NEUE DATEI anvil/core/plugins_txt_writer.py
   - scan_plugins(): Data/ nach .esp/.esm/.esl scannen
   - write(): Header + *Plugin.esp Zeilen in plugins_txt_path() schreiben
   - remove(): plugins.txt löschen
   - Primary Plugins (aus game_plugin.PRIMARY_PLUGINS) immer oben

2. anvil/core/mod_deployer.py erweitern
   - __init__: neuer Parameter game_plugin=None
   - deploy(): am Ende write() aufrufen wenn has_plugins_txt()
   - purge(): am Ende remove() aufrufen

3. anvil/plugins/base_game.py erweitern
   - PRIMARY_PLUGINS: list[str] = [] (Klassenattribut)
   - has_plugins_txt() -> bool
   - plugins_txt_path() -> Path | None

4. anvil/widgets/game_panel.py erweitern
   - Neuer "Plugins" Tab als ERSTER Tab (insertTab Index 0)
   - QTableWidget: Checkbox | Name | Markierungen | Mod Index
   - Primary Plugins: Checkbox disabled
   - refresh_plugins() in update_game() aufrufen
   - Tab nur sichtbar wenn has_plugins_txt() True

5. Locale-Dateien: plugins_tab.* Keys hinzufügen

NICHT ändern: game_fallout4.py, Cover-Bilder, Icons
```

---

## Prompt 3: /qa-pruefer

```
/qa-pruefer
Review: plugins.txt Generator + Plugin-Liste UI.
Spawne 4 parallele Agents.
Akzeptanz-Checkliste aus: docs/anvil-feature-plugins-txt.md

Geänderte/neue Dateien:
- anvil/core/plugins_txt_writer.py (NEU)
- anvil/core/mod_deployer.py (game_plugin Parameter + Hooks)
- anvil/plugins/base_game.py (Neue Defaults)
- anvil/widgets/game_panel.py (Plugins-Tab)
- anvil/mainwindow.py (game_plugin Weitergabe)
- Locale-Dateien (plugins_tab.* Keys)

Fokus:
- plugins.txt wird nach Deploy geschrieben und bei Purge gelöscht
- Nur Bethesda-Spiele betroffen (Cyberpunk/Witcher/BG3 nicht)
- Primary Plugins oben, nicht deaktivierbar
- Tab nur sichtbar bei Bethesda-Spielen
- game_plugin korrekt durch alle Aufrufe durchgereicht
- Keine zirkulären Imports, keine Crashes bei None

KEINE Dateien ändern, nur Reports.
```
