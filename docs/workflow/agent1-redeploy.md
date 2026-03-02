# Agent 1 Report: Re-Deploy-Analyse

**Datum:** 2026-03-02
**Aufgabe:** Analyse wann/warum Re-Deploy NICHT ausgeloest wird bei Mod-Toggle

---

## 1. Definition von `silent_deploy()` und `silent_purge()`

Beide Methoden sind in **`anvil/widgets/game_panel.py`** definiert.

### `silent_deploy()` (Zeile 546-603)

```python
def silent_deploy(self) -> None:
    """Deploy mods silently.  Called automatically by MainWindow."""
    result = None
    if self._deployer:
        result = self._deployer.deploy()
    # ... BA2-Packing + plugins.txt
```

Funktionsweise:
- Ruft `self._deployer.deploy()` auf (Symlink-basiertes Deployment)
- Fuehrt danach BA2-Packing fuer Bethesda-Spiele durch
- Schreibt `plugins.txt` fuer Bethesda-Spiele

### `silent_purge()` (Zeile 605-608)

```python
def silent_purge(self) -> None:
    """Purge deployed mods silently.  Called automatically by MainWindow."""
    if self._deployer:
        self._deployer.purge()
    # ... BA2-Cleanup
```

Funktionsweise:
- Ruft `self._deployer.purge()` auf (entfernt alle Symlinks)
- Raeumt BA2-Dateien auf

---

## 2. Alle Aufruforte

Datei: **`anvil/mainwindow.py`**

| Zeile | Methode | Aufruf | Kontext |
|-------|---------|--------|---------|
| 803 | `_apply_instance()` | `silent_purge()` | Vor Instanzwechsel: alte Symlinks entfernen |
| 953 | `_apply_instance()` | `silent_deploy()` | Nach Instanzwechsel: neue Mods deployen |
| 2211 | `_on_profile_changed()` | `silent_purge()` | Vor Profilwechsel: alte Symlinks entfernen |
| 2213 | `_on_profile_changed()` | `silent_deploy()` | Nach Profilwechsel: neue Mods deployen |
| 3057 | `closeEvent()` | `silent_purge()` | Beim Schliessen: alles aufraeumen |

**Fazit:** Re-Deploy passiert nur bei Instanzwechsel, Profilwechsel und App-Schliessung. NICHT bei Mod-Statusaenderung.

---

## 3. Signal-Flow bei Mod-Toggle

```
User klickt Checkbox in Mod-Liste
    |
    v
ModListModel.setData() [mod_list_model.py:333-336]
    | 1. Setzt _rows[row].enabled = new_enabled
    | 2. Emittiert dataChanged (fuer UI-Update der Checkbox)
    | 3. Emittiert mod_toggled(row, new_enabled)
    |
    v
Signal-Verbindung [mainwindow.py:271]
    model.mod_toggled.connect(self._on_mod_toggled)
    |
    v
MainWindow._on_mod_toggled(row, enabled) [mainwindow.py:1022-1034]
    | 1. Findet passenden ModEntry in _current_mod_entries
    | 2. Setzt entry.enabled = enabled (im Speicher)
    | 3. Ruft _write_current_modlist() auf
    |    -> Schreibt modlist.txt + active_mods.json auf Platte
    | 4. Ruft _update_active_count() auf (UI: "5/10 aktiv")
    |
    v
ENDE ---- KEIN silent_purge() / silent_deploy()!
```

---

## 4. Warum aktuell KEIN automatisches Re-Deploy passiert

**Kernursache:** `_on_mod_toggled()` aktualisiert nur den internen Status und die Festplatte, ruft aber NICHT `silent_deploy()` auf.

Die Konsequenz:
- Datei auf Platte (`active_mods.json`) ist korrekt aktualisiert
- Symlinks im Spiel-Verzeichnis bleiben unveraendert
- Deaktivierte Mod ist weiterhin deployed
- Aktivierte Mod ist nicht deployed
- Erst beim naechsten Instanz- oder Profilwechsel wird der korrekte Status deployed

### Wie der Deployer aktive Mods liest

`ModDeployer.deploy()` liest aktive Mods **von der Festplatte** (nicht aus dem Speicher):

```python
# mod_deployer.py:134-141
global_order = read_global_modlist(self._profiles_dir)
active_mods = read_active_mods(self._profile_path)
enabled_mods = [
    (name, idx) for idx, name in enumerate(global_order)
    if name in active_mods
]
```

Da `_write_current_modlist()` die Dateien bereits korrekt aktualisiert, wuerde ein anschliessender `silent_deploy()`-Aufruf die richtigen Mods deployen.

---

## 5. Alle Stellen wo Mod-Status geaendert wird

### Stellen OHNE Re-Deploy (BUG)

| Methode | Datei:Zeile | Trigger | Was passiert |
|---------|-------------|---------|--------------|
| `_on_mod_toggled()` | mainwindow.py:1022 | Checkbox klicken | Persistiert, KEIN Deploy |
| `_on_mods_reordered()` | mainwindow.py:1036 | Drag & Drop Reihenfolge | Persistiert + Conflicts, KEIN Deploy |
| `_ctx_enable_selected()` | mainwindow.py:2430 | Kontextmenue Aktivieren/Deaktivieren | Persistiert, KEIN Deploy |
| `_ctx_enable_all()` | mainwindow.py:2445 | Toolbar "Alle aktivieren/deaktivieren" | Delegiert an `_ctx_enable_selected`, KEIN Deploy |
| `_reload_mod_list()` | mainwindow.py:2821 | F5-Refresh, Mod-Installation, Mod-Loeschung | Liest nur neu, KEIN Deploy |
| `_ctx_remove_mods()` | mainwindow.py:2726 | Kontextmenue "Mod entfernen" | Loescht + Reload, KEIN Deploy |

### Stellen MIT Re-Deploy (korrekt)

| Methode | Datei:Zeile | Trigger | Was passiert |
|---------|-------------|---------|--------------|
| `_apply_instance()` | mainwindow.py:793 | Instanzwechsel | purge -> deploy |
| `_on_profile_changed()` | mainwindow.py:2156 | Profilwechsel | purge -> set_instance_path -> deploy |
| `closeEvent()` | mainwindow.py:3055 | App schliessen | Nur purge |

---

## 6. Abhaengigkeiten des Deployers

Der `ModDeployer` wird in `GamePanel.set_instance_path()` (game_panel.py:897-910) erstellt mit:
- `instance_path` -- Pfad zur Instanz
- `game_path` -- Pfad zum Spiel
- `profile_name` -- Name des aktiven Profils
- Diverse Plugin-Attribute (direct_patterns, data_path, nest, lml_path, etc.)

Der Deployer speichert den Profilnamen bei Erstellung. Er liest dann aus `instance_path/.profiles/` die globale `modlist.txt` und aus `instance_path/.profiles/{profile_name}/active_mods.json` die aktiven Mods.

---

## 7. Zusammenfassung

**Das Problem ist klar definiert:** An 6 von 9 Stellen, die den Mod-Status aendern, wird KEIN Re-Deploy ausgeloest. Die Daten auf der Festplatte sind korrekt, aber die Symlinks im Spiel-Verzeichnis spiegeln den aktuellen Status nicht wider.

**Die Loesung waere:** An den 6 fehlenden Stellen nach dem Persistieren ein `silent_purge()` + `silent_deploy()` aufrufen (oder eine optimierte Variante davon).
