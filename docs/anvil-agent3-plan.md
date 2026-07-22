# Agent 3: Architektur + Signal-Flow — Endorsement Integration + Category Mapping
Datum: 2026-04-05

## Zusammenfassung

Zwei Nexus-API Features, die auf dem bestehenden Tag-basierten Request/Response-Muster aufbauen:
1. **Feature 1: Endorsement Integration** — Auto-Prompt nach Mod-Installation + POST an Nexus API
2. **Feature 3: Category Mapping** — Nexus-Kategorien laden, cachen, Mods zuordnen (merge statt overwrite)

---

## 1. IST-Zustand Analyse

### 1.1 NexusAPI (nexus_api.py)
- Nur GET-Requests via `_ApiWorker(QThread)`
- Tag-basiertes Routing: `request_finished.emit(tag, data)` / `request_error.emit(tag, message)`
- Rate-Limit-Tracking aus Response-Headers
- **KEIN POST-Support** — muss ergaenzt werden fuer Endorsement

### 1.2 Endorsement-Status
- Wird beim Query Info (`query_mod_info:` Tag) aus API-Response gelesen
- Gespeichert in meta.ini als `endorsed` Feld: "0"=Undecided, "1"=Endorsed, "2"=Abstained, "3"=Unknown
- Angezeigt im ModDetailDialog (Zeile 320-325)
- Filter-Chip `PROP_ENDORSED` ist definiert (filter_panel.py:38) aber **NICHT im Proxy-Filter implementiert** (mod_list.py:306-331 fehlt PROP_ENDORSED und PROP_HAS_NOTES)
- **ModEntry hat KEIN `endorsed` Feld** — wird nur aus meta.ini gelesen
- Kontextmenu: "Endorsement entfernen" (Zeile 2566) und "Kategorie neu zuordnen" (Zeile 2568) sind disabled

### 1.3 Kategorie-System
- `CategoryManager` (categories.py): flat, per-instance `categories.json`
- Default-Kategorien: 17 vordefinierte (Animations, Armor & Clothing, etc.)
- Anvil-eigene IDs (1-17+), NICHT Nexus IDs
- `ModEntry.category_ids`: Liste von Anvil-Kategorie-IDs
- `nexusCategory` in meta.ini: Nexus category_id (numerisch, z.B. "1" = Main)
- FilterPanel zeigt Anvil-Kategorien als Chips
- Kontextmenu hat volle Kategorie-Zuordnung (toggle, primary)
- "Kategorien automatisch zuweisen" ist disabled im Kontextmenu

### 1.4 Settings-Dialog (Nexus-Tab)
- "Endorsement Integration" Checkbox → `_disabled()`, checked=True
- "Nexus-Kategoriezuordnungen" Checkbox → `_disabled()`, checked=True
- Diese muessen aktiviert werden

### 1.5 Installations-Flow
- `_install_archives()` → installiert Mods, schreibt modlist.txt, meta.ini
- Am Ende (Zeile 2169-2199): Update-Check-Queue befuellen wenn Setting aktiv
- **Kein Endorsement-Prompt existiert** — muss komplett neu gebaut werden
- Nach Installation: `_reload_mod_list()` → StatusBar-Meldung → `_schedule_redeploy()`

---

## 2. Feature 1: Endorsement Integration — Architektur

### 2.1 Nexus API v1 Endpunkte

**Endorsement setzen (POST):**
```
POST /v1/games/{game}/mods/{mod_id}/endorse.json
Body: {"Version": "version_string"}
Headers: {"apikey": key, "Content-Type": "application/json"}
Response: {"status": "Endorsed", "message": "..."}
```

**Endorsement entfernen (POST):**
```
POST /v1/games/{game}/mods/{mod_id}/abstain.json
Body: {"Version": "version_string"}
Headers: {"apikey": key, "Content-Type": "application/json"}
Response: {"status": "Abstained", "message": "..."}
```

### 2.2 NexusAPI Erweiterungen (nexus_api.py)

**Neue Methode: `_post()`**
```python
def _post(self, path: str, body: dict, tag: str = "") -> None:
    """Send a POST request via a background QThread."""
    if not self._api_key:
        self.request_error.emit(tag, "Kein API-Schluessel gesetzt.")
        return
    url = API_BASE + path
    headers = {
        "apikey": self._api_key,
        "User-Agent": f"Anvil Organizer/{APP_VERSION}",
        "Content-Type": "application/json",
    }
    worker = _ApiPostWorker(url, headers, body, tag, parent=self)
    worker.finished.connect(self._on_worker_finished)
    worker.error.connect(self._on_worker_error)
    worker.finished.connect(lambda *_: self._cleanup_worker(worker))
    worker.error.connect(lambda *_: self._cleanup_worker(worker))
    self._workers.append(worker)
    worker.start()
```

