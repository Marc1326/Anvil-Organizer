# Offene Features — Einbau-Plan

Stand: 2026-07-03, Branch `v2/modern-gui`, alle Code-Anker gegen HEAD `e9d2f31` verifiziert.
Quellen: GitHub-Issues #14/#15/#16/#17/#20, Feature-Specs in `docs/anvil-feature-*.md`,
Code-Verifikation vom 2026-07-03.

**WICHTIG:** Die Feature-Specs vom 2026-06-28 sind inhaltlich weiter gültig, aber ihre
Zeilennummern stimmen wegen des GUI-v2-Umbaus NICHT mehr. Dieses Dokument enthält die
**aktuellen** Anker — bei Widerspruch zwischen Spec und diesem Dokument gilt dieses Dokument.

Es gilt derselbe Regelblock wie in `docs/anvil-offene-bugs-fixplan.md` (PFLICHT lesen):
ein Feature → testen (`./restart.sh` + Log) → committen; kein `setStyleSheet()`; keine
hardcoded Pfade; neue tr()-Keys in ALLEN 7 Locales (de,en,es,fr,it,pt,ru); keine
Co-Authored-By-Zeile; bei Unklarheit Marc fragen.

**Empfohlene Reihenfolge** (nach Aufwand aufsteigend, jede Stufe einzeln committen):
1. #16 Vorschau bei Doppelklick (winzig)
2. #20 Nexus Cache-Button (klein)
3. #14 Notifications fertigstellen (klein)
4. #17 Kategorien-Editor (mittel — Dialog muss neu gebaut werden)
5. #15 Archive Invalidation (groß — eigene Session)

Die Prio-1-Bugs aus `anvil-offene-bugs-fixplan.md` sollten VOR den Features gemacht werden.

---

# Feature #16 — Vorschau bei Doppelklick (Setting verdrahten)

**Spec:** `docs/anvil-feature-preview-doubleclick.md` — gilt vollständig, nur Anker neu.
**Issue #16:** open. **Aufwand:** sehr gering (~10 Zeilen).

## Ist-Zustand (verifiziert)
- Der Doppelklick öffnet bereits IMMER den `ModDetailDialog`:
  Connect `mainwindow.py:243`, Handler `_on_mod_double_click` `mainwindow.py:2815`.
  Der Dialog liefert Dateien/Bilder/Beschreibung — **keine Dialog-Änderung nötig**.
- Die Checkbox ist ein toter Platzhalter: `settings_dialog.py:241-244`
  (`cb_preview` → `setChecked(True)` → `_disabled(...)`), wird nirgends gespeichert.
- Der Settings-Key `Interface/open_preview_dblclick` existiert noch nirgends im Code.

## Umsetzung
1. `settings_dialog.py:241-244`: `_disabled(...)` entfernen, Checkbox als
   `self._cb_preview` führen, Init-Wert aus
   `settings.value("Interface/open_preview_dblclick", True, type=bool)` —
   exakt das Muster der Nachbar-Checkbox `self._cb_alt_menubar` (Zeile 237-240)
   übernehmen, inkl. `self._setting_row(...)`-Wrapper.
2. In `accept()` (`settings_dialog.py:1781`) im Interface-Block (Zeilen 1799-1805)
   ergänzen: `settings.setValue("Interface/open_preview_dblclick", self._cb_preview.isChecked())`.
3. In `_on_mod_double_click` (`mainwindow.py:2815`) ganz am Anfang:
   ```python
   if not self._settings().value("Interface/open_preview_dblclick", True, type=bool):
       return
   ```
   ZWINGEND `self._settings()` (`mainwindow.py:6298`) verwenden, NICHT bare `QSettings()`.
4. Default `True` an allen drei Stellen identisch → heutiges Verhalten bleibt Standard.
5. Keine neuen tr()-Keys nötig (`settings.open_preview_dblclick` existiert in allen 7).

## Akzeptanz
- Checkbox aktiv + bedienbar; Zustand überlebt Neustart.
- AN: Doppelklick öffnet ModDetailDialog. AUS: Doppelklick tut nichts.
- `./restart.sh` ohne Tracebacks.

