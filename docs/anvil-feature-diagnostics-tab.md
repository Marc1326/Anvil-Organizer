# Feature-Spec: Diagnostics Tab (#23)
**Status:** Geplant (Spec verifiziert gegen echten Code)
**Datum:** 2026-06-28

## 1. Problem / Ziel

GitHub-Issue #23 „Feature: Implement Diagnostics Tab" (Labels: `disabled-feature`,
`enhancement`). Issue-Text wörtlich:

> The diagnostics tab is completely hidden.
> Expected Behavior:
> - Display system info (OS, Python, Qt version, memory, etc.)
> - Detect and display mod conflicts
> - Check deployment status (missing symlinks, broken links)
> - Log viewer with filter and search functionality
> - Export button for support reports
> Status: Tab completely hidden — no UI, no logic implemented.

Der Diagnose-Tab im Einstellungs-Dialog ist gebaut, aber versteckt: das Widget wird
vollständig aufgebaut, der `addTab()`-Aufruf ist jedoch auskommentiert — der Tab
erscheint nie. Die vorhandenen Widgets (Log-Level-/Crash-Dump-ComboBoxen, alle per
`_disabled()` ausgegraut) sind ein Skelett aus der Referenz-Implementierung und für
einen nativen Linux-Mod-Manager weitgehend sinnlos (kein Windows-Crash-Dump-Konzept).

**Ziel:** Ein nutzbarer Diagnose-/Log-Tab, der bei der Problemsuche hilft und
Bug-Reports erleichtert: Systeminfo, Pfad-/Deploy-Checks, erkannte Probleme,
Log-Viewer mit Filter/Suche, Export-Button. Das Skelett wird durch echten Inhalt
ersetzt.

## 2. Phasen-Rückgrat (Bau-Reihenfolge nach steigendem Risiko)

| # | Phase | Inhalt | Risiko | Testbar nach Phase? |
|---|---|---|---|---|
| 1 | Core-Modul (GUI-frei) | `anvil/core/diagnostics.py`: `collect_system_info`, `read_log_tail`, `build_report`. Reine Funktionen, nie raisen. | niedrig | Ja — direkt im Python-REPL / per import aufrufbar, kein GUI nötig |
| 2 | Tab sichtbar + Systeminfo | Skelett-Block (744–773) durch echten Tab ersetzen, `addTab` aktivieren (773), Sektion Systeminfo (read-only QLineEdits) füllen | niedrig | Ja — Tab erscheint, Systeminfo gefüllt |
| 3 | Pfad-Checks | `collect_path_checks(idata, instance_path)` + Sektion mit Status (OK/Fehlt/Nicht beschreibbar) + „Öffnen" via `host_open_path`. `%INSTANCE_DIR%`-Auflösung wie im Dialog vorhanden (Z.373) | mittel | Ja — auch mit absichtlich falschem Pfad testbar |
| 4 | Problemerkennung | `detect_problems(...)` + Sektion „Erkannte Probleme" (Severity-farbig über QPalette, kein Stylesheet) | mittel | Ja — Warnungen bei fehlendem Game-Pfad etc. |
| 5 | Log-Viewer | ComboBox (activity.log / debug.log / Backups) + Suchfeld (Live-Filter) + read-only `QPlainTextEdit` + Refresh/Öffnen | mittel | Ja — Log lädt, Filter grenzt ein |
| 6 | Export | `QFileDialog.getSaveFileName` → `build_report()` als `.txt`; „In Zwischenablage kopieren" | niedrig | Ja — Datei mit plausiblem Inhalt |
| 7 | Mod-Konflikte (optional, Scope-Cut) | Button „Konflikte scannen". **Achtung:** braucht MainWindow-State (siehe §3.4) → ggf. Folge-Schritt | hoch | Nur eingeschränkt — Abhängigkeit von Live-State |
| 8 | i18n | Alle neuen `tr()`-Keys in alle 7 Locales | niedrig | Ja — keine untersetzten Strings |

Bau-Empfehlung: Phasen 1–6 decken Issue #23 funktional ab. Phase 7 nur wenn Zeit bleibt.

## 3. Ist-Zustand im Code (verifizierte Anker)

