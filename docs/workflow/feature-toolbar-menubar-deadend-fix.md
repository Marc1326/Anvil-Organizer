# Feature: Toolbar/Menüleiste Dead-End verhindern

Datum: 2026-03-02

## Problem

Wenn der User sowohl Toolbar ALS AUCH Menüleiste ausblendet, gibt es keinen
UI-Weg zurück. `closeEvent()` persistiert den hidden-Zustand in QSettings,
sodass beim nächsten Start beide wieder versteckt sind → endloser Kreislauf.

Das bestehende Alt-Key-Handling (`keyPressEvent`, Zeile 573-582) funktioniert
nur eingeschränkt, weil Qt intern Alt-Taste-Events für Menübar-Fokus abfängt
und `keyPressEvent` nicht zuverlässig erreicht wird.

## User Stories

- Als User möchte ich IMMER einen UI-Weg haben, Toolbar oder Menüleiste
  wieder einzublenden, auch wenn ich versehentlich beide ausgeblendet habe.
- Als User möchte ich per Alt-Taste die Menüleiste togglen können,
  unabhängig davon, ob Qt den Alt-Event intern verarbeitet.

## Technische Planung

### Betroffene Dateien

| Datei | Änderung |
|---|---|
| `anvil/mainwindow.py` | Fix B: Sicherheitsnetz in `_restore_view_settings()` |
| `anvil/mainwindow.py` | Fix C: `eventFilter()` um Alt-Key-Recovery erweitern |
| `anvil/mainwindow.py` | `keyPressEvent()` entfernen (ersetzt durch eventFilter) |

### Fix B: Sicherheitsnetz in `_restore_view_settings()` (Zeile 620-652)

**Position:** Nach Zeile 641 (nach dem Restore aller Visibility-Werte)

**Logik:**
```python
# Sicherheitsnetz: Wenn BEIDE versteckt → Menüleiste erzwingen
if not self.menuBar().isVisible() and not self._toolbar.isVisible():
    self.menuBar().setVisible(True)
    if hasattr(self, "_act_menubar"):
        self._act_menubar.setChecked(True)
```

**Warum nach Zeile 641?**
- Erst müssen alle drei Visibility-Werte aus QSettings geladen sein
- Dann prüfen wir den kombinierten Zustand
- Nur wenn BEIDE (menubar + toolbar) hidden → menubar erzwingen
- `_act_menubar` Checkbox wird synchronisiert
- Kein Eingriff wenn mindestens eine Leiste sichtbar ist

### Fix C: Alt-Key-Recovery via eventFilter

**Aktueller Zustand:**
- `keyPressEvent()` (Zeile 573-582) wird für Alt-Toggle verwendet
- `eventFilter()` (Zeile 714-727) behandelt nur ContextMenu-Events
- `installEventFilter(self)` ist bereits in `__init__` (Zeile 296) für die
  App-weite Event-Filterung installiert

**Änderung:**
1. Alt-Key-Handling von `keyPressEvent()` nach `eventFilter()` verschieben
2. `eventFilter()` um `QEvent.Type.KeyRelease` für `Qt.Key.Key_Alt` erweitern
3. `keyPressEvent()` komplett entfernen (wird durch eventFilter ersetzt)

**Warum KeyRelease statt KeyPress?**
- Qt fängt Alt-KeyPress intern ab für Menübar-Fokus
- KeyRelease kommt zuverlässiger durch, auch wenn Qt den KeyPress konsumiert
- Nur reagieren wenn KEIN Modifier gedrückt (also reiner Alt-Tap, nicht Alt+F etc.)

**Logik im eventFilter:**
```python
if event.type() == QEvent.Type.KeyRelease:
    if (event.key() == Qt.Key.Key_Alt
            and not event.isAutoRepeat()
            and event.modifiers() == Qt.KeyboardModifier.NoModifier):
        s = self._settings()
        if s.value("Interface/show_menubar_on_alt", True, type=bool):
            mb = self.menuBar()
            mb.setVisible(not mb.isVisible())
            if hasattr(self, "_act_menubar"):
                self._act_menubar.setChecked(mb.isVisible())
            return True
```

**Warum App-weiter eventFilter statt keyPressEvent?**
- Fängt Alt-Events ab BEVOR Qt sie intern für Menübar-Navigation verarbeitet
- Der App-weite Filter via `QApplication.instance().installEventFilter(self)`
  ist bereits installiert (Zeile 296)
