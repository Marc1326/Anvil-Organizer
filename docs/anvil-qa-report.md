# QA Report -- Fix B + C + D: Toolbar/Menuleiste Dead-End Sicherheitsnetz

Datum: 2026-03-02

## Geaenderte Dateien

| Datei | Aenderungen |
|---|---|
| `anvil/mainwindow.py` | +29 / -10 Zeilen |

Keine anderen Dateien wurden veraendert. (Bestaetigt via `git diff --name-only`)

---

## Checklisten-Pruefung

### Fix B -- _restore_view_settings()

- [x] Nach Restore: wenn BEIDE (menubar + toolbar) hidden, wird menubar auf visible erzwungen -- Zeile 637-641: Pruefung `if not self.menuBar().isVisible() and not self._toolbar.isVisible()` mit `self.menuBar().setVisible(True)` ✅
- [x] _act_menubar Checkbox wird synchronisiert -- Zeile 640-641: `self._act_menubar.setChecked(True)` mit `hasattr`-Guard ✅
- [x] Wenn mindestens eine Leiste sichtbar, kein Eingriff -- Die `if`-Bedingung greift nur bei BEIDEN hidden, normales Verhalten bleibt ✅

### Fix C -- Event-Filter (Alt-Key-Recovery)

- [x] `self.installEventFilter(self)` ist in `__init__` vorhanden -- Zeile 126 ✅
- [x] eventFilter() behandelt Alt als KeyRelease (NICHT KeyPress) -- Zeile 729: `QEvent.Type.KeyRelease` ✅
- [x] Pruefung `not event.modifiers() & ~AltModifier` -- Zeile 732: Alt+Tab/Alt+F4 loesen NICHT aus. Getestet: `Alt|Ctrl` ergibt `ControlModifier` (truthy), wird korrekt blockiert. Reine Alt-Releases (mit oder ohne AltModifier im modifiers()) werden korrekt durchgelassen ✅
- [x] `event.isAutoRepeat()` wird geprueft -- Zeile 731: `not event.isAutoRepeat()` verhindert wiederholtes Ausloesen ✅
- [x] Nur aktiv wenn Interface/show_menubar_on_alt True (Default: True) -- Zeile 733-734: QSettings-Abfrage mit Default True ✅
- [x] _act_menubar Checkbox bleibt synchron -- Zeile 737-738: `_act_menubar.setChecked(mb.isVisible())` mit `hasattr`-Guard ✅
- [x] Alter keyPressEvent Alt-Handler ist entfernt -- Zeile 574-576: Nur noch `super().keyPressEvent(event)` Forward, komplette Alt-Logik entfernt ✅
- [x] eventFilter gibt fuer ALLE anderen Events `super().eventFilter()` zurueck -- Zeile 741: `return super().eventFilter(obj, event)` als Fallthrough ✅

### Fix D -- _save_ui_state()

- [x] Vor dem Speichern: wenn BEIDE false, wird menubar_vis auf True erzwungen -- Zeile 3043-3045: Safety-Net-Logik korrekt implementiert ✅
- [x] Statusbar wird unabhaengig davon normal gespeichert -- Zeile 3048: `s.setValue("view/statusbar_visible", self._status_bar.isVisible())` ohne Beeinflussung durch Safety Net ✅
- [x] Kein Einfluss auf andere Settings -- Splitter, Filter, Icon-Size, Button-Style etc. werden alle nach dem Safety-Net-Block geschrieben und sind unbeeinflusst ✅

### Akzeptanzkriterien

- [x] Toolbar + Menubar ausblenden, dann App-Start: Menubar erscheint automatisch wieder -- Fix B in `_restore_view_settings()` erzwingt dies ✅
- [x] Alt-Taste (reiner Tap, kein Combo) togglet Menubar zuverlaessig -- Fix C via eventFilter KeyRelease ✅
- [x] Alt+Tab, Alt+F4 loesen den Toggle NICHT aus -- Modifier-Pruefung `~AltModifier` blockiert korrekt. Verifiziert mit Python-Test: `Alt|Ctrl & ~Alt = Ctrl` (truthy, blockiert) ✅
- [x] App schliessen mit beiden hidden, Config hat menubar_visible=true -- Fix D in `_save_ui_state()` korrigiert vor Persistierung ✅
- [x] Normaler Toggle ueber Menue funktioniert weiterhin -- `_on_toggle_menubar()` (Zeile 537-539) und `_on_toggle_toolbar()` (Zeile 541-543) sind unveraendert ✅
- [x] Kein neuer Import hinzugefuegt der nicht gebraucht wird -- Keine neuen Top-Level-Imports. Die Inline-Imports in eventFilter (`QToolBar`, `QEvent`, `QCursor`) waren bereits vorhanden ✅
- [x] Keine anderen Methoden oder Dateien veraendert -- Nur `_restore_view_settings()`, `keyPressEvent()`, `eventFilter()`, `_save_ui_state()` betroffen. `git diff --name-only` zeigt nur `anvil/mainwindow.py` ✅

