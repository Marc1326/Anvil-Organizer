# Feature-Spec: Sauberer Instance-Wechsel (2-Phasen Teardown)

Datum: 2026-04-03
Agent: 4 (Konsolidierung aus Agent 1-3 + manuelle Code-Verifizierung)

---

## Zusammenfassung

Beim Game-Wechsel (z.B. Cyberpunk -> BG3) werden Trenner vom alten Game im neuen angezeigt. Ursache: `_apply_instance()` hat keinen expliziten Teardown-Schritt. Das Model (`source_model._rows`) wird nicht geleert, bevor der BG3-Pfad die Rows liest und `live_seps` daraus extrahiert. Dadurch landen Cyberpunk-Trenner in der BG3-Modliste.

**Loesung:** 2-phasiger Wechsel mit `_teardown_current_instance()` (Phase 1: alten State sichern und leeren) und bereinigtem `_apply_instance()` (Phase 2: neuen State aufbauen).

### Manuell verifizierte Kern-Fakten

- `_bg3_reload_mod_list()` (Z.5031-5047) liest `model._rows` die noch alte Game-Daten enthalten — BESTAETIGT
- `_apply_instance()` hat keinen Teardown — BESTAETIGT (nur `_redeploy_timer.stop()` + `silent_purge()`)
- BG3-Pfad (Z.1014) macht `return` BEVOR Model geleert wird — BESTAETIGT
- `_write_current_modlist()` wird beim Wegwechseln NICHT aufgerufen — BESTAETIGT (Mod-Reihenfolge geht verloren!)
- `_bg3_save_separators()` wird beim Wegwechseln NICHT aufgerufen — BESTAETIGT
- `_on_profile_changed()` (Z.2921) macht es richtig: sichert Trenner (Z.2938) und Collapsed-State (Z.2972-2978)
- `_fw_query_finished()` (Z.4148) ruft `_reload_mod_list()` auf — Agents haben uebersehen, dass Queue-Clearing allein nicht reicht
- `_batch_query_queue` wird NICHT in `__init__` initialisiert (erst Z.3982) — `hasattr()` Guard noetig

---

## Ist-Zustand

### Aktueller Flow in `_apply_instance()` (mainwindow.py:935-1171)

```
1. _redeploy_timer.stop()           -- Timer stoppen (OK)
2. _game_panel.silent_purge()       -- Symlinks entfernen (OK)
3. Instance-Daten laden             -- load_instance()
4. Plugin + Pfade setzen
5. UI-Updates (setWindowTitle, update_game)
6. BG3-WEICHE (Z.1014):
   if short_name == "baldursgate3":
     _apply_bg3_instance()          -- Eigener Pfad, return!
7. Standard-Pfad: Kategorien, Filter, Profile, Mods laden
```

### Kern-Bug: Datenleck-Kette (verifiziert im Quellcode)

1. User ist in Cyberpunk mit Trennern "Weapons", "Armor" etc.
2. User wechselt zu BG3
3. `_apply_instance()` -> KEIN Model-Clear -> `_apply_bg3_instance()` -> `_bg3_reload_mod_list()`
4. Zeile 5031-5033: `model = self._mod_list_view.source_model(); rows = model._rows`
5. `rows` enthaelt noch die Cyberpunk-Daten inkl. Trenner
6. Zeile 5034-5047: Schleife extrahiert `live_seps` aus diesen alten Rows
7. Zeile 5084: `seps_to_use = live_seps` -- die Cyberpunk-Trenner werden verwendet
8. Zeile 5094-5117: Alte Trenner werden in die BG3-Mod-Liste eingefuegt

### Weitere identifizierte Probleme

| Nr | Problem | Schwere | Code-Stelle |
|----|---------|---------|-------------|
| 1 | Model wird vor BG3-Pfad nicht geleert | KRITISCH | mainwindow.py:1014 (return vor set_mods) |
| 2 | Alte Modlist wird beim Wegwechseln nicht gespeichert | HOCH | mainwindow.py:935-947 (kein _write_current_modlist) |
| 3 | BG3-Trenner werden beim Wegwechseln nicht gesichert | HOCH | mainwindow.py:935-947 (kein _bg3_save_separators) |
| 4 | BG3-Pfad setzt weder Kategorien noch Filter zurueck | MITTEL | mainwindow.py:4891-4971 |
| 5 | Collapsed Separators lecken zwischen Instanzen | MITTEL | _collapsed_separators wird nie geleert |
| 6 | REDmod-Prozess wird nicht gestoppt | MITTEL | game_panel.py:356 |
| 7 | Nexus-Query-Queues laufen weiter | MITTEL | mainwindow.py:317-323 |
| 8 | Suchfeld wird nicht geleert | NIEDRIG | _mod_search bleibt stehen |
| 9 | Highlighted/Conflict Rows werden nicht zurueckgesetzt | NIEDRIG | mod_list_model.py:111-118 |
| 10 | Proxy-Model Filter-State leckt im BG3-Pfad | NIEDRIG | mod_list.py:234-268 |

