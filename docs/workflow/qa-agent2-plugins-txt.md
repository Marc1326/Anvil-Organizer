# QA Agent 2 -- game_panel.py Review (Deploy/Purge)

Datum: 2026-03-01

## Gepruefte Datei

- `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py` (Zeilen 546-663)
- `/home/mob/Projekte/Anvil Organizer/anvil/core/plugins_txt_writer.py` (komplett)
- `/home/mob/Projekte/Anvil Organizer/anvil/plugins/games/game_fallout4.py` (PRIMARY_PLUGINS, plugins_txt_path)
- `/home/mob/Projekte/Anvil Organizer/anvil/plugins/base_game.py` (has_plugins_txt)

## git diff (aktuelle Aenderungen)

**game_panel.py**: Einzige Aenderung ist in `silent_deploy()` -- `writer.write()` gibt jetzt `result_path` zurueck und loggt bei `None`.

**plugins_txt_writer.py**: Neue `_remove_case_variants()`-Methode, zusaetzliche Debug-Prints in `scan_plugins()`, Early-Return bei leerer `found`-Menge, Case-Variant-Bereinigung in `write()` und `remove()`.

**game_fallout4.py**: `Ba2IniKey` von `sResourceArchive2List` auf `sResourceArchiveList2` korrigiert.

---

## Methode: silent_deploy() (Zeilen 546-603)

### Writer-Initialisierung

**Befund: KORREKT**

```python
writer = PluginsTxtWriter(
    self._current_plugin, self._current_game_path, self._instance_path
)
```

Der Writer wird mit drei Argumenten instanziiert:
- `game_plugin` = `self._current_plugin` (das Game-Plugin, z.B. Fallout4Game)
- `game_path` = `self._current_game_path` (Pfad zur Game-Installation)
- `instance_path` = `self._instance_path` (Pfad zur Anvil-Instanz)

Diese entsprechen exakt der Signatur von `PluginsTxtWriter.__init__()` (plugins_txt_writer.py Zeile 27-35). Alle drei Werte sind durch die if-Bedingung davor als nicht-None gesichert.

### write()-Aufruf

**Befund: KORREKT**

```python
result_path = writer.write()
if result_path is None:
    print("[GamePanel] plugins.txt write failed or skipped", flush=True)
self._refresh_plugins_tab()
```

- `writer.write()` wird tatsaechlich aufgerufen (Zeile 600).
- Das Ergebnis wird in `result_path` gespeichert und bei `None` geloggt (neu hinzugefuegt im aktuellen Diff).
- `_refresh_plugins_tab()` wird danach IMMER aufgerufen -- auch bei fehlgeschlagenem Write. Das ist korrekt, da der Tab den aktuellen Scan-Stand der Data/-Dateien zeigen soll (unabhaengig ob plugins.txt geschrieben wurde).

### Bedingungen

**Befund: KORREKT, aber mit Anmerkung**

```python
if (
    self._current_plugin is not None
    and hasattr(self._current_plugin, "has_plugins_txt")
    and self._current_plugin.has_plugins_txt()
    and self._current_game_path is not None
    and self._instance_path is not None
):
```

Die 5 Bedingungen im Detail:

| Nr. | Bedingung | Zweck | Bewertung |
|-----|-----------|-------|-----------|
| 1 | `self._current_plugin is not None` | Plugin geladen | OK |
| 2 | `hasattr(self._current_plugin, "has_plugins_txt")` | Sicherheitscheck | Redundant (siehe Anmerkung) |
| 3 | `self._current_plugin.has_plugins_txt()` | Bethesda-Spiel? | OK -- prueft `bool(PRIMARY_PLUGINS)` |
| 4 | `self._current_game_path is not None` | Game-Pfad bekannt | OK |
| 5 | `self._instance_path is not None` | Instanz-Pfad bekannt | OK |

**Anmerkung zu Bedingung 2**: `hasattr(self._current_plugin, "has_plugins_txt")` ist technisch redundant, da `has_plugins_txt()` in `BaseGame` (base_game.py Zeile 361) definiert ist und ALLE Game-Plugins von `BaseGame` erben. Jedoch ist es als defensiver Check akzeptabel -- falls jemals ein Plugin-Objekt NICHT von BaseGame erbt. Severity: Kein Bug, nur unnoetig.

### Datenfluss deploy -> write