**Neue Worker-Klasse: `_ApiPostWorker(QThread)`**
```python
class _ApiPostWorker(QThread):
    """Background thread that performs a single HTTP POST request."""
    finished = Signal(str, int, dict, bytes)
    error = Signal(str, str)

    def __init__(self, url, headers, body, tag, parent=None):
        super().__init__(parent)
        self._url = url
        self._headers = headers
        self._body = json.dumps(body).encode("utf-8")
        self._tag = tag

    def run(self) -> None:
        try:
            req = urllib.request.Request(
                self._url, data=self._body,
                headers=self._headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = resp.status
                headers = {k.lower(): v for k, v in resp.getheaders()}
                body = resp.read()
                self.finished.emit(self._tag, status, headers, body)
        except urllib.error.HTTPError as exc:
            # Gleiche Error-Behandlung wie _ApiWorker
            ...
        except Exception as exc:
            self.error.emit(self._tag, str(exc))
```

**Neue API-Methoden:**
```python
def endorse_mod(self, game: str, mod_id: int, version: str = "") -> None:
    """POST /games/{game}/mods/{mod_id}/endorse.json"""
    self._post(
        f"/games/{game}/mods/{mod_id}/endorse.json",
        body={"Version": version},
        tag=f"endorse:{game}:{mod_id}",
    )

def abstain_mod(self, game: str, mod_id: int, version: str = "") -> None:
    """POST /games/{game}/mods/{mod_id}/abstain.json"""
    self._post(
        f"/games/{game}/mods/{mod_id}/abstain.json",
        body={"Version": version},
        tag=f"abstain:{game}:{mod_id}",
    )

def get_game_categories(self, game: str) -> None:
    """GET /games/{game}.json — enthalt categories Array"""
    self._get(f"/games/{game}.json", tag=f"game_categories:{game}")
```

### 2.3 Endorsement-Prompt Dialog (neuer Dialog)

**Neue Datei: `anvil/dialogs/endorsement_dialog.py`**

```python
class EndorsementDialog(QDialog):
    """Dialog nach Mod-Installation: Endorsement anbieten.
    
    Layout:
        [Mod-Icon] "Mod X wurde installiert."
        "Moechtest du diesen Mod auf Nexus endorsen?"
        [  Endorsen  ] [ Spaeter ] [ Nie fuer diesen Mod ]
        [ ] Nicht mehr fragen (global)
    """
    ENDORSE = 1
    LATER = 2
    NEVER = 3
    
    def __init__(self, mod_name: str, mod_id: int, parent=None):
        ...
```

Drei Buttons:
- **Endorsen** → POST endorse.json, endorsed="1" in meta.ini
- **Spaeter** → Nichts tun, kein Eintrag (naechstes Mal wieder fragen)
- **Nie fuer diesen Mod** → endorsed="2" (Abstained) in meta.ini, nie wieder fragen

Checkbox: "Nicht mehr fragen" → Setting `Nexus/endorsement_enabled` = False

### 2.4 Endorsement-Prompt Trigger (mainwindow.py)

**Position:** Am Ende von `_install_archives()`, NACH dem Update-Check-Queue-Code (Zeile 2199+)

```python
# Endorsement prompt (nach Installation)
if (
    installed
    and self._settings().value("Nexus/endorsement_enabled", True, type=bool)
    and self._nexus_api.has_api_key()
    and self._current_plugin
):
    nexus_slug = (
        getattr(self._current_plugin, "GameNexusName", "")
        or getattr(self._current_plugin, "GameShortName", "")
    )
    if nexus_slug:
        self._endorsement_queue = []
        for mod_folder_name in installed:
            for entry in self._current_mod_entries:
                if (entry.name == mod_folder_name
                    and entry.nexus_id > 0):
                    # Nur fragen wenn noch nicht endorsed/abstained
                    meta = read_meta_ini(entry.install_path)
                    endorsed = meta.get("endorsed", "3")
                    if endorsed in ("0", "3"):  # Undecided oder Unknown
                        self._endorsement_queue.append((
                            entry.display_name or entry.name,
                            entry.nexus_id,
                            entry.version,
                            entry.install_path,
                        ))
                    break
        if self._endorsement_queue:
            # Verzoegert anzeigen (nicht waehrend Installation)
            QTimer.singleShot(500, self._show_next_endorsement_prompt)
```

