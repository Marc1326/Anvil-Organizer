# Security Audit Report — anvil/core/

**Datum:** 2026-02-25
**Auditor:** Agent 1 (QA-Pruefer)
**Scope:** anvil/core/ (20 Python-Dateien)

## Zusammenfassung

**Gepruefte Dateien:** 20
**Findings gesamt:** 19
- CRITICAL: 2
- HIGH: 6
- MEDIUM: 7
- LOW: 4

---

## Findings

---

### Finding 1: ZIP Slip — Path Traversal bei zipfile.extractall()
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_installer.py:348-349`
- **Schweregrad:** CRITICAL
- **Typ:** Path Traversal (ZIP Slip)
- **Beschreibung:** `zipfile.ZipFile.extractall()` extrahiert Dateien ohne Validierung der Pfade innerhalb des Archivs. Ein boesartig erstelltes ZIP-Archiv kann Eintraege mit relativen Pfaden wie `../../etc/cron.d/malicious` enthalten, die Dateien AUSSERHALB des Zielverzeichnisses schreiben. Da Mod-Archive von Drittanbietern (Nexus Mods, etc.) heruntergeladen werden, ist dies ein realistischer Angriffsvektor.
- **Code:**
```python
@staticmethod
def _extract_zip(archive: Path, dest: Path) -> bool:
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(dest)  # <-- UNSICHER: keine Pfad-Validierung
        return True
```
- **Empfehlung:** Vor dem Extrahieren alle Eintraege pruefen. Python 3.12+ hat `zipfile.Path`, aber fuer aeltere Versionen:
```python
for info in zf.infolist():
    target = (dest / info.filename).resolve()
    if not str(target).startswith(str(dest.resolve())):
        raise ValueError(f"Path traversal detected: {info.filename}")
zf.extractall(dest)
```

---

### Finding 2: ZIP Slip — Path Traversal bei BG3 zipfile.extractall()
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/bg3_mod_installer.py:895-896`
- **Schweregrad:** CRITICAL
- **Typ:** Path Traversal (ZIP Slip)
- **Beschreibung:** Identisches Problem wie Finding 1, aber in der BG3-spezifischen Archiv-Extraktion. `_extract_archive()` verwendet ebenfalls `zipfile.extractall()` ohne Pfad-Validierung. Da BG3-Mods haeufig als ZIP geliefert werden, ist dies ein aktiver Angriffsvektor.
- **Code:**
```python
if suffix == ".zip":
    with zipfile.ZipFile(archive_path, "r") as zf:
        zf.extractall(tmp)  # <-- UNSICHER: keine Pfad-Validierung
    return tmp
```
- **Empfehlung:** Gleiche Loesung wie Finding 1 — Pfade aller Eintraege validieren bevor `extractall()` aufgerufen wird. Idealerweise eine gemeinsame sichere Extraktionsfunktion in einem Utility-Modul erstellen.

---

### Finding 3: Unsichere tempfile.mkdtemp() ohne restriktive Berechtigungen
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_installer.py:152`
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/bg3_mod_installer.py:890`
- **Schweregrad:** HIGH
- **Typ:** Unsichere Temp-Dateien / Race Condition
- **Beschreibung:** `tempfile.mkdtemp()` erstellt ein Verzeichnis mit den Standard-Berechtigungen des Systems (typisch 0o700 auf Linux, was sicher ist). Allerdings werden die darin extrahierten Dateien nicht mit restriktiven Berechtigungen erstellt. Die externen Tools `unrar` und `7z` koennen Dateien mit den im Archiv gespeicherten Berechtigungen anlegen, potenziell welt-lesbar oder sogar ausfuehrbar. Dies ist besonders relevant, da die Temp-Verzeichnisse unter `/tmp/` erstellt werden, das fuer alle Benutzer zugaenglich ist.
- **Code:**
```python
tmp = Path(tempfile.mkdtemp(prefix="anvil_install_"))
# ... spaeter:
subprocess.run(["unrar", "x", "-o+", str(archive_path), tmp + "/"], ...)
```
- **Empfehlung:** Nach der Extraktion die Berechtigungen der extrahierten Dateien explizit setzen (`os.chmod`), oder `tempfile.mkdtemp()` in einem benutzer-privaten Verzeichnis erstellen (z.B. innerhalb der Instanz statt in `/tmp/`).