1. `silent_deploy()` wird aufgerufen (von MainWindow)
2. `self._deployer.deploy()` deployt Mods per Symlinks (Zeile 550)
3. plugins.txt-Block startet (Zeile 590) -- UNABHAENGIG vom Deploy-Ergebnis
4. PluginsTxtWriter wird instanziiert (Zeile 597-599)
5. `writer.write()` wird aufgerufen (Zeile 600):
   a. `plugins_txt_path()` auf dem Game-Plugin aufgerufen -> Proton-Prefix-Pfad
   b. `scan_plugins()` scannt game_path/Data/ nach .esp/.esm/.esl
   c. Datei wird geschrieben mit `*`-Prefix (alle aktiv)
6. `_refresh_plugins_tab()` aktualisiert die UI (Zeile 603)

**WICHTIG**: Der plugins.txt-Block (Zeile 590-603) hat KEINE Abhaengigkeit vom Deploy-Ergebnis (`result`). Das ist GEWOLLT und KORREKT -- plugins.txt wird immer geschrieben wenn ein Bethesda-Spiel aktiv ist, da die Plugins aus dem originalen Data/-Verzeichnis gescannt werden, nicht aus dem Deploy-Ziel. Die Plugins (.esm/.esp) liegen immer im Game-Verzeichnis, unabhaengig davon ob Mods deployed sind.

---

## Methode: silent_purge() (Zeilen 605-634)

### Writer-Initialisierung

**Befund: KORREKT**

```python
writer = PluginsTxtWriter(
    self._current_plugin, self._current_game_path, self._instance_path
)
```

Identisch zum deploy-Fall. Alle drei Parameter sind durch die vorherige if-Bedingung gesichert.

### plugins.txt Entfernung

**Befund: KORREKT**

```python
writer.remove()
```

- `writer.remove()` wird aufgerufen (Zeile 634).
- `remove()` in plugins_txt_writer.py (Zeile 160-174):
  1. Holt `txt_path` via `self._game_plugin.plugins_txt_path()`
  2. Wenn `txt_path is None` -> gibt `True` zurueck (kein Pfad = nichts zu loeschen)
  3. Ruft `_remove_case_variants()` auf (NEU: entfernt z.B. `Plugins.txt`, `PLUGINS.TXT`)
  4. Wenn die Datei existiert -> `txt_path.unlink()` loescht sie
  5. OSError wird abgefangen und geloggt

### Bedingungen

```python
if (
    self._current_plugin is not None
    and hasattr(self._current_plugin, "has_plugins_txt")
    and self._current_plugin.has_plugins_txt()
    and self._current_game_path is not None
    and self._instance_path is not None
):
```

Identisch mit den Bedingungen in `silent_deploy()` -- gleiche Bewertung: KORREKT.

### Fehlender _refresh_plugins_tab()-Aufruf

**Befund: silent_purge() ruft _refresh_plugins_tab() NICHT auf.**

Analyse der Aufrufer in mainwindow.py:

| Stelle | Code | Danach folgt... | Problem? |
|--------|------|-----------------|----------|
| Zeile 803 | `silent_purge()` bei Instanz-Wechsel | `update_game()` Zeile 842 -> dort `_refresh_plugins_tab()` | NEIN |
| Zeile 2211 | `silent_purge()` bei Profil-Wechsel | `silent_deploy()` Zeile 2213 -> dort `_refresh_plugins_tab()` | NEIN |
| Zeile 3057 | `silent_purge()` bei App-Close | App wird geschlossen | NEIN |

Aktuell kein praktisches Problem, da nach jedem Purge entweder ein Deploy oder ein App-Close folgt. Aber wenn `silent_purge()` in Zukunft allein aufgerufen wird (z.B. "Purge-only"-Button), wuerden veraltete Daten im Plugins-Tab stehen bleiben.

---

## Weitere Findings

### [LOW] Redundantes hasattr-Check

- **Datei**: `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py` Zeilen 592, 626, 672, 403
- **Problem**: `hasattr(self._current_plugin, "has_plugins_txt")` ist immer True, da alle Plugins von BaseGame erben und BaseGame die Methode definiert (base_game.py:361).
- **Auswirkung**: Keine -- nur toter Code.
- **Fix**: Kann entfernt werden, ist aber als defensiver Check akzeptabel.

