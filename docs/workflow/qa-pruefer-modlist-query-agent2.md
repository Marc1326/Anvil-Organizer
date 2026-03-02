# QA Report -- Flow-Analyse Nexus-Info-Abruf aus Mod-Liste
Datum: 2026-03-02

## Zusammenfassung

Vollstaendiger Flow-Trace des Nexus-Info-Abrufs von Rechtsklick im Mod-Listen-Kontextmenue bis zur API-Response-Verarbeitung. Die Implementierung ist **funktional korrekt** fuer den Hauptpfad (Mod-Liste Rechtsklick). Es gibt jedoch eine **Race-Condition** beim Response-Routing und ein **schwaches Matching** bei der Archiv-Suche.

---

## Flow-Trace: Kontextmenue -> API-Call -> Response

### Schritt 1: Kontextmenue-Aufbau (mainwindow.py)

**Datei:** `anvil/mainwindow.py:1535` -- `_on_mod_context_menu()`

```
Zeile 1762: act_nexus_query = menu.addAction(tr("context.nexus_query"))
Zeile 1763: act_nexus_query.setEnabled(single and self._nexus_api.has_api_key())
```

**Ergebnis:** Der Menuepunkt wird IMMER angezeigt wenn genau 1 Mod selektiert ist UND ein API-Key existiert. Er ist NICHT davon abhaengig ob `nexus_id > 0` ist -- das ist KORREKT, da auch Mods ohne Nexus-ID abgefragt werden sollen.

### Schritt 2: Menu-Auswahl (mainwindow.py)

```
Zeile 1786: chosen = menu.exec(global_pos)
Zeile 1831: elif chosen == act_nexus_query:
Zeile 1832:     self._ctx_query_nexus_info(selected_rows[0])
```

**Ergebnis:** Korrekt. Die if/elif-Kette ist in der richtigen Reihenfolge. `act_nexus_query` wird VOR `act_explorer` und `act_info` geprueft. Es gibt KEINEN alten Code der vorher greift.

### Schritt 3: _ctx_query_nexus_info() (mainwindow.py:2701)

```python
def _ctx_query_nexus_info(self, row: int) -> None:
    # Zeile 2703: Bounds-Check
    if row >= len(self._current_mod_entries):
        return
    entry = self._current_mod_entries[row]

    # Zeile 2707: Schritt 1 -- Existierende Nexus-ID nutzen
    nexus_id = entry.nexus_id

    # Zeile 2710: Schritt 2 -- Downloads-Archiv suchen (NUR wenn nexus_id <= 0)
    if nexus_id <= 0:
        from anvil.core.nexus_filename_parser import extract_nexus_mod_id
        downloads_path = self._current_instance_path / ".downloads"
        if downloads_path.is_dir():
            mod_lower = entry.name.lower()          # Zeile 2714
            for f in downloads_path.iterdir():       # Zeile 2715
                if f.is_file() and f.suffix.lower() in ('.zip', '.rar', '.7z'):  # 2716
                    if mod_lower in f.stem.lower():  # Zeile 2717 -- SCHWACHES MATCHING
                        parsed_id = extract_nexus_mod_id(f.name)  # 2718
                        if parsed_id and parsed_id > 0:           # 2719
                            answer = QMessageBox.question(...)     # 2720-2725
                            if answer == Yes:
                                nexus_id = parsed_id               # 2727
                            break                                  # 2728

    # Zeile 2731: Schritt 3 -- Manueller Fallback-Dialog
    if nexus_id <= 0:
        text, ok = get_text_input(
            self, tr("dialog.nexus_query_title"), tr("dialog.nexus_query_prompt"),
        )
        # ... Validierung ...

    # Zeile 2745: Pfad speichern (NICHT Row-Index -- korrekt!)
    self._pending_query_path = entry.install_path

    # Zeile 2747-2754: Nexus-Slug ermitteln
    nexus_slug = getattr(plugin, "GameNexusName", "") or getattr(plugin, "GameShortName", "")
    if not nexus_slug:
        return  # STILLER ABBRUCH -- kein Fehler an User!

    # Zeile 2756: API-Call
    self._nexus_api.query_mod_info(nexus_slug, nexus_id)
```

**Flow-Entscheidungsbaum:**