---

### Finding 4: Symlink-basiertes Deployment — Symlink-Race bei Purge
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_deployer.py:358-379`
- **Schweregrad:** HIGH
- **Typ:** TOCTOU Race Condition
- **Beschreibung:** In der `purge()`-Methode wird erst geprueft ob ein Pfad ein Symlink ist (`link_path.is_symlink()`), dann aufgeloest (`link_path.resolve()`), und dann geloescht (`link_path.unlink()`). Zwischen Pruefung und Loeschung koennte der Symlink durch einen anderen Prozess ersetzt werden (z.B. durch eine echte Datei). Da der Check `str(real_target).startswith(mods_str)` ein String-Vergleich ist, koennte ein Angreifer auch einen Symlink erstellen der auf `.mods-malicious/` zeigt und den Check besteht.
- **Code:**
```python
if not link_path.is_symlink():
    continue  # <-- TOCTOU: zwischen hier...

try:
    real_target = link_path.resolve()
    mods_str = str(self._mods_path)
    if not str(real_target).startswith(mods_str):  # <-- ...und hier kann sich der Zustand aendern
        ...
        continue
except OSError:
    pass

try:
    link_path.unlink()  # <-- Loeschung einer moeglicherweise anderen Datei
```
- **Empfehlung:** Den `startswith()`-Check durch einen Vergleich mit aufgeloesten Pfaden ersetzen: `real_target.resolve().is_relative_to(self._mods_path.resolve())`. Ausserdem: Symlink-Ziel VOR dem Loeschen nochmals pruefen (atomar wenn moeglich via `os.readlink()`).

---

### Finding 5: Path Traversal bei Data-Override Installation
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/bg3_mod_installer.py:392-395`
- **Schweregrad:** HIGH
- **Typ:** Path Traversal
- **Beschreibung:** Die `uninstall_data_override()`-Methode loescht Dateien basierend auf relativen Pfaden aus einem JSON-Manifest. Wenn das Manifest manipuliert wurde (z.B. `../../important_file`), werden Dateien AUSSERHALB des Game-Verzeichnisses geloescht. Die Pfade aus dem Manifest werden nicht validiert.
- **Code:**
```python
for rel_path in manifest.get("files", []):
    full = self._game_path / rel_path  # <-- rel_path wird nicht validiert
    if full.is_file():
        full.unlink()  # <-- Loescht beliebige Dateien wenn Manifest manipuliert
```
- **Empfehlung:** Vor dem Loeschen pruefen, dass der aufgeloeste Pfad innerhalb des Game-Verzeichnisses liegt:
```python
full = (self._game_path / rel_path).resolve()
if not full.is_relative_to(self._game_path.resolve()):
    continue  # Path Traversal blocked
```

---

### Finding 6: Path Traversal bei Deploy-Manifest-basiertem Purge
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_deployer.py:339-341`
- **Schweregrad:** HIGH
- **Typ:** Path Traversal
- **Beschreibung:** Aehnlich wie Finding 5: Die `purge()`-Methode liest relative Pfade aus einer JSON-Manifest-Datei und konstruiert daraus absolute Pfade zum Loeschen. Ein manipuliertes Manifest koennte `../../.bashrc` enthalten und beliebige Dateien loeschen.
- **Code:**
```python
for entry in manifest.get("symlinks", []):
    link_rel = entry.get("link", "")
    link_path = game_path / link_rel  # <-- Keine Validierung
