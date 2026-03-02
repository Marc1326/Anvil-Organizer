# QA Agent 3 — Signal-Flow + Race Conditions
Datum: 2026-03-02

## Geprueft

- `anvil/widgets/game_panel.py` — Signale, Guard, Launch-Methoden
- `anvil/mainwindow.py` — Signal-Connection, _pre_launch_deploy, _on_start_game, Timer-Stops

---

## Checkliste

### [x] 1. Flow Steam: _on_start_clicked -> emit pre_launch_deploy -> _pre_launch_deploy (synchron) -> _launch_via_steam ✅

**Analyse:**
- `game_panel.py` Zeile 765: `self.pre_launch_deploy.emit()` wird aufgerufen
- `game_panel.py` Zeile 781: `self._launch_via_steam(plugin)` wird aufgerufen
- Der emit (Z.765) steht VOR der Steam-Erkennung (Z.768-774) und VOR `_launch_via_steam` (Z.781)
- `mainwindow.py` Zeile 281-283: Signal ist mit `_pre_launch_deploy` verbunden
- `mainwindow.py` Zeile 1119-1127: `_pre_launch_deploy()` fuehrt `silent_purge()` + `silent_deploy()` aus
- Die Connection ist `AutoConnection` (kein expliziter Typ ausser UniqueConnection) — da Sender (GamePanel) und Empfaenger (MainWindow) im gleichen Thread sind, ist es effektiv `DirectConnection` = synchron
- Kein Code-Pfad wo `_launch_via_steam` OHNE vorheriges `pre_launch_deploy.emit()` aufgerufen wird

**Ergebnis:** Korrekt. emit in Z.765, _launch_via_steam in Z.781. Deploy laeuft synchron davor.

---

### [x] 2. Flow Proton: _on_start_clicked -> emit pre_launch_deploy -> _pre_launch_deploy (synchron) -> _launch_via_proton ✅

**Analyse:**
- `game_panel.py` Zeile 765: `self.pre_launch_deploy.emit()` — identischer emit-Punkt fuer alle Pfade
- `game_panel.py` Zeile 783: `self._launch_via_proton(plugin, binary)` wird aufgerufen
- Selbe Logik wie Flow 1: emit steht vor der Branching-Logik (is_steam/is_main_binary)
- Kein Code-Pfad wo `_launch_via_proton` OHNE vorheriges emit aufgerufen wird

**Ergebnis:** Korrekt. emit in Z.765, _launch_via_proton in Z.783. Deploy laeuft synchron davor.

---

### [x] 3. Flow Direkt: _on_start_clicked -> emit pre_launch_deploy -> _pre_launch_deploy (synchron) -> start_requested.emit -> _on_start_game (NUR Launch) ✅

**Analyse:**
- `game_panel.py` Zeile 765: `self.pre_launch_deploy.emit()` — vor Branching
- `game_panel.py` Zeile 804: `self.start_requested.emit(str(binary_path), working_dir)` — am Ende des else-Zweigs (wenn NICHT Steam)
- `mainwindow.py` Zeile 280: `self._game_panel.start_requested.connect(self._on_start_game)`
- Reihenfolge: pre_launch_deploy.emit() (Z.765) -> synchron: _pre_launch_deploy() -> dann: start_requested.emit() (Z.804) -> synchron: _on_start_game()
- `_on_start_game` macht KEINEN eigenen Deploy (siehe Punkt 4)

**Ergebnis:** Korrekt. emit in Z.765, start_requested.emit in Z.804. _pre_launch_deploy laeuft komplett vor _on_start_game.

---

### [x] 4. Kein Doppel-Deploy bei Direkt-Launch ✅

**Analyse:**
- `mainwindow.py` Zeile 1229-1241: `_on_start_game()` macht NUR:
  - `QProcess.startDetached(binary_path, [], working_dir)` (Z.1232)
  - Status-Message oder Warning-Dialog
- Kein Aufruf von `silent_purge()`, `silent_deploy()`, `_pre_launch_deploy()` oder aehnlichem in `_on_start_game()`
- Der Docstring bestaetigt: "deploy already done via pre_launch_deploy" (Z.1230)
- Deploy passiert ausschliesslich in `_pre_launch_deploy()` (Z.1119-1127)

**Ergebnis:** Korrekt. Kein Doppel-Deploy. _on_start_game macht NUR den Prozessstart.

---

### [x] 5. Guard verhindert Re-Entry auch wenn Qt Events puffert waehrend BA2 blockiert ✅

**Analyse:**
- `game_panel.py` Zeile 750: `if self._is_launching: return` — ERSTE Aktion in _on_start_clicked
- `game_panel.py` Zeile 752: `self._is_launching = True` — ZWEITE Aktion, VOR dem emit
- `game_panel.py` Zeile 753: `self._start_btn.setEnabled(False)` — Button wird deaktiviert
- Reihenfolge: Guard-Check (Z.750) -> Flag setzen (Z.752) -> Button deaktivieren (Z.753) -> try-Block (Z.754) -> emit (Z.765) -> Launch -> finally (Z.805-807)
- Wenn Qt Events puffert waehrend BA2 blockiert (in _pre_launch_deploy -> silent_deploy -> BA2Packer.run): Bei Wiederaufnahme der Event-Verarbeitung wird _on_start_clicked erneut aufgerufen, aber `_is_launching == True` -> sofortiges return
- Zusaetzlich: Button ist disabled -> Click-Event wird von Qt gar nicht erst generiert (doppelte Absicherung)

