# Feature-Spec: Workarounds Tab (#22)
**Status:** Geplant
**Datum:** 2026-06-28

---

## 1. Problem / Ziel

GitHub-Issue #22 (Label: `disabled-feature`, `enhancement`):

> The workarounds tab is completely hidden — no UI, no logic implemented.

Im Settings-Dialog existiert bereits ein **fertig aufgebauter, aber auskommentierter**
Workarounds-Tab. Sein aktueller Inhalt ist eine 1:1-Übernahme der Windows-Welt
(Steam-Username/Passwort, „BSAs zurückdatieren", „Fenstergeometrien zurücksetzen",
„Datei-Endungen überspringen") — alle Widgets sind via `_disabled()` deaktiviert und
tragen den Tooltip „Noch nicht verfügbar". Dieser Inhalt ergibt unter Linux/Proton
**keinen Sinn**.

**Ziel:** Den Windows-Ballast **rauswerfen** und den Tab mit **echten,
Linux-/Proton-relevanten Workarounds pro Instanz** füllen, die persistent in der
Instanz-Config gespeichert und beim Spielstart tatsächlich angewendet werden.

**Erstes Lieferziel (Phase 0): Windows-Ballast entfernen.**
Der komplette tote Block (Steam-Login, BSA-Backdate, Geometrie-Reset, Skip-Extensions,
Systemproxy, Custom-Browser) wird gelöscht — unabhängig davon, was danach reinkommt.
Das ist kein „nice to have", sondern Voraussetzung.

**Abgrenzung (bewusst NICHT in diesem Feature):**
- Kein Steam-Username/-Passwort (Sicherheits-Unsinn, war nur Windows-Login-Relikt).
- Kein „BSAs zurückdatieren" (Windows-Timestamp-Trick, unter Proton irrelevant).
- Kein „Archiv-Parsing", kein „Fenstergeometrien zurücksetzen" (App-intern, kein Workaround).
- Kein Custom-Browser / Systemproxy (gehört nicht in Workarounds).
- **BG3-Code wird NICHT angefasst** (CLAUDE.md-Verbot).

---

## 2. Bau-Reihenfolge (Priorität) — das Rückgrat

Einmal das Fundament bauen (Phase 0), dann die Workarounds **von oben nach unten**.
Nach jeder Phase ist ein testbarer Zwischenstand erreicht.

| # | Phase | Inhalt | Risiko | Testbar nach Phase? |
|---|-------|--------|--------|---------------------|
| **0** | Fundament | Windows-Ballast raus + Config-Layer `[Workarounds]` + sichtbarer (noch leerer) Tab mit Instanz-Kopf | gering, aber zentral | Tab sichtbar, leer, speichert/lädt nichts kaputt |
| **1** | Extra-Startargumente | `wa_extra_launch_args` | gering | Args landen im Steam-Start-Log |
| **2** | Proton-Version für Tools | `wa_force_proton` | gering (isolierter Hook) | ComboBox listet Versionen, Tool startet mit gewählter Version |
| **3** | Steam-AppID überschreiben | `wa_override_appid` | **mittel (3 Start-Pfade)** | Override-ID in allen 3 Pfaden im Log |
| **4** | Copy-Deploy statt Symlinks | `wa_force_copy_deploy` | gering | Flag persistiert + Deployer liest es |
| **5** | Shim-Deploy überspringen | `wa_skip_shim_deploy` | gering | Flag persistiert + Deploy überspringt Shim |
| **6** | INI-Schreibschutz | `wa_lock_inis` | gering | Flag persistiert + INIs read-only nach Deploy |

**Warum diese Reihenfolge:** Phase 1 ist trivial und ohne Risiko → schneller erster
Erfolg, validiert das Fundament. Phase 2 hat einen einzelnen, sauber lokalisierbaren
Hook. Phase 3 (AppID) trägt das höchste Risiko (greift in 3 Launch-Pfade), kommt
deshalb erst, wenn Fundament + UI bereits durch 1–2 erprobt sind. Phasen 4–6 sind
persistierte Flags mit kleinen, unabhängigen Konsumenten.

---

## 3. Ist-Zustand im Code

### 3.1 Der auskommentierte Tab

| Ort | Bedeutung |
|-----|-----------|
| `anvil/widgets/settings_dialog.py:688–742` | Kompletter Aufbau des `workarounds_tab` (QScrollArea + 3 GroupBoxen + Button-Reihe). |
| `anvil/widgets/settings_dialog.py:742` | `# self._tabs.addTab(workarounds_tab, tr("settings.tab_workarounds"))` — auskommentiert, daher unsichtbar. |
| `anvil/widgets/settings_dialog.py:72–76` | Helper `_disabled(w)` → `setEnabled(False)` + Tooltip `settings.coming_soon`. Alle aktuellen WA-Widgets nutzen ihn. |
| `anvil/widgets/settings_dialog.py:698–709` | Checkboxen `wa_force_load_game_files`, `wa_archive_parsing`, `wa_lock_gui` (alle disabled, ohne Logik). |
| `anvil/widgets/settings_dialog.py:711–716` | Steam-GroupBox: AppID (hardcoded `"1091500"`), Username, Passwort — alle disabled. |
| `anvil/widgets/settings_dialog.py:717–729` | Netzwerk-GroupBox: Offline-Modus, Systemproxy, Custom-Browser — alle disabled. |
| `anvil/widgets/settings_dialog.py:730–735` | Button-Reihe: Geometrie-Reset, BSA-Backdate, App-Blockliste, Skip-Extensions, Skip-Directories — alle disabled. |
| `anvil/widgets/settings_dialog.py:739` | Hinweislabel `label.workarounds_hint`. |

→ **Dieser komplette Block (688–742) wird in Phase 0 durch den neuen, Linux-tauglichen
Inhalt ersetzt.** Die alten tr-Keys (`wa_steam_username`, `wa_backdate_bsa`, …) werden
im Code nicht mehr referenziert; sie bleiben in den Locale-Dateien liegen (Aufräumen
optional, kein Muss — ungenutzte Keys schaden nicht).

### 3.2 Wie Tabs registriert & persistiert werden

- Sichtbare Tabs werden mit `self._tabs.addTab(widget, tr(...))` registriert
  (Beispiele: Pfade `:413`, Nexus `:540`, Plugins `:679`).
- **Persistenz QSettings** (global, app-weit): in `accept()` `:1050–1101` via
  `settings.setValue(...)`.
- **Persistenz Instanz** (pro Game): in `accept()` `:1103–1123` — lädt `idata`,
  setzt Felder, ruft `self._instance_manager.save_instance(cur, idata)`.
  → Hier docken die neuen, **instanz-spezifischen** Workarounds an.

### 3.3 Vorhandene Proton-/Steam-/Launch-Mechanik (verstreut)

| Ort | Was existiert heute |
|-----|---------------------|
| `anvil/plugins/base_game.py:67` | `GameSteamId: int \| list[int]` — Steam-AppID, **fix pro Plugin**, NICHT pro Instanz. |
| `anvil/plugins/base_game.py:97` | `GameLaunchArgs: list[str]` — Startargumente, **fix pro Plugin**. |
| `anvil/plugins/base_game.py:291` | `detectedStore()` → `"steam"` / sonst. |
| `anvil/plugins/base_game.py:295–326` | `protonPrefix()` — leitet `compatdata/<id>/pfx` her. |
| `anvil/plugins/base_game.py:328–410` | `findProtonRun()` — **Proton-Version wird automatisch aus `compatdata/<id>/config_info` gelesen** (das ist die in Steam eingestellte Proton-Version). Fallback: neueste Proton-Installation. Es gibt **keinen** Override-Mechanismus. |
| `anvil/widgets/game_panel.py:1636–1680` | `_launch_via_steam()` — startet via `steam -applaunch <GameSteamId>`, hängt `GameLaunchArgs` an (`:1652–1653`). |
| `anvil/widgets/game_panel.py:1682–1719` | `_build_proton_env()` — baut `STEAM_COMPAT_*`, `SteamAppId`, `UMU_ID` aus `GameSteamId`. |
| `anvil/widgets/game_panel.py:1721ff` | `_launch_via_proton()` — `proton run <exe>` für Tools (F4SE etc.). |
| `anvil/widgets/executables_dialog.py:96–101` | Checkbox „Overwrites Steam AppID" + Eingabefeld — **rein dekorativ**, kein Backend, keine Persistenz. |
| `anvil/widgets/game_panel.py:1696–1717` | `STEAM_COMPAT_DATA_PATH`, `STEAM_COMPAT_CLIENT_INSTALL_PATH`, `STEAM_COMPAT_INSTALL_PATH`, `SteamAppId`, `SteamGameId`, `WINEDLLOVERRIDES`, `UMU_ID` werden gesetzt — **Einfallstor für „zusätzliche Launch-Args" und „Override AppID"**. |

### 3.4 Instanz-Config (`.anvil.ini`)

- Format: QSettings-INI, Gruppen `[%General]` und `[Paths]` (real geprüft:
  `~/.anvil-organizer/instances/Skyrim Special Edition/.anvil.ini`).
- `anvil/core/instance_manager.py:406–421` `_read_ini()`: liest **nur** `[General]`
  und `[Paths]` aus. **Eine neue Gruppe `[Workarounds]` muss hier ergänzt werden**,
  sonst landet sie nicht im `idata`-Dict.
- `anvil/core/instance_manager.py:287–322` `save_instance()`: schreibt selektiv nur
  bekannte Keys (`game_path`, `local_inis`, …). **Muss um `[Workarounds]`-Keys
  erweitert werden.**
- Flat-Dict-Konvention: `[Paths]`-Keys bekommen Präfix `path_`. Analog Vorschlag:
  `[Workarounds]`-Keys bekommen Präfix `wa_` im `idata`-Dict.

---

## 4. Die Workarounds im Detail (in Bau-Reihenfolge)

Der Tab ist **instanz-spezifisch** (Kopf: „Workarounds für Instanz: <Name>").
UI bleibt in 3 GroupBoxen gegliedert; die Bau-/Test-Reihenfolge folgt §2.

### Phase 0 — Fundament (kein Workaround, sondern Voraussetzung)

- Block `688–742` löschen (Windows-Ballast), Tab neu, **aktivierte** Widgets, Kopf mit
  Instanz-Name, `addTab` einkommentieren.
- `instance_manager._read_ini()` + `save_instance()` um Gruppe `[Workarounds]`
  (Präfix `wa_`) erweitern — abwärtskompatibel (fehlende Gruppe → leeres Dict).
- Ergebnis: sichtbarer, leerer Tab, der speichert/lädt, ohne Altinstanzen zu brechen.

### Phase 1 — Zusätzliche Startargumente (`wa_extra_launch_args`)  — GroupBox A

- QLineEdit (Freitext, leerzeichengetrennt, `shlex`-geparst).
- **Wirkung:** Wird in `_launch_via_steam` `:1651–1653` **nach** `GameLaunchArgs`
  angehängt.
- **Anwendungsfall:** `--skip-launcher`, `-windowed`, spielspezifische Flags.
- *Warum zuerst:* trivial, kein Risiko, validiert sofort Fundament + Launch-Hook.

### Phase 2 — Proton-Version für Tools erzwingen (`wa_force_proton`)  — GroupBox A

- QComboBox: „Automatisch (Steam-Einstellung)" als Default + dynamisch ermittelte
  installierte Proton-/GE-Proton-Versionen (über die in `findProtonRun` bereits
  vorhandene Library-/`common`-Scan-Logik, `:399–410`).
- **Wirkung:** Wenn gesetzt, überschreibt `findProtonRun()` die aus `config_info`
  gelesene Version — **nur für Anvils `proton run`-Tool-Starts** (F4SE/REDmod);
  der `steam -applaunch`-Hauptstart nutzt weiter Steams Auswahl (korrekt, im
  Hinweis klarstellen).
- **Anwendungsfall:** Tool (Script Extender) braucht andere Proton-Version als das
  Spiel; GE-Proton für Tools.

### Phase 3 — Steam-AppID überschreiben (`wa_override_appid`)  — GroupBox A

- Checkbox + QLineEdit (numerisch). Default leer → Plugin-`GameSteamId` gilt.
- **Wirkung:** Beim Start wird statt `GameSteamId` die Override-ID genutzt — in
  **allen drei** Pfaden: `_launch_via_steam` `:1648`, `_build_proton_env` `:1701`,
  `findProtonRun` `:367`.
- **Anwendungsfall:** Demo-/EA-/GOTY-Editionen mit abweichender ID, geteiltes
  Prefix, Non-Steam-Shortcut.
- Validierung: nur Ziffern; leer = aus → Validierungshinweis statt Crash.
- *Höchstes Risiko:* **eine** Helper-Funktion „aktive Override-AppID" als Single
  Source of Truth, von allen drei Pfaden genutzt.

### Phase 4 — Copy-Deploy statt Symlinks (`wa_force_copy_deploy`)  — GroupBox B

- Checkbox. Default aus.
- **Wirkung:** Deployer nutzt Datei-Kopie statt Symlinks (Dateisysteme/Mounts ohne
  Symlink-Support, z.B. manche exFAT-/NTFS-Mounts).
- *Umsetzung:* Flag in Instanz-Config; `mod_deployer` liest es. Erst prüfen, ob
  Copy-Logik existiert; mindestens persistieren + auslesen.

### Phase 5 — Script-Extender-Shim-Deploy überspringen (`wa_skip_shim_deploy`)  — GroupBox B

- Checkbox. Default aus.
- **Wirkung:** Überspringt das automatische Kopieren der `ProtonShimFiles`
  (`winhttp.dll`, `X3DAudio1_7.dll` etc., siehe `game_skyrimse.py:64`,
  `game_fallout4.py:62`).
- **Anwendungsfall:** Nutzer verwaltet Shim manuell / anderer Loader.

### Phase 6 — INI-Schreibschutz beim Deploy (`wa_lock_inis`)  — GroupBox C

- Checkbox. Default aus.
- **Wirkung:** Markiert die Profil-INIs nach Deploy read-only, damit das Spiel sie
  nicht überschreibt.
- **Anwendungsfall:** Spiel/Proton setzt INIs bei Start zurück.

> **Konsequenz:** Pro Instanz speicherbar, beim Start anwendbar, kein
> globaler QSettings-Eintrag (Workarounds sind game-/prefix-spezifisch).
> Phasen 1–3 haben echte, klar lokalisierbare Einhängepunkte; 4–6 sind
> persistierte Flags, deren Konsumenten teils noch zu verdrahten sind
> (Minimum = persistiert + ausgelesen).

---

## 5. Betroffene Dateien

| Datei | Änderung | Phase |
|-------|----------|-------|
| `anvil/widgets/settings_dialog.py` | Block `688–742` ersetzen: neue, **aktivierte** Widgets (kein `_disabled()`), Werte aus `self._idata` vorbelegen; `addTab` `:742` einkommentieren; in `accept()` `:1103–1123` die `wa_*`-Felder in `idata` schreiben. | 0–6 |
| `anvil/core/instance_manager.py` | `_read_ini()` `:406` um Gruppe `[Workarounds]` (Präfix `wa_`); `save_instance()` `:287` um die `wa_*`-Keys. | 0 |
| `anvil/widgets/game_panel.py` | `_launch_via_steam()` `:1648/1651` + `_build_proton_env()` `:1701`: Extra-Args & Override-AppID aus Instanz-Config lesen/anwenden (Helper für aktive `idata`). | 1, 3 |
| `anvil/plugins/base_game.py` | `findProtonRun()` `:328`: optionalen Proton-Version-Override (Instanz-Wert) berücksichtigen; Liste installierter Proton-Versionen als Hilfsfunktion für die ComboBox. | 2, 3 |
| `anvil/core/mod_deployer.py` | `wa_force_copy_deploy` / `wa_skip_shim_deploy` / `wa_lock_inis` auslesen — **erst prüfen**, ob Konsumenten existieren; sonst Flag persistieren + Verdrahtung als Folge. | 4–6 |
| `anvil/locales/{de,en,es,fr,it,pt,ru}.json` | 7 Dateien — neue tr-Keys (siehe §7). | 0–6 |

**Impact-Analyse / Risiken:**
- `_read_ini` wird von **jedem** `load_instance` genutzt → neue Gruppe muss
  abwärtskompatibel sein (fehlende Gruppe → leeres Dict, kein Fehler).
- AppID-Override greift in 3 Launch-Pfade → konsistent **eine** Override-Quelle.
- BG3-Plugin **nicht** anfassen.
- Keine `setStyleSheet()` in neuen Widgets (QSS-Vererbung).

---

## 6. Umsetzungsschritte (entlang der Phasen)

**Phase 0 — Fundament**
1. `instance_manager._read_ini()` + `save_instance()` um `[Workarounds]`-Gruppe
   (`wa_*`) erweitern. Mit echter `.anvil.ini` testen (Skyrim SE / Cyberpunk),
   Altinstanz ohne Gruppe darf nicht brechen.
2. Block `688–742` durch die 3 GroupBoxen ersetzen, Widgets **aktiviert**, Werte aus
   `self._idata` vorbelegen, Instanz-Name im Kopf.
3. `addTab` `:742` einkommentieren; in `accept()` die `wa_*`-Werte in `idata` schreiben.
4. Test: Tab sichtbar + leer-speicherbar, `.anvil.ini` bekommt `[Workarounds]`, Reopen
   zeigt Werte.

**Phase 1 — Extra-Args**
5. `_launch_via_steam` liest `wa_extra_launch_args`, `shlex`-parst, hängt nach
   `GameLaunchArgs` an. Test: Args im Start-Log.

**Phase 2 — Proton-Version**
6. Hilfsfunktion (in `base_game`/`steam_utils`), die installierte Proton-Versionen
   findet → ComboBox füllen. `findProtonRun` respektiert Override für Tool-Starts.

**Phase 3 — AppID-Override**
7. Single-Source-Helper „aktive Override-AppID". `_launch_via_steam`,
   `_build_proton_env`, `findProtonRun` nutzen ihn. Validierung (nur Ziffern).

**Phasen 4–6 — Deploy-Flags**
8. Konsumenten in `mod_deployer` prüfen; mindestens persistieren + auslesen
   (Copy-Deploy, Shim-Skip, INI-Lock).

**Querschnitt (jede Phase)**
9. Neue tr-Keys in **7** Locale-Dateien (gleiche Key-Anzahl).
10. `python -m py_compile` auf alle geänderten Dateien.
11. `./restart.sh`, Log auf Traceback/NameError/ImportError/AttributeError prüfen.
12. Manueller Test gem. Akzeptanzkriterien.

---

## 7. i18n (tr-Keys, 7 Locales)

Alle Keys in **`anvil/locales/{de,en,es,fr,it,pt,ru}.json`** — identische Key-Anzahl
halten (aktuell 1106 je Datei).

**Wiederverwendbar (vorhanden):** `settings.tab_workarounds`, `settings.options`.

**Neu anzulegen:**

| Key | DE (Referenz) |
|-----|---------------|
| `settings.wa_for_instance` | „Workarounds für Instanz: {name}" |
| `settings.wa_grp_launch` | „Start / Proton" |
| `settings.wa_grp_deploy` | „Deploy-Schritte" |
| `settings.wa_grp_ini` | „INI / Saves" |
| `settings.wa_extra_launch_args` | „Zusätzliche Startargumente" |
| `settings.wa_extra_launch_args_ph` | „z.B. --skip-launcher -windowed" |
| `settings.wa_force_proton` | „Proton-Version erzwingen (für Tools)" |
| `settings.wa_force_proton_auto` | „Automatisch (Steam-Einstellung)" |
| `settings.wa_override_appid` | „Steam-AppID überschreiben" |
| `settings.wa_override_appid_ph` | „z.B. 489830" |
| `settings.wa_force_copy_deploy` | „Statt Symlinks Dateien kopieren" |
| `settings.wa_skip_shim_deploy` | „Script-Extender-Shim nicht automatisch deployen" |
| `settings.wa_lock_inis` | „Profil-INIs nach Deploy schreibschützen" |
| `settings.wa_hint` | „Diese Einstellungen gelten nur für die aktuelle Instanz und werden beim Spielstart angewendet." |
| `settings.wa_appid_invalid` | „Steam-AppID muss eine Zahl sein." |

> Bestehende Keys `settings.wa_steam_username/_password/_backdate_bsa/_reset_geometry/…`
> werden nicht mehr referenziert; **nicht löschen nötig** (ungenutzt, harmlos),
> Aufräumen optional in separatem Commit.

---

## 8. Akzeptanzkriterien

**Phase 0**
- [ ] Workarounds-Tab ist **sichtbar** (`addTab` aktiv), Kopf zeigt **aktive Instanz**.
- [ ] Tab zeigt **nur Linux-/Proton-relevante** Optionen — keine
      Username/Passwort/BSA-Backdate/Geometrie-Reset-Widgets mehr.
- [ ] Alle Widgets **aktiviert** (kein `_disabled()`), kein „Noch nicht verfügbar".
- [ ] Werte werden in `[Workarounds]` der `.anvil.ini` geschrieben (real verifiziert),
      Reopen → korrekt vorbelegt.
- [ ] Altinstanz ohne `[Workarounds]` startet fehlerfrei (abwärtskompatibel).

**Phase 1–3**
- [ ] Extra-Startargumente werden korrekt geparst und an den Steam-Start angehängt.
- [ ] Proton-ComboBox listet „Automatisch" + tatsächlich installierte Versionen;
      gewählte Version greift bei Tool-Starts.
- [ ] Override-AppID (falls gesetzt) wird in **allen** Launch-Pfaden statt
      `GameSteamId` verwendet; leer → Plugin-Default; ungültig → Hinweis, kein Crash.

**Phase 4–6**
- [ ] Deploy-Flags (Copy/Shim/INI-Lock) werden mindestens persistiert und ausgelesen.

**Querschnitt**
- [ ] Keine `setStyleSheet()` in neuen Widgets; QSS-Theme erbt korrekt.
- [ ] Alle 7 Locale-Dateien enthalten die neuen Keys (gleiche Key-Anzahl).
- [ ] `python -m py_compile` fehlerfrei für alle geänderten Dateien.
- [ ] `./restart.sh` startet ohne Traceback/NameError/ImportError/AttributeError.
- [ ] **BG3-Code unverändert.**

---

## 9. Aufwand / Risiko

**Aufwand:** mittel (~4–6 h), gut in Phasen aufteilbar.
- Phase 0 (UI-Ersatz + Config-Layer): gering, aber zentral — sorgfältig testen.
- Phase 1 (Extra-Args): trivial.
- Phase 2 (Proton-Scan): gering–mittel.
- Phase 3 (AppID, 3 Pfade): mittel — höchste Sorgfalt.
- Phasen 4–6 (Flags): gering für Persistenz; volle Verdrahtung ggf. Folge.
- i18n: gering, aber 7 Dateien (Falle: Key-Anzahl synchron halten).

**Risiko:** mittel.
- **Höchstes Risiko (Phase 3):** AppID-Override greift in mehrere Launch-/Proton-Pfade
  — bei inkonsistenter Quelle landet ein Start im falschen Prefix. **Eine** Helper-
  Funktion „aktive Override-AppID" als Single Source of Truth.
- `_read_ini`-Änderung abwärtskompatibel testen (alte Instanzen ohne `[Workarounds]`).
- Proton-Force betrifft nur Anvil-Tool-Starts, nicht den Steam-Hauptstart — im
  UI-Hinweis klarstellen, sonst Nutzer-Verwirrung.
- BG3-Plugin nicht berühren (CLAUDE.md-Verbot).
