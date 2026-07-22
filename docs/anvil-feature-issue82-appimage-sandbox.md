# Feature: Issue #82 — AppImage Sandbox-Fixes (Ordner/URL öffnen + mods/profiles-Pfade)

Datum: 2026-06-07
Build-Kontext: v1.5.0 AppImage (PyInstaller), CachyOS, frische Installation
Konsolidiert aus: planer-agent-1-issue82.md, planer-agent-2-issue82.md, planer-agent-3-issue82.md

---

## Problem

Drei Bugs auf einer frischen v1.5.0-AppImage (gemeldet auf CachyOS):

1. **Ordner im Dateimanager öffnen ist tot** — Klick auf Folder-Buttons/Folder-Icons löst nichts aus.
2. **URL/Nexus-Seite öffnen ist tot** — Klick auf Nexus-Links/Web-Links löst nichts aus (Konsolenmeldung: `kde-open: /tmp/.mount_Anvil_XXXX/usr/bin/_in...`).
3. **mods/profiles-Pfade werden ignoriert** — Trägt der User einen abweichenden mods- oder profiles-Pfad ein, nutzt die App weiterhin hardcoded `.mods`/`.profiles`.

**Gemeinsame Wurzel Bug 1+2:** Im AppImage leakt der PyInstaller-Bootloader `LD_LIBRARY_PATH=.../usr/bin/_internal` (und Qt setzt zusätzlich `QT_PLUGIN_PATH`/`GTK_PATH`/`GIO_MODULE_DIR`/`PYTHONPATH`/`PYTHONHOME`) in den laufenden Prozess. Jeder extern gestartete Open-Helfer (`xdg-open` → `kde-open`/`/bin/sh`/GIO-MIME-Handler) erbt diese Umgebung und lädt die gebündelten Libs statt der System-Libs → symbol-lookup-error / stiller Abbruch. Es gibt **keinen zentralen Host-Opener-Helper** — die ~35 Aufrufstellen sind über drei inkonsistente Mechanismen verstreut.

**Wurzel Bug 3:** Die konfigurierten Pfade werden korrekt gespeichert und gelesen (`path_mods_directory`/`path_profiles_directory`), aber im konsumierenden Code an ~30 Stellen mit hardcoded `instance_path / ".mods"` bzw. `".profiles"` überschrieben. `downloads` ist über `self._current_downloads_path` bereits zentralisiert — für mods/profiles fehlen die analogen Instanzvariablen.

---

## Ursachen (konsolidiert)

### Bug 1 — Ordner öffnen tot
Zwei getrennte, inkonsistente Code-Wege:
- **Mechanismus A** `subprocess.Popen(["xdg-open", ...], env=clean_subprocess_env())` — übergibt zwar bereinigte Env, aber `clean_subprocess_env()` repariert NUR `LD_LIBRARY_PATH`, nicht `QT_PLUGIN_PATH`/`GTK_PATH`/`GIO_MODULE_DIR`/`PYTHONPATH`/`PYTHONHOME`. Halb-geschützt.
- **Mechanismus B** `QDesktopServices.openUrl(QUrl.fromLocalFile(...))` — komplett ohne Env-Bereinigung; Qt startet den Opener intern mit der verseuchten Env. Ungeschützt.

Wichtigste Fundstellen:
- `anvil/mainwindow.py:3369, 3376, 3385, 3394, 3409, 3416, 3425, 3433, 3440, 3447, 3454, 3462` (12 Folder-Buttons `_open_*_folder`)
- `anvil/widgets/game_panel.py:635` (`_on_explore_virtual_folder`, Qt-Weg), `:1950` (Saves-Ordner, Qt-Weg)
- `anvil/widgets/instance_manager_dialog.py:464` (Instanz-Ordner, Qt-Weg)
- `clean_subprocess_env()` in `anvil/core/subprocess_env.py:65-77` (unvollständige Env-Bereinigung)

### Bug 2 — URL/Nexus tot
ALLE URL-Öffnungen laufen über `QDesktopServices.openUrl(QUrl(...))` → Qts interner xdg-open/kde-open erbt die PyInstaller-Env → `kde-open: /tmp/.mount_.../usr/bin/_in...`.

