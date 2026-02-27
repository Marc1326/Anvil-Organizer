# Security Audit Report — Widgets & Dialogs

**Datum:** 2026-02-25
**Scope:** `anvil/widgets/` (20 Dateien) + `anvil/dialogs/` (5 Dateien)
**Auditor:** Agent 2 (Security)
**Methode:** Statische Code-Analyse aller 25 Python-Dateien

---

## Zusammenfassung

| Severity | Anzahl |
|----------|--------|
| CRITICAL | 2      |
| HIGH     | 6      |
| MEDIUM   | 5      |
| LOW      | 4      |
| **Gesamt** | **17** |

---

## Findings

---

### [CRITICAL-01] Command Injection via subprocess.Popen mit xdg-open

- **Dateien & Zeilen:**
  - `anvil/widgets/game_panel.py:1150` — `subprocess.Popen(["xdg-open", first])`
  - `anvil/widgets/game_panel.py:1152` — `subprocess.Popen(["xdg-open", str(meta_path)])`
  - `anvil/widgets/game_panel.py:1154` — `subprocess.Popen(["xdg-open", str(Path(first).parent)])`
  - `anvil/dialogs/mod_detail_dialog.py:352` — `subprocess.Popen(["xdg-open", dirpath])`
  - `anvil/dialogs/mod_detail_dialog.py:545` — `subprocess.Popen(["xdg-open", dirpath])`
  - `anvil/dialogs/mod_detail_dialog.py:791` — `subprocess.Popen(["xdg-open", mod_path])`
  - `anvil/widgets/settings_dialog.py:790` — `subprocess.Popen(["xdg-open", str(path)])`
  - `anvil/widgets/settings_dialog.py:833` — `subprocess.Popen(["xdg-open", str(get_styles_dir())])`

- **Vulnerability Type:** Command Injection / Arbitrary File Open
- **Problem:**
  `subprocess.Popen(["xdg-open", path])` uebergibt Pfade direkt an xdg-open ohne jegliche Validierung. Da die Pfade teils aus .meta-Dateien (`first` in game_panel.py), teils aus QLineEdit-Feldern (mod_detail_dialog.py `current_path[0]`), teils aus dem Dateisystem stammen, koennte ein manipulierter Pfad oder eine manipulierte .meta-Datei dazu fuehren, dass xdg-open eine unerwartete URI/Datei oeffnet.

  Besonders kritisch in `game_panel.py:1150`: `first` ist ein Pfad aus `_get_dl_archive_path()`, der aus den Tabellendaten stammt. Wenn ein Archiv-Dateiname boesartig ist (z.B. ein Symlink oder ein Pfad mit `..`-Komponenten), koennte xdg-open unerwartete Verzeichnisse/Dateien oeffnen.

  Auf Linux-Systemen interpretiert xdg-open auch URLs (`http://`, `ftp://` etc.) — ein Pfad der wie eine URL aussieht koennte einen Browser oeffnen.

- **Code-Snippet (game_panel.py:1149-1154):**
  ```python
  elif chosen == act_open:
      subprocess.Popen(["xdg-open", first])
  elif chosen == act_meta:
      subprocess.Popen(["xdg-open", str(meta_path)])
  elif chosen == act_show:
      subprocess.Popen(["xdg-open", str(Path(first).parent)])
  ```

- **Empfehlung:**
  1. Alle Pfade vor der Uebergabe an xdg-open mit `Path.resolve()` aufloesen und pruefen, ob sie innerhalb des erwarteten Verzeichnisses liegen (z.B. Downloads-Ordner, Mods-Ordner).
  2. Pruefen ob der Pfad tatsaechlich existiert (`os.path.exists()`).
  3. Sicherstellen dass der Pfad keine URL-Schemata enthaelt (kein `://`).
  4. Alternativ `QDesktopServices.openUrl(QUrl.fromLocalFile(path))` verwenden, da dies nur lokale Dateien oeffnet.
  5. Eine zentrale Hilfsfunktion `safe_open_path(path, allowed_base)` erstellen, die alle Validierung buendelt.

---

### [CRITICAL-02] URL-Injection via Nexus-Mod-ID aus .meta-Datei

