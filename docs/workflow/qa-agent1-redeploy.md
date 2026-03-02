# QA Agent 1 Report -- Redeploy-Logik in mainwindow.py

**Datum:** 2026-03-02
**Pruefgegenstand:** Auto-Redeploy bei Mod-Statusaenderung
**Spezifikation:** `docs/anvil-feature-redeploy.md`
**Geprueft:** `anvil/mainwindow.py`, `anvil/widgets/game_panel.py`, `anvil/core/mod_deployer.py`, Locale-Dateien

---

## 1. Pruefung: Existiert _on_mod_toggled? Loest es einen Re-Deploy aus?

**Ergebnis: OK**

Die Methode existiert in `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:1030`:

```python
def _on_mod_toggled(self, row: int, enabled: bool) -> None:
    """A mod checkbox was toggled -- update entries and persist."""
    model = self._mod_list_view.source_model()
    if 0 <= row < len(model._rows):
        row_data = model._rows[row]
        for entry in self._current_mod_entries:
            display = entry.display_name or entry.name
            if display == row_data.name:
                entry.enabled = enabled
                break
    self._write_current_modlist()
    self._update_active_count()
    self._schedule_redeploy()       # <-- Zeile 1043: Debounced Redeploy
```

**Signal-Verbindung** (Zeile 271):
```python
model.mod_toggled.connect(self._on_mod_toggled)
```

**Signal-Definition** in `anvil/models/mod_list_model.py:90`:
```python
mod_toggled = Signal(int, bool)   # (source_row, enabled)
```

**Signal-Emission** in `anvil/models/mod_list_model.py:336`:
```python
self.mod_toggled.emit(index.row(), new_enabled)
```

Kette vollstaendig: Checkbox -> setData() -> mod_toggled.emit() -> _on_mod_toggled() -> _schedule_redeploy()

---

## 2. Pruefung: Existiert _on_mods_reordered? Loest es einen Re-Deploy aus?

**Ergebnis: OK**

Die Methode existiert in `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:1045`:

```python
def _on_mods_reordered(self) -> None:
    """Mods were reordered via drag & drop -- sync entries and persist."""
    model = self._mod_list_view.source_model()
    new_entries = []
    for i in range(model.rowCount()):
        row_data = model._rows[i]
        for entry in self._current_mod_entries:
            display = entry.display_name or entry.name
            if display == row_data.name and entry not in new_entries:
                entry.priority = i
                new_entries.append(entry)
                break
    framework_entries = [e for e in self._current_mod_entries if e.is_direct_install]
    self._current_mod_entries = new_entries + framework_entries
    self._write_current_modlist()
    self._update_active_count()
    # Recompute conflict icons
    conflict_data = self._compute_conflict_data()
    for row_data in model._rows:
        folder = row_data.folder_name
        row_data.conflicts = conflict_data.get(folder, "")
    model.dataChanged.emit(...)
    self._schedule_redeploy()       # <-- Zeile 1073: Debounced Redeploy
```

**Signal-Verbindung** (Zeile 272):
```python
model.mods_reordered.connect(self._on_mods_reordered)
```

Kette vollstaendig: Drag&Drop -> mods_reordered.emit() -> _on_mods_reordered() -> _schedule_redeploy()

---

## 3. Pruefung: Debounce-Timer korrekt implementiert?

**Ergebnis: OK**

### Timer-Initialisierung (Zeile 285-289):
```python
self._redeploy_timer = QTimer()
self._redeploy_timer.setSingleShot(True)
self._redeploy_timer.setInterval(500)
self._redeploy_timer.timeout.connect(self._do_redeploy)
```

- `setSingleShot(True)`: Korrekt, feuert nur einmal nach Ablauf
- `setInterval(500)`: 500ms Debounce wie spezifiziert
- `timeout.connect(_do_redeploy)`: Signal korrekt verbunden

### _schedule_redeploy() (Zeile 1083-1088):
```python
def _schedule_redeploy(self) -> None:
    """Schedule a debounced redeploy (500ms)."""
    if not self._current_instance_path:
        return
    self.statusBar().showMessage(tr("status.deploying"), 0)
    self._redeploy_timer.start()
```

- Guard gegen fehlende Instanz: OK
- StatusBar-Feedback "Deploying...": OK
- `start()` auf bereits laufendem SingleShot-Timer resettet automatisch den Zaehler: **Korrektes Debounce-Verhalten** (Qt-Doku: "If the timer is already running, it will be stopped and restarted.")

