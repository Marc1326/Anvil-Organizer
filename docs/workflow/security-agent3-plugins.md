# Security Audit Report — anvil/plugins/, anvil/stores/ & nexus_api.py

**Datum:** 2026-02-25
**Auditor:** Agent 3 (QA-Pruefer)
**Scope:** anvil/plugins/, anvil/stores/, anvil/core/nexus_api.py, anvil/core/nexus_sso.py, anvil/core/mod_installer.py, anvil/core/mod_deployer.py, anvil/core/bg3_mod_installer.py

## Zusammenfassung

**26 Dateien geprueft, 14 Findings identifiziert:**

| Schweregrad | Anzahl |
|-------------|--------|
| CRITICAL    | 2      |
| HIGH        | 4      |
| MEDIUM      | 5      |
| LOW         | 3      |

---

## Findings

### Finding 1: ZipSlip — Unsichere ZIP-Extraktion ohne Pfad-Validierung

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_installer.py:348-349`
- **Schweregrad:** CRITICAL
- **Typ:** Path Traversal / ZipSlip (CWE-22)
- **Beschreibung:** `zipfile.ZipFile.extractall()` wird ohne Validierung der Archiv-Eintraege aufgerufen. Ein boesartig praepariertes ZIP-Archiv kann Dateien mit `../` im Pfad enthalten (z.B. `../../.bashrc`), die dann ausserhalb des Zielverzeichnisses entpackt werden. Da Mod-Archive von Drittanbieter-Webseiten (Nexus Mods) heruntergeladen werden, ist dies ein realistischer Angriffsvektor.
- **Code:**
  ```python
  # mod_installer.py:348-349
  with zipfile.ZipFile(archive, "r") as zf:
      zf.extractall(dest)
  ```
- **Zweite Stelle:** `/home/mob/Projekte/Anvil Organizer/anvil/core/bg3_mod_installer.py:895-896`
  ```python
  # bg3_mod_installer.py:895-896
  with zipfile.ZipFile(archive_path, "r") as zf:
      zf.extractall(tmp)
  ```
- **Empfehlung:** Vor dem Entpacken alle Eintraege pruefen:
  ```python
  import os
  with zipfile.ZipFile(archive, "r") as zf:
      for member in zf.namelist():
          target = os.path.realpath(os.path.join(dest, member))
          if not target.startswith(os.path.realpath(str(dest)) + os.sep):
              raise ValueError(f"ZipSlip detected: {member}")
      zf.extractall(dest)
  ```

---

### Finding 2: Dynamisches Code-Laden aus User-Plugin-Verzeichnis ohne Validierung

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/plugins/plugin_loader.py:116,155-165`
- **Schweregrad:** CRITICAL
- **Typ:** Arbitrary Code Execution (CWE-94)
- **Beschreibung:** Der PluginLoader laedt und fuehrt beliebige Python-Dateien aus `~/.anvil-organizer/plugins/games/` aus. Es gibt keine Signatur-Pruefung, kein Sandboxing und keine Validierung. Ein Angreifer, der Schreibzugriff auf das Home-Verzeichnis hat (z.B. durch ein boesartiges Mod-Archiv via ZipSlip/Finding 1), kann beliebigen Python-Code als Plugin einschleusen. Dies ist besonders kritisch in Kombination mit Finding 1.
- **Code:**
  ```python
  # plugin_loader.py:155-165
  spec = importlib.util.spec_from_file_location(module_name, py_file)
  # ...
  module = importlib.util.module_from_spec(spec)
  sys.modules[module_name] = module
  spec.loader.exec_module(module)  # <-- beliebiger Code wird ausgefuehrt
  ```
- **Empfehlung:**
  1. User-Plugin-Verzeichnis NICHT automatisch erstellen (`ensure_user_plugin_dir()` nicht bei jedem Start aufrufen)
  2. Mindestens eine Warnung im UI anzeigen wenn User-Plugins vorhanden sind
  3. Optional: Plugins nur laden wenn der User sie explizit aktiviert
  4. Langfristig: Signatur-Pruefung oder Plugin-Manifest mit Hash-Verifikation

---