### 3.1 Deaktivierter Tab
- **`anvil/widgets/settings_dialog.py:744–773`** — Block `# Tab Diagnose`. Verifiziert:
  - `:745` `diagnose_tab = QWidget()`, `:747` `QScrollArea`, `:752` GroupBox
    `tr("settings.diag_logs_crashes")`.
  - 3 per `_disabled()` ausgegraute Widgets: `:754` `log_combo` (`:756` `_disabled`),
    `:758` `crash_combo` (`:760`), `:762` `crash_spin` (`:764`).
  - `:767` Hinweis-Label `tr("settings.diag_hint")`.
  - **`:773`** `# self._tabs.addTab(diagnose_tab, tr("settings.tab_diagnostics"))`
    — auskommentiert, daher nie sichtbar.
- Aktiv hinzugefügte Tabs zum Vergleich: `:182` general, `:237` style, `:322`
  modlist, `:413` paths, `:540` nexus, `:679` plugins, `:828` script-merger,
  `:898` loot. (`:742` workarounds-Tab ebenfalls auskommentiert.)
- Tab-Container: **`:61`** `self._tabs = QTabWidget()`; `:900` `layout.addWidget(self._tabs)`.
- `_disabled()`-Helper: **`:73`** `def _disabled(w):`.

### 3.2 Vorhandene i18n-Keys (Skelett — verifiziert in de.json)
- **`anvil/locales/de.json:779–795`**: `diag_logs_crashes` (779), `diag_log_level` (780),
  `diag_crash_dump` (781), `diag_max_crash_dumps` (782), `diag_integrated_loot` (783),
  `diag_loot_log_level` (784), `diag_hint` (794), `tab_diagnostics` (795).
- **`tab_diagnostics` existiert in allen 7 Locales** (verifiziert: de/en/es/fr/it/pt/ru je 1×)
  → **kann wiederverwendet werden**, kein neuer Key nötig.
- `diag_loot_log_level` ist **bereits verdrahtet** (`settings_dialog.py:876`,
  `opts_layout.addRow(tr("settings.diag_loot_log_level"), self._loot_log_combo)` im
  LOOT-Tab) — **kein** Waisen-Key. Nur `diag_integrated_loot` ist ein echter Waisen-Key
  (definiert, aber nicht verdrahtet). Crash-Dump-/LOOT-Skelett-Keys dürfen bleiben
  (kein Löschen nötig).

### 3.3 Vorhandene Diagnose-Datenquellen (verifiziert, nur lesend nutzen)

| Quelle | Datei:Zeile (verifiziert) | Liefert |
|---|---|---|
| Activity-Log | `anvil/core/activity_log.py:13` `_LOG_DIR = Path.home() / ".anvil-organizer" / "logs"`, `:14` `_LOG_FILE = .../activity.log`, `:19` `_rotate_if_needed` (Backups `.log.1`…`.log.N`), `:54` `log_action()` | Nur Schreib-API (`log_action`, never raises). **Kein Reader vorhanden** — neu zu bauen. Format: strukturierte Zeilen, Wochenrotation. |
| debug.log | `restart.sh:6` `python -u main.py 2>&1 \| tee debug.log` | Roher stdout/stderr inkl. Tracebacks am **Projektroot**. **Kein Logging-Framework** — entsteht nur bei Start über `restart.sh`. Bei Flatpak/AppImage nicht vorhanden → robust behandeln (Datei kann fehlen). |
| Instance-Config | `anvil/core/instance_manager.py:270` `load_instance(name)`, `:326` `current_instance()`, `:55` `list_instances()`, `:405` `_read_ini()` | Dict aus `.anvil.ini`. **Key-Schema (verifiziert in `_read_ini`):** General-Keys OHNE Prefix (`game_path`, `detected_store`, `game_name`, `game_short_name`, `selected_profile`, `local_inis`, `local_saves`); Paths-Keys **MIT `path_`-Prefix** (`path_mods_directory`, `path_downloads_directory`, `path_overwrite_directory`, `path_profiles_directory`). Werte teils mit `%INSTANCE_DIR%`-Platzhalter. |
| LOOT-Status | `anvil/core/loot/loot_runner.py:21` `find_loot_binary()`; `anvil/core/loot/loot_report.py:45` Feld `loot_version` | Binary-Pfad oder `None` (PATH/Flatpak/QSettings). |
| Sandbox-Status | `anvil/core/subprocess_env.py:20` `is_flatpak()`, `:118` `is_appimage()`, `:123` `_is_bundled()`, `:214` `host_open_path()` | Flatpak/AppImage/PyInstaller-Erkennung; Host-Öffnen von Pfaden. |
| Konflikt-Scanner | `anvil/core/conflict_scanner.py:60` `class ConflictScanner`, `:69` `scan_conflicts(mods, game_plugin=None, mod_index=None, pak_file_lists=None) -> dict` | Dict mit `conflicts` (je `{file, mods, winner}`) + `ignored`. **Index 0 = niedrigste, letzter = höchste Priorität (Winner)** — umgekehrt zur GUI-Reihenfolge. |
| Deploy/Symlink | `anvil/core/mod_deployer.py:60` `class DeployResult`, `:132` `deploy() -> DeployResult`; `is_symlink()`-Checks u.a. `:219, :255, :424, :458, :626, :634` | Symlink-Status, broken-Link-Handling. |
| Version | `anvil/version.py:3` `APP_VERSION = "1.5.2"` (`from anvil.version import APP_VERSION`) | App-Version. |
| Log-Viewer-Vorbild | `anvil/widgets/log_panel.py:143` `class LogPanel`, `:304` `copy_all()`, `:313` Kontextmenü, `:91` `class LevelBadge` | In-Memory-Log-Panel (Card-Style, Level-Filter) — als UI-Vorbild, **nicht** direkt für Datei-Logs. |

