# Konsolidierter Security Audit Report — Anvil Organizer

**Datum:** 2026-02-25
**Scope:** Vollstaendiges Codebase-Audit (anvil/core/, anvil/widgets/, anvil/dialogs/, anvil/plugins/, anvil/stores/)
**Gepruefte Dateien:** 71 Python-Dateien (ca. 10.000+ Zeilen)
**Quellen:** 3 Teil-Reports von spezialisierten Audit-Agents

---

## Executive Summary

**Gesamtbewertung:** HOCH

Der Anvil Organizer weist mehrere sicherheitsrelevante Schwachstellen auf, von denen zwei als CRITICAL eingestuft werden. Die kritischsten Probleme betreffen die fehlende Validierung bei der Extraktion von Mod-Archiven (ZipSlip) und das unkontrollierte Laden von User-Plugins ohne Signatur-Pruefung. Beide Schwachstellen koennten in Kombination zur Ausfuehrung von beliebigem Code fuehren.

Die Gesamtarchitektur ist grundsaetzlich solide: Es wird kein `shell=True` bei subprocess verwendet, keine unsichere Deserialisierung (kein pickle/eval/exec auf User-Daten), keine hartkodierten Credentials, und die API-Kommunikation laeuft ausschliesslich ueber HTTPS mit TLS-Validierung. Jedoch fehlt eine **zentrale Validierungsschicht** fuer Pfade und externe Daten, was zu einem systematischen Muster von Path-Traversal-Schwachstellen fuehrt.

Fuer ein Pre-Release muessen mindestens die CRITICAL- und HIGH-Findings behoben werden.

### Findings nach Schweregrad

| Schweregrad | Anzahl |
|-------------|--------|
| CRITICAL    | 2      |
| HIGH        | 9      |
| MEDIUM      | 10     |
| LOW         | 7      |
| **Gesamt**  | **28** |

### Top 5 Prioritaeten

1. **ZipSlip beheben** (CRITICAL) — Gemeinsame sichere Extraktionsfunktion fuer ZIP/RAR/7z schreiben, die alle Pfade vor dem Entpacken validiert. Betrifft `mod_installer.py` und `bg3_mod_installer.py`.
2. **User-Plugin-Sicherheit** (CRITICAL) — Warnung im UI anzeigen wenn User-Plugins geladen werden. Langfristig: Signatur-Pruefung oder explizite Aktivierung.
3. **Zentrale Pfad-Validierung** (HIGH) — Eine `safe_path(target, allowed_base)` Hilfsfunktion erstellen und an allen 10+ Stellen verwenden, die Pfade aus externen Quellen (Manifeste, .meta-Dateien, Plugin-Attribute, QLineEdits) verarbeiten.
4. **API-Key sicher speichern** (HIGH) — Migration auf `keyring`/SecretService oder mindestens Datei-Berechtigungen 0o600 fuer die QSettings-Datei.
5. **defusedxml verwenden** (HIGH) — Alle `xml.etree.ElementTree`-Aufrufe durch `defusedxml` ersetzen, um Billion-Laughs-Angriffe zu verhindern.

---

## Findings nach Kategorie

### Kategorie: Path Traversal / ZipSlip

Die haeufigste Schwachstellenklasse im Projekt. **9 Findings** betreffen fehlende Pfad-Validierung in verschiedenen Kontexten: Archiv-Extraktion, Manifest-basierte Datei-Operationen, Benutzer-Eingaben und Plugin-Daten. Die Grundursache ist immer dieselbe: Pfade aus externen Quellen werden ohne `.resolve()` + `is_relative_to()` Pruefung verwendet.

Betroffene Findings: C-01, H-02, H-03, H-05, H-06, M-01, M-02, M-04, L-04

### Kategorie: Arbitrary Code Execution

Ein Finding betrifft das unkontrollierte Laden von Python-Plugins aus einem User-beschreibbaren Verzeichnis. In Kombination mit ZipSlip koennte ein Angreifer beliebigen Code einschleusen.

Betroffene Findings: C-02

### Kategorie: Credential/Information Exposure

Der Nexus API-Key wird im Klartext gespeichert und koennte in Fehlermeldungen auftauchen. Debug-Print-Statements in Produktionscode koennten zusaetzlich Informationen preisgeben.

Betroffene Findings: H-01, H-08, L-05

### Kategorie: Command Injection / Argument Injection

Pfade und Plugin-Daten werden ohne Validierung an externe Programme (xdg-open, Steam, Desktop-Entry Exec-Zeile) uebergeben. Obwohl `shell=True` nirgends verwendet wird (was direkte Shell-Injection verhindert), bleiben Risiken durch Argument-Injection und URL-Interpretation.

Betroffene Findings: H-04, H-07, H-09, M-07

### Kategorie: XML/Deserialisierung

XML-Dateien aus Mod-Archiven werden ohne defusedxml verarbeitet, was sie anfaellig fuer Billion-Laughs-Angriffe macht. LZ4-Decompression ohne Groessenlimit ist ein weiterer DoS-Vektor.

Betroffene Findings: H-03, M-05

### Kategorie: Denial of Service

WebSocket-Implementierung ohne Laengenlimit und mit rekursivem Empfang, LZ4-Decompression-Bombs, VDF-Parser ohne Eingabebegrenzung.

Betroffene Findings: M-05, M-06, M-08, L-02, L-06

