# Feature-Spec: Notifications-Button in der Toolbar (#14)
**Status:** Geplant
**Datum:** 2026-06-28 (verifiziert gegen Code)

## 1. Problem / Ziel
In der Toolbar (rechte Status-Icon-Gruppe) existiert ein Glocken-/Benachrichtigungs-Button
mit dem Icon `problems.svg`. Er ist aktuell deaktiviert (`setEnabled(False)`) und hat keine
Funktion.

Ziel laut Issue #14 (Originaltext bestätigt via `gh issue view 14`):
- Button zeigt die Anzahl ungelesener Benachrichtigungen (Badge/Zähler).
- Klick öffnet ein Benachrichtigungs-Panel bzw. -Popup.
- Benachrichtigungen für: Mod-Updates, Deploy-Status, Fehler, Nexus-Ereignisse.

Issue-Labels: `disabled-feature`, `enhancement`. Status im Issue: „Button exists in the
toolbar but is disabled (no functionality implemented)" — deckt sich mit dem Code-Befund.

## 2. Phasen-Rückgrat (Bau-Reihenfolge nach steigendem Risiko)
| # | Phase | Inhalt | Risiko | testbar nach Phase? |
|---|---|---|---|---|
| 1 | Backend-Objekt | `NotificationCenter(QObject)`: Liste, `add/mark_all_read/clear/unread_count`, Signal `changed`. Reines Datenmodell, keine UI. | Niedrig | Ja — Unit/REPL: `add()` erhöht `unread_count()`, `changed` feuert |
| 2 | Instanziierung + Quelle | `self._notification_center` in MainWindow anlegen (analog `_update_checker`), EINE reale Quelle anbinden: `_on_update_available` → `add("info", …)`. Noch ohne Button-Anbindung. | Niedrig | Ja — beim Update-Event wächst `unread_count()` (Log/Print prüfbar) |
| 3 | Button aktivieren + i18n | `setEnabled(False)` raus, Tooltip via `tr("toolbar.notifications")`, Button-Referenz `bar.notifications_btn` exportieren. Locale-Keys ergänzen. | Niedrig | Ja — Button nicht mehr ausgegraut, Tooltip korrekt, `restart.sh` ohne Fehler |
| 4 | Panel-Popup | `NotificationPanel` (QListWidget + Buttons „Alle gelesen"/„Leeren"). Klick öffnet Popup unter dem Button (Pattern aus `toolbar.py:142`), Öffnen ruft `mark_all_read()`. KEIN `setStyleSheet`. | Mittel | Ja — Klick zeigt Liste, „Leeren" entleert |
| 5 | Badge-Darstellung | `changed` → Slot in MainWindow aktualisiert Badge/Tooltip-Zähler auf `bar.notifications_btn`; bei 0 ohne Badge. Position bei Icon-Größenwechsel (Toolbar-Settings) prüfen. | Mittel | Ja — Zähler stimmt, verschwindet bei 0, übersteht Icon-Resize |
| 6 | Weitere Quellen (iterativ) | Deploy-Ende/-Fehler, Nexus-Ereignisse als zusätzliche `add(...)`-Aufrufe. | Niedrig | Ja — je Quelle ein Eintrag |

Begründung Reihenfolge: Datenmodell (testbar ohne UI) → eine echte Quelle (beweist Datenfluss)
→ Button/i18n (kleinster sichtbarer Schritt) → Panel → Badge (heikelste Stelle: Overlay-Geometrie)
→ weitere Quellen additiv.

## 3. Ist-Zustand im Code (nur VERIFIZIERTE Anker)
| Stelle | Datei:Zeile | Befund (verifiziert) |
|---|---|---|
| Button-Erstellung | `anvil/widgets/toolbar.py:221` | `notifications_btn = _add_btn("problems.svg", "Benachrichtigungen")` |
| Deaktivierung | `anvil/widgets/toolbar.py:222` | `notifications_btn.setEnabled(False)` |
| Tooltip-Text | `anvil/widgets/toolbar.py:221` | hardcoded `"Benachrichtigungen"` (Argument an `_add_btn`, NICHT über `tr()`) |
| `_add_btn`-Helper | `anvil/widgets/toolbar.py:33-39` | setzt Icon + `setToolTip(tooltip)` + `setText(tooltip)`, hängt Button an `bar` |
| Export-Pattern (Vorbild) | `anvil/widgets/toolbar.py:146` / `:166` | `bar.proton_btn = proton_btn` bzw. `bar.deploy_btn = deploy_btn` — so wird Button-Referenz nach außen gereicht |
| Popup-Pattern (Vorbild) | `anvil/widgets/toolbar.py:142` | `menu.exec(proton_btn.mapToGlobal(proton_btn.rect().bottomLeft()))` — Popup unter dem Button |
| Icon-Datei | `anvil/styles/icons/problems.svg` + `anvil/styles/Paper/Dark/Toolbar/problems.svg` | existiert |
| Toast-Widget | `anvil/widgets/toast.py` (`class Toast(QLabel)`, Z.7) | kurze Auto-Verschwind-Meldung, `clicked`-Signal vorhanden. ACHTUNG: nutzt selbst `setStyleSheet` (Z.20-27) — als bestehendes Widget ok, aber kein Vorbild für neue QSS-freie Widgets |
| Status-Bar Notif-Label | `anvil/widgets/status_bar.py:16-17` | `self._notifications_label = QLabel(tr("status.notifications"))` + `addPermanentWidget(...)` — reiner Platzhalter |
| Update-Checker (Architektur-Vorbild) | `anvil/mainwindow.py:403-407` | `self._update_checker = UpdateChecker(self)` + Signale `update_available`/`update_applied`/`update_progress` verbunden |
| Update-Quelle | `anvil/mainwindow.py:7138` | `def _on_update_available(self, count: int, changelog: str):` — liefert `count` + `changelog`, ideale erste Notification-Quelle |
| Update-Button-Handler | `anvil/widgets/toolbar.py:223-228` | `update_btn` ruft `win._update_checker.check()` — bestätigt: Toolbar greift via `bar.window()` auf MainWindow-Attribute zu |

