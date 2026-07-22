# Feature: Bundle/Group Mods (Issue #66)
Datum: 2026-03-26

## Zusammenfassung

Mods koennen innerhalb von Separatoren zu **Bundles/Gruppen** zusammengefasst werden. Gruppen sind ein visuelles Ordnungsmittel (zweite Hierarchie-Ebene unter Separatoren), das den User bei der Organisation grosser Modlisten unterstuetzt. Gruppen haben KEINEN Einfluss auf Deployment, Prioritaet oder modlist.txt — sie sind rein UI-basiert.

**Alleinstellungsmerkmal:** MO2 hat KEIN Bundle/Group-Feature. Anvils Bundle-Feature waere ein echtes Unterscheidungsmerkmal.

## User Stories

- Als User moechte ich mehrere zusammengehoerige Mods zu einer Gruppe zusammenfassen, damit ich auf einen Blick sehe was zusammengehoert.
- Als User moechte ich eine Gruppe per Kontextmenue erstellen, indem ich mehrere Mods selektiere und "Gruppe erstellen" waehle.
- Als User moechte ich eine Gruppe ein-/ausklappen koennen (analog zu Separatoren).
- Als User moechte ich eine Gruppe umbenennen und aufloesen koennen.
- Als User moechte ich eine Gruppe als Ganzes per DnD verschieben (alle Member bewegen sich mit).
- Als User moechte ich die Gruppe visuell unterscheiden (Einrueckung + farbiger linker Rand).
- Als User moechte ich, dass Gruppen ueber Neustart hinweg erhalten bleiben.

## Technische Planung

### Design-Entscheidung: FLACHE LISTE beibehalten

Kein Umbau zu Parent/Child. Gruppen werden ueber Metadaten (groups.json + meta.ini) und visuell per Custom Delegate dargestellt.

### Speicherformat

**groups.json** (pro Instanz, im Profil-Ordner `.profiles/`):
```json
{
  "version": 1,
  "groups": {
    "Armor Collection": {
      "color": "#4FC3F7",
      "collapsed": false,
      "members": ["Cool Armor Mod", "Cool Armor Patch", "Cool Armor Textures"]
    }
  }
}
```

**Regeln:**
- `members` enthaelt Ordner-Namen (nicht Display-Namen)
- Ein Mod kann nur zu einer Gruppe gehoeren
- Verschachtelte Gruppen sind verboten
- Gruppen koennen nicht separator-uebergreifend sein
- modlist.txt wird NICHT geaendert

### Neue Dateien

| Datei | Zweck | Zeilen |
|-------|-------|--------|
| `anvil/core/mod_groups.py` | GroupManager: CRUD fuer groups.json | ~200 |

### Geaenderte Dateien

| Datei | Aenderung | Aufwand |
|-------|-----------|--------|
| `anvil/core/mod_entry.py` | Neues Feld `group: str = ""` | MINIMAL |
| `anvil/models/mod_list_model.py` | ROLE_GROUP_NAME, ROLE_IS_GROUP_HEAD, `_get_group_members()`, `_move_group_block()`, data() | HOCH |
| `anvil/widgets/mod_list.py` | Group-Collapse, Delegate-Erweiterung, Selection | MITTEL |
| `anvil/mainwindow.py` | Kontextmenue, GroupManager, save/load | HOCH |
| 7 Locale-Dateien | ~15 neue tr()-Keys | KLEIN |

**NICHT betroffen:** mod_deployer.py, conflict_scanner.py, mod_list_io.py, Game-Plugins

### Signal-Flow

#### Gruppe erstellen
```
User selektiert 3 Mods → Rechtsklick → "Gruppe erstellen..."
  → MainWindow._ctx_create_group()
    → QInputDialog.getText()
    → GroupManager.create_group(name, members)
    → ModEntry.group setzen
    → ModListModel dataChanged emit
```

#### Gruppe ein-/ausklappen
```
User klickt auf Group-Head
  → _collapsed_groups toggle
  → _apply_separator_filter() (erweitert fuer Gruppen)
  → ModListProxyModel.set_hidden_rows()
```

#### Gruppe als Block verschieben
```
User zieht Group-Head per DnD
  → dropMimeData() erkennt Group-Head
  → _move_group_block() (analog _move_separator_block)
```

### GUI-Design

```
[Weapons_separator]
  ▾ Armor Collection              ← Group-Head (Einrueckung, farbiger Rand)
    │ Cool Armor Mod              ← Member (doppelt eingereekt, farbige Linie)
    │ Cool Armor Patch            ← Member
    │ Cool Armor Textures         ← Member
  Another Standalone Mod          ← Normaler Mod
  ▸ Weather Bundle (2)            ← Eingeklappte Gruppe
[Next_separator]
```

