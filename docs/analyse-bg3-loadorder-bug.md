# BG3 Load Order Bug — Analyse

**Datum:** 2026-04-08
**Status:** ⚠️ Teilweise gefixt — Nachbesserung nötig
**Fix-Datum:** 2026-04-08 (reversed), 2026-04-09 (ModOrder-Block)
**Lösung:** Option A (reversed) + ModOrder-Block muss wieder in `_write_modsettings()` eingefügt werden

**KORREKTUR 2026-04-09:** Die ursprüngliche Analyse war in einem Punkt falsch:
BG3 braucht DOCH den `<ModOrder>`-Block in der modsettings.lsx!
Ohne ModOrder hängt BG3 bei 75% beim Level-Load (Deadlock).
Der reversed-Fix allein reicht nicht — ModOrder muss zusätzlich
wieder eingefügt werden (ebenfalls in reversed-Reihenfolge).
**Betroffene Dateien:**
- `anvil/core/bg3_mod_installer.py` → `_write_modsettings()`, `reorder_mods()`
- `anvil/mainwindow.py` → `_on_mods_reordered()`

---

## Zusammenfassung

Die BG3-Mod-Reihenfolge in Anvil wird **invertiert** in die `modsettings.lsx` geschrieben. Der Mod, der in Anvil ganz oben steht (höchste Priorität), wird in BG3 als erster geladen und damit von allen nachfolgenden Mods **überschrieben** — das ist das Gegenteil der gewünschten Wirkung.

---

## Wie BG3 die modsettings.lsx liest

BG3 nutzt **kein** separates `<ModOrder>`-Tag. Die Ladereihenfolge ergibt sich direkt aus der **Position der `<ModuleShortDesc>`-Einträge im `<Mods>`-Block**:

- **Erster Eintrag** = wird zuerst geladen = **niedrigste Priorität** (kann von späteren überschrieben werden)
- **Letzter Eintrag** = wird zuletzt geladen = **höchste Priorität** (überschreibt alles davor)

Das entspricht dem Prinzip "last writer wins".

---

## Wie Anvil die Reihenfolge schreibt

### Schritt 1: UI → `_on_mods_reordered()` (mainwindow.py)

```python
uuid_order = [
    r.folder_name for r in model._rows
    if not r.is_separator and r.folder_name
    and r.folder_name.lower() in bg3_active_uuids
]
self._bg3_installer.reorder_mods(uuid_order)
```

Die UUIDs werden **in UI-Reihenfolge** (oben → unten, Index 0 → N) übergeben.

### Schritt 2: `reorder_mods()` (bg3_mod_installer.py)

```python
header = current[:last_gustav_idx + 1]  # Gustav bleibt vorne
user_mods = [u for u in uuid_order if not is_base_game_mod(u)]
final_order = header + user_mods
```

Die User-Reihenfolge wird 1:1 hinter Gustav eingefügt.

### Schritt 3: `_write_modsettings()` (bg3_mod_installer.py)

```python
for uuid in final_order:
    ...
    mods_lines.append(self._mod_xml(attrs))
```

Die Mods werden **in `final_order`-Reihenfolge** in die XML geschrieben.

### Ergebnis

| Position | Anvil UI | modsettings.lsx | BG3 Ladereihenfolge |
|----------|----------|-----------------|---------------------|
| Oben (Index 0) | Höchste Priorität | 1. Eintrag (nach Gustav) | Wird **zuerst** geladen → **niedrigste** Priorität |
| Unten (Index N) | Niedrigste Priorität | Letzter Eintrag | Wird **zuletzt** geladen → **höchste** Priorität |

**→ Invertiert!**

---

## Konkretes Beispiel

```
Anvil UI (oben = höchste Prio):     modsettings.lsx (oben = zuerst geladen):
  1. BG3aF      ← soll gewinnen       GustavDev
  2. BG3Sx                             BG3aF      ← wird zuerst geladen, verliert
  3. BG3SX AnimAddon                   BG3Sx
                                       BG3SX AnimAddon ← wird zuletzt geladen, GEWINNT

BG3 Ergebnis: BG3SX AnimAddon überschreibt alles → genau umgekehrt wie gewollt.
```

---

## Fix-Optionen

### Option A: Reihenfolge in `_write_modsettings()` umkehren (Empfohlen)

In `_write_modsettings()` die aktiven Mods (nach Gustav) in umgekehrter Reihenfolge schreiben:

```python
# Statt:
for uuid in final_order:
# Wird:
gustav_part = [u for u in final_order if is_base_game_mod(u)]
mod_part = [u for u in final_order if not is_base_game_mod(u)]
for uuid in gustav_part + list(reversed(mod_part)):
```

**Vorteil:** Nur eine Stelle ändern, UI-Konvention bleibt gleich.
**Nachteil:** Die modsettings.lsx-Reihenfolge ist dann invertiert zur UI — kann beim manuellen Debugging verwirrend sein.

### Option B: UI-Konvention anpassen (oben = niedrigste Priorität)

Die Anvil-UI so ändern, dass oben = niedrigste Priorität (wie in der modsettings.lsx). Dann schreibt `_write_modsettings()` korrekt 1:1.

**Vorteil:** modsettings.lsx und UI stimmen überein.
**Nachteil:** Widerspricht der MO2-Konvention (oben = höchste Priorität). Alle anderen Games in Anvil nutzen die MO2-Konvention.

### Option C: Reihenfolge in `reorder_mods()` umkehren

Vor dem Schreiben in `reorder_mods()` die `user_mods`-Liste umkehren:

```python
final_order = header + list(reversed(user_mods))
```

**Vorteil:** Zentrale Stelle, betrifft nur den BG3-Pfad.
**Nachteil:** `bg3_modstate.json` und `modsettings.lsx` hätten dann unterschiedliche Reihenfolgen.

### Empfehlung: Option A

Option A ist am saubersten: Die UI-Konvention (oben = höchste Priorität) bleibt für alle Spiele gleich. Nur die modsettings.lsx-Generierung wird korrigiert. Der `bg3_modstate.json`-State bleibt in UI-Reihenfolge.

---

## Zusätzlich zu prüfen

- **BG3 überschreibt modsettings.lsx beim Spielstart.** Kommentar im Code: *"BG3 may overwrite it on next launch — that's OK."* Nach dem Fix prüfen, ob BG3 die korrigierte Reihenfolge beibehält oder erneut umsortiert.
- **`ModsettingsWriter.write()` in `bg3_mod_handler.py`** schreibt beide Blöcke (`ModOrder` + `Mods`) — wird aber von Anvil NICHT benutzt (stattdessen nutzt Anvil `BG3ModInstaller._write_modsettings()`). Prüfen ob der alte Writer noch irgendwo referenziert wird.
- **`activate_mod()` und `deactivate_mod()`** rufen ebenfalls `_write_modsettings()` auf — der Fix greift dort automatisch mit.