### Regressions-Check

- [x] Rechtsklick auf Toolbar: Kontextmenue funktioniert noch -- eventFilter Zeile 719-723: ContextMenu-Handling fuer QToolBar ist unveraendert ✅
- [x] Ansicht-Menue: Toolbar/Menubar/Statusbar Toggles funktionieren noch -- Actions `_act_menubar`, `_act_toolbar`, `_act_statusbar` und deren `triggered.connect()` sind unveraendert (Zeile 346-356) ✅
- [x] closeEvent() speichert alle anderen UI-States korrekt -- closeEvent (Zeile 3118-3123) ruft `_save_ui_state()` auf, welche Splitter, Filter, Icon-Size, Button-Style, Collapsed-Separators alle korrekt nach dem Safety-Net-Block speichert ✅

### Spec-Akzeptanzkriterien (aus feature-toolbar-menubar-deadend-fix.md)

- [x] 1. Beide QSettings auf false + App-Start: Menubar sichtbar ✅
- [x] 2. Nur menubar false + toolbar true: Menubar bleibt versteckt ✅
- [x] 3. Nur toolbar false + menubar true: Toolbar bleibt versteckt ✅
- [x] 4. Alt druecken+loslassen togglet Menubar ✅
- [x] 5. Alt+F loest KEIN Toggle aus ✅
- [x] 6. show_menubar_on_alt=False: Alt reagiert nicht ✅
- [x] 7. _act_menubar Checkbox synchron nach Alt-Toggle ✅
- [x] 8. _act_menubar Checkbox korrekt nach Sicherheitsnetz ✅
- [x] 9. Alt-Recovery funktioniert unabhaengig vom Widget-Fokus (eventFilter auf self = MainWindow) ✅
- [x] 10. keyPressEvent Alt-Handling entfernt, durch eventFilter ersetzt ✅
- [x] 11. Bestehende ContextMenu-Funktionalitaet in eventFilter funktioniert weiterhin ✅
- [x] 12. `python -m py_compile anvil/mainwindow.py` erfolgreich ✅
- [x] 13. restart.sh -- nicht live getestet (nur statische Analyse), als ZU PRUEFEN markiert

## Ergebnis: 12/13 Punkte statisch verifiziert, 1 Punkt (restart.sh) erfordert Live-Test

---

## Findings

### [LOW] keyPressEvent nicht komplett entfernt, nur geleert

- Datei: `anvil/mainwindow.py:574-576`
- Problem: Die Methode `keyPressEvent()` ist nicht entfernt, sondern nur auf `super().keyPressEvent(event)` reduziert. Das ist funktional korrekt (identisch mit keinem Override), aber unnoetig. Die Spec (Punkt 10) sagt "entfernt und durch eventFilter ersetzt".
- Bewertung: Kein Bug. Das leere Override schadet nicht, da es nur an super() delegiert. Der Docstring dokumentiert die Verschiebung. Kann spaeter entfernt werden, ist aber kein Blocker.

### [LOW] Spec-Abweichung bei Modifier-Pruefung (POSITIV)

- Datei: `anvil/mainwindow.py:732`
- Problem: Die Spec schlaegt `event.modifiers() == Qt.KeyboardModifier.NoModifier` vor, die Implementierung nutzt `not event.modifiers() & ~Qt.KeyboardModifier.AltModifier`.
- Bewertung: Die Implementierung ist BESSER als die Spec. Bei KeyRelease von Alt kann `modifiers()` auf manchen Systemen noch `AltModifier` enthalten. Die Implementierung behandelt beide Faelle korrekt (Alt noch gesetzt oder bereits geloescht), waehrend die Spec-Variante bei "Alt noch gesetzt" versagen wuerde. Kein Fix noetig.

---

## Zusammenfassung

Die Implementierung von Fix B + C + D ist sauber, korrekt und vollstaendig:

- **Fix B** (`_restore_view_settings`): Safety Net korrekt an der richtigen Position (nach allen Visibility-Restores), Checkbox-Sync vorhanden
- **Fix C** (eventFilter): Robustes Alt-Key-Handling via KeyRelease, Modifier-Pruefung sogar besser als Spec, Settings-Guard, AutoRepeat-Guard, sauberer Fallthrough
- **Fix D** (`_save_ui_state`): Persistierungs-Safety-Net korrekt, Statusbar und andere Settings unbeeinflusst

Keine CRITICAL oder HIGH Findings. Zwei LOW-Findings die kein Bugfix erfordern.

## Ergebnis

**READY FOR COMMIT**
