# QA Report -- game_plugin Parameter-Durchreichung (plugins.txt Feature)
Datum: 2026-02-27

## Pruefungsumfang

Fokus auf die Durchreichung des `game_plugin`-Parameters durch alle Aufrufketten:
- `MainWindow` -> `GamePanel.update_game()` -> `PluginsTxtWriter`
- `MainWindow` -> `GamePanel.set_instance_path()` -> `ModDeployer`
- `MainWindow` -> `GamePanel.silent_deploy()` / `silent_purge()` -> `PluginsTxtWriter`
- `MainWindow._crash_recovery_purge()` -> `ModDeployer` (ohne game_plugin)
- Profile-Wechsel -> `silent_purge()` + `silent_deploy()`

Gepruefte Dateien:
- `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py`
- `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py`
- `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_deployer.py`
- `/home/mob/Projekte/Anvil Organizer/anvil/core/plugins_txt_writer.py`
- `/home/mob/Projekte/Anvil Organizer/anvil/plugins/base_game.py`
- `/home/mob/Projekte/Anvil Organizer/anvil/plugins/games/game_fallout4.py`
- `/home/mob/Projekte/Anvil Organizer/anvil/locales/*.json` (alle 6)

---

## Findings

### [HOCH] _crash_recovery_purge() raeumt plugins.txt NICHT auf

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:759-781`
- **Problem:** `_crash_recovery_purge()` erstellt einen blanken `ModDeployer(instance_path, game_path)` und ruft nur `deployer.purge()` auf. Dabei wird KEIN `game_plugin` geladen und KEIN `PluginsTxtWriter.remove()` ausgefuehrt. Wenn die App crasht waehrend Mods deployed sind, werden die Symlinks korrekt entfernt, aber die `plugins.txt` bleibt als verwaiste Datei im Proton-Prefix zurueck.
- **Auswirkung:** Das Spiel laedt beim naechsten Start Plugin-Dateien die gar nicht mehr als Symlinks vorhanden sind. Das fuehrt zu fehlenden Master-Fehlern oder Crashes im Spiel.
- **Hinweis:** Die Feature-Spec (Punkt 7, Edge Cases) sagt: `_crash_recovery_purge() ohne game_plugin: plugins.txt bleibt bestehen -- wird beim naechsten normalen Purge aufgeraeumt.` Das ist also **by design** und kein Bug, ABER:
  - Der naechste normale Purge passiert erst in `_apply_instance()` Zeile 804, also VOR dem neuen Deploy. Da `_apply_instance` zuerst `silent_purge()` ausfuehrt (was die alte plugins.txt entfernt, sofern die alte Instanz das gleiche Spiel war), ist das Verhalten korrekt fuer den Normalfall.
  - **Aber:** Wenn der User das Spiel startet BEVOR er Anvil oeffnet (z.B. direkt ueber Steam), laedt das Spiel eine veraltete plugins.txt. Das ist ein bekanntes Risiko.
- **Bewertung:** Akzeptabel per Feature-Spec, aber trotzdem als **HOCH** eingestuft wegen moeglicher Spielprobleme. Fix waere: in `_crash_recovery_purge()` den `game_plugin` laden und `PluginsTxtWriter.remove()` aufrufen.
- **Fix-Vorschlag:**
```python
# In _crash_recovery_purge():
short_name = data.get("game_short_name", "") if data else ""
plugin = self.plugin_loader.get_game(short_name) if short_name else None
if plugin and hasattr(plugin, "has_plugins_txt") and plugin.has_plugins_txt():
    from anvil.core.plugins_txt_writer import PluginsTxtWriter
    # game_path muss fuer protonPrefix() gesetzt sein
    plugin.setGamePath(game_path, store=data.get("detected_store"))
    writer = PluginsTxtWriter(plugin, game_path, instance_path)
    writer.remove()