### Kategorie: Race Conditions (TOCTOU)

Symlink-Operationen im Deployer und Instance-Erstellung mit Check-then-Act Pattern.

Betroffene Findings: M-03, L-01

### Kategorie: HTML/URL-Injection

Plugin-Daten und .meta-Dateien werden ohne Escaping in HTML-Labels und URLs eingebaut.

Betroffene Findings: H-04, M-09

### Kategorie: Unsichere Temp-Dateien

Temp-Verzeichnisse in /tmp/ mit potentiellen Berechtigungsproblemen bei den extrahierten Dateien.

Betroffene Findings: M-10

---

## Alle Findings (dedupliziert, nach Schweregrad sortiert)

---

### CRITICAL

#### C-01: ZipSlip — Path Traversal bei Archiv-Extraktion
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_installer.py:348-349`
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/bg3_mod_installer.py:895-896`
- **Typ:** Path Traversal / ZipSlip (CWE-22)
- **Beschreibung:** `zipfile.ZipFile.extractall()` wird an zwei Stellen ohne Validierung der Archiv-Eintraege aufgerufen. Ein boesartig praepariertes ZIP-Archiv kann Eintraege mit relativen Pfaden wie `../../.bashrc` oder `../../.anvil-organizer/plugins/games/evil.py` enthalten, die Dateien AUSSERHALB des Zielverzeichnisses schreiben. Da Mod-Archive von Drittanbieter-Webseiten (Nexus Mods, ModDB, etc.) heruntergeladen werden, ist dies ein realistischer Angriffsvektor. In Kombination mit C-02 (User-Plugin-Laden) koennte ein Angreifer beliebigen Python-Code einschleusen.
- **Code:**
  ```python
  # mod_installer.py:348-349
  with zipfile.ZipFile(archive, "r") as zf:
      zf.extractall(dest)  # UNSICHER: keine Pfad-Validierung

  # bg3_mod_installer.py:895-896
  with zipfile.ZipFile(archive_path, "r") as zf:
      zf.extractall(tmp)  # UNSICHER: keine Pfad-Validierung
  ```
- **Empfehlung:** Gemeinsame sichere Extraktionsfunktion in einem Utility-Modul erstellen:
  ```python
  def safe_extract_zip(archive: Path, dest: Path) -> None:
      dest_resolved = dest.resolve()
      with zipfile.ZipFile(archive, "r") as zf:
          for info in zf.infolist():
              target = (dest / info.filename).resolve()
              if not target.is_relative_to(dest_resolved):
                  raise ValueError(f"ZipSlip detected: {info.filename}")
          zf.extractall(dest)
  ```
- **Quelle:** Agent 1 (Finding 1+2), Agent 3 (Finding 1)

---

#### C-02: Dynamisches Code-Laden aus User-Plugin-Verzeichnis ohne Validierung
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/plugins/plugin_loader.py:116` (ensure_user_plugin_dir)
  - `/home/mob/Projekte/Anvil Organizer/anvil/plugins/plugin_loader.py:155-165` (exec_module)
- **Typ:** Arbitrary Code Execution (CWE-94)
- **Beschreibung:** Der PluginLoader laedt und fuehrt beliebige Python-Dateien aus `~/.anvil-organizer/plugins/games/` aus. Es gibt keine Signatur-Pruefung, kein Sandboxing und keine Validierung. Ein Angreifer, der Schreibzugriff auf das Home-Verzeichnis hat (z.B. durch ZipSlip/C-01), kann beliebigen Python-Code als Plugin einschleusen. Die Kombination aus C-01 und C-02 ergibt einen vollstaendigen Remote-Code-Execution-Vektor: Ein boesartiges Mod-Archiv schreibt via ZipSlip ein Python-Script ins Plugin-Verzeichnis, das beim naechsten App-Start automatisch ausgefuehrt wird.
- **Code:**
  ```python
  # plugin_loader.py:155-165
  spec = importlib.util.spec_from_file_location(module_name, py_file)
  module = importlib.util.module_from_spec(spec)
  sys.modules[module_name] = module
  spec.loader.exec_module(module)  # beliebiger Code wird ausgefuehrt
  ```
- **Empfehlung:**
  1. User-Plugin-Verzeichnis NICHT automatisch bei jedem Start erstellen
  2. Warnung im UI anzeigen wenn User-Plugins vorhanden sind
  3. Plugins nur laden wenn der User sie explizit aktiviert hat
  4. Langfristig: Signatur-Pruefung oder Plugin-Manifest mit Hash-Verifikation
- **Quelle:** Agent 3 (Finding 2)

---

### HIGH

#### H-01: API-Key wird im Klartext in QSettings gespeichert
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py:969`
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py:985`
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_api.py:86-88` (In-Memory-Speicherung)
- **Typ:** Credential Storage im Klartext (CWE-312)
- **Beschreibung:** Der Nexus Mods API-Key wird im Klartext ueber `QSettings.setValue("nexus/api_key", key)` gespeichert. Unter Linux speichert QSettings in `~/.config/AnvilOrganizer/...` als INI-Datei mit Standard-Berechtigungen (umask-abhaengig, typisch 0o644 = welt-lesbar). Jeder Prozess auf dem System kann den API-Key auslesen. Der Key ermoeglicht vollen Zugriff auf das Nexus-Konto des Benutzers (Downloads, Endorsements, etc.). MO2 nutzt unter Windows die Registry, die marginal besser geschuetzt ist.
- **Code:**
  ```python
  # settings_dialog.py:969
  settings.setValue("nexus/api_key", api_key)
  # settings_dialog.py:985
  settings.setValue("nexus/api_key", key.strip())
  ```