### Finding 3: API-Key im Klartext in QSettings gespeichert

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/widgets/settings_dialog.py:969,985`
- **Schweregrad:** HIGH
- **Typ:** Credential Storage (CWE-312)
- **Beschreibung:** Der Nexus Mods API-Key wird im Klartext ueber `QSettings.setValue("nexus/api_key", key)` gespeichert. Unter Linux schreibt QSettings standardmaessig in `~/.config/AnvilOrganizer/...` als INI-Datei. Jeder Prozess des gleichen Users kann den API-Key lesen. MO2 nutzt ebenfalls QSettings, aber unter Windows mit der Registry (die marginal besser geschuetzt ist). Unter Linux ist dies eine Klartextdatei.
- **Code:**
  ```python
  # settings_dialog.py:969
  settings.setValue("nexus/api_key", api_key)
  # settings_dialog.py:985
  settings.setValue("nexus/api_key", key.strip())
  ```
- **Empfehlung:** Verwende `libsecret` / `SecretService` (D-Bus) ueber `keyring`-Bibliothek:
  ```python
  import keyring
  keyring.set_password("anvil-organizer", "nexus-api-key", api_key)
  # Lesen:
  keyring.get_password("anvil-organizer", "nexus-api-key")
  ```
  Falls `keyring` nicht verfuegbar, Fallback auf QSettings mit Dateiberechtigung 0600.

---

### Finding 4: XML-Parser anfaellig fuer Billion Laughs / XXE

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/plugins/games/bg3_mod_handler.py:135`
- **Schweregrad:** HIGH
- **Typ:** XML External Entity (XXE) / Denial of Service (CWE-611, CWE-776)
- **Beschreibung:** `xml.etree.ElementTree.parse()` wird ohne Deaktivierung externer Entities und ohne defusedxml verwendet. Eine boesartig praeparierte `modsettings.lsx` Datei koennte:
  - **Billion Laughs Attack:** Exponentiell wachsende Entity-Referenzen die den Speicher erschoepfen
  - **XXE:** Lokale Dateien lesen (z.B. `/etc/passwd`) ueber `<!ENTITY xxe SYSTEM "file:///etc/passwd">`
  Die `modsettings.lsx` wird aus dem Proton-Prefix gelesen, das grundsaetzlich vertrauenswuerdig ist. Aber Mods koennten diese Datei manipulieren.
- **Code:**
  ```python
  # bg3_mod_handler.py:135
  tree = ET.parse(path)  # noqa: S314
  ```
  Der `# noqa: S314` Kommentar zeigt, dass das Problem bekannt ist aber bewusst ignoriert wird.
- **Empfehlung:**
  ```python
  # Variante A: defusedxml verwenden
  import defusedxml.ElementTree as ET
  tree = ET.parse(path)

  # Variante B: stdlib mit Schutz
  parser = ET.XMLParser()
  # Ab Python 3.8: entity_declarations sind standardmaessig deaktiviert
  tree = ET.parse(path, parser=parser)
  ```

---

### Finding 5: Unsichere Temp-Dateien mit vorhersagbarem Praefix

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_installer.py:152`
- **Schweregrad:** HIGH
- **Typ:** Insecure Temp File (CWE-377)
- **Beschreibung:** `tempfile.mkdtemp(prefix="anvil_install_")` erstellt zwar ein sicheres Verzeichnis (random suffix), aber der Pfad liegt in `/tmp/` und ist damit fuer alle Prozesse des Systems sichtbar. Zwischen Erstellen des temp-Verzeichnisses und dem Verschieben nach `.mods/` (Zeile 172) koennte ein anderer Prozess Dateien darin manipulieren (TOCTOU). Insbesondere koennte ein Symlink innerhalb des temp-Verzeichnisses platziert werden, der beim `shutil.move()` an einen unerwarteten Ort zeigt.
- **Zweite Stelle:** `/home/mob/Projekte/Anvil Organizer/anvil/core/bg3_mod_installer.py:890`
  ```python
  tmp = tempfile.mkdtemp(prefix="bg3_mod_")
  ```
- **Code:**
  ```python
  # mod_installer.py:152
  tmp = Path(tempfile.mkdtemp(prefix="anvil_install_"))
  ```
- **Empfehlung:** Verwende ein privates temp-Verzeichnis innerhalb des Instance-Pfads:
  ```python
  tmp_base = self.instance_path / ".tmp"
  tmp_base.mkdir(mode=0o700, parents=True, exist_ok=True)
  tmp = Path(tempfile.mkdtemp(prefix="anvil_install_", dir=str(tmp_base)))
  ```

---

### Finding 6: Error-Messages koennten API-Key leaken

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_api.py:58-59`
- **Schweregrad:** HIGH
- **Typ:** Information Exposure (CWE-209)
- **Beschreibung:** Bei einem Netzwerkfehler wird `str(exc)` in der Error-Signal emittiert. HTTP-Fehler-Details koennten den API-Key enthalten, wenn die URL oder Request-Header im Exception-String auftauchen (z.B. bei Redirect-Fehlern, Proxy-Fehlern die die volle URL loggen). Der API-Key wird als HTTP-Header `apikey: <key>` gesendet.
- **Code:**
  ```python
  # nexus_api.py:58-59
  except Exception as exc:
      self.error.emit(self._tag, str(exc))
  ```
  Und weiter in `_on_worker_error`:
  ```python
  # nexus_api.py:182-183
  def _on_worker_error(self, tag: str, message: str) -> None:
      self.request_error.emit(tag, message)
  ```
  Diese Fehlernachrichten werden im UI angezeigt und koennen in Logs landen.
