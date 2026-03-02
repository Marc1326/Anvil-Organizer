# QA Agent 2: game_panel.py (Signal, Kontextmenue, Tooltip)
Datum: 2026-03-02

## Gepruefte Kriterien
- [x] 1: Position im Kontextmenue -- KORREKT
- [x] 2: Mehrselektion -- KORREKT
- [x] 3: API-Key Check -- KORREKT
- [x] 5: Dateiname-Parsing + Bestaetigungsdialog -- KORREKT
- [x] 6: QInputDialog Fallback -- KORREKT
- [x] 11: Tooltip -- KORREKT

## Code-Analyse

### Signal-Deklaration
- **Zeile 88**: `dl_query_info_requested = Signal(str)  # archive_path`
- Typ: `Signal(str)` -- korrekt, uebergibt den Archiv-Pfad als String
- Klassen-Level Signal auf `GamePanel(QWidget)` -- korrekt deklariert
- Emission in Zeile 1485: `self.dl_query_info_requested.emit(first)` -- korrekt, `first` ist ein `str`
- Verbindung in mainwindow.py Zeile 285: `self._game_panel.dl_query_info_requested.connect(self._on_dl_query_info)` -- korrekt

### Kontextmenue-Reihenfolge (Zeilen 1422-1473)

Aktuelle Reihenfolge im Code:
```
1. "Installieren"              (act_install, Zeile 1425)
--- Separator ---
2. "Nexus-Seite oeffnen"      (act_nexus, Zeile 1430)
3. "Nexus-Info abrufen"        (act_query, Zeile 1434, NUR bei Einzelselektion)
4. "Oeffne Datei"              (act_open, Zeile 1436)
5. "Oeffne Meta Datei"         (act_meta, Zeile 1437)
--- Separator ---
6. "Zeige im Downloadverzeichnis" (act_show, Zeile 1443)
--- Separator ---
7. "Loeschen..."               (act_delete, Zeile 1448)
8. "Verstecken"/"Einblenden"   (act_hide/act_unhide, Zeile 1451-1454)
--- Separator ---
9-11. Bulk Delete              (Zeile 1459-1461)
--- Separator ---
12-15. Bulk Hide/Unhide        (Zeile 1466-1472)
```

Position "Nexus-Info abrufen" ist KORREKT: Nach "Nexus-Seite oeffnen" (Zeile 1430), vor "Oeffne Datei" (Zeile 1436).

### Kriterium 1: Position im Kontextmenue

**Ergebnis: PASS**

"Nexus-Info abrufen" wird in Zeile 1434 per `menu.addAction()` eingefuegt, direkt nach `act_nexus` (Zeile 1430, "Nexus-Seite oeffnen") und vor `act_open` (Zeile 1436, "Oeffne Datei"). Die Feature-Spec verlangt genau diese Position.

### Kriterium 2: Mehrselektion

**Ergebnis: PASS**

Zeile 1433: `if len(paths) == 1:` -- der Menuepunkt wird NUR bei Einzelselektion hinzugefuegt. Bei Mehrselektion bleibt `act_query = None` (Zeile 1432), und der Menuepunkt ist nicht im Menue sichtbar (nicht disabled, sondern komplett absent). Die Feature-Spec erlaubt "NICHT sichtbar oder disabled", daher ist "nicht sichtbar" akzeptabel.

### Kriterium 3: API-Key Check

**Ergebnis: PASS**

- Zeile 1435: `act_query.setEnabled(self._has_nexus_api_key)` -- Menuepunkt ausgegraut wenn kein API-Key
- Zeile 316: Initialisierung `self._has_nexus_api_key: bool = False` -- Default ist kein Key
- Zeile 1291-1293: `set_nexus_api_available(available)` setzt den Wert
- mainwindow.py Zeile 262: Wird beim Start mit `self._nexus_api.has_api_key()` gesetzt
- Korrekte Kette: Start -> API-Key pruefen -> GamePanel informieren -> Menuepunkt enabled/disabled

### Kriterium 5: Dateiname-Parsing + Bestaetigungsdialog

**Ergebnis: PASS**

mainwindow.py Zeile 2757-2769 implementiert die Fallback-Kette:
1. `.meta` wird geprueft (Zeile 2748-2755) -- wenn modID > 0, direkt verwenden
2. Wenn keine .meta-ID: `extract_nexus_mod_id(filename)` (Zeile 2760)
3. Wenn ID gefunden: `QMessageBox.question()` mit "Aus Dateiname erkannt: Mod-ID {id}. Verwenden?"
4. Bei "Yes" -> ID uebernehmen, bei "No" -> mod_id bleibt 0 -> weiter zu manuellem Dialog

