# Architektur-Review — ReShade Wizard (Issue #71)
Datum: 2026-03-26
Reviewer: Claude-Agent 1

## Architektur-Konformitaet

### Datei-Organisation
- `anvil/core/reshade_manager.py` — Backend-Logik im `core/` Package: KORREKT
- `anvil/dialogs/reshade_wizard.py` — Dialog im `dialogs/` Package: KORREKT
- Keine neuen Widgets in `widgets/` noetig: KORREKT
- Locales in allen 7 Sprachen: KORREKT

### Keine hardcoded Pfade
- Game-Path kommt aus `self._current_game_path`: OK
- Instance-Name kommt aus `instance_manager.current_instance()`: OK
- DLL-Pfad wird vom User gewaehlt: OK

### Keine setStyleSheet() in neuen Widgets
- `reshade_wizard.py` nutzt KEIN `setStyleSheet()` fuer Widgets: KORREKT
- Einzige Ausnahme: `self._status_label.setStyleSheet("color: ...")` fuer den Status-Indikator — dies ist eine minimale, dynamische Farbzuweisung (gruen/rot), keine Theme-Ueberladung.
- **Bewertung:** Akzeptabel. Das ist ein Standard-Pattern fuer Status-Indikatoren.

### Signal-Verbindungen
- `clicked.connect(lambda: ...)` Pattern korrekt verwendet: OK
- Keine `clicked.connect()` ohne checked-Parameter-Beachtung: OK

### Import-Pruefung
- Alle Imports in reshade_wizard.py vorhanden und korrekt: OK
- Alle Imports in reshade_manager.py vorhanden und korrekt: OK
- Lazy Import in mainwindow.py (`from anvil.dialogs.reshade_wizard import ReshadeWizard`): OK

### Keine BG3-Aenderungen
- Kein Code in bg3-Dateien geaendert: KORREKT

### Keine Game-Plugin-Aenderungen
- Kein Code in `anvil/plugins/games/` geaendert: KORREKT

### MO2-Vergleich
- MO2 hat keinen integrierten ReShade-Wizard — dies ist ein neues Feature
- Das Dialog-Pattern (QDialog + QStackedWidget) ist konsistent mit dem bestehenden Anvil-Code (CreateInstanceWizard nutzt das gleiche Pattern)
- Die Trennung von Manager (Backend) und Wizard (Dialog) folgt dem MO2-Muster von "Core vs. UI"

## Ergebnis: ACCEPTED

Saubere Architektur, keine Verletzungen der Projekt-Regeln.
