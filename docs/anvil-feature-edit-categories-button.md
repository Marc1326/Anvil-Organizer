# Feature-Spec: Edit-Categories-Button in den Einstellungen (#17)
**Status:** Geplant (verifiziert gegen echten Code, 2026-06-28)
**Issue:** #17 — "Feature: Edit Categories Button in Settings" (Labels: `disabled-feature`, `enhancement`)

## 1. Problem / Ziel
Im Einstellungen-Dialog (Tab „Allgemein“, Gruppe „Sonstiges“) existiert ein Button
„Mod Kategorien anpassen“. Er ist über den `_disabled(...)`-Wrapper deaktiviert
(ausgegraut, Tooltip „Noch nicht verfügbar“) und tut nichts.

Wunsch laut Issue #17:
- Button öffnet einen Kategorie-Editor.
- Kategorien anlegen, umbenennen, löschen — **plus Farben zuweisen**.
- Reihenfolge per Drag & Drop ändern.
- Änderungen wirken sich auf die Mod-Liste aus.

**Verifizierter Befund (wichtig, korrigiert gegenüber Erstentwurf):**
Ein Kategorie-Dialog (`CategoryDialog`) existiert bereits und kann **Anlegen / Umbenennen /
Löschen**. Er ist in `mainwindow.py` zwar importiert (Zeile 82), wird aber **nirgends
instanziiert** — der Import ist aktuell ungenutzt (toter Import). Der Erstentwurf behauptete,
der Dialog werde „im Mod-Kontextmenü bereits genutzt (mainwindow.py:2545)“. Das ist **falsch**:
Zeile 2545 gehört zu `ModDetailDialog`, nicht zu `CategoryDialog`.
**Farben** und **Drag&Drop-Reihenfolge** sind weder im Dialog noch im Datenmodell vorhanden.

## 2. Phasen-Rückgrat (Bau-Reihenfolge nach steigendem Risiko)

| # | Phase | Inhalt | Risiko | testbar nach Phase? |
|---|---|---|---|---|
| 1 | Button verdrahten | `_disabled`-Wrapper am Edit-Categories-Button (`settings_dialog.py:175`) entfernen, Button als benannte Variable, `clicked` → öffentliche MainWindow-Methode (mit Guard, falls keine Instanz). Neue Methode `open_category_editor()` in `mainwindow.py` baut den **vorhandenen** `CategoryDialog` mit `self._category_manager` + `self._current_mod_entries`, ruft `exec()`. | niedrig | Ja — Button aktiv, Dialog öffnet, Neu/Umbenennen/Löschen funktioniert + persistiert in `categories.json` |
| 2 | Refresh nach Schließen | Nach `dlg.exec()` den erprobten Refresh-Pfad wiederverwenden: `self._filter_panel.set_categories(self._category_manager.all_categories())` + `self._reload_mod_list()`. | niedrig | Ja — geänderte Kategorien sofort in Mod-Liste + Filter-Panel sichtbar |
| 3 | (Folge-Scope) Farben | `color`-Feld ins Datenmodell (`categories.py`), `set_color()`-Mutator mit `save()`, Farb-Spalte/Swatch + Farbwähler-Button im Dialog, Rendering in Mod-Liste. Neue tr-Keys. | mittel-hoch | Ja — Farbe wählbar, persistiert, in Liste sichtbar |
| 4 | (Folge-Scope) Reihenfolge | Heute liefert `all_categories()` **immer alphabetisch sortiert** (`categories.py:134`). Persistente Reihenfolge erfordert ein `order`-Feld + Anpassung der Sortierlogik + Drag&Drop im Tree (aktuell `SingleSelection`, `setSortingEnabled(True)`). | hoch | Ja — manuelle Reihenfolge bleibt nach Neustart erhalten |

**Empfehlung:** Phasen 1+2 = Kern dieses Issues (geringes Risiko, Dialog existiert). Phasen 3+4
mit Marc abstimmen — sie sind echte Neuentwicklung (Datenmodell + Sortierlogik) und evtl. als
separates Folge-Issue besser aufgehoben.

## 3. Ist-Zustand im Code (nur verifizierte Anker)

