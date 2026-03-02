# QA Report: Vergleich Downloads-Tab vs Mod-Liste Nexus-Info-Abruf
Datum: 2026-03-02

## Zusammenfassung

Die Methode `_on_dl_query_info()` (Downloads-Tab) hat eine 3-stufige Fallback-Kette:
1. `.meta` modID lesen
2. Dateiname parsen
3. Manueller Dialog

Die Methode `_ctx_query_nexus_info()` (Mod-Liste) hat eine aehnliche, aber ANDERS aufgebaute Kette:
1. `entry.nexus_id` (beim Laden aus meta.ini gelesen)
2. `.downloads/`-Verzeichnis nach passendem Archiv durchsuchen + Dateiname parsen
3. Manueller Dialog

## Side-by-Side Vergleich

### Step 1: Nexus-ID Ermittlung (Primaerquelle)

| Aspekt | `_on_dl_query_info()` (Downloads) | `_ctx_query_nexus_info()` (Mod-Liste) |
|--------|-----------------------------------|---------------------------------------|
| Zeilen | 2771-2778 | 2707 |
| Quelle | `.meta`-Datei neben Archiv via `_read_meta_mod_id()` | `entry.nexus_id` (beim App-Start aus `meta.ini` im Mod-Ordner geladen) |
| Methode | Liest `.meta` zur Laufzeit neu (frisch) | Nutzt gecachten Wert aus ModEntry-Dataclass |
| Problem | Keines - liest immer aktuellen Stand | **KEIN BUG** - `entry.nexus_id` wird beim Laden des Mod-Eintrags aus `meta.ini` gelesen (mod_entry.py:93-98). Das ist aequivalent, nur gecacht statt live. |

**Bewertung Step 1:** Kein funktionaler Unterschied. Beide lesen letztlich aus einer `.ini`-Datei. Der Downloads-Tab liest die `.meta` neben dem Archiv, die Mod-Liste liest die `meta.ini` im Mod-Ordner. Das sind verschiedene Dateien fuer verschiedene Kontexte -- korrekt so.

### Step 2: Dateiname-Parsing (Fallback)

| Aspekt | `_on_dl_query_info()` (Downloads) | `_ctx_query_nexus_info()` (Mod-Liste) |
|--------|-----------------------------------|---------------------------------------|
| Zeilen | 2780-2792 | 2709-2728 |
| Eingabe | `Path(archive_path).name` - direkter Dateiname des Archivs | Durchsucht `.downloads/`-Verzeichnis nach Archiv dessen Name den Mod-Namen enthaelt |
| Matching | Exakter Dateiname (bereits bekannt) | Fuzzy-Match: `mod_lower in f.stem.lower()` |
| Loop | Kein Loop noetig (1 Datei) | `for f in downloads_path.iterdir()` ueber alle Archive |
| Break-Verhalten | N/A | `break` nach erstem Match (Zeile 2728) |

**Bewertung Step 2:** Hier liegt ein **DESIGN-UNTERSCHIED**, aber kein Bug:
- Downloads-Tab: Hat das Archiv bereits, parst dessen Namen direkt.
- Mod-Liste: Muss das passende Archiv erst finden, da der Kontext ein installierter Mod ist, nicht ein Archiv.

**POTENTIELLES PROBLEM im Mod-Liste-Code (Zeile 2717):**
```python
if mod_lower in f.stem.lower():
```
Der Fuzzy-Match `mod_lower in f.stem.lower()` kann zu False Positives fuehren. Beispiel:
- Mod-Name: `archivexl` (entry.name)
- Archiv: `Peachu Casual Dress - **ArchiveXL**-14817-1-1716336327.rar`
- Ergebnis: Match! Aber falsche Mod-ID (14817 gehoert zu "Peachu Casual Dress", nicht zu "ArchiveXL")

Das ist aber eher ein MEDIUM-Risiko, da der Bestaetigungs-Dialog (QMessageBox.question) den Benutzer fragt, ob die erkannte ID korrekt ist.

### Step 2b: QMessageBox Bestaetigungs-Dialog