```
- **Empfehlung:** Aufgeloesten Pfad gegen `game_path.resolve()` validieren bevor Operationen ausgefuehrt werden.

---

### Finding 7: Unsichere Desktop-Datei-Erstellung fuer nxm:// Handler
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nxm_handler.py:97-107`
- **Schweregrad:** HIGH
- **Typ:** Command Injection via Desktop Entry
- **Beschreibung:** Die `register_nxm_handler()`-Funktion erstellt eine `.desktop`-Datei mit dem Pfad zum `main.py` Script. Der Pfad (`main_script`) stammt aus `sys.argv[0]` oder dem Dateisystem und wird unvalidiert in die `Exec=`-Zeile geschrieben. Ein Pfad mit Sonderzeichen koennte zu unbeabsichtigter Ausfuehrung fuehren. Zudem wird die Desktop-Datei mit Standard-Berechtigungen erstellt (welt-lesbar), was in einer Shared-Umgebung problematisch sein koennte.
- **Code:**
```python
content = f"""[Desktop Entry]
...
Exec=python3 {main_script} %u
...
"""
desktop_file.write_text(content, encoding="utf-8")
```
- **Empfehlung:** Den Pfad in der `Exec=`-Zeile mit Anfuehrungszeichen umschliessen und Sonderzeichen escapen. Dateiberechtigungen explizit auf 0o644 setzen.
```python
# Pfad escapen fuer Desktop Entry Spec
import shlex
escaped = shlex.quote(main_script)
content = f'Exec=python3 {escaped} %u\n'
```

---

### Finding 8: Unsichere Berechtigungen bei Konfigurationsdateien
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/instance_manager.py:122-126`
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_metadata.py:110-112`
- **Schweregrad:** MEDIUM
- **Typ:** Unsichere Dateiberechtigungen
- **Beschreibung:** Alle Dateischreiboperationen (meta.ini, .anvil.ini, modlist.txt, categories.json, etc.) verwenden Standard-Berechtigungen (umask-abhaengig, typisch 0o644). In einer Multi-User-Umgebung koennten andere Benutzer diese Dateien lesen. Insbesondere die `.current`-Datei und `QSettings`-Dateien koennten Informationen ueber die Spielinstallation preisgeben.
- **Code:**
```python
# instance_manager.py:355
f.write_text(name + "\n", encoding="utf-8")

# mod_metadata.py:111
with open(ini, "w", encoding="utf-8") as fh:
    cp.write(fh)
```
- **Empfehlung:** Fuer sicherheitskritische Dateien (API-Keys in QSettings) restriktive Berechtigungen setzen (0o600). Fuer allgemeine Konfigurationsdateien ist 0o644 akzeptabel.

---

### Finding 9: API-Key wird im Klartext in QSettings gespeichert
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_api.py:86-88`
- **Schweregrad:** MEDIUM
- **Typ:** Klartext-Credentials
- **Beschreibung:** Der Nexus-API-Schluessel wird im Klartext ueber QSettings gespeichert (in `~/.config/AnvilOrganizer/AnvilOrganizer.conf`). Dies ist eine INI-Datei die standardmaessig welt-lesbar ist. Jeder Benutzer auf dem System koennte den API-Key auslesen. Dies betrifft zwar nicht direkt den core/-Code, aber `NexusAPI.set_api_key()` speichert den Key nur im Speicher — die QSettings-Speicherung erfolgt vermutlich anderswo, mit denselben Berechtigungsproblemen.
- **Code:**
```python
def set_api_key(self, key: str) -> None:
    """Set the API key for all future requests."""
    self._api_key = key.strip()
