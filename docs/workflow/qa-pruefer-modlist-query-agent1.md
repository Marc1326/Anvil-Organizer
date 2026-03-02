# QA Report -- Code-Analyse _ctx_query_nexus_info() in mainwindow.py
Datum: 2026-03-02

## Zusammenfassung

Analyse der Methode `_ctx_query_nexus_info()` in `anvil/mainwindow.py` (Zeilen 2701-2757) im Kontext der Feature-Specs `feature-spec-nexus-query.md` (Mod-Liste) und `feature-spec-mo2-query-info.md` (Downloads-Tab).

## 1. Ist die alte Dialog-Logik noch drin?

**NEIN** -- Die alte Logik (sofort Dialog bei nexus_id=0) ist NICHT mehr vorhanden.

Die aktuelle Implementierung in Zeile 2701-2757 hat eine 3-Stufen-Fallback-Kette:

1. **Step 1 (Zeile 2707):** `nexus_id = entry.nexus_id` -- liest die nexus_id aus dem ModEntry (wird beim Laden aus meta.ini ausgelesen, siehe `mod_entry.py:93-96`)
2. **Step 2 (Zeile 2710-2728):** Archiv-Suche in `.downloads/` mit Filename-Parsing
3. **Step 3 (Zeile 2731-2743):** Manueller Eingabe-Dialog als letzter Fallback

Die alte Feature-Spec (`feature-spec-nexus-query.md`) definierte nur 2 Stufen:
- nexus_id > 0 --> direkt API-Call
- nexus_id = 0 --> QInputDialog

Die aktuelle Implementierung hat also eine ZUSAETZLICHE Stufe (Archiv-Suche) eingebaut, die in der neueren Feature-Spec (`feature-spec-mo2-query-info.md`) spezifiziert wurde. Das ist eine Verbesserung.

## 2. Ist die neue Archiv-Such-Logik eingebaut?

**JA** -- Zeilen 2710-2728.

### Ablauf der Archiv-Suche:
```python
# Zeile 2710-2728
if nexus_id <= 0:
    from anvil.core.nexus_filename_parser import extract_nexus_mod_id
    downloads_path = self._current_instance_path / ".downloads"
    if downloads_path.is_dir():
        mod_lower = entry.name.lower()
        for f in downloads_path.iterdir():
            if f.is_file() and f.suffix.lower() in ('.zip', '.rar', '.7z'):
                if mod_lower in f.stem.lower():
                    parsed_id = extract_nexus_mod_id(f.name)
                    if parsed_id and parsed_id > 0:
                        # Bestaetigungs-Dialog
                        answer = QMessageBox.question(...)
                        if answer == Yes:
                            nexus_id = parsed_id
                        break
```

### Bewertung:
- Import ist korrekt (lazy import innerhalb des if-Blocks)
- `.downloads/` Pfad wird relativ zur Instanz gebaut
- Dateiendungen-Filter ist korrekt (.zip, .rar, .7z)
- Matching: Mod-Name als Substring im Archiv-Dateinamen (case-insensitive)
- Bestaetigungs-Dialog wird angezeigt bevor die ID uebernommen wird
- `break` nach dem ersten Match (nur erste Uebereinstimmung wird geprueft)

## 3. Wird extract_nexus_mod_id() importiert und aufgerufen?

**JA** -- An zwei Stellen:
- `anvil/mainwindow.py:2711` -- Lazy Import in `_ctx_query_nexus_info()`
- `anvil/mainwindow.py:2769` -- Lazy Import in `_on_dl_query_info()`

Beide Aufrufe:
- `anvil/mainwindow.py:2718` -- `parsed_id = extract_nexus_mod_id(f.name)`
- `anvil/mainwindow.py:2783` -- `parsed_id = extract_nexus_mod_id(filename)`

## 4. Wird die .downloads/ Suche korrekt durchgefuehrt?

**GRUNDSAETZLICH JA**, aber mit einem relevanten Problem:

### Matching-Logik (Zeile 2714, 2717):
```python
mod_lower = entry.name.lower()
...
if mod_lower in f.stem.lower():
```

