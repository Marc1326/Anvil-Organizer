# Feature: Game Running Lock (UI-Sperre beim Game-Start)
Datum: 2026-03-21

## Zusammenfassung

Wenn ein Game gestartet wird, soll die gesamte Anvil-UI gesperrt werden, damit der User keine Mod-Änderungen, Deploy-Aktionen oder andere Operationen vornehmen kann, während das Spiel läuft. Die Sperre muss manuell über einen "Entsperren"-Button aufhebbar sein, oder automatisch wenn die Proton/Direkt-PID endet. Steam-Starts erhalten nur manuellen Unlock, da die Steam-PID nicht der Game-PID entspricht.

## Betroffene Dateien

| Datei | Änderung |
|---|---|
| `anvil/mainwindow.py` | Lock-Banner, `_lock_ui()`, `_unlock_ui()`, `_on_pid_poll()`, `_on_game_started()` erweitern |
| `anvil/widgets/game_panel.py` | Signal `game_started = Signal(str, int)` — name + pid |
| `anvil/locales/*.json` | 7 Locale-Dateien: neue Keys `game_lock.running_label`, `game_lock.unlock_button` |

**NICHT betroffen:** Alle Game-Plugins, BG3-Code, Deployer, ModList, Filter

## Signal-Flow: Vorher

```
GamePanel.game_started.emit(game_name)     # Signal(str)
    └── MainWindow._on_game_started(name)
        └── statusBar().showMessage(msg, 5000)   # nur 5 Sek Meldung
```

## Signal-Flow: Nachher

```
GamePanel.game_started.emit(game_name, pid)    # Signal(str, int)
    └── MainWindow._on_game_started(name, pid)
        └── _lock_ui(name, pid)
            ├── _lock_banner.setVisible(True)
            ├── _splitter.setEnabled(False)
            ├── _toolbar.setEnabled(False)
            ├── menuBar().setEnabled(False)
            └── if pid > 0: _game_poll_timer.start(1000)

_game_poll_timer.timeout → _on_pid_poll():
    └── os.kill(pid, 0) → ProcessLookupError → _unlock_ui()

Lock-Banner "Entsperren"-Button → _unlock_ui():
    ├── _lock_banner.setVisible(False)
    ├── _splitter.setEnabled(True)
    ├── _toolbar.setEnabled(True)
    └── menuBar().setEnabled(True)
```

## Implementierungsplan

### Schritt 1 — game_panel.py: Signal-Signatur ändern
- Zeile 98: `game_started = Signal(str)` → `game_started = Signal(str, int)`
- Zeile 1059 (Direkt): `self.game_started.emit(name, -1)`
- Zeile 1091 (Steam): `self.game_started.emit(name, -1)` (Steam-PID nicht nutzbar)
- Zeile 1163 (Proton): `self.game_started.emit(name, proc.pid)`

### Schritt 2 — mainwindow.py: State-Variablen
```python
self._game_running: bool = False
self._game_pid: int | None = None
self._game_poll_timer = QTimer(self)
self._game_poll_timer.setInterval(1000)
self._game_poll_timer.timeout.connect(self._on_pid_poll)
```

### Schritt 3 — mainwindow.py: Lock-Banner Widget
QFrame mit QHBoxLayout, eingefügt via `main_layout.insertWidget(0, banner)`:
- Links: QLabel "Spiel läuft: {name}"
- Rechts: QPushButton "Entsperren"
- Initial `setVisible(False)`
- KEIN `setStyleSheet()` — QSS-Theme wird vererbt

### Schritt 4 — mainwindow.py: _lock_ui() / _unlock_ui()
Sperren: `_splitter`, `_log_container`, `menuBar()`, `_toolbar` via `setEnabled(False)`
Entsperren: alle wieder `setEnabled(True)`, Banner verstecken, Timer stoppen

**Wichtig:** `centralWidget().setEnabled(False)` wird NICHT verwendet, weil der Lock-Banner selbst im centralWidget sitzt und aktiv bleiben muss.

### Schritt 5 — mainwindow.py: _on_pid_poll()
```python
def _on_pid_poll(self):
    try:
        os.kill(self._game_pid, 0)
    except ProcessLookupError:
        self._unlock_ui()
    except PermissionError:
        pass  # Prozess läuft noch
```

### Schritt 6 — Locale-Keys in alle 7 Dateien

| Sprache | running_label | unlock_button |
|---|---|---|
| de | Spiel läuft: {name} | Entsperren |
| en | Game running: {name} | Unlock |
| es | Juego en ejecución: {name} | Desbloquear |
| fr | Jeu en cours : {name} | Déverrouiller |
| it | Gioco in esecuzione: {name} | Sblocca |
| pt | Jogo a executar: {name} | Desbloquear |
| ru | Игра запущена: {name} | Разблокировать |

## Randfälle

| Szenario | Verhalten |
|---|---|
| Steam-Start | pid=-1, kein Timer, nur manueller Unlock |
| Proton-Start | pid=proc.pid, Timer polt, Auto-Unlock wenn Proton endet |
| Direkt-Start (Non-Steam) | pid=-1, nur manueller Unlock |
| User klickt "Entsperren" | Timer stop, Banner weg, UI frei |
| PermissionError bei os.kill | UI bleibt gesperrt (Prozess läuft noch) |
| Anvil während Lock geschlossen | Normales Beenden, kein spezielles Handling |

## Akzeptanz-Checkliste

- [ ] Lock-Banner erscheint beim Game-Start mit Text "Spiel läuft: [Name]" und "Entsperren"-Button
- [ ] Toolbar ist deaktiviert (ausgegraut) während Lock
- [ ] Menüleiste ist deaktiviert während Lock
- [ ] Splitter (Mod-Liste + Game-Panel) ist deaktiviert während Lock
- [ ] "Entsperren"-Button hebt Lock sofort auf
- [ ] Proton-Start: Auto-Unlock wenn Proton-Prozess beendet (innerhalb 2 Sek)
- [ ] Steam-Start: Nur manueller Unlock
- [ ] Anvil schließt normal während Lock (kein Crash)
- [ ] Kein `setStyleSheet()` im Lock-Banner
- [ ] Locale-Keys in allen 7 Dateien vorhanden
- [ ] BG3-Code unverändert
- [ ] Game-Plugin-Dateien unverändert
- [ ] `python -m py_compile` ohne Fehler
- [ ] `./restart.sh` startet ohne Fehler