## Risiken

| # | Risiko | Schwere | Mitigation |
|---|--------|---------|------------|
| R1 | Gruppe ueber Separator-Grenze | HOCH | Validierung: Mod aus Gruppe entfernen wenn ueber Grenze gezogen |
| R2 | DnD Block auf Separator-Grenze | HOCH | Block-Move nur innerhalb Separator |
| R3 | Mod loeschen in Gruppe | MITTEL | cleanup_orphans(), Auto-Aufloesen bei letztem Member |
| R4 | Konsistenz meta.ini vs groups.json | MITTEL | groups.json ist Source of Truth |
| R5 | Filter zeigt Member aber nicht Head | NIEDRIG | Head sichtbar wenn Member sichtbar |

## Locale-Keys (alle 7 Sprachen)

| Key | DE | EN |
|-----|----|----|
| `context.create_group` | "Gruppe erstellen..." | "Create group..." |
| `context.dissolve_group` | "Gruppe aufloesen" | "Dissolve group" |
| `context.rename_group` | "Gruppe umbenennen..." | "Rename group..." |
| `context.add_to_group` | "Zur Gruppe hinzufuegen" | "Add to group" |
| `context.remove_from_group` | "Aus Gruppe entfernen" | "Remove from group" |
| `context.group_color` | "Gruppenfarbe aendern..." | "Change group color..." |
| `dialog.create_group_title` | "Gruppe erstellen" | "Create Group" |
| `dialog.create_group_prompt` | "Name der neuen Gruppe:" | "Name for new group:" |
| `dialog.group_name_exists` | "Gruppe mit diesem Namen existiert bereits." | "Group with this name already exists." |
| `dialog.group_cross_separator` | "Alle Mods muessen im selben Trenner liegen." | "All mods must be in the same separator." |
| `dialog.dissolve_confirm` | "Gruppe '{name}' aufloesen? Die Mods bleiben erhalten." | "Dissolve group '{name}'? Mods will be kept." |
| `dialog.rename_group_title` | "Gruppe umbenennen" | "Rename Group" |
| `dialog.rename_group_prompt` | "Neuer Name:" | "New name:" |
| `tooltip.group_collapsed` | "{count} Mod(s) in Gruppe" | "{count} mod(s) in group" |
| `dialog.group_already_member` | "'{mod}' ist bereits in Gruppe '{group}'." | "'{mod}' is already in group '{group}'." |

## Akzeptanz-Kriterien

- [ ] 1. Wenn User 3 Mods innerhalb eines Separators selektiert und "Gruppe erstellen..." waehlt, erscheint ein Eingabedialog. Nach Eingabe werden die 3 Mods visuell als Gruppe dargestellt (Einrueckung + farbiger Rand).
- [ ] 2. Wenn User auf den Group-Head klickt, klappt die Gruppe ein — nur der Head ist sichtbar mit Member-Count. Erneuter Klick klappt aus.
- [ ] 3. Wenn User den Group-Head per DnD innerhalb des Separators verschiebt, bewegen sich alle Members als Block mit.
- [ ] 4. Wenn User einen einzelnen Mod per DnD aus der Gruppe heraus zieht, wird er aus der Gruppe entfernt.
- [ ] 5. Wenn User "Gruppe aufloesen" waehlt, verschwinden Einrueckung und Farbrand, Mods bleiben an Position.
- [ ] 6. Wenn User Mods aus verschiedenen Separatoren gruppieren will, erscheint Fehlermeldung.
- [ ] 7. Wenn User einen Mod loescht der in einer Gruppe ist, wird die Gruppe aktualisiert. Letzter Member → Gruppe aufgeloest.
- [ ] 8. Wenn User "Zur Gruppe hinzufuegen" waehlt, erscheint der Mod als Teil der Gruppe.
- [ ] 9. Wenn User Anvil schliesst und oeffnet, sind alle Gruppen erhalten (groups.json).
- [ ] 10. Wenn Text-Filter aktiv und ein Member den Filter passiert, ist der Group-Head auch sichtbar.
- [ ] 11. Wenn User eine Gruppe umbenennt, wird der Name in GUI, groups.json und meta.ini aktualisiert.
- [ ] 12. Wenn Sortierung nach Name/Kategorie aktiv, werden Gruppen NICHT zusammengehalten.
- [ ] 13. Wenn ein Member ueber Separator-Grenze gezogen wird, wird er aus der Gruppe entfernt.
- [ ] 14. Wenn Gruppenname bereits existiert, erscheint Fehlermeldung.
- [ ] 15. Alle 15 Locale-Keys sind in allen 7 Sprach-Dateien vorhanden.
- [ ] 16. `restart.sh` startet ohne Fehler.
