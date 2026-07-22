# Feature: Mehrfachauswahl und Verschieben von Mods
Datum: 2026-03-08

## User Stories
- Als User moechte ich mehrere Mods gleichzeitig per Drag & Drop verschieben, damit ich meine Mod-Liste schnell reorganisieren kann
- Als User moechte ich mehrere Mods ueber das Kontextmenue in einen bestimmten Trenner verschieben, damit ich Mods thematisch gruppieren kann
- Als User moechte ich, dass die relative Reihenfolge meiner selektierten Mods beim Verschieben erhalten bleibt, damit keine ungewollten Prioritaetswechsel entstehen

## Technische Planung

### Betroffene Dateien

| Datei | Aenderung | Zeilennummern |
|-------|-----------|---------------|
| `anvil/models/mod_list_model.py` | Neue Methode `_move_multiple_rows()`, Aenderung `dropMimeData()` | Z.406-442 (dropMimeData), neu nach Z.459 |
| `anvil/mainwindow.py` | "In Trenner verschieben" Submenu + Handler `_ctx_move_to_separator()` | Z.1777 (send_to_menu), Z.1819 (chosen-Block) |
| `anvil/widgets/mod_list.py` | `_apply_separator_filter()` wird ueber `mods_reordered` automatisch getriggert | Z.373 (bestehend) |
| Locale-Dateien (7x) | Keys: `context.move_to_separator` | Neu |

### Detaillierte Implementierung

#### 1. `_move_multiple_rows()` in `mod_list_model.py`

Neue Methode nach `_move_single_row()` (nach Zeile 459):

```python
def _move_multiple_rows(self, source_rows: list[int], target: int) -> bool:
```

**Algorithmus:**
1. Separatoren aus der source_rows-Liste herausfiltern (nur Mods verschieben)
2. Extrahierte ModRows in Originalreihenfolge speichern: `extracted = [(row, self._rows[row]) for row in sorted(source_rows)]`
3. Alle source_rows aus `self._rows` entfernen — **von hinten nach vorne** (absteigende Reihenfolge), damit Indizes stabil bleiben
4. Target-Position anpassen: Fuer jeden entfernten Row < target, target um 1 reduzieren
5. Extrahierte Rows an angepasster Target-Position in Originalreihenfolge einfuegen
6. `_update_priorities()` aufrufen

**Wichtig:** `beginMoveRows()` kann NICHT fuer nicht-zusammenhaengende Zeilen verwendet werden. Stattdessen:
```python
self.layoutAboutToBeChanged.emit()
# ... Zeilen umordnen ...
self.layoutChanged.emit()
```

#### 2. Aenderung `dropMimeData()` (Zeile 435-442)

Ersetze den aktuellen Block:
```python
source_row = source_rows[0]
if self._rows[source_row].is_separator:
    return self._move_separator_block(source_row, target)
return self._move_single_row(source_row, target)
```

Durch:
```python
if len(source_rows) == 1:
    source_row = source_rows[0]
    if self._rows[source_row].is_separator:
        return self._move_separator_block(source_row, target)
    return self._move_single_row(source_row, target)
else:
    # Mehrfachauswahl: Separatoren herausfiltern, nur Mods verschieben
    mod_rows = [r for r in source_rows if not self._rows[r].is_separator]
    if not mod_rows:
        return False
    return self._move_multiple_rows(mod_rows, target)
```

#### 3. Neue Hilfsmethode `get_all_separators()` in `mod_list_model.py`

```python
def get_all_separators(self) -> list[tuple[int, str, str]]:
    """Return list of (source_row, folder_name, display_name) for all separators."""
```

#### 4. Kontextmenue "In Trenner verschieben" in `mainwindow.py`