Es gibt **keine** Datenhaltung für Benachrichtigungen, keinen Klick-Handler, kein Badge.
**Verifiziert kein Teil-Bau vorhanden:** `grep -rn "NotificationCenter|notification_center|NotificationPanel"`
über `anvil/` liefert NULL Treffer; `anvil/core/notification_center.py` und
`anvil/widgets/notification_panel.py` existieren nicht.

## 4. Locale-Format — KORREKTUR einer Annahme
**Die Locale-Dateien sind NESTED JSON-Objekte**, kein Flat-Key-Format. `tr()` zerlegt den
Key an Punkten und steigt in die Objekte ab (`anvil/core/translator.py:79-111`,
`_get_nested`). Fallback-Kette: aktuelle Sprache → Englisch → Key selbst.

Konsequenzen für die neuen Keys:
- `toolbar.notifications` wird **in das bestehende `toolbar`-Objekt** eingefügt (existiert in
  allen 7 Locales, z.B. `anvil/locales/de.json:134`).
- `notifications.*` (Panel-Keys) bilden ein **neues Top-Level-Objekt** `"notifications": { … }`
  — verifiziert: aktuell existiert KEIN Top-Level-`notifications` in irgendeiner Locale
  (kein Konflikt). Hinweis: Es gibt bereits `menu.notifications` und `status.notifications`,
  beide in anderen Objekten — keine Kollision.
