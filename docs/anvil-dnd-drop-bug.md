# DnD-Drop-Bug — Konsolidierter Fix-Report
Datum: 2026-03-08

## Problem

Externe Archiv-Dateien (.zip, .rar, .7z) koennen nicht mehr per Drag & Drop aus dem Dateimanager (Dolphin) auf die Mod-Liste gedroppt werden. Der Cursor zeigt das "Verboten"-Symbol. Internes DnD (Mod-Reihenfolge aendern, Separator-DnD) funktioniert weiterhin korrekt.

Das Feature hat im initialen Commit `5f594e2` funktioniert, ist aber durch nachfolgende Aenderungen kaputt gegangen.

## Root-Cause Analyse

Die Root Cause ist eine **Kombination aus drei Aenderungen**, die zusammen das externe DnD brechen:

### Ursache 1: `setDefaultDropAction(Qt.DropAction.MoveAction)` (PRIMAER)

In `ModListView.__init__` (Zeile 781) wird:
```python
self._tree.setDefaultDropAction(Qt.DropAction.MoveAction)
```

gesetzt. Dieser Aufruf existierte im funktionierenden Commit `5f594e2` noch NICHT. Er wurde spaeter hinzugefuegt fuer korrektes internes DnD (Mod-Verschiebung).

**Effekt:** Wenn Dolphin eine Datei per DnD anbietet, schlaegt es `CopyAction` vor (Dateien aus dem Dateimanager werden normalerweise kopiert, nicht verschoben). Qt's interner Handler ueberschreibt die vorgeschlagene Action mit der `defaultDropAction` (`MoveAction`). Da der Sender (Dolphin) kein `MoveAction` unterstuetzt, lehnt Qt den Drop ab.

**Beweis:** Die `_DropFrameworkTree`-Klasse (Zeile 723ff) hat `setDefaultDropAction` NICHT gesetzt und akzeptiert externe Drops korrekt.

### Ursache 2: `super().dragEnterEvent()` VOR URL-Check (VERSTAERKEND)

Seit Commit `829a849` wird `super().dragEnterEvent(event)` ZUERST aufgerufen (Zeile 497), bevor der eigene URL-Check laeuft. Qt's `QAbstractItemView::dragEnterEvent()` prueft intern ob die vorgeschlagene Drop-Action mit der `defaultDropAction` kompatibel ist. Da `MoveAction` != `CopyAction`, markiert Qt den Drag-State intern als "abgelehnt".

Das nachfolgende `event.acceptProposedAction()` (Zeile 503) kommt zu spaet — Qt hat den internen State bereits gesetzt.

**Vergleich mit _DropFrameworkTree:** Dort wird `super()` am ENDE aufgerufen (Zeile 736), nur wenn KEINE URLs vorhanden sind. Das ist das korrekte Pattern.

### Ursache 3: `acceptProposedAction()` statt explizitem `setDropAction()` (VERSTAERKEND)

`event.acceptProposedAction()` akzeptiert die "proposed" Action, aber wenn Qt die proposed Action intern bereits auf `MoveAction` umgeschrieben hat (wegen `defaultDropAction`), dann akzeptiert man `MoveAction` — was der Sender nicht kann.

Die korrekte Loesung ist `event.setDropAction(Qt.DropAction.CopyAction)` gefolgt von `event.accept()`, um die Action explizit auf `CopyAction` zu setzen, unabhaengig von Qt's interner Logik.

## Was im funktionierenden Commit anders war

Im Commit `5f594e2` (erste DnD-Implementierung):

```python
# FUNKTIONIEREND — Commit 5f594e2

def dragEnterEvent(self, event):
    if event.mimeData().hasUrls():                          # URL-Check ZUERST
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if any(path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                    event.acceptProposedAction()            # Akzeptieren und SOFORT return
                    return
    super().dragEnterEvent(event)                           # super() NUR fuer internes DnD

def dragMoveEvent(self, event):
    if event.mimeData().hasUrls():
        event.acceptProposedAction()                        # URLs akzeptieren und SOFORT return
        return
    super().dragMoveEvent(event)                            # super() NUR fuer internes DnD
```

**Drei entscheidende Unterschiede zum aktuellen Code:**
1. **Kein `setDefaultDropAction(MoveAction)`** — existierte noch nicht
2. **URL-Check VOR super()** — Qt's interner Handler lief nur bei internem DnD
3. **`return` nach URL-Accept** — `super()` wurde bei externem DnD nie aufgerufen

## Was MO2 anders macht

### 1. Model-basierte Drop-Erkennung
MO2 hat eine dedizierte `ModListDropInfo`-Klasse die alle Drop-Typen klassifiziert (Mod-Drop, Download-Drop, Local-File-Drop, External-Archive-Drop, External-Folder-Drop). Anvil macht die Erkennung inline in den Event-Handlern.

### 2. dragMoveEvent Workaround
MO2 ruft bewusst `QAbstractItemView::dragMoveEvent` statt `QTreeView::dragMoveEvent` auf und faelscht `selectedIndexes()` per `m_inDragMoveEvent`-Flag. Dies verhindert dass Qt Auto-Collapse ausfuehrt und ermoeglicht Separator-in-Children-Drops. Anvil hat diesen Workaround nicht.

### 3. Text-Marker statt Custom MIME-Type
MO2 verwendet `text/plain = "mod"` als Marker fuer internes DnD. Anvil verwendet `application/x-anvil-mod-rows`. Beide Ansaetze sind funktional korrekt, aber MO2's Marker-System macht die Unterscheidung intern/extern einfacher.

