# QA Agent 1 — Code-Korrektheit game_panel.py
Datum: 2026-03-02

Geprueft: `anvil/widgets/game_panel.py` (Working-Tree mit unstaged Changes)
Spec: `docs/specs/critical-bugfix-pre-launch-deploy-v2.md`

---

## Checkliste

### 1. `pre_launch_deploy = Signal()` existiert in Klasse GamePanel (als Klassenattribut)

- [x] **ERFUELLT** — Zeile 87:
  ```python
  pre_launch_deploy = Signal()       # emitted before ANY launch path
  ```
  Korrekt als Klassenattribut deklariert, direkt nach `start_requested`.
  Import von `Signal` aus `PySide6.QtCore` ist in Zeile 34 vorhanden.

---

### 2. `self._is_launching = False` in `__init__`

- [x] **ERFUELLT** — Zeile 91:
  ```python
  self._is_launching = False
  ```
  Korrekt als erste Zeile nach `super().__init__(parent)` in `__init__` (Zeile 89-91).

---

### 3. `_on_start_clicked`: Guard `if self._is_launching: return` am Anfang der Methode

- [x] **ERFUELLT** — Zeile 750-751:
  ```python
  if self._is_launching:
      return
  ```
  Erste Anweisung im Methoden-Body nach dem Docstring.

---

### 4. `_on_start_clicked`: `self._is_launching = True` + `self._start_btn.setEnabled(False)`

- [x] **ERFUELLT** — Zeile 752-753:
  ```python
  self._is_launching = True
  self._start_btn.setEnabled(False)
  ```
  Direkt nach dem Guard, VOR dem try-Block. Korrekte Reihenfolge: Flag setzen, Button deaktivieren, dann try.

---

### 5. `_on_start_clicked`: `pre_launch_deploy.emit()` VOR allen 3 Launch-Pfaden

- [x] **ERFUELLT** — Zeile 764-765:
  ```python
  # Pre-launch deploy for ALL launch paths
  self.pre_launch_deploy.emit()
  ```
  Positioniert NACH der Binary-Validierung (idx-Check, binary-Check) aber VOR der Steam/Proton/Direkt-Verzweigung.
  Das bedeutet:
  - Steam-Launch (Zeile 781): emit passiert vorher
  - Proton-Launch (Zeile 783): emit passiert vorher
  - Direkt-Launch via `start_requested.emit()` (Zeile 804): emit passiert vorher

  Alle 3 Pfade werden abgedeckt.

---

### 6. `_on_start_clicked`: try/finally Block — `_is_launching = False` + Button re-enabled im finally

- [x] **ERFUELLT** — Zeile 754 (try) und Zeile 805-807 (finally):
  ```python
  try:
      idx = self._selected_exe_index
      # ... gesamte Launch-Logik ...
  finally:
      self._is_launching = False
      self._start_btn.setEnabled(True)
  ```
  Der finally-Block wird in JEDEM Fall ausgefuehrt:
  - Bei normalem Durchlauf
  - Bei fruehen `return`-Statements (idx invalid, binary leer, game_path None, binary_path nicht existent)
  - Bei Exceptions
  
  Korrekt: Flag wird zurueckgesetzt UND Button wird re-enabled.

---

### 7. `silent_purge`: `skip_ba2: bool = False` als keyword-only Parameter (mit `*`)

- [x] **ERFUELLT** — Zeile 628:
  ```python
  def silent_purge(self, *, skip_ba2: bool = False) -> None:
  ```
  Das `*` erzwingt keyword-only Nutzung. `skip_ba2=True` muss explizit als
  `silent_purge(skip_ba2=True)` aufgerufen werden. Default ist `False` (voller Cleanup).

---

### 8. `silent_purge`: `if skip_ba2: return` VOR BA2-Cleanup Code

- [x] **ERFUELLT** — Zeile 638-639:
  ```python
  if skip_ba2:
      return
  ```
  Positioniert NACH `self._deployer.purge()` (Zeile 635-636) und VOR dem BA2-Cleanup-Block (Zeile 641ff).
  Das heisst: Symlink-Purge passiert IMMER, aber BA2-Cleanup + plugins.txt-Removal werden
  uebersprungen wenn `skip_ba2=True`. Exakt wie in der Spec verlangt.

---

### 9. `silent_purge`: restlicher Code (BA2-Cleanup, plugins.txt) unveraendert gegenueber dem Original

- [x] **ERFUELLT** — Vergleich des git diff zeigt:
  
  **Original (committed):**
  ```python
  def silent_purge(self) -> None:
      """Purge deployed mods silently.  Called automatically by MainWindow."""
      if self._deployer:
          self._deployer.purge()
      # BA2-Cleanup for Bethesda games
      needs_ba2 = getattr(self._current_plugin, "NeedsBa2Packing", False)
      ...
  ```
  
  **Neu (working tree):**
  ```python
  def silent_purge(self, *, skip_ba2: bool = False) -> None:
      """Purge deployed mods silently.  Called automatically by MainWindow.
      Args:
          skip_ba2: If True, skip BA2 cleanup ...
      """
      if self._deployer:
          self._deployer.purge()
      if skip_ba2:
          return
      # BA2-Cleanup for Bethesda games
      needs_ba2 = getattr(self._current_plugin, "NeedsBa2Packing", False)
      ...
  ```
  
  Aenderungen:
  1. Signatur erweitert um `*, skip_ba2: bool = False` — gewollt
  2. Docstring erweitert um Args-Sektion — gewollt
  3. `if skip_ba2: return` eingefuegt — gewollt
  4. Restlicher Code (BA2-Cleanup ab Zeile 641, plugins.txt-Removal ab Zeile 654) — **IDENTISCH zum Original**. Keine Zeile geaendert.

---

## Zusaetzliche Beobachtungen (kein Checklisten-Punkt, aber relevant)

### Fruehe Returns im try-Block
Die Methode `_on_start_clicked` hat mehrere `return`-Statements innerhalb des try-Blocks
(Zeile 757, 762, 784, 793, 801). Da der finally-Block Python-seitig IMMER ausgefuehrt wird —
auch bei `return` — ist das korrekt. Flag und Button werden in jedem Fall zurueckgesetzt.

### Emit-Position bei fruehen Returns
Wenn `idx < 0` oder `binary` leer ist, wird `return` VOR `pre_launch_deploy.emit()` aufgerufen.
Das ist korrekt — in diesen Faellen gibt es nichts zu deployen, weil auch kein Spiel gestartet wird.

---

## Ergebnis: 9/9 Punkte erfuellt

Alle Aenderungen in `anvil/widgets/game_panel.py` entsprechen exakt der Spec v2.
Keine Abweichungen, keine fehlenden Teile, keine ungewollten Nebeneffekte.