- Funktioniert unabhängig davon, welches Widget den Fokus hat

### Signal-Flow

```
App-Start:
  __init__() → _restore_view_settings()
    → Liest QSettings: view/menubar_visible, view/toolbar_visible
    → WENN beide False → menuBar().setVisible(True) + _act_menubar sync
    → User sieht immer mindestens eine Navigationsleiste

Runtime (Alt-Taste):
  User drückt+löst Alt
    → QApplication eventFilter (KeyRelease)
    → Prüft: Key_Alt, kein AutoRepeat, keine Modifier
    → Prüft: Interface/show_menubar_on_alt Setting (Default: True)
    → menuBar().setVisible(toggle)
    → _act_menubar.setChecked(sync)

Close:
  closeEvent() → _save_ui_state()
    → Speichert aktuellen Zustand (auch wenn beide hidden)
    → Beim nächsten Start greift das Sicherheitsnetz
```

### MO2-Vergleich

MO2 verwendet ebenfalls ein Toolbar-Rechtsklick-Kontextmenü zum Wiederherstellen
versteckter Toolbars. Ein ähnliches Recovery-Menü existiert bereits in Anvil
(`_show_view_recovery_menu`, Zeile 701). MO2 hat kein explizites Sicherheitsnetz
gegen das Ausblenden aller Leisten — wir verbessern hier gegenüber MO2.

## Abhängigkeiten

- Keine externen Abhängigkeiten
- QSettings-Keys bleiben unverändert (`view/menubar_visible`, `view/toolbar_visible`)
- Setting `Interface/show_menubar_on_alt` existiert bereits (Default: True)

## Risiken

- **Gering:** KeyRelease statt KeyPress könnte sich für den User etwas anders
  anfühlen (Toggle passiert beim Loslassen statt beim Drücken). Dies ist aber
  der Standard bei den meisten Anwendungen und zuverlässiger.
- **Keins:** Das Sicherheitsnetz in `_restore_view_settings()` greift nur beim
  Start, nicht während der Laufzeit. User kann weiterhin manuell beide ausblenden
  — beim nächsten Start wird die Menüleiste aber wieder sichtbar.

## ✅ Akzeptanz-Kriterien (ALLE müssen erfüllt sein)

- [ ] 1. Wenn User QSettings manuell auf `view/menubar_visible=false` UND `view/toolbar_visible=false` setzt und App startet, ist die Menüleiste sichtbar
- [ ] 2. Wenn User QSettings auf `view/menubar_visible=false` UND `view/toolbar_visible=true` setzt, bleibt die Menüleiste beim Start versteckt (kein unnötiges Erzwingen)
- [ ] 3. Wenn User QSettings auf `view/menubar_visible=true` UND `view/toolbar_visible=false` setzt, bleibt die Toolbar beim Start versteckt (kein unnötiges Erzwingen)
- [ ] 4. Wenn User Alt drückt und loslässt (kein Modifier), togglet die Menüleiste ihre Sichtbarkeit
- [ ] 5. Wenn User Alt+F drückt (Alt mit anderem Key), passiert KEIN Menubar-Toggle
- [ ] 6. Wenn User `Interface/show_menubar_on_alt` auf False setzt, reagiert Alt-Taste NICHT mehr
- [ ] 7. Die `_act_menubar`-Checkbox im View-Recovery-Menü ist nach Alt-Toggle synchron mit dem tatsächlichen Sichtbarkeitszustand
- [ ] 8. Die `_act_menubar`-Checkbox ist nach dem Sicherheitsnetz-Eingriff beim Start korrekt auf Checked gesetzt
- [ ] 9. Alt-Key-Recovery funktioniert unabhängig davon, welches Widget den Fokus hat (Mod-Liste, Game-Panel, etc.)
- [ ] 10. `keyPressEvent()` Alt-Handling (Zeile 573-582) ist entfernt und durch eventFilter ersetzt
- [ ] 11. Bestehende eventFilter-Funktionalität (ContextMenu für Toolbar, Zeile 719-723) funktioniert weiterhin
- [ ] 12. `python -m py_compile anvil/mainwindow.py` erfolgreich
- [ ] 13. `restart.sh` startet ohne Fehler