- **Datei:** `anvil/widgets/game_panel.py:1147-1148`
- **Vulnerability Type:** URL Injection / Open Redirect
- **Problem:**
  Die `mod_id` wird aus einer .meta-Datei gelesen (`_read_meta_mod_id()`, Zeile 952-965) und direkt in eine URL eingebaut:

  ```python
  QDesktopServices.openUrl(
      QUrl(f"https://www.nexusmods.com/{game}/mods/{mod_id}"))
  ```

  Die .meta-Datei ist eine configparser-INI-Datei, die vom Benutzer oder von einem Mod-Download-Tool geschrieben wird. Wenn `mod_id` manipuliert wird (z.B. `../../?redirect=evil.com` oder `1234#<script>`), koennte die URL manipuliert werden. Besonders kritisch: `game` kommt aus `self._current_short_name`, was ebenfalls aus Plugin-Daten stammt.

  Ein konkretes Szenario: Ein boesartiger Mod-Autor liefert eine .meta-Datei mit `modID = 1234/../../../dangerous-site.com` oder aehnlichem Payload.

- **Code-Snippet (_read_meta_mod_id, Zeile 952-965):**
  ```python
  def _read_meta_mod_id(self, archive_path: str) -> str | None:
      meta = Path(archive_path + ".meta")
      if not meta.is_file():
          return None
      cp = configparser.ConfigParser()
      try:
          cp.read(str(meta), encoding="utf-8")
      except Exception:
          return None
      mod_id = cp.get("General", "modID", fallback=None)
      if mod_id and mod_id.strip():
          return mod_id.strip()  # Keine Validierung!
      return None
  ```

- **Empfehlung:**
  1. `mod_id` MUSS als reine Ganzzahl validiert werden: `if mod_id.isdigit(): ...`
  2. `game` (short name) sollte nur alphanumerische Zeichen enthalten: Regex-Check gegen `^[a-zA-Z0-9_-]+$`
  3. Die URL vor dem Oeffnen mit `QUrl(url)` konstruieren und `isValid()` pruefen.

---

### [HIGH-01] HTML-Injection in QLabel via Plugin-Nexus-URL

- **Datei:** `anvil/widgets/settings_dialog.py:769-770`
- **Vulnerability Type:** HTML/Script Injection in Qt Rich Text
- **Problem:**
  Der Nexus-URL wird aus Plugin-Attributen konstruiert und direkt in ein QLabel mit HTML gesetzt:

  ```python
  nexus_id = getattr(plugin, "GameNexusName", "") or getattr(plugin, "GameShortName", "")
  if nexus_id:
      url = f"https://www.nexusmods.com/{nexus_id}"
      self._pl_nexus.setText(f'<a href="{url}" style="color:#4FC3F7;">{url}</a>')
  ```

  Da `setOpenExternalLinks(True)` auf Zeile 603 gesetzt ist, wuerde ein Klick auf den Link diesen direkt im Browser oeffnen. Wenn ein Plugin-Autor `GameNexusName` mit einem boesartigen Wert belegt (z.B. `" onclick="alert(1)" href="javascript:void`), koennte HTML-Injection im Label stattfinden.

  Qt's Rich Text Engine unterstuetzt zwar kein JavaScript, aber ein manipulierter `href` koennte auf eine Phishing-Seite zeigen, wenn `nexus_id` z.B. `"><a href="https://evil.com">Click</a><a href="` enthaelt.

- **Empfehlung:**
  1. `nexus_id` mit Regex validieren: `^[a-zA-Z0-9_-]+$`
  2. HTML-Entitaeten escapen bevor sie in Rich Text eingebaut werden (z.B. `html.escape()`).
  3. `QUrl` konstruieren und `isValid()` pruefen bevor der Link angezeigt wird.

---

### [HIGH-02] Beliebige Datei-Schreiboperationen aus User-Editor

- **Dateien:**
  - `anvil/dialogs/mod_detail_dialog.py:327-333` (Textfiles-Tab)
  - `anvil/dialogs/mod_detail_dialog.py:515-521` (INI-Tab)