**Neue Methode: `_show_next_endorsement_prompt()`**
```python
def _show_next_endorsement_prompt(self) -> None:
    if not self._endorsement_queue:
        return
    
    name, nexus_id, version, mod_path = self._endorsement_queue.pop(0)
    
    dlg = EndorsementDialog(name, nexus_id, parent=self)
    result = dlg.exec()
    
    nexus_slug = (
        getattr(self._current_plugin, "GameNexusName", "")
        or getattr(self._current_plugin, "GameShortName", "")
    )
    
    if result == EndorsementDialog.ENDORSE:
        # POST an Nexus API
        self._nexus_api.endorse_mod(nexus_slug, nexus_id, version)
        write_meta_ini(mod_path, {"endorsed": "1"})
        self.statusBar().showMessage(
            tr("status.endorsed_mod", name=name), 5000)
    elif result == EndorsementDialog.NEVER:
        # Abstain — nie wieder fragen
        self._nexus_api.abstain_mod(nexus_slug, nexus_id, version)
        write_meta_ini(mod_path, {"endorsed": "2"})
    # LATER: nichts speichern
    
    if dlg.dont_ask_again():
        self._settings().setValue("Nexus/endorsement_enabled", False)
        self._endorsement_queue.clear()
        return
    
    # Naechsten Mod fragen (500ms Pause)
    if self._endorsement_queue:
        QTimer.singleShot(500, self._show_next_endorsement_prompt)
```

### 2.5 Response-Handler (mainwindow.py: _on_nexus_response)

```python
elif tag.startswith("endorse:") and isinstance(data, dict):
    status = data.get("status", "")
    if status == "Endorsed":
        self._log_panel.add_log("info",
            tr("log.endorsement_success", mod_id=tag.split(":")[-1]))
    # Kein Reload noetig — meta.ini ist bereits aktualisiert

elif tag.startswith("abstain:") and isinstance(data, dict):
    # Bestaetigungslog
    self._log_panel.add_log("info",
        tr("log.abstain_success", mod_id=tag.split(":")[-1]))
```

### 2.6 Kontextmenu "Endorsement entfernen" aktivieren

Zeile 2566-2567 aendern:
```python
# ALT:
act = menu.addAction(tr("context.remove_endorsement"))
act.setEnabled(False)

# NEU:
act_remove_endorse = menu.addAction(tr("context.remove_endorsement"))
has_endorsement = (
    single and _ctx_entry and _ctx_entry.nexus_id > 0
    and self._nexus_api.has_api_key()
)
act_remove_endorse.setEnabled(has_endorsement)
```

Handler:
```python
elif chosen == act_remove_endorse:
    self._ctx_remove_endorsement(selected_rows[0])
```

Neue Methode:
```python
def _ctx_remove_endorsement(self, row: int) -> None:
    entry = self._entry_for_row(row)
    if not entry or entry.nexus_id <= 0:
        return
    nexus_slug = (
        getattr(self._current_plugin, "GameNexusName", "")
        or getattr(self._current_plugin, "GameShortName", "")
    )
    self._nexus_api.abstain_mod(nexus_slug, entry.nexus_id, entry.version)
    write_meta_ini(entry.install_path, {"endorsed": "2"})
    self.statusBar().showMessage(
        tr("status.endorsement_removed", name=entry.display_name or entry.name), 5000)
```

### 2.7 ModEntry: `endorsed` Feld ergaenzen

ModEntry braucht ein `endorsed` Feld fuer den Filter:

```python
# mod_entry.py — ModEntry dataclass
endorsed: int = 3  # 0=Undecided, 1=Endorsed, 2=Abstained, 3=Unknown
```

In `_build_entry()`:
```python
endorsed_val = 3
raw_endorsed = meta.get("endorsed", "3")
try:
    endorsed_val = int(raw_endorsed)
except (ValueError, TypeError):
    pass
```

### 2.8 Endorsed-Filter im Proxy (mod_list.py)

Bug-Fix: PROP_ENDORSED muss im filterAcceptsRow implementiert werden:

```python
# In filterAcceptsRow, Zeile 308 — Import ergaenzen:
from anvil.widgets.filter_panel import (
    PROP_ENABLED, PROP_DISABLED, PROP_ENDORSED, PROP_HAS_NOTES,
    PROP_HAS_CATEGORY, PROP_NO_CATEGORY, PROP_CONFLICT_WIN, PROP_CONFLICT_LOSE,
)

# Nach Zeile 316:
if PROP_ENDORSED in self._filter_prop_ids and entry.endorsed == 1:
    match = True
```

### 2.9 Settings-Dialog: Endorsement-Checkbox aktivieren

```python
# ALT (settings_dialog.py Zeile 487-490):
cb = QCheckBox(tr("settings.nexus_endorsement"))
cb.setChecked(True)
_disabled(cb)
opt_left.addWidget(cb)

# NEU:
self._cb_nexus_endorsement = QCheckBox(tr("settings.nexus_endorsement"))
self._cb_nexus_endorsement.setChecked(
    self._settings().value("Nexus/endorsement_enabled", True, type=bool))
opt_left.addWidget(self._cb_nexus_endorsement)
```

In `accept()`:
```python
settings.setValue("Nexus/endorsement_enabled", self._cb_nexus_endorsement.isChecked())
```

---

## 3. Feature 3: Category Mapping — Architektur