---

## Soll-Zustand

### 2-phasiger Instance-Wechsel

```
switch_instance(instance_name):
  1. _teardown_current_instance()     -- Phase 1: Alten State sichern + leeren
  2. instance_manager.set_current_instance(instance_name)
  3. _apply_instance(instance_name)   -- Phase 2: Neuen State aufbauen (bereinigt)
```

---

## Betroffene Dateien

| Datei | Aenderungstyp | Beschreibung |
|-------|---------------|-------------|
| `anvil/mainwindow.py` | AENDERUNG | Neue Methode `_teardown_current_instance()`, `switch_instance()` anpassen, `_apply_instance()` bereinigen |
| `anvil/widgets/game_panel.py` | AENDERUNG | Neue Methode `cancel_redmod_if_running()` (kapselt REDmod-Abbruch) |
| `anvil/widgets/mod_list.py` | KEINE | `clear_mods()` existiert bereits, reicht aus |
| `anvil/models/mod_list_model.py` | OPTIONAL | `clear()` um Highlighted/Conflict-Rows erweitern (kosmetisch) |

### Zusaetzliche Aenderungen (aus manueller Code-Verifizierung)

| Datei | Aenderungstyp | Beschreibung |
|-------|---------------|-------------|
| `anvil/mainwindow.py` `_fw_query_next()` | AENDERUNG | Guard hinzufuegen: `if not self._fw_query_active: return` — verhindert dass Queue-Clearing im Teardown zu ungewolltem `_reload_mod_list()` fuehrt (via `_fw_query_finished()` Z.4148) |
| `anvil/mainwindow.py` `_batch_query_next()` | AENDERUNG | Guard hinzufuegen: `if not getattr(self, '_batch_query_active', False): return` — gleicher Grund |

---

## Architektur

### Phase 1: `_teardown_current_instance()`

Neue Methode in `MainWindow`. Wird aufgerufen BEVOR `_apply_instance()`.

**Exakte Reihenfolge (Constraints aus Agent 3 beachtet):**

```python
def _teardown_current_instance(self) -> None:
    """Phase 1: Alten Instance-State sichern und leeren.
    
    Reihenfolge ist KRITISCH:
    - Timer stoppen VOR Purge (sonst deployed Timer nach Purge nochmal)
    - Async-Queues leeren VOR State-Nullung (Callbacks pruefen Queues)
    - State speichern VOR Model-Clearing (sonst werden leere Daten gespeichert)
    - Purge VOR State-Nullung (braucht _deployer und _current_plugin)
    """
    
    # ── Schritt 1: Timer stoppen ──
    self._redeploy_timer.stop()
    
    # ── Schritt 2: Asynchrone Operationen abbrechen ──
    # Nexus-API Queues leeren + active-Flags auf False
    # WICHTIG: Die active-Flags MUESSEN False sein, weil _fw_query_next()
    # und _batch_query_next() jetzt Guards haben die bei active=False returnen.
    # Ohne diese Guards wuerde Queue-Clearing → _fw_query_finished() → 
    # _reload_mod_list() einen ungewollten Reload der neuen Instanz ausloesen.
    self._fw_query_queue.clear()
    self._fw_query_active = False
    if hasattr(self, "_batch_query_queue"):
        self._batch_query_queue.clear()
    if hasattr(self, "_batch_query_active"):
        self._batch_query_active = False
    # REDmod-Prozess abbrechen falls aktiv
    self._game_panel.cancel_redmod_if_running()
    
    # ── Schritt 3: State speichern (VOR Daten-Clearing!) ──
    # Nur wenn eine aktive Instanz existiert (nicht beim ersten Start)
    if self._current_instance_path is not None:
        # PFLICHT: Mod-Reihenfolge sichern (non-BG3)
        # Ohne diesen Save geht die vom User angelegte Reihenfolge verloren!
        if self._bg3_installer is None and self._current_mod_entries:
            self._write_current_modlist()
        # PFLICHT: BG3-Trenner sichern
        if self._bg3_installer is not None:
            self._bg3_save_separators()
        # Collapsed Separators + Splitter + Filter-State sichern
        self._save_ui_state()
    
    # ── Schritt 4: Deploy purgen ──
    # silent_purge() braucht _deployer und _current_plugin (noch nicht None!)
    self._game_panel.silent_purge()
    
    # ── Schritt 5: Model leeren ──
    # clear_mods() ruft source_model.clear() auf (beginResetModel/endResetModel).
    # Kein blockSignals noetig — die View darf ruhig wissen dass das Model leer ist.
    self._mod_list_view.clear_mods()
    
    # Collapsed Separators leeren (KERN-FIX fuer den gemeldeten Bug)
    self._mod_list_view._tree._collapsed_separators.clear()
    
    # Highlighted/Conflict Rows leeren (Indices werden im neuen Game ungueltig)
    model = self._mod_list_view.source_model()
    model._highlighted_rows.clear()
    model._conflict_win_rows.clear()
    model._conflict_lose_rows.clear()
    
    # ── Schritt 6: Filter + Suche zuruecksetzen ──
    self._filter_panel.reset_all()
    self._mod_search.clear()
    
    # ── Schritt 7: State-Variablen nullen ──
    self._current_mod_entries = []
    self._current_profile_path = None
    self._current_instance_path = None
    self._current_downloads_path = None
    self._current_plugin = None
    self._current_game_path = None
    self._bg3_installer = None
    self._mod_index = None
```

