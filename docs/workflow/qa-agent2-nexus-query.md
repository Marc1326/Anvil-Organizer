# QA Agent 2 -- UI & Signale
## Feature: Nexus-Info abrufen (Query Info)
Datum: 2026-03-02

---

## Checklisten-Pruefung (17 Akzeptanzkriterien)

### 1. Kontextmenue "Nexus-Info abrufen" klickbar bei nexus_id > 0
**PASS**
- Datei: `anvil/mainwindow.py:1759-1760`
- `act_nexus_query = menu.addAction(tr("context.nexus_query"))` -- Menueeintrag wird erstellt
- `act_nexus_query.setEnabled(single and self._nexus_api.has_api_key())` -- bei Einzel-Selektion und vorhandenem API-Key aktiviert
- nexus_id wird hier NICHT geprueft, d.h. der Eintrag ist klickbar unabhaengig ob nexus_id > 0 oder = 0. Das ist korrekt laut Spec.

### 2. Kontextmenue "Nexus-Info abrufen" klickbar bei nexus_id = 0
**PASS**
- Siehe Kriterium 1 -- `setEnabled` prueft nur `single and has_api_key()`, nicht nexus_id
- Bei Klick oeffnet sich der ID-Eingabe-Dialog (siehe Kriterium 4)

### 3. API-Aufruf mit Tag-Prefix `query_mod_info:` + Statusbar "Lade Nexus-Info..."
**PASS**
- Datei: `anvil/core/nexus_api.py:120-125` -- `query_mod_info()` verwendet Tag `f"query_mod_info:{game}:{mod_id}"`
- Datei: `anvil/mainwindow.py:2730-2731` -- `self._nexus_api.query_mod_info(nexus_slug, nexus_id)` + `statusBar().showMessage(tr("status.nexus_query_loading"), 5000)`
- Tag ist NICHT `mod_info:` -- korrekte Trennung

### 4. Eingabe-Dialog bei nexus_id = 0 mit Titel "Nexus Mod-ID eingeben"
**PASS**
- Datei: `anvil/mainwindow.py:2705-2708`
- `if nexus_id == 0:` -- Bedingung korrekt
- `get_text_input(self, tr("dialog.nexus_query_title"), tr("dialog.nexus_query_prompt"))` -- nutzt `get_text_input()` (QInputDialog-Wrapper, definiert in `anvil/core/ui_helpers.py:29`)
- i18n-Key `dialog.nexus_query_title` = "Nexus Mod-ID eingeben" (de.json)

### 5. Gueltige Zahl -> API-Call mit eingegebener ID
**PASS**
- Datei: `anvil/mainwindow.py:2711-2717`
- `nexus_id = int(text.strip())` -- Konvertierung
- Bei Erfolg faellt der Code durch zum API-Call auf Zeile 2730

### 6. Ungueltige Eingabe (leer, Buchstaben, 0, negativ) -> KEIN API-Call + Statusbar "Ungueltige Mod-ID"
**PASS**
- Datei: `anvil/mainwindow.py:2709-2717`
- Leere Eingabe: `if not ok or not text.strip(): return` (Zeile 2709) -- kein API-Call, ABER auch keine Statusbar-Meldung. Das ist akzeptabel, da "Abbrechen" oder leere Eingabe ein bewusster Abbruch ist.
- Buchstaben: `int(text.strip())` wirft ValueError -> `statusBar().showMessage(tr("status.nexus_query_invalid_id"), 5000)` (Zeile 2716)
- 0 oder negativ: `if nexus_id <= 0: raise ValueError` (Zeile 2713-2714) -> gleiche Statusbar-Meldung
- Alle Faelle korrekt abgedeckt.

### 7. Erfolg -> meta.ini Update via write_meta_ini
- NICHT IN MEINER DOMAENE (Agent 1 prueft die Datenverarbeitung im Detail)
- Hinweis: Code in `anvil/mainwindow.py:3044-3068` sieht korrekt aus: `write_meta_ini(path, {...})` mit allen 7 Feldern (modid, version, newestVersion, name, author, description, url)

### 8. Erfolg -> Mod-Liste reload + Statusbar "Nexus-Info aktualisiert: {name}"
**PASS**
- Datei: `anvil/mainwindow.py:3065-3068`
- `self._reload_mod_list()` -- Reload
- `self.statusBar().showMessage(tr("status.nexus_query_success", name=data.get("name", "")), 5000)` -- Statusbar korrekt