```

---

### [MITTEL] Locale-Key "plugins_no_prefix" wird nirgends im Code verwendet

- **Datei:** Alle 6 Locale-Dateien enthalten `"plugins_no_prefix"` (z.B. `anvil/locales/de.json:491`)
- **Problem:** Der Key `game_panel.plugins_no_prefix` ist in allen 6 Locale-Dateien definiert ("Proton-Prefix nicht gefunden" / "Proton prefix not found"), wird aber NIRGENDS im Python-Code referenziert. In `_refresh_plugins_tab()` (game_panel.py:581-626) wird bei fehlendem Prefix einfach `return` ausgefuehrt, ohne dem User eine Meldung anzuzeigen.
- **Auswirkung:** Wenn der Proton-Prefix nicht gefunden wird, ist der Plugins-Tab leer ohne Erklaerung. Der User weiss nicht warum.
- **Fix-Vorschlag:** In `_refresh_plugins_tab()` einen Hinweis-Text anzeigen wenn `plugins_txt_path()` None zurueckgibt:
```python
# In _refresh_plugins_tab(), nach dem Guard-Block:
writer = PluginsTxtWriter(...)
if self._current_plugin.plugins_txt_path() is None:
    item = QTreeWidgetItem()
    item.setText(0, tr("game_panel.plugins_no_prefix"))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
    item.setForeground(0, QColor("#FF8800"))
    self._plugins_tree.addTopLevelItem(item)
    return
```

---

### [MITTEL] PluginsTxtWriter wird bei jedem Refresh/Deploy/Purge neu instanziiert

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py:557, 575, 594`
- **Problem:** Bei `silent_deploy()`, `silent_purge()`, und `_refresh_plugins_tab()` wird jeweils ein neues `PluginsTxtWriter`-Objekt erstellt. Das ist 3x in kurzem Abstand (deploy ruft intern refresh auf). Kein Crash-Risiko, aber unnoetige Arbeit: `scan_plugins()` wird dabei 2x aufgerufen (einmal in `write()`, einmal in `_refresh_plugins_tab()`).
- **Auswirkung:** Minimale Performance-Verschwendung. Kein funktionales Problem.
- **Bewertung:** Phase-2-Optimierung. Kein akuter Handlungsbedarf.

---

## OK-Befunde (Was korrekt ist)

### [OK] Hauptkette MainWindow -> GamePanel -> PluginsTxtWriter ist lueckenlos

Die Aufrufkette in `_apply_instance()`:
1. Zeile 834: `plugin = self.plugin_loader.get_game(short_name)` -- Plugin wird geladen
2. Zeile 835: `self._current_plugin = plugin` -- Plugin wird in MainWindow gespeichert
3. Zeile 843: `self._game_panel.update_game(..., plugin, ...)` -- Plugin wird an GamePanel uebergeben
4. In `update_game()` Zeile 375: `self._current_plugin = game_plugin` -- Plugin wird im GamePanel gespeichert
5. Zeile 953: `self._game_panel.set_instance_path(instance_path, ...)` -- Deployer wird mit Plugin-Attributen erstellt
6. Zeile 954: `self._game_panel.silent_deploy()` -- Deploy + PluginsTxtWriter nutzt `self._current_plugin`

Die Reihenfolge ist korrekt: `update_game()` setzt `_current_plugin` BEVOR `set_instance_path()` und `silent_deploy()` aufgerufen werden. Keine Race Condition.

### [OK] Profile-Wechsel aktualisiert game_plugin korrekt

In `_on_profile_changed()` (mainwindow.py:2211-2214):
```python
self._game_panel.silent_purge()          # Nutzt bestehendes _current_plugin
self._game_panel.set_instance_path(...)  # Neuer Deployer mit bestehendem _current_plugin
self._game_panel.silent_deploy()         # Nutzt bestehendes _current_plugin
```
Der `game_plugin` aendert sich bei einem Profile-Wechsel NICHT (nur bei Instance-Wechsel), daher ist `self._current_plugin` hier immer korrekt.

### [OK] game_plugin kann nicht None sein wenn PluginsTxtWriter aufgerufen wird