### 3.4 Wiederverwendbare UI-/Pfad-Patterns (verifiziert)
- Read-only-Anzeige: `QLineEdit` + `setReadOnly(True)` + `setPlaceholderText("—")`
  — Muster im Nexus-Konto-Block **`settings_dialog.py:428–451`**.
- **`%INSTANCE_DIR%`-Auflösung: KEIN zentraler Resolver in `instance_manager`.**
  Auflösung erfolgt inline. Im selben Dialog bereits vorhanden:
  **`settings_dialog.py:373–381`** — `_resolve(val) = val.replace("%INSTANCE_DIR%", str(ipath))`
  liest `path_downloads_directory`, `path_mods_directory`, `path_profiles_directory`,
  `path_overwrite_directory`, `game_path` aus `self._idata`. Gleiches Muster in
  `mainwindow.py:1195–1199`. → Für die Diagnose dieselbe Inline-Logik nutzen, KEINE
  zweite Implementierung.
- Instanz-State im Dialog vorhanden: **`settings_dialog.py:64–70`** —
  `self._idata = load_instance(cur)`, `self._instance_path = instances_path() / cur`
  (beide `None`/`{}` falls keine Instanz aktiv → defensiv behandeln).
- Pfad-Öffnen im Host: `host_open_path(path)` — **bereits importiert** (`settings_dialog.py:8`).
- Tab-Aufbau-Muster: `QScrollArea` (resizable, `NoFrame`) → Content-`QWidget` →
  `QVBoxLayout` mit `QGroupBox`-Sektionen (siehe Script-Merger-Tab `:776–818`).

### 3.5 Import-Status (verifiziert in `settings_dialog.py:10–35`)
- **Bereits importiert:** `QFileDialog` (`:13`), `QGroupBox` (`:18`), `QComboBox` (`:19`),
  `QPushButton` (`:21`), `QScrollArea` (`:22`), `QFrame` (`:23`), `QTableWidget` (`:24`),
  `QTableWidgetItem` (`:25`), `QHeaderView` (`:26`), `QLabel` (`:27`), `QListWidget` (`:28`),
  `QLineEdit` (`:30`), `QFormLayout` (`:31`), `QTreeWidget` (`:32`), `QTreeWidgetItem` (`:33`),
  `QSpinBox` (`:34`), `QHBoxLayout`/`QVBoxLayout`. Auch `QColor`, `QFont` (`:36`).
- **NUR fehlend: `QPlainTextEdit`** (für den Log-Tail-Viewer) — als einziger neuer Import
  in `:10–35` zu ergänzen. (Korrektur zur Erstfassung: `QFileDialog`, `QTableWidget`,
  `QTreeWidget` sind bereits da.)

**Wichtig:** Es existiert **kein** Reader für `activity.log` und **kein** zentraler
Diagnose-Sammler. `anvil/core/diagnostics.py` existiert noch nicht — beides neu zu bauen.

## 4. Lösung / Ansatz

Den auskommentierten Tab (744–773) durch echten Inhalt ersetzen und aktiv hinzufügen.
Datenbeschaffung in ein GUI-freies Core-Modul auslagern.

### 4.1 Core-Modul `anvil/core/diagnostics.py` (neu)
Reine Sammelfunktionen, GUI-frei, werfen nie (alles try/except, liefern Strings/Dicts):