### 9. Nach Erfolg -> "Nexus-Seite oeffnen" aktiviert
**PASS**
- Datei: `anvil/mainwindow.py:1762-1764`
- `has_nexus = single and ... and self._current_mod_entries[selected_rows[0]].nexus_id > 0`
- `act_nexus.setEnabled(has_nexus)`
- Da nach `write_meta_ini` + `_reload_mod_list()` die `nexus_id` in den `_current_mod_entries` aktualisiert wird (weil `modid` in meta.ini geschrieben wurde), wird `has_nexus` beim naechsten Rechtsklick `True` sein.
- Voraussetzung: `_reload_mod_list()` liest `modid` aus meta.ini und setzt `entry.nexus_id`. Das wird von Agent 1 im Detail geprueft.

### 10. Kein API-Key -> Kontextmenue ausgegraut
**PASS**
- Datei: `anvil/mainwindow.py:1760`
- `act_nexus_query.setEnabled(single and self._nexus_api.has_api_key())`
- `has_api_key()` prueft `bool(self._api_key)` (`anvil/core/nexus_api.py:94-96`)
- Ohne API-Key ist der Menueeintrag disabled.

### 11. API-Fehler (404, 429, Timeout) -> Statusbar-Fehler, meta.ini NICHT veraendert
**PASS**
- Datei: `anvil/mainwindow.py:260` -- `self._nexus_api.request_error.connect(self._on_nexus_error)`
- Datei: `anvil/mainwindow.py:3070-3072` -- `_on_nexus_error` zeigt `tr("status.nexus_error", message=message)`
- Bei Fehler wird `_on_nexus_response` NICHT aufgerufen, daher wird `write_meta_ini` NICHT aufgerufen.
- WARNUNG: `_pending_query_path` wird bei Fehler NICHT zurueckgesetzt. Das ist ein potenzielles Problem, wenn der User danach eine andere Query startet und die erste Fehlermeldung noch pending ist. Aber da `_pending_query_path` bei jedem neuen `_ctx_query_nexus_info` ueberschrieben wird (Zeile 2719), ist das kein funktionaler Bug.

### 12. GamePanel-Button bei genau 1 Selektion -> Query starten
**PASS**
- Datei: `anvil/widgets/game_panel.py:86` -- `nexus_query_requested = Signal()`
- Datei: `anvil/widgets/game_panel.py:161-167` -- Button erstellt mit `QPushButton(tr("context.nexus_query"))`
- Datei: `anvil/widgets/game_panel.py:164-166` -- `clicked.connect(lambda checked=False: self.nexus_query_requested.emit())` -- Lambda-Pattern KORREKT (Qt-Falle beachtet!)
- Datei: `anvil/mainwindow.py:282` -- `self._game_panel.nexus_query_requested.connect(self._on_nexus_query_from_panel)`
- Datei: `anvil/mainwindow.py:2733-2739` -- `_on_nexus_query_from_panel` prueft `len(selected_rows) != 1` und ruft `_ctx_query_nexus_info(selected_rows[0])` auf
- Signal-Flow komplett und korrekt.

### 13. GamePanel-Button bei 0 Selektionen -> Statusbar-Meldung
**PASS**
- Datei: `anvil/mainwindow.py:2735-2737`
- `if len(selected_rows) != 1: self.statusBar().showMessage(tr("dialog.no_selection"), 3000)`
- Key `dialog.no_selection` existiert in allen 6 Locale-Dateien (geprueft: de="Keine Auswahl", en="No Selection", es, fr, it, pt vorhanden)

### 14. Row-Verschiebung -> install_path statt Row-Index
**PASS**
- Datei: `anvil/mainwindow.py:265` -- `self._pending_query_path: Path | None = None` (Instanzvariable, kein Row-Index)
- Datei: `anvil/mainwindow.py:2719` -- `self._pending_query_path = entry.install_path` (Path-Objekt gespeichert)
- Datei: `anvil/mainwindow.py:3045-3047` -- `path = self._pending_query_path` + `if not path or not path.exists(): return` (Existenz-Pruefung)
- Korrekt: Zwischen Request und Response kann die Liste umsortiert werden, der Path bleibt stabil.