### _do_redeploy() (Zeile 1090-1099):
```python
def _do_redeploy(self) -> None:
    """Execute purge + fast deploy immediately."""
    self._redeploy_timer.stop()
    if not self._current_instance_path:
        return
    print("[PURGE] Auto-redeploy: purging current deployment", flush=True)
    self._game_panel.silent_purge()
    print("[DEPLOY] Auto-redeploy: deploying mods (fast, no BA2)", flush=True)
    self._game_panel.silent_deploy_fast()
    self.statusBar().showMessage(tr("status.deployed"), 3000)
```

- `stop()` am Anfang: Gut, verhindert erneutes Feuern falls manuell aufgerufen
- Guard gegen fehlende Instanz: OK
- Konsolen-Output [PURGE] und [DEPLOY]: OK, pruefbar
- `silent_deploy_fast()` statt `silent_deploy()`: Korrekt, kein BA2-Packing

---

## 4. Pruefung: Race Conditions?

**Ergebnis: OK -- Kein Risiko**

Alle Ausfuehrung erfolgt im Qt Main Thread (Event Loop):
- `_on_mod_toggled()` wird per Signal/Slot im Main Thread aufgerufen
- `QTimer.timeout` wird im Main Thread dispatched
- `_do_redeploy()` laeuft synchron im Main Thread
- Es gibt keine Worker-Threads fuer Deploy/Purge
- Waehrend `_do_redeploy()` laeuft, werden keine weiteren Timer-Events verarbeitet

**Potenzielle Schwaeche (kein Bug, Performance-Hinweis):**
`_do_redeploy()` ruft `silent_purge()` + `silent_deploy_fast()` synchron auf. Bei sehr vielen Mods (300+) koennte dies die UI fuer ~500ms-2s blockieren. Dies ist im Risiko-Abschnitt der Spezifikation dokumentiert und akzeptiert.

---

## 5. Pruefung: Deploy-Aufruf korrekt an GamePanel weitergegeben?

**Ergebnis: OK mit einem Hinweis**

### silent_deploy_fast() in game_panel.py (Zeile 605-624):
```python
def silent_deploy_fast(self) -> None:
    """Deploy mods without BA2 packing. Used for quick redeploy after toggle."""
    if self._deployer:
        self._deployer.deploy()
    # Write plugins.txt for Bethesda games
    if (self._current_plugin is not None
        and hasattr(self._current_plugin, "has_plugins_txt")
        and self._current_plugin.has_plugins_txt()
        and self._current_game_path is not None
        and self._instance_path is not None):
        writer = PluginsTxtWriter(...)
        result_path = writer.write()
        ...
        self._refresh_plugins_tab()
```

- Kein BA2-Packing: Korrekt wie spezifiziert
- plugins.txt wird geschrieben: OK fuer Bethesda-Spiele
- `_refresh_plugins_tab()` wird aufgerufen: UI bleibt konsistent

### Doppel-Purge Hinweis (LOW):
`_do_redeploy()` ruft `silent_purge()` auf, danach `silent_deploy_fast()` -> `deployer.deploy()`.
Innerhalb von `deployer.deploy()` (Zeile 123-125) steht:
```python
if self.is_deployed():
    purge_result = self.purge()
```
Das bedeutet: Wenn die Purge in `_do_redeploy()` das Manifest korrekt loescht, findet `deploy()` kein Manifest mehr und ueberspringt die interne Purge. Der zweite Purge-Check ist ein No-Op, da `is_deployed()` -> `False` sein sollte. **Kein funktionaler Bug**, aber ein redundanter Purge-Aufruf.

---

## 6. Vollstaendige Aufrufliste aller Redeploy-Stellen

| Zeile | Methode | Trigger-Art | Korrekt? |
|-------|---------|-------------|----------|
| 1043 | `_on_mod_toggled()` | `_schedule_redeploy()` (debounced) | OK |
| 1073 | `_on_mods_reordered()` | `_schedule_redeploy()` (debounced) | OK |
| 1418 | `_install_archives()` | `_schedule_redeploy()` (debounced) | OK |
| 2484 | `_ctx_enable_selected()` | `_schedule_redeploy()` (debounced) | OK |
| 2731 | `_ctx_rename_mod()` | `_do_redeploy()` (sofort) | OK |
| 2767 | `_ctx_reinstall_mod()` | `_do_redeploy()` (sofort) | OK |
| 2799 | `_ctx_remove_mods()` | `_do_redeploy()` (sofort) | OK |
| 2144 | `_restore_backup()` | `_do_redeploy()` (sofort) | OK |