- `collect_system_info() -> dict`
  - OS: `platform.platform()`, Distro aus `/etc/os-release` (falls lesbar)
  - Kernel: `platform.release()`
  - Python: `platform.python_version()`
  - Qt/PySide6: `PySide6.__version__`, `qVersion()`
  - App-Version: `from anvil.version import APP_VERSION`
  - Laufmodus: `is_flatpak()` / `is_appimage()` / sonst Quellcode (aus `subprocess_env`)
  - Speicher: aus `/proc/meminfo` (`MemTotal`/`MemAvailable`), optional
  - Desktop/Session: `XDG_CURRENT_DESKTOP`, `XDG_SESSION_TYPE`
- `collect_path_checks(idata: dict, instance_path) -> list[dict]`
  - Pro Pfad ein Dict `{label, path, exists: bool, writable: bool}`
  - Geprüft (echte Key-Namen!): `game_path`, `path_mods_directory`,
    `path_downloads_directory`, `path_overwrite_directory`, `path_profiles_directory`.
  - `%INSTANCE_DIR%` über `val.replace("%INSTANCE_DIR%", str(instance_path))` auflösen
    (gleiche Inline-Logik wie `settings_dialog.py:373`). Bei `instance_path is None`
    keine Auflösung → Pfad als „unbekannt" markieren.
- `detect_problems(idata, sysinfo, path_checks) -> list[dict]`
  - Liste `{severity: "error"|"warning"|"info", message_key, detail}`
  - Heuristiken (ohne BG3-Code anzufassen):
    - Game-Pfad existiert nicht → error
    - Mods-/Downloads-/Overwrite-Verzeichnis fehlt oder nicht beschreibbar → warning
    - `detected_store == "steam"` aber kein Steam-Compatdata/Prefix auffindbar → warning
    - LOOT nicht gefunden (`find_loot_binary() is None`) → info
    - Läuft als AppImage/Flatpak → info (Kontext für Bug-Reports)
- `read_log_tail(path, max_lines: int = 2000) -> list[str]`
  - Letzte N Zeilen aus `activity.log` bzw. `debug.log`, robust gegen
    fehlende Datei/Encoding-Fehler (gibt `[]` zurück, raised nie).
- `build_report(sysinfo, path_checks, problems, log_tail=None) -> str`
  - Klartext-Support-Report. **Keine Geheimnisse:** keine API-Keys/Credentials
    (kein `credentials.bin`), nur Pfade.

### 4.2 Tab-UI in `settings_dialog.py` (Ersatz für Block 744–773)
Vier GroupBoxen plus Export-Leiste:

1. **Systeminfo** (`diag_system_info`): read-only `QLineEdit`s im `QFormLayout`
   aus `collect_system_info()`, Muster wie Nexus-Konto (`:428–451`).
2. **Pfad-Prüfung** (`diag_path_checks`): Tabelle/Liste pro Pfad mit Status
   (OK/Fehlt/Nicht beschreibbar) + „Öffnen" via `host_open_path` (bereits importiert).
3. **Erkannte Probleme** (`diag_problems`): Liste aus `detect_problems()`,
   Severity über `QColor`/`setForeground` auf Items (kein Stylesheet). Bei leer:
   `diag_no_problems`.
4. **Log-Viewer** (`diag_logs`): `QComboBox` (activity.log / debug.log / Backups)
   + Suchfeld (`QLineEdit`, Live-Filter) + read-only `QPlainTextEdit` (Log-Tail).
   Buttons „Aktualisieren"/„Datei öffnen". Kein Live-Tailing — Refresh per Knopfdruck.
5. **Export-Leiste**: „Report exportieren" → `QFileDialog.getSaveFileName` (bereits
   importiert) → schreibt `build_report(...)` als `.txt`; „In Zwischenablage kopieren".

**QSS/Theme:** Kein `setStyleSheet()` in neuen Widgets — Theme wird vererbt.

### 4.3 Aktivierung
- **`:773`** einkommentieren →
  `self._tabs.addTab(diagnose_tab, tr("settings.tab_diagnostics"))`.
  Reihenfolge unkritisch (am Ende nach LOOT/Script-Merger sinnvoll).
- Daten beim Öffnen / „Aktualisieren" laden — nicht blockierend im `__init__`
  (teure Scans nur auf Knopfdruck).