---

# Feature #20 — Nexus Options: Rest = Cache-Button

**Spec:** `docs/anvil-feature-nexus-options.md` — gilt, Anker neu.
**Issue #20:** open. **Aufwand:** gering (~40 Zeilen + 7 Locale-Edits).

## Ist-Zustand (verifiziert)
Vier der fünf Teil-Funktionen sind FERTIG — nicht anfassen:
- Tracking: `self._cb_nexus_tracking` (`settings_dialog.py:718-721`), Save `:1824`.
- Category Mapping: `self._cb_nexus_catmap` (`:724-727`), Save `:1826`;
  Backend `anvil/core/nexus_categories.py` komplett.
- NXM-Handler: `self._btn_nxm_link` (`:737`) → `_nx_register_nxm_handler` (`:2106`).
- Hide-API-Counter: `self._cb_nexus_hide_api` (`:730-733`).

**Einziges offenes Element:** `_disabled(QPushButton(tr("settings.nexus_clear_cache")))`
an `settings_dialog.py:739`.

**Endorsement existiert NICHT** (kein `endorse` im Code, verifiziert) — wurde per Commit
`4341634` (2026-04-05) bewusst komplett entfernt. → NICHT bauen, siehe offene Frage 1.

## Umsetzung (Cache-Button)
1. **i18n:** Key `status.nexus_cache_cleared` in ALLE 7 Locales
   (DE: „Nexus-Cache geleert", EN: „Nexus cache cleared", Rest analog übersetzen).
2. **mainwindow:** neuer Slot `_clear_nexus_cache(self)`:
   - Instanzpfad aus `self._current_instance_path` (Guard: `if not ... : return`).
   - Cache-Datei löschen — Dateiname aus `NexusCategoryCache.FILENAME`
     (`anvil/core/nexus_categories.py:96`), NICHT hartkodieren;
     `unlink(missing_ok=True)` in try/except OSError.
   - `self._last_nexus_chip_ids = None` setzen (Dedup-Feld, siehe `mainwindow.py:5476-5478`),
     dann `self._populate_nexus_filter_chips()` (`mainwindow.py:5444`) aufrufen →
     Chips verschwinden.
   - `self.statusBar().showMessage(tr("status.nexus_cache_cleared"), 3000)` —
     Muster wie `_clear_modindex_cache` (`mainwindow.py:957`).
3. **settings_dialog:** Konstruktor-Param `on_clear_nexus_cache=None` ergänzen —
   exakt analog zu `on_clear_modindex` (Signatur `:78`, Zuweisung `:83`,
   Connect-Muster `:628-629`). Button an `:739` aktivieren (kein `_disabled`),
   als `self._btn_nexus_clear_cache` führen, Click verbinden.
4. **Call-Site:** `mainwindow.py:862-866` — `on_clear_nexus_cache=self._clear_nexus_cache`
   mit durchreichen.

## Akzeptanz
- Button aktiv; Klick löscht `nexus_categories.json` der aktuellen Instanz,
  Nexus-Filter-Chips verschwinden, StatusBar-Meldung erscheint.
- Kein Crash ohne Instanz / ohne Cache-Datei.
- Tracking/Catmap/NXM/Hide-API funktionieren unverändert (Regressions-Check).

---

# Feature #14 — Notifications fertigstellen

**Issue #14:** bereits CLOSED — Kern ist GEBAUT (Commit e70c157). Die Status-Tabelle
mit „nicht begonnen" ist überholt. **Aufwand:** gering.

## Ist-Zustand (verifiziert)
- `NotificationCenter` + `NotificationPanel` + Toolbar-Glocke (`toolbar.py:279-292`)
  + Titelzeilen-Button (`mainwindow.py:650-653`, Handler `:7568`) existieren und laufen.
- Aktuelle Quellen (alle in `mainwindow.py`): Download fertig (`:7616`),
  Download-Fehler (`:7620`), Mod-Update verfügbar (`:7627`).