**Ergebnis:** Korrekt. Guard ist erste Aktion, Flag wird vor emit gesetzt. Doppelte Absicherung durch disabled Button.

---

### [x] 6. Redeploy-Timer wird bei JEDEM Launch-Pfad gestoppt (in _pre_launch_deploy) ✅

**Analyse:**
- `mainwindow.py` Zeile 1121: `self._redeploy_timer.stop()` — ERSTE Aktion in `_pre_launch_deploy()`
- `pre_launch_deploy.emit()` wird in `game_panel.py` Z.765 VOR allen drei Launch-Pfaden aufgerufen
- Da das emit vor dem Branching (Steam/Proton/Direkt) steht, wird `_pre_launch_deploy()` und damit `_redeploy_timer.stop()` bei JEDEM Launch-Pfad ausgefuehrt
- Weitere Timer-Stops existieren korrekt bei:
  - Instanz-Wechsel: Z.827
  - Profil-Wechsel: Z.2271
  - App-Close: Z.3126
  - _do_redeploy selbst: Z.1110

**Ergebnis:** Korrekt. Timer wird in _pre_launch_deploy (Z.1121) gestoppt. Da emit vor allen 3 Pfaden steht, wird Timer bei jedem Launch gestoppt.

---

### [x] 7. UniqueConnection verhindert doppelte Signal-Verbindung ✅

**Analyse:**
- `mainwindow.py` Zeile 281-284:
  ```python
  self._game_panel.pre_launch_deploy.connect(
      self._pre_launch_deploy,
      Qt.ConnectionType.UniqueConnection,
  )
  ```
- `Qt.ConnectionType.UniqueConnection` ist korrekt angegeben
- Wenn durch einen Bug `connect()` mehrfach aufgerufen wuerde, wuerde Qt bei UniqueConnection eine RuntimeError werfen (oder den zweiten connect ignorieren, je nach Qt-Version)
- Das `start_requested` Signal (Z.280) hat KEIN UniqueConnection — das ist akzeptabel, da es nur einmal im __init__ verbunden wird und _on_start_game keinen Deploy macht (kein Risiko)

**Ergebnis:** Korrekt. UniqueConnection bei pre_launch_deploy.connect() vorhanden.

---

### [x] 8. finally-Block: Button wird nach Launch re-enabled — kein Edge-Case wo finally VOR Deploy-Ende laeuft ✅

**Analyse:**
- `game_panel.py` Zeile 805-807:
  ```python
  finally:
      self._is_launching = False
      self._start_btn.setEnabled(True)
  ```
- `pre_launch_deploy.emit()` (Z.765) ist synchron (AutoConnection bei gleichem Thread = DirectConnection)
- Das bedeutet: `_pre_launch_deploy()` in MainWindow laeuft KOMPLETT durch (inkl. silent_purge + silent_deploy + BA2-Packing) BEVOR `emit()` zurueckkehrt
- Erst NACH dem emit() kehrt der Code zurueck zu Z.767 (plugin = ...) und dann weiter zu Launch oder start_requested.emit()
- Der finally-Block (Z.805-807) laeuft NACH allen diesen Schritten
- Reihenfolge: emit() -> _pre_launch_deploy() komplett -> emit() kehrt zurueck -> Launch -> finally

**Moegliche Edge-Cases:**
1. **Early return in try-Block (Z.756-757, Z.761-762):** Wenn `idx < 0` oder `binary` leer ist, wird `return` ausgefuehrt BEVOR emit() aufgerufen wird. Das ist korrekt — kein Deploy wenn nichts gestartet werden soll, und finally raeument trotzdem auf.
2. **Exception in _pre_launch_deploy:** Wenn silent_purge() oder silent_deploy() eine Exception werfen, propagiert diese durch emit() -> except oder finally faengt sie auf. Der finally-Block garantiert Button-Re-Enable.
3. **QMessageBox.warning in Launch-Methoden (Z.814-818, Z.844-848):** Diese sind modal und blockieren, aber der finally-Block laeuft trotzdem korrekt nach dem return aus _launch_via_steam/_launch_via_proton.

**Ergebnis:** Korrekt. emit() ist synchron, Deploy ist komplett bevor finally laeuft. Button wird in allen Pfaden (Success + Error + Exception) re-enabled.

---

## Zusammenfassung

| Nr. | Kriterium | Status |
|-----|-----------|--------|
| 1 | Flow Steam | ✅ |
| 2 | Flow Proton | ✅ |
| 3 | Flow Direkt | ✅ |
| 4 | Kein Doppel-Deploy | ✅ |
| 5 | Guard verhindert Re-Entry | ✅ |
| 6 | Redeploy-Timer bei jedem Launch gestoppt | ✅ |
| 7 | UniqueConnection | ✅ |
| 8 | finally-Block Timing | ✅ |

## Ergebnis: 8/8 Punkte erfuellt

Alle Signal-Flows sind korrekt implementiert. Keine Race Conditions gefunden.
Die Implementierung entspricht exakt der Spec v2.

READY FOR COMMIT (aus Signal-Flow/Race-Condition-Sicht)