| Stelle | Datei:Zeile | Verifizierter Befund |
|---|---|---|
| Button (deaktiviert) | `anvil/widgets/settings_dialog.py:175` | `misc_btn_row.addWidget(_disabled(QPushButton(tr("settings.edit_categories"))))` |
| `_disabled`-Helper | `anvil/widgets/settings_dialog.py:73-76` | `setEnabled(False)` + Tooltip `tr("settings.coming_soon")` |
| SettingsDialog-Konstruktor | `anvil/widgets/settings_dialog.py:46-47` | `def __init__(self, parent=None, plugin_loader=None, instance_manager=None, on_clear_modindex=None)` → `parent` = MainWindow |
| SettingsDialog-Aufruf | `anvil/mainwindow.py:755` | `dlg = SettingsDialog(self, ...)` → Parent ist MainWindow |
| `CategoryDialog`-Klasse | `anvil/widgets/category_dialog.py:24` | `class CategoryDialog(QDialog)` |
| Konstruktor-Signatur | `anvil/widgets/category_dialog.py:33-39` | `(self, category_manager, mod_entries, default_category_ids=None, parent=None)` |
| Dialog-Buttons | `anvil/widgets/category_dialog.py:78-83` | Nur `button.new`, `button.rename`, `button.delete` (kein Farb-/Reorder-Button) |
| Dialog-Aktionen | `anvil/widgets/category_dialog.py:165,182,210` | `_on_new`, `_on_rename`, `_on_delete` — keine Farbe, kein Reorder |
| `CategoryDialog`-Import | `anvil/mainwindow.py:82` | `from anvil.widgets.category_dialog import CategoryDialog` — **importiert, aber nirgends instanziiert (toter Import)** |
| CategoryManager-Instanz | `anvil/mainwindow.py:313` | `self._category_manager = CategoryManager()` |
| Mod-Einträge | `anvil/mainwindow.py:335` | `self._current_mod_entries = []` (gefüllt beim Mod-Scan) |
| Erprobter Refresh-Pfad | `anvil/mainwindow.py:5195-5196`, `5228-5229` | `self._filter_panel.set_categories(cat_mgr.all_categories())` + `self._reload_mod_list()` |
| Reload-Methode | `anvil/mainwindow.py:5487` | `def _reload_mod_list(self)` |
| Persistenz Kategorien | `anvil/core/categories.py:117,172,180,189` | `save()` → `categories.json`; `add_category`/`rename_category`/`remove_category` rufen `save()` automatisch |
| Datenmodell | `anvil/core/categories.py:171` | Eintrag = `{"id": int, "name": str}` — **kein `color`-Feld** |
| Sortierung | `anvil/core/categories.py:132-134` | `all_categories()` gibt **immer alphabetisch nach Name sortiert** zurück → keine persistente Reihenfolge möglich |
| Speicherformat | `anvil/core/categories.py:104-115` | Flache **JSON-Liste** (`categories.json`), **kein XML** |

## 4. Betroffene Dateien

| Datei | Änderung | Phase |
|---|---|---|
| `anvil/mainwindow.py` | NEU: öffentliche Methode `open_category_editor()` (baut vorhandenen `CategoryDialog`, danach Refresh über erprobten Pfad). Toter Import (Z. 82) wird dadurch endlich genutzt. | 1+2 |
| `anvil/widgets/settings_dialog.py` | Edit-Categories-Button nicht mehr `_disabled`, als Variable anlegen, `clicked` → `self.parent().open_category_editor()` (Guard via `getattr`). | 1 |
| `anvil/widgets/category_dialog.py` | Nur Phase 3/4: Farb-Spalte/Button bzw. Drag&Drop ergänzen. | 3+4 |
| `anvil/core/categories.py` | Nur Phase 3/4: `color`-Feld + `set_color()` bzw. `order`-Feld + Sortierlogik. | 3+4 |
| `anvil/locales/*.json` (7×: de,en,es,fr,it,pt,ru) | Nur Phase 3/4: neue Texte (Farbe/Reorder). | 3+4 |

## 5. Umsetzungsschritte (Phase 1+2 = Kern)
1. In `mainwindow.py` Methode `open_category_editor()` anlegen:
   - Guard: wenn keine Instanz / `not self._current_instance_path` → freundliche Statusmeldung, return.
   - `dlg = CategoryDialog(self._category_manager, self._current_mod_entries, parent=self)`
     (optional `default_category_ids` aus `_DEFAULT_CATEGORIES` für die Quelle-Spalte).
   - `_center_on_parent(dlg)` (Muster wie bei anderen Dialogen), `dlg.exec()`.
   - Danach Refresh (erprobter Pfad, verifiziert Z. 5195/5228):
     `self._filter_panel.set_categories(self._category_manager.all_categories())`
     und `self._reload_mod_list()`.
