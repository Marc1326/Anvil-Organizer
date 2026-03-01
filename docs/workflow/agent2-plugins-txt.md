# Agent 2 Report: Analyse silent_deploy() und plugins.txt
**Datum:** 2026-03-01

---

## 1. Übersicht

Dieses Dokument analysiert den kompletten Aufrufpfad von `silent_deploy()` in
`GamePanel`, mit Fokus auf die plugins.txt-Generierung.

---

## 2. Aufrufstellen von silent_deploy()

Es gibt genau **2 Stellen** in `anvil/mainwindow.py`, die `silent_deploy()` aufrufen:

### 2.1 Instanz-Wechsel / App-Start (Zeile 953)

```python
# mainwindow.py, _apply_instance()
self._game_panel.set_instance_path(instance_path, profile_name=profile_name)
self._game_panel.silent_deploy()
```

Kontext: Wird aufgerufen wenn:
- Die App startet und die zuletzt aktive Instanz lädt
- Der User eine andere Instanz aus der Seitenleiste wählt

Vorher passiert:
1. `silent_purge()` am Anfang von `_apply_instance()` (Zeile 803)
2. `update_game()` setzt `_current_plugin`, `_current_game_path` (Zeile 842)
3. `set_instance_path()` setzt `_instance_path` und erstellt `ModDeployer` (Zeile 952)

### 2.2 Profil-Wechsel (Zeile 2213)

```python
# mainwindow.py, _on_profile_changed()
self._game_panel.silent_purge()
self._game_panel.set_instance_path(self._current_instance_path, profile_name=name)
self._game_panel.silent_deploy()
```

---

## 3. Kompletter Aufrufpfad (Trace)

```
User-Aktion: Instanz wählen / Profil wechseln
    |
    v
MainWindow._apply_instance() / _on_profile_changed()
    |
    v
GamePanel.set_instance_path(instance_path, profile_name)
    |-- setzt self._instance_path
    |-- setzt self._current_profile_name
    |-- erstellt self._deployer = ModDeployer(...)
    |   (oder None, wenn _current_game_path fehlt)
    v
GamePanel.silent_deploy()
    |
    |-- [BLOCK 1: Deploy]
    |   if self._deployer:
    |       result = self._deployer.deploy()
    |   else:
    |       result = None
    |
    |-- [BLOCK 2: BA2-Packing]
    |   if needs_ba2 AND result.success AND plugin AND game_path AND instance_path:
    |       BA2Packer.pack_all_mods()
    |
    |-- [BLOCK 3: plugins.txt] *** UNABHÄNGIG von Block 1 und 2 ***
    |   if plugin AND has_plugins_txt() AND game_path AND instance_path:
    |       PluginsTxtWriter(plugin, game_path, instance_path).write()
    |       _refresh_plugins_tab()
    v
PluginsTxtWriter.write()
    |
    |-- txt_path = plugin.plugins_txt_path()
    |   (kann None sein → return None)
    |
    |-- plugins = scan_plugins()
    |   (kann leer sein → return None)
    |
    |-- Schreibt Datei nach txt_path
    v
FERTIG
```

---

## 4. Bedingungskette für plugins.txt

### 4.1 Äußere Bedingungen (in silent_deploy, Zeile 590-596)

| # | Bedingung | Gesetzt von | Kann fehlschlagen wenn |
|---|-----------|-------------|----------------------|
| 1 | `self._current_plugin is not None` | `update_game()` | Kein Game-Plugin für dieses Spiel |
| 2 | `hasattr(plugin, "has_plugins_txt")` | BaseGame-Klasse | Immer True (BaseGame hat die Methode) |
| 3 | `plugin.has_plugins_txt()` | Prüft `PRIMARY_PLUGINS` | Nicht-Bethesda-Spiel (z.B. Cyberpunk) |
| 4 | `self._current_game_path is not None` | `update_game()` | Spielpfad nicht gefunden |
| 5 | `self._instance_path is not None` | `set_instance_path()` | Wird immer vor silent_deploy() gesetzt |

### 4.2 Innere Bedingungen (in PluginsTxtWriter.write())

| # | Bedingung | Kann fehlschlagen wenn |
|---|-----------|----------------------|
| 6 | `plugins_txt_path() is not None` | Kein Proton-Prefix gefunden (kein Steam-Spiel) |
| 7 | `scan_plugins()` gibt nicht-leere Liste | Kein Data/-Verzeichnis oder keine .esp/.esm/.esl |