Wichtigste Fundstellen:
- `anvil/mainwindow.py:578` (Wiki), `:586` (Issues), `:652/:654` (`_on_menu_visit_nexus`), `:835`, `:5240` (`_ctx_open_nexus_page` — exakt die im Issue genannte Aktion)
- `anvil/widgets/game_panel.py:2534` (Download-Kontextmenü Nexus-Seite)
- `anvil/dialogs/reshade_wizard.py:169` (reshade.me)
- `anvil/dialogs/collection_import_dialog.py:68` (Nexus-URL)
- `anvil/core/nexus_sso.py:165` (SSO-Login-URL via `subprocess.Popen` — unter Flatpak ohne `--host`-Breakout)

### Bug 3 — mods/profiles-Pfade ignoriert
Datenfluss korrekt bis zum Lesen, dann hardcoded überschrieben:
- Schreiben: `anvil/widgets/settings_dialog.py:1117-1119` (`path_mods_directory`/`path_profiles_directory`/`path_downloads_directory`).
- Persistenz/Default: `anvil/core/instance_manager.py:395-399` (`mods_directory = %INSTANCE_DIR%/.mods`, `profiles_directory = %INSTANCE_DIR%/.profiles`).
- Lesen: `anvil/mainwindow.py:1196-1201` löst `mods_dir` korrekt auf — **wird aber Z.1294 sofort mit `instance_path / ".mods"` überschrieben**; `profiles_dir` (Z.1258, 1289) wird gar nicht aus Config gelesen.
- Zweiter Verbraucher: `anvil/core/mod_entry.py:220-221` (`scan_mods_directory`) hardcodet `.mods`/`.profiles`, kennt die Custom-Pfade nicht.
- ~30 weitere hardcoded `.mods`/`.profiles`-Stellen in `mainwindow.py` plus `core/mod_installer.py:39`, `core/mod_deployer.py:108-109`, `core/ba2_packer.py:112`, `core/framework_state.py:17`.

---

## Lösungsplan

### Bug 1 + 2 — zentrale Helfer `host_open_path()` + `host_open_url()`

Neu in `anvil/core/subprocess_env.py`:

- `host_open_path(path)` — öffnet lokalen Ordner/Datei. Ersetzt ALLE `xdg-open <pfad>` und `QDesktopServices.openUrl(QUrl.fromLocalFile(...))`.
- `host_open_url(url)` — öffnet http(s)/nxm-URL. Ersetzt ALLE `QDesktopServices.openUrl(QUrl(...))`.

Beide MÜSSEN:
1. Bei Flatpak → `host_popen(["xdg-open", target], env=...)` (geht über `flatpak-spawn --host`).
2. Bei AppImage/sonst → `subprocess.Popen(["xdg-open", target], env=<vollständig bereinigte Env>)` mit Argument-Liste (kein `shell=True`, kein String-Concat — Leerzeichen sicher).
3. **Env-Bereinigung erweitern:** `clean_subprocess_env()` zusätzlich um `QT_PLUGIN_PATH`, `QT_QPA_PLATFORM_PLUGIN_PATH`, `GTK_PATH`, `GDK_PIXBUF_MODULE_FILE`, `GDK_PIXBUF_MODULEDIR`, `GIO_MODULE_DIR`, `PYTHONPATH`, `PYTHONHOME`, `GSETTINGS_SCHEMA_DIR` ergänzen. Für jede: `_ORIG` restaurieren falls vorhanden, sonst **löschen** (nur `LD_LIBRARY_PATH_ORIG` wird vom Bootloader gesetzt — alle anderen existieren nicht als `_ORIG` und müssen entfernt werden, der Host setzt sie selbst korrekt).
4. Existenz-/Leer-Check + try/except mit User-sichtbarer QMessageBox-Fehlermeldung (kein stiller Crash). Fallback-Opener: `gio open`, `kde-open5`, `kde-open` falls `xdg-open` fehlt.
5. `host_open_url` muss `nxm://`-Schema durchreichen, nicht nur http/https.