### 4.4 Mod-Konflikte (Issue-Wunsch — Phase 7, Scope-Cut-Kandidat)
`ConflictScanner.scan_conflicts(mods, game_plugin, ...)` ist vorhanden, **aber der
SettingsDialog hat den nötigen Live-State NICHT.** Verifiziert: die echten Aufrufer
(`mainwindow.py:1731` und `:1744`) brauchen `_current_mod_entries`,
`_current_plugin`, `_mod_index`, `pak_file_lists` — alles MainWindow-Attribute, die
im Dialog fehlen (`_idata`/`_instance_path` reichen nicht). Optionen:
- Konflikt-Daten vom MainWindow in den Dialog reichen (Signal/Parameter), oder
- Button „Konflikte scannen" als Verweis/Folge-Schritt.
Falls Zeit knapp: **Scope-Cut** — Kern (Phasen 1–6) deckt Issue #23 bereits ab.
Gleiches gilt für „Deploy-Status" (broken Symlinks): die `is_symlink()`-Checks liegen
in `mod_deployer.deploy()`-Interna ohne fertige Status-Abfrage → bei Bedarf eigene
leichte Symlink-Prüfung über die aufgelösten Mod-/Deploy-Pfade.

## 5. Betroffene Dateien

| Datei | Art | Änderung |
|---|---|---|
| `anvil/core/diagnostics.py` | **neu** | Sammel-/Report-Funktionen (GUI-frei) |
| `anvil/widgets/settings_dialog.py` | ändern | Block 744–773 ersetzen, Tab aktivieren (Z.773), **nur `QPlainTextEdit` importieren** (Rest vorhanden); Slot-Methoden `_diag_refresh`, `_diag_export`, `_diag_copy_report`, `_diag_open_log`, `_diag_filter_log`, optional `_diag_scan_conflicts` |
| `anvil/locales/de.json` … `ru.json` (7×) | ändern | neue `diag_*`-Keys |

**Nur lesend genutzt (nicht ändern):** `activity_log.py`, `instance_manager.py`,
`loot_runner.py`, `loot_report.py`, `subprocess_env.py`, `conflict_scanner.py`,
`mod_deployer.py`, `version.py`. **BG3-Code wird nicht angefasst.**

## 6. Umsetzungsschritte

1. `anvil/core/diagnostics.py` anlegen: `collect_system_info`, `collect_path_checks`,
   `detect_problems`, `read_log_tail`, `build_report` — alle defensiv (try/except,
   nie raisen). `python -m py_compile` grün. (Phase 1)
2. In `settings_dialog.py:10–35` **`QPlainTextEdit` ergänzen** (einziger fehlender Import).
3. Block 744–773 durch die 5 Sektionen aus §4.2 ersetzen; Widgets als `self._diag_*`
   halten, wo Slots sie brauchen. (Phasen 2–6)
4. Slot-Methoden implementieren: `_diag_refresh()` (Systeminfo + Pfad-Checks + Probleme),
   `_diag_open_log()`, `_diag_filter_log()`, `_diag_export()`, `_diag_copy_report()`,
   optional `_diag_scan_conflicts()`. Button-Signale: `clicked.connect(lambda checked=False: ...)`.
5. Tab aktivieren: Z.773 einkommentieren.
6. Alle neuen `tr()`-Keys in **alle 7** Locales (de, en, es, fr, it, pt, ru).
7. `./restart.sh` ausführen, `debug.log` auf Traceback/NameError/ImportError prüfen.
8. Manuell testen: Tab sichtbar, Systeminfo gefüllt, Pfad-Checks korrekt (auch bei
   absichtlich falschem Pfad), Log-Viewer zeigt `activity.log`, Suche filtert,
   Export schreibt Datei mit plausiblem Inhalt (ohne Credentials).

## 7. i18n (tr-Keys, 7 Locales)

**Wiederverwenden (existiert in allen 7 Locales):** `tab_diagnostics`.
Skelett-Keys (`diag_logs_crashes`, `diag_hint`, `diag_crash_dump`, …) dürfen bleiben.

**Neu** (Namespace `settings.` bzw. `label.`):
- `settings.diag_system_info` — „Systeminfo"
- `settings.diag_path_checks` — „Pfad-Prüfung"
- `settings.diag_problems` — „Erkannte Probleme"
- `settings.diag_no_problems` — „Keine Probleme erkannt."
- `settings.diag_logs` — „Logs"
- `settings.diag_log_select` — „Logdatei:"
- `settings.diag_search` — „Suchen…"
- `settings.diag_refresh` — „Aktualisieren"
- `settings.diag_open_file` — „Datei öffnen"
- `settings.diag_export_report` — „Report exportieren"
- `settings.diag_copy_report` — „Report kopieren"
- `settings.diag_scan_conflicts` — „Konflikte scannen" (nur bei Phase 7)
- `label.diag_status_ok` / `..._missing` / `..._not_writable`
- `label.diag_sev_error` / `..._warning` / `..._info`
- Problem-Meldungs-Keys: `label.diag_problem_game_path`, `..._mods_dir`,
  `..._steam_prefix`, `..._loot_missing`, `..._sandbox_mode`

