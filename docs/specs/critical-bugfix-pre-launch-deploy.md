# CRITICAL BUGFIX: Pre-Launch Deploy kaputt

## Status: SPEC READY — wartet auf GO

---

## Analyse

### Ist-Zustand (Working Tree)

Der letzte Commit (`196faf8`) fügte Auto-Redeploy hinzu. Danach wurden im Working Tree
zwei Fixes versucht:
1. `pre_launch_deploy` Signal in GamePanel → vor JEDEM Launch (Steam/Proton/Direkt)
2. `skip_ba2` Parameter für `silent_purge()` → bei Mod-Toggle kein BA2-Cleanup

### Betroffene Dateien
- `anvil/widgets/game_panel.py` — Signal, `_on_start_clicked`, `silent_purge`
- `anvil/mainwindow.py` — `_pre_launch_deploy`, `_do_redeploy`, `_on_start_game`, Signal-Verbindungen

---

## Bug 1: ENDLOS-SCHLEIFE (5-6× Purge+Deploy pro Klick)

### Root Cause
`_on_start_clicked` hat keinen Schutz gegen Mehrfach-Aufrufe. Mögliche Ursachen:
- Schnelle Doppelklicks auf Start-Button
- Qt-Event-Queuing: Während `silent_purge()` + `silent_deploy()` den Main Thread
  blockieren (BA2-Packing ist I/O-intensiv), können sich Button-Click-Events stauen
- Kein Guard-Flag verhindert Re-Entrant-Aufrufe

### Fix
1. **Guard-Flag** `_is_launching` in GamePanel — verhindert Mehrfach-Ausführung
2. **Start-Button deaktivieren** während Deploy+Launch läuft
3. **`UniqueConnection`** bei Signal-Verbindung als Sicherheitsnetz

---

## Bug 2: RACE CONDITION (Spiel startet vor Deploy-Ende)

### Root Cause
Das `pre_launch_deploy` Signal ist ein **DirectConnection** (gleicher Thread), daher
sollte `_pre_launch_deploy` synchron ablaufen. ABER:
- Wenn Bug 1 (Mehrfach-Aufruf) eintritt, kann ein zweiter Aufruf den ersten
  unterbrechen oder die Reihenfolge durcheinander bringen
- Für Steam/Proton-Launch-Pfade gab es VOR dem Working-Tree-Fix **gar keinen Deploy**

### Fix
- Bug 1 Fix löst auch Bug 2 (kein Mehrfach-Aufruf → kein Race)
- Signal bleibt DirectConnection (Default für gleichen Thread)
- Guard-Flag garantiert: erst Deploy fertig, dann Launch

---

## Bug 3: CRASH nach einiger Zeit

### Root Cause
Direkte Folge von Bug 1: 5-6 volle Deploys (mit BA2-Packing) blockieren den
Main Thread für Sekunden. Qt-Event-Loop verhungert → App wird unresponsive →
System killt den Prozess oder Qt crasht intern.

### Fix
Bug 1 Fix behebt auch Bug 3.

---

## Bug 4: skip_ba2=True bei Mod-Toggle greift nicht

### Root Cause
Im COMMITTED Code (196faf8) hat `_do_redeploy` `silent_purge()` OHNE `skip_ba2`
aufgerufen, weil der Parameter noch nicht existierte:
```python
# Committed (196faf8) — FEHLERHAFT:
def _do_redeploy(self) -> None:
    self._game_panel.silent_purge()          # ← KEIN skip_ba2
    self._game_panel.silent_deploy_fast()
```

Der Working-Tree-Fix ist korrekt (`skip_ba2=True`), war aber noch nicht committed.

### Fix
Working-Tree-Fix beibehalten und committen:
```python
def _do_redeploy(self) -> None:
    self._game_panel.silent_purge(skip_ba2=True)   # ← RICHTIG
    self._game_panel.silent_deploy_fast()           # ← kein BA2-Packing
```