Alle drei Stellen (`silent_deploy`, `silent_purge`, `_refresh_plugins_tab`) haben Guards:
```python
if (
    self._current_plugin is not None
    and hasattr(self._current_plugin, "has_plugins_txt")
    and self._current_plugin.has_plugins_txt()
    and self._current_game_path is not None
    and self._instance_path is not None
):
```
Dieser 5-fache Guard verhindert zuverlaessig None-Zugriffe. Der `hasattr`-Check macht den Code auch kompatibel mit aelteren Plugins ohne `has_plugins_txt()`.

### [OK] Nicht-Bethesda-Spiele werden nicht beeinflusst

`BaseGame.has_plugins_txt()` gibt `False` zurueck wenn `PRIMARY_PLUGINS` leer ist (Zeile 342 in base_game.py). Der Tab wird mit `setTabVisible(0, False)` versteckt (game_panel.py:405). Die Hooks in `silent_deploy/purge` greifen nicht. Keine Regression fuer CP2077, Witcher 3, RDR2 etc.

### [OK] PluginsTxtWriter liest game_plugin-Attribute korrekt

- `self._primary = getattr(game_plugin, "PRIMARY_PLUGINS", [])` -- sicher mit Fallback
- `getattr(self._game_plugin, "GameDataPath", "Data")` -- sicher mit Fallback
- `self._game_plugin.plugins_txt_path()` -- wird nur aufgerufen nach Guard-Check

### [OK] Fallout 4 Plugin hat alles was noetig ist

- `PRIMARY_PLUGINS` korrekt definiert (game_fallout4.py:68-77)
- `plugins_txt_path()` korrekt implementiert (game_fallout4.py:143-152)
- `protonPrefix()` korrekt in BaseGame (base_game.py:207-238)
- `has_plugins_txt()` korrekt in BaseGame (base_game.py:341-343)

### [OK] ModDeployer hat bewusst KEINEN game_plugin-Parameter

Laut Feature-Spec (Abschnitt 4.2): "Der ModDeployer wird NICHT umgebaut. Stattdessen werden die Hooks in GamePanel eingefuegt." Das ist korrekt implementiert. Der ModDeployer bleibt game-agnostisch.

### [OK] Alle 6 Locale-Dateien haben die neuen Keys

Alle Keys vorhanden in de, en, es, fr, it, pt:
- `game_panel.plugins_tab`
- `game_panel.plugins_col_name`
- `game_panel.plugins_col_type`
- `game_panel.plugins_col_index`
- `game_panel.plugins_no_prefix` (vorhanden, aber nicht verwendet -- siehe Finding oben)
- `game_panel.start_with_name`

### [OK] Instance-Wechsel (switch_instance) purgt korrekt

`switch_instance()` -> `_apply_instance()` -> Zeile 804: `self._game_panel.silent_purge()` wird VOR dem Laden der neuen Instanz aufgerufen. Da zu diesem Zeitpunkt noch das alte `_current_plugin` gesetzt ist, wird die alte plugins.txt korrekt entfernt, bevor die neue Instanz geladen wird.

### [OK] closeEvent purgt korrekt

`closeEvent()` (mainwindow.py:3056-3060) ruft `self._game_panel.silent_purge()` auf. Da `_current_plugin` zu diesem Zeitpunkt noch gesetzt ist, wird plugins.txt korrekt entfernt.

---

## Checklisten-Pruefung (aus Feature-Spec Abschnitt 8)