**Begründung Abweichung von der Qt-Standard-API:** `QDesktopServices.openUrl` kann KEINE bereinigte Env an den intern gestarteten Opener mitgeben → es vererbt zwangsläufig die verseuchte PyInstaller-Env. Daher der eigene Helper.

**ALLE umzustellenden Aufrufstellen (vollständig — atomare Umstellung):**

`QDesktopServices.openUrl(QUrl(...))` — URLs → `host_open_url`:
- `anvil/mainwindow.py:578`
- `anvil/mainwindow.py:586`
- `anvil/mainwindow.py:652`
- `anvil/mainwindow.py:654`
- `anvil/mainwindow.py:835`
- `anvil/mainwindow.py:5240`
- `anvil/widgets/game_panel.py:2534`
- `anvil/dialogs/reshade_wizard.py:169`
- `anvil/dialogs/collection_import_dialog.py:68`

`QDesktopServices.openUrl(QUrl.fromLocalFile(...))` — lokale Pfade → `host_open_path`:
- `anvil/widgets/game_panel.py:635`
- `anvil/widgets/game_panel.py:1950`
- `anvil/widgets/instance_manager_dialog.py:464`

`subprocess.Popen(["xdg-open", ...], env=clean_subprocess_env())` — lokale Pfade → `host_open_path`:
- `anvil/mainwindow.py:3369`
- `anvil/mainwindow.py:3376`
- `anvil/mainwindow.py:3385`
- `anvil/mainwindow.py:3394`
- `anvil/mainwindow.py:3409`
- `anvil/mainwindow.py:3416`
- `anvil/mainwindow.py:3425`
- `anvil/mainwindow.py:3433`
- `anvil/mainwindow.py:3440`
- `anvil/mainwindow.py:3447`
- `anvil/mainwindow.py:3454`
- `anvil/mainwindow.py:3462`
- `anvil/mainwindow.py:5418`
- `anvil/mainwindow.py:6539`
- `anvil/mainwindow.py:6636`
- `anvil/widgets/game_panel.py:2539`
- `anvil/widgets/game_panel.py:2541`
- `anvil/widgets/game_panel.py:2543`
- `anvil/widgets/settings_dialog.py:970`
- `anvil/widgets/settings_dialog.py:1040`
- `anvil/dialogs/mod_detail_dialog.py:495`
- `anvil/dialogs/mod_detail_dialog.py:644`
- `anvil/dialogs/mod_detail_dialog.py:837`
- `anvil/dialogs/mod_detail_dialog.py:1082`

`subprocess.Popen(["xdg-open", url], ...)` — URL-Sonderfall → `host_open_url`:
- `anvil/core/nexus_sso.py:165`

Summe ~35 Aufrufstellen in 7 Dateien. Nach Umbau: `QDesktopServices`/`QUrl`-Importe in betroffenen Dateien ggf. entfernbar (Lint prüfen). DEBUG-`print` in `_open_profile_folder` (`mainwindow.py:3420/3422`) entfernen.

Wiederverwendbares Vorbild: Steam-Start `game_panel.py:1636-1659` (`host_which` + `host_popen` + `clean_subprocess_env`).

### Bug 3 — konfigurierte mods/profiles-Pfade durchreichen

**KRITISCH: Default NICHT von `.mods` auf `mods` ändern!** Der versteckte Punkt-Prefix-Default ist korrekt und muss bleiben. Sonst verlieren alle bestehenden Instanzen ihre Mods (App schaut in nicht-existentes `mods/`, Daten liegen in `.mods/`). Der Fix ist NICHT "Default ändern", sondern "konfigurierte Pfade konsequent durchreichen".

Plan (Vorbild: `self._current_downloads_path` / `_open_downloads_folder`, `mainwindow.py:1200,1203,3431`):
1. In `load_instance` (`mainwindow.py:1196ff`) zwei neue Instanzvariablen analog `_current_downloads_path` einführen:
   - `self._current_mods_path = resolve_path(data.get("path_mods_directory", "%INSTANCE_DIR%/.mods"))`
   - `self._current_profiles_path = resolve_path(data.get("path_profiles_directory", "%INSTANCE_DIR%/.profiles"))`