`entry.name` ist der Ordnername des Mods (z.B. "Peachu Casual Dress - Archive XL").
`f.stem` ist der Archiv-Dateiname ohne Endung (z.B. "Peachu Casual Dress - Archive XL-14817-1-1716336327").

Das Substring-Matching `mod_lower in f.stem.lower()` funktioniert in den meisten Faellen, ABER:

## Findings

### [MEDIUM] Substring-Matching kann False Positives erzeugen
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:2717`
- **Problem:** Wenn ein Mod-Ordner "Boots" heisst und es ein Archiv "Ripper Boots-5231-1-1663279901.zip" gibt, matcht "boots" in "ripper boots-5231-1-1663279901". Aber auch ein Archiv fuer einen voellig anderen Mod, der zufaellig "Boots" im Namen hat, wuerde matchen. Kurze Mod-Namen erhoehen die False-Positive-Rate.
- **Fix:** Optional: Praeziseres Matching, z.B. pruefen ob der Mod-Name am Anfang des Archiv-Dateinamens steht (`f.stem.lower().startswith(mod_lower)`). Allerdings ist der Bestaetigungs-Dialog ein guter Schutz, da der User die erkannte ID bestaetigen muss.
- **Schweregrad:** MEDIUM -- Der Bestaetigungs-Dialog federt das Risiko ab.

### [MEDIUM] _current_instance_path kann None sein (theoretisch)
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:2712`
- **Problem:** `downloads_path = self._current_instance_path / ".downloads"` -- Wenn `_current_instance_path` None ist (z.B. bei App-Start ohne geladene Instanz), wuerde `None / ".downloads"` einen TypeError ausloesen. Allerdings wird das Kontextmenue nur angezeigt wenn eine Mod-Liste geladen ist, was eine Instanz voraussetzt. Die `_current_instance_path` wird nur bei Reset auf None gesetzt (Zeile 839).
- **Fix:** Defensiv-Check: `if self._current_instance_path and ...` vor Zeile 2712.
- **Schweregrad:** MEDIUM -- Theoretisch moeglich, praktisch unwahrscheinlich.

### [MEDIUM] User sagt "Nein" im Bestaetigungs-Dialog --> kein weiterer Archiv-Scan
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:2726-2728`
- **Problem:** Wenn der User den Bestaetigungs-Dialog mit "Nein" beantwortet (Zeile 2726), wird trotzdem `break` ausgefuehrt (Zeile 2728). Das bedeutet: Wenn das erste matchende Archiv die falsche ID hat, wird kein weiteres Archiv geprueft. Der User landet direkt im manuellen Dialog.
- **Fix:** Zwei Optionen: (a) `break` nur bei "Ja" ausfuehren und weiter iterieren, oder (b) Aktuelles Verhalten ist akzeptabel -- der User kann die korrekte ID im manuellen Dialog eingeben.
- **Schweregrad:** MEDIUM -- Akzeptabel, aber nicht optimal.

### [LOW] Kommentar "Step 2" ohne "Step 1"
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:2709`
- **Problem:** Der Kommentar sagt "# Step 2: Search .downloads/...", aber es gibt keinen expliziten "Step 1" Kommentar. Step 1 ist implizit die Zeile `nexus_id = entry.nexus_id` (Zeile 2707), die die ID aus der meta.ini des Mod-Ordners liest.
- **Fix:** Kommentar `# Step 1: Use nexus_id from meta.ini (loaded via ModEntry)` ueber Zeile 2707 hinzufuegen.
- **Schweregrad:** LOW -- Nur Lesbarkeit.