Ersetze den deaktivierten `send_to_menu` (Zeile 1777-1778) durch ein aktives Submenu mit Trenner-Liste:
```python
move_to_sep_menu = menu.addMenu(tr("context.move_to_separator"))
separators = self._mod_list_view.source_model().get_all_separators()
if separators and has_selection:
    for sep_row, sep_folder, sep_name in separators:
        act_sep = move_to_sep_menu.addAction(sep_name)
        act_sep.setData(sep_folder)
else:
    move_to_sep_menu.setEnabled(False)
```

#### 5. Neue Methode `_ctx_move_to_separator()` in `mainwindow.py`

```python
def _ctx_move_to_separator(self, source_rows: list[int], separator_folder: str) -> None:
```

**Algorithmus:**
1. Separator-Position im Model finden (nach `folder_name`)
2. Kinder des Ziel-Separators ermitteln via `_get_separator_children(sep_row)`
3. Target-Position = letzte Kind-Position + 1 (= Ende des Separators)
4. Falls Separator keine Kinder hat: Target = sep_row + 1
5. Separatoren und Mods die bereits im Ziel-Trenner sind herausfiltern
6. `model._move_multiple_rows(filtered_rows, target)` aufrufen

### Signal-Flow

#### DnD-Mehrfachverschiebung:
```
User: Strg+Klick mehrere Mods → Drag & Drop
  ↓
_DropTreeView: Standard-Qt-DnD-Handling
  ↓
ModListModel.mimeData()         — serialisiert ALLE selektierten Source-Row-Indizes
  ↓
ModListModel.dropMimeData()     — erkennt len(source_rows) > 1
  ↓
ModListModel._move_multiple_rows()
  ↓
layoutAboutToBeChanged → Zeilen umordnen → layoutChanged
  ↓
_update_priorities() → mods_reordered.emit()
  ↓
MainWindow._on_mods_reordered()
  ↓
_write_current_modlist() + _schedule_redeploy()
```

#### Kontextmenue "In Trenner verschieben":
```
User: Rechtsklick → "In Trenner verschieben" → Trenner waehlen
  ↓
MainWindow._ctx_move_to_separator(selected_rows, separator_folder)
  ↓
ModListModel._move_multiple_rows(rows_to_move, target_position)
  ↓
[gleicher Flow wie DnD oben]
```

### MO2-Vergleich

| Aspekt | MO2 | Anvil (geplant) |
|--------|-----|-----------------|
| Selection Mode | `ExtendedSelection` | `ExtendedSelection` (bereits vorhanden) |
| Multi-DnD | `changeModPriority(rows, priority)` | `_move_multiple_rows()` — gleicher Ansatz |
| "Send to Separator" | `sendModsToSeparator()` mit ListDialog | Submenu direkt im Kontextmenue (einfacher) |
| Sortier-Logik | Erst absteigende, dann aufsteigende Prioritaeten | Extrahieren → Target anpassen → Einfuegen |
| Persistierung | Eigenes Prioritaetssystem | modlist.txt (invertiert) |

## Edge Cases

| Edge Case | Loesung |
|-----------|---------|
| Mods aus verschiedenen Trennern selektiert | Werden am Zielort zusammengefuegt |
| Separator mit selektiert bei DnD | Separatoren herausfiltern, nur Mods verschieben |
| Ziel-Trenner ist eingeklappt | Mods einfuegen; `_apply_separator_filter()` wird automatisch getriggert |
| Alle Mods eines Trenners verschoben | Trenner bleibt leer — kein Auto-Loeschen |
| Mod in eigenen Trenner verschieben | Herausfiltern — bereits vorhandene Mods werden uebersprungen |
| DnD waehrend Filter/Suche aktiv | Proxy→Source Mapping funktioniert bereits |
| Nur ein Mod bei DnD | Fallback auf bestehendes `_move_single_row()` |

## Abhaengigkeiten
- `ExtendedSelection` + `get_selected_source_rows()` — bereits vorhanden
- `_get_separator_children()` — bereits vorhanden (Z.156-167)
- `_update_priorities()` — bereits vorhanden (Z.510-521)
- `_on_mods_reordered()` — bereits vorhanden (Z.1085-1115)
- `_write_current_modlist()` + `_schedule_redeploy()` — bereits vorhanden