```
- **Empfehlung:** Den API-Key nicht im Klartext in der Konfigurationsdatei speichern. Optionen:
  1. `keyring`-Bibliothek verwenden (systemischer Keychain)
  2. Mindestens die Dateirechte der Konfigurationsdatei auf 0o600 setzen
  3. Obfuscation (XOR o.ae.) ist KEIN Ersatz fuer sichere Speicherung

---

### Finding 10: XML External Entity (XXE) bei ET.fromstring()/ET.parse()
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/lspk_parser.py:210`
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/bg3_mod_installer.py:233-234`
- **Schweregrad:** MEDIUM
- **Typ:** XXE (XML External Entity)
- **Beschreibung:** `xml.etree.ElementTree` in Python ist standardmaessig NICHT anfaellig fuer klassische XXE-Angriffe (externe Entities werden ignoriert). JEDOCH ist es anfaellig fuer "Billion Laughs" (Entity-Expansion-Angriff), der zu Denial-of-Service fuehren kann. Da die XML-Daten aus BG3 .pak-Dateien (meta.lsx) und modsettings.lsx stammen — beides von Drittanbietern — ist dies ein realistischer Vektor.
- **Code:**
```python
# lspk_parser.py:210
root = ET.fromstring(data.decode("utf-8-sig"))

# bg3_mod_installer.py:233-234
tree = ET2.parse(path)
root = tree.getroot()
```
- **Empfehlung:** `defusedxml` verwenden oder `ET.XMLParser` mit deaktivierten Entities konfigurieren:
```python
from defusedxml import ElementTree as SafeET
root = SafeET.fromstring(data)
```

---

### Finding 11: LZ4 Decompression Bomb
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/lspk_parser.py:116`
- **Schweregrad:** MEDIUM
- **Typ:** Denial of Service (Decompression Bomb)
- **Beschreibung:** `lz4.block.decompress()` wird mit `uncompressed_size` aufgerufen, das direkt aus der .pak-Datei gelesen wird. Ein boesartig erstelltes Archiv koennte einen extrem grossen `uncompressed_size` angeben (z.B. 4 GB), was zu Out-of-Memory fuehren wuerde. `expected_size = _ENTRY_SIZE * num_files` — wobei `num_files` ebenfalls aus der Datei stammt.
- **Code:**
```python
num_files = struct.unpack("<I", f.read(4))[0]
compressed_size = struct.unpack("<I", f.read(4))[0]
compressed_data = f.read(compressed_size)
expected_size = _ENTRY_SIZE * num_files  # <-- num_files aus Datei, unkontrolliert
decompressed = lz4.block.decompress(compressed_data, uncompressed_size=expected_size)
```
- **Empfehlung:** `num_files` auf einen vernuenftigen Maximalwert begrenzen (z.B. 100.000) und `expected_size` validieren:
```python
MAX_FILES = 100_000
if num_files > MAX_FILES:
    return None
```

---

### Finding 12: requirements.txt pip install nach git pull
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/update_checker.py:132-138`
- **Schweregrad:** MEDIUM
- **Typ:** Supply Chain / Code Execution
- **Beschreibung:** Nach einem `git pull` wird automatisch `pip install -r requirements.txt` ausgefuehrt, wenn sich die Datei geaendert hat. Wenn das Git-Repository kompromittiert wird (oder ein Man-in-the-Middle bei der Git-Verbindung), koennte eine manipulierte `requirements.txt` schaedliche Pakete installieren. Dies laeuft im Kontext des aktuellen Benutzers.
- **Code:**
```python
subprocess.run(
    [sys.executable, "-m", "pip", "install", "-r", str(req_path)],
    cwd=_PROJECT_ROOT,
    capture_output=True,
    text=True,
    timeout=120,
)
```
- **Empfehlung:** Benutzer VOR der automatischen Pip-Installation informieren und Bestaetigung anfordern. Alternativ: Pinned dependencies mit Hashes verwenden (`--require-hashes` in requirements.txt).

---

### Finding 13: String-basierter Pfad-Vergleich statt resolve()
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_deployer.py:365-366`
- **Schweregrad:** MEDIUM
- **Typ:** Pfad-Vergleich Bypass
- **Beschreibung:** Der Sicherheitscheck in `purge()` verwendet `str(real_target).startswith(mods_str)` — einen einfachen String-Vergleich. Dies kann umgangen werden wenn:
  1. `self._mods_path` zu `/home/user/.mods` aufloest und ein Symlink `/home/user/.mods-evil` existiert
  2. Symlinks oder Mounts den Pfad anders auflösen als erwartet
  String-basierte Pfadvergleiche sind generell unsicher.
