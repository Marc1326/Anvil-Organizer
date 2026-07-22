# Agent 2: MO2-Referenz-Analyse — Mehrfachauswahl und Verschieben von Mods

**Datum:** 2026-03-08

## 1. Wie macht MO2 Mehrfachauswahl in der Mod-Liste?

### Selection Mode
MO2 verwendet `QAbstractItemView::ExtendedSelection` auf dem `QTreeView` (gesetzt in `mainwindow.ui`, Zeile 420):
- **Klick** = einzelne Auswahl
- **Strg+Klick** = Auswahl hinzufuegen/entfernen
- **Shift+Klick** = Bereich auswaehlen
- **Strg+A** = alle auswaehlen

### Wichtiger Trick: selectedIndexes() Override
MO2 ueberschreibt `selectedIndexes()` (`modlistview.cpp:949`):
```cpp
QModelIndexList ModListView::selectedIndexes() const {
    return m_inDragMoveEvent ? QModelIndexList() : QTreeView::selectedIndexes();
}
```
Waehrend Drag&Drop-Events wird eine leere Liste zurueckgegeben, damit Drag&Drop von Separatoren in ihre eigenen Kinder funktioniert.

## 2. Wie funktioniert Drag & Drop mit mehreren Mods bei MO2?

### MIME-Daten
In `modlist.cpp` (Zeile 655):
- Qt's Standard-`mimeData()` kodiert alle ausgewaehlten Indices als `application/x-qabstractitemmodeldatalist`
- Zusaetzlich wird "mod" als `text/plain` gesetzt

### Drop-Verarbeitung
In `ModList::dropMimeData()` (Zeile 1133):
```cpp
if (dropInfo.isModDrop()) {
    changeModPriority(dropInfo.rows(), dropPriority);
}
```
Die gesamte Liste der Quell-Zeilen wird als Batch an `changeModPriority()` uebergeben.

## 3. "Send to Separator" Kontextmenue

**JA** — Teil eines "Send to..." Untermenues.

### Kontextmenue-Struktur (`modlistcontextmenu.cpp`)
`addSendToContextMenu()` (Zeile 285) erstellt:

| Menue-Eintrag | Aktion |
|---|---|
| "Lowest priority" | `sendModsToTop(m_selected)` |
| "Highest priority" | `sendModsToBottom(m_selected)` |
| "Priority..." | `sendModsToPriority(m_selected)` |
| **"Separator..."** | **`sendModsToSeparator(m_selected)`** |
| "First conflict" | `sendModsToFirstConflict(m_selected)` |
| "Last conflict" | `sendModsToLastConflict(m_selected)` |

**Wichtig:** Wenn mehrere Mods selektiert sind, arbeiten ALLE Aktionen auf der gesamten Selektion.

## 4. Reihenfolge beim Verschieben mehrerer Mods

### sendModsToSeparator() (`modlistviewactions.cpp:659`)
1. **Separator-Liste aufbauen:** Alle Separatoren nach Prioritaet sortiert
2. **Dialog anzeigen:** `ListDialog` zeigt Separator-Namen zur Auswahl
3. **Ziel-Prioritaet:** Ende des gewaehlten Separators (= vor dem naechsten Separator)
4. **Verschieben:** `changeModsPriority(indexes, priority)`

### changeModPriority() — Kern-Algorithmus (`modlist.cpp:662`)
1. **Mods nach absteigender Prioritaet sortieren** (hoechste zuerst)
2. **Mods mit hoeherer Prioritaet als Ziel zuerst verschieben** (decreasing)
3. **Sortierung umkehren** — aufsteigende Prioritaet
4. **Offset-Korrektur** bei nach-oben-Verschiebung
5. **Mods mit niedrigerer Prioritaet als Ziel verschieben** (increasing)

**Warum diese Reihenfolge?** Jedes `setModPriority()` verschiebt andere Prioritaeten. Durch getrenntes Verarbeiten (erst runter, dann rauf) bleibt die relative Reihenfolge erhalten.

## 5. UX-Patterns fuer Mehrfachoperationen

### Keyboard-Shortcuts
| Shortcut | Aktion |
|---|---|
| Strg+Hoch/Runter | Alle selektierten Mods um 1 verschieben |
| Entf | Alle selektierten Mods loeschen |
| Leertaste | Alle selektierten Mods aktivieren/deaktivieren |

### Batch-Aktionen im Kontextmenue
- Enable/Disable selected
- Remove Mod(s)
- Set Color / Reset Color
- Send to Top/Bottom/Priority/Separator
- Set Categories

## 6. Kernerkenntnisse fuer Anvil

### Was uebernehmen:
1. **ExtendedSelection + SelectRows** — bereits in Anvil vorhanden
2. **"In Trenner verschieben" Kontextmenue** mit Separator-Auswahl
3. **changeModPriority() Sortier-Logik** — erst absteigende, dann aufsteigende Mods verschieben
4. **Keyboard-Shortcuts** Strg+Hoch/Runter

### Was ANDERS machen:
1. **modlist.txt ist invertiert** — Separator steht NACH seinen Mods (MO2 arbeitet mit Prioritaetswerten)
2. **Einfacherer Model-Stack** — Anvil hat nur Model + ProxyModel (MO2 hat 4 Schichten)

### Risiken:
- Die Sortierlogik beim Verschieben ist subtil — falsche Reihenfolge fuehrt zu vertauschten Mods
- Der `selectedIndexes()`-Override ist ein Qt-Workaround — Anvil koennte das gleiche Problem haben