**Was GESPEICHERT wird (Schritt 3):**

| Was | Bedingung | Methode |
|-----|-----------|---------|
| Aktuelle Modlist-Reihenfolge | Non-BG3, Mod-Entries vorhanden | `_write_current_modlist()` |
| BG3-Trenner-Positionen | BG3 aktiv | `_bg3_save_separators()` |
| Collapsed Separators | Immer (per-profile oder global) | `_save_ui_state()` |
| Splitter-State, Filter-State | Immer | `_save_ui_state()` |

**Was GELOESCHT wird (Schritte 5-7):**

| Was | Warum |
|-----|-------|
| `source_model._rows` (via `set_mods([])`) | Verhindert Trenner-Leak in BG3-Pfad |
| `_collapsed_separators` | Verhindert Ghost-Collapsed-State im neuen Game |
| `_highlighted_rows`, `_conflict_win_rows`, `_conflict_lose_rows` | Indices werden im neuen Game ungueltig |
| Filter + Suchfeld | Alte Filter sollen nicht neue Modliste filtern |
| Alle `_current_*` State-Variablen | Garantiert sauberer Zustand fuer Apply-Phase |
| `_bg3_installer` | Muss fuer neues Game neu erstellt werden |
| `_mod_index` | Muss fuer neue Instanz neu gebaut werden |

**Was GESTOPPT wird (Schritte 1-2):**

| Was | Warum |
|-----|-------|
| `_redeploy_timer` | Koennte nach Purge nochmal deployen |
| `_fw_query_queue` + `_fw_query_active` | Nexus-Queries fuer falsches Game stoppen |
| `_batch_query_queue` + `_batch_query_active` | Batch-Queries fuer falsches Game stoppen |
| REDmod-Prozess | Laeuft in Thread, koennte neue Instanz korrumpieren |

### Phase 2: `_apply_instance()` (bereinigt)

**Was entfernt wird:**

Die ersten 2 Zeilen des aktuellen `_apply_instance()`:
```python
# ENTFERNEN (Zeilen 944-947) — wird jetzt in _teardown_current_instance() gemacht:
self._redeploy_timer.stop()
self._game_panel.silent_purge()
```

**Was bleibt (unveraendert):**

Der gesamte Rest von `_apply_instance()` ab Zeile 949 (`data = self.instance_manager.load_instance(...)`) bleibt gleich. Die Methode startet jetzt mit garantiert sauberem State.

**Spezialfall: `not data` (leere Instanz, Zeile 950-965):**

Dieser Block leert nochmal State-Variablen. Das ist nach dem Teardown redundant, aber harmlos und dient als Safety-Net. NICHT entfernen.

### Signal/Slot-Flow (neu)