2. Die hardcoded `instance_path / ".mods"` / `".profiles"` durch diese Variablen ersetzen — **vollständig/atomar**, sonst Daten-Inkonsistenz (z.B. Deploy aus `.mods`, Anzeige aus Custom-Pfad).
3. `scan_mods_directory` (`mod_entry.py:185, 220-221`) um Parameter `mods_dir`/`profiles_dir` erweitern und aufgelöste Pfade durchreichen statt intern hardcoden.
4. Core-Klassen, die selbst `.mods`/`.profiles` raten, müssen die aufgelösten Pfade als Parameter erhalten.

Hardcoded-Stellen (vollständige Liste für die atomare Umstellung):
- `.mods` in `mainwindow.py`: 1294, 3025, 3367, 3480, 3560, 3697, 3920, 4546, 5257, 5258, 5307, 5340, 5397, 5416, 5425, 5503
- `.profiles` in `mainwindow.py`: 1258, 1289, 3044, 3581, 3619, 3641, 3770, 3828, 3850, 5275, 5393, 6051, 6076, 6427, 6428
- Core: `mod_entry.py:220-221`, `mod_installer.py:39`, `mod_deployer.py:108-109`, `ba2_packer.py:112`, `framework_state.py:17`
- Hinweis: `game_panel.set_downloads_path(downloads_dir, mods_dir)` (`mainwindow.py:1204`) bekommt `mods_dir` bereits korrekt — Problem ist nur, dass `load_instance` es danach (Z.1294) wieder überschreibt.
- Tools (`tools/repair_mods.py`, `tools/check_mods.py`) sind separate Skripte, niedrigere Priorität.

---

## Risiken & Migration

- **Migrations-Risiko Bug 3 (KRITISCH):** Default-Pfad MUSS `.mods`/`.profiles` (mit Punkt) bleiben. Alt-Instanzen ohne `path_mods_directory` in `.anvil.ini` greifen auf den Default → bleibt `.mods`. Niemals den Default-Namen ändern.
- **Atomarität Bug 3:** Unvollständiger Fix führt zu Daten-Inkonsistenz (verschiedene Codepfade lesen aus verschiedenen Verzeichnissen). Alle ~30 Stellen müssen in einem Zug umgestellt werden.
- **Test-Matrix Bug 3:** mit (a) Default `.mods`/`.profiles` UND (b) abweichendem absoluten Pfad (z.B. `/mnt/gamingS/mods`) testen. Symlink-Deploy über Laufwerksgrenzen muss weiter funktionieren.
- **GC:** `subprocess.Popen(...)` fire-and-forget für xdg-open ist unkritisch. Im Helper KEIN `QProcess` als lokale Variable ohne gehaltene Referenz verwenden.
- **Edge Cases (aus Agent 3):**
  1. Kein `xdg-open`/Dateimanager → `FileNotFoundError` abfangen, QMessageBox, Fallback `gio open`/`kde-open5`/`kde-open`.
  2. Snap-confinement (separater Build) blockiert direktes xdg-open → Portal nötig; als bekannter Edge Case dokumentieren.
  3. `xdg-desktop-portal` fehlt → Fehlermeldung statt stiller Fehlschlag.
  4. Leerer/ungültiger Pfad → `if not path: return` + `Path.exists()`-Check VOR Aufruf.
  5. Pfad mit Leerzeichen → Argument-Liste statt Shell, niemals `shell=True`.
  6. Pfad existiert nicht mehr (Mod gelöscht) → Existenz-Check.
  7. Custom mods-Pfad auf anderem Mount (`/mnt/gamingS`) → absoluter Pfad muss korrekt durchgereicht werden.
  8. Alt-Instanz ohne Config-Pfad → Default `.mods`/`.profiles`.
  9. `nxm://`-URL → muss durchgereicht werden.