| Aspekt | `_on_dl_query_info()` (Downloads) | `_ctx_query_nexus_info()` (Mod-Liste) |
|--------|-----------------------------------|---------------------------------------|
| Zeilen | 2785-2792 | 2720-2727 |
| Titel | `tr("game_panel.query_nexus_info")` | `tr("game_panel.query_nexus_info")` |
| Text | `tr("game_panel.query_nexus_parsed_id", id=parsed_id)` | `tr("game_panel.query_nexus_parsed_id", id=parsed_id)` |
| Buttons | `Yes | No` | `Yes | No` |
| Bei "No" | `mod_id` bleibt 0 -> weiter zu Step 3 | `nexus_id` bleibt unveraendert -> **PROBLEM** |

**KONKRETER BUG (Zeile 2726-2728):**

```python
# Downloads-Tab (KORREKT):
if answer == QMessageBox.StandardButton.Yes:
    mod_id = parsed_id
# Kein break -> prueft naechsten Dateinamen? NEIN: kein Loop, nur 1 Datei

# Mod-Liste (PROBLEM):
if answer == QMessageBox.StandardButton.Yes:
    nexus_id = parsed_id
break  # <-- IMMER break, egal ob Yes oder No!
```

In der Mod-Liste-Version:
- Wenn der Benutzer "Nein" klickt, wird `break` trotzdem ausgefuehrt.
- Das bedeutet: Es wird NUR das ERSTE passende Archiv geprueft.
- Wenn der Benutzer "Nein" sagt und es ein zweites passendes Archiv gaebe, wird dieses NICHT geprueft.
- **Das ist GEWOLLT** (ein weiteres Archiv mit dem gleichen Mod-Namen ist unwahrscheinlich), aber es weicht vom Downloads-Tab-Verhalten ab.

### Step 3: Manueller Fallback-Dialog

| Aspekt | `_on_dl_query_info()` (Downloads) | `_ctx_query_nexus_info()` (Mod-Liste) |
|--------|-----------------------------------|---------------------------------------|
| Zeilen | 2794-2808 | 2730-2743 |
| Bedingung | `if mod_id <= 0:` | `if nexus_id <= 0:` |
| Dialog-Funktion | `get_text_input()` | `get_text_input()` |
| Titel | `tr("game_panel.query_nexus_info")` | `tr("dialog.nexus_query_title")` |
| Prompt | `tr("game_panel.query_nexus_enter_id")` | `tr("dialog.nexus_query_prompt")` |
| Fehlerbehandlung | Identisch | Identisch |

**UNTERSCHIED (LOW):** Verschiedene i18n-Keys fuer Titel und Prompt:
- Downloads-Tab: `game_panel.query_nexus_info` / `game_panel.query_nexus_enter_id`
- Mod-Liste: `dialog.nexus_query_title` / `dialog.nexus_query_prompt`

Das sind moeglicherweise verschiedene Keys aus verschiedenen Entwicklungsphasen. Funktional identisch, aber inkonsistent.

### Step 4: API-Aufruf

| Aspekt | `_on_dl_query_info()` (Downloads) | `_ctx_query_nexus_info()` (Mod-Liste) |
|--------|-----------------------------------|---------------------------------------|
| Zeilen | 2810-2823 | 2745-2757 |
| Pending-Feld | `self._pending_dl_query_path = archive_path` | `self._pending_query_path = entry.install_path` |
| Slug-Ermittlung | Identisch | Identisch |
| API-Aufruf | `self._nexus_api.query_mod_info(nexus_slug, mod_id)` | `self._nexus_api.query_mod_info(nexus_slug, nexus_id)` |
| Statusbar | Identisch | Identisch |

**Bewertung Step 4:** Identisch. Korrekt implementiert mit separaten Pending-Feldern.

## Findings nach Severity