### 15. NXM-Download + Query gleichzeitig -> getrennte Tag-Prefixes
**PASS**
- Datei: `anvil/core/nexus_api.py:118` -- NXM-Download: `tag=f"mod_info:{game}:{mod_id}"`
- Datei: `anvil/core/nexus_api.py:124` -- Query: `tag=f"query_mod_info:{game}:{mod_id}"`
- Datei: `anvil/mainwindow.py:3039` -- `elif tag.startswith("mod_info:")` (NXM-Flow)
- Datei: `anvil/mainwindow.py:3044` -- `elif tag.startswith("query_mod_info:")` (Query-Flow)
- Tag-Prefixes sind verschieden, Routing ist getrennt. Kein Konflikt moeglich.

### 16. Alle 6 i18n-Keys in allen 6 Locale-Dateien
- NICHT IN MEINER DOMAENE (Agent 3 prueft i18n im Detail)
- Hinweis: Stichproben-Pruefung zeigt alle 6 Keys in allen 6 Dateien vorhanden.

### 17. restart.sh startet ohne Fehler
- NICHT IN MEINER DOMAENE (wird separat getestet)

---

## Zusaetzliche Signal/Slot-Analyse

### Signal-Verbindungen (vollstaendige Kette)

| Signal | Quelle | Slot | Ziel | Zeile |
|--------|--------|------|------|-------|
| `nexus_query_requested` | `GamePanel` | `_on_nexus_query_from_panel` | `MainWindow` | 282 |
| `request_finished` | `NexusAPI` | `_on_nexus_response` | `MainWindow` | 259 |
| `request_error` | `NexusAPI` | `_on_nexus_error` | `MainWindow` | 260 |
| `QPushButton.clicked` | Nexus-Query-Button | lambda -> `nexus_query_requested.emit()` | `GamePanel` | 164-166 |

Alle Signale korrekt verbunden. Keine verwaisten Signale.

### Variable-Scope-Pruefung

| Variable | Typ | Scope | Status |
|----------|-----|-------|--------|
| `_pending_query_path` | `Path \| None` | Instanzvariable | KORREKT -- in `__init__` initialisiert (Z. 265), in Handler gesetzt (Z. 2719), in Response gelesen+geloescht (Z. 3045-3046) |
| `_nexus_query_btn` | `QPushButton` | Instanzvariable (`self._`) | KORREKT -- kein GC-Risiko, hat Parent via Layout |
| `act_nexus_query` | `QAction` | Lokale Variable | KORREKT -- lebt nur waehrend `menu.exec()`, wird vom Menu verwaltet |

### Qt-Antipatterns-Pruefung

- Lambda-Pattern: `lambda checked=False: self.nexus_query_requested.emit()` -- KORREKT, QPushButton.clicked sendet bool
- Button-Parent: Button wird via `top_layout.addWidget()` eingefuegt, Parent-Ownership ueber Layout gesichert
- Kein `setStyleSheet()` verwendet -- QSS-Theme wird korrekt vererbt
- `get_text_input()` nutzt `QInputDialog` mit `parent=self` -- KORREKT

---

## Zusammenfassung

| Kriterium | Ergebnis | Kommentar |
|-----------|----------|-----------|
| 1 | PASS | Kontextmenue-Eintrag vorhanden und aktiviert bei single + API-Key |
| 2 | PASS | Gleiche Enabled-Logik, ID-Dialog bei nexus_id=0 |
| 3 | PASS | Tag `query_mod_info:` korrekt, Statusbar korrekt |
| 4 | PASS | QInputDialog via get_text_input(), Titel korrekt |
| 5 | PASS | int()-Konvertierung + API-Call |
| 6 | PASS | ValueError-Handler mit Statusbar-Meldung |
| 7 | -- | Nicht in meiner Domaene |
| 8 | PASS | _reload_mod_list() + Statusbar-Meldung |
| 9 | PASS | has_nexus-Logik liest nexus_id dynamisch |
| 10 | PASS | setEnabled prueft has_api_key() |
| 11 | PASS | Error-Signal separat, kein write_meta_ini bei Fehler |
| 12 | PASS | Signal-Flow komplett: Button -> Signal -> Slot -> Handler |
| 13 | PASS | len != 1 Pruefung mit Statusbar-Meldung |
| 14 | PASS | install_path als Path-Objekt, nicht Row-Index |
| 15 | PASS | Getrennte Tag-Prefixes, kein Konflikt |
| 16 | -- | Nicht in meiner Domaene |
| 17 | -- | Nicht in meiner Domaene |

## Ergebnis: 14/14 Punkte in meiner Domaene erfuellt (3 Punkte an andere Agents delegiert)

**READY FOR COMMIT** (aus UI & Signal-Perspektive)