```
Zeitlicher Ablauf beim Instance-Wechsel:

1. User klickt "Game wechseln" in Toolbar/Dialog
   ↓
2. switch_instance(instance_name) aufgerufen
   ↓
3. ═══ PHASE 1: _teardown_current_instance() ═══
   │
   ├─ _redeploy_timer.stop()
   ├─ Nexus-Queues leeren (anonyme QTimer werden No-Ops)
   ├─ _game_panel.cancel_redmod_if_running()
   │   └─ _redmod_cancel_requested = True
   │   └─ _redmod_process.kill() (wenn laeuft)
   ├─ _save_ui_state()  [Collapsed Seps, Splitter]
   ├─ _write_current_modlist() ODER _bg3_save_separators()
   ├─ _game_panel.silent_purge()
   ├─ model.blockSignals(True)
   ├─ model.set_mods([])           ← KEIN mod_toggled/mods_reordered Signal!
   ├─ model.blockSignals(False)
   ├─ _collapsed_separators.clear()
   ├─ _filter_panel.blockSignals(True)
   ├─ _filter_panel.reset_all()    ← KEIN filter_changed Signal!
   ├─ _filter_panel.blockSignals(False)
   ├─ _mod_search.clear()
   └─ State-Variablen = None/[]
   ↓
4. instance_manager.set_current_instance(name)
   ↓
5. ═══ PHASE 2: _apply_instance(instance_name) ═══
   │
   ├─ data = load_instance()
   ├─ Plugin + Pfade setzen
   ├─ _game_panel.update_game()
   ├─ [BG3-Pfad ODER Standard-Pfad]
   │   ├─ Kategorien laden
   │   ├─ Filter setzen
   │   ├─ Profile laden
   │   ├─ Mods scannen
   │   ├─ source_model.set_mods(neue_rows)
   │   │   └─ beginResetModel / endResetModel
   │   ├─ Deployer setzen + silent_deploy()
   │   └─ Frameworks erkennen
   ├─ _status_bar.update_instance()
   ├─ _restore_ui_state()
   └─ _apply_modlist_settings()
```

### Neue Methode in GamePanel: `cancel_redmod_if_running()`

```python
def cancel_redmod_if_running(self) -> None:
    """Cancel any running REDmod deploy process.
    
    Safe to call even if no REDmod deploy is running.
    """
    self._redmod_cancel_requested = True
    if self._redmod_process is not None:
        try:
            self._redmod_process.kill()
        except (OSError, ProcessLookupError):
            pass
```

### Anpassung von `closeEvent()`

`closeEvent()` kann `_teardown_current_instance()` NICHT direkt aufrufen, weil der Teardown State-Variablen auf None setzt, was fuer den Close-Flow nicht sinnvoll ist. Stattdessen bleibt `closeEvent()` wie bisher:

```python
def closeEvent(self, event):
    self._redeploy_timer.stop()
    self._game_panel.silent_purge()
    self._save_ui_state()
    super().closeEvent(event)
```

Die gemeinsame Logik (Timer-Stop, Purge, UI-Save) ist bewusst dupliziert, weil `closeEvent` keinen State leeren muss. Eine Hilfsfunktion wuerde die Lesbarkeit verschlechtern.

---

## Edge Cases

| Nr | Situation | Erwartetes Verhalten |
|----|-----------|---------------------|
| 1 | Erster Start (keine vorherige Instanz) | Teardown ist No-Op: alle `_current_*` sind None/[], silent_purge mit _deployer=None ist No-Op, _save_ui_state schreibt leere Defaults |
| 2 | Gleiche Instanz erneut gewaehlt | Teardown + Apply = sauberer Refresh. Kein fruehes Return. |
| 3 | Schnelles Hin-und-Her-Wechseln | Apply ist synchron (blockiert UI-Thread), daher kein Race-Condition. Anonyme QTimer.singleShot werden durch Queue-Clearing zu No-Ops. |
| 4 | Instance hat keine Mods | Teardown leert Model, Apply setzt leere Liste — kein Problem. |
| 5 | Instance hat korrupte/fehlende Dateien | `_apply_instance()` behandelt `not data` bereits (Z.950-965). Teardown laeuft vorher sauber durch. |
| 6 | REDmod-Deploy laeuft beim Wechsel | `cancel_redmod_if_running()` killt Prozess. `_redmod_finished` Signal wird danach emittiert — Handler muss pruefen ob `_redmod_cancel_requested == True` (ist bereits implementiert: Z.1293 in game_panel.py). |
| 7 | Spiel der alten Instanz laeuft noch | Process-Watcher Thread (daemon) laeuft weiter. `game_stopped` Signal wird emittiert — `_unlock_ui()` ruft `silent_purge()` auf, das mit neuem Deployer ein No-Op ist (andere Instanz). Geringes Restrisiko, kein Handlungsbedarf. |
| 8 | Aktive Downloads beim Wechsel | Downloads laufen weiter im alten Verzeichnis (Worker hat `save_path` bereits). Download-Signale (`download_finished`) kommen mit alten IDs an — GamePanel muss Row-Existence pruefen (ist implizit bereits der Fall). |
| 9 | BG3 -> BG3 Wechsel (andere Instanz) | Teardown sichert BG3-Trenner und leert Model. Neuer BG3-Load startet sauber. |
| 10 | Standard -> Standard Wechsel | Teardown sichert Modlist und Collapsed-State. Neuer Standard-Load startet sauber. |