### 3.1 Nexus API: Game-Kategorien

**Endpunkt:** `GET /v1/games/{game}.json`

Response enthaelt `categories` Array:
```json
{
  "id": 1230,
  "name": "Skyrim Special Edition",
  "categories": [
    {"category_id": 1, "name": "Skyrim SE Mods", "parent_category": false},
    {"category_id": 2, "name": "Buildings", "parent_category": 1},
    {"category_id": 5, "name": "Gameplay", "parent_category": false},
    {"category_id": 30, "name": "Armour", "parent_category": false},
    ...
  ]
}
```

Jedes Spiel hat eigene Kategorien mit eigenen IDs. Diese Nexus-IDs muessen auf Anvil-Kategorien gemappt werden.

### 3.2 Nexus-Kategorie-Cache

**Neue Datei: `anvil/core/nexus_categories.py`**

```python
class NexusCategoryCache:
    """Cached Nexus game categories per instance.
    
    Speichert: nexus_categories.json in der Instanz
    Format: {
        "game_slug": "skyrimspecialedition",
        "fetched": "2026-04-05T...",
        "categories": [
            {"category_id": 5, "name": "Gameplay", "parent_category": false},
            ...
        ]
    }
    """
    FILENAME = "nexus_categories.json"
    MAX_AGE_DAYS = 30  # Cache fuer 30 Tage
    
    def __init__(self, instance_path: Path):
        self._path = instance_path / self.FILENAME
        self._data: dict = {}
    
    def load(self) -> bool:
        """Load cache from disk. Returns True if valid cache exists."""
        ...
    
    def save(self, game_slug: str, categories: list[dict]) -> None:
        """Save fetched categories to cache."""
        ...
    
    def is_expired(self) -> bool:
        """True if cache is older than MAX_AGE_DAYS."""
        ...
    
    def get_categories(self) -> list[dict]:
        """Return cached Nexus categories."""
        ...
    
    def find_nexus_category(self, nexus_cat_id: int) -> str:
        """Return category name for a Nexus category ID."""
        ...
```

### 3.3 Nexus → Anvil Kategorie-Mapping

**Problem:** Nexus verwendet spiel-spezifische Kategorie-IDs (z.B. Skyrim: 30="Armour", Cyberpunk: 12="Armor"). Anvil hat eigene generische Kategorien (ID 2 = "Armor & Clothing").

**Loesung: Fuzzy Name-Matching + manuelle Mapping-Tabelle**

```python
# In nexus_categories.py

# Vordefinierte Mappings (Nexus-Name → Anvil-Kategorie-Name)
_NEXUS_TO_ANVIL: dict[str, str] = {
    # Exakte und haeufige Mappings
    "animations": "Animations",
    "animation": "Animations",
    "armour": "Armor & Clothing",
    "armor": "Armor & Clothing",
    "clothing": "Armor & Clothing",
    "audio": "Audio",
    "sound": "Audio",
    "music": "Audio",
    "bug fixes": "Bug Fixes",
    "patches": "Patches",
    "gameplay": "Gameplay",
    "graphics": "Graphics",
    "visuals": "Graphics",
    "hair": "Hair & Face",
    "face": "Hair & Face",
    "items": "Items",
    "weapons": "Weapons",
    "miscellaneous": "Miscellaneous",
    "modders resources": "Miscellaneous",
    "models and textures": "Models & Textures",
    "models & textures": "Models & Textures",
    "textures": "Models & Textures",
    "npc": "NPC",
    "companions": "NPC",
    "overhauls": "Overhauls",
    "player homes": "Player Homes",
    "houses": "Player Homes",
    "user interface": "UI",
    "ui": "UI",
    "hud": "UI",
    "utilities": "Utilities",
    "tools": "Utilities",
}

def map_nexus_to_anvil(nexus_name: str) -> str | None:
    """Map a Nexus category name to an Anvil category name.
    
    Returns None if no mapping found (category stays unmapped).
    """
    lower = nexus_name.lower().strip()
    # 1. Exakter Match
    if lower in _NEXUS_TO_ANVIL:
        return _NEXUS_TO_ANVIL[lower]
    # 2. Teilstring-Match (z.B. "Skyrim SE - Armour" → "armour" enthalten)
    for key, anvil_name in _NEXUS_TO_ANVIL.items():
        if key in lower:
            return anvil_name
    return None
```

### 3.4 Kategorie-Zuordnung: Merge-Logik (NICHT ueberschreiben)

**Marcs explizite Anforderung:** MO2 ueberschreibt — Anvil merged.