- **Vulnerability Type:** Arbitrary File Write
- **Problem:**
  Der Benutzer kann Text in einem Editor bearbeiten und ueber "Save" speichern. Der Ziel-Pfad (`current_path[0]`) wird aus `item.data(Qt.ItemDataRole.UserRole)` gelesen und ohne Validierung zum Schreiben verwendet:

  ```python
  def on_save():
      path = current_path[0]
      if not path:
          return
      try:
          with open(path, "w", encoding="utf-8") as f:
              f.write(editor.toPlainText())
  ```

  Obwohl die Dateien aus einem Mod-Verzeichnis-Scan stammen, besteht theoretisch das Risiko, dass ein manipuliertes Mod-Archiv Symlinks enthaelt, die `current_path[0]` auf eine Datei ausserhalb des Mod-Verzeichnisses zeigen lassen. Der Benutzer wuerde dann unwissentlich eine System-Datei ueberschreiben.

- **Empfehlung:**
  1. Vor dem Schreiben pruefen: `Path(path).resolve().is_relative_to(mod_root_path)`
  2. Symlinks im Mod-Verzeichnis nicht folgen oder warnen.
  3. Backup der Original-Datei erstellen bevor sie ueberschrieben wird.

---

### [HIGH-03] Datei-Verschiebung via shutil.move ohne Pfad-Validierung

- **Datei:** `anvil/dialogs/mod_detail_dialog.py:708-713, 726-731`
- **Vulnerability Type:** Path Traversal / Arbitrary File Move
- **Problem:**
  In der Optional-ESPs-Funktionalitaet werden Dateien zwischen `mod_root` und `optional_dir` verschoben:

  ```python
  def move_to_optional():
      for item in selected:
          src = Path(item.data(Qt.ItemDataRole.UserRole))
          dst = optional_dir / src.name
          try:
              shutil.move(str(src), str(dst))
          except OSError:
              pass
  ```

  `src` kommt aus den UserRole-Daten der List-Items. `src.name` wird fuer `dst` verwendet, was path traversal via `..` im Dateinamen verhindern sollte — ABER `src` selbst wird direkt als Quellpfad verwendet. Wenn ein Mod-Archiv eine Datei mit einem symbolischen Link als UserRole-Daten enthaelt, koennte `shutil.move` eine Datei von einem beliebigen Ort verschieben.

- **Empfehlung:**
  1. `src.resolve()` verwenden und pruefen ob es innerhalb von `mod_root` liegt.
  2. Pruefen ob `src` ein Symlink ist (`src.is_symlink()`) und warnen.

---

### [HIGH-04] QProcess.startDetached fuer App-Neustart

- **Datei:** `anvil/widgets/settings_dialog.py:912`
- **Vulnerability Type:** Arbitrary Process Execution
- **Problem:**
  ```python
  QProcess.startDetached(sys.executable, sys.argv)
  ```

  `sys.executable` und `sys.argv` werden direkt verwendet. Wenn die App ueber einen manipulierten Pfad gestartet wurde (z.B. durch einen Angreifer der den Python-Interpreter oder die Argumente kontrolliert), wuerde der Neustart den boesartigen Prozess erneut starten. Dies ist ein geringes Risiko da es eine lokale Privilege-Escalation-Situation voraussetzt, aber es ist dennoch erwaehnenswert.

  Zusaetzlich: `sys.argv` koennte manipulierte Kommandozeilenargumente enthalten.

- **Empfehlung:**
  1. `sys.executable` gegen einen erwarteten Python-Pfad validieren.
  2. `sys.argv[0]` gegen den bekannten Anwendungspfad pruefen.
  3. Alternativ einen festen, bekannten Startbefehl verwenden statt `sys.argv` blind zu kopieren.

---

### [HIGH-05] QProcess.startDetached fuer Steam-Launch mit Plugin-Daten

- **Datei:** `anvil/widgets/game_panel.py:529-538`
- **Vulnerability Type:** Argument Injection
- **Problem:**
  ```python
  steam_bin = shutil.which("steam")
  if steam_bin:
      steam_id = plugin.GameSteamId
      if isinstance(steam_id, list):
          steam_id = steam_id[0]
      args = ["-applaunch", str(steam_id)]
      if hasattr(plugin, "GameLaunchArgs"):
          args.extend(plugin.GameLaunchArgs)
      success, pid = QProcess.startDetached(steam_bin, args)
  ```

  `GameSteamId` und `GameLaunchArgs` kommen aus Plugin-Klassen. Wenn ein boesartiges Plugin installiert wird, koennte es beliebige Argumente an Steam uebergeben, einschliesslich `--exec` oder anderer gefaehrlicher Steam-CLI-Optionen. `shutil.which("steam")` ist sicher (findet den echten Steam-Binary), aber die Argumente sind nicht validiert.

