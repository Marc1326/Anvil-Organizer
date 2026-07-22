# Feature: Modlist Bug-Fixes (Neustart + Multi-Select DnD)
Datum: 2026-03-09

## User Stories
- Als User moechte ich, dass per DnD installierte Mods nach einem Neustart sichtbar bleiben
- Als User moechte ich, dass Separatoren bei Multi-Select DnD nicht verschwinden

---

## Bug 1: Mods verschwinden nach Neustart

### Analyse
Nach DnD-Install wird der Mod korrekt in die globale `modlist.txt` geschrieben (Fix a5ee918).
Das Problem liegt in `_on_mods_reordered()` (mainwindow.py:1091-1100):

```python
for entry in self._current_mod_entries:
    display = entry.display_name or entry.name
    if display == row_data.name and entry not in new_entries:
```

Das Matching verwendet `display_name or name` als Key. Wenn zwei Mods denselben
display_name haben, wird der zweite Mod nicht gefunden und aus `_current_mod_entries`
gedroppt. `_write_current_modlist()` schreibt dann eine modlist.txt OHNE den
verlorenen Mod. Nach Neustart fehlt er.

Auch `_on_mod_toggled()` (mainwindow.py:1067-1070) hat dasselbe fragile Matching.

### Fix-Strategie
`folder_name` (= `entry.name` = Ordnername) ist IMMER eindeutig. Matching umstellen
auf `row_data.folder_name == entry.name`. Betrifft:
- `_on_mods_reordered()` (Zeile 1095-1097)
- `_on_mod_toggled()` (Zeile 1067-1069)

---

## Bug 2: Separator verschwindet bei Multi-Select DnD

### Root Cause (Agent 2)
Der Qt DnD-Flow bei `MoveAction`:
1. `dropMimeData()` verschiebt Mods korrekt via `_move_multiple_rows()`
2. `dropMimeData()` gibt `True` zurueck
3. Qt ruft danach `removeRows()` auf den **alten** Quell-Indizes auf
4. `QSortFilterProxyModel::removeRows()` ruft intern `beginRemoveRows()`/`endRemoveRows()`
5. Unser `removeRows()` gibt `True` zurueck (No-Op, aber `True`)
6. Der Proxy interpretiert `True` als "Rows erfolgreich entfernt" und entfernt sie aus seinem Mapping
7. Der Separator verschwindet aus der View, obwohl er im Source Model noch existiert

### Fix-Strategie
`removeRows()` in `mod_list_model.py` Zeile 559-564: Statt `True` muss `False`
zurueckgegeben werden. `False` verhindert, dass der Proxy `beginRemoveRows`/`endRemoveRows`
ausfuehrt.

---

## Technische Planung

### Betroffene Dateien
| Datei | Aenderung |
|-------|-----------|
| `anvil/models/mod_list_model.py` Z.559-564 | `removeRows()`: return `False` statt `True` |
| `anvil/mainwindow.py` Z.1091-1100 | `_on_mods_reordered()`: Matching per `folder_name` |
| `anvil/mainwindow.py` Z.1067-1070 | `_on_mod_toggled()`: Matching per `folder_name` |

### Signal-Flow
```
DnD Multi-Select:
  dropMimeData() → _move_multiple_rows() → layoutChanged → _update_priorities()
    → mods_reordered.emit() → _on_mods_reordered() → _write_current_modlist()
  Qt: removeRows() → return False (KEIN Proxy-Mapping-Update)

DnD Install:
  _install_archives() → write_global_modlist() → _reload_mod_list()
    → scan_mods_directory() → set_mods() → UI aktualisiert
  Spaeter: _on_mods_reordered() → folder_name-Matching → alle Entries erhalten
```

---

## Akzeptanz-Kriterien (ALLE muessen erfuellt sein)

- [ ] K1: Wenn User per DnD einen Mod installiert und Anvil neustartet, ist der Mod in der Mod-Liste sichtbar
- [ ] K2: Wenn User mehrere Mods selektiert und per DnD in einen Separator verschiebt, bleibt der Separator sichtbar
- [ ] K3: Wenn User mehrere Mods selektiert (inkl. Separator) und per DnD verschiebt, bleibt der Separator sichtbar
- [ ] K4: Wenn User einen einzelnen Mod per DnD verschiebt, funktioniert das weiterhin korrekt
- [ ] K5: Wenn User einen Separator-Block per DnD verschiebt, funktioniert das weiterhin korrekt
- [ ] K6: Wenn User eine Mod-Checkbox toggled, wird der korrekte Mod aktiviert/deaktiviert (folder_name-Matching)
- [ ] K7: Wenn User Mods reordert, bleiben ALLE Mods in _current_mod_entries erhalten (kein Entry-Verlust)
- [ ] K8: Wenn zwei Mods denselben display_name haben, werden beide korrekt gematcht (folder_name ist eindeutig)
- [ ] K9: `_on_mod_toggled()` verwendet folder_name statt display_name fuer Matching
- [ ] K10: `removeRows()` gibt False zurueck wenn `_drop_in_progress` ist
- [ ] K11: `python -m py_compile anvil/models/mod_list_model.py` ohne Fehler
- [ ] K12: `python -m py_compile anvil/mainwindow.py` ohne Fehler
- [ ] K13: `./restart.sh` startet ohne Fehler