- **Empfehlung:** Exception-Messages sanitizen bevor sie emittiert werden:
  ```python
  def _sanitize_error(self, msg: str) -> str:
      if self._api_key:
          return msg.replace(self._api_key, "[API_KEY]")
      return msg
  ```

---

### Finding 7: Symlink-Ziel wird nicht validiert (Deployer)

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_deployer.py:166,277`
- **Schweregrad:** MEDIUM
- **Typ:** Insecure Symlink (CWE-59)
- **Beschreibung:** Beim Deploy werden Symlinks erstellt, deren Ziel (`mod_dir`, `src_file`) aus dem `.mods/` Verzeichnis kommt. Es wird nicht geprueft ob diese Pfade tatsaechlich innerhalb von `.mods/` liegen. Wenn ein Mod-Verzeichnis selbst Symlinks enthaelt (z.B. durch ein boesartiges Archiv), koennte ein Symlink auf `/etc/passwd` o.ae. in das Spielverzeichnis deployt werden. Der `purge()`-Code prueft zwar, ob das Symlink-Ziel in `.mods/` liegt (Zeile 362-371), aber der `deploy()`-Code tut dies nicht.
- **Code:**
  ```python
  # mod_deployer.py:277
  target.symlink_to(src_file)  # src_file nicht validiert
  # mod_deployer.py:166
  lml_target.symlink_to(mod_dir)  # mod_dir nicht validiert
  ```
- **Empfehlung:** Vor dem Erstellen von Symlinks pruefen, ob das Ziel aufgeloest innerhalb von `.mods/` liegt:
  ```python
  real_src = src_file.resolve()
  if not str(real_src).startswith(str(self._mods_path.resolve())):
      result.errors.append(f"skip {rel}: source outside .mods/")
      continue
  ```

---

### Finding 8: WebSocket-Empfang ohne Laengenbegrenzung

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py:297-314`
- **Schweregrad:** MEDIUM
- **Typ:** Denial of Service (CWE-400)
- **Beschreibung:** Die WebSocket-Empfangsfunktion `_ws_recv_text()` liest die Laenge aus dem Frame-Header und allokiert dann `length` Bytes. Ein boesartiger Server (z.B. bei MITM) koennte einen Frame mit `length = 2^63 - 1` senden, was zu einem Speicherueberlauf fuehrt. Obwohl der Server `sso.nexusmods.com` ist (TLS-geschuetzt), wuerde ein Limit die Robustheit erhoehen.
- **Code:**
  ```python
  # nexus_sso.py:302-314
  elif length == 127:
      ext = _ws_recv_exact(sock, 8)
      if ext is None:
          return None
      length = struct.unpack(">Q", ext)[0]
  # ...
  payload = _ws_recv_exact(sock, length)  # Keine Begrenzung!
  ```
- **Empfehlung:** Maximale Frame-Groesse begrenzen:
  ```python
  MAX_FRAME_SIZE = 16 * 1024 * 1024  # 16 MB
  if length > MAX_FRAME_SIZE:
      return None
  ```

---

