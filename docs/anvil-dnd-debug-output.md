# DnD Debug-Output — _DropTreeView

Datum: 2026-03-08
Test: Archiv-Datei(en) aus Dolphin auf Mod-Liste gezogen

## Ergebnis

**dragEnterEvent wird korrekt aufgerufen — DnD wird ACCEPTED.**

## Rohdaten (dedupliziert)

```
[DnD-DEBUG] dragEnterEvent aufgerufen
  hasUrls: True
  proposedAction: DropAction.CopyAction
  possibleActions: DropAction.CopyAction|MoveAction
  URL: /home/mob/Downloads/Mods/CP/Button Skirt - Vanilla-8510-1-0-1686390362.zip
  → ACCEPTED (CopyAction)

[DnD-DEBUG] dragMoveEvent → URL-Zweig (CopyAction + accept)
```

## Statistik

| Event | Anzahl |
|---|---|
| dragEnterEvent | 2 (2 Dateien gezogen) |
| dragMoveEvent (URL-Zweig) | 528 |
| dragMoveEvent (else-Zweig / super) | 0 |
| Fallthrough to super() | 0 |

## Analyse

1. **dragEnterEvent()** wird aufgerufen — Qt blockt NICHT auf Widget-Ebene
2. **proposedAction** ist `CopyAction` (nicht MoveAction!) — Dolphin bietet Copy an
3. **possibleActions** sind `CopyAction|MoveAction` — beides möglich
4. **URL-Check** matcht korrekt → Event wird mit `CopyAction` accepted
5. **dragMoveEvent()** trifft IMMER den URL-Zweig (korrekt)
6. **else-Zweig (super)** wurde NIE getroffen bei externem DnD (korrekt)

## Schlussfolgerung

Der `setDropAction(CopyAction) + accept()`-Fix aus der QA-Analyse funktioniert:
- dragEnterEvent akzeptiert die Dateien korrekt
- dragMoveEvent hält den Accept-Status aufrecht
- Kein Fallthrough zu super() bei externem DnD

**Offene Frage:** Hat der Drop am Ende funktioniert (Mod wurde installiert)?
Falls nicht, liegt das Problem im `dropEvent()`, nicht in dragEnter/dragMove.

**Zweite Frage:** War das "Verboten"-Symbol sichtbar oder nicht?
Falls ja trotz ACCEPTED: Qt-Rendering-Bug oder der Sender ignoriert den Accept.