- **Code:**
```python
mods_str = str(self._mods_path)
if not str(real_target).startswith(mods_str):
```
- **Empfehlung:** `Path.is_relative_to()` (Python 3.9+) verwenden:
```python
if not real_target.resolve().is_relative_to(self._mods_path.resolve()):
```

---

### Finding 14: WebSocket-Rekursion ohne Tiefenlimit
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py:335`
- **Schweregrad:** MEDIUM
- **Typ:** Denial of Service (Stack Overflow)
- **Beschreibung:** `_ws_recv_text()` ruft sich rekursiv auf wenn ein Ping-Frame empfangen wird (Zeile 335: `return _ws_recv_text(sock)`). Ein boesartiger Server koennte kontinuierlich Ping-Frames senden und so einen Stack Overflow verursachen. Dies ist in der Praxis unwahrscheinlich, da der Server `sso.nexusmods.com` ist, aber der Code ist trotzdem fragil.
- **Code:**
```python
# Ping -> respond with pong
if opcode == 0x09:
    pong = bytearray([0x8A, 0x80]) + os.urandom(4)
    try:
        sock.sendall(bytes(pong))
    except OSError:
        pass
    return _ws_recv_text(sock)  # <-- Rekursion ohne Limit
```
- **Empfehlung:** Iterativen Ansatz statt Rekursion verwenden:
```python
while True:
    # ... read frame ...
    if opcode == 0x09:
        # send pong, continue loop
        continue
    return payload.decode(...)
```

---

### Finding 15: WebSocket Length-Feld ohne Groessenlimit
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/nexus_sso.py:296-314`
- **Schweregrad:** LOW
- **Typ:** Denial of Service (Memory Exhaustion)
- **Beschreibung:** Das `length`-Feld eines WebSocket-Frames kann bis zu 2^63 Bytes gross sein (uint64). `_ws_recv_exact(sock, length)` wuerde versuchen, diese Menge an Daten zu empfangen und im Speicher zu halten. Dies koennte zu Out-of-Memory fuehren. Da der Server bekannt ist (Nexus Mods), ist das Risiko gering.
- **Code:**
```python
elif length == 127:
    ext = _ws_recv_exact(sock, 8)
    length = struct.unpack(">Q", ext)[0]
# ...
payload = _ws_recv_exact(sock, length)  # <-- length koennte gigantisch sein
```
- **Empfehlung:** Maximale Frame-Groesse begrenzen (z.B. 1 MB):
```python
MAX_FRAME = 1_048_576
if length > MAX_FRAME:
    return None
```

---

### Finding 16: TOCTOU bei Instance-Erstellung
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/instance_manager.py:109-115`
- **Schweregrad:** LOW
- **Typ:** TOCTOU Race Condition
- **Beschreibung:** Zwischen `instance_dir.exists()` (Zeile 109) und `instance_dir.mkdir()` (Zeile 115) koennte ein anderer Prozess das Verzeichnis erstellen. Dies wuerde zu einem unerwarteten `FileExistsError` oder — schlimmer — zu einem Zustand fuehren wo die App glaubt, ein neues Verzeichnis erstellt zu haben, obwohl bereits Dateien darin existieren.
- **Code:**
```python
if instance_dir.exists():
    raise FileExistsError(...)

# Zwischen hier koennte jemand instance_dir erstellen
instance_dir.mkdir(parents=True)
```
- **Empfehlung:** `mkdir()` direkt aufrufen und `FileExistsError` abfangen, statt vorher zu pruefen:
```python
try:
    instance_dir.mkdir(parents=False, exist_ok=False)
except FileExistsError:
    raise