```python
def assign_nexus_categories(
    mod_path: Path,
    nexus_cat_id: int,
    nexus_cache: NexusCategoryCache,
    category_manager: CategoryManager,
) -> list[int]:
    """Assign Anvil categories based on Nexus category, MERGING with existing.
    
    Returns: Neue komplette category_ids Liste nach Merge.
    
    Logik:
    1. nexus_cat_id → Nexus-Kategoriename (aus Cache)
    2. Nexus-Name → Anvil-Kategoriename (aus Mapping)
    3. Anvil-Name → Anvil-ID (aus CategoryManager)
    4. Wenn Anvil-ID nicht in bestehenden categories → HINZUFUEGEN
    5. Wenn keine Anvil-Kategorie gefunden → neue erstellen
    6. Bestehende Kategorien bleiben IMMER erhalten
    """
    meta = read_meta_ini(mod_path)
    existing_cat_str = meta.get("category", "")
    existing_ids = []
    if existing_cat_str:
        for part in existing_cat_str.split(","):
            try:
                cid = int(part.strip())
                if cid > 0:
                    existing_ids.append(cid)
            except ValueError:
                pass
    
    # Nexus-Kategorie aufloesen
    nexus_name = nexus_cache.find_nexus_category(nexus_cat_id)
    if not nexus_name:
        return existing_ids  # Unbekannte Nexus-Kategorie
    
    anvil_name = map_nexus_to_anvil(nexus_name)
    if not anvil_name:
        # Nexus-Kategorie hat kein Mapping → als neue Anvil-Kategorie erstellen
        anvil_name = nexus_name  # Originalname verwenden
    
    anvil_id = category_manager.get_id(anvil_name)
    if anvil_id == 0:
        # Kategorie existiert nicht → neu erstellen
        anvil_id = category_manager.add_category(anvil_name)
    
    # MERGE: Nur hinzufuegen wenn nicht schon vorhanden
    if anvil_id > 0 and anvil_id not in existing_ids:
        existing_ids.append(anvil_id)
    
    return existing_ids
```

### 3.5 Trigger: Wann werden Nexus-Kategorien geladen?

**Drei Szenarien:**

1. **Bei Instanz-Wechsel (lazy):** Wenn `nexus_categories.json` nicht existiert oder abgelaufen → API-Request im Hintergrund
2. **On-Demand: Kontextmenu "Kategorie neu zuordnen (von Nexus)"** → Fuer einzelnen Mod
3. **On-Demand: Kontextmenu "Kategorien automatisch zuweisen"** → Fuer alle Mods (Batch)

**NICHT bei App-Start** — zu frueh, Instanz ist noch nicht geladen.

### 3.6 Signal-Flow: Nexus-Kategorien laden

```
_apply_instance()
    |
    v
[Instanz geladen, Plugin bekannt]
    |
    v
_load_nexus_categories()
    |
    ├── nexus_categories.json existiert und nicht abgelaufen?
    │     → Ja: Cache verwenden, kein API-Call
    │     → Nein: API-Call starten
    |
    v
nexus_api.get_game_categories(game_slug)
    |
    v
[HTTP GET /v1/games/{game}.json]
    |
    v
_on_nexus_response(tag="game_categories:...", data)
    |
    v
NexusCategoryCache.save(game_slug, data["categories"])
    |
    v
[Cache bereit fuer zukuenftige Zuordnungen]
```

### 3.7 Signal-Flow: "Kategorie neu zuordnen" (Einzelmod)

```
[Rechtsklick auf Mod → "Kategorie neu zuordnen (von Nexus)"]
    |
    v
_ctx_reassign_category(row)
    |
    ├── mod hat nexusCategory in meta.ini?
    │     → Nein: "Keine Nexus-Kategorie bekannt. Zuerst 'Nexus-Info abrufen'."
    │     → Ja: Weiter
    |
    v
[nexusCategory aus meta.ini lesen (z.B. "5")]
    |
    v
assign_nexus_categories(mod_path, nexus_cat_id, cache, category_manager)
    |
    ├── MERGE: Bestehende Kategorien bleiben
    ├── Neue Nexus-Kategorie wird hinzugefuegt
    └── Unbekannte Nexus-Kategorien → neue Anvil-Kategorie erstellt
    |
    v
write_meta_ini(mod_path, {"category": new_cat_str})
    |
    v
_reload_mod_list()
    |
    v
StatusBar: "Kategorie zugeordnet: Gameplay"
```

### 3.8 Signal-Flow: "Kategorien automatisch zuweisen" (Batch)

```
[Kontextmenu → "Alle Mods" → "Kategorien automatisch zuweisen"]
    |
    v
_ctx_auto_assign_categories()
    |
    v
[Pruefe: nexus_categories.json vorhanden?]
    |  → Nein: "Nexus-Kategorien werden geladen..." + API-Call + warten
    |  → Ja: Weiter
    |
    v
[Iteriere ueber alle Mods mit nexusCategory in meta.ini]
    |
    v
Fuer jeden Mod:
    assign_nexus_categories(mod_path, nexus_cat_id, cache, category_manager)
    |
    v
[Ergebnis: X Mods zugeordnet, Y uebersprungen, Z neue Kategorien erstellt]
    |
    v
_reload_mod_list()
FilterPanel.set_categories(...)  [neue Kategorien anzeigen]
    |
    v
StatusBar: "Kategorien zugeordnet: 42 Mods aktualisiert, 3 neue Kategorien"
```

