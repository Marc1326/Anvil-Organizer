# Feature-Spec: DnD Download-Tab → Mod-Liste

## Bug-Beschreibung

Mods aus dem Download-Tab koennen nicht per Drag & Drop auf die Mod-Liste gezogen werden.
Der Cursor zeigt das "Verboten"-Symbol — der Drop wird nie akzeptiert.

## Root Cause (konsolidiert aus 3 Agenten — einstimmig)

**Falsche Aufruf-Reihenfolge in `_DropTreeView`.**

In `dragEnterEvent()` (Zeile 496) und `dragMoveEvent()` (Zeile 506) wird `super()` **VOR** dem URL-Check aufgerufen:

```python
def dragEnterEvent(self, event):
    super().dragEnterEvent(event)        # ← PROBLEM: super() zuerst
    if event.mimeData().hasUrls():       # ← URL-Check danach — zu spaet
        ...
        event.acceptProposedAction()
```

### Warum scheitert super()?

1. `super().dragEnterEvent()` delegiert an `QAbstractItemView`, das intern `ModListModel.flags()` prueft
2. `ModListModel.flags()` (mod_list_model.py:366-373) gibt `ItemIsDropEnabled` nur fuer **invalide** Indices zurueck (Root-Level), nicht fuer gueltige Zeilen
3. Wenn der Cursor ueber einer existierenden Zeile ist → `super()` lehnt den Event ab
4. Das nachfolgende `event.acceptProposedAction()` akzeptiert dann `IgnoreAction` — wirkungslos

### Beweis durch Vergleich

`_DropFrameworkTree` (gleiche Datei, Zeilen 723-756) implementiert denselben URL-Check — aber in der **richtigen** Reihenfolge:

```python
def dragEnterEvent(self, event):
    if event.mimeData().hasUrls():       # ← URL-Check ZUERST
        ...
        event.acceptProposedAction()
        return
    super().dragEnterEvent(event)        # ← super() nur als Fallback
```

Diese Variante funktioniert einwandfrei.

## Betroffene Dateien

| Datei | Zeilen | Aenderung |
|-------|--------|-----------|
| `anvil/widgets/mod_list.py` | 496-504 | `dragEnterEvent()`: URL-Check VOR super() |
| `anvil/widgets/mod_list.py` | 506-509 | `dragMoveEvent()`: URL-Check VOR super() |

Keine weiteren Dateien betroffen. Sender-Seite (`game_panel.py:58-84`) ist korrekt.

## Loesungsplan

### Schritt 1: `dragEnterEvent()` fixen (Zeile 496-504)

URL-Check VOR `super()` verschieben. Bei URL-Match: `event.setDropAction(CopyAction)` + `event.accept()` + `return`. Nur wenn keine URLs: `super()` als Fallback (fuer internes DnD).

### Schritt 2: `dragMoveEvent()` fixen (Zeile 506-509)

Gleiche Reihenfolge: URL-Check VOR `super()`. Bei URL-Match: `event.setDropAction(CopyAction)` + `event.accept()` + `return`. Rest der Methode (Auto-Scroll, Auto-Expand, Separator-Logik) muss erhalten bleiben.

### Schritt 3: Testen

`./restart.sh` — App muss starten, DnD vom Download-Tab muss funktionieren, internes DnD (Mod-Reihenfolge) darf nicht kaputt gehen.

## Akzeptanz-Checkliste

- [ ] DnD von Download-Tab: .zip Archiv auf Mod-Liste ziehen → wird akzeptiert
- [ ] DnD von Download-Tab: .rar Archiv auf Mod-Liste ziehen → wird akzeptiert
- [ ] DnD von Download-Tab: .7z Archiv auf Mod-Liste ziehen → wird akzeptiert
- [ ] Drop auf existierende Mod-Zeile → korrekte Position
- [ ] Drop auf kollabierten Separator → korrekte Position
- [ ] Drop auf expandierten Separator → korrekte Position
- [ ] Drop auf leeren Bereich → ans Ende
- [ ] Internes DnD (Mod-Reihenfolge aendern) funktioniert weiterhin
- [ ] DnD vom Dateimanager auf Mod-Liste funktioniert weiterhin
- [ ] Nicht-Archiv-Dateien (.txt, .png) werden beim Drag abgelehnt
- [ ] Auto-Scroll bei Drag an Rand funktioniert weiterhin
- [ ] Auto-Expand bei Drag auf Separator funktioniert weiterhin
- [ ] `./restart.sh` startet ohne Fehler, keine Tracebacks

## Risiken / Impact

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Internes DnD (Mod-Umordnung) bricht | NIEDRIG | super() wird weiterhin fuer interne Drags aufgerufen (kein hasUrls()) |
| Dateimanager-DnD bricht | NIEDRIG | Dateimanager sendet ebenfalls text/uri-list — gleicher Pfad |
| Auto-Scroll/Expand in dragMoveEvent bricht | MITTEL | Die bestehende Logik nach super() muss erhalten bleiben, auch fuer URL-Drops |
| Drop-Position falsch berechnet | NIEDRIG | dropEvent() bleibt unveraendert |

## Referenz-Dateien (nur lesen)

- `anvil/widgets/mod_list.py` — _DropTreeView (Z.340-614), _DropFrameworkTree (Z.723-756)
- `anvil/widgets/game_panel.py` — _DraggableDownloadTable (Z.58-84)
- `anvil/models/mod_list_model.py` — mimeTypes (Z.382), flags (Z.366-373), canDropMimeData (Z.395-404)
- `anvil/mainwindow.py` — Signal-Verbindungen (Z.279-287), Handler (Z.1236-1278)