---

## Risiken

| Nr | Risiko | Schwere | Mitigation |
|----|--------|---------|-----------|
| 1 | Anonyme `QTimer.singleShot()` (6 Stellen: Z.4595, 4639, 4718, 4721, 4734, 4737) koennen NICHT gestoppt werden | HOCH | Queue-Clearing im Teardown. Callbacks pruefen `if not self._fw_query_queue: return` (Z.4130) und `_batch_query_active` — werden zu No-Ops. Verifiziert im Code. |
| 2 | REDmod-Thread laeuft nach Teardown weiter | HOCH | `_redmod_cancel_requested = True` + `_redmod_process.kill()`. Thread prueft Flag (Z.1252, 1293, 1519, 1550). Handler prueft `_redmod_cancel_requested` (Z.1293). |
| 3 | `_save_ui_state()` koennte nach Model-Clearing leere Daten schreiben | HOCH | `_save_ui_state()` wird VOR Model-Clearing aufgerufen (Schritt 3 vor Schritt 5). Reihenfolge ist in der Spec explizit als KRITISCH markiert. |
| 4 | `blockSignals(True)` verhindert interne Model-Updates | MITTEL | Nur waehrend `set_mods([])` und `reset_all()` geblockt. Danach sofort `blockSignals(False)`. Model-interne Logik (beginResetModel/endResetModel in set_mods) verwendet keine Signals fuer interne Konsistenz. |
| 5 | Process-Watcher Thread emittiert `game_stopped` nach Switch | MITTEL | `_unlock_ui()` macht `silent_purge()` — aber mit neuem Deployer ist das harmlos. Kein Handlungsbedarf. |
| 6 | `_write_current_modlist()` bei leerem `_current_mod_entries` | GERING | Guard: nur aufrufen wenn `_current_mod_entries` nicht leer. Bereits in Teardown-Pseudocode enthalten. |
| 7 | GC raeumt `_bg3_installer` nicht sofort auf | GERING | Keine Callbacks registriert die nach GC feuern koennten. Python refcount-basiert, wird sofort freigegeben wenn keine Referenzen mehr existieren. |

---

## MO2-Vergleich

| Aspekt | MO2 | Anvil (nach Fix) |
|--------|-----|-------------------|
| Instance-Wechsel | App-Neustart (Prozess terminiert) | In-App 2-Phasen-Wechsel (Teardown + Apply) |
| Teardown-Garantie | OS raeumt Prozess-Speicher auf | Explizite `_teardown_current_instance()` Methode |
| State-Persistenz | `saveCurrentProfile()` beim Shutdown | `_write_current_modlist()` + `_bg3_save_separators()` + `_save_ui_state()` im Teardown |
| Virtual FS Cleanup | `usvfsClearVirtualMappings()` | `silent_purge()` (Symlinks entfernen) |
| Pending Operations | `DelayedFileWriter` flush, Watcher disconnect | Timer-Stop, Queue-Clear, REDmod-Cancel |
| Profil-Wechsel | Innerhalb Instanz, aehnlich wie Anvil | `_on_profile_changed()` — korrekte Referenz-Implementierung fuer Separator-State |

**Fazit:** Anvil macht bewusst etwas, das MO2 vermeidet (In-App-Switching). Die 2-Phasen-Loesung bildet MO2s "Shutdown + Startup" nach, ohne die App neu starten zu muessen. Der Profil-Wechsel (`_on_profile_changed()`, Z.2921-3017) dient als bewaehrtes Template fuer das Separator-State-Management.

---

## Verwandte Funktionen (geprueft)

