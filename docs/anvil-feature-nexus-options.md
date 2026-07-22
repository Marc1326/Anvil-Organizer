# Feature-Spec: Nexus Options (#20)
**Status:** Teilweise umgesetzt — nur "Cache" offen
**Datum:** 2026-06-28 (verifiziert gegen echten Code)

> Konsolidierter Plan über alle 5 Teil-Funktionen aus GitHub-Issue #20.
> Löst die alten Specs `anvil-feature-nexus-options.md` (Stand 2026-04-04) und
> `anvil-feature-nexus-endorsement-catmap.md` (Stand 2026-04-05) ab.
> Alle Code-Anker unten wurden per `grep`/`Read` gegen den aktuellen Stand geprüft.

---

## 1. Problem / Ziel

Issue #20 (OPEN, Labels `disabled-feature`, `enhancement`):
*"All Nexus options in the settings dialog are disabled."* — Status laut Issue:
*"UI elements present but all disabled — requires Nexus connection (#19)."*

Im Nexus-Tab des Settings-Dialogs gab es ursprünglich eine "Optionen"-Box mit
ausgegrauten Checkboxen/Buttons. Die fünf im Issue genannten Funktionen:

1. **Endorsement** — Mods nach X Stunden Nutzung automatisch auf Nexus endorsen.
2. **Tracking** — Nexus-Mod-Tracking aktivieren/deaktivieren.
3. **Category Mapping** — Nexus-Kategorien auf lokale Kategorien abbilden.
4. **NXM-Handler** — Anvil als `nxm://`-Handler registrieren (1-Click-Install).
5. **Cache** — Nexus-API-Cache verwalten (Issue: "duration, size, manual clear").

**Realität (gegen Code verifiziert):** Drei der fünf Teile sind voll
implementiert (Tracking, Category Mapping, NXM-Handler). Endorsement wurde
bewusst per Commit `4341634` (2026-04-05) komplett entfernt. Der
Nexus-spezifische "Cache leeren"-Button ist das **einzige** verbliebene
deaktivierte Optionen-Element. Die im Issue genannte Blockade "#19" ist
aufgehoben (API-Key/SSO/Rate-Limit im Settings-Dialog vorhanden).

→ **Effektiv für #20 offen: nur der Nexus-Cache-Button.**

---

## 2. Phasen-Rückgrat (Bau-Reihenfolge nach steigendem Risiko)

| # | Phase | Inhalt | Risiko | testbar nach Phase? |
|---|-------|--------|--------|----------------------|
| 0 | Regressions-Check der fertigen Teile | Tracking, Category Mapping, NXM-Handler, Hide-API manuell gegen Akzeptanzkriterien gegenprüfen — KEINE Code-Änderung | keins | Ja — bestätigt, dass #20 außer Cache geschlossen werden kann |
| 1 | i18n-Key `status.nexus_cache_cleared` | Neuen Status-Key in alle 7 Locales (de,en,es,fr,it,pt,ru), Wert je Sprache | niedrig | Ja — `python -c json.load` pro Datei, kein UI nötig |
| 2 | mainwindow-Slot `_clear_nexus_cache()` | Löscht `nexus_categories.json` der aktuellen Instanz (Pfad aus Instanz-Config), resettet `_last_nexus_chip_ids`, ruft `_populate_nexus_filter_chips()`, StatusBar-Meldung; robust wenn keine Instanz/kein Cache | niedrig | Ja — Methode isoliert per Konsole/Logik prüfbar |
| 3 | settings_dialog: Button aktivieren + Callback | `_disabled(...)`-Wrapper an `settings_dialog.py:510` entfernen, Button als Member halten, Konstruktor-Param `on_clear_nexus_cache` (analog `on_clear_modindex`), Click verbinden | niedrig | Ja — Button klickbar, ruft Slot |
| 4 | Verdrahtung im Call-Site | `on_clear_nexus_cache=self._clear_nexus_cache` an `SettingsDialog(...)` in `mainwindow.py:755` durchreichen | niedrig | Ja — `./restart.sh`, Klick im Dialog, Cache verschwindet, StatusBar-Meldung |
| 5 | (blockiert) Endorsement | Nur bei explizitem GO von Marc — bewusst entfernt (Produktentscheidung) | Produkt | n/a |