- `status.notifications` ist in **allen 7 Locales** bereits vorhanden
  (de „Benachrichtigungen", en „Notifications", es „Notificaciones", fr „Notifications",
  it „Notifiche", pt „Notificações", ru „Уведомления"). Diese Werte können als Tooltip-Text
  wiederverwendet werden statt einen neuen `toolbar.notifications`-Key anzulegen — Entscheidung
  beim Umsetzen (siehe i18n).

## 5. Lösung / Ansatz
Kleines, in sich geschlossenes Notification-System ohne Persistenz-Zwang:

1. **NotificationCenter (Backend, QObject):** neue Klasse `anvil/core/notification_center.py`.
   - Hält eine Liste von Einträgen `{id, level, title, message, timestamp, read}`.
   - Methoden: `add(level, title, message)`, `mark_all_read()`, `clear()`, `unread_count()`.
   - Signal `changed` bei jeder Mutation.
   - Level als String-Konstanten: `info`, `warning`, `error` (später optional → Icon-Farbe).
2. **MainWindow** instanziiert genau eine Instanz (`self._notification_center`) analog zu
   `_update_checker` (`mainwindow.py:403`). Erste reale Quelle:
   - In `_on_update_available` (`mainwindow.py:7138`) zusätzlich
     `self._notification_center.add("info", <Titel>, <Text aus count/changelog>)`.
   - Weitere Quellen (Deploy-Ende/-Fehler, Nexus) iterativ in Phase 6.
3. **Toolbar-Button aktivieren:**
   - `setEnabled(False)` (toolbar.py:222) entfernen.
   - Tooltip via `tr(...)` statt hardcoded.
   - Klick öffnet `NotificationPanel` (Popup unter dem Button, Pattern `toolbar.py:142`:
     `mapToGlobal(btn.rect().bottomLeft())`).
   - Button-Referenz `bar.notifications_btn = notifications_btn` exportieren (Pattern wie
     `bar.deploy_btn`, toolbar.py:166) — damit MainWindow das `changed`-Signal anbinden kann.
4. **NotificationPanel (Frontend):** `QListWidget` mit Titel/Text/Zeit, Buttons „Alle als
   gelesen" und „Leeren". Beim Öffnen → `mark_all_read()`. **Kein `setStyleSheet`** (QSS-Theme
   erbt automatisch).
5. **Badge:** `notification_center.changed` → Slot in MainWindow aktualisiert Zähler auf
   `bar.notifications_btn` (Overlay-Label oder Tooltip-Zähler); bei 0 kein Badge.

## 6. Betroffene Dateien
| Datei | Änderung |
|---|---|
| `anvil/core/notification_center.py` | NEU: `NotificationCenter(QObject)` mit Signal `changed` |
| `anvil/widgets/notification_panel.py` | NEU: Popup-Widget zur Anzeige der Liste (kein `setStyleSheet`) |
| `anvil/widgets/toolbar.py` | Z.221-222: Button aktivieren, Tooltip via `tr()`, `bar.notifications_btn` exportieren, Klick-Handler |
| `anvil/mainwindow.py` | `self._notification_center` anlegen (bei ~Z.403), Signal `changed` → Badge-Slot, in `_on_update_available` (Z.7138) `add(...)` |
| `anvil/locales/*.json` (7×) | neue Keys (siehe i18n) — NESTED einfügen |

## 7. Umsetzungsschritte
1. `NotificationCenter` mit Liste, `add/mark_all_read/clear/unread_count`, Signal `changed`.
2. In `mainwindow.py`: Center neben `_update_checker` instanziieren; in `_on_update_available`
   einen Eintrag `add("info", …)` ergänzen. Datenfluss isoliert testbar.
3. In `toolbar.py`: `setEnabled(False)` (Z.222) raus, Tooltip via `tr()`, Button-Referenz
   `bar.notifications_btn` exportieren, Klick-Handler.
4. `NotificationPanel` (QListWidget + Buttons) bauen; Klick öffnet Panel via
   `mapToGlobal(btn.rect().bottomLeft())`, ruft `mark_all_read()`. Kein `setStyleSheet`.
5. Badge-Slot in MainWindow: `changed` → Zähler auf `bar.notifications_btn` aktualisieren,
   bei 0 ausblenden. Position bei Icon-Größenwechsel testen.
6. i18n-Keys in allen 7 Locales NESTED ergänzen.
7. Weitere Quellen (Deploy/Nexus) iterativ.
8. `./restart.sh`, Log prüfen (NameError/ImportError/AttributeError), Klick + Badge testen.

## 8. i18n (tr-Keys, 7 Locales: de, en, es, fr, it, pt, ru)
**Format-Hinweis:** NESTED einfügen, nicht als flache Keys (siehe Abschnitt 4).

Tooltip-Key (zwei Optionen — eine wählen):
- **Option A (empfohlen):** bestehenden `status.notifications` für den Tooltip wiederverwenden
  (existiert bereits in allen 7 Locales) → KEIN neuer Tooltip-Key nötig.
- **Option B:** neuen Key `toolbar.notifications` in das `toolbar`-Objekt aller 7 Locales
  (DE: „Benachrichtigungen").

Neue Panel-Keys (neues Top-Level-Objekt `notifications`), in allen 7 Locales:
- `notifications.title` — Panel-Titel (DE: „Benachrichtigungen")
- `notifications.empty` — Leer-Hinweis (DE: „Keine neuen Benachrichtigungen")
- `notifications.mark_all_read` — Button (DE: „Alle als gelesen markieren")
- `notifications.clear` — Button (DE: „Leeren")

Empfohlene Übersetzungen (en/es/fr/it/pt/ru) beim Umsetzen analog zu vorhandenen
`status.*`/`toolbar.*`-Strings vergeben.

## 9. Akzeptanzkriterien
- [ ] Button ist aktiv (nicht ausgegraut), Tooltip kommt aus `tr()` (kein hardcoded Text).
- [ ] Klick öffnet das Benachrichtigungs-Panel unter dem Button.
- [ ] Mindestens eine reale Quelle (Update verfügbar, `_on_update_available`) erzeugt einen Eintrag.
- [ ] Badge zeigt korrekte Anzahl ungelesener Meldungen; verschwindet bei 0.
- [ ] Öffnen des Panels markiert alles als gelesen (Badge → 0).
- [ ] „Leeren" entfernt alle Einträge.
- [ ] Badge bleibt korrekt positioniert nach Icon-Größenwechsel (Toolbar-Settings: klein/mittel/groß).
- [ ] Kein `setStyleSheet()` in den NEUEN Widgets (`notification_panel.py`); QSS-Theme erbt.
- [ ] Alle 7 Locale-Dateien enthalten die neuen Keys (NESTED, im richtigen Objekt).
- [ ] `./restart.sh` startet fehlerfrei (kein NameError/ImportError/AttributeError im Log).

## 10. Aufwand / Risiko
**Aufwand:** Mittel — neues Backend-Objekt + Popup-Widget + Verdrahtung; das meiste ist
Standard-Qt. Phasen 1-3 sind je klein und einzeln testbar.
**Risiko:** Niedrig — additiv, greift in keinen bestehenden Flow ein. Einzige heiklere Stelle:
Badge-Overlay-Positionierung auf dem `QToolButton` bei Icon-Größenwechsel (Phase 5). Locale-
Format (NESTED) muss beachtet werden — falsche Flat-Keys würden stumm zum Key-Fallback führen.