- **Empfehlung:**
  1. `GameSteamId` MUSS als Ganzzahl validiert werden: `int(steam_id)`
  2. `GameLaunchArgs` sollte gegen eine Allowlist geprueft werden (keine `-exec`, `--exec`, etc.).
  3. Plugin-Daten generell als untrusted behandeln, besonders wenn Community-Plugins unterstuetzt werden.

---

### [HIGH-06] Nexus API Key im Klartext in QSettings gespeichert

- **Datei:** `anvil/widgets/settings_dialog.py:969, 985`
- **Vulnerability Type:** Sensitive Data Exposure
- **Problem:**
  ```python
  settings.setValue("nexus/api_key", api_key)
  # und:
  settings.setValue("nexus/api_key", key.strip())
  ```

  Der Nexus API Key wird im Klartext in QSettings gespeichert. Auf Linux speichert QSettings standardmaessig in `~/.config/AnvilOrganizer/...` als INI-Datei. Jeder Prozess mit Lesezugriff auf das Home-Verzeichnis kann den Key auslesen. Der Key ermoeglicht vollen Zugriff auf das Nexus-Konto des Benutzers.

- **Empfehlung:**
  1. Den API Key verschluesselt speichern (z.B. via `keyring` Python-Paket, das den System-Keyring nutzt).
  2. Alternativ die Dateiberechtigungen der Config-Datei auf `0600` setzen.
  3. Mindestens: Den Key beim Anzeigen maskieren (nur letzte 4 Zeichen zeigen).
  4. MO2-Referenz: MO2 speichert den Key ebenfalls in einer INI-Datei, aber das ist kein Grund es nicht besser zu machen.

---

### [MEDIUM-01] Fehlende Pfad-Validierung bei Instanz-Erstellung

- **Datei:** `anvil/widgets/instance_wizard.py:602-608, 675-683`
- **Vulnerability Type:** Path Traversal
- **Problem:**
  Benutzerdefinierte Pfade fuer Mods, Downloads und Overwrite werden ohne Validierung an `create_instance()` weitergegeben:

  ```python
  if self._advanced_paths_cb.isChecked():
      if self._mods_path_edit.text().strip():
          mods_path = self._mods_path_edit.text().strip()
      if self._downloads_path_edit.text().strip():
          downloads_path = self._downloads_path_edit.text().strip()
  ```

  Obwohl der Benutzer auch ueber `QFileDialog.getExistingDirectory()` Pfade waehlen kann, ist das QLineEdit-Feld frei editierbar. Ein Pfad wie `/etc/` oder `/` koennte als Mod-Verzeichnis gesetzt werden, was spaeter zu unerwarteten Datei-Operationen fuehrt.

- **Empfehlung:**
  1. Pruefen ob der Pfad ein gueltiges, beschreibbares Verzeichnis ist.
  2. Pruefen ob der Pfad nicht auf ein System-Verzeichnis zeigt (Blocklist: `/etc`, `/usr`, `/bin`, `/boot`, `/dev`, `/proc`, `/sys`).
  3. Warnung anzeigen wenn der Pfad ausserhalb des Home-Verzeichnisses liegt.

---

### [MEDIUM-02] Fehlende Pfad-Validierung bei Instanz-Pfad-Aenderungen

- **Datei:** `anvil/widgets/settings_dialog.py:884-891`
- **Vulnerability Type:** Path Traversal / Configuration Manipulation
- **Problem:**
  ```python
  idata["path_downloads_directory"] = _unresolve(self._le_downloads.text())
  idata["path_mods_directory"] = _unresolve(self._le_mods.text())
  idata["path_profiles_directory"] = _unresolve(self._le_profiles.text())
  idata["path_overwrite_directory"] = _unresolve(self._le_overwrite.text())
  idata["game_path"] = self._le_game_path.text()
  ```

  Die Pfade aus QLineEdit-Feldern werden direkt in die Instanz-Konfiguration geschrieben. Die `_unresolve()`-Funktion (Zeile 876-882) wandelt nur absolute Pfade in relative um, fuehrt aber keine Sicherheitspruefung durch. Ein Benutzer koennte hier beliebige Pfade eintragen.