```
entry.nexus_id > 0?
  JA  --> Direkt zu API-Call (Zeile 2756)
  NEIN --> Archiv-Suche in .downloads/ (Zeile 2710-2728)
            Archiv gefunden mit Nexus-ID?
              JA  --> User bestaetigt?
                        JA  --> nexus_id = parsed_id, weiter zu API-Call
                        NEIN --> break, weiter zu manuellem Dialog
              NEIN --> Weiter zu manuellem Dialog (Zeile 2731)
            Kein Archiv gefunden?
              --> Weiter zu manuellem Dialog (Zeile 2731)
```

### Schritt 4: API-Call (nexus_api.py:120)

```python
def query_mod_info(self, game: str, mod_id: int) -> None:
    self._get(f"/games/{game}/mods/{mod_id}.json",
              tag=f"query_mod_info:{game}:{mod_id}")
```

**Tag-Prefix:** `query_mod_info:` -- NICHT `mod_info:`. Korrekt getrennt vom NXM-Download-Flow.

### Schritt 5: Response-Handler (mainwindow.py:3148)

```python
elif tag.startswith("query_mod_info:") and isinstance(data, dict):
    dl_path = self._pending_dl_query_path     # Zeile 3149
    mod_path = self._pending_query_path       # Zeile 3150

    if dl_path:                               # Zeile 3152 -- PRIORITAET!
        # Downloads-Tab query
        self._pending_dl_query_path = None
        self._update_download_meta(dl_path, data)
        ...
    elif mod_path:                            # Zeile 3169
        # Mod-Liste query
        self._pending_query_path = None
        write_meta_ini(mod_path, {...})
        self._reload_mod_list()
        ...
```

---

## Findings

### [HIGH] Race-Condition bei parallelen Queries -- Pending-Variablen nicht exklusiv

- **Datei:** `anvil/mainwindow.py:2745` und `anvil/mainwindow.py:2811`
- **Problem:** `_ctx_query_nexus_info()` setzt nur `self._pending_query_path` (Zeile 2745), setzt aber `self._pending_dl_query_path` NICHT auf None zurueck. Umgekehrt setzt `_on_dl_query_info()` nur `self._pending_dl_query_path` (Zeile 2811), aber nicht `self._pending_query_path` auf None.

  Wenn ein User zuerst einen Download-Query startet (setzt `_pending_dl_query_path`) und dann BEVOR die Response kommt einen Mod-Listen-Query startet (setzt `_pending_query_path`), sind BEIDE Variablen gesetzt. Da beide den GLEICHEN API-Endpunkt mit GLEICHEM Tag-Format nutzen, koennen die Responses nicht unterschieden werden.

  Im Response-Handler (Zeile 3152) wird `dl_path` IMMER zuerst geprueft (`if dl_path:`), wodurch die Mod-Listen-Query-Response faelschlich als Downloads-Query verarbeitet wird.

- **Fix:**
  ```python
  # In _ctx_query_nexus_info() (Zeile 2745):
  self._pending_query_path = entry.install_path
  self._pending_dl_query_path = None  # <-- Exklusivitaet sicherstellen

  # In _on_dl_query_info() (Zeile 2811):
  self._pending_dl_query_path = archive_path
  self._pending_query_path = None     # <-- Exklusivitaet sicherstellen
  ```

### [MEDIUM] Schwaches Substring-Matching bei Archiv-Suche

- **Datei:** `anvil/mainwindow.py:2717`
- **Problem:** Die Bedingung `if mod_lower in f.stem.lower()` ist ein reines Substring-Matching. Ein Mod-Ordner namens `red` wuerde JEDES Archiv matchen, dessen Name `red` enthaelt (z.B. `redscript-108418-0-5-27.zip`, `Cyber-Engine-Tweaks-redmod-12345.zip`, etc.).

  Typische False-Positive-Szenarien:
  - Mod-Ordner `red` matched `redscript-108418.zip`
  - Mod-Ordner `mod` matched JEDES Archiv das "mod" im Namen hat
  - Mod-Ordner `the` matched fast alles

  Der User wird zwar per QMessageBox gefragt, aber bei vielen False-Positives ist das stoerend.

- **Fix:** Pruefen ob der Mod-Name am Anfang des Dateinamens steht (Prefix-Match statt Substring-Match):
  ```python
  if f.stem.lower().startswith(mod_lower):
  ```
  Oder besser: Pruefen ob nach dem Mod-Namen ein Bindestrich folgt (Nexus-Konvention):
  ```python
  stem = f.stem.lower()
  if stem.startswith(mod_lower) or stem.startswith(mod_lower.replace(' ', '_')):
  ```

