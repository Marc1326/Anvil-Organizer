# QA Konsolidierter Report -- Nexus Query Info (Mod-Liste)
Datum: 2026-03-02

## Kontext
Marc meldet: "Das alte Fenster geht immer noch auf und Infos werden nicht automatisch geladen."
Die Agents 1-3 haben die Implementierung als "funktional korrekt" bewertet.
Dieser Report prueft den TATSAECHLICHEN Code gegen die TATSAECHLICHEN Daten auf der Festplatte.

---

## ROOT CAUSE ANALYSE

Die Agents 1-3 haben den Code THEORETISCH geprueft, aber NICHT gegen die realen
Instanz-Konfigurationen und Dateinamen getestet. Es gibt **3 konkrete Root Causes**:

### ROOT CAUSE 1: FALSCHER DOWNLOADS-PFAD (CRITICAL)

**Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:2712`

```python
# Zeile 2712 -- HARDCODED Default-Pfad:
downloads_path = self._current_instance_path / ".downloads"
```

**Problem:** Der Pfad wird als `<instance_path>/.downloads/` hardcoded, aber der Benutzer
kann in der Instance-Config (`Paths/downloads_directory` in `.anvil.ini`) einen EIGENEN
Pfad konfiguriert haben.

**Reale Instance-Konfigurationen:**
| Instanz | Konfigurierter Pfad | Code verwendet |
|---------|--------------------|--------------------|
| Cyberpunk 2077 | `/home/mob/Downloads` | `<instance>/.downloads/` |
| Fallout 4 | `/mnt/gamingS/Mods-test/Fallout 4` | `<instance>/.downloads/` |
| RDR2 | `/mnt/gamingS/Mods-test/RDR2` | `<instance>/.downloads/` |
| Skyrim SE | `/mnt/gamingS/Mods-test` | `<instance>/.downloads/` |
| Witcher 3 | `/mnt/gamingS/Mods-test/Witcher` | `<instance>/.downloads/` |

Bei Fallout 4, RDR2, Skyrim, Witcher: `.downloads/` in der Instanz ist LEER.
Die echten Archive liegen im konfigurierten Pfad. Der Code findet NIE etwas.

**Vergleich mit Downloads-Tab:** `_on_dl_query_info()` bekommt den Archiv-Pfad
als Parameter uebergeben (direkt aus dem GamePanel, das den RICHTIGEN Pfad kennt).
`_ctx_query_nexus_info()` muss sich den Pfad SELBST zusammenbauen -- und tut es FALSCH.

In `mainwindow.py:880` wird der korrekte Pfad berechnet:
```python
downloads_dir = resolve_path(data.get("path_downloads_directory", "%INSTANCE_DIR%/.downloads"))
```
Aber dieser Pfad wird NUR an `self._game_panel.set_downloads_path()` uebergeben (Zeile 883),
NICHT als Instanzvariable in MainWindow gespeichert. `_ctx_query_nexus_info()` hat daher
keinen Zugriff auf den konfigurierten Pfad.

**Fix:**
1. In `_apply_instance()` (ca. Zeile 880): Downloads-Pfad als Instanzvariable speichern:
   ```python
   self._current_downloads_path = downloads_dir  # NEU
   self._game_panel.set_downloads_path(downloads_dir, mods_dir)
   ```
2. In `_ctx_query_nexus_info()` Zeile 2712:
   ```python
   # ALT:
   downloads_path = self._current_instance_path / ".downloads"
   # NEU:
   downloads_path = self._current_downloads_path
   ```
3. In `__init__` (ca. Zeile 269): Variable initialisieren:
   ```python
   self._current_downloads_path: Path | None = None
   ```
4. In Reset-Block (Zeile 839): zuruecksetzen:
   ```python
   self._current_downloads_path = None
   ```

### ROOT CAUSE 2: SUBSTRING-MATCHING IGNORIERT UNDERSCORE/SPACE (HIGH)

**Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:2717`

```python
# Zeile 2714-2717:
mod_lower = entry.name.lower()
...
if mod_lower in f.stem.lower():
```