- **Empfehlung:**
  1. Gleiche Validierung wie bei MEDIUM-01.
  2. `game_path` sollte gegen das bekannte Spielverzeichnis validiert werden.

---

### [MEDIUM-03] Datei-Loeschung ohne Pfad-Validierung

- **Datei:** `anvil/widgets/game_panel.py:1001-1011, 1166-1176`
- **Vulnerability Type:** Arbitrary File Deletion
- **Problem:**
  ```python
  for p in paths:
      try:
          os.remove(p)
      except OSError:
          pass
      meta = p + ".meta"
      try:
          os.remove(meta)
      except OSError:
          pass
  ```

  `paths` stammt aus `_get_dl_archive_path(row)`, das den Pfad aus der Download-Tabelle liest. Obwohl eine Bestaetigungsdialog angezeigt wird, wird der Pfad selbst nicht validiert. Wenn die Tabellendaten manipuliert werden koennten (z.B. durch eine boesartige .meta-Datei die den Dateinamen aendert), koennten beliebige Dateien geloescht werden.

  Es fehlt eine Pruefung ob die Pfade innerhalb des Downloads-Verzeichnisses liegen.

- **Empfehlung:**
  1. Vor dem Loeschen: `Path(p).resolve().is_relative_to(downloads_dir)` pruefen.
  2. Keine Loeschung von Symlinks oder Pfaden ausserhalb des erwarteten Bereichs.

---

### [MEDIUM-04] QDesktopServices.openUrl mit QLineEdit-Pfaden

- **Datei:** `anvil/widgets/instance_manager_dialog.py:451-463`
- **Vulnerability Type:** Local File Access / Information Disclosure
- **Problem:**
  ```python
  def _on_explore(self, path_type: str) -> None:
      if path_type == "location":
          path = self._location_edit.text()
      elif path_type == "base":
          path = self._base_edit.text()
      elif path_type == "game":
          path = self._game_path_edit.text()
      if path and path != "\u2014":
          QDesktopServices.openUrl(QUrl.fromLocalFile(path))
  ```

  Die QLineEdits sind zwar als readOnly gesetzt, aber der Pfad kommt aus Instanz-Daten. Wenn die Instanz-Konfiguration manipuliert wird, koennte ein beliebiger Pfad im Dateisystem geoeffnet werden. `QUrl.fromLocalFile()` ist sicherer als `QUrl()` da es nur lokale Pfade oeffnet, aber es validiert nicht ob der Pfad sinnvoll ist.

- **Empfehlung:**
  1. Pruefen ob der Pfad existiert und ein Verzeichnis ist.
  2. Pruefen ob der Pfad innerhalb erwarteter Bereiche liegt.

---

### [MEDIUM-05] Toast-Widget akzeptiert beliebigen Text ohne Escaping

- **Datei:** `anvil/widgets/toast.py:15-16`
- **Vulnerability Type:** Potential Rich Text Injection
- **Problem:**
  ```python
  def __init__(self, parent, message: str, duration: int = 3000, clickable: bool = False):
      super().__init__(message, parent)
  ```

  Der `message`-Parameter wird direkt an den QLabel-Konstruktor uebergeben. QLabel erkennt automatisch ob Text HTML enthaelt (wenn er mit `<` beginnt). Wenn `message` aus einer externen Quelle stammt (z.B. einem Mod-Namen oder einer Server-Antwort), koennte HTML injiziert werden.

  Qt's automatische HTML-Erkennung (`Qt::AutoText`) bedeutet: Wenn der Text wie HTML aussieht, wird er als HTML gerendert.

- **Empfehlung:**
  1. `self.setTextFormat(Qt.TextFormat.PlainText)` explizit setzen.
  2. Alternativ: `html.escape(message)` vor der Uebergabe.
  3. Dies gilt auch fuer das LogPanel (`anvil/widgets/log_panel.py:69`), wo QLabel-Messages direkt gesetzt werden.

---

### [LOW-01] Clipboard-Operationen ohne Fehlerbehandlung