### [MEDIUM] Stiller Abbruch wenn kein nexus_slug

- **Datei:** `anvil/mainwindow.py:2753-2754`
- **Problem:** Wenn `nexus_slug` leer ist (Plugin hat weder `GameNexusName` noch `GameShortName`), wird die Methode still per `return` beendet. Der User hat bereits eine Nexus-ID eingegeben, bekommt aber KEIN Feedback warum nichts passiert. `_pending_query_path` bleibt gesetzt und wird nie aufgeraeumt.
- **Selbes Problem in:** `anvil/mainwindow.py:2819-2820` (`_on_dl_query_info()`)
- **Fix:**
  ```python
  if not nexus_slug:
      self._pending_query_path = None  # Aufraumen
      self.statusBar().showMessage(tr("status.nexus_no_game_slug"), 5000)
      return
  ```

### [LOW] Break nach erstem Archiv-Match -- kein Best-Match

- **Datei:** `anvil/mainwindow.py:2728`
- **Problem:** Das `break` Statement auf Zeile 2728 beendet die Schleife nach dem ERSTEN Match. Wenn es mehrere passende Archive gibt (z.B. verschiedene Versionen), wird immer das erste gefundene genommen -- die Reihenfolge von `iterdir()` ist nicht garantiert.

  Fuer die meisten Faelle ist das akzeptabel, da der User per QMessageBox bestaetigen muss. Aber bei `break` auch nach `answer == No` (Zeile 2728 ist AUSSERHALB des if-Blocks) wird kein weiteres Archiv geprueft.

- **Fix:** `break` nur bei `answer == Yes` ausfuehren, oder alle Matches sammeln und den besten (laengster Name = spezifischster Match) waehlen.

### [LOW] Filename-Parser Regex: Edge Case bei Mod-IDs mit 1 Stelle

- **Datei:** `anvil/core/nexus_filename_parser.py:7`
- **Problem:** Die Regex erfordert mind. 2-stellige IDs (`\d{2,}`). Mods mit einstelliger ID (1-9) werden nicht erkannt. Das ist aber ein bewusstes Design (Nexus-IDs sind in der Praxis immer mehrstllig), daher nur informativ.

### [LOW] Kein Schutz gegen doppelte gleichzeitige Queries

- **Datei:** `anvil/mainwindow.py:2745`
- **Problem:** Wenn der User schnell hintereinander zwei verschiedene Mods per "Nexus-Info abrufen" abfragt, wird `_pending_query_path` ueberschrieben. Die Response der ersten Query aktualisiert dann die meta.ini der ZWEITEN Mod. Die Feature-Spec erwaehnt dieses Risiko (Zeile 152: "Nur eine Query gleichzeitig erlauben"), aber es gibt keinen Guard dagegen.
- **Fix:** Entweder den Menuepunkt disablen waehrend eine Query laeuft, oder ein Dict `{tag: path}` statt einer einzelnen Variable verwenden.

---

## Flow-Diagramm: Warum der "alte Dialog" erscheint

**Antwort auf die Kernfrage: "Warum erscheint der alte Dialog immer noch?"**

Der "alte Dialog" (manueller ID-Eingabe-Dialog, `get_text_input()` auf Zeile 2732) erscheint in genau diesen Faellen:

1. **Mod hat `nexus_id = 0`** (kein modid in meta.ini) UND
2. **Kein passendes Archiv in `.downloads/` gefunden** (Schritt 2 schlaegt fehl)

Das passiert wenn:
- `.downloads/` Verzeichnis existiert nicht
- `.downloads/` ist leer
- Kein Archiv-Dateiname enthaelt den Mod-Ordnernamen als Substring
- Ein Archiv wurde gefunden, aber `extract_nexus_mod_id()` konnte keine ID parsen
- Ein Archiv wurde gefunden und ID geparst, aber User hat mit "Nein" geantwortet

**Es gibt KEINEN "alten Code" der VOR dem neuen ausgefuehrt wird.** Der Flow ist:
```
Step 1: entry.nexus_id pruefen  --> wenn > 0: DIREKT zum API-Call
Step 2: .downloads/ durchsuchen --> wenn Match + User OK: zum API-Call
Step 3: Manueller Dialog        --> User-Eingabe oder Abbruch
```