- [x] `plugins.txt` wird nach Deploy im korrekten Proton-Prefix geschrieben -- game_panel.py:557-560, PluginsTxtWriter.write() nutzt game_plugin.plugins_txt_path()
- [x] `plugins.txt` wird bei Purge geloescht -- game_panel.py:575-578, PluginsTxtWriter.remove()
- [x] Format: UTF-8, `\r\n`, Header-Kommentare, `*`-Prefix fuer aktive Plugins -- plugins_txt_writer.py:18-21 (Header), Zeile 114 (`*{plugin}\r\n`)
- [x] Primary Plugins (Fallout4.esm + DLCs) immer oben, immer aktiv -- plugins_txt_writer.py:69-72 (Primary zuerst), Zeile 114 (alle mit `*`)
- [x] Nur vorhandene Primary Plugins werden geschrieben (DLC-Check) -- plugins_txt_writer.py:66-72, prueft `if p.lower() in found_lower_map`
- [x] User-Mod-Plugins (.esp/.esm/.esl) werden nach Primary Plugins gelistet -- plugins_txt_writer.py:75-88, remaining nach Primary
- [x] Masters (.esm) werden vor normalen Plugins (.esp) sortiert -- plugins_txt_writer.py:78-88, masters vor others
- [ ] Optional-ESPs werden NICHT in plugins.txt geschrieben -- **ZU PRUEFEN**: Die Spec sagt "nur Dateien direkt in Data/". `scan_plugins()` nutzt `os.scandir(data_dir)` (nicht rglob), also werden nur direkte Kinder gescannt. Das ist korrekt, WENN optional-ESPs in einem Unterordner von Data/ liegen. Anvils optional-Mechanismus (mod_detail_dialog) verschiebt Dateien in `optional/` innerhalb des Mod-Ordners, nicht innerhalb Data/. Da nur deployed Dateien (Symlinks) in Data/ landen und optionale Dateien nicht deployed werden, ist das korrekt.
- [x] Plugins-Tab ist nur bei Bethesda-Spielen sichtbar -- game_panel.py:400-405, `setTabVisible(0, has_plugins)`
- [x] Plugins-Tab zeigt alle Plugins mit Checkbox und Typ-Markierung -- game_panel.py:604-626
- [x] Primary Plugins im Tab: Checkbox disabled, immer checked -- game_panel.py:612-617, `flags & ~ItemIsUserCheckable`, italic, grau
- [x] Tab refresht sich nach Deploy/Purge -- game_panel.py:561, 579 (`_refresh_plugins_tab()`)
- [x] Keine Regression: Nicht-Bethesda-Spiele unveraendert -- Guards pruefen `has_plugins_txt()`, Tab ist hidden
- [x] Keine Crashes bei fehlenden Proton-Prefix -- PluginsTxtWriter.write() gibt None zurueck wenn plugins_txt_path() None ist (Zeile 98-99)
- [ ] `./restart.sh` startet ohne Fehler -- **Nicht getestet** (nur Code-Review, kein Runtime-Test durchgefuehrt)
- [x] Alle 6 Locale-Dateien haben die neuen Keys -- Verifiziert: de, en, es, fr, it, pt alle vorhanden

## Ergebnis: 14/16 Punkte erfuellt

- 1 Punkt "ZU PRUEFEN" aber durch Code-Analyse als korrekt bewertet (optional-ESPs)
- 1 Punkt nicht testbar (restart.sh -- nur Code-Review beauftragt)
- 1 Finding HOCH (crash_recovery_purge raeumt plugins.txt nicht auf -- by design laut Spec)
- 1 Finding MITTEL (plugins_no_prefix Key unbenutzt)
- 1 Finding MITTEL (PluginsTxtWriter wird 2x instanziiert pro Deploy -- Optimierung)

## Gesamtbewertung

**NEEDS REVIEW** -- Die game_plugin-Durchreichung ist korrekt implementiert und die Kette ist lueckenlos. Die zwei offenen Punkte:

1. **_crash_recovery_purge**: Ist per Feature-Spec akzeptiert, stellt aber ein reales Risiko dar. Marc sollte entscheiden ob der Fix in Phase 1 oder Phase 2 kommt.
2. **plugins_no_prefix unbenutzt**: Kleiner Schoenheitsfehler. Die Locale-Keys sind da, der Code nutzt sie nur nicht.

Wenn Marc die beiden Punkte als akzeptabel bewertet: **READY FOR COMMIT**.