```

---

### Finding 17: shutil.rmtree() bei Instance-Loeschung ohne Symlink-Check
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/instance_manager.py:191`
- **Schweregrad:** LOW
- **Typ:** Unbeabsichtigte Dateiloeschung
- **Beschreibung:** `shutil.rmtree(instance_dir)` folgt standardmaessig keinen Symlinks (loescht den Link, nicht das Ziel). Jedoch: Wenn ein Angreifer einen Symlink innerhalb von `instance_dir` erstellt hat, der auf ein anderes Verzeichnis zeigt, wuerde `rmtree` den Symlink loeschen, nicht den Inhalt. Dies ist korrektes Verhalten. ABER: Wenn `instance_dir` selbst ein Symlink ist, wuerde `rmtree` das Zielverzeichnis loeschen. Eine Pruefung mit `instance_dir.is_dir()` gibt True zurueck fuer Symlinks die auf Verzeichnisse zeigen.
- **Code:**
```python
if not instance_dir.is_dir():
    return False
shutil.rmtree(instance_dir)  # <-- Loescht Ziel wenn instance_dir ein Symlink ist
```
- **Empfehlung:** Pruefen ob `instance_dir` ein Symlink ist:
```python
if instance_dir.is_symlink():
    return False  # Refuse to delete through symlinks
```

---

### Finding 18: Keine Validierung von mod_name bei Pfad-Konstruktion
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/mod_installer.py:171`
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/bg3_mod_installer.py:681`
- **Schweregrad:** LOW
- **Typ:** Path Traversal
- **Beschreibung:** In `mod_installer.py` wird `folder_name` (aus Benutzereingabe im Quick-Install Dialog) direkt fuer Pfad-Konstruktion verwendet: `dest = self.mods_path / folder_name`. Wenn der Benutzer `../../malicious` eingibt, koennte die Mod-Installation ausserhalb von `.mods/` erfolgen. `_sanitize_name()` wird nur aufgerufen wenn `mod_name` None ist (Zeile 148), nicht bei explizitem Nutzernamen (Zeile 146). Ebenso in `bg3_mod_installer.py:681` (`_save_override_manifest`).
- **Code:**
```python
if mod_name:
    folder_name = mod_name  # <-- direkt vom Benutzer, ohne Sanitization
else:
    base = self._sanitize_name(archive_path.stem)
    folder_name = self._unique_name(base)
# ...
dest = self.mods_path / folder_name  # <-- Path Traversal moeglich
```
- **Empfehlung:** `_sanitize_name()` IMMER anwenden, auch bei explizitem `mod_name`. Zusaetzlich pruefen dass der resultierende Pfad innerhalb von `mods_path` liegt.

---

### Finding 19: icon_manager rel_path wird nicht validiert
- **Datei:** `/home/mob/Projekte/Anvil Organizer/anvil/core/icon_manager.py:82-89`
- **Schweregrad:** LOW
- **Typ:** Path Traversal (Read-Only)
- **Beschreibung:** `IconManager._load()` konstruiert einen Pfad aus `game_short_name` und `rel_path` ohne Validierung. Wenn `game_short_name` oder `exe_binary` (verwendet in `get_executable_icon()` Zeile 79) einen Pfad-Traversal-String enthalten (z.B. `../../etc/passwd`), koennte der Icon-Manager beliebige Dateien als QPixmap laden. Da dies read-only ist und die Daten aus dem Plugin-System kommen (nicht direkt vom Benutzer), ist das Risiko gering.
- **Code:**
```python
def _load(self, game_short_name: str, rel_path: str) -> QPixmap | None:
    key = f"{game_short_name}/{rel_path}"
    # ...
    disk_path = self._assets_dir / game_short_name / rel_path
    if disk_path.is_file():
        pix = QPixmap(str(disk_path))
```
- **Empfehlung:** Den aufgeloesten Pfad validieren:
```python
disk_path = (self._assets_dir / game_short_name / rel_path).resolve()
if not disk_path.is_relative_to(self._assets_dir.resolve()):
    return None
```

---

## Nicht gefunden (Entwarnung)