### Stellen wo Timer gestoppt wird (Safety Guards):
| Zeile | Methode | Kontext |
|-------|---------|---------|
| 809 | `_apply_instance()` | Instanzwechsel |
| 2250 | `_on_profile_changed()` | Profilwechsel |
| 3100 | `closeEvent()` | App-Schliessung |
| 1203 | `_on_start_game()` | Vor Game-Start (Full Deploy) |

---

## 7. Pruefung: i18n-Keys

**Ergebnis: OK**

Alle 3 Keys in allen 6 Locales vorhanden:

| Key | de | en | es | fr | it | pt |
|-----|----|----|----|----|----|----|
| `status.deploying` | Zeile 436 | Zeile 436 | Zeile 436 | Zeile 436 | Zeile 436 | Zeile 436 |
| `status.deployed` | Zeile 437 | Zeile 437 | Zeile 437 | Zeile 437 | Zeile 437 | Zeile 437 |
| `status.deploy_skipped` | Zeile 438 | Zeile 438 | Zeile 438 | Zeile 438 | Zeile 438 | Zeile 438 |

**Hinweis:** `status.deploy_skipped` wird in `mainwindow.py` nirgends verwendet (kein grep-Treffer). Es existiert nur in den Locale-Dateien. Dies ist kein Bug, aber ein unbenutzer Key.

---

## 8. Befunde nach Severity

### [LOW] Unbenutzter i18n-Key `status.deploy_skipped`
- **Datei:** Alle 6 Locale-Dateien, jeweils Zeile 438
- **Problem:** Der Key `status.deploy_skipped` wird weder in `mainwindow.py` noch in einer anderen Python-Datei referenziert. Er wurde laut Spezifikation geplant, aber nicht verwendet.
- **Fix:** Entweder in `_schedule_redeploy()` als Else-Zweig verwenden, oder aus den Locale-Dateien entfernen. Kein dringendes Problem.

