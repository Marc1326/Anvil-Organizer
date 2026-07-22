# BG3 Bugs — Zusammenfassung für neuen Chat

**Datum:** 2026-03-30
**Projekt:** Anvil Organizer
**Betroffene Instanz:** Baldur's Gate 3

---

## WICHTIG: Uncommitted Changes ZUERST revertieren

Im aktuellen Working Tree sind **falsche Änderungen** die revertiert werden müssen:

- `anvil/widgets/bg3_mod_list.py` — Signal `archives_dropped_at` hinzugefügt + Drop-Position-Logik in `_BG3DropTreeView.dropEvent()` und `BG3ModListView`
- `anvil/mainwindow.py` — Signal-Connection für `_bg3_mod_list.archives_dropped_at` (Zeile ~4607-4609)

**Warum falsch:** Diese Änderungen betreffen `BG3ModListView` (`_bg3_mod_list`), aber BG3 benutzt dieses Widget **NICHT**. BG3 benutzt die **Standard-ModListView** (`_mod_list_view`). Siehe `mainwindow.py:4622-4623`:
```python
# Use normal mod list view — NOT the BG3-specific one
self._mod_list_stack.setCurrentWidget(self._mod_list_view)
```

Der einfachste Weg: `git checkout -- anvil/widgets/bg3_mod_list.py anvil/mainwindow.py`

---

## Bug 1: Data-Overrides landen in Frameworks (statt Mod-Liste)

### Problem
Wenn man BG3-Mods installiert die keine `.pak`-Dateien enthalten (z.B. Textur-Replacements, Mesh-Mods), werden sie als `data_override` klassifiziert und im **Framework-Panel** angezeigt — neben BG3 Script Extender. Das ist falsch. Es sind normale Mods, keine Frameworks.

### Betroffene Mods (Beispiele)
- **Myky's Makeup and Tattoos** — 2x DDS-Texturen, keine .pak
- **Dwarves (Durgar Tweaks)** — 1x GR2-Mesh, keine .pak
- **Native Camera Tweaks** — data_override, aber Marc sagt diese ist korrekt in Frameworks

### Ursache
`mainwindow.py:4787-4795` in `_bg3_reload_mod_list()`:
```python
data_overrides = mod_list.get("data_overrides", [])
fw_items = list(fw_list)
for ov in data_overrides:
    fw_items.append({
        "name": ov.get("name", "?"),
        "description": f"Data Override — {len(ov.get('files', []))} Dateien",
        "installed": True,
        **ov,
    })
self._mod_list_view.load_frameworks(fw_items)
```
**ALLE** data_overrides werden blind ins Framework-Panel geschoben — egal ob kosmetische Mod oder tatsächlich Framework-ähnlich.

### Klassifizierungs-Logik
`bg3_mod_installer.py:579-602` — `detect_mod_type()`:
1. Framework-Pattern erkannt? → `framework`
2. Hat `.pak`-Dateien? → `pak` (erscheint in Mod-Liste)
3. Alles andere → `data_override` (landet in Frameworks — **das ist das Problem**)

### Lösung (Vorschlag)
Data-overrides sollten in der Mod-Liste erscheinen, nicht im Framework-Panel. Nur echte Frameworks (BG3SE etc.) gehören ins Framework-Panel.

---

## Bug 2: DnD Drop-Position wird nicht respektiert

### Problem
Wenn man eine Mod per Drag & Drop in die BG3-Mod-Liste zieht, landet sie **immer ganz unten** statt an der Stelle wo man sie fallen lässt.

### Signal-Flow (der ECHTE, über Standard-ModListView)
```
Standard _mod_list_view (dropEvent)
  → archives_dropped_at Signal (list, int)
    → _on_archives_dropped_at() [mainwindow.py:1396]
      → _on_bg3_archives_dropped(paths, insert_at=target_row) [mainwindow.py:4831]
        → bg3_installer.install_mod()
        → bg3_installer.insert_mod_at(uuid, ref_uuid, activate=ref_active)
```

### Wo der Bug liegt (noch nicht vollständig analysiert)
Die Standard-ModListView hat bereits ein `archives_dropped_at` Signal das die Drop-Position korrekt emittiert. Der Bug ist irgendwo in der Kette:
- Emittiert `archives_dropped_at` überhaupt für BG3, oder nur `archives_dropped` (ohne Position)?
- Funktioniert `insert_mod_at()` korrekt?
- Stimmt die `ref_uuid`-Berechnung in `_on_bg3_archives_dropped()` (Zeilen 4838-4847)?

### Relevante Code-Stellen
- `mainwindow.py:1396-1405` — `_on_archives_dropped_at()`
- `mainwindow.py:4831-4898` — `_on_bg3_archives_dropped()`
- `mainwindow.py:4732-4796` — `_bg3_reload_mod_list()`
- `bg3_mod_installer.py:437-490` — `get_mod_list()`

---

## Wichtiger Kontext

1. **BG3 hat NUR EINE Mod-Liste** — keine getrennte aktiv/inaktiv Liste
2. **BG3 benutzt die Standard-`_mod_list_view`**, NICHT die `_bg3_mod_list` (`BG3ModListView`)
3. **`_bg3_mod_list` wird erstellt und Signale verbunden, aber NIEMALS als aktives Widget angezeigt**
4. **Manifeste** für data_overrides liegen in `.data_overrides/` als JSON-Dateien
5. **BG3-Instanzpfad:** `~/.anvil-organizer/instances/Baldur's Gate 3/`
6. **Spielpfad:** `/mnt/gamingS/SteamLibrary/steamapps/common/Baldurs Gate 3/`