| Funktion | Gleicher Fix noetig? | Begruendung |
|----------|---------------------|-------------|
| `closeEvent()` (Z.4867) | NEIN | Macht bereits Timer-Stop + Purge + UI-Save. Beim App-Close muss kein State geleert werden. |
| `_on_profile_changed()` (Z.2921) | NEIN | Wechselt Profil INNERHALB einer Instanz. Mods bleiben gleich, nur Aktiv-Status aendert sich. Hat korrekten Separator-Save/Load. |
| `_reload_mod_list()` (Z.4463) | NEIN | F5-Reload innerhalb derselben Instanz. Kein Instanz-Wechsel. |
| `_crash_recovery_purge()` (Z.901) | NEIN | Laeuft bei App-Start ueber alle Instanzen. Unabhaengig vom Switch-Flow. |
| `_check_first_start()` (Z.867) | NEIN | Ruft `switch_instance()` auf — profitiert automatisch vom neuen Teardown. |
| `_on_manage_instances()` (Z.570) | NEIN | Ruft `switch_instance()` auf — profitiert automatisch. |

---

## Akzeptanz-Checkliste

- [ ] 1. Wenn User von Cyberpunk (mit Trennern "Weapons", "Armor") zu BG3 wechselt, sind KEINE Cyberpunk-Trenner in der BG3-Modliste sichtbar
- [ ] 2. Wenn User von BG3 (mit Trennern) zu Cyberpunk wechselt, sind KEINE BG3-Trenner in der Cyberpunk-Modliste sichtbar
- [ ] 3. Wenn User in Cyberpunk Mods umsortiert hat und dann zu BG3 wechselt und zurueck, ist die Cyberpunk Mod-Reihenfolge EXAKT erhalten (`_write_current_modlist()` wurde beim Wegwechseln aufgerufen)
- [ ] 4. Wenn User von BG3 zu Cyberpunk wechselt und dann zurueck zu BG3, sind die BG3-Trenner vollstaendig erhalten (`_bg3_save_separators()` wurde beim Wegwechseln aufgerufen)
- [ ] 5. Wenn User in Cyberpunk Trenner ein-/ausgeklappt hat und dann zu BG3 wechselt, sind die Collapsed-Separators der BG3-Instanz NICHT vom Cyberpunk-State beeinflusst (kein Ghost-Collapsed-State)
- [ ] 6. Wenn User in Cyberpunk einen Suchtext im Mod-Suchfeld hat und zu BG3 wechselt, ist das Suchfeld leer und alle BG3-Mods sind sichtbar
- [ ] 7. Wenn User in Cyberpunk einen Kategorie-Filter aktiv hat und zu BG3 wechselt, sind keine alten Filter-Chips aktiv und alle BG3-Mods werden angezeigt
- [ ] 8. Wenn User waehrend eines laufenden REDmod-Deploys das Game wechselt, wird der REDmod-Prozess abgebrochen und das neue Game wird sauber geladen (kein Crash, keine korrupten Daten)
- [ ] 9. Wenn User eine neue Instanz erstellt (Wizard) und sofort wechselt, startet der Teardown ohne Crash (alle `_current_*` Variablen koennen None sein)
- [ ] 10. Wenn User die gleiche Instanz erneut auswaehlt, wird ein sauberer Reload durchgefuehrt (Teardown + Apply) ohne Datenverlust
- [ ] 11. Wenn User von Cyberpunk zu BG3 wechselt, zeigt die Statusleiste "Baldur's Gate 3" und nicht "Cyberpunk 2077"
- [ ] 12. Wenn User waehrend einer laufenden Nexus-Batch-Query das Game wechselt, werden die Queues geleert UND die active-Flags auf False gesetzt, sodass anonyme QTimer.singleShot-Callbacks zu echten No-Ops werden (kein ungewollter `_reload_mod_list()` Aufruf)
- [ ] 13. Wenn User von Cyberpunk (Collapsed Separators per-Profile) zu BG3 wechselt, werden die Cyberpunk Collapsed-Separators im alten Profil korrekt gespeichert (ui_state.json)
- [ ] 14. Wenn `_apply_instance()` fuer die neue Instanz `not data` liefert (korrupte Instanz), wird die UI sauber geleert ohne Crash
- [ ] 15. `_fw_query_next()` und `_batch_query_next()` haben Guards (`if not self._fw_query_active: return` bzw. `if not getattr(self, '_batch_query_active', False): return`) die verhindern dass Queue-Clearing im Teardown zu `_fw_query_finished()` → `_reload_mod_list()` fuehrt
- [ ] 16. `./restart.sh` startet ohne Fehler