### [LOW] Keine User-Rueckmeldung wenn .downloads/ nicht existiert
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:2713`
- **Problem:** Wenn `.downloads/` nicht existiert oder leer ist, wird der Block uebersprungen und direkt der manuelle Dialog angezeigt. Der User bekommt keinen Hinweis, warum kein Archiv gefunden wurde.
- **Fix:** Optional: debug.log Ausgabe. Allerdings ist das Verhalten korrekt -- der manuelle Dialog ist der erwartete Fallback.
- **Schweregrad:** LOW -- Funktional korrekt, nur UX-Detail.

### [LOW] Vergleich Mod-Liste vs. Downloads-Tab: Asymmetrische Fallback-Kette
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:2701-2757` vs `2767-2809`
- **Problem:** Die Downloads-Tab-Logik (`_on_dl_query_info`) hat eine 3-Stufen-Kette: `.meta modID` -> Dateinamen-Parsing -> manueller Dialog. Die Mod-Liste-Logik (`_ctx_query_nexus_info`) hat auch 3 Stufen, aber anders: `entry.nexus_id` (aus meta.ini) -> `.downloads/` Archiv-Suche -> manueller Dialog. Das ist logisch korrekt (unterschiedliche Kontexte), aber die Kommentierung suggeriert nicht, dass die Ketten bewusst unterschiedlich sind.
- **Fix:** Dokumentations-Kommentar.
- **Schweregrad:** LOW -- Bewusste Design-Entscheidung, kein Bug.

## Analyse: nexus_filename_parser.py

Die Datei `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_filename_parser.py` implementiert `extract_nexus_mod_id()` wie in der Feature-Spec beschrieben:

```python
# Zeile 5-12: Regex
_NEXUS_FILENAME_RE = re.compile(
    r'^(.+?)'              # Gruppe 1: Mod-Name (non-greedy)
    r'-(\d{2,})'           # Gruppe 2: Mod-ID (mind. 2-stellig)
    r'(?:-[\d]+)*'         # optionale Versions-/File-ID-Segmente
    r'-(\d{9,11})'         # Timestamp-Gruppe (9-11 Stellen)
    r'\.(?:zip|rar|7z)$',  # Dateiendung
    re.IGNORECASE
)
```

**Pruefung gegen Testdaten aus der Feature-Spec:**
- "Peachu Casual Dress - Archive XL-14817-1-1716336327.rar" --> Mod-ID 14817 (korrekt)
- "Caldos Ripper-8378-15-0-0-1760955833.zip" --> Mod-ID 8378 (korrekt)
- "Ripper Boots-5231-1-1663279901.zip" --> Mod-ID 5231 (korrekt)
- "random_mod_without_id.zip" --> None (korrekt, Fallback-Regex findet auch nichts)

**Potentielles Problem mit dem Fallback-Regex (Zeile 29):**
```python
candidates = re.findall(r'-(\d{2,})-', filename)
```
Dieser Fallback sucht nach Zahlengruppen zwischen Bindestrichen. Bei einem Dateinamen wie "mod-v2-final.zip" wuerde er "2" nicht finden (nur 1 Stelle). Aber bei "mod-v20-final.zip" wuerde er "20" als Mod-ID zurueckgeben, was wahrscheinlich nicht korrekt ist. Da aber der Bestaetigungs-Dialog den User fragt, ist das akzeptabel.

## Analyse: Response-Router (_on_nexus_response)

Zeilen 3148-3193 zeigen die Response-Verarbeitung:

```python
elif tag.startswith("query_mod_info:") and isinstance(data, dict):
    dl_path = self._pending_dl_query_path
    mod_path = self._pending_query_path

    if dl_path:
        # Downloads-Tab query
        ...
    elif mod_path:
        # Mod-Liste query
        ...
```

**Beobachtung:** Wenn BEIDE Pending-Felder gesetzt sind (gleichzeitige Queries), wird nur der Downloads-Tab-Pfad verarbeitet. Der Mod-Liste-Pfad geht verloren. Das ist in der Feature-Spec als Risiko dokumentiert ("Pending-Kollision"). Die Loesung mit separaten Pending-Feldern vermeidet das Problem NUR, wenn nie zwei Queries gleichzeitig laufen. Da die API asynchron ist und der User schnell hintereinander klicken koennte, ist eine Kollision moeglich.