---

## Lösungsplan

### Schritt 1: Guard-Flag in GamePanel._on_start_clicked

```python
# game_panel.py — __init__
self._is_launching = False

# game_panel.py — _on_start_clicked
def _on_start_clicked(self) -> None:
    if self._is_launching:
        return
    self._is_launching = True
    self._start_btn.setEnabled(False)
    try:
        idx = self._selected_exe_index
        if idx < 0 or idx >= len(self._executables):
            return
        # ... bestehende Logik ...
        self.pre_launch_deploy.emit()
        # ... Launch-Logik (Steam/Proton/Direkt) ...
    finally:
        self._is_launching = False
        self._start_btn.setEnabled(True)
```

### Schritt 2: UniqueConnection bei Signal-Verbindung

```python
# mainwindow.py — __init__
self._game_panel.pre_launch_deploy.connect(
    self._pre_launch_deploy,
    Qt.ConnectionType.UniqueConnection,
)
```

### Schritt 3: skip_ba2=True in _do_redeploy beibehalten

Bereits im Working Tree korrekt. Nur committen.

### Schritt 4: _pre_launch_deploy absichern

```python
# mainwindow.py
def _pre_launch_deploy(self) -> None:
    """Full purge + deploy (with BA2) before any game launch."""
    self._redeploy_timer.stop()
    if not self._current_instance_path:
        return
    print("[PURGE] Pre-launch purge", flush=True)
    self._game_panel.silent_purge()
    print("[DEPLOY] Pre-launch full deploy (with BA2)", flush=True)
    self._game_panel.silent_deploy()
```

(Bereits korrekt im Working Tree, keine Änderung nötig.)

---

## Akzeptanz-Checkliste

### Launch funktioniert (alle 3 Pfade)
- [ ] Direkt-Launch (GOG/Epic): Purge → Deploy → Start → Spiel läuft
- [ ] Steam-Launch: Purge → Deploy → Steam -applaunch → Spiel läuft
- [ ] Proton-Launch (F4SE etc.): Purge → Deploy → proton run → Spiel läuft

### Kein Mehrfach-Deploy
- [ ] Ein Klick auf Start → genau 1× "[PURGE] Pre-launch purge" in Konsole
- [ ] Ein Klick auf Start → genau 1× "[DEPLOY] Pre-launch full deploy" in Konsole
- [ ] Schneller Doppelklick → trotzdem nur 1× Deploy

### Deploy synchron vor Launch
- [ ] "[DEPLOY]" Meldung erscheint VOR "ProtonFixes" oder Spiel-Start
- [ ] Kein BA2-Packing mehr nach Spiel-Start sichtbar

### Kein Crash
- [ ] App bleibt nach Game-Start stabil
- [ ] Kein Main-Thread-Blocking über mehrere Sekunden

### skip_ba2 bei Mod-Toggle
- [ ] Mod an/aus per Checkbox → "[PURGE] Auto-redeploy" OHNE "[BA2] INI restored"
- [ ] Mod Drag&Drop → "[PURGE] Auto-redeploy" OHNE "[BA2] INI restored"
- [ ] Konsole zeigt "[DEPLOY] Auto-redeploy: deploying mods (fast, no BA2)"

### Regression: Voller Deploy weiterhin korrekt
- [ ] Game-Start → BA2 wird gepackt (bei Bethesda-Games)
- [ ] Profil-Wechsel → voller Deploy (mit BA2)
- [ ] Instanz-Wechsel → Purge alter + Deploy neuer Mods (mit BA2)
- [ ] App-Close → Purge (mit BA2-Cleanup)

### Code-Qualität
- [ ] Keine neuen Imports nötig (Qt.ConnectionType bereits importiert prüfen)
- [ ] `python -m py_compile` für beide Dateien erfolgreich
- [ ] `./restart.sh` startet ohne Fehler/Tracebacks