2. In `settings_dialog.py` Z. 175 den `_disabled(...)`-Wrapper entfernen, Button als Variable,
   `clicked.connect(lambda checked=False: self._open_category_editor())` mit einer kleinen
   Helper-Methode im SettingsDialog, die `getattr(self.parent(), "open_category_editor", None)`
   prüft und sonst nichts tut (defensiv).
3. `./restart.sh`, Log prüfen (kein NameError/AttributeError), Dialog öffnen, Neu/Umbenennen/
   Löschen testen, Schließen → Sichtbarkeit in Mod-Liste + Filter-Panel prüfen.
4. Mit Marc klären, ob Farben (Phase 3) + Drag&Drop-Reihenfolge (Phase 4) in dieses Issue gehören
   oder als Folge-Issue. Hinweis: beides ist echte Neuentwicklung am Datenmodell/der Sortierlogik.

## 6. i18n (tr-Keys, 7 Locales: de, en, es, fr, it, pt, ru)
**Für Phase 1+2 sind KEINE neuen Keys nötig** — alle benötigten Keys existieren und sind in allen
7 Locales gepflegt (verifiziert):
- `settings.edit_categories` (DE: „Mod Kategorien anpassen“)
- `dialog.categories_title`, `button.new`, `button.rename`, `button.delete`, `button.close`

**Neue Keys erst ab Phase 3/4** (dann Pflicht in ALLEN 7 Locales: de, en, es, fr, it, pt, ru),
z. B. `button.color` / `dialog.choose_color` (Phase 3), Tooltip/Hinweis für Reorder (Phase 4).

## 7. Akzeptanzkriterien

**Phase 1+2 (Kern):**
- [ ] Button „Mod Kategorien anpassen“ ist aktiv (nicht ausgegraut, kein „Noch nicht verfügbar“-Tooltip).
- [ ] Klick öffnet den vorhandenen `CategoryDialog`.
- [ ] Anlegen / Umbenennen / Löschen funktioniert und wird in `categories.json` der aktiven Instanz gespeichert.
- [ ] Nach Schließen sind Änderungen sofort in Mod-Liste UND Filter-Panel sichtbar (Refresh über erprobten Pfad).
- [ ] Kein Crash, wenn keine Instanz / keine Mods geladen sind (Guard greift).
- [ ] Der bisher tote Import `CategoryDialog` (mainwindow.py:82) wird jetzt tatsächlich verwendet.
- [ ] Kein `setStyleSheet()` in neuem Code.
- [ ] `./restart.sh` startet fehlerfrei (kein NameError/ImportError/AttributeError im Log).

**Phase 3 (Farben, falls in Scope):**
- [ ] Farbe pro Kategorie wählbar, persistiert (`color`-Feld in `categories.json`), in Mod-Liste sichtbar.
- [ ] Neue tr-Keys in allen 7 Locales.

**Phase 4 (Reihenfolge, falls in Scope):**
- [ ] Manuelle Reihenfolge per Drag&Drop bleibt nach Neustart erhalten (`order`-Feld + angepasste Sortierung).
- [ ] Neue tr-Keys in allen 7 Locales.

## 8. Aufwand / Risiko
**Aufwand Phase 1+2:** Gering — Dialog existiert vollständig, nur Button aktivieren, eine
MainWindow-Methode anlegen, erprobten Refresh-Pfad wiederverwenden. ~30-50 Zeilen.

**Aufwand Phase 3+4:** Mittel bis hoch — echte Neuentwicklung. Farben brauchen Datenmodell-Feld +
Farbwähler + Rendering. Reihenfolge bricht mit der aktuellen „immer alphabetisch“-Sortierung in
`all_categories()` und braucht ein neues `order`-Feld plus Drag&Drop im Tree.

**Risiko Phase 1+2:** Niedrig — Wiederverwendung erprobter Komponenten, kein Eingriff in
bestehende Flows. Hauptachtung: korrekte Beschaffung von `category_manager`/`mod_entries` und
Guard bei leerer Instanz.
**Risiko Phase 3+4:** Mittel-hoch — Änderung am Datenmodell und an der Sortierlogik berührt
Filter-Panel und Mod-Liste; Migration bestehender `categories.json` (ohne `color`/`order`) beachten.