Der Parser in `anvil/core/nexus_filename_parser.py` implementiert den MO2-kompatiblen Regex korrekt:
- Hauptregex: `^(.+?)-(\d{2,})(?:-[\d]+)*-(\d{9,11})\.(?:zip|rar|7z)$`
- Fallback: `re.findall(r'-(\d{2,})-', filename)` fuer Sonderfaelle

### Kriterium 6: QInputDialog Fallback

**Ergebnis: PASS**

mainwindow.py Zeile 2772-2785:
- Wenn `mod_id <= 0` (weder .meta noch Dateiname liefern ID): `get_text_input()` wird aufgerufen
- `get_text_input()` ist ein App-eigener Wrapper um `QInputDialog` (importiert in Zeile 31)
- Validierung: `int(text.strip())` und `mod_id <= 0` -> `ValueError` -> Statusbar Fehlermeldung
- Bei Abbruch (Cancel): `not ok` -> return ohne API-Call

Hinweis: Die Spec sagt "QInputDialog", der Code nutzt `get_text_input()`. Funktional gleichwertig, da `get_text_input()` intern QInputDialog.getText() aufruft.

### Kriterium 11: Tooltip

**Ergebnis: PASS**

mainwindow.py Zeile 3134-3142 (im `_on_nexus_response` Handler fuer `query_mod_info:`):
```python
name = data.get("name", "")
mod_id_val = data.get("mod_id", 0)
version = data.get("version", "")
summary = data.get("summary", "")
tooltip = f"{name} (ID: {mod_id_val}) v{version}"
if summary:
    tooltip += f"\n{summary}"
self._game_panel.update_download_tooltip(dl_path, tooltip)
```

game_panel.py Zeile 1295-1301:
```python
def update_download_tooltip(self, archive_path: str, tooltip: str) -> None:
    for row in range(self._dl_table.rowCount()):
        item = self._dl_table.item(row, 0)
        if item and item.data(Qt.ItemDataRole.UserRole) == archive_path:
            item.setToolTip(tooltip)
            break
```

Format: "ModName (ID: XXXXX) vX.X\nBeschreibung..." -- entspricht der Feature-Spec.

## Befunde

Keine Bugs oder Logikfehler gefunden. Alle 6 geprueften Kriterien sind korrekt implementiert.

### Positive Aspekte:
- Signal-Typ `Signal(str)` korrekt fuer Archiv-Pfad (kein Path-Objekt, konsistent mit bestehender API)
- Fallback-Kette .meta -> Regex -> Dialog sauber implementiert mit korrektem Flow
- Bei "No" im Bestaetigungsdialog: User wird zum manuellen Dialog weitergeleitet (nicht abgebrochen)
- Tooltip wird nur auf Spalte 0 (Name) gesetzt, Zeile via `UserRole`-Daten identifiziert
- `_has_nexus_api_key` korrekt initialisiert als `False` und ueber `set_nexus_api_available()` aktualisiert
- Mehrselektion: Menuepunkt wird nicht angezeigt (nicht nur disabled) -- sauberer Ansatz

### Hinweis (kein Bug, nur Beobachtung):
- `update_download_tooltip()` setzt den Tooltip nur auf Spalte 0 (Name-Item). Wenn der User ueber andere Spalten hovert (z.B. Status, Groesse), wird der Tooltip dort NICHT angezeigt. Das ist konsistent mit MO2-Verhalten (Tooltip nur auf Name-Spalte), daher kein Problem.

## i18n-Pruefung (fuer Kriterien 5 und 6 relevant)

Alle 3 neuen Keys in allen 6 Locale-Dateien vorhanden:
| Key | de | en | es | fr | it | pt |
|-----|----|----|----|----|----|----|
| query_nexus_info | OK | OK | OK | OK | OK | OK |
| query_nexus_enter_id | OK | OK | OK | OK | OK | OK |
| query_nexus_parsed_id | OK | OK | OK | OK | OK | OK |

## Bewertung

**PASS** -- Alle 6 geprueften Akzeptanzkriterien (1, 2, 3, 5, 6, 11) sind korrekt implementiert. Keine Bugs, keine fehlenden Checks, keine Logikfehler. Signal-Deklaration, Kontextmenue-Reihenfolge, Mehrselektion-Guard, API-Key-Check, Fallback-Kette und Tooltip-Mechanismus arbeiten wie in der Feature-Spec beschrieben.

**6/6 Punkte erfuellt.**