### [MEDIUM] Inkonsistente i18n-Keys im manuellen Dialog
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py`
- **Zeilen:** 2732-2733 vs 2796-2797
- **Problem:** `_ctx_query_nexus_info()` verwendet `dialog.nexus_query_title` und `dialog.nexus_query_prompt`, waehrend `_on_dl_query_info()` `game_panel.query_nexus_info` und `game_panel.query_nexus_enter_id` verwendet. Wenn die Keys unterschiedliche Texte enthalten, sieht der Benutzer verschiedene Dialoge fuer die gleiche Aktion, je nachdem ob er aus der Mod-Liste oder dem Downloads-Tab kommt.
- **Fix:** Beide Methoden sollten die gleichen i18n-Keys verwenden, idealerweise die neueren `game_panel.*`-Keys.

### [MEDIUM] Fuzzy-Match kann False Positives erzeugen
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:2717`
- **Problem:** `if mod_lower in f.stem.lower()` ist ein Substring-Match. Ein Mod namens "xl" wuerde in fast jedem Archiv-Namen matchen, der "archivexl" enthaelt. Umgekehrt wuerde "archivexl" in "Peachu Casual Dress - Archive XL-14817" matchen und eine falsche ID vorschlagen.
- **Mitigation:** Der Bestaetigungs-Dialog schuetzt vor der falschen ID, aber der Benutzer muss wissen, dass die vorgeschlagene ID nicht zum Mod gehoert.
- **Fix:** Exakteren Match verwenden, z.B. `f.stem.lower().startswith(mod_lower)` oder den Mod-Namen vor dem ersten Bindestrich extrahieren und vergleichen.

### [LOW] Break-Verhalten bei "Nein"-Klick im Bestaetigungs-Dialog
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/mainwindow.py:2728`
- **Problem:** `break` wird IMMER ausgefuehrt (nach dem if-Block), egal ob der Benutzer "Ja" oder "Nein" klickt. Bei "Nein" koennte ein zweites passendes Archiv mit der richtigen ID existieren.
- **Einschaetzung:** In der Praxis sehr unwahrscheinlich, dass zwei verschiedene Archive den gleichen Mod-Namen im Dateinamen enthalten. Der `break` ist defensiv und verhindert Endlos-Dialoge. Akzeptabel.
- **Fix (optional):** `break` nur bei "Ja" ausfuehren, bei "Nein" naechstes Archiv pruefen.

### [LOW] Unterschiedliche Code-Struktur erschwert Wartung
- **Problem:** Beide Methoden machen im Kern das Gleiche (ID ermitteln -> API aufrufen), aber mit unterschiedlicher Struktur. Bei zukuenftigen Aenderungen muss man beide Stellen aktualisieren.
- **Fix (optional):** Gemeinsame Hilfsmethode `_resolve_nexus_id()` extrahieren.

## Kein Bug in der Fallback-Kette selbst

Die Fallback-Kette der Mod-Liste-Methode (`_ctx_query_nexus_info`) ist **funktional korrekt**:

1. `entry.nexus_id` (aus meta.ini beim Laden) -- Wenn > 0, ueberspringe Parsing
2. Archiv in `.downloads/` suchen und Dateinamen parsen -- Wenn gefunden und Benutzer bestaetigt, verwende ID
3. Manueller Dialog -- Letzer Fallback

Der primaere Pfad (meta.ini hat modID > 0) funktioniert, weil `_build_entry()` in `mod_entry.py:93-98` die `modid` aus meta.ini liest und in `entry.nexus_id` speichert. Wenn ein Mod bereits eine Nexus-ID hat (z.B. weil er via NXM-Link installiert wurde oder vorher schon abgefragt wurde), wird diese direkt verwendet.

## Ergebnis

**KEIN CRITICAL oder HIGH Bug gefunden.**

Die beiden Methoden sind fuer ihre jeweiligen Kontexte korrekt implementiert:
- Downloads-Tab arbeitet mit Archiv-Pfaden und `.meta`-Dateien
- Mod-Liste arbeitet mit installierten Mods und `meta.ini`-Dateien

Die gefundenen Unterschiede (MEDIUM: i18n-Keys, Fuzzy-Match) sind kosmetisch bzw. Edge-Case-Probleme, die den Hauptflow nicht beeintraechtigen.