- **Empfehlung:**
  1. Beste Option: `keyring`-Bibliothek verwenden (nutzt SecretService/D-Bus unter Linux)
  2. Fallback: Dateiberechtigungen der Config-Datei auf 0o600 setzen
  3. API-Key beim Anzeigen maskieren (nur letzte 4 Zeichen)
- **Quelle:** Agent 1 (Finding 9), Agent 2 (HIGH-06), Agent 3 (Finding 3)

---

#### H-02: Path Traversal bei Data-Override Uninstall (Manifest-basiert)
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/bg3_mod_installer.py:392-395`
- **Typ:** Path Traversal (CWE-22)
- **Beschreibung:** Die `uninstall_data_override()`-Methode loescht Dateien basierend auf relativen Pfaden aus einem JSON-Manifest. Wenn das Manifest manipuliert wurde (z.B. `../../important_file`), werden Dateien AUSSERHALB des Game-Verzeichnisses geloescht. Die Pfade aus dem Manifest werden nicht validiert.
- **Code:**
  ```python
  for rel_path in manifest.get("files", []):
      full = self._game_path / rel_path  # rel_path wird nicht validiert
      if full.is_file():
          full.unlink()  # Loescht beliebige Dateien wenn Manifest manipuliert
  ```
- **Empfehlung:**
  ```python
  full = (self._game_path / rel_path).resolve()
  if not full.is_relative_to(self._game_path.resolve()):
      continue  # Path Traversal blocked
  ```
- **Quelle:** Agent 1 (Finding 5)

---

#### H-03: Path Traversal und Symlink-Probleme beim Deploy-Manifest-Purge
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_deployer.py:339-341` (Manifest-Pfade)
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_deployer.py:358-379` (TOCTOU bei Symlink-Purge)
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_deployer.py:365-366` (String-basierter Vergleich)
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_deployer.py:166,277` (Deploy ohne Ziel-Validierung)
- **Typ:** Path Traversal + TOCTOU Race Condition (CWE-22, CWE-367)
- **Beschreibung:** Mehrere zusammenhaengende Probleme im Deployer:
  1. **Purge liest Pfade aus Manifest:** Relative Pfade aus JSON-Manifest werden ohne Validierung zum Loeschen verwendet.
  2. **TOCTOU bei Symlink-Check:** Zwischen `is_symlink()` Pruefung und `unlink()` kann sich der Zustand aendern.
  3. **String-basierter Pfadvergleich:** `str(real_target).startswith(mods_str)` kann umgangen werden (z.B. `.mods-evil/` matched `.mods`).
  4. **Deploy ohne Ziel-Validierung:** Symlinks werden erstellt ohne zu pruefen, ob das Ziel tatsaechlich innerhalb von `.mods/` liegt. Ein Mod-Verzeichnis mit eingebetteten Symlinks koennte `/etc/passwd` ins Spielverzeichnis deployen.
- **Code:**
  ```python
  # Purge: String-basierter Vergleich (unsicher)
  mods_str = str(self._mods_path)
  if not str(real_target).startswith(mods_str):
      continue  # umgehbar!

  # Deploy: Keine Ziel-Validierung
  target.symlink_to(src_file)  # src_file nicht validiert
  ```
- **Empfehlung:**
  1. `Path.is_relative_to()` (Python 3.9+) statt String-Vergleich verwenden
  2. Beim Deploy Symlink-Ziele mit `.resolve()` gegen `.mods/` validieren
  3. Atomaren Symlink-Check via `os.readlink()` verwenden
- **Quelle:** Agent 1 (Finding 4, 6, 13), Agent 3 (Finding 7)

---

#### H-04: Command Injection via xdg-open an 8+ Stellen
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py:1150,1152,1154`
  - `/home/mob/Projekte/Anvil Organizer/anvil/dialogs/mod_detail_dialog.py:352,545,791`
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py:790,833`
- **Typ:** Command Injection / Arbitrary File Open (CWE-78)
- **Beschreibung:** `subprocess.Popen(["xdg-open", path])` wird an 8+ Stellen aufgerufen. Obwohl die Verwendung einer Liste statt eines Strings Shell-Injection verhindert, gibt es weitere Risiken:
  1. Pfade aus .meta-Dateien oder Tabellendaten koennten Symlinks oder `..`-Pfade enthalten
  2. xdg-open interpretiert URLs (`http://`, `ftp://`) — ein Pfad der wie eine URL aussieht oeffnet einen Browser
  3. Ein boesartiger Mod-Name koennte xdg-open dazu bringen, unerwartete Dateien/URIs zu oeffnen
  Es fehlt eine zentrale Validierungsfunktion.
- **Code:**
  ```python
  # game_panel.py:1149-1154
  elif chosen == act_open:
      subprocess.Popen(["xdg-open", first])
  elif chosen == act_meta:
      subprocess.Popen(["xdg-open", str(meta_path)])
  elif chosen == act_show:
      subprocess.Popen(["xdg-open", str(Path(first).parent)])
  ```