Die Reihenfolge der Bedingungen ist korrekt. Es gibt keine veraltete if-Kette die zuerst greift.

---

## Checklisten-Pruefung (Feature-Spec Akzeptanz-Kriterien)

- [x] 1. Kontextmenue "Nexus-Info abrufen" erscheint und ist klickbar bei nexus_id > 0 -- Zeile 1762-1763: `act_nexus_query.setEnabled(single and self._nexus_api.has_api_key())` -- KORREKT, keine nexus_id-Pruefung hier
- [x] 2. Kontextmenue "Nexus-Info abrufen" erscheint und ist klickbar bei nexus_id = 0 -- Gleiche Logik wie Punkt 1, keine nexus_id-Abhaengigkeit
- [x] 3. API-Call mit Tag-Prefix `query_mod_info:` bei nexus_id > 0 -- Zeile 2707-2756: `nexus_id = entry.nexus_id`, dann `query_mod_info(slug, nexus_id)`
- [x] 4. Eingabe-Dialog bei nexus_id = 0 -- Zeile 2731-2743: `get_text_input()` wird aufgerufen wenn `nexus_id <= 0` nach Archiv-Suche
- [x] 5. API-Call mit eingegebener ID -- Zeile 2738 + 2756: `nexus_id = int(text.strip())`, dann `query_mod_info()`
- [x] 6. Keine API bei ungueltigem Input -- Zeile 2735-2743: Validierung mit return bei leer/ungueltig
- [x] 7. meta.ini wird bei Erfolg aktualisiert -- Zeile 3174-3189: `write_meta_ini()` mit allen Feldern
- [x] 8. Mod-Liste wird neu geladen + Statusbar -- Zeile 3190: `_reload_mod_list()`, Zeile 3191-3193: Statusbar
- [x] 9. "Nexus-Seite oeffnen" wird nach Query aktiviert -- Zeile 1766: `has_nexus = ... entry.nexus_id > 0` -- nach `_reload_mod_list()` wird entry.nexus_id aus aktualisierter meta.ini gelesen
- [x] 10. Menuepunkt ausgegraut ohne API-Key -- Zeile 1763: `self._nexus_api.has_api_key()`
- [x] 11. Fehler-Handling bei API-Errors -- Zeile 3195-3200: `_on_nexus_error()` zeigt Statusbar-Fehler, setzt pending-Variablen zurueck
- [x] 12. GamePanel-Button mit Selektion -- Zeile 2759-2765: `_on_nexus_query_from_panel()` -> `_ctx_query_nexus_info()`
- [x] 13. GamePanel-Button ohne Selektion -- Zeile 2762-2763: Statusbar-Meldung bei `len != 1`
- [x] 14. install_path statt Row-Index -- Zeile 2745: `self._pending_query_path = entry.install_path`
- [ ] 15. Keine Kollision zwischen NXM-Download und Query -- Tag-Prefixe sind getrennt (`mod_info:` vs `query_mod_info:`), ABER: Race-Condition zwischen Mod-Listen-Query und Download-Query (siehe HIGH Finding)
- [x] 16. Alle i18n-Keys in allen 6 Locales -- Geprueft, alle 9 relevanten Keys vorhanden
- [ ] 17. restart.sh startet ohne Fehler -- Nicht geprueft (App nicht gestartet)

## Ergebnis: 15/17 Punkte erfuellt

---

## Gesamtbewertung

**NEEDS FIXES** -- 1 HIGH Finding (Race-Condition) muss behoben werden.

Die Kern-Implementierung (Rechtsklick -> API-Call -> meta.ini Update -> Reload) ist **funktional korrekt und vollstaendig**. Der Flow hat keine toten Pfade, keine alten Code-Reste die vorher greifen, und die if/elif-Ketten sind in der richtigen Reihenfolge.

Die Race-Condition (HIGH) ist der einzige funktionale Bug: Wenn ein User sowohl Downloads-Query als auch Mod-Listen-Query nutzt, kann die Response an den falschen Handler geroutet werden. Der Fix ist trivial (gegenseitiges Zuruecksetzen der pending-Variablen).

Die MEDIUM-Findings (schwaches Matching, stiller Abbruch) sind Verbesserungsvorschlaege, die die Grundfunktion nicht blockieren.