**Pflicht:** Jeder neue Key in **allen 7** Locales (de/en/es/fr/it/pt/ru) — fehlende
Keys führen zu untersetzten Strings.

## 8. Akzeptanzkriterien

- [ ] Diagnose-Tab ist im Einstellungs-Dialog sichtbar (Z.773 aktiviert).
- [ ] Systeminfo zeigt: OS/Distro, Kernel, Python, Qt/PySide6, App-Version,
      Laufmodus (Flatpak/AppImage/Quellcode), Desktop/Session, Speicher.
- [ ] Pfad-Prüfung listet alle Instanz-Pfade mit Status (OK/Fehlt/Nicht beschreibbar)
      über die echten Keys (`game_path`, `path_mods_directory`, `path_downloads_directory`,
      `path_overwrite_directory`, `path_profiles_directory`); `%INSTANCE_DIR%` korrekt
      aufgelöst; „Öffnen" funktioniert.
- [ ] Erkannte Probleme zeigt Warnungen bei fehlendem Game-Pfad, fehlendem
      Steam-Prefix, fehlendem LOOT etc.; bei sauberem System „Keine Probleme erkannt".
- [ ] Log-Viewer lädt `activity.log` und `debug.log` (robust, wenn Datei fehlt),
      Such-/Filterfeld grenzt Zeilen ein, „Aktualisieren" lädt neu.
- [ ] Export schreibt `.txt` mit Systeminfo + Pfad-Checks + Problemen (+ Log-Tail);
      enthält **keine** Credentials/API-Keys. „Kopieren" legt denselben Text in die Zwischenablage.
- [ ] `anvil/core/diagnostics.py` ist GUI-frei und wirft bei keinem Aufruf eine Exception
      (auch ohne aktive Instanz / bei fehlenden Dateien).
- [ ] Nur `QPlainTextEdit` neu importiert; keine doppelte `%INSTANCE_DIR%`-Logik.
- [ ] Alle neuen `tr()`-Keys in allen 7 Locale-Dateien vorhanden.
- [ ] Kein `setStyleSheet()` in neuen Widgets; keine hardcoded Pfade; kein BG3-Code berührt.
- [ ] `python -m py_compile` grün; `./restart.sh` startet ohne Traceback/NameError/ImportError.

## 9. Aufwand / Risiko

**Aufwand:** Mittel. Core-Modul ~150–250 Zeilen; Tab-UI + Slots ~200–300 Zeilen;
7 Locales × ~20 Keys. Geschätzt 1 fokussierte Session (Phasen 1–6).

**Risiken / Fallstricke:**
- **Path-Key-Namen:** Paths-Keys haben `path_`-Prefix (`path_mods_directory` etc.),
  General-Keys nicht (`game_path`). Falsche Keys → leere Pfad-Checks.
- **`%INSTANCE_DIR%`-Auflösung NICHT zentral** — Inline-Replace wie `settings_dialog.py:373`
  / `mainwindow.py:1195` nutzen, nicht neu erfinden.
- **Konflikt-/Deploy-Scan** braucht MainWindow-Live-State (`_current_mod_entries`,
  `_current_plugin`, `_mod_index`), den der Dialog nicht hat → Phase 7 ist Scope-Cut.
- Flatpak/AppImage: `debug.log` existiert dort nicht → defensiv lesen, `host_open_path`
  statt direktem Öffnen.
- Export darf keine Geheimnisse leaken (`credentials.bin`/API-Keys ausschließen).
- Qt-Signal-Falle: `clicked.connect(lambda checked=False: ...)` für Buttons.
- Dynamisch erzeugte Items/Chips ggf. `.show()` nötig (addWidget macht nicht sichtbar).

**Scope-Cut (falls Zeit knapp):** Mod-Konflikt-/Deploy-Scan (Phase 7, §4.4) als
Folge-Schritt — der Kern (Systeminfo, Pfad-Checks, Problemerkennung, Log-Viewer,
Export) deckt Issue #23 funktional ab und ist der größte Support-Nutzen.