## Was fehlt (zwei Teile)
**Teil A — Politur (PFLICHT):** Das sind die Bugs 14, 15, 16 aus
`docs/anvil-offene-bugs-fixplan.md` — dort beschrieben:
1. Toter Menüeintrag „Benachrichtigungen…" (`mainwindow.py:575-576`) verdrahten/entfernen.
2. Panel bei neuen Meldungen live aktualisieren (`center.changed` → `_refresh`).
3. `NotificationCenter` auf max. 100 Einträge deckeln.

**Teil B — fehlende Quellen (siehe offene Frage 3):** Das Issue nannte auch
„deploy status" und „errors" als Quellen. Falls Marc das will:
- Nach Deploy-Abschluss (Erfolg/Fehler) eine Notification einstellen — das
  `self._notification_center.add("info"/"error", tr(...), detail)`-Muster von
  `mainwindow.py:7616-7627` kopieren und an die Stelle hängen, wo das Deploy-Ergebnis
  verarbeitet wird (Suche: wo `DeployResult` bzw. `result.errors` nach dem Deploy
  ausgewertet wird — `grep -n "deploy" anvil/mainwindow.py` bzw. `game_panel.py`).
- Neue tr()-Keys `notifications.deploy_done` / `notifications.deploy_failed`
  in ALLEN 7 Locales.

---

# Feature #17 — Kategorien-Editor (Button in den Einstellungen)

**Spec:** `docs/anvil-feature-edit-categories-button.md` — **Phase 1 der Spec ist
NICHT mehr umsetzbar wie geschrieben** (siehe unten). Phasen-Logik gilt weiter.
**Issue #17:** open. **Aufwand:** mittel (~100-150 Zeilen, Dialog-Neubau).

## Ist-Zustand (verifiziert — WICHTIGE ABWEICHUNG von der Spec)
- Der Button ist weiter tot: `settings_dialog.py:255`
  (`misc_btn_row.addWidget(_disabled(QPushButton(tr("settings.edit_categories"))))`).