### 3.9 Settings-Dialog: Category-Mapping-Checkbox aktivieren

```python
# ALT (settings_dialog.py Zeile 499-503):
cb = QCheckBox(tr("settings.nexus_category_mapping"))
cb.setChecked(True)
_disabled(cb)
opt_left.addWidget(cb)

# NEU:
self._cb_nexus_category_mapping = QCheckBox(tr("settings.nexus_category_mapping"))
self._cb_nexus_category_mapping.setChecked(
    self._settings().value("Nexus/category_mapping_enabled", True, type=bool))
opt_left.addWidget(self._cb_nexus_category_mapping)
```

In `accept()`:
```python
settings.setValue("Nexus/category_mapping_enabled",
                  self._cb_nexus_category_mapping.isChecked())
```

### 3.10 Kontextmenu aktivieren

Zeile 2568-2569:
```python
# ALT:
act = menu.addAction(tr("context.reassign_category"))
act.setEnabled(False)

# NEU:
act_reassign_cat = menu.addAction(tr("context.reassign_category"))
has_nexus_cat = (
    single and _ctx_entry and _ctx_entry.nexus_id > 0
    and self._nexus_api.has_api_key()
)
act_reassign_cat.setEnabled(has_nexus_cat)
```

Zeile 2359:
```python
# ALT:
act = all_mods_menu.addAction(tr("context.auto_assign_categories"))
act.setEnabled(False)

# NEU:
act_auto_assign = all_mods_menu.addAction(tr("context.auto_assign_categories"))
act_auto_assign.setEnabled(self._nexus_api.has_api_key())
```

---

## 4. Neue Tags fuer Tag-basiertes Routing

| Tag-Format | Feature | Request-Typ | Beschreibung |
|------------|---------|-------------|--------------|
| `endorse:{game}:{mod_id}` | Endorsement | POST | Mod endorsen |
| `abstain:{game}:{mod_id}` | Endorsement | POST | Endorsement entfernen |
| `game_categories:{game}` | Category | GET | Spiel-Kategorien laden |

---

## 5. Neue Dateien

| Datei | Zweck |
|-------|-------|
| `anvil/dialogs/endorsement_dialog.py` | Endorsement-Prompt nach Installation |
| `anvil/core/nexus_categories.py` | Nexus-Kategorie-Cache + Mapping-Logik |

---

## 6. Betroffene bestehende Dateien

| Datei | Aenderung | Umfang |
|-------|-----------|--------|
| `anvil/core/nexus_api.py` | `_ApiPostWorker`, `_post()`, `endorse_mod()`, `abstain_mod()`, `get_game_categories()` | ~60 Zeilen |
| `anvil/core/mod_entry.py` | Neues Feld `endorsed: int = 3` + Parsing in `_build_entry()` | ~10 Zeilen |
| `anvil/widgets/mod_list.py` | `PROP_ENDORSED` Filter implementieren in `filterAcceptsRow()` | ~5 Zeilen |
| `anvil/mainwindow.py` | Endorsement-Queue + Prompt-Trigger + Response-Handler + Kontextmenu aktivieren + Category-Zuordnung | ~120 Zeilen |
| `anvil/widgets/settings_dialog.py` | 2 Checkboxen aktivieren (Endorsement + Category Mapping) | ~15 Zeilen |
| `anvil/widgets/filter_panel.py` | Keine Aenderung (PROP_ENDORSED existiert bereits) | 0 |
| `anvil/core/categories.py` | Keine Aenderung (add_category existiert) | 0 |
| Locale-Dateien (7x) | Neue Keys fuer Endorsement-Dialog + Category-Meldungen | ~15 Keys pro Datei |

---

## 7. Neue Methoden-Signaturen

### nexus_api.py
```python
def _post(self, path: str, body: dict, tag: str = "") -> None
def endorse_mod(self, game: str, mod_id: int, version: str = "") -> None
def abstain_mod(self, game: str, mod_id: int, version: str = "") -> None
def get_game_categories(self, game: str) -> None
```

### mainwindow.py
```python
def _show_next_endorsement_prompt(self) -> None
def _ctx_remove_endorsement(self, row: int) -> None
def _load_nexus_categories(self) -> None
def _ctx_reassign_category(self, row: int) -> None
def _ctx_auto_assign_categories(self) -> None
```