### Finding 9: Rekursive WebSocket-Empfangsfunktion (Stack Overflow)

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py:335`
- **Schweregrad:** MEDIUM
- **Typ:** Denial of Service / Stack Overflow (CWE-674)
- **Beschreibung:** Bei Empfang eines Ping-Frames ruft `_ws_recv_text()` sich selbst rekursiv auf. Ein Server der wiederholt Ping-Frames sendet (ohne dazwischen Datenframes), kann einen Stack Overflow ausloesen.
- **Code:**
  ```python
  # nexus_sso.py:329-335
  if opcode == 0x09:
      pong = bytearray([0x8A, 0x80]) + os.urandom(4)
      try:
          sock.sendall(bytes(pong))
      except OSError:
          pass
      return _ws_recv_text(sock)  # <-- rekursiv!
  ```
- **Empfehlung:** Iterative Schleife statt Rekursion:
  ```python
  while True:
      # Frame lesen...
      if opcode == 0x09:  # Ping
          # Pong senden...
          continue  # Naechsten Frame lesen
      return payload.decode(...)
  ```

---

### Finding 10: Subprocess-Aufrufe mit Archiv-Pfaden

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_installer.py:367-370,389-390`
- **Schweregrad:** MEDIUM
- **Typ:** Command Injection (CWE-78)
- **Beschreibung:** Die `unrar`- und `7z`-Aufrufe verwenden `str(archive)` und `str(dest)` als Argumente. Da `subprocess.run()` mit einer Liste (nicht einem String) aufgerufen wird, ist eine direkte Shell-Injection nicht moeglich. Allerdings koennten Dateinamen mit Sonderzeichen (z.B. beginnend mit `-`) als Flags interpretiert werden. Der `unrar`-Aufruf verwendet `-o+`, der `7z`-Aufruf verwendet `-y`, was Interpretations-Risiken minimiert. Das Risiko ist gering, aber es waere sauberer, `--` zu verwenden um das Ende der Optionen zu markieren.
- **Code:**
  ```python
  # mod_installer.py:367-370
  subprocess.run(
      ["unrar", "x", "-o+", "-y", str(archive), str(dest) + "/"],
      check=True, capture_output=True,
  )
  ```
- **Empfehlung:** `--` vor den Pfad-Argumenten einfuegen (sofern von unrar/7z unterstuetzt), oder Pfade mit `.resolve()` normalisieren um `-`-Praefix zu vermeiden.

---

### Finding 11: Module-Name-Kollision im Plugin-Loader

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/plugins/plugin_loader.py:152`
- **Schweregrad:** MEDIUM
- **Typ:** Module Namespace Pollution (CWE-94)
- **Beschreibung:** User-Plugins und Built-in-Plugins verwenden den gleichen Namensschema `anvil_plugin_{stem}`. Wenn ein User-Plugin den gleichen Dateinamen hat wie ein Built-in-Plugin (z.B. `game_cyberpunk2077.py`), wird das Built-in-Modul in `sys.modules` ueberschrieben. Dies koennte von einem Angreifer ausgenutzt werden, um ein bestehendes Plugin zu ersetzen.
- **Code:**
  ```python
  # plugin_loader.py:152
  module_name = f"anvil_plugin_{py_file.stem}"
  # ...
  sys.modules[module_name] = module
  ```
- **Empfehlung:** Unterschiedliche Praefixe fuer Built-in und User-Plugins verwenden:
  ```python
  prefix = "anvil_plugin_builtin_" if directory == _BUILTIN_GAMES_DIR else "anvil_plugin_user_"
  module_name = f"{prefix}{py_file.stem}"
  ```

---

### Finding 12: Debug-Print-Statements in Produktionscode

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/plugins/base_game.py:265-271`
- **Schweregrad:** LOW
- **Typ:** Information Exposure (CWE-532)
- **Beschreibung:** Mehrere `print(f"DEBUG ...")` Statements in `is_framework_mod()` geben Archiv-Inhalte und Pattern-Matching-Ergebnisse auf stdout aus. In `mod_installer.py` gibt es ebenfalls Debug-Prints (Zeilen 260, 273, 312, 323, 324). Diese koennten in Logs landen und sind in Produktionscode unerwuenscht.
- **Code:**
  ```python
  # base_game.py:265-271
  print(f"DEBUG is_framework_mod: checking {len(archive_contents)} files", flush=True)
  print(f"DEBUG is_framework_mod: lower_contents={lower_contents[:10]}", flush=True)
  # ...
  print(f"DEBUG is_framework_mod: fw={fw.name}, pattern={pat}, matched={matched}", flush=True)
  ```