### 4. Keine defaultDropAction
MO2 setzt **keine** explizite `defaultDropAction` — die Drop-Action-Logik wird komplett in `canDropMimeData` und `dropMimeData` gehandelt. Dies vermeidet das Problem das Anvil hat.

## Konkreter Fix

### Variante A: Minimaler Fix (empfohlen)

Aendere NUR die drei DnD-Event-Handler in `_DropTreeView` (Zeilen 496-509). Das Pattern wird an `_DropFrameworkTree` angeglichen, die korrekt funktioniert.

**Alter Code (Zeilen 496-509):**
```python
def dragEnterEvent(self, event):
    super().dragEnterEvent(event)                    # 497: super() ZUERST — PROBLEM
    if event.mimeData().hasUrls():                   # 498
        for url in event.mimeData().urls():          # 499
            if url.isLocalFile():                    # 500
                path = url.toLocalFile()             # 501
                if any(path.lower().endswith(ext)    # 502
                       for ext in SUPPORTED_EXTENSIONS):
                    event.acceptProposedAction()     # 503 — PROBLEM
                    return                           # 504

def dragMoveEvent(self, event):
    super().dragMoveEvent(event)                     # 507: super() ZUERST — PROBLEM
    if event.mimeData().hasUrls():                   # 508
        event.acceptProposedAction()                 # 509 — PROBLEM
```

**Neuer Code:**
```python
def dragEnterEvent(self, event):
    if event.mimeData().hasUrls():
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if any(path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                    event.setDropAction(Qt.DropAction.CopyAction)
                    event.accept()
                    return
    super().dragEnterEvent(event)

def dragMoveEvent(self, event):
    if event.mimeData().hasUrls():
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
    else:
        super().dragMoveEvent(event)
```

### Erklaerung der Aenderungen:

1. **dragEnterEvent:** URL-Check wird VOR `super()` ausgefuehrt. Bei externem Drop wird `setDropAction(CopyAction)` + `accept()` verwendet statt `acceptProposedAction()`. `super()` wird nur bei internem DnD aufgerufen.

2. **dragMoveEvent:** Bei URLs wird `super()` NICHT aufgerufen — stattdessen wird direkt akzeptiert. `super()` laeuft nur fuer internes DnD. **Konsequenz:** Bei externem DnD gibt es keinen Drop-Indicator (Linie zwischen Zeilen), aber das ist korrekt — der Drop-Indicator ist nur fuer internes Verschieben relevant. Die Drop-Position wird im `dropEvent` ueber `indexAt()` bestimmt.

3. **Auto-Scroll und Auto-Expand:** Die Auto-Scroll-Logik (Zeilen 511-528) und Auto-Expand-Logik (Zeilen 530-569) in `dragMoveEvent` muessen weiterhin fuer BEIDE DnD-Typen laufen. Im neuen Code muessen diese Bloecke NACH dem if/else stehen (nicht im else-Zweig).

### Vollstaendiger neuer dragMoveEvent:
```python
def dragMoveEvent(self, event):
    if event.mimeData().hasUrls():
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
    else:
        super().dragMoveEvent(event)

    # Auto-scroll when dragging near edges (fuer BEIDE DnD-Typen)
    EDGE_SIZE = 40
    pos = event.position().toPoint()
    viewport_height = self.viewport().height()
    y = pos.y()

    if y < EDGE_SIZE:
        ratio = 1.0 - (y / EDGE_SIZE)
        self._auto_scroll_speed = -max(1, int(ratio * 5))
        if not self._auto_scroll_timer.isActive():
            self._auto_scroll_timer.start()
    elif y > viewport_height - EDGE_SIZE:
        ratio = 1.0 - ((viewport_height - y) / EDGE_SIZE)
        self._auto_scroll_speed = max(1, int(ratio * 5))
        if not self._auto_scroll_timer.isActive():
            self._auto_scroll_timer.start()
    else:
        self._stop_auto_scroll()

    # Setting 4: Auto-Expand logic (fuer BEIDE DnD-Typen)
    if not self._auto_expand_on_drag:
        return
    # ... rest der Auto-Expand Logik bleibt unveraendert ...
```

### Variante B: Zusaetzlich defaultDropAction entfernen

Zusaetzlich zu Variante A koennte man `setDefaultDropAction(MoveAction)` (Zeile 781) entfernen. Da Anvil die Drop-Logik komplett in den Event-Handlern und in `dropMimeData` implementiert, ist `defaultDropAction` moeglicherweise ueberfluessig. **VORSICHT:** Dies koennte internes DnD beeinflussen — muss separat getestet werden.

## Akzeptanz-Checkliste

- [ ] 1. Externe Archiv-Dateien (.zip, .rar, .7z) koennen per DnD auf die Mod-Liste gedroppt werden
- [ ] 2. Der Drop-Cursor zeigt korrekt "Akzeptieren" fuer unterstuetzte Dateitypen
- [ ] 3. Der Drop-Cursor zeigt korrekt "Ablehnen" fuer nicht-unterstuetzte Dateitypen
- [ ] 4. Internes DnD (Mod-Reihenfolge aendern) funktioniert weiterhin
- [ ] 5. Separator-DnD funktioniert weiterhin
- [ ] 6. Das archives_dropped / archives_dropped_at Signal wird korrekt emittiert mit den Datei-Pfaden
- [ ] 7. Keine Regression bei Multi-Select DnD
- [ ] 8. Auto-Scroll bei Drag nahe am Rand funktioniert fuer beide DnD-Typen
- [ ] 9. Auto-Expand bei Drag ueber collapsed Separator funktioniert fuer beide DnD-Typen
- [ ] 10. Framework-Tree externes DnD funktioniert weiterhin (keine Regression)