- **Empfehlung:**
  1. Zentrale `safe_open_path(path, allowed_base)` Funktion erstellen
  2. Pfade mit `Path.resolve()` aufloesen und gegen erlaubte Basisverzeichnisse pruefen
  3. Pruefen dass kein `://` Schema enthalten ist
  4. Alternativ `QDesktopServices.openUrl(QUrl.fromLocalFile(path))` verwenden (nur lokale Dateien)
- **Quelle:** Agent 2 (CRITICAL-01)

---

#### H-05: URL-Injection via Nexus-Mod-ID aus .meta-Datei
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py:1147-1148`
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py:952-965` (_read_meta_mod_id)
- **Typ:** URL Injection / Open Redirect (CWE-601)
- **Beschreibung:** Die `mod_id` wird aus einer .meta-Datei gelesen und unvalidiert in eine Nexus-URL eingebaut: `f"https://www.nexusmods.com/{game}/mods/{mod_id}"`. Eine manipulierte .meta-Datei koennte den Browser auf eine Phishing-Seite umleiten. Ebenso kommt `game` (short name) aus Plugin-Daten ohne Validierung.
- **Code:**
  ```python
  def _read_meta_mod_id(self, archive_path: str) -> str | None:
      # ...
      mod_id = cp.get("General", "modID", fallback=None)
      if mod_id and mod_id.strip():
          return mod_id.strip()  # Keine Validierung!

  # Verwendung:
  QDesktopServices.openUrl(
      QUrl(f"https://www.nexusmods.com/{game}/mods/{mod_id}"))
  ```
- **Empfehlung:**
  1. `mod_id` MUSS als reine Ganzzahl validiert werden: `if mod_id.isdigit(): ...`
  2. `game` (short name) gegen `^[a-zA-Z0-9_-]+$` validieren
  3. Die URL mit `QUrl` konstruieren und `isValid()` pruefen
- **Quelle:** Agent 2 (CRITICAL-02)

---

#### H-06: Beliebige Datei-Schreiboperationen und -Verschiebungen aus Mod-Detail-Dialog
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/dialogs/mod_detail_dialog.py:327-333` (Textfile Save)
  - `/home/mob/Projekte/Anvil Organizer/anvil/dialogs/mod_detail_dialog.py:515-521` (INI Save)
  - `/home/mob/Projekte/Anvil Organizer/anvil/dialogs/mod_detail_dialog.py:708-713,726-731` (File Move)
- **Typ:** Arbitrary File Write/Move (CWE-22)
- **Beschreibung:** Der Mod-Detail-Dialog erlaubt das Bearbeiten und Speichern von Dateien sowie das Verschieben von Dateien. Die Pfade stammen aus `item.data(Qt.ItemDataRole.UserRole)`, die aus einem Verzeichnis-Scan generiert werden. Wenn ein Mod-Archiv Symlinks enthaelt, koennte `current_path[0]` auf eine Datei ausserhalb des Mod-Verzeichnisses zeigen. Der Benutzer wuerde dann unwissentlich eine System-Datei ueberschreiben oder verschieben.
- **Code:**
  ```python
  # Save:
  def on_save():
      path = current_path[0]
      with open(path, "w", encoding="utf-8") as f:
          f.write(editor.toPlainText())

  # Move:
  src = Path(item.data(Qt.ItemDataRole.UserRole))
  shutil.move(str(src), str(dst))
  ```
- **Empfehlung:**
  1. Vor dem Schreiben/Verschieben: `Path(path).resolve().is_relative_to(mod_root_path)` pruefen
  2. Symlinks im Mod-Verzeichnis nicht folgen oder warnen
- **Quelle:** Agent 2 (HIGH-02, HIGH-03)

---

#### H-07: Unsichere Desktop-Datei-Erstellung fuer nxm:// Handler
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/nxm_handler.py:97-107`
- **Typ:** Command Injection via Desktop Entry (CWE-78)
- **Beschreibung:** Die `register_nxm_handler()`-Funktion erstellt eine `.desktop`-Datei mit dem Pfad zum `main.py`-Script. Der Pfad (`main_script`) stammt aus `sys.argv[0]` oder dem Dateisystem und wird unvalidiert in die `Exec=`-Zeile geschrieben. Ein Pfad mit Sonderzeichen koennte zu unbeabsichtigter Ausfuehrung fuehren.
- **Code:**
  ```python
  content = f"""[Desktop Entry]
  ...
  Exec=python3 {main_script} %u
  ...
  """
  desktop_file.write_text(content, encoding="utf-8")
  ```
- **Empfehlung:** Pfad mit `shlex.quote()` escapen:
  ```python
  import shlex
  escaped = shlex.quote(main_script)
  content = f'Exec=python3 {escaped} %u\n'
  ```
- **Quelle:** Agent 1 (Finding 7)

---

#### H-08: Error-Messages koennten API-Key leaken
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_api.py:58-59`
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_api.py:182-183`
- **Typ:** Information Exposure (CWE-209)
- **Beschreibung:** Bei einem Netzwerkfehler wird `str(exc)` in einem Error-Signal emittiert. HTTP-Fehler-Details koennten den API-Key enthalten (z.B. bei Redirect-Fehlern die die volle URL mit Headern loggen). Diese Fehlernachrichten werden im UI angezeigt und landen in Logs.
- **Code:**
  ```python
  except Exception as exc:
      self.error.emit(self._tag, str(exc))
  ```