### 4.3 Zusammenfassung: Alle 7 Bedingungen müssen erfüllt sein

```
has_plugins_txt() == True        → Spiel hat PRIMARY_PLUGINS (z.B. Fallout 4)
  AND _current_plugin != None    → Game-Plugin geladen
  AND _current_game_path != None → Spielpfad erkannt
  AND _instance_path != None     → Instanz-Pfad gesetzt
  AND plugins_txt_path() != None → Proton-Prefix existiert (Steam-Spiel)
  AND scan_plugins() nicht leer  → .esp/.esm/.esl im Data/-Ordner gefunden
```

---

## 5. Kritische Beobachtungen

### 5.1 plugins.txt ist UNABHÄNGIG vom Deploy-Ergebnis

Der plugins.txt-Block (Zeile 589-601) prüft NICHT:
- Ob `self._deployer` existiert
- Ob `deploy()` erfolgreich war
- Ob überhaupt Mods aktiviert sind

Das bedeutet: Selbst wenn kein einziger Mod aktiviert ist und `deploy()` mit
"No enabled mods found" zurückkehrt, wird plugins.txt trotzdem geschrieben.
Die plugins.txt enthält dann nur die Game-eigenen .esm/.esp Dateien.

### 5.2 Kein Redeploy bei Mod-Toggle

`_on_mod_toggled()` (mainwindow.py:1022) und `_on_mods_reordered()` (mainwindow.py:1036)
rufen NICHT `silent_deploy()` auf. Sie speichern nur die Modliste auf Disk.

Das bedeutet: Wenn ein User eine Mod aktiviert/deaktiviert, wird:
- Die Modliste gespeichert (modlist.txt / active_mods.json)
- KEIN neuer Deploy ausgeführt
- KEINE plugins.txt aktualisiert

Der nächste Deploy passiert erst bei:
- Profil-Wechsel
- Instanz-Wechsel
- App-Neustart

**Dies ist beabsichtigt** — der Deploy ist eine teure Operation.

### 5.3 protonPrefix() nur für Steam

`plugins_txt_path()` in Fallout4Game delegiert an `protonPrefix()`.
`protonPrefix()` gibt `None` zurück wenn `_detected_store != "steam"`.
Das bedeutet: GOG-Versionen von Bethesda-Spielen bekommen KEINE plugins.txt.

### 5.4 Purge entfernt plugins.txt

`silent_purge()` (Zeile 603-632) ruft `PluginsTxtWriter.remove()` auf, unter
denselben Bedingungen wie der Write-Block.

---

## 6. Signal-Flow Diagramm

```
Instanz-Wechsel:
  Sidebar.instance_clicked → MainWindow._apply_instance()
    → GamePanel.update_game()        [setzt _current_plugin, _current_game_path]
    → GamePanel.set_instance_path()  [setzt _instance_path, erstellt ModDeployer]
    → GamePanel.silent_deploy()
        → ModDeployer.deploy()       [Symlinks erstellen]
        → BA2Packer (optional)       [nur wenn NeedsBa2Packing + deploy erfolgreich]
        → PluginsTxtWriter.write()   [UNABHÄNGIG vom Deploy-Ergebnis]
        → _refresh_plugins_tab()     [UI aktualisieren]

Profil-Wechsel:
  ProfileBar.profile_changed → MainWindow._on_profile_changed()
    → GamePanel.silent_purge()       [alte Symlinks + plugins.txt entfernen]
    → GamePanel.set_instance_path()  [neues Profil setzen]
    → GamePanel.silent_deploy()      [gleicher Flow wie oben]

App-Close:
  MainWindow.closeEvent()
    → GamePanel.silent_purge()       [aufräumen, plugins.txt löschen]
```

---

## 7. Betroffene Dateien

| Datei | Rolle |
|-------|-------|
| `anvil/mainwindow.py` | Ruft silent_deploy() auf (Zeile 953, 2213) |
| `anvil/widgets/game_panel.py` | Enthält silent_deploy() (Zeile 546) |
| `anvil/core/plugins_txt_writer.py` | Scannt Plugins, schreibt/löscht plugins.txt |
| `anvil/plugins/base_game.py` | has_plugins_txt(), plugins_txt_path() (Defaults) |
| `anvil/plugins/games/game_fallout4.py` | PRIMARY_PLUGINS, plugins_txt_path() (konkret) |
| `anvil/core/mod_deployer.py` | deploy() → DeployResult (wird VOR plugins.txt ausgeführt) |