**Konkretes Beispiel:**
- Mod-Ordner: `1 Peachu Casual Dress - Archive XL` (mit LEERZEICHEN)
- Archiv-Datei: `1_Peachu Casual Dress - Archive XL-14817-1-1716336327.rar` (mit UNTERSTRICH)
- `"1 peachu" in "1_peachu"` = **False** -- KEIN MATCH!

Nexus-Downloads verwenden haeufig Underscores statt Leerzeichen im Dateinamen.
Bei der Installation kann Anvil/MO2 den Ordnernamen mit Leerzeichen anlegen.
Das Substring-Matching beruecksichtigt diesen Unterschied NICHT.

Bei Cyberpunk 2077 ist genau 1 Mod ohne `nexus_id` vorhanden (`1 Peachu Casual Dress - Archive XL`),
und genau DIESER matcht nicht wegen des Underscore-Problems.

**Fix (Zeile 2714-2717):**
```python
# ALT:
mod_lower = entry.name.lower()
# NEU: Normalisiere Leerzeichen/Underscores fuer den Vergleich
mod_normalized = entry.name.lower().replace('_', ' ').replace('-', ' ')

# ALT:
if mod_lower in f.stem.lower():
# NEU:
stem_normalized = f.stem.lower().replace('_', ' ').replace('-', ' ')
if mod_normalized in stem_normalized:
```

### ROOT CAUSE 3: RACE CONDITION BEI PARALLELEN QUERIES (HIGH)

**Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:3148-3169`

```python
# Zeile 3148-3169 -- Response-Router:
elif tag.startswith("query_mod_info:") and isinstance(data, dict):
    dl_path = self._pending_dl_query_path    # Downloads-Tab
    mod_path = self._pending_query_path      # Mod-Liste

    if dl_path:                              # Downloads IMMER zuerst!
        ...
    elif mod_path:                           # Mod-Liste NUR wenn kein dl_path
        ...
```

**Problem:** Wenn BEIDE pending-Variablen gesetzt sind (User startet Downloads-Query und
dann Mod-Listen-Query), wird die Response IMMER dem Downloads-Tab zugeordnet. Die
Mod-Listen-Query geht verloren.

Gleichzeitig: `_ctx_query_nexus_info()` setzt NUR `self._pending_query_path` (Zeile 2745),
setzt aber `self._pending_dl_query_path` NICHT zurueck. Und umgekehrt.

**Fix (Zeile 2745 und 2811):**
```python
# In _ctx_query_nexus_info() Zeile 2745:
self._pending_query_path = entry.install_path
self._pending_dl_query_path = None  # Exklusivitaet sicherstellen

# In _on_dl_query_info() Zeile 2811:
self._pending_dl_query_path = archive_path
self._pending_query_path = None     # Exklusivitaet sicherstellen
```

---

## WEITERE FINDINGS (aus Agents 1-3, bestaetigt)

### [MEDIUM] Stiller Abbruch bei fehlendem nexus_slug
- **Datei:** `mainwindow.py:2753-2754`
- **Problem:** Wenn `nexus_slug` leer ist, wird `return` ausgefuehrt. `_pending_query_path`
  bleibt gesetzt und wird nie aufgeraeumt. Kein Feedback an den User.
- **Fix:**
  ```python
  if not nexus_slug:
      self._pending_query_path = None
      self.statusBar().showMessage(tr("status.nexus_no_game_slug"), 5000)
      return
  ```

### [MEDIUM] Break nach "Nein" im Bestaetigungs-Dialog
- **Datei:** `mainwindow.py:2728`
- **Problem:** `break` wird IMMER ausgefuehrt, egal ob User "Ja" oder "Nein" klickt.
  Bei "Nein" koennte ein zweites passendes Archiv existieren.
- **Fix:** `break` nur bei `answer == Yes` oder wenn kein weiteres Archiv relevant ist:
  ```python
  if answer == QMessageBox.StandardButton.Yes:
      nexus_id = parsed_id
      break
  # Ohne break: naechstes Archiv pruefen
  ```

### [MEDIUM] Inkonsistente i18n-Keys
- **Datei:** `mainwindow.py:2732-2733` vs `2796-2797`
- **Problem:** Mod-Liste nutzt `dialog.nexus_query_title` / `dialog.nexus_query_prompt`,
  Downloads-Tab nutzt `game_panel.query_nexus_info` / `game_panel.query_nexus_enter_id`.
  Verschiedene Keys = potentiell verschiedene Texte fuer den gleichen Dialog.
- **Fix:** Beide Methoden sollten dieselben i18n-Keys verwenden.

### [LOW] Kein Step-1 Kommentar
- **Datei:** `mainwindow.py:2707-2709`
- **Problem:** `# Step 2` ohne `# Step 1`. Lesbarkeitsproblem.