- **Datei:** `anvil/widgets/donate_dialog.py:183-190`
- **Vulnerability Type:** Clipboard Exposure (Geringes Risiko)
- **Problem:**
  ```python
  def _copy():
      clipboard = QGuiApplication.clipboard()
      if clipboard:
          clipboard.setText(addr)
  ```

  Die Clipboard-Operation selbst ist harmlos (schreibt eine hardcoded Crypto-Adresse). Allerdings gibt es keine Pruefung ob ein Clipboard-Hijacker aktiv ist. Unter Linux (X11) kann jeder Prozess die Zwischenablage mitlesen. Die Crypto-Adressen sind aber ohnehin im Code sichtbar.

- **Empfehlung:**
  1. Benutzer darauf hinweisen, die eingefuegte Adresse zu ueberpruefen.
  2. Kein unmittelbarer Code-Fix noetig — eher ein UX-Hinweis.

---

### [LOW-02] Import innerhalb von Funktionen (QTimer in donate_dialog.py)

- **Datei:** `anvil/widgets/donate_dialog.py:189`
- **Vulnerability Type:** Code Quality / Nicht sicherheitsrelevant
- **Problem:**
  ```python
  from PySide6.QtCore import QTimer
  QTimer.singleShot(2000, lambda: copy_btn.setText("..."))
  ```

  QTimer wird innerhalb einer verschachtelten Funktion importiert statt am Datei-Anfang. Dies ist kein Sicherheitsproblem, aber koennte zu Import-Fehlern fuehren wenn das Modul nicht verfuegbar ist. Da PySide6 bereits oben importiert wird, ist QTimer garantiert verfuegbar.

- **Empfehlung:**
  Import an den Datei-Anfang verschieben.

---

### [LOW-03] Backup-Loeschung folgt potentiell Symlinks

- **Datei:** `anvil/dialogs/backup_dialog.py:330-331`
- **Vulnerability Type:** Symlink Following
- **Problem:**
  ```python
  backup_path.unlink()
  ```

  `backup_path` stammt aus einem Dateisystem-Scan. `Path.unlink()` loescht die Datei auf die der Pfad zeigt — bei einem Symlink wird der Link geloescht, nicht das Ziel. Allerdings koennte ein boesartig platzierter Symlink im Backup-Verzeichnis (falls ein Angreifer Schreibzugriff hat) dazu fuehren, dass der Benutzer denkt er loescht ein Backup, waehrend eigentlich etwas anderes passiert.

  Geringes Risiko, da ein Angreifer mit Schreibzugriff auf das Backup-Verzeichnis bereits viel Schaden anrichten koennte.

- **Empfehlung:**
  1. Vor dem Loeschen pruefen: `not backup_path.is_symlink()`
  2. Pfad validieren: `backup_path.resolve().is_relative_to(expected_backup_dir)`

---

### [LOW-04] Fehlende Input-Laengen-Begrenzung bei Rename/Create-Operationen

- **Dateien:**
  - `anvil/widgets/instance_manager_dialog.py` — `_on_rename()` via `get_text_input()`
  - `anvil/widgets/instance_wizard.py` — Instanz-Name aus QLineEdit
  - `anvil/widgets/category_dialog.py` — Kategorie-Namen via `get_text_input()`

- **Vulnerability Type:** Resource Exhaustion (Geringes Risiko)
- **Problem:**
  Benutzereingaben fuer Namen (Instanz, Kategorie, Profil) werden nicht auf Laenge begrenzt. Ein extrem langer Name koennte zu Problemen beim Speichern (Dateisystem-Laengenlimits), bei der Anzeige (UI-Overflow) oder beim Laden fuehren.

- **Empfehlung:**
  1. `QLineEdit.setMaxLength(255)` fuer alle Name-Eingabefelder.
  2. Oder Validierung in `get_text_input()` zentral einbauen.

---

## Nicht-betroffene Bereiche (Entwarnung)

Die folgenden Dateien wurden geprueft und enthalten **keine relevanten Sicherheitsprobleme**:

| Datei | Begruendung |
|-------|-------------|
| `anvil/widgets/__init__.py` | Nur Imports, kein ausführbarer Code |
| `anvil/widgets/collapsible_bar.py` | QSettings-Nutzung mit festen Keys, kein User-Input |
| `anvil/widgets/filter_chip.py` | Einfacher QPushButton, keine Sicherheitsrelevanz |
| `anvil/widgets/flow_layout.py` | Custom QLayout, rein layouttechnisch |
| `anvil/widgets/executables_dialog.py` | Placeholder mit hardcoded Werten |
| `anvil/widgets/profile_dialog.py` | Placeholder Dialog |
| `anvil/widgets/status_bar.py` | Nur tr()-Strings in QLabel, keine externen Daten |
| `anvil/widgets/mod_list.py` | Drag&Drop mit Datei-Erweiterungs-Validierung vorhanden |
| `anvil/widgets/bg3_mod_list.py` | UUID-Parsing mit try/except, Erweiterungs-Validierung vorhanden |
| `anvil/dialogs/__init__.py` | Nur Re-Exports |
| `anvil/dialogs/query_overwrite_dialog.py` | Einfacher Auswahl-Dialog, Mod-Name via tr() |
| `anvil/dialogs/quick_install_dialog.py` | Mod-Name via QComboBox, wird stripped, geringes Risiko |

---

## Architektur-Beobachtungen

### Positiv:
1. **xdg-open als Liste:** `subprocess.Popen(["xdg-open", path])` verwendet eine Liste statt einen String — das verhindert Shell-Injection (kein `shell=True`).
2. **QFileDialog:** Wird korrekt verwendet fuer Ordner-Auswahl.
3. **Read-Only QLineEdits:** Pfad-Anzeigen sind meistens readOnly gesetzt.
4. **Exception Handling:** Die meisten File-Operationen sind in try/except gekapselt.
5. **Confirmation Dialogs:** Loeschvorgaenge zeigen immer einen Bestaetigungsdialog.

### Negativ:
1. **Keine zentrale Pfad-Validierung:** Jede Datei macht eigene ad-hoc-Pruefungen (oder keine).
2. **Keine zentrale "open in file manager"-Funktion:** subprocess.Popen mit xdg-open wird an 8+ Stellen direkt aufgerufen.
3. **Keine Eingabe-Sanitierung:** Weder HTML-Escaping noch Pfad-Normalisierung ist zentral implementiert.
4. **API Key im Klartext:** Standard-Qt-Pattern, aber fuer einen Mod Manager mit Nexus-Integration verbesserungswuerdig.

---

## Prioritaeten fuer Fixes

| Prioritaet | Finding | Aufwand |
|------------|---------|---------|
| 1 (sofort) | CRITICAL-02: mod_id Validierung | 5 min — `.isdigit()` Check |
| 2 (sofort) | HIGH-01: HTML-Escape in Plugin-Nexus-URL | 10 min — `html.escape()` |
| 3 (bald) | CRITICAL-01: Zentrale `safe_open_path()` Funktion | 30 min — 1 Funktion, 8 Callsites |
| 4 (bald) | HIGH-02/03: Pfad-Validierung bei File-Write/Move | 20 min — `is_relative_to()` Checks |
| 5 (bald) | HIGH-05: Steam-Argument-Validierung | 10 min — `int()` Cast fuer SteamId |
| 6 (mittel) | MEDIUM-05: PlainText fuer Toast/Log | 5 min — `setTextFormat()` |
| 7 (mittel) | MEDIUM-01/02: Pfad-Validierung bei Instance-Erstellung | 20 min |
| 8 (mittel) | MEDIUM-03: Download-Loeschung mit Pfad-Check | 10 min |
| 9 (spaeter) | HIGH-06: API Key verschluesselt speichern | 1-2 Std. — keyring Integration |
| 10 (spaeter) | HIGH-04: Neustart-Validierung | 10 min |
| 11 (optional) | LOW-01 bis LOW-04 | 15 min |

---

## Ergebnis

**NEEDS FIXES** — 2 CRITICAL und 6 HIGH Findings erfordern Korrekturen vor einem Release. Die CRITICAL-Findings (URL-Injection via .meta-Datei und fehlende Pfad-Validierung bei xdg-open) sind mit geringem Aufwand behebbar und sollten priorisiert werden.

Die Gesamtarchitektur ist solide (kein `shell=True`, keine SQL-Injection, keine Web-Endpunkte), aber die fehlende zentrale Validierungsschicht fuer Pfade und externe Daten (.meta-Dateien, Plugin-Attribute) stellt ein systematisches Risiko dar.