- **Empfehlung:** Exception-Messages sanitizen:
  ```python
  def _sanitize_error(self, msg: str) -> str:
      if self._api_key:
          return msg.replace(self._api_key, "[API_KEY]")
      return msg
  ```
- **Quelle:** Agent 3 (Finding 6)

---

#### H-09: Argument Injection bei Steam-Launch via Plugin-Daten
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py:529-538`
- **Typ:** Argument Injection (CWE-88)
- **Beschreibung:** `GameSteamId` und `GameLaunchArgs` kommen aus Plugin-Klassen und werden unvalidiert an `QProcess.startDetached(steam_bin, args)` uebergeben. Ein boesartiges Plugin koennte beliebige Argumente an Steam uebergeben, einschliesslich gefaehrlicher CLI-Optionen.
- **Code:**
  ```python
  steam_id = plugin.GameSteamId
  args = ["-applaunch", str(steam_id)]
  if hasattr(plugin, "GameLaunchArgs"):
      args.extend(plugin.GameLaunchArgs)
  success, pid = QProcess.startDetached(steam_bin, args)
  ```
- **Empfehlung:**
  1. `GameSteamId` als Ganzzahl validieren: `int(steam_id)`
  2. `GameLaunchArgs` gegen eine Allowlist pruefen
- **Quelle:** Agent 2 (HIGH-05)

---

### MEDIUM

#### M-01: Fehlende Pfad-Validierung bei Instanz-Erstellung
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/instance_wizard.py:602-608,675-683`
- **Typ:** Path Traversal (CWE-22)
- **Beschreibung:** Benutzerdefinierte Pfade fuer Mods, Downloads und Overwrite werden ohne Validierung an `create_instance()` weitergegeben. QLineEdit-Felder sind frei editierbar. Ein Pfad wie `/etc/` koennte als Mod-Verzeichnis gesetzt werden.
- **Empfehlung:** System-Verzeichnisse per Blocklist sperren (`/etc`, `/usr`, `/bin`, `/boot`, `/dev`, `/proc`, `/sys`). Warnung wenn Pfad ausserhalb des Home-Verzeichnisses liegt.
- **Quelle:** Agent 2 (MEDIUM-01)

---

#### M-02: Fehlende Pfad-Validierung bei Instanz-Pfad-Aenderungen im Settings-Dialog
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py:884-891`
- **Typ:** Path Traversal / Configuration Manipulation (CWE-22)
- **Beschreibung:** Pfade aus QLineEdit-Feldern werden direkt in die Instanz-Konfiguration geschrieben. Die `_unresolve()`-Funktion fuehrt keine Sicherheitspruefung durch.
- **Empfehlung:** Gleiche Validierung wie bei M-01 anwenden.
- **Quelle:** Agent 2 (MEDIUM-02)

---

#### M-03: XML-Parser anfaellig fuer Billion Laughs / XXE
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/lspk_parser.py:210`
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/bg3_mod_installer.py:233-234`
  - `/home/mob/Projekte/Anvil Organizer/anvil/plugins/games/bg3_mod_handler.py:135`
- **Typ:** XXE / Denial of Service (CWE-611, CWE-776)
- **Beschreibung:** `xml.etree.ElementTree` wird an drei Stellen fuer das Parsen von BG3-spezifischen XML-Dateien (meta.lsx, modsettings.lsx) verwendet. Python's stdlib ET ignoriert zwar externe Entities, ist aber anfaellig fuer Billion-Laughs-Angriffe (Entity-Expansion), die zu Speichererschoepfung fuehren. Die XML-Daten stammen aus Mod-Archiven (.pak-Dateien) und sind damit potenziell von Dritten kontrolliert. Der `# noqa: S314` Kommentar in `bg3_mod_handler.py:135` zeigt, dass das Problem bekannt ist aber bewusst ignoriert wird.
- **Code:**
  ```python
  # lspk_parser.py:210
  root = ET.fromstring(data.decode("utf-8-sig"))
  # bg3_mod_installer.py:233-234
  tree = ET2.parse(path)
  # bg3_mod_handler.py:135
  tree = ET.parse(path)  # noqa: S314
  ```
- **Empfehlung:** `defusedxml` als Dependency hinzufuegen:
  ```python
  from defusedxml import ElementTree as SafeET
  root = SafeET.fromstring(data)
  ```
- **Quelle:** Agent 1 (Finding 10), Agent 3 (Finding 4)

---

#### M-04: Datei-Loeschung ohne Pfad-Validierung im Download-Bereich
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/game_panel.py:1001-1011,1166-1176`
- **Typ:** Arbitrary File Deletion (CWE-22)
- **Beschreibung:** Download-Pfade aus der Tabelle werden ohne Pruefung geloescht, ob sie innerhalb des Downloads-Verzeichnisses liegen. Manipulierte Tabellendaten koennten beliebige Dateien referenzieren.
- **Empfehlung:** `Path(p).resolve().is_relative_to(downloads_dir)` vor dem Loeschen pruefen.
- **Quelle:** Agent 2 (MEDIUM-03)

---

#### M-05: LZ4 Decompression Bomb
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/lspk_parser.py:116`
- **Typ:** Denial of Service (CWE-400)
- **Beschreibung:** `lz4.block.decompress()` wird mit `uncompressed_size` aufgerufen, der direkt aus der .pak-Datei gelesen wird. Ein boesartig erstelltes Archiv koennte einen extrem grossen Wert angeben, der zu Out-of-Memory fuehrt.
- **Code:**
  ```python
  num_files = struct.unpack("<I", f.read(4))[0]
  expected_size = _ENTRY_SIZE * num_files  # num_files unkontrolliert
  decompressed = lz4.block.decompress(compressed_data, uncompressed_size=expected_size)
  ```