### [LOW] Kein _refresh_plugins_tab() in silent_purge()

- **Datei**: `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py` Zeile 605-634
- **Problem**: Nach dem Loeschen der plugins.txt wird der Plugins-Tab nicht aktualisiert. Aktuell kein Problem, da immer ein Deploy oder App-Close folgt.
- **Auswirkung**: Zukuenftiges Risiko bei isoliertem Purge-Aufruf.
- **Fix**: `self._refresh_plugins_tab()` am Ende von `silent_purge()` aufrufen (nach dem Writer-Block, oder besser: `self._plugins_tree.clear()` wenn die Datei geloescht wurde).

### [LOW] writer.remove() Rueckgabewert wird ignoriert

- **Datei**: `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py` Zeile 634
- **Problem**: `writer.remove()` gibt `True`/`False` zurueck, aber der Rueckgabewert wird ignoriert. Im Gegensatz dazu loggt `silent_deploy()` einen Fehler bei `result_path is None`.
- **Auswirkung**: Fehlgeschlagene Loesch-Operationen werden nicht im GamePanel-Log bemerkt (nur im Writer-internen print).
- **Fix**: Analog zu deploy: `if not writer.remove(): print("[GamePanel] plugins.txt remove failed", flush=True)`

### [MEDIUM] plugins.txt wird auch geschrieben wenn Deploy fehlschlaegt

- **Datei**: `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py` Zeile 589-603
- **Problem**: Der plugins.txt-Block ist NICHT an `result.success` gebunden (im Gegensatz zum BA2-Block in Zeile 554-557). Das bedeutet: Wenn `self._deployer.deploy()` fehlschlaegt oder `self._deployer` None ist, wird plugins.txt trotzdem geschrieben.
- **Bewertung**: Dies ist vermutlich GEWOLLT -- plugins.txt reflektiert die Plugins im originalen Data/-Ordner, nicht die deployed Mods. Bethesda-Spiele brauchen plugins.txt auch ohne Mod-Deployment. **Deshalb MEDIUM statt HIGH** -- es sollte dokumentiert/bestaetigt werden, ob dieses Verhalten beabsichtigt ist.
- **Analyse**: Die Game-Plugins (.esm/.esp) liegen immer im Spiel-Verzeichnis unter Data/. Sie sind keine deploybaren Mods (die liegen im mods-Verzeichnis). Insofern ist es logisch korrekt, plugins.txt unabhaengig vom Mod-Deploy zu schreiben. **Herabstufung auf LOW empfohlen.**

### [INFO] Neue _remove_case_variants() ist solide implementiert

- **Datei**: `/home/mob/Projekte/Anvil Organizer/anvil/core/plugins_txt_writer.py` Zeilen 40-64
- **Bewertung**: Korrekte Implementierung:
  - Prueft ob parent-Dir existiert
  - Case-insensitiver Vergleich: `entry.name.lower() == target_name_lower`
  - Exact-match ausgeschlossen: `entry.name != txt_path.name`
  - Doppelter OSError-try/except (Scan + einzelne Datei)
  - Loescht nur Dateien, keine Verzeichnisse
  - Kein Risiko versehentlich die richtige Datei zu loeschen

---

## Fazit

Der Datenfluss von `silent_deploy()` bis zum tatsaechlichen Schreiben der plugins.txt ist **korrekt und vollstaendig**:

1. Writer wird mit geprueften, nicht-None Parametern initialisiert
2. `writer.write()` wird aufgerufen und das Ergebnis geprueft
3. Die Bedingungskette ist lueckenlos (Plugin != None, hat plugins_txt, Game-Pfad != None, Instanz-Pfad != None)
4. Der Writer scannt korrekt Data/ und schreibt mit CRLF + UTF-8 + *-Prefix
5. Case-Varianten werden vor dem Schreiben bereinigt

Der Datenfluss von `silent_purge()` bis zum Loeschen der plugins.txt ist ebenfalls **korrekt**:

1. Writer wird identisch initialisiert
2. `writer.remove()` wird aufgerufen
3. Die Datei wird korrekt geloescht inkl. Case-Varianten

**Gefundene Probleme**: 0 CRITICAL, 0 HIGH, 1 MEDIUM (zu klaeren), 3 LOW

**Bewertung: KEIN BLOCKER -- Code ist funktional korrekt.**
