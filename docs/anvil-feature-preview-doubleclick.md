# Feature-Spec: Vorschau bei Doppelklick (Setting) (#16)
**Status:** Geplant
**Datum:** 2026-06-28 (verifiziert gegen echten Code)

## 1. Problem / Ziel
Im Einstellungen-Dialog (Tab „Allgemein“, Gruppe „Sonstiges“) gibt es die Checkbox
„Öffnen Sie die Vorschau per Doppelklick“. Sie ist deaktiviert (ausgegraut, fest auf
`Checked`), hat keine Wirkung und wird nirgends gespeichert.

**Issue #16 (Original-Wortlaut):**
- „The preview on double-click option in settings is disabled.“
- Erwartet: Setting zum Aktivieren der Mod-Vorschau bei Doppelklick; Doppelklick auf einen Mod
  öffnet einen Vorschau-Dialog; Vorschau zeigt Mod-Inhalt (Dateien, Screenshots, Beschreibung).
- Status laut Issue: „UI element present in settings but disabled — no backend logic implemented.“

**Kernbefund (verifiziert):** Die Vorschau existiert technisch bereits — der Doppelklick öffnet
schon heute den `ModDetailDialog`, der Text-, INI- und Bilder-Tabs liefert. Es fehlt **nur**:
(a) die Checkbox aktivieren + persistieren, (b) im Doppelklick-Handler das Setting auswerten.
Der Dialog selbst muss **nicht** geändert werden.

## 2. Phasen-Rückgrat (Bau-Reihenfolge nach steigendem Risiko)
| # | Phase | Inhalt | Risiko | Testbar nach Phase? |
|---|---|---|---|---|
| 1 | Checkbox aktivieren | `_disabled(cb_preview)` entfernen, als `self._cb_preview` führen, Init-Wert aus `self._settings()` lesen (Default `True`) | Sehr niedrig | Ja — Checkbox ist bedienbar, Häkchen sichtbar |
| 2 | Persistenz | In `accept()` `Interface/open_preview_dblclick` über `settings.setValue(...)` schreiben; nach Neustart wird Wert geladen | Niedrig | Ja — Setting toggeln, Dialog neu öffnen → Wert bleibt |
| 3 | Handler-Guard | In `_on_mod_double_click` zu Beginn Setting prüfen, bei `False` früh `return` | Niedrig (Verhaltensänderung am Default-Pfad) | Ja — Setting AUS → Doppelklick öffnet nichts; AN → Dialog öffnet |
| 4 | i18n-Politur (optional) | DE-Text „Öffnen Sie die Vorschau per Doppelklick“ → „Vorschau bei Doppelklick öffnen“ in allen 7 Locales angleichen (nur mit GO von Marc) | Sehr niedrig | Ja — Sichtprüfung Label |

Reihenfolge bewusst: erst die rein additive UI-Aktivierung (Phase 1/2, kein Verhaltensbruch),
zuletzt der Guard im Default-Pfad (Phase 3), der das einzige laufzeitwirksame Verhalten ändert.

## 3. Ist-Zustand im Code (nur verifizierte Anker)
| Stelle | Datei:Zeile | Befund (verifiziert) |
|---|---|---|
| Checkbox (deaktiviert) | `anvil/widgets/settings_dialog.py:165-168` | `cb_preview = QCheckBox(tr("settings.open_preview_dblclick"))` → `setChecked(True)` → `_disabled(cb_preview)` → `addWidget` |
| `_disabled`-Helper | `anvil/widgets/settings_dialog.py:73-76` | `setEnabled(False)` + `setToolTip(tr("settings.coming_soon"))`, gibt `w` zurück |
| `settings`-Variable (Init-Scope) | `anvil/widgets/settings_dialog.py:60` | `settings = self._settings()` — steht in `__init__` zur Verfügung (gleiches `settings` nutzen die Nachbar-Checkboxen z. B. Zeile 163) |
| `_settings()` (Pfad!) | `anvil/widgets/settings_dialog.py:1000-1002` | `QSettings(~/.config/AnvilOrganizer/AnvilOrganizer.conf, IniFormat)` — **kein** bare `QSettings()` |
| Save-Routine | `anvil/widgets/settings_dialog.py:1050` (`accept`) | `settings = self._settings()` (Z.1052); `Interface/...`-Block: **Zeilen 1060-1065** |
| Doppelklick-Signal | `anvil/mainwindow.py:214` | `self._mod_list_view._tree.doubleClicked.connect(self._on_mod_double_click)` |
| Doppelklick-Handler | `anvil/mainwindow.py:2520-2566` | `_on_mod_double_click(self, index=None)` öffnet **immer** `ModDetailDialog` (Z.2542) |
| `_settings()` in MainWindow | `anvil/mainwindow.py:5883-5887` | identischer Pfad `~/.config/AnvilOrganizer/AnvilOrganizer.conf` — im Handler `self._settings()` verwenden |
| `ModDetailDialog` (Import) | `anvil/mainwindow.py:50` | `from anvil.dialogs import ModDetailDialog` |
| `ModDetailDialog` (Klasse) | `anvil/dialogs/mod_detail_dialog.py:1518` | liefert die geforderten Inhalte; **keine Änderung nötig** |
| Tab Textdateien | `anvil/dialogs/mod_detail_dialog.py:1540` | `addTab(_build_textfiles_tab(...), tr("mod_detail.tab_textfiles"))` |
| Tab INI | `anvil/dialogs/mod_detail_dialog.py:1542` | `addTab(_build_ini_tab(...), tr("mod_detail.tab_ini"))` |
| Tab Bilder | `anvil/dialogs/mod_detail_dialog.py:1545` | `addTab(_build_images_tab(...), tr("mod_detail.tab_images"))` |

