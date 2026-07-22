# Feature-Spec: Nexus Server-Auswahl (#21)
**Status:** Geplant (verifiziert gegen echten Code, 2026-06-28)
**Datum:** 2026-06-28

---

## 1. Problem / Ziel

**Issue #21 (verifiziert via `gh issue view 21`):**
> The Nexus server selection in settings is disabled.
> Expected: Dropdown/list of available Nexus servers (CDN regions); Automatic server
> selection based on latency; Manual override possible; Affects download speed.
> Status: *UI element present but disabled — requires Nexus connection (#19).*
> Labels: `disabled-feature`, `enhancement`.

Die Server-Auswahl im Nexus-Settings-Tab ist aktuell **rein dekorativ und deaktiviert**.
Sie zeigt hardcodierte Dummy-Daten (Städte-Liste "Amsterdam, Prague, …" und
"Nexus CDN (58.45 MB/s)"); beide Listen sind per `_disabled()` ausgegraut
(`settings_dialog.py:524`, `:532`).

**Hintergrund Nexus-API / Account-Typen:**
Der Endpunkt `GET /v1/games/{game}/mods/{id}/files/{fid}/download_link.json` liefert ein
JSON-**Array** von CDN-Servern. Jeder Eintrag hat (gemäß Nexus-API) `name`, `short_name`, `URI`.

- **Premium-User:** bekommen (ohne `key`/`expires`) i. d. R. **genau einen** Eintrag
  (Premium-CDN). Eine Auswahl ist hier weder nötig noch sinnvoll.
- **Free-User:** bekommen mit gültigem `key`/`expires` aus dem nxm-Link **mehrere** Einträge
  (regionale CDN-Server). Hier soll der User die bevorzugte Region wählen können —
  beeinflusst die Download-Geschwindigkeit.

> **Format-Hinweis (zu verifizieren bei Implementierung):** Die Felder `name`/`short_name`/`URI`
> sind aus der Nexus-API-Doku übernommen, NICHT aus einer echten Antwort im Repo belegt.
> Der heutige Code liest ausschließlich `data[0].get("URI", "")` (`mainwindow.py:5593`) —
> d. h. nur `URI` ist im Code real bestätigt. `name`/`short_name` an einer echten
> Free-Account-Antwort gegenprüfen, bevor darauf gematcht wird.

**Ziel:**
1. Free-User können einen bevorzugten Server / eine Region wählen (Default in Settings).
2. Beim Download wird aus der API-Antwort der bevorzugte Server gewählt (statt blind `data[0]`).
3. Premium-User merken nichts davon (nur ein Server → direkt verwenden).
4. Sauberer Fallback, wenn der bevorzugte Server in der Antwort fehlt.

**Bewusst NICHT in dieser Iteration:** "Automatic server selection based on latency"
(eigenes Latenz-Probing = großer Aufwand/Risiko; Nexus liefert keine Geo-/Speed-Daten
je Server). Empfehlung: als separates Folge-Issue. Der Kern-Use-Case des Issues
("Manual override possible", "Affects download speed") wird über die manuelle
Default-Auswahl + Fallback abgedeckt.

---

## 2. Phasen-Rückgrat (Bau-Reihenfolge nach steigendem Risiko)

| # | Phase | Inhalt | Risiko | Testbar nach Phase? |
|---|-------|--------|--------|---------------------|
| 1 | **Persistenz-Helper** | QSettings-Key `Nexus/preferred_server` (leer=Auto) lesen/schreiben. Save in `accept()` analog Z. 1084–1086. Kein UI-Verhalten ändert sich noch. | sehr gering | Ja — Key landet via `_settings()` in `~/.config/AnvilOrganizer/AnvilOrganizer.conf`, prüfbar mit `cat`. |
| 2 | **Settings-UI entsperren** | `_disabled()` von `known_list`/`pref_list` entfernen; Dummy-Städte (Z. 522) + Dummy-Eintrag (Z. 531) raus; `known_list` aus Cache-Key `Nexus/known_servers` befüllen; `pref_list` single-select, gespeicherte Präferenz vorauswählen. | gering | Ja — Settings-Tab öffnet ohne Fehler, GroupBox nicht mehr ausgegraut, Auswahl wird gespeichert/geladen. |
| 3 | **Known-Server-Cache schreiben** | Bei `download_link:`-Antwort in `_on_nexus_response` die gelieferten Server-Namen nach `Nexus/known_servers` (JSON-Liste) schreiben — füllt die Liste aus Phase 2 mit echten Daten. | gering | Ja — nach einem nxm-Download enthält der Cache-Key die realen Server. |
| 4 | **Download-Auswahl (Kern-Fix)** | `mainwindow.py:5593` `data[0]` → Helper `_select_download_server(data)`: len≤1→data[0]; sonst Präferenz aus `Nexus/preferred_server` matchen; kein Treffer→data[0]. | mittel (greift in Download-Pipeline) | Ja — Free-Download nutzt gewählte Region; Premium/kein-Match → data[0] (= heute). |
| 5 | **i18n** | Neue tr-Keys in allen 7 Locales (nested unter `settings`/`dialog`). | sehr gering | Ja — App startet ohne fehlende-Key-Warnung; alle Sprachen identischer Key-Satz. |
| 6 | **(Optional) Auswahl-Dialog + Premium-Hinweis** | Bei "mehrere Server + keine Präferenz" pro Download ein Mini-Dialog mit "merken"-Checkbox; im Settings-Tab optionaler Hinweis bei `is_premium`. | gering | Ja, separat. |

> Bau-Logik: Phase 1–3 sind risikoarm und unabhängig von der Download-Pipeline. Erst in
> Phase 4 wird die funktionierende Download-Zeile angefasst — und zwar mit Fallback auf das
> heutige `data[0]`-Verhalten. So bleibt nach jeder Phase ein lauffähiger Stand.

---

## 3. Ist-Zustand im Code (verifizierte Anker)

Alle folgenden Anker wurden per Read/grep am echten Code geprüft und stimmen.

### 3.1 Download-Link-Pfad (so läuft ein nxm-Download heute)

1. **`anvil/core/nxm_handler.py:23` `class NxmLink`** — Felder `game, mod_id, file_id,
   key="", expires="", user_id="", raw_url=""`. **`:35` `parse_nxm_url()`** zerlegt
   `nxm://game/mods/{id}/files/{fid}?key=…&expires=…` in ein `NxmLink`.
2. **`anvil/mainwindow.py:5540` `_handle_nxm_link()`** — prüft `has_api_key()`, ruft
   `get_mod_info(game, mod_id)` (Z. 5554) und `get_download_links(game, mod_id, file_id,
   key=…, expires=…)` (Z. 5555–5561). Legt `self._pending_nxm_links[(mod_id, file_id)]`
   an (Z. 5566).
3. **`anvil/core/nexus_api.py:180` `get_download_links()`** — baut Pfad
   `/games/{game}/mods/{mod_id}/files/{file_id}/download_link.json` (Z. 195), hängt
   `key`/`expires` als Query an (Z. 197–202), Tag `download_link:{game}:{mod_id}:{file_id}`
   (Z. 203). Reicht die rohe Server-Liste (`data`, Array) ans Antwort-Signal weiter.
4. **`anvil/mainwindow.py:5572` `_on_nexus_response(tag, data)`** — bei Tag
   `download_link:` (Z. 5574, prüft `isinstance(data, list) and data`):
   - **`mainwindow.py:5593`: `url = data[0].get("URI", "")`** ← **Kern des Problems.**
     Es wird **immer der erste** Server genommen; die übrigen werden ignoriert.
   - Bei leerem `url`: `status.nexus_no_link` (Z. 5595), dann `return`.
   - Sonst Dateiname aus URL (Z. 5598–5601) und
     `dm.enqueue(url=…, file_name=…, …)` (Z. 5603–5612).

### 3.2 Wo die Server-Auswahl deaktiviert ist

**`anvil/widgets/settings_dialog.py:515–535`** — GroupBox `settings.nexus_server`:
- `known_list` (links): hardcodierte Städte-Liste, **Zeile 522**:
  `for city in ("Amsterdam", "Prague", "Chicago", "Los Angeles", "Miami", "Dallas"):`
  → **Zeile 524** `_disabled(known_list)`.
- `pref_list` (rechts): ein hardcodierter Dummy-Eintrag, **Zeile 531**:
  `pref_list.addItem(QListWidgetItem("Nexus CDN (58.45 MB/s)"))`
  → **Zeile 532** `_disabled(pref_list)`.
- `_disabled()` (**Zeile 73–76**): `setEnabled(False)` + `setToolTip(tr("settings.coming_soon"))`.

**KEINE bestehende Server-Auswahl-Logik im Code** (grep nach `preferred_server`,
`select_download_server`, `preferred_region`, `known_servers` in `anvil/` → nur die
Dummy-UI und die Labels; das Feature ist genuin ungebaut, nur die deaktivierte UI existiert).

**Keine Persistenz** für eine Server-Präferenz. Der Nexus-Save-Block in `accept()`
(**Zeile 1084–1086**) enthält nur `Nexus/tracking_enabled`, `Nexus/hide_api_counter`,
`Nexus/category_mapping_enabled`.

### 3.3 QSettings-Zugriff (wichtig — KEIN bare QSettings())

`settings_dialog.py:999–1002` `_settings()` ist ein **statischer Helper** mit explizitem
ini-Pfad: `QSettings(str(Path.home()/".config"/"AnvilOrganizer"/"AnvilOrganizer.conf"),
QSettings.Format.IniFormat)`.
→ **Für die neue Persistenz dieselbe Quelle nutzen.** Im Settings-Dialog via
`self._settings()`. In `mainwindow.py` (Phase 3/4) muss derselbe ini-Pfad/dieselbe
QSettings-Konfiguration verwendet werden, sonst sieht der Download-Pfad den im Dialog
gespeicherten Wert nicht. (Vor Implementierung prüfen, wie mainwindow sonst QSettings
liest, und dieselbe Form verwenden.)

### 3.4 Premium-Status ist bereits bekannt

`settings_dialog.py:1276` `_nx_on_validated(user_info)` liest `is_premium =
user_info.get("is_premium", False)` (**Zeile 1280**) und `is_supporter` (Z. 1281),
setzt `account_type` = "Premium"/"Supporter"/"Standard". Account-Typ ist nach
`validate_key()` verfügbar — Grundlage für einen optionalen Premium-Hinweis.

### 3.5 Relevante tr-Keys existieren bereits

Locale-JSON ist **nested** (Top-Level-Objekte `settings`, `label`, `dialog`, …), NICHT flach.
In allen 7 Locales vorhanden:
- `settings.nexus_server` (de: "Server") — `de.json:747` (im `settings`-Objekt ab Z. 664)
- `label.known_servers` (de: "Bekannte Server (aktualisiert bei Download)") — `de.json:379`
  (im `label`-Objekt ab Z. 316)
- `label.preferred_servers` (de: "Bevorzugte Server (Drag & Drop)") — `de.json:380`
- `settings.coming_soon` (de: "Noch nicht verfügbar") — `de.json:807`

> **i18n-Falle:** `tr("settings.foo")` löst über die **verschachtelte** Struktur auf
> (`settings` → `foo`). Neue Keys müssen in das jeweilige Top-Level-Objekt
> (`settings` bzw. `dialog`) eingefügt werden — NICHT als flache `"settings.foo"`-Keys.

---

## 4. Lösung / Ansatz

**Leitprinzip:** Minimal-invasiv, keine neuen externen Abhängigkeiten, kein Umbau der
funktionierenden Download-Pipeline. Manuelle Default-Auswahl + Fallback statt Latenz-Probing.

### 4.1 Settings: bevorzugte Server-Region als Default (Phase 1+2)

- Server-GroupBox aktivieren (`_disabled()` von `known_list`/`pref_list` entfernen).
- Funktional genügt **eine bevorzugte Region**: `pref_list` single-select ODER `QComboBox`
  (siehe offene Frage 1). Default leer = "Automatisch / erster verfügbarer".
- `known_list` zur Laufzeit aus Cache `Nexus/known_servers` befüllen (passt zum Label
  "aktualisiert bei Download"). Hardcodierte Städte (Z. 522) entfällt.
- Persistenz QSettings-Key **`Nexus/preferred_server`** (speichert `short_name` bzw.
  identifizierenden String). Speichern in `accept()` analog Z. 1084–1086, via `self._settings()`.
- Beim Öffnen die gespeicherte Präferenz vorauswählen.

### 4.2 Server-Auswahl beim Download — Kern-Fix (Phase 4)

`mainwindow.py:5593` `url = data[0].get("URI", "")` durch Helper
`_select_download_server(data) -> str` ersetzen:

```
1. len(data) <= 1            → data[0]["URI"]   (Premium oder nur 1 Server)
2. Präferenz aus Nexus/preferred_server lesen (gleiche QSettings-Quelle wie Dialog)
3. In data Eintrag mit "short_name" (bzw. "name") == Präferenz suchen → dessen "URI"
4. kein Treffer / keine Präferenz → data[0]["URI"]   (= heutiges Verhalten, Fallback)
```

Die bestehende Leer-URL-Behandlung (`status.nexus_no_link`, Z. 5595) bleibt unverändert.

### 4.3 Known-Server-Liste live cachen (Phase 3)

In `_on_nexus_response` bei `download_link:`-Antwort die Server-Identifier
(`short_name` bzw. `name`) nach `Nexus/known_servers` (JSON-Liste) schreiben — damit der
Settings-Dialog auch ohne aktiven Download eine echte Auswahl-Grundlage hat.

### 4.4 Premium-Handling

Premium-Antworten enthalten nur einen Server → Schritt 1 (len≤1) greift automatisch.
**Keine Sonderbehandlung im Download-Pfad nötig.** Optional im Settings-Tab ein Hinweis
bei `is_premium` (aus `_nx_on_validated`), dass die Auswahl für Premium ohne Wirkung ist.

### 4.5 Fallback-Garantien

- Antwort leer / kein `URI` → bestehende Meldung `status.nexus_no_link` (`mainwindow.py:5595`).
- Präferenz nicht in Liste → erster Eintrag (kein Abbruch).
- QSettings-Key fehlt → erster Eintrag.

---

## 5. Betroffene Dateien

| Datei | Änderung | Art |
|---|---|---|
| `anvil/mainwindow.py` | `_on_nexus_response` (~Z. 5593): `data[0]` → `_select_download_server(data)`; neue Helper-Methode; bekannte Server nach `Nexus/known_servers` cachen | Kern-Logik |
| `anvil/widgets/settings_dialog.py` | Server-GroupBox (Z. 515–535) aktivieren: `_disabled()` (Z. 524/532) entfernen, Dummy-Städte (Z. 522) + Dummy-Eintrag (Z. 531) durch Cache-Befüllung ersetzen, `pref_list` single-select; `accept()` (~Z. 1086) `Nexus/preferred_server` via `self._settings()` speichern; optional Premium-Hinweis | UI + Persistenz |
| `anvil/core/nexus_api.py` | Keine zwingende Änderung — Server-Liste wird bereits durchgereicht. Optional: Doc-Kommentar zu Server-Feldern | (optional) |
| `anvil/core/download_manager.py` | Keine Änderung (`enqueue` bekommt fertige URL) | — |
| `anvil/locales/{de,en,es,fr,it,pt,ru}.json` | Neue tr-Keys (nested unter `settings`/`dialog`) | i18n |

---

## 6. Umsetzungsschritte

1. **(Phase 1) Persistenz** in `accept()` ergänzen:
   `settings.setValue("Nexus/preferred_server", <gewählter Identifier>)` (über `self._settings()`).
2. **(Phase 2) Settings-UI aktivieren** (`settings_dialog.py`):
   - `_disabled()` von `known_list`/`pref_list` entfernen.
   - Hardcodierte Städte (Z. 522) + Dummy-Eintrag (Z. 531) durch Befüllen aus
     `Nexus/known_servers` ersetzen.
   - `pref_list` single-select, gespeicherte Präferenz vorauswählen.
3. **(Phase 3) Known-Server-Cache** (`mainwindow.py`): bei `download_link:`-Antwort die
   Server-Identifier nach `Nexus/known_servers` (JSON) schreiben — gleiche QSettings-Quelle.
4. **(Phase 4) Download-Auswahl** (`mainwindow.py`): Helper
   `_select_download_server(data) -> str(url)` nach §4.2; Zeile 5593 darauf umstellen.
5. **(Phase 5) i18n**: neue Keys in alle 7 Locales, nested (siehe §7).
6. **(Phase 6, optional, nach GO)** Auswahl-Dialog "mehrere Server + keine Präferenz" und
   Premium-Hinweis via `is_premium`.
7. **Test** `./restart.sh`: Settings-Tab öffnet ohne Fehler; gewählte Region wird beim
   Free-Download genutzt; Premium-Download unverändert; Fallback bei fehlender Präferenz.

---

## 7. i18n (tr-Keys, 7 Locales)

Sprachen: **de, en, es, fr, it, pt, ru** (`anvil/locales/`). Struktur **nested** — neue Keys
in das jeweilige Top-Level-Objekt (`settings` bzw. `dialog`) einfügen, nicht flach.

**Bereits vorhanden (Werte ggf. anpassen, KEINE neuen Keys nötig):**
`settings.nexus_server`, `label.known_servers`, `label.preferred_servers`, `settings.coming_soon`.

**Neu (nur falls umgesetzt — Phase 2/6):**

| Key (nested) | DE (Vorschlag) | EN (Vorschlag) |
|---|---|---|
| `settings.nexus_server_pref_hint` | "Bevorzugte Region für Free-Downloads" | "Preferred region for free downloads" |
| `settings.nexus_server_auto` | "Automatisch (erster verfügbarer)" | "Automatic (first available)" |
| `settings.nexus_server_premium_hint` | "Premium-Accounts erhalten einen direkten Server — Auswahl ohne Wirkung." | "Premium accounts get a direct server — selection has no effect." |
| `dialog.nexus_select_server_title` | "Download-Server wählen" | "Choose download server" |
| `dialog.nexus_select_server_body` | "Wähle einen Server für diesen Download:" | "Choose a server for this download:" |
| `dialog.nexus_remember_choice` | "Auswahl merken" | "Remember this choice" |

Keys für es/fr/it/pt/ru analog. **Alle 7 Dateien müssen identische Key-Sätze haben.**

---

## 8. Akzeptanzkriterien

- [ ] Free-User mit nxm-Download (mehrere Server): der in den Settings gewählte Server wird
      verwendet (verifizierbar am `URI`/Host im Download).
- [ ] Premium-User (1 Server in Antwort): unverändertes Verhalten, kein Dialog, keine Regression.
- [ ] Keine Präferenz → erster Server (`data[0]`) als Fallback (= heutiges Verhalten).
- [ ] Präferenz gesetzt, aber nicht in der Antwort → Fallback auf ersten Server, kein Abbruch.
- [ ] Server-GroupBox im Settings-Tab **nicht** mehr ausgegraut; Auswahl persistent
      (übersteht App-Neustart, Key `Nexus/preferred_server` in `AnvilOrganizer.conf`).
- [ ] Download-Pfad liest dieselbe QSettings-Quelle wie der Dialog (Präferenz wird wirksam).
- [ ] `known_list` zeigt die zuletzt von der API gelieferten Server (nicht mehr Dummy-Städte).
- [ ] Leere/fehlerhafte API-Antwort → bestehende Meldung `status.nexus_no_link`, kein Crash.
- [ ] tr-Keys in **allen 7** Locale-Dateien vorhanden, korrekt nested (de, en, es, fr, it, pt, ru).
- [ ] Kein `setStyleSheet()` in neuen Widgets; keine hardcoded Pfade.
- [ ] `python -m py_compile` sauber; `./restart.sh` startet ohne Traceback.

---

## 9. Aufwand / Risiko

**Aufwand:** Klein–Mittel.
- Phase 1–4 (Persistenz + Settings-UI + Known-Cache + Download-Auswahl): ~1–2 h.
- Optional (Auswahl-Dialog + Premium-Hinweis) + 7× i18n: +1–2 h.

**Risiko:** Gering.
- Download-Pipeline strukturell unverändert (nur URL-Quelle ändert sich, mit Fallback auf heute).
- **Hauptrisiko:** Annahme über Server-Felder. Im Code ist nur `URI` real belegt
  (`mainwindow.py:5593`). `short_name`/`name` an einer echten Free-Account-Antwort
  verifizieren, bevor darauf gematcht wird — sonst auf `name` oder Index zurückfallen.
- **Zweitrisiko:** QSettings-Quelle. Dialog nutzt `_settings()` mit explizitem ini-Pfad;
  der Download-Pfad in `mainwindow.py` MUSS dieselbe Quelle lesen, sonst bleibt die
  Präferenz wirkungslos.
- Latenz-basierte Auto-Auswahl bewusst ausgeklammert → kein Netzwerk-/Timing-Risiko.

---

## Offene Fragen an Marc

1. **UI-Form:** `pref_list` als klickbare Single-Select-Liste belassen oder durch `QComboBox`
   ersetzen (kompakter)? Brauchen wir eine **Reihenfolge** von Fallback-Servern (Drag&Drop)
   oder reicht **ein** bevorzugter Server (Empfehlung: einer reicht)?
2. **Auswahl-Dialog:** Bei "mehrere Server + keine Präferenz" pro Download ein Dialog,
   oder still `data[0]` und Auswahl nur über Settings?
3. **Latenz-Auto-Auswahl:** In dieser Iteration weglassen (Empfehlung: ja) oder als
   separates Folge-Issue?
4. **Abhängigkeit #19:** Issue verweist auf #19 (Nexus-Verbindung). API-Key-Validierung
   (`_nx_on_validated`) und nxm-Download (`_handle_nxm_link`) laufen offenbar bereits —
   ist #19 erledigt? Falls ja, kann der "requires Nexus connection"-Hinweis entfallen.