### nexus_categories.py (neue Datei)
```python
class NexusCategoryCache:
    def load(self) -> bool
    def save(self, game_slug: str, categories: list[dict]) -> None
    def is_expired(self) -> bool
    def get_categories(self) -> list[dict]
    def find_nexus_category(self, nexus_cat_id: int) -> str

def map_nexus_to_anvil(nexus_name: str) -> str | None
def assign_nexus_categories(
    mod_path: Path,
    nexus_cat_id: int,
    nexus_cache: NexusCategoryCache,
    category_manager: CategoryManager,
) -> list[int]
```

### endorsement_dialog.py (neue Datei)
```python
class EndorsementDialog(QDialog):
    ENDORSE = 1
    LATER = 2
    NEVER = 3
    def __init__(self, mod_name: str, mod_id: int, parent=None)
    def dont_ask_again(self) -> bool
```

---

## 8. Signal-Flow Diagramm (gesamt)

### Feature 1: Endorsement

```
                     ┌──────────────────────────┐
                     │  _install_archives()      │
                     │  (Mod-Installation)       │
                     └─────────┬────────────────┘
                               │ installed + API key + Setting
                               v
                     ┌──────────────────────────┐
                     │  meta.ini lesen           │
                     │  endorsed in (0, 3)?      │
                     └─────────┬────────────────┘
                               │ Ja → Queue fuellen
                               v
                     ┌──────────────────────────┐
                     │  QTimer(500ms)            │
                     │  _show_next_endorsement_  │
                     │  prompt()                 │
                     └─────────┬────────────────┘
                               │
                               v
                     ┌──────────────────────────┐
                     │  EndorsementDialog        │
                     │  [Endorsen][Spaeter][Nie] │
                     └──┬──────┬──────┬─────────┘
                        │      │      │
           ┌────────────┘      │      └─────────────┐
           v                   v                     v
    ┌─────────────┐   ┌──────────────┐   ┌────────────────┐
    │ POST endorse│   │ (nichts tun) │   │ POST abstain   │
    │ meta.ini:   │   │              │   │ meta.ini:      │
    │ endorsed=1  │   │              │   │ endorsed=2     │
    └──────┬──────┘   └──────────────┘   └───────┬────────┘
           │                                      │
           v                                      v
    ┌─────────────────────────────────────────────────┐
    │ _on_nexus_response("endorse:..." / "abstain:…") │
    │ → Log-Eintrag                                    │
    └──────────────────────────────────────────────────┘
```

### Feature 3: Category Mapping

```
   ┌───────────────────────────┐         ┌──────────────────────────────┐
   │  _apply_instance()        │         │  Kontextmenu                 │
   │  (Instanz-Wechsel)        │         │  "Kategorien zuweisen"       │
   └──────────┬────────────────┘         └──────────┬───────────────────┘
              │                                      │
              v                                      v
   ┌───────────────────────────┐         ┌──────────────────────────────┐
   │  _load_nexus_categories() │         │  _ctx_auto_assign_categories │
   │  Cache pruefen            │         │  oder                        │
   │  → expired/missing?       │         │  _ctx_reassign_category      │
   └──────────┬────────────────┘         └──────────┬───────────────────┘
              │ Nein: Cache nutzen                   │
              │ Ja: API-Call                          │
              v                                      v
   ┌───────────────────────────┐         ┌──────────────────────────────┐
   │  GET /games/{game}.json   │         │  nexus_categories.json laden │
   └──────────┬────���───────────┘         │  nexusCategory aus meta.ini  │
              │                          └──────────┬───────────────────┘
              v                                      │
   ┌───────────────────────────┐                     v
   │  _on_nexus_response       │         ┌��─────────────────────────────┐
   │  ("game_categories:...")   │         │  assign_nexus_categories()   │
   │  → Cache speichern         │         │  1. Nexus-ID → Nexus-Name   │
   └───────────────────────────┘         │  2. Nexus-Name → Anvil-Name │
                                         │  3. MERGE (nicht overwrite)  │
                                         │  4. write_meta_ini()         │
                                         └──────────┬───────────────────┘
                                                     │
                                                     v
                                         ┌──────────────────────────────┐
                                         │  _reload_mod_list()          │
                                         │  FilterPanel aktualisieren   │
                                         └──────────────────────────────┘
```

---

## 9. Risiken und Edge Cases

### Feature 1: Endorsement

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|---------------------|------------|
| Nexus API 403 "Too early to endorse" (Mod muss > 15 Min gespielt sein) | Hoch bei neuen Installationen | Fehler abfangen, Meldung "Mod muss erst gespielt werden", endorsed bleibt "0" |
| Rate Limit bei Batch-Endorsement (viele Mods gleichzeitig installiert) | Mittel | Queue mit 500ms Delay pro Dialog, POST-Requests asynchron |
| User schliesst Dialog mit X statt Button | Niedrig | Dialog.rejected → behandeln wie "Spaeter" |
| Mod hat keine Nexus-ID (manuell installiert) | Haeufig | Nur Mods mit nexus_id > 0 in Queue |
| Premium-User hat auto-endorse auf Nexus aktiviert | Niedrig | Kein Problem — POST gibt "Already endorsed" zurueck |
| endorsed-Feld in meta.ini nicht vorhanden (alte Mods) | Haeufig | Default "3" (Unknown) → wird als "nicht endorsed" behandelt, Prompt erscheint |