- **Empfehlung:** Alle `DEBUG` print-Statements entfernen oder durch ein konfigurierbares Logging-Framework ersetzen (`logging.debug()`).

---

### Finding 13: VDF-Parser ohne Eingabelaengenbegrenzung

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/stores/steam_utils.py:38-84`
- **Schweregrad:** LOW
- **Typ:** Denial of Service (CWE-400)
- **Beschreibung:** Der VDF-Parser (`parse_vdf()`) liest die gesamte Datei in den Speicher und verarbeitet sie Zeile fuer Zeile. Es gibt keine Begrenzung fuer die Dateigroesse oder die Verschachtelungstiefe. Eine manipulierte `libraryfolders.vdf` mit extremer Groesse oder Tiefe koennte den Parser verlangsamen. Das Risiko ist gering, da die VDF-Dateien von Steam generiert werden und normalerweise klein sind.
- **Empfehlung:** Optional: Dateigroesse vor dem Lesen pruefen (z.B. max 10 MB).

---

### Finding 14: Lutris SQLite-Abfrage — Pfade aus Datenbank werden nicht validiert

- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/stores/lutris_utils.py:71-75`
- **Schweregrad:** LOW
- **Typ:** Path Traversal (CWE-22)
- **Beschreibung:** Pfade aus der Lutris-Datenbank (`directory`-Spalte) werden direkt als `Path(directory)` verwendet. Obwohl `game_path.is_dir()` geprueft wird, koennte ein manipulierter Datenbank-Eintrag auf ein beliebiges Verzeichnis zeigen. Die Lutris-Datenbank gehoert dem User und ist normalerweise vertrauenswuerdig. Das Risiko ist daher gering.
- **Code:**
  ```python
  # lutris_utils.py:71-75
  for service, service_id, name, directory in con.execute(_QUERY):
      if not directory:
          continue
      game_path = Path(directory)
      if game_path.is_dir():
          games[(service, service_id)] = game_path
  ```
- **Empfehlung:** Rein informativ — kein sofortiger Handlungsbedarf. Optional: Pruefen ob Pfade unter erwarteten Verzeichnissen liegen (z.B. `/home/`, `/mnt/`).

---

## Positiv-Befunde

Folgende Aspekte sind korrekt und sicher implementiert:

1. **HTTPS-only API-Kommunikation:** `nexus_api.py` verwendet ausschliesslich `https://api.nexusmods.com/v1` (Zeile 26). Kein `verify=False`, kein HTTP-Fallback.
2. **SSL-Kontext fuer SSO:** `nexus_sso.py` verwendet `ssl.create_default_context()` (Zeile 102) — TLS-Zertifikate werden validiert.
3. **Sichere SQLite-Nutzung:** `lutris_utils.py` oeffnet die Datenbank im Read-Only-Modus (`?mode=ro`, Zeile 69). Keine SQL-Injection moeglich da keine User-Eingaben in die Query fliessen.
4. **JSON-Deserialisierung sicher:** Alle JSON-Operationen verwenden `json.loads()` / `json.dumps()` — kein `pickle`, kein `yaml.load()`, kein `eval()`.
5. **Deploy-Purge-Sicherheit:** Der Deployer prueft beim Purge, ob Symlinks in `.mods/` zeigen (Zeile 362-371), bevor sie geloescht werden.
6. **Subprocess mit Liste statt String:** Alle `subprocess.run()`-Aufrufe verwenden Argument-Listen, keine Shell-Strings. Keine `shell=True`-Nutzung.
7. **Kein hardcoded API-Key:** Kein API-Key oder Secret ist im Quellcode hardcoded.
8. **Rate-Limiting-Tracking:** Nexus API Rate-Limits werden aus Response-Headern gelesen und kommuniziert.
9. **Keine unsichere Deserialisierung:** Kein `pickle`, kein `yaml.load()`, kein `exec()` auf User-Daten.

---

## Gepruefte Dateien

