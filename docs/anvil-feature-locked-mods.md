# Feature: Locked Mods (Mod-Sperre)

Datum: 2026-03-26

## Zusammenfassung

Mods koennen vom User als "gesperrt" markiert werden. Gesperrte Mods sind IMMER aktiviert und koennen nicht per Checkbox, Kontextmenue oder Bulk-Aktion deaktiviert werden. Die Reihenfolge (DnD) bleibt aenderbar. Der Lock-Status wird pro Instanz in `locked_mods.json` gespeichert.

MO2 hat kein manuelles "Lock Mod" Feature — dort ist es nur automatisch/typ-basiert (Foreign Mods, alwaysEnabled). Anvil geht hier bewusst ueber MO2 hinaus.

---

## User Stories

- Als User moechte ich kritische Mods (z.B. Patches, Compatibility-Fixes) sperren, damit sie nicht versehentlich deaktiviert werden.
- Als User moechte ich per Rechtsklick eine Mod sperren/entsperren koennen.
- Als User moechte ich visuell erkennen, welche Mods gesperrt sind (Lock-Icon statt Checkbox).
- Als User moechte ich gesperrte Mods weiterhin per DnD verschieben koennen (Reihenfolge aendern).
- Als User moechte ich im Filter-Panel nach gesperrten Mods filtern koennen.
- Als User moechte ich, dass "Alle deaktivieren" gesperrte Mods ueberspringt.
- Als User moechte ich bei Loeschversuch einer gesperrten Mod eine extra Warnung sehen.

---

## Technische Entscheidungen

| Thema | Entscheidung | Begruendung |
|-------|-------------|-------------|
| Scope | Pro Instanz (global) | Lock gilt fuer alle Profile einer Instanz |
| Persistierung | `locked_mods.json` | KEIN `*`-Prefix in modlist.txt — sauberer, MO2-kompatibel |
| Speicherort | `<instanz>/.profiles/locked_mods.json` | Neben modlist.txt und active_mods.json |
| DnD | ERLAUBT fuer gesperrte Mods | Lock = nur Aktivierungsstatus, nicht Position |
| Deployer | NICHT aendern | Locked Mods IMMER in active_mods.json → Deployer greift automatisch |
| Icon | Schloss-Symbol (QPainter) | Kein SVG noetig — konsistent mit bestehendem Design |

---

## Betroffene Dateien

| Datei | Aenderung |
|-------|-----------|
| `anvil/core/mod_list_io.py` | `read_locked_mods()`, `write_locked_mods()`, rename/remove erweitern |
| `anvil/core/mod_entry.py` | `is_locked: bool = False` in ModEntry, scan erweitern |
| `anvil/models/mod_list_model.py` | `ROLE_IS_LOCKED`, ModRow.is_locked, setData/flags Guards |
| `anvil/widgets/mod_list.py` | Lock-Icon in CheckboxDelegate, editorEvent Guard |
| `anvil/widgets/filter_panel.py` | `PROP_LOCKED` Chip |
| `anvil/mainwindow.py` | Kontextmenue, _ctx_lock_mods(), 4 Guards |
| `anvil/locales/*.json` | 7 neue Keys in 7 Sprachen |

---

## Persistierung

### Datei: `<instanz>/.profiles/locked_mods.json`

```json
[
  "Important Patch",
  "Compatibility Fix"
]
```

JSON-Array mit sortierten Mod-Ordnernamen (analog zu active_mods.json).

### Neue Funktionen in mod_list_io.py

```python
def read_locked_mods(profiles_dir: Path) -> set[str]:
def write_locked_mods(profiles_dir: Path, locked_mods: set[str]) -> None:
```

---

## UI-Aenderungen

### 1. CheckboxDelegate.paint() — Lock-Icon
- Farbe: `#FFB300` (Amber/Gold)
- Groesse: 16x16px
- Form: Schlosskoerper + Buegel per QPainter

### 2. CheckboxDelegate.editorEvent() — Klick blockieren
```python
is_locked = index.data(ROLE_IS_LOCKED)
if is_locked:
    return True  # Event konsumiert, keine Aktion
```

### 3. Kontextmenue — Neuer Eintrag
Position: Nach "Deaktiviere Ausgewaehlte", vor Separator.
Text dynamisch: "Mod sperren" / "Mod entsperren" / "Sperre umschalten"

### 4. Filter-Panel — Neuer Chip
`PROP_LOCKED = -9` → Chip "Gesperrt"

---

## Guards (8 Stellen)