### [LOW] Redundanter Purge-Aufruf in _do_redeploy()
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:1096` + `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_deployer.py:123-125`
- **Problem:** `_do_redeploy()` ruft `silent_purge()` auf, anschliessend `silent_deploy_fast()` -> `deployer.deploy()`, welches intern NOCHMALS `purge()` aufruft falls `is_deployed()`. Da die erste Purge das Manifest loescht, ist die zweite Pruefung ein No-Op. Aber es entsteht eine unnoetige Filesystem-Pruefung.
- **Fix:** Kein Fix noetig. Der externe Purge ist defensiv und schadet nicht. Nur bei Performance-Optimierung relevant.

---

## 9. Checklisten-Pruefung (Code-Review, NICHT Runtime-Test)

Folgende Punkte koennen rein durch Code-Analyse bewertet werden:

- [x] **AK-01:** `_on_mod_toggled()` -> `_schedule_redeploy()` -> 500ms -> `_do_redeploy()` -> `silent_purge()` + `silent_deploy_fast()`. Kette vollstaendig.
- [x] **AK-02:** Gleiche Kette. `enabled=False` -> modlist wird aktualisiert -> redeploy liest neue modlist.
- [x] **AK-03:** `QTimer.setSingleShot(True)` + `start()` resettet Timer bei erneutem Aufruf. 5 Toggles in <500ms -> nur letzter Timer laeuft ab -> 1 Deploy-Zyklus.
- [x] **AK-04:** `start()` auf laufendem QTimer resettet den Countdown. Korrekt.
- [x] **AK-05:** `_on_mods_reordered()` -> `_schedule_redeploy()` -> debounced deploy. Kette vollstaendig.
- [x] **AK-06/07:** `_ctx_enable_selected()` (Zeile 2484) -> `_schedule_redeploy()`. Kette vollstaendig.
- [x] **AK-08:** `_ctx_remove_mods()` (Zeile 2799) -> `_do_redeploy()` (sofort, kein Debounce). Korrekt.
- [x] **AK-09:** `_ctx_rename_mod()` (Zeile 2731) -> `_do_redeploy()` (sofort). Korrekt.
- [x] **AK-10:** `_install_archives()` (Zeile 1418) -> `_schedule_redeploy()` (debounced). Korrekt.
- [x] **AK-11:** `_ctx_reinstall_mod()` (Zeile 2767) -> `_do_redeploy()` (sofort). Korrekt.
- [x] **AK-12:** `_restore_backup()` (Zeile 2144) -> `_do_redeploy()` (sofort). Korrekt.
- [x] **AK-13:** `_do_redeploy()` ruft `silent_deploy_fast()` auf, welches BA2-Block ueberspringt. Korrekt.
- [x] **AK-14:** `_on_start_game()` (Zeile 1203-1209) stoppt Timer, macht Purge, ruft `silent_deploy()` (MIT BA2). Korrekt.
- [x] **AK-15:** `silent_deploy_fast()` schreibt plugins.txt wenn `has_plugins_txt()`. Korrekt.
- [x] **AK-16:** `_schedule_redeploy()` -> `statusBar().showMessage(tr("status.deploying"), 0)`. Die `0` bedeutet "anzeigen bis manuell geaendert". Korrekt.
- [x] **AK-17:** `_do_redeploy()` -> `statusBar().showMessage(tr("status.deployed"), 3000)`. 3 Sekunden. Korrekt.
- [x] **AK-18:** `_apply_instance()` Zeile 809: `self._redeploy_timer.stop()`. Korrekt.
- [x] **AK-19:** `_on_profile_changed()` Zeile 2250: `self._redeploy_timer.stop()`. Korrekt.
- [x] **AK-20:** `closeEvent()` Zeile 3100: `self._redeploy_timer.stop()` + `silent_purge()`. Korrekt.
- [x] **AK-21:** `_schedule_redeploy()` prueft `if not self._current_instance_path: return`. `_do_redeploy()` prueft dasselbe. Korrekt, kein Fehler bei fehlender Instanz.
- [x] **AK-22:** Alle 3 Keys (`status.deploying`, `status.deployed`, `status.deploy_skipped`) in allen 6 Locales vorhanden.
- [x] **AK-23:** `_apply_instance()` stoppt Timer (809), purged (811), dann `set_instance_path()` + `silent_deploy()` (960-961). `_on_profile_changed()` stoppt Timer (2250), purged (2251), `set_instance_path()` (2252), `silent_deploy()` (2253). Kein doppelter Deploy.
- [x] **AK-24:** `_do_redeploy()` gibt `[PURGE]` (Zeile 1095) und `[DEPLOY]` (Zeile 1097) aus. `_on_start_game()` gibt `[PURGE]` (1206) und `[DEPLOY]` (1208) aus. Korrekt.
- [ ] **AK-25:** Nicht geprueft (kein Runtime-Test in diesem Report, nur Code-Review)

## Ergebnis: 24/25 Punkte geprueft und bestanden (1 Punkt erfordert Runtime-Test)

---

## 10. Gesamtbewertung

Die Redeploy-Logik ist **vollstaendig und korrekt implementiert**:

1. **_on_mod_toggled**: Existiert, korrekt verbunden, loest debounced Redeploy aus
2. **_on_mods_reordered**: Existiert, korrekt verbunden, loest debounced Redeploy aus
3. **Debounce-Timer**: QTimer SingleShot 500ms, korrekt implementiert mit automatischem Reset
4. **Race Conditions**: Keine -- alles laeuft synchron im Main Thread
5. **Deploy-Weitergabe**: Korrekt ueber GamePanel.silent_deploy_fast() (ohne BA2) und silent_deploy() (mit BA2 vor Game-Start)
6. **Safety Guards**: Timer wird bei Instanz-/Profilwechsel und App-Schliessung gestoppt
7. **i18n**: Alle Keys in allen 6 Locales vorhanden
8. **Alle 8 spezifizierten Stellen** haben Redeploy-Aufrufe (4x debounced, 4x sofort)

**Keine CRITICAL oder HIGH Findings.**
Zwei LOW-Findings: unbenutzter i18n-Key und redundanter Purge (beide nicht funktionsrelevant).

## Ergebnis: READY FOR COMMIT (aus Code-Review-Perspektive, AK-25 Runtime-Test steht noch aus)