- **Empfehlung:** `num_files` auf max. 100.000 begrenzen.
- **Quelle:** Agent 1 (Finding 11)

---

#### M-06: WebSocket-Rekursion ohne Tiefenlimit (Stack Overflow)
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py:335`
- **Typ:** Denial of Service / Stack Overflow (CWE-674)
- **Beschreibung:** `_ws_recv_text()` ruft sich rekursiv auf wenn ein Ping-Frame empfangen wird. Kontinuierliche Ping-Frames koennen einen Stack Overflow verursachen.
- **Code:**
  ```python
  if opcode == 0x09:
      # ... send pong ...
      return _ws_recv_text(sock)  # rekursiv!
  ```
- **Empfehlung:** Iterative `while True`-Schleife statt Rekursion.
- **Quelle:** Agent 1 (Finding 14), Agent 3 (Finding 9)

---

#### M-07: Subprocess-Aufrufe mit Archiv-Pfaden (Argument-Injection)
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_installer.py:367-370,389-390`
- **Typ:** Argument Injection (CWE-88)
- **Beschreibung:** `unrar`- und `7z`-Aufrufe verwenden Pfade als Argumente. Obwohl Listen-Argumente (kein `shell=True`) verwendet werden, koennten Dateinamen die mit `-` beginnen als Flags interpretiert werden.
- **Empfehlung:** `--` vor Pfad-Argumenten einfuegen oder Pfade mit `./` prefixen.
- **Quelle:** Agent 3 (Finding 10)

---

#### M-08: WebSocket-Empfang ohne Laengenbegrenzung
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py:296-314`
- **Typ:** Denial of Service (CWE-400)
- **Beschreibung:** Das WebSocket-Length-Feld kann bis zu 2^63 Bytes gross sein. `_ws_recv_exact(sock, length)` wuerde versuchen, diese Menge Speicher zu allokieren.
- **Empfehlung:** Maximale Frame-Groesse auf 16 MB begrenzen.
- **Quelle:** Agent 1 (Finding 15), Agent 3 (Finding 8)

---

#### M-09: HTML-Injection in QLabel via Plugin-Nexus-URL
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py:769-770`
- **Typ:** HTML Injection in Qt Rich Text (CWE-79)
- **Beschreibung:** Plugin-Attribute (`GameNexusName`) werden unescaped in ein QLabel mit HTML eingebaut. Ein manipulierter Wert koennte den Link auf eine Phishing-Seite umleiten.
- **Empfehlung:** `nexus_id` mit Regex validieren (`^[a-zA-Z0-9_-]+$`) und `html.escape()` verwenden.
- **Quelle:** Agent 2 (HIGH-01)

---

#### M-10: Unsichere Temp-Dateien und Berechtigungen
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_installer.py:152`
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/bg3_mod_installer.py:890`
- **Typ:** Insecure Temp File (CWE-377)
- **Beschreibung:** `tempfile.mkdtemp()` erstellt Verzeichnisse in `/tmp/` (0o700, sicher). Allerdings setzen externe Tools (`unrar`, `7z`) die Datei-Berechtigungen aus dem Archiv, was zu welt-lesbaren oder ausfuehrbaren Dateien in `/tmp/` fuehren kann. Zwischen Erstellen und Verschieben nach `.mods/` (TOCTOU-Fenster) koennten Dateien manipuliert werden.
- **Empfehlung:** Temp-Verzeichnisse in Instance-privatem Ordner erstellen (z.B. `.tmp/` innerhalb der Instanz).
- **Quelle:** Agent 1 (Finding 3), Agent 3 (Finding 5)

---

### LOW

#### L-01: TOCTOU bei Instance-Erstellung
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/instance_manager.py:109-115`
- **Typ:** TOCTOU Race Condition (CWE-367)
- **Beschreibung:** Zwischen `instance_dir.exists()` und `instance_dir.mkdir()` koennte ein anderer Prozess das Verzeichnis erstellen.
- **Empfehlung:** `mkdir(exist_ok=False)` direkt aufrufen und `FileExistsError` abfangen.
- **Quelle:** Agent 1 (Finding 16)

---

#### L-02: shutil.rmtree() bei Instance-Loeschung ohne Symlink-Check
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/instance_manager.py:191`
- **Typ:** Unbeabsichtigte Dateiloeschung (CWE-59)
- **Beschreibung:** Wenn `instance_dir` selbst ein Symlink ist, loescht `rmtree` das Zielverzeichnis.
- **Empfehlung:** `if instance_dir.is_symlink(): return False` vor `rmtree()`.
- **Quelle:** Agent 1 (Finding 17)

---