### anvil/plugins/
| Datei | Groesse | Findings |
|-------|---------|----------|
| `__init__.py` | leer | - |
| `base_game.py` | 387 Zeilen | Finding 12 |
| `framework_mod.py` | 39 Zeilen | - |
| `plugin_loader.py` | 234 Zeilen | Finding 2, 11 |
| `games/__init__.py` | leer | - |
| `games/game_cyberpunk2077.py` | 265 Zeilen | - |
| `games/game_baldursgate3.py` | 323 Zeilen | - |
| `games/bg3_mod_handler.py` | 534 Zeilen | Finding 4 |
| `games/game_rdr2.py` | 145 Zeilen | - |
| `games/game_witcher3.py` | 207 Zeilen | - |
| `games/_wip/game_bannerlord.py` | 154 Zeilen | - |
| `games/_wip/game_eldenring.py` | 144 Zeilen | - |
| `games/_wip/game_fallout3.py` | 164 Zeilen | - |
| `games/_wip/game_falloutnv.py` | 176 Zeilen | - |
| `games/_wip/game_morrowind.py` | 183 Zeilen | - |
| `games/_wip/game_oblivion_remastered.py` | 120 Zeilen | - |
| `games/_wip/game_stardewvalley.py` | 171 Zeilen | - |
| `games/_wip/game_skyrimse.py` | 312 Zeilen | - |
| `games/_wip/game_fallout4.py` | 230 Zeilen | - |
| `games/_wip/game_starfield.py` | 241 Zeilen | - |

### anvil/stores/
| Datei | Groesse | Findings |
|-------|---------|----------|
| `__init__.py` | leer | - |
| `steam_utils.py` | 213 Zeilen | Finding 13 |
| `heroic_utils.py` | 210 Zeilen | - |
| `lutris_utils.py` | 130 Zeilen | Finding 14 |
| `bottles_utils.py` | 137 Zeilen | - |
| `store_manager.py` | 167 Zeilen | - |

### anvil/core/ (im Scope)
| Datei | Groesse | Findings |
|-------|---------|----------|
| `nexus_api.py` | 226 Zeilen | Finding 6 |
| `nexus_sso.py` | 352 Zeilen | Finding 8, 9 |
| `mod_installer.py` | 441 Zeilen | Finding 1, 5, 10, 12 |
| `mod_deployer.py` | 430 Zeilen | Finding 7 |
| `bg3_mod_installer.py` (Auszug) | ~930 Zeilen | Finding 1, 5 |

---

## Priorisierte Empfehlungen

### Sofort beheben (CRITICAL):
1. **ZipSlip-Schutz** in `mod_installer.py` und `bg3_mod_installer.py` — Archiv-Eintraege vor `extractall()` validieren
2. **User-Plugin-Sicherheit** — Mindestens Warnung anzeigen wenn User-Plugins geladen werden

### Zeitnah beheben (HIGH):
3. **API-Key-Speicherung** — Auf `keyring`/SecretService migrieren oder zumindest Dateiberechtigungen setzen
4. **defusedxml** fuer XML-Parsing verwenden
5. **Temp-Verzeichnisse** in Instance-Ordner statt `/tmp/` erstellen
6. **Error-Sanitizing** fuer API-Key in Fehlernachrichten

### Bei Gelegenheit (MEDIUM):
7. Symlink-Ziel-Validierung im Deployer
8. WebSocket-Laengenbegrenzung
9. Rekursion in WebSocket-Handler eliminieren
10. Subprocess-Argument-Haertung
11. Module-Name-Kollision verhindern

### Wartung (LOW):
12. Debug-Prints entfernen
13. VDF-Parser-Groessenbegrenzung
14. Lutris-Pfad-Validierung (optional)

---

## Vergleich mit MO2

| Aspekt | MO2 | Anvil | Bewertung |
|--------|-----|-------|-----------|
| API-Key-Speicherung | QSettings (Registry/Windows) | QSettings (INI/Linux) | Anvil schlechter (Klartext-Datei) |
| ZIP-Extraktion | Eigener Extractor mit Pfad-Validierung | `extractall()` ohne Validierung | Anvil schlechter |
| Plugin-System | DLL-basiert mit Manifest | Python-importlib ohne Validierung | Anvil schlechter |
| XML-Parsing | Qt XML-Parser | stdlib ET ohne defusedxml | Vergleichbar |
| Symlink-Deploy | VFS-basiert (in-memory) | Symlinks auf Disk | Unterschiedlicher Ansatz |
| SSO-Login | QtNetwork/QWebSocket | Stdlib ssl+socket | Anvil einfacher, aber funktional |

---

*Report generiert am 2026-02-25 von Agent 3 (Security-Auditor)*
*Keine Dateien wurden geaendert — nur Lesen und Berichten.*