Bau-Logik: erst i18n (kann nicht brechen), dann reine Backend-Löschlogik, dann
UI-Aktivierung, zuletzt Verdrahtung. Jede Phase ist für sich testbar.

---

## 3. Ist-Zustand im Code (nur VERIFIZIERTE Anker)

### 3.1 Endorsement — **ENTFERNT (nicht aktiv)**
Per Commit `4341634` ("entferne Endorsement-Feature komplett, fix .meta
ConfigParser case bug", 2026-04-05) zurückgebaut. Verifiziert:

- `anvil/dialogs/endorsement_dialog.py` — existiert NICHT (`ls` schlägt fehl).
- `anvil/core/mod_entry.py:46` `nexus_id: int = 0`, `:67` `nexus_category: int = 0`
  — KEIN `endorsed`-Feld (grep findet keins).
- `anvil/core/nexus_api.py` — KEINE `endorse_mod()`/`abstain_mod()` (grep leer).
  POST-Infrastruktur aber vorhanden: `_ApiPostWorker` (`nexus_api.py:62`),
  `_post()` (`nexus_api.py:211`) — derzeit ungenutzt.
- `anvil/widgets/settings_dialog.py` — Optionen-Box (`opt_left`) hat NUR Tracking
  (`:489`), Category-Mapping (`:495`), Hide-API (`:501`) — keine Endorsement-Checkbox.
- Locale-Dateien — KEINE `endorse*`-Keys.
- `anvil/widgets/toolbar.py:218` `donate_btn = _add_btn("endorse.svg", "Support / Donate")`
  — `endorse.svg` ist ein **Support/Donate**-Button, KEIN Endorsement (nicht verwechseln).

→ **Endorsement bewusst entfernt. Reaktivierung nur auf ausdrückliches GO** (offene Produktfrage, §6).

### 3.2 Tracking (Update-Check) — **ERLEDIGT**
- Checkbox `self._cb_nexus_tracking` (`settings_dialog.py:489`), gespeichert als
  `Nexus/tracking_enabled` (`settings_dialog.py:1084`, Default `True`).
- Gate für Post-Install-Update-Check: `s.value("Nexus/tracking_enabled", True, type=bool)`
  (`mainwindow.py:2408`).
- Update-Pipeline: `update_check_mod()` (`nexus_api.py:161`), Queue
  `_update_check_queue` (`mainwindow.py:339`), `_update_check_next()`
  (`mainwindow.py:2440`), Befüllung mit Throttling (`mainwindow.py:2417-2433`,
  nutzt `entry.nexus_id > 0`).

→ **Erledigt.**

### 3.3 Category Mapping — **ERLEDIGT**
- Checkbox `self._cb_nexus_catmap` (`settings_dialog.py:495`), gespeichert als
  `Nexus/category_mapping_enabled` (`settings_dialog.py:1086`, Default `True`),
  Gate `mainwindow.py:5103`.
- `anvil/core/nexus_categories.py`: Mapping-Tabelle `_NEXUS_TO_ANVIL` (`:18`),
  Klasse `NexusCategoryCache` (`:93`, `FILENAME = "nexus_categories.json"` `:96`),
  `assign_nexus_categories()` (`:162`).
- Lade-/Refresh-Logik: `_load_nexus_categories()` (`mainwindow.py:5100`),
  API-Call `get_game_info()` (`nexus_api.py:205`, Tag `game_categories:{game}`),
  Response-Handler `mainwindow.py:5687` (schreibt via `NexusCategoryCache.save`).
- Filter-Chips: `_populate_nexus_filter_chips()` (`mainwindow.py:5119`),
  Dedup über `_last_nexus_chip_ids` (`mainwindow.py:5153`).
- Kontextmenü: Menü-Eintrag "Kategorie neu zuordnen" (`mainwindow.py:2853`,
  `tr("context.reassign_category")`) → `_ctx_reassign_category()` (`:5198`);
  "Kategorien automatisch zuweisen" (`mainwindow.py:2594`,
  `tr("context.auto_assign_categories")`) → `_ctx_auto_assign_categories()` (`:5169`).

→ **Erledigt.**

### 3.4 NXM-Handler — **ERLEDIGT**
- Button `self._btn_nxm_link` aktiv (`settings_dialog.py:507`), Click →
  `_nx_register_nxm_handler()` (`settings_dialog.py:1314`, ruft `register_nxm_handler()`).
- `anvil/core/nxm_handler.py`: `register_nxm_handler()` (`:111`),
  `_build_exec_command()` (`:156`, erkennt Flatpak/AppImage/frozen/Dev),
  `parse_nxm_url()` (`:35`), `is_collection_nxm()` (`:83`),
  `get_nxm_arg()` (`:98`), `check_cli_for_nxm()` (`:197`).
- Collection-Links werden seit #91 erkannt und gemeldet statt zu crashen.

→ **Erledigt.**

### 3.5 Cache — **TEILWEISE**
- **Mod-Index-Cache leeren:** aktiv. Button mit Text `tr("settings.clear_modindex_cache")`
  (`settings_dialog.py:397`), verbunden via Konstruktor-Callback `on_clear_modindex`
  (`settings_dialog.py:47/399-400`) → Slot `_clear_modindex_cache()`
  (`mainwindow.py:837`): leert `self._mod_index` und zeigt `tr("status.modindex_cleared")`.
  Call-Site: `SettingsDialog(..., on_clear_modindex=self._clear_modindex_cache)`
  (`mainwindow.py:755-759`).
- **Webcache-Pfad:** im Pfade-Tab read-only angezeigt als `ipath / ".webcache"`
  (`settings_dialog.py:380`), aber NICHT vom Code verwaltet/geleert (grep
  `webcache` in `mainwindow.py` = leer).
- **Nexus-Cache leeren (Optionen-Box):** Button ist als **einziges** Optionen-Element
  noch `_disabled(QPushButton(tr("settings.nexus_clear_cache")))` (`settings_dialog.py:510`);
  `_disabled()` setzt disabled + Tooltip `settings.coming_soon` (`settings_dialog.py:73-75`).
  Locale-Key `settings.nexus_clear_cache` existiert in allen 7 Sprachen (verifiziert).

→ **Offen:** Button aktivieren + lokale Lösch-Logik (`nexus_categories.json`,
optional `.webcache`).

### Zusammenfassung (Soll/Ist)

| Teil-Funktion | Status | Beleg (verifiziert) |
|---------------|--------|----------------------|
| Endorsement | ❌ entfernt / offen | Commit `4341634`; kein `endorsed`-Feld in `mod_entry.py`, keine Checkbox, keine Keys |
| Tracking | ✅ erledigt | `settings_dialog.py:489/1084`, Gate `mainwindow.py:2408` |
| Category Mapping | ✅ erledigt | `nexus_categories.py:18/93/162`, `mainwindow.py:5100/5119/5169/5198` |
| NXM-Handler | ✅ erledigt | `settings_dialog.py:507/1314`, `nxm_handler.py:111/156` |
| Cache | ⚠️ teilweise | `nexus_clear_cache`-Button `_disabled` (`settings_dialog.py:510`) |

---

## 4. Betroffene Dateien

| Datei | Änderung | Teil |
|-------|----------|------|
| `anvil/widgets/settings_dialog.py` | `_disabled`-Wrapper an `:510` entfernen, Button als `self._btn_nexus_clear_cache`, Konstruktor-Param `on_clear_nexus_cache` (analog `on_clear_modindex` `:47`), Click verbinden | Cache |
| `anvil/mainwindow.py` | Neuer Slot `_clear_nexus_cache()`; Callback an `SettingsDialog(...)` (`:755`) durchreichen; Chips neu aufbauen | Cache |
| `anvil/locales/{de,en,es,fr,it,pt,ru}.json` (7) | Neuer Key `status.nexus_cache_cleared` (+ optional `settings.nexus_clear_cache_tooltip`) | i18n |
| *(nur bei Endorsement-GO)* `nexus_api.py`, `mod_entry.py`, `mainwindow.py`, `settings_dialog.py`, `dialogs/endorsement_dialog.py`, 7× Locale | Endorsement reaktivieren | Endorsement |

**Keine Änderung nötig:** `nexus_categories.py`, `nxm_handler.py` (beide fertig),
`nexus_api.py` (Cache ist rein lokal/dateibasiert, keine API).

---

## 5. Umsetzungsschritte

Reihenfolge entspricht dem Phasen-Rückgrat (§2):

1. **Phase 0 — Regressions-Check:** Tracking, Category-Mapping, NXM-Handler,
   Hide-API manuell gegen die Akzeptanzkriterien (§7) gegenchecken. Keine
   Code-Änderung.
2. **Phase 1 — i18n:** Key `status.nexus_cache_cleared` in alle 7 Locales,
   je Sprache passender Wert. `python -c "import json,sys; json.load(open(p))"`
   pro Datei.
3. **Phase 2 — Slot `_clear_nexus_cache()` in `mainwindow.py`:**
   - Aktuelle Instanz ermitteln (`instance_manager.current_instance()`),
     Pfad `instance_manager.instances_path() / name` — **kein** hardcoded Pfad.
   - `nexus_categories.json` löschen (Dateiname aus `NexusCategoryCache.FILENAME`,
     nicht hartkodieren). Optional `.webcache`-Verzeichnis leeren.
   - `self._last_nexus_chip_ids` zurücksetzen (z. B. auf `None`), dann
     `_populate_nexus_filter_chips()` ohne Cache aufrufen, damit Chips verschwinden.
   - `self.statusBar().showMessage(tr("status.nexus_cache_cleared"), 3000)`
     (analog `_clear_modindex_cache`).
   - Robust: kein Crash, wenn keine Instanz/keine Datei vorhanden (`if exists`).
4. **Phase 3 — `settings_dialog.py`:** `_disabled(...)`-Wrapper an `:510`
   entfernen, Button als `self._btn_nexus_clear_cache` halten, Konstruktor um
   `on_clear_nexus_cache=None` erweitern (analog `on_clear_modindex` `:47/51`),
   Click `if self._on_clear_nexus_cache is not None:
   ...clicked.connect(lambda checked=False: self._on_clear_nexus_cache())`.
5. **Phase 4 — Call-Site:** `SettingsDialog(..., on_clear_nexus_cache=self._clear_nexus_cache)`
   an `mainwindow.py:755`. `./restart.sh`, Log auf NameError/ImportError prüfen,
   Button klicken, Cache-Datei + Chips verschwinden, StatusBar-Meldung prüfen.

---

## 6. i18n (tr-Keys, 7 Locales)

**Bereits vorhanden** in `de/en/es/fr/it/pt/ru` (verifiziert):
`settings.nexus_tracking`, `settings.nexus_category_mapping`,
`settings.nexus_hide_api_counter`, `settings.nexus_link_nxm`,
`settings.nexus_clear_cache`, `settings.coming_soon`,
`settings.clear_modindex_cache`, `settings.nxm_handler_title/_success/_failed`,
`status.update_available_mod`, `status.nexus_categories_loaded`,
`status.category_assigned_single`, `status.no_nexus_category`,
`status.modindex_cleared`, `context.reassign_category`,
`context.auto_assign_categories`.

**Neu anzulegen (alle 7 Sprachen, sonst fehlende Übersetzung):**

| Key | DE | EN |
|-----|----|----|
| `status.nexus_cache_cleared` | Nexus-Cache geleert | Nexus cache cleared |
| `settings.nexus_clear_cache_tooltip` *(optional)* | Löscht gecachte Nexus-Kategorien dieser Instanz | Deletes cached Nexus categories for this instance |

*(es/fr/it/pt/ru analog übersetzen. `status.nexus_cache_cleared` ist derzeit in
keiner Locale vorhanden — verifiziert per grep, Count 0.)*

*(Bei Endorsement-Reaktivierung zusätzlich die Endorsement-Keys aus der Alt-Spec
`anvil-feature-nexus-endorsement-catmap.md`.)*

---

## 7. Akzeptanzkriterien

### Cache (neu umzusetzen)
- [ ] 1. Im Nexus-Tab → Optionen ist "Cache leeren" aktivierbar (nicht ausgegraut).
- [ ] 2. Klick löscht `nexus_categories.json` der aktuellen Instanz (Pfad aus
      Instanz-Config, kein hardcoded Pfad, Dateiname aus `NexusCategoryCache.FILENAME`).
- [ ] 3. Nach dem Leeren sind die Nexus-Kategorie-Filter-Chips entfernt und
      werden beim nächsten API-Refresh neu aufgebaut.
- [ ] 4. StatusBar zeigt `tr("status.nexus_cache_cleared")`.
- [ ] 5. `status.nexus_cache_cleared` (+ ggf. Tooltip-Key) existiert in allen 7
      Locales ohne fehlende Einträge.
- [ ] 6. Kein Crash, wenn keine Instanz/kein Cache vorhanden ist.

### Bereits erfüllt (Regressions-Check, keine neue Arbeit)
- [ ] 7. **Tracking:** Checkbox aktivierbar, Default an; Update-Check nur bei
      `Nexus/tracking_enabled` + API-Key + `entry.nexus_id > 0`.
- [ ] 8. **Category Mapping:** Kontextmenü "Kategorie neu zuordnen" und
      "Kategorien automatisch zuweisen" funktionieren und MERGEN (überschreiben nicht).
- [ ] 9. **NXM-Handler:** Button registriert Anvil via `xdg-mime`; `nxm://`-Mod-
      Links lösen 1-Click-Install aus, Collection-Links werden sauber gemeldet.
- [ ] 10. **Hide-API-Counter:** Checkbox blendet das API-Label in der StatusBar aus/ein.
- [ ] 11. `./restart.sh` startet ohne Fehler (kein NameError/ImportError).

### Endorsement (blockiert — nur bei GO)
- [ ] 12. *(offen)* Endorsement-Verhalten gemäß Alt-Spec, falls Marc Reaktivierung
      anordnet. Sonst: #20 wird ohne Endorsement geschlossen.

**Offene Produktfrage an Marc:**
1. Soll Endorsement für #20 reaktiviert werden (Issue nennt "auto-endorse after
   X hours of use"), oder bleibt es bewusst entfernt und #20 wird ohne
   Endorsement geschlossen?

---

## 8. Aufwand / Risiko

| Teil | Aufwand | Risiko | Bemerkung |
|------|---------|--------|-----------|
| Cache (Nexus-Button) | Gering (~30-50 Zeilen + 7 Locale-Edits) | Niedrig | Reine lokale Datei-Löschung, klar abgegrenzt; Pfad aus Instanz-Config |
| Tracking | Keiner | — | Erledigt |
| Category Mapping | Keiner | — | Erledigt |
| NXM-Handler | Keiner | — | Erledigt |
| Endorsement | Mittel (~250 Zeilen, 7 Locale) | **Produkt-Risiko** | Bewusst entfernt — nur nach GO; Rate-Limits/403-Handling beachten |

**Gesamtrisiko für #20:** niedrig. Einziger echter Umsetzungsschritt ist der
Nexus-Cache-Button; alles andere ist vorhanden oder eine bewusste
Produktentscheidung (Endorsement).