- **Flatpak:** `host_open_*` → `flatpak-spawn --host xdg-open` ruft den HOST-Opener → Portal. Pfad muss für Host sichtbar sein (`--filesystem`-Permission). `nexus_sso.py:165` wird durch Umstellung auf `host_open_url` automatisch Flatpak-tauglich.
- **AppImage-PATH/AppRun (Agent 3, niedrigere Prio):** sicherstellen, dass System-`xdg-open` Vorrang vor gebündelten Binaries hat. `libreadline`/`libtinfo` werden bereits aus dem Bundle entfernt (`build-appimage.sh:97-99`) — als Sicherheitsnetz behalten.

---

## Verwandte Funktionen (geprüft)

- `clean_subprocess_env()` / `clean_env()` (`subprocess_env.py:65,80`) → Fix nötig: ja, Env-Liste erweitern (QT_*/GTK_*/GIO_*/PYTHON*).
- `host_popen()` / `host_which()` / `is_flatpak()` (`subprocess_env.py:20,25,46`) → Fix nötig: nein, wiederverwenden.
- `_current_downloads_path` / `_open_downloads_folder` (`mainwindow.py:1200,1203,3431`) → Fix nötig: nein, ist das Vorbild für Bug 3.
- `set_downloads_path(downloads_dir, mods_dir)` (`game_panel`) → Fix nötig: nein, bekommt mods_dir bereits korrekt.
- `resolve_path()` / `_resolve()` / `_unresolve()` → Fix nötig: nein, für `%INSTANCE_DIR%`-Ersetzung wiederverwenden.

---

## ✅ Akzeptanz-Checkliste

- [ ] Wenn User im AppImage auf das Ordner-Icon/den "Mods-Ordner öffnen"-Button klickt, öffnet sich der Host-Dateimanager mit dem richtigen Ordner — ohne `GLIBC`/symbol-lookup-/`kde-open: /tmp/.mount_...`-Fehler im Terminal.
- [ ] Wenn User im AppImage auf eine Nexus-URL bzw. "Open Nexus Page" (Kontextmenü) klickt, öffnet sich der Host-Browser mit der korrekten URL.
- [ ] Wenn User im AppImage auf den Wiki- oder Issues-Link im Menü klickt, öffnet sich der Host-Browser.
- [ ] Wenn die App in Flatpak läuft und User einen Ordner-/URL-Button drückt, startet der Opener über `flatpak-spawn --host` und öffnet auf dem Host korrekt.
- [ ] Wenn User in einer Instanz mit Custom mods-Pfad (z.B. `/mnt/gamingS/mods`) einen Mod installiert, landet der Ordner unter `/mnt/gamingS/mods/<Name>` und NICHT in `.mods`.
- [ ] Wenn User einen Custom mods-Pfad gesetzt hat, scannt und zeigt Anvil die Mods aus diesem Pfad (nicht aus `.mods`) und Deploy nutzt denselben Pfad.
- [ ] Wenn User "Mods-Ordner öffnen" bzw. "Profil-Ordner öffnen" klickt, öffnet sich der konfigurierte mods- bzw. profiles-Pfad der Instanz.
- [ ] Wenn eine bestehende Instanz keinen abweichenden Pfad konfiguriert hat, verwendet Anvil weiterhin `.mods`/`.profiles` — keine Mod-Verluste, alles funktioniert unverändert (Migrationsschutz).
- [ ] Wenn `xdg-open` nicht gefunden wird, zeigt Anvil eine verständliche Fehlermeldung (QMessageBox) statt stillem Crash oder Traceback.
- [ ] Wenn User einen Ordner öffnet, dessen Pfad Leerzeichen enthält, öffnet der Dateimanager exakt diesen Ordner (kein Shell-Quoting-Fehler).
- [ ] Wenn User auf eine `nxm://`-URL klickt, wird das Schema an den Host-Handler durchgereicht.
- [ ] Alle ~35 bisherigen `QDesktopServices.openUrl(...)`- und rohen `subprocess.Popen(["xdg-open", ...])`-Aufrufe nutzen die neuen Helfer `host_open_path`/`host_open_url` (kein roher Aufruf mehr im Code).
- [ ] Der DEBUG-`print` in `_open_profile_folder` (`mainwindow.py:3420/3422`) ist entfernt.
- [ ] `restart.sh` startet ohne Fehler.