**Hinweis Anker-Korrektur:** Die Tab-Zeilen waren im Erstentwurf um eins versetzt (1539/1541/1544 →
real 1540/1542/1545). Die Save-Stelle war fälschlich mit „~1086“ angegeben — 1086 ist eine
`Nexus/...`-Einstellung; der korrekte `Interface/...`-Block liegt bei 1060-1065 in `accept()` (Z.1050).

## 4. Betroffene Dateien
| Datei | Änderung |
|---|---|
| `anvil/widgets/settings_dialog.py` | Checkbox aktivieren (`_disabled` raus), als `self._cb_preview` führen, Init aus `settings.value("Interface/open_preview_dblclick", True, type=bool)`; in `accept()` (Z.1050) im `Interface/`-Block (Z.1060-1065) speichern |
| `anvil/mainwindow.py` | `_on_mod_double_click` (Z.2520): Setting-Guard am Anfang über `self._settings()` |
| `anvil/locales/*.json` (7×) | nur falls DE-Text geglättet wird (Key `open_preview_dblclick` existiert bereits in allen 7) |

## 5. Umsetzungsschritte
1. **settings_dialog.py (Z.165-168):** `_disabled(cb_preview)` entfernen. Checkbox als
   `self._cb_preview` führen und Init-Wert setzen:
   ```python
   self._cb_preview = QCheckBox(tr("settings.open_preview_dblclick"))
   self._cb_preview.setChecked(
       settings.value("Interface/open_preview_dblclick", True, type=bool))
   misc_layout.addWidget(self._cb_preview)
   ```
   (`settings` ist die Variable aus Z.60 — gleiches Muster wie `self._cb_alt_menubar`, Z.161-164.)
2. **settings_dialog.py `accept()` (Z.1050):** im `Interface/...`-Block (nach Z.1065) ergänzen:
   ```python
   settings.setValue("Interface/open_preview_dblclick", self._cb_preview.isChecked())
   ```
3. **mainwindow.py `_on_mod_double_click` (Z.2520):** ganz am Anfang der Methode:
   ```python
   if not self._settings().value("Interface/open_preview_dblclick", True, type=bool):
       return
   ```
   **Wichtig:** `self._settings()` (Z.5883-5887) verwenden, **nicht** bare `QSettings()` —
   sonst wird der falsche (leere) Store gelesen und der Default greift immer.
4. **Default-Konsistenz:** Default `True` an allen drei Stellen identisch (Init, Save, Guard),
   damit das heutige Verhalten erhalten bleibt.
5. **Inhalt:** Dateien/Screenshots/Beschreibung sind durch die vorhandenen ModDetail-Tabs
   (Z.1540/1542/1545) abgedeckt — **keine** Dialog-Änderung.
6. `./restart.sh`, Log auf Tracebacks prüfen.

## 6. i18n (tr-Keys, 7 Locales)
**Vorhanden (in allen 7 Locales `anvil/locales/{de,en,es,fr,it,pt,ru}.json` unter `settings.open_preview_dblclick`):**
- de: „Öffnen Sie die Vorschau per Doppelklick“
- en: „Open preview on double-click“
- es: „Abrir vista previa con doble clic“
- fr: „Ouvrir l'aperçu en double-cliquant“
- it: „Apri anteprima con doppio clic“
- pt: „Abrir prévia com duplo clique“
- ru: „Открывать предпросмотр двойным щелчком“

**Keine neuen Keys nötig.** Optionale Glättung des DE-Texts auf „Vorschau bei Doppelklick öffnen“
nur nach GO von Marc; dann in allen 7 Locales konsistent angleichen.

## 7. Akzeptanzkriterien
- [ ] Checkbox „Vorschau bei Doppelklick“ ist aktiv (nicht ausgegraut) und bedienbar.
- [ ] Zustand wird unter `Interface/open_preview_dblclick` in `~/.config/AnvilOrganizer/AnvilOrganizer.conf` gespeichert und beim Neustart geladen.
- [ ] Checkbox AN: Doppelklick auf einen Mod öffnet den `ModDetailDialog` (Text-/INI-/Bilder-Tab).
- [ ] Checkbox AUS: Doppelklick öffnet keinen Dialog.
- [ ] Default-Verhalten unverändert (Setting standardmäßig an).
- [ ] Handler liest über `self._settings()` (nicht bare `QSettings()`).
- [ ] Kein `setStyleSheet()` in neuem Code.
- [ ] `./restart.sh` startet fehlerfrei (keine Tracebacks im Log).

## 8. Aufwand / Risiko
**Aufwand:** Sehr gering — Checkbox aktivieren/persistieren + ein Guard im vorhandenen Handler.
Der Vorschau-Dialog existiert und funktioniert bereits.
**Risiko:** Niedrig — additiv mit Default „an“, daher kein Verhaltensbruch. Zwei Stolpersteine:
(1) konsistente Default-Werte an allen drei Stellen, (2) **zwingend** `self._settings()` statt
bare `QSettings()` verwenden, sonst greift die Persistenz nicht.
