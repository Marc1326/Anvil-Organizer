# Feature: v0.3.0 Bugfixes — Batch 1

Datum: 2026-03-04

---

## User Stories

- Als User möchte ich Mods per Drag & Drop über offene Trenner ziehen können, ohne dass diese zuklappen — damit ich die Übersicht behalte.
- Als User möchte ich, dass deaktivierte Mods keine Konflikte mehr anzeigen — damit die Konflikt-Anzeige den tatsächlichen Zustand widerspiegelt.
- Als User möchte ich einen Trenner durch Klick auf die gesamte Zeile ein-/ausklappen — nicht nur auf das kleine Dreieck.
- Als User möchte ich, dass neu installierte Mods deaktiviert starten — damit ich bewusst entscheide, welche Mods aktiv sein sollen.

---

## BUG 1: Trenner schließt sich beim Drag-Over

### Ist-Zustand
- `_DropTreeView.dragMoveEvent()` ([mod_list.py:466-529](anvil/widgets/mod_list.py#L466-L529))
- Wenn Setting `_auto_collapse_on_drag` aktiv ist, startet ein 500ms-Timer beim Hover über einen offenen Separator
- Nach Ablauf des Timers (`_on_collapse_timer`, [mod_list.py:415](anvil/widgets/mod_list.py#L415)) wird der Separator eingeklappt
- Ergebnis: Der Trenner schließt sich ungewollt während des Drag-Vorgangs

### Soll-Zustand
- Offene Trenner bleiben beim Drag-Over **offen**
- Die Auto-Collapse-Logik in `dragMoveEvent` ([mod_list.py:490-529](anvil/widgets/mod_list.py#L490-L529)) muss entfernt oder invertiert werden
- **Sinnvolleres Verhalten:** Geschlossene Trenner sollen sich beim Drag-Over automatisch **öffnen** (Auto-Expand), damit der User Mods in eingeklappte Gruppen droppen kann

### Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `anvil/widgets/mod_list.py` | `_on_collapse_timer()`: Logik invertieren — statt `_collapsed_separators.add()` → `_collapsed_separators.discard()` |
| `anvil/widgets/mod_list.py` | `dragMoveEvent()` Zeile 517: Bedingung invertieren — Timer nur starten wenn Separator **geschlossen** ist (`folder in self._collapsed_separators`), nicht wenn offen |
| `anvil/widgets/mod_list.py` | Setting-Name `_auto_collapse_on_drag` → `_auto_expand_on_drag` umbenennen für Klarheit |

### Lösung (Detail)

**`dragMoveEvent()`** — Bedingungsblock ab Zeile 515-529 ändern:
```python
# VORHER: Nur offene Separatoren (= NICHT in collapsed) → Timer starten zum Zuklappen
if folder in self._collapsed_separators:
    self._stop_collapse_timer()
    return

# NACHHER: Nur geschlossene Separatoren (= IN collapsed) → Timer starten zum Aufklappen
if folder not in self._collapsed_separators:
    self._stop_expand_timer()
    return
```

**`_on_collapse_timer()`** → `_on_expand_timer()` umbennen:
```python
# VORHER:
if folder and folder not in self._collapsed_separators:
    self._collapsed_separators.add(folder)

# NACHHER:
if folder and folder in self._collapsed_separators:
    self._collapsed_separators.discard(folder)
```

---

## BUG 4: Deaktivierte Mod zeigt Konflikte

### Ist-Zustand
- `_on_mod_toggled()` ([mainwindow.py:1057-1070](anvil/mainwindow.py#L1057-L1070)) aktualisiert beim Deaktivieren:
  - ✅ `entry.enabled = False`
  - ✅ `_write_current_modlist()` — Persistenz
  - ✅ `_schedule_redeploy()` — Deployment
  - ❌ **KEIN** `_compute_conflict_data()` — Konflikte werden NICHT neu berechnet
- `_compute_conflict_data()` ([mainwindow.py:1139-1190](anvil/mainwindow.py#L1139-L1190)) filtert korrekt: `for e in self._current_mod_entries if e.enabled` (Zeile 1150)
- Aber die ModRow-Objekte im Model behalten die alten Konflikt-Daten

### Soll-Zustand
- Nach dem Toggling einer Mod müssen Konflikte **sofort** neu berechnet werden
- Die deaktivierte Mod darf kein Konflikt-Icon mehr zeigen
- Alle anderen Mods müssen ihre Konflikte ohne die deaktivierte Mod neu berechnen

### Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `anvil/mainwindow.py` | `_on_mod_toggled()`: Nach `_schedule_redeploy()` Konflikte neu berechnen und Model-Rows aktualisieren |

### Lösung (Detail)

In `_on_mod_toggled()` nach Zeile 1070 (`self._schedule_redeploy()`) den gleichen Konflikt-Update-Code einfügen wie in `_on_mods_reordered()` (Zeile 1094-1101):

```python
def _on_mod_toggled(self, row: int, enabled: bool) -> None:
    """A mod checkbox was toggled — update entries and persist."""
    model = self._mod_list_view.source_model()
    if 0 <= row < len(model._rows):
        row_data = model._rows[row]
        for entry in self._current_mod_entries:
            display = entry.display_name or entry.name
            if display == row_data.name:
                entry.enabled = enabled
                break
    self._write_current_modlist()
    self._update_active_count()
    self._schedule_redeploy()
    # ── NEU: Konflikte neu berechnen ──
    conflict_data = self._compute_conflict_data()
    for mod_row in model._rows:
        folder = mod_row.folder_name
        mod_row.conflicts = conflict_data.get(folder, "")
    model.dataChanged.emit(
        model.index(0, 0),
        model.index(model.rowCount() - 1, model.columnCount() - 1),
    )
```

### Signal-Flow
```
CheckboxDelegate.editorEvent() → model.setData() → mod_toggled Signal
  → MainWindow._on_mod_toggled()
    → entry.enabled = False
    → _write_current_modlist()
    → _schedule_redeploy()
    → _compute_conflict_data()     ← NEU
    → model._rows aktualisieren    ← NEU
    → model.dataChanged.emit()     ← NEU
```

---

## BUG 7: Trenner nur per Dreieck klappbar

### Ist-Zustand
- `CheckboxDelegate` ist NUR für `COL_CHECK` registriert ([mod_list.py:741](anvil/widgets/mod_list.py#L741))
- `editorEvent()` ([mod_list.py:202-227](anvil/widgets/mod_list.py#L202-L227)) reagiert nur auf Klicks innerhalb der Dreieck-Spalte
- Klick auf Mod-Name, Kategorie oder andere Spalten eines Separators hat keinen Effekt

### Soll-Zustand
- Ein Klick auf **jede beliebige Spalte** einer Separator-Zeile soll den Trenner ein-/ausklappen
- Das Dreieck-Icon soll weiterhin korrekt dargestellt werden (▾ / ▸)

### Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `anvil/widgets/mod_list.py` | `_DropTreeView`: `mousePressEvent()` Override hinzufügen |

### Lösung (Detail)

In `_DropTreeView` ein `mousePressEvent()` Override hinzufügen, das prüft ob die geklickte Zeile ein Separator ist:

```python
def mousePressEvent(self, event):
    """Klick auf gesamte Separator-Zeile togglet Collapse/Expand."""
    if event.button() == Qt.MouseButton.LeftButton:
        idx = self.indexAt(event.pos())
        if idx.isValid():
            proxy = self.model()
            if isinstance(proxy, ModListProxyModel):
                source = proxy.sourceModel()
                source_idx = proxy.mapToSource(idx)
                if source and source_idx.isValid():
                    is_sep = source.data(source.index(source_idx.row(), 0), ROLE_IS_SEPARATOR)
                    if is_sep:
                        # COL_CHECK wird bereits vom CheckboxDelegate behandelt
                        if idx.column() != COL_CHECK:
                            folder = source.data(source.index(source_idx.row(), 0), ROLE_FOLDER_NAME) or ""
                            if folder in self._collapsed_separators:
                                self._collapsed_separators.discard(folder)
                            else:
                                self._collapsed_separators.add(folder)
                            self._apply_separator_filter()
                            return  # Event konsumiert
    super().mousePressEvent(event)
```

### Hinweis
- `COL_CHECK` wird weiterhin vom `CheckboxDelegate.editorEvent()` behandelt (Dreieck-Klick)
- Alle anderen Spalten werden vom neuen `mousePressEvent()` abgefangen
- Doppelklick-Events müssen NICHT abgefangen werden (DblClick öffnet keinen Editor bei Separatoren)

---

## BUG 8: Mod nach Install sofort aktiviert

### Ist-Zustand
- `_install_archives()` ([mainwindow.py:1387](anvil/mainwindow.py#L1387)):
  ```python
  add_mod_to_modlist(self._current_profile_path, mod_path.name)
  # → Default: enabled=True
  ```
- `_ctx_install_mod()` ([mainwindow.py:2421](anvil/mainwindow.py#L2421)):
  ```python
  add_mod_to_modlist(self._current_profile_path, result.name, True)
  # → Explizit True
  ```
- `add_mod_to_modlist()` ([mod_list_io.py:95](anvil/core/mod_list_io.py#L95)):
  ```python
  def add_mod_to_modlist(profile_path, mod_name, enabled=True):
  ```

### Soll-Zustand
- Neu installierte Mods sind nach Installation **deaktiviert** (Checkbox leer)
- Der User muss sie bewusst per Klick aktivieren
- Default-Parameter von `add_mod_to_modlist` bleibt `True` (Rückwärtskompatibilität für andere Aufrufer)

### Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `anvil/mainwindow.py` | `_install_archives()` Zeile 1387: `enabled=False` übergeben |
| `anvil/mainwindow.py` | `_ctx_install_mod()` Zeile 2421: `True` → `False` ändern |

### Lösung (Detail)

```python
# _install_archives(), Zeile 1387:
add_mod_to_modlist(self._current_profile_path, mod_path.name, enabled=False)

# _ctx_install_mod(), Zeile 2421:
add_mod_to_modlist(self._current_profile_path, result.name, False)
```

---

## Abhängigkeiten

- BUG 1 und BUG 7 betreffen beide `anvil/widgets/mod_list.py` — Änderungen müssen zusammen getestet werden
- BUG 4 betrifft nur `anvil/mainwindow.py` — unabhängig
- BUG 8 betrifft nur `anvil/mainwindow.py` — unabhängig
- Keine neuen i18n-Keys nötig (kein neuer UI-Text)
- Keine neuen QSettings-Keys nötig

## Risiken

| Risiko | Wahrscheinlichkeit | Gegenmaßnahme |
|--------|--------------------:|---------------|
| BUG 1: Auto-Expand verwirrt bei schnellem Scrolling | Niedrig | Timer von 500ms beibehalten |
| BUG 4: Konfliktberechnung bei großer Mod-Liste langsam | Niedrig | `_compute_conflict_data()` ist bereits schnell (<100ms für 200+ Mods) |
| BUG 7: Doppelklick auf Separator öffnet Editor | Niedrig | CheckboxDelegate konsumiert DblClick bereits (Zeile 216) |
| BUG 8: Bestehende Workflows erwarten aktive Mods | Mittel | Nur Install-Pfade ändern, Default von `add_mod_to_modlist` bleibt True |

## Geschätzter Aufwand

| Bug | Dateien | Zeilen (ca.) |
|-----|---------|:------------:|
| BUG 1 | 1 | ~15 |
| BUG 4 | 1 | ~8 |
| BUG 7 | 1 | ~20 |
| BUG 8 | 1 | ~2 |
| **Gesamt** | **2** | **~45** |

---

## ✅ Akzeptanz-Kriterien (ALLE müssen erfüllt sein)

### BUG 1: Trenner schließt sich beim Drag-Over
- [ ] Wenn User eine Mod über einen **offenen** Trenner zieht, bleibt der Trenner offen (klappt NICHT zu)
- [ ] Wenn User eine Mod über einen **geschlossenen** Trenner zieht und 500ms hält, klappt der Trenner automatisch auf (Auto-Expand)
- [ ] Wenn User die Mod vom geschlossenen Trenner weg zieht bevor 500ms abgelaufen sind, bleibt der Trenner geschlossen
- [ ] Wenn User die Mod droppt oder den Drag abbricht, wird der Expand-Timer gestoppt

### BUG 4: Deaktivierte Mod zeigt Konflikte
- [ ] Wenn User eine Mod per Checkbox deaktiviert, verschwindet das Konflikt-Icon bei dieser Mod sofort
- [ ] Wenn User eine Mod deaktiviert die Konflikte mit Mod B hatte, wird das Konflikt-Icon von Mod B aktualisiert (weniger Konflikte oder ganz weg)
- [ ] Wenn User eine zuvor deaktivierte Mod wieder aktiviert, werden Konflikte korrekt neu berechnet und angezeigt
- [ ] Wenn User die einzige Konflikt-Partnerin deaktiviert, zeigt die verbleibende Mod kein Konflikt-Icon mehr

### BUG 7: Trenner nur per Dreieck klappbar
- [ ] Wenn User auf den Mod-Namen eines Trenners klickt, klappt der Trenner ein/aus
- [ ] Wenn User auf die Kategorie-Spalte eines Trenners klickt, klappt der Trenner ein/aus
- [ ] Wenn User auf das Dreieck (COL_CHECK) eines Trenners klickt, klappt der Trenner ein/aus (wie bisher)
- [ ] Wenn User auf eine normale Mod-Zeile klickt, passiert KEIN Separator-Toggle (nur Selektion)

### BUG 8: Mod nach Install sofort aktiviert
- [ ] Wenn User eine Mod per "Mod installieren" (Menü) installiert, ist sie nach Installation deaktiviert (leerer Kreis)
- [ ] Wenn User eine Mod per Drag & Drop installiert, ist sie nach Installation deaktiviert
- [ ] Wenn User eine Mod per Kontext-Menü installiert, ist sie nach Installation deaktiviert
- [ ] Wenn User eine deaktiviert installierte Mod per Checkbox aktiviert, wird sie korrekt deployed

### Allgemein
- [ ] `restart.sh` startet ohne Fehler