- **Der `CategoryDialog`, auf den die Spec baut, wurde im GUI-Umbau ENTFERNT**
  (Commit 87121e3 „toten CategoryDialog entfernt"). `anvil/widgets/category_dialog.py`
  enthält nur noch `CategoryNameDialog` (Namens-Eingabedialog, `:16`) — der wird vom
  Filter-Panel weiterverwendet. Der Import in mainwindow ist weg.
- Das Filter-Panel kann bereits: Kategorie anlegen (`filter_panel.py:440 _add_category`,
  über den „Bearbeiten"-Link), umbenennen (`:460`) und löschen (`:483`) über das
  Kontextmenü der Chips (`:409-416`).
- Datenmodell (`anvil/core/categories.py`): Einträge sind `{"id": int, "name": str}` —
  KEIN `color`-Feld, KEIN `order`-Feld; `all_categories()` sortiert IMMER alphabetisch.
  `add/rename/remove_category` speichern selbst nach `categories.json` (pro Instanz).

## Umsetzung Phase 1+2 (Kern des Issues)
1. **Neuen kleinen Editor-Dialog bauen** (der alte passt nicht mehr zum v2-Design):
   `anvil/widgets/category_editor_dialog.py` — Liste aller Kategorien
   (`CategoryManager.all_categories()`, Anzeige über `get_display_name` aus
   `categories.py:62`), Buttons Neu / Umbenennen / Löschen.
   - Optik: das Muster der kleinen v2-Dialoge mit Modal-Hülle übernehmen
     (Vorbild ansehen: z. B. wie `CategoryNameDialog` bzw. die kleinen Dialoge
     aus Commit faf5d9c aufgebaut sind — gleiche Hülle, gleiche Fußzeile).
     KEIN `setStyleSheet()`, objectNames + QSS wie bei den anderen v2-Dialogen.
   - Eingabe für Neu/Umbenennen: den vorhandenen `CategoryNameDialog` wiederverwenden.
   - Löschen: Bestätigung + Hinweis, wenn Mods die Kategorie nutzen
     (Zuordnungs-Zähler aus `mod_entries` — das machte der alte Dialog auch;
     bei Bedarf alten Code als Referenz ansehen:
     `git show 87121e3^:anvil/widgets/category_dialog.py`).
2. **mainwindow:** neue Methode `open_category_editor(self)`:
   - Guard: `if not self._current_instance_path: return` (+ Statusbar-Hinweis).
   - Dialog mit `self._category_manager` + `self._current_mod_entries` bauen,
     `_center_on_parent(dlg)`, `dlg.exec()`.
   - Danach der erprobte Refresh-Pfad (verifiziert `mainwindow.py:1457/5520/5553`):
     `self._filter_panel.set_categories(self._category_manager.all_categories())`
     und `self._reload_mod_list()`.
3. **settings_dialog.py:255:** `_disabled` raus, Button als Variable,
   `clicked.connect(lambda checked=False: self._open_category_editor())` mit
   Helper, der `getattr(self.parent(), "open_category_editor", None)` prüft
   (defensiv, Parent ist MainWindow — Call-Site `mainwindow.py:862`).
4. **tr()-Keys:** `settings.edit_categories`, `button.new/rename/delete/close`,
   `dialog.categories_title` existieren laut Spec in allen 7 Locales —
   VOR Verwendung mit grep gegenprüfen; fehlende Keys in allen 7 anlegen.

## Phase 3 (Farben) + Phase 4 (Reihenfolge per Drag&Drop) — NUR nach Entscheidung
Beides ist echte Neuentwicklung am Datenmodell (color-/order-Feld in `categories.json`,
Migration von Bestandsdaten, Sortierlogik ändern, Rendering der Kategorie-Pills in der
Mod-Liste). Details stehen in der Spec §2 (Phasen 3+4). → Offene Frage 2 unten.
NICHT ohne Entscheidung anfangen.

## Akzeptanz (Phase 1+2)
- Button in Einstellungen aktiv; öffnet den Editor.
- Anlegen/Umbenennen/Löschen wirkt sofort in Mod-Liste + Filter-Panel und ist
  in `categories.json` der Instanz persistiert.
- Kein Crash ohne Instanz. `./restart.sh` sauber.

---

# Feature #15 — Archive Invalidation (Skyrim SE / Fallout 4)

**Spec:** `docs/anvil-feature-archive-invalidation.md` — inhaltlich VOLLSTÄNDIG und
weiter gültig (INI-Einträge, Modul-Design, Idempotenz, Risiken). Der Spec §6 folgen.
Nur die folgenden Anker haben sich geändert. **Aufwand:** ~1 Session.

## Anker-Korrekturen gegenüber der Spec (verifiziert 2026-07-03)
| Spec sagt | Aktuell |
|---|---|
| Settings-Checkbox `settings_dialog.py:147` | jetzt `settings_dialog.py:223` |
| `accept()` `:1050`, idata-Save `:1121-1123` | jetzt `accept()` `:1781`, idata-Save `:1865-1867` |
| `silent_deploy()` `game_panel.py:653`, BA2 `update_ini` `:693` | jetzt `:1002`, `update_ini` `:1042` |
| `silent_deploy_fast()` `:748` | jetzt `:1097` |
| `silent_purge()` `:769`, `restore_ini` `:786` | jetzt `:1118`, `restore_ini` `:1135` |
| Wizard-Checkbox `instance_wizard.py:369-375/596/617` | jetzt `:565-568` / `:797` / `:818` |
| Profil-Dialog-Checkbox `profile_dialog.py:83-85` | **EXISTIERT NICHT MEHR** (GUI-Umbau) → Spec-Phase 6 und offene Spec-Frage 2 entfallen ersatzlos |
| `save_instance()` `instance_manager.py:300-309` | jetzt `:346ff` |

## Umsetzung (Kurzfassung — Details in Spec §4-§6)
1. **Persistenz:** `save_instance()` (`instance_manager.py:346ff`) um Branch
   `if "auto_archive" in data: s.setValue("auto_archive", data["auto_archive"])`
   in der General-Gruppe ergänzen. (Deckt sich teilweise mit Bug 24 im Fixplan.)
   Der Key heißt `auto_archive` — KEINEN neuen Key erfinden, der Wizard schreibt
   ihn bereits (`instance_wizard.py:797/818`).
2. **Plugin-Attribute** in `base_game.py` (Defaults aus/leer) + `game_skyrimse.py` /
   `game_fallout4.py` setzen: `SupportsArchiveInvalidation`, `ArchiveInvalidationIniFile`
   (`SkyrimCustom.ini` / `Fallout4Custom.ini`), Section `Archive`, Entries
   `{"bInvalidateOlderFiles": "1", "sResourceDataDirsFinal": ""}`.
3. **Neues Modul `anvil/core/archive_invalidation.py`:** Klasse `ArchiveInvalidator`
   mit `ini_path()/is_supported()/enable()/disable()` — nach `ba2_packer.py`-Muster
   (ConfigParser, `optionxform=str`, **cp1252**), eigenes Backup `.anvil_ai_backup`
   (nur EINMAL anlegen), idempotent, fasst NUR die eigenen Keys an
   (`sResourceArchiveList2` vom BA2-Packing niemals berühren). Pfad selbst über
   `gameDocumentsDirectory()` auflösen (`ba2_ini_path()` ist auf `NeedsBa2Packing`
   gated → nicht wiederverwenden). `ini_path() is None` → no-op, kein Crash.
4. **Settings-UI:** Checkbox `settings_dialog.py:223` echt machen
   (`self._cb_archive_inval`), Init aus `self._idata.get("auto_archive", ...)`
   (Muster `local_inis` in der Nähe), Speichern in `accept()` beim idata-Block
   (`:1865-1867`): `idata["auto_archive"] = self._cb_archive_inval.isChecked()`.
5. **Deploy/Purge-Hooks in `game_panel.py`:** in `silent_deploy()` (`:1002`) nach dem
   BA2-Block (`update_ini` `:1042`): wenn Instanz-Flag `auto_archive` UND
   `plugin.SupportsArchiveInvalidation` → `ArchiveInvalidator(plugin).enable()`.
   In `silent_purge()` (`:1118`) nach `restore_ini()` (`:1135`) →
   `ArchiveInvalidator(plugin).disable()`. NICHT in `silent_deploy_fast()` (`:1097`).
6. **i18n:** neuer Key `settings.auto_archive_invalidation_desc` in ALLEN 7 Locales
   (DE: „Lose Mod-Dateien erhalten Vorrang vor den gepackten Spiel-Archiven (BSA/BA2).").
7. **Test:** Skyrim-SE-Instanz → Checkbox an → Deploy → `SkyrimCustom.ini` prüfen
   (`[Archive]` mit beiden Keys, andere Keys unangetastet); Purge → Einträge weg.
   Zweimal Deployen → keine Duplikate, Backup unverändert.

Akzeptanzkriterien: vollständige Liste in der Spec §8 — die gilt 1:1.

---

## Offene Fragen an Marc (VOR dem jeweiligen Feature klären)

1. **#20 Endorsement:** Wurde am 2026-04-05 (Commit 4341634) bewusst komplett entfernt.
   Reaktivieren (Issue nennt „auto-endorse after X hours") oder #20 nach dem
   Cache-Button ohne Endorsement schließen? → Ohne Antwort: NUR Cache-Button bauen.
2. **#17 Farben + Reihenfolge:** Gehören Phase 3 (Kategorie-Farben) und Phase 4
   (Drag&Drop-Reihenfolge) in dieses Issue, oder reicht Phase 1+2 (Editor mit
   Anlegen/Umbenennen/Löschen)? → Ohne Antwort: NUR Phase 1+2 bauen.
3. **#14 Deploy-/Fehler-Quellen:** Sollen Deploy-Ergebnis und allgemeine Fehler
   zusätzlich als Benachrichtigungen erscheinen (Teil B), oder gilt #14 mit der
   Politur aus Teil A als fertig? → Ohne Antwort: NUR Teil A umsetzen.
4. **#15 Wirksamkeits-Test:** Soll die Wirkung der INI-Einträge nach dem Einbau am
   echten Skyrim-SE-Proton-Setup gegengetestet werden (empfohlen), oder reicht das
   etablierte Vortex-Eintrags-Paar?