## Risiken

1. **`layoutChanged` statt `beginMoveRows`:** View-Reset — Selektion/Scroll gehen verloren. Mitigation: Scroll-Position vorher merken.
2. **Name-Matching in `_on_mods_reordered()`:** Problematisch bei Duplikaten. Bestehendes Problem, separates Ticket.
3. **Collapsed-State nach Verschiebung:** Wird automatisch ueber `mods_reordered` getriggert.

## ✅ Akzeptanz-Kriterien (ALLE muessen erfuellt sein)

- [ ] **AK-01:** Wenn User 3 Mods per Strg+Klick selektiert und per Drag & Drop an eine neue Position zieht, werden alle 3 Mods als Block verschoben und ihre relative Reihenfolge zueinander bleibt erhalten
- [ ] **AK-02:** Wenn User 5 Mods per Shift+Klick selektiert und per DnD nach oben zieht, landen alle 5 Mods an der Zielposition in der Originalreihenfolge
- [ ] **AK-03:** Wenn User Mods aus verschiedenen Trennern selektiert und per DnD verschiebt, werden alle selektierten Mods am Zielort zusammengefuegt
- [ ] **AK-04:** Wenn User eine Selektion bestehend aus Mods UND einem Separator per DnD zieht, werden nur die Mods verschoben und der Separator bleibt an seiner Position
- [ ] **AK-05:** Wenn User Rechtsklick auf selektierte Mods macht, erscheint im Kontextmenue "In Trenner verschieben" mit einem Submenu das alle vorhandenen Separator-Namen auflistet
- [ ] **AK-06:** Wenn User im Kontextmenue einen Trenner aus "In Trenner verschieben" waehlt, werden die selektierten Mods ans Ende der Kinder dieses Trenners verschoben
- [ ] **AK-07:** Wenn User Mods in einen eingeklappten Trenner verschiebt (per Kontextmenue), werden die Mods korrekt eingefuegt und sind sichtbar wenn der Trenner aufgeklappt wird
- [ ] **AK-08:** Wenn User Mods verschiebt die bereits im Ziel-Trenner sind (per Kontextmenue "In Trenner verschieben"), werden diese Mods uebersprungen und nicht doppelt eingefuegt
- [ ] **AK-09:** Wenn nach einer Mehrfachverschiebung die modlist.txt geoeffnet wird, spiegelt sie die neue Reihenfolge korrekt wider (inklusive invertierter Separator-Zuordnung)
- [ ] **AK-10:** Wenn nach einer Mehrfachverschiebung per DnD oder Kontextmenue ein automatischer Redeploy ausgeloest wird, wird `_schedule_redeploy()` genau einmal aufgerufen
- [ ] **AK-11:** Wenn keine Mods selektiert sind, ist "In Trenner verschieben" im Kontextmenue ausgegraut
- [ ] **AK-12:** Wenn keine Separatoren in der Modliste vorhanden sind, ist "In Trenner verschieben" im Kontextmenue ausgegraut
- [ ] **AK-13:** Wenn User nur einen einzelnen Mod per DnD verschiebt (ohne Mehrfachselektion), wird weiterhin das bestehende `_move_single_row()` verwendet (Rueckwaertskompatibilitaet)
- [ ] **AK-14:** Wenn User einen einzelnen Separator per DnD verschiebt, wird weiterhin `_move_separator_block()` verwendet (Rueckwaertskompatibilitaet)
- [ ] **AK-15:** Die Locale-Keys `context.move_to_separator` sind in allen 7 Sprachdateien (de, en, es, fr, it, pt, ru) vorhanden
- [ ] **AK-16:** Wenn nach einer Mehrfachverschiebung die Conflict-Icons in der Mod-Liste angezeigt werden, sind sie korrekt aktualisiert
- [ ] **AK-17:** `./restart.sh` startet ohne Fehler