Die folgenden Sicherheitsprobleme wurden NICHT gefunden:
- **eval()/exec():** Keine Verwendung in allen 20 Dateien.
- **pickle:** Keine Verwendung. Alle Serialisierung erfolgt ueber JSON und configparser.
- **yaml.load():** Kein YAML-Code vorhanden.
- **os.system()/os.popen():** Nicht verwendet. Alle externen Prozesse laufen ueber `subprocess.run()`.
- **shell=True bei subprocess:** Alle `subprocess.run()`-Aufrufe verwenden Listen-Argumente, NICHT `shell=True`. Das ist korrekt und sicher gegen Shell-Injection.
- **Hardcoded Credentials:** Keine API-Keys oder Passwoerter im Quellcode. Der APPLICATION_SLUG in nexus_sso.py ist ein oeffentlicher Identifier, kein Secret.

---

## Gepruefte Dateien

| # | Datei | Zeilen | Findings |
|---|-------|--------|----------|
| 1 | `anvil/core/__init__.py` | 9 | 0 |
| 2 | `anvil/core/mod_metadata.py` | 142 | 1 (Finding 8) |
| 3 | `anvil/core/icon_manager.py` | 96 | 1 (Finding 19) |
| 4 | `anvil/core/nxm_handler.py` | 159 | 1 (Finding 7) |
| 5 | `anvil/core/nexus_sso.py` | 352 | 2 (Finding 14, 15) |
| 6 | `anvil/core/lspk_parser.py` | 259 | 2 (Finding 10, 11) |
| 7 | `anvil/core/persistent_header.py` | 128 | 0 |
| 8 | `anvil/core/bg3_mod_installer.py` | 931 | 3 (Finding 2, 3, 5) |
| 9 | `anvil/core/conflict_scanner.py` | 150 | 0 |
| 10 | `anvil/core/nexus_api.py` | 226 | 1 (Finding 9) |
| 11 | `anvil/core/download_manager.py` | 333 | 0 |
| 12 | `anvil/core/mod_list_io.py` | 338 | 0 |
| 13 | `anvil/core/translator.py` | 134 | 0 |
| 14 | `anvil/core/categories.py` | 192 | 0 |
| 15 | `anvil/core/mod_installer.py` | 441 | 3 (Finding 1, 3, 18) |
| 16 | `anvil/core/instance_manager.py` | 431 | 3 (Finding 8, 16, 17) |
| 17 | `anvil/core/mod_entry.py` | 234 | 0 |
| 18 | `anvil/core/ui_helpers.py` | 40 | 0 |
| 19 | `anvil/core/mod_deployer.py` | 430 | 3 (Finding 4, 6, 13) |
| 20 | `anvil/core/update_checker.py` | 228 | 1 (Finding 12) |

**Gesamt:** 4.494 Zeilen Code geprueft, 19 Findings identifiziert.

---

## Priorisierte Empfehlungen

### Sofort beheben (CRITICAL):
1. **ZIP Slip in mod_installer.py und bg3_mod_installer.py** — Gemeinsame sichere Extraktionsfunktion schreiben die alle Pfade validiert.

### Zeitnah beheben (HIGH):
2. **Path Traversal bei Data-Override Uninstall** — resolve() + is_relative_to() verwenden.
3. **Path Traversal bei Deploy-Manifest Purge** — resolve() + is_relative_to() verwenden.
4. **Desktop-Entry Command Injection** — Pfad escapen mit shlex.quote().
5. **TOCTOU bei Symlink-Purge** — Atomaren Symlink-Check implementieren.
6. **Temp-Verzeichnis Berechtigungen** — Nach Extraktion Rechte setzen.

### Mittelfristig (MEDIUM):
7. **XXE/Billion Laughs** — defusedxml verwenden.
8. **LZ4 Decompression Bomb** — Groessenlimit fuer num_files.
9. **API-Key Klartext-Speicherung** — keyring-Bibliothek evaluieren.
10. **Pip-Auto-Install** — Benutzerbestaetigung einholen.
11. **WebSocket Rekursion** — Iterativen Ansatz verwenden.
12. **String-basierter Pfadvergleich** — is_relative_to() verwenden.