| # | Stelle | Zweck |
|---|--------|-------|
| 1 | `ModListModel.setData()` | Primaer: locked → return False |
| 2 | `ModListModel.flags()` | Kein ItemIsUserCheckable fuer locked |
| 3 | `CheckboxDelegate.editorEvent()` | Klick auf Lock-Icon ignorieren |
| 4 | `MainWindow._on_mod_toggled()` | Sekundaer: falls Signal durchkommt |
| 5 | `MainWindow._ctx_enable_selected()` | Bulk: locked Mods ueberspringen |
| 6 | `MainWindow._apply_active_state()` | KRITISCH: Profil-Wechsel → locked=enabled |
| 7 | `MainWindow._write_current_modlist()` | locked immer in active_mods.json |
| 8 | `MainWindow._ctx_remove_mods()` | Extra Warnung bei Loeschversuch |

---

## Erweiterungen bestehender Funktionen

### rename_mod_globally() (mod_list_io.py)
```python
locked = read_locked_mods(profiles_dir)
if old_name in locked:
    locked.discard(old_name)
    locked.add(new_name)
    write_locked_mods(profiles_dir, locked)
```

### remove_mod_globally() (mod_list_io.py)
```python
locked = read_locked_mods(profiles_dir)
if mod_name in locked:
    locked.discard(mod_name)
    write_locked_mods(profiles_dir, locked)
```

### scan_mods_directory() (mod_entry.py)
```python
locked_mods = read_locked_mods(profiles_dir)
# In Entry-Erstellung:
if name in locked_mods:
    entry.is_locked = True
    entry.enabled = True
```

---

## Locale-Keys (7 Sprachen)

| Key | DE | EN |
|-----|----|----|
| `context.lock_mod` | Mod sperren | Lock Mod |
| `context.unlock_mod` | Mod entsperren | Unlock Mod |
| `context.toggle_lock` | Sperre umschalten | Toggle Lock |
| `filter.prop_locked` | Gesperrt | Locked |
| `dialog.remove_locked_warning` | Achtung: {count} Mods sind gesperrt! | Warning: {count} mods are locked! |
| `status.mod_locked` | Mod gesperrt: {name} | Mod locked: {name} |
| `status.mod_unlocked` | Mod entsperrt: {name} | Mod unlocked: {name} |

---

## Implementierungsreihenfolge

1. Persistierung — read/write_locked_mods() in mod_list_io.py
2. Datenmodell — is_locked in ModEntry und ModRow
3. Scan — scan_mods_directory() erweitern
4. Model — ROLE_IS_LOCKED, setData/flags Guards, data() erweitern
5. Delegate — Lock-Icon in paint(), Click-Guard in editorEvent()
6. Controller — Guards in MainWindow, neue _ctx_lock_mods()
7. Kontextmenue — Neuer Eintrag
8. Rename/Remove — locked_mods.json mit-updaten
9. Write-Guard — _write_current_modlist() erzwingt locked in active_mods
10. Filter — PROP_LOCKED Chip
11. Locales — 7 Keys in 7 Sprachen
12. Testen — restart.sh + manuelle Tests

---

## Akzeptanz-Checkliste

- [ ] 1. Wenn User per Rechtsklick "Mod sperren" waehlt, erscheint ein gold/amber Schloss-Icon anstelle der Checkbox.
- [ ] 2. Wenn User auf das Schloss-Icon klickt, passiert NICHTS — Mod bleibt aktiviert und gesperrt.
- [ ] 3. Wenn User per Rechtsklick "Mod entsperren" waehlt, verschwindet das Schloss und die normale Checkbox erscheint.
- [ ] 4. Wenn User "Deaktiviere alle" waehlt, werden gesperrte Mods uebersprungen.
- [ ] 5. Wenn User das Profil wechselt, bleiben gesperrte Mods aktiviert.
- [ ] 6. Wenn User eine gesperrte Mod loeschen will, erscheint eine extra Warnung.
- [ ] 7. Wenn User eine gesperrte Mod umbenennt, bleibt der Lock erhalten.
- [ ] 8. Wenn User Anvil neu startet, sind gesperrte Mods weiterhin gesperrt (Persistenz).
- [ ] 9. Wenn User den "Gesperrt"-Filter aktiviert, werden nur gesperrte Mods angezeigt.
- [ ] 10. Wenn User mehrere Mods selektiert und "Sperre umschalten" waehlt, werden alle getoggelt.
- [ ] 11. Wenn User eine gesperrte Mod per DnD verschiebt, bleibt der Lock erhalten.
- [ ] 12. Wenn User "Aktiviere Ausgewaehlte" auf gemischte Selektion anwendet, werden nur normale Mods geaendert.
- [ ] 13. Deploy deployed gesperrte Mods IMMER, unabhaengig von active_mods.json.
- [ ] 14. Wenn kein locked_mods.json existiert, startet Anvil ohne Fehler.
- [ ] 15. Rechtsklick auf Separator zeigt KEINEN "Sperren"-Eintrag.
- [ ] 16. `restart.sh` startet ohne Fehler.