### [HIGH] Race Condition bei gleichzeitigen Queries (Mod-Liste + Downloads-Tab)
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:3148-3193`
- **Problem:** Wenn der User zuerst eine Mod-Liste-Query startet (`_pending_query_path` gesetzt) und danach sofort eine Downloads-Query (`_pending_dl_query_path` gesetzt), wird bei der Response NUR der Downloads-Tab verarbeitet (weil `if dl_path:` zuerst geprueft wird). Die Mod-Liste-Query geht verloren.
- **Fix:** Response anhand des Tags (z.B. Tag koennte einen Prefix enthalten der den Ursprung kodiert) routen, oder beide Pending-Felder in der Response verarbeiten.
- **Schweregrad:** HIGH -- Datenverlust moeglich, aber nur bei sehr schnellem Doppelklick.

### [MEDIUM] Stiller Abbruch wenn nexus_slug leer
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:2753-2754`
- **Problem:** Wenn `nexus_slug` leer ist (kein GameNexusName/GameShortName im Plugin), wird die Methode still mit `return` beendet. Der User hat eventuell eine ID eingegeben und bekommt keine Rueckmeldung warum nichts passiert. Kein Statusbar-Hinweis.
- **Fix:** `self.statusBar().showMessage(tr("status.nexus_error", message="..."), 5000)` vor dem return.
- **Schweregrad:** MEDIUM -- Schlechte UX, kein Datenverlust.

## Zusammenfassung aller relevanten Code-Stellen

| Zeile | Datei | Beschreibung |
|-------|-------|-------------|
| 2701-2757 | mainwindow.py | `_ctx_query_nexus_info()` -- Mod-Liste Query mit 3-Stufen-Fallback |
| 2707 | mainwindow.py | Step 1: nexus_id aus ModEntry (meta.ini) |
| 2710-2728 | mainwindow.py | Step 2: .downloads/ Archiv-Suche mit Filename-Parsing |
| 2731-2743 | mainwindow.py | Step 3: Manueller Eingabe-Dialog |
| 2745 | mainwindow.py | `_pending_query_path` wird gesetzt |
| 2756 | mainwindow.py | API-Call ueber `query_mod_info()` |
| 2759-2765 | mainwindow.py | `_on_nexus_query_from_panel()` -- GamePanel-Button Handler |
| 2767-2809 | mainwindow.py | `_on_dl_query_info()` -- Downloads-Tab Query (3 Stufen) |
| 2824-2843 | mainwindow.py | `_update_download_meta()` -- .meta Aktualisierung |
| 3148-3193 | mainwindow.py | Response-Router fuer `query_mod_info:` Tag |
| 3195-3200 | mainwindow.py | Error-Handler (beide Pending-Felder werden zurueckgesetzt) |
| 1762-1763 | mainwindow.py | Kontextmenue-Eintrag "Nexus-Info abrufen" |
| 1831-1832 | mainwindow.py | Kontextmenue-Handler fuer die Action |
| 1-36 | nexus_filename_parser.py | `extract_nexus_mod_id()` -- Regex + Fallback |
| 87-88 | game_panel.py | Signale `nexus_query_requested`, `dl_query_info_requested` |
| 158-167 | game_panel.py | Nexus-Info-Button im GamePanel |
| 1291-1293 | game_panel.py | `set_nexus_api_available()` |
| 1295-1301 | game_panel.py | `update_download_tooltip()` |
| 1429-1435 | game_panel.py | Downloads-Tab Kontextmenue-Eintrag "Query Nexus Info" |
| 1483-1485 | game_panel.py | Downloads-Tab Kontextmenue-Handler |

## Ergebnis

| Severity | Anzahl |
|----------|--------|
| CRITICAL | 0 |
| HIGH | 1 |
| MEDIUM | 4 |
| LOW | 3 |

**Status: NEEDS REVIEW** -- Die Implementierung ist funktional korrekt und die Fallback-Kette ist wie erwartet eingebaut. Die alte sofortige Dialog-Logik ist nicht mehr vorhanden. Das HIGH-Finding (Race Condition bei gleichzeitigen Queries) ist das einzige relevante Problem, das aber nur bei sehr schnellem Doppelklick auftreten kann.