#### L-03: Keine Validierung von mod_name bei Pfad-Konstruktion
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_installer.py:171`
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/bg3_mod_installer.py:681`
- **Typ:** Path Traversal (CWE-22)
- **Beschreibung:** `folder_name` aus Benutzereingabe wird direkt fuer Pfad-Konstruktion verwendet. `_sanitize_name()` wird nur aufgerufen wenn `mod_name` None ist, nicht bei explizitem Nutzernamen.
- **Empfehlung:** `_sanitize_name()` IMMER anwenden, auch bei explizitem `mod_name`.
- **Quelle:** Agent 1 (Finding 18)

---

#### L-04: icon_manager rel_path wird nicht validiert
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/icon_manager.py:82-89`
- **Typ:** Path Traversal (Read-Only, CWE-22)
- **Beschreibung:** `IconManager._load()` konstruiert einen Pfad aus `game_short_name` und `rel_path` ohne Validierung. Read-only und Daten kommen aus dem Plugin-System, daher geringes Risiko.
- **Empfehlung:** `.resolve()` + `is_relative_to()` Pruefung hinzufuegen.
- **Quelle:** Agent 1 (Finding 19)

---

#### L-05: Debug-Print-Statements in Produktionscode
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/plugins/base_game.py:265-271`
  - `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_installer.py:260,273,312,323,324`
- **Typ:** Information Exposure (CWE-532)
- **Beschreibung:** Mehrere `print(f"DEBUG ...")` Statements geben Archiv-Inhalte und Pattern-Matching-Ergebnisse auf stdout aus. Koennten in Logs landen.
- **Empfehlung:** Durch `logging.debug()` ersetzen oder entfernen.
- **Quelle:** Agent 3 (Finding 12)

---

#### L-06: VDF-Parser ohne Eingabelaengenbegrenzung
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/stores/steam_utils.py:38-84`
- **Typ:** Denial of Service (CWE-400)
- **Beschreibung:** VDF-Dateien werden vollstaendig in den Speicher gelesen. Keine Groessen- oder Tiefenbegrenzung. VDF-Dateien kommen von Steam und sind normalerweise klein.
- **Empfehlung:** Optional: Dateigroesse vor dem Lesen pruefen (max 10 MB).
- **Quelle:** Agent 3 (Finding 13)

---

#### L-07: Fehlende Input-Laengen-Begrenzung bei Rename/Create-Operationen
- **Dateien:**
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/instance_manager_dialog.py` (_on_rename)
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/instance_wizard.py` (Instanz-Name)
  - `/home/mob/Projekte/Anvil Organizer/anvil/widgets/category_dialog.py` (Kategorie-Name)
- **Typ:** Resource Exhaustion (CWE-400)
- **Beschreibung:** Benutzereingaben fuer Namen werden nicht auf Laenge begrenzt. Extrem lange Namen koennten Dateisystem-Limits ueberschreiten.
- **Empfehlung:** `QLineEdit.setMaxLength(255)` fuer alle Name-Eingabefelder.
- **Quelle:** Agent 2 (LOW-04)

---

## Entwarnung (Positives)

Die folgenden Aspekte wurden in ALLEN drei Teil-Audits als korrekt und sicher bewertet:

1. **Kein `eval()/exec()/pickle`:** Keine dynamische Code-Ausfuehrung auf User-Daten in allen 71 Dateien.
2. **Kein `shell=True`:** Alle `subprocess.run()`-Aufrufe verwenden Listen-Argumente. Keine direkte Shell-Injection moeglich.
3. **Kein `os.system()/os.popen()`:** Alle externen Prozesse laufen ueber `subprocess.run()` oder `QProcess`.
4. **Keine hardcodierten Credentials:** Kein API-Key oder Passwort im Quellcode. Der APPLICATION_SLUG in nexus_sso.py ist ein oeffentlicher Identifier.
5. **HTTPS-only API-Kommunikation:** `nexus_api.py` verwendet ausschliesslich `https://` mit TLS-Validierung. Kein `verify=False`.
6. **SSL-Kontext fuer SSO:** `nexus_sso.py` verwendet `ssl.create_default_context()` — Zertifikate werden validiert.
7. **Sichere SQLite-Nutzung:** `lutris_utils.py` oeffnet die Datenbank im Read-Only-Modus (`?mode=ro`). Keine SQL-Injection.
8. **JSON-Deserialisierung sicher:** Alle Serialisierung erfolgt ueber `json.loads()`/`json.dumps()` und `configparser`. Kein YAML, kein Pickle.
9. **Keine unsichere Deserialisierung:** Kein `yaml.load()`, kein `pickle.loads()` auf externe Daten.
10. **Rate-Limiting:** Nexus API Rate-Limits werden aus Response-Headern gelesen und kommuniziert.
11. **Bestaetigungsdialoge:** Loeschvorgaenge zeigen immer einen Bestaetigungsdialog.
12. **Exception Handling:** Die meisten File-Operationen sind in try/except gekapselt.
13. **QProcess.startDetached statt os.system:** Fuer externe Prozesse wird der sicherere Qt-Weg verwendet.

---

## Empfohlene Reihenfolge der Behebung

### Phase 1: Sofort (CRITICAL) — Geschaetzter Aufwand: 2-3 Stunden
1. **ZipSlip-Fix (C-01):** Gemeinsame `safe_extract_zip()`/`safe_extract_archive()` Funktion in `anvil/core/archive_utils.py` erstellen. Alle 2 ZIP-extractall-Stellen + RAR/7z-Extraktionen absichern. (1h)
2. **Plugin-Warnung (C-02):** UI-Warnung wenn User-Plugins im Verzeichnis gefunden werden. Auto-Erstellung des Plugin-Ordners abschalten. (30min)