### Feature 3: Category Mapping

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|---------------------|------------|
| Nexus-Kategorie hat kein Anvil-Mapping | Mittel (spiel-spezifische Kategorien) | Nexus-Kategorie als neue Anvil-Kategorie erstellen |
| Mod hat nexusCategory=0 (keine Kategorie auf Nexus) | Haeufig | Ueberspringen, bestehende Kategorien beibehalten |
| Game API-Response hat anderes Format als erwartet | Niedrig | Defensiv parsen, bei Fehler abbrechen |
| nexus_categories.json korrupt | Niedrig | JSONDecodeError abfangen, neu laden |
| Mehrere Nexus-Kategorien pro Mod (parent + child) | Haeufig | `category_id` in der Mod-API-Response ist immer nur EINE ID (die primaere) — kein Problem |
| Batch-Zuordnung dauert lange (500+ Mods) | Mittel bei grossen Instanzen | Kein API-Call noetig (nur Cache + meta.ini lesen), Fortschrittsanzeige in StatusBar |
| CategoryManager.add_category() duplikat-sicher? | Pruefung: JA, gibt 0 zurueck wenn Name existiert | Bereits abgesichert |

### Gemeinsam

| Risiko | Mitigation |
|--------|------------|
| Kein API-Key gesetzt | Alle Funktionen pruefen `has_api_key()` zuerst |
| BG3-Instanz (kein normaler Mod-Pfad) | Endorsement: gleicher Flow, mod_path existiert in meta.ini. Categories: meta.ini existiert fuer BG3-Mods |
| Race Condition: API-Response kommt nach Instanz-Wechsel | Tags enthalten game_slug — wenn nicht zur aktuellen Instanz gehoerend, verwerfen |

---

## 10. Neue Locale-Keys

```json
{
    "endorsement_dialog_title": "Mod endorsen?",
    "endorsement_dialog_text": "Moechtest du \"{name}\" auf Nexus Mods endorsen?",
    "endorsement_dialog_endorse": "Endorsen",
    "endorsement_dialog_later": "Spaeter",
    "endorsement_dialog_never": "Nie fuer diesen Mod",
    "endorsement_dialog_dont_ask": "Nicht mehr fragen",
    "status.endorsed_mod": "Endorsed: {name}",
    "status.endorsement_removed": "Endorsement entfernt: {name}",
    "status.categories_assigned": "Kategorien zugeordnet: {count} Mods aktualisiert",
    "status.category_assigned_single": "Kategorie zugeordnet: {category} fuer {name}",
    "status.no_nexus_category": "Keine Nexus-Kategorie bekannt. Zuerst 'Nexus-Info abrufen'.",
    "status.nexus_categories_loaded": "Nexus-Kategorien geladen: {count} Kategorien",
    "status.nexus_categories_loading": "Nexus-Kategorien werden geladen...",
    "log.endorsement_success": "Endorsement gesendet (Mod {mod_id})",
    "log.abstain_success": "Endorsement entfernt (Mod {mod_id})",
    "log.endorsement_error": "Endorsement fehlgeschlagen: {message}"
}
```

---

## 11. Implementierungs-Reihenfolge (Empfehlung)

### Phase 1: Endorsement
1. `nexus_api.py`: `_ApiPostWorker` + `_post()` + `endorse_mod()` + `abstain_mod()`
2. `mod_entry.py`: `endorsed` Feld + Parsing
3. `mod_list.py`: `PROP_ENDORSED` Filter implementieren
4. `endorsement_dialog.py`: Neuer Dialog
5. `mainwindow.py`: Endorsement-Queue + Prompt + Response-Handler + Kontextmenu
6. `settings_dialog.py`: Endorsement-Checkbox aktivieren
7. Locale-Dateien: Neue Keys

### Phase 2: Category Mapping
1. `nexus_api.py`: `get_game_categories()`
2. `nexus_categories.py`: Cache + Mapping-Logik
3. `mainwindow.py`: `_load_nexus_categories()` + Response-Handler + Kontextmenu-Aktionen
4. `settings_dialog.py`: Category-Mapping-Checkbox aktivieren
5. Locale-Dateien: Neue Keys

### Abhaengigkeiten
- Phase 2 haengt NICHT von Phase 1 ab — koennen parallel implementiert werden
- Beide haengen von `nexus_api.py` Erweiterungen ab (aber unterschiedliche Methoden)
- Endorsed-Filter-Fix (PROP_ENDORSED) kann sofort gemacht werden, unabhaengig vom Rest