---

## WARUM "DAS ALTE FENSTER IMMER NOCH AUFGEHT"

**Antwort:** Der manuelle Eingabe-Dialog (Step 3, `get_text_input()` in Zeile 2732)
oeffnet sich, weil Step 2 (Archiv-Suche) IMMER fehlschlaegt:

1. **Bei Instanzen mit konfiguriertem Downloads-Pfad** (Fallout 4, RDR2, Skyrim, Witcher):
   `_ctx_query_nexus_info()` sucht in `<instance>/.downloads/`, das LEER ist.
   Die echten Archive liegen im konfigurierten Pfad (z.B. `/mnt/gamingS/Mods-test/...`).
   --> Kein Archiv gefunden --> Dialog oeffnet sich.

2. **Bei Cyberpunk 2077**: `.downloads/` existiert und hat Dateien, ABER:
   Der einzige Mod ohne `nexus_id` (`1 Peachu Casual Dress - Archive XL`) matcht NICHT
   auf das Archiv (`1_Peachu Casual Dress - Archive XL-14817-...`) wegen
   Leerzeichen vs. Unterstrich.
   --> Kein Match --> Dialog oeffnet sich.

3. **Fuer Mods MIT nexus_id > 0** (254 von 255 bei Cyberpunk): Der Code springt
   DIREKT zum API-Call (Zeile 2756), OHNE Dialog. Das funktioniert KORREKT.
   Marcs Beschwerde bezieht sich wahrscheinlich auf Mods ohne ID.

**Es gibt KEINEN alten Code-Rest der vor dem neuen ausgefuehrt wird.** Der Flow ist
korrekt implementiert, aber die Archiv-Suche (Step 2) hat zwei Bugs die sie
unwirksam machen.

---

## PRIORISIERTE FIX-LISTE

| Prio | Severity | Was | Zeile(n) | Aufwand |
|------|----------|-----|----------|---------|
| 1 | CRITICAL | Downloads-Pfad aus Instance-Config statt hardcoded | 2712, 880, ~269, ~839 | 4 Zeilen |
| 2 | HIGH | Underscore/Space-Normalisierung im Matching | 2714, 2717 | 2 Zeilen |
| 3 | HIGH | Race-Condition: Pending-Variablen gegenseitig zuruecksetzen | 2745, 2811 | 2 Zeilen |
| 4 | MEDIUM | Pending-Cleanup bei fehlendem nexus_slug | 2753-2754 | 2 Zeilen |
| 5 | MEDIUM | Break nur bei "Ja"-Klick | 2728 | 1 Zeile |
| 6 | MEDIUM | i18n-Keys vereinheitlichen | 2732-2733 | 2 Zeilen |

**Geschaetzter Gesamtaufwand:** ~13 Zeilen Code-Aenderung.

---

## ERGEBNIS

**NEEDS FIXES**

3 Root Causes gefunden. Die Agents 1-3 haben den Code nur statisch analysiert und dabei
uebersehen, dass:
- Der Downloads-Pfad nicht aus der Instance-Config gelesen wird (CRITICAL)
- Underscore/Space-Unterschiede das Matching brechen (HIGH)
- Die Pending-Variablen nicht gegenseitig zurueckgesetzt werden (HIGH)

Der Fix ist minimal (ca. 13 Zeilen) und klar lokalisiert. Nach dem Fix sollte die
Archiv-Suche (Step 2) in den meisten Faellen automatisch die richtige Nexus-ID finden
und der manuelle Dialog (Step 3) nur noch als letzter Fallback erscheinen.