### Phase 2: Zeitnah (HIGH) — Geschaetzter Aufwand: 4-5 Stunden
3. **Zentrale `safe_path()` Funktion (H-02, H-03, H-06):** Eine Utility-Funktion `validate_path_within(target, base)` erstellen und an allen Manifest- und File-Operations-Stellen verwenden. (1h)
4. **Zentrale `safe_open_path()` Funktion (H-04):** Eine Hilfsfunktion fuer xdg-open mit Pfad-Validierung. 8 Callsites aktualisieren. (30min)
5. **mod_id/game Validierung (H-05):** `isdigit()` Check fuer mod_id, Regex fuer game name. (10min)
6. **Desktop-Entry Escaping (H-07):** `shlex.quote()` in nxm_handler.py. (5min)
7. **API-Key-Schutz (H-01, H-08):** `keyring` Integration oder 0o600-Berechtigungen. Error-Sanitizing fuer API-Key. (1-2h)
8. **Steam-Argument-Validierung (H-09):** `int()` Cast fuer SteamId, Allowlist fuer LaunchArgs. (10min)

### Phase 3: Mittelfristig (MEDIUM) — Geschaetzter Aufwand: 3-4 Stunden
9. **defusedxml (M-03):** Als Dependency hinzufuegen, 3 Stellen aktualisieren. (30min)
10. **WebSocket iterativ (M-06):** Rekursion durch while-Loop ersetzen. (15min)
11. **WebSocket-Laengenlimit (M-08):** MAX_FRAME_SIZE = 16 MB. (5min)
12. **LZ4-Limit (M-05):** MAX_FILES = 100.000 Check. (5min)
13. **Temp-Verzeichnis privat (M-10):** In Instance-Ordner statt /tmp/. (20min)
14. **Instanz-Pfad-Validierung (M-01, M-02):** System-Verzeichnis-Blocklist. (30min)
15. **Download-Loeschung (M-04):** is_relative_to() Check. (10min)
16. **HTML-Escape (M-09):** html.escape() + Regex-Validierung. (10min)
17. **Subprocess-Haertung (M-07):** `--` Separator oder `./`-Prefix. (10min)

### Phase 4: Wartung (LOW) — Geschaetzter Aufwand: 1-2 Stunden
18. **Debug-Prints entfernen (L-05):** Durch logging.debug() ersetzen. (15min)
19. **Instance mkdir atomar (L-01):** exist_ok=False + try/except. (5min)
20. **rmtree Symlink-Check (L-02):** is_symlink() Pruefung vor rmtree. (5min)
21. **mod_name Sanitierung (L-03):** _sanitize_name() immer anwenden. (5min)
22. **Input-Laengenbegrenzung (L-07):** setMaxLength(255). (10min)
23. **icon_manager Pfad-Check (L-04):** is_relative_to(). (5min)
24. **VDF-Parser Limit (L-06):** Optional, geringes Risiko. (5min)

**Gesamtaufwand geschaetzt: 10-14 Stunden**

---

## Vergleich mit MO2

| Aspekt | MO2 | Anvil Organizer | Bewertung |
|--------|-----|-----------------|-----------|
| ZIP-Extraktion | Eigener Extractor mit Pfad-Validierung | `extractall()` ohne Validierung | Anvil schlechter |
| API-Key-Speicherung | QSettings (Windows Registry) | QSettings (INI-Datei, Klartext) | Anvil schlechter |
| Plugin-System | C++ DLL-basiert mit Manifest | Python importlib ohne Validierung | Anvil schlechter |
| XML-Parsing | Qt XML-Parser | stdlib ET ohne defusedxml | Vergleichbar |
| Deploy-Mechanismus | VFS-basiert (in-memory) | Symlinks auf Disk | Andere Angriffsflaeche |
| Subprocess | Keine Shell-Aufrufe | Listen-basiert (kein shell=True) | Vergleichbar gut |
| SSO-Login | QtNetwork/QWebSocket | Stdlib ssl+socket | Anvil einfacher, funktional |
| Allgemein | 15 Jahre Reifung | Fruehe Entwicklung | Verbesserungspotential |

---

## Statistik

| Metrik | Wert |
|--------|------|
| Gepruefte Dateien | 71 |
| Gepruefte Codezeilen | ca. 10.000+ |
| Unique Findings (dedupliziert) | 28 |
| Davon CRITICAL | 2 |
| Davon HIGH | 9 |
| Davon MEDIUM | 10 |
| Davon LOW | 7 |
| Duplikate eliminiert | 22 (aus 50 Roh-Findings) |
| Haeufigste Kategorie | Path Traversal (9 Findings) |

---

## Quellen

- `docs/workflow/security-agent1-core.md` — 20 Dateien in anvil/core/, 19 Findings
- `docs/workflow/security-agent2-widgets.md` — 25 Dateien in anvil/widgets/ + anvil/dialogs/, 17 Findings
- `docs/workflow/security-agent3-plugins.md` — 26 Dateien in anvil/plugins/ + anvil/stores/ + Teile von anvil/core/, 14 Findings

---

*Konsolidierter Report erstellt am 2026-02-25.*
*Keine Dateien wurden geaendert — nur Lesen und Berichten.*
